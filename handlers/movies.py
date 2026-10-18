"""
Kino bo'limi qayta ishlovchisi (Kino kodi, qidiruv, janrlar, tasodifiy kino)
"""
import logging
import math
import re
from typing import Optional, Tuple
from aiogram import Router, F
from aiogram.filters import StateFilter, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from database.models import Movie
from services.movie_service import movie_service, MovieService
from keyboards.default import cancel_keyboard, main_menu_keyboard
from keyboards.inline import (
    movie_menu_keyboard,
    genres_keyboard,
    movie_list_keyboard,
    movie_item_keyboard,
)
from utils.states import MovieSearchStates
from utils.helpers import format_movie_not_found

logger = logging.getLogger(__name__)
router = Router(name="movies_router")


@router.message(F.text.in_(["🎬 Kino", "🎬 K I N O — kod orqali qidirish"]))
async def cmd_movies_menu(message: Message, state: FSMContext) -> None:
    """Kino bo'limi asosiy menyusi."""
    await state.clear()
    text = (
        "🎬 <b>Kino olamiga xush kelibsiz!</b>\n\n"
        "Quyidagi imkoniyatlardan foydalanishingiz mumkin:\n"
        "• <b>Kino kodi:</b> Shunchaki kodni (masalan, <code>101</code>) yozing\n"
        "• <b>Nomi bo'yicha qidiruv:</b> Qiziqtirgan filmingiz nomini yozing\n"
        "• <b>Tasodifiy kino:</b> Nima ko'rishni bilmayotgan bo'lsangiz\n"
        "• <b>Janrlar:</b> Sevimli yo'nalishingizdagi filmlar\n\n"
        f"🍿 <b>Barcha premyerlar:</b> {config.CHANNEL_USERNAME}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=movie_menu_keyboard())


@router.callback_query(F.data == "movie:menu")
async def cb_movie_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Kino menyusiga qaytish callback."""
    await state.clear()
    text = (
        "🎬 <b>Kino menyusi:</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang yoki to'g'ridan-to'g'ri kino kodini yuboring:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=movie_menu_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=movie_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "movie:by_code")
async def cb_movie_by_code(callback: CallbackQuery, state: FSMContext) -> None:
    """Kod orqali qidirishni boshlash."""
    await state.set_state(MovieSearchStates.waiting_for_code)
    await callback.message.answer(
        "🔢 <b>Kino kodini kiriting:</b>\nMasalan: <code>123</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "movie:by_title")
async def cb_movie_by_title(callback: CallbackQuery, state: FSMContext) -> None:
    """Nomi bo'yicha qidirishni boshlash."""
    await state.set_state(MovieSearchStates.waiting_for_title)
    await callback.message.answer(
        "🔍 <b>Kino nomini kiriting:</b>\nMasalan: <i>Forsaj</i> yoki <i>Avatar</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "movie:random")
async def cb_movie_random(callback: CallbackQuery) -> None:
    """Tasodifiy kino yuborish."""
    await callback.answer("🎲 Tasodifiy kino tanlanmoqda...")
    async with get_session() as session:
        movie = await movie_service.get_random(session)
        if not movie:
            await callback.message.answer(
                f"😔 Bazada hali kinolar mavjud emas.\n🍿 Yangi filmlar kanalimizda: {config.CHANNEL_USERNAME}",
                parse_mode="HTML"
            )
            return

        await movie_service.send_movie_to_user(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            movie=movie,
            session=session
        )


@router.callback_query(F.data == "movie:genres")
async def cb_movie_genres(callback: CallbackQuery) -> None:
    """Janrlar ro'yxatini ko'rsatish."""
    text = "🎭 <b>O'zingizga yoqqan janrni tanlang:</b>"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=genres_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=genres_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("genre:"))
async def cb_select_genre(callback: CallbackQuery) -> None:
    """Tanlangan janr bo'yicha filmlar."""
    genre = callback.data.split("genre:")[-1]
    await callback.answer(f"🎭 {genre} janri...")

    async with get_session() as session:
        total = await movie_service.get_genre_count(session, genre)
        movies = await movie_service.get_by_genre(session, genre, limit=10, offset=0)
        if not movies:
            await callback.message.answer(
                f"😔 <b>«{genre}»</b> janrida hozircha kinolar topilmadi.\n"
                f"🍿 Barcha kinolar: {config.CHANNEL_USERNAME}",
                parse_mode="HTML"
            )
            return

        total_pages = max(1, math.ceil(total / 10))
        text = f"🎭 <b>«{genre}» janridagi kinolar (1/{total_pages}-sahifa):</b>\nKo'rmoqchi bo'lgan filmingizni tanlang:"
        markup = movie_list_keyboard(movies, page=0, total_pages=total_pages, prefix=f"genre_page:{genre}")
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("genre_page:"))
async def cb_genre_page(callback: CallbackQuery) -> None:
    """Janr bo'yicha pagination."""
    parts = callback.data.split(":")
    genre = parts[1]
    page = int(parts[2])
    await callback.answer()

    async with get_session() as session:
        total = await movie_service.get_genre_count(session, genre)
        total_pages = max(1, math.ceil(total / 10))
        movies = await movie_service.get_by_genre(session, genre, limit=10, offset=page * 10)

        if not movies:
            return

        text = f"🎭 <b>«{genre}» janridagi kinolar ({page+1}/{total_pages}-sahifa):</b>\nKo'rmoqchi bo'lgan filmingizni tanlang:"
        markup = movie_list_keyboard(movies, page=page, total_pages=total_pages, prefix=f"genre_page:{genre}")
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "movie:top")
async def cb_movie_top(callback: CallbackQuery) -> None:
    """Eng ko'p ko'rilgan kinolar ro'yxati."""
    await callback.answer("🔥 Eng ommabop kinolar...")
    async with get_session() as session:
        movies = await movie_service.get_top(session, limit=10)
        if not movies:
            await callback.message.answer(
                f"😔 Hozircha kinolar mavjud emas.\n🍿 Kanalimiz: {config.CHANNEL_USERNAME}",
                parse_mode="HTML"
            )
            return

        text = "🔥 <b>Eng ommabop va ko'p ko'rilgan kinolar:</b>"
        markup = movie_list_keyboard(movies, page=0, total_pages=1, prefix="top_page")
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("top_page:"))
async def cb_top_page(callback: CallbackQuery) -> None:
    """Top kinolar pagination."""
    await callback.answer()
    async with get_session() as session:
        movies = await movie_service.get_top(session, limit=10)
        text = "🔥 <b>Eng ommabop va ko'p ko'rilgan kinolar:</b>"
        markup = movie_list_keyboard(movies, page=0, total_pages=1, prefix="top_page")
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass



@router.callback_query(F.data.startswith("get_movie:"))
async def cb_get_movie_by_code(callback: CallbackQuery) -> None:
    """Ro'yxatdan tanlangan kinoni yuborish."""
    code = callback.data.split("get_movie:")[-1]
    await callback.answer("🎬 Kino yuklanmoqda...")
    delivered = await movie_service.deliver_movie(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        code=code,
        part=1
    )
    if not delivered:
        await callback.message.answer(format_movie_not_found(code), parse_mode="HTML")


@router.callback_query(F.data.startswith("watch_part:"))
async def cb_watch_part(callback: CallbackQuery) -> None:
    """Ko'p qismli serialda qismni tanlash."""
    parts = callback.data.split(":")
    code = parts[1]
    part = int(parts[2])
    await callback.answer(f"📺 {part}-qism yuklanmoqda...")
    await movie_service.deliver_movie(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        code=code,
        part=part
    )


@router.message(MovieSearchStates.waiting_for_code)
async def state_process_code(message: Message, state: FSMContext) -> None:
    """FSM holatida kiritilgan kodni qidirish."""
    code = message.text.strip()
    await state.clear()
    delivered = await movie_service.deliver_movie(
        bot=message.bot,
        chat_id=message.chat.id,
        code=code,
        part=1,
        reply_to_message_id=message.message_id
    )
    if not delivered:
        await message.reply(
            format_movie_not_found(code),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )


@router.message(MovieSearchStates.waiting_for_title)
async def state_process_title(message: Message, state: FSMContext) -> None:
    """FSM holatida kiritilgan nom bo'yicha qidirish."""
    title = message.text.strip()
    await state.clear()

    async with get_session() as session:
        movies = await movie_service.search_by_title(session, title, limit=10)
        if movies:
            text = f"🔍 <b>«{title}» bo'yicha topilgan kinolar:</b>\nKeraklisini tanlang:"
            markup = movie_list_keyboard(movies)
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=markup
            )
        else:
            text = (
                f"❌ <b>«{title}»</b> nomli kino bazamizda topilmadi!\n\n"
                f"🍿 Eng so'nggi kinolar kanalimizda: {config.CHANNEL_USERNAME}\n"
                "Kino nomini to'g'ri yozganingizga ishonch hosil qilib qayta urinib ko'ring."
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
            )


def extract_movie_code(text: str) -> Optional[str]:
    """
    Kino kodini matndan ajratib oladi.
    Qo'llab-quvvatlanadi: 101, #101, №101, 'kod 101', 'kod: 101', 'код 101'
    """
    if not text:
        return None
    clean = text.strip()
    if "kino — kod orqali qidirish" in clean.lower() or clean.startswith("http") or len(clean) > 30:
        return None
    cleaned = clean.lstrip("#№").lower().replace("kino", "").replace("kod", "").replace("код", "").replace(":", "").strip()
    if cleaned.isdigit() and len(cleaned) <= 10:
        return cleaned
    return None


@router.message(StateFilter(None), lambda msg: msg.text and extract_movie_code(msg.text) is not None)
async def process_numeric_movie_code(message: Message) -> None:
    """
    Foydalanuvchi faqat raqam yoki kod (masalan: 123, #123, kod 123) yuborganida avtomatik kinoni topib berish.
    """
    code = extract_movie_code(message.text)
    if not code:
        return

    delivered = await movie_service.deliver_movie(
        bot=message.bot,
        chat_id=message.chat.id,
        code=code,
        part=1,
        reply_to_message_id=message.message_id
    )
    if not delivered:
        await message.reply(format_movie_not_found(code), parse_mode="HTML")


def extract_code_from_caption(text: Optional[str]) -> Optional[str]:
    """Caption yoki matndan kino kodini aniqlash (#284, Kodi: 284, 101...)."""
    if not text:
        return None
    text_clean = text.strip()

    # 1. Kodi: #284, kod: 284, код: 284, code: 284, kino kodi: 284
    m = re.search(r'(?:kino\s*kodi|kodi?|код|kod|code)[\s:—–\-#№]*(\d+)', text_clean, re.IGNORECASE)
    if m:
        return m.group(1)

    # 2. #284 yoki №284
    m = re.search(r'[#№](\d{1,8})', text_clean)
    if m:
        return m.group(1)

    # 3. [284] yoki (284)
    m = re.search(r'[\[\(](\d{1,8})[\]\)]', text_clean)
    if m:
        return m.group(1)

    # 4. Satr boshidagi raqam: masalan "284. Zo'raki folbin" yoki "284 - Zo'raki folbin"
    for line in text_clean.split("\n"):
        line_clean = line.strip()
        m = re.match(r'^(\d{1,8})[\s\.\-—–:]', line_clean)
        if m:
            return m.group(1)
        if line_clean.isdigit() and len(line_clean) <= 8:
            return line_clean

    # 5. extract_movie_code tekshiruvi
    code = extract_movie_code(text_clean)
    if code:
        return code

    return None


def extract_candidate_title(text: Optional[str]) -> Optional[str]:
    """Captiondan kino sarlavhasi bo'lishi mumkin bo'lgan qatorni ajratish."""
    if not text:
        return None
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return None
    first_line = lines[0]
    # Emojilar va ortiqcha belgilarni tozalash
    cleaned = re.sub(r'[🎬🍿🎥📽🎞📺⭐️★#№—–\-:]', ' ', first_line)
    cleaned = re.sub(r'https?://\S+|@\w+', '', cleaned).strip()
    cleaned = re.sub(r'(?:kino\s*kodi|kodi?|код|kod|code)\s*\d+', '', cleaned, flags=re.IGNORECASE).strip()
    if len(cleaned) >= 3 and not cleaned.isdigit():
        return cleaned
    return None


def format_duration_str(seconds: Optional[int]) -> str:
    """Davomiylikni chiroyli matn shaklida ko'rsatish (masalan: 14:08 yoki 1:08:09)."""
    if not seconds:
        return "Noma'lum"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_file_size_str(size_bytes: Optional[int]) -> str:
    """Fayl hajmini MB yoki GB da ko'rsatish."""
    if not size_bytes:
        return ""
    mb = size_bytes / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


async def save_or_update_movie_video(
    session,
    code: Optional[str],
    candidate_title: Optional[str],
    file_id: str,
    file_type: str = "video",
    duration: Optional[int] = None,
    file_size: Optional[int] = None,
) -> Optional[Movie]:
    """
    Kino videosini bazadagi kinoga biriktirish yoki yangi kino sifatida saqlash.
    """
    db_movie: Optional[Movie] = None
    clean_code = str(code).strip().lstrip("#№") if code else None
    if clean_code:
        db_movie = await crud.get_movie_by_code(session, clean_code)

    if not db_movie and candidate_title:
        matches = await crud.smart_search_movies(session, candidate_title, limit=1)
        if matches:
            db_movie = matches[0]
        else:
            cat_match = MovieService.search_catalog_by_title(candidate_title)
            if cat_match:
                cat_code = str(cat_match.get("c"))
                db_movie = await crud.get_movie_by_code(session, cat_code)
                if not db_movie:
                    title = cat_match.get("t", f"Kino #{cat_code}")
                    description = cat_match.get("d", None)
                    genres = cat_match.get("g", "Barcha")
                    year = int(cat_match.get("y", 0)) if cat_match.get("y") else None
                    rating = float(cat_match.get("r", 0)) if cat_match.get("r") else None
                    db_movie = await crud.create_movie(
                        session=session,
                        code=cat_code,
                        title=title,
                        file_id=file_id,
                        description=description,
                        file_type=file_type,
                        file_size=file_size,
                        duration=duration,
                        genres=genres,
                        year=year,
                        rating=rating,
                    )

    if not db_movie and clean_code:
        cat_item = MovieService.get_catalog_item(clean_code)
        title = cat_item.get("t", f"Kino #{clean_code}") if cat_item else (candidate_title or f"Kino #{clean_code}")
        description = cat_item.get("d", None) if cat_item else None
        genres = cat_item.get("g", "Barcha") if cat_item else "Barcha"
        year = int(cat_item.get("y", 0)) if (cat_item and cat_item.get("y")) else None
        rating = float(cat_item.get("r", 0)) if (cat_item and cat_item.get("r")) else None
        db_movie = await crud.create_movie(
            session=session,
            code=clean_code,
            title=title,
            file_id=file_id,
            description=description,
            file_type=file_type,
            file_size=file_size,
            duration=duration,
            genres=genres,
            year=year,
            rating=rating,
        )
    elif db_movie:
        db_movie.file_id = file_id
        db_movie.file_type = file_type
        if duration:
            db_movie.duration = duration
        if file_size:
            db_movie.file_size = file_size

    if db_movie:
        await session.commit()
    return db_movie


@router.message(Command("setmovie", "addvideo"))
async def cmd_set_movie_video(message: Message) -> None:
    """
    Admin buyrug'i: /setmovie <kod> yoki /addvideo <kod>
    Admin ixtiyoriy video xabarga Reply qilib /setmovie 284 deb yozsa,
    o'sha videoning Telegram file_id sini avtomatik 284-kinoga biriktiradi!
    """
    user_id = message.from_user.id if message.from_user else 0
    if not config.is_admin(user_id):
        await message.reply("⛔ <b>Ushbu buyruq faqat adminlar uchun!</b>", parse_mode="HTML")
        return

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.reply(
            "⚠️ <b>Kino kodini kiriting!</b>\n"
            "Masalan: video xabarga Reply qilib <code>/setmovie 284</code> deb yozing.",
            parse_mode="HTML"
        )
        return

    raw_code = args[1].strip()
    code = extract_code_from_caption(raw_code) or raw_code.lstrip("#№")
    if not code:
        await message.reply("⚠️ Yaroqsiz kino kodi!", parse_mode="HTML")
        return

    target_msg = message.reply_to_message or message
    if not (target_msg.video or target_msg.document):
        await message.reply(
            "⚠️ <b>Video topilmadi!</b>\n"
            "Ushbu buyruqni kino videosiga Reply qilib yuboring:\n"
            f"<code>/setmovie {code}</code>",
            parse_mode="HTML"
        )
        return

    if target_msg.video:
        file_id = target_msg.video.file_id
        file_type = "video"
        duration = target_msg.video.duration
        file_size = target_msg.video.file_size
    else:
        file_id = target_msg.document.file_id
        file_type = "document"
        duration = None
        file_size = target_msg.document.file_size

    async with get_session() as session:
        db_movie = await save_or_update_movie_video(
            session=session,
            code=code,
            candidate_title=None,
            file_id=file_id,
            file_type=file_type,
            duration=duration,
            file_size=file_size,
        )

    if db_movie:
        dur_str = format_duration_str(db_movie.duration)
        size_str = format_file_size_str(db_movie.file_size)
        size_line = f"📦 <b>Hajmi:</b> {size_str}\n" if size_str else ""
        text = (
            "✅ <b>Kino videosi muvaffaqiyatli biriktirildi!</b>\n\n"
            f"🎬 <b>Nomi:</b> {db_movie.title}\n"
            f"🔢 <b>Kodi:</b> #{db_movie.code}\n"
            f"⏱ <b>Davomiyligi:</b> {dur_str}\n"
            f"{size_line}\n"
            "Endi botda yoki Web Appda ushbu kino tanlanganda to'liq MP4 video yuboriladi!"
        )
        await message.reply(text, parse_mode="HTML")
    else:
        await message.reply(f"❌ Kino #{code} ni saqlab bo'lmadi.", parse_mode="HTML")


@router.message(StateFilter(None), F.video | F.document)
async def handle_incoming_movie_video(message: Message) -> None:
    """
    Foydalanuvchi yoki admin @Zakirovsfilms_bot dan (yoki boshqa kanaldan) videoni
    forward qilib yuborganida yoki to'g'ridan-to'g'ri video tashlaganida:
    - Xabar captionidan kino kodini (#284, 284, 101...) aniqlaydi.
    - Agar kod bo'lmasa, sarlavha nomini bazadan qidiradi.
    - Agar kino topilsa: movies jadvalida file_id, file_type, duration, file_size ni yangilaydi.
    - Foydalanuvchiga tasdiq xabari yuboradi.
    """
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
        duration = message.video.duration
        file_size = message.video.file_size
    elif message.document:
        doc = message.document
        is_video_doc = (
            (doc.mime_type and doc.mime_type.startswith("video/"))
            or (doc.file_name and doc.file_name.lower().endswith(
                (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts", ".m4v")
            ))
            or extract_code_from_caption(message.caption)
        )
        if not is_video_doc:
            return
        file_id = doc.file_id
        file_type = "document"
        duration = None
        file_size = doc.file_size
    else:
        return

    caption = (message.caption or message.text or "").strip()
    code = extract_code_from_caption(caption)
    candidate_title = extract_candidate_title(caption)

    async with get_session() as session:
        db_movie = await save_or_update_movie_video(
            session=session,
            code=code,
            candidate_title=candidate_title,
            file_id=file_id,
            file_type=file_type,
            duration=duration,
            file_size=file_size,
        )

    if db_movie:
        dur_str = format_duration_str(db_movie.duration)
        size_str = format_file_size_str(db_movie.file_size)
        size_line = f"📦 <b>Hajmi:</b> {size_str}\n" if size_str else ""
        text = (
            "✅ <b>Kino videosi muvaffaqiyatli saqlandi!</b>\n\n"
            f"🎬 <b>Nomi:</b> {db_movie.title}\n"
            f"🔢 <b>Kodi:</b> #{db_movie.code}\n"
            f"⏱ <b>Davomiyligi:</b> {dur_str}\n"
            f"{size_line}\n"
            "Endi botda yoki Web Appda ushbu kino tanlanganda to'liq MP4 video yuboriladi!"
        )
        await message.reply(text, parse_mode="HTML")
    else:
        await message.reply(
            "⚠️ <b>Video qabul qilindi, biroq kino kodi yoki nomi aniqlanmadi.</b>\n\n"
            "Iltimos, ushbu videoga Reply qilib <code>/setmovie &lt;kod&gt;</code> deb yozing "
            "yoki captionga kino kodini (masalan: <code>#284</code>) qo'shib qayta yuboring.",
            parse_mode="HTML"
        )


@router.channel_post(F.video | F.document)
@router.edited_channel_post(F.video | F.document)
async def handle_channel_movie_post(message: Message) -> None:
    """
    Kanal posti handleri: STORAGE_CHANNEL_ID yoki zaxira kino kanaliga video yuklanganda avtomatik indekslash.
    """
    if config.STORAGE_CHANNEL_ID and str(config.STORAGE_CHANNEL_ID).strip():
        storage_id = str(config.STORAGE_CHANNEL_ID).strip()
        chat_id_str = str(message.chat.id)
        if chat_id_str != storage_id and chat_id_str.replace("-100", "") != storage_id.replace("-100", ""):
            return

    if message.video:
        file_id = message.video.file_id
        file_type = "video"
        duration = message.video.duration
        file_size = message.video.file_size
    elif message.document:
        doc = message.document
        is_video_doc = (
            (doc.mime_type and doc.mime_type.startswith("video/"))
            or (doc.file_name and doc.file_name.lower().endswith(
                (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts", ".m4v")
            ))
            or extract_code_from_caption(message.caption)
        )
        if not is_video_doc:
            return
        file_id = doc.file_id
        file_type = "document"
        duration = None
        file_size = doc.file_size
    else:
        return

    caption = (message.caption or message.text or "").strip()
    code = extract_code_from_caption(caption)
    candidate_title = extract_candidate_title(caption)

    async with get_session() as session:
        db_movie = await save_or_update_movie_video(
            session=session,
            code=code,
            candidate_title=candidate_title,
            file_id=file_id,
            file_type=file_type,
            duration=duration,
            file_size=file_size,
        )

    if db_movie:
        logger.info(
            f"Kanal postidan video avtomatik indekslandi: #{db_movie.code} - {db_movie.title} (file_id={file_id})"
        )
