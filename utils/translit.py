"""
O'zbek tili Lotin va Kirill yozuvlari o'rtasida ikki tomonlama aqlli transliteratsiya moduli.
Qo'llab-quvvatlanadi:
- Sh, Ch, O', G', Yo, Yu, Ya, Ye, Ts, E
- Katta va kichik harflar
- Qidiruv uchun normallashtirish (smart search normalization)
"""
import re
from typing import Tuple, Dict, List

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


ACTOR_ALIASES: Dict[str, List[str]] = {
    "statham": ["Jason Statham", "Стэйтем", "Стетхем", "Стетхэм", "Steytem"],
    "jason statham": ["Jason Statham", "Джейсон Стэйтем", "Джейсон Стетхэм", "Jeyson Steytem"],
    "стэйтем": ["Jason Statham", "Statham", "Стетхэм", "Steytem"],
    "стетхэм": ["Jason Statham", "Statham", "Стэйтем", "Steytem"],
    "джейсон стэйтем": ["Jason Statham", "Jeyson Steytem", "Statham"],
    "reeves": ["Keanu Reeves", "Ривз", "Киану Ривз"],
    "keanu": ["Keanu Reeves", "Киану Ривз"],
    "keanu reeves": ["Keanu Reeves", "Киану Ривз", "Kianu Rivz"],
    "ривз": ["Keanu Reeves", "Киану Ривз", "Reeves"],
    "киану": ["Keanu Reeves", "Киану Ривз"],
    "киану ривз": ["Keanu Reeves", "Kianu Rivz", "Reeves"],
    "cruise": ["Tom Cruise", "Круз", "Том Круз"],
    "tom cruise": ["Tom Cruise", "Том Круз", "Tom Kruz"],
    "круз": ["Tom Cruise", "Том Круз", "Cruise"],
    "том круз": ["Tom Cruise", "Tom Kruz", "Cruise"],
    "diesel": ["Vin Diesel", "Дизель", "Вин Дизель"],
    "vin diesel": ["Vin Diesel", "Вин Дизель"],
    "дизель": ["Vin Diesel", "Вин Дизель", "Diesel"],
    "вин дизель": ["Vin Diesel", "Diesel"],
    "chan": ["Jackie Chan", "Чан", "Джеки Чан"],
    "jackie chan": ["Jackie Chan", "Джеки Чан"],
    "джеки чан": ["Jackie Chan", "Chan"],
    "smith": ["Will Smith", "Смит", "Уилл Смит"],
    "will smith": ["Will Smith", "Уилл Смит"],
    "уилл смит": ["Will Smith", "Smith"],
    "dicaprio": ["Leonardo DiCaprio", "Ди Каприо", "Дикаприо", "Леонардо Ди Каприо"],
    "leonardo dicaprio": ["Leonardo DiCaprio", "Леонардо Ди Каприо", "Ди Каприо"],
    "ди каприо": ["Leonardo DiCaprio", "DiCaprio", "Леонардо Ди Каприо"],
    "дикаприо": ["Leonardo DiCaprio", "DiCaprio", "Леонардо Ди Каприо"],
    "леонардо ди каприо": ["Leonardo DiCaprio", "DiCaprio"],
    "pitt": ["Brad Pitt", "Питт", "Брэд Питт"],
    "brad pitt": ["Brad Pitt", "Брэд Питт"],
    "брэд питт": ["Brad Pitt", "Pitt"],
    "джонсон": ["Dwayne Johnson", "Джонсон", "Скала", "Dwayne Johnson"],
    "дуэйн джонсон": ["Dwayne Johnson", "Dwayne Johnson"],
    "dwayne johnson": ["Dwayne Johnson", "Дуэйн Джонсон", "Скала"],
    "willis": ["Bruce Willis", "Уиллис", "Брюс Уиллис"],
    "bruce willis": ["Bruce Willis", "Брюс Уиллис"],
    "брюс уиллис": ["Bruce Willis", "Willis"],
    "depp": ["Johnny Depp", "Депп", "Джонни Депп"],
    "johnny depp": ["Johnny Depp", "Джонни Депп"],
    "джонни депп": ["Johnny Depp", "Depp"],
    "stallone": ["Sylvester Stallone", "Сталлоне", "Сильвестр Сталлоне"],
    "sylvester stallone": ["Sylvester Stallone", "Сильвестр Сталлоне"],
    "сильвестр сталлоне": ["Sylvester Stallone", "Stallone"],
    "schwarzenegger": ["Arnold Schwarzenegger", "Шварценеггер", "Арнольд Шварценеггер"],
    "arnold schwarzenegger": ["Arnold Schwarzenegger", "Арнольд Шварценеггер"],
    "арнольд шварценеггер": ["Arnold Schwarzenegger", "Schwarzenegger"],
    "шварценеггер": ["Arnold Schwarzenegger", "Schwarzenegger"],
}


def get_actor_variants(text: str) -> List[str]:
    """
    Aktyor nomi uchun barcha qidiruv variantlarini qaytaradi:
    - Asl matn
    - Lotin va Kirill transliteratsiyasi
    - Agar xalqaro mashhur aktyor bo'lsa, ingliz va o'zbek/rus tillaridagi mosliklari
    """
    clean = text.strip()
    if not clean:
        return []
    lat, cyr = get_both_scripts(clean)
    variants: List[str] = []
    for candidate in [clean, lat, cyr]:
        if candidate and candidate not in variants:
            variants.append(candidate)

    low_clean = clean.lower()
    low_lat = lat.lower()
    low_cyr = cyr.lower()
    for k, aliases in ACTOR_ALIASES.items():
        if k in low_clean or k in low_lat or k in low_cyr:
            for al in aliases:
                if al not in variants:
                    variants.append(al)
                al_lat, al_cyr = get_both_scripts(al)
                if al_lat not in variants:
                    variants.append(al_lat)
                if al_cyr not in variants:
                    variants.append(al_cyr)

    words = clean.split()
    if len(words) > 1:
        for w in words:
            if len(w) >= 3:
                w_low = w.lower()
                for k, aliases in ACTOR_ALIASES.items():
                    if k == w_low:
                        for al in aliases:
                            if al not in variants:
                                variants.append(al)

    return variants

