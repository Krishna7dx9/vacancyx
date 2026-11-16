# Local persistence operations

## Database ownership
VacancyX uses SQLAlchemy 2.x with Alembic migrations. The default SQLite database is stored at `.vacancyx/vacancyx.db`; this directory is local runtime state and must never be committed. Override the location with `VACANCYX_DATABASE_URL`. Candidate data and resume contents are not environment configuration.

## First-time setup
1. Install the project and development dependencies: `python -m pip install -e ".[dev]"`.
2. Apply schema migrations: `alembic upgrade head`.
3. Start the API: `uvicorn vacancyx.main:app --app-dir backend --host 127.0.0.1 --port 8000`.
4. Check `/health/live` for process liveness and `/health/ready` for database connectivity.

Migrations are explicit and schema creation is never performed automatically at API startup. This prevents a running process from silently changing the user's database.

## Transactions and repositories
Application services own transaction boundaries. Repositories flush but never commit. Keep transactions short; never hold one open while making network or browser calls. SQLite foreign-key enforcement and a bounded busy timeout are enabled for each connection.

## Backups and recovery
Use the built-in SQLite online backup utility to create a consistent snapshot while the database is open:

```python
from pathlib import Path

from vacancyx.db.backup import backup_sqlite_database
from vacancyx.db.session import get_engine

backup_sqlite_database(get_engine(), Path.home() / "VacancyXBackups" / "latest.sqlite3")
```

The utility uses SQLite's backup API (so committed WAL content is included), checks the backup with `PRAGMA integrity_check`, writes to a temporary file beside the destination, and atomically replaces the destination only after validation. It rejects in-memory databases, non-SQLite engines and a destination equal to the source. The destination should be outside the repository and protected by local filesystem permissions.

A backup is not proven until restoration is tested. For a recovery drill, stop the API, worker, and scheduler; copy the backup to a separate disposable database path; point `VACANCYX_DATABASE_URL` at that copy; run `alembic upgrade head` if needed; start the API; check `/health/ready`; and verify expected records through the local UI. Never overwrite the active database during a drill. Keep the original backup unchanged. Do not copy candidate data into issue reports or CI artifacts.

## Migration policy
Never edit an already released migration. Add a new revision for every schema change, review generated DDL, and test both upgrade and downgrade on a disposable database. Back up user data before applying migrations to a real local installation. SQLite table rebuilds require special care for constraints and indexes.
