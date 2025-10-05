from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import ORJSONResponse

from app.core.config import Settings, get_settings
from app.core.logging_config import configure_logging, get_logger
from app.schemas import ScrapeRequest, ScrapeResponse
from app.scraper.coordinator import ScraperCoordinator
from app.db import create_session_factory, DatabaseManager
from app.services.scheduler import ScrapeScheduler

configure_logging()
logger = get_logger(component="FastAPI")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    coordinator = ScraperCoordinator(settings)
    app.state.coordinator = coordinator
    logger.info("Scraper coordinator initialised")
    db_manager: DatabaseManager | None = None
    scheduler: ScrapeScheduler | None = None
    if settings.database_url:
        try:
            db_manager = create_session_factory(settings)
            app.state.db_manager = db_manager
            logger.info("Database connection initialised")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to initialise database", error=str(exc))
            await coordinator.close()
            raise
        scheduler_enabled = settings.enable_scheduler and settings.environment != "test"
        if scheduler_enabled:
            scheduler = ScrapeScheduler(
                coordinator=coordinator,
                db_manager=db_manager,
                interval_hours=settings.cron_interval_hours,
                enabled=True,
            )
            await scheduler.start()
            app.state.scheduler = scheduler
        else:
            logger.info("Scheduler disabled by configuration", environment=settings.environment)
    else:
        logger.warning("Database URL not configured; persistence disabled")
    try:
        yield
    finally:
        if scheduler:
            await scheduler.stop()
        if db_manager:
            await db_manager.dispose()
        await coordinator.close()
        logger.info("Scraper coordinator shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Business Listing Scraper",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    @app.get("/health", response_model=dict[str, str])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/scrape", response_model=ScrapeResponse, response_model_exclude_none=True)
    async def scrape_listings(request: ScrapeRequest, settings: Settings = Depends(get_settings)) -> ScrapeResponse:
        if len(request.urls) > settings.request_max_urls:
            raise HTTPException(status_code=400, detail=f"Too many URLs; maximum is {settings.request_max_urls}")

        coordinator: ScraperCoordinator = app.state.coordinator
        businesses, errors, meta = await coordinator.scrape(request.urls, request.maxConcurrency)
        return ScrapeResponse(businesses=businesses, errors=errors, meta=meta)

    @app.post("/ingest", response_model=dict[str, str])
    async def trigger_ingest(settings: Settings = Depends(get_settings)) -> dict[str, str]:
        scheduler: ScrapeScheduler | None = getattr(app.state, "scheduler", None)
        if not settings.database_url:
            raise HTTPException(status_code=503, detail="Database not configured")
        if scheduler is None:
            raise HTTPException(status_code=503, detail="Scheduler is disabled")
        await scheduler.trigger_now()
        return {"status": "completed"}

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
