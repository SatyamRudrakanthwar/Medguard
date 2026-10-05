from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SeverityLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class FindingType(str, Enum):
    interaction = "drug_interaction"
    contraindication = "contraindication"
    adverse_effect = "adverse_effect"
    warning = "warning"
    general_information = "general_information"


class EvidenceSource(BaseModel):
    source: str = Field(description="Name of the source (e.g. OpenFDA, PubMed)")
    source_id: Optional[str] = Field(default=None, description="Article ID, label ID, etc.")
    url: Optional[str] = Field(default=None)
    support_score: float = Field(ge=0.0, le=1.0, description="Relevance/support score from retrieval")
    excerpt: Optional[str] = Field(default=None, max_length=500, description="Relevant excerpt")


class ValidationResult(BaseModel):
    finding_id: str
    is_supported: bool
    confidence: float = Field(ge=0.0, le=1.0)
    unsupported_claims: list[str] = Field(default_factory=list)
    validator_notes: Optional[str] = None


class SafetyFinding(BaseModel):
    finding_id: str
    finding_type: FindingType
    title: str
    description: str
    severity: SeverityLevel
    medications_involved: list[str]
    evidence: list[EvidenceSource] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    is_validated: bool = Field(default=False)
    requires_professional_review: bool = Field(default=True)


class DrugInformation(BaseModel):
    medication_name: str
    normalized_name: str
    drug_class: Optional[str] = None
    indications: list[str] = Field(default_factory=list)
    contraindications: list[str] = Field(default_factory=list)
    common_side_effects: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str = Field(default="OpenFDA")


class Interaction(BaseModel):
    drug_a: str
    drug_b: str
    interaction_type: str
    description: str
    severity: SeverityLevel
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)


class InvestigationPlan(BaseModel):
    medications_to_research: list[str]
    interactions_to_check: list[tuple[str, str]]
    evidence_queries: list[str]
    focus_areas: list[str]
    reasoning: str
