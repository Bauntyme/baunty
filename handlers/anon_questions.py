"""
Anonim savollar va xabarlar (NGL uslubida ?start=q_...) handlerlari
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from keyboards.default import cancel_keyboard, main_menu_keyboard
from utils.states import AnonQuestionStates

logger = logging.getLogger(__name__)
router = Router(name="anon_questions_router")


@router.message(F.text == "💌 Anonim savollar")
async def cmd_anon_questions_link(message: Message, state: FSMContext) -> None:
    """Foydalanuvchining shaxsiy anonim savollar havolasini ko'rsatish."""
    await state.clear()
    user_id = message.from_user.id
    bot_name = config.BOT_USERNAME.lstrip('@')
    link = f"https://t.me/{bot_name}?start=q_{user_id}"

    text = (
        "💌 <b>Sizning shaxsiy anonim savollar havolangiz:</b>\n\n"
        f"🔗 <code>{link}</code>\n\n"
        "💡 <b>Qanday ishlaydi?</b>\n"
        "1. Ushbu havolani Instagram Bio, Telegram kanal yoki do'stlaringizga yuboring.\n"
        "2. Ular sizga o'z shaxsini bildirmasdan anonim savol, dil so'zlari yoki fikr yozishadi.\n"
        "3. Siz xabarlarni to'g'ridan-to'g'ri shu botda qabul qilib, anonim tarzda javob qaytara olasiz!"
    )

    share_url = f"https://t.me/share/url?url={link}&text=Menga anonim savol yoki dil so'zlaringizni yozing! Shaxsingiz sir qoladi 🤫"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↗️ Havolani ulashish", url=share_url)
    )

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("anon_reply:"))
async def cb_anon_reply(callback: CallbackQuery, state: FSMContext) -> None:
    """Anonim xabarga javob qaytarishni boshlash."""
    sender_id_str = callback.data.split("anon_reply:")[-1]
    try:
        sender_id = int(sender_id_str)
    except ValueError:
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    await state.set_state(AnonQuestionStates.waiting_for_reply)
    await state.update_data(reply_to_user_id=sender_id)

    await callback.message.reply(
        "✍️ <b>Anonim javobingizni yozing:</b>\n"
        "Sizning javobingiz savol egasiga yetkaziladi.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AnonQuestionStates.waiting_for_reply, F.text)
async def state_process_anon_reply(message: Message, state: FSMContext) -> None:
    """Anonim javobni jo'natuvchiga yetkazish."""
    data = await state.get_data()
    target_user_id = data.get("reply_to_user_id")
    reply_text = message.text.strip()
    await state.clear()

    if not target_user_id:
        await message.reply("Xatolik: qabul qiluvchi aniqlanmadi.")
        return

    try:
        reply_msg_text = (
            "💌 <b>Siz yuborgan anonim savolga javob keldi!</b>\n\n"
            f"«<i>{reply_text}</i>»"
        )
        await message.bot.send_message(chat_id=target_user_id, text=reply_msg_text, parse_mode="HTML")
        await message.reply(
            "✅ <b>Javobingiz anonim tarzda yetkazildi!</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )
    except Exception as e:
        logger.error(f"Anonim javobni yuborishda xatolik: {e}")
        await message.reply(
            "❌ Kechirasiz, foydalanuvchiga xabarni yetkazib bo'lmadi (ehtimol u botni bloklagan).",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )


@router.message(AnonQuestionStates.waiting_for_message, F.text)
async def state_process_anon_message(message: Message, state: FSMContext) -> None:
    """Anonim savolni qabul qilib egasiga yetkazish."""
    data = await state.get_data()
    target_user_id = data.get("anon_target_id")
    text = message.text.strip()
    await state.clear()

    if not target_user_id:
        await message.reply("Qabul qiluvchi aniqlanmadi.")
        return

    sender_id = message.from_user.id
    async with get_session() as session:
        await crud.create_anonymous_message(
            session=session,
            sender_id=sender_id,
            recipient_id=target_user_id,
            text=text
        )

    # Egasi uchun xabar
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↩️ Anonim javob qaytarish", callback_data=f"anon_reply:{sender_id}")
    )

    alert_text = (
        "💌 <b>Sizga yangi anonim xabar keldi!</b>\n\n"
        f"«<i>{text}</i>»\n\n"
        "🔒 <i>Yuboruvchi shaxsi to'liq sir saqlangan.</i>"
    )

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=alert_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await message.reply(
            "🎉 <b>Xabaringiz anonim tarzda muvaffaqiyatli yetkazildi!</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id))
        )
    except Exception as e:
        logger.error(f"Anonim xabarni yetkazishda xatolik: {e}")
        await message.reply(
            "❌ Xabarni yetkazib bo'lmadi. Foydalanuvchi botni to'xtatgan bo'lishi mumkin.",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id))
        )
