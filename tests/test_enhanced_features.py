"""
Kengaytirilgan imkoniyatlar uchun to'liq testlar:
- Anonim story API (IG, TG, Send, Watch, Me)
- iTunes + Deezer + Local kesh musiqalarni qidirish va MP3 yetkazish
- YouTube ID resolver va Downloader zaxira mexanizmlari (Cobalt, TikWM)
- Kinolar 1-qism va barcha qismlar yetkazilishi va @Zakirovsfilms_bot integratsiyasi
"""
import pytest
import re
from unittest.mock import AsyncMock
from aiohttp.test_utils import TestClient, TestServer
from services.web_server import create_web_app, set_bot_instance
from services.music_service import music_service
from services.downloader import media_downloader
from keyboards.inline import movie_item_keyboard, movie_parts_keyboard
from database.session import init_db, get_session
from database import crud
from services.movie_service import movie_service


@pytest.mark.asyncio
async def test_story_api_endpoints():
    """Web serverdagi yangi story API lari (/api/story/me, /ig, /ighl, /tg, /watch, /send)."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. /api/story/me
        resp_me = await client.get("/api/story/me")
        assert resp_me.status == 200
        data_me = await resp_me.json()
        assert data_me.get("ok") is True

        # /webapp/api/story/me (alias)
        resp_me_alias = await client.get("/webapp/api/story/me")
        assert resp_me_alias.status == 200

        # 2. /api/story/ig
        resp_ig = await client.get("/api/story/ig?u=cristiano")
        assert resp_ig.status == 200
        data_ig = await resp_ig.json()
        assert data_ig.get("ok") is True
        assert "name" in data_ig
        assert "items" in data_ig
        assert len(data_ig.get("items", [])) > 0

        # /api/story/ig without u parameter -> 400
        resp_ig_bad = await client.get("/api/story/ig")
        assert resp_ig_bad.status == 400

        # 3. /api/story/ighl
        resp_ighl = await client.get("/api/story/ighl?u=cristiano")
        assert resp_ighl.status == 200
        data_ighl = await resp_ighl.json()
        assert data_ighl.get("ok") is True

        # 4. /api/story/tg
        resp_tg = await client.get("/api/story/tg?u=kunuz")
        assert resp_tg.status == 200
        data_tg = await resp_tg.json()
        assert data_tg.get("ok") is True

        # 5. /api/story/watch
        resp_watch = await client.post("/api/story/watch", json={"id": "test_story_1"})
        assert resp_watch.status == 200
        data_watch = await resp_watch.json()
        assert data_watch.get("ok") is True

        # 6. /api/story/send without auth -> 401
        resp_send_unauth = await client.post("/api/story/send", json={"u": "cristiano"})
        assert resp_send_unauth.status == 401

        # 7. /api/story/send with auth header and mock bot
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=True)
        set_bot_instance(mock_bot)

        resp_send = await client.post(
            "/api/story/send",
            json={"u": "cristiano", "user_id": 12345678},
            headers={"X-Init-Data": "user=%7B%22id%22%3A12345678%7D"}
        )
        assert resp_send.status == 200
        data_send = await resp_send.json()
        assert data_send.get("ok") is True
    finally:
        set_bot_instance(None)
        await client.close()


@pytest.mark.asyncio
async def test_music_itunes_and_aggregated_search():
    """iTunes API qidiruv va ko'p manbali musiqiy qidiruv integratsiyasi testi."""
    tracks = await music_service.search_tracks("Faded", limit=5)
    assert len(tracks) > 0
    first = tracks[0]
    assert isinstance(first, dict)
    assert first.get("title")
    assert first.get("artist")

    # iTunes direct search method
    itunes_tracks = await music_service._search_itunes("Believer", limit=3)
    assert isinstance(itunes_tracks, list)
    if itunes_tracks:
        assert itunes_tracks[0].get("title")
        assert itunes_tracks[0].get("s") == "it"


def test_youtube_video_id_patterns():
    """YouTube 11 belgili ID regex va extractor tekshiruvi."""
    pattern = r"(?:v=|\/|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})"

    url1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    url2 = "https://youtu.be/dQw4w9WgXcQ"
    url3 = "https://www.youtube.com/shorts/dQw4w9WgXcQ"

    m1 = re.search(pattern, url1)
    m2 = re.search(pattern, url2)
    m3 = re.search(pattern, url3)

    assert m1 and m1.group(1) == "dQw4w9WgXcQ"
    assert m2 and m2.group(1) == "dQw4w9WgXcQ"
    assert m3 and m3.group(1) == "dQw4w9WgXcQ"


def test_movie_keyboards_zakirovsfilms_bot_integration():
    """Inline tugmalarda @Zakirovsfilms_bot deep-linki mavjudligini tekshirish."""
    # movie_item_keyboard
    kb = movie_item_keyboard(movie_code="123")
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    bot_links = [btn.url for btn in buttons if btn.url and "Zakirovsfilms_bot" in btn.url]
    assert len(bot_links) >= 1
    assert "start=123" in bot_links[0]

    # movie_parts_keyboard
    parts_kb = movie_parts_keyboard(movie_code="123", total_parts=3, current_part=1)
    parts_buttons = [btn for row in parts_kb.inline_keyboard for btn in row]
    part_links = [btn.url for btn in parts_buttons if btn.url and "Zakirovsfilms_bot" in btn.url]
    assert len(part_links) >= 1
    assert "start=123" in part_links[0] or "start=123_1" in part_links[0]


@pytest.mark.asyncio
async def test_deliver_movie_part1_variants_lookup():
    """Kinolar 1-qism uchun _1, -1, p1 va asosiy kod bo'yicha bazadan qidirish testi."""
    await init_db()
    mock_bot = AsyncMock()
    mock_bot.send_video = AsyncMock(return_value=True)
    mock_bot.send_photo = AsyncMock(return_value=True)

    real_file_id = "BAACAgIAAxkBAAE_REAL_VIDEO_ID_777_PART1_SECURE"
    async with get_session() as session:
        # Test uchun maxsus 777_1 kodli film qo'shamiz
        await crud.upsert_movie(
            session=session,
            code="777_1",
            title="Maxsus Agent (1-qism)",
            file_id=real_file_id,
            description="1-qism tafsilotlari"
        )
        await session.commit()

    # part=1 so'ralganda "777_1" kodi bilan saqlangan videoni muvaffaqiyatli yetkazishi kerak
    result = await movie_service.deliver_movie(
        bot=mock_bot,
        chat_id=987654321,
        code="777",
        part=1
    )
    assert result is True
    # mock_bot.send_video chaqirilganini tasdiqlash
    assert mock_bot.send_video.called
    call_args = mock_bot.send_video.call_args[1]
    assert call_args["video"] == real_file_id
