"""
Graph runner — executes the compiled LangGraph and streams step events.
The stream captures the final report from the last node output so we
never run the graph twice for the same review.
"""
import asyncio
import logging
import time
from typing import Any, AsyncIterator, Optional

from app.graph.graph import compiled_graph
from app.models.patient import Medication, PatientContext
from app.models.review import StreamEvent
from app.models.state import MedicationReviewState
from app.models.report import SafetyReport
from app.agents.anthropic_client import set_request_api_key
from app.agents.provider import set_request_provider
from app.observability import tracer, set_trace_context

logger = logging.getLogger(__name__)


def _serialize(obj: Any, depth: int = 0) -> Any:
    """Recursively convert Pydantic models / dataclasses to JSON-safe dicts."""
    if depth > 4:
        return str(obj)[:200]
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if hasattr(obj, "model_dump"):          # Pydantic v2
        return _serialize(obj.model_dump(), depth + 1)
    if hasattr(obj, "dict"):                # Pydantic v1
        return _serialize(obj.dict(), depth + 1)
    if isinstance(obj, dict):
        return {k: _serialize(v, depth + 1) for k, v in list(obj.items())[:30]}
    if isinstance(obj, (list, tuple)):
        items = [_serialize(i, depth + 1) for i in obj[:20]]
        return items
    return str(obj)[:300]


def _summarise_output(node_name: str, node_output: dict) -> dict:
    """Return a Langfuse-friendly summary of what a node produced."""
    out: dict[str, Any] = {}

    # Keys that are meaningful per node — always include counts/summaries
    count_keys = {
        "drug_information": lambda v: f"{len(v)} drugs fetched",
        "interactions": lambda v: f"{len(v)} interactions",
        "evidence": lambda v: f"{len(v)} evidence items",
        "findings": lambda v: f"{len(v)} findings",
        "validation_results": lambda v: f"{len(v)} validations",
        "completed_steps": lambda v: v,
        "retry_count": lambda v: v,
        "blocked": lambda v: v,
        "block_reason": lambda v: v,
        "evidence_sufficient": lambda v: v,
        "errors": lambda v: v,
    }

    detail_keys = {
        "investigation_plan",
        "medications",
        "patient_context",
        "user_question",
        "final_report",
    }

    for key, value in node_output.items():
        if value is None:
            continue
        if key in count_keys:
            out[key] = count_keys[key](value) if isinstance(value, list) else value
        elif key in detail_keys:
            out[key] = _serialize(value)
        # skip large blobs we didn't list above

    return out


NODE_LABELS: dict[str, str] = {
    "validate_input":        "Validating request...",
    "normalize_medications": "Normalizing medication names...",
    "analyze_case":          "Analyzing patient case...",
    "create_plan":           "Creating investigation plan...",
    "execute_research":      "Running parallel research (drug info, interactions, guidelines)...",
    "aggregate_evidence":    "Aggregating and de-duplicating evidence...",
    "validate_evidence":     "Validating evidence quality...",
    "research_again":        "Evidence insufficient — running supplementary research...",
    "analyze_risk":          "Analyzing risk profile...",
    "generate_report":       "Generating safety report...",
    "blocked_end":           "Request blocked by safety policy.",
}

# Final reports captured from stream — avoids running the graph twice
_completed_reports: dict[str, SafetyReport] = {}


def build_initial_state(
    review_id: str,
    age: int,
    conditions: list[str],
    medications: list[str],
    question: str,
) -> MedicationReviewState:
    return MedicationReviewState(
        review_id=review_id,
        patient_context=PatientContext(age=age, conditions=conditions),
        medications=[Medication(name=m) for m in medications],
        user_question=question,
        investigation_plan=None,
        drug_information=[],
        interactions=[],
        evidence=[],
        validation_results=[],
        evidence_sufficient=False,
        findings=[],
        retry_count=0,
        blocked=False,
        block_reason=None,
        errors=[],
        completed_steps=[],
        final_report=None,
    )


async def run_review(
    review_id: str,
    age: int,
    conditions: list[str],
    medications: list[str],
    question: str,
    api_key: str = "",
    provider: str = "",
) -> SafetyReport:
    """
    Run the full graph via ainvoke and return the final SafetyReport.
    Used for simple (non-streaming) execution.
    """
    if api_key:
        set_request_api_key(api_key)
    if provider:
        set_request_provider(provider)
    initial_state = build_initial_state(review_id, age, conditions, medications, question)
    final_state = await compiled_graph.ainvoke(initial_state)
    report = final_state.get("final_report")
    if not report:
        raise RuntimeError("Graph completed without generating a report")
    return report


async def stream_review(
    review_id: str,
    age: int,
    conditions: list[str],
    medications: list[str],
    question: str,
    api_key: str = "",
    provider: str = "",
) -> AsyncIterator[StreamEvent]:
    """
    Stream the review as it executes.
    Yields one StreamEvent per graph node.
    Captures the final SafetyReport into _completed_reports[review_id]
    so callers can retrieve it after the stream ends — no second graph run needed.
    Records a Langfuse trace with per-node spans (no-ops when not configured).
    """
    if api_key:
        set_request_api_key(api_key)
    if provider:
        set_request_provider(provider)

    # Create Langfuse trace (no-op when keys not configured)
    review_trace = tracer.start_review_trace(
        review_id=review_id,
        medications=medications,
        age=age,
        conditions=conditions,
    )
    set_trace_context(review_id)

    initial_state = build_initial_state(review_id, age, conditions, medications, question)
    final_retry_count = 0
    # track when each node's output first arrives to approximate duration
    node_start_times: dict[str, float] = {}

    try:
        async for chunk in compiled_graph.astream(initial_state, stream_mode="updates"):
            chunk_arrival = time.perf_counter()
            for node_name, node_output in chunk.items():
                if node_name in ("__end__", "__start__"):
                    continue

                # Approximate duration: time since the previous node finished
                t_start = node_start_times.get(node_name, chunk_arrival)
                duration_ms = (chunk_arrival - t_start) * 1000
                node_start_times[node_name] = chunk_arrival

                # Capture the final report as soon as it appears
                if "final_report" in node_output and node_output["final_report"]:
                    _completed_reports[review_id] = node_output["final_report"]

                if "retry_count" in node_output:
                    final_retry_count = node_output["retry_count"]

                label = NODE_LABELS.get(node_name, node_name)
                completed = node_output.get("completed_steps", [])
                retry = node_output.get("retry_count")

                data: dict = {"completed_steps": completed}
                if retry is not None:
                    data["retry_count"] = retry

                # Record the node span in Langfuse with real I/O data
                review_trace.node_span(
                    node_name=node_name,
                    input_data={"node": node_name, "step": label},
                    output_data=_summarise_output(node_name, node_output),
                    duration_ms=duration_ms,
                )

                yield StreamEvent(
                    event="step_completed",
                    step=node_name,
                    message=label,
                    data=data,
                )

                await asyncio.sleep(0)  # yield control to event loop

        # Mark the trace as successful
        report = _completed_reports.get(review_id)
        review_trace.finish(
            status="completed",
            total_findings=len(report.findings) if report else 0,
            retries=final_retry_count,
        )
        yield StreamEvent(event="done", message=review_id)

    except Exception as e:
        logger.exception("Graph execution error for review %s", review_id)
        review_trace.finish(status="failed")
        yield StreamEvent(event="error", message=str(e))


async def get_completed_report(review_id: str) -> Optional[SafetyReport]:
    """Retrieve the report captured during stream_review. Returns None if not ready."""
    return _completed_reports.get(review_id)
