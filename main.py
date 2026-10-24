"""
Bauntyfilms_bot - Asosiy ishga tushirish fayli
Aiogram 3.x + Python 3.12
"""
import sys
import asyncio
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import config
from database.session import init_db, close_db
from handlers import setup_routers
from middlewares import SubscriptionMiddleware, ThrottlingMiddleware, BotSecurityMiddleware
from utils.notifier import notify_admins_on_startup, notify_admins_on_shutdown


def setup_logging() -> None:
    """Logging sozlamalari."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "bot.log", encoding="utf-8")
        ]
    )


async def set_default_commands(bot: Bot) -> None:
    """Bot menyusi komandalarini o'rnatish."""
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="til", description="Tilni tanlash / Choose language"),
        BotCommand(command="mafia", description="Mafia onlayn o'yini"),
        BotCommand(command="help", description="Yordam va qo'llanma"),
        BotCommand(command="admin", description="Admin paneli"),
        BotCommand(command="stats", description="Statistika (admin)"),
        BotCommand(command="profilaktika", description="Profilaktika rejimi (admin)"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def set_webapp_menu_button(bot: Bot) -> None:
    """Pastki '📱 Ilova' menyu tugmasini (MenuButtonWebApp) sozlash."""
    app_url = config.webapp_url_resolved
    logger = logging.getLogger("main")
    try:
        if app_url and app_url.startswith("https://"):
            from aiogram.types import MenuButtonWebApp, WebAppInfo
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📱 Ilova",
                    web_app=WebAppInfo(url=app_url)
                )
            )
            logger.info(f"MenuButtonWebApp muvaffaqiyatli o'rnatildi: {app_url}")
        else:
            from aiogram.types import MenuButtonDefault
            await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
            if app_url:
                logger.warning(
                    f"MenuButtonWebApp faqat HTTPS havolalarni qabul qiladi ('{app_url}'). "
                    "Render.com da RENDER_EXTERNAL_URL avtomatik olinadi, yoki .env da WEBAPP_URL=https://... sozlang. "
                    "Default menyu tugmasi o'rnatildi."
                )
            else:
                logger.info("WEBAPP_URL sozlanmagan. Default menyu tugmasi o'rnatildi.")
    except Exception as e:
        logger.warning(f"MenuButtonWebApp sozlashda xatolik: {e}")


async def main() -> None:
    """Bot va Mini App web serverini parallel ishga tushirish funksiyasi."""
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Bauntyfilms_bot va Mini App ishga tushirilmoqda...")

    # Bot ob'ekti
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Dispatcher
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewarelarni ulash
    dp.message.middleware(BotSecurityMiddleware())
    dp.callback_query.middleware(BotSecurityMiddleware())
    dp.message.middleware(ThrottlingMiddleware(rate_limit=config.RATE_LIMIT_SECONDS))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=config.RATE_LIMIT_SECONDS))
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Routerlarni ulash
    dp.include_router(setup_routers())

    # Mini App aiohttp web serverini ishga tushirish (Render.com portlari bilan)
    from aiohttp import web
    from services.web_server import create_web_app, set_bot_instance
    set_bot_instance(bot)
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, host=config.HOST, port=config.PORT)
    await site.start()
    logger.info(f"Mini App va Web API serveri ishga tushdi: http://{config.HOST}:{config.PORT}")
    logger.info(f"Render health check manzili: http://{config.HOST}:{config.PORT}/health")

    # Startup va shutdown hodisalari
    async def on_startup():
        logger.info("Baza va xizmatlar ishga tushirilmoqda...")
        await init_db()
        await set_default_commands(bot)
        await set_webapp_menu_button(bot)
        await notify_admins_on_startup(bot)
        from services.movie_service import start_periodic_catalog_sync, start_background_movie_preloader
        start_periodic_catalog_sync()
        start_background_movie_preloader()
        from services.downloader import media_downloader
        asyncio.create_task(media_downloader.update_from_git())
        logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{config.BOT_USERNAME}")

    async def on_shutdown():
        logger.info("Bot va web server to'xtatilmoqda...")
        from services.movie_service import stop_periodic_catalog_sync, stop_background_movie_preloader
        stop_periodic_catalog_sync()
        stop_background_movie_preloader()
        await notify_admins_on_shutdown(bot)
        await runner.cleanup()
        await close_db()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Pollingni boshlash (eskirgan yangilanishlarni o'tkazib yuborish)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()
        await bot.session.close()



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot qo'lda to'xtatildi.")
