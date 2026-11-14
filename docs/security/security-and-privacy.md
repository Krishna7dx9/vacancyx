# Security and privacy

## Assets/threats
Candidate identity/contact, resumes, answers, credentials/session state, job history and submission authority. Threats include malicious job descriptions, spoofed source pages, unsafe uploads, local account access, accidental public commits, cross-profile access, credential leakage and unintended submission.

## Boundaries
Treat source HTML, descriptions, URLs and downloads as untrusted. Keep candidate data local. Secrets never enter Git/logs. Enforce ownership in services, not only UI. Restrict browser automation to configured domains and supported adapters.

## Authentication/authorization
The current candidate API is unauthenticated and intended strictly for loopback access on 127.0.0.1. Do not expose it to a LAN, reverse proxy or public network. Before remote access or multi-user support, add an explicit session/owner boundary, CSRF/Origin protection, restrictive CORS and ownership checks for every candidate-owned resource. Never trust a client-supplied candidate ID without authorization. Keep a future policy interface for owner/operator/read-only roles. If passwords exist, use maintained modern password hashing; never plaintext/reversible. Cookies HttpOnly, Secure under HTTPS, appropriate SameSite.

## Secrets/files
Never commit env files, tokens, browser profiles or cookies. Prefer OS credential storage. Redact credentials and personal data from logs. Uploads: current resume intake allowlists PDF, DOCX and UTF-8 TXT, checks signatures/content, enforces byte limits, uses generated storage keys outside public paths, strips path components from filenames, rejects DOCX traversal/macro entries, bounds archive expansion and never executes files. The current parser is local-only, bounded by file size, PDF page count and extracted character count, rejects encrypted PDFs and never executes document content. Scanned-PDF OCR is disabled. Future parsers must remain sandboxed and resource-bounded. Support delete/export.

## Browser/API safety
Never bypass CAPTCHA, MFA, rate limits or login controls. Stop on legal attestations/unexpected fields. Reconcile ambiguous submissions. Apply request limits, schema validation, output encoding, SSRF-safe URL handling, secure downloads, CSRF, session security and sensitive-operation rate limits.

## Privacy lifecycle
Minimize data; support export/deletion; define retention for logs, source payloads and artifacts. Backups are sensitive. Public fixtures are synthetic only.

## Verification
Test ownership isolation, unauthorized transitions, upload validation, secret redaction, CSRF/session, URL restrictions and approval invalidation. Run dependency/static security checks.
