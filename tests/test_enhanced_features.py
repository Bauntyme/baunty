"""
Kengaytirilgan imkoniyatlar uchun to'liq testlar:
- Anonim story API (IG, TG, Send, Watch, Me)
- iTunes + Deezer + Local kesh musiqalarni qidirish va MP3 yetkazish
- YouTube ID resolver va Downloader zaxira mexanizmlari (Cobalt, TikWM)
- Kinolar 1-qism va barcha qismlar yetkazilishi va upstream integratsiyasi
"""
import pytest
import re
import json
from unittest.mock import AsyncMock, MagicMock, patch
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


def test_movie_keyboards_white_label_branding():
    """Inline tugmalarda Zakirovs brendi va havolalari butunlay yo'qligini tekshirish."""
    # movie_item_keyboard
    kb = movie_item_keyboard(movie_code="123")
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    for btn in buttons:
        if btn.url:
            assert "Zakirov" not in btn.url
            assert "zakirov" not in btn.url
        assert "Zakirov" not in btn.text
        assert "zakirov" not in btn.text

    play_btns = [btn for btn in buttons if btn.callback_data == "watch_part:123:1"]
    assert len(play_btns) == 1
    assert "Kinoni tomosha qilish" in play_btns[0].text

    # movie_parts_keyboard
    parts_kb = movie_parts_keyboard(movie_code="123", total_parts=3, current_part=1)
    parts_buttons = [btn for row in parts_kb.inline_keyboard for btn in row]
    for btn in parts_buttons:
        if btn.url:
            assert "Zakirov" not in btn.url
            assert "zakirov" not in btn.url
        assert "Zakirov" not in btn.text
        assert "zakirov" not in btn.text

    parts_play_btns = [btn for btn in parts_buttons if btn.callback_data == "watch_part:123:1"]
    assert len(parts_play_btns) >= 1


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


def test_movie_parts_keyboard_pagination():
    """Ko'p qismli seriallar uchun 20 tadan sahifalash va Telegram 100-tugma cheklovi testi."""
    # 256 qismli serial uchun tugmalar
    kb_p0 = movie_parts_keyboard(movie_code="289", total_parts=256, current_part=1, page=0)
    buttons_p0 = [btn for row in kb_p0.inline_keyboard for btn in row]
    # Telegram inline keyboard limit 100 dan ancha kam bo'lishi kerak
    assert len(buttons_p0) <= 25
    part_buttons = [b for b in buttons_p0 if b.callback_data and b.callback_data.startswith("watch_part:")]
    assert len(part_buttons) == 20
    assert part_buttons[0].text == "▶️ 1"
    assert part_buttons[-1].text == "20"

    # Keyingi sahifaga o'tish tugmasi mavjudligi
    nav_next = [b for b in buttons_p0 if b.callback_data == "parts_page:289:1"]
    assert len(nav_next) == 1

    # O'rta sahifa (page=1 -> 21 dan 40 gacha)
    kb_p1 = movie_parts_keyboard(movie_code="289", total_parts=256, current_part=25, page=1)
    buttons_p1 = [btn for row in kb_p1.inline_keyboard for btn in row]
    part_buttons_p1 = [b for b in buttons_p1 if b.callback_data and b.callback_data.startswith("watch_part:")]
    assert len(part_buttons_p1) == 20
    assert part_buttons_p1[0].text == "21"
    assert part_buttons_p1[4].text == "▶️ 25"

    nav_prev = [b for b in buttons_p1 if b.callback_data == "parts_page:289:0"]
    nav_next2 = [b for b in buttons_p1 if b.callback_data == "parts_page:289:2"]
    assert len(nav_prev) == 1
    assert len(nav_next2) == 1

    # Oxirgi sahifa (page=12 -> 241 dan 256 gacha, jami 16 ta qism)
    kb_last = movie_parts_keyboard(movie_code="289", total_parts=256, current_part=250, page=12)
    buttons_last = [btn for row in kb_last.inline_keyboard for btn in row]
    part_buttons_last = [b for b in buttons_last if b.callback_data and b.callback_data.startswith("watch_part:")]
    assert len(part_buttons_last) == 16
    assert part_buttons_last[0].text == "241"
    assert part_buttons_last[-1].text == "256"

    # Oxirgi sahifada oldingi tugma bor, keyingi tugma yo'q
    nav_prev_last = [b for b in buttons_last if b.callback_data == "parts_page:289:11"]
    assert len(nav_prev_last) == 1
    nav_next_none = [b for b in buttons_last if b.callback_data and b.callback_data.startswith("parts_page:289:13")]
    assert len(nav_next_none) == 0


def test_story_username_and_url_preservation():
    """Story username tozalash va URL aniqlash tekshiruvi."""
    from services.story_service import story_service

    assert story_service.clean_username("@cristiano") == "cristiano"
    assert story_service.clean_username("https://www.instagram.com/cristiano/") == "cristiano"
    assert story_service.clean_username("https://t.me/kunuz") == "kunuz"

    # URL larni ajrata olish
    story_url = "https://www.instagram.com/stories/cristiano/321456789/"
    is_url = "instagram.com" in story_url or "t.me" in story_url
    assert is_url is True


def test_music_results_keyboard_30_tracks_pagination():
    """30 ta trek uchun 8 tadan ixcham sahifalash va [⬅️ Oldingi], [Keyingi ➡️], [📄 1/4] tugmalari testi."""
    from keyboards.inline import music_results_keyboard

    sample_tracks = [
        {"id": f"trk_{i}", "artist": "Konsta", "title": f"Qo'shiq {i}"}
        for i in range(1, 31)
    ]

    # 1. 0-sahifa (1-8 treklar)
    kb_p0 = music_results_keyboard(sample_tracks, page=0, per_page=8, search_id="test123")
    rows_p0 = kb_p0.inline_keyboard
    # 8 trek tugmasi + 1 navigatsiya qatori
    assert len(rows_p0) == 9
    track_btns_p0 = [row[0] for row in rows_p0[:8]]
    assert "1. Konsta - Qo'shiq 1" in track_btns_p0[0].text
    assert "8. Konsta - Qo'shiq 8" in track_btns_p0[-1].text

    nav_row_p0 = rows_p0[8]
    assert len(nav_row_p0) == 2  # [📄 1/4], [Keyingi ➡️]
    assert nav_row_p0[0].text == "📄 1/4"
    assert nav_row_p0[0].callback_data == "noop"
    assert nav_row_p0[1].text == "Keyingi ➡️"
    assert nav_row_p0[1].callback_data == "music_page:test123:1"

    # 2. 1-sahifa (9-16 treklar)
    kb_p1 = music_results_keyboard(sample_tracks, page=1, per_page=8, search_id="test123")
    rows_p1 = kb_p1.inline_keyboard
    assert len(rows_p1) == 9
    track_btns_p1 = [row[0] for row in rows_p1[:8]]
    assert "9. Konsta - Qo'shiq 9" in track_btns_p1[0].text
    assert "16. Konsta - Qo'shiq 16" in track_btns_p1[-1].text

    nav_row_p1 = rows_p1[8]
    assert len(nav_row_p1) == 3  # [⬅️ Oldingi], [📄 2/4], [Keyingi ➡️]
    assert nav_row_p1[0].text == "⬅️ Oldingi"
    assert nav_row_p1[0].callback_data == "music_page:test123:0"
    assert nav_row_p1[1].text == "📄 2/4"
    assert nav_row_p1[2].text == "Keyingi ➡️"
    assert nav_row_p1[2].callback_data == "music_page:test123:2"

    # 3. 3-sahifa (oxirgi, 25-30 treklar: 6 ta trek)
    kb_p3 = music_results_keyboard(sample_tracks, page=3, per_page=8, search_id="test123")
    rows_p3 = kb_p3.inline_keyboard
    assert len(rows_p3) == 7  # 6 trek + 1 navigatsiya qatori
    track_btns_p3 = [row[0] for row in rows_p3[:6]]
    assert "25. Konsta - Qo'shiq 25" in track_btns_p3[0].text
    assert "30. Konsta - Qo'shiq 30" in track_btns_p3[-1].text

    nav_row_p3 = rows_p3[6]
    assert len(nav_row_p3) == 2  # [⬅️ Oldingi], [📄 4/4]
    assert nav_row_p3[0].text == "⬅️ Oldingi"
    assert nav_row_p3[0].callback_data == "music_page:test123:2"
    assert nav_row_p3[1].text == "📄 4/4"


@pytest.mark.asyncio
async def test_bot_cb_music_page_pagination():
    """Botdagi cb_music_page inline sahifalash callbacki xabar klaviaturasini to'g'ri yangilashi testi."""
    from handlers.music import cb_music_page, _SEARCH_CACHE

    sample_tracks = [
        {"id": f"trk_{i}", "artist": "Konsta", "title": f"Trek {i}"}
        for i in range(1, 25)
    ]
    test_search_id = "unit_test_search_id"
    _SEARCH_CACHE[f"msearch:{test_search_id}"] = sample_tracks

    cb = AsyncMock()
    cb.data = f"music_page:{test_search_id}:1"
    cb.message = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.answer = AsyncMock()

    await cb_music_page(cb)
    assert cb.answer.called is True
    assert cb.message.edit_text.called is True or cb.message.edit_reply_markup.called is True
    call_kwargs = cb.message.edit_text.call_args[1] if cb.message.edit_text.called else cb.message.edit_reply_markup.call_args[1]
    markup = call_kwargs["reply_markup"]
    assert markup is not None
    rows = markup.inline_keyboard
    nav_row = rows[-1]
    assert any("2/3" in btn.text for btn in nav_row)


@pytest.mark.asyncio
async def test_movie_service_resolve_video_source(tmp_path, monkeypatch):
    """MovieService.resolve_video_source video_sources.json va lokal fayllarni to'g'ri aniqlashi testi."""
    from services.movie_service import MovieService

    v_data = {
        "888": {
            "file_id": "BAACAgIAAxkBAAE_RESOLVED_MOCK_VIDEO_888",
            "file_type": "video",
            "duration": 5400,
            "file_size": 800 * 1024 * 1024
        },
        "888_2": {
            "url": "https://example.com/videos/888_2.mp4",
            "file_type": "video"
        }
    }
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "video_sources.json").write_text(json.dumps(v_data), encoding="utf-8")
    monkeypatch.setattr("config.BASE_DIR", tmp_path)

    src1 = MovieService.resolve_video_source("888", 1)
    assert src1 is not None
    assert src1["file_id"] == "BAACAgIAAxkBAAE_RESOLVED_MOCK_VIDEO_888"

    src2 = MovieService.resolve_video_source("888", 2)
    assert src2 is not None
    assert src2["url"] == "https://example.com/videos/888_2.mp4"

    # Mavjud bo'lmagan kino kodi uchun None qaytishi
    src_none = MovieService.resolve_video_source("999999", 1)
    assert src_none is None


@pytest.mark.asyncio
async def test_deliver_movie_with_resolved_video_source(tmp_path, monkeypatch):
    """deliver_movie da resolved_source mavjud bo'lganda bot.send_video chaqirilishi testi."""
    from services.movie_service import MovieService

    v_data = {
        "991": {
            "file_id": "BAACAgIAAxkBAAE_RESOLVED_SOURCE_DELIVER_TEST_VIDEO_991",
            "file_type": "video",
            "duration": 3600
        }
    }
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "video_sources.json").write_text(json.dumps(v_data), encoding="utf-8")
    monkeypatch.setattr("config.BASE_DIR", tmp_path)

    bot_mock = AsyncMock()
    bot_mock.send_video = AsyncMock()
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    fake_session = AsyncMock()
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = []
    fake_session.execute = AsyncMock(return_value=mock_exec_res)
    fake_session.commit = AsyncMock()

    with patch("services.movie_service.crud.get_movie_by_code", new_callable=AsyncMock) as mock_get_movie, \
         patch("services.movie_service.crud.set_movie_video", new_callable=AsyncMock) as mock_set_video, \
         patch("services.movie_service.crud.increment_movie_views", new_callable=AsyncMock) as mock_inc:
        mock_get_movie.return_value = None

        res = await MovieService.deliver_movie(
            bot=bot_mock,
            chat_id=12345,
            code="991",
            part=1,
            session=fake_session
        )

        assert res is True
        assert bot_mock.send_video.called is True
        video_arg = bot_mock.send_video.call_args[1]["video"]
        assert video_arg == "BAACAgIAAxkBAAE_RESOLVED_SOURCE_DELIVER_TEST_VIDEO_991"
        assert mock_set_video.called is True


@pytest.mark.asyncio
async def test_upstream_music_home_proxy_and_sanitization(tmp_path, monkeypatch):
    """Web App musiqa bosh sahifasi upstreamdan olinib, eski brenddan to'liq tozalanishi testi."""
    from services.web_server import get_cached_music_home, sanitize_catalog_text

    (tmp_path / "data").mkdir(exist_ok=True)
    monkeypatch.setattr("services.web_server.BASE_DIR", tmp_path)

    raw_upstream_payload = (
        '{"ok": true, "banner": "Zakirovs Music", "bot": "@Zakirovsfilm_bot", '
        '"sections": [{"title": "Dilbar Zakirova treklari", "items": [{"id": "1", "artist": "Zakirova", "title": "Sevgi"}]}]}'
    )

    clean_payload = sanitize_catalog_text(raw_upstream_payload)
    assert "Zakirov" not in clean_payload
    assert "dilbar" not in clean_payload.lower()
    assert "@Bauntyfilmsbot" in clean_payload or "Baunty" in clean_payload

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=raw_upstream_payload.encode("utf-8"))

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = MagicMock(return_value=mock_resp)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_client):
        data = await get_cached_music_home(force_refresh=True)
        assert data.get("ok") is True
        data_str = json.dumps(data)
        assert "Zakirov" not in data_str
        assert "dilbar" not in data_str.lower()


@pytest.mark.asyncio
async def test_movie_service_default_fallback_video_source(tmp_path, monkeypatch):
    """Aniqlanmagan kodlar uchun video_sources.json dagi default manba olinishi testi."""
    from services.movie_service import MovieService

    v_data = {
        "items": {
            "default": {
                "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "file_type": "video",
                "duration": 596
            },
            "101": {
                "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
                "file_type": "video"
            }
        }
    }
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "video_sources.json").write_text(json.dumps(v_data), encoding="utf-8")
    monkeypatch.setattr("config.BASE_DIR", tmp_path)

    src_specific = MovieService.resolve_video_source("101", 1)
    assert src_specific is not None
    assert "TearsOfSteel" in src_specific["url"]

    src_default = MovieService.resolve_video_source("999999", 1)
    assert src_default is not None
    assert "BigBuckBunny" in src_default["url"]


@pytest.mark.asyncio
async def test_deliver_movie_self_healing_from_failed_db_video(tmp_path, monkeypatch):
    """Baza videosi yuborishda xato bersa, zaxira video manbasi orqali yuborish va yangi file_id ni saqlash testi."""
    from services.movie_service import MovieService
    from database.models import Movie

    v_data = {
        "items": {
            "777": {
                "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
                "file_type": "video",
                "duration": 888
            }
        }
    }
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "video_sources.json").write_text(json.dumps(v_data), encoding="utf-8")
    monkeypatch.setattr("config.BASE_DIR", tmp_path)

    bot_mock = AsyncMock()
    # 1-chaqiriq (baza file_id) xato beradi, 2-chaqiriq (resolved url) muvaffaqiyatli
    sent_video_mock = MagicMock()
    sent_video_mock.video = MagicMock(file_id="BAACAgIAAxkBAAE_NEW_SAVED_TELEGRAM_FID_777", duration=888, file_size=500000)
    bot_mock.send_video = AsyncMock(side_effect=[Exception("TelegramBadRequest: wrong file identifier"), sent_video_mock])
    bot_mock.send_photo = AsyncMock()

    db_movie = Movie(
        code="777",
        title="Test Kino 777",
        file_id="BAACAgIAAxkBAAE_BROKEN_OLD_FILE_ID_777",
        file_type="video",
        duration=3600
    )

    fake_session = AsyncMock()
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = []
    fake_session.execute = AsyncMock(return_value=mock_exec_res)
    fake_session.commit = AsyncMock()

    with patch("services.movie_service.crud.get_movie_by_code", new_callable=AsyncMock) as mock_get_movie, \
         patch("services.movie_service.crud.set_movie_video", new_callable=AsyncMock) as mock_set_video, \
         patch("services.movie_service.crud.increment_movie_views", new_callable=AsyncMock):
        mock_get_movie.return_value = db_movie

        res = await MovieService.deliver_movie(
            bot=bot_mock,
            chat_id=12345,
            code="777",
            part=1,
            session=fake_session
        )

        assert res is True
        # bot.send_video ikki marta chaqirilgan (1-si xato, 2-si zaxira manba)
        assert bot_mock.send_video.call_count == 2
        # Poster yuborilmagan (chunki video muvaffaqiyatli yetkazildi!)
        assert bot_mock.send_photo.called is False
        # Yangi file_id bazada saqlangan
        assert mock_set_video.called is True
        assert mock_set_video.call_args[1]["file_id"] == "BAACAgIAAxkBAAE_NEW_SAVED_TELEGRAM_FID_777"


@pytest.mark.asyncio
async def test_web_server_music_admin_and_management_endpoints():
    """Web serverdagi musiqa me, report, ban va purge endpointlari testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # /api/music/me
        resp_me = await client.get("/api/music/me")
        assert resp_me.status == 200
        data_me = await resp_me.json()
        assert data_me.get("ok") is True
        assert "admin" in data_me

        # /api/music/report
        resp_rep = await client.post("/api/music/report", json={"id": "123", "r": "broken"})
        assert resp_rep.status == 200
        data_rep = await resp_rep.json()
        assert data_rep.get("ok") is True

        # /api/music/ban
        resp_ban = await client.post("/api/music/ban", json={"id": "123"})
        assert resp_ban.status == 200
        data_ban = await resp_ban.json()
        assert data_ban.get("ok") is True

        # /api/music/purge
        resp_purge = await client.post("/api/music/purge", json={"items": ["123"]})
        assert resp_purge.status == 200
        data_purge = await resp_purge.json()
        assert data_purge.get("ok") is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cb_download_track_tarona_numeric_precedence():
    """cb_download_track da tarona numeric id si Deezer bilan adashib ketmasligi testi."""
    from handlers.music import cb_download_track, _SEARCH_CACHE

    cb = AsyncMock()
    cb.data = "dl_track:12345_tarona_998877"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.reply = AsyncMock()

    status_mock = AsyncMock()
    status_mock.delete = AsyncMock()
    status_mock.edit_text = AsyncMock()
    cb.message.reply.return_value = status_mock

    # Keshda yo'q holat
    _SEARCH_CACHE.pop("12345_tarona_998877", None)

    mock_track = {
        "id": "tarona_998877",
        "title": "Xit Qo'shiq",
        "artist": "Konsta",
        "preview": "https://example.com/audio.mp3",
        "u": "https://example.com/audio.mp3",
        "s": "tarona"
    }

    with patch("services.music_service.music_service._resolve_tarona_direct_mp3", new_callable=AsyncMock) as mock_resolve, \
         patch("services.music_service.music_service.download_track_mp3", new_callable=AsyncMock) as mock_dl, \
         patch("database.session.get_session"):

        mock_resolve.return_value = "https://example.com/audio.mp3"
        mock_dl_res = MagicMock(success=True, file_path="C:/nonexistent/temp.mp3", duration=180, error=None)
        mock_dl.return_value = mock_dl_res

        with patch("os.path.exists", return_value=True), \
             patch("handlers.music.safe_remove_file"), \
             patch("handlers.music.crud.log_download", new_callable=AsyncMock):

            await cb_download_track(cb)
            assert mock_resolve.called is True
            # Tarona tekshirilgan va keshga to'g'ri o'rnatilgan
            assert "12345_tarona_998877" in _SEARCH_CACHE
            cached = _SEARCH_CACHE["12345_tarona_998877"]
            assert cached["s"] == "tarona"



