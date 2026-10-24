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
from handlers.docs import router as docs_router
from handlers.round_video import router as round_video_router
from handlers.anon_questions import router as anon_questions_router
from handlers.referral import router as referral_router
from handlers.groups import router as groups_router
from handlers.feedback import router as feedback_router
from handlers.books import router as books_router
from handlers.mafia import router as mafia_router
from handlers.rasxod import router as rasxod_router
from handlers.kaloriya import router as kaloriya_router
from handlers.tvroom import router as tvroom_router
from handlers.language import router as language_router


_root_router: Router = None


def setup_routers() -> Router:
    """Barcha routerlarni birlashtiruvchi bosh router."""
    global _root_router
    if _root_router is not None:
        return _root_router

    _root_router = Router(name="root_router")

    # Tartib: admin -> language -> start -> downloader -> movies -> music -> books -> mafia -> rasxod -> kaloriya -> story -> docs -> round_video -> anon -> referral -> groups -> feedback
    _root_router.include_router(admin_router)
    _root_router.include_router(language_router)
    _root_router.include_router(start_router)
    _root_router.include_router(downloader_router)
    _root_router.include_router(movies_router)
    _root_router.include_router(music_router)
    _root_router.include_router(books_router)
    _root_router.include_router(mafia_router)
    _root_router.include_router(rasxod_router)
    _root_router.include_router(kaloriya_router)
    _root_router.include_router(tvroom_router)
    _root_router.include_router(story_router)
    _root_router.include_router(docs_router)
    _root_router.include_router(round_video_router)
    _root_router.include_router(anon_questions_router)
    _root_router.include_router(referral_router)
    _root_router.include_router(groups_router)
    _root_router.include_router(feedback_router)

    return _root_router


__all__ = [
    "setup_routers",
    "start_router",
    "downloader_router",
    "movies_router",
    "music_router",
    "books_router",
    "mafia_router",
    "rasxod_router",
    "kaloriya_router",
    "tvroom_router",
    "story_router",
    "admin_router",
    "docs_router",
    "round_video_router",
    "anon_questions_router",
    "referral_router",
    "groups_router",
    "feedback_router",
]

