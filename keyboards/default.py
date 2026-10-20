"""
ReplyKeyboardMarkup klaviaturalari (Doimiy tugmalar)
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import config


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasi (8 ta doimiy reply tugma va qo'shimchalar)."""
    buttons = [
        [
            KeyboardButton(text="🎬 K I N O — kod orqali qidirish"),
        ],
        [
            KeyboardButton(text="🎬 Kino"),
            KeyboardButton(text="🎵 Qo'shiq topish"),
            KeyboardButton(text="📚 Kitoblar"),
        ],
        [
            KeyboardButton(text="📥 Media yuklash"),
            KeyboardButton(text="👀 Anonim story"),
        ],
        [
            KeyboardButton(text="📄 Hujjatlar"),
            KeyboardButton(text="⭕️ Dumaloq video"),
        ],
        [
            KeyboardButton(text="💌 Anonim savollar"),
            KeyboardButton(text="🎁 Do'st taklif qilish"),
        ],
        [
            KeyboardButton(text="👥 Guruhlarim"),
            KeyboardButton(text="💬 Xato va fikrlar"),
        ],
    ]

    if is_admin:
        buttons.append([KeyboardButton(text="👑 Admin Panel")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Quyidagi tugmalardan birini tanlang yoki kino kodi yuboring...",
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Amalni bekor qilish klaviaturasi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
        input_field_placeholder="Amalni bekor qilish uchun bosing...",
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    """Orqaga qaytish klaviaturasi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Orqaga")]],
        resize_keyboard=True,
    )


def admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Admin bo'limi uchun reply klaviatura."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🎬 Kinolar")],
            [KeyboardButton(text="📢 Xabarnoma"), KeyboardButton(text="🔒 Homiylar")],
            [KeyboardButton(text="⚙️ Sozlamalar"), KeyboardButton(text="🔙 Bosh menyu")],
        ],
        resize_keyboard=True,
    )


def maintenance_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Profilaktika / Yangilanish holatida ishlaydigan ruxsat etilgan funksiyalar klaviaturasi."""
    buttons = [
        [
            KeyboardButton(text="🎵 Qo'shiq topish"),
            KeyboardButton(text="⭕️ Dumaloq video"),
        ],
        [
            KeyboardButton(text="📥 Media yuklash"),
        ],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="👑 Admin Panel")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Profilaktika davomida musiqa, dumaloq video va yuklash ishlaydi...",
    )
