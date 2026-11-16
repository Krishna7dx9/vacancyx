"""Job search and read API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobObservationRead(BaseModel):
    """Safe source provenance summary without raw provider payload or external IDs."""

    model_config = ConfigDict(from_attributes=True)

    source_key: str
    first_seen_at: datetime
    last_seen_at: datetime


class JobRead(BaseModel):
    """Public job facts; source provenance remains available through observations later."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    canonical_url: str | None
    company_name: str
    title: str
    description: str | None
    location: str | None
    work_mode: str | None
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    first_published_at: datetime | None
    last_verified_at: datetime | None
    status: str
    observations: list[JobObservationRead] = []
    created_at: datetime
    updated_at: datetime


class JobSearchResponse(BaseModel):
    """Bounded job-search page and total matching record count."""

    items: list[JobRead]
    total: int
    limit: int
    offset: int
