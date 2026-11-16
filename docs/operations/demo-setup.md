# Local setup and synthetic demo

VacancyX is a local-first application. Keep the API bound to loopback and keep the database, \`.env\`, uploaded resumes, and backups private.

## 1. Install the backend

From the repository root:

\`\`\`bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
\`\`\`

On Windows PowerShell, activate with \`.venv\\Scripts\\Activate.ps1\`.

## 2. Configure and migrate

\`\`\`bash
cp .env.example .env
alembic upgrade head
\`\`\`

VacancyX binds the API to \`127.0.0.1\` by default and stores its SQLite database and local files under \`.vacancyx/\`. Do not expose the unauthenticated API through a tunnel, reverse proxy, LAN, or public network.

## 3. Seed synthetic demo records

\`\`\`bash
vacancyx-demo-seed
\`\`\`

The command is idempotent. It creates one synthetic candidate, one clearly labeled demo job, a synthetic source observation, and a matching search profile. It prints their IDs. It does not create a fake resume or an approved application, and it never overwrites a non-demo candidate or an unexpected job that uses the reserved demo URL.

All demo identifiers use reserved test domains (\`.invalid\` and \`.test\`). The demo job is not a real vacancy and must never be applied to.

## 4. Start the API and frontend

Terminal 1, from the repository root:

\`\`\`bash
uvicorn vacancyx.main:app --reload --host 127.0.0.1 --port 8000
\`\`\`

Terminal 2:

\`\`\`bash
cd frontend
npm ci
npm run dev
\`\`\`

Open the local Vite URL shown in the terminal. The frontend proxies \`/api\` requests to the local API.

## 5. Configure and run public discovery (optional)

Add official public Greenhouse board tokens or Lever site slugs to the \`.env\` file. See [public source configuration](public-sources.md). Restart the API after editing \`.env\`, then start these in separate terminals:

\`\`\`bash
vacancyx-scheduler
vacancyx-worker
\`\`\`

The scheduler enqueues due recurring work; the worker executes it. Both processes must stay running while schedules execute. A powered-off machine does not run schedules; missed intervals are coalesced after restart. The workspace's operations summary shows database readiness, configured sources, due schedules, task states, and expired leases.

## 6. Optional browser assistance

\`\`\`bash
python -m pip install -e ".[dev,browser]"
playwright install chromium
\`\`\`

Use the visible browser assistant only for a real candidate profile, real resume, and an application revision that you have reviewed and explicitly approved. The synthetic demo job cannot be opened because its reserved \`.test\` hostname is not a real employer portal. The assistant never clicks Submit; you must submit manually and verify the employer's confirmation before updating tracking. If a browser session is interrupted, check the employer portal before retrying.

## 7. Run the test suite

\`\`\`bash
ruff check backend tests
mypy backend
pytest
\`\`\`

Frontend checks:

\`\`\`bash
cd frontend
npm ci
npm audit
npm run typecheck
npm run build
\`\`\`

The dedicated Browser Contract CI workflow installs Chromium and runs a real-browser test against a synthetic in-memory form. No real employer portal is contacted.

## 8. Optional local API benchmark

With the API running on `127.0.0.1`, run:

```bash
vacancyx-benchmark --requests 500 --warmup 50 --concurrency 10
```

For the matching endpoint, use the synthetic candidate and search-profile IDs printed by `vacancyx-demo-seed`. The benchmark refuses non-loopback URLs and does not modify records. See [testing and performance](../quality/testing-and-performance.md) for metrics, repeat-trial guidance, and limitations.

## Removing demo data

The seed command intentionally has no automatic cleanup option because it must not risk deleting candidate data. Delete the synthetic candidate and related demo job through a deliberate local database maintenance operation only after confirming the IDs printed by the seed command.
