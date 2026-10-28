"""
Yordamchi funksiyalar va vositalar
"""
import re
import os
import time
import hashlib
import shutil
import platform
from pathlib import Path
from typing import Optional, Tuple, Dict
from config import config

# URL larni aniqlash uchun regex andozalari
INSTAGRAM_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|instagr\.am)/(?:p|reel|reels|tv|stories|share)/[a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-]+)?/?",
    re.IGNORECASE
)
TIKTOK_PATTERN = re.compile(
    r"https?://(?:www\.|vm\.|vt\.|m\.)?tiktok\.com/(?:@[a-zA-Z0-9_\.]+/video/\d+|t/[a-zA-Z0-9_\-]+|v/\d+|[a-zA-Z0-9_\-]+)/?",
    re.IGNORECASE
)
YOUTUBE_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/|v/)|youtu\.be/)[a-zA-Z0-9_\-]+",
    re.IGNORECASE
)
SNAPCHAT_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:snapchat\.com/(?:spotlight|add|t)/[a-zA-Z0-9_\-\./]+)",
    re.IGNORECASE
)
GENERAL_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE
)

# Qisqa token kesh (Telegram inline callback 64 bayt chegarasi uchun)
_URL_CACHE: Dict[str, str] = {}
_CACHE_TIMESTAMP: Dict[str, float] = {}


def cache_url(url: str) -> str:
    """URL uchun qisqa token yaratadi va keshga saqlaydi."""
    # Eski keshni tozalash (1 kundan eski)
    now = time.time()
    expired = [k for k, ts in _CACHE_TIMESTAMP.items() if now - ts > 86400]
    for k in expired:
        _URL_CACHE.pop(k, None)
        _CACHE_TIMESTAMP.pop(k, None)

    # 10 belgili hash
    token = hashlib.md5(url.encode()).hexdigest()[:10]
    _URL_CACHE[token] = url
    _CACHE_TIMESTAMP[token] = now
    return token


def get_cached_url(token: str) -> Optional[str]:
    """Token orqali asl URLni qaytaradi."""
    return _URL_CACHE.get(token)


def extract_media_url(text: str) -> Optional[str]:
    """Xabar matnidan qo'llab-quvvatlanadigan media havolasini ajratib oladi."""
    if not text:
        return None

    for pattern in [INSTAGRAM_PATTERN, TIKTOK_PATTERN, YOUTUBE_PATTERN, SNAPCHAT_PATTERN]:
        match = pattern.search(text)
        if match:
            return match.group(0)

    # Agar aniq pattern topilmasa, lekin umumiy link bo'lsa
    match = GENERAL_URL_PATTERN.search(text)
    if match:
        url = match.group(0)
        low = url.lower()
        if any(d in low for d in ["instagram.com", "tiktok.com", "youtu.be", "youtube.com", "snapchat.com", "fb.watch", "facebook.com", "pin.it", "pinterest.com"]):
            return url
    return None


def detect_platform(url: str) -> str:
    """Havola qaysi platformaga tegishli ekanligini aniqlaydi."""
    low = url.lower()
    if "instagram.com" in low or "instagr.am" in low:
        return "Instagram"
    elif "tiktok.com" in low:
        return "TikTok"
    elif "youtube.com" in low or "youtu.be" in low:
        return "YouTube"
    elif "snapchat.com" in low:
        return "Snapchat"
    elif "facebook.com" in low or "fb.watch" in low:
        return "Facebook"
    elif "pinterest.com" in low or "pin.it" in low:
        return "Pinterest"
    return "Media"


def format_movie_caption(movie) -> str:
    """Kino haqidagi to'liq ma'lumot xabari."""
    genres_str = movie.genres if movie.genres else "Noma'lum"
    year_str = str(movie.year) if movie.year else "Noma'lum"
    rating_str = f"⭐ {movie.rating}/10" if movie.rating else "⭐ Baholanmagan"

    caption = (
        f"🎬 <b>{movie.title}</b>\n\n"
        f"🔢 <b>Kino kodi:</b> <code>{movie.code}</code>\n"
        f"🎭 <b>Janri:</b> {genres_str}\n"
        f"📅 <b>Yili:</b> {year_str}\n"
        f"⭐ <b>Reyting:</b> {rating_str}\n"
        f"👁️ <b>Ko'rildi:</b> {movie.views_count} marta\n"
    )

    if movie.description:
        desc = movie.description[:400] + ("..." if len(movie.description) > 400 else "")
        caption += f"\n📝 <b>Tavsif:</b>\n<i>{desc}</i>\n"

    caption += (
        f"\n🍿 <b>Barcha sara kinolar:</b> {config.CHANNEL_USERNAME}\n"
        f"🤖 <b>Botimiz:</b> @{config.BOT_USERNAME.lstrip('@')}\n\n"
        "ℹ️ Ushbu bot qidiruv indeksi sifatida ishlaydi. Fayllar Telegram serverlarida saqlanmaydi."
    )
    return caption


def format_movie_not_found(code: str) -> str:
    """Kino topilmaganda yuboriladigan xabar."""
    return (
        f"❌ Kechirasiz, <code>{code}</code> kodli kino topilmadi!\n\n"
        f"💡 <b>Kino kodini qayerdan olish mumkin?</b>\n"
        f"🍿 Bizning rasmiy kanalimizdan barcha eng so'nggi kinolar va ularning kodlarini topishingiz mumkin:\n"
        f"👉 {config.CHANNEL_USERNAME}\n\n"
        f"Iltimos, kodni to'g'ri kiritganingizni tekshirib, qayta urinib ko'ring."
    )


def safe_remove_file(file_path: Optional[str]) -> None:
    """Faylni xatoliksiz o'chirish."""
    if not file_path:
        return
    try:
        p = Path(file_path)
        if p.is_file():
            p.unlink(missing_ok=True)
        elif p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass


def get_system_stats() -> Dict[str, str]:
    """Server tizim parametrlarini olish."""
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
    }
    try:
        total, used, free = shutil.disk_usage("/")
        info["disk_total"] = f"{total // (2**30)} GB"
        info["disk_free"] = f"{free // (2**30)} GB"
    except Exception:
        info["disk_total"] = "N/A"
        info["disk_free"] = "N/A"
    return info
