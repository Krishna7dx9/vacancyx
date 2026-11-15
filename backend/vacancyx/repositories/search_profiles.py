"""Candidate-scoped search profile persistence."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from vacancyx.models import SearchProfile


class SearchProfileRepository:
    """Search profile operations always scope lookups by candidate ownership."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, profile: SearchProfile) -> SearchProfile:
        self._session.add(profile)
        self._session.flush()
        return profile

    def get_for_candidate(self, profile_id: str, candidate_id: str) -> SearchProfile | None:
        statement = select(SearchProfile).where(
            SearchProfile.id == profile_id,
            SearchProfile.candidate_id == candidate_id,
        )
        return self._session.scalar(statement)

    def list_for_candidate(self, candidate_id: str) -> list[SearchProfile]:
        statement = (
            select(SearchProfile)
            .where(SearchProfile.candidate_id == candidate_id)
            .order_by(SearchProfile.created_at.desc(), SearchProfile.id)
        )
        return list(self._session.scalars(statement))
