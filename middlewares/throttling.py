"""
Anti-flood va spamdan himoya middleware (Throttling)
"""
import time
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from config import config

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """Xabarlar oralig'ini nazorat qiluvchi anti-flood middleware."""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.user_timestamps: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user = event.from_user
        if not user or config.is_admin(user.id):
            return await handler(event, data)

        now = time.monotonic()
        last_time = self.user_timestamps.get(user.id, 0.0)

        # Eski yozuvlarni tozalash (xotira tejash uchun)
        if len(self.user_timestamps) > 10000:
            self.user_timestamps = {
                u: t for u, t in self.user_timestamps.items() if now - t < 10.0
            }

        if now - last_time < self.rate_limit:
            # Juda tez xabar yuborilgan
            logger.debug(f"User {user.id} spam chekloviga tushdi")
            return  # Xabarni e'tiborsiz qoldirish

        self.user_timestamps[user.id] = now
        return await handler(event, data)
