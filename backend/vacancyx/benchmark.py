"""Reproducible, loopback-only read API benchmark for local VacancyX installs."""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import math
import os
import platform
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx


@dataclass(frozen=True)
class RequestSample:
    endpoint: str
    elapsed_ms: float
    status_code: int | None
    error_type: str | None


def validate_loopback_url(value: str) -> str:
    """Accept only an HTTP(S) origin that resolves syntactically to loopback."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("API URL must be an HTTP(S) loopback origin.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("API URL must not contain credentials, query, or fragment.")
    if parsed.path not in {"", "/"}:
        raise ValueError("API URL must be an origin without a path.")
    hostname = parsed.hostname.casefold()
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if hostname != "localhost":
            raise ValueError("Benchmark requests are restricted to localhost/loopback.")
    else:
        if not address.is_loopback:
            raise ValueError("Benchmark requests are restricted to localhost/loopback.")
    return value.rstrip("/")


def percentile(values: list[float], percent: float) -> float:
    """Return a nearest-rank percentile for a non-empty sample."""
    if not values:
        return 0.0
    if not 0 < percent <= 100:
        raise ValueError("percent must be greater than 0 and at most 100.")
    ordered = sorted(values)
    index = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return round(ordered[index], 3)


def request_routes(candidate_id: str | None, profile_id: str | None) -> list[tuple[str, str]]:
    """Build a stable endpoint mix; optional matching is explicitly candidate-scoped."""
    routes = [
        ("GET", "/health/live"),
        ("GET", "/api/v1/jobs?status=all&limit=50&offset=0"),
    ]
    if candidate_id is not None and profile_id is not None:
        candidate = quote(candidate_id, safe="")
        profile = quote(profile_id, safe="")
        routes.append(
            (
                "POST",
                f"/api/v1/candidates/{candidate}/search-profiles/{profile}/matches"
                "?limit=50&offset=0",
            )
        )
    return routes


def _route_for(index: int, routes: list[tuple[str, str]]) -> tuple[str, str]:
    """Use a repeatable 10-request mix: 10% health, 50% jobs, 40% matching."""
    slot = index % 10
    if len(routes) == 3:
        return routes[0] if slot == 0 else routes[1] if slot < 6 else routes[2]
    return routes[0] if slot < 2 else routes[1]


async def _request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
) -> RequestSample:
    started = time.perf_counter()
    try:
        response = await client.request(method, path)
        elapsed_ms = (time.perf_counter() - started) * 1000
        error_type = "HTTPStatusError" if response.status_code >= 400 else None
        endpoint = path.split("?", maxsplit=1)[0]
        return RequestSample(endpoint, elapsed_ms, response.status_code, error_type)
    except httpx.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return RequestSample(path.split("?", maxsplit=1)[0], elapsed_ms, None, type(exc).__name__)


async def _run_phase(
    client: httpx.AsyncClient,
    routes: list[tuple[str, str]],
    request_count: int,
    concurrency: int,
) -> list[RequestSample]:
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(index: int) -> RequestSample:
        method, path = _route_for(index, routes)
        async with semaphore:
            return await _request(client, method, path)

    return list(await asyncio.gather(*(run_one(index) for index in range(request_count))))


def _summarize(samples: list[RequestSample], elapsed_seconds: float) -> dict[str, object]:
    latencies = [sample.elapsed_ms for sample in samples]
    errors = [sample for sample in samples if sample.error_type is not None]
    status_codes = Counter(
        str(sample.status_code) for sample in samples if sample.status_code is not None
    )
    error_types = Counter(sample.error_type for sample in errors)
    return {
        "requests": len(samples),
        "errors": len(errors),
        "error_rate_percent": round(100 * len(errors) / len(samples), 3) if samples else 0.0,
        "throughput_requests_per_second": round(len(samples) / elapsed_seconds, 3)
        if elapsed_seconds > 0
        else 0.0,
        "latency_ms": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "max": round(max(latencies), 3) if latencies else 0.0,
        },
        "status_codes": dict(sorted(status_codes.items())),
        "errors_by_type": dict(sorted(error_types.items())),
    }


async def run_benchmark(args: argparse.Namespace, base_url: str) -> dict[str, object]:
    routes = request_routes(args.candidate_id, args.profile_id)
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        follow_redirects=False,
        limits=httpx.Limits(
            max_connections=args.concurrency,
            max_keepalive_connections=args.concurrency,
        ),
    ) as client:
        warmup = await _run_phase(client, routes, args.warmup, args.concurrency)
        cpu_started = time.process_time()
        started = time.perf_counter()
        samples = await _run_phase(client, routes, args.requests, args.concurrency)
        elapsed_seconds = time.perf_counter() - started
        client_cpu_seconds = time.process_time() - cpu_started

    by_endpoint_samples: dict[str, list[RequestSample]] = defaultdict(list)
    for sample in samples:
        by_endpoint_samples[sample.endpoint].append(sample)

    database_size: int | None = None
    if args.database_path is not None:
        database_path = args.database_path.expanduser()
        if database_path.is_file():
            database_size = database_path.stat().st_size

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        check=False,
        text=True,
    ).stdout.strip() or "unknown"
    return {
        "metadata": {
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "commit": commit,
            "api_url": base_url,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "database_size_bytes": database_size,
            "requests": args.requests,
            "warmup_requests": args.warmup,
            "concurrency": args.concurrency,
            "timeout_seconds": args.timeout,
            "endpoint_mix": [method + " " + path for method, path in routes],
        },
        "warmup": {
            "requests": len(warmup),
            "errors": sum(sample.error_type is not None for sample in warmup),
        },
        "summary": _summarize(samples, elapsed_seconds),
        "by_endpoint": {
            endpoint: _summarize(endpoint_samples, elapsed_seconds)
            for endpoint, endpoint_samples in sorted(by_endpoint_samples.items())
        },
        "client_cpu_seconds": round(client_cpu_seconds, 3),
        "note": (
            "Client-side API measurements only. This does not measure source-fetch/browser "
            "throughput or server CPU/RSS, and results must not be extrapolated to a cluster."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark a local VacancyX read API.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--database-path", type=Path)
    parser.add_argument("--candidate-id")
    parser.add_argument("--profile-id")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a bounded, read-only benchmark against a loopback API."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        base_url = validate_loopback_url(args.api_url)
    except ValueError as exc:
        parser.error(str(exc))
    if args.requests < 1 or args.requests > 10_000:
        parser.error("--requests must be between 1 and 10000.")
    if args.warmup < 0 or args.warmup > 10_000:
        parser.error("--warmup must be between 0 and 10000.")
    if args.concurrency < 1 or args.concurrency > 2_000:
        parser.error("--concurrency must be between 1 and 2000.")
    if args.timeout <= 0:
        parser.error("--timeout must be positive.")
    if bool(args.candidate_id) != bool(args.profile_id):
        parser.error("--candidate-id and --profile-id must be supplied together.")

    result = asyncio.run(run_benchmark(args, base_url))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.expanduser().write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
