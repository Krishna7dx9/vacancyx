# End-to-end workflow verification

The backend integration test in tests/test_candidate_workflow_e2e.py exercises the
candidate journey using synthetic data and an isolated in-memory SQLite
database. It makes no network calls to employer sites and never submits a real
application.

The test verifies this sequence:

1. Create a candidate profile.
2. Register a deterministic synthetic public-source adapter and ingest its
   normalized listing through the production discovery service.
3. Persist and verify the source observation and provenance.
4. Create candidate search criteria and run explainable matching.
5. Confirm the discovered job is eligible under the supplied criteria.
6. Attach a synthetic reviewed resume and prepare an immutable application.
7. Create a revision-bound review batch and approve the exact content hash.
8. Transition to submitting, reject a submitted transition without confirmation
   evidence, then record submitted only with a synthetic employer confirmation.
9. Append an interview event and verify the application timeline and audit
   history.

This proves the discovery-service-to-application API and persistence workflow
end-to-end using a synthetic adapter. The adapter is deterministic and does not
contact Greenhouse, Lever, or an employer. Provider-specific HTTP mapping is
covered by separate adapter tests. Browser assistance has separate mocked-portal
and real Chromium contract tests; the end-to-end API test does not claim to
exercise a browser session or a real submission.
