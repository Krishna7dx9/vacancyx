# ADR-001: Modular monolith first

- Status: Accepted

## Context
Initial risks are domain correctness, external integration variability, durable workflows and local reliability—not independent service scaling.

## Decision
One backend codebase with domain-focused modules and separate API/worker entry points. Enforce dependency rules and isolate integrations behind ports/adapters.

## Alternatives
Microservices add deployment, networking, distributed tracing and transaction complexity without evidence. An unstructured monolith creates coupling and weak testability.

## Consequences
Simple local setup and transactions; clear boundaries; workers can run separately; extraction remains possible if measured scaling/team needs justify it.

## Revisit
Independent deployment/scaling requirements or measured resource contention.