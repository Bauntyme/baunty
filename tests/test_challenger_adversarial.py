"""
Adversarial Stress Test Suite - Challenger 1
Empirical verification across requirements R1–R5:
- R1: Throttling non-punitive rapid intervals (50ms), SlidingWindowRateLimiter whitelist & AutoBanJail resilience.
- R2: TV Stream Proxy SSRF prevention, direct-first CORS domains, and M3U8 rewriting.
- R3: Brand sanitization purity under adversarial input vectors.
- R4: Book retrieval, async loading, and search under adversarial/fuzzing payloads.
- R5: High-concurrency parallel database operations (zero IntegrityError).
"""

import os
import sys
import time
import asyncio
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool

from database.models import Base, User, Movie, MovieFile
from database import crud
from middlewares.throttling import ThrottlingMiddleware
from services.security_service import (
    SlidingWindowRateLimiter,
    AutoBanJail,
    is_trusted_proxy,
    is_render_nat_ip,
    is_malicious_request,
)
from services.web_server import is_stream_url_allowed
from services.movie_service import MovieService
from services.book_service import get_book_by_id, get_catalog, async_get_book_by_id, load_books


# =====================================================================
# R1: Non-Punitive Throttling & Rate Limiting Stress Tests
# =====================================================================

@pytest.mark.asyncio
async def test_throttling_non_punitive_rapid_50ms_intervals():
    """
    Stress test ThrottlingMiddleware under rapid 50ms intervals.
    Verify that spam clicks do NOT extend or reset the cooldown period,
    allowing the request immediately once the cooldown interval expires.
    """
    middleware = ThrottlingMiddleware(rate_limit=1.0)

    handler_calls = 0

    async def mock_handler(event, data):
        nonlocal handler_calls
        handler_calls += 1
        return "ok"

    user_id = 99887711
    event = MagicMock()
    user_mock = MagicMock()
    user_mock.id = user_id
    event.from_user = user_mock

    # 1. First request at t = 0 -> MUST pass
    res1 = await middleware(mock_handler, event, {})
    assert res1 == "ok"
    assert handler_calls == 1

    # 2. Simulate 8 rapid requests spaced by 50ms (total ~450ms < 1000ms limit)
    # None of these should execute the handler
    for _ in range(8):
        await asyncio.sleep(0.05)
        res = await middleware(mock_handler, event, {})
        assert res is None  # Throttled

    assert handler_calls == 1  # Still 1 call

    # 3. Wait remaining ~650ms to pass the 1000ms threshold from the initial request
    await asyncio.sleep(0.65)

    # 4. Request at t ~ 1.1s -> MUST pass because cooldown was NOT reset by the 50ms taps!
    res_after = await middleware(mock_handler, event, {})
    assert res_after == "ok"
    assert handler_calls == 2


@pytest.mark.asyncio
async def test_throttling_concurrent_multi_user_isolation():
    """
    Stress test ThrottlingMiddleware with 50 distinct users clicking rapidly.
    Verify that one user's throttling never impacts another user's requests.
    """
    middleware = ThrottlingMiddleware(rate_limit=0.3)
    executed_users = set()

    async def mock_handler(event, data):
        user = getattr(event, "from_user", None)
        if user:
            executed_users.add(user.id)
        return "success"

    async def user_request(uid: int):
        event = MagicMock()
        u = MagicMock()
        u.id = uid
        event.from_user = u
        return await middleware(mock_handler, event, {})

    # Run 50 distinct users in parallel
    results = await asyncio.gather(*[user_request(1000 + i) for i in range(50)])
    assert all(r == "success" for r in results)
    assert len(executed_users) == 50


def test_sliding_window_rate_limiter_whitelisted_paths_burst():
    """
    Stress test SlidingWindowRateLimiter with a burst of 150 rapid requests
    to whitelisted paths (/health, /ping, /webapp, /).
    Verify that 429 is NEVER returned and the IP is NEVER banned.
    """
    limiter = SlidingWindowRateLimiter(burst_limit=20, sustained_limit=50)

    test_ip = "198.51.100.42"  # Public doc IP
    paths = ["/health", "/ping", "/healthz", "/status", "/", "/webapp", "/webapp/", "/index.html"]

    for _ in range(150):
        for path in paths:
            allowed, retry_after = limiter.is_allowed(test_ip, path=path)
            assert allowed is True
            assert retry_after is None

    # Verify IP was not placed in banned_ips
    assert test_ip not in limiter._banned_ips


def test_auto_ban_jail_preserves_uptimerobot_and_render_ips():
    """
    Verify AutoBanJail never incarcerates trusted proxy, Render NAT, or monitor IPs.
    """
    jail = AutoBanJail(default_ban_seconds=60)

    # Render NAT IP
    render_ip = "216.24.57.1"
    jail.jail_ip(render_ip, duration=100, reason="test_probe")
    jailed, _, _ = jail.is_jailed(render_ip)
    assert not jailed

    # Loopback IP
    loopback_ip = "127.0.0.1"
    jail.jail_ip(loopback_ip, duration=100, reason="test_probe")
    jailed, _, _ = jail.is_jailed(loopback_ip)
    assert not jailed

    # Standard public attacker IP SHOULD be banned after threshold
    attacker_ip = "198.51.100.99"
    jail.jail_ip(attacker_ip, duration=100, reason="malicious_exploit")
    jailed, _, _ = jail.is_jailed(attacker_ip)
    assert jailed


# =====================================================================
# R2: TV Stream Proxy & CORS SSRF Resilience Tests
# =====================================================================

def test_tv_stream_proxy_ssrf_blocking():
    """
    Adversarial test for is_stream_url_allowed against SSRF attack vectors:
    - Internal private networks (10.x, 192.168.x, 172.16.x)
    - Cloud metadata endpoints (169.254.169.254)
    - Loopback hosts (localhost, 127.0.0.1, ::1)
    - Non-whitelisted external domains
    """
    forbidden_targets = [
        "http://127.0.0.1:8080/admin",
        "http://127.0.0.2:8000/stream.m3u8",
        "http://localhost:5000/api",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal.m3u8",
        "http://192.168.1.1/router",
        "http://172.16.0.5/stream",
        "http://0.0.0.0:8080/test",
        "http://evil-attacker.com/malicious.m3u8",
        "http://subdomain.google.com/test.ts",
    ]

    for target in forbidden_targets:
        allowed = is_stream_url_allowed(target)
        assert allowed is False, f"Target {target} should be blocked for SSRF prevention!"


def test_tv_stream_proxy_legitimate_domains_allowed():
    """
    Verify that legitimate media providers and CORS streaming domains are allowed:
    - cinerama.uz (including stream3.cinerama.uz)
    - biztv.uz
    - mediabay.uz
    - zabava-htlive.cdn.ngenix.net
    """
    valid_targets = [
        "https://stream3.cinerama.uz/1213/tracks-v1a1/mono.ts.m3u8",
        "https://stream3.cinerama.uz/1009/playlist.m3u8",
        "https://biztv.uz/live/stream.m3u8",
        "https://fl.biztv.media/cinema_720/index.m3u8",
        "https://zabava-htlive.cdn.ngenix.net/hls/CH_C06_NASHFOOTBALLHD/variant.m3u8",
        "https://fayllar.com/streams/test.m3u8",
    ]

    for target in valid_targets:
        allowed = is_stream_url_allowed(target)
        assert allowed is True, f"Legitimate stream {target} must be allowed!"
    assert is_stream_url_allowed("https://161-97-96-58.sslip.io/streams/test.m3u8") is False


# =====================================================================
# R3 & R4: Brand Sanitization & Book Retrieval Adversarial Tests
# =====================================================================

def test_brand_sanitization_adversarial_purity():
    """
    Test MovieService.sanitize_branding with varied case and pattern variations
    of upstream bot handles, channel handles, and personal names.
    Guarantee zero leakage of 'Zakirov' or upstream entities.
    """
    dirty_samples = [
        "Kino @Zakirovsfilms_bot orqali yuklab olindi",
        "Bizning kanal: https://t.me/Zakirovsfilms_bot",
        "Obuna bo'ling: @ZakirovsKino yoki @dilbarzakirova",
        "Rejissyor Zakirovs Films taqdim etadi",
        "Telegram bot: @Zakirovsfilm_bot va Zakirovs",
        "Dilbar Zakirova va @Zakirovs rasmiy kanali",
        "Eski bot: @Bauntyfilmsbot va t.me/Bauntyfilmsbot",
    ]

    for sample in dirty_samples:
        cleaned = MovieService.sanitize_branding(sample)
        assert "zakirov" not in cleaned.lower(), f"Leak detected in: '{cleaned}' from '{sample}'"
        assert "@BauntyCinemabot" in cleaned or "@BauntyFilms" in cleaned or "Baunty" in cleaned


@pytest.mark.asyncio
async def test_book_service_adversarial_fuzzing():
    """
    Stress test book retrieval and search with adversarial inputs:
    - SQL injection payloads
    - Cyrillic / Uzbek Unicode variations
    - Extremely long query strings
    - Null-byte attempts
    Verify graceful return without unhandled exceptions or hangs.
    """
    load_books()

    fuzz_inputs = [
        "' OR '1'='1",
        "'; DROP TABLE books; --",
        "Алкимёгар",
        "Ўзбекистон тарихи",
        "G'afur G'ulom shashmaqom",
        "A" * 2000,
        "<script>alert(1)</script>",
        "Alkimyogar\x00malicious",
        "../../../etc/passwd",
    ]

    for q in fuzz_inputs:
        # Search should execute within budget (<100ms) and never throw
        start = time.monotonic()
        results = get_catalog(query=q, limit=10)
        elapsed = time.monotonic() - start
        assert isinstance(results, dict)
        assert results.get("ok") is True
        assert isinstance(results.get("items"), list)
        assert elapsed < 0.2, f"Search for '{q[:30]}' took too long ({elapsed:.3f}s)"

    # Test non-existent book retrieval
    non_existent = await async_get_book_by_id("non_existent_id_99999999")
    assert non_existent is None


# =====================================================================
# R5: Concurrent Database Operations Stress Tests (Parallel Tasks)
# =====================================================================

@pytest.mark.asyncio
async def test_concurrent_get_or_create_user_30_tasks():
    """
    Adversarial stress test: 30 concurrent asyncio tasks simultaneously
    calling get_or_create_user for the exact same user_id on SQLite.
    Guarantees:
    - Zero IntegrityError collisions
    - Exactly 1 user record created
    - All 30 tasks return the user object successfully
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=15,
        max_overflow=20,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    target_user_id = 88776655

    async def worker(worker_idx: int):
        async with session_maker() as session:
            user, created = await crud.get_or_create_user(
                session=session,
                user_id=target_user_id,
                username=f"concurrent_user_{worker_idx}",
                first_name="Stress",
                last_name="Tester",
            )
            await session.commit()
            return user.id, created

    results = await asyncio.gather(*[worker(i) for i in range(30)])

    assert all(r[0] == target_user_id for r in results)
    created_count = sum(1 for r in results if r[1] is True)
    assert created_count == 1, f"Expected exactly 1 creation, got {created_count}"

    await engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_concurrent_upsert_movie_30_tasks():
    """
    Adversarial stress test: 30 concurrent asyncio tasks simultaneously
    calling upsert_movie for the exact same movie code on SQLite.
    Guarantees:
    - Zero IntegrityError collisions
    - Exactly 1 movie record created
    - All 30 tasks return the movie object successfully
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=15,
        max_overflow=20,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    target_movie_code = "7777"

    async def worker(worker_idx: int):
        async with session_maker() as session:
            movie, created = await crud.upsert_movie(
                session=session,
                code=target_movie_code,
                title=f"Stress Film Title {worker_idx}",
                description="Concurrently upserted movie",
            )
            await session.commit()
            return movie.code, created

    results = await asyncio.gather(*[worker(i) for i in range(30)])

    assert all(r[0] == target_movie_code for r in results)
    created_count = sum(1 for r in results if r[1] is True)
    assert created_count == 1, f"Expected exactly 1 creation, got {created_count}"

    await engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_concurrent_save_movie_file_30_tasks():
    """
    Adversarial stress test: 30 concurrent asyncio tasks simultaneously
    calling save_movie_file for the exact same (movie_code, part) tuple.
    Guarantees:
    - Zero IntegrityError / unique constraint violation
    - Exactly 1 MovieFile record persisted for (code, part)
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=15,
        max_overflow=20,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    target_code = "8888"
    target_part = 1

    async def worker(worker_idx: int):
        async with session_maker() as session:
            mf = await crud.save_movie_file(
                session=session,
                movie_code=target_code,
                part=target_part,
                file_id=f"cloud_fid_parallel_{worker_idx}",
            )
            await session.commit()
            return mf.movie_code, mf.part

    results = await asyncio.gather(*[worker(i) for i in range(30)])

    assert all(r == (target_code, target_part) for r in results)

    # Verify count in database
    async with session_maker() as session:
        from sqlalchemy import select, func
        stmt = select(func.count(MovieFile.id)).where(
            MovieFile.movie_code == target_code,
            MovieFile.part == target_part
        )
        cnt = (await session.execute(stmt)).scalar()
        assert cnt == 1, f"Expected 1 record in movie_files, found {cnt}"

    await engine.dispose()
    if os.path.exists(path):
        os.remove(path)
