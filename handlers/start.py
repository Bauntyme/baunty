"""
Boshlang'ich komandalar va umumiy tugmalar (/start, /help, obuna tekshiruvi)
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from keyboards.default import main_menu_keyboard
from keyboards.inline import subscription_keyboard
from middlewares.subscription import ALLOWED_STATUSES
from services.movie_service import movie_service
from utils.helpers import format_movie_not_found

logger = logging.getLogger(__name__)
router = Router(name="start_router")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """/start komandasi va Deep Link qayta ishlovchisi."""
    await state.clear()
    user = message.from_user
    if not user:
        return

    is_admin = config.is_admin(user.id)

    # Foydalanuvchini bazaga kiritish / yangilash
    async with get_session() as session:
        db_user, created = await crud.get_or_create_user(
            session=session,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_admin=is_admin,
        )

        if db_user.is_banned:
            await message.answer("⛔ <b>Kechirasiz, siz botdan foydalanish uchun bloklangansiz.</b>", parse_mode="HTML")
            return

    # Deep linking tekshiruvi (masalan: /start movie_123)
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("movie_"):
        movie_code = args[1].replace("movie_", "").strip()
        async with get_session() as session:
            movie = await movie_service.find_by_code(session, movie_code)
            if movie:
                await movie_service.send_movie_to_user(
                    bot=message.bot,
                    chat_id=message.chat.id,
                    movie=movie,
                    session=session,
                    reply_to_message_id=message.message_id
                )
                return
            else:
                await message.answer(format_movie_not_found(movie_code), parse_mode="HTML")
                return

    welcome_text = (
        f"👋 <b>Assalomu alaykum, {user.first_name or 'qadrdon'}!</b>\n\n"
        f"🤖 <b>Zakirovsfilms_bot</b> ga xush kelibsiz!\n\n"
        "Men quyidagi imkoniyatlarga egaman:\n"
        "📥 <b>Media yuklash:</b> Instagram, TikTok, YouTube, Snapchat (suv belgisiz)\n"
        "🎬 <b>Kino:</b> Kod orqali tezkor topish va yuklab olish\n"
        "🎵 <b>Qo'shiq topish:</b> Nom yoki ijrochi bo'yicha MP3 yuklash\n"
        "👀 <b>Anonim story:</b> Instagram hikoyalarini sezdirmasdan ko'rish\n\n"
        f"🍿 <b>Barcha sara kinolar:</b> {config.CHANNEL_USERNAME}\n\n"
        "Quyidagi tugmalardan birini tanlang yoki to'g'ridan-to'g'ri havola/kino kodini yuboring! 👇"
    )

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin)
    )


@router.callback_query(F.data == "check_subscription")
async def callback_check_subscription(callback: CallbackQuery, state: FSMContext) -> None:
    """Majburiy obuna tekshirish tugmasi."""
    user = callback.from_user
    bot = callback.bot

    async with get_session() as session:
        channels = await crud.get_active_sponsor_channels(session)

    if not channels:
        await callback.answer("✅ Siz barcha kanallarga a'zo bo'lgansiz!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "🎉 <b>Rahmat! Endi botdan to'liq foydalanishingiz mumkin.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(user.id))
        )
        return

    unsubscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch.channel_id, user_id=user.id)
            from middlewares.subscription import ALLOWED_STATUSES
            if member.status not in ALLOWED_STATUSES:
                unsubscribed.append(ch)
        except Exception as e:
            logger.warning(f"Kanal tekshirishda xatolik: {e}")

    if unsubscribed:
        await callback.answer("⚠️ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=subscription_keyboard(unsubscribed))
        except Exception:
            pass
    else:
        await callback.answer("✅ Obuna muvaffaqiyatli tasdiqlandi!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "🎉 <b>Ajoyib! Obunangiz tasdiqlandi.</b>\nMarhamat, bot imkoniyatlaridan to'liq foydalanishingiz mumkin!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(user.id))
        )


@router.message(F.text == "ℹ️ Bot haqida")
@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Bot haqida ma'lumot va yordam."""
    help_text = (
        "📖 <b>Botdan foydalanish bo'yicha qo'llanma:</b>\n\n"
        "1️⃣ <b>Media yuklash:</b>\n"
        "• Instagram (Reels, Post, Story), TikTok (suv belgisiz), YouTube (Shorts/Video) yoki Snapchat havolasini shunchaki botga yuboring.\n"
        "• Bot videoni va uning musiqasini (MP3) ajratib beradi.\n\n"
        "2️⃣ <b>Kinolarni topish:</b>\n"
        "• Shunchaki kino kodini (masalan: <code>101</code>) yuboring.\n"
        f"• Eng yangi kinolar va ularning kodlari: {config.CHANNEL_USERNAME}\n\n"
        "3️⃣ <b>Qo'shiq topish:</b>\n"
        "• <b>«🎵 Qo'shiq topish»</b> tugmasini bosing va qo'shiq nomi yoki ijrochini yozing.\n\n"
        "4️⃣ <b>Anonim Instagram story:</b>\n"
        "• <b>«👀 Anonim story»</b> tugmasini bosing va Instagram username kiriting.\n\n"
        f"🤝 Hamkorlik va savollar uchun: {config.CHANNEL_USERNAME}"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(F.text.startswith("🍿"))
async def cmd_kino_channel(message: Message) -> None:
    """Kinolar kanali haqida xabar."""
    channel_clean = config.CHANNEL_USERNAME.lstrip("@")
    text = (
        f"🍿 <b>Bizning rasmiy kinolar kanalimiz:</b>\n\n"
        f"👉 <a href='https://t.me/{channel_clean}'>{config.CHANNEL_USERNAME}</a>\n\n"
        "Kanalimizda har kuni eng yangi tarjima kinolar, premyeralar va ularning maxsus bot kodlari joylab boriladi!"
    )
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)


@router.message(F.text.in_(["❌ Bekor qilish", "🔙 Bosh menyu", "🔙 Orqaga"]))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Amalni bekor qilish va bosh menyuga qaytish."""
    await state.clear()
    user = message.from_user
    is_admin = config.is_admin(user.id) if user else False
    await message.answer(
        "🏠 <b>Bosh menyu:</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin)
    )
