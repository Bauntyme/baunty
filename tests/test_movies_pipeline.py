"""Pipeline, sanitization, Asilmedia deduplication, and delivery fallback tests."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import BASE_DIR  # noqa: E402
from handlers import movies as movies_handler  # noqa: E402
from services import movie_service as movie_service_mod  # noqa: E402
from services.asilmedia_service import AsilmediaService, asilmedia_service  # noqa: E402
from services.movie_service import MAX_TELEGRAM_UPLOAD_BYTES, MovieService  # noqa: E402


def test_is_valid_video_header_validation():
    """MP4/MKV/FLV/AVI headers pass while HTML/JS/JSON/short data fail."""
    assert asilmedia_service.is_valid_video_header(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00")
    assert asilmedia_service.is_valid_video_header(b"\x00\x00\x00 ftypisom\x00\x00\x02\x00")
    assert asilmedia_service.is_valid_video_header(b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x42\x82\x88matroska")
    assert asilmedia_service.is_valid_video_header(b"FLV\x01\x05\x00\x00\x00\x09\x00\x00\x00\x00\x12\x00\x01")
    assert asilmedia_service.is_valid_video_header(b"RIFF\x24\x00\x00\x00AVI LIST")

    assert not asilmedia_service.is_valid_video_header(b"<!DOCTYPE html><html><body>err</body></html>")
    assert not asilmedia_service.is_valid_video_header(b"<html><head><title>404</title></head></html>")
    assert not asilmedia_service.is_valid_video_header(b'{"error":"forbidden"}')
    assert not asilmedia_service.is_valid_video_header(b"var error = {code: 403};")
    assert not asilmedia_service.is_valid_video_header(b"")
    assert not asilmedia_service.is_valid_video_header(b"short")


def test_no_banned_pools_proxies_or_mock_videos():
    """Verify legacy mock pool, sslip proxy, default.mp4, and corrupt 101_10.mp4 are gone."""
    assert not hasattr(movie_service_mod, "VERIFIED_CDN_VIDEO_POOL")
    assert not (BASE_DIR / "data" / "videos" / "default.mp4").exists()
    assert not (BASE_DIR / "data" / "videos" / "101_10.mp4").exists()

    banned_ip = "161-97-" + "96-58"
    for rel in (
        "services/asilmedia_service.py",
        "services/movie_service.py",
        "handlers/movies.py",
    ):
        src = (BASE_DIR / rel).read_text(encoding="utf-8")
        assert banned_ip not in src, f"Found banned proxy IP in {rel}"
        assert "VERIFIED_CDN_VIDEO_POOL" not in src, f"Found banned pool in {rel}"

    sources_path = BASE_DIR / "data" / "video_sources.json"
    if sources_path.exists():
        parsed = json.loads(sources_path.read_text(encoding="utf-8"))
        entries = parsed.get("items", parsed) if isinstance(parsed, dict) else {}
        assert isinstance(entries, dict)
        raw_txt = json.dumps(entries).lower()
        for banned in ("samplelib", "mov_bbb", "flower.mp4", "oceans.mp4", "default.mp4", banned_ip, "sslip.io"):
            assert banned not in raw_txt, f"Found banned reference {banned} in video_sources.json"
        for key, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            for field in ("url", "download_url", "stream_url", "video_url", "src", "file_id", "file_path"):
                val = str(entry.get(field) or "").lower()
                assert "server.asilmedia.org" not in val, f"HTML wrapper in {key}.{field}"
                assert ".html" not in val and "sayt.php" not in val, f"HTML URL in {key}.{field}"


def test_extract_sources_deduplicates_multi_quality_episodes():
    """Multiple qualities for the same episode merge into 1 episode with quality_urls."""
    sample_html = """
    <html>
      <head><title>Test Series — Asilmedia</title></head>
      <body>
        <h1>Test Series (2025)</h1>
        <i id="amh" data-id="98765" data-n="abcd1234"></i>
        <div id="tg-data"
             data-title="Test Series"
             data-totalparts="4"
             data-serialpart1="1-qism 480p"
             data-serialpart2="1-qism 1080p"
             data-serialpart3="2-qism 480p"
             data-serialpart4="2-qism 720p"></div>
        <div id="episodes-raw-data">
          <a href="am:98765:ep1_480">1-qism 480p</a>
          <a href="am:98765:ep1_1080">1-qism 1080p</a>
          <a href="https://server.asilmedia.org/watch/98765?part=1">1-qism 480p watch</a>
          <a href="am:98765:ep2_480">2-qism 480p</a>
          <a href="am:98765:ep2_720">2-qism 720p</a>
          <a href="https://server.asilmedia.org/download/98765?part=2">2-qism 720p dl</a>
        </div>
      </body>
    </html>
    """
    svc = AsilmediaService()
    movie = svc.extract_sources_from_html(sample_html, "https://asilmedia.org/98765-test-series.html")
    assert movie is not None
    assert movie.amh_id == "98765"
    assert movie.amh_n == "abcd1234"
    assert movie.is_series is True
    assert len(movie.episodes) == 2
    assert movie.total_parts == 2
    eps = list(movie.episodes.values()) if isinstance(movie.episodes, dict) else list(movie.episodes)
    assert [ep.part for ep in eps] == [1, 2]

    ep1, ep2 = eps[0], eps[1]
    assert ep1.quality_urls["480p"] == "am:98765:ep1_480"
    assert ep1.quality_urls["1080p"] == "am:98765:ep1_1080"
    assert ep1.url.startswith("am:")
    assert ep1.watch_url == "https://server.asilmedia.org/watch/98765?part=1"
    assert "server.asilmedia.org" not in (ep1.url or "")
    assert "server.asilmedia.org" not in (ep1.download_url or "")

    assert ep2.quality_urls["480p"] == "am:98765:ep2_480"
    assert ep2.quality_urls["720p"] == "am:98765:ep2_720"
    assert ep2.url.startswith("am:")
    assert ep2.watch_url == "https://server.asilmedia.org/download/98765?part=2"


@pytest.mark.asyncio
async def test_resolve_stream_url_signs_am_and_rejects_html():
    """resolve_stream_url signs am:<id>:<hash> via fayllar-sign and rejects HTML wrappers."""
    svc = AsilmediaService()

    # HTML wrapper pages must immediately resolve to None
    assert await svc.resolve_stream_url("https://server.asilmedia.org/watch/123") is None
    assert await svc.resolve_stream_url("https://asilmedia.org/17638-kino.html") is None

    async def fake_sign(urls, amh_id=None, amh_n=None):
        assert amh_id == "111"
        assert amh_n == "tok222"
        return {u: "https://30.fayllar.com/17638/ep1.mp4?token=signed999" for u in urls}

    with patch.object(svc, "sign_fayllar_urls", side_effect=fake_sign):
        signed = await svc.resolve_stream_url("am:17638:hashabc", news_id="17638", amh_id="111", amh_n="tok222")

    assert signed == "https://30.fayllar.com/17638/ep1.mp4?token=signed999"


def test_is_valid_telegram_file_id_checks():
    """Reject fake BAACAgIAAxkBAAIB_* prefix, URLs, am:, and mock keywords."""
    assert not MovieService.is_valid_telegram_file_id("BAACAgIAAxkBAAIB_fake_demo_id")
    assert not MovieService.is_valid_telegram_file_id("https://server.asilmedia.org/watch/1")
    assert not MovieService.is_valid_telegram_file_id("am:17638:hash123")
    assert not MovieService.is_valid_telegram_file_id("samplelib-mp4-video-id")
    assert MovieService.is_valid_telegram_file_id("BAACAgIAAxkBAAIRealUploadedTelegramVideoFileId2026")


class _AsyncChunkReader:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def iter_chunked(self, _n):
        for ch in self._chunks:
            yield ch


class _MockHttpResp:
    def __init__(self, status=200, headers=None, chunks=None):
        self.status = status
        self.headers = headers or {}
        self.content = _AsyncChunkReader(chunks or [])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _MockHttpSession:
    def __init__(self, resp):
        self._resp = resp

    def get(self, *_args, **_kwargs):
        return self._resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_download_and_upload_rejects_html_and_oversized(tmp_path):
    """HTML responses and >50MB Content-Length are rejected cleanly with no leftover files."""
    bot = MagicMock()
    bot.send_video = AsyncMock()

    # 1) Server wrapper URL rejected before network request
    res_html_url = await MovieService.download_and_upload_media_on_demand(
        bot=bot,
        chat_id=12345,
        code="99901",
        part=1,
        source_url="https://server.asilmedia.org/watch/99901",
        caption="Test",
    )
    assert res_html_url is None
    assert not bot.send_video.called

    # 2) HTTP response with text/html Content-Type rejected
    html_resp = _MockHttpResp(
        status=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        chunks=[b"<html><body>Not a video</body></html>"],
    )
    with patch("services.movie_service.BASE_DIR", tmp_path), patch(
        "services.movie_service.aiohttp.ClientSession", return_value=_MockHttpSession(html_resp)
    ):
        (tmp_path / "data" / "videos").mkdir(parents=True, exist_ok=True)
        res_ct = await MovieService.download_and_upload_media_on_demand(
            bot=bot,
            chat_id=12345,
            code="99902",
            part=1,
            source_url="https://cdn.example.com/99902.mp4?token=1",
            caption="Test",
        )
    assert res_ct is None
    assert not list((tmp_path / "data" / "videos").glob("99902*"))

    # 3) Content-Length > 50MB rejected before downloading body
    big_resp = _MockHttpResp(
        status=200,
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": str(MAX_TELEGRAM_UPLOAD_BYTES + 1024),
        },
        chunks=[b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1024],
    )
    with patch("services.movie_service.BASE_DIR", tmp_path), patch(
        "services.movie_service.aiohttp.ClientSession", return_value=_MockHttpSession(big_resp)
    ):
        res_big = await MovieService.download_and_upload_media_on_demand(
            bot=bot,
            chat_id=12345,
            code="99903",
            part=1,
            source_url="https://cdn.example.com/99903.mp4?token=1",
            caption="Test",
        )
    assert res_big is None
    assert not bot.send_video.called


@pytest.mark.asyncio
async def test_handlers_fallback_buttons_when_deliver_movie_returns_false():
    """Fallback sends honest WebApp + signed direct download buttons without faking TG video."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_video = AsyncMock()

    cat_item = {"c": 101, "t": "Derriga xush kelibsiz", "v": 1376, "p": 8, "asil_id": 17638}
    stream_info = {
        "title": "Derriga xush kelibsiz",
        "part": 1,
        "total_parts": 8,
        "stream_url": "https://30.fayllar.com/17638/ep1.mp4?token=abc",
        "quality_urls": {"480p": "https://30.fayllar.com/17638/ep1.mp4?token=abc"},
        "watch_url": None,
        "poster": None,
        "asil_id": "17638",
    }

    with patch.object(MovieService, "get_catalog_item", return_value=cat_item), patch.object(
        MovieService, "get_movie_stream_info", new=AsyncMock(return_value=stream_info)
    ), patch("handlers.movies.crud.get_movie_by_code", new=AsyncMock(return_value=None)):
        await movies_handler._send_movie_delivery_fallback(
            bot=bot,
            chat_id=777,
            code="101",
            part=1,
            session=MagicMock(),
        )

    bot.send_video.assert_not_called()
    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.call_args.kwargs
    text_sent = kwargs["text"]
    assert "Derriga xush kelibsiz" in text_sent
    assert "50 MB" in text_sent or "WebApp" in text_sent

    kb = kwargs["reply_markup"]
    all_buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert any(getattr(btn, "web_app", None) and "c=101" in btn.web_app.url and "part=1" in btn.web_app.url for btn in all_buttons)
    assert any(btn.url == stream_info["stream_url"] for btn in all_buttons)


@pytest.mark.asyncio
async def test_unified_catalog_search_and_stream_info():
    """Unified catalog drops code_part child rows, supports translit search, and resolves stream info."""
    # search_catalog with numeric code and Cyrillic transliteration
    res_code = await MovieService.search_catalog("101", session=None, limit=10)
    assert any(str(item.get("c")) == "101" for item in res_code)

    res_cyr = await MovieService.search_catalog("Деррига", session=None, limit=10)
    assert any("derri" in str(item.get("t", "")).lower() for item in res_cyr)

    # DB rows containing child code_part rows must not become top-level items
    fake_rows = [
        SimpleNamespace(code="99990", title="Test Base Movie", description="Desc", views_count=10, year=2025, genres="Action", poster=None),
        SimpleNamespace(code="99990_2", title="Test Base Movie 2-qism", description="Desc", views_count=1, year=2025, genres="Action", poster=None),
        SimpleNamespace(code="99990_3", title="Test Base Movie 3-qism", description="Desc", views_count=1, year=2025, genres="Action", poster=None),
    ]
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = fake_rows
    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=fake_result)

    unified = await MovieService.get_unified_catalog(session=fake_session)
    codes = {str(x.get("c")) for x in unified}
    assert "99990" in codes
    assert "99990_2" not in codes
    assert "99990_3" not in codes
    item_99990 = next(x for x in unified if str(x.get("c")) == "99990")
    assert item_99990.get("p") == 3

    # get_movie_stream_info resolves signed .mp4 URL for 101 part 1
    info = await MovieService.get_movie_stream_info("101", part=1, session=None)
    assert info is not None
    assert info["part"] == 1
    assert info["total_parts"] == 8
    assert info["asil_id"] == "17638"
    assert info["stream_url"] and info["stream_url"].startswith("http")
    assert ".mp4" in info["stream_url"].lower()
    assert "server.asilmedia.org" not in info["stream_url"]


@pytest.mark.asyncio
async def test_live_asilmedia_17638_and_17608():
    """Live smoke test verifying 17638 has 8 real deduplicated parts and signed .mp4 URLs."""
    svc = AsilmediaService()
    try:
        m17638 = await svc.get_movie_details(17638)
        assert m17638 is not None
        eps_raw = m17638.episodes.values() if isinstance(m17638.episodes, dict) else m17638.episodes
        eps = sorted(eps_raw, key=lambda e: e.part)
        assert len(eps) == 8, f"Expected 8 episodes for 17638, got {len(eps)}"
        assert m17638.total_parts == 8
        assert [ep.part for ep in eps] == list(range(1, 9))

        for ep in eps:
            assert ep.url and ep.url.startswith("http")
            assert not ep.url.startswith("am:")
            assert "server.asilmedia.org" not in ep.url
            assert ".mp4" in ep.url.lower()
            assert "token=" in ep.url.lower()
            assert ep.quality_urls, f"Missing quality_urls on episode {ep.part}"

        m17608 = await svc.get_movie_details(17608)
        assert m17608 is not None
        eps_17608 = list(m17608.episodes.values()) if isinstance(m17608.episodes, dict) else list(m17608.episodes or [])
        direct_17608 = m17608.download_url or (eps_17608[0].url if eps_17608 else None)
        if not direct_17608 and m17608.video_sources:
            direct_17608 = next(iter(m17608.video_sources.values()))
        assert direct_17608 and direct_17608.startswith("http")
        assert ".mp4" in direct_17608.lower()
        assert "server.asilmedia.org" not in direct_17608
    finally:
        close_fn = getattr(svc, "close_session", None) or getattr(svc, "close", None)
        if callable(close_fn):
            await close_fn()
