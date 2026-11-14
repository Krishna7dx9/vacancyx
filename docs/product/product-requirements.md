# Product requirements

**Status:** Baseline for implementation planning. **Deployment:** Local-first.

## Vision
A new user can install VacancyX, create one or more profiles, upload their own resumes, configure search criteria, and operate the platform without editing source code. The product manages discovery through verified application tracking.

## Personas
- Candidate: manages profiles, resumes, search preferences, answers, and batch decisions.
- Maintainer: adds source adapters and maintains quality/security.
- Future operator: supports multi-user deployment only if later justified.

## Functional requirements
1. Candidate profiles: create/edit/archive; education, graduation date, skills, experience, links, multiple resume versions and reusable answers.
2. Search profiles: role keywords, locations, work modes, employment types, experience, compensation, graduation constraints, company filters, sources and schedules. All editable in UI/settings.
3. Discovery: pluggable source adapters, pagination, timeouts, rate limits, bounded retries, provenance and timestamps. Aggregator discovery is not proof a vacancy is open.
4. Normalization/deduplication: canonical job model, source observations, stable identifiers and review for uncertain matches.
5. Matching: hard eligibility separated from explainable relevance scoring; unknown salary/eligibility remains unknown.
6. Preparation: associate resume/answer revisions; validate fields; never fabricate candidate facts.
7. Batch review: approve/reject/edit/defer many entries in one session. Approval binds to immutable application revision; edits invalidate approval.
8. Submission: supported Playwright adapters only; pause on CAPTCHA, OTP/MFA, legal attestation, unexpected fields or ambiguity. Confirm success from portal evidence, not button click.
9. Tracking: append-only events for applied, assessment, interview, rejection, offer, withdrawal and follow-up.
10. Operations: task/source health, pause/resume, emergency stop, logs, export, backup and restore.

## Non-functional requirements
Privacy-first local data; authorization at service boundaries; safe uploads; durable recoverable tasks; transactional invariants; modular typed code; migrations; measured performance; portable setup; accessibility; auditability; zero mandatory paid services.

## Success measures
Source coverage, verified-open ratio, duplicate false-merge rate, eligibility accuracy on fixtures, API p50/p95/p99, worker throughput, queue wait, error rate, CPU/memory and recovery correctness. No throughput promise before reproducible benchmarks.