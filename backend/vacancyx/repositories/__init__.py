"""Persistence repositories."""

from vacancyx.repositories.core import (
    CandidateRepository,
    JobRepository,
    ResumeRepository,
    TaskRepository,
)
from vacancyx.repositories.jobs import JobSearchRepository
from vacancyx.repositories.search_profiles import SearchProfileRepository

__all__ = [
    "CandidateRepository",
    "JobRepository",
    "JobSearchRepository",
    "ResumeRepository",
    "SearchProfileRepository",
    "TaskRepository",
]
