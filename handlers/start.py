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
    try:
        async with get_session() as session:
            db_user, created = await crud.get_or_create_user(
                session=session,
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_admin=is_admin,
            )

            if db_user and db_user.is_banned:
                await message.answer("⛔ <b>Kechirasiz, siz botdan foydalanish uchun bloklangansiz.</b>", parse_mode="HTML")
                return
    except Exception as e:
        logger.warning(f"cmd_start foydalanuvchini bazada saqlashda xatolik: {e}")

    from services.maintenance_service import maintenance_service
    from keyboards.default import maintenance_menu_keyboard

    # Global profilaktika tekshiruvi: faqat musiqa deep linklari ruxsat etiladi
    if not is_admin and maintenance_service.is_global_maintenance():
        args = message.text.split(maxsplit=1)
        param = args[1].strip() if len(args) > 1 else ""
        is_music_link = bool(param and (param.startswith("m_") or param.startswith("music_") or param.startswith("song_")))
        if not is_music_link:
            m_msg = maintenance_service.get_global_message()
            maint_text = (
                f"<b>{m_msg}</b>\n\n"
                "Botda texnik yangilanish olib borilayotgani sababli ayrim xizmatlar vaqtincha to'xtatilgan.\n\n"
                "⚡ <b>Lekin hozirda quyidagi bo'limlar to'liq va uzluksiz ishlamoqda:</b>\n"
                "• 🎵 <b>Qo'shiq topish</b> (Istalgan musiqa va ijrochini topish)\n"
                "• ⭕️ <b>Dumaloq video</b> (1 soniyada video xabar tayyorlash)\n"
                "• 📥 <b>Media yuklash</b> (Instagram, TikTok, YouTube va b.)\n\n"
                "Quyidagi tugmalardan birini tanlab foydalanishingiz mumkin:"
            )
            await message.answer(
                maint_text,
                parse_mode="HTML",
                reply_markup=maintenance_menu_keyboard(is_admin=False)
            )
            return

    # Deep linking tekshiruvi (masalan: /start movie_123, /start q_12345, /start r_12345)
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        param = args[1].strip()
        if param.startswith("kino_") or param.startswith("movie_") or param.startswith("k_"):
            movie_code = param.replace("kino_", "").replace("movie_", "").replace("k_", "").strip()
            delivered = await movie_service.deliver_movie(
                bot=message.bot,
                chat_id=message.chat.id,
                code=movie_code,
                part=1,
                reply_to_message_id=message.message_id
            )
            if not delivered:
                await message.answer(format_movie_not_found(movie_code), parse_mode="HTML")
            return

        elif param.startswith("b_") or param.startswith("book_") or param == "books":
            from services import book_service
            if param == "books":
                from handlers.books import cmd_books
                await cmd_books(message)
                return
            book_id = param.replace("book_", "").replace("b_", "").strip()
            delivered = await book_service.deliver_book(
                bot=message.bot,
                chat_id=message.chat.id,
                book_id=book_id
            )
            if delivered and delivered.get("ok"):
                return
            await message.answer(f"⚠️ #{book_id} raqamli kitob topilmadi.", parse_mode="HTML")
            return

        elif param.startswith("q_"):
            target_id_str = param.replace("q_", "").strip()
            if target_id_str.isdigit():
                target_id = int(target_id_str)
                if target_id == user.id:
                    await message.answer("⚠️ <b>Siz o'zingizga anonim savol yubora olmaysiz!</b>", parse_mode="HTML")
                else:
                    from utils.states import AnonQuestionStates
                    from keyboards.default import cancel_keyboard
                    await state.set_state(AnonQuestionStates.waiting_for_message)
                    await state.update_data(anon_target_id=target_id)
                    await message.answer(
                        "💌 <b>Foydalanuvchiga anonim xabar yozing:</b>\n\n"
                        "Sizning shaxsingiz 100% sir tutiladi va xabar egasiga oshkor qilinmaydi 🤫\n\n"
                        "Xabaringizni yozing:",
                        parse_mode="HTML",
                        reply_markup=cancel_keyboard()
                    )
                    return

        elif param.startswith("r_"):
            ref_id_str = param.replace("r_", "").strip()
            if ref_id_str.isdigit() and int(ref_id_str) != user.id:
                referrer_id = int(ref_id_str)
                async with get_session() as session:
                    added = await crud.add_referral(session, referrer_id=referrer_id, new_user_id=user.id, points=10)
                    if added:
                        try:
                            await message.bot.send_message(
                                chat_id=referrer_id,
                                text=f"🎉 <b>Tabriklaymiz!</b> Sizning taklif havolangiz orqali yangi do'stingiz ({user.first_name}) botga qo'shildi! (+10 ball)",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

        elif param.startswith("m_"):
            clean_param = param.replace("m_", "").strip()
            # Kino kodi tekshiruvi: katalogda bo'lsa, bazada bo'lsa yoki kino kodi formatida bo'lsa kinoni yetkazish
            cat_movie = movie_service.get_catalog_item(clean_param)
            is_likely_movie = bool(cat_movie or not (clean_param.isdigit() and len(clean_param) >= 7))
            if is_likely_movie:
                delivered = await movie_service.deliver_movie(
                    bot=message.bot,
                    chat_id=message.chat.id,
                    code=clean_param,
                    part=1,
                    reply_to_message_id=message.message_id
                )
                if delivered:
                    return
            music_id = clean_param
            status_msg = await message.answer("🎵 <b>Qo'shiq tayyorlanmoqda...</b>", parse_mode="HTML")
            try:
                import os
                import aiohttp
                from aiogram.types import FSInputFile
                from services.music_service import music_service
                from utils.helpers import safe_remove_file

                track_title = "Musiqa"
                track_artist = ""
                track_info = None

                # Agar Deezer track ID bo'lsa
                if music_id.isdigit():
                    try:
                        async with aiohttp.ClientSession() as sess:
                            async with sess.get(f"https://api.deezer.com/track/{music_id}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                                if resp.status == 200:
                                    dz_info = await resp.json()
                                    track_title = dz_info.get("title_short", dz_info.get("title", "Musiqa"))
                                    track_artist = dz_info.get("artist", {}).get("name", "")
                                    track_info = {
                                        "title": track_title,
                                        "artist": track_artist,
                                        "preview": dz_info.get("preview"),
                                        "duration": dz_info.get("duration", 0),
                                    }
                    except Exception as e_dz:
                        logger.warning(f"Deezer track fetch error: {e_dz}")

                query = f"{track_artist} - {track_title}".strip(" -") if track_artist else (track_title if track_title != "Musiqa" else music_id)
                res = await music_service.download_track_mp3(query, track_info=track_info)

                sent = False
                caption = (
                    f"🎵 <b>{track_artist} - {track_title}</b>\n\n"
                    f"🤖 @{config.BOT_USERNAME.lstrip('@')} orqali yuklandi\n"
                    f"🍿 {config.CHANNEL_USERNAME}"
                )

                if res.success and res.file_path and os.path.exists(res.file_path):
                    await message.answer_audio(
                        audio=FSInputFile(res.file_path),
                        title=track_title,
                        performer=track_artist or f"@{config.BOT_USERNAME.lstrip('@')}",
                        duration=res.duration,
                        caption=caption,
                        parse_mode="HTML"
                    )
                    safe_remove_file(res.file_path)
                    sent = True
                elif track_info and track_info.get("preview"):
                    await message.answer_audio(
                        audio=track_info["preview"],
                        title=track_title,
                        performer=track_artist or f"@{config.BOT_USERNAME.lstrip('@')}",
                        caption=caption,
                        parse_mode="HTML"
                    )
                    sent = True

                try:
                    await status_msg.delete()
                except Exception:
                    pass

                if not sent:
                    await message.answer(
                        f"🎵 <b>«{query}»</b> qo'shig'ini yuklab bo'lmadi.\n"
                        "«🎵 Qo'shiq topish» tugmasi orqali qidirib ko'ring.",
                        parse_mode="HTML"
                    )
                return
            except Exception as e_m:
                logger.exception(f"Deep link musiqa yuklashda xatolik: {e_m}")
                try:
                    await status_msg.edit_text("❌ Musiqani yuklashda texnik xatolik yuz berdi.", parse_mode="HTML")
                except Exception:
                    pass
                return


    welcome_text = (
        f"👋 <b>Assalomu alaykum, {user.first_name or 'qadrdon'}!</b>\n\n"
        f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')}</b> ga xush kelibsiz!\n\n"
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
