"""
Keng qamrovli xavfsizlik va bardoshlilik testlari (Security & Resilience Test Suite)
===================================================================================
1. Clickjacking va xavfsizlik sarlavhalari (CSP frame-ancestors, nosniff, CORS)
2. Soxta botlar, zaiflik qidiruvchilar (sqlmap, nikto va h.k.) va SQLi/LFI skanerlarini 403 bilan bloklash
3. DoS / DDoS va in-memory sliding window rate limiter (429 Too Many Requests, /health whitelist)
4. Telegram WebApp initData HMAC-SHA256 validatsiyasi, soxta ID va soxtalashtirish (spoofing) fosh qilish
5. Oq ro'yxat va soxta ijobiy (false-positive) bo'lmasligini tekshirish (O'ylama, Forsaj, oddiy brauzerlar)
6. Bauntys brending qoidasi (hech qanday Zakirov/Zakirova sizmasligi)
"""
import time
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from aiohttp.test_utils import TestClient, TestServer
from config import config
from services.web_server import create_web_app, set_bot_instance
from services.security_service import (
    security_service,
    validate_telegram_init_data,
    generate_telegram_init_data,
    is_valid_user_id,
    is_malicious_request,
    SlidingWindowRateLimiter,
    get_security_headers,
    extract_client_ip,
)
from middlewares.throttling import ThrottlingMiddleware
from aiogram.types import CallbackQuery, User


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Har bir test oldidan rate limiter xotirasini tozalash."""
    security_service.rate_limiter.reset()
    yield
    security_service.rate_limiter.reset()


# =====================================================================
# 1. CLICKJACKING VA XAVFSIZLIK SARLAVHALARI (SECURITY HEADERS)
# =====================================================================
@pytest.mark.asyncio
async def test_security_headers_and_clickjacking_protection():
    """Barcha sahifa va API javoblarida CSP frame-ancestors va xavfsizlik sarlavhalari bo'lishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # /health endpointi
        resp = await client.get("/health")
        assert resp.status == 200

        csp = resp.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors" in csp
        assert "https://web.telegram.org" in csp
        assert "https://*.telegram.org" in csp
        assert "https://t.me" in csp
        assert "'self'" in csp

        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert "1; mode=block" in resp.headers.get("X-XSS-Protection", "")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

        # /api/movies endpointi
        resp_api = await client.get("/api/movies?limit=2")
        assert resp_api.status == 200
        csp_api = resp_api.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors" in csp_api
        assert resp_api.headers.get("X-Content-Type-Options") == "nosniff"

        # OPTIONS preflight
        resp_opt = await client.options("/api/movies")
        assert resp_opt.status == 204
        assert resp_opt.headers.get("Access-Control-Allow-Origin") == "*"
        assert "X-Init-Data" in resp_opt.headers.get("Access-Control-Allow-Headers", "")
    finally:
        await client.close()


# =====================================================================
# 2. MALICIOUS SCANNERS, EXPLOIT BOTS VA SQLi/LFI BLOKLASH (WAF)
# =====================================================================
@pytest.mark.asyncio
async def test_scanner_user_agents_blocked_with_403():
    """sqlmap, nikto, wpscan, curl, python-requests kabi skaner va botlar 403 Forbidden olishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    scanners_and_bots = [
        "sqlmap/1.7#stable",
        "Mozilla/5.0 (compatible; Nikto/2.1.6)",
        "WPScan v3.8.22",
        "masscan/1.3.2",
        "nuclei - projectdiscovery",
        "gobuster 3.5",
        "dirbuster 1.0",
        "Acunetix Web Vulnerability Scanner",
        "curl/8.4.0",
        "python-requests/2.31.0",
        "Wget/1.21.4",
        "Scrapy/2.11.0 (+https://scrapy.org)",
        "nmap/7.94",
        "PostmanRuntime/7.32.3",
    ]

    try:
        for scanner_ua in scanners_and_bots:
            resp = await client.get("/api/movies", headers={"User-Agent": scanner_ua})
            assert resp.status == 403, f"{scanner_ua} bloklanmadi! Status: {resp.status}"
            data = await resp.json()
            assert data["ok"] is False
            assert data["error"] == "forbidden"
            assert "Zararli" in data["message"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_empty_user_agent_handling():
    """Bo'sh User-Agent oddiy API larda bloklanishi, /health da esa ruxsat etilishi kerak."""
    # is_test ni vaqtincha False qilib tekshiramiz
    with patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}):
        is_mal, threat = is_malicious_request("/api/movies", user_agent="")
        assert is_mal is True
        assert threat == "empty_user_agent"

        # /health monitoring uchun esa ruxsat beriladi
        is_mal_h, threat_h = is_malicious_request("/health", user_agent="")
        assert is_mal_h is False
        assert threat_h is None


@pytest.mark.asyncio
async def test_malicious_sqli_and_lfi_patterns_blocked_with_403():
    """SQL injection, single/double traversal LFI va konfiguratsiya qidiruvlari 403 Forbidden olishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    attack_urls = [
        # SQL Injection
        "/api/movies?q=' UNION SELECT 1,2,3--",
        "/api/movies?q=%27%20UNION%20SELECT%201,2,3--",
        "/api/movies?q=' OR '1'='1",
        "/api/movies?q=; DROP TABLE users;",
        "/api/movies?q=%2527%2520UNION%2520SELECT", # Double URL encode
        # LFI & Path Traversal (ikki karra va bitta ../)
        "/api/movies?q=../../etc/passwd",
        "/api/movies?q=..%2F..%2Fetc%2Fpasswd",
        "/api/movies?q=../config.py",
        "/api/movies?q=..%2Fconfig.py",
        "/api/movies?q=%252e%252e%252fconfig.py",   # Double URL encode
        # Maxfiy fayllar
        "/.env",
        "/.git/config",
        "/.aws/credentials",
        "/.ssh/id_rsa",
        "/wp-login.php",
        "/phpmyadmin",
        # XSS
        "/api/movies?q=<script>alert('xss')</script>",
    ]

    try:
        for target in attack_urls:
            resp = await client.get(target)
            assert resp.status == 403, f"Zararli so'rov {target} bloklanmadi! Status: {resp.status}"
            data = await resp.json()
            assert data["ok"] is False
            assert data["error"] == "forbidden"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_legitimate_queries_not_false_positived():
    """O'zbekcha tutuq belgili so'zlar (O'ylama, Mo'jiza) va qonuniy so'rovlar hech qachon bloklanmasligi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    legit_urls = [
        "/api/movies?q=Forsaj",
        "/api/movies?q=O'ylama",
        "/api/movies?q=Mo'jiza",
        "/api/movies?q=Ko'ngil",
        "/api/movies?q=Форсаж",
        "/api/music?category=top50",
        "/api/tv?category=all",
        "/health",
    ]

    legit_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    try:
        for target in legit_urls:
            resp = await client.get(target, headers={"User-Agent": legit_ua})
            assert resp.status == 200, f"Qonuniy so'rov {target} xato bloklandi! Status: {resp.status}"
    finally:
        await client.close()


# =====================================================================
# 3. TELEGRAM INITDATA HMAC-SHA256 VA SOXTA ID TEKSHIRUVI
# =====================================================================
def test_telegram_init_data_hmac_sha256_validation():
    """Rasmiy Telegram WebApp HMAC-SHA256 tekshiruvi to'liq ishlashi."""
    test_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_1234567"
    user_payload = {"id": 98765432, "first_name": "Sardor", "username": "sardor_dev"}

    # 1. Haqiqiy imzolangan initData yaratish
    valid_init_data = generate_telegram_init_data(
        user_data=user_payload,
        bot_token=test_token,
        auth_date=int(time.time())
    )

    is_valid, parsed, err = validate_telegram_init_data(valid_init_data, bot_token=test_token, strict=True)
    assert is_valid is True
    assert err is None
    assert parsed["user_id"] == 98765432
    assert parsed["user"]["first_name"] == "Sardor"
    assert parsed["verified"] is True

    # 2. Buzilgan (soxtalashtirilgan) hash bilan initData
    tampered_init_data = valid_init_data.replace("hash=", "hash=deadbeef00112233")
    is_valid_tamp, _, err_tamp = validate_telegram_init_data(tampered_init_data, bot_token=test_token, strict=True)
    assert is_valid_tamp is False
    assert err_tamp == "invalid_signature"

    # 3. Foydalanuvchi IDsi o'zgartirilgan (soxta ID)
    tampered_user_data = valid_init_data.replace("98765432", "11111111")
    is_valid_uid, _, err_uid = validate_telegram_init_data(tampered_user_data, bot_token=test_token, strict=True)
    assert is_valid_uid is False
    assert err_uid == "invalid_signature"

    # 4. Muddati o'tgan auth_date (masalan 2 kun oldingi)
    expired_init_data = generate_telegram_init_data(
        user_data=user_payload,
        bot_token=test_token,
        auth_date=int(time.time() - 200000)
    )
    is_valid_exp, _, err_exp = validate_telegram_init_data(
        expired_init_data, bot_token=test_token, max_age_seconds=86400, strict=True
    )
    assert is_valid_exp is False
    assert err_exp == "auth_date_expired"

    # 5. Kelajakdagi soxta auth_date
    future_init_data = generate_telegram_init_data(
        user_data=user_payload,
        bot_token=test_token,
        auth_date=int(time.time() + 10000)
    )
    is_valid_fut, _, err_fut = validate_telegram_init_data(
        future_init_data, bot_token=test_token, strict=True
    )
    assert is_valid_fut is False
    assert err_fut == "auth_date_in_future"


def test_user_id_format_validation():
    """Telegram user_id musbat va to'g'ri diapazonda bo'lishi tekshiruvi."""
    assert is_valid_user_id(12345678) is True
    assert is_valid_user_id("87654321") is True
    assert is_valid_user_id(1) is True

    # Noto'g'ri qiymatlar
    assert is_valid_user_id(0) is False
    assert is_valid_user_id(-500) is False
    assert is_valid_user_id("not_a_number") is False
    assert is_valid_user_id("1; DROP TABLE") is False
    assert is_valid_user_id(None) is False
    assert is_valid_user_id(10**18) is False  # 2^53 dan katta


# =====================================================================
# 4. SOXTA ID (SPOOFING) VA SOXTA BOT HUJUMLARINI TO'XTATISH
# =====================================================================
@pytest.mark.asyncio
async def test_spoofed_user_id_blocked_in_send_to_chat():
    """InitData da User A ko'rsatilgan bo'lsa-yu, bodyda User B yuborilsa (spoofing) 403 bilan rad etilishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    set_bot_instance(mock_bot)

    test_token = "999999999:TEST_BOT_TOKEN_FOR_SECURITY_SUITE"
    with patch.object(config, "BOT_TOKEN", test_token):
        # Alice (ID: 10001) uchun haqiqiy imzolangan initData
        alice_init_data = generate_telegram_init_data(
            user_data={"id": 10001, "first_name": "Alice"},
            bot_token=test_token
        )

        try:
            # 1. Alice o'z nomidan so'rov yuborganda muvaffaqiyatli o'tishi kerak
            resp_alice = await client.post(
                "/api/send_to_chat",
                headers={"X-Init-Data": alice_init_data},
                json={"user_id": 10001, "type": "music", "title": "Test Track", "artist": "Singer"}
            )
            assert resp_alice.status == 200

            # 2. Alice nomidan Bob (ID: 20002) ga soxta spam yuborishga urinish -> 403 Forbidden
            resp_spoof = await client.post(
                "/api/send_to_chat",
                headers={"X-Init-Data": alice_init_data},
                json={"user_id": 20002, "type": "music", "title": "Spam Track", "artist": "Attacker"}
            )
            assert resp_spoof.status == 403
            data_spoof = await resp_spoof.json()
            assert data_spoof["code"] == "spoofing"

            # 3. Soxta imzo (fake hash) bilan yuborish -> 401 Unauthorized
            fake_init_data = alice_init_data.replace("hash=", "hash=forged_bad_hash_")
            resp_fake = await client.post(
                "/api/send_to_chat",
                headers={"X-Init-Data": fake_init_data},
                json={"user_id": 10001, "type": "music", "title": "Test Track"}
            )
            assert resp_fake.status == 401
        finally:
            await client.close()
            set_bot_instance(None)


@pytest.mark.asyncio
async def test_spoofed_user_id_blocked_in_watch_endpoint():
    """POST /api/watch endpointida soxta initData va soxta ID rad etilishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    set_bot_instance(mock_bot)

    test_token = "999999999:TEST_BOT_TOKEN_FOR_SECURITY_SUITE"
    with patch.object(config, "BOT_TOKEN", test_token):
        user_init_data = generate_telegram_init_data(
            user_data={"id": 55555, "first_name": "RealUser"},
            bot_token=test_token
        )

        try:
            # 1. InitData 55555, lekin user_id 77777 berilsa -> 403 Spoofing
            resp_spoof = await client.post(
                "/api/watch",
                headers={"X-Init-Data": user_init_data},
                json={"code": "101", "part": 1, "user_id": 77777}
            )
            assert resp_spoof.status == 403
            data_spoof = await resp_spoof.json()
            assert data_spoof["error"] == "spoofing"

            # 2. Fake hash bilan so'rov -> 401 Auth Failed
            fake_data = user_init_data.replace("hash=", "hash=completely_fake_signature_")
            resp_fake = await client.post(
                "/api/watch",
                headers={"X-Init-Data": fake_data},
                json={"code": "101", "part": 1}
            )
            assert resp_fake.status == 401
            data_fake = await resp_fake.json()
            assert data_fake["error"] == "auth_failed"
        finally:
            await client.close()
            set_bot_instance(None)


# =====================================================================
# 5. IN-MEMORY SLIDING WINDOW RATE LIMITER & DoS HIMOYASI
# =====================================================================
def test_sliding_window_rate_limiter_logic():
    """SlidingWindowRateLimiter qisqa vaqtda yuzlab spam yuborayotgan IP ni cheklashi va ban qilishi."""
    limiter = SlidingWindowRateLimiter(
        burst_limit=10,
        burst_window=2.0,
        sustained_limit=20,
        sustained_window=10.0,
        ban_duration=5.0
    )

    attacker_ip = "198.51.100.77"

    # 1. 10 ta so'rov ruxsat etiladi
    for _ in range(10):
        allowed, retry = limiter.is_allowed(attacker_ip, path="/api/movies")
        assert allowed is True
        assert retry is None

    # 2. 11-so'rov burst limitini buzadi va IP ban bo'ladi
    allowed_burst, retry_burst = limiter.is_allowed(attacker_ip, path="/api/movies")
    assert allowed_burst is False
    assert retry_burst is not None
    assert retry_burst >= 4

    # 3. Ban davomida barcha keyingi so'rovlar darhol rad etiladi
    allowed_banned, retry_banned = limiter.is_allowed(attacker_ip, path="/api/movies")
    assert allowed_banned is False
    assert retry_banned is not None

    # 4. /health endpointi esa hatto shu IP dan ham har doim ruxsat beriladi (Render monitoringi)
    allowed_health, _ = limiter.is_allowed(attacker_ip, path="/health")
    assert allowed_health is True

    # 5. Boshqa begunoh IP ga esa ta'sir qilmaydi
    innocent_ip = "203.0.113.50"
    allowed_innocent, _ = limiter.is_allowed(innocent_ip, path="/api/movies")
    assert allowed_innocent is True


@pytest.mark.asyncio
async def test_http_rate_limiter_returns_429_too_many_requests():
    """Tajovuzkor tashqi IP HTTP so'rovlar oqimi yuborganda server 429 Too Many Requests qaytarishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    # Rate limiterni qattiq test rejimiga o'rnatish (10 soniyalik burst darcha)
    custom_limiter = SlidingWindowRateLimiter(
        burst_limit=5,
        burst_window=10.0,
        sustained_limit=10,
        sustained_window=30.0,
        ban_duration=5.0
    )
    original_limiter = security_service.rate_limiter
    security_service.rate_limiter = custom_limiter

    attacker_headers = {
        "X-Forwarded-For": "198.51.100.99",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        # Birinchi 5 ta so'rov o'tadi
        for _ in range(5):
            resp = await client.get("/api/maintenance", headers=attacker_headers)
            assert resp.status == 200

        # 6-so'rov burst chegarasidan oshadi -> 429 Too Many Requests
        resp_429 = await client.get("/api/maintenance", headers=attacker_headers)
        assert resp_429.status == 429
        assert "Retry-After" in resp_429.headers
        data_429 = await resp_429.json()
        assert data_429["ok"] is False
        assert data_429["error"] == "too_many_requests"
        assert "Juda ko'p so'rovlar" in data_429["message"]

        # Health check esa doim 200 bo'lib qoladi
        resp_health = await client.get("/health", headers=attacker_headers)
        assert resp_health.status == 200
    finally:
        security_service.rate_limiter = original_limiter
        await client.close()


def test_client_ip_spoofing_defense():
    """X-Forwarded-For orqali soxta IP yuborilganda oxirgi haqiqiy IP olinishi va zararli belgilar tozalanishi."""
    req_mock = MagicMock()
    req_mock.headers = {"X-Forwarded-For": "1.1.1.1, 198.51.100.99"}
    req_mock.remote = "10.0.0.1"
    # 1.1.1.1 tajovuzkor tomonidan soxtalashtirilgan, Render esa 198.51.100.99 ni biriktirgan
    assert extract_client_ip(req_mock) == "198.51.100.99"

    # Zararli kod yuborilganda xavfsiz tozalash
    req_bad = MagicMock()
    req_bad.headers = {"X-Forwarded-For": "<script>alert(1)</script>"}
    req_bad.remote = "127.0.0.1"
    assert extract_client_ip(req_bad) == "127.0.0.1"


def test_per_user_rate_limiting():
    """Bitta foydalanuvchi turli IP manzillar orqali spam yuborganda ham user_id bo'yicha rate limiting ishlashi."""
    limiter = SlidingWindowRateLimiter(
        burst_limit=100,
        sustained_limit=200,
        user_burst_limit=4,
        user_burst_window=2.0,
        user_sustained_limit=10,
        user_sustained_window=10.0,
    )

    uid = 777888999
    # Turli IP lardan bitta user nomidan so'rovlar
    for i in range(4):
        allowed, _ = limiter.is_allowed(f"192.0.2.{i}", path="/api/movies", user_id=uid)
        assert allowed is True

    # 5-so'rov foydalanuvchi chegarasidan oshadi
    allowed_5, retry_5 = limiter.is_allowed("192.0.2.99", path="/api/movies", user_id=uid)
    assert allowed_5 is False
    assert retry_5 is not None


def test_missing_init_data_in_strict_mode_rejected():
    """Qat'iy xavfsizlik rejimida init_data bo'lmasa, state-changing so'rovlar rad etilishi kerak."""
    mock_req = MagicMock()
    mock_req.headers = {}
    mock_req.query = {}

    # Strict rejimda init_data yo'q bo'lsa
    user_id, is_valid, err = security_service.verify_telegram_user(
        mock_req, payload_user_id=12345, require_auth=True
    )
    assert is_valid is False
    assert err == "missing_init_data"
    assert user_id is None


@pytest.mark.asyncio
async def test_callback_query_throttling():
    """Tugma bosishlarni (CallbackQuery) spam qilayotgan botlar ThrottlingMiddleware tomonidan to'xtatilishi."""
    middleware = ThrottlingMiddleware(rate_limit=1.0)
    handler = AsyncMock(return_value="handled")

    cb_mock = MagicMock(spec=CallbackQuery)
    cb_mock.from_user = User(id=999111, is_bot=False, first_name="Test")
    cb_mock.answer = AsyncMock()

    # Birinchi so'rov o'tadi
    res1 = await middleware(handler, cb_mock, {})
    assert res1 == "handled"

    # Darhol ikkinchi so'rov yuborilganda throttled bo'ladi
    res2 = await middleware(handler, cb_mock, {})
    assert res2 is None
    cb_mock.answer.assert_called_once()


# =====================================================================
# 6. BAUNTYS BRENDINGI VA OQIB KETISH YO'QLIGINI TEKSHIRISH
# =====================================================================
def test_no_branding_leaks_in_security_module():
    """Xavfsizlik moduli va barcha xabarlarda qat'iy Bauntys brendingi saqlanishi kerak."""
    from config import BASE_DIR
    sec_file = BASE_DIR / "services" / "security_service.py"
    with open(sec_file, "r", encoding="utf-8") as f:
        content = f.read().lower()

    assert "dilbarzakirova" not in content
    assert "zakirova" not in content
    assert "zakirov" not in content
