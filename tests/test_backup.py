
import sqlite3
from unittest.mock import Mock

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
    engine = Mock()
    engine.dialect.name = "postgresql"
    with pytest.raises(ValueError, match="only for SQLite"):
        backup_sqlite_database(engine, tmp_path / "backup.sqlite3")



def test_verify_backup_reports_integrity_schema_and_migration_version(tmp_path) -> None:
    from sqlalchemy import text

    from vacancyx.db.backup import backup_sqlite_database
    from vacancyx.backup_cli import verify_sqlite_backup

    source = build_engine(f"sqlite:///{tmp_path / 'source.sqlite3'}")
    try:
        Base.metadata.create_all(source)
        with source.begin() as connection:
            connection.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
            )
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('0006_public_job_sources')")
            )
        backup = backup_sqlite_database(source, tmp_path / "backup.sqlite3")
    finally:
        source.dispose()

    result = verify_sqlite_backup(backup)
    assert result["integrity"] == "ok"
    assert result["foreign_key_violations"] == 0
    assert result["migration_version"] == "0006_public_job_sources"
    assert result["table_count"] > 1
    assert "candidate_profiles" in result["tables"]


def test_verify_backup_rejects_missing_and_invalid_files(tmp_path) -> None:
    from vacancyx.db.backup_cli import verify_sqlite_backup

    with pytest.raises(FileNotFoundError, match="does not exist"):
        verify_sqlite_backup(tmp_path / "missing.sqlite3")

    invalid = tmp_path / "invalid.sqlite3"
    invalid.write_text("not a sqlite database", encoding="utf-8")
    with pytest.raises(sqlite3.DatabaseError):
        verify_sqlite_backup(invalid)



def test_backup_cli_creates_and_verifies_backup(tmp_path, monkeypatch, capsys) -> None:
    from vacancyx import backup_cli

    source = build_engine(f"sqlite:///{tmp_path / 'runtime.sqlite3'}")
    Base.metadata.create_all(source)
    monkeypatch.setattr(backup_cli, "get_engine", lambda: source)
    backup = tmp_path / "backups" / "cli.sqlite3"

    assert backup_cli.main(["create", "--destination", str(backup)]) == 0
    created = capsys.readouterr().out
    assert '"operation": "backup_created"' in created
    assert backup.is_file()

    assert backup_cli.main(["verify", str(backup)]) == 0
    verified = capsys.readouterr().out
    assert '"operation": "backup_verified"' in verified
    assert '"integrity": "ok"' in verified
    source.dispose()
