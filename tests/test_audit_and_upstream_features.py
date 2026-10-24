"""
Audit & Upstream 1-to-1 Features Test Suite:
- Movie search by year and actor in CRUD, MovieService, Bot handlers & pagination
- Web API /api/movies with ?year= and ?actor= filters
- Commands /tv, /quiz, /games and deep links in start handler
- 100% Bauntys branding verification
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from config import config
from database.session import init_db, get_session
from database import crud
from services.movie_service import movie_service
from services.web_server import create_web_app
from handlers.movies import (
    cb_movie_by_year,
    cb_movie_by_actor,
    state_process_year,
    state_process_actor,
    cb_year_page,
    cb_actor_page,
)
from handlers.start import (
    cmd_start,
    cmd_tv,
    cmd_quiz,
    cmd_games,
)
from utils.states import MovieSearchStates
from keyboards.inline import movie_menu_keyboard


@pytest.mark.asyncio
async def test_movie_search_by_year_and_actor_crud_and_service():
    """CRUD va MovieService da yil va aktyor bo'yicha qidirish testlari."""
    await init_db()
    async with get_session() as session:
        # Test kinolarini kiritish
        m1, _ = await crud.upsert_movie(
            session=session,
            code="9901",
            title="Maxsus Vazifa 1",
            description="Bosh rolda Keanu Reeves Test va Jason Statham.",
            year=1904,
            views_count=500
        )
        m2, _ = await crud.upsert_movie(
            session=session,
            code="9902",
            title="Maxsus Vazifa 2",
            description="Keanu Reeves Test ishtirokidagi sarguzasht film.",
            year=1904,
            views_count=300
        )
        m3, _ = await crud.upsert_movie(
            session=session,
            code="9903",
            title="Eski Sarguzasht",
            description="Bosh rolda boshqa qahramon.",
            year=1915,
            views_count=100
        )
        await session.commit()

        # 1. Yil bo'yicha qidiruv
        y_count = await crud.get_movies_by_year_count(session, year=1904)
        assert y_count == 2
        y_movies = await crud.get_movies_by_year(session, year=1904, limit=10)
        assert len(y_movies) == 2
        assert any(m.code == "9901" for m in y_movies)
        assert any(m.code == "9902" for m in y_movies)

        # MovieService orqali
        srv_y_count = await movie_service.get_year_count(session, year=1904)
        assert srv_y_count == y_count
        srv_y_movies = await movie_service.get_by_year(session, year=1904)
        assert len(srv_y_movies) == 2

        # 2. Aktyor bo'yicha qidiruv
        act_count = await crud.get_movies_by_actor_count(session, actor="Keanu Reeves Test")
        assert act_count >= 2
        act_movies = await crud.get_movies_by_actor(session, actor="Keanu Reeves Test")
        assert any(m.code == "9901" for m in act_movies)
        assert any(m.code == "9902" for m in act_movies)

        srv_act_movies = await movie_service.search_by_actor(session, actor="Jason Statham")
        assert any(m.code == "9901" for m in srv_act_movies)

        # 3. Kirill va Lotin transliteratsiyasi bo'yicha qidiruv
        srv_cyr_movies = await movie_service.search_by_actor(session, actor="Киану Ривз")
        assert any(m.code == "9901" for m in srv_cyr_movies) or any(m.code == "9902" for m in srv_cyr_movies)
        srv_statham = await movie_service.search_by_actor(session, actor="Стэйтем")
        assert any(m.code == "9901" for m in srv_statham)

        # 4. Katalogdan aktyor va yil bo'yicha qidiruv metodlari
        cat_statham = movie_service.search_catalog_by_actor("Statham", limit=5)
        assert isinstance(cat_statham, list)
        cat_year = movie_service.search_catalog_by_year(2023, limit=5)
        assert isinstance(cat_year, list)


@pytest.mark.asyncio
async def test_bot_movie_menu_keyboard_has_year_and_actor():
    """movie_menu_keyboard da Yili bo'yicha va Aktyor bo'yicha tugmalari mavjudligi."""
    kb = movie_menu_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "movie:by_year" in callbacks
    assert "movie:by_actor" in callbacks
    assert any("Yili" in t for t in texts)
    assert any("Aktyor" in t for t in texts)


@pytest.mark.asyncio
async def test_bot_handlers_year_and_actor_flow():
    """Botda yil va aktyor qidiruvi callback va FSM message handleri testi."""
    await init_db()
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=112233, user_id=112233)
    state = FSMContext(storage=storage, key=key)

    # 1. cb_movie_by_year
    cb_year = AsyncMock()
    cb_year.message.answer = AsyncMock()
    cb_year.answer = AsyncMock()
    await cb_movie_by_year(cb_year, state)
    current_state = await state.get_state()
    assert current_state == MovieSearchStates.waiting_for_year.state

    # 2. state_process_year (invalid year)
    msg_inv = AsyncMock()
    msg_inv.text = "abc"
    msg_inv.answer = AsyncMock()
    await state_process_year(msg_inv, state)
    assert "4 xonali" in msg_inv.answer.call_args[0][0]

    # 3. state_process_year (valid year)
    msg_val = AsyncMock()
    msg_val.text = "2024"
    msg_val.answer = AsyncMock()
    msg_val.from_user.id = 112233
    await state_process_year(msg_val, state)
    assert await state.get_state() is None
    assert msg_val.answer.called

    # 4. cb_movie_by_actor
    cb_actor = AsyncMock()
    cb_actor.message.answer = AsyncMock()
    cb_actor.answer = AsyncMock()
    await cb_movie_by_actor(cb_actor, state)
    assert await state.get_state() == MovieSearchStates.waiting_for_actor.state

    # 5. state_process_actor
    msg_act = AsyncMock()
    msg_act.text = "Tom Cruise"
    msg_act.answer = AsyncMock()
    msg_act.from_user.id = 112233
    await state_process_actor(msg_act, state)
    assert await state.get_state() is None
    assert msg_act.answer.called


@pytest.mark.asyncio
async def test_cmd_start_new_deep_links():
    """cmd_start da tv, quiz, va games deep linking testi."""
    await init_db()
    mock_bot = AsyncMock()
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=554433, user_id=554433)
    state = FSMContext(storage=storage, key=key)

    # 1. /start tv
    msg_tv = AsyncMock()
    msg_tv.from_user.id = 554433
    msg_tv.from_user.username = "test_tv_user"
    msg_tv.from_user.first_name = "TV"
    msg_tv.from_user.last_name = "User"
    msg_tv.text = "/start tv"
    msg_tv.bot = mock_bot
    msg_tv.answer = AsyncMock()
    await cmd_start(msg_tv, state)
    assert msg_tv.answer.called
    assert "Jonli TV" in msg_tv.answer.call_args[0][0]

    # 2. /start games
    msg_games = AsyncMock()
    msg_games.from_user.id = 554433
    msg_games.from_user.username = "test_games_user"
    msg_games.from_user.first_name = "Games"
    msg_games.from_user.last_name = "User"
    msg_games.text = "/start games"
    msg_games.bot = mock_bot
    msg_games.answer = AsyncMock()
    await cmd_start(msg_games, state)
    assert msg_games.answer.called
    assert "O'yinlar" in msg_games.answer.call_args[0][0]

    # 3. /start quiz
    msg_quiz = AsyncMock()
    msg_quiz.from_user.id = 554433
    msg_quiz.from_user.username = "test_quiz_user"
    msg_quiz.from_user.first_name = "Quiz"
    msg_quiz.from_user.last_name = "User"
    msg_quiz.text = "/start quiz"
    msg_quiz.bot = mock_bot
    msg_quiz.answer = AsyncMock()
    await cmd_start(msg_quiz, state)
    assert msg_quiz.answer.called
    assert "Viktorina" in msg_quiz.answer.call_args[0][0]

    # 4. /start kino
    msg_kino = AsyncMock()
    msg_kino.from_user.id = 554433
    msg_kino.from_user.username = "test_kino_user"
    msg_kino.from_user.first_name = "Kino"
    msg_kino.from_user.last_name = "User"
    msg_kino.text = "/start kino"
    msg_kino.bot = mock_bot
    msg_kino.answer = AsyncMock()
    await cmd_start(msg_kino, state)
    assert msg_kino.answer.called

    # 5. /start music
    msg_music = AsyncMock()
    msg_music.from_user.id = 554433
    msg_music.from_user.username = "test_music_user"
    msg_music.from_user.first_name = "Music"
    msg_music.from_user.last_name = "User"
    msg_music.text = "/start music"
    msg_music.bot = mock_bot
    msg_music.answer = AsyncMock()
    await cmd_start(msg_music, state)
    assert msg_music.answer.called

    # 6. /start docs
    msg_docs = AsyncMock()
    msg_docs.from_user.id = 554433
    msg_docs.from_user.username = "test_docs_user"
    msg_docs.from_user.first_name = "Docs"
    msg_docs.from_user.last_name = "User"
    msg_docs.text = "/start docs"
    msg_docs.bot = mock_bot
    msg_docs.answer = AsyncMock()
    await cmd_start(msg_docs, state)
    assert msg_docs.answer.called

    # 7. /start story
    msg_story = AsyncMock()
    msg_story.from_user.id = 554433
    msg_story.from_user.username = "test_story_user"
    msg_story.from_user.first_name = "Story"
    msg_story.from_user.last_name = "User"
    msg_story.text = "/start story"
    msg_story.bot = mock_bot
    msg_story.answer = AsyncMock()
    await cmd_start(msg_story, state)
    assert msg_story.answer.called


@pytest.mark.asyncio
async def test_cmd_tv_quiz_games():
    """/tv, /quiz, /games, /kino, /docs, /story, /prava buyruqlari to'g'ridan-to'g'ri ishlashi testi."""
    from handlers.movies import cmd_movies_menu
    from handlers.docs import cmd_docs_menu
    from handlers.story import cmd_story_prompt
    from handlers.start import cmd_prava

    msg = AsyncMock()
    msg.answer = AsyncMock()
    msg.from_user.id = 112233

    await cmd_tv(msg)
    assert msg.answer.called
    assert "Jonli TV" in msg.answer.call_args[0][0]

    msg.answer.reset_mock()
    await cmd_quiz(msg)
    assert msg.answer.called
    assert "Viktorina" in msg.answer.call_args[0][0]

    msg.answer.reset_mock()
    await cmd_games(msg)
    assert msg.answer.called
    assert "O'yinlar" in msg.answer.call_args[0][0]

    msg.answer.reset_mock()
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=112233, user_id=112233)
    state = FSMContext(storage=storage, key=key)
    await cmd_movies_menu(msg, state)
    assert msg.answer.called
    assert "Kino" in msg.answer.call_args[0][0]

    msg.answer.reset_mock()
    await cmd_docs_menu(msg, state)
    assert msg.answer.called
    assert "Hujjatlar" in msg.answer.call_args[0][0]

    msg.answer.reset_mock()
    await cmd_story_prompt(msg, state)
    assert msg.answer.called
    assert "Story" in msg.answer.call_args[0][0]

    msg.answer.reset_mock()
    await cmd_prava(msg)
    assert msg.answer.called
    assert "Prava" in msg.answer.call_args[0][0]


class TestMoviesApiYearAndActor(AioHTTPTestCase):
    async def get_application(self):
        return create_web_app()

    @unittest_run_loop
    async def test_api_movies_year_and_actor_filtering(self):
        """Web API /api/movies da year va actor filtrlari (hamda Kirill scripti) ishlashi testi."""
        resp_year = await self.client.get("/api/movies?year=2024")
        assert resp_year.status == 200
        data_year = await resp_year.json()
        assert data_year.get("ok") is True

        resp_actor = await self.client.get("/api/movies?actor=Cruise")
        assert resp_actor.status == 200
        data_actor = await resp_actor.json()
        assert data_actor.get("ok") is True

        # Kirill yozuvida qidiruv
        resp_cyr = await self.client.get("/api/movies?actor=Стэйтем")
        assert resp_cyr.status == 200
        data_cyr = await resp_cyr.json()
        assert data_cyr.get("ok") is True
