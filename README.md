# VacancyX

Local-first job discovery and application workflow platform.

> Status: implementation in progress. Backend foundations, SQLite persistence and recovery, candidate profile APIs, secure local resume storage, resume parsing/review, reusable answer library, job-source ingestion, explainable matching, job search APIs, the local React workspace, immutable application preparation, revision-bound batch review, application status transitions, and an append-only timeline for assessments, interviews, offers, follow-ups and notes are implemented. The local durable worker runtime supports configured public Greenhouse and Lever discovery tasks, with fenced leases, retries, recovery, task status APIs and a local queue UI. External browser submission automation, recurring schedules and production hardening remain unfinished.

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

See [engineering docs](docs/README.md) and [roadmap](docs/roadmap/engineering-roadmap.md). One branch at a time: test, PR, merge, verify main, then create the next. The local workspace supports candidate setup, configurable search criteria, job search, explainable matching, resume review, reusable answers, application preparation, and revision-bound batch approval. A local worker process can execute registered durable task handlers, including source discovery for configured public Greenhouse and Lever boards. The workspace can enqueue per-source tasks, show status and errors, cancel pending/running tasks, and refresh indexed jobs. Application status transitions and an append-only timeline for assessments, interviews, offers, follow-ups and notes are implemented; current-revision approval is required before starting submission; a confirmation reference is required before marking submitted. External browser submission automation, recurring schedules, and production hardening remain unfinished. Start the worker with `vacancyx-worker` after applying migrations; see the [local worker guide](docs/operations/local-worker.md).

MIT License.
