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

from sqlalchemy.pool import NullPool

# Engine yaratish
engine = create_async_engine(
    config.db_url,
    echo=False,
    poolclass=NullPool if ("postgres" in config.db_url or "sqlite" in config.db_url) else None,
    connect_args=(
        {"check_same_thread": False, "timeout": 30} if "sqlite" in config.db_url
        else ({"ssl": "require"} if ("neon.tech" in config.db_url or "ssl" in config.db_url) else {})
    )
)

if "sqlite" in config.db_url:
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception:
            pass


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


def _run_sqlite_migrations(sync_conn) -> None:
    """SQLite uchun mavjud jadvallarga yangi ustunlarni qo'shish."""
    from sqlalchemy import inspect, text
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())

    if "users" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "referral_count" not in existing_cols:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0 NOT NULL"))
        if "referral_points" not in existing_cols:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN referral_points INTEGER DEFAULT 0 NOT NULL"))
        if "referred_by" not in existing_cols:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN referred_by BIGINT"))

    if "movies" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("movies")}
        if "genres" not in existing_cols:
            sync_conn.execute(text("ALTER TABLE movies ADD COLUMN genres VARCHAR(255) DEFAULT 'Barcha' NOT NULL"))
        if "year" not in existing_cols:
            sync_conn.execute(text("ALTER TABLE movies ADD COLUMN year INTEGER"))
        if "rating" not in existing_cols:
            sync_conn.execute(text("ALTER TABLE movies ADD COLUMN rating FLOAT"))
        if "poster_file_id" not in existing_cols:
            sync_conn.execute(text("ALTER TABLE movies ADD COLUMN poster_file_id VARCHAR(255)"))

    if "movie_files" not in existing_tables:
        sync_conn.execute(text("""
            CREATE TABLE IF NOT EXISTS movie_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_code VARCHAR(64) NOT NULL,
                part INTEGER DEFAULT 1 NOT NULL,
                file_id VARCHAR(255) NOT NULL,
                file_type VARCHAR(32) DEFAULT 'video' NOT NULL,
                file_size BIGINT,
                duration INTEGER,
                quality VARCHAR(32) DEFAULT '1080p',
                created_at DATETIME NOT NULL
            )
        """))
        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_movie_files_movie_code ON movie_files (movie_code)"))


async def init_db() -> None:
    """Barcha jadvallarni ma'lumotlar bazasida yaratish."""
    logger.info("Ma'lumotlar bazasi jadvallari tekshirilmoqda va yaratilmoqda...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in config.db_url:
            await conn.run_sync(_run_sqlite_migrations)
    logger.info("Ma'lumotlar bazasi muvaffaqiyatli ishga tushirildi.")
    # Boshlang'ich kinolar katalogini to'ldirish (185+ ta)
    try:
        from database.seed_data import seed_movies_if_empty
        async with get_session() as session:
            await seed_movies_if_empty(session)
    except Exception as e:
        logger.warning(f"Kinolar katalogini seed qilishda xatolik: {e}")


async def close_db() -> None:
    """Ma'lumotlar bazasi ulanishlarini yopish."""
    logger.info("Ma'lumotlar bazasi ulanishlari yopilmoqda...")
    await engine.dispose()
