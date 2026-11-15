"""Seed a clearly synthetic, repeatable local workspace demonstration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from vacancyx.models import CandidateProfile, Job, JobObservation, SearchProfile


@dataclass(frozen=True)
class DemoSeedResult:
    """Identifiers for the synthetic candidate, job, and matching profile."""

    candidate_id: str
    job_id: str
    search_profile_id: str
    created_candidate: bool
    created_job: bool
    created_search_profile: bool


def seed_demo_workspace(session: Session) -> DemoSeedResult:
    """Create the same synthetic records on each run without overwriting user data."""
    now = datetime.now(UTC)
    candidate_email = "demo@vacancyx.invalid"
    candidate = session.scalar(
        select(CandidateProfile).where(CandidateProfile.email == candidate_email)
    )
    created_candidate = candidate is None
    if candidate is None:
        candidate = CandidateProfile(
            display_name="VacancyX Demo Candidate",
            email=candidate_email,
            phone="0000000000",
            location="India",
            skills=["Python", "SQL", "FastAPI", "REST APIs"],
            education=[{"degree": "B.Tech Computer Science", "status": "In progress"}],
            experience=[{"title": "Software Engineering Intern", "type": "Synthetic demo"}],
            links={"vacancyx_demo": "true"},
        )
        session.add(candidate)
        session.flush()
    elif candidate.links.get("vacancyx_demo") != "true":
        raise ValueError(
            "The reserved demo email already belongs to a non-demo candidate; "
            "no existing candidate data was changed."
        )

    job_url = "https://jobs.example.test/demo-backend-engineer"
    job = session.scalar(select(Job).where(Job.canonical_url == job_url))
    created_job = job is None
    if job is None:
        job = Job(
            canonical_url=job_url,
            company_name="Example Systems (Synthetic)",
            title="Backend Engineer — Demo",
            description=(
                "Synthetic demonstration role. Build Python and FastAPI services, "
                "design REST APIs, and work with SQL-backed systems. This is not a real vacancy."
            ),
            location="Remote, India",
            work_mode="Remote",
            employment_type="Full-time",
            salary_min=1_200_000,
            salary_max=1_800_000,
            salary_currency="INR",
            first_published_at=now,
            last_verified_at=now,
            status="open",
        )
        session.add(job)
        session.flush()

    observation = session.scalar(
        select(JobObservation).where(
            JobObservation.source_key == "synthetic-demo",
            JobObservation.external_id == "demo-backend-engineer-v1",
        )
    )
    if observation is None:
        session.add(
            JobObservation(
                job_id=job.id,
                source_key="synthetic-demo",
                external_id="demo-backend-engineer-v1",
                source_url=job_url,
                first_seen_at=now,
                last_seen_at=now,
                evidence={"synthetic": True, "note": "Local VacancyX demo fixture; not a real job."},
            )
        )

    profile_name = "Demo backend roles in India"
    profile = session.scalar(
        select(SearchProfile).where(
            SearchProfile.candidate_id == candidate.id,
            SearchProfile.name == profile_name,
        )
    )
    created_search_profile = profile is None
    if profile is None:
        criteria: dict[str, Any] = {
            "target_titles": ["Backend Engineer"],
            "excluded_keywords": [],
            "required_skills": ["Python", "SQL", "FastAPI"],
            "allowed_locations": ["India"],
            "work_modes": ["Remote"],
            "employment_types": ["Full-time"],
            "minimum_salary": 1_000_000,
            "salary_currency": "INR",
        }
        profile = SearchProfile(
            candidate_id=candidate.id,
            name=profile_name,
            criteria=criteria,
            is_enabled=True,
        )
        session.add(profile)
        session.flush()

    return DemoSeedResult(
        candidate_id=candidate.id,
        job_id=job.id,
        search_profile_id=profile.id,
        created_candidate=created_candidate,
        created_job=created_job,
        created_search_profile=created_search_profile,
    )


def run_demo_seed(session_factory: Any) -> DemoSeedResult:
    """Run the seed in one transaction using the application's session factory."""
    with session_factory() as session, session.begin():
        return seed_demo_workspace(session)
