"""Candidate-owned search profile use cases."""

from typing import Any

from sqlalchemy.orm import Session

from vacancyx.matching.criteria import MatchCriteria
from vacancyx.models import CandidateProfile, SearchProfile
from vacancyx.repositories.search_profiles import SearchProfileRepository


class SearchProfileService:
    """Validate candidate ownership and persist explicit search criteria."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = SearchProfileRepository(session)

    def create(
        self,
        *,
        candidate_id: str,
        name: str,
        criteria: MatchCriteria,
        is_enabled: bool,
    ) -> SearchProfile | None:
        with self._session.begin():
            if self._session.get(CandidateProfile, candidate_id) is None:
                return None
            profile = SearchProfile(
                candidate_id=candidate_id,
                name=name.strip(),
                criteria=criteria.model_dump(mode="json"),
                is_enabled=is_enabled,
            )
            self._repository.add(profile)
        return profile

    def list_for_candidate(self, candidate_id: str) -> list[SearchProfile] | None:
        if self._session.get(CandidateProfile, candidate_id) is None:
            return None
        return self._repository.list_for_candidate(candidate_id)

    def get(self, profile_id: str, candidate_id: str) -> SearchProfile | None:
        return self._repository.get_for_candidate(profile_id, candidate_id)

    def update(
        self,
        *,
        profile_id: str,
        candidate_id: str,
        changes: dict[str, Any],
    ) -> SearchProfile | None:
        with self._session.begin():
            profile = self._repository.get_for_candidate(profile_id, candidate_id)
            if profile is None:
                return None
            for field, value in changes.items():
                if field == "criteria" and isinstance(value, MatchCriteria):
                    value = value.model_dump(mode="json")
                if field == "name" and isinstance(value, str):
                    value = value.strip()
                setattr(profile, field, value)
            self._session.flush()
        return profile
