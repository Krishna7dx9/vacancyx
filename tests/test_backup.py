from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from vacancyx.db.backup import backup_sqlite_database
from vacancyx.db.base import Base
from vacancyx.db.session import build_engine
from vacancyx.models import CandidateProfile


def test_backup_restores_committed_candidate_data_atomically(tmp_path) -> None:
    source_path = tmp_path / "runtime" / "vacancyx.sqlite3"
    source_engine = build_engine(f"sqlite:///{source_path}")
    Base.metadata.create_all(source_engine)
    with Session(source_engine) as session, session.begin():
        session.add(
            CandidateProfile(
                display_name="Synthetic Backup Candidate",
                skills=["Python", "SQL"],
            )
        )

    destination = tmp_path / "backups" / "daily.sqlite3"
    result = backup_sqlite_database(source_engine, destination)
    assert result == destination.resolve()
    assert result.is_file()

    restored_engine = build_engine(f"sqlite:///{result}")
    try:
        with Session(restored_engine) as session:
            restored = session.scalar(select(CandidateProfile))
            assert restored is not None
            assert restored.display_name == "Synthetic Backup Candidate"
            assert restored.skills == ["Python", "SQL"]
    finally:
        restored_engine.dispose()
        source_engine.dispose()


def test_backup_rejects_in_memory_database(tmp_path) -> None:
    engine = create_engine("sqlite://")
    try:
        with pytest.raises(ValueError, match="file-backed"):
            backup_sqlite_database(engine, tmp_path / "backup.sqlite3")
    finally:
        engine.dispose()


def test_backup_rejects_source_as_destination(tmp_path) -> None:
    source_path = tmp_path / "source.sqlite3"
    engine = build_engine(f"sqlite:///{source_path}")
    try:
        with pytest.raises(ValueError, match="differ"):
            backup_sqlite_database(engine, source_path)
    finally:
        engine.dispose()


def test_backup_rejects_non_sqlite_engine(tmp_path) -> None:
    engine = create_engine("sqlite://")
    try:
        engine.dialect.name = "postgresql"
        with pytest.raises(ValueError, match="only for SQLite"):
            backup_sqlite_database(engine, tmp_path / "backup.sqlite3")
    finally:
        engine.dispose()
