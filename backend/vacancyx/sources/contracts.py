"""Stable source adapter contracts; source-specific parsing stays outside the domain."""

import ipaddress
from datetime import datetime
from urllib.parse import urlsplit
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceCapabilities(BaseModel):
    """Capabilities an adapter can truthfully provide."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pagination: bool = True
    published_at: bool = False
    salary: bool = False
    work_mode: bool = False
    employment_type: bool = False


class SourceListing(BaseModel):
    """Normalized listing payload returned by an adapter, before persistence/deduplication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=240)
    company_name: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=100_000)
    location: str | None = Field(default=None, max_length=240)
    work_mode: str | None = Field(default=None, max_length=30)
    employment_type: str | None = Field(default=None, max_length=40)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    published_at: datetime | None = None

    @field_validator("source_url")
    @classmethod
    def require_safe_https_source_url(cls, value: str) -> str:
        """Reject executable, local, credential-bearing, and non-HTTPS listing links."""
        if "\\" in value or any(ord(character) <= 32 for character in value):
            raise ValueError("source_url must be a safe absolute HTTPS URL.")
        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as error:
            raise ValueError("source_url must be a safe absolute HTTPS URL.") from error
        if (
            parsed.scheme.casefold() != "https"
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
        ):
            raise ValueError("source_url must be a safe absolute HTTPS URL.")
        host = hostname.casefold().rstrip(".")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("source_url must not target an IP literal.")
        if host == "localhost" or host.endswith(".localhost") or "." not in host:
            raise ValueError("source_url must not target a local or single-label host.")
        return value

    @field_validator("published_at")
    @classmethod
    def require_timezone_for_published_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("published_at must include a timezone.")
        return value


class SourcePage(BaseModel):
    """One bounded page of normalized listings and an opaque continuation cursor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[SourceListing, ...] = Field(max_length=100)
    next_cursor: str | None = Field(default=None, max_length=2048)


class JobSourceAdapter(Protocol):
    """Port implemented by each source-specific adapter."""

    @property
    def source_key(self) -> str:
        """Stable, lowercase identifier matching SourceConfig.source_key."""

    @property
    def capabilities(self) -> SourceCapabilities:
        """Declare supported fields and pagination behavior."""

    async def fetch_page(self, *, cursor: str | None, page_size: int) -> SourcePage:
        """Fetch one page; never exceed page_size and return an opaque next cursor."""
