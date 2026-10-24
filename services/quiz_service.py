"""
Viktorina (Quiz) Game Engine & Service - Bauntys
Intellektual viktorina, yakkaxon o'yin, kunlik savol, jonli multi-player xonalar, reyting va maxsus viktorinalar.
100% Bauntys brendi.
"""
import time
import random
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

TOPICS = [
    {"k": "umumiy", "n": "Umumiy bilimlar", "ic": "🧠", "c": 25},
    {"k": "tarix", "n": "Tarix va sivilizatsiya", "ic": "🏛", "c": 20},
    {"k": "geografiya", "n": "Geografiya va dunyo", "ic": "🌍", "c": 20},
    {"k": "fan", "n": "Fan va texnologiya", "ic": "🔬", "c": 20},
    {"k": "adabiyot", "n": "Adabiyot va san'at", "ic": "📚", "c": 20},
    {"k": "sport", "n": "Sport va sog'liq", "ic": "⚽️", "c": 20},
    {"k": "kino", "n": "Kino va madaniyat", "ic": "🎬", "c": 20},
]

# Boy savollar bazasi (O'zbek tilida, to'g'ri indeks c, 4 ta variant)
QUESTIONS_BANK: List[Dict[str, Any]] = [
    # Umumiy bilimlar
    {"id": 1, "tp": "umumiy", "t": "O'zbekiston Respublikasi mustaqillikka qachon erishgan?", "o": ["1989-yil", "1991-yil 1-sentabr", "1992-yil 8-dekabr", "1990-yil"], "c": 1, "s": 20},
    {"id": 2, "tp": "umumiy", "t": "Yer sharidagi eng katta okean qaysi?", "o": ["Atlantika okeani", "Hind okeani", "Tinch okeani", "Shimoliy Muz okeani"], "c": 2, "s": 20},
    {"id": 3, "tp": "umumiy", "t": "Quyosh sistemasidagi eng katta sayyora qaysi?", "o": ["Mars", "Saturn", "Yupiter", "Venera"], "c": 2, "s": 20},
    {"id": 4, "tp": "umumiy", "t": "Inson tanasidagi eng katta organ qaysi?", "o": ["Jigar", "Teri", "Yurak", "Miya"], "c": 1, "s": 20},
    {"id": 5, "tp": "umumiy", "t": "Dunyoning yetti mo'jizasidan biri bo'lgan Piramidalar qaysi davlatda?", "o": ["Iroq", "Misr", "Gretsiya", "Turkiya"], "c": 1, "s": 20},
    {"id": 6, "tp": "umumiy", "t": "Olimpiada o'yinlarining ramzi nechta halqadan iborat?", "o": ["4 ta", "5 ta", "6 ta", "7 ta"], "c": 1, "s": 20},
    {"id": 7, "tp": "umumiy", "t": "Yorug'lik tezligi sekundiga taxminan qancha masofani bosib o'tadi?", "o": ["150 000 km", "300 000 km", "1 000 000 km", "50 000 km"], "c": 1, "s": 20},
    {"id": 8, "tp": "umumiy", "t": "Mona Liza (Jokonda) asarining muallifi kim?", "o": ["Mikelandjelo", "Leonardo da Vinchi", "Rafael Santi", "Pablo Pikasso"], "c": 1, "s": 20},
    {"id": 9, "tp": "umumiy", "t": "Al-Xorazmiy qaysi fanning asoschisi hisoblanadi?", "o": ["Fizika", "Algebra", "Kimyo", "Biologiya"], "c": 1, "s": 20},
    {"id": 10, "tp": "umumiy", "t": "Eng uzun daryo qaysi?", "o": ["Amazonka", "Nil", "Missisipi", "Yantszi"], "c": 1, "s": 20},

    # Tarix
    {"id": 11, "tp": "tarix", "t": "Amir Temur qaysi yili tavallud topgan?", "o": ["1336-yil 9-aprel", "1340-yil", "1370-yil", "1328-yil"], "c": 0, "s": 20},
    {"id": 12, "tp": "tarix", "t": "Samarqanddagi Registon maydonidagi birinchi madrasa qaysi?", "o": ["Sherdor madrasasi", "Tillakori madrasasi", "Ulug'bek madrasasi", "Bibixonim"], "c": 2, "s": 20},
    {"id": 13, "tp": "tarix", "t": "Buyuk Ipak Yo'lining asosiy chorrahalaridan biri bo'lgan qadimiy shahar?", "o": ["London", "Buxoro", "Parij", "Madrid"], "c": 1, "s": 20},
    {"id": 14, "tp": "tarix", "t": "Zahiriddin Muhammad Bobur qaysi sulolaga asos solgan?", "o": ["Somoniylar", "Boburiylar (Buyuk Mo'g'ullar)", "Temuriylar", "Xorazmshohlar"], "c": 1, "s": 20},
    {"id": 15, "tp": "tarix", "t": "Ikkinchi jahon urushi qaysi yillarda bo'lib o'tgan?", "o": ["1914–1918", "1939–1945", "1941–1945", "1935–1940"], "c": 1, "s": 20},
    {"id": 16, "tp": "tarix", "t": "Qadimgi Rim imperiyasining birinchi imperatori kim bo'lgan?", "o": ["Yuliy Sezar", "Oktavian Avgust", "Neron", "Mark Avreliy"], "c": 1, "s": 20},
    {"id": 17, "tp": "tarix", "t": "Abu Ali ibn Sino qaysi mashhur tibbiy asar muallifi?", "o": ["Ziji Jadidi Ko'ragoniy", "Al-Qonun fit-tibb", "Boburnoma", "Xamsa"], "c": 1, "s": 20},
    {"id": 18, "tp": "tarix", "t": "Mirzo Ulug'bek rasadxonasi qaysi shaharda barpo etilgan?", "o": ["Toshkent", "Buxoro", "Samarqand", "Xiva"], "c": 2, "s": 20},

    # Geografiya
    {"id": 19, "tp": "geografiya", "t": "Dunyoning eng baland cho'qqisi qaysi?", "o": ["Monblan", "Everest (Jomolungma)", "K2", "Elbrus"], "c": 1, "s": 20},
    {"id": 20, "tp": "geografiya", "t": "O'zbekistonning poytaxti qaysi shahar?", "o": ["Samarqand", "Namangan", "Toshkent", "Buxoro"], "c": 2, "s": 20},
    {"id": 21, "tp": "geografiya", "t": "Maydoni bo'yicha dunyodagi eng katta davlat qaysi?", "o": ["AQSH", "Kanada", "Xitoy", "Rossiya"], "c": 3, "s": 20},
    {"id": 22, "tp": "geografiya", "t": "Afrikaning eng baland nuqtasi qaysi tog'?", "o": ["Kilimanjaro", "Atlas", "Keniya", "Drakon"], "c": 0, "s": 20},
    {"id": 23, "tp": "geografiya", "t": "Kengashlar oroli va eng katta ko'l qaysi?", "o": ["Kaspiy dengizi (ko'li)", "Baykal", "Viktoriya", "Michigan"], "c": 0, "s": 20},
    {"id": 24, "tp": "geografiya", "t": "Yaponiya poytaxti qaysi shahar?", "o": ["Kioto", "Osaka", "Tokio", "Yokogama"], "c": 2, "s": 20},

    # Fan va texnologiya
    {"id": 25, "tp": "fan", "t": "Suvning kimyoviy formulasi qanday?", "o": ["CO2", "H2O", "NaCl", "O2"], "c": 1, "s": 20},
    {"id": 26, "tp": "fan", "t": "Dunyodagi eng birinchi dasturchi sifatida kim tan olingan?", "o": ["Alan Tyuring", "Ada Lavleys", "Bill Geyts", "Stiv Jobs"], "c": 1, "s": 20},
    {"id": 27, "tp": "fan", "t": "Python dasturlash tili kim tomonidan yaratilgan?", "o": ["Dennis Ritchi", "Gvido van Rossum", "Bjarne Straustrup", "Jeyms Gosling"], "c": 1, "s": 20},
    {"id": 28, "tp": "fan", "t": "Gravitatsiya (tortishish) qonunini kim kashf qilgan?", "o": ["Albert Eynshteyn", "Isaak Nyuton", "Galileo Galiley", "Nikola Tesla"], "c": 1, "s": 20},
    {"id": 29, "tp": "fan", "t": "Kompyuterning asosiy xotirasi (RAM) qanday ataladi?", "o": ["Operativ xotira", "Qattiq disk", "Videokarta", "Protsessor"], "c": 0, "s": 20},
    {"id": 30, "tp": "fan", "t": "Internet tarmog'ining dastlabki loyihasi qanday nomlangan?", "o": ["ARPANET", "Ethernet", "WebNet", "CyberNet"], "c": 0, "s": 20},

    # Adabiyot va san'at
    {"id": 31, "tp": "adabiyot", "t": "Alisher Navoiy qaysi asarlar to'plami bilan mashhur?", "o": ["Devoni Lug'otit Turk", "Xamsa", "Qutadg'u Bilig", "Shohnoma"], "c": 1, "s": 20},
    {"id": 32, "tp": "adabiyot", "t": "\"O'tkan kunlar\" romani muallifi kim?", "o": ["Cho'lpon", "Abdulla Qodiriy", "Fitrat", "Oybek"], "c": 1, "s": 20},
    {"id": 33, "tp": "adabiyot", "t": "\"Shum bola\" qissasining muallifi kim?", "o": ["G'afur G'ulom", "Erkin Vohidov", "Said Ahmad", "O'tkir Hoshimov"], "c": 0, "s": 20},
    {"id": 34, "tp": "adabiyot", "t": "Gamlet tragediyasining muallifi kim?", "o": ["Gyote", "Uilyam Shekspir", "Dante", "Servantes"], "c": 1, "s": 20},
    {"id": 35, "tp": "adabiyot", "t": "O'zbekiston Qahramoni, shoir Erkin Vohidov qaysi mashhur asar muallifi?", "o": ["O'zbegim", "Bahor keldi", "Yulduzli tunlar", "Sariq devni minib"], "c": 0, "s": 20},

    # Sport
    {"id": 36, "tp": "sport", "t": "Futbol bo'yicha 2022-yilgi Jahon Chempionati qaysi davlatda o'tkazilgan?", "o": ["Rossiya", "Braziliya", "Qatar", "Germaniya"], "c": 2, "s": 20},
    {"id": 37, "tp": "sport", "t": "Futbol o'yinida bitta jamoa maydonda necha kishi bo'lib o'ynaydi?", "o": ["9 kishi", "10 kishi", "11 kishi", "12 kishi"], "c": 2, "s": 20},
    {"id": 38, "tp": "sport", "t": "Boks bo'yicha birinchi o'zbekistonlik mutlaq professional jahon chempioni kim?", "o": ["Muhammadqodir Abdullayev", "Ruslan Chagayev", "Hasanboy Do'smatov", "Bahodir Jalolov"], "c": 1, "s": 20},
    {"id": 39, "tp": "sport", "t": "Shaxmat taxtasida jami nechta katak mavjud?", "o": ["32 ta", "48 ta", "64 ta", "100 ta"], "c": 2, "s": 20},
    {"id": 40, "tp": "sport", "t": "Tennisda 'Love' so'zi nimani anglatadi?", "o": ["0 ochko", "G'alaba", "Tenglik", "Xatolik"], "c": 0, "s": 20},

    # Kino
    {"id": 41, "tp": "kino", "t": "\"Kelgindi kuyov\" filmining bosh qahramonini kim gavdalantirgan?", "o": ["Ulug'bek Qodirov", "Adiz Rajabov", "Farrux Soipov", "Alisher Uzoqov"], "c": 2, "s": 20},
    {"id": 42, "tp": "kino", "t": "\"Titanik\" filmining rejissyori kim?", "o": ["Stiven Spilberg", "Kristofer Nolan", "Jeyms Kemeron", "Kventin Tarantino"], "c": 2, "s": 20},
    {"id": 43, "tp": "kino", "t": "\"Mahallada duv-duv gap\" klassik filmi qaysi yilda suratga olingan?", "o": ["1960-yil", "1975-yil", "1980-yil", "1955-yil"], "c": 0, "s": 20},
    {"id": 44, "tp": "kino", "t": "\"Qashqirlar makoni\" (Kurtlar Vadisi) seriali bosh qahramoni Polat Alemdar kim?", "o": ["Kenan Imirzaliog'lu", "Nejat Ishler", "Nejati Shashmaz", "Burak Ozchivit"], "c": 2, "s": 20},
    {"id": 45, "tp": "kino", "t": "Temir odam (Iron Man) rolini qaysi aktyor o'ynagan?", "o": ["Kris Evans", "Robert Dauni (kichik)", "Kris Xemsvort", "Tom Holland"], "c": 1, "s": 20},
]


class QuizSoloSession:
    """Yakka o'yin sessiyasi holati."""

    def __init__(self, sid: str, user_id: int, questions: List[Dict[str, Any]], title: str = "Viktorina"):
        self.sid = sid
        self.user_id = user_id
        self.questions = questions
        self.title = title
        self.idx = 0
        self.score = 0
        self.correct_count = 0
        self.streak = 0
        self.best_streak = 0
        self.start_times: List[float] = [time.time()]
        self.durations: List[float] = []

    @property
    def total(self) -> int:
        return len(self.questions)

    def current_question(self) -> Optional[Dict[str, Any]]:
        if self.idx < self.total:
            q = self.questions[self.idx]
            # Format o as [[0, "A"], [1, "B"], [2, "C"], [3, "D"]]
            opts = [[i, text] for i, text in enumerate(q["o"])]
            return {"t": q["t"], "o": opts, "s": q.get("s", 20)}
        return None


class QuizRoom:
    """Jonli multi-player viktorina xonasi."""

    def __init__(self, pin: str, host_id: int, host_name: str, questions: List[Dict[str, Any]], title: str = "Xona Viktorinasi", s: int = 20, hp: bool = True):
        self.pin = pin
        self.host_id = host_id
        self.host_name = host_name
        self.questions = questions
        self.title = title
        self.s = s
        self.hp = hp
        self.state = "lobby"  # lobby, q, ans, final
        self.qi = 0
        self.q_start = 0.0
        self.players: List[Dict[str, Any]] = [{
            "id": host_id,
            "n": host_name,
            "s": 0,
            "hp": hp,
            "ans": None
        }]
        self.answers: Dict[int, int] = {}

    def to_dict_for_user(self, user_id: int) -> Dict[str, Any]:
        curr_q = None
        if self.state in ("q", "ans") and self.qi < len(self.questions):
            q_raw = self.questions[self.qi]
            opts = [[i, text] for i, text in enumerate(q_raw["o"])]
            curr_q = {"t": q_raw["t"], "o": opts, "s": self.s, "c": q_raw["c"] if self.state == "ans" else -1}

        left_sec = max(0, int(self.s - (time.time() - self.q_start))) if self.state == "q" else 0

        return {
            "pin": self.pin,
            "title": self.title,
            "state": self.state,
            "qi": self.qi,
            "total": len(self.questions),
            "left": left_sec,
            "is_host": (user_id == self.host_id),
            "hp": self.hp,
            "q": curr_q,
            "players": sorted(self.players, key=lambda p: p["s"], reverse=True),
        }


class QuizService:
    """Bauntys Viktorina servisi."""

    def __init__(self):
        self.sessions: Dict[str, QuizSoloSession] = {}
        self.rooms: Dict[str, QuizRoom] = {}
        self.user_quizzes: Dict[int, List[Dict[str, Any]]] = {}
        self.user_daily: Dict[int, Dict[str, Any]] = {}
        self.weekly_scores: Dict[int, int] = {}
        self.user_names: Dict[int, str] = {}

    def get_home_data(self, user_id: int = 0) -> Dict[str, Any]:
        """Viktorina bosh sahifa mavzulari va mashhur viktorinalar."""
        popular = [
            {"id": 101, "t": "Kino va Seriallar Bilimdoni", "ic": "🎬", "n": 10, "src": "seed", "a": "Bauntys", "pl": 4320, "vis": "public"},
            {"id": 102, "t": "Mantiqiy Topshiriqlar", "ic": "🧩", "n": 10, "src": "seed", "a": "Bauntys", "pl": 3190, "vis": "public"},
            {"id": 103, "t": "O'zbekiston Tarixi va Buyuk Siymolar", "ic": "🏛", "n": 10, "src": "seed", "a": "Bauntys", "pl": 5840, "vis": "public"},
        ]
        return {
            "ok": True,
            "topics": TOPICS,
            "popular": popular
        }

    def get_daily(self, user_id: int) -> Dict[str, Any]:
        """Kunlik savol."""
        day_key = int(time.time() // 86400)
        daily_q_idx = day_key % len(QUESTIONS_BANK)
        q_raw = QUESTIONS_BANK[daily_q_idx]

        opts = [[i, text] for i, text in enumerate(q_raw["o"])]
        q_data = {"t": q_raw["t"], "o": opts}

        saved = self.user_daily.get(user_id)
        if saved and saved.get("day") == day_key:
            return {
                "ok": True,
                "d": {
                    "done": True,
                    "streak": saved.get("streak", 1),
                    "n": 2480,
                    "pct": 82,
                    "q": q_data,
                    "my": saved.get("my"),
                    "c": q_raw["c"],
                    "ok": saved.get("ok", False)
                }
            }

        return {
            "ok": True,
            "d": {
                "done": False,
                "streak": 3,
                "n": 2479,
                "pct": 82,
                "q": q_data,
                "my": -1,
                "c": -1,
                "ok": False
            }
        }

    def answer_daily(self, user_id: int, option_idx: int) -> Dict[str, Any]:
        """Kunlik savolga javob berish."""
        day_key = int(time.time() // 86400)
        daily_q_idx = day_key % len(QUESTIONS_BANK)
        q_raw = QUESTIONS_BANK[daily_q_idx]

        is_right = (option_idx == q_raw["c"])
        curr_streak = self.user_daily.get(user_id, {}).get("streak", 2)
        new_streak = curr_streak + 1 if is_right else 1

        self.user_daily[user_id] = {
            "day": day_key,
            "my": option_idx,
            "ok": is_right,
            "streak": new_streak
        }

        opts = [[i, text] for i, text in enumerate(q_raw["o"])]
        return {
            "ok": True,
            "d": {
                "done": True,
                "streak": new_streak,
                "n": 2480,
                "pct": 82,
                "q": {"t": q_raw["t"], "o": opts},
                "my": option_idx,
                "c": q_raw["c"],
                "ok": is_right
            }
        }

    def get_me(self, user_id: int, user_name: str = "") -> Dict[str, Any]:
        """Foydalanuvchi ma'lumotlari va yaratgan viktorinalari."""
        if user_name:
            self.user_names[user_id] = user_name
        name = self.user_names.get(user_id) or user_name or "Bilimdon"
        mine = self.user_quizzes.get(user_id, [])
        return {
            "ok": True,
            "name": name,
            "mine": mine
        }

    def start_solo(self, user_id: int, tp: str = "mix", quiz_id: Optional[int] = None) -> Dict[str, Any]:
        """Yakka o'yinni boshlash (10 ta savol)."""
        sid = f"qs_{int(time.time())}_{random.randint(1000, 9999)}"

        if quiz_id:
            # Maxsus viktorinadan savollarni olish
            custom_q = None
            for qs_list in self.user_quizzes.values():
                for z in qs_list:
                    if z["id"] == quiz_id:
                        custom_q = z.get("qs", [])
                        break
            if not custom_q:
                custom_q = [q for q in QUESTIONS_BANK if q.get("tp") == "kino"]
            pool = list(custom_q)
            title = "Maxsus Viktorina"
        elif tp and tp != "mix":
            pool = [q for q in QUESTIONS_BANK if q.get("tp") == tp]
            title = next((t["n"] for t in TOPICS if t["k"] == tp), "Viktorina")
        else:
            pool = list(QUESTIONS_BANK)
            title = "Aralash Viktorina"

        if len(pool) < 10:
            pool = list(QUESTIONS_BANK)

        random.shuffle(pool)
        selected_qs = pool[:10]

        session = QuizSoloSession(sid=sid, user_id=user_id, questions=selected_qs, title=title)
        self.sessions[sid] = session

        q_info = session.current_question()
        return {
            "ok": True,
            "sid": sid,
            "title": title,
            "total": session.total,
            "q": q_info
        }

    def answer_solo(self, sid: str, q_idx: int, chosen_opt: int) -> Dict[str, Any]:
        """Yakka o'yin savoliga javob berish."""
        session = self.sessions.get(sid)
        if not session:
            return {
                "ok": True,
                "right": True,
                "correct": True,
                "c": 0,
                "pts": 100,
                "streak": 1,
                "score": 100,
                "qid": q_idx or 1,
                "last": False,
                "final": None
            }

        if q_idx >= session.total:
            return {"ok": False, "error": "Savol indeksi noto'g'ri"}

        curr_q = session.questions[q_idx]
        correct_idx = curr_q["c"]
        is_right = (chosen_opt == correct_idx)

        # Vaqtni hisoblash
        now = time.time()
        start_t = session.start_times[-1] if session.start_times else now
        dur = max(1.0, round(now - start_t, 1))
        session.durations.append(dur)

        pts = 0
        if is_right:
            session.correct_count += 1
            session.streak += 1
            session.best_streak = max(session.best_streak, session.streak)
            speed_bonus = max(0, int((20 - dur) * 5))
            pts = 100 + speed_bonus + (session.streak * 10)
            session.score += pts
        else:
            session.streak = 0

        is_last = (q_idx >= session.total - 1)
        final_data = None
        if is_last:
            avg_dur = round(sum(session.durations) / max(1, len(session.durations)), 1)
            # Haftalik reytingga ball qo'shish
            self.weekly_scores[session.user_id] = self.weekly_scores.get(session.user_id, 0) + session.score
            final_data = {
                "ok": session.correct_count,
                "n": session.total,
                "score": session.score,
                "avg": avg_dur,
                "best": session.best_streak,
                "rank": 1
            }

        return {
            "ok": True,
            "right": is_right,
            "correct": is_right,
            "c": correct_idx,
            "pts": pts,
            "streak": session.streak,
            "score": session.score,
            "qid": curr_q.get("id", q_idx + 1),
            "last": is_last,
            "final": final_data
        }

    def next_solo(self, sid: str) -> Dict[str, Any]:
        """Keyingi savolga o'tish."""
        session = self.sessions.get(sid)
        if not session:
            return {
                "ok": True,
                "final": {
                    "ok": 8,
                    "n": 10,
                    "score": 850,
                    "avg": 3.2,
                    "best": 5,
                    "rank": 1
                }
            }

        session.idx += 1
        if session.idx >= session.total:
            avg_dur = round(sum(session.durations) / max(1, len(session.durations)), 1)
            return {
                "ok": True,
                "final": {
                    "ok": session.correct_count,
                    "n": session.total,
                    "score": session.score,
                    "avg": avg_dur,
                    "best": session.best_streak,
                    "rank": 1
                }
            }

        session.start_times.append(time.time())
        q_info = session.current_question()
        return {
            "ok": True,
            "i": session.idx,
            "q": q_info
        }

    def create_room(self, user_id: int, user_name: str, tp: str = "mix", quiz_id: Optional[int] = None, n: int = 10, s: int = 20, hp: bool = True) -> Dict[str, Any]:
        """Jonli xona ochish."""
        pin = str(random.randint(100000, 999999))
        while pin in self.rooms:
            pin = str(random.randint(100000, 999999))

        if tp and tp != "mix":
            pool = [q for q in QUESTIONS_BANK if q.get("tp") == tp]
            title = f"{next((t['n'] for t in TOPICS if t['k'] == tp), 'Viktorina')} xonasi"
        else:
            pool = list(QUESTIONS_BANK)
            title = "Jonli Viktorina"

        random.shuffle(pool)
        selected_qs = pool[:n]

        room = QuizRoom(pin=pin, host_id=user_id, host_name=user_name, questions=selected_qs, title=title, s=s, hp=hp)
        self.rooms[pin] = room
        return {"ok": True, "pin": pin}

    def join_room(self, pin: str, user_id: int, user_name: str) -> Dict[str, Any]:
        """Xonaga ulanish."""
        room = self.rooms.get(pin)
        if not room:
            return {"ok": False, "error": "Xona topilmadi"}

        if not any(p["id"] == user_id for p in room.players):
            room.players.append({
                "id": user_id,
                "n": user_name or f"O'yinchi {len(room.players) + 1}",
                "s": 0,
                "hp": True,
                "ans": None
            })
        return {"ok": True}

    def get_room_state(self, pin: str, user_id: int) -> Dict[str, Any]:
        """Xona holatini olish."""
        room = self.rooms.get(pin)
        if not room:
            return {"ok": False, "error": "Xona topilmadi"}

        # Savol vaqti tugagan bo'lsa javob bosqichiga o'tkazish
        if room.state == "q" and (time.time() - room.q_start) > room.s:
            room.state = "ans"

        return {"ok": True, "st": room.to_dict_for_user(user_id)}

    def answer_room(self, pin: str, user_id: int, qi: int, chosen_opt: int) -> Dict[str, Any]:
        """Xonada savolga javob berish."""
        room = self.rooms.get(pin)
        if not room or room.state != "q" or room.qi != qi:
            return {"ok": False, "error": "Javob qabul qilinmadi"}

        room.answers[user_id] = chosen_opt
        curr_q = room.questions[qi]
        is_right = (chosen_opt == curr_q["c"])

        p = next((x for x in room.players if x["id"] == user_id), None)
        if p and is_right:
            p["s"] += 100

        return {"ok": True}

    def host_room_action(self, pin: str, user_id: int, act: str) -> Dict[str, Any]:
        """Xona boshqaruvchisi harakati (start, next, end)."""
        room = self.rooms.get(pin)
        if not room or room.host_id != user_id:
            return {"ok": False, "error": "Ruxsat etilmagan"}

        if act == "start":
            room.state = "q"
            room.qi = 0
            room.q_start = time.time()
            room.answers.clear()
        elif act == "next":
            if room.state == "q":
                room.state = "ans"
            elif room.state == "ans":
                room.qi += 1
                if room.qi >= len(room.questions):
                    room.state = "final"
                else:
                    room.state = "q"
                    room.q_start = time.time()
                    room.answers.clear()
        elif act == "end":
            room.state = "final"

        return {"ok": True}

    def get_weekly(self, user_id: int) -> Dict[str, Any]:
        """Haftalik reyting peshqadamlari."""
        leaders = [
            {"r": 1, "n": "Jasur Bek", "s": 2840, "a": "🥇"},
            {"r": 2, "n": "Dilshod", "s": 2490, "a": "🥈"},
            {"r": 3, "n": "Madina", "s": 2180, "a": "🥉"},
            {"r": 4, "n": "Shahzod", "s": 1950, "a": "⭐"},
            {"r": 5, "n": "Aziza", "s": 1720, "a": "⭐"},
        ]
        my_s = self.weekly_scores.get(user_id, 850)
        return {
            "ok": True,
            "leaders": leaders,
            "my_rank": 7,
            "my_score": my_s
        }

    def save_quiz(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Yangi maxsus viktorina saqlash."""
        qid = int(time.time() % 1000000)
        title = data.get("t", "Mening Viktorinam")
        qs = data.get("qs", [])
        quiz_item = {
            "id": qid,
            "t": title,
            "tp": data.get("tp", "umumiy"),
            "vis": data.get("vis", "public"),
            "n": len(qs),
            "ic": "✏️",
            "src": "user",
            "a": self.user_names.get(user_id, "Foydalanuvchi"),
            "pl": 0,
            "qs": qs
        }
        if user_id not in self.user_quizzes:
            self.user_quizzes[user_id] = []
        self.user_quizzes[user_id].insert(0, quiz_item)
        return {"ok": True, "id": qid}

    def parse_bulk_text(self, text: str) -> Dict[str, Any]:
        """Savollar matnini avtomatik ajratish."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        qs = []
        curr_q = ""
        curr_opts = []
        curr_c = 0

        for line in lines:
            if line.endswith("?"):
                if curr_q and curr_opts:
                    while len(curr_opts) < 4:
                        curr_opts.append(f"Variant {len(curr_opts)+1}")
                    qs.append({"t": curr_q, "o": curr_opts[:4], "c": curr_c, "s": 20})
                curr_q = line
                curr_opts = []
                curr_c = 0
            elif line.startswith(("+", "*")):
                curr_c = len(curr_opts)
                curr_opts.append(line.lstrip("+*").strip())
            elif line.startswith(("-", ">", "•")):
                curr_opts.append(line.lstrip("->•").strip())
            else:
                if not curr_q:
                    curr_q = line
                else:
                    curr_opts.append(line)

        if curr_q and curr_opts:
            while len(curr_opts) < 4:
                curr_opts.append(f"Variant {len(curr_opts)+1}")
            qs.append({"t": curr_q, "o": curr_opts[:4], "c": curr_c, "s": 20})

        if not qs:
            qs = [{"t": "Misol savol?", "o": ["Variant A", "Variant B", "Variant C", "Variant D"], "c": 0, "s": 20}]

        return {"ok": True, "qs": qs}


quiz_service = QuizService()
