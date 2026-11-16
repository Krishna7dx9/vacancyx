"""Tests for local worker and scheduler process liveness files."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from vacancyx.process_heartbeat import ProcessHeartbeat, read_process_heartbeats


def test_process_heartbeat_publishes_running_then_stopped(tmp_path) -> None:
    heartbeat = ProcessHeartbeat(
        tmp_path,
        "worker",
        instance_name="test-worker",
        interval_seconds=0.02,
    )
    heartbeat.start()
    running = read_process_heartbeats(tmp_path)
    assert len(running) == 1
    assert running[0]["role"] == "worker"
    assert running[0]["instance_name"] == "test-worker"
    assert running[0]["status"] == "running"
    assert running[0]["pid"] > 0

    heartbeat.stop()
    stopped = read_process_heartbeats(tmp_path)
    assert len(stopped) == 1
    assert stopped[0]["status"] == "stopped"


def test_reader_marks_old_running_process_stale_and_ignores_corrupt_files(tmp_path) -> None:
    directory = tmp_path / "runtime" / "heartbeats"
    directory.mkdir(parents=True)
    old = datetime.now(UTC) - timedelta(minutes=5)
    (directory / "worker-old.json").write_text(
        json.dumps(
            {
                "role": "worker",
                "instance_id": "old",
                "instance_name": "old-worker",
                "pid": 123,
                "hostname": "test-host",
                "status": "running",
                "started_at": old.isoformat(),
                "last_heartbeat_at": old.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    (directory / "scheduler-corrupt.json").write_text("{", encoding="utf-8")

    records = read_process_heartbeats(tmp_path, stale_after_seconds=45)
    assert len(records) == 1
    assert records[0]["status"] == "stale"
    assert records[0]["age_seconds"] >= 300


def test_process_heartbeat_rejects_unknown_role_and_invalid_interval(tmp_path) -> None:
    with pytest.raises(ValueError, match="role"):
        ProcessHeartbeat(tmp_path, "api", instance_name="api")
    with pytest.raises(ValueError, match="interval"):
        ProcessHeartbeat(tmp_path, "worker", instance_name="worker", interval_seconds=0)
