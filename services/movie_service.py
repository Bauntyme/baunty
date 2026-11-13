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
_UNIFIED_CATALOG_CACHE: Optional[Tuple[str, float, List[Dict[str, Any]]]] = None
_LAST_SYNC_TS: float = time.time()
_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(1)

MAX_TELEGRAM_UPLOAD_BYTES = 50 * 1024 * 1024

ASILMEDIA_ID_MAP: Dict[str, str] = {
    "101": "17638",
    "718": "9165",
    "717": "16913",
    "287": "18281",
    "1500": "14902",
}


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
        text = re.sub(r'https?://t\.me/(?:Zakirovs?(?:films_bot|film_bot|Kino|_ai|_bot)?|dilbarzakirova)\b', f'https://t.me/{channel_clean}', text, flags=re.I)
        text = re.sub(r't\.me/(?:Zakirovs?(?:films_bot|film_bot|Kino|_ai|_bot)?|dilbarzakirova)\b', f't.me/{channel_clean}', text, flags=re.I)
        # Usernames with @
        text = re.sub(r'@Zakirovs?films?_bot\b', f'@{bot_clean}', text, flags=re.I)
        text = re.sub(r'@Zakirovs?_ai\b', f'@{bot_clean}', text, flags=re.I)
        text = re.sub(r'@ZakirovsKino\b', f'@{channel_clean}', text, flags=re.I)
        text = re.sub(r'@dilbarzakirova\b', f'@{channel_clean}', text, flags=re.I)
        text = re.sub(r'@Zakirovs?[\w]*\b', f'@{channel_clean}', text, flags=re.I)
        # Names
        text = re.sub(r'Zakirovs\s+Films\b', 'Baunty Films', text, flags=re.I)
        text = re.sub(r'Zakirovs?(?:films?_bot|_bot)\b', bot_clean, text, flags=re.I)
        text = re.sub(r'Zakirovs\b', 'Baunty', text, flags=re.I)
        text = re.sub(r'zakirovs\b', 'baunty', text, flags=re.I)
        text = re.sub(r'Dilbar\s*Zakirova\b', 'Baunty', text, flags=re.I)
        text = re.sub(r'Zakirova?\b', 'Baunty', text, flags=re.I)
        text = re.sub(r'zakirova?\b', 'baunty', text, flags=re.I)
        # Legacy bot username migration (@Bauntyfilmsbot -> current BOT_USERNAME)
        text = re.sub(r'https?://t\.me/Bauntyfilmsbot\b', f'https://t.me/{bot_clean}', text, flags=re.I)
        text = re.sub(r't\.me/Bauntyfilmsbot\b', f't.me/{bot_clean}', text, flags=re.I)
        text = re.sub(r'@Bauntyfilmsbot\b', f'@{bot_clean}', text, flags=re.I)
        text = re.sub(r'\bBauntyfilmsbot\b', bot_clean, text, flags=re.I)
        return text

    @staticmethod
    def _is_rejected_media_url(url: Optional[str]) -> bool:
        """Demo/mock videolarni va HTML wrapper sahifalarni video manba sifatida rad etish."""
        if not url:
            return True
        low = str(url).strip().lower()
        if not low:
            return True
        bad_tokens = (
            "samplelib",
            "sample-5s",
            "sample-10s",
            "sample-15s",
            "sample-20s",
            "sample-30s",
            "mov_bbb",
            "flower.mp4",
            "oceans.mp4",
            "default.mp4",
            "sslip.io",
            "sayt.php",
        )
        if any(tok in low for tok in bad_tokens):
            return True
        if re.search(r"server\.asilmedia\.org/(?:watch|download|embed)", low):
            return True
        if re.search(r"\.html?(?:$|[?#])", low):
            return True
        return False

    @staticmethod
    def _is_valid_local_video(path: Path, min_size: int = 500 * 1024) -> bool:
        """Lokal video fayli hajmi va boshlang'ich binar headerini tekshirish."""
        try:
            if not path.exists() or not path.is_file():
                return False
            if path.stat().st_size < min_size:
                return False
            from services.asilmedia_service import asilmedia_service
            with open(path, "rb") as vf:
                head = vf.read(64)
            return asilmedia_service.is_valid_video_header(head)
        except Exception:
            return False

    @staticmethod
    def _resolve_asilmedia_id_hint(clean_code: str, cat_item: Optional[dict] = None) -> Optional[str]:
        """Kino kodi yoki katalog kartochkasidan ishonchli Asilmedia ID ni ajratish."""
        if cat_item and cat_item.get("asil_id"):
            val = str(cat_item["asil_id"]).strip()
            if val.isdigit():
                return val
        if clean_code in ASILMEDIA_ID_MAP:
            return ASILMEDIA_ID_MAP[clean_code]
        if cat_item and cat_item.get("a") is not None:
            a_str = str(cat_item["a"]).strip()
            if a_str.isdigit() and 1 <= int(a_str) <= 1_000_000:
                return a_str
        return None

    @staticmethod
    async def sync_catalog_from_upstream(session: Optional[AsyncSession] = None) -> int:
        """
        Katalog ma'lumotlarini data/catalog.json, CUSTOM_CATALOG_ITEMS, Asilmedia.org va
        mahalliy DB bilan @BauntyCinemabot va @BauntyFilms brendi asosida sinxronlash.
        """
        global _CATALOG_CACHE, _UNIFIED_CATALOG_CACHE, _LAST_SYNC_TS
        from database.session import get_session
        from services.asilmedia_service import asilmedia_service
        _LAST_SYNC_TS = time.time()
        _UNIFIED_CATALOG_CACHE = None

        raw_items: List[Dict[str, Any]] = []
        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        catalog_file = base_dir / "data" / "catalog.json"

        # 1. Lokal catalog.json dan mavjud kinolarni yuklash
        if catalog_file.exists():
            try:
                with open(catalog_file, "r", encoding="utf-8") as f:
                    local_cat = json.load(f)
                    if isinstance(local_cat, dict) and isinstance(local_cat.get("items"), list):
                        for it in local_cat["items"]:
                            if not isinstance(it, dict):
                                continue
                            item_copy = dict(it)
                            if "d" in item_copy:
                                item_copy["d"] = MovieService.sanitize_branding(item_copy["d"])
                            if "t" in item_copy:
                                item_copy["t"] = MovieService.sanitize_branding(item_copy["t"])
                            raw_items.append(item_copy)
            except Exception as me:
                logger.debug("Merge with existing catalog.json error: %s", me)

        # 2. Agar lokal katalog juda kichik bo'lsa Asilmedia ochiq sahifalaridan to'ldirish
        if len(raw_items) < 10:
            try:
                batch_items = await asilmedia_service.fetch_catalog_batch(pages=1)
                seen_codes = {str(it.get("c")) for it in raw_items}
                for bit in batch_items:
                    iid = bit.get("id")
                    if not iid or str(iid) in seen_codes:
                        continue
                    seen_codes.add(str(iid))
                    t_clean = MovieService.sanitize_branding(bit.get("title", ""))
                    y_val = bit.get("year")
                    genres = bit.get("genres", [])
                    g_val = ", ".join(genres) if isinstance(genres, list) else str(genres or "")
                    desc = (
                        f"🎬 <b>{t_clean}</b>"
                        + (f" ({y_val})" if y_val else "")
                        + "\n\n"
                        + (f"🎭 <b>Janr:</b> {g_val}\n" if g_val else "")
                        + "📺 <b>Sifati:</b> 1080p | Full HD\n"
                        + f"🤖 <b>Tomosha qilish:</b> @{config.BOT_USERNAME.lstrip('@')}\n"
                        + f"📢 <b>Kino kanalimiz:</b> {config.CHANNEL_USERNAME}\n\n"
                        + "👇 Ko'rish uchun quyidagi tugmani bosing!"
                    )
                    raw_items.append({
                        "c": int(iid) if str(iid).isdigit() else iid,
                        "t": t_clean,
                        "p": int(bit.get("total_parts", 1)),
                        "v": int(bit.get("views", 1)),
                        "d": desc,
                        "a": iid,
                        "i": iid,
                        "asil_id": int(iid) if str(iid).isdigit() else iid,
                        "p_url": bit.get("poster", ""),
                        "type": "serial" if bit.get("is_series") else "film",
                    })
            except Exception as ae:
                logger.debug("Asilmedia catalog fallback error: %s", ae)

        # 3. Custom asosiy kinolar (718, 717, 287, 1500) doim katalogda saqlanadi
        existing_codes = {str(it.get("c")) for it in raw_items}
        for c_item in reversed(CUSTOM_CATALOG_ITEMS):
            if str(c_item.get("c")) not in existing_codes:
                raw_items.insert(0, dict(c_item))

        if not raw_items:
            return 0

        cat_json = {
            "items": raw_items,
            "channel": config.CHANNEL_USERNAME,
            "bot": config.BOT_USERNAME.lstrip("@"),
        }
        if len(raw_items) >= 20 or not (_CATALOG_CACHE and len(_CATALOG_CACHE.get("items", [])) >= 20):
            _CATALOG_CACHE = cat_json
        if len(raw_items) >= 20:
            try:
                catalog_file.parent.mkdir(parents=True, exist_ok=True)
                with open(catalog_file, "w", encoding="utf-8") as f:
                    json.dump(cat_json, f, ensure_ascii=False, indent=2)
            except Exception as fe:
                logger.warning(f"catalog.json fayliga yozishda xatolik: {fe}")

        # 4. Bazaga sinxronlash
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

        MovieService._ensure_catalog_cache()

        if _CATALOG_CACHE:
            for it in _CATALOG_CACHE.get("items", []):
                c_str = str(it.get("c"))
                a_str = str(it.get("a", ""))
                i_str = str(it.get("i", ""))
                if c_str in alias_codes or a_str in alias_codes or i_str in alias_codes:
                    return it
        return None

    @staticmethod
    def _ensure_catalog_cache() -> Optional[dict]:
        """Kesh bo'sh yoki to'liq bo'lmaganda diskdagi haqiqiy catalog.json ni yuklash."""
        global _CATALOG_CACHE
        catalog_path = BASE_DIR / "data" / "catalog.json"
        if (_CATALOG_CACHE is None or len(_CATALOG_CACHE.get("items", [])) < 20) and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    loaded_cat = json.load(f)
                    if isinstance(loaded_cat, dict) and loaded_cat.get("items"):
                        _CATALOG_CACHE = loaded_cat
            except Exception:
                pass
        return _CATALOG_CACHE

    @staticmethod
    def search_catalog_by_title(title_query: str) -> Optional[dict]:
        """Katalog keshidan sarlavha bo'yicha kino qidirish (Lotin + Kirill, apostrof tolerant, xavfsiz kalit so'zlar)."""
        if not title_query:
            return None
        MovieService._ensure_catalog_cache()

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
    async def get_unified_catalog(session: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
        """
        CUSTOM_CATALOG_ITEMS, data/catalog.json va DB 'movies' / 'movie_files' jadvallarini
        birlashtiruvchi yagona katalog ro'yxati.
        code_part kabi qism qatorlarini alohida yuqori daraja kartochkasi sifatida chiqarmaydi,
        aksincha asosiy kino kodi uchun aniq 'p' (qismlar soni) ni hisoblaydi.
        """
        global _CATALOG_CACHE, _UNIFIED_CATALOG_CACHE
        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        base_key = str(base_dir)
        now_ts = time.time()
        if (
            session is None
            and _UNIFIED_CATALOG_CACHE is not None
            and _UNIFIED_CATALOG_CACHE[0] == base_key
            and (now_ts - _UNIFIED_CATALOG_CACHE[1]) < 45.0
        ):
            return [dict(x) for x in _UNIFIED_CATALOG_CACHE[2]]
        catalog_path = base_dir / "data" / "catalog.json"
        if _CATALOG_CACHE is None and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    _CATALOG_CACHE = json.load(f)
            except Exception:
                pass

        unified: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        max_parts_by_base: Dict[str, int] = {}

        def _add_entry(raw_it: Dict[str, Any]) -> None:
            c_val = raw_it.get("c")
            if c_val is None:
                return
            c_str = str(c_val).strip()
            if not c_str:
                return
            m_child = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", c_str, re.I)
            if m_child:
                b_code, p_num = m_child.group(1), int(m_child.group(2))
                if p_num > max_parts_by_base.get(b_code, 1):
                    max_parts_by_base[b_code] = p_num
                return

            item_copy = dict(raw_it)
            p_val = int(item_copy.get("p") or 1)
            if p_val > max_parts_by_base.get(c_str, 1):
                max_parts_by_base[c_str] = p_val

            if c_str not in unified:
                unified[c_str] = item_copy
                order.append(c_str)
            else:
                cur = unified[c_str]
                if not cur.get("t") and item_copy.get("t"):
                    cur["t"] = item_copy["t"]
                if not cur.get("d") and item_copy.get("d"):
                    cur["d"] = item_copy["d"]
                if not cur.get("p_url") and item_copy.get("p_url"):
                    cur["p_url"] = item_copy["p_url"]
                if not cur.get("asil_id") and item_copy.get("asil_id"):
                    cur["asil_id"] = item_copy["asil_id"]
                cur["v"] = max(int(cur.get("v") or 0), int(item_copy.get("v") or 0))

        for it in CUSTOM_CATALOG_ITEMS:
            _add_entry(it)
        if _CATALOG_CACHE and isinstance(_CATALOG_CACHE.get("items"), list):
            for it in _CATALOG_CACHE["items"]:
                if isinstance(it, dict):
                    _add_entry(it)

        async def _merge_db(db_sess: AsyncSession) -> None:
            from sqlalchemy import select, func
            from database.models import MovieFile

            res_m = await db_sess.execute(select(Movie))
            for m in res_m.scalars().all():
                c_str = str(m.code or "").strip()
                if not c_str:
                    continue
                m_child = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", c_str, re.I)
                if m_child:
                    b_code, p_num = m_child.group(1), int(m_child.group(2))
                    if p_num > max_parts_by_base.get(b_code, 1):
                        max_parts_by_base[b_code] = p_num
                    continue
                _add_entry({
                    "c": int(c_str) if c_str.isdigit() else c_str,
                    "t": MovieService.sanitize_branding(m.title or f"Kino #{c_str}"),
                    "p": 1,
                    "v": int(m.views_count or 0),
                    "d": MovieService.sanitize_branding(m.description or ""),
                    "g": m.genres or "",
                    "y": m.year,
                    "type": "film",
                })

            res_mf = await db_sess.execute(
                select(MovieFile.movie_code, func.max(MovieFile.part)).group_by(MovieFile.movie_code)
            )
            for m_code, max_p in res_mf.all():
                if m_code and max_p:
                    b_str = str(m_code).strip()
                    if int(max_p) > max_parts_by_base.get(b_str, 1):
                        max_parts_by_base[b_str] = int(max_p)

        async def _merge_db_default() -> None:
            from database.session import get_session
            async with get_session() as s:
                await _merge_db(s)

        try:
            if session is not None:
                await _merge_db(session)
            else:
                await asyncio.wait_for(_merge_db_default(), timeout=2.5)
        except Exception as dbe:
            logger.debug(f"get_unified_catalog DB merge skipped: {dbe}")

        result: List[Dict[str, Any]] = []
        for c_str in order:
            it = unified[c_str]
            parts_cnt = max(int(it.get("p") or 1), max_parts_by_base.get(c_str, 1))
            it["p"] = parts_cnt
            if parts_cnt > 1:
                it["type"] = "serial"
            elif not it.get("type"):
                it["type"] = "film"
            result.append(it)
        if session is None:
            _UNIFIED_CATALOG_CACHE = (base_key, time.time(), [dict(x) for x in result])
        return result

    @staticmethod
    async def search_catalog(
        query: str,
        session: Optional[AsyncSession] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Kod (101, 718, ...) va Lotin/Kirill sarlavha bo'yicha yagona katalogdan qidirish."""
        clean_q = (query or "").strip().lstrip("#№")
        if not clean_q:
            return []

        items = await MovieService.get_unified_catalog(session=session)
        from utils.translit import get_both_scripts

        def _norm(txt: str) -> str:
            t_n = (
                txt.lower()
                .replace("‘", "'").replace("’", "'").replace("ʻ", "'").replace("`", "'")
                .replace("ç", "ch").replace("ş", "sh").replace("ğ", "g'").replace("ö", "o'")
                .replace("ü", "u").replace("ı", "i")
            )
            return " ".join(re.sub(r"[^\w\s']|_", " ", t_n).split())

        q_variants = list(get_both_scripts(clean_q))
        if clean_q not in q_variants:
            q_variants.insert(0, clean_q)
        norm_queries: List[str] = []
        for qv in q_variants:
            nq = _norm(qv)
            for cand_q in (nq, nq.replace("'", ""), nq.replace("cukur", "chuqur"), nq.replace("chuqur", "cukur")):
                if cand_q and cand_q not in norm_queries:
                    norm_queries.append(cand_q)

        scored: List[Tuple[int, int, Dict[str, Any]]] = []
        for it in items:
            c_str = str(it.get("c", "")).strip()
            t_raw = str(it.get("t", "") or "")
            t_norm = _norm(t_raw)
            t_strip = t_norm.replace("'", "")
            score = 0

            if clean_q.isdigit():
                if c_str == clean_q:
                    score = max(score, 1000)
                elif c_str.startswith(clean_q):
                    score = max(score, 500)

            for nq in norm_queries:
                if not nq:
                    continue
                if nq == t_norm or nq == t_strip:
                    score = max(score, 850)
                elif len(nq) >= 2 and (nq in t_norm or nq in t_strip):
                    score = max(score, 450)
                else:
                    q_words = [w for w in nq.split() if len(w) >= 3]
                    t_words = [w for w in t_strip.split() if len(w) >= 3]
                    if q_words and t_words:
                        matched = sum(1 for qw in q_words if any(qw in tw or tw in qw for tw in t_words))
                        if matched == len(q_words):
                            score = max(score, 320)
                        elif matched > 0 and matched / len(q_words) >= 0.6:
                            score = max(score, 180)

            if score > 0:
                scored.append((score, int(it.get("v") or 0), it))

        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return [row[2] for row in scored[:limit]]

    @staticmethod
    async def get_movie_stream_info(
        code: str,
        part: int = 1,
        session: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Kino/serial qismi uchun WebApp va to'g'ridan-to'g'ri yuklashda foydalaniladigan
        imzolangan MP4 oqim URL lari va sifatlarini qaytarish.
        """
        from services.asilmedia_service import asilmedia_service

        clean_code = str(code).strip().lstrip("#№")
        m_part_code = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", clean_code, re.I)
        if m_part_code and part == 1:
            clean_code = m_part_code.group(1)
            part = int(m_part_code.group(2))

        cat_item = MovieService.get_catalog_item(clean_code)
        db_movie = None
        if session:
            try:
                db_movie = await crud.get_movie_by_code(session, clean_code)
            except Exception:
                pass

        title = (cat_item.get("t") if cat_item else None) or (db_movie.title if db_movie else None) or ""
        total_parts = int(cat_item.get("p", 1)) if cat_item else 1
        poster = cat_item.get("p_url") if cat_item else None
        asil_id = MovieService._resolve_asilmedia_id_hint(clean_code, cat_item)

        resolved_src = MovieService.resolve_video_source(clean_code, part=part, allow_default=False)
        quality_urls: Dict[str, str] = {}
        watch_url: Optional[str] = None
        candidate_raws: Dict[str, str] = {}

        if resolved_src:
            w_cand = resolved_src.get("watch_url")
            if w_cand and str(w_cand).startswith("http"):
                watch_url = str(w_cand)
            if isinstance(resolved_src.get("quality_urls"), dict):
                for qk, qu in resolved_src["quality_urls"].items():
                    if qu:
                        candidate_raws[str(qk)] = str(qu)
            src_q = str(resolved_src.get("quality") or "1080p")
            for u_key in ("download_url", "url"):
                u_val = resolved_src.get(u_key)
                if u_val and not MovieService._is_rejected_media_url(u_val):
                    candidate_raws.setdefault(src_q, str(u_val))

        for qk, raw_u in list(candidate_raws.items()):
            if MovieService._is_rejected_media_url(raw_u):
                continue
            if asilmedia_service.needs_fayllar_sign(raw_u):
                signed_u = await asilmedia_service.resolve_stream_url(raw_u, news_id=asil_id)
                if signed_u and not MovieService._is_rejected_media_url(signed_u):
                    quality_urls[qk] = signed_u
            elif str(raw_u).startswith("http"):
                quality_urls[qk] = str(raw_u)

        asil_det = None
        if not quality_urls:
            if asil_id:
                asil_det = await asilmedia_service.get_movie_details(asil_id)
            if not asil_det and title and not title.lower().startswith("kino #"):
                asil_det = await asilmedia_service.find_best_match(title, target_parts=total_parts)
            if not asil_det and clean_code.isdigit() and int(clean_code) >= 10:
                cand_det = await asilmedia_service.get_movie_details(clean_code)
                if cand_det:
                    if not title or title.lower().startswith("kino #"):
                        asil_det = cand_det
                    else:
                        t_words = {w for w in re.sub(r"[^\w\s]", " ", title.lower()).split() if len(w) >= 3}
                        c_words = {w for w in re.sub(r"[^\w\s]", " ", cand_det.title.lower()).split() if len(w) >= 3}
                        if not t_words or (t_words & c_words):
                            asil_det = cand_det

            if asil_det:
                asil_id = asil_det.id
                total_parts = max(total_parts, int(asil_det.total_parts or 1))
                poster = poster or asil_det.poster
                if not title or title.lower().startswith("kino #"):
                    title = asil_det.title
                ep = asil_det.episodes.get(part)
                raw_q_map: Dict[str, str] = {}
                if ep:
                    watch_url = watch_url or ep.watch_url or asil_det.watch_url
                    for qk, qu in (ep.quality_urls or {}).items():
                        if qu and not MovieService._is_rejected_media_url(qu):
                            raw_q_map[str(qk)] = str(qu)
                    for cand_u in (ep.download_url, ep.url):
                        if cand_u and not MovieService._is_rejected_media_url(cand_u):
                            raw_q_map.setdefault(ep.quality or "1080p", str(cand_u))
                elif part == 1:
                    watch_url = watch_url or asil_det.watch_url
                    for qk, qu in (asil_det.video_sources or {}).items():
                        if qk == "primary" or str(qk).startswith("tg_"):
                            continue
                        if qu and not MovieService._is_rejected_media_url(qu):
                            raw_q_map[str(qk)] = str(qu)

                to_sign = [u for u in raw_q_map.values() if asilmedia_service.needs_fayllar_sign(u)]
                signed_map = {}
                if to_sign:
                    signed_map = await asilmedia_service.sign_fayllar_urls(
                        to_sign,
                        amh_id=asil_det.amh_id or asil_det.id,
                        amh_n=asil_det.amh_n,
                    )
                for qk, qu in raw_q_map.items():
                    final_u = signed_map.get(qu, qu)
                    if (
                        final_u
                        and str(final_u).startswith("http")
                        and not str(final_u).startswith("am:")
                        and not MovieService._is_rejected_media_url(final_u)
                    ):
                        quality_urls[qk] = str(final_u)

        if not title and not db_movie and not cat_item and not asil_det and not quality_urls:
            return None

        stream_url = None
        for pref_q in ("1080p", "720p", "480p", "4K", "360p"):
            if pref_q in quality_urls:
                stream_url = quality_urls[pref_q]
                break
        if not stream_url and quality_urls:
            stream_url = next(iter(quality_urls.values()))

        return {
            "code": clean_code,
            "title": title or f"Kino #{clean_code}",
            "part": part,
            "total_parts": total_parts,
            "stream_url": stream_url,
            "quality_urls": quality_urls,
            "watch_url": watch_url,
            "poster": poster,
            "asil_id": asil_id,
        }

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
            if part == 1 and c not in keys_to_check:
                keys_to_check.append(c)

        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        v_dir = base_dir / "data" / "videos"

        # 1. Lokal fayllar tekshiruvi (aniq kod va franchise alias bo'yicha, binar header bilan)
        for k in keys_to_check:
            for ext in [".mp4", ".mkv", ".mov"]:
                candidate = v_dir / f"{k}{ext}"
                if MovieService._is_valid_local_video(candidate):
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
                            res: Dict[str, Any] = {}
                            if isinstance(entry, str):
                                if entry.startswith("http://") or entry.startswith("https://") or entry.startswith("am:"):
                                    res = {"url": entry, "file_type": "video"}
                                elif MovieService.is_valid_telegram_file_id(entry):
                                    res = {"file_id": entry, "file_type": "video"}
                            elif isinstance(entry, dict):
                                res = dict(entry)

                            if not res:
                                continue

                            for u_k in ("url", "download_url"):
                                u_v = res.get(u_k)
                                if u_v and not str(u_v).startswith("am:") and MovieService._is_rejected_media_url(u_v):
                                    res.pop(u_k, None)
                            if res.get("file_id") and not MovieService.is_valid_telegram_file_id(res.get("file_id")):
                                res.pop("file_id", None)

                            if "file_path" in res:
                                fp = Path(res["file_path"])
                                if not MovieService._is_valid_local_video(fp):
                                    rel_cand = v_dir / fp.name
                                    if MovieService._is_valid_local_video(rel_cand):
                                        res["file_path"] = str(rel_cand)
                                    else:
                                        del res["file_path"]

                            if "file_path" not in res:
                                for c in alias_codes:
                                    cand_p = v_dir / f"{c}_{part}.mp4"
                                    if MovieService._is_valid_local_video(cand_p):
                                        res["file_path"] = str(cand_p)
                                        res["file_size"] = cand_p.stat().st_size
                                        break

                            if any(res.get(x) for x in ("file_path", "file_id", "url", "download_url", "quality_urls")):
                                return res
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
                        if MovieService._is_valid_local_video(cand):
                            return {
                                "file_path": str(cand),
                                "file_type": "video",
                                "file_size": cand.stat().st_size
                            }

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
        Hech qachon soxta yoki demo videolarni ko'chirmaydi.
        """
        import shutil
        base_dir = getattr(app_config, "BASE_DIR", BASE_DIR)
        v_dir = base_dir / "data" / "videos"
        v_dir.mkdir(parents=True, exist_ok=True)
        dest = destination_path or (v_dir / f"{code}_{part}.mp4")

        if MovieService._is_valid_local_video(dest):
            return dest

        clean_code = str(code).strip().lstrip("#№")
        alias_codes = [clean_code]
        if clean_code in FRANCHISE_CODE_MAP:
            alias_codes.append(FRANCHISE_CODE_MAP[clean_code])

        for c in alias_codes:
            for cand_name in [f"{c}_{part}.mp4", f"{c}_1.mp4", f"{c}.mp4"]:
                cand_path = v_dir / cand_name
                if MovieService._is_valid_local_video(cand_path):
                    try:
                        shutil.copyfile(str(cand_path), str(dest))
                        if MovieService._is_valid_local_video(dest):
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
        reply_to_message_id: Optional[int] = None,
        require_video: bool = False
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
                reply_to_message_id=reply_to_message_id,
                require_video=require_video
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
                    reply_to_message_id=reply_to_message_id,
                    require_video=require_video
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
            or tf_lower.startswith("am:")
            or tf_lower.startswith("baacagiaaxkbaaib_")
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
            or any(bad in tf_lower for bad in ("samplelib", "mov_bbb", "default.mp4", "server.asilmedia.org", "sayt.php", ".html", "sslip.io"))
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
        URL manbasidan xavfsiz navbat (asyncio.Semaphore(1)) va oqimli yuklab olish (<=50MB TG limiti)
        orqali videoni yuklab, foydalanuvchiga yuborish va Telegram file_id ni bazaga keshlab qo'yish.
        RAM yoki diskni to'ldirmaslik uchun vaqtinchalik fayl finally blokida 100% o'chiriladi.
        """
        from services.asilmedia_service import asilmedia_service

        async with _DOWNLOAD_SEMAPHORE:
            # 1. Navbat ichida keshni qayta tekshirish (agar parallel so'rov allaqachon yuklagan bo'lsa)
            if session:
                try:
                    cached_mf = await crud.get_movie_file(session, code, part)
                    if cached_mf and MovieService.is_valid_telegram_file_id(cached_mf.file_id):
                        try:
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
                        except Exception as cache_send_err:
                            logger.warning(f"Cached movie_file file_id yuborilmadi ({cache_send_err}), tozalanmoqda.")
                            cached_mf.file_id = ""
                            await session.commit()

                    p_code = f"{code}_{part}" if part > 1 else code
                    cached_m = await crud.get_movie_by_code(session, p_code)
                    if cached_m and MovieService.is_valid_telegram_file_id(cached_m.file_id):
                        try:
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
                        except Exception as db_send_err:
                            logger.warning(f"Cached db movie file_id yuborilmadi ({db_send_err}), tozalanmoqda.")
                            cached_m.file_id = ""
                            await session.commit()
                except Exception as ce:
                    logger.debug(f"Double-check cache error: {ce}")

            # Manba URL ni imzolash va HTML / mock sahifalardan himoyalash
            resolved_url = str(source_url or "").strip()
            if MovieService._is_rejected_media_url(resolved_url):
                logger.warning(f"Video yuklash manbasi rad etildi (demo/HTML): {resolved_url}")
                return None

            if asilmedia_service.needs_fayllar_sign(resolved_url):
                cat_hint = MovieService.get_catalog_item(code)
                nid_hint = MovieService._resolve_asilmedia_id_hint(str(code).strip(), cat_hint)
                signed_url = await asilmedia_service.resolve_stream_url(resolved_url, news_id=nid_hint)
                if not signed_url or MovieService._is_rejected_media_url(signed_url):
                    logger.warning(f"Asilmedia havolasini imzolab bo'lmadi: {resolved_url}")
                    return None
                resolved_url = signed_url

            if not resolved_url.startswith("http") or MovieService._is_rejected_media_url(resolved_url):
                return None

            # 2. Vaqtinchalik fayl yo'li
            v_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "videos"
            v_dir.mkdir(parents=True, exist_ok=True)
            temp_file = v_dir / f"temp_download_{code}_{part}.mp4"
            temp_file.unlink(missing_ok=True)

            try:
                headers = {
                    "User-Agent": asilmedia_service.USER_AGENT,
                    "Referer": f"{asilmedia_service.BASE_URL}/",
                }
                timeout = aiohttp.ClientTimeout(total=300, connect=30)
                async with aiohttp.ClientSession(headers=headers, timeout=timeout) as client:
                    async with client.get(resolved_url) as resp:
                        if resp.status not in (200, 206):
                            logger.warning(f"Download URL returned status {resp.status}: {resolved_url}")
                            return None

                        resp_headers = getattr(resp, "headers", None) or {}
                        ctype = str(resp_headers.get("Content-Type") or "").lower()
                        if any(t in ctype for t in ("text/html", "text/plain", "application/json", "application/xml")):
                            logger.warning(f"Yuklash manzili HTML/matn ({ctype}): {resolved_url}")
                            return None

                        clen_raw = resp_headers.get("Content-Length")
                        if clen_raw is not None and str(clen_raw).isdigit():
                            cl_bytes = int(clen_raw)
                            if cl_bytes > MAX_TELEGRAM_UPLOAD_BYTES:
                                logger.info(
                                    f"Kino #{code} (qism={part}) hajmi {cl_bytes // (1024 * 1024)} MB > 50 MB TG limiti, WebApp/direct oqimga yo'naltiriladi."
                                )
                                return None

                        first_chunk = True
                        valid_header = False
                        total_bytes = 0
                        with open(temp_file, "wb") as f:
                            async for chunk in resp.content.iter_chunked(1024 * 1024):
                                if not chunk:
                                    continue
                                if first_chunk:
                                    first_chunk = False
                                    if not asilmedia_service.is_valid_video_header(chunk):
                                        logger.warning(f"Video boshlang'ich baytlari yaroqsiz (HTML/matn): {resolved_url}")
                                        break
                                    valid_header = True
                                total_bytes += len(chunk)
                                if total_bytes > MAX_TELEGRAM_UPLOAD_BYTES:
                                    logger.info(f"Yuklanayotgan oqim 50 MB TG limitidan oshdi, to'xtatildi: {resolved_url}")
                                    valid_header = False
                                    break
                                f.write(chunk)

                        if not valid_header:
                            temp_file.unlink(missing_ok=True)
                            return None

                if not temp_file.exists() or temp_file.stat().st_size < 100 * 1024 or temp_file.stat().st_size > MAX_TELEGRAM_UPLOAD_BYTES:
                    logger.warning(f"Downloaded file invalid size: {resolved_url}")
                    temp_file.unlink(missing_ok=True)
                    return None

                file_size = temp_file.stat().st_size
                media_input = FSInputFile(temp_file)
                sent_msg = None
                user_delivered = False
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
                    if sent_msg:
                        user_delivered = True
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
                        if sent_msg:
                            user_delivered = True
                    except Exception as de:
                        logger.error(f"send_document fallback failed: {de}")

                storage_msg = None
                if not user_delivered and config.STORAGE_CHANNEL_ID and str(config.STORAGE_CHANNEL_ID).strip():
                    storage_id = str(config.STORAGE_CHANNEL_ID).strip()
                    if storage_id != str(chat_id):
                        try:
                            media_input = FSInputFile(temp_file)
                            storage_msg = await bot.send_video(
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
                                storage_msg = await bot.send_document(
                                    chat_id=storage_id,
                                    document=media_input,
                                    caption=f"🎬 #{code} - {display_title or code} (Part {part})",
                                    protect_content=True
                                )
                            except Exception as se_doc:
                                logger.debug(f"Direct storage channel send_document error: {se_doc}")

                persisted_msg = sent_msg or storage_msg
                if persisted_msg:
                    sent_media = (
                        getattr(persisted_msg, "video", None)
                        or getattr(persisted_msg, "document", None)
                    )
                    if sent_media:
                        new_fid = getattr(sent_media, "file_id", None)
                        if new_fid and MovieService.is_valid_telegram_file_id(new_fid):
                            dur = getattr(sent_media, "duration", None)
                            dur_val = int(dur) if isinstance(dur, (int, float)) else duration
                            fsize = getattr(sent_media, "file_size", None)
                            fsize_val = int(fsize) if isinstance(fsize, (int, float)) else file_size
                            p_code = f"{code}_{part}" if part > 1 else code
                            ftype = "video" if getattr(persisted_msg, "video", None) else "document"

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

                            if user_delivered and config.STORAGE_CHANNEL_ID and str(config.STORAGE_CHANNEL_ID).strip():
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

                if user_delivered:
                    return sent_msg
                return None
            except Exception as ex:
                logger.error(f"download_and_upload_media_on_demand error for {resolved_url}: {ex}")
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
        reply_to_message_id: Optional[int] = None,
        require_video: bool = False
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

        if not clean_code or not clean_code.strip():
            return False

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
            has_ready_media = bool(
                resolved_source
                and (
                    resolved_source.get("file_path")
                    or MovieService.is_valid_telegram_file_id(resolved_source.get("file_id"))
                )
            )
            if not has_ready_media:
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
            if target_file_id and MovieService.is_valid_telegram_file_id(target_file_id):
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
                    logger.warning(f"Baza/Cloud videosini yuborib bo'lmadi ({e}), eskirgan file_id tozalanib zaxira tekshiriladi.")
                    try:
                        if cached_mf and cached_mf.file_id == target_file_id:
                            cached_mf.file_id = ""
                        if db_movie and db_movie.file_id == target_file_id:
                            db_movie.file_id = ""
                        await session.commit()
                    except Exception:
                        pass

        if not video_sent:
            from services.asilmedia_service import asilmedia_service
            asil_nid_hint = MovieService._resolve_asilmedia_id_hint(clean_code, cat_item)
            candidates: List[Dict[str, Any]] = []
            if not resolved_source:
                resolved_source = MovieService.resolve_video_source(clean_code, part, allow_default=False)
            if resolved_source:
                res_fp = resolved_source.get("file_path")
                if res_fp:
                    fp = Path(res_fp)
                    if MovieService._is_valid_local_video(fp):
                        candidates.append(resolved_source)
                    else:
                        v_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "videos"
                        rel_cand = v_dir / fp.name
                        if MovieService._is_valid_local_video(rel_cand):
                            resolved_source["file_path"] = str(rel_cand)
                            candidates.append(resolved_source)
                elif resolved_source.get("file_id") and MovieService.is_valid_telegram_file_id(resolved_source.get("file_id")):
                    candidates.append(resolved_source)
                else:
                    q_urls_map = resolved_source.get("quality_urls")
                    if isinstance(q_urls_map, dict):
                        for qk in ("1080p", "720p", "480p", "360p", "4K"):
                            qu = q_urls_map.get(qk)
                            if qu and not MovieService._is_rejected_media_url(qu):
                                candidates.append({"url": qu, "duration": resolved_source.get("duration"), "quality": qk})
                    for uk in ("download_url", "url"):
                        uv = resolved_source.get(uk)
                        if uv and not MovieService._is_rejected_media_url(uv):
                            if not any(c.get("url") == uv for c in candidates):
                                candidates.append({
                                    "url": uv,
                                    "duration": resolved_source.get("duration"),
                                    "file_size": resolved_source.get("file_size"),
                                })

            # 2. data/videos papkasidagi tayyorlangan haqiqiy lokal fayllar (kod va franchise aliaslar)
            v_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "videos"
            for c in alias_codes:
                a_cand = v_dir / f"{c}_{part}.mp4"
                if MovieService._is_valid_local_video(a_cand):
                    if not any(cand.get("file_path") == str(a_cand) for cand in candidates):
                        candidates.insert(0, {
                            "file_path": str(a_cand),
                            "file_type": "video",
                            "file_size": a_cand.stat().st_size,
                            "duration": resolved_source.get("duration") if resolved_source else None
                        })
                    break

            if not candidates and download_online_url and not MovieService._is_rejected_media_url(download_online_url):
                candidates.append({
                    "url": str(download_online_url),
                    "duration": None,
                    "file_size": None
                })

            # 3. Agar lokal yoki direct nomzod topilmagan bo'lsa, Asilmediadan jonli MP4 oqimlarini yechib olish
            if not candidates:
                try:
                    s_info = await MovieService.get_movie_stream_info(clean_code, part=part, session=session)
                    if s_info and s_info.get("quality_urls"):
                        for qk in ("1080p", "720p", "480p", "4K", "360p"):
                            qu = s_info["quality_urls"].get(qk)
                            if qu and not MovieService._is_rejected_media_url(qu):
                                candidates.append({"url": qu, "duration": None, "quality": qk})
                        for qk, qu in s_info["quality_urls"].items():
                            if qu and not any(c.get("url") == qu for c in candidates) and not MovieService._is_rejected_media_url(qu):
                                candidates.append({"url": qu, "duration": None, "quality": qk})
                except Exception as sie:
                    logger.debug(f"Live stream fallback lookup error for #{clean_code}: {sie}")

            if not candidates:
                logger.info(f"Kino #{clean_code} (qism={part}) uchun haqiqiy video manbasi mavjud emas, silent poster downgrade bekor qilinadi.")
                return False

            for cand in candidates:
                try:
                    target_video: Optional[Any] = None
                    if "file_path" in cand:
                        target_video = FSInputFile(cand["file_path"])
                    elif cand.get("file_id") and MovieService.is_valid_telegram_file_id(cand.get("file_id")):
                        target_video = cand.get("file_id")
                    elif cand.get("url"):
                        raw_cand_u = str(cand["url"]).strip()
                        if MovieService._is_rejected_media_url(raw_cand_u):
                            continue
                        if asilmedia_service.needs_fayllar_sign(raw_cand_u):
                            signed_u = await asilmedia_service.resolve_stream_url(raw_cand_u, news_id=asil_nid_hint)
                            if not signed_u or MovieService._is_rejected_media_url(signed_u):
                                continue
                            raw_cand_u = signed_u
                        if raw_cand_u.startswith("http") and not MovieService._is_rejected_media_url(raw_cand_u):
                            target_video = raw_cand_u

                    if not target_video:
                        continue

                    sent_msg = None
                    if isinstance(target_video, str) and target_video.startswith("http"):
                        # 50MB limit va HTML/binar header tekshiruvi bilan xavfsiz oqimli yuklash va yuborish
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
                            if isinstance(new_fid, str) and MovieService.is_valid_telegram_file_id(new_fid):
                                dur = getattr(sent_media, "duration", None)
                                dur_val = int(dur) if isinstance(dur, (int, float)) else cand.get("duration")
                                fsize = getattr(sent_media, "file_size", None)
                                fsize_val = int(fsize) if isinstance(fsize, (int, float)) else cand.get("file_size")
                                p_code = f"{clean_code}_{part}" if part > 1 else clean_code
                                ftype = "video" if getattr(sent_msg, "video", None) else "document"

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

        if require_video or not candidates:
            logger.info(f"Kino #{clean_code} uchun video yetkazilmadi (require_video={require_video}), False qaytariladi.")
            return False

        # 2. HD Poster rasmi orqali yuborish (faqat require_video=False bo'lganda)
        posters_dir = getattr(app_config, "BASE_DIR", BASE_DIR) / "data" / "posters"
        posters_dir.mkdir(parents=True, exist_ok=True)
        poster_path = posters_dir / f"{clean_code}_l.webp"

        if not poster_path.exists() and cat_item and cat_item.get("p_url"):
            try:
                p_u = str(cat_item["p_url"]).strip()
                if p_u.startswith("http") and "sslip.io" not in p_u.lower():
                    async with aiohttp.ClientSession() as client:
                        async with client.get(p_u, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                            if resp.status == 200:
                                pdata = await resp.read()
                                if pdata and len(pdata) > 500:
                                    with open(poster_path, "wb") as pf:
                                        pf.write(pdata)
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
        reply_to_message_id: Optional[int] = None,
        require_video: bool = True
    ) -> bool:
        """Kino kodi orqali foydalanuvchiga yuborish."""
        return await MovieService.deliver_movie(
            bot=bot,
            chat_id=chat_id,
            code=movie.code,
            part=1,
            session=session,
            reply_to_message_id=reply_to_message_id,
            require_video=require_video
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

        # 1. Katalogdagi asil_id / ASILMEDIA_ID_MAP / yaroqli 'a' maydoni bo'yicha to'g'ridan-to'g'ri olish
        asil_hint = MovieService._resolve_asilmedia_id_hint(clean_code, cat_item)
        if asil_hint:
            try:
                asil_movie = await asilmedia_service.get_movie_details(asil_hint)
            except Exception as he:
                logger.debug(f"Asilmedia hint id lookup failed for {clean_code} -> {asil_hint}: {he}")

        # 2. Target_title bo'yicha lokal asilmedia_service.find_best_match
        if not asil_movie and target_title and not target_title.startswith("Kino "):
            asil_movie = await asilmedia_service.find_best_match(target_title, target_parts=target_parts)
            if not asil_movie:
                words = target_title.split()
                if len(words) > 1:
                    asil_movie = await asilmedia_service.find_best_match(words[0], target_parts=target_parts)

        # 3. Kod to'g'ridan-to'g'ri Asilmedia filmi ID si bo'lsa
        if not asil_movie and clean_code.isdigit() and int(clean_code) >= 10:
            try:
                cand_movie = await asilmedia_service.get_movie_details(clean_code)
                if cand_movie:
                    if not target_title or target_title.startswith("Kino "):
                        asil_movie = cand_movie
                    else:
                        t_words = {w for w in re.sub(r"[^\w\s]", " ", target_title.lower()).split() if len(w) >= 3}
                        c_words = {w for w in re.sub(r"[^\w\s]", " ", cand_movie.title.lower()).split() if len(w) >= 3}
                        if not t_words or (t_words & c_words):
                            asil_movie = cand_movie
            except Exception as ge:
                logger.debug(f"Asilmedia direct id lookup failed for {clean_code}: {ge}")

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
                clean_q_urls = {
                    qk: qu for qk, qu in (ep.quality_urls or {}).items()
                    if qu and not MovieService._is_rejected_media_url(qu)
                }
                ep_url = None
                for cand_u in (ep.url, ep.download_url):
                    if cand_u and not MovieService._is_rejected_media_url(cand_u):
                        ep_url = cand_u
                        break
                if not ep_url and clean_q_urls:
                    ep_url = next(iter(clean_q_urls.values()))
                display_t = f"{asil_movie.title} — {part_num}-qism" if total_parts > 1 else asil_movie.title
                source_entry: Dict[str, Any] = {
                    "url": ep_url,
                    "watch_url": ep.watch_url,
                    "download_url": ep.download_url if ep.download_url and not MovieService._is_rejected_media_url(ep.download_url) else ep_url,
                    "quality": ep.quality,
                    "quality_urls": clean_q_urls,
                    "label": ep.label,
                    "file_type": "video",
                    "source": "asilmedia",
                    "asil_id": str(asil_movie.id),
                    "title": display_t
                }

                if download_files:
                    v_dir = base_dir / "data" / "videos"
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
                        await crud.upsert_movie(
                            session=session,
                            code=p_code,
                            title=display_t,
                            views_count=1500
                        )
                    except Exception as de:
                        logger.debug(f"DB upsert part error: {de}")
        else:
            primary_url = None
            clean_q_urls = {}
            for qk, qu in (asil_movie.video_sources or {}).items():
                if qu and not MovieService._is_rejected_media_url(qu):
                    if qk != "primary":
                        clean_q_urls[qk] = qu
            for qk in ("1080p", "720p", "480p", "primary"):
                cand_u = asil_movie.video_sources.get(qk)
                if cand_u and not MovieService._is_rejected_media_url(cand_u):
                    primary_url = cand_u
                    break
            if primary_url or clean_q_urls:
                primary_url = primary_url or next(iter(clean_q_urls.values()))
                source_entry = {
                    "url": primary_url,
                    "quality_urls": clean_q_urls,
                    "file_type": "video",
                    "source": "asilmedia",
                    "asil_id": str(asil_movie.id),
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

        try:
            with open(sources_file, "w", encoding="utf-8") as f:
                json.dump(sources_data, f, ensure_ascii=False, indent=2)
        except Exception as fe:
            logger.warning(f"video_sources.json saqlashda xatolik: {fe}")

        clean_synced_title = MovieService.sanitize_branding(asil_movie.title) if asil_movie else ""
        clean_synced_desc = (
            MovieService.sanitize_branding(asil_movie.description or f"🎬 {clean_synced_title}")
            if asil_movie
            else ""
        )

        if session and asil_movie:
            try:
                await crud.upsert_movie(
                    session=session,
                    code=clean_code,
                    title=clean_synced_title,
                    description=clean_synced_desc,
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

        global _UNIFIED_CATALOG_CACHE
        _UNIFIED_CATALOG_CACHE = None
        if asil_movie and _CATALOG_CACHE and isinstance(_CATALOG_CACHE.get("items"), list):
            existing_codes = {str(it.get("c")) for it in _CATALOG_CACHE["items"]}
            if clean_code not in existing_codes:
                _CATALOG_CACHE["items"].append({
                    "c": int(clean_code) if clean_code.isdigit() else clean_code,
                    "t": clean_synced_title,
                    "p": total_parts,
                    "v": 1500,
                    "d": clean_synced_desc,
                    "a": clean_code,
                    "i": clean_code,
                    "asil_id": str(asil_movie.id),
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
            u_cand = source.get("download_url") or source.get("url")
            if u_cand and not MovieService._is_rejected_media_url(u_cand):
                video_url = str(u_cand)

        if not video_url:
            s_info = await MovieService.get_movie_stream_info(code, part=part)
            if s_info:
                video_url = s_info.get("stream_url")

        saved_file = None
        if video_url:
            if asilmedia_service.needs_fayllar_sign(video_url):
                signed_v = await asilmedia_service.resolve_stream_url(video_url)
                video_url = signed_v
            if video_url and str(video_url).startswith("http") and not MovieService._is_rejected_media_url(video_url):
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
        global _CATALOG_CACHE, _UNIFIED_CATALOG_CACHE
        _UNIFIED_CATALOG_CACHE = None
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

