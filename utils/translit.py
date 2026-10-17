"""
O'zbek tili Lotin va Kirill yozuvlari o'rtasida ikki tomonlama aqlli transliteratsiya moduli.
Qo'llab-quvvatlanadi:
- Sh, Ch, O', G', Yo, Yu, Ya, Ye, Ts, E
- Katta va kichik harflar
- Qidiruv uchun normallashtirish (smart search normalization)
"""
import re
from typing import Tuple

# Kirill -> Lotin lug'ati
CYR_TO_LAT_MAP = {
    "А": "A", "а": "a",
    "Б": "B", "б": "b",
    "В": "V", "в": "v",
    "Г": "G", "г": "g",
    "Д": "D", "д": "d",
    "Е": "E", "е": "e",
    "Ё": "Yo", "ё": "yo",
    "Ж": "J", "ж": "j",
    "З": "Z", "з": "z",
    "И": "I", "и": "i",
    "Й": "Y", "й": "y",
    "К": "K", "к": "k",
    "Л": "L", "л": "l",
    "М": "M", "м": "m",
    "Н": "N", "н": "n",
    "О": "O", "о": "o",
    "П": "P", "п": "p",
    "Р": "R", "р": "r",
    "С": "S", "с": "s",
    "Т": "T", "т": "t",
    "У": "U", "у": "u",
    "Ф": "F", "ф": "f",
    "Х": "X", "х": "x",
    "Ц": "Ts", "ц": "ts",
    "Ч": "Ch", "ч": "ch",
    "Ш": "Sh", "ш": "sh",
    "Щ": "Sh", "щ": "sh",
    "Ъ": "'", "ъ": "'",
    "Ы": "I", "ы": "i",
    "Ь": "", "ь": "",
    "Э": "E", "э": "e",
    "Ю": "Yu", "ю": "yu",
    "Я": "Ya", "я": "ya",
    "Ў": "O'", "ў": "o'",
    "Ғ": "G'", "ғ": "g'",
    "Қ": "Q", "қ": "q",
    "Ҳ": "H", "ҳ": "h",
}

# Lotin -> Kirill ko'p harfli birikmalar
LAT_TO_CYR_MULTI = [
    ("sh", "ш"), ("Sh", "Ш"), ("SH", "Ш"),
    ("ch", "ч"), ("Ch", "Ч"), ("CH", "Ч"),
    ("yo", "ё"), ("Yo", "Ё"), ("YO", "Ё"),
    ("yu", "ю"), ("Yu", "Ю"), ("YU", "Ю"),
    ("ya", "я"), ("Ya", "Я"), ("YA", "Я"),
    ("ts", "ц"), ("Ts", "Ц"), ("TS", "Ц"),
    ("ye", "е"), ("Ye", "Е"), ("YE", "Е"),
    ("o'", "ў"), ("O'", "Ў"), ("o`", "ў"), ("O`", "Ў"), ("oʻ", "ў"), ("Oʻ", "Ў"), ("o‘", "ў"), ("O‘", "Ў"),
    ("g'", "ғ"), ("G'", "Ғ"), ("g`", "ғ"), ("G`", "Ғ"), ("gʻ", "ғ"), ("Gʻ", "Ғ"), ("g‘", "ғ"), ("G‘", "Ғ"),
]

# Lotin -> Kirill yakka harflar
LAT_TO_CYR_SINGLE = {
    "a": "а", "A": "А",
    "b": "б", "B": "Б",
    "d": "д", "D": "Д",
    "e": "е", "E": "Э",
    "f": "ф", "F": "Ф",
    "g": "г", "G": "Г",
    "h": "ҳ", "H": "Ҳ",
    "i": "и", "I": "И",
    "j": "ж", "J": "Ж",
    "k": "к", "K": "К",
    "l": "л", "L": "Л",
    "m": "м", "M": "М",
    "n": "н", "N": "Н",
    "o": "о", "O": "О",
    "p": "п", "P": "П",
    "q": "қ", "Q": "Қ",
    "r": "р", "R": "Р",
    "s": "с", "S": "С",
    "t": "т", "T": "Т",
    "u": "у", "U": "У",
    "v": "в", "V": "В",
    "x": "х", "X": "Х",
    "y": "й", "Y": "Й",
    "z": "з", "Z": "З",
    "'": "ъ", "`": "ъ", "ʻ": "ъ", "‘": "ъ",
}


def cyrillic_to_latin(text: str) -> str:
    """Kirill yozuvidagi matnni Lotin yozuviga o'giradi."""
    if not text:
        return ""
    result = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        # So'z boshidagi 'Е'/'е' -> 'Ye'/'ye'
        if char in ("Е", "е") and (i == 0 or text[i - 1] in " \n\t.,!?-:;\"'()[]"):
            res = "Ye" if char == "Е" else "ye"
            result.append(res)
            i += 1
            continue

        result.append(CYR_TO_LAT_MAP.get(char, char))
        i += 1
    return "".join(result)


def latin_to_cyrillic(text: str) -> str:
    """Lotin yozuvidagi matnni Kirill yozuviga o'giradi."""
    if not text:
        return ""
    res = text
    # Ko'p harfli birikmalarni almashtirish
    for lat, cyr in LAT_TO_CYR_MULTI:
        res = res.replace(lat, cyr)

    # Yakka harflarni almashtirish
    out = []
    for char in res:
        out.append(LAT_TO_CYR_SINGLE.get(char, char))
    return "".join(out)


def get_both_scripts(text: str) -> Tuple[str, str]:
    """
    Kiritilgan matnning ham Lotin, ham Kirill variantlarini qaytaradi.
    Qidiruvda ikkala yozuv bo'yicha ham natija topish uchun ishlatiladi.
    """
    clean = text.strip()
    lat = cyrillic_to_latin(clean).lower()
    cyr = latin_to_cyrillic(clean).lower()
    return lat, cyr
