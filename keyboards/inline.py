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
        InlineKeyboardButton(text="📅 Yili bo'yicha", callback_data="movie:by_year"),
        InlineKeyboardButton(text="👤 Aktyor bo'yicha", callback_data="movie:by_actor"),
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


def movie_item_keyboard(
    movie_code: str,
    watch_url: Optional[str] = None,
    download_url: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Kino xabari ostidagi tugmalar."""
    builder = InlineKeyboardBuilder()
    share_url = f"https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME.lstrip('@')}?start=kino_{movie_code}&text=Ajoyib kino! Botga kirib ko'ring: kod {movie_code}"
    channel_url = f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}"

    if watch_url and watch_url.startswith("http"):
        app_url = config.webapp_url_resolved
        if app_url and app_url.startswith("https://"):
            from aiogram.types import WebAppInfo
            builder.row(
                InlineKeyboardButton(
                    text="▶️ Kinoni tomosha qilish (Full HD)",
                    web_app=WebAppInfo(url=f"{app_url}?c={movie_code}")
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="▶️ Kinoni tomosha qilish (Full HD)",
                    callback_data=f"watch_part:{movie_code}:1"
                )
            )
    else:
        builder.row(
            InlineKeyboardButton(
                text="▶️ Kinoni tomosha qilish",
                callback_data=f"watch_part:{movie_code}:1"
            )
        )
    if download_url:
        builder.row(
            InlineKeyboardButton(
                text="📥 Yuklab olish",
                callback_data=f"download_movie:{movie_code}:1"
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
            InlineKeyboardButton(text="▶️ Web App orqali tomosha qilish", web_app=WebAppInfo(url=app_url))
        )
    return builder.as_markup()


def movie_parts_keyboard(
    movie_code: str,
    total_parts: int,
    current_part: int = 1,
    page: Optional[int] = None,
    per_page: int = 20,
    watch_url: Optional[str] = None,
    download_url: Optional[str] = None
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
    app_url = config.webapp_url_resolved

    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(
                text=f"▶️ {current_part}-qism onlayn (Full HD)",
                web_app=WebAppInfo(url=f"{app_url}?c={movie_code}&part={current_part}")
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=f"▶️ {current_part}-qism onlayn (Full HD)",
                callback_data=f"watch_part:{movie_code}:{current_part}"
            )
        )
    if download_url:
        builder.row(
            InlineKeyboardButton(
                text="📥 Yuklab olish",
                callback_data=f"download_movie:{movie_code}:{current_part}"
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
            InlineKeyboardButton(text="▶️ Web App orqali tomosha qilish", web_app=WebAppInfo(url=app_url))
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


def music_results_keyboard(
    tracks: List[dict],
    page: int = 0,
    per_page: int = 8,
    search_id: str = ""
) -> InlineKeyboardMarkup:
    """
    Qo'shiq qidiruv natijalari klaviaturasi (Kamida 15-30 ta natija uchun ixcham sahifalash bilan).
    Har sahifada 8 tadan qo'shiq, ostida [⬅️ Oldingi], [Keyingi ➡️], [📄 1/3] tugmalari.
    """
    builder = InlineKeyboardBuilder()
    if not tracks:
        return builder.as_markup()

    total = len(tracks)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * per_page
    end_idx = min(total, (page + 1) * per_page)
    page_items = tracks[start_idx:end_idx]

    for offset, track in enumerate(page_items):
        idx = start_idx + offset + 1
        artist = str(track.get("artist") or "").strip()
        title = str(track.get("title") or "").strip()
        full_name = f"{idx}. {artist} - {title}".strip(" -")
        if len(full_name) > 40:
            full_name = full_name[:39] + "…"
        track_id = track.get("id", idx)
        builder.row(
            InlineKeyboardButton(
                text=f"🎵 {full_name}",
                callback_data=f"dl_track:{track_id}"
            )
        )

    # Agar 1 dan ortiq sahifa bo'lsa, ixcham inline paginatsiya tugmalari
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️ Oldingi",
                    callback_data=f"music_page:{search_id}:{page - 1}"
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop"
            )
        )
        if page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="Keyingi ➡️",
                    callback_data=f"music_page:{search_id}:{page + 1}"
                )
            )
        builder.row(*nav_row)

    return builder.as_markup()


def admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Admin boshqaruv paneli inline klaviaturasi."""
    builder = InlineKeyboardBuilder()
    app_url = config.webapp_url_resolved
    flow_url = f"{app_url}/admin/flow" if app_url and app_url.startswith("https://") else "https://baunty.onrender.com/admin/flow"
    from aiogram.types import WebAppInfo
    builder.row(
        InlineKeyboardButton(text="⚡ Live Flow & DB Monitor", web_app=WebAppInfo(url=flow_url)),
    )
    builder.row(
        InlineKeyboardButton(text="📊 To'liq statistika", callback_data="admin:stats"),
        InlineKeyboardButton(text="🎬 Kinolar boshqaruvi", callback_data="admin:movies"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Xabarnoma yuborish", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="🔒 Homiylar (Kanallar)", callback_data="admin:sponsors"),
    )
    builder.row(
        InlineKeyboardButton(text="🛠️ Yangilanish / Profilaktika", callback_data="admin:maint:menu"),
        InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Kesh & Sinxronlash", callback_data="admin:cache:sync"),
        InlineKeyboardButton(text="🖥️ Server holati", callback_data="admin:server:health"),
    )
    builder.row(
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
        InlineKeyboardButton(text="🌐 Asilmedia.org dan bog'lash", callback_data="admin:movie:asilmedia_sync"),
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


def story_platform_keyboard() -> InlineKeyboardMarkup:
    """Anonim story platformasini tanlash: Telegram yoki Instagram."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✈️ Telegram Story", callback_data="story_platform:tg"),
        InlineKeyboardButton(text="📸 Instagram Story", callback_data="story_platform:ig"),
    )
    app_url = config.webapp_url_resolved
    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(text="📱 Mini Appda ko'rish", web_app=WebAppInfo(url=f"{app_url}#story"))
        )
    return builder.as_markup()


def admin_maintenance_main_keyboard(is_global_active: bool) -> InlineKeyboardMarkup:
    """Profilaktika boshqaruv asosiy menyusi."""
    builder = InlineKeyboardBuilder()
    if is_global_active:
        builder.row(
            InlineKeyboardButton(text="🟢 Tizimni qayta yoqish (Oddiy holat)", callback_data="admin:maint:global:off")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🛑 Butun tizimni to'xtatish (Profilaktika)", callback_data="admin:maint:global:pick")
        )

    builder.row(
        InlineKeyboardButton(text="📱 Alohida Web App sahifalari", callback_data="admin:maint:pages")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin:menu")
    )
    return builder.as_markup()


def admin_maintenance_templates_keyboard(target: str) -> InlineKeyboardMarkup:
    """Profilaktika xabarlari shablonlarini tanlash (1 dan 5 gacha).
    target: 'global' yoki sahifa id (masalan 'kino', 'food')
    """
    builder = InlineKeyboardBuilder()
    templates_labels = [
        "1️⃣ 🛠️ Texnik yangilanish...",
        "2️⃣ 🚀 Yangi zo'r funksiyalar...",
        "3️⃣ ⚡ Tezlik va sifat...",
        "4️⃣ ✨ Server optimallashtirilmoqda...",
        "5️⃣ 🎯 Yangi sara kontentlar...",
    ]
    for idx, lbl in enumerate(templates_labels):
        builder.row(
            InlineKeyboardButton(text=lbl, callback_data=f"admin:maint:set_tmpl:{target}:{idx}")
        )

    back_target = "admin:maint:pages" if target != "global" else "admin:maint:menu"
    builder.row(
        InlineKeyboardButton(text="🔙 Bekor qilish", callback_data=back_target)
    )
    return builder.as_markup()


def admin_maintenance_pages_keyboard(pages_state: dict) -> InlineKeyboardMarkup:
    """10 ta Web App sahifasining profilaktika holati va tanlash ro'yxati."""
    builder = InlineKeyboardBuilder()
    from services.maintenance_service import PAGE_EMOJIS, PAGE_NAMES

    # 2 qatorli tugmalar
    page_keys = list(PAGE_EMOJIS.keys())
    for i in range(0, len(page_keys), 2):
        row_buttons = []
        for k in page_keys[i:i+2]:
            em = PAGE_EMOJIS[k]
            nm = PAGE_NAMES.get(k, k.capitalize())
            is_on = pages_state.get(k, {}).get("enabled", False)
            status_dot = "🔴" if is_on else "🟢"
            row_buttons.append(
                InlineKeyboardButton(
                    text=f"{em} {nm} {status_dot}",
                    callback_data=f"admin:maint:page:{k}"
                )
            )
        builder.row(*row_buttons)

    builder.row(
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:maint:menu")
    )
    return builder.as_markup()


def admin_maintenance_page_detail_keyboard(page_id: str, is_active: bool) -> InlineKeyboardMarkup:
    """Alohida sahifa profilaktikasini yoqish/o'chirish va xabar tanlash."""
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.row(
            InlineKeyboardButton(text="🟢 Profilaktikani o'chirish (Yoqish)", callback_data=f"admin:maint:page_off:{page_id}")
        )
        builder.row(
            InlineKeyboardButton(text="📝 Xabarni o'zgartirish (5 shablon)", callback_data=f"admin:maint:page_pick:{page_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🛑 Profilaktikaga qo'yish (O'chirish)", callback_data=f"admin:maint:page_pick:{page_id}")
        )

    builder.row(
        InlineKeyboardButton(text="🔙 Sahifalar ro'yxatiga qaytish", callback_data="admin:maint:pages")
    )
    return builder.as_markup()

