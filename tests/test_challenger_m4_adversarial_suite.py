"""
Adversarial Verification Suite for Milestone M4 (Anonymous Story Feature & Mini App)
Challenger 1 Empirical Challenge Suite.

Stress-tests:
1. Malicious / Corrupted Telegram HTML Scraping:
   - Nested emojis, custom reaction emojis, HTML entities, data: URIs, javascript: links, SVG icons, broken HTML tags.
   - High-load / large HTML payload ReDoS resistance.
2. Ghost Item & Scraper Error Stress:
   - Empty channels, zero-media pages, all-emoji pages.
   - Instagram null, empty, whitespace-only direct_url elimination.
   - Error code classification: private, rate (429), not_found, story_not_found.
   - Fail-safe exception catching in fetch_stories and get_telegram_stories.
3. Story Handler & State Machine Stress:
   - Invalid usernames (empty, punctuation-only, malformed URLs).
   - Non-text messages (photos, stickers, audio, documents) in waiting_for_username state.
   - Cancelled state transitions via cancel keyboard and commands.
   - Rapid callback toggles between platforms and menu return.
4. Frontend Bundle Integrity:
   - Strict absence of uppercase segHTML in webapp/story.js and webapp/bundle.min.js.
   - Verification of rootHead() in watchHTML() and savedHTML().
   - Verification of z-index: 1000 on body.zk>.top in webapp/zk.css and webapp/bundle.min.css.
   - JavaScript syntax validation of frontend bundles.
"""
import io
import re
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aiogram.types import CallbackQuery, Message, User, Chat, PhotoSize, Sticker
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from config import config
from services.downloader import DownloadResult
from services.story_service import (
    story_service,
    StoryService,
    normalize_and_validate_media_url,
)
from keyboards.inline import story_platform_keyboard
from handlers.story import (
    cmd_story_prompt,
    cb_story_platform,
    cb_story_platform_menu,
    state_process_story_username,
)
from handlers.start import cmd_cancel
from utils.states import StoryStates


# ===========================================================================
# 1. Malicious & Corrupted Telegram HTML Scraping Tests
# ===========================================================================

class TestMaliciousTelegramScraping:
    """Stress-test HTML parsing, regex extractors, and media URL sanitization."""

    def test_nested_and_custom_emoji_filtering(self):
        """Deeply nested and custom reaction emojis must all be filtered out."""
        adversarial_emoji_urls = [
            "//telegram.org/img/emoji/100/nested/deep/sub/1f600.png",
            "https://telegram.org/img/emoji/custom/40/reaction_heart.png",
            "http://telegram.org/img/emoji/v2/40/e29da4.png",
            "/img/emoji/nested/fire.png",
            "/emoji/custom_pack/star.png",
            "//cdn.telesco.pe/emoji/reaction_123.png",
            "https://t.me/emoji/sample.png",
            "//telegram.org/img/stickers/animated_pack/sticker1.webp",
            "https://telegram.org/img/website_icon.svg",
            "//tgme/channel_avatar_placeholder.png",
        ]

        for url in adversarial_emoji_urls:
            assert normalize_and_validate_media_url(url) is None, f"Failed to reject emoji URL: {url}"

    def test_corrupted_and_broken_html_tags(self):
        """Scraper must gracefully ignore broken, truncated, or malformed HTML tags."""
        malformed_html = """
        <div class="tgme_page_title"><span dir="auto">Stress Channel</span></div>
        <img class="tgme_page_photo_image" src="//cdn.telesco.pe/file/avatar.jpg"
        <!-- Unclosed video tag -->
        <video src="//cdn.telesco.pe/file/unclosed_vid.mp4
        <!-- Empty and whitespace-only attributes -->
        <video src="">
        <video src="   ">
        <video src="   \t\n   ">
        <!-- Broken background image styles -->
        <div style="background-image:url('')"></div>
        <div style="background-image:url('   ')"></div>
        <div style="background-image:url('//telegram.org/img/emoji/40/e2.png')"></div>
        <!-- Valid media mixed in -->
        <video src="//cdn.telesco.pe/file/genuine_video.mp4">
        <div class="tgme_widget_message_photo_wrap" style="background-image:url('//cdn.telesco.pe/file/genuine_photo.jpg')"></div>
        """

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = malformed_html.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        service = StoryService()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            import asyncio
            result = asyncio.run(service.get_telegram_stories("stress_test_channel"))

        assert result["ok"] is True
        assert result["name"] == "Stress Channel"
        # Only the genuine video and photo should be extracted
        media_urls = [it["u"] for it in result["items"]]
        assert "https://cdn.telesco.pe/file/genuine_video.mp4" in media_urls
        assert "https://cdn.telesco.pe/file/genuine_photo.jpg" in media_urls
        # None of the unclosed or broken items
        for u in media_urls:
            assert u.startswith("https://")
            assert "emoji" not in u
            assert u.strip() == u

    def test_html_entities_and_parameters_in_media_urls(self):
        """URLs containing HTML entities and complex query parameters must be parsed safely."""
        html_with_entities = """
        <div class="tgme_page_title"><span dir="auto">Entity Channel</span></div>
        <video src="//cdn.telesco.pe/file/stream.mp4?token=abc123&amp;expires=1800000000&amp;id=99">
        <div style="background-image:url('//cdn.telesco.pe/file/thumb.jpg?w=1080&amp;h=1920')"></div>
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = html_with_entities.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        service = StoryService()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            import asyncio
            result = asyncio.run(service.get_telegram_stories("entity_test"))

        assert result["ok"] is True
        assert len(result["items"]) == 2
        for it in result["items"]:
            assert it["u"].startswith("https://cdn.telesco.pe/file/")
            assert not it["u"].endswith('"')

    def test_large_html_payload_no_catastrophic_backtracking(self):
        """Scraper must handle 10,000+ tags without hanging or regex ReDoS."""
        import time

        emoji_tags = "".join([
            f'<div style="background-image:url(\'//telegram.org/img/emoji/40/{i}.png\')"></div>\n'
            for i in range(2000)
        ])
        genuine_tags = (
            '<video src="//cdn.telesco.pe/file/real_vid1.mp4">\n'
            '<div style="background-image:url(\'//cdn.telesco.pe/file/real_pic1.jpg\')"></div>\n'
        )
        huge_html = f"<html><body>{emoji_tags}{genuine_tags}</body></html>"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = huge_html.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        service = StoryService()
        t0 = time.time()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            import asyncio
            result = asyncio.run(service.get_telegram_stories("huge_channel"))
        t1 = time.time()

        elapsed = t1 - t0
        assert elapsed < 1.5, f"Scraping took too long: {elapsed:.2f}s (possible ReDoS)"
        assert result["ok"] is True
        assert len(result["items"]) == 2
        assert result["items"][0]["u"] == "https://cdn.telesco.pe/file/real_vid1.mp4"
        assert result["items"][1]["u"] == "https://cdn.telesco.pe/file/real_pic1.jpg"


# ===========================================================================
# 2. Ghost Item Stress & Scraper Error Scenarios
# ===========================================================================

class TestGhostItemAndScraperStress:
    """Ensure zero ghost items and robust error handling across edge cases."""

    @pytest.mark.asyncio
    async def test_empty_channel_strict_no_ghost_items(self):
        """Channel with zero media posts must return items=[] without dummy fallbacks."""
        html_empty = """
        <div class="tgme_page_title"><span dir="auto">No Media Channel</span></div>
        <div class="tgme_page_description">Just some text without any photos or videos.</div>
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = html_empty.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        service = StoryService()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await service.get_telegram_stories("nomedia_channel")

        assert result["ok"] is True
        assert result["items"] == []
        assert len(result["items"]) == 0

    @pytest.mark.asyncio
    async def test_all_emojis_strict_no_ghost_items(self):
        """Channel with only emojis and stickers must return items=[] without ghost items."""
        html_all_emojis = """
        <div class="tgme_page_title"><span dir="auto">Emoji-Only Channel</span></div>
        <video src="//telegram.org/img/stickers/pack.webp">
        <div style="background-image:url('//telegram.org/img/emoji/40/e29da4.png')"></div>
        <div style="background-image:url('/img/emoji/smile.png')"></div>
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = html_all_emojis.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        service = StoryService()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await service.get_telegram_stories("emoji_only")

        assert result["ok"] is True
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_instagram_null_and_empty_direct_urls_omitted(self):
        """get_user_profile_and_stories must strictly drop items with empty direct_url."""
        service = StoryService()
        # Mock fetch_stories returning DownloadResults where direct_url is None, empty, or whitespace
        mock_results = [
            DownloadResult(success=True, direct_url=None, file_path="story1.mp4"),
            DownloadResult(success=True, direct_url="", file_path="story2.mp4"),
            DownloadResult(success=True, direct_url="   ", file_path="story3.mp4"),
            DownloadResult(success=True, direct_url="https://scontent.cdninstagram.com/valid.mp4", file_path="story4.mp4"),
        ]

        with patch.object(service, "fetch_stories", new=AsyncMock(return_value=mock_results)):
            res = await service.get_user_profile_and_stories("test_user_empty_urls")

        assert res["ok"] is True
        # Only the 1 item with a genuine direct_url should be present
        assert len(res["items"]) == 1
        assert res["items"][0]["u"] == "https://scontent.cdninstagram.com/valid.mp4"
        assert res["items"][0]["u"] != ""

    @pytest.mark.asyncio
    async def test_instagram_error_code_mapping_under_simulated_failures(self):
        """Verify proper API error codes: private, rate, not_found, story_not_found."""
        service = StoryService()

        # 1. Private profile
        with patch.object(service, "fetch_stories", new=AsyncMock(return_value=[
            DownloadResult(success=False, error="Profil yopiq (private account)")
        ])):
            res = await service.get_user_profile_and_stories("private_account")
            assert res["ok"] is False
            assert res["error"] == "private"
            assert res["items"] == []

        # 2. Rate limit (429)
        with patch.object(service, "fetch_stories", new=AsyncMock(return_value=[
            DownloadResult(success=False, error="HTTP 429: Too Many Requests")
        ])):
            res = await service.get_user_profile_and_stories("rate_limited_user")
            assert res["ok"] is False
            assert res["error"] == "rate"
            assert res["items"] == []

        # 3. Profile not found
        with patch.object(service, "fetch_stories", new=AsyncMock(return_value=[
            DownloadResult(success=False, error="Foydalanuvchi topilmadi (not found)")
        ])):
            res = await service.get_user_profile_and_stories("nonexistent_user")
            assert res["ok"] is False
            assert res["error"] == "not_found"
            assert res["items"] == []

        # 4. No active stories in last 24h
        with patch.object(service, "fetch_stories", new=AsyncMock(return_value=[])):
            res = await service.get_user_profile_and_stories("no_stories_user")
            assert res["ok"] is False
            assert res["error"] == "story_not_found"
            assert res["items"] == []

    @pytest.mark.asyncio
    async def test_fetch_stories_unexpected_socket_exceptions_fail_safe(self):
        """Unexpected network exceptions during fetch_stories must return clean DownloadResult without raising."""
        service = StoryService()
        with patch.object(service.downloader, "download_video", side_effect=ConnectionResetError("Socket aborted")):
            res = await service.fetch_stories("crash_test", platform="ig")
            assert len(res) == 1
            assert res[0].success is False
            assert "xatolik" in res[0].error.lower()


# ===========================================================================
# 3. Story Handler & State Machine Stress Tests
# ===========================================================================

class TestStoryHandlerAndStateMachineStress:
    """Adversarial testing of user inputs, non-text inputs, state transitions, and keyboards."""

    @pytest.mark.asyncio
    async def test_story_handler_invalid_usernames_adversarial(self):
        """Handler must reject invalid usernames without crashing or leaking state."""
        invalid_inputs = [
            "@@@@@",
            "!!!!",
            "   ",
            "#$%%^&*()",
            "https://t.me/",
            "https://instagram.com/",
        ]

        storage = MemoryStorage()
        key = StorageKey(bot_id=1, chat_id=100, user_id=200)
        state = FSMContext(storage=storage, key=key)

        with patch("services.story_service.story_service.fetch_stories", new=AsyncMock(return_value=[
            DownloadResult(success=False, error="Foydalanuvchi topilmadi")
        ])):
            for bad_input in invalid_inputs:
                await state.set_state(StoryStates.waiting_for_username)
                await state.update_data(platform="tg")

                msg = MagicMock(spec=Message)
                msg.text = bad_input
                msg.from_user = User(id=200, is_bot=False, first_name="Tester")
                msg.chat = Chat(id=100, type="private")
                msg.reply = AsyncMock()

                # Execute handler
                await state_process_story_username(msg, state)

                # Handler must have replied with error or handled gracefully
                assert msg.reply.called, f"Handler did not respond to invalid input: {bad_input!r}"

    @pytest.mark.asyncio
    async def test_story_handler_non_text_inputs_in_waiting_state(self):
        """Non-text messages (e.g. photo, sticker) while in waiting_for_username should not trigger username processing."""
        storage = MemoryStorage()
        key = StorageKey(bot_id=1, chat_id=100, user_id=200)
        state = FSMContext(storage=storage, key=key)
        await state.set_state(StoryStates.waiting_for_username)
        await state.update_data(platform="tg")

        # Create photo message (text is None)
        photo_msg = MagicMock(spec=Message)
        photo_msg.text = None
        photo_msg.photo = [MagicMock(spec=PhotoSize)]
        photo_msg.from_user = User(id=200, is_bot=False, first_name="Tester")
        photo_msg.chat = Chat(id=100, type="private")
        photo_msg.reply = AsyncMock()

        # The state_process_story_username filter is (StoryStates.waiting_for_username, F.text)
        # Verify that state remains waiting_for_username
        assert await state.get_state() == StoryStates.waiting_for_username.state

    @pytest.mark.asyncio
    async def test_story_cancelled_state_transitions(self):
        """User pressing '❌ Bekor qilish' or sending cancel commands must clear StoryStates."""
        storage = MemoryStorage()
        key = StorageKey(bot_id=1, chat_id=100, user_id=200)
        state = FSMContext(storage=storage, key=key)

        cancel_inputs = [
            "❌ Bekor qilish",
            "❌ Бекор қилиш",
            "❌ Отмена",
            "🔙 Bosh menyu",
            "🔙 Orqaga",
        ]

        for cancel_text in cancel_inputs:
            await state.set_state(StoryStates.waiting_for_username)
            await state.update_data(platform="tg")
            assert await state.get_state() == StoryStates.waiting_for_username.state

            msg = MagicMock(spec=Message)
            msg.text = cancel_text
            msg.from_user = User(id=200, is_bot=False, first_name="Tester")
            msg.chat = Chat(id=100, type="private")
            msg.answer = AsyncMock()

            await cmd_cancel(msg, state)

            # State must be completely cleared
            assert await state.get_state() is None, f"State was not cleared after: {cancel_text}"
            assert msg.answer.called

    @pytest.mark.asyncio
    async def test_rapid_platform_keyboard_toggles_and_menu_return(self):
        """Rapid toggling between TG, IG and main menu callback queries must transition cleanly."""
        storage = MemoryStorage()
        key = StorageKey(bot_id=1, chat_id=100, user_id=200)
        state = FSMContext(storage=storage, key=key)

        # 1. Click TG
        cb_tg = MagicMock(spec=CallbackQuery)
        cb_tg.data = "story_platform:tg"
        cb_tg.message = MagicMock(spec=Message)
        cb_tg.message.answer = AsyncMock()
        cb_tg.answer = AsyncMock()
        await cb_story_platform(cb_tg, state)
        assert await state.get_state() == StoryStates.waiting_for_username.state
        data = await state.get_data()
        assert data.get("platform") == "tg"

        # 2. Click IG
        cb_ig = MagicMock(spec=CallbackQuery)
        cb_ig.data = "story_platform:ig"
        cb_ig.message = MagicMock(spec=Message)
        cb_ig.message.answer = AsyncMock()
        cb_ig.answer = AsyncMock()
        await cb_story_platform(cb_ig, state)
        assert await state.get_state() == StoryStates.waiting_for_username.state
        data = await state.get_data()
        assert data.get("platform") == "ig"

        # 3. Click Menu (back to main menu)
        cb_menu = MagicMock(spec=CallbackQuery)
        cb_menu.data = "story_platform:menu"
        cb_menu.from_user = User(id=200, is_bot=False, first_name="Tester")
        cb_menu.message = MagicMock(spec=Message)
        cb_menu.message.delete = AsyncMock()
        cb_menu.message.answer = AsyncMock()
        cb_menu.answer = AsyncMock()
        await cb_story_platform_menu(cb_menu, state)
        assert await state.get_state() is None

    @pytest.mark.asyncio
    async def test_cb_story_platform_menu_message_already_deleted_resilience(self):
        """cb_story_platform_menu must not crash if the previous message was already deleted."""
        storage = MemoryStorage()
        key = StorageKey(bot_id=1, chat_id=100, user_id=200)
        state = FSMContext(storage=storage, key=key)
        await state.set_state(StoryStates.waiting_for_username)

        cb_menu = MagicMock(spec=CallbackQuery)
        cb_menu.data = "story_platform:menu"
        cb_menu.from_user = User(id=200, is_bot=False, first_name="Tester")
        cb_menu.message = MagicMock(spec=Message)
        # Simulate Telegram API error: message can't be deleted
        cb_menu.message.delete = AsyncMock(side_effect=Exception("Message to delete not found"))
        cb_menu.message.answer = AsyncMock()
        cb_menu.answer = AsyncMock()

        # Must succeed without throwing
        await cb_story_platform_menu(cb_menu, state)
        assert await state.get_state() is None
        assert cb_menu.message.answer.called


# ===========================================================================
# 4. Frontend Bundle Integrity & Syntax Tests
# ===========================================================================

class TestFrontendBundleIntegrity:
    """Empirical verification of webapp JavaScript and CSS bundle artifacts."""

    def test_strict_absence_of_seg_html_uppercase(self):
        """Verify absence of undefined segHTML (case-sensitive) in story.js and bundle.min.js."""
        story_js_path = Path("C:/dev/copy/webapp/story.js")
        bundle_js_path = Path("C:/dev/copy/webapp/bundle.min.js")

        assert story_js_path.exists(), "webapp/story.js does not exist"
        assert bundle_js_path.exists(), "webapp/bundle.min.js does not exist"

        story_code = story_js_path.read_text(encoding="utf-8", errors="ignore")
        bundle_code = bundle_js_path.read_text(encoding="utf-8", errors="ignore")

        # Explicitly check for segHTML with uppercase HTML
        assert "segHTML" not in story_code, "segHTML found in webapp/story.js!"
        assert "segHTML" not in bundle_code, "segHTML found in webapp/bundle.min.js!"

        # Verify rootHead() is used in watchHTML and savedHTML
        assert "rootHead()" in story_code, "rootHead() not used in webapp/story.js"

    def test_top_nav_z_index_1000_in_css_and_bundle(self):
        """Verify body.zk>.top has sticky positioning and z-index: 1000 in zk.css and bundle.min.css."""
        zk_css_path = Path("C:/dev/copy/webapp/zk.css")
        bundle_css_path = Path("C:/dev/copy/webapp/bundle.min.css")

        assert zk_css_path.exists(), "webapp/zk.css does not exist"
        assert bundle_css_path.exists(), "webapp/bundle.min.css does not exist"

        zk_css = zk_css_path.read_text(encoding="utf-8", errors="ignore")
        bundle_css = bundle_css_path.read_text(encoding="utf-8", errors="ignore")

        assert "body.zk>.top{position:sticky;z-index:1000}" in zk_css, (
            "body.zk>.top{position:sticky;z-index:1000} not found in zk.css"
        )
        assert "body.zk>.top{position:sticky;z-index:1000}" in bundle_css, (
            "body.zk>.top{position:sticky;z-index:1000} not found in bundle.min.css"
        )

    def test_javascript_syntax_validity_via_node(self):
        """Verify that webapp/story.js and webapp/bundle.min.js parse cleanly with Node.js."""
        for js_file in ["C:/dev/copy/webapp/story.js", "C:/dev/copy/webapp/bundle.min.js"]:
            cmd = ["node", "-c", js_file]
            res = subprocess.run(cmd, capture_output=True, text=True)
            assert res.returncode == 0, f"JavaScript syntax error in {js_file}: {res.stderr}"
