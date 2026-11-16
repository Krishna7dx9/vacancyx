"""Public Greenhouse/Lever adapter and registry factory tests."""

import asyncio
from datetime import UTC

import httpx
import pytest

from vacancyx.config import Settings
from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import SourceListing
from vacancyx.sources.factory import build_source_registry, configured_source_descriptors
from vacancyx.sources.greenhouse import GreenhouseJobBoardAdapter
from vacancyx.sources.lever import LeverPostingsAdapter
from vacancyx.sources.policy import SourcePolicyError


def _source_config(source_key: str, host: str) -> SourceConfig:
    return SourceConfig(
        source_key=source_key,
        allowed_hosts=(host,),
        page_size=10,
    )


def test_greenhouse_adapter_maps_listing_and_validates_next_page() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 123,
                        "title": "Backend Engineer",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                        "content": "<p>Build APIs</p>",
                        "location": {"name": "Remote - India"},
                    }
                ]
            },
            headers={
                "Link": (
                    '<https://boards-api.greenhouse.io/v1/boards/acme/jobs?page=2>; rel="next"'
                )
            },
        )

    adapter = GreenhouseJobBoardAdapter(
        source_key="greenhouse-acme",
        board_token="acme",
        company_name="Acme",
        config=_source_config("greenhouse-acme", "boards-api.greenhouse.io"),
        transport=httpx.MockTransport(handler),
    )
    page = asyncio.run(adapter.fetch_page(cursor=None, page_size=10))

    assert page.items[0].external_id == "123"
    assert page.items[0].company_name == "Acme"
    assert page.items[0].title == "Backend Engineer"
    assert page.items[0].location == "Remote - India"
    assert page.next_cursor == (
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs?page=2"
    )
    assert requests[0].url.scheme == "https"
    assert requests[0].headers["user-agent"].startswith("VacancyX/")


def test_greenhouse_adapter_rejects_untrusted_pagination_host() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"jobs": []},
            headers={"Link": '<https://evil.example/jobs?page=2>; rel="next"'},
        )

    adapter = GreenhouseJobBoardAdapter(
        source_key="greenhouse-acme",
        board_token="acme",
        company_name="Acme",
        config=_source_config("greenhouse-acme", "boards-api.greenhouse.io"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(SourcePolicyError):
        asyncio.run(adapter.fetch_page(cursor=None, page_size=10))


def test_lever_adapter_maps_salary_work_mode_and_pagination() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "id": "posting-1",
                    "text": "Python API Engineer",
                    "hostedUrl": "https://jobs.lever.co/acme/posting-1",
                    "descriptionPlain": "Build reliable APIs",
                    "categories": {
                        "location": "India - Remote",
                        "commitment": "Full-time",
                    },
                    "workplaceType": "remote",
                    "salaryRange": {
                        "min": 1200000,
                        "max": 1800000,
                        "currency": "INR",
                        "interval": "year",
                    },
                    "createdAt": 1700000000000,
                }
            ],
        )

    adapter = LeverPostingsAdapter(
        source_key="lever-acme",
        site_slug="acme",
        company_name="Acme",
        config=_source_config("lever-acme", "api.lever.co"),
        transport=httpx.MockTransport(handler),
    )
    page = asyncio.run(adapter.fetch_page(cursor="10", page_size=1))

    listing = page.items[0]
    assert listing.external_id == "posting-1"
    assert listing.title == "Python API Engineer"
    assert listing.location == "India - Remote"
    assert listing.work_mode == "remote"
    assert listing.employment_type == "Full-time"
    assert listing.salary_min == 1200000
    assert listing.salary_max == 1800000
    assert listing.salary_currency == "INR"
    assert listing.published_at is not None
    assert listing.published_at.utcoffset() == UTC.utcoffset(listing.published_at)
    assert page.next_cursor == "11"
    assert requests[0].url.params["skip"] == "10"


def test_lever_adapter_rejects_invalid_cursor() -> None:
    adapter = LeverPostingsAdapter(
        source_key="lever-acme",
        site_slug="acme",
        company_name="Acme",
        config=_source_config("lever-acme", "api.lever.co"),
    )
    with pytest.raises(ValueError, match="non-negative integer"):
        asyncio.run(adapter.fetch_page(cursor="../other", page_size=10))


def test_source_factory_registers_only_enabled_configured_boards() -> None:
    settings = Settings(
        _env_file=None,
        greenhouse_boards=[
            {"board_token": "Acme", "company_name": "Acme"},
            {"board_token": "disabled", "company_name": "Disabled", "enabled": False},
        ],
        lever_sites=[{"site_slug": "beta", "company_name": "Beta"}],
    )
    registry = build_source_registry(settings)

    assert registry.enabled_source_keys() == ("greenhouse-acme", "lever-beta")
    assert [item["company_name"] for item in configured_source_descriptors(settings)] == [
        "Acme",
        "Beta",
    ]
    assert registry.get("greenhouse-acme")[1].allowed_hosts == (
        "boards-api.greenhouse.io",
    )


def test_settings_reject_duplicate_public_source_keys() -> None:
    with pytest.raises(ValueError, match="source keys must be unique"):
        Settings(
            _env_file=None,
            greenhouse_boards=[
                {"board_token": "Acme", "company_name": "Acme"},
                {"board_token": "acme", "company_name": "Acme Duplicate"},
            ],
        )



def test_greenhouse_adapter_rejects_oversized_response_body() -> None:
    adapter = GreenhouseJobBoardAdapter(
        source_key="greenhouse-acme",
        board_token="acme",
        company_name="Acme",
        config=SourceConfig(
            source_key="greenhouse-acme",
            allowed_hosts=("boards-api.greenhouse.io",),
            max_response_bytes=1024,
        ),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"x" * 1025)
        ),
    )
    with pytest.raises(SourcePolicyError, match="byte limit"):
        asyncio.run(adapter.fetch_page(cursor=None, page_size=10))


def test_lever_adapter_rejects_oversized_response_body() -> None:
    adapter = LeverPostingsAdapter(
        source_key="lever-acme",
        site_slug="acme",
        company_name="Acme",
        config=SourceConfig(
            source_key="lever-acme",
            allowed_hosts=("api.lever.co",),
            max_response_bytes=1024,
        ),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"x" * 1025)
        ),
    )
    with pytest.raises(SourcePolicyError, match="byte limit"):
        asyncio.run(adapter.fetch_page(cursor=None, page_size=10))



@pytest.mark.parametrize(
    "source_url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "http://jobs.example.com/role/1",
        "https://user:password@jobs.example.com/role/1",
        "https://localhost/role/1",
        "https://127.0.0.1/role/1",
        "https://jobs.example.com:8443/role/1",
        "https://jobs.example.com\\\\@evil.example/role/1",
    ],
)
def test_source_listing_rejects_unsafe_external_links(source_url: str) -> None:
    with pytest.raises(ValueError, match="source_url"):
        SourceListing(
            external_id="role-1",
            title="Backend Engineer",
            company_name="Example",
            source_url=source_url,
        )


def test_source_listing_accepts_public_https_link() -> None:
    listing = SourceListing(
        external_id="role-1",
        title="Backend Engineer",
        company_name="Example",
        source_url="https://jobs.example.com/role/1",
    )
    assert listing.source_url == "https://jobs.example.com/role/1"
