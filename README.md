# VacancyX

Local-first job discovery and application workflow platform.

> Status: implementation in progress. Backend foundations, SQLite persistence and recovery, candidate profile APIs, secure local resume storage, resume parsing/review, reusable answer library, job-source ingestion, explainable matching, job search APIs, the local React workspace, immutable application preparation, and revision-bound batch review are implemented. The local durable worker runtime is implemented with fenced leases, retries, recovery, and a diagnostic handler; source-specific background handlers, browser automation, outcome tracking, and production hardening remain unfinished.

VacancyX is a configurable product for candidate profiles, resume management, job discovery, explainable matching, application preparation, batch review, supported browser automation, and outcome tracking.

## Principles
- Candidate-independent: personal profiles and preferences are data, never hardcoded.
- Local-first with no mandatory paid APIs, hosted database, LLM, or subscription.
- Batch approval before external submissions; approval binds to an immutable application revision.
- Source provenance and vacancy verification are explicit.
- Durable tasks, bounded retries, audit events, recovery, and measured performance.

## Architecture
Modular monolith with separately runnable workers; SQLite initially; future PostgreSQL only when justified by measurements. Planned stack: React/TypeScript, Python/FastAPI/Pydantic, SQLAlchemy/Alembic, Playwright, pytest/Vitest, Ruff/mypy, GitHub Actions.

## Cost and access
Core runs locally. Public sites may restrict access, change interfaces, require login, or rate-limit. Respect terms and controls; never bypass CAPTCHA/MFA. Scheduled work runs only while the computer is available.

See [engineering docs](docs/README.md) and [roadmap](docs/roadmap/engineering-roadmap.md). One branch at a time: test, PR, merge, verify main, then create the next. The local workspace supports candidate setup, configurable search criteria, job search, explainable matching, resume review, reusable answers, application preparation, and revision-bound batch approval. A local worker process can execute registered durable task handlers; the built-in `system.echo` handler is diagnostic only. Discovery handlers, Playwright portal automation, outcome tracking, and the complete end-to-end workflow remain unfinished. Start the worker with `vacancyx-worker` after applying migrations; see the [local worker guide](docs/operations/local-worker.md).

MIT License.
