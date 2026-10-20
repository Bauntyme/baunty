"""
TV 1440p QHD sifati, past internetda ham tez ochilish (Instant Startup)
va barcha telekanallar (Zo'r TV, Sevimli, Milliy, MY5, BIZ Cinema va b.)
oqimlari va zaxira manbalari uchun keng qamrovli testlar.
"""
import pytest
from aiohttp.test_utils import TestClient, TestServer
from services.web_server import create_web_app
from services.tv_data import CHANNELS_LIST
from config import BASE_DIR


def test_tv_data_zor_tv_and_backup_streams():
    """Zo'r TV va boshqa asosiy telekanallar zaxira oqimlari tartibi va 1440p/4K sifatini tekshirish."""
    by_name = {c["name"]: c for c in CHANNELS_LIST}

    # 1. Zo'r TV (zor.tv / 1016)
    zor_tv = by_name.get("Zo'r TV")
    assert zor_tv is not None, "Zo'r TV telekanali CHANNELS_LIST da topilmadi"
    assert "1016" in zor_tv["stream"]
    assert "cinerama.uz" in zor_tv["stream"]
    assert "4K UHD" in zor_tv["q"]
    # Zaxira havolalari orasida playlist.m3u8 1-zaxira sifatida mavjudligi
    assert len(zor_tv["u"]) >= 3
    assert "tracks-v1a1" in zor_tv["u"][0][1]
    assert "playlist.m3u8" in zor_tv["u"][1][1]

    # 2. BIZ Cinema, Sevimli, Milliy, MY5, Renessans, Insayt
    for ch_name in ["BIZ Cinema", "Sevimli TV", "Milliy TV", "Mening Yurtim (MY5)", "Renessans TV", "Insayt TV"]:
        ch = by_name.get(ch_name)
        assert ch is not None, f"{ch_name} kanali topilmadi"
        assert len(ch["u"]) >= 3, f"{ch_name} da zaxira havolalari kam"
        assert "playlist.m3u8" in ch["u"][1][1], f"{ch_name} da playlist.m3u8 1-zaxirada emas"


def test_webapp_hls_instant_startup_and_adaptive_bitrate():
    """WebApp HLS konfiguratsiyasida majburiy qotirishlar yo'qligi va past internet uchun moslashuvchanlik."""
    index_file = BASE_DIR / "webapp" / "index.html"
    app_file = BASE_DIR / "webapp" / "app.js"
    js_app_file = BASE_DIR / "webapp" / "js" / "app.js"

    assert index_file.exists()
    assert app_file.exists()
    assert js_app_file.exists()

    index_html = index_file.read_text(encoding="utf-8")
    app_js = app_file.read_text(encoding="utf-8")
    js_app = js_app_file.read_text(encoding="utf-8")

    # 1. Sifat nishonlari 1440p QHD
    assert "1440p QHD" in index_html
    assert 'id="tv4kbadge"' in index_html
    assert 'id="tvq"' in index_html

    # 2. Qotirib qo'yilgan currentLevel yo'qligi (Adaptive Bitrate faol)
    assert "hls.currentLevel = bestIdx;" not in index_html
    assert "hls.currentLevel = topLvl;" not in app_js
    assert "hls.currentLevel = -1;" in index_html
    assert "hls.currentLevel = -1;" in app_js

    # 3. Past internetda ham zudlik bilan ochilish va kam kechikish sozlamalari
    assert "startFragPrefetch: true" in index_html
    assert "liveSyncDurationCount: 2" in index_html
    assert "liveMaxLatencyDurationCount: 5" in index_html
    assert "startFragPrefetch: true" in app_js
    assert "liveSyncDurationCount: 2" in app_js

    # 4. Past internetda tracks-v1a1 dan playlist.m3u8 ga avtomatik o'tish mexanizmi
    assert 'tracks-v1a1/mono.ts.m3u8", "playlist.m3u8"' in index_html
    assert 'tracks-v1a1/mono.ts.m3u8", "playlist.m3u8"' in app_js

    # 5. Tasvir tiniqligi filtrlari
    assert "contrast(1.06) saturate(1.05)" in index_html
    assert "-webkit-optimize-contrast" in index_html
    assert "contrast(1.06) saturate(1.05)" in app_js

    # 6. js/app.js da minAutoLevel 0 qilinganligi (cheksiz pastga tushish imkoni)
    assert "this.hls.minAutoLevel = 0;" in js_app


@pytest.mark.asyncio
async def test_tv_api_endpoint_delivers_1440p_and_backups():
    """Web Server /api/tv endpointi 150+ kanal va to'liq oqim ma'lumotlarini qaytarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/tv")
        assert resp.status == 200
        data = await resp.json()
        assert "items" in data or "channels" in data
        items = data.get("items") or data.get("channels")
        assert len(items) >= 150

        # Zo'r TV ma'lumotlari
        zor_items = [ch for ch in items if ch.get("name") == "Zo'r TV" or ch.get("n") == "Zo'r TV"]
        assert len(zor_items) == 1
        zor = zor_items[0]
        assert "1016" in (zor.get("stream") or zor.get("u")[0][1])
        assert len(zor.get("u", [])) >= 2
    finally:
        await client.close()
