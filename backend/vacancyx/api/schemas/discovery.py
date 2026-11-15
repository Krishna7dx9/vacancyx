"""Public job discovery task API contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiscoverySourceRead(BaseModel):
    source_key: str
    company_name: str
    provider: str


class DiscoverySourcesResponse(BaseModel):
    items: list[DiscoverySourceRead]


class DiscoveryTaskCreate(BaseModel):
    source_keys: list[str] = Field(min_length=1, max_length=20)
    idempotency_key: str = Field(min_length=8, max_length=150, pattern=r"^[A-Za-z0-9._:-]+$")

    @field_validator("source_keys")
    @classmethod
    def require_unique_source_keys(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("source_keys cannot contain blank values.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("source_keys must be unique.")
        return normalized


class TaskStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_type: str
    state: Literal[
        "queued",
        "running",
        "retry_wait",
        "succeeded",
        "partially_succeeded",
        "failed",
        "cancelled",
        "needs_attention",
    ]
    attempts: int
    max_attempts: int
    available_at: datetime
    lease_expires_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    result: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DiscoveryTaskEnqueueResponse(BaseModel):
    items: list[TaskStatusRead]


class DiscoveryTaskListResponse(BaseModel):
    items: list[TaskStatusRead]
    limit: int
    offset: int
