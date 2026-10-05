"""Unit tests for MCP tool utilities (no live API calls)."""
import pytest
from app.mcp.tools.guideline_search import _match_curated, CURATED_GUIDELINES
from app.mcp.tools.evidence_retrieval import _build_pubmed_query
from app.mcp.tools.interaction_check import _map_severity
from app.mcp.tools.drug_information import _truncate_list


def test_curated_guidelines_warfarin_aspirin():
    matched = _match_curated(["warfarin", "aspirin"])
    assert len(matched) >= 1
    titles = [g["title"] for g in matched]
    assert any("Warfarin" in t for t in titles)


def test_curated_guidelines_no_match():
    matched = _match_curated(["penicillin"])
    assert matched == []


def test_curated_ssri_maoi_match():
    matched = _match_curated(["fluoxetine", "phenelzine"])
    assert len(matched) >= 1
    severities = [g["severity"] for g in matched]
    assert "critical" in severities


def test_pubmed_query_interaction():
    q = _build_pubmed_query("potential drug interaction identified", ["warfarin", "aspirin"])
    assert "warfarin" in q.lower()
    assert "interaction" in q.lower()


def test_pubmed_query_bleeding():
    q = _build_pubmed_query("increased bleeding risk", ["warfarin"])
    assert "bleeding" in q.lower()


def test_severity_mapping():
    assert _map_severity("HIGH") == "high"
    assert _map_severity("MODERATE") == "moderate"
    assert _map_severity("unknown") == "low"
    assert _map_severity("N/A") == "low"


def test_truncate_list_basic():
    items = ["a" * 400, "short", "b" * 400]
    result = _truncate_list(items, 3, 300)
    assert len(result) == 3
    assert len(result[0]) <= 303  # 300 + "..."
    assert result[1] == "short"


def test_truncate_list_max_items():
    items = ["one", "two", "three", "four", "five"]
    result = _truncate_list(items, 2, 100)
    assert len(result) == 2
