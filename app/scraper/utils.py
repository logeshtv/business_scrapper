from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import urljoin

WHITESPACE_RE = re.compile(r"\s+")
PRICE_RE = re.compile(r"([£$€]|AUD|CAD|USD|EUR|GBP|SGD|AED)\s?\d[\d,. ]*")
LOCATION_HINT_RE = re.compile(r"\b(city|town|region|state|country|county|province|location)\b", re.I)
STATUS_HINT_RE = re.compile(r"\b(sold|available|under offer|completed)\b", re.I)
BUSINESS_TYPE_HINT_RE = re.compile(r"\b(franchise|restaurant|cafe|retail|service|manufacturing|property|real estate|technology)\b", re.I)


def strip_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = WHITESPACE_RE.sub(" ", value).strip()
    return cleaned or None


def normalize_price(value: Any) -> str | None:
    text = strip_text(value)
    if not text:
        return None
    match = PRICE_RE.search(text)
    if not match:
        return text
    return strip_text(match.group(0))


def guess_location_from_text(value: Any) -> str | None:
    text = strip_text(value)
    if not text:
        return None
    if LOCATION_HINT_RE.search(text):
        return text
    return None


def guess_status(value: Any) -> str | None:
    text = strip_text(value)
    if not text:
        return None
    if STATUS_HINT_RE.search(text):
        return text
    return None


def guess_business_type(value: Any) -> str | None:
    text = strip_text(value)
    if not text:
        return None
    if BUSINESS_TYPE_HINT_RE.search(text):
        return text
    return None


def absolutize(urls: Iterable[Any], base_url: str) -> list[str]:
    resolved: list[str] = []
    for url in urls:
        cleaned = strip_text(url)
        if not cleaned:
            continue
        resolved.append(urljoin(base_url, cleaned))
    return list(dict.fromkeys(resolved))


def now_iso() -> datetime:
    return datetime.utcnow()
