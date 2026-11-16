"""Migration-chain integration tests using an isolated SQLite database."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_config() -> Config:
    repository_root = Path(__file__).resolve().parents[1]
    return Config(str(repository_root / "alembic.ini"))


def test_full_migration_chain_upgrades_and_downgrades_discovery_schedules(tmp_path) -> None:
    database_path = tmp_path / "migration-check.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    config = _alembic_config()
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            assert "candidate_profiles" in tables
            assert "applications" in tables
            assert "automation_tasks" in tables
            assert "discovery_schedules" in tables
            assert "public_job_sources" in tables
            schedule_columns = {
                column["name"] for column in inspector.get_columns("discovery_schedules")
            }
            assert {
                "id",
                "name",
                "source_keys",
                "interval_seconds",
                "is_enabled",
                "next_run_at",
                "last_run_at",
                "run_number",
                "last_error_code",
            } <= schedule_columns
            assert "ix_discovery_schedules_due" in {
                index["name"] for index in inspector.get_indexes("discovery_schedules")
            }

            source_columns = {
                column["name"] for column in inspector.get_columns("public_job_sources")
            }
            assert {"id", "source_key", "provider", "external_key", "company_name", "is_enabled"} <= source_columns

            command.downgrade(config, "0004_unique_pending_batch_item")
            downgraded_tables = set(inspect(connection).get_table_names())
            assert "discovery_schedules" not in downgraded_tables
            assert "public_job_sources" not in downgraded_tables

            command.upgrade(config, "head")
            upgraded_tables = set(inspect(connection).get_table_names())
            assert "discovery_schedules" in upgraded_tables
            assert "public_job_sources" in upgraded_tables
    finally:
        config.attributes.clear()
        engine.dispose()
