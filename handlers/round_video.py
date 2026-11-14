"""
Dumaloq video (Teleskop / Video note) handlerlari
"""
import uuid
import logging
from pathlib import Path
from typing import Optional, Any
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from config import config
from services.video_service import video_service
from keyboards.default import cancel_keyboard, main_menu_keyboard
from keyboards.inline import round_video_options_keyboard, round_video_action_keyboard
from utils.states import RoundVideoStates
from utils.helpers import safe_remove_file

logger = logging.getLogger(__name__)
router = Router(name="round_video_router")


async def send_round_video_note(
    bot: Bot,
    chat_id: int,
    video_path: str,
    duration: Optional[int] = None,
    length: int = 384,
    reply_markup: Any = None,
    reply_to_message_id: Optional[int] = None,
) -> Message:
    """
    Doiraviy video note yuborish (length=384, duration).
    Agar VOICE_MESSAGES_FORBIDDEN yoki boshqa cheklov bo'lsa, zaxira sifatida video yuboradi.
    """
    try:
        return await bot.send_video_note(
            chat_id=chat_id,
            video_note=FSInputFile(video_path),
            duration=duration,
            length=length,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id
        )
    except TelegramBadRequest as tbe:
        logger.warning(f"send_video_note xatosi ({tbe}), send_video zaxirasi ishlatilmoqda...")
        return await bot.send_video(
            chat_id=chat_id,
            video=FSInputFile(video_path),
            duration=duration,
            width=length,
            height=length,
            caption=(
                "⭕️ <b>Dumaloq video tayyor!</b>\n\n"
                "<i>Sizda Telegram maxfiylik sozlamalarida video xabar (video note) qabul qilish cheklangani "
                "sababli video shaklida yuborildi.</i>"
            ),
            parse_mode="HTML",
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id
        )


@router.message(F.text.in_([
    "⭕️ Dumaloq video", "⭕ Dumaloq video", "📹 Dumaloq video", "Dumaloq video", "dumaloq video",
    "⭕️ Думалоқ видео", "⭕ Думалоқ видео", "📹 Думалоқ видео", "Думалоқ видео", "думалоқ видео",
    "⭕️ Круглое видео", "⭕ Круглое видео", "📹 Круглое видео", "Круглое видео", "круглое видео"
]))
async def cmd_round_video_prompt(message: Message, state: FSMContext) -> None:
    """Dumaloq video tayyorlash bo'limi."""
    await state.set_state(RoundVideoStates.waiting_for_video)
    await state.update_data(mute=False)
    text = (
        "⭕️ <b>Dumaloq video (Teleskop / Video Note) tayyorlash!</b>\n\n"
        "Menga istalgan video yuboring:\n"
        "• ⏱ <b>Davomiyligi:</b> Maksimal 60 soniya (ortiqcha qismi avtomatik qirqiladi)\n"
        "• 📐 <b>Shakli:</b> Markazdan 1:1 kvadrat (384x384) qilib olinadi\n"
        "• ⚡️ <b>Tezlik:</b> Yuqori tezlikda tayyorlanadi (<1s)!\n\n"
        "<i>Quyidagi tugmalar orqali ovozni o'chirish (mute) yoki bekor qilish mumkin.</i>\n\n"
        "Videoni yuboring: 👇"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=round_video_options_keyboard(mute=False)
    )


@router.callback_query(RoundVideoStates.waiting_for_video, F.data == "round:toggle_mute")
async def cb_toggle_mute(callback: CallbackQuery, state: FSMContext) -> None:
    """Ovozni o'chirish/yoqish sozlamasini o'zgartirish."""
    data = await state.get_data()
    current_mute = data.get("mute", False)
    new_mute = not current_mute
    await state.update_data(mute=new_mute)
    status_str = "o'chirildi (ovozsiz)" if new_mute else "yoqildi (ovozli)"
    await callback.answer(f"Ovoz {status_str}")
    try:
        await callback.message.edit_reply_markup(
            reply_markup=round_video_options_keyboard(mute=new_mute)
        )
    except Exception:
        pass


@router.callback_query(F.data == "round:cancel")
async def cb_cancel_round_video(callback: CallbackQuery, state: FSMContext) -> None:
    """Dumaloq video tayyorlashni inline bekor qilish."""
    await state.clear()
    await callback.answer("Bekor qilindi")
    is_admin = config.is_admin(callback.from_user.id) if callback.from_user else False
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "❌ <b>Dumaloq video tayyorlash bekor qilindi.</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin)
    )


@router.callback_query(F.data == "round:again")
async def cb_round_again(callback: CallbackQuery, state: FSMContext) -> None:
    """Yangi video yuborishni boshlash."""
    await state.set_state(RoundVideoStates.waiting_for_video)
    await state.update_data(mute=False)
    await callback.answer()
    await callback.message.answer(
        "⭕️ <b>Yangi video yuboring:</b>\n"
        "• Maksimal 60 soniya\n"
        "• 1:1 kvadrat formatga keltiriladi",
        parse_mode="HTML",
        reply_markup=round_video_options_keyboard(mute=False)
    )


@router.callback_query(F.data == "round:menu")
async def cb_round_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Asosiy menyuga qaytish."""
    await state.clear()
    await callback.answer()
    is_admin = config.is_admin(callback.from_user.id) if callback.from_user else False
    await callback.message.answer(
        "🏠 <b>Asosiy menyu:</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin)
    )


@router.message(RoundVideoStates.waiting_for_video, F.text.in_([
    "❌ Bekor qilish", "❌ Бекор қилиş", "❌ Бекор қилиш", "❌ Отмена",
    "🔙 Bosh menyu", "🔙 Бош меню", "🔙 Главное меню",
    "🔙 Orqaga", "🔙 Орқага", "🔙 Назад",
    "/cancel", "/stop"
]))
async def msg_cancel_round_video(message: Message, state: FSMContext) -> None:
    """Dumaloq video tayyorlashni matn orqali bekor qilish."""
    await state.clear()
    is_admin = config.is_admin(message.from_user.id) if message.from_user else False
    await message.answer(
        "❌ <b>Dumaloq video tayyorlash bekor qilindi.</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin)
    )


@router.message(RoundVideoStates.waiting_for_video, F.video | F.document)
async def state_process_round_video(message: Message, state: FSMContext) -> None:
    """Videoni qabul qilib dumaloq videoga aylantirish."""
    media = message.video or message.document
    if not media:
        await message.reply("❌ Video fayl topilmadi. Iltimos video yuboring.")
        return

    # Hujjat bo'lsa video formatini tekshirish
    if message.document:
        mime = getattr(message.document, "mime_type", "") or ""
        fname = getattr(message.document, "file_name", "") or ""
        if not (mime.startswith("video/") or fname.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm"))):
            await message.reply(
                "❌ Yuborilgan hujjat video formatida emas. Iltimos, video fayl yuboring (MP4, MOV, AVI).",
                reply_markup=cancel_keyboard()
            )
            return

    # FSM holatidan sozlamalarni olish (masalan, mute)
    state_data = await state.get_data()
    mute = bool(state_data.get("mute", False)) if isinstance(state_data, dict) else False

    await state.clear()
    status_msg = await message.reply("⏳ <b>Video yuklab olinmoqda va doira shakliga o'tkazilmoqda...</b>", parse_mode="HTML")

    temp_in = str(config.download_path / f"in_{uuid.uuid4().hex[:8]}.mp4")
    out_video = None
    try:
        await message.bot.download(media, destination=temp_in)

        # Video davomiyligini aniqlash (max 60s)
        raw_dur = getattr(media, "duration", None)
        if isinstance(raw_dur, (int, float)) and raw_dur > 0:
            duration = max(1, min(int(raw_dur), 60))
        else:
            duration = await video_service.get_video_duration(temp_in)
            if not duration or duration <= 0:
                duration = 1

        out_video = await video_service.convert_to_round_video(temp_in, mute=mute)
        safe_remove_file(temp_in)

        if not out_video:
            await status_msg.edit_text("❌ Videoni dumaloq shaklga o'tkazishda xatolik yuz berdi.", parse_mode="HTML")
            return

        is_admin = config.is_admin(message.from_user.id) if message.from_user else False

        # Video note sifatida yuborish (length=384, duration)
        try:
            await message.reply_video_note(
                video_note=FSInputFile(out_video),
                duration=duration,
                length=384,
                reply_markup=main_menu_keyboard(is_admin=is_admin)
            )
        except TelegramBadRequest as tbe:
            logger.warning(
                f"Foydalanuvchi {message.from_user.id} da video xabarlar taqiqlangan ({tbe}). "
                "Video shaklida yuborilmoqda..."
            )
            await message.reply_video(
                video=FSInputFile(out_video),
                duration=duration,
                width=384,
                height=384,
                caption=(
                    "⭕️ <b>Dumaloq video tayyor!</b>\n\n"
                    "<i>Sizda Telegram maxfiylik sozlamalarida video xabar (video note) qabul qilish cheklangani "
                    "sababli video shaklida yuborildi.</i>"
                ),
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(is_admin=is_admin)
            )

        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"Dumaloq video yaratishda xatolik: {e}")
        safe_remove_file(temp_in)
        try:
            await status_msg.edit_text("❌ Texnik xatolik yuz berdi.", parse_mode="HTML")
        except Exception:
            pass
    finally:
        if out_video:
            safe_remove_file(out_video)


@router.message(RoundVideoStates.waiting_for_video)
async def msg_invalid_round_video_input(message: Message) -> None:
    """Video o'rniga boshqa xabar kelganda ko'rsatma berish."""
    await message.reply(
        "⚠️ <b>Iltimos, video fayl yuboring!</b>\n\n"
        "• Davomiyligi 60 soniyagacha bo'lgan video (MP4, MOV, AVI)\n"
        "• Bekor qilish uchun: <b>❌ Bekor qilish</b>",
        parse_mode="HTML",
        reply_markup=round_video_options_keyboard(mute=False)
    )
