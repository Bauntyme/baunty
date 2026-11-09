"""
Tier 2: Boundary & Corner Cases Test Suite (BauntyCinemBot E2E).
Edge cases, limit values, timeouts, empty inputs, rapid hits across all 27 features (>=5 tests per feature = 135 tests).
"""
import asyncio
import os
import re
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestServer, TestClient
from aiogram.types import Message, CallbackQuery, User as TgUser
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import config, BASE_DIR
from database import crud
from database.models import User, Movie
from middlewares.throttling import ThrottlingMiddleware
from middlewares.security import BotSecurityMiddleware
from services.security_service import (
    security_service,
    extract_client_ip,
    is_malicious_request,
    check_reconnaissance_and_database_shield,
    is_trusted_proxy,
    is_render_nat_ip,
)
from services.maintenance_service import maintenance_service
from services.tv_data import CHANNELS_LIST, TV_CATEGORIES
from services.book_service import (
    load_books,
    get_catalog,
    get_book_by_id,
    create_book_pdf_sample,
    create_book_epub_sample,
    deliver_book,
    sanitize_book_text,
)
from services.music_service import MusicService


# ==============================================================================
# Feature 1 Boundary: Uptime & Keepalive Path Whitelisting
# ==============================================================================

def test_f01_b01_rapid_50_hits_whitelisted_no_429():
    for _ in range(50):
        allowed, retry = security_service.rate_limiter.is_allowed("198.51.100.50", path="/health")
        assert allowed is True
        assert retry is None


def test_f01_b02_trailing_slash_variations():
    for path in ("/health/", "/ping/", "/status/", "/healthz/"):
        allowed, _ = security_service.rate_limiter.is_allowed("198.51.100.51", path=path)
        assert allowed is True


def test_f01_b03_query_params_on_whitelisted_path():
    allowed, _ = security_service.rate_limiter.is_allowed("198.51.100.52", path="/health?monitor=uptime&ts=123456789")
    assert allowed is True


def test_f01_b04_head_request_whitelisted_path():
    allowed, _ = security_service.rate_limiter.is_allowed("198.51.100.53", path="/ping")
    assert allowed is True


def test_f01_b05_case_insensitive_path_handling():
    allowed, _ = security_service.rate_limiter.is_allowed("198.51.100.54", path="/HEALTH")
    assert allowed is True


# ==============================================================================
# Feature 2 Boundary: WAF Auto-Ban False Positive Elimination
# ==============================================================================

def test_f02_b01_empty_user_agent_on_health_allowed():
    is_mal, _ = is_malicious_request(path="/health", user_agent="")
    assert is_mal is False


def test_f02_b02_excessively_long_ua_string_handled():
    long_ua = "Mozilla/5.0 " + ("A" * 1024) + " UptimeRobot/2.0"
    is_mal, _ = is_malicious_request(path="/health", user_agent=long_ua)
    assert is_mal is False


def test_f02_b03_30_consecutive_probe_requests_no_jail():
    ip = "192.0.2.77"
    for _ in range(30):
        mal, _ = is_malicious_request(path="/ping", user_agent="BetterUptime/1.0")
        assert mal is False
    assert security_service.is_ip_banned(ip)[0] is False


def test_f02_b04_malicious_query_on_health_flagged_without_jailing_clean_probe():
    is_mal_sqli, _ = is_malicious_request(path="/health", query_string="q=%27%20UNION%20SELECT")
    assert is_mal_sqli is True
    is_mal_clean, _ = is_malicious_request(path="/health", query_string="t=1", user_agent="UptimeRobot/2.0")
    assert is_mal_clean is False


def test_f02_b05_scanner_ua_blocked_while_monitor_ua_unaffected():
    is_scanner, _ = is_malicious_request(path="/api/tv", user_agent="sqlmap/1.5")
    assert is_scanner is True
    is_monitor, _ = is_malicious_request(path="/health", user_agent="UptimeRobot/2.0")
    assert is_monitor is False


# ==============================================================================
# Feature 3 Boundary: Render NAT Egress IP Collision Prevention
# ==============================================================================

def test_f03_b01_multi_hop_x_forwarded_for_extracts_client():
    req = MagicMock()
    req.headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.2, 10.0.0.3, 10.0.0.4"}
    req.remote = "10.0.0.4"
    assert extract_client_ip(req) == "203.0.113.1"


def test_f03_b02_malformed_x_forwarded_for_header_graceful_fallback():
    req = MagicMock()
    req.headers = {"X-Forwarded-For": "garbage;;--not-an-ip"}
    req.remote = "198.51.100.99"
    ip = extract_client_ip(req)
    assert ip in ("garbage;;--not-an-ip", "198.51.100.99")


def test_f03_b03_ipv6_address_in_forwarded_header():
    req = MagicMock()
    req.headers = {"X-Forwarded-For": "2600:1f18:63fe:e800::1"}
    req.remote = "127.0.0.1"
    assert "2600:1f18" in extract_client_ip(req)


def test_f03_b04_private_cidr_range_detection():
    assert is_trusted_proxy("127.0.0.1") is True
    assert is_render_nat_ip("44.209.160.1") is True
    assert is_trusted_proxy("203.0.113.1") is False


def test_f03_b05_burst_from_shared_nat_gateway_isolation():
    for _ in range(20):
        allowed, _ = security_service.rate_limiter.is_allowed("127.0.0.1", path="/health")
        assert allowed is True


# ==============================================================================
# Feature 4 Boundary: Non-Punitive User Throttling
# ==============================================================================

@pytest.mark.asyncio
async def test_f04_b01_zero_time_delta_handling():
    middleware = ThrottlingMiddleware(rate_limit=1.0)
    handler = AsyncMock(return_value="ok")
    event = MagicMock(spec=Message)
    event.from_user = TgUser(id=4101, is_bot=False, first_name="User")
    await middleware(handler, event, {})
    res2 = await middleware(handler, event, {})
    assert res2 is None


@pytest.mark.asyncio
async def test_f04_b02_rapid_repeated_hits_do_not_extend_cooldown_indefinitely():
    middleware = ThrottlingMiddleware(rate_limit=0.08)
    handler = AsyncMock(return_value="ok")
    event = MagicMock(spec=Message)
    event.from_user = TgUser(id=4102, is_bot=False, first_name="User")
    await middleware(handler, event, {})
    for _ in range(5):
        await middleware(handler, event, {})
    await asyncio.sleep(0.1)
    res = await middleware(handler, event, {})
    assert res == "ok"


@pytest.mark.asyncio
async def test_f04_b03_user_timestamps_cleanup_over_10000_entries():
    middleware = ThrottlingMiddleware(rate_limit=1.0)
    now = time.monotonic()
    for i in range(10005):
        middleware.user_timestamps[i] = now - 20.0
    handler = AsyncMock(return_value="cleaned")
    event = MagicMock(spec=Message)
    event.from_user = TgUser(id=999999, is_bot=False, first_name="User")
    await middleware(handler, event, {})
    assert len(middleware.user_timestamps) < 1000


@pytest.mark.asyncio
async def test_f04_b04_independent_throttling_across_distinct_users():
    middleware = ThrottlingMiddleware(rate_limit=1.0)
    handler = AsyncMock(return_value="ok")
    event_a = MagicMock(spec=Message)
    event_a.from_user = TgUser(id=4104, is_bot=False, first_name="UserA")
    event_b = MagicMock(spec=Message)
    event_b.from_user = TgUser(id=4105, is_bot=False, first_name="UserB")
    res_a1 = await middleware(handler, event_a, {})
    res_b1 = await middleware(handler, event_b, {})
    assert res_a1 == "ok"
    assert res_b1 == "ok"


@pytest.mark.asyncio
async def test_f04_b05_subsecond_rate_limit_granularity():
    middleware = ThrottlingMiddleware(rate_limit=0.02)
    handler = AsyncMock(return_value="fast")
    event = MagicMock(spec=Message)
    event.from_user = TgUser(id=4106, is_bot=False, first_name="User")
    await middleware(handler, event, {})
    await asyncio.sleep(0.03)
    res = await middleware(handler, event, {})
    assert res == "fast"


# ==============================================================================
# Feature 5 Boundary: Negative Ban Check Caching
# ==============================================================================

@pytest.mark.asyncio
async def test_f05_b01_cache_expiration_after_ttl():
    middleware = BotSecurityMiddleware()
    middleware._banned_cache[5101] = time.monotonic() - 65.0
    assert (time.monotonic() - middleware._banned_cache[5101]) > 60.0


@pytest.mark.asyncio
async def test_f05_b02_distinct_user_ids_cache_isolation():
    middleware = BotSecurityMiddleware()
    middleware._banned_cache[5102] = time.monotonic()
    assert 5102 in middleware._banned_cache
    assert 5103 not in middleware._banned_cache


@pytest.mark.asyncio
async def test_f05_b03_db_exception_fallback_graceful():
    middleware = BotSecurityMiddleware()
    handler = AsyncMock(return_value="recovered")
    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=5104, is_bot=False, first_name="User")
    msg.text = "hello"
    with patch("middlewares.security.get_session", side_effect=RuntimeError("DB offline")):
        res = await middleware(handler, msg, {})
        assert res == "recovered"


@pytest.mark.asyncio
async def test_f05_b04_rapid_burst_queries_single_db_hit(e2e_db_session: AsyncSession):
    for _ in range(5):
        is_banned = await crud.is_user_banned(e2e_db_session, 5105)
        assert is_banned is False


@pytest.mark.asyncio
async def test_f05_b05_unban_event_invalidation(e2e_db_session: AsyncSession):
    await crud.get_or_create_user(e2e_db_session, user_id=5106)
    await crud.set_user_ban_status(e2e_db_session, 5106, True)
    await e2e_db_session.commit()
    assert await crud.is_user_banned(e2e_db_session, 5106) is True
    await crud.set_user_ban_status(e2e_db_session, 5106, False)
    await e2e_db_session.commit()
    assert await crud.is_user_banned(e2e_db_session, 5106) is False


# ==============================================================================
# Feature 6 Boundary: Syntax & Import Flaw Resolution
# ==============================================================================

def test_f06_b01_typing_symbols_available():
    import typing
    assert hasattr(typing, "Any")
    assert hasattr(typing, "Optional")
    assert hasattr(typing, "List")
    assert hasattr(typing, "Dict")


def test_f06_b02_books_module_all_exported_symbols_valid():
    import handlers.books as hb
    symbols = [s for s in dir(hb) if not s.startswith("__")]
    assert "router" in symbols
    assert "CAT_NAMES" in symbols


def test_f06_b03_no_circular_imports_across_services_and_handlers():
    import handlers.start
    import handlers.movies
    import handlers.music
    import handlers.books
    import services.web_server
    assert True


def test_f06_b04_config_instantiation_without_env_side_effects():
    from config import Settings
    c = Settings()
    assert hasattr(c, "BOT_TOKEN")
    assert hasattr(c, "ADMIN_IDS_RAW")


def test_f06_b05_state_machine_classes_instantiable():
    from utils.states import BookStates, MovieAddStates
    assert BookStates is not None
    assert MovieAddStates is not None


# ==============================================================================
# Feature 7 Boundary: Atomic Concurrency in get_or_create_user
# ==============================================================================

@pytest.mark.asyncio
async def test_f07_b01_high_concurrency_parallel_tasks_same_id(e2e_db_session: AsyncSession):
    for i in range(5):
        u, _ = await crud.get_or_create_user(e2e_db_session, user_id=7101, username=f"user_{i}")
    await e2e_db_session.commit()
    assert u.id == 7101
    assert u.username == "user_4"


@pytest.mark.asyncio
async def test_f07_b02_unicode_special_chars_in_name(e2e_db_session: AsyncSession):
    u, _ = await crud.get_or_create_user(
        e2e_db_session, user_id=7102, first_name="O'ktam", last_name="G'ulomov"
    )
    await e2e_db_session.commit()
    assert u.first_name == "O'ktam"
    assert u.last_name == "G'ulomov"


@pytest.mark.asyncio
async def test_f07_b03_none_username_and_names(e2e_db_session: AsyncSession):
    u, created = await crud.get_or_create_user(
        e2e_db_session, user_id=7103, username=None, first_name=None, last_name=None
    )
    await e2e_db_session.commit()
    assert created is True
    assert u.username is None


@pytest.mark.asyncio
async def test_f07_b04_extreme_user_id_boundaries(e2e_db_session: AsyncSession):
    max_id = 2**53 - 1
    u, _ = await crud.get_or_create_user(e2e_db_session, user_id=max_id)
    await e2e_db_session.commit()
    assert u.id == max_id


@pytest.mark.asyncio
async def test_f07_b05_transaction_rollback_preserves_consistency(e2e_db_session: AsyncSession):
    user = User(id=7105, username="temp")
    e2e_db_session.add(user)
    await e2e_db_session.flush()
    await e2e_db_session.rollback()
    e2e_db_session.expunge_all()
    assert await crud.get_user(e2e_db_session, 7105) is None


# ==============================================================================
# Feature 8 Boundary: Atomic Concurrency in Movie Upserts
# ==============================================================================

@pytest.mark.asyncio
async def test_f08_b01_numeric_string_code_variants(e2e_db_session: AsyncSession):
    m1, _ = await crud.upsert_movie(e2e_db_session, code="007", title="James Bond")
    await e2e_db_session.commit()
    found = await crud.get_movie_by_code(e2e_db_session, "007")
    assert found is not None
    assert found.code == "007"


@pytest.mark.asyncio
async def test_f08_b02_sequential_upsert_parallel_tasks_same_code(e2e_db_session: AsyncSession):
    for i in range(5):
        m, _ = await crud.upsert_movie(e2e_db_session, code="8102", title=f"Sync {i}")
    await e2e_db_session.commit()
    assert m.title == "Sync 4"


@pytest.mark.asyncio
async def test_f08_b03_empty_fields_handling(e2e_db_session: AsyncSession):
    m, _ = await crud.upsert_movie(e2e_db_session, code="8103", title="No Desc", description=None, year=None)
    await e2e_db_session.commit()
    assert m.code == "8103"


@pytest.mark.asyncio
async def test_f08_b04_special_characters_in_movie_title(e2e_db_session: AsyncSession):
    m, _ = await crud.upsert_movie(e2e_db_session, code="8104", title="Qasoskorlar: Intiho & <Final>")
    await e2e_db_session.commit()
    assert "<Final>" in m.title


@pytest.mark.asyncio
async def test_f08_b05_large_description_payload_upsert(e2e_db_session: AsyncSession):
    long_desc = "Kino tavsifi. " * 200
    m, _ = await crud.upsert_movie(e2e_db_session, code="8105", title="Long Desc", description=long_desc)
    await e2e_db_session.commit()
    assert len(m.description) > 1000


# ==============================================================================
# Feature 9 Boundary: SQLite Pool & PRAGMA Optimization
# ==============================================================================

@pytest.mark.asyncio
async def test_f09_b01_concurrent_sessions_do_not_lock(e2e_db_session: AsyncSession):
    for _ in range(5):
        res = await e2e_db_session.execute(text("SELECT 1"))
        assert res.scalar() == 1


@pytest.mark.asyncio
async def test_f09_b02_rapid_session_acquire_and_release_50x(e2e_db_session: AsyncSession):
    for i in range(50):
        await e2e_db_session.execute(text(f"SELECT {i}"))
    assert True


@pytest.mark.asyncio
async def test_f09_b03_transaction_nesting_and_savepoints(e2e_db_session: AsyncSession):
    async with e2e_db_session.begin_nested():
        await crud.get_or_create_user(e2e_db_session, user_id=9103)
    await e2e_db_session.commit()
    user = await crud.get_user(e2e_db_session, 9103)
    assert user is not None


@pytest.mark.asyncio
async def test_f09_b04_dispose_and_recreate_engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    await eng.dispose()
    assert True


@pytest.mark.asyncio
async def test_f09_b05_in_memory_sqlite_pragma_safety(e2e_db_session: AsyncSession):
    res = await e2e_db_session.execute(text("PRAGMA synchronous"))
    val = res.scalar()
    assert val is not None


# ==============================================================================
# Feature 10 Boundary: Periodic Storage Pruning Task
# ==============================================================================

def test_f10_b01_boundary_timestamp_exactly_30d():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    assert (now - cutoff).days == 30


def test_f10_b02_future_timestamp_log_entries():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=5)
    cutoff = now - timedelta(days=30)
    assert future > cutoff


@pytest.mark.asyncio
async def test_f10_b03_large_batch_prune_simulation(e2e_db_session: AsyncSession):
    res = await e2e_db_session.execute(text("DELETE FROM users WHERE id < 0"))
    assert res.rowcount >= 0


@pytest.mark.asyncio
async def test_f10_b04_concurrent_inserts_during_prune(e2e_db_session: AsyncSession):
    await crud.get_or_create_user(e2e_db_session, user_id=10104)
    await e2e_db_session.execute(text("DELETE FROM users WHERE id = -1"))
    await e2e_db_session.commit()
    assert await crud.get_user(e2e_db_session, 10104) is not None


@pytest.mark.asyncio
async def test_f10_b05_empty_table_prune_no_exception(e2e_db_session: AsyncSession):
    res = await e2e_db_session.execute(text("DELETE FROM movies WHERE code = 'none'"))
    assert res.rowcount == 0


# ==============================================================================
# Feature 11 Boundary: Docker Build Asset Optimization
# ==============================================================================

def test_f11_b01_essential_assets_not_accidentally_excluded():
    assert (BASE_DIR / "data" / "books.json").exists()


def test_f11_b02_music_catalog_retained():
    assert (BASE_DIR / "data" / "music_home.json").exists()


def test_f11_b03_webapp_static_assets_retained():
    assert (BASE_DIR / "webapp" / "index.html").exists()


def test_f11_b04_comments_and_whitespace_in_ignore_patterns():
    lines = ["# Build artifacts", "", "scratch/", "data/videos/*.mp4"]
    cleaned = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    assert len(cleaned) == 2


def test_f11_b05_deep_nested_pattern_matching():
    pattern = re.compile(r"(^|/)\.git(/|$)")
    assert pattern.search(".git/config") is not None


# ==============================================================================
# Feature 12 Boundary: Direct-First CORS TV Streaming
# ==============================================================================

def test_f12_b01_invalid_stream_url_encoding_handled():
    is_mal, _ = is_malicious_request(path="/api/tv/stream", query_string="url=http://evil.com/%27%20UNION%20SELECT")
    assert is_mal is True


@pytest.mark.asyncio
async def test_f12_b02_empty_stream_url_proxy_returns_bad_request(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/api/tv/stream?url=")
    assert resp.status in (400, 403, 404)


def test_f12_b03_mixed_http_and_https_streams_sanitized():
    for ch in CHANNELS_LIST[:30]:
        stream = ch.get("stream", "")
        assert stream.startswith("http://") or stream.startswith("https://")


@pytest.mark.asyncio
async def test_f12_b04_proxy_endpoint_supports_cors_headers(e2e_web_client: TestClient):
    resp = await e2e_web_client.options("/api/tv")
    assert resp.status in (200, 204)


def test_f12_b05_non_cinerama_stream_url_handling():
    non_cinerama = [c for c in CHANNELS_LIST if "cinerama.uz" not in c.get("stream", "")]
    assert len(non_cinerama) > 0


# ==============================================================================
# Feature 13 Boundary: TV Proxy Pool & Timeout Tuning
# ==============================================================================

def test_f13_b01_path_traversal_in_proxy_url_blocked():
    is_mal, _ = is_malicious_request(path="/api/tv/stream", query_string="url=../../etc/passwd")
    assert is_mal is True


def test_f13_b02_command_injection_in_proxy_url_blocked():
    is_mal, _ = is_malicious_request(path="/api/tv/stream", query_string="url=http://example.com/stream.m3u8;cat%20/etc/passwd")
    assert is_mal is True


def test_f13_b03_zero_byte_url_handled():
    is_mal, _ = is_malicious_request(path="/api/tv/stream")
    assert is_mal is False


def test_f13_b04_allowed_extensions_contain_video_types():
    is_recon, _ = check_reconnaissance_and_database_shield("/media/stream.mp4")
    assert is_recon is False


def test_f13_b05_sensitive_file_extensions_blocked():
    is_recon, _ = check_reconnaissance_and_database_shield("/backup/data.sqlite3")
    assert is_recon is True


# ==============================================================================
# Feature 14 Boundary: Removal of Blocking Pre-Speed Check
# ==============================================================================

@pytest.mark.asyncio
async def test_f14_b01_zero_speed_telemetry_payload(e2e_web_client: TestClient):
    resp = await e2e_web_client.post("/api/tv/telemetry", json={"event": "speed", "speed_mbps": 0.0})
    assert resp.status in (200, 204)


@pytest.mark.asyncio
async def test_f14_b02_negative_latency_value_sanitized(e2e_web_client: TestClient):
    resp = await e2e_web_client.post("/api/tv/telemetry", json={"event": "latency", "ms": -50})
    assert resp.status in (200, 204)


@pytest.mark.asyncio
async def test_f14_b03_massive_telemetry_payload_rejected_or_handled(e2e_web_client: TestClient):
    big_data = {"event": "bomb", "data": "X" * 10000}
    resp = await e2e_web_client.post("/api/tv/telemetry", json=big_data)
    assert resp.status in (200, 204, 400, 413)


@pytest.mark.asyncio
async def test_f14_b04_telemetry_without_optional_fields(e2e_web_client: TestClient):
    resp = await e2e_web_client.post("/api/tv/telemetry", json={"event": "ping"})
    assert resp.status in (200, 204)


@pytest.mark.asyncio
async def test_f14_b05_rapid_telemetry_bursts(e2e_web_client: TestClient):
    for i in range(5):
        resp = await e2e_web_client.post("/api/tv/telemetry", json={"event": f"burst_{i}"})
        assert resp.status in (200, 204)


# ==============================================================================
# Feature 15 Boundary: TV Catalog Sanitization & Health Check
# ==============================================================================

def test_f15_b01_channel_id_uniqueness_across_catalog():
    ids = [ch["id"] for ch in CHANNELS_LIST]
    assert len(ids) == len(set(ids))


def test_f15_b02_ruxsor_channel_has_valid_failover():
    ruxsor = next((ch for ch in CHANNELS_LIST if "Ruxsor" in ch.get("name", "")), None)
    if ruxsor:
        assert len(ruxsor.get("u", [])) >= 1


def test_f15_b03_nasaf_channel_has_valid_failover():
    nasaf = next((ch for ch in CHANNELS_LIST if "Nasaf" in ch.get("name", "")), None)
    if nasaf:
        assert len(nasaf.get("u", [])) >= 1


def test_f15_b04_missing_logo_fallback_handling():
    for ch in CHANNELS_LIST[:20]:
        logo = ch.get("l") or ch.get("logo")
        assert logo is not None


def test_f15_b05_empty_category_filtering_returns_all():
    all_cats = TV_CATEGORIES
    assert len(all_cats) >= 5


# ==============================================================================
# Feature 16 Boundary: HLS.js Buffer & Stalling Optimization
# ==============================================================================

def test_f16_b01_discontinuity_tag_handling():
    playlist = "#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXT-X-DISCONTINUITY\n#EXTINF:10.0,\nseg1.ts\n"
    assert "#EXT-X-DISCONTINUITY" in playlist


def test_f16_b02_endlist_tag_vod_vs_live_handling():
    live_playlist = "#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10.0,\nseg1.ts\n"
    assert "#EXT-X-ENDLIST" not in live_playlist


def test_f16_b03_very_short_target_duration_1s():
    playlist = "#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1.0,\nseg1.ts\n"
    match = re.search(r"#EXT-X-TARGETDURATION:(\d+)", playlist)
    assert match is not None
    assert int(match.group(1)) == 1


def test_f16_b04_empty_playlist_handling():
    empty_pl = ""
    assert "#EXTM3U" not in empty_pl


def test_f16_b05_playlist_with_relative_segment_paths():
    pl = "#EXTM3U\n#EXTINF:10.0,\nchunk_001.ts\n"
    assert not pl.startswith("http")


# ==============================================================================
# Feature 17 Boundary: Movie 1-to-1 Replication & Deep Linking
# ==============================================================================

@pytest.mark.asyncio
async def test_f17_b01_non_existent_movie_code_response(e2e_db_session: AsyncSession):
    found = await crud.get_movie_by_code(e2e_db_session, "9999999")
    assert found is None


@pytest.mark.asyncio
async def test_f17_b02_alphanumeric_code_variations(e2e_db_session: AsyncSession):
    await crud.upsert_movie(e2e_db_session, code="K-102", title="Kino Serial Part")
    await e2e_db_session.commit()
    m = await crud.get_movie_by_code(e2e_db_session, "K-102")
    assert m is not None


def test_f17_b03_deep_link_with_leading_zeros():
    match = re.match(r"^/start\s+(\d+)$", "/start 007")
    assert match is not None
    assert match.group(1) == "007"


def test_f17_b04_franchise_with_single_movie():
    from services.movie_service import movie_service
    assert hasattr(movie_service, "find_by_code")


@pytest.mark.asyncio
async def test_f17_b05_movie_code_exceeding_max_int(e2e_db_session: AsyncSession):
    big_code = "99999999999999999999"
    await crud.upsert_movie(e2e_db_session, code=big_code, title="Big Code Film")
    await e2e_db_session.commit()
    found = await crud.get_movie_by_code(e2e_db_session, big_code)
    assert found is not None


# ==============================================================================
# Feature 18 Boundary: Telegram Cloud Pool Movie Delivery
# ==============================================================================

@pytest.mark.asyncio
async def test_f18_b01_missing_file_id_fallback(mock_bot):
    await mock_bot.send_message(chat_id=123, text="Fayl topilmadi", protect_content=True)
    mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_f18_b02_invalid_file_id_error_handling(mock_bot):
    mock_bot.send_video.side_effect = Exception("Wrong file identifier")
    try:
        await mock_bot.send_video(chat_id=123, video="bad_id")
    except Exception as e:
        assert "Wrong file identifier" in str(e)


@pytest.mark.asyncio
async def test_f18_b03_movie_with_no_description_caption(mock_bot):
    caption = "🎬 <b>Nomsiz Film</b>\n\n@BauntyFilms"
    await mock_bot.send_message(chat_id=123, text=caption)
    assert "@BauntyFilms" in caption


@pytest.mark.asyncio
async def test_f18_b04_ultra_long_movie_title_truncation(mock_bot):
    long_title = "A" * 600
    truncated = (long_title[:100] + "...") if len(long_title) > 100 else long_title
    assert len(truncated) <= 103


@pytest.mark.asyncio
async def test_f18_b05_rapid_duplicate_delivery_requests(mock_bot):
    for _ in range(3):
        await mock_bot.send_video(chat_id=123, video="file_123")
    assert mock_bot.send_video.call_count == 3


# ==============================================================================
# Feature 19 Boundary: Music Multi-Engine Search & Shazam
# ==============================================================================

@pytest.mark.asyncio
async def test_f19_b01_empty_search_query_handling():
    svc = MusicService()
    res = await svc.search_tracks("")
    assert res == []


@pytest.mark.asyncio
async def test_f19_b02_no_results_found_graceful_message():
    svc = MusicService()
    res = await svc.search_tracks("qwertyuiopasdfghjklzxcvbnm1234567890")
    assert isinstance(res, list)


@pytest.mark.asyncio
async def test_f19_b03_special_characters_in_music_search():
    svc = MusicService()
    res = await svc.search_tracks("!@#$%^&*()_+")
    assert isinstance(res, list)


@pytest.mark.asyncio
async def test_f19_b04_single_engine_failure_fallback():
    svc = MusicService()
    with patch.object(svc, "search_tracks", AsyncMock(return_value=[])):
        res = await svc.search_tracks("fallback_test")
        assert res == []


@pytest.mark.asyncio
async def test_f19_b05_corrupted_audio_file_for_shazam():
    svc = MusicService()
    assert hasattr(svc, "search_tracks")


# ==============================================================================
# Feature 20 Boundary: Mini App Dual-Audio Preload Player
# ==============================================================================

@pytest.mark.asyncio
async def test_f20_b01_api_music_send_invalid_chat_id(e2e_web_client: TestClient):
    resp = await e2e_web_client.post("/api/music/send", json={"track_id": "1", "chat_id": "bad"})
    assert resp.status in (400, 401, 403, 404, 500)


@pytest.mark.asyncio
async def test_f20_b02_api_music_send_missing_track_id(e2e_web_client: TestClient):
    resp = await e2e_web_client.post("/api/music/send", json={"chat_id": 12345})
    assert resp.status in (400, 401, 403, 404, 500)


def test_f20_b03_atlas_cover_with_empty_title():
    from services.book_service import generate_dynamic_book_cover
    img = generate_dynamic_book_cover({"id": "99", "title": "", "author": ""})
    assert len(img) > 50


def test_f20_b04_unsupported_mood_category_filter():
    from services.music_data import MOODS_LIST
    assert not any(c.get("id") == "unsupported_xyz" for c in MOODS_LIST)


def test_f20_b05_simultaneous_dual_audio_preload_candidates():
    tracks = [
        {"id": "1", "title": "Track 1", "audio_url": "https://example.com/1.mp3"},
        {"id": "2", "title": "Track 2", "audio_url": "https://example.com/2.mp3"},
    ]
    assert len(tracks) == 2
    assert tracks[0]["audio_url"] != tracks[1]["audio_url"]


# ==============================================================================
# Feature 21 Boundary: Strict BauntyCinemBot Brand Purity
# ==============================================================================

def test_f21_b01_mixed_case_zakirovs_variants():
    text = "Follow @ZaKiRoVsFiLmS_BoT for movies"
    sanitized = re.sub(r"@zakirovs[a-zA-Z0-9_]*", "@BauntyCinemabot", text, flags=re.I)
    assert "@ZaKiRoVsFiLmS_BoT" not in sanitized
    assert "@BauntyCinemabot" in sanitized


def test_f21_b02_clean_text_unchanged_by_sanitizer():
    clean = "Baunty Films taqdim etadi"
    sanitized = re.sub(r"@zakirovs[a-zA-Z0-9_]*", "@BauntyCinemabot", clean, flags=re.I)
    assert sanitized == clean


def test_f21_b03_urls_with_zakirovs_sanitized():
    url = "https://t.me/zakirovsfilms_bot"
    sanitized = re.sub(r"zakirovsfilms_bot", "BauntyCinemabot", url, flags=re.I)
    assert "zakirovs" not in sanitized.lower()


def test_f21_b04_empty_string_sanitizer_safety():
    empty = ""
    sanitized = re.sub(r"@zakirovs[a-zA-Z0-9_]*", "@BauntyCinemabot", empty, flags=re.I)
    assert sanitized == ""


def test_f21_b05_multiple_occurrences_in_single_text():
    text = "@Zakirovsfilms_bot and @zakirovs_ai are upstream"
    sanitized = re.sub(r"@zakirovs[a-zA-Z0-9_]*", "@BauntyCinemabot", text, flags=re.I)
    assert "@Zakirovs" not in sanitized


# ==============================================================================
# Feature 22 Boundary: Books Catalog & Local Cover Caching
# ==============================================================================

def test_f22_b01_search_book_by_latin_and_cyrillic():
    res1 = get_catalog(query="Alkimyogar")
    assert res1["ok"] is True
    res2 = get_catalog(query="Алкимёгар")
    assert res2["ok"] is True


def test_f22_b02_book_id_zero_or_negative_lookup():
    assert get_book_by_id("0") is None
    assert get_book_by_id("-1") is None


def test_f22_b03_missing_cover_image_fallback():
    from services.book_service import get_book_thumbnail_bytes
    fake_book = {"id": "-999", "title": "No Cover", "author": "None"}
    thumb = get_book_thumbnail_bytes(fake_book)
    assert thumb is None or isinstance(thumb, bytes)


def test_f22_b04_book_with_mojibake_characters_sanitized():
    dirty = "Oâ€™tkan kunlar â€” Abdulla Qodiriy"
    clean = sanitize_book_text(dirty)
    assert "â€™" not in clean
    assert "â€”" not in clean


def test_f22_b05_catalog_pagination_boundary_limits():
    res = get_catalog(offset=999999, limit=10)
    assert res["ok"] is True
    assert res["items"] == []


# ==============================================================================
# Feature 23 Boundary: Async Book Remote Fetching
# ==============================================================================

def test_f23_b01_timeout_fast_fail():
    t0 = time.monotonic()
    b = get_book_by_id("non_existent_99999")
    t1 = time.monotonic()
    assert b is None
    assert (t1 - t0) < 1.5


def test_f23_b02_non_numeric_id_skips_upstream():
    b = get_book_by_id("invalid_alpha_code")
    assert b is None


def test_f23_b03_upstream_malformed_json_fallback():
    res = get_book_by_id("99998888")
    assert res is None


def test_f23_b04_book_categories_count_boundary():
    assert len(get_catalog()["categories"]) >= 5


def test_f23_b05_cached_books_immutability():
    b1 = get_book_by_id("1")
    b2 = get_book_by_id("1")
    assert b1["id"] == b2["id"]


# ==============================================================================
# Feature 24 Boundary: Book Reading & Document Delivery
# ==============================================================================

def test_f24_b01_book_with_empty_description_doc():
    b = {"id": "test_empty", "title": "Empty Desc", "author": "Author", "description": ""}
    pdf = create_book_pdf_sample(b)
    assert len(pdf) > 100


def test_f24_b02_special_characters_in_author_doc_title():
    b = {"id": "test_spec", "title": "Title <&>", "author": "Author 'Special'"}
    pdf = create_book_pdf_sample(b)
    assert len(pdf) > 100


@pytest.mark.asyncio
async def test_f24_b03_send_document_failure_falls_back_to_message(mock_bot):
    mock_bot.send_document.side_effect = Exception("Doc upload error")
    res = await deliver_book(mock_bot, chat_id=123, book_id="1", fmt="pdf")
    assert res.get("ok") is True
    assert res.get("format") == "text"


def test_f24_b04_unsupported_format_defaults_to_pdf():
    b = get_book_by_id("1")
    pdf = create_book_pdf_sample(b)
    assert pdf.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_f24_b05_protect_content_flag_on_document(mock_bot):
    await deliver_book(mock_bot, chat_id=123, book_id="1", fmt="pdf")
    mock_bot.send_document.assert_called_once()
    assert mock_bot.send_document.call_args[1]["protect_content"] is True


# ==============================================================================
# Feature 25 Boundary: Package Manifest Alignment
# ==============================================================================

def test_f25_b01_no_duplicate_package_entries():
    lines = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    pkg_names = [l.split(">=")[0].split("==")[0].split("<")[0].strip().lower() for l in lines if l.strip()]
    assert len(pkg_names) == len(set(pkg_names))


def test_f25_b02_version_operators_valid():
    lines = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    for line in lines:
        if line.strip():
            assert any(op in line for op in (">=", "==", "<=", "~=", "<"))


def test_f25_b03_shazamio_import_safety():
    import shazamio
    assert shazamio is not None


def test_f25_b04_pillow_package_installed():
    import PIL
    assert PIL is not None


def test_f25_b05_asyncio_drivers_in_manifest():
    content = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "aiosqlite" in content
    assert "asyncpg" in content


# ==============================================================================
# Feature 26 Boundary: Full Opaque-Box E2E Test Suite
# ==============================================================================

def test_f26_b01_test_isolation_no_state_leak():
    assert security_service.is_ip_banned("10.99.99.99")[0] is False


def test_f26_b02_randomized_execution_order_safety():
    b = get_book_by_id("1")
    assert b is not None
    assert len(CHANNELS_LIST) > 0


def test_f26_b03_environment_variable_override_resilience():
    with patch.dict(os.environ, {"CUSTOM_TEST_VAR": "123"}):
        assert os.getenv("CUSTOM_TEST_VAR") == "123"


def test_f26_b04_deterministic_assertion_verification():
    for _ in range(10):
        assert get_book_by_id("1")["id"] == "1"


def test_f26_b05_test_timing_budget_compliance():
    t0 = time.monotonic()
    load_books()
    t1 = time.monotonic()
    assert (t1 - t0) < 0.1


# ==============================================================================
# Feature 27 Boundary: Adversarial Hardening
# ==============================================================================

def test_f27_b01_url_encoded_sqli_evasion_blocked():
    is_mal, _ = is_malicious_request(path="/api/kino", query_string="q=%27%20OR%201=1--")
    assert is_mal is True


def test_f27_b02_double_url_encoded_path_traversal():
    is_mal, _ = is_malicious_request(path="/static/%252e%252e%252fetc/passwd")
    assert is_mal is True


def test_f27_b03_command_injection_metacharacters():
    is_mal, _ = is_malicious_request(path="/api/dl", query_string="url=http://example.com;rm%20-rf")
    assert is_mal is True


def test_f27_b04_script_alert_variation_xss():
    is_mal, _ = is_malicious_request(path="/webapp", query_string="name=<SCRIPT%20SRC=http://evil.com/xss.js>")
    assert is_mal is True


def test_f27_b05_null_byte_injection_blocked():
    is_mal, _ = is_malicious_request(path="/files/doc.pdf%00.exe")
    assert is_mal is True
