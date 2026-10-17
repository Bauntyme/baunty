"""
Xato va fikrlar bo'limi handlerlari
"""
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from keyboards.default import cancel_keyboard, main_menu_keyboard
from utils.states import FeedbackStates

logger = logging.getLogger(__name__)
router = Router(name="feedback_router")


@router.message(F.text == "💬 Xato va fikrlar")
async def cmd_feedback_prompt(message: Message, state: FSMContext) -> None:
    """Fikr bildirish yoki xato haqida xabar berish so'rovi."""
    await state.set_state(FeedbackStates.waiting_for_feedback)
    text = (
        "💬 <b>Fikr-mulohaza yoki xato haqida xabar berish</b>\n\n"
        "Bot faoliyatini yanada yaxshilash bo'yicha takliflaringiz yoki "
        "uchragan texnik kamchiliklar haqida yozib qoldiring.\n\n"
        "Xabaringizni yozing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(FeedbackStates.waiting_for_feedback, F.text)
async def state_process_feedback(message: Message, state: FSMContext) -> None:
    """Fikrni saqlash va adminlarga xabar berish."""
    user = message.from_user
    fb_text = message.text.strip()
    await state.clear()

    async with get_session() as session:
        await crud.create_feedback(
            session=session,
            user_id=user.id,
            username=user.username,
            message=fb_text
        )

    # Adminlarga xabar yetkazish
    for admin_id in config.admin_ids:
        try:
            admin_notify = (
                f"📬 <b>Yangi fikr/shikoyat!</b>\n\n"
                f"👤 <b>Foydalanuvchi:</b> {user.full_name} (@{user.username or 'mavjud_emas'}) [<code>{user.id}</code>]\n"
                f"💬 <b>Xabar:</b>\n<i>{fb_text}</i>"
            )
            await message.bot.send_message(chat_id=admin_id, text=admin_notify, parse_mode="HTML")
        except Exception:
            pass

    await message.reply(
        "✅ <b>Fikr va taklifingiz uchun tashakkur!</b>\n"
        "Xabaringiz adminga yetkazildi va tez orada ko'rib chiqiladi.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=config.is_admin(user.id))
    )
