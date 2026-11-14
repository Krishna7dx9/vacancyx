"""Candidate profile use cases and transaction boundaries."""

from sqlalchemy.orm import Session

from vacancyx.api.schemas.candidates import CandidateProfileCreate, CandidateProfilePatch
from vacancyx.models import CandidateProfile
from vacancyx.repositories import CandidateRepository


class CandidateService:
    """Coordinate candidate profile persistence without leaking HTTP concerns."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = CandidateRepository(session)

    def create(self, payload: CandidateProfileCreate) -> CandidateProfile:
        """Create a profile in one explicit transaction."""
        candidate = CandidateProfile(**payload.model_dump())
        with self._session.begin():
            self._repository.add(candidate)
        return candidate

    def get(self, candidate_id: str) -> CandidateProfile | None:
        """Return a profile by ID."""
        return self._repository.get(candidate_id)

    def list_active(self, *, limit: int, offset: int) -> list[CandidateProfile]:
        """Return a stable, bounded page of active profiles."""
        return self._repository.list_active(limit=limit, offset=offset)

    def update(
        self, candidate_id: str, payload: CandidateProfilePatch
    ) -> CandidateProfile | None:
        """Apply only supplied fields and persist them atomically."""
        with self._session.begin():
            candidate = self._repository.get(candidate_id)
            if candidate is None:
                return None
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(candidate, field, value)
            self._session.flush()
        return candidate
