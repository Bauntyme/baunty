"""
Yangi bo'limlar (Food, Quiz, FX, Book Cover Proxy, TV 4K Instant Connection) uchun testlar.
"""
import pytest
from aiohttp.test_utils import TestClient, TestServer
from services.web_server import create_web_app
from config import BASE_DIR


@pytest.mark.asyncio
async def test_api_catalog_includes_all_10_sections():
    """Catalog API da barcha 10 ta bo'lim bayroqlari yoqilgan bo'lishi testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/catalog")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("tv") is True
        assert data.get("music") is True
        assert data.get("docs") is True
        assert data.get("games") is True
        assert data.get("story") is True
        assert data.get("books") is True
        assert data.get("food") is True
        assert data.get("quiz") is True
        assert data.get("fx") is True
        assert "items" in data
        # Oq brending
        assert "Zakirovs" not in str(data.get("bot", ""))
        assert "zakirov" not in str(data.get("channel", "")).lower()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_upstream_proxy_routes_food_quiz_fx():
    """Food, Quiz va FX uchun web server API proxy endpointlari ishlashini tekshirish."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Food endpoint
        f_resp = await client.get("/api/food")
        assert f_resp.status in (200, 502)
        if f_resp.status == 200:
            f_data = await f_resp.json()
            assert "items" in f_data or "ok" in f_data

        # 2. Quiz endpoint
        q_resp = await client.get("/api/quiz/home")
        assert q_resp.status in (200, 502)
        if q_resp.status == 200:
            q_data = await q_resp.json()
            assert "topics" in q_data or "popular" in q_data

        # 3. FX endpoint
        fx_resp = await client.get("/api/fx")
        assert fx_resp.status in (200, 502)
        if fx_resp.status == 200:
            fx_data = await fx_resp.json()
            assert "items" in fx_data or "ok" in fx_data
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_bk_asset_proxy_endpoint():
    """/bk/{tail} endpointi orqali kitob muqovalarini yuklab berish va keshdan o'qish testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/bk/1871/cover_s.webp")
        # Agar internet mavjud bo'lsa 200 va image/webp, offline bo'lsa 404
        assert resp.status in (200, 404)
        if resp.status == 200:
            assert resp.content_type == "image/webp"
            body = await resp.read()
            assert len(body) > 100
    finally:
        await client.close()


def test_webapp_index_has_all_10_navigation_modules():
    """webapp/index.html da barcha 10 ta modul tugmalari, scriptlari va stillari mavjudligi."""
    html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")

    # 1. Navigation tugmalari
    for m in ["kino", "music", "books", "games", "story", "docs", "quiz", "food", "fx", "tv"]:
        assert f'data-m="{m}"' in html, f"Modul tugmasi data-m='{m}' topilmadi"

    # 2. Stillar
    for c in ["music.css", "docs.css", "games.css", "story.css", "books.css", "food.css", "quiz.css", "fx.css", "zk.css"]:
        assert f'href="{c}"' in html, f"CSS fayli {c} ulanmagan"

    # 3. Scriptlar
    for s in ["zk.js", "music.js", "docs.js", "games.js", "story.js", "books.js", "food.js", "quiz.js", "fx.js"]:
        assert f'src="{s}"' in html, f"Script {s} ulanmagan"

    # 4. TV 4K va tezlik optimallashuvi
    assert "startFragPrefetch: true" in html
    assert "image-rendering: -webkit-optimize-contrast" in html
    assert "BUFFER_STALLED_ERROR" in html
    assert "preconnect" in html
