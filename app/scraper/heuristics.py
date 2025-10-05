from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from selectolax.lexbor import LexborHTMLParser, LexborNode

from app.scraper.utils import (
    absolutize,
    guess_business_type,
    guess_location_from_text,
    guess_status,
    normalize_price,
    strip_text,
)

LISTING_CLASS_HINTS = (
    "listing",
    "result",
    "card",
    "item",
    "search-result",
    "business",
    "opportunity",
    "teaser",
    "entry",
    "record",
)
TITLE_SELECTORS = (
    "h1",
    "h2",
    "h3",
    "h4",
    "a",
)


def extract_businesses_with_heuristics(html: str, page_url: str) -> list[dict[str, Any]]:
    parser = LexborHTMLParser(html)
    if not parser.body:
        return []

    listing_nodes = identify_listing_nodes(parser.body)
    if not listing_nodes:
        listing_nodes = parser.css("article, div[class], li[class]")

    records: list[dict[str, Any]] = []
    for idx, listing_node in enumerate(listing_nodes):
        record = extract_from_node(listing_node, page_url, idx)
        if record:
            records.append(record)

    if not records:
        # as a last resort, treat entire container as single listing
        record = extract_from_node(parser.body, page_url, 0)
        return [record] if record else []

    return records


def identify_listing_nodes(root: LexborNode) -> list[LexborNode]:
    by_class: defaultdict[str, list[Node]] = defaultdict(list)
    for node in root.css("div, section, article, li"):
        cls = node.attributes.get("class", "").strip()
        if not cls:
            continue
        signature = " ".join(sorted(set(cls.split())))
        if not signature:
            continue
        if not node.css_first("a[href]"):
            continue
        by_class[signature].append(node)

    if not by_class:
        return []

    ranked = sorted(
        by_class.items(),
        key=lambda item: (
            -(1 if any(hint in item[0].lower() for hint in LISTING_CLASS_HINTS) else 0),
            -len(item[1]),
        ),
    )

    for _signature, nodes in ranked:
        if len(nodes) >= 3:
            return nodes

    return []


def extract_from_node(node: LexborNode, page_url: str, index: int) -> dict[str, Any] | None:
    title_node = first_not_none(
        *(node.css_first(selector) for selector in TITLE_SELECTORS)
    )
    if not title_node:
        return None
    title = strip_text(title_node.text())
    if not title or len(title.split()) < 2:
        return None

    link_node = title_node if title_node.tag == "a" and title_node.attributes.get("href") else node.css_first("a[href]")
    listing_url = strip_text(link_node.attributes.get("href")) if link_node else None
    if listing_url:
        listing_url = absolutize([listing_url], page_url)[0]

    description = extract_longest_text(node)
    price = normalize_price(description) or normalize_price(extract_price_hint(node))
    location_text = extract_by_class_keyword(node, ("location", "city", "county", "region"))
    location = guess_location_from_text(location_text) or location_text
    status = guess_status(extract_by_class_keyword(node, ("status", "state", "deal")))
    business_type = guess_business_type(
        extract_by_class_keyword(node, ("type", "category", "sector"))
    )

    images = absolutize((img.attributes.get("src") for img in node.css("img[src]")), page_url)

    list_text = " | ".join(li.text(separator=" ", strip=True) for li in node.css("li")) or None

    if not listing_url:
        # fallback to page URL plus anchor hash to avoid duplicates
        listing_url = f"{page_url}#listing-{index}"

    all_links = absolutize((a.attributes.get("href") for a in node.css("a[href]")), page_url)

    return {
        "title": title,
        "listingUrl": listing_url,
        "location": strip_text(location),
        "price": price,
        "description": strip_text(description),
        "businessType": business_type,
        "status": status,
        "images": images,
        "contactInfo": None,
        "financialInfo": strip_text(extract_by_class_keyword(node, ("turnover", "revenue", "profit"))),
        "features": strip_text(list_text),
        "additionalDetails": strip_text(extract_by_class_keyword(node, ("detail", "summary", "highlight"))),
        "allLinks": all_links,
        "rawText": strip_text(node.text(separator=" ", strip=True)),
        "rawHtml": node.html,
        "listingIndex": index,
        "extractionMethod": 2,
        "modifiedAt": None,
        "modifiedBy": None,
    }


def extract_longest_text(node: LexborNode) -> str | None:
    longest = ""
    for desc in node.css("p, div, span"):
        text = strip_text(desc.text())
        if text and len(text) > len(longest):
            longest = text
    return longest or None


def extract_price_hint(node: LexborNode) -> str | None:
    texts = [strip_text(desc.text()) for desc in node.css("span, div, p")]  # type: ignore[list-item]
    for text in texts:
        if text and any(sym in text for sym in ("£", "€", "$")):
            return text
    return None


def extract_by_class_keyword(node: LexborNode, keywords: Iterable[str]) -> str | None:
    lowered = [kw.lower() for kw in keywords]
    for desc in node.css("*"):
        cls = desc.attributes.get("class", "").lower()
        if cls and any(kw in cls for kw in lowered):
            return strip_text(desc.text())
    return None


def first_not_none(*nodes: LexborNode | None) -> LexborNode | None:
    for node in nodes:
        if node is not None:
            return node
    return None
