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

            command.downgrade(config, "0004_unique_pending_batch_item")
            assert "discovery_schedules" not in set(inspect(connection).get_table_names())

            command.upgrade(config, "head")
            assert "discovery_schedules" in set(inspect(connection).get_table_names())
    finally:
        config.attributes.clear()
        engine.dispose()
