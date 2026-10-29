"""Baunty Kaloriya va Fitnes hisoblagich handlerlari.

Foydalanuvchilarga kunlik kaloriya, oziq-ovqat tarkibi (oqsil, yog', uglevod),
vazn maqsadi, Eda AI darajasidagi ovqat va shirinliklar tahlili va to'liq Mini App taomnomasini taqdim etadi.
Har xil narsalarni emas, aynan yeyiladigan taomlarni to'liq tahlil qiladi.
To'liq Bauntys brendlangan.
"""

from __future__ import annotations

import io
import re
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import config
from services.kaloriya_service import kaloriya_service, FOOD_DATABASE, NON_FOOD_KEYWORDS

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
@router.message(F.text.in_([
    "🥗 Kaloriya", "🍏 Kaloriya", "Kaloriya", "Kaloriya hisoblagich",
    "🥗 Калория", "🍏 Калория", "Калория", "Калория ҳисоблагич",
    "🥗 Калории", "Калории"
]))
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
        f"<code>osh 300 gr</code> yoki <code>2 ta somsa va choy</code> yoki <code>medovik</code>\n\n"
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
        "🔍 <b>Taom va Shirinliklar Kaloriyasini Tekshirish</b>\n\n"
        "Shunchaki bot chatiga yozib yuboring:\n"
        "• <code>somsa 2 ta va choy</code>\n"
        "• <code>osh 300 gr</code>\n"
        "• <code>medovik va kofe</code>\n"
        "• <code>shashlik 200 gr</code>\n"
        "• <code>lavash va cola</code>\n"
        "• <code>tuxum 2 dona</code>\n\n"
        "Yoki taom suratini yuboring — Bot darhol uning aniq kaloriya, oqsil, yog', uglevod va tavsiyalarini hisoblab beradi!"
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


# --------------------------------------------------------------------------
# Eda AI: Taom va Shirinliklar tahlili (Text & Photo)
# --------------------------------------------------------------------------

def _format_food_result(res: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Tahlil natijalarini Eda AI ko'rinishida formatlash."""
    items = res.get("items", [])
    total = res.get("total", {})
    rec = res.get("recommendation", "")
    tot_kcal = total.get("kcal", 0)
    p = total.get("p", 0)
    f = total.get("f", 0)
    c = total.get("c", 0)

    lines = ["🥗 <b>Baunty Eda AI — Taom & Shirinlik Tahlili</b>\n"]
    for it in items:
        lines.append(f"🍽 <b>{it.get('uz') or it.get('n')}</b>: {it.get('g')}g — <b>{it.get('kcal')} kkal</b>")
        lines.append(f"   └ 🥩 Oqsil: {it.get('p')}g | 🧈 Yog': {it.get('f')}g | 🍞 Uglevod: {it.get('c')}g")

    lines.append(f"\n🔥 <b>Jami kaloriya:</b> {tot_kcal} kkal")
    lines.append(f"📊 <b>BJU umumiy:</b> Oqsil: {p}g | Yog': {f}g | Uglevod: {c}g")
    if rec:
        lines.append(f"\n💡 <i>Tavsiya: {rec}</i>")

    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍳 Nonushta", callback_data=f"kal:add:b:{tot_kcal}"),
            InlineKeyboardButton(text="🍲 Tushlik", callback_data=f"kal:add:l:{tot_kcal}"),
        ],
        [
            InlineKeyboardButton(text="🥗 Kechki ovqat", callback_data=f"kal:add:d:{tot_kcal}"),
            InlineKeyboardButton(text="🍏 Snack", callback_data=f"kal:add:s:{tot_kcal}"),
        ],
        [
            InlineKeyboardButton(text="🥗 Kaloriya hisoblagich (Mini App)", web_app=WebAppInfo(url=f"{base_url}?m=kal"))
        ]
    ])
    return "\n".join(lines), kb


def is_food_or_calorie_message(text: Optional[str]) -> bool:
    """Matn taom, shirinlik yoki kaloriya hisoblash bilan bog'liqligini aniqlash."""
    if not text:
        return False
    t = text.lower().strip()
    if t.startswith(("/kal", "/kcal", "/ovqat", "kaloriya", "калория")):
        return True
    # Non-food filtri
    has_non_food = any(re.search(rf"\b{re.escape(nk)}\b", t) for nk in NON_FOOD_KEYWORDS)
    # Ovqat kalit so'zlari
    has_food = any(any(re.search(rf"\b{re.escape(k)}\b", t) for k in f["keys"]) for f in FOOD_DATABASE)
    return has_food or (has_non_food and ("kaloriya" in t or "qancha" in t))


@router.message(F.photo)
async def handle_calorie_photo(message: Message) -> None:
    """Taom yoki shirinlik fotosuratini qabul qilib to'liq tahlil qilish."""
    try:
        photo = message.photo[-1]
        bot = message.bot
        photo_file = await bot.get_file(photo.file_id)
        photo_bytes_io = io.BytesIO()
        await bot.download_file(photo_file.file_path, destination=photo_bytes_io)
        photo_bytes = photo_bytes_io.getvalue()

        caption = message.caption or ""
        res = kaloriya_service.scan_food_text_or_image(text=caption, photo_data=photo_bytes)
        if not res.get("ok"):
            err_msg = res.get("msg") or "Yuborilgan fotosuratdan ovqat aniqlanmadi. Iltimos, aniq va yorug' surat yuboring."
            await message.answer(f"⚠️ {err_msg}")
            return

        text_out, kb = _format_food_result(res)
        await message.answer(text_out, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"Foto tahlilida xatolik: {e}")
        await message.answer("⚠️ Rasmni tahlil qilishda xatolik yuz berdi. Qaytadan urinib ko'ring.")


@router.message(F.text, lambda msg: is_food_or_calorie_message(msg.text))
async def handle_calorie_text(message: Message) -> None:
    """Foydalanuvchi yozgan taom yoki shirinlik matnini tahlil qilish."""
    res = kaloriya_service.scan_food_text_or_image(text=message.text)
    if not res.get("ok"):
        await message.answer(
            "⚠️ <b>Faqat yeyiladigan mahsulotlar!</b>\n\n"
            "Men faqat taomlar, shirinliklar, mevalar va ichimliklarni tahlil qila olaman.\n"
            "Iltimos, oziq-ovqat nomini yuboring (masalan: <code>osh 300 gr</code>, <code>2 ta somsa va choy</code>, <code>medovik</code>, <code>lavash</code>).",
            parse_mode="HTML"
        )
        return

    text_out, kb = _format_food_result(res)
    await message.answer(text_out, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("kal:add:"))
async def cb_kal_add_meal(call: CallbackQuery) -> None:
    """Taomni bugungi taomnomaga kiritish callbacki."""
    parts = call.data.split(":")
    meal = parts[2] if len(parts) > 2 else "l"
    kcal = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 250
    meal_names = {"b": "Nonushta", "l": "Tushlik", "d": "Kechki ovqat", "s": "Snack"}
    m_name = meal_names.get(meal, "Taom")

    items = [{"uz": f"{m_name} taomi", "g": 200, "kcal": kcal, "p": 15.0, "f": 10.0, "c": 25.0}]
    await kaloriya_service.add_meal(user_id=call.from_user.id, meal=meal, items=items, src="t")
    await call.answer(f"✅ {m_name}ga {kcal} kkal qo'shildi!", show_alert=True)
