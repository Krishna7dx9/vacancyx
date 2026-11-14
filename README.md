# VacancyX

Local-first job discovery and application workflow platform.

> Status: product and engineering blueprint; implementation has not started.

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

See [engineering docs](docs/README.md) and [roadmap](docs/roadmap/engineering-roadmap.md). One branch at a time: test, PR, merge, verify main, then create the next.

MIT License.