"""Read-only job search endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from vacancyx.api.schemas.jobs import JobRead, JobSearchResponse
from vacancyx.db.session import get_session
from vacancyx.models import Job
from vacancyx.repositories.jobs import JobSearchRepository

router = APIRouter(prefix="/jobs", tags=["jobs"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=JobSearchResponse)
def search_jobs(
    session: SessionDep,
    query: Annotated[str | None, Query(max_length=120)] = None,
    location: Annotated[str | None, Query(max_length=240)] = None,
    work_mode: Annotated[str | None, Query(max_length=30)] = None,
    employment_type: Annotated[str | None, Query(max_length=40)] = None,
    job_status: Annotated[str, Query(alias="status", max_length=30)] = "open",
    minimum_salary: Annotated[int | None, Query(ge=0)] = None,
    salary_currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    include_unknown_salary: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobSearchResponse:
    """Search normalized jobs with bounded pagination and explicit salary semantics."""
    if minimum_salary is not None and salary_currency is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="salary_currency is required with minimum_salary.",
        )
    if salary_currency is not None and not salary_currency.isalpha():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="salary_currency must contain three letters.",
        )
    selected_status = None if job_status.casefold() == "all" else job_status
    items, total = JobSearchRepository(session).search(
        query=query,
        location=location,
        work_mode=work_mode,
        employment_type=employment_type,
        status=selected_status,
        minimum_salary=minimum_salary,
        salary_currency=salary_currency,
        include_unknown_salary=include_unknown_salary,
        limit=limit,
        offset=offset,
    )
    return JobSearchResponse(
        items=[JobRead.model_validate(job) for job in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: SessionDep) -> Job:
    """Fetch one normalized job by its opaque identifier."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job
