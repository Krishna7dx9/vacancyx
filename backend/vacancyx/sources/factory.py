"""Build safe Greenhouse and Lever source adapters from env and local DB config."""

from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from vacancyx.config import Settings
from vacancyx.models import PublicJobSource
from vacancyx.sources.config import SourceConfig
from vacancyx.sources.greenhouse import GreenhouseJobBoardAdapter
from vacancyx.sources.lever import LeverPostingsAdapter
from vacancyx.sources.registry import SourceRegistry


class SourceDescriptor(TypedDict):
    source_key: str
    company_name: str
    provider: str


class SourceConfiguration(SourceDescriptor):
    is_enabled: bool
    managed_by: str


class _SourceSpec(TypedDict):
    source_key: str
    provider: str
    external_key: str
    company_name: str
    is_enabled: bool
    managed_by: str


def _source_specs(settings: Settings, session: Session | None) -> list[_SourceSpec]:
    """Merge environment bootstrap entries with DB entries; DB wins by source key."""
    specs: dict[str, _SourceSpec] = {}
    for board in settings.greenhouse_boards:
        key = "greenhouse-" + board.board_token.lower()
        specs[key] = {
            "source_key": key,
            "provider": "greenhouse",
            "external_key": board.board_token,
            "company_name": board.company_name,
            "is_enabled": board.enabled,
            "managed_by": "environment",
        }
    for site in settings.lever_sites:
        key = "lever-" + site.site_slug.lower()
        specs[key] = {
            "source_key": key,
            "provider": "lever",
            "external_key": site.site_slug,
            "company_name": site.company_name,
            "is_enabled": site.enabled,
            "managed_by": "environment",
        }

    if session is not None:
        rows = session.scalars(select(PublicJobSource)).all()
        for row in rows:
            specs[row.source_key] = {
                "source_key": row.source_key,
                "provider": row.provider,
                "external_key": row.external_key,
                "company_name": row.company_name,
                "is_enabled": row.is_enabled,
                "managed_by": "database",
            }
    return sorted(
        specs.values(),
        key=lambda item: (item["provider"], item["company_name"].casefold()),
    )


def configured_source_configurations(
    settings: Settings,
    session: Session | None = None,
) -> list[SourceConfiguration]:
    """Return all configured sources for the local source-management workspace."""
    return [
        {
            "source_key": item["source_key"],
            "company_name": item["company_name"],
            "provider": "Greenhouse" if item["provider"] == "greenhouse" else "Lever",
            "is_enabled": item["is_enabled"],
            "managed_by": item["managed_by"],
        }
        for item in _source_specs(settings, session)
    ]


def configured_source_descriptors(
    settings: Settings,
    session: Session | None = None,
) -> list[SourceDescriptor]:
    """Return enabled source descriptors for discovery selection."""
    return [
        {
            "source_key": item["source_key"],
            "company_name": item["company_name"],
            "provider": "Greenhouse" if item["provider"] == "greenhouse" else "Lever",
        }
        for item in _source_specs(settings, session)
        if item["is_enabled"]
    ]


def build_source_registry(settings: Settings, session: Session | None = None) -> SourceRegistry:
    """Register enabled sources with provider-specific HTTPS host policies."""
    registry = SourceRegistry()
    for item in _source_specs(settings, session):
        if not item["is_enabled"]:
            continue
        source_key = item["source_key"]
        if len(source_key) > 120:
            raise ValueError("Configured source key is too long.")
        config = SourceConfig(
            source_key=source_key,
            allowed_hosts=(
                ("boards-api.greenhouse.io",)
                if item["provider"] == "greenhouse"
                else ("api.lever.co",)
            ),
            requests_per_minute=30,
            max_concurrent_requests=2,
            timeout_seconds=15,
            max_pages_per_run=10,
            page_size=100,
        )
        if item["provider"] == "greenhouse":
            registry.register(
                GreenhouseJobBoardAdapter(
                    source_key=source_key,
                    board_token=item["external_key"],
                    company_name=item["company_name"],
                    config=config,
                ),
                config,
            )
        else:
            registry.register(
                LeverPostingsAdapter(
                    source_key=source_key,
                    site_slug=item["external_key"],
                    company_name=item["company_name"],
                    config=config,
                ),
                config,
            )
    return registry
