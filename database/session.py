"""
Ma'lumotlar bazasi sessiyalari va ulanish boshqaruvi
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from config import config
from database.models import Base

logger = logging.getLogger(__name__)

# Engine yaratish
engine = create_async_engine(
    config.db_url,
    echo=False,
    pool_pre_ping=True,
    # SQLite uchun connect_args
    connect_args={"check_same_thread": False} if "sqlite" in config.db_url else {}
)

# Async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Ma'lumotlar bazasi sessiyasini xavfsiz context manager orqali olish."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Barcha jadvallarni ma'lumotlar bazasida yaratish."""
    logger.info("Ma'lumotlar bazasi jadvallari tekshirilmoqda va yaratilmoqda...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Ma'lumotlar bazasi muvaffaqiyatli ishga tushirildi.")


async def close_db() -> None:
    """Ma'lumotlar bazasi ulanishlarini yopish."""
    logger.info("Ma'lumotlar bazasi ulanishlari yopilmoqda...")
    await engine.dispose()
