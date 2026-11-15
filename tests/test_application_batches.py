"""Integration tests for revision-bound application batch review."""

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
    Application,
    ApplicationApproval,
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


def _candidate(client: TestClient, name: str = "Batch Candidate") -> str:
    response = client.post(
        "/api/v1/candidates",
        json={
            "display_name": name,
            "email": "candidate@example.test",
            "phone": "0000000000",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _job(factory: sessionmaker[Session], suffix: str) -> str:
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


def _reviewed_resume(factory: sessionmaker[Session], candidate_id: str) -> str:
    with factory() as session, session.begin():
        resume = Resume(
            candidate_id=candidate_id,
            storage_key="resumes/reviewed.pdf",
            original_filename="candidate-resume.pdf",
            media_type="application/pdf",
            file_size_bytes=100,
            checksum_sha256="a" * 64,
            parse_status="reviewed",
            parsed_content={"reviewed_fields": {}},
        )
        session.add(resume)
        session.flush()
        return resume.id


def _application(
    client: TestClient,
    factory: sessionmaker[Session],
    candidate_id: str,
    *,
    suffix: str,
    with_resume: bool = True,
) -> str:
    job_id = _job(factory, suffix)
    payload: dict[str, object] = {"job_id": job_id}
    if with_resume:
        payload["resume_id"] = _reviewed_resume(factory, candidate_id)
    response = client.post(
        f"/api/v1/candidates/{candidate_id}/applications",
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_batch(
    client: TestClient, candidate_id: str, application_ids: list[str]
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches",
        json={"name": "Review batch", "application_ids": application_ids},
    )
    assert response.status_code == 201
    return response.json()


def test_batch_captures_revision_and_approval_is_audited(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    application_id = _application(
        client, factory, candidate_id, suffix="approve"
    )
    batch = _create_batch(client, candidate_id, [application_id])
    item = batch["items"][0]
    assert item["revision"] == 1
    assert len(item["content_hash"]) == 64
    assert batch["status"] == "reviewing"

    decision = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches/{batch['id']}/decisions",
        json={
            "decisions": [
                {"application_id": application_id, "decision": "approved"}
            ]
        },
    )
    assert decision.status_code == 200
    assert decision.json()["results"] == [
        {"application_id": application_id, "result": "approved"}
    ]
    assert decision.json()["batch"]["status"] == "completed"
    assert decision.json()["batch"]["items"][0]["decision"] == "approved"

    application = client.get(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}"
    )
    assert application.json()["status"] == "approved"
    with factory() as session:
        approval = session.scalar(
            select(ApplicationApproval).where(
                ApplicationApproval.application_id == application_id
            )
        )
        events = list(
            session.scalars(
                select(ApplicationEvent).where(
                    ApplicationEvent.application_id == application_id
                )
            )
        )
    assert approval is not None
    assert approval.revision == 1
    assert approval.decision == "approved"
    assert {event.event_type for event in events} >= {"batch_added", "approved"}


def test_revision_change_makes_batch_item_stale_and_cannot_be_approved(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    application_id = _application(
        client, factory, candidate_id, suffix="stale"
    )
    batch = _create_batch(client, candidate_id, [application_id])

    revised = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}",
        json={"custom_fields": {"cover_note": "Updated after batch creation"}},
    )
    assert revised.status_code == 200
    assert revised.json()["current_revision"] == 2

    decision = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches/{batch['id']}/decisions",
        json={
            "decisions": [
                {"application_id": application_id, "decision": "approved"}
            ]
        },
    )
    assert decision.status_code == 200
    assert decision.json()["results"][0]["result"] == "stale"
    item = decision.json()["batch"]["items"][0]
    assert item["decision"] == "stale"
    assert item["is_stale"] is True
    assert item["revision"] == 1
    assert item["current_revision"] == 2

    application = client.get(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}"
    )
    assert application.json()["status"] == "prepared"
    with factory() as session:
        approvals = list(
            session.scalars(
                select(ApplicationApproval).where(
                    ApplicationApproval.application_id == application_id
                )
            )
        )
    assert approvals == []


def test_approval_requires_ready_snapshot_but_rejection_is_allowed(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    application_id = _application(
        client, factory, candidate_id, suffix="needs-attention", with_resume=False
    )
    batch = _create_batch(client, candidate_id, [application_id])

    blocked = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches/{batch['id']}/decisions",
        json={
            "decisions": [
                {"application_id": application_id, "decision": "approved"}
            ]
        },
    )
    assert blocked.status_code == 200
    assert blocked.json()["results"][0]["result"] == "needs_attention"
    assert blocked.json()["batch"]["items"][0]["decision"] == "pending"
    assert blocked.json()["batch"]["status"] == "reviewing"

    rejected = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches/{batch['id']}/decisions",
        json={
            "decisions": [
                {"application_id": application_id, "decision": "rejected"}
            ]
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["results"][0]["result"] == "rejected"
    assert rejected.json()["batch"]["status"] == "completed"
    application = client.get(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}"
    )
    assert application.json()["status"] == "rejected"


def test_approval_is_historic_and_invalidated_when_content_is_revised(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    application_id = _application(
        client, factory, candidate_id, suffix="invalidate"
    )
    batch = _create_batch(client, candidate_id, [application_id])
    decision = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches/{batch['id']}/decisions",
        json={
            "decisions": [
                {"application_id": application_id, "decision": "approved"}
            ]
        },
    )
    assert decision.status_code == 200

    revised = client.patch(
        f"/api/v1/candidates/{candidate_id}/applications/{application_id}",
        json={"custom_fields": {"cover_note": "New content after approval"}},
    )
    assert revised.status_code == 200
    assert revised.json()["status"] == "prepared"
    assert revised.json()["current_revision"] == 2

    with factory() as session:
        approvals = list(
            session.scalars(
                select(ApplicationApproval).where(
                    ApplicationApproval.application_id == application_id
                )
            )
        )
        event_types = set(
            session.scalars(
                select(ApplicationEvent.event_type).where(
                    ApplicationEvent.application_id == application_id
                )
            )
        )
    assert len(approvals) == 1
    assert approvals[0].revision == 1
    assert "approval_invalidated" in event_types


def test_batch_rejects_foreign_and_duplicate_applications(workspace) -> None:
    client, factory = workspace
    owner = _candidate(client, "Owner")
    other = _candidate(client, "Other")
    foreign_application = _application(
        client, factory, other, suffix="foreign"
    )

    foreign = client.post(
        f"/api/v1/candidates/{owner}/application-batches",
        json={
            "name": "Foreign",
            "application_ids": [foreign_application],
        },
    )
    assert foreign.status_code == 422

    duplicate = client.post(
        f"/api/v1/candidates/{owner}/application-batches",
        json={"name": "Duplicate", "application_ids": ["a", "a"]},
    )
    assert duplicate.status_code == 422


def test_batch_decision_cannot_be_replayed(workspace) -> None:
    client, factory = workspace
    candidate_id = _candidate(client)
    application_id = _application(
        client, factory, candidate_id, suffix="replay"
    )
    batch = _create_batch(client, candidate_id, [application_id])
    payload = {
        "decisions": [
            {"application_id": application_id, "decision": "approved"}
        ]
    }
    first = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches/{batch['id']}/decisions",
        json=payload,
    )
    assert first.status_code == 200
    replay = client.post(
        f"/api/v1/candidates/{candidate_id}/application-batches/{batch['id']}/decisions",
        json=payload,
    )
    assert replay.status_code == 409
