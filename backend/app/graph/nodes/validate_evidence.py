"""
Node: validate_evidence
LLM agent that checks whether collected evidence is sufficient to support findings.
Stage 4: structured stub. Stage 5: real Claude call.
Triggers retry if evidence is insufficient and retry budget remains.
"""
import logging
from app.models.state import MedicationReviewState
from app.models.findings import ValidationResult
from app.agents.base import get_evidence_validator

logger = logging.getLogger(__name__)

MIN_EVIDENCE_ITEMS = 2
MIN_AVG_SUPPORT_SCORE = 0.60


async def validate_evidence(state: MedicationReviewState) -> dict:
    evidence = state.get("evidence", [])
    medications = state.get("medications", [])
    interactions = state.get("interactions", [])
    drug_info = state.get("drug_information", [])

    validator = get_evidence_validator()
    result = await validator.validate(
        evidence=evidence,
        medications=medications,
        interactions=interactions,
        drug_info=drug_info,
    )

    sufficient = result["sufficient"]
    validation_results = result.get("validation_results", [])

    if sufficient:
        logger.info("Evidence validated as SUFFICIENT (%d items)", len(evidence))
    else:
        logger.warning(
            "Evidence INSUFFICIENT — retry_count=%d, evidence=%d",
            state.get("retry_count", 0), len(evidence),
        )

    return {
        "evidence_sufficient": sufficient,
        "validation_results": validation_results,
        "completed_steps": ["validate_evidence"],
    }
