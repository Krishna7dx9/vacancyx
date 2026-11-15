"""Integration tests for immutable, candidate-owned application preparation."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app
from vacancyx.models import ApplicationEvent, ApplicationRevision, Job, Resume


@pytest.fixture
def workspace() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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


def _candidate(client: TestClient, name: str = "Synthetic Candidate") -> str:
    response = client.post(
        "/api/v1/candidates",
        json={"display_name": name, "email": "candidate@example.test", "phone": "0000000000"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _job(factory: sessionmaker[Session], suffix: str = "one") -> str:
    with factory() as session, session.begin():
        job = Job(
            canonical_url=f"https://jobs.example.test/{suffix}",
            company_name="Example Systems",
            title="Backend Engineer",
            description="Build Python services.",
            location="Remote, India",
            work_mode="Remote",
            employment_type="Full-time",
            last_verified_at=datetime.now(UTC),
            status="open",
        )
        session.add(job)
        session.flush()
        return job.id


def test_prepare_snapshots_candidate_job_and_readiness(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    job_id = _job(factory)
    response = client.post(
        f"/api/v1/candidates/{candidate_id}/applications",
        json={"job_id": job_id, "custom_fields": {"notice_period": "Immediate"}},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "prepared"
    assert payload["current_revision"] == 1
    revision = payload["latest_revision"]
    assert len(revision["content_hash"]) == 64
    assert revision["content_snapshot"]["candidate"]["display_name"] == "Synthetic Candidate"
    assert revision["content_snapshot"]["job"]["title"] == "Backend Engineer"
    assert revision["content_snapshot"]["readiness"]["status"] == "needs_attention"
    assert "resume" in revision["content_snapshot"]["readiness"]["missing_fields"]


def test_revision_is_immutable_and_hash_changes(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    job_id = _job(factory)
    created = client.post(
        f"/api/v1/candidates/{candidate_id}/applications", json={"job_id": job_id}
    )
    application_id = created.json()["id"]
    original = created.json()["latest_revision"]
    updated = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}",
        json={"custom_fields": {"cover_note": "Reviewed manually"}},
    )
    assert updated.status_code == 200
    assert updated.json()["current_revision"] == 2
    assert updated.json()["latest_revision"]["content_hash"] != original["content_hash"]
    with factory() as session:
        revisions = list(
            session.scalars(
                select(ApplicationRevision)
                .where(ApplicationRevision.application_id == application_id)
                .order_by(ApplicationRevision.revision)
            )
        )
        events = list(
            session.scalars(
                select(ApplicationEvent).where(ApplicationEvent.application_id == application_id)
            )
        )
    assert [revision.revision for revision in revisions] == [1, 2]
    assert revisions[0].content_snapshot["custom_fields"] == {}
    assert revisions[1].content_snapshot["custom_fields"]["cover_note"] == "Reviewed manually"
    assert {event.event_type for event in events} == {"prepared", "content_revised"}


def test_duplicate_application_and_candidate_boundary(workspace) -> None:
    client, factory = workspace
    owner = _candidate(client, "Owner")
    other = _candidate(client, "Other")
    job_id = _job(factory)
    created = client.post(f"/api/v1/candidates/{owner}/applications", json={"job_id": job_id})
    application_id = created.json()["id"]
    duplicate = client.post(f"/api/v1/candidates/{owner}/applications", json={"job_id": job_id})
    assert duplicate.status_code == 409
    foreign_read = client.get(
        f"/api/v1/candidates/{other}/applications/{application_id}"
    )
    assert foreign_read.status_code == 404
    assert client.get(f"/api/v1/candidates/{other}/applications").json()["total"] == 0


def test_invalid_job_and_missing_candidate(workspace) -> None:
    client, _factory = workspace
    candidate_id = _candidate(client)
    assert client.post(
        f"/api/v1/candidates/{candidate_id}/applications", json={"job_id": "missing"}
    ).status_code == 404
    assert client.get("/api/v1/candidates/missing/applications").status_code == 404


def test_inactive_or_foreign_answer_is_rejected(workspace) -> None:
    client, _factory = workspace
    owner = _candidate(client, "Owner")
    other = _candidate(client, "Other")
    answer = client.post(
        f"/api/v1/candidates/{other}/answers",
        json={"question": "Why this role?", "answer_text": "Synthetic answer"},
    )
    assert answer.status_code == 201
    job_id = _job(_factory)
    response = client.post(
        f"/api/v1/candidates/{owner}/applications",
        json={"job_id": job_id, "answer_ids": [answer.json()["id"]]},
    )
    assert response.status_code == 422


def _resume(
    factory: sessionmaker[Session],
    candidate_id: str,
    *,
    suffix: str,
    parse_status: str = "reviewed",
) -> str:
    with factory() as session, session.begin():
        resume = Resume(
            candidate_id=candidate_id,
            storage_key=f"resumes/{suffix}.pdf",
            original_filename="candidate-resume.pdf",
            media_type="application/pdf",
            file_size_bytes=100,
            checksum_sha256=(suffix * 64)[:64],
            parse_status=parse_status,
            parsed_content={"reviewed_fields": {}},
        )
        session.add(resume)
        session.flush()
        return resume.id


def test_resume_must_be_reviewed_before_application_is_ready(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    job_id = _job(factory)
    resume_id = _resume(factory, candidate_id, suffix="a", parse_status="parsed")

    created = client.post(
        f"/api/v1/candidates/{candidate_id}/applications",
        json={"job_id": job_id, "resume_id": resume_id},
    )
    assert created.status_code == 201
    readiness = created.json()["latest_revision"]["content_snapshot"]["readiness"]
    assert readiness["status"] == "needs_attention"
    assert "resume.review" in readiness["missing_fields"]

    reviewed = client.patch(
        f"/api/v1/resumes/{resume_id}/parse/review",
        json={"display_name": "Reviewed Candidate"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["parse_status"] == "reviewed"

    revised = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{created.json()['id']}",
        json={"custom_fields": {"notice_period": "Immediate"}},
    )
    assert revised.status_code == 200
    updated_readiness = revised.json()["latest_revision"]["content_snapshot"]["readiness"]
    assert updated_readiness["status"] == "ready_for_review"
    assert updated_readiness["missing_fields"] == []


def test_revising_resume_recalculates_readiness(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    job_id = _job(factory)
    resume_id = _resume(factory, candidate_id, suffix="b")

    created = client.post(
        f"/api/v1/candidates/{candidate_id}/applications",
        json={"job_id": job_id, "resume_id": resume_id},
    )
    assert created.status_code == 201
    assert (
        created.json()["latest_revision"]["content_snapshot"]["readiness"]["status"]
        == "ready_for_review"
    )

    revised = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{created.json()['id']}",
        json={"resume_id": None},
    )
    assert revised.status_code == 200
    readiness = revised.json()["latest_revision"]["content_snapshot"]["readiness"]
    assert readiness["status"] == "needs_attention"
    assert "resume" in readiness["missing_fields"]


def test_application_copies_immutable_answer_revision(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    job_id = _job(factory)
    answer = client.post(
        f"/api/v1/candidates/{candidate_id}/answers",
        json={
            "question": "Why this role?",
            "answer_text": "Original reviewed answer",
            "category": "motivation",
            "tags": ["backend"],
        },
    )
    assert answer.status_code == 201
    answer_id = answer.json()["id"]

    created = client.post(
        f"/api/v1/candidates/{candidate_id}/applications",
        json={"job_id": job_id, "answer_ids": [answer_id]},
    )
    assert created.status_code == 201
    original_snapshot = created.json()["latest_revision"]["content_snapshot"]["answers"][0]
    assert original_snapshot["answer"] == "Original reviewed answer"
    assert len(original_snapshot["content_hash"]) == 64

    changed = client.patch(
        f"/api/v1/candidates/{candidate_id}/answers/{answer_id}",
        json={"answer_text": "Updated answer after application preparation"},
    )
    assert changed.status_code == 200
    fetched = client.get(
        f"/api/v1/candidates/{candidate_id}/applications/{created.json()['id']}"
    )
    preserved = fetched.json()["latest_revision"]["content_snapshot"]["answers"][0]
    assert preserved["answer"] == "Original reviewed answer"
    assert preserved["revision"] == 1


def test_foreign_resume_and_unbounded_custom_fields_are_rejected(workspace) -> None:
    client, factory = workspace
    owner = _candidate(client, "Owner")
    other = _candidate(client, "Other")
    job_id = _job(factory)
    foreign_resume = _resume(factory, other, suffix="c")

    foreign = client.post(
        f"/api/v1/candidates/{owner}/applications",
        json={"job_id": job_id, "resume_id": foreign_resume},
    )
    assert foreign.status_code == 422

    oversized = client.post(
        f"/api/v1/candidates/{owner}/applications",
        json={"job_id": job_id, "custom_fields": {"cover_letter": "x" * 4001}},
    )
    assert oversized.status_code == 422

    blank_key = client.post(
        f"/api/v1/candidates/{owner}/applications",
        json={"job_id": job_id, "custom_fields": {"   ": "value"}},
    )
    assert blank_key.status_code == 422


def test_application_patch_rejects_null_answer_and_custom_fields(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    job_id = _job(factory)
    created = client.post(
        f"/api/v1/candidates/{candidate_id}/applications", json={"job_id": job_id}
    )
    application_id = created.json()["id"]
    base = f"/api/v1/candidates/{candidate_id}/applications/{application_id}"

    assert client.patch(base, json={"answer_ids": None}).status_code == 422
    assert client.patch(base, json={"custom_fields": None}).status_code == 422
