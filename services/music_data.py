"""
Mini App uchun Musiqa ma'lumotlari (Top 50, O'zbek xitlari, Kayfiyatlar)
"""
from typing import List, Dict, Any

TOP_50_TRACKS: List[Dict[str, Any]] = [
    {"id": 1, "title": "O'ylama", "artist": "Konsta", "duration": "3:24", "category": "uzb", "mood": "relax", "cover": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"},
    {"id": 2, "title": "Men edim", "artist": "Jaloliddin Ahmadaliyev", "duration": "4:12", "category": "uzb", "mood": "romantic", "cover": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"},
    {"id": 3, "title": "Xayolim", "artist": "Rayhon", "duration": "3:45", "category": "uzb", "mood": "romantic", "cover": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"},
    {"id": 4, "title": "Yig'lama qizaloq", "artist": "Shohruxxon", "duration": "3:18", "category": "uzb", "mood": "party", "cover": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3"},
    {"id": 5, "title": "Asalim", "artist": "Xamdam Sobirov", "duration": "3:30", "category": "uzb", "mood": "party", "cover": "https://images.unsplash.com/photo-1487180144351-b8472da7d491?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3"},
    {"id": 6, "title": "Yomg'ir", "artist": "Sevara Nazarkhan", "duration": "4:05", "category": "uzb", "mood": "relax", "cover": "https://images.unsplash.com/photo-1445985543470-41fdd6ce388d?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3"},
    {"id": 7, "title": "Sevgi bu", "artist": "Munisa Rizayeva", "duration": "3:52", "category": "uzb", "mood": "party", "cover": "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3"},
    {"id": 8, "title": "Kechir meni", "artist": "Ummon", "duration": "4:15", "category": "uzb", "mood": "romantic", "cover": "https://images.unsplash.com/photo-1485579149621-3123dd979885?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3"},
    {"id": 9, "title": "Gulim", "artist": "Konsta & Timur", "duration": "3:40", "category": "uzb", "mood": "drive", "cover": "https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3"},
    {"id": 10, "title": "Yurak", "artist": "Dildora Niyozova", "duration": "3:58", "category": "uzb", "mood": "relax", "cover": "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3"},
    {"id": 11, "title": "Blinding Lights", "artist": "The Weeknd", "duration": "3:20", "category": "top50", "mood": "drive", "cover": "https://images.unsplash.com/photo-1518609878373-06d740f60d8b?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"},
    {"id": 12, "title": "Levitating", "artist": "Dua Lipa", "duration": "3:23", "category": "top50", "mood": "workout", "cover": "https://images.unsplash.com/photo-1465847899084-d164df4dedc6?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"},
    {"id": 13, "title": "Shape of You", "artist": "Ed Sheeran", "duration": "3:53", "category": "top50", "mood": "workout", "cover": "https://images.unsplash.com/photo-1447069387593-a5de0862481e?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"},
    {"id": 14, "title": "Believer", "artist": "Imagine Dragons", "duration": "3:24", "category": "top50", "mood": "workout", "cover": "https://images.unsplash.com/photo-1501386761578-eac5c94b800a?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3"},
    {"id": 15, "title": "Stay", "artist": "The Kid LAROI & Justin Bieber", "duration": "2:21", "category": "top50", "mood": "drive", "cover": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3"},
    {"id": 16, "title": "Mockingbird", "artist": "Eminem", "duration": "4:10", "category": "top50", "mood": "drive", "cover": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3"},
    {"id": 17, "title": "Starboy", "artist": "The Weeknd & Daft Punk", "duration": "3:50", "category": "top50", "mood": "drive", "cover": "https://images.unsplash.com/photo-1506157786151-b8491531f063?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3"},
    {"id": 18, "title": "Bad Guy", "artist": "Billie Eilish", "duration": "3:14", "category": "top50", "mood": "workout", "cover": "https://images.unsplash.com/photo-1520523839898-50712825e3a7?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3"},
    {"id": 19, "title": "Lovely", "artist": "Billie Eilish & Khalid", "duration": "3:20", "category": "top50", "mood": "relax", "cover": "https://images.unsplash.com/photo-1483032469466-b937c425697b?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3"},
    {"id": 20, "title": "Medina", "artist": "Jah Khalib", "duration": "3:40", "category": "top50", "mood": "romantic", "cover": "https://images.unsplash.com/photo-1458560871784-56d23406c091?w=200", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3"},
]

# Qo'shimcha 30 ta trek bilan Top 50 to'ldiriladi
EXTRA_TRACKS = [
    ("Leila", "Jah Khalib", "drive"),
    ("Uletay", "MiyaGi & Andy Panda", "relax"),
    ("Tamada", "MiyaGi & Endshpil", "drive"),
    ("Minor", "Miyagi & Andy Panda", "relax"),
    ("Gori", "Jony", "romantic"),
    ("Kometa", "Jony", "romantic"),
    ("Mne ne smeshno", "Rauf & Faik", "romantic"),
    ("Detstvo", "Rauf & Faik", "relax"),
    ("Poshevelis", "Navai", "party"),
    ("Ptichka", "HammAli & Navai", "romantic"),
    ("Pryatki", "HammAli & Navai", "drive"),
    ("Yana kel", "Shohrux", "drive"),
    ("Xayr bevafo", "Tohir Sodiqov (Bolalar)", "romantic"),
    ("Esingdami seni", "Bolalar", "relax"),
    ("Kerak emas", "Bolalar", "romantic"),
    ("Sen ketma", "Setora", "romantic"),
    ("Ajdodlar ruhi", "Yulduz Usmonova", "party"),
    ("Sanamjon", "Yulduz Usmonova", "party"),
    ("Zor-zor", "Janob Rasul", "party"),
    ("Gulyor", "Janob Rasul", "party"),
    ("Daryo bo'yida", "Ozoda Nursaidova", "party"),
    ("Dilbarim", "Ozoda Nursaidova", "party"),
    ("Muhabbat", "Doston Ubaydullayev", "relax"),
    ("Alla bolam", "O'zbek xalq allasi", "kids"),
    ("Quvnoq bolalar", "Bolalar bog'chasi", "kids"),
    ("Chertmak", "Bolalar ashulasi", "kids"),
    ("Energy Boost", "Workout EDM Beats", "workout"),
    ("Hard Power Gym", "Fitness Bass", "workout"),
    ("Night Drive", "Synthwave Retro", "drive"),
    ("Midnight Chill", "Lo-Fi Beats Cafe", "relax"),
]

for idx, (t, a, m) in enumerate(EXTRA_TRACKS, start=21):
    cat = "uzb" if any(u in a.lower() for u in ["bolalar", "shohrux", "yulduz", "janob", "ozoda", "doston", "o'zbek", "setora"]) else "top50"
    TOP_50_TRACKS.append({
        "id": idx,
        "title": t,
        "artist": a,
        "duration": f"3:{20 + (idx % 35):02d}",
        "category": cat,
        "mood": m,
        "cover": f"https://images.unsplash.com/photo-{1511671782779 + (idx * 137) % 10000}?w=200",
        "url": f"https://www.soundhelix.com/examples/mp3/SoundHelix-Song-{(idx % 15) + 1}.mp3",
    })

MOODS_LIST = [
    {"key": "all", "title": "Barchasi", "icon": "🎵"},
    {"key": "workout", "title": "Mashg'ulot (Sport)", "icon": "🏋️‍♂️"},
    {"key": "drive", "title": "Yo'lda (Avtomobil)", "icon": "🚗"},
    {"key": "romantic", "title": "Romantik (Sevgi)", "icon": "❤️"},
    {"key": "relax", "title": "Dam olish (Relax)", "icon": "☕"},
    {"key": "party", "title": "Kayfiyat (Raqs)", "icon": "🎉"},
    {"key": "kids", "title": "Bolalar uchun", "icon": "👶"},
]
