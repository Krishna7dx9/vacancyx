"""Tests for the idempotent synthetic VacancyX demo seed."""

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from vacancyx.db.base import Base
from vacancyx.models import CandidateProfile, Job, JobObservation, SearchProfile
from vacancyx.services.demo_seed import run_demo_seed


def _session_factory() -> tuple[sessionmaker[Session], Engine]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def test_demo_seed_is_idempotent_and_uses_only_synthetic_records() -> None:
    factory, engine = _session_factory()
    try:
        first = run_demo_seed(factory)
        second = run_demo_seed(factory)
        assert first.candidate_id == second.candidate_id
        assert first.job_id == second.job_id
        assert first.search_profile_id == second.search_profile_id
        assert first.created_candidate is True
        assert first.created_job is True
        assert first.created_search_profile is True
        assert second.created_candidate is False
        assert second.created_job is False
        assert second.created_search_profile is False

        with factory() as session:
            candidates = list(session.scalars(select(CandidateProfile)))
            jobs = list(session.scalars(select(Job)))
            observations = list(session.scalars(select(JobObservation)))
            profiles = list(session.scalars(select(SearchProfile)))
        assert len(candidates) == 1
        assert candidates[0].email == "demo@vacancyx.invalid"
        assert candidates[0].links["vacancyx_demo"] == "true"
        assert len(jobs) == 1
        assert jobs[0].canonical_url == "https://jobs.example.test/demo-backend-engineer"
        assert "not a real vacancy" in (jobs[0].description or "")
        assert len(observations) == 1
        assert observations[0].source_key == "synthetic-demo"
        assert len(profiles) == 1
        assert profiles[0].criteria["required_skills"] == ["Python", "SQL", "FastAPI"]
    finally:
        engine.dispose()


def test_demo_seed_does_not_overwrite_reserved_email_owned_by_non_demo() -> None:
    factory, engine = _session_factory()
    try:
        with factory() as session, session.begin():
            session.add(
                CandidateProfile(
                    display_name="User Candidate",
                    email="demo@vacancyx.invalid",
                    skills=["Do not overwrite"],
                    links={},
                )
            )
        with pytest.raises(ValueError, match="non-demo candidate"):
            run_demo_seed(factory)
        with factory() as session:
            candidate = session.scalar(
                select(CandidateProfile).where(
                    CandidateProfile.email == "demo@vacancyx.invalid"
                )
            )
            assert candidate is not None
            assert candidate.display_name == "User Candidate"
            assert candidate.skills == ["Do not overwrite"]
    finally:
        engine.dispose()
