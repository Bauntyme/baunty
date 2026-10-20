"""
Tests for Maintenance Mode, Video Note 1s Turnaround, CBU.uz FX Sync,
Book Text Cleaning, Sticky Header, and Ultra-Sharp Image Rendering.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat
from aiogram.fsm.context import FSMContext

from services.maintenance_service import maintenance_service, MAINTENANCE_TEMPLATES, PAGE_EMOJIS, PAGE_NAMES
from services.book_service import sanitize_book_text
from services.web_server import create_web_app
from aiohttp.test_utils import TestClient, TestServer
from keyboards.default import maintenance_menu_keyboard, main_menu_keyboard
from handlers.start import cmd_start
from config import BASE_DIR, Settings


def test_maintenance_service_global_and_pages(tmp_path):
    """MaintenanceService global va bo'limlar holati to'g'ri ishlashi va saqlanishi."""
    test_json = tmp_path / "maintenance_test.json"
    with patch("services.maintenance_service.MAINTENANCE_FILE", test_json):
        # Reset cache
        with patch("services.maintenance_service._CACHE", None):
            state = maintenance_service.get_state()
            assert state["global"]["enabled"] is False
            assert len(state["pages"]) == 10
            assert "kino" in state["pages"]
            assert "tv" in state["pages"]

            # Global profilaktikani yoqish (2-shablon bilan)
            maintenance_service.set_global_maintenance(True, message_idx=1)
            assert maintenance_service.is_global_maintenance() is True
            msg = maintenance_service.get_global_message()
            assert MAINTENANCE_TEMPLATES[1] in msg

            # Sahifa profilaktikasini yoqish
            maintenance_service.set_global_maintenance(False)
            maintenance_service.set_page_maintenance("tv", True, message_idx=0)
            assert maintenance_service.is_page_maintenance("tv") is True
            assert maintenance_service.is_page_maintenance("kino") is False
            page_msg = maintenance_service.get_page_message("tv")
            assert MAINTENANCE_TEMPLATES[0] in page_msg

            # O'chirish
            maintenance_service.set_page_maintenance("tv", False)
            assert maintenance_service.is_page_maintenance("tv") is False


@pytest.mark.asyncio
async def test_cmd_start_with_maintenance_active():
    """Global profilaktika yoqilganda oddiy foydalanuvchiga faqat 3 ta bo'lim ko'rinishi."""
    with patch.object(maintenance_service, "is_global_maintenance", return_value=True), \
         patch.object(maintenance_service, "get_global_message", return_value="Texnik ishlar!"):

        msg_user = MagicMock(spec=Message)
        msg_user.from_user = User(id=99999999, is_bot=False, first_name="Ali")
        msg_user.chat = Chat(id=99999999, type="private")
        msg_user.text = "/start"
        msg_user.answer = AsyncMock()

        state = MagicMock(spec=FSMContext)
        state.clear = AsyncMock()

        with patch.object(Settings, "is_admin", return_value=False), \
             patch("database.session.get_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            await cmd_start(msg_user, state)

            msg_user.answer.assert_called_once()
            called_args = msg_user.answer.call_args
            assert "Texnik ishlar!" in called_args[0][0]
            # Reply markup maintenance_menu_keyboard bo'lishi kerak
            kb = called_args[1].get("reply_markup")
            buttons = [b.text for row in kb.keyboard for b in row]
            assert "🎵 Qo'shiq topish" in buttons
            assert "⭕️ Dumaloq video" in buttons
            assert "📥 Media yuklash" in buttons
            assert "🎬 Kinolar" not in buttons


@pytest.mark.asyncio
async def test_cmd_start_admin_bypasses_maintenance():
    """Admin foydalanuvchi profilaktikadan o'tib, asosiy menyuni ko'rishi."""
    with patch.object(maintenance_service, "is_global_maintenance", return_value=True):
        msg_admin = MagicMock(spec=Message)
        msg_admin.from_user = User(id=11111111, is_bot=False, first_name="Admin")
        msg_admin.chat = Chat(id=11111111, type="private")
        msg_admin.text = "/start"
        msg_admin.answer = AsyncMock()

        state = MagicMock(spec=FSMContext)
        state.clear = AsyncMock()

        with patch.object(Settings, "is_admin", return_value=True), \
             patch("database.session.get_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            await cmd_start(msg_admin, state)

            msg_admin.answer.assert_called_once()
            called_args = msg_admin.answer.call_args
            # Admin bosh menyuni olishi kerak
            kb = called_args[1].get("reply_markup")
            buttons = [b.text for row in kb.keyboard for b in row]
            assert "🎬 Kino" in buttons or "⚙️ Admin panel" in buttons


def test_sanitize_book_text_cleaning():
    """Kitob matnidagi mojibake, ligaturalar va bo'g'in chiziqchalari to'g'rilanishi."""
    corrupt_text = "Kitobâ€™dagi maâ€™lumot va o‘qish. Birinchi \u00adbob: sha- \nhar hayoti. ﬁlologiya."
    cleaned = sanitize_book_text(corrupt_text)
    assert "Kitob'dagi" in cleaned
    assert "ma'lumot" in cleaned
    assert "o'qish" in cleaned
    assert "\u00ad" not in cleaned
    assert "shahar" in cleaned
    assert "filologiya" in cleaned


@pytest.mark.asyncio
async def test_api_maintenance_endpoint():
    """/api/maintenance so'rovi to'g'ri JSON qaytarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/maintenance")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert "maintenance" in data
        assert "global" in data["maintenance"]
        assert "pages" in data["maintenance"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_fx_endpoint():
    """/api/fx valyuta kursi so'rovi to'g'ri ishlashi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/fx")
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert "items" in data
        assert len(data["items"]) > 0
        usd = next((r for r in data["items"] if r.get("c") == "USD"), None)
        assert usd is not None
        assert "r" in usd
    finally:
        await client.close()


def test_sticky_header_and_image_rendering_css():
    """Web app CSS da .top sticky, z-index: 999 va ultra-sharp image-rendering mavjudligi."""
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")

    assert "position:sticky;top:0;z-index:999" in zk_css.replace(" ", "") or "position: sticky; top: 0; z-index: 999" in zk_css
    assert "image-rendering:-webkit-optimize-contrast" in zk_css.replace(" ", "")
    assert "image-rendering:-webkit-optimize-contrast" in index_html.replace(" ", "")
    assert "z-index:999" in index_html.replace(" ", "")
    assert "backdrop-filter:blur(16px)" in index_html.replace(" ", "")
