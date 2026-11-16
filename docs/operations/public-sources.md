# Configuring public job sources

VacancyX currently supports public Greenhouse and Lever job boards through their public JSON APIs. No account credentials, candidate profile data, or employer portal access are sent to these endpoints.

## Configure boards

Source identifiers are currently configured in the backend environment file, not in a source-management screen. Add one or both JSON arrays to the repository-root \`.env\` file:

\`\`\`dotenv
VACANCYX_GREENHOUSE_BOARDS='[{"board_token":"company-board-token","company_name":"Company Name"}]'
VACANCYX_LEVER_SITES='[{"site_slug":"company-site-slug","company_name":"Company Name"}]'
\`\`\`

To configure several boards, add several objects to the corresponding JSON array. Example:

\`\`\`dotenv
VACANCYX_GREENHOUSE_BOARDS='[{"board_token":"acme","company_name":"Acme"},{"board_token":"globex","company_name":"Globex"}]'
VACANCYX_LEVER_SITES='[{"site_slug":"initech","company_name":"Initech"}]'
\`\`\`

- Greenhouse uses the public board token from the company's hosted Greenhouse board URL.
- Lever uses the public site slug from the company's hosted Lever postings URL.
- Each entry requires the display name used in normalized job records.
- Entries with \`enabled: false\` are not registered or shown in the UI.
- Source keys are generated as \`greenhouse-{board_token}\` and \`lever-{site_slug}\`.
- Duplicate source keys are rejected at settings validation time.
- Restart the API, scheduler, and worker after changing source configuration so all processes use the same settings.

There are no built-in employer slugs. Configure only boards you have verified are official and public. This keeps the repository candidate-independent and avoids hardcoding a personal target-company list.

## Run discovery

1. Add official board identifiers to \`.env\` and restart the local API.
2. Open the Background Discovery panel. The configured boards appear as selectable sources.
3. Queue selected sources. The API creates one idempotent task per source and returns immediately.
4. Run \`vacancyx-worker\` in a separate terminal.
5. Refresh task statuses in the UI. Completed tasks show counts; partial results and errors remain visible.
6. Refresh indexed jobs to see the new listings in search and matching.

For recurring discovery, create a schedule in the same panel and keep both \`vacancyx-scheduler\` and \`vacancyx-worker\` running in separate terminals. The computer must remain on; missed intervals are coalesced after restart.

The workspace's operations summary reports database readiness, configured source count, enabled/due schedules, discovery task counts, and expired leases. It intentionally does not claim that a separate worker or scheduler process is alive.

## API routes

- \`GET /api/v1/discovery/sources\`
- \`POST /api/v1/discovery/tasks\`
- \`GET /api/v1/discovery/tasks\`
- \`GET /api/v1/discovery/tasks/{task_id}\`
- \`POST /api/v1/discovery/tasks/{task_id}/cancel\`
- \`GET /api/v1/discovery/schedules\`
- \`POST /api/v1/discovery/schedules\`
- \`PATCH /api/v1/discovery/schedules/{schedule_id}\`
- \`DELETE /api/v1/discovery/schedules/{schedule_id}\`
- \`GET /api/v1/operations/summary\`

## Source controls

- All fetch URLs are HTTPS and checked against a per-provider host allowlist before requests.
- Redirects are not followed automatically.
- Requests have timeouts, per-source rate/concurrency gates, a page size cap, and a maximum page count.
- Each fetched page is committed independently; retrying a task deduplicates jobs and source observations.
- Greenhouse board responses may not expose salary, work mode, or publication time. VacancyX leaves unknown fields blank instead of guessing.
- Lever fields are normalized only when the API provides them; salary currency is retained as supplied.
- A partial result is explicitly labelled partial. Transient network/persistence failures retry with bounded backoff.
- The worker does not access candidate profile data while discovering public jobs.

## Current limits

- Source configuration is local environment configuration; there is not yet a source-management form in the UI.
- Only public Greenhouse and Lever APIs are supported today. Workday, SmartRecruiters, Ashby, iCIMS, and direct HTML sites are not implemented.
- No default company list is shipped. Add only verified official public board tokens/slugs.
- Task status refresh is user-triggered; the workspace does not poll continuously.
- The local scheduler and worker are not hosted services. They run only while their processes and the local computer are available.
- This discovery workflow does not submit applications to employer portals.
