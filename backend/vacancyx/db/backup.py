"""Safe, atomic backups for file-backed SQLite databases."""

import os
import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy.engine import Engine


def backup_sqlite_database(engine: Engine, destination: str | Path) -> Path:
    """Create a consistent SQLite backup and atomically publish it at destination.

    The SQLite online backup API includes committed WAL content and avoids copying a
    potentially inconsistent database file while the application is running. The
    temporary backup is created beside the destination so os.replace is atomic.
    """
    if engine.dialect.name != "sqlite":
        raise ValueError("Database backups are currently supported only for SQLite.")
    database = engine.url.database
    if database is None or database == ":memory:":
        raise ValueError("A file-backed SQLite database is required for backups.")

    source_path = Path(database).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise ValueError("The backup destination must differ from the source database.")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination_path.parent,
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)

    try:
        with engine.connect() as source_connection:
            source_dbapi = source_connection.connection.driver_connection
            if not isinstance(source_dbapi, sqlite3.Connection):
                raise RuntimeError("The configured SQLite driver does not expose a sqlite3 connection.")
            backup_connection = sqlite3.connect(temporary_path)
            try:
                source_dbapi.backup(backup_connection)
                integrity = backup_connection.execute("PRAGMA integrity_check").fetchone()
                if integrity != ("ok",):
                    raise RuntimeError(f"SQLite backup integrity check failed: {integrity!r}")
            finally:
                backup_connection.close()

        os.replace(temporary_path, destination_path)
        return destination_path
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
