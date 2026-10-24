"""
Bot Xavfsizlik Middleware (Bot Security Middleware) - Bauntys
Anti-flood, WAF tahlil, xavfli buyruqlar filtratsiyasi va bloklangan foydalanuvchilarni to'xtatish.
100% Bauntys brendi.
"""
import time
import logging
from collections import defaultdict, deque
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import config
from database.session import get_session
from database import crud

logger = logging.getLogger("bot.security")

# Xavfli WAF payloadlar va exploit belgilari
MALICIOUS_PATTERNS = (
    "/bin/sh",
    "/bin/bash",
    ";cat /etc/passwd",
    "wget http",
    "curl http",
    "<script>",
    "javascript:",
    "UNION SELECT",
    "DROP TABLE",
    "../",
    "..\\",
    "0x90",
)


class BotSecurityMiddleware(BaseMiddleware):
    """Telegram bot so'rovlarini himoyalovchi xavfsizlik middleware."""

    def __init__(self, window_seconds: float = 3.0, max_requests: int = 5):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.user_requests: Dict[int, deque] = defaultdict(deque)
        self._banned_cache: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        user_id = user.id
        is_admin = config.is_admin(user_id)

        # 1. Adminlar barcha cheklovlardan ozod
        if is_admin:
            return await handler(event, data)

        # 2. Bloklangan foydalanuvchilarni tekshirish (10 soniyalik kesh bilan)
        now = time.monotonic()
        if user_id in self._banned_cache:
            if now - self._banned_cache[user_id] < 15.0:
                if isinstance(event, Message):
                    await event.answer("⛔ <b>Kechirasiz, siz botdan foydalanish uchun bloklangansiz.</b>", parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⛔ Siz bloklangansiz!", show_alert=True)
                return

        try:
            async with get_session() as session:
                is_banned = await crud.is_user_banned(session, user_id)
                if is_banned:
                    self._banned_cache[user_id] = now
                    if isinstance(event, Message):
                        await event.answer("⛔ <b>Kechirasiz, siz botdan foydalanish uchun bloklangansiz.</b>", parse_mode="HTML")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⛔ Siz bloklangansiz!", show_alert=True)
                    return
                elif user_id in self._banned_cache:
                    del self._banned_cache[user_id]
        except Exception as e:
            logger.debug(f"Ban check xatolik: {e}")

        # 3. Anti-Flood sliding window cheklovi
        user_queue = self.user_requests[user_id]
        while user_queue and (now - user_queue[0]) > self.window_seconds:
            user_queue.popleft()

        user_queue.append(now)
        if len(user_queue) > self.max_requests:
            logger.warning(f"Anti-flood ogohlantirish: User {user_id} tez-tez so'rov yubordi ({len(user_queue)}/{self.window_seconds}s)")
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("⚠️ Juda ko'p so'rov! Biroz kuting.", show_alert=False)
                except Exception:
                    pass
            return

        # 4. Input Sanitization & Threat WAF tekshiruvi
        if isinstance(event, Message) and event.text:
            text = event.text
            # Null-byte tozalash
            if "\x00" in text:
                logger.warning(f"Null-byte aniqlandi User {user_id}")
                return

            text_upper = text.upper()
            for pattern in MALICIOUS_PATTERNS:
                if pattern.upper() in text_upper:
                    logger.warning(f"WAF: Xavfli xabar aniqlandi User {user_id}: {text[:50]}")
                    await event.reply("⚠️ <b>Xavfsizlik tizimi:</b> Noto'g'ri so'rov aniqlandi.", parse_mode="HTML")
                    return

        # 5. Global profilaktika tekshiruvi (faqat non-adminlar uchun)
        from services.maintenance_service import maintenance_service
        if maintenance_service.is_global_maintenance():
            allowed = False
            if isinstance(event, Message):
                text = (event.text or "").strip()
                if text.startswith("/start"):
                    allowed = True
                elif text.startswith(("/music", "/musiqa", "/song", "/mp3")):
                    allowed = True
                elif text.startswith(("/til", "/lang", "/language")):
                    allowed = True
                elif any(text.startswith(p) for p in ("http://", "https://", "www.")):
                    allowed = True
                elif any(x in text for x in [
                    "🎵", "⭕️", "⭕", "Dumaloq video", "Думалоқ видео", "Круглое видео",
                    "Qo'shiq topish", "Қўшиқ топиш", "Поиск музыки",
                    "Media yuklash", "Медиа юклаш", "Скачать медиа",
                    "🌐 Til", "🌐 Тил", "🌐 Язык"
                ]):
                    allowed = True
                elif getattr(event, "video", None) or getattr(event, "document", None):
                    allowed = True
            elif isinstance(event, CallbackQuery):
                cdata = event.data or ""
                if cdata.startswith(("music:", "song:", "set_lang:", "check_subscription")):
                    allowed = True

            if not allowed:
                from keyboards.default import maintenance_menu_keyboard
                m_msg = maintenance_service.get_global_message()
                maint_text = (
                    f"<b>{m_msg}</b>\n\n"
                    "Botda texnik yangilanish olib borilayotgani sababli ayrim xizmatlar vaqtincha to'xtatilgan.\n\n"
                    "⚡ <b>Lekin hozirda quyidagi bo'limlar to'liq va uzluksiz ishlamoqda:</b>\n"
                    "• 🎵 <b>Qo'shiq topish</b> (Istalgan musiqa va ijrochini topish)\n"
                    "• ⭕️ <b>Dumaloq video</b> (1 soniyada video xabar tayyorlash)\n"
                    "• 📥 <b>Media yuklash</b> (Instagram, TikTok, YouTube va b.)\n\n"
                    "Quyidagi tugmalardan birini tanlab foydalanishingiz mumkin:"
                )
                if isinstance(event, Message):
                    user_lang = "uz"
                    try:
                        async with get_session() as session:
                            user_lang = await crud.get_user_language(session, user_id)
                    except Exception:
                        pass
                    await event.answer(maint_text, parse_mode="HTML", reply_markup=maintenance_menu_keyboard(is_admin=False, lang=user_lang))
                elif isinstance(event, CallbackQuery):
                    try:
                        await event.answer(f"⚠️ {m_msg}", show_alert=True)
                    except Exception:
                        pass
                return

        # Eski ma'lumotlarni tozalash
        if len(self.user_requests) > 5000:
            self.user_requests = defaultdict(
                deque,
                {uid: q for uid, q in self.user_requests.items() if q and (now - q[-1]) < 30.0}
            )

        return await handler(event, data)
