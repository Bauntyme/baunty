"""Baunty Mafia o'yini handlerlari (Mafia Handlers).

Telegram bot va Mini App orqali onlayn multi-player Mafia o'yini.
To'liq Bauntys brendlangan.
"""

from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import config
from services.mafia_service import mafia_service

logger = logging.getLogger(__name__)

router = Router(name="mafia")


def get_mafia_keyboard(code: str = "") -> InlineKeyboardMarkup:
    """Mafia bosh inline klaviaturasi."""
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    webapp_url = f"{base_url}?m=mafia" + (f"&startapp=maf_{code}" if code else "")
    btn_text = f"🕵️ Mafia xonasiga kirish (#{code})" if code else "🕵️ Mafia o'ynash (Mini App)"

    buttons = [
        [
            InlineKeyboardButton(text=btn_text, web_app=WebAppInfo(url=webapp_url))
        ],
        [
            InlineKeyboardButton(text="⚡ Tezkor o'yinga kirish", callback_data="mafia:quick"),
            InlineKeyboardButton(text="📜 Qoidalar", callback_data="mafia:rules"),
        ],
        [
            InlineKeyboardButton(text="📊 O'yin statistikasi", callback_data="mafia:stats"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("mafia", "mafiya"))
@router.message(F.text.in_(["🕵️ Mafia", "🕵️‍♂️ Mafia", "Mafia", "Mafiya"]))
async def cmd_mafia(message: Message) -> None:
    """Mafia bosh menyusi."""
    user_name = message.from_user.first_name or "O'yinchi"
    code = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            p = parts[1].strip()
            if p.startswith("maf_"):
                code = p[4:]
            elif p.startswith("mafia_"):
                code = p[6:]
            elif p.isdigit() and len(p) in (4, 5, 6):
                code = p

    room_info = f"\n\n🎯 <b>Taklif qilingan xona:</b> <code>#{code}</code>" if code else ""
    text = (
        f"🕵️ <b>Baunty Mafia Onlayn Klubiga Xush Kelibsiz, {user_name}!</b>\n\n"
        f"Do'stlaringiz yoki tasodifiy o'yinchilar bilan birga mashhur sarguzashtli psixologik "
        f"Mafia o'yinini to'g'ridan-to'g'ri Telegram Mini App orqali o'ynang!\n\n"
        f"🎭 <b>Rollar:</b> Don, Mafia, Komissar Katani, Shifokor va Tinch aholi.\n"
        f"🌙 <b>Bosqichlar:</b> Qorong'u tun, shahar uyg'onishi, fikr almashish va sud ovoz berishi!\n"
        f"🎙 <b>Imkoniyatlar:</b> Real vaqt rejimidagi chat, ovozli xonalar va to'liq animatsiyalar.{room_info}\n\n"
        f"<i>O'yinni boshlash uchun pastdagi tugmani bosing:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_mafia_keyboard(code))


@router.callback_query(F.data == "mafia:main")
async def cb_mafia_main(call: CallbackQuery) -> None:
    """Bosh menyuga qaytish."""
    text = (
        "🕵️ <b>Baunty Mafia Onlayn Klubi</b>\n\n"
        "Mini App ilovamizda istalgan vaqtda xona ochishingiz yoki mavjud xonalarga qo'shilishingiz mumkin."
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_mafia_keyboard())
    await call.answer()


@router.callback_query(F.data == "mafia:quick")
async def cb_mafia_quick(call: CallbackQuery) -> None:
    """Tezkor o'yinga qo'shilish yoki yangi xona ochish."""
    user_id = call.from_user.id
    user_name = call.from_user.first_name or "O'yinchi"
    res = mafia_service.quick_play(user_id=user_id, user_name=user_name)

    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    room_code = res.get("room", {}).get("id", "r1")
    app_url = f"{base_url}?m=mafia&room={room_code}"

    text = (
        f"⚡ <b>Xona tayyor:</b> <code>{room_code}</code>\n\n"
        f"👤 Siz xonaga muvaffaqiyatli qo'shildingiz!\n"
        f"O'yinni Mini App orqali davom ettiring:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Xonaga kirish (Mini App)", web_app=WebAppInfo(url=app_url))],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="mafia:main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "mafia:rules")
async def cb_mafia_rules(call: CallbackQuery) -> None:
    """Mafia qoidalari."""
    text = (
        "📜 <b>Baunty Mafia O'yin Qoidalari:</b>\n\n"
        "1. <b>O'yin maqsadi:</b>\n"
        "• Tinch aholi: Shahardagi barcha mafiozlarni topish va ovoz berish orqali zararsizlantirish.\n"
        "• Mafia: Tinch aholini yo'q qilib, tenglik yoki son jihatdan ustunlikka erishish.\n\n"
        "2. <b>Rollar:</b>\n"
        "• 🤵 <b>Don:</b> Mafiya boshlig'i, tunda nishonni tanlaydi va Komissarni qidiradi.\n"
        "• 🔫 <b>Mafia:</b> Don bilan birga tunda harakat qiladi.\n"
        "• 🕵️ <b>Komissar Katani:</b> Har kecha 1 nafar shubhali fuqaroni tekshiradi.\n"
        "• 🩺 <b>Shifokor:</b> Har kecha 1 kishini mafiyadan qutqarib qoladi.\n"
        "• 👨‍🌾 <b>Tinch aholi:</b> Kunduzgi muhokama va sud orqali haqiqatni aniqlaydi.\n\n"
        "<i>Har bir bosqich taymer bo'yicha avtomatik o'tadi.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="mafia:main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "mafia:stats")
async def cb_mafia_stats(call: CallbackQuery) -> None:
    """O'yin statistikasi."""
    home_data = mafia_service.get_home_data(user_id=call.from_user.id, user_name=call.from_user.first_name or "")
    rooms_count = len(home_data.get("rooms", []))
    online_count = home_data.get("online", 1)

    text = (
        f"📊 <b>Baunty Mafia Statistikasi:</b>\n\n"
        f"• Faol xonalar: <b>{rooms_count}</b> ta\n"
        f"• Hozirda onlayn o'yinchilar: <b>{online_count}</b> nafar\n"
        f"• Tizim holati: <b>Uzluksiz va faol</b> 🟢\n\n"
        f"<i>Xona oching va do'stlaringizni taklif qiling!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="mafia:main")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()
