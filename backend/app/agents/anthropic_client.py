"""
Anthropic client factory.
Supports two key sources:
  1. ANTHROPIC_API_KEY env var (server-side, for development)
  2. X-API-Key request header (user-supplied from the UI settings page)

The runner sets the contextvar before invoking the graph so every agent
in that request uses the correct key — no global state shared between requests.
"""
import contextvars
import logging
from anthropic import AsyncAnthropic
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# Per-request API key — set by the graph runner before invoking the graph
_request_api_key: contextvars.ContextVar[str] = contextvars.ContextVar(
    "anthropic_api_key", default=""
)


def set_request_api_key(key: str) -> None:
    _request_api_key.set(key)
    # Also wire the provider contextvar so agents auto-detect the right backend
    from app.agents.provider import set_request_provider, detect_provider
    from app.agents.provider import get_request_provider
    if not get_request_provider():
        set_request_provider(detect_provider(key))


def get_api_key() -> str:
    """Returns the request-scoped key, falling back to the env key."""
    return _request_api_key.get() or get_settings().anthropic_api_key


def get_client() -> AsyncAnthropic:
    key = get_api_key()
    if not key:
        raise ValueError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY in .env "
            "or provide it via the Settings page in the UI."
        )
    return AsyncAnthropic(api_key=key)


def llm_available() -> bool:
    return bool(get_api_key())
