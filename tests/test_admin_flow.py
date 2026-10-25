"""
Bauntys Admin Flow & Database Telemetry Test Suite
==================================================
Tests for:
1. GET /admin/flow and GET /webapp/admin/flow UI page delivery and branding.
2. GET /api/admin/flow/data and aliases telemetry JSON structure.
3. Real-time Neon PostgreSQL / SQLite health check, ping ms, and 6 table row counts.
4. Live request flow recording via telemetry_middleware.
5. DB Benchmark execution endpoint POST /api/admin/flow/benchmark.
6. Clear logs endpoint POST /api/admin/flow/clear.
7. Security bypass: Scanner user-agents, empty UA, and IP jail bypass for /admin/flow.
8. Database error handling resilience.
"""
import pytest
import time
from unittest.mock import patch, AsyncMock
from aiohttp.test_utils import TestServer, TestClient
from services.web_server import create_web_app
from services.telemetry_service import telemetry_service, get_process_memory_mb
from services.security_service import security_service, is_malicious_request


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_admin_flow_html_page_delivery():
    """GET /admin/flow va /webapp/admin/flow 200 OK va to'liq brendlangan HTML qaytarishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        for path in ("/admin/flow", "/webapp/admin/flow"):
            resp = await client.get(path)
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")
            text = await resp.text()

            # Branding va muhim elementlar tekshiruvi
            assert "BAUNTYS FLOW" in text
            assert "@Bauntyfilmsbot" in text
            assert "@BauntyFilms" in text
            assert "movies" in text
            assert "users" in text
            assert "downloads" in text
            assert "expenses" in text
            assert "calories" in text
            assert "mafia_games" in text
            assert "Test DB Query (Benchmark)" in text
            assert "STREAMING" in text
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_admin_flow_telemetry_data_endpoint():
    """GET /api/admin/flow/data to'liq tuzilmali JSON telemetriya qaytarishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        for path in ("/api/admin/flow/data", "/webapp/api/admin/flow/data"):
            resp = await client.get(path)
            assert resp.status == 200
            data = await resp.json()

            assert data["ok"] is True

            # Server bo'limi
            server_info = data["server"]
            assert "Bauntys" in server_info["name"]
            assert server_info["bot_username"] == "@Bauntyfilmsbot"
            assert server_info["channel_username"] == "@BauntyFilms"
            assert server_info["uptime_seconds"] >= 0
            assert "memory_mb" in server_info
            assert "python_version" in server_info

            # Database bo'limi
            db_info = data["database"]
            assert db_info["status"] in ("ONLINE", "DEGRADED", "OFFLINE")
            assert "ping_ms" in db_info
            assert "engine" in db_info
            assert "pool_status" in db_info

            # 6 ta asosiy jadval hisobi
            counts = db_info["table_counts"]
            for table_name in ("users", "movies", "downloads", "expenses", "calories", "mafia_games"):
                assert table_name in counts
                assert isinstance(counts[table_name], int)
            assert counts["total_records"] >= 0

            # Trafik bo'limi
            traffic = data["traffic"]
            assert "total_requests" in traffic
            assert "rpm" in traffic
            assert "success_rate" in traffic
            assert "avg_latency_ms" in traffic
            assert "errors_4xx" in traffic
            assert "errors_5xx" in traffic
            assert "status_distribution" in traffic

            # So'rovlar buferi
            assert isinstance(data["recent_requests"], list)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_admin_flow_benchmark_and_clear_endpoints():
    """POST /api/admin/flow/benchmark va /clear endpointlari to'g'ri ishlashi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Benchmark testi
        resp_bm = await client.post("/api/admin/flow/benchmark")
        assert resp_bm.status == 200
        data_bm = await resp_bm.json()
        assert data_bm["ok"] is True
        assert data_bm["status"] == "ONLINE"
        assert data_bm["ping_ms"] >= 0

        # 2. Clear buffer testi
        resp_clear = await client.post("/api/admin/flow/clear")
        assert resp_clear.status == 200
        data_clear = await resp_clear.json()
        assert data_clear["ok"] is True
        assert data_clear["message"] == "Buffer cleared"

        # So'ngra telemetriya olinganda recent_requests tozalangan yoki minimal (faqat clear/data) bo'lishi
        resp_data = await client.get("/api/admin/flow/data")
        assert resp_data.status == 200
        data_data = await resp_data.json()
        assert len(data_data["recent_requests"]) <= 2
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_telemetry_middleware_records_live_traffic():
    """Serverga kelgan har qanday so'rov telemetriya ring buferiga yozilishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        telemetry_service.clear_buffer()

        # Bir nechta turli so'rovlar yuborish
        await client.get("/ping")
        await client.get("/health")
        await client.get("/api/catalog")

        # Telemetriyani tekshirish
        resp = await client.get("/api/admin/flow/data")
        assert resp.status == 200
        data = await resp.json()

        paths = [r["path"] for r in data["recent_requests"]]
        assert any("/ping" in p for p in paths)
        assert any("/health" in p for p in paths)
        assert any("/api/catalog" in p for p in paths)

        # Har bir yozuvda kerakli parametrlar mavjudligi
        record = data["recent_requests"][0]
        assert "method" in record
        assert "path" in record
        assert "status" in record
        assert "duration_ms" in record
        assert "client_ip" in record
        assert "user_agent" in record
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_admin_flow_security_waf_and_scanner_bypass():
    """
    /admin/flow va /api/admin/flow skanerlar (curl, python-requests, ffuf, nikto)
    va bo'sh User-Agent tomonidan ochilganda ham 403 bilan to'silmasligi kerak.
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    scanner_agents = [
        "curl/7.88.1",
        "Wget/1.21.3",
        "python-requests/2.31.0",
        "PostmanRuntime/7.32.0",
        "nikto/2.1.6",
        "sqlmap/1.7#stable",
    ]

    try:
        for ua in scanner_agents:
            headers = {"User-Agent": ua}
            # Oddiy API yo'li bloklanadi (masalan /api/movies yoki /api/catalog)
            resp_blocked = await client.get("/api/movies", headers=headers)
            assert resp_blocked.status == 403, f"Oddiy yo'l {ua} uchun bloklanishi kerak edi"

            # /admin/flow esa to'siqsiz 200 OK qaytarishi shart!
            resp_flow = await client.get("/admin/flow", headers=headers)
            assert resp_flow.status == 200, f"/admin/flow {ua} uchun ruxsat berilishi shart"

            # /api/admin/flow/data ham to'siqsiz 200 OK qaytarishi shart!
            resp_data = await client.get("/api/admin/flow/data", headers=headers)
            assert resp_data.status == 200, f"/api/admin/flow/data {ua} uchun ruxsat berilishi shart"

        # Bo'sh User-Agent bilan ham /admin/flow va /api/admin/flow/data 200 OK qaytarishi shart
        empty_headers = {"User-Agent": ""}
        resp_flow_empty = await client.get("/admin/flow", headers=empty_headers)
        assert resp_flow_empty.status == 200
        resp_data_empty = await client.get("/api/admin/flow/data", headers=empty_headers)
        assert resp_data_empty.status == 200
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_admin_flow_unbans_jailed_ip():
    """Qamoqqa (Auto-Ban Jail) tushgan administrator IP manzili /admin/flow ga kirganda avtomatik unban bo'lishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    admin_ip = "198.51.100.99"
    try:
        # IP ni sun'iy ravishda ban qilish
        security_service.ban_ip(admin_ip, reason="test_violation")
        assert security_service.is_ip_banned(admin_ip)[0] is True

        # Ushbu IP dan /admin/flow ga so'rov yuborish
        headers = {"X-Forwarded-For": admin_ip, "User-Agent": "Mozilla/5.0"}
        resp = await client.get("/admin/flow", headers=headers)
        assert resp.status == 200

        # IP unban qilinganligini tekshirish
        assert security_service.is_ip_banned(admin_ip)[0] is False
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_database_health_graceful_error_handling():
    """Ma'lumotlar bazasi uzilganda OFFLINE (-1 ms), jadval xatosida esa DEGRADED qaytarishi kerak."""
    # 1. Connection failure -> OFFLINE and ping_ms == -1.0
    with patch("services.telemetry_service.get_session") as mock_session_ctx:
        mock_session_ctx.side_effect = Exception("Database connection timeout")

        result = await telemetry_service.check_database_health()
        assert result["status"] == "OFFLINE"
        assert result["ping_ms"] == -1.0
        assert "Database connection timeout" in result["error"]

        # get_full_telemetry ham qulab tushmasligi kerak
        full = await telemetry_service.get_full_telemetry()
        assert full["ok"] is True
        assert full["database"]["status"] == "OFFLINE"
        assert full["database"]["ping_ms"] == -1.0


def test_is_malicious_request_admin_flow_bypass():
    """is_malicious_request funksiyasi /admin/flow yo'llarini skanerlardan o'tkazishi, lekin path traversalni to'sishi kerak."""
    # Oddiy admin dashboard skaner UA bilan o'tishi kerak
    is_mal, threat = is_malicious_request("/admin/flow", user_agent="sqlmap/1.0")
    assert is_mal is False
    assert threat is None

    is_mal2, threat2 = is_malicious_request("/api/admin/flow/data", user_agent="curl/7.0")
    assert is_mal2 is False
    assert threat2 is None

    # Path traversal urinishlari esa qat'iy to'silishi shart!
    is_mal_traversal, threat_traversal = is_malicious_request("/admin/flow/../../bot.db")
    assert is_mal_traversal is True
    assert threat_traversal == "path_traversal"


@pytest.mark.asyncio
async def test_admin_flow_bot_command_and_health_integration():
    """Telegram bot /flow buyrug'i va admin:server:health tugmasi to'g'ri ishlashi kerak."""
    from unittest.mock import MagicMock
    from aiogram.types import Message, CallbackQuery, User
    from handlers.admin import cmd_admin_flow, cb_admin_server_health

    # 1. /flow buyrug'i
    msg = MagicMock(spec=Message)
    msg.from_user = User(id=99999999, is_bot=False, first_name="Admin")
    msg.answer = AsyncMock()
    msg.reply = AsyncMock()

    with patch("handlers.admin.is_admin_check", return_value=True):
        await cmd_admin_flow(msg)
        msg.answer.assert_called_once()
        flow_text = msg.answer.call_args[0][0]
        assert "Bauntys Flow & Database Live Monitor" in flow_text
        assert "/admin/flow" in flow_text

    # 2. admin:server:health callback
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = User(id=99999999, is_bot=False, first_name="Admin")
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()

    with patch("handlers.admin.is_admin_check", return_value=True), \
         patch("handlers.admin.get_session") as mock_sess, \
         patch("database.crud.get_total_users_count", new_callable=AsyncMock, return_value=100), \
         patch("database.crud.get_total_movies_count", new_callable=AsyncMock, return_value=50), \
         patch("database.crud.get_total_downloads_count", new_callable=AsyncMock, return_value=300):
        mock_s = AsyncMock()
        mock_sess.return_value.__aenter__.return_value = mock_s
        await cb_admin_server_health(cb)
        cb.message.edit_text.assert_called_once()
        health_text = cb.message.edit_text.call_args[0][0]
        # Ham avvalgi testlar talab qilgan matn, ham yangi flow havolasi bo'lishi shart!
        assert "Server va Tizim Salomatligi" in health_text
        assert "/admin/flow" in health_text

