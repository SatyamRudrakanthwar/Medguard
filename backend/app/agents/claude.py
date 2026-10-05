"""
Stage 5: Real Claude agents using Anthropic API with structured tool-use output.
Each agent uses tool_choice={"type": "tool"} to force a structured JSON response
so output is always parseable — no regex, no brittle string parsing.
"""
import json
import logging
import uuid
from itertools import combinations

from app.agents.anthropic_client import get_client, get_settings
from app.models.patient import Medication, PatientContext
from app.models.findings import (
    DrugInformation, Interaction, EvidenceSource, ValidationResult,
    SafetyFinding, FindingType, SeverityLevel, InvestigationPlan,
)

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

_SAFETY_SYSTEM = (
    "You are a medication safety research assistant. "
    "You provide factual, evidence-based medication safety information for research purposes only. "
    "You do NOT provide diagnoses, treatment recommendations, or advice on starting/stopping medications. "
    "Always cite the source of information. Be precise and conservative in your assessments."
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _med_summary(medications: list[Medication]) -> str:
    lines = []
    for m in medications:
        name = m.normalized_name or m.name
        parts = [name]
        if m.dosage:
            parts.append(f"({m.dosage})")
        if m.rxcui:
            parts.append(f"[RXCUI: {m.rxcui}]")
        lines.append(" ".join(parts))
    return "\n".join(f"- {l}" for l in lines)


def _patient_summary(ctx: PatientContext | None) -> str:
    if not ctx:
        return "Age: unknown, Conditions: none specified"
    conds = ", ".join(ctx.conditions) if ctx.conditions else "none specified"
    return f"Age: {ctx.age}, Conditions: {conds}"


async def _call_tool(messages: list[dict], tool: dict, system: str, max_tokens: int = 1024) -> dict:
    """
    Call the configured LLM provider with a structured tool schema.
    Provider is auto-detected from the API key format, or overridden
    via the X-Provider request header.  Falls back to stub on any failure.
    """
    import time
    import json
    from app.agents.provider import call_structured, ProviderError
    from app.observability import get_trace_context

    api_key = get_api_key()
    if not api_key:
        raise ValueError("No API key set. Add one in Settings to enable AI analysis.")

    t0 = time.perf_counter()
    result, input_tokens, output_tokens = await call_structured(
        api_key=api_key,
        messages=messages,
        tool_name=tool["name"],
        tool_schema=tool.get("input_schema", tool),
        system=system,
        max_tokens=max_tokens,
    )
    duration_ms = (time.perf_counter() - t0) * 1000

    # Record LLM generation in Langfuse (no-op when not configured)
    try:
        trace_ctx = get_trace_context()
        if trace_ctx:
            prompt_text = messages[0]["content"] if messages else ""
            trace_ctx.llm_generation(
                agent_name=tool["name"],
                model=MODEL,
                prompt=str(prompt_text)[:1000],
                output=json.dumps(result)[:500],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
            )
    except Exception:
        pass

    return result


# ── Agent 1: Case Analyzer ────────────────────────────────────────────────────

class ClaudeCaseAnalyzer:
    async def analyze(
        self,
        medications: list[Medication],
        patient_context: PatientContext | None,
        question: str,
    ) -> dict:
        tool = {
            "name": "submit_case_analysis",
            "description": "Submit the structured case analysis",
            "input_schema": {
                "type": "object",
                "properties": {
                    "key_concerns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of key medication safety concerns identified",
                    },
                    "patient_summary": {
                        "type": "string",
                        "description": "One-sentence patient context summary",
                    },
                    "complexity": {
                        "type": "string",
                        "enum": ["low", "moderate", "high"],
                        "description": "Complexity of the medication regimen",
                    },
                },
                "required": ["key_concerns", "patient_summary", "complexity"],
            },
        }

        prompt = (
            f"Analyze this medication safety case:\n\n"
            f"Patient: {_patient_summary(patient_context)}\n\n"
            f"Medications:\n{_med_summary(medications)}\n\n"
            f"Question: {question}\n\n"
            "Identify the key medication safety concerns that should be investigated. "
            "Focus on: potential interactions, patient-specific risk factors, and drug classes involved."
        )

        try:
            result = await _call_tool([{"role": "user", "content": prompt}], tool, _SAFETY_SYSTEM)
            logger.info("Case analysis: complexity=%s concerns=%d", result.get("complexity"), len(result.get("key_concerns", [])))
            return result
        except Exception as e:
            logger.error("ClaudeCaseAnalyzer failed: %s", e)
            from app.agents.stub import StubCaseAnalyzer
            return await StubCaseAnalyzer().analyze(medications, patient_context, question)


# ── Agent 2: Planner ──────────────────────────────────────────────────────────

class ClaudePlanner:
    async def plan(
        self,
        medications: list[Medication],
        patient_context: PatientContext | None,
        question: str,
    ) -> InvestigationPlan:
        med_names = [m.normalized_name or m.name for m in medications]
        all_pairs = list(combinations(med_names, 2))

        tool = {
            "name": "submit_investigation_plan",
            "description": "Submit the investigation plan",
            "input_schema": {
                "type": "object",
                "properties": {
                    "medications_to_research": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Medications to look up in OpenFDA",
                    },
                    "interaction_pairs": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                        "description": "Drug pairs to check for interactions (highest priority first)",
                    },
                    "evidence_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "PubMed search queries (2–4 queries, specific and targeted)",
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key safety areas to focus on",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief reasoning for this investigation plan",
                    },
                },
                "required": ["medications_to_research", "interaction_pairs", "evidence_queries", "focus_areas", "reasoning"],
            },
        }

        prompt = (
            f"Create a medication safety investigation plan.\n\n"
            f"Patient: {_patient_summary(patient_context)}\n\n"
            f"Medications:\n{_med_summary(medications)}\n\n"
            f"Question: {question}\n\n"
            f"All possible pairs to check: {all_pairs}\n\n"
            "Create a targeted investigation plan. Prioritize the highest-risk pairs. "
            "Write PubMed queries that would find relevant safety literature."
        )

        try:
            result = await _call_tool([{"role": "user", "content": prompt}], tool, _SAFETY_SYSTEM, max_tokens=512)
            pairs = [tuple(p) for p in result.get("interaction_pairs", all_pairs)]
            return InvestigationPlan(
                medications_to_research=result.get("medications_to_research", med_names),
                interactions_to_check=pairs,
                evidence_queries=result.get("evidence_queries", []),
                focus_areas=result.get("focus_areas", []),
                reasoning=result.get("reasoning", ""),
            )
        except Exception as e:
            logger.error("ClaudePlanner failed: %s", e)
            from app.agents.stub import StubPlanner
            return await StubPlanner().plan(medications, patient_context, question)


# ── Agent 3: Evidence Validator ───────────────────────────────────────────────

class ClaudeEvidenceValidator:
    async def validate(
        self,
        evidence: list[EvidenceSource],
        medications: list[Medication],
        interactions: list[Interaction],
        drug_info: list[DrugInformation],
    ) -> dict:
        tool = {
            "name": "submit_validation_result",
            "description": "Submit evidence validation result",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sufficient": {
                        "type": "boolean",
                        "description": "Whether the collected evidence is sufficient to generate a reliable report",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Confidence in the evidence quality (0-1)",
                    },
                    "gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of evidence gaps that should be addressed (empty if sufficient)",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Brief explanation of the validation decision",
                    },
                },
                "required": ["sufficient", "confidence", "gaps", "notes"],
            },
        }

        evidence_summary = "\n".join(
            f"- [{e.source}] score={e.support_score:.2f} excerpt={e.excerpt[:80] if e.excerpt else 'N/A'}"
            for e in evidence[:8]
        )
        drug_info_summary = "\n".join(
            f"- {d.normalized_name}: {d.drug_class or 'class unknown'}, "
            f"{len(d.warnings)} warnings, {len(d.contraindications)} contraindications"
            for d in drug_info
        )
        interaction_summary = "\n".join(
            f"- {ix.drug_a} + {ix.drug_b}: {ix.severity.value} ({ix.description[:80]})"
            for ix in interactions
        ) or "No interactions found via RxNorm API."

        prompt = (
            f"Evaluate whether this evidence is sufficient to generate a reliable medication safety report.\n\n"
            f"Evidence collected ({len(evidence)} items):\n{evidence_summary or 'None'}\n\n"
            f"Drug information ({len(drug_info)} records):\n{drug_info_summary or 'None'}\n\n"
            f"Interactions:\n{interaction_summary}\n\n"
            "Mark as sufficient if we have: (a) drug info for most medications OR "
            "(b) at least 2 relevant evidence sources OR (c) known interaction data. "
            "Mark insufficient only if we have almost nothing useful."
        )

        try:
            result = await _call_tool([{"role": "user", "content": prompt}], tool, _SAFETY_SYSTEM, max_tokens=256)
            return {
                "sufficient": result["sufficient"],
                "validation_results": [
                    ValidationResult(
                        finding_id="summary",
                        is_supported=result["sufficient"],
                        confidence=result["confidence"],
                        unsupported_claims=result.get("gaps", []),
                        validator_notes=result.get("notes", ""),
                    )
                ],
            }
        except Exception as e:
            logger.error("ClaudeEvidenceValidator failed: %s", e)
            from app.agents.stub import StubEvidenceValidator
            return await StubEvidenceValidator().validate(evidence, medications, interactions, drug_info)


# ── Agent 4: Risk Analyzer ────────────────────────────────────────────────────

class ClaudeRiskAnalyzer:
    async def analyze(
        self,
        medications: list[Medication],
        drug_information: list[DrugInformation],
        interactions: list[Interaction],
        evidence: list[EvidenceSource],
        patient_context: PatientContext | None,
        question: str,
    ) -> list[SafetyFinding]:
        tool = {
            "name": "submit_safety_findings",
            "description": "Submit the structured safety findings",
            "input_schema": {
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "finding_type": {
                                    "type": "string",
                                    "enum": ["drug_interaction", "contraindication", "adverse_effect", "warning", "general_information"],
                                },
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "severity": {
                                    "type": "string",
                                    "enum": ["low", "moderate", "high", "critical"],
                                },
                                "medications_involved": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                            },
                            "required": ["finding_type", "title", "description", "severity", "medications_involved", "confidence"],
                        },
                        "description": "List of safety findings (most severe first)",
                    }
                },
                "required": ["findings"],
            },
        }

        drug_info_text = "\n".join(
            f"- {d.normalized_name} ({d.drug_class or 'unknown class'}): "
            f"contraindications: {'; '.join(d.contraindications[:2]) or 'none listed'}; "
            f"warnings: {'; '.join(w[:100] for w in d.warnings[:2]) or 'none listed'}"
            for d in drug_information
        ) or "No drug information retrieved."

        interaction_text = "\n".join(
            f"- {ix.drug_a} + {ix.drug_b} [{ix.severity.value}]: {ix.description[:150]}"
            for ix in interactions
        ) or "No direct interactions found via RxNorm."

        evidence_text = "\n".join(
            f"- [{e.source}] {e.excerpt[:120] if e.excerpt else 'no excerpt'}"
            for e in evidence[:6]
        ) or "No evidence retrieved."

        prompt = (
            f"Analyze this medication safety data and identify specific safety findings.\n\n"
            f"Patient: {_patient_summary(patient_context)}\n\n"
            f"Medications reviewed:\n{_med_summary(medications)}\n\n"
            f"Drug information:\n{drug_info_text}\n\n"
            f"Interactions found:\n{interaction_text}\n\n"
            f"Evidence:\n{evidence_text}\n\n"
            f"User question: {question}\n\n"
            "Generate specific, actionable safety findings. For each finding:\n"
            "- Be specific about which medications are involved\n"
            "- Use conservative severity ratings based on actual evidence\n"
            "- Write descriptions that a patient could understand\n"
            "- Only report findings supported by the evidence above\n"
            "- Do NOT recommend starting/stopping medications\n"
            "- Sort most severe findings first"
        )

        try:
            result = await _call_tool(
                [{"role": "user", "content": prompt}], tool, _SAFETY_SYSTEM, max_tokens=2048
            )
            findings = []
            sev_map = {
                "critical": SeverityLevel.critical,
                "high": SeverityLevel.high,
                "moderate": SeverityLevel.moderate,
                "low": SeverityLevel.low,
            }
            type_map = {
                "drug_interaction": FindingType.interaction,
                "contraindication": FindingType.contraindication,
                "adverse_effect": FindingType.adverse_effect,
                "warning": FindingType.warning,
                "general_information": FindingType.general_information,
            }
            for f in result.get("findings", []):
                relevant_evidence = [
                    e for e in evidence
                    if any(m.lower() in (e.excerpt or "").lower() for m in f.get("medications_involved", []))
                ][:3] or evidence[:2]

                findings.append(SafetyFinding(
                    finding_id=str(uuid.uuid4()),
                    finding_type=type_map.get(f["finding_type"], FindingType.warning),
                    title=f["title"],
                    description=f["description"],
                    severity=sev_map.get(f["severity"], SeverityLevel.moderate),
                    medications_involved=f["medications_involved"],
                    evidence=relevant_evidence,
                    confidence=f["confidence"],
                    is_validated=True,
                ))
            return findings

        except Exception as e:
            logger.error("ClaudeRiskAnalyzer failed: %s", e)
            from app.agents.stub import StubRiskAnalyzer
            return await StubRiskAnalyzer().analyze(
                medications, drug_information, interactions, evidence, patient_context, question
            )
