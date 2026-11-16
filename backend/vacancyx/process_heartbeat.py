"""Atomic local process heartbeats for the worker and recurring scheduler."""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ProcessHeartbeat:
    """Publish liveness for one local process without writing candidate data."""

    def __init__(
        self,
        storage_dir: Path,
        role: str,
        *,
        instance_name: str,
        interval_seconds: float = 10.0,
    ) -> None:
        if role not in {"worker", "scheduler"}:
            raise ValueError("role must be worker or scheduler.")
        if not instance_name.strip() or len(instance_name) > 120:
            raise ValueError("instance_name must contain 1 to 120 characters.")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive.")
        self.role = role
        self.instance_id = uuid4().hex
        self.instance_name = instance_name
        self.interval_seconds = interval_seconds
        self.started_at = datetime.now(UTC)
        self._directory = storage_dir / "runtime" / "heartbeats"
        self._path = self._directory / f"{role}-{self.instance_id}.json"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = "running"

    def start(self) -> None:
        """Write an initial heartbeat and refresh it until stop is called."""
        if self._thread is not None:
            raise RuntimeError("Process heartbeat has already been started.")
        self._write()
        self._thread = threading.Thread(
            target=self._run,
            name=f"vacancyx-{self.role}-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop refreshing and publish a final stopped state."""
        if self._thread is None:
            return
        self._status = "stopped"
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.interval_seconds + 1.0))
        self._write()
        self._thread = None

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self._write()
            except OSError:
                logger.exception("Could not publish local process heartbeat")

    def _write(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "role": self.role,
            "instance_id": self.instance_id,
            "instance_name": self.instance_name,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "status": self._status,
            "started_at": self.started_at.isoformat(),
            "last_heartbeat_at": datetime.now(UTC).isoformat(),
        }
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            logger.debug("Could not restrict heartbeat file permissions", exc_info=True)
        os.replace(temporary, self._path)


def read_process_heartbeats(
    storage_dir: Path,
    *,
    stale_after_seconds: int = 45,
) -> list[dict[str, Any]]:
    """Read bounded, validated process metadata and classify missed heartbeats."""
    directory = storage_dir / "runtime" / "heartbeats"
    if not directory.is_dir():
        return []

    now = datetime.now(UTC)
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("role") not in {"worker", "scheduler"}:
                continue
            last_heartbeat = datetime.fromisoformat(payload["last_heartbeat_at"])
            started_at = datetime.fromisoformat(payload["started_at"])
            if last_heartbeat.tzinfo is None or started_at.tzinfo is None:
                continue
            age_seconds = max(0, int((now - last_heartbeat).total_seconds()))
            status = payload.get("status")
            if status == "running" and age_seconds > stale_after_seconds:
                status = "stale"
            if status not in {"running", "stopped", "stale"}:
                continue
            records.append(
                {
                    "role": payload["role"],
                    "instance_id": str(payload["instance_id"]),
                    "instance_name": str(payload["instance_name"]),
                    "pid": int(payload["pid"]),
                    "hostname": str(payload["hostname"]),
                    "status": status,
                    "started_at": started_at,
                    "last_heartbeat_at": last_heartbeat,
                    "age_seconds": age_seconds,
                }
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            logger.warning("Ignoring invalid local process heartbeat file: %s", path.name)
    return records
