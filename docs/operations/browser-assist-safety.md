# Browser assistance safety contract

VacancyX browser assistance is a human-supervised workflow, not an unattended
application bot.

## Required controls

- Navigate only to HTTPS employer hosts explicitly configured by the user.
  Host matching is exact; subdomains and lookalike suffixes are not implicitly
  trusted.
- Build a reviewable field-fill plan from the immutable application snapshot.
  Only ordinary text, email, and telephone fields with unambiguous labels may
  be mapped automatically.
- Unknown questions, free-text responses, dropdown choices, radio buttons,
  checkboxes, demographic questions, work-authorization answers, and legal
  attestations require human review.
- CAPTCHA, sign-in, password, OTP, and MFA screens stop assistance. VacancyX
  does not bypass or solve them.
- Filling a form is not submission. The user must inspect the completed portal
  form and explicitly submit it themselves.
- A browser crash, timeout, navigation change, or missing confirmation must
  never be reported as a successful application. Mark the outcome uncertain
  and ask the user to check the employer portal before retrying.

## Current implementation

The browser_assist service provides the URL allowlist validator, interruption
classification, and deterministic field-fill planner. It is intentionally
side-effect-free and covered by unit tests. The Playwright browser runner and
application workflow integration are subsequent milestones; do not interpret
this policy module alone as an enabled submission feature.
