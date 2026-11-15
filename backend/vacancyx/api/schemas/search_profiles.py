"""Candidate-owned search profile and match API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vacancyx.matching.criteria import MatchCriteria
from vacancyx.matching.engine import MatchResult
from vacancyx.api.schemas.jobs import JobRead


class SearchProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    criteria: MatchCriteria
    is_enabled: bool = True


class SearchProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    criteria: MatchCriteria | None = None
    is_enabled: bool | None = None


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
