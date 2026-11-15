# Candidate answer library API

Base path: /api/v1

Candidate answers are reusable, candidate-owned responses to common application and interview questions. The library is local data, not bundled sample content or hardcoded candidate facts.

| Method | Path | Behavior |
|---|---|---|
| POST | /candidates/{candidate_id}/answers | Create an answer and immutable revision 1 |
| GET | /candidates/{candidate_id}/answers | Search/list with category, active-only and bounded pagination filters |
| PATCH | /candidates/{candidate_id}/answers/{answer_id} | Partially update an answer |
| GET | /candidates/{candidate_id}/answers/{answer_id}/revisions | Read immutable historical snapshots |

Question identity is normalized using Unicode case folding and whitespace normalization before SHA-256 hashing. A database uniqueness constraint prevents duplicate normalized questions for the same candidate. A collision returns HTTP 409. The same question may exist for different candidates.

Content changes (question, answer text, category or tags) append a new immutable snapshot and increment current_revision. Activation changes do not create content revisions. PATCH only changes supplied fields; omitted tags/category/state remain untouched. Unknown fields, blank text and explicit null question/answer values are rejected.

All reads and mutations are scoped by candidate_id. An answer belonging to another candidate is indistinguishable from a missing answer and returns 404. Historical revisions are read-only through this API. Candidate deletion cascades to the candidate's answer library and its snapshots.

This is a local single-user application boundary, not multi-user authentication. Keep the API bound to loopback until the security milestone implements an explicit authenticated owner/session boundary.
