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
    app_url = config.webapp_url_resolved
    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(text="📱 Kinolar katalogi (Mini App)", web_app=WebAppInfo(url=app_url))
        )
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
    share_url = f"https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME.lstrip('@')}?start=kino_{movie_code}&text=Ajoyib kino! Botga kirib ko'ring: kod {movie_code}"
    channel_url = f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}"

    builder.row(
        InlineKeyboardButton(
            text="▶️ Kinoni tomosha qilish (@Zakirovsfilms_bot)",
            url=f"https://t.me/Zakirovsfilms_bot?start={movie_code}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="↗️ Do'stlarga ulashish", url=share_url),
        InlineKeyboardButton(text=f"🍿 {config.CHANNEL_USERNAME}", url=channel_url),
    )
    app_url = config.webapp_url_resolved
    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(text="📱 Mini Appda ko'rish", web_app=WebAppInfo(url=app_url))
        )
    return builder.as_markup()


def movie_parts_keyboard(
    movie_code: str,
    total_parts: int,
    current_part: int = 1,
    page: Optional[int] = None,
    per_page: int = 20
) -> InlineKeyboardMarkup:
    """Ko'p qismli seriallar uchun qismlar tugmalari ([1] [2] ... [N]) va ulashish.
    Telegram 100-tugma cheklovidan oshib ketmasligi uchun 20 tadan sahifalarga ajratiladi.
    """
    builder = InlineKeyboardBuilder()

    # Sahifani avtomatik hisoblash (agar berilmagan bo'lsa)
    if page is None:
        page = max(0, (current_part - 1) // per_page) if current_part > 0 else 0

    total_pages = max(1, (total_parts + per_page - 1) // per_page)
    if page >= total_pages:
        page = total_pages - 1

    start_part = page * per_page + 1
    end_part = min(total_parts, (page + 1) * per_page)

    row = []
    for p in range(start_part, end_part + 1):
        btn_text = f"▶️ {p}" if p == current_part else str(p)
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"watch_part:{movie_code}:{p}"))
        if len(row) == 5:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)

    # Agar qismlar 20 tadan ko'p bo'lsa, sahifalar navigatsiyasi
    if total_pages > 1:
        nav_row = []
        if page > 0:
            prev_label = f"⬅️ { (page-1)*per_page + 1 }–{ page*per_page }"
            nav_row.append(InlineKeyboardButton(text=prev_label, callback_data=f"parts_page:{movie_code}:{page-1}"))
        if page < total_pages - 1:
            next_label = f"{ (page+1)*per_page + 1 }–{ min(total_parts, (page+2)*per_page) } ➡️"
            nav_row.append(InlineKeyboardButton(text=next_label, callback_data=f"parts_page:{movie_code}:{page+1}"))
        if nav_row:
            builder.row(*nav_row)

    target_start = f"{movie_code}_{current_part}" if current_part > 1 else movie_code
    builder.row(
        InlineKeyboardButton(
            text=f"▶️ {current_part}-qismni ko'rish (@Zakirovsfilms_bot)",
            url=f"https://t.me/Zakirovsfilms_bot?start={target_start}"
        )
    )

    share_url = f"https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME.lstrip('@')}?start=kino_{movie_code}&text=Ajoyib kino! Botga kirib ko'ring: kod {movie_code}"
    channel_url = f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}"
    builder.row(
        InlineKeyboardButton(text="↗️ Do'stlarga ulashish", url=share_url),
        InlineKeyboardButton(text=f"🍿 {config.CHANNEL_USERNAME}", url=channel_url),
    )
    app_url = config.webapp_url_resolved
    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(text="📱 Mini Appda ko'rish", web_app=WebAppInfo(url=app_url))
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
    """Yuklab olingan video ostidagi tugmalar (Video musiqasi va Original qo'shiq)."""
    builder = InlineKeyboardBuilder()
    share_url = f"https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME.lstrip('@')}&text=Tezkor video yuklovchi bot!"
    channel_url = f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}"

    builder.row(
        InlineKeyboardButton(text="🎵 Video musiqasi", callback_data=f"dl_audio:{cache_key}"),
        InlineKeyboardButton(text="🔍 Original qo'shiq", callback_data=f"dl_shazam:{cache_key}"),
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


def admin_movie_detail_keyboard(movie_code: str) -> InlineKeyboardMarkup:
    """Admin kino batafsil ma'lumotlari ostidagi tugmalar."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"admin:movie:edit:{movie_code}"),
        InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"admin:movie:del_direct:{movie_code}"),
    )
    builder.row(
        InlineKeyboardButton(text="▶️ Kinoni ko'rish", callback_data=f"get_movie:{movie_code}"),
        InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="admin:movie:list:0"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Kinolar boshqaruvi", callback_data="admin:movies")
    )
    return builder.as_markup()


def movie_edit_keyboard(movie_code: str) -> InlineKeyboardMarkup:
    """Kinoni tahrirlash maydonlari klaviaturasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Nomi", callback_data=f"admin:medit:title:{movie_code}"),
        InlineKeyboardButton(text="🎭 Janri", callback_data=f"admin:medit:genres:{movie_code}"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Yili", callback_data=f"admin:medit:year:{movie_code}"),
        InlineKeyboardButton(text="⭐ Reytingi", callback_data=f"admin:medit:rating:{movie_code}"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Tavsifi", callback_data=f"admin:medit:desc:{movie_code}"),
        InlineKeyboardButton(text="📹 Video fayli", callback_data=f"admin:medit:media:{movie_code}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Ortga", callback_data=f"admin:movie:view_direct:{movie_code}")
    )
    return builder.as_markup()


def admin_settings_keyboard() -> InlineKeyboardMarkup:
    """Admin sozlamalar menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Kanalni yangilash", callback_data="admin:set:channel"),
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin:menu"),
    )
    return builder.as_markup()

