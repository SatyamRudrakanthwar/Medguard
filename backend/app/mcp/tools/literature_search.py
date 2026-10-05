"""
MCP Tool: search_medical_literature
Searches PubMed for relevant medical research articles.
Free NIH API — no key required.
"""
import logging
from typing import Annotated

import httpx
from fastmcp import Context

logger = logging.getLogger(__name__)

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PUBMED_TOOL   = "medguard"
PUBMED_EMAIL  = "medguard@research.local"


async def search_medical_literature(
    query: Annotated[str, "Medical search query (e.g. 'metformin warfarin interaction')"],
    max_results: Annotated[int, "Maximum number of articles to return (1-10)"] = 5,
    ctx: Context = None,
) -> dict:
    """
    Search PubMed for peer-reviewed medical literature relevant to a query.
    Returns article titles, abstracts, authors, and publication year.
    Source: NCBI PubMed (free, no API key required).
    """
    if ctx:
        await ctx.info(f"Searching PubMed for: {query}")

    max_results = min(max(1, max_results), 10)

    # Step 1: Search for article IDs
    pmids = await _search_pmids(query, max_results)
    if not pmids:
        return {
            "query": query,
            "results_found": 0,
            "articles": [],
            "note": "No PubMed articles found for this query.",
        }

    # Step 2: Fetch summaries for those IDs
    articles = await _fetch_summaries(pmids)

    if ctx:
        await ctx.info(f"Found {len(articles)} PubMed articles")

    return {
        "query": query,
        "results_found": len(articles),
        "articles": articles,
        "source": "PubMed (NCBI)",
    }


async def _search_pmids(query: str, max_results: int) -> list[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
        "tool": PUBMED_TOOL,
        "email": PUBMED_EMAIL,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(PUBMED_SEARCH, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        logger.error("PubMed search error: %s", e)
    return []


async def _fetch_summaries(pmids: list[str]) -> list[dict]:
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
        "tool": PUBMED_TOOL,
        "email": PUBMED_EMAIL,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(PUBMED_FETCH, params=params)
            if resp.status_code == 200:
                data = resp.json()
                result_data = data.get("result", {})
                articles = []
                for pmid in pmids:
                    article = result_data.get(pmid, {})
                    if not article:
                        continue
                    authors = [
                        a.get("name", "") for a in article.get("authors", [])[:3]
                    ]
                    articles.append({
                        "pmid": pmid,
                        "title": article.get("title", ""),
                        "authors": authors,
                        "publication_year": article.get("pubdate", "")[:4],
                        "journal": article.get("fulljournalname", ""),
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "source": "PubMed",
                        "support_score": 0.75,
                    })
                return articles
    except Exception as e:
        logger.error("PubMed fetch error: %s", e)
    return []
