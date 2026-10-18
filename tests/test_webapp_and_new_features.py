"""
Mini App web serveri, yangi API lar va yangi bot handlerlari uchun testlar
"""
import pytest
import os
from aiohttp.test_utils import TestClient, TestServer
from database.session import init_db, get_session
from database.models import User
from database import crud
from services.web_server import create_web_app
from services.doc_service import doc_service
from utils.translit import cyrillic_to_latin, latin_to_cyrillic, get_both_scripts


def test_transliteration_two_way():
    """Kirill va Lotin yozuvlari o'rtasidagi ikki tomonlama transliteratsiya testi."""
    cyr = "Форсаж 10"
    lat = cyrillic_to_latin(cyr)
    assert "Forsaj 10" in lat

    orig_lat = "Qasoskorlar"
    cyr_conv = latin_to_cyrillic(orig_lat)
    assert len(cyr_conv) > 0

    l_script, c_script = get_both_scripts("Avatar")
    assert "avatar" in l_script
    assert len(c_script) > 0


def test_doc_service_tools(tmp_path):
    """Hujjatlar xizmati vositalari testi (tahlil, PDF, tarjima)."""
    text = "Salom dunyo! Bu test matni bo'lib, so'zlar sonini hisoblash uchun xizmat qiladi."
    analysis = doc_service.analyze_text(text)
    assert analysis["words_count"] > 5
    assert analysis["chars_total"] > 20
    assert analysis["read_time_min"] >= 1

    # Simple PDF generation
    pdf_path = str(tmp_path / "test_doc.pdf")
    doc_service.create_simple_pdf("Arizanoma", text, pdf_path)
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 100

    # Translation
    en_trans = doc_service.simple_translate("salom", target_lang="en")
    assert "Hello" in en_trans
    ru_trans = doc_service.simple_translate("rahmat", target_lang="ru")
    assert "Спасибо" in ru_trans


@pytest.mark.asyncio
async def test_seed_movies_catalog():
    """Bazada kamida 180 ta kino seed qilinganligini tekshirish."""
    await init_db()
    async with get_session() as session:
        count = await crud.get_total_movies_count(session)
        assert count >= 180, f"Kutilgan kinolar soni >= 180, biroq {count} ta topildi"


@pytest.mark.asyncio
async def test_smart_search_latin_and_cyrillic():
    """Kino qidiruvida ham Lotin, ham Kirill yozuvlarida topilishini tekshirish."""
    await init_db()
    async with get_session() as session:
        # Lotincha qidiruv
        res_lat = await crud.smart_search_movies(session, query="Forsaj")
        assert len(res_lat) > 0
        assert any("Forsaj" in m.title for m in res_lat)

        # Kirillcha qidiruv
        res_cyr = await crud.smart_search_movies(session, query="Форсаж")
        assert len(res_cyr) > 0
        assert any("Forsaj" in m.title for m in res_cyr)


@pytest.mark.asyncio
async def test_referral_and_feedback():
    """Referal ballari va fikr-mulohazalar CRUD testi."""
    await init_db()
    async with get_session() as session:
        from sqlalchemy import delete
        await session.execute(delete(User).where(User.id.in_([990001, 990002])))
        await session.flush()

        u1, _ = await crud.get_or_create_user(session, user_id=990001, username="ref_master")
        u2, _ = await crud.get_or_create_user(session, user_id=990002, username="new_invite")

        success = await crud.add_referral(session, referrer_id=990001, new_user_id=990002, points=10)
        assert success is True

        count, points = await crud.get_referral_stats(session, user_id=990001)
        assert count == 1
        assert points == 10

        fb = await crud.create_feedback(session, user_id=990001, username="ref_master", message="Ajoyib bot!")
        assert fb.id is not None
        assert fb.message == "Ajoyib bot!"


@pytest.mark.asyncio
async def test_webapp_health_endpoint():
    """Render.com health check /health endpointi testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert "bot" in data
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_movies_api():
    """/api/movies va /api/movies/{code} API endpointlari testi."""
    await init_db()
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Barcha kinolar
        resp = await client.get("/api/movies?limit=20")
        assert resp.status == 200
        data = await resp.json()
        assert data["total"] >= 180
        assert len(data["items"]) == 20

        # Smart search Latin
        resp_q = await client.get("/api/movies?q=Forsaj")
        data_q = await resp_q.json()
        assert len(data_q["items"]) > 0

        # Smart search Cyrillic
        resp_cyr = await client.get("/api/movies?q=Форсаж")
        data_cyr = await resp_cyr.json()
        assert len(data_cyr["items"]) > 0

        # Detail
        resp_det = await client.get("/api/movies/101")
        assert resp_det.status == 200
        det_data = await resp_det.json()
        assert det_data["code"] == "101"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_music_api():
    """/api/music va /api/music/shazam API endpointlari testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/music?category=top50")
        assert resp.status == 200
        data = await resp.json()
        assert len(data["items"]) > 0
        assert len(data["moods"]) >= 6

        # Shazam
        resp_shazam = await client.post("/api/music/shazam")
        assert resp_shazam.status == 200
        shazam_data = await resp_shazam.json()
        assert shazam_data["success"] is True
        assert "track" in shazam_data
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_tv_api():
    """/api/tv endpointi va 114 ta kanal testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/tv?category=all")
        assert resp.status == 200
        data = await resp.json()
        assert data["total"] >= 130
        assert len(data["items"]) >= 130
        assert len(data["categories"]) >= 8

        # Sport toifasi
        resp_sport = await client.get("/api/tv?category=sport")
        data_sport = await resp_sport.json()
        assert len(data_sport["items"]) >= 5
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_games_api():
    """/api/games, chest va pet endpointlari testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/games")
        assert resp.status == 200
        data = await resp.json()
        assert data["total"] == 50
        assert len(data["games"]) == 50

        # Chest claim
        resp_chest = await client.post("/api/games/chest/claim")
        assert resp_chest.status == 200
        chest_data = await resp_chest.json()
        assert chest_data["success"] is True
        assert chest_data["reward"] > 0

        # Pet action
        resp_pet = await client.post("/api/games/pet/action", json={"action": "feed"})
        assert resp_pet.status == 200
        pet_data = await resp_pet.json()
        assert pet_data["success"] is True
        assert "mazza" in pet_data["message"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_story_and_docs_api():
    """/api/story va /api/docs/convert API lari testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Story
        resp_story = await client.get("/api/story?username=uzb_kino")
        assert resp_story.status == 200
        story_data = await resp_story.json()
        assert story_data["username"] == "uzb_kino"
        assert len(story_data["stories"]) > 0

        # Docs translit
        resp_doc = await client.post("/api/docs/convert", json={"text": "Salom dunyo", "target": "cyrillic"})
        assert resp_doc.status == 200
        doc_data = await resp_doc.json()
        assert "Салом" in doc_data["result"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_docs_pdf_api():
    """/api/docs/pdf endpointi orqali to'liq valid PDF generatsiya qilish testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.post("/api/docs/pdf", json={"title": "Ariza", "text": "Bu rasmiy ariza matni hisoblanadi."})
        assert resp.status == 200
        assert resp.headers.get("Content-Type") == "application/pdf"
        body = await resp.read()
        assert body.startswith(b"%PDF-1.4")
        assert len(body) > 200
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_cors_preflight():
    """OPTIONS preflight so'rovlariga 204 va to'g'ri CORS sarlavhalari qaytishini tekshirish."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.options("/api/send_to_chat")
        assert resp.status == 204
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_send_to_chat_api():
    """/api/send_to_chat endpointi (kino va musiqa yuborish) testi."""
    from unittest.mock import AsyncMock
    from services.web_server import set_bot_instance

    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_video = AsyncMock()
    mock_bot.send_audio = AsyncMock()
    set_bot_instance(mock_bot)

    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Kino yuborish
        resp_movie = await client.post("/api/send_to_chat", json={"user_id": 12345, "type": "movie", "code": "101"})
        assert resp_movie.status == 200
        data_movie = await resp_movie.json()
        assert data_movie["success"] is True

        # 2. Musiqa yuborish
        resp_music = await client.post("/api/send_to_chat", json={"user_id": 12345, "type": "music", "title": "O'ylama", "artist": "Konsta"})
        assert resp_music.status == 200
        data_music = await resp_music.json()
        assert data_music["success"] is True

        # 3. Noto'g'ri user_id
        resp_bad = await client.post("/api/send_to_chat", json={"user_id": "not_an_id", "type": "movie", "code": "101"})
        assert resp_bad.status == 400
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_video_service_round_conversion(tmp_path):
    """video_service orqali videoni dumaloq (video note) formatiga o'tkazish testi."""
    import subprocess
    from services.video_service import video_service
    from config import config

    ffmpeg_bin = config.ffmpeg_path
    if not ffmpeg_bin:
        pytest.skip("ffmpeg o'rnatilmagan")

    test_in = str(tmp_path / "test_in.mp4")
    # 1 soniyalik sinov videosi yaratish
    cmd = [ffmpeg_bin, "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10", test_in]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        pytest.skip("ffmpeg testsrc ishlamadi")

    out_file = await video_service.convert_to_round_video(test_in)
    assert out_file is not None
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 100
    from utils.helpers import safe_remove_file
    safe_remove_file(out_file)


def test_config_webapp_url_resolution(monkeypatch):
    """Render.com va .env dan WebApp URL ini to'g'ri HTTPS ga aylantirish testi."""
    from config import Settings

    # 1. Oddiy HTTPS berilganda
    s1 = Settings(WEBAPP_URL="https://mybot.onrender.com")
    assert s1.webapp_url_resolved == "https://mybot.onrender.com"

    # 2. Protokolsiz berilganda
    s2 = Settings(WEBAPP_URL="mybot.onrender.com")
    assert s2.webapp_url_resolved == "https://mybot.onrender.com"

    # 3. WEBAPP_URL bo'sh bo'lib, RENDER_EXTERNAL_URL mavjud bo'lganda
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://auto.onrender.com")
    s3 = Settings(WEBAPP_URL="")
    assert s3.webapp_url_resolved == "https://auto.onrender.com"


def test_movie_code_extraction():
    """Kino kodini har xil formatlarda (#101, №101, kod 101, 101) to'g'ri ajratib olish testi."""
    from handlers.movies import extract_movie_code

    assert extract_movie_code("101") == "101"
    assert extract_movie_code("#101") == "101"
    assert extract_movie_code("№101") == "101"
    assert extract_movie_code("kod 101") == "101"
    assert extract_movie_code("kod: 101") == "101"
    assert extract_movie_code("код 101") == "101"
    assert extract_movie_code("Salom dunyo") is None
    assert extract_movie_code("https://instagram.com/p/12345") is None


@pytest.mark.asyncio
async def test_poster_proxy_and_catalog_api():
    """Poster proxy va sanitizatsiya qilingan oq brend katalog API testi."""
    from config import config
    from services.web_server import create_web_app
    from aiohttp.test_utils import TestServer, TestClient

    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Katalog API
        resp_cat = await client.get("/api/catalog")
        assert resp_cat.status == 200
        cat_data = await resp_cat.json()
        assert "items" in cat_data
        assert len(cat_data["items"]) >= 170
        assert cat_data["channel"] == config.CHANNEL_USERNAME
        assert cat_data["bot"] == config.BOT_USERNAME.lstrip("@")

        # Barcha tavsiflarda Zakirovlar olib tashlanganligini tekshirish
        for it in cat_data["items"]:
            desc = it.get("d", "")
            assert "@Zakirovsfilms_bot" not in desc
            assert "@ZakirovsKino" not in desc

        # 2. Poster proxy API
        resp_poster = await client.get("/p/284_s.webp")
        assert resp_poster.status == 200
        assert "image/webp" in resp_poster.headers.get("Content-Type", "")
        img_bytes = await resp_poster.read()
        assert len(img_bytes) > 1000

        # 3. Watch API
        resp_watch = await client.post("/api/watch", json={"code": 284, "part": 1})
        assert resp_watch.status == 200
        watch_data = await resp_watch.json()
        assert watch_data["ok"] is True
        assert watch_data["code"] == "284"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_webapp_watch_with_delivery_and_fallback():
    """/api/watch da foydalanuvchi chatiga rostdan ham yetkazish va fallback testlari."""
    from unittest.mock import AsyncMock
    from services.web_server import set_bot_instance

    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_video = AsyncMock()
    mock_bot.send_photo = AsyncMock()
    set_bot_instance(mock_bot)

    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. user_id bilan yuborilganda va bot mavjud bo'lganda muvaffaqiyatli yetkazish
        resp = await client.post("/api/watch", json={"code": "284", "part": 1, "user_id": 998877})
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert data["delivered"] is True
        assert data["code"] == "284"

        # 2. deliver_movie xatolik berganda yoki bot xabar yubora olmaganda open_bot qaytarish
        mock_bot.send_message.side_effect = Exception("Forbidden: bot was blocked by the user")
        mock_bot.send_photo.side_effect = Exception("Forbidden: bot was blocked by the user")
        mock_bot.send_video.side_effect = Exception("Forbidden: bot was blocked by the user")
        resp_fail = await client.post("/api/watch", json={"code": "99999", "part": 1, "user_id": 998877})
        assert resp_fail.status == 200
        data_fail = await resp_fail.json()
        assert data_fail["ok"] is False
        assert data_fail["action"] == "open_bot"
        assert "t.me" in data_fail["url"]

        # 3. bot_instance None bo'lganda va user_id bo'lganda open_bot qaytarish
        set_bot_instance(None)
        resp_nobot = await client.post("/api/watch", json={"code": "284", "part": 1, "user_id": 998877})
        assert resp_nobot.status == 200
        data_nobot = await resp_nobot.json()
        assert data_nobot["ok"] is False
        assert data_nobot["action"] == "open_bot"
        assert "m_284" in data_nobot["url"]
    finally:
        set_bot_instance(None)
        await client.close()


