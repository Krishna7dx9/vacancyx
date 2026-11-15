"""Application tracking and timeline API contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationStatusTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["submitting", "submitted", "uncertain", "blocked", "rejected", "withdrawn"]
    confirmation_reference: str | None = Field(default=None, max_length=2048)

    @field_validator("confirmation_reference")
    @classmethod
    def normalize_confirmation_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("confirmation_reference cannot be blank.")
        return normalized


class ApplicationTimelineEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal[
        "assessment_scheduled",
        "assessment_completed",
        "interview_scheduled",
        "interview_completed",
        "offer_received",
        "offer_declined",
        "follow_up",
        "note",
    ]
    summary: str = Field(min_length=1, max_length=2000)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summary cannot be blank.")
        return normalized


class ApplicationTimelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    occurred_at: datetime
    metadata_json: dict[str, Any]
