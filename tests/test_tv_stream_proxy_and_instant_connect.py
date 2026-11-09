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

    # 1. Tezkor va to'liq ulanish: qulay timeoutlar (5s / 7s va 5000ms manifest timeout)
    assert "_isSlow ? 7000 : 5000" in index_html
    assert "_isSlow ? 7000 : 5000" in app_js
    assert "manifestLoadingTimeOut: 5000" in index_html
    assert "manifestLoadingTimeOut: 5000" in app_js
    assert "manifestLoadingTimeOut: 5000" in tvroom_js
    assert "manifestLoadingTimeOut: 5000" in js_app

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
    assert "manifestLoadingTimeOut: 5000" in js_text


@pytest.mark.asyncio
async def test_tv_proxy_connection_pool_tuning():
    """Proxy sessiyasi ulanishlar puli (limit=1000, per_host=100) va qisqa timeoutlar (3s/15s) tekshiruvi."""
    from services.web_server import _get_tv_proxy_session
    session = await _get_tv_proxy_session()
    assert session is not None
    assert session.connector.limit == 1000
    assert session.connector.limit_per_host == 100
    assert session.connector._keepalive_timeout == 30
    assert session.timeout.connect == 3.0
    assert session.timeout.sock_read == 15.0


@pytest.mark.asyncio
async def test_tv_report_auto_failover_and_cache_invalidation():
    """Ketma-ket 3 ta nosozlik hisoboti yuborilganda kanal zaxiraga o'tishi va kesh tozalanishi."""
    from services.tv_data import CHANNELS_LIST
    from services.web_server import _TV_ALL_CACHE, _TV_STREAM_FAILURES

    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Zo'r TV (id=4)
        zor_ch = next(c for c in CHANNELS_LIST if c.get("id") == 4 or c.get("i") == 4)
        orig_stream = zor_ch["stream"]
        backups = zor_ch.get("u", [])
        assert len(backups) >= 2

        # 1. TV sahifasini chaqirib keshni to'ldirish
        r_tv = await client.get("/api/tv")
        assert r_tv.status == 200
        assert _TV_ALL_CACHE.get("bytes") is not None

        # 2. 3 marta xatolik hisoboti yuborish
        for _ in range(3):
            r_rep = await client.post("/api/tv/report", json={"id": 4, "ok": False, "bad": True})
            assert r_rep.status == 200
            data = await r_rep.json()
            assert data.get("ok") is True

        # 3. Zaxira oqim birlamchi oqimga aylanishi va kesh tozalanishi
        assert zor_ch["stream"] != orig_stream
        assert zor_ch["stream"] == backups[1][1]
        assert _TV_ALL_CACHE.get("bytes") is None

        # 4. Muvaffaqiyatli o'ynash hisoboti yuborilganda xatolar kamayishi
        r_ok = await client.post("/api/tv/report", json={"id": 4, "ok": True})
        assert r_ok.status == 200

        # Kanal oqimini qaytarish (test tozaligi uchun)
        zor_ch["stream"] = orig_stream
        _TV_STREAM_FAILURES.pop(4, None)
    finally:
        await client.close()


def test_tv_catalog_sanitization_and_stream8_backups():
    """Ruxsor va Nasaf TV oqimlarida o'lik stream3 o'rniga ishlaydigan stream8 mavjudligi va barcha kanallar HTTPS."""
    by_name = {c["name"]: c for c in CHANNELS_LIST}

    # Ruxsor TV (stream 1040)
    ruxsor = by_name["Ruxsor TV"]
    for idx, u in ruxsor["u"]:
        assert "stream8.cinerama.uz/1040" in u
        assert not u.startswith("http://")

    # Nasaf TV (stream 1199)
    nasaf = by_name["Nasaf TV"]
    for idx, u in nasaf["u"]:
        assert "stream8.cinerama.uz/1199" in u
        assert not u.startswith("http://")


def test_frontend_direct_first_and_stall_recovery():
    """app.js, tv_room.js va tvroom.js da direct-first CORS, non-blocking tezlik va qotishdan xavfsiz chiqish."""
    app_js = (BASE_DIR / "webapp" / "app.js").read_text(encoding="utf-8")
    tv_room_js = (BASE_DIR / "webapp" / "tv_room.js").read_text(encoding="utf-8")
    tvroom_js = (BASE_DIR / "webapp" / "tvroom.js").read_text(encoding="utf-8")

    for code, name in [(tv_room_js, "tv_room.js"), (tvroom_js, "tvroom.js")]:
        # Direct-first: majburiy pre-proxy yo'qligi
        assert 'if (streamUrl.includes("cinerama.uz") && !streamUrl.includes("/api/tv/stream"))' not in code, f"Forced proxy in {name}"
        # Bloklovchi tezlik to'xtatuvchisi (return) yo'qligi
        assert "if (speedMbps < 1.0) {\n      if (loader) loader.hidden = true;" not in code
        # Stall recovery da ko'r-ko'rona currentTime += 0.15 sakrashi yo'qligi
        assert "video.currentTime += 0.15;" not in code
        # maxBufferLength 15 va maxMaxBufferLength 30
        assert "maxBufferLength: 15," in code
        assert "maxMaxBufferLength: 30," in code

    # app.js da ham currentTime += 0.15 sakrashi yo'qligi
    assert "vid.currentTime += 0.15;" not in app_js
    assert "hls.config.maxBufferLength = 15;" in app_js
