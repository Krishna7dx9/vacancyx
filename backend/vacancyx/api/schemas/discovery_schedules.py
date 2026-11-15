"""Recurring discovery schedule API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiscoveryScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    source_keys: list[str] = Field(min_length=1, max_length=100)
    interval_seconds: int = Field(ge=60, le=2_592_000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Schedule name cannot be blank.")
        return normalized

    @field_validator("source_keys")
    @classmethod
    def normalize_source_keys(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 120 for value in normalized):
            raise ValueError("Source keys must contain 1 to 120 characters.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Source keys cannot contain duplicates.")
        return sorted(normalized)


class DiscoveryScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool


class DiscoveryScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    source_keys: list[str]
    interval_seconds: int
    is_enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None
    run_number: int
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime


class DiscoveryScheduleList(BaseModel):
    items: list[DiscoveryScheduleRead]
    total: int
