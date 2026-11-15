# Local durable worker

VacancyX uses a database-backed task queue so long-running work can survive API request timeouts and process restarts. The worker is a separate local process; it does not run automatically when FastAPI starts.

## Install and migrate

From the repository root:

```bash
python -m pip install -e ".[dev]"
alembic upgrade head
vacancyx-worker
```

Keep the computer and database available while the worker is running. Press Ctrl+C to stop the process. If interruption happens during a handler, its lease expires and the task becomes eligible for recovery; handlers must make side effects idempotent.

## Diagnostic task

The built-in `system.echo` handler verifies queue claiming, execution, and result persistence. When public boards are configured, the worker also registers `jobs.discover_source`, which fetches one configured Greenhouse or Lever board through its public JSON API and persists normalized jobs and provenance observations. It does not interact with employer application portals.

```bash
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
```

The worker should claim this task, finish it as `succeeded`, and persist the echoed payload in its result.

## Commands and settings

- `vacancyx-worker`: poll continuously.
- `vacancyx-worker --once`: claim at most one available task, then exit.
- `vacancyx-worker --worker-id my-worker`: set an explicit worker identifier.
- `vacancyx-worker --poll-interval 1.5`: override the idle polling delay.

Environment settings use the `VACANCYX_` prefix:

| Setting | Default | Purpose |
|---|---:|---|
| `WORKER_POLL_INTERVAL_SECONDS` | 2 | Idle queue polling interval |
| `WORKER_LEASE_SECONDS` | 60 | Initial claim lease duration |
| `WORKER_RETRY_BASE_DELAY_SECONDS` | 5 | First retry delay |
| `WORKER_RETRY_MAX_DELAY_SECONDS` | 300 | Maximum exponential retry delay |

Each task has a unique idempotency key and bounded attempt count. Claims use a per-claim fencing token. Discovery renews the lease between pages. Completion and failure are accepted only while the token is current and the lease is still live; a worker that wakes after its lease has expired cannot overwrite a newer attempt.

Retryable failures use bounded exponential backoff. Permanent failures move to `failed`; unknown task types move to `needs_attention` instead of being silently discarded. Expired leases are recovered on each worker poll. Cancellation revokes a running task's lease token.

## Current limits

- This is a local worker runtime, not an always-on hosted service. The computer must remain on.
- With no source configuration, only the diagnostic echo handler is registered. Configure public boards to enable the discovery handler; browser submission handlers remain a separate future integration.
- Task handlers must make external side effects idempotent using the task idempotency key. A process can crash after an external side effect but before saving success.
- No task payloads are written to application logs. Keep personal data out of diagnostic task payloads.
- The queue is SQLite-first. A multi-host worker fleet should wait until PostgreSQL and concurrency/load tests justify it.
