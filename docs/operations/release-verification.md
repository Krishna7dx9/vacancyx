# Release verification checklist

Use this checklist before calling a VacancyX build release-ready. CI proves repeatable checks on a clean runner; a human still needs to verify the actual target machine and browser environment.

## Automated clean-install gate

The `Fresh Install Verification` workflow performs these steps from a clean Git checkout:

- Create a new Python 3.11 virtual environment and install the project plus development dependencies.
- Run Ruff, strict mypy, and the complete pytest suite.
- Create an isolated SQLite database, apply every Alembic migration, and seed synthetic demo data.
- Verify core migrated tables exist.
- Install the locked frontend dependencies with `npm ci`, run the dependency audit, TypeScript check, and production build.
- Confirm the workflow did not leave untracked local data in the checkout.

A green run is necessary but not sufficient for release.

## Fresh-machine manual drill

On a machine that has never run VacancyX:

1. Clone the repository and follow [local setup](demo-setup.md) without copying an existing database, `.env`, resume, or backup.
2. Create a new virtual environment and install from the documented commands.
3. Copy `.env.example`, apply migrations, and run `vacancyx-demo-seed`.
4. Start the API and frontend. Confirm the UI loads and the operations summary reports database readiness.
5. Add one verified public Greenhouse or Lever board, run one discovery task, and confirm source provenance is visible. Do not use a private board or submit an application.
6. Start the local scheduler and worker. Create a short-interval schedule, confirm a task is queued and completed, then pause the schedule.
7. Complete the synthetic workflow in the test suite: matching, immutable application preparation, batch approval, and confirmation-gated tracking.
8. If testing browser assistance, use only the local synthetic fixture and a headed browser. Confirm it fills only ordinary fields, stops on blockers, and never clicks Submit.
9. Back up the local database, restore it to a separate temporary path using the documented recovery procedure, and verify SQLite integrity and expected records.
10. Close API, frontend, scheduler, and worker. Restart them and verify the local database and task history remain intact.

Record OS, Python, Node, browser version, commit SHA, test output, and any manual deviations. Never attach a real resume, contact details, employer credentials, database, or `.env` to a public issue or PR.

## Security and release boundary

- The unauthenticated API must remain bound to loopback. Do not expose it to LAN, a tunnel, reverse proxy, or public internet.
- Keep `.env`, SQLite files, resume storage, backups, browser profiles, and logs private.
- Public discovery only uses supported Greenhouse and Lever public endpoints and their fixed HTTPS hosts.
- CAPTCHA, login, OTP/MFA, unknown questions, work authorization, demographic questions, and legal attestations require manual handling.
- Browser assistance does not submit forms. A candidate verifies the employer confirmation before recording a submission.
- Local schedules only run while the machine and scheduler/worker processes are available.

## Release decision

A release candidate is ready for a limited local demo only when:

- Backend, frontend, browser-contract, and fresh-install workflows are green on the exact release commit.
- Migration upgrade and backup/restore checks pass.
- The synthetic end-to-end workflow passes.
- The fresh-machine manual drill is recorded with no unresolved data-loss or security issue.
- Known limitations are visible in the README and operating guides.

Do not describe the product as production-ready or suitable for multi-user/remote deployment until authentication, authorization, deployment hardening, and a separate security review are complete.
