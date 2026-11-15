"""Immutable application preparation and revision snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from vacancyx.models import (
    Application,
    ApplicationEvent,
    ApplicationRevision,
    CandidateProfile,
    Job,
    Resume,
)
from vacancyx.models.candidate_answers import CandidateAnswer, CandidateAnswerRevision


class ApplicationNotFoundError(LookupError):
    """An application or its candidate-owned parent does not exist."""


class ApplicationConflictError(ValueError):
    """The requested application conflicts with existing workflow state."""


class ApplicationInputError(ValueError):
    """The requested resume or answer does not belong to the candidate."""


class ApplicationService:
    """Build candidate-specific snapshots without exposing local storage paths."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_candidate(
        self, candidate_id: str, *, limit: int, offset: int
    ) -> tuple[list[Application], int] | None:
        candidate = self.session.get(CandidateProfile, candidate_id)
        if candidate is None:
            return None
        query = (
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .options(selectinload(Application.revisions))
            .order_by(Application.updated_at.desc(), Application.id)
        )
        total = len(
            self.session.scalars(
                select(Application.id).where(Application.candidate_id == candidate_id)
            ).all()
        )
        items = list(self.session.scalars(query.limit(limit).offset(offset)).all())
        for item in items:
            item.revisions.sort(key=lambda revision: revision.revision)
        return items, total

    def get(self, candidate_id: str, application_id: str) -> Application:
        application = self.session.scalar(
            select(Application)
            .where(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            )
            .options(selectinload(Application.revisions))
        )
        if application is None:
            raise ApplicationNotFoundError("Application not found.")
        application.revisions.sort(key=lambda revision: revision.revision)
        return application

    def prepare(
        self,
        *,
        candidate_id: str,
        job_id: str,
        resume_id: str | None,
        answer_ids: list[str],
        custom_fields: dict[str, str],
    ) -> Application:
        candidate = self.session.get(CandidateProfile, candidate_id)
        if candidate is None:
            raise ApplicationNotFoundError("Candidate not found.")
        job = self.session.get(Job, job_id)
        if job is None:
            raise ApplicationNotFoundError("Job not found.")
        if job.status != "open":
            raise ApplicationConflictError("Only open jobs can be prepared.")
        if self.session.scalar(
            select(Application.id).where(
                Application.candidate_id == candidate_id,
                Application.job_id == job_id,
            )
        ):
            raise ApplicationConflictError("An application already exists for this candidate and job.")
        resume = self._owned_resume(candidate_id, resume_id)
        answers = self._owned_answers(candidate_id, answer_ids)
        snapshot = self._build_snapshot(candidate, job, resume, answers, custom_fields)
        application = Application(
            candidate_id=candidate_id,
            job_id=job_id,
            resume_id=resume.id if resume else None,
            status="prepared",
            current_revision=1,
        )
        try:
            with self.session.begin_nested():
                self.session.add(application)
                self.session.flush()
                self._add_revision(application, snapshot, resume.id if resume else None)
                self._add_event(application.id, "prepared", {"revision": 1})
                self.session.flush()
        except IntegrityError as error:
            raise ApplicationConflictError(
                "An application already exists for this candidate and job."
            ) from error
        self.session.refresh(application)
        return application

    def revise(
        self,
        *,
        candidate_id: str,
        application_id: str,
        resume_id: str | None,
        answer_ids: list[str] | None,
        custom_fields: dict[str, str] | None,
    ) -> Application:
        application = self.get(candidate_id, application_id)
        if application.status in {"submitting", "submitted", "uncertain", "withdrawn"}:
            raise ApplicationConflictError("This application can no longer be edited.")
        current = application.revisions[-1]
        snapshot = dict(current.content_snapshot)
        selected_resume_id = application.resume_id if resume_id is None else resume_id
        if resume_id is not None or application.resume_id is not None:
            resume = self._owned_resume(candidate_id, selected_resume_id)
        else:
            resume = None
        if answer_ids is not None:
            answers = self._owned_answers(candidate_id, answer_ids)
            snapshot["answers"] = self._answer_snapshots(answers)
        if custom_fields is not None:
            snapshot["custom_fields"] = custom_fields
        snapshot["resume"] = self._resume_snapshot(resume)
        next_revision = application.current_revision + 1
        with self.session.begin_nested():
            application.resume_id = resume.id if resume else None
            application.current_revision = next_revision
            application.status = "prepared"
            self._add_revision(application, snapshot, application.resume_id)
            self._add_event(
                application.id,
                "content_revised",
                {"revision": next_revision, "previous_revision": next_revision - 1},
            )
            self.session.flush()
        self.session.refresh(application)
        return self.get(candidate_id, application_id)

    def _owned_resume(self, candidate_id: str, resume_id: str | None) -> Resume | None:
        if resume_id is None:
            return None
        resume = self.session.scalar(
            select(Resume).where(
                Resume.id == resume_id,
                Resume.candidate_id == candidate_id,
            )
        )
        if resume is None:
            raise ApplicationInputError("Resume does not belong to this candidate.")
        return resume

    def _owned_answers(self, candidate_id: str, answer_ids: list[str]) -> list[CandidateAnswer]:
        if not answer_ids:
            return []
        answers = list(
            self.session.scalars(
                select(CandidateAnswer).where(
                    CandidateAnswer.candidate_id == candidate_id,
                    CandidateAnswer.id.in_(answer_ids),
                    CandidateAnswer.is_active.is_(True),
                )
            ).all()
        )
        if len(answers) != len(answer_ids):
            raise ApplicationInputError(
                "One or more answers are inactive or do not belong to this candidate."
            )
        by_id = {answer.id: answer for answer in answers}
        return [by_id[answer_id] for answer_id in answer_ids]

    def _build_snapshot(
        self,
        candidate: CandidateProfile,
        job: Job,
        resume: Resume | None,
        answers: list[CandidateAnswer],
        custom_fields: dict[str, str],
    ) -> dict[str, Any]:
        return {
            "candidate": {
                "display_name": candidate.display_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "location": candidate.location,
                "skills": list(candidate.skills),
                "education": candidate.education,
                "experience": candidate.experience,
                "links": candidate.links,
            },
            "job": {
                "company_name": job.company_name,
                "title": job.title,
                "canonical_url": job.canonical_url,
                "location": job.location,
                "description": job.description,
                "employment_type": job.employment_type,
                "work_mode": job.work_mode,
            },
            "resume": self._resume_snapshot(resume),
            "answers": self._answer_snapshots(answers),
            "custom_fields": custom_fields,
            "readiness": self._readiness(candidate, resume, answers),
        }

    @staticmethod
    def _resume_snapshot(resume: Resume | None) -> dict[str, Any] | None:
        if resume is None:
            return None
        return {
            "id": resume.id,
            "filename": resume.original_filename,
            "checksum_sha256": resume.checksum_sha256,
            "parse_status": resume.parse_status,
        }

    def _answer_snapshots(self, answers: list[CandidateAnswer]) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for answer in answers:
            revision = self.session.scalar(
                select(CandidateAnswerRevision).where(
                    CandidateAnswerRevision.answer_id == answer.id,
                    CandidateAnswerRevision.revision == answer.current_revision,
                )
            )
            snapshots.append(
                {
                    "id": answer.id,
                    "question": answer.question,
                    "answer": answer.answer_text,
                    "revision": answer.current_revision,
                    "content_hash": revision.content_hash if revision else None,
                }
            )
        return snapshots

    @staticmethod
    def _readiness(
        candidate: CandidateProfile,
        resume: Resume | None,
        answers: list[CandidateAnswer],
    ) -> dict[str, Any]:
        missing = []
        if not candidate.email:
            missing.append("candidate.email")
        if not candidate.phone:
            missing.append("candidate.phone")
        if resume is None:
            missing.append("resume")
        if resume is not None and resume.parse_status not in {"parsed", "reviewed"}:
            missing.append("resume.review")
        return {
            "status": "ready_for_review" if not missing else "needs_attention",
            "missing_fields": missing,
            "selected_answer_count": len(answers),
        }

    def _add_revision(
        self, application: Application, snapshot: dict[str, Any], resume_id: str | None
    ) -> None:
        serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        self.session.add(
            ApplicationRevision(
                application_id=application.id,
                revision=application.current_revision,
                content_hash=digest,
                content_snapshot=snapshot,
                resume_id=resume_id,
            )
        )

    def _add_event(self, application_id: str, event_type: str, metadata: dict[str, Any]) -> None:
        self.session.add(
            ApplicationEvent(
                application_id=application_id,
                event_type=event_type,
                metadata_json=metadata,
            )
        )
