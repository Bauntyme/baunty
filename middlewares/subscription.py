"""
Majburiy kanal obunasini tekshirish middleware
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import config
from database.session import get_session
from database import crud
from keyboards.inline import subscription_keyboard

logger = logging.getLogger(__name__)

ALLOWED_STATUSES = {"creator", "administrator", "member", "restricted"}


class SubscriptionMiddleware(BaseMiddleware):
    """Foydalanuvchi majburiy kanallarga a'zo ekanligini tekshiruvchi middleware."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Adminlar obunani tekshirishdan ozod
        if config.is_admin(user.id):
            return await handler(event, data)

        bot = data["bot"]

        # /start komandasi va obunani tekshirish callback_data uchun ruxsat berish
        if isinstance(event, Message) and event.text:
            text = event.text.strip()
            # /start komandasi parametr bilan yoki parametrsiz
            if text.startswith("/start"):
                return await handler(event, data)

        if isinstance(event, CallbackQuery):
            if event.data == "check_subscription":
                return await handler(event, data)

        # Bazadagi faol homiy kanallarni olish
        async with get_session() as session:
            channels = await crud.get_active_sponsor_channels(session)

        if not channels:
            return await handler(event, data)

        unsubscribed = []
        for ch in channels:
            try:
                member = await bot.get_chat_member(chat_id=ch.channel_id, user_id=user.id)
                if member.status not in ALLOWED_STATUSES:
                    unsubscribed.append(ch)
            except Exception as e:
                logger.warning(f"Kanal obunasini tekshirishda xatolik ({ch.channel_id}): {e}")
                # Agar bot kanalda admin bo'lmasa yoki kanal topilmasa, foydalanuvchini to'xtatmaymiz

        if unsubscribed:
            alert_text = (
                "⚠️ <b>Botdan foydalanish uchun quyidagi homiy kanallarga a'zo bo'ling!</b>\n\n"
                "A'zo bo'lganingizdan so'ng, pastdagi <b>«✅ Obunani tekshirish»</b> tugmasini bosing."
            )
            markup = subscription_keyboard(unsubscribed)

            if isinstance(event, Message):
                await event.answer(alert_text, parse_mode="HTML", reply_markup=markup)
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
                try:
                    await event.message.edit_text(alert_text, parse_mode="HTML", reply_markup=markup)
                except Exception:
                    pass
            return

        return await handler(event, data)
