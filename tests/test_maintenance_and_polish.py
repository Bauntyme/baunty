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


@pytest.mark.asyncio
async def test_cb_admin_maint_set_template():
    """cb_admin_maint_set_template callback data to'g'ri target va idx ni olishi va IndexError bermasligi."""
    from handlers.admin import cb_admin_maint_set_template
    from aiogram.types import CallbackQuery

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = User(id=11111111, is_bot=False, first_name="Admin")
    cb.data = "admin:maint:set_tmpl:global:2"
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()

    with patch("handlers.admin.is_admin_check", return_value=True), \
         patch.object(maintenance_service, "set_global_maintenance") as mock_set_global:
        await cb_admin_maint_set_template(cb)
        mock_set_global.assert_called_once_with(True, message_idx=2)
        assert cb.answer.call_count >= 1

    # Per-page template test: admin:maint:set_tmpl:kino:3
    cb2 = MagicMock(spec=CallbackQuery)
    cb2.from_user = User(id=11111111, is_bot=False, first_name="Admin")
    cb2.data = "admin:maint:set_tmpl:kino:3"
    cb2.answer = AsyncMock()
    cb2.message = MagicMock()
    cb2.message.edit_text = AsyncMock()

    with patch("handlers.admin.is_admin_check", return_value=True), \
         patch.object(maintenance_service, "set_page_maintenance") as mock_set_page, \
         patch("handlers.admin.cb_admin_maint_page_detail", new_callable=AsyncMock) as mock_page_detail:
        await cb_admin_maint_set_template(cb2)
        mock_set_page.assert_called_once_with("kino", True, message_idx=3)
        mock_page_detail.assert_called_once()


@pytest.mark.asyncio
async def test_start_movie_deep_link_blocked_by_maintenance():
    """Foydalanuvchi /start movie_284 yuborganida profilaktika yoqilgan bo'lsa kino berilmasligi."""
    from services.movie_service import movie_service
    with patch.object(maintenance_service, "is_global_maintenance", return_value=True), \
         patch.object(maintenance_service, "get_global_message", return_value="Profilaktika!"):

        msg = MagicMock(spec=Message)
        msg.from_user = User(id=99999999, is_bot=False, first_name="Ali")
        msg.chat = Chat(id=99999999, type="private")
        msg.text = "/start movie_284"
        msg.answer = AsyncMock()

        state = MagicMock(spec=FSMContext)
        state.clear = AsyncMock()

        with patch.object(Settings, "is_admin", return_value=False), \
             patch("database.session.get_session") as mock_session_ctx, \
             patch.object(movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliver:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            await cmd_start(msg, state)

            mock_deliver.assert_not_called()
            msg.answer.assert_called_once()
            called_args = msg.answer.call_args
            assert "Profilaktika!" in called_args[0][0]
            kb = called_args[1].get("reply_markup")
            buttons = [b.text for row in kb.keyboard for b in row]
            assert "🎬 Kinolar" not in buttons


@pytest.mark.asyncio
async def test_movie_code_input_blocked_by_maintenance():
    """Foydalanuvchi kino kodi yuborganida profilaktika paytida kino berilmasligi."""
    from handlers.movies import process_numeric_movie_code
    from services.movie_service import movie_service

    with patch.object(maintenance_service, "is_global_maintenance", return_value=True), \
         patch.object(maintenance_service, "get_global_message", return_value="Profilaktika!"):

        msg = MagicMock(spec=Message)
        msg.from_user = User(id=99999999, is_bot=False, first_name="Ali")
        msg.chat = Chat(id=99999999, type="private")
        msg.text = "284"
        msg.reply = AsyncMock()

        with patch.object(Settings, "is_admin", return_value=False), \
             patch.object(movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliver:

            await process_numeric_movie_code(msg)

            mock_deliver.assert_not_called()
            msg.reply.assert_called_once()
            assert "Profilaktika!" in msg.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_quiz_solo_endpoints_offline_fallbacks():
    """Quiz/viktorina solo rejimida upstream ishlamay qolsa ham 502 bermasligi va offline savollar berishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        import aiohttp
        real_request = aiohttp.ClientSession.request

        class MockRespContext:
            async def __aenter__(self):
                raise aiohttp.ClientError("Upstream connection refused")
            async def __aexit__(self, exc_type, exc, tb):
                pass

        def mock_request(self, method, url, **kwargs):
            if "161-97-96-58.sslip.io" in str(url):
                return MockRespContext()
            return real_request(self, method, url, **kwargs)

        with patch("aiohttp.ClientSession.request", new=mock_request):
            # /api/quiz/me
            resp = await client.get("/api/quiz/me")
            assert resp.status == 200
            d_me = await resp.json()
            assert d_me["ok"] is True
            assert "mine" in d_me

            # /api/quiz/solo/start
            resp_start = await client.post("/api/quiz/solo/start", json={"category": "general"})
            assert resp_start.status == 200
            d_start = await resp_start.json()
            assert d_start["ok"] is True
            assert "q" in d_start
            assert "o" in d_start["q"]
            assert len(d_start["q"]["o"]) == 4

            # /api/quiz/solo/answer
            resp_ans = await client.post("/api/quiz/solo/answer", json={"question_id": 1, "selected": 0})
            assert resp_ans.status == 200
            d_ans = await resp_ans.json()
            assert d_ans["ok"] is True
            assert d_ans["correct"] is True

            # /api/quiz/solo/next
            resp_next = await client.get("/api/quiz/solo/next?category=general")
            assert resp_next.status == 200
            d_next = await resp_next.json()
            assert d_next["ok"] is True
            assert "final" in d_next
    finally:
        await client.close()


def test_maintenance_dual_keys_active_and_enabled():
    """Frontend va backend muvofiqligi: get_state() ichida 'enabled' hamda 'active' kalitlari mavjudligi."""
    st = maintenance_service.get_state()
    assert "enabled" in st["global"]
    assert "active" in st["global"]
    assert st["global"]["enabled"] == st["global"]["active"]

    for page_id, p_data in st["pages"].items():
        assert "enabled" in p_data
        assert "active" in p_data
        assert p_data["enabled"] == p_data["active"]


@pytest.mark.asyncio
async def test_admin_cache_sync_and_server_health_handlers():
    """Admin cache sync va server health callbacklarining xatoliksiz ishlashi."""
    from handlers.admin import cb_admin_cache_sync, cb_admin_server_health
    from services.movie_service import movie_service
    from aiogram.types import CallbackQuery

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = User(id=11111111, is_bot=False, first_name="Admin")
    cb.data = "admin:cache:sync"
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()

    with patch("handlers.admin.is_admin_check", return_value=True), \
         patch("handlers.admin.get_session") as mock_sess_ctx, \
         patch.object(movie_service, "sync_catalog_from_upstream", new_callable=AsyncMock) as mock_sync, \
         patch("database.crud.get_total_movies_count", new_callable=AsyncMock) as mock_count:
        mock_sess = AsyncMock()
        mock_sess_ctx.return_value.__aenter__.return_value = mock_sess
        mock_sync.return_value = 5
        mock_count.return_value = 100

        await cb_admin_cache_sync(cb)
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "Katalog va Kesh muvaffaqiyatli yangilandi" in text

    # Server health
    cb_h = MagicMock(spec=CallbackQuery)
    cb_h.from_user = User(id=11111111, is_bot=False, first_name="Admin")
    cb_h.data = "admin:server:health"
    cb_h.answer = AsyncMock()
    cb_h.message = MagicMock()
    cb_h.message.edit_text = AsyncMock()

    with patch("handlers.admin.is_admin_check", return_value=True), \
         patch("handlers.admin.get_session") as mock_sess_ctx2, \
         patch("database.crud.get_total_users_count", new_callable=AsyncMock) as mock_u, \
         patch("database.crud.get_total_movies_count", new_callable=AsyncMock) as mock_m, \
         patch("database.crud.get_total_downloads_count", new_callable=AsyncMock) as mock_d:
        mock_sess2 = AsyncMock()
        mock_sess_ctx2.return_value.__aenter__.return_value = mock_sess2
        mock_u.return_value = 500
        mock_m.return_value = 120
        mock_d.return_value = 2500

        await cb_admin_server_health(cb_h)
        cb_h.message.edit_text.assert_called_once()
        h_text = cb_h.message.edit_text.call_args[0][0]
        assert "Server va Tizim Salomatligi" in h_text


