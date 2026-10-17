"""
Admin boshqaruv paneli (Statistika, Kinolar boshqaruvi, Xabarnoma, Homiylar)
"""
import asyncio
import logging
from typing import Dict, Any, List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
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
)
from utils.states import (
    MovieAddStates,
    MovieDeleteStates,
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
        "👑 <b>Zakirovs_bot Boshqaruv Paneli</b>\n\n"
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
        "3-qadam: Endi kinoning <b>video faylini</b> (yoki hujjat ko'rinishida) botga yuboring:",
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


@router.callback_query(F.data.startswith("admin:movie:list:"))
async def cb_admin_movie_list(callback: CallbackQuery) -> None:
    """Kinolar ro'yxatini ko'rsatish."""
    if not is_admin_check(callback.from_user.id):
        return

    page = int(callback.data.split(":")[-1])
    async with get_session() as session:
        total = await crud.get_total_movies_count(session)
        movies = await crud.get_all_movies(session, limit=10, offset=page * 10)

    if not movies:
        await callback.message.answer("Bazada kinolar mavjud emas.")
        await callback.answer()
        return

    lines = [f"📋 <b>Kinolar ro'yxati ({page+1}-sahifa, jami: {total}):</b>\n"]
    for m in movies:
        lines.append(f"• <code>{m.code}</code> | <b>{m.title}</b> ({m.views_count} ko'rildi)")

    await callback.message.answer("\n".join(lines), parse_mode="HTML")
    await callback.answer()


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
