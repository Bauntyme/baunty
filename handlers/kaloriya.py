"""Baunty Kaloriya va Fitnes hisoblagich handlerlari.

Foydalanuvchilarga kunlik kaloriya, oziq-ovqat tarkibi (oqsil, yog', uglevod),
vazn maqsadi va to'liq Mini App taomnomasini taqdim etadi.
To'liq Bauntys brendlangan.
"""

from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import config
from services.kaloriya_service import kaloriya_service

logger = logging.getLogger(__name__)

router = Router(name="kaloriya")


def get_kaloriya_keyboard() -> InlineKeyboardMarkup:
    """Kaloriya bosh inline klaviaturasi."""
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    webapp_url = f"{base_url}?m=kal"

    buttons = [
        [
            InlineKeyboardButton(text="🥗 Kaloriya hisoblagich (Mini App)", web_app=WebAppInfo(url=webapp_url))
        ],
        [
            InlineKeyboardButton(text="📊 Bugungi kundalik", callback_data="kal:today"),
            InlineKeyboardButton(text="🍏 Oziq-ovqat kaloriyasini tekshirish", callback_data="kal:search_hint"),
        ],
        [
            InlineKeyboardButton(text="🎯 Shaxsiy profil va maqsad", callback_data="kal:profile_info"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("kaloriya", "kal", "kcal", "ovqat"))
@router.message(F.text.in_(["🥗 Kaloriya", "🍏 Kaloriya", "Kaloriya", "Kaloriya hisoblagich"]))
async def cmd_kaloriya(message: Message) -> None:
    """Kaloriya bo'limi bosh menyusi."""
    user_id = message.from_user.id
    status = await kaloriya_service.get_status(user_id=user_id)

    today = status.get("today", {})
    t_kcal = today.get("kcal", 0)
    target = today.get("target", 2000)
    rem = today.get("rem", target - t_kcal)
    p = today.get("p", 0)
    f = today.get("f", 0)
    c = today.get("c", 0)

    text = (
        f"🥗 <b>Baunty Kaloriya & Fitnes Nazorati</b>\n\n"
        f"🎯 <b>Bugungi ko'rsatkichlar:</b>\n"
        f"• Iste'mol qilindi: <b>{t_kcal} / {target} kkal</b>\n"
        f"• Qolgan me'yor: <b>{rem} kkal</b>\n"
        f"• Oqsil (Protein): <b>{p} g</b> | Yog': <b>{f} g</b> | Uglevod: <b>{c} g</b>\n\n"
        f"🔍 <b>Taomni tekshirish:</b>\n"
        f"Istalgan taom nomini yozing, masalan:\n"
        f"<code>osh 300 gr</code> yoki <code>non 100g</code> yoki <code>olma 2 dona</code>\n\n"
        f"<i>Kamera orqali skanerlash va to'liq reja uchun Mini Appni oching:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_kaloriya_keyboard())


@router.callback_query(F.data == "kal:main")
async def cb_kal_main(call: CallbackQuery) -> None:
    """Kaloriya bosh menyusiga qaytish."""
    await cmd_kaloriya(call.message)
    await call.answer()


@router.callback_query(F.data == "kal:today")
async def cb_kal_today(call: CallbackQuery) -> None:
    """Bugun yeyilgan taomlar ro'yxati."""
    user_id = call.from_user.id
    status = await kaloriya_service.get_status(user_id=user_id)
    meals = status.get("meals", {})

    lines = ["📅 <b>Bugungi taomnoma ro'yxati:</b>\n"]
    meal_names = {
        "b": "🍳 Nonushta",
        "l": "🍲 Tushlik",
        "d": "🥗 Kechki ovqat",
        "s": "🍏 Qorinda qolgan (Snack)"
    }

    has_any = False
    for mk, title in meal_names.items():
        m_data = meals.get(mk, {})
        items = m_data.get("items", [])
        tot = m_data.get("total", {})
        if items:
            has_any = True
            lines.append(f"<b>{title}</b> ({tot.get('kcal', 0)} kkal):")
            for it in items:
                lines.append(f"  • {it.get('name', 'Taom')}: {it.get('grams', 0)}g — {it.get('kcal', 0)} kkal")
            lines.append("")

    if not has_any:
        lines.append("<i>Bugun hali taomlar kiritilmagan.</i>\n<i>Masalan: <code>osh 250g</code> deb yuboring.</i>")

    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Taom qo'shish (Mini App)", web_app=WebAppInfo(url=f"{base_url}?m=kal"))],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="kal:main")]
    ])
    await call.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "kal:search_hint")
async def cb_kal_search_hint(call: CallbackQuery) -> None:
    """Taom qidirish bo'yicha yordam."""
    text = (
        "🔍 <b>Taom kaloriyasini qanday tekshirish mumkin?</b>\n\n"
        "Shunchaki bot chatiga yozib yuboring:\n"
        "• <code>somsa 1 dona</code>\n"
        "• <code>shashlik 200 gr</code>\n"
        "• <code>lagmon 400g</code>\n"
        "• <code>tuxum 2 dona</code>\n"
        "• <code>banan 1 dona</code>\n\n"
        "Bot darhol uning kaloriya, oqsil, yog' va uglevod miqdorini hisoblab beradi!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="kal:main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "kal:profile_info")
async def cb_kal_profile(call: CallbackQuery) -> None:
    """Foydalanuvchi fitnes profili."""
    user_id = call.from_user.id
    status = await kaloriya_service.get_status(user_id=user_id)
    prof = status.get("profile", {})

    target_kcal = prof.get("daily_kcal", 2000)
    bmr = prof.get("bmr", 1500)
    weight = prof.get("weight", 70)
    target_weight = prof.get("target_weight", 65)
    goal = prof.get("goal", "lose")

    goal_titles = {
        "lose": "Vazn tashlash (ozish) 📉",
        "keep": "Vaznni saqlash ⚖️",
        "gain": "Vazn yig'ish (mushak chiqarish) 📈"
    }

    text = (
        f"🎯 <b>Sizning Shaxsiy Fitnes Profilingiz:</b>\n\n"
        f"• Joriy vazn: <b>{weight} kg</b>\n"
        f"• Maqsadli vazn: <b>{target_weight} kg</b>\n"
        f"• Maqsad yo'nalishi: <b>{goal_titles.get(goal, goal)}</b>\n"
        f"• Kunlik tavsiya etilgan me'yor: <b>{target_kcal} kkal</b>\n"
        f"• Asosiy moddalar almashinuvi (BMR): <b>{bmr} kkal</b>\n\n"
        f"<i>Profilingiz parametrlarini o'zgartirish uchun Mini Appga kiring:</i>"
    )
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Profilni sozlash (Mini App)", web_app=WebAppInfo(url=f"{base_url}?m=kal"))],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="kal:main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()
