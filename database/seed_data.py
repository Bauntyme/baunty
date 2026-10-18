"""
Kinolar bazasi uchun boshlang'ich ma'lumotlar (185+ sara film va seriallar).
Lotin va Kirill tillarida to'liq tavsif, janrlar va reytinglar bilan.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Movie
from database.crud import get_total_movies_count, get_movie_by_code

logger = logging.getLogger(__name__)

MOVIES_DATA: List[Dict[str, Any]] = [
    # --- JANGARI VA FANTASTIKA ---
    {"code": "101", "title": "Forsaj 10 (Fast X)", "genres": "Jangari, Sarguzasht, Triller", "year": 2023, "rating": 7.4, "duration": 141, "views_count": 28400, "downloads_count": 9120, "description": "Dominik Toretto va uning oilasi bu safar eng shafqatsiz dushman — Dante Reyes bilan to'qnash keladi.", "file_id": "BAACAgIAAxkBAAIB_forsaj10_vid"},
    {"code": "102", "title": "Avatar 2: Suv yo'li (The Way of Water)", "genres": "Fantastika, Sarguzasht, Jangari", "year": 2022, "rating": 8.1, "duration": 192, "views_count": 34100, "downloads_count": 12450, "description": "Jeyk Salli va Neytiri Pandorada o'z oilasini yangi dushmandan himoya qilish uchun suv qabilasiga boshpana izlab borishadi.", "file_id": "BAACAgIAAxkBAAIB_avatar2_vid"},
    {"code": "103", "title": "Qasoskorlar: Intiho (Avengers: Endgame)", "genres": "Fantastika, Jangari, Sarguzasht", "year": 2019, "rating": 8.7, "duration": 181, "views_count": 52300, "downloads_count": 21300, "description": "Tanos olamning yarmini yo'q qilgandan so'ng, omon qolgan Qasoskorlar vaqt orqali o'tmishga sayohat qilishadi.", "file_id": "BAACAgIAAxkBAAIB_endgame_vid"},
    {"code": "104", "title": "Jon Uik 4 (John Wick: Chapter 4)", "genres": "Jangari, Triller, Kriminal", "year": 2023, "rating": 8.0, "duration": 169, "views_count": 31200, "downloads_count": 11500, "description": "Jon Uik Oliy Kengashga qarshi kurashadi va o'zining ozodligi uchun dunyo bo'ylab eng xavfli qotillar bilan to'qnashadi.", "file_id": "BAACAgIAAxkBAAIB_jw4_vid"},
    {"code": "105", "title": "Oppenheimer", "genres": "Drama, Tarixiy, Biografiya", "year": 2023, "rating": 8.9, "duration": 180, "views_count": 41800, "downloads_count": 14200, "description": "Atom bombasining yaratuvchisi Robert Oppenxaymerning hayoti va Manxetten loyihasi haqidagi epik drama.", "file_id": "BAACAgIAAxkBAAIB_oppenheimer_vid"},
    {"code": "106", "title": "Dyuna 2 (Dune: Part Two)", "genres": "Fantastika, Sarguzasht, Jangari", "year": 2024, "rating": 8.6, "duration": 166, "views_count": 39500, "downloads_count": 13900, "description": "Pol Atreydes va Chani Arrakis cho'llarida ozodlik va intiqom uchun kurash olib borishadi.", "file_id": "BAACAgIAAxkBAAIB_dune2_vid"},
    {"code": "107", "title": "Dedpul va Rosomaxa (Deadpool & Wolverine)", "genres": "Jangari, Komediya, Fantastika", "year": 2024, "rating": 8.2, "duration": 128, "views_count": 48200, "downloads_count": 18100, "description": "Ueyd Uilson va Logan koinotni saqlab qolish uchun aqlbovar qilmas umumiy missiyaga birlashadilar.", "file_id": "BAACAgIAAxkBAAIB_dpwolv_vid"},
    {"code": "108", "title": "Interstellar", "genres": "Fantastika, Drama, Sarguzasht", "year": 2014, "rating": 8.9, "duration": 169, "views_count": 62100, "downloads_count": 27800, "description": "Insoniyatni halokatdan qutqarish uchun koinot tadqiqotchilari yangi yashash sayyorasini topish maqsadida qurt uyasidan o'tishadi.", "file_id": "BAACAgIAAxkBAAIB_interstellar_vid"},
    {"code": "109", "title": "Boshlanish (Inception)", "genres": "Fantastika, Triller, Jangari", "year": 2010, "rating": 8.8, "duration": 148, "views_count": 44300, "downloads_count": 16500, "description": "Dom Kobb tushlar ichida odamlarning maxfiy fikrlarini o'g'irlaydigan eng mohir firibgardir.", "file_id": "BAACAgIAAxkBAAIB_inception_vid"},
    {"code": "110", "title": "Qora Ritsar (The Dark Knight)", "genres": "Jangari, Kriminal, Drama", "year": 2008, "rating": 9.0, "duration": 152, "views_count": 58900, "downloads_count": 24100, "description": "Betmen Gotem shahrini yovuz va aqldan ozgan Joker changalidan saqlab qolishga harakat qiladi.", "file_id": "BAACAgIAAxkBAAIB_darkknight_vid"},
    {"code": "111", "title": "Matritsa (The Matrix)", "genres": "Fantastika, Jangari", "year": 1999, "rating": 8.7, "duration": 136, "views_count": 41200, "downloads_count": 15400, "description": "Neo ismli dasturchi o'zi yashayotgan dunyo robotlar tomonidan yaratilgan virtual illyuziya ekanligini anglab yetadi.", "file_id": "BAACAgIAAxkBAAIB_matrix_vid"},
    {"code": "112", "title": "Gladiator 2", "genres": "Tarixiy, Jangari, Drama", "year": 2024, "rating": 7.8, "duration": 148, "views_count": 29800, "downloads_count": 9400, "description": "Maksiniusning vafotidan so'ng yangi avlod gladiatorlari Rim Kolizeyida shon-sharaf va haqiqat uchun jang qilishadi.", "file_id": "BAACAgIAAxkBAAIB_gladiator2_vid"},
    {"code": "113", "title": "Gladiator", "genres": "Tarixiy, Jangari, Drama", "year": 2000, "rating": 8.5, "duration": 155, "views_count": 47600, "downloads_count": 19200, "description": "Sotqinlik qurboni bo'lgan Rim generali Maksimus gladiatorga aylanadi va imperatorga qarshi kurashadi.", "file_id": "BAACAgIAAxkBAAIB_gladiator1_vid"},
    {"code": "114", "title": "Tomir 2 (Extraction 2)", "genres": "Jangari, Triller", "year": 2023, "rating": 7.9, "duration": 123, "views_count": 27300, "downloads_count": 8900, "description": "Tayler Reyk o'limdan omon qolib, yangi xavfli vazifani — gruzin mafiyasi asiridagi oilani qutqarishni o'z zimmasiga oladi.", "file_id": "BAACAgIAAxkBAAIB_extraction2_vid"},
    {"code": "115", "title": "Tomir (Extraction)", "genres": "Jangari, Triller", "year": 2020, "rating": 7.7, "duration": 116, "views_count": 32100, "downloads_count": 11300, "description": "Yollanma jangchi Hindiston va Bangladesh narkobaronlari to'qnashuvi markazida qolgan o'smirni qutqarishi kerak.", "file_id": "BAACAgIAAxkBAAIB_extraction1_vid"},
    {"code": "116", "title": "Uddalab bo'lmas topshiriq 7 (Mission: Impossible 7)", "genres": "Jangari, Triller, Sarguzasht", "year": 2023, "rating": 8.1, "duration": 163, "views_count": 26400, "downloads_count": 8700, "description": "Iton Xant va uning jamoasi butun insoniyatga tahdid solayotgan sun'iy intellektga qarshi kurashadi.", "file_id": "BAACAgIAAxkBAAIB_mi7_vid"},
    {"code": "117", "title": "O'rgimchak odam: Uyga yo'l yo'q (No Way Home)", "genres": "Fantastika, Jangari, Sarguzasht", "year": 2021, "rating": 8.3, "duration": 148, "views_count": 51900, "downloads_count": 20600, "description": "Piter Parker shaxsi fosh bo'lgach, Doktor Strenjdan yordam so'raydi, biroq koinotlar chegarasi buziladi.", "file_id": "BAACAgIAAxkBAAIB_spidermannwh_vid"},
    {"code": "118", "title": "Top Gun: Meverik (Top Gun: Maverick)", "genres": "Jangari, Drama", "year": 2022, "rating": 8.4, "duration": 130, "views_count": 38100, "downloads_count": 13200, "description": "30 yillik xizmatdan so'ng Pit Meverik yosh harbiy uchuvchilarni maxsus operatsiyaga tayyorlash uchun qaytadi.", "file_id": "BAACAgIAAxkBAAIB_topgun2_vid"},
    {"code": "119", "title": "Betmen (The Batman)", "genres": "Kriminal, Detektiv, Jangari", "year": 2022, "rating": 7.9, "duration": 176, "views_count": 33400, "downloads_count": 10800, "description": "Bryus Ueyn Gotem shahrining qorong'u ko'chalarida sirli qotil Riddlerni qidirishga kirishadi.", "file_id": "BAACAgIAAxkBAAIB_thebatman_vid"},
    {"code": "120", "title": "Joker", "genres": "Drama, Kriminal, Triller", "year": 2019, "rating": 8.4, "duration": 122, "views_count": 49800, "downloads_count": 18900, "description": "Jamiyat tomonidan rad etilgan yolg'iz komik Artur Flek asta-sekin jinoyat olamining eng mashhur Jokeri darajasiga yetadi.", "file_id": "BAACAgIAAxkBAAIB_joker_vid"},

    # --- SARA O'ZBEK FILMLARI ---
    {"code": "121", "title": "Osmondagi bolalar 1", "genres": "Komediya, Drama, O'zbek kino", "year": 2002, "rating": 8.6, "duration": 95, "views_count": 68400, "downloads_count": 32100, "description": "To'rt nafar toshkentlik do'stning o'smirlik davri, muhabbati, orzulari va qiziqarli sarguzashtlari haqida unutilmas film.", "file_id": "BAACAgIAAxkBAAIB_osmondagibolalar1_vid"},
    {"code": "122", "title": "Osmondagi bolalar 2", "genres": "Komediya, Drama, O'zbek kino", "year": 2003, "rating": 8.4, "duration": 98, "views_count": 59100, "downloads_count": 27400, "description": "Do'stlarning ulg'ayishi, talabalik yillari va hayotning jiddiy sinovlari.", "file_id": "BAACAgIAAxkBAAIB_osmondagibolalar2_vid"},
    {"code": "123", "title": "Osmondagi bolalar 3", "genres": "Drama, O'zbek kino", "year": 2023, "rating": 7.8, "duration": 110, "views_count": 42300, "downloads_count": 16800, "description": "20 yil o'tib ulg'aygan va oila qurgan to'rt do'stning yangi davrdagi hayoti va muammolari.", "file_id": "BAACAgIAAxkBAAIB_osmondagibolalar3_vid"},
    {"code": "124", "title": "Shum bola", "genres": "Komediya, Klassika, O'zbek kino", "year": 1977, "rating": 9.1, "duration": 85, "views_count": 76500, "downloads_count": 39800, "description": "G'afur G'ulom qissasi asosida suratga olingan, o'tkir zehni va sho'xligi bilan xalq mehrini qozongan Qoravoy sarguzashtlari.", "file_id": "BAACAgIAAxkBAAIB_shumbola_vid"},
    {"code": "125", "title": "Mahallada duv-duv gap", "genres": "Komediya, O'zbek kino, Klassika", "year": 1960, "rating": 9.2, "duration": 80, "views_count": 81200, "downloads_count": 41200, "description": "O'zbek kino san'atining durdonasi — Toshkent mahallasidagi quvnoq va samimiy oilaviy voqealar.", "file_id": "BAACAgIAAxkBAAIB_mahalladaduvduv_vid"},
    {"code": "126", "title": "Kelinlar qo'zg'oloni", "genres": "Komediya, Klassika, O'zbek kino", "year": 1984, "rating": 9.0, "duration": 82, "views_count": 71800, "downloads_count": 35200, "description": "Farmonbibi va uning yetti kelini o'rtasidagi munosabatlar hamda o'zbek oilasining qadriyatlari.", "file_id": "BAACAgIAAxkBAAIB_kelinlarqozgoloni_vid"},
    {"code": "127", "title": "Suyunchi (Buvijon)", "genres": "Drama, Komediya, O'zbek kino", "year": 1982, "rating": 8.9, "duration": 78, "views_count": 58200, "downloads_count": 24900, "description": "Mehribon, biroq qattiqqo'l Anzirat buvining qishloq ahlini tartibga solishi va futbolchi nabiralar.", "file_id": "BAACAgIAAxkBAAIB_suyunchi_vid"},
    {"code": "128", "title": "Abdullajon", "genres": "Fantastika, Komediya, O'zbek kino", "year": 1991, "rating": 9.0, "duration": 88, "views_count": 69400, "downloads_count": 31000, "description": "O'zbek qishlog'iga tushib qolgan o'zga sayyoralik bola Abdullajon va ketmon uchirish sarguzashti.", "file_id": "BAACAgIAAxkBAAIB_abdullajon_vid"},
    {"code": "129", "title": "Tangalik bolalar", "genres": "Komediya, Bolalar, O'zbek kino", "year": 1990, "rating": 8.5, "duration": 75, "views_count": 48100, "downloads_count": 19300, "description": "Dastavval tanga topib olgan bolalarning qiziqarli va ibratli sarguzashtlari.", "file_id": "BAACAgIAAxkBAAIB_tangalikbolalar_vid"},
    {"code": "130", "title": "Baron", "genres": "Jangari, Kriminal, O'zbek kino", "year": 2016, "rating": 8.1, "duration": 135, "views_count": 54200, "downloads_count": 23600, "description": "Xalqaro giyohvand moddalar savdosiga qarshi kurashuvchi maxsus xizmat xodimlarining hayoti va jangi.", "file_id": "BAACAgIAAxkBAAIB_baron1_vid"},
    {"code": "131", "title": "Baron 2: Sog'inch", "genres": "Jangari, Drama, O'zbek kino", "year": 2022, "rating": 7.9, "duration": 128, "views_count": 39400, "downloads_count": 15100, "description": "Maxfiy agent Botir xalqaro terrorizmga qarshi kurashni davom ettiradi.", "file_id": "BAACAgIAAxkBAAIB_baron2_vid"},
    {"code": "132", "title": "Scorpion", "genres": "Jangari, Triller, O'zbek kino", "year": 2018, "rating": 7.7, "duration": 110, "views_count": 33100, "downloads_count": 11900, "description": "Maxsus xizmat zobiti xalqaro terrorchilik guruhiga qarshi yolg'iz kurash ochadi.", "file_id": "BAACAgIAAxkBAAIB_scorpion_vid"},
    {"code": "133", "title": "Snayper", "genres": "Jangari, Harbiy, O'zbek kino", "year": 2019, "rating": 7.8, "duration": 105, "views_count": 31800, "downloads_count": 10800, "description": "Chegara hududlarida terrorchilarni zararsizlantirishga yo'naltirilgan shiddatli harakatlar.", "file_id": "BAACAgIAAxkBAAIB_snayper_vid"},
    {"code": "134", "title": "Vatan", "genres": "Drama, Tarixiy, O'zbek kino", "year": 2006, "rating": 8.7, "duration": 130, "views_count": 45100, "downloads_count": 18300, "description": "Ikkinchi jahon urushidan so'ng o'zga yurtlarda qolib ketgan o'zbek askarining ona yurtga qaytish orzusi.", "file_id": "BAACAgIAAxkBAAIB_vatan_vid"},
    {"code": "135", "title": "Sarvinoz", "genres": "Melodrama, Drama, O'zbek kino", "year": 2004, "rating": 8.2, "duration": 100, "views_count": 51200, "downloads_count": 21700, "description": "Sevgisi uchun barcha qiyinchiliklarni yengib o'tishga intilgan ikki yoshning dramatik muhabbati.", "file_id": "BAACAgIAAxkBAAIB_sarvinoz_vid"},
    {"code": "136", "title": "Telba", "genres": "Drama, Melodrama, O'zbek kino", "year": 2008, "rating": 8.5, "duration": 115, "views_count": 61300, "downloads_count": 28400, "description": "Boy oilaning erka qizi va oddiy xizmatkor yigit o'rtasidagi samimiy va fojiali muhabbat qissasi.", "file_id": "BAACAgIAAxkBAAIB_telba_vid"},
    {"code": "137", "title": "Panoh", "genres": "Drama, O'zbek kino", "year": 2007, "rating": 8.0, "duration": 95, "views_count": 36700, "downloads_count": 13400, "description": "Insoniylik, qadr-qimmat va mehr-oqibat haqidagi ta'sirchan film.", "file_id": "BAACAgIAAxkBAAIB_panoh_vid"},
    {"code": "138", "title": "Mendirman Jaloliddin (Serial)", "genres": "Tarixiy, Jangari, Seriallar", "year": 2021, "rating": 8.4, "duration": 60, "views_count": 64200, "downloads_count": 29800, "description": "Mo'g'ul istilosiga qarshi mardonavor kurashgan afsonaviy sarkarda Jaloliddin Manguberdining jasorati.", "file_id": "BAACAgIAAxkBAAIB_jaloliddin_vid"},

    # --- MULTFILM VA ANIMATSIYA ---
    {"code": "139", "title": "Qirol Sher (The Lion King)", "genres": "Multfilm, Drama, Sarguzasht", "year": 1994, "rating": 8.9, "duration": 88, "views_count": 67300, "downloads_count": 34100, "description": "Yosh sher bolasi Simba o'zining taxtini qaytarib olish uchun ko'plab qiyinchiliklarni bosib o'tadi.", "file_id": "BAACAgIAAxkBAAIB_lionking_vid"},
    {"code": "140", "title": "Muz yurak (Frozen)", "genres": "Multfilm, Sarguzasht, Komediya", "year": 2013, "rating": 8.0, "duration": 102, "views_count": 59400, "downloads_count": 26800, "description": "Anna o'z opasi Elzani qidirib, muzlab qolgan qirollikni qutqarish uchun sarguzashtga otlanadi.", "file_id": "BAACAgIAAxkBAAIB_frozen1_vid"},
    {"code": "141", "title": "Muz yurak 2 (Frozen II)", "genres": "Multfilm, Sarguzasht, Fantastika", "year": 2019, "rating": 7.8, "duration": 103, "views_count": 48200, "downloads_count": 19400, "description": "Elza, Anna, Kristoff va Olaf sehrli o'rmon sirlarini ochish uchun shimolga yo'l olishadi.", "file_id": "BAACAgIAAxkBAAIB_frozen2_vid"},
    {"code": "142", "title": "Shrek 1", "genres": "Multfilm, Komediya, Sarguzasht", "year": 2001, "rating": 8.4, "duration": 90, "views_count": 63400, "downloads_count": 29800, "description": "Yashil bahaybat Shrek va uning gapdon eshagi malika Fionani qutqarish uchun xavfli yo'lga chiqishadi.", "file_id": "BAACAgIAAxkBAAIB_shrek1_vid"},
    {"code": "143", "title": "Shrek 2", "genres": "Multfilm, Komediya, Sarguzasht", "year": 2004, "rating": 8.3, "duration": 93, "views_count": 57100, "downloads_count": 25400, "description": "Shrek va Fiona qizning ota-onasi yashaydigan Olis-olis qirollikka mehmonga borishadi.", "file_id": "BAACAgIAAxkBAAIB_shrek2_vid"},
    {"code": "144", "title": "Panda Kung-Fu 4 (Kung Fu Panda 4)", "genres": "Multfilm, Jangari, Komediya", "year": 2024, "rating": 7.7, "duration": 94, "views_count": 41200, "downloads_count": 16900, "description": "Ajdaho jangchisi Po Tinchlik vodiysining ma'naviy yetakchisiga aylanishi va yangi shogird topishi lozim.", "file_id": "BAACAgIAAxkBAAIB_panda4_vid"},
    {"code": "145", "title": "Madagaskar 1", "genres": "Multfilm, Komediya, Sarguzasht", "year": 2005, "rating": 8.0, "duration": 86, "views_count": 58900, "downloads_count": 26100, "description": "Nyu-York hayvonot bog'ining to'rt do'sti Afrikaning yovvoyi tabiatiga tushib qolishadi.", "file_id": "BAACAgIAAxkBAAIB_madagascar1_vid"},
    {"code": "146", "title": "Boshqotirma 2 (Inside Out 2)", "genres": "Multfilm, Komediya, Oila", "year": 2024, "rating": 8.2, "duration": 96, "views_count": 49500, "downloads_count": 22400, "description": "Raylining miyasiga o'smirlik davrida yangi his-tuyg'ular — Xavotir, Uyatsizlik, Hasad kirib keladi.", "file_id": "BAACAgIAAxkBAAIB_insideout2_vid"},
    {"code": "147", "title": "Moana 2", "genres": "Multfilm, Sarguzasht, Komediya", "year": 2024, "rating": 7.9, "duration": 100, "views_count": 38700, "downloads_count": 15600, "description": "Moana ajdodlarining chorloviga javoban ulkan okean bo'ylab yangi xavfli ekspeditsiyaga otlanadi.", "file_id": "BAACAgIAAxkBAAIB_moana2_vid"},
    {"code": "148", "title": "Yaramas Men 4 (Despicable Me 4)", "genres": "Multfilm, Komediya, Oila", "year": 2024, "rating": 7.6, "duration": 95, "views_count": 44200, "downloads_count": 18700, "description": "Gryu va minionlar yangi dushman Maksim Le Malga qarshi kurashib, maxfiy uyda yashirinishga majbur bo'ladi.", "file_id": "BAACAgIAAxkBAAIB_despicableme4_vid"},

    # --- TOP SERIALLAR ---
    {"code": "149", "title": "Taxtlar o'yini (Game of Thrones)", "genres": "Seriallar, Fantastika, Drama", "year": 2011, "rating": 9.2, "duration": 60, "views_count": 91200, "downloads_count": 45800, "description": "Vesterosning Temir taxti uchun yetti qirollik o'rtasidagi shafqatsiz va qonli kurash.", "file_id": "BAACAgIAAxkBAAIB_got_vid"},
    {"code": "150", "title": "Qora sevgi (Kara Sevda)", "genres": "Seriallar, Melodrama, Drama", "year": 2015, "rating": 8.2, "duration": 120, "views_count": 84500, "downloads_count": 41200, "description": "Kamtarin kon muhandisi Kamol va boy oilaning qizi Nihonning to'siqlarga to'la buyuk sevgisi.", "file_id": "BAACAgIAAxkBAAIB_karasevda_vid"},
    {"code": "151", "title": "Chuqur (Çukur)", "genres": "Seriallar, Kriminal, Jangari", "year": 2017, "rating": 8.7, "duration": 130, "views_count": 78900, "downloads_count": 36700, "description": "Istanbulning eng xavfli tumani Chuqurni Ko'chovali oilasi qanday boshqarishi va qonun-qoidalari haqida.", "file_id": "BAACAgIAAxkBAAIB_cukur_vid"},
    {"code": "152", "title": "Qashqirlar makoni (Kurtlar Vadisi)", "genres": "Seriallar, Jangari, Kriminal", "year": 2003, "rating": 9.1, "duration": 80, "views_count": 89400, "downloads_count": 43900, "description": "Maxfiy xizmat agenti Po'lat Alemdar Turkiya mafiyasining ichiga kirib boradi va uni yo'q qilishga kirishadi.", "file_id": "BAACAgIAAxkBAAIB_kurtlarvadisi_vid"},
    {"code": "153", "title": "Kalmar o'yini (Squid Game)", "genres": "Seriallar, Triller, Drama", "year": 2021, "rating": 8.5, "duration": 55, "views_count": 86300, "downloads_count": 39500, "description": "Mablag'ga muhtoj yuzlab odamlar katta sovrin uchun bolalar o'yinlarini o'lim bilan o'ynashga rozi bo'lishadi.", "file_id": "BAACAgIAAxkBAAIB_squidgame_vid"},
    {"code": "154", "title": "Qog'oz bino (La Casa de Papel)", "genres": "Seriallar, Kriminal, Triller", "year": 2017, "rating": 8.6, "duration": 50, "views_count": 74300, "downloads_count": 32800, "description": "Professor boshchiligidagi maxsus guruh Ispaniya Qirollik zarbxonasiga kirib, milliardlab yevro bosib chiqarishni rejalashtiradi.", "file_id": "BAACAgIAAxkBAAIB_lacasadepapel_vid"},
    {"code": "155", "title": "O'tkir soyabonlar (Peaky Blinders)", "genres": "Seriallar, Kriminal, Drama", "year": 2013, "rating": 8.8, "duration": 60, "views_count": 68100, "downloads_count": 29400, "description": "Birinchi jahon urushidan so'ng Birmingemdagi Shelbi oilasi gangsterlar to'dasining yuksalishi.", "file_id": "BAACAgIAAxkBAAIB_peakyblinders_vid"},
    {"code": "156", "title": "Chernobil (Chernobyl)", "genres": "Seriallar, Tarixiy, Drama", "year": 2019, "rating": 9.4, "duration": 60, "views_count": 58900, "downloads_count": 24800, "description": "1986-yilda yuz bergan Chernobil AES halokati va uni bartaraf etishga uringan qahramonlar fojeasi.", "file_id": "BAACAgIAAxkBAAIB_chernobyl_vid"},
    {"code": "157", "title": "Sherlok (Sherlock)", "genres": "Seriallar, Detektiv, Kriminal", "year": 2010, "rating": 9.1, "duration": 88, "views_count": 65400, "downloads_count": 28100, "description": "Zamonaviy Londonda detektiv Sherlok Xolms va doktor Jon Vatsonning eng murakkab jinoyatlarni fosh etishi.", "file_id": "BAACAgIAAxkBAAIB_sherlock_vid"},
    {"code": "158", "title": "G'alati narsalar (Stranger Things)", "genres": "Seriallar, Fantastika, Qo'rqinchli", "year": 2016, "rating": 8.7, "duration": 50, "views_count": 62400, "downloads_count": 26900, "description": "Xoukins shahrida g'oyib bo'lgan bolani qidirish jarayonida maxfiy laboratoriya va boshqa o'lcham ochiladi.", "file_id": "BAACAgIAAxkBAAIB_strangerthings_vid"},

    # --- JAXON KLASSIKASI VA DRAMA ---
    {"code": "159", "title": "Shoushenkdan qochish (The Shawshank Redemption)", "genres": "Drama, Kriminal", "year": 1994, "rating": 9.3, "duration": 142, "views_count": 78200, "downloads_count": 36100, "description": "Begunoh qamalgan bankir Endi Dyufreyn Shoushenk qamoqxonasida umidini yo'qotmay, aqlbovar qilmas rejani amalga oshiradi.", "file_id": "BAACAgIAAxkBAAIB_shawshank_vid"},
    {"code": "160", "title": "Yashil yo'lak (The Green Mile)", "genres": "Drama, Fantastika, Kriminal", "year": 1999, "rating": 9.2, "duration": 189, "views_count": 74100, "downloads_count": 33900, "description": "O'lim jazosiga hukm qilingan maxbuslar bo'limida mo''jizaviy shifobaxsh kuchga ega bahaybat Jon Koffi paydo bo'ladi.", "file_id": "BAACAgIAAxkBAAIB_greenmile_vid"},
    {"code": "161", "title": "Titanik (Titanic)", "genres": "Melodrama, Drama, Tarixiy", "year": 1997, "rating": 8.8, "duration": 194, "views_count": 82500, "downloads_count": 38400, "description": "Cho'kmas hisoblangan afsonaviy kemada boy qiz Rouz va oddiy rassom Jek o'rtasidagi abadiy muhabbat.", "file_id": "BAACAgIAAxkBAAIB_titanic_vid"},
    {"code": "162", "title": "1+1 (Daxlsizlar / The Intouchables)", "genres": "Komediya, Drama, Biografiya", "year": 2011, "rating": 8.9, "duration": 112, "views_count": 69200, "downloads_count": 31400, "description": "Nogiron aristokrat Filipp qamoqdan chiqqan quvnoq qora tanli Drissni o'ziga parvarishchi qilib yollaydi.", "file_id": "BAACAgIAAxkBAAIB_intouchables_vid"},
    {"code": "163", "title": "Uch savdoyi (3 Idiots)", "genres": "Komediya, Drama", "year": 2009, "rating": 8.7, "duration": 170, "views_count": 61200, "downloads_count": 27300, "description": "Hindiston muhandislik kollejida tahsil olayotgan uch do'stning ta'lim tizimiga va orzulariga qarashlari.", "file_id": "BAACAgIAAxkBAAIB_3idiots_vid"},
    {"code": "164", "title": "Leon (Léon: The Professional)", "genres": "Jangari, Drama, Kriminal", "year": 1994, "rating": 8.6, "duration": 110, "views_count": 52100, "downloads_count": 22900, "description": "Yollanma professional qotil Leon oilasi qatl etilgan 12 yoshli Matilda ismli qizchani himoya qiladi.", "file_id": "BAACAgIAAxkBAAIB_leon_vid"},
    {"code": "165", "title": "Jang klubi (Fight Club)", "genres": "Triller, Drama", "year": 1999, "rating": 8.8, "duration": 139, "views_count": 57400, "downloads_count": 25100, "description": "Uyqusizlikdan aziyat chekuvchi xizmatchi va g'alati sovun sotuvchisi Tayler Derden yashirin jang klubi tuzishadi.", "file_id": "BAACAgIAAxkBAAIB_fightclub_vid"},
    {"code": "166", "title": "Lannat (The Conjuring)", "genres": "Qo'rqinchli, Triller, Detektiv", "year": 2013, "rating": 7.9, "duration": 112, "views_count": 43500, "downloads_count": 17200, "description": "Paranormal hodisalar bo'yicha mutaxassislar Perronlar oilasining fermasidagi qorong'u ruhlarni tadqiq qilishadi.", "file_id": "BAACAgIAAxkBAAIB_conjuring_vid"},
    {"code": "167", "title": "Astral (Insidious)", "genres": "Qo'rqinchli, Triller, Fantastika", "year": 2010, "rating": 7.7, "duration": 103, "views_count": 39800, "downloads_count": 15400, "description": "Komaga tushib qolgan bolaning ruhi qorong'u o'lcham — Astralga tushib qoladi.", "file_id": "BAACAgIAAxkBAAIB_astral_vid"},
    {"code": "168", "title": "Garri Potter va Falsafa toshi", "genres": "Fantastika, Sarguzasht, Oila", "year": 2001, "rating": 8.6, "duration": 152, "views_count": 73200, "downloads_count": 35800, "description": "Yetim bola Garri Potter o'zining sehrgar ekanligini bilib, Xogvarts afsungarlik maktabiga yo'l oladi.", "file_id": "BAACAgIAAxkBAAIB_harrypotter1_vid"},
]

# Qo'shimcha 112 ta kino avtomatik generatsiya qilinadi (jami 180+ taga yetkazish uchun)
ADDITIONAL_TITLES = [
    ("Forsaj 9", "Jangari, Sarguzasht", 2021, 7.1),
    ("Forsaj 8", "Jangari, Triller", 2017, 7.3),
    ("Forsaj 7", "Jangari, Triller", 2015, 7.9),
    ("Avatar 1", "Fantastika, Sarguzasht", 2009, 8.5),
    ("Jon Uik 3: Parabellum", "Jangari, Triller", 2019, 7.8),
    ("Jon Uik 2", "Jangari, Triller", 2017, 7.9),
    ("Jon Uik 1", "Jangari, Triller", 2014, 7.8),
    ("Dedpul 1", "Jangari, Komediya", 2016, 8.0),
    ("Dedpul 2", "Jangari, Komediya", 2018, 7.9),
    ("Qora Pantera (Black Panther)", "Jangari, Fantastika", 2018, 7.8),
    ("Doktor Strendj 2", "Fantastika, Sarguzasht", 2022, 7.5),
    ("Tor: Sevgi va chaqmoq", "Fantastika, Komediya", 2022, 7.2),
    ("Tor: Ragnarok", "Fantastika, Jangari", 2017, 8.1),
    ("Temir odam 1", "Fantastika, Jangari", 2008, 8.3),
    ("Temir odam 2", "Fantastika, Jangari", 2010, 7.8),
    ("Temir odam 3", "Fantastika, Jangari", 2013, 7.9),
    ("Kapitan Amerika: Qishki askar", "Jangari, Fantastika", 2014, 8.1),
    ("Kapitan Amerika: Fuqarolar urushi", "Jangari, Fantastika", 2016, 8.2),
    ("Galaktika qo'riqchilari 3", "Fantastika, Sarguzasht", 2023, 8.3),
    ("Galaktika qo'riqchilari 1", "Fantastika, Komediya", 2014, 8.2),
    ("Dyuna 1", "Fantastika, Sarguzasht", 2021, 8.3),
    ("Venom 1", "Fantastika, Jangari", 2018, 7.4),
    ("Venom 2: Qirg'in", "Fantastika, Jangari", 2021, 7.1),
    ("Venom 3: So'nggi raqs", "Fantastika, Jangari", 2024, 7.6),
    ("O'rgimchak odam: Uyga qaytish", "Fantastika, Sarguzasht", 2017, 7.9),
    ("O'rgimchak odam: Uydan uzoqda", "Fantastika, Sarguzasht", 2019, 7.8),
    ("Transformatorlar: Yirtqichlar yuksalishi", "Fantastika, Jangari", 2023, 7.1),
    ("Transformatorlar 1", "Fantastika, Jangari", 2007, 7.8),
    ("Terminator 2: Hukm kuni", "Jangari, Fantastika", 1991, 8.9),
    ("Godzilla Kongga qarshi", "Fantastika, Jangari", 2021, 7.4),
    ("Godzilla va Kong: Yangi imperiya", "Fantastika, Jangari", 2024, 7.5),
    ("Qora beva (Black Widow)", "Jangari, Sarguzasht", 2021, 7.2),
    ("Shan-Chi va o'n uzuk afsonasi", "Fantastika, Jangari", 2021, 7.7),
    ("Abadiylar (Eternals)", "Fantastika, Drama", 2021, 6.9),
    ("Akvamen 1", "Fantastika, Jangari", 2018, 7.4),
    ("Akvamen 2: Yo'qolgan qirollik", "Fantastika, Sarguzasht", 2023, 7.0),
    ("Supermen: Chelik odam", "Fantastika, Jangari", 2013, 7.6),
    ("Adolat ligasi (Zack Snyder)", "Fantastika, Jangari", 2021, 8.2),
    ("Garri Potter va Maxfiy xona", "Fantastika, Sarguzasht", 2002, 8.2),
    ("Garri Potter va Azkaban mahbusi", "Fantastika, Sarguzasht", 2004, 8.5),
    ("Garri Potter va Alanga kubogi", "Fantastika, Sarguzasht", 2005, 8.3),
    ("Garri Potter va Feniks jamiyati", "Fantastika, Sarguzasht", 2007, 8.1),
    ("Garri Potter va Tilsim shahzodasi", "Fantastika, Sarguzasht", 2009, 8.2),
    ("Garri Potter va Ajal tuhfasi 1", "Fantastika, Sarguzasht", 2010, 8.3),
    ("Garri Potter va Ajal tuhfasi 2", "Fantastika, Sarguzasht", 2011, 8.7),
    ("Uzuklar hukumdori: Uzuklar birodarligi", "Fantastika, Sarguzasht", 2001, 9.0),
    ("Uzuklar hukumdori: Ikki qal'a", "Fantastika, Sarguzasht", 2002, 9.0),
    ("Uzuklar hukumdori: Qirolning qaytishi", "Fantastika, Sarguzasht", 2003, 9.1),
    ("Hobbit: Kutilmagan sayohat", "Fantastika, Sarguzasht", 2012, 8.2),
    ("Hobbit: Smog vayronasi", "Fantastika, Sarguzasht", 2013, 8.3),
    ("Hobbit: Besh qo'shin jangi", "Fantastika, Sarguzasht", 2014, 8.1),
    ("Karib dengizi qaroqchilari 1", "Sarguzasht, Komediya", 2003, 8.5),
    ("Karib dengizi qaroqchilari 2", "Sarguzasht, Komediya", 2006, 8.2),
    ("Karib dengizi qaroqchilari 3", "Sarguzasht, Komediya", 2007, 8.0),
    ("Janob Bin ta'tilda", "Komediya, Oila", 2007, 7.9),
    ("Uyda yolg'iz 1 (Home Alone)", "Komediya, Oila", 1990, 8.9),
    ("Uyda yolg'iz 2: Nyu-Yorkda", "Komediya, Oila", 1992, 8.7),
    ("Niqob (The Mask)", "Komediya, Fantastika", 1994, 8.4),
    ("Bryus Butunqudrat", "Komediya, Fantastika", 2003, 8.1),
    ("Yolg'onchi, yolg'onchi", "Komediya", 1997, 8.0),
    ("Eyfe (Ace Ventura)", "Komediya", 1994, 7.8),
    ("Madagaskar 2: Qochish Afrikaga", "Multfilm, Komediya", 2008, 8.1),
    ("Madagaskar 3: Yevropa qidiruvida", "Multfilm, Komediya", 2012, 8.0),
    ("Panda Kung-Fu 1", "Multfilm, Jangari", 2008, 8.3),
    ("Panda Kung-Fu 2", "Multfilm, Jangari", 2011, 8.2),
    ("Panda Kung-Fu 3", "Multfilm, Jangari", 2016, 8.1),
    ("Shrek 3", "Multfilm, Komediya", 2007, 7.6),
    ("Shrek abadiy", "Multfilm, Komediya", 2010, 7.7),
    ("Etik kiygan mushuk 2: So'nggi tilak", "Multfilm, Sarguzasht", 2022, 8.5),
    ("O'yinchoqlar tarixi 1", "Multfilm, Sarguzasht", 1995, 8.6),
    ("O'yinchoqlar tarixi 4", "Multfilm, Sarguzasht", 2019, 8.2),
    ("Ruh (Soul)", "Multfilm, Falsafa", 2020, 8.5),
    ("Koko siri (Coco)", "Multfilm, Oila", 2017, 8.7),
    ("Zootopiya (Hayvonlar shahri)", "Multfilm, Komediya", 2016, 8.4),
    ("Megamiya (Megamind)", "Multfilm, Komediya", 2010, 8.1),
    ("Ratatuy", "Multfilm, Komediya", 2007, 8.5),
    ("Wall-E (Valli)", "Multfilm, Fantastika", 2008, 8.7),
    ("Up (Yuqoriga)", "Multfilm, Drama", 2009, 8.6),
    ("Moana 1", "Multfilm, Sarguzasht", 2016, 8.1),
    ("Aladdin", "Sarguzasht, Fantastika", 2019, 7.9),
    ("Qo'rqinchli kino 1", "Komediya, Parodiya", 2000, 7.5),
    ("Hangover (Vegasdagi boshog'riq)", "Komediya", 2009, 8.2),
    ("Vegasdagi boshog'riq 2", "Komediya", 2011, 7.6),
    ("Snayper: Oq o'lim", "Jangari, Harbiy", 2022, 7.3),
    ("Qasos (V for Vendetta)", "Triller, Fantastika", 2005, 8.6),
    ("Yulduzlar jangi 7", "Fantastika, Sarguzasht", 2015, 8.0),
    ("Yulduzlar jangi 8", "Fantastika, Sarguzasht", 2017, 7.5),
    ("Yulduzlar jangi 9", "Fantastika, Sarguzasht", 2019, 7.2),
    ("Qotillik anotomiyasi (Knives Out)", "Detektiv, Komediya", 2019, 8.1),
    ("Shisha piyoz (Glass Onion)", "Detektiv, Komediya", 2022, 7.7),
    ("Qora nina (Black Mirror)", "Seriallar, Fantastika", 2011, 8.8),
    ("Vikinglar (Vikings)", "Seriallar, Tarixiy", 2013, 8.7),
    ("Rik va Morti (Rick and Morty)", "Seriallar, Multfilm", 2013, 9.1),
    ("Loki (Serial)", "Seriallar, Fantastika", 2021, 8.4),
    ("Vanda Vijen (WandaVision)", "Seriallar, Fantastika", 2021, 8.1),
    ("Yigitlar (The Boys)", "Seriallar, Jangari", 2019, 8.8),
    ("Uinsdey (Wednesday)", "Seriallar, Fantastika", 2022, 8.3),
    ("Oxirgi qahramon (The Last of Us)", "Seriallar, Drama", 2023, 8.9),
    ("Echki bolalari (O'zbek kino)", "Komediya, O'zbek kino", 2010, 7.8),
    ("Majruh (O'zbek kino)", "Drama, O'zbek kino", 2010, 8.1),
    ("O'g'irlangan kelin (O'zbek kino)", "Komediya, O'zbek kino", 2009, 8.0),
    ("Super kelinchak (O'zbek kino)", "Komediya, O'zbek kino", 2008, 8.3),
    ("Boyvachcha (O'zbek kino)", "Komediya, O'zbek kino", 2007, 8.2),
    ("Shabnam (O'zbek kino)", "Melodrama, O'zbek kino", 2008, 8.0),
    ("Sevali (O'zbek kino)", "Drama, O'zbek kino", 2011, 7.9),
    ("Zirapcha (O'zbek kino)", "Drama, O'zbek kino", 2015, 7.8),
    ("Sotqin (O'zbek kino)", "Drama, Kriminal", 2015, 8.3),
    ("Ilhaq (O'zbek kino)", "Harbiy, Tarixiy, Drama", 2020, 8.8),
    ("101-reys (O'zbek kino)", "Drama, O'zbek kino", 2022, 8.0),
    ("Sabot (O'zbek kino)", "Drama, O'zbek kino", 2018, 7.7),
    ("Qo'rg'on (O'zbek kino)", "Tarixiy, Drama", 2021, 7.9),
    ("Tutqunlik (O'zbek kino)", "Harbiy, Drama", 2021, 8.2),
    ("Bahor qaytmaydi (O'zbek kino)", "Klassika, Drama", 1972, 8.9),
    ("O'tgan kunlar (O'zbek kino)", "Klassika, Tarixiy", 1969, 9.3),
    ("Kelinlar daftaridan (O'zbek kino)", "Komediya", 2013, 7.6),
    ("G'ariblar (O'zbek kino)", "Drama", 2012, 7.8),
]

# Jami 185+ ta kinoni to'ldirish
start_code = 169
for idx, (title, genres, year, rating) in enumerate(ADDITIONAL_TITLES):
    code_str = str(start_code + idx)
    MOVIES_DATA.append({
        "code": code_str,
        "title": title,
        "genres": genres,
        "year": year,
        "rating": rating,
        "duration": 100 + (idx % 40),
        "views_count": 15000 + (idx * 317) % 35000,
        "downloads_count": 5000 + (idx * 113) % 15000,
        "description": f"«{title}» filmi ({year}) — qiziqarli syujet, ajoyib aktyorlik mahorati va unutilmas lahzalar taqdim etadi.",
        "file_id": f"BAACAgIAAxkBAAIB_mov_{code_str}_vid",
    })


async def seed_movies_if_empty(session: AsyncSession) -> int:
    """
    Bazada barcha rasmiy kinolar (MOVIES_DATA va data/catalog.json)
    mavjudligini tekshiradi va yetishmayotganlarini bazaga kiritadi.
    Bitta so'rov orqali barcha mavjud kodlarni oladi va WAN latency'ni kamaytiradi.
    """
    from sqlalchemy import select
    res = await session.execute(select(Movie.code))
    existing_codes = set(res.scalars().all())
    inserted = 0
    to_add = []

    # 1. Boshlang'ich kinolar
    for m in MOVIES_DATA:
        if m["code"] not in existing_codes:
            movie = Movie(
                code=m["code"],
                title=m["title"],
                description=m["description"],
                file_id=m["file_id"],
                file_type="video",
                file_size=1024 * 1024 * 450,  # 450 MB taxminiy
                duration=m["duration"] * 60,
                genres=m["genres"],
                year=m["year"],
                rating=m["rating"],
                views_count=m["views_count"],
                downloads_count=m["downloads_count"],
            )
            to_add.append(movie)
            existing_codes.add(m["code"])
            inserted += 1

    # 2. Rasmiy katalogdagi kinolar (data/catalog.json)
    catalog_path = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                cat = json.load(f)
            for it in cat.get("items", []):
                code = str(it.get("c", "")).strip()
                if not code or code in existing_codes:
                    continue
                movie = Movie(
                    code=code,
                    title=it.get("t", "Kino"),
                    description=it.get("d", ""),
                    file_id=f"BAACAgIAAxkBAAIB_mov_{code}_vid",
                    file_type="video",
                    file_size=1024 * 1024 * 550,
                    duration=95 * 60,
                    genres="Kino, Komediya, O'zbek kino",
                    year=2023,
                    rating=8.0,
                    views_count=it.get("v", 150),
                    downloads_count=it.get("v", 150) // 3,
                )
                to_add.append(movie)
                existing_codes.add(code)
                inserted += 1
        except Exception as e:
            logger.warning(f"catalog.json dan kinolarni seed qilishda xatolik: {e}")

    if to_add:
        session.add_all(to_add)
        await session.commit()
        logger.info(f"Bazada jami {inserted} ta yangi kino seed qilindi (Jami: {len(existing_codes)} ta).")
    else:
        logger.info(f"Kinolar bazada yetarli ({len(existing_codes)} ta mavjud). Seed kerak emas.")

    return inserted
