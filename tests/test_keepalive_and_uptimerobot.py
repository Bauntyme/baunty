"""
Test suite for UptimeRobot, Render Keep-Alive, Health Endpoints and Resilience.
Ensures zero-friction 200 OK responses for all legitimate probes, no false-positive rate-limiting,
and rigorous protection against malicious attacks.
"""
import pytest
import asyncio
from aiohttp.test_utils import TestServer, TestClient
from services.web_server import create_web_app
from services.security_service import security_service, FAST_MASTER_THREAT_REGEX
from services.keepalive_service import TARGET_HEALTH_URLS


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
