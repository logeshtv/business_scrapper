from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings

SessionFactory = async_sessionmaker[AsyncSession]


class DatabaseManager:
    def __init__(self, settings: Settings):
        if not settings.database_url:
            raise ValueError("Database URL is required to initialise DatabaseManager")
        self._settings = settings
        self._engine: AsyncEngine = create_async_engine(
            self._prepare_async_url(settings.database_url),
            echo=settings.sqlalchemy_echo,
            pool_pre_ping=True,
        )
        self._session_factory: SessionFactory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
        )

    def _prepare_async_url(self, value: str) -> str:
        url: URL = make_url(value)
        driver = (url.drivername or "").lower()
        if driver.startswith("postgres"):
            url = url.set(drivername="postgresql+asyncpg")
        elif driver.startswith("mysql") or driver.startswith("mariadb"):
            url = url.set(drivername="mysql+aiomysql")
        return url.render_as_string(hide_password=False)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> SessionFactory:
        return self._session_factory

    async def dispose(self) -> None:
        await self._engine.dispose()

    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:  # noqa: BLE001
            await session.rollback()
            raise
        finally:
            await session.close()


def create_session_factory(settings: Settings) -> DatabaseManager:
    return DatabaseManager(settings)
