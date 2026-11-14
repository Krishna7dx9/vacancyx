# Domain and data model

Logical model and first physical persistence slice. The initial migration establishes core relational ownership and uniqueness; later milestones add source registry, match evaluation, batch entities and richer task-attempt history.

## Persisted entities
- CandidateProfile: configurable display/contact/location, skills, education, experience and links. These values are user data, never compiled defaults.
- Resume: candidate-owned document metadata, generated local storage key, checksum, size, media type and parse state. File bytes live outside the database.
- SearchProfile: named, candidate-owned criteria stored as structured JSON; supports multiple independently configured searches.
- Job: normalized canonical opportunity, employer, role, location, work mode, employment type, salary/currency and freshness.
- JobObservation: source key, external ID, source URL, first/last seen and provenance evidence. Unique source/external identity prevents duplicate observations.
- Application: candidate/job intent, selected resume, lifecycle state and current revision. Candidate/job pair is unique.
- ApplicationRevision: immutable prepared-content snapshot, hash, revision number and resume reference.
- ApplicationApproval: append-only decision bound to the exact application revision and content hash.
- ApplicationEvent: append-only lifecycle event with timestamp, correlation ID and safe metadata.
- AutomationTask: durable queued work with idempotency key, availability, attempts, lease, result and error details.

## Planned additions
JobSource and SourceRun capture adapter configuration and provenance; JobMatch stores versioned eligibility and explainable ranking; ApplicationBatch and BatchItem support bulk review; AutomationTaskAttempt preserves each execution attempt. These are deliberately separate follow-on increments rather than premature abstractions in the first schema.

## Invariants
Candidate-owned records are candidate-scoped; resume belongs to the application candidate; submission requires approval for the exact current revision and hash; material edits invalidate approval; task claims use conditional updates and lease tokens; events are append-only; file names are generated storage keys; money has explicit currency and unknown differs from zero.

## Indexes and constraints
The initial schema enforces candidate/job application uniqueness, source/external observation uniqueness, candidate/resume checksum uniqueness, positive resume size, allowed lifecycle states and unique task idempotency keys. Query plans and additional indexes should be driven by measured workloads.
