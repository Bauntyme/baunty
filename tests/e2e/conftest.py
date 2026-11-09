"""
BauntyCinemBot E2E Test Suite Fixtures & Configuration.
Provides ephemeral SQLite in-memory database, clean security state, and WebApp test client.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from aiohttp.test_utils import TestServer, TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
from services.security_service import security_service
from services.web_server import create_web_app


@pytest.fixture(autouse=True)
def clean_security_state():
    """Reset security service sliding window and auto-ban jail before and after each test."""
    security_service.reset()
    yield
    security_service.reset()


@pytest_asyncio.fixture
async def e2e_db_session():
    """Provide an isolated, ephemeral in-memory SQLite database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def e2e_web_client():
    """Provide an ephemeral aiohttp TestClient for WebApp and REST endpoints."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def mock_bot():
    """Mock aiogram Bot instance for testing handlers and delivery workflows."""
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))
    bot.send_document = AsyncMock(return_value=MagicMock(message_id=124))
    bot.send_audio = AsyncMock(return_value=MagicMock(message_id=125))
    bot.send_video = AsyncMock(return_value=MagicMock(message_id=126))
    bot.answer_callback_query = AsyncMock(return_value=True)
    return bot
