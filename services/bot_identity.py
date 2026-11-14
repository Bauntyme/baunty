"""
Botning Telegram'dagi haqiqiy username'ini sinxronlash va barcha havolalar uchun yagona manba.
Agar .env yoki hosting (Render) muhitida BOT_USERNAME eskirgan/xato bo'lsa ham
(masalan: Bauntycinema_bot), haqiqiy bot.get_me().username ni aniqlab config.BOT_USERNAME ni
xotirada avtomatik yangilaydi va barcha share/deep-link URL larini xavfsiz kodlaydi.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

_VALID_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,63}$")
_KNOWN_STALE_USERNAMES = {
    "bauntycinema_bot",
    "bauntyfilmsbot",
    "zakirovsfilms_bot",
    "zakirovs_bot",
}
_DEFAULT_BOT_USERNAME = "BauntyCinemabot"
_LIVE_BOT_USERNAME: Optional[str] = None


def _is_mock_obj(obj: object) -> bool:
    if obj is None:
        return False
    mod = getattr(type(obj), "__module__", "") or ""
    return mod.startswith("unittest.mock")


def is_valid_bot_username(raw: object) -> bool:
    """Faqat haqiqiy str Telegram username bo'lsa True qaytaradi."""
    if not isinstance(raw, str) or _is_mock_obj(raw):
        return False
    clean = raw.strip().lstrip("@")
    return bool(clean and _VALID_USERNAME_RE.match(clean))


def set_live_bot_username(raw: object) -> Optional[str]:
    """Aniqlangan jonli bot username'ini saqlaydi va config.BOT_USERNAME ni yangilaydi."""
    global _LIVE_BOT_USERNAME
    if not is_valid_bot_username(raw):
        return None
    clean = str(raw).strip().lstrip("@")
    prev = (getattr(config, "BOT_USERNAME", "") or "").strip().lstrip("@")
    _LIVE_BOT_USERNAME = clean
    if prev != clean:
        try:
            config.BOT_USERNAME = clean
            logger.info("config.BOT_USERNAME jonli qiymatga yangilandi: @%s -> @%s", prev or "(bo'sh)", clean)
        except Exception:
            pass
    return clean


def get_bot_username() -> str:
    """Sinxron kodlar uchun eng ishonchli bot username'ini '@' siz qaytaradi."""
    if _LIVE_BOT_USERNAME:
        return _LIVE_BOT_USERNAME
    raw = (getattr(config, "BOT_USERNAME", "") or "").strip().lstrip("@")
    if is_valid_bot_username(raw) and raw.lower() not in _KNOWN_STALE_USERNAMES:
        return raw
    return _DEFAULT_BOT_USERNAME


def reset_live_bot_username_cache() -> None:
    """Faqat testlar uchun keshni tozalash."""
    global _LIVE_BOT_USERNAME
    _LIVE_BOT_USERNAME = None


async def resolve_bot_username(bot: object = None) -> str:
    """Asinxron handlerlar uchun Telegram API/cache dan haqiqiy bot username'ini oladi."""
    if _LIVE_BOT_USERNAME:
        return _LIVE_BOT_USERNAME

    if bot is not None and not _is_mock_obj(bot):
        cached_me = getattr(bot, "_me", None)
        if cached_me is not None and not _is_mock_obj(cached_me):
            synced = set_live_bot_username(getattr(cached_me, "username", None))
            if synced:
                return synced

        me_callable = getattr(bot, "me", None) or getattr(bot, "get_me", None)
        if callable(me_callable):
            try:
                me_obj = await me_callable()
                if me_obj is not None and not _is_mock_obj(me_obj):
                    synced = set_live_bot_username(getattr(me_obj, "username", None))
                    if synced:
                        return synced
            except Exception as err:
                logger.debug("Bot username'ini Telegram API dan aniqlashda xatolik: %s", err)

    return get_bot_username()


async def sync_bot_username(bot: object = None) -> str:
    """Bot ishga tushganda Telegram get_me() orqali username'ni majburiy sinxronlaydi."""
    if bot is not None and not _is_mock_obj(bot):
        get_me_fn = getattr(bot, "get_me", None) or getattr(bot, "me", None)
        if callable(get_me_fn):
            try:
                me_obj = await get_me_fn()
                if me_obj is not None and not _is_mock_obj(me_obj):
                    synced = set_live_bot_username(getattr(me_obj, "username", None))
                    if synced:
                        return synced
            except Exception as err:
                logger.warning("Bot startup get_me() sinxronlash xatoligi: %s", err)
    return get_bot_username()


def build_telegram_share_url(target_url: str, share_text: str = "") -> str:
    """Telegram share/url havolasini to'liq URL-kodlangan xavfsiz shaklda yaratadi."""
    encoded_url = urllib.parse.quote(str(target_url or "").strip(), safe="")
    if share_text:
        encoded_text = urllib.parse.quote(str(share_text), safe="")
        return f"https://t.me/share/url?url={encoded_url}&text={encoded_text}"
    return f"https://t.me/share/url?url={encoded_url}"
