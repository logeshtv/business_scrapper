from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.scraper.extractor import ListingExtractor

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "fixture_name",
    ["sample_structured.html", "sample_heuristic.html"],
)
def test_listing_extractor_produces_results(fixture_name: str) -> None:
    html = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    settings = Settings(environment="test")
    extractor = ListingExtractor(html, "https://example.com", settings=settings)
    records = extractor.extract()
    assert records, "Extractor should find at least one listing"
    for record in records:
        assert record["title"]
        assert record["listingUrl"].startswith("http")


def test_extractor_deduplicates_by_listing_url() -> None:
    html = (FIXTURES / "sample_structured.html").read_text(encoding="utf-8")
    settings = Settings(environment="test")
    extractor = ListingExtractor(html, "https://example.com", settings=settings)
    records = extractor.extract()
    # duplicate entries with same URL should not appear twice
    urls = [record["listingUrl"] for record in records]
    assert len(urls) == len(set(urls))


def test_extractor_filters_navigation_entries() -> None:
    html = (FIXTURES / "sample_nav.html").read_text(encoding="utf-8")
    settings = Settings(environment="test")
    extractor = ListingExtractor(html, "https://example.com/listings", settings=settings)
    records = extractor.extract()
    assert records, "Expected valid listings"
    titles = {record["title"] for record in records}
    for unwanted in ("Contact Us", "Privacy Policy"):
        assert unwanted not in titles
    for record in records:
        assert "/contact" not in record["listingUrl"].lower()
