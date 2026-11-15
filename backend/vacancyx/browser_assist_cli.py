"""CLI for explicitly approved single or batch browser-assistance sessions."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from vacancyx.db.session import get_session_factory
from vacancyx.models import (
    Application,
    ApplicationApproval,
    ApplicationBatch,
    ApplicationBatchItem,
    ApplicationEvent,
)
from vacancyx.services.browser_assist import validate_portal_url
from vacancyx.services.browser_runner import BrowserAssistResult, run_browser_assist

ApprovedApplication = tuple[str, str, dict[str, Any], int, str]


def _approved_application_record(
    session: Session,
    application: Application,
) -> ApprovedApplication:
    """Validate and serialize the exact current approved immutable application."""
    if application.status != "approved":
        raise ValueError("Only an application with current approved status can be opened.")
    revision = next(
        (
            item for item in application.revisions
            if item.revision == application.current_revision
        ),
        None,
    )
    if revision is None:
        raise ValueError("The current immutable application revision is missing.")
    approval = session.scalar(
        select(ApplicationApproval).where(
            ApplicationApproval.application_id == application.id,
            ApplicationApproval.revision == application.current_revision,
            ApplicationApproval.decision == "approved",
            ApplicationApproval.content_hash == revision.content_hash,
        )
    )
    if approval is None:
        raise ValueError("The current application revision has no matching approval.")
    job = application.job
    if job is None or not job.canonical_url:
        raise ValueError("The job does not have an employer application URL.")
    return (
        job.canonical_url,
        f"{job.company_name} — {job.title}",
        dict(revision.content_snapshot),
        revision.revision,
        revision.content_hash,
    )


def _load_approved_application(
    candidate_id: str, application_id: str
) -> ApprovedApplication:
    """Load one candidate-owned application with its current matching approval."""
    factory = get_session_factory()
    with factory() as session:
        application = session.scalar(
            select(Application)
            .where(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            )
            .options(
                selectinload(Application.revisions),
                selectinload(Application.job),
            )
        )
        if application is None:
            raise ValueError("Application not found for this candidate.")
        return _approved_application_record(session, application)


def _load_approved_batch(
    candidate_id: str, batch_id: str
) -> tuple[list[tuple[str, ApprovedApplication]], int]:
    """Return current approved batch items and count rejected, pending, or stale items."""
    factory = get_session_factory()
    with factory() as session:
        batch = session.scalar(
            select(ApplicationBatch)
            .where(
                ApplicationBatch.id == batch_id,
                ApplicationBatch.candidate_id == candidate_id,
            )
            .options(
                selectinload(ApplicationBatch.items)
                .selectinload(ApplicationBatchItem.application)
                .selectinload(Application.revisions),
                selectinload(ApplicationBatch.items)
                .selectinload(ApplicationBatchItem.application)
                .selectinload(Application.job),
            )
        )
        if batch is None:
            raise ValueError("Application batch not found for this candidate.")
        approved: list[tuple[str, ApprovedApplication]] = []
        skipped = 0
        for item in batch.items:
            if item.decision != "approved":
                skipped += 1
                continue
            try:
                record = _approved_application_record(session, item.application)
            except ValueError:
                skipped += 1
                continue
            _url, _title, _snapshot, revision, content_hash = record
            if revision != item.revision or content_hash != item.content_hash:
                skipped += 1
                continue
            approved.append((item.application_id, record))
        if not approved:
            raise ValueError("The batch contains no current approved applications to assist.")
        return approved, skipped


def _record_assist_event(
    candidate_id: str,
    application_id: str,
    revision: int,
    content_hash: str,
    host: str | None,
    result: BrowserAssistResult,
) -> None:
    """Append a non-sensitive event; never change application lifecycle status."""
    factory = get_session_factory()
    with factory() as session, session.begin():
        application = session.scalar(
            select(Application).where(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            )
        )
        if application is None:
            return
        event_type = (
            "browser_assist_interrupted"
            if result.interruption_codes
            else "browser_assist_opened"
        )
        session.add(
            ApplicationEvent(
                application_id=application.id,
                event_type=event_type,
                metadata_json={
                    "revision": revision,
                    "content_hash": content_hash,
                    "page_host": host,
                    "filled_field_count": result.filled_field_count,
                    "skipped_field_count": result.skipped_field_count,
                    "interruption_codes": list(result.interruption_codes),
                },
            )
        )


def _run_one(
    candidate_id: str,
    application_id: str,
    expected_record: ApprovedApplication,
    allowed_hosts: set[str],
) -> str:
    """Revalidate one approved revision immediately before opening the browser."""
    url, title, snapshot, revision, content_hash = _load_approved_application(
        candidate_id, application_id
    )
    expected_url, _expected_title, _expected_snapshot, expected_revision, expected_hash = (
        expected_record
    )
    if revision != expected_revision or content_hash != expected_hash or url != expected_url:
        raise ValueError("The application changed after batch approval; review it again.")
    validate_portal_url(url, allowed_hosts)
    host = urlsplit(url).hostname
    print(f"\nApplication: {title}")
    print(f"Employer URL: {url}")
    print(f"Approved revision: {revision} ({content_hash[:12]}…)")
    print(f"Portal host: {host}")
    print("Only recognized ordinary candidate fields may be filled.")
    print("Unknown questions and all legal attestations remain for you.")
    choice = input("Type OPEN to launch, SKIP to move on, or STOP to finish: ").strip().upper()
    if choice != "OPEN":
        return "stopped" if choice == "STOP" else "skipped"
    result = run_browser_assist(url, snapshot, allowed_hosts)
    _record_assist_event(
        candidate_id,
        application_id,
        revision,
        content_hash,
        host,
        result,
    )
    print(
        "Session recorded. Application status was not changed. "
        "Update tracking only after verifying the employer's outcome."
    )
    return "opened"


def main(argv: Sequence[str] | None = None) -> int:
    """Run one approved application or the approved items in a review batch."""
    parser = argparse.ArgumentParser(
        description="Open approved VacancyX applications in a visible browser."
    )
    parser.add_argument("--candidate-id", required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--application-id")
    selection.add_argument("--batch-id")
    parser.add_argument(
        "--allowed-host",
        action="append",
        required=True,
        help="Exact HTTPS hostname explicitly trusted for this session; repeat if needed.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum approved batch items to offer (1–100; default 25).",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100.")

    allowed_hosts = set(args.allowed_host)
    try:
        if args.application_id:
            records = [
                (
                    args.application_id,
                    _load_approved_application(args.candidate_id, args.application_id),
                )
            ]
            skipped = 0
        else:
            records, skipped = _load_approved_batch(args.candidate_id, args.batch_id)
            records = records[: args.limit]

        if skipped:
            print(f"Skipping {skipped} rejected, pending, stale, or unapproved batch item(s).")
        opened = 0
        user_skipped = 0
        for application_id, record in records:
            try:
                outcome = _run_one(
                    args.candidate_id,
                    application_id,
                    record,
                    allowed_hosts,
                )
            except ValueError as error:
                print(f"Skipping {application_id}: {error}")
                user_skipped += 1
                continue
            if outcome == "stopped":
                break
            if outcome == "skipped":
                user_skipped += 1
                continue
            opened += 1
        print(
            f"Browser assistance finished: {opened} session(s) opened; "
            f"{skipped + user_skipped} item(s) skipped."
        )
        return 0
    except (ValueError, RuntimeError) as error:
        parser.exit(2, f"VacancyX browser assistance stopped: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
