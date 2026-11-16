"""Public job discovery task API contracts."""

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DiscoverySourceRead(BaseModel):
    source_key: str
    company_name: str
    provider: str


class PublicJobSourceRead(DiscoverySourceRead):
    is_enabled: bool
    managed_by: Literal["environment", "database"]


class PublicJobSourceCreate(BaseModel):
    provider: Literal["greenhouse", "lever"]
    external_key: str = Field(min_length=2, max_length=74)
    company_name: str = Field(min_length=1, max_length=200)
    is_enabled: bool = True

    @field_validator("external_key")
    @classmethod
    def normalize_external_key(cls, value: str) -> str:
        return value.strip()

    @field_validator("company_name")
    @classmethod
    def normalize_company_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("company_name cannot be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_provider_key(self) -> "PublicJobSourceCreate":
        pattern = r"^[A-Za-z0-9_-]+$" if self.provider == "greenhouse" else r"^[A-Za-z0-9-]+$"
        maximum = 69 if self.provider == "greenhouse" else 74
        if len(self.external_key) > maximum or not re.fullmatch(pattern, self.external_key):
            raise ValueError("external_key contains characters not allowed by this provider.")
        return self

    @property
    def source_key(self) -> str:
        return self.provider + "-" + self.external_key.lower()


class PublicJobSourceUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_enabled: bool | None = None

    @field_validator("company_name")
    @classmethod
    def normalize_company_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("company_name cannot be blank.")
        return normalized

    @model_validator(mode="after")
    def require_changes(self) -> "PublicJobSourceUpdate":
        if self.company_name is None and self.is_enabled is None:
            raise ValueError("At least one source field must be provided.")
        return self


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
    source_key: str | None = None
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
