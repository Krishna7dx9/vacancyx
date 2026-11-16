# Configuring public job sources

VacancyX supports public Greenhouse and Lever job boards through their public JSON APIs. Discovery requests send no candidate profile, resume, or employer-portal credentials.

## Database-managed sources

Public boards can be created and managed in the Background Discovery workspace. Settings are stored in SQLite and can also be managed through the loopback-only API.

- `GET /api/v1/discovery/source-configs` lists environment and database sources, including disabled sources.
- `POST /api/v1/discovery/source-configs` adds a database-managed source.
- `PATCH /api/v1/discovery/source-configs/{source_key}` changes its display name or enabled state.
- `DELETE /api/v1/discovery/source-configs/{source_key}` removes a database-managed source.

Create a Greenhouse source:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/discovery/source-configs \
  -H "Content-Type: application/json" \
  -d '{"provider":"greenhouse","external_key":"acme","company_name":"Acme"}'
```

For Lever, use `"provider":"lever"` and the official Lever site slug as `external_key`.

The API validates provider-specific identifier characters and lengths, canonicalizes source keys, and prevents duplicates. Callers cannot supply fetch URLs or arbitrary hosts: the adapter uses only the fixed HTTPS API host for its provider. Environment-managed entries are visible but read-only through these endpoints; change or remove them in `.env`.

## Environment bootstrap

Environment variables remain supported for existing installations and initial setup. Add one or both JSON arrays to the repository-root `.env` file:

```dotenv
VACANCYX_GREENHOUSE_BOARDS='[{"board_token":"company-board-token","company_name":"Company Name"}]'
VACANCYX_LEVER_SITES='[{"site_slug":"company-site-slug","company_name":"Company Name"}]'
```

Several boards can be configured in each array:

```dotenv
VACANCYX_GREENHOUSE_BOARDS='[{"board_token":"acme","company_name":"Acme"},{"board_token":"globex","company_name":"Globex"}]'
VACANCYX_LEVER_SITES='[{"site_slug":"initech","company_name":"Initech"}]'
```

- Greenhouse uses the public board token from the company's hosted Greenhouse board URL.
- Lever uses the public site slug from the company's hosted Lever postings URL.
- Entries with `enabled: false` are not registered or shown in discovery selection.
- Source keys are generated as `greenhouse-{board_token}` and `lever-{site_slug}`.
- Duplicate source keys are rejected during settings validation.
- Database entries override environment entries with the same canonical source key.

There are no built-in employer slugs. Configure only boards verified as official and public; this keeps the repository candidate-independent.

## Run discovery

1. Add sources in the Manage public sources section or bootstrap them through `.env`.
2. Open the Background Discovery panel and select enabled boards.
3. Queue selected sources. The API creates one idempotent task per source and returns immediately.
4. Run `vacancyx-worker` in a separate terminal.
5. Refresh task statuses in the UI. Completed tasks show counts; partial results and errors remain visible.
6. Refresh indexed jobs to see the new listings in search and matching.

For recurring discovery, create a schedule in the same panel and keep both `vacancyx-scheduler` and `vacancyx-worker` running in separate terminals. The computer must remain on; missed intervals are coalesced after restart.

Database-managed source changes appear in the API immediately; restart the scheduler and worker so they reload the same source registry. Changes to environment-managed `.env` entries require restarting the API, scheduler, and worker. The operations summary reports configured sources, enabled/due schedules, task states, expired leases, and local process liveness.

## API routes

- `GET /api/v1/discovery/sources`
- `GET /api/v1/discovery/source-configs`
- `POST /api/v1/discovery/source-configs`
- `PATCH /api/v1/discovery/source-configs/{source_key}`
- `DELETE /api/v1/discovery/source-configs/{source_key}`
- `POST /api/v1/discovery/tasks`
- `GET /api/v1/discovery/tasks`
- `GET /api/v1/discovery/tasks/{task_id}`
- `POST /api/v1/discovery/tasks/{task_id}/cancel`
- `GET /api/v1/discovery/schedules`
- `POST /api/v1/discovery/schedules`
- `PATCH /api/v1/discovery/schedules/{schedule_id}`
- `DELETE /api/v1/discovery/schedules/{schedule_id}`
- `GET /api/v1/operations/summary`

## Source controls

- All fetch URLs are HTTPS and checked against a per-provider host allowlist before requests.
- Redirects are not followed automatically.
- Requests have timeouts, per-source rate/concurrency gates, a page-size cap, and a maximum page count.
- Each provider response is streamed with a 5 MiB default decompressed-body limit (configurable per adapter, capped at 20 MiB); oversized responses fail before JSON parsing.
- Each fetched page is committed independently; retrying a task deduplicates jobs and source observations.
- Greenhouse may not expose salary, work mode, or publication time. VacancyX leaves unknown fields blank instead of guessing.
- Lever fields are normalized only when the API provides them; salary currency is retained as supplied.
- Partial results are explicitly labelled. Transient network/persistence failures retry with bounded backoff.
- The worker does not access candidate profile data while discovering public jobs.

## Current limits

- Only public Greenhouse and Lever APIs are supported. Workday, SmartRecruiters, Ashby, iCIMS, and direct HTML sites are not implemented.
- No default company list is shipped. Add only verified official public board tokens/slugs.
- Task status refresh is user-triggered; the workspace does not poll continuously.
- The local scheduler and worker are not hosted services. They run only while their processes and the local computer are available.
- This discovery workflow does not submit applications to employer portals.
