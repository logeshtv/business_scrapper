from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BusinessModel, ScraperDetailModel, ScrapingSiteModel
from app.schemas import Business, ScrapeError
from app.services.ids import new_id


@dataclass(slots=True)
class PersistResult:
    persisted: int
    duplicates_in_db: int


@dataclass(slots=True)
class ScrapeRunSummary:
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    total_urls: int
    scraped_count: int
    unique_count: int
    persisted_count: int
    duplicate_count: int
    error_count: int
    errors: list[ScrapeError]
    notes: str | None = None


class BusinessRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_active_sites(self) -> list[ScrapingSiteModel]:
        result = await self._session.execute(
            select(ScrapingSiteModel).where(ScrapingSiteModel.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def save_businesses(self, businesses: Sequence[Business]) -> PersistResult:
        if not businesses:
            return PersistResult(persisted=0, duplicates_in_db=0)

        urls = {biz.listingUrl for biz in businesses if biz.listingUrl}
        existing_urls = await self._existing_listing_urls(urls)
        persisted = 0
        duplicates = 0

        for biz in businesses:
            listing_url = biz.listingUrl
            if listing_url and listing_url in existing_urls:
                duplicates += 1
                continue

            record = BusinessModel(
                id=new_id(),
                title=biz.title,
                location=biz.location,
                price=biz.price,
                description=biz.description,
                business_type=biz.businessType,
                status=biz.status,
                listing_url=listing_url,
                images=biz.images or [],
                contact_info=biz.contactInfo,
                financial_info=biz.financialInfo,
                features=biz.features,
                additional_details=biz.additionalDetails,
                all_links=biz.allLinks or [],
                listing_index=biz.listingIndex,
                extraction_method=biz.extractionMethod,
                modified_at=biz.modifiedAt,
                modified_by=biz.modifiedBy,
            )
            self._session.add(record)
            persisted += 1
            if listing_url:
                existing_urls.add(listing_url)

        return PersistResult(persisted=persisted, duplicates_in_db=duplicates)

    async def _existing_listing_urls(self, urls: Iterable[str]) -> set[str]:
        url_set = {url for url in urls if url}
        if not url_set:
            return set()
        result = await self._session.execute(
            select(BusinessModel.listing_url).where(BusinessModel.listing_url.in_(url_set))
        )
        return {row[0] for row in result if row[0]}

    async def record_scrape_detail(self, summary: ScrapeRunSummary) -> None:
        detail = ScraperDetailModel(
            id=new_id(),
            started_at=summary.started_at,
            finished_at=summary.finished_at,
            duration_ms=summary.duration_ms,
            total_urls=summary.total_urls,
            scraped_count=summary.scraped_count,
            unique_count=summary.unique_count,
            persisted_count=summary.persisted_count,
            duplicate_count=summary.duplicate_count,
            error_count=summary.error_count,
            error_details=[error.model_dump(mode="json") for error in summary.errors] or None,
            notes=summary.notes,
        )
        self._session.add(detail)

    async def update_sites_last_scraped(self, site_ids: Iterable[str], timestamp: datetime) -> None:
        ids = list(site_ids)
        if not ids:
            return
        await self._session.execute(
            update(ScrapingSiteModel)
            .where(ScrapingSiteModel.id.in_(ids))
            .values(last_scraped=timestamp, updated_at=timestamp)
        )
