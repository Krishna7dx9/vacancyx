# Workflow and reliability

## Discovery
The discovery service now resolves an enabled adapter, fetches bounded pages through the source execution gate, canonicalizes public HTTPS listing URLs, and commits each page as a short transaction. Canonical jobs are deduplicated by URL; source/external identities remain separate observations. A later page failure returns a partial outcome without rolling back earlier committed pages. The current service returns an in-memory summary; scheduler-enqueued durable SourceRun history and worker retries are still future work.

The intended full workflow remains: scheduler enqueues durable run -> worker claims lease -> adapter fetches bounded pages under rate limits -> normalize observations -> persist short transactions -> deduplicate -> record verification/freshness -> evaluate matches -> persist run summary. One source failure must not erase other source results; partial success is explicit.

## Application batch
Select eligible jobs -> choose resume/answer revision -> validate required fields -> create immutable application revision -> place in batch -> user approves/rejects/edits many items -> record approval hash -> worker revalidates approval, duplicate state and vacancy evidence -> portal adapter executes -> classify confirmed/failed/blocked/uncertain -> append event and task result.

## Task states
Queued, running, retry-wait, succeeded, partially-succeeded, failed, cancelled, needs-attention. Running tasks have lease/heartbeat. Reclaim expired lease only after checking safe resumption.

## Retry/idempotency
Retry transient network errors, selected 5xx and 429 while respecting Retry-After. Do not automatically retry validation, permission, CAPTCHA, MFA or unsupported flows. Use bounded exponential backoff with jitter and max attempts. Internal upserts/task creation use stable keys. External submission is not exactly-once: after timeout mark uncertain, reconcile portal evidence, then decide retry.

## Concurrency/recovery
Start one SQLite worker and bounded source concurrency. Keep transactions short; never hold DB transaction across network/browser wait. Test conditional updates and lease expiry. Failure injection must cover process crashes, source schema drift, browser crashes and database corruption. Disk-full should stop new writes safely. Shutdown stops claiming and persists interruption state.

## Controls
Pause/resume schedules, disable sources, stop workers, cancel safe tasks and emergency-stop new submissions. Audit control actions.
