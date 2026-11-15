# Running the headed browser assistant

The browser assistant is a local, candidate-controlled helper. It opens employer application pages in a visible Chromium window and fills only recognized name, email, phone, and location fields from an approved immutable application snapshot.

## Install

```bash
pip install -e ".[dev,browser]"
playwright install chromium
```

## Assist with one approved application

Prepare the application in the workspace and approve its exact revision through batch review. Then run:

```bash
vacancyx-apply-assist \
  --candidate-id "<candidate-id>" \
  --application-id "<application-id>" \
  --allowed-host "jobs.example.com"
```

## Assist with an approved review batch

```bash
vacancyx-apply-assist \
  --candidate-id "<candidate-id>" \
  --batch-id "<batch-id>" \
  --allowed-host "jobs.example.com" \
  --limit 25
```

Batch mode opens only items whose decision is approved and whose current application revision and SHA-256 hash still match the batch item and approval record. Rejected, pending, stale, or otherwise unapproved items are skipped. Before each browser launch, the candidate must type OPEN; SKIP moves to the next item and STOP ends the batch. The default batch limit is 25, with a maximum of 100.

The host must exactly match the employer URL hostname. Repeat `--allowed-host` only for additional exact hosts the candidate intentionally trusts. Main-frame redirects to any host outside this allowlist are blocked.

## Human control and limitations

- The CLI refuses applications that are not in approved status or whose current immutable revision has no matching approval record.
- The browser is headed (visible). The assistant never clicks Submit.
- Only ordinary known text fields are filled. Unknown questions, dropdowns, checkboxes, radio buttons, passwords, and legal declarations are untouched.
- CAPTCHA, login, password, OTP, MFA, and legal-attestation screens stop filling.
- The candidate must inspect each page and submit manually if they choose.
- The CLI does not mark applications submitted. Record a status only after checking the employer's actual confirmation; ambiguous outcomes must remain unresolved until manually verified.
- Run this command on the same machine as the local VacancyX database. A graphical desktop session is required for the headed browser.

This is a best-effort helper for supported forms, not a promise that every employer portal can be automated. Batch mode saves navigation time but does not submit applications automatically.