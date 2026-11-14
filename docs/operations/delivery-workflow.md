# Delivery, Git, CI/CD and operations

## Branch discipline
Only one active branch: confirm prior PR merged; create one focused branch; implement agreed scope; run checks/tests; inspect diff for secrets/unrelated files; open detailed PR; wait for CI and fix on same branch; review risks; merge; verify main and CI; only then create next branch. Never force-push or rewrite main.

## PR requirements
Summary/motivation, scope/exclusions, design decisions, migration impact, security/privacy, failure/recovery, exact test commands/results, screenshots/benchmarks, docs updated, risks/follow-ups and acceptance checklist.

## CI strategy
GitHub Actions validates code; it is not local runtime scheduler. Run on PRs and main pushes with least-privilege permissions. Pin third-party actions to reviewed immutable SHAs where practical. Planned stages: runtime setup, locked dependencies, format/lint, type checks, unit/integration tests, migration validation, frontend checks, security/dependency audit, build smoke test and useful artifacts. Releases from reviewed tags or explicit release action.

## Local workflow
Document install, lint/type, unit/integration/all tests, API, worker, frontend, backup and restore commands in foundation milestone.

## Configuration/backup
Commit safe defaults and placeholder-only env example. Validate startup; keep user settings in local app data; version config schemas. Back up DB and managed files with checksums; test restore; keep backups outside repository.

## Release readiness
CI green on release SHA; migration and restore pass; security reviewed; clean setup tested; known limitations and rollback documented; demo data synthetic.