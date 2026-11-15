"""API integration tests for job search and candidate-owned matching profiles."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app
from vacancyx.models import Job


@pytest.fixture
def api() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def _create_candidate(client: TestClient, name: str = "Synthetic Candidate") -> str:
    response = client.post(
        "/api/v1/candidates",
        json={"display_name": name, "skills": ["Python", "SQL"]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_job(
    factory: sessionmaker[Session],
    *,
    suffix: str,
    title: str = "Backend Engineer",
    description: str | None = "Build Python and SQL services.",
    location: str | None = "Remote, India",
    work_mode: str | None = "Remote",
    employment_type: str | None = "Full-time",
    salary_min: int | None = 1_200_000,
    salary_max: int | None = 1_600_000,
    salary_currency: str | None = "INR",
    status: str = "open",
) -> None:
    with factory() as session, session.begin():
        session.add(
            Job(
                canonical_url=f"https://jobs.example.test/roles/{suffix}",
                company_name="Example Systems",
                title=title,
                description=description,
                location=location,
                work_mode=work_mode,
                employment_type=employment_type,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                last_verified_at=datetime.now(UTC),
                status=status,
            )
        )


def _criteria() -> dict[str, object]:
    return {
        "target_titles": ["Backend Engineer"],
        "excluded_keywords": ["intern"],
        "required_skills": ["Python", "SQL"],
        "allowed_locations": ["Remote"],
        "work_modes": ["Remote"],
        "employment_types": ["Full-time"],
        "minimum_salary": 1_000_000,
        "salary_currency": "INR",
    }


def test_search_profile_create_list_get_and_patch(api) -> None:
    client, _factory = api
    candidate_id = _create_candidate(client)
    created = client.post(
        f"/api/v1/candidates/{candidate_id}/search-profiles",
        json={"name": "Backend roles", "criteria": _criteria()},
    )
    assert created.status_code == 201
    profile = created.json()
    profile_id = profile["id"]
    assert profile["criteria"]["salary_currency"] == "INR"

    listed = client.get(f"/api/v1/candidates/{candidate_id}/search-profiles")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [profile_id]

    fetched = client.get(
        f"/api/v1/candidates/{candidate_id}/search-profiles/{profile_id}"
    )
    assert fetched.status_code == 200

    updated = client.patch(
        f"/api/v1/candidates/{candidate_id}/search-profiles/{profile_id}",
        json={"name": "Backend roles in India"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Backend roles in India"
    assert updated.json()["criteria"] == profile["criteria"]


def test_search_profile_rejects_invalid_and_null_patch_values(api) -> None:
    client, _factory = api
    candidate_id = _create_candidate(client)

    invalid_criteria = client.post(
        f"/api/v1/candidates/{candidate_id}/search-profiles",
        json={"name": "Invalid", "criteria": {"minimum_salary": 1000000}},
    )
    assert invalid_criteria.status_code == 422

    created = client.post(
        f"/api/v1/candidates/{candidate_id}/search-profiles",
        json={"name": "Valid", "criteria": {}},
    )
    profile_id = created.json()["id"]
    base = f"/api/v1/candidates/{candidate_id}/search-profiles/{profile_id}"

    assert client.patch(base, json={}).status_code == 400
    assert client.patch(base, json={"name": None}).status_code == 422
    assert client.patch(base, json={"criteria": None}).status_code == 422
    assert client.patch(base, json={"is_enabled": None}).status_code == 422
    assert client.post(
        f"/api/v1/candidates/{candidate_id}/search-profiles",
        json={"name": "   ", "criteria": {}},
    ).status_code == 422


def test_search_profile_ownership_and_missing_candidate(api) -> None:
    client, _factory = api
    owner_id = _create_candidate(client, "Owner")
    other_id = _create_candidate(client, "Other")
    created = client.post(
        f"/api/v1/candidates/{owner_id}/search-profiles",
        json={"name": "Private search", "criteria": {}},
    )
    profile_id = created.json()["id"]

    assert client.get(
        f"/api/v1/candidates/{other_id}/search-profiles/{profile_id}"
    ).status_code == 404
    assert client.post(
        "/api/v1/candidates/missing/search-profiles",
        json={"name": "No owner", "criteria": {}},
    ).status_code == 404


def test_job_search_filters_and_pagination(api) -> None:
    client, factory = api
    _add_job(factory, suffix="remote")
    _add_job(factory, suffix="onsite", location="Bengaluru", work_mode="On-site")
    _add_job(factory, suffix="closed", status="closed")

    response = client.get(
        "/api/v1/jobs",
        params={"query": "Backend", "location": "Remote", "status": "open", "limit": 1},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["location"] == "Remote, India"

    missing_currency = client.get("/api/v1/jobs", params={"minimum_salary": 1_000_000})
    assert missing_currency.status_code == 422

    salary_filtered = client.get(
        "/api/v1/jobs",
        params={
            "minimum_salary": 1_000_000,
            "salary_currency": "INR",
            "include_unknown_salary": "false",
        },
    )
    assert salary_filtered.status_code == 200
    assert salary_filtered.json()["total"] == 2

    all_statuses = client.get("/api/v1/jobs", params={"status": "all", "limit": 10})
    assert all_statuses.json()["total"] == 3


def test_job_detail_returns_not_found_for_unknown_id(api) -> None:
    client, _factory = api
    assert client.get("/api/v1/jobs/not-found").status_code == 404


def test_search_profile_evaluation_ranks_and_explains_jobs(api) -> None:
    client, factory = api
    candidate_id = _create_candidate(client)
    profile_response = client.post(
        f"/api/v1/candidates/{candidate_id}/search-profiles",
        json={"name": "Backend jobs", "criteria": _criteria()},
    )
    profile_id = profile_response.json()["id"]

    _add_job(factory, suffix="eligible")
    _add_job(
        factory,
        suffix="review",
        location=None,
    )
    _add_job(factory, suffix="excluded", title="Backend Engineer Intern")

    response = client.post(
        f"/api/v1/candidates/{candidate_id}/search-profiles/{profile_id}/matches",
        params={"limit": 2},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_jobs_available"] == 3
    assert payload["evaluated_count"] == 3
    assert payload["truncated"] is False
    assert [item["match"]["status"] for item in payload["items"]] == [
        "eligible",
        "needs_review",
    ]
    assert payload["items"][0]["match"]["score"] > 0
    assert payload["items"][0]["match"]["rule_version"] == "1.0"
    assert payload["items"][0]["match"]["components"]


def test_disabled_search_profile_cannot_be_evaluated(api) -> None:
    client, _factory = api
    candidate_id = _create_candidate(client)
    created = client.post(
        f"/api/v1/candidates/{candidate_id}/search-profiles",
        json={"name": "Disabled", "criteria": {}, "is_enabled": False},
    )
    profile_id = created.json()["id"]
    response = client.post(
        f"/api/v1/candidates/{candidate_id}/search-profiles/{profile_id}/matches"
    )
    assert response.status_code == 409
