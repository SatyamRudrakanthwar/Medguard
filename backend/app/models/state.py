from typing import TypedDict, Optional, Annotated
import operator

from .patient import Medication, PatientContext
from .findings import (
    DrugInformation,
    Interaction,
    EvidenceSource,
    ValidationResult,
    SafetyFinding,
    InvestigationPlan,
)
from .report import SafetyReport


class MedicationReviewState(TypedDict):
    # --- Input ---
    review_id: str
    patient_context: PatientContext
    medications: list[Medication]
    user_question: str

    # --- Planning ---
    investigation_plan: Optional[InvestigationPlan]

    # --- Research results (appended across retries) ---
    drug_information: Annotated[list[DrugInformation], operator.add]
    interactions: Annotated[list[Interaction], operator.add]
    evidence: Annotated[list[EvidenceSource], operator.add]

    # --- Validation ---
    validation_results: list[ValidationResult]
    evidence_sufficient: bool

    # --- Analysis ---
    findings: list[SafetyFinding]

    # --- Control ---
    retry_count: int
    blocked: bool                                    # safety layer blocked the request
    block_reason: Optional[str]
    errors: Annotated[list[str], operator.add]
    completed_steps: Annotated[list[str], operator.add]

    # --- Output ---
    final_report: Optional[SafetyReport]
