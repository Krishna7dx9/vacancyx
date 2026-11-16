# Local job-search workspace UI

The React workspace is a local client for the versioned FastAPI endpoints. It currently supports:

- Creating, selecting, and editing candidate profiles (display name, contact details, location, and skills).
- Creating, selecting, editing, and enabling/disabling saved search profiles.
- Configuring role titles, required skills, excluded keywords, locations, work modes, employment types, and optional minimum salary/currency.
- Searching indexed open jobs by role/company/description and location.
- Running on-demand matching and inspecting eligibility status, score components, matched terms, reasons, and unknown fields.
- Reviewing resumes, maintaining reusable candidate answers, preparing immutable application revisions, and creating revision-bound approval batches.
- Queueing public job discovery, managing recurring schedules, inspecting task outcomes and aggregate local operations diagnostics.
- Tracking application lifecycle and timeline events, and copying safe single/batch browser-assistance commands for approved applications.

Candidate and search profile edits use the existing candidate-scoped PATCH endpoints. Switching the active candidate or search profile closes any open editor so unsaved fields cannot be accidentally applied to a different record.

The UI does not store candidate details in browser local storage. It fetches them from the local API and keeps current form state in memory.

## Development

Start the backend on \`127.0.0.1:8000\`, then run the frontend development server from the frontend directory:

\`\`\`bash
npm ci
npm run dev
\`\`\`

Vite serves the UI on \`127.0.0.1:5173\` and proxies \`/api\` and \`/health\` to the local FastAPI server. The frontend uses relative API paths, so no public API host or paid service is required.

## Current limitations

Public Greenhouse and Lever board identifiers are configured through local environment settings, not yet through a source-management form in the UI. The API remains unauthenticated and is restricted to loopback access; do not expose it to an untrusted network. Browser assistance remains human-supervised and never clicks Submit.
