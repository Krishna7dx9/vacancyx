"""Integration tests for paginated, idempotent job-source ingestion."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.models import Job, JobObservation
from vacancyx.services.discovery import JobDiscoveryService, canonicalize_job_url
from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import SourceCapabilities, SourceListing, SourcePage
from vacancyx.sources.registry import SourceRegistry


class FixtureSource:
    capabilities = SourceCapabilities(pagination=True, published_at=True)

    def __init__(
        self,
        source_key: str,
        pages: dict[str | None, SourcePage],
        failures: set[str | None] | None = None,
    ) -> None:
        self.source_key = source_key
        self._pages = pages
        self._failures = failures or set()
        self.requested: list[str | None] = []

    async def fetch_page(self, *, cursor: str | None, page_size: int) -> SourcePage:
        self.requested.append(cursor)
        if cursor in self._failures:
            raise TimeoutError("synthetic timeout")
        return self._pages[cursor]


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def _listing(
    external_id: str,
    url: str = "https://jobs.example.test/roles/backend-engineer",
    *,
    title: str = "Backend Engineer",
) -> SourceListing:
    return SourceListing(
        external_id=external_id,
        title=title,
        company_name="Example Systems",
        source_url=url,
        location="Remote, India",
    )


def _source_config(source_key: str, **overrides: object) -> SourceConfig:
    values: dict[str, object] = {
        "source_key": source_key,
        "allowed_hosts": ("example.test",),
        "requests_per_minute": 120,
        "timeout_seconds": 1,
        "page_size": 10,
        "max_pages_per_run": 5,
    }
    values.update(overrides)
    return SourceConfig.model_validate(values)


def _registry(*sources: FixtureSource) -> SourceRegistry:
    registry = SourceRegistry()
    for source in sources:
        registry.register(source, _source_config(source.source_key))
    return registry


def test_canonical_url_removes_tracking_and_normalizes_path() -> None:
    canonical = canonicalize_job_url(
        "https://JOBS.EXAMPLE.test/roles/123/?utm_source=feed&b=2&a=1&fbclid=click#apply"
    )
    assert canonical == "https://jobs.example.test/roles/123?a=1&b=2"


def test_canonical_url_rejects_non_public_or_non_https_urls() -> None:
    for url in (
        "http://jobs.example.test/role/1",
        "https://localhost/role/1",
        "https://127.0.0.1/role/1",
        "https://user:pass@jobs.example.test/role/1",
    ):
        with pytest.raises(ValueError):
            canonicalize_job_url(url)


def test_pagination_and_cross_source_deduplication(db_session: Session) -> None:
    first = FixtureSource(
        "board-one",
        {
            None: SourcePage(
                items=(
                    _listing(
                        "one-1",
                        "https://jobs.example.test/roles/123/?utm_source=board-one",
                    ),
                ),
                next_cursor="page-2",
            ),
            "page-2": SourcePage(
                items=(_listing("one-2", "https://jobs.example.test/roles/123#apply"),),
            ),
        },
    )
    second = FixtureSource(
        "board-two",
        {
            None: SourcePage(
                items=(_listing("two-1", "https://jobs.example.test/roles/123?ref=board-two"),),
            )
        },
    )
    service = JobDiscoveryService(db_session, _registry(first, second))

    first_result = asyncio.run(service.discover_source("board-one"))
    second_result = asyncio.run(service.discover_source("board-two"))

    assert first_result.status == "completed"
    assert first_result.pages_fetched == 2
    assert first_result.jobs_created == 1
    assert first_result.observations_created == 2
    assert second_result.jobs_created == 0
    assert second_result.observations_created == 1
    assert db_session.scalar(select(func.count()).select_from(Job)) == 1
    assert db_session.scalar(select(func.count()).select_from(JobObservation)) == 3


def test_repeated_ingestion_updates_observation_without_duplicate_job(
    db_session: Session,
) -> None:
    source = FixtureSource(
        "board-one",
        {None: SourcePage(items=(_listing("stable-id"),))},
    )
    service = JobDiscoveryService(db_session, _registry(source))

    first = asyncio.run(service.discover_source("board-one"))
    observation_before = db_session.scalar(select(JobObservation))
    assert observation_before is not None
    first_seen = observation_before.first_seen_at
    db_session.rollback()

    second = asyncio.run(service.discover_source("board-one"))
    observation_after = db_session.scalar(select(JobObservation))

    assert first.jobs_created == 1
    assert second.jobs_created == 0
    assert second.observations_created == 0
    assert second.observations_updated == 1
    assert observation_after is not None
    assert observation_after.first_seen_at == first_seen
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(Job)) == 1
    assert db_session.scalar(select(func.count()).select_from(JobObservation)) == 1


def test_source_failure_preserves_previously_committed_pages(db_session: Session) -> None:
    source = FixtureSource(
        "board-one",
        {None: SourcePage(items=(_listing("page-one"),), next_cursor="page-two")},
        failures={"page-two"},
    )
    result = asyncio.run(
        JobDiscoveryService(db_session, _registry(source)).discover_source("board-one")
    )

    assert result.status == "partial"
    assert result.pages_fetched == 1
    assert result.error_codes == ("source_timeout",)
    assert db_session.scalar(select(func.count()).select_from(Job)) == 1


def test_pagination_cycle_is_detected_after_preserving_page(db_session: Session) -> None:
    source = FixtureSource(
        "board-one",
        {
            None: SourcePage(items=(_listing("page-one"),), next_cursor="same"),
            "same": SourcePage(items=(_listing("page-two"),), next_cursor="same"),
        },
    )
    result = asyncio.run(
        JobDiscoveryService(db_session, _registry(source)).discover_source("board-one")
    )

    assert result.status == "partial"
    assert result.pages_fetched == 2
    assert result.error_codes == ("pagination_cycle",)
    assert db_session.scalar(select(func.count()).select_from(JobObservation)) == 2


def test_page_limit_truncates_run_without_losing_current_page(db_session: Session) -> None:
    source = FixtureSource(
        "board-one",
        {None: SourcePage(items=(_listing("page-one"),), next_cursor="page-two")},
    )
    registry = SourceRegistry()
    registry.register(source, _source_config("board-one", max_pages_per_run=1))

    result = asyncio.run(
        JobDiscoveryService(db_session, registry).discover_source("board-one")
    )

    assert result.status == "partial"
    assert result.truncated is True
    assert result.pages_fetched == 1
    assert db_session.scalar(select(func.count()).select_from(Job)) == 1


def test_unsafe_listing_url_rejects_entire_page(db_session: Session) -> None:
    source = FixtureSource(
        "board-one",
        {None: SourcePage(items=(_listing("unsafe", "http://jobs.example.test/role/1"),))},
    )
    result = asyncio.run(
        JobDiscoveryService(db_session, _registry(source)).discover_source("board-one")
    )

    assert result.status == "failed"
    assert result.error_codes == ("unsafe_listing_url",)
    assert db_session.scalar(select(func.count()).select_from(Job)) == 0


def test_adapter_cannot_exceed_configured_page_size(db_session: Session) -> None:
    source = FixtureSource(
        "board-one",
        {None: SourcePage(items=(_listing("one"), _listing("two")))},
    )
    registry = SourceRegistry()
    registry.register(source, _source_config("board-one", page_size=1))

    result = asyncio.run(
        JobDiscoveryService(db_session, registry).discover_source("board-one")
    )

    assert result.status == "failed"
    assert result.error_codes == ("source_page_limit_exceeded",)
    assert db_session.scalar(select(func.count()).select_from(Job)) == 0


def test_discovery_uses_injected_clock(db_session: Session) -> None:
    fixed = datetime(2026, 1, 2, tzinfo=UTC)
    source = FixtureSource("board-one", {None: SourcePage(items=(_listing("fixed-time"),))})
    result = asyncio.run(
        JobDiscoveryService(db_session, _registry(source), clock=lambda: fixed).discover_source(
            "board-one"
        )
    )
    job = db_session.scalar(select(Job))

    assert result.status == "completed"
    assert job is not None
    assert job.last_verified_at is not None
    assert job.last_verified_at.replace(tzinfo=UTC) == fixed


def test_first_published_at_keeps_earliest_timezone_aware_value(db_session: Session) -> None:
    original = _listing("published", title="Backend Engineer").model_copy(
        update={"published_at": datetime(2025, 5, 1, tzinfo=UTC)}
    )
    source = FixtureSource("board-one", {None: SourcePage(items=(original,))})
    registry = _registry(source)
    service = JobDiscoveryService(db_session, registry)
    asyncio.run(service.discover_source("board-one"))

    db_session.expire_all()
    earlier = original.model_copy(
        update={
            "published_at": datetime(2024, 5, 1, tzinfo=UTC),
            "title": "Senior Backend Engineer",
        }
    )
    source._pages[None] = SourcePage(items=(earlier,))
    asyncio.run(service.discover_source("board-one"))

    job = db_session.scalar(select(Job))
    assert job is not None
    assert job.first_published_at is not None
    assert job.first_published_at.replace(tzinfo=UTC) == datetime(
        2024, 5, 1, tzinfo=UTC
    )
    assert job.title == "Senior Backend Engineer"


def test_source_listing_rejects_naive_publication_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone"):
        SourceListing(
            external_id="naive",
            title="Backend Engineer",
            company_name="Example Systems",
            source_url="https://jobs.example.test/roles/naive",
            published_at=datetime(2025, 5, 1),
        )
