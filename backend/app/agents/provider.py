"""
Multi-provider LLM abstraction.

Supports: Anthropic Claude, OpenAI (GPT-4o etc.), Google Gemini,
          Ollama (local, no key), HuggingFace Inference API.

Provider is auto-detected from the API key format, or overridden
via the X-Provider request header.

All providers share the same interface:
    call_structured(messages, tool_name, tool_schema, system, max_tokens)
    → dict  (the structured JSON the LLM returned)

If a provider package is not installed or the call fails, a
ProviderError is raised so the agent can fall back to stub.
"""
import contextvars
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Per-request provider override — set alongside the API key by the runner
_request_provider: contextvars.ContextVar[str] = contextvars.ContextVar(
    "llm_provider", default=""
)


def set_request_provider(provider: str) -> None:
    _request_provider.set(provider.lower().strip())


def get_request_provider() -> str:
    return _request_provider.get()


class ProviderError(Exception):
    pass


# ── Auto-detection ─────────────────────────────────────────────────────────────

def detect_provider(api_key: str, hint: str = "") -> str:
    """
    Returns a provider name given an API key and optional hint.
    hint is the value of X-Provider header (e.g. "openai", "gemini").
    """
    if hint:
        return hint.lower()
    if not api_key:
        return "stub"
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    if api_key.startswith("sk-"):
        return "openai"
    if api_key.startswith("AIza"):
        return "gemini"
    if api_key.startswith("hf_"):
        return "huggingface"
    if api_key.lower() in ("ollama", "local", "none"):
        return "ollama"
    # Unknown format — assume Anthropic (most common)
    return "anthropic"


# ── Providers ─────────────────────────────────────────────────────────────────

async def _call_anthropic(
    api_key: str,
    messages: list[dict],
    tool_name: str,
    tool_schema: dict,
    system: str,
    max_tokens: int,
) -> dict:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        tools=[{"name": tool_name, "description": tool_schema.get("description", ""), "input_schema": tool_schema}],
        tool_choice={"type": "tool", "name": tool_name},
        messages=messages,
    )
    for block in response.content:
        if block.type == "tool_use":
            return {
                "result": block.input,
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }
    raise ProviderError("Anthropic did not return tool_use block")


async def _call_openai(
    api_key: str,
    messages: list[dict],
    tool_name: str,
    tool_schema: dict,
    system: str,
    max_tokens: int,
    base_url: str = "",
) -> dict:
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise ProviderError("openai package not installed — run: pip install openai")

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = AsyncOpenAI(**kwargs)
    all_messages = [{"role": "system", "content": system}] + messages
    model = "gpt-4o-mini" if not base_url else "llama3.1"  # Ollama default

    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=all_messages,
        tools=[{
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_schema.get("description", ""),
                "parameters": {
                    k: v for k, v in tool_schema.items()
                    if k not in ("description",)
                },
            },
        }],
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )
    msg = response.choices[0].message
    if msg.tool_calls:
        return {
            "result": json.loads(msg.tool_calls[0].function.arguments),
            "input_tokens": getattr(response.usage, "prompt_tokens", 0),
            "output_tokens": getattr(response.usage, "completion_tokens", 0),
        }
    raise ProviderError("OpenAI did not return a tool call")


async def _call_ollama(
    messages: list[dict],
    tool_name: str,
    tool_schema: dict,
    system: str,
    max_tokens: int,
) -> dict:
    """Ollama — runs locally, no API key needed."""
    return await _call_openai(
        api_key="ollama",
        messages=messages,
        tool_name=tool_name,
        tool_schema=tool_schema,
        system=system,
        max_tokens=max_tokens,
        base_url="http://localhost:11434/v1",
    )


async def _call_gemini(
    api_key: str,
    messages: list[dict],
    tool_name: str,
    tool_schema: dict,
    system: str,
    max_tokens: int,
) -> dict:
    try:
        import google.generativeai as genai
    except ImportError:
        raise ProviderError("google-generativeai package not installed — run: pip install google-generativeai")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system,
        tools=[genai.protos.Tool(
            function_declarations=[genai.protos.FunctionDeclaration(
                name=tool_name,
                description=tool_schema.get("description", ""),
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        k: genai.protos.Schema(type=genai.protos.Type.STRING)
                        for k in tool_schema.get("properties", {})
                    },
                ),
            )]
        )],
    )
    # Convert messages to Gemini format
    history = []
    for m in messages:
        history.append({"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]})

    chat = model.start_chat(history=history[:-1] if len(history) > 1 else [])
    response = await chat.send_message_async(
        history[-1]["parts"][0] if history else "",
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
    )
    for part in response.parts:
        if fn := getattr(part, "function_call", None):
            return {
                "result": dict(fn.args),
                "input_tokens": 0,
                "output_tokens": 0,
            }
    raise ProviderError("Gemini did not return a function call")


async def _call_huggingface(
    api_key: str,
    messages: list[dict],
    tool_name: str,
    tool_schema: dict,
    system: str,
    max_tokens: int,
) -> dict:
    """
    HuggingFace Inference API — uses the chat_completion endpoint.
    Works with models that support tool use (Mixtral, Llama-3.1, etc.).
    Falls back to JSON-mode prompting for models without tool support.
    """
    try:
        from huggingface_hub import AsyncInferenceClient
    except ImportError:
        raise ProviderError("huggingface_hub not installed — run: pip install huggingface_hub")

    client = AsyncInferenceClient(
        model="meta-llama/Meta-Llama-3-8B-Instruct",
        token=api_key,
    )
    all_messages = [{"role": "system", "content": system}] + messages

    # Try tool calling first
    try:
        response = await client.chat_completion(
            messages=all_messages,
            tools=[{
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_schema.get("description", ""),
                    "parameters": {k: v for k, v in tool_schema.items() if k != "description"},
                },
            }],
            tool_choice="auto",
            max_tokens=max_tokens,
        )
        msg = response.choices[0].message
        if msg.tool_calls:
            return {
                "result": json.loads(msg.tool_calls[0].function.arguments),
                "input_tokens": 0,
                "output_tokens": 0,
            }
    except Exception:
        pass

    # Fallback: ask for raw JSON
    json_prompt = (
        f"{all_messages[-1]['content']}\n\n"
        f"Respond ONLY with a valid JSON object matching this schema:\n"
        f"{json.dumps(tool_schema.get('properties', {}), indent=2)}\n"
        f"Required fields: {tool_schema.get('required', [])}"
    )
    response = await client.chat_completion(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": json_prompt}],
        max_tokens=max_tokens,
    )
    raw = response.choices[0].message.content or "{}"
    # Extract JSON from the response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return {"result": json.loads(raw[start:end]), "input_tokens": 0, "output_tokens": 0}


# ── Public interface ───────────────────────────────────────────────────────────

async def call_structured(
    api_key: str,
    messages: list[dict],
    tool_name: str,
    tool_schema: dict,
    system: str,
    max_tokens: int = 1024,
) -> tuple[dict, int, int]:
    """
    Call whichever LLM provider matches the API key.
    Returns (result_dict, input_tokens, output_tokens).
    Raises ProviderError on failure.
    """
    provider_hint = get_request_provider()
    provider = detect_provider(api_key, hint=provider_hint)

    logger.debug("LLM call via provider=%s tool=%s", provider, tool_name)

    if provider == "anthropic":
        out = await _call_anthropic(api_key, messages, tool_name, tool_schema, system, max_tokens)
    elif provider == "openai":
        out = await _call_openai(api_key, messages, tool_name, tool_schema, system, max_tokens)
    elif provider == "ollama":
        out = await _call_ollama(messages, tool_name, tool_schema, system, max_tokens)
    elif provider == "gemini":
        out = await _call_gemini(api_key, messages, tool_name, tool_schema, system, max_tokens)
    elif provider == "huggingface":
        out = await _call_huggingface(api_key, messages, tool_name, tool_schema, system, max_tokens)
    else:
        raise ProviderError(f"Unknown provider: {provider!r}")

    return out["result"], out["input_tokens"], out["output_tokens"]


PROVIDER_DISPLAY_NAMES = {
    "anthropic":   "Anthropic Claude",
    "openai":      "OpenAI (GPT-4o)",
    "gemini":      "Google Gemini",
    "ollama":      "Ollama (local)",
    "huggingface": "HuggingFace",
}

KEY_FORMAT_HINTS = {
    "anthropic":   "Starts with sk-ant-...",
    "openai":      "Starts with sk-...",
    "gemini":      "Starts with AIza...",
    "huggingface": "Starts with hf_...",
    "ollama":      "No key needed — runs locally",
}
