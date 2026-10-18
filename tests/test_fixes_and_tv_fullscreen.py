"""
Testlar: VOICE_MESSAGES_FORBIDDEN fallback, YouTube vs Instagram xizmatlari ajratilishi,
Cobalt xatoliklarini to'g'ri qayta ishlash, favicon 204 va TV Fullscreen funksiyalari.
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, User, Chat
from aiogram.fsm.context import FSMContext
from services.downloader import media_downloader, DownloadResult
from services.web_server import create_web_app
from aiohttp.test_utils import TestClient, TestServer
from config import BASE_DIR


def test_youtube_url_detection():
    """YouTube URL lari aniqlanishi va Instagram/TikTok URL laridan farqlanishi."""
    yt_urls = [
        "https://www.youtube.com/watch?v=pvqgeTiRWEo",
        "https://youtu.be/pvqgeTiRWEo",
        "https://www.youtube.com/shorts/pvqgeTiRWEo",
        "ytsearch:konsta oylama",
    ]
    for u in yt_urls:
        assert media_downloader._is_youtube_url(u) is True

    non_yt_urls = [
        "https://www.instagram.com/syrex_support/",
        "https://www.instagram.com/stories/Mc_f65/",
        "https://www.instagram.com/p/C_q8Wq-oVqW/",
        "https://www.tiktok.com/@user/video/123456789",
        "https://t.me/cinerama_uz",
    ]
    for u in non_yt_urls:
        assert media_downloader._is_youtube_url(u) is False


def test_youtube_id_extraction_strictness():
    """Instagram havolalaridan 11 belgili soxta YouTube video ID ajratilmasligi testi."""
    ig_url = "https://www.instagram.com/syrex_support/"
    # syrex_support (13 ta belgi) hech qachon YouTube ID sifatida olinmasligi kerak
    assert media_downloader._extract_youtube_id(ig_url) is None

    yt_id = media_downloader._extract_youtube_id("https://www.youtube.com/watch?v=pvqgeTiRWEo")
    assert yt_id == "pvqgeTiRWEo"

    yt_short = media_downloader._extract_youtube_id("https://youtu.be/pvqgeTiRWEo")
    assert yt_short == "pvqgeTiRWEo"


def test_invidious_rejects_non_youtube():
    """Invidious va Piped ga Instagram yoki begona havolalar yuborilmasligi testi."""
    res = media_downloader._download_via_invidious("https://www.instagram.com/syrex_support/")
    assert res is None

    res2 = media_downloader._download_via_invidious("https://www.instagram.com/stories/Mc_f65/")
    assert res2 is None


def test_video_fallbacks_instagram_error_message():
    """Instagram havolasi uchun 429 xatosi chiqqanda tushunarli o'zbekcha xabar qaytishi."""
    res = media_downloader._try_video_fallbacks(
        url="https://www.instagram.com/syrex_support/",
        file_prefix="test_123",
        original_err="HTTP Error 429: Too Many Requests"
    )
    assert res.success is False
    assert "429 Too Many Requests" in res.error
    assert "vaqtincha chekladi" in res.error


@pytest.mark.asyncio
async def test_round_video_voice_messages_forbidden_fallback(tmp_path):
    """VOICE_MESSAGES_FORBIDDEN bo'lganda dumaloq videoni video shaklida yuborish testi."""
    from handlers.round_video import state_process_round_video

    mock_message = AsyncMock(spec=Message)
    mock_message.video = MagicMock()
    mock_message.document = None
    mock_message.from_user = User(id=987654, is_bot=False, first_name="TestUser")
    mock_message.chat = Chat(id=987654, type="private")

    status_msg = AsyncMock()
    mock_message.reply = AsyncMock(return_value=status_msg)
    mock_message.bot = AsyncMock()

    # reply_video_note VOICE_MESSAGES_FORBIDDEN xatosini tashlaydi
    mock_message.reply_video_note = AsyncMock(side_effect=TelegramBadRequest(
        method="sendVideoNote",
        message="Bad Request: VOICE_MESSAGES_FORBIDDEN"
    ))
    mock_message.reply_video = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)

    test_dummy_video = str(tmp_path / "dummy.mp4")
    Path(test_dummy_video).write_bytes(b"dummy_video_bytes")

    with patch("services.video_service.video_service.convert_to_round_video", return_value=test_dummy_video):
        await state_process_round_video(mock_message, mock_state)

    # reply_video_note chaqirilgan bo'lishi kerak
    assert mock_message.reply_video_note.called
    # reply_video zaxira sifatida chaqirilgan bo'lishi kerak
    assert mock_message.reply_video.called
    call_kwargs = mock_message.reply_video.call_args[1]
    assert "caption" in call_kwargs
    assert "video xabar (video note) qabul qilish cheklangani" in call_kwargs["caption"]


@pytest.mark.asyncio
async def test_favicon_endpoint_returns_204():
    """/favicon.ico endpointi 404 bermasdan 204 No Content qaytarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/favicon.ico")
        assert resp.status in [200, 204]

        resp_sub = await client.get("/webapp/favicon.ico")
        assert resp_sub.status in [200, 204]
    finally:
        await client.close()


def test_webapp_tv_fullscreen_elements():
    """Mini App index.html da to'liq ekran, 4K UHD va ko'p qurilmalarga mos boshqaruv elementlari mavjudligi."""
    index_file = BASE_DIR / "webapp" / "index.html"
    assert index_file.exists()
    content = index_file.read_text(encoding="utf-8")

    # CSS Pseudo-Fullscreen
    assert ".tv-full-screen-mode" in content
    assert "position:fixed !important" in content

    # HTML boshqaruv elementlari
    assert 'id="fsbar"' in content
    assert 'id="vboxfs"' in content
    assert 'id="fsclose"' in content
    assert 'id="fsname"' in content
    assert "4K UHD" in content

    # JS Funksiyalar
    assert "toggleTVFullscreen" in content
    assert "requestFullscreen" in content
    assert "orientation.lock" in content
