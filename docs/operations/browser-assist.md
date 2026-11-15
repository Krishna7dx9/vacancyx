# Running the headed browser assistant

The browser assistant is a local, candidate-controlled helper. It opens the employer's application page in a visible Chromium window and fills only recognized name, email, phone, and location fields from the approved immutable application snapshot.

## Install

Install the optional dependency and browser:

```bash
pip install -e ".[dev,browser]"
playwright install chromium
```

## Run

First prepare the application in the workspace and approve its exact revision through the batch review workflow. Then run:

```bash
vacancyx-apply-assist \
  --candidate-id "<candidate-id>" \
  --application-id "<application-id>" \
  --allowed-host "jobs.example.com"
```

The host must exactly match the employer URL hostname. Repeat `--allowed-host` only when the exact employer page host is intentionally different from the canonical listing host. The CLI displays the application, URL, revision, and hash, then requires typing OPEN before launching the browser.

## Human control and limitations

- The CLI refuses applications that are not in approved status or whose current immutable revision has no matching approval record.
- The browser is headed (visible). The assistant never clicks Submit.
- Only ordinary known text fields are filled. Unknown questions, dropdowns, checkboxes, radio buttons, passwords, and legal declarations are untouched.
- CAPTCHA, login, password, OTP, MFA, and legal-attestation screens stop filling.
- The candidate must inspect the page and submit manually if they choose.
- The CLI does not mark the application submitted. Record a status only after checking the employer's actual confirmation; ambiguous outcomes must remain unresolved until manually verified.
- Run this command on the same machine as the local VacancyX database. A graphical desktop session is required for the headed browser.

This is a best-effort helper for supported forms, not a promise that every employer portal can be automated.