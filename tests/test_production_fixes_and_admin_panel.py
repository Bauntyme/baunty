"""
Production log xatolari (yt-dlp/Audius/Piped/t.me/CGNAT/Asilmedia/Obuna cooldown)
va yangi Admin Panel funksiyalari bo'yicha testlar to'plami.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import config
from database import crud
from database.models import (
    AnonQuestionProfile,
    AnonymousMessage,
    Base,
    DownloadLog,
    Feedback,
    Movie,
    SponsorChannel,
)
from middlewares.subscription import SubscriptionMiddleware, clear_subscription_cache
from services.asilmedia_service import AsilmediaService
from services.downloader import DownloadResult, MediaDownloader
from services.music_service import MusicService
from services.security_service import security_service
from services.web_server import create_web_app


@pytest_asyncio.fixture
async def mem_session():
    """In-memory SQLite async session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def test_unsupported_telegram_profile_url_rejected_immediately(tmp_path):
    """t.me/aiko_64 kabi bare Telegram profil havolalari 0ms da rad etilishi kerak."""
    assert MediaDownloader.is_unsupported_telegram_url("https://t.me/aiko_64") is True
    assert MediaDownloader.is_unsupported_telegram_url("t.me/aiko_64/") is True
    assert MediaDownloader.is_unsupported_telegram_url("https://telegram.me/someone") is True
    assert MediaDownloader.is_unsupported_telegram_url("https://t.me/durov/123") is False
    assert MediaDownloader.is_unsupported_telegram_url("https://t.me/c/1234567/89") is False

    dl = MediaDownloader(download_dir=tmp_path)
    with patch("services.downloader.yt_dlp.YoutubeDL") as mock_ydl:
        res = dl._sync_download_video("https://t.me/aiko_64")
        assert res.success is False
        assert "profil" in (res.error or "").lower()
        mock_ydl.assert_not_called()

        res_aud = dl._sync_download_audio("https://t.me/aiko_64")
        assert res_aud.success is False
        mock_ydl.assert_not_called()


@pytest.mark.asyncio
async def test_music_valid_audio_url_and_resolvers(monkeypatch):
    """Audius HTML sahifa rad etilishi, Audius /stream, SoundCloud transcoding va Piped yechilishi."""
    svc = MusicService()
    assert svc._is_valid_audio_url("https://audius.co/artist/song") is False
    assert svc._is_valid_audio_url("https://api-v2.soundcloud.com/media/123/stream") is False
    assert svc._is_valid_audio_url(
        "https://discoveryprovider.audius.co/v1/tracks/NlV7dpp/stream?app_name=baunty"
    ) is True
    assert svc._is_preview_audio_url("https://cdns-preview-x.dzcdn.net/stream/x.mp3") is True
    assert svc._is_preview_audio_url("https://discoveryprovider.audius.co/v1/tracks/NlV7dpp/stream") is False

    # 1. Audius permalink -> /stream
    monkeypatch.setattr(
        svc,
        "_resolve_audius_permalink",
        AsyncMock(return_value="https://discoveryprovider.audius.co/v1/tracks/abc/stream?app_name=baunty"),
    )
    res_au = await svc.play_track(track_info={"u": "https://audius.co/dj/track", "s": "audius"})
    assert res_au["ok"] is True
    assert "/v1/tracks/abc/stream" in res_au["url"]

    # 2. SoundCloud transcoding -> CDN MP3
    monkeypatch.setattr(
        svc,
        "_resolve_soundcloud_stream",
        AsyncMock(return_value="https://cf-media.sndcdn.com/track.mp3"),
    )
    res_sc = await svc.play_track(
        track_info={"preview": "https://api-v2.soundcloud.com/media/sc/stream/progressive?client_id=x", "s": "sc"}
    )
    assert res_sc["ok"] is True
    assert res_sc["url"] == "https://cf-media.sndcdn.com/track.mp3"

    # 3. YouTube ID bo'lganda yt-dlp yiqilsa -> Piped fallback ishlaydi
    monkeypatch.setattr(svc, "_search_tarona", AsyncMock(return_value=[]))
    monkeypatch.setattr(svc, "_search_deezer", AsyncMock(return_value=[]))
    monkeypatch.setattr(svc, "_search_itunes", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        svc,
        "_resolve_piped_audio_stream",
        AsyncMock(return_value="https://pipedproxy.example/audio.m4a"),
    )

    class _FailYDL:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, *args, **kwargs):
            raise RuntimeError("Failed to extract any player response")

    import sys
    import types
    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=_FailYDL))

    res_yt = await svc.play_track(
        track_info={"id": "dQw4w9WgXcQ", "y": "dQw4w9WgXcQ", "s": "yt", "t": "Test", "a": "Artist"},
        title="Test",
        artist="Artist",
    )
    assert res_yt["ok"] is True
    assert res_yt["source"] == "piped"
    assert res_yt["url"] == "https://pipedproxy.example/audio.m4a"


def test_downloader_node_runtime_and_parallel_fallback(tmp_path):
    """_build_yt_dlp_base_opts node runtime qo'shishi va parallel endpoint fallback ishlashi."""
    dl = MediaDownloader(download_dir=tmp_path)
    with patch("services.downloader.shutil.which", side_effect=lambda x: "/usr/bin/node" if x == "node" else None):
        opts = dl._build_yt_dlp_base_opts(str(tmp_path / "out.%(ext)s"))
        assert opts["js_runtimes"] == {"node": {}}
        assert "player_skip" not in str(opts)

    # Birinchi endpoint yiqilganda qolganlari parallel ishlab natija berishi
    piped_payload = json.dumps({
        "title": "Parallel Video",
        "duration": 95,
        "videoStreams": [{"videoOnly": False, "url": "https://cdn.example.com/v.mp4"}],
    }).encode("utf-8")

    def _fake_urlopen(req, timeout=5):
        url = getattr(req, "full_url", str(req))
        if "piped.private.coffee" in url:
            raise TimeoutError("timed out")
        resp = MagicMock()
        resp.status = 200
        resp.headers = {"Content-Type": "application/json" if "api" in url or "videos" in url else "video/mp4"}
        if "cdn.example.com" in url:
            resp.read = MagicMock(side_effect=[b"MP4DATA" * 40, b""])
        else:
            resp.read = MagicMock(return_value=piped_payload)
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = None
        return resp

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        res = dl._download_via_invidious("https://www.youtube.com/watch?v=dQw4w9WgXcQ", is_audio=False)
        assert res is not None
        assert res.success is True
        assert res.title == "Parallel Video"
        assert res.duration == 95


@pytest.mark.asyncio
async def test_api_asil_colls_never_returns_bare_integer_posters():
    """GET /api/asil/colls hech qachon '5', '131', '54', '11' kabi raqamlarni rasm URL qilmasligi kerak."""
    import services.web_server as ws
    ws._LOCAL_COLLS_CACHE = None

    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.get("/api/asil/colls?limit=10")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        for coll in data.get("items") or []:
            assert not str(coll.get("cov") or "").isdigit()
            for p in coll.get("posters") or []:
                assert not str(p).isdigit()
                assert str(p).startswith(("http://", "https://", "/"))

        # asil.js va bundle.min.js da aniqlanmagan bare `INIT` bo'lmasligi
        asil_src = Path("webapp/asil.js").read_text(encoding="utf-8")
        assert "X-Init-Data': INIT" not in asil_src
        bundle_src = Path("webapp/bundle.min.js").read_text(encoding="utf-8")
        assert "INIT&&" not in bundle_src
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cgnat_python_urllib_no_jail_and_hmac_bypass(monkeypatch):
    """python-urllib so'rovi CGNAT IP ni qamoqqa olmasligi va valid HMAC X-Init-Data o'tishi kerak."""
    security_service.reset()
    cgnat_ip = "62.209.158.125"

    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        # 1. python-urllib -> 403 beradi, lekin IP ban qilinmaydi
        resp = await client.get(
            "/api/init",
            headers={"User-Agent": "Python-urllib/3.12", "X-Forwarded-For": cgnat_ip},
        )
        assert resp.status == 403
        assert security_service.is_ip_banned(cgnat_ip)[0] is False

        # 2. Tajovuzkor skaner (ffuf) bilan bloklangan IP ga ham haqiqiy HMAC X-Init-Data egasi kira olishi
        security_service.ban_ip(cgnat_ip, reason="scanner_ua:ffuf")
        assert security_service.is_ip_banned(cgnat_ip)[0] is True

        # Oddiy so'rov bloklanadi
        resp_blocked = await client.get(
            "/api/catalog",
            headers={"User-Agent": "Mozilla/5.0", "X-Forwarded-For": cgnat_ip},
        )
        assert resp_blocked.status == 403

        # Valid Telegram HMAC initData bilan so'rov bloklanmaydi
        test_token = "123456:TEST_REAL_HMAC_TOKEN_FOR_BYPASS"
        monkeypatch.setattr(config, "BOT_TOKEN", test_token)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

        user_json = json.dumps({"id": 777001, "first_name": "Baunty"})
        pairs = {"auth_date": str(int(time.time())), "query_id": "AAE123", "user": user_json}
        dcs = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        sec_key = hmac.new(b"WebAppData", test_token.encode(), hashlib.sha256).digest()
        hsh = hmac.new(sec_key, dcs.encode(), hashlib.sha256).hexdigest()
        init_data = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in {**pairs, "hash": hsh}.items())

        resp_tg = await client.get(
            "/api/donate?lang=uz",
            headers={
                "User-Agent": "Mozilla/5.0",
                "X-Forwarded-For": cgnat_ip,
                "X-Init-Data": init_data,
            },
        )
        assert resp_tg.status == 200
    finally:
        security_service.reset()
        await client.close()


@pytest.mark.asyncio
async def test_asilmedia_timeout_logs_non_blank_error(caplog):
    """Asilmedia TimeoutError yuz berganda bo'sh log emas, TimeoutError nomi yozilishi kerak."""
    svc = AsilmediaService()
    svc._details_cache.clear()

    with patch("services.asilmedia_service.aiohttp.ClientSession") as mock_sess_cls:
        mock_sess = MagicMock()
        mock_sess.__aenter__ = AsyncMock(return_value=mock_sess)
        mock_sess.__aexit__ = AsyncMock(return_value=False)
        mock_sess.get = MagicMock(side_effect=asyncio.TimeoutError())
        mock_sess_cls.return_value = mock_sess

        with caplog.at_level(logging.WARNING):
            res = await svc.get_movie_details("https://asilmedia.net/9045-kino.html")
            assert res is None
            assert any("TimeoutError" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_subscription_inaccessible_channel_cooldown():
    """member list is inaccessible xatosi 10 daqiqa davomida qayta so'rov yuborishni to'xtatishi kerak."""
    clear_subscription_cache()
    mw = SubscriptionMiddleware()

    bot = MagicMock()
    bot.get_chat_member = AsyncMock(side_effect=Exception("Telegram server says - Bad Request: member list is inaccessible"))

    ch = SponsorChannel(id=1, channel_id="@badchannel", title="Bad", is_active=True)

    async def _handler(event, data):
        return "ok"

    for uid in (1001, 1002, 1003):
        msg = MagicMock(spec=Message)
        msg.from_user = TgUser(id=uid, is_bot=False, first_name="U")
        msg.chat = MagicMock(type="private")
        msg.text = "hello"
        with patch("middlewares.subscription.get_session") as m_sess, \
             patch("middlewares.subscription.crud.get_active_sponsor_channels", new_callable=AsyncMock, return_value=[ch]):
            s = AsyncMock()
            m_sess.return_value.__aenter__.return_value = s
            res = await mw(_handler, msg, {"bot": bot, "event_from_user": msg.from_user})
            assert res == "ok"

    assert bot.get_chat_member.await_count == 1
    clear_subscription_cache()


@pytest.mark.asyncio
async def test_too_big_movie_sends_chat_card():
    """50MB dan katta video Web App dan so'ralganda chatga WebApp + sifat tugmalari bor xabar yuborilishi."""
    from services.web_server import _send_too_big_movie_card

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    delivered = await _send_too_big_movie_card(
        bot=mock_bot,
        user_id=55501,
        code="123",
        part=1,
        stream_info={
            "title": "Avatar: Fire",
            "stream_url": "https://cdn.example.com/1080.mp4",
            "quality_urls": {"1080p": "https://cdn.example.com/1080.mp4", "480p": "https://cdn.example.com/480.mp4"},
            "total_parts": 1,
        },
    )
    assert delivered is True
    mock_bot.send_message.assert_awaited_once()
    kwargs = mock_bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == 55501
    assert "Avatar: Fire" in kwargs["text"]
    assert "50 MB" in kwargs["text"]
    markup = kwargs["reply_markup"]
    btn_texts = [b.text for row in markup.inline_keyboard for b in row]
    assert any("1080p" in t for t in btn_texts)
    assert any("480p" in t for t in btn_texts)


@pytest.mark.asyncio
async def test_admin_crud_and_new_panel_handlers(mem_session: AsyncSession):
    """Yangi Admin CRUD funksiyalari va Foydalanuvchi/WAF/Diagnostika/Analitika handlerlari testi."""
    u1, _ = await crud.get_or_create_user(mem_session, 10001, username="AliDev", first_name="Ali")
    u2, _ = await crud.get_or_create_user(mem_session, 10002, username="ValiBanned", first_name="Vali")
    u1.referral_count = 7
    u1.referral_points = 70
    u2.is_banned = True

    m1 = await crud.create_movie(mem_session, code="701", title="Matrix", file_id="FILE_ID_701")
    m1.views_count = 250
    await crud.create_feedback(mem_session, user_id=10001, username="AliDev", message="Zo'r bot!")
    mem_session.add(AnonQuestionProfile(user_id=10001, token="tkn10001", is_accepting=True))
    mem_session.add(AnonymousMessage(sender_id=10002, recipient_id=10001, message_text="Salom!"))
    await crud.log_download(mem_session, user_id=10001, platform="youtube", query_or_url="https://youtu.be/x")
    await mem_session.commit()

    # CRUD qidiruv va ro'yxatlar
    by_id = await crud.search_user_by_query(mem_session, "10001")
    assert by_id is not None and by_id.username == "AliDev"
    by_uname = await crud.search_user_by_query(mem_session, "@alidev")
    assert by_uname is not None and by_uname.id == 10001
    assert len(await crud.get_recent_users(mem_session, 5)) == 2
    assert [u.id for u in await crud.get_banned_users(mem_session, 5)] == [10002]
    assert [u.id for u in await crud.get_top_referrers(mem_session, 5)] == [10001]

    analytics = await crud.get_admin_extended_analytics(mem_session)
    assert analytics["banned_users_count"] == 1
    assert analytics["referrals_total"] == 7
    assert analytics["anon_total"] == 1
    assert analytics["anon_profiles_count"] == 1
    assert analytics["feedback_total"] == 1
    assert analytics["downloads_24h"] == 1
    assert analytics["top_movies"][0].code == "701"

    # Admin Panel handlerlari
    from handlers import admin as admin_h
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_session():
        yield mem_session

    def _mk_cb(data_str: str):
        cb = MagicMock(spec=CallbackQuery)
        cb.from_user = TgUser(id=99999999, is_bot=False, first_name="Admin")
        cb.data = data_str
        cb.answer = AsyncMock()
        cb.message = MagicMock()
        cb.message.edit_text = AsyncMock()
        cb.message.answer = AsyncMock()
        return cb

    with patch("handlers.admin.is_admin_check", return_value=True), \
         patch("handlers.admin.get_session", side_effect=_fake_session):
        # 1. Users menu + recent + ban toggle
        cb_users = _mk_cb("admin:users")
        state = FSMContext(storage=MemoryStorage(), key=MagicMock())
        await admin_h.cb_admin_users(cb_users, state)
        assert "Foydalanuvchilar boshqaruvi" in cb_users.message.edit_text.call_args[0][0]

        cb_toggle = _mk_cb("admin:users:ban_toggle:10001")
        await admin_h.cb_admin_users_ban_toggle(cb_toggle)
        refreshed = await crud.get_user(mem_session, 10001)
        assert refreshed.is_banned is True

        # 2. Analytics
        cb_an = _mk_cb("admin:analytics")
        await admin_h.cb_admin_analytics(cb_an)
        an_txt = cb_an.message.edit_text.call_args[0][0]
        assert "Matrix" in an_txt
        assert "r bot!" in an_txt

        # 3. Security WAF + unban_all
        security_service.ban_ip("203.0.113.5", reason="scanner_ua:sqlmap")
        cb_sec = _mk_cb("admin:security")
        await admin_h.cb_admin_security(cb_sec)
        assert "203.0.113.5" in cb_sec.message.edit_text.call_args[0][0]

        cb_unban = _mk_cb("admin:security:unban_all")
        await admin_h.cb_admin_security_unban_all(cb_unban)
        assert security_service.get_banned_ips() == []

        # 4. Diagnostics + clear cache
        cb_diag = _mk_cb("admin:diagnostics")
        await admin_h.cb_admin_diagnostics(cb_diag)
        assert "yt-dlp versiyasi" in cb_diag.message.edit_text.call_args[0][0]

        from services import web_server as ws
        ws._PLAY_STREAM_CACHE["k"] = (time.monotonic(), "https://example.com/a.mp3")
        cb_clr = _mk_cb("admin:diag:clear_media_cache")
        await admin_h.cb_admin_diag_clear_media_cache(cb_clr)
        assert len(ws._PLAY_STREAM_CACHE) == 0

        # 5. FSM qidiruv
        msg = MagicMock(spec=Message)
        msg.from_user = TgUser(id=99999999, is_bot=False, first_name="Admin")
        msg.text = "@AliDev"
        msg.answer = AsyncMock()
        await state.set_state(admin_h.AdminUserStates.waiting_for_user_id)
        await admin_h.process_admin_user_lookup(msg, state)
        assert "10001" in msg.answer.call_args[0][0]
        assert await state.get_state() is None
