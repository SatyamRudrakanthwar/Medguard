"""
MedGuard Observability — Langfuse tracing with graceful no-op fallback.

When LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY are set in .env, every review
gets a Langfuse trace with spans for each graph node, generations for each
Claude call (with token counts), and tool spans for each MCP call.

When keys are absent or Langfuse is unreachable, every method silently
no-ops so the rest of the application is never affected.
"""
import logging
import time
import contextvars
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Contextvar — threads the current review_id through async graph calls ──────
_current_review_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "obs_review_id", default=""
)

# Active trace contexts keyed by review_id
_active_traces: dict[str, Any] = {}


def set_trace_context(review_id: str) -> None:
    _current_review_id.set(review_id)


def get_trace_context(review_id: str = "") -> Optional["ReviewTrace"]:
    rid = review_id or _current_review_id.get()
    return _active_traces.get(rid)


# ── No-op helpers ─────────────────────────────────────────────────────────────

class _NoopSpan:
    def end(self, **kwargs) -> None:
        pass


class _NoopTrace:
    def span(self, *args, **kwargs) -> _NoopSpan:
        return _NoopSpan()

    def generation(self, *args, **kwargs) -> _NoopSpan:
        return _NoopSpan()

    def update(self, **kwargs) -> None:
        pass


# ── Real trace wrapper ─────────────────────────────────────────────────────────

class ReviewTrace:
    """
    Wraps a Langfuse trace for a single medication review.
    All methods are safe to call even if Langfuse is unavailable.
    """

    def __init__(self, trace: Any, review_id: str):
        self._trace = trace
        self._review_id = review_id

    def node_span(self, node_name: str, input_data: dict, output_data: dict, duration_ms: float) -> None:
        try:
            span = self._trace.span(
                name=f"node:{node_name}",
                input=input_data,
                metadata={"node": node_name, "duration_ms": round(duration_ms)},
            )
            span.end(output=output_data)
        except Exception:
            pass

    def llm_generation(
        self,
        agent_name: str,
        model: str,
        prompt: str,
        output: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
    ) -> None:
        try:
            from langfuse.model import Usage  # type: ignore[import]
            gen = self._trace.generation(
                name=f"llm:{agent_name}",
                model=model,
                model_parameters={"max_tokens": output_tokens},
                input=prompt,
            )
            gen.end(
                output=output,
                usage=Usage(input=input_tokens, output=output_tokens),
                metadata={"duration_ms": round(duration_ms)},
            )
        except ImportError:
            # langfuse.model.Usage may not exist in all versions — use dict
            try:
                gen = self._trace.generation(
                    name=f"llm:{agent_name}",
                    model=model,
                    input=prompt,
                )
                gen.end(
                    output=output,
                    usage={"input": input_tokens, "output": output_tokens},
                    metadata={"duration_ms": round(duration_ms)},
                )
            except Exception:
                pass
        except Exception:
            pass

    def tool_span(self, tool_name: str, input_data: dict, output_data: Any, duration_ms: float) -> None:
        try:
            span = self._trace.span(
                name=f"tool:{tool_name}",
                input=input_data,
                metadata={"tool": tool_name, "duration_ms": round(duration_ms)},
            )
            span.end(output=str(output_data)[:500])
        except Exception:
            pass

    def finish(self, status: str, total_findings: int = 0, retries: int = 0) -> None:
        try:
            self._trace.update(
                output={
                    "status": status,
                    "total_findings": total_findings,
                    "retries": retries,
                },
                metadata={"status": status},
            )
        except Exception:
            pass
        _active_traces.pop(self._review_id, None)


# ── Tracer singleton ───────────────────────────────────────────────────────────

class MedGuardTracer:
    """
    Singleton tracer. Initialises Langfuse once at startup.
    Falls back to no-ops silently when keys are missing or the service is down.
    """

    def __init__(self):
        self._langfuse: Any = None
        self._enabled = False
        self._try_init()

    def _try_init(self) -> None:
        try:
            from app.config.settings import get_settings
            s = get_settings()
            if not s.observability_enabled:
                logger.info("Langfuse not configured — observability disabled")
                return

            from langfuse import Langfuse  # type: ignore[import]
            self._langfuse = Langfuse(
                public_key=s.langfuse_public_key,
                secret_key=s.langfuse_secret_key,
                host=s.langfuse_host,
            )
            self._enabled = True
            logger.info("Langfuse observability enabled (host: %s)", s.langfuse_host)
        except ImportError:
            logger.warning("langfuse package not installed — observability disabled")
        except Exception as exc:
            logger.warning("Langfuse init failed: %s — observability disabled", exc)

    def start_review_trace(
        self,
        review_id: str,
        medications: list[str],
        age: int,
        conditions: list[str],
    ) -> ReviewTrace:
        """Create a Langfuse trace for one review and register it in _active_traces."""
        if not self._enabled or not self._langfuse:
            noop = ReviewTrace(_NoopTrace(), review_id)
            _active_traces[review_id] = noop
            return noop

        try:
            trace = self._langfuse.trace(
                name="medication_review",
                id=review_id,
                metadata={
                    "medications": medications,
                    "patient_age": age,
                    "conditions": conditions,
                    "medication_count": len(medications),
                },
                tags=["medguard", "review"],
            )
            ctx = ReviewTrace(trace, review_id)
            _active_traces[review_id] = ctx
            return ctx
        except Exception as exc:
            logger.warning("Failed to create Langfuse trace: %s", exc)
            noop = ReviewTrace(_NoopTrace(), review_id)
            _active_traces[review_id] = noop
            return noop

    def flush(self) -> None:
        """Flush pending events to Langfuse (call at app shutdown)."""
        if self._enabled and self._langfuse:
            try:
                self._langfuse.flush()
            except Exception:
                pass

    @property
    def enabled(self) -> bool:
        return self._enabled


# Module-level singleton — imported everywhere
tracer = MedGuardTracer()
