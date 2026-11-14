# ADR-005: Source adapters with provenance

- Status: Accepted

## Context
Sources differ in authentication, pagination, schema, rate limits, terms and freshness.

## Decision
Define adapter contract with capabilities, configuration, pagination, rate policy and timeout. Map results into canonical observations with provenance and verification evidence.

## Alternatives
One scraper creates tight coupling. Aggregators are not authoritative. Unrestricted scraping can violate terms/access controls.

## Consequences
New sources do not require matching-engine changes. Every adapter needs contract/fixture tests. Coverage is incomplete and reported honestly.