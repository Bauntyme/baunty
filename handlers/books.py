"""Kitoblar va Kutubxona bo'limi handlerlari (Books Handlers).

Foydalanuvchilarga kitoblar katalogini ko'rsatish, kitob qidirish,
va kitobni to'liq PDF formatida yuklab berish.
To'liq oq brendlangan: Baunty Films, @BauntyCinemabot.
"""

from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import config
from services import book_service

logger = logging.getLogger(__name__)

router = Router(name="books")


def get_books_main_keyboard() -> InlineKeyboardMarkup:
    """Kutubxona bosh inline klaviaturasi."""
    bot_user = config.BOT_USERNAME.lstrip("@")
    webapp_url = f"{config.WEBAPP_URL}?books" if config.WEBAPP_URL else None

    buttons = []
    if webapp_url:
        buttons.append([
            InlineKeyboardButton(text="📚 Kutubxonani ochish (Ilova)", web_app=WebAppInfo(url=webapp_url))
        ])

    buttons.append([
        InlineKeyboardButton(text="🔥 Ommabop kitoblar", callback_data="books:pop"),
        InlineKeyboardButton(text="📖 Badiiy adabiyot", callback_data="books:cat:badiiy"),
    ])
    buttons.append([
        InlineKeyboardButton(text="💼 Biznes & Moliya", callback_data="books:cat:biznes"),
        InlineKeyboardButton(text="🧠 Psixologiya", callback_data="books:cat:psixologiya"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🕌 Diniy & Ma'rifiy", callback_data="books:cat:diniy"),
        InlineKeyboardButton(text="🧸 Bolalar uchun", callback_data="books:cat:bolalar"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("books", "kitob", "kutubxona"))
@router.message(F.text.in_([
    "📚 Kitoblar", "📚 Kitob", "Kitoblar", "Kutubxona",
    "📚 Китоблар", "📚 Китоб", "Китоблар",
    "📚 Книги", "📚 Книга", "Книги"
]))
async def cmd_books(message: Message) -> None:
    from services.maintenance_service import maintenance_service
    from keyboards.default import maintenance_menu_keyboard
    if not config.is_admin(message.from_user.id) and (maintenance_service.is_global_maintenance() or maintenance_service.is_page_maintenance("books")):
        msg = maintenance_service.get_page_message("books") if maintenance_service.is_page_maintenance("books") else maintenance_service.get_global_message()
        await message.answer(
            f"📚 <b>{msg}</b>\n\n<i>Kitoblar bo'limida texnik yangilanish olib borilmoqda. Tez orada qaytamiz!</i>",
            parse_mode="HTML",
            reply_markup=maintenance_menu_keyboard(is_admin=False),
            protect_content=True
        )
        return
    cat = book_service.get_catalog(limit=6)
    total = cat.get("total", 20)

    text = (
        f"📚 <b>Baunty Kutubxonasi — {total}+ Sara Elektron Kitoblar!</b>\n\n"
        f"Kutubxonamizda o'zbek va jahon adabiyoti durdonalari, shaxsiy rivojlanish, "
        f"biznes, psixologiya, diniy-ma'rifiy va bolalar uchun qiziqarli asarlar to'plangan.\n\n"
        f"📖 <b>Ilovada mutolaa:</b> Har bir kitobni to'g'ridan-to'g'ri qulay rejimda o'qishingiz "
        f"yoki PDF formatida chatga yuklab olishingiz mumkin!\n\n"
        f"<i>Quyidagi toifalardan birini tanlang yoki kitob nomini yozing:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_books_main_keyboard(), protect_content=True)


@router.callback_query(F.data == "books:main")
async def cb_books_main(call: CallbackQuery) -> None:
    """Kutubxona bosh menyusiga qaytish."""
    cat = book_service.get_catalog(limit=6)
    total = cat.get("total", 20)

    text = (
        f"📚 <b>Baunty Kutubxonasi — {total}+ Sara Elektron Kitoblar!</b>\n\n"
        f"Har bir kitobni to'g'ridan-to'g'ri qulay ilovada o'qishingiz "
        f"yoki PDF formatida chatga yuklab olishingiz mumkin!\n\n"
        f"<i>Quyidagi toifalardan birini tanlang:</i>"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_books_main_keyboard())
    await call.answer()


@router.callback_query(F.data.startswith("books:cat:") | (F.data == "books:pop"))
async def cb_books_category(call: CallbackQuery) -> None:
    """Toifa bo'yicha kitoblar ro'yxatini ko'rsatish."""
    if call.data == "books:pop":
        category = "pop"
        cat_title = "🔥 Ommabop kitoblar"
    else:
        category = call.data.split(":")[-1]
        cat_names = {
            "badiiy": "📖 Badiiy adabiyot",
            "biznes": "💼 Biznes & Moliya",
            "psixologiya": "🧠 Psixologiya",
            "diniy": "🕌 Diniy & Ma'rifiy",
            "tarix": "📜 Tarix & Fan",
            "bolalar": "🧸 Bolalar uchun",
        }
        cat_title = cat_names.get(category, "📚 Kitoblar")

    res = book_service.get_catalog(category=category, limit=10)
    items = res.get("items", [])

    if not items:
        await call.answer("Bu toifada hozircha kitoblar topilmadi", show_alert=True)
        return

    text = f"<b>{cat_title}</b> ({len(items)} ta kitob):\n\n"
    buttons = []

    for b in items:
        bid = b["id"]
        title = b["title"]
        author = b["author"]
        rating = b.get("rating", 4.9)
        text += f"• <b>{title}</b> — {author} (⭐ {rating})\n"
        buttons.append([
            InlineKeyboardButton(text=f"📥 {title} ({b.get('format', 'PDF')})", callback_data=f"book:dl:{bid}")
        ])

    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="books:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("book:dl:"))
async def cb_book_download(call: CallbackQuery) -> None:
    """Kitobni chatga yuklab berish."""
    bid = call.data.split(":")[-1]
    book = book_service.get_book_by_id(bid)
    if not book:
        await call.answer("Kitob topilmadi!", show_alert=True)
        return

    await call.answer("📥 Kitob tayyorlanmoqda va yuborilmoqda…")
    try:
        await book_service.deliver_book(
            bot=call.bot,
            chat_id=call.message.chat.id,
            book_id=bid
        )
    except Exception as e:
        logger.error(f"Kitob yetkazishda xatolik: {e}")
        await call.message.answer(f"⚠️ Kitobni yuborishda xatolik yuz berdi: {e}", protect_content=True)
