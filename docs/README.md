# Engineering documentation

Source of truth for product scope and engineering decisions. Update docs and tests with implementation changes. Do not silently guess unresolved requirements or publish unmeasured capacity claims.

## Reading order
1. [Product requirements](product/product-requirements.md)
2. [Scope/non-goals](product/scope-and-non-goals.md)
3. [Architecture](architecture/system-architecture.md)
4. [ADRs](architecture/decisions/README.md)
5. [Domain/data model](data/domain-and-data-model.md)
6. [Reliability workflows](architecture/workflows-and-reliability.md)
7. [Security/privacy](security/security-and-privacy.md)
8. [Testing/performance](quality/testing-and-performance.md)
9. [Roadmap](roadmap/engineering-roadmap.md)
10. [Delivery workflow](operations/delivery-workflow.md)
11. [Local durable worker and scheduler](operations/local-worker.md)
12. [Public job sources](operations/public-sources.md)
13. [Local setup and synthetic demo](operations/demo-setup.md)

## Implemented API and domain slices
- [Candidate profiles](api/candidate-profiles.md)
- [Candidate answer library](api/candidate-answers.md)
- [Job-source adapters](api/job-source-adapters.md)
- [Job discovery and ingestion](api/job-discovery.md)
- [Explainable job matching](api/job-matching.md)
- [Job search and candidate search profiles](api/job-search-and-profiles.md)
- [Local workspace UI](ui/local-workspace.md)

PRD defines behavior; architecture defines boundaries; ADRs record decisions, alternatives and consequences; roadmap exit criteria define completion.