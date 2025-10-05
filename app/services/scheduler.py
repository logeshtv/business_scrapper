from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Iterable

from app.core.logging_config import get_logger
from app.db.session import DatabaseManager
from app.schemas import Business, ScrapeError
from app.scraper.coordinator import ScraperCoordinator
from app.services.repository import BusinessRepository, PersistResult, ScrapeRunSummary
from app.services.ids import new_id


class ScrapeScheduler:
    def __init__(
        self,
        coordinator: ScraperCoordinator,
        db_manager: DatabaseManager,
        interval_hours: float,
        enabled: bool = True,
    ) -> None:
        self._coordinator = coordinator
        self._db_manager = db_manager
        self._interval = max(interval_hours, 0.1)
        self._enabled = enabled
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._logger = get_logger(component="ScrapeScheduler")

    async def start(self) -> None:
        if not self._enabled:
            self._logger.info("Scheduler disabled; not starting")
            return
        if self._task and not self._task.done():
            return
        self._logger.info("Starting scraper scheduler", interval_hours=self._interval)
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="scrape-scheduler")

    async def stop(self) -> None:
        if not self._task:
            return
        self._logger.info("Stopping scraper scheduler")
        self._stop_event.set()
        await self._task
        self._task = None

    async def trigger_now(self) -> None:
        await self._execute_once()

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._execute_once()
            except Exception as exc:  # noqa: BLE001
                self._logger.exception("Scheduled scrape failed", error=str(exc))
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._interval * 3600,
                )
            except asyncio.TimeoutError:
                continue

    async def _execute_once(self) -> None:
        started_at = datetime.utcnow()
        self._logger.info("Cron scrape started", started_at=started_at.isoformat())
        async with self._db_manager.session_scope() as session:
            repo = BusinessRepository(session)
            sites = await repo.get_active_sites()

        total_urls = len(sites)
        if total_urls == 0:
            finished = datetime.utcnow()
            summary = ScrapeRunSummary(
                started_at=started_at,
                finished_at=finished,
                duration_ms=int((finished - started_at).total_seconds() * 1000),
                total_urls=0,
                scraped_count=0,
                unique_count=0,
                persisted_count=0,
                duplicate_count=0,
                error_count=0,
                errors=[],
                notes="No active scraping sites",
            )
            async with self._db_manager.session_scope() as session:
                repo = BusinessRepository(session)
                await repo.record_scrape_detail(summary)
            self._logger.info("Cron scrape finished", summary="no-active-sites")
            return

        businesses: list[Business] = []
        errors: list[ScrapeError] = []
        attempted_site_ids: list[str] = []

        for site in sites:
            attempted_site_ids.append(site.id)
            try:
                site_businesses, site_errors, _meta = await self._coordinator.scrape([site.url])
                businesses.extend(site_businesses)
                errors.extend(site_errors)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    ScrapeError(
                        url=site.url,
                        message=str(exc),
                        stage="general",
                    )
                )
                self._logger.warning(
                    "Scrape failed for site",
                    site_id=site.id,
                    site_url=site.url,
                    error=str(exc),
                )

        unique_businesses, duplicates_in_run = self._deduplicate_businesses(businesses)
        persist_result = await self._persist(unique_businesses)

        finished_at = datetime.utcnow()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        summary = ScrapeRunSummary(
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            total_urls=total_urls,
            scraped_count=len(businesses),
            unique_count=len(unique_businesses),
            persisted_count=persist_result.persisted,
            duplicate_count=duplicates_in_run + persist_result.duplicates_in_db,
            error_count=len(errors),
            errors=errors,
        )

        async with self._db_manager.session_scope() as session:
            repo = BusinessRepository(session)
            await repo.record_scrape_detail(summary)
            await repo.update_sites_last_scraped(attempted_site_ids, finished_at)

        self._logger.info(
            "Cron scrape finished",
            total_urls=summary.total_urls,
            scraped=summary.scraped_count,
            unique=summary.unique_count,
            persisted=summary.persisted_count,
            duplicates=summary.duplicate_count,
            errors=summary.error_count,
        )

    def _deduplicate_businesses(self, businesses: Iterable[Business]) -> tuple[list[Business], int]:
        seen: dict[str, Business] = {}
        duplicates = 0
        for biz in businesses:
            key = self._business_key(biz)
            if key in seen:
                duplicates += 1
                continue
            seen[key] = biz
        return list(seen.values()), duplicates

    def _business_key(self, biz: Business) -> str:
        if biz.listingUrl:
            return biz.listingUrl.lower()
        composite = (biz.title or "").lower()
        if biz.location:
            composite += f"|{biz.location.lower()}"
        return composite or new_id()

    async def _persist(self, businesses: list[Business]) -> PersistResult:
        async with self._db_manager.session_scope() as session:
            repo = BusinessRepository(session)
            result = await repo.save_businesses(businesses)
        return result
