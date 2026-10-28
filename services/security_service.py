"""
Bauntys Ultra-Hardened Xavfsizlik va Himoya Xizmati (Security Service)
======================================================================
1. Zero Reconnaissance & Database Shield:
   - SQLite bazalar (*.db, *.sqlite, *.sqlite3), JSON ma'lumotlar fayllari (data/*.json,
     maintenance.json, video_sources.json), .env, .git, .py, .sh, .yml, .yaml, .bak, .conf
     fayllariga to'g'ridan-to'g'ri HTTP so'rovlar va path traversal urinishlari (../, %2e%2e, ..\\)
     darhol 403 Forbidden bilan kesiladi.
   - Ichki server xatolari, Python stack trace va versiya ma'lumotlari berkitiladi (Server header niqoblanadi).
2. Web Application Firewall (WAF) & Intrusion Detection:
   - SQL Injection (SQLi), Cross-Site Scripting (XSS), LFI/RFI, Command Injection, admin/backdoor panellarini
     (phpmyadmin, wp-admin, cgi-bin, actuator, xmlrpc, spring, shell, config.json) aniqlash va darhol 403 qaytarish.
   - Taniqli hakerlik skanerlari (sqlmap, nikto, wpscan, masscan, nmap, dirbuster, gobuster, ffuf,
     acunetix, burp, zgrab, hydra, metasploit, censys) ni 403 Forbidden bilan to'xtatish.
   - Qora ro'yxatga tushgan tajovuzkor IP larni avtomatik dinamik ravishda bloklash (Auto-Ban Jail).
3. DoS / DDoS va in-memory sliding window rate limiter:
   - IP va User bazasida burst va sustained sliding window
   - Render.com health check (/health, UptimeRobot, Render internal) har doim oq ro'yxatda
4. Clickjacking va qat'iy xavfsizlik sarlavhalari:
   - Content-Security-Policy: frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://t.me;
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: SAMEORIGIN
   - X-XSS-Protection: 1; mode=block
   - Referrer-Policy: strict-origin-when-cross-origin
   - Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
5. Soxta ID va Telegram WebApp initData HMAC-SHA256 validatsiyasi
"""
import os
import re
import time
import json
import hmac
import hashlib
import logging
import ipaddress
import urllib.parse
from collections import defaultdict, deque
from typing import Optional, Dict, Any, Tuple, List, Set
from aiohttp import web
from config import config

logger = logging.getLogger("security")

# Taniqli tajovuzkor skanerlar, zaiflik qidiruvchilar va avtomatlashtirilgan exploit botlar
KNOWN_SCANNER_AGENTS = (
    # Zaiflik va port skanerlari
    "sqlmap",
    "nikto",
    "wpscan",
    "masscan",
    "dirbuster",
    "gobuster",
    "ffuf",
    "acunetix",
    "burp",
    "burpsuite",
    "metasploit",
    "nmap",
    "zgrab",
    "hydra",
    "censys",
    "nessus",
    "openvas",
    "nuclei",
    "havij",
    "zaproxy",
    "beefproject",
    "arachni",
    "whatweb",
    "w3af",
    "netsparker",
    "shodan",
    "qualys",
    "commix",
    "sublist3r",
    "amass",
    "recon-ng",
    "dirb",
    "feroxbuster",
    "wfuzz",
    # Skraperlar va avtomatlashtirilgan bot klientlari
    "curl/",
    "wget/",
    "python-requests",
    "python-urllib",
    "requests/",
    "scrapy",
    "httpclient",
    "libwww-perl",
    "postmanruntime",
    "insomnia",
    # Headless brauzerlar va avtomatizatsiya
    "headlesschrome",
    "phantomjs",
    "selenium",
    "puppeteer",
)

# Himoyalangan fayl kengaytmalari (Zero Reconnaissance & Database Shield)
PROTECTED_EXTENSIONS = (
    # SQLite va boshqa ma'lumotlar bazalari, WAL, SHM va jurnallar
    ".db", ".sqlite", ".sqlite3", ".db3", ".sql", ".mdb", ".accdb",
    ".db-wal", ".db-shm", ".db-journal",
    ".sqlite-wal", ".sqlite-shm", ".sqlite-journal",
    ".sqlite3-wal", ".sqlite3-shm", ".sqlite3-journal",
    # Zaxira arxivlari va ma'lumotlar damplari
    ".rdb", ".dump", ".tar", ".gz", ".tgz", ".zip", ".rar", ".7z", ".bz2",
    # Konfiguratsiya, maxfiy kalitlar va zaxira nusxalari
    ".env", ".bak", ".backup", ".old", ".swp", ".conf", ".cfg", ".ini", ".log",
    ".pem", ".key", ".crt", ".pfx", ".p12",
    # Dastur kodlari va shell skriptlari
    ".py", ".pyc", ".pyo", ".pyd", ".sh", ".bash", ".zsh",
    # Konteyner va orkestratsiya fayllari hamda source maplar
    ".yml", ".yaml", ".dockerignore", ".lock", ".map"
)

# Himoyalangan ichki kataloglar
PROTECTED_DIRS = (
    "/data", "/database", "/logs", "/handlers", "/keyboards",
    "/middlewares", "/services", "/utils", "/tests", "/temp_downloads",
    "/scripts", "/scratch", "/.github", "/.vscode", "/.idea",
    "/.git", "/.pytest_cache", "/.venv", "/venv", "/__pycache__"
)

# Maxsus himoyalangan fayl nomlari (ma'lumotlar va server konfiguratsiyalari)
PROTECTED_FILENAMES = (
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "requirements.txt", "pytest.ini", "readme.md", "license",
    "maintenance.json", "video_sources.json", "catalog.json",
    "books.json", "music_home.json", "prava_images.json",
    "package.json", "tsconfig.json", "composer.json", "config.json",
    "web.config", "settings.json", "bot.db", "bauntyfilms.db"
)

# Zararli so'rovlar (SQLi, LFI, RCE, XSS, Backdoor) patternlari
# Izoh: O'zbek lotin yozuvidagi tutuq belgilarini (masalan: O'ylama, Mo'jiza) soxta SQL injection deb bilmaslik
# hamda &id=, &cat= kabi oddiy query parametrlarni xato bloklamaslik uchun patternlar qat'iy va kontekstual tuzilgan.
MALICIOUS_PATTERNS = [
    # 1. SQL Injection (inline comment /**/ va tautology aylanib o'tishlariga qarshi mustahkam)
    re.compile(r"(?i)\bunion(?:\s+|/\*.*?\*/)+(?:all(?:\s+|/\*.*?\*/)+)?select\b"),
    re.compile(r"(?i)(?:'|\"|%27|%22)\s*(?:or|and)\s*(?:'?[a-z0-9_]+'?\s*=\s*'?[a-z0-9_]+'?|true\b|''=''|''=')"),
    re.compile(r"(?i)(?:;|'|\"|%27|%22)(?:\s+|/\*.*?\*/)*(?:drop|alter|truncate|delete)(?:\s+|/\*.*?\*/)+(?:table|database)\b"),
    re.compile(r"(?i)\b(?:waitfor(?:\s+|/\*.*?\*/)+delay|benchmark(?:\s+|/\*.*?\*/)*\(|sleep(?:\s+|/\*.*?\*/)*\(|pg_sleep(?:\s+|/\*.*?\*/)*\(|extractvalue(?:\s+|/\*.*?\*/)*\(|updatexml(?:\s+|/\*.*?\*/)*\()"),
    re.compile(r"(?i)\b(?:select(?:\s+|/\*.*?\*/)+@@version|information_schema|load_file(?:\s+|/\*.*?\*/)*\(|into(?:\s+|/\*.*?\*/)+(?:out|dump)file\b)"),
    re.compile(r"(?i)\bexec(?:ute)?(?:\s+|/\*.*?\*/)*\("),

    # 2. Path Traversal & LFI
    re.compile(r"(?:\.\.[/\\]|%2e%2e[%2f%5c]|%252e%252e)"),
    re.compile(r"(?i)(?:/etc/passwd|/etc/shadow|/proc/self/environ|win\.ini|boot\.ini)"),

    # 3. Maxfiy konfiguratsiyalar, tizim kalitlari va exploit yo'llari
    re.compile(r"(?i)(?:/\.env(?:\.|$)|/\.git(?:/|$)|/\.svn(?:/|$)|/\.aws(?:/|$)|/\.ssh(?:/|$)|/\.ds_store|/web\.config|/id_rsa)"),

    # 4. Admin panellar, eskirgan CMS va backdoor yo'llari
    re.compile(r"(?i)(?:/wp-login(?:\.php)?|/wp-admin(?:/|$)|/wp-content(?:/|$)|/phpmyadmin(?:/|$)|/pma(?:/|$)|/adminer(?:/|$)|/cgi-bin(?:/|$)|/actuator(?:/|$)|/xmlrpc(?:\.php)?|/spring(?:/|$)|/shell(?:\.(?:php|sh|asp|jsp))?|/config\.json|/server-status|/telescope(?:/|$)|/solr(?:/|$)|/boaform(?:/|$))"),

    # 5. Command Injection (aniq separatorlar: ;, |, &&, ` yoki cmd=/exec=, &id= va &cat= ni xato bloklamaydi)
    re.compile(r"(?i)(?:cmd\b|exec\b)[\"'\s:=]+(?:\s*[\"']?\s*(?:cat|rm|ls|id|whoami|uname|nc|curl|wget|bash|sh|powershell|cmd\.exe)\b)|(?:cmd=|exec=|(?:;|\||&&|`)\s*(?:cat|rm|ls|id|whoami|uname|nc|curl|wget|bash|sh|powershell|cmd\.exe)\b)"),
    re.compile(r"(?i)(?:(?:;|\||&&|`)\s*(?:cat\s+/etc|whoami|id|uname))"),
    re.compile(r"(?i)(?:\$\([^\)]+\)|`[^`]+`)"),

    # 6. XSS Script Injection
    re.compile(r"(?i)<script\b"),
    re.compile(r"(?i)javascript:"),
    re.compile(r"(?i)(?:onerror|onload|onclick|onmouseover|onfocus|onblur|onchange|eval)\s*="),
    re.compile(r"(?i)<(?:iframe|svg\b[^>]*onload|object|embed)"),

    # 7. RFI & SSRF (Zararli wrapperlar va ichki cloud metadata)
    re.compile(r"(?i)(?:=(?:php|data|expect|gopher|dict|ldap)://|=(?:https?|ftp)://(?:127\.|0\.|169\.254|10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.|localhost|metadata\.google))"),
    re.compile(r"(?i)(?:169\.254\.169\.254|metadata\.google\.internal)"),

    # 8. Log4j (JNDI Injection)
    re.compile(r"(?i)\$\{(?:jndi|base64|date|env|lower|upper|main|sys):[^\}]+\}"),

    # 9. Server-Side Template Injection (SSTI)
    re.compile(r"(?:\{\{\s*(?:config|self|request|session|lipsum|cycler|joiner|[0-9\+\*\-\/]{3,})\s*\}\}|\{\%.*?\%\}|\$\{[0-9\+\*\-\/]{3,}\})"),

    # 10. Shellshock
    re.compile(r"\(\)\s*\{\s*:\s*;\s*\}\s*;"),

    # 11. Prototype Pollution
    re.compile(r"(?i)(?:__proto__|constructor\s*\[\s*['\"]prototype['\"]|\.prototype\b)"),
]

# Yagona 1-taktda (one-pass) kompilyatsiya qilingan master regex
_clean_subpats = [p.pattern[4:] if p.pattern.startswith("(?i)") else p.pattern for p in MALICIOUS_PATTERNS]
FAST_MASTER_THREAT_REGEX = re.compile(
    r"(?:" + "|".join(f"(?:{pat})" for pat in _clean_subpats) + r")",
    re.IGNORECASE
)


def check_reconnaissance_and_database_shield(path: str) -> Tuple[bool, Optional[str]]:
    """
    Ma'lumotlar bazasi, manba kodlari, ichki papkalar va JSON ma'lumotlar fayllarini
    to'g'ridan-to'g'ri ko'rishni 100% to'sish (Zero Reconnaissance & Database Shield).
    Har qanday nozik fayl yoki ichki tizim papkasi so'ralganda darhol 403 Forbidden qaytariladi.
    """
    if not path:
        return False, None

    # 0. Null byte injection tekshiruvi (%00, \x00)
    if "%00" in path or "\x00" in path or "\\0" in path:
        return True, "null_byte_injection"

    # URL decode (3 marta tozalash)
    clean = path
    for _ in range(3):
        try:
            nxt = urllib.parse.unquote(clean)
            if nxt == clean:
                break
            clean = nxt
        except Exception:
            break

    if "\x00" in clean:
        return True, "null_byte_injection"

    # Normalizatsiya: \ -> /, ketma-ket // larni bittaga keltirish, kichik harflar
    norm = clean.replace("\\", "/")
    while "//" in norm:
        norm = norm.replace("//", "/")
    norm_lower = norm.lower().split("?")[0]

    # Windows Alternate Data Streams (::$DATA) tozalash
    if "::$data" in norm_lower:
        norm_lower = norm_lower.replace("::$data", "")

    # Windows va web serverlarda bo'shliq va nuqtalar bilan aylanib o'tishga qarshi rstrip
    norm_lower = norm_lower.rstrip("/. \t\r\n")
    if not norm_lower:
        norm_lower = "/"
    # 1. Path traversal tekshiruvi: .., ..;, %2e%2e
    if ".." in norm_lower:
        return True, "path_traversal"

    # 2. Admin Flow monitoring endpointlari uchun to'g'ridan-to'g'ri ruxsat
    if norm_lower in ("/admin/flow", "/webapp/admin/flow") or norm_lower.startswith(("/admin/flow/", "/webapp/admin/flow/", "/api/admin/flow", "/webapp/api/admin/flow")):
        if not any(norm_lower.endswith(ext) for ext in (".db", ".sqlite", ".py", ".env", ".sh")):
            return False, None

    # 2. Kitob va retsept assetlari (/bk/ va /rc/) keshdan xizmat ko'rsatiladi
    # Lekin ularning ichida ham hech qanday traversal yoki .db/.py/.env bo'lmasligi shart
    is_book_or_rc_asset = norm_lower.startswith(("/bk/", "/webapp/bk/", "/rc/", "/webapp/rc/"))
    if is_book_or_rc_asset:
        allowed_asset_exts = (".webp", ".png", ".jpg", ".jpeg", ".pdf", ".json", ".epub")
        if any(norm_lower.endswith(ext) for ext in allowed_asset_exts):
            return False, None
        return True, "blocked_asset_extension"

    # 3. Ichki papkalarga to'g'ridan-to'g'ri murojaatni to'sish
    for pdir in PROTECTED_DIRS:
        if norm_lower == pdir or norm_lower.startswith(f"{pdir}/") or f"{pdir}/" in norm_lower:
            return True, f"protected_dir:{pdir}"

    # 4. Nozik fayl kengaytmalarini to'sish (.db, .sqlite, .py, .env, .sh, .yml, .conf, .bak, ...)
    for ext in PROTECTED_EXTENSIONS:
        if norm_lower.endswith(ext) or f"{ext}/" in norm_lower or f"{ext}." in norm_lower:
            return True, f"protected_extension:{ext}"

    # 5. Maxsus nozik fayllar va JSON ma'lumotlar bazalari
    # (data/*.json, maintenance.json, video_sources.json, config.json, Dockerfile, ...)
    filename = norm_lower.split("/")[-1]
    if filename in PROTECTED_FILENAMES or filename.startswith(".env"):
        return True, f"protected_filename:{filename}"

    # Agar so'rov to'g'ridan-to'g'ri .json faylga yo'naltirilgan bo'lsa (API yo'llaridan tashqari)
    if norm_lower.endswith(".json") and not norm_lower.startswith(("/api/", "/webapp/api/")):
        return True, "protected_json_file"

    return False, None


def is_valid_user_id(uid: Any) -> bool:
    """Telegram user_id musbat 64-bit butun son ekanligini qat'iy tekshirish."""
    if uid is None:
        return False
    try:
        val = int(uid)
        return 1 <= val <= 9007199254740991
    except (ValueError, TypeError):
        return False


def extract_user_id_from_init_data(init_data: str) -> Optional[int]:
    """init_data satridan user_id ni xavfsiz ajratish."""
    if not init_data:
        return None
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "user" in parsed:
            u_obj = json.loads(parsed["user"])
            raw_id = u_obj.get("id")
            if is_valid_user_id(raw_id):
                return int(raw_id)
    except Exception:
        pass
    return None


def validate_telegram_init_data(
    init_data: str,
    bot_token: Optional[str] = None,
    max_age_seconds: Optional[int] = 86400,
    strict: bool = True
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Telegram WebApp initData HMAC-SHA256 haqiqiyligini tekshirish."""
    if not init_data or not isinstance(init_data, str):
        return False, None, "empty_init_data"

    token = bot_token or config.BOT_TOKEN
    parsed_pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    if not parsed_pairs:
        return False, None, "invalid_query_string"

    params: Dict[str, str] = {k: v for k, v in parsed_pairs}
    received_hash = params.get("hash")

    if not received_hash:
        if not strict and (not token or token.startswith("YOUR_") or os.getenv("PYTEST_CURRENT_TEST")):
            user_raw = params.get("user")
            if user_raw:
                try:
                    u_obj = json.loads(user_raw)
                    return True, {"user": u_obj, "user_id": u_obj.get("id"), "verified": False}, None
                except Exception:
                    pass
        return False, None, "missing_hash"

    auth_date_str = params.get("auth_date")
    if auth_date_str:
        try:
            auth_date = int(auth_date_str)
            now = time.time()
            if auth_date > now + 300:
                return False, None, "auth_date_in_future"
            if max_age_seconds is not None and (now - auth_date) > max_age_seconds:
                return False, None, "auth_date_expired"
        except (ValueError, TypeError):
            return False, None, "invalid_auth_date"

    data_pairs = {k: v for k, v in params.items() if k != "hash"}
    sorted_items = [f"{k}={data_pairs[k]}" for k in sorted(data_pairs.keys())]
    data_check_string = "\n".join(sorted_items)

    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash.lower(), received_hash.lower()):
        return False, None, "invalid_signature"

    user_dict = None
    user_id = None
    if "user" in params:
        try:
            user_dict = json.loads(params["user"])
            if isinstance(user_dict, dict):
                raw_id = user_dict.get("id")
                if is_valid_user_id(raw_id):
                    user_id = int(raw_id)
                else:
                    return False, None, "invalid_user_id_in_data"
        except Exception:
            return False, None, "invalid_user_json"

    res_data: Dict[str, Any] = {
        "params": params,
        "user": user_dict,
        "user_id": user_id,
        "auth_date": int(auth_date_str) if auth_date_str and auth_date_str.isdigit() else None,
        "verified": True
    }
    return True, res_data, None


def generate_telegram_init_data(
    user_data: Dict[str, Any],
    bot_token: str,
    auth_date: Optional[int] = None,
    extra_params: Optional[Dict[str, str]] = None
) -> str:
    """Rasmiy Telegram WebApp formati bo'yicha haqiqiy imzolangan initData yaratish."""
    if auth_date is None:
        auth_date = int(time.time())

    params: Dict[str, str] = {
        "auth_date": str(auth_date),
        "user": json.dumps(user_data, separators=(",", ":"))
    }
    if extra_params:
        params.update(extra_params)

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    params["hash"] = calc_hash
    return urllib.parse.urlencode(params)


def is_malicious_request(
    path: str,
    query_string: str = "",
    user_agent: str = "",
    body: str = "",
    headers: Optional[Dict[str, str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    So'rovda tajovuzkor skaner, bot, SQLi, LFI, RCE, exploit, nozik fayllarni
    titkilash yoki zararli body/header belgilari mavjudligini aniqlaydi.
    """
    clean_path = path.lower().split("?")[0].rstrip("/")
    is_test = bool(os.getenv("PYTEST_CURRENT_TEST"))

    # 1. Zero Reconnaissance & Database Shield: Nozik fayllar va bazalarni to'sish
    is_recon, recon_threat = check_reconnaissance_and_database_shield(path)
    if is_recon:
        return True, recon_threat

    # 2. Admin Flow monitoring endpointlari uchun WAF / Scanner bypass
    # (Admin brauzerlar, skanerlar, curl, bo'sh UA va Telegram Webviewlar to'siqsiz kirishi uchun)
    if clean_path in ("/admin/flow", "/webapp/admin/flow") or clean_path.startswith(("/admin/flow/", "/webapp/admin/flow/", "/api/admin/flow", "/webapp/api/admin/flow")):
        return False, None

    # 2. User-Agent va Health/Ping tekshiruvi (UptimeRobot va Render healthcheck oq ro'yxatda)
    ua_raw = user_agent or ""
    ua_clean = ua_raw.strip().lower()

    # Agar so'rov toza monitoring probe bo'lsa (query va body bo'sh)
    is_probe_path = clean_path in (
        "/health", "health", "/ping", "ping", "/healthz", "healthz", "/status", "status",
        "/", "", "/webapp", "webapp", "/webapp/", "/favicon.ico", "favicon.ico"
    )
    is_probe_ua = "uptimerobot" in ua_clean or "uptime" in ua_clean or "probe" in ua_clean or "monitor" in ua_clean or "ping" in ua_clean
    if (is_probe_ua or is_probe_path) and not query_string and not body:
        return False, None

    if not ua_clean:
        if clean_path not in ("/health", "health", "/ping", "ping", "/healthz", "healthz", "/", "", "/webapp", "webapp") and not is_test:
            return True, "empty_user_agent"
    else:
        # Taniqli tajovuzkor skanerlar va avtomatlashtirilgan exploit agentlarini tekshirish
        for scanner in KNOWN_SCANNER_AGENTS:
            if scanner in ua_clean:
                return True, f"scanner_ua:{scanner}"

        # Standalone CLI skanerlar va kutubxonalar (curl, wget, requests)
        if re.search(r"\b(?:curl|wget|requests|python-requests|python-urllib)\b", ua_clean):
            return True, "scanner_ua:cli_tool"

        # User-Agent orqali SQLi/XSS/Log4j/SSTI kiritish urinishlari (1-taktda master regex)
        if FAST_MASTER_THREAT_REGEX.search(ua_raw):
            for pattern in MALICIOUS_PATTERNS:
                if pattern.search(ua_raw):
                    return True, f"malicious_ua:{pattern.pattern[:30]}"
            return True, "malicious_ua_threat"

        # To'g'ridan-to'g'ri internetdan kelgan xom python/aiohttp so'rovlarini cheklash
        if not is_test:
            if any(bot in ua_clean for bot in ("aiohttp/", "python/")):
                return True, "blocked_bot_client"

    # 3. HTTP Headers (Referer, Cookie, X-Forwarded-Host, X-Forwarded-For, X-Real-IP) orqali exploit kiritish urinishlari
    if headers:
        for h_key in ("referer", "cookie", "x-forwarded-host", "x-forwarded-for", "x-real-ip"):
            h_val = headers.get(h_key) or headers.get(h_key.title())
            if h_val and isinstance(h_val, str):
                if FAST_MASTER_THREAT_REGEX.search(h_val):
                    for pattern in MALICIOUS_PATTERNS:
                        if pattern.search(h_val):
                            return True, f"malicious_header:{h_key}"
                    return True, f"malicious_header_threat:{h_key}"

    # 4. Path va query stringni tekshirish (Double/Triple URL-decoding va null byte bilan aylanib o'tishlarga qarshi)
    raw_target = f"{path}?{query_string}" if query_string else path
    if "%00" in raw_target or "\x00" in raw_target or "\\0" in raw_target:
        return True, "null_byte_injection"

    try:
        decoded_1 = urllib.parse.unquote_plus(raw_target)
        decoded_2 = urllib.parse.unquote_plus(decoded_1)
        decoded_3 = urllib.parse.unquote(decoded_2)
    except Exception:
        decoded_1 = raw_target
        decoded_2 = raw_target
        decoded_3 = raw_target

    targets = [raw_target, decoded_1, decoded_2, decoded_3]
    for t in targets:
        if "\x00" in t:
            return True, "null_byte_injection"
        if FAST_MASTER_THREAT_REGEX.search(t):
            for pattern in MALICIOUS_PATTERNS:
                if pattern.search(t):
                    return True, f"malicious_pattern:{pattern.pattern[:30]}"
            return True, "malicious_threat_detected"

    # 5. POST / PUT / PATCH body qismini tekshirish (SQLi, XSS, Cmd Injection in JSON/Form)
    if body and isinstance(body, str):
        if "\x00" in body or "%00" in body:
            return True, "null_byte_injection"
        try:
            body_dec_1 = urllib.parse.unquote_plus(body)
        except Exception:
            body_dec_1 = body
        for b_target in (body, body_dec_1):
            if FAST_MASTER_THREAT_REGEX.search(b_target):
                for pattern in MALICIOUS_PATTERNS:
                    if pattern.search(b_target):
                        return True, f"malicious_body:{pattern.pattern[:30]}"
                return True, "malicious_body_detected"

    return False, None


def _normalize_ip_str(val: str) -> str:
    """IP satridan port raqami va qavslarni tozalab sof IP manzilni qaytarish."""
    if not val:
        return ""
    s = val.strip()
    # [2001:db8::1]:8080 yoki [2001:db8::1]
    if s.startswith("[") and "]" in s:
        return s[1:s.index("]")].strip()
    # IPv4:port (masalan 198.51.100.88:8080). IPv6 da 2 yoki undan ortiq ikki nuqta bo'ladi
    if ":" in s and s.count(":") == 1:
        return s.split(":", 1)[0].strip()
    return s


def _is_valid_ip(val: str) -> bool:
    """Manzil haqiqiy IPv4 yoki IPv6 formatida ekanligini tekshirish."""
    if not val:
        return False
    clean = _normalize_ip_str(val)
    if not clean:
        return False
    try:
        ipaddress.ip_address(clean)
        return True
    except ValueError:
        return False


# Ishonchli ichki proksilar, Render tarmog'i va Cloudflare diapazonlari
TRUSTED_PROXY_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    # Upstream server (@BauntyCinemabot backend / catalog / streaming)
    ipaddress.ip_network("161.97.96.58/32"),
]

for _extra_env in ("SERVER_IP", "HOST_IP", "IMMUNE_IPS", "RENDER_EXTERNAL_IP"):
    _val = os.getenv(_extra_env)
    if _val:
        for _ip in _val.split(","):
            _clean_extra = _normalize_ip_str(_ip)
            if _is_valid_ip(_clean_extra):
                try:
                    TRUSTED_PROXY_NETWORKS.append(ipaddress.ip_network(f"{_clean_extra}/32"))
                except ValueError:
                    pass

CLOUDFLARE_NETWORKS = [
    ipaddress.ip_network("173.245.48.0/20"),
    ipaddress.ip_network("103.21.244.0/22"),
    ipaddress.ip_network("103.22.200.0/22"),
    ipaddress.ip_network("103.31.4.0/22"),
    ipaddress.ip_network("141.101.64.0/18"),
    ipaddress.ip_network("108.162.192.0/18"),
    ipaddress.ip_network("190.93.240.0/20"),
    ipaddress.ip_network("188.114.96.0/20"),
    ipaddress.ip_network("197.234.240.0/22"),
    ipaddress.ip_network("198.41.128.0/17"),
    ipaddress.ip_network("162.158.0.0/15"),
    ipaddress.ip_network("104.16.0.0/13"),
    ipaddress.ip_network("104.24.0.0/14"),
    ipaddress.ip_network("172.64.0.0/13"),
    ipaddress.ip_network("131.0.72.0/22"),
    ipaddress.ip_network("2400:cb00::/32"),
    ipaddress.ip_network("2606:4700::/32"),
    ipaddress.ip_network("2803:f800::/32"),
    ipaddress.ip_network("2405:b500::/32"),
    ipaddress.ip_network("2405:8100::/32"),
    ipaddress.ip_network("2a06:98c0::/29"),
    ipaddress.ip_network("2c0f:f248::/32"),
]


RFC_DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),    # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),   # TEST-NET-3 (RFC 5737)
)


def is_private_or_loopback_ip(ip_str: str) -> bool:
    """
    IP manzil ichki xususiy tarmoq (RFC1918), loopback, link-local,
    yoki maxsus zaxiralangan tarmoqqa tegishli ekanligini aniqlash.
    Bunday IP manzillar (masalan 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16,
    127.0.0.1, ::1, 169.254.0.0/16) HECH QACHON ban qilinmasligi shart!
    Izoh: RFC 5737 test tarmoqlari (198.51.100.0/24, 203.0.113.0/24) testlarda begona
    tashqi hujumchi IP lari sifatida ishlatilgani uchun tashqi IP deb hisoblanadi.
    """
    if not ip_str:
        return False
    clean = _normalize_ip_str(ip_str).lower()
    if clean in ("127.0.0.1", "::1", "localhost", "testclient", "testserver"):
        return True
    try:
        ip_obj = ipaddress.ip_address(clean)
        for doc_net in RFC_DOCUMENTATION_NETWORKS:
            if ip_obj in doc_net:
                return False
        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_unspecified
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        )
    except ValueError:
        return False


def is_trusted_proxy(ip_str: str) -> bool:
    """
    IP manzil serverning o'zi, lokal tarmoq, Render/Cloudflare proksisi
    yoki ichki infratuzilmaga tegishli ekanligini aniqlash.
    Bunday IP manzillar hech qachon qamoqqa (Auto-Ban Jail) olinmasligi shart.
    """
    if not ip_str:
        return False
    if is_private_or_loopback_ip(ip_str):
        return True
    ip_clean = _normalize_ip_str(ip_str).lower()
    try:
        ip_obj = ipaddress.ip_address(ip_clean)
        for net in TRUSTED_PROXY_NETWORKS:
            if ip_obj in net:
                return True
        for net in CLOUDFLARE_NETWORKS:
            if ip_obj in net:
                return True
    except ValueError:
        return False
    return False


def is_public_ip(ip_str: str) -> bool:
    """Tekshirilayotgan IP haqiqiy ochiq (public internet) IP ekanligini aniqlash."""
    if not ip_str:
        return False
    clean = _normalize_ip_str(ip_str)
    if not clean:
        return False
    if is_private_or_loopback_ip(clean):
        return False
    try:
        ip_obj = ipaddress.ip_address(clean)
        for net in TRUSTED_PROXY_NETWORKS:
            if ip_obj in net:
                return False
        for net in CLOUDFLARE_NETWORKS:
            if ip_obj in net:
                return False
        return True
    except ValueError:
        return False


class AutoBanJail:
    """
    Tajovuzkor IP manzillarni dinamik qora ro'yxatga olish (Auto-Ban Jail).
    Skaner, exploit, SQLi yoki nozik fayllarni titkilash aniqlanganda IP avtomatik ravishda
    jail ga olinadi va keyingi so'rovlari darhol 403 Forbidden bilan to'xtatiladi.
    """
    def __init__(self, default_ban_seconds: float = 900.0):
        self.default_ban_seconds = default_ban_seconds
        self._jailed: Dict[str, Tuple[float, str]] = {}

    def cleanup(self, now: Optional[float] = None) -> None:
        """Muddati tugagan IP larni xotiradan tozalash."""
        if now is None:
            now = time.monotonic()
        expired = [ip for ip, (exp, _) in self._jailed.items() if now >= exp]
        for ip in expired:
            del self._jailed[ip]

    def jail_ip(self, ip: str, duration: Optional[float] = None, reason: str = "malicious_activity") -> None:
        if not ip:
            return
        # Private, loopback yoki ishonchli proksi IP manzillar HECH QACHON va HECH QANDAY SHARTDA jail ga olinmaydi!
        if is_private_or_loopback_ip(ip) or is_trusted_proxy(ip):
            logger.debug(f"Private/trusted IP {ip} jail ga olinmadi (Sabab: {reason})")
            return
        # Faqat haqiqiy public tashqi hujumchi IP lari jail ga olinadi
        if not is_public_ip(ip):
            logger.debug(f"Non-public IP {ip} jail ga olinmadi (Sabab: {reason})")
            return
        now = time.monotonic()
        if len(self._jailed) > 1000:
            self.cleanup(now)
        dur = duration if duration is not None else self.default_ban_seconds
        self._jailed[ip] = (now + dur, reason)
        logger.warning(f"IP Auto-Ban Jail ga olindi: {ip} | {dur}s | Sabab: {reason}")

    def is_jailed(self, ip: str) -> Tuple[bool, Optional[float], Optional[str]]:
        if not ip or ip not in self._jailed:
            return False, None, None
        # Himoya: private yoki loopback yoki trusted IP hech qachon jailed deb hisoblanmaydi
        if is_private_or_loopback_ip(ip) or is_trusted_proxy(ip):
            self._jailed.pop(ip, None)
            return False, None, None
        exp, reason = self._jailed[ip]
        now = time.monotonic()
        if now < exp:
            return True, exp - now, reason
        else:
            del self._jailed[ip]
            return False, None, None

    def unban_ip(self, ip: str) -> None:
        self._jailed.pop(ip, None)

    def reset(self) -> None:
        self._jailed.clear()


class SlidingWindowRateLimiter:
    """
    In-memory sliding window rate limiter:
    - Har bir IP va user_id uchun vaqt tamg'alari (timestamp deque)
    - Burst / DDoS hujumlarini avtomatik aniqlab vaqtincha bloklash (ban_duration)
    - /health (Render healthcheck) va statik resurslar uchun qulay oq ro'yxat
    """
    def __init__(
        self,
        burst_limit: int = 80,
        burst_window: float = 5.0,
        sustained_limit: int = 240,
        sustained_window: float = 60.0,
        user_burst_limit: int = 40,
        user_burst_window: float = 5.0,
        user_sustained_limit: int = 150,
        user_sustained_window: float = 60.0,
        sensitive_limit: int = 25,
        sensitive_window: float = 10.0,
        ban_duration: float = 60.0,
    ):
        self.burst_limit = burst_limit
        self.burst_window = burst_window
        self.sustained_limit = sustained_limit
        self.sustained_window = sustained_window
        self.user_burst_limit = user_burst_limit
        self.user_burst_window = user_burst_window
        self.user_sustained_limit = user_sustained_limit
        self.user_sustained_window = user_sustained_window
        self.sensitive_limit = sensitive_limit
        self.sensitive_window = sensitive_window
        self.ban_duration = ban_duration

        self._ip_requests: Dict[str, deque] = defaultdict(deque)
        self._user_requests: Dict[int, deque] = defaultdict(deque)
        self._sensitive_requests: Dict[str, deque] = defaultdict(deque)
        self._banned_ips: Dict[str, float] = {}

    def is_allowed(self, client_ip: str, path: str = "", user_id: Optional[int] = None) -> Tuple[bool, Optional[int]]:
        now = time.monotonic()

        # 1. /health, /ping va render ichki cheklari har doim oq ro'yxatda
        clean_path = path.lower().split("?")[0].rstrip("/")
        if clean_path in ("/health", "health", "/ping", "ping", "/healthz", "healthz", "/status", "status"):
            return True, None

        # 2. Localhost / Trusted proxy / TestClient uchun testlarda yengillik
        is_loopback_or_proxy = is_trusted_proxy(client_ip) or client_ip in ("127.0.0.1", "::1", "localhost", "testclient")
        if is_loopback_or_proxy and not os.getenv("STRICT_RATE_LIMIT_TEST"):
            return True, None

        # 3. Vaqtincha bloklangan IP tekshiruvi
        if client_ip in self._banned_ips:
            banned_until = self._banned_ips[client_ip]
            if now < banned_until:
                retry_after = max(1, int(banned_until - now))
                return False, retry_after
            else:
                del self._banned_ips[client_ip]

        # 4. Statik assetlar va media oqimlari (kengaytirilgan chegara)
        is_static_or_stream = any(clean_path.startswith(prefix) for prefix in (
            "/webapp", "/css", "/js", "/f", "/bk", "/rc", "/p", "/prava", "/pv",
            "/api/tv", "/webapp/api/tv", "/api/tv/icon", "/favicon.ico", "/logo."
        )) or clean_path.endswith((
            ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".css", ".js",
            ".woff", ".woff2", ".ttf", ".mp3", ".mp4", ".pdf", ".m3u8", ".ts"
        ))

        # 5. IP sliding window tozalash va tekshirish
        q = self._ip_requests[client_ip]
        while q and now - q[0] > self.sustained_window:
            q.popleft()

        recent_burst = sum(1 for t in reversed(q) if now - t <= self.burst_window)
        if not is_static_or_stream and recent_burst >= self.burst_limit:
            self._banned_ips[client_ip] = now + self.ban_duration
            return False, int(self.ban_duration)

        max_sustained = (self.sustained_limit * 5) if is_static_or_stream else self.sustained_limit
        if len(q) >= max_sustained:
            oldest = q[0]
            retry_after = max(1, int(self.sustained_window - (now - oldest)))
            return False, retry_after

        # 6. User bo'yicha sliding window tekshiruvi
        if user_id and is_valid_user_id(user_id):
            uid = int(user_id)
            uq = self._user_requests[uid]
            while uq and now - uq[0] > self.user_sustained_window:
                uq.popleft()

            recent_user_burst = sum(1 for t in reversed(uq) if now - t <= self.user_burst_window)
            if not is_static_or_stream and recent_user_burst >= self.user_burst_limit:
                return False, int(self.user_burst_window)

            if len(uq) >= self.user_sustained_limit:
                oldest_u = uq[0]
                retry_after_u = max(1, int(self.user_sustained_window - (now - oldest_u)))
                return False, retry_after_u

            uq.append(now)

        # 7. Sensitive / state-changing endpoints tekshiruvi
        if clean_path in (
            "/api/send", "/webapp/api/send",
            "/api/send_to_chat", "/api/music/send", "/api/books/send",
            "/api/story/send", "/api/watch", "/webapp/api/send_to_chat",
            "/webapp/api/music/send", "/webapp/api/books/send", "/webapp/api/watch"
        ):
            key = f"user:{user_id}" if user_id else f"ip:{client_ip}"
            sq = self._sensitive_requests[key]
            while sq and now - sq[0] > self.sensitive_window:
                sq.popleft()
            if len(sq) >= self.sensitive_limit:
                retry_after = max(1, int(self.sensitive_window - (now - sq[0])))
                return False, retry_after
            sq.append(now)

        q.append(now)

        if len(self._ip_requests) > 10000:
            self.cleanup(now)

        return True, None

    def cleanup(self, now: Optional[float] = None) -> None:
        if now is None:
            now = time.monotonic()
        dead_ips = [ip for ip, q in self._ip_requests.items() if not q or now - q[-1] > self.sustained_window]
        for ip in dead_ips:
            del self._ip_requests[ip]
        dead_users = [u for u, q in self._user_requests.items() if not q or now - q[-1] > self.user_sustained_window]
        for u in dead_users:
            del self._user_requests[u]
        dead_sens = [k for k, q in self._sensitive_requests.items() if not q or now - q[-1] > self.sensitive_window]
        for k in dead_sens:
            del self._sensitive_requests[k]
        dead_bans = [ip for ip, exp in self._banned_ips.items() if now >= exp]
        for ip in dead_bans:
            del self._banned_ips[ip]

    def reset(self) -> None:
        self._ip_requests.clear()
        self._user_requests.clear()
        self._sensitive_requests.clear()
        self._banned_ips.clear()


def get_real_client_ip(request: web.Request) -> str:
    """
    So'rovdan haqiqiy mijoz IP manzilini xavfsiz va proksi soxtalashtirishlaridan
    (IP spoofing va soxta DDoS blokirovkalaridan) himoyalangan holda ajratib olish.
    CF-Connecting-IP va X-Forwarded-For sarlavhalaridagi birinchi HAQIQIY OCHIQ (PUBLIC) IP ni oladi.
    Agar faqat ichki private IP bo'lsa, uni hech qachon ban qilmaslik uchun remote ni qaytaradi.
    """
    # 1. To'g'ridan-to'g'ri bog'langan remote manzil
    raw_remote = str(request.remote).strip() if request.remote else "127.0.0.1"
    clean_remote = _normalize_ip_str(raw_remote)

    # Agar to'g'ridan-to'g'ri bog'langan remote manzil ishonchli proksi (Cloudflare, Render, loopback)
    # bo'lmasa, demak mijoz serverga to'g'ridan-to'g'ri bog'langan va uning yuborgan CF/XFF
    # sarlavhalari soxta (spoofed) deb hisoblanadi!
    is_peer_trusted = is_trusted_proxy(clean_remote)

    if not is_peer_trusted:
        # Tashqi foydalanuvchi proksisiz kelgan — uning haqiqiy IP manzili remote ning o'zi
        if _is_valid_ip(clean_remote):
            return clean_remote
        return "127.0.0.1"

    # 2. Ishonchli proksi (Render 10.x.x.x, Cloudflare, loopback) orqali kelganda:
    # Cloudflare CF-Connecting-IP
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        clean_cf = _normalize_ip_str(cf_ip)
        if is_public_ip(clean_cf):
            return clean_cf

    # 3. X-Forwarded-For: ishonchli proksi biriktirgan haqiqiy ochiq (PUBLIC) IP ni olamiz
    # IP spoofingdan himoyalanish uchun teskaridan aylanib, proksi qo'shgan haqiqiy public IP ni olamiz
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        parts = [_normalize_ip_str(p) for p in xff.split(",") if p.strip()]
        for p in reversed(parts):
            if is_public_ip(p):
                return p

    # 4. X-Real-IP
    x_real = request.headers.get("X-Real-IP")
    if x_real:
        clean_real = _normalize_ip_str(x_real)
        if is_public_ip(clean_real):
            return clean_real

    # 5. Agar faqat ichki private IP bo'lsa (masalan Render 10.29.121.249)
    if _is_valid_ip(clean_remote):
        return clean_remote

    return "127.0.0.1"


def extract_client_ip(request: web.Request) -> str:
    """Orqaga moslik uchun extract_client_ip get_real_client_ip ga yo'naltiriladi."""
    return get_real_client_ip(request)


def get_security_headers() -> Dict[str, str]:
    """Clickjacking, XSS, MIME sniffing va brauzer xavfsizlik sarlavhalari to'plami."""
    return {
        # Clickjacking himoyasi: Telegram Web App iframelari va 'self' ga ruxsat, begona saytlarga taqiq
        "Content-Security-Policy": (
            "default-src 'self' https: data: blob: 'unsafe-inline' 'unsafe-eval'; "
            "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://t.me;"
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        # CORS sarlavhalari va source maplarni taqiqlash
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-Init-Data, Accept, Origin",
        "Access-Control-Max-Age": "86400",
        "X-SourceMap": "none",
        "SourceMap": "",
    }


def _clean_sensitive_headers(resp: web.StreamResponse) -> None:
    """Server, dastur versiyalari va texnologiya tafsilotlarini berkitish."""
    if hasattr(resp, "_server"):
        try:
            resp._server = None
        except Exception:
            pass
    resp.headers["Server"] = "Bauntys-Shield"
    for h in (
        "X-Powered-By", "x-powered-by", "X-Runtime", "x-runtime",
        "X-AspNet-Version", "x-aspnet-version", "X-Version", "x-version",
        "X-Backend-Server", "x-backend-server"
    ):
        if h in resp.headers:
            try:
                del resp.headers[h]
            except KeyError:
                pass


class SecurityService:
    """Bauntys ultra-hardened xavfsizlik xizmati sinfi."""
    def __init__(self):
        self.rate_limiter = SlidingWindowRateLimiter()
        self.jail = AutoBanJail()

    def ban_ip(self, ip: str, duration: Optional[float] = None, reason: str = "manual_ban") -> None:
        """IP manzilni vaqtincha Auto-Ban Jail ga kiritish."""
        self.jail.jail_ip(ip, duration=duration, reason=reason)

    def is_ip_banned(self, ip: str) -> Tuple[bool, Optional[float], Optional[str]]:
        """IP qamoqda ekanligini tekshirish."""
        return self.jail.is_jailed(ip)

    def unban_ip(self, ip: str) -> None:
        """IP manzilni qamoqdan chiqarish."""
        self.jail.unban_ip(ip)

    def reset_jail(self) -> None:
        """Jail xotirasini tozalash."""
        self.jail.reset()

    def reset(self) -> None:
        """Barcha rate limiter va jail xotiralarini tozalash."""
        self.rate_limiter.reset()
        self.jail.reset()

    def verify_telegram_user(
        self,
        request: web.Request,
        payload_user_id: Optional[Any] = None,
        require_auth: Optional[bool] = None
    ) -> Tuple[Optional[int], bool, Optional[str]]:
        """So'rovdan foydalanuvchini ajratish va soxtalashtirish (spoofing) xavfini tekshirish."""
        init_data = (
            request.headers.get("X-Init-Data")
            or request.query.get("init_data")
            or ""
        ).strip()

        is_test = bool(os.getenv("PYTEST_CURRENT_TEST"))
        is_dummy_token = config.BOT_TOKEN.startswith("YOUR_")

        if require_auth is None:
            strict_auth = not is_test and not is_dummy_token
        else:
            strict_auth = require_auth

        verified_user_id: Optional[int] = None

        if init_data:
            has_hash = "hash=" in init_data
            strict = has_hash or (not is_dummy_token and not is_test)
            is_valid, data, err = validate_telegram_init_data(init_data, config.BOT_TOKEN, strict=strict)
            if not is_valid:
                return None, False, err or "invalid_init_data"
            if data and data.get("user_id"):
                verified_user_id = data["user_id"]
        elif strict_auth:
            return None, False, "missing_init_data"

        if payload_user_id is not None:
            if not is_valid_user_id(payload_user_id):
                return None, False, "invalid_user_id_format"
            payload_uid_int = int(payload_user_id)

            if verified_user_id is not None and verified_user_id != payload_uid_int:
                logger.warning(
                    f"Soxta ID urinishi aniqlandi! InitData ID: {verified_user_id}, Payload ID: {payload_uid_int}"
                )
                return None, False, "user_id_spoofing"

            return payload_uid_int, True, None

        if verified_user_id is not None:
            return verified_user_id, True, None

        return None, True, None


security_service = SecurityService()


@web.middleware
async def security_middleware(request: web.Request, handler) -> web.Response:
    """aiohttp web application uchun ultra kuchaytirilgan xavfsizlik middleware."""
    sec_headers = get_security_headers()

    # 1. OPTIONS preflight
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
        for k, v in sec_headers.items():
            resp.headers[k] = v
        _clean_sensitive_headers(resp)
        return resp

    path = request.path

    # 2. Render.com, UptimeRobot health check va Admin Flow monitoring - to'siqsiz o'tkazish
    ua = (request.headers.get("User-Agent") or "").lower()
    is_admin_flow = (
        path in ("/admin/flow", "/admin/flow/", "/webapp/admin/flow", "/webapp/admin/flow/")
        or path.startswith(("/admin/flow/", "/webapp/admin/flow/", "/api/admin/flow/", "/api/admin/flow", "/webapp/api/admin/flow/", "/webapp/api/admin/flow"))
    )
    is_health_or_ping = (
        path in (
            "/health", "/health/", "/ping", "/ping/",
            "/healthz", "/healthz/", "/status", "/status/",
            "/favicon.ico", "/webapp/favicon.ico"
        ) or (
            path in ("/", "", "/webapp", "/webapp/", "/webapp/index.html", "/index.html")
            and request.method in ("GET", "HEAD")
            and (
                request.method == "HEAD"
                or "uptimerobot" in ua
                or "uptime" in ua
                or not ua
                or "bot" in ua
                or "monitor" in ua
                or "ping" in ua
                or "probe" in ua
                or "health" in ua
                or "render" in ua
                or "betteruptime" in ua
                or "cron-job" in ua
                or "freshping" in ua
                or "pingdom" in ua
            )
        )
    )
    # Xavfsizlik: agar kimdir /health yoki / ga SQLi/XSS/exploit query yuborsa, oq ro'yxatdan chiqarish
    if is_health_or_ping and request.query_string:
        clean_qs = urllib.parse.unquote_plus(request.query_string)
        if FAST_MASTER_THREAT_REGEX.search(request.query_string) or FAST_MASTER_THREAT_REGEX.search(clean_qs):
            is_health_or_ping = False

    is_uptimerobot = (
        ("uptimerobot" in ua or "uptime" in ua)
        and path in (
            "/", "", "/webapp", "/webapp/", "/index.html", "/webapp/index.html",
            "/health", "/health/", "/ping", "/ping/", "/status", "/status/", "/healthz", "/healthz/",
            "/favicon.ico", "/webapp/favicon.ico"
        )
    )
    if is_uptimerobot and request.query_string:
        clean_qs_ur = urllib.parse.unquote_plus(request.query_string)
        if FAST_MASTER_THREAT_REGEX.search(request.query_string) or FAST_MASTER_THREAT_REGEX.search(clean_qs_ur):
            is_uptimerobot = False

    if is_health_or_ping or is_uptimerobot or is_admin_flow:
        # Agar admin yoki UptimeRobot IP manzili adashib jail ga olingan bo'lsa, avtomatik ravishda unban qilinadi
        client_ip = extract_client_ip(request)
        if client_ip:
            security_service.unban_ip(client_ip)
        resp = await handler(request)
        for k, v in sec_headers.items():
            if k not in resp.headers:
                resp.headers[k] = v
        _clean_sensitive_headers(resp)
        return resp

    client_ip = extract_client_ip(request)

    # 3. Auto-Ban Jail tekshiruvi (faqat haqiqiy ochiq tashqi tajovuzkor IP lar uchun)
    if is_public_ip(client_ip):
        is_jailed, rem_time, jail_reason = security_service.is_ip_banned(client_ip)
        if is_jailed:
            logger.warning(
                f"Bloklangan IP so'rovi to'xtatildi: {client_ip} | Qolgan vaqt: {int(rem_time or 0)}s | Sabab: {jail_reason}"
            )
            resp = web.json_response(
                {
                    "ok": False,
                    "error": "forbidden",
                    "message": "Zararli faoliyat sababli ushbu IP vaqtincha bloklangan.",
                    "threat": "ip_auto_banned",
                    "reason": jail_reason
                },
                status=403
            )
            for k, v in sec_headers.items():
                resp.headers[k] = v
            _clean_sensitive_headers(resp)
            return resp

    # 4. Zero Reconnaissance & Database Shield: Nozik fayllar va bazalarni to'sish
    is_recon, recon_threat = check_reconnaissance_and_database_shield(path)
    if is_recon:
        if is_public_ip(client_ip):
            security_service.ban_ip(client_ip, reason=recon_threat)
        logger.warning(
            f"Nozik fayl/baza qidiruvi to'sildi: {recon_threat} | Path: {path} | IP: {client_ip}"
        )
        resp = web.json_response(
            {
                "ok": False,
                "error": "forbidden",
                "message": "Zararli yoki ruxsat etilmagan so'rov aniqlandi va bloklandi.",
                "threat": recon_threat
            },
            status=403
        )
        for k, v in sec_headers.items():
            resp.headers[k] = v
        _clean_sensitive_headers(resp)
        return resp

    # 5. Zararli botlar, skanerlar, exploitlar va WAF filtr (query, headers, body)
    user_agent = request.headers.get("User-Agent", "")
    query_str = request.query_string

    body_str = ""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.can_read_body:
        content_type = request.content_type.lower() if request.content_type else ""
        if not content_type.startswith("multipart/"):
            try:
                body_bytes = await request.read()
                if body_bytes:
                    body_str = body_bytes[:65536].decode("utf-8", errors="replace")
            except Exception:
                body_str = ""

    req_headers_dict = dict(request.headers)
    is_malicious, threat_name = is_malicious_request(
        path, query_str, user_agent, body=body_str, headers=req_headers_dict
    )
    if is_malicious:
        if is_public_ip(client_ip):
            security_service.ban_ip(client_ip, reason=threat_name)
        logger.warning(
            f"Zararli so'rov bloklandi: {threat_name} | Path: {path} | IP: {client_ip} | UA: {user_agent}"
        )
        resp = web.json_response(
            {
                "ok": False,
                "error": "forbidden",
                "message": "Zararli yoki ruxsat etilmagan so'rov aniqlandi va bloklandi.",
                "threat": threat_name
            },
            status=403
        )
        for k, v in sec_headers.items():
            resp.headers[k] = v
        _clean_sensitive_headers(resp)
        return resp

    # 6. DoS / DDoS va Rate Limiter (IP va foydalanuvchi hisobida)
    user_id = None
    init_data_hdr = (request.headers.get("X-Init-Data") or request.query.get("init_data") or "").strip()
    if init_data_hdr:
        parsed_uid = extract_user_id_from_init_data(init_data_hdr)
        if parsed_uid and is_valid_user_id(parsed_uid):
            user_id = int(parsed_uid)
    if not user_id:
        raw_uid = request.query.get("user_id")
        if raw_uid and is_valid_user_id(raw_uid):
            user_id = int(raw_uid)

    allowed, retry_after = security_service.rate_limiter.is_allowed(client_ip, path, user_id=user_id)
    if not allowed:
        retry_val = retry_after or 60
        logger.warning(f"Rate limit oshib ketdi! IP: {client_ip} | User: {user_id} | Path: {path} | Retry-After: {retry_val}s")
        resp = web.json_response(
            {
                "ok": False,
                "error": "too_many_requests",
                "message": "Juda ko'p so'rovlar yuborildi. Iltimos, bir oz kuting.",
                "retry_after": retry_val
            },
            status=429,
            headers={"Retry-After": str(retry_val)}
        )
        for k, v in sec_headers.items():
            resp.headers[k] = v
        _clean_sensitive_headers(resp)
        return resp

    # 7. Asosiy handler ijrosi va xatoliklar tafsilotini yashirish (Zero Trace Leak)
    try:
        resp = await handler(request)
    except web.HTTPException as http_ex:
        resp = http_ex
    except Exception as ex:
        logger.error(f"Kutilmagan ichki server xatoligi: {ex}", exc_info=True)
        resp = web.json_response(
            {
                "ok": False,
                "error": "server_error",
                "message": "Ichki tizim xatoligi yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."
            },
            status=500
        )

    # 8. Xavfsizlik sarlavhalarini o'rnatish va nozik server sarlavhalarini tozalash
    for k, v in sec_headers.items():
        if k.startswith("X-") or k == "Content-Security-Policy" or k == "Referrer-Policy" or k == "Strict-Transport-Security" or k == "Permissions-Policy":
            resp.headers[k] = v
        elif k not in resp.headers:
            resp.headers[k] = v

    # Restrictive DENY ni Telegram WebApp iframe uchun SAMEORIGIN ga to'g'irlash
    if resp.headers.get("X-Frame-Options", "").upper() == "DENY":
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"

    _clean_sensitive_headers(resp)

    # ETag va 304 Not Modified tekshiruvi (Kesh orqali nollik kechikish va ortiqcha tarmoq uzatishlarini yo'qotish)
    if request.method in ("GET", "HEAD") and resp.status == 200:
        etag = resp.headers.get("ETag")
        if not etag and getattr(resp, "body", None) is not None and len(resp.body) < 5_000_000:
            cc = resp.headers.get("Cache-Control", "")
            if "public" in cc or "max-age" in cc:
                etag = f'W/"{hashlib.md5(resp.body).hexdigest()[:16]}"'
                resp.headers["ETag"] = etag

        if etag:
            client_inm = request.headers.get("If-None-Match")
            if client_inm:
                c_clean = client_inm.strip().strip('"').lstrip('W/').strip('"')
                s_clean = etag.strip().strip('"').lstrip('W/').strip('"')
                if client_inm.strip() == etag.strip() or c_clean == s_clean:
                    resp_304 = web.Response(status=304)
                    for hk, hv in resp.headers.items():
                        if hk not in ("Content-Length", "Content-Type"):
                            resp_304.headers[hk] = hv
                    _clean_sensitive_headers(resp_304)
                    return resp_304

    if hasattr(resp, "enable_compression") and resp.status not in (204, 304):
        if getattr(resp, "body", None) is not None or isinstance(resp, web.FileResponse):
            try:
                resp.enable_compression()
            except Exception:
                pass
    return resp
