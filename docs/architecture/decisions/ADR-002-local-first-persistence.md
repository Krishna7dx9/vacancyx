# ADR-002: SQLite local-first persistence

- Status: Accepted

## Context
Core must work without hosted infrastructure or subscription fees; initial use is local and single-user.

## Decision
SQLAlchemy + Alembic with SQLite initially; repository boundaries and migrations preserve a PostgreSQL path. Store files outside DB with metadata/checksums.

## Alternatives
PostgreSQL adds local service setup; JSON lacks relational integrity; hosted DB conflicts with local privacy/cost.

## Consequences
Easy local setup; SQLite write concurrency is limited, so begin with one worker and short transactions. Avoid SQLite-specific SQL in domain logic.

## Revisit
Concurrent writers/users or measured write contention exceed documented limits.