# Security and privacy

## Assets/threats
Candidate identity/contact, resumes, answers, credentials/session state, job history and submission authority. Threats include malicious job descriptions, spoofed source pages, unsafe uploads, local account access, accidental public commits, cross-profile access, credential leakage and unintended submission.

## Boundaries
Treat source HTML, descriptions, URLs and downloads as untrusted. Keep candidate data local. Secrets never enter Git/logs. Enforce ownership in services, not only UI. Restrict browser automation to configured domains and supported adapters.

## Authentication/authorization
Initial local deployment still needs a deliberate session boundary. Protect cookie-authenticated changes against CSRF; avoid permissive CORS. Check ownership for every candidate-owned resource; never trust client-supplied candidate ID without authorization. Keep a future policy interface for owner/operator/read-only roles. If passwords exist, use maintained modern password hashing; never plaintext/reversible. Cookies HttpOnly, Secure under HTTPS, appropriate SameSite.

## Secrets/files
Never commit env files, tokens, browser profiles or cookies. Prefer OS credential storage. Redact credentials and personal data from logs. Uploads: allowlist and signature-check types, size limits, generated storage keys, outside public paths, path traversal/symlink protection, bounded parsing, never execute files. Support delete/export.

## Browser/API safety
Never bypass CAPTCHA, MFA, rate limits or login controls. Stop on legal attestations/unexpected fields. Reconcile ambiguous submissions. Apply request limits, schema validation, output encoding, SSRF-safe URL handling, secure downloads, CSRF, session security and sensitive-operation rate limits.

## Privacy lifecycle
Minimize data; support export/deletion; define retention for logs, source payloads and artifacts. Backups are sensitive. Public fixtures are synthetic only.

## Verification
Test ownership isolation, unauthorized transitions, upload validation, secret redaction, CSRF/session, URL restrictions and approval invalidation. Run dependency/static security checks.