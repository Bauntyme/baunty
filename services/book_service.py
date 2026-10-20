"""Kitoblar va Kutubxona xizmati (Book Service).

O'zbek va jahon adabiyoti, biznes, psixologiya va diniy kitoblarni qidirish,
katalogini taqdim etish hamda foydalanuvchi chatiga PDF shaklida yuborish.
To'liq oq brendlangan: Baunty, Baunty Films, @Bauntyfilmsbot.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
BOOKS_FILE = BASE_DIR / "data" / "books.json"

_BOOKS_CACHE: List[Dict[str, Any]] = []
_BOOKS_BY_ID: Dict[str, Dict[str, Any]] = {}

CATEGORIES_META = [
    {"id": "all", "name": "Barchasi", "icon": "📚"},
    {"id": "pop", "name": "Ommabop", "icon": "🔥"},
    {"id": "badiiy", "name": "Badiiy adabiyot", "icon": "📖"},
    {"id": "biznes", "name": "Biznes & Moliya", "icon": "💼"},
    {"id": "psixologiya", "name": "Psixologiya", "icon": "🧠"},
    {"id": "diniy", "name": "Diniy & Ma'rifiy", "icon": "🕌"},
    {"id": "tarix", "name": "Tarix & Fan", "icon": "📜"},
    {"id": "bolalar", "name": "Bolalar uchun", "icon": "🧸"},
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
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


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
        norm_lat = f"{_normalize(title)} {_normalize(author)} {_normalize(desc)}"
        raw_lower = f"{title} {author} {desc}".lower()
        item["_search"] = f"{norm_lat} {raw_lower} {bid}"
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
        raw_words = query.lower().split()
        filtered = [
            b for b in filtered
            if (words and all(w in b.get("_search", "") for w in words)) or
               (raw_words and all(w in b.get("_search", "") for w in raw_words))
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


def get_book_by_id(book_id: str | int) -> Optional[Dict[str, Any]]:
    """Kitobni ID orqali olish (mahalliy yoki upstream katalogidan)."""
    load_books()
    bid = str(book_id).strip()
    book = _BOOKS_BY_ID.get(bid)
    if book:
        return book

    # Agar lokal bazada bo'lmasa, upstream katalogidan olishga urinish
    try:
        import urllib.request
        url = f"https://161-97-96-58.sslip.io/api/books/b/{bid}"
        req = urllib.request.Request(url, headers={"User-Agent": "BauntyBot/2.0"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok") and data.get("book"):
                    ub = data["book"]
                    title = ub.get("t") or f"Kitob #{bid}"
                    author = ub.get("a") or "Noma'lum muallif"
                    category_code = ub.get("g") or "badiiy"
                    meta = next((c for c in CATEGORIES_META if c["id"] == category_code), None)
                    category_name = meta["name"] if meta else "Badiiy adabiyot"
                    desc = ub.get("desc") or f"{title} — {author} asari."
                    size_bytes = (ub.get("s") or {}).get("pdf") or 2500000
                    size_mb = round(size_bytes / 1048576, 1) if size_bytes else 2.5

                    book_obj = {
                        "id": str(ub.get("i", bid)),
                        "title": title,
                        "author": author,
                        "category": category_code,
                        "category_name": category_name,
                        "pages": ub.get("p") or 120,
                        "lang": ub.get("l") or "uz",
                        "year": ub.get("y"),
                        "rating": ub.get("r") or 4.9,
                        "views": (ub.get("rd") or 10) * 150,
                        "format": "PDF",
                        "size_mb": size_mb,
                        "popular": True,
                        "description": desc,
                        "sample_text": f"«{title}» ({author}) kitobining mutolaa va tanishuv nusxasi.",
                        "cover": f"https://161-97-96-58.sslip.io/bk/{ub.get('i', bid)}/cover_l.webp" if ub.get("c") else "",
                        # Upstream mosligi (i, t, a, c, p, l, g, f)
                        "i": ub.get("i", int(bid) if bid.isdigit() else 0),
                        "t": title,
                        "a": author,
                        "c": ub.get("c", 0),
                        "p": ub.get("p", 120),
                        "l": ub.get("l", "uz"),
                        "g": category_code,
                        "f": ub.get("f", ["pdf"]),
                    }
                    _BOOKS_BY_ID[bid] = book_obj
                    return book_obj
    except Exception as e:
        logger.debug(f"Upstreamdan kitob #{book_id} yuklab bo'lmadi: {e}")

    return None


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
        b["c"] = b.get("c") or (1 if b.get("cover") else 0)
        b["p"] = b.get("p") or b.get("pages", 100)
        b["l"] = b.get("l") or b.get("lang", "uz")
        b["f"] = b.get("f") or [b.get("format", "pdf").lower()]
        normalized.append(b)
    return normalized


def create_book_pdf_sample(book: Dict[str, Any]) -> bytes:
    """Kitob uchun chiroyli PDF mutolaa nusxasini yaratish (Pillow/ReportLab yordamida)."""
    title = book.get("title", "Kitob")
    author = book.get("author", "Noma'lum muallif")
    desc = book.get("description", "")
    sample = book.get("sample_text", desc)
    category_name = book.get("category_name", "Badiiy adabiyot")
    pages = book.get("pages", 200)

    # 1. Agar ReportLab mavjud bo'lsa
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "BookTitle",
            parent=styles["Title"],
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#1A1D20"),
            alignment=1,
            spaceAfter=12
        )
        author_style = ParagraphStyle(
            "BookAuthor",
            parent=styles["Normal"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#E5484D"),
            alignment=1,
            spaceAfter=18
        )
        meta_style = ParagraphStyle(
            "BookMeta",
            parent=styles["Normal"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#6C757D"),
            alignment=1,
            spaceAfter=24
        )
        body_style = ParagraphStyle(
            "BookBody",
            parent=styles["Normal"],
            fontSize=12,
            leading=18,
            textColor=colors.HexColor("#2B2D42"),
            spaceAfter=14
        )
        footer_style = ParagraphStyle(
            "BookFooter",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#8D99AE"),
            alignment=1
        )

        elements = [
            Paragraph(f"<b>{title}</b>", title_style),
            Paragraph(f"✍️ Muallif: <b>{author}</b>", author_style),
            Paragraph(f"📂 Janr: {category_name} | 📄 {pages} sahifa | ⭐ Reyting: {book.get('rating', 4.9)}", meta_style),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=20),
            Paragraph("<b>Qisqacha mazmuni:</b>", ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#1A1D20"))),
            Spacer(1, 6),
            Paragraph(desc, body_style),
            Spacer(1, 14),
            Paragraph("<b>Kitobdan parcha (Mutolaa):</b>", ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#1A1D20"))),
            Spacer(1, 6),
            Paragraph(sample, body_style),
            Spacer(1, 30),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=14),
            Paragraph(f"📚 Baunty Kutubxonasi — @{config.BOT_USERNAME.lstrip('@')} | {config.CHANNEL_USERNAME}", footer_style)
        ]

        doc.build(elements)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        logger.info(f"ReportLab orqali PDF generatsiyasida xatolik ({e}), matnli PDF nusxa tayyorlanadi.")

    # 2. Oddiy zaxira matnli PDF
    pdf_content = (
        f"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        f"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        f"3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R/Resources<<>>>>endobj\n"
        f"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n"
        f"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n"
    )
    return pdf_content.encode("utf-8")


async def deliver_book(
    bot: Any,
    chat_id: int | str,
    book_id: str | int
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

    caption = (
        f"📚 <b>{title}</b>\n\n"
        f"✍️ <b>Muallif:</b> {author}\n"
        f"📂 <b>Toifa:</b> {category_name}\n"
        f"📄 <b>Sahifalar:</b> {pages} ta | 💾 <b>Format:</b> PDF ({book.get('size_mb', 2.5)} MB)\n"
        f"⭐ <b>Reyting:</b> {rating} / 5.0\n\n"
        f"📖 <i>{short_desc}</i>\n\n"
        f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} • {config.CHANNEL_USERNAME}</b>"
    )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile

    bot_user = config.BOT_USERNAME.lstrip("@")
    webapp_url = f"{config.WEBAPP_URL}?books&b={book['id']}" if config.WEBAPP_URL else None

    buttons = []
    if webapp_url:
        from aiogram.types import WebAppInfo
        buttons.append([InlineKeyboardButton(text="📖 Ilovada o'qish (Mutolaa)", web_app=WebAppInfo(url=webapp_url))])

    share_url = f"https://t.me/share/url?url=https://t.me/{bot_user}?start=b_{book['id']}&text={title}%20kitobini%20o'qish"
    buttons.append([
        InlineKeyboardButton(text="🔗 Do'stlarga ulashish", url=share_url),
        InlineKeyboardButton(text="📚 Barcha kitoblar", url=f"https://t.me/{bot_user}?start=books")
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    # PDF faylni generatsiya qilib yoki yuklab yuborish
    try:
        pdf_bytes = create_book_pdf_sample(book)
        safe_filename = re.sub(r'[^\w\s-]', '', f"{title} - {author}").strip() + ".pdf"
        input_file = BufferedInputFile(pdf_bytes, filename=safe_filename)

        await bot.send_document(
            chat_id=chat_id,
            document=input_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb
        )
        return {"ok": True, "delivered": True, "book": book}
    except Exception as e:
        logger.warning(f"Kitob hujjatini yuborishda xatolik ({e}), xabar sifatida yuboriladi.")
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=kb
            )
            return {"ok": True, "delivered": True, "book": book}
        except Exception as e2:
            logger.error(f"Kitobni chatga yetkazib bo'lmadi: {e2}")
            return {"ok": False, "error": str(e2)}
