"""Safety tests for the human-supervised browser assistance policy."""
import pytest

from vacancyx.services.browser_assist import (
    BrowserAssistPolicyError, PortalField, build_fill_plan,
    detect_manual_interruption, validate_portal_url,
)


def test_portal_url_requires_exact_allowlisted_https_host() -> None:
    assert validate_portal_url(
        "https://jobs.example.test/apply/123", {"jobs.example.test"}
    ) == "https://jobs.example.test/apply/123"
    for url in (
        "http://jobs.example.test/apply",
        "https://sub.jobs.example.test/apply",
        "https://jobs.example.test.evil.test/apply",
        "https://user:secret@jobs.example.test/apply",
        "https://jobs.example.test:8443/apply",
    ):
        with pytest.raises(BrowserAssistPolicyError):
            validate_portal_url(url, {"jobs.example.test"})


def test_fill_plan_maps_only_known_safe_text_fields() -> None:
    plan = build_fill_plan(
        [
            PortalField("applicant_name", "Full name", required=True),
            PortalField("email_input", "Email address", "email", required=True),
            PortalField("legal", "I certify that the information is true", "checkbox", True),
            PortalField("unknown", "Why should we hire you?", "textarea"),
            PortalField("password", "Password", "password"),
        ],
        {"candidate": {"display_name": "Synthetic Candidate", "email": "candidate@example.test"}},
    )
    assert [(item.field_name, item.value) for item in plan.fields] == [
        ("applicant_name", "Synthetic Candidate"),
        ("email_input", "candidate@example.test"),
    ]
    assert plan.skipped_fields == ("legal", "unknown", "password")
    assert plan.manual_review_reasons == ("required_choice_needs_human_review",)


def test_missing_required_candidate_data_is_not_guessed() -> None:
    plan = build_fill_plan(
        [PortalField("phone", "Phone number", "tel", required=True)], {"candidate": {}}
    )
    assert plan.fields == ()
    assert plan.manual_review_reasons == ("required_candidate_data_missing",)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Please complete the reCAPTCHA", ("captcha_required",)),
        ("Sign in to continue with your application", ("authentication_required",)),
        ("Enter your one-time password", ("multi_factor_required",)),
        ("I certify that all information is accurate", ("legal_attestation_required",)),
        ("Welcome to the application", ()),
    ],
)
def test_manual_interruption_detection(text: str, expected: tuple[str, ...]) -> None:
    assert detect_manual_interruption(text) == expected
