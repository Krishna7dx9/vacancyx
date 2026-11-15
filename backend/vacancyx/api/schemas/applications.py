"""Application preparation API contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationPrepare(BaseModel):
    """Create a prepared application from candidate-owned material."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1, max_length=36)
    resume_id: str | None = Field(default=None, max_length=36)
    answer_ids: list[str] = Field(default_factory=list, max_length=100)
    custom_fields: dict[str, str] = Field(default_factory=dict, max_length=100)

    @field_validator("answer_ids")
    @classmethod
    def answer_ids_must_be_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("answer_ids must not contain duplicates")
        return values


class ApplicationUpdate(BaseModel):
    """Revise application content; omitted fields remain unchanged."""

    model_config = ConfigDict(extra="forbid")

    resume_id: str | None = Field(default=None, max_length=36)
    answer_ids: list[str] | None = Field(default=None, max_length=100)
    custom_fields: dict[str, str] | None = Field(default=None, max_length=100)

    @field_validator("answer_ids")
    @classmethod
    def answer_ids_must_be_unique(cls, values: list[str] | None) -> list[str] | None:
        if values is not None and len(values) != len(set(values)):
            raise ValueError("answer_ids must not contain duplicates")
        return values


class ApplicationRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    revision: int
    content_hash: str
    content_snapshot: dict[str, Any]
    resume_id: str | None
    created_at: datetime


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    job_id: str
    resume_id: str | None
    status: str
    current_revision: int
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    latest_revision: ApplicationRevisionRead | None = None


class ApplicationList(BaseModel):
    items: list[ApplicationRead]
    total: int
    limit: int
    offset: int
