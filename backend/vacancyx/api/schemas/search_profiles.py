"""Candidate-owned search profile and match API contracts."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

from vacancyx.matching.criteria import MatchCriteria
from vacancyx.matching.engine import MatchResult
from vacancyx.api.schemas.jobs import JobRead


class SearchProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    criteria: MatchCriteria
    is_enabled: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Search profile name must not be blank.")
        return normalized


class SearchProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    criteria: MatchCriteria | None = None
    is_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_patch_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Search profile name cannot be null.")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Search profile name must not be blank.")
        return normalized

    @field_validator("criteria")
    @classmethod
    def criteria_cannot_be_null(cls, value: MatchCriteria | None) -> MatchCriteria:
        if value is None:
            raise ValueError("Search criteria cannot be null.")
        return value

    @field_validator("is_enabled")
    @classmethod
    def enabled_cannot_be_null(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("is_enabled cannot be null.")
        return value


class SearchProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    name: str
    criteria: MatchCriteria
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class SearchProfileMatchItem(BaseModel):
    job: JobRead
    match: MatchResult


class SearchProfileMatchResponse(BaseModel):
    profile_id: str
    total_jobs_available: int
    evaluated_count: int
    truncated: bool
    items: list[SearchProfileMatchItem]
    limit: int
    offset: int
