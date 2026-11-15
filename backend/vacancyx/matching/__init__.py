"""Candidate-independent, explainable job matching domain."""

from vacancyx.matching.criteria import CandidateSnapshot, JobSnapshot, MatchCriteria, MatchingRuleSet
from vacancyx.matching.engine import MatchResult, MatchingEngine, ScoreComponent

__all__ = [
    "CandidateSnapshot",
    "JobSnapshot",
    "MatchCriteria",
    "MatchResult",
    "MatchingEngine",
    "MatchingRuleSet",
    "ScoreComponent",
]
