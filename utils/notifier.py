"""
Adminlarga xabar yetkazish vositalari
"""
import logging
from aiogram import Bot
from config import config

logger = logging.getLogger(__name__)


async def notify_admins_on_startup(bot: Bot) -> None:
    """Bot ishga tushganda adminlarga xabar yuborish."""
    from services.bot_identity import resolve_bot_username
    bot_name = await resolve_bot_username(bot)
    message = (
        f"🚀 <b>@{bot_name} muvaffaqiyatli ishga tushdi!</b>\n\n"
        f"🤖 Bot: @{bot_name}\n"
        f"🍿 Kanal: {config.CHANNEL_USERNAME}\n"
        "✅ Barcha xizmatlar tayyor va faol."
    )
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Adminga ({admin_id}) startup xabari yuborilmadi: {e}")


async def notify_admins_on_shutdown(bot: Bot) -> None:
    """Bot to'xtaganda adminlarga xabar yuborish."""
    from services.bot_identity import get_bot_username
    bot_name = get_bot_username()
    message = f"🛑 <b>@{bot_name} to'xtatildi!</b>"
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Adminga ({admin_id}) shutdown xabari yuborilmadi: {e}")
