"""Contract and policy tests for the pluggable job-source framework."""

import asyncio

import httpx
import pytest

from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import SourceCapabilities, SourceListing, SourcePage
from vacancyx.sources.policy import (
    AsyncRateLimiter,
    SourceExecutionGate,
    SourcePolicyError,
    read_bounded_response,
    validate_source_url,
)
from vacancyx.sources.registry import SourceRegistry


class FakeSource:
    source_key = "fixture-board"
    capabilities = SourceCapabilities(pagination=True, published_at=True)

    async def fetch_page(self, *, cursor: str | None, page_size: int) -> SourcePage:
        listing = SourceListing(
            external_id="fixture-1",
            title="Backend Engineer",
            company_name="Example Systems",
            source_url="https://jobs.example.test/roles/fixture-1",
        )
        return SourcePage(items=(listing,), next_cursor=None)


def _config(**overrides: object) -> SourceConfig:
    values: dict[str, object] = {
        "source_key": "fixture-board",
        "allowed_hosts": ("example.test",),
        "requests_per_minute": 120,
        "timeout_seconds": 1,
    }
    values.update(overrides)
    return SourceConfig.model_validate(values)


def test_fake_adapter_obeys_contract_and_registry() -> None:
    adapter = FakeSource()
    registry = SourceRegistry()
    registry.register(adapter, _config())

    registered, config = registry.get("fixture-board")
    page = asyncio.run(registered.fetch_page(cursor=None, page_size=config.page_size))

    assert page.items[0].external_id == "fixture-1"
    assert registered.capabilities.pagination is True
    assert registry.enabled_source_keys() == ("fixture-board",)


def test_registry_rejects_duplicate_and_mismatched_adapters() -> None:
    registry = SourceRegistry()
    registry.register(FakeSource(), _config())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeSource(), _config())

    mismatched = _config(source_key="another-board")
    with pytest.raises(ValueError, match="must match"):
        SourceRegistry().register(FakeSource(), mismatched)


def test_disabled_source_is_not_resolved() -> None:
    registry = SourceRegistry()
    registry.register(FakeSource(), _config(enabled=False))
    assert registry.enabled_source_keys() == ()
    with pytest.raises(ValueError, match="disabled"):
        registry.get("fixture-board")


@pytest.mark.parametrize(
    "url",
    [
        "http://jobs.example.test/roles/1",
        "https://evil.test/roles/1",
        "https://example.test.evil.test/roles/1",
        "https://user:password@example.test/roles/1",
        "https://localhost/roles/1",
        "https://127.0.0.1/roles/1",
        "https://example.test:8443/roles/1",
    ],
)
def test_source_url_policy_rejects_unsafe_or_unapproved_urls(url: str) -> None:
    with pytest.raises(SourcePolicyError):
        validate_source_url(url, _config())


def test_source_url_policy_accepts_allowlisted_subdomain() -> None:
    url = "https://careers.example.test/jobs/1"
    assert validate_source_url(url, _config()) == url


def test_rate_limiter_requires_positive_rate() -> None:
    with pytest.raises(ValueError, match="positive"):
        AsyncRateLimiter(0)


def test_execution_gate_enforces_timeout() -> None:
    async def scenario() -> None:
        gate = SourceExecutionGate(_config(timeout_seconds=0.01))

        async def slow_operation() -> str:
            await asyncio.sleep(0.05)
            return "late"

        with pytest.raises(TimeoutError):
            await gate.execute(slow_operation)

    asyncio.run(scenario())


def test_source_config_rejects_unbounded_limits_and_bad_hosts() -> None:
    with pytest.raises(ValueError):
        _config(requests_per_minute=500)
    with pytest.raises(ValueError):
        _config(allowed_hosts=("https://example.test",))
    with pytest.raises(ValueError):
        _config(max_response_bytes=21 * 1024 * 1024)



def test_read_bounded_response_rejects_declared_and_streamed_oversize() -> None:
    async def scenario() -> None:
        declared = httpx.Response(
            200,
            headers={"Content-Length": "2048"},
            content=b"x",
        )
        with pytest.raises(SourcePolicyError, match="byte limit"):
            await read_bounded_response(declared, max_bytes=1024)

        streamed = httpx.Response(200, content=b"x" * 1025)
        with pytest.raises(SourcePolicyError, match="byte limit"):
            await read_bounded_response(streamed, max_bytes=1024)

    asyncio.run(scenario())
