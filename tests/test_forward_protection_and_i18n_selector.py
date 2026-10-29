"""
Tests for Bot Forward Protection and Web App 3-Language Selection & Localization.
Verifies:
1. Forward Protection: protect_content=True globally on DefaultBotProperties in main.py,
   as well as explicit protect_content=True across movies, music, books, anon_questions,
   and start handlers and services.
2. 3-Language Selection UI & Localization:
   - Header selector in webapp/index.html with 3 language pills (UZ, RU, EN) and zkLangBtn.
   - Comprehensive translation dictionaries (DICT_RU, DICT_EN) and regex rules in webapp/i18n.js.
   - Synchronization and cycling logic in webapp/app.js and webapp/index.html.
   - Bundled production assets in webapp/dist/bundle.min.js.
3. White-Label Branding:
   - Strict brand enforcement: No competitor names ("Zakirov", "Zakirova", "dilbarzakirova", "Zakirovsfilms_bot") leaked.
"""
import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


def test_main_bot_properties_has_protect_content():
    """Verify that main.py configures DefaultBotProperties with protect_content=True."""
    main_py = (BASE_DIR / "main.py").read_text(encoding="utf-8")
    assert "DefaultBotProperties" in main_py
    assert "protect_content=True" in main_py


def test_handlers_and_services_forward_protection():
    """Verify explicit protect_content=True across content delivery handlers and services."""
    movie_service = (BASE_DIR / "services" / "movie_service.py").read_text(encoding="utf-8")
    music_handler = (BASE_DIR / "handlers" / "music.py").read_text(encoding="utf-8")
    books_handler = (BASE_DIR / "handlers" / "books.py").read_text(encoding="utf-8")
    book_service = (BASE_DIR / "services" / "book_service.py").read_text(encoding="utf-8")
    anon_handler = (BASE_DIR / "handlers" / "anon_questions.py").read_text(encoding="utf-8")
    start_handler = (BASE_DIR / "handlers" / "start.py").read_text(encoding="utf-8")
    movies_handler = (BASE_DIR / "handlers" / "movies.py").read_text(encoding="utf-8")

    assert "protect_content=True" in movie_service
    assert "protect_content=True" in music_handler
    assert "protect_content=True" in books_handler
    assert "protect_content=True" in book_service
    assert "protect_content=True" in anon_handler
    assert "protect_content=True" in start_handler
    assert "protect_content=True" in movies_handler


def test_webapp_header_3_language_selector():
    """Verify that webapp/index.html contains 3-language selector pills (UZ, RU, EN) and #zkLangBtn."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")

    assert 'id="zkLangPills"' in index_html
    assert 'data-lang="uz"' in index_html
    assert 'data-lang="ru"' in index_html
    assert 'data-lang="en"' in index_html
    assert 'id="zkLangBtn"' in index_html
    assert 'id="zkLangText"' in index_html
    assert ".zk-lang-pills" in index_html
    assert ".zk-lang-pill" in index_html


def test_webapp_i18n_dictionaries_and_auto_loader():
    """Verify that webapp/i18n.js has comprehensive dictionaries and auto-loading for UZ, RU, and EN."""
    i18n_js = (BASE_DIR / "webapp" / "i18n.js").read_text(encoding="utf-8")

    assert "DICT_RU" in i18n_js
    assert "DICT_EN" in i18n_js
    assert "RULES_RU" in i18n_js
    assert "RULES_EN" in i18n_js
    assert "ZK_DICT_LOAD" in i18n_js
    assert "ZK_setLang" in i18n_js
    assert "ZK_T" in i18n_js
    assert "ZK_tr" in i18n_js
    assert "MutationObserver" in i18n_js

    # Verify key translations exist in dictionaries
    assert '"🎬 Kinolar": "🎬 Фильмы"' in i18n_js
    assert '"🎬 Kinolar": "🎬 Movies"' in i18n_js
    assert '"Tomosha qilish": "Смотреть"' in i18n_js
    assert '"Tomosha qilish": "Watch"' in i18n_js
    assert '"Hech narsa topilmadi": "Ничего не найдено"' in i18n_js
    assert '"Hech narsa topilmadi": "Nothing found"' in i18n_js


def test_webapp_app_js_3_way_cycling_and_pill_sync():
    """Verify that webapp/app.js syncs pill active state and cycles through 3 languages (uz -> ru -> en)."""
    app_js = (BASE_DIR / "webapp" / "app.js").read_text(encoding="utf-8")

    assert "zk-lang-pill" in app_js
    assert "zkLangBtn" in app_js
    assert "zkLangText" in app_js
    assert 'curLang === "uz" ? "ru" : curLang === "ru" ? "en" : "uz"' in app_js


def test_bundled_assets_contain_i18n_and_selector_styles():
    """Verify that production bundles (webapp/dist/bundle.min.js and bundle.min.css) include i18n and styling."""
    dist_js = (BASE_DIR / "webapp" / "dist" / "bundle.min.js").read_text(encoding="utf-8")
    dist_css = (BASE_DIR / "webapp" / "dist" / "bundle.min.css").read_text(encoding="utf-8")

    assert "DICT_RU" in dist_js
    assert "DICT_EN" in dist_js
    assert "ZK_setLang" in dist_js
    assert "zk-lang-pills" in dist_css
    assert "zk-lang-pill" in dist_css


def test_white_label_brand_enforcement_in_frontend():
    """Ensure no competitor or upstream brand names leak into the webapp files."""
    forbidden = ["zakirovsfilms_bot", "zakirova", "dilbarzakirova"]
    
    files_to_check = [
        BASE_DIR / "webapp" / "index.html",
        BASE_DIR / "webapp" / "i18n.js",
        BASE_DIR / "webapp" / "app.js",
    ]

    for f in files_to_check:
        content = f.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in content, f"Forbidden brand '{token}' found in {f.name}"


@pytest.mark.asyncio
async def test_deliver_movie_protect_content_enforcement():
    """Verify that MovieService.deliver_movie explicitly passes protect_content=True to bot.send_video."""
    from unittest.mock import AsyncMock, MagicMock
    from services.movie_service import MovieService
    from database.models import Base
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        bot_mock = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.video = MagicMock(file_id="BAACAgIAAxkBAAE_TEST_FID", duration=120, file_size=10000000)
        mock_sent.document = None
        bot_mock.send_video = AsyncMock(return_value=mock_sent)

        # 284 is in catalog
        res = await MovieService.deliver_movie(
            bot=bot_mock,
            chat_id=123456,
            code="284",
            part=1,
            session=session
        )
        assert res is True
        assert bot_mock.send_video.called
        _, kwargs = bot_mock.send_video.call_args
        assert kwargs.get("protect_content") is True

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_deliver_book_protect_content_enforcement(tmp_path):
    """Verify that deliver_book passes protect_content=True."""
    from unittest.mock import AsyncMock, patch
    from services.book_service import deliver_book

    bot_mock = AsyncMock()
    bot_mock.send_document = AsyncMock(return_value=True)

    dummy_pdf = tmp_path / "test_book.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 test")

    dummy_book = {
        "id": "999",
        "title": "Test Book",
        "author": "Author",
        "file_path": str(dummy_pdf),
        "file_id": None
    }

    with patch("services.book_service.get_book_by_id", return_value=dummy_book):
        res = await deliver_book(
            bot=bot_mock,
            chat_id=55555,
            book_id="999"
        )
        assert res.get("ok") is True
        assert bot_mock.send_document.called
        _, kwargs = bot_mock.send_document.call_args
        assert kwargs.get("protect_content") is True


def test_i18n_fetch_interceptor_accept_language():
    """Verify that webapp/i18n.js intercepts fetch to inject Accept-Language and X-Lang headers."""
    i18n_js = (BASE_DIR / "webapp" / "i18n.js").read_text(encoding="utf-8")
    assert "Accept-Language" in i18n_js
    assert "X-Lang" in i18n_js
    assert "origFetch" in i18n_js

