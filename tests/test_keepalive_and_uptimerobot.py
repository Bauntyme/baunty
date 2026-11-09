"""
Test suite for UptimeRobot, Render Keep-Alive, Health Endpoints and Resilience.
Ensures zero-friction 200 OK responses for all legitimate probes, no false-positive rate-limiting,
and rigorous protection against malicious attacks.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp.test_utils import TestServer, TestClient
from services.web_server import create_web_app
from services.security_service import (
    security_service,
    FAST_MASTER_THREAT_REGEX,
    SlidingWindowRateLimiter,
    AutoBanJail,
    is_malicious_request,
    is_render_nat_ip,
)
from services.keepalive_service import TARGET_HEALTH_URLS
from middlewares.throttling import ThrottlingMiddleware
from middlewares.security import BotSecurityMiddleware
from aiogram.types import Message, CallbackQuery, User, Chat


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health_and_ping_endpoints_get_and_head():
    """Test /ping, /health, /status, /healthz with both GET and HEAD."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        for path in ("/ping", "/health", "/status", "/healthz"):
            # GET
            resp_get = await client.get(path)
            assert resp_get.status == 200, f"GET {path} failed with {resp_get.status}"
            if path == "/ping":
                text = await resp_get.text()
                assert "pong" in text
            else:
                data = await resp_get.json()
                assert data.get("status") == "ok"

            # HEAD
            resp_head = await client.head(path)
            assert resp_head.status == 200, f"HEAD {path} failed with {resp_head.status}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_uptimerobot_user_agents_on_root_and_health():
    """Test various UptimeRobot user-agent formats."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        uptimerobot_uas = [
            "Mozilla/5.0 (compatible; UptimeRobot/2.0; +http://www.uptimerobot.com/)",
            "Mozilla/5.0+(compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)",
            "UptimeRobot/2.0",
            "Mozilla/5.0 (compatible; UptimeRobot/2.0; BauntysKeepAlive/1.0; +http://www.uptimerobot.com/)",
            "BetterUptime/1.0",
            "Pingdom.com_bot_version_1.4_(http://www.pingdom.com/)",
            "Render/1.0 Healthcheck",
        ]

        for ua in uptimerobot_uas:
            headers = {"User-Agent": ua}
            # HEAD /
            resp_head_root = await client.head("/", headers=headers)
            assert resp_head_root.status == 200, f"HEAD / failed with UA {ua}"

            # GET /ping
            resp_ping = await client.get("/ping", headers=headers)
            assert resp_ping.status == 200, f"GET /ping failed with UA {ua}"

            # HEAD /health
            resp_health = await client.head("/health", headers=headers)
            assert resp_health.status == 200, f"HEAD /health failed with UA {ua}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_head_root_generic_browser_ua():
    """HEAD / should succeed with 200 OK regardless of User-Agent."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        generic_uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "",
        ]
        for ua in generic_uas:
            headers = {"User-Agent": ua} if ua else {}
            resp = await client.head("/", headers=headers)
            assert resp.status == 200, f"HEAD / failed with generic UA '{ua}'"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_rate_limiter_immunity_for_monitoring_probes():
    """Monitoring probes must not be rate-limited even under heavy bursts."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; UptimeRobot/2.0; +http://www.uptimerobot.com/)"}
        for i in range(40):
            resp = await client.head("/", headers=headers)
            assert resp.status == 200, f"Iteration {i} failed with status {resp.status}"

        for i in range(40):
            resp = await client.get("/ping", headers=headers)
            assert resp.status == 200, f"Iteration {i} of /ping failed with status {resp.status}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_jailed_ip_auto_unbanned_on_healthcheck():
    """If an IP was mistakenly jailed, a probe to /ping or /health automatically unbans it."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        test_ip = "198.51.100.88"
        security_service.ban_ip(test_ip, duration=300.0, reason="test_accidental_ban")
        is_jailed, _, _ = security_service.is_ip_banned(test_ip)
        assert is_jailed is True

        # Probe from jailed IP to /ping
        resp = await client.get("/ping", headers={"X-Forwarded-For": test_ip, "User-Agent": "UptimeRobot/2.0"})
        assert resp.status == 200

        # Verify IP is unbanned
        is_jailed_after, _, _ = security_service.is_ip_banned(test_ip)
        assert is_jailed_after is False
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_strong_security_still_blocks_malicious_queries_on_health_paths():
    """Even if an attacker sends an UptimeRobot UA, SQL injection on health paths is blocked."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; UptimeRobot/2.0; +http://www.uptimerobot.com/)"}
        malicious_urls = [
            "/health?q=1'%20OR%20'1'='1",
            "/ping?cmd=cat%20/etc/passwd",
            "/?id=1'%20UNION%20SELECT%20null--",
        ]
        for url in malicious_urls:
            resp = await client.get(url, headers=headers)
            assert resp.status == 403, f"Expected 403 for {url}, got {resp.status}"
    finally:
        await client.close()


def test_keepalive_target_urls_clean():
    """Ensure TARGET_HEALTH_URLS does not contain dead domains like baunty.onrender.com."""
    for url in TARGET_HEALTH_URLS:
        assert "baunty.onrender.com" not in url
        assert "baunty-cinema.onrender.com" in url or "127.0.0.1" in url


def test_rate_limiter_root_and_webapp_immunity():
    """SlidingWindowRateLimiter whitelists root, webapp, index.html, and favicon.ico without rate limiting."""
    limiter = SlidingWindowRateLimiter(burst_limit=10, burst_window=5.0)
    test_ip = "198.51.100.77"

    whitelisted_paths = ["/", "", "/webapp", "/webapp/", "/index.html", "/favicon.ico", "/webapp/index.html", "/health", "/ping"]
    for p in whitelisted_paths:
        for _ in range(25):
            allowed, retry_after = limiter.is_allowed(test_ip, path=p)
            assert allowed is True, f"Path '{p}' was unexpectedly rate limited!"
            assert retry_after is None

    # However, a non-whitelisted path from that IP should hit burst limit
    hit_limit = False
    for _ in range(15):
        allowed, _ = limiter.is_allowed(test_ip, path="/api/other_endpoint")
        if not allowed:
            hit_limit = True
            break
    assert hit_limit is True, "Non-whitelisted path should be subject to burst limit"


def test_automated_healthcheck_tools_on_probe_paths():
    """is_malicious_request allows automated monitors on health/root paths but blocks actual exploits."""
    probe_paths = ["/", "/health", "/ping", "/webapp", "/webapp/", "/index.html", "/favicon.ico"]
    monitoring_uas = [
        "curl/8.4.0",
        "Wget/1.21.4",
        "python-requests/2.31.0",
        "Python/3.12 aiohttp/3.9.5",
        "Mozilla/5.0 (compatible; UptimeRobot/2.0; +http://www.uptimerobot.com/)",
        "Render/1.0 Healthcheck",
        "",
    ]

    for p in probe_paths:
        for ua in monitoring_uas:
            is_mal, threat = is_malicious_request(path=p, user_agent=ua)
            assert is_mal is False, f"False positive on path='{p}' with UA='{ua}': {threat}"

    # Non-probe path should still flag CLI tools
    is_mal_cli, threat_cli = is_malicious_request(path="/api/movies", user_agent="curl/8.4.0")
    assert is_mal_cli is True
    assert "scanner_ua" in threat_cli

    # Exploitation tools must still be blocked even on health endpoints
    is_mal_sqlmap, threat_sqlmap = is_malicious_request(path="/health", user_agent="sqlmap/1.7#stable")
    assert is_mal_sqlmap is True
    assert "sqlmap" in threat_sqlmap

    # Exploit payload in query string on / must be blocked
    is_mal_sqli, threat_sqli = is_malicious_request(path="/", query_string="id=1'%20UNION%20SELECT%20null--", user_agent="curl/8.4.0")
    assert is_mal_sqli is True


def test_autoban_jail_render_nat_and_loopback_immunity():
    """AutoBanJail must never jail Render NAT gateway IPs, loopback, or private IPs."""
    jail = AutoBanJail(default_ban_seconds=60.0)

    immune_ips = [
        "127.0.0.1",
        "::1",
        "10.0.0.5",
        "172.16.0.1",
        "192.168.1.100",
        "216.24.57.10",    # Render Oregon NAT
        "216.24.60.25",    # Render Anycast NAT
        "3.125.105.150",   # Render Frankfurt NAT
        "44.209.160.100",  # Render Virginia NAT
    ]

    for ip in immune_ips:
        jail.jail_ip(ip, reason="test_attempt")
        is_j, _, _ = jail.is_jailed(ip)
        assert is_j is False, f"Immune IP {ip} was jailed in AutoBanJail!"

    # Genuine attacker public IP can be jailed
    attacker_ip = "198.51.100.88"
    jail.jail_ip(attacker_ip, duration=30.0, reason="test_exploit")
    is_j, rem, reason = jail.is_jailed(attacker_ip)
    assert is_j is True
    assert reason == "test_exploit"
    jail.unban_ip(attacker_ip)
    assert jail.is_jailed(attacker_ip)[0] is False


@pytest.mark.asyncio
async def test_throttling_middleware_non_punitive_rapid_clicks():
    """Suppressed rapid clicks in ThrottlingMiddleware must NOT reset the cooldown timer."""
    middleware = ThrottlingMiddleware(rate_limit=1.0)
    user = User(id=88889999, is_bot=False, first_name="TestUser")
    event = MagicMock(spec=CallbackQuery)
    event.from_user = user
    event.data = "test_click"
    event.answer = AsyncMock()

    handler_mock = AsyncMock(return_value="OK")

    with patch("time.monotonic") as mock_time:
        # Event 1 at t=100.0: Allowed
        mock_time.return_value = 100.0
        res1 = await middleware(handler_mock, event, {})
        assert res1 == "OK"
        assert middleware.user_timestamps[user.id] == 100.0

        # Rapid clicks at t=100.2, 100.4, 100.6, 100.8: Throttled, but timestamp stays 100.0
        for t in (100.2, 100.4, 100.6, 100.8):
            mock_time.return_value = t
            handler_mock.reset_mock()
            res = await middleware(handler_mock, event, {})
            assert res is None
            assert not handler_mock.called
            # Crucial assertion: timestamp did NOT update to t!
            assert middleware.user_timestamps[user.id] == 100.0

        # Click at t=101.05 (1.05s after original event): Allowed!
        mock_time.return_value = 101.05
        handler_mock.reset_mock()
        res_allowed = await middleware(handler_mock, event, {})
        assert res_allowed == "OK"
        assert handler_mock.called
        assert middleware.user_timestamps[user.id] == 101.05


@pytest.mark.asyncio
async def test_bot_security_negative_ban_caching():
    """BotSecurityMiddleware caches negative ban checks (is_banned=False) to avoid per-event DB queries."""
    middleware = BotSecurityMiddleware(window_seconds=5.0, max_requests=50, negative_ban_ttl=45.0)
    user = User(id=77778888, is_bot=False, first_name="CleanUser")
    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.text = "Salom"
    msg.answer = AsyncMock()

    handler_mock = AsyncMock(return_value="PASS")
    crud_ban_mock = AsyncMock(return_value=False)

    fake_session = AsyncMock()
    fake_session_ctx = MagicMock()
    fake_session_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("middlewares.security.get_session", return_value=fake_session_ctx), \
         patch("middlewares.security.crud.is_user_banned", crud_ban_mock):

        # First message: triggers DB query
        res1 = await middleware(handler_mock, msg, {})
        assert res1 == "PASS"
        assert crud_ban_mock.call_count == 1
        assert user.id in middleware._not_banned_cache

        # Next 10 messages from the same user: DB query is SKIPPED due to negative cache
        for _ in range(10):
            handler_mock.reset_mock()
            res = await middleware(handler_mock, msg, {})
            assert res == "PASS"
            assert handler_mock.called

        # DB was still only called once
        assert crud_ban_mock.call_count == 1


def test_books_handler_imports_any():
    """handlers/books has Any imported and safe_html handles various input types."""
    import handlers.books as hb
    assert hasattr(hb, "Any"), "handlers.books must import Any"
    assert hb.safe_html("<b>Test & 'quote'</b>") == "&lt;b&gt;Test &amp; 'quote'&lt;/b&gt;"
    assert hb.safe_html(42) == "42"
    assert hb.safe_html(None) == "None"

