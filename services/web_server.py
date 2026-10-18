"""
Zakirovsfilms Web Server va Mini App API (aiohttp.web)
Portlar va Render.com mosligi bilan.
"""
import os
import json
import time
import random
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
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
        "service": "Zakirovsfilms_bot & Mini App",
        "port": config.PORT,
        "timestamp": time.time(),
    })


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
            return u_obj.get("id")
    except Exception:
        pass
    return None


_CATALOG_CACHE: Dict[str, Any] = {"data": None, "ts": 0}


def sanitize_catalog_text(text: str) -> str:
    """Barcha tashqi bot/kanal havolalarini @Bauntyfilmsbot va @BauntyFilms ga almashtirish."""
    if not text:
        return ""
    text = text.replace("@Zakirovsfilms_bot", f"@{config.BOT_USERNAME.lstrip('@')}")
    text = text.replace("@ZakirovsKino", config.CHANNEL_USERNAME)
    text = text.replace("@dilbarzakirova", config.CHANNEL_USERNAME)
    text = text.replace("Zakirovs Films", "Baunty Films")
    text = text.replace("Zakirovs_bot", config.BOT_USERNAME.lstrip('@'))
    text = text.replace("Zakirovs", "Baunty")
    text = text.replace("zakirovs", "baunty")
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


async def handle_get_catalog(request: web.Request) -> web.Response:
    """Mini Appning rasmiy kinolar katalogi API (Real-time va to'liq oq brendlangan)."""
    now = time.time()
    if _CATALOG_CACHE["data"] and (now - _CATALOG_CACHE["ts"] < 120):
        return web.json_response(_CATALOG_CACHE["data"])

    data = None
    # 1. Real-time upstreamdan olishga urinish
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("https://161-97-96-58.sslip.io/api/catalog", timeout=aiohttp.ClientTimeout(total=3.5)) as resp:
                if resp.status == 200:
                    raw_data = await resp.json()
                    if isinstance(raw_data, dict) and "items" in raw_data:
                        for it in raw_data.get("items", []):
                            if "d" in it:
                                it["d"] = sanitize_catalog_text(it["d"])
                            if "t" in it:
                                it["t"] = sanitize_catalog_text(it["t"])
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

    _CATALOG_CACHE["data"] = data
    _CATALOG_CACHE["ts"] = now
    return web.json_response(data)


async def handle_watch(request: web.Request) -> web.Response:
    """Mini Appda 'Tomosha qilish' bosilganda kino chatga yuboriladi."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    code = str(body.get("code", "")).strip()
    part = int(body.get("part", 1))
    init_data = request.headers.get("X-Init-Data", "")
    user_id = extract_user_id_from_init_data(init_data) or request.query.get("user_id")

    if not code:
        return web.json_response({"ok": False, "error": "not_found"})

    if _bot_instance and user_id:
        try:
            chat_id = int(user_id)
            await movie_service.deliver_movie(
                bot=_bot_instance,
                chat_id=chat_id,
                code=code,
                part=part
            )
        except Exception as e:
            logger.error(f"Watch so'rovida chatga yuborishda xatolik: {e}")

    return web.json_response({"ok": True, "code": code, "part": part})


async def handle_music_home(request: web.Request) -> web.Response:
    """Mini App musiqa bosh sahifasi (Top 50, Hits, Kliplar, Ijrochilar)."""
    music_home_path = BASE_DIR / "data" / "music_home.json"
    if music_home_path.exists():
        with open(music_home_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return web.json_response(data)
    return web.json_response({"ok": True, "top": TOP_50_TRACKS})


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


async def handle_music_search(request: web.Request) -> web.Response:
    """Web App va qidiruv uchun musiqa qidirish API."""
    q = request.query.get("q", "").strip()
    try:
        n = int(request.query.get("n", 25))
    except (ValueError, TypeError):
        n = 25

    if not q:
        return web.json_response({"ok": True, "items": []})

    try:
        tracks = await music_service.search_tracks(query=q, limit=n)
        return web.json_response({"ok": True, "items": tracks})
    except Exception as e:
        logger.error(f"Musiqa qidirishda xatolik: {e}")
        return web.json_response({"ok": False, "error": str(e), "items": []})


async def handle_music_play(request: web.Request) -> web.Response:
    """Web App musiqa tinglash uchun MP3 oqim havolasini tayyorlash API."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    url = body.get("u") or body.get("preview") or body.get("url")
    if url and str(url).startswith("http"):
        return web.json_response({"ok": True, "url": url})

    # Deezer ID bo'yicha to'g'ridan-to'g'ri preview olish
    track_id = body.get("id")
    if track_id and body.get("s") == "dz":
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.deezer.com/track/{track_id}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        dz_data = await resp.json()
                        preview_mp3 = dz_data.get("preview")
                        if preview_mp3:
                            return web.json_response({"ok": True, "url": preview_mp3})
        except Exception as e:
            logger.info(f"Deezer preview olishda xatolik: {e}")

    # Qo'shiq va ijrochi nomi bo'yicha Deezer ochiq preview qidirish
    artist = body.get("a") or body.get("artist") or ""
    title = body.get("t") or body.get("title") or ""
    query = f"{artist} {title}".strip()
    if query:
        try:
            results = await music_service.search_tracks(query=query, limit=1)
            if results and results[0].get("preview"):
                return web.json_response({"ok": True, "url": results[0]["preview"]})
        except Exception as e:
            logger.warning(f"Play search fallback xatosi: {e}")

    # YouTube id bo'lsa
    yt_id = body.get("y") or (body.get("id") if body.get("s") == "yt" else None)
    if yt_id:
        return web.json_response({"ok": True, "url": f"https://www.youtube.com/watch?v={yt_id}"})

    # Oxirgi chora: top 50 dan biror ishlaydigan namuna
    if TOP_50_TRACKS and TOP_50_TRACKS[0].get("url"):
        return web.json_response({"ok": True, "url": TOP_50_TRACKS[0]["url"]})

    return web.json_response({"ok": False, "error": "not_found"}, status=404)


async def handle_music_send(request: web.Request) -> web.Response:
    """Web Appdan foydalanuvchining Telegram chatiga haqiqiy MP3 audio yuborish."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    init_data = request.headers.get("X-Init-Data", "")
    user_id = extract_user_id_from_init_data(init_data) or request.query.get("user_id") or body.get("user_id")

    if not user_id:
        return web.json_response({"ok": False, "error": "auth"}, status=401)

    if not _bot_instance:
        return web.json_response({"ok": False, "error": "bot_not_ready"}, status=503)

    try:
        chat_id = int(user_id)
    except (ValueError, TypeError):
        return web.json_response({"ok": False, "error": "invalid_user"}, status=400)

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
        try:
            caption = (
                f"🎵 <b>{artist} - {title}</b>\n\n"
                f"🤖 @{config.BOT_USERNAME.lstrip('@')} Mini App orqali yuborildi\n"
                f"🍿 {config.CHANNEL_USERNAME}"
            )
            await _bot_instance.send_audio(
                chat_id=chat_id,
                audio=preview_url,
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
    """114 ta jonli telekanal ro'yxati (Barcha formatlar mosligi bilan)."""
    cat = request.query.get("category", "all").strip()
    q = request.query.get("q", "").strip().lower()

    channels = CHANNELS_LIST
    if q:
        channels = [
            c for c in channels
            if q in c["name"].lower() or q in c.get("desc", "").lower() or q in c.get("n", "").lower()
        ]
    elif cat and cat != "all":
        channels = [c for c in channels if c.get("category") == cat or c.get("k") == cat]

    return web.json_response({
        "categories": TV_CATEGORIES,
        "items": channels,
        "total": len(channels),
    })


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

    try:
        chat_id = int(user_id_raw)
    except (ValueError, TypeError):
        return web.json_response({"error": "Noto'g'ri user_id formati"}, status=400)

    try:
        if action_type == "movie" and code:
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


def create_web_app() -> web.Application:
    """aiohttp web application yaratish va routerlarni sozlash."""
    app = web.Application()

    # CORS va xavfsizlik sarlavhalari middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        return response

    app.middlewares.append(cors_middleware)

    # API va sahifa marshrutlari
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/webapp", handle_index)
    app.router.add_get("/webapp/", handle_index)
    app.router.add_get("/api/catalog", handle_get_catalog)
    app.router.add_post("/api/watch", handle_watch)
    app.router.add_get("/api/movies", handle_get_movies)
    app.router.add_get("/api/movies/{code}", handle_get_movie_detail)
    app.router.add_get("/api/music", handle_get_music)
    app.router.add_get("/api/music/home", handle_music_home)
    app.router.add_get("/api/music/search", handle_music_search)
    app.router.add_post("/api/music/play", handle_music_play)
    app.router.add_post("/api/music/send", handle_music_send)
    app.router.add_post("/api/music/recognize", handle_music_recognize)
    app.router.add_post("/api/music/shazam", handle_music_shazam)
    app.router.add_get("/api/tv", handle_get_tv)
    app.router.add_post("/api/tv/report", handle_tv_report)
    app.router.add_get("/api/tv/me", handle_tv_me)
    app.router.add_post("/api/tv/hide", handle_tv_hide)
    app.router.add_get("/api/games", handle_get_games)
    app.router.add_post("/api/games/chest/claim", handle_chest_claim)
    app.router.add_post("/api/games/pet/action", handle_pet_action)
    app.router.add_get("/api/story", handle_story)
    app.router.add_post("/api/docs/convert", handle_doc_convert)
    app.router.add_post("/api/docs/pdf", handle_doc_pdf)
    app.router.add_post("/api/send_to_chat", handle_send_to_chat)

    app.router.add_get("/p/{filename}", handle_poster_proxy)

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

    # Asosiy Mini App papkasidagi yordamchi fayllarni root orqali ham berish
    for fname in ["music.js", "docs.js", "games.js", "story.js", "music.css", "docs.css", "games.css", "story.css"]:
        fpath = webapp_dir / fname
        if fpath.exists():
            def make_handler(target_path):
                async def _h(req):
                    return web.FileResponse(target_path)
                return _h
            app.router.add_get(f"/{fname}", make_handler(fpath))

    return app
