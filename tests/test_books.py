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


def test_create_book_epub_sample():
    """Kitob EPUB mutolaa nusxasi generatsiyasini tekshirish."""
    b = book_service.get_book_by_id("1")
    assert b is not None
    epub_bytes = book_service.create_book_epub_sample(b)
    assert isinstance(epub_bytes, bytes)
    assert len(epub_bytes) > 100
    assert epub_bytes.startswith(b"PK")  # ZIP container


@pytest.mark.asyncio
async def test_deliver_book():
    """Kitobni Telegram chatga yetkazishni tekshirish (PDF)."""
    mock_bot = MagicMock()
    mock_bot.send_document = AsyncMock()
    mock_bot.send_message = AsyncMock()

    res = await book_service.deliver_book(
        bot=mock_bot,
        chat_id=123456789,
        book_id="1",
        fmt="pdf"
    )
    assert res["ok"] is True
    assert res["delivered"] is True
    assert mock_bot.send_document.called or mock_bot.send_message.called


@pytest.mark.asyncio
async def test_deliver_book_epub():
    """Kitobni Telegram chatga EPUB formatida yetkazishni tekshirish."""
    mock_bot = MagicMock()
    mock_bot.send_document = AsyncMock()
    mock_bot.send_message = AsyncMock()

    res = await book_service.deliver_book(
        bot=mock_bot,
        chat_id=123456789,
        book_id="1",
        fmt="epub"
    )
    assert res["ok"] is True
    assert res["delivered"] is True
    assert mock_bot.send_document.called
    args, kwargs = mock_bot.send_document.call_args
    doc = kwargs.get("document")
    assert doc is not None
    assert doc.filename.endswith(".epub")


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

    @unittest_run_loop
    async def test_api_catalog_type_book(self):
        """GET /api/catalog?type=book kitoblar katalogini qaytarishi kerak."""
        resp = await self.client.request("GET", "/api/catalog?type=book")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("type") == "book"
        assert "items" in data
        assert len(data["items"]) >= 15

    @unittest_run_loop
    async def test_api_books_home(self):
        """GET /api/books/home to'liq javonlar va toifalar sxemasini qaytarishi kerak."""
        resp = await self.client.request("GET", "/api/books/home")
        assert resp.status == 200
        data = await resp.json()
        assert "shelves" in data
        assert "genres" in data
        assert "collections" in data
        assert "total" in data
        assert data["total"] >= 15
        assert len(data["shelves"]) >= 2
        # featured va top javonlari mavjud bo'lishi kerak
        shelf_keys = [s["k"] for s in data["shelves"]]
        assert "featured" in shelf_keys
        assert "top" in shelf_keys

    @unittest_run_loop
    async def test_api_books_b_id(self):
        """GET /api/books/b/{id} dual-schema formatida kitobni qaytarishi kerak."""
        resp = await self.client.request("GET", "/api/books/b/1")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        book = data["book"]
        assert book["id"] == "1"
        assert book["i"] == 1
        assert "t" in book
        assert "a" in book
        assert "f" in book
        assert "pdf" in book["f"]
        assert "epub" in book["f"]

    @unittest_run_loop
    async def test_api_books_me(self):
        """GET /api/books/me foydalanuvchi ma'lumotlarini qaytarishi kerak."""
        resp = await self.client.request("GET", "/api/books/me")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert "shelf" in data
        assert "stats" in data

    @unittest_run_loop
    async def test_bk_toc_and_chapter_dynamic_generation(self):
        """GET /bk/{id}/toc.json va c1.json dinamik ravishda yaratilishi kerak."""
        resp_toc = await self.client.request("GET", "/bk/1/toc.json")
        assert resp_toc.status == 200
        toc_data = await resp_toc.json()
        assert toc_data.get("ok") is True
        assert "toc" in toc_data
        assert len(toc_data["toc"]) >= 1

        resp_ch = await self.client.request("GET", "/bk/1/c1.json")
        assert resp_ch.status == 200
        ch_data = await resp_ch.json()
        assert "h" in ch_data
        assert "p" in ch_data
        assert len(ch_data["p"]) >= 2


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


def test_webapp_books_tab_attributes():
    """index.html da '📚 Kitoblar' tugmasi data-tab='books' va id='tab-books' ga ega bo'lishini tekshirish."""
    html_path = book_service.BASE_DIR / "webapp" / "index.html"
    content = html_path.read_text(encoding="utf-8")
    assert 'data-tab="books"' in content
    assert 'id="tab-books"' in content
    assert '/#(?:tab-)?(?:books|kitob)/i' in content


@pytest.mark.asyncio
async def test_bot_cmd_books_flow():
    """Telegram bot /books va /kitob buyruqlarini tekshirish."""
    from handlers import books as books_handler
    from aiogram.filters import CommandObject

    # 1. Argumentsiz /books buyrug'i (asosiy menyu)
    msg_main = AsyncMock()
    msg_main.text = "/books"
    msg_main.answer = AsyncMock()
    await books_handler.cmd_books(msg_main, command=CommandObject(prefix="/", command="books", args=None))
    assert msg_main.answer.called
    args, kwargs = msg_main.answer.call_args
    assert "Baunty Kutubxonasi" in args[0]
    assert kwargs.get("reply_markup") is not None

    # 2. Argumentli /books qidiruvi (Alkimyogar)
    msg_search = AsyncMock()
    msg_search.text = "/books Alkimyogar"
    msg_search.answer = AsyncMock()
    await books_handler.cmd_books(msg_search, command=CommandObject(prefix="/", command="books", args="Alkimyogar"))
    assert msg_search.answer.called
    args, kwargs = msg_search.answer.call_args
    assert "Alkimyogar" in args[0]

    # 3. Kirill yozuvidagi /kitob qidiruvi (Ўткан кунлар)
    msg_cyr = AsyncMock()
    msg_cyr.text = "/kitob Ўткан кунлар"
    msg_cyr.answer = AsyncMock()
    await books_handler.cmd_books(msg_cyr, command=CommandObject(prefix="/", command="kitob", args="Ўткан кунлар"))
    assert msg_cyr.answer.called
    args, kwargs = msg_cyr.answer.call_args
    assert "O'tkan kunlar" in args[0]


@pytest.mark.asyncio
async def test_bot_msg_book_search():
    """Foydalanuvchi matnli 'kitob ...' yoki 'китоб ...' yozganda qidiruv ishlashini tekshirish."""
    from handlers import books as books_handler

    # 1. 'kitob Alkimyogar'
    msg_lat = AsyncMock()
    msg_lat.text = "kitob Alkimyogar"
    msg_lat.answer = AsyncMock()
    await books_handler.msg_book_search(msg_lat)
    assert msg_lat.answer.called
    args, kwargs = msg_lat.answer.call_args
    assert "Alkimyogar" in args[0]

    # 2. 'китоб Ўткан кунлар'
    msg_cyr = AsyncMock()
    msg_cyr.text = "китоб Ўткан кунлар"
    msg_cyr.answer = AsyncMock()
    await books_handler.msg_book_search(msg_cyr)
    assert msg_cyr.answer.called
    args, kwargs = msg_cyr.answer.call_args
    assert "O'tkan kunlar" in args[0]


@pytest.mark.asyncio
async def test_bot_callbacks():
    """Bot callback_query tugmalarini tekshirish (main, category, item, read, dl)."""
    from handlers import books as books_handler

    # 1. books:main
    call_main = AsyncMock()
    call_main.data = "books:main"
    call_main.message = AsyncMock()
    call_main.message.edit_text = AsyncMock()
    call_main.answer = AsyncMock()
    await books_handler.cb_books_main(call_main)
    assert call_main.message.edit_text.called
    assert "Baunty Kutubxonasi" in call_main.message.edit_text.call_args[0][0]

    # 2. book:cat:badiiy:1 (1-sahifa)
    call_cat1 = AsyncMock()
    call_cat1.data = "book:cat:badiiy:1"
    call_cat1.message = AsyncMock()
    call_cat1.message.edit_text = AsyncMock()
    call_cat1.answer = AsyncMock()
    await books_handler.cb_books_category(call_cat1)
    assert call_cat1.message.edit_text.called
    assert "Badiiy adabiyot" in call_cat1.message.edit_text.call_args[0][0]

    # 3. book:cat:badiiy:2 (2-sahifa)
    call_cat2 = AsyncMock()
    call_cat2.data = "book:cat:badiiy:2"
    call_cat2.message = AsyncMock()
    call_cat2.message.edit_text = AsyncMock()
    call_cat2.answer = AsyncMock()
    await books_handler.cb_books_category(call_cat2)
    assert call_cat2.message.edit_text.called

    # 4. book:item:1 (kitob kartasi)
    call_item = AsyncMock()
    call_item.data = "book:item:1"
    call_item.message = AsyncMock()
    call_item.message.edit_text = AsyncMock()
    call_item.answer = AsyncMock()
    await books_handler.cb_book_item(call_item)
    assert call_item.message.edit_text.called
    assert "O'tkan kunlar" in call_item.message.edit_text.call_args[0][0]

    # 5. book:read:1 (mutolaa parchasi)
    call_read = AsyncMock()
    call_read.data = "book:read:1"
    call_read.message = AsyncMock()
    call_read.message.edit_text = AsyncMock()
    call_read.answer = AsyncMock()
    await books_handler.cb_book_read(call_read)
    assert call_read.message.edit_text.called
    assert "Mutolaa parchasi" in call_read.message.edit_text.call_args[0][0]

    # 6. book:pdf:1 (PDF yuklab berish)
    call_pdf = AsyncMock()
    call_pdf.data = "book:pdf:1"
    call_pdf.bot = MagicMock()
    call_pdf.bot.send_document = AsyncMock()
    call_pdf.message = AsyncMock()
    call_pdf.message.chat = MagicMock()
    call_pdf.message.chat.id = 123456
    call_pdf.answer = AsyncMock()
    await books_handler.cb_book_download(call_pdf)
    assert call_pdf.bot.send_document.called
    doc_pdf = call_pdf.bot.send_document.call_args[1].get("document")
    assert doc_pdf.filename.endswith(".pdf")

    # 7. book:epub:1 (EPUB yuklab berish)
    call_epub = AsyncMock()
    call_epub.data = "book:epub:1"
    call_epub.bot = MagicMock()
    call_epub.bot.send_document = AsyncMock()
    call_epub.message = AsyncMock()
    call_epub.message.chat = MagicMock()
    call_epub.message.chat.id = 123456
    call_epub.answer = AsyncMock()
    await books_handler.cb_book_download(call_epub)
    assert call_epub.bot.send_document.called
    doc_epub = call_epub.bot.send_document.call_args[1].get("document")
    assert doc_epub.filename.endswith(".epub")


@pytest.mark.asyncio
async def test_start_command_book_deep_links():
    """Start buyrug'i orqali kitob deep linklarini ochish (b_1, book_1, kitob_1, books)."""
    from handlers.start import cmd_start

    # 1. /start b_1
    msg1 = AsyncMock()
    msg1.text = "/start b_1"
    msg1.from_user = MagicMock(id=12345, is_bot=False, username="test", first_name="Test", last_name="")
    msg1.chat.id = 12345
    msg1.bot.send_document = AsyncMock()
    msg1.bot.send_message = AsyncMock()
    state1 = AsyncMock()
    await cmd_start(msg1, state=state1)
    assert msg1.bot.send_document.called or msg1.bot.send_message.called

    # 2. /start kitob_1
    msg2 = AsyncMock()
    msg2.text = "/start kitob_1"
    msg2.from_user = MagicMock(id=12345, is_bot=False, username="test", first_name="Test", last_name="")
    msg2.chat.id = 12345
    msg2.bot.send_document = AsyncMock()
    msg2.bot.send_message = AsyncMock()
    state2 = AsyncMock()
    await cmd_start(msg2, state=state2)
    assert msg2.bot.send_document.called or msg2.bot.send_message.called

    # 3. /start kitob (katalog ochish)
    msg3 = AsyncMock()
    msg3.text = "/start kitob"
    msg3.from_user = MagicMock(id=12345, is_bot=False, username="test", first_name="Test", last_name="")
    msg3.chat.id = 12345
    msg3.answer = AsyncMock()
    state3 = AsyncMock()
    await cmd_start(msg3, state=state3)
    assert msg3.answer.called


@pytest.mark.asyncio
async def test_book_states_search_fsm():
    """Qidiruv tugmasi bosilganda FSM holati va qidiruv xabari qabul qilinishini tekshirish."""
    from handlers import books as books_handler
    from utils.states import BookStates

    state = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()

    call = AsyncMock()
    call.message = AsyncMock()
    call.message.edit_text = AsyncMock()
    call.answer = AsyncMock()

    # Tugma bosilganda
    await books_handler.cb_books_search_prompt(call, state=state)
    state.set_state.assert_called_with(BookStates.waiting_for_query)
    assert call.message.edit_text.called

    # Foydalanuvchi qidiruv yozganda
    msg = AsyncMock()
    msg.text = "Atom odatlar"
    msg.answer = AsyncMock()
    await books_handler.state_process_book_query(msg, state=state)
    state.clear.assert_called()
    assert msg.answer.called


@pytest.mark.asyncio
async def test_cmd_browser_cyrillic_books():
    """Browser komandasi orqali kirillcha kitob so'rovlarini tekshirish."""
    from handlers.movies import cmd_browser

    # 1. /browser @Zakirovs_ai китоб
    msg = AsyncMock()
    msg.text = "/browser @Zakirovs_ai китоб"
    msg.reply = AsyncMock()
    msg.bot.send_document = AsyncMock()
    msg.bot.send_message = AsyncMock()
    await cmd_browser(msg)
    assert msg.reply.called
    assert "Kutubxonasi" in msg.reply.call_args[0][0]

    # 2. /browser @Zakirovs_ai китоб уткан кунлар
    from unittest.mock import patch
    msg2 = AsyncMock()
    msg2.text = "/browser @Zakirovs_ai китоб уткан кунlar".replace("lar", "лар")
    msg2.chat = MagicMock(id=12345)
    msg2.reply = AsyncMock()
    msg2.bot = AsyncMock()
    with patch.object(book_service, "deliver_book", new_callable=AsyncMock) as mock_book_deliv:
        mock_book_deliv.return_value = {"ok": True, "delivered": True}
        await cmd_browser(msg2)
        mock_book_deliv.assert_called_once()
        assert mock_book_deliv.call_args[1].get("book_id") == "1"


@pytest.mark.asyncio
async def test_deliver_book_escaping_and_entities():
    """HTML belgilari (&, <, >) bo'lgan kitoblar xavfsiz va xatosiz uzatilishini tekshirish."""
    mock_bot = MagicMock()
    mock_bot.send_document = AsyncMock()

    fake_book = {
        "id": "99988",
        "title": "Biznes & Moliya <Asoslari>",
        "author": "Muallif & Hammuallif",
        "category": "biznes",
        "category_name": "Biznes & Moliya",
        "pages": 150,
        "rating": 5.0,
        "description": "Test tavsifi & <izoh>",
        "sample_text": "Mutolaa & sinov.",
    }
    book_service._BOOKS_BY_ID["99988"] = fake_book

    res = await book_service.deliver_book(
        bot=mock_bot,
        chat_id=123,
        book_id="99988",
        fmt="pdf"
    )
    assert res["ok"] is True
    assert mock_bot.send_document.called
    kwargs = mock_bot.send_document.call_args[1]
    caption = kwargs.get("caption", "")
    assert "&amp;" in caption
    assert "&lt;" in caption
    assert "&gt;" in caption
    assert "<Asoslari>" not in caption

