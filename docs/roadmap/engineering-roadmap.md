# Engineering roadmap

Sequential delivery: one active branch at a time. Complete, test, document, PR, merge, verify main, then create the next branch.

| Milestone | Status | Deliverables | Exit criteria |
|---|---|---|---|
| 0 Blueprint | Complete | PRD, scope, architecture, ADRs, data model, security, reliability, tests, roadmap | Docs consistent, no personal data, open decisions explicit |
| 1 Foundation | Complete | Packaging, backend/frontend skeleton, config, env example, ignore rules, CI, developer commands | Clean setup; lint/type/test; CI green; secrets ignored |
| 2 Persistence | Complete | Entities, SQLAlchemy, repositories, Alembic, SQLite, transactions, online backup/restore | Empty DB migration; constraints/rollback; backup restore smoke test |
| 3 Profiles | Complete | Candidate profile API, secure local resume storage, parser/review, versioned answer library | Multiple synthetic profiles; safe upload; editable parse output; ownership and immutable revisions tested |
| 4 Source framework | Complete | Adapter protocol, normalized listing contract, validated source config, source registry, HTTPS host policy, timeout/concurrency/rate gate | Fake adapter passes; unsafe URLs rejected; limits enforced |
| 5 Discovery | Complete | Bounded pagination, page-atomic persistence, source observations, canonical URL identity, cross-source deduplication | Idempotent ingestion; partial failure preserved; limits honored |
| 6 Matching | Complete | Pure versioned rule engine, hard eligibility, explainable weighted score, unknown-data review state | Curated decision tests and explanations pass |
| 7 API/UI | Complete | Versioned job search, candidate-owned search profile CRUD, on-demand matching, responsive local workspace | API contracts and UI build pass; ownership enforced |
| 8 Preparation | Complete | Candidate-owned application drafts, immutable snapshots, resume/answer selection, readiness warnings, review workspace | Edits create revisions; ownership enforced; hashes and audit events tested |
| 9 Batch workflow | Complete | Candidate-owned review batches, immutable revision/hash items, exact snapshot inspection, approve/reject, stale-item detection | Decisions bind to exact revision/hash; stale content cannot be approved |
| 9b Durable worker | Complete | Database-backed tasks, atomic claims, fenced leases, heartbeats, bounded retries, recovery, cancellation, local worker CLI | No double claims; stale workers cannot complete; retries bounded; restart-safe |
| 9c Background task integrations | Complete | Configurable Greenhouse/Lever adapters, background discovery tasks, task status/cancel APIs and queue UI | Progress and partial outcomes visible; source allowlists and page limits enforced |
| 9d Recurring discovery | Complete | Durable schedule model/migration, create/list/pause/resume/delete API, idempotent scheduler CLI, workspace controls | Schedule CRUD, missed-run coalescing, idempotent enqueue, and local scheduler/worker documented |
| 10 Browser assistance | In progress | Strict URL allowlist, manual-interruption detection, approved-revision CLI guard, headed Playwright runner, single and batch modes, safe known-field fill, redirect guard, mocked portal tests, uncertain-outcome audit | Human approval per application; CAPTCHA/OTP/MFA/legal attestations stop; off-host redirects blocked; failures remain uncertain; no automatic submission |
| 11 Tracking | Complete | Candidate-scoped lifecycle transitions, submission evidence, append-only assessment/interview/offer/follow-up timeline | Safe transitions; submission requires confirmation evidence; event history tested |
| 12 Hardening | In progress | Loopback-only binding, dependency audit, lockfile, migration and backup checks, demo seed, browser failure audit, real-browser contract test, operational diagnostics | Clean install; all CI green; no sensitive data in logs/repo; browser contract verified; recovery steps documented |
| 13 Release/demo | In progress | Install guide, synthetic demo, end-to-end API workflow, architecture/operations docs, release checklist | Fresh-machine walkthrough; CI green; docs match code; limitations explicit; no unsupported claims |

Definition of done: acceptance met; scoped typed implementation; tests pass; lint/type/security/CI green; errors/logs reviewed; docs updated; PR has design, alternatives, evidence and risks; no secrets/unrelated changes.
