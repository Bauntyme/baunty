"""
Test suite verifying the @Zakirovs_ai bridge in /browser:
- Unified Kinolar (Movies) and Kitoblar (Books) integration
- /browser @Zakirovs_ai main portal menu with both WebApps and quick actions
- /browser @Zakirovs_ai kitoblar category and catalog lookup
- /browser @Zakirovs_ai <code/part> direct movie delivery
- /browser @Zakirovs_ai <book title> direct book delivery and multi-book lookup
- Combined movie + book search results
- Strict Bauntys branding enforcement and forward protection (protect_content=True)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, Chat, User as TgUser, InlineKeyboardMarkup, CallbackQuery
from config import config
from handlers.movies import cmd_browser
from services.movie_service import movie_service
from services import book_service


def _create_mock_msg(text: str) -> AsyncMock:
    msg = AsyncMock()
    msg.text = text
    msg.from_user = TgUser(id=112233, is_bot=False, first_name="Bilol")
    msg.chat = MagicMock(id=112233)
    msg.message_id = 789
    msg.bot = AsyncMock()
    msg.reply = AsyncMock()
    return msg


@pytest.mark.asyncio
async def test_cmd_browser_zakirovs_ai_main_portal():
    """/browser @Zakirovs_ai argümensiz portal xabari va ikkala WebApp tugmalari mavjudligi."""
    msg = _create_mock_msg("/browser @Zakirovs_ai")

    await cmd_browser(msg)

    assert msg.reply.called
    reply_args = msg.reply.call_args
    portal_text = reply_args.args[0] if reply_args.args else reply_args.kwargs.get("text", "")
    kwargs = reply_args.kwargs

    # Sarlavha va matn tekshiruvi
    assert "Bauntys — Kinolar va Kitoblar Portali" in portal_text
    assert "@Zakirovs_ai integratsiyasi" in portal_text
    assert "Kinolar Portali" in portal_text
    assert "Kutubxona Portali" in portal_text
    assert config.CHANNEL_USERNAME in portal_text
    assert "dilbarzakirova" not in portal_text

    # Forward protection
    assert kwargs.get("protect_content") is True

    # Klaviaturadagi tugmalar
    kb = kwargs.get("reply_markup")
    assert kb is not None
    all_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Kinolar Web App" in t for t in all_texts)
    assert any("Kitoblar Web App" in t for t in all_texts)
    assert any("Taksi" in t for t in all_texts)
    assert any("Forsaj" in t for t in all_texts)
    assert any("O'tkan kunlar" in t for t in all_texts)
    assert any("Boy ota" in t for t in all_texts)

    # WebApp URL lar tekshiruvi
    all_web_apps = [btn.web_app.url for row in kb.inline_keyboard for btn in row if btn.web_app]
    assert any("?books" in url for url in all_web_apps)


@pytest.mark.asyncio
async def test_cmd_browser_zakirovs_ai_kitob_category():
    """/browser @Zakirovs_ai kitoblar buyrug'i kutubxona menyusini ochishi testi."""
    msg = _create_mock_msg("/browser @Zakirovs_ai kitob")

    await cmd_browser(msg)

    assert msg.reply.called
    reply_args = msg.reply.call_args
    text = reply_args.args[0] if reply_args.args else reply_args.kwargs.get("text", "")
    kwargs = reply_args.kwargs

    assert "Baunty Kutubxonasi" in text
    assert kwargs.get("protect_content") is True


@pytest.mark.asyncio
async def test_cmd_browser_zakirovs_ai_movie_code():
    """/browser @Zakirovs_ai 718_2 buyrug'i filmni to'g'ridan-to'g'ri yetkazishi testi."""
    msg = _create_mock_msg("/browser @Zakirovs_ai 718_2")

    with patch.object(movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = True
        await cmd_browser(msg)
        mock_deliv.assert_called_once()
        _, kwargs = mock_deliv.call_args
        assert kwargs.get("code") == "718"
        assert kwargs.get("part") == 2


@pytest.mark.asyncio
async def test_cmd_browser_zakirovs_ai_book_search_and_delivery():
    """/browser @Zakirovs_ai Otkan kunlar buyrug'i kitobni aniqlab yetkazishi testi."""
    msg = _create_mock_msg("/browser @Zakirovs_ai Otkan kunlar")

    with patch.object(book_service, "deliver_book", new_callable=AsyncMock) as mock_book_deliv:
        mock_book_deliv.return_value = {"ok": True, "delivered": True}
        await cmd_browser(msg)
        mock_book_deliv.assert_called_once()
        _, kwargs = mock_book_deliv.call_args
        assert kwargs.get("book_id") == "1"


@pytest.mark.asyncio
async def test_cmd_browser_zakirovs_ai_multi_book_results():
    """/browser @Zakirovs_ai bir nechta kitob topilganda yuklab olish tugmalarini qaytarishi."""
    msg = _create_mock_msg("/browser @Zakirovs_ai Qodiriy")

    await cmd_browser(msg)

    assert msg.reply.called
    reply_args = msg.reply.call_args
    text = reply_args.args[0] if reply_args.args else reply_args.kwargs.get("text", "")
    kwargs = reply_args.kwargs

    assert "Topilgan kitoblar" in text
    assert kwargs.get("protect_content") is True
    kb = kwargs.get("reply_markup")
    assert kb is not None
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
    assert any(cb and cb.startswith("book:dl:") for cb in callbacks)


@pytest.mark.asyncio
async def test_cmd_browser_zakirovs_ai_not_found():
    """/browser @Zakirovs_ai topilmagan so'rovda to'g'ri yo'naltiruvchi klaviatura qaytarishi."""
    msg = _create_mock_msg("/browser @Zakirovs_ai mavjud_bolmagan_noma_12345")

    await cmd_browser(msg)

    assert msg.reply.called
    reply_args = msg.reply.call_args
    text = reply_args.args[0] if reply_args.args else reply_args.kwargs.get("text", "")
    assert "topilmadi" in text
    kwargs = reply_args.kwargs
    assert kwargs.get("protect_content") is True
