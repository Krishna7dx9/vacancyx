# ADR-003: Database-backed durable tasks

- Status: Accepted

## Context
Discovery and browser workflows are long-running and must survive process restarts without mandatory paid infrastructure.

## Decision
Persist versioned tasks with state, attempts, next-run time, lease/heartbeat, result and error classification. Workers claim tasks transactionally. Keep queue implementation behind an interface.

## Alternatives
In-process background tasks lose work on restart. Redis/Celery adds infrastructure before need is proven. GitHub Actions is CI, not a local user task queue.

## Consequences
Local durability and recovery; SQLite limits parallel claims, so begin with one worker, short transactions and lease expiry. Revisit on measured contention/throughput.