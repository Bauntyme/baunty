"""
Handlers package
"""
from aiogram import Router
from handlers.start import router as start_router
from handlers.downloader import router as downloader_router
from handlers.movies import router as movies_router
from handlers.music import router as music_router
from handlers.story import router as story_router
from handlers.admin import router as admin_router


def setup_routers() -> Router:
    """Barcha routerlarni birlashtiruvchi bosh router."""
    root_router = Router(name="root_router")

    # Tartib: admin -> start -> downloader -> movies -> music -> story
    root_router.include_router(admin_router)
    root_router.include_router(start_router)
    root_router.include_router(downloader_router)
    root_router.include_router(movies_router)
    root_router.include_router(music_router)
    root_router.include_router(story_router)

    return root_router


__all__ = [
    "setup_routers",
    "start_router",
    "downloader_router",
    "movies_router",
    "music_router",
    "story_router",
    "admin_router",
]
