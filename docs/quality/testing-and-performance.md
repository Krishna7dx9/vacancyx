# Testing, performance and capacity

## Test layers
- Unit: domain invariants/transitions, eligibility, scoring, canonicalization, dedupe, retries and approval hashes.
- Contract: source/portal adapters, repositories and API schemas.
- Integration: migrations, constraints, rollback, task leases/recovery, uploads, authorization, scheduler-worker flow.
- E2E: synthetic candidate through discovery/review; batch approve/reject/edit; local mock portal success, validation, CAPTCHA/OTP, crash and uncertain outcome.

Live third-party portals are not required for deterministic CI. Use synthetic profiles, resumes, listings and mock pages; never commit real personal data.

## Quality gates
Format/lint, type checks, unit/integration tests, migration validation, frontend checks, dependency/security audit, docs/link checks and build smoke test. Flaky tests are defects.

## Performance questions
API RPS for defined endpoint mix? p50/p95/p99 and errors at concurrency? Worker throughput? SQLite lock behavior? CPU/memory for parsing/browser? Queue wait under load? Query plans/indexes? Burst and slow dependency behavior?

## Benchmark protocol
Record commit, hardware, OS, runtime, DB size, dataset, endpoint mix, concurrency, warm-up, duration and raw results. Measure throughput, p50/p95/p99, errors, CPU, RSS, DB lock events and queue delay. Repeat trials and report variance. Separate API RPS from source-fetch and browser throughput. Never extrapolate a local machine result to a cluster.

Capacity estimates are hypotheses until load-tested. Include headroom/backpressure. Failure-inject process termination, lease expiry, DB busy, source timeout, 429/5xx, malformed payload, browser crash and uncertain submit; verify no duplicate external application.