"""Kitoblar va Kutubxona xizmati (Book Service).

O'zbek va jahon adabiyoti, biznes, psixologiya va diniy kitoblarni qidirish,
katalogini taqdim etish hamda foydalanuvchi chatiga PDF shaklida yuborish.
To'liq oq brendlangan: Baunty, Baunty Films, @BauntyCinemabot.
"""

from __future__ import annotations

import asyncio
import html
import io
import json
import logging
import os
import re
import threading
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
BOOKS_FILE = BASE_DIR / "data" / "books.json"

_BOOKS_CACHE: List[Dict[str, Any]] = []
_BOOKS_BY_ID: Dict[str, Dict[str, Any]] = {}

CATEGORIES_META = [
    {"id": "badiiy", "name": "Badiiy adabiyot", "icon": "📚"},
    {"id": "biznes", "name": "Biznes va moliya", "icon": "💼"},
    {"id": "psixologiya", "name": "Psixologiya va rivojlanish", "icon": "🧠"},
    {"id": "fantastika", "name": "Ilmiy fantastika", "icon": "🚀"},
    {"id": "detektiv", "name": "Detektiv va triller", "icon": "🔍"},
    {"id": "diniy", "name": "Diniy va ma'rifiy", "icon": "🌙"},
    {"id": "tarix", "name": "Tarixiy asarlar", "icon": "🏛️"},
    {"id": "bolalar", "name": "Bolalar adabiyoti", "icon": "🎈"},
    {"id": "hikoya", "name": "Hikoyalar va qissalar", "icon": "📖"},
    {"id": "falsafa", "name": "Falsafa va tafakkur", "icon": "💡"},
    {"id": "sarguzasht", "name": "Sarguzasht asarlar", "icon": "🧭"},
    {"id": "sheriyat", "name": "She'riyat durdonalari", "icon": "✨"},
]


def _normalize(text: str) -> str:
    """Qidiruv uchun matnni normallashtirish (lotin-kirill va belgilardan tozalash)."""
    if not text:
        return ""
    try:
        from utils.translit import cyrillic_to_latin
        t = cyrillic_to_latin(str(text)).lower()
    except Exception:
        t = str(text).lower()
    t = t.replace("o‘", "o'").replace("g‘", "g'").replace("oʻ", "o'").replace("gʻ", "g'")
    t = t.replace("ў", "o'").replace("ғ", "g'").replace("ш", "sh").replace("ч", "ch")
    t = t.replace("ё", "yo").replace("ю", "yu").replace("я", "ya").replace("ц", "ts")
    t = re.sub(r'[«»""“”„!?.,;:()\[\]{}—–\-_/\\*&^%$#@~<>|]', ' ', t)
    t_clean = re.sub(r"['`ʻʼ’´]", "", t)
    t_punct = re.sub(r"[^\w\s]", " ", t)
    return " ".join((t_punct + " " + t_clean).split())



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

    # Siniq so'z bo'g'inlari
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


def load_books() -> List[Dict[str, Any]]:
    """Kitoblar ro'yxatini yuklash va keshlashtirish."""
    global _BOOKS_CACHE, _BOOKS_BY_ID
    if _BOOKS_CACHE:
        return _BOOKS_CACHE

    items: List[Dict[str, Any]] = []
    if BOOKS_FILE.exists():
        try:
            with open(BOOKS_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception as e:
            logger.error(f"Kitoblar faylini o'qishda xatolik: {e}")

    for item in items:
        bid = str(item.get("id"))
        title = sanitize_book_text(item.get("title", ""))
        author = sanitize_book_text(item.get("author", ""))
        desc = sanitize_book_text(item.get("description", ""))
        item["title"] = title
        item["author"] = author
        item["description"] = desc
        if "sample_text" in item:
            item["sample_text"] = sanitize_book_text(item["sample_text"])

        # WebApp va upstream dual-schema maydonlari (i, t, a, y, g, l, p, r, rn, desc, c, f, s, m, me, lic)
        cat_code = item.get("category", "badiiy")
        meta = next((c for c in CATEGORIES_META if c["id"] == cat_code), None)
        category_name = meta["name"] if meta else item.get("category_name", "Badiiy adabiyot")
        item["category_name"] = category_name

        pages = item.get("pages", 120)
        size_mb = item.get("size_mb", 2.5)
        size_bytes = int(size_mb * 1048576)
        rating = item.get("rating", 4.9)
        views = item.get("views", 10000)

        num_id = int(bid) if bid.isdigit() else 0
        item["i"] = num_id or bid
        item["t"] = title
        item["a"] = author
        item["y"] = item.get("year", 2020)
        item["g"] = cat_code
        item["l"] = item.get("lang", "uz")
        item["p"] = pages
        item["r"] = rating
        item["rn"] = max(10, views // 200)
        item["desc"] = desc
        cover_val = (item.get("cover") or item.get("poster") or item.get("image") or item.get("img") or "").strip()
        item["cover"] = cover_val
        item["poster"] = cover_val
        item["image"] = cover_val
        item["img"] = cover_val
        item["c"] = 1  # Barcha kitoblarda muqova mavjud (lokal, masofaviy yoki dinamik)
        item["cover_url"] = cover_val or f"/bk/{bid}/cover_l.webp"
        item["cover_thumb"] = f"/bk/{bid}/cover_s.webp"
        item["f"] = ["pdf", "epub"]
        item["s"] = {"pdf": size_bytes, "epub": int(size_bytes * 0.55)}
        item["m"] = "text"
        item["me"] = {"pct": 0, "done": False, "saved": False, "stars": 0, "ch": 0}
        item["lic"] = f"Baunty Kutubxonasi — @{config.BOT_USERNAME.lstrip('@')}"

        norm_lat = f"{_normalize(title)} {_normalize(author)} {_normalize(desc)}"
        raw_lower = f"{title} {author} {desc}".lower()
        from utils.translit import latin_to_cyrillic, cyrillic_to_latin
        cyr = latin_to_cyrillic(f"{title} {author}").lower()
        cyr_ru = cyr.replace("қ", "к").replace("ў", "у").replace("ғ", "г").replace("ҳ", "х")
        clean_no_apos = re.sub(r"['`ʻʼ’´]", "", f"{title} {author}").lower()
        norm_k = clean_no_apos.replace("q", "k").replace("o'", "u").replace("g'", "g")
        norm_o = clean_no_apos.replace("o'", "o")
        item["_search"] = f"{norm_lat} {raw_lower} {cyr} {cyr_ru} {clean_no_apos} {norm_k} {norm_o} {bid}"
        _BOOKS_BY_ID[bid] = item

    _BOOKS_CACHE = items
    return _BOOKS_CACHE


def get_catalog(
    category: Optional[str] = None,
    query: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Kutubxona katalogi va toifalarini qaytarish."""
    books = load_books()
    filtered = books

    if lang and lang != "all":
        filtered = [b for b in filtered if b.get("lang") == lang]

    if category and category != "all":
        if category == "pop":
            filtered = [b for b in filtered if b.get("popular") or b.get("views", 0) > 50000]
        else:
            filtered = [b for b in filtered if b.get("category") == category]

    if query:
        norm_q = _normalize(query)
        words = norm_q.split()

        # Punctuation delimiter stripping for tokens
        punct_pattern = r'[«»""“”„!?.,;:()\[\]{}—–\-_/\\*&^%$#@~<>|]'
        clean_no_punct = re.sub(punct_pattern, " ", query).lower()
        clean_q = re.sub(r"['`ʻʼ’´]", "", clean_no_punct).strip()
        clean_words = clean_q.split()

        raw_words = [re.sub(punct_pattern, "", w).strip("'`ʻʼ’´ ") for w in query.lower().split()]
        raw_words = [w for w in raw_words if w]

        cyr_ru_clean = re.sub(punct_pattern, " ", query.lower())
        cyr_ru_q = cyr_ru_clean.replace("қ", "к").replace("ў", "у").replace("ғ", "г").replace("ҳ", "х")
        cyr_ru_words = [w.strip() for w in cyr_ru_q.split() if w.strip()]

        from utils.translit import cyrillic_to_latin, latin_to_cyrillic
        cyr_to_lat = cyrillic_to_latin(query).lower()
        cyr_to_lat_words = _normalize(cyr_to_lat).split()
        lat_to_cyr = latin_to_cyrillic(query).lower()
        lat_to_cyr_clean = re.sub(punct_pattern, " ", lat_to_cyr)
        lat_to_cyr_words = [w.strip() for w in lat_to_cyr_clean.split() if w.strip()]

        filtered = [
            b for b in filtered
            if (clean_q and clean_q in b.get("_search", "")) or
               (clean_words and all(w in b.get("_search", "") for w in clean_words)) or
               (words and all(w in b.get("_search", "") for w in words)) or
               (raw_words and all(w in b.get("_search", "") for w in raw_words)) or
               (cyr_ru_words and all(w in b.get("_search", "") for w in cyr_ru_words)) or
               (cyr_to_lat_words and all(w in b.get("_search", "") for w in cyr_to_lat_words)) or
               (lat_to_cyr_words and all(w in b.get("_search", "") for w in lat_to_cyr_words))
        ]

    total = len(filtered)
    paged = filtered[offset: offset + limit]

    return {
        "ok": True,
        "items": paged,
        "total": total,
        "categories": CATEGORIES_META,
        "bot": config.BOT_USERNAME.lstrip("@"),
        "channel": config.CHANNEL_USERNAME
    }


_BOOKS_STATE_LOCK = threading.RLock()
_BOOKS_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "books_state.json",
)


def _load_books_state() -> Dict[str, Any]:
    """Foydalanuvchi kutubxona holatini JSON fayldan xavfsiz o'qish."""
    import json
    with _BOOKS_STATE_LOCK:
        if not os.path.exists(_BOOKS_STATE_PATH):
            return {"users": {}}
        try:
            with open(_BOOKS_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("users"), dict):
                return data
        except Exception as e:
            logger.warning(f"Kitob holatini o'qishda xatolik: {e}")
        return {"users": {}}


def _save_books_state(data: Dict[str, Any]) -> None:
    """Foydalanuvchi kutubxona holatini JSON faylga atomik saqlash."""
    import json
    with _BOOKS_STATE_LOCK:
        os.makedirs(os.path.dirname(_BOOKS_STATE_PATH), exist_ok=True)
        tmp_path = f"{_BOOKS_STATE_PATH}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _BOOKS_STATE_PATH)


def _ensure_user_entry(state: Dict[str, Any], user_id: Any) -> Dict[str, Any]:
    """Foydalanuvchi yozuvini tayyorlash yoki yaratish."""
    uid = str(user_id or "guest")
    users = state.setdefault("users", {})
    entry = users.setdefault(uid, {})
    entry.setdefault("books", {})
    entry.setdefault("audio", {})
    entry.setdefault("notes", [])
    stats = entry.setdefault("stats", {})
    stats.setdefault("secs", 0)
    stats.setdefault("books", 0)
    stats.setdefault("month", 0)
    stats.setdefault("streak", 0)
    if not isinstance(stats.get("week"), list) or len(stats["week"]) != 7:
        stats["week"] = [0, 0, 0, 0, 0, 0, 0]
    return entry


def _serialize_book_entry(bid: str, rec: Dict[str, Any]) -> Dict[str, Any]:
    """Saqlangan kitob holatini katalog metama'lumotlari bilan birlashtirish."""
    b = get_book_by_id(bid) or {}
    bid_int = int(bid) if str(bid).isdigit() else bid
    return {
        "i": bid_int,
        "id": str(bid),
        "t": b.get("title", f"Kitob #{bid}"),
        "a": b.get("author", "Noma'lum muallif"),
        "c": b.get("cover", "") or f"bk/{bid}/cover_l.webp",
        "l": b.get("lang", "uz"),
        "p": int(b.get("pages", 200) or 200),
        "ch": int(rec.get("ch", 0) or 0),
        "off": float(rec.get("off", 0.0) or 0.0),
        "pct": round(float(rec.get("pct", 0.0) or 0.0), 1),
        "saved": bool(rec.get("saved", False)),
        "done": bool(rec.get("done", False)),
        "dl": bool(rec.get("dl", False)),
        "stars": int(rec.get("stars", 0) or 0),
        "at": int(rec.get("at", 0) or 0),
        "ap": rec.get("ap"),
    }


def get_user_state(user_id: Any) -> Dict[str, Any]:
    """Foydalanuvchining javoni, mutolaa jarayoni, izohlari va statistikasini olish."""
    load_books()
    with _BOOKS_STATE_LOCK:
        state = _load_books_state()
        entry = _ensure_user_entry(state, user_id)
        books_list = [
            _serialize_book_entry(bid, rec)
            for bid, rec in entry["books"].items()
            if isinstance(rec, dict)
        ]
        books_list.sort(key=lambda x: x.get("at", 0), reverse=True)
        shelf_list = [x for x in books_list if x["saved"] or x["done"]]

        audio_list = []
        for bid, ap in entry.get("audio", {}).items():
            if not isinstance(ap, dict):
                continue
            b = get_book_by_id(bid) or {}
            audio_list.append({
                "i": int(bid) if str(bid).isdigit() else bid,
                "t": b.get("title", f"Kitob #{bid}"),
                "a": b.get("author", ""),
                "l": b.get("lang", "uz"),
                "c": 1,
                "n": int(ap.get("n", 1) or 1),
                "pt": float(ap.get("t", 0.0) or 0.0),
                "ts": int(ap.get("ts", 0) or 0),
            })
        audio_list.sort(key=lambda x: x.get("ts", 0), reverse=True)

        notes_list = sorted(
            [n for n in entry.get("notes", []) if isinstance(n, dict)],
            key=lambda x: x.get("ts", 0),
            reverse=True,
        )
        return {
            "ok": True,
            "books": books_list,
            "shelf": shelf_list,
            "audio": audio_list,
            "notes": notes_list,
            "stats": dict(entry["stats"]),
        }


def get_user_book_me(user_id: Any, book_id: Any) -> Dict[str, Any]:
    """Bitta kitob bo'yicha foydalanuvchi holatini (progress, saqlash, izohlar) qaytarish."""
    bid = str(book_id)
    with _BOOKS_STATE_LOCK:
        state = _load_books_state()
        entry = _ensure_user_entry(state, user_id)
        rec = dict(entry["books"].get(bid, {}))
        ap = entry.get("audio", {}).get(bid)
        notes = [
            n for n in entry.get("notes", [])
            if isinstance(n, dict) and str(n.get("i")) == bid
        ]
        return {
            "ch": int(rec.get("ch", 0) or 0),
            "off": float(rec.get("off", 0.0) or 0.0),
            "pct": float(rec.get("pct", 0.0) or 0.0),
            "saved": bool(rec.get("saved", False)),
            "done": bool(rec.get("done", False)),
            "dl": bool(rec.get("dl", False)),
            "stars": int(rec.get("stars", 0) or 0),
            "ap": ap,
            "notes": notes,
        }


def save_user_progress(
    user_id: Any,
    book_id: Any,
    ch: int = 0,
    off: float = 0.0,
    pct: float = 0.0,
    secs: int = 0,
) -> Dict[str, Any]:
    """Mutolaa jarayonini va o'qish vaqtini JSON bazaga saqlash."""
    import time
    from datetime import datetime
    bid = str(book_id)
    now_ts = int(time.time())
    safe_pct = max(0.0, min(100.0, float(pct or 0.0)))
    safe_secs = max(0, int(secs or 0))
    with _BOOKS_STATE_LOCK:
        state = _load_books_state()
        entry = _ensure_user_entry(state, user_id)
        rec = entry["books"].setdefault(bid, {})
        was_done = bool(rec.get("done", False))
        rec["ch"] = max(0, int(ch or 0))
        rec["off"] = max(0.0, min(1.0, float(off or 0.0)))
        rec["pct"] = round(safe_pct, 2)
        rec["at"] = now_ts
        if safe_pct >= 99.0:
            rec["done"] = True
            if not was_done:
                entry["stats"]["books"] = int(entry["stats"].get("books", 0)) + 1
                entry["stats"]["month"] = int(entry["stats"].get("month", 0)) + 1
        if safe_secs > 0:
            entry["stats"]["secs"] = int(entry["stats"].get("secs", 0)) + safe_secs
            entry["stats"]["week"][6] = int(entry["stats"]["week"][6]) + safe_secs
        today_str = datetime.now().strftime("%Y-%m-%d")
        if entry["stats"].get("last_day") != today_str:
            entry["stats"]["streak"] = int(entry["stats"].get("streak", 0)) + 1
            entry["stats"]["last_day"] = today_str
        _save_books_state(state)
        return {"ok": True, "me": _serialize_book_entry(bid, rec)}


def toggle_shelf(
    user_id: Any,
    book_id: Any,
    saved: Optional[bool] = None,
    done: Optional[bool] = None,
    stars: Optional[int] = None,
    remove: bool = False,
    dl: Optional[bool] = None,
) -> Dict[str, Any]:
    """Kitobni javonga qo'shish/o'chirish, tugatish va baholash holatini saqlash."""
    import time
    bid = str(book_id)
    with _BOOKS_STATE_LOCK:
        state = _load_books_state()
        entry = _ensure_user_entry(state, user_id)
        if remove:
            entry["books"].pop(bid, None)
            _save_books_state(state)
            return {"ok": True, "removed": True}
        rec = entry["books"].setdefault(bid, {})
        was_done = bool(rec.get("done", False))
        if saved is not None:
            rec["saved"] = bool(saved)
        elif done is None and stars is None and dl is None:
            rec["saved"] = not bool(rec.get("saved", False))
        if done is not None:
            rec["done"] = bool(done)
            if rec["done"] and float(rec.get("pct", 0.0) or 0.0) < 100.0:
                rec["pct"] = 100.0
            if rec["done"] and not was_done:
                entry["stats"]["books"] = int(entry["stats"].get("books", 0)) + 1
                entry["stats"]["month"] = int(entry["stats"].get("month", 0)) + 1
        if stars is not None:
            rec["stars"] = max(1, min(5, int(stars)))
        if dl is not None:
            rec["dl"] = bool(dl)
        rec["at"] = int(time.time())
        if (
            not rec.get("saved")
            and not rec.get("done")
            and not rec.get("dl")
            and float(rec.get("pct", 0.0) or 0.0) == 0.0
            and not rec.get("stars")
        ):
            entry["books"].pop(bid, None)
            _save_books_state(state)
            return {"ok": True, "saved": False}
        _save_books_state(state)
        return {"ok": True, "me": _serialize_book_entry(bid, rec)}


def add_note(
    user_id: Any,
    book_id: Any,
    ch: int = 0,
    q: str = "",
    note: str = "",
    pos: int = -1,
) -> Dict[str, Any]:
    """Kitobdagi belgilangan parcha va shaxsiy izohni saqlash."""
    import time
    import uuid
    bid = str(book_id)
    b = get_book_by_id(bid) or {}
    nid = uuid.uuid4().hex[:10]
    item = {
        "id": nid,
        "i": int(bid) if bid.isdigit() else bid,
        "t": b.get("title", f"Kitob #{bid}"),
        "ch": max(0, int(ch or 0)),
        "q": str(q or "").strip()[:600],
        "n": str(note or "").strip()[:2000],
        "pos": int(pos if pos is not None else -1),
        "ts": int(time.time()),
    }
    with _BOOKS_STATE_LOCK:
        state = _load_books_state()
        entry = _ensure_user_entry(state, user_id)
        entry["notes"].insert(0, item)
        entry["notes"] = entry["notes"][:200]
        _save_books_state(state)
    return {"ok": True, "id": nid, "note": item}


def delete_note(user_id: Any, note_id: Any) -> Dict[str, Any]:
    """Foydalanuvchi izohini o'chirish."""
    nid = str(note_id)
    with _BOOKS_STATE_LOCK:
        state = _load_books_state()
        entry = _ensure_user_entry(state, user_id)
        before = len(entry["notes"])
        entry["notes"] = [n for n in entry["notes"] if str(n.get("id")) != nid]
        if len(entry["notes"]) != before:
            _save_books_state(state)
            return {"ok": True, "deleted": True}
    return {"ok": True, "deleted": False}


def save_user_audio_progress(
    user_id: Any,
    book_id: Any,
    n: int = 1,
    t: float = 0.0,
    secs: int = 0,
) -> Dict[str, Any]:
    """Audiokitob tinglash joyini saqlash."""
    import time
    bid = str(book_id)
    now_ts = int(time.time())
    with _BOOKS_STATE_LOCK:
        state = _load_books_state()
        entry = _ensure_user_entry(state, user_id)
        entry["audio"][bid] = {"n": max(1, int(n or 1)), "t": max(0.0, float(t or 0.0)), "ts": now_ts}
        if secs and int(secs) > 0:
            entry["stats"]["secs"] = int(entry["stats"].get("secs", 0)) + int(secs)
        _save_books_state(state)
    return {"ok": True}


async def async_get_book_by_id(book_id: str | int) -> Optional[Dict[str, Any]]:
    """Kitobni ID orqali asinxron olish (mahalliy 3390 kitoblar keshidan darhol qaytarish)."""
    return get_book_by_id(book_id)

get_book_by_id_async = async_get_book_by_id


def get_book_by_id(book_id: str | int) -> Optional[Dict[str, Any]]:
    """Kitobni ID orqali olish (mahalliy 3390 kitoblar keshidan darhol <1ms qaytarish)."""
    load_books()
    raw = str(book_id).strip()
    bid = re.sub(r'^(?:book_|books_|b_|kitob_)', '', raw).strip()
    return _BOOKS_BY_ID.get(bid) or _BOOKS_BY_ID.get(raw)


def search_books(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Kitoblarni tezkor qidirish (dual-schema: ham i, t, a, ham id, title, author bilan)."""
    if not query:
        return []
    res = get_catalog(query=query, limit=limit)
    items = res.get("items", [])
    normalized = []
    for it in items:
        b = dict(it)
        b["id"] = str(b.get("i") or b.get("id", ""))
        b["title"] = b.get("t") or b.get("title", "")
        b["author"] = b.get("a") or b.get("author", "")
        b["category"] = b.get("g") or b.get("category", "badiiy")
        b["i"] = b.get("i") or (int(b["id"]) if str(b.get("id", "")).isdigit() else 0)
        b["t"] = b["title"]
        b["a"] = b["author"]
        b["g"] = b["category"]
        cover_val = (b.get("cover") or b.get("poster") or b.get("image") or b.get("img") or "").strip()
        b["cover"] = cover_val
        b["poster"] = cover_val
        b["image"] = cover_val
        b["img"] = cover_val
        b["c"] = 1
        b["cover_url"] = cover_val or f"/bk/{b['id']}/cover_l.webp"
        b["cover_thumb"] = f"/bk/{b['id']}/cover_s.webp"
        b["p"] = b.get("p") or b.get("pages", 100)
        b["l"] = b.get("l") or b.get("lang", "uz")
        b["f"] = b.get("f") or [b.get("format", "pdf").lower()]
        normalized.append(b)
    return normalized


BOOK_PALETTES = [
    {"bg": (123, 30, 43), "accent": (233, 180, 76), "text": (255, 255, 255)},   # k0: Deep Crimson & Gold
    {"bg": (31, 42, 92), "accent": (243, 238, 226), "text": (255, 255, 255)},   # k1: Midnight Navy & Cream
    {"bg": (47, 93, 58), "accent": (217, 164, 65), "text": (255, 255, 255)},   # k2: Emerald Forest & Gold
    {"bg": (91, 44, 111), "accent": (240, 180, 60), "text": (255, 255, 255)},  # k3: Royal Purple & Amber
    {"bg": (45, 52, 54), "accent": (225, 177, 44), "text": (255, 255, 255)},   # k4: Charcoal & Topaz
    {"bg": (26, 26, 26), "accent": (229, 72, 77), "text": (255, 255, 255)},    # k5: Jet Black & Ruby
    {"bg": (43, 78, 110), "accent": (168, 197, 218), "text": (255, 255, 255)}, # k6: Slate Ocean & Ice
    {"bg": (90, 35, 48), "accent": (242, 198, 194), "text": (255, 255, 255)},  # k7: Burgundy & Rose
    {"bg": (15, 30, 46), "accent": (212, 175, 55), "text": (255, 255, 255)},  # k8: Dark Sapphire & Gold
    {"bg": (61, 51, 38), "accent": (224, 197, 143), "text": (255, 255, 255)}, # k9: Warm Umber & Parchment
    {"bg": (30, 77, 68), "accent": (247, 211, 90), "text": (255, 255, 255)},  # k10: Deep Teal & Amber
    {"bg": (181, 86, 43), "accent": (255, 235, 175), "text": (255, 255, 255)},# k11: Burnt Sienna & Cream
    {"bg": (74, 90, 42), "accent": (230, 217, 168), "text": (255, 255, 255)}, # k12: Olive Moss & Sand
    {"bg": (14, 85, 96), "accent": (240, 180, 60), "text": (255, 255, 255)},  # k13: Deep Cyan & Gold
]


def _get_cover_font(size: int, bold: bool = False):
    """Platformaga mos TrueType yoki Default shriftni olish."""
    from PIL import ImageFont
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size=size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def generate_dynamic_book_cover(
    book: Dict[str, Any],
    size: str = "l",
    fmt: str = "WEBP"
) -> bytes:
    """Kitob uchun yuqori sifatli va zamonaviy muqova rasmini generatsiya qilish (Pillow)."""
    import textwrap
    from PIL import Image, ImageDraw

    title = str(book.get("title") or book.get("t") or "Kitob").strip()
    author = str(book.get("author") or book.get("a") or "Noma'lum muallif").strip()
    cat_name = str(book.get("category_name") or "Badiiy adabiyot").strip()
    rating = str(book.get("rating") or "4.9")
    bid = str(book.get("id") or book.get("i") or "1")

    is_thumb = size in ("thumb", "thumbnail")
    is_large = size in ("l", "large", "big", "feat")
    if is_thumb:
        w, h = (300, 300)
    elif is_large:
        w, h = (600, 900)
    else:
        w, h = (240, 360)

    num_id = int(bid) if bid.isdigit() else len(title)
    k_idx = (num_id * 7 + len(title)) % len(BOOK_PALETTES)
    pal = BOOK_PALETTES[k_idx]
    bg = pal["bg"]
    accent = pal["accent"]
    text_color = pal["text"]

    img = Image.new("RGB", (w, h), color=bg)
    draw = ImageDraw.Draw(img)

    pad = 18 if is_large else 8
    bw = 3 if is_large else 2
    draw.rectangle([(pad, pad), (w - pad - 1, h - pad - 1)], outline=accent, width=bw)

    # Kitob jildi chizig'i (spine crease)
    if not is_thumb:
        spine_x = int(w * 0.065)
        draw.line([(spine_x, pad), (spine_x, h - pad - 1)], fill=(0, 0, 0), width=2)
        draw.line([(spine_x + 2, pad), (spine_x + 2, h - pad - 1)], fill=(255, 255, 255), width=1)

    # Sarlavha ribboni
    f_head = _get_cover_font(max(10, int(h * 0.024)), bold=True)
    draw.text((w // 2, int(h * 0.08)), "BAUNTY KUTUBXONASI", fill=accent, font=f_head, anchor="mm")

    f_cat = _get_cover_font(max(9, int(h * 0.02)), bold=False)
    draw.text((w // 2, int(h * 0.12)), cat_name.upper(), fill=(200, 215, 230), font=f_cat, anchor="mm")

    # Ajratuvchi chiziq
    div_w = int(w * 0.3)
    draw.line([(w // 2 - div_w, int(h * 0.155)), (w // 2 + div_w, int(h * 0.155))], fill=accent, width=1)

    # Kitob nomi
    f_title = _get_cover_font(max(13, int(h * 0.042)), bold=True)
    wrap_len = 16 if is_large else 13
    lines = textwrap.wrap(title, width=wrap_len)
    start_y = int(h * 0.38) - (len(lines) * int(h * 0.025))
    line_h = int(h * 0.055)
    for line in lines[:4]:
        draw.text((w // 2, start_y), line, fill=text_color, font=f_title, anchor="mm")
        start_y += line_h

    draw.line([(w // 2 - div_w, start_y + 8), (w // 2 + div_w, start_y + 8)], fill=accent, width=1)

    # Muallif nomi
    f_author = _get_cover_font(max(11, int(h * 0.03)), bold=True)
    draw.text((w // 2, start_y + int(h * 0.06)), author[:32], fill=accent, font=f_author, anchor="mm")

    # Quyi ma'lumotlar
    if not is_thumb:
        f_foot = _get_cover_font(max(9, int(h * 0.02)), bold=False)
        draw.text((w // 2, h - int(h * 0.08)), f"★ {rating} • Oltin To'plam", fill=(180, 195, 210), font=f_foot, anchor="mm")
        draw.text((w // 2, h - int(h * 0.045)), f"@{config.BOT_USERNAME.lstrip('@')}", fill=accent, font=f_foot, anchor="mm")

    buf = io.BytesIO()
    fmt_clean = "JPEG" if fmt.upper() in ("JPG", "JPEG") else "PNG" if fmt.upper() == "PNG" else "WEBP"
    img.save(buf, format=fmt_clean, quality=88)
    return buf.getvalue()


def generate_svg_book_cover(book: Dict[str, Any]) -> str:
    """Kitob uchun vektorli SVG muqovasi yaratish."""
    title = html.escape(str(book.get("title") or book.get("t") or "Kitob"))
    author = html.escape(str(book.get("author") or book.get("a") or "Noma'lum muallif"))
    category = html.escape(str(book.get("category_name") or "Badiiy adabiyot"))
    bid = str(book.get("id") or book.get("i") or "1")

    num_id = int(bid) if bid.isdigit() else len(title)
    k_idx = (num_id * 7 + len(title)) % len(BOOK_PALETTES)
    pal = BOOK_PALETTES[k_idx]
    bg_rgb = f"rgb{pal['bg']}"
    accent_rgb = f"rgb{pal['accent']}"

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">'
        f'<rect width="400" height="600" fill="{bg_rgb}"/>'
        f'<rect x="12" y="12" width="376" height="576" fill="none" stroke="{accent_rgb}" stroke-width="2"/>'
        '<line x1="26" y1="12" x2="26" y2="588" stroke="rgba(0,0,0,0.4)" stroke-width="2"/>'
        f'<text x="200" y="55" fill="{accent_rgb}" font-family="sans-serif" font-size="11" font-weight="bold" text-anchor="middle" letter-spacing="2">BAUNTY KUTUBXONASI</text>'
        f'<text x="200" y="80" fill="#E2E8F0" font-family="sans-serif" font-size="10" text-anchor="middle">{category.upper()}</text>'
        f'<line x1="140" y1="95" x2="260" y2="95" stroke="{accent_rgb}" stroke-width="1"/>'
        f'<text x="200" y="260" fill="#FFFFFF" font-family="Georgia,serif" font-size="22" font-weight="bold" text-anchor="middle">{title[:28]}</text>'
        f'<line x1="150" y1="300" x2="250" y2="300" stroke="{accent_rgb}" stroke-width="1"/>'
        f'<text x="200" y="340" fill="{accent_rgb}" font-family="sans-serif" font-size="14" font-weight="bold" text-anchor="middle">{author[:30]}</text>'
        f'<text x="200" y="550" fill="{accent_rgb}" font-family="sans-serif" font-size="11" text-anchor="middle">@{config.BOT_USERNAME.lstrip("@")}</text>'
        '</svg>'
    )


def get_book_thumbnail_bytes(book_or_id: Any) -> Optional[bytes]:
    """Kitob uchun Telegram hujjat thumbnaili (JPEG, max 320x320)."""
    if isinstance(book_or_id, dict):
        book = book_or_id
        bid = str(book.get("id") or book.get("i") or "")
    else:
        bid = str(book_or_id)
        book = get_book_by_id(bid) or {"id": bid, "title": f"Kitob #{bid}", "author": "Baunty Kutubxonasi"}
    local_thumb = BASE_DIR / "data" / "bk" / bid / "thumb.jpg"
    if local_thumb.exists():
        try:
            return local_thumb.read_bytes()
        except Exception:
            pass

    local_cover = BASE_DIR / "data" / "bk" / bid / "cover_s.webp"
    if not local_cover.exists():
        local_cover = BASE_DIR / "data" / "bk" / bid / "cover_l.webp"

    try:
        from PIL import Image
        if local_cover.exists():
            with Image.open(local_cover) as im:
                im = im.convert("RGB")
                im.thumbnail((320, 320), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=85)
                thumb_bytes = buf.getvalue()
                try:
                    local_thumb.parent.mkdir(parents=True, exist_ok=True)
                    local_thumb.write_bytes(thumb_bytes)
                except Exception:
                    pass
                return thumb_bytes
    except Exception as e:
        logger.debug(f"Thumbnail yaratishda xato: {e}")

    try:
        return generate_dynamic_book_cover(book, size="thumb", fmt="JPEG")
    except Exception as e:
        logger.warning(f"Zaxira thumbnail generatsiyasida xato: {e}")
        return None


def get_book_cover_bytes(book_or_id: Any, size: str = "l", fmt: str = "WEBP") -> bytes:
    """Kitob muqovasi baytlarini olish (keshdan yoki dinamik generatsiyadan)."""
    if isinstance(book_or_id, dict):
        book = book_or_id
        bid = str(book.get("id") or book.get("i") or "")
    else:
        bid = str(book_or_id)
        book = get_book_by_id(bid) or {"id": bid, "title": f"Kitob #{bid}", "author": "Baunty Kutubxonasi"}

    clean_size = "s" if size in ("s", "small", "thumb") else "l"
    ext = "jpg" if fmt.upper() in ("JPG", "JPEG") else "webp"
    local_path = BASE_DIR / "data" / "bk" / bid / f"cover_{clean_size}.{ext}"
    if local_path.exists():
        try:
            return local_path.read_bytes()
        except Exception:
            pass

    local_webp = BASE_DIR / "data" / "bk" / bid / f"cover_{clean_size}.webp"
    if local_webp.exists() and ext == "webp":
        try:
            return local_webp.read_bytes()
        except Exception:
            pass

    return generate_dynamic_book_cover(book, size=clean_size, fmt=fmt)


def get_book_cover_url(book: Dict[str, Any]) -> str:
    """Telegram va WebApp uchun kitob muqovasi to'liq URL manzilini olish."""
    cover_val = (book.get("cover") or book.get("poster") or book.get("image") or book.get("img") or "").strip()
    bid = str(book.get("id") or book.get("i") or "")
    if cover_val.startswith("http"):
        return cover_val
    webapp_url = (config.webapp_url_resolved or "https://baunty-cinema.onrender.com/").rstrip("/")
    if bid:
        return f"{webapp_url}/bk/{bid}/cover_l.webp"
    return "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&q=80"


def _find_unicode_ttf(bold: bool = False) -> Optional[str]:
    """Kirill va O'zbek lotin harflarini qo'llab-quvvatlovchi tizim shriftini topish."""
    candidates = (
        [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "arialbd.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "DejaVuSans.ttf",
            "arial.ttf",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _clean_pdf_text(text: str) -> str:
    """TTF shriftda bo'sh kvadrat (tofu) bermasligi uchun emoji belgilarini tozalash."""
    import re
    cleaned = re.sub(r"[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F]", "", str(text or ""))
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def create_book_pdf_sample(book: Dict[str, Any]) -> bytes:
    """Kitob uchun chiroyli PDF mutolaa nusxasini yaratish (ReportLab yoki Pillow yordamida)."""
    title = _clean_pdf_text(book.get("title", "Kitob"))
    author = _clean_pdf_text(book.get("author", "Noma'lum muallif"))
    desc = _clean_pdf_text(book.get("description", ""))
    sample = _clean_pdf_text(book.get("sample_text", desc))
    category_name = _clean_pdf_text(book.get("category_name", "Badiiy adabiyot"))
    pages = book.get("pages", 200)
    bot_user = config.BOT_USERNAME.lstrip("@")

    # 1. Agar ReportLab mavjud bo'lsa (Unicode TTF ro'yxatdan o'tkazish bilan)
    try:
        import html
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        reg_ttf = _find_unicode_ttf(False)
        bold_ttf = _find_unicode_ttf(True) or reg_ttf
        font_reg = "Helvetica"
        font_bold = "Helvetica-Bold"
        if reg_ttf:
            pdfmetrics.registerFont(TTFont("BauntyBook", reg_ttf))
            pdfmetrics.registerFont(TTFont("BauntyBookBold", bold_ttf))
            pdfmetrics.registerFontFamily("BauntyBook", normal="BauntyBook", bold="BauntyBookBold")
            font_reg = "BauntyBook"
            font_bold = "BauntyBookBold"

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "BookTitle",
            parent=styles["Title"],
            fontName=font_bold,
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#1A1D20"),
            alignment=1,
            spaceAfter=12
        )
        author_style = ParagraphStyle(
            "BookAuthor",
            parent=styles["Normal"],
            fontName=font_reg,
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#E5484D"),
            alignment=1,
            spaceAfter=18
        )
        meta_style = ParagraphStyle(
            "BookMeta",
            parent=styles["Normal"],
            fontName=font_reg,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#6C757D"),
            alignment=1,
            spaceAfter=24
        )
        h2_style = ParagraphStyle(
            "BookH2",
            parent=styles["Heading2"],
            fontName=font_bold,
            fontSize=14,
            textColor=colors.HexColor("#1A1D20")
        )
        body_style = ParagraphStyle(
            "BookBody",
            parent=styles["Normal"],
            fontName=font_reg,
            fontSize=12,
            leading=18,
            textColor=colors.HexColor("#2B2D42"),
            spaceAfter=14
        )
        footer_style = ParagraphStyle(
            "BookFooter",
            parent=styles["Normal"],
            fontName=font_reg,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#8D99AE"),
            alignment=1
        )

        elements = [
            Paragraph(f"<b>{html.escape(title)}</b>", title_style),
            Paragraph(f"Muallif: <b>{html.escape(author)}</b>", author_style),
            Paragraph(f"Janr: {html.escape(category_name)} | {pages} sahifa | Reyting: {book.get('rating', 4.9)}", meta_style),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=20),
            Paragraph("<b>Qisqacha mazmuni:</b>", h2_style),
            Spacer(1, 6),
            Paragraph(html.escape(desc), body_style),
            Spacer(1, 14),
            Paragraph("<b>Kitobdan parcha (Mutolaa):</b>", h2_style),
            Spacer(1, 6),
            Paragraph(html.escape(sample), body_style),
            Spacer(1, 30),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=14),
            Paragraph(f"Baunty Kutubxonasi — @{bot_user} | {config.CHANNEL_USERNAME}", footer_style)
        ]

        doc.build(elements)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        logger.debug(f"ReportLab orqali PDF generatsiyasida xatolik ({e}), Pillow yordamida yaratiladi.")

    # 2. Pillow (PIL) yordamida to'liq Unicode TTF shriftli 2 sahifali PDF
    try:
        import textwrap
        from PIL import Image, ImageDraw, ImageFont

        reg_ttf = _find_unicode_ttf(False)
        bold_ttf = _find_unicode_ttf(True) or reg_ttf
        f_head = ImageFont.truetype(bold_ttf, 28) if bold_ttf else _get_cover_font(28, bold=True)
        f_title = ImageFont.truetype(bold_ttf, 44) if bold_ttf else _get_cover_font(44, bold=True)
        f_sub = ImageFont.truetype(reg_ttf, 28) if reg_ttf else _get_cover_font(28)
        f_sec = ImageFont.truetype(bold_ttf, 28) if bold_ttf else _get_cover_font(28, bold=True)
        f_body = ImageFont.truetype(reg_ttf, 26) if reg_ttf else _get_cover_font(26)
        f_foot = ImageFont.truetype(reg_ttf, 22) if reg_ttf else _get_cover_font(22)

        W, H = 1200, 1600
        p1 = Image.new("RGB", (W, H), color=(253, 251, 247))
        d1 = ImageDraw.Draw(p1)
        d1.rectangle([(0, 0), (W, 110)], fill=(26, 29, 32))
        d1.text((50, 38), f"BAUNTY KUTUBXONASI — @{bot_user}", fill=(255, 255, 255), font=f_head)
        d1.text((50, 155), title[:42], fill=(26, 29, 32), font=f_title)
        d1.text((50, 225), f"Muallif: {author[:50]}", fill=(229, 72, 77), font=f_sub)
        d1.text((50, 275), f"Janr: {category_name}  |  {pages} bet  |  Reyting: {book.get('rating', 4.9)}/5.0", fill=(108, 117, 125), font=f_foot)
        d1.line([(50, 320), (W - 50, 320)], fill=(226, 232, 240), width=2)
        d1.text((50, 350), "QISQACHA MAZMUNI:", fill=(26, 29, 32), font=f_sec)
        y = 405
        for para in (desc or "").split("\n"):
            for line in textwrap.wrap(para, width=64) or [""]:
                d1.text((50, y), line, fill=(43, 45, 66), font=f_body)
                y += 38
                if y > H - 105:
                    break
            y += 10
            if y > H - 105:
                break
        d1.line([(50, H - 70), (W - 50, H - 70)], fill=(226, 232, 240), width=1)
        d1.text((50, H - 52), f"Baunty Books | {config.CHANNEL_USERNAME} | 1-sahifa", fill=(141, 153, 174), font=f_foot)

        p2 = Image.new("RGB", (W, H), color=(253, 251, 247))
        d2 = ImageDraw.Draw(p2)
        d2.rectangle([(0, 0), (W, 110)], fill=(26, 29, 32))
        d2.text((50, 38), f"«{title[:38]}» — MUTOLAA PARCHASI", fill=(255, 255, 255), font=f_head)
        y = 155
        d2.text((50, y), "KITOBDAN PARCHA:", fill=(26, 29, 32), font=f_sec)
        y += 50
        for para in (sample or "").split("\n"):
            for line in textwrap.wrap(para, width=64) or [""]:
                d2.text((50, y), line, fill=(43, 45, 66), font=f_body)
                y += 38
                if y > H - 105:
                    break
            y += 10
            if y > H - 105:
                break
        d2.line([(50, H - 70), (W - 50, H - 70)], fill=(226, 232, 240), width=1)
        d2.text((50, H - 52), f"Baunty Books | @{bot_user} | 2-sahifa", fill=(141, 153, 174), font=f_foot)

        buf = io.BytesIO()
        p1.save(buf, format="PDF", save_all=True, append_images=[p2])
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"Pillow orqali PDF generatsiyasida xatolik ({e}), zaxira matnli PDF yaratiladi.")

    # 3. Zaxira sodda PDF
    pdf_content = (
        f"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        f"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        f"3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R/Resources<<>>>>endobj\n"
        f"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        f"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n"
    )
    return pdf_content.encode("utf-8")


def create_book_epub_sample(book: Dict[str, Any]) -> bytes:
    """Kitob uchun standart EPUB mutolaa faylini yaratish."""
    import html
    import zipfile

    title = book.get("title", "Kitob")
    author = book.get("author", "Noma'lum muallif")
    desc = book.get("description", "")
    sample = book.get("sample_text", desc)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
        container_xml = (
            '<?xml version="1.0"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
            '  <rootfiles>\n'
            '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
            '  </rootfiles>\n'
            '</container>'
        )
        z.writestr("META-INF/container.xml", container_xml.encode("utf-8"))

        content_opf = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">\n'
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f'    <dc:title>{html.escape(title)}</dc:title>\n'
            f'    <dc:creator>{html.escape(author)}</dc:creator>\n'
            f'    <dc:description>{html.escape(desc)}</dc:description>\n'
            '    <dc:language>uz</dc:language>\n'
            f'    <dc:publisher>Baunty Books (@{config.BOT_USERNAME.lstrip("@")})</dc:publisher>\n'
            '  </metadata>\n'
            '  <manifest>\n'
            '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'
            '    <item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>\n'
            '  </manifest>\n'
            '  <spine toc="ncx">\n'
            '    <itemref idref="c1"/>\n'
            '  </spine>\n'
            '</package>'
        )
        z.writestr("OEBPS/content.opf", content_opf.encode("utf-8"))

        toc_ncx = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
            '  <head><meta name="dtb:uid" content="1"/></head>\n'
            f'  <docTitle><text>{html.escape(title)}</text></docTitle>\n'
            '  <navMap>\n'
            '    <navPoint id="navpoint-1" playOrder="1">\n'
            '      <navLabel><text>1-bob. Mutolaa</text></navLabel>\n'
            '      <content src="chapter1.xhtml"/>\n'
            '    </navPoint>\n'
            '  </navMap>\n'
            '</ncx>'
        )
        z.writestr("OEBPS/toc.ncx", toc_ncx.encode("utf-8"))

        p_tags = "".join(f"<p>{html.escape(line)}</p>" for line in sample.split("\n") if line.strip())
        chapter_xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
            '<html xmlns="http://www.w3.org/1999/xhtml">\n'
            '<head>\n'
            f'  <title>{html.escape(title)}</title>\n'
            '  <style>body { font-family: sans-serif; margin: 4%; line-height: 1.6; } h1 { color: #1a1d20; } h2 { color: #e5484d; }</style>\n'
            '</head>\n'
            '<body>\n'
            f'  <h1>{html.escape(title)}</h1>\n'
            f'  <h2>{html.escape(author)}</h2>\n'
            '  <hr/>\n'
            '  <h3>Qisqacha mazmuni</h3>\n'
            f'  <p>{html.escape(desc)}</p>\n'
            '  <hr/>\n'
            '  <h3>Kitobdan parcha</h3>\n'
            f'  {p_tags}\n'
            '  <hr/>\n'
            f'  <p><small>Baunty Kutubxonasi — @{config.BOT_USERNAME.lstrip("@")} | {config.CHANNEL_USERNAME}</small></p>\n'
            '</body>\n'
            '</html>'
        )
        z.writestr("OEBPS/chapter1.xhtml", chapter_xhtml.encode("utf-8"))

    return buf.getvalue()


async def deliver_book(
    bot: Any,
    chat_id: int | str,
    book_id: str | int,
    fmt: str = "pdf"
) -> Dict[str, Any]:
    """Kitobni foydalanuvchining Telegram chatiga yetkazish."""
    book = get_book_by_id(book_id)
    if not book:
        return {"ok": False, "error": "not_found"}

    title = book.get("title", "Kitob")
    author = book.get("author", "Noma'lum muallif")
    category_name = book.get("category_name", "Badiiy adabiyot")
    pages = book.get("pages", 200)
    rating = book.get("rating", 4.9)
    desc = book.get("description", "")
    short_desc = (desc[:280] + "…") if len(desc) > 280 else desc
    format_label = fmt.upper()

    safe_title = html.escape(str(title), quote=False)
    safe_author = html.escape(str(author), quote=False)
    safe_cat_name = html.escape(str(category_name), quote=False)
    safe_short_desc = html.escape(str(short_desc), quote=False)

    caption = (
        f"📚 <b>{safe_title}</b>\n\n"
        f"✍️ <b>Muallif:</b> {safe_author}\n"
        f"📂 <b>Toifa:</b> {safe_cat_name}\n"
        f"📄 <b>Sahifalar:</b> {pages} ta | 💾 <b>Format:</b> {format_label} ({book.get('size_mb', 2.5)} MB)\n"
        f"⭐ <b>Reyting:</b> {rating} / 5.0\n\n"
        f"📖 <i>{safe_short_desc}</i>\n\n"
        f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} • {config.CHANNEL_USERNAME}</b>"
    )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile

    bot_user = config.BOT_USERNAME.lstrip("@")
    webapp_url = f"{config.WEBAPP_URL}?books&b={book['id']}" if config.WEBAPP_URL else None

    buttons = []
    if webapp_url:
        from aiogram.types import WebAppInfo
        buttons.append([InlineKeyboardButton(text="📖 Ilovada o'qish (Mutolaa)", web_app=WebAppInfo(url=webapp_url))])

    quoted_text = urllib.parse.quote(f"{title} kitobini o'qish")
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_user}?start=b_{book['id']}&text={quoted_text}"
    buttons.append([
        InlineKeyboardButton(text="🔗 Do'stlarga ulashish", url=share_url),
        InlineKeyboardButton(text="📚 Barcha kitoblar", url=f"https://t.me/{bot_user}?start=books")
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Faylni formatga qarab generatsiya qilish (PDF yoki EPUB)
    try:
        clean_ext = "epub" if str(fmt).lower() == "epub" else "pdf"
        if clean_ext == "epub":
            doc_bytes = create_book_epub_sample(book)
        else:
            doc_bytes = create_book_pdf_sample(book)

        safe_filename = re.sub(r'[^\w\s-]', '', f"{title} - {author}").strip() + f".{clean_ext}"
        input_file = BufferedInputFile(doc_bytes, filename=safe_filename)

        thumb_bytes = get_book_thumbnail_bytes(book)
        thumb_file = BufferedInputFile(thumb_bytes, filename="thumb.jpg") if thumb_bytes else None

        try:
            await bot.send_document(
                chat_id=chat_id,
                document=input_file,
                thumbnail=thumb_file,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
                protect_content=True
            )
        except Exception as e_thumb:
            logger.debug(f"Thumbnail bilan yuborishda xatolik ({e_thumb}), oddiy yuboriladi.")
            await bot.send_document(
                chat_id=chat_id,
                document=input_file,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
                protect_content=True
            )
        return {"ok": True, "delivered": True, "book": book, "format": clean_ext}
    except Exception as e:
        logger.warning(f"Kitob hujjatini yuborishda xatolik ({e}), xabar sifatida yuboriladi.")
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=kb,
                protect_content=True
            )
            return {"ok": True, "delivered": True, "book": book, "format": "text"}
        except Exception as e2:
            logger.error(f"Kitobni chatga yetkazib bo'lmadi: {e2}")
            return {"ok": False, "error": str(e2)}
