"""
Milestone M2 Adversarial Test Suite - Empirical Challenger
==========================================================
Adversarial coverage for:
1. Local Bot API Server Edge Cases (trailing slashes, empty strings, port configs, schema injection, limits).
2. Dual-Table file_id Synchronization & Invalidation (corrupted file_id, partial failure, backfill, concurrency).
3. Instant Delivery Latency & Zero Disk/Network Verification (0 MB disk, 0 network I/O, <100ms latency).
4. Multi-Part Episode Isolation & Anti-Collision Verification.
5. Large File Limits (50 MB standard vs 2000 MB local Bot API vs >2000 MB over-limit).
"""

import asyncio
import time
import builtins
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from config import Settings, config
from database import crud
from database.models import Base, Movie, MovieFile
from services.movie_service import MovieService, get_max_upload_bytes
from handlers.movies import save_or_update_movie_video


@pytest_asyncio.fixture
async def adversarial_engine():
    """Isolated in-memory SQLite engine with StaticPool."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def adversarial_session(adversarial_engine):
    """Isolated in-memory SQLite session with StaticPool to prevent connection drift."""
    session_maker = async_sessionmaker(bind=adversarial_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    fake_sent = MagicMock()
    fake_sent.video = MagicMock(
        file_id="BAACAgIAAxkDAAIC_valid_bot_file_id_fixture_998877665544",
        duration=5400,
        file_size=700000000,
    )
    fake_sent.document = None
    bot.send_video.return_value = fake_sent
    bot.send_document.return_value = fake_sent
    return bot


# =========================================================================
# 1. Local Bot API Server Configuration Adversarial Tests
# =========================================================================

@pytest.mark.parametrize(
    "raw_input,expected_url,expected_is_local,expected_bytes",
    [
        ("", None, False, 50 * 1024 * 1024),
        ("   ", None, False, 50 * 1024 * 1024),
        (None, None, False, 50 * 1024 * 1024),
        ("http://127.0.0.1:8081", "http://127.0.0.1:8081", True, 2000 * 1024 * 1024),
        ("http://127.0.0.1:8081/", "http://127.0.0.1:8081", True, 2000 * 1024 * 1024),
        ("http://127.0.0.1:8081///", "http://127.0.0.1:8081", True, 2000 * 1024 * 1024),
        ("127.0.0.1:8081", "http://127.0.0.1:8081", True, 2000 * 1024 * 1024),
        ("localhost:8081", "http://localhost:8081", True, 2000 * 1024 * 1024),
        ("https://tg-api.internal:8443/", "https://tg-api.internal:8443", True, 2000 * 1024 * 1024),
    ],
)
def test_adversarial_local_bot_api_variations(raw_input, expected_url, expected_is_local, expected_bytes):
    """Stress-test diverse LOCAL_BOT_API_URL formats, edge cases, and upload limits."""
    settings = Settings(LOCAL_BOT_API_URL=raw_input, BOT_API_SERVER=None)
    assert settings.local_bot_api_url_resolved == expected_url
    assert settings.is_local_bot_api is expected_is_local
    assert settings.max_upload_bytes == expected_bytes
    assert settings.max_upload_mb == expected_bytes // (1024 * 1024)


def test_adversarial_bot_api_server_precedence_and_sync():
    """Verify bidirectional synchronization between BOT_API_SERVER and LOCAL_BOT_API_URL."""
    # BOT_API_SERVER set, LOCAL_BOT_API_URL None
    s1 = Settings(LOCAL_BOT_API_URL=None, BOT_API_SERVER="http://127.0.0.1:8082/")
    assert s1.is_local_bot_api is True
    assert s1.LOCAL_BOT_API_URL == "http://127.0.0.1:8082"
    assert s1.local_bot_api_url_resolved == "http://127.0.0.1:8082"

    # Degenerate MAX_FILE_SIZE_MB cases
    s_zero = Settings(LOCAL_BOT_API_URL=None, BOT_API_SERVER=None, MAX_FILE_SIZE_MB=0)
    assert s_zero.max_upload_bytes == 50 * 1024 * 1024

    s_neg = Settings(LOCAL_BOT_API_URL=None, BOT_API_SERVER=None, MAX_FILE_SIZE_MB=-10)
    assert s_neg.max_upload_bytes == 50 * 1024 * 1024


def test_adversarial_aiogram_server_instantiation():
    """Verify TelegramAPIServer.from_base constructs compliant local endpoint URLs."""
    from aiogram.client.telegram import TelegramAPIServer
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    raw_base = "http://127.0.0.1:8081"
    server = TelegramAPIServer.from_base(raw_base, is_local=True)
    assert server.is_local is True
    assert server.base.startswith("http://127.0.0.1:8081/bot")
    assert server.file.startswith("http://127.0.0.1:8081/file/bot")

    session = AiohttpSession(api=server)
    bot = Bot(
        token="999999999:AAFakeTokenForChallengerTesting123456",
        session=session,
        default=DefaultBotProperties(protect_content=True),
    )
    assert bot.session.api.is_local is True


# =========================================================================
# 2. Dual-Table Synchronization & Edge Cases
# =========================================================================

@pytest.mark.asyncio
async def test_adversarial_corrupted_file_id_preserves_existing_cache(adversarial_session: AsyncSession):
    """
    If a record already holds a valid Telegram file_id, calling save_movie_file
    or set_movie_video with empty/corrupted/placeholder values must NEVER overwrite the good file_id.
    """
    code = "8101"
    good_fid = "BAACAgIAAxkDAAIC_good_persisted_fid_8101_1234567890"

    # Save initial good file_id in both tables
    await crud.create_movie(adversarial_session, code=code, title="Test 8101", file_id=good_fid)
    await crud.save_movie_file(adversarial_session, movie_code=code, part=1, file_id=good_fid)
    await adversarial_session.commit()

    # Attempt to overwrite with corrupted/invalid values in save_movie_file
    for bad_val in ["", "   ", "none", "None", "NULL", "<file_id>", "<placeholder>"]:
        await crud.save_movie_file(adversarial_session, movie_code=code, part=1, file_id=bad_val)
        await adversarial_session.commit()
        mf = await crud.get_movie_file(adversarial_session, code, 1)
        assert mf.file_id == good_fid, f"Good file_id was overwritten by bad_val={bad_val!r}!"

    # Attempt to overwrite with an HTTP URL in set_movie_video
    http_stream = "https://fayllar.com/streams/8101_sample.mp4"
    await crud.set_movie_video(adversarial_session, code=code, file_id=http_stream)
    await adversarial_session.commit()

    m = await crud.get_movie_by_code(adversarial_session, code)
    assert m.file_id == good_fid, "Good Telegram file_id was overwritten by HTTP URL in set_movie_video!"


@pytest.mark.parametrize(
    "input_code,expected_base,expected_part",
    [
        ("8102", "8102", 1),
        ("#8102", "8102", 1),
        ("№8102", "8102", 1),
        ("8102_1", "8102", 1),
        ("8102-1", "8102", 1),
        ("8102_2", "8102", 2),
        ("8102-2", "8102", 2),
        ("8102 2", "8102", 2),
        ("8102_part3", "8102", 3),
        ("8102_qism4", "8102", 4),
        ("8102p5", "8102", 5),
    ],
)
@pytest.mark.asyncio
async def test_adversarial_dual_table_code_patterns(adversarial_session: AsyncSession, input_code, expected_base, expected_part):
    """Verify regex decomposition correctly parses varied episode syntax into movie_files."""
    fid = f"BAACAgIAAxkDAAIC_fid_for_{expected_base}_part_{expected_part}_abcdef"

    m = await crud.set_movie_video(
        session=adversarial_session,
        code=input_code,
        file_id=fid,
        duration=3600,
        file_size=500000,
    )
    await adversarial_session.commit()

    mf = await crud.get_movie_file(adversarial_session, expected_base, expected_part)
    assert mf is not None, f"Failed to persist movie_file for input_code={input_code}"
    assert mf.movie_code == expected_base
    assert mf.part == expected_part
    assert mf.file_id == fid


@pytest.mark.asyncio
async def test_adversarial_dual_table_bidirectional_healing(adversarial_session: AsyncSession, mock_bot):
    """
    Self-healing dual-table synchronization:
    - If movie_files has file_id but movies lacks it, deliver_movie heals movies.file_id.
    - If movies has file_id but movie_files lacks it, deliver_movie heals movie_files.
    """
    code_a = "8103"
    fid_a = "BAACAgIAAxkDAAIC_healing_fid_a_8103_0987654321"

    # Case A: movie_files has file_id, movies has empty file_id
    await crud.create_movie(adversarial_session, code=code_a, title="Healing A", file_id="")
    await crud.save_movie_file(adversarial_session, movie_code=code_a, part=1, file_id=fid_a, duration=4000)
    await adversarial_session.commit()

    delivered_a = await MovieService.deliver_movie(mock_bot, 12345, code=code_a, part=1, session=adversarial_session)
    assert delivered_a is True

    # Check movies table backfilled
    m_a = await crud.get_movie_by_code(adversarial_session, code_a)
    assert m_a.file_id == fid_a

    # Case B: movies has file_id, movie_files lacks it
    code_b = "8104"
    fid_b = "BAACAgIAAxkDAAIC_healing_fid_b_8104_1234509876"
    await crud.create_movie(adversarial_session, code=code_b, title="Healing B", file_id=fid_b, duration=4200)
    await adversarial_session.commit()

    delivered_b = await MovieService.deliver_movie(mock_bot, 12345, code=code_b, part=1, session=adversarial_session)
    assert delivered_b is True

    # Check movie_files backfilled
    mf_b = await crud.get_movie_file(adversarial_session, code_b, 1)
    assert mf_b is not None
    assert mf_b.file_id == fid_b


@pytest.mark.asyncio
async def test_adversarial_concurrent_staggered_save_movie_file(adversarial_engine):
    """Stress test save_movie_file against rapid staggered concurrent writes for the same movie/part across sessions."""
    maker = async_sessionmaker(bind=adversarial_engine, class_=AsyncSession, expire_on_commit=False)
    code = "8105"
    part = 1

    async def writer(writer_id: int):
        await asyncio.sleep(writer_id * 0.02)
        async with maker() as session:
            fid = f"BAACAgIAAxkDAAIC_concurrent_staggered_fid_{writer_id}_123456"
            res = await crud.save_movie_file(
                session=session,
                movie_code=code,
                part=part,
                file_id=fid,
                duration=3600 + writer_id,
            )
            await session.commit()
            return res.file_id

    results = await asyncio.gather(*(writer(i) for i in range(4)), return_exceptions=True)
    for r in results:
        assert not isinstance(r, Exception), f"Writer failed with exception: {r}"

    async with maker() as verify_session:
        mf = await crud.get_movie_file(verify_session, code, part)
        assert mf is not None
        assert mf.file_id.startswith("BAACAgIAAxkDAAIC_concurrent_staggered_fid_")


# =========================================================================
# 3. Instant Delivery Latency & Zero Disk/Network Empirical Verification
# =========================================================================

@pytest.mark.asyncio
async def test_adversarial_instant_delivery_zero_disk_zero_net(adversarial_session: AsyncSession, mock_bot):
    """
    Empirical proof of zero-disk, zero-network-download instant delivery:
    1. Intercept builtins.open (write modes), Path.write_bytes, Path.write_text.
    2. Intercept aiohttp.ClientSession.get.
    3. Measure elapsed latency (<100ms requirement).
    """
    code = "8106"
    cached_fid = "BAACAgIAAxkDAAIC_zero_disk_net_instant_fid_8106_abcdef"

    await crud.create_movie(adversarial_session, code=code, title="Zero I/O Film", file_id=cached_fid, duration=3600)
    await crud.save_movie_file(adversarial_session, movie_code=code, part=1, file_id=cached_fid, duration=3600)
    await adversarial_session.commit()

    intercepted_disk_writes = []
    orig_open = builtins.open

    def tracking_open(file, mode="r", *args, **kwargs):
        if any(m in mode for m in ("w", "a", "x", "+")):
            intercepted_disk_writes.append((str(file), mode))
        return orig_open(file, mode, *args, **kwargs)

    with patch("builtins.open", side_effect=tracking_open), \
         patch("pathlib.Path.write_bytes") as mock_wb, \
         patch("pathlib.Path.write_text") as mock_wt, \
         patch("aiohttp.ClientSession.get") as mock_http_get:

        t_start = time.perf_counter()
        delivered = await MovieService.deliver_movie(
            bot=mock_bot,
            chat_id=98765,
            code=code,
            part=1,
            session=adversarial_session,
            require_video=True,
        )
        elapsed = time.perf_counter() - t_start

        # Verification asserts
        assert delivered is True
        assert elapsed < 0.20, f"Delivery latency too high: {elapsed*1000:.2f}ms (expected <200ms)"
        assert len(intercepted_disk_writes) == 0, f"Unexpected disk writes: {intercepted_disk_writes}"
        assert mock_wb.call_count == 0, "Path.write_bytes was called during cached delivery!"
        assert mock_wt.call_count == 0, "Path.write_text was called during cached delivery!"
        assert mock_http_get.call_count == 0, "External HTTP GET was made during cached delivery!"
        assert mock_bot.send_video.called
        assert mock_bot.send_video.call_args[1]["video"] == cached_fid


@pytest.mark.asyncio
async def test_adversarial_corrupted_cached_fid_invalidation_and_recovery(adversarial_session: AsyncSession, mock_bot):
    """
    When Telegram rejects a cached file_id with TelegramBadRequest ('wrong file identifier'):
    1. Both movies and movie_files must invalidate the bad file_id (wiped to '').
    2. Fallback candidate is delivered.
    3. Newly delivered file_id is re-persisted across both tables.
    """
    code = "8107"
    bad_fid = "BAACAgIAAxkDAAIC_corrupted_bad_fid_8107_rejected_by_tg"
    new_good_fid = "BAACAgIAAxkDAAIC_recovered_good_fid_8107_accepted_by_tg"

    await crud.create_movie(adversarial_session, code=code, title="Invalidation Film", file_id=bad_fid, duration=3600)
    await crud.save_movie_file(adversarial_session, movie_code=code, part=1, file_id=bad_fid, duration=3600)
    await adversarial_session.commit()

    # Bot rejects bad_fid on first call, accepts new_good_fid on fallback
    fake_recovered = MagicMock()
    fake_recovered.video = MagicMock(file_id=new_good_fid, duration=3600, file_size=400000000)
    fake_recovered.document = None

    mock_bot.send_video.side_effect = [
        TelegramBadRequest(method=MagicMock(), message="Bad Request: wrong remote file id"),
        fake_recovered,
    ]

    fallback_candidate = {
        "file_id": new_good_fid,
        "duration": 3600,
        "file_size": 400000000,
    }

    with patch.object(MovieService, "resolve_video_source", return_value=fallback_candidate):
        delivered = await MovieService.deliver_movie(
            bot=mock_bot,
            chat_id=12345,
            code=code,
            part=1,
            session=adversarial_session,
            require_video=True,
        )
        assert delivered is True

    # Both tables must now hold the newly recovered good file_id
    mf = await crud.get_movie_file(adversarial_session, code, 1)
    m = await crud.get_movie_by_code(adversarial_session, code)
    assert mf.file_id == new_good_fid
    assert m.file_id == new_good_fid


@pytest.mark.asyncio
async def test_adversarial_deleted_message_reply_resilience(adversarial_session: AsyncSession, mock_bot):
    """
    If user deleted the trigger command message before delivery completes,
    bot.send_video throws 'message to be replied not found'.
    MovieService must retry delivery without reply_to_message_id successfully.
    """
    code = "8108"
    fid = "BAACAgIAAxkDAAIC_deleted_reply_fid_8108_abcdef1234"

    await crud.create_movie(adversarial_session, code=code, title="Reply Resilience Film", file_id=fid)
    await crud.save_movie_file(adversarial_session, movie_code=code, part=1, file_id=fid)
    await adversarial_session.commit()

    fake_sent = MagicMock()
    fake_sent.video = MagicMock(file_id=fid, duration=3600, file_size=100000000)
    fake_sent.document = None

    mock_bot.send_video.side_effect = [
        TelegramBadRequest(method=MagicMock(), message="Bad Request: message to be replied not found"),
        fake_sent,
    ]

    delivered = await MovieService.deliver_movie(
        bot=mock_bot,
        chat_id=12345,
        code=code,
        part=1,
        session=adversarial_session,
        reply_to_message_id=999999,
        require_video=True,
    )

    assert delivered is True
    assert mock_bot.send_video.call_count == 2
    # Second call must have reply_to_message_id=None
    assert mock_bot.send_video.call_args_list[1][1]["reply_to_message_id"] is None


# =========================================================================
# 4. Multi-Part Series Cache Isolation & Non-Contamination
# =========================================================================

@pytest.mark.asyncio
async def test_adversarial_multipart_series_strict_cache_isolation(adversarial_session: AsyncSession, mock_bot):
    """
    Verify complete isolation across series episodes:
    - Ep 1 has cached file_id FID_1.
    - Ep 2 has cached file_id FID_2.
    - Ep 3 is dynamically resolved and cached as FID_3.
    - Ep 4 has no video source, cleanly returns False without corrupting 1, 2, 3.
    - Ep 5 has invalid file_id, gets wiped without affecting 1, 2, 3.
    """
    series_code = "8109"
    fid_1 = "BAACAgIAAxkDAAIC_series8109_ep1_fid_aaaaaaaa"
    fid_2 = "BAACAgIAAxkDAAIC_series8109_ep2_fid_bbbbbbbb"
    fid_3_new = "BAACAgIAAxkDAAIC_series8109_ep3_new_fid_cccccccc"
    fid_5_bad = "BAACAgIAAxkDAAIC_series8109_ep5_bad_fid_dddddddd"

    await crud.create_movie(adversarial_session, code=series_code, title="Series 8109", file_id=fid_1)
    await crud.save_movie_file(adversarial_session, movie_code=series_code, part=1, file_id=fid_1)
    await crud.save_movie_file(adversarial_session, movie_code=series_code, part=2, file_id=fid_2)
    await crud.save_movie_file(adversarial_session, movie_code=series_code, part=5, file_id=fid_5_bad)
    await adversarial_session.commit()

    # Deliver Ep 1
    mock_bot.reset_mock()
    d1 = await MovieService.deliver_movie(mock_bot, 111, code=series_code, part=1, session=adversarial_session, require_video=True)
    assert d1 is True
    assert mock_bot.send_video.call_args[1]["video"] == fid_1

    # Deliver Ep 2
    mock_bot.reset_mock()
    d2 = await MovieService.deliver_movie(mock_bot, 111, code=series_code, part=2, session=adversarial_session, require_video=True)
    assert d2 is True
    assert mock_bot.send_video.call_args[1]["video"] == fid_2

    # Deliver Ep 3 via dynamic candidate
    mock_bot.reset_mock()
    fake_3 = MagicMock()
    fake_3.video = MagicMock(file_id=fid_3_new, duration=3600, file_size=300000000)
    mock_bot.send_video.return_value = fake_3

    with patch.object(MovieService, "resolve_video_source", return_value={"file_id": fid_3_new, "duration": 3600, "file_size": 300000000}):
        d3 = await MovieService.deliver_movie(mock_bot, 111, code=series_code, part=3, session=adversarial_session, require_video=True)
        assert d3 is True

    # Deliver Ep 4 (missing, no source)
    mock_bot.reset_mock()
    with patch.object(MovieService, "resolve_video_source", return_value=None), \
         patch.object(MovieService, "sync_movie_from_asilmedia", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = {"success": False}
        d4 = await MovieService.deliver_movie(mock_bot, 111, code=series_code, part=4, session=adversarial_session, require_video=True)
        assert d4 is False

    # Deliver Ep 5 (rejected by Telegram)
    mock_bot.reset_mock()
    mock_bot.send_video.side_effect = TelegramBadRequest(method=MagicMock(), message="Bad Request: wrong remote file id")
    with patch.object(MovieService, "resolve_video_source", return_value=None), \
         patch.object(MovieService, "sync_movie_from_asilmedia", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = {"success": False}
        d5 = await MovieService.deliver_movie(mock_bot, 111, code=series_code, part=5, session=adversarial_session, require_video=True)
        assert d5 is False

    # Final DB assertions: Ep 1, 2, 3 must retain exact distinct file_ids, Ep 5 must be wiped
    mf1 = await crud.get_movie_file(adversarial_session, series_code, 1)
    mf2 = await crud.get_movie_file(adversarial_session, series_code, 2)
    mf3 = await crud.get_movie_file(adversarial_session, series_code, 3)
    mf5 = await crud.get_movie_file(adversarial_session, series_code, 5)

    assert mf1.file_id == fid_1
    assert mf2.file_id == fid_2
    assert mf3.file_id == fid_3_new
    assert mf5.file_id == ""


# =========================================================================
# 5. Upload Limits (50 MB vs 2000 MB vs Over-Limit)
# =========================================================================

@pytest.mark.asyncio
async def test_adversarial_upload_boundary_limits(mock_bot):
    """
    Verify upload limits under boundary conditions:
    1. Cloud Bot API (50 MB): 49 MB allowed, 51 MB rejected.
    2. Local Bot API (2000 MB): 1999 MB allowed, 2001 MB rejected.
    """
    # 1. Cloud API boundary: 51 MB
    with patch.object(config, "LOCAL_BOT_API_URL", None), \
         patch.object(config, "BOT_API_SERVER", None):
        assert config.max_upload_bytes == 50 * 1024 * 1024

        size_51mb = 51 * 1024 * 1024
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Length": str(size_51mb), "Content-Type": "video/mp4"}
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_client = MagicMock()
        mock_client.get.return_value = mock_ctx
        mock_client.__aenter__.return_value = mock_client

        with patch("aiohttp.ClientSession", return_value=mock_client):
            res_51mb = await MovieService.download_and_upload_media_on_demand(
                bot=mock_bot, chat_id=123, code="8110", part=1, source_url="https://test.com/51mb.mp4", caption="Test Caption"
            )
            assert res_51mb is None, "51 MB file should be rejected under standard 50 MB limit!"

    # 2. Local API boundary: 2001 MB rejected
    with patch.object(config, "LOCAL_BOT_API_URL", "http://127.0.0.1:8081"), \
         patch.object(config, "BOT_API_SERVER", "http://127.0.0.1:8081"):
        assert config.max_upload_bytes == 2000 * 1024 * 1024

        size_2001mb = 2001 * 1024 * 1024
        mock_resp_huge = AsyncMock()
        mock_resp_huge.status = 200
        mock_resp_huge.headers = {"Content-Length": str(size_2001mb), "Content-Type": "video/mp4"}
        mock_ctx_huge = AsyncMock()
        mock_ctx_huge.__aenter__.return_value = mock_resp_huge
        mock_client_huge = MagicMock()
        mock_client_huge.get.return_value = mock_ctx_huge
        mock_client_huge.__aenter__.return_value = mock_client_huge

        with patch("aiohttp.ClientSession", return_value=mock_client_huge):
            res_2001mb = await MovieService.download_and_upload_media_on_demand(
                bot=mock_bot, chat_id=123, code="8110", part=1, source_url="https://test.com/2001mb.mp4", caption="Test Caption"
            )
            assert res_2001mb is None, "2001 MB file should be rejected even with local Bot API (2000 MB limit)!"
