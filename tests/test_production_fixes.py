"""
Ishlab chiqarish (production) xatolarini tuzatish va Ziyouz kutubxonasi integratsiyasi uchun testlar:
1. Telegram HTML caption escape + MovieService._send_with_telegram_fallback plain-text qayta urinishi.
2. MusicService._is_valid_audio_url (/get/music/.../*.mp3), _build_query_variants, YouTube bloklanganda ochiq MP3 zaxirasi.
3. /p/{i}_s.webp poster zaxirasi (_resolve_catalog_item_any va fallback WebP 200).
4. /api/asil/stream Referer + Range (206) proksi va re-sign tekshiruvi.
5. Ziyouz real kutubxonasi (9,976+ PDF, /api/books/home 12 janr + featured/top, qidiruv, TOC va real PDF oqimi)
   hamda load_books() == 3390 / get_book_by_id("999999") is None mosligi.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer

from services import book_service, web_server
from services.downloader import DownloadResult
from services.movie_service import MovieService
from services.music_service import MusicService
from services.ziyouz_service import ziyouz_service
from utils.helpers import format_movie_caption, format_movie_not_found


# ---------------------------------------------------------------------------
# 1. Telegram HTML Entity Escape & Plain-Text Fallback
# ---------------------------------------------------------------------------


def test_format_movie_caption_escapes_html_and_strips_raw_tags():
    movie = SimpleNamespace(
        title="Eshref <va> Ruya & Do'stlar",
        code="17071",
        genres=["Drama & <Melodrama>"],
        year=2025,
        rating=8.7,
        quality="1080p",
        description="<b>Asosiy tavsif</b> & <script>alert(1)</script> matn",
        movie_type="serial",
        views_count=12,
    )
    cap = format_movie_caption(movie)
    assert "Eshref &lt;va&gt; Ruya &amp; Do'stlar" in cap
    assert "Drama &amp; &lt;Melodrama&gt;" in cap
    assert "<script>" not in cap
    assert "<b" in cap  # formatlash teglari saqlanadi

    nf = format_movie_not_found("Test <tag> &")
    assert "Test &lt;tag&gt; &amp;" in nf


@pytest.mark.asyncio
async def test_send_with_telegram_fallback_retries_plain_text_on_parse_error():
    calls = []

    async def fake_send(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise Exception("Telegram server says - Bad Request: can't parse entities: Unexpected end tag at byte offset 10")
        return SimpleNamespace(message_id=777)

    res = await MovieService._send_with_telegram_fallback(
        fake_send,
        text_key="caption",
        chat_id=12345,
        caption="<b>Eshref va Ruya</b>\n<i>Yangi <xato qism</i>",
        parse_mode="HTML",
        reply_to_message_id=99,
    )
    assert res.message_id == 777
    assert len(calls) == 2
    assert calls[0]["parse_mode"] == "HTML"
    assert calls[1]["parse_mode"] is None
    assert "<b>" not in calls[1]["caption"]
    assert "Eshref va Ruya" in calls[1]["caption"]


# ---------------------------------------------------------------------------
# 2. Music URL Validation, Query Cleaning & YT Bot-Block Bypass
# ---------------------------------------------------------------------------


def test_music_is_valid_audio_url_and_query_variants():
    # Oldingi bug '/music/' qismini rad etardi; Hitmotop URL qabul qilinishi shart
    assert MusicService._is_valid_audio_url("https://rus.hitmotop.com/get/music/20260101/Track_123.mp3")
    assert MusicService._is_valid_audio_url("https://uzhits.net/dl/song.mp3")
    assert not MusicService._is_valid_audio_url("https://example.com/page.html")
    assert not MusicService._is_valid_audio_url("")

    variants = MusicService._build_query_variants("🎵 Yomg'ir | Xamdam Sobirov - Yomg'ir 🔥")
    assert variants
    assert "Xamdam Sobirov" in variants[0] and "Yomg'ir" in variants[0]
    assert all("|" not in v and "🎵" not in v and "🔥" not in v for v in variants)


@pytest.mark.asyncio
async def test_music_download_bypasses_youtube_with_open_mp3(tmp_path):
    svc = MusicService()
    mp3_file = tmp_path / "track.mp3"
    mp3_file.write_bytes(b"ID3" + b"\x00" * 5000)

    yt_mock = AsyncMock(return_value=DownloadResult(success=False, error="Sign in to confirm you're not a bot"))
    direct_mock = AsyncMock(return_value=DownloadResult(success=True, file_path=str(mp3_file), title="Yomg'ir"))

    with (
        patch.object(svc, "_find_open_mp3_url", AsyncMock(return_value=("https://rus.hitmotop.com/get/music/1/yomgir.mp3", "hitmotop"))),
        patch.object(svc.downloader, "download_direct_audio", direct_mock),
        patch.object(svc.downloader, "download_audio", yt_mock),
    ):
        res = await svc.download_track_mp3("Xamdam Sobirov - Yomg'ir")

    assert res.success is True
    assert res.file_path == str(mp3_file)
    yt_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3. Movie Poster Proxy (/p/{code}_s.webp) & Stream Proxy (/api/asil/stream)
# ---------------------------------------------------------------------------


def test_resolve_catalog_item_any_matches_id_and_suffix():
    fake_entry = {"c": "1234", "i": "987654", "asil_id": "17071", "t": "Eshref va Ruya"}
    with (
        patch.object(MovieService, "get_catalog_item", side_effect=lambda k: fake_entry if k == "1234" else None),
        patch.object(MovieService, "_ensure_catalog_cache", return_value={"items": [fake_entry]}),
    ):
        assert web_server._resolve_catalog_item_any("1234_s") == fake_entry
        assert web_server._resolve_catalog_item_any("987654_s") == fake_entry
        assert web_server._resolve_catalog_item_any("17071_l") == fake_entry


@pytest.mark.asyncio
async def test_poster_proxy_returns_webp_fallback_instead_of_404():
    app = web_server.create_web_app()
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        with patch.object(web_server, "_resolve_catalog_item_any", return_value=None):
            resp = await client.get("/p/99999888_s.webp")
            assert resp.status == 200
            assert resp.headers.get("Content-Type", "").startswith("image/webp")
            body = await resp.read()
            assert len(body) > 100
            assert body[:4] == b"RIFF"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_asil_stream_proxies_referer_and_range_206():
    captured_requests = []

    class _FakeContent:
        async def iter_chunked(self, size):
            yield b"0123456789"

    class _FakeUpstreamResp:
        def __init__(self):
            self.status = 206
            self.headers = {
                "Content-Type": "video/mp4",
                "Accept-Ranges": "bytes",
                "Content-Range": "bytes 0-9/100",
                "Content-Length": "10",
            }
            self.content = _FakeContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class _FakeClientSession:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, headers=None, allow_redirects=True):
            captured_requests.append(("GET", url, dict(headers or {})))
            return _FakeUpstreamResp()

        def head(self, url, headers=None, allow_redirects=True):
            captured_requests.append(("HEAD", url, dict(headers or {})))
            return _FakeUpstreamResp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    fake_stream_info = {
        "stream_url": "https://fayllar1.ru/17071/ep1.mp4",
        "quality_urls": {"1080p": "https://fayllar1.ru/17071/ep1.mp4"},
    }
    fake_aiohttp = SimpleNamespace(
        ClientSession=_FakeClientSession,
        ClientTimeout=aiohttp.ClientTimeout,
        ClientError=aiohttp.ClientError,
        ClientConnectionError=aiohttp.ClientConnectionError,
    )

    app = web_server.create_web_app()
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        from services.asilmedia_service import asilmedia_service

        with (
            patch.object(MovieService, "get_movie_stream_info", AsyncMock(return_value=fake_stream_info)),
            patch.object(asilmedia_service, "is_token_expired", return_value=False),
            patch.object(asilmedia_service, "needs_fayllar_sign", return_value=False),
            patch.object(web_server, "aiohttp", fake_aiohttp),
        ):
            resp = await client.get("/api/asil/stream?id=17071&part=1&quality=1080p", headers={"Range": "bytes=0-9"})
            assert resp.status == 206
            assert resp.headers.get("Content-Range") == "bytes 0-9/100"
            assert await resp.read() == b"0123456789"
            assert captured_requests
            method, url, hdrs = captured_requests[0]
            assert method == "GET"
            assert "fayllar1.ru" in url
            assert hdrs.get("Referer") == "https://asilmedia.org/"
            assert hdrs.get("Range") == "bytes=0-9"
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# 4. Ziyouz Real Uzbek Library Integration & Book Service Compatibility
# ---------------------------------------------------------------------------


def test_book_service_compat_and_ziyouz_catalog():
    books = book_service.load_books()
    assert len(books) == 3390
    assert book_service.get_book_by_id("999999") is None

    assert ziyouz_service.count() >= 9000
    items, total = ziyouz_service.search(query="O'tkan kunlar", limit=10)
    assert total >= 1 and len(items) >= 1
    first = items[0]
    assert first["src"] == "ziyouz"
    assert isinstance(first["f"], list) and "pdf" in first["f"]
    assert isinstance(first["p"], int) and first["p"] >= 16
    assert book_service.get_book_by_id(first["i"]) is not None


@pytest.mark.asyncio
async def test_books_home_search_toc_and_pdf_stream(tmp_path):
    import json
    import services.ziyouz_service as zmod

    sample_id = ziyouz_service.load()[0]["i"]
    fake_pdf = b"%PDF-1.6\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    ziyouz_service._mem_toc_cache.clear()

    app = web_server.create_web_app()
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        r_home = await client.get("/api/books/home")
        assert r_home.status == 200
        home = await r_home.json()
        assert home["ok"] is True
        assert "zakirov" not in json.dumps(home, ensure_ascii=False).lower()
        assert len(home["genres"]) == 12
        assert len(home["categories"]) == 12
        shelf_keys = {s["k"] for s in home["shelves"]}
        assert "featured" in shelf_keys and "top" in shelf_keys
        assert home["total"] > 10000
        assert home["langs"]["uz"] > 9000

        r_search = await client.get("/api/books/search?q=Alisher+Navoiy&limit=5")
        assert r_search.status == 200
        sdata = await r_search.json()
        assert sdata["ok"] is True and sdata["total"] >= 10
        assert isinstance(sdata["items"][0]["f"], list)

        with (
            patch.object(zmod, "ZIYOUZ_CACHE_DIR", tmp_path),
            patch.object(ziyouz_service, "fetch_pdf_bytes", AsyncMock(return_value=fake_pdf)),
        ):
            r_toc = await client.get(f"/bk/{sample_id}/toc.json")
            assert r_toc.status == 200
            toc_json = await r_toc.json()
            assert toc_json["ok"] is True and isinstance(toc_json["toc"], list) and len(toc_json["toc"]) >= 1

            r_ch = await client.get(f"/bk/{sample_id}/c1.json")
            assert r_ch.status == 200
            ch_json = await r_ch.json()
            assert "t" in ch_json and isinstance(ch_json["p"], list) and len(ch_json["p"]) >= 1

            r_pdf = await client.get(f"/api/books/{sample_id}/pdf")
            assert r_pdf.status == 200
            assert r_pdf.headers.get("Content-Type", "").startswith("application/pdf")
            assert await r_pdf.read() == fake_pdf
    finally:
        ziyouz_service._mem_toc_cache.clear()
        await client.close()
