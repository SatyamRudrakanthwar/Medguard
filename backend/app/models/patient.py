from pydantic import BaseModel, Field, field_validator
from typing import Optional


class Medication(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dosage: Optional[str] = Field(default=None, max_length=100)
    frequency: Optional[str] = Field(default=None, max_length=100)
    normalized_name: Optional[str] = Field(default=None)
    rxcui: Optional[str] = Field(default=None, description="RxNorm concept unique identifier")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class PatientContext(BaseModel):
    age: int = Field(ge=1, le=120, description="Patient age in years")
    conditions: list[str] = Field(default_factory=list, description="Known medical conditions")
    allergies: list[str] = Field(default_factory=list, description="Known drug allergies")

    @field_validator("conditions", "allergies")
    @classmethod
    def strip_items(cls, v: list[str]) -> list[str]:
        return [item.strip() for item in v if item.strip()]
