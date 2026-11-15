# VacancyX

Local-first job discovery and application workflow platform.

> Status: implementation in progress. Backend foundations, SQLite persistence and recovery, candidate profile APIs, secure local resume storage, resume parsing/review, reusable answer library, job-source ingestion, explainable matching, job search APIs, the local React workspace, immutable application preparation, revision-bound batch review, application tracking, and the local durable worker runtime are implemented. Configured public Greenhouse and Lever discovery can run as durable background tasks. Human-supervised browser assistance now has a visible Playwright runner gated by a current approved immutable application revision. The user must submit manually; recurring schedules, mock employer-portal end-to-end coverage, and production hardening remain unfinished.

VacancyX is a configurable product for candidate profiles, resume management, job discovery, explainable matching, application preparation, batch review, human-supervised browser assistance, and outcome tracking.

## Principles

- Candidate-independent: personal profiles and preferences are data, never hardcoded.
- Local-first with no mandatory paid APIs, hosted database, LLM, or subscription.
- Batch approval binds to an immutable application revision.
- Source provenance and vacancy verification are explicit.
- Durable tasks, bounded retries, audit events, recovery, and measured performance.
- Browser assistance never bypasses CAPTCHA/MFA or clicks Submit.

## Architecture

Modular monolith with separately runnable workers; SQLite initially; future PostgreSQL only when justified by measurements. Stack: React/TypeScript, Python/FastAPI/Pydantic, SQLAlchemy/Alembic, Playwright (optional), pytest, Ruff/mypy, and GitHub Actions.

## Cost and access

Core runs locally. Public sites may restrict access, change interfaces, require login, or rate-limit. Respect terms and controls; never bypass CAPTCHA/MFA. Scheduled work runs only while the computer is available.

See [engineering docs](docs/README.md), [roadmap](docs/roadmap/engineering-roadmap.md), [local worker guide](docs/operations/local-worker.md), [browser assistance setup](docs/operations/browser-assist.md), and [browser assistance safety contract](docs/operations/browser-assist-safety.md).

One branch at a time: test, PR, merge, verify main, then create the next. The local workspace supports candidate setup, configurable search criteria, job search, explainable matching, resume review, reusable answers, application preparation, revision-bound batch approval, discovery task queueing, and application tracking. The CLI opens only a currently approved application revision, checks the exact employer host allowlist, fills recognized ordinary text fields in a visible browser, and records an audit event. It never clicks Submit or marks an application submitted. Run it on the machine with the local VacancyX database and a graphical desktop session.

MIT License.
