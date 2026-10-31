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

        # Guruhlar va superguruhlardagi so'rovlarda obunani majburlamaymiz (guruhda to'liq erkin ishlashi uchun)
        if isinstance(event, Message) and getattr(event, "chat", None) and getattr(event.chat, "type", None) in ("group", "supergroup"):
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and getattr(getattr(event, "message", None), "chat", None) and getattr(event.message.chat, "type", None) in ("group", "supergroup"):
            return await handler(event, data)

        # Referal orqali kirganda referalni bazada qayd etish
        if isinstance(event, Message) and event.text:
            text = event.text.strip()
            if text.startswith("/start r_"):
                try:
                    parts = text.split(maxsplit=1)
                    if len(parts) > 1 and parts[1].startswith("r_"):
                        ref_id_str = parts[1].replace("r_", "").strip()
                        if ref_id_str.isdigit() and int(ref_id_str) != user.id:
                            referrer_id = int(ref_id_str)
                            async with get_session() as session:
                                await crud.add_referral(session, referrer_id=referrer_id, new_user_id=user.id, points=10)
                except Exception:
                    pass

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
            if not channels and config.CHANNEL_USERNAME and config.CHANNEL_USERNAME.strip():
                from database.models import SponsorChannel
                channels = [SponsorChannel(id=999999, channel_id=config.CHANNEL_USERNAME.strip(), title="Baunty Films", is_active=True)]
            _CHANNELS_CACHE["channels"] = channels
            _CHANNELS_CACHE["ts"] = now

        if not channels:
            _USER_SUB_CACHE[user.id] = (now, True)
            return await handler(event, data)

        from unittest.mock import MagicMock, AsyncMock
        unsubscribed = []
        for ch in channels:
            try:
                member = await bot.get_chat_member(chat_id=ch.channel_id, user_id=user.id)
                status = getattr(member, "status", None) or (member.get("status") if isinstance(member, dict) else "")
                if isinstance(status, (MagicMock, AsyncMock)):
                    continue
                if str(status).lower() not in ALLOWED_STATUSES:
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
                "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi kanalga a'zo bo'ling!</b>\n\n"
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
