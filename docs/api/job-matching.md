# Explainable job matching

The matching engine is a pure domain component. It receives immutable candidate/job snapshots, explicit search criteria and a versioned rule set. It has no database, network, AI-service or candidate-specific defaults.

## Hard eligibility

Known facts can reject a listing:

- Job status is not open.
- An excluded keyword appears in the title, employer or description.
- A configured required skill is absent from the title and description.
- A known location, work mode or employment type conflicts with the configured allowed values.
- A known salary ceiling is below the configured floor, or the published currency conflicts with the requested currency.

Missing facts are not treated as failures. Missing location, work mode, employment type, salary range, description or candidate skills are reported in `unknown_fields`; the result becomes `needs_review` unless a separate known hard failure already makes it ineligible.

## Explainable ranking

The default versioned weights are:

| Component | Weight |
|---|---:|
| Target-title overlap | 35 |
| Candidate skill overlap | 35 |
| Location fit | 10 |
| Work-mode fit | 10 |
| Salary fit | 10 |

Only configured and available dimensions contribute. The final score is the earned weighted points divided by the total available component weight, scaled to 100. Each component returns its weight, raw score, earned points, matched terms and explanation. This makes the score reproducible and inspectable rather than a black-box prediction.

Target titles are soft ranking signals. Excluded keywords, required skills and explicit location/work-mode/employment/salary constraints are hard eligibility rules. Candidate skill overlap is measured against the job title and description using term boundaries, not arbitrary substring matches.

## Versioning and boundaries

Every result records the rule-set version. Changing weights or matching semantics should create a new version and keep curated regression fixtures. The engine does not infer graduation eligibility, sponsorship, years of experience or other facts not represented in the supplied data. Those constraints should be added only with explicit fields and tests.

No job match is persisted yet. Persisted JobMatch records, search-profile API integration, candidate-specific match explanations in the UI and re-evaluation workflows are later delivery work.
