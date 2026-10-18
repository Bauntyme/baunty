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
        title = item.get("title", "")
        author = item.get("author", "")
        desc = item.get("description", "")
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
    """Kitobni ID orqali olish."""
    load_books()
    return _BOOKS_BY_ID.get(str(book_id))


def search_books(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Kitoblarni tezkor qidirish."""
    if not query:
        return []
    res = get_catalog(query=query, limit=limit)
    return res.get("items", [])


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
