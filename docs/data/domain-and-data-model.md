# Domain and data model

Logical model; physical schema, indexes and constraints are finalized in the persistence milestone.

## Entities
- Candidate: profile identity/contact, education, experience references, skills and links; owns search profiles, resumes, answer templates and applications.
- Resume: candidate-owned versioned document; safe storage key, filename metadata, media type, size, checksum and parse status.
- SearchProfile: named roles, locations, work modes, employment types, experience, compensation, graduation constraints, company filters, sources and schedule.
- JobSource: registered integration and configuration; secrets referenced through local secret provider.
- Job: canonical normalized opportunity.
- JobObservation: source ID, external ID, URL, first/last seen, verification evidence and provenance.
- JobMatch: candidate/job evaluation, rule version, eligibility, explainable score, missing data and reasons.
- Application: candidate/job intent and lifecycle, selected resume and answer revision.
- ApplicationRevision: immutable prepared content snapshot and hash.
- ApplicationBatch/BatchItem: review grouping and per-application decision/execution state.
- Approval: append-only approver, timestamp, revision hash, resume and answer revisions.
- ApplicationEvent: append-only lifecycle/audit event with actor, correlation ID and safe metadata.
- AutomationTask: durable versioned task, state, attempts, lease, heartbeat, schedule, result and error.
- SourceRun: execution record, pages/items, timing, status, rate limits and errors.

## Invariants
Candidate-owned records are candidate-scoped; resume belongs to application candidate; submission requires approval for exact revision; material edits invalidate approval; only one valid worker lease owns a task; state transitions pass through domain services; events are append-only; file names are generated storage keys; money has explicit currency and unknown differs from zero.

## Index candidates
Foreign keys; source + external job ID; canonical URL; candidate + job application policy; task state/next-run/lease; application candidate/status/updated time. Confirm with query plans and representative data.