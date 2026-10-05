"""
MCP Tool: retrieve_evidence
Retrieves supporting evidence from the Qdrant vector knowledge base.
Falls back to live PubMed search when Qdrant is unavailable or empty.
"""
import logging
from typing import Annotated

from fastmcp import Context

from app.mcp.tools.literature_search import search_medical_literature

logger = logging.getLogger(__name__)


async def retrieve_evidence(
    finding: Annotated[str, "The safety finding or concern to find evidence for"],
    medications: Annotated[list[str], "Medications involved in the finding"],
    max_results: Annotated[int, "Maximum evidence items to retrieve"] = 5,
    ctx: Context = None,
) -> dict:
    """
    Retrieve supporting evidence for a medication safety finding.
    Primary: Qdrant vector knowledge base (semantic search over embedded documents).
    Fallback: Live PubMed search when vector DB is unavailable.
    """
    if ctx:
        await ctx.info(f"Retrieving evidence for: {finding[:80]}")

    # Try Qdrant first
    from app.retrieval.retriever import is_qdrant_ready, drug_filtered_search
    try:
        if await is_qdrant_ready():
            if ctx:
                await ctx.info("Using Qdrant vector knowledge base")
            results = await drug_filtered_search(
                query=finding,
                drug_names=medications,
                top_k=max_results,
            )
            if results:
                return {
                    "finding": finding,
                    "medications": medications,
                    "evidence_count": len(results),
                    "evidence": [
                        {
                            "source": e.source,
                            "source_id": e.source_id,
                            "url": e.url,
                            "excerpt": e.excerpt,
                            "support_score": e.support_score,
                            "retrieval_method": "qdrant_vector",
                        }
                        for e in results
                    ],
                    "retrieval_method": "qdrant_vector",
                }
    except Exception as e:
        logger.warning("Qdrant retrieval failed, falling back to PubMed: %s", e)

    # Fallback: live PubMed search
    if ctx:
        await ctx.info("Qdrant unavailable — falling back to PubMed live search")

    query = _build_pubmed_query(finding, medications)
    pubmed_result = await search_medical_literature(query, max_results, ctx)

    articles = pubmed_result.get("articles", [])
    return {
        "finding": finding,
        "medications": medications,
        "evidence_count": len(articles),
        "evidence": [
            {
                "source": a["source"],
                "source_id": a["pmid"],
                "url": a.get("url", ""),
                "excerpt": a.get("title", ""),
                "support_score": a.get("support_score", 0.70),
                "retrieval_method": "pubmed_live",
            }
            for a in articles
        ],
        "retrieval_method": "pubmed_live",
    }


def _build_pubmed_query(finding: str, medications: list[str]) -> str:
    med_str = " ".join(medications[:2])
    keywords = []
    finding_lower = finding.lower()
    if "interaction" in finding_lower:
        keywords.append("drug interaction")
    if "bleeding" in finding_lower:
        keywords.append("bleeding risk")
    if "serotonin" in finding_lower:
        keywords.append("serotonin syndrome")
    if "qt" in finding_lower:
        keywords.append("QT prolongation")
    if "myopathy" in finding_lower or "statin" in finding_lower:
        keywords.append("myopathy rhabdomyolysis")
    keyword_str = " ".join(keywords) if keywords else "safety adverse effects"
    return f"{med_str} {keyword_str}"
