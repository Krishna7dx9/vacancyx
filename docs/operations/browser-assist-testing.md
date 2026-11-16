# Browser assistance test coverage

Browser-assistance verification has two layers:

1. Deterministic mocked-portal tests in the standard backend suite. These cover
   allowlisted navigation, known-field mapping, CAPTCHA interruption,
   off-allowlist redirect blocking, navigation timeout, partial field-fill
   failure, and immutable approval checks.
2. A separate Browser Contract CI job installs Chromium and runs a real-browser
   contract test against an in-memory synthetic HTML form. It verifies that
   actual Chromium inputs receive only recognized candidate values, passwords,
   free-text answers, and legal/eligibility choices remain untouched, and no
   submit event is triggered.

Neither layer contacts a real employer or job board. The Chromium test is
headless and local-only; the interactive user workflow remains visible/headed.
