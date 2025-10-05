from __future__ import annotations

import asyncio
import random
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from urllib.parse import urlparse, urlsplit

import httpx

from app.core.config import Settings
from app.core.logging_config import get_logger


class FetchResult(tuple[Any, ...]):
    __slots__ = ()

    def __new__(cls, url: str, final_url: str, status_code: int, text: str, headers: dict[str, str]):
        return super().__new__(cls, (url, final_url, status_code, text, headers))

    @property
    def url(self) -> str:  # type: ignore[override]
        return self[0]

    @property
    def final_url(self) -> str:
        return self[1]

    @property
    def status_code(self) -> int:
        return self[2]

    @property
    def text(self) -> str:
        return self[3]

    @property
    def headers(self) -> dict[str, str]:
        return self[4]


class AsyncFetcher:
    """HTTP client with concurrency control and retry support."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._logger = get_logger(component="AsyncFetcher")
        self._limits = httpx.Limits(
            max_connections=settings.http_max_concurrency * 2,
            max_keepalive_connections=settings.http_max_concurrency,
        )
        self._base_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        self._language_pool: tuple[str, ...] = (
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.8,fr;q=0.6",
        )
        http2_enabled = settings.http_enable_http2
        if http2_enabled:
            try:
                import h2  # noqa: F401
            except ImportError:
                self._logger.warning("h2 package missing; falling back to HTTP/1.1")
                http2_enabled = False
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.http_timeout_seconds,
            limits=self._limits,
            headers=self._base_headers,
            http2=http2_enabled,
        )
        self._semaphore = asyncio.Semaphore(settings.http_max_concurrency)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch(self, url: str) -> FetchResult:
        if not urlparse(url).scheme:
            raise ValueError(f"Invalid URL: {url}")
        backoff = self._settings.http_retry_backoff_seconds
        attempt = 0
        while True:
            try:
                headers = self._prepare_headers(url)
                async with self._semaphore:
                    response = await self._client.get(url, headers=headers)
                response.raise_for_status()
                block_reason = self._detect_antibot(response)
                if block_reason:
                    raise RuntimeError(f"{block_reason} [{url}]")
                return FetchResult(
                    url,
                    str(response.url),
                    response.status_code,
                    response.text,
                    dict(response.headers),
                )
            except httpx.HTTPError as exc:
                if attempt + 1 >= self._settings.http_retry_attempts:
                    self._logger.warning("HTTP request failed", url=url, attempt=attempt + 1, error=str(exc))
                    raise
                attempt += 1
                sleep_for = backoff * (self._settings.http_retry_backoff_factor ** (attempt - 1))
                self._logger.debug(
                    "Retrying HTTP request",
                    url=url,
                    attempt=attempt,
                    sleep=sleep_for,
                    error=str(exc),
                )
                await asyncio.sleep(sleep_for)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning("Unexpected error during fetch", url=url, error=str(exc))
                raise

    def _prepare_headers(self, url: str) -> dict[str, str]:
        headers = dict(self._base_headers)
        agent_pool = self._settings.user_agent_pool or (self._settings.user_agent,)
        user_agent = random.choice(agent_pool)
        headers["User-Agent"] = user_agent
        headers["Accept-Language"] = random.choice(self._language_pool)
        headers.update(self._sec_ch_hints(user_agent))
        parsed = urlsplit(url)
        if parsed.scheme and parsed.netloc:
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
            headers["Host"] = parsed.netloc
        return headers

    def _sec_ch_hints(self, user_agent: str) -> dict[str, str]:
        lowered = user_agent.lower()
        if "chrome" in lowered or "chromium" in lowered:
            platform = "\"Windows\"" if "windows" in lowered else "\"macOS\""
            major_version_match = re.search(r"chrome/(\d+)", lowered)
            major = major_version_match.group(1) if major_version_match else "124"
            return {
                "Sec-CH-UA": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not.A/Brand";v="99"',
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": platform,
            }
        if "safari" in lowered and "chrome" not in lowered:
            return {
                "Sec-CH-UA": '"Not A Brand";v="99", "Safari";v="17"',
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": "\"macOS\"",
            }
        return {}

    def _detect_antibot(self, response: httpx.Response) -> str | None:
        if response.status_code in {401, 403, 409, 429, 503}:
            return f"Request blocked by target site (HTTP {response.status_code})"
        sample = response.text[:1500].lower()
        block_markers = (
            "just a moment",
            "enable javascript to continue",
            "attention required",
            "cloudflare",
            "are you a human",
            "access denied",
            "bot detection",
        )
        if any(marker in sample for marker in block_markers):
            return "Request blocked by target site (anti-bot page detected)"
        return None

    async def fetch_many(self, urls: list[str], concurrency_override: int | None = None) -> AsyncIterator[tuple[str, FetchResult | Exception]]:
        semaphore = (
            asyncio.Semaphore(min(concurrency_override, self._settings.http_max_concurrency))
            if concurrency_override and concurrency_override > 0
            else self._semaphore
        )

        async def runner(target_url: str) -> tuple[str, FetchResult | Exception]:
            try:
                async with semaphore:
                    return target_url, await self.fetch(target_url)
            except Exception as exc:  # noqa: BLE001
                return target_url, exc

        tasks = [asyncio.create_task(runner(url)) for url in urls]
        for task in asyncio.as_completed(tasks):
            yield await task

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator["AsyncFetcher", None]:
        try:
            yield self
        finally:
            await self.aclose()
