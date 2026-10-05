"""
Agent factory — returns a Claude agent when an API key is available,
stub agent otherwise. Checked at call time so hot-swapping the key works.
"""
from app.agents.anthropic_client import llm_available


def get_case_analyzer():
    if llm_available():
        from app.agents.claude import ClaudeCaseAnalyzer
        return ClaudeCaseAnalyzer()
    from app.agents.stub import StubCaseAnalyzer
    return StubCaseAnalyzer()


def get_planner():
    if llm_available():
        from app.agents.claude import ClaudePlanner
        return ClaudePlanner()
    from app.agents.stub import StubPlanner
    return StubPlanner()


def get_evidence_validator():
    if llm_available():
        from app.agents.claude import ClaudeEvidenceValidator
        return ClaudeEvidenceValidator()
    from app.agents.stub import StubEvidenceValidator
    return StubEvidenceValidator()


def get_risk_analyzer():
    if llm_available():
        from app.agents.claude import ClaudeRiskAnalyzer
        return ClaudeRiskAnalyzer()
    from app.agents.stub import StubRiskAnalyzer
    return StubRiskAnalyzer()
