"""
Node: research_again
Retry node — performs targeted supplementary research when evidence is insufficient.
Increments retry_count. Hard-limited by MAX_RESEARCH_RETRIES in settings.
"""
import logging
from app.models.state import MedicationReviewState
from app.models.findings import EvidenceSource
from app.mcp.client import mcp_client

logger = logging.getLogger(__name__)


async def research_again(state: MedicationReviewState) -> dict:
    retry_count = state.get("retry_count", 0) + 1
    medications = state.get("medications", [])
    question = state.get("user_question", "")
    existing_evidence = state.get("evidence", [])

    med_names = [m.normalized_name or m.name for m in medications]

    logger.info("Retry research attempt #%d for medications: %s", retry_count, med_names)

    # Build a more targeted query based on what's missing
    # Focus on interactions and adverse effects for this retry
    new_evidence: list[EvidenceSource] = []

    for i, drug_a in enumerate(med_names):
        for drug_b in med_names[i + 1:]:
            query = f"{drug_a} {drug_b} adverse effects contraindications"
            try:
                result = await mcp_client.search_medical_literature(query, max_results=3)
                for article in result.get("articles", []):
                    pmid = article.get("pmid", "")
                    # Skip if already in evidence
                    if any(e.source_id == pmid for e in existing_evidence):
                        continue
                    new_evidence.append(EvidenceSource(
                        source="PubMed",
                        source_id=pmid,
                        url=article.get("url"),
                        support_score=article.get("support_score", 0.70),
                        excerpt=article.get("title", ""),
                    ))
            except Exception as e:
                logger.warning("Retry literature search failed: %s", e)

    # Also retry guidelines with broader query
    try:
        guideline_result = await mcp_client.search_guidelines(med_names, query=question)
        for g in guideline_result.get("curated_guidelines", []):
            excerpt = g.get("guideline", "")
            if not any(e.excerpt == excerpt[:400] for e in existing_evidence):
                new_evidence.append(EvidenceSource(
                    source=g.get("source", "Clinical Guideline"),
                    support_score=0.90,
                    excerpt=excerpt[:400],
                ))
    except Exception as e:
        logger.warning("Retry guideline search failed: %s", e)

    logger.info("Retry #%d found %d new evidence items", retry_count, len(new_evidence))

    return {
        "retry_count": retry_count,
        "evidence": new_evidence,  # appended via operator.add reducer
        "completed_steps": [f"research_again_attempt_{retry_count}"],
    }
