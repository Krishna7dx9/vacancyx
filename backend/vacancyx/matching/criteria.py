"""Versioned matching inputs and rule configuration."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CandidateSnapshot(BaseModel):
    """Only candidate attributes needed by the matching engine; no contact details."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skills: tuple[str, ...] = Field(default=(), max_length=100)

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = [value.strip() for value in values if value.strip()]
        return tuple(dict.fromkeys(normalized))


class JobSnapshot(BaseModel):
    """Stable job facts consumed by matching, independent of SQLAlchemy entities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=240)
    company_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=100_000)
    location: str | None = Field(default=None, max_length=240)
    work_mode: str | None = Field(default=None, max_length=30)
    employment_type: str | None = Field(default=None, max_length=40)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: str = "open"

    @model_validator(mode="after")
    def validate_salary_range(self) -> "JobSnapshot":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot exceed salary_max.")
        return self


class MatchCriteria(BaseModel):
    """Explicit search constraints configured independently for each candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_titles: tuple[str, ...] = Field(default=(), max_length=50)
    excluded_keywords: tuple[str, ...] = Field(default=(), max_length=100)
    required_skills: tuple[str, ...] = Field(default=(), max_length=100)
    allowed_locations: tuple[str, ...] = Field(default=(), max_length=50)
    work_modes: tuple[str, ...] = Field(default=(), max_length=10)
    employment_types: tuple[str, ...] = Field(default=(), max_length=10)
    minimum_salary: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator(
        "target_titles",
        "excluded_keywords",
        "required_skills",
        "allowed_locations",
        "work_modes",
        "employment_types",
    )
    @classmethod
    def normalize_terms(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = [value.strip() for value in values if value.strip()]
        return tuple(dict.fromkeys(normalized))

    @field_validator("salary_currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def validate_salary_currency_pair(self) -> "MatchCriteria":
        if (self.minimum_salary is None) != (self.salary_currency is None):
            raise ValueError("minimum_salary and salary_currency must be configured together.")
        return self


class MatchingRuleSet(BaseModel):
    """Versioned scoring weights; the weights must form a 100-point scale."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(default="1.0", min_length=1, max_length=30)
    role_weight: int = Field(default=35, ge=0, le=100)
    skill_weight: int = Field(default=35, ge=0, le=100)
    location_weight: int = Field(default=10, ge=0, le=100)
    work_mode_weight: int = Field(default=10, ge=0, le=100)
    salary_weight: int = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def weights_must_total_one_hundred(self) -> "MatchingRuleSet":
        total = (
            self.role_weight
            + self.skill_weight
            + self.location_weight
            + self.work_mode_weight
            + self.salary_weight
        )
        if total != 100:
            raise ValueError("Matching rule weights must sum to 100.")
        return self
