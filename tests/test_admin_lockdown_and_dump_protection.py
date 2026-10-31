"""
Tests for Admin Lockdown, Cryptographic Verification, Anti-Dump & TV Connection
==============================================================================
1. Admin Panel & Flow Lockdown:
   - Direct unauthenticated access (curl / cmd / browser) to /admin/flow, /webapp/admin/flow,
     /api/admin/flow/data, /api/admin/maintenance returns HTTP 403 Forbidden.
   - Forged user_id without HMAC signature returns HTTP 403 Forbidden.
   - Genuine Telegram initData signed by BOT_TOKEN for an admin returns 200 OK + session cookie.
   - Admin Vault Key (X-Admin-Key) returns 200 OK.
   - Non-admin initData returns 403 Forbidden.
2. Anti-Database Dump & Schema Reconnaissance:
   - Queries containing sqlite_master, sqlite_schema, pg_catalog, pg_dump, mysqldump
     are intercepted by WAF and return 403 Forbidden.
   - Requests targeting *.db, *.sqlite, *.sql, *.bak, *.dump, *.env return 403 Forbidden.
3. Information Disclosure & Health Sanitization:
   - /health and /status return only minimal status/timestamp with zero port or bot name leaks.
   - Admin routes never return wildcard CORS (Access-Control-Allow-Origin: *).
4. TV Connection Optimization:
   - tvroom.js Hls config has lowLatencyMode: false, startFragPrefetch: true, and balanced timeouts.
"""
import pytest
import time
import re
from unittest.mock import patch
from aiohttp.test_utils import TestServer, TestClient
from config import config
from services.web_server import create_web_app
from services.security_service import (
    generate_telegram_init_data,
    get_admin_vault_key,
    create_admin_session_token,
    verify_admin_session_token,
    is_malicious_request,
    check_reconnaissance_and_database_shield,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_admin_flow_strict_unauthenticated_blocked():
    """Unauthenticated access to /admin/flow and /api/admin/* must strictly return 403 Forbidden."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Strict mode flag to simulate production external request without pytest auto-bypass
        headers = {"X-Require-Strict-Admin": "1", "User-Agent": "curl/8.4.0"}

        # 1. UI endpoints
        for p in ("/admin/flow", "/webapp/admin/flow", "/admin_flow.html", "/webapp/admin_flow.html"):
            resp = await client.get(p, headers=headers)
            assert resp.status == 403, f"{p} must return 403 for unauthenticated curl"
            body = await resp.text()
            assert "403" in body

        # 2. API endpoints
        resp_data = await client.get("/api/admin/flow/data", headers=headers)
        assert resp_data.status == 403

        resp_bench = await client.post("/api/admin/flow/benchmark", headers=headers)
        assert resp_bench.status == 403

        resp_clear = await client.post("/api/admin/flow/clear", headers=headers)
        assert resp_clear.status == 403

        resp_maint = await client.post("/api/admin/maintenance", headers=headers, json={"action": "toggle_global"})
        assert resp_maint.status == 403

        # 3. Forged user_id without cryptographic signature must also return 403
        resp_spoofed = await client.get("/admin/flow?user_id=881122", headers=headers)
        assert resp_spoofed.status == 403

        resp_spoofed_hdr = await client.get("/admin/flow", headers={"X-Require-Strict-Admin": "1", "X-User-Id": "881122"})
        assert resp_spoofed_hdr.status == 403
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_admin_flow_cryptographic_auth_success():
    """Admin access with genuine HMAC initData or X-Admin-Key must succeed with 200 OK."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        admin_id = 881122
        with patch.object(type(config), "is_admin", side_effect=lambda *args, **kwargs: args[-1] == admin_id if args else False):
            # 1. Genuine Telegram initData with HMAC-SHA256 signature
            valid_init_data = generate_telegram_init_data(
                user_data={"id": admin_id, "first_name": "Boss"},
                bot_token=config.BOT_TOKEN
            )

            # Test via header
            auth_headers = {
                "X-Telegram-Init-Data": valid_init_data,
                "X-Require-Strict-Admin": "1"
            }
            resp = await client.get("/admin/flow", headers=auth_headers)
            assert resp.status == 200
            text = await resp.text()
            assert "BAUNTYS FLOW" in text
            assert "baunty_admin_session" in resp.cookies

            # Test API via header
            resp_api = await client.get("/api/admin/flow/data", headers=auth_headers)
            assert resp_api.status == 200
            data = await resp_api.json()
            assert data.get("ok") is True

            # 2. Test via Admin Vault Key (for CLI / CMD / automated scripts)
            vault_key = get_admin_vault_key()
            key_headers = {
                "X-Admin-Key": vault_key,
                "X-Require-Strict-Admin": "1"
            }
            resp_key = await client.get("/admin/flow", headers=key_headers)
            assert resp_key.status == 200

            resp_key_maint = await client.post(
                "/api/admin/maintenance",
                headers=key_headers,
                json={"action": "get"}
            )
            assert resp_key_maint.status == 200

            # 3. Test signed session cookie
            sess_token = create_admin_session_token(admin_id)
            ok, uid = verify_admin_session_token(sess_token)
            assert ok is True
            assert uid == admin_id

            cookie_headers = {
                "Cookie": f"baunty_admin_session={sess_token}",
                "X-Require-Strict-Admin": "1"
            }
            resp_cookie = await client.get("/api/admin/flow/data", headers=cookie_headers)
            assert resp_cookie.status == 200

            # 4. Non-admin user initData must be rejected with 403
            non_admin_init = generate_telegram_init_data(
                user_data={"id": 1122334455, "first_name": "Intruder"},
                bot_token=config.BOT_TOKEN
            )
            bad_headers = {
                "X-Telegram-Init-Data": non_admin_init,
                "X-Require-Strict-Admin": "1"
            }
            resp_bad = await client.get("/admin/flow", headers=bad_headers)
            assert resp_bad.status == 403
    finally:
        await client.close()


def test_anti_database_dump_patterns():
    """WAF must detect and block schema dumps, sqlite_master, pg_dump and database extraction attempts."""
    dump_queries = [
        ("UNION SELECT 1, sql FROM sqlite_master", "sql_injection"),
        ("SELECT * FROM sqlite_schema", "sql_injection"),
        ("SELECT tbl_name FROM sqlite_temp_master", "sql_injection"),
        ("SELECT * FROM pg_catalog.pg_tables", "sql_injection"),
        ("'; ATTACH DATABASE 'evil.db' AS evil;--", "sql_injection"),
        ("'; pg_dump baunty_db;--", "sql_injection"),
        ("'; mysqldump --all-databases;--", "sql_injection"),
        ("1' INTO OUTFILE '/var/www/dump.txt", "sql_injection"),
        ("1' INTO DUMPFILE '/tmp/dump.db", "sql_injection"),
    ]

    for q, expected_cat in dump_queries:
        is_mal, threat = is_malicious_request("/api/movies", query_string=f"q={q}")
        assert is_mal is True, f"Dump attack '{q}' was NOT detected by WAF!"

    # Nozik fayllar va bazalarni to'sish (check_reconnaissance_and_database_shield)
    protected_paths = [
        "/bot.db",
        "/baunty.db",
        "/bauntyfilms.db",
        "/data/bot.db",
        "/data/users.db",
        "/backup.sql",
        "/database.sqlite",
        "/db.sqlite3",
        "/dump.rdb",
        "/.env",
        "/config.json",
        "/../bot.db",
        "/webapp/../../bot.db",
    ]
    for p in protected_paths:
        is_blocked, reason = check_reconnaissance_and_database_shield(p)
        assert is_blocked is True, f"Path '{p}' was NOT blocked by database shield!"


@pytest.mark.asyncio
async def test_health_sanitization_and_no_wildcard_cors_on_admin():
    """Health check must be minimal with no port/bot leakage, and admin routes must not return CORS *."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Healthcheck response sanitization
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("status") == "ok"
        assert "timestamp" in data
        assert "bot" not in data, "bot username must NOT be leaked in health check"
        assert "port" not in data, "port must NOT be leaked in health check"
        assert "service" not in data, "internal service details must NOT be leaked"

        # 2. Admin routes should not return Access-Control-Allow-Origin: *
        admin_id = 881122
        with patch.object(type(config), "is_admin", side_effect=lambda *args, **kwargs: args[-1] == admin_id if args else False):
            key = get_admin_vault_key()
            headers = {"X-Admin-Key": key, "X-Require-Strict-Admin": "1"}
            resp_admin = await client.get("/api/admin/flow/data", headers=headers)
            assert resp_admin.status == 200
            cors = resp_admin.headers.get("Access-Control-Allow-Origin")
            assert cors != "*", f"Admin route must NEVER return wildcard CORS! Got: {cors}"
    finally:
        await client.close()


def test_tvroom_hls_configuration_stability():
    """tvroom.js and tv_room.js must have balanced HLS parameters (no ultra low-latency stall, quick retry)."""
    with open("webapp/tvroom.js", "r", encoding="utf-8") as f:
        content = f.read()

    assert "lowLatencyMode: false" in content, "lowLatencyMode must be false to prevent mobile stalling"
    assert "startFragPrefetch: true" in content, "startFragPrefetch must be true for fast startup"
    assert "manifestLoadingTimeOut: 5000" in content, "manifestLoadingTimeOut should be 5000ms"
    assert "manifestLoadingRetryDelay: 500" in content, "retry delay should be 500ms"
    assert "maxBufferSize: 30 * 1000 * 1000" in content, "buffer size should be capped at 30MB"
