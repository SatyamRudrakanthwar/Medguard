from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid

from .findings import SafetyFinding, EvidenceSource


class ReviewStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    blocked = "blocked"  # safety layer blocked the request


class ReviewRequest(BaseModel):
    age: int = Field(ge=1, le=120, description="Patient age in years")
    conditions: list[str] = Field(default_factory=list, description="Known medical conditions")
    medications: list[str] = Field(
        min_length=1,
        max_length=20,
        description="List of medication names",
    )
    question: str = Field(
        min_length=5,
        max_length=1000,
        description="Safety question to investigate",
    )

    @field_validator("medications")
    @classmethod
    def validate_medications(cls, v: list[str]) -> list[str]:
        cleaned = [m.strip() for m in v if m.strip()]
        if not cleaned:
            raise ValueError("At least one medication is required")
        return cleaned

    @field_validator("question")
    @classmethod
    def strip_question(cls, v: str) -> str:
        return v.strip()


class ReviewResponse(BaseModel):
    review_id: str
    status: ReviewStatus
    message: Optional[str] = None

    # Populated when status == completed
    medications_reviewed: list[str] = Field(default_factory=list)
    findings: list[SafetyFinding] = Field(default_factory=list)
    evidence: list[EvidenceSource] = Field(default_factory=list)
    additional_information: list[str] = Field(default_factory=list)
    high_severity_count: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    disclaimer: str = Field(
        default=(
            "This is an informational safety review and not a diagnosis "
            "or treatment recommendation. Consult your healthcare provider."
        )
    )


class StreamEvent(BaseModel):
    event: str  # step_started, step_completed, error, done
    step: Optional[str] = None
    message: Optional[str] = None
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
