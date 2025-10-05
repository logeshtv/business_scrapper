from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    environment: Literal["development", "production", "test"] = "development"
    http_timeout_seconds: float = 20.0
    http_max_redirects: int = 5
    http_max_concurrency: int = 8
    http_retry_attempts: int = 3
    http_retry_backoff_seconds: float = 0.75
    http_retry_backoff_factor: float = 2.0
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36"
    )
    user_agent_pool: tuple[str, ...] = (
        user_agent,
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    )
    http_enable_http2: bool = True
    request_max_urls: int = 50
    allow_parallelism: bool = True
    database_url: Optional[str] = None
    sqlalchemy_echo: bool = False
    enable_scheduler: bool = True
    cron_interval_hours: float = 6.0
    min_listing_title_words: int = 2
    min_listing_text_length: int = 40
    min_listing_feature_length: int = 16
    structured_data_weight: float = 0.6
    heuristics_weight: float = 0.4
    junk_title_keywords: tuple[str, ...] = (
        "contact",
        "privacy",
        "terms",
        "login",
        "register",
        "sitemap",
        "cookie",
        "about",
        "support",
        "export",
        "news",
    )
    junk_url_keywords: tuple[str, ...] = (
        "contact",
        "privacy",
        "terms",
        "login",
        "register",
        "sitemap",
        "cookie",
        "about",
        "support",
        "export",
        "newsletter",
        "blog",
    )

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SCRAPER_", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
