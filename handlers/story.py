"""
Anonim Instagram Story ko'rish bo'limi
"""
import logging
from pathlib import Path
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
        "⚡️ <b>Tezkor yuklash:</b> Rasm va video formatidagi barcha faol hikoyalar yetkaziladi.\n"
        "⚠️ <b>Diqqat:</b> Profil ochiq (public) bo'lishi va faol hikoyalar mavjud bo'lishi shart."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(StoryStates.waiting_for_username, F.text)
async def state_process_story_username(message: Message, state: FSMContext) -> None:
    """Kiritilgan username yoki story havolasi bo'yicha story yuklash."""
    raw_input = message.text.strip()
    is_url = "instagram.com" in raw_input or "t.me" in raw_input
    username = story_service.clean_username(raw_input)
    if not username and not is_url:
        await message.reply("❌ Noto'g'ri username yoki havola kiritildi. Qaytadan urinib ko'ring.")
        return

    display_name = f"@{username}" if username else "Ko'rsatilgan profil"
    status_msg = await message.reply(
        f"⏳ <b>{display_name} hikoyalari yuklanmoqda...</b>\n<i>Iltimos, kuting...</i>",
        parse_mode="HTML"
    )

    try:
        target_param = raw_input if is_url else username
        results = await story_service.fetch_stories(target_param, limit=5)
        # Faqat muvaffaqiyatli yuklangan fayllarni olish
        valid_results = [r for r in results if r.success and r.file_path and Path(r.file_path).exists()]

        # Agar to'g'ridan-to'g'ri yuklangan fayllar bo'lmasa, keshdagi ommaviy story oqimlarini tekshirish
        if not valid_results and username:
            cached_prof = story_service._profile_cache.get(username)
            if cached_prof and cached_prof.get("items"):
                for it in cached_prof["items"][:3]:
                    m_url = it.get("u")
                    if m_url and str(m_url).startswith("http"):
                        caption = (
                            f"👀 <b>@{username} ning hikoyasi</b>\n\n"
                            f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yuklandi</b>\n"
                            f"🍿 <b>Kinolar:</b> {config.CHANNEL_USERNAME}"
                        )
                        try:
                            if it.get("k") == "video":
                                await message.reply_video(video=m_url, caption=caption, parse_mode="HTML")
                            else:
                                await message.reply_photo(photo=m_url, caption=caption, parse_mode="HTML")
                            valid_results.append(m_url)
                        except Exception:
                            pass

        if not valid_results:
            await status_msg.edit_text(
                f"❌ <b>{display_name} profilida faol hikoyalar topilmadi.</b>\n\n"
                "Mumkin bo'lgan sabablar:\n"
                "• Foydalanuvchi hozirda hech qanday story joylamagan\n"
                "• Profil yopiq (shaxsiy / private)\n"
                "• Foydalanuvchi nomi xato kiritilgan",
                parse_mode="HTML"
            )
            await state.clear()
            return

        caption = (
            f"👀 <b>@{username} ning yangi videosi/hikoyasi</b>\n\n"
            f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yuklandi</b>\n"
            f"🍿 <b>Kinolar:</b> {config.CHANNEL_USERNAME}"
        )

        for res in valid_results:
            media_file = FSInputFile(res.file_path)
            ext = Path(res.file_path).suffix.lower()
            if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                await message.reply_photo(
                    photo=media_file,
                    caption=caption,
                    parse_mode="HTML"
                )
            else:
                await message.reply_video(
                    video=media_file,
                    caption=caption,
                    duration=res.duration,
                    parse_mode="HTML"
                )
            safe_remove_file(res.file_path)

        try:
            await status_msg.delete()
        except Exception:
            pass

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
