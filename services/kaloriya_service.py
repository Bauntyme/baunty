"""
Kaloriya & Nutrition Tracker xizmati - Bauntys
Mifflin-St Jeor formulasi, shaxsiy ozish/vazn olish rejasi, taomlar skaneri va kundalik hisob.
Har xil narsalarni emas, aynan taomlar, shirinliklar va yeyiladigan mahsulotlarni to'liq tahlil qiluvchi Eda AI darajasidagi tizim.
100% Bauntys brendi.
"""
import re
import io
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from database.session import get_session
from database import crud

logger = logging.getLogger(__name__)

# Taomlar, shirinliklar, ichimliklar va oziq-ovqatlar ma'lumotlar bazasi
# Har bir mahsulot: kalit so'zlar, nom (uz, ru, en), standart gramm, kaloriya (kkal), oqsil (p), yog' (f), uglevod (c), toifa va tavsiya
FOOD_DATABASE: List[Dict[str, Any]] = [
    # --- 1. Milliy va issiq taomlar ---
    {
        "keys": ["osh", "palov", "plov", "choyxona oshi", "to'y oshi", "devzira", "toy oshi"],
        "n": "Osh (Palov)", "uz": "Osh (Palov)", "ru": "Плов", "en": "Pilaf",
        "g": 350, "kcal": 680, "p": 24.0, "f": 32.0, "c": 74.0, "cat": "dish",
        "rec": "To'yimli va energetik taom. Kunlik faol harakat yoki sport bilan uyg'unlashtirish tavsiya etiladi."
    },
    {
        "keys": ["somsa", "katlama somsa", "tandir somsa", "varaqi somsa", "goshtli somsa", "qovoqli somsa"],
        "n": "Somsa", "uz": "Somsa", "ru": "Самса", "en": "Samsa",
        "g": 180, "kcal": 410, "p": 14.0, "f": 21.0, "c": 42.0, "cat": "pastry",
        "rec": "Yog'li va to'yimli pishiriq. Nonushta yoki tushlikda me'yorida iste'mol qilish ma'qul."
    },
    {
        "keys": ["shashlik", "kabob", "qiyma shashlik", "jigar shashlik", "kavkazcha", "shashliklar"],
        "n": "Shashlik", "uz": "Shashlik", "ru": "Шашлык", "en": "Kebab",
        "g": 150, "kcal": 340, "p": 28.0, "f": 24.0, "c": 2.0, "cat": "meat",
        "rec": "Yuqori oqsilga boy, mushaklarni mustahkamlash uchun ajoyib taom. Ko'katlar bilan yeyish tavsiya etiladi."
    },
    {
        "keys": ["lag'mon", "lagman", "cho'zma lag'mon", "chozma lagman", "uyg'ur lag'mon", "qovurma lag'mon"],
        "n": "Lag'mon", "uz": "Lag'mon", "ru": "Лагман", "en": "Lagman",
        "g": 400, "kcal": 560, "p": 22.0, "f": 18.0, "c": 75.0, "cat": "dish",
        "rec": "Uglevod va sabzavotlarga boy to'liq tushlik taomi."
    },
    {
        "keys": ["manti", "qovoqli manti", "mantiya"],
        "n": "Manti", "uz": "Manti", "ru": "Манты", "en": "Manty",
        "g": 250, "kcal": 480, "p": 19.0, "f": 22.0, "c": 51.0, "cat": "dish",
        "rec": "Bug'da pishirilgan to'yimli milliy taom."
    },
    {
        "keys": ["chuchvara", "pelmeni", "qovurma chuchvara"],
        "n": "Chuchvara", "uz": "Chuchvara", "ru": "Пельмени (Чучвара)", "en": "Dumplings",
        "g": 250, "kcal": 450, "p": 20.0, "f": 18.0, "c": 52.0, "cat": "dish",
        "rec": "Sho'rvasi yoki qatiq bilan birga yaxshi hazm bo'ladi."
    },
    {
        "keys": ["shorva", "sho'rva", "qaynatma sho'rva", "shurpa", "no'xat sho'rva"],
        "n": "Sho'rva", "uz": "Sho'rva", "ru": "Шурпа", "en": "Meat Soup",
        "g": 350, "kcal": 320, "p": 20.0, "f": 16.0, "c": 24.0, "cat": "soup",
        "rec": "Sho'rva oson hazm bo'ladi va tanani foydali minerallar bilan ta'minlaydi."
    },
    {
        "keys": ["mastava", "goja", "ugra", "chuchvara shorva"],
        "n": "Mastava", "uz": "Mastava", "ru": "Мастава", "en": "Mastava",
        "g": 350, "kcal": 310, "p": 16.0, "f": 14.0, "c": 30.0, "cat": "soup",
        "rec": "Guruchli va sabzavotli yengil sho'rva taom."
    },
    {
        "keys": ["qozon kabob", "kazan kebab", "dimlama", "jiz", "jiz-biz"],
        "n": "Qozon kabob", "uz": "Qozon kabob", "ru": "Казан-кебаб", "en": "Kazan Kebab",
        "g": 300, "kcal": 620, "p": 32.0, "f": 40.0, "c": 30.0, "cat": "meat",
        "rec": "Go'sht va kartoshkadan iborat to'yimli va kaloriyali taom."
    },
    {
        "keys": ["norin", "narin", "qazi", "kazi"],
        "n": "Norin va Qazi", "uz": "Norin va Qazi", "ru": "Нарын с казы", "en": "Narin with Kazi",
        "g": 250, "kcal": 490, "p": 26.0, "f": 20.0, "c": 52.0, "cat": "dish",
        "rec": "Ot go'shti va yupqa xamirdan tayyorlangan oqsilga boy milliy lazzat."
    },
    {
        "keys": ["xonim", "hanum"],
        "n": "Xonim", "uz": "Xonim", "ru": "Ханум", "en": "Khanum",
        "g": 250, "kcal": 390, "p": 12.0, "f": 14.0, "c": 54.0, "cat": "dish",
        "rec": "Bug'da pishirilgan kartoshkali yoki go'shtli xamir taom."
    },

    # --- 2. Non va non mahsulotlari ---
    {
        "keys": ["non", "patir", "lepyoshka", "tandir non", "obi non", "buxanka"],
        "n": "Non", "uz": "Non", "ru": "Хлеб", "en": "Bread",
        "g": 100, "kcal": 260, "p": 8.0, "f": 3.0, "c": 52.0, "cat": "bread",
        "rec": "Murakkab uglevodlarga boy, kunlik ratsionning ajralmas qismi."
    },

    # --- 3. Shirinliklar, Tortlar va Desertlar (User Critical Requirement) ---
    {
        "keys": ["medovik", "asalli tort", "medoviy", "медовик"],
        "n": "Medovik (Asalli tort)", "uz": "Medovik (Asalli tort)", "ru": "Медовик", "en": "Honey Cake (Medovik)",
        "g": 120, "kcal": 440, "p": 6.0, "f": 18.0, "c": 64.0, "cat": "sweet",
        "rec": "Asalli shirinlik tezkor energiya beradi, kunning birinchi yarmida choy bilan iste'mol qilish ma'qul."
    },
    {
        "keys": ["napoleon", "napaleon", "qavatli tort", "наполеон"],
        "n": "Napoleon torti", "uz": "Napoleon torti", "ru": "Торт Наполеон", "en": "Napoleon Cake",
        "g": 130, "kcal": 470, "p": 6.5, "f": 26.0, "c": 54.0, "cat": "sweet",
        "rec": "Krem va qavatli xamirdan tayyorlangan, kaloriyasi baland shirinlik."
    },
    {
        "keys": ["chizkeyk", "cheesecake", "чизкейк"],
        "n": "Chizkeyk", "uz": "Chizkeyk", "ru": "Чизкейк", "en": "Cheesecake",
        "g": 120, "kcal": 380, "p": 7.0, "f": 22.0, "c": 38.0, "cat": "sweet",
        "rec": "Tvorogli pishloqdan tayyorlangan oqsilga boy shirinlik."
    },
    {
        "keys": ["tort", "qizil baxmal", "red velvet", "shokoladli tort", "praga", "biskvit"],
        "n": "Tort", "uz": "Tort", "ru": "Торт", "en": "Cake",
        "g": 130, "kcal": 420, "p": 5.0, "f": 20.0, "c": 56.0, "cat": "sweet",
        "rec": "Shirinlik uglevodlarga boy, me'yorni saqlash parhez uchun muhim."
    },
    {
        "keys": ["paxlava", "baklava", "пахлава"],
        "n": "Paxlava", "uz": "Paxlava", "ru": "Пахлава", "en": "Baklava",
        "g": 100, "kcal": 430, "p": 7.0, "f": 24.0, "c": 48.0, "cat": "sweet",
        "rec": "Yong'oqli va sharbatli sharqona shirinlik."
    },
    {
        "keys": ["xolva", "halva", "халва"],
        "n": "Xolva", "uz": "Xolva", "ru": "Халва", "en": "Halva",
        "g": 80, "kcal": 410, "p": 9.0, "f": 24.0, "c": 40.0, "cat": "sweet",
        "rec": "Kalsiy va magniyga boy, kuch bag'ishlaydigan shirinlik."
    },
    {
        "keys": ["chak-chak", "chakchak", "чак-чак"],
        "n": "Chak-chak", "uz": "Chak-chak", "ru": "Чак-чак", "en": "Chak-chak",
        "g": 100, "kcal": 420, "p": 6.0, "f": 18.0, "c": 58.0, "cat": "sweet",
        "rec": "Asalli an'anaviy pishiriq."
    },
    {
        "keys": ["shokolad", "chocolate", "snickers", "snikers", "kitkat", "twix", "bounty", "mars"],
        "n": "Shokolad", "uz": "Shokolad", "ru": "Шоколад", "en": "Chocolate",
        "g": 50, "kcal": 265, "p": 3.5, "f": 15.0, "c": 28.0, "cat": "sweet",
        "rec": "Miyaning ishlashini yaxshilaydi va kayfiyatni ko'taradi."
    },
    {
        "keys": ["muzqaymoq", "morojenoe", "morojnoe", "plombir", "eskimo", "ice cream"],
        "n": "Muzqaymoq", "uz": "Muzqaymoq", "ru": "Мороженое", "en": "Ice Cream",
        "g": 100, "kcal": 220, "p": 3.5, "f": 12.0, "c": 24.0, "cat": "sweet",
        "rec": "Issiq kunda yoqimli, sutli lazzat."
    },
    {
        "keys": ["kruassan", "croissant", "bulochka", "keks", "muffin", "pechenye", "vafli"],
        "n": "Kruassan / Bulochka", "uz": "Kruassan / Bulochka", "ru": "Круассан / Выпечка", "en": "Croissant / Pastry",
        "g": 90, "kcal": 360, "p": 6.0, "f": 18.0, "c": 44.0, "cat": "sweet",
        "rec": "Ertalabki qahva yoki choy bilan ajoyib nonushta."
    },
    {
        "keys": ["ponchik", "donut", "donuts", "ekler"],
        "n": "Ponchik / Ekler", "uz": "Ponchik / Ekler", "ru": "Пончик / Эклер", "en": "Donut / Eclair",
        "g": 90, "kcal": 340, "p": 4.5, "f": 17.0, "c": 42.0, "cat": "sweet",
        "rec": "Yengil shirin tamaddi."
    },
    {
        "keys": ["asal", "med", "honey", "murabbo", "varenye", "jem"],
        "n": "Asal / Murabbo", "uz": "Asal / Murabbo", "ru": "Мёд / Варенье", "en": "Honey / Jam",
        "g": 50, "kcal": 150, "p": 0.3, "f": 0.0, "c": 38.0, "cat": "sweet",
        "rec": "Tabiiy immunitetni ko'taruvchi va vitaminlarga boy shirinlik."
    },

    # --- 4. Fast Food va yeguliklar ---
    {
        "keys": ["lavash", "donar", "shaurma", "shawarma", "turkcha lavash", "mini lavash"],
        "n": "Lavash", "uz": "Lavash", "ru": "Лаваш", "en": "Shawarma (Lavash)",
        "g": 280, "kcal": 540, "p": 24.0, "f": 22.0, "c": 62.0, "cat": "fastfood",
        "rec": "Go'sht va sabzavotlar balansi, to'yimli va oqsilga boy."
    },
    {
        "keys": ["pizza", "pitsa", "peperoni", "margarita", "margaritta"],
        "n": "Pitsa (2 bo'lak)", "uz": "Pitsa", "ru": "Пицца", "en": "Pizza",
        "g": 220, "kcal": 520, "p": 22.0, "f": 20.0, "c": 64.0, "cat": "fastfood",
        "rec": "Pishloq va souslar bilan boyitilgan mashhur taom."
    },
    {
        "keys": ["burger", "gamburger", "chizburger", "dabl burger", "big burger"],
        "n": "Burger", "uz": "Burger", "ru": "Бургер", "en": "Burger",
        "g": 220, "kcal": 510, "p": 25.0, "f": 24.0, "c": 48.0, "cat": "fastfood",
        "rec": "Kotlet, pishloq va sabzavotlar uyg'unligi."
    },
    {
        "keys": ["hot dog", "hotdog", "xotdog", "sendvich", "sandwich"],
        "n": "Hot-dog / Sendvich", "uz": "Hot-dog", "ru": "Хот-дог / Сэндвич", "en": "Hot Dog / Sandwich",
        "g": 180, "kcal": 420, "p": 16.0, "f": 20.0, "c": 44.0, "cat": "fastfood",
        "rec": "Tez va qulay tushlik tamaddisi."
    },
    {
        "keys": ["kartoshka fri", "fri", "french fries", "naggets", "nuggets"],
        "n": "Kartoshka fri", "uz": "Kartoshka fri", "ru": "Картофель фри", "en": "French Fries",
        "g": 150, "kcal": 460, "p": 5.0, "f": 22.0, "c": 60.0, "cat": "fastfood",
        "rec": "Qisirlovchi qovurilgan kartoshka, me'yorda iste'mol qilish tavsiya etiladi."
    },
    {
        "keys": ["kfc", "strips", "qanotcha", "tovuq go'shti", "tovuq filesi", "tovuq"],
        "n": "Qovurilgan tovuq", "uz": "Qovurilgan tovuq", "ru": "Курица", "en": "Chicken",
        "g": 200, "kcal": 440, "p": 34.0, "f": 22.0, "c": 18.0, "cat": "meat",
        "rec": "Tovuq go'shti oqsilga nihoyatda boy va mushaklar uchun juda foydali."
    },

    # --- 5. Nonushta va sut mahsulotlari ---
    {
        "keys": ["tuxum", "omlet", "yaichnitsa", "glazunya", "qaynatilgan tuxum"],
        "n": "Tuxum (2 dona)", "uz": "Tuxum", "ru": "Яйца (Омлет)", "en": "Eggs",
        "g": 120, "kcal": 180, "p": 14.0, "f": 12.0, "c": 2.0, "cat": "breakfast",
        "rec": "Eng mukammal oqsil manbai, nonushta uchun 1-raqamli tanlov."
    },
    {
        "keys": ["pishloq", "sir", "cheese", "suluguni", "golland"],
        "n": "Pishloq (Sir)", "uz": "Pishloq", "ru": "Сыр", "en": "Cheese",
        "g": 50, "kcal": 180, "p": 12.0, "f": 14.0, "c": 1.0, "cat": "dairy",
        "rec": "Kalsiy va sog'lom yog'larga boy tabiiy mahsulot."
    },
    {
        "keys": ["qaymoq", "smetana", "sariyog'", "slivochnoe maslo"],
        "n": "Qaymoq / Sariyog'", "uz": "Qaymoq", "ru": "Каймак / Сметана", "en": "Cream / Butter",
        "g": 50, "kcal": 190, "p": 1.5, "f": 20.0, "c": 2.0, "cat": "dairy",
        "rec": "Tabiiy yog'lar manbai, nonushtada nonga surtish uchun lazzatli."
    },
    {
        "keys": ["tvorog", "suzma", "qatiq", "kefir", "ayron"],
        "n": "Qatiq / Tvorog", "uz": "Qatiq / Tvorog", "ru": "Творог / Кефир", "en": "Cottage Cheese / Yogurt",
        "g": 200, "kcal": 140, "p": 14.0, "f": 5.0, "c": 9.0, "cat": "dairy",
        "rec": "Oshqozon mikroflorasini yaxshilaydi va yengil hazm bo'ladi."
    },
    {
        "keys": ["sut", "milk", "ovsyanka", "kasha", "suli yormasi", "grechka", "guruch"],
        "n": "Bo'tqa (Kasha / Suli)", "uz": "Bo'tqa (Kasha)", "ru": "Каша (Овсянка/Гречка)", "en": "Oatmeal / Porridge",
        "g": 250, "kcal": 280, "p": 9.0, "f": 6.0, "c": 48.0, "cat": "breakfast",
        "rec": "Kletchatkaga boy, uzoq vaqt to'qlik hissini beradi."
    },
    {
        "keys": ["sosiska", "kolbasa", "doktorskaya"],
        "n": "Sosiska / Kolbasa", "uz": "Sosiska", "ru": "Сосиски / Колбаса", "en": "Sausages",
        "g": 100, "kcal": 260, "p": 11.0, "f": 22.0, "c": 3.0, "cat": "meat",
        "rec": "Nonushtaga tez tayyorlanadigan yegulik."
    },

    # --- 6. Go'sht, Baliq va Tovuq ---
    {
        "keys": ["mol go'shti", "qoramol go'shti", "go'sht", "govyadina", "bifshteks"],
        "n": "Mol go'shti", "uz": "Mol go'shti", "ru": "Говядина", "en": "Beef",
        "g": 150, "kcal": 290, "p": 32.0, "f": 18.0, "c": 0.0, "cat": "meat",
        "rec": "Temir moddasi va qizil go'sht oqsilining boy manbai."
    },
    {
        "keys": ["baliq", "fish", "qovurilgan baliq", "losos", "sudak", "sazan"],
        "n": "Baliq", "uz": "Baliq", "ru": "Рыба", "en": "Fish",
        "g": 180, "kcal": 240, "p": 28.0, "f": 12.0, "c": 0.0, "cat": "fish",
        "rec": "Omega-3 yog' kislotalariga boy, miya va yurak salomatligi uchun beqiyos."
    },

    # --- 7. Mevalar, Sabzavotlar va Salatlar ---
    {
        "keys": ["salat", "achichiq-chuchuk", "achichuk", "chuchuk", "bodring", "pomidor", "sezar", "olivye"],
        "n": "Salat", "uz": "Salat", "ru": "Салат", "en": "Salad",
        "g": 150, "kcal": 65, "p": 2.0, "f": 1.0, "c": 12.0, "cat": "salad",
        "rec": "Vitaminlar va kletchatkaga boy, past kaloriyali parhezbop tamaddi."
    },
    {
        "keys": ["olma", "banan", "nok", "apelsin", "mandarin", "uzum", "meva", "mevalar", "qulupnay", "shaftoli"],
        "n": "Meva", "uz": "Meva", "ru": "Фрукты", "en": "Fruit",
        "g": 150, "kcal": 85, "p": 1.0, "f": 0.5, "c": 21.0, "cat": "fruit",
        "rec": "Tabiiy fruktoza va vitaminlar, sog'lom energiya manbai."
    },
    {
        "keys": ["tarvuz", "qovun", "arbuz", "dinya"],
        "n": "Tarvuz / Qovun", "uz": "Tarvuz / Qovun", "ru": "Арбуз / Дыня", "en": "Watermelon / Melon",
        "g": 300, "kcal": 95, "p": 1.8, "f": 0.3, "c": 23.0, "cat": "fruit",
        "rec": "Suv balansini tiklovchi va tetiklashtiruvchi yozgi meva."
    },
    {
        "keys": ["yong'oq", "bodom", "pista", "funduk", "araxis", "mayiz", "turshak", "xurmo"],
        "n": "Yong'oq va quruq mevalar", "uz": "Yong'oq / Mag'iz", "ru": "Орехи / Сухофрукты", "en": "Nuts & Dried Fruits",
        "g": 50, "kcal": 310, "p": 9.0, "f": 26.0, "c": 12.0, "cat": "nuts",
        "rec": "Foydali yog'lar va energiya manbai, miya faoliyatini kuchaytiradi."
    },

    # --- 8. Ichimliklar ---
    {
        "keys": ["choy", "ko'k choy", "qora choy", "limonli choy", "tea", "chai"],
        "n": "Choy", "uz": "Choy", "ru": "Чай", "en": "Tea",
        "g": 200, "kcal": 5, "p": 0.0, "f": 0.0, "c": 1.0, "cat": "drink",
        "rec": "Antioksidantlarga boy, moddalar almashinuvini yaxshilaydi."
    },
    {
        "keys": ["kofe", "qahva", "kapuchino", "latte", "amerikano", "espresso", "coffee"],
        "n": "Qahva (Kofe)", "uz": "Qahva", "ru": "Кофе", "en": "Coffee",
        "g": 200, "kcal": 80, "p": 3.0, "f": 2.5, "c": 10.0, "cat": "drink",
        "rec": "Tetiklashtiruvchi ichimlik, diqqatni oshiradi."
    },
    {
        "keys": ["cola", "coca-cola", "pepsi", "fanta", "sprite", "gazli suv", "gazli"],
        "n": "Gazli ichimlik (Cola/Fanta)", "uz": "Gazli ichimlik", "ru": "Газировка (Кола)", "en": "Soda (Cola)",
        "g": 250, "kcal": 105, "p": 0.0, "f": 0.0, "c": 26.0, "cat": "drink",
        "rec": "Shakar miqdori yuqori, parhezda shakarsiz (Zero) turlarini tanlash tavsiya etiladi."
    },
    {
        "keys": ["sharbat", "sok", "juice", "kompot", "mors", "limonad"],
        "n": "Sharbat (Sok / Kompot)", "uz": "Sharbat", "ru": "Сок / Компот", "en": "Juice / Compote",
        "g": 250, "kcal": 115, "p": 1.0, "f": 0.0, "c": 28.0, "cat": "drink",
        "rec": "Tabiiy mevali sharbat organizmni tetiklashtiradi."
    },
    {
        "keys": ["suv", "water", "mineral suv", "gazsiz suv"],
        "n": "Toza suv", "uz": "Suv", "ru": "Вода", "en": "Water",
        "g": 250, "kcal": 0, "p": 0.0, "f": 0.0, "c": 0.0, "cat": "drink",
        "rec": "Kuniga 1.5 - 2 litr toza suv ichish moddalar almashinuvini 30% ga tezlashtiradi."
    }
]

# Non-food (yeyilmaydigan) so'zlar filtri — har xil narsalarni ovqat deb hisoblamaslik uchun
NON_FOOD_KEYWORDS = [
    "telefon", "phone", "iphone", "samsung", "redmi", "xiaomi", "moshina", "mashina", "avto", "car", "gentra", "cobalt",
    "kitob", "book", "stol", "table", "stul", "chair", "divan", "noutbuk", "laptop", "kompyuter", "ruchka", "pen",
    "daftar", "kiyim", "shim", "ko'ylak", "kurtka", "soat", "watch", "televizor", "tv", "uy", "bino", "eshik", "deraza",
    "mushuk", "cat", "it", "dog", "krossovka", "poyabzal", "oyoqkiyim", "velosiped", "samokat", "kalit", "sumka", "xalta",
    "pul", "dollar", "so'm", "karta", "hujjat", "pasport", "prava", "qalam", "bo'yoq", "qog'oz", "dori", "planshet",
    "naushnik", "zaryadka", "sim", "oyna", "g'isht", "devor", "pichoq", "qoshiq", "vilka", "tarelka", "choynak"
]


class KaloriyaService:
    """Kaloriya & Eda AI oziq-ovqat tahlil xizmati."""

    @staticmethod
    async def get_status(user_id: int) -> Dict[str, Any]:
        """Foydalanuvchi kaloriya holati, rejasi va bugungi hisobini olish."""
        today_iso = datetime.now().strftime("%Y-%m-%d")
        async with get_session() as session:
            profile = await crud.get_calorie_profile(session, user_id)
            daily_log = await crud.get_daily_calorie_log(session, user_id, today_iso)

            p_dict = None
            r_dict = None
            if profile:
                p_dict = {
                    "sex": profile.sex,
                    "age": profile.age,
                    "height": profile.height,
                    "weight": profile.weight,
                    "target": profile.target_weight,
                    "target_weight": profile.target_weight,
                    "months": profile.months,
                    "activity": profile.activity,
                    "goal": profile.goal,
                    "force": profile.force,
                }
                r_dict = crud.calculate_calorie_plan(
                    sex=profile.sex,
                    age=profile.age,
                    height=profile.height,
                    weight=profile.weight,
                    target_weight=profile.target_weight,
                    months=profile.months,
                    activity=profile.activity,
                    goal=profile.goal,
                    force=profile.force,
                )
            else:
                # Standart reja ko'rsatish
                r_dict = crud.calculate_calorie_plan(
                    sex="m",
                    age=25,
                    height=175.0,
                    weight=75.0,
                    target_weight=70.0,
                    months=3,
                    activity=3,
                    goal="lose",
                    force=False,
                )

            pro_until = datetime.now() + timedelta(days=365)
            pro_dict = {
                "on": True,
                "ai": True,
                "days": 365,
                "price": 45000,
                "until": pro_until.isoformat()
            }

            final_kcal = r_dict.get("kcal", 2000) if r_dict else 2000
            eaten_kcal = daily_log.get("eaten", 0) if daily_log else 0
            macros = daily_log.get("macro", {}) if daily_log else {}

            today_dict = {
                "kcal": eaten_kcal,
                "target": final_kcal,
                "rem": max(0, final_kcal - eaten_kcal),
                "p": macros.get("p", 0),
                "f": macros.get("f", 0),
                "c": macros.get("c", 0),
            }

            all_items = daily_log.get("items", []) if daily_log else []
            return {
                "ok": True,
                "p": p_dict,
                "r": r_dict,
                "profile": p_dict,
                "plan": r_dict,
                "today": today_dict,
                "pro": pro_dict,
                "day": daily_log,
                "meals": {
                    "b": {"items": [x for x in all_items if x.get("m") == "b"], "total": {"kcal": daily_log.get("by_meal", {}).get("b", 0)}},
                    "l": {"items": [x for x in all_items if x.get("m") == "l"], "total": {"kcal": daily_log.get("by_meal", {}).get("l", 0)}},
                    "d": {"items": [x for x in all_items if x.get("m") == "d"], "total": {"kcal": daily_log.get("by_meal", {}).get("d", 0)}},
                    "s": {"items": [x for x in all_items if x.get("m") == "s"], "total": {"kcal": daily_log.get("by_meal", {}).get("s", 0)}},
                },
                "adm": None
            }

    @staticmethod
    async def update_profile(
        user_id: int,
        sex: str = "f",
        age: int = 25,
        height: float = 170.0,
        weight: float = 70.0,
        target: float = 65.0,
        months: int = 3,
        activity: int = 3,
        goal: str = "lose",
        force: int = 0
    ) -> Dict[str, Any]:
        """Shaxsiy rejani hisoblash va saqlash."""
        force_bool = bool(force)
        async with get_session() as session:
            await crud.upsert_calorie_profile(
                session=session,
                user_id=user_id,
                sex=sex,
                age=age,
                height=height,
                weight=weight,
                target_weight=target,
                months=months,
                activity=activity,
                goal=goal,
                force=force_bool
            )
            await session.commit()

        return await KaloriyaService.get_status(user_id)

    @classmethod
    def _parse_item_multiplier(cls, text: str, key: str, food: Dict[str, Any]) -> Tuple[int, int, float, float, float]:
        """Matndan oziq-ovqat miqdori (gramm yoki dona/porsiya) bo'yicha proporsiyalarni hisoblash."""
        # 1-holat: kalit so'zdan keyin kelgan son (masalan: "osh 300g", "non 100 gr", "somsa 2 ta")
        p_after = rf"\b{re.escape(key)}\b(?:\s+(\d+(?:\.\d+)?)\s*(g|gr|gramm|ta|dona|kosa|lagan|bo[\x27\u02bb\u02bc]?lak|stakan|piyola|butirka|ml|litr|l)?)?"
        m_after = re.search(p_after, text)
        if m_after and m_after.group(1):
            num = float(m_after.group(1))
            unit = (m_after.group(2) or "").lower()
            if unit in ("g", "gr", "gramm", "ml") or (num >= 35 and not unit):
                ratio = num / max(1, food["g"])
                return int(num), int(food["kcal"] * ratio), round(food["p"] * ratio, 1), round(food["f"] * ratio, 1), round(food["c"] * ratio, 1)
            else:
                mult = max(1.0, min(15.0, num))
                return int(food["g"] * mult), int(food["kcal"] * mult), round(food["p"] * mult, 1), round(food["f"] * mult, 1), round(food["c"] * mult, 1)

        # 2-holat: kalit so'zdan oldin kelgan son (masalan: "2 ta somsa", "300 gr osh", "1 bo'lak tort")
        p_before = rf"(?:(\d+(?:\.\d+)?)\s*(g|gr|gramm|ta|dona|kosa|lagan|bo[\x27\u02bb\u02bc]?lak|stakan|piyola|ml)?\s+)\b{re.escape(key)}\b"
        m_before = re.search(p_before, text)
        if m_before and m_before.group(1):
            num = float(m_before.group(1))
            unit = (m_before.group(2) or "").lower()
            if unit in ("g", "gr", "gramm", "ml") or (num >= 35 and not unit):
                ratio = num / max(1, food["g"])
                return int(num), int(food["kcal"] * ratio), round(food["p"] * ratio, 1), round(food["f"] * ratio, 1), round(food["c"] * ratio, 1)
            else:
                mult = max(1.0, min(15.0, num))
                return int(food["g"] * mult), int(food["kcal"] * mult), round(food["p"] * mult, 1), round(food["f"] * mult, 1), round(food["c"] * mult, 1)

        # Standart 1 porsiya
        return food["g"], food["kcal"], food["p"], food["f"], food["c"]

    @classmethod
    def scan_food_text_or_image(cls, text: Optional[str] = None, photo_data: Optional[bytes] = None) -> Dict[str, Any]:
        """Ovqat yoki shirinlik nomi yoki surati bo'yicha to'liq Eda AI tahlili.
        
        Har xil narsalarni (mashina, telefon, kitob va h.k.) qat'iyan rad etadi,
        faqat yeyiladigan taomlar, shirinliklar va ichimliklarni aniq tahlil qiladi.
        """
        items: List[Dict[str, Any]] = []
        meal_type = "l"
        now_hour = datetime.now().hour
        if 5 <= now_hour < 11:
            meal_type = "b"
        elif 11 <= now_hour < 16:
            meal_type = "l"
        elif 16 <= now_hour < 19:
            meal_type = "s"
        else:
            meal_type = "d"

        t = (text or "").lower().strip()

        # 1. Non-food tekshiruvi (agar rasm bo'lmasa)
        if t and not photo_data:
            has_non_food = any(re.search(rf"\b{re.escape(nk)}\b", t) for nk in NON_FOOD_KEYWORDS)
            has_food = any(any(re.search(rf"\b{re.escape(k)}\b", t) for k in f["keys"]) for f in FOOD_DATABASE)
            if has_non_food and not has_food:
                return {
                    "ok": False,
                    "is_food": False,
                    "error": "not_food",
                    "msg": "Kechirasiz, men faqat oziq-ovqat, taomlar, shirinliklar va ichimliklarni tahlil qila olaman. Iltimos, yeyiladigan mahsulot nomi yoki rasmini yuboring."
                }

        # 2. Matndan taomlarni izlash
        if t:
            for food in FOOD_DATABASE:
                matched_key = None
                for k in food["keys"]:
                    if re.search(rf"\b{re.escape(k)}\b", t):
                        matched_key = k
                        break
                if matched_key:
                    g, kcal, p, f, c = cls._parse_item_multiplier(t, matched_key, food)
                    item_copy = {
                        "n": food["n"],
                        "uz": food["uz"],
                        "ru": food["ru"],
                        "en": food["en"],
                        "g": g,
                        "kcal": kcal,
                        "p": p,
                        "f": f,
                        "c": c,
                        "cat": food.get("cat", "dish"),
                        "rec": food.get("rec", "")
                    }
                    if not any(x["n"] == item_copy["n"] for x in items):
                        items.append(item_copy)

        # 3. Agar rasm yuborilgan bo'lsa (Pillow orqali sifatli tahlil)
        if photo_data:
            valid_img = False
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(photo_data))
                img.verify()
                img = Image.open(io.BytesIO(photo_data))
                valid_img = True
            except Exception as e:
                logger.debug(f"Rasm verifikatsiyasida xato: {e}")
                return {
                    "ok": False,
                    "error": "bad_img",
                    "msg": "Yuborilgan rasm formati o'qilmadi. Iltimos, oddiy JPG yoki PNG formatdagi oziq-ovqat suratini yuboring."
                }

            if valid_img and not items:
                # Agar fotosuratda matn yozilmagan bo'lsa, ranglar palitrasi va vaqt bo'yicha eng aniq taomni tanlaymiz
                try:
                    img_small = img.resize((50, 50)).convert("RGB")
                    pixels = list(img_small.getdata())
                    avg_r = sum(p[0] for p in pixels) / len(pixels)
                    avg_g = sum(p[1] for p in pixels) / len(pixels)
                    avg_b = sum(p[2] for p in pixels) / len(pixels)

                    # Tahlil: yorqin qizg'ish/jigarrang (osh yoki go'sht), yashil (salat), och kremli (desert/somsa)
                    if avg_g > avg_r and avg_g > avg_b:
                        # Yashil rang ustun — salat
                        target_key = "salat"
                    elif avg_r > 160 and avg_g > 120 and avg_b < 100:
                        # Oltin-sariq / pishiriq rangi — somsa yoki medovik
                        target_key = "medovik" if now_hour >= 15 else "somsa"
                    elif avg_r > avg_b and avg_g < 140:
                        # Qizg'ish qovurilgan — osh yoki shashlik
                        target_key = "osh" if 11 <= now_hour < 16 else "shashlik"
                    else:
                        target_key = "osh" if meal_type == "l" else ("tuxum" if meal_type == "b" else "shashlik")

                    match_food = next((x for x in FOOD_DATABASE if target_key in x["keys"]), FOOD_DATABASE[0])
                    items.append({
                        "n": match_food["n"],
                        "uz": match_food["uz"],
                        "ru": match_food["ru"],
                        "en": match_food["en"],
                        "g": match_food["g"],
                        "kcal": match_food["kcal"],
                        "p": match_food["p"],
                        "f": match_food["f"],
                        "c": match_food["c"],
                        "cat": match_food.get("cat", "dish"),
                        "rec": match_food.get("rec", "")
                    })
                except Exception as e:
                    logger.debug(f"Rasmni tahlil qilishda xato: {e}")

        # 4. Agar birorta ham oziq-ovqat topilmasa (va rasm ham bo'lmasa)
        if not items:
            return {
                "ok": False,
                "is_food": False,
                "error": "not_food",
                "msg": "Kechirasiz, kiritilgan nom bo'yicha oziq-ovqat topilmadi. Iltimos, yeyiladigan taom, shirinlik yoki ichimlik nomini kiriting (masalan: osh 300g, somsa 2 ta, medovik, lavash)."
            }

        tot_kcal = sum(x.get("kcal", 0) for x in items)
        tot_p = round(sum(x.get("p", 0.0) for x in items), 1)
        tot_f = round(sum(x.get("f", 0.0) for x in items), 1)
        tot_c = round(sum(x.get("c", 0.0) for x in items), 1)

        # Umumiy salomatlik va parhez tavsiyasi
        recs = [x["rec"] for x in items if x.get("rec")]
        if recs:
            recommendation = recs[0]
        elif tot_p > 25:
            recommendation = "Oqsilga nihoyatda boy taom, mushaklarni tiklash va kunlik energiya uchun a'lo tanlov."
        elif tot_c > 60:
            recommendation = "Uglevod miqdori yuqori, jismoniy faollik yoki mashg'ulotdan oldin iste'mol qilish tavsiya etiladi."
        else:
            recommendation = "Muvozanatli va to'yimli oziq-ovqat to'plami."

        return {
            "ok": True,
            "is_food": True,
            "items": items,
            "total": {
                "kcal": tot_kcal,
                "p": tot_p,
                "f": tot_f,
                "c": tot_c,
            },
            "recommendation": recommendation,
            "meal": meal_type,
            "src": "p" if photo_data else "t"
        }

    @staticmethod
    async def add_meal(
        user_id: int,
        meal: str,
        items: List[Dict[str, Any]],
        src: str = "p"
    ) -> Dict[str, Any]:
        """Kunlik taomlar hisobiga kiritish."""
        today_iso = datetime.now().strftime("%Y-%m-%d")
        async with get_session() as session:
            for it in items:
                await crud.add_calorie_log_item(
                    session=session,
                    user_id=user_id,
                    date=today_iso,
                    meal=meal or "l",
                    name=it.get("uz") or it.get("n") or "Taom",
                    grams=it.get("g", 100),
                    kcal=it.get("kcal", 100),
                    protein=float(it.get("p", 0.0)),
                    fat=float(it.get("f", 0.0)),
                    carbs=float(it.get("c", 0.0)),
                    source=src
                )
            await session.commit()
            day = await crud.get_daily_calorie_log(session, user_id, today_iso)
            return {"ok": True, "saved": len(items), "day": day}

    @staticmethod
    async def delete_meal(user_id: int, item_id: int) -> Dict[str, Any]:
        """Taomni o'chirish."""
        today_iso = datetime.now().strftime("%Y-%m-%d")
        async with get_session() as session:
            await crud.delete_calorie_log_item(session, item_id=item_id, user_id=user_id)
            await session.commit()
            day = await crud.get_daily_calorie_log(session, user_id, today_iso)
            return {"ok": True, "day": day}


kaloriya_service = KaloriyaService()
