"""
Anonim savollar va xabarlar (NGL / @Zakirovsfilms_bot uslubida ?start=q_<token>) handlerlari
"""
import asyncio
import html
import logging
import urllib.parse
from typing import Tuple
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from config import config
from database.session import get_session
from database import crud
from database.models import AnonQuestionProfile
from keyboards.default import cancel_keyboard, main_menu_keyboard
from keyboards.inline import (
    anon_questions_keyboard,
    anon_regen_confirm_keyboard,
    anon_incoming_keyboard,
    anon_share_card_keyboard,
)
from services.anon_story_image import generate_anon_story_image, generate_anon_share_banner
from services.bot_identity import (
    build_telegram_share_url,
    get_bot_username,
    resolve_bot_username,
)
from utils.states import AnonQuestionStates

logger = logging.getLogger(__name__)
router = Router(name="anon_questions_router")

CANCEL_WORDS = {
    "❌ bekor qilish", "❌ бекор қилиш", "❌ отмена",
    "🔙 bosh menyu", "🔙 бош меню", "🔙 главное меню",
    "🔙 orqaga", "🔙 орқага", "🔙 назад",
    "/cancel", "/stop",
}


def build_anon_link_and_share(bot_username: str, token: str) -> Tuple[str, str]:
    """Shaxsiy anonim havola va URL-kodlangan chiroyli Telegram ulashish havolasini yaratadi."""
    fallback_bot = get_bot_username()
    clean_bot = str(bot_username or fallback_bot).strip().lstrip("@") or fallback_bot
    link = f"https://t.me/{clean_bot}?start=q_{token}"
    share_text = (
        "\n💌 Menga anonim savol yoki dil so'zlaringizni yozing!\n\n"
        "🤫 Shaxsingiz 100% sir saqlanadi — kim yozganini bilmayman.\n"
        "✨ Istalgan savol, fikr yoki samimiy tilagingizni bemalol qoldiring!\n\n"
        "👇 Xabar yuborish uchun yuqoridagi havolani bosing"
    )
    share_url = build_telegram_share_url(link, share_text)
    return link, share_url


def format_anon_card_text(
    bot_username: str,
    token: str,
    received_count: int = 0,
    blocked_count: int = 0,
    is_accepting: bool = True,
) -> str:
    """Anonim savollar boshqaruv kartasi matnini shakllantiradi."""
    link, _ = build_anon_link_and_share(bot_username, token)
    status_line = "✅ xabar qabul qilinyapti" if is_accepting else "⏸ to'xtatilgan"
    return (
        "💌 <b>Anonim savollar</b>\n\n"
        "Sizning shaxsiy havolangiz (bosib nusxa oling):\n"
        f"<code>{html.escape(link)}</code>\n\n"
        "Uni do'stingizga, kanalingiz, guruh yoki Instagram story'ga joylang — "
        "odamlar sizga <b>anonim savol va fikr yozadi</b>. "
        "Siz javob bera olasiz, ular kimligini bilmaysiz.\n\n"
        f"📬 Qabul qilingan: <b>{int(received_count)}</b>\n"
        f"🚫 Bloklanganlar: <b>{int(blocked_count)}</b>\n"
        f"Holat: {status_line}\n\n"
        "<i>💡 Do'stga chiroyli taklif shaklida yuborish uchun «🪄 Chiroyli karta» tugmasini bosing.</i>"
    )


def _build_card_payload(
    bot_username: str,
    token: str,
    received_count: int,
    blocked_count: int,
    is_accepting: bool,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Karta matni va 5 qatorli boshqaruv klaviaturasini qaytaradi."""
    text = format_anon_card_text(
        bot_username=bot_username,
        token=token,
        received_count=received_count,
        blocked_count=blocked_count,
        is_accepting=is_accepting,
    )
    _, share_url = build_anon_link_and_share(bot_username, token)
    kb = anon_questions_keyboard(share_url=share_url, is_accepting=is_accepting)
    return text, kb


async def _load_user_anon_state(user_id: int) -> Tuple[str, int, int, bool]:
    """Foydalanuvchining joriy tokeni, statistikasi va qabul holatini DB dan oladi."""
    try:
        async with get_session() as session:
            prof = await crud.get_or_create_anon_profile(session, user_id)
            recv_cnt, blk_cnt = await crud.get_anon_stats(session, user_id)
            return prof.token, recv_cnt, blk_cnt, bool(prof.is_accepting)
    except Exception as e:
        logger.warning(f"Anonim profil ma'lumotlarini olishda zaxira ishlatildi: {e}")
        return str(user_id), 0, 0, True


async def _edit_or_send_card(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    """Karta xabarini joyida tahrirlaydi yoki yangi xabar sifatida yuboradi."""
    if not callback.message:
        return
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except TelegramBadRequest as err:
        if "message is not modified" not in str(err).lower():
            await callback.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                protect_content=True,
            )


def _has_supported_media(message: Message) -> bool:
    return bool(
        getattr(message, "photo", None)
        or getattr(message, "video", None)
        or getattr(message, "voice", None)
        or getattr(message, "audio", None)
        or getattr(message, "document", None)
    )


@router.message(Command("anon", "savol", "savollar", "ask", "q"))
@router.message(F.text.in_(["💌 Anonim savollar", "💌 Аноним саволлар", "💌 Анонимные вопросы"]))
async def cmd_anon_questions_link(message: Message, state: FSMContext, user_id: int | None = None) -> None:
    """Foydalanuvchining shaxsiy anonim savollar boshqaruv kartasini ko'rsatish."""
    await state.clear()
    uid = int(user_id) if user_id is not None else message.from_user.id
    bot_name = await resolve_bot_username(message.bot)
    token, recv_cnt, blk_cnt, is_accepting = await _load_user_anon_state(uid)
    text, kb = _build_card_payload(bot_name, token, recv_cnt, blk_cnt, is_accepting)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb,
        disable_web_page_preview=True,
        protect_content=True,
    )


@router.callback_query(F.data == "anon:share_card")
async def cb_anon_share_card(callback: CallbackQuery) -> None:
    """Do'stlarga, guruh yoki kanalga forward qilish uchun chiroyli taklif kartasi yuborish."""
    await callback.answer("🪄 Chiroyli taklif kartasi tayyorlanmoqda...")
    user_id = callback.from_user.id if callback.from_user else 0
    bot_name = await resolve_bot_username(callback.bot)
    token, _, _, _ = await _load_user_anon_state(user_id)
    link, _ = build_anon_link_and_share(bot_name, token)

    banner_bytes = await asyncio.to_thread(generate_anon_share_banner, bot_name)
    safe_link = html.escape(link, quote=True)
    caption = (
        "💌 <b>Menga anonim savol yoki dil so'zingizni yozing!</b>\n\n"
        "🤫 <i>Shaxsingiz 100% sir saqlanadi — kim yozganini bilmayman.</i>\n"
        "✨ Savol, maslahat yoki samimiy tilagingizni bemalol qoldiring!\n\n"
        f"👉 <a href=\"{safe_link}\"><b>Anonim savol yozish</b></a>"
    )
    target_msg = callback.message
    if not target_msg:
        return
    # Do'stlarga va kanallarga bemalol forward qilish uchun protect_content=False
    await target_msg.answer_photo(
        photo=BufferedInputFile(banner_bytes, filename="anonim_taklif.png"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=anon_share_card_keyboard(link),
        protect_content=False,
    )


@router.callback_query(F.data == "anon:ig_story_img")
async def cb_anon_ig_story_image(callback: CallbackQuery) -> None:
    """Instagram story'ga joylash uchun rasm shabloni va 3 qadamli qo'llanma yuborish."""
    await callback.answer("🖼 Rasm tayyorlanmoqda...")
    user_id = callback.from_user.id if callback.from_user else 0
    bot_name = await resolve_bot_username(callback.bot)
    token, _, _, _ = await _load_user_anon_state(user_id)
    link, _ = build_anon_link_and_share(bot_name, token)

    png_bytes = await asyncio.to_thread(generate_anon_story_image, bot_name)
    caption = (
        "📸 <b>Instagram story'ga joylash:</b>\n"
        "1) Rasmni saqlang va story'ga qo'ying.\n"
        "2) Yuqoridagi stiker belgisini bosing → <b>LINK</b> (Ссылка).\n"
        "3) Havolani qo'ying va stikerni rasmdagi ramka ustiga joylang:\n"
        f"<code>{html.escape(link)}</code>\n\n"
        "<i>Fayl ko'rinishidagi nusxa — sifati yo'qolmaydi.</i>"
    )

    target_msg = callback.message
    if not target_msg:
        return

    # Story shablonini foydalanuvchi galereyaga saqlashi uchun protect_content=False
    try:
        await target_msg.answer_photo(
            photo=BufferedInputFile(png_bytes, filename="anonim_story.png"),
            protect_content=False,
        )
    except Exception as photo_err:
        logger.debug(f"Story preview rasm yuborishda xatolik: {photo_err}")

    await target_msg.answer_document(
        document=BufferedInputFile(png_bytes, filename="anonim_story.png"),
        caption=caption,
        parse_mode="HTML",
        protect_content=False,
    )


@router.callback_query(F.data == "anon:toggle_accept")
async def cb_anon_toggle_accept(callback: CallbackQuery) -> None:
    """Anonim xabarlar qabulini yoqish yoki vaqtincha to'xtatish."""
    user_id = callback.from_user.id if callback.from_user else 0
    bot_name = await resolve_bot_username(callback.bot)

    try:
        async with get_session() as session:
            prof = await crud.get_or_create_anon_profile(session, user_id)
            new_state = not bool(prof.is_accepting)
            prof = await crud.set_anon_accepting(session, user_id, new_state)
            recv_cnt, blk_cnt = await crud.get_anon_stats(session, user_id)
            token = prof.token
    except Exception as e:
        logger.warning(f"Qabul holatini o'zgartirishda xatolik: {e}")
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    text, kb = _build_card_payload(bot_name, token, recv_cnt, blk_cnt, new_state)
    await _edit_or_send_card(callback, text, kb)
    await callback.answer("Qabul yoqildi" if new_state else "Qabul to'xtatildi")


@router.callback_query(F.data == "anon:regen_confirm")
async def cb_anon_regen_confirm(callback: CallbackQuery) -> None:
    """Havolani yangilashdan oldin tasdiqlash so'rovi."""
    await callback.answer()
    warn_text = (
        "⚠️ <b>Havolani yangilasangiz</b>, eski havola ishlamay qoladi "
        "(story va kanallardagi eski havoladan endi xabar kelmaydi).\n\n"
        "Davom etamizmi?"
    )
    await _edit_or_send_card(callback, warn_text, anon_regen_confirm_keyboard())


@router.callback_query(F.data == "anon:regen_no")
async def cb_anon_regen_cancel(callback: CallbackQuery) -> None:
    """Havolani yangilashni bekor qilib asosiy kartani qaytarish."""
    await callback.answer("Bekor qilindi")
    user_id = callback.from_user.id if callback.from_user else 0
    bot_name = await resolve_bot_username(callback.bot)
    token, recv_cnt, blk_cnt, is_accepting = await _load_user_anon_state(user_id)
    text, kb = _build_card_payload(bot_name, token, recv_cnt, blk_cnt, is_accepting)
    await _edit_or_send_card(callback, text, kb)


@router.callback_query(F.data == "anon:regen_yes")
async def cb_anon_regen_execute(callback: CallbackQuery) -> None:
    """Yangi anonim havola yaratish va eskisini bekor qilish."""
    user_id = callback.from_user.id if callback.from_user else 0
    bot_name = await resolve_bot_username(callback.bot)

    try:
        async with get_session() as session:
            prof = await crud.regenerate_anon_token(session, user_id)
            recv_cnt, blk_cnt = await crud.get_anon_stats(session, user_id)
            new_token = prof.token
            is_accepting = bool(prof.is_accepting)
    except Exception as e:
        logger.warning(f"Havolani yangilashda xatolik: {e}")
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    text, kb = _build_card_payload(bot_name, new_token, recv_cnt, blk_cnt, is_accepting)
    await _edit_or_send_card(callback, text, kb)
    await callback.answer("✅ Yangi havola yaratildi!")


@router.callback_query(F.data == "anon:main_menu")
async def cb_anon_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Anonim savollar bo'limidan asosiy menyuga qaytish."""
    await state.clear()
    await callback.answer()
    user_id = callback.from_user.id if callback.from_user else 0
    if callback.message:
        await callback.message.answer(
            "🏠 <b>Asosiy menyu. Kerakli bo'limni tanlang 👇</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(user_id)),
        )


@router.callback_query(F.data.startswith("anon:block:"))
async def cb_anon_block_sender(callback: CallbackQuery) -> None:
    """Anonim xabar yuboruvchini bloklash."""
    raw_sid = callback.data.split("anon:block:")[-1].strip()
    try:
        sender_id = int(raw_sid)
    except (ValueError, TypeError):
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    recipient_id = callback.from_user.id if callback.from_user else 0
    try:
        async with get_session() as session:
            await crud.block_anon_sender(session, recipient_id=recipient_id, sender_id=sender_id)
    except Exception as e:
        logger.warning(f"Bloklashda xatolik: {e}")

    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=anon_incoming_keyboard(sender_id=sender_id, is_blocked=True)
            )
        except TelegramBadRequest:
            pass
    await callback.answer("🚫 Yuboruvchi bloklandi")


@router.callback_query(F.data.startswith("anon:unblock:"))
async def cb_anon_unblock_sender(callback: CallbackQuery) -> None:
    """Bloklangan anonim yuboruvchini blokdan chiqarish."""
    raw_sid = callback.data.split("anon:unblock:")[-1].strip()
    try:
        sender_id = int(raw_sid)
    except (ValueError, TypeError):
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    recipient_id = callback.from_user.id if callback.from_user else 0
    try:
        async with get_session() as session:
            await crud.unblock_anon_sender(session, recipient_id=recipient_id, sender_id=sender_id)
    except Exception as e:
        logger.warning(f"Blokdan chiqarishda xatolik: {e}")

    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=anon_incoming_keyboard(sender_id=sender_id, is_blocked=False)
            )
        except TelegramBadRequest:
            pass
    await callback.answer("✅ Blokdan chiqarildi")


@router.callback_query(F.data.startswith("anon_reply:"))
async def cb_anon_reply(callback: CallbackQuery, state: FSMContext) -> None:
    """Anonim xabarga javob qaytarishni boshlash."""
    sender_id_str = callback.data.split("anon_reply:")[-1].strip()
    try:
        sender_id = int(sender_id_str)
    except (ValueError, TypeError):
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    await state.set_state(AnonQuestionStates.waiting_for_reply)
    await state.update_data(reply_to_user_id=sender_id)

    await callback.message.reply(
        "✍️ <b>Anonim javobingizni yozing:</b>\n"
        "Sizning javobingiz savol egasiga to'liq yetkaziladi.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(AnonQuestionStates.waiting_for_reply)
async def state_process_anon_reply(message: Message, state: FSMContext) -> None:
    """Anonim javobni jo'natuvchiga yetkazish."""
    data = await state.get_data()
    raw_target = data.get("reply_to_user_id")

    if message.text and message.text.strip().lower() in CANCEL_WORDS:
        await state.clear()
        await message.reply(
            "❌ <b>Amal bekor qilindi.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id)),
        )
        return

    try:
        target_user_id = int(raw_target) if raw_target is not None else None
    except (ValueError, TypeError):
        target_user_id = None

    reply_text = (message.text or message.caption or "").strip()
    await state.clear()

    sender_id = message.from_user.id
    if not target_user_id:
        await message.reply(
            "Xatolik: qabul qiluvchi aniqlanmadi.",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
        )
        return

    has_media = _has_supported_media(message)
    if not reply_text and has_media:
        reply_text = "(Media fayl ilova qilindi)"

    if not reply_text:
        await message.reply("Iltimos, javob matnini yozing.", reply_markup=cancel_keyboard())
        await state.set_state(AnonQuestionStates.waiting_for_reply)
        await state.update_data(reply_to_user_id=target_user_id)
        return

    is_blocked = False
    try:
        async with get_session() as session:
            is_blocked = await crud.is_anon_sender_blocked(
                session=session, recipient_id=target_user_id, sender_id=sender_id
            )
    except Exception as db_err:
        logger.debug(f"Anonim javob blok tekshiruvida ogohlantirish: {db_err}")

    if is_blocked:
        await message.reply(
            "🚫 <b>Siz ushbu foydalanuvchiga javob yubora olmaysiz.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
        )
        return

    safe_reply = html.escape(reply_text)
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↩️ Anonim javob yozish", callback_data=f"anon_reply:{sender_id}")
    )

    reply_msg_text = (
        "💌 <b>Siz yuborgan anonim savolga javob keldi!</b>\n\n"
        f"«<i>{safe_reply}</i>»\n\n"
        "🔒 <i>Yozishish to'liq anonim davom etmoqda.</i>"
    )

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=reply_msg_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
            protect_content=True,
        )
        if has_media and hasattr(message, "copy_to"):
            try:
                await message.copy_to(chat_id=target_user_id, protect_content=True)
            except Exception as media_err:
                logger.debug(f"Anonim javob mediasini nusxalashda xatolik: {media_err}")
        await message.reply(
            "✅ <b>Javobingiz anonim tarzda muvaffaqiyatli yetkazildi!</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
            protect_content=True,
        )
    except Exception as e:
        logger.error(f"Anonim javobni yuborishda xatolik: {e}")
        await message.reply(
            "❌ Kechirasiz, foydalanuvchiga xabarni yetkazib bo'lmadi (ehtimol u botni to'xtatgan).",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
        )


@router.message(AnonQuestionStates.waiting_for_message)
async def state_process_anon_message(message: Message, state: FSMContext) -> None:
    """Anonim savolni qabul qilib egasiga yetkazish."""
    data = await state.get_data()
    raw_target = data.get("anon_target_id")

    if message.text and message.text.strip().lower() in CANCEL_WORDS:
        await state.clear()
        await message.reply(
            "❌ <b>Amal bekor qilindi.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id)),
        )
        return

    try:
        target_user_id = int(raw_target) if raw_target is not None else None
    except (ValueError, TypeError):
        target_user_id = None

    text = (message.text or message.caption or "").strip()
    await state.clear()

    sender_id = message.from_user.id
    if not target_user_id:
        await message.reply(
            "Qabul qiluvchi aniqlanmadi.",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
        )
        return

    has_media = _has_supported_media(message)
    if not text and has_media:
        text = "(Media fayl ilova qilindi)"

    if not text:
        await message.reply("Iltimos, anonim xabaringiz matnini yozing.", reply_markup=cancel_keyboard())
        await state.set_state(AnonQuestionStates.waiting_for_message)
        await state.update_data(anon_target_id=target_user_id)
        return

    is_blocked = False
    is_accepting = True
    try:
        async with get_session() as session:
            is_blocked = await crud.is_anon_sender_blocked(
                session=session, recipient_id=target_user_id, sender_id=sender_id
            )
            if not is_blocked:
                acc_row = (
                    await session.execute(
                        select(AnonQuestionProfile.is_accepting).where(
                            AnonQuestionProfile.user_id == target_user_id
                        )
                    )
                ).scalar_one_or_none()
                if acc_row is not None:
                    is_accepting = bool(acc_row)
            if not is_blocked and is_accepting:
                await crud.create_anonymous_message(
                    session=session,
                    sender_id=sender_id,
                    recipient_id=target_user_id,
                    text=text,
                )
    except Exception as db_err:
        logger.warning(f"Anonim xabarni DB ga saqlashda ogohlantirish: {db_err}")

    if is_blocked:
        await message.reply(
            "🚫 <b>Siz ushbu foydalanuvchiga anonim xabar yubora olmaysiz.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
        )
        return

    if not is_accepting:
        await message.reply(
            "⏸ <b>Bu foydalanuvchi hozircha anonim xabarlar qabulini vaqtincha to'xtatgan.</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
        )
        return

    safe_text = html.escape(text)
    alert_text = (
        "💌 <b>Sizga yangi anonim xabar keldi!</b>\n\n"
        f"«<i>{safe_text}</i>»\n\n"
        "🔒 <i>Yuboruvchi shaxsi to'liq sir saqlangan. Pastdagi tugmalar orqali javob berishingiz yoki bloklashingiz mumkin.</i>"
    )

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=alert_text,
            parse_mode="HTML",
            reply_markup=anon_incoming_keyboard(sender_id=sender_id, is_blocked=False),
            protect_content=True,
        )
        if has_media and hasattr(message, "copy_to"):
            try:
                await message.copy_to(chat_id=target_user_id, protect_content=True)
            except Exception as media_err:
                logger.debug(f"Anonim savol mediasini nusxalashda xatolik: {media_err}")

        await message.reply(
            "🎉 <b>Xabaringiz anonim tarzda muvaffaqiyatli yetkazildi!</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
            protect_content=True,
        )
    except Exception as e:
        logger.error(f"Anonim xabarni yetkazishda xatolik: {e}")
        await message.reply(
            "❌ Xabarni yetkazib bo'lmadi. Foydalanuvchi botni to'xtatgan bo'lishi mumkin.",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(sender_id)),
        )
