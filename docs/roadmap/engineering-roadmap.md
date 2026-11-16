# Engineering roadmap

Sequential delivery: one active branch at a time. Complete, test, document, PR, merge, verify main, then create next branch.

| Milestone | Status | Deliverables | Exit criteria |
|---|---|---|---|
| 0 Blueprint | Complete | PRD, scope, architecture, ADRs, data model, security, reliability, tests, roadmap | Docs consistent, no personal data, open decisions explicit |
| 1 Foundation | Complete | Packaging, backend/frontend skeleton, config, env example, ignore rules, CI, developer commands | Clean setup; lint/type/test; CI green; secrets ignored |
| 2 Persistence | Complete | Entities, SQLAlchemy, repositories, Alembic, SQLite, transactions, online backup/restore | Empty DB migration; constraints/rollback; backup restore smoke test |
| 3 Profiles | Complete | Candidate profile API/UI, editable candidate and search profiles, secure local resume storage, parser/review, versioned answer library | Ownership, safe upload, editable review output, and immutable answer revisions tested |
| 4 Source framework | Complete | Adapter protocol, normalized listing contract, validated source config, source registry, HTTPS host policy, timeout/concurrency/rate gate | Fake adapter passes; unsafe URLs rejected; limits enforced |
| 5 Discovery | Complete | Greenhouse/Lever adapters, bounded pagination, page-atomic persistence, provenance, deduplication, background task queue | Idempotent ingestion; partial failure preserved; limits and task retries tested |
| 6 Matching | Complete | Pure versioned rule engine, hard eligibility, explainable weighted score, unknown-data review state | Curated decision tests and explanations pass |
| 7 API/UI | Complete | Job search, candidate-owned search profile CRUD, editable profile UI, discovery/schedule UI, operations summary | API contracts, TypeScript, and frontend build pass |
| 8 Preparation | Complete | Candidate-owned application drafts, immutable snapshots, resume/answer selection, readiness warnings, review workspace | Edits create revisions; ownership enforced; hashes and audit events tested |
| 9 Batch workflow | Complete | Candidate-owned review batches, immutable revision/hash items, exact snapshot inspection, approve/reject, stale-item detection | Decisions bind to exact revision/hash; stale content cannot be approved |
| 9b Durable worker | Complete | Database-backed tasks, atomic claims, fenced leases, heartbeats, bounded retries, recovery, cancellation, local worker CLI | No stale worker can complete; retries bounded; restart recovery tested |
| 9c Recurring discovery | Complete | Durable schedule model/API, idempotent scheduler CLI, workspace controls, missed-run coalescing | Schedule CRUD, idempotent enqueue, pause/resume and worker integration tested |
| 10 Browser assistance | Complete | Strict HTTPS host allowlist, interruption detection, approved-revision CLI guard, headed Playwright single/batch runner, safe field fill, redirect guard, uncertain-outcome audit, mocked portal and real Chromium contract CI | CAPTCHA/MFA/legal blockers stop; off-host redirects blocked; failures remain uncertain; no automatic submission |
| 11 Tracking | Complete | Candidate-scoped lifecycle transitions, confirmation evidence, append-only assessment/interview/offer/follow-up timeline | Safe transitions; submitted requires confirmation evidence; event history tested |
| 12 Hardening | In progress | Loopback-only binding, dependency audit, npm lockfile, migration and backup checks, synthetic seed, operations summary, real Chromium CI, local worker/scheduler process heartbeats | Reproducible load benchmark; clean install/recovery drill; security review |
| 13 Release/demo | In progress | Install guide, synthetic demo, end-to-end API workflow, source-management UI, browser safety guide, operations runbook, automated fresh-machine release verification | Recovery drill; security review; manual fresh-machine walkthrough; release checklist; limitations explicit |

Definition of done: acceptance met; scoped typed implementation; tests pass; lint/type/security/CI green; errors/logs reviewed; docs updated; PR has design, alternatives, evidence and risks; no secrets/unrelated changes.
