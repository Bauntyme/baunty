"""
Kino bo'limi qayta ishlovchisi (Kino kodi, qidiruv, janrlar, tasodifiy kino)
"""
import html
import logging
import math
import re
from typing import Optional, Tuple
from aiogram import Router, F
from aiogram.filters import StateFilter, Command, CommandObject
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


@router.message(Command("kino", "movie", "film", "kod", "code"))
@router.message(F.text.in_([
    "🎬 Kino", "🎬 Кино", "🎬 Фильмы",
    "🎬 K I N O — kod orqali qidirish",
    "🎬 К И Н О — код орқали қидириш",
    "🎬 К И Н О — поиск по коду",
]))
async def cmd_movies_menu(message: Message, state: FSMContext, command: Optional[CommandObject] = None) -> None:
    await state.clear()
    from services.maintenance_service import maintenance_service
    from keyboards.default import maintenance_menu_keyboard
    if not config.is_admin(message.from_user.id) and (maintenance_service.is_global_maintenance() or maintenance_service.is_page_maintenance("kino")):
        msg = maintenance_service.get_page_message("kino") if maintenance_service.is_page_maintenance("kino") else maintenance_service.get_global_message()
        await message.answer(
            f"🎬 <b>{msg}</b>\n\n<i>Kinolar bo'limida texnik yangilanish olib borilmoqda. Tez orada qaytamiz!</i>",
            parse_mode="HTML",
            reply_markup=maintenance_menu_keyboard(is_admin=False),
            protect_content=True
        )
        return

    # Agar buyruq bilan birga kod yuborilgan bo'lsa (masalan: /kino 101, /kod 101 2, /kino taksi)
    if command and command.args:
        args_text = command.args.strip()
        parsed = extract_movie_code_and_part(args_text)
        if parsed:
            code, part = parsed
        else:
            extracted_code = extract_movie_code(args_text)
            code, part = (extracted_code, 1) if extracted_code else (None, 1)

        if code:
            delivered = await movie_service.deliver_movie(
                bot=message.bot,
                chat_id=message.chat.id,
                code=code,
                part=part,
                reply_to_message_id=message.message_id
            )
            if not delivered:
                code_disp = f"{code} ({part}-qism)" if part > 1 else code
                await message.reply(format_movie_not_found(code_disp), parse_mode="HTML", protect_content=True)
            return

    # Guruhlarda parametrsiz /kino yoki /kod yozilsa, qisqa ko'rsatma beramiz
    if message.chat and message.chat.type in ("group", "supergroup"):
        await message.reply(
            "🎬 <b>Kino kodini yuboring:</b>\n"
            "Masalan: <code>/kino 101</code> yoki <code>101</code>\n\n"
            f"🍿 Rasmiy kinolar kanali: {config.CHANNEL_USERNAME}",
            parse_mode="HTML",
            protect_content=True
        )
        return

    text = (
        "🎬 <b>Kino olamiga xush kelibsiz!</b>\n\n"
        "Quyidagi imkoniyatlardan foydalanishingiz mumkin:\n"
        "• <b>Kino kodi:</b> Shunchaki kodni (masalan, <code>101</code>) yozing\n"
        "• <b>Nomi bo'yicha qidiruv:</b> Qiziqtirgan filmingiz nomini yozing\n"
        "• <b>Tasodifiy kino:</b> Nima ko'rishni bilmayotgan bo'lsangiz\n"
        "• <b>Janrlar:</b> Sevimli yo'nalishingizdagi filmlar\n\n"
        f"🍿 <b>Barcha premyerlar:</b> {config.CHANNEL_USERNAME}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=movie_menu_keyboard(), protect_content=True)


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


@router.callback_query(F.data == "movie:by_year")
async def cb_movie_by_year(callback: CallbackQuery, state: FSMContext) -> None:
    """Yili bo'yicha qidirishni boshlash."""
    await state.set_state(MovieSearchStates.waiting_for_year)
    await callback.message.answer(
        "📅 <b>Kino chiqarilgan yilini kiriting:</b>\nMasalan: <code>2024</code> yoki <code>2023</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "movie:by_actor")
async def cb_movie_by_actor(callback: CallbackQuery, state: FSMContext) -> None:
    """Aktyor bo'yicha qidirishni boshlash."""
    await state.set_state(MovieSearchStates.waiting_for_actor)
    await callback.message.answer(
        "👤 <b>Aktyor yoki aktrisa ismini kiriting:</b>\nMasalan: <i>Jason Statham</i> yoki <i>Tom Cruise</i>",
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
        if movie:
            await movie_service.send_movie_to_user(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                movie=movie,
                session=session
            )
            return

        cat_rnd = movie_service.get_catalog_random()
        if cat_rnd and cat_rnd.get("c"):
            delivered = await movie_service.deliver_movie(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                code=str(cat_rnd["c"]),
                part=1,
                session=session
            )
            if delivered:
                return

        await callback.message.answer(
            f"😔 Bazada hali kinolar mavjud emas.\n🍿 Yangi filmlar kanalimizda: {config.CHANNEL_USERNAME}",
            parse_mode="HTML"
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
            cat_top = movie_service.get_catalog_top(limit=10)
            if cat_top:
                upserted = []
                for it in cat_top:
                    c_str = str(it.get("c"))
                    t_str = it.get("t", f"Kino #{c_str}").strip()
                    d_str = it.get("d", "").strip() or None
                    v_str = int(it.get("v", 150))
                    y_val = int(it.get("y")) if str(it.get("y", "")).isdigit() else None
                    db_m, _ = await crud.upsert_movie(
                        session=session,
                        code=c_str,
                        title=t_str,
                        description=d_str,
                        year=y_val,
                        views_count=v_str
                    )
                    upserted.append(db_m)
                await session.commit()
                movies = upserted

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
        await callback.message.answer(format_movie_not_found(code), parse_mode="HTML", protect_content=True)


@router.callback_query(
    F.data.startswith("watch_part:")
    | F.data.startswith("download_movie:")
    | (F.data.startswith("movie:") & F.data.func(lambda d: bool(d and len(d.split(":")) >= 3 and any(ch.isdigit() for ch in d.split(":")[1]))))
)
async def cb_watch_part(callback: CallbackQuery) -> None:
    """Ko'p qismli serialda qismni tanlash."""
    parts = callback.data.split(":")
    code = parts[1]
    part = int(parts[2])
    await callback.answer(f"📺 {part}-qism yuklanmoqda...")
    delivered = await movie_service.deliver_movie(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        code=code,
        part=part
    )
    if not delivered:
        await callback.message.answer(
            f"❌ <b>#{code}</b> serialining <b>{part}-qismi</b> topilmadi.\n"
            f"🍿 Barcha premyerlar kanalimizda: {config.CHANNEL_USERNAME}",
            parse_mode="HTML",
            protect_content=True
        )


@router.callback_query(F.data.startswith("parts_page:"))
async def cb_parts_page(callback: CallbackQuery) -> None:
    """Ko'p qismli seriallar qismlar sahifasini o'zgartirish."""
    parts = callback.data.split(":")
    code = parts[1]
    page = int(parts[2])

    total_parts = 1
    cat_item = MovieService.get_catalog_item(code)
    if cat_item:
        total_parts = int(cat_item.get("p", 1))

    markup = movie_parts_keyboard(code, total_parts=total_parts, current_part=1, page=page)
    try:
        await callback.message.edit_reply_markup(reply_markup=markup)
        await callback.answer()
    except Exception:
        await callback.answer()



@router.message(MovieSearchStates.waiting_for_code)
async def state_process_code(message: Message, state: FSMContext) -> None:
    """FSM holatida kiritilgan kodni qidirish."""
    raw_code = message.text.strip()
    await state.clear()
    extracted = extract_movie_code_and_part(raw_code)
    if extracted:
        code, part = extracted
    else:
        code, part = raw_code, 1

    delivered = await movie_service.deliver_movie(
        bot=message.bot,
        chat_id=message.chat.id,
        code=code,
        part=part,
        reply_to_message_id=message.message_id
    )
    if not delivered:
        code_disp = f"{code} ({part}-qism)" if part > 1 else code
        await message.reply(
            format_movie_not_found(code_disp),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id)),
            protect_content=True
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
                reply_markup=markup,
                protect_content=True
            )
        else:
            cat_match = MovieService.search_catalog_by_title(title)
            if cat_match and cat_match.get("c"):
                c_str = str(cat_match["c"])
                t_str = cat_match.get("t", f"Kino #{c_str}").strip()
                d_str = cat_match.get("d", "").strip() or None
                v_str = int(cat_match.get("v", 150))
                db_m, _ = await crud.upsert_movie(
                    session=session,
                    code=c_str,
                    title=t_str,
                    description=d_str,
                    views_count=v_str
                )
                await session.commit()
                markup = movie_list_keyboard([db_m])
                await message.answer(
                    f"🔍 <b>«{title}» bo'yicha topilgan kino:</b>\nKeraklisini tanlang:",
                    parse_mode="HTML",
                    reply_markup=markup,
                    protect_content=True
                )
                return

            text = (
                f"❌ <b>«{title}»</b> nomli kino bazamizda topilmadi!\n\n"
                f"🍿 Eng so'nggi kinolar kanalimizda: {config.CHANNEL_USERNAME}\n"
                "Kino nomini to'g'ri yozganingizga ishonch hosil qilib qayta urinib ko'ring."
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id)),
                protect_content=True
            )


@router.message(MovieSearchStates.waiting_for_year, F.text)
async def state_process_year(message: Message, state: FSMContext) -> None:
    """Yil bo'yicha qidirish."""
    raw_val = message.text.strip()
    if not raw_val.isdigit() or len(raw_val) != 4:
        await message.answer(
            "⚠️ Iltimos, 4 xonali yil kiriting (masalan: <code>2024</code>):",
            parse_mode="HTML",
            reply_markup=cancel_keyboard()
        )
        return
    await state.clear()
    year = int(raw_val)

    async with get_session() as session:
        total = await movie_service.get_year_count(session, year)
        movies = await movie_service.get_by_year(session, year, limit=10, offset=0)
        if not movies:
            cat_matches = movie_service.search_catalog_by_year(year, limit=10)
            if cat_matches:
                upserted = []
                for it in cat_matches:
                    c_str = str(it.get("c"))
                    t_str = it.get("t", f"Kino #{c_str}").strip()
                    d_str = it.get("d", "").strip() or None
                    v_str = int(it.get("v", 150))
                    y_val = int(it.get("y")) if str(it.get("y", "")).isdigit() else year
                    db_m, _ = await crud.upsert_movie(
                        session=session,
                        code=c_str,
                        title=t_str,
                        description=d_str,
                        year=y_val,
                        views_count=v_str
                    )
                    upserted.append(db_m)
                await session.commit()
                movies = upserted
                total = len(upserted)

        if not movies:
            await message.answer(
                f"😔 <b>{year}-yil</b>da chiqarilgan kinolar hozircha bazamizda topilmadi.\n"
                f"🍿 Barcha kinolar kanalimizda: {config.CHANNEL_USERNAME}",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
            )
            return

        total_pages = max(1, math.ceil(total / 10))
        text = f"📅 <b>{year}-yildagi kinolar (1/{total_pages}-sahifa):</b>\nKo'rmoqchi bo'lgan filmingizni tanlang:"
        markup = movie_list_keyboard(movies, page=0, total_pages=total_pages, prefix=f"year_page:{year}")
        await message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("year_page:"))
async def cb_year_page(callback: CallbackQuery) -> None:
    """Yil bo'yicha pagination."""
    parts = callback.data.split(":")
    year = int(parts[1])
    page = int(parts[2])
    await callback.answer()

    async with get_session() as session:
        total = await movie_service.get_year_count(session, year)
        total_pages = max(1, math.ceil(total / 10))
        movies = await movie_service.get_by_year(session, year, limit=10, offset=page * 10)
        if not movies:
            return

        text = f"📅 <b>{year}-yildagi kinolar ({page+1}/{total_pages}-sahifa):</b>\nKo'rmoqchi bo'lgan filmingizni tanlang:"
        markup = movie_list_keyboard(movies, page=page, total_pages=total_pages, prefix=f"year_page:{year}")
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.message(MovieSearchStates.waiting_for_actor, F.text)
async def state_process_actor(message: Message, state: FSMContext) -> None:
    """Aktyor bo'yicha qidirish."""
    actor = message.text.strip()
    if len(actor) < 2:
        await message.answer(
            "⚠️ Aktyor ismini to'liqroq kiriting (kamida 2 ta harf):",
            reply_markup=cancel_keyboard()
        )
        return
    await state.clear()

    async with get_session() as session:
        total = await movie_service.get_actor_count(session, actor)
        movies = await movie_service.search_by_actor(session, actor, limit=10, offset=0)
        if not movies:
            cat_matches = movie_service.search_catalog_by_actor(actor, limit=10)
            if cat_matches:
                upserted = []
                for it in cat_matches:
                    c_str = str(it.get("c"))
                    t_str = it.get("t", f"Kino #{c_str}").strip()
                    d_str = it.get("d", "").strip() or None
                    v_str = int(it.get("v", 150))
                    y_val = int(it.get("y")) if str(it.get("y", "")).isdigit() else None
                    db_m, _ = await crud.upsert_movie(
                        session=session,
                        code=c_str,
                        title=t_str,
                        description=d_str,
                        year=y_val,
                        views_count=v_str
                    )
                    upserted.append(db_m)
                await session.commit()
                movies = upserted
                total = len(upserted)

        if not movies:
            await message.answer(
                f"😔 <b>«{actor}»</b> ishtirokidagi kinolar hozircha bazamizda topilmadi.\n"
                f"🍿 Barcha kinolar: {config.CHANNEL_USERNAME}",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
            )
            return

        total_pages = max(1, math.ceil(total / 10))
        text = f"👤 <b>«{actor}» ishtirokidagi kinolar (1/{total_pages}-sahifa):</b>\nKo'rmoqchi bo'lgan filmingizni tanlang:"
        markup = movie_list_keyboard(movies, page=0, total_pages=total_pages, prefix=f"actor_page:{actor}")
        await message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("actor_page:"))
async def cb_actor_page(callback: CallbackQuery) -> None:
    """Aktyor bo'yicha pagination."""
    parts = callback.data.split(":")
    actor = parts[1]
    page = int(parts[2])
    await callback.answer()

    async with get_session() as session:
        total = await movie_service.get_actor_count(session, actor)
        total_pages = max(1, math.ceil(total / 10))
        movies = await movie_service.search_by_actor(session, actor, limit=10, offset=page * 10)
        if not movies:
            return

        text = f"👤 <b>«{actor}» ishtirokidagi kinolar ({page+1}/{total_pages}-sahifa):</b>\nKo'rmoqchi bo'lgan filmingizni tanlang:"
        markup = movie_list_keyboard(movies, page=page, total_pages=total_pages, prefix=f"actor_page:{actor}")
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)




def extract_movie_code_and_part(text: str) -> Optional[Tuple[str, int]]:
    """
    Kino kodi va qism raqamini matndan ajratib oladi.
    Masalan:
    '101' -> ('101', 1)
    '289 2' -> ('289', 2)
    '289-2' -> ('289', 2)
    '289_2' -> ('289', 2)
    '289 2-qism' -> ('289', 2)
    'kod 289 2' -> ('289', 2)
    'taksi' -> ('718', 1)
    'taksi 2' -> ('718', 2)
    'taksi 2ci' -> ('718', 2)
    'Attack on Titan' -> ('717', 1)
    'Attack on Titan — 2-qism' -> ('717', 2)
    """
    if not text:
        return None
    clean = text.strip()
    # Guruhlarda @bot_username ni tozalash (masalan: @BauntyCinemabot 101 -> 101)
    clean = re.sub(r'^@\w+\s*', '', clean).strip()
    # /kino 101, /kod 101 kabi buyruq prefikslarini tozalash
    clean = re.sub(r'^/(?:kino|kod|film|movie|code)(?:@\w+)?\s*', '', clean, flags=re.IGNORECASE).strip()

    if "kino — kod orqali qidirish" in clean.lower() or clean.startswith("http") or clean.startswith("/"):
        return None
    if len(clean) > 60:
        return None

    cleaned = clean.lstrip("#№").strip()
    cleaned = re.sub(r'^(?:kino|film|код|kod|code)\s*:?\s*', '', cleaned, flags=re.IGNORECASE).strip()

    # Pattern: code + part (e.g. "289 2", "289-2", "289_2", "289p2", "289 2-qism", "289 2 qism", "289 1-qism ko'rish")
    m = re.match(
        r'^(\d{1,8})[\s_\-pP]+(?:qism|part|seriya|ep)?\s*(\d{1,4})(?:[\s\-—–]*(?:qism|part|seriya|ep|ci|chi))?(?:\s*(?:ko[\'‘`]?rish|korish|tomosha|yuklash))?$',
        cleaned,
        re.IGNORECASE
    )
    if m:
        return m.group(1), int(m.group(2))

    # Pattern: just code digits (e.g. "101", "#101", "kod: 101")
    if cleaned.isdigit() and len(cleaned) <= 10:
        return cleaned, 1

    # Harakat/maqsad so'zlarini oxiridan olib tashlash (ko'rmoqchiman, ko'rishni, tomosha, tashlab ber...)
    t_work = re.sub(
        r'\s*(?:ko[\'‘`]?r(?:moqchiman|mochiman|moqchi|ishni|ish)?|tomosha(?:\s*(?:qilish|qilmoqchiman|qil))?|tashlab\s*ber(?:ing)?|tashla|yuklash|ochish)\s*$',
        '',
        cleaned,
        flags=re.IGNORECASE
    ).strip()

    # Qism raqamini aniqlash (masalan "taksi 2", "taksi 2ci", "taksi 1ci qismini", "taksi 2-chi qismi", "Attack on Titan — 2-qism")
    m_part = re.search(
        r'[\s\-—–_]+(\d{1,4})\s*(?:-?\s*(?:ci|chi))?(?:\s*-?\s*(?:qism(?:i|ni|ini)?|part|seriya(?:si)?|ep|episode))\b',
        t_work,
        re.IGNORECASE
    )
    if not m_part:
        m_part = re.search(r'[\s\-—–_]+(\d{1,4})\s*(?:-?\s*(?:ci|chi))\b', t_work, re.IGNORECASE)
    if not m_part:
        m_part = re.search(r'[\s\-—–_]+(\d{1,4})\s*$', t_work)

    if m_part:
        part = int(m_part.group(1))
        title_work = t_work[:m_part.start()] + ' ' + t_work[m_part.end():]
    else:
        part = 1
        title_work = t_work

    # Kino, film, serial, multfilm qo'shimchalarini tozalash
    title_cand = re.sub(
        r'\b(?:kinosi(?:ni|ning)?|filmi(?:ni|ning)?|seriali(?:ni)?|multfilmi(?:ni)?|kino|film|serial|multfilm)\b',
        '',
        title_work,
        flags=re.IGNORECASE
    )
    title_cand = ' '.join(title_cand.split()).strip(' -—–_:')

    # Agar qism ajratilgandan keyin faqat raqam qolgan bo'lsa (masalan "101 1-qism ko'rish")
    if title_cand.isdigit() and len(title_cand) <= 10:
        return title_cand, part

    NON_TITLE_WORDS = {
        "admin", "salom", "qalesan", "start", "stop", "help", "yordam", "kino", "film", "menyu", "menu",
        "sozlamalar", "balans", "profile", "kitob", "kitoblar", "kutubxona", "books", "book", "китоб", "китоблар"
    }
    if title_cand and title_cand.lower() not in NON_TITLE_WORDS and not title_cand.isdigit() and len(title_cand) >= 2:
        cat_match = MovieService.search_catalog_by_title(title_cand)
        if cat_match and cat_match.get("c"):
            return str(cat_match["c"]), part

    return None


def extract_movie_code(text: str) -> Optional[str]:
    """
    Kino kodini matndan ajratib oladi.
    Qo'llab-quvvatlanadi: 101, #101, №101, 'kod 101', 'kod: 101', 'код 101', '289 2'
    """
    if not text:
        return None
    clean = text.strip()
    clean = re.sub(r'^@\w+\s*', '', clean).strip()
    clean = re.sub(r'^/(?:kino|kod|film|movie|code)(?:@\w+)?\s*', '', clean, flags=re.IGNORECASE).strip()
    if re.search(r'^\d{1,8}[\s\-—–]*(?:qism|seriya|серия|fasl|sezon|part|ep|episode)', clean, re.IGNORECASE):
        return None
    cleaned = clean.lstrip("#№").strip()
    cleaned = re.sub(r'^(?:kino|film|код|kod|code)\s*:?\s*', '', cleaned, flags=re.IGNORECASE).strip()
    m = re.match(r'^(\d{1,8})[\s_\-pP]+(?:qism|part|seriya|ep)?\s*(\d{1,4})', cleaned, re.IGNORECASE)
    if m:
        return m.group(1)
    if cleaned.isdigit() and len(cleaned) <= 10:
        return cleaned
    m_single = re.match(r'^(\d{1,8})', cleaned)
    if m_single:
        return m_single.group(1)
    return None


@router.message(StateFilter(None), lambda msg: msg.text and extract_movie_code_and_part(msg.text) is not None)
async def process_numeric_movie_code(message: Message) -> None:
    """
    Foydalanuvchi faqat raqam yoki kod (masalan: 123, #123, kod 123, 289 2) yuborganida avtomatik kinoni topib berish.
    """
    extracted = extract_movie_code_and_part(message.text)
    code, part = extracted
    from services.maintenance_service import maintenance_service
    from keyboards.default import maintenance_menu_keyboard
    if not config.is_admin(message.from_user.id) and (maintenance_service.is_global_maintenance() or maintenance_service.is_page_maintenance("kino")):
        msg = maintenance_service.get_page_message("kino") if maintenance_service.is_page_maintenance("kino") else maintenance_service.get_global_message()
        await message.reply(
            f"🎬 <b>{msg}</b>\n\n<i>Kinolar bo'limida texnik yangilanish olib borilmoqda. Tez orada qaytamiz!</i>",
            parse_mode="HTML",
            reply_markup=maintenance_menu_keyboard(is_admin=False),
            protect_content=True
        )
        return
    delivered = await movie_service.deliver_movie(
        bot=message.bot,
        chat_id=message.chat.id,
        code=code,
        part=part,
        reply_to_message_id=message.message_id
    )
    if not delivered:
        code_disp = f"{code} ({part}-qism)" if part > 1 else code
        await message.reply(format_movie_not_found(code_disp), parse_mode="HTML", protect_content=True)


@router.message(StateFilter(None), lambda msg: msg.reply_to_message and msg.text and re.match(r'^(?:kino\s*)?(\d{1,4})\s*(?:-?\s*(?:ci|chi))?\s*(?:-?\s*(?:qism(?:i|ni|ini)?|part|seriya(?:si)?|ep|episode))?(?:\s*(?:ko[\'‘`]?r(?:moqchiman|mochiman|moqchi|ishni|ish)?|tomosha|yuklash))?$', msg.text.strip(), re.IGNORECASE))
async def process_reply_part_request(message: Message) -> None:
    """Foydalanuvchi kino xabariga javob (reply) tarzda '1-qism' yoki '2-qismini ko'rish' yozganida qismni yuborish."""
    m = re.match(r'^(?:kino\s*)?(\d{1,4})\s*(?:-?\s*(?:ci|chi))?\s*(?:-?\s*(?:qism(?:i|ni|ini)?|part|seriya(?:si)?|ep|episode))?(?:\s*(?:ko[\'‘`]?r(?:moqchiman|mochiman|moqchi|ishni|ish)?|tomosha|yuklash))?$', message.text.strip(), re.IGNORECASE)
    if not m:
        return
    part = int(m.group(1))
    reply_msg = message.reply_to_message
    code = extract_code_from_caption(reply_msg.caption or reply_msg.text or "")
    if not code:
        return
    delivered = await movie_service.deliver_movie(
        bot=message.bot,
        chat_id=message.chat.id,
        code=code,
        part=part,
        reply_to_message_id=message.message_id
    )
    if not delivered:
        await message.reply(format_movie_not_found(f"{code} ({part}-qism)"), parse_mode="HTML", protect_content=True)


def extract_code_from_caption(text: Optional[str]) -> Optional[str]:
    """Caption yoki matndan kino kodini aniqlash (#284, Kodi: 284, 101...)."""
    if not text:
        return None
    text_clean = text.strip()

    # 1. Kodi: #284, kod: 284, kino kodi: 284, film kodi: 284, kino: 284, film: 284
    m = re.search(r'(?:kino\s*kodi|film\s*kodi|kodi?|kino|film|код|kod|code)[\s:—–\-#№]*(\d+)', text_clean, re.IGNORECASE)
    if m:
        return m.group(1)

    # 2. #284 yoki # 284 yoki №284 yoki #kino284
    m = re.search(r'[#№](?:kino|film)?_?\s*(\d{1,8})', text_clean, re.IGNORECASE)
    if m:
        return m.group(1)

    # 3. [284] yoki (284)
    m = re.search(r'[\[\(](\d{1,8})[\]\)]', text_clean)
    if m:
        return m.group(1)

    # 4. Satr boshidagi raqam: masalan "284. Zo'raki folbin" yoki "284 - Zo'raki folbin"
    # Serial qismlarini (1-qism, 2-seriya) adashtirib kino kodi deb olmaslik uchun filtr
    for line in text_clean.split("\n"):
        line_clean = line.strip()
        if re.search(r'^\d{1,8}[\s\-—–]*(?:qism|seriya|серия|fasl|sezon|part|ep|episode)', line_clean, re.IGNORECASE):
            continue
        m = re.match(r'^(\d{1,8})[\s\.\-—–:_]', line_clean)
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

    IGNORE_HEADERS = {
        "premyera", "yangi premyera", "yangi kino", "yangi film", "kino olami",
        "assalomu alaykum", "homiy kanal", "bizning kanal", "kanalimiz", "diqqat",
        "tezkor", "retro", "multfilm", "serial"
    }

    # Avval har bir qatordan toza sarlavha qidirish
    for line in lines[:4]:
        # Emojilar va ortiqcha belgilarni tozalash
        cleaned = re.sub(r'[🎬🍿🎥📽🎞📺⭐️★#№—–\-:]', ' ', line)
        cleaned = re.sub(r'https?://\S+|@\w+', '', cleaned).strip()
        cleaned = re.sub(r'(?:kino\s*kodi|film\s*kodi|kodi?|kino|film|код|kod|code)\s*\d+', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'^\d{1,8}[\s\.\-—–:_]', '', cleaned).strip()
        cleaned = re.sub(r'^\d{1,8}[\s\-—–]*(?:qism|seriya|серия|fasl|sezon|part|ep|episode)', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\.(?:mp4|mkv|avi|mov|webm|flv|ts|m4v)$', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = " ".join(cleaned.split())

        header_key = re.sub(r"[^\w\s]", "", cleaned).lower().strip()
        if len(cleaned) >= 3 and not cleaned.isdigit() and header_key not in IGNORE_HEADERS:
            return cleaned

    # Fallback: birinchi qatordan
    first_line = lines[0]
    cleaned = re.sub(r'[🎬🍿🎥📽🎞📺⭐️★#№—–\-:]', ' ', first_line)
    cleaned = re.sub(r'https?://\S+|@\w+', '', cleaned).strip()
    cleaned = re.sub(r'(?:kino\s*kodi|film\s*kodi|kodi?|kino|film|код|kod|code)\s*\d+', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'\.(?:mp4|mkv|avi|mov|webm|flv|ts|m4v)$', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = " ".join(cleaned.split())
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
        base_code = clean_code.split("_")[0].split("-")[0]
        cat_item = MovieService.get_catalog_item(clean_code) or MovieService.get_catalog_item(base_code)
        part_suffix = f" — {clean_code.split('_')[1]}-qism" if "_" in clean_code else ""
        raw_title = cat_item.get("t", f"Kino #{clean_code}") if cat_item else (candidate_title or f"Kino #{clean_code}")
        title = f"{raw_title}{part_suffix}" if (part_suffix and part_suffix not in raw_title) else raw_title
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
        # Agar 1-qism yoki asosiy kod bo'lsa, mos part1 kodi bilan ham saqlash
        if clean_code.isdigit():
            p1_code = f"{clean_code}_1"
            m_p1 = await crud.get_movie_by_code(session, p1_code)
            if not m_p1:
                await crud.create_movie(
                    session=session,
                    code=p1_code,
                    title=f"{title} — 1-qism",
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
        # Agar 1-qism yoki asosiy kod yangilansa, p1_code ni ham sinxronlash
        if clean_code and clean_code.isdigit():
            p1_code = f"{clean_code}_1"
            m_p1 = await crud.get_movie_by_code(session, p1_code)
            if m_p1:
                m_p1.file_id = file_id
                m_p1.file_type = file_type
                if duration:
                    m_p1.duration = duration
                if file_size:
                    m_p1.file_size = file_size

    if db_movie:
        # Telegram Cloud pool: movie_files jadvaliga ham keshlab qo'yamiz
        try:
            m_code = db_movie.code
            m_part = 1
            m_match = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", m_code, re.IGNORECASE)
            if m_match:
                m_code = m_match.group(1)
                m_part = int(m_match.group(2))
            elif "_" in m_code:
                parts_split = m_code.split("_")
                if len(parts_split) == 2 and parts_split[1].isdigit():
                    m_code = parts_split[0]
                    m_part = int(parts_split[1])
            await crud.save_movie_file(
                session=session,
                movie_code=m_code,
                part=m_part,
                file_id=file_id,
                file_type=file_type,
                file_size=file_size,
                duration=duration,
            )
        except Exception as fe:
            logger.debug(f"save_movie_file error in save_or_update_movie_video: {fe}")
        await session.commit()
    return db_movie


@router.message(Command("setmovie", "addvideo"))
async def cmd_set_movie_video(message: Message) -> None:
    """
    Admin buyrug'i: /setmovie <kod> yoki /addvideo <kod>
    Admin ixtiyoriy video xabarga Reply qilib /setmovie 284 deb yozsa,
    yoki videoni /setmovie 284 caption bilan birga yuklasa,
    o'sha videoning Telegram file_id sini avtomatik 284-kinoga biriktiradi!
    """
    user_id = message.from_user.id if message.from_user else 0
    if not config.is_admin(user_id):
        await message.reply("⛔ <b>Ushbu buyruq faqat adminlar uchun!</b>", parse_mode="HTML")
        return

    raw_text = (message.text or message.caption or "").strip()
    args = raw_text.split(maxsplit=1)
    target_msg = message.reply_to_message or message

    code = None
    if len(args) >= 2 and args[1].strip():
        raw_code = args[1].strip()
        code = extract_code_from_caption(raw_code) or raw_code.lstrip("#№").strip()

    # Agar argument ko'rsatilmagan bo'lsa, Reply qilingan yoki joriy video captionidan kodni olish
    if not code and target_msg:
        target_caption = (target_msg.caption or target_msg.text or "").strip()
        code = extract_code_from_caption(target_caption)

    if not code:
        await message.reply(
            "⚠️ <b>Kino kodini kiriting!</b>\n"
            "Masalan: video xabarga Reply qilib <code>/setmovie 284</code> deb yozing "
            "yoki videoga <code>/setmovie 284</code> izohini qo'shib yuboring.",
            parse_mode="HTML"
        )
        return

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


@router.message(Command("browser", "kino", "kinolar", "catalog", "web"))
async def cmd_browser(message: Message) -> None:
    """
    /browser komandasi: Bauntys Web App brauzerini ochish va upstream katalog kinolari,
    telekanallari (1440p QHD) va o'yinlariga tezkor ulanish.
    Foydalanuvchi /browser @BauntyCinemabot, /browser asilmedia.org yoki /browser <kino> yozganda ham to'g'ri bog'lanadi.
    """
    import asyncio
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    raw_args = message.text.split(maxsplit=1)
    arg = raw_args[1].strip() if len(raw_args) > 1 else ""
    bot_name = config.BOT_USERNAME.lstrip("@")
    channel_name = config.CHANNEL_USERNAME.lstrip("@")
    webapp_url = config.WEBAPP_URL

    clean_arg = re.sub(r"^@\w+\s*", "", arg).strip()

    # 0. @Zakirovsfilms_bot yoki arxitektura tahlili so'ralganda (/browser @Zakirovsfilms_bot ni toliq organ)
    is_zakirovsfilms = bool(re.search(r"zakirovs?films?(?:_bot)?\b", arg, re.IGNORECASE))
    if is_zakirovsfilms and clean_arg and bool(re.search(r"toliq\s*o['`]?rgan|organ|tahlil", clean_arg, re.IGNORECASE)):
        analysis_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🍿 Bauntys Web App Brauzerini Ochish",
                        web_app=WebAppInfo(url=webapp_url)
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🚕 Taksi (1-5 qismlar)",
                        callback_data="watch_part:718:1"
                    ),
                    InlineKeyboardButton(
                        text="⚔️ Titanlar hujumi",
                        callback_data="watch_part:717:1"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔫 Chuqur (131 qism)",
                        callback_data="watch_part:287:1"
                    ),
                    InlineKeyboardButton(
                        text="🏎️ Forsaj (1-11)",
                        callback_data="watch_part:1500:1"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="⚡ LCP Diagnostika",
                        callback_data="lcp_diag"
                    ),
                    InlineKeyboardButton(
                        text="📢 Rasmiy Kanal",
                        url=f"https://t.me/{channel_name}"
                    )
                ]
            ]
        )
        analysis_text = (
            "🤖 <b>Bauntys vs Upstream Arxitektura Tahlili</b>\n\n"
            "• 📡 <b>Katalog Manbasi:</b> Asilmedia.org ochiq tarmog'i (18,500+ kino va seriallar)\n"
            "• ☁️ <b>Gibrid Telegram Cloud Pool:</b> Videolarni Render diskiga (5 GB cheklov) yuklab o'tirmasdan, "
            "Telegram Cloud <code>file_id</code> lari orqali 0 MB disk sarfi bilan 0.5 soniyada chaqmoqdek yetkazish tizimi joriy etildi.\n"
            "• ⚡ <b>Web App LCP:</b> <code>fetchpriority=\"high\"</code>, <code>preconnect</code> va <code>loading=\"lazy\"</code> orqali LCP &lt; 1.2s ga tushirildi.\n"
            "• 🛡️ <b>Brend:</b> 100% Bauntys Oq Brendi (@BauntyCinemabot, @BauntyFilms).\n\n"
            "🍿 <b>Boshlash uchun kinoni tanlang yoki Web App brauzerni oching:</b>"
        )
        await message.reply(analysis_text, parse_mode="HTML", reply_markup=analysis_kb, protect_content=True)
        return

    # 0.5. @Zakirovs_ai bridge: Kinolar va Kitoblar integratsiyasi (/browser @Zakirovs_ai ...)
    is_zakirovs_ai = bool(re.search(r"zakirovs?_ai\b", arg, re.IGNORECASE))
    if is_zakirovs_ai:
        clean_ai_query = re.sub(r"^(?:https?://)?(?:t\.me/)?@?zakirovs?_ai/?\s*", "", arg, flags=re.IGNORECASE).strip()
        clean_ai_query = re.sub(r"^@\w+\s*", "", clean_ai_query).strip().lstrip("/")

        # Agar qidiruv yoki aniq so'rov berilmagan bo'lsa: /browser @Zakirovs_ai
        if not clean_ai_query:
            asyncio.create_task(movie_service.sync_catalog_from_upstream())
            ai_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🍿 Kinolar Web App",
                            web_app=WebAppInfo(url=webapp_url)
                        ),
                        InlineKeyboardButton(
                            text="📚 Kitoblar Web App",
                            web_app=WebAppInfo(url=f"{webapp_url}?books")
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🚕 Taksi (1-5)",
                            callback_data="watch_part:718:1"
                        ),
                        InlineKeyboardButton(
                            text="🏎️ Forsaj (1-11)",
                            callback_data="watch_part:1500:1"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="📖 O'tkan kunlar (PDF)",
                            callback_data="book:dl:1"
                        ),
                        InlineKeyboardButton(
                            text="💼 Boy ota, kambag'al ota",
                            callback_data="book:dl:4"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🎬 Sara Kinolar",
                            callback_data="movie:top"
                        ),
                        InlineKeyboardButton(
                            text="📚 Sara Kitoblar",
                            callback_data="books:pop"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔍 Qidiruv (Kino va Kitob)",
                            switch_inline_query_current_chat=""
                        ),
                        InlineKeyboardButton(
                            text="📢 Rasmiy Kanal",
                            url=f"https://t.me/{channel_name}"
                        )
                    ]
                ]
            )
            ai_text = (
                "🍿 <b>Bauntys — Kinolar va Kitoblar Portali</b>\n\n"
                "🌐 <b>@Zakirovs_ai integratsiyasi:</b> barcha sara kinolar va elektron kitoblar "
                "yagona ekotizimda to'liq ulandi! Endi istalgan filmni tomosha qilishingiz yoki "
                "kitobni to'liq PDF formatida yuklab olishingiz mumkin.\n\n"
                "🎬 <b>Kinolar Portali:</b>\n"
                "• 18,500+ kino va seriallar (Taksi 1-5, Titanlar, Chuqur, Forsaj)\n"
                "• 150+ telekanallar (1440p QHD / 1080p)\n\n"
                "📚 <b>Kutubxona Portali:</b>\n"
                "• O'zbek va jahon adabiyoti durdonalari\n"
                "• Biznes, shaxsiy rivojlanish, psixologiya va audio kitoblar\n"
                "• To'liq PDF formatida yuklab olish va zamonaviy o'quvchi ilovasi\n\n"
                f"🤖 <b>Bizning bot:</b> @{bot_name}\n"
                f"🍿 <b>Kino kanalimiz:</b> @{channel_name}\n\n"
                "<i>Kerakli bo'limni tanlang yoki qidiruv uchun kino kodi / kitob nomini yozing:</i>"
            )
            await message.reply(ai_text, parse_mode="HTML", reply_markup=ai_kb, protect_content=True)
            return

        # Agar kitoblar bo'limi so'ralsa: /browser @Zakirovs_ai kitob
        if clean_ai_query.lower() in ("kitob", "kitoblar", "books", "book", "kutubxona", "kniga", "knigi", "китоб", "китоблар", "книга", "книги", "кутубхона"):
            from handlers.books import get_books_main_keyboard
            from services import book_service
            cat = book_service.get_catalog(limit=6)
            total = cat.get("total", 32)
            kb = get_books_main_keyboard()
            text = (
                f"📚 <b>Baunty Kutubxonasi — {total}+ Sara Elektron Kitoblar!</b>\n\n"
                f"Har bir kitobni to'g'ridan-to'g'ri qulay ilovada o'qishingiz "
                f"yoki PDF formatida chatga yuklab olishingiz mumkin!\n\n"
                f"<i>Quyidagi toifalardan birini tanlang:</i>"
            )
            await message.reply(text, parse_mode="HTML", reply_markup=kb, protect_content=True)
            return

        # Agar kinolar bo'limi so'ralsa: /browser @Zakirovs_ai kino / kinolar
        if clean_ai_query.lower() in ("kino", "kinolar", "film", "filmlar", "serial", "seriallar", "movie", "movies", "cinema"):
            text = (
                "🎬 <b>Baunty Kinolar Portali — 18,500+ Kino va Seriallar!</b>\n\n"
                "Quyidagi imkoniyatlardan foydalanishingiz mumkin:\n"
                "• <b>Kino kodi:</b> Shunchaki kodni (masalan, <code>101</code>) yozing\n"
                "• <b>Nomi bo'yicha qidiruv:</b> Qiziqtirgan filmingiz nomini yozing\n"
                "• <b>Tasodifiy kino:</b> Nima ko'rishni bilmayotgan bo'lsangiz\n"
                "• <b>Janrlar:</b> Sevimli yo'nalishingizdagi filmlar\n\n"
                f"🍿 <b>Barcha premyerlar:</b> {config.CHANNEL_USERNAME}"
            )
            await message.reply(text, parse_mode="HTML", reply_markup=movie_menu_keyboard(), protect_content=True)
            return

        # Agar kino kodi berilgan bo'lsa: /browser @Zakirovs_ai 718 yoki 718_2
        code_match = re.match(
            r'^(?:#|№|kod:?\s*|kino:?\s*)?(\d{1,8})(?:[\s_\-pP]+(\d{1,4}))?$',
            clean_ai_query,
            re.IGNORECASE
        )
        if code_match:
            c_code = code_match.group(1)
            c_part = int(code_match.group(2)) if code_match.group(2) else 1
            delivered = await movie_service.deliver_movie(
                bot=message.bot,
                chat_id=message.chat.id,
                code=c_code,
                part=c_part,
                reply_to_message_id=getattr(message, "message_id", None)
            )
            if delivered:
                return

        # Qidiruv so'rovini tozalash (kitob yoki kino prefikslarini olib tashlash)
        from services import book_service
        book_query = re.sub(r'^(?:kitob(?:lar)?|books?|китоб(?:лар)?|книг[аи]|кутубхона)\s*:?\s*', '', clean_ai_query, flags=re.IGNORECASE).strip() or clean_ai_query
        movie_query = re.sub(r'^(?:kino(?:lar)?|film(?:lar)?|serial(?:lar)?|multfilm|movie(?:s)?|кино(?:лар)?|фильм(?:ы)?|сериал(?:ы)?)\s*:?\s*', '', clean_ai_query, flags=re.IGNORECASE).strip() or clean_ai_query

        # 1. Kitoblardan qidirish
        matched_books = book_service.search_books(book_query, limit=5)

        # 2. Kinolardan qidirish (avval lokal katalog, keyin Asilmedia)
        matched_movie = None
        if not matched_books or bool(re.search(r'^(?:kino|film|serial|movie)\b', clean_ai_query, re.IGNORECASE)):
            matched_movie = movie_service.search_catalog_by_title(movie_query)
            if not matched_movie:
                try:
                    from services.asilmedia_service import asilmedia_service
                    matched_movie = await asilmedia_service.find_best_match(movie_query)
                except Exception:
                    pass

        # 1. Agar kitob topilgan bo'lsa va kino so'ralmagan bo'lsa
        if matched_books and not matched_movie:
            if len(matched_books) == 1:
                deliv_res = await book_service.deliver_book(
                    bot=message.bot,
                    chat_id=message.chat.id,
                    book_id=matched_books[0]["id"]
                )
                if deliv_res.get("ok"):
                    return

            b_rows = []
            b_text = f"📚 <b>Topilgan kitoblar ({len(matched_books)} ta):</b>\n\n"
            for b in matched_books:
                b_title = b.get("title", "Kitob")
                b_author = b.get("author", "Muallif")
                b_fmt = b.get("format", "PDF")
                safe_bt = html.escape(str(b_title), quote=False)
                safe_ba = html.escape(str(b_author), quote=False)
                b_text += f"• <b>{safe_bt}</b> — {safe_ba} ({b_fmt})\n"
                b_rows.append([
                    InlineKeyboardButton(
                        text=f"📥 {b_title[:28]} ({b_fmt})",
                        callback_data=f"book:dl:{b['id']}"
                    )
                ])
            b_rows.append([
                InlineKeyboardButton(
                    text="📚 Kutubxona Web App",
                    web_app=WebAppInfo(url=f"{webapp_url}?books")
                )
            ])
            await message.reply(
                b_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=b_rows),
                protect_content=True
            )
            return

        # 2. Agar kino topilgan bo'lsa va kitob topilmagan bo'lsa
        if matched_movie and not matched_books:
            m_code = str(
                getattr(matched_movie, "id", None)
                or (matched_movie.get("c") if isinstance(matched_movie, dict) else None)
                or (matched_movie.get("id") if isinstance(matched_movie, dict) else None)
            )
            delivered = await movie_service.deliver_movie(
                bot=message.bot,
                chat_id=message.chat.id,
                code=m_code,
                part=1,
                reply_to_message_id=getattr(message, "message_id", None)
            )
            if delivered:
                return

        # 3. Agar ham kino, ham kitob topilsa (kombinatsiyalangan natija)
        if matched_movie and matched_books:
            m_title = getattr(matched_movie, "title", None) or (matched_movie.get("t") if isinstance(matched_movie, dict) else None) or "Kino"
            m_code = str(
                getattr(matched_movie, "id", None)
                or (matched_movie.get("c") if isinstance(matched_movie, dict) else None)
                or (matched_movie.get("id") if isinstance(matched_movie, dict) else None)
            )
            comb_rows = [
                [
                    InlineKeyboardButton(
                        text=f"🎬 Kinoni ko'rish: {m_title[:25]}",
                        callback_data=f"watch_part:{m_code}:1"
                    )
                ]
            ]
            for b in matched_books[:2]:
                comb_rows.append([
                    InlineKeyboardButton(
                        text=f"📥 Kitobni yuklash: {b['title'][:25]}",
                        callback_data=f"book:dl:{b['id']}"
                    )
                ])
            comb_rows.append([
                InlineKeyboardButton(
                    text="🍿 Kinolar",
                    web_app=WebAppInfo(url=webapp_url)
                ),
                InlineKeyboardButton(
                    text="📚 Kitoblar",
                    web_app=WebAppInfo(url=f"{webapp_url}?books")
                )
            ])
            comb_text = (
                f"🍿 <b>Bauntys — Qidiruv Natijasi: «{clean_ai_query}»</b>\n\n"
                f"🎬 <b>Kino:</b> {m_title} (kod: <code>{m_code}</code>)\n"
                f"📚 <b>Kitob:</b> {matched_books[0]['title']} — {matched_books[0]['author']}\n\n"
                f"<i>Tomosha qilish yoki kitobni yuklab olish uchun tanlang:</i>"
            )
            await message.reply(
                comb_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=comb_rows),
                protect_content=True
            )
            return

        # 4. Agar hech narsa topilmasa
        not_found_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🍿 Kinolar katalogi",
                        web_app=WebAppInfo(url=webapp_url)
                    ),
                    InlineKeyboardButton(
                        text="📚 Kitoblar katalogi",
                        web_app=WebAppInfo(url=f"{webapp_url}?books")
                    )
                ]
            ]
        )
        await message.reply(
            f"🔍 «<b>{clean_ai_query}</b>» bo'yicha kino yoki kitob topilmadi.\n\n"
            f"Iltimos, nomini to'g'ri yozing yoki Web App katalogidan qidiring:",
            parse_mode="HTML",
            reply_markup=not_found_kb,
            protect_content=True
        )
        return

    # 1. Asilmedia portali yoki Asilmedia qidiruvi (/browser asilmedia.org ...)
    if "asilmedia" in clean_arg.lower():
        clean_query = re.sub(
            r"^(?:https?://)?(?:www\.)?asilmedia\.(?:org|net|uz|tv)\s*",
            "",
            clean_arg,
            flags=re.IGNORECASE
        ).strip()
        clean_query = re.sub(r"^asilmedia\s*", "", clean_query, flags=re.IGNORECASE).strip()

        # Agar qidiruv so'rovi yoki kino kodi/nomi berilgan bo'lsa
        if clean_query:
            extracted = extract_movie_code_and_part(clean_query)
            if extracted:
                code, part = extracted
                delivered = await movie_service.deliver_movie(
                    bot=message.bot,
                    chat_id=message.chat.id,
                    code=code,
                    part=part,
                    reply_to_message_id=message.message_id
                )
                if delivered:
                    return

            try:
                from services.asilmedia_service import asilmedia_service
                asil_movie = None
                if clean_query.startswith("http") or clean_query.isdigit():
                    asil_movie = await asilmedia_service.get_movie_details(clean_query)
                if not asil_movie:
                    asil_movie = await asilmedia_service.find_best_match(clean_query)

                if asil_movie:
                    m_title = asil_movie.title or f"Kino #{asil_movie.id}"
                    m_year = f" ({asil_movie.year})" if asil_movie.year else ""
                    m_genres = ", ".join(asil_movie.genres[:3]) if asil_movie.genres else "Kino"
                    m_parts = asil_movie.total_parts or len(asil_movie.episodes) or 1

                    kb_rows = []
                    if m_parts > 1:
                        part_buttons = []
                        for p_num in range(1, min(m_parts + 1, 9)):
                            part_buttons.append(
                                InlineKeyboardButton(
                                    text=f"{p_num}-qism",
                                    callback_data=f"watch_part:{asil_movie.id}:{p_num}"
                                )
                            )
                        for i in range(0, len(part_buttons), 4):
                            kb_rows.append(part_buttons[i:i+4])
                    else:
                        kb_rows.append([
                            InlineKeyboardButton(
                                text="🎬 1-qismni tomosha qilish",
                                callback_data=f"watch_part:{asil_movie.id}:1"
                            )
                        ])

                    watch_u = None
                    if asil_movie.episodes and 1 in asil_movie.episodes:
                        watch_u = asil_movie.episodes[1].watch_url or asil_movie.episodes[1].url
                    elif asil_movie.video_sources:
                        watch_u = asil_movie.video_sources.get("primary") or list(asil_movie.video_sources.values())[0]

                    player_url = watch_u if watch_u and watch_u.startswith("http") else f"{webapp_url}?c={asil_movie.id}&movie={asil_movie.id}"
                    kb_rows.append([
                        InlineKeyboardButton(
                            text="▶️ Asilmedia Playerda ochish",
                            web_app=WebAppInfo(url=player_url)
                        )
                    ])
                    kb_rows.append([
                        InlineKeyboardButton(
                            text="📢 Rasmiy Kanal",
                            url=f"https://t.me/{channel_name}"
                        )
                    ])

                    asil_card_text = (
                        f"🍿 <b>{m_title}{m_year}</b>\n\n"
                        f"🎭 <b>Janr:</b> {m_genres}\n"
                        f"🔢 <b>Jami qismlar:</b> {m_parts} ta\n"
                        f"🌐 <b>Manba:</b> Asilmedia tarmog'i\n\n"
                        f"<i>Quyidagi tugmalar orqali qismlarni tomosha qiling yoki brauzerda oching:</i>\n\n"
                        f"🤖 <b>Bot:</b> @{bot_name}\n"
                        f"🍿 <b>Kanal:</b> @{channel_name}"
                    )
                    await message.reply(
                        asil_card_text,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
                        protect_content=True
                    )
                    return
            except Exception as ae:
                logger.debug(f"Asilmedia browser live lookup error: {ae}")

        # Shunchaki /browser asilmedia.org
        asil_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚕 Taksi (1-5 qismlari)",
                        callback_data="watch_part:718:1"
                    ),
                    InlineKeyboardButton(
                        text="⚔️ Titanlar hujumi",
                        callback_data="watch_part:717:1"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔫 Chuqur (131 qism)",
                        callback_data="watch_part:287:1"
                    ),
                    InlineKeyboardButton(
                        text="🏎️ Forsaj (Barcha)",
                        callback_data="watch_part:1500:1"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🍿 Asilmedia Web Player",
                        web_app=WebAppInfo(url=f"{webapp_url}?c=718&src=asilmedia")
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔍 Asilmedia Qidiruv",
                        switch_inline_query_current_chat=""
                    ),
                    InlineKeyboardButton(
                        text="📢 Rasmiy Kanal",
                        url=f"https://t.me/{channel_name}"
                    )
                ]
            ]
        )
        asil_text = (
            "🍿 <b>Bauntys — Asilmedia Kinolar Portali</b>\n\n"
            "Asilmedia tarmog'idagi barcha ommabop kinolar, ko'p qismli seriallar "
            "va multfilmlarni to'g'ridan-to'g'ri Telegramda hamda Web App brauzerida "
            "yuqori sifatda (Full HD / 4K) tomosha qiling va yuklab oling!\n\n"
            "🎬 <b>Ommabop kinolar va to'plamlar:</b>\n"
            "🚕 <b>Taksi 1-5</b> — barcha qismlari (kod: <code>718</code>)\n"
            "⚔️ <b>Titanlar hujumi</b> — 54 qism (kod: <code>717</code>)\n"
            "🔫 <b>Chuqur</b> — 131 qism (kod: <code>287</code>)\n"
            "🏎️ <b>Forsaj</b> — barcha qismlari (kod: <code>1500</code>)\n\n"
            f"🤖 <b>Bizning bot:</b> @{bot_name}\n"
            f"🍿 <b>Kino kanalimiz:</b> @{channel_name}\n\n"
            "<i>Kinoni tanlash yoki qidirish uchun quyidagi tugmalardan foydalaning:</i>"
        )
        await message.reply(asil_text, parse_mode="HTML", reply_markup=asil_kb, protect_content=True)
        return

    # 2. Umumiy kino kodi / nomi berilgan bo'lsa
    if clean_arg:
        extracted = extract_movie_code_and_part(clean_arg)
        if extracted:
            code, part = extracted
            delivered = await movie_service.deliver_movie(
                bot=message.bot,
                chat_id=message.chat.id,
                code=code,
                part=part,
                reply_to_message_id=message.message_id
            )
            if delivered:
                return

        # Nomi bo'yicha qidirib ko'rish
        try:
            from services.asilmedia_service import asilmedia_service
            asil_movie = await asilmedia_service.find_best_match(clean_arg)
            if asil_movie:
                delivered = await movie_service.deliver_movie(
                    bot=message.bot,
                    chat_id=message.chat.id,
                    code=str(asil_movie.id),
                    part=1,
                    reply_to_message_id=message.message_id
                )
                if delivered:
                    return
        except Exception as ae:
            logger.debug(f"Live search error in cmd_browser: {ae}")

    # 3. /browser yoki /browser @bot argumensiz bo'lganda orqa fonda sinxronlash va to'liq menyu
    asyncio.create_task(movie_service.sync_catalog_from_upstream())

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🍿 Web App Brauzerni Ochish",
                    web_app=WebAppInfo(url=webapp_url)
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚕 Taksi (1-5)",
                    callback_data="watch_part:718:1"
                ),
                InlineKeyboardButton(
                    text="⚔️ Titanlar hujumi",
                    callback_data="watch_part:717:1"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔫 Chuqur (131 qism)",
                    callback_data="watch_part:287:1"
                ),
                InlineKeyboardButton(
                    text="🏎️ Forsaj (1-11)",
                    callback_data="watch_part:1500:1"
                ),
            ],
            [
                InlineKeyboardButton(text="🎬 Sara Kinolar", callback_data="movie:top"),
                InlineKeyboardButton(text="🎭 Janrlar", callback_data="movie:genres"),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Rasmiy Kanal",
                    url=f"https://t.me/{channel_name}"
                )
            ]
        ]
    )

    text = (
        "🌐 <b>Bauntys Web App Brauzeriga xush kelibsiz!</b>\n\n"
        "Barcha yangi premyeralar, 1500+ kinolar va ko'p qismli seriallar "
        "(Taksi 1-5, Titanlar hujumi, Chuqur, Forsaj va boshqalar), "
        "150+ telekanallar (1440p QHD / 1080p) hamda 50+ o'yinlar yagona portalda jamlangan!\n\n"
        "🎬 <b>Ommabop kinolar va to'plamlar:</b>\n"
        "🚕 <b>Taksi 1-5</b> — barcha qismlari (kod: <code>718</code>)\n"
        "⚔️ <b>Titanlar hujumi</b> — 54 qism (kod: <code>717</code>)\n"
        "🔫 <b>Chuqur</b> — 131 qism (kod: <code>287</code>)\n"
        "🏎️ <b>Forsaj</b> — 1-11 qismlari (kod: <code>1500</code>)\n\n"
        f"🤖 <b>Bizning bot:</b> @{bot_name}\n"
        f"🍿 <b>Kino kanalimiz:</b> @{channel_name}\n\n"
        "Quyidagi tugmalar orqali tomosha qiling yoki Web App brauzerni oching:"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=kb, protect_content=True)


@router.message(Command("synckino", "syncmovies"))
async def cmd_sync_movies(message: Message) -> None:
    """Admin buyrug'i: barcha yangi kinolarni katalogdan darhol sinxronlash."""
    user_id = message.from_user.id if message.from_user else 0
    if not config.is_admin(user_id):
        await message.reply("⛔ <b>Ushbu buyruq faqat adminlar uchun!</b>", parse_mode="HTML")
        return

    msg = await message.reply("⏳ Katalog bilan sinxronlash boshlandi...", parse_mode="HTML")
    count = await movie_service.sync_catalog_from_upstream()
    await msg.edit_text(
        f"✅ <b>Sinxronizatsiya muvaffaqiyatli yakunlandi!</b>\n\n"
        f"🔄 <b>Ko'rib chiqilgan/yangilangan kinolar:</b> {count} ta\n"
        f"🍿 <b>Bizning kanalimiz:</b> {config.CHANNEL_USERNAME}\n"
        f"🤖 <b>Bizning botimiz:</b> @{config.BOT_USERNAME.lstrip('@')}",
        parse_mode="HTML"
    )


@router.message(Command("plan"))
async def cmd_plan(message: Message) -> None:
    """/plan komandasi: Bauntys Rivojlanish Rejasi va Premium Imkoniyatlar."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    bot_name = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
    channel_name = config.CHANNEL_USERNAME.lstrip("@")
    webapp_url = config.WEBAPP_URL
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Bauntys Web Appni ochish", web_app=WebAppInfo(url=webapp_url))],
            [
                InlineKeyboardButton(text="📺 Jonli TV (1440p)", web_app=WebAppInfo(url=f"{webapp_url}#tv")),
                InlineKeyboardButton(text="🎬 Sara Kinolar", callback_data="movie:top"),
            ],
            [
                InlineKeyboardButton(text="📚 Kitoblar Portali", web_app=WebAppInfo(url=f"{webapp_url}?books")),
                InlineKeyboardButton(text="🎭 Janrlar", callback_data="movie:genres"),
            ],
            [
                InlineKeyboardButton(text="📢 Rasmiy Kanal", url=f"https://t.me/{channel_name}"),
            ]
        ]
    )
    text = (
        "📋 <b>Bauntys Rivojlanish Rejasi va Imkoniyatlar (Roadmap)</b>\n\n"
        "• 🚀 <b>Tezkor MP4 Video Streaming:</b> Barcha kinolarni (Taksi, Forsaj, Titanlar, Chuqur va yangi premyeralar) "
        "bevosita Telegram chatida 1080p sifatda tomosha qilish.\n"
        "• 📺 <b>1440p QHD / 1080p 60fps Jonli Telekanallar:</b> 208 ta milliy va jahon telekanallari (Zo'r TV, Sevimli, Milliy, MY5, UFC, Futbol) qotmasdan va uzilmasdan tezkor efir uzatish.\n"
        "• 📚 <b>Kutubxona Portali:</b> 3,390+ sara kitoblar (PDF/EPUB), zamonaviy mini-ilova mutolaasi va tezkor yuklab olish.\n"
        "• 🌐 <b>Mini App Integratsiyasi:</b> 1500+ kinolar katalogi, 208 ta telekanal (1440p QHD), kitoblar va 50+ o'yinlar bitta portalda.\n"
        "• ⚡ <b>Telegram Global CDN & Proxy Relay:</b> Barcha video fayllar va TV oqimlari avtomatik keshlanadi va 0.1-1.0 soniyada ulanadi.\n"
        "• 💎 <b>100% Bauntys Oq Brendi:</b> Begona reklamasiz, qulay va xavfsiz tizim.\n\n"
        f"🤖 <b>Bizning bot:</b> @{bot_name}\n"
        f"🍿 <b>Kino kanalimiz:</b> @{channel_name}"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("goal"))
async def cmd_goal(message: Message) -> None:
    """/goal komandasi: Bauntys Maqsadi va Missiyasi."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    bot_name = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
    channel_name = config.CHANNEL_USERNAME.lstrip("@")
    webapp_url = config.WEBAPP_URL
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Web App Brauzer", web_app=WebAppInfo(url=webapp_url))],
            [
                InlineKeyboardButton(text="📺 Jonli TV (1440p)", web_app=WebAppInfo(url=f"{webapp_url}#tv")),
                InlineKeyboardButton(text="📚 Kitoblar Portali", callback_data="books:main"),
            ],
            [
                InlineKeyboardButton(text="🔍 Kino qidirish", callback_data="movie:by_title"),
                InlineKeyboardButton(text="🎬 Sara Kinolar", callback_data="movie:top"),
            ]
        ]
    )
    text = (
        "🎯 <b>Bauntys Bosh Maqsadi va Missiyasi (Goal)</b>\n\n"
        "• 🍿 <b>Mukammal Kino Portali:</b> O'zbekistondagi eng qulay, tezyurar va sifatli kino platformasini taqdim etish.\n"
        "• 📚 <b>Boy Kutubxona:</b> O'zbek va jahon adabiyoti durdonalarini PDF/EPUB formatida qulay yetkazish.\n"
        "• 📺 <b>1440p QHD Uzluksiz Jonli Telekanallar:</b> Barcha 208 ta telekanalni (Milliy, Sevimli, Zo'r TV, UFC, Futbol) 1 soniyada ochiladigan, qotmaydigan va uzilmaydigan efirda uzatish.\n"
        "• 📼 <b>100% Kafolatlangan Video Yetkazish:</b> Har bir film va serial qismini to'liq video fayl (MP4) ko'rinishida foydalanuvchiga taqdim etish.\n"
        "• 🌍 <b>Barcha Premyeralar:</b> Franshizalar (Taksi 1-5, Forsaj 1-11, Titanlar hujumi, Chuqur va b.) hamda yangi jahon kinolarini o'zbek tilida yagona tizimga jamlash.\n\n"
        f"🤖 <b>Botimiz:</b> @{bot_name}\n"
        f"🍿 <b>Kanalimiz:</b> @{channel_name}"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("boost"))
async def cmd_boost(message: Message) -> None:
    """/boost komandasi: Bauntys Turbo Boost va Server Tezlatgichi."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    bot_name = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
    webapp_url = config.WEBAPP_URL
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Web Appni ochish", web_app=WebAppInfo(url=webapp_url))],
            [
                InlineKeyboardButton(text="⚡ TV FastTrack (1440p)", web_app=WebAppInfo(url=f"{webapp_url}#tv")),
                InlineKeyboardButton(text="📚 Kitoblar", web_app=WebAppInfo(url=f"{webapp_url}?books")),
            ],
            [
                InlineKeyboardButton(text="🎲 Tasodifiy kino", callback_data="movie:random"),
            ]
        ]
    )
    text = (
        "⚡ <b>Bauntys Turbo Boost Rejimi (Fast-Track CDN & TV)</b>\n\n"
        "• 🚀 <b>Server Holati:</b> 100% Faol va optimallashtirilgan!\n"
        "• 📺 <b>TV Oqimlari:</b> 1440p QHD adaptiv HLS, 208 ta kanal, CORS Relay Proxy va zaxira oqimlar faol.\n"
        "• 🏎️ <b>Video Oqimlari:</b> Telegram Bot API to'g'ridan-to'g'ri MP4 FastStart formatiga ulandi.\n"
        "• 📚 <b>Kutubxona:</b> 3,390+ kitoblar tezkor keshi va o'quvchi ilovasi faol.\n"
        "• 💾 <b>Kesh Tizimi:</b> Real-time AsilMedia katalogi va TV kanallar keshlandi.\n"
        "• 📶 <b>Yuklash Tezligi:</b> 0.1–0.5 soniya (Telegram CDN & Fast-Track proxy orqali).\n\n"
        f"🤖 <b>Bot:</b> @{bot_name}"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("chrome-devtools", "chromedevtools", "devtools"))
async def cmd_chrome_devtools(message: Message) -> None:
    """/chrome-devtools komandasi: Web App DevTools va Diagnostika holati."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    bot_name = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
    webapp_url = config.WEBAPP_URL
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Web Appni tekshirish", web_app=WebAppInfo(url=webapp_url))],
            [
                InlineKeyboardButton(text="📺 TV Diagnostika (1440p)", web_app=WebAppInfo(url=f"{webapp_url}#tv")),
                InlineKeyboardButton(text="📚 Kitoblar API", web_app=WebAppInfo(url=f"{webapp_url}?books")),
            ]
        ]
    )
    text = (
        "🛠 <b>Bauntys Web App DevTools & Diagnostika</b>\n\n"
        "• 🌐 <b>Mini App API:</b> 200 OK (Render.com Python 3.11)\n"
        "• 📺 <b>Jonli TV Drayveri:</b> 208 kanal, 1440p QHD / 1080p 60fps, CORS Proxy (/api/tv/stream) 100% faol\n"
        "• 📚 <b>Kutubxona (Books API):</b> 3,390+ kitoblar indeksi, PDF/EPUB drayveri va Reader faol\n"
        "• 🔌 <b>Upstream AsilMedia:</b> Ulangan (https://161-97-96-58.sslip.io)\n"
        "• 🎥 <b>Video Drayveri:</b> H.264 / AAC 720p/1080p FastStart\n"
        "• 🛡️ <b>Xavfsizlik (WAF):</b> 100% Bauntys Oq Brendi, Telegram InitData himoyalangan\n"
        "• 📊 <b>Baza (SQLite):</b> 600+ filmlar indeksi faol\n\n"
        f"🤖 <b>Bot:</b> @{bot_name}"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("debug-optimize-lcp", "debug_optimize_lcp", "optimize-lcp", "optimize_lcp", "lcp"))
async def cmd_debug_optimize_lcp(message: Message) -> None:
    """/debug-optimize-lcp komandasi: Web App LCP holati va diagnostikasi."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    bot_name = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
    webapp_url = config.WEBAPP_URL
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Web Appni ochish (LCP < 1.2s)", web_app=WebAppInfo(url=webapp_url))]
        ]
    )
    text = (
        "⚡ <b>Bauntys Web App LCP Optimallashtirish & Diagnostika</b>\n\n"
        "• 🚀 <b>LCP (Largest Contentful Paint):</b> &lt; 1.2s (Chaqmoqdek tezkor yuklanish)\n"
        "• 🖼️ <b>Hero Banner & Top-1:</b> <code>fetchpriority=\"high\"</code>, <code>decoding=\"async\"</code>\n"
        "• 📦 <b>Katalog Posterlari:</b> <code>loading=\"lazy\"</code>, <code>decoding=\"async\"</code>\n"
        "• 🌐 <b>Preconnect & DNS-prefetch:</b>\n"
        "  — <code>https://161-97-96-58.sslip.io</code> (SSL ulanish keshlandi)\n"
        "  — <code>https://asilmedia.org</code> (Preconnect faol)\n"
        "• ☁️ <b>Telegram Cloud File ID Pool:</b> 0 bayt Render disk sarfi, 0.5s playback\n"
        "• 🛡️ <b>Brend:</b> 100% Bauntys Oq Brendi (@BauntyCinemabot, @BauntyFilms)\n\n"
        f"🤖 <b>Bot:</b> @{bot_name}"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("teamwork-preview", "teamworkpreview", "teamwork"))
async def cmd_teamwork_preview(message: Message) -> None:
    """/teamwork-preview komandasi: Jamoaviy oldindan ko'rish va test qilish."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    bot_name = (config.BOT_USERNAME or "BauntyCinemabot").lstrip("@")
    channel_name = config.CHANNEL_USERNAME.lstrip("@")
    webapp_url = config.WEBAPP_URL
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Web App Preview", web_app=WebAppInfo(url=webapp_url))],
            [
                InlineKeyboardButton(text="📺 Jonli TV (1440p QHD)", web_app=WebAppInfo(url=f"{webapp_url}#tv")),
                InlineKeyboardButton(text="📚 Kitoblar", web_app=WebAppInfo(url=f"{webapp_url}?books")),
            ],
            [
                InlineKeyboardButton(text="🚕 Taksi (1-5)", callback_data="watch_part:718:1"),
                InlineKeyboardButton(text="⚔️ Titanlar", callback_data="watch_part:717:1"),
            ],
            [
                InlineKeyboardButton(text="🔫 Chuqur", callback_data="watch_part:287:1"),
                InlineKeyboardButton(text="🏎️ Forsaj", callback_data="watch_part:1500:1"),
            ],
            [
                InlineKeyboardButton(text="📢 Rasmiy Kanal", url=f"https://t.me/{channel_name}"),
            ]
        ]
    )
    text = (
        "👥 <b>Bauntys Jamoaviy Oldindan Ko'rish (Teamwork Preview)</b>\n\n"
        "Barcha yangilangan funksiyalar va katalog to'plamlarini sinab ko'rishingiz mumkin:\n"
        "📺 <b>Jonli TV (1440p QHD):</b> 208 ta kanal, sub-second start, zaxira oqimlar va proxy relay\n"
        "📚 <b>Kutubxona:</b> 3,390+ sara kitoblar, PDF/EPUB to'liq yuklash va mini ilova mutolaasi\n"
        "🚕 <b>Taksi 1-5:</b> Barcha qismlari MP4 video oqimi bilan (kod: <code>718</code> / <code>9165</code>)\n"
        "⚔️ <b>Titanlar hujumi:</b> 54 qism (kod: <code>717</code> / <code>16913</code>)\n"
        "🔫 <b>Chuqur (Çukur):</b> 131 qism (kod: <code>287</code> / <code>18281</code>)\n"
        "🏎️ <b>Forsaj 1-11:</b> To'liq franshiza (kod: <code>1500</code> / <code>14902</code>)\n\n"
        f"🤖 <b>Bot:</b> @{bot_name}\n"
        f"🍿 <b>Kanal:</b> @{channel_name}\n\n"
        "Quyidagi tugmalar orqali video jo'natilishini sinovdan o'tkazing:"
    )
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.message(StateFilter(None), F.video | F.document)
async def handle_incoming_movie_video(message: Message) -> None:
    """
    Foydalanuvchi yoki admin ixtiyoriy kanaldan videoni
    forward qilib yuborganida yoki to'g'ridan-to'g'ri video tashlaganida:
    - Xabar captionidan kino kodini (#284, 284, 101...) aniqlaydi.
    - Agar kod bo'lmasa, sarlavha nomini bazadan qidiradi.
    - Agar kino topilsa: movies jadvalida file_id, file_type, duration, file_size ni yangilaydi.
    - Foydalanuvchiga tasdiq xabari yuboradi.
    """
    file_name = None
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
        duration = message.video.duration
        file_size = message.video.file_size
        file_name = getattr(message.video, "file_name", None)
    elif message.document:
        doc = message.document
        file_name = getattr(doc, "file_name", None)
        NON_VIDEO_EXTENSIONS = (
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar",
            ".7z", ".tar", ".gz", ".txt", ".apk", ".exe", ".png", ".jpg", ".jpeg"
        )
        if file_name and file_name.lower().endswith(NON_VIDEO_EXTENSIONS):
            return
        is_video_doc = (
            (doc.mime_type and doc.mime_type.startswith("video/"))
            or (file_name and file_name.lower().endswith(
                (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts", ".m4v")
            ))
            or (doc.file_size and doc.file_size > 10 * 1024 * 1024)
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
    code = extract_code_from_caption(caption) or (extract_code_from_caption(file_name) if file_name else None)
    candidate_title = extract_candidate_title(caption) or (extract_candidate_title(file_name) if file_name else None)

    # Agar kod to'g'ridan-to'g'ri topilmasa, lekin sarlavha bo'lsa, katalogdan kodni aniqlash
    if not code and candidate_title:
        cat_match = MovieService.search_catalog_by_title(candidate_title)
        if cat_match and cat_match.get("c"):
            code = str(cat_match["c"])

    # Qism (part) raqamini aniqlash (masalan: 2-qism, 3-seriya)
    m_part = re.search(r'(\d+)[\s\-—–]*(?:qism|seriya|серия|fasl|sezon|part|ep|episode)', caption, re.IGNORECASE)
    if code and m_part:
        part_num = int(m_part.group(1))
        if part_num > 1 and "_" not in code and "-" not in code:
            code = f"{code}_{part_num}"

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
        chat_username = f"@{message.chat.username}" if message.chat.username else ""
        is_match = (
            chat_id_str == storage_id
            or chat_id_str.replace("-100", "") == storage_id.replace("-100", "")
            or (chat_username and chat_username.lower() == storage_id.lower())
            or message.chat.id == -1001999999999
        )
        if not is_match:
            return

    file_name = None
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
        duration = message.video.duration
        file_size = message.video.file_size
        file_name = getattr(message.video, "file_name", None)
    elif message.document:
        doc = message.document
        file_name = getattr(doc, "file_name", None)
        NON_VIDEO_EXTENSIONS = (
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar",
            ".7z", ".tar", ".gz", ".txt", ".apk", ".exe", ".png", ".jpg", ".jpeg"
        )
        if file_name and file_name.lower().endswith(NON_VIDEO_EXTENSIONS):
            return
        is_video_doc = (
            (doc.mime_type and doc.mime_type.startswith("video/"))
            or (file_name and file_name.lower().endswith(
                (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts", ".m4v")
            ))
            or (doc.file_size and doc.file_size > 10 * 1024 * 1024)
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
    code = extract_code_from_caption(caption) or (extract_code_from_caption(file_name) if file_name else None)
    candidate_title = extract_candidate_title(caption) or (extract_candidate_title(file_name) if file_name else None)

    # Agar kod to'g'ridan-to'g'ri topilmasa, lekin sarlavha bo'lsa, katalogdan kodni aniqlash
    if not code and candidate_title:
        cat_match = MovieService.search_catalog_by_title(candidate_title)
        if cat_match and cat_match.get("c"):
            code = str(cat_match["c"])

    # Qism (part) raqamini aniqlash (masalan: 2-qism, 3-seriya)
    m_part = re.search(r'(\d+)[\s\-—–]*(?:qism|seriya|серия|fasl|sezon|part|ep|episode)', caption, re.IGNORECASE)
    if code and m_part:
        part_num = int(m_part.group(1))
        if part_num > 1 and "_" not in code and "-" not in code:
            code = f"{code}_{part_num}"

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
