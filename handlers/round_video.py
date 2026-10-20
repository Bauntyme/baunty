"""
Dumaloq video (Teleskop / Video note) handlerlari
"""
import uuid
import logging
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from config import config
from services.video_service import video_service
from keyboards.default import cancel_keyboard, main_menu_keyboard
from utils.states import RoundVideoStates
from utils.helpers import safe_remove_file

logger = logging.getLogger(__name__)
router = Router(name="round_video_router")


@router.message(F.text.in_(["⭕️ Dumaloq video", "📹 Dumaloq video", "Dumaloq video", "dumaloq video"]))
async def cmd_round_video_prompt(message: Message, state: FSMContext) -> None:
    """Dumaloq video tayyorlash bo'limi."""
    await state.set_state(RoundVideoStates.waiting_for_video)
    text = (
        "⭕️ <b>Dumaloq video (Teleskop) tayyorlash!</b>\n\n"
        "Menga istalgan video yuboring (davomiyligi 1 daqiqagacha bo'lishi tavsiya etiladi).\n"
        "Men uni Telegram doira shaklidagi video xabar (video note) holatiga keltirib beraman! 🎬\n\n"
        "Videoni yuboring: 👇"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(RoundVideoStates.waiting_for_video, F.video | F.document)
async def state_process_round_video(message: Message, state: FSMContext) -> None:
    """Videoni qabul qilib dumaloq videoga aylantirish."""
    media = message.video or message.document
    if not media:
        await message.reply("❌ Video fayl topilmadi. Iltimos video yuboring.")
        return

    await state.clear()
    status_msg = await message.reply("⏳ <b>Video yuklab olinmoqda va doira shakliga o'tkazilmoqda...</b>", parse_mode="HTML")

    temp_in = str(config.download_path / f"in_{uuid.uuid4().hex[:8]}.mp4")
    try:
        await message.bot.download(media, destination=temp_in)
        out_video = await video_service.convert_to_round_video(temp_in)
        safe_remove_file(temp_in)

        if not out_video:
            await status_msg.edit_text("❌ Videoni dumaloq shaklga o'tkazishda xatolik yuz berdi.", parse_mode="HTML")
            return

        # Video note sifatida yuborish
        try:
            await message.reply_video_note(
                video_note=FSInputFile(out_video),
                reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
            )
        except TelegramBadRequest as tbe:
            if "VOICE_MESSAGES_FORBIDDEN" in str(tbe):
                logger.warning(
                    f"Foydalanuvchi {message.from_user.id} da video xabarlar taqiqlangan ({tbe}). "
                    "Video shaklida yuborilmoqda..."
                )
                await message.reply_video(
                    video=FSInputFile(out_video),
                    caption=(
                        "⭕️ <b>Dumaloq video tayyor!</b>\n\n"
                        "<i>Sizda Telegram maxfiylik sozlamalarida video xabar (video note) qabul qilish cheklangani "
                        "sababli video shaklida yuborildi.</i>"
                    ),
                    parse_mode="HTML",
                    reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
                )
            else:
                raise
        try:
            await status_msg.delete()
        except Exception:
            pass
        safe_remove_file(out_video)

    except Exception as e:
        logger.exception(f"Dumaloq video yaratishda xatolik: {e}")
        safe_remove_file(temp_in)
        try:
            await status_msg.edit_text("❌ Texnik xatolik yuz berdi.", parse_mode="HTML")
        except Exception:
            pass
