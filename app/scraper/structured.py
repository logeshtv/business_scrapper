from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Generator

import extruct
from w3lib.html import get_base_url

from app.scraper.utils import absolutize, guess_business_type, normalize_price, strip_text

BUSINESS_TYPES = {
    "LocalBusiness",
    "Business",
    "Product",
    "Offer",
    "Service",
    "Organization",
    "Corporation",
}


def extract_structured_businesses(html: str, page_url: str) -> list[dict[str, Any]]:
    base_url = get_base_url(html, page_url)
    try:
        data = extruct.extract(
            html,
            base_url=base_url,
            syntaxes=["json-ld", "microdata", "opengraph", "rdfa"],
            uniform=True,
        )
    except Exception:  # noqa: BLE001
        return []

    results: list[dict[str, Any]] = []
    for syntax in ("json-ld", "microdata", "rdfa"):
        for item in data.get(syntax, []) or []:
            for candidate in iter_business_candidates(item):
                record = normalise_candidate(candidate, base_url or page_url)
                if record:
                    results.append(record)
    # OpenGraph fallback
    results.extend(normalise_opengraph(data.get("opengraph", []), base_url or page_url))
    return results


def iter_business_candidates(node: Any) -> Generator[dict[str, Any], None, None]:
    if isinstance(node, list):
        for item in node:
            yield from iter_business_candidates(item)
    elif isinstance(node, dict):
        types = set()
        raw_type = node.get("@type")
        if isinstance(raw_type, list):
            types.update(raw_type)
        elif isinstance(raw_type, str):
            types.add(raw_type)
        if types & BUSINESS_TYPES:
            yield node
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                yield from iter_business_candidates(value)
    else:
        return


def normalise_candidate(item: dict[str, Any], base_url: str) -> dict[str, Any] | None:
    name = strip_text(
        item.get("name")
        or item.get("headline")
        or item.get("title")
        or item.get("legalName")
    )
    url = strip_text(item.get("url") or item.get("@id"))
    if not (name and url):
        return None

    price = None
    offers = item.get("offers")
    if isinstance(offers, dict):
        price = offers.get("price") or offers.get("priceCurrency")
    elif isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                price = offer.get("price") or offer.get("priceCurrency")
                if price:
                    break

    location = None
    loc = item.get("address") or item.get("areaServed")
    if isinstance(loc, dict):
        components = [
            loc.get("streetAddress"),
            loc.get("addressLocality"),
            loc.get("addressRegion"),
            loc.get("addressCountry"),
        ]
        location = strip_text(", ".join(filter(None, components)))

    description = strip_text(item.get("description"))
    business_type = guess_business_type(item.get("@type") if isinstance(item.get("@type"), str) else None)

    images: list[str] = []
    image = item.get("image")
    if isinstance(image, list):
        images = absolutize(image, base_url)
    elif isinstance(image, str):
        images = absolutize([image], base_url)

    links = [url]
    same_as = item.get("sameAs")
    if isinstance(same_as, list):
        links.extend(same_as)
    elif isinstance(same_as, str):
        links.append(same_as)

    return {
        "title": name,
        "listingUrl": absolutize([url], base_url)[0],
        "location": location,
    "price": normalize_price(price) or normalize_price(description),
        "description": description,
        "businessType": business_type,
        "status": None,
        "images": images,
        "contactInfo": None,
        "financialInfo": strip_text(item.get("founder") or item.get("foundingDate")),
        "features": None,
        "additionalDetails": strip_text(item.get("slogan")),
        "allLinks": absolutize(links, base_url),
        "rawText": None,
        "rawHtml": None,
        "listingIndex": None,
        "extractionMethod": 1,
        "modifiedAt": None,
        "modifiedBy": None,
    }


def normalise_opengraph(items: Iterable[dict[str, Any]], base_url: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for meta in items:
        if "og:title" not in meta or "og:url" not in meta:
            continue
        results.append(
            {
                "title": strip_text(meta.get("og:title")) or "",
                "listingUrl": absolutize([strip_text(meta.get("og:url")) or ""], base_url)[0],
                "location": None,
                "price": normalize_price(meta.get("og:price:amount")),
                "description": strip_text(meta.get("og:description")),
                "businessType": guess_business_type(meta.get("og:type")),
                "status": None,
                "images": absolutize([meta.get("og:image")] if meta.get("og:image") else [], base_url),
                "contactInfo": None,
                "financialInfo": None,
                "features": None,
                "additionalDetails": None,
                "allLinks": absolutize([meta.get("og:url")], base_url),
                "rawText": None,
                "rawHtml": None,
                "listingIndex": None,
                "extractionMethod": 1,
                "modifiedAt": None,
                "modifiedBy": None,
            }
        )
    return results
