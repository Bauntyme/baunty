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

    @unittest_run_loop
    async def test_api_books_language_filter(self):
        """GET /api/books?lang=en va lang=ru tildagi kitoblarni to'g'ri qaytarishi kerak."""
        resp_en = await self.client.request("GET", "/api/books?lang=en")
        assert resp_en.status == 200
        data_en = await resp_en.json()
        assert data_en["ok"] is True
        assert len(data_en["items"]) > 0
        for b in data_en["items"]:
            assert b["lang"] == "en"

        resp_ru = await self.client.request("GET", "/api/books?lang=ru")
        assert resp_ru.status == 200
        data_ru = await resp_ru.json()
        assert data_ru["ok"] is True
        assert len(data_ru["items"]) > 0
        for b in data_ru["items"]:
            assert b["lang"] == "ru"


def test_books_languages_catalog():
    """3 tilda kitoblar (uz, en, ru) mavjudligini tekshirish."""
    uz = book_service.get_catalog(lang="uz")
    en = book_service.get_catalog(lang="en")
    ru = book_service.get_catalog(lang="ru")

    assert len(uz["items"]) >= 15, "Kamida 15 ta o'zbekcha kitob bo'lishi kerak"
    assert len(en["items"]) >= 5, "Kamida 5 ta inglizcha kitob bo'lishi kerak"
    assert len(ru["items"]) >= 5, "Kamida 5 ta ruscha kitob bo'lishi kerak"


def test_webapp_index_structure_and_order():
    """index.html da segmented bar tartibi va random dice tugmasini tekshirish."""
    index_path = book_service.BASE_DIR / "webapp" / "index.html"
    assert index_path.exists()
    content = index_path.read_text(encoding="utf-8")

    # 1. Segmented bar ketma-ketligi: kino -> music -> books -> games -> story -> docs -> tv
    seg_match = content.find('data-m="kino"') < content.find('data-m="music"') < \
                content.find('data-m="books"') < content.find('data-m="games"') < \
                content.find('data-m="story"') < content.find('data-m="docs"') < \
                content.find('data-m="tv"')
    assert seg_match, "Segmented bar tartibi: Kinolar -> Musiqa -> Kitoblar -> O'yinlar -> Story -> Hujjatlar -> TV bo'lishi shart"

    # 2. Random kubik (dice) tugmasi mavjudligi
    assert "zkDice" in content or "zk-dice" in content
    assert "openDetail(rnd)" in content or "openDetail(" in content


def test_books_cyrillic_search_transliteration():
    """Kirill yozuvida qidirganda ham kitoblar to'g'ri topilishini tekshirish."""
    # 1. 'Ўткан кунлар' -> O'tkan kunlar
    res_cyr = book_service.get_catalog(query="Ўткан кунлар")
    assert res_cyr["ok"] is True
    assert len(res_cyr["items"]) >= 1
    assert "O'tkan kunlar" in res_cyr["items"][0]["title"]

    # 2. 'Абдулла Қодирий' -> Abdulla Qodiriy
    res_author = book_service.get_catalog(query="Абдулла Қодирий")
    assert res_author["ok"] is True
    assert len(res_author["items"]) >= 2

    # 3. 'Атом' -> Atom odatlar / Atomic Habits / Атомные привычки
    res_atom = book_service.get_catalog(query="Атом")
    assert res_atom["ok"] is True
    assert len(res_atom["items"]) >= 2


def test_books_js_and_css_quality_invariants():
    """books.js va books.css dagi xatoliklar bartaraf etilganini tekshirish."""
    js_path = book_service.BASE_DIR / "webapp" / "books.js"
    css_path = book_service.BASE_DIR / "webapp" / "books.css"
    html_path = book_service.BASE_DIR / "webapp" / "index.html"

    js_code = js_path.read_text(encoding="utf-8")
    css_code = css_path.read_text(encoding="utf-8")
    html_code = html_path.read_text(encoding="utf-8")

    # 1. Zakirovs so'zi kommentariyada ham qolmagan bo'lishi kerak
    assert "Zakirovs" not in js_code
    assert "Zakirovs" not in css_code

    # 2. BackButton listener books.js da mavjud bo'lishi kerak
    assert "tg.BackButton.onClick" in js_code
    assert "ZBooks.busy" in html_code

    # 3. Reader matni A+/A- bosilganda bkReaderText orqali shrifti o'zgarishi kerak
    assert "bkReaderText" in js_code
    assert 'id="bkReaderText"' in js_code

    # 4. Javonim nishoni har doim DOM da bo'lishi va dinamik yangilanishi kerak
    assert 'id="bkShelfCount"' in js_code

    # 5. Skeleton yuklanish animatsiyasi mavjud bo'lishi kerak
    assert "bk-sk" in css_code
    assert "bkShimmer" in css_code


def test_main_reply_keyboard_has_books():
    """Asosiy reply menyuda '📚 Kitoblar' tugmasi mavjudligini tekshirish."""
    from keyboards.default import main_menu_keyboard
    kb = main_menu_keyboard(is_admin=False)
    button_texts = [btn.text for row in kb.keyboard for btn in row]
    assert "📚 Kitoblar" in button_texts

