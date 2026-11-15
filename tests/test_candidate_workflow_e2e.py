"""End-to-end API workflow from candidate matching through verified application tracking."""

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app
from vacancyx.models import ApplicationEvent, Job, JobObservation, Resume


def _workspace() -> tuple[TestClient, sessionmaker[Session], object]:
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
    return TestClient(app), factory, (engine, app)


def test_complete_candidate_to_verified_application_workflow() -> None:
    client, factory, resources = _workspace()
    engine, app = resources
    try:
        # 1. Create a candidate-owned profile.
        candidate_response = client.post(
            "/api/v1/candidates",
            json={
                "display_name": "Synthetic Backend Candidate",
                "email": "candidate@example.test",
                "phone": "0000000000",
                "location": "India",
                "skills": ["Python", "SQL", "FastAPI"],
            },
        )
        assert candidate_response.status_code == 201
        candidate_id = candidate_response.json()["id"]

        # 2. Simulate one normalized public-source listing and its provenance.
        now = datetime.now(UTC)
        with factory() as session, session.begin():
            job = Job(
                canonical_url="https://jobs.example.test/backend-engineer",
                company_name="Example Systems",
                title="Backend Engineer",
                description="Build Python and SQL APIs using FastAPI.",
                location="Remote, India",
                work_mode="Remote",
                employment_type="Full-time",
                last_verified_at=now,
                status="open",
            )
            session.add(job)
            session.flush()
            session.add(
                JobObservation(
                    job_id=job.id,
                    source_key="synthetic-greenhouse",
                    external_id="job-1001",
                    source_url=job.canonical_url,
                    first_seen_at=now,
                    last_seen_at=now,
                    evidence={"fixture": "synthetic", "provider": "test"},
                )
            )
            job_id = job.id

        # 3. Create explicit search criteria and evaluate the normalized job.
        profile_response = client.post(
            f"/api/v1/candidates/{candidate_id}/search-profiles",
            json={
                "name": "Backend roles in India",
                "criteria": {
                    "target_titles": ["Backend Engineer"],
                    "excluded_keywords": [],
                    "required_skills": ["Python", "SQL"],
                    "allowed_locations": ["India"],
                    "work_modes": ["Remote"],
                    "employment_types": ["Full-time"],
                },
            },
        )
        assert profile_response.status_code == 201
        profile_id = profile_response.json()["id"]
        matches = client.post(
            f"/api/v1/candidates/{candidate_id}/search-profiles/{profile_id}/matches?limit=10"
        )
        assert matches.status_code == 200
        match_payload = matches.json()
        assert match_payload["evaluated_count"] == 1
        assert match_payload["items"][0]["job"]["id"] == job_id
        assert match_payload["items"][0]["match"]["status"] == "eligible"

        # 4. Add reviewed resume material and prepare an immutable application snapshot.
        with factory() as session, session.begin():
            resume = Resume(
                candidate_id=candidate_id,
                storage_key="resumes/synthetic-e2e.pdf",
                original_filename="synthetic-resume.pdf",
                media_type="application/pdf",
                file_size_bytes=128,
                checksum_sha256="e" * 64,
                parse_status="reviewed",
                parsed_content={
                    "reviewed_fields": {
                        "display_name": "Synthetic Backend Candidate",
                        "skills": ["Python", "SQL", "FastAPI"],
                    }
                },
            )
            session.add(resume)
            session.flush()
            resume_id = resume.id

        prepared = client.post(
            f"/api/v1/candidates/{candidate_id}/applications",
            json={
                "job_id": job_id,
                "resume_id": resume_id,
                "custom_fields": {"cover_note": "Synthetic demo only."},
            },
        )
        assert prepared.status_code == 201
        application = prepared.json()
        application_id = application["id"]
        assert application["status"] == "prepared"
        assert application["latest_revision"]["content_snapshot"]["readiness"]["status"] == (
            "ready_for_review"
        )
        original_hash = application["latest_revision"]["content_hash"]
        assert len(original_hash) == 64

        # 5. Create a revision-bound review batch and approve that exact snapshot.
        batch_response = client.post(
            f"/api/v1/candidates/{candidate_id}/application-batches",
            json={"name": "Synthetic E2E approval", "application_ids": [application_id]},
        )
        assert batch_response.status_code == 201
        batch = batch_response.json()
        assert batch["items"][0]["content_hash"] == original_hash

        approved = client.post(
            f"/api/v1/candidates/{candidate_id}/application-batches/{batch['id']}/decisions",
            json={
                "decisions": [
                    {"application_id": application_id, "decision": "approved"}
                ]
            },
        )
        assert approved.status_code == 200
        assert approved.json()["results"][0]["result"] == "approved"

        # 6. Model a candidate-controlled submission and require real confirmation evidence.
        application_path = (
            f"/api/v1/candidates/{candidate_id}/applications/{application_id}"
        )
        submitting = client.patch(
            f"{application_path}/status",
            json={"status": "submitting"},
        )
        assert submitting.status_code == 200
        missing_confirmation = client.patch(
            f"{application_path}/status",
            json={"status": "submitted"},
        )
        assert missing_confirmation.status_code == 409

        submitted = client.patch(
            f"{application_path}/status",
            json={
                "status": "submitted",
                "confirmation_reference": "SYNTHETIC-EMPLOYER-CONFIRMATION-1001",
            },
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "submitted"

        # 7. Track the next interview event and verify the append-only history.
        interview = client.post(
            f"{application_path}/events",
            json={
                "event_type": "interview_scheduled",
                "summary": "Synthetic first-round interview for integration test.",
            },
        )
        assert interview.status_code == 201
        timeline = client.get(f"{application_path}/events")
        assert timeline.status_code == 200
        event_types = [event["event_type"] for event in timeline.json()]
        assert "status_changed" in event_types
        assert "interview_scheduled" in event_types

        with factory() as session:
            audit_events = list(
                session.scalars(
                    select(ApplicationEvent).where(
                        ApplicationEvent.application_id == application_id
                    )
                )
            )
            observation = session.scalar(
                select(JobObservation).where(JobObservation.job_id == job_id)
            )
        assert observation is not None
        assert observation.source_key == "synthetic-greenhouse"
        assert {event.event_type for event in audit_events} >= {
            "prepared",
            "batch_added",
            "approved",
            "status_changed",
            "interview_scheduled",
        }
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()
