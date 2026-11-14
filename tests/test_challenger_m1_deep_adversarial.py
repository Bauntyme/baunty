"""
Empirical Adversarial Test Suite - Challenger M1-1
Direct empirical verification of:
1. Deleted reply message handling (TelegramBadRequest: message to be replied not found)
2. Selective file_id cache retention (preserving file_id on network timeout / user block / flood limits)
3. Windows file locking concurrency & UUID temporary filenames
4. >50MB fallback delivery in /api/send_to_chat (fallback card vs 404)
5. Multi-part serial part calculation in /api/movies/{code} (f.part vs f.part_number)
"""

import asyncio
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import BASE_DIR, config
from database import crud
from database.models import Base, Movie, MovieFile
from handlers.movies import _send_movie_delivery_fallback
from services.movie_service import MovieService, movie_service
from services.web_server import create_web_app
import services.web_server as ws


@pytest_asyncio.fixture
async def mem_session():
    """In-memory SQLite isolated session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


# =====================================================================
# 1. Deleted Reply Message Handling
# =====================================================================

@pytest.mark.asyncio
async def test_deleted_reply_cached_movie_file_retries_and_succeeds(mem_session):
    """When replying to a deleted message, cached MovieFile send retries without reply_to_message_id."""
    bot = AsyncMock()
    
    sent_mock = MagicMock()
    sent_mock.video = MagicMock(file_id="BAACAgIAAxkBAA_VALID_FILE_ID...", duration=120, file_size=1048576)

    call_count = 0
    async def mock_send_video(**kwargs):
        nonlocal call_count
        call_count += 1
        if kwargs.get("reply_to_message_id") is not None:
            raise TelegramBadRequest(
                method="sendVideo",
                message="Bad Request: message to be replied not found"
            )
        return sent_mock

    bot.send_video.side_effect = mock_send_video

    # Seed DB with a Movie and MovieFile
    m = Movie(code="8801", title="Test Deleted Reply", views_count=0)
    mem_session.add(m)
    await mem_session.flush()

    mf = MovieFile(
        movie_code="8801",
        part=1,
        file_id="BAACAgIAAxkBAA_VALID_FILE_ID...",
        file_type="video",
        duration=120,
        file_size=1048576,
    )
    mem_session.add(mf)
    await mem_session.commit()

    # Deliver movie with deleted reply_to_message_id=99999
    success = await MovieService._deliver_movie_impl(
        bot=bot,
        chat_id=12345,
        code="8801",
        part=1,
        session=mem_session,
        reply_to_message_id=99999,
        require_video=True,
    )

    assert success is True
    assert call_count == 2
    # Check that file_id was NOT wiped
    await mem_session.refresh(mf)
    assert mf.file_id == "BAACAgIAAxkBAA_VALID_FILE_ID..."


@pytest.mark.asyncio
async def test_deleted_reply_fallback_card_retries_and_succeeds():
    """In handlers/movies._send_movie_delivery_fallback, deleted reply message falls back to reply_to_message_id=None."""
    bot = AsyncMock()

    call_count = 0
    async def mock_send_message(**kwargs):
        nonlocal call_count
        call_count += 1
        if kwargs.get("reply_to_message_id") is not None:
            raise TelegramBadRequest(
                method="sendMessage",
                message="Bad Request: message to be replied not found"
            )
        return MagicMock()

    bot.send_message.side_effect = mock_send_message

    # Test with non-existent movie
    await _send_movie_delivery_fallback(
        bot=bot,
        chat_id=12345,
        code="nonexistent_code_9999",
        part=1,
        reply_to_message_id=123456,
    )
    assert call_count == 2
    # Verify the second call had reply_to_message_id=None
    second_call = bot.send_message.call_args_list[1]
    assert second_call.kwargs.get("reply_to_message_id") is None


# =====================================================================
# 2. Selective file_id Cache Retention
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("error_exc,expected_retention", [
    (asyncio.TimeoutError("Connection timed out after 30s"), True),
    (TelegramForbiddenError(method="sendVideo", message="Forbidden: bot was blocked by the user"), True),
    (TelegramRetryAfter(method="sendVideo", message="Too Many Requests: retry after 10", retry_after=10), True),
    (TelegramBadRequest(method="sendVideo", message="Bad Request: wrong remote file id specified"), False),
    (TelegramBadRequest(method="sendVideo", message="Bad Request: wrong file identifier/HTTP URL specified"), False),
])
async def test_cache_retention_only_wipes_on_true_invalid_file_tokens(mem_session, error_exc, expected_retention):
    """Contextual errors must retain file_id; only true invalid file token errors may wipe file_id."""
    bot = AsyncMock()
    bot.send_video.side_effect = error_exc

    code = f"ret_{uuid.uuid4().hex[:6]}"
    m = Movie(code=code, title="Test Retention", views_count=0)
    mem_session.add(m)
    await mem_session.flush()

    mf = MovieFile(
        movie_code=code,
        part=1,
        file_id="BAACAgIAAxkBAA_STABLE_TOKEN...",
        file_type="video",
        duration=120,
        file_size=1048576,
    )
    mem_session.add(mf)
    await mem_session.commit()

    with patch.object(MovieService, "resolve_video_source", return_value=None):
        await MovieService._deliver_movie_impl(
            bot=bot,
            chat_id=12345,
            code=code,
            part=1,
            session=mem_session,
            require_video=True,
        )

    await mem_session.refresh(mf)
    if expected_retention:
        assert mf.file_id == "BAACAgIAAxkBAA_STABLE_TOKEN...", (
            f"file_id was erroneously cleared on error: {error_exc}"
        )
    else:
        assert mf.file_id == "", (
            f"file_id should have been cleared for invalid file token: {error_exc}"
        )


# =====================================================================
# 3. Windows File Locking Concurrency (UUID Temporary Filename)
# =====================================================================

@pytest.mark.asyncio
async def test_concurrent_downloads_use_unique_uuid_filenames(mem_session):
    """Concurrent on-demand downloads must use unique UUID-suffixed filenames to prevent WinError 32."""
    created_filenames = set()

    real_open = open
    def track_open(file, *args, **kwargs):
        s = str(file)
        if "temp_download_concurrent_" in s:
            created_filenames.add(s)
        return real_open(file, *args, **kwargs)

    mp4_bytes = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 200000)

    class FakeContent:
        async def iter_chunked(self, _size):
            yield mp4_bytes

    class FakeResp:
        status = 200
        headers = {"Content-Type": "video/mp4", "Content-Length": str(len(mp4_bytes))}
        content = FakeContent()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClientSession:
        def __init__(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            return FakeResp()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    bot = AsyncMock()
    sent_msg = MagicMock()
    sent_msg.video = MagicMock(file_id="BAACAgIAAxkBAA_CONCURRENT...", duration=120, file_size=len(mp4_bytes))
    bot.send_video.return_value = sent_msg

    with patch("services.movie_service.aiohttp.ClientSession", FakeClientSession):
        with patch("services.movie_service.open", side_effect=track_open):
            # Run 5 concurrent downloads with distinct codes so each generates a temp file
            tasks = [
                MovieService.download_and_upload_media_on_demand(
                    bot=bot,
                    chat_id=12345 + i,
                    code=f"concurrent_{i}",
                    part=1,
                    source_url="http://fakecdn.local/video.mp4",
                    caption="Test",
                    session=mem_session,
                )
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)

    # All should complete without permission errors and each should have had a distinct file path
    assert len(created_filenames) == 5, f"Expected 5 distinct filenames, got {len(created_filenames)}"
    for fn in created_filenames:
        assert not Path(fn).exists(), f"Temp file {fn} was not unlinked!"


# =====================================================================
# 4. Large Video (>50MB) WebApp /api/send_to_chat
# =====================================================================

@pytest.mark.asyncio
async def test_api_send_to_chat_large_video_fallback():
    """When deliver_movie returns False for >50MB video, return 200 fallback_card if movie exists, 404 if not."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    mock_bot = AsyncMock()
    orig_bot = ws._bot_instance
    ws._bot_instance = mock_bot

    try:
        # 1. Existing movie (e.g. 103 in catalog or stream sources)
        with patch.object(ws.security_service, "verify_telegram_user", return_value=(998877, True, None)):
            with patch("services.web_server.MovieService.deliver_movie", new_callable=AsyncMock) as mock_del:
                mock_del.return_value = False
                with patch("services.web_server.MovieService.get_movie_stream_info", new_callable=AsyncMock) as mock_si:
                    mock_si.return_value = {"url": "https://cdn.example.com/stream.mp4"}
                    with patch("handlers.movies._send_movie_delivery_fallback", new_callable=AsyncMock) as mock_fb:
                        resp = await client.post(
                            "/api/send_to_chat",
                            json={"type": "movie", "code": "103", "chat_id": 998877},
                            headers={"X-Requested-With": "XMLHttpRequest"}
                        )
                        assert resp.status == 200
                        data = await resp.json()
                        assert data.get("ok") is True
                        assert data.get("action") == "fallback_card"
                        assert "fallback" in data.get("message", "").lower() or "havolasi" in data.get("message", "").lower()
                        mock_fb.assert_awaited_once()

        # 2. Non-existent movie should return 404 video_unavailable
        with patch.object(ws.security_service, "verify_telegram_user", return_value=(998877, True, None)):
            with patch("services.web_server.MovieService.deliver_movie", new_callable=AsyncMock) as mock_del:
                mock_del.return_value = False
                with patch("services.web_server.MovieService.get_movie_stream_info", new_callable=AsyncMock) as mock_si:
                    mock_si.return_value = None
                    resp = await client.post(
                        "/api/send_to_chat",
                        json={"type": "movie", "code": "strictly_nonexistent_999999", "chat_id": 998877},
                        headers={"X-Requested-With": "XMLHttpRequest"}
                    )
                    assert resp.status == 404
                    data = await resp.json()
                    assert data.get("ok") is False
                    assert data.get("error") == "video_unavailable"
    finally:
        ws._bot_instance = orig_bot
        await client.close()


# =====================================================================
# 5. Multi-Part Serial Part Extraction in /api/movies/{code}
# =====================================================================

@pytest.mark.asyncio
async def test_api_movie_detail_handles_part_attribute():
    """Verify handle_get_movie_detail handles MovieFile.part when part_number is absent."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        mock_movie = SimpleNamespace(
            id=1,
            code="serial_test_99",
            title="Serial Test",
            genres="Action",
            year=2024,
            rating=8.5,
            duration=6000,
            views_count=10,
            downloads_count=5,
            description="Test serial",
            file_id="FID",
        )
        mock_file1 = SimpleNamespace(part=1, part_number=None, file_id="F1")
        mock_file2 = SimpleNamespace(part=2, part_number=None, file_id="F2")
        mock_file3 = SimpleNamespace(part=3, part_number=None, file_id="F3")

        with patch("services.web_server.crud.get_movie_by_code", new_callable=AsyncMock) as mock_get_m:
            mock_get_m.return_value = mock_movie
            with patch.object(crud, "get_movie_files", create=True, new_callable=AsyncMock) as mock_get_f:
                mock_get_f.return_value = [mock_file1, mock_file2, mock_file3]
                resp = await client.get("/api/movies/serial_test_99")
                assert resp.status == 200
                data = await resp.json()
                assert data.get("ok") is True
                assert data.get("p") == 3, f"Expected p=3, got {data.get('p')}"
                assert data.get("parts") == 3, f"Expected parts=3, got {data.get('parts')}"
    finally:
        await client.close()
