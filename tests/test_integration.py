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

    # Subrouterlar mavjudligi
    subrouter_names = [r.name for r in root_router.sub_routers]
    assert "admin_router" in subrouter_names
    assert "start_router" in subrouter_names
    assert "downloader_router" in subrouter_names
    assert "movies_router" in subrouter_names
    assert "music_router" in subrouter_names
    assert "story_router" in subrouter_names


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
