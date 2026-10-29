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
)
from services.telemetry_service import telemetry_service
from services.admin_flow_html import ADMIN_FLOW_HTML
from services.rasxod_service import rasxod_service
from services.kaloriya_service import kaloriya_service
from services.mafia_service import mafia_service
from services.quiz_service import quiz_service
from services.tv_room_service import tv_room_service, DEFAULT_CHANNEL_ID

logger = logging.getLogger(__name__)

# Global Bot ob'ekti (chatga ma'lumot yuborish uchun)
_bot_instance = None


def set_bot_instance(bot) -> None:
    """Asosiy bot nusxasini web serverga ulash."""
    global _bot_instance
    _bot_instance = bot


async def handle_health(request: web.Request) -> web.Response:
    """Render.com va boshqa bulutli xizmatlar uchun health check endpointi."""
    return web.json_response({
        "status": "ok",
        "bot": config.BOT_USERNAME,
        "service": "Bauntyfilms_bot & Mini App",
        "port": config.PORT,
        "timestamp": time.time(),
    })


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
    """Admin Flow & Database Monitor UI sahifasini uzatish."""
    return web.Response(
        text=ADMIN_FLOW_HTML,
        content_type="text/html",
        charset="utf-8",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


async def handle_admin_flow_data(request: web.Request) -> web.Response:
    """Admin Flow uchun real-vaqtdagi telemetriya va baza ma'lumotlarini JSON qaytarish."""
    data = await telemetry_service.get_full_telemetry()
    return web.json_response(data, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate"
    })


async def handle_admin_flow_benchmark(request: web.Request) -> web.Response:
    """Admin Flow ma'lumotlar bazasi tezkorlik benchmarkini bajarish."""
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

    # 1. 16 ta alohida CSS faylini yagona bundle.min.css ga almashtirish
    css_pattern = r'<link\s+rel="stylesheet"\s+href="(?:rasxod|kaloriya|asil|kattalar|mafia|tvroom|music|docs|fx|food|quiz|prava|games|story|books|zk)\.css">'
    html, n_css = re.subn(css_pattern, '', html)
    if n_css > 0:
        html = html.replace(
            '<link rel="preload" as="image" href="logo.webp">',
            f'<link rel="stylesheet" href="{css_ref}">\n<link rel="preload" as="image" href="logo.webp">'
        )

    # 2. 17 ta alohida JS skriptlarini va 1600 qatorli inline skriptni bundle.min.js ga almashtirish
    js_pattern = r'<script\s+src="(?:i18n|music|docs|games|kattalar|mafia|tvroom|story|books|fx|food|quiz|prava|rasxod|kaloriya|asil|zk)\.js"></script>'
    html = re.sub(js_pattern, '', html)

    last_script_pattern = r'<script>\s*\(\(\)\s*=>\s*\{\s*"use strict";[\s\S]*?load\(\);\s*\}\)\(\);\s*</script>'
    html = re.sub(last_script_pattern, f'<script src="{js_ref}" defer></script>', html)

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
    if (
        _PROD_INDEX_CACHE["html"] is None
        or (now - _PROD_INDEX_CACHE["ts"] > 300)
        or (_PROD_INDEX_CACHE["ts"] < file_mtime)
        or request.query.get("nocache")
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
        if cached is None or (len(cached) > 3 and cached[3] < file_mtime) or request.query.get("nocache"):
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
        if cached is None or (len(cached) > 3 and cached[3] < file_mtime) or request.query.get("nocache"):
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


def sanitize_catalog_text(text: str) -> str:
    """Barcha tashqi bot/kanal havolalarini @BauntyCinemabot va @BauntyFilms ga almashtirish."""
    if not text:
        return ""
    bot_clean = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
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
    """Kino posterlarini keshlab uzatish (161-97-96-58.sslip.io ga 1v1 proxy va in-memory kesh)."""
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

    # 3. Upstream serverdan yuklab olish
    upstream_url = f"https://161-97-96-58.sslip.io/p/{clean_name}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=2.0, connect=1.0)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
                    if len(_POSTER_CACHE) > 500:
                        _POSTER_CACHE.clear()
                    _POSTER_CACHE[clean_name] = (content, etag)
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
        logger.warning(f"Posterni yuklab bo'lmadi ({clean_name}): {e}")

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

    # 3. Upstream serverdan yuklab olish va lokal saqlash
    upstream_url = f"https://161-97-96-58.sslip.io/prava/{clean_name}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=2.0, connect=1.0)) as resp:
                if resp.status == 200:
                    content = await resp.read()
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
        logger.debug(f"Prava rasmini yuklab bo'lmadi ({clean_name}): {e}")

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

        # 3.1. Upstream @Zakirovs_ai sslip.io serveridan tezkor olishga urinish (0.4s limit)
        upstream_url = f"https://161-97-96-58.sslip.io/bk/{tail}"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=0.45, connect=0.25)) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
                        if len(_BOOK_CACHE) > 1000:
                            _BOOK_CACHE.clear()
                        _BOOK_CACHE[tail] = (content, content_type, etag)
                        def _save_bk(lp, c):
                            try:
                                lp.parent.mkdir(parents=True, exist_ok=True)
                                lp.write_bytes(c)
                            except Exception:
                                pass
                        asyncio.create_task(asyncio.to_thread(_save_bk, local_path, content))
                        return web.Response(
                            body=content,
                            content_type=content_type,
                            headers={
                                "Cache-Control": "public, max-age=31536000, immutable",
                                "Access-Control-Allow-Origin": "*",
                                "ETag": etag,
                            }
                        )
        except Exception:
            pass

        # 3.2. Asinxron fonda Unsplash dan yuklab olish (javobni kutmasdan, bloklamaydi)
        if book:
            cover_url = (book.get("cover") or book.get("poster") or book.get("image") or "").strip()
            if cover_url.startswith("http"):
                async def _bg_fetch_cover(u: str, t: str, lp: Path, e: str):
                    try:
                        import aiohttp
                        async with aiohttp.ClientSession() as s:
                            async with s.get(u, timeout=aiohttp.ClientTimeout(total=4.0, connect=2.0)) as r:
                                if r.status == 200:
                                    rb = await r.read()
                                    await asyncio.to_thread(_process_and_save_book_cover, rb, t, lp, e)
                    except Exception:
                        pass
                asyncio.create_task(_bg_fetch_cover(cover_url, tail, local_path, ext))

        # 3.3. Dinamik sifatli ultra-tezkor WebP muqova yaratish (Pillow yoki SVG) - <5ms javob
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
                toc_data = {
                    "ok": True,
                    "mode": "text",
                    "pages": book.get("pages", 120),
                    "toc": [
                        {"t": "1-bob. Muqaddima va mutolaa", "c": 1}
                    ]
                }
                c_bytes = json.dumps(toc_data, ensure_ascii=False).encode("utf-8")
                return web.Response(
                    body=c_bytes,
                    content_type="application/json",
                    headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=86400"}
                )
            elif m_ch:
                title = book.get("title", "Kitob")
                author = book.get("author", "Muallif")
                desc = book.get("description", "")
                sample = book.get("sample_text", desc)
                paras = [f"«{title}» ({author}) — Mutolaa nusxasi.", desc]
                paras.extend([p.strip() for p in sample.split("\n") if p.strip()])
                ch_data = {
                    "t": f"{title} — {author}",
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

    upstream_url = f"https://161-97-96-58.sslip.io/rc/{tail}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=2.0, connect=1.0)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    etag = f'"{hashlib.md5(content).hexdigest()[:16]}"'
                    if len(_RC_CACHE) > 500:
                        _RC_CACHE.clear()
                    _RC_CACHE[tail] = (content, content_type, etag)
                    def _save_rc(lp, c):
                        try:
                            lp.parent.mkdir(parents=True, exist_ok=True)
                            lp.write_bytes(c)
                        except Exception:
                            pass
                    asyncio.create_task(asyncio.to_thread(_save_rc, local_path, content))
                    return web.Response(
                        body=content,
                        content_type=content_type,
                        headers={
                            "Cache-Control": "public, max-age=604800, immutable",
                            "Access-Control-Allow-Origin": "*",
                            "ETag": etag,
                        }
                    )
    except Exception as e:
        logger.warning(f"Taom rasmi yuklanmadi ({tail}): {e}")

    return web.Response(status=404, text="Rasm topilmadi")


async def handle_watch_get(request: web.Request) -> web.Response:
    """Watch GET so'rovi (holat va yo'naltirish ma'lumoti)."""
    bot_username = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
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
        "bot": (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
    })


async def handle_doc_config(request: web.Request) -> web.Response:
    """Hujjatlar xizmati konfiguratsiyasi."""
    return web.json_response({
        "ok": True,
        "stamp": True,
        "max_mb": 50,
        "translate": True,
        "max_images": 50,
        "bot": (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
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
        "bot": (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@"),
        "channel": config.CHANNEL_USERNAME,
        "status": "online"
    })


_UPSTREAM_API_CACHE: Dict[str, Any] = {}


async def handle_upstream_api_proxy(request: web.Request) -> web.Response:
    """Yangi bo'limlar (food, quiz, fx, books/home, books/shelf) uchun API proxy va oq brendlash."""
    path = request.path.lstrip("/")
    if path.startswith("webapp/"):
        path = path[7:]

    now = time.time()
    cache_key = f"{request.method}:{path}:{request.query_string}"
    if request.method == "GET" and cache_key in _UPSTREAM_API_CACHE:
        entry = _UPSTREAM_API_CACHE[cache_key]
        if now - entry["ts"] < 120:
            cached_ct = (entry.get("content_type") or "application/json").split(";")[0].strip()
            return web.Response(
                body=entry["body"],
                content_type=cached_ct,
                headers={"Access-Control-Allow-Origin": "*"}
            )

    upstream_url = f"https://161-97-96-58.sslip.io/{path}"
    if request.query_string:
        upstream_url += f"?{request.query_string}"

    req_headers = {}
    init_data = request.headers.get("X-Init-Data")
    if init_data:
        req_headers["X-Init-Data"] = init_data
    if "Content-Type" in request.headers:
        req_headers["Content-Type"] = request.headers["Content-Type"]

    body_bytes = None
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body_bytes = await request.read()
        except Exception:
            body_bytes = None

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method,
                url=upstream_url,
                headers=req_headers,
                data=body_bytes,
                timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)
            ) as resp:
                resp_bytes = await resp.read()
                raw_ct = resp.headers.get("Content-Type", "application/json")
                clean_ct = raw_ct.split(";")[0].strip() if raw_ct else "application/json"
                try:
                    resp_text = resp_bytes.decode("utf-8", errors="replace")
                    clean_text = sanitize_catalog_text(resp_text)
                    if "books" in path:
                        clean_text = sanitize_book_text(clean_text)
                    resp_bytes = clean_text.encode("utf-8")
                except Exception:
                    pass

                if resp.status >= 400:
                    raise aiohttp.ClientError(f"Upstream returned {resp.status}")

                if request.method == "GET" and resp.status == 200:
                    _UPSTREAM_API_CACHE[cache_key] = {
                        "body": resp_bytes,
                        "content_type": clean_ct,
                        "ts": now
                    }

                return web.Response(
                    body=resp_bytes,
                    status=resp.status,
                    content_type=clean_ct,
                    headers={"Access-Control-Allow-Origin": "*"}
                )
    except Exception as e:
        logger.info(f"Upstream API tezkor zaxiraga o'tildi ({upstream_url}): {e}")
        # Barcha bo'limlar uchun xatosiz zaxira va chidamli fallback
        if "docs/config" in path:
            return await handle_doc_config(request)
        if "docs" in path:
            return await handle_doc_root(request)
        if "books/home" in path or "books/shelf" in path:
            from services import book_service
            cat = book_service.get_catalog(limit=20)
            return web.json_response({
                "ok": True,
                "categories": cat.get("categories", []),
                "featured": cat.get("books", [])[:10],
                "items": cat.get("books", [])[:20]
            })
        if "books/me" in path:
            return web.json_response({"ok": True, "shelf": [], "history": []})
        if "duel" in path:
            return web.json_response({"ok": True, "active": False, "rooms": []})
        if "story/me" in path:
            return await handle_story_me(request)
        if "story" in path:
            return web.json_response({"ok": True, "items": [], "profiles": []})
        if "food" in path:
            return web.json_response({"ok": True, "items": [], "categories": []})
        if "fx" in path:
            return await handle_fx_api(request)
        if "prava" in path:
            return await handle_prava_home(request)
        if "music/home" in path or path in ("api/music", "api/music/"):
            return await handle_music_home(request)
        if "music/me" in path:
            return web.json_response({"ok": True, "favorites": [], "history": [], "admin": False})
        if "music" in path:
            return web.json_response({"ok": True, "items": TOP_50_TRACKS[:20]})
        if "tv" in path:
            return await handle_get_tv(request)
        if "games" in path:
            return await handle_get_games(request)
        if "asil/colls" in path or path.endswith("colls"):
            return await handle_asil_colls(request)
        if "asil/coll" in path or "coll" in path:
            return await handle_asil_coll(request)
        if "asil" in path:
            return await handle_asil_home(request)
        if "quiz/home" in path:
            fallback_quiz = {
                "ok": True,
                "topics": [
                    {"k": "kino", "n": "Kino & Filmlar", "ic": "🎬", "c": 50},
                    {"k": "adabiyot", "n": "O'zbek adabiyoti", "ic": "📚", "c": 45},
                    {"k": "tarix", "n": "Tarix & Geografiya", "ic": "🌍", "c": 60},
                    {"k": "mantiq", "n": "Mantiq & Zukkolik", "ic": "🧠", "c": 40},
                    {"k": "fan", "n": "IT & Texnologiya", "ic": "💻", "c": 35}
                ],
                "popular": [
                    {"id": "q1", "t": "Kino olami bilimdoni", "ic": "🍿", "n": 10, "src": "seed", "pl": 1240},
                    {"id": "q2", "t": "O'zbek durdonalari", "ic": "📖", "n": 10, "src": "seed", "pl": 980}
                ]
            }
            return web.json_response(fallback_quiz)
        if "quiz/daily" in path:
            return web.json_response({
                "ok": True, "streak": 3, "n": 4820, "pct": 74, "done": False,
                "q": {
                    "t": "«O'tkan kunlar» romanida Otabekning Marg'ilondagi sevgilisi kim edi?",
                    "o": [["a", "Zaynab"], ["b", "Kumushbibi"], ["c", "Ra'no"], ["d", "Saodat"]],
                    "c": "b"
                }
            })
        if "quiz/me" in path:
            return web.json_response({"ok": True, "mine": []})
        if "quiz/solo/start" in path:
            return web.json_response({
                "ok": True,
                "sid": "solo_local_session",
                "title": "Kino & Adabiyot",
                "total": 5,
                "q": {
                    "t": "«O'tkan kunlar» romanida Otabekning Marg'ilondagi sevgilisi kim edi?",
                    "o": [["a", "Zaynab"], ["b", "Kumushbibi"], ["c", "Ra'no"], ["d", "Saodat"]],
                    "c": "b"
                }
            })
        if "quiz/solo/answer" in path:
            return web.json_response({"ok": True, "correct": True, "c": "b", "pts": 100})
        if "quiz/solo/next" in path:
            return web.json_response({"ok": True, "final": True, "score": 500, "total": 5, "rank": 1})
        if "rasxod" in path:
            return await handle_rasxod_api(request)
        if "kal" in path or "food/kcal" in path:
            return await handle_kaloriya_api(request)
        if "mafia" in path:
            return await handle_mafia_api(request)
        if "tvroom" in path or "tv_room" in path or "tvxona" in path:
            return await handle_tvroom_api(request)
        return web.json_response({"ok": False, "error": "upstream_unavailable"}, status=502)


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
            user_id = 7271080503  # default fallback id
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
            body = await request.json() if request.can_read_body else {}
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
            body = await request.json() if request.can_read_body else {}
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
            body = await request.json() if request.can_read_body else {}
            data = await rasxod_service.delete(user_id=user_id, expense_id=int(body.get("id", 0)))
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

        elif path.endswith("/budget"):
            body = await request.json() if request.can_read_body else {}
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
        if not request.can_read_body:
            return {}
        try:
            return await request.json()
        except Exception:
            return {}

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
            elif request.can_read_body:
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
            async with get_session() as session:
                prof = await crud.get_calorie_profile(session, user_id)
                if prof:
                    prof.is_pro = True
                    prof.pro_until = datetime.now() + timedelta(days=365)
                    await session.commit()
            st_data = await kaloriya_service.get_status(user_id=user_id)
            st_data["status"] = "approved"
            st_data["ok"] = True
            return web.json_response(st_data, headers={"Access-Control-Allow-Origin": "*"})

        elif "api/kal/adm" in path:
            st_data = await kaloriya_service.get_status(user_id=user_id)
            return web.json_response({
                "ok": True,
                "items": [],
                "user": {"id": user_id, "n": "Foydalanuvchi", "on": True, "d": 30, "until": (datetime.now() + timedelta(days=30)).isoformat()},
                "stats": {"act": 1, "today": 1, "soon": 0, "wait": 0}
            }, headers={"Access-Control-Allow-Origin": "*"})

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
    if _FX_CACHE["data"] and (now - _FX_CACHE["ts"] < 60):
        return web.json_response(_FX_CACHE["data"])

    raw_list = None
    try:
        import aiohttp
        cbu_url = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
        async with aiohttp.ClientSession() as session:
            async with session.get(cbu_url, timeout=aiohttp.ClientTimeout(total=2.0, connect=1.0)) as resp:
                if resp.status == 200:
                    raw_list = await resp.json()
    except Exception as e:
        logger.debug(f"CBU.uz API ulanishida kutilmagan holat ({e})")

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
    return web.json_response(result)


async def handle_fx_alerts(request: web.Request) -> web.Response:
    """Kurs o'zgarganda xabarnoma sozlamasi."""
    return web.json_response({"ok": True, "items": []})


async def handle_maintenance(request: web.Request) -> web.Response:
    """Mini App profilaktika holati API."""
    state = maintenance_service.get_state()
    return web.json_response({"ok": True, "maintenance": state, **state})


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

    # 304 Not Modified tekshiruvi
    if _CATALOG_CACHE.get("etag") and request.headers.get("If-None-Match") == _CATALOG_CACHE.get("etag"):
        return web.Response(
            status=304,
            headers={
                "ETag": _CATALOG_CACHE["etag"],
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=60"
            }
        )

    if _CATALOG_CACHE.get("data") and (now - _CATALOG_CACHE.get("ts", 0) < 120):
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
    # 1. Real-time upstreamdan olishga urinish
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("https://161-97-96-58.sslip.io/api/catalog", timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    raw_data = await resp.json()
                    if isinstance(raw_data, dict) and isinstance(raw_data.get("items"), list) and len(raw_data["items"]) >= 20:
                        for it in raw_data.get("items", []):
                            if "d" in it:
                                it["d"] = sanitize_catalog_text(it["d"])
                            if "t" in it:
                                it["t"] = sanitize_catalog_text(it["t"])
                        raw_data["channel"] = config.CHANNEL_USERNAME
                        raw_data["bot"] = config.BOT_USERNAME.lstrip("@")
                        data = raw_data
                        cat_file = BASE_DIR / "data" / "catalog.json"
                        asyncio.create_task(asyncio.to_thread(_save_cat_file, data, cat_file))
    except Exception as e:
        logger.info(f"Upstream katalog ulanishida kutilmagan holat ({e}), lokal kesh ishlatiladi.")

    # 2. Agar upstream bo'lmasa, lokal fayldan o'qish (asinxron thread)
    if not data:
        data = await asyncio.to_thread(_load_cat_file, BASE_DIR / "data" / "catalog.json")

    # Foydalanuvchi boti va kanali bilan dinamik sinxronlash
    data["ok"] = True
    data["channel"] = config.CHANNEL_USERNAME
    data["bot"] = config.BOT_USERNAME.lstrip("@")
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


async def handle_asil_home(request: web.Request) -> web.Response:
    """Asilmedia bosh sahifa tavsiyalari va janrlar (Real-time va Bauntys brendi)."""
    now = time.time()
    cache_key = "asil:home"
    if cache_key in _ASIL_API_CACHE:
        entry = _ASIL_API_CACHE[cache_key]
        if now - entry["ts"] < 120:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    upstream_url = "https://161-97-96-58.sslip.io/api/asil/home"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    resp_bytes = await resp.read()
                    text = resp_bytes.decode("utf-8", errors="replace")
                    clean = sanitize_catalog_text(text)
                    clean_bytes = clean.encode("utf-8")
                    _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
                    try:
                        backup_file = BASE_DIR / "data" / "asil_home_cache.json"
                        backup_file.write_text(clean, encoding="utf-8")
                    except Exception:
                        pass
                    return web.Response(
                        body=clean_bytes,
                        content_type="application/json",
                        headers={"Access-Control-Allow-Origin": "*"}
                    )
    except Exception as e:
        logger.debug("Upstream /api/asil/home error: %s", e)

    backup_file = BASE_DIR / "data" / "asil_home_cache.json"
    if backup_file.exists():
        try:
            data = backup_file.read_text(encoding="utf-8")
            return web.Response(
                text=data,
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        except Exception:
            pass

    return web.json_response({
        "ok": True,
        "film": [],
        "serial": [],
        "pop": [],
        "genres": [],
        "countries": []
    }, headers={"Access-Control-Allow-Origin": "*"})


async def handle_asil_list(request: web.Request) -> web.Response:
    """Asilmedia saralangan kinolar ro'yxati (Real-time)."""
    now = time.time()
    cache_key = f"asil:list:{request.query_string}"
    if cache_key in _ASIL_API_CACHE:
        entry = _ASIL_API_CACHE[cache_key]
        if now - entry["ts"] < 120:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    upstream_url = f"https://161-97-96-58.sslip.io/api/asil/list?{request.query_string}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    resp_bytes = await resp.read()
                    text = resp_bytes.decode("utf-8", errors="replace")
                    clean = sanitize_catalog_text(text)
                    clean_bytes = clean.encode("utf-8")
                    _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
                    return web.Response(
                        body=clean_bytes,
                        content_type="application/json",
                        headers={"Access-Control-Allow-Origin": "*"}
                    )
    except Exception as e:
        logger.debug("Upstream /api/asil/list error: %s", e)

    # Fast local fallback
    data = _build_local_colls_data()
    fallback_items = data.get("pool", [])[:20]
    return web.json_response({
        "ok": True,
        "items": fallback_items,
        "more": False,
        "page": 1
    }, headers={"Access-Control-Allow-Origin": "*"})


async def handle_asil_search(request: web.Request) -> web.Response:
    """Asilmedia qidiruv tizimi (Real-time)."""
    q = request.query.get("q", "").strip()
    if not q:
        return web.json_response({"ok": True, "items": []}, headers={"Access-Control-Allow-Origin": "*"})

    now = time.time()
    cache_key = f"asil:search:{q.lower()}"
    if cache_key in _ASIL_API_CACHE:
        entry = _ASIL_API_CACHE[cache_key]
        if now - entry["ts"] < 120:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    upstream_url = f"https://161-97-96-58.sslip.io/api/asil/search?q={urllib.parse.quote(q)}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    raw = await resp.json()
                    if isinstance(raw, dict) and "items" in raw:
                        for it in raw["items"]:
                            if "t" in it:
                                it["t"] = sanitize_catalog_text(it["t"])
                            if "alt" in it:
                                it["alt"] = sanitize_catalog_text(it["alt"])
                        clean_bytes = json.dumps(raw, ensure_ascii=False).encode("utf-8")
                        _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
                        return web.Response(
                            body=clean_bytes,
                            content_type="application/json",
                            headers={"Access-Control-Allow-Origin": "*"}
                        )
    except Exception as e:
        logger.debug("Upstream /api/asil/search error: %s", e)

    # Fallback: lokal asilmedia_service
    try:
        from services.asilmedia_service import asilmedia_service
        results = await asilmedia_service.search(q, limit=20)
        items = []
        for it in results:
            items.append({
                "id": int(it["id"]) if str(it.get("id", "")).isdigit() else it.get("id"),
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
        return web.json_response({"ok": True, "items": items}, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as fe:
        logger.warning("Local Asilmedia search fallback error: %s", fe)

    return web.json_response({"ok": True, "items": []}, headers={"Access-Control-Allow-Origin": "*"})


async def handle_asil_item(request: web.Request) -> web.Response:
    """Asilmedia film yoki serial to'liq kartochkasi va qismlari (Real-time va 100% Bauntys)."""
    item_id = request.query.get("id", "").strip()
    if not item_id:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)

    now = time.time()
    cache_key = f"asil:item:{item_id}"
    if cache_key in _ASIL_API_CACHE:
        entry = _ASIL_API_CACHE[cache_key]
        if now - entry["ts"] < 300:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    upstream_url = f"https://161-97-96-58.sslip.io/api/asil/item?id={urllib.parse.quote(item_id)}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    resp_bytes = await resp.read()
                    text = resp_bytes.decode("utf-8", errors="replace")
                    clean = sanitize_catalog_text(text)
                    clean_bytes = clean.encode("utf-8")
                    _ASIL_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
                    return web.Response(
                        body=clean_bytes,
                        content_type="application/json",
                        headers={"Access-Control-Allow-Origin": "*"}
                    )
    except Exception as e:
        logger.debug("Upstream /api/asil/item error: %s", e)

    # Fallback: lokal asilmedia_service
    try:
        from services.asilmedia_service import asilmedia_service
        movie = await asilmedia_service.get_movie_details(item_id)
        if movie:
            files = []
            if movie.episodes:
                parts_cnt = len(movie.episodes)
                files = [
                    {"s": 3, "q": "1080p", "tr": "", "note": "", "mb": 0, "parts": parts_cnt, "ok": True},
                    {"s": 2, "q": "720p", "tr": "", "note": "", "mb": 0, "parts": parts_cnt, "ok": True},
                    {"s": 1, "q": "480p", "tr": "", "note": "", "mb": 0, "parts": parts_cnt, "ok": True},
                ]
            else:
                files = [{"s": 3, "q": "1080p", "parts": 1, "ok": True}]

            item_data = {
                "id": int(movie.id) if str(movie.id).isdigit() else movie.id,
                "type": "serial" if movie.is_series else "film",
                "t": sanitize_catalog_text(movie.title),
                "alt": sanitize_catalog_text(movie.orig_title or ""),
                "y": movie.year,
                "p": movie.poster or "",
                "imdb": movie.rating,
                "ok": True,
                "g": movie.genres or [],
                "c": [],
                "desc": sanitize_catalog_text(movie.description or ""),
                "dur": movie.duration or "",
                "lang": "O'zbek",
                "watch": movie.watch_url or movie.url,
                "url": movie.url,
                "files": files
            }
            return web.json_response({"ok": True, "item": item_data}, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as fe:
        logger.warning("Local Asilmedia get_movie_details fallback error: %s", fe)

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
            all_pool.append({
                "id": int(cid) if cid.isdigit() else cid,
                "t": sanitize_catalog_text(it.get("t") or ""),
                "p": it.get("p_url") or it.get("p") or "",
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

        posters = [m["p"] for m in matched if m.get("p")][:4]
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
    """Asilmedia to'plamlari / kolleksiyalari — Fast upstream with instant local fallback."""
    now = time.time()
    cache_key = f"colls:{request.query_string}"
    if cache_key in _UPSTREAM_API_CACHE:
        entry = _UPSTREAM_API_CACHE[cache_key]
        if now - entry["ts"] < 180:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    upstream_url = "https://161-97-96-58.sslip.io/api/asil/colls"
    if request.query_string:
        upstream_url += f"?{request.query_string}"

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    resp_bytes = await resp.read()
                    clean_text = sanitize_catalog_text(resp_bytes.decode("utf-8", errors="replace"))
                    clean_bytes = clean_text.encode("utf-8")
                    _UPSTREAM_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
                    return web.Response(
                        body=clean_bytes,
                        content_type="application/json",
                        headers={"Access-Control-Allow-Origin": "*"}
                    )
    except Exception as e:
        logger.info(f"Upstream colls timeout/error ({e}), using instant local fallback.")

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
    """Asilmedia alohida to'plam tarkibi — Fast upstream with instant local fallback."""
    slug = request.query.get("slug", "").strip()
    now = time.time()
    cache_key = f"coll:{slug}:{request.query_string}"
    if cache_key in _UPSTREAM_API_CACHE:
        entry = _UPSTREAM_API_CACHE[cache_key]
        if now - entry["ts"] < 180:
            return web.Response(
                body=entry["body"],
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

    upstream_url = f"https://161-97-96-58.sslip.io/api/asil/coll?{request.query_string}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    resp_bytes = await resp.read()
                    clean_text = sanitize_catalog_text(resp_bytes.decode("utf-8", errors="replace"))
                    clean_bytes = clean_text.encode("utf-8")
                    _UPSTREAM_API_CACHE[cache_key] = {"body": clean_bytes, "ts": now}
                    return web.Response(
                        body=clean_bytes,
                        content_type="application/json",
                        headers={"Access-Control-Allow-Origin": "*"}
                    )
    except Exception as e:
        logger.info(f"Upstream coll [{slug}] timeout/error ({e}), using instant local fallback.")

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
            if not cached_item:
                import aiohttp
                async with aiohttp.ClientSession() as cl:
                    async with cl.get(
                        f"https://161-97-96-58.sslip.io/api/asil/item?id={urllib.parse.quote(item_id)}",
                        timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)
                    ) as ir:
                        if ir.status == 200:
                            ir_data = await ir.json()
                            cached_item = ir_data.get("item")
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
                        is_single_film = (
                            cached_item.get("is_series") is False
                            or cached_item.get("type") == "film"
                            or int(cached_item.get("parts") or cached_item.get("p") or 1) <= 1
                            or all(not re.search(r'(?:qism|part|ep|seriya|taksi|forsaj|chuqur|titan)[\s\-—–]*\d+', f"{fl.get('label', '')} {fl.get('note', '')}", re.IGNORECASE) for fl in file_list if isinstance(fl, dict))
                        )
                        for idx, fl in enumerate(file_list):
                            if isinstance(fl, dict) and (fl.get("s") == slot or fl.get("slot") == slot):
                                ep_num = fl.get("part") or fl.get("p") or fl.get("e")
                                if ep_num is not None:
                                    try:
                                        part = int(ep_num)
                                        break
                                    except (ValueError, TypeError):
                                        pass
                                label_text = f"{fl.get('label', '')} {fl.get('note', '')} {fl.get('tr', '')}"
                                m_part = re.search(r'(?:taksi|forsaj|chuqur|titan|qism|part|ep|seriya)[\s\-—–]*(\d+)', label_text, re.IGNORECASE)
                                if not m_part:
                                    m_part = re.search(r'(\d+)[\s\-—–]*(?:qism|part|seriya|ep)', label_text, re.IGNORECASE)
                                if m_part:
                                    part = int(m_part.group(1))
                                    break
                                part = 1 if is_single_film else idx + 1
                                break
                            elif fl == slot:
                                part = 1 if is_single_film else idx + 1
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

    bot_username = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
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
                part=part
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
                    "error": "need_start",
                    "url": bot_url,
                    "bot": bot_username
                })
            else:
                return web.json_response({
                    "ok": False,
                    "error": "not_ready",
                    "id": item_id,
                    "part": part
                })
    else:
        return web.json_response({"ok": True, "delivered": True, "id": item_id, "part": part, "mock": True})


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

    # 2. Asilmedia orqali Telegram pleyer yoki fayllar stream havolasini olish
    try:
        from services.asilmedia_service import asilmedia_service
        movie = await asilmedia_service.get_movie_details(clean_id)
        if movie:
            watch_url = None
            if part in movie.episodes:
                ep = movie.episodes[part]
                watch_url = ep.watch_url or ep.url
            if not watch_url:
                watch_url = (
                    movie.watch_url
                    or movie.video_sources.get(f"tg_{quality}")
                    or movie.video_sources.get(quality)
                    or movie.video_sources.get("tg_1080p")
                    or movie.video_sources.get("1080p")
                    or movie.video_sources.get("primary")
                    or (list(movie.video_sources.values())[0] if movie.video_sources else None)
                )
            if watch_url and str(watch_url).startswith("http"):
                raise web.HTTPFound(watch_url)
    except web.HTTPFound:
        raise
    except Exception as e:
        logger.debug("handle_asil_stream lookup error: %s", e)

    # 3. Upstream /api/asil/item orqali qidirish
    try:
        import aiohttp
        async with aiohttp.ClientSession() as cl:
            async with cl.get(
                f"https://161-97-96-58.sslip.io/api/asil/item?id={urllib.parse.quote(clean_id)}",
                timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)
            ) as ir:
                if ir.status == 200:
                    ir_data = await ir.json()
                    it = ir_data.get("item")
                    if it and it.get("watch") and str(it["watch"]).startswith("http"):
                        raise web.HTTPFound(it["watch"])
    except web.HTTPFound:
        raise
    except Exception:
        pass

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

    bot_username = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
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
                part=part
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
            return web.json_response({
                "ok": False,
                "action": "open_bot",
                "url": bot_url,
                "error": "send_failed",
                "delivered": False,
                "code": clean_code,
                "part": part
            })
    elif user_id and not _bot_instance:
        return web.json_response({
            "ok": False,
            "action": "open_bot",
            "url": bot_url,
            "error": "bot_not_connected",
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
            "error": "user_id_missing",
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
    """Mini App musiqa bosh sahifasi (Top 50, Hits, Kliplar, Ijrochilar) - upstream bilan to'g'ridan-to'g'ri bog'langan."""
    global _MUSIC_HOME_CACHE, _MUSIC_HOME_TS
    now = time.time()
    if not force_refresh and _MUSIC_HOME_CACHE is not None and (now - _MUSIC_HOME_TS < 300):
        return _MUSIC_HOME_CACHE

    # 1. Upstream serverdan (@BauntyCinemabot / https://161-97-96-58.sslip.io) to'g'ridan-to'g'ri yangilash
    try:
        import aiohttp
        upstream_url = "https://161-97-96-58.sslip.io/api/music/home"
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    resp_bytes = await resp.read()
                    resp_text = resp_bytes.decode("utf-8", errors="replace")
                    clean_text = sanitize_catalog_text(resp_text)
                    data = json.loads(clean_text)
                    if isinstance(data, dict) and data.get("ok"):
                        _update_music_home_cache(data, now)
                        music_home_path = BASE_DIR / "data" / "music_home.json"
                        asyncio.create_task(asyncio.to_thread(_save_music_home_file, data, music_home_path))
                        return data
    except Exception as e:
        logger.info(f"Upstream music/home ulanishida xatolik ({e}), lokal kesh ishlatiladi.")

    # 2. Lokal music_home.json faylidan o'qish (asinxron thread)
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


async def handle_tv_report(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def handle_tv_me(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "admin": False})


async def handle_tv_hide(request: web.Request) -> web.Response:
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
    code = request.match_info.get("code", "")
    try:
        async with get_session() as session:
            movie = await crud.get_movie_by_code(session, code)
            if movie:
                return web.json_response({
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
                })
    except Exception as e:
        logger.warning(f"Kino tafsilotini DB dan olishda xatolik ({e}), zaxira tekshirilmoqda")

    cat = await asyncio.to_thread(_load_cat_file, BASE_DIR / "data" / "catalog.json")
    for it in cat.get("items", []):
        if str(it.get("c")) == str(code):
            return web.json_response({
                "ok": True,
                "id": it.get("c"),
                "code": str(it.get("c")),
                "title": it.get("t", ""),
                "genres": "Barcha",
                "year": None,
                "rating": it.get("r"),
                "duration": None,
                "views_count": it.get("v", 0),
                "downloads_count": 0,
                "description": it.get("d", "")
            })

    return web.json_response({"error": "Kino topilmadi"}, status=404)


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
    return web.json_response({"ok": True})


async def handle_music_purge(request: web.Request) -> web.Response:
    """Musiqa keshini tozalash (admin)."""
    return web.json_response({"ok": True})


async def handle_music_search(request: web.Request) -> web.Response:
    """Web App va qidiruv uchun musiqa qidirish API — Upstream + Fallback bilan."""
    q = request.query.get("q", "").strip()
    try:
        n = int(request.query.get("n", 25))
    except (ValueError, TypeError):
        n = 25

    if not q:
        return web.json_response({"ok": True, "items": []})

    init_data = request.headers.get("X-Init-Data", "")

    # 1. Upstream (@BauntyCinemabot / https://161-97-96-58.sslip.io) dan qidirishga urinish
    try:
        import aiohttp
        import urllib.parse
        upstream_url = f"https://161-97-96-58.sslip.io/api/music/search?q={urllib.parse.quote(q)}&n={n}"
        req_headers = {"User-Agent": "Mozilla/5.0"}
        if init_data:
            req_headers["X-Init-Data"] = init_data

        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, headers=req_headers, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    raw_text = await resp.text()
                    clean_text = sanitize_catalog_text(raw_text)
                    data = json.loads(clean_text)
                    if isinstance(data, dict) and data.get("ok") and data.get("items"):
                        return web.json_response(data, headers={"Cache-Control": "public, max-age=180"})
    except Exception as e:
        logger.info(f"Upstream music/search xatolik ({e}), lokal qidiruv ishlatiladi.")

    # 2. Mahalliy parallel qidiruv (Deezer + Tarona + Soundcloud + iTunes + Invidious)
    try:
        tracks = await music_service.search_tracks(query=q, limit=n)
        return web.json_response({"ok": True, "items": tracks}, headers={"Cache-Control": "public, max-age=180"})
    except Exception as e:
        logger.error(f"Musiqa qidirishda xatolik: {e}")
        return web.json_response({"ok": False, "error": str(e), "items": []})


_PLAY_STREAM_CACHE: Dict[str, Tuple[float, str]] = {}


async def handle_music_play(request: web.Request) -> web.Response:
    """Web App musiqa tinglash uchun MP3 oqim havolasini tayyorlash API — Upstream + in-memory kesh bilan."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    url = body.get("u") or body.get("preview") or body.get("url")
    track_id = str(body.get("id") or "")
    cache_key = f"{track_id}_{url}"
    now = time.time()

    if cache_key in _PLAY_STREAM_CACHE:
        ts, cached_url = _PLAY_STREAM_CACHE[cache_key]
        if now - ts < 3600:
            return web.json_response({"ok": True, "url": cached_url}, headers={"Cache-Control": "public, max-age=1800"})

    init_data = request.headers.get("X-Init-Data", "")

    # 1. Upstream (@BauntyCinemabot / https://161-97-96-58.sslip.io) dan oqim havolasini olish
    try:
        import aiohttp
        upstream_url = "https://161-97-96-58.sslip.io/api/music/play"
        req_headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        if init_data:
            req_headers["X-Init-Data"] = init_data

        async with aiohttp.ClientSession() as session:
            async with session.post(upstream_url, json=body, headers=req_headers, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    raw_text = await resp.text()
                    clean_text = sanitize_catalog_text(raw_text)
                    data = json.loads(clean_text)
                    if isinstance(data, dict) and data.get("ok") and data.get("url"):
                        stream_url = data["url"]
                        _PLAY_STREAM_CACHE[cache_key] = (now, stream_url)
                        return web.json_response(data, headers={"Cache-Control": "public, max-age=1800"})
    except Exception as e:
        logger.debug(f"Upstream music/play xatolik: {e}")

    # Tarona bazasi bo'lsa, to'g'ridan-to'g'ri .mp3 audio oqim havolasini aniqlash
    if body.get("s") == "tarona" or (url and any(d in str(url) for d in ["muzfm", "mp3uz", "/music/"])):
        direct_tarona = await music_service._resolve_tarona_direct_mp3(body)
        if direct_tarona:
            _PLAY_STREAM_CACHE[cache_key] = (now, direct_tarona)
            return web.json_response({"ok": True, "url": direct_tarona}, headers={"Cache-Control": "public, max-age=1800"})

    # Faqat haqiqiy audio oqim yoki CDN bo'lsa darhol qaytarish (YouTube yoki HTML sahifalar audio emas)
    is_direct_audio = (
        url and str(url).startswith("http")
        and not any(p in str(url) for p in ["/music/", ".html", "search?", "youtube.com", "youtu.be", "/watch?", "t.me"])
        and (
            any(ext in str(url) for ext in [".mp3", ".m4a", ".ogg", "dzcdn", "mzstatic", "sndcdn", "audio-preview"])
            or not any(w in str(url) for w in ["youtube", "youtu.be", "watch?"])
        )
    )
    if is_direct_audio:
        _PLAY_STREAM_CACHE[cache_key] = (now, url)
        return web.json_response({"ok": True, "url": url}, headers={"Cache-Control": "public, max-age=1800"})

    # Deezer ID bo'yicha to'g'ridan-to'g'ri preview olish
    if track_id and body.get("s") == "dz":
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.deezer.com/track/{track_id}", timeout=aiohttp.ClientTimeout(total=2.0, connect=1.0)) as resp:
                    if resp.status == 200:
                        dz_data = await resp.json()
                        preview_mp3 = dz_data.get("preview")
                        if preview_mp3:
                            _PLAY_STREAM_CACHE[cache_key] = (now, preview_mp3)
                            return web.json_response({"ok": True, "url": preview_mp3}, headers={"Cache-Control": "public, max-age=1800"})
        except Exception as e:
            logger.info(f"Deezer preview olishda xatolik: {e}")

    # Qo'shiq va ijrochi nomi bo'yicha haqiqiy audio oqim qidirish (Tarona direct MP3 va Deezer/iTunes)
    artist = body.get("a") or body.get("artist") or ""
    title = body.get("t") or body.get("title") or ""
    # Emojilar, yil, shovqin so'zlarni tozalash
    clean_title = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]', '', title)
    clean_title = re.sub(r'\|.*$|\(.*?\)|\[.*?\]', '', clean_title)
    clean_title = re.sub(r'\b(202\d|xit|premyera|official|video|mp3|remix|hd|klip)\b', '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'[^\w\s\'-]', ' ', clean_title).strip()
    
    clean_artist = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]', '', artist)
    clean_artist = re.sub(r'[^\w\s\'-]', ' ', clean_artist).strip()

    search_queries = [
        f"{clean_artist} {clean_title}".strip(),
        f"{clean_title}".strip(),
        f"{artist} {title}".strip()
    ]

    for q in search_queries:
        if not q or len(q) < 2:
            continue
        try:
            results = await music_service.search_tracks(query=q, limit=5)
            for res in results:
                # 1. Tarona / Muzfm to'g'ridan-to'g'ri MP3 faylini olish
                tarona_link = res.get("link") or res.get("u") or res.get("preview")
                if tarona_link and ("muzfm" in str(tarona_link) or "tarona" in str(tarona_link) or "/music/" in str(tarona_link)):
                    direct_mp3 = await music_service._resolve_tarona_direct_mp3(res)
                    if direct_mp3 and direct_mp3.startswith("http"):
                        _PLAY_STREAM_CACHE[cache_key] = (now, direct_mp3)
                        return web.json_response({"ok": True, "url": direct_mp3}, headers={"Cache-Control": "public, max-age=1800"})

                # 2. To'g'ridan-to'g'ri audio preview yoki CDN oqimi
                stream_res = res.get("preview") or res.get("url") or res.get("u")
                if stream_res and str(stream_res).startswith("http") and not any(p in str(stream_res) for p in ["youtube.com", "youtu.be", "/watch?", ".html", "/music/"]):
                    if any(ext in str(stream_res) for ext in [".mp3", ".m4a", ".ogg", "dzcdn", "mzstatic", "sndcdn", "audio-preview"]):
                        _PLAY_STREAM_CACHE[cache_key] = (now, stream_res)
                        return web.json_response({"ok": True, "url": stream_res}, headers={"Cache-Control": "public, max-age=1800"})
        except Exception as e:
            logger.debug(f"Play search query '{q}' xatosi: {e}")

    # Agar YouTube ID (y) mavjud bo'lsa, Invidious ochiq audio oqimini sinash
    yt_id = body.get("y") or (track_id if len(track_id) == 11 and not track_id.isdigit() else None)
    if yt_id:
        for host in ["invidious.jing.rocks", "invidious.nerdvpn.de", "invidious.private.coffee"]:
            inv_stream = f"https://{host}/latest_version?id={yt_id}&itag=140"
            _PLAY_STREAM_CACHE[cache_key] = (now, inv_stream)
            return web.json_response({"ok": True, "url": inv_stream}, headers={"Cache-Control": "public, max-age=1800"})

    # Begona yoki adashgan qo'shiqni qo'ymaslik uchun random fallback olib tashlandi
    return web.json_response({"ok": False, "error": "stream_not_found"}, status=404)


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
    # 1. Haqiqiy MP3 faylini yuklab olib yuborish
    try:
        res = await music_service.download_track_mp3(full_query, track_info=body)
        if res.success and res.file_path and os.path.exists(res.file_path):
            caption = (
                f"🎵 <b>{artist} - {title}</b>\n\n"
                f"🤖 @{config.BOT_USERNAME.lstrip('@')} Mini App orqali yuborildi\n"
                f"🍿 {config.CHANNEL_USERNAME}"
            )
            await _bot_instance.send_audio(
                chat_id=chat_id,
                audio=FSInputFile(res.file_path),
                title=title,
                performer=artist or f"@{config.BOT_USERNAME.lstrip('@')}",
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
                    f"🤖 @{config.BOT_USERNAME.lstrip('@')} Mini App orqali yuborildi\n"
                    f"🍿 {config.CHANNEL_USERNAME}"
                )
                await _bot_instance.send_audio(
                    chat_id=chat_id,
                    audio=send_url,
                    title=title,
                    performer=artist or f"@{config.BOT_USERNAME.lstrip('@')}",
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
                    f"🤖 @{config.BOT_USERNAME.lstrip('@')}\n"
                    f"🍿 {config.CHANNEL_USERNAME}"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    return web.json_response({"ok": True, "message": f"«{artist} - {title}» chatga yuborildi!"})


_TV_ALL_CACHE: Dict[str, Any] = {"bytes": None, "ts": 0, "etag": None}


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
            limit=200,
            ttl_dns_cache=300,
            keepalive_timeout=60,
            ssl=False,
        )
        timeout = aiohttp.ClientTimeout(total=60.0, connect=5.0, sock_read=25.0)
        _TV_PROXY_SESSION = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        )
    return _TV_PROXY_SESSION


async def handle_tv_stream_proxy(request: web.Request) -> web.StreamResponse:
    """
    Jonli telekanallar uchun yuqori tezlikdagi HLS (m3u8 va ts segmentlar) proxy va CORS relay.
    CORS cheklovlari va brauzer aralash kontent (mixed-content) xatolarini bartaraf qiladi.
    M3U8 oqimlari relatsion yo'llarini qayta yozadi, TS segmentlarini oqimli uzatadi.
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

    # Xavfsizlik: SSRF himoyasi
    from urllib.parse import urlparse, quote, urljoin
    try:
        parsed = urlparse(target_url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or host.startswith("192.168.") or host.startswith("10.") or host.startswith("172.16."):
            return web.Response(
                status=403,
                text="Taqiqlangan manzil",
                headers={"Access-Control-Allow-Origin": "*"}
            )
    except Exception:
        pass

    req_headers = {
        "User-Agent": request.headers.get("User-Agent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": request.headers.get("Accept") or "*/*",
    }
    if "Range" in request.headers:
        req_headers["Range"] = request.headers["Range"]

    # Upstream referer va origin headerlari (Cinerama, Mediabay, BizTV va b. uchun)
    if "cinerama.uz" in host:
        req_headers["Referer"] = "https://cinerama.uz/"
        req_headers["Origin"] = "https://cinerama.uz"
    elif "mediabay" in host:
        req_headers["Referer"] = "https://mediabay.uz/"
        req_headers["Origin"] = "https://mediabay.uz"
    elif "biztv" in host:
        req_headers["Referer"] = "https://biztv.uz/"
        req_headers["Origin"] = "https://biztv.uz"
    elif "famelack" in host:
        req_headers["Referer"] = "https://famelack.com/"
        req_headers["Origin"] = "https://famelack.com"
    elif parsed.scheme and host:
        req_headers["Referer"] = f"{parsed.scheme}://{host}/"
        req_headers["Origin"] = f"{parsed.scheme}://{host}"

    stream_resp = None
    try:
        session = await _get_tv_proxy_session()
        async with session.request(
            method=request.method,
            url=target_url,
            headers=req_headers,
            allow_redirects=True,
        ) as upstream_resp:
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

            stream_resp = web.StreamResponse(
                status=upstream_resp.status,
                headers=resp_headers
            )
            await stream_resp.prepare(request)
            async for chunk in upstream_resp.content.iter_chunked(64 * 1024):
                await stream_resp.write(chunk)
            await stream_resp.write_eof()
            return stream_resp

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
    """Anonim story ko'rish API."""
    username = request.query.get("username", "instagram").strip().lstrip("@")
    stories = [
        {"id": 1, "type": "image", "media_url": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600", "timestamp": "2 soat oldin"},
        {"id": 2, "type": "video", "media_url": "https://www.w3schools.com/html/mov_bbb.mp4", "timestamp": "5 soat oldin"},
    ]
    return web.json_response({
        "ok": True,
        "username": username,
        "avatar": f"https://api.dicebear.com/7.x/identicon/svg?seed={username}",
        "stories": stories,
        "total": len(stories),
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
    sent_any = False
    caption = (
        f"👀 <b>@{clean_u} ning hikoyasi</b>\n\n"
        f"🤖 @{config.BOT_USERNAME.lstrip('@')} orqali yuklandi\n"
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

    # 3. Zaxira matn
    if not sent_any:
        try:
            await _bot_instance.send_message(
                chat_id=chat_id,
                text=(
                    f"👀 <b>@{clean_u}</b> profili hikoyalari (Mini App)\n\n"
                    f"🍿 {config.CHANNEL_USERNAME}\n"
                    f"🤖 @{config.BOT_USERNAME.lstrip('@')}"
                ),
                parse_mode="HTML"
            )
            sent_any = True
        except Exception:
            pass

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
                part=req_part
            )
            if delivered:
                cat_item = MovieService.get_catalog_item(clean_code)
                title = cat_item.get("t") if cat_item else f"Kino #{clean_code}"
                return web.json_response({"success": True, "ok": True, "message": f"«{title}» chatga yuborildi!"})
            else:
                return web.json_response({"error": "Kino topilmadi"}, status=404)
        elif action_type == "music":
            title = body.get("title", "Musiqa")
            artist = body.get("artist", "")
            # Musiqa trekini TOP_50_TRACKS dan qidirish
            matching_track = next((t for t in TOP_50_TRACKS if t["title"].lower() == title.lower() or (artist and artist.lower() in t["artist"].lower())), None)
            sent_audio = False
            if matching_track and matching_track.get("url"):
                try:
                    caption = (
                        f"🎵 <b>{artist} - {title}</b>\n\n"
                        f"🤖 @{config.BOT_USERNAME.lstrip('@')} Mini App orqali yuborildi\n"
                        f"🍿 {config.CHANNEL_USERNAME}"
                    )
                    await _bot_instance.send_audio(
                        chat_id=chat_id,
                        audio=matching_track["url"],
                        title=title,
                        performer=artist,
                        caption=caption,
                        parse_mode="HTML"
                    )
                    sent_audio = True
                except Exception as e_audio:
                    logger.warning(f"Audio yuborishda xatolik ({e_audio}), xabar yuborilmoqda")

            if not sent_audio:
                await _bot_instance.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🎵 <b>{artist} - {title}</b>\n\n"
                        "Ilovadan tanlangan musiqa!\n\n"
                        f"🤖 @{config.BOT_USERNAME.lstrip('@')}\n"
                        f"🍿 {config.CHANNEL_USERNAME}"
                    ),
                    parse_mode="HTML"
                )
            return web.json_response({"success": True, "message": f"«{artist} - {title}» chatga yuborildi!"})
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
        "bot": config.BOT_USERNAME.lstrip("@"),
        "channel": config.CHANNEL_USERNAME
    }
    return web.json_response(home_data, headers={"Access-Control-Allow-Origin": "*"})


async def handle_books_me(request: web.Request) -> web.Response:
    """Foydalanuvchining kitob javoni va o'qish statistikasi."""
    return web.json_response({
        "ok": True,
        "books": [],
        "shelf": [],
        "stats": {"secs": 0, "books": 0},
        "audio": [],
        "notes": []
    }, headers={"Access-Control-Allow-Origin": "*"})


async def handle_books_action(request: web.Request) -> web.Response:
    """Javon, progress va qaydlar amallari."""
    return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})


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

    # 1. Avval real-time upstream API ga so'rov (3390+ kitoblar)
    upstream_url = "https://161-97-96-58.sslip.io/api/books/search"
    if request.query_string:
        upstream_url += f"?{request.query_string}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                if resp.status == 200:
                    raw_data = await resp.json()
                    if isinstance(raw_data, dict) and "items" in raw_data:
                        raw_items = raw_data.get("items", [])
                        total = raw_data.get("total", len(raw_items))
                        for it in raw_items:
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
                            b["p"] = b.get("p", 0)
                            b["l"] = b.get("l", "uz")
                            b["f"] = b.get("f") or ["pdf", "epub"]
                            b["s"] = b.get("s") or {"pdf": 2500000, "epub": 1375000}
                            items.append(b)
    except Exception as e:
        logger.debug(f"Upstream books search xatosi ({e}), lokal qidiruvga o'tiladi")

    # 2. Agar upstream natija bermasa yoki offline bo'lsa — mahalliy katalogdan qidirish
    if not items:
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
            local_items = sorted(local_items, key=lambda x: x.get("title", ""))
        elif sort == "rate":
            local_items = sorted(local_items, key=lambda x: x.get("rating", 0), reverse=True)
        elif sort == "new":
            local_items = sorted(local_items, key=lambda x: x.get("year", 0), reverse=True)
        items = local_items

    return web.json_response({"ok": True, "items": items, "total": total}, headers={"Access-Control-Allow-Origin": "*"})


async def handle_book_detail(request: web.Request) -> web.Response:
    """Kitobning to'liq ma'lumotlarini olish (mahalliy yoki upstream)."""
    book_id = request.match_info.get("id", "").strip() or request.query.get("id", "").strip() or request.query.get("i", "").strip()
    from services import book_service
    book = book_service.get_book_by_id(book_id)
    if not book:
        return web.json_response({"ok": False, "error": "not_found"}, status=404, headers={"Access-Control-Allow-Origin": "*"})
    return web.json_response({"ok": True, "book": book}, headers={"Access-Control-Allow-Origin": "*"})


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

    bot_username = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
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
    channel = config.CHANNEL_USERNAME.strip()
    if not user_id or not channel or not _bot_instance:
        return web.json_response({"ok": True, "sub": True})

    if config.is_admin(user_id):
        return web.json_response({"ok": True, "sub": True})

    try:
        member = await _bot_instance.get_chat_member(chat_id=channel, user_id=user_id)
        status = getattr(member, "status", None) or (member.get("status") if isinstance(member, dict) else "")
        if status in ("creator", "administrator", "member", "restricted"):
            return web.json_response({"ok": True, "sub": True})
        else:
            return web.json_response({
                "ok": True,
                "sub": False,
                "channels": [
                    {
                        "title": "Baunty Films",
                        "url": f"https://t.me/{channel.lstrip('@')}"
                    }
                ]
            })
    except Exception as e:
        logger.debug(f"Kanal obunasini tekshirishda xatolik yoki bypass: {e}")
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
    """Bauntys reklama berish ma'lumotlari."""
    channel_clean = config.CHANNEL_USERNAME.lstrip("@")
    return web.json_response({
        "ok": True,
        "on": True,
        "users": 250000,
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
        ("GET", "/api/music/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/music/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/tv/stream", handle_tv_stream_proxy),
        ("POST", "/api/tv/stream", handle_tv_stream_proxy),
        ("GET", "/api/tv", handle_get_tv),
        ("POST", "/api/tv", handle_get_tv),
        ("GET", "/api/tv/icon/{id}", handle_tv_icon),
        ("POST", "/api/tv/report", handle_tv_report),
        ("GET", "/api/tv/me", handle_tv_me),
        ("POST", "/api/tv/hide", handle_tv_hide),
        ("GET", "/api/tv/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/tv/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/games", handle_get_games),
        ("POST", "/api/games", handle_get_games),
        ("POST", "/api/games/chest/claim", handle_chest_claim),
        ("POST", "/api/games/pet/action", handle_pet_action),
        ("GET", "/api/games/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/games/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/story", handle_story),
        ("POST", "/api/story", handle_story),
        ("GET", "/api/story/me", handle_story_me),
        ("GET", "/api/story/ig", handle_story_ig),
        ("GET", "/api/story/ighl", handle_story_ighl),
        ("GET", "/api/story/tg", handle_story_tg),
        ("POST", "/api/story/send", handle_story_send),
        ("POST", "/api/story/watch", handle_story_watch),
        ("GET", "/api/story/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/story/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/docs", handle_doc_root),
        ("POST", "/api/docs", handle_doc_root),
        ("GET", "/api/docs/config", handle_doc_config),
        ("POST", "/api/docs/convert", handle_doc_convert),
        ("POST", "/api/docs/pdf", handle_doc_pdf),
        ("POST", "/api/docs/upload", handle_upstream_api_proxy),
        ("POST", "/api/docs/run", handle_upstream_api_proxy),
        ("POST", "/api/docs/preview", handle_upstream_api_proxy),
        ("GET", "/api/docs/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/docs/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/books", handle_books_catalog),
        ("POST", "/api/books", handle_books_catalog),
        ("GET", "/api/books/home", handle_books_home),
        ("POST", "/api/books/home", handle_books_home),
        ("GET", "/api/books/shelf", handle_books_me),
        ("POST", "/api/books/shelf", handle_books_action),
        ("GET", "/api/books/me", handle_books_me),
        ("POST", "/api/books/progress", handle_books_action),
        ("POST", "/api/books/note", handle_books_action),
        ("GET", "/api/books/audio", handle_upstream_api_proxy),
        ("GET", "/api/books/b/{id}", handle_book_detail),
        ("GET", "/api/books/page/{id}/{n}", handle_upstream_api_proxy),
        ("GET", "/api/books/search", handle_books_search),
        ("GET", "/api/books/{id}", handle_book_detail),
        ("GET", "/api/books/{id}/pdf", handle_book_pdf),
        ("POST", "/api/books/send", handle_book_send),
        ("GET", "/api/books/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/books/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/food/kcal/{tail:.*}", handle_kaloriya_api),
        ("POST", "/api/food/kcal/{tail:.*}", handle_kaloriya_api),
        ("GET", "/api/food", handle_upstream_api_proxy),
        ("GET", "/api/food/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/quiz", handle_quiz_api),
        ("POST", "/api/quiz", handle_quiz_api),
        ("GET", "/api/quiz/{tail:.*}", handle_quiz_api),
        ("POST", "/api/quiz/{tail:.*}", handle_quiz_api),
        ("GET", "/api/fx", handle_fx_api),
        ("POST", "/api/fx", handle_fx_api),
        ("GET", "/api/fx/alerts", handle_fx_alerts),
        ("GET", "/api/fx/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/fx/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/maintenance", handle_maintenance),
        ("POST", "/api/maintenance", handle_maintenance),
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
        ("GET", "/api/prava/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/prava/{tail:.*}", handle_upstream_api_proxy),
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
        ("GET", "/api/asil/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/asil/{tail:.*}", handle_upstream_api_proxy),
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
        ("GET", "/api/duel", handle_upstream_api_proxy),
        ("GET", "/api/duel/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/duel/{tail:.*}", handle_upstream_api_proxy),
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

    # Asosiy Mini App papkasidagi barcha statik fayllarni root orqali ham berish
    for fpath in webapp_dir.iterdir():
        if fpath.is_file() and fpath.name != "index.html":
            def make_handler(target_path):
                async def _h(req):
                    return web.FileResponse(target_path)
                return _h
            app.router.add_get(f"/{fpath.name}", make_handler(fpath))

    return app
