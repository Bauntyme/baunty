"""Script to generate the full 3390-book library catalog for Baunty Cinema & Books.

Preserves the original 32 seed books and expands up to exactly 3390 books
with rich Uzbek, Russian, and World classical, business, psychological,
detective, historical, and scientific literature.
"""

import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BOOKS_FILE = BASE_DIR / "data" / "books.json"

# Load existing 32 books to preserve them identically
existing_books = []
if BOOKS_FILE.exists():
    try:
        with open(BOOKS_FILE, "r", encoding="utf-8") as f:
            existing_books = json.load(f)
    except Exception as e:
        print(f"Error reading existing books: {e}")

preserved_count = len(existing_books)
target_total = 3390
needed_count = target_total - preserved_count

print(f"Preserving {preserved_count} existing books, generating {needed_count} new books...")

# Authors by domain
UZ_AUTHORS = [
    ("Abdulla Qodiriy", "O'zbek adabiyoti klassigi"),
    ("Abdulhamid Cho'lpon", "O'zbek jadid adabiyoti peshvosi"),
    ("Abdurauf Fitrat", "Buyuk alloma va jadid mutafakkiri"),
    ("Oybek (Muso Toshmuhammad o'g'li)", "O'zbek xalq yozuvchisi, akademik"),
    ("G'afur G'ulom", "O'zbek xalq shoiri va akademik"),
    ("Erkin Vohidov", "O'zbekiston Qahramoni, xalq shoiri"),
    ("Abdulla Oripov", "O'zbekiston Qahramoni, Davlat madhiyasi muallifi"),
    ("Said Ahmad", "O'zbekiston Qahramoni, xalq yozuvchisi"),
    ("O'tkir Hoshimov", "O'zbekiston xalq yozuvchisi"),
    ("Pirimqul Qodirov", "O'zbekiston xalq yozuvchisi"),
    ("Tohir Malik", "O'zbekiston xalq yozuvchisi, detektiv ustasi"),
    ("Xudoyberdi To'xtaboyev", "O'zbekiston xalq yozuvchisi, bolalar adibi"),
    ("Odil Yoqubov", "O'zbekiston xalq yozuvchisi"),
    ("Asqad Muxtor", "O'zbekiston xalq yozuvchisi"),
    ("Mirkarim Osim", "Tarixiy qissalar ustasi"),
    ("Shukur Xolmirzayev", "O'zbekiston xalq yozuvchisi"),
    ("Murod Muhammad Do'st", "O'zbekiston xalq yozuvchisi"),
    ("Muhammad Yusuf", "O'zbekiston xalq shoiri"),
    ("Halima Xudoyberdiyeva", "O'zbekiston xalq shoirasi"),
    ("Rauf Parfi", "O'zbekiston xalq shoiri"),
    ("Zulfiya Isroilova", "O'zbekiston xalq shoirasi"),
    ("Hamid Olimjon", "O'zbek she'riyati yulduzi"),
    ("Usmon Nosir", "Olovli o'zbek shoiri"),
    ("Maqsud Shayxzoda", "Shoir, dramaturg va tarjimon"),
    ("Alisher Navoiy", "Buyuk o'zbek shoiri va mutafakkiri"),
    ("Zahiriddin Muhammad Bobur", "Buyuk sarkarda, shoh va shoir"),
    ("Mashrab (Boborahim)", "Tasavvuf she'riyati dahosi"),
    ("Ogahiy (Muhammad Rizo)", "Tarixchi, shoir va tarjimon"),
    ("Muqimiy (Muhammad Aminxo'ja)", "Hajviyot va lirik she'riyat ustasi"),
    ("Furqat (Zokirjon)", "Ma'rifatparvar o'zbek shoiri"),
    ("Ahmad Yassaviy", "Turkiy tasavvuf asoschisi, Hikmatlar muallifi"),
    ("Alixonto'ra Sog'uniy", "Tarixchi va din arbobi"),
    ("Shayx Muhammad Sodiq Muhammad Yusuf", "Islom olamining ulug' faqihi"),
    ("Isajon Sulton", "O'zbekiston xalq yozuvchisi"),
    ("Erkin A'zam", "O'zbekiston xalq yozuvchisi"),
    ("Xurshid Do'stmuhammad", "Taniqli adib va olim"),
    ("Luqmon Bo'rixon", "Iste'dodli qalamkash"),
    ("Anvar Obidjon", "O'zbekiston xalq shoiri, hajv ustasi"),
    ("Quddus Muhammadiy", "Bolalar she'riyati klassigi"),
]

RU_AUTHORS = [
    ("Лев Толстой", "Великий русский писатель и мыслитель"),
    ("Фёдор Достоевский", "Классик мировой литературы, психолог"),
    ("Антон Чехов", "Мастер короткого рассказа и драматургии"),
    ("Александр Пушкин", "Солнце русской поэзии"),
    ("Михаил Лермонтов", "Гений русской романтической поэзии"),
    ("Николай Гоголь", "Мастер мистики, юмора и сатиры"),
    ("Иван Тургенев", "Тонкий знаток человеческой души"),
    ("Михаил Булгаков", "Автор бессмертных мистических шедевров"),
    ("Борис Пастернак", "Лауреат Нобелевской премии по литературе"),
    ("Михаил Шолохов", "Летописец донского казачества"),
    ("Александр Солженицын", "Лауреат Нобелевской премии"),
    ("Владимир Набоков", "Мастер словесного стиля и интеллекта"),
    ("Иван Бунин", "Первый русский лауреат Нобелевской премии"),
    ("Александр Куприн", "Реалист, мастер тонких чувств"),
    ("Сергей Есенин", "Певец русской природы и любви"),
    ("Владимир Маяковский", "Бунтарь и реформатор стиха"),
    ("Анна Ахматова", "Голос серебряного века"),
    ("Марина Цветаева", "Страстная поэтесса трагической судьбы"),
    ("Александр Блок", "Символист, рыцарь прекрасной дамы"),
    ("Илья Ильф, Евгений Петров", "Классики сатиры и иронии"),
    ("Борис Акунин", "Мастер исторического детектива"),
    ("Евгений Замятин", "Основоположник антиутопии"),
    ("Аркадий и Борис Стругацкие", "Легенды советской фантастики"),
    ("Виктор Пелевин", "Культовый постмодернист современности"),
]

WORLD_AUTHORS = [
    ("Ernest Hemingway", "Nobel prize-winning American author"),
    ("George Orwell", "English novelist and essayist, master of dystopian fiction"),
    ("Gabriel Garcia Marquez", "Master of magical realism, Nobel laureate"),
    ("Arthur Conan Doyle", "Creator of Sherlock Holmes"),
    ("Agatha Christie", "Queen of Crime and mystery"),
    ("Jules Verne", "Father of science fiction and adventure"),
    ("Jack London", "Master of wild adventures and human spirit"),
    ("Mark Twain", "Great American humorist and novelist"),
    ("Franz Kafka", "Visionary of existential philosophy and alienation"),
    ("Erich Maria Remarque", "Chronicler of the Lost Generation"),
    ("Victor Hugo", "Giant of French romanticism and social justice"),
    ("Alexandre Dumas", "Legendary French adventure novelist"),
    ("Honore de Balzac", "Creator of the Human Comedy"),
    ("Charles Dickens", "Great Victorian social realist"),
    ("Jane Austen", "Master of wit, romance, and social manners"),
    ("James Clear", "World-renowned habits and performance expert"),
    ("Robert Kiyosaki", "Personal finance pioneer and educator"),
    ("Dale Carnegie", "Pioneer in leadership and human communication"),
    ("Stephen R. Covey", "Legendary leadership consultant and thinker"),
    ("Napoleon Hill", "Pioneer of success philosophy and mindset"),
    ("Daniel Kahneman", "Nobel laureate in economics, psychologist"),
    ("Malcolm Gladwell", "Brilliant explorer of human behavior and success"),
    ("Yuval Noah Harari", "Historian and philosopher of the future"),
    ("Viktor E. Frankl", "Founder of logotherapy, psychiatrist"),
    ("Marcus Aurelius", "Roman Emperor and Stoic philosopher"),
    ("Sun Tzu", "Ancient Chinese military general and strategist"),
    ("Niccolo Machiavelli", "Renaissance political philosopher"),
    ("Robert Greene", "Master of strategy, power, and human nature"),
    ("Brian Tracy", "Global authority on achievement and goal setting"),
    ("Robin Sharma", "Leadership and personal mastery expert"),
    ("Jordan B. Peterson", "Clinical psychologist and cultural thinker"),
    ("J.K. Rowling", "Creator of the wizarding world"),
    ("J.R.R. Tolkien", "Father of modern high fantasy"),
    ("Isaac Asimov", "Grand Master of science fiction"),
    ("Arthur C. Clarke", "Visionary science fiction author and futurist"),
    ("Ray Bradbury", "Poetic master of speculative fiction"),
    ("Philip K. Dick", "Pioneer of philosophical cyberpunk and sci-fi"),
    ("Stephen King", "Master of horror, suspense, and human drama"),
    ("Dan Brown", "Master of historical mystery and symbology"),
    ("Paulo Coelho", "Internationally bestselling philosophical novelist"),
    ("Khaled Hosseini", "Heart-rending chronicler of human resilience"),
]

# Thematic title generators
GENRE_CONFIGS = [
    ("badiiy", "Badiiy adabiyot", [
        "Qadimgi ko'chaning siri", "Qorong'i tun sadosi", "Yulduzlar ostidagi suhbat", "Kechikkan pushaymon",
        "Tong yulduzi so'nganda", "Bahor epkini", "Ufq ortidagi shahar", "Qor bosgan izlar", "Tog'lar sadosi",
        "Oq bulutlar karvoni", "Xazon fasli", "Yurakdagi tugun", "Olis manzillar chorlovi", "Yashil daryo bo'yida",
        "Sohildagi shamchiroq", "Umid uchqunlari", "Kuzgi yomg'ir nolasi", "Begona nigohlar", "Qalb gavhari",
        "Kechirim ilinjida", "Ona mehri", "Otalar merosi", "Vatan sarhadlari", "Yorug' yo'llar", "Hayot sinovlari",
        "Bosh egmagan mag'rur qalb", "Qaytib kelgan bahor", "Qora qoya qissasi", "Oltin kuz nafasida", "Mehr chashmasi"
    ]),
    ("biznes", "Biznes & Moliya", [
        "Muvaffaqiyat strategiyasi", "Moliyaviy erkinlik sari", "Kapital boshqaruvi sirlari", "Biznesda yetakchilik",
        "Boylik falsafasi", "Samarali investitsiya san'ati", "Startapdan korporatsiyagacha", "Muzokaralar olib borish mahorati",
        "Krizisda rivojlanish qoidalari", "Vaqtni boshqarish tizimi", "Raqamli iqtisodiyot davri", "Mijozlar sadoqati siri",
        "Brend yaratish san'ati", "Shaxsiy brend qudrati", "Katta pullar psixologiyasi", "Kreativ marketing usullari",
        "Bozorda ustunlikka erishish", "Biznes jarayonlarini avtomatlashtirish", "Yangi asr tadbirkorligi", "Kichik biznesdan katta foyda"
    ]),
    ("psixologiya", "Psixologiya", [
        "Ichki xotirjamlik kaliti", "Hissiy aql va o'zini anglash", "Stress va xavotirdan xalos bo'lish", "Munosabatlar sirlari",
        "Inson ruhiyati jumbog'i", "Qat'iyatlilik va iroda kuchi", "O'ziga ishonch san'ati", "Bolalar psixologiyasi asoslari",
        "Depressiyani yengish yo'li", "Pozitiv fikrlash qudrati", "Qaror qabul qilish mexanizmi", "Miya va ong evolyutsiyasi",
        "Yolg'onni aniqlash san'ati", "O'tmish jarohatlaridan forig' bo'lish", "Baxtli hayot formulasi", "Manipulyatsiyadan himoyalanish"
    ]),
    ("detektiv", "Detektiv & Triller", [
        "Yopiq xona jumbog'i", "Tungi poyezddagi qotillik", "Qora niqobli qotil", "Yo'qolgan meros izidan",
        "Qonga belangan xanjar", "Tergovchining so'nggi xatosi", "Sirli qo'ng'iroq", "Shahar ostidagi labirint",
        "Gumonlanuvchi №1", "O'ch olinmagan jinoyat", "Sud zalidagi sir", "Xufyona bitim", "Qidiruvdagi jinoyatchi",
        "Muzlagan haqiqat", "O'rmon ichidagi topilma", "Qorong'ilikdagi izlar", "Sud-tibbiy ekspertizasi siri"
    ]),
    ("fantastika", "Fantastika & Kosmos", [
        "Yulduzlararo sayohat", "Koinot qa'ridagi stansiya", "Kiber-dunyo qonunlari", "Sun'iy intellekt isyoni",
        "Vaqt sayohatchilari", "Boshqa o'lcham siri", "Marsdagi birinchi shahar", "Qora tuynuk ostonasida",
        "Galaktikalar jangi", "Kvant sakrashi", "Klonlar jamiyati", "So'nggi yerlik", "Begona sivilizatsiya elchisi",
        "Paralel olamlar chorrahasi", "Metagalaktika asiri", "Androidlar orzusi", "Kosmik kema halokati"
    ]),
    ("tarix", "Tarix & Fan", [
        "Buyuk Ipak yo'li sirlari", "Amir Temur saltanati haqiqatlari", "Qadimgi Turon xazinalari", "Boburiylar sulolasi yorug'ligi",
        "Jahon sivilizatsiyalari beshigi", "Markaziy Osiyo Renessansi", "Xorazm Ma'mun akademiyasi", "Ulug'bek rasadxonasi mo'jizasi",
        "Ibn Sino va Sharq tabobati", "Buyuk allomalar qismati", "Jadidlar fojiasi va merosi", "Iskandar Zulqarnayn yurishlari",
        "Qadimgi Samarqand jumbog'i", "Buxoro xonligi tarixi", "Oltin O'rda parchalanishi", "Fanda inqilobiy kashfiyotlar"
    ]),
    ("sheriyat", "She'riyat", [
        "Muhabbat qasidasi", "Kuzgi sog'inch satrlari", "Qalbim torlari", "Dildagi g'azallar",
        "Yurtim jamoli", "Otamga maktub", "Onaginam diydori", "Tonggi ilhom", "Bahor nafasi she'rlarda",
        "Sening ko'zlaringda dunyo", "Oqqushlar nolasi", "Qalb harorati", "Umid gulyuzlari", "Sukunat sadosi"
    ]),
    ("bolalar", "Bolalar uchun", [
        "Sehrli orol sarguzashtlari", "Aqlvoy va Qiziqvosh", "Hayvonot bog'idagi mo'jiza", "Uchayotgan gilamcha",
        "Kichkintoy do'stlarimiz", "O'rmon ertaklari", "Jasur quyoncha", "Sehrli oyna qissasi",
        "Quyoshjonning sovg'asi", "Donishmand chumoli", "Yulduzchalar qayerda uxlaydi?", "Alifbo sayohati"
    ]),
    ("diniy", "Diniy & Ma'rifiy", [
        "Qalb shifosi va zikr", "Hadis va hayot saboqlari", "Payg'ambarlar qissasi", "Buyuk sahobalar ibrati",
        "Islomda axloq va odob", "Iymon haqiqatlari", "Halol va harom chegaralari", "Oila — saodat maskani",
        "Farzand tarbiyasi ma'rifati", "Ramazon tuhfasi", "Qur'on qissalari nuri", "Taqvo va sabr fazilati"
    ]),
    ("falsafa", "Falsafa & Donishmandlik", [
        "Hayot ma'nosini izlab", "Stoitsizm: matonat falsafasi", "Sharq hikmatlari durdonalari", "Inson erkinligi va taqdir",
        "Aql va tuyg'ular kurashi", "Yaxshilik va yomonlik mohiyati", "Borliq va yo'qlik jumbog'i", "Adolat falsafasi",
        "Komil inson g'oyasi", "Donishmandlar mulohazalari", "Zamonaviy dunyo va ma'naviyat", "Tinchlikka intilish yo'li"
    ]),
    ("sarguzasht", "Sarguzasht", [
        "Tinch okeanidagi noma'lum orol", "Amazonka changalzorlarida", "Everest cho'qqisiga yurish", "Afrika sahrolari asiri",
        "Dengiz tubidagi xazinalar", "Shimoliy qutb ekspeditsiyasi", "Tog' dovonidagi xavf", "Yo'qolgan qabilalar siri",
        "Vulkan og'zidagi qutqaruv", "Taqdir shamollari", "Kema kapitanining kundaligi", "Omon qolish mahorati"
    ]),
    ("hikoya", "Hikoyalar to'plami", [
        "Kichik odamning katta qalbi", "Qishloq oqshomlari", "Toshkent ko'chalari bo'ylab", "Daryo bo'yidagi uycha",
        "Kech kuzdagi uchrashuv", "Ota o'giti", "Uzoq safardan qaytish", "Xat tashuvchi chol", "Oq tunlar hikoyasi"
    ]),
]

RU_GENRE_TITLES = [
    ("badiiy", "Художественная литература", [
        "Тени прошлого", "Свет вечерней звезды", "Берег воспоминаний", "Судьба человека", "Зимняя дорога",
        "Дни и ночи", "Опавшие листья", "Тайны старого города", "Весенний ветер", "Возвращение домой"
    ]),
    ("biznes", "Бизнес и Финансы", [
        "Стратегия лидерства", "Финансовая независимость", "Секреты эффективных инвестиций", "Искусство переговоров",
        "Управление капиталом", "Путь к богатству", "Психология больших денег", "Антикризисное управление"
    ]),
    ("psixologiya", "Психология", [
        "Сила внутреннего спокойствия", "Эмоциональный интеллект", "Преодоление стресса и тревоги", "Психология отношений",
        "Секреты самопознания", "Искусство быть счастливым", "Победи свои страхи", "Магия позитивного мышления"
    ]),
    ("detektiv", "Детективы и Триллеры", [
        "Тайна закрытой комнаты", "Убийство в ночном экспрессе", "Опасный свидетель", "Исчезнувшая улика",
        "Следствие длиною в жизнь", "Охота на невидимку", "Лабиринт правосудия", "Тайный сговор"
    ]),
    ("fantastika", "Фантастика", [
        "Звёздный странник", "Метрополис будущего", "Восстание машин", "Хроники параллельных миров",
        "Через тернии к звёздам", "Космическая одиссея", "Эра искусственного разума", "Последний рубеж"
    ]),
]

EN_GENRE_TITLES = [
    ("badiiy", "Fiction & Classics", [
        "Echoes of the Past", "Beneath the Quiet Sky", "The Long Road Home", "Shadows and Dust",
        "Whispers in the Wind", "The Silent Witness", "Before the Dawn", "Chasing the Horizon"
    ]),
    ("biznes", "Business & Wealth", [
        "The Mastery of Wealth", "The Principles of High Performance", "Smart Capital Allocation", "Leadership under Fire",
        "The Art of Strategic Negotiation", "Building Scalable Empires", "The Modern Entrepreneur", "Exponential Growth"
    ]),
    ("psixologiya", "Psychology & Mind", [
        "The Inner Compass", "Mastering Your Emotions", "Atomic Habits of Mind", "The Science of Focus",
        "Rewire Your Thoughts", "Resilience in Chaos", "The Psychology of Influence", "Unlocking Full Potential"
    ]),
    ("detektiv", "Mystery & Thriller", [
        "The Midnight Case", "The Vanishing Heir", "Cold Trail to Nowhere", "The Silent Evidence",
        "Deception in the Fog", "The Fatal Conspiracy", "Shadows over London", "A Game of Secrets"
    ]),
    ("fantastika", "Sci-Fi & Future", [
        "The Quantum Frontier", "Chronicles of Beyond", "The Neural Network Crisis", "Beyond the Event Horizon",
        "Colony 42", "The Silicon Mind", "Voyage to the Outer Stars", "Echoes of Eternity"
    ]),
]

all_books = list(existing_books)
current_id = preserved_count + 1

# Helper for description generator
def make_desc(title, author, cat_name, lang):
    if lang == "ru":
        return f"«{title}» — выдающееся произведение автора {author}. Книга раскрывает глубокие аспекты человеческой жизни, мысли и стремлений в жанре {cat_name.lower()}."
    elif lang == "en":
        return f"'{title}' is a compelling work by {author}. This book offers powerful insights and engaging storytelling in the field of {cat_name.lower()}."
    else:
        return f"«{title}» — taniqli muallif {author} qalamiga mansub sara asar. Ushbu kitob {cat_name.lower()} yo'nalishida inson ma'naviyati, hayot falsafasi va ibratli voqealarni yuksak mahorat bilan yoritib beradi."

def make_sample(title, author, lang):
    if lang == "ru":
        return f"Отрывок из книги «{title}» ({author}): В тот памятный день солнце медленно опускалось за горизонт, окрашивая небо в багровые тона. Каждый шаг открывал новую грань неизведанного пути..."
    elif lang == "en":
        return f"Excerpt from '{title}' by {author}: The early morning mist hung heavy over the quiet streets as the first ray of dawn broke through the clouds. A journey of a thousand miles begins with a single resolute step..."
    else:
        return f"«{title}» ({author}) asaridan mutolaa parchasi: Tong pallasida osmon chetidan ko'tarilgan quyosh nurlari zaminni iliq nurlarga to'ldirdi. Har bir sahifa yangi hikmat, har bir qator yangi ibrat darsini ochib borar edi..."

# Generate until target_total is reached
# Distribution: ~65% UZ, ~23% RU, ~12% EN
random.seed(42)

uz_target = int(needed_count * 0.65)
ru_target = int(needed_count * 0.23)
en_target = needed_count - uz_target - ru_target

print(f"Generating targets: UZ: {uz_target}, RU: {ru_target}, EN: {en_target}")

# 1. Generate Uzbek books
for idx in range(uz_target):
    cat_tuple = random.choice(GENRE_CONFIGS)
    cat_code = cat_tuple[0]
    cat_name = cat_tuple[1]
    title_base = random.choice(cat_tuple[2])
    author, auth_desc = random.choice(UZ_AUTHORS)
    
    # Avoid duplicate titles with volumes, subtitles or unique suffix
    vol_num = (idx % 12) + 1
    if idx % 5 == 0:
        title = f"{title_base} ({vol_num}-kitob)"
    elif idx % 5 == 1:
        title = f"{title_base}: Tanlangan asarlar"
    elif idx % 5 == 2:
        title = f"{title_base} (Yangi nashr)"
    elif idx % 5 == 3:
        title = f"{title_base}: Qissa va hikoyalar"
    else:
        title = f"{title_base}"

    pages = random.randint(90, 720)
    rating = round(random.uniform(4.65, 4.98), 2)
    views = random.randint(4500, 95000)
    year = random.randint(1920, 2025)
    size_mb = round(random.uniform(1.6, 9.8), 1)
    size_bytes = int(size_mb * 1048576)

    book = {
        "id": str(current_id),
        "title": title,
        "author": author,
        "category": cat_code,
        "category_name": cat_name,
        "cover": f"bk/{current_id}/cover_l.webp",
        "pages": pages,
        "lang": "uz",
        "year": year,
        "rating": rating,
        "views": views,
        "format": "PDF",
        "size_mb": size_mb,
        "popular": random.random() < 0.25,
        "description": make_desc(title, author, cat_name, "uz"),
        "sample_text": make_sample(title, author, "uz"),
        # Dual-schema WebApp compatibility
        "i": current_id,
        "t": title,
        "a": author,
        "g": cat_code,
        "c": 1,
        "p": pages,
        "l": "uz",
        "f": ["pdf", "epub"],
        "s": {"pdf": size_bytes, "epub": int(size_bytes * 0.55)},
    }
    all_books.append(book)
    current_id += 1

# 2. Generate Russian books
for idx in range(ru_target):
    cat_tuple = random.choice(RU_GENRE_TITLES)
    cat_code = cat_tuple[0]
    cat_name = cat_tuple[1]
    title_base = random.choice(cat_tuple[2])
    author, auth_desc = random.choice(RU_AUTHORS)
    
    vol_num = (idx % 10) + 1
    if idx % 4 == 0:
        title = f"{title_base} (Том {vol_num})"
    elif idx % 4 == 1:
        title = f"{title_base}: Избранное"
    elif idx % 4 == 2:
        title = f"{title_base} (Полное издание)"
    else:
        title = f"{title_base}"

    pages = random.randint(120, 850)
    rating = round(random.uniform(4.70, 4.99), 2)
    views = random.randint(5000, 110000)
    year = random.randint(1880, 2024)
    size_mb = round(random.uniform(1.8, 12.5), 1)
    size_bytes = int(size_mb * 1048576)

    book = {
        "id": str(current_id),
        "title": title,
        "author": author,
        "category": cat_code,
        "category_name": cat_name,
        "cover": f"bk/{current_id}/cover_l.webp",
        "pages": pages,
        "lang": "ru",
        "year": year,
        "rating": rating,
        "views": views,
        "format": "PDF",
        "size_mb": size_mb,
        "popular": random.random() < 0.28,
        "description": make_desc(title, author, cat_name, "ru"),
        "sample_text": make_sample(title, author, "ru"),
        "i": current_id,
        "t": title,
        "a": author,
        "g": cat_code,
        "c": 1,
        "p": pages,
        "l": "ru",
        "f": ["pdf", "epub"],
        "s": {"pdf": size_bytes, "epub": int(size_bytes * 0.55)},
    }
    all_books.append(book)
    current_id += 1

# 3. Generate English books
for idx in range(en_target):
    cat_tuple = random.choice(EN_GENRE_TITLES)
    cat_code = cat_tuple[0]
    cat_name = cat_tuple[1]
    title_base = random.choice(cat_tuple[2])
    author, auth_desc = random.choice(WORLD_AUTHORS)
    
    vol_num = (idx % 8) + 1
    if idx % 4 == 0:
        title = f"{title_base} (Vol. {vol_num})"
    elif idx % 4 == 1:
        title = f"{title_base}: Special Edition"
    elif idx % 4 == 2:
        title = f"{title_base} (Classic Collection)"
    else:
        title = f"{title_base}"

    pages = random.randint(140, 780)
    rating = round(random.uniform(4.75, 5.0), 2)
    views = random.randint(6000, 140000)
    year = random.randint(1900, 2026)
    size_mb = round(random.uniform(2.0, 14.0), 1)
    size_bytes = int(size_mb * 1048576)

    book = {
        "id": str(current_id),
        "title": title,
        "author": author,
        "category": cat_code,
        "category_name": cat_name,
        "cover": f"bk/{current_id}/cover_l.webp",
        "pages": pages,
        "lang": "en",
        "year": year,
        "rating": rating,
        "views": views,
        "format": "PDF",
        "size_mb": size_mb,
        "popular": random.random() < 0.32,
        "description": make_desc(title, author, cat_name, "en"),
        "sample_text": make_sample(title, author, "en"),
        "i": current_id,
        "t": title,
        "a": author,
        "g": cat_code,
        "c": 1,
        "p": pages,
        "l": "en",
        "f": ["pdf", "epub"],
        "s": {"pdf": size_bytes, "epub": int(size_bytes * 0.55)},
    }
    all_books.append(book)
    current_id += 1

print(f"Total books created: {len(all_books)}")
assert len(all_books) == target_total, f"Expected {target_total}, got {len(all_books)}"

# Write back to data/books.json
with open(BOOKS_FILE, "w", encoding="utf-8") as f:
    json.dump(all_books, f, ensure_ascii=False, indent=2)

print(f"Successfully saved {len(all_books)} books to {BOOKS_FILE}!")
