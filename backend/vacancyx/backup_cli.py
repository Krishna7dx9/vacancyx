"""Command-line backup and verification tools for local SQLite data."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Sequence

from vacancyx.db.backup import backup_sqlite_database
from vacancyx.db.session import get_engine


def verify_sqlite_backup(path: str | Path) -> dict[str, object]:
    """Verify integrity, foreign keys, and schema readability without modifying a backup."""
    backup_path = Path(path).expanduser().resolve()
    if not backup_path.is_file():
        raise FileNotFoundError(f"Backup file does not exist: {backup_path}")

    connection = sqlite3.connect(
        f"{backup_path.as_uri()}?mode=ro",
        uri=True,
    )
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise ValueError(f"SQLite integrity check failed: {integrity!r}")
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise ValueError(
                f"SQLite backup contains foreign-key violations: {foreign_key_errors[:5]!r}"
            )
        version_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone()
        migration_version: str | None = None
        if version_table is not None:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            migration_version = str(row[0]) if row else None
        table_names = sorted(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        )
    finally:
        connection.close()
    if not table_names:
        raise ValueError("SQLite backup contains no application tables.")
    return {
        "path": str(backup_path),
        "integrity": "ok",
        "foreign_key_violations": 0,
        "migration_version": migration_version,
        "table_count": len(table_names),
        "tables": table_names,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Create or verify a local SQLite backup."""
    parser = argparse.ArgumentParser(
        prog="vacancyx-backup",
        description="Create or verify a private local SQLite backup.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create_parser = commands.add_parser("create", help="create a consistent online backup")
    create_parser.add_argument(
        "--destination",
        required=True,
        type=Path,
        help="backup file path (store outside the repository)",
    )
    verify_parser = commands.add_parser("verify", help="verify a backup without modifying it")
    verify_parser.add_argument("backup_path", type=Path)
    args = parser.parse_args(argv)

    if args.command == "create":
        result = backup_sqlite_database(get_engine(), args.destination)
        output: dict[str, object] = {
            "operation": "backup_created",
            "path": str(result),
            "note": "Backup contains private candidate data; protect it and test restoration.",
        }
    else:
        output = {"operation": "backup_verified", **verify_sqlite_backup(args.backup_path)}
        output["note"] = (
            "Integrity and schema readability passed. This is not a substitute for "
            "a full restore drill."
        )
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
