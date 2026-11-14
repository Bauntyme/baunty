"""
Milestone 1 Empirical Challenger Adversarial Test Suite
Author: Challenger M1-2
Mandate: Empirically stress-test Movie Retrieval and Delivery Fixes (R1).
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
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base, Movie, MovieFile
from database import crud
from services.movie_service import movie_service, MovieService
from handlers.movies import _send_movie_delivery_fallback, extract_movie_code_and_part, extract_movie_code
from services.web_server import handle_get_movie_detail, handle_send_to_chat
from services.security_service import security_service
import services.web_server as ws
from config import config, BASE_DIR


@pytest_asyncio.fixture
async def mem_session():
    """In-memory SQLite async session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


# =====================================================================
# Challenge 1: Selective file_id Invalidation vs Context Error Retention
# =====================================================================

@pytest.mark.asyncio
async def test_adv_cache_retention_on_transient_telegram_errors(mem_session: AsyncSession):
    """
    Stress-test Cloud Pool cache retention:
    - Transient errors (Blocked by user, Timeout, FloodWait) MUST NOT wipe cached file_id.
    - True file invalidation errors (wrong remote file id, wrong file identifier) MUST wipe cached file_id.
    """
    valid_fid = "BAACAgIAAxkBAAE_CHALLENGER_VALID_FID_123"
    code = "adv_901"
    part = 1

    # 1. Seed movie and movie file in DB
    await crud.upsert_movie(session=mem_session, code=code, title="Test Movie 901")
    mf = await crud.save_movie_file(
        session=mem_session,
        movie_code=code,
        part=part,
        file_id=valid_fid,
        file_type="video",
        duration=180,
        file_size=1024 * 1024 * 10
    )
    assert mf.file_id == valid_fid

    bot_mock = AsyncMock()

    # Scenario A: User blocked bot -> file_id MUST be preserved
    bot_mock.send_video.side_effect = TelegramForbiddenError(
        method=MagicMock(), message="Forbidden: bot was blocked by the user"
    )
    res_block = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=123456,
        code=code,
        part=part,
        session=mem_session,
        require_video=True
    )
    assert res_block is False
    check_mf = await crud.get_movie_file(mem_session, code, part)
    assert check_mf is not None
    assert check_mf.file_id == valid_fid, "file_id was wiped on user block error!"

    # Scenario B: Network timeout -> file_id MUST be preserved
    bot_mock.send_video.side_effect = TelegramNetworkError(
        method=MagicMock(), message="Connection reset by peer / timed out"
    )
    res_timeout = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=123456,
        code=code,
        part=part,
        session=mem_session,
        require_video=True
    )
    assert res_timeout is False
    check_mf = await crud.get_movie_file(mem_session, code, part)
    assert check_mf.file_id == valid_fid, "file_id was wiped on network timeout error!"

    # Scenario C: TelegramBadRequest with invalid file identifier token -> MUST be wiped!
    bot_mock.send_video.side_effect = TelegramBadRequest(
        method=MagicMock(), message="Bad Request: wrong remote file id specified: can't unserialize"
    )
    res_bad_fid = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=123456,
        code=code,
        part=part,
        session=mem_session,
        require_video=True
    )
    assert res_bad_fid is False
    check_mf = await crud.get_movie_file(mem_session, code, part)
    assert check_mf.file_id == "", "file_id was NOT invalidated on invalid file identifier error!"


# =====================================================================
# Challenge 2: Deleted Reply-To Message Retry Resilience
# =====================================================================

@pytest.mark.asyncio
async def test_adv_deleted_reply_retry_in_deliver_movie(mem_session: AsyncSession):
    """
    Stress-test deliver_movie when reply_to_message_id is deleted:
    - 1st call to bot.send_video raises 'Bad Request: message to be replied not found'
    - 2nd call (retry without reply_to_message_id) MUST succeed with True.
    """
    code = "adv_902"
    part = 1
    valid_fid = "BAACAgIAAxkBAAE_CHALLENGER_REPLY_FID"

    await crud.upsert_movie(session=mem_session, code=code, title="Test Movie 902")
    await crud.save_movie_file(
        session=mem_session,
        movie_code=code,
        part=part,
        file_id=valid_fid,
        file_type="video",
        duration=180
    )

    sent_success = MagicMock(video=MagicMock(file_id=valid_fid), document=None)
    bot_mock = AsyncMock()

    call_count = 0
    async def mock_send_video(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if kwargs.get("reply_to_message_id") is not None:
            raise TelegramBadRequest(method=MagicMock(), message="Bad Request: message to be replied not found")
        return sent_success

    bot_mock.send_video = AsyncMock(side_effect=mock_send_video)

    delivered = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=777888,
        code=code,
        part=part,
        reply_to_message_id=99999,
        session=mem_session,
        require_video=True
    )

    assert delivered is True, "deliver_movie did not recover from deleted reply message!"
    assert call_count == 2, f"Expected 2 attempts (initial + retry), got {call_count}"


@pytest.mark.asyncio
async def test_adv_deleted_reply_retry_in_fallback_handler():
    """
    Stress-test _send_movie_delivery_fallback:
    - Both 'not found' and 'fallback streaming card' paths must recover when reply_to_message_id is deleted.
    """
    bot_mock = AsyncMock()
    send_attempts = []

    async def mock_send_message(*args, **kwargs):
        send_attempts.append(kwargs)
        if kwargs.get("reply_to_message_id") is not None:
            raise TelegramBadRequest(method=MagicMock(), message="Bad Request: message to be replied not found")
        return MagicMock()

    bot_mock.send_message = AsyncMock(side_effect=mock_send_message)

    # 1. Non-existent movie fallback
    send_attempts.clear()
    await _send_movie_delivery_fallback(
        bot=bot_mock,
        chat_id=555111,
        code="totally_unknown_code_9999",
        part=1,
        reply_to_message_id=4444
    )
    assert len(send_attempts) == 2
    assert send_attempts[0]["reply_to_message_id"] == 4444
    assert send_attempts[1]["reply_to_message_id"] is None

    # 2. Known catalog movie fallback
    send_attempts.clear()
    await _send_movie_delivery_fallback(
        bot=bot_mock,
        chat_id=555111,
        code="103",
        part=1,
        reply_to_message_id=4444
    )
    assert len(send_attempts) == 2
    assert send_attempts[0]["reply_to_message_id"] == 4444
    assert send_attempts[1]["reply_to_message_id"] is None


# =====================================================================
# Challenge 3: Windows Concurrent Download Isolation
# =====================================================================

@pytest.mark.asyncio
async def test_adv_concurrent_download_uuid_isolation():
    """
    Verify unique UUID temp filenames prevent Windows I/O sharing violations.
    Simulate 5 parallel download invocations for the same movie code.
    """
    mp4_bytes = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 120000)

    class FakeChunkStream:
        async def iter_chunked(self, size):
            yield mp4_bytes

    class FakeResp:
        status = 200
        headers = {"Content-Type": "video/mp4", "Content-Length": str(len(mp4_bytes))}
        content = FakeChunkStream()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    class FakeClientSession:
        def get(self, *args, **kwargs):
            return FakeResp()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    bot_mock = AsyncMock()
    bot_mock.send_video = AsyncMock(return_value=MagicMock(video=MagicMock(file_id="FID_TEMP_TEST", duration=120, file_size=len(mp4_bytes))))

    with patch("aiohttp.ClientSession", return_value=FakeClientSession()):
        tasks = [
            MovieService.download_and_upload_media_on_demand(
                bot=bot_mock,
                chat_id=1000 + i,
                code="adv_concur",
                part=1,
                source_url="http://media.example.com/stream.mp4",
                caption="Adversarial test",
                duration=120,
                reply_markup=None,
                reply_to_message_id=None
            )
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            assert not isinstance(r, Exception), f"Concurrent download failed with exception: {r}"
            assert r is not None, "Expected valid message return from download_and_upload_media_on_demand"

    # Confirm no orphan temp files remained in data/videos
    v_dir = Path(BASE_DIR) / "data" / "videos"
    orphans = list(v_dir.glob("temp_download_adv_concur_*.mp4"))
    assert len(orphans) == 0, f"Found orphan temp files: {orphans}"


# =====================================================================
# Challenge 4: Multi-Part Serial Compatibility in Web API
# =====================================================================

@pytest.mark.asyncio
async def test_adv_handle_get_movie_detail_part_attribute_compatibility(mem_session: AsyncSession):
    """
    Stress-test handle_get_movie_detail part counting:
    SQLAlchemy model MovieFile defines column 'part', while older code looked for 'part_number'.
    Verify both 'part' and 'part_number' attributes on db_files are correctly resolved.
    """
    movie = await crud.upsert_movie(
        session=mem_session,
        code="adv_serial_1",
        title="Adversarial Serial",
        description="Multi-part test"
    )

    class MockMovieFile:
        def __init__(self, part=None, part_number=None):
            if part is not None:
                self.part = part
            if part_number is not None:
                self.part_number = part_number

    mock_files = [
        MockMovieFile(part=1),
        MockMovieFile(part=2),
        MockMovieFile(part=4),  # uses .part
    ]

    class MemSessionCtx:
        async def __aenter__(self):
            return mem_session
        async def __aexit__(self, *args):
            pass

    req = MagicMock(spec=web.Request)
    req.match_info = {"code": "adv_serial_1"}

    with patch("services.web_server.get_session", return_value=MemSessionCtx()), \
         patch.object(crud, "get_movie_files", new_callable=AsyncMock, return_value=mock_files, create=True):
        resp = await handle_get_movie_detail(req)
        assert resp.status == 200
        data = json.loads(resp.text)
        assert data.get("ok") is True
        assert data.get("parts") == 4, f"Expected 4 parts, got {data.get('parts')}"
        assert data.get("p") == 4


# =====================================================================
# Challenge 5: /api/send_to_chat Oversized Fallback vs 404
# =====================================================================

@pytest.mark.asyncio
async def test_adv_send_to_chat_oversized_fallback_and_invalid_404():
    """
    Stress-test handle_send_to_chat:
    - When deliver_movie returns False for an existing movie (>50MB):
      MUST return 200 with action: 'fallback_card' and dispatch card to Telegram.
    - When deliver_movie returns False for an invalid non-existent movie:
      MUST return 404 with error: 'video_unavailable'.
    """
    bot_mock = AsyncMock()
    bot_mock.send_message = AsyncMock()
    ws._bot_instance = bot_mock

    # Case A: Known catalog movie (e.g. '103') where delivery returns False
    req_known = MagicMock(spec=web.Request)
    req_known.json = AsyncMock(return_value={
        "action": "movie",
        "code": "103",
        "part": 1,
        "chat_id": 998877
    })

    with patch.object(security_service, "verify_telegram_user", return_value=(998877, True, None)), \
         patch.object(movie_service, "deliver_movie", new_callable=AsyncMock, return_value=False):
        resp_known = await handle_send_to_chat(req_known)
        assert resp_known.status == 200
        data_known = json.loads(resp_known.text)
        assert data_known.get("ok") is True
        assert data_known.get("action") == "fallback_card"
        assert bot_mock.send_message.called is True

    # Case B: Unknown non-existent movie code
    bot_mock.reset_mock()
    req_unknown = MagicMock(spec=web.Request)
    req_unknown.json = AsyncMock(return_value={
        "action": "movie",
        "code": "unknown_nonexistent_999999",
        "part": 1,
        "chat_id": 998877
    })

    with patch.object(security_service, "verify_telegram_user", return_value=(998877, True, None)), \
         patch.object(movie_service, "deliver_movie", new_callable=AsyncMock, return_value=False):
        resp_unknown = await handle_send_to_chat(req_unknown)
        assert resp_unknown.status == 404
        data_unknown = json.loads(resp_unknown.text)
        assert data_unknown.get("ok") is False
        assert data_unknown.get("error") == "video_unavailable"


# =====================================================================
# Challenge 6: Fuzzing & Injection Resilience
# =====================================================================

@pytest.mark.asyncio
async def test_adv_fuzzing_and_injection_payloads(mem_session: AsyncSession):
    """
    Inject malicious payloads into movie code extraction and delivery.
    Verify zero uncaught exceptions, zero SQL injections, and clean handling.
    """
    fuzz_payloads = [
        "<script>alert('xss')</script>",
        "'; DROP TABLE movies; --",
        "../../../../../../etc/passwd",
        "\\x00\\xff\\xfe",
        "103' UNION SELECT * FROM users --",
        "NaN",
        "-1",
        "0",
        "99999999999999999999999999999999999999999999999999999999999999999999",
        " \t \n \r ",
    ]

    bot_mock = AsyncMock()

    for payload in fuzz_payloads:
        # 1. extract_movie_code_and_part should not crash
        res_extract = extract_movie_code_and_part(payload)
        # 2. deliver_movie should return False gracefully without throwing
        res_deliv = await movie_service.deliver_movie(
            bot=bot_mock,
            chat_id=12345,
            code=payload,
            part=1,
            session=mem_session,
            require_video=True
        )
        assert res_deliv is False, f"Fuzz payload {payload!r} unexpectedly succeeded!"
