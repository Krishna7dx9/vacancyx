"""Public Greenhouse Job Board API adapter."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import httpx

from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import SourceCapabilities, SourceListing, SourcePage
from vacancyx.sources.policy import read_bounded_response, validate_source_url


class GreenhouseJobBoardAdapter:
    """Read published jobs from a configured public Greenhouse board."""

    capabilities = SourceCapabilities(
        pagination=True,
        published_at=False,
        salary=False,
        work_mode=False,
        employment_type=False,
    )

    def __init__(
        self,
        *,
        source_key: str,
        board_token: str,
        company_name: str,
        config: SourceConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.source_key = source_key
        self._board_token = board_token
        self._company_name = company_name
        self._config = config
        self._transport = transport

    async def fetch_page(self, *, cursor: str | None, page_size: int) -> SourcePage:
        """Fetch one public board page, following only allowlisted HTTPS next links."""
        initial_url = (
            "https://boards-api.greenhouse.io/v1/boards/"
            + self._board_token
            + "/jobs?content=true"
        )
        url = cursor or initial_url
        validate_source_url(url, self._config)

        async with httpx.AsyncClient(
            timeout=self._config.timeout_seconds,
            headers={
                "User-Agent": self._config.user_agent,
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                body = await read_bounded_response(
                    response,
                    max_bytes=self._config.max_response_bytes,
                )
                link_header = response.headers.get("Link")
                response_url = str(response.url)

        payload: Any = json.loads(body)
        raw_jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(raw_jobs, list):
            raise ValueError("Greenhouse response did not contain a jobs list.")
        if len(raw_jobs) > 100:
            raise ValueError("Greenhouse response exceeded the normalized page limit.")

        listings: list[SourceListing] = []
        for raw in raw_jobs:
            if not isinstance(raw, dict):
                raise ValueError("Greenhouse returned an invalid job record.")
            location = raw.get("location")
            location_name = location.get("name") if isinstance(location, dict) else None
            listings.append(
                SourceListing(
                    external_id=str(raw["id"]),
                    title=str(raw["title"]),
                    company_name=self._company_name,
                    source_url=str(raw["absolute_url"]),
                    description=raw.get("content"),
                    location=location_name,
                )
            )

        next_cursor = self._next_link(link_header, response_url)
        if next_cursor is not None:
            validate_source_url(next_cursor, self._config)
        return SourcePage(items=tuple(listings), next_cursor=next_cursor)

    @staticmethod
    def _next_link(link_header: str | None, response_url: str) -> str | None:
        if not link_header:
            return None
        for part in link_header.split(","):
            lowered = part.casefold()
            if 'rel="next"' not in lowered and "rel=next" not in lowered:
                continue
            left = part.find("<")
            right = part.find(">", left + 1)
            if left < 0 or right < 0:
                continue
            return urljoin(response_url, part[left + 1 : right])
        return None
