"""
Anonim savollar (@Zakirovsfilms_bot darajasida ?start=q_<token> va barcha boshqaruv oqimlari) testlari.
"""
import io
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, User as TgUser
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import config
from database import crud
from database.models import Base
from handlers.anon_questions import (
    cb_anon_block_sender,
    cb_anon_ig_story_image,
    cb_anon_main_menu,
    cb_anon_regen_cancel,
    cb_anon_regen_confirm,
    cb_anon_regen_execute,
    cb_anon_toggle_accept,
    cb_anon_unblock_sender,
    cmd_anon_questions_link,
    state_process_anon_message,
)
from handlers.start import cmd_start
from services.anon_story_image import generate_anon_story_image
from utils.states import AnonQuestionStates


@pytest_asyncio.fixture
async def db_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def _get_session():
        async with session_maker() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    yield session_maker, _get_session
    await engine.dispose()


@pytest.mark.asyncio
async def test_anon_profile_token_regen_and_block_crud(db_session_factory):
    session_maker, _ = db_session_factory
    async with session_maker() as s:
        await crud.get_or_create_user(s, user_id=1001, username="alice", first_name="Alice")
        await crud.get_or_create_user(s, user_id=2002, username="bob", first_name="Bob")

        # 1. Profile created with 10-char opaque token, not raw user_id
        prof = await crud.get_or_create_anon_profile(s, 1001)
        assert len(prof.token) == 10
        assert prof.token != "1001"
        assert prof.is_accepting is True

        # 2. Token resolves to (1001, True); numeric fallback rejected once profile exists
        assert await crud.resolve_anon_target(s, prof.token) == (1001, True)
        assert await crud.resolve_anon_target(s, "1001") is None

        # 3. Unprofiled legacy user 2002 still resolves safely via numeric fallback
        assert await crud.resolve_anon_target(s, "2002") == (2002, True)

        # 4. Regenerating token invalidates old token immediately
        old_token = prof.token
        prof2 = await crud.regenerate_anon_token(s, 1001)
        assert prof2.token != old_token
        assert len(prof2.token) == 10
        assert await crud.resolve_anon_target(s, old_token) is None
        assert await crud.resolve_anon_target(s, prof2.token) == (1001, True)

        # 5. Pause/resume toggle
        await crud.set_anon_accepting(s, 1001, False)
        assert await crud.resolve_anon_target(s, prof2.token) == (1001, False)
        await crud.set_anon_accepting(s, 1001, True)
        assert await crud.resolve_anon_target(s, prof2.token) == (1001, True)

        # 6. Stats & sender blocking
        await crud.create_anonymous_message(s, sender_id=2002, recipient_id=1001, text="Salom!")
        assert await crud.block_anon_sender(s, recipient_id=1001, sender_id=2002) is True
        assert await crud.block_anon_sender(s, recipient_id=1001, sender_id=2002) is False
        assert await crud.is_anon_sender_blocked(s, recipient_id=1001, sender_id=2002) is True
        recv_cnt, blk_cnt = await crud.get_anon_stats(s, 1001)
        assert recv_cnt == 1
        assert blk_cnt == 1
        assert await crud.unblock_anon_sender(s, recipient_id=1001, sender_id=2002) is True
        assert await crud.get_anon_stats(s, 1001) == (1, 0)


def test_anon_story_image_generation_and_cache():
    t0 = time.perf_counter()
    png_bytes = generate_anon_story_image(config.BOT_USERNAME)
    _ = time.perf_counter() - t0

    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    im = Image.open(io.BytesIO(png_bytes))
    assert im.size == (1080, 1920)

    # Cached reuse must be instantaneous
    t1 = time.perf_counter()
    png_cached = generate_anon_story_image(config.BOT_USERNAME)
    cached_ms = (time.perf_counter() - t1) * 1000.0
    assert png_cached == png_bytes
    assert cached_ms < 5.0


@pytest.mark.asyncio
async def test_anon_card_toggles_regen_story_img_and_menu(db_session_factory):
    _, fake_get_session = db_session_factory
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=MagicMock())

    user = TgUser(id=5050, is_bot=False, first_name="Kamron", username="kamron")
    msg = AsyncMock(spec=Message)
    msg.from_user = user
    msg.chat = Chat(id=5050, type="private")
    msg.text = "💌 Anonim savollar"
    msg.answer = AsyncMock()

    with patch("handlers.anon_questions.get_session", fake_get_session):
        # 1. Main card displays 5 exact rows + token link + stats + active status
        await cmd_anon_questions_link(msg, state)
        assert msg.answer.called
        card_text = msg.answer.call_args.args[0]
        kb = msg.answer.call_args.kwargs["reply_markup"]
        assert "💌 <b>Anonim savollar</b>" in card_text
        assert "?start=q_" in card_text
        assert "?start=q_5050" not in card_text
        assert "📬 Qabul qilingan: <b>0</b>" in card_text
        assert "🚫 Bloklanganlar: <b>0</b>" in card_text
        assert "✅ xabar qabul qilinyapti" in card_text

        row_texts = [row[0].text for row in kb.inline_keyboard]
        assert len(kb.inline_keyboard) == 5
        assert row_texts == [
            "✈️ Telegramda ulashish",
            "📸 Instagram story uchun rasm",
            "⏸ Qabulni to'xtatish",
            "🔄 Havolani yangilash",
            "🏠 Asosiy menyu",
        ]

        # Extract initial link
        import re
        token_match = re.search(r"start=q_([A-Za-z0-9]+)", card_text)
        assert token_match is not None
        token1 = token_match.group(1)

        # 2. Toggle pause -> Holat: ⏸ to'xtatilgan & button becomes ▶️ Qabulni yoqish
        cb_msg = AsyncMock(spec=Message)
        cb_msg.edit_text = AsyncMock()
        cb_msg.answer = AsyncMock()
        cb_msg.answer_photo = AsyncMock()
        cb_msg.answer_document = AsyncMock()
        cb_msg.edit_reply_markup = AsyncMock()

        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = user
        cb.message = cb_msg
        cb.answer = AsyncMock()
        cb.data = "anon:toggle_accept"

        await cb_anon_toggle_accept(cb)
        edited_text = cb_msg.edit_text.call_args.args[0]
        edited_kb = cb_msg.edit_text.call_args.kwargs["reply_markup"]
        assert "⏸ to'xtatilgan" in edited_text
        assert edited_kb.inline_keyboard[2][0].text == "▶️ Qabulni yoqish"
        assert "to'xtatildi" in cb.answer.call_args.args[0]

        # Toggle resume back
        await cb_anon_toggle_accept(cb)
        resumed_text = cb_msg.edit_text.call_args.args[0]
        assert "✅ xabar qabul qilinyapti" in resumed_text

        # 3. Instagram Story image generation & guide (must allow saving: protect_content=False)
        cb.data = "anon:ig_story_img"
        await cb_anon_ig_story_image(cb)
        assert cb_msg.answer_photo.called
        assert cb_msg.answer_document.called
        assert cb_msg.answer_photo.call_args.kwargs["protect_content"] is False
        doc_kwargs = cb_msg.answer_document.call_args.kwargs
        assert doc_kwargs["protect_content"] is False
        assert f"start=q_{token1}" in doc_kwargs["caption"]
        assert "LINK" in doc_kwargs["caption"]

        # 4. Regenerate link confirmation -> cancel -> confirm -> brand new token
        cb.data = "anon:regen_confirm"
        await cb_anon_regen_confirm(cb)
        confirm_kb = cb_msg.edit_text.call_args.kwargs["reply_markup"]
        assert [b.text for row in confirm_kb.inline_keyboard for b in row] == ["✅ Ha, yangilash", "❌ Yo'q"]

        cb.data = "anon:regen_no"
        await cb_anon_regen_cancel(cb)
        assert f"start=q_{token1}" in cb_msg.edit_text.call_args.args[0]

        cb.data = "anon:regen_yes"
        await cb_anon_regen_execute(cb)
        regen_text = cb_msg.edit_text.call_args.args[0]
        token2_match = re.search(r"start=q_([A-Za-z0-9]+)", regen_text)
        assert token2_match is not None
        assert token2_match.group(1) != token1

        # 5. Main menu button
        cb.data = "anon:main_menu"
        await cb_anon_main_menu(cb, state)
        assert "Asosiy menyu" in cb_msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_anon_deep_link_paused_blocked_and_delivery_flow(db_session_factory):
    session_maker, fake_get_session = db_session_factory
    storage = MemoryStorage()

    # Seed recipient (7001) & sender (8002)
    async with session_maker() as s:
        await crud.get_or_create_user(s, user_id=7001, username="recip", first_name="Recipient")
        await crud.get_or_create_user(s, user_id=8002, username="sendr", first_name="Sender")
        prof = await crud.get_or_create_anon_profile(s, 7001)
        token = prof.token
        await s.commit()

    def _make_msg(uid: int, text: str) -> AsyncMock:
        m = AsyncMock(spec=Message)
        m.from_user = TgUser(id=uid, is_bot=False, first_name=f"User{uid}")
        m.chat = Chat(id=uid, type="private")
        m.text = text
        m.caption = None
        m.photo = None
        m.video = None
        m.voice = None
        m.audio = None
        m.document = None
        m.bot = AsyncMock()
        m.answer = AsyncMock()
        m.reply = AsyncMock()
        return m

    with patch("handlers.start.get_session", fake_get_session), \
         patch("handlers.anon_questions.get_session", fake_get_session):

        # 1. Invalid / rotated link
        st_sender = FSMContext(storage=storage, key=MagicMock())
        m_bad = _make_msg(8002, "/start q_INVALID999")
        await cmd_start(m_bad, st_sender)
        assert "eskirgan" in m_bad.answer.call_args.args[0].lower()

        # 2. Self link
        m_self = _make_msg(7001, f"/start q_{token}")
        await cmd_start(m_self, st_sender)
        assert "o'zingizga" in m_self.answer.call_args.args[0].lower()

        # 3. Valid active link puts sender into waiting_for_message
        m_valid = _make_msg(8002, f"/start q_{token}")
        await cmd_start(m_valid, st_sender)
        assert await st_sender.get_state() == AnonQuestionStates.waiting_for_message.state
        assert (await st_sender.get_data())["anon_target_id"] == 7001

        # 4. Sender submits question -> delivered to 7001 with reply & block buttons
        m_q = _make_msg(8002, "Eng yaxshi kino qaysi <3?")
        await state_process_anon_message(m_q, st_sender)
        assert m_q.bot.send_message.called
        sent_kwargs = m_q.bot.send_message.call_args.kwargs
        assert sent_kwargs["chat_id"] == 7001
        assert "&lt;3?" in sent_kwargs["text"]
        assert sent_kwargs["protect_content"] is True
        in_kb = sent_kwargs["reply_markup"]
        in_cbs = [b.callback_data for row in in_kb.inline_keyboard for b in row]
        assert "anon_reply:8002" in in_cbs
        assert "anon:block:8002" in in_cbs

        # 5. Recipient clicks Block -> blocks 8002 -> further /start & messages denied
        cb_blk = AsyncMock(spec=CallbackQuery)
        cb_blk.from_user = TgUser(id=7001, is_bot=False, first_name="Recipient")
        cb_blk.data = "anon:block:8002"
        cb_blk.message = AsyncMock(spec=Message)
        cb_blk.message.edit_reply_markup = AsyncMock()
        cb_blk.answer = AsyncMock()
        await cb_anon_block_sender(cb_blk)
        assert cb_blk.message.edit_reply_markup.call_args.kwargs["reply_markup"].inline_keyboard[0][1].callback_data == "anon:unblock:8002"

        m_blk = _make_msg(8002, f"/start q_{token}")
        await cmd_start(m_blk, st_sender)
        assert "yubora olmaysiz" in m_blk.answer.call_args.args[0].lower()

        # Unblock 8002
        cb_blk.data = "anon:unblock:8002"
        await cb_anon_unblock_sender(cb_blk)

        # 6. Recipient pauses accepting -> /start q_<token> rejected with paused notice
        async with session_maker() as s:
            await crud.set_anon_accepting(s, 7001, False)
            await s.commit()

        m_paused = _make_msg(8002, f"/start q_{token}")
        await cmd_start(m_paused, st_sender)
        assert "to'xtatgan" in m_paused.answer.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_stale_bot_username_correction_and_all_links(tmp_path):
    """Eskirgan BOT_USERNAME (Bauntycinema_bot) barcha link va kartalarda tuzatilishi testi."""
    import urllib.parse
    from types import SimpleNamespace
    from aiogram.types import BufferedInputFile

    from handlers.anon_questions import build_anon_link_and_share, cb_anon_share_card
    from handlers.groups import cmd_groups_info
    from handlers.referral import cmd_referral_info
    from handlers.tvroom import get_tvroom_keyboard
    from keyboards.inline import anon_questions_keyboard, movie_item_keyboard
    from services.bot_identity import (
        get_bot_username,
        reset_live_bot_username_cache,
        set_live_bot_username,
        sync_bot_username,
    )

    db_file = tmp_path / "anon_links_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def fake_get_session():
        async with session_maker() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    orig_username = config.BOT_USERNAME
    reset_live_bot_username_cache()
    try:
        # 1. Mock obyektlar jonli username sifatida qabul qilinmasligi kerak
        assert set_live_bot_username(MagicMock()) is None
        config.BOT_USERNAME = "Bauntycinema_bot"
        assert get_bot_username() == "BauntyCinemabot"

        # 2. Bot get_me() orqali jonli sinxronizatsiya config.BOT_USERNAME ni ham tuzatadi
        fake_bot = SimpleNamespace(
            get_me=AsyncMock(return_value=SimpleNamespace(username="BauntyCinemabot"))
        )
        synced = await sync_bot_username(fake_bot)
        assert synced == "BauntyCinemabot"
        assert config.BOT_USERNAME == "BauntyCinemabot"

        # 3. URL encoding bilan share URL hamda barcha link generatorlar
        link, share_url = build_anon_link_and_share(get_bot_username(), "XyZ9876543")
        assert link == "https://t.me/BauntyCinemabot?start=q_XyZ9876543"
        parsed_share = urllib.parse.parse_qs(urllib.parse.urlparse(share_url).query)
        assert parsed_share["url"] == [link]
        assert "anonim savol" in parsed_share["text"][0].lower()

        kb_movie = movie_item_keyboard("101")
        movie_urls = [b.url for row in kb_movie.inline_keyboard for b in row if b.url]
        assert any("https%3A%2F%2Ft.me%2FBauntyCinemabot%3Fstart%3Dkino_101" in u for u in movie_urls)
        assert all("Bauntycinema_bot" not in u for u in movie_urls)

        kb_tv = get_tvroom_keyboard("4242")
        tv_urls = [b.url for row in kb_tv.inline_keyboard for b in row if b.url]
        assert any("https%3A%2F%2Ft.me%2FBauntyCinemabot%3Fstart%3Dtvroom_4242" in u for u in tv_urls)
        assert all("Bauntycinema_bot" not in u for u in tv_urls)

        kb_anon = anon_questions_keyboard(share_url, is_accepting=True)
        row1_callbacks = [b.callback_data for b in kb_anon.inline_keyboard[0] if b.callback_data]
        assert "anon:share_card" in row1_callbacks

        # 4. /groups va Referral handlerlari
        storage = MemoryStorage()
        state = FSMContext(storage=storage, key=MagicMock())
        m_grp = AsyncMock(spec=Message)
        m_grp.from_user = TgUser(id=9101, is_bot=False, first_name="Ali")
        m_grp.bot = fake_bot
        m_grp.answer = AsyncMock()
        await cmd_groups_info(m_grp, state)
        grp_kb = m_grp.answer.call_args.kwargs["reply_markup"]
        assert grp_kb.inline_keyboard[0][0].url == "https://t.me/BauntyCinemabot?startgroup=true"

        with patch("handlers.referral.get_session", fake_get_session):
            m_ref = AsyncMock(spec=Message)
            m_ref.from_user = TgUser(id=9101, is_bot=False, first_name="Ali")
            m_ref.bot = fake_bot
            m_ref.answer = AsyncMock()
            await cmd_referral_info(m_ref, state)
            ref_kb = m_ref.answer.call_args.kwargs["reply_markup"]
            ref_url = ref_kb.inline_keyboard[0][0].url
            assert "BauntyCinemabot%3Fstart%3Dr_9101" in ref_url
            assert "Bauntycinema_bot" not in ref_url

        # 5. Chiroyli karta (anon:share_card) protect_content=False va 1200x675 PNG banner yuboradi
        with patch("handlers.anon_questions.get_session", fake_get_session):
            cb_card = AsyncMock(spec=CallbackQuery)
            cb_card.from_user = TgUser(id=9101, is_bot=False, first_name="Ali")
            cb_card.bot = fake_bot
            cb_card.answer = AsyncMock()
            cb_card.message = AsyncMock(spec=Message)
            cb_card.message.answer_photo = AsyncMock()
            await cb_anon_share_card(cb_card)

            assert cb_card.message.answer_photo.called
            photo_kwargs = cb_card.message.answer_photo.call_args.kwargs
            assert photo_kwargs["protect_content"] is False
            assert photo_kwargs["parse_mode"] == "HTML"
            assert "https://t.me/BauntyCinemabot?start=q_" in photo_kwargs["caption"]
            assert isinstance(photo_kwargs["photo"], BufferedInputFile)
            banner_im = Image.open(io.BytesIO(photo_kwargs["photo"].data))
            assert banner_im.size == (1200, 675)
            card_btn = photo_kwargs["reply_markup"].inline_keyboard[0][0]
            assert card_btn.url.startswith("https://t.me/BauntyCinemabot?start=q_")
    finally:
        config.BOT_USERNAME = orig_username
        reset_live_bot_username_cache()
        await engine.dispose()


@pytest.mark.asyncio
async def test_anon_target_normalization_and_pending_sub_resume(tmp_path):
    """Token registr/tinish belgilaridan tozalash va obunadan keyin /start q_<token> ni tiklash testi."""
    from types import SimpleNamespace
    from aiogram.types import ChatMemberMember
    from handlers.start import callback_check_subscription
    from middlewares.subscription import SubscriptionMiddleware, pop_pending_start_param
    from services.bot_identity import reset_live_bot_username_cache

    db_file = tmp_path / "anon_sub_resume.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def fake_get_session():
        async with session_maker() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    reset_live_bot_username_cache()
    try:
        async with session_maker() as s:
            await crud.get_or_create_user(s, user_id=7101, first_name="Owner")
            await crud.get_or_create_user(s, user_id=8103, first_name="Sender")
            prof = await crud.get_or_create_anon_profile(s, 7101)
            await s.commit()
            token = prof.token

            # Registr va qo'shimcha belgilarga chidamlilik
            assert await crud.resolve_anon_target(s, token) == (7101, True)
            assert await crud.resolve_anon_target(s, token.lower()) == (7101, True)
            assert await crud.resolve_anon_target(s, token.upper()) == (7101, True)
            assert await crud.resolve_anon_target(s, f"{token}.)") == (7101, True)
            assert await crud.resolve_anon_target(s, f"{token}&fbclid=123") == (7101, True)

        sender = TgUser(id=8103, is_bot=False, first_name="Sender")
        unsub_bot = MagicMock()
        unsub_bot.get_me = AsyncMock(return_value=SimpleNamespace(username="BauntyCinemabot"))
        unsub_bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="left"))

        msg_start = AsyncMock(spec=Message)
        msg_start.from_user = sender
        msg_start.text = f"/start q_{token}"
        msg_start.chat = Chat(id=8103, type="private")
        msg_start.bot = unsub_bot
        msg_start.answer = AsyncMock()

        downstream = AsyncMock()
        mw = SubscriptionMiddleware()
        with patch("middlewares.subscription.get_session", fake_get_session):
            await mw(downstream, msg_start, {"event_from_user": sender, "bot": unsub_bot})

        assert not downstream.called
        assert msg_start.answer.called

        # Obunadan keyin «✅ Obunani tekshirish» bosilganda saqlangan q_<token> davom etadi
        storage = MemoryStorage()
        st = FSMContext(storage=storage, key=MagicMock())

        sub_bot = MagicMock()
        sub_bot.get_me = AsyncMock(return_value=SimpleNamespace(username="BauntyCinemabot"))
        sub_bot.get_chat_member = AsyncMock(
            return_value=ChatMemberMember(status="member", user=sender)
        )

        cb_check = AsyncMock(spec=CallbackQuery)
        cb_check.from_user = sender
        cb_check.data = "check_subscription"
        cb_check.bot = sub_bot
        cb_check.answer = AsyncMock()
        cb_check.message = AsyncMock(spec=Message)
        cb_check.message.bot = sub_bot
        cb_check.message.chat = Chat(id=8103, type="private")
        cb_check.message.delete = AsyncMock()
        cb_check.message.answer = AsyncMock()

        with patch("handlers.start.get_session", fake_get_session):
            await callback_check_subscription(cb_check, st)

        assert await st.get_state() == AnonQuestionStates.waiting_for_message.state
        assert (await st.get_data())["anon_target_id"] == 7101
        assert "anonim" in cb_check.message.answer.call_args.args[0].lower()
        assert pop_pending_start_param(8103) is None
    finally:
        reset_live_bot_username_cache()
        await engine.dispose()

