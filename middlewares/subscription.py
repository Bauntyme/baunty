"""
Majburiy kanal obunasini tekshirish middleware
"""
import logging
import time
from typing import Callable, Dict, Any, Awaitable, List
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import config
from database.session import get_session
from database import crud
from keyboards.inline import subscription_keyboard

logger = logging.getLogger(__name__)

ALLOWED_STATUSES = {"creator", "administrator", "member", "restricted"}

# Tezkor xotira keshi (Telegram API va DB ga ortiqcha so'rovlarni oldini olish)
_CHANNELS_CACHE: Dict[str, Any] = {"channels": [], "ts": 0.0}
_USER_SUB_CACHE: Dict[int, tuple[float, bool]] = {}


def clear_subscription_cache(user_id: int | None = None) -> None:
    """Homiy kanallar yoki foydalanuvchi keshi tozalanadi."""
    global _CHANNELS_CACHE
    if user_id is not None:
        _USER_SUB_CACHE.pop(user_id, None)
    else:
        _CHANNELS_CACHE["ts"] = 0.0
        _USER_SUB_CACHE.clear()


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
                # Foydalanuvchi o'zi "Tekshirish"ni bosganda uning keshini yangilaymiz
                _USER_SUB_CACHE.pop(user.id, None)
                return await handler(event, data)

        now = time.monotonic()
        # Foydalanuvchi yaqinda (oxirgi 60 soniyada) muvaffaqiyatli tekshirilgan bo'lsa darhol o'tkazish
        if user.id in _USER_SUB_CACHE:
            cached_ts, is_sub = _USER_SUB_CACHE[user.id]
            if now - cached_ts < 60.0 and is_sub:
                return await handler(event, data)

        # Bazadagi faol homiy kanallarni olish (30s TTL kesh bilan)
        if now - _CHANNELS_CACHE["ts"] < 30.0:
            channels = _CHANNELS_CACHE["channels"]
        else:
            async with get_session() as session:
                channels = await crud.get_active_sponsor_channels(session)
            _CHANNELS_CACHE["channels"] = channels
            _CHANNELS_CACHE["ts"] = now

        if not channels:
            _USER_SUB_CACHE[user.id] = (now, True)
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

        if not unsubscribed:
            _USER_SUB_CACHE[user.id] = (now, True)
            return await handler(event, data)

        _USER_SUB_CACHE[user.id] = (now, False)

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
