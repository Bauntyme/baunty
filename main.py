"""
Zakirovsfilms_bot - Asosiy ishga tushirish fayli
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
from middlewares import SubscriptionMiddleware, ThrottlingMiddleware
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
        BotCommand(command="help", description="Yordam va qo'llanma"),
        BotCommand(command="admin", description="Admin paneli (adminlar uchun)"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def main() -> None:
    """Botni to'liq ishga tushirish funksiyasi."""
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Zakirovsfilms_bot ishga tushirilmoqda...")

    # Bot ob'ekti
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Dispatcher
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewarelarni ulash
    dp.message.middleware(ThrottlingMiddleware(rate_limit=config.RATE_LIMIT_SECONDS))
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Routerlarni ulash
    dp.include_router(setup_routers())

    # Startup va shutdown hodisalari
    async def on_startup():
        logger.info("Baza va xizmatlar ishga tushirilmoqda...")
        await init_db()
        await set_default_commands(bot)
        await notify_admins_on_startup(bot)
        logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{config.BOT_USERNAME}")

    async def on_shutdown():
        logger.info("Bot to'xtatilmoqda...")
        await notify_admins_on_shutdown(bot)
        await close_db()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Pollingni boshlash (eskirgan yangilanishlarni o'tkazib yuborish)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot qo'lda to'xtatildi.")
