"""Build the configured public-source registry from process settings."""

from typing import TypedDict

from vacancyx.config import Settings
from vacancyx.sources.config import SourceConfig
from vacancyx.sources.greenhouse import GreenhouseJobBoardAdapter
from vacancyx.sources.lever import LeverPostingsAdapter
from vacancyx.sources.registry import SourceRegistry


class SourceDescriptor(TypedDict):
    source_key: str
    company_name: str
    provider: str


def configured_source_descriptors(settings: Settings) -> list[SourceDescriptor]:
    """Return only enabled, candidate-independent public source descriptors."""
    descriptors: list[SourceDescriptor] = []
    for board in settings.greenhouse_boards:
        if board.enabled:
            descriptors.append(
                {
                    "source_key": "greenhouse-" + board.board_token.lower(),
                    "company_name": board.company_name,
                    "provider": "Greenhouse",
                }
            )
    for site in settings.lever_sites:
        if site.enabled:
            descriptors.append(
                {
                    "source_key": "lever-" + site.site_slug.lower(),
                    "company_name": site.company_name,
                    "provider": "Lever",
                }
            )
    return descriptors


def build_source_registry(settings: Settings) -> SourceRegistry:
    """Register enabled Greenhouse and Lever boards with strict HTTPS host policies."""
    registry = SourceRegistry()
    for board in settings.greenhouse_boards:
        if not board.enabled:
            continue
        source_key = "greenhouse-" + board.board_token.lower()
        if len(source_key) > 80:
            raise ValueError("Greenhouse board token is too long for a source key.")
        config = SourceConfig(
            source_key=source_key,
            allowed_hosts=("boards-api.greenhouse.io",),
            requests_per_minute=30,
            max_concurrent_requests=2,
            timeout_seconds=15,
            max_pages_per_run=10,
            page_size=100,
        )
        registry.register(
            GreenhouseJobBoardAdapter(
                source_key=source_key,
                board_token=board.board_token,
                company_name=board.company_name,
                config=config,
            ),
            config,
        )

    for site in settings.lever_sites:
        if not site.enabled:
            continue
        source_key = "lever-" + site.site_slug.lower()
        if len(source_key) > 80:
            raise ValueError("Lever site slug is too long for a source key.")
        config = SourceConfig(
            source_key=source_key,
            allowed_hosts=("api.lever.co",),
            requests_per_minute=30,
            max_concurrent_requests=2,
            timeout_seconds=15,
            max_pages_per_run=10,
            page_size=100,
        )
        registry.register(
            LeverPostingsAdapter(
                source_key=source_key,
                site_slug=site.site_slug,
                company_name=site.company_name,
                config=config,
            ),
            config,
        )
    return registry
