# Browser assistance test coverage

The browser assistance tests use synthetic candidate data and a mocked employer
portal. They do not contact real job boards or submit applications.

The mock portal workflow covers:

- Opening an allowlisted HTTPS employer page.
- Filling only recognized visible name and email fields.
- Leaving passwords and free-text questions untouched.
- Stopping all automatic filling when a CAPTCHA interruption is detected.
- Blocking a main-frame redirect to a hostname outside the exact allowlist.
- Returning an uncertain result on navigation timeout or a blocked redirect.
- Preserving the count of fields filled before a field-level browser error.
- Refusing CLI launch unless the application status is approved and the
  approval's revision and content hash match the current immutable revision.

The Playwright API boundary is mocked in deterministic backend CI; no live
employer site or downloaded browser is required. A real Chromium browser
contract test remains a release-hardening item.
