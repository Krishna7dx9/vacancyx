# VacancyX

Local-first job discovery and application workflow platform.

> Status: functional local-first MVP with automated backend, frontend, and real Chromium contract CI. Candidate profiles (including editing), resume management, reusable answers, public Greenhouse/Lever discovery, explainable matching, immutable application preparation, revision-bound batch review, application tracking, durable local workers, recurring discovery schedules, operations diagnostics (including worker/scheduler process liveness), and synthetic demo workflows are implemented. Human-supervised single and batch browser assistance uses exact host allowlists and immutable approval checks. Interrupted browser sessions are recorded as uncertain; they never mark an application submitted. The user must submit manually. Remaining release hardening includes a source-management screen, reproducible load benchmarks, fresh-machine release verification, and authentication before any remote access.

## Quick start

\`\`\`bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
vacancyx-demo-seed
uvicorn vacancyx.main:app --reload --host 127.0.0.1 --port 8000
\`\`\`

In a second terminal, run \`cd frontend && npm ci && npm run dev\`. See [local setup and demo](docs/operations/demo-setup.md) for Windows activation, public source configuration, background worker/scheduler, and optional Playwright setup.

## Principles

- Candidate-independent: personal profiles and preferences are data, never hardcoded.
- Local-first with no mandatory paid APIs, hosted database, LLM, or subscription.
- Batch approval binds to an immutable application revision.
- Source provenance and vacancy verification are explicit.
- Durable tasks, bounded retries, audit events, recovery, and measured performance.
- Browser assistance never bypasses CAPTCHA/MFA or clicks Submit.

## Architecture

Modular monolith with separately runnable local workers; SQLite initially; future PostgreSQL only when justified by measurements. Stack: React/TypeScript, Python/FastAPI/Pydantic, SQLAlchemy/Alembic, Playwright (optional), pytest, Ruff/mypy, and GitHub Actions.

## Cost, access, and security boundary

Core runs locally. The API is loopback-only because candidate endpoints do not yet have authentication. Do not expose it through a tunnel, reverse proxy, LAN, or public network. Public job boards may restrict access, change interfaces, require login, or rate-limit. Respect their terms and controls. Scheduled work only runs while the local computer, scheduler, and worker are available.

See [engineering docs](docs/README.md), [roadmap](docs/roadmap/engineering-roadmap.md), [local setup and demo](docs/operations/demo-setup.md), [public source configuration](docs/operations/public-sources.md), [worker and scheduler guide](docs/operations/local-worker.md), [browser assistance setup](docs/operations/browser-assist.md), [browser safety contract](docs/operations/browser-assist-safety.md), [browser tests](docs/operations/browser-assist-testing.md), and [end-to-end workflow](docs/operations/end-to-end-workflow.md).

The workspace supports candidate and search-profile editing, job search, explainable matching, resume review, reusable answers, application preparation, revision-bound batch approval, background discovery, recurring schedules, aggregate operations diagnostics, and application tracking. Browser assistance opens only currently approved revisions, revalidates each item before launch, fills recognized ordinary fields in a visible browser, and asks OPEN/SKIP/STOP per application. Browser errors are audited as uncertain; they do not imply an application was submitted. The synthetic API workflow test covers matching through approved and confirmed tracking. Recurring schedules enqueue idempotent tasks while the local scheduler and worker are running.

MIT License.
