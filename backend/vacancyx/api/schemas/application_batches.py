"""Application batch review and decision contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationBatchCreate(BaseModel):
    """Create a candidate-owned batch from prepared applications."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    application_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Batch name cannot be blank.")
        return normalized

    @field_validator("application_ids")
    @classmethod
    def validate_application_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 36 for value in normalized):
            raise ValueError("Each application ID must contain 1 to 36 characters.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("application_ids must not contain duplicates.")
        return normalized


class ApplicationBatchDecision(BaseModel):
    """One explicit human decision for a batch item."""

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(min_length=1, max_length=36)
    decision: Literal["approved", "rejected"]


class ApplicationBatchDecisionRequest(BaseModel):
    """A bounded set of human decisions for one review batch."""

    model_config = ConfigDict(extra="forbid")

    decisions: list[ApplicationBatchDecision] = Field(min_length=1, max_length=100)

    @field_validator("decisions")
    @classmethod
    def unique_applications(
        cls, values: list[ApplicationBatchDecision]
    ) -> list[ApplicationBatchDecision]:
        ids = [value.application_id for value in values]
        if len(ids) != len(set(ids)):
            raise ValueError("A decision request cannot repeat an application.")
        return values


class ApplicationBatchItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    revision: int
    content_hash: str
    decision: str
    decided_at: datetime | None
    current_revision: int
    current_content_hash: str | None
    is_stale: bool
    company_name: str
    job_title: str
    readiness_status: str | None
    missing_fields: list[str]


class ApplicationBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[ApplicationBatchItemRead]
    total_items: int


class ApplicationBatchDecisionResult(BaseModel):
    application_id: str
    result: Literal["approved", "rejected", "stale", "needs_attention"]


class ApplicationBatchDecisionResponse(BaseModel):
    batch: ApplicationBatchRead
    results: list[ApplicationBatchDecisionResult]
