"""
InlineKeyboardMarkup klaviaturalari (Xabarlar ostidagi tugmalar)
"""
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import config
from database.models import SponsorChannel, Movie

GENRES_LIST = [
    "Jangari", "Komediya", "Drama", "Fantastika",
    "Melodrama", "Qo'rqinchli", "Multfilm", "Sarguzasht",
    "Detektiv", "Tarixiy", "Triller", "Anime"
]


def subscription_keyboard(channels: List[SponsorChannel]) -> InlineKeyboardMarkup:
    """Majburiy a'zolik kanallari klaviaturasi."""
    builder = InlineKeyboardBuilder()

    for idx, channel in enumerate(channels, 1):
        link = channel.invite_link
        if not link.startswith("http"):
            link = f"https://t.me/{link.lstrip('@')}"
        builder.row(
            InlineKeyboardButton(
                text=f"📢 {idx}-kanal: {channel.title}",
                url=link
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="✅ Obunani tekshirish",
            callback_data="check_subscription"
        )
    )
    return builder.as_markup()


def movie_menu_keyboard() -> InlineKeyboardMarkup:
    """Kino asosiy menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔢 Kod orqali qidirish", callback_data="movie:by_code"),
        InlineKeyboardButton(text="🔍 Nomi bo'yicha qidirish", callback_data="movie:by_title"),
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Tasodifiy kino", callback_data="movie:random"),
        InlineKeyboardButton(text="🎭 Janrlar bo'yicha", callback_data="movie:genres"),
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Eng ommabop kinolar", callback_data="movie:top"),
    )
    channel_link = f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}"
    builder.row(
        InlineKeyboardButton(text=f"🍿 {config.CHANNEL_USERNAME} kanali", url=channel_link),
    )
    return builder.as_markup()


def genres_keyboard() -> InlineKeyboardMarkup:
    """Janrlar ro'yxati klaviaturasi."""
    builder = InlineKeyboardBuilder()
    # 2 qatordan terish
    for i in range(0, len(GENRES_LIST), 2):
        row = [InlineKeyboardButton(text=f"🎬 {GENRES_LIST[i]}", callback_data=f"genre:{GENRES_LIST[i]}")]
        if i + 1 < len(GENRES_LIST):
            row.append(InlineKeyboardButton(text=f"🎬 {GENRES_LIST[i+1]}", callback_data=f"genre:{GENRES_LIST[i+1]}"))
        builder.row(*row)

    builder.row(
        InlineKeyboardButton(text="🔙 Kino menyusiga qaytish", callback_data="movie:menu")
    )
    return builder.as_markup()


def movie_item_keyboard(movie_code: str) -> InlineKeyboardMarkup:
    """Kino xabari ostidagi tugmalar."""
    builder = InlineKeyboardBuilder()
    share_url = f"https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME.lstrip('@')}?start=movie_{movie_code}&text=Ajoyib kino! Botga kirib ko'ring: kod {movie_code}"
    channel_url = f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}"

    builder.row(
        InlineKeyboardButton(text="↗️ Do'stlarga ulashish", url=share_url),
        InlineKeyboardButton(text=f"🍿 {config.CHANNEL_USERNAME}", url=channel_url),
    )
    return builder.as_markup()


def movie_list_keyboard(movies: List[Movie], page: int = 0, total_pages: int = 1, prefix: str = "mlist") -> InlineKeyboardMarkup:
    """Kinolar ro'yxati va pagination klaviaturasi."""
    builder = InlineKeyboardBuilder()
    for m in movies:
        builder.row(
            InlineKeyboardButton(
                text=f"🎬 {m.code} | {m.title[:30]}",
                callback_data=f"get_movie:{m.code}"
            )
        )

    # Navigatsiya
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{prefix}:{page+1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="🔙 Kino menyusiga qaytish", callback_data="movie:menu")
    )
    return builder.as_markup()


def media_download_keyboard(cache_key: str) -> InlineKeyboardMarkup:
    """Yuklab olingan video ostidagi tugmalar (MP3 ajratish va ulashish)."""
    builder = InlineKeyboardBuilder()
    share_url = f"https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME.lstrip('@')}&text=Tezkor video yuklovchi bot!"
    channel_url = f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}"

    builder.row(
        InlineKeyboardButton(text="🎵 Musiqasini yuklash (MP3)", callback_data=f"dl_audio:{cache_key}"),
    )
    builder.row(
        InlineKeyboardButton(text="↗️ Do'stlarga ulashish", url=share_url),
        InlineKeyboardButton(text=f"🍿 {config.CHANNEL_USERNAME}", url=channel_url),
    )
    return builder.as_markup()


def music_results_keyboard(tracks: List[dict]) -> InlineKeyboardMarkup:
    """Qo'shiq qidiruv natijalari klaviaturasi."""
    builder = InlineKeyboardBuilder()
    for idx, track in enumerate(tracks, 1):
        title = f"{idx}. {track.get('artist', '')} - {track.get('title', '')}"[:40]
        # track_id or index
        builder.row(
            InlineKeyboardButton(
                text=f"🎵 {title}",
                callback_data=f"dl_track:{track.get('id', idx)}"
            )
        )
    return builder.as_markup()


def admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Admin boshqaruv paneli inline klaviaturasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 To'liq statistika", callback_data="admin:stats"),
        InlineKeyboardButton(text="🎬 Kinolar boshqaruvi", callback_data="admin:movies"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Xabarnoma yuborish", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="🔒 Homiylar (Kanallar)", callback_data="admin:sponsors"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings"),
        InlineKeyboardButton(text="❌ Yopish", callback_data="admin:close"),
    )
    return builder.as_markup()


def admin_movies_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin kinolar menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Yangi kino qo'shish", callback_data="admin:movie:add"),
        InlineKeyboardButton(text="🗑️ Kinoni o'chirish", callback_data="admin:movie:delete"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="admin:movie:list:0"),
        InlineKeyboardButton(text="🔍 Kod bo'yicha ko'rish", callback_data="admin:movie:view"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin:menu")
    )
    return builder.as_markup()


def admin_sponsors_menu_keyboard(channels: List[SponsorChannel]) -> InlineKeyboardMarkup:
    """Admin homiylar menyusi."""
    builder = InlineKeyboardBuilder()
    for ch in channels:
        status_icon = "🟢" if ch.is_active else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {ch.title[:20]} ({ch.channel_id})",
                callback_data=f"admin:sponsor:toggle:{ch.channel_id}"
            ),
            InlineKeyboardButton(
                text="🗑️ O'chirish",
                callback_data=f"admin:sponsor:delete:{ch.channel_id}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="admin:sponsor:add"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin:menu"),
    )
    return builder.as_markup()


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Xabarnoma tasdiqlash klaviaturasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yuborishni boshlash", callback_data="admin:broadcast:confirm"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:broadcast:cancel"),
    )
    return builder.as_markup()


def genre_picker_keyboard() -> InlineKeyboardMarkup:
    """Yangi kino qo'shishda janr tanlash klaviaturasi."""
    builder = InlineKeyboardBuilder()
    for i in range(0, len(GENRES_LIST), 2):
        row = [InlineKeyboardButton(text=GENRES_LIST[i], callback_data=f"pick_genre:{GENRES_LIST[i]}")]
        if i + 1 < len(GENRES_LIST):
            row.append(InlineKeyboardButton(text=GENRES_LIST[i+1], callback_data=f"pick_genre:{GENRES_LIST[i+1]}"))
        builder.row(*row)
    builder.row(
        InlineKeyboardButton(text="✅ Tanlashni tugatish", callback_data="pick_genre:done")
    )
    return builder.as_markup()
