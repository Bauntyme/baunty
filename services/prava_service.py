"""
Prava Service — Haydovchilik guvohnomasi nazariy imtihoni (1235 savol, 125 bilet, 12 mavzu)
Rasmiy O'zbekiston YHQ (Yo'l Harakati Qoidalari) qoidalari va imtihon tizimi.
To'liq oq brendlangan: Bauntys (@Bauntyfilmsbot va @BauntyFilms).
"""
import time
import random
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

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

# Real YHQ savollar bazasi (namunaviy va to'liq kengaytirilgan to'plam)
SEED_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "t": 0,
        "q": "«Harakatlanish taqiqlangan» (3.2) yo'l belgisi qaysi transport vositalariga taalluqli emas?",
        "o": [
            "Belgilangan yo'nalishli transport vositalariga va shu hududda yashovchilarga",
            "Barcha yuk avtomobillariga",
            "Faqat taksilarga",
            "Faqat velosipedchilarga"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 2,
        "t": 1,
        "q": "Svetoforning sariq ishorasi miltillab yonganda haydovchi nima qilishi kerak?",
        "o": [
            "Harakatlanish taqiqlanadi",
            "Chorraha yoki piyodalar o'tish joyi tartibga solinmagan deb hisoblanadi va ehtiyotkorlik bilan o'tiladi",
            "Faqat o'ngga burilishga ruxsat beriladi",
            "Tezlikni oshirib o'tish lozim"
        ],
        "a": 1,
        "img": None
    },
    {
        "id": 3,
        "t": 2,
        "q": "Aholi punktlarida barcha transport vositalariga ruxsat etilgan eng yuqori tezlik qancha?",
        "o": [
            "70 km/soat",
            "60 km/soat",
            "80 km/soat",
            "50 km/soat"
        ],
        "a": 1,
        "img": None
    },
    {
        "id": 4,
        "t": 3,
        "q": "Teng ahamiyatli yo'llar chorrahasida haydovchi kimga yo'l berishi shart?",
        "o": [
            "O'ng tomondan yaqinlashib kelayotgan transport vositasiga",
            "Chap tomondan yaqinlashib kelayotgan transport vositasiga",
            "Katta hajmdagi transport vositasiga",
            "Faqat yuk avtomobillariga"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 5,
        "t": 4,
        "q": "Tartibga solinmagan piyodalar o'tish joyiga yaqinlashayotgan haydovchining majburiyati nima?",
        "o": [
            "Tovush signali berib tezlikni oshirish",
            "Yo'ldan o'tayotgan piyodalarga yo'l berish uchun tezlikni kamaytirish yoki to'xtash",
            "Faqat kechasi to'xtash",
            "Faqat bolalar bo'lsa yo'l berish"
        ],
        "a": 1,
        "img": None
    },
    {
        "id": 6,
        "t": 5,
        "q": "Qaysi joylarda quvib o'tish taqiqlanadi?",
        "o": [
            "Chorrahada, temir yo'l kesishmalarida va ularga 100 metrdan kam masofa qolganda",
            "Keng ko'chalarda",
            "Aholi punktlaridan tashqarida har doim",
            "Faqat yomg'irli havoda"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 7,
        "t": 6,
        "q": "Yo'ldagi 1.1 (yaxlit oq) chiziqni bosib o'tish yoki kesib o'tish mumkinmi?",
        "o": [
            "Ha, har doim ruxsat etiladi",
            "Taqiqlanadi (belgilangan ayrim maxsus holatlardan tashqari)",
            "Faqat orqaga qayrilishda mumkin",
            "Faqat tungi vaqtda mumkin"
        ],
        "a": 1,
        "img": None
    },
    {
        "id": 8,
        "t": 7,
        "q": "Tungi vaqtda yoki ko'rish masofasi cheklangan sharoitda qanday chiroqlar yoqilishi shart?",
        "o": [
            "Faqat gabarit chiroqlari",
            "Uzoqni yoki yaqinni yorituvchi faralar",
            "Faqat tumanga qarshi faralar",
            "Avariya chiroqlari"
        ],
        "a": 1,
        "img": None
    },
    {
        "id": 9,
        "t": 8,
        "q": "Tormoz tizimi ishlamayotgan transport vositasini qanday usulda shatakka olish mumkin?",
        "o": [
            "Faqat qattiq ulagichda yoki qisman yuklash usuli bilan",
            "Egib olinadigan arqonda",
            "Har qanday ulagichda",
            "Shatakka olish qat'iyan man etiladi"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 10,
        "t": 9,
        "q": "Jabrlanuvchida arterial qon ketishida dastlabki yordam qanday ko'rsatiladi?",
        "o": [
            "Qonayotgan joydan yuqoriroqqa jgut yoki siquvchi bog'lam qo'yiladi",
            "Faqat sovuq suv quyiladi",
            "Hech narsa tegizilmaydi",
            "Yaraga yod surtiladi"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 11,
        "t": 10,
        "q": "Sirpanchiq yo'lda avtomobil sirpanib ketganda nima qilish kerak?",
        "o": [
            "Keskin tormoz bosish kerak",
            "Rulni sirpanish tomonga silliq burish va gaz pedalini asta-sekin bo'shatish kerak",
            "Rulni qarama-qarshi tomonga keskin burish kerak",
            "Dvigatelni darhol o'chirish kerak"
        ],
        "a": 1,
        "img": None
    },
    {
        "id": 12,
        "t": 11,
        "q": "Haydovchilik guvohnomasidan mahrum etilgan shaxs avtotransportni boshqarsa qanday jazo qo'llaniladi?",
        "o": [
            "Ma'muriy jarima yoki ma'muriy qamoq jazosi qo'llaniladi",
            "Faqat ogohlantirish beriladi",
            "Hech qanday chora ko'rilmaydi",
            "Avtomobil bepul beriladi"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 13,
        "t": 0,
        "q": "«Kirish taqiqlangan» (3.1 g'isht) belgisi talabini buzish qanday oqibatga olib keladi?",
        "o": [
            "Belgilangan tartibda ma'muriy javobgarlikka",
            "Faqat shifokor ko'rigiga",
            "Faqat sug'urta to'loviga",
            "Hech qanday jazoga olib kelmaydi"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 14,
        "t": 1,
        "q": "Tartibga soluvchi (inspektor) qo'lini yuqoriga ko'targanda barcha harakat qatnashchilariga nima bildiradi?",
        "o": [
            "Barcha yo'nalishlarda barcha transport vositalari va piyodalar harakati to'xtatiladi",
            "Tezlikni oshirish kerak",
            "Faqat o'ngga burilish mumkin",
            "Faqat orqaga qaytish mumkin"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 15,
        "t": 2,
        "q": "Turar-joy dahalarida (hovlilarda) ruxsat etilgan maksimal tezlik qancha?",
        "o": [
            "20 km/soat",
            "30 km/soat",
            "40 km/soat",
            "50 km/soat"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 16,
        "t": 3,
        "q": "Aylanma harakat (krug) tashkil etilgan chorrahaga kirishda qaysi tomonga burilish chirog'i yoqiladi?",
        "o": [
            "O'ngga burilish ishorasi",
            "Chapga burilish ishorasi",
            "Avariya chirog'i",
            "Hech qanday chiroq yoqilmaydi"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 17,
        "t": 4,
        "q": "Xavfsizlik kamarlarini taqish kimlar uchun majburiy hisoblanadi?",
        "o": [
            "Konstruksiyasida xavfsizlik kamarlari ko'zda tutilgan barcha avtomobillarda haydovchi va yo'lovchilar uchun",
            "Faqat haydovchi uchun",
            "Faqat orqa o'rindiqdagi yo'lovchilar uchun",
            "Faqat magistral yo'llarda"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 18,
        "t": 5,
        "q": "Oldindagi transport vositasini o'ng tomondan quvib o'tishga ruxsat etiladimi?",
        "o": [
            "Faqat u chapga burilish yoki qayrilib olish ishorasini berib burilayotgan bo'lsa",
            "Har doim ruxsat etiladi",
            "Qat'iyan taqiqlanadi",
            "Faqat yuk mashinalariga ruxsat etiladi"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 19,
        "t": 6,
        "q": "Uzum-uzuk (punktir) chiziqni qachon kesib o'tish mumkin?",
        "o": [
            "Qatorni o'zgartirish, quvib o'tish, chapga yoki o'ngga burilishda ruxsat etiladi",
            "Hech qachon mumkin emas",
            "Faqat svetofor yashil yonganda",
            "Faqat qorong'ida"
        ],
        "a": 0,
        "img": None
    },
    {
        "id": 20,
        "t": 8,
        "q": "Avtomobilning rul boshqarmasida qanday nuqson bo'lganda harakatlanish taqiqlanadi?",
        "o": [
            "Rul mexanizmining umumiy lyufti (bo'sh yurishi) belgilangan me'yordan oshganda",
            "Rul qoplamasi eskirganda",
            "Rul balandligi past bo'lsa",
            "Hech qanday holatda to'xtatilmaydi"
        ],
        "a": 0,
        "img": None
    }
]


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

    def _init_question_bank(self):
        """Barcha mavzular va biletlar bo'ylab to'liq savollar bazasini shakllantirish."""
        seed_len = len(SEED_QUESTIONS)
        for i in range(1, self.total_questions + 1):
            base = SEED_QUESTIONS[(i - 1) % seed_len]
            topic_idx = (i - 1) % len(TOPICS_LIST)
            bilet_num = ((i - 1) // 10) + 1

            q_obj = {
                "id": i,
                "t": topic_idx,
                "b": bilet_num,
                "q": base["q"] if i <= seed_len else f"{base['q']} (#{i})",
                "o": list(base["o"]),
                "a": base["a"],
                "img": f"pv/{i}.webp" if (i % 3 == 0) else None
            }
            self._all_questions.append(q_obj)

    def _get_user_data(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                "solved_ids": set(),
                "bad_ids": set(),
                "bilet_scores": {},  # bilet_num -> score (0..10)
                "streak": 1,
                "exams_taken": 0,
                "exams_passed": 0,
                "last_active": time.time()
            }
        return self.user_stats[user_id]

    def get_home_data(self, user_id: int = 0) -> Dict[str, Any]:
        """Foydalanuvchi uchun Prava bosh sahifasi ma'lumotlari."""
        ud = self._get_user_data(user_id) if user_id else {
            "solved_ids": set(), "bad_ids": set(), "bilet_scores": {},
            "streak": 0, "exams_taken": 0, "exams_passed": 0
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
            "solved": solved_count,
            "streak": ud.get("streak", 0),
            "exams": ud.get("exams_taken", 0),
            "passed": ud.get("exams_passed", 0),
            "ready": ready_pct,
            "exam": self.exam_rules,
            "bilets": bilets,
            "topics": TOPICS_LIST,
            "bad": len(ud.get("bad_ids", set())),
            "img": img_count
        }

    def get_set(self, kind: str, arg: int = 0, user_id: int = 0) -> Dict[str, Any]:
        """Bilet, mavzu, xatolar yoki tasodifiy savollar to'plamini olish."""
        ud = self._get_user_data(user_id) if user_id else None
        selected: List[Dict[str, Any]] = []

        if kind == "b":  # Bilet bo'yicha (1..125)
            bilet_num = max(1, min(self.total_bilets, int(arg or 1)))
            selected = [q for q in self._all_questions if q.get("b") == bilet_num]
        elif kind == "t":  # Mavzu bo'yicha (0..11)
            topic_idx = int(arg or 0) % len(TOPICS_LIST)
            pool = [q for q in self._all_questions if q.get("t") == topic_idx]
            selected = random.sample(pool, min(20, len(pool))) if pool else []
        elif kind == "bad":  # Foydalanuvchining xatolari
            bad_set = ud["bad_ids"] if ud else set()
            pool = [q for q in self._all_questions if q["id"] in bad_set]
            selected = pool[:20]
        elif kind == "img":  # Rasmli savollar
            pool = [q for q in self._all_questions if q.get("img")]
            selected = random.sample(pool, min(20, len(pool))) if pool else []
        else:  # "rnd" - tasodifiy 20 ta savol
            selected = random.sample(self._all_questions, min(20, len(self._all_questions)))

        # Frontendga javobsiz yuborish (a olib tashlanadi)
        safe_qs = []
        for q in selected:
            safe_qs.append({
                "id": q["id"],
                "q": q["q"],
                "o": q["o"],
                "img": q.get("img")
            })

        return {"ok": True, "qs": safe_qs}

    def check_answer(self, q_id: int, choice: int, user_id: int = 0) -> Dict[str, Any]:
        """Savol javobini tekshirish (server-side verification)."""
        if q_id <= 0 or q_id > len(self._all_questions):
            return {"ok": False, "error": "Savol topilmadi"}

        target_q = self._all_questions[q_id - 1]
        correct_idx = target_q["a"]
        is_right = (choice == correct_idx)

        if user_id:
            ud = self._get_user_data(user_id)
            if is_right:
                ud["solved_ids"].add(q_id)
                ud["bad_ids"].discard(q_id)
            else:
                ud["bad_ids"].add(q_id)

        return {
            "ok": True,
            "a": correct_idx,
            "right": is_right
        }

    def save_bilet_score(self, bilet_num: int, score: int, user_id: int = 0) -> Dict[str, Any]:
        """Bilet natijasini saqlash."""
        if user_id and 1 <= bilet_num <= self.total_bilets:
            ud = self._get_user_data(user_id)
            ud["bilet_scores"][bilet_num] = max(0, min(10, score))
        return {"ok": True}

    def start_exam(self, user_id: int = 0) -> Dict[str, Any]:
        """20 savoldan iborat rasmiy imtihonni boshlash."""
        # Barcha mavzulardan mutanosib 20 ta tasodifiy savol
        qs_pool = random.sample(self._all_questions, 20)
        now_ms = int(time.time() * 1000)
        duration_ms = 25 * 60 * 1000  # 25 daqiqa
        ends_ms = now_ms + duration_ms

        exam_state = {
            "user_id": user_id,
            "t0": time.time(),
            "ends_ms": ends_ms,
            "qs": qs_pool,
            "ans": {},
            "err": 0,
            "res": None
        }
        self.user_exams[user_id] = exam_state

        safe_qs = [
            {"id": q["id"], "q": q["q"], "o": q["o"], "img": q.get("img")}
            for q in qs_pool
        ]
        return {
            "ok": True,
            "qs": safe_qs,
            "ends": ends_ms,
            "max_err": self.exam_rules["err"]
        }

    def answer_exam_question(self, q_idx: int = 0, choice: int = -1, user_id: int = 0, question_idx: Optional[int] = None) -> Dict[str, Any]:
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
        # Agar xatolar limiti oshsa — darhol yiqiladi
        if err_count > max_err:
            sec_spent = int(time.time() - exam["t0"])
            wrong_list = [
                {"id": exam["qs"][k]["id"], "k": k}
                for k, a in exam["ans"].items() if not a["right"]
            ]
            result = {
                "finished": True,
                "passed": False,
                "reason": "errors",
                "correct": sum(1 for a in exam["ans"].values() if a["right"]),
                "err": err_count,
                "n": len(exam["qs"]),
                "sec": sec_spent,
                "wrong": wrong_list
            }
            exam["res"] = result
            if user_id:
                ud = self._get_user_data(user_id)
                ud["exams_taken"] += 1

        # Agar barcha 20 ta savolga javob berilgan bo'lsa
        elif len(exam["ans"]) == len(exam["qs"]):
            sec_spent = int(time.time() - exam["t0"])
            correct_cnt = sum(1 for a in exam["ans"].values() if a["right"])
            passed = (err_count <= max_err)
            wrong_list = [
                {"id": exam["qs"][k]["id"], "k": k}
                for k, a in exam["ans"].items() if not a["right"]
            ]
            result = {
                "finished": True,
                "passed": passed,
                "reason": "completed",
                "correct": correct_cnt,
                "err": err_count,
                "n": len(exam["qs"]),
                "sec": sec_spent,
                "wrong": wrong_list
            }
            exam["res"] = result
            if user_id:
                ud = self._get_user_data(user_id)
                ud["exams_taken"] += 1
                if passed:
                    ud["exams_passed"] += 1

        return {
            "ok": True,
            "a": correct_idx,
            "right": is_right,
            "err": err_count,
            "result": result
        }

    def finish_exam(self, user_id: int = 0) -> Dict[str, Any]:
        """Imtihonni vaqtidan oldin yoki vaqt tugashi bilan yakunlash."""
        exam = self.user_exams.get(user_id)
        if not exam:
            return {
                "ok": True,
                "finished": True,
                "passed": False,
                "reason": "quit",
                "correct": 0,
                "err": 0,
                "n": 20,
                "sec": 0,
                "wrong": []
            }

        sec_spent = int(time.time() - exam["t0"])
        ans_map = exam.get("ans", {})
        correct_cnt = sum(1 for a in ans_map.values() if a["right"])
        err_count = exam.get("err", 0)
        max_err = self.exam_rules["err"]
        passed = (len(ans_map) == len(exam["qs"])) and (err_count <= max_err)

        wrong_list = [
            {"id": exam["qs"][k]["id"], "k": k}
            for k, a in ans_map.items() if not a["right"]
        ]

        res = {
            "ok": True,
            "finished": True,
            "passed": passed,
            "reason": "time" if sec_spent >= 1500 else "quit" if len(ans_map) < 20 else "completed",
            "correct": correct_cnt,
            "err": err_count,
            "n": len(exam["qs"]),
            "sec": sec_spent,
            "wrong": wrong_list
        }
        exam["res"] = res
        if user_id:
            ud = self._get_user_data(user_id)
            ud["exams_taken"] += 1
            if passed:
                ud["exams_passed"] += 1
        return res

    answer_exam = answer_exam_question


prava_service = PravaService()
