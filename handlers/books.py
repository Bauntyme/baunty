"""Kitoblar va Kutubxona bo'limi handlerlari (Books Handlers).

Foydalanuvchilarga kitoblar katalogini ko'rsatish, toifalar, sahifalash (pagination),
nom va muallif bo'yicha qidirish, mutolaa (read) hamda kitobni to'liq PDF va EPUB
formatlarida chatga yetkazish.
To'liq oq brendlangan: Baunty Films, @BauntyCinemabot.
"""

from __future__ import annotations

import html
import logging
import math
import re
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import config
from services import book_service
from utils.states import BookStates

logger = logging.getLogger(__name__)

router = Router(name="books")

CAT_NAMES = {
    "badiiy": "📖 Badiiy adabiyot",
    "biznes": "💼 Biznes & Moliya",
    "psixologiya": "🧠 Psixologiya",
    "diniy": "🕌 Diniy & Ma'rifiy",
    "tarix": "📜 Tarix & Fan",
    "bolalar": "🧸 Bolalar uchun",
    "pop": "🔥 Ommabop kitoblar",
}

PAGE_SIZE = 5


def safe_html(text: Any) -> str:
    """Telegram HTML parse mode uchun faqat &, <, > belgilarini xavfsiz qilish (quote=False)."""
    return html.escape(str(text), quote=False)


def get_books_main_keyboard() -> InlineKeyboardMarkup:
    """Kutubxona bosh inline klaviaturasi."""
    webapp_url = f"{config.WEBAPP_URL}?books" if config.WEBAPP_URL else None

    buttons = []
    if webapp_url:
        buttons.append([
            InlineKeyboardButton(text="📚 Kutubxonani ochish (Ilova)", web_app=WebAppInfo(url=webapp_url))
        ])

    buttons.append([
        InlineKeyboardButton(text="🔥 Ommabop kitoblar", callback_data="book:cat:pop:1"),
        InlineKeyboardButton(text="📖 Badiiy adabiyot", callback_data="book:cat:badiiy:1"),
    ])
    buttons.append([
        InlineKeyboardButton(text="💼 Biznes & Moliya", callback_data="book:cat:biznes:1"),
        InlineKeyboardButton(text="🧠 Psixologiya", callback_data="book:cat:psixologiya:1"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🕌 Diniy & Ma'rifiy", callback_data="book:cat:diniy:1"),
        InlineKeyboardButton(text="🧸 Bolalar uchun", callback_data="book:cat:bolalar:1"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🔍 Kitob qidirish", callback_data="books:search"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_book_item_card(book: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Kitob batafsil kartasi va interaktiv klaviaturasi."""
    bid = str(book.get("id") or book.get("i"))
    title = book.get("title") or book.get("t") or "Kitob"
    author = book.get("author") or book.get("a") or "Noma'lum muallif"
    cat_code = book.get("category") or book.get("g") or "badiiy"
    cat_name = CAT_NAMES.get(cat_code, book.get("category_name", "Badiiy adabiyot"))
    pages = book.get("pages") or book.get("p") or 120
    rating = book.get("rating") or book.get("r") or 4.9
    size_mb = book.get("size_mb", 2.5)
    desc = book.get("description") or book.get("desc") or ""
    short_desc = (desc[:280] + "…") if len(desc) > 280 else desc

    safe_title = safe_html(title)
    safe_author = safe_html(author)
    safe_cat_name = safe_html(cat_name)
    safe_desc = safe_html(short_desc)

    text = (
        f"📚 <b>{safe_title}</b>\n\n"
        f"✍️ <b>Muallif:</b> {safe_author}\n"
        f"📂 <b>Toifa:</b> {safe_cat_name}\n"
        f"📄 <b>Sahifalar:</b> {pages} bet | 💾 <b>Format:</b> PDF & EPUB ({size_mb} MB)\n"
        f"⭐ <b>Reyting:</b> {rating} / 5.0\n\n"
        f"📖 <b>Qisqacha mazmuni:</b>\n<i>{safe_desc}</i>\n\n"
        f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} • {config.CHANNEL_USERNAME}</b>"
    )

    webapp_url = f"{config.WEBAPP_URL}?books&b={bid}" if config.WEBAPP_URL else None
    buttons = [
        [
            InlineKeyboardButton(text="📥 PDF yuklab olish", callback_data=f"book:pdf:{bid}"),
            InlineKeyboardButton(text="📱 EPUB yuklab olish", callback_data=f"book:epub:{bid}"),
        ],
        [
            InlineKeyboardButton(text="📖 Mutolaa (Parcha)", callback_data=f"book:read:{bid}"),
        ]
    ]
    if webapp_url:
        buttons.append([
            InlineKeyboardButton(text="🌐 Ilovada to'liq o'qish", web_app=WebAppInfo(url=webapp_url))
        ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Toifaga qaytish", callback_data=f"book:cat:{cat_code}:1"),
        InlineKeyboardButton(text="📚 Bosh menyu", callback_data="books:main"),
    ])
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


def format_category_page(category: str, page: int = 1) -> tuple[str, InlineKeyboardMarkup]:
    """Toifa bo'yicha sahifalangan kitoblar ro'yxati."""
    cat_title = CAT_NAMES.get(category, "📚 Kitoblar")
    safe_cat_title = safe_html(cat_title)
    res = book_service.get_catalog(category=category, limit=200)
    all_items = res.get("items", [])
    total_items = len(all_items)

    if total_items == 0:
        text = f"<b>{safe_cat_title}</b>\n\n<i>Bu toifada hozircha kitoblar mavjud emas.</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Orqaga", callback_data="books:main")]])
        return text, kb

    total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * PAGE_SIZE
    page_items = all_items[start_idx : start_idx + PAGE_SIZE]

    text = f"<b>{safe_cat_title}</b> ({total_items} ta kitob):\n\n"
    buttons = []

    for b in page_items:
        bid = str(b.get("id") or b.get("i"))
        title = b.get("title") or b.get("t") or "Kitob"
        author = b.get("author") or b.get("a") or ""
        rating = b.get("rating") or b.get("r") or 4.9
        safe_t = safe_html(title)
        safe_a = safe_html(author)
        text += f"• <b>{safe_t}</b> — {safe_a} (⭐ {rating})\n"
        buttons.append([
            InlineKeyboardButton(text=f"📖 {title[:24]}", callback_data=f"book:item:{bid}"),
            InlineKeyboardButton(text="📥 Yuklash", callback_data=f"book:dl:{bid}"),
        ])

    # Sahifalash (pagination) tugmalari
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"book:cat:{category}:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"book:cat:{category}:{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton(text="🔍 Qidiruv", callback_data="books:search"),
        InlineKeyboardButton(text="◀️ Bosh menyu", callback_data="books:main")
    ])
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


def format_search_results(query: str, items: list) -> tuple[str, InlineKeyboardMarkup]:
    """Qidiruv natijalarini formatlash."""
    safe_query = safe_html(query)
    if not items:
        text = (
            f"🔍 <b>«{safe_query}» bo'yicha hech qanday kitob topilmadi.</b>\n\n"
            f"Kitob nomi yoki muallifini to'g'ri yozganingizga ishonch hosil qiling, "
            f"yoki quyidagi toifalardan birini ko'rib chiqing:"
        )
        return text, get_books_main_keyboard()

    if len(items) == 1:
        return format_book_item_card(items[0])

    text = f"📚 <b>«{safe_query}» bo'yicha topilgan kitoblar ({len(items)} ta):</b>\n\n"
    buttons = []
    for b in items[:8]:
        bid = str(b.get("id") or b.get("i"))
        title = b.get("title") or b.get("t") or "Kitob"
        author = b.get("author") or b.get("a") or ""
        rating = b.get("rating") or b.get("r") or 4.9
        safe_t = safe_html(title)
        safe_a = safe_html(author)
        text += f"• <b>{safe_t}</b> — {safe_a} (⭐ {rating})\n"
        buttons.append([
            InlineKeyboardButton(text=f"📖 {title[:24]}", callback_data=f"book:item:{bid}"),
            InlineKeyboardButton(text="📥 Yuklash", callback_data=f"book:dl:{bid}"),
        ])

    buttons.append([InlineKeyboardButton(text="◀️ Kutubxonaga qaytish", callback_data="books:main")])
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("books", "book", "kitob", "kutubxona", "library"))
@router.message(F.text.lower().in_([
    "📚 kitoblar", "📚 kitob", "kitoblar", "kitob", "kutubxona",
    "📚 китоблар", "📚 китоб", "китоблар", "китоб", "кутубхона",
    "📚 книги", "📚 книга", "книги", "книга",
    "📚 books", "📚 book", "books", "book", "library"
]))
async def cmd_books(message: Message, command: Optional[CommandObject] = None, state: Optional[FSMContext] = None) -> None:
    if state:
        await state.clear()
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

    # Agar buyruq bilan argument yuborilgan bo'lsa (masalan: /kitob O'tkan kunlar)
    query = ""
    if command and command.args:
        query = command.args.strip()
    elif message.text:
        m = re.match(r"^/(?:books|book|kitob|kutubxona|library)(?:@\w+)?\s+(.+)$", message.text, re.IGNORECASE)
        if m:
            query = m.group(1).strip()

    if query:
        matched = book_service.search_books(query, limit=10)
        text, kb = format_search_results(query, matched)
        await message.answer(text, parse_mode="HTML", reply_markup=kb, protect_content=True)
        return

    cat = book_service.get_catalog(limit=6)
    total = cat.get("total", 32)

    text = (
        f"📚 <b>Baunty Kutubxonasi — {total}+ Sara Elektron Kitoblar!</b>\n\n"
        f"Kutubxonamizda o'zbek va jahon adabiyoti durdonalari, shaxsiy rivojlanish, "
        f"biznes, psixologiya, diniy-ma'rifiy va bolalar uchun sara asarlar to'plangan.\n\n"
        f"📖 <b>Ilovada mutolaa:</b> Har bir kitobni to'g'ridan-to'g'ri qulay rejimda o'qishingiz "
        f"yoki to'liq PDF va EPUB formatida chatga yuklab olishingiz mumkin!\n\n"
        f"<i>Quyidagi toifalardan birini tanlang yoki kitob nomini yozing:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_books_main_keyboard(), protect_content=True)


@router.message(BookStates.waiting_for_query, F.text)
async def state_process_book_query(message: Message, state: FSMContext) -> None:
    """Foydalanuvchi qidiruv tugmasini bosgandan so'ng kiritgan so'rovni qidirish."""
    query = (message.text or "").strip()
    await state.clear()
    if not query:
        return
    matched = book_service.search_books(query, limit=10)
    text, kb = format_search_results(query, matched)
    await message.answer(text, parse_mode="HTML", reply_markup=kb, protect_content=True)


@router.message(F.text.regexp(r'^(?:kitob|kitoblar|китоб|китоблар|kutubxona|кутубхона|books?|книг[аи])\s*[:\-—]?\s*(.+)$', flags=re.IGNORECASE))
async def msg_book_search(message: Message) -> None:
    """Matn orqali kitob qidirish (masalan: 'kitob O'tkan kunlar', 'китоб сариқ дев')."""
    m = re.match(r'^(?:kitob|kitoblar|китоб|китобlar|kutubxona|кутубхона|books?|книг[аи])\s*[:\-—]?\s*(.+)$', message.text, re.IGNORECASE)
    if not m:
        return
    query = m.group(1).strip()
    if not query:
        return
    matched = book_service.search_books(query, limit=10)
    text, kb = format_search_results(query, matched)
    await message.answer(text, parse_mode="HTML", reply_markup=kb, protect_content=True)


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery) -> None:
    """Faol bo'lmagan sahifalash tugmasi."""
    await call.answer()


@router.callback_query(F.data == "books:main")
async def cb_books_main(call: CallbackQuery, state: Optional[FSMContext] = None) -> None:
    """Kutubxona bosh menyusiga qaytish."""
    if state:
        await state.clear()
    cat = book_service.get_catalog(limit=6)
    total = cat.get("total", 32)

    text = (
        f"📚 <b>Baunty Kutubxonasi — {total}+ Sara Elektron Kitoblar!</b>\n\n"
        f"Har bir kitobni to'g'ridan-to'g'ri qulay ilovada o'qishingiz "
        f"yoki PDF va EPUB formatida chatga yuklab olishingiz mumkin!\n\n"
        f"<i>Quyidagi toifalardan birini tanlang yoki kitob nomini yozing:</i>"
    )
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_books_main_keyboard())
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.debug(f"edit_text error: {e}")
    await call.answer()


@router.callback_query((F.data == "books:search") | (F.data == "book:search"))
async def cb_books_search_prompt(call: CallbackQuery, state: Optional[FSMContext] = None) -> None:
    """Qidiruv bo'yicha yo'riqnoma berish va FSM holatini faollashtirish."""
    if state:
        await state.set_state(BookStates.waiting_for_query)
    text = (
        "🔍 <b>Kitob qidirish</b>\n\n"
        "Istalgan kitob yoki muallif nomini chatga yozing:\n"
        "• <i>O'tkan kunlar</i>\n"
        "• <i>Atom odatlar</i>\n"
        "• <i>Abdulla Qodiriy</i>\n"
        "• <i>kitob Alkimyogar</i>\n\n"
        "Bot darhol kerakli kitobni topib beradi!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Kutubxonaga qaytish", callback_data="books:main")]
    ])
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.debug(f"edit_text error: {e}")
    await call.answer()


@router.callback_query(
    F.data.startswith("book:cat:") |
    F.data.startswith("books:cat:") |
    (F.data == "books:pop") |
    (F.data == "book:pop")
)
async def cb_books_category(call: CallbackQuery) -> None:
    """Toifa bo'yicha kitoblar ro'yxatini ko'rsatish (sahifalash bilan)."""
    parts = call.data.split(":")
    if call.data in ("books:pop", "book:pop"):
        category = "pop"
        page = 1
    else:
        category = parts[2] if len(parts) >= 3 else parts[1]
        page = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 1

    text, kb = format_category_page(category, page)
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.debug(f"edit_text error: {e}")
    await call.answer()


@router.callback_query(F.data.startswith("book:item:") | F.data.startswith("books:item:"))
async def cb_book_item(call: CallbackQuery) -> None:
    """Kitob haqida batafsil ma'lumot va amal tugmalari."""
    bid = call.data.split(":")[-1]
    book = book_service.get_book_by_id(bid)
    if not book:
        await call.answer("Kitob topilmadi!", show_alert=True)
        return

    text, kb = format_book_item_card(book)
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.debug(f"edit_text error: {e}")
    await call.answer()


@router.callback_query(F.data.startswith("book:read:") | F.data.startswith("books:read:"))
async def cb_book_read(call: CallbackQuery) -> None:
    """Kitobdan parcha / mutolaa matnini ko'rsatish."""
    bid = call.data.split(":")[-1]
    book = book_service.get_book_by_id(bid)
    if not book:
        await call.answer("Kitob topilmadi!", show_alert=True)
        return

    title = book.get("title") or book.get("t") or "Kitob"
    author = book.get("author") or book.get("a") or ""
    sample = book.get("sample_text") or book.get("description", "")
    webapp_url = f"{config.WEBAPP_URL}?books&b={bid}" if config.WEBAPP_URL else None

    safe_title = safe_html(title)
    safe_author = safe_html(author)
    safe_sample = safe_html(sample)

    text = (
        f"📖 <b>«{safe_title}» — {safe_author}</b>\n"
        f"<i>(Mutolaa parchasi)</i>\n\n"
        f"{safe_sample}\n\n"
        f"<i>To'liq nusxasini PDF yoki EPUB formatida yuklab olishingiz yoki ilovada o'qishingiz mumkin.</i>"
    )

    buttons = [
        [
            InlineKeyboardButton(text="📥 PDF yuklab olish", callback_data=f"book:pdf:{bid}"),
            InlineKeyboardButton(text="📱 EPUB yuklab olish", callback_data=f"book:epub:{bid}"),
        ]
    ]
    if webapp_url:
        buttons.append([
            InlineKeyboardButton(text="🌐 Ilovada to'liq o'qish", web_app=WebAppInfo(url=webapp_url))
        ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Kitob sahifasiga qaytish", callback_data=f"book:item:{bid}"),
        InlineKeyboardButton(text="📚 Bosh menyu", callback_data="books:main")
    ])

    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.debug(f"edit_text error: {e}")
    await call.answer()


@router.callback_query(
    F.data.startswith("book:dl:") |
    F.data.startswith("books:dl:") |
    F.data.startswith("book:pdf:") |
    F.data.startswith("books:pdf:") |
    F.data.startswith("book:epub:") |
    F.data.startswith("books:epub:")
)
async def cb_book_download(call: CallbackQuery) -> None:
    """Kitobni chatga yuklab berish (PDF yoki EPUB)."""
    parts = call.data.split(":")
    action = parts[1]  # dl, pdf, yoki epub
    bid = parts[-1]
    fmt = "epub" if action == "epub" else "pdf"

    book = book_service.get_book_by_id(bid)
    if not book:
        await call.answer("Kitob topilmadi!", show_alert=True)
        return

    await call.answer("📥 Kitob tayyorlanmoqda va yuborilmoqda…")
    try:
        await book_service.deliver_book(
            bot=call.bot,
            chat_id=call.message.chat.id,
            book_id=bid,
            fmt=fmt
        )
    except Exception as e:
        logger.error(f"Kitob yetkazishda xatolik: {e}")
        await call.message.answer(f"⚠️ Kitobni yuborishda xatolik yuz berdi: {e}", protect_content=True)
