# Local VacancyX security review

**Review date:** 2026-11-16  
**Review type:** focused source-level review of the local MVP security boundaries  
**Review status:** targeted findings fixed; target-computer sign-off and independent penetration testing remain outstanding

This is an engineering review of selected high-risk paths, not an external audit, penetration test, or certification.

## Scope reviewed

- Runtime network binding and unauthenticated API boundary.
- Public Greenhouse/Lever URL policy, response handling, normalized listing links, and UI rendering.
- Resume upload validation, local storage, and bounded parsing.
- Browser-assisted application safety and approval revalidation.
- SQLite backup creation and verification.

## Findings and remediation

### Public job-source response resource bounds

**Finding:** Provider adapters originally buffered complete HTTP responses before parsing. Timeouts and page-count limits did not bound memory consumed by one response.

**Remediation:** PR #53 introduced streamed response reads with a 5 MiB default body limit and a hard 20 MiB configuration ceiling. PR #55 requests identity encoding, rejects compressed responses, and reads raw chunks so decompression cannot expand a payload before the byte cap is checked.

**Verification:** Adapter tests cover oversized Greenhouse and Lever responses, declared-length overflow, chunked overflow, and compressed response rejection.

### Untrusted job listing URLs

**Finding:** A source provider controls the listing URL returned in its payload. The workspace renders this value as an external anchor; non-HTTPS or executable schemes must not be trusted.

**Remediation:** PR #54 validates normalized listing URLs as absolute HTTPS URLs and rejects credentials, local/IP-literal hosts, non-default ports, whitespace/control characters, and backslashes. The React workspace applies a second URL check and uses noopener/noreferrer.

**Verification:** Regression tests cover javascript:, data:, file:, HTTP, credentials, localhost, IP literals, non-default ports, and backslash confusion.

### Python and frontend dependency audits

**Finding:** The first Python dependency audit identified vulnerable versions admitted by the previous development/build constraints: pytest 8.4.2 and setuptools 79.0.1 (PYSEC-2026-1845, PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w).

**Remediation:** PR #84 raised the minimum pytest version to 9.0.3 and the setuptools build-system version to 84.1.0. Backend CI now runs `pip-audit --skip-editable` against the resolved environment; Frontend CI runs `npm audit`. CI also uses read-only repository permissions for frontend builds. PR #85 upgraded checkout/setup-python/setup-node actions to v7.

**Verification:** Backend dependency audit, lint, strict mypy, and pytest passed on PR #84 head `736c92ee06a84a1ede4169bc3bce58d5deb69bef`. Browser Contract CI and Fresh Machine Release Verification also passed on that revision. The consolidated GitHub Actions v7 upgrade passed Backend CI, Frontend CI, Browser Contract CI, and Fresh Machine Release Verification on PR #85 head `13d85463c5bc73d332ee77e70484473921d5cc31`.

**Residual requirement:** Re-run all release checks on the final tagged release commit; dependency databases and advisories change over time.

### Unauthenticated API

**Finding:** Candidate profile, resume metadata, application, and workflow endpoints do not have user authentication or multi-user authorization.

**Mitigation:** Runtime configuration accepts only localhost or loopback IP addresses. README and setup documentation prohibit LAN binding, tunnels, reverse proxies, and public exposure.

**Residual risk:** Local processes and users with access to the same operating-system account can access candidate data. Do not expose the API remotely. Before remote or multi-user use, implement and review authentication, session security, CSRF/Origin protections, authorization/ownership enforcement, restrictive CORS, and rate limits.

### Resume upload and parsing

**Controls reviewed:** Allowlisted PDF/DOCX/TXT extensions, generated storage names, byte limits while staging, signature/content validation, UTF-8 validation, DOCX archive entry and uncompressed-size bounds, path traversal and macro checks, PDF encryption/page limits, and extracted-character limits. Resume content is stored outside the web root and is not executed.

**Residual risk:** The parser is a local in-process parser, not a separate sandbox. Keep dependencies updated and treat resumes as sensitive untrusted documents.

### Browser-assisted applications

**Controls reviewed:** Explicit employer-host allowlist, HTTPS-only portal validation, main-frame redirect checks, visible browser, immutable current-revision approval revalidation, ordinary-field-only fill plan, manual interruption detection, and no Submit click. CAPTCHA, MFA, login, legal attestations, unsupported controls, and uncertain outcomes require human handling.

**Residual risk:** A real employer portal and its scripts are third-party code. The user must supervise every session, inspect filled data, and submit manually. Browser assistance does not prove an application was submitted.

### Local filesystem permissions

**Finding:** SQLite creates database files using the process umask, which is commonly permissive enough to make a new database readable by other local OS accounts. Resume files were created with restrictive temporary-file permissions, but their containing directory could remain broadly listable.

**Remediation:** The SQLite engine now restricts file-backed database permissions to owner read/write (0600) on POSIX systems whenever a connection is opened. Resume storage uses a dedicated owner-only directory (0700); staged resume files retain owner-only permissions (0600). SQLite backups are created through owner-only temporary files (0600) before atomic publication.

**Verification:** POSIX-only regression tests inspect the resulting database, resume directory/file, and backup modes. These checks are skipped on non-POSIX platforms, where filesystem ACLs must be managed using the operating system's security controls.

**Additional path control:** Resume uploads reject a symlinked `resumes` directory and verify the resolved destination remains inside the configured storage root, preventing an existing local symlink from redirecting uploaded documents outside private storage. A local attacker with the same OS account can still modify the storage tree concurrently.\n\n**Residual risk:** These mode bits do not encrypt data, protect against the same OS account, or guarantee Windows ACL configuration. Keep the database, resume storage, browser state, and backup paths on a private local account and configure Windows folder permissions where applicable.

### Backup and recovery

**Controls reviewed:** SQLite online backup API, integrity check before atomic publication, destination/source separation, read-only backup verification, foreign-key check, and explicit warning that backup files contain candidate data.

**Residual risk:** Backup files are not encrypted or automatically retained. Protect them with operating-system permissions and store them outside the repository. Perform the documented restore drill against a disposable copy before relying on backups.

## Automated evidence

The relevant regression suites run through Backend CI, Frontend CI, Browser Contract CI, and Fresh Machine Release Verification. The latter verifies a clean dependency install, migrations, repeatable synthetic seed, API readiness/OpenAPI, and frontend production build.

Automated CI does not replace a target-computer recovery drill, a real user walkthrough, or an independent security assessment.

## Remaining sign-off

- [ ] Confirm Backend CI pip-audit and Frontend CI npm audit pass on the exact release commit; reassess any newly reported advisories.
- [ ] Complete the target-computer install and synthetic product walkthrough.
- [ ] Complete a backup restore drill using a disposable copy.
- [ ] Confirm local filesystem permissions for database, resumes, browser state, and backups.
- [ ] Obtain an independent security review before changing the loopback-only boundary.

**Decision:** Suitable for continued local MVP testing under the documented loopback-only boundary. Not approved for remote access, multi-user deployment, or public hosting.
