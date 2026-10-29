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
        "keys": ["osh", "palov", "plov", "choyxona oshi", "to'y oshi", "devzira", "toy oshi", "плов", "плова", "пловом", "ош", "палов", "pilaf", "palaw"],
        "n": "Osh (Palov)", "uz": "Osh (Palov)", "ru": "Плов", "en": "Pilaf",
        "g": 350, "kcal": 680, "p": 24.0, "f": 32.0, "c": 74.0, "cat": "dish",
        "rec": "To'yimli va energetik taom. Kunlik faol harakat yoki sport bilan uyg'unlashtirish tavsiya etiladi."
    },
    {
        "keys": ["somsa", "katlama somsa", "tandir somsa", "varaqi somsa", "goshtli somsa", "qovoqli somsa", "самса", "самсы", "самсу", "samsa", "samosa"],
        "n": "Somsa", "uz": "Somsa", "ru": "Самса", "en": "Samsa",
        "g": 180, "kcal": 410, "p": 14.0, "f": 21.0, "c": 42.0, "cat": "pastry",
        "rec": "Yog'li va to'yimli pishiriq. Nonushta yoki tushlikda me'yorida iste'mol qilish ma'qul."
    },
    {
        "keys": ["shashlik", "kabob", "qiyma shashlik", "jigar shashlik", "kavkazcha", "shashliklar", "шашлык", "шашлыка", "шашлыки", "кебаб", "люля-кебаб", "kebab", "shish kebab"],
        "n": "Shashlik", "uz": "Shashlik", "ru": "Шашлык", "en": "Kebab",
        "g": 150, "kcal": 340, "p": 28.0, "f": 24.0, "c": 2.0, "cat": "meat",
        "rec": "Yuqori oqsilga boy, mushaklarni mustahkamlash uchun ajoyib taom. Ko'katlar bilan yeyish tavsiya etiladi."
    },
    {
        "keys": ["lag'mon", "lagman", "cho'zma lag'mon", "chozma lagman", "uyg'ur lag'mon", "qovurma lag'mon", "лагман", "лагмана", "лагмон", "lagman"],
        "n": "Lag'mon", "uz": "Lag'mon", "ru": "Лагман", "en": "Lagman",
        "g": 400, "kcal": 560, "p": 22.0, "f": 18.0, "c": 75.0, "cat": "dish",
        "rec": "Uglevod va sabzavotlarga boy to'liq tushlik taomi."
    },
    {
        "keys": ["manti", "qovoqli manti", "mantiya", "манты", "мантов", "манти", "manty", "manti"],
        "n": "Manti", "uz": "Manti", "ru": "Манты", "en": "Manty",
        "g": 250, "kcal": 480, "p": 19.0, "f": 22.0, "c": 51.0, "cat": "dish",
        "rec": "Bug'da pishirilgan to'yimli milliy taom."
    },
    {
        "keys": ["chuchvara", "pelmeni", "qovurma chuchvara", "чучвара", "пельмени", "пельменей", "dumplings", "pelmeni"],
        "n": "Chuchvara", "uz": "Chuchvara", "ru": "Пельмени (Чучвара)", "en": "Dumplings",
        "g": 250, "kcal": 450, "p": 20.0, "f": 18.0, "c": 52.0, "cat": "dish",
        "rec": "Sho'rvasi yoki qatiq bilan birga yaxshi hazm bo'ladi."
    },
    {
        "keys": ["shorva", "sho'rva", "qaynatma sho'rva", "shurpa", "no'xat sho'rva", "шурпа", "шурпы", "суп", "супа", "борщ", "солянка", "meat soup", "soup"],
        "n": "Sho'rva", "uz": "Sho'rva", "ru": "Шурпа", "en": "Meat Soup",
        "g": 350, "kcal": 320, "p": 20.0, "f": 16.0, "c": 24.0, "cat": "soup",
        "rec": "Sho'rva oson hazm bo'ladi va tanani foydali minerallar bilan ta'minlaydi."
    },
    {
        "keys": ["mastava", "goja", "ugra", "chuchvara shorva", "мастава", "угра", "mastava"],
        "n": "Mastava", "uz": "Mastava", "ru": "Мастава", "en": "Mastava",
        "g": 350, "kcal": 310, "p": 16.0, "f": 14.0, "c": 30.0, "cat": "soup",
        "rec": "Guruchli va sabzavotli yengil sho'rva taom."
    },
    {
        "keys": ["qozon kabob", "kazan kebab", "dimlama", "jiz", "jiz-biz", "казан-кебаб", "казан кебаб", "димлама", "джиз", "kazan kebab", "dimlama"],
        "n": "Qozon kabob", "uz": "Qozon kabob", "ru": "Казан-кебаб", "en": "Kazan Kebab",
        "g": 300, "kcal": 620, "p": 32.0, "f": 40.0, "c": 30.0, "cat": "meat",
        "rec": "Go'sht va kartoshkadan iborat to'yimli va kaloriyali taom."
    },
    {
        "keys": ["norin", "narin", "qazi", "kazi", "нарын", "казы", "казылык", "narin with kazi", "narin"],
        "n": "Norin va Qazi", "uz": "Norin va Qazi", "ru": "Нарын с казы", "en": "Narin with Kazi",
        "g": 250, "kcal": 490, "p": 26.0, "f": 20.0, "c": 52.0, "cat": "dish",
        "rec": "Ot go'shti va yupqa xamirdan tayyorlangan oqsilga boy milliy lazzat."
    },
    {
        "keys": ["xonim", "hanum", "ханум", "хоним", "khanum"],
        "n": "Xonim", "uz": "Xonim", "ru": "Ханум", "en": "Khanum",
        "g": 250, "kcal": 390, "p": 12.0, "f": 14.0, "c": 54.0, "cat": "dish",
        "rec": "Bug'da pishirilgan kartoshkali yoki go'shtli xamir taom."
    },
    {
        "keys": ["kotlet", "teftel", "kotletlar", "котлета", "котлеты", "тефтели", "бифштекс", "cutlet", "meatballs"],
        "n": "Kotlet / Teftel", "uz": "Kotlet", "ru": "Котлета / Тефтели", "en": "Cutlet",
        "g": 180, "kcal": 360, "p": 24.0, "f": 22.0, "c": 14.0, "cat": "meat",
        "rec": "Go'shtli to'yimli taom, sabzavotli garnir bilan tavsiya etiladi."
    },
    {
        "keys": ["pirojki", "cheburek", "pirojok", "пирожки", "пирожок", "чебурек", "чебуреки", "belash", "беляш"],
        "n": "Pirojki / Cheburek", "uz": "Pirojki", "ru": "Пирожки / Чебурек", "en": "Pirozhki / Cheburek",
        "g": 150, "kcal": 380, "p": 12.0, "f": 18.0, "c": 42.0, "cat": "pastry",
        "rec": "Issiq qovurilgan pishiriq, me'yorni saqlang."
    },

    # --- 2. Non va non mahsulotlari ---
    {
        "keys": ["non", "patir", "lepyoshka", "tandir non", "obi non", "buxanka", "хлеб", "хлеба", "лепешка", "лепешки", "батон", "булочка", "bread", "flatbread"],
        "n": "Non", "uz": "Non", "ru": "Хлеб", "en": "Bread",
        "g": 100, "kcal": 260, "p": 8.0, "f": 3.0, "c": 52.0, "cat": "bread",
        "rec": "Murakkab uglevodlarga boy, kunlik ratsionning ajralmas qismi."
    },

    # --- 3. Shirinliklar, Tortlar va Desertlar (User Critical Requirement) ---
    {
        "keys": ["medovik", "asalli tort", "medoviy", "медовик", "медовика", "медовый торт", "honey cake"],
        "n": "Medovik (Asalli tort)", "uz": "Medovik (Asalli tort)", "ru": "Медовик", "en": "Honey Cake (Medovik)",
        "g": 120, "kcal": 440, "p": 6.0, "f": 18.0, "c": 64.0, "cat": "sweet",
        "rec": "Asalli shirinlik tezkor energiya beradi, kunning birinchi yarmida choy bilan iste'mol qilish ma'qul."
    },
    {
        "keys": ["napoleon", "napaleon", "qavatli tort", "наполеон", "наполеона", "торт наполеон", "napoleon cake"],
        "n": "Napoleon torti", "uz": "Napoleon torti", "ru": "Торт Наполеон", "en": "Napoleon Cake",
        "g": 130, "kcal": 470, "p": 6.5, "f": 26.0, "c": 54.0, "cat": "sweet",
        "rec": "Krem va qavatli xamirdan tayyorlangan, kaloriyasi baland shirinlik."
    },
    {
        "keys": ["chizkeyk", "cheesecake", "чизкейк", "чизкейка", "cheesecake"],
        "n": "Chizkeyk", "uz": "Chizkeyk", "ru": "Чизкейк", "en": "Cheesecake",
        "g": 120, "kcal": 380, "p": 7.0, "f": 22.0, "c": 38.0, "cat": "sweet",
        "rec": "Tvorogli pishloqdan tayyorlangan oqsilga boy shirinlik."
    },
    {
        "keys": ["tort", "qizil baxmal", "red velvet", "shokoladli tort", "praga", "biskvit", "торт", "торта", "торты", "бисквит", "красный бархат", "прага", "cake"],
        "n": "Tort", "uz": "Tort", "ru": "Торт", "en": "Cake",
        "g": 130, "kcal": 420, "p": 5.0, "f": 20.0, "c": 56.0, "cat": "sweet",
        "rec": "Shirinlik uglevodlarga boy, me'yorni saqlash parhez uchun muhim."
    },
    {
        "keys": ["paxlava", "baklava", "пахлава", "пахлавы", "баклава", "baklava"],
        "n": "Paxlava", "uz": "Paxlava", "ru": "Пахлава", "en": "Baklava",
        "g": 100, "kcal": 430, "p": 7.0, "f": 24.0, "c": 48.0, "cat": "sweet",
        "rec": "Yong'oqli va sharbatli sharqona shirinlik."
    },
    {
        "keys": ["xolva", "halva", "халва", "халвы", "halva"],
        "n": "Xolva", "uz": "Xolva", "ru": "Халва", "en": "Halva",
        "g": 80, "kcal": 410, "p": 9.0, "f": 24.0, "c": 40.0, "cat": "sweet",
        "rec": "Kalsiy va magniyga boy, kuch bag'ishlaydigan shirinlik."
    },
    {
        "keys": ["chak-chak", "chakchak", "чак-чак", "чак чак", "chak-chak"],
        "n": "Chak-chak", "uz": "Chak-chak", "ru": "Чак-чак", "en": "Chak-chak",
        "g": 100, "kcal": 420, "p": 6.0, "f": 18.0, "c": 58.0, "cat": "sweet",
        "rec": "Asalli an'anaviy pishiriq."
    },
    {
        "keys": ["shokolad", "chocolate", "snickers", "snikers", "kitkat", "twix", "bounty", "mars", "шоколад", "шоколада", "сникерс", "киткат", "твикс", "баунти", "марс", "конфеты"],
        "n": "Shokolad", "uz": "Shokolad", "ru": "Шоколад", "en": "Chocolate",
        "g": 50, "kcal": 265, "p": 3.5, "f": 15.0, "c": 28.0, "cat": "sweet",
        "rec": "Miyaning ishlashini yaxshilaydi va kayfiyatni ko'taradi."
    },
    {
        "keys": ["muzqaymoq", "morojenoe", "morojnoe", "plombir", "eskimo", "ice cream", "мороженое", "мороженого", "пломбир", "эскимо"],
        "n": "Muzqaymoq", "uz": "Muzqaymoq", "ru": "Мороженое", "en": "Ice Cream",
        "g": 100, "kcal": 220, "p": 3.5, "f": 12.0, "c": 24.0, "cat": "sweet",
        "rec": "Issiq kunda yoqimli, sutli lazzat."
    },
    {
        "keys": ["kruassan", "croissant", "bulochka", "keks", "muffin", "pechenye", "vafli", "круассан", "круассана", "булочка", "кекс", "маффин", "печенье", "вафли", "croissant", "cookie"],
        "n": "Kruassan / Bulochka", "uz": "Kruassan / Bulochka", "ru": "Круассан / Выпечка", "en": "Croissant / Pastry",
        "g": 90, "kcal": 360, "p": 6.0, "f": 18.0, "c": 44.0, "cat": "sweet",
        "rec": "Ertalabki qahva yoki choy bilan ajoyib nonushta."
    },
    {
        "keys": ["ponchik", "donut", "donuts", "ekler", "пончик", "пончики", "эклер", "эклеры"],
        "n": "Ponchik / Ekler", "uz": "Ponchik / Ekler", "ru": "Пончик / Эклер", "en": "Donut / Eclair",
        "g": 90, "kcal": 340, "p": 4.5, "f": 17.0, "c": 42.0, "cat": "sweet",
        "rec": "Yengil shirin tamaddi."
    },
    {
        "keys": ["blinchik", "blin", "quymoq", "блины", "блинчики", "блин", "блинчик", "pancakes", "crepes"],
        "n": "Blinchik / Quymoq", "uz": "Blinchik / Quymoq", "ru": "Блины / Блинчики", "en": "Pancakes / Crepes",
        "g": 120, "kcal": 250, "p": 7.0, "f": 9.0, "c": 35.0, "cat": "sweet",
        "rec": "Nonushtaga asal yoki murabbo bilan juda lazzatli."
    },
    {
        "keys": ["sirnik", "sirniki", "tvorojnik", "сырники", "сырник", "сырников", "творожники", "cottage cheese pancakes"],
        "n": "Sirniki", "uz": "Sirniki", "ru": "Сырники", "en": "Cottage Cheese Pancakes",
        "g": 150, "kcal": 310, "p": 18.0, "f": 12.0, "c": 32.0, "cat": "breakfast",
        "rec": "Tvorogli oqsilga boy foydali nonushta."
    },
    {
        "keys": ["asal", "med", "honey", "murabbo", "varenye", "jem", "мёд", "мед", "меда", "варенье", "джем", "honey", "jam"],
        "n": "Asal / Murabbo", "uz": "Asal / Murabbo", "ru": "Мёд / Варенье", "en": "Honey / Jam",
        "g": 50, "kcal": 150, "p": 0.3, "f": 0.0, "c": 38.0, "cat": "sweet",
        "rec": "Tabiiy immunitetni ko'taruvchi va vitaminlarga boy shirinlik."
    },

    # --- 4. Fast Food va yeguliklar ---
    {
        "keys": ["lavash", "donar", "shaurma", "shawarma", "turkcha lavash", "mini lavash", "лаваш", "лаваша", "шаурма", "шаурмы", "донар", "shawarma", "wrap"],
        "n": "Lavash", "uz": "Lavash", "ru": "Лаваш", "en": "Shawarma (Lavash)",
        "g": 280, "kcal": 540, "p": 24.0, "f": 22.0, "c": 62.0, "cat": "fastfood",
        "rec": "Go'sht va sabzavotlar balansi, to'yimli va oqsilga boy."
    },
    {
        "keys": ["pizza", "pitsa", "peperoni", "margarita", "margaritta", "пицца", "пиццы", "пепперони", "маргарита", "pizza", "pepperoni"],
        "n": "Pitsa (2 bo'lak)", "uz": "Pitsa", "ru": "Пицца", "en": "Pizza",
        "g": 220, "kcal": 520, "p": 22.0, "f": 20.0, "c": 64.0, "cat": "fastfood",
        "rec": "Pishloq va souslar bilan boyitilgan mashhur taom."
    },
    {
        "keys": ["burger", "gamburger", "chizburger", "dabl burger", "big burger", "бургер", "бургера", "гамбургер", "чизбургер", "burger", "hamburger", "cheeseburger"],
        "n": "Burger", "uz": "Burger", "ru": "Бургер", "en": "Burger",
        "g": 220, "kcal": 510, "p": 25.0, "f": 24.0, "c": 48.0, "cat": "fastfood",
        "rec": "Kotlet, pishloq va sabzavotlar uyg'unligi."
    },
    {
        "keys": ["hot dog", "hotdog", "xotdog", "sendvich", "sandwich", "tost", "buterbrod", "хот-дог", "хотдог", "сэндвич", "бутерброд", "тост", "hot dog", "sandwich"],
        "n": "Hot-dog / Sendvich", "uz": "Hot-dog", "ru": "Хот-дог / Сэндвич", "en": "Hot Dog / Sandwich",
        "g": 180, "kcal": 420, "p": 16.0, "f": 20.0, "c": 44.0, "cat": "fastfood",
        "rec": "Tez va qulay tushlik tamaddisi."
    },
    {
        "keys": ["kartoshka fri", "fri", "french fries", "naggets", "nuggets", "картофель фри", "картошка фри", "фри", "наггетсы", "french fries", "nuggets"],
        "n": "Kartoshka fri", "uz": "Kartoshka fri", "ru": "Картофель фри", "en": "French Fries",
        "g": 150, "kcal": 460, "p": 5.0, "f": 22.0, "c": 60.0, "cat": "fastfood",
        "rec": "Qisirlovchi qovurilgan kartoshka, me'yorda iste'mol qilish tavsiya etiladi."
    },
    {
        "keys": ["kfc", "strips", "qanotcha", "tovuq go'shti", "tovuq filesi", "tovuq", "курица", "курицы", "куриное филе", "жареная курица", "крылышки", "стрипсы", "fried chicken", "chicken"],
        "n": "Qovurilgan tovuq", "uz": "Qovurilgan tovuq", "ru": "Курица", "en": "Chicken",
        "g": 200, "kcal": 440, "p": 34.0, "f": 22.0, "c": 18.0, "cat": "meat",
        "rec": "Tovuq go'shti oqsilga nihoyatda boy va mushaklar uchun juda foydali."
    },
    {
        "keys": ["chips", "chipsi", "lays", "pringles", "чипсы", "чипсов", "сухарики", "chips", "crisps"],
        "n": "Chips", "uz": "Chips", "ru": "Чипсы", "en": "Chips",
        "g": 70, "kcal": 370, "p": 4.5, "f": 24.0, "c": 36.0, "cat": "snack",
        "rec": "Tuzli va qisirlovchi yegulik, parhezda kamroq iste'mol qilish ma'qul."
    },

    # --- 5. Nonushta va sut mahsulotlari ---
    {
        "keys": ["tuxum", "omlet", "yaichnitsa", "glazunya", "qaynatilgan tuxum", "яйца", "яйцо", "яиц", "омлет", "яичница", "eggs", "egg", "omelet"],
        "n": "Tuxum (2 dona)", "uz": "Tuxum", "ru": "Яйца (Омлет)", "en": "Eggs",
        "g": 120, "kcal": 180, "p": 14.0, "f": 12.0, "c": 2.0, "cat": "breakfast",
        "rec": "Eng mukammal oqsil manbai, nonushta uchun 1-raqamli tanlov."
    },
    {
        "keys": ["pishloq", "sir", "cheese", "suluguni", "golland", "сыр", "сыра", "брынза", "сулугуни", "моцарелла", "cheese"],
        "n": "Pishloq (Sir)", "uz": "Pishloq", "ru": "Сыр", "en": "Cheese",
        "g": 50, "kcal": 180, "p": 12.0, "f": 14.0, "c": 1.0, "cat": "dairy",
        "rec": "Kalsiy va sog'lom yog'larga boy tabiiy mahsulot."
    },
    {
        "keys": ["qaymoq", "smetana", "sariyog'", "slivochnoe maslo", "каймак", "сметана", "сметаны", "сливочное масло", "масло", "cream", "sour cream", "butter"],
        "n": "Qaymoq / Sariyog'", "uz": "Qaymoq", "ru": "Каймак / Сметана", "en": "Cream / Butter",
        "g": 50, "kcal": 190, "p": 1.5, "f": 20.0, "c": 2.0, "cat": "dairy",
        "rec": "Tabiiy yog'lar manbai, nonushtada nonga surtish uchun lazzatli."
    },
    {
        "keys": ["tvorog", "suzma", "qatiq", "kefir", "ayron", "qurt", "kurt", "йогурт", "yogurt", "творог", "творога", "кефир", "кефира", "айран", "катык", "сузьма", "курт", "cottage cheese", "yogurt"],
        "n": "Qatiq / Tvorog", "uz": "Qatiq / Tvorog", "ru": "Творог / Кефир", "en": "Cottage Cheese / Yogurt",
        "g": 200, "kcal": 140, "p": 14.0, "f": 5.0, "c": 9.0, "cat": "dairy",
        "rec": "Oshqozon mikroflorasini yaxshilaydi va yengil hazm bo'ladi."
    },
    {
        "keys": ["sut", "milk", "ovsyanka", "kasha", "suli yormasi", "grechka", "guruch", "каша", "каши", "овсянка", "овсянки", "гречка", "молоко", "молока", "porridge", "oatmeal"],
        "n": "Bo'tqa (Kasha / Suli)", "uz": "Bo'tqa (Kasha)", "ru": "Каша (Овсянка/Гречка)", "en": "Oatmeal / Porridge",
        "g": 250, "kcal": 280, "p": 9.0, "f": 6.0, "c": 48.0, "cat": "breakfast",
        "rec": "Kletchatkaga boy, uzoq vaqt to'qlik hissini beradi."
    },
    {
        "keys": ["sosiska", "kolbasa", "doktorskaya", "сосиски", "сосисок", "сосиска", "колбаса", "колбасы", "ветчина", "sausages", "sausage"],
        "n": "Sosiska / Kolbasa", "uz": "Sosiska", "ru": "Сосиски / Колбаса", "en": "Sausages",
        "g": 100, "kcal": 260, "p": 11.0, "f": 22.0, "c": 3.0, "cat": "meat",
        "rec": "Nonushtaga tez tayyorlanadigan yegulik."
    },

    # --- 6. Go'sht, Baliq ---
    {
        "keys": ["mol go'shti", "qoramol go'shti", "go'sht", "govyadina", "bifshteks", "говядина", "говядины", "мясо", "мяса", "стейк", "beef", "meat", "steak"],
        "n": "Mol go'shti", "uz": "Mol go'shti", "ru": "Говядина", "en": "Beef",
        "g": 150, "kcal": 290, "p": 32.0, "f": 18.0, "c": 0.0, "cat": "meat",
        "rec": "Temir moddasi va qizil go'sht oqsilining boy manbai."
    },
    {
        "keys": ["baliq", "fish", "qovurilgan baliq", "losos", "sudak", "sazan", "рыба", "рыбы", "жареная рыба", "лосось", "судак", "сазан", "fish", "salmon"],
        "n": "Baliq", "uz": "Baliq", "ru": "Рыба", "en": "Fish",
        "g": 180, "kcal": 240, "p": 28.0, "f": 12.0, "c": 0.0, "cat": "fish",
        "rec": "Omega-3 yog' kislotalariga boy, miya va yurak salomatligi uchun beqiyos."
    },

    # --- 7. Mevalar, Sabzavotlar va Salatlar ---
    {
        "keys": ["salat", "achichiq-chuchuk", "achichuk", "chuchuk", "bodring", "pomidor", "sezar", "olivye", "салат", "салата", "ачик-чучук", "ачичук", "огурцы", "помидоры", "цезарь", "оливье", "salad"],
        "n": "Salat", "uz": "Salat", "ru": "Салат", "en": "Salad",
        "g": 150, "kcal": 65, "p": 2.0, "f": 1.0, "c": 12.0, "cat": "salad",
        "rec": "Vitaminlar va kletchatkaga boy, past kaloriyali parhezbop tamaddi."
    },
    {
        "keys": ["olma", "banan", "nok", "apelsin", "mandarin", "uzum", "meva", "mevalar", "qulupnay", "shaftoli", "яблоко", "яблоки", "банан", "бананы", "груша", "апельсин", "мандарин", "виноград", "фрукты", "клубника", "fruit", "fruits", "apple", "banana"],
        "n": "Meva", "uz": "Meva", "ru": "Фрукты", "en": "Fruit",
        "g": 150, "kcal": 85, "p": 1.0, "f": 0.5, "c": 21.0, "cat": "fruit",
        "rec": "Tabiiy fruktoza va vitaminlar, sog'lom energiya manbai."
    },
    {
        "keys": ["tarvuz", "qovun", "arbuz", "dinya", "арбуз", "арбуза", "дыня", "дыни", "watermelon", "melon"],
        "n": "Tarvuz / Qovun", "uz": "Tarvuz / Qovun", "ru": "Арбуз / Дыня", "en": "Watermelon / Melon",
        "g": 300, "kcal": 95, "p": 1.8, "f": 0.3, "c": 23.0, "cat": "fruit",
        "rec": "Suv balansini tiklovchi va tetiklashtiruvchi yozgi meva."
    },
    {
        "keys": ["yong'oq", "bodom", "pista", "funduk", "araxis", "mayiz", "turshak", "xurmo", "орехи", "орехов", "миндаль", "фисташки", "фундук", "арахис", "изюм", "сухофрукты", "nuts", "almonds"],
        "n": "Yong'oq va quruq mevalar", "uz": "Yong'oq / Mag'iz", "ru": "Орехи / Сухофрукты", "en": "Nuts & Dried Fruits",
        "g": 50, "kcal": 310, "p": 9.0, "f": 26.0, "c": 12.0, "cat": "nuts",
        "rec": "Foydali yog'lar va energiya manbai, miya faoliyatini kuchaytiradi."
    },

    # --- 8. Ichimliklar ---
    {
        "keys": ["choy", "ko'k choy", "qora choy", "limonli choy", "tea", "chai", "чай", "чая", "зеленый чай", "черный чай", "чай с лимоном", "green tea", "black tea"],
        "n": "Choy", "uz": "Choy", "ru": "Чай", "en": "Tea",
        "g": 200, "kcal": 5, "p": 0.0, "f": 0.0, "c": 1.0, "cat": "drink",
        "rec": "Antioksidantlarga boy, moddalar almashinuvini yaxshilaydi."
    },
    {
        "keys": ["kofe", "qahva", "kapuchino", "latte", "amerikano", "espresso", "coffee", "кофе", "капучино", "латте", "американо", "эспрессо"],
        "n": "Qahva (Kofe)", "uz": "Qahva", "ru": "Кофе", "en": "Coffee",
        "g": 200, "kcal": 80, "p": 3.0, "f": 2.5, "c": 10.0, "cat": "drink",
        "rec": "Tetiklashtiruvchi ichimlik, diqqatni oshiradi."
    },
    {
        "keys": ["cola", "coca-cola", "pepsi", "fanta", "sprite", "gazli suv", "gazli", "кола", "колы", "кока-кола", "пепси", "фанта", "спрайт", "газировка", "soda", "coke"],
        "n": "Gazli ichimlik (Cola/Fanta)", "uz": "Gazli ichimlik", "ru": "Газировка (Кола)", "en": "Soda (Cola)",
        "g": 250, "kcal": 105, "p": 0.0, "f": 0.0, "c": 26.0, "cat": "drink",
        "rec": "Shakar miqdori yuqori, parhezda shakarsiz (Zero) turlarini tanlash tavsiya etiladi."
    },
    {
        "keys": ["sharbat", "sok", "juice", "kompot", "mors", "limonad", "сок", "сока", "компот", "морс", "лимонад", "juice", "compote"],
        "n": "Sharbat (Sok / Kompot)", "uz": "Sharbat", "ru": "Сок / Компот", "en": "Juice / Compote",
        "g": 250, "kcal": 115, "p": 1.0, "f": 0.0, "c": 28.0, "cat": "drink",
        "rec": "Tabiiy mevali sharbat organizmni tetiklashtiradi."
    },
    {
        "keys": ["energetik", "red bull", "flash", "gorilla", "adrenaline", "monster", "энергетик", "энергетика", "ред булл", "горилла", "флеш", "адреналин", "energy drink"],
        "n": "Energetik ichimlik", "uz": "Energetik ichimlik", "ru": "Энергетик", "en": "Energy Drink",
        "g": 250, "kcal": 120, "p": 0.5, "f": 0.0, "c": 29.0, "cat": "drink",
        "rec": "Tarkibida kofein va taurin mavjud, me'yorni oshirmaslik tavsiya etiladi."
    },
    {
        "keys": ["suv", "water", "mineral suv", "gazsiz suv", "вода", "воды", "минеральная вода", "mineral water"],
        "n": "Toza suv", "uz": "Suv", "ru": "Вода", "en": "Water",
        "g": 250, "kcal": 0, "p": 0.0, "f": 0.0, "c": 0.0, "cat": "drink",
        "rec": "Kuniga 1.5 - 2 litr toza suv ichish moddalar almashinuvini 30% ga tezlashtiradi."
    }
]

# Non-food (yeyilmaydigan) so'zlar filtri — har xil narsalarni ovqat deb hisoblamaslik uchun
NON_FOOD_KEYWORDS = [
    # Uzbek
    "telefon", "phone", "iphone", "samsung", "redmi", "xiaomi", "moshina", "mashina", "avto", "car", "gentra", "cobalt",
    "kitob", "book", "stol", "table", "stul", "chair", "divan", "noutbuk", "laptop", "kompyuter", "ruchka", "pen",
    "daftar", "kiyim", "shim", "ko'ylak", "kurtka", "soat", "watch", "televizor", "tv", "uy", "bino", "eshik", "deraza",
    "mushuk", "cat", "it", "dog", "krossovka", "poyabzal", "oyoqkiyim", "velosiped", "samokat", "kalit", "sumka", "xalta",
    "pul", "dollar", "so'm", "karta", "hujjat", "pasport", "prava", "qalam", "bo'yoq", "qog'oz", "dori", "planshet",
    "naushnik", "zaryadka", "sim", "oyna", "g'isht", "devor", "pichoq", "qoshiq", "vilka", "tarelka", "choynak",
    # Russian
    "телефон", "машина", "авто", "книга", "стол", "стул", "диван", "ноутбук", "компьютер", "ручка", "тетрадь",
    "одежда", "брюки", "рубашка", "куртка", "часы", "телевизор", "дом", "здание", "дверь", "окно", "кошка", "собака",
    "кроссовки", "обувь", "велосипед", "самокат", "ключ", "сумка", "деньги", "доллар", "паспорт", "карандаш", "бумага",
    "лекарство", "планшет", "наушники", "зарядка", "провод", "зеркало", "кирпич", "стена", "нож", "ложка", "вилка", "тарелка", "чайник",
    # English
    "phone", "car", "book", "table", "chair", "sofa", "laptop", "computer", "pen", "notebook", "clothes", "shirt",
    "jacket", "watch", "tv", "house", "building", "door", "window", "cat", "dog", "shoes", "sneakers", "bicycle", "scooter",
    "key", "bag", "money", "dollar", "passport", "pencil", "paper", "medicine", "tablet", "headphones", "charger",
    "wire", "mirror", "brick", "wall", "knife", "spoon", "fork", "plate", "kettle"
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
        units_pattern = (
            r"(?:g|gr|gramm|г|гр|грамм|gram|grams|ml|litr|l|мл|л|литр|liter|liters|"
            r"ta|dona|шт|штук|штука|штуки|pcs|piece|pieces|kosa|lagan|stakan|piyola|butirka|"
            r"кружка|кружки|стакан|стакана|банка|бут|чашка|чашки|cup|cups|bowl|bowls|bottle|can|"
            r"bo[\x27\u02bb\u02bc]?lak|кусок|куска|порция|порции|порций|пачка|пачки|пачек|slice|slices|portion|portions|pack|packs)"
        )

        # 1-holat: kalit so'zdan keyin kelgan son (masalan: "osh 300g", "плов 300г", "somsa 2 ta", "pizza 2 slices")
        p_after = rf"\b{re.escape(key)}\b(?:\s+(?:из\s+)?(\d+(?:\.\d+)?)\s*({units_pattern})?)?"
        m_after = re.search(p_after, text, re.IGNORECASE)
        if m_after and m_after.group(1):
            num = float(m_after.group(1))
            unit = (m_after.group(2) or "").lower()
            if unit in ("g", "gr", "gramm", "г", "гр", "грамм", "gram", "grams", "ml", "мл") or (num >= 35 and not unit):
                ratio = num / max(1, food["g"])
                return int(num), max(1, int(food["kcal"] * ratio)), round(food["p"] * ratio, 1), round(food["f"] * ratio, 1), round(food["c"] * ratio, 1)
            else:
                mult = max(0.5, min(20.0, num))
                return int(food["g"] * mult), max(1, int(food["kcal"] * mult)), round(food["p"] * mult, 1), round(food["f"] * mult, 1), round(food["c"] * mult, 1)

        # 2-holat: kalit so'zdan oldin kelgan son (masalan: "2 ta somsa", "2 самсы", "300 gr osh", "1 bo'lak tort", "2 cups of coffee")
        p_before = rf"(?:(\d+(?:\.\d+)?)\s*({units_pattern})?\s*(?:of|из|ta|dona)?\s+)\b{re.escape(key)}\b"
        m_before = re.search(p_before, text, re.IGNORECASE)
        if m_before and m_before.group(1):
            num = float(m_before.group(1))
            unit = (m_before.group(2) or "").lower()
            if unit in ("g", "gr", "gramm", "г", "гр", "грамм", "gram", "grams", "ml", "мл") or (num >= 35 and not unit):
                ratio = num / max(1, food["g"])
                return int(num), max(1, int(food["kcal"] * ratio)), round(food["p"] * ratio, 1), round(food["f"] * ratio, 1), round(food["c"] * ratio, 1)
            else:
                mult = max(0.5, min(20.0, num))
                return int(food["g"] * mult), max(1, int(food["kcal"] * mult)), round(food["p"] * mult, 1), round(food["f"] * mult, 1), round(food["c"] * mult, 1)

        # Standart 1 porsiya
        return food["g"], food["kcal"], food["p"], food["f"], food["c"]

    @classmethod
    def scan_food_text_or_image(cls, text: Optional[str] = None, photo_data: Optional[bytes] = None) -> Dict[str, Any]:
        """Ovqat yoki shirinlik nomi yoki surati bo'yicha to'liq Eda AI tahlili.
        
        Har xil narsalarni (mashina, telefon, kitob, hujjat, devor va h.k.) qat'iyan rad etadi,
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
            has_non_food = any(re.search(rf"\b{re.escape(nk)}\b", t, re.IGNORECASE) for nk in NON_FOOD_KEYWORDS)
            has_food = any(any(re.search(rf"\b{re.escape(k)}\b", t, re.IGNORECASE) for k in f["keys"]) for f in FOOD_DATABASE)
            if has_non_food and not has_food:
                return {
                    "ok": False,
                    "is_food": False,
                    "error": "not_food",
                    "msg": "Kechirasiz, men faqat oziq-ovqat, taomlar, shirinliklar va ichimliklarni tahlil qila olaman. Iltimos, yeyiladigan mahsulot nomi yoki rasmini yuboring."
                }

        # 2. Matndan taomlarni izlash (caption yoki to'g'ridan-to'g'ri so'rov)
        if t:
            for food in FOOD_DATABASE:
                matched_key = None
                for k in food["keys"]:
                    if re.search(rf"\b{re.escape(k)}\b", t, re.IGNORECASE):
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

        # 3. Agar rasm yuborilgan bo'lsa (Pillow orqali sifatli tahlil va non-food filtri)
        if photo_data:
            valid_img = False
            img = None
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
                # Fotosurat piksel tahlili: ovqat rang profillarini tekshirish va har xil narsalarni rad etish
                try:
                    img_small = img.resize((64, 64)).convert("RGB")
                    raw_bytes = img_small.tobytes()
                    n_px = len(raw_bytes) // 3
                    if n_px > 0:
                        r_ch = raw_bytes[0::3]
                        g_ch = raw_bytes[1::3]
                        b_ch = raw_bytes[2::3]
                        avg_r = sum(r_ch) / n_px
                        avg_g = sum(g_ch) / n_px
                        avg_b = sum(b_ch) / n_px
                        brightness = (avg_r + avg_g + avg_b) / 3.0

                        # Rang to'yinganligi va dispersiyasi (tekstura/kontrast)
                        diffs = [max(r_ch[i], g_ch[i], b_ch[i]) - min(r_ch[i], g_ch[i], b_ch[i]) for i in range(n_px)]
                        avg_sat = sum(diffs) / n_px
                        var_r = sum((r_ch[i] - avg_r) ** 2 for i in range(n_px)) / n_px
                        std_r = var_r ** 0.5

                        # NON-FOOD filtrlari:
                        # 1) Qorong'u/qora rasm
                        is_too_dark = brightness < 28
                        # 2) Oq qog'oz / oq bo'sh fon
                        is_white_doc = brightness > 235 and avg_sat < 18
                        # 3) Monoxrom / kulrang metall, devor, qalam
                        is_monochrome = avg_sat < 14 and std_r < 15
                        # 4) Sovuq ko'k / osmon / ekran / ko'k kiyim (tabiatda ko'k ovqat deyarli yo'q)
                        is_cold_blue = avg_b > 70 and avg_b > avg_r * 1.25 and avg_b > avg_g * 1.15
                        # 5) Teksturasiz bir xil rangli tekis kvadrat
                        is_flat = std_r < 4.0 and avg_sat < 20

                        if is_too_dark or is_white_doc or is_monochrome or is_cold_blue or is_flat:
                            return {
                                "ok": False,
                                "is_food": False,
                                "error": "not_food",
                                "msg": "Kechirasiz, yuborilgan suratda taom yoki yeyiladigan mahsulot aniqlanmadi. Iltimos, faqat oziq-ovqat, taom yoki shirinlikning aniq suratini yuboring."
                            }

                        # Ovqat profiliga mos kelganda, ranglar va vaqt bo'yicha mos taomni aniqlash
                        if avg_g > avg_r and avg_g > avg_b:
                            # Yashil rang ustun — yangi salat
                            target_key = "salat"
                        elif avg_r > 150 and avg_g > 110 and avg_b < 120:
                            # Oltin-sariq / pishiriq rangi — shirinlik (medovik) yoki somsa
                            target_key = "medovik" if now_hour >= 15 else "somsa"
                        elif avg_r > avg_b * 1.2 and avg_g < 150:
                            # Qovurilgan qizg'ish-jigarrang go'sht / osh
                            target_key = "osh" if 11 <= now_hour < 16 else "shashlik"
                        elif meal_type == "b" and avg_r > 140 and avg_g > 130:
                            # Nonushta oqsil / tuxum
                            target_key = "tuxum"
                        elif avg_r < 110 and avg_g < 75 and avg_b < 65 and avg_r > avg_b:
                            # To'q shokoladli shirinlik
                            target_key = "shokolad"
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
