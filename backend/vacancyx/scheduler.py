"""Local process that turns due recurring discovery schedules into durable tasks."""

from __future__ import annotations

import argparse
import logging
import threading
from collections.abc import Sequence

from vacancyx.config import get_settings
from vacancyx.db.session import get_session_factory
from vacancyx.services.discovery_scheduler import DiscoveryScheduler
from vacancyx.sources.factory import build_source_registry

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local scheduler; the separate vacancyx-worker executes queued tasks."""
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the local VacancyX discovery scheduler.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Enqueue due schedules once, then exit.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=30.0,
        help="Seconds between due-schedule checks (default: 30).",
    )
    args = parser.parse_args(argv)
    if args.poll_interval <= 0:
        parser.error("--poll-interval must be positive.")

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    source_registry = build_source_registry(settings)
    scheduler = DiscoveryScheduler(
        get_session_factory(),
        lambda: set(source_registry.enabled_source_keys()),
    )

    def run_once() -> int:
        enqueued = scheduler.run_due_once()
        if enqueued:
            logger.info("Enqueued scheduled discovery tasks", extra={"task_count": enqueued})
        return enqueued

    if args.once:
        run_once()
        return 0

    stop = threading.Event()
    logger.info("Discovery scheduler started")
    try:
        while not stop.is_set():
            run_once()
            stop.wait(args.poll_interval)
    except KeyboardInterrupt:
        logger.info("Discovery scheduler shutdown requested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
