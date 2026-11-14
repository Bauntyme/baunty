"""Regression testlari: Mini App seriallar UI, XSS-safe <b> formatlash, fayllar-sign chunking,
@ZakirovsKino public feed sinxronizatsiyasi, aniq kino qidirish va Kitoblar-@Zakirovs_ai ulanishi.
"""
import json
import subprocess
import urllib.parse
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

from services.asilmedia_service import AsilmediaEpisode, AsilmediaMovie, asilmedia_service
from services.movie_service import MovieService, movie_service
from services.web_server import create_web_app

ROOT = Path(__file__).resolve().parents[1]
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0"}


@pytest.mark.asyncio
async def test_sign_fayllar_urls_chunks_at_most_20():
    """fayllar-sign.php ~25 URL dan ko'p so'rovda bo'sh qaytargani uchun chunk <= 20 bo'lishi shart."""
    urls = [f"am:17071:hash_{i}" for i in range(42)]
    seen_chunk_sizes = []

    class FakeResp:
        def __init__(self, url: str):
            qs = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            self._chunk = qs.get("u[]", [])
            seen_chunk_sizes.append(len(self._chunk))
            self.status = 200

        async def json(self, content_type=None):
            return {u: f"https://fayllar1.ru/v/{i}.mp4?token=sig{i}" for i, u in enumerate(self._chunk)}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, **kwargs):
            return FakeResp(url)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with patch("services.asilmedia_service.aiohttp.ClientSession", FakeSession):
        signed = await asilmedia_service.sign_fayllar_urls(urls, amh_id="17071", amh_n="2")

    assert len(signed) == 42
    assert len(seen_chunk_sizes) >= 3
    assert all(1 <= sz <= 20 for sz in seen_chunk_sizes), f"Batch size too large: {seen_chunk_sizes}"


@pytest.mark.asyncio
async def test_get_movie_details_dedupes_and_limits_upfront_signing():
    """100+ qismli serialda get_movie_details takror havolalarni olib tashlab dastlabki 24 tasini imzolaydi."""
    ep_lines = []
    for ep in range(1, 35):
        ep_lines.append(f"serialpart{ep}={ep}-qism 1080p=am:17071:h{ep}_1080,{ep}-qism 720p=am:17071:h{ep}_720")
    html = (
        "<html><head><title>Eshref va Ruya (2025)</title></head><body>"
        "<h1>Eshref va Ruya (2025)</h1>"
        "<i id='amh' data-id='17071' data-n='2'></i>"
        f"<pre id='tg-data'>{chr(10).join(ep_lines)}</pre>"
        "</body></html>"
    )

    class FakeResp:
        def __init__(self, text: str):
            self.status = 200
            self._text = text

        async def text(self):
            return self._text

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, **kwargs):
            return FakeResp(html)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    asilmedia_service._details_cache.clear()
    captured = {}

    async def fake_sign(urls, amh_id=None, amh_n=None, force=False):
        captured["urls"] = list(urls)
        captured["amh_id"] = amh_id
        captured["amh_n"] = amh_n
        return {u: f"https://cdn.example/{i}.mp4?token=abc" for i, u in enumerate(urls)}

    with patch("services.asilmedia_service.aiohttp.ClientSession", FakeSession), \
         patch.object(asilmedia_service, "sign_fayllar_urls", side_effect=fake_sign), \
         patch.object(asilmedia_service, "get_telegram_media_info", new_callable=AsyncMock, return_value=None):
        movie = await asilmedia_service.get_movie_details("17071")

    assert movie is not None
    assert len(movie.episodes) == 34
    assert len(captured["urls"]) == 24
    assert len(set(captured["urls"])) == 24
    assert captured["amh_id"] == "17071"
    assert captured["amh_n"] == "2"


@pytest.mark.asyncio
async def test_handle_asil_item_returns_numbered_episodes_without_10_bolak():
    """/api/asil/item multi-qism serial uchun seasons va aniq parts=1 hamda stream_url qaytaradi."""
    fake_movie = AsilmediaMovie(
        id="17071",
        title="Eshref va Ruya",
        url="https://asilmedia.org/17071.html",
        orig_title="Esref Ruya",
        year=2025,
        poster="https://asilmedia.org/uploads/17071.jpg",
        rating=8.1,
        genres=["Drama"],
        description="🎬 <b>Eshref va Ruya</b> (2025)\nTavsif @ZakirovsKino",
        is_series=True,
        total_parts=12,
        episodes={
            n: AsilmediaEpisode(
                part=n,
                label=f"{n}-qism",
                quality="1080p",
                quality_urls={"1080p": f"https://f.example/{n}_1080.mp4?token=x", "720p": f"https://f.example/{n}_720.mp4?token=y"},
                url=f"https://f.example/{n}_1080.mp4?token=x",
                download_url=f"https://f.example/{n}_1080.mp4?token=x",
            )
            for n in range(1, 13)
        },
    )

    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        with patch("services.asilmedia_service.asilmedia_service.get_movie_details", new_callable=AsyncMock, return_value=fake_movie):
            resp = await client.get("/api/asil/item?id=17071&nocache=1", headers=BROWSER_HEADERS)
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True
            it = data["item"]
            assert "zakirov" not in json.dumps(it, ensure_ascii=False).lower()
            assert "seasons" in it and len(it["seasons"]) == 1
            eps = it["seasons"][0]["eps"]
            assert len(eps) == 12
            assert eps[4]["e"] == 5
            assert eps[4]["name"] == "5-qism"
            for f in it["files"]:
                assert f["parts"] == 1
                assert "stream_url" in f and f"part={f['part']}" in f["stream_url"]
    finally:
        await client.close()


def test_frontend_fmt_html_xss_safe_and_no_zakirov():
    """asil.js, app.js, books.js fmtHtml orqali faqat <b>/<i> ni ochadi, XSS escape qiladi va Zakirov yo'q."""
    for rel in ("webapp/asil.js", "webapp/app.js", "webapp/books.js", "webapp/bundle.min.js"):
        txt = (ROOT / rel).read_text(encoding="utf-8")
        assert "zakirov" not in txt.lower(), f"Brand leak found in {rel}"
        assert "fmtHtml" in txt, f"Missing fmtHtml in {rel}"

    asil_txt = (ROOT / "webapp/asil.js").read_text(encoding="utf-8")
    assert "${esc(x.desc)}" not in asil_txt
    assert "${fmtHtml(x.desc)}" in asil_txt
    assert "(!epNum && f.parts > 1)" in asil_txt

    node_out = subprocess.check_output(
        [
            "node",
            "-e",
            (
                'const esc=(s)=>String(s==null?"":s).replace(/[&<>"\']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;","\'":"&#39;"}[c]));'
                'const fmtHtml=(s)=>esc(s).replace(/&lt;(\\/?(?:b|strong|i|em|u))&gt;/gi,"<$1>");'
                'console.log(fmtHtml("<b>Eshref</b> <b onclick=alert(1)>x</b> <script>bad()</script>"));'
            ),
        ],
        text=True,
    ).strip()
    assert node_out.startswith("<b>Eshref</b> ")
    assert "&lt;b onclick=alert(1)&gt;" in node_out
    assert "&lt;script&gt;bad()&lt;/script&gt;" in node_out


def test_parse_zakirovs_channel_html_and_exact_catalog_match():
    """@ZakirovsKino public postlaridan aniq asil_<ID> kino parsing va qidiruv aniqligi."""
    sample_html = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn4.cdn-telegram.org/file/test9157.jpg')"></div>
      <div class="tgme_widget_message_text js-message_text">
        🎬 <b>Begona ona (2026)</b><br><br>
        🎭 Janr: Triller, Drama<br>
        ⭐ IMDb: 7.4<br>
        🤖 @Zakirovs_ai<br>
        <a href="https://t.me/Zakirovs_ai?start=asil_9157">Tomosha qilish</a>
      </div>
    </div>
    """
    parsed = MovieService._parse_zakirovs_channel_html(sample_html)
    assert len(parsed) == 1
    it = parsed[0]
    assert it["c"] == 9157
    assert it["t"] == "Begona ona"
    assert it["y"] == 2026
    assert it["r"] == 7.4
    assert it["p_url"] == "https://cdn4.cdn-telegram.org/file/test9157.jpg"
    assert "zakirov" not in it["d"].lower()
    assert "@Baunty" in it["d"]


def test_search_catalog_by_title_ranks_exact_match_first():
    """Birinchi uchragan substring emas, aniq nom mosligi ustun turishi kerak."""
    import sys
    ms_mod = sys.modules["services.movie_service"]
    old_cache = getattr(ms_mod, "_CATALOG_CACHE", None)
    old_base = getattr(ms_mod, "_CATALOG_CACHE_BASE", None)
    try:
        filler = [{"c": 50000 + i, "t": f"Boshqa Film {i}", "v": 10, "d": ""} for i in range(20)]
        ms_mod._CATALOG_CACHE = {
            "items": [
                {"c": 111, "t": "Ona qalbi va sirlari", "v": 9999, "d": "Ona haqida"},
                {"c": 9157, "t": "Begona ona", "v": 100, "d": "Begona ona (2026)"},
            ] + filler
        }
        ms_mod._CATALOG_CACHE_BASE = str(getattr(ms_mod.app_config, "BASE_DIR", ms_mod.BASE_DIR))
        hit = MovieService.search_catalog_by_title("Begona ona")
        assert hit is not None
        assert hit["c"] == 9157
        assert MovieService.search_catalog_by_title("Yangi film") is None
    finally:
        ms_mod._CATALOG_CACHE = old_cache
        ms_mod._CATALOG_CACHE_BASE = old_base


@pytest.mark.asyncio
async def test_sync_movie_from_asilmedia_does_not_fallback_to_single_word():
    """Multi-word kino topilmasa 1 ta birinchi so'z bilan boshqa xato kino yuklab yubormasligi shart."""
    with patch("services.asilmedia_service.asilmedia_service.find_best_match", new_callable=AsyncMock, return_value=None) as mock_fbm, \
         patch("services.asilmedia_service.asilmedia_service.get_movie_details", new_callable=AsyncMock, return_value=None):
        res = await MovieService.sync_movie_from_asilmedia(code="915799", title="Begona ona (2026)")
    assert res["success"] is False
    called_queries = [c.args[0] for c in mock_fbm.call_args_list]
    assert "Begona" not in called_queries


@pytest.mark.asyncio
async def test_books_and_browser_zakirovs_ai_asil_start_connection():
    """Kitoblar klaviaturasi @Zakirovs_ai ga ulangani va /browser asil_9157 ni to'g'ri ochishi."""
    from handlers.books import get_books_main_keyboard
    from handlers.movies import cmd_browser
    from aiogram.types import Message

    kb = get_books_main_keyboard()
    urls = [b.url for row in kb.inline_keyboard for b in row if b.url]
    assert any("t.me/Zakirovs_ai?start=kitob" in u for u in urls)

    msg = AsyncMock(spec=Message)
    msg.text = "/browser https://t.me/Zakirovs_ai?start=asil_9157"
    msg.chat = MagicMock(id=55555)
    msg.message_id = 1
    msg.reply = AsyncMock()
    msg.bot = AsyncMock()

    with patch.object(movie_service, "deliver_movie", new_callable=AsyncMock, return_value=True) as mock_deliv:
        await cmd_browser(msg)
        mock_deliv.assert_called_once()
        assert mock_deliv.call_args.kwargs.get("code") == "9157"
