# VacancyX release acceptance checklist

This checklist separates automated evidence from checks that must be performed on the target computer. VacancyX is a local-first single-user tool; passing CI does not authorize remote exposure or prove that a particular computer has a recoverable backup.

## Automated release evidence

Before calling a build release-ready, verify all of the following on the exact main commit:

- [ ] Backend CI: Ruff, strict mypy, and full pytest suite pass.
- [ ] Frontend CI: npm audit, TypeScript checks, and production build pass.
- [ ] Browser Contract CI: real Chromium contract passes against the synthetic local form.
- [ ] Fresh Machine Release Verification: clean dependency install, empty-database migrations, repeatable synthetic seed, API readiness/OpenAPI, and frontend clean build pass.
- [ ] Migration chain upgrades from an empty database and the migration rollback tests pass.
- [ ] Benchmark report is generated on the target hardware and retained locally with commit, OS, Python, DB size, dataset, concurrency, warm-up, endpoint mix, p50/p95/p99, throughput, and errors.

Do not treat a benchmark on GitHub-hosted runners as a capacity guarantee for another computer.

## Target-computer installation

- [ ] Start from a clean checkout or a separate clean working copy.
- [ ] Follow the local setup guide; install Python 3.11+, backend dependencies, and frontend dependencies with npm ci.
- [ ] Copy .env.example to .env; keep .env and .vacancyx/ out of Git.
- [ ] Run alembic upgrade head.
- [ ] Run vacancyx-demo-seed twice; confirm it is idempotent and the demo job is clearly synthetic.
- [ ] Start the API bound to 127.0.0.1; verify /health/live and /health/ready.
- [ ] Start the frontend and confirm the local workspace loads.
- [ ] Confirm the API rejects non-loopback bind addresses. Do not use a tunnel, LAN binding, reverse proxy, or public hosting.

## Core product walkthrough

Use only synthetic records for this first walkthrough:

- [ ] Create and edit a candidate profile and saved search profile.
- [ ] Upload a synthetic PDF/DOCX/TXT resume and review parsed fields before reuse.
- [ ] Create and revise reusable answers.
- [ ] Add a verified public Greenhouse or Lever source, run discovery, and inspect provenance/verification.
- [ ] Confirm duplicate jobs are deduplicated and unknown salary/location/work-mode facts are not guessed.
- [ ] Run matching and inspect hard eligibility separately from the explainable score.
- [ ] Prepare an application, inspect the exact resume/answer snapshot, revise it, and confirm an old approval becomes stale.
- [ ] Approve the exact current revision through batch review.
- [ ] Run browser assistance only against a controlled local mock portal first. Confirm it fills ordinary fields but never clicks Submit.
- [ ] Confirm CAPTCHA, OTP/MFA, legal attestations, unsupported fields, redirects, and interruptions stop for manual handling.
- [ ] Confirm interrupted/ambiguous browser runs remain uncertain and are never marked submitted automatically.
- [ ] Record a synthetic confirmation reference manually and inspect the application timeline.

Never use the synthetic demo vacancy for a real application. Do not test against a real employer portal without the candidate's direct supervision and a genuine, reviewed application.

## Backup and recovery drill

1. Stop the API, worker, and scheduler.
2. Create a backup outside the repository with vacancyx-backup create --destination PATH.
3. Run vacancyx-backup verify PATH; require SQLite integrity and foreign-key checks to pass.
4. Make a separate disposable copy of the backup. Never experiment on the only backup or active database.
5. Point VACANCYX_DATABASE_URL at the disposable copy and run alembic upgrade head.
6. Start the API against that copy; require /health/ready to pass.
7. Inspect the expected candidate, resumes, saved searches, prepared applications, approvals, and timeline records.
8. Stop all processes and discard only the disposable copy after verification.
9. Keep the original backup protected with local filesystem permissions and a separate recovery copy.

A successful backup command or integrity check alone is not a completed restore drill.

## Security and privacy sign-off

- [ ] Confirm API binding remains loopback-only.
- [ ] Confirm .env, .vacancyx/, resume uploads, browser profile/session files, and backups are ignored by Git and absent from release artifacts.
- [ ] Confirm public source requests use only fixed provider HTTPS hosts and contain no candidate profile/resume data.
- [ ] Confirm upload size/type/archive bounds and generated storage names remain enforced.
- [ ] Confirm logs and error messages do not expose resume contents, access tokens, or browser cookies.
- [ ] Confirm browser assistance never bypasses CAPTCHA, MFA, login controls, rate limits, or legal attestations and never clicks Submit.
- [ ] Review dependency audit output and resolve or explicitly document accepted findings.
- [ ] Do not enable remote access or multi-user use. Authentication, authorization, CSRF/Origin protections, and ownership enforcement must be designed and reviewed before that boundary changes.

## Release decision

A release may be called a local MVP only when automated evidence is green, the target-computer walkthrough is complete, the restore drill succeeds, and the security/privacy checklist is reviewed. Record the commit SHA, date, machine/OS, test evidence, benchmark report location, backup location, and unresolved limitations.

Known limitations to disclose:

- Only public Greenhouse and Lever source adapters are implemented.
- Discovery schedules run only while the local computer and scheduler/worker processes are available.
- Browser assistance fills supported fields but does not submit applications.
- The API has no authentication and must remain loopback-only.
- No cloud backup, automatic retention, multi-user mode, or remote deployment is provided.
