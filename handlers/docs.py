"""
Hujjatlar bo'limi handlerlari (PDF, Kirill-Lotin, Matn tahlili, Tarjima)
"""
import uuid
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from config import config
from services.doc_service import doc_service
from keyboards.default import cancel_keyboard, main_menu_keyboard
from utils.states import DocsStates
from utils.helpers import safe_remove_file

router = Router(name="docs_router")


def docs_menu_keyboard() -> InlineKeyboardMarkup:
    """Hujjatlar menyusi klaviaturasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Kirill ⇄ Lotin", callback_data="doc:translit"),
        InlineKeyboardButton(text="📄 Matndan PDF yaratish", callback_data="doc:pdf"),
    )
    builder.row(
        InlineKeyboardButton(text="🌐 Tezkor Tarjimon", callback_data="doc:translate"),
        InlineKeyboardButton(text="📊 Matn tahlili", callback_data="doc:analyze"),
    )
    return builder.as_markup()


@router.message(F.text == "📄 Hujjatlar")
async def cmd_docs_menu(message: Message, state: FSMContext) -> None:
    """Hujjatlar asosiy bo'limi."""
    await state.clear()
    text = (
        "📄 <b>Hujjatlar va Matn vositalari</b>\n\n"
        "Quyidagi xizmatlardan birini tanlang:\n"
        "• <b>Kirill ⇄ Lotin:</b> Matnlarni to'g'ri o'girish\n"
        "• <b>Matndan PDF:</b> Istalgan matndan PDF hujjat yaratish\n"
        "• <b>Tezkor Tarjimon:</b> Lug'at va tarjima\n"
        "• <b>Matn tahlili:</b> So'zlar, harflar soni va o'qish vaqti"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=docs_menu_keyboard())


@router.callback_query(F.data == "doc:translit")
async def cb_doc_translit(callback: CallbackQuery, state: FSMContext) -> None:
    """Transliteratsiya so'rovi."""
    await state.set_state(DocsStates.waiting_for_translit)
    await callback.message.answer(
        "✍️ <b>Lotin yoki Kirill yozuvidagi matnni yuboring:</b>\n"
        "Bot uni avtomatik qarama-qarshi yozuvga o'girib beradi.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(DocsStates.waiting_for_translit, F.text)
async def state_process_translit(message: Message, state: FSMContext) -> None:
    """Transliteratsiya natijasini chiqarish."""
    text = message.text.strip()
    await state.clear()

    # Agar kirill harflari ko'p bo'lsa -> lotin, aks holda -> kirill
    cyr_chars = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    if cyr_chars > len(text) * 0.3:
        converted = doc_service.transliterate(text, target_script="latin")
        direction = "Kirill ➔ Lotin"
    else:
        converted = doc_service.transliterate(text, target_script="cyrillic")
        direction = "Lotin ➔ Kirill"

    response = (
        f"✅ <b>{direction} muvaffaqiyatli o'girildi:</b>\n\n"
        f"<code>{converted}</code>"
    )
    await message.reply(
        response,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
    )


@router.callback_query(F.data == "doc:pdf")
async def cb_doc_pdf(callback: CallbackQuery, state: FSMContext) -> None:
    """PDF yaratish so'rovi."""
    await state.set_state(DocsStates.waiting_for_pdf)
    await callback.message.answer(
        "📄 <b>PDF yaratish uchun matnni yuboring:</b>\n"
        "Birinchi qator PDF sarlavhasi sifatida qabul qilinadi.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(DocsStates.waiting_for_pdf, F.text)
async def state_process_pdf(message: Message, state: FSMContext) -> None:
    """Matndan PDF yaratib foydalanuvchiga yuborish."""
    raw_text = message.text.strip()
    await state.clear()

    lines = raw_text.splitlines()
    title = lines[0][:40] if lines else "Hujjat"
    body = "\n".join(lines[1:]) if len(lines) > 1 else raw_text

    status_msg = await message.reply("⏳ <b>PDF hujjat yaratilmoqda...</b>", parse_mode="HTML")

    out_file = str(config.download_path / f"doc_{uuid.uuid4().hex[:8]}.pdf")
    try:
        doc_service.create_simple_pdf(title=title, text=body, output_path=out_file)
        pdf_input = FSInputFile(out_file, filename=f"{title[:25]}.pdf")

        caption = (
            f"📄 <b>{title}</b>\n\n"
            f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} orqali yaratildi</b>"
        )
        await message.reply_document(
            document=pdf_input,
            caption=caption,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
        )
        try:
            await status_msg.delete()
        except Exception:
            pass
        safe_remove_file(out_file)
    except Exception as e:
        safe_remove_file(out_file)
        await status_msg.edit_text("❌ PDF yaratishda xatolik yuz berdi.", parse_mode="HTML")


@router.callback_query(F.data == "doc:translate")
async def cb_doc_translate(callback: CallbackQuery, state: FSMContext) -> None:
    """Tarjima so'rovi."""
    await state.set_state(DocsStates.waiting_for_translate)
    await callback.message.answer(
        "🌐 <b>Tarjima qilish uchun so'z yoki matn yuboring:</b>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(DocsStates.waiting_for_translate, F.text)
async def state_process_translate(message: Message, state: FSMContext) -> None:
    """Tarjimani chiqarish."""
    text = message.text.strip()
    await state.clear()

    en_res = doc_service.simple_translate(text, target_lang="en")
    ru_res = doc_service.simple_translate(text, target_lang="ru")

    res_text = (
        f"🌐 <b>Tarjima natijalari:</b>\n\n"
        f"🇺🇿 <b>Asl matn:</b> {text}\n"
        f"🇬🇧 <b>Inglizcha:</b> {en_res}\n"
        f"🇷🇺 <b>Ruscha:</b> {ru_res}"
    )
    await message.reply(
        res_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
    )


@router.callback_query(F.data == "doc:analyze")
async def cb_doc_analyze(callback: CallbackQuery, state: FSMContext) -> None:
    """Matn tahlili so'rovi."""
    await state.set_state(DocsStates.waiting_for_translit)  # Reuse text prompt
    await callback.message.answer(
        "📊 <b>Tahlil qilish uchun matnni yuboring:</b>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()
