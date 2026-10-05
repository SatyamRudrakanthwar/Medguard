"""
MCP Client wrapper for LangGraph agents.
Provides a clean async interface so agents call tool functions directly
(in-process) rather than over a network socket during development.
In production, this can switch to a remote MCP transport.
"""
import time
import logging
from typing import Any

from app.mcp.tools.drug_information import get_drug_information
from app.mcp.tools.interaction_check import check_drug_interaction, check_multiple_interactions
from app.mcp.tools.literature_search import search_medical_literature
from app.mcp.tools.guideline_search import search_guidelines
from app.mcp.tools.evidence_retrieval import retrieve_evidence

logger = logging.getLogger(__name__)


class _NoopContext:
    """Minimal context substitute for in-process tool calls (no real MCP session)."""
    async def info(self, msg: str) -> None:
        logger.info("[MCP] %s", msg)

    async def warning(self, msg: str) -> None:
        logger.warning("[MCP] %s", msg)

    async def error(self, msg: str) -> None:
        logger.error("[MCP] %s", msg)


_ctx = _NoopContext()


def _record_tool_span(tool_name: str, input_data: dict, output: Any, duration_ms: float) -> None:
    """Non-blocking Langfuse tool span — silently no-ops on any error."""
    try:
        from app.observability import get_trace_context
        trace_ctx = get_trace_context()
        if trace_ctx:
            trace_ctx.tool_span(tool_name, input_data, output, duration_ms)
    except Exception:
        pass


class MedGuardMCPClient:
    """
    In-process MCP client used by LangGraph agent nodes.
    Each method maps directly to a registered MCP tool.
    Switching to a remote transport only requires changing this class.
    """

    async def get_drug_information(self, drug_name: str) -> dict:
        t0 = time.perf_counter()
        result = await get_drug_information(drug_name=drug_name, ctx=_ctx)
        _record_tool_span("get_drug_information", {"drug_name": drug_name}, result, (time.perf_counter() - t0) * 1000)
        return result

    async def check_drug_interaction(self, drug_a: str, drug_b: str) -> dict:
        t0 = time.perf_counter()
        result = await check_drug_interaction(drug_a=drug_a, drug_b=drug_b, ctx=_ctx)
        _record_tool_span("check_drug_interaction", {"drug_a": drug_a, "drug_b": drug_b}, result, (time.perf_counter() - t0) * 1000)
        return result

    async def check_multiple_interactions(self, medications: list[str]) -> dict:
        t0 = time.perf_counter()
        result = await check_multiple_interactions(medications=medications, ctx=_ctx)
        _record_tool_span("check_multiple_interactions", {"medications": medications}, result, (time.perf_counter() - t0) * 1000)
        return result

    async def search_medical_literature(self, query: str, max_results: int = 5) -> dict:
        t0 = time.perf_counter()
        result = await search_medical_literature(query=query, max_results=max_results, ctx=_ctx)
        _record_tool_span("search_medical_literature", {"query": query}, result, (time.perf_counter() - t0) * 1000)
        return result

    async def search_guidelines(self, drug_names: list[str], query: str = "") -> dict:
        t0 = time.perf_counter()
        result = await search_guidelines(drug_names=drug_names, query=query, ctx=_ctx)
        _record_tool_span("search_guidelines", {"drug_names": drug_names, "query": query}, result, (time.perf_counter() - t0) * 1000)
        return result

    async def retrieve_evidence(self, finding: str, medications: list[str], max_results: int = 5) -> dict:
        t0 = time.perf_counter()
        result = await retrieve_evidence(finding=finding, medications=medications, max_results=max_results, ctx=_ctx)
        _record_tool_span("retrieve_evidence", {"finding": finding[:80], "medications": medications}, result, (time.perf_counter() - t0) * 1000)
        return result


# Singleton — agents import this directly
mcp_client = MedGuardMCPClient()
