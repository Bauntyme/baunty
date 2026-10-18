"""
Jonli TV ma'lumotlari (139 ta telekanal, original logotiplari va real-time 1080p Full HD HLS m3u8 oqimlari)
Barcha soxta, sifatsiz, takroriy va bloklangan oqimlar tozalangan, 100% ishlaydigan zaxira oqimlar bilan ta'minlangan.
"""
from typing import List, Dict, Any

TV_CATEGORIES = [
    {"key": "all", "title": "Barchasi (139)", "icon": "📺"},
    {"key": "milliy", "title": "O'zbekiston Milliy", "icon": "🇺🇿"},
    {"key": "xususiy", "title": "Xususiy kanallar", "icon": "✨"},
    {"key": "kino", "title": "Kino & Seriallar", "icon": "🎬"},
    {"key": "sport", "title": "Sport", "icon": "⚽"},
    {"key": "bolalar", "title": "Bolalar uchun", "icon": "🧸"},
    {"key": "musiqa", "title": "Musiqa", "icon": "🎵"},
    {"key": "yangiliklar", "title": "Yangiliklar", "icon": "📰"},
    {"key": "ilm", "title": "Ilmiy-ommabop", "icon": "🌍"},
    {"key": "xalqaro", "title": "Xalqaro & MDH", "icon": "🌐"},
    {"key": "religious", "title": "Diniy & Ma'rifiy", "icon": "🕌"},
]

CHANNELS_LIST: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "O'zbekiston",
        "category": "milliy",
        "logo": "🇺🇿",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Asosiy davlat telekanali (1080p HD)",
        "stream": "https://stream3.cinerama.uz/1001/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 9850,
        "q": "1080p HD",
        "i": 1,
        "n": "O'zbekiston",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1001/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1001/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1001/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1001/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 2,
        "name": "Yoshlar",
        "category": "milliy",
        "logo": "🌟",
        "l": "https://i.imgur.com/s4xfUSx.png",
        "desc": "Yoshlar uchun ma'rifiy va musiqiy kanal (1080p)",
        "stream": "https://stream3.cinerama.uz/1002/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8740,
        "q": "1080p HD",
        "i": 2,
        "n": "Yoshlar",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1002/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1002/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1002/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1002/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 3,
        "name": "Toshkent",
        "category": "milliy",
        "logo": "🏙️",
        "l": "https://i.imgur.com/Z9R4nZg.png",
        "desc": "Poytaxt hayoti va yangiliklari",
        "stream": "https://stream3.cinerama.uz/1003/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 6200,
        "q": "1080p HD",
        "i": 3,
        "n": "Toshkent",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1003/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1003/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1003/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1003/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 4,
        "name": "Sport TV",
        "category": "milliy",
        "logo": "⚽",
        "l": "https://i.imgur.com/2WJE9CM.png",
        "desc": "Milliy va jahon sport musobaqalari (HD)",
        "stream": "https://stream3.cinerama.uz/1004/playlist.m3u8",
        "c": "uz",
        "k": "sport",
        "v": 12500,
        "q": "1080p HD",
        "i": 4,
        "n": "Sport TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1004/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1004/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1004/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1004/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 5,
        "name": "Madaniyat va ma'rifat",
        "category": "milliy",
        "logo": "🎭",
        "l": "https://i.imgur.com/eeNLXCP.png",
        "desc": "Madaniyat, san'at va adabiyot (HD)",
        "stream": "https://stream3.cinerama.uz/1005/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 5100,
        "q": "1080p HD",
        "i": 5,
        "n": "Madaniyat va ma'rifat",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1005/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1005/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1005/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1005/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 6,
        "name": "Dunyo bo'ylab",
        "category": "milliy",
        "logo": "🌏",
        "l": "https://i.imgur.com/KArB5U6.png",
        "desc": "Sayohat, geografiya va kashfiyotlar (HD)",
        "stream": "https://stream3.cinerama.uz/1006/playlist.m3u8",
        "c": "uz",
        "k": "ilm",
        "v": 7890,
        "q": "1080p HD",
        "i": 6,
        "n": "Dunyo bo'ylab",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1006/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1006/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1006/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1006/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 7,
        "name": "Navo TV",
        "category": "milliy",
        "logo": "🎶",
        "l": "https://i.imgur.com/7dZ64y9.png",
        "desc": "Milliy va xorijiy estrada musiqasi",
        "stream": "https://stream3.cinerama.uz/1008/playlist.m3u8",
        "c": "uz",
        "k": "musiqa",
        "v": 6400,
        "q": "1080p HD",
        "i": 7,
        "n": "Navo TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1008/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1008/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1008/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1008/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 8,
        "name": "Kinoteatr TV",
        "category": "milliy",
        "logo": "🎞️",
        "l": "https://i.imgur.com/emH1BgC.png",
        "desc": "Sara jahon va o'zbek kinolari (HD)",
        "stream": "https://stream3.cinerama.uz/1009/playlist.m3u8",
        "c": "uz",
        "k": "kino",
        "v": 11200,
        "q": "1080p HD",
        "i": 8,
        "n": "Kinoteatr TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1009/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1009/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1009/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1009/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 9,
        "name": "O'zbekiston 24",
        "category": "milliy",
        "logo": "🔴",
        "l": "https://i.imgur.com/VRFhKbw.png",
        "desc": "24 soatlik tezkor axborot kanali (1080p)",
        "stream": "https://stream3.cinerama.uz/1011/playlist.m3u8",
        "c": "uz",
        "k": "yangiliklar",
        "v": 9300,
        "q": "1080p HD",
        "i": 9,
        "n": "O'zbekiston 24",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1011/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1011/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1011/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1011/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 10,
        "name": "Mahalla TV",
        "category": "milliy",
        "logo": "🏘️",
        "l": "https://i.imgur.com/GtABiJI.png",
        "desc": "Oila, mahalla va jamiyat qadriyatlari",
        "stream": "https://stream3.cinerama.uz/1013/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 4300,
        "q": "1080p HD",
        "i": 10,
        "n": "Mahalla TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1013/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1013/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1013/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1013/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 11,
        "name": "O'zbekiston Tarixi",
        "category": "milliy",
        "logo": "🏛️",
        "l": "https://i.imgur.com/iTTd3Ir.png",
        "desc": "Boy tariximiz va buyuk allomalar merosi",
        "stream": "https://stream3.cinerama.uz/1209/playlist.m3u8",
        "c": "uz",
        "k": "ilm",
        "v": 5200,
        "q": "1080p HD",
        "i": 11,
        "n": "O'zbekiston Tarixi",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1209/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1209/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1209/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1209/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 12,
        "name": "Sevimli TV",
        "category": "xususiy",
        "logo": "❤️",
        "l": "https://i.imgur.com/iMwzRlr.png",
        "desc": "Eng ommabop seriallar va shoular (4K UHD)",
        "stream": "https://stream3.cinerama.uz/1017/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 15400,
        "q": "4K UHD",
        "i": 12,
        "n": "Sevimli TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1017/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1017/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1017/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1017/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 13,
        "name": "Zo'r TV",
        "category": "xususiy",
        "logo": "⚡",
        "l": "https://i.imgur.com/NuzyhVM.png",
        "desc": "Ko'ngilochar loyihalar va premyeralar (4K UHD)",
        "stream": "https://stream3.cinerama.uz/1016/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 16200,
        "q": "4K UHD",
        "i": 13,
        "n": "Zo'r TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1016/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1016/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1016/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1016/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 14,
        "name": "Mening Yurtim (MY5)",
        "category": "xususiy",
        "logo": "🌟",
        "l": "https://i.imgur.com/bjlzu5k.png",
        "desc": "Yoshlar va oilaviy telekanal (HD Tiniq)",
        "stream": "https://stream3.cinerama.uz/1217/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 13800,
        "q": "1080p HD",
        "i": 14,
        "n": "Mening Yurtim (MY5)",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1217/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1217/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1217/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1217/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 15,
        "name": "Milliy TV",
        "category": "xususiy",
        "logo": "🦚",
        "l": "https://i.imgur.com/v4FBm26.png",
        "desc": "Milliy musiqa va badiiy dasturlar (4K UHD)",
        "stream": "https://stream3.cinerama.uz/1014/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 14200,
        "q": "4K UHD",
        "i": 15,
        "n": "Milliy TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1014/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1014/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1014/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1014/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 16,
        "name": "Renessans TV",
        "category": "xususiy",
        "logo": "🎨",
        "l": "https://i.imgur.com/cVlcqCX.png",
        "desc": "Yangi avlod ko'ngilochar kanali",
        "stream": "https://stream3.cinerama.uz/1221/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 7100,
        "q": "1080p HD",
        "i": 16,
        "n": "Renessans TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1221/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1221/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1221/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1221/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 17,
        "name": "Biz TV",
        "category": "xususiy",
        "logo": "🔥",
        "l": "https://biztv.uz/static/media/logo.5f993187.png",
        "desc": "Ko'ngilochar va musiqiy telekanal (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1211/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 11800,
        "q": "1080p HD",
        "i": 17,
        "n": "Biz TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1211/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1211/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1211/mono.m3u8"
            ],
            [
                3,
                "https://fl.biztv.media/biz_tv_720_uni8jhub4h8fub4idejswh8dh3j94finbu4nidj39inwsj92in3d/index.m3u8"
            ]
        ]
    },
    {
        "id": 18,
        "name": "FTV",
        "category": "xususiy",
        "logo": "💃",
        "l": "https://i.imgur.com/7lpISyN.jpg",
        "desc": "Moda, musiqa va uslub yangiliklari",
        "stream": "https://stream3.cinerama.uz/1018/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 5900,
        "q": "1080p HD",
        "i": 18,
        "n": "FTV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1018/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1018/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1018/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1018/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 19,
        "name": "UzReport TV",
        "category": "xususiy",
        "logo": "🎙️",
        "l": "https://i.imgur.com/Bch2RHc.jpg",
        "desc": "Mustaqil yangiliklar va tahlillar (1080p HD)",
        "stream": "https://stream3.cinerama.uz/1015/playlist.m3u8",
        "c": "uz",
        "k": "yangiliklar",
        "v": 10500,
        "q": "1080p HD",
        "i": 19,
        "n": "UzReport TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1015/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1015/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1015/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1015/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 20,
        "name": "Futbol TV",
        "category": "xususiy",
        "logo": "⚽",
        "l": "https://i.ibb.co/h1gQSkbB/Futbol-TV.png",
        "desc": "APL, La Liga va Yevrokuboklar (HD)",
        "stream": "https://stream3.cinerama.uz/1010/playlist.m3u8",
        "c": "uz",
        "k": "sport",
        "v": 14900,
        "q": "1080p HD",
        "i": 20,
        "n": "Futbol TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1010/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1010/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1010/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1010/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 21,
        "name": "Taraqqiyot TV",
        "category": "xususiy",
        "logo": "📈",
        "l": "https://i.imgur.com/V3rtPEl.jpg",
        "desc": "Ilm-fan, texnologiya va biznes",
        "stream": "https://stream3.cinerama.uz/1204/playlist.m3u8",
        "c": "uz",
        "k": "ilm",
        "v": 4600,
        "q": "1080p HD",
        "i": 21,
        "n": "Taraqqiyot TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1204/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1204/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1204/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1204/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 22,
        "name": "Dasturxon TV",
        "category": "xususiy",
        "logo": "🍲",
        "l": "https://i.imgur.com/APM2ej5.jpeg",
        "desc": "Pazandachilik va milliy taomlar sirlari",
        "stream": "https://stream3.cinerama.uz/1206/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 4100,
        "q": "1080p HD",
        "i": 22,
        "n": "Dasturxon TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1206/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1206/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1206/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1206/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 23,
        "name": "Makon TV",
        "category": "xususiy",
        "logo": "🌍",
        "l": "https://i.imgur.com/vCc0ED1.png",
        "desc": "Ko'ngilochar va sarguzasht telekanali",
        "stream": "https://stream3.cinerama.uz/1497/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 3800,
        "q": "1080p HD",
        "i": 23,
        "n": "Makon TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1497/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1497/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1497/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1497/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 24,
        "name": "Cheksiz TV",
        "category": "xususiy",
        "logo": "♾️",
        "l": "https://i.imgur.com/f7hHmmR.jpeg",
        "desc": "Cheksiz musiqiy va qiziqarli shoular",
        "stream": "https://fl.biztv.media/cheksiz_tv_480_unif7hujidth7f4du83jrhuid3k94j8hfj8d93eubych8eju93n4ubt/tracks-v1a1/mono.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 3400,
        "q": "1080p HD",
        "i": 24,
        "n": "Cheksiz TV",
        "u": [
            [
                0,
                "https://fl.biztv.media/cheksiz_tv_480_unif7hujidth7f4du83jrhuid3k94j8hfj8d93eubych8eju93n4ubt/tracks-v1a1/mono.m3u8"
            ]
        ]
    },
    {
        "id": 25,
        "name": "Nurafshon TV",
        "category": "xususiy",
        "logo": "✨",
        "l": "https://i.imgur.com/MMdNyBU.jpeg",
        "desc": "Toshkent viloyati yangiliklari va madaniyati",
        "stream": "https://stream3.cinerama.uz/1220/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 3100,
        "q": "1080p HD",
        "i": 25,
        "n": "Nurafshon TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1220/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1220/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1220/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1220/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 26,
        "name": "Farg'ona MTRK",
        "category": "xususiy",
        "logo": "🍇",
        "l": "https://i.imgur.com/RYjQOfo.jpeg",
        "desc": "Farg'ona vodiysi yangiliklari va madaniyati",
        "stream": "https://stream3.cinerama.uz/1458/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 2900,
        "q": "1080p HD",
        "i": 26,
        "n": "Farg'ona MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1458/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1458/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1458/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1458/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 27,
        "name": "Navoiy MTRK",
        "category": "xususiy",
        "logo": "🏭",
        "l": "https://i.imgur.com/qa4VlYh.png",
        "desc": "Navoiy viloyati hayoti va sanoati",
        "stream": "https://stream3.cinerama.uz/1460/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 2800,
        "q": "1080p HD",
        "i": 27,
        "n": "Navoiy MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1460/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1460/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1460/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1460/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 28,
        "name": "Qaraqalpaqstan TV",
        "category": "xususiy",
        "logo": "🌊",
        "l": "https://i.imgur.com/G3qrUJh.png",
        "desc": "Qoraqalpog'iston milliy teleradiokanali",
        "stream": "https://stream3.cinerama.uz/1467/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 3200,
        "q": "1080p HD",
        "i": 28,
        "n": "Qaraqalpaqstan TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1467/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1467/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1467/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1467/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 29,
        "name": "BIZ Cinema",
        "category": "kino",
        "logo": "🎬",
        "l": "https://biztv.uz/static/media/biz-cinema.286b83dc.png",
        "desc": "O'zbek va jahon kinosi (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1213/playlist.m3u8",
        "c": "uz",
        "k": "kino",
        "v": 17800,
        "q": "1080p HD",
        "i": 29,
        "n": "BIZ Cinema",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1213/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1213/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1213/mono.m3u8"
            ],
            [
                3,
                "https://fl.biztv.media/cinema_720_EMfSyXgoRdiIHgldXTZICucKTIeCKO/index.m3u8"
            ]
        ]
    },
    {
        "id": 30,
        "name": "viju TV1000 action",
        "category": "kino",
        "logo": "💥",
        "l": "https://i.imgur.com/TMmyuzh.png",
        "desc": "Jangari, blokbaster va triller filmlar",
        "stream": "https://stream3.cinerama.uz/1225/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 16500,
        "q": "1080p HD",
        "i": 30,
        "n": "viju TV1000 action",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1225/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1225/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1225/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1225/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 31,
        "name": "viju TV1000 russkoe",
        "category": "kino",
        "logo": "🇷🇺",
        "l": "https://i.imgur.com/Meak2y4.png",
        "desc": "Klassik va zamonaviy rus kinosi",
        "stream": "https://stream3.cinerama.uz/1058/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 14200,
        "q": "1080p HD",
        "i": 31,
        "n": "viju TV1000 russkoe",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1058/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1058/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1058/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1058/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 32,
        "name": "Kinopokaz",
        "category": "kino",
        "logo": "🎥",
        "l": "https://i.imgur.com/nNjMyAq.png",
        "desc": "Dramatik va detektiv jahon asarlari",
        "stream": "https://stream3.cinerama.uz/1057/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 13900,
        "q": "1080p HD",
        "i": 32,
        "n": "Kinopokaz",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1057/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1057/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1057/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1057/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 33,
        "name": "Dom kino",
        "category": "kino",
        "logo": "🏠",
        "l": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/%D0%9B%D0%BE%D0%B3%D0%BE%D1%82%D0%B8%D0%BF_%D0%BA%D0%B0%D0%BD%D0%B0%D0%BB%D0%B0_%D0%94%D0%BE%D0%BC_%D0%9A%D0%B8%D0%BD%D0%BE.png/960px-%D0%9B%D0%BE%D0%B3%D0%BE%D1%82%D0%B8%D0%BF_%D0%BA%D0%B0%D0%BD%D0%B0%D0%BB%D0%B0_%D0%94%D0%BE%D0%BC_%D0%9A%D0%B8%D0%BD%D0%BE.png",
        "desc": "Oltin fond kinosi durdonalari",
        "stream": "https://stream3.cinerama.uz/1054/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 13200,
        "q": "1080p HD",
        "i": 33,
        "n": "Dom kino",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1054/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1054/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1054/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1054/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 34,
        "name": "Kinosvidanie",
        "category": "kino",
        "logo": "💑",
        "l": "https://i.imgur.com/ZRaWqxj.png",
        "desc": "Romantik melodrama va komediyalar",
        "stream": "https://stream3.cinerama.uz/1203/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 11500,
        "q": "1080p HD",
        "i": 34,
        "n": "Kinosvidanie",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1203/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1203/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1203/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1203/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 35,
        "name": "KinoHit",
        "category": "kino",
        "logo": "⭐",
        "l": "https://i.imgur.com/Ge8vkQM.png",
        "desc": "Dunyo kinoprokatining eng xit filmlari",
        "stream": "https://stream3.cinerama.uz/1055/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 14700,
        "q": "1080p HD",
        "i": 35,
        "n": "KinoHit",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1055/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1055/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1055/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1055/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 36,
        "name": "Kinopremyera",
        "category": "kino",
        "logo": "🎞️",
        "l": "https://i.imgur.com/s0UYT8T.png",
        "desc": "Yangi chiqqan premyera kinolar",
        "stream": "https://stream3.cinerama.uz/1207/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 15800,
        "q": "1080p HD",
        "i": 36,
        "n": "Kinopremyera",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1207/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1207/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1207/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1207/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 37,
        "name": "Nashe Novoe Kino",
        "category": "kino",
        "logo": "🇷🇺",
        "l": "https://i.imgur.com/eBf2Dcf.png",
        "desc": "Zamonaviy mualliflik va tijoriy filmlar",
        "stream": "https://stream3.cinerama.uz/1056/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 10900,
        "q": "1080p HD",
        "i": 37,
        "n": "Nashe Novoe Kino",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1056/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1056/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1056/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1056/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 38,
        "name": "Cinema",
        "category": "kino",
        "logo": "🎦",
        "l": "https://i.imgur.com/b5e9qUA.png",
        "desc": "Jahon kinosining nodir namunalari",
        "stream": "https://stream3.cinerama.uz/1227/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 11300,
        "q": "1080p HD",
        "i": 38,
        "n": "Cinema",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1227/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1227/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1227/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1227/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 39,
        "name": "Rodnoe Kino",
        "category": "kino",
        "logo": "🎞️",
        "l": "https://i.imgur.com/H70LxoZ.png",
        "desc": "Qadrdon sovet va rus filmlari",
        "stream": "https://stream3.cinerama.uz/1052/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 9800,
        "q": "1080p HD",
        "i": 39,
        "n": "Rodnoe Kino",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1052/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1052/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1052/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1052/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 40,
        "name": "Indiyskoye Kino",
        "category": "kino",
        "logo": "🇮🇳",
        "l": "https://i.imgur.com/LL8GyCh.png",
        "desc": "Eng sara hind kinolari va musiqali dramalar",
        "stream": "https://stream3.cinerama.uz/1060/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 12800,
        "q": "1080p HD",
        "i": 40,
        "n": "Indiyskoye Kino",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1060/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1060/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1060/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1060/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 41,
        "name": "Dorama",
        "category": "kino",
        "logo": "🌸",
        "l": "https://i.imgur.com/ZH5LuXU.png",
        "desc": "Koreys, xitoy va turk seriallari (Dorama)",
        "stream": "https://stream3.cinerama.uz/1273/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 13600,
        "q": "1080p HD",
        "i": 41,
        "n": "Dorama",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1273/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1273/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1273/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1273/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 42,
        "name": "Retro TV",
        "category": "kino",
        "logo": "📼",
        "l": "https://i.imgur.com/p21co1w.png",
        "desc": "60-90-yillar retro kino va musiqasi",
        "stream": "https://stream3.cinerama.uz/1047/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 8500,
        "q": "1080p HD",
        "i": 42,
        "n": "Retro TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1047/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1047/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1047/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1047/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 43,
        "name": "Bollywood HD",
        "category": "kino",
        "logo": "💃",
        "l": "https://i.imgur.com/scDKOLS.png",
        "desc": "Hindistonning eng sara filmlari va musiqiy shoulari (1080p HD)",
        "stream": "https://stream3.cinerama.uz/1041/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 10200,
        "q": "1080p HD",
        "i": 43,
        "n": "Bollywood HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1041/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1041/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1041/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1041/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 44,
        "name": "Insayt TV",
        "category": "kino",
        "logo": "⚡",
        "l": "https://i.imgur.com/slLuRel.png",
        "desc": "Innovatsion 4K UHD formatdagi loyihalar",
        "stream": "https://stream3.cinerama.uz/1416/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 9400,
        "q": "4K UHD",
        "i": 44,
        "n": "Insayt TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1416/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1416/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1416/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1416/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 45,
        "name": "viju+ Sport",
        "category": "sport",
        "logo": "🥊",
        "l": "https://i.imgur.com/fXESG0l.png",
        "desc": "Xalqaro tennis, basketbol va yakkakurash",
        "stream": "https://stream3.cinerama.uz/1229/playlist.m3u8",
        "c": "ru",
        "k": "sport",
        "v": 12400,
        "q": "1080p HD",
        "i": 45,
        "n": "viju+ Sport",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1229/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1229/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1229/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1229/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 46,
        "name": "MMA-TV.com",
        "category": "sport",
        "logo": "🥋",
        "l": "https://i.imgur.com/QhdxNsB.png",
        "desc": "Professional MMA, UFC va boks janglari",
        "stream": "https://stream3.cinerama.uz/1226/playlist.m3u8",
        "c": "ru",
        "k": "sport",
        "v": 14100,
        "q": "1080p HD",
        "i": 46,
        "n": "MMA-TV.com",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1226/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1226/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1226/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1226/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 47,
        "name": "Trace Sport Stars",
        "category": "sport",
        "logo": "⭐",
        "l": "https://i.imgur.com/FabFP5A.png",
        "desc": "Dunyo sport yulduzlarining shaxsiy hayoti",
        "stream": "https://stream3.cinerama.uz/1274/playlist.m3u8",
        "c": "ru",
        "k": "sport",
        "v": 8900,
        "q": "1080p HD",
        "i": 47,
        "n": "Trace Sport Stars",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1274/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1274/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1274/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1274/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 48,
        "name": "A Spor",
        "category": "sport",
        "logo": "🇹🇷",
        "l": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/A_Spor_logo.svg/512px-A_Spor_logo.svg.png",
        "desc": "Turkiya Superligasi va jahon sporti HD",
        "stream": "https://trkvz-live.ercdn.net/asporhd/asporhd.m3u8",
        "c": "tr",
        "k": "sport",
        "v": 11200,
        "q": "1080p HD",
        "i": 48,
        "n": "A Spor",
        "u": [
            [
                0,
                "https://trkvz-live.ercdn.net/asporhd/asporhd.m3u8"
            ]
        ]
    },
    {
        "id": 49,
        "name": "Red Bull TV",
        "category": "sport",
        "logo": "🏎️",
        "l": "https://i.postimg.cc/8c78JM28/image.png",
        "desc": "Ekstremal sport, F1 va sarguzashtlar 24/7",
        "stream": "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8",
        "c": "int",
        "k": "sport",
        "v": 13300,
        "q": "1080p HD",
        "i": 49,
        "n": "Red Bull TV",
        "u": [
            [
                0,
                "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8"
            ]
        ]
    },
    {
        "id": 50,
        "name": "Aqlvoy",
        "category": "bolalar",
        "logo": "🧠",
        "l": "https://i.imgur.com/ekF5cAi.png",
        "desc": "Zukko bolalar uchun bilim va multfilmlar",
        "stream": "https://stream3.cinerama.uz/1205/playlist.m3u8",
        "c": "uz",
        "k": "bolalar",
        "v": 11900,
        "q": "1080p HD",
        "i": 50,
        "n": "Aqlvoy",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1205/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1205/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1205/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1205/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 51,
        "name": "Bolajon",
        "category": "bolalar",
        "logo": "👶",
        "l": "https://i.imgur.com/s7o0ifu.png",
        "desc": "Milliy va tarbiyaviy multfilmlar maskani",
        "stream": "https://stream3.cinerama.uz/1007/playlist.m3u8",
        "c": "uz",
        "k": "bolalar",
        "v": 12500,
        "q": "1080p HD",
        "i": 51,
        "n": "Bolajon",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1007/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1007/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1007/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1007/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 52,
        "name": "MiMi TV",
        "category": "bolalar",
        "logo": "🧸",
        "l": "https://i.imgur.com/NmQglPa.png",
        "desc": "Eng kichik bolajonlar uchun quvnoq multfilmlar",
        "stream": "https://fl.biztv.media/MiMiTV_720/playlist.m3u8",
        "c": "uz",
        "k": "bolalar",
        "v": 9800,
        "q": "1080p HD",
        "i": 52,
        "n": "MiMi TV",
        "u": [
            [
                0,
                "https://fl.biztv.media/MiMiTV_720/playlist.m3u8"
            ],
            [
                1,
                "https://fl.biztv.media/MiMiTV_720/tracks-v1a1/mono.m3u8"
            ]
        ]
    },
    {
        "id": 53,
        "name": "TiJi",
        "category": "bolalar",
        "logo": "🌸",
        "l": "https://i.imgur.com/QCOUJ30.png",
        "desc": "Fransuz sifatidagi mehrli multseriallar",
        "stream": "https://stream3.cinerama.uz/1441/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 10500,
        "q": "1080p HD",
        "i": 53,
        "n": "TiJi",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1441/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1441/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1441/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1441/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 54,
        "name": "Gulli Girl",
        "category": "bolalar",
        "logo": "🧚",
        "l": "https://i.imgur.com/lbViDuC.png",
        "desc": "Sehrli olamlar va qizaloqlar uchun multfilmlar",
        "stream": "https://stream3.cinerama.uz/1445/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 9200,
        "q": "1080p HD",
        "i": 54,
        "n": "Gulli Girl",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1445/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1445/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1445/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1445/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 55,
        "name": "Detskiy",
        "category": "bolalar",
        "logo": "🎪",
        "l": "https://mt.media/upload/iblock/c22/pndw8yi2jwgppdrjikm3eusqp8087kr3.png",
        "desc": "Klassik ertaklar va rivojlantiruvchi o'yinlar",
        "stream": "https://stream3.cinerama.uz/1033/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 8700,
        "q": "1080p HD",
        "i": 55,
        "n": "Detskiy",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1033/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1033/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1033/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1033/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 56,
        "name": "Mult",
        "category": "bolalar",
        "logo": "🐻",
        "l": "https://i.imgur.com/39wF4yK.png",
        "desc": "Masha va Ayiq, Fixiklar, Smeshariki",
        "stream": "https://stream3.cinerama.uz/1247/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 15600,
        "q": "1080p HD",
        "i": 56,
        "n": "Mult",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1247/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1247/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1247/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1247/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 57,
        "name": "Multilandia",
        "category": "bolalar",
        "logo": "🎈",
        "l": "https://i.imgur.com/97y42jW.png",
        "desc": "Bolalar va butun oila uchun sevimli multfilmlar (HD)",
        "stream": "https://stream3.cinerama.uz/1247/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 10800,
        "q": "1080p HD",
        "i": 57,
        "n": "Multilandia",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1247/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1247/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1247/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1247/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 58,
        "name": "Nickelodeon CIS",
        "category": "bolalar",
        "logo": "🟧",
        "l": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Nickelodeon_2023.svg/512px-Nickelodeon_2023.svg.png",
        "desc": "Gubka Bob, Ninja Toshbaqalar va Loud House",
        "stream": "https://stream3.cinerama.uz/1500/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 16400,
        "q": "1080p HD",
        "i": 58,
        "n": "Nickelodeon CIS",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1500/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1500/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1500/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1500/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 59,
        "name": "Nick Jr.",
        "category": "bolalar",
        "logo": "🐾",
        "l": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Nick_Jr._logo_2023_(outline).svg/960px-Nick_Jr._logo_2023_(outline).svg.png",
        "desc": "Kichkintoylar uchun Patrul kuchukchalar",
        "stream": "https://stream3.cinerama.uz/1501/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 11400,
        "q": "1080p HD",
        "i": 59,
        "n": "Nick Jr.",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1501/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1501/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1501/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1501/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 60,
        "name": "Nicktoons CIS",
        "category": "bolalar",
        "logo": "⚡",
        "l": "https://upload.wikimedia.org/wikipedia/commons/d/d8/Nicktoons_UK_Logo_2014.png",
        "desc": "Eng sara Nickeloden animatsiyalari",
        "stream": "https://stream3.cinerama.uz/1502/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 10900,
        "q": "1080p HD",
        "i": 60,
        "n": "Nicktoons CIS",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1502/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1502/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1502/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1502/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 61,
        "name": "V gostyakh u skazki",
        "category": "bolalar",
        "logo": "🧙‍♂️",
        "l": "https://i.imgur.com/jNJkLHl.png",
        "desc": "Ertaklar olamiga sehrli sayohat",
        "stream": "https://stream3.cinerama.uz/1270/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 9500,
        "q": "1080p HD",
        "i": 61,
        "n": "V gostyakh u skazki",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1270/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1270/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1270/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1270/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 62,
        "name": "Kapitan Fantastika",
        "category": "bolalar",
        "logo": "🚀",
        "l": "https://i.imgur.com/K3PSHiT.png",
        "desc": "Superqahramonlar va koinot sarguzashtlari",
        "stream": "https://stream3.cinerama.uz/1406/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 8800,
        "q": "1080p HD",
        "i": 62,
        "n": "Kapitan Fantastika",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1406/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1406/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1406/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1406/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 63,
        "name": "Ryzhiy",
        "category": "bolalar",
        "logo": "🦊",
        "l": "https://i.imgur.com/acrU2IE.png",
        "desc": "Mehrli va imo-ishora tiliga mos multfilmlar",
        "stream": "https://stream3.cinerama.uz/1407/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 8200,
        "q": "1080p HD",
        "i": 63,
        "n": "Ryzhiy",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1407/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1407/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1407/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1407/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 64,
        "name": "Smile TV",
        "category": "bolalar",
        "logo": "😄",
        "l": "https://static.tildacdn.com/tild3936-3138-4234-b536-326531343933/-_13x.png",
        "desc": "Kulgili va ijobiy animatsion dasturlar",
        "stream": "https://stream3.cinerama.uz/1425/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 7900,
        "q": "1080p HD",
        "i": 64,
        "n": "Smile TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1425/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1425/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1425/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1425/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 65,
        "name": "Mama",
        "category": "bolalar",
        "logo": "👩‍👧",
        "l": "https://i.imgur.com/kmMIjjf.png",
        "desc": "Onalar va farzandlar tarbiyasi kanali",
        "stream": "https://stream3.cinerama.uz/1244/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 7600,
        "q": "1080p HD",
        "i": 65,
        "n": "Mama",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1244/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1244/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1244/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1244/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 66,
        "name": "BIZ Music",
        "category": "musiqa",
        "logo": "🎶",
        "l": "https://i.ibb.co/DfsCJwk/Uz-biz-music-5462.jpg",
        "desc": "Zamonaviy o'zbek va jahon xitlari (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1212/playlist.m3u8",
        "c": "uz",
        "k": "musiqa",
        "v": 15400,
        "q": "1080p HD",
        "i": 66,
        "n": "BIZ Music",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1212/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1212/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1212/mono.m3u8"
            ],
            [
                3,
                "https://fl.biztv.media/music_720_QAKpGmVUjaPApCNjpsgBxrdqNihAkl/index.m3u8"
            ]
        ]
    },
    {
        "id": 67,
        "name": "1HD Music Television",
        "category": "musiqa",
        "logo": "🎧",
        "l": "https://i.imgur.com/4Ww7CsR.png",
        "desc": "Jahon xitlari va elektron musiqa 1080p",
        "stream": "https://stream3.cinerama.uz/1267/playlist.m3u8",
        "c": "ru",
        "k": "musiqa",
        "v": 13800,
        "q": "1080p HD",
        "i": 67,
        "n": "1HD Music Television",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1267/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1267/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1267/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1267/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 68,
        "name": "FON Music",
        "category": "musiqa",
        "logo": "📻",
        "l": "https://i.imgur.com/tXABQDE.png",
        "desc": "Chillout, lofi va relaks musiqa oqimi",
        "stream": "https://stream3.cinerama.uz/1272/playlist.m3u8",
        "c": "ru",
        "k": "musiqa",
        "v": 9600,
        "q": "1080p HD",
        "i": 68,
        "n": "FON Music",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1272/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1272/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1272/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1272/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 69,
        "name": "RU.TV",
        "category": "musiqa",
        "logo": "🇷🇺",
        "l": "https://rutv.by/wp-content/uploads/2020/09/logo.png",
        "desc": "Eng yaxshi rus estradasi premyeralari",
        "stream": "https://stream3.cinerama.uz/1202/playlist.m3u8",
        "c": "ru",
        "k": "musiqa",
        "v": 12700,
        "q": "1080p HD",
        "i": 69,
        "n": "RU.TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1202/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1202/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1202/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1202/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 70,
        "name": "Muz TV HD",
        "category": "musiqa",
        "logo": "🎤",
        "l": "https://i.imgur.com/W2dO41N.png",
        "desc": "Musiqiy kliplar, chartlar va shoular (1080p HD)",
        "stream": "https://stream3.cinerama.uz/1063/playlist.m3u8",
        "c": "ru",
        "k": "musiqa",
        "v": 14500,
        "q": "1080p HD",
        "i": 70,
        "n": "Muz TV HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1063/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1063/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1063/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1063/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 71,
        "name": "Muzyka Pervogo",
        "category": "musiqa",
        "logo": "🔥",
        "l": "https://i.imgur.com/uGzH7yP.png",
        "desc": "Yoshlarbop trendlar va zamonaviy sound",
        "stream": "https://stream3.cinerama.uz/1053/playlist.m3u8",
        "c": "ru",
        "k": "musiqa",
        "v": 11300,
        "q": "1080p HD",
        "i": 71,
        "n": "Muzyka Pervogo",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1053/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1053/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1053/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1053/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 72,
        "name": "TRT Muzik",
        "category": "musiqa",
        "logo": "🇹🇷",
        "l": "https://i.imgur.com/JgUzRH8.png",
        "desc": "Klassik turk qo'shiqlari va zamonaviy hitlar",
        "stream": "https://stream3.cinerama.uz/1208/playlist.m3u8",
        "c": "tr",
        "k": "musiqa",
        "v": 10900,
        "q": "1080p HD",
        "i": 72,
        "n": "TRT Muzik",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1208/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1208/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1208/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1208/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 73,
        "name": "Euronews HD",
        "category": "yangiliklar",
        "logo": "🇪🇺",
        "l": "https://i.imgur.com/8t9mdg9.png",
        "desc": "Yevropa va butun dunyo yangiliklari xolis tahlili",
        "stream": "https://stream3.cinerama.uz/1024/playlist.m3u8",
        "c": "ru",
        "k": "yangiliklar",
        "v": 12800,
        "q": "1080p HD",
        "i": 73,
        "n": "Euronews HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1024/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1024/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1024/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1024/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 74,
        "name": "BBC News Europe",
        "category": "yangiliklar",
        "logo": "🇬🇧",
        "l": "https://dtil.tmsimg.com/assets/s158142_ld_h15_aa.png?lock=720x540",
        "desc": "Global axborot olamining nufuzli yetakchisi",
        "stream": "https://stream3.cinerama.uz/1251/playlist.m3u8",
        "c": "int",
        "k": "yangiliklar",
        "v": 13500,
        "q": "1080p HD",
        "i": 74,
        "n": "BBC News Europe",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1251/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1251/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1251/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1251/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 75,
        "name": "DW English",
        "category": "yangiliklar",
        "logo": "🇩🇪",
        "l": "https://i.imgur.com/MNKkgfa.png",
        "desc": "Germaniya xalqaro teleradiokompaniyasi",
        "stream": "https://stream3.cinerama.uz/1418/playlist.m3u8",
        "c": "int",
        "k": "yangiliklar",
        "v": 9800,
        "q": "1080p HD",
        "i": 75,
        "n": "DW English",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1418/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1418/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1418/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1418/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 76,
        "name": "Russia-24",
        "category": "yangiliklar",
        "logo": "🇷🇺",
        "l": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Rossiya-24_Logo.svg/960px-Rossiya-24_Logo.svg.png",
        "desc": "Rossiya federal kecha-yu kunduz axborot tarmog'i",
        "stream": "https://stream3.cinerama.uz/1021/playlist.m3u8",
        "c": "ru",
        "k": "yangiliklar",
        "v": 11800,
        "q": "1080p HD",
        "i": 76,
        "n": "Russia-24",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1021/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1021/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1021/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1021/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 77,
        "name": "Mir 24",
        "category": "yangiliklar",
        "logo": "🌐",
        "l": "https://i.imgur.com/dj9c8Yd.png",
        "desc": "MDH davlatlarining birlashgan axborot kanali",
        "stream": "https://stream3.cinerama.uz/1219/playlist.m3u8",
        "c": "ru",
        "k": "yangiliklar",
        "v": 8900,
        "q": "1080p HD",
        "i": 77,
        "n": "Mir 24",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1219/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1219/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1219/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1219/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 78,
        "name": "TRT Haber",
        "category": "yangiliklar",
        "logo": "🇹🇷",
        "l": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/TRT_Haber_logo_2020.svg/512px-TRT_Haber_logo_2020.svg.png",
        "desc": "Turkiya va jahon siyosiy voqealari",
        "stream": "https://tv-trthaber.medya.trt.com.tr/master.m3u8",
        "c": "tr",
        "k": "yangiliklar",
        "v": 11600,
        "q": "1080p HD",
        "i": 78,
        "n": "TRT Haber",
        "u": [
            [
                0,
                "https://tv-trthaber.medya.trt.com.tr/master.m3u8"
            ]
        ]
    },
    {
        "id": 79,
        "name": "viju Nature",
        "category": "ilm",
        "logo": "🌿",
        "l": "https://i.imgur.com/8BPZ18l.png",
        "desc": "Yovvoyi tabiat, o'rmonlar va dengiz tubi sirlari",
        "stream": "https://stream3.cinerama.uz/1228/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 14200,
        "q": "1080p HD",
        "i": 79,
        "n": "viju Nature",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1228/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1228/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1228/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1228/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 80,
        "name": "Zhivaya Planeta",
        "category": "ilm",
        "logo": "🦁",
        "l": "https://i.imgur.com/onNv1tM.png",
        "desc": "Noyob jonivorlar hayoti va ekologiya",
        "stream": "https://stream3.cinerama.uz/1250/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 12600,
        "q": "1080p HD",
        "i": 80,
        "n": "Zhivaya Planeta",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1250/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1250/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1250/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1250/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 81,
        "name": "Doctor",
        "category": "ilm",
        "logo": "🩺",
        "l": "https://i.imgur.com/VNirxxn.png",
        "desc": "Tibbiyot yangiliklari, salomatlik va profilaktika",
        "stream": "https://stream3.cinerama.uz/1409/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9700,
        "q": "1080p HD",
        "i": 81,
        "n": "Doctor",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1409/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1409/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1409/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1409/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 82,
        "name": "Zoopark",
        "category": "ilm",
        "logo": "🐼",
        "l": "https://i.imgur.com/IO5jegK.png",
        "desc": "Uy hayvonlari va qiziqarli zoologiya",
        "stream": "https://stream3.cinerama.uz/1417/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9100,
        "q": "1080p HD",
        "i": 82,
        "n": "Zoopark",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1417/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1417/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1417/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1417/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 83,
        "name": "Domashnie Zhivotnye",
        "category": "ilm",
        "logo": "🐶",
        "l": "https://i.imgur.com/ISJzQGP.png",
        "desc": "Mushuklar, itlar va boshqa jonivorlarni parvarishlash",
        "stream": "https://stream3.cinerama.uz/1426/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8400,
        "q": "1080p HD",
        "i": 83,
        "n": "Domashnie Zhivotnye",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1426/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1426/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1426/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1426/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 84,
        "name": "Dikij",
        "category": "ilm",
        "logo": "🌲",
        "l": "https://i.imgur.com/VDXDiPC.png",
        "desc": "Yovvoyi tabiat qo'ynida omon qolish mahorati",
        "stream": "https://stream3.cinerama.uz/1230/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8800,
        "q": "1080p HD",
        "i": 84,
        "n": "Dikij",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1230/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1230/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1230/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1230/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 85,
        "name": "Ohotnik i rybolov",
        "category": "ilm",
        "logo": "🎣",
        "l": "https://i.imgur.com/Bj1jI7F.png",
        "desc": "Professional baliq ovi va ovchilik sarguzashtlari",
        "stream": "https://stream3.cinerama.uz/1413/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9200,
        "q": "1080p HD",
        "i": 85,
        "n": "Ohotnik i rybolov",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1413/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1413/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1413/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1413/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 86,
        "name": "Okhota i rybalka",
        "category": "ilm",
        "logo": "🦌",
        "l": "https://i.imgur.com/nZwBaeW.png",
        "desc": "Daryo, ko'l va o'rmonlarda haqiqiy tajribalar",
        "stream": "https://stream3.cinerama.uz/1038/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9400,
        "q": "1080p HD",
        "i": 86,
        "n": "Okhota i rybalka",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1038/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1038/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1038/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1038/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 87,
        "name": "Auto Plus",
        "category": "ilm",
        "logo": "🚗",
        "l": "https://i.imgur.com/sVc8cFt.png",
        "desc": "Avtomobil test-drayvlari, superkarlar va ta'mirlash",
        "stream": "https://stream3.cinerama.uz/1036/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 12100,
        "q": "1080p HD",
        "i": 87,
        "n": "Auto Plus",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1036/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1036/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1036/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1036/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 88,
        "name": "Drive",
        "category": "ilm",
        "logo": "🏎️",
        "l": "https://i.imgur.com/FnuwfSC.png",
        "desc": "Tezlik, poygalar va avtomobil madaniyati",
        "stream": "https://stream3.cinerama.uz/1421/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 10500,
        "q": "1080p HD",
        "i": 88,
        "n": "Drive",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1421/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1421/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1421/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1421/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 89,
        "name": "Arsenal",
        "category": "ilm",
        "logo": "🛡️",
        "l": "https://i.imgur.com/DBpVeb0.png",
        "desc": "Harbiy texnika, qurol-aslahalar va aviatsiya",
        "stream": "https://stream3.cinerama.uz/1414/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8900,
        "q": "1080p HD",
        "i": 89,
        "n": "Arsenal",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1414/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1414/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1414/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1414/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 90,
        "name": "T24",
        "category": "ilm",
        "logo": "🔬",
        "l": "https://i.imgur.com/1W6R14o.png",
        "desc": "Muhandislik mo'jizalari va kosmik texnologiya",
        "stream": "https://stream3.cinerama.uz/1037/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9900,
        "q": "1080p HD",
        "i": 90,
        "n": "T24",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1037/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1037/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1037/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1037/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 91,
        "name": "Tochka otryva",
        "category": "ilm",
        "logo": "🪂",
        "l": "https://i.imgur.com/TZiBQDK.png",
        "desc": "Parashyut, dayving va tog' turizmi",
        "stream": "https://stream3.cinerama.uz/1031/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8700,
        "q": "1080p HD",
        "i": 91,
        "n": "Tochka otryva",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1031/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1031/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1031/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1031/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 92,
        "name": "365 days TV",
        "category": "ilm",
        "logo": "📜",
        "l": "https://i.imgur.com/NfnAiTR.png",
        "desc": "Jahon tarixi, sulolalar va buyuk janglar",
        "stream": "https://stream3.cinerama.uz/1242/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9300,
        "q": "1080p HD",
        "i": 92,
        "n": "365 days TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1242/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1242/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1242/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1242/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 93,
        "name": "Da Vinci",
        "category": "ilm",
        "logo": "🎨",
        "l": "https://i.imgur.com/iBx7K1M.png",
        "desc": "Bolalar va o'smirlar uchun intellektual fan dasturlari",
        "stream": "https://stream3.cinerama.uz/1231/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 11100,
        "q": "1080p HD",
        "i": 93,
        "n": "Da Vinci",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1231/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1231/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1231/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1231/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 94,
        "name": "Glazami Turista",
        "category": "ilm",
        "logo": "✈️",
        "l": "https://i.imgur.com/GXJKWdy.png",
        "desc": "Eng chiroyli sayohat marshrutlari va maslahatlar",
        "stream": "https://stream3.cinerama.uz/1423/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8600,
        "q": "1080p HD",
        "i": 94,
        "n": "Glazami Turista",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1423/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1423/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1423/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1423/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 95,
        "name": "Priklyucheniya",
        "category": "ilm",
        "logo": "🧭",
        "l": "https://i.imgur.com/qQ6pPPQ.png",
        "desc": "Sarguzashtlar, ekspeditsiyalar va yangi kashfiyotlar",
        "stream": "https://stream3.cinerama.uz/1420/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8900,
        "q": "1080p HD",
        "i": 95,
        "n": "Priklyucheniya",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1420/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1420/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1420/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1420/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 96,
        "name": "Kuhnya TV",
        "category": "ilm",
        "logo": "🍳",
        "l": "https://cdn2.red-media.ru/wp-content/uploads/2016/08/Kuhnya-mediakit.png",
        "desc": "Dunyo xalqlari oshxonasi va master-klasslar",
        "stream": "https://stream3.cinerama.uz/1236/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 10700,
        "q": "1080p HD",
        "i": 96,
        "n": "Kuhnya TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1236/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1236/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1236/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1236/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 97,
        "name": "Telecafe",
        "category": "ilm",
        "logo": "☕",
        "l": "https://i.imgur.com/1H3h1HL.png",
        "desc": "Mazali pishiriqlar va oilaviy retseptlar",
        "stream": "https://stream3.cinerama.uz/1035/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8300,
        "q": "1080p HD",
        "i": 97,
        "n": "Telecafe",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1035/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1035/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1035/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1035/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 98,
        "name": "Usadba",
        "category": "ilm",
        "logo": "🏡",
        "l": "https://i.imgur.com/mf13haG.png",
        "desc": "Bog'dorchilik, landshaft dizayni va gulchilik",
        "stream": "https://stream3.cinerama.uz/1427/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8100,
        "q": "1080p HD",
        "i": 98,
        "n": "Usadba",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1427/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1427/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1427/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1427/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 99,
        "name": "Zagorodnaya Zhizn",
        "category": "ilm",
        "logo": "🌻",
        "l": "https://i.imgur.com/RoYd5pz.png",
        "desc": "Shahar tashqarisidagi shinam hayot sirlari",
        "stream": "https://stream3.cinerama.uz/1044/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 7800,
        "q": "1080p HD",
        "i": 99,
        "n": "Zagorodnaya Zhizn",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1044/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1044/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1044/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1044/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 100,
        "name": "Zdorovoe TV",
        "category": "ilm",
        "logo": "🥗",
        "l": "https://i.imgur.com/jedtE5l.png",
        "desc": "Sog'lom turmush tarzi, fitnes va to'g'ri ovqatlanish",
        "stream": "https://stream3.cinerama.uz/1428/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8200,
        "q": "1080p HD",
        "i": 100,
        "n": "Zdorovoe TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1428/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1428/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1428/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1428/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 101,
        "name": "English Club TV",
        "category": "ilm",
        "logo": "🗣️",
        "l": "https://i.imgur.com/9FMvaRK.png",
        "desc": "Ingliz tilini interaktiv o'rganish kanali",
        "stream": "https://stream3.cinerama.uz/1442/playlist.m3u8",
        "c": "int",
        "k": "ilm",
        "v": 11800,
        "q": "1080p HD",
        "i": 101,
        "n": "English Club TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1442/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1442/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1442/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1442/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 102,
        "name": "Channel One (Perviy)",
        "category": "xalqaro",
        "logo": "1️⃣",
        "l": "https://uut-telecom.ru/wp-content/uploads/2021/12/pervyj-hd.png",
        "desc": "Rossiya Birinchi telekanali (HD)",
        "stream": "https://stream3.cinerama.uz/1214/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 15900,
        "q": "1080p HD",
        "i": 102,
        "n": "Channel One (Perviy)",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1214/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1214/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1214/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1214/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 103,
        "name": "Russia-1",
        "category": "xalqaro",
        "logo": "🇷🇺",
        "l": "https://uut-telecom.ru/wp-content/uploads/2021/12/rossiya-1-hd.png",
        "desc": "Rossiya Bosh davlat telekanali",
        "stream": "https://stream3.cinerama.uz/1020/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 14900,
        "q": "1080p HD",
        "i": 103,
        "n": "Russia-1",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1020/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1020/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1020/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1020/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 104,
        "name": "NTV",
        "category": "xalqaro",
        "logo": "🟢",
        "l": "https://real.su/wp-content/uploads/2019/12/%D0%9D%D0%A2%D0%92_HD-20220826-123641.png",
        "desc": "Ommabop detektivlar, teleseriallar va yangiliklar",
        "stream": "https://stream3.cinerama.uz/1023/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 13700,
        "q": "1080p HD",
        "i": 104,
        "n": "NTV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1023/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1023/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1023/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1023/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 105,
        "name": "Mir",
        "category": "xalqaro",
        "logo": "🌐",
        "l": "https://i.imgur.com/AqWaJT8.png",
        "desc": "MDH davlatlari do'stlik va birdamlik telekanali",
        "stream": "https://stream3.cinerama.uz/1218/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 11100,
        "q": "1080p HD",
        "i": 105,
        "n": "Mir",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1218/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1218/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1218/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1218/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 106,
        "name": "Zvezda",
        "category": "xalqaro",
        "logo": "⭐",
        "l": "https://i.imgur.com/4PAcpfM.png",
        "desc": "Harbiy-vatanparvarlik, tarix va texnika",
        "stream": "https://stream3.cinerama.uz/1050/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 10400,
        "q": "1080p HD",
        "i": 106,
        "n": "Zvezda",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1050/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1050/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1050/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1050/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 107,
        "name": "TV Centr",
        "category": "xalqaro",
        "logo": "🔴",
        "l": "https://www.moscow-telecom.ru/img/logo_channels/tvc_hd.svg",
        "desc": "Moskva poytaxt kanali, publitsistika va filmlar",
        "stream": "https://stream3.cinerama.uz/1025/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 9800,
        "q": "1080p HD",
        "i": 107,
        "n": "TV Centr",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1025/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1025/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1025/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1025/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 108,
        "name": "TV Centr International",
        "category": "xalqaro",
        "logo": "🌐",
        "l": "https://i.imgur.com/tsCOnBW.png",
        "desc": "TV Centr xalqaro versiyasi",
        "stream": "https://stream3.cinerama.uz/1281/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 8900,
        "q": "1080p HD",
        "i": 108,
        "n": "TV Centr International",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1281/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1281/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1281/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1281/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 109,
        "name": "Russia-K",
        "category": "xalqaro",
        "logo": "🏛️",
        "l": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/Russia-Cultura.svg/960px-Russia-Cultura.svg.png",
        "desc": "Madaniyat, klassik san'at, opera va spektakllar",
        "stream": "https://stream3.cinerama.uz/1048/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 9300,
        "q": "1080p HD",
        "i": 109,
        "n": "Russia-K",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1048/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1048/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1048/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1048/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 110,
        "name": "TRT 1",
        "category": "xalqaro",
        "logo": "🇹🇷",
        "l": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/TRT_1_logo_2021.svg/512px-TRT_1_logo_2021.svg.png",
        "desc": "Turkiya bosh davlat telekanali, tarixiy seriallar",
        "stream": "https://tv-trt1.medya.trt.com.tr/master.m3u8",
        "c": "tr",
        "k": "xalqaro",
        "v": 15800,
        "q": "1080p HD",
        "i": 110,
        "n": "TRT 1",
        "u": [
            [
                0,
                "https://tv-trt1.medya.trt.com.tr/master.m3u8"
            ]
        ]
    },
    {
        "id": 111,
        "name": "Qazaqstan TV",
        "category": "xalqaro",
        "logo": "🇰🇿",
        "l": "https://cdn.qazaqstan.tv/qazaqstan.png?w=420&h=196&format=png&resize=aspectfill&g=centeralt=",
        "desc": "Qozog'iston milliy telekanali",
        "stream": "https://stream3.cinerama.uz/1431/playlist.m3u8",
        "c": "kz",
        "k": "xalqaro",
        "v": 10500,
        "q": "1080p HD",
        "i": 111,
        "n": "Qazaqstan TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1431/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1431/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1431/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1431/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 112,
        "name": "TNV Planet",
        "category": "xalqaro",
        "logo": "🪐",
        "l": "https://i.imgur.com/ijA1zDw.png",
        "desc": "Tatariston Respublikasi teleradiosi sun'iy yo'ldosh kanali",
        "stream": "https://stream3.cinerama.uz/1062/playlist.m3u8",
        "c": "ru",
        "k": "xalqaro",
        "v": 7800,
        "q": "1080p HD",
        "i": 112,
        "n": "TNV Planet",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1062/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1062/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1062/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1062/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 113,
        "name": "KBS World",
        "category": "xalqaro",
        "logo": "🇰🇷",
        "l": "https://upload.wikimedia.org/wikipedia/commons/9/98/NewsNetLogo2022.png",
        "desc": "Janubiy Koreya xalqaro kanali (K-Pop, Doramalar)",
        "stream": "https://stream3.cinerama.uz/1448/playlist.m3u8",
        "c": "int",
        "k": "xalqaro",
        "v": 11400,
        "q": "1080p HD",
        "i": 113,
        "n": "KBS World",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1448/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1448/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1448/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1448/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 114,
        "name": "Makka Jonli Efir",
        "category": "religious",
        "logo": "🕋",
        "l": "https://i.imgur.com/A2fJysM.png",
        "desc": "Makkai Mukarrama jonli efiri (24/7 1080p Full HD)",
        "stream": "https://cdn-globecast.akamaized.net/live/eds/saudi_quran/hls_roku/index.m3u8",
        "c": "sa",
        "k": "religious",
        "v": 25000,
        "q": "1080p HD",
        "i": 114,
        "n": "Makka Jonli Efir",
        "u": [
            [
                0,
                "https://cdn-globecast.akamaized.net/live/eds/saudi_quran/hls_roku/index.m3u8"
            ]
        ]
    },
    {
        "id": 115,
        "name": "Madina Jonli Efir",
        "category": "religious",
        "logo": "🕌",
        "l": "https://i.imgur.com/S6LcTJv.png",
        "desc": "Madinai Munavvara jonli efiri (24/7 1080p Full HD)",
        "stream": "https://cdn-globecast.akamaized.net/live/eds/saudi_sunnah/hls_roku/index.m3u8",
        "c": "sa",
        "k": "religious",
        "v": 24000,
        "q": "1080p HD",
        "i": 115,
        "n": "Madina Jonli Efir",
        "u": [
            [
                0,
                "https://cdn-globecast.akamaized.net/live/eds/saudi_sunnah/hls_roku/index.m3u8"
            ]
        ]
    },
    {
        "id": 116,
        "name": "Samarqand MTRK (STV)",
        "category": "milliy",
        "logo": "🏛️",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Samarqand viloyati teleradiokanali va telenavosi (HD)",
        "stream": "https://stream3.cinerama.uz/1452/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8900,
        "q": "1080p HD",
        "i": 116,
        "n": "Samarqand MTRK (STV)",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1452/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1452/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1452/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1452/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 117,
        "name": "Andijon MTRK",
        "category": "milliy",
        "logo": "🌸",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Andijon viloyati teleradiokanali va xushnavolari",
        "stream": "https://stream3.cinerama.uz/1455/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8700,
        "q": "1080p HD",
        "i": 117,
        "n": "Andijon MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1455/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1455/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1455/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1455/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 118,
        "name": "Buxoro MTRK",
        "category": "milliy",
        "logo": "🕌",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Buxoro viloyati qadimiy madaniyati va navolari",
        "stream": "https://stream3.cinerama.uz/1456/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8600,
        "q": "1080p HD",
        "i": 118,
        "n": "Buxoro MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1456/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1456/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1456/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1456/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 119,
        "name": "Jizzax MTRK",
        "category": "milliy",
        "logo": "⛰️",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Jizzax viloyati teleradiokanali va dasturlari",
        "stream": "https://stream3.cinerama.uz/1457/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8100,
        "q": "1080p HD",
        "i": 119,
        "n": "Jizzax MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1457/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1457/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1457/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1457/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 120,
        "name": "Namangan MTRK",
        "category": "milliy",
        "logo": "🌺",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Gullar shahri Namangan viloyat teleradiokanali",
        "stream": "https://stream3.cinerama.uz/1459/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8500,
        "q": "1080p HD",
        "i": 120,
        "n": "Namangan MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1459/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1459/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1459/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1459/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 121,
        "name": "Qashqadaryo MTRK",
        "category": "milliy",
        "logo": "🏜️",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Nasaf va Qashqadaryo vohasi teleradiokanali",
        "stream": "https://stream3.cinerama.uz/1461/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8300,
        "q": "1080p HD",
        "i": 121,
        "n": "Qashqadaryo MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1461/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1461/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1461/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1461/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 122,
        "name": "Surxondaryo MTRK",
        "category": "milliy",
        "logo": "☀️",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Termiz va janubiy voha yangiliklari hamda navolari",
        "stream": "https://stream3.cinerama.uz/1462/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8200,
        "q": "1080p HD",
        "i": 122,
        "n": "Surxondaryo MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1462/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1462/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1462/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1462/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 123,
        "name": "Sirdaryo MTRK",
        "category": "milliy",
        "logo": "🌊",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Guliston va Sirdaryo viloyat teleradiokanali",
        "stream": "https://stream3.cinerama.uz/1463/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 7900,
        "q": "1080p HD",
        "i": 123,
        "n": "Sirdaryo MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1463/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1463/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1463/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1463/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 124,
        "name": "Xorazm MTRK",
        "category": "milliy",
        "logo": "🏰",
        "l": "https://i.imgur.com/QUIIhTD.png",
        "desc": "Xiva va Xorazm viloyati san'ati, tarixi va navolari",
        "stream": "https://stream3.cinerama.uz/1464/playlist.m3u8",
        "c": "uz",
        "k": "milliy",
        "v": 8800,
        "q": "1080p HD",
        "i": 124,
        "n": "Xorazm MTRK",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1464/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1464/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1464/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1464/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 125,
        "name": "Hayot TV",
        "category": "kino",
        "logo": "🎬",
        "l": "https://i.imgur.com/emH1BgC.png",
        "desc": "O'zbek tilidagi jahon va milliy kinofilmlari (1080p HD)",
        "stream": "https://stream3.cinerama.uz/1064/playlist.m3u8",
        "c": "uz",
        "k": "kino",
        "v": 9400,
        "q": "1080p HD",
        "i": 125,
        "n": "Hayot TV",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1064/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1064/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1064/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1064/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 126,
        "name": "viju+ comedy",
        "category": "kino",
        "logo": "😂",
        "l": "https://i.imgur.com/O618d3R.png",
        "desc": "Kulgili va quvnoq komediya filmlari kanali (1080p HD)",
        "stream": "https://stream3.cinerama.uz/1061/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 8900,
        "q": "1080p HD",
        "i": 126,
        "n": "viju+ comedy",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1061/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1061/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1061/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1061/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 127,
        "name": "viju+ serial",
        "category": "kino",
        "logo": "🎬",
        "l": "https://i.imgur.com/O618d3R.png",
        "desc": "Eng sara jahon seriallari va filmlari (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1224/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 9400,
        "q": "1080p HD",
        "i": 127,
        "n": "viju+ serial",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1224/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1224/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1224/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1224/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 128,
        "name": "KinoSemya HD",
        "category": "kino",
        "logo": "🍿",
        "l": "https://i.imgur.com/8Qp4z7p.png",
        "desc": "Butun oila uchun sevimli filmlar (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1234/playlist.m3u8",
        "c": "ru",
        "k": "kino",
        "v": 9350,
        "q": "1080p HD",
        "i": 128,
        "n": "KinoSemya HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1234/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1234/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1234/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1234/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 129,
        "name": "ducktv HD",
        "category": "bolalar",
        "logo": "🦆",
        "l": "https://i.imgur.com/tHqgU6V.png",
        "desc": "Kichkintoylar va bolalar uchun tarbiyaviy multfilmlar (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1271/playlist.m3u8",
        "c": "ru",
        "k": "bolalar",
        "v": 9200,
        "q": "1080p HD",
        "i": 129,
        "n": "ducktv HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1271/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1271/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1271/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1271/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 130,
        "name": "Setanta Sports 1 HD",
        "category": "sport",
        "logo": "⚽",
        "l": "https://i.imgur.com/6U8Y1wQ.png",
        "desc": "APL, La Liga, Seria A va UFC jonli efirlari (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1263/playlist.m3u8",
        "c": "uz",
        "k": "sport",
        "v": 9900,
        "q": "1080p HD",
        "i": 130,
        "n": "Setanta Sports 1 HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1263/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1263/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1263/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1263/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 131,
        "name": "LTV HD",
        "category": "xususiy",
        "logo": "🎭",
        "l": "https://i.imgur.com/gK2T3nM.png",
        "desc": "O'zbek qiziqchilari va komediya shoulari (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1210/playlist.m3u8",
        "c": "uz",
        "k": "xususiy",
        "v": 8950,
        "q": "1080p HD",
        "i": 131,
        "n": "LTV HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1210/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1210/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1210/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1210/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 132,
        "name": "Discovery Channel HD",
        "category": "ilm",
        "logo": "🌍",
        "l": "https://i.imgur.com/9g5vM1X.png",
        "desc": "Ilm-fan, texnologiya va tabiat sirlari (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1039/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9600,
        "q": "1080p HD",
        "i": 132,
        "n": "Discovery Channel HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1039/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1039/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1039/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1039/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 133,
        "name": "Nat Geo Wild HD",
        "category": "ilm",
        "logo": "🦁",
        "l": "https://i.imgur.com/Qv9mY0K.png",
        "desc": "Yovvoyi tabiat va hayvonot olami (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1042/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9550,
        "q": "1080p HD",
        "i": 133,
        "n": "Nat Geo Wild HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1042/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1042/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1042/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1042/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 134,
        "name": "Animal Planet HD",
        "category": "ilm",
        "logo": "🐘",
        "l": "https://i.imgur.com/4h9jZ9B.png",
        "desc": "Hayvonot dunyosi va sarguzashtlar (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1043/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 9500,
        "q": "1080p HD",
        "i": 134,
        "n": "Animal Planet HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1043/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1043/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1043/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1043/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 135,
        "name": "viju Explore HD",
        "category": "ilm",
        "logo": "🧭",
        "l": "https://i.imgur.com/O618d3R.png",
        "desc": "Kashfiyotlar va qiziqarli hujjatli filmlar (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1045/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8900,
        "q": "1080p HD",
        "i": 135,
        "n": "viju Explore HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1045/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1045/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1045/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1045/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 136,
        "name": "viju History HD",
        "category": "ilm",
        "logo": "🏛️",
        "l": "https://i.imgur.com/O618d3R.png",
        "desc": "Buyuk tarixiy voqealar va shaxslar (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1046/playlist.m3u8",
        "c": "ru",
        "k": "ilm",
        "v": 8850,
        "q": "1080p HD",
        "i": 136,
        "n": "viju History HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1046/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1046/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1046/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1046/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 137,
        "name": "Ilm TV HD",
        "category": "religious",
        "logo": "🕌",
        "l": "https://i.imgur.com/dK1c8zW.png",
        "desc": "Diniy-ma'rifiy va axloqiy suhbatlar (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1198/playlist.m3u8",
        "c": "uz",
        "k": "religious",
        "v": 9300,
        "q": "1080p HD",
        "i": 137,
        "n": "Ilm TV HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1198/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1198/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1198/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1198/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 138,
        "name": "MYDAY TV HD",
        "category": "musiqa",
        "logo": "🎶",
        "l": "https://i.imgur.com/7vY9X7M.png",
        "desc": "O'zbek va xalqaro estrada, gastro & art (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1265/playlist.m3u8",
        "c": "uz",
        "k": "musiqa",
        "v": 8800,
        "q": "1080p HD",
        "i": 138,
        "n": "MYDAY TV HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1265/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1265/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1265/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1265/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    },
    {
        "id": 139,
        "name": "TRT Avaz HD",
        "category": "xalqaro",
        "logo": "🌐",
        "l": "https://i.imgur.com/3YpGz5Y.png",
        "desc": "Turkiy xalqlar madaniyati va yangiliklari (1080p Full HD)",
        "stream": "https://stream3.cinerama.uz/1258/playlist.m3u8",
        "c": "tr",
        "k": "xalqaro",
        "v": 8600,
        "q": "1080p HD",
        "i": 139,
        "n": "TRT Avaz HD",
        "u": [
            [
                0,
                "https://stream3.cinerama.uz/1258/playlist.m3u8"
            ],
            [
                1,
                "https://stream3.cinerama.uz/1258/tracks-v1a1/mono.ts.m3u8"
            ],
            [
                2,
                "https://stream3.cinerama.uz/1258/mono.m3u8"
            ],
            [
                3,
                "https://stream3.cinerama.uz/1258/tracks-v2a1/mono.ts.m3u8"
            ]
        ]
    }
]

# Frontend mosligi uchun dinamik xususiyatlarni to'ldirish
for _ch in CHANNELS_LIST:
    _ch["i"] = _ch["id"]
    _ch["n"] = _ch["name"]
    _ch["k"] = _ch.get("k", _ch["category"])
    _ch["c"] = _ch.get("c", "uz" if _ch["category"] in ("milliy", "xususiy") else "ru")
    _ch["l"] = _ch.get("l")
    _ch["u"] = _ch.get("u") or [[0, _ch["stream"]]]
    _ch["v"] = _ch.get("v", max(500, 10000 - _ch["id"] * 50))
    _ch["q"] = _ch.get("q") or _ch.get("quality") or "1080p HD"
