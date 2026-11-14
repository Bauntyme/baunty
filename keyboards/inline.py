"""
InlineKeyboardMarkup klaviaturalari (Xabarlar ostidagi tugmalar)
"""
from typing import List, Optional, Set, Union
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
        link = getattr(channel, "invite_link", None) or ""
        if not link:
            ch_id = str(getattr(channel, "channel_id", "")).lstrip("@")
            link = f"https://t.me/{ch_id}"
        elif not link.startswith("http"):
            link = f"https://t.me/{link.lstrip('@')}"

        title = getattr(channel, "title", "Baunty Films")
        btn_text = f"📢 Kanalga a'zo bo'lish: {title}" if len(channels) == 1 else f"📢 {idx}-kanal: {title}"
        builder.row(
            InlineKeyboardButton(
                text=btn_text,
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
    from services.bot_identity import build_telegram_share_url, get_bot_username

    bot_user = get_bot_username()
    share_url = build_telegram_share_url(
        f"https://t.me/{bot_user}?start=kino_{movie_code}",
        f"Ajoyib kino! Botga kirib ko'ring: kod {movie_code}",
    )
    channel_url = f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}"

    # 1. Asosiy va birinchi tugma: Web App orqali onlayn tomosha qilish (Anti-Ban / DMCA-Safe HLS)
    app_url = config.webapp_url_resolved
    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(
                text="▶️ Onlayn tomosha qilish",
                web_app=WebAppInfo(url=f"{app_url}?c={movie_code}")
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="▶️ Onlayn tomosha qilish",
                callback_data=f"watch_part:{movie_code}:1"
            )
        )

    # 2. Telegram ichida ko'rish (Bot orqali ijro)
    builder.row(
        InlineKeyboardButton(
            text="🎬 Kinoni tomosha qilish",
            callback_data=f"watch_part:{movie_code}:1"
        )
    )
    # 3. Yuklab olish
    builder.row(
        InlineKeyboardButton(
            text="📥 Yuklab olish",
            callback_data=f"download_movie:{movie_code}:1"
        )
    )
    # 4. Ulashish va rasmiy kanal
    builder.row(
        InlineKeyboardButton(text="↗️ Do'stlarga ulashish", url=share_url),
        InlineKeyboardButton(text=f"🍿 {config.CHANNEL_USERNAME}", url=channel_url),
    )
    return builder.as_markup()


def movie_parts_keyboard(
    movie_code: str,
    total_parts: int,
    current_part: int = 1,
    page: Optional[int] = None,
    per_page: int = 50,
    watched_parts: Optional[Union[Set[int], List[int]]] = None,
    webapp_url: Optional[str] = None,
    watch_url: Optional[str] = None,
    download_url: Optional[str] = None,
    window_threshold: int = 20,
) -> InlineKeyboardMarkup:
    """Ko'p qismli seriallar uchun 5 ustunli qismlar tugmalari ([1] [2] ... [50]),
    ko'rilganlik belgisi (✓), davom ettirish tugmasi va in-place range pagination pills.
    """
    builder = InlineKeyboardBuilder()

    clean_code = str(movie_code).strip().lstrip("#№")[:40]
    total_p = max(1, int(total_parts))
    cur_p = max(1, int(current_part)) if current_part else 1
    per_p = max(1, int(per_page))

    # Sahifani hisoblash (agar berilmagan bo'lsa, current_part joylashgan sahifa)
    if page is None:
        page = max(0, (cur_p - 1) // per_p)

    total_pages = max(1, (total_p + per_p - 1) // per_p)
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0

    watched_set = set(watched_parts or [])

    # 1. Next-episode shortcut button at the top:
    # [Davom ettirish: {next_p}-qism] yoki [Qayta ko'rish: 1-qism]
    next_p = None
    for p_num in range(1, total_p + 1):
        if p_num not in watched_set:
            next_p = p_num
            break

    if next_p is not None:
        shortcut_text = f"Davom ettirish: {next_p}-qism"
        shortcut_cb = f"watch_part:{clean_code}:{next_p}"
    else:
        shortcut_text = "Qayta ko'rish: 1-qism"
        shortcut_cb = f"watch_part:{clean_code}:1"

    builder.row(InlineKeyboardButton(text=shortcut_text, callback_data=shortcut_cb))

    # 2. 5 ustunli qismlar to'plami (5 cols x 10 rows = 50 max)
    start_part = page * per_p + 1
    end_part = min(total_p, (page + 1) * per_p)

    row = []
    for p in range(start_part, end_part + 1):
        if p == cur_p:
            btn_text = f"▶️ {p}"
        elif p in watched_set:
            btn_text = f"✓ {p}"
        else:
            btn_text = str(p)
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"watch_part:{clean_code}:{p}"))
        if len(row) == 5:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)

    # 3. In-place range pagination pills below grid:
    # Masalan, 139 qism uchun: [ • 1–50 ], [ 51–100 ], [ 101–139 ]
    # Ultra-long series windowing: when total_pages > window_threshold, window pills around page
    # (page - 3 to page + 3, plus first and last page) so total buttons never exceed 100.
    if total_pages > 1:
        pill_buttons = []
        if total_pages > window_threshold:
            win_start = max(0, page - 3)
            win_end = min(total_pages, page + 4)
            page_indices = sorted(set([0, total_pages - 1] + list(range(win_start, win_end))))
        else:
            page_indices = list(range(total_pages))

        for p_idx in page_indices:
            p_start = p_idx * per_p + 1
            p_end = min(total_p, (p_idx + 1) * per_p)
            if p_idx == page:
                pill_text = f"• {p_start}–{p_end}"
            else:
                pill_text = f"{p_start}–{p_end}"
            pill_buttons.append(
                InlineKeyboardButton(
                    text=pill_text,
                    callback_data=f"parts_page:{clean_code}:{p_idx}"
                )
            )

        # Chunk pills into rows of up to 3 or 4 pills
        chunk_size = 3 if len(pill_buttons) > 3 else len(pill_buttons)
        for i in range(0, len(pill_buttons), chunk_size):
            builder.row(*pill_buttons[i:i + chunk_size])

    # 4. [🎬 Katalogda ochish] WebApp button
    app_url = webapp_url or config.webapp_url_resolved
    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(
                text="🎬 Katalogda ochish",
                web_app=WebAppInfo(url=f"{app_url}?c={clean_code}&part={cur_p}")
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="🎬 Katalogda ochish",
                callback_data=f"get_movie:{clean_code}"
            )
        )

    # 5. Yuklab olish va ulashish tugmalari
    if download_url or total_p <= per_p:
        builder.row(
            InlineKeyboardButton(
                text="📥 Yuklab olish",
                callback_data=f"download_movie:{clean_code}:{cur_p}"
            )
        )

    from services.bot_identity import build_telegram_share_url, get_bot_username

    bot_user = get_bot_username()
    share_url = build_telegram_share_url(
        f"https://t.me/{bot_user}?start=kino_{clean_code}",
        f"Ajoyib kino! Botga kirib ko'ring: kod {clean_code}",
    )
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
    """Yuklab olingan video ostidagi tugmalar (Video musiqasi va Original qo'shiq)."""
    builder = InlineKeyboardBuilder()
    from services.bot_identity import build_telegram_share_url, get_bot_username

    bot_user = get_bot_username()
    share_url = build_telegram_share_url(
        f"https://t.me/{bot_user}",
        "Tezkor video va musiqa yuklovchi bot!",
    )
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
    app_url_clean = app_url.rstrip("/") if app_url else ""
    flow_url = f"{app_url_clean}/admin/flow" if app_url and app_url.startswith("https://") else "https://baunty-cinema.onrender.com/admin/flow"
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


def story_platform_keyboard(webapp_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Anonim story platformasini tanlash: Telegram yoki Instagram."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 Telegram story", callback_data="story_platform:tg"),
        InlineKeyboardButton(text="📸 Instagram story", callback_data="story_platform:ig"),
    )
    app_url = webapp_url if webapp_url is not None else config.webapp_url_resolved
    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(text="📱 Mini Appda ko'rish", web_app=WebAppInfo(url=f"{app_url}#story"))
        )
    builder.row(
        InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="story_platform:menu"),
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


def round_video_options_keyboard(mute: bool = False) -> InlineKeyboardMarkup:
    """Dumaloq video tayyorlash sozlamalari (Ovozni o'chirish/yoqish va bekor qilish)."""
    builder = InlineKeyboardBuilder()
    mute_text = "🔇 Ovoz: O'chirilgan" if mute else "🔊 Ovoz: Yoqilgan"
    builder.row(
        InlineKeyboardButton(text=mute_text, callback_data="round:toggle_mute"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="round:cancel"),
    )
    return builder.as_markup()


def round_video_action_keyboard(cache_key: Optional[str] = None) -> InlineKeyboardMarkup:
    """Dumaloq video tayyor bo'lgandan keyingi amallar (MP3 ajratish, yangi video)."""
    builder = InlineKeyboardBuilder()
    if cache_key:
        builder.row(
            InlineKeyboardButton(text="🎵 Musiqasini (MP3) yuklab olish", callback_data=f"round:mp3:{cache_key}"),
        )
    builder.row(
        InlineKeyboardButton(text="🔄 Yangi video yuborish", callback_data="round:again"),
        InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="round:menu"),
    )
    return builder.as_markup()


def anon_questions_keyboard(share_url: str, is_accepting: bool = True) -> InlineKeyboardMarkup:
    """Anonim savollar boshqaruv klaviaturasi (5 ta qator)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✈️ Telegramda ulashish", url=share_url),
        InlineKeyboardButton(text="🪄 Chiroyli karta", callback_data="anon:share_card"),
    )
    builder.row(
        InlineKeyboardButton(text="📸 Instagram story uchun rasm", callback_data="anon:ig_story_img")
    )
    toggle_text = "⏸ Qabulni to'xtatish" if is_accepting else "▶️ Qabulni yoqish"
    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data="anon:toggle_accept")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Havolani yangilash", callback_data="anon:regen_confirm")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="anon:main_menu")
    )
    return builder.as_markup()


def anon_share_card_keyboard(link: str) -> InlineKeyboardMarkup:
    """Do'stlarga va kanallarga forward qilish uchun chiroyli taklif kartasi tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💌 Anonim savol yozish", url=link)
    )
    return builder.as_markup()


def anon_regen_confirm_keyboard() -> InlineKeyboardMarkup:
    """Anonim savol havolasini yangilash tasdiqlash tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, yangilash", callback_data="anon:regen_yes"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="anon:regen_no"),
    )
    return builder.as_markup()


def anon_incoming_keyboard(sender_id: int, is_blocked: bool = False) -> InlineKeyboardMarkup:
    """Kelgan anonim savolga javob berish va bloklash tugmalari."""
    builder = InlineKeyboardBuilder()
    block_btn = (
        InlineKeyboardButton(text="✅ Blokdan chiqarish", callback_data=f"anon:unblock:{sender_id}")
        if is_blocked
        else InlineKeyboardButton(text="🚫 Bloklash", callback_data=f"anon:block:{sender_id}")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ Anonim javob qaytarish", callback_data=f"anon_reply:{sender_id}"),
        block_btn,
    )
    return builder.as_markup()

