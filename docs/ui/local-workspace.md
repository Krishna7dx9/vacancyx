# Local job-search workspace UI

The React workspace is a local client for the versioned FastAPI endpoints. It currently supports:

- Creating a candidate profile with display name, skills and optional location.
- Selecting among local candidate profiles.
- Creating and selecting configurable search profiles.
- Searching indexed open jobs by role/company/description and location.
- Running on-demand matching and inspecting eligibility status, score components, matched terms, reasons and unknown fields.
- Opening the original job listing in a separate tab.

The UI does not store candidate details in browser local storage. It fetches them from the local API and keeps current form state in memory.

## Development

Start the backend on `127.0.0.1:8000`, then run the frontend development server from the frontend directory:

```bash
npm install
npm run dev
```

Vite serves the UI on `127.0.0.1:5173` and proxies `/api` and `/health` to the local FastAPI server. The frontend uses relative API paths, so no public API host or paid service is required.

## Current limitations

This is the first usable search/matching surface, not the finished VacancyX product. It does not yet configure job sources, run discovery, upload/review resumes, prepare application revisions, batch-approve, submit applications or track outcomes. Those workflows are separate roadmap milestones.

The API is intended for local use. Candidate IDs provide resource scoping but are not authentication; do not expose the backend to an untrusted network until the local authentication and deployment-security work is complete.
