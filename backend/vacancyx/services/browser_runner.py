"""Headed Playwright runner for explicitly supervised application assistance."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from vacancyx.services.browser_assist import (
    FillPlan,
    PortalField,
    build_fill_plan,
    detect_manual_interruption,
    validate_portal_url,
)

_FIELD_SELECTOR = (
    "input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]), "
    "textarea, select"
)
_FIELD_METADATA_SCRIPT = """elements => elements.map((element, index) => {
  const labels = element.labels
    ? Array.from(element.labels).map(label => label.innerText || label.textContent || "").join(" ")
    : "";
  return {
    index,
    label: labels || element.getAttribute("aria-label")
      || element.getAttribute("placeholder") || element.getAttribute("name") || "",
    field_type: element.tagName.toLowerCase() === "textarea"
      ? "textarea"
      : element.tagName.toLowerCase() === "select"
        ? "select"
        : (element.getAttribute("type") || "text").toLowerCase(),
    required: Boolean(element.required)
  };
})"""


@dataclass(frozen=True)
class BrowserAssistResult:
    """Non-submission result from one visible, human-supervised browser session."""

    page_url: str
    interruption_codes: tuple[str, ...]
    filled_field_count: int
    skipped_field_count: int
    manual_review_reasons: tuple[str, ...]


class BrowserAssistExecutionError(RuntimeError):
    """Field fill failed after a known number of controls had already been filled."""

    def __init__(self, filled_field_count: int) -> None:
        super().__init__("A browser field could not be filled safely.")
        self.filled_field_count = filled_field_count


def portal_fields_from_metadata(metadata: list[dict[str, Any]]) -> list[PortalField]:
    """Convert browser metadata into the narrow, deterministic policy contract."""
    return [
        PortalField(
            name=str(item["index"]),
            label=str(item.get("label", "")),
            field_type=str(item.get("field_type", "text")),
            required=bool(item.get("required", False)),
        )
        for item in metadata
    ]


def fill_planned_fields(locator: Any, plan: FillPlan) -> int:
    """Fill only planned visible fields; do not click, select, or submit controls."""
    filled = 0
    for field in plan.fields:
        try:
            control = locator.nth(int(field.field_name))
            if not control.is_visible():
                continue
            control.fill(field.value)
            filled += 1
        except Exception as error:
            raise BrowserAssistExecutionError(filled) from error
    return filled


def run_browser_assist(
    url: str,
    candidate_snapshot: dict[str, Any],
    allowed_hosts: set[str],
) -> BrowserAssistResult:
    """Open a visible browser, fill safe known fields, then hand control to the user.

    Browser runtime errors after launch are returned as an interrupted, uncertain
    session. The caller can audit the interruption without ever treating it as a
    successful application submission.
    """
    safe_url = validate_portal_url(url, allowed_hosts)
    try:
        playwright_api = import_module("playwright.sync_api")
    except ImportError as error:
        raise RuntimeError(
            "Browser assistance requires the optional browser extra: "
            "install vacancyx[browser] and run playwright install chromium."
        ) from error

    result: BrowserAssistResult | None = None
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page: Any = None
        filled_count = 0
        skipped_count = 0
        try:
            page = browser.new_page()

            def guard_main_frame_navigation(route: Any) -> None:
                request = route.request
                if request.is_navigation_request() and request.frame == page.main_frame:
                    try:
                        validate_portal_url(request.url, allowed_hosts)
                    except ValueError:
                        route.abort()
                        return
                route.continue_()

            page.route("**/*", guard_main_frame_navigation)
            page.goto(safe_url, wait_until="domcontentloaded", timeout=30_000)
            # Check the final URL too; a redirected employer URL must remain allowlisted.
            validate_portal_url(page.url, allowed_hosts)
            body_text = page.locator("body").inner_text(timeout=10_000)
            interruptions = detect_manual_interruption(body_text)
            if interruptions:
                result = BrowserAssistResult(
                    page_url=page.url,
                    interruption_codes=interruptions,
                    filled_field_count=0,
                    skipped_field_count=0,
                    manual_review_reasons=("manual_intervention_required",),
                )
                print(
                    "VacancyX stopped automatic assistance: "
                    + ", ".join(interruptions)
                )
            else:
                locator = page.locator(_FIELD_SELECTOR)
                metadata = locator.evaluate_all(_FIELD_METADATA_SCRIPT)
                fields = portal_fields_from_metadata(metadata)
                plan = build_fill_plan(fields, candidate_snapshot)
                skipped_count = len(plan.skipped_fields)
                filled_count = fill_planned_fields(locator, plan)
                result = BrowserAssistResult(
                    page_url=page.url,
                    interruption_codes=(),
                    filled_field_count=filled_count,
                    skipped_field_count=skipped_count,
                    manual_review_reasons=plan.manual_review_reasons,
                )
                print(
                    f"Filled {filled_count} recognized fields; "
                    f"left {skipped_count} fields untouched."
                )
                if plan.manual_review_reasons:
                    print("Manual review required: " + ", ".join(plan.manual_review_reasons))
            print(
                "Review the visible employer page. VacancyX will not click Submit. "
                "If you choose to apply, submit manually on the employer site. "
                "Close the browser when finished, then press Enter here."
            )
            input()
        except Exception as error:
            if isinstance(error, BrowserAssistExecutionError):
                filled_count = error.filled_field_count
            result = BrowserAssistResult(
                page_url=getattr(page, "url", safe_url),
                interruption_codes=("browser_session_uncertain",),
                filled_field_count=filled_count,
                skipped_field_count=skipped_count,
                manual_review_reasons=("check_employer_portal_before_retry",),
            )
            print(
                "Browser assistance was interrupted. The application outcome is uncertain. "
                "Check the employer portal before retrying; VacancyX did not submit it."
            )
        finally:
            browser.close()

    if result is None:
        raise RuntimeError("The browser assistance session did not produce a result.")
    return result
