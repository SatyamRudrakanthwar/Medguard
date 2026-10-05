"""
MedGuard LangGraph — compiles the full medication safety review workflow.

Flow:
  START
    → validate_input
        → [blocked]  → END
        → [ok]       → normalize_medications
    → analyze_case
    → create_plan
    → execute_research
    → aggregate_evidence
    → validate_evidence
        → [sufficient | max_retries] → analyze_risk
        → [insufficient]             → research_again → aggregate_evidence
    → analyze_risk
    → generate_report
    → END
"""
from langgraph.graph import StateGraph, START, END

from app.models.state import MedicationReviewState
from app.graph.nodes import (
    validate_input,
    normalize_medications,
    analyze_case,
    create_plan,
    execute_research,
    aggregate_evidence,
    validate_evidence,
    research_again,
    analyze_risk,
    generate_report,
)
from app.config.settings import get_settings

settings = get_settings()


def _route_after_input(state: MedicationReviewState) -> str:
    if state.get("blocked"):
        return "blocked_end"
    return "normalize_medications"


def _route_after_validation(state: MedicationReviewState) -> str:
    if state.get("evidence_sufficient"):
        return "analyze_risk"
    if state.get("retry_count", 0) >= settings.max_research_retries:
        return "analyze_risk"   # proceed with whatever we have
    return "research_again"


async def _blocked_end(state: MedicationReviewState) -> dict:
    """Terminal node when safety layer blocks the request."""
    from app.models.report import SafetyReport
    import uuid

    meds = state.get("medications", [])
    patient = state.get("patient_context")

    report = SafetyReport(
        review_id=state.get("review_id", str(uuid.uuid4())),
        medications_reviewed=[m.name for m in meds],
        patient_age=patient.age if patient else 0,
        patient_conditions=patient.conditions if patient else [],
        findings=[],
        additional_information=[state.get("block_reason", "Request blocked by safety policy.")],
    )
    return {"final_report": report, "completed_steps": ["blocked_end"]}


def build_graph() -> StateGraph:
    builder = StateGraph(MedicationReviewState)

    # Register all nodes
    builder.add_node("validate_input", validate_input)
    builder.add_node("blocked_end", _blocked_end)
    builder.add_node("normalize_medications", normalize_medications)
    builder.add_node("analyze_case", analyze_case)
    builder.add_node("create_plan", create_plan)
    builder.add_node("execute_research", execute_research)
    builder.add_node("aggregate_evidence", aggregate_evidence)
    builder.add_node("validate_evidence", validate_evidence)
    builder.add_node("research_again", research_again)
    builder.add_node("analyze_risk", analyze_risk)
    builder.add_node("generate_report", generate_report)

    # Edges — linear flow
    builder.add_edge(START, "validate_input")
    builder.add_conditional_edges(
        "validate_input",
        _route_after_input,
        {"blocked_end": "blocked_end", "normalize_medications": "normalize_medications"},
    )
    builder.add_edge("blocked_end", END)
    builder.add_edge("normalize_medications", "analyze_case")
    builder.add_edge("analyze_case", "create_plan")
    builder.add_edge("create_plan", "execute_research")
    builder.add_edge("execute_research", "aggregate_evidence")
    builder.add_edge("aggregate_evidence", "validate_evidence")

    # Conditional routing — retry loop
    builder.add_conditional_edges(
        "validate_evidence",
        _route_after_validation,
        {"analyze_risk": "analyze_risk", "research_again": "research_again"},
    )
    builder.add_edge("research_again", "aggregate_evidence")  # loop back
    builder.add_edge("analyze_risk", "generate_report")
    builder.add_edge("generate_report", END)

    return builder


# Compiled graph — import this in the runner
compiled_graph = build_graph().compile()
