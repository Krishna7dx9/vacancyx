"""Persistence behavior and schema migration tests."""

from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from vacancyx.db.base import Base
from vacancyx.models import Application, CandidateProfile, Job, Resume
from vacancyx.repositories import CandidateRepository, TaskRepository


@pytest.fixture
def engine():
    database_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(database_engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(database_engine)
    yield database_engine
    database_engine.dispose()


def test_candidate_repository_persists_configurable_profile(engine) -> None:
    with Session(engine) as session, session.begin():
        candidate = CandidateRepository(session).add(
            CandidateProfile(
                display_name="Synthetic Candidate",
                skills=["Python", "SQL"],
                education=[{"degree": "B.Tech"}],
            )
        )
        candidate_id = candidate.id

    with Session(engine) as session:
        stored = CandidateRepository(session).get(candidate_id)
        assert stored is not None
        assert stored.skills == ["Python", "SQL"]
        assert stored.education[0]["degree"] == "B.Tech"


def test_candidate_transaction_rolls_back(engine) -> None:
    with pytest.raises(RuntimeError), Session(engine) as session:
        with session.begin():
            CandidateRepository(session).add(CandidateProfile(display_name="Rollback candidate"))
            raise RuntimeError("force rollback")

    with Session(engine) as session:
        assert session.scalar(select(CandidateProfile)) is None


def test_resume_requires_positive_file_size(engine) -> None:
    with Session(engine) as session, session.begin():
        candidate = CandidateProfile(display_name="Synthetic Candidate")
        session.add(candidate)
        session.flush()
        session.add(
            Resume(
                candidate_id=candidate.id,
                storage_key="resumes/test.pdf",
                original_filename="resume.pdf",
                media_type="application/pdf",
                file_size_bytes=0,
                checksum_sha256="a" * 64,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_application_candidate_job_pair_is_unique(engine) -> None:
    with Session(engine) as session, session.begin():
        candidate = CandidateProfile(display_name="Synthetic Candidate")
        job = Job(company_name="Example Co", title="Backend Engineer")
        session.add_all([candidate, job])
        session.flush()
        session.add_all(
            [
                Application(candidate_id=candidate.id, job_id=job.id),
                Application(candidate_id=candidate.id, job_id=job.id),
            ]
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_task_enqueue_is_idempotent_and_claims_once(engine) -> None:
    with Session(engine) as session, session.begin():
        repository = TaskRepository(session)
        first = repository.enqueue(
            task_type="discover",
            payload={"source": "sample"},
            idempotency_key="source-run:sample:synthetic",
        )
        second = repository.enqueue(
            task_type="discover",
            payload={"source": "different-payload-is-ignored"},
            idempotency_key="source-run:sample:synthetic",
        )
        assert first.id == second.id
        task_id = first.id

    with Session(engine) as session, session.begin():
        claimed = TaskRepository(session).claim_next(worker_id="worker-a", lease_seconds=30)
        assert claimed is not None
        assert claimed.id == task_id
        assert claimed.state == "running"
        assert claimed.lease_owner == "worker-a"
        assert claimed.lease_token is not None
        assert claimed.attempts == 1

    with Session(engine) as session, session.begin():
        assert TaskRepository(session).claim_next(worker_id="worker-b") is None


def test_task_not_claimed_before_available_at(engine) -> None:
    with Session(engine) as session, session.begin():
        TaskRepository(session).enqueue(
            task_type="later",
            payload={},
            idempotency_key="later-task",
            available_at=datetime(2099, 1, 1, tzinfo=UTC),
        )

    with Session(engine) as session, session.begin():
        assert TaskRepository(session).claim_next(worker_id="worker-a") is None


def test_alembic_upgrade_creates_expected_schema(tmp_path) -> None:
    database_path = tmp_path / "migration-test.sqlite3"
    config = Config("alembic.ini")
    migrated_engine = create_engine(f"sqlite:///{database_path}")
    try:
        with migrated_engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        inspector = inspect(migrated_engine)
        tables = set(inspector.get_table_names())
        assert {
            "candidate_profiles",
            "resumes",
            "search_profiles",
            "jobs",
            "job_observations",
            "applications",
            "application_revisions",
            "application_approvals",
            "application_events",
            "automation_tasks",
            "alembic_version",
        }.issubset(tables)
        assert {fk["referred_table"] for fk in inspector.get_foreign_keys("applications")} == {
            "candidate_profiles",
            "jobs",
            "resumes",
        }
    finally:
        migrated_engine.dispose()
