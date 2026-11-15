"""Application status transitions and auditable candidate timeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from vacancyx.models import Application, ApplicationApproval, ApplicationEvent


class TrackingNotFoundError(LookupError):
    """The candidate or candidate-owned application does not exist."""


class TrackingConflictError(ValueError):
    """A requested lifecycle transition is invalid or not sufficiently evidenced."""


class ApplicationTrackingService:
    """Enforce safe lifecycle transitions and append-only timeline events."""

    TRANSITIONS: dict[str, frozenset[str]] = {
        "prepared": frozenset({"withdrawn"}),
        "approved": frozenset({"submitting", "blocked", "withdrawn"}),
        "submitting": frozenset({"submitted", "uncertain", "blocked"}),
        "uncertain": frozenset({"submitted", "blocked", "withdrawn"}),
        "submitted": frozenset({"rejected", "withdrawn"}),
        "blocked": frozenset({"withdrawn"}),
        "rejected": frozenset(),
        "withdrawn": frozenset(),
        "draft": frozenset({"withdrawn"}),
    }

    TIMELINE_TYPES = frozenset({
        "assessment_scheduled",
        "assessment_completed",
        "interview_scheduled",
        "interview_completed",
        "offer_received",
        "offer_declined",
        "follow_up",
        "note",
    })

    def __init__(self, session: Session) -> None:
        self.session = session

    def _application(self, candidate_id: str, application_id: str) -> Application:
        application = self.session.scalar(
            select(Application)
            .where(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            )
            .options(selectinload(Application.revisions))
        )
        if application is None:
            raise TrackingNotFoundError("Application not found.")
        return application

    def transition(
        self,
        *,
        candidate_id: str,
        application_id: str,
        target_status: str,
        confirmation_reference: str | None = None,
    ) -> Application:
        application = self._application(candidate_id, application_id)
        allowed = self.TRANSITIONS.get(application.status, frozenset())
        if target_status not in allowed:
            raise TrackingConflictError(
                f"Cannot transition application from {application.status} to {target_status}."
            )
        if target_status == "submitting":
            revision = next(
                (
                    item for item in application.revisions
                    if item.revision == application.current_revision
                ),
                None,
            )
            approval = self.session.scalar(
                select(ApplicationApproval).where(
                    ApplicationApproval.application_id == application.id,
                    ApplicationApproval.revision == application.current_revision,
                    ApplicationApproval.decision == "approved",
                )
            )
            if (
                revision is None
                or approval is None
                or approval.content_hash != revision.content_hash
            ):
                raise TrackingConflictError(
                    "The current application revision has no valid approval."
                )
        if target_status == "submitted" and not confirmation_reference:
            raise TrackingConflictError(
                "A confirmation reference is required before marking an application submitted."
            )

        previous_status = application.status
        now = datetime.now(UTC)
        application.status = target_status
        if target_status == "submitted":
            application.submitted_at = now
        metadata: dict[str, Any] = {
            "from_status": previous_status,
            "to_status": target_status,
        }
        if confirmation_reference:
            metadata["confirmation_reference"] = confirmation_reference
        self.session.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="status_changed",
                occurred_at=now,
                metadata_json=metadata,
            )
        )
        self.session.commit()
        self.session.refresh(application)
        return application

    def add_event(
        self,
        *,
        candidate_id: str,
        application_id: str,
        event_type: str,
        summary: str,
    ) -> ApplicationEvent:
        application = self._application(candidate_id, application_id)
        if event_type not in self.TIMELINE_TYPES:
            raise TrackingConflictError("Unsupported application timeline event type.")
        event = ApplicationEvent(
            application_id=application.id,
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            metadata_json={"summary": summary},
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def list_events(self, *, candidate_id: str, application_id: str) -> list[ApplicationEvent]:
        application = self._application(candidate_id, application_id)
        return list(
            self.session.scalars(
                select(ApplicationEvent)
                .where(ApplicationEvent.application_id == application.id)
                .order_by(ApplicationEvent.occurred_at, ApplicationEvent.id)
            ).all()
        )
