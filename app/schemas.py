from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ScrapeRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, description="Listing page URLs to scrape")
    maxConcurrency: Optional[int] = Field(
        default=None,
        ge=1,
        le=32,
        description="Override global concurrency limit for this request",
    )

    @model_validator(mode="after")
    def normalise_urls(self) -> "ScrapeRequest":
        unique: list[str] = []
        seen: set[str] = set()
        for raw in self.urls:
            value = raw.strip()
            if not value:
                continue
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Each URL must include a scheme and host: {value}")
            lowered = value.lower()
            if lowered not in seen:
                seen.add(lowered)
                unique.append(value)
        if not unique:
            raise ValueError("At least one valid URL is required")
        self.urls = unique
        return self


class Business(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="ignore")

    title: str
    listingUrl: str = Field(serialization_alias="listingUrl")
    location: Optional[str] = None
    price: Optional[str] = None
    description: Optional[str] = None
    businessType: Optional[str] = None
    status: Optional[str] = None
    images: list[str] = Field(default_factory=list)
    contactInfo: Optional[str] = None
    financialInfo: Optional[str] = None
    features: Optional[str] = None
    additionalDetails: Optional[str] = None
    allLinks: list[str] = Field(default_factory=list)
    rawText: Optional[str] = None
    rawHtml: Optional[str] = None
    listingIndex: Optional[int] = None
    extractionMethod: Optional[int] = None
    modifiedAt: Optional[datetime] = None
    modifiedBy: Optional[str] = None


class ScrapeError(BaseModel):
    url: HttpUrl
    message: str
    stage: Literal["fetch", "parse", "general"]


class ScrapeMeta(BaseModel):
    totalRequested: int
    totalSucceeded: int
    totalBusinesses: int
    durationMs: int


class ScrapeResponse(BaseModel):
    businesses: list[Business]
    errors: list[ScrapeError]
    meta: ScrapeMeta
