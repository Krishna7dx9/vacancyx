# Local durable worker and scheduler

VacancyX uses a database-backed task queue so long-running work can survive API request timeouts and process restarts. The worker and recurring scheduler are separate local processes; neither starts automatically with FastAPI.

## Install and migrate

From the repository root:

\`\`\`bash
python -m pip install -e ".[dev]"
alembic upgrade head
\`\`\`

Start both processes in separate terminals:

\`\`\`bash
vacancyx-scheduler
vacancyx-worker
\`\`\`

The scheduler checks due schedules every 30 seconds by default and enqueues idempotent discovery tasks. The worker claims and executes those tasks. Keep the computer and database available while both processes are running. Press Ctrl+C to stop either process. If the computer is off, no schedule runs; after restart, each overdue schedule is coalesced into one run rather than replaying every missed interval.

## Operational summary

The workspace calls \`GET /api/v1/operations/summary\` to show:

- Database connectivity as observed by the API request.
- Number of configured public sources.
- Enabled and currently due schedules.
- Discovery tasks grouped by queue state.
- Running task leases that have already expired.
- Worker and scheduler process heartbeats, including running, stale, and cleanly stopped states.

This endpoint exposes aggregate counts and minimal local process metadata only; it does not return task payloads, candidate data, or idempotency keys. Worker and scheduler processes publish atomic heartbeat files under `.vacancyx/runtime/heartbeats/`. A heartbeat older than 45 seconds is reported as `stale`; a clean Ctrl+C shutdown is reported as `stopped`. A hard crash leaves a stale record until it ages out of operational relevance. Heartbeat files contain only process role, PID, host, instance label, and timestamps; they are not a substitute for OS-level process supervision. A queued task with no progress and no live worker heartbeat is a signal to start the worker. An expired task lease is recoverable when a worker polls the queue again.

## Recurring discovery schedules

Create a schedule through \`POST /api/v1/discovery/schedules\` with a name, configured source keys, and an interval in seconds (minimum 60 seconds, maximum 30 days). A new schedule is due immediately. List schedules with \`GET /api/v1/discovery/schedules\`, pause or resume with \`PATCH /api/v1/discovery/schedules/{id}\` using \`{"is_enabled": false}\` or \`true\`, and delete with \`DELETE /api/v1/discovery/schedules/{id}\`. Deleting a schedule does not cancel tasks already queued.

Schedule runs are claimed using a conditional update of the expected run number and next-run timestamp. The schedule advancement and task enqueue happen in one database transaction. Task idempotency keys include schedule ID, run number, and source key. Missing or disabled source configuration is exposed as \`source_not_configured\`; available configured sources can still run.

## Diagnostic task

The built-in \`system.echo\` handler verifies queue claiming, execution, and result persistence. When public boards are configured, the worker also registers \`jobs.discover_source\`, which fetches one configured Greenhouse or Lever board through its public JSON API and persists normalized jobs and provenance observations. It does not interact with employer application portals.

\`\`\`bash
python - <<'PY'
from vacancyx.db.session import get_session_factory
from vacancyx.repositories import TaskRepository

with get_session_factory() as session, session.begin():
    TaskRepository(session).enqueue(
        task_type="system.echo",
        payload={"message": "VacancyX worker is running"},
        idempotency_key="local-smoke:system-echo:v1",
    )
PY
\`\`\`

The worker should claim this task, finish it as \`succeeded\`, and persist the echoed payload in its result.

## Commands and settings

- \`vacancyx-worker\`: poll continuously.
- \`vacancyx-worker --once\`: claim at most one available task, then exit.
- \`vacancyx-worker --worker-id my-worker\`: set an explicit worker identifier.
- \`vacancyx-worker --poll-interval 1.5\`: override the idle polling delay.
- \`vacancyx-scheduler\`: check recurring schedules every 30 seconds.
- \`vacancyx-scheduler --once\`: enqueue due schedules once, then exit.
- \`vacancyx-scheduler --poll-interval 10\`: check schedules every 10 seconds.

Environment settings use the \`VACANCYX_\` prefix:

| Setting | Default | Purpose |
|---|---:|---|
| \`WORKER_POLL_INTERVAL_SECONDS\` | 2 | Idle queue polling interval |
| \`WORKER_LEASE_SECONDS\` | 60 | Initial claim lease duration |
| \`WORKER_RETRY_BASE_DELAY_SECONDS\` | 5 | First retry delay |
| \`WORKER_RETRY_MAX_DELAY_SECONDS\` | 300 | Maximum exponential retry delay |

Each task has a unique idempotency key and bounded attempt count. Claims use a per-claim fencing token. Discovery renews the lease between pages. Completion and failure are accepted only while the token is current and the lease is still live; a worker that wakes after its lease has expired cannot overwrite a newer attempt.

Retryable failures use bounded exponential backoff. Permanent failures move to \`failed\`; unknown task types move to \`needs_attention\` instead of being silently discarded. Expired leases are recovered on each worker poll. Cancellation revokes a running task's lease token.

## Current limits

- This is a local worker/scheduler runtime, not an always-on hosted service. The computer must remain on and both processes must be running.
- With no source configuration, only the diagnostic echo handler is registered. Configure public boards to enable the discovery handler; browser application assistance remains a separate user-driven workflow.
- Task handlers must make external side effects idempotent using the task idempotency key. A process can crash after an external side effect but before saving success.
- No task payloads are written to application logs. Keep personal data out of diagnostic task payloads.
- The queue is SQLite-first. A multi-host worker fleet should wait until PostgreSQL and concurrency/load tests justify it.
