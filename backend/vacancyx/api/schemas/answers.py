"""Validated API contracts for reusable candidate answers."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CandidateAnswerCreate(BaseModel):
    """Create a reusable answer owned by one candidate."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)
    answer_text: str = Field(min_length=1, max_length=10_000)
    category: str | None = Field(default=None, max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("question", "answer_text")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text fields must not be blank.")
        return normalized


class CandidateAnswerPatch(BaseModel):
    """Partially update content or activation state without resetting omitted fields."""

    model_config = ConfigDict(extra="forbid")

    question: str | None = Field(default=None, min_length=1, max_length=500)
    answer_text: str | None = Field(default=None, min_length=1, max_length=10_000)
    category: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = Field(default=None, max_length=50)
    is_active: bool | None = None

    @field_validator("question", "answer_text")
    @classmethod
    def reject_null_or_blank_text(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Question and answer text cannot be null.")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text fields must not be blank.")
        return normalized

    @field_validator("tags")
    @classmethod
    def tags_must_not_be_null(cls, value: list[str] | None) -> list[str]:
        if value is None:
            raise ValueError("tags cannot be null.")
        return value

    @field_validator("is_active")
    @classmethod
    def active_must_not_be_null(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("is_active cannot be null.")
        return value


class CandidateAnswerRead(BaseModel):
    """Current answer content and revision metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    question: str
    answer_text: str
    category: str | None
    tags: list[str]
    source: str
    current_revision: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CandidateAnswerRevisionRead(BaseModel):
    """Read-only historical snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    answer_id: str
    revision: int
    question_snapshot: str
    answer_snapshot: str
    category_snapshot: str | None
    tags_snapshot: list[str]
    source: str
    content_hash: str
    created_at: datetime
