"""
Node: create_plan
LLM agent that creates a structured investigation plan.
Stage 4: structured stub. Stage 5: real Claude call.
"""
import logging
from itertools import combinations
from app.models.state import MedicationReviewState
from app.models.findings import InvestigationPlan
from app.agents.base import get_planner

logger = logging.getLogger(__name__)


async def create_plan(state: MedicationReviewState) -> dict:
    medications = state.get("medications", [])
    patient_context = state.get("patient_context")
    question = state.get("user_question", "")

    planner = get_planner()
    plan = await planner.plan(
        medications=medications,
        patient_context=patient_context,
        question=question,
    )

    logger.info(
        "Investigation plan created. Meds: %d, Pairs: %d, Queries: %d",
        len(plan.medications_to_research),
        len(plan.interactions_to_check),
        len(plan.evidence_queries),
    )

    return {
        "investigation_plan": plan,
        "completed_steps": ["create_plan"],
    }
