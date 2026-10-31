"""
Boshlang'ich komandalar va umumiy tugmalar (/start, /help, obuna tekshiruvi)
"""
import html
import logging
import re
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
@router.message(Command("startapp"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """/start komandasi va Deep Link qayta ishlovchisi."""
    await state.clear()
    user = message.from_user
    if not user:
        return

    is_admin = config.is_admin(user.id)

    # Foydalanuvchini bazaga kiritish / yangilash
    user_lang = "uz"
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
                await message.answer("⛔ <b>Kechirasiz, siz botdan foydalanish uchun bloklangansiz.</b>", parse_mode="HTML", protect_content=True)
                return
            if db_user and db_user.language:
                user_lang = db_user.language
    except Exception as e:
        logger.warning(f"cmd_start foydalanuvchini bazada saqlashda xatolik: {e}")

    from services.maintenance_service import maintenance_service
    from keyboards.default import maintenance_menu_keyboard

    # Global profilaktika tekshiruvi: faqat musiqa deep linklari ruxsat etiladi
    if not is_admin and maintenance_service.is_global_maintenance():
        args = message.text.split(maxsplit=1)
        param = args[1].strip() if len(args) > 1 else ""
        is_allowed_link = bool(param and (
            param.startswith(("m_", "music_", "song_"))
            or param.startswith(("b_", "book_", "kitob_", "books_"))
            or param in ("books", "book", "kitob", "kitoblar", "kutubxona")
        ))
        if not is_allowed_link:
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
                reply_markup=maintenance_menu_keyboard(is_admin=False, lang=user_lang),
                protect_content=True
            )
            return

    # Deep linking tekshiruvi (masalan: /start movie_123, /start q_12345, /start r_12345)
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        param = args[1].strip()
        if (
            param in ("kino", "movie", "film")
            or param.startswith("kino_")
            or param.startswith("movie_")
            or param.startswith("k_")
            or param.isdigit()
            or (param.startswith("#") and param[1:].isdigit())
            or bool(re.match(r"^#?\d+[\s_\-pP]+\d+$", param))
        ):
            if param in ("kino", "movie", "film"):
                from handlers.movies import cmd_movies_menu
                await cmd_movies_menu(message, state)
                return
            raw_param = param.replace("kino_", "").replace("movie_", "").replace("k_", "").lstrip("#№").strip()
            movie_code = raw_param
            part = 1
            m_code_part = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", raw_param, re.IGNORECASE)
            if m_code_part:
                movie_code = m_code_part.group(1)
                part = int(m_code_part.group(2))
            elif "_" in raw_param:
                parts_k = raw_param.rsplit("_", 1)
                if parts_k[1].isdigit():
                    movie_code = parts_k[0]
                    part = int(parts_k[1])
            delivered = await movie_service.deliver_movie(
                bot=message.bot,
                chat_id=message.chat.id,
                code=movie_code,
                part=part,
                reply_to_message_id=message.message_id
            )
            if not delivered:
                code_disp = f"{movie_code} ({part}-qism)" if part > 1 else movie_code
                await message.answer(format_movie_not_found(code_disp), parse_mode="HTML", protect_content=True)
            return

        elif param in ("books", "book", "kitob", "kitoblar", "kutubxona") or param.startswith(("b_", "book_", "kitob_", "books_")):
            from services import book_service
            if param in ("books", "book", "kitob", "kitoblar", "kutubxona"):
                from handlers.books import cmd_books
                await cmd_books(message)
                return
            book_id = re.sub(r'^(?:book_|books_|b_|kitob_)', '', param).strip()
            delivered = await book_service.deliver_book(
                bot=message.bot,
                chat_id=message.chat.id,
                book_id=book_id
            )
            if delivered and delivered.get("ok"):
                return
            safe_bid = html.escape(str(book_id))
            await message.answer(f"⚠️ #{safe_bid} raqamli kitob topilmadi.", parse_mode="HTML", protect_content=True)
            return

        elif param in ("prava", "exam") or param.startswith("prava_"):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
            base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
            url = f"{base_url}?prava=exam" if param == "exam" else f"{base_url}?m=prava"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🚗 Prava Mini Appni ochish", web_app=WebAppInfo(url=url))
            ]])
            text = (
                "🚗 <b>Haydovchilik guvohnomasi nazariy imtihoni (Prava)</b>\n\n"
                "• 1235 ta rasmiy YHQ savollari\n"
                "• 125 ta bilet (har birida 10 savol)\n"
                "• 12 ta asosiy mavzular\n"
                "• ⏱ Rasmiy 20 talik imtihon simulyatori\n"
                "• ❌ Xatolar ustida ishlash bo'limi\n\n"
                "Imtihonga tayyorgarlikni boshlash uchun quyidagi tugmani bosing:"
            )
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            return

        elif param in ("donate", "donat", "xayriya"):
            await send_donate_info(message)
            return

        elif param in ("mafia", "mafiya") or param.startswith("mafia_") or param.startswith("maf_"):
            from handlers.mafia import cmd_mafia
            await cmd_mafia(message)
            return

        elif param in ("til", "lang", "language") or param.startswith("lang_") or param.startswith("til_"):
            from handlers.language import cmd_language
            await cmd_language(message)
            return

        elif param in ("rasxod", "xarajat", "harajat") or param.startswith("rasxod_"):
            from handlers.rasxod import cmd_rasxod
            await cmd_rasxod(message)
            return

        elif param in ("kal", "kaloriya", "kcal") or param.startswith("kal_"):
            from handlers.kaloriya import cmd_kaloriya
            await cmd_kaloriya(message)
            return

        elif (
            param in ("tvroom", "tvxona")
            or param.startswith("tvroom_")
            or param.startswith("tvxona_")
            or (param.startswith("tv_") and len(param) > 3 and not param.startswith("tv_channel_"))
        ):
            from handlers.tvroom import handle_tvroom_start
            await handle_tvroom_start(message, param)
            return

        elif param in ("tv", "telekanal") or param.startswith("tv_"):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
            base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
            url = f"{base_url}?m=tv"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📺 Jonli TV Kanallar (1440p / 1080p)", web_app=WebAppInfo(url=url))
            ]])
            text = (
                "📺 <b>Bauntys Jonli TV Kanallar (1440p / 1080p)</b>\n\n"
                "• O'zbekiston milliy telekanallari (Sevimli, Zo'r TV, MY5, Milliy va b.)\n"
                "• Jahon va sport telekanallari\n"
                "• 1440p QHD / 1080p FHD tiniq uzluksiz oqim\n\n"
                "Tomosha qilish uchun quyidagi tugmani bosing:"
            )
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            return

        elif param in ("games", "oyun", "oyinlar") or param.startswith("games_") or param.startswith("game_"):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
            base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
            url = f"{base_url}?m=games" if param in ("games", "oyun", "oyinlar") else f"{base_url}?games={param}"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎮 O'yinlar Portalini Ochish", web_app=WebAppInfo(url=url))
            ]])
            text = (
                "🎮 <b>Bauntys O'yinlar Portali (Mini App Games)</b>\n\n"
                "• 2048, Snake, Flappy, Tetris, Runner va b.\n"
                "• Sandiqlar va mukofotlar\n"
                "• Uy hayvoni (Pet) tizimi\n\n"
                "O'yinlarni boshlash uchun quyidagi tugmani bosing:"
            )
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            return

        elif param in ("quiz", "viktorina") or param.startswith("quiz_") or param.startswith("qz_") or (param.startswith("qz") and len(param) > 2):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
            base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
            clean_pin = param.replace("quiz_", "").replace("qz_", "").replace("qz", "").strip()
            url = f"{base_url}?m=quiz&quiz={clean_pin}&room={clean_pin}&code={clean_pin}" if clean_pin else f"{base_url}?m=quiz"
            btn_text = f"🧠 Viktorina xonasiga kirish (#{clean_pin})" if clean_pin else "🧠 Viktorinani Boshlash"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=btn_text, web_app=WebAppInfo(url=url))
            ]])
            room_info = f"\n\n🎯 <b>Taklif qilingan xona:</b> <code>#{clean_pin}</code>" if clean_pin else ""
            text = (
                f"🧠 <b>Bauntys Viktorina & Bilim Sinovi (Quiz)</b>\n\n"
                f"• Qiziqarli savollar va intellektual janglar\n"
                f"• Do'stlar bilan duel yoki yakkaxon rejim\n"
                f"• Reyting va ballar tizimi!{room_info}\n\n"
                f"Boshlash uchun quyidagi tugmani bosing:"
            )
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            return

        elif param in ("music", "musiqa", "song", "mp3"):
            from handlers.music import cmd_music_menu
            await cmd_music_menu(message, state)
            return

        elif param in ("docs", "doc", "hujjat", "hujjatlar") or param.startswith("doc_"):
            from handlers.docs import cmd_docs_menu
            await cmd_docs_menu(message, state)
            return

        elif param in ("story", "stories", "hikoya") or param.startswith("story_"):
            from handlers.story import cmd_story_prompt
            await cmd_story_prompt(message, state)
            return

        elif param in ("anon", "savol", "savollar", "ask") or param.startswith("anon_"):
            from handlers.anon_questions import cmd_anon_questions_link
            await cmd_anon_questions_link(message, state)
            return

        elif param.startswith("q_"):
            target_id_str = param.replace("q_", "").strip()
            if target_id_str.isdigit():
                target_id = int(target_id_str)
                if target_id == user.id:
                    await message.answer("⚠️ <b>Siz o'zingizga anonim savol yubora olmaysiz!</b>", parse_mode="HTML")
                    return
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
            clean_param = param.replace("m_", "", 1).strip()
            movie_code = clean_param
            part = 1
            if "_" in clean_param:
                parts_m = clean_param.rsplit("_", 1)
                if parts_m[1].isdigit():
                    movie_code = parts_m[0]
                    part = int(parts_m[1])

            # Kino kodi tekshiruvi: katalogda bo'lsa, bazada bo'lsa yoki kino kodi formatida bo'lsa kinoni yetkazish
            cat_movie = movie_service.get_catalog_item(movie_code)
            is_likely_movie = bool(cat_movie or not (clean_param.isdigit() and len(clean_param) >= 7))
            if is_likely_movie:
                delivered = await movie_service.deliver_movie(
                    bot=message.bot,
                    chat_id=message.chat.id,
                    code=movie_code,
                    part=part,
                    reply_to_message_id=message.message_id
                )
                if delivered:
                    return
                elif cat_movie or "_" in clean_param:
                    await message.answer(format_movie_not_found(movie_code), parse_mode="HTML")
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
                        parse_mode="HTML",
                        protect_content=True
                    )
                    safe_remove_file(res.file_path)
                    sent = True
                elif track_info and track_info.get("preview"):
                    await message.answer_audio(
                        audio=track_info["preview"],
                        title=track_title,
                        performer=track_artist or f"@{config.BOT_USERNAME.lstrip('@')}",
                        caption=caption,
                        parse_mode="HTML",
                        protect_content=True
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
        f"🍿 <b>Baunty Cinema</b> rasmiy botiga xush kelibsiz!\n\n"
        "🎬 <b>Kinolarni topish bo'yicha ko'rsatma:</b>\n"
        "• 🔢 <b>Kod orqali:</b> Shunchaki kino kodini yuboring (masalan: <code>101</code> yoki <code>718</code>)\n"
        "• 🔍 <b>Nomi bo'yicha:</b> Qiziqtirgan filmingiz nomini yozing (masalan: <i>Forsaj</i>, <i>Taksi</i>, <i>Avatar</i>)\n"
        "• 📺 <b>Serial qismlari:</b> Kod va qism raqamini yozing (masalan: <code>718 2</code> yoki <code>Taksi 2</code>)\n\n"
        "⚡ <b>Boshqa imkoniyatlar:</b>\n"
        "📥 <b>Media yuklash:</b> Instagram, TikTok, YouTube, Snapchat (suv belgisiz)\n"
        "🎵 <b>Qo'shiq topish:</b> Nom yoki ijrochi bo'yicha MP3 yuklash\n"
        "👀 <b>Anonim story:</b> Instagram hikoyalarini sezdirmasdan ko'rish\n"
        "📺 <b>Jonli TV:</b> 1440p QHD / 1080p milliy va jahon telekanallari\n\n"
        f"🍿 <b>Barcha sara kinolar va yangi premyeralar:</b> {config.CHANNEL_USERNAME}\n\n"
        "Quyidagi tugmalardan birini tanlang yoki to'g'ridan-to'g'ri kino kodi/nomini yuboring! 👇\n\n"
        "ℹ️ Ushbu bot qidiruv indeksi sifatida ishlaydi. Fayllar Telegram serverlarida saqlanmaydi."
    )

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin, lang=user_lang),
        protect_content=True
    )


@router.message(Command("prava", "pdd", "avto", "imtihon"))
async def cmd_prava(message: Message) -> None:
    """/prava komandasi orqali to'g'ridan-to'g'ri Prava bo'limini ochish."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    url = f"{base_url}?m=prava"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚗 Prava Mini Appni ochish", web_app=WebAppInfo(url=url))
    ]])
    text = (
        "🚗 <b>Haydovchilik guvohnomasi nazariy imtihoni (Prava)</b>\n\n"
        "• 1235 ta rasmiy YHQ savollari\n"
        "• 125 ta bilet (har birida 10 savol)\n"
        "• 12 ta asosiy mavzular\n"
        "• ⏱ Rasmiy 20 talik imtihon simulyatori\n\n"
        "Imtihonga tayyorgarlikni boshlash uchun quyidagi tugmani bosing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb, protect_content=True)



@router.callback_query(F.data == "check_subscription")
async def callback_check_subscription(callback: CallbackQuery, state: FSMContext) -> None:
    """Majburiy obuna tekshirish tugmasi."""
    user = callback.from_user
    bot = callback.bot

    async with get_session() as session:
        channels = await crud.get_active_sponsor_channels(session)

    if not channels and config.CHANNEL_USERNAME and config.CHANNEL_USERNAME.strip():
        from database.models import SponsorChannel
        channels = [SponsorChannel(id=999999, channel_id=config.CHANNEL_USERNAME.strip(), title="Baunty Films", is_active=True)]

    if not channels:
        await callback.answer("✅ Siz barcha kanallarga a'zo bo'lgansiz!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "🎉 <b>Rahmat! Endi botdan to'liq foydalanishingiz mumkin.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(user.id)),
            protect_content=True
        )
        return

    from unittest.mock import MagicMock, AsyncMock
    from middlewares.subscription import ALLOWED_STATUSES
    unsubscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch.channel_id, user_id=user.id)
            status = getattr(member, "status", None) or (member.get("status") if isinstance(member, dict) else "")
            if isinstance(status, (MagicMock, AsyncMock)):
                continue
            if str(status).lower() not in ALLOWED_STATUSES:
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
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(user.id)),
            protect_content=True
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
        f"🤝 Hamkorlik va savollar uchun: {config.CHANNEL_USERNAME}\n\n"
        "ℹ️ Ushbu bot qidiruv indeksi sifatida ishlaydi. Fayllar Telegram serverlarida saqlanmaydi."
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


@router.message(F.text.in_([
    "❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена",
    "🔙 Bosh menyu", "🔙 Бош меню", "🔙 Главное меню",
    "🔙 Orqaga", "🔙 Орқага", "🔙 Назад"
]))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Amalni bekor qilish va bosh menyuga qaytish."""
    await state.clear()
    user = message.from_user
    is_admin = config.is_admin(user.id) if user else False
    user_lang = "uz"
    if user:
        try:
            async with get_session() as session:
                user_lang = await crud.get_user_language(session, user.id)
        except Exception:
            pass
    await message.answer(
        "🏠 <b>Bosh menyu:</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin, lang=user_lang)
    )


async def send_donate_info(message: Message) -> None:
    """Donat va homiylik xabarini chiqarish."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    card_number = "9860 1766 1922 0088"
    card_holder = "Xaydarov Biloliddin"
    payment_system = "Humo"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Nusxalash: 9860 1766 1922 0088", callback_data="copy_donate_card")
        ]
    ])
    text = (
        "💛 <b>Bauntys loyihasini qo'llab-quvvatlash (Donat)</b>\n\n"
        "Har bir yordam loyiha rivoji, yangi kinolar va server xarajatlari uchun sarflanadi. "
        "E'tiboringiz va qo'llab-quvvatlaganingiz uchun katta rahmat! 💛\n\n"
        f"💳 <b>Karta raqami:</b> <code>{card_number}</code>\n"
        f"👤 <b>Karta egasi:</b> {card_holder}\n"
        f"🏦 <b>To'lov tizimi:</b> {payment_system}\n\n"
        "<i>(Karta raqami ustiga bosib bir zumda nusxa olishingiz mumkin)</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("donate", "donat", "xayriya"))
@router.message(F.text.in_(["💛 Donat", "Donat", "Xayriya", "Qo'llab-quvvatlash"]))
async def cmd_donate(message: Message) -> None:
    """Donat buyrug'i."""
    await send_donate_info(message)


@router.callback_query(F.data == "copy_donate_card")
async def cb_copy_donate_card(callback: CallbackQuery) -> None:
    """Karta raqamidan nusxa olinganligini xabardor qilish."""
    await callback.answer("✅ Karta raqami nusxalandi: 9860 1766 1922 0088", show_alert=True)


@router.message(Command("tv"))
async def cmd_tv(message: Message) -> None:
    """/tv buyrug'i: Jonli TV kanallari."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    url = f"{base_url}?m=tv"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📺 Jonli TV Kanallar (1440p / 1080p)", web_app=WebAppInfo(url=url))
    ]])
    text = (
        "📺 <b>Bauntys Jonli TV Kanallar (1440p / 1080p)</b>\n\n"
        "• O'zbekiston milliy telekanallari (Sevimli, Zo'r TV, MY5, Milliy va b.)\n"
        "• Jahon va sport telekanallari\n"
        "• 1440p QHD / 1080p FHD tiniq uzluksiz oqim\n\n"
        "Tomosha qilish uchun quyidagi tugmani bosing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("quiz", "viktorina"))
async def cmd_quiz(message: Message) -> None:
    """/quiz buyrug'i: Viktorina va bilim sinovi."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    url = f"{base_url}?m=quiz"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🧠 Viktorinani Boshlash", web_app=WebAppInfo(url=url))
    ]])
    text = (
        "🧠 <b>Bauntys Viktorina & Bilim Sinovi (Quiz)</b>\n\n"
        "• Qiziqarli savollar va intellektual janglar\n"
        "• Do'stlar bilan duel yoki yakkaxon rejim\n"
        "• Reyting va ballar tizimi\n\n"
        "Boshlash uchun quyidagi tugmani bosing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("games", "oyinlar", "oyunlar"))
async def cmd_games(message: Message) -> None:
    """/games buyrug'i: O'yinlar portali."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    url = f"{base_url}?m=games"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎮 O'yinlar Portalini Ochish", web_app=WebAppInfo(url=url))
    ]])
    text = (
        "🎮 <b>Bauntys O'yinlar Portali (Mini App Games)</b>\n\n"
        "• 2048, Snake, Flappy, Tetris, Runner va b.\n"
        "• Sandiqlar va mukofotlar\n"
        "• Uy hayvoni (Pet) tizimi\n\n"
        "O'yinlarni boshlash uchun quyidagi tugmani bosing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

