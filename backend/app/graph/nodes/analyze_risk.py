"""
Node: analyze_risk
LLM agent that synthesizes all research into structured SafetyFindings.
Stage 4: structured stub that uses curated guideline matches + interaction data.
Stage 5: real Claude call.
"""
import logging
from app.models.state import MedicationReviewState
from app.agents.base import get_risk_analyzer

logger = logging.getLogger(__name__)


async def analyze_risk(state: MedicationReviewState) -> dict:
    medications = state.get("medications", [])
    drug_information = state.get("drug_information", [])
    interactions = state.get("interactions", [])
    evidence = state.get("evidence", [])
    patient_context = state.get("patient_context")
    question = state.get("user_question", "")

    analyzer = get_risk_analyzer()
    findings = await analyzer.analyze(
        medications=medications,
        drug_information=drug_information,
        interactions=interactions,
        evidence=evidence,
        patient_context=patient_context,
        question=question,
    )

    logger.info(
        "Risk analysis complete: %d findings (%d high/critical)",
        len(findings),
        sum(1 for f in findings if f.severity.value in ("high", "critical")),
    )

    return {
        "findings": findings,
        "completed_steps": ["analyze_risk"],
    }
