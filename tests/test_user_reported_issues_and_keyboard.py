"""
Tests for user reported issues:
1. Keyboard buttons cleanup: mafia, tvroom, rasxod, and kaloriya removed from default keyboard layout.
2. Movie code extraction in groups: support /kino, /kod, @Bauntyfilmsbot mentions, and plain numbers.
3. Subscription bypass in groups: group messages never blocked by mandatory channel subscription.
4. Anonymous questions: safe HTML escaping, bidirectional conversation reply buttons, and deep link.
5. Feedback responsiveness: async non-blocking admin notification.
6. WebApp Language switcher: button in header, toggle logic.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, Chat, User as TgUser, CallbackQuery
from keyboards.default import main_menu_keyboard, DEFAULT_BUTTONS
from handlers.movies import extract_movie_code_and_part, extract_movie_code
from middlewares.subscription import SubscriptionMiddleware
from handlers.anon_questions import state_process_anon_message, state_process_anon_reply
from handlers.feedback import state_process_feedback
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from pathlib import Path


def test_main_menu_keyboard_removes_unwanted_buttons():
    """Verify mafia, tvroom, rasxod, and kaloriya are removed from main_menu_keyboard in all languages."""
    for lang in ("uz", "oz", "ru"):
        kb = main_menu_keyboard(is_admin=False, lang=lang)
        all_buttons = [btn.text for row in kb.keyboard for btn in row]
        t = DEFAULT_BUTTONS[lang]

        # These 4 buttons MUST NOT be in the keyboard:
        assert t["mafia"] not in all_buttons, f"{t['mafia']} should be removed"
        assert t["tvroom"] not in all_buttons, f"{t['tvroom']} should be removed"
        assert t["rasxod"] not in all_buttons, f"{t['rasxod']} should be removed"
        assert t["kaloriya"] not in all_buttons, f"{t['kaloriya']} should be removed"

        # The rest of the buttons MUST be preserved:
        assert t["kino_search"] in all_buttons
        assert t["kino"] in all_buttons
        assert t["music"] in all_buttons
        assert t["books"] in all_buttons
        assert t["media"] in all_buttons
        assert t["story"] in all_buttons
        assert t["docs"] in all_buttons
        assert t["round_video"] in all_buttons
        assert t["anon"] in all_buttons
        assert t["referral"] in all_buttons
        assert t["groups"] in all_buttons
        assert t["feedback"] in all_buttons
        assert t["lang"] in all_buttons


def test_movie_code_extraction_for_groups():
    """Test group movie lookups with various prefixes, mentions, and commands."""
    # Plain numbers
    assert extract_movie_code_and_part("101") == ("101", 1)
    assert extract_movie_code_and_part("101 2") == ("101", 2)
    assert extract_movie_code_and_part("101 3-qism") == ("101", 3)

    # Commands with args
    assert extract_movie_code_and_part("/kino 101") == ("101", 1)
    assert extract_movie_code_and_part("/kod 101") == ("101", 1)
    assert extract_movie_code_and_part("/film 101") == ("101", 1)
    assert extract_movie_code_and_part("/movie 101 2") == ("101", 2)

    # Commands with bot username in supergroups
    assert extract_movie_code_and_part("/kino@Bauntyfilmsbot 101") == ("101", 1)
    assert extract_movie_code_and_part("/kod@Bauntyfilmsbot 101 2") == ("101", 2)

    # Mentions in groups
    assert extract_movie_code_and_part("@Bauntyfilmsbot 101") == ("101", 1)
    assert extract_movie_code_and_part("@Bauntyfilmsbot kino 101") == ("101", 1)
    assert extract_movie_code_and_part("@Bauntyfilmsbot /kino 101") == ("101", 1)
    assert extract_movie_code_and_part("@Bauntyfilmsbot kod 101") == ("101", 1)

    # extract_movie_code standalone
    assert extract_movie_code("/kino 101") == "101"
    assert extract_movie_code("/kod 101") == "101"
    assert extract_movie_code("@Bauntyfilmsbot 101") == "101"


@pytest.mark.asyncio
async def test_subscription_middleware_group_bypass():
    """Verify that SubscriptionMiddleware does not check channels in groups."""
    middleware = SubscriptionMiddleware()
    handler = AsyncMock(return_value="handled")

    # Group message: should pass directly without checking channels
    group_chat = Chat(id=-1001234567890, type="supergroup", title="Test Group")
    user = TgUser(id=999999, is_bot=False, first_name="Ali")
    event = MagicMock(spec=Message)
    event.chat = group_chat
    event.text = "101"

    data = {
        "event_from_user": user,
        "bot": AsyncMock()
    }

    result = await middleware(handler, event, data)
    assert result == "handled"
    assert handler.called


@pytest.mark.asyncio
async def test_anon_question_html_safety_and_reply():
    """Verify that anonymous messages with HTML chars (<3, &, >) are escaped and sent safely."""
    bot_mock = AsyncMock()
    user = TgUser(id=1111, is_bot=False, first_name="Sender")
    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.text = "Salom <3 qandaysiz & nima gaplar?"
    msg.caption = None
    msg.bot = bot_mock
    msg.reply = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=MagicMock())
    await state.update_data(anon_target_id=2222)

    with patch("handlers.anon_questions.crud.create_anonymous_message", new_callable=AsyncMock):
        await state_process_anon_message(msg, state)

    assert bot_mock.send_message.called
    call_args = bot_mock.send_message.call_args[1]
    assert call_args["chat_id"] == 2222
    assert "&lt;3" in call_args["text"]
    assert "&amp;" in call_args["text"]
    assert "<3" not in call_args["text"]  # Unescaped tag must NOT be present in HTML parse mode
    assert msg.reply.called


@pytest.mark.asyncio
async def test_feedback_instant_response():
    """Verify that feedback replies to the user immediately and does not hang on admin sending."""
    bot_mock = AsyncMock()
    user = TgUser(id=3333, is_bot=False, first_name="Tester", username="tester")
    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.text = "Bot juda tez ishlamoqda, rahmat!"
    msg.caption = None
    msg.photo = None
    msg.document = None
    msg.video = None
    msg.bot = bot_mock
    msg.reply = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=MagicMock())

    with patch("handlers.feedback.crud.create_feedback", new_callable=AsyncMock):
        await state_process_feedback(msg, state)

    # User got immediate confirmation
    assert msg.reply.called
    reply_text = msg.reply.call_args[0][0]
    assert "tashakkur" in reply_text.lower()


def test_webapp_language_switcher_markup():
    """Verify that index.html and app.js contain the header language switcher."""
    base_dir = Path(__file__).resolve().parent.parent
    index_html = (base_dir / "webapp" / "index.html").read_text(encoding="utf-8")
    app_js = (base_dir / "webapp" / "app.js").read_text(encoding="utf-8")

    # In index.html:
    assert 'id="zkLangBtn"' in index_html
    assert 'id="zkLangText"' in index_html
    assert '.zk-lang-btn' in index_html

    # In app.js:
    assert 'zkLangBtn' in app_js
    assert 'zkLangText' in app_js
    assert 'ZK_setLang' in app_js
