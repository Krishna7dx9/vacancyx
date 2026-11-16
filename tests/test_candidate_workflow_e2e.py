"""End-to-end API workflow from source ingestion through verified application tracking."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.db.session import get_session
from vacancyx.main import create_app
from vacancyx.models import ApplicationEvent, Job, JobObservation, Resume
from vacancyx.services.discovery import JobDiscoveryService
from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import SourceCapabilities, SourceListing, SourcePage
from vacancyx.sources.registry import SourceRegistry


class SyntheticPublicSource:
    """Deterministic source adapter; no network or employer portal is contacted."""

    source_key = "synthetic-greenhouse"
    capabilities = SourceCapabilities(pagination=False, published_at=True)

    async def fetch_page(self, *, cursor: str | None, page_size: int) -> SourcePage:
        assert cursor is None
        assert page_size >= 1
        return SourcePage(
            items=(
                SourceListing(
                    external_id="job-1001",
                    title="Backend Engineer",
                    company_name="Example Systems",
                    source_url="https://jobs.example.test/backend-engineer",
                    description="Build Python and SQL APIs using FastAPI.",
                    location="Remote, India",
                    work_mode="Remote",
                    employment_type="Full-time",
                    published_at=datetime(2026, 11, 1, tzinfo=UTC),
                ),
            )
        )


def _workspace() -> tuple[TestClient, sessionmaker[Session], Engine, FastAPI]:
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
    return TestClient(app), factory, engine, app


def test_complete_candidate_to_verified_application_workflow() -> None:
    client, factory, engine, app = _workspace()
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

        # 2. Ingest a normalized public-source listing through the real discovery service.
        source = SyntheticPublicSource()
        registry = SourceRegistry()
        registry.register(
            source,
            SourceConfig(
                source_key=source.source_key,
                allowed_hosts=("jobs.example.test",),
                requests_per_minute=120,
                timeout_seconds=1,
                page_size=10,
                max_pages_per_run=1,
            ),
        )
        with factory() as session:
            discovery = asyncio.run(
                JobDiscoveryService(session, registry).discover_source(source.source_key)
            )
            assert discovery.status == "completed"
            assert discovery.pages_fetched == 1
            assert discovery.jobs_created == 1
            assert discovery.observations_created == 1
            job = session.scalar(
                select(Job).where(
                    Job.canonical_url == "https://jobs.example.test/backend-engineer"
                )
            )
            assert job is not None
            job_id = job.id
            observation = session.scalar(
                select(JobObservation).where(JobObservation.job_id == job_id)
            )
            assert observation is not None
            assert observation.source_key == source.source_key
            assert observation.external_id == "job-1001"

        # 3. Create explicit search criteria and evaluate the discovered job.
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
        assert observation.source_key == source.source_key
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
