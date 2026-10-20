"""
Musiqa bo'limi qayta ishlovchisi (Qo'shiq qidirish va MP3 yuklash)
"""
import html
import logging
from typing import Dict, Any
from aiogram import Router, F
from aiogram.filters import Command
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

import hashlib
import uuid

logger = logging.getLogger(__name__)
router = Router(name="music_router")

# Foydalanuvchi qidiruv natijalarini vaqtinchalik saqlash (xotira sizib ketishidan himoyalangan)
_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}


def _cache_track(key: str, data: Any) -> None:
    """Xotira cheklovi bilan qidiruv keshiga ma'lumot saqlash."""
    if len(_SEARCH_CACHE) > 4000:
        oldest_keys = list(_SEARCH_CACHE.keys())[:1000]
        for k in oldest_keys:
            _SEARCH_CACHE.pop(k, None)
    _SEARCH_CACHE[key] = data


@router.message(Command("music", "musiqa", "song", "mp3"))
@router.message(F.text.in_(["🎵 Qo'shiq topish", "🎵 Musiqa topish", "Qo'shiq topish", "Musiqa topish"]))
async def cmd_music_menu(message: Message, state: FSMContext) -> None:
    """Musiqa qidirish boshlanishi."""
    # Agar buyruq bilan birga so'rov ham yozilgan bo'lsa (masalan: /music Konsta, /musiqa Konsta)
    if message.text:
        text_clean = message.text.strip()
        for cmd in ["/music", "/musiqa", "/song", "/mp3"]:
            if text_clean.lower().startswith(cmd) and len(text_clean.split(maxsplit=1)) > 1:
                query = text_clean.split(maxsplit=1)[1].strip()
                await _execute_music_search(message, query, state)
                return

    await state.set_state(MusicStates.waiting_for_query)
    text = (
        "🎵 <b>Tezkor Musiqa qidirish xizmati!</b>\n\n"
        "Qidirayotgan qo'shig'ingiz nomi yoki ijrochisini yozing:\n"
        "<i>Masalan: Konsta, Jaloliddin, Phonk, Kordhell, EDM, Jah Khalib yoki Rayhon</i>\n\n"
        "⚡️ <i>Har qanday qo'shiq, phonk, remiks va xitlar 1 soniyada topiladi!</i>\n"
        "🎙️ Yoki ovozli xabar (voice) yuboring — Shazam orqali aniqlaymiz!"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(
    lambda msg: msg.text and any(
        msg.text.strip().lower().startswith(p)
        for p in ["🎵 ", "musiqa ", "qo'shiq ", "muzyka ", "trek "]
    ) and len(msg.text.strip().split(maxsplit=1)) > 1
)
async def cmd_quick_music_search(message: Message, state: FSMContext) -> None:
    """Prefixli matnli musiqa qidiruvi (masalan: 'musiqa Konsta', 'qo'shiq Rayhon')."""
    query = message.text.strip().split(maxsplit=1)[1].strip()
    await _execute_music_search(message, query, state)


async def _execute_music_search(message: Message, query: str, state: FSMContext) -> None:
    """Kengaytirilgan musiqa qidiruvi (kamida 15-30 ta natija) va sahifalash bilan."""
    status_msg = await message.reply("🔍 <b>Qo'shiqlar qidirilmoqda...</b>", parse_mode="HTML")

    try:
        # Kamida 15-30 ta natija qidirish (Deezer, Tarona, Soundcloud, iTunes parallel)
        tracks = await music_service.search_tracks(query, limit=30)
        if not tracks:
            await status_msg.edit_text(
                f"❌ <b>«{html.escape(query)}»</b> bo'yicha hech qanday qo'shiq topilmadi.\n"
                "Iltimos, nomni to'g'ri yozib qayta urinib ko'ring.",
                parse_mode="HTML"
            )
            return

        user_id = message.from_user.id
        search_id = uuid.uuid4().hex[:8]

        # Natijalarni keshga saqlash (64 bayt Telegram callback_data chekloviga to'liq moslangan)
        formatted_tracks = []
        for t in tracks:
            raw_id = str(t.get("id", ""))
            if len(raw_id) > 28:
                raw_id = hashlib.md5(raw_id.encode()).hexdigest()[:16]
            track_key = f"{user_id}_{raw_id}"
            _cache_track(track_key, t)
            formatted_tracks.append({
                "id": track_key,
                "title": t.get("title", ""),
                "artist": t.get("artist", ""),
            })

        _cache_track(f"msearch:{search_id}", {
            "user_id": user_id,
            "query": query,
            "tracks": formatted_tracks,
        })

        total_tracks = len(tracks)
        total_pages = max(1, (total_tracks + 7) // 8)
        text = (
            f"🎵 <b>«{html.escape(query)}» bo'yicha {total_tracks} ta qo'shiq topildi:</b>\n"
            f"Yuklab olmoqchi bo'lgan qo'shiqni tanlang (1-sahifa / {total_pages}):"
        )

        markup = music_results_keyboard(formatted_tracks, page=0, per_page=8, search_id=search_id)
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await state.clear()

    except Exception as e:
        logger.exception(f"Musiqa qidirishda xatolik: {e}")
        await status_msg.edit_text("❌ Musiqa qidirishda texnik xatolik yuz berdi.", parse_mode="HTML")


@router.message(MusicStates.waiting_for_query, F.text)
async def state_process_music_query(message: Message, state: FSMContext) -> None:
    """Qo'shiq so'rovi bo'yicha qidirish."""
    query = message.text.strip()
    await _execute_music_search(message, query, state)


@router.callback_query(F.data.startswith("music_page:"))
async def cb_music_page(callback: CallbackQuery) -> None:
    """Musiqa qidiruv natijalari bo'ylab inline sahifalash (Keyingi / Oldingi)."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    search_id = parts[1]
    try:
        page = int(parts[2])
    except (ValueError, TypeError):
        page = 0

    search_data = _SEARCH_CACHE.get(f"msearch:{search_id}")
    if not search_data:
        await callback.answer("⚠️ Qidiruv muddati tugagan, iltimos qaytadan qidiring.", show_alert=True)
        return

    if isinstance(search_data, list):
        formatted_tracks = search_data
        query = "Qo'shiqlar"
    else:
        formatted_tracks = search_data.get("tracks", [])
        query = search_data.get("query", "Qo'shiqlar")
    total_tracks = len(formatted_tracks)
    total_pages = max(1, (total_tracks + 7) // 8)
    page = max(0, min(page, total_pages - 1))

    text = (
        f"🎵 <b>«{html.escape(query)}» bo'yicha {total_tracks} ta qo'shiq topildi:</b>\n"
        f"Yuklab olmoqchi bo'lgan qo'shiqni tanlang ({page + 1}-sahifa / {total_pages}):"
    )
    markup = music_results_keyboard(formatted_tracks, page=page, per_page=8, search_id=search_id)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=markup)
        except Exception:
            pass

    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Sahifa ko'rsatkichi bosilganda hech narsa o'zgarmaydi."""
    await callback.answer()


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

        safe_title = html.escape(str(title))
        safe_artist = html.escape(str(artist))
        safe_genre = html.escape(str(genre))

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=f"📥 «{artist[:20]} - {title[:20]}» MP3 yuklash",
                callback_data=f"dl_track:{track_key}"
            )
        )
        builder.row(
            InlineKeyboardButton(text=f"🍿 {config.CHANNEL_USERNAME}", url=f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}")
        )

        caption = (
            "🎉 <b>Qo'shiq muvaffaqiyatli aniqlandi!</b>\n\n"
            f"🎵 <b>Nomi:</b> {safe_title}\n"
            f"👤 <b>Ijrochi:</b> {safe_artist}\n"
            f"🎭 <b>Janr:</b> {safe_genre}\n\n"
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
        if "tarona" in track_key:
            try:
                song_part = track_key.split("tarona_")[-1]
                direct_url = await music_service._resolve_tarona_direct_mp3(f"https://muzfm.uz/music/{song_part}")
                if not direct_url:
                    direct_url = await music_service._resolve_tarona_direct_mp3(f"https://muzfm.uz/index.php?newsid={song_part}")
                if direct_url:
                    track_data = {
                        "id": f"tarona_{song_part}",
                        "title": song_part.replace("-", " ").title(),
                        "artist": "Tarona Music",
                        "preview": direct_url,
                        "u": direct_url,
                        "s": "tarona",
                        "link": f"https://muzfm.uz/music/{song_part}"
                    }
                    _cache_track(track_key, track_data)
                else:
                    clean_search = song_part.replace("-", " ")
                    t_results = await music_service._search_tarona(clean_search, limit=1)
                    if t_results:
                        track_data = t_results[0]
                        _cache_track(track_key, track_data)
            except Exception:
                pass
        else:
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
                                _cache_track(track_key, track_data)
                except Exception:
                    pass

    if not track_data:
        await callback.answer("⚠️ Ma'lumot eskirgan, iltimos qaytadan qidiring.", show_alert=True)
        return

    artist = track_data.get("artist", "")
    title = track_data.get("title", "")
    full_search_query = f"{artist} - {title}"
    safe_query = html.escape(full_search_query)
    safe_title = html.escape(str(title))
    safe_artist = html.escape(str(artist))

    await callback.answer("⏳ MP3 tayyorlanmoqda...")
    status_msg = await callback.message.reply(
        f"⏳ <b>«{safe_query}» yuklanmoqda...</b>\n<i>Iltimos, kuting...</i>",
        parse_mode="HTML"
    )

    try:
        res = await music_service.download_track_mp3(full_search_query, track_info=track_data)

        if not res.success or not res.file_path:
            # Agar fayl sifatida yuklab bo'lmasa, lekin preview havolasi mavjud bo'lsa
            preview_url = track_data.get("preview") or track_data.get("u")
            if preview_url:
                send_url = str(preview_url)
                if any(x in send_url for x in ["/music/", ".html", "muzfm", "mp3uz"]):
                    resolved = await music_service._resolve_tarona_direct_mp3(send_url)
                    if resolved:
                        send_url = resolved
                    else:
                        send_url = None

                if send_url:
                    caption = (
                        f"🎵 <b>{safe_artist} - {safe_title}</b>\n\n"
                        f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yuklandi</b>\n"
                        f"🍿 <b>Kinolar kanalimiz:</b> {config.CHANNEL_USERNAME}"
                    )
                    await callback.message.reply_audio(
                        audio=send_url,
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
                f"❌ <b>Qo'shiqni yuklab bo'lmadi:</b>\n{html.escape(err_msg)}",
                parse_mode="HTML"
            )
            return

        audio_file = FSInputFile(res.file_path)
        caption = (
            f"🎵 <b>{safe_artist} - {safe_title}</b>\n\n"
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
