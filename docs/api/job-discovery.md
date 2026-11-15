# Job discovery and ingestion

The discovery service consumes one configured adapter at a time. It is intentionally independent of candidate matching: it records source facts and provenance first; candidate-specific eligibility and ranking happen later.

## Current service behavior

Use `JobDiscoveryService(session, registry)` and await `discover_source(source_key)`. Each run:

1. Resolves an enabled adapter and its bounded source configuration.
2. Requests no more than the configured page count and page size, through the source execution gate.
3. Rejects pages larger than requested and detects repeated continuation cursors.
4. Validates and canonicalizes every listing URL before writing the page.
5. Upserts a canonical Job and a source/external-ID JobObservation in one short transaction per page.
6. Returns aggregate counts, truncation state and safe error codes.

The database transaction is never held while waiting for a source network operation. A page is atomic: if a listing in that page is invalid, none of that page is persisted. Earlier successful pages remain committed if a later page times out or fails.

## Identity and deduplication

Canonical identity is based on the HTTPS listing URL, not a guessed title/company match. Canonicalization lowercases and IDNA-normalizes the hostname, removes the default port, fragment and common tracking parameters, sorts remaining query parameters, and removes a trailing path slash. It does not merge different URLs merely because their titles or employers look similar.

A Job is shared by canonical URL. Each source/external-ID pair has its own JobObservation, so multiple sources can corroborate one opportunity without creating duplicate canonical jobs. Re-seeing an observation updates its latest source URL, evidence and last-seen time while preserving first-seen time.

## Partial outcomes

- `completed`: all available pages were ingested.
- `partial`: one or more pages were committed before a source error, a pagination cycle or the page cap.
- `failed`: no page could be committed before an error.

Error codes intentionally avoid copying exception text, URLs or source payloads into summaries. The service does not yet persist a durable SourceRun; that is part of the later worker/task orchestration work.

## Current boundaries

This is an ingestion service, not a live job-board integration or scheduler. No real source is enabled by default. Adapters still require individual terms/access review, fixture coverage and a policy-compliant implementation. Durable run history, retry scheduling, candidate matching and the UI are separate roadmap increments.
