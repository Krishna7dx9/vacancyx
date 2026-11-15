"""Persistence operations for source observations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from vacancyx.models import JobObservation


class JobObservationRepository:
    """Source identity lookup and writes; transaction ownership stays with the service."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_source_identity(self, source_key: str, external_id: str) -> JobObservation | None:
        statement = select(JobObservation).where(
            JobObservation.source_key == source_key,
            JobObservation.external_id == external_id,
        )
        return self._session.scalar(statement)

    def add(self, observation: JobObservation) -> JobObservation:
        self._session.add(observation)
        self._session.flush()
        return observation
