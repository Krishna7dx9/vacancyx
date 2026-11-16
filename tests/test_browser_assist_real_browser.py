"""Real Chromium contract test; all HTML and candidate data are synthetic."""

from __future__ import annotations

import pytest

from vacancyx.services.browser_assist import build_fill_plan
from vacancyx.services.browser_runner import (
    _FIELD_METADATA_SCRIPT,
    _FIELD_SELECTOR,
    fill_planned_fields,
    portal_fields_from_metadata,
)


def test_chromium_fills_only_known_candidate_fields() -> None:
    playwright_api = pytest.importorskip("playwright.sync_api")
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(
                """
                <!doctype html>
                <html><body>
                  <form id="application">
                    <label>Full name <input name="full_name" type="text"></label>
                    <label>Email <input name="email" type="email"></label>
                    <label>Password <input name="password" type="password"></label>
                    <label>Why this role? <textarea name="motivation"></textarea></label>
                    <label>Work authorization
                      <select name="authorization" required>
                        <option value="">Choose</option>
                        <option value="yes">Yes</option>
                      </select>
                    </label>
                    <input type="hidden" name="csrf" value="synthetic-token">
                    <button type="submit">Submit application</button>
                  </form>
                  <output id="submitted">not-submitted</output>
                  <script>
                    document.querySelector("form").addEventListener("submit", event => {
                      event.preventDefault();
                      document.querySelector("#submitted").textContent = "submitted";
                    });
                  </script>
                </body></html>
                """
            )
            locator = page.locator(_FIELD_SELECTOR)
            metadata = locator.evaluate_all(_FIELD_METADATA_SCRIPT)
            fields = portal_fields_from_metadata(metadata)
            plan = build_fill_plan(
                fields,
                {
                    "candidate": {
                        "display_name": "Synthetic Chromium Candidate",
                        "email": "chromium@example.test",
                    }
                },
            )
            filled = fill_planned_fields(locator, plan)

            assert filled == 2
            assert page.locator('input[name="full_name"]').input_value() == (
                "Synthetic Chromium Candidate"
            )
            assert page.locator('input[name="email"]').input_value() == (
                "chromium@example.test"
            )
            assert page.locator('input[name="password"]').input_value() == ""
            assert page.locator('textarea[name="motivation"]').input_value() == ""
            assert page.locator('select[name="authorization"]').input_value() == ""
            assert page.locator("#submitted").inner_text() == "not-submitted"
        finally:
            browser.close()
