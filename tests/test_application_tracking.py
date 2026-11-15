"""Application lifecycle and timeline integration tests."""

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
from vacancyx.models import (
    ApplicationEvent,
    Job,
    Resume,
)


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


def _candidate(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/candidates",
        json={"display_name": name, "email": "candidate@example.test", "phone": "0000000000"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _application(client: TestClient, factory: sessionmaker[Session], candidate_id: str) -> str:
    with factory() as session, session.begin():
        job = Job(
            canonical_url="https://jobs.example.test/tracking",
            company_name="Example Systems",
            title="Backend Engineer",
            last_verified_at=datetime.now(UTC),
            status="open",
        )
        session.add(job)
        session.flush()
        resume = Resume(
            candidate_id=candidate_id,
            storage_key="resumes/tracking.pdf",
            original_filename="resume.pdf",
            media_type="application/pdf",
            file_size_bytes=100,
            checksum_sha256="b" * 64,
            parse_status="reviewed",
        )
        session.add(resume)
        session.flush()
        job_id, resume_id = job.id, resume.id
    created = client.post(
        f"/api/v1/candidates/{candidate_id}/applications",
        json={"job_id": job_id, "resume_id": resume_id},
    )
    assert created.status_code == 201
    return created.json()["id"]


def _approve(client: TestClient, candidate_id: str, application_id: str) -> None:
    batch = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches",
        json={"name": "Ready to submit", "application_ids": [application_id]},
    )
    assert batch.status_code == 201
    response = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches/{batch.json()['id']}/decisions",
        json={"decisions": [{"application_id": application_id, "decision": "approved"}]},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["result"] == "approved"


def test_submission_requires_current_revision_approval_and_confirmation(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client, "Owner")
    application_id = _application(client, factory, candidate_id)

    no_approval = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={"status": "submitting"},
    )
    assert no_approval.status_code == 409

    _approve(client, candidate_id, application_id)
    submitting = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={"status": "submitting"},
    )
    assert submitting.status_code == 200
    assert submitting.json()["status"] == "submitting"

    no_confirmation = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={"status": "submitted"},
    )
    assert no_confirmation.status_code == 409

    submitted = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={
            "status": "submitted",
            "confirmation_reference": "confirmation-123",
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    with factory() as session:
        event = session.scalar(
            select(ApplicationEvent).where(
                ApplicationEvent.application_id == application_id,
                ApplicationEvent.event_type == "status_changed",
            ).order_by(ApplicationEvent.occurred_at.desc())
        )
        assert event is not None
        assert event.metadata_json["confirmation_reference"] == "confirmation-123"


def test_uncertain_submission_can_be_resolved_only_with_evidence(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client, "Candidate")
    application_id = _application(client, factory, candidate_id)
    _approve(client, candidate_id, application_id)
    assert client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={"status": "submitting"},
    ).status_code == 200
    assert client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={"status": "uncertain"},
    ).status_code == 200
    resolved = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={"status": "submitted", "confirmation_reference": "portal-ref"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "submitted"


def test_timeline_is_candidate_scoped_append_only_and_ordered(workspace) -> None:
    client, factory = workspace
    owner = _candidate(client, "Owner")
    other = _candidate(client, "Other")
    application_id = _application(client, factory, owner)

    created = client.post(
        f"/api/v1/candidates/{owner}/applications/{application_id}/events",
        json={"event_type": "interview_scheduled", "summary": "Technical round next Tuesday"},
    )
    assert created.status_code == 201
    assert created.json()["metadata_json"]["summary"] == "Technical round next Tuesday"

    timeline = client.get(f"/api/v1/candidates/{owner}/applications/{application_id}/events")
    assert timeline.status_code == 200
    assert [event["event_type"] for event in timeline.json()] == [
        "prepared",
        "interview_scheduled",
    ]
    assert client.get(
        f"/api/v1/candidates/{other}/applications/{application_id}/events"
    ).status_code == 404

    invalid = client.post(
        f"/api/v1/candidates/{owner}/applications/{application_id}/events",
        json={"event_type": "arbitrary", "summary": "Should not be accepted"},
    )
    assert invalid.status_code == 422


def test_terminal_status_cannot_be_reopened_by_api(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client, "Candidate")
    application_id = _application(client, factory, candidate_id)
    withdrawn = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={"status": "withdrawn"},
    )
    assert withdrawn.status_code == 200
    reopened = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}/status",
        json={"status": "submitting"},
    )
    assert reopened.status_code == 409
