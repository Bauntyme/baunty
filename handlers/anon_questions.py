"""
Anonim savollar va xabarlar (NGL uslubida ?start=q_...) handlerlari
"""
import html
import logging
from aiogram import Router, F
from aiogram.filters import Command
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

CANCEL_WORDS = {
    "❌ bekor qilish", "❌ бекор қилиш", "❌ отмена",
    "🔙 bosh menyu", "🔙 бош меню", "🔙 главное меню",
    "🔙 orqaga", "🔙 орқага", "🔙 назад",
    "/cancel", "/stop"
}


@router.message(Command("anon", "savol", "savollar", "ask", "q"))
@router.message(F.text.in_(["💌 Anonim savollar", "💌 Аноним саволlar", "💌 Аноним саволлар", "💌 Анонимные вопросы"]))
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
    sender_id_str = callback.data.split("anon_reply:")[-1].strip()
    try:
        sender_id = int(sender_id_str)
    except (ValueError, TypeError):
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    await state.set_state(AnonQuestionStates.waiting_for_reply)
    await state.update_data(reply_to_user_id=sender_id)

    await callback.message.reply(
        "✍️ <b>Anonim javobingizni yozing:</b>\n"
        "Sizning javobingiz savol egasiga to'liq yetkaziladi.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AnonQuestionStates.waiting_for_reply)
async def state_process_anon_reply(message: Message, state: FSMContext) -> None:
    """Anonim javobni jo'natuvchiga yetkazish."""
    data = await state.get_data()
    raw_target = data.get("reply_to_user_id")

    # Bekor qilish tekshiruvi
    if message.text and message.text.strip().lower() in CANCEL_WORDS:
        await state.clear()
        await message.reply(
            "❌ <b>Amal bekor qilindi.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )
        return

    try:
        target_user_id = int(raw_target) if raw_target is not None else None
    except (ValueError, TypeError):
        target_user_id = None

    reply_text = (message.text or message.caption or "").strip()
    await state.clear()

    if not target_user_id:
        await message.reply("Xatolik: qabul qiluvchi aniqlanmadi.", reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id)))
        return

    has_media = bool(
        getattr(message, "photo", None)
        or getattr(message, "video", None)
        or getattr(message, "voice", None)
        or getattr(message, "audio", None)
        or getattr(message, "document", None)
    )
    if not reply_text and has_media:
        reply_text = "(Media fayl ilova qilindi)"

    if not reply_text:
        await message.reply("Iltimos, javob matnini yozing.", reply_markup=cancel_keyboard())
        await state.set_state(AnonQuestionStates.waiting_for_reply)
        await state.update_data(reply_to_user_id=target_user_id)
        return

    safe_reply = html.escape(reply_text)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↩️ Anonim javob yozish", callback_data=f"anon_reply:{message.from_user.id}")
    )

    reply_msg_text = (
        "💌 <b>Siz yuborgan anonim savolga javob keldi!</b>\n\n"
        f"«<i>{safe_reply}</i>»\n\n"
        "🔒 <i>Yozishish to'liq anonim davom etmoqda.</i>"
    )

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=reply_msg_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        if has_media and hasattr(message, "copy_to"):
            try:
                await message.copy_to(chat_id=target_user_id)
            except Exception as media_err:
                logger.debug(f"Anonim javob mediasini nusxalashda xatolik: {media_err}")
        await message.reply(
            "✅ <b>Javobingiz anonim tarzda muvaffaqiyatli yetkazildi!</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )
    except Exception as e:
        logger.error(f"Anonim javobni yuborishda xatolik: {e}")
        await message.reply(
            "❌ Kechirasiz, foydalanuvchiga xabarni yetkazib bo'lmadi (ehtimol u botni to'xtatgan).",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )


@router.message(AnonQuestionStates.waiting_for_message)
async def state_process_anon_message(message: Message, state: FSMContext) -> None:
    """Anonim savolni qabul qilib egasiga yetkazish."""
    data = await state.get_data()
    raw_target = data.get("anon_target_id")

    # Bekor qilish tekshiruvi
    if message.text and message.text.strip().lower() in CANCEL_WORDS:
        await state.clear()
        await message.reply(
            "❌ <b>Amal bekor qilindi.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )
        return

    try:
        target_user_id = int(raw_target) if raw_target is not None else None
    except (ValueError, TypeError):
        target_user_id = None

    text = (message.text or message.caption or "").strip()
    await state.clear()

    sender_id = message.from_user.id
    if not target_user_id:
        await message.reply("Qabul qiluvchi aniqlanmadi.", reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)))
        return

    has_media = bool(
        getattr(message, "photo", None)
        or getattr(message, "video", None)
        or getattr(message, "voice", None)
        or getattr(message, "audio", None)
        or getattr(message, "document", None)
    )
    if not text and has_media:
        text = "(Media fayl ilova qilindi)"

    if not text:
        await message.reply("Iltimos, anonim xabaringiz matnini yozing.", reply_markup=cancel_keyboard())
        await state.set_state(AnonQuestionStates.waiting_for_message)
        await state.update_data(anon_target_id=target_user_id)
        return

    # Bazaga saqlash
    try:
        async with get_session() as session:
            await crud.create_anonymous_message(
                session=session,
                sender_id=sender_id,
                recipient_id=target_user_id,
                text=text
            )
    except Exception as db_err:
        logger.warning(f"Anonim xabarni DB ga saqlashda ogohlantirish: {db_err}")

    # Egasi uchun xabar
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↩️ Anonim javob qaytarish", callback_data=f"anon_reply:{sender_id}")
    )

    safe_text = html.escape(text)
    alert_text = (
        "💌 <b>Sizga yangi anonim xabar keldi!</b>\n\n"
        f"«<i>{safe_text}</i>»\n\n"
        "🔒 <i>Yuboruvchi shaxsi to'liq sir saqlangan. Pastdagi tugma orqali javob berishingiz mumkin.</i>"
    )

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=alert_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        if has_media and hasattr(message, "copy_to"):
            try:
                await message.copy_to(chat_id=target_user_id)
            except Exception as media_err:
                logger.debug(f"Anonim savol mediasini nusxalashda xatolik: {media_err}")
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

