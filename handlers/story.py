"""
Anonim Telegram va Instagram Story ko'rish bo'limi
"""
import logging
import html
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from services.story_service import story_service
from keyboards.default import cancel_keyboard, main_menu_keyboard
from keyboards.inline import story_platform_keyboard
from utils.states import StoryStates
from utils.helpers import safe_remove_file

logger = logging.getLogger(__name__)
router = Router(name="story_router")


@router.message(Command("story"))
@router.message(F.text == "👀 Anonim story")
async def cmd_story_prompt(message: Message, state: FSMContext) -> None:
    await state.clear()
    from services.maintenance_service import maintenance_service
    from keyboards.default import maintenance_menu_keyboard
    if not config.is_admin(message.from_user.id) and (maintenance_service.is_global_maintenance() or maintenance_service.is_page_maintenance("story")):
        msg = maintenance_service.get_page_message("story") if maintenance_service.is_page_maintenance("story") else maintenance_service.get_global_message()
        await message.answer(
            f"👻 <b>{msg}</b>\n\n<i>Story bo'limida texnik yangilanish olib borilmoqda. Tez orada qaytamiz!</i>",
            parse_mode="HTML",
            reply_markup=maintenance_menu_keyboard(is_admin=False)
        )
        return
    text = (
        "👀 <b>Anonim Story ko'rish va yuklash!</b>\n\n"
        "Qaysi ijtimoiy tarmoqdagi hikoyalarni (stories) ko'rmoqchisiz? Tanlang:\n\n"
        "✈️ <b>Telegram Story</b> — Telegram kanal yoki profil hikoyalari\n"
        "📸 <b>Instagram Story</b> — Ochiq Instagram profil hikoyalari\n\n"
        "🔒 <b>To'liq anonim:</b> Profil egasi siz uning hikoyasini ko'rganingizni bilmaydi.\n"
        "⚡️ <b>Tezkor yuklash:</b> Rasm va video formatidagi barcha faol hikoyalar yetkaziladi."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=story_platform_keyboard())


@router.callback_query(F.data.startswith("story_platform:"))
async def cb_story_platform(callback: CallbackQuery, state: FSMContext) -> None:
    """Telegram yoki Instagram platformasi tanlanganda."""
    plat = callback.data.split(":")[1]
    await state.set_state(StoryStates.waiting_for_username)
    await state.update_data(platform=plat)

    if plat == "tg":
        text = (
            "✈️ <b>Anonim Telegram Story yuklash!</b>\n\n"
            "Telegram kanal yoki foydalanuvchi nomini yozing:\n"
            "<i>Masalan: <code>kunuz</code>, <code>@durov</code> yoki <code>https://t.me/kunuz</code></i>\n\n"
            "🔒 <b>To'liq anonim:</b> Kanal yoki profil egasi bilmaydi.\n"
            "⚠️ <b>Eslatma:</b> Kanal yoki profil ochiq (public) bo'lishi kerak."
        )
    else:
        text = (
            "📸 <b>Anonim Instagram Story yuklash!</b>\n\n"
            "Instagram foydalanuvchi nomini yoki profil havolasini yozing:\n"
            "<i>Masalan: <code>cristiano</code> yoki <code>@leomessi</code></i>\n\n"
            "🔒 <b>To'liq anonim:</b> Profil egasi bilmaydi.\n"
            "⚠️ <b>Diqqat:</b> Profil ochiq (public) bo'lishi va faol hikoyalar mavjud bo'lishi shart."
        )

    await callback.message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(StoryStates.waiting_for_username, F.text)
async def state_process_story_username(message: Message, state: FSMContext) -> None:
    """Kiritilgan username yoki story havolasi bo'yicha story yuklash."""
    raw_input = message.text.strip()
    state_data = await state.get_data()
    selected_platform = state_data.get("platform", "ig")

    is_tg = (
        selected_platform == "tg"
        or "t.me/" in raw_input
        or "telegram.me/" in raw_input
    )
    is_ig = (
        selected_platform == "ig"
        or "instagram.com" in raw_input
    )

    is_url = "instagram.com" in raw_input or "t.me" in raw_input
    username = story_service.clean_username(raw_input)
    if not username and not is_url:
        await message.reply("❌ Noto'g'ri username yoki havola kiritildi. Qaytadan urinib ko'ring.")
        return

    plat_title = "Telegram" if is_tg else "Instagram"
    display_name = f"@{username}" if username else "Ko'rsatilgan profil"
    safe_display = html.escape(display_name)
    status_msg = await message.reply(
        f"⏳ <b>{safe_display} {plat_title} hikoyalari yuklanmoqda...</b>\n<i>Iltimos, kuting...</i>",
        parse_mode="HTML"
    )

    try:
        target_param = raw_input if is_url else username
        plat_code = "tg" if is_tg else "ig"
        results = await story_service.fetch_stories(target_param, limit=5, platform=plat_code)
        # Faqat muvaffaqiyatli yuklangan fayllarni olish
        valid_results = [r for r in results if r.success and r.file_path and Path(r.file_path).exists()]

        if not valid_results:
            error_reason = ""
            for r in results:
                if not r.success and r.error:
                    error_reason = str(r.error)
                    break

            reason_text = f"\n\n<b>Xatolik tafsiloti:</b>\n{html.escape(error_reason)}" if error_reason else ""
            await status_msg.edit_text(
                f"❌ <b>{safe_display} profilida faol {plat_title} hikoyalari topilmadi.</b>{reason_text}\n\n"
                "Mumkin bo'lgan sabablar:\n"
                "• Hozirda hech qanday hikoya (story) mavjud emas\n"
                "• Profil yopiq (shaxsiy / private hisob)\n"
                "• Foydalanuvchi nomi yoki havola noto'g'ri kiritilgan",
                parse_mode="HTML"
            )
            await state.clear()
            return

        safe_user = html.escape(username or "user")
        caption = (
            f"👀 <b>@{safe_user} ning yangi {plat_title} hikoyasi/videosi</b>\n\n"
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
                platform="telegram_story" if is_tg else "instagram_story",
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
