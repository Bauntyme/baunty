"""
Guruhlar bo'limi handlerlari (Botni guruhga qo'shish va guruhdagi qutlov)
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, ADMINISTRATOR
from aiogram.types import Message, InlineKeyboardButton, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from config import config

logger = logging.getLogger(__name__)
router = Router(name="groups_router")


@router.message(Command("groups", "guruh", "guruhlar", "guruhlarim"))
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


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER | ADMINISTRATOR))
async def on_bot_added_to_group(event: ChatMemberUpdated) -> None:
    """Bot guruhga yangi qo'shilganda qutlov va ko'rsatma yuborish."""
    try:
        if event.chat and event.chat.type in ("group", "supergroup"):
            welcome_text = (
                "👋 <b>Assalomu alaykum!</b>\n\n"
                "Men kinolarni kod orqali bir zumda topib beruvchi rasmiy botman 🍿\n\n"
                "🎬 <b>Qanday ishlatiladi?</b>\n"
                "• Shunchaki kino kodini yozing (masalan: <code>101</code> yoki <code>/kino 101</code>)\n"
                "• Qo'shiq topish: <code>/music nom</code>\n\n"
                f"🍿 <b>Barcha kinolar katalogi va kodlari:</b> {config.CHANNEL_USERNAME}\n"
                "<i>(Bot barcha xabarlarni uzluksiz o'qishi uchun guruh admini qilib tayinlash tavsiya etiladi)</i>"
            )
            await event.bot.send_message(chat_id=event.chat.id, text=welcome_text, parse_mode="HTML")
    except Exception as e:
        logger.debug(f"Guruh qutlov xabarini yuborishda xatolik: {e}")


@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message) -> None:
    """Guruhga bot qo'shilganida xush kelibsiz xabarini berish."""
    try:
        bot_info = await message.bot.get_me()
        for member in (message.new_chat_members or []):
            if member.id == bot_info.id:
                welcome_text = (
                    "👋 <b>Assalomu alaykum!</b>\n\n"
                    "Men guruhda kinolarni kod orqali bir zumda topib beruvchi rasmiy botman 🍿\n\n"
                    "🎬 <b>Qanday ishlatiladi?</b>\n"
                    "• Shunchaki kino kodini yozing (masalan: <code>101</code> yoki <code>/kino 101</code>)\n"
                    "• Qo'shiq topish: <code>/music nom</code>\n\n"
                    f"🍿 <b>Barcha kinolar katalogi:</b> {config.CHANNEL_USERNAME}\n"
                    "<i>(Bot barcha xabarlarni o'qishi uchun guruh admini qilib tayinlash tavsiya etiladi)</i>"
                )
                await message.reply(welcome_text, parse_mode="HTML")
                break
    except Exception as e:
        logger.debug(f"new_chat_members xabarida xatolik: {e}")

