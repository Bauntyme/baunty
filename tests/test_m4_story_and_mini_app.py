"""
Milestone M4 Test Suite: Anonymous Story Feature Fix & Mini App
Verifies:
1. Telegram story URL sanitization and normalization:
   - Emoji URLs (protocol-relative //telegram.org/img/emoji/... or absolute) filtered out.
   - Stickers and tgme internal UI resources filtered out.
   - Protocol-relative URLs starting with '//' normalized to 'https:'.
   - Empty, whitespace, or invalid URLs safely rejected.
2. Ghost / blank item elimination:
   - get_telegram_stories returns genuine items or empty list [] (never dummy items with "u": "").
   - get_user_profile_and_stories filters out items with empty direct_url.
3. Scraper error handling:
   - Private profiles, rate limits (429), and not-found profiles return clean error responses.
   - fetch_stories catches unexpected exceptions without crashing callers.
4. Story Level 1 menu & handlers:
   - story_platform_keyboard returns Level 1 buttons:
     Row 1: [📱 Telegram story] (story_platform:tg), [📸 Instagram story] (story_platform:ig)
     Row 2: [⬅️ Asosiy menyu] (story_platform:menu)
     Optional Mini App button [📱 Mini Appda ko'rish] when WebApp URL is configured.
   - cb_story_platform_menu clears FSM state and sends main menu keyboard.
   - cb_story_platform routes 'tg' and 'ig' to waiting_for_username state.
5. Mini App source code fixes:
   - webapp/story.js has zero calls to undefined segHTML() and uses rootHead() in watchHTML and savedHTML.
   - webapp/zk.css has body.zk>.top with z-index: 1000 and position: sticky.
6. Web server story endpoint integration:
   - /api/story/tg and /api/story/ig endpoints return sanitized JSON responses without ghost items.
"""
import io
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiohttp import web
from aiogram.types import CallbackQuery, Message, User, Chat, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from config import config
from services.downloader import DownloadResult
from services.story_service import story_service, normalize_and_validate_media_url
from keyboards.inline import story_platform_keyboard
from handlers.story import cb_story_platform, cb_story_platform_menu, cmd_story_prompt
from utils.states import StoryStates


# ===========================================================================
# 1. URL Sanitization and Normalization Tests
# ===========================================================================

def test_normalize_and_validate_media_url_emoji_filtering():
    """Emoji havolalari qat'iy filtrlanishi va rad etilishi kerak."""
    # Protocol-relative emoji links
    assert normalize_and_validate_media_url("//telegram.org/img/emoji/40/e29da4.png") is None
    assert normalize_and_validate_media_url("//telegram.org/img/emoji/100/1f600.png") is None

    # Absolute emoji links
    assert normalize_and_validate_media_url("https://telegram.org/img/emoji/40/2764.png") is None
    assert normalize_and_validate_media_url("http://telegram.org/img/emoji/custom.png") is None

    # Path-based emoji links
    assert normalize_and_validate_media_url("/img/emoji/heart.png") is None
    assert normalize_and_validate_media_url("/emoji/smile.png") is None

    # Stiker va tgme ichki resurslari
    assert normalize_and_validate_media_url("//telegram.org/img/stickers/pack1.webp") is None
    assert normalize_and_validate_media_url("https://telegram.org/img/website_icon.svg") is None
    assert normalize_and_validate_media_url("//tgme/channel_icon.png") is None


def test_normalize_and_validate_media_url_protocol_relative_normalization():
    """Haqiqiy media havolalari to'g'ri 'https:' bilan normallashtirilishi kerak."""
    # Video files
    res_v = normalize_and_validate_media_url("//cdn.telesco.pe/file/video_123.mp4")
    assert res_v == "https://cdn.telesco.pe/file/video_123.mp4"

    # Photo files
    res_p = normalize_and_validate_media_url("//cdn.telesco.pe/file/photo_456.jpg")
    assert res_p == "https://cdn.telesco.pe/file/photo_456.jpg"

    # Relative paths
    res_rel = normalize_and_validate_media_url("/file/media.mp4", base_domain="t.me")
    assert res_rel == "https://t.me/file/media.mp4"

    # Allaqachon to'liq URL bo'lsa
    res_abs = normalize_and_validate_media_url("https://cdn4.telesco.pe/file/vid.mp4")
    assert res_abs == "https://cdn4.telesco.pe/file/vid.mp4"

    # Bo'sh yoki yaroqsiz qiymatlar
    assert normalize_and_validate_media_url("") is None
    assert normalize_and_validate_media_url("   ") is None
    assert normalize_and_validate_media_url(None) is None


# ===========================================================================
# 2. Telegram Story Sanitization & Ghost Item Elimination Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_get_telegram_stories_sanitization_and_no_ghost_items():
    """Telegram kanal hikoyalarini olishda emoji filtrlanishi va faqat toza media olinishi testi."""
    html_sample = """
    <div class="tgme_page_title"><span dir="auto">Baunty Channel</span></div>
    <img class="tgme_page_photo_image" src="//cdn.telesco.pe/avatars/baunty.jpg">
    <div class="tgme_widget_message_text">Check our latest updates!</div>
    <video src="//cdn.telesco.pe/file/valid_video_1.mp4"></video>
    <div style="background-image:url('//telegram.org/img/emoji/40/e29da4.png')"></div>
    <div style="background-image:url('//telegram.org/img/stickers/cat.webp')"></div>
    <div style="background-image:url('//cdn.telesco.pe/file/valid_photo_1.jpg')"></div>
    """

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = html_sample.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    story_service._profile_cache.clear()
    with patch("urllib.request.urlopen", return_value=mock_resp):
        data = await story_service.get_telegram_stories("baunty_test")

    assert data["ok"] is True
    assert data["name"] == "Baunty Channel"
    assert data["pic"] == "https://cdn.telesco.pe/avatars/baunty.jpg"

    items = data["items"]
    assert len(items) == 2  # 1 video, 1 image (emojilar va stikerlar chiqarib tashlangan)

    # Barcha itemlarning URL'lari to'liq 'https://' bilan boshlanishi va bo'sh emasligi
    for it in items:
        assert it["u"].startswith("https://")
        assert "emoji" not in it["u"]
        assert "sticker" not in it["u"]
        assert it["u"] != ""

    assert items[0]["k"] == "video"
    assert items[0]["u"] == "https://cdn.telesco.pe/file/valid_video_1.mp4"
    assert items[1]["k"] == "image"
    assert items[1]["u"] == "https://cdn.telesco.pe/file/valid_photo_1.jpg"


@pytest.mark.asyncio
async def test_get_telegram_stories_empty_channel_no_ghost_items():
    """Bo'sh kanalda hech qachon 'u': '' bo'lgan soxta (ghost) item qaytmasligi kerak."""
    empty_html = """
    <div class="tgme_page_title"><span dir="auto">Empty Channel</span></div>
    <img class="tgme_page_photo_image" src="//cdn.telesco.pe/avatars/empty.jpg">
    <div class="tgme_page_description">Nothing here yet.</div>
    """

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = empty_html.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    story_service._profile_cache.clear()
    with patch("urllib.request.urlopen", return_value=mock_resp):
        data = await story_service.get_telegram_stories("empty_channel")

    assert data["ok"] is True
    assert data["name"] == "Empty Channel"
    assert data["items"] == []  # Bo'sh ro'yxat, ghost item yo'q!
    # "u": "" bo'lgan hech qanday item yo'qligini tekshiramiz
    assert not any(it.get("u") == "" for it in data["items"])


@pytest.mark.asyncio
async def test_fetch_telegram_stories_sanitizes_download_urls():
    """fetch_telegram_stories funksiyasida emoji havolalari download qilinmasligi testi."""
    html_sample = """
    <video src="//cdn.telesco.pe/file/clip.mp4"></video>
    <div style="background-image:url('//telegram.org/img/emoji/40/fire.png')"></div>
    <div style="background-image:url('//cdn.telesco.pe/file/pic.jpg')"></div>
    """
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = html_sample.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    downloaded_urls = []

    def mock_download_direct_stream(url, is_audio=False, title=""):
        downloaded_urls.append(url)
        return DownloadResult(success=True, file_path=f"/tmp/{title}.mp4", direct_url=url)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch.object(story_service.downloader, "_download_direct_stream", side_effect=mock_download_direct_stream):
            results = await story_service.fetch_telegram_stories("sample_channel", limit=5)

    assert len(results) == 2
    # Hech qaysi URL emoji emas
    for u in downloaded_urls:
        assert u.startswith("https://")
        assert "emoji" not in u
    assert "https://cdn.telesco.pe/file/clip.mp4" in downloaded_urls
    assert "https://cdn.telesco.pe/file/pic.jpg" in downloaded_urls


# ===========================================================================
# 3. Instagram Story Sanitization & Error Handling Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_get_user_profile_and_stories_filters_empty_direct_urls():
    """Instagram hikoyalarida direct_url bo'sh bo'lgan itemlar chiqarib tashlanishi testi."""
    mock_stories = [
        DownloadResult(success=True, direct_url="https://ig.cdn.com/story1.mp4", file_path="/tmp/1.mp4", duration=15),
        DownloadResult(success=True, direct_url=None, file_path="/tmp/2.mp4"),  # Bo'sh URL
        DownloadResult(success=True, direct_url="", file_path="/tmp/3.mp4"),    # Bo'sh URL
        DownloadResult(success=True, direct_url="https://ig.cdn.com/story2.jpg", file_path="/tmp/4.jpg"),
    ]

    story_service._profile_cache.clear()
    with patch.object(story_service, "fetch_stories", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_stories
        data = await story_service.get_user_profile_and_stories("cristiano")

    assert data["ok"] is True
    assert len(data["items"]) == 2
    for it in data["items"]:
        assert it["u"] != ""
        assert it["u"].startswith("https://")


@pytest.mark.asyncio
async def test_get_user_profile_and_stories_private_and_rate_limit_errors():
    """Yopiq hisob va rate limit xatoliklari to'g'ri kodlar bilan qaytarilishi testi."""
    story_service._profile_cache.clear()

    # 1. Yopiq profil
    with patch.object(story_service, "fetch_stories", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [DownloadResult(success=False, error="Profil yopiq (shaxsiy / private hisob)")]
        data = await story_service.get_user_profile_and_stories("private_user")
        assert data["ok"] is False
        assert data["error"] == "private"
        assert data["items"] == []

    # 2. Rate limit (429)
    story_service._profile_cache.clear()
    with patch.object(story_service, "fetch_stories", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [DownloadResult(success=False, error="HTTP 429: Too Many Requests")]
        data = await story_service.get_user_profile_and_stories("popular_user")
        assert data["ok"] is False
        assert data["error"] == "rate"
        assert data["items"] == []


@pytest.mark.asyncio
async def test_fetch_stories_robust_exception_handling():
    """fetch_stories barcha kutilmagan istisnolarni ushlab, chaqiruvchini qulatmasligi testi."""
    with patch.object(story_service, "_fetch_stories_via_public_endpoints", side_effect=RuntimeError("Socket hang up")):
        with patch.object(story_service.downloader, "download_video", side_effect=RuntimeError("yt-dlp fatal crash")):
            results = await story_service.fetch_stories("any_account", platform="ig")
            assert isinstance(results, list)
            assert len(results) == 1
            assert results[0].success is False
            assert "xatolik" in results[0].error.lower()


# ===========================================================================
# 4. Level 1 Menu & Handlers Tests
# ===========================================================================

def test_story_platform_keyboard_structure():
    """story_platform_keyboard Level 1 tugmalarini to'liq o'z ichiga olishi testi."""
    # 1. Standart holat (WebApp URL belgilanmagan)
    kb_no_web = story_platform_keyboard(webapp_url="")
    assert isinstance(kb_no_web, InlineKeyboardMarkup)
    buttons = [btn for row in kb_no_web.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for btn in buttons]

    assert "story_platform:tg" in callbacks
    assert "story_platform:ig" in callbacks
    assert "story_platform:menu" in callbacks

    # Tugma matnlarini aniq tekshirish
    tg_btn = next(btn for btn in buttons if btn.callback_data == "story_platform:tg")
    ig_btn = next(btn for btn in buttons if btn.callback_data == "story_platform:ig")
    menu_btn = next(btn for btn in buttons if btn.callback_data == "story_platform:menu")

    assert tg_btn.text == "📱 Telegram story"
    assert ig_btn.text == "📸 Instagram story"
    assert menu_btn.text == "⬅️ Asosiy menyu"

    # Qatorlar joylashuvi: Row 1 da TG va IG, Row 2 da menyu
    assert kb_no_web.inline_keyboard[0][0].callback_data == "story_platform:tg"
    assert kb_no_web.inline_keyboard[0][1].callback_data == "story_platform:ig"
    assert kb_no_web.inline_keyboard[1][0].callback_data == "story_platform:menu"

    # 2. WebApp URL sozlangan holat
    kb_web = story_platform_keyboard(webapp_url="https://baunty.uz")
    all_btns = [btn for row in kb_web.inline_keyboard for btn in row]
    assert any("Mini App" in btn.text for btn in all_btns)
    assert any(btn.callback_data == "story_platform:menu" for btn in all_btns)
    assert any(btn.callback_data == "story_platform:tg" for btn in all_btns)
    assert any(btn.callback_data == "story_platform:ig" for btn in all_btns)

    # 3. Default chaqiruv
    kb_default = story_platform_keyboard()
    def_callbacks = [btn.callback_data for row in kb_default.inline_keyboard for btn in row]
    assert "story_platform:tg" in def_callbacks
    assert "story_platform:ig" in def_callbacks
    assert "story_platform:menu" in def_callbacks


@pytest.mark.asyncio
async def test_cb_story_platform_menu():
    """[⬅️ Asosiy menyu] bosilganda FSM holati tozalanib, asosiy menyuga qaytarilishi testi."""
    mock_cb = AsyncMock(spec=CallbackQuery)
    mock_cb.data = "story_platform:menu"
    mock_cb.answer = AsyncMock()
    mock_cb.from_user = User(id=12345, is_bot=False, first_name="TestUser")
    mock_cb.message = AsyncMock(spec=Message)
    mock_cb.message.delete = AsyncMock()
    mock_cb.message.answer = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)

    await cb_story_platform_menu(mock_cb, mock_state)

    # 1. State tozalandi
    mock_state.clear.assert_called_once()
    # 2. Callbackga javob berildi
    mock_cb.answer.assert_called_once()
    # 3. Asosiy menyu xabari yuborildi
    assert mock_cb.message.answer.called
    call_args = mock_cb.message.answer.call_args
    assert "Asosiy menyu" in call_args[0][0]
    assert "reply_markup" in call_args[1]


@pytest.mark.asyncio
async def test_cb_story_platform_tg_and_ig_routing():
    """Telegram va Instagram platformasi tanlanganda state to'g'ri o'rnatilishi testi."""
    # 1. Telegram
    mock_cb_tg = AsyncMock(spec=CallbackQuery)
    mock_cb_tg.data = "story_platform:tg"
    mock_cb_tg.answer = AsyncMock()
    mock_cb_tg.message = AsyncMock(spec=Message)
    mock_cb_tg.message.answer = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)
    await cb_story_platform(mock_cb_tg, mock_state)
    mock_state.set_state.assert_called_with(StoryStates.waiting_for_username)
    mock_state.update_data.assert_called_with(platform="tg")
    assert "Telegram story" in mock_cb_tg.message.answer.call_args[0][0]

    # 2. Instagram
    mock_cb_ig = AsyncMock(spec=CallbackQuery)
    mock_cb_ig.data = "story_platform:ig"
    mock_cb_ig.answer = AsyncMock()
    mock_cb_ig.message = AsyncMock(spec=Message)
    mock_cb_ig.message.answer = AsyncMock()

    mock_state_ig = AsyncMock(spec=FSMContext)
    await cb_story_platform(mock_cb_ig, mock_state_ig)
    mock_state_ig.set_state.assert_called_with(StoryStates.waiting_for_username)
    mock_state_ig.update_data.assert_called_with(platform="ig")
    assert "Instagram story" in mock_cb_ig.message.answer.call_args[0][0]


# ===========================================================================
# 5. Mini App Source Code Fixes Verification Tests
# ===========================================================================

def test_story_js_source_code_seg_html_fix():
    """webapp/story.js da undefined segHTML() chaqiriqlari mavjud emasligi va rootHead() ishlatilishi testi."""
    story_js_path = Path(__file__).resolve().parent.parent / "webapp" / "story.js"
    assert story_js_path.exists(), f"story.js fayli topilmadi: {story_js_path}"

    content = story_js_path.read_text(encoding="utf-8")

    # segHTML() hech qayerda chaqirilmasligi kerak
    assert "segHTML()" not in content, "story.js faylida hali ham 'segHTML()' chaqirig'i mavjud!"

    # watchHTML va savedHTML funksiyalarida rootHead() ishlatilayotganligi
    watch_match = re.search(r"function watchHTML\(\)\s*\{[\s\S]*?return\s*`\$\{rootHead\(\)\}", content)
    saved_match = re.search(r"function savedHTML\(\)\s*\{[\s\S]*?return\s*`\$\{rootHead\(\)\}", content)

    assert watch_match is not None, "watchHTML ichida ${rootHead()} chaqirig'i topilmadi!"
    assert saved_match is not None, "savedHTML ichida ${rootHead()} chaqirig'i topilmadi!"


def test_zk_css_top_nav_z_index_fix():
    """webapp/zk.css faylida body.zk>.top elementi z-index: 1000 ga ega ekanligi testi."""
    zk_css_path = Path(__file__).resolve().parent.parent / "webapp" / "zk.css"
    assert zk_css_path.exists(), f"zk.css fayli topilmadi: {zk_css_path}"

    content = zk_css_path.read_text(encoding="utf-8")

    # body.zk>.top uchun sticky va z-index: 1000 qoidasi mavjudligi
    assert re.search(r"body\.zk>\.top\s*\{[^}]*z-index:\s*1000", content) is not None, (
        "zk.css faylida 'body.zk>.top' uchun 'z-index: 1000' qoidasi topilmadi!"
    )
    assert re.search(r"body\.zk>\.top\s*\{[^}]*position:\s*sticky", content) is not None, (
        "zk.css faylida 'body.zk>.top' uchun 'position: sticky' qoidasi topilmadi!"
    )


# ===========================================================================
# 6. Web Server Endpoints Integration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_web_server_story_tg_endpoint():
    """services/web_server.py dagi handle_story_tg toza javob qaytarishi testi."""
    from services.web_server import handle_story_tg

    mock_request = MagicMock(spec=web.Request)
    mock_request.query = {"u": "baunty_official"}

    with patch.object(story_service, "get_telegram_stories", new_callable=AsyncMock) as mock_get_tg:
        mock_get_tg.return_value = {
            "ok": True,
            "name": "Baunty Official",
            "pic": "https://cdn.telesco.pe/avatar.jpg",
            "pending": False,
            "items": [
                {
                    "id": "tg_1_100",
                    "k": "video",
                    "t": "https://cdn.telesco.pe/avatar.jpg",
                    "u": "https://cdn.telesco.pe/file/video.mp4",
                    "d": 15,
                    "ts": 1700000000,
                }
            ],
        }

        response = await handle_story_tg(mock_request)
        assert response.status == 200
        import json
        data = json.loads(response.text)
        assert data["ok"] is True
        assert len(data["items"]) == 1
        assert data["items"][0]["u"] == "https://cdn.telesco.pe/file/video.mp4"
        assert not any(it.get("u") == "" for it in data["items"])


@pytest.mark.asyncio
async def test_web_server_story_ig_endpoint():
    """services/web_server.py dagi handle_story_ig toza javob qaytarishi testi."""
    from services.web_server import handle_story_ig

    mock_request = MagicMock(spec=web.Request)
    mock_request.query = {"u": "official_user"}

    with patch.object(story_service, "get_user_profile_and_stories", new_callable=AsyncMock) as mock_get_ig:
        mock_get_ig.return_value = {
            "ok": True,
            "name": "official_user",
            "pic": "https://api.dicebear.com/7.x/identicon/svg?seed=official_user",
            "verified": False,
            "items": [],
        }

        response = await handle_story_ig(mock_request)
        assert response.status == 200
        import json
        data = json.loads(response.text)
        assert data["ok"] is True
        assert data["items"] == []
        assert not any(it.get("u") == "" for it in data["items"])
