from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.config import Settings
from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_candidate_profile_create_read_update_and_list(client: TestClient) -> None:
    created = client.post(
        "/api/v1/candidates",
        json={
            "display_name": "Synthetic Candidate",
            "skills": ["Python", "SQL"],
            "education": [{"degree": "B.Tech"}],
            "experience": [{"role": "Backend Intern"}],
        },
    )
    assert created.status_code == 201
    profile = created.json()
    candidate_id = profile["id"]
    assert profile["display_name"] == "Synthetic Candidate"
    assert profile["skills"] == ["Python", "SQL"]

    fetched = client.get(f"/api/v1/candidates/{candidate_id}")
    assert fetched.status_code == 200
    assert fetched.json()["education"][0]["degree"] == "B.Tech"

    updated = client.patch(
        f"/api/v1/candidates/{candidate_id}",
        json={"location": "Remote", "skills": []},
    )
    assert updated.status_code == 200
    assert updated.json()["location"] == "Remote"
    assert updated.json()["skills"] == []
    assert updated.json()["display_name"] == "Synthetic Candidate"

    listed = client.get("/api/v1/candidates")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [candidate_id]


def test_candidate_profile_rejects_unknown_fields_and_null_name(client: TestClient) -> None:
    extra_field = client.post(
        "/api/v1/candidates",
        json={"display_name": "Candidate", "hardcoded_resume": "not-allowed"},
    )
    assert extra_field.status_code == 422

    null_name = client.patch(
        "/api/v1/candidates/unknown",
        json={"display_name": None},
    )
    assert null_name.status_code == 422

    blank_name = client.post("/api/v1/candidates", json={"display_name": "   "})
    assert blank_name.status_code == 422

    null_active = client.patch("/api/v1/candidates/unknown", json={"is_active": None})
    assert null_active.status_code == 422


def test_candidate_profile_not_found_and_empty_patch(client: TestClient) -> None:
    missing = client.get("/api/v1/candidates/not-a-real-id")
    assert missing.status_code == 404

    empty_patch = client.patch("/api/v1/candidates/not-a-real-id", json={})
    assert empty_patch.status_code == 400

    missing_update = client.patch(
        "/api/v1/candidates/not-a-real-id", json={"location": "Remote"}
    )
    assert missing_update.status_code == 404


def test_candidate_profile_pagination_is_bounded(client: TestClient) -> None:
    invalid_limit = client.get("/api/v1/candidates?limit=1000")
    assert invalid_limit.status_code == 422

def test_resume_upload_endpoint_uses_local_storage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from vacancyx.api.routes import resumes as resume_routes

    monkeypatch.setattr(resume_routes, "get_settings", lambda: Settings(storage_dir=tmp_path))
    created = client.post(
        "/api/v1/candidates",
        json={"display_name": "Synthetic Upload Candidate"},
    )
    candidate_id = created.json()["id"]

    uploaded = client.post(
        f"/api/v1/candidates/{candidate_id}/resumes",
        files={"file": ("resume.pdf", b"%PDF-1.7\\nsynthetic", "application/pdf")},
    )
    assert uploaded.status_code == 201
    metadata = uploaded.json()
    assert metadata["candidate_id"] == candidate_id
    assert metadata["original_filename"] == "resume.pdf"
    assert metadata["parse_status"] == "pending"
    assert (tmp_path / metadata["id"]).exists() is False
    assert (tmp_path / "resumes").is_dir()

    listed = client.get(f"/api/v1/candidates/{candidate_id}/resumes")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [metadata["id"]]
