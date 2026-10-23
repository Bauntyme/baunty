"""
Admin boshqaruv paneli (Statistika, Kinolar boshqaruvi, Xabarnoma, Homiylar)
"""
import asyncio
import time
import logging
from typing import Dict, Any, List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from config import config
from database.session import get_session
from database import crud
from keyboards.default import main_menu_keyboard, cancel_keyboard, admin_reply_keyboard
from keyboards.inline import (
    admin_dashboard_keyboard,
    admin_movies_menu_keyboard,
    admin_sponsors_menu_keyboard,
    broadcast_confirm_keyboard,
    genre_picker_keyboard,
    movie_list_keyboard,
    admin_movie_detail_keyboard,
    movie_edit_keyboard,
    admin_settings_keyboard,
    admin_maintenance_main_keyboard,
    admin_maintenance_templates_keyboard,
    admin_maintenance_pages_keyboard,
    admin_maintenance_page_detail_keyboard,
)
from services.maintenance_service import (
    maintenance_service,
    MAINTENANCE_TEMPLATES,
    PAGE_EMOJIS,
    PAGE_NAMES,
)
from services.movie_service import movie_service

from utils.states import (
    MovieAddStates,
    MovieDeleteStates,
    MovieViewStates,
    MovieEditStates,
    MovieAsilmediaSyncStates,
    BroadcastStates,
    SponsorAddStates,
)
from utils.helpers import get_system_stats

logger = logging.getLogger(__name__)
router = Router(name="admin_router")


# Admin tekshiruvi filteri
def is_admin_check(user_id: int) -> bool:
    return config.is_admin(user_id)


@router.message(Command("admin"))
@router.message(F.text == "👑 Admin Panel")
async def cmd_admin_panel(message: Message, state: FSMContext) -> None:
    """Admin boshqaruv paneli asosiy ko'rinishi."""
    if not is_admin_check(message.from_user.id):
        await message.reply("⛔ <b>Kechirasiz, siz ushbu bo'limdan foydalana olmaysiz!</b>", parse_mode="HTML")
        return

    await state.clear()
    async with get_session() as session:
        total_users = await crud.get_total_users_count(session)
        today_users = await crud.get_today_users_count(session)
        active_24h = await crud.get_active_users_24h_count(session)
        total_movies = await crud.get_total_movies_count(session)
        total_downloads = await crud.get_total_downloads_count(session)

    sys_info = get_system_stats()

    text = (
        f"👑 <b>@{config.BOT_USERNAME.lstrip('@')} Boshqaruv Paneli</b>\n\n"
        "📊 <b>Asosiy statistika:</b>\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users:,}</b> ta\n"
        f"🆕 Bugun qo'shilganlar: <b>{today_users:,}</b> ta\n"
        f"⚡ 24 soatdagi faollar: <b>{active_24h:,}</b> ta\n"
        f"🎬 Jami yuklangan kinolar: <b>{total_movies:,}</b> ta\n"
        f"📥 Jami yuklab olishlar: <b>{total_downloads:,}</b> marta\n\n"
        "💻 <b>Server holati:</b>\n"
        f"🖥️ OS: <code>{sys_info.get('os')}</code>\n"
        f"🐍 Python: <code>{sys_info.get('python')}</code>\n"
        f"💾 Disk bo'sh joy: <code>{sys_info.get('disk_free')}</code>\n\n"
        "Kerakli bo'limni tanlang:"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=admin_dashboard_keyboard())


@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Admin menyusiga qaytish."""
    if not is_admin_check(callback.from_user.id):
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    await state.clear()
    async with get_session() as session:
        total_users = await crud.get_total_users_count(session)
        today_users = await crud.get_today_users_count(session)
        active_24h = await crud.get_active_users_24h_count(session)
        total_movies = await crud.get_total_movies_count(session)
        total_downloads = await crud.get_total_downloads_count(session)

    text = (
        "👑 <b>Admin Boshqaruv Paneli</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{total_users:,}</b>\n"
        f"🆕 Bugun: <b>+{today_users:,}</b>\n"
        f"⚡ Faol (24s): <b>{active_24h:,}</b>\n"
        f"🎬 Kinolar: <b>{total_movies:,}</b>\n"
        f"📥 Yuklamalar: <b>{total_downloads:,}</b>\n"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_dashboard_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_dashboard_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:close")
async def cb_admin_close(callback: CallbackQuery, state: FSMContext) -> None:
    """Admin panelni yopish."""
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Yopildi")


@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(callback: CallbackQuery) -> None:
    """Batafsil yuklamalar statistikasi."""
    if not is_admin_check(callback.from_user.id):
        return

    async with get_session() as session:
        stats = await crud.get_downloads_stats_by_platform(session)
        total = await crud.get_total_downloads_count(session)

    lines = ["📊 <b>Platformalar bo'yicha yuklamalar:</b>\n"]
    for platform, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"• <b>{platform.capitalize()}:</b> {count:,} marta")

    lines.append(f"\n📦 <b>Jami yuklamalar:</b> {total:,} marta")
    await callback.message.answer("\n".join(lines), parse_mode="HTML")
    await callback.answer()


# ==========================================
# KINOLAR BOSHQARUVI (ADMIN MOVIES)
# ==========================================

@router.callback_query(F.data == "admin:movies")
async def cb_admin_movies(callback: CallbackQuery) -> None:
    """Admin kinolar menyusi."""
    if not is_admin_check(callback.from_user.id):
        return

    async with get_session() as session:
        count = await crud.get_total_movies_count(session)

    text = (
        "🎬 <b>Kinolar boshqaruvi bo'limi</b>\n\n"
        f"Bazada jami kinolar soni: <b>{count}</b> ta\n\n"
        "Kerakli amalni tanlang:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_movies_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:movie:add")
async def cb_admin_movie_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Yangi kino qo'shish jarayonini boshlash."""
    if not is_admin_check(callback.from_user.id):
        return

    await state.set_state(MovieAddStates.waiting_for_code)
    text = (
        "➕ <b>Yangi kino qo'shish</b>\n\n"
        "1-qadam: Kinoning <b>kodini</b> kiriting (masalan: <code>105</code>):"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(MovieAddStates.waiting_for_code, F.text)
async def state_add_movie_code(message: Message, state: FSMContext) -> None:
    """Kino kodi kiritilganda tekshirish."""
    code = message.text.strip()
    async with get_session() as session:
        existing = await crud.get_movie_by_code(session, code)
        if existing:
            await message.reply(
                f"⚠️ <b>{code}</b> kodli kino allaqachon bazada mavjud (Nomi: {existing.title})!\n"
                "Iltimos, boshqa kod kiriting:",
                parse_mode="HTML"
            )
            return

    await state.update_data(code=code)
    await state.set_state(MovieAddStates.waiting_for_title)
    await message.reply(
        f"✅ Kod: <code>{code}</code>\n\n"
        "2-qadam: Kinoning <b>nomini</b> kiriting (masalan: <i>Qasoskorlar: Intiho</i>):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


@router.message(MovieAddStates.waiting_for_title, F.text)
async def state_add_movie_title(message: Message, state: FSMContext) -> None:
    """Kino nomi kiritilganda faylni so'rash."""
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(MovieAddStates.waiting_for_media)
    await message.reply(
        f"✅ Nomi: <b>{title}</b>\n\n"
        "3-qadam: Endi kinoning <b>video faylini</b> (yoki hujjat ko'rinishida) botga yuboring:\n"
        "<i>💡 Yoki Asilmedia.org dan avtomatik yuklash va bog'lash uchun <code>asilmedia</code> deb yozing:</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


@router.message(MovieAddStates.waiting_for_media, F.video | F.document)
async def state_add_movie_media(message: Message, state: FSMContext) -> None:
    """Kino videosi yoki hujjati kelganda file_id ni saqlash."""
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
        duration = message.video.duration
        file_size = message.video.file_size
    else:
        file_id = message.document.file_id
        file_type = "document"
        duration = None
        file_size = message.document.file_size

    await state.update_data(
        file_id=file_id,
        file_type=file_type,
        duration=duration,
        file_size=file_size,
        genres=[]
    )
    await state.set_state(MovieAddStates.waiting_for_genres)
    await message.reply(
        "✅ Video qabul qilindi!\n\n"
        "4-qadam: Kinoning <b>janrini</b> tanlang (yoki matn ko'rinishida yozing, masalan: <i>Jangari, Drama</i>):",
        parse_mode="HTML",
        reply_markup=genre_picker_keyboard()
    )


@router.message(MovieAddStates.waiting_for_media, F.text)
async def state_add_movie_media_text(message: Message, state: FSMContext) -> None:
    """Admin video fayli o'rniga Asilmedia havolasi yoki 'asilmedia' deb yozganda."""
    raw = message.text.strip()
    data = await state.get_data()
    code = data.get("code")
    title = data.get("title")

    status_msg = await message.reply(
        f"⏳ <b>{title}</b> uchun Asilmedia.org dan video qidirilmoqda va tayyorlanmoqda...",
        parse_mode="HTML"
    )

    query_title = raw if (not raw.startswith("http") and raw.lower() not in ["asilmedia", "avto", "auto", "skip", "yoq", "yo'q"]) else title
    async with get_session() as session:
        sync_res = await movie_service.sync_movie_from_asilmedia(
            code=code,
            title=query_title,
            session=session,
            download_files=True
        )

    file_id = f"asilmedia_stream_{code}"
    file_type = "video"
    duration = None
    file_size = None

    if sync_res.get("success"):
        parts_cnt = len(sync_res.get("synced_parts", []))
        await status_msg.edit_text(
            f"✅ Asilmedia.org dan <b>{parts_cnt} ta qism</b> muvaffaqiyatli bog'landi va tayyorlandi!\n"
            f"🎬 Sarlavha: <b>{sync_res.get('title')}</b>",
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(
            f"ℹ️ Asilmedia.org dan to'g'ridan-to'g'ri topilmadi: {sync_res.get('error')}.\n"
            f"Video so'ralganda avtomatik uzatish uchun saqlandi.",
            parse_mode="HTML"
        )

    await state.update_data(
        file_id=file_id,
        file_type=file_type,
        duration=duration,
        file_size=file_size,
        genres=[]
    )
    await state.set_state(MovieAddStates.waiting_for_genres)
    await message.reply(
        "4-qadam: Kinoning <b>janrini</b> tanlang (yoki matn ko'rinishida yozing, masalan: <i>Jangari, Drama</i>):",
        parse_mode="HTML",
        reply_markup=genre_picker_keyboard()
    )


@router.callback_query(MovieAddStates.waiting_for_genres, F.data.startswith("pick_genre:"))
async def cb_pick_genre_step(callback: CallbackQuery, state: FSMContext) -> None:
    """Janr tanlash tugmalari bosilganda."""
    val = callback.data.split("pick_genre:")[-1]
    data = await state.get_data()
    genres: List[str] = data.get("genres", [])

    if val == "done":
        if not genres:
            genres = ["Barcha"]
        await state.update_data(genres_str=", ".join(genres))
        await state.set_state(MovieAddStates.waiting_for_year)
        await callback.message.answer(
            f"✅ Janrlar: <b>{', '.join(genres)}</b>\n\n"
            "5-qadam: Chiqarilgan <b>yilini</b> kiriting (masalan: <code>2024</code>) yoki o'tkazib yuborish uchun <code>yoq</code> deb yozing:",
            parse_mode="HTML",
            reply_markup=cancel_keyboard()
        )
        await callback.answer()
        return

    if val not in genres:
        genres.append(val)
        await state.update_data(genres=genres)
        await callback.answer(f"Qo'shildi: {val}")
    else:
        genres.remove(val)
        await state.update_data(genres=genres)
        await callback.answer(f"O'chirildi: {val}")


@router.message(MovieAddStates.waiting_for_genres, F.text)
async def state_add_movie_genres_text(message: Message, state: FSMContext) -> None:
    """Janr matn ko'rinishida yozilganda."""
    genres_str = message.text.strip()
    await state.update_data(genres_str=genres_str)
    await state.set_state(MovieAddStates.waiting_for_year)
    await message.reply(
        f"✅ Janr: <b>{genres_str}</b>\n\n"
        "5-qadam: Chiqarilgan <b>yilini</b> kiriting (masalan: <code>2024</code>) yoki <code>yoq</code>:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


@router.message(MovieAddStates.waiting_for_year, F.text)
async def state_add_movie_year(message: Message, state: FSMContext) -> None:
    """Kino yili kiritilganda."""
    val = message.text.strip()
    year = int(val) if val.isdigit() else None
    await state.update_data(year=year)
    await state.set_state(MovieAddStates.waiting_for_rating)
    year_str = str(year) if year else "Noma'lum"
    await message.reply(
        f"✅ Yili: <b>{year_str}</b>\n\n"
        "6-qadam: Kinoning <b>reytingini</b> kiriting (masalan: <code>8.5</code>) yoki <code>yoq</code>:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


@router.message(MovieAddStates.waiting_for_rating, F.text)
async def state_add_movie_rating(message: Message, state: FSMContext) -> None:
    """Kino reytingi kiritilganda."""
    val = message.text.strip().replace(",", ".")
    try:
        rating = float(val)
    except ValueError:
        rating = None

    await state.update_data(rating=rating)
    await state.set_state(MovieAddStates.waiting_for_description)
    await message.reply(
        f"✅ Reyting: <b>{rating or 'Belgilanmagan'}</b>\n\n"
        "7-qadam: Kino haqida qisqacha <b>tavsif</b> yozing yoki <code>yoq</code> deb yuboring:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


@router.message(MovieAddStates.waiting_for_description, F.text)
async def state_add_movie_finish(message: Message, state: FSMContext) -> None:
    """Tavsif kiritilib kino saqlanishi."""
    val = message.text.strip()
    description = None if val.lower() in ["yoq", "yo'q", "skip", "-"] else val

    data = await state.get_data()
    code = data["code"]
    title = data["title"]
    file_id = data["file_id"]
    file_type = data.get("file_type", "video")
    duration = data.get("duration")
    file_size = data.get("file_size")
    genres = data.get("genres_str", "Barcha")
    year = data.get("year")
    rating = data.get("rating")

    async with get_session() as session:
        movie = await crud.create_movie(
            session=session,
            code=code,
            title=title,
            file_id=file_id,
            description=description,
            file_type=file_type,
            duration=duration,
            file_size=file_size,
            genres=genres,
            year=year,
            rating=rating
        )

    await state.clear()
    movie_year_str = str(movie.year) if movie.year else "Noma'lum"
    success_text = (
        "🎉 <b>Kino muvaffaqiyatli saqlandi!</b>\n\n"
        f"🔢 Kod: <code>{movie.code}</code>\n"
        f"🎬 Nomi: <b>{movie.title}</b>\n"
        f"🎭 Janr: {movie.genres}\n"
        f"📅 Yili: {movie_year_str}\n\n"
        f"Foydalanuvchilar endi <code>{movie.code}</code> kodini yuborib ushbu kinoni yuklab olishlari mumkin!"
    )
    await message.reply(
        success_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=True)
    )


@router.callback_query(F.data == "admin:movie:delete")
async def cb_admin_movie_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """Kino o'chirishni boshlash."""
    if not is_admin_check(callback.from_user.id):
        return

    await state.set_state(MovieDeleteStates.waiting_for_code)
    await callback.message.answer(
        "🗑️ <b>O'chirmoqchi bo'lgan kinongiz kodini kiriting:</b>\nMasalan: <code>101</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(MovieDeleteStates.waiting_for_code, F.text)
async def state_delete_movie_confirm(message: Message, state: FSMContext) -> None:
    """Kino kodini o'chirish."""
    code = message.text.strip()
    await state.clear()

    async with get_session() as session:
        deleted = await crud.delete_movie(session, code)

    if deleted:
        await message.reply(
            f"✅ <b>{code}</b> kodli kino ma'lumotlar bazasidan butunlay o'chirildi!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=True)
        )
    else:
        await message.reply(
            f"❌ <b>{code}</b> kodli kino bazada topilmadi.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=True)
        )


@router.callback_query(F.data == "admin:movie:asilmedia_sync")
async def cb_admin_movie_asilmedia_sync(callback: CallbackQuery, state: FSMContext) -> None:
    """Asilmedia.org dan kino/serial qismlarini bog'lash."""
    if not is_admin_check(callback.from_user.id):
        return

    await state.set_state(MovieAsilmediaSyncStates.waiting_for_input)
    text = (
        "🌐 <b>Asilmedia.org orqali kinoni bog'lash</b>\n\n"
        "Kino kodini va (ixtiyoriy) nomini kiriting:\n"
        "Masalan:\n"
        "• <code>718</code> (Taksi 1..5)\n"
        "• <code>717</code> (Attack on Titan)\n"
        "• <code>287</code> (Chuqur)\n"
        "• <code>101 Forsaj</code>\n\n"
        "Asilmedia.org dan barcha qismlar va yuqori sifatli video oqimlari avtomatik topilib ulanadi!"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(MovieAsilmediaSyncStates.waiting_for_input, F.text)
async def state_movie_asilmedia_sync(message: Message, state: FSMContext) -> None:
    """Kino kodi va sarlavhasini Asilmediadan qidirib bog'lash."""
    raw = message.text.strip()
    await state.clear()

    parts = raw.split(maxsplit=1)
    code = parts[0]
    title = parts[1] if len(parts) > 1 else None

    status_msg = await message.reply(
        f"⏳ <b>#{code}</b> uchun Asilmedia.org dan qidirilmoqda va video qismlari tayyorlanmoqda...",
        parse_mode="HTML"
    )

    async with get_session() as session:
        res = await movie_service.sync_movie_from_asilmedia(
            code=code,
            title=title,
            session=session
        )

    if res.get("success"):
        parts_cnt = len(res.get("synced_parts", []))
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="▶️ Ko'rish (Test)", callback_data=f"get_movie:{code}")
        )
        text = (
            "🎉 <b>Asilmedia.org dan muvaffaqiyatli bog'landi!</b>\n\n"
            f"🔢 Kod: <code>{code}</code>\n"
            f"🎬 Nomi: <b>{res.get('title')}</b>\n"
            f"📺 Bog'langan qismlar: <b>{parts_cnt} ta</b>\n"
            f"🌐 Manba: Asilmedia.org\n\n"
            "Endi foydalanuvchilar 'Ko'rish' tugmasini bossa, video darhol uzatiladi!"
        )
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        err_msg = res.get('error') or "Noma'lum"
        await status_msg.edit_text(
            f"❌ <b>#{code}</b> uchun Asilmedia.org dan video topilmadi.\n"
            f"Sabab: {err_msg}",
            parse_mode="HTML"
        )


@router.message(Command("sync_asilmedia"))
async def cmd_sync_asilmedia(message: Message) -> None:
    """Admin buyrug'i: /sync_asilmedia 718 yoki /sync_asilmedia 718 Taksi"""
    if not is_admin_check(message.from_user.id):
        return

    args = message.text.split()[1:]
    if not args:
        await message.reply(
            "ℹ️ <b>Foydalanish:</b>\n<code>/sync_asilmedia 718</code> yoki <code>/sync_asilmedia 718 Taksi</code>",
            parse_mode="HTML"
        )
        return

    code = args[0]
    title = " ".join(args[1:]) if len(args) > 1 else None

    status_msg = await message.reply(
        f"⏳ <b>#{code}</b> Asilmedia.org dan qidirilmoqda...",
        parse_mode="HTML"
    )
    async with get_session() as session:
        res = await movie_service.sync_movie_from_asilmedia(code=code, title=title, session=session)

    if res.get("success"):
        parts_cnt = len(res.get("synced_parts", []))
        await status_msg.edit_text(
            f"✅ <b>#{code}</b> Asilmedia.org dan {parts_cnt} ta qism bilan muvaffaqiyatli bog'landi!\n"
            f"🎬 Nomi: <b>{res.get('title')}</b>",
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(
            f"❌ #{code} topilmadi: {res.get('error')}",
            parse_mode="HTML"
        )


@router.message(Command("sync_catalog_asilmedia"))
async def cmd_sync_catalog_asilmedia(message: Message) -> None:
    """Admin buyrug'i: katalogdagi mashhur kinolarni Asilmedia orqali sinxronlash."""
    if not is_admin_check(message.from_user.id):
        return
    args = message.text.split()[1:]
    pages = 5
    limit = 30
    if args and args[0].isdigit():
        pages = int(args[0])
        limit = max(pages * 10, 30)
    status_msg = await message.reply(
        f"⏳ Asilmedia.org ochiq API va katalog sahifalaridan ({pages} sahifa) barcha kino metadatalari sinxronlanmoqda...",
        parse_mode="HTML"
    )
    start_t = time.time()
    async with get_session() as session:
        count = await movie_service.sync_catalog_from_asilmedia(limit=limit, pages=pages, session=session)
    elapsed = round(time.time() - start_t, 2)
    await status_msg.edit_text(
        f"✅ Asilmedia.org dan <b>{count} ta</b> kino/serial muvaffaqiyatli sinxronlandi!\n\n"
        f"• 📄 <b>Ko'rib chiqilgan sahifalar:</b> {pages} ta\n"
        f"• 💾 <b>SQLite `movies` jadvali:</b> Yangilandi\n"
        f"• 📦 <b>data/catalog.json:</b> Keshlandi\n"
        f"• ⏱️ <b>Vaqt:</b> {elapsed} soniya",
        parse_mode="HTML"
    )


@router.message(Command("download_catalog_asilmedia"))
async def cmd_download_catalog_asilmedia(message: Message) -> None:
    """Admin buyrug'i: katalogdagi mashhur kinolarni (Taksi, Titans, Chuqur, Forsaj) Asilmedia orqali yuklab tayyorlash."""
    if not is_admin_check(message.from_user.id):
        return
    args = message.text.split()[1:]
    limit = int(args[0]) if args and args[0].isdigit() else 15
    status_msg = await message.reply(
        f"⏳ Asilmedia.org orqali {limit} ta katalog kinosini orqa fonda yuklab tayyorlash boshlandi...",
        parse_mode="HTML"
    )
    from services.movie_service import start_background_movie_preloader
    start_background_movie_preloader(limit=limit)
    await status_msg.edit_text(
        f"✅ <b>{limit} ta</b> katalog kinosini (Taksi 1..5, Titans, Chuqur, Forsaj...) orqa fonda yuklab tayyorlash muvaffaqiyatli ishga tushirildi!\n"
        "Barcha qismlar to'liq yuklanib, ko'rish tugmasi bosilganda darhol tezkor uzatiladi.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin:movie:list:"))
async def cb_admin_movie_list(callback: CallbackQuery) -> None:
    """Kinolar ro'yxatini ko'rsatish va sahifalash."""
    if not is_admin_check(callback.from_user.id):
        return

    import math
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    page = int(callback.data.split(":")[-1])
    async with get_session() as session:
        total = await crud.get_total_movies_count(session)
        movies = await crud.get_all_movies(session, limit=10, offset=page * 10)

    if not movies:
        await callback.message.answer("Bazada kinolar mavjud emas.")
        await callback.answer()
        return

    total_pages = max(1, math.ceil(total / 10))
    lines = [f"📋 <b>Kinolar ro'yxati ({page+1}/{total_pages}-sahifa, jami: {total}):</b>\n"]
    for m in movies:
        lines.append(f"• <code>{m.code}</code> | <b>{m.title}</b> ({m.views_count} ko'rildi)")

    builder = InlineKeyboardBuilder()
    for m in movies:
        builder.row(
            InlineKeyboardButton(
                text=f"🎬 {m.code} - {m.title[:25]}",
                callback_data=f"admin:movie:view_direct:{m.code}"
            )
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:movie:list:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:movie:list:{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Kinolar boshqaruvi", callback_data="admin:movies"))

    try:
        await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


async def show_admin_movie_detail(target_message: Message, code: str, is_edit: bool = False) -> None:
    """Kino haqidagi batafsil ma'lumotni admin uchun chiqarish."""
    async with get_session() as session:
        movie = await crud.get_movie_by_code(session, code)
    if not movie:
        await target_message.answer(f"❌ <code>{code}</code> kodli kino topilmadi.", parse_mode="HTML")
        return

    year_str = str(movie.year) if movie.year else "Noma'lum"
    rating_str = f"{movie.rating}/10" if movie.rating else "Baholanmagan"
    desc_str = movie.description or "Mavjud emas"
    text = (
        f"🎬 <b>Kino ma'lumotlari:</b>\n\n"
        f"🔢 Kod: <code>{movie.code}</code>\n"
        f"📌 Nomi: <b>{movie.title}</b>\n"
        f"🎭 Janri: {movie.genres}\n"
        f"📅 Yili: {year_str}\n"
        f"⭐ Reyting: {rating_str}\n"
        f"👁️ Ko'rishlar: {movie.views_count}\n"
        f"📥 Yuklashlar: {movie.downloads_count}\n"
        f"📁 Fayl turi: {movie.file_type}\n"
        f"📝 Tavsif: <i>{desc_str[:300]}</i>"
    )
    markup = admin_movie_detail_keyboard(movie.code)
    if is_edit:
        try:
            await target_message.edit_text(text, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            pass
    await target_message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "admin:movie:view")
async def cb_admin_movie_view(callback: CallbackQuery, state: FSMContext) -> None:
    """Kino kodini so'rab ko'rish."""
    if not is_admin_check(callback.from_user.id):
        return
    await state.set_state(MovieViewStates.waiting_for_code)
    await callback.message.answer(
        "🔍 <b>Ko'rmoqchi bo'lgan kinongiz kodini kiriting:</b>\nMasalan: <code>101</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(MovieViewStates.waiting_for_code, F.text)
async def state_admin_movie_view_code(message: Message, state: FSMContext) -> None:
    """Kiritilgan kod bo'yicha kinoni ko'rsatish."""
    code = message.text.strip()
    await state.clear()
    await show_admin_movie_detail(message, code)


@router.callback_query(F.data.startswith("admin:movie:view_direct:"))
async def cb_admin_movie_view_direct(callback: CallbackQuery) -> None:
    """To'g'ridan-to'g'ri kino ma'lumotlarini ko'rsatish."""
    if not is_admin_check(callback.from_user.id):
        return
    code = callback.data.split(":")[-1]
    await show_admin_movie_detail(callback.message, code, is_edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:movie:del_direct:"))
async def cb_admin_movie_del_direct(callback: CallbackQuery) -> None:
    """Kinoni to'g'ridan-to'g'ri o'chirish."""
    if not is_admin_check(callback.from_user.id):
        return
    code = callback.data.split(":")[-1]
    async with get_session() as session:
        deleted = await crud.delete_movie(session, code)
    if deleted:
        await callback.answer(f"✅ {code} kodli kino o'chirildi!", show_alert=True)
        try:
            await callback.message.edit_text(
                f"✅ <b>{code}</b> kodli kino ma'lumotlar bazasidan o'chirildi.",
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        await callback.answer("❌ Kino topilmadi", show_alert=True)


@router.callback_query(F.data.startswith("admin:movie:edit:"))
async def cb_admin_movie_edit(callback: CallbackQuery) -> None:
    """Kinoni tahrirlash menyusini ko'rsatish."""
    if not is_admin_check(callback.from_user.id):
        return
    code = callback.data.split(":")[-1]
    text = f"✏️ <b>{code}</b> kodli kinoning qaysi ma'lumotini o'zgartirmoqchisiz?"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=movie_edit_keyboard(code))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=movie_edit_keyboard(code))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:medit:"))
async def cb_admin_medit_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Maydonni tahrirlash uchun yangi qiymat so'rash."""
    if not is_admin_check(callback.from_user.id):
        return
    parts = callback.data.split(":")
    field = parts[2]
    code = parts[3]
    await state.update_data(edit_code=code, edit_field=field)
    await state.set_state(MovieEditStates.waiting_for_new_value)

    field_names = {
        "title": "yangi nomini",
        "genres": "yangi janrini (masalan: Jangari, Komediya)",
        "year": "yangi chiqarilgan yilini (masalan: 2024)",
        "rating": "yangi reytingini (masalan: 8.5)",
        "desc": "yangi tavsifini",
        "media": "yangi video yoki hujjat faylini"
    }
    prompt = field_names.get(field, "yangi qiymatni")
    await callback.message.answer(
        f"✏️ <b>{code}</b> kodli kino uchun <b>{prompt}</b> kiriting yoki yuboring:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(MovieEditStates.waiting_for_new_value)
async def state_admin_medit_save(message: Message, state: FSMContext) -> None:
    """Yangi qiymat kelganda kinoni yangilash."""
    data = await state.get_data()
    code = data["edit_code"]
    field = data["edit_field"]
    await state.clear()

    update_kwargs = {}
    if field == "title" and message.text:
        update_kwargs["title"] = message.text.strip()
    elif field == "genres" and message.text:
        update_kwargs["genres"] = message.text.strip()
    elif field == "year" and message.text:
        val = message.text.strip()
        update_kwargs["year"] = int(val) if val.isdigit() else None
    elif field == "rating" and message.text:
        val = message.text.strip().replace(",", ".")
        try:
            update_kwargs["rating"] = float(val)
        except ValueError:
            update_kwargs["rating"] = None
    elif field == "desc" and message.text:
        val = message.text.strip()
        update_kwargs["description"] = None if val.lower() in ["yoq", "yo'q", "-"] else val
    elif field == "media":
        if message.video:
            update_kwargs["file_id"] = message.video.file_id
            update_kwargs["file_type"] = "video"
            update_kwargs["duration"] = message.video.duration
            update_kwargs["file_size"] = message.video.file_size
        elif message.document:
            update_kwargs["file_id"] = message.document.file_id
            update_kwargs["file_type"] = "document"
            update_kwargs["duration"] = None
            update_kwargs["file_size"] = message.document.file_size
        else:
            await message.reply("❌ Video yoki hujjat fayli yuborilmadi.")
            return

    async with get_session() as session:
        updated = await crud.update_movie(session, code, **update_kwargs)

    if updated:
        await message.reply(
            f"✅ <b>{code}</b> kodli kino muvaffaqiyatli yangilandi!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=True)
        )
        await show_admin_movie_detail(message, code)
    else:
        await message.reply(f"❌ <b>{code}</b> kodli kino topilmadi.")



# ==========================================
# HOMIYLAR BOSHQARUVI (SPONSOR CHANNELS)
# ==========================================

@router.callback_query(F.data == "admin:sponsors")
async def cb_admin_sponsors(callback: CallbackQuery) -> None:
    """Homiylar bo'limi."""
    if not is_admin_check(callback.from_user.id):
        return

    async with get_session() as session:
        channels = await crud.get_all_sponsor_channels(session)

    text = (
        "🔒 <b>Homiylar (Majburiy a'zolik kanallari) boshqaruvi:</b>\n\n"
        "Foydalanuvchilar botdan to'liq foydalanishi uchun ushbu kanallarga obuna bo'lishi shart.\n"
        "<i>Eslatma: Bot ushbu kanallarda admin bo'lishi kerak!</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_sponsors_menu_keyboard(channels))
    await callback.answer()


@router.callback_query(F.data == "admin:sponsor:add")
async def cb_admin_sponsor_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Homiy kanal qo'shish."""
    if not is_admin_check(callback.from_user.id):
        return

    await state.set_state(SponsorAddStates.waiting_for_channel_id)
    text = (
        "➕ <b>Homiy kanal qo'shish</b>\n\n"
        "1-qadam: Kanal ID sini yoki username sini yuboring:\n"
        "<i>Masalan: <code>-1001234567890</code> yoki <code>@kanal_nomi</code></i>"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(SponsorAddStates.waiting_for_channel_id, F.text)
async def state_sponsor_add_id(message: Message, state: FSMContext) -> None:
    """Kanal ID kiritilganda."""
    ch_id = message.text.strip()
    await state.update_data(channel_id=ch_id)
    await state.set_state(SponsorAddStates.waiting_for_title)
    await message.reply(
        f"✅ Kanal ID: <code>{ch_id}</code>\n\n"
        "2-qadam: Kanal <b>nomini</b> kiriting (masalan: <i>Kinolar Olami</i>):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


@router.message(SponsorAddStates.waiting_for_title, F.text)
async def state_sponsor_add_title(message: Message, state: FSMContext) -> None:
    """Kanal nomi kiritilganda."""
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(SponsorAddStates.waiting_for_link)
    await message.reply(
        f"✅ Nomi: <b>{title}</b>\n\n"
        "3-qadam: Kanal <b>taklif havolasini</b> (invite link) yuboring:\n"
        "<i>Masalan: https://t.me/+AbCdEfGhIjK yoki https://t.me/kanal_nomi</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


@router.message(SponsorAddStates.waiting_for_link, F.text)
async def state_sponsor_add_link(message: Message, state: FSMContext) -> None:
    """Kanal linki kiritilib saqlanishi."""
    link = message.text.strip()
    data = await state.get_data()
    ch_id = data["channel_id"]
    title = data["title"]

    async with get_session() as session:
        await crud.add_sponsor_channel(
            session=session,
            channel_id=ch_id,
            title=title,
            invite_link=link
        )

    await state.clear()
    await message.reply(
        f"✅ <b>{title}</b> kanali muvaffaqiyatli homiylar safiga qo'shildi!",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=True)
    )


@router.callback_query(F.data.startswith("admin:sponsor:delete:"))
async def cb_admin_sponsor_delete(callback: CallbackQuery) -> None:
    """Kanalni o'chirish."""
    ch_id = callback.data.split("admin:sponsor:delete:")[-1]
    async with get_session() as session:
        await crud.remove_sponsor_channel(session, ch_id)
        channels = await crud.get_all_sponsor_channels(session)

    await callback.answer("Kanal o'chirildi", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=admin_sponsors_menu_keyboard(channels))


@router.callback_query(F.data.startswith("admin:sponsor:toggle:"))
async def cb_admin_sponsor_toggle(callback: CallbackQuery) -> None:
    """Kanal holatini yoqish/o'chirish."""
    ch_id = callback.data.split("admin:sponsor:toggle:")[-1]
    async with get_session() as session:
        channels = await crud.get_all_sponsor_channels(session)
        target = next((c for c in channels if c.channel_id == ch_id), None)
        if target:
            await crud.toggle_sponsor_channel(session, ch_id, not target.is_active)
        channels = await crud.get_all_sponsor_channels(session)

    await callback.answer("Holat yangilandi")
    await callback.message.edit_reply_markup(reply_markup=admin_sponsors_menu_keyboard(channels))


# ==========================================
# GLOBAL XABARNOMA (BROADCAST)
# ==========================================

@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    """Xabarnoma yuborishni boshlash."""
    if not is_admin_check(callback.from_user.id):
        return

    await state.set_state(BroadcastStates.waiting_for_message)
    text = (
        "📢 <b>Barcha foydalanuvchilarga xabarnoma yuborish</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring (Matn, Rasm, Video, Ovozli xabar yoki Forward):\n"
        "Bot barcha faol foydalanuvchilarga ushbu xabarni tarqatadi."
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(BroadcastStates.waiting_for_message)
async def state_broadcast_receive_message(message: Message, state: FSMContext) -> None:
    """Xabar qabul qilinganda tasdiqlashni so'rash."""
    await state.update_data(
        broadcast_chat_id=message.chat.id,
        broadcast_message_id=message.message_id
    )
    await state.set_state(BroadcastStates.confirm)

    await message.reply(
        "👆 <b>Ushbu xabar barcha foydalanuvchilarga yuboriladi.</b>\n"
        "Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=broadcast_confirm_keyboard()
    )


@router.callback_query(BroadcastStates.confirm, F.data == "admin:broadcast:confirm")
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Xabarnomani tarqatishni boshlash."""
    data = await state.get_data()
    from_chat_id = data["broadcast_chat_id"]
    from_message_id = data["broadcast_message_id"]
    await state.clear()

    await callback.answer("📢 Xabarnoma boshlandi...")
    status_msg = await callback.message.reply("⏳ <b>Xabarnoma tarqatilmoqda...</b>", parse_mode="HTML")

    async with get_session() as session:
        user_ids = await crud.get_all_user_ids(session, include_banned=False)

    total = len(user_ids)
    success = 0
    fail = 0

    # Tarqatish
    for idx, u_id in enumerate(user_ids, 1):
        try:
            await bot.copy_message(
                chat_id=u_id,
                from_chat_id=from_chat_id,
                message_id=from_message_id
            )
            success += 1
        except Exception:
            fail += 1

        # Har 50 ta yuborilganda status yangilash
        if idx % 50 == 0 or idx == total:
            try:
                await status_msg.edit_text(
                    f"📢 <b>Xabarnoma yuborilmoqda...</b>\n\n"
                    f"✅ Yuborildi: {success}\n"
                    f"❌ Xatolik: {fail}\n"
                    f"📊 Jarayon: {idx}/{total} ({int(idx/total*100)}%)",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # Telegram limitlariga rioya qilish (soniyasiga ~25 xabar)
        await asyncio.sleep(0.04)

    finish_text = (
        "🎉 <b>Xabarnoma yakunlandi!</b>\n\n"
        f"👥 Jami foydalanuvchilar: {total}\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Yetib bormadi (bloklaganlar): {fail}"
    )
    await status_msg.edit_text(finish_text, parse_mode="HTML")


@router.callback_query(BroadcastStates.confirm, F.data == "admin:broadcast:cancel")
async def cb_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Xabarnomani bekor qilish."""
    await state.clear()
    await callback.answer("Bekor qilindi")
    await callback.message.edit_text("❌ Xabarnoma bekor qilindi.")


# ==========================================
# ADMIN SOZLAMALARI VA REPLY TUGMALAR
# ==========================================

@router.callback_query(F.data == "admin:settings")
async def cb_admin_settings(callback: CallbackQuery) -> None:
    """Admin sozlamalari ko'rinishi."""
    if not is_admin_check(callback.from_user.id):
        return

    async with get_session() as session:
        channel_name = await crud.get_setting(session, "channel_username", config.CHANNEL_USERNAME)

    text = (
        f"⚙️ <b>@{config.BOT_USERNAME.lstrip('@')} Tizim Sozlamalari:</b>\n\n"
        f"🤖 <b>Bot nomi:</b> @{config.BOT_USERNAME.lstrip('@')}\n"
        f"🍿 <b>Rasmiy kino kanali:</b> {channel_name}\n"
        f"💾 <b>Baza turi:</b> <code>{config.DB_TYPE}</code>\n"
        f"📦 <b>Max yuklash hajmi:</b> {config.MAX_FILE_SIZE_MB} MB\n"
        f"⚡ <b>Anti-flood oraliq:</b> {config.RATE_LIMIT_SECONDS}s\n"
        f"👑 <b>Adminlar soni:</b> {len(config.admin_ids)} ta\n"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_settings_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_settings_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:set:channel")
async def cb_admin_set_channel_info(callback: CallbackQuery) -> None:
    """Kanal sozlamasi haqida ma'lumot."""
    await callback.answer(f"Hozirgi kanal: {config.CHANNEL_USERNAME}", show_alert=True)


# Reply keyboard tugmalari uchun admin handlerlari
@router.message(F.text == "📊 Statistika")
async def reply_admin_stats(message: Message, state: FSMContext) -> None:
    await cmd_admin_panel(message, state)


@router.message(F.text == "🎬 Kinolar")
async def reply_admin_movies(message: Message) -> None:
    if not is_admin_check(message.from_user.id):
        return
    async with get_session() as session:
        count = await crud.get_total_movies_count(session)
    text = (
        "🎬 <b>Kinolar boshqaruvi bo'limi</b>\n\n"
        f"Bazada jami kinolar soni: <b>{count}</b> ta\n\n"
        "Kerakli amalni tanlang:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_movies_menu_keyboard())


@router.message(F.text == "📢 Xabarnoma")
async def reply_admin_broadcast(message: Message, state: FSMContext) -> None:
    if not is_admin_check(message.from_user.id):
        return
    await state.set_state(BroadcastStates.waiting_for_message)
    text = (
        "📢 <b>Barcha foydalanuvchilarga xabarnoma yuborish</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring (Matn, Rasm, Video, Ovozli xabar yoki Forward):\n"
        "Bot barcha faol foydalanuvchilarga ushbu xabarni tarqatadi."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(F.text == "🔒 Homiylar")
async def reply_admin_sponsors(message: Message) -> None:
    if not is_admin_check(message.from_user.id):
        return
    async with get_session() as session:
        channels = await crud.get_all_sponsor_channels(session)
    text = (
        "🔒 <b>Homiylar (Majburiy a'zolik kanallari) boshqaruvi:</b>\n\n"
        "Foydalanuvchilar botdan to'liq foydalanishi uchun ushbu kanallarga obuna bo'lishi shart.\n"
        "<i>Eslatma: Bot ushbu kanallarda admin bo'lishi kerak!</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_sponsors_menu_keyboard(channels))


@router.message(F.text == "⚙️ Sozlamalar")
async def reply_admin_settings(message: Message) -> None:
    if not is_admin_check(message.from_user.id):
        return
    async with get_session() as session:
        channel_name = await crud.get_setting(session, "channel_username", config.CHANNEL_USERNAME)
    text = (
        f"⚙️ <b>@{config.BOT_USERNAME.lstrip('@')} Tizim Sozlamalari:</b>\n\n"
        f"🤖 <b>Bot nomi:</b> @{config.BOT_USERNAME.lstrip('@')}\n"
        f"🍿 <b>Rasmiy kino kanali:</b> {channel_name}\n"
        f"💾 <b>Baza turi:</b> <code>{config.DB_TYPE}</code>\n"
        f"📦 <b>Max yuklash hajmi:</b> {config.MAX_FILE_SIZE_MB} MB\n"
        f"⚡ <b>Anti-flood oraliq:</b> {config.RATE_LIMIT_SECONDS}s\n"
        f"👑 <b>Adminlar soni:</b> {len(config.admin_ids)} ta\n"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_settings_keyboard())


# ==========================================
# 🛠️ PROFILAKTIKA VA YANGILANISH (MAINTENANCE)
# ==========================================

@router.callback_query(F.data == "admin:maint:menu")
async def cb_admin_maint_menu(callback: CallbackQuery) -> None:
    """Profilaktika boshqaruv asosiy menyusi."""
    if not is_admin_check(callback.from_user.id):
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    is_global = maintenance_service.is_global_maintenance()
    global_msg = maintenance_service.get_global_message()
    status_text = "🔴 <b>PROFILAKTIKA YOQILGAN (Tizim to'xtatilgan)</b>" if is_global else "🟢 <b>NORMAL ISHLAMOQDA (Faol)</b>"

    text = (
        "🛠️ <b>Profilaktika va Yangilanish Boshqaruvi</b>\n\n"
        f"📊 <b>Bot & Web App holati:</b> {status_text}\n"
        f"📝 <b>Amaldagi xabar:</b>\n<i>«{global_msg}»</i>\n\n"
        "💡 <i>Eslatma: Butun bot to'xtatilganda ham foydalanuvchilar uchun 3 ta muhim funksiya:\n"
        "• 🎵 Musiqa topish\n"
        "• ⭕️ Dumaloq video\n"
        "• 📥 Media yuklash\n"
        "to'xtovsiz ishlashda davom etadi!</i>\n\n"
        "Kerakli amalni tanlang:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_maintenance_main_keyboard(is_global))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_maintenance_main_keyboard(is_global))
    await callback.answer()


@router.callback_query(F.data == "admin:maint:global:pick")
async def cb_admin_maint_global_pick(callback: CallbackQuery) -> None:
    """Butun bot va Web Appni to'xtatish uchun 5 ta xabar shablonini ko'rsatish."""
    if not is_admin_check(callback.from_user.id):
        return

    text = (
        "🛑 <b>Butun tizimni profilaktikaga qo'yish</b>\n\n"
        "Foydalanuvchilar /start bosganda yoki Web App sahifalariga kirganda "
        "ko'rinishi kerak bo'lgan xabarni tanlang (5 ta tayyor variant):"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_maintenance_templates_keyboard("global"))
    await callback.answer()


@router.callback_query(F.data == "admin:maint:global:off")
async def cb_admin_maint_global_off(callback: CallbackQuery) -> None:
    """Butun tizim profilaktikasini o'chirish (Normal ishga qaytarish)."""
    if not is_admin_check(callback.from_user.id):
        return

    maintenance_service.set_global_maintenance(False)
    await callback.answer("✅ Profilaktika o'chirildi! Tizim to'liq ishga tushirildi.", show_alert=True)
    await cb_admin_maint_menu(callback)


@router.callback_query(F.data.startswith("admin:maint:set_tmpl:"))
async def cb_admin_maint_set_template(callback: CallbackQuery) -> None:
    """Tanlangan shablon xabarni biriktirish va profilaktikani yoqish."""
    if not is_admin_check(callback.from_user.id):
        return

    parts = callback.data.split(":")
    # callback_data: admin:maint:set_tmpl:<target>:<idx>
    if len(parts) >= 5:
        target = parts[3]
        try:
            idx = int(parts[4])
        except (IndexError, ValueError):
            idx = 0
    else:
        target = "global"
        idx = 0

    if target == "global":
        maintenance_service.set_global_maintenance(True, message_idx=idx)
        await callback.answer("✅ Butun bot va Web App profilaktikaga olindi!", show_alert=True)
        await cb_admin_maint_menu(callback)
    else:
        maintenance_service.set_page_maintenance(target, True, message_idx=idx)
        page_name = PAGE_NAMES.get(target, target)
        await callback.answer(f"✅ {page_name} sahifasi profilaktikaga olindi!", show_alert=True)
        await cb_admin_maint_page_detail(callback, override_page=target)


@router.callback_query(F.data == "admin:maint:pages")
async def cb_admin_maint_pages(callback: CallbackQuery) -> None:
    """10 ta Web App sahifasini alohida profilaktikaga qo'yish ro'yxati."""
    if not is_admin_check(callback.from_user.id):
        return

    state = maintenance_service.get_state()
    pages_state = state.get("pages", {})

    text = (
        "📱 <b>Alohida Web App sahifalarini boshqarish:</b>\n\n"
        "O'zingiz xohlagan sahifani tanlab, faqat o'sha bo'limni profilaktikaga qo'yishingiz mumkin.\n"
        "Qolgan barcha bo'limlar uzluksiz ishlayveradi!\n\n"
        "🟢 — Normal ishlamoqda\n"
        "🔴 — Profilaktikada (Yangilanishda)\n\n"
        "Boshqarish uchun sahifani bosing:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_maintenance_pages_keyboard(pages_state))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:maint:page:"))
async def cb_admin_maint_page_detail_query(callback: CallbackQuery) -> None:
    """Sahifa ustiga bosilganda uning tafsilotlarini ko'rsatish."""
    if not is_admin_check(callback.from_user.id):
        return
    page_id = callback.data.split("admin:maint:page:")[-1]
    await cb_admin_maint_page_detail(callback, override_page=page_id)


async def cb_admin_maint_page_detail(callback: CallbackQuery, override_page: str) -> None:
    page_id = override_page
    em = PAGE_EMOJIS.get(page_id, "📱")
    nm = PAGE_NAMES.get(page_id, page_id.capitalize())
    is_active = maintenance_service.is_page_maintenance(page_id)
    msg = maintenance_service.get_page_message(page_id)

    status_str = "🔴 <b>Profilaktika yoqilgan</b>" if is_active else "🟢 <b>Normal ishlamoqda</b>"

    text = (
        f"{em} <b>{nm} sahifasi profilaktika sozlamasi</b>\n\n"
        f"📊 Holati: {status_str}\n"
        f"📝 Biriktirilgan xabar:\n<i>«{msg}»</i>\n\n"
        "Ushbu sahifa profilaktikasini o'zgartirish:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_maintenance_page_detail_keyboard(page_id, is_active))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:maint:page_pick:"))
async def cb_admin_maint_page_pick(callback: CallbackQuery) -> None:
    """Alohida sahifa uchun 5 ta xabar shablonidan birini tanlash."""
    if not is_admin_check(callback.from_user.id):
        return
    page_id = callback.data.split("admin:maint:page_pick:")[-1]
    nm = PAGE_NAMES.get(page_id, page_id)
    text = (
        f"📝 <b>{nm} sahifasi uchun profilaktika xabarini tanlang:</b>\n\n"
        "Quyidagi 5 ta tayyor xabardan birini bosing:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_maintenance_templates_keyboard(page_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:maint:page_off:"))
async def cb_admin_maint_page_off(callback: CallbackQuery) -> None:
    """Alohida sahifa profilaktikasini o'chirish."""
    if not is_admin_check(callback.from_user.id):
        return
    page_id = callback.data.split("admin:maint:page_off:")[-1]
    maintenance_service.set_page_maintenance(page_id, False)
    nm = PAGE_NAMES.get(page_id, page_id)
    await callback.answer(f"✅ {nm} sahifasi profilaktikadan chiqarildi!", show_alert=True)
    await cb_admin_maint_page_detail(callback, override_page=page_id)


# ==========================================
# 🔄 KESH & KATALOGNI SINXRONLASH
# ==========================================

@router.callback_query(F.data == "admin:cache:sync")
async def cb_admin_cache_sync(callback: CallbackQuery) -> None:
    """Upstream katalog bilan sinxronlash va barcha keshni tozalash."""
    if not is_admin_check(callback.from_user.id):
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    await callback.answer("⏳ Katalog va kesh yangilanmoqda...", show_alert=False)
    async with get_session() as session:
        synced = await movie_service.sync_catalog_from_upstream(session=session)
        total_movies = await crud.get_total_movies_count(session)

    # Web server keshlarini tozalash
    try:
        from services import web_server
        web_server._UPSTREAM_API_CACHE.clear()
        web_server._FX_CACHE = {"data": None, "ts": 0}
        web_server._CATALOG_CACHE = {"data": None, "ts": 0}
    except Exception:
        pass

    text = (
        "✅ <b>Katalog va Kesh muvaffaqiyatli yangilandi!</b>\n\n"
        f"🎬 Yangilangan/ko'rib chiqilgan kinolar: <b>{synced}</b> ta\n"
        f"📦 Bazadagi jami kinolar: <b>{total_movies}</b> ta\n"
        "⚡ API va valyuta keshlar tozalandi."
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin:menu"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())


# ==========================================
# 🖥️ SERVER & TIZIM HOLATI (HEALTH)
# ==========================================

@router.callback_query(F.data == "admin:server:health")
async def cb_admin_server_health(callback: CallbackQuery) -> None:
    """Server, xotira va tizim resurslari holatini ko'rsatish."""
    if not is_admin_check(callback.from_user.id):
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    import os
    import sys
    import platform

    mem_mb = "N/A"
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_mb = f"{process.memory_info().rss / 1024 / 1024:.1f} MB"
    except Exception:
        pass

    async with get_session() as session:
        u_count = await crud.get_total_users_count(session)
        m_count = await crud.get_total_movies_count(session)
        d_count = await crud.get_total_downloads_count(session)

    maint_status = "🔴 Profilaktika" if maintenance_service.is_global_maintenance() else "🟢 Faol (Normal)"

    text = (
        "🖥️ <b>Server va Tizim Salomatligi:</b>\n\n"
        f"🟢 <b>Status:</b> Onlayn va barqaror\n"
        f"🛠️ <b>Rejim:</b> {maint_status}\n"
        f"💾 <b>Baza:</b> <code>{config.DB_TYPE}</code>\n"
        f"🧠 <b>Python:</b> {platform.python_version()} ({platform.system()})\n"
        f"📊 <b>Bot RAM sarfi:</b> {mem_mb}\n"
        f"🌐 <b>Web App Port:</b> {config.PORT}\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {u_count:,} ta\n"
        f"🎬 <b>Kinolar:</b> {m_count:,} ta\n"
        f"📥 <b>Jami yuklamalar:</b> {d_count:,} marta"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:server:health"),
        InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin:menu"),
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


