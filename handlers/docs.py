"""
Hujjatlar bo'limi handlerlari (PDF, Rasmdan PDF, OCR, Kirill-Lotin, Matn tahlili, Tarjima)
"""
import uuid
import html
import logging
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from config import config
from services.doc_service import doc_service
from keyboards.default import cancel_keyboard, main_menu_keyboard
from utils.states import DocsStates
from utils.helpers import safe_remove_file

logger = logging.getLogger(__name__)
router = Router(name="docs_router")


def docs_menu_keyboard() -> InlineKeyboardMarkup:
    """Hujjatlar menyusi klaviaturasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Kirill ⇄ Lotin", callback_data="doc:translit"),
        InlineKeyboardButton(text="📄 Matndan PDF", callback_data="doc:pdf"),
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Rasmdan PDF", callback_data="doc:img2pdf"),
        InlineKeyboardButton(text="🔍 Rasmdan matn (OCR)", callback_data="doc:ocr"),
    )
    builder.row(
        InlineKeyboardButton(text="🌐 Tezkor Tarjimon", callback_data="doc:translate"),
        InlineKeyboardButton(text="📊 Matn tahlili", callback_data="doc:analyze"),
    )
    app_url = config.webapp_url_resolved
    if app_url and app_url.startswith("https://"):
        from aiogram.types import WebAppInfo
        builder.row(
            InlineKeyboardButton(text="📱 Mini App Hujjatlar bo'limi", web_app=WebAppInfo(url=f"{app_url}#docs"))
        )
    return builder.as_markup()


@router.message(Command("docs"))
@router.message(F.text == "📄 Hujjatlar")
async def cmd_docs_menu(message: Message, state: FSMContext) -> None:
    """Hujjatlar asosiy bo'limi."""
    await state.clear()
    text = (
        "📄 <b>Hujjatlar va Matn vositalari markazi</b>\n\n"
        "Quyidagi xizmatlardan birini tanlang:\n"
        "• <b>Kirill ⇄ Lotin:</b> Matnlarni to'g'ri o'girish\n"
        "• <b>Matndan PDF:</b> Istalgan matndan PDF hujjat yaratish\n"
        "• <b>Rasmdan PDF:</b> Fotosuratlarni PDF kitob/hujjatga aylantirish\n"
        "• <b>Rasmdan matn (OCR):</b> Rasmdagi yozuvlarni matnga aylantirish\n"
        "• <b>Tezkor Tarjimon:</b> Ko'p tilli tarjima (UZ, EN, RU)\n"
        "• <b>Matn tahlili:</b> So'zlar, belgilar soni va o'qish vaqti"
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
        f"<code>{html.escape(converted)}</code>"
    )
    await message.reply(
        response,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
    )


@router.callback_query(F.data == "doc:pdf")
async def cb_doc_pdf(callback: CallbackQuery, state: FSMContext) -> None:
    """Matndan PDF yaratish so'rovi."""
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

        safe_title = html.escape(title)
        caption = (
            f"📄 <b>{safe_title}</b>\n\n"
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
        logger.exception(f"PDF yaratish xatosi: {e}")
        safe_remove_file(out_file)
        await status_msg.edit_text("❌ PDF yaratishda xatolik yuz berdi.", parse_mode="HTML")


@router.callback_query(F.data == "doc:img2pdf")
async def cb_doc_img2pdf(callback: CallbackQuery, state: FSMContext) -> None:
    """Rasmdan PDF yaratish so'rovi."""
    await state.set_state(DocsStates.waiting_for_img_to_pdf)
    await callback.message.answer(
        "🖼 <b>PDF qilish uchun fotosurat(lar) yuboring:</b>\n"
        "Rasm yuboring, bot uni standart A4 PDF hujjatiga aylantirib beradi.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(DocsStates.waiting_for_img_to_pdf, F.photo | F.document)
async def state_process_img_to_pdf(message: Message, state: FSMContext) -> None:
    """Rasmni PDF ga aylantirish."""
    await state.clear()
    status_msg = await message.reply("⏳ <b>Rasm PDF formatiga o'tkazilmoqda...</b>", parse_mode="HTML")

    temp_img = str(config.download_path / f"img_{uuid.uuid4().hex[:8]}.jpg")
    out_pdf = str(config.download_path / f"imgdoc_{uuid.uuid4().hex[:8]}.pdf")

    try:
        if message.photo:
            photo = message.photo[-1]
            await message.bot.download(photo, destination=temp_img)
        elif message.document and message.document.mime_type and "image" in message.document.mime_type:
            await message.bot.download(message.document, destination=temp_img)
        else:
            await status_msg.edit_text("❌ Iltimos, faqat rasm faylini yuboring.")
            return

        doc_service.images_to_pdf([temp_img], out_pdf)
        pdf_input = FSInputFile(out_pdf, filename="Hujjat_rasm.pdf")

        caption = (
            "🖼 <b>Rasmdan yaratilgan PDF hujjat</b>\n\n"
            f"🤖 <b>@{config.BOT_USERNAME.lstrip('@')} orqali tayyorlandi</b>"
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
    except Exception as e:
        logger.exception(f"Rasmdan PDF yaratish xatosi: {e}")
        await status_msg.edit_text("❌ Rasmni PDF ga aylantirishda xatolik yuz berdi.", parse_mode="HTML")
    finally:
        safe_remove_file(temp_img)
        safe_remove_file(out_pdf)


@router.callback_query(F.data == "doc:ocr")
async def cb_doc_ocr(callback: CallbackQuery, state: FSMContext) -> None:
    """OCR (Rasmdan matn olish) so'rovi."""
    await state.set_state(DocsStates.waiting_for_ocr)
    await callback.message.answer(
        "🔍 <b>Rasmdagi matnni o'qish (OCR)</b>\n\n"
        "Matn yozilgan fotosuratni yuboring. Bot undagi yozuvlarni ajratib beradi.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(DocsStates.waiting_for_ocr, F.photo | F.document)
async def state_process_ocr(message: Message, state: FSMContext) -> None:
    """Rasmdan matnni aniqlab yuborish."""
    await state.clear()
    status_msg = await message.reply("🔍 <b>Suratdagi yozuvlar o'qilmoqda...</b>", parse_mode="HTML")

    temp_img = str(config.download_path / f"ocr_{uuid.uuid4().hex[:8]}.jpg")
    try:
        if message.photo:
            photo = message.photo[-1]
            await message.bot.download(photo, destination=temp_img)
        elif message.document and message.document.mime_type and "image" in message.document.mime_type:
            await message.bot.download(message.document, destination=temp_img)
        else:
            await status_msg.edit_text("❌ Iltimos, matn yozilgan fotosurat yuboring.")
            return

        extracted = await doc_service.ocr_image(temp_img)
        clean_ocr = (extracted or "Matn topilmadi").strip()
        if len(clean_ocr) > 3800:
            clean_ocr = clean_ocr[:3800] + "... (qisqartirildi)"

        caption = (
            "🔍 <b>Rasmdan ajratib olingan matn:</b>\n\n"
            f"<code>{html.escape(clean_ocr)}</code>"
        )
        await status_msg.edit_text(caption, parse_mode="HTML")
    except Exception as e:
        logger.exception(f"OCR xatoligi: {e}")
        await status_msg.edit_text("❌ Rasmdagi matnni o'qishda xatolik yuz berdi.", parse_mode="HTML")
    finally:
        safe_remove_file(temp_img)


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
        f"🇺🇿 <b>Asl matn:</b> {html.escape(text)}\n"
        f"🇬🇧 <b>Inglizcha:</b> {html.escape(en_res)}\n"
        f"🇷🇺 <b>Ruscha:</b> {html.escape(ru_res)}"
    )
    await message.reply(
        res_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
    )


@router.callback_query(F.data == "doc:analyze")
async def cb_doc_analyze(callback: CallbackQuery, state: FSMContext) -> None:
    """Matn tahlili so'rovi."""
    await state.set_state(DocsStates.waiting_for_analyze)
    await callback.message.answer(
        "📊 <b>Tahlil qilish uchun matnni yuboring:</b>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(DocsStates.waiting_for_analyze, F.text)
async def state_process_analyze(message: Message, state: FSMContext) -> None:
    """Matn statistikasini tahlil qilib chiqarish."""
    text = message.text.strip()
    await state.clear()

    stats = doc_service.analyze_text(text)
    res_text = (
        "📊 <b>Matn tahlili natijalari:</b>\n\n"
        f"📝 <b>So'zlar soni:</b> {stats['words_count']} ta\n"
        f"🔤 <b>Belgilar (jami):</b> {stats['chars_total']} ta\n"
        f"✂️ <b>Bo'sh joysiz belgilar:</b> {stats['chars_no_spaces']} ta\n"
        f"📑 <b>Qatorlar soni:</b> {stats['lines_count']} ta\n"
        f"⏱ <b>Taxminiy o'qish vaqti:</b> ~{stats['read_time_min']} daqiqa"
    )
    await message.reply(
        res_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=config.is_admin(message.from_user.id))
    )
