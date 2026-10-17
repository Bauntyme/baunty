"""
Musiqa bo'limi qayta ishlovchisi (Qo'shiq qidirish va MP3 yuklash)
"""
import logging
from typing import Dict, Any
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from services.music_service import music_service
from keyboards.default import cancel_keyboard, main_menu_keyboard
from keyboards.inline import music_results_keyboard
from utils.states import MusicStates
from utils.helpers import safe_remove_file

logger = logging.getLogger(__name__)
router = Router(name="music_router")

# Foydalanuvchi qidiruv natijalarini vaqtinchalik saqlash
_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}


@router.message(F.text == "🎵 Qo'shiq topish")
async def cmd_music_menu(message: Message, state: FSMContext) -> None:
    """Musiqa qidirish boshlanishi."""
    await state.set_state(MusicStates.waiting_for_query)
    text = (
        "🎵 <b>Qo'shiq qidirish xizmati!</b>\n\n"
        "Qidirayotgan qo'shig'ingiz nomi yoki ijrochisini yozing:\n"
        "<i>Masalan: Konsta, Jaloliddin Ahmadaliyev, Jah Khalib yoki Rayhon</i>\n\n"
        "Yoki ovozli xabar (voice) yuborishingiz ham mumkin! 🎙️"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(MusicStates.waiting_for_query, F.text)
async def state_process_music_query(message: Message, state: FSMContext) -> None:
    """Qo'shiq so'rovi bo'yicha qidirish."""
    query = message.text.strip()
    status_msg = await message.reply("🔍 <b>Qo'shiqlar qidirilmoqda...</b>", parse_mode="HTML")

    try:
        tracks = await music_service.search_tracks(query, limit=8)
        if not tracks:
            await status_msg.edit_text(
                f"❌ <b>«{query}»</b> bo'yicha hech qanday qo'shiq topilmadi.\n"
                "Iltimos, nomni to'g'ri yozib qayta urinib ko'ring.",
                parse_mode="HTML"
            )
            return

        # Natijalarni keshga saqlash
        user_id = message.from_user.id
        for t in tracks:
            track_key = f"{user_id}_{t['id']}"
            _SEARCH_CACHE[track_key] = t

        text = (
            f"🎵 <b>«{query}» bo'yicha topilgan natijalar:</b>\n"
            "Yuklab olmoqchi bo'lgan qo'shiqni tanlang:"
        )

        # Inline tugmalar yaratish
        formatted_tracks = []
        for t in tracks:
            formatted_tracks.append({
                "id": f"{user_id}_{t['id']}",
                "title": t["title"],
                "artist": t["artist"],
            })

        markup = music_results_keyboard(formatted_tracks)
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await state.clear()

    except Exception as e:
        logger.exception(f"Musiqa qidirishda xatolik: {e}")
        await status_msg.edit_text("❌ Musiqa qidirishda texnik xatolik yuz berdi.", parse_mode="HTML")


@router.message(F.voice | F.audio)
async def process_voice_or_audio(message: Message) -> None:
    """Ovozli xabar yoki audio kelganda javob berish."""
    text = (
        "🎙️ <b>Ovozli xabaringiz qabul qilindi!</b>\n\n"
        "Qo'shiqni aniqroq topish uchun uning so'zlarini yoki ijrochisini matn sifatida yuboring:\n"
        "<i>«🎵 Qo'shiq topish» tugmasidan foydalaning.</i>"
    )
    await message.reply(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("dl_track:"))
async def cb_download_track(callback: CallbackQuery) -> None:
    """Tanlangan qo'shiqni yuklab berish."""
    track_key = callback.data.split("dl_track:")[-1]
    track_data = _SEARCH_CACHE.get(track_key)

    if not track_data:
        await callback.answer("⚠️ Ma'lumot eskirgan, iltimos qaytadan qidiring.", show_alert=True)
        return

    artist = track_data.get("artist", "")
    title = track_data.get("title", "")
    full_search_query = f"{artist} - {title}"

    await callback.answer("⏳ MP3 tayyorlanmoqda...")
    status_msg = await callback.message.reply(
        f"⏳ <b>«{full_search_query}» yuklanmoqda...</b>\n<i>Iltimos, kuting...</i>",
        parse_mode="HTML"
    )

    try:
        res = await music_service.download_track_mp3(full_search_query)

        if not res.success or not res.file_path:
            err_msg = res.error if res.error else "Noma'lum xato"
            await status_msg.edit_text(
                f"❌ <b>Qo'shiqni yuklab bo'lmadi:</b>\n{err_msg}",
                parse_mode="HTML"
            )
            return

        audio_file = FSInputFile(res.file_path)
        caption = (
            f"🎵 <b>{artist} - {title}</b>\n\n"
            f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yuklandi</b>\n"
            f"🍿 <b>Kinolar kanalimiz:</b> {config.CHANNEL_USERNAME}"
        )

        await callback.message.reply_audio(
            audio=audio_file,
            title=title,
            performer=artist or f"@{config.BOT_USERNAME.lstrip('@')}",
            duration=res.duration,
            caption=caption,
            parse_mode="HTML"
        )

        try:
            await status_msg.delete()
        except Exception:
            pass

        safe_remove_file(res.file_path)

        async with get_session() as session:
            await crud.log_download(
                session=session,
                user_id=callback.from_user.id,
                platform="music",
                query_or_url=full_search_query
            )

    except Exception as e:
        logger.exception(f"Qo'shiq yuklashda xatolik: {e}")
        try:
            await status_msg.edit_text("❌ Qo'shiqni yuklashda texnik xatolik yuz berdi.", parse_mode="HTML")
        except Exception:
            pass
