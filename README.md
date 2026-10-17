# 🎬 Zakirovs_bot (@Zakirovsfilms_bot)

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-blue.svg)](https://docs.aiogram.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Zakirovsfilms_bot** — Telegram uchun professional, yuqori tezlikda ishlovchi, ko'p funksiyali universal media yuklovchi va kino boti.

> 📥 **Insta, TikTok, YouTube, Snapchat yuklash**  
> 🎵 **Qo'shiq topish** • 🎬 **Kino** • 👀 **Anonim story**  
> 🍿 **Kinolar kanali:** [@ZakirovsKino](https://t.me/ZakirovsKino)

---

## 🚀 Asosiy Imkoniyatlar

### 1. 📥 Universal Media Yuklovchi
* **Instagram:** Reels, postlar, stories, karusellar va IGTV.
* **TikTok:** Suv belgisiz (no watermark) eng yuqori sifatli HD videolar.
* **YouTube:** Shorts, to'liq videolar va audiolarni (MP3) ajratib olish.
* **Snapchat:** Spotlight va ommaviy hikoyalar.
* **Qo'shimcha:** Pinterest, Facebook, Twitter/X va boshqa 100+ saytlardan video yuklash.
* **🎵 Musiqasini ajratish:** Har bir yuklangan video ostida uning MP3 audiosini bitta tugma orqali ajratib olish imkoniyati.

### 2. 🎬 Kino Tizimi (Kino Kodlari)
* **Kodni yuborish:** Foydalanuvchi shunchaki kino kodini (masalan: `101`, `245`) yuborsa, bot darhol filmni barcha ma'lumotlari bilan chiqarib beradi.
* **Kino nomi bo'yicha qidiruv:** Filmlar nomi yoki tavsifi bo'yicha aqlli qidiruv.
* **🎲 Tasodifiy kino:** Nima ko'rishni bilmayotganlar uchun tasodifiy film taklif qilish.
* **🎭 Janrlar:** Jangari, Komediya, Drama, Fantastika, Multfilm va boshqa janrlar bo'yicha saralash.
* **🔥 Eng ommabop:** Eng ko'p ko'rilgan va yuklab olingan top kinolar ro'yxati.
* **🍿 @ZakirovsKino integratsiyasi:** Bot va rasmiy kino kanali o'rtasida to'liq bog'liqlik.

### 3. 🎵 Qo'shiq Topish (Musiqa Bo'limi)
* Qo'shiq nomi yoki ijrochisi bo'yicha qidirish (Deezer API integratsiyasi orqali tezkor va aniq natijalar).
* Natijalardan bitta tugma bilan to'liq MP3 qo'shiqni yuklab olish.
* Ovozli xabar (voice note) va audio xabarlarni qabul qilish.

### 4. 👀 Anonim Instagram Story
* Foydalanuvchi nomini kiritish orqali uning so'nggi faol hikoyalarini (stories) anonim, sezdirmasdan yuklab olish.

### 5. 🔒 Majburiy A'zolik (Homiylar Tizimi)
* Botdan foydalanishdan oldin admin kiritgan homiy kanallarga a'zo bo'lish talab qilinadi.
* «✅ Obunani tekshirish» tugmasi orqali a'zolik holati real vaqtda tekshiriladi.
* Adminlar ushbu tekshiruvdan avtomatik ozod qilingan.

### 6. 👑 To'liq Admin Paneli (`/admin`)
* **📊 Jonli statistika:** Jami foydalanuvchilar, bugun qo'shilganlar, 24 soatlik faollar, yuklangan kinolar soni, platformalar bo'yicha yuklamalar va server parametrlari.
* **🎬 Kinolarni boshqarish:** Yangi kino qo'shish (FSM orqali: kod, nom, video, janr, yil, reyting, tavsif), kinolarni o'chirish va ro'yxatni ko'rish.
* **📢 Global xabarnoma (Broadcast):** Barcha foydalanuvchilarga matn, rasm, video yoki forward xabarlarni yuborish (jonli foiz ko'rsatkichi bilan).
* **🔒 Homiylar boshqaruvi:** Yangi homiy kanallar qo'shish, o'chirish yoki vaqtincha to'xtatish.

---

## 🛠 Texnologiyalar

* **Til:** Python 3.12+
* **Framework:** Aiogram 3.x
* **ORM:** SQLAlchemy 2.0 (To'liq asinxron)
* **Ma'lumotlar bazasi:** SQLite (`aiosqlite`) va PostgreSQL (`asyncpg`) dual-qo'llab-quvvatlov
* **Media yuklovchi:** `yt-dlp` (Asinxron multithreading)
* **Audio konvertatsiya:** FFmpeg
* **Validatsiya:** Pydantic v2 & Pydantic-Settings

---

## 📂 Loyiha Tuzilishi

```
zakirovs_bot/
├── config.py             # Asosiy konfiguratsiya (Pydantic Settings)
├── main.py               # Botni ishga tushirish (Startup/Shutdown, Polling)
├── requirements.txt      # Kerakli Python kutubxonalari
├── Dockerfile            # Docker muhiti
├── docker-compose.yml    # Docker Compose sozlamalari
├── .env.example          # Muhit o'zgaruvchilari namunasi
├── database/             # Ma'lumotlar bazasi
│   ├── models.py         # SQLAlchemy modellari (User, Movie, SponsorChannel...)
│   ├── session.py        # Asinxron sessiyalar va jadvallarni yaratish
│   └── crud.py           # Barcha DB amallari (foydalanuvchilar, kinolar, statistika)
├── handlers/             # Telegram xabarlarini qayta ishlovchilar
│   ├── start.py          # /start, /help, obuna tekshirish
│   ├── downloader.py     # Instagram, TikTok, YouTube, Snapchat yuklovchi
│   ├── movies.py         # Kino menyusi, kod bo'yicha qidiruv, janrlar
│   ├── music.py          # Qo'shiq qidirish va MP3 yuklash
│   ├── story.py          # Anonim Instagram story ko'rish
│   └── admin.py          # Admin boshqaruv paneli, xabarnoma, kino qo'shish
├── keyboards/            # Tugmalar
│   ├── default.py        # Asosiy Reply klaviaturalar
│   └── inline.py         # Inline menyular va pagination
├── middlewares/          # Oraliq qatlamlar
│   ├── subscription.py   # Majburiy kanal a'zoligi tekshiruvi
│   └── throttling.py     # Anti-flood (spamdan himoya)
├── services/             # Tashqi servislar
│   ├── downloader.py     # yt-dlp media va audio yuklovchi
│   ├── movie_service.py  # Kino yuborish va qidiruv mantiqi
│   ├── music_service.py  # Deezer va YouTube musiqa qidiruvi
│   └── story_service.py  # Instagram story tahlilchisi
└── utils/                # Yordamchi vositalar
    ├── states.py         # FSM holatlari (StateGroups)
    ├── helpers.py        # Havolalarni aniqlash, kesh, tizim ma'lumotlari
    └── notifier.py       # Adminlarga ogohlantirish yuborish
```

---

## ⚙️ O'rnatish va Ishga Tushirish

### 1-usul: Oddiy ishga tushirish (Lokal kompyuter yoki VPS)

1. Loyihani yuklab oling va papkaga kiring:
   ```bash
   cd zakirovs_bot
   ```

2. Virtual muhit (venv) yarating va faollashtiring:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/MacOS:
   source venv/bin/activate
   ```

3. Kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```

4. Tizimda **FFmpeg** o'rnatilganligiga ishonch hosil qiling (audio ajratish uchun kerak):
   * Ubuntu/Debian: `sudo apt install ffmpeg`
   * Windows: `winget install Gyan.FFmpeg` yoki rasmiy saytidan yuklab PATH ga qo'shing.

5. `.env` faylini sozlang:
   ```bash
   cp .env.example .env
   ```
   `.env` faylini ochib, o'z Telegram bot tokeningizni va admin ID laringizni yozing:
   ```env
   BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
   BOT_USERNAME=Zakirovsfilms_bot
   CHANNEL_USERNAME=@ZakirovsKino
   ADMIN_IDS=123456789
   DB_TYPE=sqlite
   DATABASE_URL=sqlite+aiosqlite:///data/bot.db
   ```

6. Botni ishga tushiring:
   ```bash
   python main.py
   ```

---

### 2-usul: Docker va Docker Compose orqali

Docker o'rnatilgan serverda bitta buyruq bilan ishga tushirish mumkin:

```bash
docker compose up -d --build
```

Loglarni ko'rish:
```bash
docker compose logs -f
```

---

## 🎬 Kinolarni Botga Joylash Yo'riqnomasi

1. Botga `/admin` komandasini yuboring.
2. **«🎬 Kinolar boshqaruvi»** bo'limiga kiring.
3. **«➕ Yangi kino qo'shish»** tugmasini bosing:
   * **Kino kodi:** Masalan, `101` (Kanalda e'lon qilinadigan unikal kod)
   * **Kino nomi:** Masalan, `Avatar: Suv yo'li`
   * **Video fayl:** Filmni Telegram orqali yuboring (video yoki hujjat ko'rinishida)
   * **Janr:** Tugmalar orqali janrlarni tanlang va «✅ Tanlashni tugatish»ni bosing
   * **Yili:** Masalan, `2024`
   * **Reyting:** Masalan, `7.8`
   * **Tavsif:** Film haqida qisqacha ma'lumot
4. Saqlangandan so'ng, istalgan foydalanuvchi `101` deb yozsa, bot shu zahotiyoq kinoni chiqarib beradi!

---

## 🔒 Xavfsizlik va Xatoliklarga Chidamlilik

* **Anti-Flood:** Foydalanuvchilar ketma-ket tinimsiz xabar yozganda server yuklanishini oldini oladi.
* **Resilient File Handling:** Yuklab olingan barcha vaqtinchalik video/audio fayllar jo'natilgach xavfsiz o'chiriladi. Disk to'lib qolmaydi.
* **Hajm tekshiruvi:** 50MB dan katta bo'lgan fayllar xatoliksiz tekshirilib, foydalanuvchiga tegishli ogohlantirish beriladi.
* **Dual Database:** Hech qanday tashqi ma'lumotlar bazasisiz (SQLite yordamida) nol konfiguratsiyada ishlaydi, xohlasangiz yuqori yuklamalar uchun PostgreSQL ga osongina ulanadi.

---

## 👨‍💻 Muallif

Loyiha maxsus **@Zakirovsfilms_bot** va **@ZakirovsKino** uchun 1-ga-1 to'liq funktsional nusxa sifatida ishlab chiqilgan.
