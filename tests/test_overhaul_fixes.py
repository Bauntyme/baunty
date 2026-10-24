"""
Overhaul & Comprehensive Fixes Test Suite:
1. Movie delivery & watch keyboard (no raw external URLs, 20-item pagination, WebAppInfo)
2. Mafia matchmaking (quick_play joins most populated waiting room, deep link formats)
3. Viktorina (Quiz) local QuizService & API endpoints (/home, /daily, /solo/start, /solo/answer, /solo/next, /weekly)
4. Multi-language i18n service & handlers (/til, /lang, /language, set_lang)
5. BotSecurityMiddleware (threat WAF, anti-flood sliding window, ban check)
6. Admin commands (/profilaktika on/off, /stats, /movies, /sponsors, /settings, /broadcast, /ban, /unban)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User as TgUser, Chat
from aiohttp.test_utils import TestClient, TestServer

from config import config
from keyboards.inline import movie_item_keyboard, movie_parts_keyboard
from services.web_server import create_web_app
from services.quiz_service import quiz_service, TOPICS
from services.i18n_service import i18n_service
from services.mafia_service import mafia_service
from services.maintenance_service import maintenance_service
from database.session import init_db, get_session
from database import crud
from middlewares.security import BotSecurityMiddleware
from handlers.admin import (
    cmd_admin_profilaktika,
    cmd_admin_stats,
    cmd_admin_movies,
    cmd_admin_sponsors,
    cmd_admin_settings,
    cmd_admin_broadcast,
    cmd_admin_ban,
    cmd_admin_unban,
)
from handlers.language import cmd_language, cb_set_language


import pytest_asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base


@pytest_asyncio.fixture
async def in_memory_session():
    """In-memory SQLite testi uchun fixture."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


def make_session_ctx(session_obj):
    @asynccontextmanager
    async def _ctx():
        yield session_obj
        await session_obj.commit()
    return _ctx


def make_tg_user(user_id=12345, first_name="TestUser", is_bot=False):
    return TgUser(id=user_id, is_bot=is_bot, first_name=first_name, username="testuser")


def make_message(text="/start", user_id=12345, first_name="TestUser"):
    u = make_tg_user(user_id, first_name)
    chat = Chat(id=user_id, type="private")
    msg = MagicMock(spec=Message)
    msg.message_id = 999
    msg.from_user = u
    msg.chat = chat
    msg.text = text
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg


def make_callback_query(data="test:data", user_id=12345, first_name="TestUser"):
    u = make_tg_user(user_id, first_name)
    msg = make_message(user_id=user_id, first_name=first_name)
    msg.edit_text = AsyncMock()
    cb = MagicMock(spec=CallbackQuery)
    cb.id = "cb_123"
    cb.from_user = u
    cb.message = msg
    cb.data = data
    cb.answer = AsyncMock()
    return cb


# =====================================================================
# 1. MOVIE KEYBOARD TESTS
# =====================================================================
def test_movie_parts_keyboard_no_raw_popup_and_exact_parts():
    """movie_parts_keyboard must not produce raw external popups and must have exact 20 parts."""
    kb = movie_parts_keyboard(movie_code="777", total_parts=50, current_part=1, page=0)
    buttons = [btn for row in kb.inline_keyboard for btn in row]

    part_buttons = [b for b in buttons if b.callback_data and b.callback_data.startswith("watch_part:")]
    assert len(part_buttons) == 20
    assert part_buttons[0].text == "▶️ 1"
    assert part_buttons[-1].text == "20"

    # Make sure no raw external non-telegram URL exists
    for b in buttons:
        if b.url:
            assert b.url.startswith("https://t.me/")


def test_movie_item_keyboard_webapp_or_internal():
    """movie_item_keyboard uses WebAppInfo or callback_data instead of raw browser url."""
    kb = movie_item_keyboard(movie_code="999", watch_url="https://server.asilmedia.org/watch/999")
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    for b in buttons:
        if b.url:
            assert b.url.startswith("https://t.me/")
        if b.web_app:
            assert b.web_app.url.startswith("https://")


# =====================================================================
# 2. MAFIA MATCHMAKING & INVITE LINKS
# =====================================================================
def test_mafia_quick_play_joins_most_filled_waiting_lobby():
    """quick_play should join an existing waiting lobby sorted by player count descending."""
    mafia_service.rooms.clear()
    mafia_service.user_room_map.clear()

    # Create room 1 with 1 player
    r1 = mafia_service.create_room(user_id=101, user_name="User101", room_name="Room1", max_players=10, pub=True)
    r1_id = r1["room"]["id"]

    # Create room 2 with 3 players
    r2 = mafia_service.create_room(user_id=201, user_name="User201", room_name="Room2", max_players=10, pub=True)
    r2_id = r2["room"]["id"]
    mafia_service.join_room(user_id=202, user_name="User202", room_id=r2_id)
    mafia_service.join_room(user_id=203, user_name="User203", room_id=r2_id)

    # quick_play for new player 301
    qp_res = mafia_service.quick_play(user_id=301, user_name="User301")
    assert qp_res["ok"] is True
    # Should join Room2 because it has 3 players (closest to starting)
    assert qp_res["room"]["id"] == r2_id
    assert any(p["u"] == 301 for p in mafia_service.rooms[r2_id].players)


# =====================================================================
# 3. VIKTORINA (QUIZ) LOCAL SERVICE & ENDPOINTS
# =====================================================================
@pytest.mark.asyncio
async def test_quiz_local_endpoints():
    """All quiz API endpoints must return 200 with rich local QuizService data."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. /api/quiz/home
        resp = await client.get("/api/quiz/home")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("ok") is True
        assert len(data.get("topics", [])) == len(TOPICS)
        assert len(data.get("popular", [])) > 0

        # 2. /api/quiz/daily
        resp_d = await client.get("/api/quiz/daily")
        assert resp_d.status == 200
        data_d = await resp_d.json()
        assert data_d.get("ok") is True
        assert "d" in data_d
        assert "q" in data_d["d"]

        # 3. /api/quiz/solo/start
        resp_s = await client.post("/api/quiz/solo/start", json={"tp": "umumiy"})
        assert resp_s.status == 200
        data_s = await resp_s.json()
        assert data_s.get("ok") is True
        sid = data_s.get("sid")
        assert sid is not None
        assert data_s.get("total") == 10
        assert data_s.get("q") is not None
        assert len(data_s["q"]["o"]) == 4

        # 4. /api/quiz/solo/answer
        resp_a = await client.post("/api/quiz/solo/answer", json={"sid": sid, "i": 0, "o": 1})
        assert resp_a.status == 200
        data_a = await resp_a.json()
        assert data_a.get("ok") is True
        assert "right" in data_a
        assert "score" in data_a

        # 5. /api/quiz/solo/next
        resp_n = await client.post("/api/quiz/solo/next", json={"sid": sid})
        assert resp_n.status == 200
        data_n = await resp_n.json()
        assert data_n.get("ok") is True
        assert "i" in data_n or "final" in data_n

        # 6. /api/quiz/weekly
        resp_w = await client.get("/api/quiz/weekly")
        assert resp_w.status == 200
        data_w = await resp_w.json()
        assert data_w.get("ok") is True
        assert len(data_w.get("leaders", [])) > 0

        # 7. /api/quiz/room create & join
        resp_r = await client.post("/api/quiz/room", json={"tp": "tarix", "n": 5, "s": 20})
        assert resp_r.status == 200
        data_r = await resp_r.json()
        assert data_r.get("ok") is True
        pin = data_r.get("pin")
        assert pin is not None and len(pin) == 6

        resp_j = await client.post(f"/api/quiz/room/{pin}/join", json={"name": "Otabek"})
        assert resp_j.status == 200
        data_j = await resp_j.json()
        assert data_j.get("ok") is True

    finally:
        await client.close()


# =====================================================================
# 4. MULTI-LANGUAGE I18N TESTS
# =====================================================================
@pytest.mark.asyncio
async def test_i18n_service_and_commands(in_memory_session):
    """i18n_service translates keys and handlers update database language."""
    # Test translations
    assert "Tilni tanlang" in i18n_service.get_text("choose_language", "uz")
    assert "Тилни танланг" in i18n_service.get_text("choose_language", "oz")
    assert "Выберите язык" in i18n_service.get_text("choose_language", "ru")

    kb = i18n_service.get_language_keyboard("uz")
    assert len(kb.inline_keyboard) >= 2

    with patch("handlers.language.get_session", make_session_ctx(in_memory_session)):
        # Test /til command
        msg = make_message(text="/til", user_id=4444)
        await cmd_language(msg)
        assert msg.answer.called

        # Test set_lang callback
        cb = make_callback_query(data="set_lang:ru", user_id=4444)
        await cb_set_language(cb)
        assert cb.answer.called

        lang = await crud.get_user_language(in_memory_session, 4444)
        assert lang == "ru"


# =====================================================================
# 5. BOT SECURITY MIDDLEWARE TESTS
# =====================================================================
@pytest.mark.asyncio
async def test_bot_security_middleware(in_memory_session):
    """BotSecurityMiddleware catches WAF exploits, blocks banned users, allows normal traffic."""
    middleware = BotSecurityMiddleware(window_seconds=2.0, max_requests=3)
    handler_mock = AsyncMock(return_value="OK")

    with patch("middlewares.security.get_session", make_session_ctx(in_memory_session)):
        # 1. Normal user call passes
        msg_normal = make_message(text="Salom, kino qidiryapman", user_id=5555)
        res = await middleware(handler_mock, msg_normal, {})
        assert res == "OK"
        assert handler_mock.called

        # 2. WAF malicious exploit pattern gets blocked
        handler_mock.reset_mock()
        msg_waf = make_message(text="UNION SELECT * FROM users", user_id=6666)
        res_waf = await middleware(handler_mock, msg_waf, {})
        assert res_waf is None
        assert not handler_mock.called
        assert msg_waf.reply.called

        # 3. Banned user gets blocked
        await crud.get_or_create_user(in_memory_session, user_id=7777)
        await crud.set_user_ban_status(in_memory_session, 7777, True)

        handler_mock.reset_mock()
        msg_banned = make_message(text="start", user_id=7777)
        res_banned = await middleware(handler_mock, msg_banned, {})
        assert res_banned is None
        assert not handler_mock.called
        assert msg_banned.answer.called


# =====================================================================
# 6. ADMIN COMMANDS TESTS
# =====================================================================
@pytest.mark.asyncio
async def test_admin_commands(in_memory_session):
    """Admin slash commands work properly for authorized admin."""
    admin_id = config.admin_ids[0] if config.admin_ids else 123456789
    with patch("handlers.admin.is_admin_check", return_value=True), \
         patch("handlers.admin.get_session", make_session_ctx(in_memory_session)):
        # 1. /profilaktika on and off
        msg_prof_on = make_message(text="/profilaktika on", user_id=admin_id)
        await cmd_admin_profilaktika(msg_prof_on)
        assert maintenance_service.is_global_maintenance() is True
        assert msg_prof_on.answer.called

        msg_prof_off = make_message(text="/profilaktika off", user_id=admin_id)
        await cmd_admin_profilaktika(msg_prof_off)
        assert maintenance_service.is_global_maintenance() is False

        # 2. /stats
        msg_stats = make_message(text="/stats", user_id=admin_id)
        await cmd_admin_stats(msg_stats)
        assert msg_stats.answer.called

        # 3. /movies
        msg_movies = make_message(text="/movies", user_id=admin_id)
        await cmd_admin_movies(msg_movies)
        assert msg_movies.answer.called

        # 4. /sponsors
        msg_sponsors = make_message(text="/sponsors", user_id=admin_id)
        await cmd_admin_sponsors(msg_sponsors)
        assert msg_sponsors.answer.called

        # 5. /settings
        msg_settings = make_message(text="/settings", user_id=admin_id)
        await cmd_admin_settings(msg_settings)
        assert msg_settings.answer.called

        # 6. /broadcast
        msg_bc = make_message(text="/broadcast", user_id=admin_id)
        state_mock = AsyncMock()
        await cmd_admin_broadcast(msg_bc, state_mock)
        assert state_mock.set_state.called
        assert msg_bc.answer.called

        # 7. /ban and /unban
        msg_ban = make_message(text="/ban 888888 spammer", user_id=admin_id)
        await cmd_admin_ban(msg_ban)
        assert msg_ban.answer.called
        assert await crud.is_user_banned(in_memory_session, 888888) is True

        msg_unban = make_message(text="/unban 888888", user_id=admin_id)
        await cmd_admin_unban(msg_unban)
        assert msg_unban.answer.called
        assert await crud.is_user_banned(in_memory_session, 888888) is False


# =====================================================================
# 7. DEEP LINK MOVIE WITH PART & MAFIA EDGE CASES
# =====================================================================
@pytest.mark.asyncio
async def test_movie_deeplink_m_with_part_parsing(in_memory_session):
    """Deep link /start m_101_2 extracts movie_code 101 and part 2."""
    from handlers.start import cmd_start
    from services.movie_service import movie_service

    msg = make_message(text="/start m_101_2", user_id=12345)
    state_mock = AsyncMock()

    with patch("handlers.start.get_session", make_session_ctx(in_memory_session)), \
         patch.object(movie_service, "get_catalog_item", return_value={"code": "101", "title": "Test Movie"}), \
         patch.object(movie_service, "deliver_movie", new_callable=AsyncMock) as deliver_mock:
        deliver_mock.return_value = True
        await cmd_start(msg, state_mock)

        assert deliver_mock.called
        call_kwargs = deliver_mock.call_args[1]
        assert call_kwargs["code"] == "101"
        assert call_kwargs["part"] == 2


def test_mafia_quick_play_already_in_room():
    """quick_play re-returns the user's active lobby room without creating a duplicate."""
    mafia_service.rooms.clear()
    mafia_service.user_room_map.clear()

    # User 501 calls quick_play
    res1 = mafia_service.quick_play(user_id=501, user_name="User501")
    assert res1["ok"] is True
    room_id = res1["room"]["id"]

    # User 501 calls quick_play again while in lobby
    res2 = mafia_service.quick_play(user_id=501, user_name="User501")
    assert res2["ok"] is True
    assert res2["room"]["id"] == room_id
    # Ensure user is not duplicated in players
    players_501 = [p for p in mafia_service.rooms[room_id].players if p["u"] == 501]
    assert len(players_501) == 1


@pytest.mark.asyncio
async def test_security_middleware_global_maintenance_interception(in_memory_session):
    """BotSecurityMiddleware intercepts unauthorized actions during global maintenance."""
    middleware = BotSecurityMiddleware()
    handler_mock = AsyncMock()

    maintenance_service.set_global_maintenance(True, custom_message="Test maintenance")
    try:
        with patch("middlewares.security.get_session", make_session_ctx(in_memory_session)):
            # 1. Non-admin normal message is blocked
            msg_blocked = make_message(text="🎬 Kino", user_id=99999)
            res = await middleware(handler_mock, msg_blocked, {})
            assert res is None
            assert not handler_mock.called
            assert msg_blocked.answer.called

            # 2. Allowed action (music) passes through
            handler_mock.reset_mock()
            msg_music = make_message(text="🎵 Qo'shiq topish", user_id=99999)
            await middleware(handler_mock, msg_music, {})
            assert handler_mock.called

            # 3. Allowed action (media URL) passes through
            handler_mock.reset_mock()
            msg_url = make_message(text="https://instagram.com/p/12345", user_id=99999)
            await middleware(handler_mock, msg_url, {})
            assert handler_mock.called
    finally:
        maintenance_service.set_global_maintenance(False)

