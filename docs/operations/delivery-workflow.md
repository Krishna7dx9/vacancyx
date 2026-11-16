# Delivery, Git, CI/CD and operations

## Branch discipline
Only one active branch: confirm prior PR merged; create one focused branch; implement agreed scope; run checks/tests; inspect diff for secrets/unrelated files; open detailed PR; wait for CI and fix on same branch; review risks; merge; verify main and CI; only then create next branch. Never force-push or rewrite main. Do not delete branches automatically; the repository owner may clean up merged branches.

## PR requirements
Summary/motivation, scope/exclusions, design decisions, migration impact, security/privacy, failure/recovery, exact test commands/results, screenshots/benchmarks, docs updated, risks/follow-ups and acceptance checklist. Use the repository pull request template. Bug reports and feature requests should use the issue forms and include reproducible acceptance criteria. Never create placeholder issues or self-approve reviews just to improve contribution metrics.

## Main branch protection (repository owner setup)
In GitHub, open **Settings → Rules → Rulesets → New ruleset → New branch ruleset** (or **Settings → Branches → Add branch protection rule** on repositories using classic protection). Target the `main` branch and enable:
- Require a pull request before merging.
- Require status checks to pass before merging, selecting the checks below.
- Require branches to be up to date before merging.
- Block force pushes and branch deletion.
- Do not allow bypass for routine changes; keep any emergency bypass restricted to the owner and document its use.

Required status checks (GitHub may display the workflow/job pair):
- `Backend CI / quality`
- `Frontend CI / build`
- `Browser Contract CI / chromium-contract`
- `Fresh Machine Release Verification / clean-install`

Enable at least one approving review only when an independent collaborator is available. On a solo-maintained repository, do not manufacture an approval; use the PR checklist and review the diff/test evidence yourself until a real second reviewer is available. Confirm the exact check names in the ruleset picker after the workflows have run on a PR.

The GitHub automation connection used for repository maintenance cannot read or configure branch protection in this repository. The owner must apply these settings in GitHub's repository settings.

## CI strategy
GitHub Actions validates code; it is not local runtime scheduler. Run on PRs and main pushes with least-privilege permissions. Keep dependencies locked and install them reproducibly. Use dependency audits and automated dependency update PRs. Pin third-party actions to reviewed immutable SHAs where practical. Planned stages: runtime setup, locked dependencies, format/lint, type checks, unit/integration tests, migration validation, frontend checks, security/dependency audit, build smoke test and useful artifacts. Releases from reviewed tags or explicit release action.

## Local workflow
Document install, lint/type, unit/integration/all tests, API, worker, frontend, backup and restore commands in foundation milestone.

## Configuration/backup
Commit safe defaults and placeholder-only env example. Validate startup; keep user settings in local app data; version config schemas. Back up DB and managed files with checksums; test restore; keep backups outside repository.

## Release readiness
CI green on release SHA; migration and restore pass; security reviewed; clean setup tested; known limitations and rollback documented; demo data synthetic.
