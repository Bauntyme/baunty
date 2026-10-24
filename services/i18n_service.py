"""
Xalqaro tillar va mahalliylashtirish servisi (i18n Service) - Bauntys
Qo'llab-quvvatlanadigan tillar:
- 'uz' - O'zbekcha (Lotin)
- 'oz' - Ўзбекча (Кирилл)
- 'ru' - Русский
100% Bauntys brendi.
"""
from typing import Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

LANGUAGES = {
    "uz": {"code": "uz", "name": "O'zbekcha", "flag": "🇺🇿"},
    "oz": {"code": "oz", "name": "Ўзбекча", "flag": "🇺🇿"},
    "ru": {"code": "ru", "name": "Русский", "flag": "🇷🇺"},
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "choose_language": {
        "uz": "🌐 <b>Tilni tanlang / Выберите язык:</b>\n\nIltimos, o'zingizga qulay bo'lgan tilni tanlang:",
        "oz": "🌐 <b>Тилни танланг / Выберите язык:</b>\n\nИлтимос, ўзингизга қулай бўлган тилни танланг:",
        "ru": "🌐 <b>Выберите язык / Tilni tanlang:</b>\n\nПожалуйста, выберите удобный для вас язык:",
    },
    "language_changed": {
        "uz": "✅ <b>Til muvaffaqiyatli o'zgartirildi:</b> O'zbekcha (Lotin)\n\nBotdan bemalol foydalanishingiz mumkin!",
        "oz": "✅ <b>Тил муваффақиятли ўзгартирилди:</b> Ўзбекча (Кирилл)\n\nБотдан бемалол фойдаланишингиз мумкин!",
        "ru": "✅ <b>Язык успешно изменен:</b> Русский\n\nПриятного пользования ботом!",
    },
    "main_menu_title": {
        "uz": "🍿 <b>Baunty Asosiy Menyu</b>",
        "oz": "🍿 <b>Baunty Асосий Меню</b>",
        "ru": "🍿 <b>Главное меню Baunty</b>",
    },
    "btn_movies": {
        "uz": "🎬 Kinolar",
        "oz": "🎬 Кинолар",
        "ru": "🎬 Фильмы",
    },
    "btn_music": {
        "uz": "🎵 Musiqa",
        "oz": "🎵 Мусиқа",
        "ru": "🎵 Музыка",
    },
    "btn_mafia": {
        "uz": "🕵️ Mafia",
        "oz": "🕵️ Мафия",
        "ru": "🕵️ Мафия",
    },
    "btn_quiz": {
        "uz": "🧠 Viktorina",
        "oz": "🧠 Викторина",
        "ru": "🧠 Викторина",
    },
    "btn_settings": {
        "uz": "⚙️ Sozlamalar",
        "oz": "⚙️ Созламалар",
        "ru": "⚙️ Настройки",
    },
    "btn_lang": {
        "uz": "🌐 Tilni o'zgartirish",
        "oz": "🌐 Тилни ўзгартириш",
        "ru": "🌐 Сменить язык",
    },
}


class I18nService:
    """Ko'p tillilik servisi."""

    def __init__(self):
        self.default_lang = "uz"

    def get_text(self, key: str, lang: Optional[str] = "uz", default: str = "") -> str:
        """Berilgan kalit va til bo'yicha matnni olish."""
        lang_code = (lang or self.default_lang).lower()
        if lang_code not in LANGUAGES:
            lang_code = self.default_lang

        translations = TRANSLATIONS.get(key)
        if not translations:
            return default or key

        return translations.get(lang_code, translations.get(self.default_lang, default or key))

    def get_language_keyboard(self, current_lang: str = "uz") -> InlineKeyboardMarkup:
        """Tilni tanlash inline klaviaturasi."""
        clean_cur = (current_lang or "uz").lower()
        buttons = []
        row = []
        for code, info in LANGUAGES.items():
            mark = " ✅" if code == clean_cur else ""
            row.append(
                InlineKeyboardButton(
                    text=f"{info['flag']} {info['name']}{mark}",
                    callback_data=f"set_lang:{code}"
                )
            )
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        return InlineKeyboardMarkup(inline_keyboard=buttons)


i18n_service = I18nService()
