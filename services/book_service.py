"""Kitoblar va Kutubxona xizmati (Book Service).

O'zbek va jahon adabiyoti, biznes, psixologiya va diniy kitoblarni qidirish,
katalogini taqdim etish hamda foydalanuvchi chatiga PDF shaklida yuborish.
To'liq oq brendlangan: Baunty, Baunty Films, @BauntyCinemabot.
"""

from __future__ import annotations

import html
import io
import json
import logging
import os
import re
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
        item["c"] = 1 if item.get("cover") else 0
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
        raw_words = query.lower().split()
        clean_q = re.sub(r"['`ʻʼ’´]", "", query).lower().strip()
        clean_words = clean_q.split()
        cyr_ru_q = query.lower().replace("қ", "к").replace("ў", "у").replace("ғ", "г").replace("ҳ", "х")
        cyr_ru_words = cyr_ru_q.split()

        from utils.translit import cyrillic_to_latin, latin_to_cyrillic
        cyr_to_lat = cyrillic_to_latin(query).lower()
        cyr_to_lat_words = _normalize(cyr_to_lat).split()
        lat_to_cyr = latin_to_cyrillic(query).lower()
        lat_to_cyr_words = lat_to_cyr.split()

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


def get_book_by_id(book_id: str | int) -> Optional[Dict[str, Any]]:
    """Kitobni ID orqali olish (mahalliy yoki upstream katalogidan)."""
    load_books()
    raw = str(book_id).strip()
    bid = re.sub(r'^(?:book_|books_|b_|kitob_)', '', raw).strip()
    book = _BOOKS_BY_ID.get(bid) or _BOOKS_BY_ID.get(raw)
    if book:
        return book

    # Faqat raqamli bo'lsa va lokal bazada bo'lmasa, upstream katalogidan olishga urinish
    if bid.isdigit():
        try:
            import urllib.request
            url = f"https://161-97-96-58.sslip.io/api/books/b/{bid}"
            req = urllib.request.Request(url, headers={"User-Agent": "BauntyBot/2.0"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
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
                            # Upstream mosligi (i, t, a, c, p, l, g, f, s)
                            "i": ub.get("i", int(bid) if bid.isdigit() else 0),
                            "t": title,
                            "a": author,
                            "c": ub.get("c", 0),
                            "p": ub.get("p", 120),
                            "l": ub.get("l", "uz"),
                            "g": category_code,
                            "f": ["pdf", "epub"],
                            "s": {"pdf": size_bytes, "epub": int(size_bytes * 0.55)},
                        }
                        _BOOKS_BY_ID[bid] = book_obj
                        _BOOKS_BY_ID[raw] = book_obj
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
    """Kitob uchun chiroyli PDF mutolaa nusxasini yaratish (ReportLab yoki Pillow yordamida)."""
    title = book.get("title", "Kitob")
    author = book.get("author", "Noma'lum muallif")
    desc = book.get("description", "")
    sample = book.get("sample_text", desc)
    category_name = book.get("category_name", "Badiiy adabiyot")
    pages = book.get("pages", 200)

    # 1. Agar ReportLab mavjud bo'lsa
    try:
        import html
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
            Paragraph(f"<b>{html.escape(title)}</b>", title_style),
            Paragraph(f"✍️ Muallif: <b>{html.escape(author)}</b>", author_style),
            Paragraph(f"📂 Janr: {html.escape(category_name)} | 📄 {pages} sahifa | ⭐ Reyting: {book.get('rating', 4.9)}", meta_style),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=20),
            Paragraph("<b>Qisqacha mazmuni:</b>", ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#1A1D20"))),
            Spacer(1, 6),
            Paragraph(html.escape(desc), body_style),
            Spacer(1, 14),
            Paragraph("<b>Kitobdan parcha (Mutolaa):</b>", ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#1A1D20"))),
            Spacer(1, 6),
            Paragraph(html.escape(sample), body_style),
            Spacer(1, 30),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=14),
            Paragraph(f"📚 Baunty Kutubxonasi — @{config.BOT_USERNAME.lstrip('@')} | {config.CHANNEL_USERNAME}", footer_style)
        ]

        doc.build(elements)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        logger.debug(f"ReportLab orqali PDF generatsiyasida xatolik ({e}), Pillow yordamida yaratiladi.")

    # 2. Pillow (PIL) yordamida to'liq, sifatli va o'qiladigan 2 sahifali PDF
    try:
        import textwrap
        from PIL import Image, ImageDraw

        W, H = 1200, 1600
        p1 = Image.new("RGB", (W, H), color=(253, 251, 247))
        d1 = ImageDraw.Draw(p1)
        d1.rectangle([(0, 0), (W, 110)], fill=(26, 29, 32))
        d1.text((50, 40), f"BAUNTY KUTUBXONASI — @{config.BOT_USERNAME.lstrip('@')}", fill=(255, 255, 255))
        d1.text((50, 160), title[:45], fill=(26, 29, 32))
        d1.text((50, 220), f"Muallif: {author[:50]}", fill=(229, 72, 77))
        d1.text((50, 270), f"Janr: {category_name}  |  {pages} bet  |  Reyting: {book.get('rating', 4.9)}/5.0", fill=(108, 117, 125))
        d1.line([(50, 315), (W - 50, 315)], fill=(226, 232, 240), width=2)
        d1.text((50, 340), "QISQACHA MAZMUNI:", fill=(26, 29, 32))
        y = 390
        for line in textwrap.wrap(desc, width=68):
            d1.text((50, y), line, fill=(43, 45, 66))
            y += 34
            if y > H - 100:
                break
        d1.line([(50, H - 70), (W - 50, H - 70)], fill=(226, 232, 240), width=1)
        d1.text((50, H - 50), f"Baunty Books • {config.CHANNEL_USERNAME} • 1-sahifa", fill=(141, 153, 174))

        p2 = Image.new("RGB", (W, H), color=(253, 251, 247))
        d2 = ImageDraw.Draw(p2)
        d2.rectangle([(0, 0), (W, 110)], fill=(26, 29, 32))
        d2.text((50, 40), f"«{title[:40]}» — MUTOLAA PARCHASI", fill=(255, 255, 255))
        y = 150
        d2.text((50, y), "KITOBDAN PARCHA:", fill=(26, 29, 32))
        y += 45
        for line in textwrap.wrap(sample, width=68):
            d2.text((50, y), line, fill=(43, 45, 66))
            y += 34
            if y > H - 100:
                break
        d2.line([(50, H - 70), (W - 50, H - 70)], fill=(226, 232, 240), width=1)
        d2.text((50, H - 50), f"Baunty Books • @{config.BOT_USERNAME.lstrip('@')} • 2-sahifa", fill=(141, 153, 174))

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
