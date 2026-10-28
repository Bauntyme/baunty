"""Tests for Anti-Ban, Anti-DMCA and Token Migration to @BauntyCinemabot."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from config import config
from keyboards.inline import movie_item_keyboard, movie_parts_keyboard
from utils.helpers import format_movie_caption
from database.models import Movie
from handlers.start import cmd_start, cmd_help
from services.movie_service import MovieService


def test_token_and_username_configuration():
    assert config.BOT_TOKEN == "9047244772:AAHevPLbK9Uz_NQ0AtcemQqpA0C5OgXtkgw"
    assert config.BOT_USERNAME.lstrip("@") == "BauntyCinemabot"


def test_movie_item_keyboard_webapp_primary_button():
    kb = movie_item_keyboard(
        movie_code="101",
        watch_url="https://asilmedia.org/watch/101",
        download_url="https://asilmedia.org/download/101"
    )
    # First row must be the primary WebApp button
    assert len(kb.inline_keyboard) >= 1
    first_btn = kb.inline_keyboard[0][0]
    assert "▶️ Onlayn tomosha qilish" in first_btn.text
    assert first_btn.web_app is not None
    assert "c=101" in first_btn.web_app.url

    # Second row must have the watch_part callback button
    second_btn = kb.inline_keyboard[1][0]
    assert second_btn.callback_data == "watch_part:101:1"


def test_movie_caption_indexer_disclaimer():
    movie = Movie(
        code="101",
        title="Test Movie",
        genres="Action",
        year=2024,
        rating=8.0,
        views_count=10,
        description="A great test movie"
    )
    caption = format_movie_caption(movie)
    disclaimer = "ℹ️ Ushbu bot qidiruv indeksi sifatida ishlaydi. Fayllar Telegram serverlarida saqlanmaydi."
    assert disclaimer in caption


@pytest.mark.asyncio
async def test_welcome_and_help_disclaimers():
    disclaimer = "ℹ️ Ushbu bot qidiruv indeksi sifatida ishlaydi. Fayllar Telegram serverlarida saqlanmaydi."

    msg_start = AsyncMock()
    msg_start.text = "/start"
    msg_start.from_user = MagicMock(id=12345, first_name="User", last_name=None, username="tester")
    state_mock = AsyncMock()
    state_mock.get_data.return_value = {}

    await cmd_start(msg_start, state_mock)
    assert msg_start.answer.called
    start_text = msg_start.answer.call_args[0][0]
    assert disclaimer in start_text

    msg_help = AsyncMock()
    msg_help.text = "/help"
    await cmd_help(msg_help)
    assert msg_help.answer.called
    help_text = msg_help.answer.call_args[0][0]
    assert disclaimer in help_text


@pytest.mark.asyncio
async def test_movie_delivery_protect_content():
    """Verify _deliver_movie_impl invokes send_video or send_document with protect_content=True."""
    from unittest.mock import patch
    bot = AsyncMock()
    session = AsyncMock()

    mock_movie = MagicMock(
        id=1,
        code="101",
        title="Forsaj 10",
        file_id="BAACAgIAAxkBAAE1234567890abcdefghijklmnopqrstuvwxyz",
        file_type="video",
        duration=7200,
        genres="Action",
        year=2023,
        rating=7.5,
        views_count=50,
        description="Dom Toretto"
    )

    with patch("database.crud.get_movie_by_code", return_value=mock_movie), \
         patch("database.crud.get_movie_file", return_value=None), \
         patch("database.crud.increment_movie_views", return_value=True):
        success = await MovieService._deliver_movie_impl(
            bot=bot,
            chat_id=12345,
            code="101",
            part=1,
            session=session
        )
        assert success is True
        assert bot.send_video.called
        call_kwargs = bot.send_video.call_args[1]
        assert call_kwargs.get("protect_content") is True
        assert "ℹ️ Ushbu bot qidiruv indeksi sifatida ishlaydi. Fayllar Telegram serverlarida saqlanmaydi." in call_kwargs.get("caption")


@pytest.mark.asyncio
async def test_movie_service_source_protect_content_and_disclaimer():
    """Verify source code of movie_service has protect_content=True on all delivery calls."""
    with open("services/movie_service.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Disclaimer check
    assert "ℹ️ Ushbu bot qidiruv indeksi sifatida ishlaydi. Fayllar Telegram serverlarida saqlanmaydi." in content
    # protect_content=True check
    assert content.count("protect_content=True") >= 6


def test_sanitize_branding_legacy_bot_migration():
    """Verify legacy @Bauntyfilmsbot is sanitized to @BauntyCinemabot."""
    from services.web_server import sanitize_catalog_text
    raw = "Tomosha qilish: @Bauntyfilmsbot yoki https://t.me/Bauntyfilmsbot?start=101"
    clean_ms = MovieService.sanitize_branding(raw)
    assert "@BauntyCinemabot" in clean_ms
    assert "@Bauntyfilmsbot" not in clean_ms
    assert "t.me/BauntyCinemabot" in clean_ms

    clean_ws = sanitize_catalog_text(raw)
    assert "@BauntyCinemabot" in clean_ws
    assert "@Bauntyfilmsbot" not in clean_ws


def test_catalog_json_migration_and_preservation():
    """Verify data/catalog.json has zero legacy bot references and all movies preserved."""
    import json
    from pathlib import Path
    cat_path = Path("data/catalog.json")
    assert cat_path.exists()
    content = cat_path.read_text(encoding="utf-8")
    assert "Bauntyfilmsbot" not in content
    data = json.loads(content)
    assert isinstance(data, dict) and "items" in data
    assert len(data["items"]) >= 700


def test_webapp_source_files_no_legacy_bot():
    """Verify webapp JS/HTML sources use BauntyCinemabot instead of dead Bauntyfilmsbot."""
    files_to_check = [
        "webapp/index.html",
        "webapp/js/app.js",
        "webapp/mafia.js",
        "webapp/tvroom.js",
        "webapp/quiz.js",
        "webapp/admin_flow.html"
    ]
    for rel_path in files_to_check:
        with open(rel_path, "r", encoding="utf-8") as f:
            text = f.read()
        assert "Bauntyfilmsbot" not in text, f"Legacy bot found in {rel_path}"


def test_movie_parts_keyboard_clean_no_duplicate_webapp():
    """Verify movie_parts_keyboard has web_app button and no redundant bottom button."""
    kb = movie_parts_keyboard(
        movie_code="289",
        total_parts=5,
        current_part=2
    )
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    webapp_btns = [btn for btn in buttons if btn.web_app is not None]
    # Should only have 1 WebApp button (for the selected part)
    assert len(webapp_btns) == 1
    assert "c=289" in webapp_btns[0].web_app.url
    assert "part=2" in webapp_btns[0].web_app.url

