"""Public Lever Postings API adapter."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import SourceCapabilities, SourceListing, SourcePage
from vacancyx.sources.policy import read_bounded_response, validate_source_url


class LeverPostingsAdapter:
    """Read published postings from a configured public Lever job site."""

    capabilities = SourceCapabilities(
        pagination=True,
        published_at=True,
        salary=True,
        work_mode=True,
        employment_type=True,
    )

    def __init__(
        self,
        *,
        source_key: str,
        site_slug: str,
        company_name: str,
        config: SourceConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.source_key = source_key
        self._site_slug = site_slug
        self._company_name = company_name
        self._config = config
        self._transport = transport

    async def fetch_page(self, *, cursor: str | None, page_size: int) -> SourcePage:
        """Fetch a bounded page using Lever's opaque numeric skip cursor."""
        try:
            skip = int(cursor) if cursor is not None else 0
        except ValueError as error:
            raise ValueError("Lever pagination cursor must be a non-negative integer.") from error
        if skip < 0:
            raise ValueError("Lever pagination cursor must be a non-negative integer.")

        url = "https://api.lever.co/v0/postings/" + quote(self._site_slug, safe="")
        validate_source_url(url, self._config)
        async with httpx.AsyncClient(
            timeout=self._config.timeout_seconds,
            headers={"User-Agent": self._config.user_agent, "Accept": "application/json"},
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            async with client.stream(
                "GET",
                url,
                params={"mode": "json", "limit": page_size, "skip": skip},
            ) as response:
                response.raise_for_status()
                body = await read_bounded_response(
                    response,
                    max_bytes=self._config.max_response_bytes,
                )

        payload: Any = json.loads(body)
        if not isinstance(payload, list):
            raise ValueError("Lever response did not contain a postings list.")
        if len(payload) > page_size:
            raise ValueError("Lever response exceeded the requested page size.")

        listings: list[SourceListing] = []
        for raw in payload:
            if not isinstance(raw, dict):
                raise ValueError("Lever returned an invalid posting record.")
            categories = raw.get("categories")
            categories = categories if isinstance(categories, dict) else {}
            all_locations = raw.get("allLocations")
            location = categories.get("location")
            if not isinstance(location, str) or not location:
                location = (
                    ", ".join(value for value in all_locations if isinstance(value, str))
                    if isinstance(all_locations, list)
                    else None
                )
            workplace_type = raw.get("workplaceType")
            if isinstance(workplace_type, str):
                normalized_workplace = workplace_type.casefold()
                work_mode = (
                    normalized_workplace
                    if normalized_workplace in {"remote", "hybrid", "onsite"}
                    else None
                )
            else:
                work_mode = None

            salary = raw.get("salaryRange")
            salary = salary if isinstance(salary, dict) else {}
            interval = salary.get("interval")
            annual_salary = isinstance(interval, str) and interval.casefold() in {
                "year",
                "yearly",
                "annual",
                "annually",
                "per year",
            }
            salary_min = self._optional_int(salary.get("min")) if annual_salary else None
            salary_max = self._optional_int(salary.get("max")) if annual_salary else None
            if (
                salary_min is not None
                and salary_max is not None
                and salary_max < salary_min
            ):
                salary_min = None
                salary_max = None
            currency = salary.get("currency")
            salary_currency = (
                currency.upper()
                if annual_salary
                and (salary_min is not None or salary_max is not None)
                and isinstance(currency, str)
                and len(currency) == 3
                else None
            )
            published_at = self._published_at(raw.get("createdAt"))

            listings.append(
                SourceListing(
                    external_id=str(raw["id"]),
                    title=str(raw["text"]),
                    company_name=self._company_name,
                    source_url=str(raw["hostedUrl"]),
                    description=raw.get("descriptionPlain") or raw.get("description"),
                    location=location,
                    work_mode=work_mode,
                    employment_type=categories.get("commitment"),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=salary_currency,
                    published_at=published_at,
                )
            )

        next_cursor = str(skip + len(listings)) if len(listings) == page_size else None
        return SourcePage(items=tuple(listings), next_cursor=next_cursor)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)) and value >= 0:
            return int(value)
        return None

    @staticmethod
    def _published_at(value: Any) -> datetime | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            return None
        return datetime.fromtimestamp(value / 1000, tz=UTC)
