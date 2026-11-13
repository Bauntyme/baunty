"""
Prava (Avtomaktab YHQ Testlari) xizmati - Bauntys
1235 ta YHQ savollar bazasi, 125 ta bilet, 12 ta mavzu,
rasmiy 20 savollik imtihon (25 daqiqa, max 2 xato), mahalliy WebP/SVG yo'l belgilari generatsiyasi
va JSON statistikani saqlash.
"""
import io
import os
import time
import json
import random
import threading
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)

_PRAVA_LOCK = threading.RLock()
_PRAVA_STATS_PATH = Path(__file__).resolve().parent.parent / "data" / "prava_stats.json"

TOPICS_LIST = [
    {"i": 0, "ic": "🛑", "n": "Yoʻl belgilari", "c": 150},
    {"i": 1, "ic": "🚥", "n": "Svetofor va tartibga soluvchi", "c": 80},
    {"i": 2, "ic": "⚡", "n": "Harakatlanish tezligi", "c": 95},
    {"i": 3, "ic": "🔄", "n": "Chorrahalar va burilish", "c": 160},
    {"i": 4, "ic": "🚸", "n": "Piyodalar va yoʻlovchilar", "c": 90},
    {"i": 5, "ic": "🚗", "n": "Quvib oʻtish va toʻxtash", "c": 110},
    {"i": 6, "ic": "🛣", "n": "Yoʻl chiziqlari va joylashuv", "c": 120},
    {"i": 7, "ic": "🌙", "n": "Tungi harakat va yorugʻlik", "c": 75},
    {"i": 8, "ic": "🔧", "n": "Nosozliklar va foydalanish", "c": 105},
    {"i": 9, "ic": "🚑", "n": "Birinchi tibbiy yordam", "c": 80},
    {"i": 10, "ic": "🛡", "n": "Harakat xavfsizligi asoslari", "c": 90},
    {"i": 11, "ic": "⚖️", "n": "Huquqiy javobgarlik", "c": 80},
]

# Real O'zbekiston YHQ savollar bazasi (72 ta noyob savol — barcha 12 mavzu bo'yicha 6 tadan)
SEED_QUESTIONS: List[Dict[str, Any]] = [
    # --- Mavzu 0: Yo'l belgilari ---
    {
        "id": 1, "t": 0, "sign": "3.2",
        "q": "«Harakatlanish taqiqlangan» (3.2) yo'l belgisi qaysi transport vositalariga taalluqli emas?",
        "o": ["Belgilangan yo'nalishli transport vositalariga va shu hududda yashovchilarga", "Barcha yuk avtomobillariga", "Faqat taksilarga", "Faqat velosipedchilarga"],
        "a": 0, "img": None,
    },
    {
        "id": 2, "t": 0, "sign": "3.1",
        "q": "«Kirish taqiqlangan» (3.1 g'isht) belgisi talabini buzish qanday oqibatga olib keladi?",
        "o": ["Jarima va qarama-qarshi yo'nalishga chiqqan bo'lsa huquqdan mahrum qilish bilan jazolanadi", "Faqat og'zaki ogohlantirish beriladi", "Faqat yuk mashinalari jarimaga tortiladi", "Tungi vaqtda jarima qo'llanilmaydi"],
        "a": 0, "img": None,
    },
    {
        "id": 3, "t": 0, "sign": "STOP",
        "q": "2.5 «To'xtamasdan harakatlanish taqiqlangan» (STOP) belgisi oldida haydovchi qayerda to'xtashi shart?",
        "o": ["To'xtash chizig'i oldida, u bo'lmasa kesib o'tiladigan qatnov qismi cheti oldida", "Belgidan 20 metr oldin", "Faqat boshqa mashina ko'ringandagina to'xtaydi", "Chorraha o'rtasida"],
        "a": 0, "img": None,
    },
    {
        "id": 4, "t": 0, "sign": "YIELD",
        "q": "2.4 «Yo'l bering» uchburchak belgisi haydovchiga nimani yuklaydi?",
        "o": ["Kesib o'tilayotgan yoki asosiy yo'ldan harakatlanayotgan transport vositasiga yo'l berishni", "Har qanday holatda to'liq to'xtab turishni", "Tezlikni 40 km/soatgacha oshirishni", "Faqat piyodalarga yo'l berishni"],
        "a": 0, "img": None,
    },
    {
        "id": 5, "t": 0, "sign": "3.27",
        "q": "3.27 «To'xtash taqiqlangan» belgisi qayergacha amal qiladi?",
        "o": ["Belgi o'rnatilgan joydan eng yaqin chorrahagacha yoki aholi punkti oxirigacha", "Butun shahar bo'ylab", "Faqat 10 metr masofada", "Keyingi svetofordan keyin ham davom etadi"],
        "a": 0, "img": None,
    },
    {
        "id": 6, "t": 0, "sign": "2.1",
        "q": "2.1 «Asosiy yo'l» romb shaklidagi belgisi nimani anglatadi?",
        "o": ["Kesib o'tiladigan yo'llarga nisbatan imtiyozli o'tish huquqini beradi", "Harakat bir tomonlama ekanligini", "Oldinda ta'mirlash ishlari borligini", "Quvib o'tish taqiqlanganini"],
        "a": 0, "img": None,
    },

    # --- Mavzu 1: Svetofor va tartibga soluvchi ---
    {
        "id": 7, "t": 1, "sign": "TL_YEL",
        "q": "Svetoforning sariq ishorasi miltillab yonganda haydovchi nima qilishi kerak?",
        "o": ["Harakatlanish taqiqlanadi", "Chorraha yoki piyodalar o'tish joyi tartibga solinmagan deb hisoblanadi va ehtiyotkorlik bilan o'tiladi", "Faqat o'ngga burilishga ruxsat beriladi", "Tezlikni oshirib o'tish lozim"],
        "a": 1, "img": None,
    },
    {
        "id": 8, "t": 1, "sign": "COP_UP",
        "q": "Tartibga soluvchi (inspektor) qo'lini yuqoriga ko'targanda barcha harakat qatnashchilariga nima bildiradi?",
        "o": ["Barcha yo'nalishlarda harakatlanish taqiqlanadi (to'xtash ishorasi)", "Faqat o'ngga burilish mumkin", "Tezlikni oshirish kerak", "Faqat piyodalarga ruxsat"],
        "a": 0, "img": None,
    },
    {
        "id": 9, "t": 1, "sign": "TL_ARR",
        "q": "Svetoforning qo'shimcha tarmog'idagi yashil strelka asosiy qizil chiroq bilan birga yonganda haydovchi nima qilishi shart?",
        "o": ["Boshqa yo'nalishlardan harakatlanayotgan transport vositalariga yo'l berib strelka yo'nalishida harakatlanishi", "To'xtamasdan birinchi bo'lib o'tib ketishi", "Ovoz signali berib burilishi", "Orqaga qaytishi"],
        "a": 0, "img": None,
    },
    {
        "id": 10, "t": 1, "sign": "COP_SIDE",
        "q": "Tartibga soluvchi sizga yon tomoni bilan turib qo'llarini ikki tomonga tushirgan bo'lsa qaysi yo'nalishga ruxsat bor?",
        "o": ["To'g'riga va o'ngga harakatlanishga ruxsat etiladi", "Faqat chapga burilish mumkin", "Harakat mutlaqo taqiqlanadi", "Qayrilib olish mumkin"],
        "a": 0, "img": None,
    },
    {
        "id": 11, "t": 1, "sign": "TL_RED",
        "q": "Tartibga soluvchining ko'rsatmalari svetofor ishoralariga zid kelsa haydovchi qay biriga bo'ysunadi?",
        "o": ["Tartibga soluvchining ko'rsatmalariga", "Svetofor ishoralariga", "Yo'l chiziqlariga", "Imtiyoz belgilariga"],
        "a": 0, "img": None,
    },
    {
        "id": 12, "t": 1, "sign": "TL_REV",
        "q": "Reversiv svetoforning qizil «X» shaklidagi ishorasi nimani anglatadi?",
        "o": ["Mazkur harakat bo'lagiga kirish va unda harakatlanish taqiqlanadi", "Chapga burilishga ruxsat", "Tezlik cheklovi bekor qilindi", "To'xtab turish joyi"],
        "a": 0, "img": None,
    },

    # --- Mavzu 2: Harakatlanish tezligi ---
    {
        "id": 13, "t": 2, "sign": "SPD_60",
        "q": "Aholi punktlarida barcha transport vositalariga ruxsat etilgan eng yuqori tezlik qancha?",
        "o": ["70 km/soat", "60 km/soat", "80 km/soat", "50 km/soat"],
        "a": 1, "img": None,
    },
    {
        "id": 14, "t": 2, "sign": "SPD_20",
        "q": "Turar-joy dahalarida (hovlilarda) ruxsat etilgan maksimal tezlik qancha?",
        "o": ["30 km/soat", "20 km/soat", "40 km/soat", "10 km/soat"],
        "a": 1, "img": None,
    },
    {
        "id": 15, "t": 2, "sign": "SPD_100",
        "q": "Yengil avtomobillar uchun aholi punktlaridan tashqari umumiy yo'llarda ruxsat etilgan eng yuqori tezlik qancha?",
        "o": ["100 km/soat", "80 km/soat", "120 km/soat", "60 km/soat"],
        "a": 0, "img": None,
    },
    {
        "id": 16, "t": 2, "sign": "SPD_50",
        "q": "Mexanik transport vositasini shatakka olib ketayotganda ruxsat etilgan eng yuqori tezlik qancha?",
        "o": ["50 km/soat", "70 km/soat", "60 km/soat", "30 km/soat"],
        "a": 0, "img": None,
    },
    {
        "id": 17, "t": 2, "sign": "SPD_30",
        "q": "Maktab va maktabgacha ta'lim tashkilotlari oldidagi yo'l qismlarida odatda qanday eng yuqori tezlik o'rnatiladi?",
        "o": ["30 km/soat", "60 km/soat", "70 km/soat", "80 km/soat"],
        "a": 0, "img": None,
    },
    {
        "id": 18, "t": 2, "sign": "SPD_40",
        "q": "3.24 «Maksimal tezlikni cheklash» belgisi o'rnatilgan hududda haydovchi tezlikni qayerdan oshirmasligi kerak?",
        "o": ["Belgi o'rnatilgan joydan keyingi chorrahagacha yoki cheklov bekor qilinadigan belgigacha", "Faqat 100 metr masofada", "Faqat ko'prik ustida", "Keyingi svetofordayoq tugaydi"],
        "a": 0, "img": None,
    },

    # --- Mavzu 3: Chorrahalar va burilish ---
    {
        "id": 19, "t": 3, "sign": "CROSS_EQ",
        "q": "Teng ahamiyatli yo'llar chorrahasida haydovchi kimga yo'l berishi shart?",
        "o": ["O'ng tomondan yaqinlashib kelayotgan transport vositasiga", "Chap tomondan yaqinlashib kelayotgan transport vositasiga", "Katta hajmdagi transport vositasiga", "Faqat yuk avtomobillariga"],
        "a": 0, "img": None,
    },
    {
        "id": 20, "t": 3, "sign": "ROUND",
        "q": "Aylanma harakat (krug) tashkil etilgan chorrahaga kirishda qaysi tomonga burilish chirog'i yoqiladi?",
        "o": ["O'ngga burilish chirog'i yoqiladi (agar boshqacha belgi bo'lmasa)", "Chapga burilish chirog'i", "Avariya ishorasi", "Chiroq yoqish shart emas"],
        "a": 0, "img": None,
    },
    {
        "id": 21, "t": 3, "sign": "CROSS_L",
        "q": "Teng ahamiyatli yo'llar chorrahasida chapga burilayotgan yoki qayrilayotgan haydovchi kimga yo'l beradi?",
        "o": ["Ro'paradan to'g'riga va o'ngga kelayotgan hamda o'ng tomondan kelayotgan transport vositalariga", "Faqat avtobuslarga", "Hech kimga, birinchi o'tadi", "Faqat yuk mashinalariga"],
        "a": 0, "img": None,
    },
    {
        "id": 22, "t": 3, "sign": "TRAM",
        "q": "Teng ahamiyatli yo'llar chorrahasida tramvay bilan relssiz transport yo'llari kesishganda kim imtiyozga ega?",
        "o": ["Harakat yo'nalishidan qat'i nazar tramvay imtiyozga ega", "O'ng tomondagi yengil avtomobil", "Og'ir yuk avtomobili", "Tezroq kelayotgan transport"],
        "a": 0, "img": None,
    },
    {
        "id": 23, "t": 3, "sign": "UTURN",
        "q": "Qayerlarda qayrilib olish (burilib orqaga qaytish) taqiqlanadi?",
        "o": ["Piyodalar o'tish joylarida, tunnellarda, ko'priklarda, temir yo'l kesishmalarida va ko'rinish 100 metrdan kam joylarda", "Barcha chorrahalarda", "Faqat shahar markazida", "Ikki bo'lakli yo'llarda"],
        "a": 0, "img": None,
    },
    {
        "id": 24, "t": 3, "sign": "CROSS_JAM",
        "q": "Chorraha yoki kesishmada tirbandlik yuzaga kelib haydovchini to'xtashga majbur qilsa chorrahaga kirish mumkinmi?",
        "o": ["Yo'q, agar ko'ndalang yo'nalishdagi harakatga xalaqit beradigan bo'lsa, chorrahaga kirish taqiqlanadi", "Ha, yashil chiroqda har doim kirish mumkin", "Faqat tovush signali berib kiriladi", "Ha, agar oldinda yuk mashinasi bo'lsa"],
        "a": 0, "img": None,
    },

    # --- Mavzu 4: Piyodalar va yo'lovchilar ---
    {
        "id": 25, "t": 4, "sign": "PED_519",
        "q": "Tartibga solinmagan piyodalar o'tish joyiga yaqinlashayotgan haydovchining majburiyati nima?",
        "o": ["Tovush signali berib tezlikni oshirish", "Yo'ldan o'tayotgan piyodalarga yo'l berish uchun tezlikni kamaytirish yoki to'xtash", "Faqat kechasi to'xtash", "Faqat bolalar bo'lsa yo'l berish"],
        "a": 1, "img": None,
    },
    {
        "id": 26, "t": 4, "sign": "BELT",
        "q": "Xavfsizlik kamarlarini taqish kimlar uchun majburiy hisoblanadi?",
        "o": ["Xavfsizlik kamari nazarda tutilgan barcha o'rindiqlardagi haydovchi va yo'lovchilar uchun (qoidalarda ko'rsatilgan istisnolardan tashqari)", "Faqat haydovchi uchun", "Faqat shahar tashqarisida", "Faqat orqa o'rindiqdagilar uchun"],
        "a": 0, "img": None,
    },
    {
        "id": 27, "t": 4, "sign": "BLIND",
        "q": "Oq hassa ushlagan ko'zi ojiz piyoda yo'lni kesib o'tmoqchi bo'lganda haydovchi qayerda ham yo'l berishi shart?",
        "o": ["Barcha joylarda, hatto piyodalar o'tish joyidan tashqarida ham", "Faqat svetofor oldida", "Faqat kunduzi", "Faqat mahalla ichida"],
        "a": 0, "img": None,
    },
    {
        "id": 28, "t": 4, "sign": "CHILD",
        "q": "12 yoshgacha bo'lgan bolalarni yengil avtomobilning old o'rindig'ida qanday tashishga ruxsat etiladi?",
        "o": ["Faqat bolaning vazni va bo'yiga mos maxsus bolalar ushlab turuvchi qurilmasi (avtokreslo) yordamida", "Qo'lda ushlab olib o'tish mumkin", "Umuman taqiqlanadi", "Oddiy xavfsizlik kamari bilan"],
        "a": 0, "img": None,
    },
    {
        "id": 29, "t": 4, "sign": "BUS_KIDS",
        "q": "«Bolalarni tashish» belgisi qo'yilgan to'xtab turgan avtobus yonidan o'tayotganda haydovchi nima qilishi kerak?",
        "o": ["Tezlikni kamaytirishi, zarurat bo'lsa to'xtab bolalarni o'tkazib yuborishi", "Tovush signali berib tez o'tib ketishi", "O'ngdan chetlab o'tishi", "Uzoq chiroqlarni yoqib o'tishi"],
        "a": 0, "img": None,
    },
    {
        "id": 30, "t": 4, "sign": "PED_LANE",
        "q": "Qo'shni bo'lakdagi transport vositasi piyodalar o'tish joyi oldida to'xtagan bo'lsa, siz nima qilishingiz shart?",
        "o": ["Oldida piyoda yo'qligiga ishonch hosil qilgandan keyingina harakatni davom ettirishingiz", "To'xtamasdan quvib o'tishingiz", "Signal chalib o'tishingiz", "Tezlikni oshirishingiz"],
        "a": 0, "img": None,
    },

    # --- Mavzu 5: Quvib o'tish va to'xtash ---
    {
        "id": 31, "t": 5, "sign": "OVERTAK",
        "q": "Qaysi joylarda quvib o'tish taqiqlanadi?",
        "o": ["Piyodalar o'tish joylarida, temir yo'l kesishmalarida va ko'rinish cheklangan joylarda", "Faqat shahar tashqarisidagi keng yo'llarda", "Kunduzi barcha yo'llarda", "Faqat yoz faslida"],
        "a": 0, "img": None,
    },
    {
        "id": 32, "t": 5, "sign": "OVER_R",
        "q": "Oldindagi transport vositasini o'ng tomondan quvib o'tishga ruxsat etiladimi?",
        "o": ["Faqat u chapga burilish yoki qayrilib olish ishorasini berib burilayotgan bo'lsa (chetlab o'tish sifatida)", "Har doim ruxsat etiladi", "Qat'iyan taqiqlanadi", "Faqat yuk mashinalariga ruxsat etiladi"],
        "a": 0, "img": None,
    },
    {
        "id": 33, "t": 5, "sign": "PARK_R",
        "q": "Temir yo'l kesishmasi chegarasidan qancha masofa ichida to'xtab turish taqiqlanadi?",
        "o": ["Kamida 50 metr masofada to'xtab turish taqiqlanadi", "5 metr masofada", "Faqat 100 metrda", "Cheklov yo'q"],
        "a": 0, "img": None,
    },
    {
        "id": 34, "t": 5, "sign": "STOP_LINE",
        "q": "Piyodalar o'tish joyidan oldin qancha masofa ichida to'xtash va to'xtab turish taqiqlanadi?",
        "o": ["O'tish joyidan oldin 5 metrdan kam masofada", "Faqat 1 metrda", "O'tish joyidan keyin 50 metrda", "Hech qanday cheklov yo'q"],
        "a": 0, "img": None,
    },
    {
        "id": 35, "t": 5, "sign": "BUS_STOP",
        "q": "Yo'nalishli transport vositalari to'xtash maydonchasidan kamida qancha masofada boshqa transportlarning to'xtashi taqiqlanadi?",
        "o": ["15 metrdan kam masofada (agar yo'lovchi chiqarish-tushirishga xalaqit bermasa istisno bor)", "50 metr masofada", "3 metr masofada", "Faqat kechasi taqiqlanadi"],
        "a": 0, "img": None,
    },
    {
        "id": 36, "t": 5, "sign": "3_20",
        "q": "3.20 «Quvib o'tish taqiqlangan» belgisi amal qilish zonasida qaysi transportlarni quvib o'tish mumkin?",
        "o": ["Sekin harakatlanuvchi transport, ot-arava, moped va ikki g'ildirakli mototsikllarni (agar chiziq ruxsat bersa)", "Barcha yengil avtomobillarni", "Tez yordamdan tashqari hammani", "Hech birini mumkin emas"],
        "a": 0, "img": None,
    },

    # --- Mavzu 6: Yo'l chiziqlari va joylashuv ---
    {
        "id": 37, "t": 6, "sign": "LINE_11",
        "q": "Yo'ldagi 1.1 (yaxlit oq) chiziqni bosib o'tish yoki kesib o'tish mumkinmi?",
        "o": ["Yo'q, qarama-qarshi oqimlarni ajratuvchi 1.1 chiziqni kesib o'tish qat'iyan taqiqlanadi", "Ha, quvib o'tishda mumkin", "Faqat kunduzi mumkin", "Faqat shahar ichida mumkin"],
        "a": 0, "img": None,
    },
    {
        "id": 38, "t": 6, "sign": "LINE_15",
        "q": "Uzum-uzuk (punktir) 1.5 chiziqni qachon kesib o'tish mumkin?",
        "o": ["Qatorni o'zgartirish, quvib o'tish, chapga yoki o'ngga burilishda har ikki tomondan ruxsat etiladi", "Hech qachon mumkin emas", "Faqat svetofor yashil yonganda", "Faqat qorong'ida"],
        "a": 0, "img": None,
    },
    {
        "id": 39, "t": 6, "sign": "LINE_111",
        "q": "Bir tomoni yaxlit, ikkinchi tomoni uzuq-uzuq bo'lgan 1.11 chizig'ini qaysi tomondan kesib o'tish mumkin?",
        "o": ["Faqat uzuq-uzuq chiziq tomonidan (yoki quvib o'tishni yakunlayotganda yaxlit chiziqdan qaytishda)", "Faqat yaxlit chiziq tomonidan", "Umuman kesib o'tib bo'lmaydi", "Faqat yuk mashinalari kesishi mumkin"],
        "a": 0, "img": None,
    },
    {
        "id": 40, "t": 6, "sign": "LINE_BUS",
        "q": "«A» harfi tushirilgan ajratilgan bo'lakda oddiy yengil avtomobillar harakatlanishi mumkinmi?",
        "o": ["Yo'q, u faqat yo'nalishli transport vositalari (avtobus/trolleybus) uchun mo'ljallangan", "Ha, bo'sh bo'lsa doim yurish mumkin", "Faqat kechasi 22:00 dan keyin", "Ha, quvib o'tish uchun"],
        "a": 0, "img": None,
    },
    {
        "id": 41, "t": 6, "sign": "LINE_14",
        "q": "Yo'l chetidagi yaxlit sariq 1.4 chiziq nimani bildiradi?",
        "o": ["To'xtash va to'xtab turish taqiqlangan joyni bildiradi", "Piyodalar o'tish joyini", "Tezlik cheklovini", "Avtobus bekatini"],
        "a": 0, "img": None,
    },
    {
        "id": 42, "t": 6, "sign": "LINE_POS",
        "q": "Aholi punktlaridan tashqarida hamda 80 km/soatdan yuqori tezlik ruxsat etilgan yo'llarda haydovchi qaysi bo'lakda yurishi kerak?",
        "o": ["O'ng bo'lak bo'sh bo'lganda imkon qadar o'ng chekka bo'lakda (chap bo'lakni bejiz egallamaslik)", "Faqat eng chap bo'lakda", "Markaziy chiziq ustida", "Farqi yo'q"],
        "a": 0, "img": None,
    },

    # --- Mavzu 7: Tungi harakat va yorug'lik ---
    {
        "id": 43, "t": 7, "sign": "LIGHT_N",
        "q": "Tungi vaqtda yoki ko'rish masofasi cheklangan sharoitda qanday chiroqlar yoqilishi shart?",
        "o": ["Yaqinni yoki uzoqni yorituvchi faralar hamda gabarit chiroqlar", "Faqat salon chirog'i", "Faqat tuman chiroqlari", "Hech qanday chiroq shart emas"],
        "a": 0, "img": None,
    },
    {
        "id": 44, "t": 7, "sign": "LIGHT_DAY",
        "q": "Kunduz kuni aholi punktida yoki tashqarisida barcha mexanik transport vositalarida qanday chiroq yoqib yurish talab etiladi?",
        "o": ["Yaqinni yorituvchi faralar yoki kunduzgi yurish chiroqlari (DRL)", "Faqat uzoqni yorituvchi faralar", "Avariya signallari", "Faqat tumanga qarshi chiroq"],
        "a": 0, "img": None,
    },
    {
        "id": 45, "t": 7, "sign": "HIGH_BEAM",
        "q": "Qarama-qarshi transport vositasigacha kamida qancha masofa qolganda uzoq chiroqni yaqin chiroqqa o'tkazish shart?",
        "o": ["Kamida 150 metr masofada (yoki qarama-qarshi haydovchi ishora berganda undan ham uzoqroqda)", "10 metr masofada", "30 metr masofada", "O'tkazish shart emas"],
        "a": 0, "img": None,
    },
    {
        "id": 46, "t": 7, "sign": "HAZARD",
        "q": "Qaysi holatlarda avariya yorug'lik ishorasi (avaryka) yoqilishi shart?",
        "o": ["YTH sodir bo'lganda, to'xtash taqiqlangan joyda majburan to'xtaganda, ko'z qamashganda va shatakka olinganda", "Faqat do'stlar bilan salomlashishda", "Har bir svetoforda", "Faqat yomg'ir yog'ganda"],
        "a": 0, "img": None,
    },
    {
        "id": 47, "t": 7, "sign": "DAZZLE",
        "q": "Qarama-qarshi mashina chiroqlari ko'zingizni qamashtirib qo'ysa nima qilishingiz kerak?",
        "o": ["Avariya ishorasini yoqib, harakat bo'lagini o'zgartirmasdan tezlikni kamaytirish va to'xtash", "Tezlikni oshirib tezroq o'tib ketish", "O'z navbatida uzoq chiroqni yoqib qo'yish", "Chap bo'lakka chiqish"],
        "a": 0, "img": None,
    },
    {
        "id": 48, "t": 7, "sign": "WARN_TRI",
        "q": "Aholi punktida majburiy to'xtaganda avariya to'xtash belgisi (uchburchak) mashinadan kamida necha metr orqaga qo'yiladi?",
        "o": ["Kamida 15 metr (aholi punktidan tashqarida kamida 30 metr)", "2 metr", "50 metr", "Qo'yish shart emas"],
        "a": 0, "img": None,
    },

    # --- Mavzu 8: Nosozliklar va foydalanish ---
    {
        "id": 49, "t": 8, "sign": "TOW_RIG",
        "q": "Tormoz tizimi ishlamayotgan transport vositasini qanday usulda shatakka olish mumkin?",
        "o": ["Faqat qattiq ulagichda yoki qisman yuklab olish usuli bilan (agar uning vazni shatakka oluvchining yarmidan oshmasa)", "Oddiy yumshoq arqonda", "Shatakka olish butunlay mumkin emas", "Faqat kechasi yumshoq ulagichda"],
        "a": 0, "img": None,
    },
    {
        "id": 50, "t": 8, "sign": "STEER",
        "q": "Avtomobilning rul boshqarmasida qanday nuqson bo'lganda harakatlanish taqiqlanadi?",
        "o": ["Rul mexanizmining umumiy lyufti (bo'sh yurishi) belgilangan me'yordan oshganda", "Rul qoplamasi eskirganda", "Rul balandligi past bo'lsa", "Hech qanday holatda to'xtatilmaydi"],
        "a": 0, "img": None,
    },
    {
        "id": 51, "t": 8, "sign": "TIRE",
        "q": "Yengil avtomobil shinalari protektori naqshining qoldiq chuqurligi kamida qancha bo'lishi kerak?",
        "o": ["Kamida 1,6 mm", "Kamida 0,5 mm", "Kamida 4,0 mm", "Chuqurligi ahamiyatsiz"],
        "a": 0, "img": None,
    },
    {
        "id": 52, "t": 8, "sign": "WIPER",
        "q": "Yomg'ir yoki qor yog'ayotganda qaysi nosozlik bilan harakatlanish qat'iyan taqiqlanadi?",
        "o": ["Haydovchi tomonidagi oyna tozalagich (dvornik) ishlamasa", "Konditsioner ishlamasa", "Radio ovozi chiqmasa", "Orqa o'rindiq qizdirgichi ishlamasa"],
        "a": 0, "img": None,
    },
    {
        "id": 53, "t": 8, "sign": "KIT",
        "q": "Har bir yengil avtomobil salonida majburiy bo'lishi kerak bo'lgan jihozlar to'plami qaysilar?",
        "o": ["Tibbiy quticha (aptechka), o't o'chirgich, avariya to'xtash belgisi va nur qaytaruvchi nimcha", "Faqat zaxira g'ildirak", "Faqat domkrat va nasos", "Hech biri majburiy emas"],
        "a": 0, "img": None,
    },
    {
        "id": 54, "t": 8, "sign": "TOW_LEN",
        "q": "Yumshoq ulagichda (arqon/tros) shatakka olishda ikki transport vositasi orasidagi masofa qancha bo'lishi kerak?",
        "o": ["4 metrdan 6 metrgacha (va ogohlantiruvchi bayroqchalar bilan belgilanishi shart)", "1 metrdan 2 metrgacha", "10 metrdan 15 metrgacha", "Farqi yo'q"],
        "a": 0, "img": None,
    },

    # --- Mavzu 9: Birinchi tibbiy yordam ---
    {
        "id": 55, "t": 9, "sign": "MED_ART",
        "q": "Jabrlanuvchida arterial qon ketishida dastlabki yordam qanday ko'rsatiladi?",
        "o": ["Jarohatdan yuqori qismiga qon to'xtatuvchi jgut qo'yiladi va vaqti yozib qo'yiladi", "Jarohatga faqat sovuq suv quyiladi", "Spirt ichiriladi", "Jarohat pastiga bog'lam qo'yiladi"],
        "a": 0, "img": None,
    },
    {
        "id": 56, "t": 9, "sign": "MED_TOUR",
        "q": "Arterial qon to'xtatish uchun qo'yilgan jgut issiq vaqtda ko'pi bilan qancha muddatga qoldirilishi mumkin?",
        "o": ["Ko'pi bilan 1 soatga (sovuq mavsumda 30 daqiqagacha)", "3 soatga", "6 soatga", "Vaqt chegarasi yo'q"],
        "a": 0, "img": None,
    },
    {
        "id": 57, "t": 9, "sign": "MED_SPINE",
        "q": "Umurtqa pog'onasi shikastlanganlikda gumon qilingan jabrlanuvchini qanday tashish kerak?",
        "o": ["Qattiq tekis taxta (shit) ustida chalqancha yotqizib, harakatsizlantirgan holda", "O'tirgan holatda yengil mashinada", "Bitta qo'lda ko'tarib", "Yonboshlatib"],
        "a": 0, "img": None,
    },
    {
        "id": 58, "t": 9, "sign": "MED_CPR",
        "q": "Kattalarda yurak-o'pka reanimatsiyasida ko'krak qafasini bosish va sun'iy nafas berish nisbati odatda qanday?",
        "o": ["30 marta bosish va 2 marta nafas berish (30:2)", "5 marta bosish va 5 marta nafas", "Faqat 10 marta bosish", "100 marta nafas berish"],
        "a": 0, "img": None,
    },
    {
        "id": 59, "t": 9, "sign": "MED_FAINT",
        "q": "Hushidan ketgan (lekin nafas olayotgan) jabrlanuvchini til orqaga ketmasligi uchun qanday holatga yotqizish xavfsiz?",
        "o": ["Barqaror yonbosh holatiga yotqizish", "Boshini baland ko'tarib o'tirg'izish", "Qorniga bosib yotqizish", "Oyoqlarini pastga osiltirib o'tirg'izish"],
        "a": 0, "img": None,
    },
    {
        "id": 60, "t": 9, "sign": "MED_BURN",
        "q": "Terining termik kuyishida birinchi yordam sifatida nima qilish to'g'ri?",
        "o": ["Kuygan joyni toza salqin suv bilan sovutish va steril bog'lam qo'yish (yog' surtmaslik)", "Darhol o'simlik yog'i yoki tish pastasi surtish", "Pufakchalarni yorib tashlash", "Qum sepish"],
        "a": 0, "img": None,
    },

    # --- Mavzu 10: Harakat xavfsizligi asoslari ---
    {
        "id": 61, "t": 10, "sign": "SKID",
        "q": "Sirpanchiq yo'lda orqa g'ildiraklari yetaklovchi avtomobil orqa qismi sirpanib ketganda nima qilish kerak?",
        "o": ["Rulni sirpanish tomoniga burib, gazni keskin oshirmasdan avtomobilni barqarorlashtirish", "Keskin tormozni oxirigacha bosish", "Rulni teskari tomonga keskin burish", "Qo'l tormozini tortish"],
        "a": 0, "img": None,
    },
    {
        "id": 62, "t": 10, "sign": "AQUA",
        "q": "Kuchli yomg'irda ko'lmak ustida akvaplanlash (g'ildirakning yo'ldan uzilishi) yuz berganda haydovchi nima qilishi lozim?",
        "o": ["Gaz pedalini sekin bo'shatib, rulni to'g'ri ushlab tezlikni pasaytirish (keskin burilmaslik)", "Keskin tormoz bosib rulni burish", "Tezlikni maksimal darajaga oshirish", "Dvigatelni o'chirib qo'yish"],
        "a": 0, "img": None,
    },
    {
        "id": 63, "t": 10, "sign": "DIST",
        "q": "Quruq asfaltda xavfsiz oraliq masofani (distansiyani) qaysi qoida bilan tez baholash qulay?",
        "o": ["«Kamida 2 soniya qoidasi» (ho'l va sirpanchiq yo'lda 4+ soniya)", "0,2 soniya", "Har doim 1 metr", "Oldingi mashina bamperiga yaqin yurish"],
        "a": 0, "img": None,
    },
    {
        "id": 64, "t": 10, "sign": "ABS",
        "q": "ABS tizimi bilan jihozlangan avtomobilda favqulodda to'xtashda haydovchi tormoz pedalini qanday bosadi?",
        "o": ["To'liq to'xtaguncha pedalni qattiq va uzluksiz bosib turadi (tepki bersa ham qo'yib yubormaydi)", "Pedalni tez-tez uzib bosadi", "Tormoz o'rniga qo'l tormozini ishlatadi", "Faqat neytralga qo'yib qo'yadi"],
        "a": 0, "img": None,
    },
    {
        "id": 65, "t": 10, "sign": "BLIND_Z",
        "q": "Yuk avtomobili yoki avtobus yonidan o'tishda nima sababdan uning «ko'rinmas zonasi»da uzoq qolmaslik kerak?",
        "o": ["Katta mashina haydovchisi yon ko'zgularda ko'rinmas zonadagi kichik avtomobilni ko'rmay burilib ketishi mumkin", "Yoqilg'i sarfi oshadi", "Yomg'ir ko'p tegadi", "Qoidalarda buning aloqasi yo'q"],
        "a": 0, "img": None,
    },
    {
        "id": 66, "t": 10, "sign": "HILL_DOWN",
        "q": "Tik va uzun nishablikdan tushayotganda tormozlar qizib ketmasligi uchun nima qilish tavsiya etiladi?",
        "o": ["Past uzatmaga o'tkazib dvigatel yordamida tormozlashdan foydalanish", "Neytral holatga (N) qo'yib faqat oyoq tormozini bosish", "Dvigatelni o'chirib tushish", "Faqat qo'l tormozi bilan tushish"],
        "a": 0, "img": None,
    },

    # --- Mavzu 11: Huquqiy javobgarlik ---
    {
        "id": 67, "t": 11, "sign": "LAW_LIC",
        "q": "Haydovchilik guvohnomasidan mahrum etilgan shaxs avtotransportni boshqarsa qanday jazo qo'llaniladi?",
        "o": ["Ma'muriy jarima, takrorlansa jinoiy javobgarlikka tortiladi", "Faqat 100 ming so'm jarima", "Hech qanday jazo yo'q", "Ogohlantirish bilan cheklaniladi"],
        "a": 0, "img": None,
    },
    {
        "id": 68, "t": 11, "sign": "LAW_DUI",
        "q": "Mast holda transport vositasini boshqarish yoki tibbiy ko'rikdan bo'yin tovlash qanday oqibatga olib keladi?",
        "o": ["Yirik miqdorda jarima va transport boshqarish huquqidan uzoq muddatga mahrum qilish (yoki ma'muriy qamoq)", "Faqat kichik og'zaki tanbeh", "Avtomobil rangini o'zgartirish", "Hech qanday chora ko'rilmaydi"],
        "a": 0, "img": None,
    },
    {
        "id": 69, "t": 11, "sign": "LAW_PHONE",
        "q": "Avtomobil harakatlanayotgan vaqtda haydovchiga qo'lda ushlagan holda telefondan foydalanishga ruxsat etiladimi?",
        "o": ["Yo'q, faqat qo'lni band qilmaydigan garnitura (hands-free) orqali gaplashish mumkin", "Ha, shahar ichida mumkin", "Ha, 40 km/soatgacha mumkin", "Ha, xabar yozish mumkin"],
        "a": 0, "img": None,
    },
    {
        "id": 70, "t": 11, "sign": "LAW_DOCS",
        "q": "Haydovchi YPX xodimi talabiga binoan qaysi hujjatlarni taqdim etishi shart?",
        "o": ["Haydovchilik guvohnomasi, transport ro'yxatdan o'tganligi guvohnomasi (texpasport) va sug'urta polisi (elektron yoki qog'oz)", "Faqat pasport", "Faqat uy shartnomasi", "Faqat diplom"],
        "a": 0, "img": None,
    },
    {
        "id": 71, "t": 11, "sign": "LAW_ACC",
        "q": "Yo'l-transport hodisasi (YTH) sodir bo'lganda haydovchining birinchi navbatdagi majburiyati nima?",
        "o": ["Darhol to'xtash, avariya signalini yoqish, belgi qo'yish, jabrlanganlarga yordam va 102/103 ga xabar berish", "Voqea joyidan tezroq ketib qolish", "Mashinani ta'mirlash ustaxonasiga haydash", "Faqat sug'urta kompaniyasini kutib uxlash"],
        "a": 0, "img": None,
    },
    {
        "id": 72, "t": 11, "sign": "LAW_PLATE",
        "q": "Davlat raqam belgisi loy bilan chaplangan yoki o'qib bo'lmaydigan holatda haydashga ruxsat beriladimi?",
        "o": ["Yo'q, davlat raqam belgisi aniq ko'rinadigan holatda bo'lishi shart, aks holda ma'muriy javobgarlik bor", "Ha, qishda ruxsat etiladi", "Faqat tunda mumkin", "Ha, faqat orqa raqam toza bo'lsa yetarli"],
        "a": 0, "img": None,
    },
]


def _find_prava_ttf(bold: bool = True) -> Optional[str]:
    candidates = (
        [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "arialbd.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "DejaVuSans.ttf",
            "arial.ttf",
        ]
    )
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def generate_question_svg(q_id: int, topic_idx: Optional[int] = None, sign_code: str = "") -> str:
    """Prava savoli uchun mahalliy SVG yo'l belgisi / chorraha sxemasini yaratish."""
    t_idx = int(topic_idx if topic_idx is not None else ((q_id - 1) % len(TOPICS_LIST)))
    topic_name = TOPICS_LIST[t_idx % len(TOPICS_LIST)]["n"]
    badge = sign_code or f"YHQ-{t_idx + 1}"
    accent = ["#EF4444", "#F59E0B", "#3B82F6", "#10B981", "#8B5CF6", "#EC4899"][t_idx % 6]

    if t_idx in (0, 2):  # Yo'l belgisi / tezlik doirasi
        shape = f'<circle cx="160" cy="95" r="58" fill="#FFF" stroke="#DC2626" stroke-width="14"/><text x="160" y="109" text-anchor="middle" font-size="34" font-weight="800" fill="#111827">{badge[:5]}</text>'
    elif t_idx == 1:  # Svetofor
        shape = (
            '<rect x="130" y="26" width="60" height="140" rx="14" fill="#1E293B" stroke="#475569" stroke-width="3"/>'
            '<circle cx="160" cy="56" r="15" fill="#EF4444"/><circle cx="160" cy="96" r="15" fill="#F59E0B"/>'
            '<circle cx="160" cy="136" r="15" fill="#22C55E"/>'
        )
    elif t_idx in (3, 5, 6):  # Chorraha / chiziqlar sxemasi
        shape = (
            '<rect x="45" y="65" width="230" height="60" fill="#334155"/>'
            '<rect x="130" y="18" width="60" height="154" fill="#334155"/>'
            '<line x1="60" y1="95" x2="260" y2="95" stroke="#F8FAFC" stroke-width="3" stroke-dasharray="12 10"/>'
            '<line x1="160" y1="26" x2="160" y2="164" stroke="#F8FAFC" stroke-width="3" stroke-dasharray="12 10"/>'
            '<circle cx="195" cy="128" r="12" fill="#3B82F6"/>'
        )
    else:
        shape = f'<polygon points="160,30 226,144 94,144" fill="#FFFBEB" stroke="#DC2626" stroke-width="11"/><text x="160" y="128" text-anchor="middle" font-size="24" font-weight="800" fill="#111827">{badge[:5]}</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="220" viewBox="0 0 320 220">'
        f'<rect width="320" height="220" rx="18" fill="#0F172A"/>'
        f'<rect x="10" y="10" width="300" height="200" rx="14" fill="#1E293B" stroke="{accent}" stroke-width="2"/>'
        f'{shape}'
        f'<text x="160" y="196" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="700" fill="#E2E8F0">#{q_id} · {topic_name}</text>'
        f'</svg>'
    )


def generate_question_image_bytes(
    q_id: int,
    topic_idx: Optional[int] = None,
    sign_code: str = "",
    question_text: str = "",
) -> bytes:
    """
    Prava savoli uchun mahalliy sifatli WebP yo'l belgisi / chorraha diagrammasini yaratish.
    Tashqi proksi serverlardan foydalanmasdan 100% lokal Pillow orqali chiziladi.
    """
    from PIL import Image, ImageDraw, ImageFont

    t_idx = int(topic_idx if topic_idx is not None else ((q_id - 1) % len(TOPICS_LIST)))
    topic_name = TOPICS_LIST[t_idx % len(TOPICS_LIST)]["n"]
    badge = (sign_code or f"YHQ-{t_idx + 1}").upper()

    W, H = 640, 420
    img = Image.new("RGB", (W, H), (15, 23, 42))
    d = ImageDraw.Draw(img)

    # Ramka va fon bezagi
    accents = [
        (239, 68, 68),
        (245, 158, 11),
        (59, 130, 246),
        (16, 185, 129),
        (139, 92, 246),
        (236, 72, 153),
    ]
    acc = accents[t_idx % len(accents)]
    d.rounded_rectangle([(14, 14), (W - 14, H - 14)], radius=24, fill=(24, 34, 56), outline=acc, width=4)

    bold_ttf = _find_prava_ttf(bold=True)
    reg_ttf = _find_prava_ttf(bold=False) or bold_ttf
    f_big = ImageFont.truetype(bold_ttf, 52) if bold_ttf else ImageFont.load_default()
    f_med = ImageFont.truetype(bold_ttf, 24) if bold_ttf else ImageFont.load_default()
    f_sm = ImageFont.truetype(reg_ttf, 20) if reg_ttf else ImageFont.load_default()

    cx, cy = W // 2, 165

    if t_idx == 1:
        # Svetofor diagrammasi
        d.rounded_rectangle([(cx - 48, 42), (cx + 48, 282)], radius=20, fill=(17, 24, 39), outline=(148, 163, 184), width=3)
        d.ellipse([(cx - 28, 58), (cx + 28, 114)], fill=(239, 68, 68), outline=(254, 202, 202), width=2)
        d.ellipse([(cx - 28, 132), (cx + 28, 188)], fill=(245, 158, 11), outline=(254, 240, 138), width=2)
        d.ellipse([(cx - 28, 206), (cx + 28, 262)], fill=(34, 197, 94), outline=(187, 247, 208), width=2)
    elif t_idx in (3, 5, 6):
        # Chorraha va yo'l chiziqlari diagrammasi
        d.rectangle([(70, 110), (W - 70, 220)], fill=(51, 65, 85))
        d.rectangle([(cx - 58, 36), (cx + 58, 294)], fill=(51, 65, 85))
        for x in range(85, W - 85, 36):
            d.line([(x, 165), (min(x + 20, W - 85), 165)], fill=(248, 250, 252), width=4)
        for y in range(48, 285, 34):
            d.line([(cx, y), (cx, min(y + 18, 285))], fill=(248, 250, 252), width=4)
        # Avtomobil A va B
        d.rounded_rectangle([(cx + 8, 200), (cx + 46, 256)], radius=8, fill=(59, 130, 246), outline=(255, 255, 255), width=2)
        d.rounded_rectangle([(125, 124), (185, 158)], radius=8, fill=(245, 158, 11), outline=(255, 255, 255), width=2)
        d.text((cx + 21, 214), "A", fill=(255, 255, 255), font=f_med)
        d.text((147, 128), "B", fill=(17, 24, 39), font=f_med)
    elif t_idx == 2 or badge.startswith("SPD"):
        # Tezlik cheklovi doirasi
        spd_txt = badge.replace("SPD_", "") if "SPD_" in badge else "60"
        d.ellipse([(cx - 102, cy - 102), (cx + 102, cy + 102)], fill=(255, 255, 255), outline=(220, 38, 38), width=20)
        d.text((cx - 34, cy - 30), spd_txt[:3], fill=(15, 23, 42), font=f_big)
    elif badge == "STOP":
        # STOP belgisi
        pts = [(cx - 42, cy - 95), (cx + 42, cy - 95), (cx + 95, cy - 42), (cx + 95, cy + 42),
               (cx + 42, cy + 95), (cx - 42, cy + 95), (cx - 95, cy + 42), (cx - 95, cy - 42)]
        d.polygon(pts, fill=(220, 38, 38), outline=(255, 255, 255))
        d.text((cx - 66, cy - 28), "STOP", fill=(255, 255, 255), font=f_big)
    elif t_idx in (4, 9, 10):
        # Ogohlantiruvchi uchburchak / ko'k piyoda belgisi
        if t_idx == 4:
            d.rounded_rectangle([(cx - 92, cy - 92), (cx + 92, cy + 92)], radius=16, fill=(37, 99, 235), outline=(255, 255, 255), width=5)
            d.polygon([(cx, cy - 62), (cx + 62, cy + 52), (cx - 62, cy + 52)], fill=(255, 255, 255))
            d.text((cx - 12, cy - 4), "!", fill=(15, 23, 42), font=f_big)
        else:
            d.polygon([(cx, cy - 96), (cx + 102, cy + 82), (cx - 102, cy + 82)], fill=(254, 249, 195), outline=(220, 38, 38))
            d.line([(cx, cy - 96), (cx + 102, cy + 82), (cx - 102, cy + 82), (cx, cy - 96)], fill=(220, 38, 38), width=14)
            mark = "+" if t_idx == 9 else "!"
            d.text((cx - 14, cy - 12), mark, fill=(15, 23, 42), font=f_big)
    else:
        # Taqiqlovchi / asosiy yo'l belgisi
        d.ellipse([(cx - 100, cy - 100), (cx + 100, cy + 100)], fill=(255, 255, 255), outline=(220, 38, 38), width=18)
        d.line([(cx - 64, cy - 64), (cx + 64, cy + 64)], fill=(220, 38, 38), width=14)

    # Pastki ma'lumot paneli
    d.rounded_rectangle([(34, 310), (W - 34, H - 28)], radius=14, fill=(30, 41, 59))
    d.text((54, 324), f"Savol #{q_id}  |  {topic_name}", fill=(248, 250, 252), font=f_med)
    short_q = (question_text or "Yo'l harakati qoidalari bo'yicha tasvirli vaziyat")[:56]
    d.text((54, 360), short_q, fill=(148, 163, 184), font=f_sm)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=88)
    return buf.getvalue()


class PravaService:
    """Haydovchilik guvohnomasi imtihon tizimi va statistikasi."""

    def __init__(self):
        self.total_questions = 1235
        self.total_bilets = 125
        self.exam_rules = {"n": 20, "min": 25, "err": 2}
        self.user_stats: Dict[int, Dict[str, Any]] = {}
        self.user_exams: Dict[int, Dict[str, Any]] = {}

        # 1235 ta savolni to'liq shakllantirish
        self._all_questions: List[Dict[str, Any]] = []
        self._init_question_bank()
        self._load_stats()

    def _init_question_bank(self):
        """Barcha 12 mavzu va 125 bilet bo'ylab to'liq savollar bazasini shakllantirish."""
        by_topic: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(len(TOPICS_LIST))}
        for q in SEED_QUESTIONS:
            by_topic[int(q["t"]) % len(TOPICS_LIST)].append(q)

        for i in range(1, self.total_questions + 1):
            topic_idx = (i - 1) % len(TOPICS_LIST)
            topic_pool = by_topic[topic_idx] or SEED_QUESTIONS
            cycle_idx = (i - 1) // len(TOPICS_LIST)
            base = topic_pool[cycle_idx % len(topic_pool)]
            bilet_num = ((i - 1) // 10) + 1
            # Har bir savol matni toza (soxta #123 yorliqlarisiz) saqlanadi
            has_img = bool(base.get("sign")) or (i % 2 == 1) or (i % 4 == 0)
            q_obj = {
                "id": i,
                "t": topic_idx,
                "b": bilet_num,
                "sign": base.get("sign", ""),
                "q": base["q"],
                "o": list(base["o"]),
                "a": base["a"],
                "img": f"prava/{i}.webp" if has_img else None,
            }
            self._all_questions.append(q_obj)

    def _load_stats(self) -> None:
        """Foydalanuvchilar Prava statistikasini JSON fayldan yuklash."""
        with _PRAVA_LOCK:
            if not _PRAVA_STATS_PATH.exists():
                return
            try:
                with open(_PRAVA_STATS_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    for uid_str, rec in raw.items():
                        if not str(uid_str).lstrip("-").isdigit() or not isinstance(rec, dict):
                            continue
                        uid = int(uid_str)
                        bilet_scores = {
                            int(k): int(v)
                            for k, v in (rec.get("bilet_scores") or {}).items()
                            if str(k).isdigit()
                        }
                        self.user_stats[uid] = {
                            "solved_ids": set(int(x) for x in rec.get("solved_ids", [])),
                            "bad_ids": set(int(x) for x in rec.get("bad_ids", [])),
                            "bilet_scores": bilet_scores,
                            "streak": int(rec.get("streak", 1)),
                            "exams_taken": int(rec.get("exams_taken", 0)),
                            "exams_passed": int(rec.get("exams_passed", 0)),
                            "last_active": float(rec.get("last_active", time.time())),
                        }
            except Exception as e:
                logger.warning(f"Prava statistikasini o'qishda xatolik: {e}")

    def _save_stats(self) -> None:
        """Foydalanuvchilar Prava statistikasini JSON faylga atomik saqlash."""
        with _PRAVA_LOCK:
            _PRAVA_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
            serializable = {}
            for uid, ud in self.user_stats.items():
                serializable[str(uid)] = {
                    "solved_ids": sorted(int(x) for x in ud.get("solved_ids", set())),
                    "bad_ids": sorted(int(x) for x in ud.get("bad_ids", set())),
                    "bilet_scores": {str(k): int(v) for k, v in ud.get("bilet_scores", {}).items()},
                    "streak": int(ud.get("streak", 1)),
                    "exams_taken": int(ud.get("exams_taken", 0)),
                    "exams_passed": int(ud.get("exams_passed", 0)),
                    "last_active": float(ud.get("last_active", time.time())),
                }
            tmp_path = _PRAVA_STATS_PATH.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, _PRAVA_STATS_PATH)

    def _get_user_data(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                "solved_ids": set(),
                "bad_ids": set(),
                "bilet_scores": {},
                "streak": 1,
                "exams_taken": 0,
                "exams_passed": 0,
                "last_active": time.time(),
            }
        return self.user_stats[user_id]

    def generate_question_image_bytes(self, q_id: int) -> bytes:
        """Berilgan savol ID bo'yicha mahalliy WebP rasm baytlarini qaytarish."""
        q_idx = int(q_id) - 1
        if 0 <= q_idx < len(self._all_questions):
            q = self._all_questions[q_idx]
            return generate_question_image_bytes(
                q_id=int(q_id),
                topic_idx=q.get("t"),
                sign_code=q.get("sign", ""),
                question_text=q.get("q", ""),
            )
        return generate_question_image_bytes(q_id=int(q_id))

    get_question_image = generate_question_image_bytes

    def generate_question_svg(self, q_id: int) -> str:
        """Berilgan savol ID bo'yicha SVG yo'l belgisi / sxema qaytarish."""
        q_idx = int(q_id) - 1
        if 0 <= q_idx < len(self._all_questions):
            q = self._all_questions[q_idx]
            return generate_question_svg(int(q_id), topic_idx=q.get("t"), sign_code=q.get("sign", ""))
        return generate_question_svg(int(q_id))

    def get_home_data(self, user_id: int = 0) -> Dict[str, Any]:
        """Foydalanuvchi uchun Prava bosh sahifasi ma'lumotlari."""
        ud = self._get_user_data(user_id) if user_id else {
            "solved_ids": set(), "bad_ids": set(), "bilet_scores": {},
            "streak": 0, "exams_taken": 0, "exams_passed": 0,
        }
        solved_count = len(ud["solved_ids"])
        total = self.total_questions
        ready_pct = min(100, round((solved_count / max(1, total)) * 100))

        bilets = []
        for b in range(1, self.total_bilets + 1):
            score = ud["bilet_scores"].get(b)
            bilets.append({"b": b, "c": 10, "s": score})

        img_count = sum(1 for q in self._all_questions if q.get("img"))

        return {
            "ok": True,
            "total": total,
            "unique_questions": len(SEED_QUESTIONS),
            "solved": solved_count,
            "streak": ud.get("streak", 0),
            "exams": ud.get("exams_taken", 0),
            "passed": ud.get("exams_passed", 0),
            "ready": ready_pct,
            "exam": self.exam_rules,
            "bilets": bilets,
            "topics": TOPICS_LIST,
            "bad": len(ud.get("bad_ids", set())),
            "img": img_count,
        }

    def _sample_unique_questions(self, pool: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
        """Bir to'plam ichida ayni savol matni takrorlanmasligi uchun noyob tanlash."""
        shuffled = list(pool)
        random.shuffle(shuffled)
        picked: List[Dict[str, Any]] = []
        seen_texts: Set[str] = set()
        for q in shuffled:
            if q["q"] not in seen_texts:
                seen_texts.add(q["q"])
                picked.append(q)
                if len(picked) >= count:
                    break
        if len(picked) < count:
            for q in shuffled:
                if q not in picked:
                    picked.append(q)
                    if len(picked) >= count:
                        break
        return picked

    def get_set(self, kind: str, arg: int = 0, user_id: int = 0) -> Dict[str, Any]:
        """Bilet, mavzu, xatolar yoki tasodifiy savollar to'plamini olish."""
        ud = self._get_user_data(user_id) if user_id else None
        selected: List[Dict[str, Any]] = []

        if kind == "b":
            bilet_num = max(1, min(self.total_bilets, int(arg or 1)))
            selected = [q for q in self._all_questions if q.get("b") == bilet_num]
        elif kind == "t":
            topic_idx = int(arg or 0) % len(TOPICS_LIST)
            pool = [q for q in self._all_questions if q.get("t") == topic_idx]
            selected = self._sample_unique_questions(pool, min(20, len(pool))) if pool else []
        elif kind == "bad":
            bad_set = ud["bad_ids"] if ud else set()
            pool = [q for q in self._all_questions if q["id"] in bad_set]
            selected = pool[:20]
        elif kind == "img":
            pool = [q for q in self._all_questions if q.get("img")]
            selected = self._sample_unique_questions(pool, min(20, len(pool))) if pool else []
        else:
            selected = self._sample_unique_questions(self._all_questions, 20)

        safe_qs = [
            {"id": q["id"], "q": q["q"], "o": q["o"], "img": q.get("img")}
            for q in selected
        ]
        return {"ok": True, "qs": safe_qs}

    def check_answer(self, q_id: int, choice: int, user_id: int = 0) -> Dict[str, Any]:
        """Savol javobini tekshirish (server-side verification) va saqlash."""
        if q_id <= 0 or q_id > len(self._all_questions):
            return {"ok": False, "error": "Savol topilmadi"}

        target_q = self._all_questions[q_id - 1]
        correct_idx = target_q["a"]
        is_right = (choice == correct_idx)

        if user_id:
            ud = self._get_user_data(user_id)
            ud["last_active"] = time.time()
            if is_right:
                ud["solved_ids"].add(q_id)
                ud["bad_ids"].discard(q_id)
            else:
                ud["bad_ids"].add(q_id)
            self._save_stats()

        return {"ok": True, "a": correct_idx, "right": is_right}

    def save_bilet_score(self, bilet_num: int, score: int, user_id: int = 0) -> Dict[str, Any]:
        """Bilet natijasini saqlash."""
        if user_id and 1 <= bilet_num <= self.total_bilets:
            ud = self._get_user_data(user_id)
            ud["bilet_scores"][bilet_num] = max(0, min(10, score))
            ud["last_active"] = time.time()
            self._save_stats()
        return {"ok": True}

    def start_exam(self, user_id: int = 0) -> Dict[str, Any]:
        """20 ta takrorlanmaydigan savoldan iborat rasmiy imtihonni boshlash."""
        qs_pool = self._sample_unique_questions(self._all_questions, 20)
        now_ms = int(time.time() * 1000)
        duration_ms = 25 * 60 * 1000
        ends_ms = now_ms + duration_ms

        exam_state = {
            "user_id": user_id,
            "t0": time.time(),
            "ends_ms": ends_ms,
            "qs": qs_pool,
            "ans": {},
            "err": 0,
            "res": None,
        }
        self.user_exams[user_id] = exam_state

        safe_qs = [
            {"id": q["id"], "q": q["q"], "o": q["o"], "img": q.get("img")}
            for q in qs_pool
        ]
        return {"ok": True, "qs": safe_qs, "ends": ends_ms, "max_err": self.exam_rules["err"]}

    def answer_exam_question(
        self,
        q_idx: int = 0,
        choice: int = -1,
        user_id: int = 0,
        question_idx: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Imtihon savoliga berilgan javobni tekshirish."""
        if question_idx is not None:
            q_idx = question_idx
        exam = self.user_exams.get(user_id)
        if not exam:
            return {"ok": False, "error": "no_exam"}
        if q_idx < 0 or q_idx >= len(exam["qs"]):
            return {"ok": False, "error": "invalid_index"}

        q = exam["qs"][q_idx]
        correct_idx = q["a"]
        is_right = (choice == correct_idx)

        if q_idx not in exam["ans"]:
            exam["ans"][q_idx] = {"c": choice, "a": correct_idx, "right": is_right}
            if not is_right:
                exam["err"] += 1
                if user_id:
                    self._get_user_data(user_id)["bad_ids"].add(q["id"])
            elif user_id:
                self._get_user_data(user_id)["solved_ids"].add(q["id"])

        err_count = exam["err"]
        max_err = self.exam_rules["err"]
        result = None

        if err_count > max_err:
            sec_spent = int(time.time() - exam["t0"])
            wrong_list = [{"id": exam["qs"][k]["id"], "k": k} for k, a in exam["ans"].items() if not a["right"]]
            result = {
                "finished": True,
                "passed": False,
                "reason": "errors",
                "correct": sum(1 for a in exam["ans"].values() if a["right"]),
                "err": err_count,
                "n": len(exam["qs"]),
                "sec": sec_spent,
                "wrong": wrong_list,
            }
            exam["res"] = result
            if user_id:
                ud = self._get_user_data(user_id)
                ud["exams_taken"] += 1
                self._save_stats()

        elif len(exam["ans"]) == len(exam["qs"]):
            sec_spent = int(time.time() - exam["t0"])
            correct_cnt = sum(1 for a in exam["ans"].values() if a["right"])
            passed = (err_count <= max_err)
            wrong_list = [{"id": exam["qs"][k]["id"], "k": k} for k, a in exam["ans"].items() if not a["right"]]
            result = {
                "finished": True,
                "passed": passed,
                "reason": "completed",
                "correct": correct_cnt,
                "err": err_count,
                "n": len(exam["qs"]),
                "sec": sec_spent,
                "wrong": wrong_list,
            }
            exam["res"] = result
            if user_id:
                ud = self._get_user_data(user_id)
                ud["exams_taken"] += 1
                if passed:
                    ud["exams_passed"] += 1
                self._save_stats()
        elif user_id:
            self._save_stats()

        return {"ok": True, "a": correct_idx, "right": is_right, "err": err_count, "result": result}

    def finish_exam(self, user_id: int = 0) -> Dict[str, Any]:
        """Imtihonni vaqtidan oldin yoki vaqt tugashi bilan yakunlash."""
        exam = self.user_exams.get(user_id)
        if not exam:
            return {
                "ok": True, "finished": True, "passed": False, "reason": "quit",
                "correct": 0, "err": 0, "n": 20, "sec": 0, "wrong": [],
            }

        sec_spent = int(time.time() - exam["t0"])
        ans_map = exam.get("ans", {})
        correct_cnt = sum(1 for a in ans_map.values() if a["right"])
        err_count = exam.get("err", 0)
        max_err = self.exam_rules["err"]
        passed = (len(ans_map) == len(exam["qs"])) and (err_count <= max_err)
        wrong_list = [{"id": exam["qs"][k]["id"], "k": k} for k, a in ans_map.items() if not a["right"]]

        res = {
            "ok": True,
            "finished": True,
            "passed": passed,
            "reason": "time" if sec_spent >= 1500 else "quit" if len(ans_map) < 20 else "completed",
            "correct": correct_cnt,
            "err": err_count,
            "n": len(exam["qs"]),
            "sec": sec_spent,
            "wrong": wrong_list,
        }
        exam["res"] = res
        if user_id:
            ud = self._get_user_data(user_id)
            ud["exams_taken"] += 1
            if passed:
                ud["exams_passed"] += 1
            self._save_stats()
        return res

    answer_exam = answer_exam_question


prava_service = PravaService()
