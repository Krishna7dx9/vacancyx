# Engineering roadmap

Sequential delivery: one active branch at a time. Complete, test, document, PR, merge, verify main, then create next branch.

| Milestone | Status | Deliverables | Exit criteria |
|---|---|---|---|
| 0 Blueprint | Complete | PRD, scope, architecture, ADRs, data model, security, reliability, tests, roadmap | Docs consistent, no personal data, open decisions explicit |
| 1 Foundation | Complete | Packaging, backend/frontend skeleton, config, env example, ignore rules, CI, developer commands | Clean setup; lint/type/test; CI green; secrets ignored |
| 2 Persistence | Complete | Entities, SQLAlchemy, repositories, Alembic, SQLite, transactions, online backup/restore | Empty DB migration; constraints/rollback; backup restore smoke test |
| 3 Profiles | Complete | Candidate profile API, secure resume storage, local parser/review, versioned candidate answer library | Multiple synthetic profiles; safe upload; editable parse output; answer ownership and immutable revision history tested |
| 4 Source framework | Complete | Adapter protocol, normalized listing contract, validated source config, source registry, HTTPS host policy, timeout/concurrency/rate gate, fake adapter contract tests | Fake adapter passes; unsafe URLs rejected; limits enforced; adding a source does not change matching |
| 5 Discovery | Complete | Bounded pagination, page-atomic persistence, source observations, canonical HTTPS URL identity, cross-source deduplication, safe partial outcomes | Idempotent ingestion; partial failure preserved; limits honored |
| 6 Matching | Complete | Pure versioned rule engine, hard eligibility, explainable weighted score, explicit unknown-data review state, curated fixtures | Curated decision tests and explanations pass |
| 7 API/UI | Complete | Versioned job search, candidate-owned search profile CRUD, on-demand match evaluation, responsive local React workspace for candidate setup, criteria, search and explanations | API contracts and UI build pass; ownership enforced; local auth boundary verified; long work not in HTTP |
| 8 Preparation | Complete | Candidate-owned application drafts, immutable content snapshots, resume/answer selection, readiness warnings, preparation API and candidate-facing review workspace | Edits create revisions; ownership enforced; snapshot hashes and audit events tested; UI supports local resume review and reusable answers |
| 9 Batch workflow | Complete | Candidate-owned review batches, immutable revision/hash items, exact snapshot inspection, approve/reject decisions, readiness gate, stale-item detection, approval invalidation audit and database uniqueness guard | Decisions bind to exact revision/hash; stale content cannot be approved; readiness gates approval; historical approvals remain auditable; candidate can inspect all submitted content before deciding |
| 9b Durable worker | Complete | Database-backed task queue, atomic claims, fenced leases, heartbeats, bounded exponential retry/backoff, expired-lease recovery, cancellation, explicit handler registry and local worker CLI | Concurrent workers cannot double-claim; expired leases recover; stale workers cannot complete; retries are bounded; tasks are observable and restart-safe; no long work runs inside database transactions |
| 9c Background task integrations | In progress | Configurable public Greenhouse/Lever adapters, background source discovery tasks, candidate-independent task status/cancel APIs and a local discovery queue UI | HTTP requests enqueue quickly; workers execute bounded source handlers; progress and partial outcomes are visible; source allowlists and page limits are enforced; schedules do not duplicate tasks |
| 10 Browser | Planned | Playwright, portal adapters, forms, confirmation, exceptions | Mock portal E2E success/failure/CAPTCHA/crash/uncertain; no duplicate retry |
| 11 Tracking | In progress | Candidate-scoped lifecycle transitions, submission evidence, append-only assessment/interview/offer/follow-up timeline | Safe transitions enforced; submission requires confirmation evidence; event history is candidate-scoped and tested |
| 12 Hardening | Planned | Threat verification, dependency checks, profiling, load tests, backup drills | Security tests; reproducible benchmark; limits documented |
| 13 Release/demo | Planned | Release, install guide, synthetic demo, diagrams, API docs, benchmark | Clean setup; CI green; docs verified; no unsupported claims |

Definition of done: acceptance met; scoped typed implementation; tests pass; lint/type/security/CI green; errors/logs reviewed; docs updated; PR has design, alternatives, evidence and risks; no secrets/unrelated changes.
