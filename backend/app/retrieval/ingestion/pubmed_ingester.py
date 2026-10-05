"""
PubMed ingester — fetches abstracts for high-value drug interaction queries
and embeds them into Qdrant.
"""
import asyncio
import logging
import httpx
from app.retrieval.document_processor import process_pubmed_abstract
from app.retrieval.qdrant_store import upsert_documents

logger = logging.getLogger(__name__)

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_TOOL   = "medguard-ingestion"
PUBMED_EMAIL  = "medguard@research.local"

# High-value drug interaction queries that cover common clinical scenarios
SEED_QUERIES = [
    ("warfarin aspirin bleeding risk", ["warfarin", "aspirin"]),
    ("warfarin drug interactions anticoagulation", ["warfarin"]),
    ("metformin lactic acidosis contrast media", ["metformin"]),
    ("statin myopathy rhabdomyolysis CYP3A4", ["simvastatin", "atorvastatin"]),
    ("SSRI serotonin syndrome drug interaction", ["sertraline", "fluoxetine"]),
    ("ACE inhibitor hyperkalemia potassium", ["lisinopril", "enalapril"]),
    ("fluoroquinolone QT prolongation", ["ciprofloxacin", "levofloxacin"]),
    ("NSAIDs renal function blood pressure", ["ibuprofen", "naproxen"]),
    ("clopidogrel PPI drug interaction proton pump", ["clopidogrel", "omeprazole"]),
    ("beta blocker diabetes hypoglycemia masking", ["metoprolol"]),
    ("lisinopril amlodipine hypertension combination", ["lisinopril", "amlodipine"]),
    ("aspirin cardiovascular secondary prevention", ["aspirin"]),
    ("metformin type 2 diabetes renal function eGFR", ["metformin"]),
]


async def ingest_pubmed_abstracts(queries: list[tuple] | None = None) -> int:
    """
    Search PubMed and embed abstracts for given queries.
    Each query is a (search_string, drug_names_list) tuple.
    Returns total chunk count stored.
    """
    targets = queries or SEED_QUERIES
    total = 0

    for query_str, drug_names in targets:
        try:
            pmids = await _search_pmids(query_str, max_results=5)
            if not pmids:
                logger.warning("No PubMed results for: %s", query_str)
                continue

            abstracts = await _fetch_abstracts(pmids)
            documents = []
            for pmid, title, abstract in abstracts:
                docs = process_pubmed_abstract(pmid, title, abstract, drug_names)
                documents.extend(docs)

            if documents:
                stored = await upsert_documents(documents)
                total += stored
                logger.info("Ingested '%s': %d abstracts → %d chunks", query_str[:50], len(abstracts), stored)

            await asyncio.sleep(0.4)  # respect NCBI rate limit

        except Exception as e:
            logger.error("PubMed ingestion error for '%s': %s", query_str, e)

    return total


async def _search_pmids(query: str, max_results: int) -> list[str]:
    params = {
        "db": "pubmed", "term": query, "retmax": max_results,
        "retmode": "json", "sort": "relevance",
        "tool": PUBMED_TOOL, "email": PUBMED_EMAIL,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(PUBMED_SEARCH, params=params)
        if resp.status_code == 200:
            return resp.json().get("esearchresult", {}).get("idlist", [])
    return []


async def _fetch_abstracts(pmids: list[str]) -> list[tuple[str, str, str]]:
    """Returns list of (pmid, title, abstract) tuples."""
    params = {
        "db": "pubmed", "id": ",".join(pmids), "rettype": "abstract",
        "retmode": "xml", "tool": PUBMED_TOOL, "email": PUBMED_EMAIL,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(PUBMED_FETCH, params=params)
            if resp.status_code != 200:
                return []
            return _parse_pubmed_xml(resp.text, pmids)
    except Exception as e:
        logger.error("PubMed fetch error: %s", e)
        return []


def _parse_pubmed_xml(xml: str, pmids: list[str]) -> list[tuple[str, str, str]]:
    import re
    results = []
    articles = re.findall(r"<PubmedArticle>(.*?)</PubmedArticle>", xml, re.DOTALL)
    for article in articles:
        # Extract PMID
        pmid_match = re.search(r"<PMID[^>]*>(\d+)</PMID>", article)
        pmid = pmid_match.group(1) if pmid_match else "unknown"

        # Extract title
        title_match = re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", article, re.DOTALL)
        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""

        # Extract abstract
        abstract_matches = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", article, re.DOTALL)
        abstract = " ".join(
            re.sub(r"<[^>]+>", "", m).strip() for m in abstract_matches
        )

        if title:
            results.append((pmid, title, abstract))
    return results
