# Job-source adapter framework

VacancyX isolates each job board or employer feed behind a small asynchronous adapter contract. Source-specific authentication, pagination tokens and parsing remain inside the adapter; adapters return normalized `SourceListing` values. The discovery and matching layers must not import source-specific code.

## Adapter contract

An adapter exposes:

- `source_key`: stable lowercase identifier matching its `SourceConfig`.
- `capabilities`: truthful declarations about pagination and optional listing fields.
- `fetch_page(cursor, page_size)`: one bounded page and an opaque continuation cursor.

The framework includes a fake adapter contract test. A source is not considered production-ready merely because it implements the protocol: it also needs fixture/contract tests, terms and access review, pagination behavior, freshness evidence and failure handling.

## Source configuration

`SourceConfig` contains source-level controls, not candidate preferences:

- Explicit HTTPS host allowlist.
- Enable/disable switch.
- Request rate and concurrency ceilings.
- Request timeout.
- Maximum pages per run and page size.
- Descriptive user-agent.

Configuration is validated and rejects unknown fields, invalid limits and malformed host entries. Candidate search preferences belong to candidate/search-profile records, not source configuration.

## Request policy

Call `validate_source_url` before issuing a request. It requires HTTPS, rejects credentials, non-default ports, IP literals, localhost/single-label hosts, and hosts outside the exact or subdomain allowlist. Use `SourceExecutionGate` around each network operation to apply the configured timeout, concurrency bound and per-source minimum request interval.

The framework does not bypass login walls, CAPTCHA, MFA, robots directives, terms, or rate limits. A source that requires prohibited access is unsupported and should be disabled or represented as a manual link.

## Deliberate boundaries

- No live third-party source is enabled by default.
- No scraping implementation or source credentials are bundled.
- Pagination orchestration, observation persistence, canonical identity and deduplication are the next discovery milestone.
- Retry decisions and `Retry-After` handling belong to the durable discovery workflow, not an unbounded retry loop inside an adapter.
