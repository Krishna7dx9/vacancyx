"""Candidate answer persistence operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from vacancyx.models.candidate_answers import CandidateAnswer, CandidateAnswerRevision


class CandidateAnswerRepository:
    """Repository methods never commit; the use-case service owns transactions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, answer: CandidateAnswer) -> CandidateAnswer:
        self._session.add(answer)
        self._session.flush()
        return answer

    def add_revision(self, revision: CandidateAnswerRevision) -> CandidateAnswerRevision:
        self._session.add(revision)
        self._session.flush()
        return revision

    def get_for_candidate(self, answer_id: str, candidate_id: str) -> CandidateAnswer | None:
        statement = select(CandidateAnswer).where(
            CandidateAnswer.id == answer_id,
            CandidateAnswer.candidate_id == candidate_id,
        )
        return self._session.scalar(statement)

    def list_for_candidate(
        self,
        candidate_id: str,
        *,
        query: str | None,
        category: str | None,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> list[CandidateAnswer]:
        statement = select(CandidateAnswer).where(CandidateAnswer.candidate_id == candidate_id)
        if active_only:
            statement = statement.where(CandidateAnswer.is_active.is_(True))
        if category is not None:
            statement = statement.where(CandidateAnswer.category == category)
        if query:
            term = query.strip()
            statement = statement.where(
                CandidateAnswer.question.contains(term, autoescape=True)
                | CandidateAnswer.answer_text.contains(term, autoescape=True)
            )
        statement = (
            statement.order_by(CandidateAnswer.updated_at.desc(), CandidateAnswer.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(statement))

    def list_revisions(
        self, answer_id: str, candidate_id: str
    ) -> list[CandidateAnswerRevision] | None:
        answer = self.get_for_candidate(answer_id, candidate_id)
        if answer is None:
            return None
        statement = (
            select(CandidateAnswerRevision)
            .where(CandidateAnswerRevision.answer_id == answer_id)
            .order_by(CandidateAnswerRevision.revision.desc())
        )
        return list(self._session.scalars(statement))
