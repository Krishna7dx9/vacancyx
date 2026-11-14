# Engineering roadmap

Sequential delivery: one active branch at a time. Complete, test, document, PR, merge, verify main, then create next branch.

| Milestone | Status | Deliverables | Exit criteria |
|---|---|---|---|
| 0 Blueprint | Complete | PRD, scope, architecture, ADRs, data model, security, reliability, tests, roadmap | Docs consistent, no personal data, open decisions explicit |
| 1 Foundation | Complete | Packaging, backend/frontend skeleton, config, env example, ignore rules, CI, developer commands | Clean setup; lint/type/test; CI green; secrets ignored |
| 2 Persistence | Complete | Entities, SQLAlchemy, repositories, Alembic, SQLite, transactions, online backup/restore | Empty DB migration; constraints/rollback; backup restore smoke test |
| 3 Profiles | In progress | Candidate/resume versioning, parser, answer library | Multiple synthetic profiles; safe upload; editable parse output |
| 4 Source framework | Adapter contract, config schema, rate limiter, HTTP policy, contract tests | Fake adapter passes; adding source does not change matching |
| 5 Discovery | Pagination, observations, normalization, canonical identity, dedupe | Idempotent ingestion; partial failure preserved; limits honored |
| 6 Matching | Versioned rules, hard eligibility, explainable score, unknown semantics | Curated decision tests and explanations pass |
| 7 API/UI | Versioned REST, filters, errors, dashboard, local auth boundary | Contracts pass; ownership enforced; long work not in HTTP |
| 8 Preparation | Immutable revisions, resume/answer selection, readiness | Edits create revisions; unknown answers flagged |
| 9 Batch workflow | Batches, approvals, task states, leases, retries, cancellation, audit | Approval invalidation; crash recovery; concurrent claim safety |
| 10 Browser | Playwright, portal adapters, forms, confirmation, exceptions | Mock portal E2E success/failure/CAPTCHA/crash/uncertain; no duplicate retry |
| 11 Tracking | Timeline, transitions, follow-ups, analytics, exports | Events consistent; exports complete |
| 12 Hardening | Threat verification, dependency checks, profiling, load tests, backup drills | Security tests; reproducible benchmark; limits documented |
| 13 Release/demo | Release, install guide, synthetic demo, diagrams, API docs, benchmark | Clean setup; CI green; docs verified; no unsupported claims |

Definition of done: acceptance met; scoped typed implementation; tests pass; lint/type/security/CI green; errors/logs reviewed; docs updated; PR has design, alternatives, evidence and risks; no secrets/unrelated changes.