"""Deterministic eligibility and explainable ranking engine."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vacancyx.matching.criteria import (
    CandidateSnapshot,
    JobSnapshot,
    MatchCriteria,
    MatchingRuleSet,
)


class ScoreComponent(BaseModel):
    """One normalized scoring dimension with an auditable explanation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    weight: int = Field(ge=0, le=100)
    raw_score: float = Field(ge=0, le=1)
    points: float = Field(ge=0, le=100)
    explanation: str
    matched_terms: tuple[str, ...] = ()


class MatchResult(BaseModel):
    """Eligibility, score and reasons produced by one specific rule-set version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["eligible", "ineligible", "needs_review"]
    score: float = Field(ge=0, le=100)
    rule_version: str
    reasons: tuple[str, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    components: tuple[ScoreComponent, ...] = ()


class MatchingEngine:
    """Pure matching engine: no database, network, clock or candidate-specific defaults."""

    def evaluate(
        self,
        candidate: CandidateSnapshot,
        job: JobSnapshot,
        criteria: MatchCriteria,
        rules: MatchingRuleSet | None = None,
    ) -> MatchResult:
        """Evaluate hard constraints first, then rank using only available dimensions."""
        rule_set = rules or MatchingRuleSet()
        reasons: list[str] = []
        unknown_fields: set[str] = set()
        hard_failures: list[str] = []
        components: list[ScoreComponent] = []
        job_text = " ".join(part for part in (job.title, job.description or "") if part)
        searchable_text = " ".join(
            part for part in (job.title, job.company_name, job.description or "") if part
        )

        if job.status.casefold() != "open":
            hard_failures.append("job_not_open")

        excluded = self._matching_terms(criteria.excluded_keywords, searchable_text)
        hard_failures.extend(f"excluded_keyword:{term}" for term in excluded)

        if criteria.required_skills:
            if job.description is None:
                unknown_fields.add("job.description")
            else:
                missing = tuple(
                    skill
                    for skill in criteria.required_skills
                    if not self._contains_term(skill, job_text)
                )
                if missing:
                    hard_failures.append("required_skills_missing:" + ",".join(missing))

        if criteria.allowed_locations:
            if job.location is None:
                unknown_fields.add("job.location")
            elif not self._matching_terms(criteria.allowed_locations, job.location):
                hard_failures.append("location_not_allowed")
            else:
                self._add_component(
                    components,
                    "location",
                    rule_set.location_weight,
                    1.0,
                    "Job location matches an allowed location.",
                )

        if criteria.work_modes:
            if job.work_mode is None:
                unknown_fields.add("job.work_mode")
            elif job.work_mode.casefold() not in {mode.casefold() for mode in criteria.work_modes}:
                hard_failures.append("work_mode_not_allowed")
            else:
                self._add_component(
                    components,
                    "work_mode",
                    rule_set.work_mode_weight,
                    1.0,
                    "Work mode matches a configured preference.",
                )

        if criteria.employment_types:
            if job.employment_type is None:
                unknown_fields.add("job.employment_type")
            elif job.employment_type.casefold() not in {
                item.casefold() for item in criteria.employment_types
            }:
                hard_failures.append("employment_type_not_allowed")

        if criteria.minimum_salary is not None:
            salary_reason = self._evaluate_salary(job, criteria, rule_set, components)
            if salary_reason == "unknown":
                unknown_fields.add("job.salary_range")
            elif salary_reason is not None:
                hard_failures.append(salary_reason)

        if criteria.target_titles:
            matched_titles = self._matching_terms(criteria.target_titles, job.title)
            raw_score = len(matched_titles) / len(criteria.target_titles)
            self._add_component(
                components,
                "role",
                rule_set.role_weight,
                raw_score,
                "Matched configured role keywords in the job title.",
                matched_titles,
            )

        if candidate.skills:
            if job.description is None:
                unknown_fields.add("job.description")
            else:
                matched_skills = self._matching_terms(candidate.skills, job_text)
                raw_score = len(matched_skills) / len(candidate.skills)
                self._add_component(
                    components,
                    "skills",
                    rule_set.skill_weight,
                    raw_score,
                    "Candidate skills found in the job title or description.",
                    matched_skills,
                )
        else:
            unknown_fields.add("candidate.skills")

        available_weight = sum(component.weight for component in components)
        earned_points = sum(component.points for component in components)
        score = round(earned_points / available_weight * 100, 2) if available_weight else 0.0

        reasons.extend(hard_failures)
        reasons.extend(
            f"{component.name}_match:{','.join(component.matched_terms)}"
            if component.matched_terms
            else f"{component.name}_score:{component.raw_score:.2f}"
            for component in components
        )
        if unknown_fields:
            reasons.append("insufficient_data_for_some_checks")

        if hard_failures:
            status: Literal["eligible", "ineligible", "needs_review"] = "ineligible"
        elif unknown_fields:
            status = "needs_review"
        else:
            status = "eligible"

        return MatchResult(
            status=status,
            score=score,
            rule_version=rule_set.version,
            reasons=tuple(reasons),
            unknown_fields=tuple(sorted(unknown_fields)),
            components=tuple(components),
        )

    @staticmethod
    def _contains_term(term: str, text: str) -> bool:
        pattern = rf"(?<!\w){re.escape(term.strip())}(?!\w)"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    @classmethod
    def _matching_terms(cls, terms: tuple[str, ...], text: str) -> tuple[str, ...]:
        return tuple(term for term in terms if cls._contains_term(term, text))

    @staticmethod
    def _add_component(
        components: list[ScoreComponent],
        name: str,
        weight: int,
        raw_score: float,
        explanation: str,
        matched_terms: tuple[str, ...] = (),
    ) -> None:
        if weight == 0:
            return
        components.append(
            ScoreComponent(
                name=name,
                weight=weight,
                raw_score=raw_score,
                points=round(weight * raw_score, 2),
                explanation=explanation,
                matched_terms=matched_terms,
            )
        )

    @classmethod
    def _evaluate_salary(
        cls,
        job: JobSnapshot,
        criteria: MatchCriteria,
        rules: MatchingRuleSet,
        components: list[ScoreComponent],
    ) -> str | None:
        minimum_salary = criteria.minimum_salary
        currency = criteria.salary_currency
        if minimum_salary is None or currency is None:
            return None
        if job.salary_currency is None:
            return "unknown"
        if job.salary_currency.upper() != currency:
            return "salary_currency_mismatch"
        if job.salary_max is not None and job.salary_max < minimum_salary:
            return "salary_below_minimum"
        if job.salary_min is None or job.salary_min < minimum_salary:
            return "unknown"
        cls._add_component(
            components,
            "salary",
            rules.salary_weight,
            1.0,
            "Published salary minimum meets the configured floor.",
        )
        return None
