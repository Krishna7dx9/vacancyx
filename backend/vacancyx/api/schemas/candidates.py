"""Validated candidate profile API contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CandidateProfileCreate(BaseModel):
    """Create a configurable candidate profile."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    skills: list[str] = Field(default_factory=list, max_length=200)
    education: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    experience: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    links: dict[str, str] = Field(default_factory=dict)


class CandidateProfilePatch(BaseModel):
    """Partially update a candidate without replacing omitted fields."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    skills: list[str] = Field(default_factory=list, max_length=200)
    education: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    experience: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    links: dict[str, str] = Field(default_factory=dict)
    is_active: bool | None = None

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("display_name cannot be null")
        return value


class CandidateProfileRead(BaseModel):
    """Candidate profile representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    email: str | None
    phone: str | None
    location: str | None
    skills: list[str]
    education: list[dict[str, Any]]
    experience: list[dict[str, Any]]
    links: dict[str, str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
