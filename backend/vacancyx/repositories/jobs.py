"""Filtered job listing queries with stable pagination."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from vacancyx.models import Job


class JobSearchRepository:
    """Read-only search queries over canonical jobs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        *,
        query: str | None,
        location: str | None,
        work_mode: str | None,
        employment_type: str | None,
        status: str | None,
        minimum_salary: int | None,
        salary_currency: str | None,
        include_unknown_salary: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Job], int]:
        """Return one bounded page and the total count for the same filters."""
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    Job.title.ilike(pattern),
                    Job.company_name.ilike(pattern),
                    Job.description.ilike(pattern),
                )
            )
        if location:
            filters.append(Job.location.ilike(f"%{location.strip()}%"))
        if work_mode:
            filters.append(func.lower(Job.work_mode) == work_mode.casefold())
        if employment_type:
            filters.append(func.lower(Job.employment_type) == employment_type.casefold())
        if status is not None:
            filters.append(func.lower(Job.status) == status.casefold())
        if minimum_salary is not None:
            if salary_currency is None:
                raise ValueError("salary_currency is required with minimum_salary.")
            known_salary = and_(
                Job.salary_max >= minimum_salary,
                func.upper(Job.salary_currency) == salary_currency.upper(),
            )
            if include_unknown_salary:
                unknown_salary = or_(
                    Job.salary_max.is_(None),
                    Job.salary_currency.is_(None),
                )
                filters.append(or_(known_salary, unknown_salary))
            else:
                filters.append(known_salary)

        count_statement = select(func.count()).select_from(Job).where(*filters)
        total = self._session.scalar(count_statement) or 0
        statement = (
            select(Job)
            .where(*filters)
            .order_by(
                Job.last_verified_at.desc().nullslast(),
                Job.created_at.desc(),
                Job.id,
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(statement)), total
