"""
Tests for AsilMedia real-time integration, upstream catalog delegation,
white-label branding protection, and new sections (rasxod, kaloriya, mafia, kattalar).
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web

from services.web_server import create_web_app, sanitize_catalog_text
import services.web_server as ws
from services.asilmedia_service import AsilmediaMovie
from config import config, BASE_DIR

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)"
}


@pytest.mark.asyncio
async def test_catalog_api_has_asil_and_missing_sections():
    """Catalog API da asil va barcha yangi bo'limlar yoqilganligi hamda Bauntys brendi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/catalog", headers=BROWSER_HEADERS)
        assert resp.status == 200
        data = await resp.json()
        assert data.get("asil") is True
        assert data.get("rasxod") is True
        assert data.get("kal") is True
        assert data.get("mafia") is True
        assert data.get("kattalar") is True
        assert data.get("tv") is True
        assert data.get("music") is True
        assert data.get("books") is True
        assert data.get("games") is True
        assert data.get("docs") is True
        assert "items" in data

        bot_str = str(data.get("bot", "")).lower()
        chan_str = str(data.get("channel", "")).lower()
        assert "zakirov" not in bot_str
        assert "zakirova" not in bot_str
        assert "zakirov" not in chan_str
        assert "zakirova" not in chan_str
        assert "baunty" in bot_str or "baunty" in chan_str
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_asil_home_realtime_endpoint():
    """AsilMedia /api/asil/home real-time endpointi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/asil/home", headers=BROWSER_HEADERS)
        assert resp.status == 200
        data = await resp.json()
        assert data.get("ok") is True
        assert "film" in data
        assert "serial" in data
        assert "pop" in data
        # Check white-label sanitization on home content
        text_data = str(data).lower()
        assert "dilbarzakirova" not in text_data
        assert "zakirovs" not in text_data
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_asil_list_and_search_endpoints():
    """AsilMedia /api/asil/list va /api/asil/search endpointlari."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. list
        resp = await client.get("/api/asil/list?tab=film&page=1", headers=BROWSER_HEADERS)
        assert resp.status == 200
        data = await resp.json()
        assert data.get("ok") is True
        assert "items" in data or "list" in data

        # 2. search
        s_resp = await client.get("/api/asil/search?q=qasoskorlar", headers=BROWSER_HEADERS)
        assert s_resp.status == 200
        s_data = await s_resp.json()
        assert s_data.get("ok") is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_asil_item_and_fallback_to_local_service():
    """AsilMedia /api/asil/item va upstream uzilganda lokal asilmedia_service fallback."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Mavjud bo'lgan kino ID si bilan so'rov
        h_resp = await client.get("/api/asil/home", headers=BROWSER_HEADERS)
        h_data = await h_resp.json()
        pop_list = h_data.get("pop") or h_data.get("film") or []
        real_id = pop_list[0]["id"] if pop_list else 11637

        resp = await client.get(f"/api/asil/item?id={real_id}", headers=BROWSER_HEADERS)
        assert resp.status == 200
        data = await resp.json()
        assert data.get("ok") is True

        # 2. Upstream xatolik bergan taqdirda lokal fallback tekshiruvi
        fake_movie = AsilmediaMovie(
            id="8888",
            title="Test Kino",
            orig_title="Test Movie",
            year=2024,
            poster="https://example.com/p.jpg",
            rating=8.5,
            genres=["Jangari"],
            description="Lokal zaxira tavsif",
            duration="120 daqiqa",
            url="https://asilmedia.org/8888.html"
        )
        with patch("aiohttp.ClientSession.get", side_effect=Exception("Network down")):
            with patch("services.asilmedia_service.asilmedia_service.get_movie_details", new_callable=AsyncMock) as mock_local:
                mock_local.return_value = fake_movie
                fb_resp = await client.get("/api/asil/item?id=8888", headers=BROWSER_HEADERS)
                assert fb_resp.status == 200
                fb_data = await fb_resp.json()
                assert fb_data.get("ok") is True
                assert fb_data.get("item", {}).get("t") == "Test Kino"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_asil_colls_and_coll():
    """AsilMedia /api/asil/colls va /api/asil/coll?slug=... endpointlari."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/asil/colls", headers=BROWSER_HEADERS)
        assert resp.status == 200
        data = await resp.json()
        assert data.get("ok") is True

        # Asil to'plam slug bo'yicha
        resp2 = await client.get("/api/asil/coll?slug=hayvonlar-haqida-multfilmlar", headers=BROWSER_HEADERS)
        assert resp2.status == 200
        data2 = await resp2.json()
        assert data2.get("ok") is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_asil_send_validation_and_delivery():
    """AsilMedia /api/asil/send endpointida auth, spoofing va deliver_movie integratsiyasi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Bo'sh id bo'lsa not_found
        resp = await client.post("/api/asil/send", json={}, headers=BROWSER_HEADERS)
        assert resp.status == 200
        data = await resp.json()
        assert data.get("ok") is False
        assert data.get("error") == "not_found"

        # 2. User ID bo'lmasa need_start
        resp = await client.post("/api/asil/send", json={"id": "123"}, headers=BROWSER_HEADERS)
        assert resp.status == 200
        data = await resp.json()
        assert data.get("ok") is False
        assert data.get("error") == "need_start"
        assert "url" in data

        # 3. Muvaffaqiyatli yetkazish (mock bot va deliver_movie)
        mock_bot = AsyncMock()
        mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
        orig_bot = ws._bot_instance
        ws._bot_instance = mock_bot

        with patch.object(ws.movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.return_value = True
            with patch.object(ws.security_service, "verify_telegram_user", return_value=(12345678, True, None)):
                resp = await client.post("/api/asil/send", json={"id": "123", "user_id": 12345678, "part": 1}, headers=BROWSER_HEADERS)
                assert resp.status == 200
                data = await resp.json()
                assert data.get("ok") is True
                assert data.get("delivered") is True
                mock_deliver.assert_awaited_once_with(
                    bot=mock_bot,
                    chat_id=12345678,
                    code="123",
                    part=1
                )
        ws._bot_instance = orig_bot
    finally:
        await client.close()


def test_upstream_branding_sanitization():
    """Upstream brendingini 100% tozalash testi."""
    raw_text = (
        "Zakirovs Films taqdim etadi. Botimiz @Zakirovsfilms_bot va kanalimiz https://t.me/dilbarzakirova. "
        "Yana bir bot @Zakirov_bot va @Zakirovsfilm_bot. Zakirov kino olami."
    )
    clean = sanitize_catalog_text(raw_text)
    assert "Zakirov" not in clean
    assert "zakirov" not in clean
    assert "dilbarzakirova" not in clean
    assert "Baunty" in clean
    assert config.BOT_USERNAME.lstrip('@') in clean


@pytest.mark.asyncio
async def test_new_modules_upstream_proxy_routes():
    """Rasxod, Kaloriya, Mafia, Duel bo'limlari proxy marshrutlari mavjudligi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Har bir yangi modul routerda ro'yxatga olingan bo'lishi va 404 (topilmadi) bo'lmasligi shart
        routes = [
            ("GET", "/api/rasxod/home"),
            ("POST", "/api/kal/profile"),
            ("GET", "/api/mafia/home"),
            ("POST", "/api/duel/find")
        ]
        for method, route in routes:
            resp = await client.request(method, route, headers=BROWSER_HEADERS, json={})
            # 200 (muvaffaqiyat), 401 (auth kerak), yoki 502 (upstream tarmoq)
            assert resp.status in (200, 401, 502), f"Route {route} kutilmagan status: {resp.status}"
    finally:
        await client.close()


def test_webapp_assets_and_index_structure():
    """Frontend fayllarida yangi modullar, tartib va brending insoniyligi."""
    index_path = BASE_DIR / "webapp" / "index.html"
    app_js_path = BASE_DIR / "webapp" / "app.js"
    assert index_path.exists()
    assert app_js_path.exists()

    index_html = index_path.read_text(encoding="utf-8")
    app_js = app_js_path.read_text(encoding="utf-8")

    # 1. index.html dagi segmented bar tartibi (kino < music < books < games < story < docs < tv)
    assert (
        index_html.find('data-m="kino"') <
        index_html.find('data-m="music"') <
        index_html.find('data-m="books"') <
        index_html.find('data-m="games"') <
        index_html.find('data-m="story"') <
        index_html.find('data-m="docs"') <
        index_html.find('data-m="tv"')
    ), "Segmented bar tartibi buzilgan"

    # 2. Yangi bo'limlar seg va sectionlari
    for mod in ["mafia", "rasxod", "kal"]:
        assert f'data-m="{mod}"' in index_html, f"index.html da data-m='{mod}' topilmadi"
        assert f'id="{mod}"' in index_html, f"index.html da id='{mod}' container topilmadi"

    # 3. Yangi stillar va scriptlar
    for css in ["asil.css", "rasxod.css", "kaloriya.css", "mafia.css", "kattalar.css"]:
        assert f'href="{css}"' in index_html, f"index.html da {css} ulanmagan"
        assert (BASE_DIR / "webapp" / css).exists(), f"webapp/{css} fayli mavjud emas"

    for js in ["i18n.js", "asil.js", "rasxod.js", "kaloriya.js", "mafia.js", "kattalar.js"]:
        assert f'src="{js}"' in index_html, f"index.html da {js} ulanmagan"
        assert (BASE_DIR / "webapp" / js).exists(), f"webapp/{js} fayli mavjud emas"

    # 4. ASIL integratsiyasi app.js va index.html da
    for code in [index_html, app_js]:
        assert "ASIL" in code
        assert "ZAsil.render" in code
        assert "ZAsil.random" in code
        assert "ZAsil.chips" in code
        assert "ZAsil.busy" in code

    # 5. Oq brending tekshiruvi: barcha yangi webapp fayllarida 0 ta yot brend
    for fname in ["asil.js", "asil.css", "rasxod.js", "rasxod.css", "kaloriya.js", "kaloriya.css", "mafia.js", "mafia.css", "kattalar.js", "kattalar.css", "i18n.js"]:
        fpath = BASE_DIR / "webapp" / fname
        fcontent = fpath.read_text(encoding="utf-8").lower()
        assert "zakirov" not in fcontent, f"webapp/{fname} da 'zakirov' brendingi topildi!"
        assert "dilbarzakirova" not in fcontent, f"webapp/{fname} da 'dilbarzakirova' topildi!"


@pytest.mark.asyncio
async def test_asil_send_slot_to_part_resolution():
    """Mini Appda slot bosilganda (masalan, 2-qism slot 243) handle_asil_send part=2 ni aniqlashi."""
    import json
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Cache ga ko'p qismli serial kiritamiz
        sample_item = {
            "id": 11637,
            "t": "Ruhshunos",
            "seasons": [
                {
                    "n": 1,
                    "eps": [
                        {"e": 1, "name": "1-qism", "f": [{"s": 240, "q": "1080p", "ok": True}]},
                        {"e": 2, "name": "2-qism", "f": [{"s": 243, "q": "1080p", "ok": True}]},
                        {"e": 5, "name": "5-qism", "f": [{"s": 255, "q": "1080p", "ok": True}]},
                    ]
                }
            ]
        }
        ws._ASIL_API_CACHE["asil:item:11637"] = {
            "body": json.dumps({"ok": True, "item": sample_item}).encode("utf-8"),
            "ts": 9999999999.0
        }

        mock_bot = AsyncMock()
        mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
        orig_bot = ws._bot_instance
        ws._bot_instance = mock_bot

        with patch.object(ws.movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.return_value = True
            with patch.object(ws.security_service, "verify_telegram_user", return_value=(12345678, True, None)):
                # 1. Slot 243 yuboriladi -> part=2 deb aniqlanishi shart
                resp = await client.post(
                    "/api/asil/send",
                    json={"id": "11637", "slot": 243, "user_id": 12345678},
                    headers=BROWSER_HEADERS
                )
                assert resp.status == 200
                data = await resp.json()
                assert data.get("ok") is True
                assert data.get("part") == 2
                mock_deliver.assert_awaited_with(
                    bot=mock_bot,
                    chat_id=12345678,
                    code="11637",
                    part=2
                )

                # 2. Aniq part=5 yuboriladi -> part=5 chaqirilishi shart
                mock_deliver.reset_mock()
                resp5 = await client.post(
                    "/api/asil/send",
                    json={"id": "11637", "part": 5, "slot": 255, "user_id": 12345678},
                    headers=BROWSER_HEADERS
                )
                assert resp5.status == 200
                data5 = await resp5.json()
                assert data5.get("ok") is True
                assert data5.get("part") == 5
                mock_deliver.assert_awaited_with(
                    bot=mock_bot,
                    chat_id=12345678,
                    code="11637",
                    part=5
                )
        ws._bot_instance = orig_bot
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_movie_service_sync_catalog_and_fastpath():
    """movie_service.sync_catalog_from_upstream real-time va fast-path sync testi."""
    from services.movie_service import movie_service, MovieService
    from database.session import get_session

    # 1. sync_catalog_from_upstream
    async with get_session() as session:
        count = await movie_service.sync_catalog_from_upstream(session=session)
        assert count is not None and count >= 0
        cat_718 = movie_service.get_catalog_item("718")
        assert cat_718 is not None
        assert "Taksi" in cat_718["t"]

    # 2. Fast-path sync_movie_from_asilmedia
    fake_item_resp = {
        "ok": True,
        "item": {
            "id": 99991,
            "t": "Test Film Premyera",
            "desc": "Tavsif @Zakirovsfilms_bot",
            "watch": "https://samplelib.com/lib/preview/mp4/sample-5s.mp4",
            "p": "https://example.com/poster.webp",
            "y": 2026,
            "g": ["Jangari"],
            "type": "film",
            "files": [{"s": 1, "q": "1080p", "ok": True}]
        }
    }
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=fake_item_resp)
        mock_get.return_value.__aenter__.return_value = mock_resp

        async with get_session() as session:
            res = await MovieService.sync_movie_from_asilmedia(code="99991", session=session)
            assert res.get("success") is True
            assert "Baunty" in res.get("title", "") or "Test Film Premyera" in res.get("title", "")
            # Katalog keshiga ham qo'shilganini tekshiramiz
            cached = movie_service.get_catalog_item("99991")
            assert cached is not None
