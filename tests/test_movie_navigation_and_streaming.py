"""
Tests for Milestone M1: Series/Episode Navigation, Watched Tracking, and 410 Token Streaming Fix.
"""
import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base, UserWatchProgress
from database import crud
from keyboards.inline import movie_parts_keyboard
from services.asilmedia_service import (
    AsilmediaService,
    asilmedia_service,
    strip_fayllar_token,
    needs_fayllar_sign,
)
from services.movie_service import MovieService
from handlers.movies import cb_parts_page, cb_watch_part, cb_get_movie_by_code


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite testi uchun alohida session fixture."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


# ==============================================================================
# 1. EPISODE KEYBOARD 5-COLUMN GRID & RANGE PAGINATION PILLS TESTS
# ==============================================================================

def test_movie_parts_keyboard_5_columns_and_50_per_page():
    """139 qismli serial uchun 50 tadan sahifalash va 5 ustunli tugmalar to'plami testi."""
    code = "1390"
    total_parts = 139

    # Page 0: 1 dan 50 gacha
    kb_p0 = movie_parts_keyboard(code, total_parts=total_parts, current_part=1, page=0, per_page=50)
    buttons_p0 = [btn for row in kb_p0.inline_keyboard for btn in row]
    part_buttons_p0 = [
        b for b in buttons_p0
        if b.callback_data and b.callback_data.startswith(f"watch_part:{code}:")
        and not b.text.startswith("Davom") and not b.text.startswith("Qayta")
    ]

    # Aynan 50 ta qism tugmasi bo'lishi kerak
    assert len(part_buttons_p0) == 50
    assert part_buttons_p0[0].text == "▶️ 1"
    assert part_buttons_p0[-1].text == "50"

    # Har bir qatorda maksimal 5 ta tugma bo'lishi kerak (5 ustun)
    for row in kb_p0.inline_keyboard:
        row_parts = [
            b for b in row
            if b.callback_data and b.callback_data.startswith(f"watch_part:{code}:")
            and not b.text.startswith("Davom") and not b.text.startswith("Qayta")
        ]
        if row_parts:
            assert len(row_parts) <= 5

    # In-place range pagination pills: [ • 1–50 ], [ 51–100 ], [ 101–139 ]
    pill_buttons_p0 = [b for b in buttons_p0 if b.callback_data and b.callback_data.startswith(f"parts_page:{code}:")]
    assert len(pill_buttons_p0) == 3
    assert pill_buttons_p0[0].text == "• 1–50"
    assert pill_buttons_p0[0].callback_data == f"parts_page:{code}:0"
    assert pill_buttons_p0[1].text == "51–100"
    assert pill_buttons_p0[1].callback_data == f"parts_page:{code}:1"
    assert pill_buttons_p0[2].text == "101–139"
    assert pill_buttons_p0[2].callback_data == f"parts_page:{code}:2"

    # Page 1: 51 dan 100 gacha
    kb_p1 = movie_parts_keyboard(code, total_parts=total_parts, current_part=55, page=1, per_page=50)
    buttons_p1 = [btn for row in kb_p1.inline_keyboard for btn in row]
    part_buttons_p1 = [
        b for b in buttons_p1
        if b.callback_data and b.callback_data.startswith(f"watch_part:{code}:")
        and not b.text.startswith("Davom") and not b.text.startswith("Qayta")
    ]
    assert len(part_buttons_p1) == 50
    assert part_buttons_p1[0].text == "51"
    assert part_buttons_p1[4].text == "▶️ 55"
    assert part_buttons_p1[-1].text == "100"

    pill_buttons_p1 = [b for b in buttons_p1 if b.callback_data and b.callback_data.startswith(f"parts_page:{code}:")]
    assert pill_buttons_p1[0].text == "1–50"
    assert pill_buttons_p1[1].text == "• 51–100"
    assert pill_buttons_p1[2].text == "101–139"

    # Page 2 (oxirgi sahifa): 101 dan 139 gacha (39 ta qism)
    kb_p2 = movie_parts_keyboard(code, total_parts=total_parts, current_part=130, page=2, per_page=50)
    buttons_p2 = [btn for row in kb_p2.inline_keyboard for btn in row]
    part_buttons_p2 = [
        b for b in buttons_p2
        if b.callback_data and b.callback_data.startswith(f"watch_part:{code}:")
        and not b.text.startswith("Davom") and not b.text.startswith("Qayta")
    ]
    assert len(part_buttons_p2) == 39
    assert part_buttons_p2[0].text == "101"
    assert part_buttons_p2[-1].text == "139"

    pill_buttons_p2 = [b for b in buttons_p2 if b.callback_data and b.callback_data.startswith(f"parts_page:{code}:")]
    assert pill_buttons_p2[0].text == "1–50"
    assert pill_buttons_p2[1].text == "51–100"
    assert pill_buttons_p2[2].text == "• 101–139"

    # Telegram 64 bayt callback cheklovi tekshiruvi
    for btn in buttons_p0 + buttons_p1 + buttons_p2:
        if btn.callback_data:
            assert len(btn.callback_data.encode("utf-8")) <= 64


def test_movie_parts_keyboard_watched_indicators_and_next_episode():
    """Ko'rilgan qismlarda ✓ belgisi va birinchi ko'rilmagan qismga 'Davom ettirish' tugmasi testi."""
    code = "555"
    total_parts = 10
    watched = {1, 2, 3}

    # Current part 4, watched 1, 2, 3
    kb = movie_parts_keyboard(
        code,
        total_parts=total_parts,
        current_part=4,
        watched_parts=watched,
        per_page=50
    )
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    grid_buttons = [
        b for b in buttons
        if b.callback_data and b.callback_data.startswith(f"watch_part:{code}:")
        and not b.text.startswith("Davom") and not b.text.startswith("Qayta")
    ]

    # Qismlar tugmalari tekshiruvi
    b1 = [b for b in grid_buttons if b.callback_data == f"watch_part:{code}:1"][0]
    b2 = [b for b in grid_buttons if b.callback_data == f"watch_part:{code}:2"][0]
    b3 = [b for b in grid_buttons if b.callback_data == f"watch_part:{code}:3"][0]
    b4 = [b for b in grid_buttons if b.callback_data == f"watch_part:{code}:4"][0]
    b5 = [b for b in grid_buttons if b.callback_data == f"watch_part:{code}:5"][0]

    assert b1.text == "✓ 1"
    assert b2.text == "✓ 2"
    assert b3.text == "✓ 3"
    assert b4.text == "▶️ 4"
    assert b5.text == "5"

    # Yuqoridagi shortcut tugma: Davom ettirish: 4-qism (chunki 4 hali ko'rilmagan)
    top_btn = kb.inline_keyboard[0][0]
    assert "Davom ettirish: 4-qism" in top_btn.text
    assert top_btn.callback_data == f"watch_part:{code}:4"

    # Barcha qismlar ko'rilgan holat (1 dan 10 gacha)
    all_watched = set(range(1, 11))
    kb_all = movie_parts_keyboard(
        code,
        total_parts=total_parts,
        current_part=10,
        watched_parts=all_watched,
        per_page=50
    )
    top_btn_all = kb_all.inline_keyboard[0][0]
    assert "Qayta ko'rish: 1-qism" in top_btn_all.text
    assert top_btn_all.callback_data == f"watch_part:{code}:1"

    # Katalogda ochish WebApp tugmasi
    webapp_btns = [b for b in buttons if b.web_app is not None or "Katalogda ochish" in b.text]
    assert len(webapp_btns) >= 1
    if webapp_btns[0].web_app:
        assert f"c={code}" in webapp_btns[0].web_app.url


# ==============================================================================
# 2. WATCH PROGRESS DATABASE MODEL & CRUD TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_user_watch_progress_crud(db_session: AsyncSession):
    """UserWatchProgress model va CRUD funksiyalari (record / get) testi."""
    user_id = 123456789
    movie_code = "777"

    # Dastlab foydalanuvchi hech qanday qism ko'rmagan
    watched = await crud.get_user_watched_episodes(db_session, user_id, movie_code)
    assert watched == set()

    # 1 va 2-qismlarni ko'rish
    await crud.record_user_watched_episode(db_session, user_id, movie_code, part=1)
    await crud.record_user_watched_episode(db_session, user_id, movie_code, part=2)

    watched = await crud.get_user_watched_episodes(db_session, user_id, movie_code)
    assert watched == {1, 2}

    # Takroriy ko'rish (idempotentlik testi - xatolik bermasligi kerak)
    await crud.record_user_watched_episode(db_session, user_id, movie_code, part=1)
    watched_after = await crud.get_user_watched_episodes(db_session, user_id, movie_code)
    assert watched_after == {1, 2}

    # 3-qism qo'shish
    await crud.record_user_watched_episode(db_session, user_id, movie_code, part=3)
    watched_3 = await crud.get_user_watched_episodes(db_session, user_id, movie_code)
    assert watched_3 == {1, 2, 3}

    # Boshqa foydalanuvchi ma'lumotlari alohidaligi
    other_user_id = 987654321
    other_watched = await crud.get_user_watched_episodes(db_session, other_user_id, movie_code)
    assert other_watched == set()


# ==============================================================================
# 3. STREAM TOKEN EXPIRATION & STRIP & SIGN TESTS
# ==============================================================================

def test_strip_fayllar_token():
    """Fayllar havolasidan token va expires parametrlarini toza olib tashlash testi."""
    url1 = "https://30.fayllar.com/17638/1-qism.mp4?token=abc123xyz&expires=1731600000"
    clean1 = strip_fayllar_token(url1)
    assert clean1 == "https://30.fayllar.com/17638/1-qism.mp4"

    url2 = "https://30.fayllar1.ru/kino/video.mp4?token=def456"
    clean2 = strip_fayllar_token(url2)
    assert clean2 == "https://30.fayllar1.ru/kino/video.mp4"

    # Token bo'lmagan havolaga tegilmasligi kerak
    url3 = "https://30.fayllar.com/17638/1-qism.mp4"
    clean3 = strip_fayllar_token(url3)
    assert clean3 == url3


def test_needs_fayllar_sign_expiration_and_force():
    """needs_fayllar_sign token muddati o'tganida yoki force=True bo'lganda True qaytarishi testi."""
    # am:... har doim imzo talab qiladi
    assert needs_fayllar_sign("am:17638:hash123") is True

    # Tokensiz fayllar URL imzo talab qiladi
    unsigned = "https://30.fayllar.com/17638/1-qism.mp4"
    assert needs_fayllar_sign(unsigned) is True

    # Amaldagi tokeni bor havola (kelajakdagi expires)
    future_ts = int(time.time()) + 3600
    valid_signed = f"https://30.fayllar.com/17638/1-qism.mp4?token=good123&expires={future_ts}"
    assert needs_fayllar_sign(valid_signed, force=False) is False

    # force=True bo'lganda hatto amaldagi token bo'lsa ham imzo talab qiladi
    assert needs_fayllar_sign(valid_signed, force=True) is True

    # Muddati o'tgan token (o'tmishdagi expires)
    past_ts = int(time.time()) - 300
    expired_signed = f"https://30.fayllar.com/17638/1-qism.mp4?token=expired123&expires={past_ts}"
    assert needs_fayllar_sign(expired_signed, force=False) is True


@pytest.mark.asyncio
async def test_resolve_stream_url_force_refresh_strips_token():
    """resolve_stream_url force_refresh=True da eskirgan tokenni tozalab yangi imzo olishi testi."""
    svc = AsilmediaService()
    expired_url = "https://30.fayllar.com/17638/1-qism.mp4?token=old_expired_token&expires=1700000000"

    async def fake_sign(urls, amh_id=None, amh_n=None, force=False):
        # Stripped url kelishi kerak
        assert "token=" not in urls[0]
        return {urls[0]: "https://30.fayllar.com/17638/1-qism.mp4?token=fresh_new_token&expires=1800000000"}

    with patch.object(svc, "sign_fayllar_urls", side_effect=fake_sign):
        fresh = await svc.resolve_stream_url(expired_url, news_id="17638", force_refresh=True)

    assert fresh is not None
    assert "token=fresh_new_token" in fresh


# ==============================================================================
# 4. 410 GONE RECOVERY IN DOWNLOAD_VIDEO_STREAM
# ==============================================================================

@pytest.mark.asyncio
async def test_download_video_stream_410_token_refresh(tmp_path):
    """download_video_stream HTTP 410 olganida eskirgan tokenni yangilab qayta urinishi testi."""
    svc = AsilmediaService()
    future_ts = int(time.time()) + 3600
    expired_url = f"https://30.fayllar.com/17638/1-qism.mp4?token=revoked_token&expires={future_ts}"
    fresh_url = "https://30.fayllar.com/17638/1-qism.mp4?token=fresh_refreshed&expires=1800000000"
    dest = tmp_path / "video.mp4"

    # Birinchi so'rovda 410 Gone (serverda bekor qilingan), ikkinchisida (fresh_url) 200 OK
    call_count = 0

    class FakeResponse:
        def __init__(self, status, url):
            self.status = status
            self.headers = {"Content-Type": "video/mp4", "Content-Length": "2048"}

            async def fake_iter(chunk_size):
                yield b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00" + b"A" * 2000

            content_mock = MagicMock()
            content_mock.iter_chunked = fake_iter
            self.content = content_mock

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_get(url, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if "token=revoked_token" in url:
            return FakeResponse(410, url)
        else:
            return FakeResponse(200, url)

    with patch.object(svc, "resolve_stream_url", return_value=fresh_url) as mock_resolve, \
         patch("aiohttp.ClientSession.get", side_effect=mock_get):
        result = await svc.download_video_stream(expired_url, destination_path=dest)

    assert result is not None
    assert result.exists()
    assert call_count == 2
    mock_resolve.assert_called_once()


# ==============================================================================
# 5. CONCISE MOVIE CARD CAPTION FORMAT TEST
# ==============================================================================

def test_format_concise_movie_caption():
    """Qisqa va ixcham kino kartochkasi formati tekshiruvi:
    {Title}\n{Year} · {Duration} · {Language} · {Genres} · IMDb: {Rating} · Kod: {Code}
    """
    caption = MovieService.format_concise_movie_caption(
        title="Qasoskorlar: Intiho",
        year=2019,
        duration=10800,  # 180 daqiqa
        language="O'zbek tilida",
        genres="Fantastika, Jangari",
        rating=8.4,
        code="101",
        part=1
    )
    lines = caption.split("\n")
    assert len(lines) == 2
    assert lines[0] == "Qasoskorlar: Intiho"
    assert lines[1] == "2019 · 180 daqiqa · O'zbek tilida · Fantastika, Jangari · IMDb: 8.4 · Kod: 101"

    # Ko'p qismli serial qismi formati
    caption_part = MovieService.format_concise_movie_caption(
        title="Wednesday",
        year=2022,
        duration=3000,  # 50 daqiqa
        language="O'zbek tilida",
        genres="Komediya, Fantastika",
        rating=8.1,
        code="202",
        part=3
    )
    lines_part = caption_part.split("\n")
    assert lines_part[0] == "Wednesday (3-qism)"
    assert lines_part[1] == "2022 · 50 daqiqa · O'zbek tilida · Komediya, Fantastika · IMDb: 8.1 · Kod: 202"


# ==============================================================================
# 6. WEB SERVER HANDLE_ASIL_STREAM 410 TOKEN REFRESH TEST
# ==============================================================================

@pytest.mark.asyncio
async def test_handle_asil_stream_410_re_resolves():
    """handle_asil_stream endpoint eskirgan fayllar tokenni yangilab qayta yo'naltirishi (HTTPFound) testi."""
    from services.web_server import handle_asil_stream
    from aiohttp.test_utils import make_mocked_request

    req = make_mocked_request(
        "GET",
        "/api/asil/stream?id=17638&part=1&quality=1080p",
        headers={"Host": "localhost"}
    )

    expired_url = "https://30.fayllar.com/17638/1-qism.mp4?token=old_token&expires=1700000000"
    refreshed_url = "https://30.fayllar.com/17638/1-qism.mp4?token=new_fresh_token&expires=1900000000"

    fake_stream_info = {
        "title": "Test Film",
        "quality_urls": {"1080p": expired_url},
        "stream_url": expired_url
    }

    with patch.object(MovieService, "get_movie_stream_info", return_value=fake_stream_info), \
         patch.object(asilmedia_service, "resolve_stream_url", return_value=refreshed_url) as mock_resolve:
        with pytest.raises(web.HTTPFound) as exc_info:
            await handle_asil_stream(req)

    assert exc_info.value.location == refreshed_url
    mock_resolve.assert_called_once()


# ==============================================================================
# 7. CB_PARTS_PAGE IN-PLACE REPLY MARKUP EDITING TEST
# ==============================================================================

@pytest.mark.asyncio
async def test_cb_parts_page_in_place_edit():
    """cb_parts_page callback reply_markup ni o'z joyida tahrirlashi (in-place) testi."""
    callback = AsyncMock()
    callback.data = "parts_page:999:1"
    callback.from_user.id = 555666
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()

    cat_item = {"t": "Serial Test", "p": 120}

    with patch.object(MovieService, "get_catalog_item", return_value=cat_item), \
         patch.object(crud, "get_user_watched_episodes", return_value={1, 2, 3}) as mock_watched:
        await cb_parts_page(callback)

    callback.message.edit_reply_markup.assert_called_once()
    called_markup = callback.message.edit_reply_markup.call_args[1]["reply_markup"]
    assert called_markup is not None
    # Qismlar 51 dan 100 gacha bo'lishi kerak
    btn_texts = [b.text for row in called_markup.inline_keyboard for b in row]
    assert "51" in btn_texts
    assert "100" in btn_texts
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_send_movie_delivery_fallback_deleted_reply_message_retries():
    """_send_movie_delivery_fallback deleted parent message (message to be replied not found) retries with reply_to_message_id=None."""
    from handlers.movies import _send_movie_delivery_fallback
    from aiogram.exceptions import TelegramBadRequest

    mock_bot = AsyncMock()
    bad_req_err = TelegramBadRequest(method=MagicMock(), message="Bad Request: message to be replied not found")
    mock_bot.send_message.side_effect = [bad_req_err, AsyncMock()]

    # Case 1: not found branch
    with patch.object(MovieService, "get_catalog_item", return_value=None), \
         patch.object(MovieService, "get_movie_stream_info", return_value=None):
        await _send_movie_delivery_fallback(
            bot=mock_bot,
            chat_id=12345,
            code="nonexistent_code_99999",
            part=1,
            reply_to_message_id=999,
            session=None,
        )
    assert mock_bot.send_message.call_count == 2
    assert mock_bot.send_message.call_args_list[1][1]["reply_to_message_id"] is None

    # Case 2: fallback stream/webapp buttons branch
    mock_bot.send_message.reset_mock()
    mock_bot.send_message.side_effect = [bad_req_err, AsyncMock()]
    mock_cat_item = {"t": "Some Movie", "p": 1}
    with patch.object(MovieService, "get_catalog_item", return_value=mock_cat_item), \
         patch.object(MovieService, "get_movie_stream_info", return_value={"title": "Some Movie", "stream_url": "https://example.com/stream.mp4"}):
        await _send_movie_delivery_fallback(
            bot=mock_bot,
            chat_id=12345,
            code="100",
            part=1,
            reply_to_message_id=999,
            session=None,
        )
    assert mock_bot.send_message.call_count == 2
    assert mock_bot.send_message.call_args_list[1][1]["reply_to_message_id"] is None

