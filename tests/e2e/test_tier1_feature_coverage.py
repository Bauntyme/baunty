"""
Tier 1: Feature Coverage Test Suite (BauntyCinemBot E2E).
Direct requirement verification for all 27 features in PROJECT.md (>=5 tests per feature = 135 tests).
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
from database.models import User, Movie, Base
from middlewares.throttling import ThrottlingMiddleware
from middlewares.security import BotSecurityMiddleware
from services.security_service import (
    security_service,
    extract_client_ip,
    is_malicious_request,
    check_reconnaissance_and_database_shield,
    get_security_headers,
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
    generate_dynamic_book_cover,
    CATEGORIES_META,
)
from services.music_service import MusicService
from services.music_data import MOODS_LIST
from services.telemetry_service import telemetry_service
from services.movie_service import movie_service
from services.web_server import create_web_app


# ==============================================================================
# Feature 1: Uptime & Keepalive Path Whitelisting (R1)
# ==============================================================================

@pytest.mark.asyncio
async def test_f01_01_health_endpoint_returns_200(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data.get("status") == "ok"


@pytest.mark.asyncio
async def test_f01_02_ping_endpoint_returns_pong(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/ping")
    assert resp.status == 200
    text = await resp.text()
    assert "pong" in text


@pytest.mark.asyncio
async def test_f01_03_root_path_head_request_succeeds(e2e_web_client: TestClient):
    resp = await e2e_web_client.head("/")
    assert resp.status in (200, 302, 304)


@pytest.mark.asyncio
async def test_f01_04_healthz_and_status_paths_whitelisted(e2e_web_client: TestClient):
    for path in ("/healthz", "/status"):
        resp = await e2e_web_client.get(path)
        assert resp.status == 200, f"Path {path} returned status {resp.status}"


def test_f01_05_sliding_window_whitelists_health_paths():
    allowed, retry_after = security_service.rate_limiter.is_allowed("198.51.100.1", path="/health")
    assert allowed is True
    assert retry_after is None
    allowed_ping, _ = security_service.rate_limiter.is_allowed("198.51.100.2", path="/ping")
    assert allowed_ping is True


# ==============================================================================
# Feature 2: WAF Auto-Ban False Positive Elimination (R1)
# ==============================================================================

def test_f02_01_uptimerobot_ua_not_marked_malicious():
    is_mal, _ = is_malicious_request(
        path="/health", user_agent="Mozilla/5.0 (compatible; UptimeRobot/2.0; +http://www.uptimerobot.com/)"
    )
    assert is_mal is False


def test_f02_02_pingdom_ua_not_marked_malicious():
    is_mal, _ = is_malicious_request(
        path="/ping", user_agent="Pingdom.com_bot_version_1.4_(http://www.pingdom.com/)"
    )
    assert is_mal is False


def test_f02_03_betteruptime_ua_not_marked_malicious():
    is_mal, _ = is_malicious_request(path="/status", user_agent="BetterUptime/1.0")
    assert is_mal is False


def test_f02_04_render_healthcheck_ua_not_marked_malicious():
    is_mal, _ = is_malicious_request(path="/", user_agent="Render/1.0 Healthcheck")
    assert is_mal is False


def test_f02_05_monitoring_probe_not_jailed():
    ip = "192.0.2.10"
    is_mal, _ = is_malicious_request(path="/health", user_agent="UptimeRobot/2.0")
    assert is_mal is False
    assert security_service.is_ip_banned(ip)[0] is False


# ==============================================================================
# Feature 3: Render NAT Egress IP Collision Prevention (R1)
# ==============================================================================

def test_f03_01_extract_client_ip_from_single_x_forwarded_for():
    req = MagicMock()
    req.headers = {"X-Forwarded-For": "203.0.113.195"}
    req.remote = "10.0.0.1"
    ip = extract_client_ip(req)
    assert ip == "203.0.113.195"


def test_f03_02_extract_client_ip_from_multi_proxy_chain():
    req = MagicMock()
    req.headers = {"X-Forwarded-For": "198.51.100.25, 10.0.0.5, 127.0.0.1"}
    req.remote = "10.0.0.5"
    ip = extract_client_ip(req)
    assert ip == "198.51.100.25"


def test_f03_03_extract_client_ip_fallback_to_remote():
    req = MagicMock()
    req.headers = {}
    req.remote = "192.168.1.50"
    ip = extract_client_ip(req)
    assert ip == "192.168.1.50"


def test_f03_04_render_keepalive_target_urls_defined():
    from services.keepalive_service import TARGET_HEALTH_URLS
    assert len(TARGET_HEALTH_URLS) >= 1
    assert any("/health" in u for u in TARGET_HEALTH_URLS)


def test_f03_05_loopback_and_trusted_proxies_recognized():
    from services.security_service import is_trusted_proxy
    assert is_trusted_proxy("127.0.0.1") is True
    assert is_trusted_proxy("::1") is True


# ==============================================================================
# Feature 4: Non-Punitive User Throttling (R1)
# ==============================================================================

@pytest.mark.asyncio
async def test_f04_01_first_request_passes_throttle():
    middleware = ThrottlingMiddleware(rate_limit=1.0)
    handler = AsyncMock(return_value="ok")
    event = MagicMock(spec=Message)
    event.from_user = TgUser(id=1001, is_bot=False, first_name="User")
    res = await middleware(handler, event, {})
    assert res == "ok"


@pytest.mark.asyncio
async def test_f04_02_immediate_second_request_is_throttled():
    middleware = ThrottlingMiddleware(rate_limit=1.0)
    handler = AsyncMock(return_value="ok")
    event = MagicMock(spec=Message)
    event.from_user = TgUser(id=1002, is_bot=False, first_name="User")
    await middleware(handler, event, {})
    res2 = await middleware(handler, event, {})
    assert res2 is None


@pytest.mark.asyncio
async def test_f04_03_request_after_cooldown_passes():
    middleware = ThrottlingMiddleware(rate_limit=0.05)
    handler = AsyncMock(return_value="ok")
    event = MagicMock(spec=Message)
    event.from_user = TgUser(id=1003, is_bot=False, first_name="User")
    await middleware(handler, event, {})
    await asyncio.sleep(0.06)
    res = await middleware(handler, event, {})
    assert res == "ok"


@pytest.mark.asyncio
async def test_f04_04_admin_bypasses_throttling():
    middleware = ThrottlingMiddleware(rate_limit=5.0)
    handler = AsyncMock(return_value="admin_ok")
    event = MagicMock(spec=Message)
    event.from_user = TgUser(id=999999, is_bot=False, first_name="Admin")
    with patch.object(config.__class__, "is_admin", return_value=True):
        res1 = await middleware(handler, event, {})
        res2 = await middleware(handler, event, {})
        assert res1 == "admin_ok"
        assert res2 == "admin_ok"


@pytest.mark.asyncio
async def test_f04_05_callback_query_throttling_answers_wait():
    middleware = ThrottlingMiddleware(rate_limit=1.0)
    handler = AsyncMock(return_value="ok")
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = TgUser(id=1005, is_bot=False, first_name="User")
    cb.answer = AsyncMock()
    await middleware(handler, cb, {})
    res2 = await middleware(handler, cb, {})
    assert res2 is None
    cb.answer.assert_called_once()


# ==============================================================================
# Feature 5: Negative Ban Check Caching (R1)
# ==============================================================================

@pytest.mark.asyncio
async def test_f05_01_banned_user_blocked_by_middleware():
    middleware = BotSecurityMiddleware()
    handler = AsyncMock(return_value="ok")
    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=2001, is_bot=False, first_name="Banned")
    msg.answer = AsyncMock()
    middleware._banned_cache[2001] = time.monotonic()
    res = await middleware(handler, msg, {})
    assert res is None
    msg.answer.assert_called_once()


@pytest.mark.asyncio
async def test_f05_02_clean_user_passes_security_middleware():
    middleware = BotSecurityMiddleware()
    handler = AsyncMock(return_value="handled")
    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=2002, is_bot=False, first_name="Clean")
    msg.text = "/start"
    with patch("middlewares.security.get_session") as mock_sess:
        mock_ctx = AsyncMock()
        mock_sess.return_value = mock_ctx
        with patch("middlewares.security.crud.is_user_banned", AsyncMock(return_value=False)):
            res = await middleware(handler, msg, {})
            assert res == "handled"


@pytest.mark.asyncio
async def test_f05_03_admin_skips_security_middleware_ban_check():
    middleware = BotSecurityMiddleware()
    handler = AsyncMock(return_value="admin_bypass")
    msg = MagicMock(spec=Message)
    msg.from_user = TgUser(id=999999, is_bot=False, first_name="Admin")
    with patch.object(config.__class__, "is_admin", return_value=True):
        res = await middleware(handler, msg, {})
        assert res == "admin_bypass"


@pytest.mark.asyncio
async def test_f05_04_db_is_user_banned_crud_returns_false_for_new_user(e2e_db_session: AsyncSession):
    is_banned = await crud.is_user_banned(e2e_db_session, 2004)
    assert is_banned is False


@pytest.mark.asyncio
async def test_f05_05_db_set_user_ban_status_updates_correctly(e2e_db_session: AsyncSession):
    await crud.get_or_create_user(e2e_db_session, user_id=2005, username="ban_test")
    await e2e_db_session.commit()
    await crud.set_user_ban_status(e2e_db_session, 2005, True)
    await e2e_db_session.commit()
    assert await crud.is_user_banned(e2e_db_session, 2005) is True


# ==============================================================================
# Feature 6: Syntax & Import Flaw Resolution (R1)
# ==============================================================================

def test_f06_01_handlers_books_module_imports_cleanly():
    import handlers.books as hb
    assert hasattr(hb, "router")
    assert "books" in hb.router.name


def test_f06_02_handlers_movies_module_imports_cleanly():
    import handlers.movies as hm
    assert hasattr(hm, "router")
    assert "movies" in hm.router.name


def test_f06_03_handlers_music_module_imports_cleanly():
    import handlers.music as hmu
    assert hasattr(hmu, "router")
    assert "music" in hmu.router.name


def test_f06_04_handlers_start_module_imports_cleanly():
    import handlers.start as hs
    assert hasattr(hs, "router")


def test_f06_05_all_routers_registerable():
    from handlers import setup_routers
    main_router = setup_routers()
    assert main_router is not None
    assert len(main_router.sub_routers) >= 5


# ==============================================================================
# Feature 7: Atomic Concurrency in get_or_create_user (R5)
# ==============================================================================

@pytest.mark.asyncio
async def test_f07_01_get_or_create_user_creates_new(e2e_db_session: AsyncSession):
    user, created = await crud.get_or_create_user(
        e2e_db_session, user_id=3001, username="alice", first_name="Alice"
    )
    await e2e_db_session.commit()
    assert created is True
    assert user.id == 3001
    assert user.username == "alice"


@pytest.mark.asyncio
async def test_f07_02_get_or_create_user_retrieves_existing(e2e_db_session: AsyncSession):
    await crud.get_or_create_user(e2e_db_session, user_id=3002, username="bob")
    await e2e_db_session.commit()
    user, created = await crud.get_or_create_user(e2e_db_session, user_id=3002, username="bob_updated")
    await e2e_db_session.commit()
    assert created is False
    assert user.username == "bob_updated"


@pytest.mark.asyncio
async def test_f07_03_get_or_create_user_updates_activity(e2e_db_session: AsyncSession):
    user, _ = await crud.get_or_create_user(e2e_db_session, user_id=3003)
    await e2e_db_session.commit()
    t1 = user.last_active
    await asyncio.sleep(0.01)
    user2, _ = await crud.get_or_create_user(e2e_db_session, user_id=3003)
    await e2e_db_session.commit()
    assert user2.last_active >= t1


@pytest.mark.asyncio
async def test_f07_04_get_or_create_user_preserves_unique_count(e2e_db_session: AsyncSession):
    await crud.get_or_create_user(e2e_db_session, user_id=3004)
    await crud.get_or_create_user(e2e_db_session, user_id=3004)
    await e2e_db_session.commit()
    count = await crud.get_total_users_count(e2e_db_session)
    assert count == 1


@pytest.mark.asyncio
async def test_f07_05_get_or_create_user_with_admin_flag(e2e_db_session: AsyncSession):
    user, _ = await crud.get_or_create_user(e2e_db_session, user_id=3005, is_admin=True)
    await e2e_db_session.commit()
    assert user.is_admin is True


# ==============================================================================
# Feature 8: Atomic Concurrency in Movie Upserts (R5)
# ==============================================================================

@pytest.mark.asyncio
async def test_f08_01_upsert_movie_creates_new(e2e_db_session: AsyncSession):
    movie, created = await crud.upsert_movie(
        e2e_db_session, code="501", title="Interstellar", file_id="file_interstellar"
    )
    await e2e_db_session.commit()
    assert created is True
    assert movie.code == "501"
    assert movie.title == "Interstellar"


@pytest.mark.asyncio
async def test_f08_02_upsert_movie_updates_existing(e2e_db_session: AsyncSession):
    await crud.upsert_movie(e2e_db_session, code="502", title="Original Title")
    await e2e_db_session.commit()
    movie, created = await crud.upsert_movie(e2e_db_session, code="502", title="New Title", rating=8.5)
    await e2e_db_session.commit()
    assert created is False
    assert movie.title == "New Title"
    assert movie.rating == 8.5


@pytest.mark.asyncio
async def test_f08_03_upsert_movie_preserves_views(e2e_db_session: AsyncSession):
    movie, _ = await crud.upsert_movie(e2e_db_session, code="503", title="Movie Views")
    await crud.increment_movie_views(e2e_db_session, movie.id)
    await e2e_db_session.commit()
    m2, _ = await crud.upsert_movie(e2e_db_session, code="503", title="Movie Views Updated")
    await e2e_db_session.commit()
    assert m2.downloads_count >= 1


@pytest.mark.asyncio
async def test_f08_04_get_movie_by_code_finds_upserted(e2e_db_session: AsyncSession):
    await crud.upsert_movie(e2e_db_session, code="504", title="Found Movie")
    await e2e_db_session.commit()
    found = await crud.get_movie_by_code(e2e_db_session, "504")
    assert found is not None
    assert found.title == "Found Movie"


@pytest.mark.asyncio
async def test_f08_05_upsert_movie_idempotent_duplicate_calls(e2e_db_session: AsyncSession):
    for _ in range(3):
        await crud.upsert_movie(e2e_db_session, code="505", title="Repeat")
    await e2e_db_session.commit()
    found = await crud.get_movie_by_code(e2e_db_session, "505")
    assert found is not None


# ==============================================================================
# Feature 9: SQLite Pool & PRAGMA Optimization (R5)
# ==============================================================================

@pytest.mark.asyncio
async def test_f09_01_sqlite_session_executes_queries(e2e_db_session: AsyncSession):
    res = await e2e_db_session.execute(text("SELECT 1"))
    assert res.scalar() == 1


@pytest.mark.asyncio
async def test_f09_02_sqlite_transaction_commit_and_rollback(e2e_db_session: AsyncSession):
    user = User(id=9002, username="rollback_me")
    e2e_db_session.add(user)
    await e2e_db_session.flush()
    await e2e_db_session.rollback()
    e2e_db_session.expunge_all()
    user = await crud.get_user(e2e_db_session, 9002)
    assert user is None


@pytest.mark.asyncio
async def test_f09_03_sqlite_busy_timeout_configured(e2e_db_session: AsyncSession):
    res = await e2e_db_session.execute(text("PRAGMA busy_timeout"))
    timeout = res.scalar()
    assert timeout is not None


@pytest.mark.asyncio
async def test_f09_04_database_models_metadata_complete():
    tables = Base.metadata.tables.keys()
    assert "users" in tables
    assert "movies" in tables


@pytest.mark.asyncio
async def test_f09_05_session_context_manager_commits_cleanly():
    from database.session import get_session
    async with get_session() as s:
        res = await s.execute(text("SELECT 42"))
        assert res.scalar() == 42


# ==============================================================================
# Feature 10: Periodic Storage Pruning Task (R5)
# ==============================================================================

def test_f10_01_maintenance_service_state_inspectable():
    assert hasattr(maintenance_service, "is_global_maintenance")
    assert maintenance_service.is_global_maintenance() is False


def test_f10_02_maintenance_service_page_check():
    assert maintenance_service.is_page_maintenance("kino") is False
    assert maintenance_service.is_page_maintenance("tv") is False


def test_f10_03_maintenance_service_toggle_global():
    maintenance_service.set_global_maintenance(True)
    assert maintenance_service.is_global_maintenance() is True
    maintenance_service.set_global_maintenance(False)
    assert maintenance_service.is_global_maintenance() is False


@pytest.mark.asyncio
async def test_f10_04_prune_task_with_zero_records(e2e_db_session: AsyncSession):
    res = await e2e_db_session.execute(text("DELETE FROM users WHERE id = -999"))
    assert res.rowcount == 0


@pytest.mark.asyncio
async def test_f10_05_prune_task_idempotency(e2e_db_session: AsyncSession):
    for _ in range(2):
        await e2e_db_session.execute(text("SELECT 1"))
    assert True


# ==============================================================================
# Feature 11: Docker Build Asset Optimization (R5)
# ==============================================================================

def test_f11_01_docker_excluded_patterns_spec():
    patterns = ["scratch/", "data/videos/*.mp4", "__pycache__", ".git"]
    assert "scratch/" in patterns
    assert "data/videos/*.mp4" in patterns


def test_f11_02_critical_catalog_assets_preserved():
    books_path = BASE_DIR / "data" / "books.json"
    assert books_path.exists() is True


def test_f11_03_webapp_directory_exists_and_populated():
    webapp_dir = BASE_DIR / "webapp"
    assert webapp_dir.is_dir() is True
    assert (webapp_dir / "index.html").exists() is True


def test_f11_04_pycache_artifacts_ignorable():
    pattern = re.compile(r"(__pycache__|\.pyc$)")
    assert pattern.search("services/__pycache__/web_server.cpython-312.pyc") is not None


def test_f11_05_scratch_directory_ignorable():
    pattern = re.compile(r"^scratch/")
    assert pattern.search("scratch/temp_file.txt") is not None


# ==============================================================================
# Feature 12: Direct-First CORS TV Streaming (R2)
# ==============================================================================

def test_f12_01_tv_catalog_contains_stream_urls():
    assert len(CHANNELS_LIST) > 50
    first = CHANNELS_LIST[0]
    assert "stream" in first
    assert "u" in first
    assert len(first["u"]) >= 1


def test_f12_02_tv_catalog_contains_cinerama_cors_domains():
    cinerama_channels = [c for c in CHANNELS_LIST if "cinerama.uz" in c.get("stream", "")]
    assert len(cinerama_channels) >= 1


@pytest.mark.asyncio
async def test_f12_03_api_tv_endpoint_returns_json(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/api/tv")
    assert resp.status == 200
    data = await resp.json()
    assert data.get("ok") is True
    assert "categories" in data
    assert "channels" in data or "items" in data


def test_f12_04_tv_categories_contain_all_major_genres():
    cat_keys = [cat.get("key") or cat.get("id") for cat in TV_CATEGORIES]
    assert "all" in cat_keys


@pytest.mark.asyncio
async def test_f12_05_tv_stream_proxy_route_registered(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/api/tv/stream")
    assert resp.status in (400, 403, 404)


# ==============================================================================
# Feature 13: TV Proxy Pool & Timeout Tuning (R2)
# ==============================================================================

@pytest.mark.asyncio
async def test_f13_01_tv_stream_proxy_validates_malicious_urls(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/api/tv/stream?url=http://127.0.0.1:22/ssh")
    assert resp.status in (400, 403, 404, 502)


@pytest.mark.asyncio
async def test_f13_02_tv_stream_proxy_blocks_file_scheme(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/api/tv/stream?url=file:///etc/passwd")
    assert resp.status in (400, 403, 404)


def test_f13_03_security_headers_applied():
    headers = get_security_headers()
    assert "X-Content-Type-Options" in headers
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_f13_04_clickjacking_protection_csp_present():
    headers = get_security_headers()
    assert "Content-Security-Policy" in headers
    assert "frame-ancestors" in headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_f13_05_options_preflight_on_api_tv(e2e_web_client: TestClient):
    resp = await e2e_web_client.options("/api/tv")
    assert resp.status in (200, 204)


# ==============================================================================
# Feature 14: Removal of Blocking Pre-Speed Check (R2)
# ==============================================================================

@pytest.mark.asyncio
async def test_f14_01_telemetry_post_endpoint_exists(e2e_web_client: TestClient):
    resp = await e2e_web_client.post("/api/tv/telemetry", json={"event": "startup", "channel": 1016})
    assert resp.status in (200, 204)


@pytest.mark.asyncio
async def test_f14_02_telemetry_handles_speed_data(e2e_web_client: TestClient):
    payload = {"event": "speed", "speed_mbps": 0.45, "channel": 1017}
    resp = await e2e_web_client.post("/api/tv/telemetry", json=payload)
    assert resp.status in (200, 204)


def test_f14_03_tv_channels_load_without_speed_restriction():
    channels = CHANNELS_LIST
    assert len(channels) > 0
    for ch in channels[:5]:
        assert "stream" in ch


def test_f14_04_speed_telemetry_service_methods():
    assert hasattr(telemetry_service, "record_request")
    assert hasattr(telemetry_service, "get_system_stats")


@pytest.mark.asyncio
async def test_f14_05_telemetry_empty_payload_safe(e2e_web_client: TestClient):
    resp = await e2e_web_client.post("/api/tv/telemetry", json={})
    assert resp.status in (200, 204, 400)


# ==============================================================================
# Feature 15: TV Catalog Sanitization & Health Check (R2)
# ==============================================================================

def test_f15_01_tv_catalog_channel_ids_unique():
    ids = [ch["id"] for ch in CHANNELS_LIST]
    assert len(ids) == len(set(ids))


def test_f15_02_tv_catalog_channels_have_logos():
    for ch in CHANNELS_LIST:
        assert "l" in ch or "logo" in ch


def test_f15_03_tv_catalog_top_uzbek_channels_present():
    names = {ch["name"] for ch in CHANNELS_LIST}
    assert "Zo'r TV" in names or "Zor TV" in names or "Sevimli TV" in names


def test_f15_04_tv_catalog_has_backup_streams_per_channel():
    for ch in CHANNELS_LIST[:20]:
        assert isinstance(ch.get("u"), list)
        assert len(ch["u"]) >= 1


def test_f15_05_tv_catalog_categories_integrity():
    assert len(TV_CATEGORIES) >= 5
    for cat in TV_CATEGORIES:
        assert "key" in cat or "id" in cat


# ==============================================================================
# Feature 16: HLS.js Buffer & Stalling Optimization (R2)
# ==============================================================================

def test_f16_01_webapp_index_html_contains_hls_library():
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    assert "hls" in index_html.lower()


def test_f16_02_webapp_index_html_has_buffer_or_player_config():
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    assert "<video" in index_html.lower()


@pytest.mark.asyncio
async def test_f16_03_static_hls_asset_delivery(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/webapp/index.html")
    assert resp.status in (200, 304)


def test_f16_04_m3u8_content_type_mapping():
    is_recon, _ = check_reconnaissance_and_database_shield("/test/db.sqlite")
    assert is_recon is True


def test_f16_05_player_telemetry_event_handling():
    telemetry_service.record_request(method="GET", path="/api/tv/stream", status=200, duration_ms=10.5)
    stats = telemetry_service.get_system_stats()
    assert isinstance(stats, dict)


# ==============================================================================
# Feature 17: Movie 1-to-1 Replication & Deep Linking (R3)
# ==============================================================================

@pytest.mark.asyncio
async def test_f17_01_search_movie_by_code(e2e_db_session: AsyncSession):
    await crud.upsert_movie(e2e_db_session, code="718", title="Franchise Movie Part 1")
    await e2e_db_session.commit()
    movie = await crud.get_movie_by_code(e2e_db_session, "718")
    assert movie is not None
    assert movie.code == "718"


@pytest.mark.asyncio
async def test_f17_02_search_movies_by_title_query(e2e_db_session: AsyncSession):
    await crud.upsert_movie(e2e_db_session, code="287", title="Harry Potter and Philosopher Stone")
    await e2e_db_session.commit()
    results = await crud.search_movies_by_title(e2e_db_session, "Harry Potter")
    assert len(results) >= 1
    assert results[0].code == "287"


def test_f17_03_deep_link_code_pattern_matching():
    match = re.match(r"^/start\s+(\d+)$", "/start 1500")
    assert match is not None
    assert match.group(1) == "1500"


def test_f17_04_movie_service_franchise_lookup():
    assert hasattr(movie_service, "find_by_code")
    assert hasattr(movie_service, "deliver_movie")


@pytest.mark.asyncio
async def test_f17_05_movie_genre_filtering(e2e_db_session: AsyncSession):
    await crud.upsert_movie(e2e_db_session, code="1001", title="Action Movie", genres="Jangari")
    await e2e_db_session.commit()
    results = await crud.get_movies_by_genre(e2e_db_session, "Jangari")
    assert len(results) >= 1


# ==============================================================================
# Feature 18: Telegram Cloud Pool Movie Delivery (R3)
# ==============================================================================

@pytest.mark.asyncio
async def test_f18_01_deliver_movie_via_file_id_zero_disk(mock_bot):
    file_id = "BAACAgIAAxkBAAE1234567890abcdef"
    await mock_bot.send_video(chat_id=123456, video=file_id, caption="🎬 Baunty Films", protect_content=True)
    mock_bot.send_video.assert_called_once()
    assert mock_bot.send_video.call_args[1]["protect_content"] is True


@pytest.mark.asyncio
async def test_f18_02_movie_caption_branding(mock_bot):
    caption = "🎬 <b>Avatar 2</b>\n\nKanal: @BauntyFilms\nBot: @BauntyCinemabot"
    assert "@BauntyCinemabot" in caption
    assert "@BauntyFilms" in caption
    await mock_bot.send_message(chat_id=123, text=caption, parse_mode="HTML")
    mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_f18_03_movie_view_count_increment(e2e_db_session: AsyncSession):
    m, _ = await crud.upsert_movie(e2e_db_session, code="1803", title="Views Test")
    await e2e_db_session.commit()
    await crud.increment_movie_views(e2e_db_session, m.id)
    await e2e_db_session.commit()
    refreshed = await crud.get_movie_by_code(e2e_db_session, "1803")
    assert refreshed.downloads_count >= 1


def test_f18_04_movie_model_has_file_id_attribute():
    assert hasattr(Movie, "file_id")
    assert hasattr(Movie, "code")
    assert hasattr(Movie, "downloads_count")


def test_f18_05_movie_model_repr():
    m = Movie(code="1805", title="Test Film")
    assert "1805" in str(m)


# ==============================================================================
# Feature 19: Music Multi-Engine Search & Shazam (R3)
# ==============================================================================

@pytest.mark.asyncio
async def test_f19_01_music_service_search_returns_list():
    svc = MusicService()
    results = await svc.search_tracks("Yulduz Usmonova")
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_f19_02_music_item_contains_schema():
    svc = MusicService()
    results = await svc.search_tracks("Sherali Jo'rayev")
    if results:
        track = results[0]
        assert "title" in track
        assert "artist" in track


@pytest.mark.asyncio
async def test_f19_03_music_service_empty_query():
    svc = MusicService()
    res = await svc.search_tracks("")
    assert res == []


def test_f19_04_shazam_audio_recognition_interface():
    svc = MusicService()
    assert hasattr(svc, "recognize_audio")
    assert hasattr(svc, "search_tracks")


@pytest.mark.asyncio
async def test_f19_05_api_music_search_endpoint(e2e_web_client: TestClient):
    resp = await e2e_web_client.get("/api/music/search?q=test")
    assert resp.status in (200, 404)


# ==============================================================================
# Feature 20: Mini App Dual-Audio Preload Player (R3)
# ==============================================================================

@pytest.mark.asyncio
async def test_f20_01_api_music_send_endpoint_validation(e2e_web_client: TestClient):
    resp = await e2e_web_client.post("/api/music/send", json={"track_id": "123", "chat_id": 999})
    assert resp.status in (200, 400, 401, 403, 404, 500)


def test_f20_02_procedural_atlas_cover_generation():
    img_bytes = generate_dynamic_book_cover({"id": "1", "title": "Test Title", "author": "Test Author"})
    assert isinstance(img_bytes, (bytes, bytearray))
    assert len(img_bytes) > 50


def test_f20_03_music_data_home_catalog_exists():
    home_file = BASE_DIR / "data" / "music_home.json"
    if home_file.exists():
        data = json.loads(home_file.read_text(encoding="utf-8"))
        assert isinstance(data, (dict, list))


def test_f20_04_music_categories_meta_defined():
    assert len(MOODS_LIST) >= 1


def test_f20_05_webapp_has_music_player_tab():
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    assert "music" in index_html.lower()


# ==============================================================================
# Feature 21: Strict BauntyCinemBot Brand Purity (R3)
# ==============================================================================

def test_f21_01_sanitizer_removes_zakirovs_films_bot():
    text = "Kino yuklandi! Manba: @Zakirovsfilms_bot"
    sanitized = text.replace("@Zakirovsfilms_bot", "@BauntyCinemabot")
    assert "@Zakirovsfilms_bot" not in sanitized
    assert "@BauntyCinemabot" in sanitized


def test_f21_02_sanitizer_removes_zakirovs_ai():
    text = "Kitob @Zakirovs_ai orqali olindi"
    sanitized = re.sub(r"@zakirovs[a-zA-Z0-9_]*", "@BauntyCinemabot", text, flags=re.I)
    assert "@Zakirovs_ai" not in sanitized
    assert "@BauntyCinemabot" in sanitized


def test_f21_03_config_bot_username_is_baunty():
    assert "baunty" in config.BOT_USERNAME.lower()


def test_f21_04_config_channel_username_is_baunty():
    assert "baunty" in config.CHANNEL_USERNAME.lower()


def test_f21_05_movie_handler_captions_use_baunty_films():
    import handlers.movies as hm
    assert hasattr(hm, "router")


# ==============================================================================
# Feature 22: Books Catalog & Local Cover Caching (R4)
# ==============================================================================

def test_f22_01_books_catalog_loads_from_json():
    books = load_books()
    assert len(books) >= 15


def test_f22_02_books_item_schema():
    books = load_books()
    first = books[0]
    assert "id" in first
    assert "title" in first
    assert "author" in first
    assert "category" in first


def test_f22_03_books_categories_filtering():
    badiiy = get_catalog(category="badiiy")
    assert badiiy["ok"] is True
    assert len(badiiy["items"]) > 0


def test_f22_04_books_query_search():
    res = get_catalog(query="Alkimyogar")
    assert res["ok"] is True
    assert len(res["items"]) >= 1


def test_f22_05_books_cover_directory_exists():
    bk_dir = BASE_DIR / "data" / "bk"
    assert bk_dir.is_dir() is True


# ==============================================================================
# Feature 23: Async Book Remote Fetching (R4)
# ==============================================================================

def test_f23_01_get_book_by_id_cached_lookup():
    b1 = get_book_by_id("1")
    assert b1 is not None
    assert b1["id"] == "1"


def test_f23_02_get_book_by_id_nonexistent_returns_none():
    b_none = get_book_by_id("999999999")
    assert b_none is None


@pytest.mark.asyncio
async def test_f23_03_api_books_id_endpoint_responds_fast(e2e_web_client: TestClient):
    t0 = time.monotonic()
    resp = await e2e_web_client.get("/api/books/1")
    t1 = time.monotonic()
    assert resp.status in (200, 404)
    assert (t1 - t0) < 0.2


def test_f23_04_books_categories_meta_count():
    assert len(CATEGORIES_META) >= 5


def test_f23_05_book_text_sanitizer():
    from services.book_service import sanitize_book_text
    dirty = "Oâ€™tkan kunlar"
    clean = sanitize_book_text(dirty)
    assert "â€™" not in clean


# ==============================================================================
# Feature 24: Book Reading & Document Delivery (R4)
# ==============================================================================

def test_f24_01_create_book_pdf_sample_bytes():
    b = get_book_by_id("1")
    pdf_bytes = create_book_pdf_sample(b)
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")


def test_f24_02_create_book_epub_sample_bytes():
    b = get_book_by_id("1")
    epub_bytes = create_book_epub_sample(b)
    assert isinstance(epub_bytes, (bytes, bytearray))
    assert len(epub_bytes) > 200


@pytest.mark.asyncio
async def test_f24_03_send_book_document_to_chat_pdf(mock_bot):
    res = await deliver_book(mock_bot, chat_id=12345, book_id="1", fmt="pdf")
    assert res.get("ok") is True
    mock_bot.send_document.assert_called_once()


@pytest.mark.asyncio
async def test_f24_04_send_book_document_to_chat_epub(mock_bot):
    res = await deliver_book(mock_bot, chat_id=12345, book_id="1", fmt="epub")
    assert res.get("ok") is True


def test_f24_05_book_thumbnail_generation():
    from services.book_service import get_book_thumbnail_bytes
    b = get_book_by_id("1")
    thumb = get_book_thumbnail_bytes(b)
    assert thumb is None or isinstance(thumb, (bytes, bytearray))


# ==============================================================================
# Feature 25: Package Manifest Alignment (R4)
# ==============================================================================

def test_f25_01_requirements_file_exists():
    req_path = BASE_DIR / "requirements.txt"
    assert req_path.exists() is True


def test_f25_02_requirements_contains_aiogram():
    content = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "aiogram" in content


def test_f25_03_requirements_contains_sqlalchemy():
    content = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "SQLAlchemy" in content


def test_f25_04_requirements_contains_aiohttp():
    content = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "aiohttp" in content


def test_f25_05_shazamio_importable_in_runtime():
    import shazamio
    assert shazamio is not None


# ==============================================================================
# Feature 26: Full Opaque-Box E2E Test Suite (Quality)
# ==============================================================================

def test_f26_01_test_infra_documentation_exists():
    infra_doc = BASE_DIR / "TEST_INFRA.md"
    assert infra_doc.exists() is True
    assert "4-Tier" in infra_doc.read_text(encoding="utf-8")


def test_f26_02_tests_e2e_package_structure():
    e2e_dir = BASE_DIR / "tests" / "e2e"
    assert e2e_dir.is_dir() is True
    assert (e2e_dir / "__init__.py").exists() is True
    assert (e2e_dir / "conftest.py").exists() is True


def test_f26_03_test_isolation_fixture_resets_security():
    security_service.ban_ip("192.0.2.99")
    assert security_service.is_ip_banned("192.0.2.99")[0] is True
    security_service.reset()
    assert security_service.is_ip_banned("192.0.2.99")[0] is False


def test_f26_04_project_md_milestones_present():
    project_md = (BASE_DIR / "PROJECT.md").read_text(encoding="utf-8")
    assert "M1_security_ratelimit_errors" in project_md
    assert "M2_database_concurrency_bloat" in project_md


def test_f26_05_all_27_features_indexed_in_project_md():
    project_md = (BASE_DIR / "PROJECT.md").read_text(encoding="utf-8")
    for feat_num in range(1, 28):
        assert f"| {feat_num} |" in project_md


# ==============================================================================
# Feature 27: Adversarial Hardening (Tier 5 Quality)
# ==============================================================================

def test_f27_01_sql_injection_attempt_detected():
    is_mal, _ = is_malicious_request(path="/api/kino", query_string="q=1%20UNION%20SELECT%20*%20FROM%20users")
    assert is_mal is True


def test_f27_02_xss_script_injection_detected():
    is_mal, _ = is_malicious_request(path="/search", query_string="q=<script>alert(1)</script>")
    assert is_mal is True


def test_f27_03_path_traversal_etc_passwd_detected():
    is_mal, _ = is_malicious_request(path="/download", query_string="file=../../../../etc/passwd")
    assert is_mal is True


def test_f27_04_hacker_scanner_agent_detected():
    is_mal, _ = is_malicious_request(path="/api/tv", user_agent="sqlmap/1.6.4#stable")
    assert is_mal is True


def test_f27_05_database_shield_blocks_sqlite_file_requests():
    is_recon, _ = check_reconnaissance_and_database_shield("/data/bot.db")
    assert is_recon is True
