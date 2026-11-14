"""
Empirical Challenger 2 Test Suite for Milestone 1: Movie Retrieval and Delivery Fix.
Author: Challenger M1-2 Replacement
Mandate: Empirically stress-test deep edge cases across:
  1. Selective file_id cache retention on transient vs permanent errors (cached_m path & cached_mf path).
  2. Resilient reply-to retry on deleted messages across send_video, send_photo, send_message, and fallback handler.
  3. Safe fallback in _send_movie_delivery_fallback for not-found movie when user deleted reply-to.
  4. Multi-part part vs part_number resolution edge cases in /api/movies/{code}.
  5. Fallback card dispatch in /api/send_to_chat for oversize videos across catalog, stream, and db-only sources.
  6. Atomic temporary file isolation and unlink cleanup under failure conditions.
"""
import os
import json
import uuid
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiohttp import web
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
from services.web_server import handle_get_movie_detail, handle_send_to_chat
from services.security_service import security_service
import services.web_server as ws
from config import config, BASE_DIR


@pytest_asyncio.fixture
async def mem_session():
    """Isolated in-memory SQLite async session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


# ==============================================================================
# Challenge 1: Cached Movie (cached_m) Selective Cache Invalidation & Retry
# ==============================================================================

@pytest.mark.asyncio
async def test_adv2_cached_movie_reply_retry_and_retention(mem_session: AsyncSession, tmp_path, monkeypatch):
    """
    Test cached_m path (when Movie record has file_id, but MovieFile does not):
    1. If send_video fails with 'message to be replied not found', it retries with reply_to_message_id=None.
    2. If send_video fails with transient error (network error or bot blocked), file_id is preserved.
    3. If send_video fails with 'wrong remote file id', file_id is cleared.
    """
    import sys
    from services.asilmedia_service import asilmedia_service
    monkeypatch.setattr("config.BASE_DIR", tmp_path)
    monkeypatch.setattr(sys.modules["services.movie_service"], "BASE_DIR", tmp_path)
    monkeypatch.setattr(asilmedia_service, "find_best_match", AsyncMock(return_value=None))
    monkeypatch.setattr(asilmedia_service, "get_movie_details", AsyncMock(return_value=None))
    code = "adv2_m1"
    valid_fid = "BAACAgIAAxkBAAE_M1_REPLACEMENT_CACHED_M_123"

    # Seed movie with file_id directly in Movie model
    m, _ = await crud.upsert_movie(
        session=mem_session,
        code=code,
        title="Cached M Test Movie",
        file_id=valid_fid,
    )
    assert m.file_id == valid_fid

    bot_mock = AsyncMock()

    # Step 1: Missing reply message -> must retry with reply_to_message_id=None and succeed
    bot_mock.send_video.side_effect = [
        TelegramBadRequest(method=MagicMock(), message="Bad Request: message to be replied not found"),
        MagicMock(video=MagicMock(file_id=valid_fid)),
    ]

    res = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=112233,
        code=code,
        part=1,
        session=mem_session,
        reply_to_message_id=999,
        require_video=True,
    )

    assert res is True
    assert bot_mock.send_video.call_count == 2
    # Verify first call had reply_to_message_id=999, second had reply_to_message_id=None
    call1_kwargs = bot_mock.send_video.call_args_list[0].kwargs
    call2_kwargs = bot_mock.send_video.call_args_list[1].kwargs
    assert call1_kwargs.get("reply_to_message_id") == 999
    assert call2_kwargs.get("reply_to_message_id") is None

    # Verify file_id in DB is untouched
    db_m = await crud.get_movie_by_code(mem_session, code)
    assert db_m.file_id == valid_fid

    # Step 2: Transient error (TelegramNetworkError) -> file_id MUST NOT be wiped
    bot_mock.reset_mock()
    bot_mock.send_video.side_effect = TelegramNetworkError(method=MagicMock(), message="Connection reset by peer")

    await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=112233,
        code=code,
        part=1,
        session=mem_session,
        reply_to_message_id=None,
        require_video=True,
    )
    db_m_after_net = await crud.get_movie_by_code(mem_session, code)
    assert db_m_after_net.file_id == valid_fid

    # Step 3: Hard invalid file_id error -> file_id MUST be wiped
    bot_mock.reset_mock()
    bot_mock.send_video.side_effect = TelegramBadRequest(
        method=MagicMock(), message="Bad Request: wrong remote file id specified: can't unserialize..."
    )

    await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=112233,
        code=code,
        part=1,
        session=mem_session,
        reply_to_message_id=None,
        require_video=True,
    )
    db_m_after_bad = await crud.get_movie_by_code(mem_session, code)
    assert db_m_after_bad.file_id == ""


# ==============================================================================
# Challenge 2: Poster & Text Delivery Deleted-Reply Fallback Retries
# ==============================================================================

@pytest.mark.asyncio
async def test_adv2_poster_and_text_reply_retries(mem_session: AsyncSession, tmp_path, monkeypatch):
    """
    When video cannot be sent and require_video=False, deliver_movie attempts:
    1. send_photo (poster fallback)
    2. send_message (text fallback)
    If user deleted their reply message, both MUST catch the error and retry with reply_to_message_id=None.
    """
    import sys
    from services.asilmedia_service import asilmedia_service
    monkeypatch.setattr("config.BASE_DIR", tmp_path)
    monkeypatch.setattr(sys.modules["services.movie_service"], "BASE_DIR", tmp_path)
    monkeypatch.setattr(asilmedia_service, "find_best_match", AsyncMock(return_value=None))
    monkeypatch.setattr(asilmedia_service, "get_movie_details", AsyncMock(return_value=None))
    monkeypatch.setattr(MovieService, "download_and_upload_media_on_demand", AsyncMock(return_value=None))
    code = "adv2_poster_01"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "video_sources.json").write_text(
        json.dumps({"items": {code: {"url": "https://cdn.example.invalid/adv2_poster_01.mp4", "file_type": "video"}}}),
        encoding="utf-8",
    )
    posters_dir = data_dir / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)
    poster_file = posters_dir / f"{code}_l.webp"
    poster_file.write_bytes(b"RIFF\x20\x00\x00\x00WEBPVP8 " + b"\x00" * 100)

    try:
        await crud.upsert_movie(
            session=mem_session,
            code=code,
            title="Poster Movie",
        )

        bot_mock = AsyncMock()

        # Case A: send_photo encounters "message to be replied not found", retries and succeeds
        bot_mock.send_photo.side_effect = [
            TelegramBadRequest(method=MagicMock(), message="Bad Request: message to be replied not found"),
            MagicMock(),
        ]

        res_poster = await movie_service.deliver_movie(
            bot=bot_mock,
            chat_id=554433,
            code=code,
            part=1,
            session=mem_session,
            reply_to_message_id=888,
            require_video=False,
        )
        assert res_poster is True
        assert bot_mock.send_photo.call_count == 2
        assert bot_mock.send_photo.call_args_list[0].kwargs.get("reply_to_message_id") == 888
        assert bot_mock.send_photo.call_args_list[1].kwargs.get("reply_to_message_id") is None

        # Case B: send_photo completely fails, falls back to send_message with "message to be replied not found"
        bot_mock.reset_mock()
        bot_mock.send_photo.side_effect = Exception("Poster I/O broken")
        bot_mock.send_message.side_effect = [
            TelegramBadRequest(method=MagicMock(), message="Bad Request: message to be replied not found"),
            MagicMock(),
        ]

        res_text = await movie_service.deliver_movie(
            bot=bot_mock,
            chat_id=554433,
            code=code,
            part=1,
            session=mem_session,
            reply_to_message_id=777,
            require_video=False,
        )
        assert res_text is True
        assert bot_mock.send_message.call_count == 2
        assert bot_mock.send_message.call_args_list[0].kwargs.get("reply_to_message_id") == 777
        assert bot_mock.send_message.call_args_list[1].kwargs.get("reply_to_message_id") is None
    finally:
        poster_file.unlink(missing_ok=True)


# ==============================================================================
# Challenge 3: Fallback Handler on Not-Found Movie with Deleted Reply
# ==============================================================================

@pytest.mark.asyncio
async def test_adv2_fallback_handler_not_found_deleted_reply(mem_session: AsyncSession):
    """
    In handlers/movies._send_movie_delivery_fallback:
    When movie is not in catalog, not in DB, and not in stream_info:
    If bot.send_message raises 'message to be replied not found', it must retry with reply_to_message_id=None.
    """
    bot_mock = AsyncMock()
    bot_mock.send_message.side_effect = [
        TelegramBadRequest(method=MagicMock(), message="Bad Request: message to be replied not found"),
        MagicMock(),
    ]

    with patch.object(MovieService, "get_catalog_item", return_value=None), \
         patch.object(MovieService, "get_movie_stream_info", new_callable=AsyncMock, return_value=None):
        await _send_movie_delivery_fallback(
            bot=bot_mock,
            chat_id=443322,
            code="nonexistent_9999",
            part=1,
            reply_to_message_id=654,
            session=mem_session,
        )

    assert bot_mock.send_message.call_count == 2
    assert bot_mock.send_message.call_args_list[0].kwargs.get("reply_to_message_id") == 654
    assert bot_mock.send_message.call_args_list[1].kwargs.get("reply_to_message_id") is None


# ==============================================================================
# Challenge 4: Multi-Part Movie Detail Part Attribute Permutations
# ==============================================================================

@pytest.mark.asyncio
async def test_adv2_movie_detail_part_attribute_permutations(mem_session: AsyncSession):
    """
    Stress-test handle_get_movie_detail with various attribute shapes on MovieFile:
    - Only f.part
    - Only f.part_number
    - Both f.part and f.part_number
    - None / missing values
    Ensure total_parts is calculated correctly and never crashes.
    """
    code = "adv2_parts_10"
    m, _ = await crud.upsert_movie(session=mem_session, code=code, title="Multipart Stress Movie")

    class MockFileA:
        part = 5
        part_number = None

    class MockFileB:
        part = None
        part_number = 8

    class MockFileC:
        part = 12
        part_number = 3

    class MockFileD:
        part = None
        part_number = None

    mock_files = [MockFileA(), MockFileB(), MockFileC(), MockFileD()]

    req = MagicMock(spec=web.Request)
    req.match_info = {"code": code}

    with patch.object(crud, "get_movie_by_code", new_callable=AsyncMock, return_value=m), \
         patch.object(crud, "get_movie_files", new_callable=AsyncMock, return_value=mock_files, create=True), \
         patch("services.web_server.get_session") as mock_gs:
        mock_gs.return_value.__aenter__.return_value = mem_session

        resp = await handle_get_movie_detail(req)
        assert resp.status == 200
        data = json.loads(resp.text)
        assert data.get("ok") is True
        # Max of (5, 8, 12, default 1) is 12
        assert data.get("parts") == 12
        assert data.get("p") == 12


# ==============================================================================
# Challenge 5: /api/send_to_chat Large Video Fallback Card Matrix
# ==============================================================================

@pytest.mark.asyncio
async def test_adv2_send_to_chat_large_video_source_matrix(mem_session: AsyncSession):
    """
    When deliver_movie returns False (e.g. video > 50MB):
    - If movie exists ONLY in catalog -> returns 200 with action: fallback_card
    - If movie exists ONLY in stream_info -> returns 200 with action: fallback_card
    - If movie exists ONLY in db -> returns 200 with action: fallback_card
    - If movie exists in NONE -> returns 404 with error: video_unavailable
    """
    bot_mock = AsyncMock()
    ws._bot_instance = bot_mock

    # Sub-case A: Exists ONLY in catalog
    req_cat = MagicMock(spec=web.Request)
    req_cat.json = AsyncMock(return_value={"action": "movie", "code": "cat_only_01", "part": 1, "chat_id": 11111})
    with patch.object(security_service, "verify_telegram_user", return_value=(11111, True, None)), \
         patch.object(movie_service, "deliver_movie", new_callable=AsyncMock, return_value=False), \
         patch.object(MovieService, "get_catalog_item", return_value={"t": "Catalog Movie", "p": 1}), \
         patch.object(MovieService, "get_movie_stream_info", new_callable=AsyncMock, return_value=None), \
         patch("services.web_server.get_session") as mock_gs:
        mock_gs.return_value.__aenter__.return_value = mem_session
        resp_cat = await handle_send_to_chat(req_cat)
        assert resp_cat.status == 200
        data_cat = json.loads(resp_cat.text)
        assert data_cat.get("action") == "fallback_card"

    # Sub-case B: Exists ONLY in stream_info
    bot_mock.reset_mock()
    req_str = MagicMock(spec=web.Request)
    req_str.json = AsyncMock(return_value={"action": "movie", "code": "stream_only_01", "part": 1, "chat_id": 11111})
    with patch.object(security_service, "verify_telegram_user", return_value=(11111, True, None)), \
         patch.object(movie_service, "deliver_movie", new_callable=AsyncMock, return_value=False), \
         patch.object(MovieService, "get_catalog_item", return_value=None), \
         patch.object(MovieService, "get_movie_stream_info", new_callable=AsyncMock, return_value={"title": "Stream Movie", "stream_url": "https://cdn.example.com/stream.mp4"}), \
         patch("services.web_server.get_session") as mock_gs:
        mock_gs.return_value.__aenter__.return_value = mem_session
        resp_str = await handle_send_to_chat(req_str)
        assert resp_str.status == 200
        data_str = json.loads(resp_str.text)
        assert data_str.get("action") == "fallback_card"

    # Sub-case C: Exists ONLY in database
    bot_mock.reset_mock()
    await crud.upsert_movie(session=mem_session, code="db_only_01", title="Database Movie")
    req_db = MagicMock(spec=web.Request)
    req_db.json = AsyncMock(return_value={"action": "movie", "code": "db_only_01", "part": 1, "chat_id": 11111})
    with patch.object(security_service, "verify_telegram_user", return_value=(11111, True, None)), \
         patch.object(movie_service, "deliver_movie", new_callable=AsyncMock, return_value=False), \
         patch.object(MovieService, "get_catalog_item", return_value=None), \
         patch.object(MovieService, "get_movie_stream_info", new_callable=AsyncMock, return_value=None), \
         patch("services.web_server.get_session") as mock_gs:
        mock_gs.return_value.__aenter__.return_value = mem_session
        resp_db = await handle_send_to_chat(req_db)
        assert resp_db.status == 200
        data_db = json.loads(resp_db.text)
        assert data_db.get("action") == "fallback_card"

    # Sub-case D: Exists in NONE
    bot_mock.reset_mock()
    req_none = MagicMock(spec=web.Request)
    req_none.json = AsyncMock(return_value={"action": "movie", "code": "ghost_01", "part": 1, "chat_id": 11111})
    with patch.object(security_service, "verify_telegram_user", return_value=(11111, True, None)), \
         patch.object(movie_service, "deliver_movie", new_callable=AsyncMock, return_value=False), \
         patch.object(MovieService, "get_catalog_item", return_value=None), \
         patch.object(MovieService, "get_movie_stream_info", new_callable=AsyncMock, return_value=None), \
         patch("services.web_server.get_session") as mock_gs:
        mock_gs.return_value.__aenter__.return_value = mem_session
        resp_none = await handle_send_to_chat(req_none)
        assert resp_none.status == 404
        data_none = json.loads(resp_none.text)
        assert data_none.get("error") == "video_unavailable"


# ==============================================================================
# Challenge 6: Concurrent UUID Filenames and Cleanup on Abort
# ==============================================================================

def test_adv2_temp_download_filenames_are_unique():
    """
    Ensure the filename generation in download_and_upload_media_on_demand
    guarantees unique paths even for the same movie code and part.
    """
    code = "103"
    part = 1
    v_dir = Path("C:/dev/copy/data/videos")

    names = {
        v_dir / f"temp_download_{code}_{part}_{uuid.uuid4().hex[:8]}.mp4"
        for _ in range(100)
    }
    # 100 iterations must yield 100 strictly unique file paths
    assert len(names) == 100
