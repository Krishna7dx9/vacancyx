"""Deterministic tests for eligibility, unknown data and explainable ranking."""

import pytest

from vacancyx.matching.criteria import (
    CandidateSnapshot,
    JobSnapshot,
    MatchCriteria,
    MatchingRuleSet,
)
from vacancyx.matching.engine import MatchingEngine


def _candidate() -> CandidateSnapshot:
    return CandidateSnapshot(skills=("Python", "SQL", "Redis"))


def _job(**overrides: object) -> JobSnapshot:
    values: dict[str, object] = {
        "title": "Backend Engineer / Python Developer",
        "company_name": "Example Systems",
        "description": "Build Python and SQL services with FastAPI.",
        "location": "Remote, India",
        "work_mode": "Remote",
        "employment_type": "Full-time",
        "salary_min": 1_200_000,
        "salary_max": 1_600_000,
        "salary_currency": "INR",
        "status": "open",
    }
    values.update(overrides)
    return JobSnapshot.model_validate(values)


def _criteria(**overrides: object) -> MatchCriteria:
    values: dict[str, object] = {
        "target_titles": ("Backend Engineer", "Python Developer"),
        "required_skills": ("Python", "SQL"),
        "allowed_locations": ("Remote",),
        "work_modes": ("Remote",),
        "employment_types": ("Full-time",),
        "minimum_salary": 1_000_000,
        "salary_currency": "inr",
    }
    values.update(overrides)
    return MatchCriteria.model_validate(values)


def test_matching_returns_deterministic_explainable_score() -> None:
    result = MatchingEngine().evaluate(_candidate(), _job(), _criteria())

    assert result.status == "eligible"
    assert result.rule_version == "1.0"
    assert result.score == 88.33
    assert result.unknown_fields == ()
    assert {component.name for component in result.components} == {
        "role",
        "skills",
        "location",
        "work_mode",
        "salary",
    }
    skills = next(component for component in result.components if component.name == "skills")
    assert skills.matched_terms == ("Python", "SQL")
    assert "skills_match:Python,SQL" in result.reasons


def test_closed_job_is_ineligible() -> None:
    result = MatchingEngine().evaluate(
        _candidate(), _job(status="closed"), MatchCriteria()
    )
    assert result.status == "ineligible"
    assert "job_not_open" in result.reasons


def test_excluded_keyword_is_a_hard_rejection() -> None:
    result = MatchingEngine().evaluate(
        _candidate(),
        _job(title="Backend Engineer Intern"),
        _criteria(excluded_keywords=("intern",)),
    )
    assert result.status == "ineligible"
    assert "excluded_keyword:intern" in result.reasons


def test_missing_required_job_skill_is_a_hard_rejection() -> None:
    result = MatchingEngine().evaluate(
        _candidate(), _job(description="Build Java services."), _criteria()
    )
    assert result.status == "ineligible"
    assert "required_skills_missing:Python,SQL" in result.reasons


def test_known_location_work_mode_and_employment_mismatches_reject() -> None:
    engine = MatchingEngine()
    cases = (
        (_job(location="Bengaluru"), _criteria(), "location_not_allowed"),
        (_job(work_mode="On-site"), _criteria(), "work_mode_not_allowed"),
        (_job(employment_type="Internship"), _criteria(), "employment_type_not_allowed"),
    )
    for job, criteria, reason in cases:
        result = engine.evaluate(_candidate(), job, criteria)
        assert result.status == "ineligible"
        assert reason in result.reasons


def test_unknown_fields_require_review_instead_of_false_rejection() -> None:
    job = _job(
        description=None,
        location=None,
        work_mode=None,
        employment_type=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
    )
    result = MatchingEngine().evaluate(_candidate(), job, _criteria())

    assert result.status == "needs_review"
    assert set(result.unknown_fields) == {
        "job.description",
        "job.employment_type",
        "job.location",
        "job.salary_range",
        "job.work_mode",
    }


def test_salary_floor_and_currency_are_hard_constraints() -> None:
    engine = MatchingEngine()
    low_salary = engine.evaluate(
        _candidate(),
        _job(salary_min=700_000, salary_max=900_000),
        _criteria(),
    )
    wrong_currency = engine.evaluate(
        _candidate(),
        _job(salary_currency="USD"),
        _criteria(),
    )

    assert low_salary.status == "ineligible"
    assert "salary_below_minimum" in low_salary.reasons
    assert wrong_currency.status == "ineligible"
    assert "salary_currency_mismatch" in wrong_currency.reasons


def test_salary_range_crossing_floor_is_unknown() -> None:
    result = MatchingEngine().evaluate(
        _candidate(),
        _job(salary_min=800_000, salary_max=1_200_000),
        _criteria(),
    )
    assert result.status == "needs_review"
    assert "job.salary_range" in result.unknown_fields


def test_missing_candidate_skills_is_unknown_not_a_rejection() -> None:
    result = MatchingEngine().evaluate(
        CandidateSnapshot(), _job(), MatchCriteria(target_titles=("Backend Engineer",))
    )
    assert result.status == "needs_review"
    assert result.unknown_fields == ("candidate.skills",)


def test_skill_matching_uses_term_boundaries() -> None:
    candidate = CandidateSnapshot(skills=("Go",))
    job = _job(description="Build services on Google Cloud.")
    result = MatchingEngine().evaluate(candidate, job, MatchCriteria())

    assert result.status == "eligible"
    skills = next(component for component in result.components if component.name == "skills")
    assert skills.matched_terms == ()
    assert skills.raw_score == 0


def test_rule_set_is_versioned_and_weights_must_sum_to_one_hundred() -> None:
    rules = MatchingRuleSet(
        version="2.1",
        role_weight=50,
        skill_weight=25,
        location_weight=10,
        work_mode_weight=5,
        salary_weight=10,
    )
    result = MatchingEngine().evaluate(_candidate(), _job(), _criteria(), rules)
    assert result.rule_version == "2.1"

    with pytest.raises(ValueError, match="sum to 100"):
        MatchingRuleSet(
            role_weight=50,
            skill_weight=20,
            location_weight=10,
            work_mode_weight=10,
            salary_weight=5,
        )


def test_salary_criteria_requires_explicit_currency() -> None:
    with pytest.raises(ValueError, match="configured together"):
        MatchCriteria(minimum_salary=1_000_000)


def test_invalid_salary_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        _job(salary_min=2_000_000, salary_max=1_000_000)
