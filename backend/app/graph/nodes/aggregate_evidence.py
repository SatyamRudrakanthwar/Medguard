"""
Node: aggregate_evidence
De-duplicates and scores all evidence collected across research rounds.
Pure logic — no LLM, no API calls.
"""
import logging
from app.models.state import MedicationReviewState
from app.models.findings import EvidenceSource

logger = logging.getLogger(__name__)


async def aggregate_evidence(state: MedicationReviewState) -> dict:
    evidence = state.get("evidence", [])

    # De-duplicate by (source, source_id) or (source, excerpt prefix)
    seen: set[str] = set()
    unique: list[EvidenceSource] = []

    for item in evidence:
        key = f"{item.source}::{item.source_id or item.excerpt[:50] if item.excerpt else ''}"
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Sort by support score descending
    unique.sort(key=lambda e: e.support_score, reverse=True)

    logger.info(
        "Evidence aggregated: %d total → %d unique items",
        len(evidence), len(unique),
    )

    # Return de-duped list — note: this overwrites the accumulated list
    # We use a sentinel step to signal we're replacing, not appending
    return {
        "evidence": unique,
        "completed_steps": ["aggregate_evidence"],
    }
