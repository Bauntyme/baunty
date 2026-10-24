"""
Guruhlar bo'limi handlerlari (Botni guruhga qo'shish)
"""
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from config import config

router = Router(name="groups_router")


@router.message(F.text.in_(["👥 Guruhlarim", "👥 Гуруҳларим", "👥 Мои группы"]))
async def cmd_groups_info(message: Message, state: FSMContext) -> None:
    """Botni guruhga qo'shish ko'rsatmasi."""
    await state.clear()
    bot_name = config.BOT_USERNAME.lstrip('@')
    add_group_url = f"https://t.me/{bot_name}?startgroup=true"

    text = (
        "👥 <b>Botni guruhingizga qo'shing!</b>\n\n"
        "Botni o'z guruhingizga qo'shib quyidagi imkoniyatlardan birgalikda foydalaning:\n"
        "• Guruh a'zolari kino kodlarini yozib to'g'ridan-to'g'ri filmlarni tomosha qilishlari mumkin\n"
        "• Instagram, TikTok, YouTube videolarini suv belgisiz guruhga yuklash\n"
        "• Qo'shiqlarni nom yoki ovoz orqali topib, guruhda eshitish\n"
        "• Mini HTML5 o'yinlarni guruhda o'ynash\n\n"
        "Botni guruhga administrator qilib tayinlash tavsiya etiladi! 👇"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Guruhga qo'shish", url=add_group_url)
    )

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
