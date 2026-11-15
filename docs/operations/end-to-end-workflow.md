# End-to-end workflow verification

The backend integration test in tests/test_candidate_workflow_e2e.py exercises the
candidate journey using synthetic data and an isolated in-memory SQLite
database. It makes no network calls to employer sites and never submits a real
application.

The test verifies this sequence:

1. Create a candidate profile.
2. Persist a normalized public-source job and its source observation.
3. Create candidate search criteria and run explainable matching.
4. Confirm the job is eligible under the supplied criteria.
5. Attach a synthetic reviewed resume and prepare an immutable application.
6. Create a revision-bound review batch and approve the exact content hash.
7. Transition to submitting, reject a submitted transition without confirmation
   evidence, then record submitted only with a synthetic employer confirmation.
8. Append an interview event and verify the application timeline and audit
   history.

This proves the API and persistence workflow end-to-end. It does not claim that
external job discovery, a live employer portal, or a real submission has been
tested. Browser assistance has its own deterministic mocked-portal tests.
