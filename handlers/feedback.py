"""
Xato va fikrlar bo'limi handlerlari
"""
import asyncio
import html
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from keyboards.default import cancel_keyboard, main_menu_keyboard
from utils.states import FeedbackStates

logger = logging.getLogger(__name__)
router = Router(name="feedback_router")

CANCEL_WORDS = {
    "❌ bekor qilish", "❌ бекор қилиш", "❌ отмена",
    "🔙 bosh menyu", "🔙 бош меню", "🔙 главное меню",
    "🔙 orqaga", "🔙 орқага", "🔙 назад",
    "/cancel", "/stop"
}


@router.message(Command("feedback", "xato", "fikr", "shikoyat", "report"))
@router.message(F.text.in_(["💬 Xato va fikrlar", "💬 Хато ва фикрлар", "💬 Отзывы и ошибки"]))
async def cmd_feedback_prompt(message: Message, state: FSMContext) -> None:
    """Fikr bildirish yoki xato haqida xabar berish so'rovi."""
    await state.set_state(FeedbackStates.waiting_for_feedback)
    text = (
        "💬 <b>Fikr-mulohaza yoki xato haqida xabar berish</b>\n\n"
        "Bot faoliyatini yanada yaxshilash bo'yicha takliflaringiz yoki "
        "uchragan texnik kamchiliklar haqida yozib qoldiring.\n\n"
        "<i>(Matn, rasm yoki skrinshot yuborishingiz mumkin)</i>\n\n"
        "Xabaringizni yozing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


async def _notify_admins_async(bot, user, fb_text: str, message: Message) -> None:
    """Adminlarga fonda zudlik bilan bildirishnoma yuborish."""
    safe_name = html.escape(user.full_name or "Foydalanuvchi")
    safe_uname = f"@{user.username}" if user.username else "mavjud_emas"
    safe_text = html.escape(fb_text) if fb_text else "(Media fayl ilova qilindi)"

    admin_notify = (
        f"📬 <b>Yangi fikr/shikoyat!</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {safe_name} ({safe_uname}) [<code>{user.id}</code>]\n"
        f"💬 <b>Xabar:</b>\n<i>{safe_text}</i>"
    )

    for admin_id in config.admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_notify, parse_mode="HTML")
            if getattr(message, "photo", None) or getattr(message, "document", None) or getattr(message, "video", None):
                try:
                    await bot.copy_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Admin {admin_id} ga bildirishnoma yuborishda xatolik: {e}")


@router.message(FeedbackStates.waiting_for_feedback)
async def state_process_feedback(message: Message, state: FSMContext) -> None:
    """Fikrni saqlash va adminlarga xabar berish."""
    # Bekor qilish tekshiruvi
    if message.text and message.text.strip().lower() in CANCEL_WORDS:
        await state.clear()
        await message.reply(
            "❌ <b>Amal bekor qilindi.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )
        return

    user = message.from_user
    fb_text = (message.text or message.caption or "").strip()
    await state.clear()

    # Bazaga saqlash
    try:
        async with get_session() as session:
            await crud.create_feedback(
                session=session,
                user_id=user.id,
                username=user.username,
                message=fb_text or "(Fayl yuborildi)"
            )
    except Exception as db_err:
        logger.warning(f"Feedback saqlashda DB ogohlantirish: {db_err}")

    # Adminlarga asinxron fon vazifasi sifatida yetkazish (foydalanuvchi kutib qolmaydi)
    asyncio.create_task(_notify_admins_async(message.bot, user, fb_text, message))

    # Foydalanuvchiga darhol tezkor javob qaytarish
    await message.reply(
        "✅ <b>Fikr va taklifingiz uchun tashakkur!</b>\n"
        "Xabaringiz adminga yetkazildi va tez orada ko'rib chiqiladi.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=config.is_admin(user.id))
    )
