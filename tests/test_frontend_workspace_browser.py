"""Real Chromium smoke test for the React workspace against a deterministic API."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _wait_for_vite(process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("Vite exited before becoming ready.")
        try:
            with urllib.request.urlopen("http://127.0.0.1:5173", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise AssertionError("Vite did not become ready within 30 seconds.")


def _api_response(route: Any) -> None:
    request = route.request
    path = request.url.split("/api/v1", 1)[-1]
    method = request.method
    payload = json.loads(request.post_data) if request.post_data else {}

    if path == "/candidates" and method == "GET":
        body: Any = []
    elif path == "/candidates" and method == "POST":
        body = {
            "id": "candidate-smoke-1",
            "display_name": payload["display_name"],
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "location": payload.get("location"),
            "skills": payload.get("skills", []),
            "is_active": True,
        }
    elif path == "/candidates/candidate-smoke-1/search-profiles" and method == "GET":
        body = []
    elif path == "/candidates/candidate-smoke-1/search-profiles" and method == "POST":
        body = {
            "id": "profile-smoke-1",
            "candidate_id": "candidate-smoke-1",
            "name": payload["name"],
            "criteria": payload["criteria"],
            "is_enabled": True,
        }
    elif path.startswith("/candidates/candidate-smoke-1/search-profiles/profile-smoke-1/matches"):
        body = {
            "profile_id": "profile-smoke-1",
            "total_jobs_available": 1,
            "evaluated_count": 1,
            "truncated": False,
            "items": [{
                "job": _job(),
                "match": {
                    "status": "eligible",
                    "score": 91.5,
                    "rule_version": "1.0",
                    "reasons": ["Required skills matched"],
                    "unknown_fields": [],
                    "components": [{
                        "name": "skills",
                        "weight": 1,
                        "raw_score": 0.915,
                        "points": 91.5,
                        "explanation": "Python and SQL matched",
                        "matched_terms": ["Python", "SQL"],
                    }],
                },
            }],
            "limit": 50,
            "offset": 0,
        }
    elif path.startswith("/jobs"):
        body = {
            "items": [_job()] if "query=" in request.url else [],
            "total": 1 if "query=" in request.url else 0,
            "limit": 50,
            "offset": 0,
        }
    elif path == "/discovery/sources":
        body = {"items": []}
    elif path == "/discovery/source-configs":
        body = []
    elif path == "/discovery/tasks?limit=30":
        body = {"items": [], "limit": 30, "offset": 0}
    elif path == "/discovery/schedules":
        body = {"items": [], "total": 0}
    elif path == "/operations/summary":
        body = {
            "database_status": "ok",
            "configured_source_count": 0,
            "enabled_schedule_count": 0,
            "due_schedule_count": 0,
            "next_schedule_at": None,
            "task_counts": {},
            "expired_lease_count": 0,
            "processes": [],
            "generated_at": "2026-01-01T00:00:00Z",
        }
    elif path.startswith("/candidates/candidate-smoke-1/"):
        if "/resumes" in path or "/answers" in path or "/applications" in path or "/application-batches" in path:
            body = {"items": [], "total": 0} if "/applications?" in path else []
        else:
            body = {}
    else:
        body = {}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def _job() -> dict[str, Any]:
    return {
        "id": "job-smoke-1",
        "canonical_url": "https://jobs.example.test/backend-engineer",
        "company_name": "Synthetic Systems",
        "title": "Backend Engineer",
        "description": "Synthetic fixture only",
        "location": "Remote, India",
        "work_mode": "Remote",
        "employment_type": "Full-time",
        "salary_min": 1000000,
        "salary_max": 1500000,
        "salary_currency": "INR",
        "status": "open",
        "last_verified_at": "2026-01-01T00:00:00Z",
    }


def test_workspace_candidate_search_and_matching_flow() -> None:
    server = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        cwd=FRONTEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_vite(server)
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            page = browser.new_page()
            page.route("**/api/v1/**", _api_response)
            page.goto("http://127.0.0.1:5173", wait_until="networkidle")

            expect(page.get_by_role("heading", name="Find the right role. Know why it fits.")).to_be_visible()
            page.get_by_text("Create your first candidate profile").click()
            page.get_by_label("Display name").fill("Smoke Test Candidate")
            page.get_by_label("Skills", exact=False).fill("Python, SQL, FastAPI")
            page.get_by_label("Current location").fill("India")
            page.get_by_role("button", name="Save candidate").click()
            expect(page.get_by_text("Smoke Test Candidate")).to_be_visible()

            page.get_by_label("Search name").fill("Backend roles")
            page.get_by_label("Target job titles").fill("Backend Engineer, Software Engineer")
            page.get_by_label("Required job skills").fill("Python, SQL")
            page.get_by_label("Minimum salary").fill("1000000")
            page.get_by_label("Currency").fill("INR")
            page.get_by_role("button", name="Save search profile").click()
            expect(page.get_by_text("Search profile saved.")).to_be_visible()

            page.get_by_label("Role, company or keyword").fill("Backend Engineer")
            page.get_by_role("button", name="Search jobs").click()
            expect(page.get_by_role("heading", name="Backend Engineer")).to_be_visible()
            page.get_by_role("button", name="Evaluate my matches").click()
            expect(page.get_by_text("91.5")).to_be_visible()
            expect(page.get_by_text("eligible", exact=True)).to_be_visible()
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
