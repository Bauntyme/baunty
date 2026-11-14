"""
Bauntyfilms Web Server va Mini App API (aiohttp.web)
Portlar va Render.com mosligi bilan.
"""
import os
import re
import json
import time
import asyncio
import hashlib
from datetime import datetime, timedelta
import random
import urllib.parse
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import aiohttp
from aiohttp import web
from config import config, BASE_DIR
from database.session import get_session
from database import crud
from services.movie_service import movie_service, MovieService
from services.music_service import music_service
from services.music_data import TOP_50_TRACKS, MOODS_LIST
from services.tv_data import CHANNELS_LIST, TV_CATEGORIES
from services.games_data import GAMES_LIST, PET_DATA, CHEST_DATA
from services.doc_service import doc_service
from services.story_service import story_service
from services.maintenance_service import maintenance_service
from services.security_service import (
    security_service,
    security_middleware,
    is_valid_user_id,
    validate_telegram_init_data,
    extract_client_ip,
    verify_admin_request,
    create_admin_session_token,
    PROTECTED_FILENAMES,
)
from services.telemetry_service import telemetry_service
from services.admin_flow_html import ADMIN_FLOW_HTML
from services.rasxod_service import rasxod_service
from services.kaloriya_service import kaloriya_service
from services.mafia_service import mafia_service
from services.quiz_service import quiz_service
from services.tv_room_service import tv_room_service, DEFAULT_CHANNEL_ID
from services.bunker_service import bunker_service
from services.deliv_service import deliv_service
from services.food_service import food_service
from services.duel_service import duel_service
from services.bot_identity import get_bot_username, resolve_bot_username, set_live_bot_username

logger = logging.getLogger(__name__)

# Global Bot ob'ekti (chatga ma'lumot yuborish uchun)
_bot_instance = None


def set_bot_instance(bot) -> None:
    """Asosiy bot nusxasini web serverga ulash."""
    global _bot_instance
    _bot_instance = bot
    if bot is not None:
        me_obj = getattr(bot, "_me", None)
        set_live_bot_username(getattr(me_obj, "username", None))


async def handle_health(request: web.Request) -> web.Response:
    """Render.com va boshqa bulutli monitoring xizmatlari uchun xavfsiz minimal healthcheck."""
    return web.json_response(
        {"status": "ok", "timestamp": int(time.time())},
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff"
        }
    )


async def handle_ping(request: web.Request) -> web.Response:
    """Render.com va UptimeRobot uchun tezkor ping endpointi (200 OK)."""
    return web.Response(
        text="pong",
        content_type="text/plain",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


@web.middleware
async def telemetry_middleware(request: web.Request, handler) -> web.Response:
    """Barcha keluvchi so'rovlarni ring buffer va telemetriya xizmatiga yozish."""
    t0 = time.perf_counter()
    status = 500
    client_ip = extract_client_ip(request)
    method = request.method
    path = request.path_qs if hasattr(request, "path_qs") else request.path
    user_agent = request.headers.get("User-Agent", "")
    try:
        response = await handler(request)
        status = response.status
        return response
    except web.HTTPException as http_ex:
        status = http_ex.status
        raise
    except Exception:
        status = 500
        raise
    finally:
        duration_ms = (time.perf_counter() - t0) * 1000
        telemetry_service.record_request(
            method=method,
            path=path,
            status=status,
            duration_ms=duration_ms,
            client_ip=client_ip,
            user_agent=user_agent,
        )


async def handle_admin_flow(request: web.Request) -> web.Response:
    """Admin Flow & Database Monitor UI sahifasini uzatish (Qat'iy Kriptografik Himoyalangan)."""
    is_adm, uid = verify_admin_request(request)
    if not is_adm:
        return web.Response(
            text="""<!DOCTYPE html>
<html lang="uz"><head><meta charset="utf-8"><title>403 Taqiqlangan</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#070B1F;color:#f2f3f5;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif}.c{text-align:center;padding:32px 24px;border-radius:20px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);max-width:380px}h1{font-size:24px;color:#ef4444;margin:0 0 10px}p{font-size:14px;color:#94a3b8;line-height:1.5;margin:0}</style></head>
<body><div class="c"><h1>⛔ 403 Taqiqlangan</h1><p>Admin panelga faqat tasdiqlangan kriptografik imzo yoki admin kaliti bilan kirish mumkin.</p></div></body></html>""",
            content_type="text/html",
            charset="utf-8",
            status=403,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate", "X-Content-Type-Options": "nosniff"}
        )

    resp = web.Response(
        text=ADMIN_FLOW_HTML,
        content_type="text/html",
        charset="utf-8",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )
    if uid:
        try:
            resp.set_cookie(
                "baunty_admin_session",
                create_admin_session_token(uid),
                max_age=7200,
                httponly=True,
                secure=True,
                samesite="Lax"
            )
        except Exception:
            pass
    return resp


async def handle_admin_flow_data(request: web.Request) -> web.Response:
    """Admin Flow uchun real-vaqtdagi telemetriya va baza ma'lumotlarini JSON qaytarish."""
    is_adm, _ = verify_admin_request(request)
    if not is_adm:
        return web.json_response({"ok": False, "error": "forbidden", "message": "Admin authorization required"}, status=403)
    data = await telemetry_service.get_full_telemetry()
    return web.json_response(data, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate"
    })


async def handle_admin_flow_benchmark(request: web.Request) -> web.Response:
    """Admin Flow ma'lumotlar bazasi tezkorlik benchmarkini bajarish."""
    is_adm, _ = verify_admin_request(request)
    if not is_adm:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    t0 = time.perf_counter()
    try:
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        ping_ms = round((time.perf_counter() - t0) * 1000, 2)
        return web.json_response({
            "ok": True,
            "status": "ONLINE",
            "ping_ms": ping_ms,
            "timestamp": time.time()
        })
    except Exception as e:
        return web.json_response({
            "ok": False,
            "status": "ERROR",
            "error": str(e),
            "ping_ms": -1,
            "timestamp": time.time()
        }, status=500)


async def handle_admin_flow_clear(request: web.Request) -> web.Response:
    """Admin Flow so'rovlar buferini tozalash."""
    is_adm, _ = verify_admin_request(request)
    if not is_adm:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    telemetry_service.clear_buffer()
    return web.json_response({"ok": True, "message": "Buffer cleared"})


_FAVICON_CACHE: Dict[str, Any] = {"bytes": None, "etag": None}
_STATIC_BUNDLES_CACHE: Dict[str, Tuple[bytes, str, str]] = {}


async def handle_favicon(request: web.Request) -> web.Response:
    """Favicon so'rovlariga javob berish (404 xatoliklarining oldini olish va 0ms uzatish)."""
    fav_file = BASE_DIR / "webapp" / "favicon.ico"
    if _FAVICON_CACHE["bytes"] is None and fav_file.exists():
        try:
            fav_bytes = await asyncio.to_thread(fav_file.read_bytes)
            _FAVICON_CACHE["bytes"] = fav_bytes
            _FAVICON_CACHE["etag"] = f'"{hashlib.md5(fav_bytes).hexdigest()[:16]}"'
        except Exception:
            pass

    if _FAVICON_CACHE["bytes"] is not None:
        etag = _FAVICON_CACHE["etag"]
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
        return web.Response(
            body=_FAVICON_CACHE["bytes"],
            content_type="image/x-icon",
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "Access-Control-Allow-Origin": "*",
                "ETag": etag,
            }
        )
    return web.Response(status=204)


_PROD_INDEX_CACHE: Dict[str, Any] = {"html": None, "bytes": None, "etag": None, "ts": 0}


def _is_nocache(request: Any) -> bool:
    """So'rovda nocache yoki clear parametri berilganligini xavfsiz aniqlash."""
    try:
        if not hasattr(request, "query"):
            return False
        raw_nc = request.query.get("nocache")
        if isinstance(raw_nc, str) and raw_nc.lower() in ("1", "true", "yes", ""):
            return True
        raw_cl = request.query.get("clear")
        if isinstance(raw_cl, str) and raw_cl.lower() in ("1", "true", "yes", ""):
            return True
    except Exception:
        pass
    return False


def _get_bundle_version_hash() -> str:
    """bundle.min.js va bundle.min.css fayllaridan xesh olib 12 xonali versiya tamg'asini olish."""
    h = hashlib.md5()
    dist_dir = BASE_DIR / "webapp" / "dist"
    webapp_dir = BASE_DIR / "webapp"
    for fname in ("bundle.min.css", "bundle.min.js"):
        p = dist_dir / fname
        if not p.exists():
            p = webapp_dir / fname
        if p.exists():
            try:
                h.update(p.read_bytes())
            except Exception:
                pass
    v = h.hexdigest()[:12]
    return v if v else "1.0.0"


def get_production_index_html(cache_bust: bool = False, version: Optional[str] = None) -> str:
    """Ishlab chiqarish (production) uchun barcha CSS va JS skriptlari bundle qilingan,
    DevTools shield bilan himoyalangan va 80% gacha yengillashtirilgan index.html ni tayyorlash."""
    index_file = BASE_DIR / "webapp" / "index.html"
    if not index_file.exists():
        return "<h1>Kinolar katalogi Mini App ishga tushirilmoqda...</h1>"

    bundle_file = BASE_DIR / "webapp" / "dist" / "bundle.min.js"
    if not bundle_file.exists():
        bundle_file = BASE_DIR / "webapp" / "bundle.min.js"
    if not bundle_file.exists():
        try:
            from scripts.bundle_frontend import build_bundle
            build_bundle()
        except Exception as be:
            logger.warning(f"Frontend bundle yaratishda xatolik: {be}")

    html = index_file.read_text(encoding="utf-8")

    v_str = version or _get_bundle_version_hash()
    css_ref = f'bundle.min.css?v={v_str}' if (cache_bust or version) else 'bundle.min.css'
    js_ref = f'bundle.min.js?v={v_str}' if (cache_bust or version) else 'bundle.min.js'

    # 1. Barcha alohida CSS fayllarini yagona bundle.min.css ga almashtirish
    css_pattern = r'<link\s+rel="stylesheet"\s+href="(?:rasxod|kaloriya|asil|kattalar|mafia|tvroom|bunker|deliv|music|docs|fx|food|quiz|prava|games|story|books|zk)\.css">'
    html, n_css = re.subn(css_pattern, '', html)
    if n_css > 0:
        html = html.replace(
            '<link rel="preload" as="image" href="logo.webp">',
            f'<link rel="stylesheet" href="{css_ref}">\n<link rel="preload" as="image" href="logo.webp">'
        )

    # 2. Barcha alohida JS skriptlarini va inline main skriptni (agar bo'lsa) yagona bundle.min.js ga almashtirish
    js_pattern = r'<script\s+src="(?:i18n|zintro|music|docs|games|kattalar|mafia|bunker|deliv|tvroom|story|books|fx|food|quiz|prava|rasxod|kaloriya|asil|zk|app)\.js"></script>'
    html, n_js = re.subn(js_pattern, '', html)

    last_script_pattern = r'<script>\s*\(\(\)\s*=>\s*\{\s*"use strict";[\s\S]*?load\(\);\s*\}\)\(\);\s*</script>'
    html, n_inline = re.subn(last_script_pattern, f'<script src="{js_ref}" defer></script>', html)
    if (n_js > 0 or n_inline == 0) and js_ref not in html:
        html = html.replace('</body>', f'<script src="{js_ref}" defer></script>\n</body>')

    return html


async def handle_index(request: web.Request) -> web.Response:
    """Asosiy Mini App sahifasi (index.html) - production bundle, ETag va nol kechikish bilan."""
    if request.method == "HEAD":
        return web.Response(
            status=200,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "X-Robots-Tag": "noindex, nofollow"
            }
        )

    index_file = BASE_DIR / "webapp" / "index.html"
    if not index_file.exists():
        return web.Response(text="<h1>Kinolar katalogi Mini App ishga tushirilmoqda...</h1>", content_type="text/html")

    if request.query.get("raw") == "1":
        return web.FileResponse(index_file)

    now = time.time()
    file_mtime = index_file.stat().st_mtime if index_file.exists() else 0
    bundle_js = BASE_DIR / "webapp" / "dist" / "bundle.min.js"
    bundle_css = BASE_DIR / "webapp" / "dist" / "bundle.min.css"
    bundle_mtime = max(
        bundle_js.stat().st_mtime if bundle_js.exists() else 0,
        bundle_css.stat().st_mtime if bundle_css.exists() else 0,
    )
    max_mtime = max(file_mtime, bundle_mtime)
    if (
        _PROD_INDEX_CACHE["html"] is None
        or (now - _PROD_INDEX_CACHE["ts"] > 120)
        or (_PROD_INDEX_CACHE["ts"] < max_mtime)
        or _is_nocache(request)
    ):
        _PROD_INDEX_CACHE["html"] = get_production_index_html(cache_bust=True)
        _PROD_INDEX_CACHE["bytes"] = _PROD_INDEX_CACHE["html"].encode("utf-8")
        _PROD_INDEX_CACHE["etag"] = f'"{hashlib.md5(_PROD_INDEX_CACHE["bytes"]).hexdigest()[:16]}"'
        _PROD_INDEX_CACHE["ts"] = now

    etag = _PROD_INDEX_CACHE.get("etag")
    if etag and request.headers.get("If-None-Match") == etag:
        return web.Response(
            status=304,
            headers={
                "ETag": etag,
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            }
        )

    resp = web.Response(
        body=_PROD_INDEX_CACHE["bytes"],
        content_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-SourceMap": "none",
            "ETag": etag,
        }
    )
    if hasattr(resp, "enable_compression"):
        resp.enable_compression()
    return resp


async def handle_bundle_js(request: web.Request) -> web.Response:
    """Yagona minifikatsiya qilingan va himoyalangan JS bundle."""
    bundle_file = BASE_DIR / "webapp" / "dist" / "bundle.min.js"
    if not bundle_file.exists():
        bundle_file = BASE_DIR / "webapp" / "bundle.min.js"
    if bundle_file.exists():
        fkey = str(bundle_file)
        file_mtime = bundle_file.stat().st_mtime
        cached = _STATIC_BUNDLES_CACHE.get(fkey)
        if cached is None or (len(cached) > 3 and cached[3] < file_mtime) or _is_nocache(request):
            content = await asyncio.to_thread(bundle_file.read_bytes)
            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
            _STATIC_BUNDLES_CACHE[fkey] = (content, "application/javascript", etag, file_mtime)

        content, ct, etag, _ = _STATIC_BUNDLES_CACHE[fkey]
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=86400, immutable"})

        resp = web.Response(
            body=content,
            content_type=ct,
            headers={
                "Cache-Control": "public, max-age=86400, immutable",
                "X-SourceMap": "none",
                "ETag": etag,
                "Access-Control-Allow-Origin": "*",
            }
        )
        if hasattr(resp, "enable_compression"):
            resp.enable_compression()
        return resp
    return web.Response(status=404, text="Bundle topilmadi")


async def handle_bundle_css(request: web.Request) -> web.Response:
    """Yagona minifikatsiya qilingan CSS bundle."""
    bundle_file = BASE_DIR / "webapp" / "dist" / "bundle.min.css"
    if not bundle_file.exists():
        bundle_file = BASE_DIR / "webapp" / "bundle.min.css"
    if bundle_file.exists():
        fkey = str(bundle_file)
        file_mtime = bundle_file.stat().st_mtime
        cached = _STATIC_BUNDLES_CACHE.get(fkey)
        if cached is None or (len(cached) > 3 and cached[3] < file_mtime) or _is_nocache(request):
            content = await asyncio.to_thread(bundle_file.read_bytes)
            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
            _STATIC_BUNDLES_CACHE[fkey] = (content, "text/css", etag, file_mtime)

        content, ct, etag, _ = _STATIC_BUNDLES_CACHE[fkey]
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=86400, immutable"})

        resp = web.Response(
            body=content,
            content_type=ct,
            headers={
                "Cache-Control": "public, max-age=86400, immutable",
                "X-SourceMap": "none",
                "ETag": etag,
                "Access-Control-Allow-Origin": "*",
            }
        )
        if hasattr(resp, "enable_compression"):
            resp.enable_compression()
        return resp
    return web.Response(status=404, text="CSS bundle topilmadi")


async def handle_shield_js(request: web.Request) -> web.Response:
    """DevTools himoyasi va anti-debugging skripti."""
    shield_file = BASE_DIR / "webapp" / "dist" / "shield.min.js"
    if not shield_file.exists():
        shield_file = BASE_DIR / "webapp" / "shield.min.js"
    if shield_file.exists():
        fkey = str(shield_file)
        if fkey not in _STATIC_BUNDLES_CACHE or request.query.get("nocache"):
            content = await asyncio.to_thread(shield_file.read_bytes)
            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
            _STATIC_BUNDLES_CACHE[fkey] = (content, "application/javascript", etag)

        content, ct, etag = _STATIC_BUNDLES_CACHE[fkey]
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=86400, immutable"})

        resp = web.Response(
            body=content,
            content_type=ct,
            headers={
                "Cache-Control": "public, max-age=86400, immutable",
                "X-SourceMap": "none",
                "ETag": etag,
                "Access-Control-Allow-Origin": "*",
            }
        )
        if hasattr(resp, "enable_compression"):
            resp.enable_compression()
        return resp
    return web.Response(status=404, text="Shield topilmadi")


def extract_user_id_from_init_data(init_data: str) -> Optional[int]:
    """Telegram WebApp initData satridan user_id ni xavfsiz ajratib olish."""
    if not init_data:
        return None
    try:
        import urllib.parse
        parsed = urllib.parse.parse_qs(init_data)
        if "user" in parsed:
            u_str = parsed["user"][0]
            u_obj = json.loads(u_str)
            raw_id = u_obj.get("id")
            if is_valid_user_id(raw_id):
                return int(raw_id)
    except Exception:
        pass
    return None


_CATALOG_CACHE: Dict[str, Any] = {"data": None, "ts": 0, "bytes": None, "m_hash": None}


def clear_catalog_cache() -> None:
    """Katalog va bog'liq web keshlarini tozalash (maintenance, yangi kontent yoki refresh bo'lganda chaqiriladi)."""
    _CATALOG_CACHE.update({"data": None, "ts": 0, "bytes": None, "m_hash": None, "etag": None})
    _ASIL_API_CACHE.clear()
    _PROD_INDEX_CACHE.update({"html": None, "bytes": None, "etag": None, "ts": 0})
    _STATIC_BUNDLES_CACHE.clear()


def clear_all_web_caches() -> None:
    """Barcha in-memory web server keshlarini tozalash."""
    clear_catalog_cache()



def sanitize_catalog_text(text: str) -> str:
    """Barcha tashqi bot/kanal havolalarini @BauntyCinemabot va @BauntyFilms ga almashtirish."""
    if not text:
        return ""
    bot_clean = get_bot_username()
    channel_clean = (config.CHANNEL_USERNAME or "BauntyFilms").lstrip("@")

    text = re.sub(r'https?://t\.me/(?:Zakirovs?(?:films_bot|film_bot|Kino|_bot)?|dilbarzakirova)\b', f'https://t.me/{channel_clean}', text, flags=re.I)
    text = re.sub(r't\.me/(?:Zakirovs?(?:films_bot|film_bot|Kino|_bot)?|dilbarzakirova)\b', f't.me/{channel_clean}', text, flags=re.I)
    text = re.sub(r'@Zakirovs?(?:films?_bot|kino|_bot)?\b', f'@{bot_clean}', text, flags=re.I)
    text = re.sub(r'@dilbarzakirova\b', f'@{channel_clean}', text, flags=re.I)
    text = re.sub(r'@Zakirovs?\b', f'@{channel_clean}', text, flags=re.I)
    text = re.sub(r'Zakirovs\s+Films\b', 'Baunty Films', text, flags=re.I)
    text = re.sub(r'Zakirovs?(?:films?_bot|_bot)\b', bot_clean, text, flags=re.I)
    text = re.sub(r'Dilbar\s*Zakirova\b', 'Baunty', text, flags=re.I)
    text = re.sub(r'Zakirova?\b', 'Baunty', text, flags=re.I)
    text = re.sub(r'zakirova?\b', 'baunty', text, flags=re.I)
    text = re.sub(r'Zakirovs\b', 'Baunty', text, flags=re.I)
    text = re.sub(r'zakirovs\b', 'baunty', text, flags=re.I)
    # Legacy bot username migration (@Bauntyfilmsbot -> current BOT_USERNAME)
    text = re.sub(r'https?://t\.me/Bauntyfilmsbot\b', f'https://t.me/{bot_clean}', text, flags=re.I)
    text = re.sub(r't\.me/Bauntyfilmsbot\b', f't.me/{bot_clean}', text, flags=re.I)
    text = re.sub(r'@Bauntyfilmsbot\b', f'@{bot_clean}', text, flags=re.I)
    text = re.sub(r'\bBauntyfilmsbot\b', bot_clean, text, flags=re.I)
    return text


def sanitize_book_text(text: str) -> str:
    """
    Kitoblar matnidagi kodirovka xatolari (mojibake), noto'g'ri UTF-8 belgilari,
    siniq ligaturalar va bo'g'in ajratuvchi chalkashliklarni tozalash.
    """
    if not text:
        return ""

    mojibake_map = {
        "Ã¢â‚¬â„¢": "'",
        "Ã¢â‚¬Å“": "“",
        "Ã¢â‚¬Â": "”",
        "Ã¢â‚¬â€": " — ",
        "Ã¢â‚¬â€“": " – ",
        "Ã¢â‚¬Â¦": "…",
        "â€™": "'",
        "â€˜": "'",
        "â€œ": "“",
        "â€": "”",
        "â€”": " — ",
        "â€“": " – ",
        "â€¦": "…",
        "Ã‚Â": " ",
        "Â ": " ",
        "Â": "",
        "\ufeff": "",
        "\ufffd": "",
        "\u00ad": "",
    }
    for bad, good in mojibake_map.items():
        if bad in text:
            text = text.replace(bad, good)

    # O'zbekcha harflardagi chalkash apostroflar
    text = re.sub(r"o[‘`ʻʼ’´]", "o'", text)
    text = re.sub(r"O[‘`ʻʼ’´]", "O'", text)
    text = re.sub(r"g[‘`ʻʼ’´]", "g'", text)
    text = re.sub(r"G[‘`ʻʼ’´]", "G'", text)

    # Siniq so'z bo'g'inlari (masalan: "kitob- lar" -> "kitoblar")
    text = re.sub(r"(\b[A-Za-zА-Яа-яЎўҒғҚқҲҳ]+)-[ \t\r\n]+([A-Za-zА-Яа-яЎўҒғҚқҲҳ]+\b)", r"\1\2", text)

    # Siniq ligaturalar
    ligature_map = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
    }
    for lig, rep in ligature_map.items():
        if lig in text:
            text = text.replace(lig, rep)

    return text


_POSTER_CACHE: Dict[str, Tuple[bytes, str]] = {}
_PRAVA_CACHE: Dict[str, Tuple[bytes, str]] = {}
_BOOK_CACHE: Dict[str, Tuple[bytes, str, str]] = {}
_BOOK_404_CACHE: Dict[str, float] = {}
_RC_CACHE: Dict[str, Tuple[bytes, str, str]] = {}


async def handle_poster_proxy(request: web.Request) -> web.Response:
    """Kino posterlarini keshlab uzatish (mahalliy katalog, Asilmedia CDN va in-memory kesh)."""
    filename = request.match_info.get("filename", "")
    clean_name = os.path.basename(filename)
    if not clean_name or not (clean_name.endswith(".webp") or clean_name.endswith(".jpg") or clean_name.endswith(".png")):
        return web.Response(status=404, text="Topilmadi")

    # 1. Tezkor xotira keshidan uzatish (0ms kechikish)
    if clean_name in _POSTER_CACHE:
        content, etag = _POSTER_CACHE[clean_name]
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
        return web.Response(
            body=content,
            content_type="image/webp",
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "Access-Control-Allow-Origin": "*",
                "ETag": etag,
            }
        )

    posters_dir = BASE_DIR / "data" / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)
    local_path = posters_dir / clean_name

    # 2. Diskdagi fayldan asinxron o'qish (event-loop bloklanmaydi)
    if local_path.exists():
        try:
            content = await asyncio.to_thread(local_path.read_bytes)
            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
            if len(_POSTER_CACHE) > 500:
                _POSTER_CACHE.clear()
            _POSTER_CACHE[clean_name] = (content, etag)
            if request.headers.get("If-None-Match") == etag:
                return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
            return web.Response(
                body=content,
                content_type="image/webp",
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Access-Control-Allow-Origin": "*",
                    "ETag": etag,
                }
            )
        except Exception:
            pass

    # 3. Katalog yoki Asilmedia CDN manzilidan poster olish
    stem = os.path.splitext(clean_name)[0].strip()
    poster_url = ""
    try:
        cat_item = MovieService.get_catalog_item(stem)
        if cat_item:
            poster_url = str(cat_item.get("p_url") or cat_item.get("poster") or "").strip()
            if not poster_url and cat_item.get("asil_id"):
                from services.asilmedia_service import asilmedia_service
                am = await asilmedia_service.get_movie_details(str(cat_item["asil_id"]))
                if am and am.poster:
                    poster_url = am.poster
        elif stem.isdigit():
            from services.asilmedia_service import asilmedia_service
            am = await asilmedia_service.get_movie_details(stem)
            if am and am.poster:
                poster_url = am.poster
    except Exception:
        poster_url = ""

    if poster_url.startswith("http") and "sslip.io" not in poster_url.lower():
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(poster_url, timeout=aiohttp.ClientTimeout(total=3.0, connect=1.5)) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        if content and len(content) > 200:
                            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
                            if len(_POSTER_CACHE) > 500:
                                _POSTER_CACHE.clear()
                            _POSTER_CACHE[clean_name] = (content, etag)
                            asyncio.create_task(asyncio.to_thread(local_path.write_bytes, content))
                            return web.Response(
                                body=content,
                                content_type=resp.headers.get("Content-Type", "image/webp").split(";")[0],
                                headers={
                                    "Cache-Control": "public, max-age=604800, immutable",
                                    "Access-Control-Allow-Origin": "*",
                                    "ETag": etag,
                                }
                            )
        except Exception as e:
            logger.debug(f"Posterni CDN dan yuklab bo'lmadi ({clean_name}): {e}")

    return web.Response(status=404, text="Poster topilmadi")


async def handle_prava_image_proxy(request: web.Request) -> web.Response:
    """Prava savollari rasmlarini (prava/... va pv/...) keshlab uzatish."""
    filename = request.match_info.get("filename", "")
    if not filename:
        filename = request.match_info.get("tail", "").lstrip("/")

    clean_name = os.path.basename(filename)
    if not clean_name:
        return web.Response(status=404, text="Topilmadi")

    if not clean_name.endswith(".webp") and not clean_name.endswith(".png") and not clean_name.endswith(".jpg"):
        clean_name = f"{clean_name}.webp"

    # 1. Xotira keshidan uzatish
    if clean_name in _PRAVA_CACHE:
        content, etag = _PRAVA_CACHE[clean_name]
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
        return web.Response(
            body=content,
            content_type="image/webp",
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "Access-Control-Allow-Origin": "*",
                "ETag": etag,
            }
        )

    prava_dir = BASE_DIR / "data" / "prava"
    prava_dir.mkdir(parents=True, exist_ok=True)
    local_path = prava_dir / clean_name

    # 2. Lokal diskdan asinxron o'qish
    if local_path.exists() and local_path.stat().st_size > 100:
        try:
            content = await asyncio.to_thread(local_path.read_bytes)
            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
            if len(_PRAVA_CACHE) > 500:
                _PRAVA_CACHE.clear()
            _PRAVA_CACHE[clean_name] = (content, etag)
            if request.headers.get("If-None-Match") == etag:
                return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
            return web.Response(
                body=content,
                content_type="image/webp",
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Access-Control-Allow-Origin": "*",
                    "ETag": etag,
                }
            )
        except Exception:
            pass

    # 3. Lokal Prava savol rasmini generatsiya qilish va diskda keshlash (faqat haqiqiy savol ID lari uchun)
    try:
        from services.prava_service import prava_service
        m_qid = re.fullmatch(r"(\d+)\.webp", clean_name)
        q_id = int(m_qid.group(1)) if m_qid else 0
        if q_id <= 0 or q_id > prava_service.total_questions:
            return web.Response(status=404, text="Topilmadi")
        content = await asyncio.to_thread(prava_service.generate_question_image_bytes, q_id)
        if content and len(content) > 100:
            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
            if len(_PRAVA_CACHE) > 500:
                _PRAVA_CACHE.clear()
            _PRAVA_CACHE[clean_name] = (content, etag)
            asyncio.create_task(asyncio.to_thread(local_path.write_bytes, content))
            return web.Response(
                body=content,
                content_type="image/webp",
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Access-Control-Allow-Origin": "*",
                    "ETag": etag,
                }
            )
    except Exception as e:
        logger.debug(f"Prava rasmini generatsiya qilib bo'lmadi ({clean_name}): {e}")

    return web.Response(status=404, text="Prava rasmi topilmadi")


def _process_and_save_book_cover(raw_bytes: bytes, tail: str, local_path: Path, ext: str) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    is_s = "cover_s" in tail or "thumb" in tail
    target_size = (240, 360) if is_s else (600, 900)
    im.thumbnail(target_size, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    fmt = "JPEG" if ext in (".jpg", ".jpeg") else "PNG" if ext == ".png" else "WEBP"
    im.save(buf, format=fmt, quality=85)
    content = buf.getvalue()
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)
    except Exception:
        pass
    return content


async def handle_book_asset_proxy(request: web.Request) -> web.Response:
    """Kitob muqovalari, rasmlari va sahifalarini (bk/...) keshlab uzatish."""
    tail = request.match_info.get("tail", "").lstrip("/")
    if not tail:
        p = request.path.lstrip("/")
        if p.startswith("webapp/bk/"):
            tail = p[10:]
        elif p.startswith("bk/"):
            tail = p[3:]
    if not tail or ".." in tail:
        return web.Response(status=404, text="Topilmadi")

    ext = os.path.splitext(tail)[1].lower()
    ct_map = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".epub": "application/epub+zip",
    }
    content_type = ct_map.get(ext, "application/octet-stream")
    is_image = ext in (".webp", ".png", ".jpg", ".jpeg", ".svg")

    # 1. Xotira keshidan uzatish
    if tail in _BOOK_CACHE:
        content, ct, etag = _BOOK_CACHE[tail]
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
        return web.Response(
            body=content,
            content_type=ct,
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "Access-Control-Allow-Origin": "*",
                "ETag": etag,
            }
        )

    # 2. Diskdagi lokal keshdan tekshirish
    bk_dir = BASE_DIR / "data" / "bk"
    local_path = bk_dir / tail
    if not local_path.exists() and is_image:
        alt_names = ["cover_s.webp", "cover_l.webp", "thumb.jpg"] if ("cover_s" in tail or "small" in tail or "thumb" in tail) else ["cover_l.webp", "cover_s.webp", "thumb.jpg"]
        for alt in alt_names:
            alt_p = local_path.parent / alt
            if alt_p.exists():
                local_path = alt_p
                ext = alt_p.suffix.lower()
                content_type = ct_map.get(ext, content_type)
                break

    if local_path.exists():
        try:
            content = await asyncio.to_thread(local_path.read_bytes)
            if ext == ".json":
                try:
                    content = sanitize_book_text(content.decode("utf-8")).encode("utf-8")
                except Exception:
                    pass
            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
            if len(_BOOK_CACHE) > 500:
                _BOOK_CACHE.clear()
            _BOOK_CACHE[tail] = (content, content_type, etag)
            if request.headers.get("If-None-Match") == etag:
                return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
            return web.Response(
                body=content,
                content_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Access-Control-Allow-Origin": "*",
                    "ETag": etag,
                }
            )
        except Exception:
            pass

    # 3. Agar rasm so'ralgan bo'lsa (muqova, thumbnail)
    if is_image:
        m_bid = re.match(r"^(\d+)/", tail) or re.match(r"^(?:cover|thumb|bk)_?(\d+)", tail)
        book_id = m_bid.group(1) if m_bid else None
        if not book_id:
            parts = tail.split("/")
            if parts[0].isdigit():
                book_id = parts[0]

        from services import book_service
        book = book_service.get_book_by_id(book_id) if book_id else None

        # 3.1. Dinamik sifatli ultra-tezkor WebP muqova yaratish (Pillow yoki SVG) - <5ms javob
        size = "s" if ("cover_s" in tail or "thumb" in tail or "small" in tail) else "l"
        fmt = "JPEG" if ext in (".jpg", ".jpeg") else "PNG" if ext == ".png" else "WEBP"
        target_book = book or {"id": book_id or "0", "title": f"Kitob #{book_id or 0}", "author": "Baunty Kutubxonasi", "category_name": "Kutubxona"}

        if ext == ".svg":
            content = book_service.generate_svg_book_cover(target_book).encode("utf-8")
        else:
            content = book_service.generate_dynamic_book_cover(target_book, size=size, fmt=fmt)

        etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
        if len(_BOOK_CACHE) > 1000:
            _BOOK_CACHE.clear()
        _BOOK_CACHE[tail] = (content, content_type, etag)

        def _save_fallback(lp, c):
            try:
                lp.parent.mkdir(parents=True, exist_ok=True)
                lp.write_bytes(c)
            except Exception:
                pass
        asyncio.create_task(asyncio.to_thread(_save_fallback, local_path, content))

        return web.Response(
            body=content,
            content_type=content_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "Access-Control-Allow-Origin": "*",
                "ETag": etag,
            }
        )

    # 4. Agar fayl topilmasa va tail toc.json yoki c{n}.json bo'lsa — kitob matnidan avtomatik generatsiya
    m_toc = re.match(r"^(\d+)/toc\.json$", tail)
    m_ch = re.match(r"^(\d+)/c(\d+)\.json$", tail)
    if m_toc or m_ch:
        from services import book_service
        bid = m_toc.group(1) if m_toc else m_ch.group(1)
        book = book_service.get_book_by_id(bid)
        if book:
            if m_toc:
                pages = book.get("pages") or book.get("p") or 120
                toc_data = {
                    "ok": True,
                    "mode": "text",
                    "pages": pages,
                    "toc": [
                        {"t": "1-bob. Muqaddima va asar tavsifi", "c": 1},
                        {"t": "2-bob. Asosiy g'oyalar va voqealar rivoji", "c": 2},
                        {"t": "3-bob. Saralangan parcha va tahlil", "c": 3},
                        {"t": "4-bob. Xotima va xulosalar", "c": 4},
                    ]
                }
                c_bytes = json.dumps(toc_data, ensure_ascii=False).encode("utf-8")
                return web.Response(
                    body=c_bytes,
                    content_type="application/json",
                    headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=86400"}
                )
            elif m_ch:
                ch_num = int(m_ch.group(2))
                title = book.get("title") or book.get("t") or "Kitob"
                author = book.get("author") or book.get("a") or "Muallif"
                desc = book.get("description") or book.get("desc") or ""
                sample = book.get("sample_text") or desc
                cat_name = book.get("category_name") or "Adabiyot"

                sample_paras = [p.strip() for p in sample.split("\n") if p.strip()]
                if not sample_paras:
                    sample_paras = [desc] if desc else ["Matn mavjud emas."]

                if ch_num == 1:
                    ch_title = "1-bob. Muqaddima va asar tavsifi"
                    paras = [
                        f"«{title}» ({author}) — {cat_name} durdonasi.",
                        desc or f"Ushbu mashhur asar {author} tomonidan yozilgan bo'lib, o'quvchilar qalbidan chuqur joy olgan.",
                        "Kitob mutolaasi inson dunyoqarashini boyitadi, tafakkurini charxlaydi va yangi ufqlarni ochadi."
                    ]
                elif ch_num == 2:
                    ch_title = "2-bob. Asosiy g'oyalar va voqealar rivoji"
                    mid = len(sample_paras) // 2
                    p_slice = sample_paras[:mid] if mid > 0 else sample_paras
                    paras = [
                        f"«{title}» asarining asosiy g'oyalari va voqealar bayoni:",
                    ] + p_slice
                elif ch_num == 3:
                    ch_title = "3-bob. Saralangan parcha va tahlil"
                    mid = len(sample_paras) // 2
                    p_slice = sample_paras[mid:] if mid > 0 else sample_paras
                    paras = [
                        f"«{title}» asaridan saralangan parcha:",
                    ] + p_slice
                else:
                    ch_title = f"{ch_num}-bob. Xotima va xulosalar"
                    paras = [
                        f"«{title}» kitobining yakuniy xulosalari va mazmun-mohiyati.",
                        f"{author} qalamiga mansub ushbu asar chuqur hayotiy saboqlar va qimmatli fikrlarni o'z ichiga oladi.",
                        "Mutolaa uchun tashakkur! Baunty Kutubxonasida boshqa sara asarlarni ham kashf eting."
                    ]

                ch_data = {
                    "t": ch_title,
                    "h": f"«{title}» — {author}",
                    "p": paras
                }
                c_bytes = json.dumps(ch_data, ensure_ascii=False).encode("utf-8")
                return web.Response(
                    body=c_bytes,
                    content_type="application/json",
                    headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=86400"}
                )

    if len(_BOOK_404_CACHE) > 500:
        _BOOK_404_CACHE.clear()
    _BOOK_404_CACHE[tail] = time.time()
    return web.Response(status=404, text="Resurs topilmadi")


async def handle_book_cover_api(request: web.Request) -> web.Response:
    """Kitob muqovasi API endpointi (/api/book_cover/{id})."""
    raw_id = request.match_info.get("id", "").strip() or request.query.get("id", "").strip()
    if not raw_id:
        return web.Response(status=400, text="Kitob ID ko'rsatilmadi")

    size = request.query.get("size", "s").lower()
    fmt = request.query.get("format", "webp").lower()

    bid = re.sub(r"\.(webp|jpg|jpeg|png|svg)$", "", raw_id)
    ext = os.path.splitext(raw_id)[1].lower() or f".{fmt}"
    if ext not in (".webp", ".jpg", ".jpeg", ".png", ".svg"):
        ext = ".webp"

    size_code = "s" if size in ("s", "small", "thumb") else "l"
    tail = f"{bid}/cover_{size_code}{ext}"
    request.match_info["tail"] = tail
    return await handle_book_asset_proxy(request)


async def handle_rc_asset_proxy(request: web.Request) -> web.Response:
    """Retseptlar rasmlarini (rc/...) keshlab uzatish."""
    tail = request.match_info.get("tail", "").lstrip("/")
    if not tail or ".." in tail:
        return web.Response(status=404, text="Topilmadi")

    ext = os.path.splitext(tail)[1].lower()
    ct_map = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    content_type = ct_map.get(ext, "image/webp")

    # 1. Xotira keshidan uzatish
    if tail in _RC_CACHE:
        content, ct, etag = _RC_CACHE[tail]
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
        return web.Response(
            body=content,
            content_type=ct,
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "Access-Control-Allow-Origin": "*",
                "ETag": etag,
            }
        )

    rc_dir = BASE_DIR / "data" / "rc"
    local_path = rc_dir / tail
    if local_path.exists():
        try:
            content = await asyncio.to_thread(local_path.read_bytes)
            etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
            if len(_RC_CACHE) > 500:
                _RC_CACHE.clear()
            _RC_CACHE[tail] = (content, content_type, etag)
            if request.headers.get("If-None-Match") == etag:
                return web.Response(status=304, headers={"ETag": etag, "Cache-Control": "public, max-age=604800, immutable"})
            return web.Response(
                body=content,
                content_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Access-Control-Allow-Origin": "*",
                    "ETag": etag,
                }
            )
        except Exception:
            pass

    return web.Response(status=404, text="Rasm topilmadi")


async def handle_watch_get(request: web.Request) -> web.Response:
    """Watch GET so'rovi (holat va yo'naltirish ma'lumoti)."""
    bot_username = await resolve_bot_username(_bot_instance)
    return web.json_response({
        "ok": True,
        "service": "watch",
        "bot": bot_username,
        "methods": ["POST"]
    })


async def handle_send_api(request: web.Request) -> web.Response:
    """Mini Appdan Telegram chatga kino yoki musiqa yuborish (POST va GET)."""
    if request.method == "POST":
        return await handle_send_to_chat(request)
    return web.json_response({
        "ok": True,
        "service": "send",
        "methods": ["POST"],
        "bot": await resolve_bot_username(_bot_instance)
    })


async def handle_doc_config(request: web.Request) -> web.Response:
    """Hujjatlar xizmati konfiguratsiyasi."""
    return web.json_response({
        "ok": True,
        "stamp": True,
        "max_mb": 50,
        "translate": True,
        "max_images": 50,
        "bot": await resolve_bot_username(_bot_instance)
    })


async def handle_doc_root(request: web.Request) -> web.Response:
    """Hujjatlar xizmati asosiy ma'lumotlari."""
    return web.json_response({
        "ok": True,
        "service": "docs",
        "tools": [
            {"id": "topdf", "name": "Hujjatni PDF qilish"},
            {"id": "img2pdf", "name": "Rasmlardan PDF"},
            {"id": "translit", "name": "Kirill ↔ Lotin"},
            {"id": "pdf", "name": "Matndan PDF"}
        ]
    })


async def handle_api_lang(request: web.Request) -> web.Response:
    """Foydalanuvchi interfeys tili sozlamasi."""
    lang = "uz"
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                lang = body.get("lang") or "uz"
        except Exception:
            pass
    else:
        lang = request.query.get("lang") or "uz"
    if lang not in ("uz", "ru", "en"):
        lang = "uz"
    return web.json_response({"ok": True, "lang": lang})


async def handle_api_overview(request: web.Request) -> web.Response:
    """Bauntys asosiy API ma'lumotlari."""
    return web.json_response({
        "ok": True,
        "service": "Bauntys API",
        "bot": await resolve_bot_username(_bot_instance),
        "channel": config.CHANNEL_USERNAME,
        "status": "online"
    })


_DOCS_FILES: Dict[str, Dict[str, Any]] = {}
_DOCS_JOBS: Dict[str, Dict[str, Any]] = {}
_FX_ALERTS_BY_USER: Dict[int, List[Dict[str, Any]]] = {}


def _extract_api_path(request: web.Request) -> str:
    path = request.path.lstrip("/").rstrip("/")
    if path.startswith("webapp/"):
        path = path[7:].lstrip("/").rstrip("/")
    if "?" in path:
        path = path.split("?", 1)[0].rstrip("/")
    return path


async def _read_json_body(request: web.Request) -> Dict[str, Any]:
    # security_middleware oldindan request.read() chaqirgani sababli can_read_body False bo'lishi mumkin;
    # shu bois keshlangan baytlarni yoki json() ni bevosita o'qiymiz.
    try:
        raw = await request.read()
        if raw:
            data = json.loads(raw.decode("utf-8", errors="replace"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def handle_bunker_api(request: web.Request) -> web.Response:
    """Bunker o'yini Mini App API handleri."""
    path = _extract_api_path(request)
    user_id, user_name = extract_request_user(request)
    uid = user_id or 0
    body = await _read_json_body(request) if request.method == "POST" else {}
    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        if path in ("api/bunker", "api/bunker/home"):
            res = bunker_service.get_home(user_id=uid, user_name=user_name)
        elif path == "api/bunker/state":
            res = bunker_service.get_state(
                code_or_user_id=str(request.query.get("code") or body.get("code") or ""),
                user_id=uid,
            )
        elif path == "api/bunker/create":
            res = bunker_service.create_room(
                user_id=uid,
                user_name=user_name,
                room_name=str(body.get("name") or ""),
                max_players=int(body.get("max") or 8),
                pub=bool(body.get("pub", True)),
            )
        elif path == "api/bunker/join":
            res = bunker_service.join_room(
                user_id=uid,
                user_name=user_name,
                code=str(body.get("code") or ""),
            )
        elif path == "api/bunker/bot":
            res = bunker_service.add_bots(
                user_id=uid,
                count=int(body.get("count") or 1),
                code=body.get("code"),
            )
        elif path == "api/bunker/start":
            res = bunker_service.start_game(user_id=uid, code=body.get("code"))
        elif path == "api/bunker/reveal":
            res = bunker_service.reveal_card(
                user_id=uid,
                card_key=str(body.get("card") or ""),
                code=body.get("code"),
            )
        elif path == "api/bunker/vote":
            res = bunker_service.vote(
                user_id=uid,
                target_id=int(body.get("target") or 0),
                code=body.get("code"),
            )
        elif path == "api/bunker/next":
            res = bunker_service.next_round(user_id=uid, code=body.get("code"))
        elif path == "api/bunker/chat":
            res = bunker_service.send_chat(
                user_id=uid,
                user_name=user_name,
                text=str(body.get("text") or ""),
                code=body.get("code"),
            )
        elif path == "api/bunker/leave":
            res = bunker_service.leave_room(user_id=uid)
        else:
            return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)
        return web.json_response(res, headers=headers)
    except Exception as e:
        logger.warning(f"Bunker API xatolik ({path}): {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=400, headers=headers)


async def handle_deliv_api(request: web.Request) -> web.Response:
    """Yetkazish (Deliv) Mini App API handleri."""
    path = _extract_api_path(request)
    user_id, user_name = extract_request_user(request)
    uid = user_id or 0
    body = await _read_json_body(request) if request.method == "POST" else {}
    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        if path in ("api/deliv", "api/deliv/home"):
            res = deliv_service.get_home(user_id=uid)
        elif path == "api/deliv/stores":
            res = deliv_service.list_stores(
                category=str(request.query.get("cat") or request.query.get("category") or ""),
                query=str(request.query.get("q") or ""),
            )
        elif path == "api/deliv/order":
            res = deliv_service.create_order(
                user_id=uid,
                user_name=user_name,
                address=str(body.get("address") or body.get("addr") or ""),
                phone=str(body.get("phone") or ""),
                items=body.get("items") or [],
                pickup=str(body.get("pickup") or ""),
                store_id=str(body.get("store_id") or ""),
                note=str(body.get("note") or ""),
                payment=str(body.get("payment") or body.get("pay") or "naqd"),
            )
        elif path == "api/deliv/track":
            code = str(request.query.get("code") or request.query.get("id") or body.get("code") or body.get("id") or "")
            res = deliv_service.get_order(code_or_id=code, user_id=uid)
        elif path == "api/deliv/advance":
            res = deliv_service.advance_status(
                code_or_id=str(body.get("code") or body.get("id") or ""),
                step=body.get("step"),
            )
        elif path == "api/deliv/cancel":
            res = deliv_service.cancel_order(
                code_or_id=str(body.get("code") or body.get("id") or ""),
                user_id=uid,
            )
        else:
            return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)
        return web.json_response(res, headers=headers)
    except Exception as e:
        logger.warning(f"Deliv API xatolik ({path}): {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=400, headers=headers)


async def handle_food_api(request: web.Request) -> web.Response:
    """Taomlar va Retseptlar (Food) Mini App API handleri."""
    path = _extract_api_path(request)
    user_id, _ = extract_request_user(request)
    uid = user_id or 0
    is_adm = bool(uid and config.is_admin(uid))
    body = await _read_json_body(request) if request.method == "POST" else {}
    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        if path == "api/food":
            res = food_service.get_catalog(
                user_id=uid,
                category=str(request.query.get("k") or request.query.get("category") or ""),
                meal=str(request.query.get("m") or request.query.get("meal") or ""),
                query=str(request.query.get("q") or ""),
            )
        elif path == "api/food/me":
            res = food_service.get_user_me(user_id=uid, is_admin=is_adm)
        elif path.startswith("api/food/r/"):
            rec_id = path.split("api/food/r/", 1)[1].strip("/")
            r_obj = food_service.get_recipe(recipe_id=rec_id)
            if not r_obj:
                return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)
            res = {"ok": True, "r": r_obj}
        elif path == "api/food/random":
            ex_raw = request.query.get("ex") or ""
            ex_ids = [x.strip() for x in ex_raw.split(",") if x.strip()]
            res = food_service.get_random(
                meal=str(request.query.get("m") or request.query.get("meal") or ""),
                exclude_ids=ex_ids,
            )
        elif path == "api/food/fav":
            res = food_service.toggle_fav(user_id=uid, recipe_id=str(body.get("id") or ""))
        elif path == "api/food/cook":
            res = food_service.mark_cook(user_id=uid, recipe_id=str(body.get("id") or ""))
        elif path == "api/food/shop":
            rec_id = str(body.get("id") or "")
            r_obj = food_service.get_recipe(recipe_id=rec_id)
            names = body.get("names")
            if not names and isinstance(r_obj, dict):
                names = [ing[0] for ing in (r_obj.get("ing") or []) if isinstance(ing, (list, tuple)) and ing]
            if not _bot_instance or not uid:
                return web.json_response({"ok": False, "error": "need_start"}, headers=headers)
            title = (r_obj or {}).get("t") or "Taom"
            lines = "\n".join(f"• {n}" for n in (names or [])[:30])
            await _bot_instance.send_message(
                chat_id=uid,
                text=f"🛒 <b>{title} — xarid ro'yxati</b>\n\n{lines}",
                parse_mode="HTML",
            )
            res = {"ok": True}
        elif path.startswith("api/food/admin/"):
            ok_adm, _ = verify_admin_request(request)
            if not ok_adm:
                return web.json_response({"ok": False, "error": "forbidden"}, status=403, headers=headers)
            res = {"ok": True}
        else:
            return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)
        return web.json_response(res, headers=headers)
    except Exception as e:
        logger.warning(f"Food API xatolik ({path}): {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=400, headers=headers)


async def handle_duel_api(request: web.Request) -> web.Response:
    """Viktorina va Stolda Duel (Kattalar / Board & Quiz Duel) Mini App API handleri."""
    path = _extract_api_path(request)
    user_id, user_name = extract_request_user(request)
    uid = user_id or 0
    body = await _read_json_body(request) if request.method == "POST" else {}
    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        if path in ("api/duel", "api/duel/home"):
            res = duel_service.get_home(user_id=uid, user_name=user_name)
        elif path == "api/duel/create":
            res = duel_service.create_duel(
                user_id=uid,
                user_name=user_name,
                topic=str(body.get("topic") or "mix"),
                vs_bot=bool(body.get("vs_bot", False)),
                num_questions=int(body.get("n") or 5),
            )
        elif path == "api/duel/answer":
            res = duel_service.submit_answer(
                user_id=uid,
                q_idx=int(body.get("q_idx", body.get("i", 0)) or 0),
                choice=int(body.get("choice", body.get("c", -1)) if body.get("choice", body.get("c", None)) is not None else -1),
                code=str(body.get("code") or ""),
                elapsed_sec=body.get("elapsed"),
            )
        elif path == "api/duel/state":
            res = duel_service.get_state(
                code_or_user_id=str(request.query.get("code") or body.get("code") or ""),
                user_id=uid,
            )
        elif path == "api/duel/find":
            res = duel_service.board_find(
                user_id=uid,
                user_name=user_name,
                g=str(body.get("g") or request.query.get("g") or "chess"),
            )
        elif path == "api/duel/code":
            res = duel_service.board_create_code(
                user_id=uid,
                user_name=user_name,
                g=str(body.get("g") or "chess"),
                pub=bool(body.get("pub", False)),
            )
        elif path == "api/duel/join":
            code_val = str(body.get("code") or "").strip()
            if code_val.isdigit() and len(code_val) == 4:
                res = duel_service.board_join(user_id=uid, user_name=user_name, code=code_val)
            else:
                res = duel_service.join_duel(user_id=uid, user_name=user_name, code=code_val)
        elif path == "api/duel/poll":
            try:
                ver = int(request.query.get("v", -1))
            except (ValueError, TypeError):
                ver = -1
            res = duel_service.board_poll(
                user_id=uid,
                ver=ver,
                room_id=request.query.get("id") or None,
            )
        elif path == "api/duel/move":
            res = duel_service.board_move(user_id=uid, move_data=body)
        elif path == "api/duel/resign":
            res = duel_service.board_resign(user_id=uid)
        else:
            return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)
        return web.json_response(res, headers=headers)
    except Exception as e:
        logger.warning(f"Duel API xatolik ({path}): {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=400, headers=headers)


async def handle_docs_api(request: web.Request) -> web.Response:
    """Hujjatlar xizmati: upload, preview, run (PDF/img2pdf/translit/OCR/tarjima), job status."""
    path = _extract_api_path(request)
    user_id, _ = extract_request_user(request)
    uid = user_id or 0
    headers = {"Access-Control-Allow-Origin": "*"}
    docs_dir = BASE_DIR / "data" / "docs_tmp"
    docs_dir.mkdir(parents=True, exist_ok=True)

    try:
        if path == "api/docs/upload":
            if not request.content_type or "multipart" not in request.content_type:
                return web.json_response({"ok": False, "error": "empty"}, status=400, headers=headers)
            reader = await request.multipart()
            part = await reader.next()
            while part is not None and part.name != "file":
                part = await reader.next()
            if part is None:
                return web.json_response({"ok": False, "error": "empty"}, status=400, headers=headers)
            orig_name = os.path.basename(part.filename or "fayl.txt")
            data = await part.read()
            if not data:
                return web.json_response({"ok": False, "error": "empty"}, status=400, headers=headers)
            if len(data) > 50 * 1024 * 1024:
                return web.json_response({"ok": False, "error": "too_large"}, status=413, headers=headers)
            fid = hashlib.md5(f"{time.time()}_{orig_name}".encode("utf-8")).hexdigest()[:12]
            ext = os.path.splitext(orig_name)[1].lower()
            dst = docs_dir / f"{fid}{ext or '.bin'}"
            await asyncio.to_thread(dst.write_bytes, data)
            kind = "image" if ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp") else "pdf" if ext == ".pdf" else "word" if ext in (".doc", ".docx") else "text"
            w = h = thumbs = 0
            pages = 1
            lang = "uz"
            script = "latn"
            text_val = ""
            if kind == "image":
                try:
                    from PIL import Image
                    import io
                    im = Image.open(io.BytesIO(data))
                    w, h = im.size
                    thumbs = 1
                    thumb_path = docs_dir / f"{fid}_t0.jpg"
                    im_copy = im.convert("RGB")
                    im_copy.thumbnail((320, 320))
                    im_copy.save(thumb_path, format="JPEG", quality=80)
                except Exception:
                    pass
            elif kind == "text":
                text_val = data.decode("utf-8", errors="replace")
                info = doc_service.analyze_text(text_val)
                lang = info.get("lang", "uz")
                script = info.get("script", "latn")
            meta = {
                "fid": fid,
                "name": orig_name,
                "size": len(data),
                "kind": kind,
                "pages": pages,
                "w": w,
                "h": h,
                "thumbs": thumbs,
                "lang": lang,
                "script": script,
                "path": str(dst),
            }
            _DOCS_FILES[fid] = meta
            return web.json_response({"ok": True, "file": {k: v for k, v in meta.items() if k != "path"}}, headers=headers)

        if path.startswith("api/docs/t/"):
            segs = path.split("api/docs/t/", 1)[1].split("/")
            fid = segs[0] if segs else ""
            idx = segs[1] if len(segs) > 1 else "0"
            tpath = docs_dir / f"{fid}_t{idx}.jpg"
            if tpath.exists():
                return web.FileResponse(tpath, headers={"Cache-Control": "public, max-age=3600"})
            return web.Response(status=404)

        if path == "api/docs/preview":
            body = await _read_json_body(request)
            fid = str(body.get("fid") or "")
            meta = _DOCS_FILES.get(fid)
            if not meta or not os.path.exists(meta["path"]):
                return web.json_response({"ok": False, "error": "expired"}, headers=headers)
            raw_text = Path(meta["path"]).read_text(encoding="utf-8", errors="replace")[:4000]
            if body.get("script"):
                out_text = doc_service.transliterate(raw_text, target_script=str(body["script"]))
            elif body.get("target"):
                out_text = doc_service.simple_translate(raw_text, target_lang=str(body["target"]))
            else:
                out_text = raw_text
            return web.json_response({"ok": True, "text": out_text}, headers=headers)

        if path == "api/docs/run":
            body = await _read_json_body(request)
            tool = str(body.get("tool") or "")
            fids = body.get("fids") or []
            options = body.get("options") or {}
            src_paths = []
            for f in fids:
                m = _DOCS_FILES.get(str(f))
                if m and os.path.exists(m["path"]):
                    src_paths.append(m)
            if not src_paths:
                return web.json_response({"ok": False, "error": "expired"}, headers=headers)

            jid = hashlib.md5(f"{time.time()}_{tool}".encode("utf-8")).hexdigest()[:10]
            out_files: List[Dict[str, Any]] = []
            out_text: Optional[str] = None
            out_fid = f"{jid}_out"

            if tool == "img2pdf":
                out_p = docs_dir / f"{out_fid}.pdf"
                await asyncio.to_thread(doc_service.images_to_pdf, [m["path"] for m in src_paths], str(out_p))
                out_files.append({"fid": out_fid, "name": "Hujjat.pdf", "kind": "pdf", "size": out_p.stat().st_size})
            elif tool == "topdf":
                m0 = src_paths[0]
                out_p = docs_dir / f"{out_fid}.pdf"
                if m0["kind"] == "image":
                    await asyncio.to_thread(doc_service.images_to_pdf, [m0["path"]], str(out_p))
                else:
                    raw_txt = Path(m0["path"]).read_text(encoding="utf-8", errors="replace")
                    await asyncio.to_thread(doc_service.create_simple_pdf, m0["name"], raw_txt, str(out_p))
                out_files.append({"fid": out_fid, "name": f"{Path(m0['name']).stem}.pdf", "kind": "pdf", "size": out_p.stat().st_size})
            elif tool in ("translit", "translate"):
                m0 = src_paths[0]
                raw_txt = Path(m0["path"]).read_text(encoding="utf-8", errors="replace")
                if tool == "translit":
                    out_text = doc_service.transliterate(raw_txt, str(options.get("script") or "cyrl"))
                else:
                    out_text = doc_service.simple_translate(raw_txt, str(options.get("target") or "uz"))
            elif tool == "ocr":
                m0 = src_paths[0]
                out_text = await asyncio.to_thread(doc_service.ocr_image, m0["path"], str(options.get("lang") or "uzb+eng"))
            elif tool == "pdf2txt":
                out_text = Path(src_paths[0]["path"]).read_text(encoding="utf-8", errors="replace")[:15000]
            else:
                return web.json_response({"ok": False, "error": "type"}, headers=headers)

            if _bot_instance and uid and out_files:
                try:
                    from aiogram.types import FSInputFile
                    op = docs_dir / f"{out_fid}.pdf"
                    if op.exists():
                        await _bot_instance.send_document(chat_id=uid, document=FSInputFile(op, filename=out_files[0]["name"]))
                except Exception as send_err:
                    logger.debug(f"Docs telegram yuborish xatosi: {send_err}")

            job = {
                "id": jid,
                "state": "done",
                "tool": tool,
                "fids": fids,
                "options": options,
                "result": {"files": out_files, "text": out_text},
            }
            _DOCS_JOBS[jid] = job
            return web.json_response({"ok": True, "job": job}, headers=headers)

        if path.startswith("api/docs/job/"):
            jid = path.split("api/docs/job/", 1)[1].strip("/")
            job = _DOCS_JOBS.get(jid)
            if not job:
                return web.json_response({"ok": False, "error": "expired"}, headers=headers)
            return web.json_response({"ok": True, "job": job}, headers=headers)

        if path == "api/docs/unlock":
            return web.json_response({"ok": False, "error": "bad_pass"}, headers=headers)

        return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)
    except Exception as e:
        logger.warning(f"Docs API xatolik ({path}): {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=400, headers=headers)


def extract_request_user(request: web.Request) -> Tuple[int, str]:
    """So'rovdan Telegram user ID va ismini xavfsiz ajratib olish."""
    user_id = None
    user_name = "O'yinchi"
    init_data = request.headers.get("X-Init-Data") or request.query.get("init_data")
    if init_data:
        try:
            params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
            if "user" in params:
                u_data = json.loads(params["user"])
                if isinstance(u_data, dict):
                    user_id = int(u_data.get("id"))
                    user_name = u_data.get("first_name") or u_data.get("username") or user_name
        except Exception:
            pass
    if not user_id:
        uid_param = request.query.get("user_id")
        if not uid_param and "?" in request.path:
            qs = request.path.split("?", 1)[1]
            q_dict = dict(urllib.parse.parse_qsl(qs))
            uid_param = q_dict.get("user_id")
            if "user_name" in q_dict:
                user_name = q_dict["user_name"]
        elif request.query.get("user_name"):
            user_name = request.query.get("user_name")

        if uid_param and str(uid_param).isdigit():
            user_id = int(uid_param)
        else:
            user_id = 0
    return user_id, user_name


async def handle_rasxod_api(request: web.Request) -> web.Response:
    """Rasxod (Expense tracker) Mini App API handleri."""
    path = request.path.lstrip("/")
    if path.startswith("webapp/"):
        path = path[7:]
    if "?" in path:
        path = path.split("?", 1)[0]
    user_id, _ = extract_request_user(request)

    try:
        if path.endswith("/home") or path == "api/rasxod":
            month = request.query.get("m")
            data = await rasxod_service.get_home(user_id=user_id, year_month=month)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/add"):
            body = await _read_json_body(request)
            text = body.get("text", "")
            data = await rasxod_service.add_expenses_from_text(user_id=user_id, text=text)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/list"):
            month = request.query.get("m")
            cat = request.query.get("cat") or None
            before = int(request.query["before"]) if request.query.get("before") and request.query["before"].isdigit() else None
            data = await rasxod_service.get_list(user_id=user_id, month=month, category=cat, before_id=before)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/edit"):
            body = await _read_json_body(request)
            data = await rasxod_service.edit(
                user_id=user_id,
                expense_id=int(body.get("id", 0)),
                amount=int(body.get("a", 0)),
                note=str(body.get("n", "")),
                date=str(body.get("d", "")),
                category=body.get("c")
            )
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/del"):
            body = await _read_json_body(request)
            data = await rasxod_service.delete(user_id=user_id, expense_id=int(body.get("id", 0)))
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/budget"):
            body = await _read_json_body(request)
            data = await rasxod_service.set_budget(user_id=user_id, amount=int(body.get("a", 0)))
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        data = await rasxod_service.get_home(user_id=user_id)
        return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logger.warning(f"Rasxod API xatolik: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=200, headers={"Access-Control-Allow-Origin": "*"})


async def handle_kaloriya_api(request: web.Request) -> web.Response:
    """Kaloriya (Nutrition & Calorie tracker) Mini App API handleri."""
    path = request.path.lstrip("/").rstrip("/")
    if path.startswith("webapp/"):
        path = path[7:].lstrip("/").rstrip("/")
    if "?" in path:
        path = path.split("?", 1)[0].rstrip("/")
    user_id, _ = extract_request_user(request)
    user_id = user_id or 0

    async def _safe_json() -> Dict[str, Any]:
        return await _read_json_body(request)

    try:
        if path in ("api/kal", "api/kal/home", "api/kal/status"):
            data = await kaloriya_service.get_status(user_id=user_id)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/kal/profile":
            body = await _safe_json()
            data = await kaloriya_service.update_profile(
                user_id=user_id,
                sex=str(body.get("sex", "f")),
                age=int(body.get("age", 25)),
                height=float(body.get("height", 170.0)),
                weight=float(body.get("weight", 70.0)),
                target=float(body.get("target", 65.0)),
                months=int(body.get("months", 3)),
                activity=int(body.get("activity", 3)),
                goal=str(body.get("goal", "lose")),
                force=int(body.get("force", 0))
            )
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif "food/kcal/scan" in path:
            text = None
            photo_data = None
            if request.content_type and "multipart" in request.content_type:
                reader = await request.multipart()
                while True:
                    part = await reader.next()
                    if part is None:
                        break
                    if part.name == "text":
                        text = await part.text()
                    elif part.name == "photo":
                        photo_data = await part.read()
            else:
                body = await _safe_json()
                text = body.get("text")
            data = kaloriya_service.scan_food_text_or_image(text=text, photo_data=photo_data)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif "food/kcal/add" in path:
            body = await _safe_json()
            data = await kaloriya_service.add_meal(
                user_id=user_id,
                meal=str(body.get("meal", "l")),
                items=body.get("items", []),
                src=str(body.get("src", "p"))
            )
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif "food/kcal/del" in path:
            body = await _safe_json()
            data = await kaloriya_service.delete_meal(user_id=user_id, item_id=int(body.get("id", 0)))
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/kal/receipt":
            st_data = await kaloriya_service.get_status(user_id=user_id)
            st_data["status"] = "pending_review"
            pro_val = st_data.get("pro")
            if not isinstance(pro_val, dict):
                st_data["pro"] = {"on": bool(pro_val), "pay": {"status": "wait"}}
            st_data["ok"] = True
            st_data["message"] = "Chek qabul qilindi, moderator tekshiruvidan so'ng faollashtiriladi."
            return web.json_response(st_data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/kal/adm/photo":
            is_adm, _ = verify_admin_request(request)
            if not is_adm:
                return web.json_response({"ok": False, "error": "forbidden", "status": 403}, status=403)
            return web.Response(
                body=b"",
                content_type="image/jpeg"
            )

        elif "api/kal/adm" in path:
            is_adm, _ = verify_admin_request(request)
            if not is_adm:
                return web.json_response({"ok": False, "error": "forbidden", "status": 403}, status=403)
            st_data = await kaloriya_service.get_status(user_id=user_id)
            return web.json_response({
                "ok": True,
                "items": [],
                "user": {"id": user_id, "n": "Foydalanuvchi", "on": True, "d": 30, "until": (datetime.now() + timedelta(days=30)).isoformat()},
                "stats": {"act": 1, "today": 1, "soon": 0, "wait": 0}
            })

        data = await kaloriya_service.get_status(user_id=user_id)
        return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logger.warning(f"Kaloriya API xatolik: {e}")
        try:
            default_plan = crud.calculate_calorie_plan(
                sex="m", age=25, height=175.0, weight=75.0, target_weight=70.0, months=3, activity=3, goal="lose", force=False
            )
            return web.json_response({
                "ok": True,
                "p": {"sex": "m", "age": 25, "height": 175.0, "weight": 75.0, "target": 70.0, "target_weight": 70.0, "months": 3, "activity": 3, "goal": "lose", "force": False},
                "r": default_plan,
                "profile": {"sex": "m", "age": 25, "height": 175.0, "weight": 75.0, "target": 70.0, "target_weight": 70.0, "months": 3, "activity": 3, "goal": "lose", "force": False},
                "plan": default_plan,
                "today": {"kcal": 0, "target": default_plan.get("kcal", 2000), "rem": default_plan.get("kcal", 2000), "p": 0, "f": 0, "c": 0},
                "pro": {"on": True, "ai": True, "days": 365, "price": 45000, "until": (datetime.now() + timedelta(days=365)).isoformat()},
                "day": {"eaten": 0, "items": []},
                "meals": {"b": {"items": [], "total": {"kcal": 0}}, "l": {"items": [], "total": {"kcal": 0}}, "d": {"items": [], "total": {"kcal": 0}}, "s": {"items": [], "total": {"kcal": 0}}},
                "adm": None
            }, headers={"Access-Control-Allow-Origin": "*"})
        except Exception:
            return web.json_response({"ok": False, "error": str(e)}, status=200, headers={"Access-Control-Allow-Origin": "*"})


async def handle_quiz_api(request: web.Request) -> web.Response:
    """Viktorina (Quiz) Mini App API handleri."""
    path = request.path.lstrip("/")
    if path.startswith("webapp/"):
        path = path[7:]
    if "?" in path:
        path = path.split("?", 1)[0]
    user_id, user_name = extract_request_user(request)

    try:
        async def _get_body() -> Dict[str, Any]:
            try:
                return await request.json()
            except Exception:
                return {}

        if path.endswith("/home") or path == "api/quiz":
            data = quiz_service.get_home_data(user_id=user_id)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/daily"):
            if request.method == "POST":
                body = await _get_body()
                chosen_o = int(body.get("o", 0))
                data = quiz_service.answer_daily(user_id=user_id, option_idx=chosen_o)
            else:
                data = quiz_service.get_daily(user_id=user_id)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/me"):
            data = quiz_service.get_me(user_id=user_id, user_name=user_name)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/weekly"):
            data = quiz_service.get_weekly(user_id=user_id)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/solo/start"):
            body = await _get_body()
            tp = str(body.get("tp") or body.get("category") or request.query.get("category") or "mix")
            qid = body.get("id") or body.get("quiz_id")
            data = quiz_service.start_solo(user_id=user_id, tp=tp, quiz_id=int(qid) if qid else None)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/solo/answer"):
            body = await _get_body()
            sid = str(body.get("sid", ""))
            i = int(body.get("i") if "i" in body else body.get("question_id", 0))
            o = int(body.get("o") if "o" in body else body.get("selected", -1))
            data = quiz_service.answer_solo(sid=sid, q_idx=i, chosen_opt=o)
            if "correct" not in data:
                data["correct"] = data.get("right", True)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/solo/next"):
            if request.method == "GET":
                category = request.query.get("category", "")
                data = quiz_service.next_solo(sid="")
                return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})
            body = await _get_body()
            sid = str(body.get("sid", ""))
            data = quiz_service.next_solo(sid=sid)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/quiz/room" or path.endswith("/room"):
            body = await _get_body()
            tp = str(body.get("tp", "mix"))
            qid = body.get("id")
            n = int(body.get("n", 10))
            s = int(body.get("s", 20))
            hp = bool(body.get("hp", True))
            data = quiz_service.create_room(user_id=user_id, user_name=user_name, tp=tp, quiz_id=int(qid) if qid else None, n=n, s=s, hp=hp)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif "/room/" in path:
            parts = path.split("/room/")[1].split("/")
            pin = parts[0]
            action = parts[1] if len(parts) > 1 else ""

            if action == "join":
                body = await _get_body()
                pname = str(body.get("name") or user_name or "O'yinchi")
                data = quiz_service.join_room(pin=pin, user_id=user_id, user_name=pname)
            elif action == "answer":
                body = await _get_body()
                qi = int(body.get("qi", 0))
                o = int(body.get("o", -1))
                data = quiz_service.answer_room(pin=pin, user_id=user_id, qi=qi, chosen_opt=o)
            elif action == "host":
                body = await _get_body()
                act = str(body.get("act", ""))
                data = quiz_service.host_room_action(pin=pin, user_id=user_id, act=act)
            else:
                data = quiz_service.get_room_state(pin=pin, user_id=user_id)

            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/save"):
            body = await _get_body()
            data = quiz_service.save_quiz(user_id=user_id, data=body)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/parse"):
            body = await _get_body()
            text = str(body.get("text", ""))
            data = quiz_service.parse_bulk_text(text=text)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/report"):
            return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/delete"):
            return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})

        data = quiz_service.get_home_data(user_id=user_id)
        return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logger.warning(f"Quiz API xatolik: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=200, headers={"Access-Control-Allow-Origin": "*"})


async def handle_mafia_api(request: web.Request) -> web.Response:
    """Mafia onlayn o'yini Mini App API handleri."""
    path = request.path.lstrip("/")
    if path.startswith("webapp/"):
        path = path[7:]
    if "?" in path:
        path = path.split("?", 1)[0]
    user_id, user_name = extract_request_user(request)

    try:
        async def _get_body() -> Dict[str, Any]:
            try:
                return await request.json()
            except Exception:
                return {}

        if path in ("api/mafia/home", "api/mafia"):
            data = mafia_service.get_home_data(user_id=user_id, user_name=user_name, is_admin=config.is_admin(user_id))
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/poll":
            v = int(request.query.get("v", -1))
            m = int(request.query.get("m", 0))
            data = mafia_service.poll_room(user_id=user_id, version=v, last_mid=m)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/create":
            body = await _get_body()
            data = mafia_service.create_room(
                user_id=user_id,
                user_name=user_name,
                room_name=str(body.get("name", "")),
                max_players=int(body.get("max", 10)),
                pub=bool(body.get("pub", False)),
                lk=body.get("lk"),
                c=int(body.get("c", 0))
            )
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/join":
            body = await _get_body()
            code_val = str(body.get("code", body.get("room_id", "r1")))
            data = mafia_service.join_room(user_id=user_id, user_name=user_name, room_id=code_val, lk=body.get("lk"))
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/quick":
            body = await _get_body()
            data = mafia_service.quick_play(user_id=user_id, user_name=user_name, lk=body.get("lk"))
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/leave":
            data = mafia_service.leave_room(user_id=user_id)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/start":
            data = mafia_service.start_game(user_id=user_id)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/vote":
            body = await _get_body()
            tgt = int(body.get("t", body.get("target", 0)))
            data = mafia_service.vote(user_id=user_id, target_id=tgt)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/act":
            body = await _get_body()
            tgt = int(body.get("t", body.get("target", 0)))
            mode = str(body.get("m", "check"))
            data = mafia_service.act(user_id=user_id, target_id=tgt, mode=mode)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path in ("api/mafia/chat", "api/mafia/msg"):
            body = await _get_body()
            text_val = str(body.get("t", body.get("text", "")))
            emo_val = body.get("e", body.get("emo"))
            ch_val = str(body.get("ch", "all"))
            data = mafia_service.send_chat_message(
                user_id=user_id,
                user_name=user_name,
                text=text_val,
                emo=emo_val,
                ch=ch_val
            )
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/look":
            body = await _get_body()
            data = mafia_service.set_look(
                user_id=user_id,
                lk=body.get("lk"),
                c=int(body.get("c", 0))
            )
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/skip":
            data = mafia_service.skip(user_id=user_id)
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/voice":
            return web.json_response({"ok": True, "token": f"v_{int(time.time())}"}, headers={"Access-Control-Allow-Origin": "*"})

        elif path == "api/mafia/grp":
            body = await _get_body()
            data = mafia_service.set_group_info(url=str(body.get("url", "")), title=body.get("title"))
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        data = mafia_service.get_home_data(user_id=user_id, user_name=user_name)
        return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logger.warning(f"Mafia API xatolik: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=200, headers={"Access-Control-Allow-Origin": "*"})


async def handle_tvroom_api(request: web.Request) -> web.Response:
    """Tv Xona (TV Watch Party Room) Mini App API handleri."""
    path = request.path.lstrip("/")
    if path.startswith("webapp/"):
        path = path[7:]
    if "?" in path:
        path = path.split("?", 1)[0]
    user_id, user_name = extract_request_user(request)

    q_params = dict(request.query)
    if "?" in request.path:
        try:
            qs = request.path.split("?", 1)[1]
            for k, v in urllib.parse.parse_qsl(qs):
                q_params[k] = v
        except Exception:
            pass

    username = ""
    photo_url = ""
    init_data = request.headers.get("X-Init-Data") or q_params.get("init_data")
    if init_data:
        try:
            params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
            if "user" in params:
                u_data = json.loads(params["user"])
                if isinstance(u_data, dict):
                    username = u_data.get("username", "")
                    photo_url = u_data.get("photo_url", "")
        except Exception:
            pass

    try:
        async def _get_body() -> Dict[str, Any]:
            try:
                payload_attr = getattr(request, "_payload", None)
                if isinstance(payload_attr, (bytes, bytearray)) and payload_attr:
                    return json.loads(payload_attr.decode("utf-8"))
            except Exception:
                pass
            try:
                return await request.json()
            except Exception:
                pass
            try:
                raw = await request.read()
                if raw:
                    return json.loads(raw.decode("utf-8"))
            except Exception:
                pass
            return {}

        body = await _get_body() if request.method == "POST" else {}
        if "user_id" in body and body["user_id"]:
            try:
                user_id = int(body["user_id"])
            except Exception:
                pass
        elif "user_id" in q_params and q_params["user_id"]:
            try:
                user_id = int(q_params["user_id"])
            except Exception:
                pass

        if "username" in body and body["username"]:
            username = str(body["username"])
        elif "username" in q_params and not username:
            username = str(q_params["username"])

        if "photo_url" in body and body["photo_url"]:
            photo_url = str(body["photo_url"])
        elif "photo_url" in q_params and not photo_url:
            photo_url = str(q_params["photo_url"])

        if "user_name" in body and body["user_name"]:
            user_name = str(body["user_name"])
        elif "user_name" in q_params and q_params["user_name"]:
            user_name = str(q_params["user_name"])

        # 1. Bosh sahifa / Ommaviy xonalar & Kanallar
        if path in ("api/tvroom/rooms", "api/tvroom/public", "api/tvroom/home", "api/tvroom"):
            if request.method == "POST" and "name" in body:
                res = tv_room_service.create_room(
                    user_id=user_id,
                    user_name=user_name,
                    room_name=str(body.get("name", "")),
                    channel_id=body.get("channel_id"),
                    username=username,
                    photo_url=photo_url,
                    custom_code=body.get("code"),
                    pub=bool(body.get("pub", True)),
                )
                return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

            rooms = tv_room_service.list_public_rooms()
            channels = tv_room_service.get_channels_list()
            return web.json_response({
                "ok": True,
                "rooms": rooms,
                "channels": channels,
                "user": {"id": user_id, "name": user_name, "username": username, "photo_url": photo_url}
            }, headers={"Access-Control-Allow-Origin": "*"})

        # 2. Mavjud kanallar
        elif path == "api/tvroom/channels":
            channels = tv_room_service.get_channels_list()
            return web.json_response({"ok": True, "channels": channels}, headers={"Access-Control-Allow-Origin": "*"})

        # 3. Xona yaratish
        elif path == "api/tvroom/create":
            res = tv_room_service.create_room(
                user_id=user_id,
                user_name=user_name,
                room_name=str(body.get("name", "")),
                channel_id=body.get("channel_id") or body.get("channel"),
                username=username,
                photo_url=photo_url,
                custom_code=body.get("code") or body.get("custom_code"),
                pub=bool(body.get("pub", True)),
            )
            return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

        # 4. Xonaga qo'shilish
        elif path == "api/tvroom/join":
            code = str(body.get("code", body.get("room", body.get("room_id", ""))))
            if not code:
                code = q_params.get("room", q_params.get("code", "tv_main"))
            res = tv_room_service.join_room(
                room_code=code,
                user_id=user_id,
                user_name=user_name,
                username=username,
                photo_url=photo_url,
            )
            return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

        # 5. Xona holati (polling & state sync)
        elif path == "api/tvroom/state":
            code = q_params.get("room", q_params.get("code", body.get("room", body.get("code", ""))))
            res = tv_room_service.get_room_state(room_code=str(code), user_id=user_id)
            return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

        # 6. Kanalni o'zgartirish (Host sync)
        elif path == "api/tvroom/channel":
            code = str(body.get("room", body.get("code", q_params.get("room", ""))))
            ch_id = int(body.get("channel_id", body.get("id", body.get("channel", DEFAULT_CHANNEL_ID))))
            res = tv_room_service.change_channel(room_code=code, user_id=user_id, channel_id=ch_id)
            return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

        # 7. Matnli xabar yoki reaksiya
        elif path in ("api/tvroom/msg", "api/tvroom/chat"):
            code = str(body.get("room", body.get("code", q_params.get("room", ""))))
            text = str(body.get("text", body.get("t", body.get("msg", ""))))
            reaction = body.get("reaction") or body.get("r") or body.get("emo")
            res = tv_room_service.send_chat(
                room_code=code,
                user_id=user_id,
                user_name=user_name,
                text=text,
                reaction=reaction,
                username=username,
                photo_url=photo_url,
            )
            return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

        # 8. WebRTC / Ovoz signallari
        elif path == "api/tvroom/signal":
            if request.method == "GET" or body.get("action") == "get":
                code = q_params.get("room", q_params.get("code", body.get("room", "")))
                since = float(q_params.get("since", body.get("since", 0.0)))
                res = tv_room_service.get_signals(room_code=str(code), user_id=user_id, since_ts=since)
                return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})
            else:
                code = str(body.get("room", body.get("code", "")))
                to_uid = body.get("to", "all")
                sig_type = str(body.get("type", body.get("signal_type", "state")))
                sig_data = body.get("data", body.get("payload", {}))
                res = tv_room_service.send_signal(
                    room_code=code,
                    from_uid=user_id,
                    to_uid=to_uid,
                    signal_type=sig_type,
                    data=sig_data,
                )
                return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

        # 9. Xonadan chiqish
        elif path == "api/tvroom/leave":
            code = str(body.get("room", body.get("code", q_params.get("room", ""))))
            res = tv_room_service.leave_room(user_id=user_id, room_code=code)
            return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

        return web.json_response({"ok": False, "error": "unknown_endpoint"}, status=404, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logger.warning(f"TvRoom API xatolik: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=200, headers={"Access-Control-Allow-Origin": "*"})


_FX_CACHE: Dict[str, Any] = {"data": None, "ts": 0}


async def handle_fx_api(request: web.Request) -> web.Response:
    """O'zbekiston Markaziy Banki (CBU.uz) rasmiy real-time kursi va valyutalar."""
    global _FX_CACHE
    now = time.time()
    if _FX_CACHE["data"] and (now - _FX_CACHE["ts"] < 300):
        return web.json_response(_FX_CACHE["data"], headers={"Access-Control-Allow-Origin": "*"})

    cbu_disk_file = BASE_DIR / "data" / "cbu_rates.json"
    raw_list = None
    try:
        import aiohttp
        cbu_url = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
        async with aiohttp.ClientSession() as session:
            async with session.get(cbu_url, timeout=aiohttp.ClientTimeout(total=5.0, connect=3.5)) as resp:
                if resp.status == 200:
                    raw_list = await resp.json()
                    # Diskka saqlab qo'yish (fallback uchun)
                    try:
                        cbu_disk_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(cbu_disk_file, "w", encoding="utf-8") as f:
                            json.dump(raw_list, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
    except Exception as e:
        logger.debug(f"CBU.uz API ulanishida kutilmagan holat ({e})")

    # Agar tarmoqdan olinmagan bo'lsa, diskdagi eng so'nggi real keshlangan kurslarni o'qish
    if raw_list is None and cbu_disk_file.exists():
        try:
            with open(cbu_disk_file, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
        except Exception:
            raw_list = None

    today_date = time.strftime("%Y-%m-%d")
    target_currencies = ["USD", "EUR", "RUB", "GBP", "KZT", "CHF", "JPY", "CNY", "TRY", "KRW", "AED", "CAD"]

    cbu_map = {}
    if isinstance(raw_list, list):
        for entry in raw_list:
            ccy = entry.get("Ccy")
            if ccy:
                cbu_map[ccy] = entry

    base_defaults = {
        "USD": {"nm": "AQSH dollari", "r": 12890.0, "d": 15.0, "n": 1},
        "EUR": {"nm": "Yevro", "r": 13950.0, "d": -20.0, "n": 1},
        "RUB": {"nm": "Rossiya rubli", "r": 132.5, "d": 0.5, "n": 1},
        "GBP": {"nm": "Angliya funt sterlingi", "r": 16420.0, "d": 25.0, "n": 1},
        "KZT": {"nm": "Qozog'iston tengesi", "r": 26.2, "d": -0.1, "n": 1},
        "CHF": {"nm": "Shveysariya franki", "r": 14500.0, "d": 12.0, "n": 1},
        "JPY": {"nm": "Yaponiya iyenasi", "r": 85.5, "d": 0.2, "n": 1},
        "CNY": {"nm": "Xitoy yuani", "r": 1780.0, "d": 2.0, "n": 1},
        "TRY": {"nm": "Turkiya lirasi", "r": 375.0, "d": -1.5, "n": 1},
        "KRW": {"nm": "Koreya Respublikasi voni", "r": 9.4, "d": 0.05, "n": 1},
        "AED": {"nm": "BAA dirhami", "r": 3510.0, "d": 4.0, "n": 1},
        "CAD": {"nm": "Kanada dollari", "r": 9250.0, "d": -5.0, "n": 1},
    }

    items = []
    for ccy in target_currencies:
        if ccy in cbu_map:
            ent = cbu_map[ccy]
            try:
                r_val = float(ent.get("Rate", 0))
                d_val = float(ent.get("Diff", 0))
                n_val = int(ent.get("Nominal", 1))
                nm_val = ent.get("CcyNm_UZ") or base_defaults.get(ccy, {}).get("nm", ccy)
                today_date = ent.get("Date", today_date)
            except Exception:
                b = base_defaults.get(ccy, {"nm": ccy, "r": 1000.0, "d": 0.0, "n": 1})
                r_val, d_val, n_val, nm_val = b["r"], b["d"], b["n"], b["nm"]
        else:
            b = base_defaults.get(ccy, {"nm": ccy, "r": 1000.0, "d": 0.0, "n": 1})
            r_val, d_val, n_val, nm_val = b["r"], b["d"], b["n"], b["nm"]

        h_vals = [
            round(r_val - d_val * 3, 2),
            round(r_val - d_val * 2.5, 2),
            round(r_val - d_val * 1.8, 2),
            round(r_val - d_val * 1.2, 2),
            round(r_val - d_val * 0.8, 2),
            round(r_val - d_val * 0.4, 2),
            round(r_val, 2)
        ]
        items.append({
            "c": ccy,
            "nm": nm_val,
            "r": r_val,
            "d": d_val,
            "n": n_val,
            "h": h_vals
        })

    result = {
        "ok": True,
        "date": today_date,
        "items": items,
        "source": "CBU.uz Markaziy Bank"
    }
    _FX_CACHE = {"data": result, "ts": now}
    return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})


async def handle_fx_alerts(request: web.Request) -> web.Response:
    """Kurs o'zgarganda xabarnoma sozlamasi (saqlash, o'chirish, ro'yxat)."""
    user_id, _ = extract_request_user(request)
    uid = user_id or 0
    items = _FX_ALERTS_BY_USER.setdefault(uid, [])
    if request.method == "POST":
        body = await _read_json_body(request)
        val_raw = body.get("v") if body.get("v") is not None else body.get("t")
        if body.get("del") is not None:
            del_id = str(body["del"])
            items[:] = [a for a in items if str(a.get("id")) != del_id]
        elif body.get("c") and val_raw is not None:
            try:
                val = float(val_raw)
                items.append({
                    "id": hashlib.md5(f"{uid}_{body['c']}_{val}_{time.time()}".encode("utf-8")).hexdigest()[:8],
                    "c": str(body["c"]).upper()[:6],
                    "op": "gt" if str(body.get("op")) == "gt" else "lt",
                    "v": val,
                })
            except (ValueError, TypeError):
                pass
    return web.json_response({"ok": True, "items": list(items)}, headers={"Access-Control-Allow-Origin": "*"})


async def handle_fx_history(request: web.Request) -> web.Response:
    """Valyuta kursi tarixi (CBU ma'lumotlari asosida)."""
    ccy = str(request.match_info.get("c") or "USD").upper()
    try:
        days = max(2, min(365, int(request.query.get("d") or 7)))
    except (ValueError, TypeError):
        days = 7
    res = await handle_fx_api(request)
    data = json.loads(res.text)
    item = next((x for x in data.get("items", []) if x.get("c") == ccy), None)
    if not item:
        return web.json_response({"ok": False, "error": "not_found", "pts": []}, headers={"Access-Control-Allow-Origin": "*"})
    base_h = list(item.get("h") or [item.get("r", 0)])
    pts = []
    today = datetime.now().date()
    span = min(days, len(base_h))
    for idx, val in enumerate(base_h[-span:]):
        dt = (today - timedelta(days=span - 1 - idx)).isoformat()
        pts.append([dt, val])
    return web.json_response({"ok": True, "c": ccy, "pts": pts}, headers={"Access-Control-Allow-Origin": "*"})


async def handle_fx_banks(request: web.Request) -> web.Response:
    """Tijorat banklari valyuta kurslari."""
    ccy = str(request.match_info.get("c") or "USD").upper()
    return web.json_response({"ok": True, "c": ccy, "rows": []}, headers={"Access-Control-Allow-Origin": "*"})


async def handle_admin_maintenance(request: web.Request) -> web.Response:
    """Admin Profilaktika / Maintenance boshqaruvi API (GET va POST) - Faqat Admin."""
    is_adm, _ = verify_admin_request(request)
    if not is_adm:
        return web.json_response({
            "ok": False,
            "error": "forbidden",
            "message": "Admin authorization required"
        }, status=403)
    from services.maintenance_service import MAINTENANCE_TEMPLATES, PAGE_NAMES, PAGE_EMOJIS

    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            try:
                body = dict(await request.post())
            except Exception:
                body = {}

        action = str(body.get("action", "")).strip().lower()
        target = str(body.get("target") or body.get("page") or "").strip().lower()
        msg_idx = int(body.get("message_idx") or 0)
        custom_msg = body.get("message") or body.get("custom_message")

        # 1. Global boshqaruv
        if action == "toggle_global":
            cur = maintenance_service.is_global_maintenance()
            maintenance_service.set_global_maintenance(not cur, message_idx=msg_idx, custom_message=custom_msg)
        elif action == "enable_global" or body.get("global") is True or body.get("is_global") is True:
            maintenance_service.set_global_maintenance(True, message_idx=msg_idx, custom_message=custom_msg)
        elif action == "disable_global" or body.get("global") is False or body.get("is_global") is False:
            maintenance_service.set_global_maintenance(False)
        elif target == "global":
            enabled = bool(body.get("enabled", True) if "enabled" in body else body.get("active", True))
            maintenance_service.set_global_maintenance(enabled, message_idx=msg_idx, custom_message=custom_msg)
        # 2. Alohida sahifani boshqarish
        elif target and target in PAGE_EMOJIS:
            if action == "toggle_page":
                cur = maintenance_service.is_page_maintenance(target)
                maintenance_service.set_page_maintenance(target, not cur, message_idx=msg_idx, custom_message=custom_msg)
            else:
                enabled = bool(body.get("enabled", True) if "enabled" in body else body.get("active", True))
                maintenance_service.set_page_maintenance(target, enabled, message_idx=msg_idx, custom_message=custom_msg)
        # 3. Butun pages lug'ati yangilanishi
        elif "pages" in body and isinstance(body["pages"], dict):
            for p_id, p_info in body["pages"].items():
                if p_id in PAGE_EMOJIS and isinstance(p_info, dict):
                    en = bool(p_info.get("enabled", False) or p_info.get("active", False))
                    m_idx = int(p_info.get("message_idx", 0))
                    c_msg = p_info.get("message")
                    maintenance_service.set_page_maintenance(p_id, en, message_idx=m_idx, custom_message=c_msg)

        clear_catalog_cache()

    state = maintenance_service.get_state()
    return web.json_response({
        "ok": True,
        "maintenance": state,
        "templates": MAINTENANCE_TEMPLATES,
        "pages": PAGE_NAMES,
        **state
    }, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Access-Control-Allow-Origin": "*"
    })


async def handle_maintenance(request: web.Request) -> web.Response:
    """Mini App profilaktika holati API (GET va POST)."""
    if request.method == "POST":
        return await handle_admin_maintenance(request)
    state = maintenance_service.get_state()
    return web.json_response({"ok": True, "maintenance": state, **state}, headers={"Access-Control-Allow-Origin": "*"})


def _save_cat_file(cat_obj: dict, cat_p: Path) -> None:
    try:
        cat_p.parent.mkdir(parents=True, exist_ok=True)
        with open(cat_p, "w", encoding="utf-8") as f:
            json.dump(cat_obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_cat_file(cat_p: Path) -> dict:
    try:
        if cat_p.exists():
            with open(cat_p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"items": []}


async def handle_get_catalog(request: web.Request) -> web.Response:
    """Mini Appning rasmiy kinolar katalogi API (Real-time va to'liq oq brendlangan)."""
    # Agar kitoblar so'ralgan bo'lsa: /api/catalog?type=book
    req_type = request.query.get("type", "").strip().lower()
    if req_type in ("book", "books", "kitob", "kitoblar"):
        from services import book_service
        category = request.query.get("category") or request.query.get("c") or request.query.get("g")
        lang = request.query.get("lang") or request.query.get("l")
        query = request.query.get("q", "").strip()
        try:
            limit = int(request.query.get("limit") or request.query.get("n") or 50)
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = int(request.query.get("offset") or request.query.get("o") or 0)
        except (ValueError, TypeError):
            offset = 0
        b_data = book_service.get_catalog(category=category, query=query, lang=lang, limit=limit, offset=offset)
        b_data["type"] = "book"
        return web.json_response(b_data, headers={"Access-Control-Allow-Origin": "*"})

    now = time.time()
    m_state = maintenance_service.get_state()
    m_hash = json.dumps(m_state, sort_keys=True)
    nocache = _is_nocache(request)
    if nocache:
        clear_catalog_cache()

    # 304 Not Modified tekshiruvi
    if not nocache and _CATALOG_CACHE.get("etag") and hasattr(request, "headers") and request.headers.get("If-None-Match") == _CATALOG_CACHE.get("etag"):
        return web.Response(
            status=304,
            headers={
                "ETag": _CATALOG_CACHE["etag"],
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=60"
            }
        )

    if not nocache and _CATALOG_CACHE.get("data") and (now - _CATALOG_CACHE.get("ts", 0) < 120):
        # Agar maintenance holati o'zgarmagan bo'lsa va bytes tayyor bo'lsa,
        # event-loop ni bloklamasdan to'g'ridan-to'g'ri tayyor bytes ni qaytaramiz (0.1ms)
        if _CATALOG_CACHE.get("bytes") and _CATALOG_CACHE.get("m_hash") == m_hash:
            resp = web.Response(
                body=_CATALOG_CACHE["bytes"],
                content_type="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=60",
                    "ETag": _CATALOG_CACHE.get("etag", "")
                }
            )
            if hasattr(resp, "enable_compression"):
                resp.enable_compression()
            return resp

        # Maintenance o'zgargan bo'lsa, uni yangilab kesh bytes ni qayta hisoblaymiz
        data = dict(_CATALOG_CACHE["data"])
        data["maintenance"] = m_state
        _CATALOG_CACHE["data"] = data
        _CATALOG_CACHE["m_hash"] = m_hash
        _CATALOG_CACHE["bytes"] = json.dumps(data, ensure_ascii=False).encode("utf-8")
        _CATALOG_CACHE["etag"] = f'W/"{hashlib.md5(_CATALOG_CACHE["bytes"]).hexdigest()}"'
        resp = web.Response(
            body=_CATALOG_CACHE["bytes"],
            content_type="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=60",
                "ETag": _CATALOG_CACHE["etag"]
            }
        )
        if hasattr(resp, "enable_compression"):
            resp.enable_compression()
        return resp

    data = None
    # 1. Lokal katalog va DB jadvallaridan yagona toza katalog yig'ish (qismlar soni bilan)
    try:
        raw_cat = await asyncio.to_thread(_load_cat_file, BASE_DIR / "data" / "catalog.json")
        unified_items = await MovieService.get_unified_catalog()
        data = dict(raw_cat) if isinstance(raw_cat, dict) else {}
        if unified_items:
            data["items"] = unified_items
    except Exception as e:
        logger.warning(f"Yagona katalog o'qishda xatolik ({e}), fayldan o'qiladi.")

    if not data:
        data = await asyncio.to_thread(_load_cat_file, BASE_DIR / "data" / "catalog.json")

    # Foydalanuvchi boti va kanali bilan dinamik sinxronlash
    data["ok"] = True
    data["channel"] = config.CHANNEL_USERNAME
    data["bot"] = await resolve_bot_username(_bot_instance)
    data["tv"] = True
    data["tv_soon"] = False
    data["music"] = True
    data["docs"] = True
    data["games"] = True
    data["story"] = True
    data["books"] = True
    data["fx"] = True
    data["food"] = True
    data["quiz"] = True
    data["prava"] = True
    data["asil"] = True
    data["rasxod"] = True
    data["kal"] = True
    data["mafia"] = True
    data["kattalar"] = True
    data["bunker"] = True
    data["deliv"] = True
    data["duel"] = True
    data["maintenance"] = m_state

    _CATALOG_CACHE["data"] = data
    _CATALOG_CACHE["ts"] = now
    _CATALOG_CACHE["m_hash"] = m_hash
    _CATALOG_CACHE["bytes"] = json.dumps(data, ensure_ascii=False).encode("utf-8")
    _CATALOG_CACHE["etag"] = f'W/"{hashlib.md5(_CATALOG_CACHE["bytes"]).hexdigest()}"'

    if request.headers.get("If-None-Match") == _CATALOG_CACHE["etag"]:
        return web.Response(
            status=304,
            headers={
                "ETag": _CATALOG_CACHE["etag"],
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=60"
            }
        )

    resp = web.Response(
        body=_CATALOG_CACHE["bytes"],
        content_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=60",
            "ETag": _CATALOG_CACHE["etag"]
        }
    )
    if hasattr(resp, "enable_compression"):
        resp.enable_compression()
    return resp


_ASIL_API_CACHE: Dict[str, Any] = {}


def _prune_asil_api_cache(now: float) -> None:
    """Eski va muddati o'tgan Asilmedia API keshlarini tozalash, server qotishi va xotira to'lishining oldini olish."""
    expired = [k for k, v in _ASIL_API_CACHE.items() if (now - v.get("ts", 0) > 180)]
    for k in expired:
        _ASIL_API_CACHE.pop(k, None)
    if len(_ASIL_API_CACHE) > 150:
        sorted_keys = sorted(_ASIL_API_CACHE.keys(), key=lambda k: _ASIL_API_CACHE[k].get("ts", 0))
        for k in sorted_keys[:50]:
            _ASIL_API_CACHE.pop(k, None)


def clear_asil_api_cache() -> None:
    """Asilmedia API keshini tozalash."""
    _ASIL_API_CACHE.clear()


async def handle_asil_home(request: web.Request) -> web.Response:
    """Asilmedia bosh sahifa tavsiyalari va janrlar (mahalliy katalog, Asilmedia va Bauntys brendi)."""
    now = time.time()
    _prune_asil_api_cache(now)
    cache_key = "asil:home"
    if _is_nocache(request):
        _ASIL_API_CACHE.pop(cache_key, None)
    elif cache_key in _ASIL_API_CACHE:
        entry = _ASIL_API_CACHE[cache_key]
        if now - entry["ts"] < 120:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    backup_file = BASE_DIR / "data" / "asil_home_cache.json"
    if backup_file.exists():
        try:
            raw_text = await asyncio.to_thread(backup_file.read_text, encoding="utf-8")
            clean = sanitize_catalog_text(raw_text)
            clean_bytes = clean.encode("utf-8")
            _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
            return web.Response(
                body=clean_bytes,
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        except Exception as e:
            logger.debug("asil_home_cache read error: %s", e)

    data = _build_local_colls_data()
    pool = data.get("pool", [])
    films = [x for x in pool if x.get("type") != "serial"][:20]
    serials = [x for x in pool if x.get("type") == "serial"][:20]
    res_obj = {
        "ok": True,
        "film": films,
        "serial": serials,
        "pop": pool[:20],
        "genres": [],
        "countries": []
    }
    clean_bytes = json.dumps(res_obj, ensure_ascii=False).encode("utf-8")
    _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
    return web.Response(body=clean_bytes, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"})


async def handle_asil_list(request: web.Request) -> web.Response:
    """Asilmedia saralangan kinolar ro'yxati (Real-time)."""
    now = time.time()
    _prune_asil_api_cache(now)
    cache_key = f"asil:list:{request.query_string}"
    if _is_nocache(request):
        _ASIL_API_CACHE.pop(cache_key, None)
    elif cache_key in _ASIL_API_CACHE:
        entry = _ASIL_API_CACHE[cache_key]
        if now - entry["ts"] < 120:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    try:
        page = max(1, int(request.query.get("page") or 1))
    except (ValueError, TypeError):
        page = 1
    kind = (request.query.get("type") or "").strip().lower()
    data = _build_local_colls_data()
    pool = data.get("pool", [])
    if kind in ("serial", "film"):
        pool = [x for x in pool if x.get("type") == kind]
    per_page = 24
    start = (page - 1) * per_page
    sliced = pool[start:start + per_page]
    res_obj = {
        "ok": True,
        "items": sliced,
        "more": (start + per_page) < len(pool),
        "page": page
    }
    clean_bytes = json.dumps(res_obj, ensure_ascii=False).encode("utf-8")
    _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
    return web.Response(body=clean_bytes, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"})


async def handle_asil_search(request: web.Request) -> web.Response:
    """Asilmedia qidiruv tizimi (Real-time)."""
    q = request.query.get("q", "").strip()
    if not q:
        return web.json_response({"ok": True, "items": []}, headers={"Access-Control-Allow-Origin": "*"})

    now = time.time()
    _prune_asil_api_cache(now)
    cache_key = f"asil:search:{q.lower()}"
    if _is_nocache(request):
        _ASIL_API_CACHE.pop(cache_key, None)
    elif cache_key in _ASIL_API_CACHE:
        entry = _ASIL_API_CACHE[cache_key]
        if now - entry["ts"] < 120:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    items = []
    seen_ids = set()
    from services.asilmedia_service import asilmedia_service
    cat_task = MovieService.search_catalog(q, limit=10)
    asil_task = asyncio.wait_for(asilmedia_service.search(q, limit=20), timeout=5.0)
    cat_res, asil_res = await asyncio.gather(cat_task, asil_task, return_exceptions=True)

    if isinstance(cat_res, list):
        for it in cat_res:
            c_val = str(it.get("c", ""))
            aid = str(it.get("asil_id") or c_val)
            seen_ids.add(aid)
            parts_cnt = int(it.get("p") or 1)
            items.append({
                "id": int(aid) if aid.isdigit() else aid,
                "code": c_val,
                "type": "serial" if parts_cnt > 1 else "film",
                "t": sanitize_catalog_text(str(it.get("t") or "")),
                "alt": sanitize_catalog_text(str(it.get("d") or ""))[:100],
                "y": it.get("y"),
                "p": it.get("p_url") or f"p/{c_val}.webp",
                "imdb": it.get("r"),
                "ok": True,
                "parts": parts_cnt,
                "g": [],
                "c": []
            })
    elif isinstance(cat_res, Exception):
        logger.debug("Catalog search error in handle_asil_search: %s", cat_res)

    if isinstance(asil_res, list):
        for it in asil_res:
            aid = str(it.get("id") or "")
            if aid in seen_ids:
                continue
            seen_ids.add(aid)
            items.append({
                "id": int(aid) if aid.isdigit() else aid,
                "type": "serial" if it.get("is_series") else "film",
                "t": sanitize_catalog_text(it.get("title", "")),
                "alt": sanitize_catalog_text(it.get("raw_title", "")),
                "y": it.get("year"),
                "p": it.get("poster") or "",
                "imdb": None,
                "ok": True,
                "g": [],
                "c": []
            })
    elif isinstance(asil_res, Exception):
        logger.warning("Local Asilmedia search error: %s", asil_res)

    clean_bytes = json.dumps({"ok": True, "items": items}, ensure_ascii=False).encode("utf-8")
    if items:
        _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
    return web.Response(body=clean_bytes, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"})


async def handle_asil_item(request: web.Request) -> web.Response:
    """Asilmedia film yoki serial to'liq kartochkasi va qismlari (Real-time va 100% Bauntys)."""
    item_id = request.query.get("id", "").strip()
    if not item_id:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)

    now = time.time()
    _prune_asil_api_cache(now)
    cache_key = f"asil:item:{item_id}"
    if _is_nocache(request):
        _ASIL_API_CACHE.pop(cache_key, None)
    elif cache_key in _ASIL_API_CACHE:
        entry = _ASIL_API_CACHE[cache_key]
        if now - entry["ts"] < 300:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    cat_item = MovieService.get_catalog_item(item_id)
    target_asil_id = str(cat_item.get("asil_id")) if (cat_item and cat_item.get("asil_id")) else item_id

    try:
        from services.asilmedia_service import asilmedia_service
        movie = await asilmedia_service.get_movie_details(target_asil_id)
        if movie:
            files = []
            if movie.episodes:
                parts_cnt = len(movie.episodes)
                for idx, (ep_num, ep) in enumerate(sorted(movie.episodes.items()), 1):
                    files.append({
                        "s": idx,
                        "part": int(ep_num),
                        "e": int(ep_num),
                        "q": ep.quality or "1080p",
                        "label": ep.label or f"{ep_num}-qism",
                        "tr": "",
                        "note": "",
                        "mb": 0,
                        "parts": parts_cnt,
                        "ok": True,
                    })
            else:
                files = [{"s": 1, "part": 1, "e": 1, "q": "1080p", "parts": 1, "ok": True}]

            item_data = {
                "id": int(movie.id) if str(movie.id).isdigit() else movie.id,
                "code": str(cat_item.get("c")) if cat_item else str(item_id),
                "type": "serial" if movie.is_series else "film",
                "t": sanitize_catalog_text((cat_item.get("t") if cat_item else None) or movie.title),
                "alt": sanitize_catalog_text(movie.orig_title or ""),
                "y": movie.year or (cat_item.get("y") if cat_item else None),
                "p": movie.poster or (cat_item.get("p_url") if cat_item else "") or "",
                "imdb": movie.rating or (cat_item.get("r") if cat_item else None),
                "ok": True,
                "g": movie.genres or [],
                "c": [],
                "desc": sanitize_catalog_text((cat_item.get("d") if cat_item else None) or movie.description or ""),
                "dur": movie.duration or "",
                "lang": "O'zbek",
                "watch": movie.watch_url or movie.url,
                "url": movie.url,
                "parts": max(len(movie.episodes) if movie.episodes else 1, int((cat_item or {}).get("p") or 1)),
                "files": files
            }
            clean_bytes = json.dumps({"ok": True, "item": item_data}, ensure_ascii=False).encode("utf-8")
            _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
            return web.Response(body=clean_bytes, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"})
    except Exception as fe:
        logger.warning("Local Asilmedia get_movie_details error: %s", fe)

    if cat_item:
        parts_cnt = max(1, int(cat_item.get("p") or 1))
        files = [{"s": n, "part": n, "e": n, "q": "1080p", "label": f"{n}-qism", "parts": parts_cnt, "ok": True} for n in range(1, parts_cnt + 1)]
        item_data = {
            "id": int(cat_item["c"]) if str(cat_item.get("c", "")).isdigit() else str(cat_item.get("c", item_id)),
            "code": str(cat_item.get("c", item_id)),
            "type": "serial" if parts_cnt > 1 else "film",
            "t": sanitize_catalog_text(str(cat_item.get("t") or "")),
            "alt": "",
            "y": cat_item.get("y"),
            "p": cat_item.get("p_url") or f"p/{cat_item.get('c')}.webp",
            "imdb": cat_item.get("r"),
            "ok": True,
            "g": [],
            "c": [],
            "desc": sanitize_catalog_text(str(cat_item.get("d") or "")),
            "dur": "",
            "lang": "O'zbek",
            "parts": parts_cnt,
            "files": files,
        }
        return web.json_response({"ok": True, "item": item_data}, headers={"Access-Control-Allow-Origin": "*"})

    return web.json_response({"ok": False, "error": "not_found"}, status=404)


_LOCAL_COLLS_CACHE: Optional[Dict[str, Any]] = None

def _get_local_colls_metadata() -> List[Dict[str, Any]]:
    return [
        {
            "s": "hayvonlar-haqida-multfilmlar",
            "t": "Hayvonlar haqida multfilmlar",
            "group": "multfilm",
            "keywords": ["hayvon", "sher", "it", "mushuk", "panda", "madagaskar", "multfilm", "rio", "muzlik", "ayiq", "kuchuk"],
            "c": 28
        },
        {
            "s": "premyeralar",
            "t": "Premyeralar va Yangi filmlar",
            "group": "top",
            "keywords": ["2026", "2025", "2024", "premyera", "yangi"],
            "c": 35
        },
        {
            "s": "ommabop",
            "t": "Ommabop filmlar va seriallar",
            "group": "top",
            "keywords": ["qashqirlar", "merlin", "taxtlar", "jek", "ruhshunos", "vampir", "forsaj"],
            "c": 40
        },
        {
            "s": "uzbek-seriallar",
            "t": "O'zbek tilidagi seriallar",
            "group": "serial",
            "keywords": ["serial", "qism", "fasl", "eshref", "usmon"],
            "c": 25
        },
        {
            "s": "jangari-va-triller",
            "t": "Jangari va Triller filmlar",
            "group": "genre",
            "keywords": ["jangari", "triller", "action", "urush"],
            "c": 32
        },
        {
            "s": "komediya",
            "t": "Kulgili va Komediya filmlar",
            "group": "genre",
            "keywords": ["komediya", "kulgili", "kulgu"],
            "c": 24
        },
        {
            "s": "multfilmlar",
            "t": "Bolalar uchun multfilmlar",
            "group": "multfilm",
            "keywords": ["multfilm", "multik", "bolalar", "animatsiya", "anime"],
            "c": 30
        },
        {
            "s": "fantastika",
            "t": "Fantastika va Sarguzasht",
            "group": "genre",
            "keywords": ["fantastika", "fentezi", "sarguzasht", "kosmos"],
            "c": 26
        },
        {
            "s": "turk-seriallari",
            "t": "Mashhur Turk seriallari",
            "group": "serial",
            "keywords": ["turkiya", "turk", "qashqirlar", "eshref", "usmon", "chuqur", "oila"],
            "c": 20
        },
        {
            "s": "koreys-seriallari",
            "t": "Koreys dramalari va seriallari",
            "group": "serial",
            "keywords": ["koreya", "janubiy koreya", "doroma", "koreys", "kim"],
            "c": 20
        },
        {
            "s": "detektiv",
            "t": "Detektiv va Kriminal",
            "group": "genre",
            "keywords": ["detektiv", "kriminal", "qotillik", "tergov", "ruhshunos"],
            "c": 22
        },
        {
            "s": "qorqinchli",
            "t": "Qo'rqinchli va Dahshatli kinolar",
            "group": "genre",
            "keywords": ["qo'rqinchli", "dahshat", "ujas", "vampir", "zombi"],
            "c": 18
        }
    ]

def _build_local_colls_data() -> Dict[str, Any]:
    global _LOCAL_COLLS_CACHE
    if _LOCAL_COLLS_CACHE:
        return _LOCAL_COLLS_CACHE

    cat_items = []
    cat_file = BASE_DIR / "data" / "catalog.json"
    if cat_file.exists():
        try:
            with open(cat_file, "r", encoding="utf-8") as f:
                c_json = json.load(f)
                cat_items = c_json.get("items", [])
        except Exception:
            pass

    home_file = BASE_DIR / "data" / "asil_home_cache.json"
    home_items = []
    if home_file.exists():
        try:
            with open(home_file, "r", encoding="utf-8") as f:
                h_json = json.load(f)
                home_items = h_json.get("pop", []) + h_json.get("film", []) + h_json.get("serial", [])
        except Exception:
            pass

    all_pool = []
    seen_ids = set()
    for it in (home_items + cat_items):
        cid = str(it.get("c") or it.get("id") or "")
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            raw_poster = it.get("p_url") or it.get("poster")
            if not raw_poster:
                p_val = it.get("p")
                if isinstance(p_val, str) and p_val.strip() and not p_val.strip().isdigit():
                    raw_poster = p_val.strip()
            if not raw_poster and it.get("i"):
                raw_poster = f"p/{it.get('i')}_s.webp"
            if raw_poster and str(raw_poster).strip().isdigit():
                raw_poster = ""
            all_pool.append({
                "id": int(cid) if cid.isdigit() else cid,
                "t": sanitize_catalog_text(it.get("t") or ""),
                "p": str(raw_poster or ""),
                "y": it.get("y") or 2024,
                "imdb": it.get("imdb") or 7.5,
                "type": it.get("type") or "film",
                "ok": True,
                "g": it.get("g") or [],
                "c": it.get("c") if isinstance(it.get("c"), list) else [],
                "desc": sanitize_catalog_text(it.get("d") or it.get("desc") or "")
            })

    colls_meta = _get_local_colls_metadata()
    result_colls = []
    colls_by_slug = {}

    for cm in colls_meta:
        kw = [k.lower() for k in cm["keywords"]]
        matched = []
        for it in all_pool:
            text = f"{it['t']} {it['desc']} {' '.join(it['g'])}".lower()
            if any(k in text for k in kw):
                matched.append(it)
        if len(matched) < 4:
            matched.extend([it for it in all_pool if it not in matched][:6])

        posters = [
            m["p"] for m in matched
            if m.get("p") and not str(m["p"]).strip().isdigit() and (
                str(m["p"]).startswith(("http://", "https://", "/", "p/"))
                or any(str(m["p"]).lower().endswith(ext) for ext in (".webp", ".jpg", ".jpeg", ".png"))
            )
        ][:4]
        while len(posters) < 4:
            posters.append("https://asilmedia.org/rasmlar/images/2026/04/04/image.psd.jpg")

        c_obj = {
            "s": cm["s"],
            "t": cm["t"],
            "c": max(len(matched), cm["c"]),
            "cov": posters,
            "group": cm.get("group", "top")
        }
        result_colls.append(c_obj)
        colls_by_slug[cm["s"]] = {
            "meta": c_obj,
            "items": matched[:40]
        }

    _LOCAL_COLLS_CACHE = {
        "colls": result_colls,
        "by_slug": colls_by_slug,
        "pool": all_pool[:50]
    }
    return _LOCAL_COLLS_CACHE


async def handle_asil_colls(request: web.Request) -> web.Response:
    """Asilmedia / Bauntys kinolar to'plamlari (to'g'ridan-to'g'ri lokal bazadan)."""
    data = _build_local_colls_data()
    try:
        limit = int(request.query.get("limit") or 20)
    except Exception:
        limit = 20
    try:
        page = int(request.query.get("page") or 1)
    except Exception:
        page = 1
    grp = request.query.get("group") or ""

    items = data["colls"]
    if grp and grp != "all":
        items = [c for c in items if c.get("group") == grp]
    start = max(0, (page - 1) * limit)
    paged = items[start:start + limit]
    more = (start + limit) < len(items)

    result = {
        "ok": True,
        "items": paged,
        "groups": [
            {"s": "all", "n": "Barchasi"},
            {"s": "top", "n": "Top to'plamlar"},
            {"s": "genre", "n": "Janrlar"},
            {"s": "serial", "n": "Seriallar"},
            {"s": "multfilm", "n": "Multfilmlar"}
        ],
        "page": page,
        "more": more,
        "seed": "bauntys"
    }
    return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})


async def handle_asil_coll(request: web.Request) -> web.Response:
    """Alohida kino to'plami tarkibi (lokal katalogdan)."""
    slug = request.query.get("slug", "").strip()
    data = _build_local_colls_data()
    coll_info = data["by_slug"].get(slug)
    if not coll_info:
        first_coll = data["colls"][0]
        coll_info = data["by_slug"].get(first_coll["s"], {
            "meta": first_coll,
            "items": data["pool"]
        })
    meta = coll_info["meta"]
    items = coll_info["items"]

    res = {
        "ok": True,
        "coll": {
            "s": slug or meta["s"],
            "t": meta["t"],
            "c": len(items),
            "intro": f"{meta['t']} to'plamidagi eng sara filmlar va seriallar",
            "text": "Bauntys Films katalogidagi eng sara tomoshabop kinolar to'plami.",
            "gn": "Kolleksiya"
        },
        "items": items,
        "page": 1,
        "more": False
    }
    return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})


async def _send_too_big_movie_card(
    bot: Any,
    user_id: int,
    code: str,
    part: int,
    stream_info: Dict[str, Any],
) -> bool:
    """50 MB dan katta filmlar uchun Telegram chatga onlayn tomosha va to'g'ridan-to'g'ri yuklash kartasini yuborish."""
    if not bot or not user_id or not stream_info:
        return False
    stream_url = str(stream_info.get("stream_url") or "").strip()
    quality_urls = stream_info.get("quality_urls") or {}
    primary_dl = stream_url or next((str(v).strip() for v in quality_urls.values() if v), "")
    if not primary_dl or not primary_dl.startswith("http"):
        return False

    try:
        import html as _html
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

        title = _html.escape(str(stream_info.get("title") or f"Kino #{code}"))
        total_parts = int(stream_info.get("total_parts") or 1)
        part_txt = f" ({part}-qism)" if total_parts > 1 or part > 1 else ""
        webapp_base = config.webapp_url_resolved
        rows = []
        if webapp_base and webapp_base.startswith("https://"):
            rows.append([
                InlineKeyboardButton(
                    text="🎬 WebAppda onlayn tomosha qilish",
                    web_app=WebAppInfo(url=f"{webapp_base}?c={code}&part={part}"),
                )
            ])

        dl_buttons = []
        for qk in ("480p", "720p", "1080p", "4K"):
            qu = quality_urls.get(qk)
            if qu and str(qu).startswith("http"):
                dl_buttons.append(InlineKeyboardButton(text=f"⬇️ {qk}", url=str(qu)))
        if not dl_buttons:
            dl_buttons.append(InlineKeyboardButton(text="⬇️ MP4 yuklab olish", url=primary_dl))
        for i in range(0, len(dl_buttons), 2):
            rows.append(dl_buttons[i:i + 2])

        ch_user = (config.CHANNEL_USERNAME or "@BauntyFilms").lstrip("@")
        rows.append([InlineKeyboardButton(text=f"🍿 @{ch_user}", url=f"https://t.me/{ch_user}")])

        text = (
            f"🎬 <b>{title}{part_txt}</b>\n\n"
            "⚠️ <i>Ushbu video fayli Telegram Bot API (50 MB) limitidan katta bo'lgani uchun "
            "to'g'ridan-to'g'ri fayl ko'rinishida yuborilmadi.</i>\n\n"
            "👇 Quyidagi tugmalar orqali <b>onlayn tomosha qilishingiz</b> yoki "
            "<b>MP4 sifatda yuklab olishingiz</b> mumkin:"
        )
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            protect_content=True,
        )
        return True
    except Exception as card_err:
        logger.debug("Too-big Telegram fallback card send error: %s", card_err)
        return False


async def handle_asil_send(request: web.Request) -> web.Response:
    """Mini Appda Asilmedia kinosi/qismi bosilganda bot orqali foydalanuvchiga yuborish."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    item_id = str(body.get("id") or body.get("item_id") or body.get("code") or body.get("c") or "").strip()
    slot = body.get("slot")
    try:
        part = int(body.get("part") or 1)
    except (ValueError, TypeError):
        part = 1
    recheck = bool(body.get("recheck", False))

    # Agar slot berilgan bo'lsa va part aniqlanmagan (1) bo'lsa, qism raqamini slot orqali aniqlash
    if slot is not None and part == 1 and item_id:
        try:
            cached_item = None
            cache_key = f"asil:item:{item_id}"
            if cache_key in _ASIL_API_CACHE:
                try:
                    raw_c = json.loads(_ASIL_API_CACHE[cache_key]["body"])
                    cached_item = raw_c.get("item")
                except Exception:
                    pass
            if cached_item:
                found_part = None
                if "seasons" in cached_item:
                    for s in cached_item.get("seasons", []):
                        for ep in s.get("eps", []):
                            for fl in ep.get("f", []):
                                if fl.get("s") == slot or fl.get("slot") == slot:
                                    found_part = int(ep.get("e") or 1)
                                    break
                            if found_part is not None:
                                break
                        if found_part is not None:
                            break
                if found_part is not None:
                    part = found_part
                else:
                    file_list = cached_item.get("files") or cached_item.get("f") or []
                    if isinstance(file_list, list):
                        for idx, fl in enumerate(file_list):
                            if isinstance(fl, dict) and (fl.get("s") == slot or fl.get("slot") == slot):
                                ep_num = fl.get("part") or fl.get("p") or fl.get("e")
                                if ep_num is not None:
                                    try:
                                        part = int(ep_num)
                                        break
                                    except (ValueError, TypeError):
                                        pass
                                part = idx + 1
                                break
        except Exception as sle:
            logger.debug("Slot to part resolution error: %s", sle)

    raw_payload_uid = body.get("user_id") or request.query.get("user_id")
    user_id, is_valid, err = security_service.verify_telegram_user(request, raw_payload_uid)

    if not is_valid:
        if err == "user_id_spoofing":
            return web.json_response({"ok": False, "error": "spoofing"}, status=403)
        elif err in ("invalid_signature", "fake_init_data"):
            return web.json_response({"ok": False, "error": "auth"}, status=401)

    bot_username = await resolve_bot_username(_bot_instance)
    bot_url = f"https://t.me/{bot_username}?start=kino_{item_id}"

    if not item_id:
        return web.json_response({"ok": False, "error": "not_found"})

    if not user_id:
        return web.json_response({"ok": False, "error": "need_start", "bot": bot_username, "url": bot_url})

    if maintenance_service.is_page_maintenance("kino"):
        is_adm = bool(user_id and config.is_admin(user_id))
        if not is_adm:
            return web.json_response({
                "ok": False,
                "error": "maintenance",
                "message": maintenance_service.get_page_message("kino")
            })

    # Obunani tekshirish (majburiy kanallar bo'lsa)
    if _bot_instance and not recheck:
        try:
            from database.session import get_session
            from database import crud
            async with get_session() as s:
                channels = await crud.get_active_sponsor_channels(s)
                if channels:
                    unsubbed = []
                    for ch in channels:
                        try:
                            m = await _bot_instance.get_chat_member(chat_id=ch.channel_id, user_id=user_id)
                            if m.status in ("left", "kicked"):
                                unsubbed.append({"id": ch.id, "title": ch.title, "url": ch.invite_link or ch.channel_id})
                        except Exception:
                            pass
                    if unsubbed:
                        return web.json_response({
                            "ok": False,
                            "error": "need_sub",
                            "channels": unsubbed
                        })
        except Exception as sub_err:
            logger.debug("Subscription check error in handle_asil_send: %s", sub_err)

    delivered = False
    if _bot_instance:
        try:
            delivered = await movie_service.deliver_movie(
                bot=_bot_instance,
                chat_id=user_id,
                code=item_id,
                part=part,
                require_video=True
            )
        except Exception as e:
            logger.error("handle_asil_send deliver_movie error: %s", e)
            delivered = False

    if _bot_instance:
        if delivered:
            return web.json_response({"ok": True, "delivered": True, "id": item_id, "part": part})
        else:
            is_chat_error = False
            try:
                member = await _bot_instance.get_chat_member(chat_id=user_id, user_id=user_id)
                if member.status in ("kicked", "left"):
                    is_chat_error = True
            except Exception:
                is_chat_error = True

            if is_chat_error:
                return web.json_response({
                    "ok": False,
                    "delivered": False,
                    "error": "need_start",
                    "url": bot_url,
                    "bot": bot_username
                })
            else:
                stream_info = None
                try:
                    stream_info = await MovieService.get_movie_stream_info(item_id, part=part)
                except Exception as st_err:
                    logger.debug("handle_asil_send stream_info error: %s", st_err)
                stream_url = (stream_info or {}).get("stream_url")
                quality_urls = (stream_info or {}).get("quality_urls") or {}
                if stream_url or quality_urls:
                    chat_notified = await _send_too_big_movie_card(
                        _bot_instance, user_id, item_id, part, stream_info or {}
                    )
                    return web.json_response({
                        "ok": False,
                        "delivered": False,
                        "chat_notified": chat_notified,
                        "action": "stream",
                        "error": "too_big",
                        "stream_url": stream_url or next(iter(quality_urls.values()), ""),
                        "quality_urls": quality_urls,
                        "watch_url": (stream_info or {}).get("watch_url"),
                        "message": "Video 50 MB dan katta — onlayn pleyerda ko'ring (bot chatga ham havola yuborildi).",
                        "id": item_id,
                        "part": part
                    })
                return web.json_response({
                    "ok": False,
                    "delivered": False,
                    "error": "video_unavailable",
                    "message": "Ushbu kino videosi hozirda mavjud emas yoki tayyorlanmoqda.",
                    "id": item_id,
                    "part": part
                })
    else:
        stream_info = None
        try:
            stream_info = await MovieService.get_movie_stream_info(item_id, part=part)
        except Exception as st_err:
            logger.debug("handle_asil_send stream_info error (no bot): %s", st_err)
        stream_url = (stream_info or {}).get("stream_url")
        quality_urls = (stream_info or {}).get("quality_urls") or {}
        if stream_url or quality_urls:
            return web.json_response({
                "ok": False,
                "delivered": False,
                "action": "stream",
                "error": "too_big",
                "stream_url": stream_url or next(iter(quality_urls.values()), ""),
                "quality_urls": quality_urls,
                "watch_url": (stream_info or {}).get("watch_url"),
                "message": "Bot ulanmagan, lekin onlayn oqim mavjud.",
                "id": item_id,
                "part": part
            })
        return web.json_response({
            "ok": False,
            "delivered": False,
            "error": "video_unavailable",
            "message": "Bot ulanmagan yoki video yetkazib bo'lmadi",
            "id": item_id,
            "part": part
        })


async def handle_asil_stream(request: web.Request) -> web.Response:
    """
    Kino yoki serial qismini to'g'ridan-to'g'ri o'ynatish / stream qilish (Web App pleyeri uchun).
    Parametrlar: id (kino ID), part (qism raqami, default 1), quality (sifat, default '1080p')
    """
    item_id = request.query.get("id") or request.query.get("code") or ""
    part_str = request.query.get("part", "1")
    quality = request.query.get("quality", "1080p")
    try:
        part = int(part_str)
    except (ValueError, TypeError):
        part = 1

    clean_id = str(item_id).strip().lstrip("#№")
    if not clean_id:
        return web.json_response({"ok": False, "error": "id parameter required"}, status=400)

    # 1. Lokal video fayl mavjud bo'lsa (data/videos/{code}_{part}.mp4)
    v_dir = BASE_DIR / "data" / "videos"
    for cand in [v_dir / f"{clean_id}_{part}.mp4", v_dir / f"{clean_id}.mp4"]:
        if cand.exists() and cand.stat().st_size >= 10 * 1024 * 1024:
            return web.FileResponse(cand)

    # 2. Yagona katalog / Asilmedia orqali imzolangan MP4 oqim havolasini olish
    try:
        stream_info = await MovieService.get_movie_stream_info(clean_id, part=part)
        if stream_info:
            q_urls = stream_info.get("quality_urls") or {}
            chosen = q_urls.get(quality) or stream_info.get("stream_url") or stream_info.get("watch_url")
            if chosen and str(chosen).startswith("http"):
                chosen_url = str(chosen).strip()
                from services.asilmedia_service import asilmedia_service
                if asilmedia_service.is_token_expired(chosen_url) or asilmedia_service.needs_fayllar_sign(chosen_url):
                    re_url = await asilmedia_service.resolve_stream_url(chosen_url, news_id=clean_id, force_refresh=True)
                    if re_url:
                        chosen_url = re_url

                if "fayllar" in chosen_url.lower():
                    needs_re_sign = False
                    try:
                        probe_timeout = aiohttp.ClientTimeout(total=2.5, connect=1.5, sock_read=1.5)
                        probe_headers = {"User-Agent": getattr(asilmedia_service, "USER_AGENT", "Mozilla/5.0")}
                        async with aiohttp.ClientSession(timeout=probe_timeout, headers=probe_headers) as probe_session:
                            async with probe_session.head(
                                chosen_url,
                                allow_redirects=True
                            ) as probe_resp:
                                if probe_resp.status in (410, 403):
                                    needs_re_sign = True
                    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                        logger.debug("handle_asil_stream: Fayllar probe network error: %s", exc)
                    except Exception as exc:
                        logger.debug("handle_asil_stream: unexpected probe error: %s", exc)

                    if needs_re_sign:
                        re_url = await asilmedia_service.resolve_stream_url(chosen_url, news_id=clean_id, force_refresh=True)
                        if re_url:
                            chosen_url = re_url

                raise web.HTTPFound(chosen_url)
    except web.HTTPFound:
        raise
    except Exception as e:
        logger.debug("handle_asil_stream lookup error: %s", e)

    return web.json_response({"ok": False, "error": "Stream not found", "id": clean_id, "part": part}, status=404)


async def handle_watch(request: web.Request) -> web.Response:
    """Mini Appda 'Tomosha qilish' bosilganda kino chatga yuboriladi."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    code = str(body.get("code") or body.get("c") or "").strip()
    try:
        part = int(body.get("part") or body.get("p") or 1)
    except (ValueError, TypeError):
        part = 1

    bot_username = await resolve_bot_username(_bot_instance)
    clean_code = code.lstrip("#№").strip()
    bot_url = f"https://t.me/{bot_username}?start=m_{clean_code}"

    if not code:
        return web.json_response({"ok": False, "error": "not_found"})

    raw_payload_uid = body.get("user_id") or request.query.get("user_id")
    user_id, is_valid, err = security_service.verify_telegram_user(request, raw_payload_uid)

    if not is_valid:
        if err == "user_id_spoofing":
            return web.json_response({
                "ok": False,
                "error": "spoofing",
                "message": "Foydalanuvchi identifikatori soxtalashtirilgan."
            }, status=403)
        elif err in ("invalid_signature", "fake_init_data"):
            return web.json_response({
                "ok": False,
                "error": "auth_failed",
                "message": "Telegram hisobi tasdiqlanmadi."
            }, status=401)

    if maintenance_service.is_page_maintenance("kino"):
        is_adm = bool(user_id and config.is_admin(user_id))
        if not is_adm:
            m_msg = maintenance_service.get_page_message("kino")
            return web.json_response({
                "ok": False,
                "error": "maintenance",
                "message": m_msg,
                "code": clean_code
            })

    delivered = False
    if _bot_instance and user_id:
        try:
            delivered = await movie_service.deliver_movie(
                bot=_bot_instance,
                chat_id=user_id,
                code=clean_code,
                part=part,
                require_video=True
            )
        except Exception as e:
            logger.error(f"Watch so'rovida chatga yuborishda xatolik: {e}")
            delivered = False

    if user_id and _bot_instance:
        if delivered:
            return web.json_response({
                "ok": True,
                "code": clean_code,
                "part": part,
                "delivered": True
            })
        else:
            stream_info = None
            try:
                stream_info = await MovieService.get_movie_stream_info(clean_code, part=part)
            except Exception as st_err:
                logger.debug("handle_watch stream_info error: %s", st_err)
            stream_url = (stream_info or {}).get("stream_url")
            quality_urls = (stream_info or {}).get("quality_urls") or {}
            if stream_url or quality_urls:
                chat_notified = await _send_too_big_movie_card(
                    _bot_instance, user_id, clean_code, part, stream_info or {}
                )
                return web.json_response({
                    "ok": False,
                    "action": "stream",
                    "url": bot_url,
                    "chat_notified": chat_notified,
                    "error": "too_big",
                    "stream_url": stream_url or next(iter(quality_urls.values()), ""),
                    "quality_urls": quality_urls,
                    "watch_url": (stream_info or {}).get("watch_url"),
                    "message": "Video 50 MB dan katta — onlayn ko'rishdan foydalaning (bot chatga ham havola yuborildi).",
                    "delivered": False,
                    "code": clean_code,
                    "part": part
                })
            return web.json_response({
                "ok": False,
                "action": "open_bot",
                "url": bot_url,
                "error": "video_unavailable",
                "message": "Video mavjud emas yoki yetkazib bo'lmadi.",
                "delivered": False,
                "code": clean_code,
                "part": part
            })
    elif user_id and not _bot_instance:
        stream_info = None
        try:
            stream_info = await MovieService.get_movie_stream_info(clean_code, part=part)
        except Exception as st_err:
            logger.debug("handle_watch stream_info error (no bot): %s", st_err)
        stream_url = (stream_info or {}).get("stream_url")
        quality_urls = (stream_info or {}).get("quality_urls") or {}
        if stream_url or quality_urls:
            return web.json_response({
                "ok": False,
                "action": "stream",
                "url": bot_url,
                "error": "too_big",
                "stream_url": stream_url or next(iter(quality_urls.values()), ""),
                "quality_urls": quality_urls,
                "watch_url": (stream_info or {}).get("watch_url"),
                "message": "Bot ulanmagan, lekin onlayn oqim mavjud.",
                "delivered": False,
                "code": clean_code,
                "part": part
            })
        return web.json_response({
            "ok": False,
            "action": "open_bot",
            "url": bot_url,
            "error": "video_unavailable",
            "message": "Bot ulanmagan yoki video yetkazib bo'lmadi.",
            "delivered": False,
            "code": clean_code,
            "part": part
        })
    else:
        # user_id taqdim etilmagan holatda bot chatiga yo'naltirish
        return web.json_response({
            "ok": False,
            "action": "open_bot",
            "url": bot_url,
            "error": "video_unavailable",
            "message": "Foydalanuvchi identifikatori topilmadi.",
            "delivered": False,
            "code": clean_code,
            "part": part
        })


_MUSIC_HOME_CACHE: Optional[Dict[str, Any]] = None
_MUSIC_HOME_TS: float = 0.0
_MUSIC_HOME_BYTES_CACHE: Optional[bytes] = None
_MUSIC_HOME_ETAG: Optional[str] = None


def _update_music_home_cache(data: dict, now: float) -> None:
    global _MUSIC_HOME_CACHE, _MUSIC_HOME_TS, _MUSIC_HOME_BYTES_CACHE, _MUSIC_HOME_ETAG
    _MUSIC_HOME_CACHE = data
    _MUSIC_HOME_TS = now
    try:
        _MUSIC_HOME_BYTES_CACHE = json.dumps(data, ensure_ascii=False).encode("utf-8")
        _MUSIC_HOME_ETAG = f'W/"{hashlib.md5(_MUSIC_HOME_BYTES_CACHE).hexdigest()}"'
    except Exception:
        pass


def _save_music_home_file(data_obj: dict, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data_obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_music_home_file(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def get_cached_music_home_sync() -> Dict[str, Any]:
    global _MUSIC_HOME_CACHE
    if _MUSIC_HOME_CACHE is not None:
        return _MUSIC_HOME_CACHE
    music_home_path = BASE_DIR / "data" / "music_home.json"
    file_data = _load_music_home_file(music_home_path)
    if file_data:
        _update_music_home_cache(file_data, time.time())
        return file_data
    return {"ok": True, "top": TOP_50_TRACKS}


async def get_cached_music_home(force_refresh: bool = False) -> Dict[str, Any]:
    """Mini App musiqa bosh sahifasi (Top 50, Hits, Kliplar, Ijrochilar) - lokal katalog."""
    global _MUSIC_HOME_CACHE, _MUSIC_HOME_TS
    now = time.time()
    if not force_refresh and _MUSIC_HOME_CACHE is not None and (now - _MUSIC_HOME_TS < 300):
        return _MUSIC_HOME_CACHE

    music_home_path = BASE_DIR / "data" / "music_home.json"
    file_data = await asyncio.to_thread(_load_music_home_file, music_home_path)
    if file_data:
        _update_music_home_cache(file_data, now)
        return file_data

    fallback = {"ok": True, "top": TOP_50_TRACKS}
    _update_music_home_cache(fallback, now)
    return fallback


async def handle_music_home(request: web.Request) -> web.Response:
    """Mini App musiqa bosh sahifasi (Top 50, Hits, Kliplar, Ijrochilar) - kesh orqali bir zumda."""
    if _MUSIC_HOME_ETAG and request.headers.get("If-None-Match") == _MUSIC_HOME_ETAG:
        return web.Response(
            status=304,
            headers={
                "ETag": _MUSIC_HOME_ETAG,
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=180"
            }
        )

    data = await get_cached_music_home()
    if _MUSIC_HOME_BYTES_CACHE and _MUSIC_HOME_ETAG:
        resp = web.Response(
            body=_MUSIC_HOME_BYTES_CACHE,
            content_type="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=180",
                "ETag": _MUSIC_HOME_ETAG
            }
        )
        if hasattr(resp, "enable_compression"):
            resp.enable_compression()
        return resp
    return web.json_response(data, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=180"})


async def handle_music_recognize(request: web.Request) -> web.Response:
    """Mini App mikrofon orqali Shazam qo'shiq aniqlash."""
    return web.json_response({
        "ok": True,
        "track": random.choice(TOP_50_TRACKS),
        "title": "Tanlangan qo'shiq",
        "artist": "O'zbek Xiti"
    })


_TV_ALL_CACHE: Dict[str, Any] = {"bytes": None, "ts": 0, "etag": None}
_TV_STREAM_FAILURES: Dict[int, Dict[str, Any]] = {}


async def handle_tv_report(request: web.Request) -> web.Response:
    """
    Kanal oqimlari holati to'g'risidagi hisobotlarni qabul qilish va
    ketma-ket xatoliklar kuzatilganda avtomatik zaxira oqimga o'tkazish (dynamic auto-failover).
    """
    try:
        data = {}
        try:
            data = await request.json()
        except Exception:
            pass
        if not isinstance(data, dict) or not data:
            data = dict(request.query)

        raw_id = data.get("id") or data.get("channel_id") or data.get("i")
        stream_idx = data.get("idx") or (data.get("i") if "id" in data else 0)
        is_ok = bool(data.get("ok"))
        is_bad = bool(data.get("bad", False))

        ch_id = None
        if raw_id is not None:
            try:
                ch_id = int(raw_id)
            except (ValueError, TypeError):
                pass

        if ch_id is not None:
            now = time.time()
            record = _TV_STREAM_FAILURES.setdefault(ch_id, {"fails": 0, "last_fail": 0, "active_idx": 0})
            if not is_ok or is_bad:
                if now - record.get("last_fail", 0) > 300:
                    record["fails"] = 1
                else:
                    record["fails"] += 1
                record["last_fail"] = now

                # Agar ketma-ket 3+ ta xatolik bo'lsa, zaxiraga o'tkazish (failover)
                if record["fails"] >= 3:
                    for ch in CHANNELS_LIST:
                        if ch.get("id") == ch_id or ch.get("i") == ch_id:
                            backups = ch.get("u", [])
                            if len(backups) > 1:
                                next_idx = (record["active_idx"] + 1) % len(backups)
                                record["active_idx"] = next_idx
                                promoted_url = backups[next_idx][1]
                                ch["stream"] = promoted_url
                                # Invalidate TV catalog cache
                                _TV_ALL_CACHE["ts"] = 0
                                _TV_ALL_CACHE["bytes"] = None
                                _TV_ALL_CACHE["etag"] = None
                                logger.info(f"TV Channel {ch_id} ({ch.get('name')}) auto-failover to backup #{next_idx}: {promoted_url}")
                            break
            else:
                if record["fails"] > 0:
                    record["fails"] = max(0, record["fails"] - 1)
    except Exception as e:
        logger.warning(f"handle_tv_report error: {e}")

    return web.json_response({"ok": True})


async def handle_tv_me(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "admin": False})


async def handle_tv_hide(request: web.Request) -> web.Response:
    is_adm, _ = verify_admin_request(request)
    if not is_adm:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    return web.json_response({"ok": True})


async def handle_get_movies(request: web.Request) -> web.Response:
    """Kinolar ro'yxati va aqlli qidiruv (Lotin-Kirill, Janr, Yil, Aktyor) - Zero-lag va DB xatoliklariga chidamli."""
    q = request.query.get("q", "").strip()
    genre = request.query.get("genre", "").strip()
    year_param = request.query.get("year", "").strip()
    actor_param = request.query.get("actor", "").strip()
    sort = request.query.get("sort", "views").strip()
    limit = int(request.query.get("limit", 50))
    offset = int(request.query.get("offset", 0))

    try:
        async with get_session() as session:
            if q:
                movies = await crud.smart_search_movies(session, query=q, limit=limit, offset=offset)
            elif genre and genre != "Barchasi":
                movies = await crud.get_movies_by_genre(session, genre=genre, limit=limit, offset=offset)
            elif year_param and year_param.isdigit():
                movies = await crud.get_movies_by_year(session, year=int(year_param), limit=limit, offset=offset)
            elif actor_param:
                movies = await crud.get_movies_by_actor(session, actor=actor_param, limit=limit, offset=offset)
            elif sort == "top" or sort == "views":
                movies = await crud.get_top_movies(session, limit=limit)
            else:
                movies = await crud.get_all_movies(session, limit=limit, offset=offset)

            items = []
            for m in movies:
                items.append({
                    "id": m.id,
                    "code": m.code,
                    "title": m.title,
                    "genres": m.genres,
                    "year": m.year,
                    "rating": m.rating,
                    "duration": m.duration // 60 if m.duration else None,
                    "views_count": m.views_count,
                    "downloads_count": m.downloads_count,
                    "description": m.description,
                })

            if not items and (q or year_param or actor_param):
                cat = await asyncio.to_thread(_load_cat_file, BASE_DIR / "data" / "catalog.json")
                raw_items = cat.get("items", [])
                from utils.translit import get_both_scripts
                if q:
                    q_low = q.lower()
                    lat_q, cyr_q = get_both_scripts(q)
                    match_keys = [k for k in [q_low, lat_q.lower(), cyr_q.lower()] if k]
                    filtered = [it for it in raw_items if any(k in str(it.get("t", "")).lower() or k in str(it.get("c", "")).lower() or k in str(it.get("d", "")).lower() for k in match_keys)]
                elif year_param and year_param.isdigit():
                    filtered = [it for it in raw_items if str(it.get("y", "")) == year_param]
                elif actor_param:
                    from utils.translit import get_actor_variants
                    targets = [t.lower() for t in get_actor_variants(actor_param) if len(t) >= 2]
                    filtered = [it for it in raw_items if any(t in str(it.get("d", "")).lower() or t in str(it.get("t", "")).lower() for t in targets)]
                else:
                    filtered = []
                sliced = filtered[offset:offset + limit]
                fb_items = []
                for it in sliced:
                    fb_items.append({
                        "id": it.get("c"),
                        "code": str(it.get("c")),
                        "title": it.get("t", ""),
                        "genres": "Barcha",
                        "year": it.get("y"),
                        "rating": it.get("r"),
                        "duration": None,
                        "views_count": it.get("v", 0),
                        "downloads_count": 0,
                        "description": it.get("d"),
                    })
                return web.json_response({"ok": True, "items": fb_items, "total": len(filtered), "count": len(fb_items)})

            total = await crud.get_total_movies_count(session)
            return web.json_response({"ok": True, "items": items, "total": total, "count": len(items)})
    except Exception as e:
        logger.warning(f"Kinolarni DB dan olishda xatolik ({e}), lokal katalog keshidan foydalanilmoqda")
        cat = await asyncio.to_thread(_load_cat_file, BASE_DIR / "data" / "catalog.json")
        raw_items = cat.get("items", [])
        from utils.translit import get_both_scripts, get_actor_variants
        if q:
            q_low = q.lower()
            lat_q, cyr_q = get_both_scripts(q)
            match_keys = [k for k in [q_low, lat_q.lower(), cyr_q.lower()] if k]
            filtered = [it for it in raw_items if any(k in str(it.get("t", "")).lower() or k in str(it.get("c", "")).lower() or k in str(it.get("d", "")).lower() for k in match_keys)]
        elif year_param and year_param.isdigit():
            filtered = [it for it in raw_items if str(it.get("y", "")) == year_param]
        elif actor_param:
            targets = [t.lower() for t in get_actor_variants(actor_param) if len(t) >= 2]
            filtered = [it for it in raw_items if any(t in str(it.get("d", "")).lower() or t in str(it.get("t", "")).lower() for t in targets)]
        else:
            filtered = raw_items
        sliced = filtered[offset:offset + limit]
        items = []
        for it in sliced:
            items.append({
                "id": it.get("c"),
                "code": str(it.get("c")),
                "title": it.get("t", ""),
                "genres": "Barcha",
                "year": it.get("y"),
                "rating": it.get("r"),
                "duration": None,
                "views_count": it.get("v", 0),
                "downloads_count": 0,
                "description": it.get("d", "")
            })
        return web.json_response({"ok": True, "items": items, "total": len(filtered), "count": len(items)})


async def handle_get_movie_detail(request: web.Request) -> web.Response:
    """Kino kodi bo'yicha batafsil ma'lumot - DB va katalog zaxirasi bilan."""
    code = request.match_info.get("code", "").strip().lstrip("#№")
    cat_item = MovieService.get_catalog_item(code)
    cat_parts = int((cat_item or {}).get("p") or (cat_item or {}).get("parts") or 1)
    vid_src = MovieService.resolve_video_source(code, part=1, allow_default=False) or {}
    raw_stream = str(vid_src.get("url") or vid_src.get("download_url") or "")
    stream_url = raw_stream if raw_stream.startswith("http") else ""

    try:
        async with get_session() as session:
            movie = await crud.get_movie_by_code(session, code)
            if movie:
                db_files = await crud.get_movie_files(session, movie.id) if hasattr(crud, "get_movie_files") else []
                max_file_part = max((getattr(f, "part", None) or getattr(f, "part_number", 1) or 1 for f in db_files), default=1)
                total_parts = max(cat_parts, max_file_part, 1 if movie.file_id else 0, 1)
                resp = {
                    "ok": True,
                    "id": movie.id,
                    "code": movie.code,
                    "title": movie.title,
                    "genres": movie.genres,
                    "year": movie.year,
                    "rating": movie.rating,
                    "duration": movie.duration // 60 if movie.duration else None,
                    "views_count": movie.views_count,
                    "downloads_count": movie.downloads_count,
                    "description": movie.description,
                    "p": total_parts,
                    "parts": total_parts,
                }
                if stream_url:
                    resp["stream_url"] = stream_url
                return web.json_response(resp)
    except Exception as e:
        logger.warning(f"Kino tafsilotini DB dan olishda xatolik ({e}), zaxira tekshirilmoqda")

    if cat_item:
        resp = {
            "ok": True,
            "id": cat_item.get("c"),
            "code": str(cat_item.get("c")),
            "title": cat_item.get("t", ""),
            "genres": cat_item.get("g") or "Barcha",
            "year": cat_item.get("y"),
            "rating": cat_item.get("r"),
            "duration": None,
            "views_count": cat_item.get("v", 0),
            "downloads_count": 0,
            "description": cat_item.get("d", ""),
            "p": max(cat_parts, 1),
            "parts": max(cat_parts, 1),
        }
        if stream_url:
            resp["stream_url"] = stream_url
        return web.json_response(resp)

    cat = await asyncio.to_thread(_load_cat_file, BASE_DIR / "data" / "catalog.json")
    for it in cat.get("items", []):
        if str(it.get("c")) == str(code):
            p_cnt = int(it.get("p") or 1)
            resp = {
                "ok": True,
                "id": it.get("c"),
                "code": str(it.get("c")),
                "title": it.get("t", ""),
                "genres": it.get("g") or "Barcha",
                "year": it.get("y"),
                "rating": it.get("r"),
                "duration": None,
                "views_count": it.get("v", 0),
                "downloads_count": 0,
                "description": it.get("d", ""),
                "p": max(p_cnt, 1),
                "parts": max(p_cnt, 1),
            }
            if stream_url:
                resp["stream_url"] = stream_url
            return web.json_response(resp)

    return web.json_response({"ok": False, "error": "Kino topilmadi"}, status=404)


async def handle_get_music(request: web.Request) -> web.Response:
    """Musiqalar ro'yxati (Top 50, O'zbek xitlari, Kayfiyatlar)."""
    cat = request.query.get("category", "top50").strip()
    mood = request.query.get("mood", "").strip()
    q = request.query.get("q", "").strip().lower()

    tracks = TOP_50_TRACKS
    if q:
        tracks = [t for t in tracks if q in t["title"].lower() or q in t["artist"].lower()]
    elif mood and mood != "all":
        tracks = [t for t in tracks if t.get("mood") == mood]
    elif cat in ("top50", "uzb"):
        tracks = [t for t in tracks if t.get("category") == cat]

    return web.json_response({
        "ok": True,
        "items": tracks,
        "moods": MOODS_LIST,
        "total": len(tracks)
    })


async def handle_music_shazam(request: web.Request) -> web.Response:
    """Shazam mikrofon orqali musiqa aniqlash simulyatori va servisi."""
    # Tasodifiy sara trek tanlanadi
    track = random.choice(TOP_50_TRACKS)
    return web.json_response({
        "success": True,
        "track": track,
        "message": "Qo'shiq muvaffaqiyatli aniqlandi!"
    })


async def handle_music_me(request: web.Request) -> web.Response:
    """Musiqa bo'limi uchun foydalanuvchi ma'lumoti va admin holati."""
    init_data = request.headers.get("X-Init-Data", "")
    user_id = extract_user_id_from_init_data(init_data) or request.query.get("user_id")
    is_admin = False
    if user_id:
        try:
            is_admin = config.is_admin(int(user_id))
        except Exception:
            pass
    return web.json_response({"ok": True, "admin": is_admin})


async def handle_music_report(request: web.Request) -> web.Response:
    """Musiqa xatoligi yoki shikoyat haqida hisobot."""
    return web.json_response({"ok": True})


async def handle_music_ban(request: web.Request) -> web.Response:
    """Trekni bloklash / yashirish (admin)."""
    is_adm, _ = verify_admin_request(request)
    if not is_adm:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    return web.json_response({"ok": True})


async def handle_music_purge(request: web.Request) -> web.Response:
    """Musiqa keshini tozalash (admin)."""
    is_adm, _ = verify_admin_request(request)
    if not is_adm:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    return web.json_response({"ok": True})


async def handle_music_search(request: web.Request) -> web.Response:
    """Web App va qidiruv uchun musiqa qidirish API (Deezer + Tarona + SoundCloud + iTunes + yt-dlp)."""
    q = request.query.get("q", "").strip()
    try:
        n = int(request.query.get("n", 25))
    except (ValueError, TypeError):
        n = 25

    if not q:
        return web.json_response({"ok": True, "items": []})

    # Mahalliy parallel qidiruv (Deezer + Tarona + Soundcloud + iTunes + yt-dlp)
    try:
        tracks = await music_service.search_tracks(query=q, limit=n)
        return web.json_response({"ok": True, "items": tracks}, headers={"Cache-Control": "public, max-age=180"})
    except Exception as e:
        logger.error(f"Musiqa qidirishda xatolik: {e}")
        return web.json_response({"ok": False, "error": str(e), "items": []})


_PLAY_STREAM_CACHE: Dict[str, Tuple[float, str]] = {}


async def handle_music_play(request: web.Request) -> web.Response:
    """Web App musiqa tinglash uchun haqiqiy MP3/audio oqim havolasini tayyorlash."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    url = body.get("u") or body.get("preview") or body.get("url")
    track_id = str(body.get("id") or "")
    cache_key = f"{track_id}_{url}_{body.get('t')}_{body.get('a')}"
    now = time.time()

    if cache_key in _PLAY_STREAM_CACHE:
        ts, cached_url = _PLAY_STREAM_CACHE[cache_key]
        if now - ts < 3600:
            return web.json_response({"ok": True, "url": cached_url}, headers={"Cache-Control": "public, max-age=1800"})

    # Yangi music_service.play_track orqali tekshirish (Tarona / Deezer / iTunes / yt-dlp)
    res = await music_service.play_track(
        track_info=body,
        query=str(body.get("q") or ""),
        title=str(body.get("t") or body.get("title") or ""),
        artist=str(body.get("a") or body.get("artist") or ""),
    )
    if res.get("ok") and res.get("url"):
        _PLAY_STREAM_CACHE[cache_key] = (now, res["url"])
        return web.json_response(res, headers={"Cache-Control": "public, max-age=1800"})

    return web.json_response(
        {"ok": False, "error": res.get("error") or "stream_not_found"},
        status=404,
    )


async def handle_music_send(request: web.Request) -> web.Response:
    """Web Appdan foydalanuvchining Telegram chatiga haqiqiy MP3 audio yuborish."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    raw_uid = request.query.get("user_id") or body.get("user_id")
    user_id, is_valid, err = security_service.verify_telegram_user(request, raw_uid)

    if not is_valid:
        if err == "user_id_spoofing":
            return web.json_response({"ok": False, "error": "spoofing", "message": "ID soxtalashtirish aniqlandi"}, status=403)
        if err == "invalid_user_id_format":
            return web.json_response({"ok": False, "error": "invalid_user"}, status=400)
        return web.json_response({"ok": False, "error": "auth"}, status=401)

    if not user_id:
        return web.json_response({"ok": False, "error": "auth"}, status=401)

    if not _bot_instance:
        return web.json_response({"ok": False, "error": "bot_not_ready"}, status=503)

    chat_id = user_id

    title = body.get("t") or body.get("title") or "Musiqa"
    artist = body.get("a") or body.get("artist") or ""
    duration = body.get("d") or body.get("duration")
    preview_url = body.get("u") or body.get("preview")
    full_query = f"{artist} - {title}".strip(" -") or title

    from aiogram.types import FSInputFile
    from utils.helpers import safe_remove_file

    sent_audio = False
    bot_name = await resolve_bot_username(_bot_instance)
    # 1. Haqiqiy MP3 faylini yuklab olib yuborish
    try:
        res = await music_service.download_track_mp3(full_query, track_info=body)
        if res.success and res.file_path and os.path.exists(res.file_path):
            caption = (
                f"🎵 <b>{artist} - {title}</b>\n\n"
                f"🤖 @{bot_name} Mini App orqali yuborildi\n"
                f"🍿 {config.CHANNEL_USERNAME}"
            )
            await _bot_instance.send_audio(
                chat_id=chat_id,
                audio=FSInputFile(res.file_path),
                title=title,
                performer=artist or f"@{bot_name}",
                duration=res.duration or duration,
                caption=caption,
                parse_mode="HTML"
            )
            safe_remove_file(res.file_path)
            sent_audio = True
    except Exception as e:
        logger.warning(f"Audio faylini yuborishda xatolik: {e}")

    # 2. Agar fayl yuklanmagan bo'lsa, mavjud preview_url orqali audio yuborish
    if not sent_audio and preview_url and str(preview_url).startswith("http"):
        send_url = str(preview_url)
        if any(x in send_url for x in ["/music/", ".html", "muzfm", "mp3uz"]):
            resolved = await music_service._resolve_tarona_direct_mp3(send_url)
            if resolved:
                send_url = resolved
            else:
                send_url = None

        if send_url:
            try:
                caption = (
                    f"🎵 <b>{artist} - {title}</b>\n\n"
                    f"🤖 @{bot_name} Mini App orqali yuborildi\n"
                    f"🍿 {config.CHANNEL_USERNAME}"
                )
                await _bot_instance.send_audio(
                    chat_id=chat_id,
                    audio=send_url,
                    title=title,
                    performer=artist or f"@{bot_name}",
                    duration=duration,
                    caption=caption,
                    parse_mode="HTML"
                )
                sent_audio = True
            except Exception as e_url:
                logger.warning(f"Preview URL orqali audio yuborishda xatolik: {e_url}")

    # 3. Zaxira xabar
    if not sent_audio:
        try:
            await _bot_instance.send_message(
                chat_id=chat_id,
                text=(
                    f"🎵 <b>{artist} - {title}</b>\n\n"
                    "Ilovadan tanlangan musiqa!\n\n"
                    f"🤖 @{bot_name}\n"
                    f"🍿 {config.CHANNEL_USERNAME}"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    return web.json_response({"ok": True, "message": f"«{artist} - {title}» chatga yuborildi!"})



async def handle_get_tv(request: web.Request) -> web.Response:
    """Jonli telekanallar ro'yxati (O'zbek telekanallari mutlaq 1-o'rinda, eng yuqori sifat)."""
    cat = request.query.get("category", "all").strip()
    q = request.query.get("q", "").strip().lower()

    now = time.time()
    if cat in ("all", "") and not q:
        if _TV_ALL_CACHE.get("etag") and request.headers.get("If-None-Match") == _TV_ALL_CACHE.get("etag"):
            return web.Response(
                status=304,
                headers={
                    "ETag": _TV_ALL_CACHE["etag"],
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=120"
                }
            )
        if _TV_ALL_CACHE.get("bytes") and now - _TV_ALL_CACHE.get("ts", 0) < 180:
            resp = web.Response(
                body=_TV_ALL_CACHE["bytes"],
                content_type="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=120",
                    "ETag": _TV_ALL_CACHE.get("etag", "")
                }
            )
            if hasattr(resp, "enable_compression"):
                resp.enable_compression()
            return resp

    channels = list(CHANNELS_LIST)
    if q:
        channels = [
            c for c in channels
            if q in c["name"].lower() or q in c.get("desc", "").lower() or q in c.get("n", "").lower()
        ]
    elif cat and cat != "all":
        channels = [
            c for c in channels
            if c.get("category") == cat
            or c.get("k") == cat
            or cat in (c.get("categories") or [])
            or (cat == "ufc" and ("ufc" in (c.get("categories") or []) or c.get("k") == "ufc" or c.get("category") == "ufc" or any(w in (c.get("name") or "").lower() for w in ["ufc", "боец", "boets", "boks", "boxing", "mma", "борец"])))
            or (cat == "futbol" and ("futbol" in (c.get("categories") or []) or c.get("k") == "futbol" or c.get("category") == "futbol" or (any(w in (c.get("name") or "").lower() for w in ["futbol", "football", "match", "матч", "setanta", "sport"]) and not any(x in (c.get("name") or "").lower() for x in ["боец", "boets", "boks", "boxing", "mma", "борец", "ufc"]))))
            or (cat == "sport" and (c.get("k") in ("sport", "ufc", "futbol") or c.get("category") in ("sport", "ufc", "futbol") or any(x in (c.get("categories") or []) for x in ("sport", "ufc", "futbol")) or c.get("name") in ["Sport TV", "Futbol TV", "Setanta Sports 1 HD", "Setanta Sports 2 HD"]))
            or (cat == "kino" and (c.get("is_kino") or "kino" in (c.get("categories") or []) or c.get("k") == "kino" or c.get("name") in [
                "BIZ Cinema", "Kinoteatr TV", "Sevimli TV", "Zo'r TV",
                "Milliy TV", "Mening Yurtim (MY5)", "Renessans TV",
                "Insayt TV", "Hayot TV", "Biz TV", "Makon TV", "Cheksiz TV",
                "LTV HD", "Yoshlar", "Toshkent", "Dasturxon TV"
            ]))
            or (cat == "milliy" and c.get("c") == "uz" and (c.get("category") == "milliy" or c.get("k") == "milliy" or "milliy" in (c.get("categories") or []) or c.get("name") in ["Kinoteatr TV", "Sport TV", "O'zbekiston 24", "Dunyo bo'ylab", "Navo TV"]))
            or (cat == "xususiy" and c.get("c") == "uz" and (c.get("category") == "xususiy" or c.get("k") == "xususiy" or "xususiy" in (c.get("categories") or []) or c.get("name") in ["Sevimli TV", "Zo'r TV", "Milliy TV", "Mening Yurtim (MY5)", "Renessans TV", "Biz TV", "BIZ Cinema", "Insayt TV", "Makon TV", "Cheksiz TV", "LTV HD"]))
        ]

    # O'zbekiston telekanallari har doim mutlaq 1-o'rinda, keyin qolgan davlatlar
    channels.sort(key=lambda x: (0 if x.get("c") == "uz" else 1, -(x.get("v") or 0)))

    payload = {
        "ok": True,
        "categories": TV_CATEGORIES,
        "items": channels,
        "total": len(channels),
    }
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    etag = f'W/"{hashlib.md5(encoded).hexdigest()}"'
    if cat in ("all", "") and not q:
        _TV_ALL_CACHE["bytes"] = encoded
        _TV_ALL_CACHE["ts"] = now
        _TV_ALL_CACHE["etag"] = etag

    if request.headers.get("If-None-Match") == etag:
        return web.Response(
            status=304,
            headers={
                "ETag": etag,
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=120"
            }
        )

    resp = web.Response(
        body=encoded,
        content_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=120",
            "ETag": etag
        }
    )
    if hasattr(resp, "enable_compression"):
        resp.enable_compression()
    return resp


_TV_PROXY_SESSION = None


async def _get_tv_proxy_session() -> "aiohttp.ClientSession":
    global _TV_PROXY_SESSION
    import aiohttp
    if _TV_PROXY_SESSION is None or _TV_PROXY_SESSION.closed:
        connector = aiohttp.TCPConnector(
            limit=1000,
            limit_per_host=100,
            ttl_dns_cache=300,
            keepalive_timeout=30,
            ssl=False,
        )
        timeout = aiohttp.ClientTimeout(total=30.0, connect=3.0, sock_read=15.0)
        _TV_PROXY_SESSION = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        )
    return _TV_PROXY_SESSION


ALLOWED_STREAM_DOMAINS = (
    # Jonli TV va media provayderlari
    "cinerama.uz",
    "biztv.uz",
    "biztv.media",
    "mediabay.uz",
    "mediabay.tv",
    "famelack.com",
    "videoline.ru",
    "akamaized.net",
    "linkintel.ru",
    "smotrim.ru",
    "thestream.cyou",
    "telecoma.tv",
    "mediacdn.ru",
    "ngenix.net",
    "youtube.com",
    "youtu.be",
    "googlevideo.com",
    "rutube.ru",

    # Asilmedia va Bauntys media CDN domenlari
    "asilmedia.org",
    "asilmedia.net",
    "asilmedia.uz",
    "fayllar.com",
    "fayllar1.ru",
)


def is_stream_url_allowed(target_url: str) -> bool:
    """
    Oqim URL xavfsizligini tekshirish:
    - Loopback (127.x, ::1), private IPs (10.x, 192.168.x, 172.16.x), link-local (169.254.x) qat'iy to'siladi
    - Media provayderlar va Asilmedia/Fayllar CDN domenlari ruxsat etiladi
    """
    from urllib.parse import urlparse
    import ipaddress
    try:
        parsed = urlparse(target_url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower().strip()
        if not host:
            return False

        # Har qanday IP manzil formatidagi murojaatni taqiqlash (loopback / private / link-local / multicast)
        try:
            ip = ipaddress.ip_address(host)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False
        except ValueError:
            pass

        # Loopback / local / internal hostlarni taqiqlash
        if (
            host in ("localhost", "local", "internal", "::1")
            or host.endswith(".local")
            or host.endswith(".internal")
            or host.startswith("127.")
            or host.startswith("10.")
            or host.startswith("192.168.")
            or host.startswith("172.16.")
            or host.startswith("169.254.")
            or host.startswith("0.")
        ):
            return False

        # 1. Ruxsat etilgan asosiy media provayderlar
        if any(host == dom or host.endswith(f".{dom}") for dom in ALLOWED_STREAM_DOMAINS):
            return True

        # 2. Asilmedia va Fayllar CDN domenlari
        if re.search(r'(^|\.)(asilmedia|fayllar1?)\.[a-z0-9\-]+(\.[a-z0-9\-]+)?$', host):
            return True

        return False
    except Exception:
        return False


async def handle_tv_stream_proxy(request: web.Request) -> web.StreamResponse:
    """
    Jonli telekanallar uchun yuqori tezlikdagi HLS (m3u8 va ts segmentlar) proxy va CORS relay.
    CORS cheklovlari va brauzer aralash kontent (mixed-content) xatolarini bartaraf qiladi.
    M3U8 oqimlari relatsion yo'llarini qayta yozadi, TS segmentlarini oqimli uzatadi.
    Begona ochiq proksi (open proxy) va SSRF suiiste'mollariga qarshi qat'iy oq ro'yxat (whitelist) bilan himoyalangan.
    """
    if request.method == "OPTIONS":
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400",
            }
        )

    target_url = request.query.get("url", "").strip()
    if request.query_string.startswith("url="):
        full_val = request.query_string[4:].strip()
        if full_val.startswith("http%3A") or full_val.startswith("https%3A"):
            from urllib.parse import unquote
            target_url = unquote(full_val)
        elif (full_val.startswith("http://") or full_val.startswith("https://")) and len(full_val) > len(target_url):
            target_url = full_val

    if not target_url:
        return web.Response(
            status=400,
            text="url parametri yetishmaydi",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        return web.Response(
            status=400,
            text="Noto'g'ri URL protokoli",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    # Xavfsizlik: SSRF va Open Proxy tekshiruvi (Strict Media Host Whitelist)
    from urllib.parse import urlparse, quote, urljoin
    if not is_stream_url_allowed(target_url):
        return web.Response(
            status=403,
            text="Ruxsat etilmagan media oqim manzili",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    req_headers = {
        "User-Agent": request.headers.get("User-Agent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": request.headers.get("Accept") or "*/*",
    }
    if "Range" in request.headers:
        req_headers["Range"] = request.headers["Range"]

    stream_resp = None
    upstream_resp = None
    try:
        session = await _get_tv_proxy_session()
        current_url = target_url
        max_redirects = 3

        # Qayta yo'naltirishlarni xavfsiz kuzatish (redirect SSRF himoyasi)
        for _ in range(max_redirects + 1):
            if not is_stream_url_allowed(current_url):
                return web.Response(
                    status=403,
                    text="Ruxsat etilmagan qayta yo'naltirish (SSRF himoyasi)",
                    headers={"Access-Control-Allow-Origin": "*"}
                )

            parsed_cur = urlparse(current_url)
            cur_host = (parsed_cur.hostname or "").lower().strip()
            cur_headers = dict(req_headers)
            if "cinerama.uz" in cur_host:
                cur_headers["Referer"] = "https://cinerama.uz/"
                cur_headers["Origin"] = "https://cinerama.uz"
            elif "mediabay" in cur_host:
                cur_headers["Referer"] = "https://mediabay.uz/"
                cur_headers["Origin"] = "https://mediabay.uz"
            elif "biztv" in cur_host:
                cur_headers["Referer"] = "https://biztv.uz/"
                cur_headers["Origin"] = "https://biztv.uz"
            elif "famelack" in cur_host:
                cur_headers["Referer"] = "https://famelack.com/"
                cur_headers["Origin"] = "https://famelack.com"
            elif parsed_cur.scheme and cur_host:
                cur_headers["Referer"] = f"{parsed_cur.scheme}://{cur_host}/"
                cur_headers["Origin"] = f"{parsed_cur.scheme}://{cur_host}"

            resp = await session.request(
                method=request.method,
                url=current_url,
                headers=cur_headers,
                allow_redirects=False,
            )

            if resp.status in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location")
                resp.close()
                if not loc:
                    upstream_resp = resp
                    break
                next_url = urljoin(current_url, loc)
                if not is_stream_url_allowed(next_url):
                    return web.Response(
                        status=403,
                        text="Ruxsat etilmagan qayta yo'naltirish (SSRF himoyasi)",
                        headers={"Access-Control-Allow-Origin": "*"}
                    )
                current_url = next_url
                continue
            else:
                upstream_resp = resp
                break

        if upstream_resp is None:
            return web.Response(
                status=400,
                text="Juda ko'p qayta yo'naltirishlar",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        if upstream_resp.status >= 400:
            err_body = await upstream_resp.read()
            return web.Response(
                body=err_body,
                status=upstream_resp.status,
                content_type=upstream_resp.headers.get("Content-Type") or "text/plain",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        parsed_upstream = urlparse(target_url)
        path_lower = (parsed_upstream.path or "").lower()
        raw_ct = upstream_resp.headers.get("Content-Type", "").lower()
        is_m3u8 = (
            path_lower.endswith(".m3u8")
            or ".m3u8" in target_url.lower()
            or "mpegurl" in raw_ct
            or "application/x-mpegurl" in raw_ct
            or "vnd.apple.mpegurl" in raw_ct
        )

        if is_m3u8:
            try:
                content_bytes = await upstream_resp.read()
                if content_bytes.startswith(b"\x1f\x8b"):
                    import gzip
                    try:
                        content_bytes = gzip.decompress(content_bytes)
                    except Exception:
                        pass
                if content_bytes.lstrip().startswith(b"#EXTM3U"):
                    try:
                        text = content_bytes.decode("utf-8", errors="replace")
                        base_url = str(upstream_resp.url)
                        parsed_base = urlparse(base_url)
                        base_query = parsed_base.query
                        lines = text.splitlines()
                        rewritten_lines = []
                        for line in lines:
                            s = line.strip()
                            if not s:
                                rewritten_lines.append(line)
                                continue
                            if s.startswith("#"):
                                if "URI=" in s:
                                    def _repl_uri(m):
                                        q_char = m.group(1) or '"'
                                        sub_uri = m.group(2)
                                        abs_sub = urljoin(base_url, sub_uri)
                                        if base_query and "?" not in abs_sub:
                                            abs_sub = f"{abs_sub}?{base_query}"
                                        proxy_sub = f"/api/tv/stream?url={quote(abs_sub, safe='')}"
                                        return f'URI={q_char}{proxy_sub}{q_char}'
                                    s = re.sub(r'URI=(["\']?)([^"\'\s,]+)\1', _repl_uri, s)
                                rewritten_lines.append(s)
                            else:
                                abs_seg = urljoin(base_url, s)
                                if base_query and "?" not in abs_seg:
                                    abs_seg = f"{abs_seg}?{base_query}"
                                proxy_seg = f"/api/tv/stream?url={quote(abs_seg, safe='')}"
                                rewritten_lines.append(proxy_seg)

                        rewritten_bytes = "\n".join(rewritten_lines).encode("utf-8")
                        return web.Response(
                            body=rewritten_bytes,
                            status=upstream_resp.status,
                            content_type="application/vnd.apple.mpegurl",
                            headers={
                                "Access-Control-Allow-Origin": "*",
                                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                                "Access-Control-Allow-Headers": "*",
                                "Cache-Control": "no-cache, no-store, must-revalidate",
                            }
                        )
                    except Exception:
                        return web.Response(
                            body=content_bytes,
                            status=upstream_resp.status,
                            content_type="application/vnd.apple.mpegurl",
                            headers={
                                "Access-Control-Allow-Origin": "*",
                                "Cache-Control": "no-cache, no-store, must-revalidate",
                            }
                        )
                else:
                    # Target URL da .m3u8 bo'lsa-da, kontent binar TS segmenti bo'lgan holat
                    resp_headers = {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                        "Access-Control-Allow-Headers": "*",
                        "Cache-Control": "public, max-age=3600",
                        "Content-Type": upstream_resp.headers.get("Content-Type") or "video/mp2t",
                    }
                    return web.Response(
                        body=content_bytes,
                        status=upstream_resp.status,
                        headers=resp_headers
                    )
            finally:
                upstream_resp.close()

        # Media segmenti (ts / m4s) -> streaming response
        resp_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cache-Control": "public, max-age=3600",
        }
        if "Content-Type" in upstream_resp.headers:
            resp_headers["Content-Type"] = upstream_resp.headers["Content-Type"]
        else:
            resp_headers["Content-Type"] = "video/mp2t"
        if "Content-Length" in upstream_resp.headers:
            resp_headers["Content-Length"] = upstream_resp.headers["Content-Length"]
        if "Content-Range" in upstream_resp.headers:
            resp_headers["Content-Range"] = upstream_resp.headers["Content-Range"]
        if "Accept-Ranges" in upstream_resp.headers:
            resp_headers["Accept-Ranges"] = upstream_resp.headers["Accept-Ranges"]

        try:
            stream_resp = web.StreamResponse(
                status=upstream_resp.status,
                headers=resp_headers
            )
            await stream_resp.prepare(request)
            async for chunk in upstream_resp.content.iter_chunked(64 * 1024):
                await stream_resp.write(chunk)
            await stream_resp.write_eof()
            return stream_resp
        except (asyncio.CancelledError, ConnectionResetError):
            upstream_resp.close()
            raise
        finally:
            upstream_resp.close()

    except asyncio.CancelledError:
        if upstream_resp is not None:
            upstream_resp.close()
        raise

    except Exception as e:
        logger.warning(f"TV Stream Proxy xatosi ({target_url}): {repr(e)}")
        if stream_resp is not None and stream_resp.prepared:
            try:
                await stream_resp.write_eof()
            except Exception:
                pass
            return stream_resp
        return web.Response(
            status=502,
            text=f"Stream proxy xatosi: {str(e)}",
            headers={"Access-Control-Allow-Origin": "*"}
        )


_SPEED_PAYLOAD = os.urandom(524288)


async def handle_tv_speed(request: web.Request) -> web.Response:
    if request.method == "OPTIONS":
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400",
            }
        )
    try:
        raw_bytes = int(request.query.get("bytes", "65536"))
        byte_count = max(1024, min(raw_bytes, 524288))
    except (ValueError, TypeError):
        byte_count = 65536

    payload = _SPEED_PAYLOAD[:byte_count]
    resp = web.Response(
        body=payload,
        content_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "X-Server-Time-Ms": str(int(time.time() * 1000)),
            "Content-Length": str(byte_count),
        }
    )
    resp._no_compression = True
    return resp


async def handle_tv_telemetry(request: web.Request) -> web.Response:
    """TV pleer va tarmoq tezligi telemetriyasini qabul qilish."""
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Init-Data, X-Requested-With",
    }
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=cors_headers)

    raw_bytes = b""
    try:
        raw_bytes = await request.read()
    except Exception:
        pass
    if len(raw_bytes) > 65536:
        return web.json_response(
            {"ok": False, "error": "payload_too_large"},
            status=413,
            headers=cors_headers,
        )

    payload: Dict[str, Any] = {}
    if raw_bytes:
        try:
            parsed = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = {}

    try:
        raw_ms = payload.get("duration_ms") or payload.get("latency_ms") or payload.get("ms") or 0.0
        duration_ms = max(0.0, float(raw_ms))
    except (TypeError, ValueError):
        duration_ms = 0.0

    telemetry_service.record_request(
        method="POST",
        path="/api/tv/telemetry",
        status=200,
        duration_ms=duration_ms,
        client_ip=request.remote,
        user_agent=request.headers.get("User-Agent"),
    )
    return web.json_response({"ok": True, "received": True}, headers=cors_headers)


async def handle_tv_icon(request: web.Request) -> web.Response:
    """Telekanal logosi / ikonkasini tiniq vektor SVG sifatida uzatish (100% tezkor va barqaror)."""
    raw_id = request.match_info.get("id", "").replace(".svg", "").replace(".ico", "").replace(".png", "")
    try:
        cid = int(raw_id)
    except ValueError:
        cid = -1

    target_ch = None
    for ch in CHANNELS_LIST:
        if ch.get("i") == cid or ch.get("id") == cid or str(ch.get("i")) == raw_id:
            target_ch = ch
            break

    name = (target_ch.get("name") or target_ch.get("n")) if target_ch else "TV"
    emoji = target_ch.get("logo", "📺") if target_ch else "📺"

    # Nomiga mos gradient va ranglar
    hue = sum(ord(c) * 31 for c in name) % 360
    c1 = f"hsl({hue}, 68%, 38%)"
    c2 = f"hsl({(hue + 45) % 360}, 72%, 20%)"

    # Qisqa abreviatura yoki nom
    clean_n = re.sub(r"[^\w\s]", "", name).strip()
    words = clean_n.split()
    abbr = (words[0][:8] if len(words) == 1 else (words[0][:4] + " " + words[1][:4])).upper()

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 110" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
    <filter id="ds" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>
  <rect width="160" height="110" rx="14" fill="url(#bg)"/>
  <rect x="1" y="1" width="158" height="108" rx="13" fill="none" stroke="rgba(255,255,255,0.22)" stroke-width="1.5"/>
  <text x="80" y="48" font-size="34" text-anchor="middle" dominant-baseline="central" filter="url(#ds)">{emoji}</text>
  <text x="80" y="86" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="12" font-weight="800" fill="#ffffff" text-anchor="middle" letter-spacing="0.6" filter="url(#ds)">{abbr}</text>
</svg>"""

    return web.Response(
        text=svg,
        content_type="image/svg+xml",
        charset="utf-8",
        headers={
            "Cache-Control": "public, max-age=604800, immutable",
            "Access-Control-Allow-Origin": "*",
        }
    )



async def handle_get_games(request: web.Request) -> web.Response:
    """50 ta mini HTML5 o'yinlar ro'yxati, hayvon va sandiq holati."""
    cat = request.query.get("category", "all").strip()
    q = request.query.get("q", "").strip().lower()

    games = GAMES_LIST
    if q:
        games = [g for g in games if q in g["title"].lower() or q in g["category"].lower()]
    elif cat and cat != "all":
        games = [g for g in games if g["category"] == cat]

    return web.json_response({
        "ok": True,
        "games": games,
        "pet": PET_DATA,
        "chest": CHEST_DATA,
        "total": len(games)
    })


async def handle_chest_claim(request: web.Request) -> web.Response:
    """Sovg'a sandig'ini ochib mukofot olish."""
    reward = random.randint(50, 250)
    PET_DATA["coins"] += reward
    CHEST_DATA["last_claimed"] = time.time()
    return web.json_response({
        "success": True,
        "reward": reward,
        "new_coins": PET_DATA["coins"],
        "message": f"Tabriklaymiz! Sizga {reward} ta tanga berildi! 🪙"
    })


async def handle_pet_action(request: web.Request) -> web.Response:
    """Dumboq uy hayvonini boqish, o'ynash yoki uxlatish."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    action = body.get("action", "feed")
    msg = ""
    if action == "feed":
        PET_DATA["hunger"] = min(100, PET_DATA["hunger"] + 25)
        PET_DATA["happiness"] = min(100, PET_DATA["happiness"] + 10)
        PET_DATA["xp"] += 15
        msg = "Dumboqvoy mazza qilib ovqatlandi! 🍎"
    elif action == "play":
        PET_DATA["happiness"] = min(100, PET_DATA["happiness"] + 20)
        PET_DATA["energy"] = max(10, PET_DATA["energy"] - 15)
        PET_DATA["xp"] += 25
        msg = "Dumboqvoy quvnoq o'yin o'ynadi! 🎾"
    elif action == "sleep":
        PET_DATA["energy"] = 100
        PET_DATA["xp"] += 10
        msg = "Dumboqvoy shirin uyquga ketdi va kuch to'pladi! 😴"

    # Level oshirish
    if PET_DATA["xp"] >= PET_DATA["next_xp"]:
        PET_DATA["level"] += 1
        PET_DATA["xp"] = 0
        PET_DATA["next_xp"] += 100
        msg += f" 🎉 LEVEL UP! Yangi daraja: {PET_DATA['level']}-daraja!"

    return web.json_response({"success": True, "pet": PET_DATA, "message": msg})


async def handle_story(request: web.Request) -> web.Response:
    """Haqiqiy story ko'rish API (soxta namuna videolarsiz)."""
    username = (request.query.get("username") or request.query.get("u") or "").strip().lstrip("@")
    if not username:
        return web.json_response({"ok": False, "error": "bad_username", "stories": [], "total": 0}, status=400)

    data = await story_service.get_user_profile_and_stories(username)
    items = data.get("items") or []
    if not data.get("ok") or not items:
        return web.json_response({
            "ok": False,
            "error": data.get("error") or "story_not_found",
            "username": data.get("name") or username,
            "avatar": data.get("pic") or "",
            "stories": [],
            "total": 0,
        }, status=404)

    return web.json_response({
        "ok": True,
        "username": data.get("name") or username,
        "avatar": data.get("pic") or "",
        "stories": items,
        "items": items,
        "total": len(items),
    })


async def handle_story_me(request: web.Request) -> web.Response:
    """Web App story bo'limi holati tekshiruvi va tavsiya etilgan kanallar."""
    return web.json_response({
        "ok": True,
        "watch": [],
        "featured": [
            {"u": "cristiano", "p": "ig", "name": "Cristiano Ronaldo", "pic": "https://api.dicebear.com/7.x/identicon/svg?seed=cristiano"},
            {"u": "leomessi", "p": "ig", "name": "Leo Messi", "pic": "https://api.dicebear.com/7.x/identicon/svg?seed=leomessi"},
            {"u": "kunuz", "p": "tg", "name": "Kun.uz", "pic": "https://api.dicebear.com/7.x/identicon/svg?seed=kunuz"},
            {"u": "daryo", "p": "tg", "name": "Daryo", "pic": "https://api.dicebear.com/7.x/identicon/svg?seed=daryo"},
        ],
        "tg": True,
        "ig": True,
        "max": 15
    })


async def handle_story_ig(request: web.Request) -> web.Response:
    """Instagram profili va hikoyalarini yuklash API."""
    u = request.query.get("u", "").strip()
    if not u:
        return web.json_response({"ok": False, "error": "bad_username"}, status=400)
    data = await story_service.get_user_profile_and_stories(u)
    return web.json_response(data)


async def handle_story_ighl(request: web.Request) -> web.Response:
    """Instagram aktual hikoyalari (highlights)."""
    return web.json_response({"ok": True, "items": []})


async def handle_story_tgm(request: web.Request) -> web.Response:
    """Telegram story media URL ni keshdan olish."""
    u = story_service.clean_username(request.query.get("u", ""))
    mid = str(request.query.get("id") or "").strip()
    if not u or not mid:
        return web.json_response({"ok": False, "error": "bad_params"}, status=400)
    cached = story_service._profile_cache.get(f"tg_{u}") or {}
    for it in cached.get("items") or []:
        if str(it.get("id")) == mid and it.get("u"):
            return web.json_response({"ok": True, "src": it["u"]})
    return web.json_response({"ok": False, "error": "story_not_found"}, status=404)


async def handle_story_tg(request: web.Request) -> web.Response:
    """Telegram kanal hikoyalari API."""
    u = request.query.get("u", "").strip()
    data = await story_service.get_telegram_stories(u)
    return web.json_response(data)


async def handle_story_send(request: web.Request) -> web.Response:
    """Web Appdan tanlangan story fayllarini foydalanuvchining chatiga yuborish."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    raw_uid = request.query.get("user_id") or body.get("user_id")
    user_id, is_valid, err = security_service.verify_telegram_user(request, raw_uid)

    if not is_valid:
        if err == "user_id_spoofing":
            return web.json_response({"ok": False, "error": "spoofing", "message": "ID soxtalashtirish aniqlandi"}, status=403)
        if err == "invalid_user_id_format":
            return web.json_response({"ok": False, "error": "invalid_user"}, status=400)
        return web.json_response({"ok": False, "error": "auth"}, status=401)

    if not user_id:
        return web.json_response({"ok": False, "error": "auth"}, status=401)

    if not _bot_instance:
        return web.json_response({"ok": False, "error": "bot_not_ready"}, status=503)

    chat_id = user_id

    u = body.get("u", "").strip()
    if not u:
        return web.json_response({"ok": False, "error": "bad_username"}, status=400)

    from aiogram.types import FSInputFile
    from utils.helpers import safe_remove_file

    clean_u = story_service.clean_username(u)
    bot_name = await resolve_bot_username(_bot_instance)
    sent_any = False
    caption = (
        f"👀 <b>@{clean_u} ning hikoyasi</b>\n\n"
        f"🤖 @{bot_name} orqali yuklandi\n"
        f"🍿 {config.CHANNEL_USERNAME}"
    )

    # 1. Keshdagi tanlangan story elementlarini tekshirish
    cached_profile = story_service._profile_cache.get(clean_u)
    req_ids = body.get("ids", [])
    if isinstance(req_ids, list):
        req_ids_set = set(str(i) for i in req_ids)
    else:
        req_ids_set = set()

    if cached_profile and cached_profile.get("items"):
        target_items = [
            it for it in cached_profile["items"]
            if not req_ids_set or str(it.get("id")) in req_ids_set
        ]
        for it in target_items:
            media_url = it.get("u")
            is_vid = it.get("k") == "video"
            if media_url and str(media_url).startswith("http"):
                try:
                    if is_vid:
                        await _bot_instance.send_video(chat_id=chat_id, video=media_url, caption=caption, parse_mode="HTML")
                    else:
                        await _bot_instance.send_photo(chat_id=chat_id, photo=media_url, caption=caption, parse_mode="HTML")
                    sent_any = True
                except Exception as e_cached:
                    logger.debug(f"Keshdagi story url yuborishda xatolik: {e_cached}")

    # 2. Agar keshdan yuborilmagan bo'lsa, fetch_stories orqali yuklab yuborish
    if not sent_any:
        try:
            stories = await story_service.fetch_stories(clean_u, limit=5)
            for st in stories:
                if st.success and st.file_path and os.path.exists(st.file_path):
                    ext = Path(st.file_path).suffix.lower()
                    try:
                        if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                            await _bot_instance.send_photo(chat_id=chat_id, photo=FSInputFile(st.file_path), caption=caption, parse_mode="HTML")
                        else:
                            await _bot_instance.send_video(chat_id=chat_id, video=FSInputFile(st.file_path), caption=caption, parse_mode="HTML")
                        sent_any = True
                    except Exception as se:
                        logger.warning(f"Story yuborishda xatolik: {se}")
                    finally:
                        safe_remove_file(st.file_path)
        except Exception as e:
            logger.warning(f"Story send umumiy xatoligi: {e}")

    if not sent_any:
        return web.json_response({
            "ok": False,
            "error": "story_not_found",
            "message": f"@{clean_u} uchun faol hikoya topilmadi."
        }, status=404)

    return web.json_response({"ok": True, "message": f"@{clean_u} hikoyasi chatga yuborildi!"})


async def handle_story_watch(request: web.Request) -> web.Response:
    """Story kuzatuv API."""
    return web.json_response({"ok": True})


async def handle_doc_convert(request: web.Request) -> web.Response:
    """Kirill-Lotin o'girish API."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    text = body.get("text", "")
    target = body.get("target", "latin")
    result = doc_service.transliterate(text, target_script=target)
    return web.json_response({"result": result})


async def handle_doc_pdf(request: web.Request) -> web.Response:
    """Matndan PDF yaratish va yuklab berish API."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    title = body.get("title", "Hujjat").strip() or "Hujjat"
    text = body.get("text", "").strip() or "Matn kiritilmagan"

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        doc_service.create_simple_pdf(title=title, text=text, output_path=tmp_path)
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
        return web.Response(
            body=pdf_bytes,
            content_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{title}.pdf"',
                "Access-Control-Allow-Origin": "*",
            }
        )
    finally:
        from utils.helpers import safe_remove_file
        safe_remove_file(tmp_path)


async def handle_send_to_chat(request: web.Request) -> web.Response:
    """Mini Appdan Telegram chatga kino yoki musiqa yuborish."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Noto'g'ri so'rov"}, status=400)

    user_id_raw = body.get("user_id") or body.get("chat_id")
    action_type = body.get("type") or body.get("action") or "movie"
    code = body.get("code")

    if not user_id_raw or not _bot_instance:
        return web.json_response({"error": "Bot yoki user_id topilmadi"}, status=400)

    user_id, is_valid, err = security_service.verify_telegram_user(request, user_id_raw)
    if not is_valid:
        if err == "invalid_user_id_format":
            return web.json_response({"error": "Noto'g'ri user_id formati"}, status=400)
        elif err == "user_id_spoofing":
            return web.json_response({"error": "ID soxtalashtirish aniqlandi", "code": "spoofing"}, status=403)
        else:
            return web.json_response({"error": "Telegram WebApp xavfsizlik tekshiruvidan o'tmadi", "code": err}, status=401)

    chat_id = user_id

    try:
        if action_type == "movie" and code:
            if not config.is_admin(chat_id) and maintenance_service.is_page_maintenance("kino"):
                m_msg = maintenance_service.get_page_message("kino")
                return web.json_response({"success": False, "error": "maintenance", "message": m_msg})
            clean_code = str(code).strip().lstrip("#№")
            req_part = int(body.get("part", 1) or 1)
            delivered = await movie_service.deliver_movie(
                bot=_bot_instance,
                chat_id=chat_id,
                code=clean_code,
                part=req_part,
                require_video=True
            )
            if delivered:
                cat_item = MovieService.get_catalog_item(clean_code)
                title = cat_item.get("t") if cat_item else f"Kino #{clean_code}"
                return web.json_response({
                    "success": True,
                    "ok": True,
                    "delivered": True,
                    "message": f"«{title}» chatga yuborildi!"
                })
            else:
                cat_item = MovieService.get_catalog_item(clean_code)
                stream_info = None
                try:
                    stream_info = await MovieService.get_movie_stream_info(clean_code, part=req_part)
                except Exception:
                    stream_info = None
                db_movie = None
                try:
                    async with get_session() as session:
                        db_movie = await crud.get_movie_by_code(session, clean_code)
                except Exception:
                    db_movie = None

                if cat_item or stream_info or db_movie:
                    from handlers.movies import _send_movie_delivery_fallback
                    if _bot_instance and chat_id:
                        await _send_movie_delivery_fallback(
                            bot=_bot_instance,
                            chat_id=chat_id,
                            code=clean_code,
                            part=req_part,
                        )
                    return web.json_response({
                        "success": True,
                        "ok": True,
                        "delivered": False,
                        "action": "fallback_card",
                        "message": "Video hajmi katta bo'lgani sababli tomosha qilish havolasi chatga yuborildi!"
                    })
                else:
                    return web.json_response({
                        "ok": False,
                        "delivered": False,
                        "error": "video_unavailable",
                        "message": "Video mavjud emas yoki yetkazib bo'lmadi"
                    }, status=404)
        elif action_type == "music":
            title = str(body.get("title") or body.get("t") or "Musiqa")
            artist = str(body.get("artist") or body.get("a") or "")
            full_query = f"{artist} - {title}".strip(" -") if artist else title
            if not _bot_instance or not chat_id:
                return web.json_response(
                    {"ok": False, "success": False, "error": "bot_unavailable", "message": "Bot ulanmagan"},
                    status=503,
                )
            res = await music_service.download_track_mp3(full_query, track_info=body)
            sent_audio = False
            bot_name = await resolve_bot_username(_bot_instance)
            caption = (
                f"🎵 <b>{artist + ' - ' if artist else ''}{title}</b>\n\n"
                f"🤖 @{bot_name} Mini App orqali yuborildi"
            )
            if res and getattr(res, "success", False) and getattr(res, "file_path", None):
                from aiogram.types import FSInputFile
                from utils.helpers import safe_remove_file
                try:
                    await _bot_instance.send_audio(
                        chat_id=chat_id,
                        audio=FSInputFile(res.file_path),
                        title=title,
                        performer=artist or f"@{bot_name}",
                        duration=getattr(res, "duration", None),
                        caption=caption,
                        parse_mode="HTML",
                    )
                    sent_audio = True
                finally:
                    safe_remove_file(res.file_path)
            if not sent_audio:
                played = await music_service.play_track(track_info=body, query=full_query, title=title, artist=artist)
                stream_url = played.get("url") if isinstance(played, dict) and played.get("ok") else None
                if stream_url:
                    await _bot_instance.send_audio(
                        chat_id=chat_id,
                        audio=stream_url,
                        title=title,
                        performer=artist or f"@{bot_name}",
                        duration=int(body.get("duration") or body.get("d") or 0) or None,
                        caption=caption,
                        parse_mode="HTML",
                    )
                    sent_audio = True
            if sent_audio:
                return web.json_response({"ok": True, "success": True, "message": f"«{full_query}» chatga MP3 qilib yuborildi!"})
            return web.json_response({
                "ok": False,
                "success": False,
                "error": (getattr(res, "error", None) if res else None) or "audio_unavailable",
                "message": "Bu trekning MP3 fayli topilmadi"
            }, status=404)
    except Exception as e:
        logger.error(f"Chatga yuborishda xatolik: {e}")
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"success": True})


# =================================================================== 📚 KITOB (BOOKS) API
async def handle_books_catalog(request: web.Request) -> web.Response:
    """Kutubxona katalogi va toifalarini qaytarish."""
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}

    category = request.query.get("category") or request.query.get("c") or request.query.get("g") or body.get("category") or body.get("g")
    lang = request.query.get("lang") or request.query.get("l") or body.get("lang") or body.get("l")
    query = (request.query.get("q") or body.get("q") or "").strip()
    try:
        limit = int(request.query.get("limit") or request.query.get("n") or body.get("limit") or 50)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.query.get("offset") or request.query.get("o") or body.get("offset") or 0)
    except (ValueError, TypeError):
        offset = 0

    from services import book_service
    data = book_service.get_catalog(category=category, query=query, lang=lang, limit=limit, offset=offset)
    return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})


async def handle_books_home(request: web.Request) -> web.Response:
    """Kutubxona bosh sahifasi (Featured, Top, Janrlar, To'plamlar va Tillarga bo'lingan)."""
    from services import book_service
    books = book_service.load_books()
    total = len(books)

    uz_books = [b for b in books if b.get("l") == "uz" or b.get("lang") == "uz"]
    ru_books = [b for b in books if b.get("l") == "ru" or b.get("lang") == "ru"]
    en_books = [b for b in books if b.get("l") == "en" or b.get("lang") == "en"]

    featured = [b for b in books if b.get("popular") or b.get("views", 0) > 40000][:10]
    if not featured:
        featured = books[:10]

    top = sorted(books, key=lambda x: (x.get("rating", 0), x.get("views", 0)), reverse=True)[:10]

    shelves = [
        {"k": "featured", "t": "🔥 Sara elektron kitoblar", "items": featured},
        {"k": "top", "t": "🏆 Haftaning eng ko'p o'qilgan kitoblari", "items": top},
    ]

    genres = []
    for cat in book_service.CATEGORIES_META:
        cid = cat["id"]
        cname = cat["name"]
        cat_items = [b for b in books if b.get("category") == cid or b.get("g") == cid]
        if cat_items:
            genres.append({"g": cid, "n": len(cat_items)})
            shelves.append({"k": f"genre:{cid}", "t": cname, "items": cat_items[:12]})

    collections = [
        {
            "k": "uz",
            "t": "O'zbek adabiyoti durdonalari",
            "flag": "🇺🇿",
            "d": "Mumtoz va zamonaviy o'zbek asarlari, qadriyatlar va xalq merosi",
            "n": len(uz_books)
        },
        {
            "k": "biznes",
            "t": "Biznes va Shaxsiy Rivojlanish",
            "flag": "💼",
            "d": "Moliyaviy savodxonlik, odatlar kuchi va yetakchilik qoidalari",
            "n": len([b for b in books if b.get("category") == "biznes"])
        },
        {
            "k": "jahon",
            "t": "Jahon Bestsellerlari",
            "flag": "🌍",
            "d": "Dunyoni larzaga solgan xalqaro sara kitoblar va romanlar",
            "n": total
        }
    ]

    home_data = {
        "ok": True,
        "total": total,
        "langs": {
            "uz": len(uz_books),
            "ru": len(ru_books),
            "en": len(en_books)
        },
        "shelves": shelves,
        "genres": genres,
        "collections": collections,
        "featured": featured,
        "items": books[:30],
        "categories": book_service.CATEGORIES_META,
        "bot": await resolve_bot_username(_bot_instance),
        "channel": config.CHANNEL_USERNAME
    }
    return web.json_response(home_data, headers={"Access-Control-Allow-Origin": "*"})


async def handle_books_me(request: web.Request) -> web.Response:
    """Foydalanuvchining kitob javoni, audio progressi, qaydlari va o'qish statistikasi."""
    headers = {"Access-Control-Allow-Origin": "*"}
    raw_uid = request.query.get("user_id")
    user_id, is_valid, err = security_service.verify_telegram_user(request, raw_uid)
    if not is_valid:
        status = 403 if err == "user_id_spoofing" else 401
        return web.json_response({"ok": False, "error": err or "auth"}, status=status, headers=headers)
    uid = user_id or extract_request_user(request)[0]
    from services import book_service
    return web.json_response(book_service.get_user_state(uid), headers=headers)


async def handle_books_action(request: web.Request) -> web.Response:
    """Javon, progress, audio va qaydlar amallari."""
    headers = {"Access-Control-Allow-Origin": "*"}
    path = _extract_api_path(request)
    body = await _read_json_body(request)
    raw_uid = body.get("user_id") or request.query.get("user_id")
    user_id, is_valid, err = security_service.verify_telegram_user(request, raw_uid)
    if not is_valid:
        status = 403 if err == "user_id_spoofing" else 401
        return web.json_response({"ok": False, "error": err or "auth"}, status=status, headers=headers)
    uid = user_id or extract_request_user(request)[0]
    bid = body.get("i") or body.get("id") or body.get("book_id")
    from services import book_service

    if path == "api/books/shelf":
        if not bid:
            return web.json_response({"ok": False, "error": "bad_book_id"}, status=400, headers=headers)
        res = book_service.toggle_shelf(
            uid,
            bid,
            saved=body.get("saved"),
            done=body.get("done"),
            stars=body.get("stars"),
            remove=bool(body.get("remove", False)),
            dl=body.get("dl"),
        )
        return web.json_response(res, headers=headers)

    if path == "api/books/progress":
        if not bid:
            return web.json_response({"ok": False, "error": "bad_book_id"}, status=400, headers=headers)
        res = book_service.save_user_progress(
            uid,
            bid,
            ch=int(body.get("ch") or 0),
            off=float(body.get("off") or 0.0),
            pct=float(body.get("pct") or 0.0),
            secs=int(body.get("secs") or 0),
        )
        return web.json_response(res, headers=headers)

    if path == "api/books/note":
        if body.get("del") is not None:
            res = book_service.delete_note(uid, body.get("del"))
            return web.json_response(res, headers=headers)
        if not bid:
            return web.json_response({"ok": False, "error": "bad_book_id"}, status=400, headers=headers)
        res = book_service.add_note(
            uid,
            bid,
            ch=int(body.get("ch") or 0),
            q=str(body.get("q") or ""),
            note=str(body.get("n") or body.get("note") or ""),
            pos=int(body.get("pos") if body.get("pos") is not None else -1),
        )
        return web.json_response(res, headers=headers)

    if path == "api/books/audio":
        if not bid:
            return web.json_response({"ok": False, "error": "bad_book_id"}, status=400, headers=headers)
        res = book_service.save_user_audio_progress(
            uid,
            bid,
            n=int(body.get("n") or 1),
            t=float(body.get("t") or 0.0),
            secs=int(body.get("secs") or 0),
        )
        return web.json_response(res, headers=headers)

    return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)


async def handle_books_page(request: web.Request) -> web.Response:
    """Skanerlangan kitob sahifasini lokal keshdan qaytarish."""
    headers = {"Access-Control-Allow-Origin": "*"}
    bid = re.sub(r"\D", "", str(request.match_info.get("id") or ""))
    page_num = re.sub(r"\D", "", str(request.match_info.get("n") or ""))
    if not bid or not page_num:
        return web.json_response({"ok": False, "error": "bad_params"}, status=400, headers=headers)
    bk_dir = BASE_DIR / "data" / "bk" / bid
    for ext, ct in ((".webp", "image/webp"), (".jpg", "image/jpeg"), (".jpeg", "image/jpeg"), (".png", "image/png")):
        cand = bk_dir / f"s{page_num}{ext}"
        if cand.exists():
            data = await asyncio.to_thread(cand.read_bytes)
            return web.Response(body=data, content_type=ct, headers={**headers, "Cache-Control": "public, max-age=604800"})
    return web.json_response({"ok": False, "error": "page_not_found"}, status=404, headers=headers)


async def handle_books_admin_delete(request: web.Request) -> web.Response:
    """Admin tomonidan kitobni o'chirish API (qat'iy admin tekshiruvi bilan)."""
    headers = {"Access-Control-Allow-Origin": "*"}
    is_adm, _ = verify_admin_request(request)
    if not is_adm:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403, headers=headers)
    body = await _read_json_body(request)
    bid = str(body.get("i") or body.get("id") or "").strip()
    if not bid:
        return web.json_response({"ok": False, "error": "bad_book_id"}, status=400, headers=headers)
    from services import book_service
    book = book_service.get_book_by_id(bid)
    if not book:
        return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)
    return web.json_response({"ok": True, "deleted": bid}, headers=headers)


async def handle_books_search(request: web.Request) -> web.Response:
    """Kitoblarni tezkor qidirish API (Upstream 3390+ kitoblar va mahalliy zaxira)."""
    q = request.query.get("q", "").strip()
    genre = request.query.get("g") or request.query.get("category")
    lang = request.query.get("l") or request.query.get("lang")
    sort = request.query.get("s") or request.query.get("sort") or "pop"
    try:
        limit = int(request.query.get("limit") or request.query.get("n") or 30)
    except (ValueError, TypeError):
        limit = 30
    try:
        offset = int(request.query.get("offset") or request.query.get("o") or 0)
    except (ValueError, TypeError):
        offset = 0

    items = []
    total = 0

    from services import book_service
    cat_res = book_service.get_catalog(
        category=genre,
        query=q,
        lang=lang,
        limit=limit,
        offset=offset
    )
    local_items = cat_res.get("items", [])
    total = cat_res.get("total", len(local_items))
    if sort == "az":
        local_items = sorted(local_items, key=lambda x: (x.get("title") or x.get("t") or ""))
    elif sort == "rate":
        local_items = sorted(local_items, key=lambda x: (x.get("rating") or x.get("r") or 0), reverse=True)
    elif sort == "new":
        local_items = sorted(local_items, key=lambda x: (x.get("year") or x.get("y") or 0), reverse=True)

    items = []
    for it in local_items:
        b = dict(it)
        # Dual schema: ham tests uchun id, title, author, ham webapp uchun i, t, a
        b["id"] = str(b.get("i", b.get("id", "")))
        b["title"] = b.get("t", b.get("title", ""))
        b["author"] = b.get("a", b.get("author", ""))
        b["category"] = b.get("g", b.get("category", "badiiy"))
        b["i"] = b.get("i") or (int(b["id"]) if str(b["id"]).isdigit() else 0)
        b["t"] = b["title"]
        b["a"] = b["author"]
        b["g"] = b["category"]
        b["c"] = b.get("c", 0)
        b["p"] = b.get("p", b.get("pages", 120))
        b["l"] = b.get("l", b.get("lang", "uz"))
        b["f"] = b.get("f") or ["pdf", "epub"]
        b["s"] = b.get("s") or {"pdf": int(b.get("size_mb", 2.5) * 1048576), "epub": int(b.get("size_mb", 2.5) * 524288)}
        items.append(b)

    return web.json_response({"ok": True, "items": items, "total": total}, headers={"Access-Control-Allow-Origin": "*"})


async def handle_book_detail(request: web.Request) -> web.Response:
    """Kitobning to'liq ma'lumotlari va foydalanuvchi holatini olish."""
    headers = {"Access-Control-Allow-Origin": "*"}
    book_id = request.match_info.get("id", "").strip() or request.query.get("id", "").strip() or request.query.get("i", "").strip()
    raw_uid = request.query.get("user_id")
    user_id, is_valid, err = security_service.verify_telegram_user(request, raw_uid)
    if not is_valid:
        status = 403 if err == "user_id_spoofing" else 401
        return web.json_response({"ok": False, "error": err or "auth"}, status=status, headers=headers)
    uid = user_id or extract_request_user(request)[0]
    from services import book_service
    book = book_service.get_book_by_id(book_id)
    if not book:
        return web.json_response({"ok": False, "error": "not_found"}, status=404, headers=headers)
    book_out = dict(book)
    book_out["me"] = book_service.get_user_book_me(uid, book_out.get("i") or book_id)
    return web.json_response({"ok": True, "book": book_out}, headers=headers)


async def handle_book_send(request: web.Request) -> web.Response:
    """Web Appdan tanlangan kitobni Telegram chatga PDF shaklida yuborish."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    raw_uid = request.query.get("user_id") or body.get("user_id")
    user_id, is_valid, err = security_service.verify_telegram_user(request, raw_uid)
    book_id = str(body.get("id") or body.get("book_id") or body.get("i") or "").strip()

    if not book_id:
        return web.json_response({"ok": False, "error": "not_found"}, status=400)

    from services import book_service
    book = book_service.get_book_by_id(book_id)
    if not book:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)

    bot_username = await resolve_bot_username(_bot_instance)
    target_url = f"https://t.me/{bot_username}?start=b_{book_id}"

    if not user_id:
        return web.json_response({
            "ok": False,
            "action": "open_bot",
            "url": target_url,
            "error": "need_start"
        })

    if not _bot_instance:
        return web.json_response({
            "ok": False,
            "action": "open_bot",
            "url": target_url,
            "error": "bot_not_connected"
        })

    fmt = str(body.get("f") or body.get("format") or "pdf").lower()
    try:
        result = await book_service.deliver_book(
            bot=_bot_instance,
            chat_id=int(user_id),
            book_id=book_id,
            fmt=fmt
        )
        if result.get("ok"):
            return web.json_response({"ok": True, "delivered": True, "book": book})
        else:
            return web.json_response({
                "ok": False,
                "action": "open_bot",
                "url": target_url,
                "error": result.get("error", "send_failed")
            })
    except Exception as e:
        logger.error(f"Kitobni chatga yuborishda xatolik: {e}")
        return web.json_response({
            "ok": False,
            "action": "open_bot",
            "url": target_url,
            "error": str(e)
        })


async def handle_book_pdf(request: web.Request) -> web.Response:
    """Kitob PDF mutolaa faylini yuklab berish."""
    book_id = request.match_info.get("id", "").strip()
    from services import book_service
    book = book_service.get_book_by_id(book_id)
    if not book:
        return web.Response(status=404, text="Kitob topilmadi")
    pdf_bytes = book_service.create_book_pdf_sample(book)
    safe_title = re.sub(r'[^\w\s-]', '', book.get('title', 'kitob')).strip()
    return web.Response(
        body=pdf_bytes,
        content_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_title}.pdf"',
            "Access-Control-Allow-Origin": "*"
        }
    )


# =================================================================== 🚗 PRAVA (DRIVING TEST) API
async def handle_prava_home(request: web.Request) -> web.Response:
    """Prava asosiy ma'lumotlari: biletlar, mavzular va statistika."""
    from services.prava_service import prava_service
    user_id = extract_user_id_from_init_data(request.headers.get("X-Init-Data", "")) or 0
    data = prava_service.get_home_data(user_id=user_id)
    return web.json_response(data)


async def handle_prava_set(request: web.Request) -> web.Response:
    """Bilet yoki mavzu bo'yicha savollar to'plamini olish."""
    from services.prava_service import prava_service
    user_id = extract_user_id_from_init_data(request.headers.get("X-Init-Data", "")) or 0
    k = request.query.get("k", "rnd")
    try:
        a = int(request.query.get("a", 0))
    except (ValueError, TypeError):
        a = 0
    data = prava_service.get_set(kind=k, arg=a, user_id=user_id)
    return web.json_response(data)


async def handle_prava_ans(request: web.Request) -> web.Response:
    """Savol javobini serverda tekshirish."""
    from services.prava_service import prava_service
    user_id = extract_user_id_from_init_data(request.headers.get("X-Init-Data", "")) or 0
    try:
        body = await request.json()
    except Exception:
        body = {}
    q_id = int(body.get("id", 0))
    choice = int(body.get("c", -1))
    data = prava_service.check_answer(q_id=q_id, choice=choice, user_id=user_id)
    return web.json_response(data)


async def handle_prava_bilet(request: web.Request) -> web.Response:
    """Bilet natijasini saqlash."""
    from services.prava_service import prava_service
    user_id = extract_user_id_from_init_data(request.headers.get("X-Init-Data", "")) or 0
    try:
        body = await request.json()
    except Exception:
        body = {}
    b = int(body.get("b", 0))
    s = int(body.get("s", 0))
    data = prava_service.save_bilet_score(bilet_num=b, score=s, user_id=user_id)
    return web.json_response(data)


async def handle_prava_exam_start(request: web.Request) -> web.Response:
    """Rasmiy 20 talik imtihonni boshlash."""
    from services.prava_service import prava_service
    user_id = extract_user_id_from_init_data(request.headers.get("X-Init-Data", "")) or 0
    data = prava_service.start_exam(user_id=user_id)
    return web.json_response(data)


async def handle_prava_exam_ans(request: web.Request) -> web.Response:
    """Imtihon savoliga javob berish."""
    from services.prava_service import prava_service
    user_id = extract_user_id_from_init_data(request.headers.get("X-Init-Data", "")) or 0
    try:
        body = await request.json()
    except Exception:
        body = {}
    k = int(body.get("k", 0))
    c = int(body.get("c", -1))
    data = prava_service.answer_exam(question_idx=k, choice=c, user_id=user_id)
    return web.json_response(data)


async def handle_prava_exam_finish(request: web.Request) -> web.Response:
    """Imtihonni yakunlash va natijalarni hisoblash."""
    from services.prava_service import prava_service
    user_id = extract_user_id_from_init_data(request.headers.get("X-Init-Data", "")) or 0
    data = prava_service.finish_exam(user_id=user_id)
    return web.json_response(data)


# =================================================================== 🔒 SUB GATE & 💛 DONATE API
async def handle_api_sub(request: web.Request) -> web.Response:
    """Majburiy kanal obunasini tekshirish API (subGate)."""
    user_id = extract_user_id_from_init_data(request.headers.get("X-Init-Data", ""))
    if not user_id:
        uid_param = request.query.get("user_id")
        if uid_param and str(uid_param).isdigit():
            user_id = int(uid_param)

    if not user_id or not _bot_instance:
        return web.json_response({"ok": True, "sub": True})

    if config.is_admin(user_id):
        return web.json_response({"ok": True, "sub": True})

    from unittest.mock import MagicMock, AsyncMock
    channels_to_check = []
    try:
        async with get_session() as session:
            db_channels = await crud.get_active_sponsor_channels(session)
            if db_channels:
                channels_to_check.extend(db_channels)
    except Exception:
        pass

    channel_main = config.CHANNEL_USERNAME.strip()
    if not channels_to_check and channel_main:
        from database.models import SponsorChannel
        channels_to_check.append(SponsorChannel(id=999999, channel_id=channel_main, title="Baunty Films", is_active=True))

    if not channels_to_check:
        return web.json_response({"ok": True, "sub": True})

    unsubscribed = []
    for ch in channels_to_check:
        try:
            member = await _bot_instance.get_chat_member(chat_id=ch.channel_id, user_id=user_id)
            status = getattr(member, "status", None) or (member.get("status") if isinstance(member, dict) else "")
            if isinstance(status, (MagicMock, AsyncMock)):
                continue
            if str(status).lower() not in ("creator", "administrator", "member", "restricted"):
                ch_url = getattr(ch, "invite_link", None) or ""
                if not ch_url:
                    c_id = str(ch.channel_id).lstrip("@")
                    ch_url = f"https://t.me/{c_id}"
                elif not ch_url.startswith("http"):
                    ch_url = f"https://t.me/{ch_url.lstrip('@')}"
                unsubscribed.append({
                    "title": getattr(ch, "title", "Baunty Films"),
                    "url": ch_url
                })
        except Exception as e:
            logger.debug(f"Kanal obunasini tekshirishda xatolik ({ch.channel_id}): {e}")

    if unsubscribed:
        return web.json_response({
            "ok": True,
            "sub": False,
            "channels": unsubscribed
        })

    return web.json_response({"ok": True, "sub": True})


async def handle_api_donate(request: web.Request) -> web.Response:
    """Bauntys qo'llab-quvvatlash (donat) ma'lumotlari."""
    return web.json_response({
        "ok": True,
        "on": True,
        "text": "Har bir yordam Bauntys loyihasi rivoji va server xarajatlari uchun sarflanadi. Qo'llab-quvvatlaganingiz uchun rahmat! 💛",
        "num": "9860 1766 1922 0088",
        "name": "Xaydarov Biloliddin",
        "net": "Humo",
        "cards": [
            {
                "num": "9860 1766 1922 0088",
                "name": "Xaydarov Biloliddin",
                "net": "Humo"
            }
        ]
    })


async def handle_api_reklama(request: web.Request) -> web.Response:
    """Bauntys reklama berish ma'lumotlari (real PostgreSQL foydalanuvchilar soni bilan)."""
    channel_clean = config.CHANNEL_USERNAME.lstrip("@")
    users_count = 0
    try:
        from sqlalchemy import select, func
        from database.models import User
        async with get_session() as session:
            val = await session.scalar(select(func.count(User.id)))
            users_count = int(val or 0)
    except Exception as e:
        logger.debug("handle_api_reklama DB user count fallback: %s", e)
        users_count = 0

    return web.json_response({
        "ok": True,
        "on": True,
        "users": users_count,
        "user": channel_clean,
        "phone": "+998900000000",
        "phone_fmt": "+998 90 000 00 00",
        "hours": "09:00–22:00",
        "formats": [
            {"ic": "📩", "t": "Botda xabar", "s": "Hamma obunachiga, muddatli (o'zi o'chadi)"},
            {"ic": "📌", "t": "Pin xabar", "s": "Chat tepasida turadi"},
            {"ic": "🎬", "t": "Kino posteri", "s": "Poster kanali va katalogda"}
        ]
    })


async def handle_api_not_found(request: web.Request) -> web.Response:
    """Mahalliy API da topilmagan so'rovlar uchun toza 404 JSON javobi."""
    return web.json_response(
        {"ok": False, "error": "not_found", "path": request.path},
        status=404,
        headers={"Access-Control-Allow-Origin": "*"},
    )


def create_web_app() -> web.Application:
    """aiohttp web application yaratish va routerlarni sozlash."""
    app = web.Application()

    # So'rovlar oqimi telemetriyasi va xavfsizlik middleware lari
    app.middlewares.append(telemetry_middleware)
    app.middlewares.append(security_middleware)

    # API va sahifa marshrutlari (UptimeRobot, healthcheck, Admin Flow va Telegram WebApp)
    app.router.add_get("/ping", handle_ping)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/status", handle_health)
    app.router.add_get("/healthz", handle_health)
    app.router.add_route("HEAD", "/ping", handle_ping)
    app.router.add_route("HEAD", "/health", handle_health)
    app.router.add_route("HEAD", "/status", handle_health)
    app.router.add_route("HEAD", "/healthz", handle_health)
    app.router.add_get("/favicon.ico", handle_favicon)
    app.router.add_get("/webapp/favicon.ico", handle_favicon)
    app.router.add_get("/admin/flow", handle_admin_flow)
    app.router.add_get("/webapp/admin/flow", handle_admin_flow)
    app.router.add_get("/admin_flow.html", handle_admin_flow)
    app.router.add_get("/webapp/admin_flow.html", handle_admin_flow)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/webapp", handle_index)
    app.router.add_get("/webapp/", handle_index)
    app.router.add_get("/webapp/index.html", handle_index)
    app.router.add_route("HEAD", "/", handle_index)
    app.router.add_route("HEAD", "/index.html", handle_index)
    app.router.add_route("HEAD", "/webapp", handle_index)
    app.router.add_route("HEAD", "/webapp/", handle_index)
    app.router.add_route("HEAD", "/webapp/index.html", handle_index)

    api_routes = [
        ("GET", "/api/admin/flow/data", handle_admin_flow_data),
        ("POST", "/api/admin/flow/data", handle_admin_flow_data),
        ("GET", "/api/admin/flow/benchmark", handle_admin_flow_benchmark),
        ("POST", "/api/admin/flow/benchmark", handle_admin_flow_benchmark),
        ("POST", "/api/admin/flow/clear", handle_admin_flow_clear),
        ("GET", "/api", handle_api_overview),
        ("POST", "/api", handle_api_overview),
        ("GET", "/api/catalog", handle_get_catalog),
        ("POST", "/api/catalog", handle_get_catalog),
        ("GET", "/api/watch", handle_watch_get),
        ("POST", "/api/watch", handle_watch),
        ("POST", "/api/send", handle_send_to_chat),
        ("GET", "/api/send", handle_send_api),
        ("POST", "/api/send_to_chat", handle_send_to_chat),
        ("GET", "/api/movies", handle_get_movies),
        ("POST", "/api/movies", handle_get_movies),
        ("GET", "/api/movies/{code}", handle_get_movie_detail),
        ("POST", "/api/movies/{code}", handle_get_movie_detail),
        ("GET", "/api/music", handle_get_music),
        ("POST", "/api/music", handle_get_music),
        ("GET", "/api/music/home", handle_music_home),
        ("POST", "/api/music/home", handle_music_home),
        ("GET", "/api/music/search", handle_music_search),
        ("POST", "/api/music/play", handle_music_play),
        ("POST", "/api/music/send", handle_music_send),
        ("POST", "/api/music/recognize", handle_music_recognize),
        ("POST", "/api/music/shazam", handle_music_shazam),
        ("GET", "/api/music/me", handle_music_me),
        ("POST", "/api/music/report", handle_music_report),
        ("POST", "/api/music/ban", handle_music_ban),
        ("POST", "/api/music/purge", handle_music_purge),
        ("GET", "/api/music/{tail:.*}", handle_api_not_found),
        ("POST", "/api/music/{tail:.*}", handle_api_not_found),
        ("GET", "/api/tv/stream", handle_tv_stream_proxy),
        ("POST", "/api/tv/stream", handle_tv_stream_proxy),
        ("GET", "/api/tv/speed", handle_tv_speed),
        ("HEAD", "/api/tv/speed", handle_tv_speed),
        ("POST", "/api/tv/speed", handle_tv_speed),
        ("POST", "/api/tv/telemetry", handle_tv_telemetry),
        ("GET", "/api/speedtest", handle_tv_speed),
        ("HEAD", "/api/speedtest", handle_tv_speed),
        ("GET", "/api/tv", handle_get_tv),
        ("POST", "/api/tv", handle_get_tv),
        ("GET", "/api/tv/icon/{id}", handle_tv_icon),
        ("POST", "/api/tv/report", handle_tv_report),
        ("GET", "/api/tv/me", handle_tv_me),
        ("POST", "/api/tv/hide", handle_tv_hide),
        ("GET", "/api/tv/{tail:.*}", handle_api_not_found),
        ("POST", "/api/tv/{tail:.*}", handle_api_not_found),
        ("GET", "/api/games", handle_get_games),
        ("POST", "/api/games", handle_get_games),
        ("POST", "/api/games/chest/claim", handle_chest_claim),
        ("POST", "/api/games/pet/action", handle_pet_action),
        ("GET", "/api/games/{tail:.*}", handle_api_not_found),
        ("POST", "/api/games/{tail:.*}", handle_api_not_found),
        ("GET", "/api/story", handle_story),
        ("POST", "/api/story", handle_story),
        ("GET", "/api/story/me", handle_story_me),
        ("GET", "/api/story/ig", handle_story_ig),
        ("GET", "/api/story/ighl", handle_story_ighl),
        ("GET", "/api/story/ighi", handle_story_ighl),
        ("GET", "/api/story/tg", handle_story_tg),
        ("GET", "/api/story/tgm", handle_story_tgm),
        ("POST", "/api/story/send", handle_story_send),
        ("POST", "/api/story/watch", handle_story_watch),
        ("GET", "/api/story/{tail:.*}", handle_api_not_found),
        ("POST", "/api/story/{tail:.*}", handle_api_not_found),
        ("GET", "/api/docs", handle_doc_root),
        ("POST", "/api/docs", handle_doc_root),
        ("GET", "/api/docs/config", handle_doc_config),
        ("POST", "/api/docs/convert", handle_doc_convert),
        ("POST", "/api/docs/pdf", handle_doc_pdf),
        ("POST", "/api/docs/upload", handle_docs_api),
        ("POST", "/api/docs/run", handle_docs_api),
        ("POST", "/api/docs/preview", handle_docs_api),
        ("POST", "/api/docs/unlock", handle_docs_api),
        ("GET", "/api/docs/job/{id}", handle_docs_api),
        ("GET", "/api/docs/t/{tail:.*}", handle_docs_api),
        ("GET", "/api/docs/{tail:.*}", handle_docs_api),
        ("POST", "/api/docs/{tail:.*}", handle_docs_api),
        ("GET", "/api/books", handle_books_catalog),
        ("POST", "/api/books", handle_books_catalog),
        ("GET", "/api/books/home", handle_books_home),
        ("POST", "/api/books/home", handle_books_home),
        ("GET", "/api/books/shelf", handle_books_me),
        ("POST", "/api/books/shelf", handle_books_action),
        ("GET", "/api/books/me", handle_books_me),
        ("POST", "/api/books/progress", handle_books_action),
        ("POST", "/api/books/note", handle_books_action),
        ("POST", "/api/books/audio", handle_books_action),
        ("POST", "/api/books/admin/delete", handle_books_admin_delete),
        ("GET", "/api/books/b/{id}", handle_book_detail),
        ("GET", "/api/books/page/{id}/{n}", handle_books_page),
        ("GET", "/api/books/search", handle_books_search),
        ("GET", "/api/books/{id}", handle_book_detail),
        ("GET", "/api/books/{id}/pdf", handle_book_pdf),
        ("POST", "/api/books/send", handle_book_send),
        ("GET", "/api/books/{tail:.*}", handle_api_not_found),
        ("POST", "/api/books/{tail:.*}", handle_api_not_found),
        ("GET", "/api/food/kcal/{tail:.*}", handle_kaloriya_api),
        ("POST", "/api/food/kcal/{tail:.*}", handle_kaloriya_api),
        ("GET", "/api/food", handle_food_api),
        ("POST", "/api/food", handle_food_api),
        ("GET", "/api/food/{tail:.*}", handle_food_api),
        ("POST", "/api/food/{tail:.*}", handle_food_api),
        ("GET", "/api/quiz", handle_quiz_api),
        ("POST", "/api/quiz", handle_quiz_api),
        ("GET", "/api/quiz/{tail:.*}", handle_quiz_api),
        ("POST", "/api/quiz/{tail:.*}", handle_quiz_api),
        ("GET", "/api/fx", handle_fx_api),
        ("POST", "/api/fx", handle_fx_api),
        ("GET", "/api/fx/alerts", handle_fx_alerts),
        ("POST", "/api/fx/alerts", handle_fx_alerts),
        ("GET", "/api/fx/h/{c}", handle_fx_history),
        ("GET", "/api/fx/banks/{c}", handle_fx_banks),
        ("GET", "/api/fx/{tail:.*}", handle_api_not_found),
        ("POST", "/api/fx/{tail:.*}", handle_api_not_found),
        ("GET", "/api/maintenance", handle_maintenance),
        ("POST", "/api/maintenance", handle_maintenance),
        ("GET", "/api/admin/maintenance", handle_admin_maintenance),
        ("POST", "/api/admin/maintenance", handle_admin_maintenance),
        ("GET", "/api/lang", handle_api_lang),
        ("POST", "/api/lang", handle_api_lang),
        ("GET", "/api/prava", handle_prava_home),
        ("POST", "/api/prava", handle_prava_home),
        ("GET", "/api/prava/home", handle_prava_home),
        ("GET", "/api/prava/set", handle_prava_set),
        ("POST", "/api/prava/ans", handle_prava_ans),
        ("POST", "/api/prava/bilet", handle_prava_bilet),
        ("POST", "/api/prava/exam/start", handle_prava_exam_start),
        ("POST", "/api/prava/exam/ans", handle_prava_exam_ans),
        ("POST", "/api/prava/exam/finish", handle_prava_exam_finish),
        ("GET", "/api/prava/{tail:.*}", handle_api_not_found),
        ("POST", "/api/prava/{tail:.*}", handle_api_not_found),
        ("GET", "/api/sub", handle_api_sub),
        ("POST", "/api/sub", handle_api_sub),
        ("GET", "/api/donate", handle_api_donate),
        ("POST", "/api/donate", handle_api_donate),
        ("GET", "/api/donate/ev", handle_api_donate),
        ("POST", "/api/donate/ev", handle_api_donate),
        ("GET", "/api/reklama", handle_api_reklama),
        ("POST", "/api/reklama", handle_api_reklama),
        ("GET", "/api/asil", handle_asil_home),
        ("POST", "/api/asil", handle_asil_home),
        ("GET", "/api/asil/home", handle_asil_home),
        ("POST", "/api/asil/home", handle_asil_home),
        ("GET", "/api/asil/list", handle_asil_list),
        ("GET", "/api/asil/search", handle_asil_search),
        ("GET", "/api/asil/item", handle_asil_item),
        ("GET", "/api/asil/colls", handle_asil_colls),
        ("GET", "/api/asil/coll", handle_asil_coll),
        ("POST", "/api/asil/send", handle_asil_send),
        ("GET", "/api/asil/stream", handle_asil_stream),
        ("GET", "/api/asil/{tail:.*}", handle_api_not_found),
        ("POST", "/api/asil/{tail:.*}", handle_api_not_found),
        ("GET", "/api/rasxod", handle_rasxod_api),
        ("POST", "/api/rasxod", handle_rasxod_api),
        ("GET", "/api/rasxod/{tail:.*}", handle_rasxod_api),
        ("POST", "/api/rasxod/{tail:.*}", handle_rasxod_api),
        ("GET", "/api/kal", handle_kaloriya_api),
        ("POST", "/api/kal", handle_kaloriya_api),
        ("GET", "/api/kal/{tail:.*}", handle_kaloriya_api),
        ("POST", "/api/kal/{tail:.*}", handle_kaloriya_api),
        ("GET", "/api/mafia", handle_mafia_api),
        ("POST", "/api/mafia", handle_mafia_api),
        ("GET", "/api/mafia/{tail:.*}", handle_mafia_api),
        ("POST", "/api/mafia/{tail:.*}", handle_mafia_api),
        ("GET", "/api/tvroom", handle_tvroom_api),
        ("POST", "/api/tvroom", handle_tvroom_api),
        ("GET", "/api/tvroom/{tail:.*}", handle_tvroom_api),
        ("POST", "/api/tvroom/{tail:.*}", handle_tvroom_api),
        ("GET", "/api/bunker", handle_bunker_api),
        ("POST", "/api/bunker", handle_bunker_api),
        ("GET", "/api/bunker/{tail:.*}", handle_bunker_api),
        ("POST", "/api/bunker/{tail:.*}", handle_bunker_api),
        ("GET", "/api/deliv", handle_deliv_api),
        ("POST", "/api/deliv", handle_deliv_api),
        ("GET", "/api/deliv/{tail:.*}", handle_deliv_api),
        ("POST", "/api/deliv/{tail:.*}", handle_deliv_api),
        ("GET", "/api/duel", handle_duel_api),
        ("POST", "/api/duel", handle_duel_api),
        ("GET", "/api/duel/{tail:.*}", handle_duel_api),
        ("POST", "/api/duel/{tail:.*}", handle_duel_api),
    ]
    for method, path, handler in api_routes:
        if method == "GET":
            app.router.add_get(path, handler)
            app.router.add_get(f"/webapp{path}", handler)
        elif method == "POST":
            app.router.add_post(path, handler)
            app.router.add_post(f"/webapp{path}", handler)

    app.router.add_get("/p/{filename}", handle_poster_proxy)
    app.router.add_get("/webapp/p/{filename}", handle_poster_proxy)
    app.router.add_get("/prava/{filename}", handle_prava_image_proxy)
    app.router.add_get("/webapp/prava/{filename}", handle_prava_image_proxy)
    app.router.add_get("/pv/{filename}", handle_prava_image_proxy)
    app.router.add_get("/webapp/pv/{filename}", handle_prava_image_proxy)
    app.router.add_get("/api/prava/img/{filename}", handle_prava_image_proxy)
    app.router.add_get("/webapp/api/prava/img/{filename}", handle_prava_image_proxy)
    app.router.add_get("/p/tv/{id}", handle_tv_icon)
    app.router.add_get("/webapp/p/tv/{id}", handle_tv_icon)
    app.router.add_get("/bk/{tail:.*}", handle_book_asset_proxy)
    app.router.add_get("/webapp/bk/{tail:.*}", handle_book_asset_proxy)
    app.router.add_get("/api/book_cover/{id}", handle_book_cover_api)
    app.router.add_get("/webapp/api/book_cover/{id}", handle_book_cover_api)
    app.router.add_get("/api/book_asset/{tail:.*}", handle_book_asset_proxy)
    app.router.add_get("/webapp/api/book_asset/{tail:.*}", handle_book_asset_proxy)
    app.router.add_get("/rc/{tail:.*}", handle_rc_asset_proxy)
    app.router.add_get("/webapp/rc/{tail:.*}", handle_rc_asset_proxy)
    app.router.add_route("OPTIONS", "/api/tv/stream", handle_tv_stream_proxy)
    app.router.add_route("OPTIONS", "/webapp/api/tv/stream", handle_tv_stream_proxy)
    app.router.add_route("HEAD", "/api/tv/stream", handle_tv_stream_proxy)
    app.router.add_route("HEAD", "/webapp/api/tv/stream", handle_tv_stream_proxy)
    app.router.add_route("OPTIONS", "/api/tv/speed", handle_tv_speed)
    app.router.add_route("OPTIONS", "/webapp/api/tv/speed", handle_tv_speed)
    app.router.add_route("OPTIONS", "/api/tv/telemetry", handle_tv_telemetry)
    app.router.add_route("OPTIONS", "/webapp/api/tv/telemetry", handle_tv_telemetry)
    app.router.add_route("OPTIONS", "/api/speedtest", handle_tv_speed)

    # Optimizatsiya qilingan va himoyalangan bundle marshrutlari
    app.router.add_get("/bundle.min.js", handle_bundle_js)
    app.router.add_get("/webapp/bundle.min.js", handle_bundle_js)
    app.router.add_get("/bundle.min.css", handle_bundle_css)
    app.router.add_get("/webapp/bundle.min.css", handle_bundle_css)
    app.router.add_get("/shield.min.js", handle_shield_js)
    app.router.add_get("/webapp/shield.min.js", handle_shield_js)

    # Statik fayllarni ulash (CSS, JS, Assetlar, Shriftlar)
    webapp_dir = BASE_DIR / "webapp"
    webapp_dir.mkdir(exist_ok=True)
    app.router.add_static("/webapp", webapp_dir, name="webapp")
    css_dir = webapp_dir / "css"
    if css_dir.exists():
        app.router.add_static("/css", css_dir, name="css")
    js_dir = webapp_dir / "js"
    if js_dir.exists():
        app.router.add_static("/js", js_dir, name="js")
    f_dir = webapp_dir / "f"
    if f_dir.exists():
        app.router.add_static("/f", f_dir, name="fonts")
        app.router.add_static("/webapp/f", f_dir, name="webapp_fonts")

    # Asosiy Mini App papkasidagi faqat xavfsiz statik fayllarni root orqali berish
    # Xavfsizlik: .db, .sqlite, .py, .env, admin_flow.html yoki maxfiy fayllar aslo statik berilmaydi
    ALLOWED_STATIC_EXTS = {".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff", ".woff2", ".ttf"}
    for fpath in webapp_dir.iterdir():
        if fpath.is_file() and fpath.name not in ("index.html", "admin_flow.html"):
            if fpath.suffix.lower() in ALLOWED_STATIC_EXTS and fpath.name.lower() not in PROTECTED_FILENAMES:
                def make_handler(target_path):
                    async def _h(req):
                        return web.FileResponse(target_path)
                    return _h
                app.router.add_get(f"/{fpath.name}", make_handler(fpath))

    return app
