"""
Asilmedia.org integratsiyasi, video manbalari, qismlar va deliver_movie testlari.
100% Bauntys oq brendi: @Bauntyfilmsbot va @BauntyFilms.
"""
import json
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
