from sqlalchemy import (
    String, Integer, Float, Boolean, Text, DateTime, JSON,
    ForeignKey, Index, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.services.database import Base


class ReviewStatusEnum(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    blocked = "blocked"


class ReviewRecord(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[ReviewStatusEnum] = mapped_column(
        SAEnum(ReviewStatusEnum), default=ReviewStatusEnum.pending, nullable=False
    )

    # Input
    patient_age: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_conditions: Mapped[list] = mapped_column(JSON, default=list)
    medications_input: Mapped[list] = mapped_column(JSON, default=list)
    user_question: Mapped[str] = mapped_column(Text, nullable=False)

    # Output
    findings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    additional_information: Mapped[list] = mapped_column(JSON, default=list)
    high_severity_count: Mapped[int] = mapped_column(Integer, default=0)
    research_retries: Mapped[int] = mapped_column(Integer, default=0)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_reviews_status", "status"),
        Index("ix_reviews_created_at", "created_at"),
    )


class DrugCacheRecord(Base):
    """Cache of drug information fetched from OpenFDA to avoid repeated API calls."""
    __tablename__ = "drug_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    rxcui: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    drug_class: Mapped[str | None] = mapped_column(String(200), nullable=True)
    indications: Mapped[list] = mapped_column(JSON, default=list)
    contraindications: Mapped[list] = mapped_column(JSON, default=list)
    common_side_effects: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    raw_openfda: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)


class InteractionCacheRecord(Base):
    """Cache of known drug interactions."""
    __tablename__ = "interaction_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drug_a: Mapped[str] = mapped_column(String(200), nullable=False)
    drug_b: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(100), default="OpenFDA")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_interaction_drugs", "drug_a", "drug_b"),
    )
