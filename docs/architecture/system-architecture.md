# System architecture

## Style
Modular monolith with separately runnable background workers. A single backend keeps local deployment and transactions simple; ports/adapters isolate integrations. No premature microservices.

## Components
- React/TypeScript presentation; no business rules in UI.
- FastAPI API: schemas, auth/session boundary, authorization, pagination, error mapping.
- Application services: use-case orchestration and transaction boundaries.
- Domain: candidate, search profile, job, match, application, approval, task and event invariants.
- Ports: job source, application portal, parser, notification, clock and repository.
- Adapters: source clients, Playwright site adapters, filesystem, SQLite, scheduler.
- Workers: task claims, leases, heartbeats, retries and results.
- Observability: structured logs, task history, health and metrics.

## Dependency rules
Domain imports no FastAPI/SQLAlchemy/Playwright/vendor SDK. Routes call services, not workflows. Services depend on domain and ports. Infrastructure implements ports. Source parsing stays in adapters. Browser adapters report observations through services. Frontend is not business source of truth.

## Runtime
Frontend, FastAPI, one worker initially, SQLite, managed local file directory and scheduler that enqueues durable tasks. Long-running work never runs inside HTTP requests; return task IDs and expose status.

## Request path
HTTP limits -> session/auth -> ownership authorization -> schema validation -> service -> domain invariants -> repository transaction -> response and safe logs.

## Scale path
Start SQLite + one worker + bounded source concurrency. Move to PostgreSQL if concurrent writers/users or measured contention require it. Add a broker only when durable DB task claims are insufficient. Horizontal scale requires shared storage, distributed leases, secrets management and explicit tenant authorization.

## Capacity evidence
Benchmark API RPS separately from source-fetch and browser throughput. Record commit, hardware, OS, runtime, dataset, workload, concurrency, duration, p50/p95/p99, errors, CPU, memory and DB utilization. Never claim capacity without reproducible results.