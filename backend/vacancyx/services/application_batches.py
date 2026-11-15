"""Revision-bound batch review and approval orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from vacancyx.models import (
    Application,
    ApplicationApproval,
    ApplicationBatch,
    ApplicationBatchItem,
    ApplicationEvent,
    ApplicationRevision,
    CandidateProfile,
)


class BatchNotFoundError(LookupError):
    """A candidate or candidate-owned application batch does not exist."""


class BatchConflictError(ValueError):
    """A batch or application is in a state that prevents the requested action."""


class BatchInputError(ValueError):
    """A batch request contains invalid or foreign application identifiers."""


class ApplicationBatchService:
    """Create review batches and bind each decision to an immutable application revision."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_candidate(self, candidate_id: str) -> list[dict[str, Any]] | None:
        if self.session.get(CandidateProfile, candidate_id) is None:
            return None
        batches = self.session.scalars(
            self._batch_query().where(ApplicationBatch.candidate_id == candidate_id)
            .order_by(ApplicationBatch.created_at.desc(), ApplicationBatch.id)
        ).all()
        return [self._serialize(batch) for batch in batches]

    def get(self, candidate_id: str, batch_id: str) -> dict[str, Any]:
        batch = self.session.scalar(
            self._batch_query().where(
                ApplicationBatch.id == batch_id,
                ApplicationBatch.candidate_id == candidate_id,
            )
        )
        if batch is None:
            raise BatchNotFoundError("Application batch not found.")
        return self._serialize(batch)

    def create(
        self,
        *,
        candidate_id: str,
        name: str,
        application_ids: list[str],
    ) -> dict[str, Any]:
        if self.session.get(CandidateProfile, candidate_id) is None:
            raise BatchNotFoundError("Candidate not found.")
        if not application_ids:
            raise BatchInputError("Select at least one application.")
        if len(application_ids) > 100:
            raise BatchInputError("A batch cannot contain more than 100 applications.")
        if len(application_ids) != len(set(application_ids)):
            raise BatchInputError("An application can appear only once in a batch.")
        active_item = self.session.scalar(
            select(ApplicationBatchItem.id)
            .join(ApplicationBatch, ApplicationBatch.id == ApplicationBatchItem.batch_id)
            .where(
                ApplicationBatchItem.application_id.in_(application_ids),
                ApplicationBatchItem.decision == "pending",
                ApplicationBatch.status == "reviewing",
            )
        )
        if active_item is not None:
            raise BatchConflictError(
                "An application already belongs to an active review batch."
            )

        applications = list(
            self.session.scalars(
                select(Application)
                .where(
                    Application.candidate_id == candidate_id,
                    Application.id.in_(application_ids),
                )
                .options(selectinload(Application.revisions), selectinload(Application.job))
            ).all()
        )
        by_id = {application.id: application for application in applications}
        if len(by_id) != len(application_ids):
            raise BatchInputError(
                "One or more applications do not belong to this candidate."
            )

        batch = ApplicationBatch(
            candidate_id=candidate_id,
            name=name.strip(),
            status="reviewing",
        )
        try:
            with self.session.begin_nested():
                self.session.add(batch)
                self.session.flush()
                for application_id in application_ids:
                    application = by_id[application_id]
                    if application.status != "prepared":
                        raise BatchConflictError(
                            "Only prepared applications can enter a new review batch."
                        )
                    revision = self._current_revision(application)
                    if revision is None:
                        raise BatchConflictError(
                            "An application is missing its current immutable revision."
                        )
                    item = ApplicationBatchItem(
                        batch_id=batch.id,
                        application_id=application.id,
                        revision=revision.revision,
                        content_hash=revision.content_hash,
                        decision="pending",
                    )
                    self.session.add(item)
                    self._add_event(
                        application,
                        "batch_added",
                        {
                            "batch_id": batch.id,
                            "revision": revision.revision,
                            "content_hash": revision.content_hash,
                        },
                    )
                self.session.flush()
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise BatchConflictError("The review batch could not be created.") from error
        return self.get(candidate_id, batch.id)

    def decide(
        self,
        *,
        candidate_id: str,
        batch_id: str,
        decisions: list[dict[str, str]],
    ) -> dict[str, Any]:
        batch = self.session.scalar(
            self._batch_query().where(
                ApplicationBatch.id == batch_id,
                ApplicationBatch.candidate_id == candidate_id,
            )
        )
        if batch is None:
            raise BatchNotFoundError("Application batch not found.")
        if batch.status != "reviewing":
            raise BatchConflictError("This batch is no longer accepting decisions.")
        if not decisions:
            raise BatchInputError("Provide at least one decision.")
        application_ids = [item["application_id"] for item in decisions]
        if len(application_ids) != len(set(application_ids)):
            raise BatchInputError("A batch decision request cannot repeat an application.")

        items_by_application = {item.application_id: item for item in batch.items}
        if any(application_id not in items_by_application for application_id in application_ids):
            raise BatchInputError("A decision references an application outside this batch.")

        outcomes: list[dict[str, str]] = []
        now = datetime.now(UTC)
        try:
            with self.session.begin_nested():
                for requested in decisions:
                    application_id = requested["application_id"]
                    decision = requested["decision"]
                    item = items_by_application[application_id]
                    application = item.application
                    current = self._current_revision(application)
                    if item.decision != "pending":
                        raise BatchConflictError(
                            "A batch item already has a recorded decision."
                        )
                    if (
                        current is None
                        or current.revision != item.revision
                        or current.content_hash != item.content_hash
                    ):
                        item.decision = "stale"
                        item.decided_at = now
                        self._add_event(
                            application,
                            "batch_item_stale",
                            {
                                "batch_id": batch.id,
                                "batch_revision": item.revision,
                                "current_revision": application.current_revision,
                            },
                        )
                        outcomes.append(
                            {"application_id": application_id, "result": "stale"}
                        )
                        continue
                    if application.status != "prepared":
                        raise BatchConflictError(
                            "An application changed workflow state after the batch was created."
                        )
                    snapshot = current.content_snapshot
                    readiness = snapshot.get("readiness", {})
                    if decision == "approved" and readiness.get("status") != "ready_for_review":
                        outcomes.append(
                            {"application_id": application_id, "result": "needs_attention"}
                        )
                        continue
                    approval = ApplicationApproval(
                        application_id=application.id,
                        revision=item.revision,
                        content_hash=item.content_hash,
                        decision=decision,
                        decided_at=now,
                    )
                    self.session.add(approval)
                    self.session.flush()
                    item.decision = decision
                    item.decided_at = now
                    application.status = decision
                    self._add_event(
                        application,
                        decision,
                        {
                            "batch_id": batch.id,
                            "approval_id": approval.id,
                            "revision": item.revision,
                            "content_hash": item.content_hash,
                        },
                    )
                    outcomes.append(
                        {"application_id": application_id, "result": decision}
                    )
                if all(item.decision != "pending" for item in batch.items):
                    batch.status = "completed"
                self.session.flush()
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise BatchConflictError(
                "A decision for this application revision already exists."
            ) from error
        return {"batch": self.get(candidate_id, batch_id), "results": outcomes}

    @staticmethod
    def _batch_query() -> Select[ApplicationBatch]:
        return select(ApplicationBatch).options(
            selectinload(ApplicationBatch.items)
            .selectinload(ApplicationBatchItem.application)
            .selectinload(Application.revisions),
            selectinload(ApplicationBatch.items)
            .selectinload(ApplicationBatchItem.application)
            .selectinload(Application.job),
        )

    @staticmethod
    def _current_revision(application: Application) -> ApplicationRevision | None:
        return next(
            (
                revision
                for revision in application.revisions
                if revision.revision == application.current_revision
            ),
            None,
        )

    def _serialize(self, batch: ApplicationBatch) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for item in batch.items:
            application = item.application
            current = self._current_revision(application)
            is_stale = (
                current is None
                or current.revision != item.revision
                or current.content_hash != item.content_hash
            )
            readiness = current.content_snapshot.get("readiness", {}) if current else {}
            items.append(
                {
                    "id": item.id,
                    "application_id": application.id,
                    "revision": item.revision,
                    "content_hash": item.content_hash,
                    "decision": item.decision,
                    "decided_at": item.decided_at,
                    "current_revision": application.current_revision,
                    "current_content_hash": current.content_hash if current else None,
                    "is_stale": is_stale,
                    "company_name": application.job.company_name,
                    "job_title": application.job.title,
                    "readiness_status": readiness.get("status"),
                    "missing_fields": readiness.get("missing_fields", []),
                }
            )
        return {
            "id": batch.id,
            "candidate_id": batch.candidate_id,
            "name": batch.name,
            "status": batch.status,
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
            "items": items,
            "total_items": len(items),
        }

    def _add_event(
        self,
        application: Application,
        event_type: str,
        metadata: dict[str, Any],
    ) -> None:
        self.session.add(
            ApplicationEvent(
                application_id=application.id,
                event_type=event_type,
                metadata_json=metadata,
            )
        )
