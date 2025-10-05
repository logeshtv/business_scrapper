from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from loguru import logger

from app.core.config import Settings, get_settings
from app.scraper.heuristics import extract_businesses_with_heuristics
from app.scraper.structured import extract_structured_businesses
from app.scraper.utils import strip_text


class ListingExtractor:
    """Combine multiple extraction signals into consolidated business records."""

    def __init__(self, html: str, page_url: str, settings: Settings | None = None):
        self.html = html
        self.page_url = page_url
        self._logger = logger.bind(component="ListingExtractor", url=page_url)
        self._settings = settings or get_settings()
        self._title_blocklist = tuple(kw.lower() for kw in self._settings.junk_title_keywords)
        self._url_blocklist = tuple(kw.lower() for kw in self._settings.junk_url_keywords)

    def extract(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        structured = extract_structured_businesses(self.html, self.page_url)
        if structured:
            self._logger.debug("Structured data extractor produced {} candidates", len(structured))
            candidates.extend(structured)

        heuristic = extract_businesses_with_heuristics(self.html, self.page_url)
        if heuristic:
            self._logger.debug("Heuristic extractor produced {} candidates", len(heuristic))
            candidates.extend(heuristic)

        merged = self._deduplicate(candidates)
        self._logger.debug("Extractor produced {} merged candidates", len(merged))
        return merged

    def _deduplicate(self, items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_keys: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in items:
            normalised = self._normalise_item(item)
            if not self._is_valid_candidate(normalised):
                continue
            key = normalised["listingUrl"].lower()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(normalised)
        return deduped

    def _normalise_item(self, item: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = dict(item)
        cleaned["title"] = strip_text(item.get("title"))
        cleaned["listingUrl"] = strip_text(item.get("listingUrl"))
        cleaned["description"] = strip_text(item.get("description"))
        cleaned["price"] = strip_text(item.get("price"))
        cleaned["location"] = strip_text(item.get("location"))
        cleaned["status"] = strip_text(item.get("status"))
        cleaned["businessType"] = strip_text(item.get("businessType"))
        cleaned["contactInfo"] = strip_text(item.get("contactInfo"))
        cleaned["financialInfo"] = strip_text(item.get("financialInfo"))
        cleaned["features"] = strip_text(item.get("features"))
        cleaned["additionalDetails"] = strip_text(item.get("additionalDetails"))
        cleaned["rawText"] = strip_text(item.get("rawText"))
        cleaned["rawHtml"] = item.get("rawHtml")
        all_links = item.get("allLinks") or []
        if isinstance(all_links, list):
            cleaned["allLinks"] = list(dict.fromkeys(link for link in (strip_text(link) for link in all_links) if link))
        else:
            cleaned["allLinks"] = []
        images = item.get("images") or []
        if isinstance(images, list):
            cleaned["images"] = list(dict.fromkeys(img for img in (strip_text(img) for img in images) if img))
        else:
            cleaned["images"] = []
        return cleaned

    def _is_valid_candidate(self, item: dict[str, Any]) -> bool:
        title = item.get("title")
        if not title or len(title.split()) < self._settings.min_listing_title_words:
            return False
        lowered_title = title.lower()
        if any(keyword in lowered_title for keyword in self._title_blocklist):
            return False

        url = item.get("listingUrl")
        if not url:
            return False
        lowered_url = url.lower()
        if any(keyword in lowered_url for keyword in self._url_blocklist):
            return False
        if lowered_url.rstrip("/") == self.page_url.rstrip("/"):
            return False

        description = item.get("description")
        price = item.get("price")
        features = item.get("features")
        financial = item.get("financialInfo")
        raw_text = item.get("rawText")
        has_rich_content = False
        if description and len(description) >= self._settings.min_listing_text_length:
            has_rich_content = True
        if price:
            has_rich_content = True
        if financial:
            has_rich_content = True
        if features and len(features) >= self._settings.min_listing_feature_length:
            has_rich_content = True
        if raw_text and len(raw_text) >= self._settings.min_listing_text_length:
            has_rich_content = True
        if item.get("images"):
            has_rich_content = True
        return has_rich_content
