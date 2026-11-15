"""Runtime configuration validation tests."""

import pytest
from pydantic import ValidationError

from vacancyx.config import Settings


def test_worker_settings_have_local_safe_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.worker_poll_interval_seconds == 2.0
    assert settings.worker_lease_seconds == 60
    assert settings.worker_retry_base_delay_seconds == 5
    assert settings.worker_retry_max_delay_seconds == 300


def test_worker_retry_maximum_cannot_be_below_base() -> None:
    with pytest.raises(ValidationError, match="worker retry maximum delay"):
        Settings(
            _env_file=None,
            worker_retry_base_delay_seconds=20,
            worker_retry_max_delay_seconds=10,
        )
