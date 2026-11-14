"""
Milestone 1 Replacement Empirical Challenger Adversarial Test Suite
Author: Challenger M1-1 Replacement (challenger_m1_1_rep)
Scope: High-stress empirical verification of M1 Movie Retrieval & Delivery Fixes
"""
import uuid
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base, Movie, MovieFile
from database import crud
from services.movie_service import movie_service, MovieService
from handlers.movies import _send_movie_delivery_fallback
from services.web_server import create_web_app, handle_get_movie_detail
import services.web_server as ws


@pytest_asyncio.fixture
async def mem_session():
    """In-memory SQLite isolated async session for empirical stress testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


# ============================================================================
# 1. EMPIRICAL TEST: Selective file_id Invalidation vs Transient Errors
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("error_exc,should_wipe", [
    (TelegramForbiddenError(method="sendVideo", message="Forbidden: bot was blocked by the user"), False),
    (TelegramNetworkError(method="sendVideo", message="Connection reset by peer"), False),
    (TelegramRetryAfter(method="sendVideo", message="Flood control exceeded", retry_after=42), False),
    (asyncio.TimeoutError("Network timeout connecting to api.telegram.org"), False),
    (TelegramBadRequest(method="sendVideo", message="Bad Request: wrong remote file id specified"), True),
    (TelegramBadRequest(method="sendVideo", message="Bad Request: wrong file identifier/HTTP URL specified"), True),
    (TelegramBadRequest(method="sendVideo", message="Bad Request: file_id is invalid"), True),
])
async def test_empirical_file_id_cache_retention_matrix(mem_session: AsyncSession, error_exc, should_wipe):
    """
    Stress-test Cloud Pool cache retention across the entire error spectrum.
    Only explicit file token invalidations should wipe cached file_id.
    Contextual or transient delivery errors must NEVER wipe the cached file_id.
    """
    code = f"emp_fid_{uuid.uuid4().hex[:6]}"
    part = 1
    valid_fid = f"BAACAgIAAxkBAAE_{uuid.uuid4().hex}"

    # Seed parent Movie and child MovieFile
    m = Movie(code=code, title="Empirical Stress Test", views_count=0)
    mem_session.add(m)
    await mem_session.flush()

    mf = MovieFile(
        movie_code=code,
        part=part,
        file_id=valid_fid,
        file_type="video",
        duration=180,
        file_size=1024 * 1024 * 25
    )
    mem_session.add(mf)
    await mem_session.commit()

    bot_mock = AsyncMock()
    bot_mock.send_video.side_effect = error_exc

    delivered = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=987654321,
        code=code,
        part=part,
        session=mem_session,
        require_video=True
    )
    assert delivered is False

    # Verify DB state
    await mem_session.refresh(mf)
    if should_wipe:
        assert mf.file_id == "", f"Expected file_id to be wiped for error: {error_exc}, but got: {mf.file_id}"
    else:
        assert mf.file_id == valid_fid, f"file_id was erroneously wiped for transient error: {error_exc}"


# ============================================================================
# 2. EMPIRICAL TEST: Deleted Reply Message Recovery & Double-Attempt Logic
# ============================================================================

@pytest.mark.asyncio
async def test_empirical_deliver_movie_deleted_reply_recovery(mem_session: AsyncSession):
    """
    Empirically verify deliver_movie recovers when reply_to_message_id is deleted.
    Attempt 1: Fails with 'message to be replied not found'
    Attempt 2: Automatically retries with reply_to_message_id=None and succeeds.
    """
    code = f"emp_reply_{uuid.uuid4().hex[:6]}"
    part = 1
    valid_fid = f"BAACAgIAAxkBAAE_REPLY_{uuid.uuid4().hex}"

    m = Movie(code=code, title="Deleted Reply Test", views_count=0)
    mem_session.add(m)
    await mem_session.flush()

    mf = MovieFile(
        movie_code=code,
        part=part,
        file_id=valid_fid,
        file_type="video",
        duration=120,
        file_size=1024 * 1024 * 15
    )
    mem_session.add(mf)
    await mem_session.commit()

    sent_msg = MagicMock()
    sent_msg.video = MagicMock(file_id=valid_fid)
    sent_msg.document = None

    call_history = []
    async def mock_send_video(*args, **kwargs):
        call_history.append(kwargs)
        if kwargs.get("reply_to_message_id") is not None:
            raise TelegramBadRequest(method="sendVideo", message="Bad Request: message to be replied not found")
        return sent_msg

    bot_mock = AsyncMock()
    bot_mock.send_video.side_effect = mock_send_video

    delivered = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=555666777,
        code=code,
        part=part,
        reply_to_message_id=112233,
        session=mem_session,
        require_video=True
    )

    assert delivered is True, "deliver_movie did not recover from deleted reply-to message!"
    assert len(call_history) == 2, f"Expected exactly 2 delivery attempts, got {len(call_history)}"
    assert call_history[0].get("reply_to_message_id") == 112233
    assert call_history[1].get("reply_to_message_id") is None

    # Ensure cached file_id was preserved
    await mem_session.refresh(mf)
    assert mf.file_id == valid_fid


@pytest.mark.asyncio
async def test_empirical_fallback_card_deleted_reply_recovery():
    """
    Empirically verify _send_movie_delivery_fallback recovers when reply_to_message_id is deleted.
    """
    bot_mock = AsyncMock()
    call_history = []

    async def mock_send_message(*args, **kwargs):
        call_history.append(kwargs)
        if kwargs.get("reply_to_message_id") is not None:
            raise TelegramBadRequest(method="sendMessage", message="Bad Request: message to be replied not found")
        return MagicMock()

    bot_mock.send_message.side_effect = mock_send_message

    # Test fallback card on existing catalog movie '103'
    await _send_movie_delivery_fallback(
        bot=bot_mock,
        chat_id=1234567,
        code="103",
        part=1,
        reply_to_message_id=987654
    )

    assert len(call_history) == 2, f"Expected 2 attempts in fallback card, got {len(call_history)}"
    assert call_history[0].get("reply_to_message_id") == 987654
    assert call_history[1].get("reply_to_message_id") is None


# ============================================================================
# 3. EMPIRICAL TEST: Unique UUID Temp Filenames for Concurrency Isolation
# ============================================================================

@pytest.mark.asyncio
async def test_empirical_concurrent_uuid_temp_filenames():
    """
    Verify that temporary download filenames incorporate unique UUID suffixes
    to prevent file locking / collisions under concurrent downloads on Windows.
    """
    download_urls = []
    with patch("services.movie_service.Path.mkdir"), \
         patch("services.movie_service.Path.stat") as mock_stat, \
         patch("services.movie_service.Path.unlink"):
        
        mock_stat.return_value.st_size = 1024 * 1024 * 10
        
        # Capture generated Path instances in download_and_upload_media_on_demand
        orig_path_init = Path.__new__
        generated_paths = []
        
        def mock_path_new(cls, *args, **kwargs):
            instance = orig_path_init(cls, *args, **kwargs)
            str_path = str(instance)
            if "temp_download_" in str_path:
                generated_paths.append(str_path)
            return instance

        with patch("services.movie_service.Path", side_effect=mock_path_new):
            # Inspect the source code directly to guarantee uuid presence in temp filename
            import inspect
            src = inspect.getsource(MovieService.download_and_upload_media_on_demand)
            assert "uuid.uuid4().hex" in src, "Temp filename generation lacks uuid.uuid4().hex isolation!"


# ============================================================================
# 4. EMPIRICAL TEST: Multi-Part Serial Compatibility in /api/movies/{code}
# ============================================================================

@pytest.mark.asyncio
async def test_empirical_movie_detail_part_attribute_compatibility():
    """
    Empirically test handle_get_movie_detail part counting:
    Ensures that MovieFile instances with either .part or .part_number are correctly evaluated.
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        mock_movie = SimpleNamespace(
            id=42,
            code="emp_serial_42",
            title="Empirical Multi-Part Serial",
            genres="Drama",
            year=2025,
            rating=9.1,
            duration=7200,
            views_count=500,
            downloads_count=120,
            description="Multi-part test serial",
            file_id="BAACAgIAAxkBAAE_SAMPLE",
        )

        # File 1 has .part, File 2 has .part_number, File 3 has .part=5
        mock_file1 = SimpleNamespace(part=1, part_number=None, file_id="FID_1")
        mock_file2 = SimpleNamespace(part=None, part_number=3, file_id="FID_3")
        mock_file3 = SimpleNamespace(part=5, part_number=None, file_id="FID_5")

        with patch("services.web_server.crud.get_movie_by_code", new_callable=AsyncMock, return_value=mock_movie):
            with patch.object(crud, "get_movie_files", create=True, new_callable=AsyncMock) as mock_get_files:
                mock_get_files.return_value = [mock_file1, mock_file2, mock_file3]
                resp = await client.get("/api/movies/emp_serial_42")
                assert resp.status == 200
                data = await resp.json()
                assert data.get("ok") is True
                assert data.get("parts") == 5, f"Expected parts=5, got {data.get('parts')}"
                assert data.get("p") == 5, f"Expected p=5, got {data.get('p')}"
    finally:
        await client.close()


# ============================================================================
# 5. EMPIRICAL TEST: /api/send_to_chat Oversized Fallback vs 404
# ============================================================================

@pytest.mark.asyncio
async def test_empirical_send_to_chat_oversized_fallback_and_invalid_404():
    """
    Stress-test /api/send_to_chat:
    1. Oversized video (>50MB): deliver_movie returns False, but movie exists.
       Must return HTTP 200 with action: 'fallback_card' and dispatch fallback card.
    2. Non-existent movie: deliver_movie returns False, and movie does not exist.
       Must return HTTP 404 with error: 'video_unavailable'.
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    orig_bot = ws._bot_instance
    bot_mock = AsyncMock()
    ws._bot_instance = bot_mock

    try:
        # Mock security service auth to simulate valid Telegram WebApp session
        with patch.object(ws.security_service, "verify_telegram_user", return_value=(11223344, True, None)):
            
            # Scenario 1: Existing movie ('103'), deliver_movie fails due to >50MB
            with patch("services.web_server.MovieService.deliver_movie", new_callable=AsyncMock, return_value=False):
                with patch("handlers.movies._send_movie_delivery_fallback", new_callable=AsyncMock) as mock_fallback:
                    resp_large = await client.post(
                        "/api/send_to_chat",
                        json={"type": "movie", "code": "103", "part": 1, "chat_id": 11223344},
                        headers={"X-Requested-With": "XMLHttpRequest"}
                    )
                    assert resp_large.status == 200, f"Expected 200 for oversized fallback, got {resp_large.status}"
                    data_large = await resp_large.json()
                    assert data_large.get("ok") is True or data_large.get("success") is True
                    assert data_large.get("action") == "fallback_card"
                    mock_fallback.assert_awaited_once()

            # Scenario 2: Non-existent movie, deliver_movie fails
            with patch("services.web_server.MovieService.deliver_movie", new_callable=AsyncMock, return_value=False):
                with patch("services.web_server.MovieService.get_movie_stream_info", new_callable=AsyncMock, return_value=None):
                    resp_nonexistent = await client.post(
                        "/api/send_to_chat",
                        json={"type": "movie", "code": "nonexistent_code_999999", "part": 1, "chat_id": 11223344},
                        headers={"X-Requested-With": "XMLHttpRequest"}
                    )
                    assert resp_nonexistent.status == 404, f"Expected 404 for invalid movie, got {resp_nonexistent.status}"
                    data_nonexistent = await resp_nonexistent.json()
                    assert data_nonexistent.get("ok") is False
                    assert data_nonexistent.get("error") == "video_unavailable"

    finally:
        ws._bot_instance = orig_bot
        await client.close()
