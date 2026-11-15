"""Deterministic mocked-portal workflow tests for browser assistance."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from vacancyx.services import browser_runner


class FakeControl:
    def __init__(self) -> None:
        self.value: str | None = None

    def is_visible(self) -> bool:
        return True

    def fill(self, value: str) -> None:
        self.value = value


class FakeBody:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self, timeout: int) -> str:
        return self.text


class FakeLocator:
    def __init__(self, metadata: list[dict[str, Any]], body: FakeBody | None = None) -> None:
        self.metadata = metadata
        self.body = body
        self.controls = [FakeControl() for _ in metadata]

    def inner_text(self, timeout: int) -> str:
        if self.body is None:
            raise AssertionError("Body text requested from a form locator.")
        return self.body.inner_text(timeout)

    def evaluate_all(self, script: str) -> list[dict[str, Any]]:
        return self.metadata

    def nth(self, index: int) -> FakeControl:
        return self.controls[index]


class FakeRequest:
    def __init__(self, url: str, frame: object) -> None:
        self.url = url
        self.frame = frame

    def is_navigation_request(self) -> bool:
        return True


class FakeRoute:
    def __init__(self, request: FakeRequest) -> None:
        self.request = request
        self.aborted = False
        self.continued = False

    def abort(self) -> None:
        self.aborted = True

    def continue_(self) -> None:
        self.continued = True


class FakePage:
    def __init__(
        self,
        *,
        body_text: str = "Welcome to the application",
        redirect_url: str | None = None,
    ) -> None:
        self.main_frame = object()
        self.url = "about:blank"
        self.body_text = body_text
        self.redirect_url = redirect_url
        self.route_handler: Callable[[Any], None] | None = None
        self.routes: list[FakeRoute] = []
        self.form_locator = FakeLocator(
            [
                {"index": 0, "label": "Full name", "field_type": "text", "required": True},
                {"index": 1, "label": "Email", "field_type": "email", "required": True},
                {"index": 2, "label": "Password", "field_type": "password", "required": True},
                {"index": 3, "label": "Why this role?", "field_type": "textarea"},
            ]
        )

    def route(self, pattern: str, handler: Callable[[Any], None]) -> None:
        self.route_handler = handler

    def _navigate(self, url: str) -> FakeRoute:
        assert self.route_handler is not None
        route = FakeRoute(FakeRequest(url, self.main_frame))
        self.routes.append(route)
        self.route_handler(route)
        return route

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        initial = self._navigate(url)
        if initial.aborted:
            raise RuntimeError("Initial navigation was blocked.")
        self.url = url
        if self.redirect_url is not None:
            redirect = self._navigate(self.redirect_url)
            if redirect.aborted:
                raise RuntimeError("Off-allowlist redirect was blocked.")
            self.url = self.redirect_url

    def locator(self, selector: str) -> FakeLocator:
        if selector == "body":
            return FakeLocator([], FakeBody(self.body_text))
        return self.form_locator


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.closed = False

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class FakePlaywrightContext:
    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = SimpleNamespace(launch=self.launch)
        self.browser = browser
        self.launch_arguments: dict[str, Any] = {}

    def launch(self, **kwargs: Any) -> FakeBrowser:
        self.launch_arguments = kwargs
        return self.browser


class FakePlaywrightManager:
    def __init__(self, playwright: FakePlaywrightContext) -> None:
        self.playwright = playwright

    def __enter__(self) -> FakePlaywrightContext:
        return self.playwright

    def __exit__(self, *args: object) -> None:
        return None


def _install_fake_playwright(
    monkeypatch: pytest.MonkeyPatch, page: FakePage
) -> FakeBrowser:
    browser = FakeBrowser(page)
    playwright = FakePlaywrightContext(browser)
    module = SimpleNamespace(sync_playwright=lambda: FakePlaywrightManager(playwright))
    monkeypatch.setattr(browser_runner, "import_module", lambda _name: module)
    monkeypatch.setattr("builtins.input", lambda: "")
    return browser


def test_mock_employer_portal_fills_known_fields_and_leaves_unknown_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = FakePage()
    browser = _install_fake_playwright(monkeypatch, page)

    result = browser_runner.run_browser_assist(
        "https://jobs.example.test/apply",
        {
            "candidate": {
                "display_name": "Synthetic Candidate",
                "email": "candidate@example.test",
            }
        },
        {"jobs.example.test"},
    )

    assert browser.closed
    assert result.filled_field_count == 2
    assert result.skipped_field_count == 2
    assert result.interruption_codes == ()
    assert page.form_locator.controls[0].value == "Synthetic Candidate"
    assert page.form_locator.controls[1].value == "candidate@example.test"
    assert page.form_locator.controls[2].value is None
    assert page.form_locator.controls[3].value is None
    assert all(route.continued for route in page.routes)


def test_mock_employer_portal_stops_on_captcha_without_filling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = FakePage(body_text="Please complete the reCAPTCHA to continue")
    browser = _install_fake_playwright(monkeypatch, page)

    result = browser_runner.run_browser_assist(
        "https://jobs.example.test/apply",
        {"candidate": {"display_name": "Synthetic Candidate"}},
        {"jobs.example.test"},
    )

    assert browser.closed
    assert result.interruption_codes == ("captcha_required",)
    assert result.filled_field_count == 0
    assert all(control.value is None for control in page.form_locator.controls)


def test_mock_employer_portal_blocks_off_allowlist_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = FakePage(redirect_url="https://evil.example.test/collect")
    browser = _install_fake_playwright(monkeypatch, page)

    with pytest.raises(RuntimeError, match="redirect was blocked"):
        browser_runner.run_browser_assist(
            "https://jobs.example.test/apply",
            {"candidate": {"display_name": "Synthetic Candidate"}},
            {"jobs.example.test"},
        )

    assert browser.closed
    assert page.routes[0].continued
    assert page.routes[1].aborted
    assert all(control.value is None for control in page.form_locator.controls)
