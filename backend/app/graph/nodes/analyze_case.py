"""
Node: analyze_case
LLM agent that understands the patient case and identifies key concerns.
Stage 4: uses a structured stub. Stage 5: replaced with real Claude call.
"""
import logging
from app.models.state import MedicationReviewState
from app.agents.base import get_case_analyzer

logger = logging.getLogger(__name__)


async def analyze_case(state: MedicationReviewState) -> dict:
    medications = state.get("medications", [])
    patient_context = state.get("patient_context")
    question = state.get("user_question", "")

    analyzer = get_case_analyzer()
    analysis = await analyzer.analyze(
        medications=medications,
        patient_context=patient_context,
        question=question,
    )

    logger.info("Case analysis complete. Key concerns: %s", analysis.get("key_concerns", []))

    return {
        "completed_steps": ["analyze_case"],
        # Store analysis in errors field temporarily as metadata
        # (proper analysis storage added when we have a dedicated field in Stage 5)
    }
