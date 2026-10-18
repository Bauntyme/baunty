"""Kitoblar va Kutubxona bo'limi testlari (Tests for Books feature)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from services import book_service
from services.web_server import create_web_app


def test_books_load_and_catalog():
    """Kitoblar bazasi to'g'ri yuklanishi va katalog ishlashini tekshirish."""
    books = book_service.load_books()
    assert len(books) >= 15, "Kamida 15 ta sara kitob bo'lishi kerak"

    first = books[0]
    assert "id" in first
    assert "title" in first
    assert "author" in first
    assert "category" in first
    assert "description" in first


def test_books_catalog_filtering():
    """Toifalar va qidiruv bo'yicha saralashni tekshirish."""
    # Badiiy toifasi
    badiiy = book_service.get_catalog(category="badiiy")
    assert badiiy["ok"] is True
    assert len(badiiy["items"]) > 0
    for b in badiiy["items"]:
        assert b["category"] == "badiiy"

    # Ommabop (pop)
    pop = book_service.get_catalog(category="pop")
    assert pop["ok"] is True
    assert len(pop["items"]) > 0

    # Qidiruv: "Alkimyogar"
    search_res = book_service.get_catalog(query="Alkimyogar")
    assert search_res["ok"] is True
    assert len(search_res["items"]) >= 1
    assert "Alkimyogar" in search_res["items"][0]["title"]


def test_get_book_by_id():
    """ID bo'yicha kitobni olish."""
    b1 = book_service.get_book_by_id("1")
    assert b1 is not None
    assert b1["id"] == "1"
    assert "O'tkan kunlar" in b1["title"]

    b_none = book_service.get_book_by_id("999999")
    assert b_none is None


def test_create_book_pdf_sample():
    """Kitob PDF mutolaa nusxasi generatsiyasini tekshirish."""
    b = book_service.get_book_by_id("1")
    assert b is not None
    pdf_bytes = book_service.create_book_pdf_sample(b)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 50
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_deliver_book():
    """Kitobni Telegram chatga yetkazishni tekshirish."""
    mock_bot = MagicMock()
    mock_bot.send_document = AsyncMock()
    mock_bot.send_message = AsyncMock()

    res = await book_service.deliver_book(
        bot=mock_bot,
        chat_id=123456789,
        book_id="1"
    )
    assert res["ok"] is True
    assert res["delivered"] is True
    assert mock_bot.send_document.called or mock_bot.send_message.called


def test_no_branding_leaks_in_books():
    """Kitoblar xizmatida va ma'lumotlarida 'Zakirovs' yo'qligini tekshirish."""
    books = book_service.load_books()
    for b in books:
        for val in b.values():
            if isinstance(val, str):
                assert "Zakirovs" not in val
                assert "zakirovs" not in val
                assert "@Zakirovsfilms_bot" not in val


class TestBooksWebServerAPI(AioHTTPTestCase):
    """Web server API testlari."""

    async def get_application(self):
        return create_web_app()

    @unittest_run_loop
    async def test_api_catalog_includes_books(self):
        """Katalog API da books: True bo'lishi kerak."""
        resp = await self.client.request("GET", "/api/catalog")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("books") is True

    @unittest_run_loop
    async def test_api_books_list(self):
        """GET /api/books kitoblar ro'yxatini qaytarishi kerak."""
        resp = await self.client.request("GET", "/api/books")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert "items" in data
        assert len(data["items"]) >= 15
        assert "categories" in data

    @unittest_run_loop
    async def test_api_books_search(self):
        """GET /api/books/search?q=... qidiruv natijalarini qaytarishi kerak."""
        resp = await self.client.request("GET", "/api/books/search?q=Atom")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert len(data["items"]) >= 1
        assert any("Atom" in b["title"] for b in data["items"])

    @unittest_run_loop
    async def test_api_book_detail(self):
        """GET /api/books/{id} kitob ma'lumotlarini qaytarishi kerak."""
        resp = await self.client.request("GET", "/api/books/1")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert data["book"]["id"] == "1"

    @unittest_run_loop
    async def test_api_book_pdf_download(self):
        """GET /api/books/{id}/pdf PDF faylini qaytarishi kerak."""
        resp = await self.client.request("GET", "/api/books/1/pdf")
        assert resp.status == 200
        assert resp.headers.get("Content-Type") == "application/pdf"
        body = await resp.read()
        assert body.startswith(b"%PDF")

    @unittest_run_loop
    async def test_api_book_send_fallback_bot_url(self):
        """POST /api/books/send user_id bo'lmaganda bot havolasini qaytarishi kerak."""
        resp = await self.client.request(
            "POST",
            "/api/books/send",
            json={"id": "1"}
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is False
        assert data["action"] == "open_bot"
        assert "start=b_1" in data["url"]
