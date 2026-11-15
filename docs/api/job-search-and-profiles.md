# Job search and candidate search-profile API

The API exposes normalized jobs and candidate-owned search criteria over the local database. All endpoints are versioned under `/api/v1`.

## Job search

- `GET /jobs`: bounded, filterable job list.
- `GET /jobs/{job_id}`: one normalized job.

Supported filters: `query` (title, employer or description), `location`, `work_mode`, `employment_type`, `status` (defaults to open; use all to include every status), `minimum_salary` plus `salary_currency`, and `include_unknown_salary`. Pagination is limited to 1–100 items.

Salary-floor searches require an explicit three-letter currency. By default, jobs with unknown salary are retained so missing pay data is not silently treated as below the floor. Known salaries in another currency are excluded. Set `include_unknown_salary=false` to require a known salary.

## Candidate-owned search profiles

- `POST /candidates/{candidate_id}/search-profiles`: create a profile.
- `GET /candidates/{candidate_id}/search-profiles`: list profiles.
- `GET /candidates/{candidate_id}/search-profiles/{profile_id}`: read one profile.
- `PATCH /candidates/{candidate_id}/search-profiles/{profile_id}`: partially update name, criteria or enablement.
- `POST /candidates/{candidate_id}/search-profiles/{profile_id}/matches`: evaluate and rank recent open jobs.

Profile criteria are validated by the matching domain schema before persistence. All reads and writes scope profile IDs by candidate ID; an ID belonging to another candidate is returned as not found. Profiles can be disabled without deleting their criteria.

## Match evaluation response

The matches endpoint evaluates up to 500 most recently verified open jobs, then orders eligible results first, needs-review results second and ineligible results last; score breaks ties. The response reports the number of open jobs available, how many were evaluated, whether the 500-job cap truncated the evaluation, and a bounded page of jobs with full matching explanations.

Evaluation is currently on demand and not persisted. Re-evaluation uses the current rule-set version. Durable JobMatch snapshots, historical rule versions, asynchronous evaluation tasks and UI controls remain later increments.

## Local privacy boundary

These APIs are intended for the local VacancyX workspace. Candidate profile routes are candidate-scoped but there is not yet a multi-user authentication/authorization system. Do not expose the API to an untrusted network until the local auth boundary and deployment security milestone are implemented.
