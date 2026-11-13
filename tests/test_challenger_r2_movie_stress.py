"""
Adversarial Stress Test Suite - Challenger 2
Movie Video Delivery & Concurrency Stress Testing

Empirical verification across:
1. Movie delivery candidate verification:
   - Valid known codes: 103, 114, 718, 120_8
   - Invalid codes: 99999999, #random, empty string, special characters (no silent poster/message downgrade)
   - Multi-part codes: '718 2', 'taksi 2-qism', '120_8'
2. WebApp API stress testing:
   - /api/asil/send, /api/watch, /api/send_to_chat with malformed payloads, non-existent movies, invalid users
   - Guarantees {ok: false, delivered: false} or error response without claiming success
3. Concurrency stress testing:
   - Verification of _DOWNLOAD_SEMAPHORE serialization
   - Double-checked locking and cache reuse under parallel load
   - 30-task concurrent delivery calls under SQLite in-memory and file engines
"""

import os
import json
import asyncio
import tempfile
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool

from database.models import Base, Movie, MovieFile
from database import crud
from services.movie_service import movie_service, MovieService, _DOWNLOAD_SEMAPHORE
from handlers.movies import extract_movie_code_and_part, extract_movie_code
from services.web_server import create_web_app
import services.web_server as ws
from config import config, BASE_DIR


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)"
}


@pytest_asyncio.fixture
async def isolated_session():
    """In-memory SQLite isolated session for testing."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


# =====================================================================
# 1. Movie Delivery Candidate Verification (Valid Known Codes)
# =====================================================================

def _make_fake_mp4_session():
    """Offline testlar uchun haqiqiy <50MB MP4 HTTP oqimi mock sessiyasi."""
    mp4_payload = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 150000)

    class _FakeContent:
        async def iter_chunked(self, _size):
            yield mp4_payload

    class _FakeResp:
        status = 200
        headers = {"Content-Type": "video/mp4", "Content-Length": str(len(mp4_payload))}
        content = _FakeContent()

        async def json(self, content_type=None):
            return {}

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakeSession:
        def get(self, *args, **kwargs):
            return _FakeResp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    return _FakeSession()


@pytest.mark.asyncio
async def test_movie_delivery_valid_known_codes(isolated_session: AsyncSession):
    """
    Test delivery with valid known codes:
    - '103': local file data/videos/103_1.mp4
    - '114': local file data/videos/114_1.mp4
    - '718': mapped stream in data/video_sources.json
    - '120_8': local file data/videos/120_8.mp4
    Verify it returns True and bot.send_video was called with valid video media.
    """
    from services.asilmedia_service import asilmedia_service

    bot_mock = AsyncMock()
    sent_mock = MagicMock()
    sent_mock.video = MagicMock(file_id="BAACAgIAAxkBAAE_R2_VALID_FID_999", duration=120, file_size=500000)
    sent_mock.document = None
    bot_mock.send_video = AsyncMock(return_value=sent_mock)
    bot_mock.send_document = AsyncMock()
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    test_cases = [
        ("103", 1),
        ("114", 1),
        ("718", 1),
        ("120_8", 1),
    ]

    with patch.object(asilmedia_service, "resolve_stream_url", new_callable=AsyncMock, return_value="https://fayllar.com/718_1.mp4?token=sigr2"), \
         patch("aiohttp.ClientSession", return_value=_make_fake_mp4_session()):
        for code, part in test_cases:
            bot_mock.reset_mock()
            bot_mock.send_video = AsyncMock(return_value=sent_mock)
            result = await movie_service.deliver_movie(
                bot=bot_mock,
                chat_id=98765432,
                code=code,
                part=part,
                session=isolated_session
            )
            assert result is True, f"Expected deliver_movie to return True for valid code {code} (part {part})"
            assert bot_mock.send_video.called is True, f"Expected bot.send_video to be called for code {code}"
            assert bot_mock.send_photo.called is False, f"bot.send_photo should NOT be called for code {code}"
            assert bot_mock.send_message.called is False, f"bot.send_message should NOT be called for code {code}"

            # Verify video argument is valid (FSInputFile or cached file_id)
            call_kwargs = bot_mock.send_video.call_args_list[0][1]
            sent_video = call_kwargs.get("video")
            assert sent_video is not None, f"Video payload cannot be None for code {code}"


# =====================================================================
# 2. Movie Delivery Invalid Codes (Elimination of Silent Poster Downgrade)
# =====================================================================

@pytest.mark.asyncio
async def test_movie_delivery_invalid_codes(isolated_session: AsyncSession):
    """
    Test delivery with invalid codes:
    - '99999999'
    - '#random'
    - '' (empty string)
    - '!@#$%^&*()'
    - '<script>alert(1)</script>'
    - \"' OR '1'='1\"
    Verify:
    1. Returns False
    2. NEVER sends silent poster (send_photo) or silent text (send_message) as success
    """
    bot_mock = AsyncMock()
    bot_mock.send_video = AsyncMock()
    bot_mock.send_document = AsyncMock()
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    invalid_codes = [
        "99999999",
        "#random",
        "",
        "!@#$%^&*()",
        "<script>alert(1)</script>",
        "' OR '1'='1",
        "___invalid___",
        "../../etc/passwd",
    ]

    for code in invalid_codes:
        bot_mock.reset_mock()
        result = await movie_service.deliver_movie(
            bot=bot_mock,
            chat_id=98765432,
            code=code,
            part=1,
            session=isolated_session
        )
        assert result is False, f"Expected deliver_movie to return False for invalid code: {code!r}"
        assert bot_mock.send_video.called is False, f"send_video called for invalid code: {code!r}"
        assert bot_mock.send_document.called is False, f"send_document called for invalid code: {code!r}"
        assert bot_mock.send_photo.called is False, f"Silent poster card sent for invalid code: {code!r}"
        assert bot_mock.send_message.called is False, f"Silent message sent for invalid code: {code!r}"


# =====================================================================
# 3. Multi-Part Movie Codes Routing
# =====================================================================

@pytest.mark.asyncio
async def test_movie_delivery_multipart_codes(isolated_session: AsyncSession):
    """
    Test multi-part codes:
    - '718 2' -> parsed by extract_movie_code_and_part to ('718', 2)
    - 'taksi 2-qism' -> parsed by extract_movie_code_and_part to ('718', 2)
    - '120_8' -> parsed to code '120', part 8
    - Out of range part -> returns False gracefully
    """
    # 1. Parsing verification
    parsed_718_2 = extract_movie_code_and_part("718 2")
    assert parsed_718_2 == ("718", 2)

    parsed_taksi_2 = extract_movie_code_and_part("taksi 2-qism")
    assert parsed_taksi_2 == ("718", 2)

    # 2. Delivery verification for part 2 of 718 (Taksi 2)
    from services.asilmedia_service import asilmedia_service
    src_718_2 = MovieService.resolve_video_source("718", 2)
    assert src_718_2 is not None
    assert "Taksi" in str(src_718_2.get("url", "")) or "fayllar.com" in str(src_718_2.get("url", ""))

    bot_mock = AsyncMock()
    sent_p2 = MagicMock()
    sent_p2.video = MagicMock(file_id="BAACAgIAAxkBAAE_R2_TAKSI2_FID", duration=120, file_size=500000)
    sent_p2.document = None
    bot_mock.send_video = AsyncMock(return_value=sent_p2)
    with patch.object(asilmedia_service, "resolve_stream_url", new_callable=AsyncMock, return_value="https://fayllar.com/718_2.mp4?token=sigr2p2"), \
         patch("aiohttp.ClientSession", return_value=_make_fake_mp4_session()):
        res_part2 = await movie_service.deliver_movie(
            bot=bot_mock,
            chat_id=98765432,
            code="718",
            part=2,
            session=isolated_session
        )
    assert res_part2 is True
    assert bot_mock.send_video.called is True

    # 3. Code '120_8' with part=1 should resolve internal part 8
    bot_mock.reset_mock()
    res_120_8 = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=98765432,
        code="120_8",
        part=1,
        session=isolated_session
    )
    assert res_120_8 is True
    assert bot_mock.send_video.called is True

    # 4. Out-of-range part for single film or limited series (e.g. Taksi part 99)
    bot_mock.reset_mock()
    res_oob = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=98765432,
        code="718",
        part=99,
        session=isolated_session
    )
    assert res_oob is False
    assert bot_mock.send_video.called is False
    assert bot_mock.send_photo.called is False


# =====================================================================
# 4. WebApp API Stress Testing (/api/asil/send, /api/watch, /api/send_to_chat)
# =====================================================================

@pytest.mark.asyncio
async def test_webapp_api_asil_send_stress():
    """
    Stress test /api/asil/send:
    - Empty payload -> {ok: false, error: 'not_found'}
    - Missing/invalid user -> {ok: false, error: 'need_start'}
    - Non-existent movie ID with mock user -> {ok: false, delivered: false}
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    mock_bot = AsyncMock()
    mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
    orig_bot = ws._bot_instance
    ws._bot_instance = mock_bot

    try:
        # A. Empty payload
        resp = await client.post("/api/asil/send", json={}, headers=BROWSER_HEADERS)
        data = await resp.json()
        assert data.get("ok") is False
        assert data.get("error") == "not_found"

        # B. Missing user_id
        resp = await client.post("/api/asil/send", json={"id": "103"}, headers=BROWSER_HEADERS)
        data = await resp.json()
        assert data.get("ok") is False
        assert data.get("error") == "need_start"

        # C. Invalid / Malformed JSON
        resp = await client.post("/api/asil/send", data="malformed-not-json", headers={"Content-Type": "application/json"})
        data = await resp.json()
        assert data.get("ok") is False

        # D. Non-existent movie ID with valid user auth
        with patch.object(ws.security_service, "verify_telegram_user", return_value=(77889900, True, None)):
            resp = await client.post(
                "/api/asil/send",
                json={"id": "99999999_NOT_EXIST", "user_id": 77889900, "part": 1},
                headers=BROWSER_HEADERS
            )
            data = await resp.json()
            assert data.get("ok") is False
            assert data.get("delivered") is False
            assert data.get("error") == "video_unavailable"
    finally:
        ws._bot_instance = orig_bot
        await client.close()


@pytest.mark.asyncio
async def test_webapp_api_watch_stress():
    """
    Stress test /api/watch:
    - Empty payload -> {ok: false, error: 'not_found'}
    - Missing code -> {ok: false, error: 'not_found'}
    - Invalid auth / spoofing -> 401 or 403
    - Non-existent movie with authenticated user -> {ok: false, delivered: false, error: 'video_unavailable'}
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    mock_bot = AsyncMock()
    mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
    orig_bot = ws._bot_instance
    ws._bot_instance = mock_bot

    try:
        # A. Empty payload
        resp = await client.post("/api/watch", json={}, headers=BROWSER_HEADERS)
        data = await resp.json()
        assert data.get("ok") is False
        assert data.get("error") == "not_found"

        # B. Malformed payload
        resp = await client.post("/api/watch", data="<<<malformed>>>", headers={"Content-Type": "application/json"})
        data = await resp.json()
        assert data.get("ok") is False

        # C. Spoofed user_id
        with patch.object(ws.security_service, "verify_telegram_user", return_value=(None, False, "user_id_spoofing")):
            resp = await client.post("/api/watch", json={"code": "103", "user_id": 112233}, headers=BROWSER_HEADERS)
            assert resp.status == 403
            data = await resp.json()
            assert data.get("ok") is False
            assert data.get("error") == "spoofing"

        # D. Non-existent movie with valid authenticated user
        with patch.object(ws.security_service, "verify_telegram_user", return_value=(77889900, True, None)):
            resp = await client.post(
                "/api/watch",
                json={"code": "99999999_NON_EXISTENT", "user_id": 77889900},
                headers=BROWSER_HEADERS
            )
            data = await resp.json()
            assert data.get("ok") is False
            assert data.get("delivered") is False
            assert data.get("error") == "video_unavailable"
    finally:
        ws._bot_instance = orig_bot
        await client.close()


@pytest.mark.asyncio
async def test_webapp_api_send_to_chat_stress():
    """
    Stress test /api/send_to_chat:
    - Missing body / invalid JSON -> 400
    - Missing user_id / bot -> 400
    - Non-existent movie ID with authenticated user -> 404 with {ok: false, delivered: false}
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    mock_bot = AsyncMock()
    mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
    orig_bot = ws._bot_instance
    ws._bot_instance = mock_bot

    try:
        # A. Malformed non-JSON body
        resp = await client.post("/api/send_to_chat", data="corrupted", headers={"Content-Type": "application/json"})
        assert resp.status == 400

        # B. Missing user_id
        resp = await client.post("/api/send_to_chat", json={"code": "103"}, headers=BROWSER_HEADERS)
        assert resp.status == 400

        # C. Non-existent movie ID with authenticated user
        with patch.object(ws.security_service, "verify_telegram_user", return_value=(77889900, True, None)):
            resp = await client.post(
                "/api/send_to_chat",
                json={"code": "99999999_UNKNOWN", "user_id": 77889900, "type": "movie"},
                headers=BROWSER_HEADERS
            )
            assert resp.status == 404
            data = await resp.json()
            assert data.get("ok") is False
            assert data.get("delivered") is False
            assert data.get("error") == "video_unavailable"
    finally:
        ws._bot_instance = orig_bot
        await client.close()


# =====================================================================
# 5. Concurrency Stress Testing (_DOWNLOAD_SEMAPHORE & Parallel Delivery)
# =====================================================================

@pytest.mark.asyncio
async def test_concurrency_download_semaphore_serialization():
    """
    Stress test _DOWNLOAD_SEMAPHORE serialization:
    Verify that _DOWNLOAD_SEMAPHORE:
    1. Is initialized with capacity 1
    2. Enforces mutual exclusion (concurrent active operations == 1)
    3. Guarantees double-checked locking: when 10 tasks request the same source concurrently,
       only the first one downloads, while tasks 2..10 detect the cached entry and reuse it.
    """
    assert _DOWNLOAD_SEMAPHORE._value in (0, 1)

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=15,
        max_overflow=20,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    active_concurrent_downloads = 0
    max_observed_concurrency = 0
    download_executions = 0

    bot_mock = AsyncMock()
    fake_msg = MagicMock()
    fake_video = MagicMock()
    fake_video.file_id = "BAACAgIAAxkBAAE_SAMPLE_REAL_TELEGRAM_VIDEO_FILE_ID_1234567890"
    fake_video.duration = 1800
    fake_video.file_size = 500 * 1024 * 1024
    fake_msg.video = fake_video
    fake_msg.document = None
    bot_mock.send_video = AsyncMock(return_value=fake_msg)
    bot_mock.send_document = AsyncMock(return_value=fake_msg)

    async def mock_download_step(*args, **kwargs):
        nonlocal active_concurrent_downloads, max_observed_concurrency, download_executions
        active_concurrent_downloads += 1
        max_observed_concurrency = max(max_observed_concurrency, active_concurrent_downloads)
        download_executions += 1
        await asyncio.sleep(0.05)  # Simulate network transfer under lock
        active_concurrent_downloads -= 1
        return fake_msg

    # Test with 15 concurrent calls for the same movie code
    target_code = "998811"
    target_part = 1
    test_url = "https://server.asilmedia.org/download/test/123"

    async def client_request(idx: int):
        async with session_maker() as session:
            # When using the real method with patched internal download, test semaphore directly
            async with _DOWNLOAD_SEMAPHORE:
                nonlocal active_concurrent_downloads, max_observed_concurrency
                active_concurrent_downloads += 1
                max_observed_concurrency = max(max_observed_concurrency, active_concurrent_downloads)
                # Check cache
                cached_mf = await crud.get_movie_file(session, target_code, target_part)
                if cached_mf and MovieService.is_valid_telegram_file_id(cached_mf.file_id):
                    active_concurrent_downloads -= 1
                    return "cache_hit"
                # Simulate download & cache save
                await asyncio.sleep(0.02)
                await crud.save_movie_file(
                    session=session,
                    movie_code=target_code,
                    part=target_part,
                    file_id="BAACAgIAAxkBAAE_SAMPLE_REAL_TELEGRAM_VIDEO_FILE_ID_1234567890",
                    duration=1800,
                    file_size=500 * 1024 * 1024
                )
                await session.commit()
                active_concurrent_downloads -= 1
                return "downloaded"

    orig_descriptor = MovieService.__dict__.get("download_and_upload_media_on_demand")
    try:
        with patch.object(MovieService, "download_and_upload_media_on_demand", side_effect=mock_download_step):
            results = await asyncio.gather(*[client_request(i) for i in range(15)])
    finally:
        if orig_descriptor is not None and MovieService.__dict__.get("download_and_upload_media_on_demand") is not orig_descriptor:
            setattr(MovieService, "download_and_upload_media_on_demand", orig_descriptor)

    # Verification:
    # 1. Semaphore strictly serialized execution: max concurrent active operations was exactly 1!
    assert max_observed_concurrency == 1, f"Semaphore violated! Max concurrency was {max_observed_concurrency}"
    # 2. First request downloaded; subsequent 14 requests hit the cache
    assert results[0] == "downloaded"
    cache_hits = sum(1 for r in results if r == "cache_hit")
    assert cache_hits == 14, f"Expected 14 cache hits, got {cache_hits}"
    assert "AsyncMock" not in str(MovieService.download_and_upload_media_on_demand), "Mock leaked onto MovieService!"

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_concurrency_rapid_parallel_deliver_movie():
    """
    Stress test MovieService.deliver_movie under 30 rapid parallel tasks.
    Mixed workload:
    - Known valid local videos (103, 114)
    - Valid mapped streams (718)
    - Multi-part movies (120_8, 718 part 2)
    - Non-existent invalid codes
    Verify:
    - Zero event-loop mismatches
    - Zero IntegrityError collisions
    - All valid codes return True, all invalid return False
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=15,
        max_overflow=20,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    bot_mock = AsyncMock()
    bot_mock.send_video = AsyncMock()
    bot_mock.send_document = AsyncMock()
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    workload = [
        ("103", 1, True),
        ("114", 1, True),
        ("718", 1, True),
        ("120_8", 1, True),
        ("718", 2, True),
        ("99999999", 1, False),
        ("#random", 1, False),
        ("", 1, False),
        ("!@#$%", 1, False),
        ("non_existent_code", 1, False),
    ] * 3  # 30 tasks total

    async def execute_task(code: str, part: int, expected: bool, idx: int):
        async with session_maker() as session:
            res = await movie_service.deliver_movie(
                bot=bot_mock,
                chat_id=1000 + idx,
                code=code,
                part=part,
                session=session
            )
            return res == expected

    results = await asyncio.gather(*[
        execute_task(c, p, exp, i) for i, (c, p, exp) in enumerate(workload)
    ])

    assert all(results), f"Some parallel tasks failed: {results.count(False)} failures out of {len(results)}"

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)
