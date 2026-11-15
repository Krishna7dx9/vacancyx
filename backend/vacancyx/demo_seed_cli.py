"""Console entry point for creating synthetic VacancyX demo records."""

from __future__ import annotations

import json

from vacancyx.db.session import get_session_factory
from vacancyx.services.demo_seed import run_demo_seed


def main() -> int:
    """Seed one idempotent synthetic candidate, job, and search profile."""
    result = run_demo_seed(get_session_factory())
    print(
        json.dumps(
            {
                "candidate_id": result.candidate_id,
                "job_id": result.job_id,
                "search_profile_id": result.search_profile_id,
                "created_candidate": result.created_candidate,
                "created_job": result.created_job,
                "created_search_profile": result.created_search_profile,
                "note": "All seeded records are synthetic; the example job is not a real vacancy.",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
