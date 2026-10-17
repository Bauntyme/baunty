"""
Anonim Instagram Story ko'rish bo'limi
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from services.story_service import story_service
from keyboards.default import cancel_keyboard, main_menu_keyboard
from utils.states import StoryStates
from utils.helpers import safe_remove_file

logger = logging.getLogger(__name__)
router = Router(name="story_router")


@router.message(F.text == "👀 Anonim story")
async def cmd_story_prompt(message: Message, state: FSMContext) -> None:
    """Anonim story ko'rish uchun so'rov."""
    await state.set_state(StoryStates.waiting_for_username)
    text = (
        "👀 <b>Anonim Instagram Story yuklash!</b>\n\n"
        "Instagram foydalanuvchi nomini yoki profil havolasini yozing:\n"
        "<i>Masalan: <code>cristiano</code> yoki <code>@leomessi</code></i>\n\n"
        "🔒 <b>To'liq anonim:</b> Profil egasi siz uning hikoyasini ko'rganingizni bilmaydi.\n"
        "⚠️ <b>Diqqat:</b> Profil ochiq (public) bo'lishi va faol hikoyalar mavjud bo'lishi shart."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(StoryStates.waiting_for_username, F.text)
async def state_process_story_username(message: Message, state: FSMContext) -> None:
    """Kiritilgan username bo'yicha story yuklash."""
    username = story_service.clean_username(message.text)
    if not username:
        await message.reply("❌ Noto'g'ri username kiritildi. Qaytadan urinib ko'ring.")
        return

    status_msg = await message.reply(
        f"⏳ <b>@{username} profilidagi hikoyalar yuklanmoqda...</b>\n<i>Iltimos, kuting...</i>",
        parse_mode="HTML"
    )

    try:
        result = await story_service.fetch_story(username)

        if not result.success or not result.file_path:
            await status_msg.edit_text(
                f"❌ <b>@{username} profilida faol hikoyalar topilmadi.</b>\n\n"
                "Mumkin bo'lgan sabablar:\n"
                "• Foydalanuvchi hozirda hech qanday story joylamagan\n"
                "• Profil yopiq (shaxsiy / private)\n"
                "• Foydalanuvchi nomi xato kiritilgan",
                parse_mode="HTML"
            )
            await state.clear()
            return

        video_file = FSInputFile(result.file_path)
        caption = (
            f"👀 <b>@{username} ning yangi videosi/hikoyasi</b>\n\n"
            f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yuklandi</b>\n"
            f"🍿 <b>Kinolar:</b> {config.CHANNEL_USERNAME}"
        )

        await message.reply_video(
            video=video_file,
            caption=caption,
            parse_mode="HTML"
        )

        try:
            await status_msg.delete()
        except Exception:
            pass

        safe_remove_file(result.file_path)

        async with get_session() as session:
            await crud.log_download(
                session=session,
                user_id=message.from_user.id,
                platform="instagram_story",
                query_or_url=username
            )

        await state.clear()

    except Exception as e:
        logger.exception(f"Story yuklashda xatolik: {e}")
        try:
            await status_msg.edit_text("❌ Story yuklashda texnik xatolik yuz berdi.", parse_mode="HTML")
        except Exception:
            pass
        await state.clear()
