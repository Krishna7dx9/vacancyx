"""Application preparation API contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_custom_fields(values: dict[str, str]) -> dict[str, str]:
    if len(values) > 100:
        raise ValueError("At most 100 custom fields are allowed.")
    total_characters = 0
    normalized: dict[str, str] = {}
    for key, value in values.items():
        name = key.strip()
        if not name or len(name) > 120:
            raise ValueError("Custom field names must contain 1 to 120 characters.")
        if len(value) > 4_000:
            raise ValueError("Custom field values cannot exceed 4,000 characters.")
        total_characters += len(name) + len(value)
        normalized[name] = value
    if total_characters > 20_000:
        raise ValueError("Custom fields exceed the 20,000-character total limit.")
    return normalized


def _validate_answer_ids(values: list[str]) -> list[str]:
    normalized = [value.strip() for value in values]
    if any(not value or len(value) > 36 for value in normalized):
        raise ValueError("Each answer ID must contain 1 to 36 characters.")
    if len(normalized) != len(set(normalized)):
        raise ValueError("answer_ids must not contain duplicates.")
    return normalized


class ApplicationPrepare(BaseModel):
    """Create a prepared application from candidate-owned material."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1, max_length=36)
    resume_id: str | None = Field(default=None, max_length=36)
    answer_ids: list[str] = Field(default_factory=list, max_length=100)
    custom_fields: dict[str, str] = Field(default_factory=dict, max_length=100)

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("job_id cannot be blank.")
        return normalized

    @field_validator("resume_id")
    @classmethod
    def validate_resume_id(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or len(value) > 36):
            raise ValueError("resume_id must contain 1 to 36 characters.")
        return value

    @field_validator("answer_ids")
    @classmethod
    def validate_answers(cls, values: list[str]) -> list[str]:
        return _validate_answer_ids(values)

    @field_validator("custom_fields")
    @classmethod
    def validate_fields(cls, values: dict[str, str]) -> dict[str, str]:
        return _validate_custom_fields(values)


class ApplicationUpdate(BaseModel):
    """Revise application content; omitted fields remain unchanged."""

    model_config = ConfigDict(extra="forbid")

    resume_id: str | None = Field(default=None, max_length=36)
    answer_ids: list[str] | None = Field(default=None, max_length=100)
    custom_fields: dict[str, str] | None = Field(default=None, max_length=100)

    @field_validator("resume_id")
    @classmethod
    def validate_resume_id(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or len(value) > 36):
            raise ValueError("resume_id must contain 1 to 36 characters.")
        return value

    @field_validator("answer_ids")
    @classmethod
    def validate_answers(cls, values: list[str] | None) -> list[str]:
        if values is None:
            raise ValueError("answer_ids cannot be null.")
        return _validate_answer_ids(values)

    @field_validator("custom_fields")
    @classmethod
    def validate_fields(cls, values: dict[str, str] | None) -> dict[str, str]:
        if values is None:
            raise ValueError("custom_fields cannot be null.")
        return _validate_custom_fields(values)


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
