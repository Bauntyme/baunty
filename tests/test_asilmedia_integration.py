"""
Asilmedia.org integratsiyasi, video manbalari, qismlar va deliver_movie testlari.
100% Bauntys oq brendi: @Bauntyfilmsbot va @BauntyFilms.
"""
import json
import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, Chat, User as TgUser
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import config, BASE_DIR
from database import crud
from database.session import get_session
from database.models import Base, Movie
from services.asilmedia_service import (
    asilmedia_service,
    AsilmediaService,
    AsilmediaMovie,
    AsilmediaEpisode,
)
from services.movie_service import movie_service, MovieService


@pytest_asyncio.fixture
async def in_memory_session():
    """In-memory SQLite testi uchun alohida session fixture."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


SAMPLE_SINGLE_MOVIE_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <title>Taksi 1 / Taxi 1 Uzbek tilida 1998 O'zbekcha tarjima kino Full HD tas-ix skachat</title>
</head>
<body>
  <div class="fs-hero">
    <div class="fs-poster">
      <img src="/rasmlar/taksi1.webp" alt="Taksi 1">
    </div>
    <div class="fs-info">
      <h1 class="fs-title">Taksi 1 / Taxi 1 Uzbek tilida 1998 O'zbekcha tarjima kino</h1>
      <div class="fs-year-info">
        <a href="/xfsearch/year/1998/">1998</a>
      </div>
      <div class="fs-tags">
        <a href="/xfsearch/genre/komediya/">Komediya (комедия)</a>,
        <a href="/xfsearch/genre/jangari/">Jangari (боевик)</a>
      </div>
      <div class="fs-description">Marsellik tezkor taksichi Daniel sarguzashtlari.</div>
    </div>
  </div>

  <div class="fs-player">
    <iframe data-player-src="https://fayllar.com/9/Taksi 1 480p O'zbek tilida (asilmedia.net).mp4"></iframe>
  </div>

  <div id="tg-data" hidden>
kino_url1=480p=https://server.asilmedia.org/watch/4310693215/24996
kino_url2=720p=https://server.asilmedia.org/watch/4310693215/25011
kino_url3=1080p=https://server.asilmedia.org/watch/4310693215/25014
  </div>
</body>
</html>
"""

SAMPLE_SERIES_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <title>Taksi 1 2 3 4 5 Barcha qismlar Uzbek tilida Full HD tas-ix skachat</title>
</head>
<body>
  <h1 class="fs-title">Taksi 1 2 3 4 5 Barcha qismlar Uzbek tilida</h1>
  <div class="fs-description">Barcha Taksi filmlari to'plami.</div>

  <div id="episodes-raw-data" style="display:none">
    <a href="https://fayllar.com/30/Taksi/Taksi 1 1080p (asilmedia.net).mp4" data-label="1-qism 1080p">1</a>
    <a href="https://fayllar.com/30/Taksi/Taksi 2 1080p (asilmedia.net).mp4" data-label="2-qism 1080p">2</a>
    <a href="https://fayllar.com/30/Taksi/Taksi 3 1080p (asilmedia.net).mp4" data-label="3-qism 1080p">3</a>
    <a href="https://fayllar.com/30/Taksi/Taksi 4 1080p (asilmedia.net).mp4" data-label="4-qism 1080p">4</a>
    <a href="https://fayllar.com/30/Taksi/Taksi 5 1080p (asilmedia.net).mp4" data-label="5-qism 1080p">5</a>
  </div>

  <div id="tg-data" hidden>
kino_url1=720p Taksi-1 / HD=https://server.asilmedia.org/watch/4310693215/31871
kino_url2=720p Taksi-2 / HD=https://server.asilmedia.org/watch/4310693215/31874
kino_url3=720p Taksi-3 / HD=https://server.asilmedia.org/watch/4310693215/31875
kino_url4=1080p Taksi-4 / HD=https://server.asilmedia.org/watch/4310693215/31873
kino_url5=480p Taksi-5 / HD=https://server.asilmedia.org/watch/4310693215/37884
  </div>
</body>
</html>
"""

SAMPLE_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<body>
  <div class="card">
    <a href="https://asilmedia.org/9165-taksi-1-2-3-4-5-barcha-qismlar-uzbek-tilida-uzbekcha-tarjima-kino-tas-ix.html" class="card__link">
      <h3 class="card__title" itemprop="name">Taksi 1 2 3 4 5 Barcha qismlar Uzbek tilida</h3>
      <img src="/rasmlar/taksi.jpg" alt="Taksi 1 2 3 4 5">
    </a>
  </div>
  <div class="card">
    <a href="https://asilmedia.org/11126-taksi-1-taxi-1-uzbek-tilida-1998-ozbekcha-tarjima-kino-hd.html" class="card__link">
      <h3 class="card__title" itemprop="name">Taksi 1 / Taxi 1 Uzbek tilida 1998</h3>
    </a>
  </div>
</body>
</html>
"""


def test_asilmedia_clean_title():
    """clean_title texnik so'zlar va reklamalarni tozalashi kerak."""
    raw = "Taksi 1 / Taxi 1 Uzbek tilida 1998 O'zbekcha tarjima kino Full HD tas-ix skachat"
    cleaned = asilmedia_service.clean_title(raw)
    assert "Taksi 1" in cleaned
    assert "tas-ix" not in cleaned.lower()
    assert "skachat" not in cleaned.lower()


def test_asilmedia_parse_episode_label():
    """Turli qism sarlavhalaridan fasl, qism va sifatni ajratib olish testi."""
    s, ep, q = asilmedia_service.parse_episode_label("1-fasl 1-qism 1080p")
    assert (s, ep, q) == (1, 1, "1080p")

    s, ep, q = asilmedia_service.parse_episode_label("4-fasl 5-qism 480p")
    assert (s, ep, q) == (4, 5, "480p")

    s, ep, q = asilmedia_service.parse_episode_label("720p Taksi-2 / HD")
    assert (s, ep, q) == (1, 2, "720p")

    s, ep, q = asilmedia_service.parse_episode_label("12-qism Full HD")
    assert (s, ep, q) == (1, 12, "1080p")


def test_asilmedia_extract_sources_from_html_single_movie():
    """Bitta qismli kino HTML sahifasidan sifatlar va video oqimini ajratish testi."""
    movie = asilmedia_service.extract_sources_from_html(
        SAMPLE_SINGLE_MOVIE_HTML,
        page_url="https://asilmedia.org/11126-taksi-1.html"
    )
    assert movie is not None
    assert movie.id == "11126"
    assert "Taksi 1" in movie.title
    assert movie.year == 1998
    assert "Komediya" in movie.genres
    assert movie.total_parts == 1
    assert 1 in movie.episodes
    ep1 = movie.episodes[1]
    assert "server.asilmedia.org" in ep1.url or "fayllar.com" in ep1.url
    assert "1080p" in movie.video_sources or "480p" in movie.video_sources


def test_asilmedia_extract_sources_from_html_series():
    """Ko'p qismli serial/to'plam HTML sahifasidan barcha qismlarni ajratish testi."""
    movie = asilmedia_service.extract_sources_from_html(
        SAMPLE_SERIES_HTML,
        page_url="https://asilmedia.org/9165-taksi-barcha-qismlar.html"
    )
    assert movie is not None
    assert movie.id == "9165"
    assert movie.total_parts == 5
    assert movie.is_series is True
    assert len(movie.episodes) == 5

    for p in range(1, 6):
        assert p in movie.episodes
        ep = movie.episodes[p]
        assert ep.part == p
        assert ep.url.startswith("http")
        assert ep.download_url is not None


@pytest.mark.asyncio
async def test_asilmedia_search_mocked():
    """Asilmedia qidiruv so'rovi va parsing testi (mock orqali)."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=SAMPLE_SEARCH_HTML)

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_resp
        results = await asilmedia_service.search("Taksi", limit=5)
        assert len(results) >= 2
        assert any(r["id"] == "9165" for r in results)
        assert any(r["id"] == "11126" for r in results)


@pytest.mark.asyncio
async def test_asilmedia_get_movie_details_and_caching():
    """get_movie_details natijasi va keshlash mexanizmi testi."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=SAMPLE_SERIES_HTML)

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_resp
        url = "https://asilmedia.org/9165-test.html"
        details1 = await asilmedia_service.get_movie_details(url)
        assert details1 is not None
        assert details1.total_parts == 5

        # Ikkinchi chaqiruv keshdan kelishi kerak (ClientSession chaqirilmasligi)
        mock_get.reset_mock()
        details2 = await asilmedia_service.get_movie_details(url)
        assert details2 is not None
        assert details2.total_parts == 5
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_asilmedia_download_video_stream(tmp_path):
    """Videoni oqim shaklida xavfsiz yuklab olish testi."""
    dest = tmp_path / "test_movie.mp4"

    # Mock chunk generator
    async def mock_iter(chunk_size):
        yield b"MP4_HEADER_MOCK_DATA" * 100
        yield b"MP4_BODY_MOCK_DATA" * 100

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {"Content-Length": "3800"}
    mock_resp.content.iter_chunked = mock_iter

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_resp
        saved = await asilmedia_service.download_video_stream(
            url="https://sample.com/video.mp4",
            destination_path=dest,
            max_bytes=1024 * 1024
        )
        assert saved is not None
        assert saved.exists()
        assert saved.stat().st_size > 1000


@pytest.mark.asyncio
async def test_movie_service_sync_movie_from_asilmedia(in_memory_session, tmp_path, monkeypatch):
    """movie_service.sync_movie_from_asilmedia Asilmediadan qismlarni bog'lashi testi."""
    # Test uchun video_sources.json faylini tmp_path ga yo'naltirish
    test_sources = tmp_path / "video_sources.json"
    monkeypatch.setattr("config.BASE_DIR", tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    real_sources_path = tmp_path / "data" / "video_sources.json"
    with open(real_sources_path, "w", encoding="utf-8") as f:
        json.dump({"items": {}}, f)

    # Mock asilmedia_service.find_best_match
    mock_movie = asilmedia_service.extract_sources_from_html(
        SAMPLE_SERIES_HTML,
        page_url="https://asilmedia.org/9165-taksi-barcha-qismlar.html"
    )

    with patch.object(asilmedia_service, "find_best_match", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = mock_movie
        res = await MovieService.sync_movie_from_asilmedia(
            code="999",
            title="Taksi",
            session=in_memory_session
        )
        assert res["success"] is True
        assert res["code"] == "999"
        assert res["total_parts"] == 5
        assert len(res["synced_parts"]) == 5

        # video_sources.json tekshiruvi
        src = MovieService.resolve_video_source("999", part=2, allow_default=False)
        assert src is not None
        assert "server.asilmedia.org" in src["url"] or "fayllar.com" in src["url"]

        # DB tekshiruvi
        db_p1 = await crud.get_movie_by_code(in_memory_session, "999")
        db_p2 = await crud.get_movie_by_code(in_memory_session, "999_2")
        assert db_p1 is not None
        assert db_p2 is not None


@pytest.mark.asyncio
async def test_movie_service_download_movie_from_asilmedia(tmp_path, monkeypatch):
    """movie_service.download_movie_from_asilmedia lokal fayl yaratishi va bog'lashi testi."""
    v_dir = tmp_path / "data" / "videos"
    v_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    sources_path = tmp_path / "data" / "video_sources.json"
    with open(sources_path, "w", encoding="utf-8") as f:
        json.dump({"items": {"888": {"url": "https://sample.com/888.mp4", "file_type": "video"}}}, f)

    monkeypatch.setattr("config.BASE_DIR", tmp_path)

    fake_file = v_dir / "888_1.mp4"
    with open(fake_file, "wb") as f:
        f.write(b"MOCK_DOWNLOADED_VIDEO_BYTES_1234567890" * 50)

    with patch.object(asilmedia_service, "download_video_stream", new_callable=AsyncMock) as mock_down:
        mock_down.return_value = fake_file
        saved = await MovieService.download_movie_from_asilmedia("888", part=1, destination_dir=v_dir)
        assert saved is not None
        assert saved.exists()
        assert saved.name == "888_1.mp4"


@pytest.mark.asyncio
async def test_deliver_movie_with_asilmedia_source(in_memory_session, tmp_path, monkeypatch):
    """deliver_movie Asilmedia manbasi orqali videoni bot.send_video da jo'natishi va file_id ni saqlashi testi."""
    bot = AsyncMock()
    mock_sent = MagicMock()
    mock_sent.video.file_id = "BAACAgIAAxkBAAE_ASILMEDIA_REAL_FILE_ID_1234567890"
    mock_sent.video.duration = 120
    mock_sent.video.file_size = 15000000
    mock_sent.document = None
    bot.send_video.return_value = mock_sent

    # video_sources.json da Asilmedia manbasi bo'lgan kino
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    sources_path = tmp_path / "data" / "video_sources.json"
    with open(sources_path, "w", encoding="utf-8") as f:
        json.dump({
            "items": {
                "777": {
                    "url": "https://server.asilmedia.org/download/4310693215/12345",
                    "file_type": "video",
                    "source": "asilmedia"
                }
            }
        }, f)

    monkeypatch.setattr("config.BASE_DIR", tmp_path)

    res = await MovieService.deliver_movie(
        bot=bot,
        chat_id=12345678,
        code="777",
        part=1,
        session=in_memory_session
    )

    assert res is True
    bot.send_video.assert_called_once()
    _, kwargs = bot.send_video.call_args
    assert kwargs.get("supports_streaming") is True
    assert "@Bauntyfilmsbot" in kwargs.get("caption")
    assert "@BauntyFilms" in kwargs.get("caption")

    # DB ga yangi file_id saqlanganligini tekshirish
    db_m = await crud.get_movie_by_code(in_memory_session, "777")
    assert db_m is not None
    assert db_m.file_id == "BAACAgIAAxkBAAE_ASILMEDIA_REAL_FILE_ID_1234567890"


@pytest.mark.asyncio
async def test_admin_sync_asilmedia_command():
    """Admin /sync_asilmedia buyrug'i testi."""
    from handlers.admin import cmd_sync_asilmedia

    msg = AsyncMock(spec=Message)
    msg.text = "/sync_asilmedia 718 Taksi"
    admin_id = config.admin_ids[0] if config.admin_ids else 7271080503
    msg.from_user = TgUser(id=admin_id, is_bot=False, first_name="Admin")
    status_mock = AsyncMock()
    msg.reply = AsyncMock(return_value=status_mock)

    with patch.object(movie_service, "sync_movie_from_asilmedia", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = {
            "success": True,
            "title": "Taksi 1 2 3 4 5",
            "synced_parts": [1, 2, 3, 4, 5]
        }
        await cmd_sync_asilmedia(msg)
        mock_sync.assert_called_once()
        status_mock.edit_text.assert_called_once()
        sent_text = status_mock.edit_text.call_args[0][0]
        assert "muvaffaqiyatli bog'landi" in sent_text
        assert "5 ta qism" in sent_text


@pytest.mark.asyncio
async def test_white_label_branding_asilmedia():
    """Asilmedia xizmatida va xabarlarida 100% Bauntys brendi qo'llanilishi testi."""
    bot_clean = config.BOT_USERNAME.lstrip("@")
    channel_clean = config.CHANNEL_USERNAME.lstrip("@")

    assert bot_clean == "Bauntyfilmsbot"
    assert channel_clean == "BauntyFilms"

    # sanitize_branding testi
    raw_desc = "Kino @Zakirovsfilms_bot va @ZakirovsKino tomonidan tayyorlandi"
    cleaned = MovieService.sanitize_branding(raw_desc)
    assert "@Bauntyfilmsbot" in cleaned
    assert "@BauntyFilms" in cleaned
    assert "Zakirov" not in cleaned


@pytest.mark.asyncio
async def test_asilmedia_download_video_stream_rejects_html(tmp_path):
    """HTML yoki xato javoblarni video sifatida saqlamaslik testi."""
    dest = tmp_path / "corrupted.mp4"

    # 1. Content-Type: text/html bo'lganda
    mock_resp1 = AsyncMock()
    mock_resp1.status = 200
    mock_resp1.headers = {"Content-Type": "text/html; charset=utf-8"}
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_resp1
        res1 = await asilmedia_service.download_video_stream("https://server.asilmedia.org/download/1/2", dest)
        assert res1 is None
        assert not dest.exists()

    # 2. Content-Type berilmagan, lekin birinchi chunk HTML teglari bo'lganda
    async def mock_html_chunks(chunk_size):
        yield b"<!DOCTYPE html><html><head><title>Error</title></head><body>Server error</body></html>"

    mock_resp2 = AsyncMock()
    mock_resp2.status = 200
    mock_resp2.headers = {"Content-Type": "application/octet-stream"}
    mock_resp2.content.iter_chunked = mock_html_chunks
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_resp2
        res2 = await asilmedia_service.download_video_stream("https://server.asilmedia.org/download/3/4", dest)
        assert res2 is None
        assert not dest.exists()


def test_asilmedia_is_valid_video_header():
    """Video sarlavhalari (magic bytes) tekshiruvi testi."""
    # To'g'ri MP4 (ftyp)
    mp4_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42"
    assert asilmedia_service.is_valid_video_header(mp4_bytes) is True

    # To'g'ri MKV
    mkv_bytes = b"\x1a\x45\xdf\xa3\x93\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81"
    assert asilmedia_service.is_valid_video_header(mkv_bytes) is True

    # Noto'g'ri HTML / matn
    html_bytes = b"<!DOCTYPE html>\n<html>\n<head>\n"
    assert asilmedia_service.is_valid_video_header(html_bytes) is False

    js_bytes = b"var player = new Player();\n/* script */"
    assert asilmedia_service.is_valid_video_header(js_bytes) is False

    # Bo'sh yoki juda qisqa
    assert asilmedia_service.is_valid_video_header(b"abc") is False


@pytest.mark.asyncio
async def test_background_movie_preloader_lifecycle():
    """Kinolarni orqa fonda yuklash va tayyorlash vazifasi ishga tushishi va to'xtashi testi."""
    from services.movie_service import (
        start_background_movie_preloader,
        stop_background_movie_preloader,
        _background_movie_preloader_loop
    )

    with patch("services.movie_service._background_movie_preloader_loop", new_callable=AsyncMock) as mock_loop:
        task = start_background_movie_preloader(limit=2)
        assert task is not None
        # Qayta chaqirilganda bir xil task qaytishi kerak
        task2 = start_background_movie_preloader(limit=2)
        assert task == task2

        stop_background_movie_preloader()
        await asyncio.sleep(0)
        assert getattr(task, "cancelling", lambda: 0)() > 0 or task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_admin_download_catalog_asilmedia_command():
    """Admin /download_catalog_asilmedia buyrug'i testi."""
    from handlers.admin import cmd_download_catalog_asilmedia

    msg = AsyncMock(spec=Message)
    msg.text = "/download_catalog_asilmedia 5"
    admin_id = config.admin_ids[0] if config.admin_ids else 7271080503
    msg.from_user = TgUser(id=admin_id, is_bot=False, first_name="Admin")
    status_mock = AsyncMock()
    msg.reply = AsyncMock(return_value=status_mock)

    with patch("services.movie_service.start_background_movie_preloader") as mock_preload:
        mock_task = AsyncMock()
        mock_preload.return_value = mock_task
        await cmd_download_catalog_asilmedia(msg)
        mock_preload.assert_called_once_with(limit=5)
        status_mock.edit_text.assert_called_once()
        sent_text = status_mock.edit_text.call_args[0][0]
        assert "5 ta" in sent_text
        assert "orqa fonda" in sent_text


@pytest.mark.asyncio
async def test_admin_add_movie_media_text_flow():
    """Admin kino qo'shishda fayl o'rniga Asilmedia matni yuborishi testi."""
    from handlers.admin import state_add_movie_media_text
    from utils.states import MovieAddStates

    msg = AsyncMock(spec=Message)
    msg.text = "asilmedia"
    msg.from_user = TgUser(id=12345, is_bot=False, first_name="Admin")
    status_mock = AsyncMock()
    msg.reply = AsyncMock(return_value=status_mock)

    state = AsyncMock()
    state.get_data.return_value = {"code": "999", "title": "Avatar 2"}

    with patch("services.movie_service.movie_service.sync_movie_from_asilmedia", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = {
            "success": True,
            "title": "Avatar 2",
            "synced_parts": [1]
        }
        await state_add_movie_media_text(msg, state)
        mock_sync.assert_called_once()
        state.update_data.assert_called_once()
        update_kwargs = state.update_data.call_args[1]
        assert "asilmedia_stream_999" in update_kwargs.get("file_id")
        state.set_state.assert_called_once_with(MovieAddStates.waiting_for_genres)


@pytest.mark.asyncio
async def test_cmd_browser_asilmedia_portal_and_search():
    """/browser asilmedia.org va /browser asilmedia Taksi 2 to'g'ri ishlashi testi."""
    from handlers.movies import cmd_browser
    bot_mock = AsyncMock()
    msg_mock = AsyncMock()
    msg_mock.bot = bot_mock
    msg_mock.chat = MagicMock(id=123456)
    msg_mock.from_user = MagicMock(id=123456)
    msg_mock.message_id = 999
    msg_mock.reply = AsyncMock()

    # 1. /browser asilmedia.org -> Asilmedia Portali klaviaturasi
    msg_mock.text = "/browser asilmedia.org"
    await cmd_browser(msg_mock)
    assert msg_mock.reply.called
    reply_args = msg_mock.reply.call_args
    portal_text = reply_args.args[0] if reply_args.args else reply_args.kwargs.get("text", "")
    assert "Bauntys — Asilmedia Kinolar Portali" in portal_text
    assert "@Bauntyfilmsbot" in portal_text
    assert "@BauntyFilms" in portal_text
    kb = reply_args.kwargs.get("reply_markup")
    assert kb is not None

    # 2. /browser asilmedia.org Taksi 2 -> deliver_movie chaqirilishi
    msg_mock.reply.reset_mock()
    msg_mock.text = "/browser asilmedia.org Taksi 2"
    with patch("services.movie_service.movie_service.deliver_movie", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = True
        await cmd_browser(msg_mock)
        mock_deliv.assert_called_once()
        _, kwargs = mock_deliv.call_args
        assert kwargs.get("code") == "718"
        assert kwargs.get("part") == 2


@pytest.mark.asyncio
async def test_cb_watch_part_handles_movie_and_watch_part():
    """cb_watch_part 'watch_part:code:part' va 'movie:code:part' ni birdek muvaffaqiyatli qabul qilishi testi."""
    from handlers.movies import cb_watch_part
    bot_mock = AsyncMock()
    msg_mock = AsyncMock()
    msg_mock.chat = MagicMock(id=987654)
    msg_mock.answer = AsyncMock()

    cb_mock = AsyncMock()
    cb_mock.bot = bot_mock
    cb_mock.message = msg_mock
    cb_mock.answer = AsyncMock()

    with patch("services.movie_service.movie_service.deliver_movie", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = True

        # 1. movie:718:1 formatidagi callback
        cb_mock.data = "movie:718:1"
        await cb_watch_part(cb_mock)
        mock_deliv.assert_called_with(
            bot=bot_mock,
            chat_id=987654,
            code="718",
            part=1
        )
        cb_mock.answer.assert_called()

        # 2. watch_part:1500:3 formatidagi callback
        mock_deliv.reset_mock()
        cb_mock.data = "watch_part:1500:3"
        await cb_watch_part(cb_mock)
        mock_deliv.assert_called_with(
            bot=bot_mock,
            chat_id=987654,
            code="1500",
            part=3
        )


@pytest.mark.asyncio
async def test_forsaj_1500_catalog_and_delivery(in_memory_session):
    """Forsaj (kod 1500) katalogda 11 ta qism bilan mavjudligi va deliver_movie muvaffaqiyatli uzatishi testi."""
    cat = MovieService.get_catalog_item("1500")
    assert cat is not None
    assert cat.get("c") == 1500
    assert cat.get("p") == 11
    assert "Forsaj" in cat.get("t")

    bot_mock = AsyncMock()
    mock_sent = MagicMock()
    mock_sent.video = MagicMock(file_id="BAACAgIAAxkBAAE_FORSAJ_1234567890", duration=120, file_size=788493)
    mock_sent.document = None
    bot_mock.send_video = AsyncMock(return_value=mock_sent)

    res = await MovieService.deliver_movie(
        bot=bot_mock,
        chat_id=555555,
        code="1500",
        part=1,
        session=in_memory_session
    )
    assert res is True
    assert bot_mock.send_video.called


@pytest.mark.asyncio
async def test_dynamic_asilmedia_sync_on_uncataloged_code(in_memory_session):
    """Katalogda bo'lmagan Asilmedia kodi so'ralganda darhol rad etmasdan sinxronlash va yetkazish testi."""
    bot_mock = AsyncMock()
    mock_sent = MagicMock()
    mock_sent.video = MagicMock(file_id="BAACAgIAAxkBAAE_UNCATALOGED_12345", duration=90, file_size=5000000)
    mock_sent.document = None
    bot_mock.send_video = AsyncMock(return_value=mock_sent)

    with patch.object(MovieService, "sync_movie_from_asilmedia", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = {
            "success": True,
            "title": "Yangi Asilmedia Kino",
            "synced_parts": [1]
        }
        res = await MovieService.deliver_movie(
            bot=bot_mock,
            chat_id=444444,
            code="99999",
            part=1,
            session=in_memory_session
        )
        assert res is True
        assert mock_sync.call_count >= 1



