# VacancyX

Local-first job discovery and application workflow platform.

> Status: implementation in progress. Backend foundations, SQLite persistence and recovery, candidate profile APIs, secure local resume storage, resume parsing/review, reusable answer library, job-source ingestion, explainable matching, job search APIs, the local React workspace, immutable application preparation, revision-bound batch review, application tracking, and the local durable worker runtime are implemented. Configured public Greenhouse and Lever discovery can run as durable background tasks. Human-supervised browser assistance has a visible Playwright runner gated by a current approved immutable application revision; it supports single applications and sequential assistance for approved items in a review batch. The user submits manually. Recurring discovery schedules have durable storage, create/pause/resume/delete APIs, a local scheduler process, and workspace controls. Synthetic end-to-end API coverage exercises candidate matching through approved application tracking. A repeatable synthetic demo seed is available. Live-browser CI coverage, richer operational monitoring, and production hardening remain unfinished.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
vacancyx-demo-seed
uvicorn vacancyx.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, run `cd frontend && npm install && npm run dev`. See [local setup and demo](docs/operations/demo-setup.md) for Windows activation, background worker/scheduler, and optional Playwright setup.

VacancyX is a configurable product for candidate profiles, resume management, job discovery, explainable matching, application preparation, batch review, human-supervised browser assistance, recurring discovery, and outcome tracking.

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

See [engineering docs](docs/README.md), [roadmap](docs/roadmap/engineering-roadmap.md), [local setup and demo](docs/operations/demo-setup.md), [local worker and scheduler guide](docs/operations/local-worker.md), [browser assistance setup](docs/operations/browser-assist.md), [browser assistance safety contract](docs/operations/browser-assist-safety.md), [browser assistance tests](docs/operations/browser-assist-testing.md), and [end-to-end workflow verification](docs/operations/end-to-end-workflow.md).

One branch at a time: test, PR, merge, verify main, then create the next. The local workspace supports candidate setup, configurable search criteria, job search, explainable matching, resume review, reusable answers, application preparation, revision-bound batch approval, discovery task queueing, recurring discovery schedules, and application tracking. The browser assistant can open one approved application or sequentially walk through approved items in a review batch, rechecking each immutable revision before launch. It fills recognized ordinary text fields in a visible browser, records audit events, and requires a per-application OPEN/SKIP/STOP choice. It never clicks Submit or marks an application submitted. The synthetic end-to-end API test covers matching through approved and confirmed application tracking. Recurring schedules enqueue idempotent discovery tasks while the local scheduler and worker processes are running.

MIT License.