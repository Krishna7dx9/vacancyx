"""Unit tests for the headed browser runner's safe field inventory and fill behavior."""
from typing import Any

from vacancyx.services.browser_runner import (
    fill_planned_fields,
    portal_fields_from_metadata,
)
from vacancyx.services.browser_assist import build_fill_plan


def test_portal_metadata_becomes_narrow_field_contract() -> None:
    fields = portal_fields_from_metadata(
        [
            {"index": 0, "label": "Full name", "field_type": "text", "required": True},
            {"index": 1, "label": "Password", "field_type": "password", "required": True},
        ]
    )
    assert [(field.name, field.label, field.field_type) for field in fields] == [
        ("0", "Full name", "text"),
        ("1", "Password", "password"),
    ]


class FakeControl:
    def __init__(self, visible: bool = True) -> None:
        self.visible = visible
        self.value: str | None = None

    def is_visible(self) -> bool:
        return self.visible

    def fill(self, value: str) -> None:
        self.value = value


class FakeLocator:
    def __init__(self, controls: list[FakeControl]) -> None:
        self.controls = controls

    def nth(self, index: int) -> FakeControl:
        return self.controls[index]


def test_runner_fills_only_planned_visible_fields() -> None:
    fields = portal_fields_from_metadata(
        [
            {"index": 0, "label": "Full name", "field_type": "text"},
            {"index": 1, "label": "Email", "field_type": "email"},
        ]
    )
    plan = build_fill_plan(
        fields,
        {"candidate": {"display_name": "Synthetic Candidate", "email": "candidate@example.test"}},
    )
    controls = [FakeControl(), FakeControl(visible=False)]
    filled = fill_planned_fields(FakeLocator(controls), plan)
    assert filled == 1
    assert controls[0].value == "Synthetic Candidate"
    assert controls[1].value is None
