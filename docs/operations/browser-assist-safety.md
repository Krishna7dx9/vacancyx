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
- Browser errors, timeouts, blocked redirects, and partial fills are recorded
  as interrupted/uncertain browser-assistance events. They never change the
  application lifecycle to submitted. Check the employer portal before retrying.
- A missing employer confirmation is not proof of submission. Only the
  candidate can record submitted after verifying an actual confirmation.

## Current implementation

The browser runner catches failures after browser launch and returns an
interrupted result with a non-sensitive reason code and the number of fields
known to have been filled. The CLI appends an audit event without storing
exception text, candidate answers, or changing application status. A failure
to install Playwright or launch the browser remains a setup/runtime error and
does not imply a portal submission.
