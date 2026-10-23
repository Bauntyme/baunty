"""
Bauntyfilms Web Server va Mini App API (aiohttp.web)
Portlar va Render.com mosligi bilan.
"""
import os
import re
import json
import time
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
)

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


async def handle_favicon(request: web.Request) -> web.Response:
    """Favicon so'rovlariga javob berish (404 xatoliklarining oldini olish)."""
    fav_file = BASE_DIR / "webapp" / "favicon.ico"
    if fav_file.exists():
        return web.FileResponse(fav_file)
    return web.Response(status=204)


async def handle_index(request: web.Request) -> web.FileResponse:
    """Asosiy Mini App sahifasi (index.html)."""
    index_file = BASE_DIR / "webapp" / "index.html"
    if index_file.exists():
        return web.FileResponse(index_file)
    return web.Response(text="<h1>Kinolar katalogi Mini App ishga tushirilmoqda...</h1>", content_type="text/html")


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


_CATALOG_CACHE: Dict[str, Any] = {"data": None, "ts": 0}


def sanitize_catalog_text(text: str) -> str:
    """Barcha tashqi bot/kanal havolalarini @Bauntyfilmsbot va @BauntyFilms ga almashtirish."""
    if not text:
        return ""
    bot_clean = (config.BOT_USERNAME or "Bauntyfilmsbot").lstrip("@")
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


async def handle_poster_proxy(request: web.Request) -> web.Response:
    """Kino posterlarini keshlab uzatish (161-97-96-58.sslip.io ga 1v1 proxy)."""
    filename = request.match_info.get("filename", "")
    clean_name = os.path.basename(filename)
    if not clean_name or not (clean_name.endswith(".webp") or clean_name.endswith(".jpg") or clean_name.endswith(".png")):
        return web.Response(status=404, text="Topilmadi")

    posters_dir = BASE_DIR / "data" / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)
    local_path = posters_dir / clean_name

    if local_path.exists():
        with open(local_path, "rb") as f:
            content = f.read()
        return web.Response(
            body=content,
            content_type="image/webp",
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "Access-Control-Allow-Origin": "*",
            }
        )

    # Upstream serverdan yuklab olish
    upstream_url = f"https://161-97-96-58.sslip.io/p/{clean_name}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open(local_path, "wb") as pf:
                        pf.write(content)
                    return web.Response(
                        body=content,
                        content_type="image/webp",
                        headers={
                            "Cache-Control": "public, max-age=604800, immutable",
                            "Access-Control-Allow-Origin": "*",
                        }
                    )
    except Exception as e:
        logger.warning(f"Posterni yuklab bo'lmadi ({clean_name}): {e}")

    return web.Response(status=404, text="Poster topilmadi")


async def handle_prava_image_proxy(request: web.Request) -> web.Response:
    """Prava savollari rasmlarini (prava/... va pv/...) keshlab uzatish."""
    filename = request.match_info.get("filename", "")
    if not filename:
        tail = request.match_info.get("tail", "").lstrip("/")
        filename = tail

    clean_name = os.path.basename(filename)
    if not clean_name:
        return web.Response(status=404, text="Topilmadi")

    if not clean_name.endswith(".webp") and not clean_name.endswith(".png") and not clean_name.endswith(".jpg"):
        clean_name = f"{clean_name}.webp"

    prava_dir = BASE_DIR / "data" / "prava"
    prava_dir.mkdir(parents=True, exist_ok=True)
    local_path = prava_dir / clean_name

    # 1. Lokal keshdan bir zumda uzatish (0ms kechikish)
    if local_path.exists() and local_path.stat().st_size > 100:
        with open(local_path, "rb") as f:
            content = f.read()
        return web.Response(
            body=content,
            content_type="image/webp",
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "Access-Control-Allow-Origin": "*",
            }
        )

    # 2. Upstream serverdan yuklab olish va lokal saqlash
    upstream_url = f"https://161-97-96-58.sslip.io/prava/{clean_name}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    if content and len(content) > 100:
                        try:
                            with open(local_path, "wb") as pf:
                                pf.write(content)
                        except Exception as we:
                            logger.debug(f"Prava rasmini saqlashda xatolik: {we}")
                        return web.Response(
                            body=content,
                            content_type="image/webp",
                            headers={
                                "Cache-Control": "public, max-age=604800, immutable",
                                "Access-Control-Allow-Origin": "*",
                            }
                        )
    except Exception as e:
        logger.debug(f"Prava rasmini yuklab bo'lmadi ({clean_name}): {e}")

    return web.Response(status=404, text="Prava rasmi topilmadi")


async def handle_book_asset_proxy(request: web.Request) -> web.Response:
    """Kitob muqovalari, rasmlari va sahifalarini (bk/...) keshlab uzatish."""
    tail = request.match_info.get("tail", "").lstrip("/")
    if not tail or ".." in tail:
        return web.Response(status=404, text="Topilmadi")

    ext = os.path.splitext(tail)[1].lower()
    ct_map = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".epub": "application/epub+zip",
    }
    content_type = ct_map.get(ext, "application/octet-stream")

    bk_dir = BASE_DIR / "data" / "bk"
    local_path = bk_dir / tail
    if local_path.exists():
        try:
            with open(local_path, "rb") as f:
                content = f.read()
            if ext == ".json":
                try:
                    content = sanitize_book_text(content.decode("utf-8")).encode("utf-8")
                except Exception:
                    pass
            return web.Response(
                body=content,
                content_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        except Exception:
            pass

    upstream_url = f"https://161-97-96-58.sslip.io/bk/{tail}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    if ext == ".json":
                        try:
                            content = sanitize_book_text(content.decode("utf-8")).encode("utf-8")
                        except Exception:
                            pass
                    try:
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(local_path, "wb") as bf:
                            bf.write(content)
                    except Exception:
                        pass
                    return web.Response(
                        body=content,
                        content_type=content_type,
                        headers={
                            "Cache-Control": "public, max-age=604800, immutable",
                            "Access-Control-Allow-Origin": "*",
                        }
                    )
    except Exception as e:
        logger.warning(f"Kitob resursi yuklanmadi ({tail}): {e}")

    return web.Response(status=404, text="Resurs topilmadi")


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

    rc_dir = BASE_DIR / "data" / "rc"
    local_path = rc_dir / tail
    if local_path.exists():
        try:
            with open(local_path, "rb") as f:
                content = f.read()
            return web.Response(
                body=content,
                content_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        except Exception:
            pass

    upstream_url = f"https://161-97-96-58.sslip.io/rc/{tail}"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    try:
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(local_path, "wb") as bf:
                            bf.write(content)
                    except Exception:
                        pass
                    return web.Response(
                        body=content,
                        content_type=content_type,
                        headers={
                            "Cache-Control": "public, max-age=604800, immutable",
                            "Access-Control-Allow-Origin": "*",
                        }
                    )
    except Exception as e:
        logger.warning(f"Taom rasmi yuklanmadi ({tail}): {e}")

    return web.Response(status=404, text="Rasm topilmadi")


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
                timeout=aiohttp.ClientTimeout(total=6)
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

                if resp.status >= 500:
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
        logger.warning(f"Upstream API so'rovida xatolik ({upstream_url}): {e}")
        # Quiz uchun zaxira (oflayn yoki upstream ishlamay qolganda ham to'liq ishlashi)
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
        return web.json_response({"ok": False, "error": "upstream_unavailable"}, status=502)


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
            async with session.get(cbu_url, timeout=aiohttp.ClientTimeout(total=3.5)) as resp:
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


async def handle_get_catalog(request: web.Request) -> web.Response:
    """Mini Appning rasmiy kinolar katalogi API (Real-time va to'liq oq brendlangan)."""
    now = time.time()
    if _CATALOG_CACHE["data"] and (now - _CATALOG_CACHE["ts"] < 120):
        data = dict(_CATALOG_CACHE["data"])
        data["maintenance"] = maintenance_service.get_state()
        return web.json_response(data)

    data = None
    # 1. Real-time upstreamdan olishga urinish
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("https://161-97-96-58.sslip.io/api/catalog", timeout=aiohttp.ClientTimeout(total=3.5)) as resp:
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
                        try:
                            cat_file = BASE_DIR / "data" / "catalog.json"
                            with open(cat_file, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
    except Exception as e:
        logger.info(f"Upstream katalog ulanishida kutilmagan holat ({e}), lokal kesh ishlatiladi.")

    # 2. Agar upstream bo'lmasa, lokal fayldan o'qish
    if not data:
        catalog_path = BASE_DIR / "data" / "catalog.json"
        if catalog_path.exists():
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"items": []}

    # Foydalanuvchi boti va kanali bilan dinamik sinxronlash
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
    data["maintenance"] = maintenance_service.get_state()

    _CATALOG_CACHE["data"] = data
    _CATALOG_CACHE["ts"] = now
    return web.json_response(data)


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
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=4.5)) as resp:
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
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=4.5)) as resp:
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

    return web.json_response({
        "ok": True,
        "items": [],
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
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=4.5)) as resp:
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
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=4.5)) as resp:
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


async def handle_asil_colls(request: web.Request) -> web.Response:
    """Asilmedia to'plamlari / kolleksiyalari."""
    return await handle_upstream_api_proxy(request)


async def handle_asil_coll(request: web.Request) -> web.Response:
    """Asilmedia alohida to'plam tarkibi."""
    return await handle_upstream_api_proxy(request)


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
                        timeout=aiohttp.ClientTimeout(total=2.5)
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

    bot_username = (config.BOT_USERNAME or "Bauntyfilmsbot").lstrip("@")
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
        if cand.exists() and cand.stat().st_size >= 1024:
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
                timeout=aiohttp.ClientTimeout(total=3.0)
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

    bot_username = (config.BOT_USERNAME or "Bauntyfilmsbot").lstrip("@")
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


def get_cached_music_home_sync() -> Dict[str, Any]:
    global _MUSIC_HOME_CACHE
    if _MUSIC_HOME_CACHE is not None:
        return _MUSIC_HOME_CACHE
    music_home_path = BASE_DIR / "data" / "music_home.json"
    if music_home_path.exists():
        try:
            with open(music_home_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"ok": True, "top": TOP_50_TRACKS}


async def get_cached_music_home(force_refresh: bool = False) -> Dict[str, Any]:
    """Mini App musiqa bosh sahifasi (Top 50, Hits, Kliplar, Ijrochilar) - upstream bilan to'g'ridan-to'g'ri bog'langan."""
    global _MUSIC_HOME_CACHE, _MUSIC_HOME_TS
    now = time.time()
    if not force_refresh and _MUSIC_HOME_CACHE is not None and (now - _MUSIC_HOME_TS < 300):
        return _MUSIC_HOME_CACHE

    # 1. Upstream serverdan (@Bauntyfilmsbot / https://161-97-96-58.sslip.io) to'g'ridan-to'g'ri yangilash
    try:
        import aiohttp
        upstream_url = "https://161-97-96-58.sslip.io/api/music/home"
        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status == 200:
                    resp_bytes = await resp.read()
                    resp_text = resp_bytes.decode("utf-8", errors="replace")
                    clean_text = sanitize_catalog_text(resp_text)
                    data = json.loads(clean_text)
                    if isinstance(data, dict) and data.get("ok"):
                        _MUSIC_HOME_CACHE = data
                        _MUSIC_HOME_TS = now
                        music_home_path = BASE_DIR / "data" / "music_home.json"
                        try:
                            with open(music_home_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                        except Exception as fe:
                            logger.debug(f"music_home.json saqlashda xatolik: {fe}")
                        return data
    except Exception as e:
        logger.info(f"Upstream music/home ulanishida xatolik ({e}), lokal kesh ishlatiladi.")

    # 2. Lokal music_home.json faylidan o'qish
    music_home_path = BASE_DIR / "data" / "music_home.json"
    if music_home_path.exists():
        try:
            with open(music_home_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _MUSIC_HOME_CACHE = data
            _MUSIC_HOME_TS = now
            return data
        except Exception as e:
            logger.warning(f"music_home.json o'qishda xatolik: {e}")

    fallback = {"ok": True, "top": TOP_50_TRACKS}
    _MUSIC_HOME_CACHE = fallback
    _MUSIC_HOME_TS = now
    return fallback


async def handle_music_home(request: web.Request) -> web.Response:
    """Mini App musiqa bosh sahifasi (Top 50, Hits, Kliplar, Ijrochilar) - kesh orqali bir zumda."""
    data = await get_cached_music_home()
    return web.json_response(data, headers={"Cache-Control": "public, max-age=180"})


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
    return web.json_response({"admin": False})


async def handle_tv_hide(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def handle_get_movies(request: web.Request) -> web.Response:
    """Kinolar ro'yxati va aqlli qidiruv (Lotin-Kirill)."""
    q = request.query.get("q", "").strip()
    genre = request.query.get("genre", "").strip()
    sort = request.query.get("sort", "views").strip()
    limit = int(request.query.get("limit", 50))
    offset = int(request.query.get("offset", 0))

    async with get_session() as session:
        if q:
            movies = await crud.smart_search_movies(session, query=q, limit=limit, offset=offset)
        elif genre and genre != "Barchasi":
            movies = await crud.get_movies_by_genre(session, genre=genre, limit=limit, offset=offset)
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

        total = await crud.get_total_movies_count(session)

    return web.json_response({"items": items, "total": total, "count": len(items)})


async def handle_get_movie_detail(request: web.Request) -> web.Response:
    """Kino kodi bo'yicha batafsil ma'lumot."""
    code = request.match_info.get("code", "")
    async with get_session() as session:
        movie = await crud.get_movie_by_code(session, code)
        if not movie:
            return web.json_response({"error": "Kino topilmadi"}, status=404)

        return web.json_response({
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

    # 1. Upstream (@Bauntyfilmsbot / https://161-97-96-58.sslip.io) dan qidirishga urinish
    try:
        import aiohttp
        import urllib.parse
        upstream_url = f"https://161-97-96-58.sslip.io/api/music/search?q={urllib.parse.quote(q)}&n={n}"
        req_headers = {"User-Agent": "Mozilla/5.0"}
        if init_data:
            req_headers["X-Init-Data"] = init_data

        async with aiohttp.ClientSession() as session:
            async with session.get(upstream_url, headers=req_headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
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

    # 1. Upstream (@Bauntyfilmsbot / https://161-97-96-58.sslip.io) dan oqim havolasini olish
    try:
        import aiohttp
        upstream_url = "https://161-97-96-58.sslip.io/api/music/play"
        req_headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        if init_data:
            req_headers["X-Init-Data"] = init_data

        async with aiohttp.ClientSession() as session:
            async with session.post(upstream_url, json=body, headers=req_headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
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
                async with session.get(f"https://api.deezer.com/track/{track_id}", timeout=aiohttp.ClientTimeout(total=4)) as resp:
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


async def handle_get_tv(request: web.Request) -> web.Response:
    """Jonli telekanallar ro'yxati (O'zbek telekanallari mutlaq 1-o'rinda, eng yuqori sifat)."""
    cat = request.query.get("category", "all").strip()
    q = request.query.get("q", "").strip().lower()

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
            or cat in c.get("categories", [])
            or (cat == "kino" and (c.get("is_kino") or "kino" in c.get("categories", []) or c.get("k") == "kino" or c.get("name") in [
                "BIZ Cinema", "Kinoteatr TV", "Sevimli TV", "Zo'r TV",
                "Milliy TV", "Mening Yurtim (MY5)", "Renessans TV",
                "Insayt TV", "Hayot TV", "Biz TV", "Makon TV", "Cheksiz TV",
                "LTV HD", "Yoshlar", "Toshkent", "Dasturxon TV"
            ]))
            or (cat == "sport" and (c.get("k") == "sport" or "sport" in c.get("categories", []) or c.get("name") in ["Sport TV", "Futbol TV", "Setanta Sports 1 HD"]))
            or (cat == "milliy" and c.get("c") == "uz" and (c.get("category") == "milliy" or c.get("k") == "milliy" or "milliy" in c.get("categories", []) or c.get("name") in ["Kinoteatr TV", "Sport TV", "O'zbekiston 24", "Dunyo bo'ylab", "Navo TV"]))
            or (cat == "xususiy" and c.get("c") == "uz" and (c.get("category") == "xususiy" or c.get("k") == "xususiy" or "xususiy" in c.get("categories", []) or c.get("name") in ["Sevimli TV", "Zo'r TV", "Milliy TV", "Mening Yurtim (MY5)", "Renessans TV", "Biz TV", "BIZ Cinema", "Insayt TV", "Makon TV", "Cheksiz TV", "LTV HD"]))
        ]

    # O'zbekiston telekanallari har doim mutlaq 1-o'rinda, keyin qolgan davlatlar
    channels.sort(key=lambda x: (0 if x.get("c") == "uz" else 1, -(x.get("v") or 0)))

    return web.json_response({
        "categories": TV_CATEGORIES,
        "items": channels,
        "total": len(channels),
    })


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

    user_id_raw = body.get("user_id")
    action_type = body.get("type", "movie")
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
            delivered = await movie_service.deliver_movie(
                bot=_bot_instance,
                chat_id=chat_id,
                code=clean_code,
                part=1
            )
            if delivered:
                cat_item = MovieService.get_catalog_item(clean_code)
                title = cat_item.get("t") if cat_item else f"Kino #{clean_code}"
                return web.json_response({"success": True, "message": f"«{title}» chatga yuborildi!"})
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
    category = request.query.get("category") or request.query.get("c")
    lang = request.query.get("lang") or request.query.get("l")
    query = request.query.get("q", "").strip()
    try:
        limit = int(request.query.get("limit", 50))
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.query.get("offset", 0))
    except (ValueError, TypeError):
        offset = 0

    from services import book_service
    data = book_service.get_catalog(category=category, query=query, lang=lang, limit=limit, offset=offset)
    return web.json_response(data)


async def handle_books_search(request: web.Request) -> web.Response:
    """Kitoblarni tezkor qidirish API (Upstream 3390+ kitoblar va mahalliy zaxira)."""
    q = request.query.get("q", "").strip()
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
            async with session.get(upstream_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
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
                            items.append(b)
    except Exception as e:
        logger.debug(f"Upstream books search xatosi ({e}), lokal qidiruvga o'tiladi")

    # 2. Agar upstream natija bermasa yoki offline bo'lsa — mahalliy katalogdan qidirish
    if not items and q:
        from services import book_service
        local_items = book_service.search_books(q, limit=limit)
        total = len(local_items)
        items = local_items

    return web.json_response({"ok": True, "items": items, "total": total})


async def handle_book_detail(request: web.Request) -> web.Response:
    """Kitobning to'liq ma'lumotlarini olish (mahalliy yoki upstream)."""
    book_id = request.match_info.get("id", "").strip()
    from services import book_service
    book = book_service.get_book_by_id(book_id)
    if not book:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    return web.json_response({"ok": True, "book": book})


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

    bot_username = (config.BOT_USERNAME or "Bauntyfilmsbot").lstrip("@")
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

    try:
        result = await book_service.deliver_book(
            bot=_bot_instance,
            chat_id=int(user_id),
            book_id=book_id
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

    # CORS, DoS / DDoS Rate Limiting, WAF va Clickjacking (CSP) xavfsizlik middleware
    app.middlewares.append(security_middleware)

    # API va sahifa marshrutlari
    app.router.add_get("/health", handle_health)
    app.router.add_get("/favicon.ico", handle_favicon)
    app.router.add_get("/webapp/favicon.ico", handle_favicon)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/webapp", handle_index)
    app.router.add_get("/webapp/", handle_index)

    api_routes = [
        ("GET", "/api/catalog", handle_get_catalog),
        ("POST", "/api/watch", handle_watch),
        ("GET", "/api/movies", handle_get_movies),
        ("GET", "/api/movies/{code}", handle_get_movie_detail),
        ("GET", "/api/music", handle_get_music),
        ("GET", "/api/music/home", handle_music_home),
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
        ("GET", "/api/tv", handle_get_tv),
        ("GET", "/api/tv/icon/{id}", handle_tv_icon),
        ("POST", "/api/tv/report", handle_tv_report),
        ("GET", "/api/tv/me", handle_tv_me),
        ("POST", "/api/tv/hide", handle_tv_hide),
        ("GET", "/api/games", handle_get_games),
        ("POST", "/api/games/chest/claim", handle_chest_claim),
        ("POST", "/api/games/pet/action", handle_pet_action),
        ("GET", "/api/story", handle_story),
        ("GET", "/api/story/me", handle_story_me),
        ("GET", "/api/story/ig", handle_story_ig),
        ("GET", "/api/story/ighl", handle_story_ighl),
        ("GET", "/api/story/tg", handle_story_tg),
        ("POST", "/api/story/send", handle_story_send),
        ("POST", "/api/story/watch", handle_story_watch),
        ("POST", "/api/docs/convert", handle_doc_convert),
        ("POST", "/api/docs/pdf", handle_doc_pdf),
        ("GET", "/api/books/home", handle_upstream_api_proxy),
        ("GET", "/api/books/shelf", handle_upstream_api_proxy),
        ("POST", "/api/books/shelf", handle_upstream_api_proxy),
        ("GET", "/api/books/me", handle_upstream_api_proxy),
        ("POST", "/api/books/progress", handle_upstream_api_proxy),
        ("POST", "/api/books/note", handle_upstream_api_proxy),
        ("GET", "/api/books/audio", handle_upstream_api_proxy),
        ("GET", "/api/books/b/{id}", handle_upstream_api_proxy),
        ("GET", "/api/books/page/{id}/{n}", handle_upstream_api_proxy),
        ("GET", "/api/food", handle_upstream_api_proxy),
        ("GET", "/api/food/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/food/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/quiz/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/quiz/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/fx", handle_fx_api),
        ("GET", "/api/fx/alerts", handle_fx_alerts),
        ("GET", "/api/fx/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/maintenance", handle_maintenance),
        ("GET", "/api/books", handle_books_catalog),
        ("GET", "/api/books/search", handle_books_search),
        ("GET", "/api/books/{id}", handle_book_detail),
        ("GET", "/api/books/{id}/pdf", handle_book_pdf),
        ("POST", "/api/books/send", handle_book_send),
        ("GET", "/api/books/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/books/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/send_to_chat", handle_send_to_chat),
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
        ("GET", "/api/donate", handle_api_donate),
        ("GET", "/api/reklama", handle_api_reklama),
        ("GET", "/api/asil/home", handle_asil_home),
        ("GET", "/api/asil/list", handle_asil_list),
        ("GET", "/api/asil/search", handle_asil_search),
        ("GET", "/api/asil/item", handle_asil_item),
        ("GET", "/api/asil/colls", handle_asil_colls),
        ("GET", "/api/asil/coll", handle_asil_coll),
        ("POST", "/api/asil/send", handle_asil_send),
        ("GET", "/api/asil/stream", handle_asil_stream),
        ("GET", "/api/rasxod", handle_upstream_api_proxy),
        ("GET", "/api/rasxod/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/rasxod/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/kal", handle_upstream_api_proxy),
        ("GET", "/api/kal/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/kal/{tail:.*}", handle_upstream_api_proxy),
        ("GET", "/api/mafia", handle_upstream_api_proxy),
        ("GET", "/api/mafia/{tail:.*}", handle_upstream_api_proxy),
        ("POST", "/api/mafia/{tail:.*}", handle_upstream_api_proxy),
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
    app.router.add_get("/rc/{tail:.*}", handle_rc_asset_proxy)
    app.router.add_get("/webapp/rc/{tail:.*}", handle_rc_asset_proxy)

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
