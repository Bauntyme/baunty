"""
ReplyKeyboardMarkup klaviaturalari (Doimiy tugmalar)
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import config


DEFAULT_BUTTONS = {
    "uz": {
        "kino_search": "🎬 K I N O — kod orqali qidirish",
        "kino": "🎬 Kino",
        "music": "🎵 Qo'shiq topish",
        "books": "📚 Kitoblar",
        "mafia": "🕵️ Mafia",
        "tvroom": "📺 Tv Xona",
        "rasxod": "💰 Rasxod",
        "kaloriya": "🥗 Kaloriya",
        "media": "📥 Media yuklash",
        "story": "👀 Anonim story",
        "docs": "📄 Hujjatlar",
        "round_video": "⭕️ Dumaloq video",
        "anon": "💌 Anonim savollar",
        "referral": "🎁 Do'st taklif qilish",
        "groups": "👥 Guruhlarim",
        "feedback": "💬 Xato va fikrlar",
        "lang": "🌐 Tilni tanlash",
        "admin": "👑 Admin Panel",
        "cancel": "❌ Bekor qilish",
        "back": "🔙 Orqaga",
        "stats": "📊 Statistika",
        "movies": "🎬 Kinolar",
        "broadcast": "📢 Xabarnoma",
        "sponsors": "🔒 Homiylar",
        "settings": "⚙️ Sozlamalar",
        "main_menu": "🔙 Bosh menyu",
        "placeholder": "Quyidagi tugmalardan birini tanlang yoki kino kodi yuboring...",
        "cancel_placeholder": "Amalni bekor qilish uchun bosing...",
        "maint_placeholder": "Profilaktika davomida musiqa, dumaloq video va yuklash ishlaydi...",
    },
    "oz": {
        "kino_search": "🎬 К И Н О — код орқали қидириш",
        "kino": "🎬 Кино",
        "music": "🎵 Қўшиқ топиш",
        "books": "📚 Китоблар",
        "mafia": "🕵️ Мафия",
        "tvroom": "📺 Тв Хона",
        "rasxod": "💰 Расход",
        "kaloriya": "🥗 Калория",
        "media": "📥 Медиа юклаш",
        "story": "👀 Аноним стори",
        "docs": "📄 Ҳужжатлар",
        "round_video": "⭕️ Думалоқ видео",
        "anon": "💌 Аноним саволлар",
        "referral": "🎁 Дўст таклиф қилиш",
        "groups": "👥 Гуруҳларим",
        "feedback": "💬 Хато ва фикрлар",
        "lang": "🌐 Тилни танлаш",
        "admin": "👑 Админ Панел",
        "cancel": "❌ Бекор қилиш",
        "back": "🔙 Орқага",
        "stats": "📊 Статистика",
        "movies": "🎬 Кинолар",
        "broadcast": "📢 Хабарнома",
        "sponsors": "🔒 Ҳомийлар",
        "settings": "⚙️ Созламалар",
        "main_menu": "🔙 Бош меню",
        "placeholder": "Қуйидаги тугмалардан бирини танланг ёки кино кодини юборинг...",
        "cancel_placeholder": "Амални бекор қилиш учун босинг...",
        "maint_placeholder": "Профилактика давомида мусиқа, думалоқ видео ва юклаш ишлайди...",
    },
    "ru": {
        "kino_search": "🎬 К И Н О — поиск по коду",
        "kino": "🎬 Фильмы",
        "music": "🎵 Поиск музыки",
        "books": "📚 Книги",
        "mafia": "🕵️ Мафия",
        "tvroom": "📺 ТВ Комната",
        "rasxod": "💰 Расход",
        "kaloriya": "🥗 Калории",
        "media": "📥 Скачать медиа",
        "story": "👀 Анонимные истории",
        "docs": "📄 Документы",
        "round_video": "⭕️ Круглое видео",
        "anon": "💌 Анонимные вопросы",
        "referral": "🎁 Пригласить друга",
        "groups": "👥 Мои группы",
        "feedback": "💬 Отзывы и ошибки",
        "lang": "🌐 Сменить язык",
        "admin": "👑 Панель админа",
        "cancel": "❌ Отмена",
        "back": "🔙 Назад",
        "stats": "📊 Статистика",
        "movies": "🎬 Фильмы",
        "broadcast": "📢 Рассылка",
        "sponsors": "🔒 Спонсоры",
        "settings": "⚙️ Настройки",
        "main_menu": "🔙 Главное меню",
        "placeholder": "Выберите действие ниже или отправьте код фильма...",
        "cancel_placeholder": "Нажмите для отмены действия...",
        "maint_placeholder": "Во время техработ работают музыка, круглое видео и загрузка...",
    }
}


def _get_lang_dict(lang: str = "uz") -> dict:
    clean = (lang or "uz").lower()
    return DEFAULT_BUTTONS.get(clean, DEFAULT_BUTTONS["uz"])


def main_menu_keyboard(is_admin: bool = False, lang: str = "uz") -> ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasi (8 ta doimiy reply tugma va qo'shimchalar)."""
    t = _get_lang_dict(lang)
    buttons = [
        [
            KeyboardButton(text=t["kino_search"]),
        ],
        [
            KeyboardButton(text=t["kino"]),
            KeyboardButton(text=t["music"]),
            KeyboardButton(text=t["books"]),
        ],
        [
            KeyboardButton(text=t["media"]),
            KeyboardButton(text=t["story"]),
        ],
        [
            KeyboardButton(text=t["docs"]),
            KeyboardButton(text=t["round_video"]),
        ],
        [
            KeyboardButton(text=t["anon"]),
            KeyboardButton(text=t["referral"]),
        ],
        [
            KeyboardButton(text=t["groups"]),
            KeyboardButton(text=t["feedback"]),
        ],
        [
            KeyboardButton(text=t["lang"]),
        ],
    ]

    if is_admin:
        buttons.append([KeyboardButton(text=t["admin"])])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder=t["placeholder"],
    )


def cancel_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Amalni bekor qilish klaviaturasi."""
    t = _get_lang_dict(lang)
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t["cancel"])]],
        resize_keyboard=True,
        input_field_placeholder=t["cancel_placeholder"],
    )


def back_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Orqaga qaytish klaviaturasi."""
    t = _get_lang_dict(lang)
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t["back"])]],
        resize_keyboard=True,
    )


def admin_reply_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Admin bo'limi uchun reply klaviatura."""
    t = _get_lang_dict(lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["stats"]), KeyboardButton(text=t["movies"])],
            [KeyboardButton(text=t["broadcast"]), KeyboardButton(text=t["sponsors"])],
            [KeyboardButton(text=t["settings"]), KeyboardButton(text=t["main_menu"])],
        ],
        resize_keyboard=True,
    )


def maintenance_menu_keyboard(is_admin: bool = False, lang: str = "uz") -> ReplyKeyboardMarkup:
    """Profilaktika / Yangilanish holatida ishlaydigan ruxsat etilgan funksiyalar klaviaturasi."""
    t = _get_lang_dict(lang)
    buttons = [
        [
            KeyboardButton(text=t["music"]),
            KeyboardButton(text=t["round_video"]),
        ],
        [
            KeyboardButton(text=t["media"]),
        ],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text=t["admin"])])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder=t["maint_placeholder"],
    )
