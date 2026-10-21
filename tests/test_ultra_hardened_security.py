"""
Bauntys Ultra-Hardened Security Test Suite
==========================================
Foydalanuvchining barcha xavfsizlik talablarini to'liq tekshirish:
1. Zero Reconnaissance & Database Shield:
   - SQLite bazalar (*.db, *.sqlite, *.sqlite3, *.sql), JSON ma'lumotlar fayllari
     (data/*.json, maintenance.json, video_sources.json), .env, .git, .py, .sh,
     .yml, .yaml, .bak, .conf fayllariga barcha to'g'ridan-to'g'ri HTTP so'rovlar
     va path traversal urinishlari darhol 403 Forbidden bilan to'siladi.
   - Ichki server xatolari va texnologiya tafsilotlari (Server header, Python stack trace)
     tashqariga sizdirilmaydi.
2. Web Application Firewall (WAF) & Intrusion Detection:
   - SQLi, XSS, RFI/LFI, Command Injection, admin/backdoor panellari (phpmyadmin,
     wp-admin, cgi-bin, actuator, xmlrpc, spring, shell, config.json) darhol 403.
   - Taniqli hakerlik skanerlari (sqlmap, nikto, wpscan, masscan, nmap, dirbuster,
     gobuster, ffuf, acunetix, burp, zgrab, hydra, metasploit, censys) darhol 403.
   - Auto-Ban Jail: Tajovuzkor IP avtomatik ravishda dinamik qamoqqa olinadi.
3. Web App va Telegram Bot modullarining benuqson ishlashi:
   - Clickjacking CSP (frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://t.me;),
     nosniff, SAMEORIGIN, HSTS sarlavhalari.
   - 10 ta modul va o'zbekcha so'rovlar (O'ylama, Mo'jiza) false-positive siz to'liq ishlaydi.
   - Render.com health check (/health) doim oq ro'yxatda.
4. Bauntys brendingi qat'iy saqlanadi.
"""
import os
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web
from config import config
from services.web_server import create_web_app, set_bot_instance
from services.security_service import (
    security_service,
    is_malicious_request,
    check_reconnaissance_and_database_shield,
    get_security_headers,
    extract_client_ip,
)


@pytest.fixture(autouse=True)
def reset_security_state():
    """Har bir test oldidan va keyin xavfsizlik holatini tozalash."""
    security_service.reset()
    yield
    security_service.reset()


# =====================================================================
# 1. ZERO RECONNAISSANCE & DATABASE SHIELD
# =====================================================================
@pytest.mark.asyncio
async def test_database_files_shield_blocks_all_db_and_sqlite_requests():
    """SQLite bazalar (*.db, *.sqlite, *.sqlite3, *.sql, wal, shm) so'ralganda darhol 403 Forbidden qaytarishi shart."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    database_probe_urls = [
        "/bauntyfilms.db",
        "/bot.db",
        "/bot.db-wal",
        "/bot.db-shm",
        "/bauntyfilms.db-wal",
        "/bauntyfilms.db-journal",
        "/test.sqlite-wal",
        "/test.sqlite-shm",
        "/production.sqlite3-wal",
        "/data/bot.db",
        "/database/bauntyfilms.db",
        "/test.sqlite",
        "/production.sqlite3",
        "/backup.db3",
        "/dump.sql",
        "/database/schema.sql",
        "/webapp/bauntyfilms.db",
        "/webapp/../bauntyfilms.db",
        "/webapp/..%2fbauntyfilms.db",
        # Windows nuqta, bo'shliq va ADS aylanib o'tishlari
        "/bot.db.",
        "/bot.db ",
        "/bot.db%20",
        "/bot.db::$DATA",
        "/bauntyfilms.db::$DATA",
        # Zaxira arxivlari va maxfiy sertifikatlar
        "/backup.zip",
        "/backup.tar.gz",
        "/bot.rdb",
        "/db.dump",
        "/server.key",
    ]

    try:
        for url in database_probe_urls:
            resp = await client.get(url)
            assert resp.status == 403, f"Baza fayli {url} bloklanmadi! Status: {resp.status}"
            data = await resp.json()
            assert data["ok"] is False
            assert data["error"] == "forbidden"
            assert "Zararli" in data["message"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_json_data_files_shield_blocks_direct_access():
    """JSON ma'lumotlar fayllari (data/*.json, maintenance.json, video_sources.json) 403 bilan to'silishi shart."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    json_probe_urls = [
        "/data/movies.json",
        "/data/catalog.json",
        "/data/books.json",
        "/data/maintenance.json",
        "/data/video_sources.json",
        "/data/music_home.json",
        "/data/prava_images.json",
        "/maintenance.json",
        "/video_sources.json",
        "/catalog.json",
        "/books.json",
        "/config.json",
        "/package.json",
        "/composer.json",
        "/secret.json",
    ]

    try:
        for url in json_probe_urls:
            resp = await client.get(url)
            assert resp.status == 403, f"JSON fayl {url} bloklanmadi! Status: {resp.status}"
            data = await resp.json()
            assert data["ok"] is False
            assert data["error"] == "forbidden"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_source_code_and_env_files_shield():
    """.env, .git, .py, .sh, .yml, .yaml, .bak, .conf fayllar 403 Forbidden bilan to'liq to'silishi shart."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    source_and_config_urls = [
        "/.env",
        "/.env.example",
        "/.env.local",
        "/.env.production",
        "/.env.",
        "/.env ",
        "/.git",
        "/.git/config",
        "/.git/HEAD",
        "/main.py",
        "/main.py.",
        "/main.py ",
        "/main.py::$DATA",
        "/config.py",
        "/database/crud.py",
        "/database/models.py",
        "/services/web_server.py",
        "/services/security_service.py",
        "/scripts/test.sh",
        "/scratch/test.py",
        "/Dockerfile",
        "/docker-compose.yml",
        "/docker-compose.yaml",
        "/requirements.txt",
        "/pytest.ini",
        "/setup.sh",
        "/deploy.bash",
        "/backup.bak",
        "/nginx.conf",
        "/app.cfg",
    ]

    try:
        for url in source_and_config_urls:
            resp = await client.get(url)
            assert resp.status == 403, f"Manba/konfiguratsiya fayli {url} bloklanmadi! Status: {resp.status}"
            data = await resp.json()
            assert data["ok"] is False
            assert data["error"] == "forbidden"
    finally:
        await client.close()


# =====================================================================
# 2. PATH TRAVERSAL VA OBFUSKATSIYA
# =====================================================================
@pytest.mark.asyncio
async def test_path_traversal_and_obfuscation_blocked_with_403():
    """Har qanday path traversal urinishlari (../, ..\\, %2e%2e, %252e%252e, null byte) darhol 403 Forbidden olishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    traversal_urls = [
        "/webapp/../data/movies.json",
        "/webapp/..%2fdata/movies.json",
        "/webapp/..%5cdata/movies.json",
        "/webapp/..;/data/bot.db",
        "/webapp/%2e%2e/%2e%2e/bauntyfilms.db",
        "/webapp/%252e%252e/%252e%252e/main.py",
        "/api/movies?q=../../etc/passwd",
        "/api/movies?q=..%2F..%2Fetc%2Fshadow",
        "/api/movies?q=%252e%252e%252fconfig.py",
        "/api/movies?q=..\\..\\win.ini",
        "/api/movies?q=../config.py",
        "/main.py%00.png",
        "/bot.db%00.jpg",
        "/api/movies?q=1%00' UNION SELECT",
    ]

    try:
        for url in traversal_urls:
            resp = await client.get(url)
            assert resp.status == 403, f"Path traversal {url} bloklanmadi! Status: {resp.status}"
            data = await resp.json()
            assert data["ok"] is False
            assert data["error"] == "forbidden"
    finally:
        await client.close()


# =====================================================================
# 3. TANIQLI HAKERLIK SKANERLARI (HACKER TOOLS / SCANNERS)
# =====================================================================
@pytest.mark.asyncio
async def test_all_hacker_scanners_blocked_with_403():
    """Foydalanuvchi talab qilgan barcha skanerlar (sqlmap, nikto, wpscan, ffuf, burp, curl, wget va h.k.) 403 olishi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    scanner_user_agents = [
        "sqlmap/1.7#stable",
        "Mozilla/5.0 (compatible; Nikto/2.1.6)",
        "WPScan v3.8.22",
        "masscan/1.3.2",
        "Nmap Scripting Engine",
        "dirbuster 1.0",
        "gobuster 3.5",
        "ffuf/2.0.0",
        "Acunetix Web Vulnerability Scanner",
        "BurpSuite/2024.1",
        "Mozilla/5.0 (compatible; Burp)",
        "zgrab/2.0",
        "Hydra v9.5",
        "metasploit-framework",
        "CensysInspect/1.1",
        "nuclei - projectdiscovery",
        "Netsparker",
        # CLI va skraperlar (trailing slash siz ham)
        "curl",
        "curl/8.4.0",
        "wget",
        "wget/1.21",
        "requests",
        "python-requests/2.31.0",
        # UA ichiga yashirilgan SQLi va XSS
        "Mozilla/5.0 <script>alert(1)</script>",
        "Mozilla/5.0 ' UNION SELECT 1,2,3--",
    ]

    try:
        for ua in scanner_user_agents:
            resp = await client.get("/api/movies", headers={"User-Agent": ua})
            assert resp.status == 403, f"Skaner {ua} bloklanmadi! Status: {resp.status}"
            data = await resp.json()
            assert data["ok"] is False
            assert data["error"] == "forbidden"
            assert "Zararli" in data["message"]
    finally:
        await client.close()


# =====================================================================
# 4. WEB APPLICATION FIREWALL (SQLi, XSS, RCE, BACKDOORS)
# =====================================================================
@pytest.mark.asyncio
async def test_web_application_firewall_sqli_xss_rce_blocked():
    """SQL Injection, XSS, Command Injection, POST body hamda Admin/Backdoor yo'llari 403 Forbidden bilan to'xtatiladi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    attack_payloads = [
        # SQL Injection (standart va inline comment /**/ aylanib o'tishlari)
        "/api/movies?q=' UNION SELECT 1,2,3--",
        "/api/movies?q=UNION/**/SELECT 1,2,3",
        "/api/movies?q=UNION/*all*/SELECT 1,2,3",
        "/api/movies?q=' OR '1'='1",
        "/api/movies?q=' OR 2=2",
        "/api/movies?q=' OR 'x'='x'",
        "/api/movies?q=' OR ''=''",
        "/api/movies?q=; DROP TABLE users;",
        "/api/movies?q=; DROP/**/TABLE users;",
        "/api/movies?q=1; SLEEP(5)",
        "/api/movies?q=1; SLEEP/*comment*/(5)",
        "/api/movies?q=1; BENCHMARK(1000000,MD5(1))",
        "/api/movies?q=1; BENCHMARK/*comment*/(1000000,MD5(1))",
        "/api/movies?q=1; pg_sleep(5)",
        "/api/movies?q=1; pg_sleep/*comment*/(5)",
        "/api/movies?q=SELECT @@VERSION",
        "/api/movies?q=SELECT * FROM INFORMATION_SCHEMA.TABLES",
        # XSS
        "/api/movies?q=<script>alert('xss')</script>",
        "/api/movies?q=javascript:alert(1)",
        "/api/movies?q=<img src=x onerror=alert(1)>",
        "/api/movies?q=<img src=x onfocus=alert(1)>",
        "/api/movies?q=<svg onload=alert(1)>",
        "/api/movies?q=<svg onblur=alert(1)>",
        "/api/movies?q=<iframe src='evil.com'></iframe>",
        # Command Injection
        "/api/movies?cmd=whoami",
        "/api/movies?exec=id",
        "/api/movies?q=; cat /etc/passwd",
        "/api/movies?q=| whoami",
        "/api/movies?q=&& id",
        "/api/movies?q=$(whoami)",
        # Admin / Backdoor Panellari
        "/phpmyadmin",
        "/pma",
        "/wp-admin",
        "/wp-login.php",
        "/cgi-bin/test",
        "/actuator",
        "/actuator/health",
        "/actuator/env",
        "/xmlrpc.php",
        "/spring/admin",
        "/shell.php",
        "/config.json",
        "/server-status",
        "/telescope",
        "/boaform/admin",
        "/solr/admin",
    ]

    try:
        # 1. GET so'rovlari orqali hujumlar
        for target in attack_payloads:
            resp = await client.get(target)
            assert resp.status == 403, f"Hujum so'rovi {target} bloklanmadi! Status: {resp.status}"
            data = await resp.json()
            assert data["ok"] is False
            assert data["error"] == "forbidden"

        # 2. POST so'rovlari orqali JSON body exploitlari
        post_attacks = [
            ("/api/watch", {"movie_code": "' UNION SELECT 1,2,3--"}),
            ("/api/watch", {"movie_code": "UNION/**/SELECT 1,2,3"}),
            ("/api/send_to_chat", {"cmd": "whoami"}),
            ("/api/send_to_chat", {"message": "<script>alert('xss')</script>"}),
            ("/api/send_to_chat", {"path": "../../etc/passwd"}),
        ]
        for ep, payload in post_attacks:
            resp_post = await client.post(ep, json=payload)
            assert resp_post.status == 403, f"POST hujumi {ep} {payload} bloklanmadi! Status: {resp_post.status}"
            data_post = await resp_post.json()
            assert data_post["ok"] is False
            assert data_post["error"] == "forbidden"

        # 3. HTTP Header (Cookie, Referer) orqali exploitlar
        header_attacks = [
            ("/api/movies", {"Cookie": "session=1' OR 1=1"}),
            ("/api/movies", {"Referer": "<script>alert(1)</script>"}),
        ]
        for ep, hdrs in header_attacks:
            resp_hdr = await client.get(ep, headers=hdrs)
            assert resp_hdr.status == 403, f"Header hujumi {hdrs} bloklanmadi! Status: {resp_hdr.status}"
            data_hdr = await resp_hdr.json()
            assert data_hdr["ok"] is False
            assert data_hdr["error"] == "forbidden"
    finally:
        await client.close()


# =====================================================================
# 5. AUTO-BAN JAIL DINAMIK QORA RO'YXAT
# =====================================================================
@pytest.mark.asyncio
async def test_auto_ban_jail_dynamic_blacklisting():
    """
    Zararli harakat qilgan IP avtomatik ravishda Auto-Ban Jail ga olinadi.
    Shundan so'ng u yuborgan keyingi har qanday so'rov darhol 403 Forbidden oladi.
    /health esa monitoring uchun har doim ochiq qoladi.
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    attacker_ip = "198.51.100.88"
    attacker_headers = {
        "X-Forwarded-For": attacker_ip,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        # 1. Dastlab oddiy so'rov o'tadi
        resp_init = await client.get("/api/movies", headers=attacker_headers)
        assert resp_init.status == 200

        # 2. Tajovuzkor skaner orqali hujum qiladi -> 403 Forbidden va Auto-Ban Jail ga tushadi
        resp_attack = await client.get(
            "/api/movies",
            headers={"X-Forwarded-For": attacker_ip, "User-Agent": "ffuf/2.0.0"}
        )
        assert resp_attack.status == 403
        assert security_service.is_ip_banned(attacker_ip)[0] is True

        # 3. Shundan so'ng hatto oddiy brauzer User-Agent bilan kelsa ham 403 Forbidden oladi
        resp_blocked = await client.get("/api/movies", headers=attacker_headers)
        assert resp_blocked.status == 403
        data_blocked = await resp_blocked.json()
        assert data_blocked["threat"] == "ip_auto_banned"
        assert "vaqtincha bloklangan" in data_blocked["message"]

        # 4. Render /health endpointi esa ushbu IP dan ham to'siqsiz ishlaydi (oq ro'yxat)
        resp_health = await client.get("/health", headers=attacker_headers)
        assert resp_health.status == 200
        health_data = await resp_health.json()
        assert health_data["status"] == "ok"

        # 5. IP qamoqdan chiqarilganda (unban) normal ishlashi tiklanadi
        security_service.unban_ip(attacker_ip)
        assert security_service.is_ip_banned(attacker_ip)[0] is False
        resp_restored = await client.get("/api/movies", headers=attacker_headers)
        assert resp_restored.status == 200
    finally:
        await client.close()


# =====================================================================
# 6. XAVFSIZLIK SARLAVHALARI VA SERVER NIQOBLASH (ZERO TRACE LEAK)
# =====================================================================
@pytest.mark.asyncio
async def test_server_header_masked_and_error_shielding():
    """
    1. Server sarlavhasi 'Bauntys-Shield' qilib niqoblangan, Python/aiohttp versiyalari ko'rinmaydi.
    2. Clickjacking CSP (frame-ancestors), X-Content-Type-Options, SAMEORIGIN, HSTS mavjud.
    3. Kutilmagan server xatoliklarida Python stack trace tashqariga chiqmaydi (xavfsiz JSON 500).
    """
    app = create_web_app()

    # Xatolik keltirib chiqaruvchi sinov marshruti
    async def crash_handler(req):
        raise ValueError("Secret database password / trace inside internal logic")

    app.router.add_get("/api/test_crash", crash_handler)

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/health")
        assert resp.status == 200
        headers = resp.headers

        # Server sarlavhasi niqoblangan
        assert headers.get("Server") == "Bauntys-Shield"
        assert "python" not in headers.get("Server", "").lower()
        assert "aiohttp" not in headers.get("Server", "").lower()
        assert "X-Powered-By" not in headers

        # Qat'iy brauzer xavfsizlik sarlavhalari
        assert "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://t.me;" in headers.get("Content-Security-Policy", "")
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert "1; mode=block" in headers.get("X-XSS-Protection", "")
        assert "strict-origin-when-cross-origin" in headers.get("Referrer-Policy", "")
        assert "max-age=31536000" in headers.get("Strict-Transport-Security", "")

        # 500 ichki xatolikda Python trace sizmasligi testi
        resp_500 = await client.get("/api/test_crash")
        assert resp_500.status == 500
        data_500 = await resp_500.json()
        assert data_500["ok"] is False
        assert data_500["error"] == "server_error"
        # Xabar xavfsiz va ichki maxfiy parollardan xoli
        assert "Secret" not in json.dumps(data_500)
        assert "Traceback" not in json.dumps(data_500)
        assert "ValueError" not in json.dumps(data_500)
        assert resp_500.headers.get("Server") == "Bauntys-Shield"
    finally:
        await client.close()


# =====================================================================
# 7. QONUNIY WEB APP MODULLARI VA O'ZBEKCHA SO'ROVLAR TO'LIQ ISHLASHI
# =====================================================================
@pytest.mark.asyncio
async def test_legitimate_webapp_modules_and_uzbek_queries_unaffected():
    """
    Telegram Web App ning barcha 10 ta moduli va o'zbekcha tutuq belgili so'rovlar
    (O'ylama, Mo'jiza, Ko'ngil) xatosiz va to'siqsiz 200 OK qaytarishi kerak.
    """
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    legit_endpoints = [
        # 1. 1440p TV
        "/api/tv",
        # 2. Kinolar
        "/api/movies",
        "/api/catalog",
        # 3. Musiqa
        "/api/music",
        "/api/music/home",
        # 4. Kitoblar
        "/api/books",
        "/api/books/home",
        # 5. Taomlar
        "/api/food",
        # 6. Viktorina
        "/api/quiz/home",
        # 7. Prava
        "/api/prava/home",
        # 8. O'yinlar
        "/api/games",
        # 9. Story
        "/api/story",
        # 10. SubGate & Donat
        "/api/sub",
        "/api/donate",
        "/api/reklama",
        # O'zbekcha tutuq belgili qidiruvlar va parametrlar (False-Positive yo'qligini tekshirish)
        "/api/movies?q=O'ylama",
        "/api/movies?q=Mo'jiza",
        "/api/movies?q=Ko'ngil",
        "/api/movies?q=Forsaj",
        # &id= va &cat= kabi oddiy query parametrlar soxta Command Injection deb olinmasligini tekshirish
        "/api/movies?sort=popular&id=10",
        "/api/books?filter=all&cat=action",
        "/api/music?type=track&id=5",
        "/api/movies?genre=action&cat=movies",
        "/api/movies?format=standard&sh=compact",
        "/api/movies?mode=safe&rm=none",
        # Asosiy Mini App sahifasi va statik assetlar
        "/",
        "/index.html",
        "/webapp",
        "/webapp/app.js",
        "/webapp/css/style.css",
        "/webapp/f/manrope-500.woff2",
        # Kitob assetlari (bk)
        "/bk/1/meta.json",
        # Render monitoring
        "/health",
    ]

    legit_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Telegram-Android/10.9.0"

    # Test kitob assetini lokal data/bk/1/ papkaga joylashtirish
    from config import BASE_DIR
    test_bk_file = BASE_DIR / "data" / "bk" / "1" / "meta.json"
    test_bk_file.parent.mkdir(parents=True, exist_ok=True)
    with open(test_bk_file, "w", encoding="utf-8") as bf:
        bf.write('{"id": 1, "title": "Test Kitob"}')

    try:
        for ep in legit_endpoints:
            resp = await client.get(ep, headers={"User-Agent": legit_ua})
            assert resp.status in (200, 204), f"Qonuniy resurs {ep} xato bloklandi! Status: {resp.status}"
            assert resp.status != 403, f"Qonuniy resurs {ep} 403 bilan noto'g'ri bloklandi!"

        # Qonuniy POST so'rovi (kinoni ko'rish) to'siqsiz ishlashi
        resp_post = await client.post(
            "/api/watch",
            json={"movie_code": "101", "user_id": 12345},
            headers={"User-Agent": legit_ua}
        )
        assert resp_post.status != 403, f"Qonuniy POST so'rovi 403 bilan noto'g'ri bloklandi! Status: {resp_post.status}"
    finally:
        if test_bk_file.exists():
            test_bk_file.unlink()
        await client.close()


# =====================================================================
# 8. QAT'IY BAUNTYS BRENDINGI
# =====================================================================
def test_branding_integrity_in_security():
    """Xavfsizlik moduli va yangi testlarda qat'iy Bauntys brendingi saqlanishi kerak."""
    from config import BASE_DIR
    sec_file = BASE_DIR / "services" / "security_service.py"
    with open(sec_file, "r", encoding="utf-8") as f:
        content = f.read().lower()

    assert "dilbarzakirova" not in content
    assert "zakirova" not in content
    assert "zakirov" not in content
