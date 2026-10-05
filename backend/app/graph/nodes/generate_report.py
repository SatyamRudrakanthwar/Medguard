"""
Node: generate_report
Pure assembly — no LLM. Compiles all validated findings into a SafetyReport.
"""
import logging
import uuid
from app.models.state import MedicationReviewState
from app.models.report import SafetyReport

logger = logging.getLogger(__name__)


async def generate_report(state: MedicationReviewState) -> dict:
    findings = state.get("findings", [])
    evidence = state.get("evidence", [])
    medications = state.get("medications", [])
    patient_context = state.get("patient_context")
    review_id = state.get("review_id", str(uuid.uuid4()))
    completed_steps = state.get("completed_steps", [])

    med_names = [m.normalized_name or m.name for m in medications]

    additional_info = []
    if state.get("retry_count", 0) > 0:
        additional_info.append(
            f"Note: Additional research was performed ({state['retry_count']} retry attempt(s)) "
            "to ensure adequate evidence coverage."
        )
    if not findings:
        additional_info.append(
            "No specific safety concerns were identified based on available data. "
            "This does not guarantee the medication combination is safe for your situation."
        )

    report = SafetyReport(
        review_id=review_id,
        medications_reviewed=med_names,
        patient_age=patient_context.age if patient_context else 0,
        patient_conditions=patient_context.conditions if patient_context else [],
        findings=findings,
        evidence_summary=evidence[:10],
        additional_information=additional_info,
        research_retries=state.get("retry_count", 0),
        agent_steps_completed=[s for s in completed_steps if s],
    )

    logger.info(
        "Report generated: %d findings, %d evidence items, %d steps",
        len(findings), len(evidence), len(completed_steps),
    )

    return {
        "final_report": report,
        "completed_steps": ["generate_report"],
    }
