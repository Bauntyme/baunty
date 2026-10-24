"""
Tests for Frontend/Backend Separation, DevTools Protection,
Script Bundling, Source Map Shielding, and Performance Optimizations.
"""
import pytest
import os
import time
from pathlib import Path
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web
from config import BASE_DIR
from services.web_server import (
    create_web_app,
    get_production_index_html,
    _CATALOG_CACHE,
    _TV_ALL_CACHE,
)
from services.security_service import security_service, check_reconnaissance_and_database_shield
from middlewares.subscription import SubscriptionMiddleware, clear_subscription_cache, _CHANNELS_CACHE, _USER_SUB_CACHE


@pytest.fixture(autouse=True)
def reset_state():
    security_service.reset()
    clear_subscription_cache()
    yield
    security_service.reset()
    clear_subscription_cache()


def test_production_index_html_consolidation():
    """Production index.html barcha 15 ta CSS va 16 ta JS skriptlarini bundle.min ga almashtirishi."""
    prod_html = get_production_index_html()
    assert "bundle.min.css" in prod_html
    assert "bundle.min.js" in prod_html
    assert '<link rel="stylesheet" href="bundle.min.css">' in prod_html
    assert '<script src="bundle.min.js" defer></script>' in prod_html

    # Alohida CSS va JS fayllar production HTML da yo'qligi
    assert 'href="rasxod.css"' not in prod_html
    assert 'href="kaloriya.css"' not in prod_html
    assert 'src="games.js"' not in prod_html
    assert 'src="music.js"' not in prod_html

    # DevTools va console shield mavjudligi
    assert "Bauntys Production Security Shield" in prod_html
    assert "contextmenu" in prod_html
    assert "debugger" in prod_html


def test_bundle_files_exist_and_no_sourcemaps():
    """bundle.min.js va bundle.min.css mavjudligi va source map directive lari yo'qligi."""
    dist_dir = BASE_DIR / "webapp" / "dist"
    bundle_js = dist_dir / "bundle.min.js"
    bundle_css = dist_dir / "bundle.min.css"
    shield_js = dist_dir / "shield.min.js"

    assert bundle_js.exists(), "bundle.min.js mavjud emas"
    assert bundle_css.exists(), "bundle.min.css mavjud emas"
    assert shield_js.exists(), "shield.min.js mavjud emas"

    js_text = bundle_js.read_text(encoding="utf-8")
    css_text = bundle_css.read_text(encoding="utf-8")
    shield_text = shield_js.read_text(encoding="utf-8")

    assert "//# sourceMappingURL" not in js_text
    assert "//# sourceMappingURL" not in css_text
    assert "//# sourceMappingURL" not in shield_text

    # Shield da F12 va context menu to'siqlari
    assert "keyCode === 123" in shield_text
    assert "contextmenu" in shield_text
    assert "antiDebugCheck" in shield_text


@pytest.mark.asyncio
async def test_sourcemap_blocked_with_403_by_shield():
    """Source map (*.map) so'rovlari 403 Forbidden bilan to'silishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp1 = await client.get("/bundle.min.js.map")
        assert resp1.status == 403
        data1 = await resp1.json()
        assert data1["ok"] is False
        assert data1["error"] == "forbidden"

        resp2 = await client.get("/webapp/bundle.min.js.map")
        assert resp2.status == 403

        resp3 = await client.get("/app.js.map")
        assert resp3.status == 403
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_web_server_serves_bundles_and_headers():
    """Server bundle.min.js, bundle.min.css va shield.min.js ni to'g'ri sarlavhalar bilan berishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. /index.html production html qaytarishi
        resp_idx = await client.get("/index.html")
        assert resp_idx.status == 200
        assert resp_idx.headers.get("X-SourceMap") == "none"
        html = await resp_idx.text()
        assert "bundle.min.js" in html
        assert "bundle.min.css" in html

        # 2. bundle.min.js
        resp_js = await client.get("/bundle.min.js")
        assert resp_js.status == 200
        assert "max-age=86400" in resp_js.headers.get("Cache-Control", "")
        js_body = await resp_js.text()
        assert len(js_body) > 10000

        # 3. bundle.min.css
        resp_css = await client.get("/bundle.min.css")
        assert resp_css.status == 200
        assert "max-age=86400" in resp_css.headers.get("Cache-Control", "")
        css_body = await resp_css.text()
        assert len(css_body) > 5000

        # 4. shield.min.js
        resp_sh = await client.get("/shield.min.js")
        assert resp_sh.status == 200
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_subscription_middleware_caching():
    """SubscriptionMiddleware ning in-memory TTL keshi va ortiqcha API so'rovlarini bartaraf etishi."""
    from unittest.mock import AsyncMock, MagicMock
    from database.models import SponsorChannel

    middleware = SubscriptionMiddleware()
    mock_bot = AsyncMock()
    mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))

    mock_event = MagicMock()
    mock_event.text = "Salom"
    mock_user = MagicMock()
    mock_user.id = 77712345
    mock_user.is_bot = False

    data = {
        "event_from_user": mock_user,
        "bot": mock_bot,
    }

    dummy_handler = AsyncMock(return_value="handled_ok")

    # Mock faol kanallar
    fake_channel = SponsorChannel(id=1, channel_id=-1001234567890, title="Test Channel", is_active=True)
    _CHANNELS_CACHE["channels"] = [fake_channel]
    _CHANNELS_CACHE["ts"] = time.monotonic()

    # 1-chaqiriq: a'zolik tekshiriladi
    res1 = await middleware(dummy_handler, mock_event, data)
    assert res1 == "handled_ok"
    assert mock_bot.get_chat_member.call_count == 1

    # 2-chaqiriq darhol: keshdan olinishi shart (bot.get_chat_member qayta chaqirilmasligi kerak!)
    res2 = await middleware(dummy_handler, mock_event, data)
    assert res2 == "handled_ok"
    assert mock_bot.get_chat_member.call_count == 1, "Kesh ishlamadi! bot.get_chat_member qayta chaqirildi"

    # check_subscription bosilganda kesh tozalanadi va qayta tekshiriladi
    cb_event = MagicMock()
    cb_event.data = "check_subscription"
    res3 = await middleware(dummy_handler, cb_event, data)
    assert res3 == "handled_ok"


def test_bundle_min_js_valid_syntax_and_no_string_corruption():
    """bundle.min.js da stringlar (masalan image/*) kesilib ketmagani va sintaktik xato yo'qligi."""
    dist_dir = BASE_DIR / "webapp" / "dist"
    bundle_js = dist_dir / "bundle.min.js"
    assert bundle_js.exists()

    text = bundle_js.read_text(encoding="utf-8")
    assert 'accept: "image/*"' in text or 'accept:"image/*"' in text, "image/* stringi buzulgan!"
    assert 'accept: "image\n' not in text, "Tugallanmagan unclosed string topildi!"

    # Node.js orqali tekshirish
    import subprocess
    try:
        res = subprocess.run(["node", "--check", str(bundle_js)], capture_output=True, text=True)
        assert res.returncode == 0, f"bundle.min.js sintaktik xatoga ega: {res.stderr}"
    except FileNotFoundError:
        pass


@pytest.mark.asyncio
async def test_catalog_cache_invalidation_and_zero_serialization():
    """/api/catalog maintenance o'zgarganda darhol yangilanishi va keshdan tezkor bytes qaytarishi."""
    from services.maintenance_service import maintenance_service
    from services.web_server import handle_get_catalog, _CATALOG_CACHE
    import json
    from unittest.mock import MagicMock

    _CATALOG_CACHE.clear()
    req = MagicMock()

    # 1. Odatiy holatda so'rov (maintenance=None/false)
    maintenance_service.set_global_maintenance(False)
    resp1 = await handle_get_catalog(req)
    assert resp1.status == 200
    body1 = json.loads(resp1.body.decode("utf-8"))
    assert body1["maintenance"]["global"]["enabled"] is False
    assert _CATALOG_CACHE.get("bytes") is not None

    cached_bytes_ref = _CATALOG_CACHE["bytes"]

    # 2. 2-so'rov keshdan tayyor bytes bilan kelishi (0 serialization)
    resp2 = await handle_get_catalog(req)
    assert resp2.status == 200
    assert resp2.body is cached_bytes_ref

    # 3. Admin profilaktikani yoqdi -> kesh darhol yangilanishi shart
    maintenance_service.set_global_maintenance(True)
    resp3 = await handle_get_catalog(req)
    assert resp3.status == 200
    body3 = json.loads(resp3.body.decode("utf-8"))
    assert body3["maintenance"]["global"]["enabled"] is True
    assert resp3.body is not cached_bytes_ref

    # 4. Profilaktikani o'chirish -> yana darhol aks etishi
    maintenance_service.set_global_maintenance(False)
    resp4 = await handle_get_catalog(req)
    assert resp4.status == 200
    body4 = json.loads(resp4.body.decode("utf-8"))
    assert body4["maintenance"]["global"]["enabled"] is False


@pytest.mark.asyncio
async def test_bundle_compression_headers():
    """bundle.min.js va bundle.min.css so'rovlarida gzip kompressiya ishlashi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp_js = await client.get("/bundle.min.js", headers={"Accept-Encoding": "gzip"})
        assert resp_js.status == 200
        assert resp_js.headers.get("Content-Encoding") == "gzip"

        resp_css = await client.get("/bundle.min.css", headers={"Accept-Encoding": "gzip"})
        assert resp_css.status == 200
        assert resp_css.headers.get("Content-Encoding") == "gzip"
    finally:
        await client.close()

