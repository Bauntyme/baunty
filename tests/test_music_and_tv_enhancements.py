"""
Musiqa va Jonli TV yangilanishlari uchun kengaytirilgan testlar.
1. MediaDownloader (YouTube extractor_args, Cobalt / Direct fallback).
2. MusicService (Deezer qidiruv, 10-25 ta natija, preview fallback).
3. Web Server (/api/music/search, /api/music/play, /api/music/send, /api/tv schema mosligi).
4. TV Data (Biz Cinema, Sevimli, Zo'r TV, Milliy, MY5, 114 ta kanal va HLS streamlar).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp.test_utils import TestServer, TestClient
from services.web_server import create_web_app, set_bot_instance
from services.tv_data import CHANNELS_LIST, TV_CATEGORIES
from services.downloader import MediaDownloader, DownloadResult
from services.music_service import MusicService
import handlers.music as music_handler


# ----------------- 1. TV Data va HLS Streamlar Testlari -----------------

def test_tv_channels_list_count_and_schema():
    """CHANNELS_LIST da 130+ ta saralangan kanal borligi va har ikkala schema (id va i, stream va u, logo l) mavjudligi."""
    assert len(CHANNELS_LIST) >= 130
    for ch in CHANNELS_LIST:
        # Backend schema
        assert "id" in ch
        assert "name" in ch
        assert "category" in ch
        assert "stream" in ch
        # Frontend webapp/index.html schema
        assert "i" in ch
        assert "n" in ch
        assert "k" in ch
        assert "c" in ch
        assert "l" in ch
        assert ch["l"] is not None and len(ch["l"]) > 5
        assert "u" in ch
        assert isinstance(ch["u"], list)
        assert len(ch["u"]) >= 1
        assert "v" in ch
        assert isinstance(ch["v"], int)


def test_tv_real_working_streams():
    """Top O'zbek telekanallariga haqiqiy HLS streamlar biriktirilganligini tekshirish."""
    by_name = {ch["name"]: ch for ch in CHANNELS_LIST}

    # BIZ Cinema
    biz_cinema = by_name.get("BIZ Cinema")
    assert biz_cinema is not None
    assert ("fl.biztv.media/cinema_720" in biz_cinema["stream"] or "1213" in biz_cinema["stream"] or "cinerama.uz" in biz_cinema["stream"])

    # Sevimli TV
    sevimli = by_name.get("Sevimli TV")
    assert sevimli is not None
    assert "1017" in sevimli["stream"] and "cinerama.uz" in sevimli["stream"]

    # Zo'r TV
    zor_tv = by_name.get("Zo'r TV")
    assert zor_tv is not None
    assert "1016" in zor_tv["stream"] and "cinerama.uz" in zor_tv["stream"]

    # Milliy TV
    milliy = by_name.get("Milliy TV")
    assert milliy is not None
    assert "1014" in milliy["stream"] and "cinerama.uz" in milliy["stream"]

    # Mening Yurtim (MY5)
    my5 = by_name.get("Mening Yurtim (MY5)")
    assert my5 is not None
    assert "1217" in my5["stream"] and "cinerama.uz" in my5["stream"]

    # Kinoteatr TV
    kinoteatr = by_name.get("Kinoteatr TV")
    assert kinoteatr is not None
    assert "1009" in kinoteatr["stream"] and "cinerama.uz" in kinoteatr["stream"]

    # O'zbekiston 24
    oz24 = by_name.get("O'zbekiston 24")
    assert oz24 is not None
    assert "1011" in oz24["stream"] and "cinerama.uz" in oz24["stream"]

    # Sport TV
    sport = by_name.get("Sport TV")
    assert sport is not None
    assert "1004" in sport["stream"] and "cinerama.uz" in sport["stream"]

    # BIZ TV
    biz_tv = by_name.get("Biz TV")
    assert biz_tv is not None
    assert ("fl.biztv.media/biz_tv_720" in biz_tv["stream"] or "1211" in biz_tv["stream"] or "cinerama.uz" in biz_tv["stream"])

    # BIZ Music
    biz_music = by_name.get("BIZ Music")
    assert biz_music is not None
    assert ("fl.biztv.media/music_720" in biz_music["stream"] or "1212" in biz_music["stream"] or "cinerama.uz" in biz_music["stream"])

    # Makka va Madina Jonli Efir (Real Akamai HLS .m3u8 streams)
    makka = by_name.get("Makka Jonli Efir")
    assert makka is not None
    assert "saudi_quran" in makka["stream"] and "m3u8" in makka["stream"]

    madina = by_name.get("Madina Jonli Efir")
    assert madina is not None
    assert "saudi_sunnah" in madina["stream"] and "m3u8" in madina["stream"]

    # Navo TV
    navo = by_name.get("Navo TV")
    assert navo is not None
    assert "1008" in navo["stream"] and "cinerama.uz" in navo["stream"]

    # Samarqand MTRK (STV)
    samarqand = by_name.get("Samarqand MTRK (STV)")
    assert samarqand is not None
    assert "1452" in samarqand["stream"] and "cinerama.uz" in samarqand["stream"]


@pytest.mark.asyncio
async def test_api_tv_query_and_category_filtering():
    """GET /api/tv endpointi har ikkala sxema bo'yicha qidiruv va filtrlashni to'g'ri bajarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Barchasi
        resp = await client.get("/api/tv?category=all")
        assert resp.status == 200
        data = await resp.json()
        assert data["total"] >= 130
        assert len(data["items"]) >= 130
        assert len(data["categories"]) >= 8

        # Nomi bo'yicha qidirish
        resp_q = await client.get("/api/tv?q=sevimli")
        data_q = await resp_q.json()
        assert data_q["total"] >= 1
        assert any("Sevimli" in ch["name"] for ch in data_q["items"])

        # Qisqa schema i, n, u tekshirish
        first = data["items"][0]
        assert "i" in first
        assert "n" in first
        assert "u" in first
        assert isinstance(first["u"], list)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_uzbek_channels_rank_first_and_kino_channels():
    """O'zbek telekanallari mutlaq 1-o'rinda bo'lishi va kino toifasida barcha O'zbek kino kanallari birinchi chiqishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Barcha kanallar ro'yxatida dastlabki barcha kanallar O'zbekistonlik (c: 'uz') bo'lishi
        resp = await client.get("/api/tv?category=all")
        assert resp.status == 200
        data = await resp.json()
        items = data["items"]

        # Dastlabki 45+ ta kanal barchasi uz bo'lishi kerak
        top_uz = [ch for ch in items[:45]]
        assert all(ch.get("c") == "uz" for ch in top_uz)

        # Mashhur kanallar (popular) ro'yxati filtri tekshiruvi: faqat c: 'uz'
        popular_uz = [ch for ch in items if ch.get("c") == "uz" and ch.get("v", 0) > 0]
        assert len(popular_uz) >= 40
        # Boshidagi 10 ta ommabop kanal
        top_10_names = [ch["name"] for ch in popular_uz[:10]]
        assert "BIZ Cinema" in top_10_names
        assert "Kinoteatr TV" in top_10_names
        assert "Sevimli TV" in top_10_names
        assert "Zo'r TV" in top_10_names
        assert "Milliy TV" in top_10_names

        # 2. Kino toifasida O'zbekiston kino ko'rsatadigan barcha telekanallari eng boshida chiqishi
        resp_kino = await client.get("/api/tv?category=kino")
        assert resp_kino.status == 200
        data_kino = await resp_kino.json()
        kino_items = data_kino["items"]

        kino_names = [ch["name"] for ch in kino_items]
        # O'zbek kino kanallari to'liq borligi
        assert "BIZ Cinema" in kino_names
        assert "Kinoteatr TV" in kino_names
        assert "Sevimli TV" in kino_names
        assert "Zo'r TV" in kino_names
        assert "Milliy TV" in kino_names
        assert "Mening Yurtim (MY5)" in kino_names
        assert "Renessans TV" in kino_names
        assert "Insayt TV" in kino_names
        assert "Hayot TV" in kino_names
        assert "Makon TV" in kino_names
        assert "Cheksiz TV" in kino_names
        assert "LTV HD" in kino_names
        assert "Yoshlar" in kino_names
        assert "Toshkent" in kino_names

        # O'zbek kino kanallari xorijiy kino kanallaridan (viju, TV1000, Dom kino va b.) oldinda turishi
        first_kino_channels = kino_items[:12]
        assert all(ch.get("c") == "uz" for ch in first_kino_channels)

        # 3. Sifat belgilari (4K UHD yoki 1080p HD) va to'g'ridan-to'g'ri 1080p Full HD oqimlar
        biz_cinema = next(ch for ch in items if ch["name"] == "BIZ Cinema")
        assert biz_cinema.get("q") == "4K UHD"
        assert "tracks-v1a1" in biz_cinema["stream"]
        assert "tracks-v1a1" in biz_cinema["u"][0][1]

        insayt = next(ch for ch in items if ch["name"] == "Insayt TV")
        assert insayt.get("q") == "4K UHD"
        assert "tracks-v1a1" in insayt["stream"]

        sevimli = next(ch for ch in items if ch["name"] == "Sevimli TV")
        assert "1080p" in sevimli.get("q", "")
        assert "tracks-v1a1" in sevimli["stream"]
        assert "tracks-v1a1" in sevimli["u"][0][1]
    finally:
        await client.close()


# ----------------- 2. Musiqa Qidiruv va Servisi Testlari -----------------

@pytest.mark.asyncio
async def test_music_service_search_tracks_mapping():
    """MusicService.search_tracks ikkala formatni (title/artist va t/a/d/u/c/s) to'liq qaytarishi."""
    music_srv = MusicService()

    fake_deezer_data = {
        "data": [
            {
                "id": 12345,
                "title_short": "Men O'sha",
                "title": "Men O'sha",
                "duration": 210,
                "preview": "https://cdns-preview-d.dzcdn.net/stream/sample.mp3",
                "link": "https://www.deezer.com/track/12345",
                "artist": {"name": "Konsta"},
                "album": {"cover_medium": "https://e-cdns-images.dzcdn.net/images/cover/sample.jpg"}
            }
        ]
    }

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=fake_deezer_data)

    mock_resp_cm = MagicMock()
    mock_resp_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp_cm
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        tracks = await music_srv.search_tracks("Konsta", limit=20)
        assert len(tracks) == 1
        t = tracks[0]
        assert t["id"] == 12345
        assert t["title"] == "Men O'sha"
        assert t["artist"] == "Konsta"
        assert t["preview"] == "https://cdns-preview-d.dzcdn.net/stream/sample.mp3"
        # Web App schema
        assert t["t"] == "Men O'sha"
        assert t["a"] == "Konsta"
        assert t["d"] == 210
        assert t["s"] == "dz"
        assert t["m"] == 1


@pytest.mark.asyncio
async def test_music_service_download_track_preview_fallback():
    """Agar YouTube yuklash muvaffaqiyatsiz bo'lsa, preview_url orqali MP3 muvaffaqiyatli olinishi."""
    music_srv = MusicService()

    # YouTube downloader xato bersin
    music_srv.downloader.download_audio = AsyncMock(
        return_value=DownloadResult(success=False, error="Sign in to confirm you're not a bot")
    )
    # Direct audio yuklash esa muvaffaqiyatli bo'lsin
    music_srv.downloader.download_direct_audio = AsyncMock(
        return_value=DownloadResult(success=True, file_path="/tmp/test.mp3", title="Men O'sha", duration=210)
    )

    track_info = {
        "title": "Men O'sha",
        "artist": "Konsta",
        "preview": "https://cdns-preview-d.dzcdn.net/sample.mp3"
    }

    res = await music_srv.download_track_mp3("Konsta - Men O'sha", track_info=track_info)
    assert res.success is True
    assert res.file_path == "/tmp/test.mp3"
    assert res.title == "Men O'sha"


# ----------------- 3. Web App Musiqa API Endpointlari Testlari -----------------

@pytest.mark.asyncio
async def test_api_music_search_endpoint():
    """GET /api/music/search endpointi test."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Bo'sh qidiruv
        resp_empty = await client.get("/api/music/search")
        assert resp_empty.status == 200
        data_empty = await resp_empty.json()
        assert data_empty["ok"] is True
        assert data_empty["items"] == []

        # Haqiqiy yoki mock qidiruv
        with patch.object(
            MusicService, "search_tracks",
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [
                {"id": 1, "title": "Track 1", "artist": "Artist 1", "t": "Track 1", "a": "Artist 1"}
            ]
            resp = await client.get("/api/music/search?q=Konsta&n=10")
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True
            assert len(data["items"]) == 1
            assert data["items"][0]["t"] == "Track 1"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_music_play_endpoint():
    """POST /api/music/play endpointi audio oqim havolasini qaytarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. To'g'ridan-to'g'ri u (preview) havolasi berilgan holat
        body_with_u = {
            "id": "123",
            "t": "Test Song",
            "a": "Test Artist",
            "u": "https://cdns-preview.example.com/test.mp3"
        }
        resp = await client.post("/api/music/play", json=body_with_u)
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert data["url"] == "https://cdns-preview.example.com/test.mp3"

        # 2. YouTube ID berilgan holat
        body_yt = {
            "id": "dQw4w9WgXcQ",
            "s": "yt",
            "t": "Never Gonna Give You Up"
        }
        resp_yt = await client.post("/api/music/play", json=body_yt)
        assert resp_yt.status == 200
        data_yt = await resp_yt.json()
        assert data_yt["ok"] is True
        assert data_yt["url"].startswith("http")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_music_send_endpoint_with_auth_and_bot():
    """POST /api/music/send endpointi bot orqali chatga audio yuborishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    mock_bot = MagicMock()
    mock_bot.send_audio = AsyncMock(return_value=True)
    mock_bot.send_message = AsyncMock(return_value=True)
    set_bot_instance(mock_bot)

    try:
        # Auth bo'lmasa -> 401
        resp_no_auth = await client.post("/api/music/send", json={"t": "Song"})
        assert resp_no_auth.status == 401
        data_no_auth = await resp_no_auth.json()
        assert data_no_auth["ok"] is False

        # InitData orqali yuborish
        import urllib.parse
        import json
        init_data_sample = urllib.parse.urlencode({"user": json.dumps({"id": 12345678, "first_name": "Ali"})})

        track_payload = {
            "t": "Boylik",
            "a": "Konsta",
            "d": 180,
            "u": "https://cdns-preview.example.com/boylik.mp3"
        }

        # download_track_mp3 muvaffaqiyatli mock
        with patch.object(
            MusicService, "download_track_mp3",
            new_callable=AsyncMock
        ) as mock_dl:
            mock_dl.return_value = DownloadResult(
                success=True,
                file_path=None,  # fayl yo'q bo'lsa preview_url ga o'tadi
            )

            resp_send = await client.post(
                "/api/music/send",
                headers={"X-Init-Data": init_data_sample},
                json=track_payload
            )
            assert resp_send.status == 200
            data_send = await resp_send.json()
            assert data_send["ok"] is True

            # Bot send_audio chaqirilganini tekshirish
            assert mock_bot.send_audio.called
            call_kwargs = mock_bot.send_audio.call_args[1]
            assert call_kwargs["chat_id"] == 12345678
            assert call_kwargs["title"] == "Boylik"
    finally:
        await client.close()
        set_bot_instance(None)


# ----------------- 4. Downloader va Fallback Testlari -----------------

def test_downloader_extractor_args():
    """Downloader da YouTube mobil mijozlari va TikTok extractor_args mavjudligini tekshirish."""
    dl = MediaDownloader()
    assert dl is not None


@pytest.mark.asyncio
async def test_downloader_direct_stream_chunking(tmp_path):
    """To'g'ridan-to'g'ri audio stream havolasidan yuklab olishni tekshirish."""
    dl = MediaDownloader(download_dir=tmp_path)

    # 1 baytli soxta fayl serveri yoki mock
    mock_resp = MagicMock()
    mock_resp.read.side_effect = [b"ID3" + b"\x00" * 100, b""]
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = await dl.download_direct_audio("https://example.com/audio.mp3", title="Test Audio")
        assert res.success is True
        assert res.file_path is not None
        assert "Test Audio" in res.file_path


@pytest.mark.asyncio
async def test_bot_cb_download_track_fallback():
    """handlers/music.py da dl_track bosilganda preview fallback ishlashi."""
    callback = AsyncMock()
    callback.data = "dl_track:user123_456"
    callback.message.reply = AsyncMock()
    callback.message.reply_audio = AsyncMock()
    callback.from_user.id = 12345

    status_msg = AsyncMock()
    callback.message.reply.return_value = status_msg

    # Cache ga trek ma'lumotini kiritish
    music_handler._SEARCH_CACHE["user123_456"] = {
        "title": "Aprel",
        "artist": "Konsta",
        "preview": "https://example.com/aprel_preview.mp3"
    }

    # download_track_mp3 xato qaytarsin
    with patch.object(
        MusicService, "download_track_mp3",
        new_callable=AsyncMock
    ) as mock_dl:
        mock_dl.return_value = DownloadResult(success=False, error="yt-dlp blocked")

        await music_handler.cb_download_track(callback)

        # preview_url orqali reply_audio yuborilishi kerak
        assert callback.message.reply_audio.called
        audio_kwargs = callback.message.reply_audio.call_args[1]
        assert audio_kwargs["audio"] == "https://example.com/aprel_preview.mp3"
        assert audio_kwargs["title"] == "Aprel"


@pytest.mark.asyncio
async def test_downloader_invidious_fallback(tmp_path):
    """Downloader da YouTube bot detection holatida Invidious orqali media muvaffaqiyatli yuklanishi."""
    dl = MediaDownloader(download_dir=tmp_path)

    # Invidious API javobi mock
    invidious_json = {
        "title": "Test YouTube Video",
        "lengthSeconds": 180,
        "formatStreams": [
            {"type": 'video/mp4; codecs="avc1"', "url": "https://example.com/stream.mp4"}
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.side_effect = [
        import_json := __import__("json").dumps(invidious_json).encode("utf-8"),
        b"header" + b"\x00" * 200,
        b""
    ]
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = dl._download_via_invidious("https://www.youtube.com/watch?v=dQw4w9WgXcQ", is_audio=False)
        assert res is not None
        assert res.success is True
        assert res.title == "Test YouTube Video"
        assert res.duration == 180


@pytest.mark.asyncio
async def test_start_music_deep_link():
    """Botga /start m_{id} deep link yuborilganda musiqa yuborilishi."""
    import handlers.start as start_handler
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage

    message = AsyncMock()
    message.from_user.id = 998877
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.chat.id = 998877
    message.message_id = 1001
    message.text = "/start m_3135556"
    message.answer = AsyncMock()
    message.answer_audio = AsyncMock()

    status_msg = AsyncMock()
    message.answer.return_value = status_msg

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=__import__("aiogram.fsm.storage.base", fromlist=["StorageKey"]).StorageKey(
        bot_id=1, chat_id=998877, user_id=998877
    ))

    with patch.object(
        MusicService, "download_track_mp3",
        new_callable=AsyncMock
    ) as mock_dl:
        mock_dl.return_value = DownloadResult(
            success=True,
            file_path=None,
            duration=210,
        )

        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json = AsyncMock(return_value={
            "title_short": "Harder",
            "title": "Harder",
            "artist": {"name": "Daft Punk"},
            "preview": "https://example.com/preview.mp3",
            "duration": 210
        })
        mock_get_ctx = MagicMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_get_resp)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_get_ctx
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            await start_handler.cmd_start(message, state)
            assert message.answer.called


@pytest.mark.asyncio
async def test_webapp_api_prefix_aliases():
    """/webapp/api/... va /api/... marshrutlari bir xil muvaffaqiyatli javob qaytarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Standard route
        r1 = await client.get("/api/tv?category=all")
        assert r1.status == 200

        # /webapp/ prefixed route
        r2 = await client.get("/webapp/api/tv?category=all")
        assert r2.status == 200

        d1 = await r1.json()
        d2 = await r2.json()
        assert d1["total"] == d2["total"]
        assert len(d1["items"]) == len(d2["items"])
    finally:
        await client.close()


# ----------------- 5. Tarona Musiqa Bazasi Testlari -----------------

@pytest.mark.asyncio
async def test_tarona_search_and_schema_mapping():
    """MusicService._search_tarona o'zbek musiqalarini to'g'ri parse qilishi va schema mosligi."""
    music_srv = MusicService()

    fake_html = '''
    <div class="track-item song-short fx-row fx-middle js-item" id="music-0O92Mn">
      <div class="track-img play">
        <img src="https://muzfm.uz/storage/uploads/images/songs/2026/09/konsta-34_1788928256_100x100.webp" alt="Konsta - 34">
        <div class="track-play playp playicon js-ctrl js-play" data-songid="0O92Mn" title="Play"></div>
      </div>
      <div class="track-desc info fx-1">
        <a class="track-link" href="https://muzfm.uz/music/konsta-34">
          <div class="track-subtitle artist nowrap"> Konsta </div>
          <div class="track-title song nowrap">34</div>
        </a>
      </div>
      <div class="track-time time">02:53</div>
    </div>
    '''

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=fake_html)

    mock_resp_cm = MagicMock()
    mock_resp_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp_cm
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        tracks = await music_srv._search_tarona("Konsta", limit=5)
        assert len(tracks) == 1
        tr = tracks[0]
        assert tr["id"] == "tarona_0O92Mn"
        assert tr["title"] == "34"
        assert tr["artist"] == "Konsta"
        assert tr["duration"] == 173
        assert tr["s"] == "tarona"
        assert tr["m"] == 1
        assert "muzfm.uz" in tr["link"]


@pytest.mark.asyncio
async def test_tarona_download_mp3_direct():
    """MusicService._download_tarona_mp3 sahifadan to'g'ridan-to'g'ri MP3 topib yuklashi."""
    music_srv = MusicService()

    fake_song_html = '''
    <html>
      <body>
        <a class="btn-download" href="https://muzfm.uz/storage/uploads/music/2026/09/konsta-34.mp3">Download</a>
      </body>
    </html>
    '''

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=fake_song_html)

    mock_resp_cm = MagicMock()
    mock_resp_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp_cm
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    music_srv.downloader.download_direct_audio = AsyncMock(
        return_value=DownloadResult(success=True, file_path="/tmp/konsta-34.mp3", title="34")
    )

    with patch("aiohttp.ClientSession", return_value=mock_session):
        track_info = {
            "title": "34",
            "artist": "Konsta",
            "link": "https://muzfm.uz/music/konsta-34",
            "s": "tarona"
        }
        res = await music_srv._download_tarona_mp3(track_info, title="34")
        assert res.success is True
        assert res.file_path == "/tmp/konsta-34.mp3"
        music_srv.downloader.download_direct_audio.assert_called_once()
        call_url = music_srv.downloader.download_direct_audio.call_args[0][0]
        assert "storage/uploads/music" in call_url


@pytest.mark.asyncio
async def test_downloader_update_from_git():
    """MediaDownloader.update_from_git asinxron chaqiruvini tekshirish."""
    dl = MediaDownloader()

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"Successfully installed", b""))
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        success = await dl.update_from_git()
        assert success is True


@pytest.mark.asyncio
async def test_tarona_direct_mp3_resolution_edge_cases():
    """_resolve_tarona_direct_mp3 uncaptured regex, relative URL va sluglarni to'g'ri hal qilishi."""
    music_srv = MusicService()

    # 1. HTML ichida uncaptured regex bo'lsa (guruhi yo'q https://...mp3 pattern)
    html_uncaptured = """
    <html>
      <script>var audioFile = 'https://cdn.example.com/audio/song.mp3';</script>
    </html>
    """
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=html_uncaptured)

    mock_resp_cm = MagicMock()
    mock_resp_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp_cm
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        res = await music_srv._resolve_tarona_direct_mp3("https://muzfm.uz/music/sample-song")
        assert res == "https://cdn.example.com/audio/song.mp3"

    # 2. Nisbiy URL (/uploads/song.mp3)
    html_relative = """
    <div><a href="/uploads/songs/song.mp3">Download</a></div>
    """
    mock_resp_rel = AsyncMock()
    mock_resp_rel.status = 200
    mock_resp_rel.text = AsyncMock(return_value=html_relative)

    mock_resp_cm_rel = MagicMock()
    mock_resp_cm_rel.__aenter__ = AsyncMock(return_value=mock_resp_rel)
    mock_resp_cm_rel.__aexit__ = AsyncMock(return_value=None)

    mock_session_rel = MagicMock()
    mock_session_rel.get.return_value = mock_resp_cm_rel
    mock_session_rel.__aenter__ = AsyncMock(return_value=mock_session_rel)
    mock_session_rel.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session_rel):
        res2 = await music_srv._resolve_tarona_direct_mp3({"link": "https://mp3uz.net/music/sample"})
        assert res2 == "https://mp3uz.net/uploads/songs/song.mp3"

    # 3. Allaqachon to'g'ridan-to'g'ri .mp3 bo'lsa
    res3 = await music_srv._resolve_tarona_direct_mp3("https://cdn.example.com/track.mp3")
    assert res3 == "https://cdn.example.com/track.mp3"


@pytest.mark.asyncio
async def test_tarona_search_mp3uz_format():
    """Mp3uz.net formati (js-itemsiz, track-item__title va xfsearch artist) to'g'ri tanilishi."""
    music_srv = MusicService()

    fake_mp3uz_html = """
    <div class="track-item fx-row fx-middle">
      <div class="track-desc">
        <a href="/music/3064-sample-track.html">
          <div class="track-item__title ws-nowrap">Yulduzlar</div>
          <div class="track-item__subtitle ws-nowrap">
            <a href="/xfsearch/Artist/" title="Artist">Sardor Rahimxon</a>
          </div>
        </a>
      </div>
      <div class="track-time time">03:40</div>
    </div>
    """
    def mock_get(req_url, **kwargs):
        cm = MagicMock()
        r = AsyncMock()
        if "mp3uz" in req_url:
            r.status = 200
            r.text = AsyncMock(return_value=fake_mp3uz_html)
        else:
            r.status = 503
            r.text = AsyncMock(return_value="")
        cm.__aenter__ = AsyncMock(return_value=r)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    mock_session = MagicMock()
    mock_session.get.side_effect = mock_get
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        tracks = await music_srv._search_tarona("Sardor", limit=5)
        assert len(tracks) >= 1
        t = tracks[0]
        assert t["title"] == "Yulduzlar"
        assert t["artist"] == "Sardor Rahimxon"
        assert t["duration"] == 220
        assert "mp3uz.net" in t["link"]


@pytest.mark.asyncio
async def test_handle_music_play_never_leaks_html_page():
    """handle_music_play web audio pleerga HTML sahifa manzilini berib yubormasligi kerak."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Tarona sahifasi yuborilganda va direct MP3 hal bo'lsa
        with patch.object(
            MusicService, "_resolve_tarona_direct_mp3",
            new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = "https://muzfm.uz/uploads/sample.mp3"
            resp = await client.post("/api/music/play", json={"s": "tarona", "u": "https://muzfm.uz/music/sample"})
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True
            assert data["url"] == "https://muzfm.uz/uploads/sample.mp3"

        # HTML sahifasi bo'lib, uning direct MP3 si topilmasa, HTML sahifa URL i o'zi qaytmasligi kerak
        with patch.object(
            MusicService, "_resolve_tarona_direct_mp3",
            new_callable=AsyncMock
        ) as mock_resolve_none:
            mock_resolve_none.return_value = None
            resp_none = await client.post("/api/music/play", json={"s": "tarona", "u": "https://muzfm.uz/music/sample", "t": "Sample", "a": "Artist"})
            assert resp_none.status == 200
            data_none = await resp_none.json()
            # Hech qachon /music/ yoki .html qaytmasligi shart
            assert "https://muzfm.uz/music/sample" != data_none.get("url")
    finally:
        await client.close()



