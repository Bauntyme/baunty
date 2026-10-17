"""
Media yuklab olish qayta ishlovchisi (Instagram, TikTok, YouTube, Snapchat)
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from config import config
from database.session import get_session
from database import crud
from services.downloader import media_downloader
from utils.helpers import (
    extract_media_url,
    detect_platform,
    cache_url,
    get_cached_url,
    safe_remove_file,
)
from keyboards.inline import media_download_keyboard

logger = logging.getLogger(__name__)
router = Router(name="downloader_router")


@router.message(F.text == "📥 Media yuklash")
async def cmd_media_download_info(message: Message) -> None:
    """Media yuklash bo'limi ko'rsatmasi."""
    text = (
        "📥 <b>Universal Media Yuklovchi</b>\n\n"
        "Quyidagi platformalardan istalgan havolani yuboring:\n"
        "• <b>Instagram:</b> Reels, Post, Story, IGTV\n"
        "• <b>TikTok:</b> Suv belgisiz (no watermark) HD video\n"
        "• <b>YouTube:</b> Shorts va to'liq videolar\n"
        "• <b>Snapchat:</b> Spotlight va hikoyalar\n"
        "• <b>Pinterest, Facebook:</b> Videolar\n\n"
        "Shunchaki havolani shu yerga yuboring! 👇"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(lambda msg: msg.text and extract_media_url(msg.text) is not None)
async def process_media_url(message: Message) -> None:
    """Xabarda media havolasi aniqlanganda yuklab olish."""
    url = extract_media_url(message.text)
    if not url:
        return

    platform_name = detect_platform(url)
    status_msg = await message.reply(
        f"⏳ <b>{platform_name} dan media yuklanmoqda...</b>\n<i>Iltimos, ozgina kuting...</i>",
        parse_mode="HTML"
    )

    try:
        # Asinxron yuklab olish
        result = await media_downloader.download_video(url)

        if not result.success:
            err = result.error or "Havolani yuklab bo'lmadi."
            await status_msg.edit_text(
                f"❌ <b>Yuklab olishda xatolik:</b>\n{err}",
                parse_mode="HTML"
            )
            return

        # Token keshga saqlash (MP3 ajratish tugmasi uchun)
        cache_key = cache_url(url)
        reply_markup = media_download_keyboard(cache_key)

        caption = (
            f"🎬 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yuklandi</b>\n\n"
            f"🍿 <b>Kinolar kanalimiz:</b> {config.CHANNEL_USERNAME}"
        )

        video_file = FSInputFile(result.file_path)
        await message.reply_video(
            video=video_file,
            caption=caption,
            parse_mode="HTML",
            duration=result.duration,
            reply_markup=reply_markup
        )

        # Holat xabarini tozalash
        try:
            await status_msg.delete()
        except Exception:
            pass

        # Faylni diskdan xavfsiz o'chirish
        safe_remove_file(result.file_path)

        # Yuklash statistikasini qayd qilish
        async with get_session() as session:
            await crud.log_download(
                session=session,
                user_id=message.from_user.id,
                platform=platform_name.lower(),
                query_or_url=url
            )

    except Exception as e:
        logger.exception(f"Media yuklashda kutilmagan xatolik: {e}")
        try:
            await status_msg.edit_text(
                "❌ <b>Kechirasiz, yuklab olishda texnik xatolik yuz berdi.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("dl_audio:"))
async def process_download_audio_callback(callback: CallbackQuery) -> None:
    """Videodan MP3 musiqasini ajratib yuborish."""
    cache_key = callback.data.split("dl_audio:")[-1]
    url = get_cached_url(cache_key)

    if not url:
        await callback.answer("⚠️ Havola eskirgan yoki topilmadi. Havolani qayta yuboring.", show_alert=True)
        return

    await callback.answer("🎵 Musiqa ajratilmoqda, kuting...")
    temp_msg = await callback.message.reply("⏳ <b>Audio (MP3) ajratilmoqda...</b>", parse_mode="HTML")

    try:
        res = await media_downloader.download_audio(url)
        if not res.success or not res.file_path:
            err_msg = res.error if res.error else "Noma'lum xatolik"
            await temp_msg.edit_text(
                f"❌ <b>Audioni ajratib bo'lmadi:</b>\n{err_msg}",
                parse_mode="HTML"
            )
            return

        audio_file = FSInputFile(res.file_path)
        caption = (
            f"🎵 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yuklandi</b>\n"
            f"🍿 <b>Kinolar kanalimiz:</b> {config.CHANNEL_USERNAME}"
        )

        await callback.message.reply_audio(
            audio=audio_file,
            title=res.title or "Audio",
            performer=f"@{config.BOT_USERNAME.lstrip('@')}",
            caption=caption,
            parse_mode="HTML"
        )

        try:
            await temp_msg.delete()
        except Exception:
            pass

        safe_remove_file(res.file_path)

        async with get_session() as session:
            await crud.log_download(
                session=session,
                user_id=callback.from_user.id,
                platform="music_extract",
                query_or_url=url
            )

    except Exception as e:
        logger.exception(f"Audio ajratishda xatolik: {e}")
        try:
            await temp_msg.edit_text("❌ <b>Audio ajratishda texnik xatolik yuz berdi.</b>", parse_mode="HTML")
        except Exception:
            pass
