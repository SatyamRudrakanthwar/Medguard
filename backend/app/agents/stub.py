"""
Stage 4 stub agents — return structured mock responses.
These are replaced by real Claude agents in Stage 5 when an API key is configured.
"""
import uuid
from itertools import combinations

from app.models.patient import Medication, PatientContext
from app.models.findings import (
    DrugInformation, Interaction, EvidenceSource, ValidationResult,
    SafetyFinding, FindingType, SeverityLevel, InvestigationPlan,
)
from app.mcp.tools.guideline_search import _match_curated


class StubCaseAnalyzer:
    async def analyze(
        self,
        medications: list[Medication],
        patient_context: PatientContext | None,
        question: str,
    ) -> dict:
        med_names = [m.normalized_name or m.name for m in medications]
        return {
            "key_concerns": [f"Medication safety review for {', '.join(med_names)}"],
            "patient_summary": f"Patient age {patient_context.age if patient_context else 'unknown'}",
            "analysis_complete": True,
        }


class StubPlanner:
    async def plan(
        self,
        medications: list[Medication],
        patient_context: PatientContext | None,
        question: str,
    ) -> InvestigationPlan:
        med_names = [m.normalized_name or m.name for m in medications]
        pairs = list(combinations(med_names, 2))
        queries = [
            f"{' '.join(med_names[:2])} drug interaction safety",
            f"{med_names[0]} adverse effects contraindications",
            f"{'elderly ' if patient_context and patient_context.age >= 65 else ''}"
            f"{' '.join(med_names[:2])} safety",
        ]
        return InvestigationPlan(
            medications_to_research=med_names,
            interactions_to_check=pairs,
            evidence_queries=queries,
            focus_areas=["drug interactions", "contraindications", "patient-specific factors"],
            reasoning=(
                f"Patient presents with {len(med_names)} medications. "
                "Will check all pairwise interactions and individual drug safety profiles."
            ),
        )


class StubEvidenceValidator:
    async def validate(
        self,
        evidence: list[EvidenceSource],
        medications: list[Medication],
        interactions: list[Interaction],
        drug_info: list[DrugInformation],
    ) -> dict:
        # Sufficient if we have at least 2 evidence items OR drug info for all meds
        has_evidence = len(evidence) >= 2
        has_drug_info = len(drug_info) >= len(medications) * 0.5

        sufficient = has_evidence or has_drug_info

        return {
            "sufficient": sufficient,
            "validation_results": [
                ValidationResult(
                    finding_id="summary",
                    is_supported=sufficient,
                    confidence=0.85 if sufficient else 0.40,
                    unsupported_claims=[] if sufficient else ["Insufficient evidence retrieved"],
                    validator_notes=(
                        f"Found {len(evidence)} evidence items and "
                        f"{len(drug_info)} drug information records."
                    ),
                )
            ],
        }


class StubRiskAnalyzer:
    async def analyze(
        self,
        medications: list[Medication],
        drug_information: list[DrugInformation],
        interactions: list[Interaction],
        evidence: list[EvidenceSource],
        patient_context: PatientContext | None,
        question: str,
    ) -> list[SafetyFinding]:
        findings: list[SafetyFinding] = []
        med_names = [m.normalized_name or m.name for m in medications]
        med_names_lower = [n.lower() for n in med_names]

        # Convert RxNorm interaction results to findings
        for ix in interactions:
            findings.append(SafetyFinding(
                finding_id=str(uuid.uuid4()),
                finding_type=FindingType.interaction,
                title=f"Drug Interaction: {ix.drug_a} + {ix.drug_b}",
                description=ix.description or f"Known interaction between {ix.drug_a} and {ix.drug_b}.",
                severity=ix.severity,
                medications_involved=[ix.drug_a, ix.drug_b],
                evidence=[e for e in evidence if e.support_score >= 0.7][:3],
                confidence=0.80,
                is_validated=True,
            ))

        # Match curated high-confidence safety rules
        matched_guidelines = _match_curated(med_names_lower)
        for guideline in matched_guidelines:
            # Don't duplicate an interaction already found via RxNorm
            already_found = any(
                guideline["title"].lower() in f.title.lower() for f in findings
            )
            if already_found:
                continue

            sev_map = {
                "critical": SeverityLevel.critical,
                "high": SeverityLevel.high,
                "moderate": SeverityLevel.moderate,
                "low": SeverityLevel.low,
            }
            findings.append(SafetyFinding(
                finding_id=str(uuid.uuid4()),
                finding_type=FindingType.warning,
                title=guideline["title"],
                description=guideline["guideline"],
                severity=sev_map.get(guideline["severity"], SeverityLevel.moderate),
                medications_involved=guideline.get("matched_drugs", []),
                evidence=[EvidenceSource(
                    source=guideline["source"],
                    support_score=0.95,
                    excerpt=guideline["guideline"][:300],
                )],
                confidence=0.92,
                is_validated=True,
            ))

        # Add drug-specific warnings from OpenFDA data
        for info in drug_information:
            for warning in info.warnings[:1]:  # top warning only
                if warning and len(warning) > 20:
                    findings.append(SafetyFinding(
                        finding_id=str(uuid.uuid4()),
                        finding_type=FindingType.warning,
                        title=f"{info.normalized_name} — FDA Warning",
                        description=warning[:500],
                        severity=SeverityLevel.low,
                        medications_involved=[info.normalized_name],
                        evidence=[EvidenceSource(
                            source="OpenFDA",
                            support_score=0.85,
                            excerpt=warning[:300],
                        )],
                        confidence=0.88,
                        is_validated=True,
                    ))

        return findings
