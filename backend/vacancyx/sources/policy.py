"""Central URL, timeout, concurrency and request-rate safeguards for adapters."""

import asyncio
import ipaddress
from collections.abc import Awaitable, Callable
from typing import TypeVar
from urllib.parse import urlsplit

from vacancyx.sources.config import SourceConfig

T = TypeVar("T")


class SourcePolicyError(ValueError):
    """Raised when a source request violates its configured access policy."""


def validate_source_url(url: str, config: SourceConfig) -> str:
    """Require HTTPS and an exact or subdomain match against configured public hosts."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise SourcePolicyError("Malformed source URL.") from exc

    if parsed.scheme.lower() != "https" or hostname is None:
        raise SourcePolicyError("Source URLs must use HTTPS and include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise SourcePolicyError("Credentials are not allowed in source URLs.")
    if port not in (None, 443):
        raise SourcePolicyError("Only the default HTTPS port is allowed.")

    host = hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise SourcePolicyError("IP-literal source URLs are not allowed.")

    if host == "localhost" or host.endswith(".localhost") or "." not in host:
        raise SourcePolicyError("Local and single-label hosts are not allowed.")

    allowed = any(host == item or host.endswith(f".{item}") for item in config.allowed_hosts)
    if not allowed:
        raise SourcePolicyError("Source URL host is not in the configured allowlist.")
    return url


class AsyncRateLimiter:
    """Serialize admission decisions so requests respect a per-source minimum interval."""

    def __init__(self, requests_per_minute: int) -> None:
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be positive.")
        self._interval = 60.0 / requests_per_minute
        self._lock = asyncio.Lock()
        self._next_allowed_at = 0.0

    async def wait(self) -> None:
        """Wait until this source is allowed to start another request."""
        loop = asyncio.get_running_loop()
        async with self._lock:
            delay = self._next_allowed_at - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_allowed_at = loop.time() + self._interval


class SourceExecutionGate:
    """Bound concurrent adapter work, request rate and per-request duration."""

    def __init__(self, config: SourceConfig) -> None:
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self._rate_limiter = AsyncRateLimiter(config.requests_per_minute)

    async def execute(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Run one adapter operation under configured limits."""
        async with self._semaphore:
            await self._rate_limiter.wait()
            return await asyncio.wait_for(operation(), timeout=self._config.timeout_seconds)
