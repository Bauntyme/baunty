"""
Bauntys Tv Xona Handlerlari (TV Watch Party Handlers)
Telegram bot va Telegram Mini App orqali do'stlar bilan jonli TV tomosha qilish,
kanalni sinxronlashtirish, matnli va ovozli suhbat.
100% Bauntys brendi.
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import config
from services.tv_room_service import tv_room_service, normalize_room_code

logger = logging.getLogger(__name__)

router = Router(name="tvroom")


def get_tvroom_keyboard(code: str = "") -> InlineKeyboardMarkup:
    """Tv Xona boshqaruv inline klaviaturasi."""
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    if code:
        norm = normalize_room_code(code)
        webapp_url = f"{base_url}?m=tvroom&room={norm}"
        btn_text = f"📺 Tv Xonaga Kirish (#{code})"
    else:
        webapp_url = f"{base_url}?m=tvroom"
        btn_text = "📺 Tv Xona Yaratish / Kirish"

    buttons = [
        [
            InlineKeyboardButton(text=btn_text, web_app=WebAppInfo(url=webapp_url))
        ],
        [
            InlineKeyboardButton(text="⚡ Tezkor xonaga kirish", callback_data="tvroom:quick"),
            InlineKeyboardButton(text="📋 Ommaviy xonalar", callback_data="tvroom:list"),
        ],
        [
            InlineKeyboardButton(text="📡 Telekanallar ro'yxati", callback_data="tvroom:channels"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("tvxona", "tvroom"))
@router.message(F.text.in_([
    "📺 Tv Xona", "Tv Xona", "TV Xona", "📺 Tv xona", "tvroom", "tvxona", "📺 TV Xona", "📺 TV xona"
]))
async def cmd_tvroom(message: Message) -> None:
    """Tv Xona bosh menyusi."""
    user = message.from_user
    user_name = user.first_name if user else "Do'stim"
    code = ""

    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            p = parts[1].strip()
            if p.startswith("tvroom_"):
                code = p[7:]
            elif p.startswith("tvxona_"):
                code = p[7:]
            elif p.startswith("tv_"):
                code = p[3:]
            elif p.isalnum() and len(p) in (4, 5, 6, 7, 8):
                code = p

    room_info = f"\n\n🎯 <b>Taklif etilgan xona:</b> <code>#{code}</code>" if code else ""
    text = (
        f"📺 <b>Bauntys «Tv Xona» — Do'stlar Bilan TV Tomosha Qilish!</b>\n\n"
        f"Assalomu alaykum, {user_name}! Endi siz do'stlaringizni taklif qilib, "
        f"birgalikda 4K UHD / 1080p sifatdagi jonli telekanallarni bir vaqtda sinxron tomosha qilishingiz mumkin!\n\n"
        f"✨ <b>Asosiy imkoniyatlar:</b>\n"
        f"• 👑 <b>Sinxron TV efir:</b> Xona boshqaruvchisi kanalni o'zgartirganda, hamma uchun bir vaqtda o'zgaradi.\n"
        f"• 💬 <b>Jonli chat va reaksiyalar:</b> Tomosha jarayonida fikr almashing va his-tuyg'ularingizni bildiring.\n"
        f"• 🎙 <b>Kristal ovozli chat:</b> Aks-sado va shovqinlarsiz (Echo & Noise Suppression) suhbatlashing.\n"
        f"• 👥 <b>Do'stlarni chaqirish:</b> Xona kodini bitta tugma orqali ulashing.{room_info}\n\n"
        f"<i>Xonaga kirish yoki yangi xona ochish uchun pastdagi tugmani bosing:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_tvroom_keyboard(code))


async def handle_tvroom_start(message: Message, param: str) -> None:
    """Deep Link (/start tvroom_<code>) orqali xonaga to'g'ridan-to'g'ri ulanish."""
    code = param.replace("tvroom_", "").replace("tvxona_", "").replace("tv_", "").strip()
    norm = normalize_room_code(code)
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    webapp_url = f"{base_url}?m=tvroom&room={norm}"

    text = (
        f"🎉 <b>Sizni do'stingiz «Tv Xona»ga taklif qildi!</b>\n\n"
        f"🔑 <b>Xona kodi:</b> <code>#{code or 'Asosiy'}</code>\n\n"
        f"Birgalikda 4K telekanal tomosha qilish, suhbatlashish va zavqlanish uchun "
        f"quyidagi tugmani bosing:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Tv Xonaga Kirish", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="tvroom:main")],
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "tvroom:main")
async def cb_tvroom_main(call: CallbackQuery) -> None:
    """Tv Xona asosiy ko'rinishiga qaytish."""
    text = (
        "📺 <b>Bauntys «Tv Xona» — Tomosha Party</b>\n\n"
        "Do'stlaringiz bilan birgalikda sevimli telekanallarni tomosha qiling, "
        "fikr almashing va ovozli suhbatda bo'ling."
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_tvroom_keyboard())
    await call.answer()


@router.callback_query(F.data == "tvroom:quick")
async def cb_tvroom_quick(call: CallbackQuery) -> None:
    """Tezkor xonaga ulanish."""
    user = call.from_user
    user_id = user.id
    user_name = user.first_name or "Foydalanuvchi"
    username = user.username or ""

    res = tv_room_service.join_room(
        room_code="tv_main",
        user_id=user_id,
        user_name=user_name,
        username=username,
    )
    room = res.get("room", {})
    code = room.get("code", "main")
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    webapp_url = f"{base_url}?m=tvroom&room={room.get('id', 'tv_main')}"

    text = (
        f"⚡ <b>Tezkor TV Xona tayyor:</b> <code>#{code}</code>\n\n"
        f"📺 <b>Joriy kanal:</b> {room.get('channel', {}).get('name', 'Sevimli TV HD')}\n"
        f"👥 <b>Tomoshabinlar:</b> {room.get('count', 1)} ta\n\n"
        f"Tomoshani boshlash uchun Mini Appni oching:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Xonani Ochish (Mini App)", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="tvroom:main")],
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "tvroom:list")
async def cb_tvroom_list(call: CallbackQuery) -> None:
    """Faol ommaviy TV xonalari ro'yxati."""
    rooms = tv_room_service.list_public_rooms()
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"

    lines = ["📋 <b>Faol TV Xonalar:</b>\n"]
    buttons = []

    for r in rooms[:6]:
        ch_name = r.get("channel_name", "TV")
        cnt = r.get("viewers_count", 1)
        r_id = r.get("id", "tv_main")
        r_name = r.get("name", "TV Xona")
        url = f"{base_url}?m=tvroom&room={r_id}"
        lines.append(f"• <b>{r_name}</b> — 📺 {ch_name} (👥 {cnt} kishi)")
        buttons.append([InlineKeyboardButton(text=f"👉 {r_name} ({cnt} 👥)", web_app=WebAppInfo(url=url))])

    buttons.append([
        InlineKeyboardButton(text="➕ Yangi Xona Yaratish", web_app=WebAppInfo(url=f"{base_url}?m=tvroom&action=create")),
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="tvroom:main")
    ])

    text = "\n".join(lines) + "\n\n<i>Qo'shilish uchun xonalardan birini tanlang:</i>"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()


@router.callback_query(F.data == "tvroom:channels")
async def cb_tvroom_channels(call: CallbackQuery) -> None:
    """Xonalarda tomosha qilish mumkin bo'lgan HD telekanallar haqida ma'lumot."""
    base_url = config.webapp_url_resolved or f"https://127.0.0.1:{config.PORT}"
    text = (
        "📡 <b>Tv Xonada Mavjud Mashhur Telekanallar (4K / 1080p):</b>\n\n"
        "• ❤️ <b>Sevimli TV HD:</b> Seriallar va eng yangi ko'ngilochar loyihalar\n"
        "• ⚡ <b>Zo'r TV HD:</b> Premyeralar, musiqiy shoular va xit konsertlar\n"
        "• 🇺🇿 <b>Milliy TV HD:</b> Milliy madaniyat, kliplar va filmlar\n"
        "• ⚽ <b>Sport TV HD:</b> Futbol, UFC va jahon chempionatlari\n"
        "• 🎬 <b>Kinoteatr & BIZ Cinema:</b> O'zbekcha tarjima qilingan jahon kinolari\n\n"
        "Xonangizda istalgan kanalni bir tegish bilan tanlashingiz mumkin!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Tv Xonaga Kirish", web_app=WebAppInfo(url=f"{base_url}?m=tvroom"))],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="tvroom:main")],
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()
