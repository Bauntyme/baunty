"""
Tests for WebApp URL update to baunty-cinema.onrender.com,
Render Keep-Alive anti-sleep background service,
and Elimination of false-positive "Xavfsizlik ishga tushdi" on phone screen rotation / landscape mode.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from config import BASE_DIR, Settings, config
from keyboards.inline import admin_dashboard_keyboard
from main import set_webapp_menu_button
from services.keepalive_service import (
    TARGET_HEALTH_URLS,
    KEEPALIVE_HEADERS,
    ping_endpoint,
    start_keepalive_service,
    stop_keepalive_service,
    _keepalive_task
)


def test_webapp_url_configured_to_baunty_cinema():
    """WebApp URL baunty-cinema.onrender.com/ ga to'g'ri sozlanganligi."""
    s = Settings()
    assert "baunty-cinema.onrender.com" in s.WEBAPP_URL
    assert "baunty-cinema.onrender.com" in s.webapp_url_resolved


def test_webapp_url_empty_fallback_to_baunty_cinema():
    """Agar WEBAPP_URL bo'sh bo'lsa ham avtomatik baunty-cinema ga fallback qilishi."""
    with patch.dict("os.environ", {"WEBAPP_URL": "", "RENDER_EXTERNAL_URL": ""}, clear=False):
        s = Settings(WEBAPP_URL="")
        assert s.webapp_url_resolved == "https://baunty-cinema.onrender.com/"



@pytest.mark.asyncio
async def test_set_webapp_menu_button_uses_baunty_cinema():
    """Pastki 'Ilova' tugmasi MenuButtonWebApp orqali baunty-cinema.onrender.com ni o'rnatishi."""
    mock_bot = AsyncMock()
    await set_webapp_menu_button(mock_bot)

    assert mock_bot.set_chat_menu_button.called
    call_args = mock_bot.set_chat_menu_button.call_args[1]
    menu_btn = call_args["menu_button"]
    assert menu_btn.text == "📱 Ilova"
    assert "baunty-cinema.onrender.com" in menu_btn.web_app.url


def test_admin_dashboard_flow_url_clean():
    """Admin Live Flow URL da ikki qavat slash (//admin/flow) bo'lmasligi va baunty-cinema ga yo'naltirilishi."""
    kb = admin_dashboard_keyboard()
    first_btn = kb.inline_keyboard[0][0]
    assert first_btn.web_app is not None
    assert "//admin/flow" not in first_btn.web_app.url
    assert "baunty-cinema.onrender.com/admin/flow" in first_btn.web_app.url


def test_keepalive_target_urls_contains_both_endpoints():
    """Keepalive xizmati baunty-cinema health va ping endpointlarini o'z ichiga olishi."""
    assert "https://baunty-cinema.onrender.com/health" in TARGET_HEALTH_URLS
    assert "https://baunty-cinema.onrender.com/ping" in TARGET_HEALTH_URLS
    assert "UptimeRobot" in KEEPALIVE_HEADERS["User-Agent"]


class MockResponseCtx:
    def __init__(self, resp):
        self.resp = resp
    async def __aenter__(self):
        return self.resp
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.mark.asyncio
async def test_keepalive_ping_endpoint_success_and_resilience():
    """ping_endpoint 200 OK da True, xatolikda False qaytarishi va hech qachon botni qulatmasligi."""
    # 1. 200 OK holati
    mock_resp_ok = MagicMock()
    mock_resp_ok.status = 200
    mock_session = MagicMock()
    mock_session.get.return_value = MockResponseCtx(mock_resp_ok)

    res_ok = await ping_endpoint(mock_session, "https://baunty-cinema.onrender.com/health")
    assert res_ok is True

    # 2. Xatolik holati (masalan server 503 yoki ulanish uzilishi)
    mock_resp_err = MagicMock()
    mock_resp_err.status = 503
    mock_session.get.return_value = MockResponseCtx(mock_resp_err)

    res_err = await ping_endpoint(mock_session, "https://baunty-cinema.onrender.com/health")
    assert res_err is False

    # 3. Network Exception (Timeout / DNS error)
    mock_session.get.side_effect = Exception("Connection timed out")
    res_exc = await ping_endpoint(mock_session, "https://baunty-cinema.onrender.com/health")
    assert res_exc is False

    # 4. 301 / 302 Redirect yoki 204 No Content holatlarida ham True qaytarishi (Render reverse proxy tirikligini bildiradi)
    mock_resp_redir = MagicMock()
    mock_resp_redir.status = 301
    mock_session.get.side_effect = None
    mock_session.get.return_value = MockResponseCtx(mock_resp_redir)
    res_redir = await ping_endpoint(mock_session, "https://baunty-cinema.onrender.com/health")
    assert res_redir is True


@pytest.mark.asyncio
async def test_keepalive_start_and_stop_lifecycle():
    """start_keepalive_service va stop_keepalive_service fon vazifasini xavfsiz boshqarishi."""
    task = start_keepalive_service(interval_seconds=600)
    assert task is not None
    assert not task.done()

    # Qayta chaqirilganda o'sha faol vazifani qaytarishi kerak
    task2 = start_keepalive_service(interval_seconds=600)
    assert task2 is task

    # To'xtatish
    stop_keepalive_service()
    await asyncio.sleep(0.01)
    assert task.cancelled() or task.done()


def test_phone_screen_rotation_no_false_positive_security_screen():
    """
    Telefonda ekran yotqizilganda (landscape / rotation)
    'Xavfsizlik nazorati faollashdi' degan xatolik chiqmasligi,
    devDocked va resize hodisalariga DOM almashtiruvchi listener bog'lanmaganligi.
    """
    webapp_dir = BASE_DIR / "webapp"
    dist_dir = webapp_dir / "dist"

    index_html = (webapp_dir / "index.html").read_text(encoding="utf-8")
    shield_js = (dist_dir / "shield.min.js").read_text(encoding="utf-8")
    bundle_js = (dist_dir / "bundle.min.js").read_text(encoding="utf-8")

    # 1. '🔒 Xavfsizlik nazorati faollashdi' matni barcha frontend fayllaridan butkul olib tashlangan
    assert "Xavfsizlik nazorati faollashdi" not in index_html
    assert "Xavfsizlik nazorati faollashdi" not in shield_js
    assert "Xavfsizlik nazorati faollashdi" not in bundle_js

    # 2. window resize hodisasiga antiDebugCheck ulanmagan
    assert 'addEventListener("resize", antiDebugCheck' not in index_html
    assert 'addEventListener("resize", antiDebugCheck' not in shield_js
    assert 'addEventListener("resize", antiDebugCheck' not in bundle_js

    # 3. devDocked false-positive tekshiruvi shield da yo'q
    assert "devDocked" not in index_html
    assert "devDocked" not in shield_js
    assert "devDocked" not in bundle_js

    # 4. Majburiy audit talablari (F12, contextmenu, antiDebugCheck identifikatori) saqlangan
    assert "antiDebugCheck" in shield_js
    assert "contextmenu" in shield_js
    assert "keyCode === 123" in shield_js
