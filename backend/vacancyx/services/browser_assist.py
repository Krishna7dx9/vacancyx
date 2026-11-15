"""Safety policy for human-supervised employer portal assistance.

This module deliberately plans form fills; it never submits an application,
clicks legal attestations, bypasses access controls, or treats navigation as
proof of submission.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


class BrowserAssistPolicyError(ValueError):
    """A portal or application is outside the supported safety policy."""


@dataclass(frozen=True)
class PortalField:
    """A field descriptor obtained from a portal's accessible form metadata."""
    name: str
    label: str
    field_type: str = "text"
    required: bool = False


@dataclass(frozen=True)
class PlannedField:
    """A deterministic mapping from a known portal field to candidate data."""
    field_name: str
    label: str
    value: str


@dataclass(frozen=True)
class FillPlan:
    """Reviewable plan; no browser action has been performed."""
    fields: tuple[PlannedField, ...]
    skipped_fields: tuple[str, ...]
    manual_review_reasons: tuple[str, ...]


_BLOCKER_TERMS: dict[str, tuple[str, ...]] = {
    "captcha_required": ("captcha", "recaptcha", "hcaptcha", "verify you are human"),
    "authentication_required": ("sign in", "log in", "password", "create an account"),
    "multi_factor_required": ("one-time password", "verification code", "authenticator"),
    "legal_attestation_required": (
        "I certify", "I hereby declare", "agree to the terms",
        "legally authorized", "equal opportunity",
    ),
}

_CANDIDATE_KEYS: dict[str, tuple[str, ...]] = {
    "name": ("display_name",),
    "full name": ("display_name",),
    "first name": ("first_name",),
    "last name": ("last_name",),
    "email": ("email",),
    "email address": ("email",),
    "phone": ("phone",),
    "phone number": ("phone",),
    "location": ("location",),
    "city": ("city",),
}


def validate_portal_url(url: str, allowed_hosts: set[str]) -> str:
    """Accept HTTPS URLs only when the exact hostname is explicitly allowed."""
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as error:
        raise BrowserAssistPolicyError("The employer portal URL is invalid.") from error
    normalized_hosts = {host.lower().rstrip(".") for host in allowed_hosts}
    if (
        parsed.scheme != "https" or not hostname or hostname not in normalized_hosts
        or parsed.username is not None or parsed.password is not None
        or port not in (None, 443)
    ):
        raise BrowserAssistPolicyError(
            "This portal is not in the explicitly configured HTTPS host allowlist."
        )
    return url


def detect_manual_interruption(page_text: str) -> tuple[str, ...]:
    """Return safety blockers that require a person to take over."""
    normalized = " ".join(page_text.casefold().split())
    matches = [
        code for code, phrases in _BLOCKER_TERMS.items()
        if any(phrase.casefold() in normalized for phrase in phrases)
    ]
    # "One-time password" also contains the generic password keyword. Report
    # the more actionable MFA reason rather than two overlapping categories.
    if "multi_factor_required" in matches and "authentication_required" in matches:
        matches.remove("authentication_required")
    return tuple(matches)


def build_fill_plan(fields: list[PortalField], candidate_snapshot: dict[str, Any]) -> FillPlan:
    """Map only recognized, ordinary text fields; never infer legal answers."""
    candidate = candidate_snapshot.get("candidate", {})
    if not isinstance(candidate, dict):
        candidate = {}
    planned: list[PlannedField] = []
    skipped: list[str] = []
    reasons: list[str] = []
    for field in fields:
        field_type = field.field_type.casefold()
        label = " ".join(field.label.casefold().split())
        keys = _CANDIDATE_KEYS.get(label, ())
        value: Any = None
        for key in keys:
            value = candidate.get(key)
            if value is not None and str(value).strip():
                break
        if field_type not in {"text", "email", "tel"} or not keys:
            skipped.append(field.name)
            if field.required and field_type in {"checkbox", "radio", "select"}:
                reasons.append("required_choice_needs_human_review")
            continue
        if value is None or not str(value).strip():
            skipped.append(field.name)
            if field.required:
                reasons.append("required_candidate_data_missing")
            continue
        planned.append(PlannedField(field.name, field.label, str(value)))
    return FillPlan(
        fields=tuple(planned),
        skipped_fields=tuple(skipped),
        manual_review_reasons=tuple(sorted(set(reasons))),
    )
