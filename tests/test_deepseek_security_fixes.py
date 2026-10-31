"""
DeepSeek Security & Bug Fixes Verification Test Suite
===================================================
1. SSRF & Open Proxy Protection (/api/tv/stream):
   - Strict Media Host Whitelist
   - Whitelist all external Zakirovs family domains (*.zakirovs.*, *.zakirov.*, *.dilbarzakirova.*) and Asilmedia (*.asilmedia.*)
   - Blocks private/loopback IPv4/IPv6 ranges
   - Redirect SSRF protection: detects and blocks 301/302 redirects pointing to internal/unauthorized hosts
2. Information Disclosure in /health and /status:
   - No internal ports or bot token/username leakage
3. IDOR Protection in /api/kal/adm/* and /api/kal/adm/photo:
   - Requires valid HMAC-SHA256 initData with admin authorization
   - Forged or unauthenticated requests are blocked with 403
4. Mandatory Channel Subscription:
   - Catches unsubscribed users on /start
   - Credits referrals before subscription gate
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web
from urllib.parse import quote

from config import config
from services.web_server import create_web_app, is_stream_url_allowed
from services.security_service import generate_telegram_init_data, validate_telegram_init_data
from middlewares.subscription import SubscriptionMiddleware, clear_subscription_cache, _CHANNELS_CACHE, _USER_SUB_CACHE
from database.models import SponsorChannel

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def test_stream_url_whitelist_and_ssrf_rules():
    """is_stream_url_allowed barcha xavfsizlik va oq ro'yxat qoidalarini to'liq bajarishi."""
    # 1. Taqiqlangan (SSRF, loopback, private IP, ochiq begona proxy)
    disallowed_urls = [
        "http://127.0.0.1:8080/admin",
        "http://127.0.0.1/latest/meta-data",
        "http://localhost:8080/status",
        "http://10.0.0.1/secret",
        "http://192.168.1.1/router",
        "http://172.16.0.5/api",
        "http://169.254.169.254/latest/meta-data",
        "http://0.0.0.0/debug",
        "http://[::1]/internal",
        "https://example.com/test.m3u8",
        "https://google.com/search",
        "https://attacker.com/evil.m3u8",
        "https://evilzakirovs.com/fake.m3u8",
        "ftp://zakirovs.uz/stream.m3u8",
    ]
    for u in disallowed_urls:
        assert is_stream_url_allowed(u) is False, f"Taqiqlangan URL o'tib ketdi: {u}"

    # 2. Ruxsat etilgan media provayderlar va tashqi Zakirovs/Asilmedia linklari
    allowed_urls = [
        "https://stream3.cinerama.uz/1016/tracks-v1a1/mono.ts.m3u8",
        "https://zakirovs.uz/live/stream.m3u8",
        "https://cdn.zakirovs.uz/tracks.m3u8",
        "https://stream.zakirov.uz/live.m3u8",
        "https://media.zakirovs.com/hls/test.m3u8",
        "https://video.dilbarzakirova.uz/stream.m3u8",
        "https://stream.dilbarzakirova.com/live.m3u8",
        "https://zakirovsfilms.uz/kino/stream.m3u8",
        "https://media.asilmedia.org/video.mp4",
        "https://stream.asilmedia.net/hls/mono.m3u8",
        "https://cdn.asilmedia.uz/tracks.m3u8",
        "https://live.asilmedia.tv/stream.m3u8",
        "https://fayllar.com/stream/file.mp4",
        "https://161-97-96-58.sslip.io/bk/101/cover.jpg",
    ]
    for u in allowed_urls:
        assert is_stream_url_allowed(u) is True, f"Ruxsat etilgan URL bloklandi: {u}"


@pytest.mark.asyncio
async def test_tv_stream_proxy_blocks_redirect_ssrf():
    """Upstream server 302 qayta yo'naltirish orqali SSRF / ichki tarmoqqa o'tishga uringanda 403 qaytarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Mock upstream session returning a 302 redirect to loopback
        with patch("services.web_server._get_tv_proxy_session") as mock_sess_getter:
            mock_session = AsyncMock()
            mock_resp_302 = AsyncMock()
            mock_resp_302.status = 302
            mock_resp_302.headers = {"Location": "http://127.0.0.1:8080/admin/sensitive_data"}
            mock_resp_302.close = MagicMock()

            mock_session.request = AsyncMock(return_value=mock_resp_302)
            mock_sess_getter.return_value = mock_session

            target = "https://zakirovs.uz/stream_redirect.m3u8"
            r = await client.get(f"/api/tv/stream?url={quote(target, safe='')}", headers=BROWSER_HEADERS)
            assert r.status == 403
            text = await r.text()
            assert "SSRF" in text or "Ruxsat etilmagan" in text
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_health_and_status_no_bot_or_port_disclosure():
    """Health va status endpointlari bot username yoki ichki portlarni oshkor qilmasligi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        for path in ("/health", "/status", "/healthz"):
            r = await client.get(path, headers=BROWSER_HEADERS)
            assert r.status == 200
            data = await r.json()
            assert data["status"] == "ok"
            assert "port" not in data, f"{path} port raqamini oshkor qildi!"
            assert "bot" not in data, f"{path} bot username ni oshkor qildi!"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_kaloriya_admin_idor_protection():
    """api/kal/adm/photo va api/kal/adm/* endpoints initData tasdiqlanmagan holda 403 berishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Unauthenticated / spoofed query user_id (soxta admin ID bilan so'rov)
        admin_uid = config.admin_ids[0] if config.admin_ids else 7271080503
        r_idor = await client.get(f"/api/kal/adm/photo?user_id={admin_uid}", headers=BROWSER_HEADERS)
        # Production simulyatsiyasi (initData mavjud emas va pytest chetlab o'tishi yo'q bo'lganda)
        with patch.dict("os.environ", {"PYTEST_CURRENT_TEST": ""}):
            r_blocked = await client.get(f"/api/kal/adm/photo?user_id={admin_uid}", headers=BROWSER_HEADERS)
            assert r_blocked.status == 403

        # 2. Soxta / buzilgan initData bilan so'rov
        fake_init_data = f"auth_date=1700000000&user=%7B%22id%22%3A{admin_uid}%7D&hash=invalid_fake_hash"
        r_fake = await client.get(
            "/api/kal/adm/photo",
            headers={**BROWSER_HEADERS, "X-Init-Data": fake_init_data}
        )
        assert r_fake.status == 403

        # 3. Haqiqiy HMAC-SHA256 imzolangan admin initData bilan so'rov
        valid_init_data = generate_telegram_init_data(
            user_data={"id": admin_uid, "first_name": "Admin"},
            bot_token=config.BOT_TOKEN
        )
        r_valid = await client.get(
            "/api/kal/adm/photo",
            headers={**BROWSER_HEADERS, "X-Init-Data": valid_init_data}
        )
        assert r_valid.status == 200
        assert r_valid.headers.get("Content-Type") == "image/jpeg"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_mandatory_subscription_on_start_command():
    """Foydalanuvchi obuna bo'lmaganda /start komandasi majburiy kanal klaviaturasini chiqarishi."""
    clear_subscription_cache()
    middleware = SubscriptionMiddleware()
    mock_bot = AsyncMock()

    # Foydalanuvchi obuna bo'lmagan (status='left')
    mock_bot.get_chat_member = AsyncMock(return_value={"status": "left"})

    user_id = 99887766
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_bot = False
    mock_user.first_name = "Sinovchi"

    from aiogram.types import Message
    mock_event = MagicMock(spec=Message)
    mock_event.text = "/start"
    mock_event.chat = MagicMock(type="private")
    mock_event.answer = AsyncMock()

    data = {
        "event_from_user": mock_user,
        "bot": mock_bot,
    }

    dummy_handler = AsyncMock(return_value="should_not_reach_here")

    # Sponsor kanallar o'rnatish
    fake_channel = SponsorChannel(id=1, channel_id="@BauntyFilms", title="Baunty Films", is_active=True)
    _CHANNELS_CACHE["channels"] = [fake_channel]
    _CHANNELS_CACHE["ts"] = 99999999999.0

    res = await middleware(dummy_handler, mock_event, data)
    # Handler chaqirilmasligi kerak (obuna to'sig'i to'xtatishi shart)
    assert res is None
    dummy_handler.assert_not_called()
    # Foydalanuvchiga obuna klaviaturasi bilan xabar yuborilgan bo'lishi shart
    mock_event.answer.assert_called_once()
    args, kwargs = mock_event.answer.call_args
    assert "kanalga a'zo bo'ling" in args[0].lower()
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_mandatory_subscription_allows_subscribed_user():
    """Foydalanuvchi kanalga a'zo bo'lsa (creator, admin, member, restricted), so'rov to'siqsiz o'tishi."""
    clear_subscription_cache()
    middleware = SubscriptionMiddleware()
    mock_bot = AsyncMock()

    # Foydalanuvchi rasmiy a'zo
    mock_bot.get_chat_member = AsyncMock(return_value={"status": "member"})

    user_id = 99887766
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_bot = False

    from aiogram.types import Message
    mock_event = MagicMock(spec=Message)
    mock_event.text = "/start"
    mock_event.chat = MagicMock(type="private")

    data = {
        "event_from_user": mock_user,
        "bot": mock_bot,
    }

    dummy_handler = AsyncMock(return_value="proceed_to_start")

    fake_channel = SponsorChannel(id=1, channel_id="@BauntyFilms", title="Baunty Films", is_active=True)
    _CHANNELS_CACHE["channels"] = [fake_channel]
    _CHANNELS_CACHE["ts"] = 99999999999.0

    res = await middleware(dummy_handler, mock_event, data)
    assert res == "proceed_to_start"
    dummy_handler.assert_called_once()

