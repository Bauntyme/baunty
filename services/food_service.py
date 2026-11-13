"""
Oshxona & Retseptlar (Food) Backend Xizmati - Bauntys (@BauntyCinemabot)
20 ta haqiqiy O'zbek va Jahon oshxonasi retseptlari, kunlik tasodifiy tanlov (g'ildirak),
sevimlilar va tayyorlashlar hisobi JSON bazada saqlanadi.
"""
import os
import json
import random
import threading
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

_FOOD_LOCK = threading.RLock()
_FOOD_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "food_state.json",
)

RECIPES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "t": "Toshkent choyxona oshi",
        "e": "🍛",
        "c": "#F59E0B",
        "k": "milliy",
        "ml": "ld",
        "mn": 85,
        "lv": 2,
        "sv": 6,
        "d": "Devzira yoki lazer guruch, sariq sabzi va zira bilan qozonda damlanadigan haqiqiy o'zbek oshi.",
        "tip": "Guruchni solishdan avval iliq tuzli suvda 30 daqiqa ivitib qo'ysangiz, donalari ezilmaydi va uzun pishadi.",
        "ck": 42,
        "ing": [
            ["Qo'y yoki mol go'shti", 700, "g"],
            ["Guruch (Lazer/Devzira)", 800, "g"],
            ["Sariq sabzi", 800, "g"],
            ["Piyoz", 250, "g"],
            ["O'simlik yog'i", 180, "ml"],
            ["Sarimsoq piyoz", 2, "bosh"],
            ["No'xat (ivitilgan)", 100, "g"],
            ["Zira va tuz", None, "ta'bga ko'ra"],
        ],
        "st": [
            {"t": "Qozonda yog'ni qizdirib, parraklangan piyozni tillarang bo'lguncha qovuring.", "m": 7},
            {"t": "Katta bo'laklangan go'shtni solib, suvi qochib qizarguncha baland olovda qovuring.", "m": 10},
            {"t": "Somoncha to'g'ralgan sabzini solib, yumshaguncha aralashtirib pishiring.", "m": 10},
            {"t": "Suv, no'xat, tuz va sarimsoqni solib zirvakni o'rta olovda qaynatib oling.", "m": 25},
            {"t": "Yuvilgan guruchni tekis yoyib, suvini shimdirib olgach qopqog'ini yopib damlang.", "m": 22},
        ],
    },
    {
        "id": 2,
        "t": "Qiyma va piyozli manti",
        "e": "🥟",
        "c": "#FB923C",
        "k": "milliy",
        "ml": "ld",
        "mn": 65,
        "lv": 2,
        "sv": 4,
        "d": "Yupqa xamir ichida qo'lda mayda to'g'ralgan sersuv go'sht va ko'p piyozli bug'da pishgan manti.",
        "tip": "Go'shtni go'sht qiymalagichdan emas, pichoqda mayda to'g'rasangiz, manti ichidagi shira saqlanib qoladi.",
        "ck": 28,
        "ing": [
            ["Un", 500, "g"],
            ["Mol go'shti (yog'liroq)", 500, "g"],
            ["Piyoz", 450, "g"],
            ["Tuxum", 1, "dona"],
            ["Suv (xamir uchun)", 200, "ml"],
            ["Zira, murch va tuz", None, "ta'bga ko'ra"],
        ],
        "st": [
            {"t": "Tuxum, tuz, suv va un bilan qattiqroq xamir qorib, 20 daqiqa tindiring.", "m": 20},
            {"t": "Mayda to'g'ralgan go'sht, yupqa piyoz va ziravorlarni aralashtirib nachinka tayyorlang.", "m": 10},
            {"t": "Xamirni yupqa yoyib kvadratlarga kesing va manti tugib chiqing.", "m": 15},
            {"t": "Yog'langan qasqon qavatlariga terib, qaynab turgan suv ustida bug'da pishiring.", "m": 40},
        ],
    },
    {
        "id": 3,
        "t": "Qatlama somsa",
        "e": "🥐",
        "c": "#D97706",
        "k": "milliy",
        "ml": "bld",
        "mn": 70,
        "lv": 3,
        "sv": 6,
        "d": "Qarsildoq qavatli xamir ichida shirador go'sht va zira hidli pech somsasi.",
        "tip": "Xamirga surtiladigan sariyog' xona haroratida yumshagan bo'lsa, qavatlari yanada chiroyli ajraladi.",
        "ck": 34,
        "ing": [
            ["Un", 550, "g"],
            ["Sariyog' yoki margarin", 150, "g"],
            ["Mol go'shti", 400, "g"],
            ["Piyoz", 350, "g"],
            ["Kunjut", 15, "g"],
            ["Tuxum sarig'i", 1, "dona"],
        ],
        "st": [
            {"t": "Xamir qorib yupqa yoying, sariyog' surtib rulet qilib o'rang va muzlatkichga qo'ying.", "m": 25},
            {"t": "Go'sht va piyozni mayda kubik shaklida to'g'rab ziravorlar bilan aralashtiring.", "m": 10},
            {"t": "Xamirni bo'laklarga bo'lib yoying, nachinka solib uchburchak tuging.", "m": 15},
            {"t": "Tuxum sarig'i va kunjut sepib 200°C qizigan duxovkada qizarguncha pishiring.", "m": 28},
        ],
    },
    {
        "id": 4,
        "t": "Uyg'urcha cho'zma lag'mon",
        "e": "🍜",
        "c": "#EF4444",
        "k": "milliy",
        "ml": "ld",
        "mn": 60,
        "lv": 2,
        "sv": 4,
        "d": "Xushbo'y sabzavotli qayla (say) va qaynoq lag'mon ugrasi uyg'unlashgan to'yimli taom.",
        "tip": "Say tayyorlashda sabzavotlarni baland olovda tez qovurish ularga xushta'm qarsildoq sifat beradi.",
        "ck": 23,
        "ing": [
            ["Lag'mon ugrasi (tayyor yoki uy)", 500, "g"],
            ["Mol go'shti", 400, "g"],
            ["Bulg'or qalampiri", 2, "dona"],
            ["Pomidor", 2, "dona"],
            ["Selder va jandiq", 150, "g"],
            ["Sarimsoq va soya sousi", 30, "ml"],
        ],
        "st": [
            {"t": "Go'shtni yupqa uzunchoq qilib kesib, qizigan yog'da qovuring.", "m": 8},
            {"t": "Piyoz, pomidor, bulg'or qalampiri va selderni ketma-ket solib baland olovda aralashtiring.", "m": 10},
            {"t": "Ozroq suv va soya sousi qo'shib qaylani past olovda dimlang.", "m": 12},
            {"t": "Ugrani tuzli suvda qaynatib oling va ustiga qaynoq say quyib torting.", "m": 8},
        ],
    },
    {
        "id": 5,
        "t": "Toshkent norini",
        "e": "🍝",
        "c": "#CA8A04",
        "k": "milliy",
        "ml": "ld",
        "mn": 90,
        "lv": 3,
        "sv": 5,
        "d": "Qaynatilgan go'sht sho'rvasida pishgan mayda to'g'ralgan xamir va qazi bilan bayramona taom.",
        "tip": "Xamir bo'laklari yopishib qolmasligi uchun pishgach zudlik bilan go'sht yog'i surtib sovuting.",
        "ck": 19,
        "ing": [
            ["Qaynatilgan mol go'shti", 500, "g"],
            ["Qazi (xohishga ko'ra)", 200, "g"],
            ["Un", 450, "g"],
            ["Tuxum", 1, "dona"],
            ["Zira va murch", None, "ta'bga ko'ra"],
        ],
        "st": [
            {"t": "Go'shtni tuzli suvda yumshaguncha qaynatib oling.", "m": 50},
            {"t": "Yupqa yoyilgan xamirni sho'rvada 2-3 daqiqa qaynatib yog'lab sovuting.", "m": 15},
            {"t": "Xamir va go'shtni ingichka somoncha qilib mayda to'g'rang.", "m": 20},
            {"t": "Zira bilan aralashtirib ustiga qazi va piyoz qo'yib dasturxonga torting.", "m": 0},
        ],
    },
    {
        "id": 6,
        "t": "Kichik chuchvara sho'rva",
        "e": "🥣",
        "c": "#F97316",
        "k": "milliy",
        "ml": "ld",
        "mn": 50,
        "lv": 2,
        "sv": 4,
        "d": "Qaynoq sabzavotli bulyonda pishirilgan nafis go'shtli chuchvaralar, smetana yoki qatiq bilan.",
        "tip": "Chuchvarani qozonga solishdan oldin dasturxon ustida 10 daqiqa quritib olsangiz, sho'rvada yorilmaydi.",
        "ck": 21,
        "ing": [
            ["Un", 350, "g"],
            ["Qiyma go'sht", 300, "g"],
            ["Piyoz", 2, "dona"],
            ["Pomidor va sabzi", 200, "g"],
            ["Kashnich va qatiq", None, "bezash uchun"],
        ],
        "st": [
            {"t": "Qattiq xamir qorib 15 daqiqa dam bering, qiymaga piyoz va tuz aralashtiring.", "m": 15},
            {"t": "Mayda kvadratlar kesib nafis chuchvaralar tugib chiqing.", "m": 20},
            {"t": "Sabzavotli qaynatma tayyorlab, chuchvaralarni solib yuzaga chiqquncha pishiring.", "m": 10},
        ],
    },
    {
        "id": 7,
        "t": "Mastava — guruchli sho'rva",
        "e": "🍲",
        "c": "#EA580C",
        "k": "milliy",
        "ml": "ld",
        "mn": 45,
        "lv": 1,
        "sv": 4,
        "d": "Go'sht, sabzi, kartoshka va guruchdan tayyorlanadigan iliq va hazmi yengil uy sho'rvasi.",
        "tip": "Oxirida bir qoshiq qatiq va mayda to'g'ralgan rayhon qo'shsangiz ta'mi yanada boyiydi.",
        "ck": 31,
        "ing": [
            ["Mol go'shti", 350, "g"],
            ["Guruch", 150, "g"],
            ["Kartoshka", 2, "dona"],
            ["Sabzi va pomidor", 2, "dona"],
            ["Qatiq va ko'kat", None, "tortishda"],
        ],
        "st": [
            {"t": "Go'sht, piyoz, pomidor va sabzini kubik kesib qozonda qovuring.", "m": 12},
            {"t": "Suv quyib qaynab chiqqach, kartoshka va guruchni soling.", "m": 25},
            {"t": "Guruch pishgach olovni o'chiring va ko'katlar sepib 5 daqiqa tindiring.", "m": 5},
        ],
    },
    {
        "id": 8,
        "t": "Dimlama — qozonda sabzavotli go'sht",
        "e": "🥘",
        "c": "#16A34A",
        "k": "milliy",
        "ml": "ld",
        "mn": 75,
        "lv": 1,
        "sv": 6,
        "d": "O'z suvida past olovda dimlab pishiriladigan go'sht, karam, kartoshka va shirin sabzavotlar.",
        "tip": "Qozon qopqog'ini karam barglari bilan yopsangiz bug' chiqmaydi va taom hidi saqlanadi.",
        "ck": 26,
        "ing": [
            ["Qo'y yoki mol go'shti", 700, "g"],
            ["Kartoshka", 600, "g"],
            ["Karam", 400, "g"],
            ["Sabzi, pomidor, baqlajon", 500, "g"],
            ["Zira va sarimsoq", None, "ta'bga ko'ra"],
        ],
        "st": [
            {"t": "Sovuq qozon tagiga yog' va go'sht bo'laklarini qavatlab tering.", "m": 5},
            {"t": "Ustidan piyoz, sabzi, pomidor, kartoshka va karam barglarini joylashtiring.", "m": 10},
            {"t": "Qopqog'ini zich yopib, dastlab baland, keyin eng past olovda dimlang.", "m": 55},
        ],
    },
    {
        "id": 9,
        "t": "Qozonkabob",
        "e": "🍖",
        "c": "#B91C1C",
        "k": "milliy",
        "ml": "ld",
        "mn": 60,
        "lv": 2,
        "sv": 4,
        "d": "Yog'da qizartirilgan qarsildoq kartoshka va yumshoq qovurilgan qo'y qovurg'alari.",
        "tip": "Kartoshkani avval butunligicha qizdirilgan yog'da qizartirib olib, keyin go'sht ustiga tering.",
        "ck": 37,
        "ing": [
            ["Qo'y go'shti (qovurg'a)", 700, "g"],
            ["O'rtacha kartoshka", 600, "g"],
            ["Yog'", 200, "ml"],
            ["Piyoz (uzukcha)", 150, "g"],
            ["Zira va kashnich urug'i", None, "ta'bga ko'ra"],
        ],
        "st": [
            {"t": "Go'sht bo'laklariga tuz va kashnich urug'i surtib 20 daqiqa marinadlang.", "m": 20},
            {"t": "Qizigan yog'da kartoshkalarni tillarang qobig'i chiqquncha qovurib oling.", "m": 12},
            {"t": "Go'shtni qovurib qizartiring, kartoshkani ustiga terib past olovda dimlang.", "m": 30},
        ],
    },
    {
        "id": 10,
        "t": "To'rt burchakli kartoshkali xonim",
        "e": "🥟",
        "c": "#EAB308",
        "k": "milliy",
        "ml": "bld",
        "mn": 55,
        "lv": 1,
        "sv": 4,
        "d": "Yupqa rulet xamirda bug'da pishgan kartoshka, piyoz va tomat qaylasi bilan oson taom.",
        "tip": "Ruletni bug'dan olgandan keyin ustiga tomat-sarimsoq qaylasini issiqligida surting.",
        "ck": 18,
        "ing": [
            ["Un", 400, "g"],
            ["Kartoshka", 600, "g"],
            ["Piyoz", 300, "g"],
            ["Tomat pastasi", 40, "g"],
        ],
        "st": [
            {"t": "Elastik xamir qorib tindiring, kartoshka va piyozni mayda to'g'rang.", "m": 15},
            {"t": "Xamirni katta doira qilib yoyib, nachinka solib rulet shaklida o'rang.", "m": 10},
            {"t": "Qasqonda bug'da pishiring va ustiga qovurilgan tomat qaylasi quyib kesing.", "m": 35},
        ],
    },
    {
        "id": 11,
        "t": "Turkcha Menemen (Nonushta)",
        "e": "🍳",
        "c": "#DC2626",
        "k": "jahon",
        "ml": "b",
        "mn": 15,
        "lv": 1,
        "sv": 2,
        "d": "Pomidor, ko'k qalampir va yumshoq pishgan tuxumdan iborat 15 daqiqalik issiq nonushta.",
        "tip": "Pomidor po'stlog'ini archib maydalasangiz, sous ipakdek silliq chiqadi.",
        "ck": 24,
        "ing": [
            ["Tuxum", 4, "dona"],
            ["Shirin pomidor", 3, "dona"],
            ["Ko'k achchiq/shirin qalampir", 2, "dona"],
            ["Sariyog'", 25, "g"],
        ],
        "st": [
            {"t": "Tovada sariyog' eritib mayda to'g'ralgan qalampirni yumshating.", "m": 3},
            {"t": "Pomidorni qo'shib qayla quyuqlashguncha dimlang.", "m": 6},
            {"t": "Chaqilgan tuxumlarni solib muloyim aralashtiring va issiq non bilan torting.", "m": 3},
        ],
    },
    {
        "id": 12,
        "t": "Tvorogli mayin sirniki",
        "e": "🥞",
        "c": "#F59E0B",
        "k": "jahon",
        "ml": "b",
        "mn": 20,
        "lv": 1,
        "sv": 2,
        "d": "Tashqarisi qizargan, ichi yumshoq va oqsilga boy tonggi tvorogli pishiriq.",
        "tip": "Tvorog nam bo'lsa elakdan o'tkazing va unni juda ko'p solmang — shunda mayin chiqadi.",
        "ck": 29,
        "ing": [
            ["Tvorog (quruqroq)", 350, "g"],
            ["Tuxum sarig'i", 1, "dona"],
            ["Un", 50, "g"],
            ["Shakar va vanilin", 30, "g"],
        ],
        "st": [
            {"t": "Tvorog, tuxum sarig'i, shakar va unni silliq massa bo'lguncha aralashtiring.", "m": 5},
            {"t": "Shayba shaklida yasab unga belab oling.", "m": 5},
            {"t": "O'rta olovda ikki tomonini qizarguncha qovuring va asal bilan torting.", "m": 8},
        ],
    },
    {
        "id": 13,
        "t": "Sezar salati (tovuqli)",
        "e": "🥗",
        "c": "#22C55E",
        "k": "salat",
        "ml": "ld",
        "mn": 25,
        "lv": 1,
        "sv": 2,
        "d": "Qovurilgan tovuq ko'kragi, aysberg barglari, suxarik va parmezan sousli mashhur salat.",
        "tip": "Non kubiklarini sarimsoqli zaytun yog'ida quritib olsangiz, salatda tez yumshab qolmaydi.",
        "ck": 33,
        "ing": [
            ["Tovuq filesi", 250, "g"],
            ["Aysberg yoki Romen bargi", 150, "g"],
            ["Cherri pomidor", 100, "g"],
            ["Parmezan pishlog'i", 40, "g"],
            ["Sezar sousi va suxarik", 60, "g"],
        ],
        "st": [
            {"t": "Tovuq filesini ziravorlar bilan grilda yoki tovada qovurib tilimlarga bo'ling.", "m": 10},
            {"t": "Salat barglarini qo'lda yirtib, sous bilan yengil aralashtiring.", "m": 4},
            {"t": "Tovuq, cherri, suxarik va parmezan qirindisini ustiga terib torting.", "m": 0},
        ],
    },
    {
        "id": 14,
        "t": "Toshkentcha Achichuk salati",
        "e": "🍅",
        "c": "#EF4444",
        "k": "salat",
        "ml": "ld",
        "mn": 10,
        "lv": 1,
        "sv": 4,
        "d": "Osh va kaboblarning ajralmas hamrohi: yupqa pomidor, qizil piyoz va rayhon salati.",
        "tip": "Tuzni dasturxonga tortishdan aynan 2 daqiqa oldin seping, shunda pomidor suvi chiqib ketmaydi.",
        "ck": 45,
        "ing": [
            ["Pishgan qizil pomidor", 4, "dona"],
            ["Oq yoki qizil piyoz", 1, "dona"],
            ["Achchiq qalampir (xohishga)", 1, "dona"],
            ["Rayhon va tuz", None, "ta'bga ko'ra"],
        ],
        "st": [
            {"t": "Piyozni iloji boricha yupqa yarim halqa qilib to'g'rang va sovuq suvda chaying.", "m": 3},
            {"t": "Pomidorni yupqa tilimlarga bo'lib piyoz bilan aralashtiring.", "m": 4},
            {"t": "Rayhon barglari va tuz sepib darhol dasturxonga qo'ying.", "m": 0},
        ],
    },
    {
        "id": 15,
        "t": "Asalli Medovik torti",
        "e": "🍰",
        "c": "#D97706",
        "k": "shirin",
        "ml": "bld",
        "mn": 95,
        "lv": 3,
        "sv": 8,
        "d": "Tabiiy asal hidli yupqa korjlar va qaymoqli smetana kremi singib ketgan klassik tort.",
        "tip": "Tort yig'ilgach kamida 6 soat muzlatkichda tursa, korjlar kremni mukammal shimib oladi.",
        "ck": 27,
        "ing": [
            ["Tabiiy asal", 100, "g"],
            ["Sariyog'", 120, "g"],
            ["Un", 420, "g"],
            ["Tuxum", 3, "dona"],
            ["Smetana (25%+) va qaymoq", 600, "g"],
            ["Shakar upasi", 160, "g"],
        ],
        "st": [
            {"t": "Suv hammomida asal, sariyog' va shakarni eritib, soda solib ko'pirtiring.", "m": 10},
            {"t": "Tuxum va un qo'shib yumshoq xamir qoring, 8 ta zuvalaga bo'lib pishiring.", "m": 35},
            {"t": "Smetana va shakar upasini mikserda ko'pirtirib krem tayyorlang.", "m": 8},
            {"t": "Korjlarni kremlab yig'ing va chetidagi uvoqlari bilan bezating.", "m": 15},
        ],
    },
    {
        "id": 16,
        "t": "Qarsildoq Napoleon torti",
        "e": "🎂",
        "c": "#FBBF24",
        "k": "shirin",
        "ml": "ld",
        "mn": 110,
        "lv": 3,
        "sv": 10,
        "d": "Qavatma xamir korjlari va vanilli qaynatma plombir kremidan tayyorlangan shohona desert.",
        "tip": "Krem sovuganda ustiga oziq-ovqat plyonkasini tekkizib yopsangiz, qobiq bog'lamaydi.",
        "ck": 16,
        "ing": [
            ["Qavatma xamir (muzlatilgan)", 800, "g"],
            ["Sut", 750, "ml"],
            ["Sariyog'", 180, "g"],
            ["Tuxum sarig'i", 4, "dona"],
            ["Jo'xori kraxmali va shakar", 200, "g"],
        ],
        "st": [
            {"t": "Sut, tuxum sarig'i, shakar va kraxmaldan quyuq qaynatma krem pishirib sovuting.", "m": 15},
            {"t": "Sovugan kremni ko'pirtirilgan sariyog' bilan birlashtiring.", "m": 6},
            {"t": "Yupqa yoyilgan korjlarni 200°C da qizarguncha pishiring va kremlab taxlang.", "m": 40},
        ],
    },
    {
        "id": 17,
        "t": "Tovuq va qo'ziqorinli Fettuchini Alfredo",
        "e": "🍝",
        "c": "#FDE047",
        "k": "jahon",
        "ml": "ld",
        "mn": 30,
        "lv": 1,
        "sv": 3,
        "d": "Qaymoqli sarimsoq sousida pishirilgan italyan pastasi va qovurilgan tovuq bo'laklari.",
        "tip": "Pasta qaynatilgan suvdan yarim cho'mich sousga qo'shsangiz, qaymoq yaltiroq emulsiya hosil qiladi.",
        "ck": 22,
        "ing": [
            ["Fettuchini makaroni", 300, "g"],
            ["Tovuq ko'kragi", 300, "g"],
            ["Shampinyon qo'ziqorini", 200, "g"],
            ["Qaymoq (20%)", 250, "ml"],
            ["Parmezan pishlog'i", 60, "g"],
        ],
        "st": [
            {"t": "Tovuq va qo'ziqorinni sariyog'da qizartirib qovuring, sarimsoq qo'shing.", "m": 8},
            {"t": "Qaymoq quyib past olovda quyuqlashguncha aralashtiring.", "m": 5},
            {"t": "Al-dente pishgan makaron va parmezanni sous bilan aralashtirib torting.", "m": 9},
        ],
    },
    {
        "id": 18,
        "t": "Uy sharoitida Tovuqli Lavash",
        "e": "🌯",
        "c": "#F97316",
        "k": "jahon",
        "ml": "bld",
        "mn": 25,
        "lv": 1,
        "sv": 3,
        "d": "Yupqa lavash noni ichida qovurilgan tovuq, qarsildoq chips, bodring va sarimsoqli sous.",
        "tip": "O'ralgan lavashni quruq gril tovasida 1 daqiqa bosib qizdirib olsangiz, tashqarisi qarsildoq bo'ladi.",
        "ck": 39,
        "ing": [
            ["Yupqa lavash", 3, "varaq"],
            ["Tovuq filesi", 350, "g"],
            ["Pomidor va bodring", 2, "dona"],
            ["Smetana va mayonez sousi", 100, "g"],
        ],
        "st": [
            {"t": "Tovuqni ziravorlar bilan ingichka to'g'rab qovuring.", "m": 10},
            {"t": "Lavashga sous surtib, tovuq va sabzavotlarni zich o'rang.", "m": 6},
            {"t": "Quruq tovada ikki tomonini 2 daqiqa qizartirib oling.", "m": 4},
        ],
    },
    {
        "id": 19,
        "t": "Banan va jo'xori pankeyklari",
        "e": "🥞",
        "c": "#FBBF24",
        "k": "shirin",
        "ml": "b",
        "mn": 15,
        "lv": 1,
        "sv": 2,
        "d": "Shakar qo'shilmagan, pishgan banan va suli yormasidan foydali energiyali tonggi quymoq.",
        "tip": "Qanchalik pishgan banan ishlatsangiz, pankeyklar shunchalik shirin va xushbo'y chiqadi.",
        "ck": 17,
        "ing": [
            ["Pishgan banan", 2, "dona"],
            ["Tuxum", 2, "dona"],
            ["Suli yormasi (maydalangan)", 80, "g"],
            ["Sut", 60, "ml"],
        ],
        "st": [
            {"t": "Banan, tuxum, suli va sutni blenderda silliq bo'lguncha aralashtiring.", "m": 3},
            {"t": "Yog'siz yopishmaydigan tovada pufakchalar chiqquncha ikki tomondan pishiring.", "m": 10},
        ],
    },
    {
        "id": 20,
        "t": "Yunoncha zaytunli salat",
        "e": "🥗",
        "c": "#10B981",
        "k": "salat",
        "ml": "bld",
        "mn": 12,
        "lv": 1,
        "sv": 3,
        "d": "Yirik to'g'ralgan yangi sabzavotlar, Feta pishlog'i, qora zaytun va zaytun yog'ili vitaminli salat.",
        "tip": "Feta pishlog'ini oxirida ustiga kubik qilib qo'ysangiz, ezilib salat ko'rinishini buzmaydi.",
        "ck": 20,
        "ing": [
            ["Pomidor va bodring", 3, "dona"],
            ["Feta (Brinza) pishlog'i", 150, "g"],
            ["Qora zaytun", 70, "g"],
            ["Zaytun yog'i va oregano", 30, "ml"],
        ],
        "st": [
            {"t": "Sabzavotlarni yirik bo'laklarga to'g'rab chuqur idishga soling.", "m": 6},
            {"t": "Zaytun, limon sharbati, zaytun yog'i va Feta qo'shib ehtiyotkor aralashtiring.", "m": 4},
        ],
    },
]


class FoodService:
    """Retseptlar katalogi, kunlik random tanlov, sevimlilar va tayyorlashlar hisobi."""

    def __init__(self) -> None:
        self._recipes_by_id: Dict[int, Dict[str, Any]] = {int(r["id"]): r for r in RECIPES}

    def _load_state(self) -> Dict[str, Any]:
        with _FOOD_LOCK:
            if not os.path.exists(_FOOD_STATE_PATH):
                return {"users": {}, "cooks": {}}
            try:
                with open(_FOOD_STATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("users", {})
                    data.setdefault("cooks", {})
                    return data
            except Exception as e:
                logger.warning(f"Food holatini yuklashda xatolik: {e}")
            return {"users": {}, "cooks": {}}

    def _save_state(self, data: Dict[str, Any]) -> None:
        with _FOOD_LOCK:
            os.makedirs(os.path.dirname(_FOOD_STATE_PATH), exist_ok=True)
            tmp = f"{_FOOD_STATE_PATH}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _FOOD_STATE_PATH)

    def _materialize_recipe(self, base: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(base)
        extra_ck = int(state.get("cooks", {}).get(str(base["id"]), 0) or 0)
        item["ck"] = int(base.get("ck", 0)) + extra_ck
        return item

    def get_catalog(self, user_id: int = 0, category: str = "", meal: str = "", query: str = "") -> Dict[str, Any]:
        """Barcha retseptlarni (ixtiyoriy toifa, vaqt va qidiruv bo'yicha) qaytarish."""
        state = self._load_state()
        cat_clean = (category or "").strip().lower()
        meal_clean = (meal or "").strip().lower()
        q_clean = (query or "").strip().lower()

        items = []
        for r in RECIPES:
            if cat_clean and cat_clean != "all" and r["k"] != cat_clean:
                continue
            if meal_clean and meal_clean not in r["ml"]:
                continue
            if q_clean:
                hay = f"{r['t']} {r['d']} {' '.join(x[0] for x in r['ing'])}".lower()
                if q_clean not in hay:
                    continue
            items.append(self._materialize_recipe(r, state))
        return {"ok": True, "items": items, "total": len(items)}

    def get_recipe(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        """ID bo'yicha bitta retseptni to'liq qaytarish."""
        base = self._recipes_by_id.get(int(recipe_id))
        if not base:
            return None
        state = self._load_state()
        return self._materialize_recipe(base, state)

    def get_random(self, meal: str = "", exclude_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Ovqat vaqti (b/l/d) va chiqarib tashlangan ID lardan tashqari tasodifiy retsept tanlash."""
        state = self._load_state()
        ex_set = {int(x) for x in (exclude_ids or []) if str(x).isdigit()}
        meal_clean = (meal or "").strip().lower()

        pool = [
            r for r in RECIPES
            if (not meal_clean or meal_clean in r["ml"]) and int(r["id"]) not in ex_set
        ]
        if not pool and meal_clean:
            pool = [r for r in RECIPES if meal_clean in r["ml"]]
        if not pool:
            pool = list(RECIPES)

        pick = random.choice(pool)
        return {"ok": True, "r": self._materialize_recipe(pick, state)}

    def get_user_me(self, user_id: int, is_admin: bool = False) -> Dict[str, Any]:
        """Foydalanuvchi sevimli retseptlari ro'yxatini qaytarish."""
        state = self._load_state()
        fav = state.get("users", {}).get(str(user_id), {}).get("fav", [])
        return {"ok": True, "admin": bool(is_admin), "fav": list(fav)}

    def toggle_fav(self, user_id: int, recipe_id: int) -> Dict[str, Any]:
        """Retseptni sevimlilarga qo'shish yoki olib tashlash."""
        rid = int(recipe_id)
        if rid not in self._recipes_by_id:
            return {"ok": False, "error": "not_found"}
        with _FOOD_LOCK:
            state = self._load_state()
            u = state["users"].setdefault(str(user_id), {"fav": []})
            fav = [int(x) for x in u.get("fav", []) if str(x).isdigit()]
            if rid in fav:
                fav = [x for x in fav if x != rid]
                on = False
            else:
                fav.insert(0, rid)
                on = True
            u["fav"] = fav
            self._save_state(state)
        return {"ok": True, "on": on, "fav": fav}

    def mark_cook(self, user_id: int, recipe_id: int) -> Dict[str, Any]:
        """Retsept tayyorlanganligini belgilash va sanog'ini oshirish."""
        rid = int(recipe_id)
        base = self._recipes_by_id.get(rid)
        if not base:
            return {"ok": False, "error": "not_found"}
        with _FOOD_LOCK:
            state = self._load_state()
            cooks = state.setdefault("cooks", {})
            cooks[str(rid)] = int(cooks.get(str(rid), 0) or 0) + 1
            total_ck = int(base.get("ck", 0)) + cooks[str(rid)]
            self._save_state(state)
        return {"ok": True, "ck": total_ck}


food_service = FoodService()
