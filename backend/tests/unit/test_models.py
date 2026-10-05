"""Unit tests for Pydantic models."""
import pytest
from app.models import (
    Medication,
    PatientContext,
    ReviewRequest,
    ReviewStatus,
    SeverityLevel,
    FindingType,
)


def test_medication_strips_whitespace():
    med = Medication(name="  aspirin  ")
    assert med.name == "aspirin"


def test_medication_optional_fields():
    med = Medication(name="metformin", dosage="500mg", frequency="twice daily")
    assert med.dosage == "500mg"
    assert med.rxcui is None


def test_patient_context_valid():
    ctx = PatientContext(age=62, conditions=["hypertension", "diabetes"])
    assert ctx.age == 62
    assert len(ctx.conditions) == 2


def test_patient_context_age_bounds():
    with pytest.raises(Exception):
        PatientContext(age=0)
    with pytest.raises(Exception):
        PatientContext(age=200)


def test_review_request_valid():
    req = ReviewRequest(
        age=62,
        conditions=["hypertension"],
        medications=["aspirin", "metformin"],
        question="Are there any safety concerns?",
    )
    assert len(req.medications) == 2


def test_review_request_strips_empty_medications():
    req = ReviewRequest(
        age=40,
        medications=["aspirin", "  ", "metformin"],
        question="Any concerns?",
    )
    assert len(req.medications) == 2


def test_review_request_requires_medications():
    with pytest.raises(Exception):
        ReviewRequest(age=40, medications=[], question="Any concerns?")


def test_severity_levels():
    assert SeverityLevel.high == "high"
    assert SeverityLevel.critical == "critical"
