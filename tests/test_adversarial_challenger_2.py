"""
Adversarial Stress Test Suite — Challenger 2
============================================
Empirically stress-testing requirements R1–R5 against BauntyCinemBot:
1. R1: Rate-limiter whitelists, WAF auto-ban, and non-punitive throttling under rapid 50ms intervals.
2. R2: TV stream proxy, direct-first CORS, auto-failover on report, and SSRF defense.
3. R3 & R4: Brand sanitization purity, book async retrieval, and adversarial payload resilience.
4. R5: Concurrent database operations under parallel tasks (zero IntegrityError collisions).
"""
import os
import re
import time
import asyncio
import tempfile
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from aiohttp.test_utils import TestServer, TestClient
from aiohttp import web
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool

from database.models import Base
from database import crud
from services.security_service import (
    security_service,
    AutoBanJail,
    SlidingWindowRateLimiter,
    is_render_nat_ip,
    is_public_ip,
    is_trusted_proxy,
)
from middlewares.throttling import ThrottlingMiddleware
from services.web_server import (
    create_web_app,
    sanitize_catalog_text,
    sanitize_book_text,
    is_stream_url_allowed,
    _TV_STREAM_FAILURES,
    _TV_ALL_CACHE,
    CHANNELS_LIST,
)
from services.book_service import async_get_book_by_id, sanitize_book_text as b_sanitize
from services.movie_service import movie_service


@pytest.fixture(autouse=True)
def clean_security_state():
    """Reset security state before and after each test."""
    security_service.reset()
    yield
    security_service.reset()


# =====================================================================
# R1: Rate Limiter Whitelists, WAF Auto-Ban, and Non-Punitive Throttling
# =====================================================================

@pytest.mark.asyncio
async def test_r1_adv01_burst_monitoring_whitelisted_paths():
    """
    Stress test whitelisted endpoints with 100 rapid requests (sub-10ms intervals)
    using monitoring User-Agents (UptimeRobot, Render internal, empty UA).
    Must return 200/OK and NEVER trigger 429 or AutoBanJail.
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        paths = ["/health", "/ping", "/", "/webapp", "/webapp/", "/index.html"]
        user_agents = [
            "Mozilla/5.0 (compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)",
            "Render/1.0",
            "BetterUptime/1.0",
            "",  # empty UA
        ]

        for p in paths:
            for ua in user_agents:
                headers = {"User-Agent": ua}
                # Burst of 10 requests per path/UA combination
                for _ in range(10):
                    resp = await client.get(p, headers=headers)
                    assert resp.status in (200, 304), f"Path {p} with UA '{ua}' returned status {resp.status}"

        # Confirm client IP is not jailed
        is_jailed, _, _ = security_service.jail.is_jailed("127.0.0.1")
        assert not is_jailed, "Local/monitoring IP was erroneously jailed"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_r1_adv02_non_punitive_throttling_50ms_rapid_clicks():
    """
    Adversarial stress test of ThrottlingMiddleware:
    - User clicks 20 times at 50ms intervals (1000ms total elapsed).
    - Event 1 succeeds (at t=0).
    - Events 2–20 are throttled (rate_limit=1.0s).
    - Crucially: at t=1.05s, event 21 MUST SUCCEED because the cooldown was NOT reset
      by the intermediate throttled clicks (non-punitive throttling invariant).
    """
    throttle = ThrottlingMiddleware(rate_limit=1.0)
    handler_mock = AsyncMock(return_value="OK")

    user_id = 999111001

    class FakeUser:
        def __init__(self, uid):
            self.id = uid

    class FakeEvent:
        def __init__(self, uid):
            self.from_user = FakeUser(uid)

    event = FakeEvent(user_id)
    data = {}

    # Initial hit at t=0
    res1 = await throttle(handler_mock, event, data)
    assert res1 == "OK", "First request must pass"
    assert handler_mock.call_count == 1

    # Simulate 20 rapid clicks at 50ms intervals
    # We advance monotonically simulated timestamps
    start_time = throttle.user_timestamps[user_id]

    for click_idx in range(1, 20):
        # Even if clicks arrive every 50ms, timestamp must NOT reset
        # Let's temporarily manipulate time.monotonic or verify that rejected clicks don't change timestamp
        prev_ts = throttle.user_timestamps[user_id]
        res = await throttle(handler_mock, event, data)
        assert res is None, f"Click {click_idx} during cooldown should be dropped"
        # The stored timestamp must remain unchanged!
        assert throttle.user_timestamps[user_id] == prev_ts, "Cooldown was punitively reset!"

    assert handler_mock.call_count == 1

    # Now simulate time passing beyond the 1.0s rate_limit (e.g. 1.05s after event 1)
    throttle.user_timestamps[user_id] = time.monotonic() - 1.05

    # Event 21 must now succeed immediately despite the 19 rejected clicks!
    res21 = await throttle(handler_mock, event, data)
    assert res21 == "OK", "Event after rate_limit elapsed must succeed despite prior rapid clicks"
    assert handler_mock.call_count == 2


@pytest.mark.asyncio
async def test_r1_adv03_concurrent_multi_user_throttling_isolation():
    """
    5 distinct users spamming buttons at 50ms intervals:
    One user's throttled state must never leak or affect another user.
    """
    throttle = ThrottlingMiddleware(rate_limit=0.5)
    handler_mock = AsyncMock(return_value="OK")

    class FakeUser:
        def __init__(self, uid):
            self.id = uid

    class FakeEvent:
        def __init__(self, uid):
            self.from_user = FakeUser(uid)

    users = [10001, 10002, 10003, 10004, 10005]

    # Every user's first click passes
    for uid in users:
        ev = FakeEvent(uid)
        res = await throttle(handler_mock, ev, {})
        assert res == "OK"
    assert handler_mock.call_count == 5

    # Every user's immediate second click is throttled
    for uid in users:
        ev = FakeEvent(uid)
        res = await throttle(handler_mock, ev, {})
        assert res is None
    assert handler_mock.call_count == 5

    # Reset only user 10003
    throttle.user_timestamps[10003] = time.monotonic() - 0.6

    # User 10003 can click, while user 10001 is still throttled
    assert await throttle(handler_mock, FakeEvent(10003), {}) == "OK"
    assert await throttle(handler_mock, FakeEvent(10001), {}) is None


def test_r1_adv04_render_nat_ip_immunity():
    """
    Empirically verify that Render NAT egress IP ranges cannot be jailed in AutoBanJail.
    """
    jail = AutoBanJail(default_ban_seconds=60.0)

    render_ips = [
        "216.24.56.1",
        "216.24.59.254",
        "216.24.60.10",
        "169.150.247.50",
        "44.209.160.1",
        "44.209.175.254",
        "3.125.105.150",
    ]

    for ip in render_ips:
        assert is_render_nat_ip(ip), f"IP {ip} should be recognized as Render NAT"
        # Attempt to jail
        jail.jail_ip(ip, reason="scanner_test")
        is_j, _, _ = jail.is_jailed(ip)
        assert not is_j, f"Render NAT IP {ip} must NOT be jailed in AutoBanJail"


def test_r1_adv05_malicious_scanners_jailed_on_external_ips():
    """
    Adversarial test: Confirm that true external public attack IPs ARE jailed
    when attempting scans or exploits, while trusted/private ones are not.
    """
    jail = AutoBanJail(default_ban_seconds=60.0)

    attacker_ip = "198.51.100.55"  # RFC 5737 public test net
    assert is_public_ip(attacker_ip), "198.51.100.55 should be treated as public external IP"

    jail.jail_ip(attacker_ip, reason="sqli_attack")
    is_j, remaining, reason = jail.is_jailed(attacker_ip)
    assert is_j is True
    assert remaining > 0
    assert reason == "sqli_attack"

    # Unban test
    jail.unban_ip(attacker_ip)
    is_j_after, _, _ = jail.is_jailed(attacker_ip)
    assert is_j_after is False


# =====================================================================
# R2: TV Stream Proxy, Direct CORS, Auto-Failover & SSRF Defense
# =====================================================================

@pytest.mark.asyncio
async def test_r2_adv01_tv_stream_proxy_cors_and_methods():
    """
    Empirically verify TV proxy responds with open CORS headers
    Access-Control-Allow-Origin: * on OPTIONS, GET, and HEAD.
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Preflight OPTIONS
        resp_opt = await client.options(
            "/api/tv/stream?url=https://stream3.cinerama.uz/1213/mono.m3u8",
            headers={"Origin": "https://web.telegram.org"}
        )
        assert resp_opt.status in (200, 204)
        assert resp_opt.headers.get("Access-Control-Allow-Origin") == "*"

        # Missing URL
        resp_empty = await client.get("/api/tv/stream")
        assert resp_empty.status == 400
        assert resp_empty.headers.get("Access-Control-Allow-Origin") == "*"
    finally:
        await client.close()


def test_r2_adv02_ssrf_protection_blocked_destinations():
    """
    Adversarial test: verify that loopback, private IPs, AWS/GCP metadata endpoints,
    and non-http schemes are strictly blocked by is_stream_url_allowed.
    """
    malicious_urls = [
        "http://127.0.0.1:8080/admin/flow",
        "http://localhost:8080/health",
        "http://[::1]:8080/api/tv",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://172.16.0.5/secret",
        "file:///etc/passwd",
        "ftp://attacker.com/evil.m3u8",
        "gopher://attacker.com/",
        "javascript:alert(1)",
        "http://attacker.com/malicious.sh",
    ]

    for url in malicious_urls:
        assert not is_stream_url_allowed(url), f"URL '{url}' must be blocked by SSRF defense"


def test_r2_adv03_allowed_legitimate_media_streams():
    """
    Verify that legitimate configured streaming domains and CDNs are allowed.
    """
    allowed_urls = [
        "https://stream3.cinerama.uz/1213/tracks-v1a1/mono.ts.m3u8",
        "https://fl.biztv.media/cinema_720/index.m3u8",
        "https://cdn.mediabay.uz/live/milliy.m3u8",
        "https://live.famelack.com/hls/stream.m3u8",
        "https://asilmedia.org/stream/kino123.m3u8",
        "https://161-97-96-58.sslip.io/hls/live.m3u8",
    ]

    for url in allowed_urls:
        assert is_stream_url_allowed(url), f"Legitimate stream URL '{url}' should be allowed"


@pytest.mark.asyncio
async def test_r2_adv04_tv_auto_failover_on_repeated_bad_reports():
    """
    Adversarial stress test on handle_tv_report:
    Reporting 3 consecutive stream failures for a channel with backups
    MUST automatically promote the next backup URL in CHANNELS_LIST and invalidate TV cache.
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Find a channel with multiple stream backups (e.g. channel ID 1 or 2)
        target_ch = next((ch for ch in CHANNELS_LIST if len(ch.get("u", [])) > 1), None)
        assert target_ch is not None, "At least one channel must have multiple stream backups"

        ch_id = target_ch["id"]
        initial_stream = target_ch["stream"]
        backups = target_ch["u"]

        # Reset failure state for target channel
        _TV_STREAM_FAILURES.pop(ch_id, None)

        # 1st failure report
        r1 = await client.post("/api/tv/report", json={"id": ch_id, "bad": True})
        assert r1.status == 200
        assert _TV_STREAM_FAILURES[ch_id]["fails"] == 1
        assert target_ch["stream"] == initial_stream

        # 2nd failure report
        r2 = await client.post("/api/tv/report", json={"id": ch_id, "bad": True})
        assert r2.status == 200
        assert _TV_STREAM_FAILURES[ch_id]["fails"] == 2
        assert target_ch["stream"] == initial_stream

        # 3rd failure report -> triggers auto-failover!
        r3 = await client.post("/api/tv/report", json={"id": ch_id, "bad": True})
        assert r3.status == 200
        assert _TV_STREAM_FAILURES[ch_id]["fails"] >= 3

        # Stream should now be changed to backup #1
        expected_backup_url = backups[1][1]
        assert target_ch["stream"] == expected_backup_url, "Stream was not promoted to backup URL"
        assert _TV_ALL_CACHE["ts"] == 0, "TV catalog cache was not invalidated after failover"

        # Now send a recovery report (ok: True)
        r_ok = await client.post("/api/tv/report", json={"id": ch_id, "ok": True})
        assert r_ok.status == 200
        assert _TV_STREAM_FAILURES[ch_id]["fails"] == 2, "Failure counter should decrement on ok"

        # Restore original stream for clean test hygiene
        target_ch["stream"] = initial_stream
        _TV_STREAM_FAILURES.pop(ch_id, None)
    finally:
        await client.close()


# =====================================================================
# R3 & R4: Brand Sanitization, Book Retrieval & Adversarial Inputs
# =====================================================================

def test_r3_r4_adv01_strict_brand_sanitization_adversarial_matrix():
    """
    Adversarial test of sanitize_catalog_text:
    Stress-test with mixed casing, URLs, bot handles, and multiple occurrences.
    Zero remnants of competitor branding must remain.
    """
    test_cases = [
        (
            "Kino kodi: 123. Rasmiy bot: @Zakirovsfilms_bot va kanal @ZakirovsKino",
            "@BauntyCinemabot",
            "@BauntyFilms",
        ),
        (
            "Havola: https://t.me/zakirovsfilms_bot yoki t.me/dilbarzakirova",
            "https://t.me/BauntyFilms",
            "t.me/BauntyFilms",
        ),
        (
            "Yaratuvchi: Dilbar Zakirova, Zakirovs Films taqdim etadi.",
            "Baunty",
            "Baunty Films",
        ),
        (
            "Eski bot: @Bauntyfilmsbot yoki https://t.me/Bauntyfilmsbot",
            "@BauntyCinemabot",
            "https://t.me/BauntyCinemabot",
        ),
        (
            "Takroriy: @zakirovs @ZAKIROVS_BOT @zakirov @dilbarzakirova",
            "@BauntyFilms",
            "@BauntyCinemabot",
        ),
    ]

    for raw, exp_part1, exp_part2 in test_cases:
        sanitized = sanitize_catalog_text(raw)
        assert "zakirov" not in sanitized.lower(), f"Competitor brand found in: '{sanitized}'"
        assert "dilbar" not in sanitized.lower(), f"Competitor name found in: '{sanitized}'"
        assert exp_part1 in sanitized or exp_part2 in sanitized, f"Expected '{exp_part1}' or '{exp_part2}' in '{sanitized}'"


def test_r3_r4_adv02_book_mojibake_and_encoding_sanitizer():
    """
    Adversarial test on sanitize_book_text:
    Verify removal of mojibake, corrupted UTF-8 sequences, split ligatures, and hyphens.
    """
    corrupted = "â€œOâ€™tkan kunlarâ€\u201d â€” Abdulla Qodiriy kitob- lari. \ufb01kr va \ufb02oqat."
    cleaned = sanitize_book_text(corrupted)

    assert "â" not in cleaned
    assert "kitoblari" in cleaned
    assert "fikr" in cleaned
    assert "floqat" in cleaned


@pytest.mark.asyncio
async def test_r3_r4_adv03_book_retrieval_adversarial_inputs():
    """
    Stress-test async_get_book_by_id with boundary and malicious inputs:
    - Non-numeric strings
    - SQL injection strings
    - Path traversal strings
    - Extreme integer boundaries
    Must return None gracefully without raising unhandled exceptions or crashing.
    """
    malicious_ids = [
        "-1",
        "0",
        "9999999999",
        "1' OR '1'='1",
        "../../../../etc/passwd",
        "<script>alert(1)</script>",
        "null",
        "undefined",
        "NaN",
        "b_" + "9" * 20,
        "   ",
        "\x00\x00\x00",
    ]

    for mid in malicious_ids:
        res = await async_get_book_by_id(mid)
        # For non-existent or adversarial IDs, must be None
        assert res is None, f"Adversarial ID '{mid}' should return None"


@pytest.mark.asyncio
async def test_r3_r4_adv04_movie_deep_link_franchise_mapping():
    """
    Test movie franchise deep linking codes (718, 717, 287) in MovieService.
    Must map correctly to franchise metadata with Baunty branding.
    """
    # 718: Taksi (Taxi) - 5 parts
    info_718 = movie_service.get_catalog_item("718")
    assert info_718 is not None
    assert "Taksi" in info_718.get("t", "") or "Taxi" in info_718.get("t", "")
    assert info_718.get("p") == 5
    assert "@BauntyCinemabot" in info_718.get("d", "")

    # 717: Attack on Titan - 54 parts
    info_717 = movie_service.get_catalog_item("717")
    assert info_717 is not None
    assert "Titan" in info_717.get("t", "")
    assert info_717.get("p") == 54

    # 287: Chuqur - 131 parts
    info_287 = movie_service.get_catalog_item("287")
    assert info_287 is not None
    assert "Chuqur" in info_287.get("t", "") or "Çukur" in info_287.get("t", "")
    assert info_287.get("p") == 131


# =====================================================================
# R5: High-Concurrency Database Stress (Zero IntegrityError Collisions)
# =====================================================================

@pytest.mark.asyncio
async def test_r5_adv01_50_concurrent_user_creations_same_id():
    """
    HIGH-STRESS CONCURRENCY TEST:
    50 concurrent async tasks attempting get_or_create_user for the EXACT SAME user_id.
    Must produce exactly ZERO IntegrityError crashes and exactly 1 created record.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=20,
        max_overflow=40,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    target_user_id = 888777666
    concurrency_level = 50

    async def worker(idx: int):
        async with session_maker() as s:
            user, created = await crud.get_or_create_user(
                session=s,
                user_id=target_user_id,
                username=f"parallel_user_{idx}",
                first_name=f"First_{idx}",
            )
            await s.commit()
            return user.id, created

    results = await asyncio.gather(*[worker(i) for i in range(concurrency_level)])

    # All 50 workers must have successfully returned the target user ID
    assert all(r[0] == target_user_id for r in results), "Mismatch in returned user IDs"

    # Exactly 1 worker should have created the record; 49 should report created=False
    created_count = sum(1 for r in results if r[1] is True)
    assert created_count == 1, f"Expected exactly 1 creation, got {created_count}"

    # Confirm database contains exactly 1 user
    async with session_maker() as s:
        total_users = await crud.get_total_users_count(s)
        assert total_users == 1

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_r5_adv02_50_concurrent_movie_upserts_same_code():
    """
    HIGH-STRESS CONCURRENCY TEST:
    50 concurrent async tasks attempting upsert_movie with the EXACT SAME code.
    Must produce zero IntegrityError collisions.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=20,
        max_overflow=40,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    target_code = "CONC_CODE_777"
    concurrency_level = 50

    async def worker(idx: int):
        async with session_maker() as s:
            movie, created = await crud.upsert_movie(
                session=s,
                code=target_code,
                title=f"Parallel Title {idx}",
                year=2024,
                rating=8.5,
            )
            await s.commit()
            return movie.code, created

    results = await asyncio.gather(*[worker(i) for i in range(concurrency_level)])

    assert all(r[0] == target_code for r in results)
    created_count = sum(1 for r in results if r[1] is True)
    assert created_count == 1, f"Expected exactly 1 movie creation, got {created_count}"

    async with session_maker() as s:
        movie_in_db = await crud.get_movie_by_code(s, target_code)
        assert movie_in_db is not None
        assert movie_in_db.code == target_code

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_r5_adv03_50_concurrent_save_movie_file_same_part():
    """
    HIGH-STRESS CONCURRENCY TEST:
    50 concurrent async tasks saving movie file parts for the same code and part.
    Must handle unique constraints smoothly without IntegrityError.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=20,
        max_overflow=40,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    target_code = "CONC_CODE_777"
    target_part = 1
    concurrency_level = 50

    async def worker(idx: int):
        async with session_maker() as s:
            mf = await crud.save_movie_file(
                session=s,
                movie_code=target_code,
                part=target_part,
                file_id=f"cloud_fid_{idx:03d}",
                file_size=1024 * 1024 * 500,
            )
            await s.commit()
            return mf.movie_code, mf.part

    results = await asyncio.gather(*[worker(i) for i in range(concurrency_level)])

    assert all(r == (target_code, target_part) for r in results)

    async with session_maker() as s:
        mf = await crud.get_movie_file(s, target_code, target_part)
        assert mf is not None
        assert mf.movie_code == target_code
        assert mf.part == target_part
        assert mf.file_id.startswith("cloud_fid_")

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_r5_adv04_mixed_parallel_concurrency_stress():
    """
    MIXED WORKLOAD STRESS:
    Simultaneously execute:
    - 20 user registrations
    - 20 movie upserts
    - 20 movie file saves
    All running concurrently in parallel tasks against SQLite pool.
    Zero deadlocks, zero IntegrityErrors.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=25,
        max_overflow=50,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def user_task(i):
        async with session_maker() as s:
            u, _ = await crud.get_or_create_user(s, 20000 + (i % 5), username=f"mixed_user_{i}")
            await s.commit()
            return "user", u.id

    async def movie_task(i):
        async with session_maker() as s:
            m, _ = await crud.upsert_movie(s, f"MIXED_{i % 5}", f"Mixed Movie {i}")
            await s.commit()
            return "movie", m.code

    async def file_task(i):
        async with session_maker() as s:
            mf = await crud.save_movie_file(s, f"MIXED_{i % 5}", part=(i % 3) + 1, file_id=f"fid_{i}")
            await s.commit()
            return "file", mf.movie_code

    tasks = []
    for i in range(20):
        tasks.append(user_task(i))
        tasks.append(movie_task(i))
        tasks.append(file_task(i))

    results = await asyncio.gather(*tasks)
    assert len(results) == 60
    assert sum(1 for r in results if r[0] == "user") == 20
    assert sum(1 for r in results if r[0] == "movie") == 20
    assert sum(1 for r in results if r[0] == "file") == 20

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)
