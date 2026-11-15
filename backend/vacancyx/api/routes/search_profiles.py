"""Candidate-owned search profile and matching endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from vacancyx.api.schemas.jobs import JobRead
from vacancyx.api.schemas.search_profiles import (
    SearchProfileCreate,
    SearchProfileMatchItem,
    SearchProfileMatchResponse,
    SearchProfilePatch,
    SearchProfileRead,
)
from vacancyx.db.session import get_session
from vacancyx.matching.criteria import (
    CandidateSnapshot,
    JobSnapshot,
    MatchCriteria,
    MatchingRuleSet,
)
from vacancyx.matching.engine import MatchingEngine, MatchResult
from vacancyx.models import CandidateProfile, SearchProfile
from vacancyx.repositories.jobs import JobSearchRepository
from vacancyx.services.search_profiles import SearchProfileService

router = APIRouter(
    prefix="/candidates/{candidate_id}/search-profiles",
    tags=["search-profiles"],
)
SessionDep = Annotated[Session, Depends(get_session)]
MAX_EVALUATION_JOBS = 500


@router.post("", response_model=SearchProfileRead, status_code=status.HTTP_201_CREATED)
def create_search_profile(
    candidate_id: str,
    payload: SearchProfileCreate,
    session: SessionDep,
) -> SearchProfile:
    """Create a candidate-owned search profile with validated matching criteria."""
    profile = SearchProfileService(session).create(
        candidate_id=candidate_id,
        name=payload.name,
        criteria=payload.criteria,
        is_enabled=payload.is_enabled,
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )
    return profile


@router.get("", response_model=list[SearchProfileRead])
def list_search_profiles(
    candidate_id: str,
    session: SessionDep,
) -> list[SearchProfile]:
    """List only the selected candidate's search profiles."""
    profiles = SearchProfileService(session).list_for_candidate(candidate_id)
    if profiles is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )
    return profiles


@router.get("/{profile_id}", response_model=SearchProfileRead)
def get_search_profile(
    candidate_id: str,
    profile_id: str,
    session: SessionDep,
) -> SearchProfile:
    """Fetch a search profile only within its candidate ownership boundary."""
    profile = SearchProfileService(session).get(profile_id, candidate_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search profile not found.",
        )
    return profile


@router.patch("/{profile_id}", response_model=SearchProfileRead)
def update_search_profile(
    candidate_id: str,
    profile_id: str,
    payload: SearchProfilePatch,
    session: SessionDep,
) -> SearchProfile:
    """Partially update a search profile without replacing omitted criteria."""
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be supplied.",
        )
    profile = SearchProfileService(session).update(
        profile_id=profile_id,
        candidate_id=candidate_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search profile not found.",
        )
    return profile


@router.post("/{profile_id}/matches", response_model=SearchProfileMatchResponse)
def evaluate_search_profile(
    candidate_id: str,
    profile_id: str,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchProfileMatchResponse:
    """Evaluate a bounded set of recent open jobs and return explainable ranked results."""
    service = SearchProfileService(session)
    profile = service.get(profile_id, candidate_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search profile not found.",
        )
    if not profile.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Search profile is disabled.",
        )
    candidate = session.get(CandidateProfile, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )
    try:
        criteria = MatchCriteria.model_validate(profile.criteria)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stored search criteria are invalid; update the search profile.",
        ) from exc

    jobs, total_jobs = JobSearchRepository(session).search(
        query=None,
        location=None,
        work_mode=None,
        employment_type=None,
        status="open",
        minimum_salary=None,
        salary_currency=None,
        include_unknown_salary=True,
        limit=MAX_EVALUATION_JOBS,
        offset=0,
    )
    candidate_snapshot = CandidateSnapshot(skills=tuple(candidate.skills))
    engine = MatchingEngine()
    evaluated: list[SearchProfileMatchItem] = []
    for job in jobs:
        job_snapshot = JobSnapshot(
            title=job.title,
            company_name=job.company_name,
            description=job.description,
            location=job.location,
            work_mode=job.work_mode,
            employment_type=job.employment_type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            status=job.status,
        )
        result: MatchResult = engine.evaluate(
            candidate_snapshot,
            job_snapshot,
            criteria,
            MatchingRuleSet(),
        )
        evaluated.append(
            SearchProfileMatchItem(
                job=JobRead.model_validate(job),
                match=result,
            )
        )

    status_order = {"eligible": 0, "needs_review": 1, "ineligible": 2}
    evaluated.sort(
        key=lambda item: (
            status_order[item.match.status],
            -item.match.score,
            item.job.id,
        )
    )
    return SearchProfileMatchResponse(
        profile_id=profile_id,
        total_jobs_available=total_jobs,
        evaluated_count=len(evaluated),
        truncated=total_jobs > len(evaluated),
        items=evaluated[offset : offset + limit],
        limit=limit,
        offset=offset,
    )
