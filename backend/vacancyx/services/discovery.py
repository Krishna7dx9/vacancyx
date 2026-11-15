"""Bounded, idempotent ingestion of normalized job-source pages."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from ipaddress import ip_address
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from vacancyx.models import Job, JobObservation
from vacancyx.repositories.core import JobRepository
from vacancyx.repositories.observations import JobObservationRepository
from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import JobSourceAdapter, SourceListing, SourcePage
from vacancyx.sources.policy import SourceExecutionGate, SourcePolicyError
from vacancyx.sources.registry import SourceRegistry

_TRACKING_PARAMETERS = frozenset(
    {
        "fbclid",
        "gclid",
        "gh_src",
        "igshid",
        "mc_cid",
        "mc_eid",
        "ref",
        "source",
        "trk",
        "trackingid",
    }
)


@dataclass(frozen=True)
class DiscoverySummary:
    """Safe, aggregate outcome for one bounded source run."""

    source_key: str
    pages_fetched: int = 0
    listings_seen: int = 0
    jobs_created: int = 0
    observations_created: int = 0
    observations_updated: int = 0
    truncated: bool = False
    error_codes: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        """Distinguish full, partial and failed runs without leaking source payloads."""
        if self.error_codes or self.truncated:
            return "partial" if self.pages_fetched else "failed"
        return "completed"


def canonicalize_job_url(url: str) -> str:
    """Normalize safe HTTPS listing URLs without guessing identity from title/company."""
    try:
        parsed = urlsplit(url.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise SourcePolicyError("Malformed listing URL.") from exc

    if parsed.scheme.lower() != "https" or hostname is None:
        raise SourcePolicyError("Listing URLs must use HTTPS and include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise SourcePolicyError("Credentials are not allowed in listing URLs.")
    if port not in (None, 443):
        raise SourcePolicyError("Non-default listing URL ports are not allowed.")

    host = hostname.encode("idna").decode("ascii").lower().rstrip(".")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise SourcePolicyError("IP-literal listing URLs are not allowed.")
    if host == "localhost" or host.endswith(".localhost") or "." not in host:
        raise SourcePolicyError("Local and single-label listing hosts are not allowed.")

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_PARAMETERS
    ]
    query_items.sort()
    return urlunsplit(("https", host, path, urlencode(query_items, doseq=True), ""))


class JobDiscoveryService:
    """Fetch source pages outside DB transactions and commit each page atomically."""

    def __init__(
        self,
        session: Session,
        registry: SourceRegistry,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._registry = registry
        self._clock = clock or (lambda: datetime.now(UTC))
        self._jobs = JobRepository(session)
        self._observations = JobObservationRepository(session)

    async def discover_source(self, source_key: str) -> DiscoverySummary:
        """Fetch at most the configured page count and preserve already committed pages."""
        adapter, config = self._registry.get(source_key)
        gate = SourceExecutionGate(config)
        cursor: str | None = None
        requested_cursors: set[str | None] = set()
        pages_fetched = 0
        listings_seen = 0
        jobs_created = 0
        observations_created = 0
        observations_updated = 0
        errors: list[str] = []
        truncated = False

        for _page_number in range(config.max_pages_per_run):
            if cursor in requested_cursors:
                errors.append("pagination_cycle")
                break
            requested_cursors.add(cursor)

            try:
                page = await gate.execute(
                    lambda: adapter.fetch_page(cursor=cursor, page_size=config.page_size)
                )
            except TimeoutError:
                errors.append("source_timeout")
                break
            except Exception:
                errors.append("source_request_failed")
                break

            if len(page.items) > config.page_size:
                errors.append("source_page_limit_exceeded")
                break

            try:
                canonical_urls = tuple(
                    canonicalize_job_url(item.source_url) for item in page.items
                )
            except SourcePolicyError:
                errors.append("unsafe_listing_url")
                break

            try:
                page_counts = self._persist_page(
                    source_key=source_key,
                    page=page,
                    canonical_urls=canonical_urls,
                )
            except Exception:
                errors.append("persistence_failed")
                break

            pages_fetched += 1
            listings_seen += len(page.items)
            jobs_created += page_counts[0]
            observations_created += page_counts[1]
            observations_updated += page_counts[2]

            if page.next_cursor is None:
                break
            if page.next_cursor in requested_cursors:
                errors.append("pagination_cycle")
                break
            cursor = page.next_cursor
        else:
            truncated = cursor is not None

        return DiscoverySummary(
            source_key=source_key,
            pages_fetched=pages_fetched,
            listings_seen=listings_seen,
            jobs_created=jobs_created,
            observations_created=observations_created,
            observations_updated=observations_updated,
            truncated=truncated,
            error_codes=tuple(errors),
        )

    def _persist_page(
        self,
        *,
        source_key: str,
        page: SourcePage,
        canonical_urls: tuple[str, ...],
    ) -> tuple[int, int, int]:
        """Upsert jobs and source identities in one short transaction per page."""
        jobs_created = 0
        observations_created = 0
        observations_updated = 0
        now = self._clock()

        with self._session.begin():
            for listing, canonical_url in zip(page.items, canonical_urls, strict=True):
                job = self._jobs.find_by_canonical_url(canonical_url)
                if job is None:
                    job = self._jobs.add(self._new_job(listing, canonical_url, now))
                    jobs_created += 1
                else:
                    self._refresh_job(job, listing, now)

                observation = self._observations.get_by_source_identity(
                    source_key, listing.external_id
                )
                evidence = self._evidence(listing, canonical_url)
                if observation is None:
                    self._observations.add(
                        JobObservation(
                            job_id=job.id,
                            source_key=source_key,
                            external_id=listing.external_id,
                            source_url=listing.source_url,
                            first_seen_at=now,
                            last_seen_at=now,
                            evidence=evidence,
                        )
                    )
                    observations_created += 1
                else:
                    observation.job_id = job.id
                    observation.source_url = listing.source_url
                    observation.last_seen_at = now
                    observation.evidence = evidence
                    observations_updated += 1

        return jobs_created, observations_created, observations_updated

    @staticmethod
    def _new_job(listing: SourceListing, canonical_url: str, now: datetime) -> Job:
        return Job(
            canonical_url=canonical_url,
            company_name=listing.company_name,
            title=listing.title,
            description=listing.description,
            location=listing.location,
            work_mode=listing.work_mode,
            employment_type=listing.employment_type,
            salary_min=listing.salary_min,
            salary_max=listing.salary_max,
            salary_currency=listing.salary_currency,
            first_published_at=listing.published_at,
            last_verified_at=now,
            status="open",
        )

    @staticmethod
    def _refresh_job(job: Job, listing: SourceListing, now: datetime) -> None:
        job.company_name = listing.company_name
        job.title = listing.title
        for field in (
            "description",
            "location",
            "work_mode",
            "employment_type",
            "salary_min",
            "salary_max",
            "salary_currency",
        ):
            value = getattr(listing, field)
            if value is not None:
                setattr(job, field, value)
        if listing.published_at is not None and (
            job.first_published_at is None or listing.published_at < job.first_published_at
        ):
            job.first_published_at = listing.published_at
        job.last_verified_at = now

    @staticmethod
    def _evidence(listing: SourceListing, canonical_url: str) -> dict[str, str | int | None]:
        published_at = listing.published_at.isoformat() if listing.published_at else None
        return {
            "canonical_url": canonical_url,
            "title": listing.title,
            "company_name": listing.company_name,
            "published_at": published_at,
        }
