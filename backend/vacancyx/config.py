"""Validated application configuration.

Candidate profiles and search preferences belong in the database, not environment variables.
Environment configuration is reserved for process/runtime concerns.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()
