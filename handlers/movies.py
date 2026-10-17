"""
Kino bo'limi qayta ishlovchisi (Kino kodi, qidiruv, janrlar, tasodifiy kino)
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from services.movie_service import movie_service
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


@router.message(F.text == "🎬 Kino")
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
        movies = await movie_service.get_by_genre(session, genre, limit=10)
        if not movies:
            await callback.message.answer(
                f"😔 <b>«{genre}»</b> janrida hozircha kinolar topilmadi.\n"
                f"🍿 Barcha kinolar: {config.CHANNEL_USERNAME}",
                parse_mode="HTML"
            )
            return

        text = f"🎭 <b>«{genre}» janridagi kinolar:</b>\nKo'rmoqchi bo'lgan filmingizni tanlang:"
        markup = movie_list_keyboard(movies)
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
        markup = movie_list_keyboard(movies)
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("get_movie:"))
async def cb_get_movie_by_code(callback: CallbackQuery) -> None:
    """Ro'yxatdan tanlangan kinoni yuborish."""
    code = callback.data.split("get_movie:")[-1]
    await callback.answer("🎬 Kino yuklanmoqda...")

    async with get_session() as session:
        movie = await movie_service.find_by_code(session, code)
        if movie:
            await movie_service.send_movie_to_user(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                movie=movie,
                session=session
            )
        else:
            await callback.message.answer(format_movie_not_found(code), parse_mode="HTML")


@router.message(MovieSearchStates.waiting_for_code)
async def state_process_code(message: Message, state: FSMContext) -> None:
    """FSM holatida kiritilgan kodni qidirish."""
    code = message.text.strip()
    await state.clear()

    async with get_session() as session:
        movie = await movie_service.find_by_code(session, code)
        if movie:
            await movie_service.send_movie_to_user(
                bot=message.bot,
                chat_id=message.chat.id,
                movie=movie,
                session=session,
                reply_to_message_id=message.message_id
            )
        else:
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


@router.message(lambda msg: msg.text and msg.text.strip().isdigit())
async def process_numeric_movie_code(message: Message) -> None:
    """
    Foydalanuvchi faqat raqam (kino kodi) yuborganida avtomatik kinoni topib berish.
    Masalan: 123, 405, 1002
    """
    code = message.text.strip()
    async with get_session() as session:
        movie = await movie_service.find_by_code(session, code)
        if movie:
            await movie_service.send_movie_to_user(
                bot=message.bot,
                chat_id=message.chat.id,
                movie=movie,
                session=session,
                reply_to_message_id=message.message_id
            )
        else:
            await message.reply(format_movie_not_found(code), parse_mode="HTML")
