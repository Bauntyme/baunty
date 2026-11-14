"""
Ziyouz.com O'zbek va jahon adabiyoti kutubxonasi integratsiyasi.
9,900+ haqiqiy o'zbek tilidagi PDF kitoblar katalogi, tezkor kirill/lotin qidiruv,
PDF oqimini proksi qilish va matnli boblarni ajratib olish xizmati.
"""
import asyncio
import html
import io
import json
import logging
import re
import time
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from config import BASE_DIR
from utils.translit import get_both_scripts

logger = logging.getLogger(__name__)

ZIYOUZ_BASE = "https://n.ziyouz.com"
ZIYOUZ_CATALOG_PATH = BASE_DIR / "data" / "ziyouz_books.json"
ZIYOUZ_CACHE_DIR = BASE_DIR / "data" / "ziyouz_cache"

GENRE_UZ_NAMES: Dict[str, str] = {
    "badiiy": "Badiiy adabiyot",
    "fantastika": "Fantastika",
    "detektiv": "Detektiv",
    "psixologiya": "Psixologiya",
    "biznes": "Biznes va ilm",
    "hikoya": "Hikoyalar",
    "falsafa": "Falsafa",
    "sarguzasht": "Sarguzasht",
    "diniy": "Ma'rifiy va diniy",
    "bolalar": "Bolalar adabiyoti",
    "sheriyat": "She'riyat",
    "tarix": "Tarixiy kitoblar",
}

COVER_THEMES: Dict[str, List[str]] = {
    "badiiy": ["#1E293B", "#0F172A", "#F59E0B"],
    "fantastika": ["#1E1B4B", "#090822", "#818CF8"],
    "detektiv": ["#18181B", "#09090B", "#EF4444"],
    "psixologiya": ["#064E3B", "#022C22", "#34D399"],
    "biznes": ["#0F172A", "#1E3A8A", "#38BDF8"],
    "hikoya": ["#4C1D95", "#2E1065", "#C084FC"],
    "falsafa": ["#431407", "#1C0A00", "#FB923C"],
    "sarguzasht": ["#065F46", "#022C22", "#FBBF24"],
    "diniy": ["#14532D", "#052E16", "#FDE047"],
    "bolalar": ["#831843", "#500724", "#F472B6"],
    "sheriyat": ["#581C87", "#2E1065", "#E879F9"],
    "tarix": ["#713F12", "#271402", "#FACC15"],
}


def _strip_pdf_text_pure(pdf_bytes: bytes, max_pages: int = 18) -> List[str]:
    """pypdf mavjud bo'lmaganda FlateDecode streamlaridan matn ajratish zaxira usuli."""
    pages_txt: List[str] = []
    # FlateDecode Compressed Streams ni qidirish
    for m in re.finditer(rb"stream[\r\n]+(.*?)[\r\n]*endstream", pdf_bytes, re.S):
        raw_stream = m.group(1)
        data = raw_stream
        if not raw_stream.lstrip().startswith(b"BT"):
            try:
                data = zlib.decompress(raw_stream)
            except Exception:
                continue
        if b"BT" not in data or b"ET" not in data:
            continue
        chunks: List[str] = []
        for lit in re.findall(rb"\(([^()\\]*(?:\\.[^()\\]*)*)\)\s*(?:Tj|'|\"|\])", data):
            try:
                s = lit.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
                if s.startswith(b"\xfe\xff"):
                    txt = s[2:].decode("utf-16-be", errors="ignore")
                else:
                    txt = s.decode("utf-8", errors="ignore") or s.decode("cp1251", errors="ignore")
                txt = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", "", txt)
                if txt.strip():
                    chunks.append(txt)
            except Exception:
                continue
        joined = " ".join(chunks).strip()
        # Faqat o'qiladigan harfli matnlarni qabul qilish (shrift glyph shovqinini rad etish)
        if len(joined) >= 120 and sum(c.isalpha() for c in joined) / max(len(joined), 1) > 0.45:
            pages_txt.append(re.sub(r"\s+", " ", joined).strip())
            if len(pages_txt) >= max_pages:
                break
    return pages_txt


def _extract_pdf_text_pages(pdf_bytes: bytes, max_pages: int = 35) -> Tuple[List[str], int]:
    """PDF baytlaridan sahifama-sahifa toza UTF-8 matn ajratish."""
    total_pages = 0
    pages: List[str] = []
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        total_pages = len(reader.pages)
        for idx, page in enumerate(reader.pages[:max_pages]):
            try:
                txt = (page.extract_text() or "").strip()
            except Exception:
                txt = ""
            txt = re.sub(r"[ \t]+", " ", txt)
            txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
            if len(txt) >= 40 and sum(c.isalpha() for c in txt) / max(len(txt), 1) > 0.35:
                pages.append(txt)
    except ImportError:
        pages = _strip_pdf_text_pure(pdf_bytes, max_pages=max_pages)
    except Exception as exc:
        logger.debug("pypdf PDF extract error: %s", exc)
        pages = _strip_pdf_text_pure(pdf_bytes, max_pages=max_pages)

    return pages, total_pages


class ZiyouzLibraryService:
    """9,900+ haqiqiy o'zbek va jahon adabiyoti PDF kitoblari boshqaruvi."""

    def __init__(self) -> None:
        self._items: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self._mem_toc_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def load(self) -> List[Dict[str, Any]]:
        if self._loaded:
            return self._items
        self._loaded = True
        if not ZIYOUZ_CATALOG_PATH.exists():
            logger.warning("Ziyouz catalog topilmadi: %s", ZIYOUZ_CATALOG_PATH)
            return []
        try:
            raw = json.loads(ZIYOUZ_CATALOG_PATH.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            items: List[Dict[str, Any]] = []
            by_id: Dict[str, Dict[str, Any]] = {}
            for row in raw:
                if not isinstance(row, dict) or not row.get("i") or not row.get("t"):
                    continue
                bid = str(row["i"])
                genre = str(row.get("g") or "badiiy")
                g_name = str(row.get("gn") or GENRE_UZ_NAMES.get(genre, "Badiiy adabiyot"))
                title = html.unescape(str(row.get("t") or "")).strip()
                author = html.unescape(str(row.get("a") or "Ziyouz Kutubxonasi")).strip()
                sz = float(row.get("sz") or 1.5)
                views = int(row.get("v") or 100)
                yr = int(row.get("y") or 2020)
                cs = str(row.get("cs") or "")
                fs = str(row.get("fs") or "")
                fid = int(row.get("fid") or (int(row["i"]) - 100000))
                dl_url = f"{ZIYOUZ_BASE}/kutubxona/category/{cs}?download={fid}:{fs}" if (cs and fs) else ""
                pages_est = max(16, min(1200, int(sz * 42)))
                rating = round(min(4.95, 4.55 + min(views, 50000) / 125000.0), 2)
                desc = (
                    f"{author} — «{title}». {g_name} bo'limidagi to'liq o'zbekcha elektron kitob "
                    f"({row.get('f', 'PDF')}, {sz:.2f} MB, {views:,} marta yuklab olingan)."
                )
                fmt_str = str(row.get("f") or "PDF").upper()
                fmt_low = fmt_str.lower()
                if fmt_low not in ("pdf", "epub", "fb2", "txt"):
                    fmt_low = "pdf"
                size_bytes = max(65536, int(sz * 1048576))
                rating_cnt = max(12, min(9500, views // 25))
                norm = {
                    "id": bid,
                    "i": int(row["i"]),
                    "fid": fid,
                    "t": title,
                    "title": title,
                    "a": author,
                    "author": author,
                    "g": genre,
                    "category": genre,
                    "category_name": g_name,
                    "gn": g_name,
                    "lang": "uz",
                    "l": "uz",
                    "y": yr,
                    "year": yr,
                    "r": rating,
                    "rating": rating,
                    "rn": rating_cnt,
                    "pg": pages_est,
                    "pages": pages_est,
                    "p": pages_est,
                    "v": views,
                    "views": views,
                    "f": [fmt_low],
                    "format": fmt_str,
                    "s": {fmt_low: size_bytes},
                    "sz": sz,
                    "size_mb": sz,
                    "c": 1,
                    "cv": 1,
                    "src": "ziyouz",
                    "cs": cs,
                    "fs": fs,
                    "download_url": dl_url,
                    "pdf_url": f"api/books/{bid}/pdf",
                    "description": desc,
                    "d": desc,
                    "popular": views >= 5000,
                    "new": yr >= 2022,
                }
                items.append(norm)
                by_id[bid] = norm
            self._items = items
            self._by_id = by_id
            logger.info("Ziyouz kutubxona yuklandi: %d ta haqiqiy kitob", len(items))
        except Exception as exc:
            logger.error("Ziyouz katalog yuklash xatosi: %s", exc)
        return self._items

    def get_by_id(self, book_id: Any) -> Optional[Dict[str, Any]]:
        self.load()
        return self._by_id.get(str(book_id).strip())

    def count(self) -> int:
        return len(self.load())

    def search(
        self,
        query: str = "",
        genre: str = "",
        lang: str = "",
        sort: str = "top",
        limit: int = 36,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        items = self.load()
        if not items:
            return [], 0
        filtered = items
        if lang and lang.lower() not in ("all", "uz"):
            # Ziyouz asosan O'zbek kutubxonasi; faqat "ru"/"en" filtri so'ralsa kirill/english izlaymiz
            l_low = lang.lower()
            if l_low == "en":
                filtered = [b for b in filtered if "english" in b["gn"].lower()]
            elif l_low == "ru":
                filtered = [b for b in filtered if any("а" <= ch <= "я" or "А" <= ch <= "Я" for ch in b["t"])]
        if genre and genre.lower() not in ("all", "top", "new", ""):
            g_low = genre.lower()
            filtered = [b for b in filtered if b["g"] == g_low]
        q_clean = str(query or "").strip()
        if q_clean:
            forms = [f.lower() for f in get_both_scripts(q_clean) if f.strip()]
            scored: List[Tuple[int, Dict[str, Any]]] = []
            for b in filtered:
                t_low = b["t"].lower()
                a_low = b["a"].lower()
                gn_low = b["gn"].lower()
                best = 0
                for form in forms:
                    tokens = form.split()
                    if t_low == form:
                        best = max(best, 100)
                    elif t_low.startswith(form):
                        best = max(best, 90)
                    elif form in t_low:
                        best = max(best, 75)
                    elif form in a_low:
                        best = max(best, 70)
                    elif len(tokens) > 1 and all(tok in f"{t_low} {a_low} {gn_low}" for tok in tokens):
                        best = max(best, 60)
                    elif form in gn_low:
                        best = max(best, 40)
                if best > 0:
                    scored.append((best, b))
            scored.sort(key=lambda x: (-x[0], -x[1]["v"]))
            filtered = [x[1] for x in scored]
        else:
            if sort == "new" or genre == "new":
                filtered = sorted(filtered, key=lambda x: (-x["y"], -x["v"]))
            elif sort == "az":
                filtered = sorted(filtered, key=lambda x: x["t"].lower())
            else:
                filtered = sorted(filtered, key=lambda x: -x["v"])

        total = len(filtered)
        return filtered[offset: offset + limit], total

    async def fetch_pdf_bytes(self, book: Dict[str, Any], timeout_s: float = 28.0) -> Optional[bytes]:
        """Ziyouzdan haqiqiy PDF faylni yuklab olish."""
        dl_url = str(book.get("download_url") or "").strip()
        if not dl_url:
            return None
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            "Referer": f"{ZIYOUZ_BASE}/kutubxona",
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(dl_url, timeout=aiohttp.ClientTimeout(total=timeout_s, connect=8), allow_redirects=True) as resp:
                    if resp.status != 200:
                        return None
                    ct = (resp.headers.get("Content-Type") or "").lower()
                    if "text/html" in ct:
                        return None
                    data = await resp.read()
                    if data and (data.startswith(b"%PDF") or "pdf" in ct or len(data) > 4096):
                        return data
        except Exception as exc:
            logger.debug("Ziyouz PDF fetch error (%s): %s", book.get("id"), exc)
        return None

    async def get_book_chapters_data(self, book_id: Any) -> Optional[Dict[str, Any]]:
        """Kitob boblari (TOC + matn bo'limlari) ni real PDF dan ajratib keshlash."""
        book = self.get_by_id(book_id)
        if not book:
            return None
        bid = str(book["i"])
        now = time.time()
        cached = self._mem_toc_cache.get(bid)
        if cached and now - cached[0] < 3600:
            return cached[1]

        ZIYOUZ_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = ZIYOUZ_CACHE_DIR / f"{bid}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("chapters"):
                    self._mem_toc_cache[bid] = (now, data)
                    return data
            except Exception:
                pass

        # Katta (>20MB) PDF larni web readerda bir zumda chiqarish uchun faqat <=20MB dan matn ajratamiz
        pages_txt: List[str] = []
        total_pages = int(book.get("pg") or 120)
        if float(book.get("sz") or 0) <= 20.0:
            pdf_bytes = await self.fetch_pdf_bytes(book, timeout_s=22.0)
            if pdf_bytes and pdf_bytes.startswith(b"%PDF"):
                pages_txt, pdf_total = await asyncio.to_thread(_extract_pdf_text_pages, pdf_bytes, 40)
                if pdf_total > 0:
                    total_pages = pdf_total

        chapters: List[Dict[str, Any]] = []
        if pages_txt:
            combined = "\n\n".join(pages_txt)
            # Matnni ~4000 belgilik qulay o'qish boblariga ajratish
            chunk_size = max(2500, min(5500, len(combined) // 6 or 3000))
            pos = 0
            idx = 1
            while pos < len(combined) and idx <= 12:
                end = min(len(combined), pos + chunk_size)
                if end < len(combined):
                    br = combined.rfind("\n", pos + chunk_size // 2, end + 400)
                    if br == -1:
                        br = combined.rfind(". ", pos + chunk_size // 2, end + 200)
                    if br > pos:
                        end = br + 1
                part_txt = combined[pos:end].strip()
                if part_txt:
                    chapters.append({
                        "n": idx,
                        "t": f"{idx}-bo'lim" if idx > 1 else "Asarning boshlanishi",
                        "p": max(1, len(part_txt) // 350),
                        "text": part_txt,
                    })
                    idx += 1
                pos = end
        if not chapters:
            chapters = [
                {
                    "n": 1,
                    "t": "Kitob haqida & To'liq PDF",
                    "p": total_pages,
                    "text": (
                        f"{book['t']}\nMuallif: {book['a']}\nBo'lim: {book['gn']}\n"
                        f"Hajmi: {book['sz']:.2f} MB · PDF format\n\n"
                        "Ushbu asar Ziyouz kutubxonasining asl skanerlangan yoki to'liq PDF nashridir. "
                        "Asarni to'liq ko'rinishda o'qish va saqlab olish uchun «To'liq PDF ochish» "
                        "yoki «Telegram'ga yuborish» tugmalaridan foydalaning."
                    ),
                }
            ]

        toc_entries = [{"n": ch["n"], "t": ch["t"], "p": ch["p"]} for ch in chapters]
        payload = {
            "id": int(bid),
            "title": book["t"],
            "author": book["a"],
            "pages": total_pages,
            "pdf_url": f"/api/books/{bid}/pdf",
            "download_url": book.get("download_url") or "",
            "toc": toc_entries,
            "chapters": chapters,
        }
        try:
            cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        if len(self._mem_toc_cache) > 120:
            self._mem_toc_cache.clear()
        self._mem_toc_cache[bid] = (now, payload)
        return payload


ziyouz_service = ZiyouzLibraryService()
