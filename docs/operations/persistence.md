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
Stop the API and worker before copying the SQLite database and its associated WAL/SHM files. Prefer SQLite's online backup API when a live backup facility is introduced. Keep backups outside the repository, restrict filesystem permissions, and test restoration before relying on a backup. Do not copy candidate data into issue reports or CI artifacts.

## Migration policy
Never edit an already released migration. Add a new revision for every schema change, review generated DDL, and test both upgrade and downgrade on a disposable database. Back up user data before applying migrations to a real local installation. SQLite table rebuilds require special care for constraints and indexes.
