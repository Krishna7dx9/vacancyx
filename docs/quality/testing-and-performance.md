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

## Local API benchmark CLI

Install the development package, migrate the local database, start the API on loopback, and run:

```bash
vacancyx-benchmark --requests 500 --warmup 50 --concurrency 10
```

The command is read-only and refuses non-loopback API URLs. Its deterministic endpoint mix measures health and bounded job search. To include the candidate-owned matching endpoint, seed the synthetic demo and pass the IDs printed by the seed command:

```bash
vacancyx-demo-seed
vacancyx-benchmark --requests 500 --warmup 50 --concurrency 10 \
  --candidate-id YOUR_SYNTHETIC_CANDIDATE_ID \
  --profile-id YOUR_SYNTHETIC_SEARCH_PROFILE_ID
```

Use only the synthetic demo IDs for matching benchmarks. The benchmark does not retain response bodies or modify application data. It reports total throughput, p50/p95/p99/max latency, HTTP status counts, error rate, per-endpoint metrics, client CPU time, commit, runtime, OS, concurrency, and optional SQLite file size. Save a JSON report with `--output benchmark.json`; supply `--database-path` to include the local SQLite file size.

The benchmark intentionally measures the API client perspective only. It does not measure server CPU/RSS, external source-fetch throughput, browser throughput, or distributed capacity. Capture server CPU/RSS separately with OS tooling during the run. Record hardware, DB size, dataset size, and repeat trials before making capacity decisions. The URL guard allows only `localhost`, `127.0.0.1`, or `::1`; do not point this command at production or a shared remote service.
