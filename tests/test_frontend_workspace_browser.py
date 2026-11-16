"""Real Chromium smoke test for the React workspace against a deterministic API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
expect = playwright_api.expect

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
STATE: dict[str, Any] = {}


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



def _wait_for_api(process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("FastAPI exited before becoming ready.")
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/health/ready", timeout=1
            ) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise AssertionError("FastAPI did not become ready within 30 seconds.")


def _api_response(route: Any) -> None:
    request = route.request
    path = request.url.split("/api/v1", 1)[-1]
    method = request.method
    payload: dict[str, Any] = {}
    if request.post_data and "application/json" in request.headers.get("content-type", ""):
        payload = json.loads(request.post_data)

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
        STATE["candidate"] = body
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
    elif path == "/discovery/sources" and method == "GET":
        body = {"items": STATE.get("sources", [])}
    elif path == "/discovery/source-configs" and method == "GET":
        body = STATE.get("source_configs", [])
    elif path == "/discovery/source-configs" and method == "POST":
        source = {
            "source_key": "greenhouse-" + payload["external_key"].lower(),
            "provider": payload["provider"],
            "company_name": payload["company_name"],
            "is_enabled": True,
            "managed_by": "database",
        }
        STATE["source_configs"] = [source]
        STATE["sources"] = [{
            "source_key": source["source_key"],
            "provider": source["provider"],
            "company_name": source["company_name"],
        }]
        body = source
    elif path == "/discovery/tasks?limit=30" and method == "GET":
        body = {"items": STATE.get("tasks", []), "limit": 30, "offset": 0}
    elif path == "/discovery/tasks" and method == "POST":
        task = {
            "id": "task-smoke-1",
            "source_key": "greenhouse-acme",
            "task_type": "source_discovery",
            "state": "queued",
            "attempts": 0,
            "max_attempts": 3,
            "available_at": "2026-01-01T00:00:00Z",
            "lease_expires_at": None,
            "last_error_code": None,
            "last_error_message": None,
            "result": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        STATE["tasks"] = [task]
        body = {"items": [task]}
    elif path == "/discovery/schedules" and method == "GET":
        schedules = STATE.get("schedules", [])
        body = {"items": schedules, "total": len(schedules)}
    elif path == "/discovery/schedules" and method == "POST":
        schedule = {
            "id": "schedule-smoke-1",
            "name": payload["name"],
            "source_keys": payload["source_keys"],
            "interval_seconds": payload["interval_seconds"],
            "is_enabled": True,
            "next_run_at": "2026-01-01T00:00:00Z",
            "last_run_at": None,
            "run_number": 0,
            "last_error_code": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        STATE["schedules"] = [schedule]
        body = schedule
    elif path == "/operations/summary":
        body = {
            "database_status": "ok",
            "configured_source_count": len(STATE.get("source_configs", [])),
            "enabled_schedule_count": len(STATE.get("schedules", [])),
            "due_schedule_count": 0,
            "next_schedule_at": None,
            "task_counts": {},
            "expired_lease_count": 0,
            "processes": [],
            "generated_at": "2026-01-01T00:00:00Z",
        }
    elif path == "/candidates/candidate-smoke-1/resumes" and method == "GET":
        body = STATE.get("resumes", [])
    elif path == "/candidates/candidate-smoke-1/resumes" and method == "POST":
        resume = {**_resume(), "parse_status": "uploaded"}
        STATE["resumes"] = [resume]
        body = resume
    elif path == "/resumes/resume-smoke-1/parse/review" and method == "PATCH":
        parsed = _resume_parse()
        parsed["parse_status"] = "reviewed"
        parsed["parsed_content"]["reviewed_fields"] = {
            "display_name": payload["display_name"],
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "location": payload.get("location"),
            "skills": payload.get("skills", []),
        }
        STATE["resumes"][0]["parse_status"] = "reviewed"
        body = parsed
    elif path == "/resumes/resume-smoke-1/parse" and method == "POST":
        body = _resume_parse()
    elif path.startswith("/candidates/candidate-smoke-1/answers") and method == "GET":
        body = STATE.get("answers", [])
    elif path == "/candidates/candidate-smoke-1/answers" and method == "POST":
        answer = {
            "id": "answer-smoke-1",
            "candidate_id": "candidate-smoke-1",
            "question": payload["question"],
            "answer_text": payload["answer_text"],
            "category": payload.get("category"),
            "tags": [],
            "source": "candidate",
            "current_revision": 1,
            "is_active": True,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        STATE["answers"] = [answer]
        body = answer
    elif path == "/candidates/candidate-smoke-1/applications?limit=100" and method == "GET":
        applications = STATE.get("applications", [])
        body = {"items": applications, "total": len(applications)}
    elif path == "/candidates/candidate-smoke-1/applications" and method == "POST":
        application = _application(payload)
        STATE["applications"] = [application]
        body = application
    elif path == "/candidates/candidate-smoke-1/application-batches" and method == "GET":
        body = STATE.get("batches", [])
    elif path == "/candidates/candidate-smoke-1/application-batches" and method == "POST":
        application = STATE["applications"][0]
        snapshot = application["latest_revision"]["content_snapshot"]
        item = {
            "id": "batch-item-smoke-1",
            "application_id": application["id"],
            "revision": 1,
            "content_hash": application["latest_revision"]["content_hash"],
            "decision": "pending",
            "decided_at": None,
            "current_revision": 1,
            "current_content_hash": application["latest_revision"]["content_hash"],
            "is_stale": False,
            "company_name": "Synthetic Systems",
            "job_title": "Backend Engineer",
            "readiness_status": "ready_for_review",
            "missing_fields": [],
            "content_snapshot": snapshot,
        }
        batch = {
            "id": "batch-smoke-1",
            "candidate_id": "candidate-smoke-1",
            "name": payload["name"],
            "status": "reviewing",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "items": [item],
            "total_items": 1,
        }
        STATE["batches"] = [batch]
        body = batch
    elif path == "/candidates/candidate-smoke-1/application-batches/batch-smoke-1/decisions":
        batch = STATE["batches"][0]
        batch["status"] = "completed"
        batch["items"][0]["decision"] = "approved"
        batch["items"][0]["decided_at"] = "2026-01-01T00:00:00Z"
        application = STATE["applications"][0]
        application["status"] = "approved"
        body = {
            "batch": batch,
            "results": [{"application_id": application["id"], "result": "approved"}],
        }
    elif (
        path == "/candidates/candidate-smoke-1/applications/application-smoke-1/status"
        and method == "PATCH"
    ):
        application = STATE["applications"][0]
        application["status"] = payload["status"]
        body = {"id": application["id"], "status": payload["status"], "submitted_at": None}
    elif (
        path == "/candidates/candidate-smoke-1/applications/application-smoke-1/events"
        and method == "GET"
    ):
        body = STATE.get("events", [])
    elif (
        path == "/candidates/candidate-smoke-1/applications/application-smoke-1/events"
        and method == "POST"
    ):
        event = {
            "id": "event-smoke-1",
            "event_type": payload["event_type"],
            "occurred_at": "2026-01-01T00:00:00Z",
            "metadata_json": {"summary": payload["summary"]},
        }
        STATE["events"] = [event]
        body = event
    elif path.startswith("/candidates/candidate-smoke-1/"):
        body = {}
    else:
        body = {}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))



def _resume() -> dict[str, Any]:
    return {
        "id": "resume-smoke-1",
        "candidate_id": "candidate-smoke-1",
        "original_filename": "synthetic-resume.txt",
        "media_type": "text/plain",
        "file_size_bytes": 1000,
        "checksum_sha256": "b" * 64,
        "parse_status": "reviewed",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _resume_parse() -> dict[str, Any]:
    candidate = STATE.get("candidate", {})
    return {
        "id": "resume-smoke-1",
        "parse_status": "parsed",
        "parsed_content": {
            "reviewed_fields": {
                "display_name": candidate.get("display_name", "Smoke Test Candidate"),
                "email": candidate.get("email"),
                "phone": candidate.get("phone"),
                "location": candidate.get("location"),
                "skills": candidate.get("skills", []),
            },
            "warnings": [],
        },
    }


def _application(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = STATE["candidate"]
    answers = [
        answer for answer in STATE.get("answers", [])
        if answer["id"] in payload.get("answer_ids", [])
    ]
    snapshot = {
        "candidate": {
            "display_name": candidate["display_name"],
            "email": candidate["email"],
            "phone": candidate["phone"],
            "location": candidate["location"],
            "skills": candidate["skills"],
        },
        "job": _job(),
        "resume": {
            "id": "resume-smoke-1",
            "filename": "synthetic-resume.txt",
            "checksum_sha256": "b" * 64,
            "parse_status": "reviewed",
        },
        "answers": [{
            "id": answer["id"],
            "question": answer["question"],
            "answer": answer["answer_text"],
            "category": answer["category"],
            "tags": answer["tags"],
            "revision": 1,
            "content_hash": "c" * 64,
        } for answer in answers],
        "custom_fields": payload.get("custom_fields", {}),
        "readiness": {
            "status": "ready_for_review",
            "missing_fields": [],
            "selected_answer_count": len(answers),
        },
    }
    return {
        "id": "application-smoke-1",
        "candidate_id": "candidate-smoke-1",
        "job_id": "job-smoke-1",
        "resume_id": "resume-smoke-1",
        "status": "prepared",
        "current_revision": 1,
        "submitted_at": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "latest_revision": {
            "id": "revision-smoke-1",
            "revision": 1,
            "content_hash": "a" * 64,
            "content_snapshot": snapshot,
            "resume_id": "resume-smoke-1",
            "created_at": "2026-01-01T00:00:00Z",
        },
    }


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
    STATE.clear()
    STATE.update({
        "answers": [], "applications": [], "batches": [], "events": [], "resumes": [],
        "sources": [], "source_configs": [], "tasks": [], "schedules": [],
    })
    server = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        cwd=FRONTEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_vite(server)
        with playwright_api.sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            page = browser.new_page()
            page.route("**/api/v1/**", _api_response)
            page.goto("http://127.0.0.1:5173", wait_until="networkidle")

            page.get_by_role("heading", name="Find the right role.").wait_for(state="visible")
            page.get_by_text("Create your first candidate profile").click()
            page.get_by_label("Display name", exact=True).fill("Smoke Test Candidate")
            page.get_by_placeholder("Python, SQL, FastAPI").fill("Python, SQL, FastAPI")
            page.get_by_placeholder("name@example.com").fill("candidate@example.test")
            page.get_by_placeholder("Phone number").fill("+910000000000")
            page.get_by_label("Current location").fill("India")
            page.get_by_role("button", name="Save candidate").click()
            expect(page.locator(".candidate-summary strong")).to_have_text("Smoke Test Candidate")

            page.get_by_label("Search name").fill("Backend roles")
            page.get_by_label("Target job titles").fill("Backend Engineer, Software Engineer")
            page.get_by_label("Required job skills").fill("Python, SQL")
            page.get_by_label("Minimum salary").fill("1000000")
            page.get_by_label("Currency").fill("INR")
            page.get_by_role("button", name="Save search profile").click()
            expect(page.get_by_text("Search profile saved.")).to_be_visible()

            page.get_by_label("Provider").select_option("greenhouse")
            page.get_by_label("Greenhouse board token").fill("acme")
            page.get_by_label("Company display name").fill("Acme Systems")
            page.get_by_role("button", name="Add public source").click()
            expect(
                page.get_by_text(
                    "Acme Systems was added. Restart the worker and scheduler to load it."
                )
            ).to_be_visible()
            expect(
                page.locator(".source-config-item").get_by_text("greenhouse · greenhouse-acme")
            ).to_be_visible()

            page.get_by_role("button", name="Queue selected sources").click()
            expect(
                page.get_by_text(
                    "Queued 1 source refresh task(s). Start the local worker to execute them."
                )
            ).to_be_visible()
            expect(page.get_by_text("queued", exact=True)).to_be_visible()

            page.get_by_label("Schedule name").fill("Smoke daily refresh")
            page.get_by_label("Run frequency").select_option("86400")
            page.get_by_role("button", name="Save recurring schedule").click()
            expect(
                page.get_by_text(
                    "Schedule saved. Its first discovery run is due immediately "
                    "when the local scheduler is running."
                )
            ).to_be_visible()
            expect(page.get_by_text("Smoke daily refresh")).to_be_visible()

            page.get_by_label("Role, company or keyword").fill("Backend Engineer")
            page.get_by_role("button", name="Search jobs").click()
            expect(page.get_by_role("heading", name="Backend Engineer")).to_be_visible()
            page.get_by_role("button", name="Evaluate my matches").click()
            expect(page.get_by_text("91.5", exact=True)).to_be_visible()
            expect(page.get_by_text("eligible", exact=True)).to_be_visible()

            page.locator('input[type="file"]').set_input_files({
                "name": "synthetic-resume.txt",
                "mimeType": "text/plain",
                "buffer": b"Synthetic resume\\nPython\\nSQL\\nFastAPI",
            })
            page.get_by_role("button", name="Upload resume").click()
            expect(
                page.get_by_text(
                    "Resume uploaded to private local storage. "
                    "Parse it to review extracted fields."
                )
            ).to_be_visible()
            page.get_by_role("button", name="Parse locally").click()
            expect(
                page.get_by_text(
                    "Resume parsed locally. Review the suggested fields "
                    "before marking it reviewed."
                )
            ).to_be_visible()
            page.get_by_label("Name", exact=True).fill("Reviewed Smoke Candidate")
            page.get_by_role("button", name="Confirm reviewed fields").click()
            expect(
                page.get_by_text(
                    "Resume fields marked reviewed. Candidate profile contact details "
                    "remain separately editable above."
                )
            ).to_be_visible()

            page.get_by_label("Question").fill("Why backend engineering?")
            page.get_by_label("Answer").fill("I build Python APIs and data workflows.")
            page.get_by_role("button", name="Save reusable answer").click()
            expect(
                page.get_by_text("Reusable answer saved and selected for the application draft.")
            ).to_be_visible()

            page.get_by_label("Open job").select_option("job-smoke-1")
            page.get_by_label("Additional application note").fill("Synthetic review note.")
            page.get_by_role("button", name="Prepare application draft").click()
            expect(
                page.locator(".application-item .workflow-item-heading .status-pill")
            ).to_have_text("prepared")

            page.get_by_label("Add this draft to a review batch").check()
            page.get_by_role("button", name="Create batch from 1 selected").click()
            page.locator(".batch-review-item input[type='checkbox']").check()
            page.get_by_role("button", name="Approve selected").click()
            expect(
                page.locator(".application-item .workflow-item-heading .status-pill")
            ).to_have_text("approved")

            page.get_by_role("button", name="Mark submission started").click()
            expect(page.locator(".tracking-item .status-pill")).to_have_text("submitting")
            page.get_by_role("button", name="Show timeline").click()
            page.get_by_label("Timeline note").fill("Interview scheduled for next week.")
            page.get_by_role("button", name="Add timeline event").click()
            expect(page.get_by_text("Interview scheduled for next week.")).to_be_visible()
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def test_workspace_uses_live_local_api_for_candidate_and_matching() -> None:
    with tempfile.TemporaryDirectory(prefix="vacancyx-browser-e2e-") as temporary:
        temporary_path = Path(temporary)
        environment = os.environ.copy()
        environment.update({
            "VACANCYX_DATABASE_URL": f"sqlite:///{temporary_path / 'workspace.db'}",
            "VACANCYX_STORAGE_DIR": str(temporary_path / "storage"),
            "VACANCYX_ENVIRONMENT": "test",
            "VACANCYX_API_HOST": "127.0.0.1",
            "VACANCYX_API_PORT": "8000",
        })
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["vacancyx-demo-seed"],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

        api_server = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "vacancyx.main:app",
                "--host", "127.0.0.1", "--port", "8000",
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            text=True,
        )
        frontend_server: subprocess.Popen[str] | None = None
        try:
            _wait_for_api(api_server)
            frontend_server = subprocess.Popen(
                [
                    "npm", "run", "dev", "--", "--host", "127.0.0.1",
                    "--port", "5173", "--strictPort",
                ],
                cwd=FRONTEND,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                text=True,
            )
            _wait_for_vite(frontend_server)

            with playwright_api.sync_playwright() as runtime:
                browser = runtime.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto("http://127.0.0.1:5173", wait_until="networkidle")
                    page.get_by_role("heading", name="Find the right role.").wait_for(
                        state="visible"
                    )

                    page.get_by_text("Add another candidate").click()
                    page.get_by_label("Display name", exact=True).fill("Live API Smoke Candidate")
                    page.get_by_placeholder("Python, SQL, FastAPI").fill("Python, SQL, FastAPI")
                    page.locator('details.editor input[placeholder="name@example.com"]').fill(
                        "live-api@example.test"
                    )
                    page.locator('details.editor input[placeholder="Phone number"]').fill(
                        "0000000000"
                    )
                    page.get_by_label("Current location").fill("India")
                    page.get_by_role("button", name="Save candidate").click()
                    expect(page.locator(".candidate-summary strong")).to_have_text(
                        "Live API Smoke Candidate"
                    )

                    page.get_by_label("Search name").fill("Live API backend roles")
                    page.get_by_label("Target job titles").fill("Backend Engineer")
                    page.get_by_label("Required job skills").fill("Python, SQL, FastAPI")
                    page.get_by_label("Allowed locations").fill("India")
                    page.get_by_label("Work modes").fill("Remote")
                    page.get_by_label("Employment").fill("Full-time")
                    page.get_by_role("button", name="Save search profile").click()
                    expect(page.get_by_text("Search profile saved.")).to_be_visible()

                    # Configure a real public-board source and durable recurring schedule.
                    page.get_by_label("Provider").select_option("greenhouse")
                    page.get_by_label("Greenhouse board token").fill("synthetic-board")
                    page.get_by_label("Company display name").fill("Synthetic Systems")
                    page.get_by_role("button", name="Add public source").click()
                    expect(
                        page.get_by_text(
                            "Synthetic Systems was added. Restart the worker and scheduler to load it."
                        )
                    ).to_be_visible()
                    expect(
                        page.locator(".source-config-item").get_by_text(
                            "greenhouse · greenhouse-synthetic-board"
                        )
                    ).to_be_visible()

                    page.get_by_role("button", name="Queue selected sources").click()
                    expect(
                        page.get_by_text(
                            "Queued 1 source refresh task(s). Start the local worker to execute them."
                        )
                    ).to_be_visible()
                    expect(page.get_by_text("queued", exact=True)).to_be_visible()

                    page.get_by_label("Schedule name").fill("Live API daily refresh")
                    page.get_by_label("Run frequency").select_option("86400")
                    page.get_by_role("button", name="Save recurring schedule").click()
                    expect(
                        page.get_by_text(
                            "Schedule saved. Its first discovery run is due immediately "
                            "when the local scheduler is running."
                        )
                    ).to_be_visible()
                    expect(page.get_by_text("Live API daily refresh")).to_be_visible()

                    page.get_by_label("Role, company or keyword").fill("Backend Engineer")
                    page.get_by_role("button", name="Search jobs").click()
                    expect(
                        page.get_by_role("heading", name="Backend Engineer — Demo")
                    ).to_be_visible()
                    page.get_by_role("button", name="Evaluate my matches").click()
                    expect(page.get_by_text("eligible", exact=True)).to_be_visible()

                    # Exercise the real API-backed resume, application, approval, and tracking path.
                    page.locator('input[type="file"]').set_input_files({
                        "name": "live-api-synthetic-resume.txt",
                        "mimeType": "text/plain",
                        "buffer": (
                            b"Live API Synthetic Candidate\\n"
                            b"Email: live-api@example.test\\n"
                            b"Python, SQL, FastAPI\\n"
                            b"Backend engineering experience"
                        ),
                    })
                    page.get_by_role("button", name="Upload resume").click()
                    expect(
                        page.get_by_text(
                            "Resume uploaded to private local storage. "
                            "Parse it to review extracted fields."
                        )
                    ).to_be_visible()
                    page.get_by_role("button", name="Parse locally").click()
                    expect(
                        page.get_by_text(
                            "Resume parsed locally. Review the suggested fields "
                            "before marking it reviewed."
                        )
                    ).to_be_visible()
                    page.get_by_label("Name", exact=True).fill("Live API Reviewed Candidate")
                    page.get_by_role("button", name="Confirm reviewed fields").click()
                    expect(
                        page.get_by_text(
                            "Resume fields marked reviewed. Candidate profile contact details "
                    "remain separately editable above."
                        )
                    ).to_be_visible()

                    page.get_by_label("Question").fill("Why backend engineering?")
                    page.get_by_label("Answer").fill(
                        "I build Python APIs and data workflows with FastAPI and SQL."
                    )
                    page.get_by_role("button", name="Save reusable answer").click()
                    expect(
                        page.get_by_text(
                            "Reusable answer saved and selected for the application draft."
                        )
                    ).to_be_visible()

                    page.get_by_label("Open job").select_option(
                        label="Backend Engineer — Demo — Example Systems (Synthetic)"
                    )
                    page.get_by_label("Additional application note").fill(
                        "Initial synthetic application note."
                    )
                    page.get_by_role("button", name="Prepare application draft").click()
                    expect(
                        page.locator(
                            ".application-item .workflow-item-heading .status-pill"
                        ).first
                    ).to_have_text("prepared")

                    # Approve revision 1, then edit it and verify that approval cannot carry over.
                    page.get_by_label("Add this draft to a review batch").check()
                    page.get_by_role(
                        "button", name="Create batch from 1 selected"
                    ).click()
                    page.locator(".batch-review-item input[type='checkbox']").check()
                    page.get_by_role("button", name="Approve selected").click()
                    expect(
                        page.locator(
                            ".application-item .workflow-item-heading .status-pill"
                        ).first
                    ).to_have_text("approved")

                    page.get_by_role("button", name="Revise approved content").click()
                    page.get_by_label("Additional application note").last.fill(
                        "Revised synthetic application note."
                    )
                    page.get_by_role("button", name="Save new revision").click()
                    expect(
                        page.get_by_text(
                            "Draft revised to content revision 2. "
                    "Any prior review must be repeated."
                        )
                    ).to_be_visible()
                    expect(
                        page.locator(
                            ".application-item .workflow-item-heading .status-pill"
                        ).first
                    ).to_have_text("prepared")
                    expect(page.get_by_text("Stale revision", exact=True)).to_be_visible()

                    page.get_by_label("Add this draft to a review batch").check()
                    page.get_by_role(
                        "button", name="Create batch from 1 selected"
                    ).click()
                    page.locator(
                        ".batch-review-item input[type='checkbox']:not(:disabled)"
                    ).first.check()
                    page.get_by_role("button", name="Approve selected").last.click()
                    expect(
                        page.locator(
                            ".application-item .workflow-item-heading .status-pill"
                        ).first
                    ).to_have_text("approved")

                    page.get_by_role("button", name="Mark submission started").click()
                    expect(page.locator(".tracking-item .status-pill")).to_have_text(
                        "submitting"
                    )
                    page.get_by_role("button", name="Show timeline").click()
                    page.get_by_label("Timeline note").fill(
                        "Synthetic acceptance: interview scheduled."
                    )
                    page.get_by_role("button", name="Add timeline event").click()
                    expect(
                        page.get_by_text(
                            "Synthetic acceptance: interview scheduled."
                        )
                    ).to_be_visible()
                finally:
                    browser.close()
        finally:
            if frontend_server is not None:
                frontend_server.terminate()
                try:
                    frontend_server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    frontend_server.kill()
                    frontend_server.wait(timeout=5)
            api_server.terminate()
            try:
                api_server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_server.kill()
                api_server.wait(timeout=5)
