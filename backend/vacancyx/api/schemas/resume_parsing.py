"""Resume parser output and user-review API contracts."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResumeParseResult(BaseModel):
    """Local extraction output and review state."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    parse_status: str
    parsed_content: dict[str, Any] | None


class ResumeReviewPatch(BaseModel):
    """User-confirmed values kept separate from raw parser suggestions."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    skills: list[str] = Field(default_factory=list, max_length=200)
    links: dict[str, str] = Field(default_factory=dict)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("display_name cannot be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized
