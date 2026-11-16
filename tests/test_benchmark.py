"""Unit tests for the local API benchmark's safety and reporting helpers."""

import pytest

from vacancyx.benchmark import (
    RequestSample,
    _route_for,
    _summarize,
    percentile,
    request_routes,
    validate_loopback_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000",
        "http://localhost:8000/",
        "https://[::1]:8443",
    ],
)
def test_benchmark_accepts_loopback_origins(url: str) -> None:
    assert validate_loopback_url(url).rstrip("/") == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://192.168.1.20:8000",
        "http://127.0.0.1:8000/api",
        "http://user:password@127.0.0.1:8000",
        "http://127.0.0.1:8000?token=secret",
    ],
)
def test_benchmark_rejects_non_loopback_or_non_origin_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_loopback_url(url)


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([5, 1, 4, 2, 3], 50) == 3
    assert percentile([5, 1, 4, 2, 3], 95) == 5
    assert percentile([], 95) == 0


def test_request_mix_includes_matching_only_when_both_ids_are_supplied() -> None:
    assert len(request_routes(None, None)) == 2
    routes = request_routes("candidate/id", "profile id")
    assert len(routes) == 3
    assert "candidate%2Fid" in routes[2][1]
    assert "profile%20id" in routes[2][1]
    assert _route_for(0, routes) == routes[0]
    assert _route_for(1, routes) == routes[1]
    assert _route_for(6, routes) == routes[2]


def test_summary_reports_latency_throughput_status_and_errors() -> None:
    samples = [
        RequestSample("/health/live", 2.0, 200, None),
        RequestSample("/api/v1/jobs", 4.0, 200, None),
        RequestSample("/api/v1/jobs", 8.0, 503, "HTTPStatusError"),
    ]
    summary = _summarize(samples, 2.0)
    assert summary["requests"] == 3
    assert summary["errors"] == 1
    assert summary["throughput_requests_per_second"] == 1.5
    assert summary["latency_ms"] == {"p50": 4.0, "p95": 8.0, "p99": 8.0, "max": 8.0}
    assert summary["status_codes"] == {"200": 2, "503": 1}
