"""
Til tanlash handlerlari (/til, /lang, /language) - Bauntys
Foydalanuvchi interfeysi tilini tanlash va almashtirish (uz, oz, ru).
100% Bauntys brendi.
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database.session import get_session
from database import crud
from services.i18n_service import i18n_service
from keyboards.default import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="language_router")


@router.message(Command("til", "lang", "language"))
@router.message(F.text.in_([
    "🌐 Til", "🌐 Tilni tanlash", "🌐 Тилни танлаш", "🌐 Сменить язык",
    "🌐 Язык", "🌐 Выбрать язык", "Til", "Lang", "Тил"
]))
async def cmd_language(message: Message) -> None:
    """Til tanlash menyusini ko'rsatish."""
    user = message.from_user
    if not user:
        return

    current_lang = "uz"
    try:
        async with get_session() as session:
            current_lang = await crud.get_user_language(session, user.id)
    except Exception as e:
        logger.debug(f"Tilni olishda xatolik: {e}")

    text = i18n_service.get_text("choose_language", current_lang)
    kb = i18n_service.get_language_keyboard(current_lang)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("set_lang:"))
async def cb_set_language(call: CallbackQuery) -> None:
    """Foydalanuvchi tanlagan tilni saqlash."""
    user = call.from_user
    if not user:
        return

    lang_code = call.data.split(":", 1)[1].strip().lower()
    if lang_code not in ("uz", "oz", "ru"):
        lang_code = "uz"

    try:
        async with get_session() as session:
            await crud.set_user_language(session, user_id=user.id, language=lang_code)
    except Exception as e:
        logger.warning(f"Tilni saqlashda xatolik: {e}")

    success_text = i18n_service.get_text("language_changed", lang_code)
    kb = i18n_service.get_language_keyboard(lang_code)

    try:
        await call.message.edit_text(success_text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass

    # Yangi tildagi asosiy reply klaviaturani yuborish
    try:
        from config import config
        is_admin = config.is_admin(user.id)
        await call.message.answer(
            i18n_service.get_text("main_menu_title", lang_code),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=is_admin, lang=lang_code)
        )
    except Exception:
        pass

    await call.answer("✅ Til o'zgartirildi!")
