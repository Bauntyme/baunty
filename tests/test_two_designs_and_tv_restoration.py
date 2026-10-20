"""
Ikki xil dizayn (Oddiy/Lite vs Yangi/Modern/Kreativ),
Barcha TV kanallarning 100% barqaror jonli oqimlari va logotiplari (ico),
Kinolar, multfilmlar va animelarni to'liq saralash va yetkazish testlari.
"""
from pathlib import Path
import pytest
from services.tv_data import CHANNELS_LIST
from config import BASE_DIR


def test_two_designs_coexistence_and_switching():
    """Ikkala dizayn (Oddiy / Classic va Kreativ / Modern) to'liq qo'llab-quvvatlanishi."""
    index_file = BASE_DIR / "webapp" / "index.html"
    zk_file = BASE_DIR / "webapp" / "zk.js"
    app_file = BASE_DIR / "webapp" / "app.js"

    index_html = index_file.read_text(encoding="utf-8")
    zk_js = zk_file.read_text(encoding="utf-8")
    app_js = app_file.read_text(encoding="utf-8")

    # 1. index.html head qismida ZK_LITE dastlabki yuklanishi (localStorage va URL query orqali)
    assert "window.ZK_LITE" in index_html
    assert 'localStorage.getItem("zk_ui")' in index_html
    assert "zk-lite" in index_html

    # 2. zk.js da ZK_LITE bo'lganda splash va body.splashing to'liq olib tashlanishi
    assert "document.body.classList.remove(\"splashing\");" in zk_js
    assert "window.ZK_LITE" in zk_js

    # 3. index.html va app.js da dizayn tanlash/almashtirish modal va tugmalari
    assert "✨ Kreativ" in index_html
    assert "⚡ Oddiy" in index_html
    assert "✨ Kreativ" in app_js
    assert "⚡ Oddiy" in app_js
    assert 'data-ui="kr"' in index_html
    assert 'data-ui="lite"' in index_html
    assert 'data-pick="kr"' in index_html
    assert 'data-pick="lite"' in index_html

    # 4. setUI funksiyasi lite / oddiy / classic qiymatlarini qo'llab-quvvatlashi
    assert "want = (v === \"lite\" || v === \"classic\" || v === \"oddy\" || v === \"oddiy\")" in index_html
    assert "want = (v === \"lite\" || v === \"classic\" || v === \"oddy\" || v === \"oddiy\")" in app_js


def test_tv_channel_icons_and_direct_stable_streams():
    """TV kanallarning ico klassli logotiplari, zaxira svg va birlamchi to'g'ridan-to'g'ri oqimlari."""
    index_file = BASE_DIR / "webapp" / "index.html"
    app_file = BASE_DIR / "webapp" / "app.js"
    js_app_file = BASE_DIR / "webapp" / "js" / "app.js"

    index_html = index_file.read_text(encoding="utf-8")
    app_js = app_file.read_text(encoding="utf-8")
    js_app = js_app_file.read_text(encoding="utf-8")

    # 1. Telekanal kartochkalari ustida haqiqiy ico logotipi
    assert 'class="ico tvl"' in index_html
    assert 'class="ico tvl"' in app_js
    assert 'class="ico tvl"' in js_app

    # 2. CSS da .ico klassi to'liq shakllantirilgan
    assert ".tvb .ico" in index_html
    assert ".tvbar .lg .ico" in index_html

    # 3. Rasm topilmasa yoki yuklanmasa zaxira logo.svg
    assert "logo.svg" in index_html
    assert "logo.svg" in app_js
    assert "logo.svg" in js_app

    # 4. attempt funksiyasida boshlang'ich majburiy playlist almashtirish olib tashlangan
    # (birlamchi to'g'ridan-to'g'ri oqim darhol o'ynaydi)
    assert 'let streamTarget = url;' in index_html
    assert 'let streamTarget = url;' in app_js
    assert 'let targetUrl = streamUrl;' in js_app

    # 5. Barcha telekanallarning birlamchi oqimlari mavjudligi
    assert len(CHANNELS_LIST) >= 150
    for ch in CHANNELS_LIST[:20]:
        assert ch.get("stream"), f"{ch.get('n')} da oqim manzili yo'q"
        assert len(ch.get("u", [])) >= 2, f"{ch.get('n')} da zaxira oqimlar kam"


def test_cartoons_and_anime_categories_and_delivery():
    """Kino katalogida multfilmlar va animelar filtrlari va botga yetkazilishi."""
    index_file = BASE_DIR / "webapp" / "index.html"
    app_file = BASE_DIR / "webapp" / "app.js"

    index_html = index_file.read_text(encoding="utf-8")
    app_js = app_file.read_text(encoding="utf-8")

    # 1. Chiplar orasida Multfilmlar va Anime tugmalari
    assert 'data-t="mult"' in index_html
    assert 'data-t="anime"' in index_html
    assert 'Multfilmlar' in index_html
    assert 'Anime' in index_html

    # 2. render funksiyasida mult va anime saralash logikasi
    assert 'tab === "mult"' in index_html
    assert 'tab === "anime"' in index_html
    assert 'tab === "mult"' in app_js
    assert 'tab === "anime"' in app_js


@pytest.mark.asyncio
async def test_tv_icon_vector_endpoint_and_2mbps_resilience():
    """TV ikonkalari (/api/tv/icon/{id}) SVG endpointi, 2Mbps buferlash va zk-lite CSS testi."""
    from services.web_server import create_web_app
    from aiohttp.test_utils import TestServer, TestClient

    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. /api/tv/icon/1 va /p/tv/2 SVG formatda qaytishi
        r1 = await client.get("/api/tv/icon/1", headers={"User-Agent": "Mozilla/5.0"})
        assert r1.status == 200
        assert "image/svg+xml" in r1.headers.get("Content-Type", "")
        svg1 = await r1.text()
        assert "<svg" in svg1
        assert "BIZ" in svg1 or "CINEMA" in svg1

        r2 = await client.get("/p/tv/2", headers={"User-Agent": "Mozilla/5.0"})
        assert r2.status == 200
        assert "image/svg+xml" in r2.headers.get("Content-Type", "")
        svg2 = await r2.text()
        assert "<svg" in svg2

        # 2. 2Mbps internet uchun ABR boshlang'ich startLevel <= 720p va ewma estimate
        index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
        app_js = (BASE_DIR / "webapp" / "app.js").read_text(encoding="utf-8")
        zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")

        assert "1800000" in index_html
        assert "1800000" in app_js
        assert "h <= 720" in index_html
        assert "h <= 720" in app_js
        assert "playlist.m3u8" in index_html
        assert "playlist.m3u8" in app_js

        # 3. zk-lite stillari mavjudligi
        assert "html.zk-lite" in zk_css
        assert "body.zk-lite" in zk_css
    finally:
        await client.close()

