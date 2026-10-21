"""
🚗 Prava rasmlari, 💛 9860 Donat, 🎬 Haqiqiy kinolar yetkazish va 📺 1440p QHD TV testlari.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from aiohttp.test_utils import TestClient, TestServer

from config import config, BASE_DIR
from services.prava_service import prava_service
from services.web_server import create_web_app
from services.movie_service import movie_service, VERIFIED_CDN_VIDEO_POOL


def test_prava_real_images_mapped():
    """Prava xizmatida 700+ haqiqiy rasm savollarga to'g'ri bog'langanligini tekshirish."""
    home = prava_service.get_home_data()
    assert home["ok"] is True
    # Haqiqiy rasmlar soni kamida 700 ta
    assert home["img"] >= 700

    # Rasmli savollar to'plami
    img_set = prava_service.get_set(kind="img")
    assert img_set["ok"] is True
    assert len(img_set["qs"]) == 20
    for q in img_set["qs"]:
        assert q.get("img") is not None
        assert q["img"].startswith("prava/")
        assert q["img"].endswith(".webp")


@pytest.mark.asyncio
async def test_prava_image_proxy_endpoints():
    """Web server /prava/{id}.webp va /pv/{id}.webp endpointlari to'g'ri ishlashini tekshirish."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. /prava/1.webp
        resp1 = await client.get("/prava/1.webp")
        assert resp1.status == 200
        assert "image/webp" in resp1.headers.get("Content-Type", "")
        body1 = await resp1.read()
        assert len(body1) > 1000

        # 2. /webapp/prava/1.webp
        resp2 = await client.get("/webapp/prava/1.webp")
        assert resp2.status == 200
        assert "image/webp" in resp2.headers.get("Content-Type", "")

        # 3. /pv/1.webp (alias)
        resp3 = await client.get("/pv/1.webp")
        assert resp3.status == 200
        assert "image/webp" in resp3.headers.get("Content-Type", "")

        # 4. Mavjud bo'lmagan rasm
        resp4 = await client.get("/prava/9999999.webp")
        assert resp4.status == 404
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_donate_card_xaydarov_biloliddin():
    """Donat bo'limida 9860 1766 1922 0088 Xaydarov Biloliddin ma'lumotlari to'g'riligi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/donate")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert data["on"] is True
        assert data["num"] == "9860 1766 1922 0088"
        assert data["name"] == "Xaydarov Biloliddin"
        assert data["net"] == "Humo"
        assert len(data["cards"]) >= 1
        assert data["cards"][0]["num"] == "9860 1766 1922 0088"
        assert data["cards"][0]["name"] == "Xaydarov Biloliddin"
    finally:
        await client.close()


def test_no_intel_iot_debug_videos():
    """VERIFIED_CDN_VIDEO_POOL va data/video_sources.json da AI car detection debug videolari yo'qligi."""
    # 1. VERIFIED_CDN_VIDEO_POOL tekshiruvi
    for item in VERIFIED_CDN_VIDEO_POOL:
        url = item.get("url", "")
        assert "intel-iot-devkit" not in url
        assert "person-bicycle-car-detection" not in url
        assert "face-demographics" not in url
        assert "car-detection" not in url
        assert "classroom" not in url
        assert "head-pose" not in url

    # 2. data/video_sources.json tekshiruvi
    sources_path = BASE_DIR / "data" / "video_sources.json"
    if sources_path.exists():
        text = sources_path.read_text(encoding="utf-8")
        assert "intel-iot-devkit" not in text
        assert "person-bicycle-car-detection" not in text


@pytest.mark.asyncio
async def test_movie_delivery_branding_and_sources():
    """Kinolar yetkazilganda Bauntys brendi va to'g'ri oqim bilan yuborilishi."""
    bot_mock = AsyncMock()
    sent_mock = MagicMock()
    sent_mock.video = MagicMock(file_id="BAACAgIAAxkBAAE_SAMPLE_REAL_717", duration=90, file_size=12000000)
    bot_mock.send_video = AsyncMock(return_value=sent_mock)
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    res = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=12345678,
        code="284",
        part=1
    )
    assert res is True
    #send_video yoki send_photo chaqirilgan
    assert bot_mock.send_video.called or bot_mock.send_photo.called
    kwargs = bot_mock.send_video.call_args.kwargs if bot_mock.send_video.called else bot_mock.send_photo.call_args.kwargs
    caption = kwargs.get("caption", "")
    assert config.CHANNEL_USERNAME in caption
    assert config.BOT_USERNAME.lstrip("@") in caption
    assert "Zakirov" not in caption


def test_tv_hls_high_res_and_smooth():
    """TV playerda 1440p / 1080p yuqori sifat va silliq (smooth) buferlash sozlamalari tekshiruvi."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    app_js = (BASE_DIR / "webapp" / "app.js").read_text(encoding="utf-8")

    # 1. 1440p QHD nishonlari
    assert "1440p QHD" in index_html
    assert "1440p QHD" in app_js

    # 2. Sifatni 720p ga majburiy pasaytirish yo'qligi
    assert "if (h <= 720) targetIdx = i;" not in index_html
    assert "if (h <= 720) targetIdx = i;" not in app_js

    # 3. autoLevelCapping -1
    assert "hls.autoLevelCapping = -1;" in index_html
    assert "hls.currentLevel = -1;" in index_html
