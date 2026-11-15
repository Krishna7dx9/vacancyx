# Local setup and synthetic demo

## 1. Install the backend

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## 2. Configure and migrate

```bash
cp .env.example .env
alembic upgrade head
```

VacancyX binds the API to `127.0.0.1` by default and stores its SQLite database and local files under `.vacancyx/`. Keep `.env`, `.vacancyx/`, uploaded resumes, and backups private; they are local user data.

## 3. Seed synthetic demo records

```bash
vacancyx-demo-seed
```

The command is idempotent. It creates one synthetic candidate, one clearly labeled demo job, a synthetic source observation, and a matching search profile. It prints their IDs. It does not create a fake resume or an approved application, and it never overwrites a non-demo candidate or an unexpected job that uses the reserved demo URL.

All demo identifiers use reserved test domains (`.invalid` and `.test`). The demo job is not a real vacancy and must never be applied to.

## 4. Start the API and frontend

Terminal 1, from the repository root:

```bash
uvicorn vacancyx.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open the local Vite URL shown in the terminal. The frontend proxies `/api` requests to the local API.

## 5. Optional background discovery

Configure official public Greenhouse board tokens or Lever site slugs in `.env`, then run the following in separate terminals:

```bash
vacancyx-scheduler
vacancyx-worker
```

Both processes must stay running while schedules execute. A powered-off machine does not run schedules; missed intervals are coalesced after restart.

## 6. Optional browser assistance

```bash
python -m pip install -e ".[dev,browser]"
playwright install chromium
```

Use the visible browser assistant only for a real candidate profile, real resume, and an application revision that you have reviewed and explicitly approved. The synthetic demo job cannot be opened because its reserved `.test` hostname is not a real employer portal. The assistant never clicks Submit; you must submit manually and verify the employer's confirmation before updating tracking.

## Removing demo data

The seed command intentionally has no automatic cleanup option because it must not risk deleting candidate data. Delete the synthetic candidate and related demo job through a deliberate local database maintenance operation only after confirming the IDs printed by the seed command.