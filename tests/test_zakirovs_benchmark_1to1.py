"""
Test suite verifying 1-to-1 replication of upstream movie bot benchmark:
- Main start message & keyboard layout with search instructions by code or title
- Direct /start <code> deep linking (e.g. /start 101, /start 718, /start 718_2, /start #101)
- Movie search by direct numeric code, command, and title
- Delivery card formatting: Title, Original name, Year, Genre, Country, Quality, Description, and Bauntys branding
- Movie inline buttons: Parts navigation, streaming, download options, WebApp streaming, and channel links
- Group movie lookups (commands, mentions, and numeric codes)
- Strict Bauntys branding enforcement (no external handles)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, Chat, User as TgUser, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from config import config
from database.session import init_db, get_session
from database import crud
from services.movie_service import movie_service, MovieService
from handlers.start import cmd_start
from handlers.movies import (
    cmd_movies_menu,
    extract_movie_code_and_part,
    extract_movie_code,
)
from keyboards.default import main_menu_keyboard
from keyboards.inline import (
    movie_menu_keyboard,
    movie_item_keyboard,
    movie_parts_keyboard,
)


@pytest.mark.asyncio
async def test_start_message_and_instructions_branding():
    """Start xabarida kod yoki nom bo'yicha qidirish ko'rsatmasi va Baunty Cinema brendi mavjudligi."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=778899, user_id=778899)
    state = FSMContext(storage=storage, key=key)

    msg = AsyncMock(spec=Message)
    msg.from_user = TgUser(id=778899, is_bot=False, first_name="Biloliddin")
    msg.text = "/start"
    msg.answer = AsyncMock()

    await cmd_start(msg, state)

    assert msg.answer.called
    sent_text = msg.answer.call_args[0][0]

    # Ko'rsatmalar
    assert "Baunty Cinema" in sent_text
    assert "Kod orqali" in sent_text
    assert "Nomi bo'yicha" in sent_text
    assert "Serial qismlari" in sent_text
    assert config.CHANNEL_USERNAME in sent_text
    assert "Zakirov" not in sent_text
    assert "dilbarzakirova" not in sent_text


@pytest.mark.asyncio
async def test_start_direct_code_deep_linking():
    """/start 101, /start 718_2, /start #101 orqali to'g'ridan-to'g'ri kinoni yetkazish testi."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=778899, user_id=778899)
    state = FSMContext(storage=storage, key=key)

    # 1. /start 718 (Taksi)
    msg_code = AsyncMock(spec=Message)
    msg_code.from_user = TgUser(id=778899, is_bot=False, first_name="Ali")
    msg_code.text = "/start 718"
    msg_code.bot = AsyncMock()
    msg_code.chat = MagicMock(id=778899)
    msg_code.message_id = 111

    with patch.object(movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = True
        await cmd_start(msg_code, state)
        mock_deliv.assert_called_once()
        _, kwargs = mock_deliv.call_args
        assert kwargs.get("code") == "718"
        assert kwargs.get("part") == 1

    # 2. /start 718_2 (Taksi 2-qism)
    msg_part = AsyncMock(spec=Message)
    msg_part.from_user = TgUser(id=778899, is_bot=False, first_name="Ali")
    msg_part.text = "/start 718_2"
    msg_part.bot = AsyncMock()
    msg_part.chat = MagicMock(id=778899)
    msg_part.message_id = 112

    with patch.object(movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = True
        await cmd_start(msg_part, state)
        mock_deliv.assert_called_once()
        _, kwargs = mock_deliv.call_args
        assert kwargs.get("code") == "718"
        assert kwargs.get("part") == 2

    # 3. /start #101
    msg_hash = AsyncMock(spec=Message)
    msg_hash.from_user = TgUser(id=778899, is_bot=False, first_name="Ali")
    msg_hash.text = "/start #101"
    msg_hash.bot = AsyncMock()
    msg_hash.chat = MagicMock(id=778899)
    msg_hash.message_id = 113

    with patch.object(movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = True
        await cmd_start(msg_hash, state)
        mock_deliv.assert_called_once()
        _, kwargs = mock_deliv.call_args
        assert kwargs.get("code") == "101"
        assert kwargs.get("part") == 1


def test_movie_delivery_keyboards_have_all_options():
    """Movie post inline klaviaturalarida barcha tugmalar (qismlar, yuklash, streaming, kanal) mavjudligi."""
    # 1. Bitta qismli kino klaviaturasi
    kb_single = movie_item_keyboard("101")
    all_buttons_single = [btn.text for row in kb_single.inline_keyboard for btn in row]
    callbacks_single = [btn.callback_data for row in kb_single.inline_keyboard for btn in row if btn.callback_data]
    urls_single = [btn.url for row in kb_single.inline_keyboard for btn in row if btn.url]

    assert any("Kinoni tomosha qilish" in t for t in all_buttons_single)
    assert any("Yuklab olish" in t for t in all_buttons_single)
    assert "download_movie:101:1" in callbacks_single
    assert any("Do'stlarga ulashish" in t for t in all_buttons_single)
    assert any(config.CHANNEL_USERNAME in t for t in all_buttons_single)

    # 2. Ko'p qismli serial klaviaturasi
    kb_parts = movie_parts_keyboard("718", total_parts=5, current_part=1)
    all_buttons_parts = [btn.text for row in kb_parts.inline_keyboard for btn in row]
    callbacks_parts = [btn.callback_data for row in kb_parts.inline_keyboard for btn in row if btn.callback_data]

    # Qismlar navigatsiyasi
    assert "▶️ 1" in all_buttons_parts
    assert "2" in all_buttons_parts
    assert "5" in all_buttons_parts
    assert "watch_part:718:2" in callbacks_parts

    # Yuklab olish tugmasi
    assert any("Yuklab olish" in t for t in all_buttons_parts)
    assert "download_movie:718:1" in callbacks_parts


@pytest.mark.asyncio
async def test_movie_card_formatting_structure(tmp_path, monkeypatch):
    """Movie post delivery card: Title, Original name, Year, Genre, Country, Quality, Description va Bauntys brendi."""
    bot_mock = AsyncMock()
    mock_sent = MagicMock()
    mock_sent.video = MagicMock(file_id="BAACAgIAAxkBAAE_SAMPLE_REAL_PERSISTED_CARD_FID", duration=120, file_size=15000000)
    mock_sent.document = None
    bot_mock.send_video = AsyncMock(return_value=mock_sent)

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=12345, user_id=12345)
    state = FSMContext(storage=storage, key=key)

    # 718 (Taksi) kinoni yetkazish
    res = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=12345,
        code="718",
        part=1
    )
    assert res is True
    assert bot_mock.send_video.called
    call_args = bot_mock.send_video.call_args[1]
    caption = call_args["caption"]

    # Format elementlari tekshiruvi: Title, Original name, Year, Genre, Country, Quality, Description
    assert "Taksi" in caption
    assert "Original nomi:" in caption
    assert "Taxi" in caption
    assert "Janr:" in caption or "Janri:" in caption
    assert "Komediya" in caption
    assert "Davlat:" in caption
    assert "Fransiya" in caption
    assert "Sifati:" in caption
    assert "Yil:" in caption or "Yili:" in caption
    assert "1998" in caption
    assert "@BauntyCinemabot" in caption
    assert "@BauntyFilms" in caption
    assert "Zakirov" not in caption
    assert "dilbarzakirova" not in caption


@pytest.mark.asyncio
async def test_group_movie_lookup_reply():
    """Guruhlarda /kino 101, @bot 101, yoki oddiy 101 yuborilganda kinoni reply qilib yetkazishi testi."""
    group_chat = Chat(id=-100987654321, type="supergroup", title="Kinochilar Guruhi")
    user = TgUser(id=556677, is_bot=False, first_name="Doston")

    # 1. /kino 718 buyrug'i
    msg_cmd = AsyncMock(spec=Message)
    msg_cmd.chat = group_chat
    msg_cmd.from_user = user
    msg_cmd.text = "/kino 718"
    msg_cmd.message_id = 991
    msg_cmd.bot = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=group_chat.id, user_id=user.id))

    from aiogram.filters import CommandObject
    cmd_obj = CommandObject(prefix="/", command="kino", args="718")

    with patch.object(movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = True
        await cmd_movies_menu(msg_cmd, state, command=cmd_obj)
        mock_deliv.assert_called_once()
        _, kwargs = mock_deliv.call_args
        assert kwargs.get("code") == "718"
        assert kwargs.get("part") == 1
        assert kwargs.get("reply_to_message_id") == 991


@pytest.mark.asyncio
async def test_top_and_random_movies_catalog_fallback():
    """Baza bo'sh bo'lganda ham Top kinolar va Tasodifiy kino katalogdan uzluksiz ishlashi testi."""
    from handlers.movies import cb_movie_top, cb_movie_random

    # 1. cb_movie_top
    cb_top = AsyncMock(spec=CallbackQuery)
    cb_top.answer = AsyncMock()
    cb_top.message = AsyncMock()
    cb_top.message.answer = AsyncMock()

    with patch.object(movie_service, "get_top", new_callable=AsyncMock, return_value=[]):
        await cb_movie_top(cb_top)
        assert cb_top.message.answer.called
        sent_text = cb_top.message.answer.call_args[0][0]
        assert "Eng ommabop va ko'p ko'rilgan kinolar" in sent_text

    # 2. cb_movie_random
    cb_rnd = AsyncMock(spec=CallbackQuery)
    cb_rnd.bot = AsyncMock()
    cb_rnd.answer = AsyncMock()
    cb_rnd.message = AsyncMock()
    cb_rnd.message.chat = MagicMock(id=889900)
    cb_rnd.message.answer = AsyncMock()

    with patch.object(movie_service, "get_random", new_callable=AsyncMock, return_value=None), \
         patch.object(movie_service, "deliver_movie", new_callable=AsyncMock, return_value=True) as mock_deliv:
        await cb_movie_random(cb_rnd)
        assert mock_deliv.called
        _, kwargs = mock_deliv.call_args
        assert kwargs.get("chat_id") == 889900
        assert kwargs.get("code") is not None

