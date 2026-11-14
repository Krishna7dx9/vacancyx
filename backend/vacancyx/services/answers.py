"""Candidate answer library use cases and immutable revision history."""

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from vacancyx.models import CandidateProfile
from vacancyx.models.candidate_answers import CandidateAnswer, CandidateAnswerRevision
from vacancyx.repositories.answers import CandidateAnswerRepository


class CandidateAnswerService:
    """Manage candidate-owned answers without coupling use cases to HTTP."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = CandidateAnswerRepository(session)

    def create(
        self,
        *,
        candidate_id: str,
        question: str,
        answer_text: str,
        category: str | None,
        tags: list[str],
    ) -> CandidateAnswer | None:
        """Create an answer and immutable revision one; return None for unknown candidate."""
        question = question.strip()
        answer_text = answer_text.strip()
        with self._session.begin():
            candidate = self._session.get(CandidateProfile, candidate_id)
            if candidate is None:
                return None
            answer = CandidateAnswer(
                candidate_id=candidate_id,
                question=question,
                answer_text=answer_text,
                category=category,
                tags=self._normalize_tags(tags),
                question_hash=self._question_hash(question),
                source="manual",
                current_revision=1,
            )
            self._repository.add(answer)
            self._repository.add_revision(self._build_revision(answer))
        return answer

    def list_for_candidate(
        self,
        candidate_id: str,
        *,
        query: str | None,
        category: str | None,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> list[CandidateAnswer] | None:
        if self._session.get(CandidateProfile, candidate_id) is None:
            return None
        return self._repository.list_for_candidate(
            candidate_id,
            query=query,
            category=category,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    def update(
        self, *, answer_id: str, candidate_id: str, changes: dict[str, Any]
    ) -> CandidateAnswer | None:
        """Update selected fields; append a revision only when answer content changes."""
        with self._session.begin():
            answer = self._repository.get_for_candidate(answer_id, candidate_id)
            if answer is None:
                return None

            previous_hash = self._content_hash(
                question=answer.question,
                answer_text=answer.answer_text,
                category=answer.category,
                tags=answer.tags,
            )
            for field, value in changes.items():
                if field in {"question", "answer_text"} and isinstance(value, str):
                    value = value.strip()
                if field == "tags":
                    value = self._normalize_tags(value)
                setattr(answer, field, value)

            if "question" in changes:
                answer.question_hash = self._question_hash(answer.question)
            current_hash = self._content_hash(
                question=answer.question,
                answer_text=answer.answer_text,
                category=answer.category,
                tags=answer.tags,
            )
            if current_hash != previous_hash:
                answer.current_revision += 1
                self._repository.add_revision(self._build_revision(answer))
            self._session.flush()
        return answer

    def list_revisions(
        self, *, answer_id: str, candidate_id: str
    ) -> list[CandidateAnswerRevision] | None:
        return self._repository.list_revisions(answer_id, candidate_id)

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        normalized = [tag.strip() for tag in tags if tag.strip()]
        return list(dict.fromkeys(normalized))

    @staticmethod
    def _question_hash(question: str) -> str:
        normalized = " ".join(question.casefold().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _content_hash(
        *, question: str, answer_text: str, category: str | None, tags: list[str]
    ) -> str:
        content = json.dumps(
            {"question": question, "answer_text": answer_text, "category": category, "tags": tags},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _build_revision(self, answer: CandidateAnswer) -> CandidateAnswerRevision:
        return CandidateAnswerRevision(
            answer_id=answer.id,
            revision=answer.current_revision,
            question_snapshot=answer.question,
            answer_snapshot=answer.answer_text,
            category_snapshot=answer.category,
            tags_snapshot=list(answer.tags),
            source=answer.source,
            content_hash=self._content_hash(
                question=answer.question,
                answer_text=answer.answer_text,
                category=answer.category,
                tags=answer.tags,
            ),
        )
