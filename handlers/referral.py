"""
Referal tizimi (Do'st taklif qilish ?start=r_...) handlerlari
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from keyboards.default import main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router(name="referral_router")


@router.message(F.text.in_(["🎁 Do'st taklif qilish", "🎁 Дўст таклиф қилиш", "🎁 Пригласить друга"]))
async def cmd_referral_info(message: Message, state: FSMContext) -> None:
    """Do'st taklif qilish bo'limi va statistika."""
    await state.clear()
    user = message.from_user
    bot_name = config.BOT_USERNAME.lstrip('@')
    ref_link = f"https://t.me/{bot_name}?start=r_{user.id}"

    async with get_session() as session:
        ref_count, points = await crud.get_referral_stats(session, user.id)

    text = (
        "🎁 <b>Do'stlarni taklif qiling va ballar to'plang!</b>\n\n"
        f"Sizning shaxsiy referal havolangiz:\n"
        f"🔗 <code>{ref_link}</code>\n\n"
        "📊 <b>Sizning ko'rsatkichlaringiz:</b>\n"
        f"👥 Taklif qilingan do'stlar: <b>{ref_count}</b> ta\n"
        f"💎 To'plangan ballar: <b>{points}</b> ball\n\n"
        "💡 Har bir taklif qilgan faol do'stingiz uchun sizga <b>+10 ball</b> beriladi!"
    )

    share_url = f"https://t.me/share/url?url={ref_link}&text=Ajoyib kino va musiqa botini sinab ko'ring! 🎬🍿"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↗️ Havolani ulashish", url=share_url)
    )

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
