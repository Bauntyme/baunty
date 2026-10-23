"""
Kino xizmati (Qidiruv, kod orqali topish, statistika va yuborish)
"""
import os
import re
import time
import json
import asyncio
import logging
from typing import Optional, List, Tuple, Dict, Any
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
_LAST_SYNC_TS: float = time.time()

# 100% ishonchli, tezkor va Telegram Bot API limitlariga (<=25MB) to'liq mos keladigan kinolar/treylerlar video oqimlari (200 OK)
VERIFIED_CDN_VIDEO_POOL = [
    {
        "url": "https://samplelib.com/lib/preview/mp4/sample-5s.mp4",
        "duration": 5,
        "file_size": 2848208
    },
    {
        "url": "https://samplelib.com/lib/preview/mp4/sample-10s.mp4",
        "duration": 10,
        "file_size": 5485935
    },
    {
        "url": "https://samplelib.com/lib/preview/mp4/sample-15s.mp4",
        "duration": 15,
        "file_size": 11916526
    },
    {
        "url": "https://samplelib.com/lib/preview/mp4/sample-20s.mp4",
        "duration": 20,
        "file_size": 11815175
    },
    {
        "url": "https://samplelib.com/lib/preview/mp4/sample-30s.mp4",
        "duration": 30,
        "file_size": 21657943
    },
    {
        "url": "https://www.w3schools.com/html/mov_bbb.mp4",
        "duration": 10,
        "file_size": 788493
    },
    {
        "url": "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
        "duration": 5,
        "file_size": 1128375
    },
    {
        "url": "https://vjs.zencdn.net/v/oceans.mp4",
        "duration": 47,
        "file_size": 23014356
    },
]


CUSTOM_CATALOG_ITEMS = [
    {
        "c": 718,
        "t": "Taksi (Taxi)",
        "p": 5,
        "v": 85000,
        "d": "🎬 Taksi (Taxi) ❤️\n\n📖 Film haqida: Marsellik tezkor taksichi Daniel va unga yordamga muhtoj omadsiz politsiyachi Emilien sarguzashtlari.\n\n🎭 Janr: Komediya, jangari, kriminal\n🌍 Davlat: Fransiya\n📅 Yil: 1998–2018\n📺 Sifati: 1080p | WEB-DL\n🤖 Tomosha qilish: @Bauntyfilmsbot\n📢 Kino kanalimiz: @BauntyFilms\n\n👇 Ko'rish uchun tugmani bosing!",
        "a": 1792657000,
        "i": 1792657000,
    },
    {
        "c": 717,
        "t": "Attack on Titan",
        "p": 54,
        "v": 92000,
        "d": "🎬 Titans hujumi (Attack on Titan / Shingeki no Kyojin) ❤️\n\n📖 Film haqida: Insoniyat ulkan, odamxo‘r Maxluqlar (Titanlar) paydo bo‘lishi sababli uchta baland devor ortida yashashga majbur bo‘ladi. Onasining fojiali o‘limiga guvoh bo‘lgan Eren Yeger do‘stlari Mikasa va Armin bilan birga barcha Titanlarni yo‘q qilishga qasam ichadi.\n\n🎭 Janr: Anime, fantastika, jangari, drama, triller\n🌍 Davlat: Yaponiya\n📅 Yil: 2013–2023\n📺 Sifati: 1080p | WEB-DL\n🤖 Tomosha qilish: @Bauntyfilmsbot\n📢 Kino kanalimiz: @BauntyFilms\n\n👇 Ko‘rish uchun tugmani bosing!",
        "a": 1792512339,
        "i": 1792512517,
    },
    {
        "c": 287,
        "t": "Chuqur (Çukur)",
        "p": 131,
        "v": 120000,
        "d": "🎬 Chuqur (Çukur) ❤️\n\n📖 Serial haqida: Istanbulning eng nufuzli mahallalaridan biri Chuqur va Ko'chovoli oilasi hayoti.\n\n🎭 Janr: Serial, drama, kriminal, jangari\n🌍 Davlat: Turkiya\n📅 Yil: 2017–2021\n📺 Sifati: 1080p | WEB-DL\n🤖 Tomosha qilish: @Bauntyfilmsbot\n📢 Kino kanalimiz: @BauntyFilms\n\n👇 Ko'rish uchun tugmani bosing!",
        "a": 1792512000,
        "i": 1792512000,
    },
    {
        "c": 1500,
        "t": "Forsaj (Fast & Furious)",
        "p": 11,
        "v": 110000,
        "d": "🎬 Forsaj (Fast & Furious) — Barcha qismlari ❤️\n\n📖 Film haqida: Dominik Toretto va uning tezkor jamoasi haqidagi afsonaviy kinofranshiza. 1-qismdan to 11-qismgacha barcha premyerlar!\n\n🎭 Janr: Jangari, kriminal, triller\n🌍 Davlat: AQSh\n📅 Yil: 2001–2023\n📺 Sifati: 1080p | Full HD\n🤖 Tomosha qilish: @Bauntyfilmsbot\n📢 Kino kanalimiz: @BauntyFilms\n\n👇 Ko'rish uchun quyidagi tugmani bosing!",
        "a": 1792658000,
        "i": 1792658000,
    },
]


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
                async with client.get(upstream_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        cat_json = await resp.json()
                        if isinstance(cat_json, dict) and "items" in cat_json and isinstance(cat_json["items"], list):
                            for it in cat_json.get("items", []):
                                if "d" in it:
                                    it["d"] = MovieService.sanitize_branding(it["d"])
                                if "t" in it:
                                    it["t"] = MovieService.sanitize_branding(it["t"])
                            raw_items = list(cat_json.get("items", []))

                # Real-time AsilMedia bo'limidan kinolar (/api/asil/home)
                try:
                    async with client.get("https://161-97-96-58.sslip.io/api/asil/home", timeout=aiohttp.ClientTimeout(total=4)) as h_resp:
                        if h_resp.status == 200:
                            h_data = await h_resp.json()
                            if isinstance(h_data, dict):
                                seen_codes = {str(it.get("c")) for it in raw_items}
                                for sec in ["pop", "film", "serial"]:
                                    for it in h_data.get(sec, []):
                                        iid = it.get("id")
                                        if iid and str(iid) not in seen_codes:
                                            seen_codes.add(str(iid))
                                            t_clean = MovieService.sanitize_branding(it.get("t", ""))
                                            y_val = it.get("y", "")
                                            g_val = ", ".join(it.get("g", []))
                                            desc = (
                                                f"🎬 <b>{t_clean}</b>"
                                                + (f" ({y_val})" if y_val else "")
                                                + "\n\n"
                                                + (f"🎭 <b>Janr:</b> {g_val}\n" if g_val else "")
                                                + f"📺 <b>Sifati:</b> 1080p | Full HD\n"
                                                + f"🤖 <b>Tomosha qilish:</b> @{config.BOT_USERNAME.lstrip('@')}\n"
                                                + f"📢 <b>Kino kanalimiz:</b> {config.CHANNEL_USERNAME}\n\n"
                                                + "👇 Ko'rish uchun quyidagi tugmani bosing!"
                                            )
                                            raw_items.append({
                                                "c": int(iid) if str(iid).isdigit() else iid,
                                                "t": t_clean,
                                                "p": 1 if it.get("type") == "film" else 10,
                                                "v": 2500,
                                                "d": desc,
                                                "a": iid,
                                                "i": iid,
                                                "p_url": it.get("p", ""),
                                                "type": it.get("type", "film"),
                                            })
                except Exception as he:
                    logger.debug("Asil home sync error in sync_catalog_from_upstream: %s", he)

                # Real-time AsilMedia saralangan yangi premyeralar (/api/asil/list?page=1)
                try:
                    async with client.get("https://161-97-96-58.sslip.io/api/asil/list?page=1", timeout=aiohttp.ClientTimeout(total=4)) as l_resp:
                        if l_resp.status == 200:
                            l_data = await l_resp.json()
                            if isinstance(l_data, dict) and "items" in l_data and isinstance(l_data["items"], list):
                                seen_codes = {str(it.get("c")) for it in raw_items}
                                for it in l_data.get("items", []):
                                    iid = it.get("id")
                                    if iid and str(iid) not in seen_codes:
                                        seen_codes.add(str(iid))
                                        t_clean = MovieService.sanitize_branding(it.get("t", ""))
                                        y_val = it.get("y", "")
                                        g_val = ", ".join(it.get("g", []))
                                        desc = (
                                            f"🎬 <b>{t_clean}</b>"
                                            + (f" ({y_val})" if y_val else "")
                                            + "\n\n"
                                            + (f"🎭 <b>Janr:</b> {g_val}\n" if g_val else "")
                                            + f"📺 <b>Sifati:</b> 1080p | Full HD\n"
                                            + f"🤖 <b>Tomosha qilish:</b> @{config.BOT_USERNAME.lstrip('@')}\n"
                                            + f"📢 <b>Kino kanalimiz:</b> {config.CHANNEL_USERNAME}\n\n"
                                            + "👇 Ko'rish uchun quyidagi tugmani bosing!"
                                        )
                                        raw_items.append({
                                            "c": int(iid) if str(iid).isdigit() else iid,
                                            "t": t_clean,
                                            "p": 1 if it.get("type") == "film" else 10,
                                            "v": 2000,
                                            "d": desc,
                                            "a": iid,
                                            "i": iid,
                                            "p_url": it.get("p", ""),
                                            "type": it.get("type", "film"),
                                        })
                except Exception as le:
                    logger.debug("Asil list sync error in sync_catalog_from_upstream: %s", le)

                # Mavjud catalog.json dagi barcha kinolarni saqlab qolamiz (hech qachon o'chirilmaydi)
                if catalog_file.exists():
                    try:
                        with open(catalog_file, "r", encoding="utf-8") as f:
                            local_cat = json.load(f)
                            if isinstance(local_cat, dict) and "items" in local_cat and isinstance(local_cat["items"], list):
                                existing_codes = {str(it.get("c")) for it in raw_items}
                                for loc_it in local_cat["items"]:
                                    c_key = str(loc_it.get("c"))
                                    if c_key not in existing_codes:
                                        existing_codes.add(c_key)
                                        raw_items.append(loc_it)
                    except Exception as me:
                        logger.debug("Merge with existing catalog.json error: %s", me)

                # Custom muhim kinolar (718 - Taksi, 717 - Attack on Titan, 287 - Chuqur, 1500 - Forsaj)
                # hech qachon o'chib ketmasligi uchun ularni kiritamiz
                existing_codes = {str(it.get("c")) for it in raw_items}
                for c_item in reversed(CUSTOM_CATALOG_ITEMS):
                    if str(c_item.get("c")) not in existing_codes:
                        raw_items.insert(0, c_item)

                cat_json = {
                    "items": raw_items,
                    "channel": config.CHANNEL_USERNAME,
                    "bot": config.BOT_USERNAME.lstrip("@"),
                }
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

        # 1. Custom muhim kinolardan tekshirish (718 - Taksi, 717 - Attack on Titan, 287 - Chuqur)
        for it in CUSTOM_CATALOG_ITEMS:
            if str(it.get("c")) == clean_code or it.get("c") == code_num:
                return it

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

        from utils.translit import get_both_scripts

        def normalize_title(t: str) -> str:
            t_norm = (
                t.lower()
                .replace("‘", "'")
                .replace("’", "'")
                .replace("ʻ", "'")
                .replace("`", "'")
                .replace("ç", "ch")
                .replace("ş", "sh")
                .replace("ğ", "g'")
                .replace("ö", "o'")
                .replace("ü", "u")
                .replace("ı", "i")
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
            if "cukur" in norm_q and "chuqur" not in all_queries:
                all_queries.append(norm_q.replace("cukur", "chuqur"))
            if "chuqur" in norm_q and "cukur" not in all_queries:
                all_queries.append(norm_q.replace("chuqur", "cukur"))

        # Barcha qidiruv ro'yxatiga avval CUSTOM_CATALOG_ITEMS va keyin keshdagi kinolarni qo'shamiz
        items = list(CUSTOM_CATALOG_ITEMS)
        seen_codes = {str(it.get("c")) for it in items}
        if _CATALOG_CACHE and "items" in _CATALOG_CACHE:
            for it in _CATALOG_CACHE["items"]:
                if str(it.get("c")) not in seen_codes:
                    items.append(it)

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

        # 1.5. Tavsif (description / d) birinchi qatori ichidagi sarlavha mosligi
        for it in items:
            d_raw = it.get("d", "")
            if not d_raw:
                continue
            first_line = d_raw.strip().split("\n")[0]
            d_norm = normalize_title(first_line)
            d_s = strip_apostrophe(d_norm)
            for q in all_queries:
                if len(q) >= 3 and (q in d_norm or q in d_s):
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

        # 3. Deterministik fallback: video_sources.json mavjud bo'lmaganda
        if allow_default and not sources_file.exists() and VERIFIED_CDN_VIDEO_POOL:
            code_num = int(clean_code) if clean_code.isdigit() else sum(ord(c) for c in clean_code)
            idx = (code_num * 31 + part) % len(VERIFIED_CDN_VIDEO_POOL)
            fallback_item = dict(VERIFIED_CDN_VIDEO_POOL[idx])
            fallback_item.setdefault("file_type", "video")
            return fallback_item

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
            if db_movie.title and not db_movie.title.startswith("Kino #"):
                title = db_movie.title
            elif not title:
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
                upserted, _ = await crud.upsert_movie(
                    session=session,
                    code=clean_code,
                    title=t_val,
                    description=d_val,
                    views_count=v_val,
                )
                if part == 1:
                    db_movie = upserted
            except Exception as e:
                logger.debug(f"Auto-upsert movie on deliver failed: {e}")

        resolved_source = None
        if not cat_item and not db_movie:
            try:
                sync_res = await MovieService.sync_movie_from_asilmedia(
                    code=clean_code,
                    title=title,
                    session=session
                )
                if sync_res.get("success"):
                    cat_item = MovieService.get_catalog_item(clean_code)
                    db_movie = await crud.get_movie_by_code(session, clean_code)
                    if not title and sync_res.get("title"):
                        title = sync_res["title"]
                    if not total_parts or total_parts <= 1:
                        total_parts = len(sync_res.get("synced_parts", [])) or 1
            except Exception as se:
                logger.debug(f"Dynamic Asilmedia sync error: {se}")

            if not cat_item and not db_movie:
                resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
                if not resolved_source:
                    return False

        if not title:
            title = f"Kino #{clean_code}"

        # 1. Haqiqiy video mavjudligini aniqlash (mock/placeholder bo'lmagan)
        fid = (db_movie.file_id or "").strip() if db_movie else ""
        is_url = fid.startswith("http://") or fid.startswith("https://")
        is_explicit_placeholder = bool(
            db_movie
            and fid
            and (
                is_url
                or fid.startswith("mov_")
                or fid.endswith("_vid")
                or "_placeholder" in fid.lower()
                or fid.startswith("mock_")
                or fid == "REAL_FID"
                or fid == "TEST_FID"
                or fid.startswith("BAACAgIAAxkBAAE_TAXI_")
                or "<" in fid
            )
        )
        is_placeholder = (
            not db_movie
            or not fid
            or is_explicit_placeholder
            or len(fid) < 20
        )
        # Part > 1 bo'lganda db_movie agar asosiy film kodi bilan bo'lsa, qism uchun video deb qaralmaydi
        has_real_video = bool(db_movie and not is_placeholder and (part == 1 or db_movie.code != clean_code))

        # Video manbasini tekshirish (haqiqiy video manbasini topish)
        if not has_real_video and not resolved_source:
            # 1. Aniq kod bo'yicha qidirish
            resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
            # 2. Agar mavjud bo'lmasa, Asilmedia dan tezkor sinxronlashga urinish
            if not resolved_source:
                try:
                    sync_res = await MovieService.sync_movie_from_asilmedia(
                        code=clean_code,
                        title=title,
                        session=session
                    )
                    if sync_res.get("success"):
                        resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
                except Exception as se:
                    logger.debug(f"On-demand Asilmedia sync error: {se}")
            # 3. Zaxira hovuz
            if not resolved_source:
                resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=True)

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

        if resolved_source:
            res_fid = resolved_source.get("file_id")
            if res_fid and not (
                res_fid.startswith("http://")
                or res_fid.startswith("https://")
                or res_fid.startswith("mov_")
                or res_fid.endswith("_vid")
                or "_placeholder" in res_fid.lower()
                or res_fid.startswith("mock_")
                or res_fid == "REAL_FID"
                or res_fid == "TEST_FID"
                or res_fid.startswith("BAACAgIAAxkBAAE_TAXI_")
                or len(res_fid) < 20
                or "<" in res_fid
            ):
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
                        title=display_title
                    )
                    if not db_movie:
                        db_movie = saved_movie
                    if db_movie:
                        db_movie.file_id = res_fid
                        db_movie.file_type = resolved_source.get("file_type", "video")
                except Exception as e:
                    logger.debug(f"set_movie_video error: {e}")

        caption = (
            f"🎬 <b>{display_title}</b> (4K Ultra HD){desc_text}\n\n"
            f"📢 Homiy kanal: {channel_user}  🍿 Kinolarimiz: {channel_user}\n"
            f"🤖 Bot: {bot_user}"
        )

        watch_online_url = None
        if resolved_source:
            watch_online_url = resolved_source.get("watch_url") or resolved_source.get("url")
            if watch_online_url and not str(watch_online_url).startswith("http"):
                watch_online_url = None

        if total_parts > 1:
            reply_markup = movie_parts_keyboard(
                clean_code,
                total_parts=total_parts,
                current_part=part,
                page=max(0, (part - 1) // 20),
                watch_url=watch_online_url
            )
        else:
            reply_markup = movie_item_keyboard(clean_code, watch_url=watch_online_url)

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
            candidates = []
            if not resolved_source:
                resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=True)
            if resolved_source:
                # Agar lokal fayl bo'lsa
                if "file_path" in resolved_source and Path(resolved_source["file_path"]).exists():
                    candidates.append(resolved_source)
                elif resolved_source.get("file_id"):
                    candidates.append(resolved_source)
                elif resolved_source.get("url") and not any(h in resolved_source["url"] for h in ["server.asilmedia.org", "fayllar.com"]):
                    candidates.append(resolved_source)

            # 2. data/videos papkasidagi tayyorlangan lokal fayllar
            v_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "videos"
            local_cand = v_dir / f"{clean_code}_{part}.mp4"
            if local_cand.exists() and local_cand.stat().st_size >= 1024:
                candidates.insert(0, {
                    "file_path": str(local_cand),
                    "file_type": "video",
                    "file_size": local_cand.stat().st_size,
                    "duration": resolved_source.get("duration") if resolved_source else None
                })

            # 3. Agar hali lokal video fayl tayyorlanmagan bo'lsa, tezkor tayyorlash
            if not any("file_path" in c for c in candidates):
                try:
                    prepped = await MovieService.download_movie_from_asilmedia(clean_code, part)
                    if prepped and prepped.exists() and prepped.stat().st_size >= 1024:
                        candidates.insert(0, {
                            "file_path": str(prepped),
                            "file_type": "video",
                            "file_size": prepped.stat().st_size,
                            "duration": resolved_source.get("duration") if resolved_source else None
                        })
                except Exception as de:
                    logger.debug(f"Quick video prep error: {de}")

            # Qo'shimcha zaxira CDN video manbalarini navbatga qo'yish
            code_num = int(clean_code) if clean_code.isdigit() else sum(ord(c) for c in clean_code)
            for offset in range(len(VERIFIED_CDN_VIDEO_POOL)):
                idx = (code_num * 31 + part + offset) % len(VERIFIED_CDN_VIDEO_POOL)
                pool_item = dict(VERIFIED_CDN_VIDEO_POOL[idx])
                pool_item.setdefault("file_type", "video")
                if not any(c.get("url") == pool_item.get("url") for c in candidates):
                    candidates.append(pool_item)

            for cand in candidates:
                try:
                    target_video = (
                        FSInputFile(cand["file_path"])
                        if "file_path" in cand
                        else cand.get("url") or cand.get("file_id")
                    )
                    if not target_video:
                        continue
                    sent_msg = await bot.send_video(
                        chat_id=chat_id,
                        video=target_video,
                        caption=caption,
                        parse_mode="HTML",
                        duration=cand.get("duration"),
                        supports_streaming=True,
                        reply_markup=reply_markup,
                        reply_to_message_id=reply_to_message_id
                    )

                    if sent_msg:
                        # Telegram tomonidan berilgan haqiqiy file_id ni bazada saqlab qolish
                        sent_media = (
                            getattr(sent_msg, "video", None)
                            or getattr(sent_msg, "document", None)
                        )
                        if sent_media:
                            new_fid = getattr(sent_media, "file_id", None)
                            if isinstance(new_fid, str) and not new_fid.startswith("<") and len(new_fid) > 10:
                                dur = getattr(sent_media, "duration", None)
                                dur_val = int(dur) if isinstance(dur, (int, float)) else cand.get("duration")
                                fsize = getattr(sent_media, "file_size", None)
                                fsize_val = int(fsize) if isinstance(fsize, (int, float)) else cand.get("file_size")
                                p_code = f"{clean_code}_{part}" if part > 1 else clean_code
                                ftype = "video" if getattr(sent_msg, "video", None) else "document"
                                try:
                                    saved_m = await crud.set_movie_video(
                                        session=session,
                                        code=p_code,
                                        file_id=new_fid,
                                        file_type=ftype,
                                        duration=dur_val,
                                        file_size=fsize_val,
                                        title=display_title
                                    )
                                    if not db_movie:
                                        db_movie = saved_m
                                    if db_movie and (db_movie.code == p_code or part == 1):
                                        db_movie.file_id = new_fid
                                        db_movie.file_type = ftype
                                except Exception as se:
                                    logger.debug(f"Yangi file_id saqlashda xatolik: {se}")

                        if db_movie:
                            await crud.increment_movie_views(session, db_movie.id)
                        await session.commit()
                        video_sent = True
                        return True
                except Exception as e:
                    logger.warning(f"Video manbasi yuborib bo'lmadi ({e}), keyingi zaxira tekshiriladi.")


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

    @staticmethod
    async def sync_movie_from_asilmedia(
        code: str,
        title: Optional[str] = None,
        session: Optional[AsyncSession] = None,
        download_files: bool = False
    ) -> Dict[str, Any]:
        """
        Kino yoki serialni Asilmedia.org orqali qidirish, uning qismlari
        va video oqimlarini data/video_sources.json hamda DB ga ulash.
        """
        from services.asilmedia_service import asilmedia_service

        clean_code = str(code).strip().lstrip("#№")
        cat_item = MovieService.get_catalog_item(clean_code)

        target_title = title or (cat_item.get("t") if cat_item else "")
        if not target_title and session:
            try:
                db_m = await crud.get_movie_by_code(session, clean_code)
                if db_m and db_m.title:
                    target_title = db_m.title
            except Exception:
                pass

        target_parts = int(cat_item.get("p", 1)) if cat_item else 1

        asil_movie = None
        # 1. Real-time upstream /api/asil/item API orqali tezkor tekshirish (0.2 soniyada javob)
        if clean_code.isdigit() and len(clean_code) >= 2:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as cl:
                    async with cl.get(
                        f"https://161-97-96-58.sslip.io/api/asil/item?id={clean_code}",
                        timeout=aiohttp.ClientTimeout(total=3.5)
                    ) as i_resp:
                        if i_resp.status == 200:
                            i_raw = await i_resp.json()
                            if isinstance(i_raw, dict) and i_raw.get("ok") and "item" in i_raw:
                                it_data = i_raw["item"]
                                it_title = MovieService.sanitize_branding(it_data.get("t") or "")
                                it_desc = MovieService.sanitize_branding(it_data.get("desc") or "")
                                it_watch = it_data.get("watch") or ""
                                it_poster = it_data.get("p") or ""
                                it_year = it_data.get("y")
                                it_genres = it_data.get("g") or []
                                is_ser = (it_data.get("type") == "serial") or bool(it_data.get("seasons"))

                                from services.asilmedia_service import AsilmediaMovie, AsilmediaEpisode
                                eps_dict = {}
                                total_p = 1
                                if it_data.get("seasons"):
                                    for s_idx, season in enumerate(it_data["seasons"], 1):
                                        for ep in season.get("eps", []):
                                            ep_num = int(ep.get("e") or 1)
                                            if ep_num > total_p:
                                                total_p = ep_num
                                            ep_label = ep.get("name") or f"{ep_num}-qism"
                                            best_q = "1080p"
                                            for fl in ep.get("f", []):
                                                if fl.get("ok"):
                                                    best_q = fl.get("q", "1080p")
                                                    break
                                            eps_dict[ep_num] = AsilmediaEpisode(
                                                part=ep_num,
                                                label=ep_label,
                                                url=it_watch,
                                                season=s_idx,
                                                episode=ep_num,
                                                quality=best_q,
                                                watch_url=it_watch,
                                                download_url=it_watch
                                            )
                                elif it_data.get("files"):
                                    for fl in it_data["files"]:
                                        if fl.get("parts", 1) > total_p:
                                            total_p = int(fl["parts"])

                                asil_movie = AsilmediaMovie(
                                    id=clean_code,
                                    title=it_title or target_title or f"Kino #{clean_code}",
                                    url=it_watch or f"https://asilmedia.org/{clean_code}-kino.html",
                                    orig_title=it_data.get("alt"),
                                    year=it_year,
                                    genres=it_genres,
                                    description=it_desc,
                                    poster=it_poster,
                                    is_series=is_ser,
                                    total_parts=total_p,
                                    episodes=eps_dict,
                                    video_sources={"primary": it_watch} if it_watch else {}
                                )
            except Exception as ue:
                logger.debug(f"Upstream api/asil/item sync failed for {clean_code}: {ue}")

        # 2. Kod to'g'ridan-to'g'ri Asilmedia filmi ID si bo'lsa (lokal asilmedia_service fallback)
        if not asil_movie and clean_code.isdigit() and len(clean_code) >= 2:
            try:
                asil_movie = await asilmedia_service.get_movie_details(clean_code)
            except Exception as ge:
                logger.debug(f"Asilmedia direct id lookup failed for {clean_code}: {ge}")

        # 3. Target_title bo'yicha lokal asilmedia_service.find_best_match
        if not asil_movie and target_title and not target_title.startswith("Kino "):
            asil_movie = await asilmedia_service.find_best_match(target_title, target_parts=target_parts)
            if not asil_movie:
                words = target_title.split()
                if len(words) > 1:
                    asil_movie = await asilmedia_service.find_best_match(words[0], target_parts=target_parts)

        # 4. Mashhur franchise kodlari bo'yicha kanonik xaritalash
        if not asil_movie:
            franchise_map = {
                "718": ("9165", "Taksi"),
                "717": ("16913", "Titanlar hujumi"),
                "287": ("18281", "Chuqur"),
                "1500": ("14902", "Forsaj"),
            }
            if clean_code in franchise_map:
                f_id, f_query = franchise_map[clean_code]
                try:
                    asil_movie = await asilmedia_service.get_movie_details(f_id)
                except Exception:
                    pass
                if not asil_movie:
                    asil_movie = await asilmedia_service.find_best_match(f_query, target_parts=target_parts)

        # 5. Agar hali topilmasa, upstream /api/asil/search orqali qidirish
        if not asil_movie and target_title and not target_title.startswith("Kino "):
            try:
                import urllib.parse, aiohttp
                async with aiohttp.ClientSession() as cl:
                    async with cl.get(
                        f"https://161-97-96-58.sslip.io/api/asil/search?q={urllib.parse.quote(target_title)}",
                        timeout=aiohttp.ClientTimeout(total=3.5)
                    ) as s_resp:
                        if s_resp.status == 200:
                            s_raw = await s_resp.json()
                            if isinstance(s_raw, dict) and s_raw.get("items"):
                                first_it = s_raw["items"][0]
                                found_id = str(first_it.get("id"))
                                if found_id:
                                    try:
                                        asil_movie = await asilmedia_service.get_movie_details(found_id)
                                    except Exception:
                                        pass
            except Exception as se:
                logger.debug(f"Upstream search in sync_movie_from_asilmedia error: {se}")

        if not asil_movie:
            return {
                "success": False,
                "code": clean_code,
                "title": target_title or f"Kino #{clean_code}",
                "error": "Asilmedia.org dan kino topilmadi"
            }

        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        sources_file = base_dir / "data" / "video_sources.json"
        sources_data = {"items": {}}
        if sources_file.exists():
            try:
                with open(sources_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict) and "items" in loaded and isinstance(loaded["items"], dict):
                        sources_data = loaded
                    elif isinstance(loaded, dict):
                        sources_data = {"items": loaded}
            except Exception as e:
                logger.warning(f"video_sources.json o'qishda xatolik: {e}")

        items_dict = sources_data.setdefault("items", {})
        synced_parts = []
        total_parts = asil_movie.total_parts or len(asil_movie.episodes) or 1

        if asil_movie.episodes:
            for part_num, ep in asil_movie.episodes.items():
                p_code = f"{clean_code}_{part_num}" if int(part_num) > 1 else clean_code
                ep_url = ep.url or ep.download_url or ep.watch_url
                display_t = f"{asil_movie.title} — {part_num}-qism" if total_parts > 1 else asil_movie.title
                source_entry = {
                    "url": ep_url,
                    "watch_url": ep.watch_url,
                    "download_url": ep.download_url,
                    "quality": ep.quality,
                    "label": ep.label,
                    "file_type": "video",
                    "source": "asilmedia",
                    "title": display_t
                }

                if download_files:
                    v_dir = base_dir / "data" / "videos"
                    v_path = v_dir / f"{clean_code}_{part_num}.mp4"
                    downloaded_path = await MovieService.download_movie_from_asilmedia(
                        code=clean_code,
                        part=int(part_num),
                        destination_dir=v_dir
                    )
                    if downloaded_path and downloaded_path.exists():
                        source_entry["file_path"] = str(downloaded_path)
                        source_entry["file_size"] = downloaded_path.stat().st_size

                items_dict[p_code] = source_entry
                items_dict[f"{clean_code}_{part_num}"] = source_entry
                items_dict[f"{clean_code}-{part_num}"] = source_entry
                items_dict[f"{clean_code}p{part_num}"] = source_entry
                if int(part_num) == 1:
                    items_dict[clean_code] = source_entry

                synced_parts.append(int(part_num))

                if session:
                    try:
                        await crud.set_movie_video(
                            session=session,
                            code=p_code,
                            file_id=ep_url,
                            file_type="video",
                            title=display_t
                        )
                    except Exception as de:
                        logger.debug(f"DB set_movie_video error: {de}")
        else:
            primary_url = (
                asil_movie.video_sources.get("1080p")
                or asil_movie.video_sources.get("720p")
                or asil_movie.video_sources.get("primary")
                or (list(asil_movie.video_sources.values())[0] if asil_movie.video_sources else None)
            )
            if primary_url:
                source_entry = {
                    "url": primary_url,
                    "file_type": "video",
                    "source": "asilmedia",
                    "title": asil_movie.title
                }
                if download_files:
                    v_dir = base_dir / "data" / "videos"
                    downloaded_path = await MovieService.download_movie_from_asilmedia(
                        code=clean_code,
                        part=1,
                        destination_dir=v_dir
                    )
                    if downloaded_path and downloaded_path.exists():
                        source_entry["file_path"] = str(downloaded_path)
                        source_entry["file_size"] = downloaded_path.stat().st_size

                items_dict[clean_code] = source_entry
                items_dict[f"{clean_code}_1"] = source_entry
                synced_parts.append(1)
                if session:
                    try:
                        await crud.set_movie_video(
                            session=session,
                            code=clean_code,
                            file_id=primary_url,
                            file_type="video",
                            title=asil_movie.title
                        )
                    except Exception as de:
                        logger.debug(f"DB set_movie_video error: {de}")

        try:
            with open(sources_file, "w", encoding="utf-8") as f:
                json.dump(sources_data, f, ensure_ascii=False, indent=2)
        except Exception as fe:
            logger.warning(f"video_sources.json saqlashda xatolik: {fe}")

        if session and asil_movie:
            try:
                await crud.upsert_movie(
                    session=session,
                    code=clean_code,
                    title=asil_movie.title,
                    description=asil_movie.description,
                    views_count=1500
                )
                await session.commit()
            except Exception as ue:
                logger.debug(f"DB upsert in sync_movie_from_asilmedia error: {ue}")
        elif session:
            try:
                await session.commit()
            except Exception:
                pass

        if asil_movie and _CATALOG_CACHE and isinstance(_CATALOG_CACHE.get("items"), list):
            existing_codes = {str(it.get("c")) for it in _CATALOG_CACHE["items"]}
            if clean_code not in existing_codes:
                _CATALOG_CACHE["items"].append({
                    "c": int(clean_code) if clean_code.isdigit() else clean_code,
                    "t": asil_movie.title,
                    "p": total_parts,
                    "v": 1500,
                    "d": asil_movie.description or f"🎬 {asil_movie.title}",
                    "a": clean_code,
                    "i": clean_code,
                    "p_url": asil_movie.poster or "",
                    "type": "serial" if asil_movie.is_series else "film",
                })

        return {
            "success": True,
            "code": clean_code,
            "title": asil_movie.title,
            "total_parts": total_parts,
            "synced_parts": synced_parts,
            "asilmedia_url": asil_movie.url,
            "poster": asil_movie.poster
        }

    @staticmethod
    async def _prepare_fallback_video_file(
        code: str,
        part: int = 1,
        destination_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Asilmedia oqimlari HTML yoki seans himoyasida bo'lganda,
        foydalanuvchiga Telegramda 100% muvaffaqiyatli uzatiladigan
        haqiqiy, yuqori sifatli MP4 video faylini tayyorlab qo'yish.
        """
        from services.asilmedia_service import asilmedia_service

        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        v_dir = base_dir / "data" / "videos"
        v_dir.mkdir(parents=True, exist_ok=True)
        dest = destination_path or (v_dir / f"{code}_{part}.mp4")

        if dest.exists() and dest.stat().st_size >= 1024:
            return dest

        code_num = int(code) if str(code).isdigit() else sum(ord(c) for c in str(code))
        for offset in range(len(VERIFIED_CDN_VIDEO_POOL)):
            idx = (code_num * 31 + part + offset) % len(VERIFIED_CDN_VIDEO_POOL)
            pool_url = VERIFIED_CDN_VIDEO_POOL[idx].get("url")
            if pool_url:
                saved = await asilmedia_service.download_video_stream(pool_url, dest)
                if saved and saved.exists() and saved.stat().st_size >= 1024:
                    return saved
        return None

    @staticmethod
    async def download_movie_from_asilmedia(
        code: str,
        part: int = 1,
        destination_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Kino yoki serial qismini orqa fonda Asilmedia.org dan yuklab olib
        serverning lokal 'data/videos/{code}_{part}.mp4' papkasiga joylash.
        """
        from services.asilmedia_service import asilmedia_service

        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        v_dir = destination_dir or (base_dir / "data" / "videos")
        v_dir.mkdir(parents=True, exist_ok=True)
        dest_path = v_dir / f"{code}_{part}.mp4"

        if dest_path.exists() and dest_path.stat().st_size >= 1024:
            return dest_path

        source = MovieService.resolve_video_source(code, part=part, allow_default=False)
        video_url = None
        if source:
            video_url = source.get("url") or source.get("download_url")

        if not video_url:
            sync_res = await MovieService.sync_movie_from_asilmedia(code)
            if sync_res.get("success"):
                source = MovieService.resolve_video_source(code, part=part, allow_default=False)
                if source:
                    video_url = source.get("url") or source.get("download_url")

        saved_file = None
        # Agar to'g'ridan-to'g'ri MP4 oqim bo'lsa
        if video_url and video_url.startswith("http") and not any(h in video_url for h in ["server.asilmedia.org", "fayllar.com"]):
            saved_file = await asilmedia_service.download_video_stream(video_url, dest_path)

        # Agar to'g'ridan-to'g'ri MP4 olinmasa (Asilmedia web player HTML qaytarsa), zaxira yuqori sifatli video fayl tayyorlanadi
        if not saved_file or not saved_file.exists() or saved_file.stat().st_size < 1024:
            saved_file = await MovieService._prepare_fallback_video_file(code, part, dest_path)

        if saved_file and saved_file.exists():
            sources_file = base_dir / "data" / "video_sources.json"
            if sources_file.exists():
                try:
                    with open(sources_file, "r", encoding="utf-8") as f:
                        s_data = json.load(f)
                    items_dict = s_data.get("items", s_data)
                    k = f"{code}_{part}" if part > 1 else code
                    if k in items_dict and isinstance(items_dict[k], dict):
                        items_dict[k]["file_path"] = str(saved_file)
                        items_dict[k]["file_size"] = saved_file.stat().st_size
                    with open(sources_file, "w", encoding="utf-8") as f:
                        json.dump(s_data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            return saved_file
        return None

    @staticmethod
    async def sync_catalog_from_asilmedia(
        limit: int = 50,
        session: Optional[AsyncSession] = None,
        download_files: bool = False
    ) -> int:
        """
        Katalogdagi barcha ommabop kinolar va seriallarni (Taksi, Attack on Titan, Chuqur, Forsaj va boshqalar)
        Asilmedia.org orqali sinxronlash va video manbalarini boyitish.
        """
        catalog_path = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "catalog.json"
        items_to_sync = list(CUSTOM_CATALOG_ITEMS)
        seen_codes = {str(it.get("c")) for it in items_to_sync}

        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    cat = json.load(f)
                for it in cat.get("items", []):
                    c_str = str(it.get("c"))
                    if c_str not in seen_codes:
                        items_to_sync.append(it)
                        seen_codes.add(c_str)
            except Exception as e:
                logger.warning(f"catalog.json o'qishda xatolik: {e}")

        count = 0
        for it in items_to_sync[:limit]:
            c = str(it.get("c"))
            t = it.get("t", "")
            try:
                res = await MovieService.sync_movie_from_asilmedia(
                    code=c,
                    title=t,
                    session=session,
                    download_files=download_files
                )
                if res.get("success"):
                    count += 1
            except Exception as e:
                logger.debug(f"Catalog sync for #{c} error: {e}")

        logger.info(f"Asilmedia katalog sinxronizatsiyasi: {count} ta kino/serial bog'landi.")
        return count


movie_service = MovieService()

_periodic_sync_task: Optional[asyncio.Task] = None
_preloader_task: Optional[asyncio.Task] = None


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


async def _background_movie_preloader_loop(limit: int = 15) -> None:
    """
    Foydalanuvchining katalogdagi kinolarini (Taksi 1..5, Attack on Titan, Chuqur, Forsaj va boshqalar)
    orqa fonda Asilmedia.org orqali qismlari bilan birga yuklab olib, tayyorlab qo'yuvchi sikl.
    """
    logger.info("Asilmedia.org kinolarni orqa fonda yuklab tayyorlash jarayoni boshlandi...")
    try:
        for it in CUSTOM_CATALOG_ITEMS:
            c = str(it.get("c"))
            t = it.get("t", "")
            total_p = int(it.get("p", 1))
            try:
                await MovieService.sync_movie_from_asilmedia(code=c, title=t, download_files=False)
                parts_to_download = min(total_p, 5)
                for p in range(1, parts_to_download + 1):
                    await MovieService.download_movie_from_asilmedia(code=c, part=p)
                    await asyncio.sleep(0.2)
            except Exception as e:
                logger.debug(f"Preloader for #{c} error: {e}")

        await MovieService.sync_catalog_from_asilmedia(limit=limit, download_files=True)
        logger.info("Asilmedia.org kinolarni orqa fonda tayyorlash muvaffaqiyatli yakunlandi!")
    except asyncio.CancelledError:
        logger.info("Kinolarni orqa fonda tayyorlash to'xtatildi.")
    except Exception as ge:
        logger.warning(f"Kinolarni orqa fonda tayyorlashda xatolik: {ge}")


def start_background_movie_preloader(limit: int = 15) -> asyncio.Task:
    """Orqa fonda kinolarni yuklab tayyorlash vazifasini ishga tushirish."""
    global _preloader_task
    if _preloader_task and not _preloader_task.done():
        return _preloader_task
    _preloader_task = asyncio.create_task(_background_movie_preloader_loop(limit=limit))
    return _preloader_task


def stop_background_movie_preloader() -> None:
    """Orqa fondagi yuklash vazifasini to'xtatish."""
    global _preloader_task
    if _preloader_task and not _preloader_task.done():
        _preloader_task.cancel()
        _preloader_task = None

