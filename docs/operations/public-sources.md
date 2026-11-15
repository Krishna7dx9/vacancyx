# Configuring public job sources

VacancyX currently supports public Greenhouse and Lever job boards through their public JSON APIs. No account credentials, candidate profile data or employer portal access are sent to these endpoints.

## Configure boards

Add one or both JSON arrays to the backend environment file and restart the API:

```dotenv
VACANCYX_GREENHOUSE_BOARDS='[{"board_token":"company-board-token","company_name":"Company Name"}]'
VACANCYX_LEVER_SITES='[{"site_slug":"company-site-slug","company_name":"Company Name"}]'
```

- Greenhouse uses the public board token from the company's hosted Greenhouse board URL.
- Lever uses the public site slug from the company's hosted Lever postings URL.
- Each entry requires the display name used in normalized job records.
- Entries with `enabled: false` are not registered or shown in the UI.
- Source keys are generated as `greenhouse-{board_token}` and `lever-{site_slug}`.
- Duplicate source keys are rejected at settings validation time.

There are no built-in employer slugs. Configure only boards you have verified are official and public. This keeps the repository candidate-independent and avoids hardcoding a personal target-company list.

## Run discovery

1. Start the FastAPI app.
2. Open the Background Discovery panel and select one or more configured boards.
3. Queue selected sources. The API creates one idempotent task per source and returns immediately.
4. Run `vacancyx-worker` in a separate terminal.
5. Refresh task statuses in the UI. Completed tasks show counts; partial results and errors remain visible.
6. Refresh indexed jobs to see the new listings in search and matching.

The API routes are:

- `GET /api/v1/discovery/sources`
- `POST /api/v1/discovery/tasks`
- `GET /api/v1/discovery/tasks`
- `GET /api/v1/discovery/tasks/{task_id}`
- `POST /api/v1/discovery/tasks/{task_id}/cancel`

## Source controls

- All fetch URLs are HTTPS and checked against a per-provider host allowlist before requests.
- Redirects are not followed automatically.
- Requests have timeouts, per-source rate/concurrency gates, a page size cap and a maximum page count.
- Each fetched page is committed independently; retrying a task deduplicates jobs and source observations.
- Greenhouse job-board responses may not expose salary, work mode or publication time. VacancyX leaves unknown fields blank instead of guessing.
- Lever fields are normalized only when the API provides them; salary currency is retained as supplied.
- A partial result is explicitly labelled partial. Transient network/persistence failures retry with bounded backoff.
- The worker does not access candidate profile data while discovering public jobs.

## Current limits

- Source configuration is local environment configuration; there is not yet a source-management screen.
- Only public Greenhouse and Lever APIs are supported today. Workday, SmartRecruiters, Ashby, iCIMS and direct HTML sites are not implemented.
- No default company list is shipped. Add only verified official public board tokens/slugs.
- The task UI refreshes status on demand; automatic polling and recurring schedules are future work.
- This discovery workflow does not submit applications to employer portals.
