"""
Integratsiya testlari: Aiogram Dispatcher, Routerlar va Tashqi API
"""
import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import setup_routers
from middlewares import SubscriptionMiddleware, ThrottlingMiddleware
from services.music_service import music_service


def test_dispatcher_routers_and_middlewares():
    """Barcha routerlar va middlewarelar to'g'ri bog'lanishini tekshirish."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.0))
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    root_router = setup_routers()
    dp.include_router(root_router)

    # Barcha 12 ta subrouter mavjudligi
    subrouter_names = [r.name for r in root_router.sub_routers]
    assert "admin_router" in subrouter_names
    assert "start_router" in subrouter_names
    assert "downloader_router" in subrouter_names
    assert "movies_router" in subrouter_names
    assert "music_router" in subrouter_names
    assert "story_router" in subrouter_names
    assert "docs_router" in subrouter_names
    assert "round_video_router" in subrouter_names
    assert "anon_questions_router" in subrouter_names
    assert "referral_router" in subrouter_names
    assert "groups_router" in subrouter_names
    assert "feedback_router" in subrouter_names


@pytest.mark.asyncio
async def test_deezer_api_music_search():
    """Deezer ochiq musiqa API si ishlayotganligini va to'g'ri json formatini qaytarishini tekshirish."""
    tracks = await music_service.search_tracks("Konsta", limit=3)
    # Agar internet mavjud bo'lsa natijalar keladi
    assert isinstance(tracks, list)
    if tracks:
        first = tracks[0]
        assert "title" in first
        assert "artist" in first


@pytest.mark.asyncio
async def test_audio_recognition_parsing(monkeypatch):
    """Shazam audio recognition natijasi to'g'ri parse qilinishini tekshirish."""
    mock_out = {
        "track": {
            "key": "40333609",
            "title": "Never Gonna Give You Up",
            "subtitle": "Rick Astley",
            "genres": {"primary": "Pop"},
            "images": {"coverart": "https://example.com/cover.jpg"},
            "url": "https://www.shazam.com/track/40333609"
        }
    }

    class MockShazam:
        async def recognize(self, file_path):
            return mock_out

    import sys, types
    mock_mod = types.ModuleType("shazamio")
    mock_mod.Shazam = MockShazam
    monkeypatch.setitem(sys.modules, "shazamio", mock_mod)

    res = await music_service.recognize_audio("fake_path.ogg")
    assert res is not None
    assert res["title"] == "Never Gonna Give You Up"
    assert res["artist"] == "Rick Astley"
    assert res["genre"] == "Pop"
    assert res["cover"] == "https://example.com/cover.jpg"


@pytest.mark.asyncio
async def test_audio_recognition_none_when_no_match(monkeypatch):
    """Shazam qo'shiqni topolmaganda None qaytarishini tekshirish."""
    class MockShazamEmpty:
        async def recognize(self, file_path):
            return {}

    import sys, types
    mock_mod = types.ModuleType("shazamio")
    mock_mod.Shazam = MockShazamEmpty
    monkeypatch.setitem(sys.modules, "shazamio", mock_mod)

    res = await music_service.recognize_audio("ambient_noise.ogg")
    assert res is None


@pytest.mark.asyncio
async def test_fsm_numeric_code_isolation():
    """FSM holatida (masalan musiqa qidiruv) raqam yoki URL yozilsa kino yoki downloader ushlamasligini tekshirish."""
    from aiogram.filters.state import StateFilter
    from handlers.movies import router as movies_router
    from handlers.downloader import router as downloader_router

    # process_numeric_movie_code handlersi StateFilter(None) bilan himoyalanganligini tekshirish
    h_movie = [h for h in movies_router.message.handlers if h.callback.__name__ == "process_numeric_movie_code"][0]
    movie_state_filters = [f.callback for f in h_movie.filters if isinstance(f.callback, StateFilter)]
    assert len(movie_state_filters) == 1
    assert movie_state_filters[0].states == (None,)

    # process_media_url handlersi StateFilter(None) bilan himoyalanganligini tekshirish
    h_dl = [h for h in downloader_router.message.handlers if h.callback.__name__ == "process_media_url"][0]
    dl_state_filters = [f.callback for f in h_dl.filters if isinstance(f.callback, StateFilter)]
    assert len(dl_state_filters) == 1
    assert dl_state_filters[0].states == (None,)



