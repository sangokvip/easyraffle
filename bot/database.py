from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


def _build_engine() -> AsyncEngine:
    return create_async_engine(settings.database_url, pool_pre_ping=True, pool_recycle=3600)


engine: AsyncEngine = _build_engine()
SessionMaker = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


@asynccontextmanager
async def get_session():
    session = SessionMaker()
    try:
        yield session
    finally:
        await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
