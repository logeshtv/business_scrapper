from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.schemas import Business, ScrapeError, ScrapeMeta
from app.scraper.extractor import ListingExtractor
from app.scraper.fetcher import AsyncFetcher
from app.scraper.utils import strip_text


class ScraperCoordinator:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._logger = get_logger(component="ScraperCoordinator")
        self._fetcher = AsyncFetcher(settings)

    async def close(self) -> None:
        await self._fetcher.aclose()

    async def scrape(self, urls: list[str], max_concurrency: int | None = None) -> tuple[list[Business], list[ScrapeError], ScrapeMeta]:
        start_time = time.perf_counter()
        max_urls = self._settings.request_max_urls
        target_urls = urls[:max_urls]
        errors: list[ScrapeError] = []
        businesses: list[Business] = []

        async for target_url, outcome in self._fetcher.fetch_many(target_urls, max_concurrency):
            if isinstance(outcome, Exception):
                errors.append(
                    ScrapeError(url=target_url, message=str(outcome), stage="fetch")
                )
                continue
            try:
                extractor = ListingExtractor(outcome.text, outcome.final_url, settings=self._settings)
                records = extractor.extract()
                businesses.extend(self._normalise_records(records))
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    ScrapeError(url=outcome.final_url or target_url, message=str(exc), stage="parse")
                )

        deduped = self._deduplicate_businesses(businesses)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        meta = ScrapeMeta(
            totalRequested=len(target_urls),
            totalSucceeded=len(target_urls) - len(errors),
            totalBusinesses=len(deduped),
            durationMs=duration_ms,
        )
        return deduped, errors, meta

    def _normalise_records(self, records: Iterable[dict[str, Any]]) -> Iterable[Business]:
        for record in records:
            try:
                business = Business(**record)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning("Failed to normalise record", error=str(exc), record_keys=list(record.keys()))
                continue
            yield business

    def _deduplicate_businesses(self, businesses: Iterable[Business]) -> list[Business]:
        seen: dict[str, Business] = {}
        for business in businesses:
            key = strip_text(business.listingUrl) or strip_text(business.title)
            if not key:
                continue
            lowered = key.lower()
            if lowered in seen:
                continue
            seen[lowered] = business
        return list(seen.values())
