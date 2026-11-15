"""Validated, candidate-independent configuration for job sources."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceConfig(BaseModel):
    """Operational limits and public-host allowlist for one source adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    enabled: bool = True
    allowed_hosts: tuple[str, ...] = Field(min_length=1, max_length=30)
    requests_per_minute: int = Field(default=30, ge=1, le=120)
    max_concurrent_requests: int = Field(default=2, ge=1, le=10)
    timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    max_pages_per_run: int = Field(default=10, ge=1, le=100)
    page_size: int = Field(default=25, ge=1, le=100)
    user_agent: str = Field(
        default="VacancyX/0.1 (local job discovery; respects source policies)",
        min_length=8,
        max_length=200,
    )

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_hosts(cls, hosts: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for host in hosts:
            value = host.strip().lower().rstrip(".")
            if (
                not value or "://" in value or "/" in value or ":" in value
                or "@" in value or any(character.isspace() for character in value)
            ):
                raise ValueError("Allowed hosts must be bare DNS hostnames.")
            if value not in normalized:
                normalized.append(value)
        if not normalized:
            raise ValueError("At least one allowed host is required.")
        return tuple(normalized)
