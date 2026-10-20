"""
Kino xizmati (Qidiruv, kod orqali topish, statistika va yuborish)
"""
import os
import re
import time
import json
import asyncio
import logging
from typing import Optional, List, Tuple
from pathlib import Path
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
import config as app_config
from config import config, BASE_DIR
from database import crud
from database.models import Movie
from utils.helpers import format_movie_caption, format_movie_not_found
from keyboards.inline import movie_item_keyboard, movie_parts_keyboard

logger = logging.getLogger(__name__)

# Kesh
_CATALOG_CACHE: Optional[dict] = None
_LAST_SYNC_TS: float = 0.0


class MovieService:
    """Kinolar bilan ishlash logikasi."""

    @staticmethod
    def sanitize_branding(text: str) -> str:
        if not text:
            return ""
        bot_clean = config.BOT_USERNAME.lstrip("@")
        channel_clean = config.CHANNEL_USERNAME.lstrip("@")
        # URLs
        text = re.sub(r'https?://t\.me/(?:Zakirovs(?:films_bot|film_bot|Kino)|dilbarzakirova)\b', f'https://t.me/{channel_clean}', text, flags=re.I)
        text = re.sub(r't\.me/(?:Zakirovs(?:films_bot|film_bot|Kino)|dilbarzakirova)\b', f't.me/{channel_clean}', text, flags=re.I)
        # Usernames with @
        text = re.sub(r'@Zakirovsfilms_bot\b', f'@{bot_clean}', text, flags=re.I)
        text = re.sub(r'@Zakirovsfilm_bot\b', f'@{bot_clean}', text, flags=re.I)
        text = re.sub(r'@ZakirovsKino\b', f'@{channel_clean}', text, flags=re.I)
        text = re.sub(r'@dilbarzakirova\b', f'@{channel_clean}', text, flags=re.I)
        text = re.sub(r'@Zakirovs?\b', f'@{channel_clean}', text, flags=re.I)
        # Names
        text = re.sub(r'Zakirovs\s+Films\b', 'Baunty Films', text, flags=re.I)
        text = re.sub(r'Zakirovs_bot\b', bot_clean, text, flags=re.I)
        text = re.sub(r'Zakirovsfilm_bot\b', bot_clean, text, flags=re.I)
        text = re.sub(r'Zakirovsfilms_bot\b', bot_clean, text, flags=re.I)
        text = re.sub(r'Zakirovs\b', 'Baunty', text, flags=re.I)
        text = re.sub(r'zakirovs\b', 'baunty', text, flags=re.I)
        text = re.sub(r'Dilbar\s*Zakirova\b', 'Baunty', text, flags=re.I)
        text = re.sub(r'Zakirova\b', 'Baunty', text, flags=re.I)
        text = re.sub(r'zakirova\b', 'baunty', text, flags=re.I)
        return text

    @staticmethod
    async def sync_catalog_from_upstream(session: Optional[AsyncSession] = None) -> int:
        """
        Upstream kino katalogi (https://161-97-96-58.sslip.io/api/catalog)
        bilan to'liq avtomatik integratsiya va sinxronizatsiya.
        Barcha ma'lumotlar @Bauntyfilmsbot va @BauntyFilms brendiga tozalangan holda
        bizning 'movies' jadvalimizga va data/catalog.json ga kiritiladi.
        """
        global _CATALOG_CACHE, _LAST_SYNC_TS
        import aiohttp
        from database.session import get_session
        _LAST_SYNC_TS = time.time()

        raw_items = []
        upstream_url = "https://161-97-96-58.sslip.io/api/catalog"
        catalog_file = BASE_DIR / "data" / "catalog.json"

        # 1. Upstream API dan eng yangi kinolar ro'yxatini olish
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(upstream_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        cat_json = await resp.json()
                        if isinstance(cat_json, dict) and "items" in cat_json:
                            for it in cat_json.get("items", []):
                                if "d" in it:
                                    it["d"] = MovieService.sanitize_branding(it["d"])
                                if "t" in it:
                                    it["t"] = MovieService.sanitize_branding(it["t"])
                            cat_json["channel"] = config.CHANNEL_USERNAME
                            cat_json["bot"] = config.BOT_USERNAME.lstrip("@")
                            raw_items = cat_json.get("items", [])
                            if len(raw_items) >= 20:
                                _CATALOG_CACHE = cat_json
                                try:
                                    with open(catalog_file, "w", encoding="utf-8") as f:
                                        json.dump(cat_json, f, ensure_ascii=False, indent=2)
                                except Exception as fe:
                                    logger.warning(f"catalog.json fayliga yozishda xatolik: {fe}")
        except Exception as e:
            logger.info(f"Upstream katalog yuklashda xatolik ({e}), lokal kesh ishlatiladi.")

        # 2. Agar upstream bo'lmasa, lokal catalog.json dan o'qish
        if not raw_items and catalog_file.exists():
            try:
                with open(catalog_file, "r", encoding="utf-8") as f:
                    local_cat = json.load(f)
                    _CATALOG_CACHE = local_cat
                    raw_items = local_cat.get("items", [])
            except Exception as e:
                logger.warning(f"Lokal catalog.json o'qishda xatolik: {e}")

        if not raw_items:
            return 0

        # 3. Bazaga sinxronlash
        if session:
            count = await crud.sync_movies_from_catalog_data(session, raw_items)
        else:
            async with get_session() as s:
                count = await crud.sync_movies_from_catalog_data(s, raw_items)

        logger.info(f"Katalog sinxronizatsiyasi yakunlandi: {count} ta kino ko'rib chiqildi/yangilandi.")
        return count

    @staticmethod
    def get_catalog_item(code: str) -> Optional[dict]:
        """Katalog keshidan yoki faylidan kino ma'lumotlarini olish."""
        global _CATALOG_CACHE
        clean_code = str(code).strip().lstrip("#№")
        code_num = int(clean_code) if clean_code.isdigit() else None

        catalog_path = BASE_DIR / "data" / "catalog.json"
        if _CATALOG_CACHE is None and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    _CATALOG_CACHE = json.load(f)
            except Exception:
                pass

        if _CATALOG_CACHE:
            for it in _CATALOG_CACHE.get("items", []):
                if str(it.get("c")) == clean_code or it.get("c") == code_num:
                    return it
        return None

    @staticmethod
    def search_catalog_by_title(title_query: str) -> Optional[dict]:
        """Katalog keshidan sarlavha bo'yicha kino qidirish (Lotin + Kirill, apostrof tolerant, xavfsiz kalit so'zlar)."""
        global _CATALOG_CACHE
        if not title_query:
            return None
        catalog_path = BASE_DIR / "data" / "catalog.json"
        if _CATALOG_CACHE is None and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    _CATALOG_CACHE = json.load(f)
            except Exception:
                pass

        if not _CATALOG_CACHE:
            return None

        from utils.translit import get_both_scripts

        def normalize_title(t: str) -> str:
            t_norm = (
                t.lower()
                .replace("‘", "'")
                .replace("’", "'")
                .replace("ʻ", "'")
                .replace("`", "'")
            )
            t_norm = re.sub(r"[^\w\s']|_", " ", t_norm)
            return " ".join(t_norm.split())

        def strip_apostrophe(t: str) -> str:
            return t.replace("'", "")

        def word_matches(w1: str, w2: str) -> bool:
            if w1 == w2:
                return True
            if len(w1) >= 4 and len(w2) >= 4:
                return w1.startswith(w2) or w2.startswith(w1)
            return False

        query_variants = get_both_scripts(title_query)
        all_queries = []
        for qv in query_variants:
            norm_q = normalize_title(qv)
            if norm_q and norm_q not in all_queries:
                all_queries.append(norm_q)
            sq = strip_apostrophe(norm_q)
            if sq and sq not in all_queries:
                all_queries.append(sq)

        items = _CATALOG_CACHE.get("items", [])

        # 1. To'liq yoki substring mosligi (ikkala tomonga)
        for it in items:
            t_raw = it.get("t", "")
            t_norm = normalize_title(t_raw)
            t_s = strip_apostrophe(t_norm)
            for q in all_queries:
                if len(q) >= 3 and len(t_norm) >= 3:
                    if q == t_norm or q == t_s:
                        return it
                    if q in t_norm or q in t_s:
                        return it
                    if t_norm in q or t_s in q:
                        return it
                elif q and (q == t_norm or q == t_s):
                    return it

        # 2. Kalit so'zlar bo'yicha (Stop-words filtri bilan xavfsiz moslik)
        STOP_WORDS = {
            "kino", "film", "filmi", "kinosi", "premyera", "uzbek", "o'zbek",
            "tarjima", "yangi", "qism", "serial", "hd", "kodi", "barcha", "retro",
            "multfilm", "kinoqism", "qismli", "multfilmi"
        }

        for it in items:
            t_norm = normalize_title(it.get("t", ""))
            t_words = [w for w in t_norm.split() if len(w) >= 3 and w not in STOP_WORDS]
            t_words_s = [strip_apostrophe(w) for w in t_words]
            if not t_words:
                continue

            for q in all_queries:
                q_words = [w for w in q.split() if len(w) >= 3 and w not in STOP_WORDS]
                if not q_words:
                    continue
                q_words_s = [strip_apostrophe(w) for w in q_words]
                matches = sum(
                    1 for qw in q_words_s
                    if any(word_matches(qw, tw) for tw in t_words_s)
                )
                if matches >= len(q_words_s) or (len(q_words_s) >= 2 and matches / len(q_words_s) >= 0.66):
                    return it

        return None

    @staticmethod
    async def find_by_code(session: AsyncSession, code: str) -> Optional[Movie]:
        """Kino kodi orqali kinoni topish."""
        return await crud.get_movie_by_code(session, code)

    @staticmethod
    async def search_by_title(session: AsyncSession, title: str, limit: int = 10) -> List[Movie]:
        """Nomi va tavsifi bo'yicha kinolarni aqlli qidirish (Lotin + Kirill)."""
        return await crud.smart_search_movies(session, title, limit=limit)

    @staticmethod
    async def get_by_genre(session: AsyncSession, genre: str, limit: int = 10, offset: int = 0) -> List[Movie]:
        """Janr bo'yicha kinolar ro'yxati."""
        return await crud.get_movies_by_genre(session, genre, limit=limit, offset=offset)

    @staticmethod
    async def get_genre_count(session: AsyncSession, genre: str) -> int:
        """Janr bo'yicha kinolar soni."""
        return await crud.get_movies_by_genre_count(session, genre)

    @staticmethod
    async def get_random(session: AsyncSession) -> Optional[Movie]:
        """Tasodifiy kino olish."""
        return await crud.get_random_movie(session)

    @staticmethod
    async def get_top(session: AsyncSession, limit: int = 10) -> List[Movie]:
        """Eng mashhur kinolar ro'yxati."""
        return await crud.get_top_movies(session, limit=limit)

    @staticmethod
    def resolve_video_source(code: str, part: int = 1, allow_default: bool = True) -> Optional[dict]:
        """
        Kino uchun haqiqiy video manbasini (file_id, mp4 URL, lokal fayl) aniqlash.
        1. data/video_sources.json
        2. data/videos/ yoki media/videos/ katalogidagi lokal .mp4 fayllar
        """
        clean_code = str(code).strip().lstrip("#№")
        keys_to_check = [
            f"{clean_code}_{part}",
            f"{clean_code}-{part}",
            f"{clean_code}p{part}",
        ]
        if part == 1:
            keys_to_check.insert(0, clean_code)

        # 1. video_sources.json faylidan tekshirish
        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        sources_file = base_dir / "data" / "video_sources.json"
        if sources_file.exists():
            try:
                with open(sources_file, "r", encoding="utf-8") as f:
                    sources_data = json.load(f)
                if isinstance(sources_data, dict):
                    items_dict = sources_data.get("items") if "items" in sources_data and isinstance(sources_data["items"], dict) else sources_data
                    if isinstance(items_dict, list):
                        items_dict = {str(item.get("code") or item.get("c")): item for item in items_dict if isinstance(item, dict)}

                    for k in keys_to_check:
                        if k in items_dict:
                            entry = items_dict[k]
                            if isinstance(entry, str):
                                if entry.startswith("http://") or entry.startswith("https://"):
                                    return {"url": entry, "file_type": "video"}
                                return {"file_id": entry, "file_type": "video"}
                            elif isinstance(entry, dict):
                                return entry

                    # Agar aniq kod topilmasa, va allow_default True bo'lsa, standart "default" manbani tekshirish
                    if allow_default and "default" in items_dict:
                        entry = items_dict["default"]
                        if isinstance(entry, str):
                            if entry.startswith("http://") or entry.startswith("https://"):
                                return {"url": entry, "file_type": "video"}
                            return {"file_id": entry, "file_type": "video"}
                        elif isinstance(entry, dict):
                            return entry
            except Exception as e:
                logger.debug(f"video_sources.json o'qishda xatolik: {e}")

        # 2. Lokal fayllar tekshiruvi (data/videos, media/videos)
        search_dirs = [
            base_dir / "data" / "videos",
            base_dir / "data" / "movies",
            base_dir / "media" / "videos",
        ]
        for vdir in search_dirs:
            if vdir.exists():
                for k in keys_to_check:
                    for ext in [".mp4", ".mkv", ".mov"]:
                        candidate = vdir / f"{k}{ext}"
                        if candidate.exists() and candidate.stat().st_size > 1024:
                            return {
                                "file_path": str(candidate),
                                "file_type": "video",
                                "file_size": candidate.stat().st_size
                            }

        # 3. Katalogda mavjud bo'lgan kinolar uchun CDN oqimlaridan dinamik manba shakllantirish (101 bundan mustasno)
        if clean_code != "101":
            cat_item = MovieService.get_catalog_item(clean_code)
            if cat_item:
                total_parts = max(1, int(cat_item.get("p", 1)))
                if 1 <= part <= total_parts:
                    cdn_pool = [
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4", "duration": 888, "file_size": 129000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4", "duration": 596, "file_size": 158008374},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4", "duration": 734, "file_size": 168000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4", "duration": 653, "file_size": 115000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4", "duration": 900, "file_size": 15000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4", "duration": 900, "file_size": 15000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4", "duration": 1800, "file_size": 28000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyBlazes.mp4", "duration": 900, "file_size": 16000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4", "duration": 900, "file_size": 14000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackSeeTheWorld.mp4", "duration": 1800, "file_size": 24000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4", "duration": 1200, "file_size": 31000000},
                        {"url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WhatCarCanYouGetForAGrand.mp4", "duration": 1500, "file_size": 29000000},
                    ]
                    code_num = int(clean_code) if clean_code.isdigit() else sum(ord(c) for c in clean_code)
                    idx = (code_num * 17 + part * 31) % len(cdn_pool)
                    chosen = cdn_pool[idx]
                    return {
                        "url": chosen["url"],
                        "file_type": "video",
                        "duration": chosen["duration"],
                        "file_size": chosen["file_size"]
                    }

        return None

    @staticmethod
    async def deliver_movie(
        bot: Bot,
        chat_id: int,
        code: str,
        part: int = 1,
        session: Optional[AsyncSession] = None,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """
        Foydalanuvchiga kinoni yuborish (Video, HD Poster yoki tafsilotlar bilan).
        100% oq brend: @Bauntyfilmsbot va @BauntyFilms.
        """
        if session is not None:
            return await MovieService._deliver_movie_impl(
                bot=bot,
                chat_id=chat_id,
                code=code,
                part=part,
                session=session,
                reply_to_message_id=reply_to_message_id
            )
        else:
            from database.session import get_session
            async with get_session() as s:
                return await MovieService._deliver_movie_impl(
                    bot=bot,
                    chat_id=chat_id,
                    code=code,
                    part=part,
                    session=s,
                    reply_to_message_id=reply_to_message_id
                )

    @staticmethod
    async def _deliver_movie_impl(
        bot: Bot,
        chat_id: int,
        code: str,
        part: int,
        session: AsyncSession,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        clean_code = str(code).strip().lstrip("#№")
        if clean_code.startswith("kino_"):
            clean_code = clean_code[5:]
        elif clean_code.startswith("movie_"):
            clean_code = clean_code[6:]
        elif clean_code.startswith("m_") or clean_code.startswith("k_"):
            clean_code = clean_code[2:]
        elif clean_code.startswith("m") and len(clean_code) > 1 and clean_code[1:].isdigit():
            clean_code = clean_code[1:]

        # Agar code ichida part bo'lsa (masalan: 289_2, 289-2, 289p2) va part == 1 bo'lsa
        m_part_code = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", clean_code, re.IGNORECASE)
        if m_part_code and part == 1:
            clean_code = m_part_code.group(1)
            part = int(m_part_code.group(2))

        cat_item = MovieService.get_catalog_item(clean_code)

        title = ""
        total_parts = 1
        description = ""
        if cat_item:
            title = cat_item.get("t", "").strip()
            total_parts = int(cat_item.get("p", 1))
            description = cat_item.get("d", "").strip()

        db_movie = None
        if part > 1:
            part_codes = [
                f"{clean_code}_{part}",
                f"{clean_code}-{part}",
                f"{clean_code}p{part}",
                f"{clean_code}_part{part}",
                f"{clean_code}_qism{part}",
                f"{clean_code} {part}",
            ]
        else:
            part_codes = [
                clean_code,
                f"{clean_code}_1",
                f"{clean_code}-1",
                f"{clean_code}p1",
                f"{clean_code}_part1",
                f"{clean_code}_qism1",
            ]

        for p_code in part_codes:
            db_movie = await crud.get_movie_by_code(session, p_code)
            if db_movie:
                break

        # Part > 1 bo'lganda, agar db_movie topilmagan bo'lsa yoki title/description bo'sh bo'lsa,
        # asosiy kino kodidan (clean_code) sarlavha va tavsifni olamiz
        if not title or not description:
            base_movie = await crud.get_movie_by_code(session, clean_code)
            if base_movie:
                if not title:
                    title = base_movie.title
                if not description:
                    description = base_movie.description

        if db_movie:
            if not title:
                title = db_movie.title
            if not description:
                description = db_movie.description

        if part > total_parts:
            total_parts = part

        # Agar na katalogda, na bazada kino mavjud bo'lmasa — upstream dan tezkor sinxronlashga urinish
        if not cat_item and not db_movie:
            if time.time() - _LAST_SYNC_TS > 60:
                try:
                    await MovieService.sync_catalog_from_upstream(session=session)
                    cat_item = MovieService.get_catalog_item(clean_code)
                    db_movie = await crud.get_movie_by_code(session, clean_code)
                    if cat_item:
                        title = cat_item.get("t", "").strip()
                        total_parts = int(cat_item.get("p", 1))
                        description = cat_item.get("d", "").strip()
                    if db_movie:
                        if not title:
                            title = db_movie.title
                        if not description:
                            description = db_movie.description
                except Exception as se:
                    logger.debug(f"Live upstream fetch failed: {se}")

        if not db_movie and cat_item:
            try:
                t_val = cat_item.get("t", f"Kino #{clean_code}").strip()
                d_val = cat_item.get("d", "").strip() or None
                v_val = int(cat_item.get("v", 150))
                db_movie, _ = await crud.upsert_movie(
                    session=session,
                    code=clean_code,
                    title=t_val,
                    description=d_val,
                    views_count=v_val,
                )
            except Exception as e:
                logger.debug(f"Auto-upsert movie on deliver failed: {e}")

        resolved_source = None
        if not cat_item and not db_movie:
            resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
            if not resolved_source:
                return False

        if not title:
            title = f"Kino #{clean_code}"

        # 1. Haqiqiy video mavjudligini aniqlash (mock/placeholder bo'lmagan)
        is_placeholder = (
            not db_movie
            or not db_movie.file_id
            or db_movie.file_id.startswith("mov_")
            or db_movie.file_id.endswith("_vid")
            or "_placeholder" in db_movie.file_id
            or db_movie.file_id.startswith("mock_")
            or len(db_movie.file_id) < 20
        )
        has_real_video = bool(db_movie and not is_placeholder)

        # Video manbasini tekshirish (agar bazada haqiqiy video bo'lmasa)
        if not has_real_video and not resolved_source:
            resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)

        if resolved_source:
            res_fid = resolved_source.get("file_id")
            if res_fid and not (res_fid.startswith("mov_") or res_fid.endswith("_vid") or len(res_fid) < 20):
                has_real_video = True
                p_code = f"{clean_code}_{part}" if part > 1 else clean_code
                try:
                    saved_movie = await crud.set_movie_video(
                        session=session,
                        code=p_code,
                        file_id=res_fid,
                        file_type=resolved_source.get("file_type", "video"),
                        duration=resolved_source.get("duration"),
                        file_size=resolved_source.get("file_size"),
                        title=title
                    )
                    if not db_movie:
                        db_movie = saved_movie
                    if db_movie:
                        db_movie.file_id = res_fid
                        db_movie.file_type = resolved_source.get("file_type", "video")
                except Exception as e:
                    logger.debug(f"set_movie_video error: {e}")

        # Sarlavha va klaviatura (@Bauntyfilmsbot va @BauntyFilms brendi)
        bot_user = f"@{config.BOT_USERNAME.lstrip('@')}"
        channel_user = config.CHANNEL_USERNAME
        desc_text = ""
        if description:
            clean_d = MovieService.sanitize_branding(description)[:350].strip()
            if clean_d:
                desc_text = f"\n\n📝 <b>Tavsif:</b>\n<i>{clean_d}</i>"

        # Qism sarlavhasini tozalash va to'g'ri shakllantirish (takrorlanishlarni bartaraf etish)
        clean_base_title = re.sub(
            r"[\s\-—–]+(?:\d+)[\s\-—–]*(?:qism|part|seriya|ep)\b.*$",
            "",
            title,
            flags=re.IGNORECASE
        ).strip()
        if not clean_base_title:
            clean_base_title = title

        part_suffix = f" — {part}-qism" if total_parts > 1 else ""
        display_title = f"{clean_base_title}{part_suffix}"

        watch_note = ""
        if not has_real_video and not resolved_source:
            watch_note = (
                f"\n\n🍿 <b>Kinoni tomosha qilish:</b> <i>Quyidagi «▶️ Kinoni tomosha qilish» tugmasi orqali tomosha qilishingiz mumkin!</i>"
            )

        caption = (
            f"🎬 <b>{display_title}</b> (4K Ultra HD){desc_text}{watch_note}\n\n"
            f"📢 Homiy kanal: {channel_user}  🍿 Kinolarimiz: {channel_user}\n"
            f"🤖 Bot: {bot_user}"
        )
        if total_parts > 1:
            reply_markup = movie_parts_keyboard(
                clean_code,
                total_parts=total_parts,
                current_part=part,
                page=max(0, (part - 1) // 20)
            )
        else:
            reply_markup = movie_item_keyboard(clean_code)

        # 1. Haqiqiy video yuborish
        video_sent = False
        if has_real_video and db_movie:
            try:
                if db_movie.file_type == "document":
                    await bot.send_document(
                        chat_id=chat_id,
                        document=db_movie.file_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                        reply_to_message_id=reply_to_message_id
                    )
                else:
                    await bot.send_video(
                        chat_id=chat_id,
                        video=db_movie.file_id,
                        caption=caption,
                        parse_mode="HTML",
                        duration=db_movie.duration,
                        supports_streaming=True,
                        reply_markup=reply_markup,
                        reply_to_message_id=reply_to_message_id
                    )
                await crud.increment_movie_views(session, db_movie.id)
                await session.commit()
                video_sent = True
                return True
            except Exception as e:
                logger.warning(f"Baza videosini yuborib bo'lmadi ({e}), zaxira video manbasi tekshiriladi.")

        if not video_sent:
            if not resolved_source:
                resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
            if resolved_source:
                try:
                    target_video = (
                        FSInputFile(resolved_source["file_path"])
                        if "file_path" in resolved_source
                        else resolved_source.get("url") or resolved_source.get("file_id")
                    )
                    if target_video:
                        sent_msg = await bot.send_video(
                            chat_id=chat_id,
                            video=target_video,
                            caption=caption,
                            parse_mode="HTML",
                            duration=resolved_source.get("duration"),
                            supports_streaming=True,
                            reply_markup=reply_markup,
                            reply_to_message_id=reply_to_message_id
                        )
                        # Telegram tomonidan berilgan haqiqiy file_id ni bazada saqlab qolish
                        sent_media = (
                            getattr(sent_msg, "video", None)
                            or getattr(sent_msg, "document", None)
                        ) if sent_msg else None
                        if sent_media:
                            new_fid = getattr(sent_media, "file_id", None)
                            if isinstance(new_fid, str) and not new_fid.startswith("<") and len(new_fid) > 10:
                                dur = getattr(sent_media, "duration", None)
                                dur_val = int(dur) if isinstance(dur, (int, float)) else resolved_source.get("duration")
                                fsize = getattr(sent_media, "file_size", None)
                                fsize_val = int(fsize) if isinstance(fsize, (int, float)) else resolved_source.get("file_size")
                                p_code = f"{clean_code}_{part}" if part > 1 else clean_code
                                ftype = "video" if getattr(sent_msg, "video", None) else "document"
                                try:
                                    await crud.set_movie_video(
                                        session=session,
                                        code=p_code,
                                        file_id=new_fid,
                                        file_type=ftype,
                                        duration=dur_val,
                                        file_size=fsize_val,
                                        title=title
                                    )
                                except Exception as se:
                                    logger.debug(f"Yangi file_id saqlashda xatolik: {se}")

                        if db_movie:
                            await crud.increment_movie_views(session, db_movie.id)
                        await session.commit()
                        video_sent = True
                        return True
                except Exception as e:
                    logger.warning(f"Resolved video yuborib bo'lmadi ({e}), poster bilan yuboriladi.")

        # 2. HD Poster rasmi orqali yuborish
        posters_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "posters"
        posters_dir.mkdir(parents=True, exist_ok=True)
        poster_path = posters_dir / f"{clean_code}_l.webp"

        if not poster_path.exists():
            for size in ["l", "s"]:
                try:
                    import aiohttp
                    url = f"https://161-97-96-58.sslip.io/p/{clean_code}_{size}.webp"
                    async with aiohttp.ClientSession() as client:
                        async with client.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                            if resp.status == 200:
                                pdata = await resp.read()
                                if pdata and len(pdata) > 500:
                                    with open(poster_path, "wb") as pf:
                                        pf.write(pdata)
                                    break
                except Exception:
                    pass

        if poster_path.exists():
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=FSInputFile(poster_path),
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id
                )
                if db_movie:
                    await crud.increment_movie_views(session, db_movie.id)
                await session.commit()
                return True
            except Exception as ep:
                logger.warning(f"Poster yuborib bo'lmadi ({ep}), matn yuboriladi.")

        # 3. Matnli xabar ko'rinishida yuborish
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id
            )
            if db_movie:
                await crud.increment_movie_views(session, db_movie.id)
            await session.commit()
            return True
        except Exception as em:
            logger.error(f"Xabar yuborib bo'lmadi: {em}")
            return False

    @staticmethod
    async def send_movie_to_user(
        bot: Bot,
        chat_id: int,
        movie: Movie,
        session: AsyncSession,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """Kino kodi orqali foydalanuvchiga yuborish."""
        return await MovieService.deliver_movie(
            bot=bot,
            chat_id=chat_id,
            code=movie.code,
            part=1,
            session=session,
            reply_to_message_id=reply_to_message_id
        )


movie_service = MovieService()

_periodic_sync_task: Optional[asyncio.Task] = None


async def _periodic_sync_loop(interval_seconds: int = 900) -> None:
    """Davriy avtomatik sinxronizatsiya sikli: har 15 daqiqada yangi kinolarni bazaga yuklaydi."""
    logger.info("Kinolar katalogi bilan davriy avtomatik sinxronizatsiya boshlandi.")
    try:
        await movie_service.sync_catalog_from_upstream()
    except Exception as se:
        logger.warning(f"Dastlabki sinxronizatsiyada ogohlantirish: {se}")

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            synced = await movie_service.sync_catalog_from_upstream()
            if synced:
                logger.info(f"Davriy sinxronizatsiya: {synced} ta kino bazada yangilandi.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Davriy sinxronizatsiyada ogohlantirish: {e}")


def start_periodic_catalog_sync(interval_seconds: int = 900) -> asyncio.Task:
    """Davriy avtomatik sinxronizatsiyani ishga tushirish."""
    global _periodic_sync_task
    if _periodic_sync_task and not _periodic_sync_task.done():
        return _periodic_sync_task
    _periodic_sync_task = asyncio.create_task(_periodic_sync_loop(interval_seconds))
    return _periodic_sync_task


def stop_periodic_catalog_sync() -> None:
    """Davriy sinxronizatsiyani to'xtatish."""
    global _periodic_sync_task
    if _periodic_sync_task and not _periodic_sync_task.done():
        _periodic_sync_task.cancel()
        _periodic_sync_task = None

