"""Validated application configuration.

Candidate profiles and search preferences belong in the database, not environment variables.
Environment configuration is reserved for process/runtime concerns.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from vacancyx.sources.config import GreenhouseBoardSetting, LeverSiteSetting


class Settings(BaseSettings):
    """Runtime settings loaded from environment and optional local .env file."""

    model_config = SettingsConfigDict(
        env_prefix="VACANCYX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VacancyX"
    database_url: str = "sqlite:///./.vacancyx/vacancyx.db"
    storage_dir: Path = Path(".vacancyx")
    max_resume_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    max_resume_pages: int = Field(default=30, ge=1, le=100)
    max_extracted_chars: int = Field(default=100_000, ge=1_000, le=500_000)
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    worker_poll_interval_seconds: float = Field(default=2.0, gt=0, le=60)
    worker_lease_seconds: int = Field(default=60, ge=1, le=3600)
    worker_retry_base_delay_seconds: int = Field(default=5, ge=0, le=3600)
    worker_retry_max_delay_seconds: int = Field(default=300, ge=0, le=86400)
    greenhouse_boards: list[GreenhouseBoardSetting] = Field(default_factory=list)
    lever_sites: list[LeverSiteSetting] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_worker_retry_bounds(self) -> Self:
        if self.worker_retry_max_delay_seconds < self.worker_retry_base_delay_seconds:
            raise ValueError("worker retry maximum delay must be at least the base delay.")
        source_keys = [
            "greenhouse-" + board.board_token.lower()
            for board in self.greenhouse_boards
            if board.enabled
        ] + [
            "lever-" + site.site_slug.lower()
            for site in self.lever_sites
            if site.enabled
        ]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("Configured public job source keys must be unique.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()
