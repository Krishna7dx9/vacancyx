"""Command-line entry point for human-supervised employer portal assistance."""
from __future__ import annotations

import argparse
from typing import Sequence
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from vacancyx.db.session import get_session_factory
from vacancyx.models import Application, ApplicationApproval, ApplicationEvent, Job
from vacancyx.services.browser_assist import validate_portal_url
from vacancyx.services.browser_runner import run_browser_assist


def _load_approved_application(
    candidate_id: str, application_id: str
) -> tuple[str, str, dict[str, object], int, str]:
    """Load only the exact current approved immutable application revision."""
    factory = get_session_factory()
    with factory() as session:
        application = session.scalar(
            select(Application)
            .where(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            )
            .options(selectinload(Application.revisions))
        )
        if application is None:
            raise ValueError("Application not found for this candidate.")
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
        job = session.get(Job, application.job_id)
        if job is None or not job.canonical_url:
            raise ValueError("The job does not have an employer application URL.")
        return (
            job.canonical_url,
            f"{job.company_name} — {job.title}",
            dict(revision.content_snapshot),
            revision.revision,
            revision.content_hash,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one explicitly confirmed browser-assistance session."""
    parser = argparse.ArgumentParser(
        description="Open an approved VacancyX application in a visible browser."
    )
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--application-id", required=True)
    parser.add_argument(
        "--allowed-host",
        action="append",
        required=True,
        help="Exact HTTPS hostname explicitly trusted for this session; repeat if needed.",
    )
    args = parser.parse_args(argv)
    try:
        url, title, snapshot, revision, content_hash = _load_approved_application(
            args.candidate_id, args.application_id
        )
        host = urlsplit(url).hostname
        validate_portal_url(url, set(args.allowed_host))
        print(f"Application: {title}")
        print(f"Employer URL: {url}")
        print(f"Approved revision: {revision} ({content_hash[:12]}…)")
        print(f"Portal host: {host}")
        print("The browser will only fill a small set of known candidate fields.")
        print("Unknown questions and all legal attestations remain for you.")
        if input("Type OPEN to launch the visible browser: ").strip() != "OPEN":
            print("Cancelled; no browser was opened.")
            return 0
        result = run_browser_assist(url, snapshot, set(args.allowed_host))
        factory = get_session_factory()
        with factory() as session, session.begin():
            application = session.scalar(
                select(Application).where(
                    Application.id == args.application_id,
                    Application.candidate_id == args.candidate_id,
                )
            )
            if application is not None:
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
        print(
            "Session recorded. Application status was not changed. "
            "Update tracking only after you have verified the employer's outcome."
        )
        return 0
    except (ValueError, RuntimeError) as error:
        parser.exit(2, f"VacancyX browser assistance stopped: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
