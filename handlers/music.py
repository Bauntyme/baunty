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
        tracks = await music_service.search_tracks(query, limit=15)
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


import uuid
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


@router.message(F.voice | F.audio | F.video_note)
async def process_voice_or_audio(message: Message, state: FSMContext) -> None:
    """Ovozli xabar, audio yoki video note kelganda Shazam orqali qo'shiqni aniqlash."""
    await state.clear()
    status_msg = await message.reply(
        "🎧 <b>Ovozli xabar eshitilmoqda va qo'shiq aniqlanmoqda...</b>\n<i>Iltimos, kuting...</i>",
        parse_mode="HTML"
    )

    media_obj = message.voice or message.audio or message.video_note
    if not media_obj:
        await status_msg.edit_text("❌ Audio fayl topilmadi.")
        return

    ext = ".ogg" if message.voice else (".mp3" if message.audio else ".mp4")
    temp_file = str(config.download_path / f"rec_{uuid.uuid4().hex[:8]}{ext}")

    try:
        await message.bot.download(media_obj, destination=temp_file)
        track = await music_service.recognize_audio(temp_file)
        safe_remove_file(temp_file)

        if not track:
            fail_text = (
                "😔 <b>Afsuski, ushbu audio orqali qo'shiqni aniqlab bo'lmadi.</b>\n\n"
                "💡 <b>Maslahatlar:</b>\n"
                "• Qo'shiq balandroq va shovqinsiz eshitilayotgan joyini yuboring (kamida 5-10 soniya)\n"
                "• Yoki <b>«🎵 Qo'shiq topish»</b> tugmasi orqali nomini yozing."
            )
            await status_msg.edit_text(fail_text, parse_mode="HTML")
            return

        # Natijani keshga saqlash
        user_id = message.from_user.id
        track_key = f"{user_id}_{track['id']}"
        _SEARCH_CACHE[track_key] = track

        title = track.get("title", "Noma'lum")
        artist = track.get("artist", "Noma'lum")
        genre = track.get("genre", "Musiqa")
        cover_url = track.get("cover")

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=f"📥 «{artist} - {title}» MP3 yuklash",
                callback_data=f"dl_track:{track_key}"
            )
        )
        builder.row(
            InlineKeyboardButton(text=f"🍿 {config.CHANNEL_USERNAME}", url=f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}")
        )

        caption = (
            "🎉 <b>Qo'shiq muvaffaqiyatli aniqlandi!</b>\n\n"
            f"🎵 <b>Nomi:</b> {title}\n"
            f"👤 <b>Ijrochi:</b> {artist}\n"
            f"🎭 <b>Janr:</b> {genre}\n\n"
            "To'liq MP3 formatida yuklab olish uchun quyidagi tugmani bosing: 👇"
        )

        try:
            await status_msg.delete()
        except Exception:
            pass

        if cover_url:
            try:
                await message.reply_photo(
                    photo=cover_url,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
                return
            except Exception:
                pass

        await message.reply(caption, parse_mode="HTML", reply_markup=builder.as_markup())

    except Exception as e:
        logger.exception(f"Audio aniqlashda kutilmagan xatolik: {e}")
        safe_remove_file(temp_file)
        try:
            await status_msg.edit_text("❌ Qo'shiqni aniqlash jarayonida texnik xatolik yuz berdi.", parse_mode="HTML")
        except Exception:
            pass


@router.callback_query(F.data.startswith("dl_track:"))
async def cb_download_track(callback: CallbackQuery) -> None:
    """Tanlangan qo'shiqni yuklab berish."""
    track_key = callback.data.split("dl_track:")[-1]
    track_data = _SEARCH_CACHE.get(track_key)

    if not track_data:
        track_id_part = track_key.split("_")[-1]
        if track_id_part.isdigit():
            try:
                import aiohttp
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(f"https://api.deezer.com/track/{track_id_part}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            dz_info = await resp.json()
                            track_data = {
                                "id": track_id_part,
                                "title": dz_info.get("title_short", dz_info.get("title", "Musiqa")),
                                "artist": dz_info.get("artist", {}).get("name", "Noma'lum"),
                                "preview": dz_info.get("preview"),
                                "duration": dz_info.get("duration", 0),
                            }
                            _SEARCH_CACHE[track_key] = track_data
            except Exception:
                pass
        elif "tarona" in track_key:
            try:
                song_part = track_key.split("tarona_")[-1]
                t_results = await music_service._search_tarona(song_part, limit=1)
                if t_results:
                    track_data = t_results[0]
                    _SEARCH_CACHE[track_key] = track_data
            except Exception:
                pass

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
        res = await music_service.download_track_mp3(full_search_query, track_info=track_data)

        if not res.success or not res.file_path:
            # Agar fayl sifatida yuklab bo'lmasa, lekin preview havolasi mavjud bo'lsa
            preview_url = track_data.get("preview") or track_data.get("u")
            if preview_url:
                caption = (
                    f"🎵 <b>{artist} - {title}</b>\n\n"
                    f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yuklandi</b>\n"
                    f"🍿 <b>Kinolar kanalimiz:</b> {config.CHANNEL_USERNAME}"
                )
                await callback.message.reply_audio(
                    audio=preview_url,
                    title=title,
                    performer=artist or f"@{config.BOT_USERNAME.lstrip('@')}",
                    caption=caption,
                    parse_mode="HTML"
                )
                try:
                    await status_msg.delete()
                except Exception:
                    pass
                return

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
