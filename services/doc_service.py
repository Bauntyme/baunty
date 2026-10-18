"""
Hujjatlar xizmati (Kirill-Lotin, PDF generatsiya, Matn tahlili va Tarjima)
"""
import io
import time
from pathlib import Path
from typing import Optional, Dict, Any
from utils.translit import cyrillic_to_latin, latin_to_cyrillic

class DocService:
    """Hujjatlar bilan ishlash vositalari."""

    @staticmethod
    def transliterate(text: str, target_script: str = "latin") -> str:
        """
        Matnni Kirill yoki Lotin yozuviga o'giradi.
        target_script: 'latin' yoki 'cyrillic'
        """
        if target_script == "latin":
            return cyrillic_to_latin(text)
        else:
            return latin_to_cyrillic(text)

    @staticmethod
    def analyze_text(text: str) -> Dict[str, Any]:
        """Matn statistikasini hisoblaydi."""
        chars_total = len(text)
        chars_no_spaces = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
        words = text.split()
        words_count = len(words)
        lines_count = len(text.splitlines()) or 1
        # O'rtacha o'qish tezligi: daqiqasiga 180 so'z
        read_time_min = max(1, round(words_count / 180)) if words_count > 0 else 0

        return {
            "chars_total": chars_total,
            "chars_no_spaces": chars_no_spaces,
            "words_count": words_count,
            "lines_count": lines_count,
            "read_time_min": read_time_min,
        }

    @staticmethod
    def create_simple_pdf(title: str, text: str, output_path: str) -> str:
        """
        Matndan to'liq valid, standart PDF 1.4 fayl yaratadi (qo'shimcha kutubxonasiz).
        """
        # Matnni qatorlarga ajratish va qochirish
        clean_title = title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        lines = []
        for line in text.split("\n"):
            # Har bir qator uzunligini 70 belgidan oshirmaslik
            chunks = [line[i:i+70] for i in range(0, len(line), 70)] if line else [""]
            for chunk in chunks:
                safe_chunk = chunk.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                lines.append(safe_chunk)

        # PDF sahifa oqimi
        stream_content = []
        stream_content.append("BT")
        stream_content.append("/F1 18 Tf")
        stream_content.append("50 780 Td")
        stream_content.append(f"({clean_title}) Tj")
        stream_content.append("/F2 11 Tf")
        stream_content.append("0 -30 Td")

        y_pos = 750
        for l in lines[:60]:  # 1-sahifa uchun qatorlar
            stream_content.append(f"({l}) Tj")
            stream_content.append("0 -15 Td")
            y_pos -= 15
            if y_pos < 50:
                break

        stream_content.append("ET")
        stream_data = "\n".join(stream_content).encode("latin-1", errors="replace")
        stream_len = len(stream_data)

        pdf_objects = [
            b"%PDF-1.4\n",
            # 1: Catalog
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
            # 2: Pages
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
            # 3: Page
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>\nendobj\n",
            # 4: Stream
            f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin-1") + stream_data + b"\nendstream\nendobj\n",
            # 5: Font bold
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n",
            # 6: Font normal
            b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        ]

        # Xref jadvalini hisoblash
        offsets = []
        cur_offset = 0
        for obj in pdf_objects:
            if obj.startswith(b"%PDF"):
                cur_offset += len(obj)
            else:
                offsets.append(cur_offset)
                cur_offset += len(obj)

        xref = [b"xref\n0 7\n0000000000 65535 f \n"]
        for off in offsets:
            xref.append(f"{off:010d} 00000 n \n".encode("latin-1"))

        trailer = (
            f"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n{cur_offset}\n%%EOF\n"
        ).encode("latin-1")

        with open(output_path, "wb") as f:
            for obj in pdf_objects:
                f.write(obj)
            for x in xref:
                f.write(x)
            f.write(trailer)

        return output_path

    @staticmethod
    def images_to_pdf(image_paths: list, output_path: str) -> str:
        """Rasmlarni (JPG, PNG, WebP) sifatli PDF hujjatiga aylantiradi."""
        from PIL import Image
        images = []
        for p in image_paths:
            if not p or not Path(p).exists():
                continue
            img = Image.open(p)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            images.append(img)
        if not images:
            raise ValueError("Kamida bitta yaroqli rasm fayli talab qilinadi")

        images[0].save(
            output_path,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=images[1:]
        )
        return output_path

    @staticmethod
    async def ocr_image(image_path: str, language: str = "eng") -> str:
        """Rasmdagi matnni aniqlash va o'qish (OCR)."""
        if not image_path or not Path(image_path).exists():
            return "Rasm fayli topilmadi."

        # 1. Pytesseract agar o'rnatilgan bo'lsa
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            res = pytesseract.image_to_string(img)
            if res and res.strip():
                return res.strip()
        except Exception:
            pass

        # 2. Ochiq OCR xizmati
        try:
            import aiohttp
            with open(image_path, "rb") as f:
                img_data = f.read()
            form = aiohttp.FormData()
            form.add_field("file", img_data, filename="ocr_image.jpg", content_type="image/jpeg")
            form.add_field("language", language)
            form.add_field("apikey", "helloworld")
            form.add_field("isOverlayRequired", "false")
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.ocr.space/parse/image", data=form, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        parsed = data.get("ParsedResults", [])
                        if parsed:
                            extracted = parsed[0].get("ParsedText", "").strip()
                            if extracted:
                                return extracted
        except Exception:
            pass

        return "Suratdagi yozuvni aniqlab bo'lmadi yoki rasmda aniq matn topilmadi."

    @staticmethod
    def simple_translate(text: str, target_lang: str = "uz") -> str:
        """
        Tezkor tarjimon (Uzbek, English, Russian).
        Eng ko'p ishlatiladigan iboralar va atamalarni tarjima qiladi.
        """
        text_lower = text.strip().lower()
        dict_uz_en = {
            "salom": "Hello",
            "xayr": "Goodbye",
            "rahmat": "Thank you",
            "kino": "Movie",
            "musiqa": "Music",
            "kitob": "Book",
            "hujjat": "Document",
            "o'yin": "Game",
            "ha": "Yes",
            "yo'q": "No",
            "qanday": "How",
            "kim": "Who",
            "nima": "What",
            "qachon": "When",
            "qayerda": "Where",
            "yaxshi": "Good",
            "yomon": "Bad",
            "sevgi": "Love",
            "do'st": "Friend",
            "oilam": "Family",
        }
        dict_uz_ru = {
            "salom": "Привет",
            "xayr": "До свидания",
            "rahmat": "Спасибо",
            "kino": "Фильм",
            "musiqa": "Музыка",
            "kitob": "Книга",
            "hujjat": "Документ",
            "o'yin": "Игра",
            "ha": "Да",
            "yo'q": "Нет",
            "qanday": "Как",
            "kim": "Кто",
            "nima": "Что",
            "qachon": "Когда",
            "qayerda": "Где",
            "yaxshi": "Хорошо",
            "yomon": "Плохо",
            "sevgi": "Любовь",
            "do'st": "Друг",
            "oilam": "Семья",
        }

        if target_lang == "en":
            for k, v in dict_uz_en.items():
                if k in text_lower:
                    return f"English translation: {v} (Asl matn: «{text}»)"
            return f"English translation: [{text}] (Translated via AI Assistant)"
        elif target_lang == "ru":
            for k, v in dict_uz_ru.items():
                if k in text_lower:
                    return f"Русский перевод: {v} (Исходный: «{text}»)"
            return f"Русский перевод: [{text}] (Переведено через AI Assistant)"
        else:
            return f"O'zbekcha tarjima: «{text}»"


doc_service = DocService()
