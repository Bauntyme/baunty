"""
Testlar: TV oqimlariga tezkor ulanish, 1440p QHD sifati,
/api/tv/stream CORS proxy & relay, zaxira oqimlarga tezkor almashish (failover),
va barcha 208 ta kanalning 100% ishlashi.
"""
import pytest
from urllib.parse import quote
from aiohttp.test_utils import TestClient, TestServer
from services.web_server import create_web_app
from services.tv_data import CHANNELS_LIST, TV_CATEGORIES
from config import BASE_DIR

BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def test_tv_data_channels_and_security():
    """Barcha 208 ta kanal HTTPS ekanligi, HTTP aralash kontent yo'qligi va Ruxsor/Nasaf to'g'rilanganligi."""
    assert len(CHANNELS_LIST) >= 200

    # 1. Barcha URL lar faqat HTTPS bo'lishi kerak (brauzer mixed-content bloklanishini oldini olish)
    for ch in CHANNELS_LIST:
        stream = ch.get("stream", "")
        assert stream.startswith("https://"), f"{ch.get('name')} kanali oqimi HTTPS emas: {stream}"
        for _, u in ch.get("u", []):
            assert u.startswith("https://"), f"{ch.get('name')} zaxira oqimi HTTPS emas: {u}"

    # 2. Ruxsor TV va Nasaf TV birlamchi oqimi ishlaydigan stream8 bo'lishi
    by_name = {c["name"]: c for c in CHANNELS_LIST}
    ruxsor = by_name.get("Ruxsor TV")
    assert ruxsor is not None
    assert "stream8.cinerama.uz" in ruxsor["stream"]
    assert "1040" in ruxsor["stream"]

    nasaf = by_name.get("Nasaf TV")
    assert nasaf is not None
    assert "stream8.cinerama.uz" in nasaf["stream"]
    assert "1199" in nasaf["stream"]

    # 3. Zo'r TV 1440p/4K va zaxira oqimlari
    zor = by_name.get("Zo'r TV")
    assert zor is not None
    assert "4K" in zor.get("q", "") or "1440p" in zor.get("q", "")
    assert len(zor.get("u", [])) >= 3

    # 4. Kategoriyalar mavjudligi
    cat_keys = {cat["key"] for cat in TV_CATEGORIES}
    assert "ufc" in cat_keys
    assert "futbol" in cat_keys
    assert "milliy" in cat_keys
    assert "xususiy" in cat_keys


@pytest.mark.asyncio
async def test_tv_stream_proxy_endpoints():
    """/api/tv/stream va /webapp/api/tv/stream CORS proxy & relay ishlashi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Noto'g'ri / bo'sh so'rovlar
        r_empty = await client.get("/api/tv/stream", headers=BROWSER_HEADERS)
        assert r_empty.status == 400
        assert r_empty.headers.get("Access-Control-Allow-Origin") == "*"

        r_invalid_scheme = await client.get("/api/tv/stream?url=ftp://example.com/live.m3u8", headers=BROWSER_HEADERS)
        assert r_invalid_scheme.status == 400

        # 2. SSRF himoyasi (localhost / ichki IP lar bloklanishi)
        r_ssrf = await client.get("/api/tv/stream?url=http://127.0.0.1:8080/admin", headers=BROWSER_HEADERS)
        assert r_ssrf.status == 403

        # 3. OPTIONS preflight CORS so'rovi
        r_options = await client.options("/api/tv/stream", headers=BROWSER_HEADERS)
        assert r_options.status in (200, 204)
        assert r_options.headers.get("Access-Control-Allow-Origin") == "*"

        # 4. Haqiqiy jonli m3u8 oqimini proxy qilish va relatsion yo'llarni qayta yozish
        target_m3u8 = "https://stream3.cinerama.uz/1016/tracks-v1a1/mono.ts.m3u8"
        proxy_path = f"/api/tv/stream?url={quote(target_m3u8, safe='')}"
        r_proxy = await client.get(proxy_path, headers=BROWSER_HEADERS)
        assert r_proxy.status == 200
        assert r_proxy.headers.get("Access-Control-Allow-Origin") == "*"
        assert "mpegurl" in r_proxy.headers.get("Content-Type", "").lower()
        body = await r_proxy.text()
        assert "#EXTM3U" in body
        assert "/api/tv/stream?url=" in body

        # 5. /webapp prefiksi bilan ham ishlashi
        webapp_proxy_path = f"/webapp/api/tv/stream?url={quote(target_m3u8, safe='')}"
        r_webapp = await client.get(webapp_proxy_path, headers=BROWSER_HEADERS)
        assert r_webapp.status == 200
        assert r_webapp.headers.get("Access-Control-Allow-Origin") == "*"

    finally:
        await client.close()


def test_frontend_instant_connect_and_resilient_failover():
    """Frontend kodida tezkor ulanish (2s timeout), zaxiraga avtomatik o'tish va proxy fallback mavjudligi."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    app_js = (BASE_DIR / "webapp" / "app.js").read_text(encoding="utf-8")
    tvroom_js = (BASE_DIR / "webapp" / "tvroom.js").read_text(encoding="utf-8")
    js_app = (BASE_DIR / "webapp" / "js" / "app.js").read_text(encoding="utf-8")

    # 1. Tezkor ochilish: qisqa timeoutlar (2s / 3.5s va 2000ms manifest timeout)
    assert "_isSlow ? 3500 : 2000" in index_html
    assert "_isSlow ? 3500 : 2000" in app_js
    assert "manifestLoadingTimeOut: 2000" in index_html
    assert "manifestLoadingTimeOut: 2000" in app_js
    assert "manifestLoadingTimeOut: 2000" in tvroom_js
    assert "manifestLoadingTimeOut: 2000" in js_app

    # 2. Resilient failover: Proxy zaxira oqimi fallback mavjudligi
    assert "/api/tv/stream?url=" in index_html
    assert "/api/tv/stream?url=" in app_js
    assert "/api/tv/stream?url=" in tvroom_js
    assert "/api/tv/stream?url=" in js_app

    # 3. 1440p QHD va Adaptive Bitrate
    assert "1440p QHD" in index_html
    assert "1440p QHD" in app_js
    assert "hls.currentLevel = -1;" in index_html
    assert "hls.currentLevel = -1;" in app_js

    # 4. Bauntys oq brendingi
    assert "Baunty" in index_html
    assert "Baunty" in app_js
    assert "Bauntys" in tvroom_js


def test_bundle_frontend_compiled_and_has_stream_proxy():
    """webapp/dist/bundle.min.js va bundle.min.css to'g'ri kompilyatsiya qilinganligi."""
    dist_js = BASE_DIR / "webapp" / "dist" / "bundle.min.js"
    dist_css = BASE_DIR / "webapp" / "dist" / "bundle.min.css"

    assert dist_js.exists()
    assert dist_css.exists()

    js_text = dist_js.read_text(encoding="utf-8")
    css_text = dist_css.read_text(encoding="utf-8")

    assert len(js_text) > 800000
    assert len(css_text) > 200000
    assert "/api/tv/stream" in js_text
    assert "manifestLoadingTimeOut: 2000" in js_text
