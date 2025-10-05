from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from app.core.config import Settings
from app.scraper.coordinator import ScraperCoordinator

FIXTURE_DIR = Path(__file__).parent / "fixtures"
MOCK_URLS = {
    "https://example.com/page-a": "sample_structured.html",
    "https://example.com/page-b": "sample_heuristic.html",
    "https://example.com/page-c": "sample_nav.html",
}


@pytest.mark.anyio
async def test_coordinator_scrapes_multiple_urls() -> None:
    settings = Settings(environment="test")
    coordinator = ScraperCoordinator(settings)
    try:
        with respx.mock(assert_all_called=True) as mock:
            for url, fixture in MOCK_URLS.items():
                html = (FIXTURE_DIR / fixture).read_text(encoding="utf-8")
                mock.get(url).mock(
                    return_value=httpx.Response(
                        200,
                        text=html,
                        headers={"Content-Type": "text/html"},
                    )
                )

            businesses, errors, meta = await coordinator.scrape(list(MOCK_URLS))

        assert errors == []
        assert meta.totalRequested == len(MOCK_URLS)
        assert len(businesses) >= len(MOCK_URLS)
        listing_urls = [biz.listingUrl for biz in businesses]
        assert len(listing_urls) == len(set(listing_urls))
        titles = {biz.title for biz in businesses}
        assert "Contact Us" not in titles
    finally:
        await coordinator.close()


@pytest.mark.anyio
async def test_coordinator_flags_block_page_as_error() -> None:
    settings = Settings(environment="test")
    coordinator = ScraperCoordinator(settings)
    try:
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://example.com/blocked").mock(
                return_value=httpx.Response(
                    200,
                    text="<html><title>Just a moment...</title><body>Attention required</body></html>",
                    headers={"Content-Type": "text/html"},
                )
            )

            businesses, errors, meta = await coordinator.scrape(["https://example.com/blocked"])

        assert businesses == []
        assert len(errors) == 1
        assert "blocked" in errors[0].message.lower()
        assert meta.totalRequested == 1
        assert meta.totalSucceeded == 0
        assert meta.totalBusinesses == 0
    finally:
        await coordinator.close()
