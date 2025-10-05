from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BusinessModel(Base):
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_type: Mapped[Optional[str]] = mapped_column("business_type", String, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    listing_url: Mapped[Optional[str]] = mapped_column("listing_url", String, nullable=True)
    images: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    contact_info: Mapped[Optional[str]] = mapped_column("contact_info", Text, nullable=True)
    financial_info: Mapped[Optional[str]] = mapped_column("financial_info", Text, nullable=True)
    features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    additional_details: Mapped[Optional[str]] = mapped_column("additional_details", Text, nullable=True)
    all_links: Mapped[List[str]] = mapped_column("all_links", ARRAY(String), nullable=False, default=list)
    raw_text: Mapped[Optional[str]] = mapped_column("raw_text", Text, nullable=True)
    raw_html: Mapped[Optional[str]] = mapped_column("raw_html", Text, nullable=True)
    listing_index: Mapped[Optional[int]] = mapped_column("listing_index", Integer, nullable=True)
    extraction_method: Mapped[Optional[int]] = mapped_column("extraction_method", Integer, nullable=True)
    is_approved: Mapped[bool] = mapped_column("is_approved", Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_rejected: Mapped[bool] = mapped_column("is_rejected", Boolean, default=False, nullable=False)
    modified_at: Mapped[Optional[datetime]] = mapped_column("modified_at", DateTime, nullable=True)
    modified_by: Mapped[Optional[str]] = mapped_column("modified_by", String, nullable=True)
    is_junk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ScrapingSiteModel(Base):
    __tablename__ = "scraping_sites"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column("isActive", Boolean, default=True, nullable=False)
    last_scraped: Mapped[Optional[datetime]] = mapped_column("last_scraped", DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ScraperDetailModel(Base):
    __tablename__ = "scraper_details"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    started_at: Mapped[datetime] = mapped_column("started_at", DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column("finished_at", DateTime, nullable=False)
    duration_ms: Mapped[int] = mapped_column("duration_ms", Integer, nullable=False)
    total_urls: Mapped[int] = mapped_column("total_urls", Integer, nullable=False)
    scraped_count: Mapped[int] = mapped_column("scraped_count", Integer, nullable=False)
    unique_count: Mapped[int] = mapped_column("unique_count", Integer, nullable=False)
    persisted_count: Mapped[int] = mapped_column("persisted_count", Integer, nullable=False)
    duplicate_count: Mapped[int] = mapped_column("duplicate_count", Integer, nullable=False)
    error_count: Mapped[int] = mapped_column("error_count", Integer, nullable=False)
    error_details: Mapped[Optional[dict[str, object]]] = mapped_column("error_details", JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow, nullable=False)
