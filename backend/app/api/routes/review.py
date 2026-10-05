import uuid
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Request
from fastapi.responses import StreamingResponse

from app.models import ReviewRequest, ReviewResponse, ReviewStatus, StreamEvent
from app.graph.runner import stream_review, get_completed_report
from app.safety import safety_engine, rate_limiter
from app.services.event_stream import ReviewEventStream
from app.agents.provider import set_request_provider, detect_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/review", tags=["review"])

# In-memory store — each entry holds response, request, api_key, and event stream
_store: dict[str, dict] = {}


@router.post("", response_model=ReviewResponse, status_code=202)
async def create_review(
    raw_request: Request,
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(default=None),
    x_provider: Optional[str] = Header(default=None),
) -> ReviewResponse:
    """
    Submit a medication safety review.
    Returns 202 immediately; connect to GET /review/{id}/stream for live progress.
    Poll GET /review/{id} for the final result once status != processing.
    """
    # Rate limiting by IP before any work
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    allowed, remaining = rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 10 reviews per hour.",
        )

    # Deterministic safety policy check — no LLM call yet
    safety_result = safety_engine.check_request(request.question, request.medications)

    review_id = str(uuid.uuid4())
    event_stream = ReviewEventStream(review_id)

    if not safety_result.passed:
        response = ReviewResponse(
            review_id=review_id,
            status=ReviewStatus.blocked,
            message=safety_result.reason,
            medications_reviewed=request.medications,
            additional_information=[safety_result.reason],
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        _store[review_id] = {"response": response, "stream": event_stream}
        event_stream.publish(StreamEvent(event="error", message=safety_result.reason))
        return response

    # Use sanitized inputs from the safety engine
    sanitized = ReviewRequest(
        age=request.age,
        conditions=request.conditions,
        medications=safety_result.sanitized_medications,
        question=safety_result.sanitized_question,
    )

    response = ReviewResponse(
        review_id=review_id,
        status=ReviewStatus.processing,
        message="Review accepted. Connect to /stream for live progress.",
        medications_reviewed=sanitized.medications,
        created_at=datetime.utcnow(),
    )
    # Resolve provider: explicit header > auto-detect from key
    resolved_provider = detect_provider(x_api_key or "", hint=x_provider or "")

    _store[review_id] = {
        "response": response,
        "request": sanitized,
        "api_key": x_api_key or "",
        "provider": resolved_provider,
        "stream": event_stream,
    }

    background_tasks.add_task(_run_review, review_id)
    return response


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str) -> ReviewResponse:
    """Retrieve a review by ID. Poll until status is 'completed', 'failed', or 'blocked'."""
    entry = _store.get(review_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")
    return entry["response"]


@router.get("/{review_id}/stream")
async def stream_review_sse(review_id: str) -> StreamingResponse:
    """
    Server-Sent Events stream.
    Late connections replay all past events before streaming new ones.
    """
    entry = _store.get(review_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")

    event_stream: ReviewEventStream = entry["stream"]

    async def event_generator():
        async for event in event_stream.subscribe():
            yield f"data: {event.model_dump_json()}\n\n"
            if event.event in ("done", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=list[ReviewResponse])
async def list_reviews() -> list[ReviewResponse]:
    """List the 20 most recent reviews (newest first)."""
    reviews = [e["response"] for e in _store.values()]
    return sorted(reviews, key=lambda r: r.created_at, reverse=True)[:20]


async def _run_review(review_id: str) -> None:
    """
    Background task — single graph execution.
    stream_review() streams step events AND captures the final report
    into the runner's _completed_reports dict. We fetch it from there;
    no second graph run is needed.
    """
    entry = _store.get(review_id)
    if not entry:
        return

    req: ReviewRequest = entry["request"]
    api_key: str = entry.get("api_key", "")
    provider: str = entry.get("provider", "")
    event_stream: ReviewEventStream = entry["stream"]

    try:
        # Run the graph once — events are published as each node completes
        async for event in stream_review(
            review_id=review_id,
            age=req.age,
            conditions=req.conditions,
            medications=req.medications,
            question=req.question,
            api_key=api_key,
            provider=provider,
        ):
            event_stream.publish(event)

        # The stream captured the final report — no second graph run
        report = await get_completed_report(review_id)
        if not report:
            raise RuntimeError("Graph completed without producing a report")

        # Validate LLM output through the safety engine before storing
        clean_findings = safety_engine.validate_findings(report.findings)

        entry["response"] = ReviewResponse(
            review_id=review_id,
            status=ReviewStatus.completed,
            medications_reviewed=report.medications_reviewed,
            findings=clean_findings,
            evidence=report.evidence_summary,
            additional_information=report.additional_information,
            high_severity_count=report.high_severity_count,
            created_at=entry["response"].created_at,
            completed_at=datetime.utcnow(),
            disclaimer=report.disclaimer,
        )
        logger.info("Review %s completed: %d findings", review_id, report.total_findings)

    except Exception as e:
        logger.exception("Review %s failed", review_id)
        entry["response"].status = ReviewStatus.failed
        entry["response"].message = f"Review failed: {str(e)}"
        event_stream.publish(StreamEvent(event="error", message=str(e)))
