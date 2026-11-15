# Browser assistance test coverage

The browser assistance tests use synthetic candidate data and a mocked employer
portal. They do not contact real job boards or submit applications.

The mock portal workflow covers:

- Opening an allowlisted HTTPS employer page.
- Filling only recognized visible name and email fields.
- Leaving passwords and free-text questions untouched.
- Stopping all automatic filling when a CAPTCHA interruption is detected.
- Blocking a main-frame redirect to a hostname outside the exact allowlist.
- Refusing CLI launch unless the application status is approved and the
  approval's revision and content hash match the current immutable revision.

The Playwright runner's browser boundary is mocked in unit tests, so the
standard backend CI does not need a graphical display or a downloaded browser.
A separate browser-enabled CI environment can later add a real Chromium
contract test against an in-memory/local TLS fixture.
