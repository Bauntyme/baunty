"""Baunty Rasxod (Shaxsiy moliya va xarajatlar) handlerlari.

Foydalanuvchilarga xarajatlarni chatda tezkor yozib borish,
byudjet belgilash va Mini App orqali oylik tahlilni ko'rish imkonini beradi.
To'liq Bauntys brendlangan.
"""

from __future__ import annotations

import re
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import config
from services.rasxod_service import rasxod_service
from database import crud

logger = logging.getLogger(__name__)

router = Router(name="rasxod")


def get_rasxod_keyboard() -> InlineKeyboardMarkup:
    """Rasxod bosh inline klaviaturasi."""
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    webapp_url = f"{base_url}?m=rasxod"

    buttons = [
        [
            InlineKeyboardButton(text="💰 Rasxod Mini App (Batafsil tahlil)", web_app=WebAppInfo(url=webapp_url))
        ],
        [
            InlineKeyboardButton(text="📊 Oylik hisobot", callback_data="rasxod:month"),
            InlineKeyboardButton(text="📅 Bugungi xarajatlar", callback_data="rasxod:today"),
        ],
        [
            InlineKeyboardButton(text="💡 Xarajat yozish namunasi", callback_data="rasxod:help"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("rasxod", "xarajat", "harajat"))
@router.message(F.text.in_([
    "💰 Rasxod", "📊 Rasxod", "Rasxod", "Xarajatlar", "Xarajat",
    "💰 Расход", "📊 Расход", "Расход", "Харажатлар", "Харажат",
    "Расходы"
]))
async def cmd_rasxod(message: Message) -> None:
    """Rasxod bo'limi bosh menyusi."""
    user_id = message.from_user.id
    home = await rasxod_service.get_home(user_id=user_id)
    spent = home.get("spent", 0)
    budget = home.get("budget", 0)
    month_name = home.get("month", "Joriy oy")

    text = (
        f"💰 <b>Baunty Rasxod — Shaxsiy Moliya & Xarajatlar Nazorati</b>\n\n"
        f"🗓 <b>{month_name} oyi sarhisobi:</b>\n"
        f"• Jami sarflandi: <b>{spent:,} so'm</b>\n"
    )
    if budget > 0:
        pct = home.get("pct", 0)
        rem = home.get("rem", 0)
        text += (
            f"• Belgilangan byudjet: <b>{budget:,} so'm</b>\n"
            f"• Byudjet bajarilishi: <b>{pct}%</b>\n"
            f"• Qolgan qoldiq: <b>{rem:,} so'm</b>\n\n"
        )
    else:
        text += (
            f"• Byudjet: <i>Belgilanmagan</i> (Oylik limit uchun: <code>/budget 3000000</code>)\n\n"
        )

    text += (
        f"✍️ <b>Tezkor xarajat yozish:</b>\n"
        f"Shunchaki botga xabar qilib yuboring, masalan:\n"
        f"<code>non 8000, taksi 25 ming</code> yoki <code>obed 45k</code>\n\n"
        f"<i>To'liq diagramma va toifalar tahlilini Mini Appda ko'ring:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_rasxod_keyboard())


@router.message(Command("budget"))
async def cmd_budget(message: Message) -> None:
    """Oylik byudjet belgilash."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "ℹ️ <b>Oylik byudjet kiritish uchun:</b>\n"
            "<code>/budget 3500000</code> yoki <code>/budget 3.5 mln</code> deb yuboring.",
            parse_mode="HTML"
        )
        return

    val_str = args[1].strip()
    parsed = crud.parse_expense_text(f"byudjet {val_str}")
    if not parsed:
        # Oddiy raqam sifatida tekshirish
        clean = re.sub(r"[^\d]", "", val_str)
        amount = int(clean) if clean.isdigit() else 0
    else:
        amount = parsed[0].get("a") or parsed[0].get("amount") or 0

    if amount <= 0:
        await message.answer("⚠️ Iltimos, to'g'ri byudjet miqdorini kiriting.")
        return

    res = await rasxod_service.set_budget(user_id=message.from_user.id, amount=amount)
    await message.answer(
        f"✅ <b>Oylik byudjet belgilandi:</b> {amount:,} so'm\n"
        f"Endi har bir xarajatingiz ushbu limitga qarab hisoblanadi.",
        parse_mode="HTML",
        reply_markup=get_rasxod_keyboard()
    )


@router.callback_query(F.data == "rasxod:main")
async def cb_rasxod_main(call: CallbackQuery) -> None:
    """Rasxod bosh menyusiga qaytish."""
    user_id = call.from_user.id
    home = await rasxod_service.get_home(user_id=user_id)
    spent = home.get("spent", 0)
    month_name = home.get("month", "Joriy oy")

    text = (
        f"💰 <b>Baunty Rasxod — Shaxsiy Moliya</b>\n\n"
        f"🗓 <b>{month_name}:</b> {spent:,} so'm sarflandi.\n"
        f"Barcha tahlil va toifalar quyidagi Mini Appda:"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_rasxod_keyboard())
    await call.answer()


@router.callback_query(F.data == "rasxod:help")
async def cb_rasxod_help(call: CallbackQuery) -> None:
    """Xarajat kiritish namunasi."""
    text = (
        "💡 <b>Xarajatlarni kiritish juda oddiy!</b>\n\n"
        "Shunchaki botga quyidagi formatlarda yozishingiz mumkin:\n"
        "• <code>taksi 25 ming</code>\n"
        "• <code>non 8000, sut 12000</code>\n"
        "• <code>lavash 35k</code>\n"
        "• <code>benzin 150 000</code>\n"
        "• <code>telefon abonent tolovi 40 ming</code>\n\n"
        "🤖 <i>Bot avtomatik tarzda toifani (transport, oziq-ovqat, aloqa, kafe va h.k.) aniqlaydi va bazaga yozadi!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="rasxod:main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "rasxod:month")
async def cb_rasxod_month(call: CallbackQuery) -> None:
    """Oylik toifalar tahlili."""
    user_id = call.from_user.id
    home = await rasxod_service.get_home(user_id=user_id)
    spent = home.get("spent", 0)
    donut = home.get("donut", [])

    lines = [f"📊 <b>Oylik xarajatlar taqsimoti:</b>\nJami: <b>{spent:,} so'm</b>\n"]
    if donut:
        for item in donut:
            lines.append(f"• {item.get('ic', '💳')} <b>{item.get('t', 'Boshqa')}:</b> {item.get('v', 0):,} so'm ({item.get('p', 0)}%)")
    else:
        lines.append("<i>Bu oyda hali xarajatlar qayd etilmagan.</i>")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Mini Appda ko'rish", web_app=WebAppInfo(url=f"{config.webapp_url_resolved}?m=rasxod"))],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="rasxod:main")]
    ])
    await call.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "rasxod:today")
async def cb_rasxod_today(call: CallbackQuery) -> None:
    """Bugungi xarajatlar."""
    user_id = call.from_user.id
    items_res = await rasxod_service.get_list(user_id=user_id)
    all_items = items_res.get("items", [])

    # Faqat bugungi kunnikini saralash
    import datetime
    today_str = datetime.date.today().isoformat()
    today_items = [it for it in all_items if it.get("d") == today_str]

    if not today_items:
        text = "📅 <b>Bugun hali hech qanday xarajat kiritilmadi.</b>\nMasalan: <code>taksi 20 ming</code> deb yozib yuboring."
    else:
        today_total = sum(it.get("a", 0) for it in today_items)
        lines = [f"📅 <b>Bugungi xarajatlar ({len(today_items)} ta):</b>\nJami: <b>{today_total:,} so'm</b>\n"]
        for it in today_items[:10]:
            lines.append(f"• {it.get('ic', '💳')} <b>{it.get('n', 'Xarajat')}:</b> {it.get('a', 0):,} so'm")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="rasxod:main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()
