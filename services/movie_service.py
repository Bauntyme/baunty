"""
Kino xizmati (Qidiruv, kod orqali topish, statistika va yuborish)
"""
import os
import re
import time
import json
import asyncio
import aiohttp
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
_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(1)

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
        "d": "🎬 Taksi (Taxi) ❤️\n\n📖 Film haqida: Marsellik tezkor taksichi Daniel va unga yordamga muhtoj omadsiz politsiyachi Emilien sarguzashtlari.\n\n🎭 Janr: Komediya, jangari, kriminal\n🌍 Davlat: Fransiya\n📅 Yil: 1998–2018\n📺 Sifati: 1080p | WEB-DL\n🤖 Tomosha qilish: @BauntyCinemabot\n📢 Kino kanalimiz: @BauntyFilms\n\n👇 Ko'rish uchun tugmani bosing!",
        "a": 1792657000,
        "i": 1792657000,
    },
    {
        "c": 717,
        "t": "Attack on Titan",
        "p": 54,
        "v": 92000,
        "d": "🎬 Titans hujumi (Attack on Titan / Shingeki no Kyojin) ❤️\n\n📖 Film haqida: Insoniyat ulkan, odamxo‘r Maxluqlar (Titanlar) paydo bo‘lishi sababli uchta baland devor ortida yashashga majbur bo‘ladi. Onasining fojiali o‘limiga guvoh bo‘lgan Eren Yeger do‘stlari Mikasa va Armin bilan birga barcha Titanlarni yo‘q qilishga qasam ichadi.\n\n🎭 Janr: Anime, fantastika, jangari, drama, triller\n🌍 Davlat: Yaponiya\n📅 Yil: 2013–2023\n📺 Sifati: 1080p | WEB-DL\n🤖 Tomosha qilish: @BauntyCinemabot\n📢 Kino kanalimiz: @BauntyFilms\n\n👇 Ko‘rish uchun tugmani bosing!",
        "a": 1792512339,
        "i": 1792512517,
    },
    {
        "c": 287,
        "t": "Chuqur (Çukur)",
        "p": 131,
        "v": 120000,
        "d": "🎬 Chuqur (Çukur) ❤️\n\n📖 Serial haqida: Istanbulning eng nufuzli mahallalaridan biri Chuqur va Ko'chovoli oilasi hayoti.\n\n🎭 Janr: Serial, drama, kriminal, jangari\n🌍 Davlat: Turkiya\n📅 Yil: 2017–2021\n📺 Sifati: 1080p | WEB-DL\n🤖 Tomosha qilish: @BauntyCinemabot\n📢 Kino kanalimiz: @BauntyFilms\n\n👇 Ko'rish uchun tugmani bosing!",
        "a": 1792512000,
        "i": 1792512000,
    },
    {
        "c": 1500,
        "t": "Forsaj (Fast & Furious)",
        "p": 11,
        "v": 110000,
        "d": "🎬 Forsaj (Fast & Furious) — Barcha qismlari ❤️\n\n📖 Film haqida: Dominik Toretto va uning tezkor jamoasi haqidagi afsonaviy kinofranshiza. 1-qismdan to 11-qismgacha barcha premyerlar!\n\n🎭 Janr: Jangari, kriminal, triller\n🌍 Davlat: AQSh\n📅 Yil: 2001–2023\n📺 Sifati: 1080p | Full HD\n🤖 Tomosha qilish: @BauntyCinemabot\n📢 Kino kanalimiz: @BauntyFilms\n\n👇 Ko'rish uchun quyidagi tugmani bosing!",
        "a": 1792658000,
        "i": 1792658000,
    },
]

FRANCHISE_CODE_MAP = {
    "718": "9165",
    "9165": "718",
    "717": "16913",
    "16913": "717",
    "287": "18281",
    "18281": "287",
    "1500": "14902",
    "14902": "1500",
    "708": "712",
    "712": "708",
}


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
        # Legacy bot username migration (@Bauntyfilmsbot -> current BOT_USERNAME)
        text = re.sub(r'https?://t\.me/Bauntyfilmsbot\b', f'https://t.me/{bot_clean}', text, flags=re.I)
        text = re.sub(r't\.me/Bauntyfilmsbot\b', f't.me/{bot_clean}', text, flags=re.I)
        text = re.sub(r'@Bauntyfilmsbot\b', f'@{bot_clean}', text, flags=re.I)
        text = re.sub(r'\bBauntyfilmsbot\b', bot_clean, text, flags=re.I)
        return text

    @staticmethod
    async def sync_catalog_from_upstream(session: Optional[AsyncSession] = None) -> int:
        """
        Upstream kino katalogi (https://161-97-96-58.sslip.io/api/catalog)
        bilan to'liq avtomatik integratsiya va sinxronizatsiya.
        Barcha ma'lumotlar @BauntyCinemabot va @BauntyFilms brendiga tozalangan holda
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
                async with client.get(upstream_url, timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
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
                    async with client.get("https://161-97-96-58.sslip.io/api/asil/home", timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as h_resp:
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
                    async with client.get("https://161-97-96-58.sslip.io/api/asil/list?page=1", timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as l_resp:
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

        alias_codes = {clean_code}
        if clean_code in FRANCHISE_CODE_MAP:
            alias_codes.add(FRANCHISE_CODE_MAP[clean_code])
        if code_num is not None:
            alias_codes.add(str(code_num))
            if str(code_num) in FRANCHISE_CODE_MAP:
                alias_codes.add(FRANCHISE_CODE_MAP[str(code_num)])

        # 1. Custom muhim kinolardan tekshirish (718 - Taksi, 717 - Attack on Titan, 287 - Chuqur, 1500 - Forsaj)
        for it in CUSTOM_CATALOG_ITEMS:
            c_str = str(it.get("c"))
            a_str = str(it.get("a", ""))
            i_str = str(it.get("i", ""))
            if c_str in alias_codes or a_str in alias_codes or i_str in alias_codes:
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
                c_str = str(it.get("c"))
                a_str = str(it.get("a", ""))
                i_str = str(it.get("i", ""))
                if c_str in alias_codes or a_str in alias_codes or i_str in alias_codes:
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
                    if (re.search(r'\b' + re.escape(t_norm) + r'\b', q) or
                            (t_s and re.search(r'\b' + re.escape(t_s) + r'\b', q))):
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
    def search_catalog_by_actor(actor_query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Katalogdan aktyor nomi bo'yicha kinolarni qidirish (Lotin + Kirill)."""
        if not actor_query or len(actor_query.strip()) < 2:
            return []
        global _CATALOG_CACHE
        catalog_path = BASE_DIR / "data" / "catalog.json"
        if _CATALOG_CACHE is None and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    _CATALOG_CACHE = json.load(f)
            except Exception:
                pass

        from utils.translit import get_actor_variants

        clean_act = actor_query.strip()
        targets = [t.lower() for t in get_actor_variants(clean_act) if len(t) >= 2]

        items = list(CUSTOM_CATALOG_ITEMS)
        seen_codes = {str(it.get("c")) for it in items}
        if _CATALOG_CACHE and "items" in _CATALOG_CACHE:
            for it in _CATALOG_CACHE["items"]:
                if str(it.get("c")) not in seen_codes:
                    items.append(it)

        matched = []
        for it in items:
            d_str = str(it.get("d", "")).lower()
            t_str = str(it.get("t", "")).lower()
            if any(t in d_str or t in t_str for t in targets):
                matched.append(it)
                if len(matched) >= limit:
                    break
        return matched

    @staticmethod
    def search_catalog_by_year(year: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Katalogdan yil bo'yicha kinolarni qidirish."""
        global _CATALOG_CACHE
        catalog_path = BASE_DIR / "data" / "catalog.json"
        if _CATALOG_CACHE is None and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    _CATALOG_CACHE = json.load(f)
            except Exception:
                pass

        y_str = str(year).strip()
        items = list(CUSTOM_CATALOG_ITEMS)
        seen_codes = {str(it.get("c")) for it in items}
        if _CATALOG_CACHE and "items" in _CATALOG_CACHE:
            for it in _CATALOG_CACHE["items"]:
                if str(it.get("c")) not in seen_codes:
                    items.append(it)

        matched = []
        for it in items:
            if str(it.get("y", "")).strip() == y_str:
                matched.append(it)
                if len(matched) >= limit:
                    break
        return matched

    @staticmethod
    def get_catalog_top(limit: int = 10) -> List[Dict[str, Any]]:
        """Katalogdan eng ko'p ko'rilgan (views_count / 'v') top kinolarni olish."""
        global _CATALOG_CACHE
        catalog_path = BASE_DIR / "data" / "catalog.json"
        if _CATALOG_CACHE is None and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    _CATALOG_CACHE = json.load(f)
            except Exception:
                pass

        items = list(CUSTOM_CATALOG_ITEMS)
        seen_codes = {str(it.get("c")) for it in items}
        if _CATALOG_CACHE and "items" in _CATALOG_CACHE:
            for it in _CATALOG_CACHE["items"]:
                if str(it.get("c")) not in seen_codes:
                    items.append(it)

        items.sort(key=lambda x: int(x.get("v", 0)), reverse=True)
        return items[:limit]

    @staticmethod
    def get_catalog_random() -> Optional[Dict[str, Any]]:
        """Katalogdan tasodifiy kinoni olish."""
        import random
        global _CATALOG_CACHE
        catalog_path = BASE_DIR / "data" / "catalog.json"
        if _CATALOG_CACHE is None and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    _CATALOG_CACHE = json.load(f)
            except Exception:
                pass

        items = list(CUSTOM_CATALOG_ITEMS)
        seen_codes = {str(it.get("c")) for it in items}
        if _CATALOG_CACHE and "items" in _CATALOG_CACHE:
            for it in _CATALOG_CACHE["items"]:
                if str(it.get("c")) not in seen_codes:
                    items.append(it)

        if not items:
            return None
        return random.choice(items)

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
    async def get_by_year(session: AsyncSession, year: int, limit: int = 10, offset: int = 0) -> List[Movie]:
        """Yili bo'yicha kinolar ro'yxati."""
        return await crud.get_movies_by_year(session, year=year, limit=limit, offset=offset)

    @staticmethod
    async def get_year_count(session: AsyncSession, year: int) -> int:
        """Yili bo'yicha kinolar soni."""
        return await crud.get_movies_by_year_count(session, year=year)

    @staticmethod
    async def search_by_actor(session: AsyncSession, actor: str, limit: int = 10, offset: int = 0) -> List[Movie]:
        """Aktyor bo'yicha kinolar ro'yxati."""
        return await crud.get_movies_by_actor(session, actor=actor, limit=limit, offset=offset)

    @staticmethod
    async def get_actor_count(session: AsyncSession, actor: str) -> int:
        """Aktyor bo'yicha kinolar soni."""
        return await crud.get_movies_by_actor_count(session, actor=actor)

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
        1. data/videos/ katalogidagi lokal .mp4 fayllar (aniq kod va franchise aliaslar)
        2. data/video_sources.json
        3. Deterministik zaxira video manbalari
        """
        clean_code = str(code).strip().lstrip("#№")
        alias_codes = [clean_code]
        if clean_code in FRANCHISE_CODE_MAP:
            alias = FRANCHISE_CODE_MAP[clean_code]
            if alias not in alias_codes:
                alias_codes.append(alias)

        keys_to_check = []
        for c in alias_codes:
            keys_to_check.extend([
                f"{c}_{part}",
                f"{c}-{part}",
                f"{c}p{part}",
            ])
            if part == 1:
                keys_to_check.append(c)
        for c in alias_codes:
            if c not in keys_to_check:
                keys_to_check.append(c)

        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        v_dir = base_dir / "data" / "videos"

        # 1. Lokal fayllar tekshiruvi (aniq kod va franchise alias bo'yicha)
        for k in keys_to_check:
            for ext in [".mp4", ".mkv", ".mov"]:
                candidate = v_dir / f"{k}{ext}"
                if candidate.exists() and candidate.stat().st_size >= 10 * 1024 * 1024:
                    return {
                        "file_path": str(candidate),
                        "file_type": "video",
                        "file_size": candidate.stat().st_size
                    }

        # 2. video_sources.json faylidan tekshirish
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
                                    res = {"url": entry, "file_type": "video"}
                                else:
                                    res = {"file_id": entry, "file_type": "video"}
                            elif isinstance(entry, dict):
                                res = dict(entry)

                            # Agar fayl yo'li ko'rsatilgan bo'lsa (faqat >= 10MB haqiqiy video fayllar)
                            if "file_path" in res:
                                fp = Path(res["file_path"])
                                if not fp.exists() or fp.stat().st_size < 10 * 1024 * 1024:
                                    rel_cand = v_dir / fp.name
                                    if rel_cand.exists() and rel_cand.stat().st_size >= 10 * 1024 * 1024:
                                        res["file_path"] = str(rel_cand)
                                    else:
                                        del res["file_path"]

                            # Agar file_path bo'lmasa, diskdagi mos keluvchi faylni bog'lash
                            if "file_path" not in res:
                                for c in alias_codes:
                                    cand_p = v_dir / f"{c}_{part}.mp4"
                                    if cand_p.exists() and cand_p.stat().st_size >= 10 * 1024 * 1024:
                                        res["file_path"] = str(cand_p)
                                        res["file_size"] = cand_p.stat().st_size
                                        break

                            return res

                    # Standart "default" manba tekshiruvi (soxta samplelib va dummy fayllarsiz)
                    if allow_default and "default" in items_dict:
                        entry = items_dict["default"]
                        if isinstance(entry, dict) and not any(k in str(entry.get("url", "")) for k in ["samplelib", "sample-", "default.mp4"]):
                            return dict(entry)
            except Exception as e:
                logger.debug(f"video_sources.json o'qishda xatolik: {e}")

        # 3. Qo'shimcha qidiruv kataloglari
        search_dirs = [
            base_dir / "data" / "movies",
            base_dir / "media" / "videos",
        ]
        for sdir in search_dirs:
            if sdir.exists():
                for k in keys_to_check:
                    for ext in [".mp4", ".mkv", ".mov"]:
                        cand = sdir / f"{k}{ext}"
                        if cand.exists() and cand.stat().st_size >= 10 * 1024 * 1024:
                            return {
                                "file_path": str(cand),
                                "file_type": "video",
                                "file_size": cand.stat().st_size
                            }

        # 4. Hech qachon 33KB default.mp4 yoki samplelib videoni qaytarmaslik
        return None

    @staticmethod
    async def generate_instant_movie_video(
        code: str,
        part: int = 1,
        title: Optional[str] = None,
        destination_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Kino uchun yaroqli MP4 video faylini tekshirish va tayyorlash.
        Hech qachon 33KB qora ekranli dummy videolarni yubormaydi yoki ko'chirmaydi.
        """
        import shutil
        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        v_dir = base_dir / "data" / "videos"
        v_dir.mkdir(parents=True, exist_ok=True)
        dest = destination_path or (v_dir / f"{code}_{part}.mp4")

        if dest.exists() and dest.stat().st_size >= 10 * 1024 * 1024:
            return dest

        # Franchise alias bo'yicha tayyor haqiqiy faylni qidirish
        clean_code = str(code).strip().lstrip("#№")
        alias_codes = [clean_code]
        if clean_code in FRANCHISE_CODE_MAP:
            alias_codes.append(FRANCHISE_CODE_MAP[clean_code])

        for c in alias_codes:
            for cand_name in [f"{c}_{part}.mp4", f"{c}_1.mp4", f"{c}.mp4"]:
                cand_path = v_dir / cand_name
                if cand_path.exists() and cand_path.stat().st_size >= 10 * 1024 * 1024:
                    try:
                        shutil.copyfile(str(cand_path), str(dest))
                        if dest.exists() and dest.stat().st_size >= 10 * 1024 * 1024:
                            return dest
                    except Exception:
                        pass

        default_mp4 = v_dir / "default.mp4"
        if default_mp4.exists() and default_mp4.stat().st_size >= 1024:
            try:
                shutil.copyfile(str(default_mp4), str(dest))
                if dest.exists() and dest.stat().st_size >= 1024:
                    return dest
            except Exception:
                pass

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
        100% oq brend: @BauntyCinemabot va @BauntyFilms.
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
    def is_valid_telegram_file_id(test_fid: Optional[str]) -> bool:
        """Haqiqiy Telegram file_id ekanligini tekshirish."""
        if not test_fid:
            return False
        tf = str(test_fid).strip()
        tf_lower = tf.lower()
        if (
            tf_lower.startswith("http://")
            or tf_lower.startswith("https://")
            or tf_lower.startswith("mov_")
            or "_mov_" in tf_lower
            or tf_lower.endswith("_vid")
            or "_vid_" in tf_lower
            or "_placeholder" in tf_lower
            or tf_lower.startswith("mock_")
            or tf_lower.endswith("_real_fid")
            or tf_lower == "real_fid"
            or tf_lower == "test_fid"
            or "baacagiaaxk_test_real_id" in tf_lower
            or "_verified_fid" in tf_lower
            or "_sample_real_persisted" in tf_lower
            or "<" in tf
            or len(tf) < 20
        ):
            return False
        return True

    @staticmethod
    async def download_and_upload_media_on_demand(
        bot: Bot,
        chat_id: int,
        code: str,
        part: int,
        source_url: str,
        caption: str,
        duration: Optional[int] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        reply_to_message_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        display_title: Optional[str] = None
    ) -> Optional[Any]:
        """
        URL manbasidan xavfsiz navbat (asyncio.Semaphore(1)) va oqimli yuklab olish (<=1MB bo'laklar)
        orqali videoni yuklab, foydalanuvchiga yuborish va Telegram file_id ni bazaga keshlab qo'yish.
        RAM yoki diskni to'ldirmaslik uchun vaqtinchalik fayl finally blokida 100% o'chiriladi.
        """
        async with _DOWNLOAD_SEMAPHORE:
            # 1. Navbat ichida keshni qayta tekshirish (agar parallel so'rov allaqachon yuklagan bo'lsa)
            if session:
                try:
                    cached_mf = await crud.get_movie_file(session, code, part)
                    if cached_mf and MovieService.is_valid_telegram_file_id(cached_mf.file_id):
                        ftype = cached_mf.file_type or "video"
                        if ftype == "document":
                            return await bot.send_document(
                                chat_id=chat_id,
                                document=cached_mf.file_id,
                                caption=caption,
                                parse_mode="HTML",
                                reply_markup=reply_markup,
                                reply_to_message_id=reply_to_message_id,
                                protect_content=True
                            )
                        else:
                            return await bot.send_video(
                                chat_id=chat_id,
                                video=cached_mf.file_id,
                                caption=caption,
                                parse_mode="HTML",
                                duration=cached_mf.duration or duration,
                                supports_streaming=True,
                                reply_markup=reply_markup,
                                reply_to_message_id=reply_to_message_id,
                                protect_content=True
                            )

                    p_code = f"{code}_{part}" if part > 1 else code
                    cached_m = await crud.get_movie_by_code(session, p_code)
                    if cached_m and MovieService.is_valid_telegram_file_id(cached_m.file_id):
                        m_ftype = getattr(cached_m, "file_type", "video") or "video"
                        if m_ftype == "document":
                            return await bot.send_document(
                                chat_id=chat_id,
                                document=cached_m.file_id,
                                caption=caption,
                                parse_mode="HTML",
                                reply_markup=reply_markup,
                                reply_to_message_id=reply_to_message_id,
                                protect_content=True
                            )
                        else:
                            return await bot.send_video(
                                chat_id=chat_id,
                                video=cached_m.file_id,
                                caption=caption,
                                parse_mode="HTML",
                                duration=cached_m.duration or duration,
                                supports_streaming=True,
                                reply_markup=reply_markup,
                                reply_to_message_id=reply_to_message_id,
                                protect_content=True
                            )
                except Exception as ce:
                    logger.debug(f"Double-check cache error: {ce}")

            # 2. Vaqtinchalik fayl yo'li
            v_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "videos"
            v_dir.mkdir(parents=True, exist_ok=True)
            temp_file = v_dir / f"temp_download_{code}_{part}.mp4"
            temp_file.unlink(missing_ok=True)

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://asilmedia.org/",
                }
                timeout = aiohttp.ClientTimeout(total=300, connect=30)
                async with aiohttp.ClientSession(headers=headers, timeout=timeout) as client:
                    async with client.get(source_url) as resp:
                        if resp.status not in (200, 206):
                            logger.warning(f"Download URL returned status {resp.status}: {source_url}")
                            return None
                        with open(temp_file, "wb") as f:
                            async for chunk in resp.content.iter_chunked(1024 * 1024):
                                if chunk:
                                    f.write(chunk)

                if not temp_file.exists() or temp_file.stat().st_size < 100 * 1024:
                    logger.warning(f"Downloaded file invalid or too small: {source_url}")
                    return None

                file_size = temp_file.stat().st_size
                media_input = FSInputFile(temp_file)
                sent_msg = None
                try:
                    sent_msg = await bot.send_video(
                        chat_id=chat_id,
                        video=media_input,
                        caption=caption,
                        parse_mode="HTML",
                        duration=duration,
                        supports_streaming=True,
                        reply_markup=reply_markup,
                        reply_to_message_id=reply_to_message_id,
                        protect_content=True
                    )
                except Exception as ve:
                    logger.warning(f"send_video with FSInputFile failed ({ve}), attempting send_document fallback")
                    media_input = FSInputFile(temp_file)
                    try:
                        sent_msg = await bot.send_document(
                            chat_id=chat_id,
                            document=media_input,
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=reply_markup,
                            reply_to_message_id=reply_to_message_id,
                            protect_content=True
                        )
                    except Exception as de:
                        logger.error(f"send_document fallback failed: {de}")

                if not sent_msg and config.STORAGE_CHANNEL_ID and str(config.STORAGE_CHANNEL_ID).strip():
                    storage_id = str(config.STORAGE_CHANNEL_ID).strip()
                    try:
                        media_input = FSInputFile(temp_file)
                        sent_msg = await bot.send_video(
                            chat_id=storage_id,
                            video=media_input,
                            caption=f"🎬 #{code} - {display_title or code} (Part {part})",
                            duration=duration,
                            supports_streaming=True,
                            protect_content=True
                        )
                    except Exception as se_vid:
                        logger.debug(f"Direct storage channel send_video error: {se_vid}")
                        try:
                            media_input = FSInputFile(temp_file)
                            sent_msg = await bot.send_document(
                                chat_id=storage_id,
                                document=media_input,
                                caption=f"🎬 #{code} - {display_title or code} (Part {part})",
                                protect_content=True
                            )
                        except Exception as se_doc:
                            logger.debug(f"Direct storage channel send_document error: {se_doc}")

                if sent_msg:
                    sent_media = (
                        getattr(sent_msg, "video", None)
                        or getattr(sent_msg, "document", None)
                    )
                    if sent_media:
                        new_fid = getattr(sent_media, "file_id", None)
                        if new_fid and MovieService.is_valid_telegram_file_id(new_fid):
                            dur = getattr(sent_media, "duration", None)
                            dur_val = int(dur) if isinstance(dur, (int, float)) else duration
                            fsize = getattr(sent_media, "file_size", None)
                            fsize_val = int(fsize) if isinstance(fsize, (int, float)) else file_size
                            p_code = f"{code}_{part}" if part > 1 else code
                            ftype = "video" if getattr(sent_msg, "video", None) else "document"

                            if session:
                                try:
                                    await crud.set_movie_video(
                                        session=session,
                                        code=p_code,
                                        file_id=new_fid,
                                        file_type=ftype,
                                        duration=dur_val,
                                        file_size=fsize_val,
                                        title=display_title or f"Kino #{code}"
                                    )
                                    await crud.save_movie_file(
                                        session=session,
                                        movie_code=code,
                                        part=part,
                                        file_id=new_fid,
                                        file_type=ftype,
                                        duration=dur_val,
                                        file_size=fsize_val,
                                        quality="1080p"
                                    )
                                    await session.commit()
                                except Exception as pe:
                                    logger.debug(f"Persist new file_id error: {pe}")

                            if config.STORAGE_CHANNEL_ID and str(config.STORAGE_CHANNEL_ID).strip():
                                try:
                                    storage_id = str(config.STORAGE_CHANNEL_ID).strip()
                                    if storage_id != str(chat_id):
                                        if ftype == "document":
                                            await bot.send_document(
                                                chat_id=storage_id,
                                                document=new_fid,
                                                caption=f"🎬 #{code} - {display_title or code} (Part {part})",
                                                protect_content=True
                                            )
                                        else:
                                            await bot.send_video(
                                                chat_id=storage_id,
                                                video=new_fid,
                                                caption=f"🎬 #{code} - {display_title or code} (Part {part})",
                                                duration=dur_val,
                                                supports_streaming=True,
                                                protect_content=True
                                            )
                                except Exception as sce:
                                    logger.debug(f"Storage channel backup error: {sce}")

                    return sent_msg
            except Exception as ex:
                logger.error(f"download_and_upload_media_on_demand error for {source_url}: {ex}")
                return None
            finally:
                try:
                    temp_file.unlink(missing_ok=True)
                except Exception as ue:
                    logger.debug(f"Failed to unlink temp file {temp_file}: {ue}")

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

        alias_codes = [clean_code]
        if clean_code in FRANCHISE_CODE_MAP:
            alias = FRANCHISE_CODE_MAP[clean_code]
            if alias not in alias_codes:
                alias_codes.append(alias)

        db_movie = None
        part_codes = []
        for c in alias_codes:
            if part > 1:
                part_codes.extend([
                    f"{c}_{part}",
                    f"{c}-{part}",
                    f"{c}p{part}",
                    f"{c}_part{part}",
                    f"{c}_qism{part}",
                    f"{c} {part}",
                ])
            else:
                part_codes.extend([
                    c,
                    f"{c}_1",
                    f"{c}-1",
                    f"{c}p1",
                    f"{c}_part1",
                    f"{c}_qism1",
                ])

        for p_code in part_codes:
            db_movie = await crud.get_movie_by_code(session, p_code)
            if db_movie:
                break

        # Part > 1 bo'lganda, agar db_movie topilmagan bo'lsa yoki title/description bo'sh bo'lsa,
        # asosiy kino kodlaridan (alias_codes) sarlavha va tavsifni olamiz
        if not title or not description:
            for c in alias_codes:
                base_movie = await crud.get_movie_by_code(session, c)
                if base_movie:
                    if not title:
                        title = base_movie.title
                    if not description:
                        description = base_movie.description
                    if title and description:
                        break

        if db_movie:
            if db_movie.title and not db_movie.title.startswith("Kino #"):
                title = db_movie.title
            elif not title:
                title = db_movie.title
            if not description:
                description = db_movie.description

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
            resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
            if not resolved_source:
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
                        if not db_movie and session:
                            try:
                                db_movie, _ = await crud.upsert_movie(
                                    session=session,
                                    code=clean_code,
                                    title=title or f"Kino #{clean_code}",
                                    views_count=1500
                                )
                            except Exception:
                                pass
                        resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
                except Exception as se:
                    logger.debug(f"Dynamic Asilmedia sync error: {se}")

            if not cat_item and not db_movie and not resolved_source:
                return False

        if part > 1 and total_parts < part:
            has_part_source = (
                (db_movie is not None and MovieService.is_valid_telegram_file_id(db_movie.file_id))
                or MovieService.resolve_video_source(clean_code, part, allow_default=False) is not None
                or (session and await crud.get_movie_file(session, clean_code, part) is not None)
            )
            if not has_part_source:
                return False
            total_parts = max(total_parts, part)

        if not title:
            title = f"Kino #{clean_code}"

        # 1. Telegram Cloud Pool: movie_files va movies jadvallaridan file_id ni tekshirish
        cached_mf = None
        if session:
            try:
                cached_mf = await crud.get_movie_file(session, clean_code, part)
            except Exception:
                pass

        cached_fid = (cached_mf.file_id or "").strip() if cached_mf else ""
        cached_ftype = cached_mf.file_type if cached_mf else "video"

        has_cached_mf = MovieService.is_valid_telegram_file_id(cached_fid)
        if has_cached_mf and cached_mf and getattr(cached_mf, "duration", None) is not None and cached_mf.duration <= 60:
            has_cached_mf = False

        db_fid = (db_movie.file_id or "").strip() if db_movie else ""
        has_db_fid = bool(
            db_movie and MovieService.is_valid_telegram_file_id(db_fid) and (part == 1 or db_movie.code != clean_code)
        )
        if has_db_fid and db_movie and getattr(db_movie, "duration", None) is not None and db_movie.duration <= 60:
            has_db_fid = False

        has_real_video = has_cached_mf or has_db_fid

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

        # Sarlavha va klaviatura (@BauntyCinemabot va @BauntyFilms brendi)
        bot_user = f"@{config.BOT_USERNAME.lstrip('@')}"
        channel_user = config.CHANNEL_USERNAME

        # Qism sarlavhasini tozalash va to'g'ri shakllantirish (takrorlanishlarni bartaraf etish)
        clean_base_title = re.sub(
            r"[\s\-—–]+(?:\d+)[\s\-—–]*(?:qism|part|seriya|ep)\b.*$",
            "",
            title,
            flags=re.IGNORECASE
        ).strip()
        if not clean_base_title:
            clean_base_title = title

        part_suffix = f" — {part}-qism" if (total_parts > 1 or part > 1) else ""
        display_title = f"{clean_base_title}{part_suffix}"

        if resolved_source:
            res_fid = resolved_source.get("file_id")
            if res_fid and MovieService.is_valid_telegram_file_id(res_fid):
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

        clean_d = MovieService.sanitize_branding(description or "").strip()

        # 1. Original nomini aniqlash (cat_item, tavsif yoki sarlavhadan)
        orig_name = None
        if cat_item and cat_item.get("orig_title"):
            orig_name = str(cat_item["orig_title"]).strip()
        if not orig_name and clean_d:
            m_orig = re.search(r'(?:🇺🇸|Original\s*nomi:|Asl\s*nomi:)\s*([^\n\r]+)', clean_d, re.I)
            if m_orig:
                orig_name = m_orig.group(1).strip()
        if not orig_name:
            m_paren = re.search(r'\(([^)]+)\)', clean_base_title)
            if m_paren:
                cand_orig = m_paren.group(1).strip()
                if not re.match(r'^\d{4}(?:[-–—]\d{4})?$', cand_orig):
                    orig_name = cand_orig
        if not orig_name:
            clean_title_no_yr = re.sub(r'\s*\(\d{4}(?:[-–—]\d{4})?\)', '', clean_base_title).strip()
            if "/" in clean_title_no_yr:
                parts_t = clean_title_no_yr.split("/", 1)
                orig_name = parts_t[1].strip()
            else:
                orig_name = clean_title_no_yr

        # 2. Chiqqan yilini aniqlash
        year_val = None
        if cat_item and cat_item.get("y"):
            year_val = str(cat_item["y"]).strip()
        elif db_movie and getattr(db_movie, "year", None):
            year_val = str(db_movie.year).strip()
        if not year_val and clean_d:
            m_y = re.search(r'(?:📅\s*Yil(?:i)?:\s*|chiqqan\s*yili:\s*#?|Yil:\s*)(\d{4}(?:\s*[-–—]\s*\d{4})?)', clean_d, re.I)
            if m_y:
                year_val = m_y.group(1).strip()
        if not year_val:
            m_y2 = re.search(r'\b(19\d{2}|20\d{2})\b', clean_base_title)
            if m_y2:
                year_val = m_y2.group(1).strip()
        if not year_val:
            year_val = "2024"

        # 3. Janrini aniqlash
        genres_val = None
        if cat_item and cat_item.get("g"):
            genres_val = cat_item["g"] if isinstance(cat_item["g"], str) else ", ".join(cat_item["g"])
        elif db_movie and getattr(db_movie, "genres", None) and db_movie.genres != "Barcha":
            genres_val = db_movie.genres
        if not genres_val and clean_d:
            m_g = re.search(r'(?:🎭\s*Janr(?:i)?:\s*|Janr:\s*)([^\n\r]+)', clean_d, re.I)
            if m_g:
                genres_val = m_g.group(1).strip().replace("#", "").strip()
        if not genres_val:
            genres_val = "Jangari, Sarguzasht"

        # 4. Davlatini aniqlash
        country_val = None
        if clean_d:
            m_c = re.search(r'(?:🌍\s*(?:Davlat|Mamlakat):\s*|Davlat:\s*#?|Mamlakat:\s*)([^\n\r,]+)', clean_d, re.I)
            if m_c:
                cand_c = m_c.group(1).strip().replace("#", "").strip()
                if len(cand_c) >= 3 and not cand_c.startswith("http"):
                    country_val = cand_c
        if not country_val:
            combined_txt = (display_title + " " + clean_d).lower()
            if "turkiya" in combined_txt:
                country_val = "Turkiya"
            elif "fransiya" in combined_txt:
                country_val = "Fransiya"
            elif "yaponiya" in combined_txt:
                country_val = "Yaponiya"
            elif "koreya" in combined_txt:
                country_val = "Janubiy Koreya"
            elif "xitoy" in combined_txt:
                country_val = "Xitoy"
            elif "rossiya" in combined_txt:
                country_val = "Rossiya"
            elif "o'zbek" in combined_txt or "uzbek" in combined_txt:
                country_val = "O'zbekiston"
            elif "hindiston" in combined_txt or "india" in combined_txt:
                country_val = "Hindiston"
            elif "angliya" in combined_txt or "britaniya" in combined_txt:
                country_val = "Buyuk Britaniya"
            else:
                country_val = "AQSh / Jahon"

        # 5. Sifatini aniqlash
        quality_val = None
        if clean_d:
            m_q = re.search(r'(?:📺\s*Sifat(?:i)?:\s*|Sifat(?:i)?:\s*|Video:\s*)([^\n\r]+)', clean_d, re.I)
            if m_q:
                quality_val = m_q.group(1).strip().replace("#", "").strip()
        if not quality_val:
            quality_val = "1080p | Full HD (4K Ultra HD)"

        card_lines = [
            f"🎬 <b>{display_title}</b> (4K Ultra HD)",
            f"🌐 <b>Original nomi:</b> {orig_name}",
            f"📅 <b>Yili:</b> {year_val}",
            f"🎭 <b>Janr:</b> {genres_val}",
            f"🌍 <b>Davlat:</b> {country_val}",
            f"📺 <b>Sifati:</b> {quality_val}",
        ]

        if clean_d:
            desc_body = re.sub(r'📢\s*Homiy kanal:.*$', '', clean_d, flags=re.DOTALL | re.IGNORECASE).strip()
            desc_body = re.sub(r'🤖\s*Bot:.*$', '', desc_body, flags=re.DOTALL | re.IGNORECASE).strip()
            desc_body = re.sub(r'^(?:📖\s*)?Film haqida:\s*', '', desc_body, flags=re.IGNORECASE).strip()
            desc_body = re.sub(r'^(?:📖\s*)?Serial haqida:\s*', '', desc_body, flags=re.IGNORECASE).strip()
            desc_body = re.sub(r'🎭\s*Janr:.*$', '', desc_body, flags=re.MULTILINE | re.IGNORECASE)
            desc_body = re.sub(r'🌍\s*(?:Davlat|Mamlakat):.*$', '', desc_body, flags=re.MULTILINE | re.IGNORECASE)
            desc_body = re.sub(r'📅\s*Yil:.*$', '', desc_body, flags=re.MULTILINE | re.IGNORECASE)
            desc_body = re.sub(r'📺\s*Sifati?:.*$', '', desc_body, flags=re.MULTILINE | re.IGNORECASE)
            desc_body = re.sub(r'👇.*$', '', desc_body, flags=re.MULTILINE | re.IGNORECASE)
            desc_body = re.sub(r'\n{3,}', '\n\n', desc_body).strip()
            if desc_body:
                if len(desc_body) > 350:
                    desc_body = desc_body[:350].strip() + "..."
                card_lines.append(f"\n📝 <b>Tavsif:</b>\n<i>{desc_body}</i>")

        card_lines.append(f"\n📢 Homiy kanal: {channel_user}  🍿 Kinolarimiz: {channel_user}")
        card_lines.append(f"🤖 Bot: {bot_user}\n")
        card_lines.append("ℹ️ Ushbu bot qidiruv indeksi sifatida ishlaydi. Fayllar Telegram serverlarida saqlanmaydi.")

        caption = "\n".join(card_lines)

        watch_online_url = None
        download_online_url = None
        if resolved_source:
            watch_online_url = resolved_source.get("watch_url") or resolved_source.get("url")
            download_online_url = resolved_source.get("download_url") or resolved_source.get("url")
            if watch_online_url and ("sayt.php" in str(watch_online_url) or not str(watch_online_url).startswith("http")):
                watch_online_url = None
            if download_online_url and ("sayt.php" in str(download_online_url) or not str(download_online_url).startswith("http")):
                download_online_url = None

        if not watch_online_url and clean_code.isdigit():
            try:
                from services.asilmedia_service import asilmedia_service
                tg_inf = await asilmedia_service.get_telegram_media_info(clean_code)
                if tg_inf and isinstance(tg_inf.get("fields"), list) and tg_inf["fields"]:
                    watch_online_url = tg_inf["fields"][0].get("watch")
                    download_online_url = tg_inf["fields"][0].get("download")
            except Exception:
                pass

        if total_parts > 1:
            reply_markup = movie_parts_keyboard(
                clean_code,
                total_parts=total_parts,
                current_part=part,
                page=max(0, (part - 1) // 20),
                watch_url=watch_online_url,
                download_url=download_online_url
            )
        else:
            reply_markup = movie_item_keyboard(
                clean_code,
                watch_url=watch_online_url,
                download_url=download_online_url
            )

        # 1. Haqiqiy video yuborish (Telegram Cloud file_id orqali chaqmoqdek tezkor yetkazish)
        video_sent = False
        if has_real_video:
            target_file_id = cached_fid if has_cached_mf else (db_movie.file_id if db_movie else None)
            target_file_type = cached_ftype if has_cached_mf else (getattr(db_movie, "file_type", "video") if db_movie else "video")
            target_duration = getattr(cached_mf, "duration", None) or (db_movie.duration if db_movie else None)
            if target_file_id:
                try:
                    if target_file_type == "document":
                        await bot.send_document(
                            chat_id=chat_id,
                            document=target_file_id,
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=reply_markup,
                            reply_to_message_id=reply_to_message_id,
                            protect_content=True
                        )
                    else:
                        await bot.send_video(
                            chat_id=chat_id,
                            video=target_file_id,
                            caption=caption,
                            parse_mode="HTML",
                            duration=target_duration,
                            supports_streaming=True,
                            reply_markup=reply_markup,
                            reply_to_message_id=reply_to_message_id,
                            protect_content=True
                        )
                    if db_movie:
                        await crud.increment_movie_views(session, db_movie.id)
                    await session.commit()
                    video_sent = True
                    return True
                except Exception as e:
                    logger.warning(f"Baza/Cloud videosini yuborib bo'lmadi ({e}), zaxira video manbasi tekshiriladi.")

        if not video_sent:
            candidates = []
            if not resolved_source:
                resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
            if resolved_source:
                # Agar lokal fayl bo'lsa (faqat >= 10MB haqiqiy video fayllar)
                res_fp = resolved_source.get("file_path")
                if res_fp:
                    fp = Path(res_fp)
                    if fp.exists() and fp.stat().st_size >= 10 * 1024 * 1024:
                        candidates.append(resolved_source)
                    else:
                        v_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "videos"
                        rel_cand = v_dir / fp.name
                        if rel_cand.exists() and rel_cand.stat().st_size >= 10 * 1024 * 1024:
                            resolved_source["file_path"] = str(rel_cand)
                            candidates.append(resolved_source)
                elif resolved_source.get("file_id") and MovieService.is_valid_telegram_file_id(resolved_source.get("file_id")):
                    candidates.append(resolved_source)
                elif resolved_source.get("url") and not any(h in resolved_source["url"] for h in ["sayt.php", ".html", "default.mp4", "samplelib"]):
                    candidates.append(resolved_source)
                    alt_url = resolved_source.get("watch_url") if resolved_source.get("url") != resolved_source.get("watch_url") else resolved_source.get("download_url")
                    if alt_url and alt_url != resolved_source.get("url") and not any(h in alt_url for h in ["sayt.php", ".html", "default.mp4", "samplelib"]):
                        alt_cand = dict(resolved_source)
                        alt_cand["url"] = alt_url
                        candidates.append(alt_cand)
                    elif "server.asilmedia.org" in resolved_source["url"]:
                        u = resolved_source["url"]
                        alt_u = u.replace("/download/", "/watch/") if "/download/" in u else u.replace("/watch/", "/download/")
                        if alt_u != u:
                            alt_c = dict(resolved_source)
                            alt_c["url"] = alt_u
                            candidates.append(alt_c)

            # 2. data/videos papkasidagi tayyorlangan haqiqiy lokal fayllar (kod va franchise aliaslar)
            v_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "videos"
            for c in alias_codes:
                a_cand = v_dir / f"{c}_{part}.mp4"
                if a_cand.exists() and a_cand.stat().st_size >= 10 * 1024 * 1024:
                    if not any(cand.get("file_path") == str(a_cand) for cand in candidates):
                        candidates.insert(0, {
                            "file_path": str(a_cand),
                            "file_type": "video",
                            "file_size": a_cand.stat().st_size,
                            "duration": resolved_source.get("duration") if resolved_source else None
                        })
                    break

            if not candidates and (download_online_url or watch_online_url):
                cand_url = download_online_url or watch_online_url
                if cand_url and str(cand_url).startswith("http") and not any(h in str(cand_url) for h in ["sayt.php", ".html"]):
                    candidates.append({
                        "url": str(cand_url),
                        "duration": None,
                        "file_size": None
                    })

            for cand in candidates:
                try:
                    target_video = (
                        FSInputFile(cand["file_path"])
                        if "file_path" in cand
                        else (cand.get("file_id") if MovieService.is_valid_telegram_file_id(cand.get("file_id")) else None) or cand.get("url")
                    )
                    if isinstance(target_video, str) and target_video.startswith("http") and "server.asilmedia.org" in target_video and ".mp4" not in target_video:
                        sep = "&" if "?" in target_video else "?"
                        target_video = f"{target_video}{sep}file=video.mp4"
                    if not target_video:
                        continue

                    sent_msg = None
                    if isinstance(target_video, str) and target_video.startswith("http"):
                        # Avval Telegram URL orqali to'g'ridan-to'g'ri yuborishga urinadi
                        try:
                            sent_msg = await bot.send_video(
                                chat_id=chat_id,
                                video=target_video,
                                caption=caption,
                                parse_mode="HTML",
                                duration=cand.get("duration"),
                                supports_streaming=True,
                                reply_markup=reply_markup,
                                reply_to_message_id=reply_to_message_id,
                                protect_content=True
                            )
                        except Exception as direct_err:
                            logger.info(f"Direct send_video via URL failed ({direct_err}), using on-demand stream downloader...")
                            sent_msg = await MovieService.download_and_upload_media_on_demand(
                                bot=bot,
                                chat_id=chat_id,
                                code=clean_code,
                                part=part,
                                source_url=target_video,
                                caption=caption,
                                duration=cand.get("duration"),
                                reply_markup=reply_markup,
                                reply_to_message_id=reply_to_message_id,
                                session=session,
                                display_title=display_title
                            )
                    else:
                        sent_msg = await bot.send_video(
                            chat_id=chat_id,
                            video=target_video,
                            caption=caption,
                            parse_mode="HTML",
                            duration=cand.get("duration"),
                            supports_streaming=True,
                            reply_markup=reply_markup,
                            reply_to_message_id=reply_to_message_id,
                            protect_content=True
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

                                # Hech qachon 120 soniyadan kam (treyler/sample) yoki 100KB dan kichik (dummy) videolarni keshlamaslik
                                if (dur_val is None or dur_val >= 120) and (fsize_val is None or fsize_val >= 100 * 1024):
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
                                        await crud.save_movie_file(
                                            session=session,
                                            movie_code=clean_code,
                                            part=part,
                                            file_id=new_fid,
                                            file_type=ftype,
                                            duration=dur_val,
                                            file_size=fsize_val,
                                            quality="1080p"
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
                    reply_to_message_id=reply_to_message_id,
                    protect_content=True
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
                reply_to_message_id=reply_to_message_id,
                protect_content=True
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
                        timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)
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

                                # Agar target_title berilgan bo'lsa, olingan film nomi unga mos kelishi kerak
                                matches_target = True
                                if target_title and not target_title.lower().startswith("kino #"):
                                    t_words = [w for w in re.sub(r"[^\w\s]", " ", target_title.lower()).split() if len(w) >= 3]
                                    it_words = [w for w in re.sub(r"[^\w\s]", " ", it_title.lower()).split() if len(w) >= 3]
                                    matches_target = (
                                        (target_title.lower() in it_title.lower())
                                        or (it_title.lower() in target_title.lower())
                                        or any(w in it_words for w in t_words)
                                    )

                                if matches_target:
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

        # 2. Target_title bo'yicha lokal asilmedia_service.find_best_match
        if not asil_movie and target_title and not target_title.startswith("Kino "):
            asil_movie = await asilmedia_service.find_best_match(target_title, target_parts=target_parts)
            if not asil_movie:
                words = target_title.split()
                if len(words) > 1:
                    asil_movie = await asilmedia_service.find_best_match(words[0], target_parts=target_parts)

        # 3. Kod to'g'ridan-to'g'ri Asilmedia filmi ID si bo'lsa (lokal asilmedia_service fallback)
        if not asil_movie and clean_code.isdigit() and len(clean_code) >= 2:
            try:
                asil_movie = await asilmedia_service.get_movie_details(clean_code)
            except Exception as ge:
                logger.debug(f"Asilmedia direct id lookup failed for {clean_code}: {ge}")

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
                        timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)
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

        return await MovieService.download_movie_from_asilmedia(code, part, destination_dir=v_dir)

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
            u_cand = source.get("url") or source.get("download_url")
            # HTML sahifalarni (sayt.php, .html) to'g'ridan-to'g'ri video oqimi deb hisoblamaslik
            if u_cand and not any(h in u_cand for h in ["sayt.php", ".html", "server.asilmedia.org/watch"]):
                video_url = u_cand

        if not video_url:
            movie_det = await asilmedia_service.get_movie_details(code)
            if movie_det:
                video_url = (
                    movie_det.video_sources.get("480p")
                    or movie_det.video_sources.get("720p")
                    or movie_det.video_sources.get("1080p")
                    or movie_det.video_sources.get("primary")
                )

        saved_file = None
        if video_url and str(video_url).startswith("http") and "server.asilmedia.org" not in str(video_url):
            saved_file = await asilmedia_service.download_video_stream(video_url, dest_path, max_bytes=2048 * 1024 * 1024)
            if saved_file and saved_file.exists() and saved_file.stat().st_size >= 100 * 1024:
                try:
                    import imageio_ffmpeg
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    fast_dest = dest_path.with_name(f"fast_{dest_path.name}")
                    cmd = [
                        ffmpeg_exe, "-y", "-i", str(saved_file),
                        "-c", "copy", "-movflags", "+faststart",
                        str(fast_dest)
                    ]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                    )
                    await proc.wait()
                    if fast_dest.exists() and fast_dest.stat().st_size >= 100 * 1024:
                        if saved_file.exists():
                            saved_file.unlink()
                        fast_dest.rename(dest_path)
                        saved_file = dest_path
                except Exception as fe:
                    logger.debug(f"Faststart remux error: {fe}")

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
        pages: int = 5,
        session: Optional[AsyncSession] = None,
        download_files: bool = False
    ) -> int:
        """
        Katalogdagi barcha ommabop kinolar va seriallarni (Taksi, Attack on Titan, Chuqur, Forsaj va boshqalar)
        Asilmedia.org ochiq API va sahifalari orqali batch sinxronlash, data/catalog.json va
        SQLite 'movies' jadvalini to'liq yangilash hamda video manbalarini boyitish.
        """
        global _CATALOG_CACHE
        from services.asilmedia_service import asilmedia_service
        from database.session import get_session

        catalog_path = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "catalog.json"
        items_to_sync = list(CUSTOM_CATALOG_ITEMS)
        seen_codes = {str(it.get("c")) for it in items_to_sync}

        # 1. Asilmedia ochiq API va katalog sahifalaridan yangi metadatalarni olish
        batch_items = []
        if pages > 0:
            try:
                batch_items = await asilmedia_service.fetch_catalog_batch(pages=pages)
            except Exception as be:
                logger.debug(f"fetch_catalog_batch error in sync_catalog_from_asilmedia: {be}")

        for bit in batch_items:
            iid = bit.get("id")
            if not iid:
                continue
            s_id = str(iid)
            if s_id in seen_codes:
                continue
            seen_codes.add(s_id)
            t_clean = MovieService.sanitize_branding(bit.get("title", ""))
            y_val = bit.get("year")
            genres = bit.get("genres", [])
            g_val = ", ".join(genres) if isinstance(genres, list) else str(genres or "Barcha")
            desc = bit.get("description") or (
                f"🎬 <b>{t_clean}</b>"
                + (f" ({y_val})" if y_val else "")
                + "\n\n"
                + (f"🎭 <b>Janr:</b> {g_val}\n" if g_val else "")
                + "📺 <b>Sifati:</b> 1080p | Full HD\n"
                + f"🤖 <b>Tomosha qilish:</b> @{config.BOT_USERNAME.lstrip('@')}\n"
                + f"📢 <b>Kino kanalimiz:</b> {config.CHANNEL_USERNAME}\n\n"
                + "👇 Ko'rish uchun quyidagi tugmani bosing!"
            )
            desc = MovieService.sanitize_branding(desc)
            items_to_sync.append({
                "c": int(iid) if s_id.isdigit() else iid,
                "t": t_clean,
                "p": bit.get("total_parts", 1),
                "v": bit.get("views", 2500),
                "d": desc,
                "a": iid,
                "i": iid,
                "p_url": bit.get("poster", ""),
                "type": "serial" if bit.get("is_series") else "film",
                "g": g_val,
                "y": y_val,
            })

        # 2. Mavjud catalog.json dagi kinolarni saqlab qolish
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

        # 3. catalog.json fayliga yozish va _CATALOG_CACHE ni yangilash
        cat_json = {
            "items": items_to_sync,
            "channel": config.CHANNEL_USERNAME,
            "bot": config.BOT_USERNAME.lstrip("@"),
        }
        if len(items_to_sync) >= 20:
            _CATALOG_CACHE = cat_json
            try:
                with open(catalog_path, "w", encoding="utf-8") as f:
                    json.dump(cat_json, f, ensure_ascii=False, indent=2)
            except Exception as fe:
                logger.warning(f"catalog.json saqlashda xatolik: {fe}")

        # 4. SQLite 'movies' jadvaliga yozish
        synced_db = 0
        try:
            if session:
                synced_db = await crud.sync_movies_from_catalog_data(session, items_to_sync)
            else:
                async with get_session() as s:
                    synced_db = await crud.sync_movies_from_catalog_data(s, items_to_sync)
                    await s.commit()
        except Exception as dbe:
            logger.debug(f"DB sync in sync_catalog_from_asilmedia error: {dbe}")

        # 5. limit bo'yicha video havolalarni boyitish
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

        result_count = count if count > 0 else (synced_db or len(batch_items) or len(items_to_sync))
        logger.info(f"Asilmedia katalog sinxronizatsiyasi: {result_count} ta kino/serial bog'landi/sinxronlandi.")
        return result_count


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

    try:
        await movie_service.sync_catalog_from_asilmedia(pages=2)
    except Exception as ae:
        logger.debug(f"Dastlabki Asilmedia batch sinxronizatsiyada ogohlantirish: {ae}")

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            synced = await movie_service.sync_catalog_from_upstream()
            if synced:
                logger.info(f"Davriy sinxronizatsiya: {synced} ta kino bazada yangilandi.")
            asil_synced = await movie_service.sync_catalog_from_asilmedia(pages=2)
            if asil_synced:
                logger.info(f"Davriy Asilmedia batch sinxronizatsiyasi: {asil_synced} ta yangi kino kiritildi.")
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
    orqa fonda Asilmedia.org orqali qismlari va video oqim havolalarini xotiraga tayyorlab qo'yuvchi engil sikl.
    Katta hajmli video fayllarni diskka yuklab olish (Render 512MB OOM/Disk xatari) qilinmaydi.
    """
    # Bot va web server tezkor ishga tushishi uchun orqa fon jarayonini biroz kechiktirib boshlaymiz
    await asyncio.sleep(15)
    logger.info("Asilmedia.org kinolar metama'lumotlari va video oqimlarini orqa fonda tayyorlash boshlandi...")
    try:
        for it in CUSTOM_CATALOG_ITEMS:
            c = str(it.get("c"))
            t = it.get("t", "")
            try:
                await MovieService.sync_movie_from_asilmedia(code=c, title=t, download_files=False)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Preloader for #{c} error: {e}")

        await MovieService.sync_catalog_from_asilmedia(limit=limit, download_files=False)
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

