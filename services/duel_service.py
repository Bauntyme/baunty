"""
Duel 1v1 Backend Xizmati - Bauntys (@BauntyCinemabot)
1) Tezkor bilim dueli (1v1 xona, kod bilan qo'shilish, Botga qarshi rejim, 5 ta vaqtli savol, ball va g'olib)
2) Taxta/stol o'yinlari onlayn dueli (kattalar.js: chess, draughts, xo, domino, sea matchmaking va harakatlar)
Natijalar va reyting data/duel_state.json faylida saqlanadi.
"""
import os
import json
import time
import random
import string
import threading
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

_DUEL_LOCK = threading.RLock()
_DUEL_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "duel_state.json",
)

QUIZ_POOL: List[Dict[str, Any]] = [
    {"q": "O'zbekiston poytaxti Toshkent qaysi yili 2200 yilligini nishonlagan?", "o": ["2009-yil", "2001-yil", "2015-yil", "1996-yil"], "a": 0, "cat": "tarix"},
    {"q": "Alisher Navoiyning «Xamsa» asari nechta dostondan iborat?", "o": ["5 ta", "4 ta", "7 ta", "3 ta"], "a": 0, "cat": "adabiyot"},
    {"q": "Quyosh sistemasidagi eng katta sayyora qaysi?", "o": ["Yupiter", "Saturn", "Uran", "Neptun"], "a": 0, "cat": "fan"},
    {"q": "«O'tkan kunlar» romanining muallifi kim?", "o": ["Abdulla Qodiriy", "Cho'lpon", "Oybek", "G'afur G'ulom"], "a": 0, "cat": "adabiyot"},
    {"q": "Suvning kimyoviy formulasi qaysi?", "o": ["H2O", "CO2", "NaCl", "O2"], "a": 0, "cat": "fan"},
    {"q": "Aholi punktlarida yengil avtomobilning ruxsat etilgan maksimal tezligi qancha?", "o": ["60 km/soat", "70 km/soat", "80 km/soat", "50 km/soat"], "a": 0, "cat": "yhq"},
    {"q": "Dunyodagi eng uzun daryolardan biri Nil qaysi materikda oqadi?", "o": ["Afrika", "Osiyo", "Janubiy Amerika", "Yevropa"], "a": 0, "cat": "geografiya"},
    {"q": "Bir kilobayt (KB) kompyuter xotirasida odatda nechta baytga teng?", "o": ["1024 bayt", "100 bayt", "512 bayt", "2048 bayt"], "a": 0, "cat": "texnologiya"},
    {"q": "O'zbekiston davlat bayrog'ida nechta yulduz tasvirlangan?", "o": ["12 ta", "7 ta", "10 ta", "15 ta"], "a": 0, "cat": "tarix"},
    {"q": "Pifagor teoremasi qaysi shakldagi uchburchak uchun o'rinli?", "o": ["To'g'ri burchakli", "Teng tomonli", "O'tmas burchakli", "Ixtiyoriy"], "a": 0, "cat": "fan"},
    {"q": "Amir Temur qaysi shaharda tug'ilgan?", "o": ["Shahrisabz yaqinidagi Xo'ja Ilg'or", "Buxoro", "Xiva", "Qo'qon"], "a": 0, "cat": "tarix"},
    {"q": "Inson tanasidagi eng katta a'zo qaysi?", "o": ["Teri", "Jigar", "Yurak", "O'pka"], "a": 0, "cat": "fan"},
    {"q": "Shaxmat taxtasida jami nechta katak mavjud?", "o": ["64 ta", "32 ta", "48 ta", "81 ta"], "a": 0, "cat": "mantiq"},
    {"q": "O'zbekiston Respublikasi Davlat madhiyasi musiqasini kim bastalagan?", "o": ["Mutal Burhonov", "Yunus Rajabiy", "To'xtasin Jalilov", "Sulaymon Yudakov"], "a": 0, "cat": "madaniyat"},
    {"q": "Yorug'lik tezligi vakuumda taxminan qanchaga teng?", "o": ["300 000 km/s", "150 000 km/s", "340 m/s", "1 000 km/s"], "a": 0, "cat": "fan"},
    {"q": "Samarqanddagi Registon maydonidagi eng qadimgi madrasa qaysi?", "o": ["Ulug'bek madrasasi", "Sherdor madrasasi", "Tillaqori madrasasi", "Bibixonim"], "a": 0, "cat": "tarix"},
    {"q": "Bir sutkada necha daqiqa bor?", "o": ["1440 daqiqa", "1200 daqiqa", "3600 daqiqa", "720 daqiqa"], "a": 0, "cat": "mantiq"},
    {"q": "Orol dengizi suvining kamayishiga asosan qaysi ikki daryo suvidan sug'orishda ko'p foydalanish sabab bo'lgan?",
        "o": ["Amudaryo va Sirdaryo", "Zarafshon va Chirchiq", "Norin va Qoradaryo", "Vaxsh va Panj"], "a": 0, "cat": "geografiya"},
]

BOT_DUEL_NAMES = ["Alpomish Bot", "Intellekt Pro", "Zukko Bot", "Shaxmat Ustasi"]


def _shuffle_question(raw_q: Dict[str, Any]) -> Dict[str, Any]:
    opts = list(raw_q["o"])
    correct_text = opts[raw_q["a"]]
    random.shuffle(opts)
    return {
        "q": raw_q["q"],
        "o": opts,
        "a": opts.index(correct_text),
        "cat": raw_q.get("cat", "umumiy"),
    }


class DuelService:
    """1v1 Tezkor bilim dueli va onlayn taxta o'yinlari dueli xizmati."""

    def __init__(self) -> None:
        self.quiz_rooms: Dict[str, Dict[str, Any]] = {}
        self.user_quiz_map: Dict[int, str] = {}
        # Board duel (kattalar.js) uchun xonalar
        self.board_rooms: Dict[str, Dict[str, Any]] = {}
        self.user_board_map: Dict[int, str] = {}
        self._persisted = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        with _DUEL_LOCK:
            if not os.path.exists(_DUEL_STATE_PATH):
                return {"users": {}, "matches": []}
            try:
                with open(_DUEL_STATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("users", {})
                    data.setdefault("matches", [])
                    return data
            except Exception as e:
                logger.warning(f"Duel holatini yuklashda xato: {e}")
            return {"users": {}, "matches": []}

    def _save_state(self) -> None:
        with _DUEL_LOCK:
            os.makedirs(os.path.dirname(_DUEL_STATE_PATH), exist_ok=True)
            tmp = f"{_DUEL_STATE_PATH}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._persisted, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _DUEL_STATE_PATH)

    def _gen_code(self, existing: set) -> str:
        for _ in range(50):
            c = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if c not in existing:
                return c
        return str(random.randint(1000, 9999))

    def _gen_num_code(self, existing: set) -> str:
        """4 xonali raqamli kod (kattalar.js Onlayn duel uchun)."""
        for _ in range(80):
            c = f"{random.randint(1000, 9999)}"
            if c not in existing:
                return c
        return str(random.randint(1000, 9999))

    # ------------------------------------------------------------------ 1v1 Bilim/Tezlik Dueli
    def get_home(self, user_id: int = 0, user_name: str = "O'yinchi") -> Dict[str, Any]:
        """Duel bosh sahifasi: ochiq xonalar, shaxsiy statistika va yetakchilar."""
        with _DUEL_LOCK:
            open_rooms = [
                {
                    "code": r["code"],
                    "host_name": r["players"][0]["name"] if r["players"] else "O'yinchi",
                    "topic": r["topic"],
                    "players": len(r["players"]),
                }
                for r in self.quiz_rooms.values()
                if r["phase"] == "lobby" and not r["vs_bot"]
            ]
            ustats = self._persisted["users"].get(str(user_id), {"games": 0, "wins": 0, "score": 0})
            board = sorted(
                self._persisted["users"].values(),
                key=lambda u: (int(u.get("wins", 0)), int(u.get("score", 0))),
                reverse=True,
            )[:10]
            cur_code = self.user_quiz_map.get(int(user_id))
            cur = self._serialize_quiz(self.quiz_rooms[cur_code], user_id) if cur_code and cur_code in self.quiz_rooms else None
            return {
                "ok": True,
                "me": int(user_id),
                "name": user_name,
                "stats": ustats,
                "rooms": open_rooms,
                "cur": cur,
                "leaderboard": board,
            }

    def create_duel(
        self,
        user_id: int,
        user_name: str = "O'yinchi",
        topic: str = "mixed",
        vs_bot: bool = False,
        num_questions: int = 5,
    ) -> Dict[str, Any]:
        """Yangi 1v1 bilim dueli xonasini yaratish (5 ta vaqtli savol)."""
        uid = int(user_id)
        with _DUEL_LOCK:
            code = self._gen_code(set(self.quiz_rooms.keys()))
            n_q = max(3, min(10, int(num_questions or 5)))
            pool = [q for q in QUIZ_POOL if topic == "mixed" or q.get("cat") == topic] or list(QUIZ_POOL)
            picked = [_shuffle_question(q) for q in random.sample(pool, min(n_q, len(pool)))]

            players = [
                {"u": uid, "name": str(user_name or "O'yinchi")[:40], "bot": False, "score": 0, "answers": {}},
            ]
            phase = "lobby"
            if vs_bot:
                players.append({
                    "u": -999,
                    "name": random.choice(BOT_DUEL_NAMES),
                    "bot": True,
                    "score": 0,
                    "answers": {},
                })
                phase = "active"

            room = {
                "code": code,
                "topic": topic,
                "vs_bot": bool(vs_bot),
                "phase": phase,
                "players": players,
                "questions": picked,
                "q_started_at": time.time(),
                "time_limit": 15,
                "winner": None,
                "created_at": time.time(),
                "recorded": False,
            }
            self.quiz_rooms[code] = room
            self.user_quiz_map[uid] = code
            return {"ok": True, "code": code, "duel": self._serialize_quiz(room, uid)}

    def join_duel(self, user_id: int, user_name: str = "Raqib", code: str = "") -> Dict[str, Any]:
        """Kod orqali 1v1 duelga qo'shilish."""
        uid = int(user_id)
        clean_code = str(code or "").strip().upper()
        with _DUEL_LOCK:
            room = self.quiz_rooms.get(clean_code)
            if not room:
                return {"ok": False, "error": "not_found", "msg": "Bunday kodli duel topilmadi."}
            if any(p["u"] == uid for p in room["players"]):
                self.user_quiz_map[uid] = clean_code
                return {"ok": True, "code": clean_code, "duel": self._serialize_quiz(room, uid)}
            if len(room["players"]) >= 2 or room["phase"] != "lobby":
                return {"ok": False, "error": "full_or_started"}

            room["players"].append({
                "u": uid,
                "name": str(user_name or "Raqib")[:40],
                "bot": False,
                "score": 0,
                "answers": {},
            })
            room["phase"] = "active"
            room["q_started_at"] = time.time()
            self.user_quiz_map[uid] = clean_code
            return {"ok": True, "code": clean_code, "duel": self._serialize_quiz(room, uid)}

    def submit_answer(
        self,
        user_id: int,
        q_idx: int = 0,
        choice: int = -1,
        code: str = "",
        elapsed_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Duel savoliga javob yuborish, tezkorlik bonusi va g'olibni aniqlash."""
        uid = int(user_id)
        with _DUEL_LOCK:
            room = self._find_quiz_room(uid, code)
            if not room:
                return {"ok": False, "error": "not_found"}
            if room["phase"] != "active":
                return {"ok": False, "error": "not_active", "duel": self._serialize_quiz(room, uid)}

            player = next((p for p in room["players"] if p["u"] == uid), None)
            if not player:
                return {"ok": False, "error": "not_in_duel"}

            qi = int(q_idx)
            if qi < 0 or qi >= len(room["questions"]):
                return {"ok": False, "error": "invalid_question_index"}

            q = room["questions"][qi]
            is_right = (int(choice) == int(q["a"]))
            spent = float(elapsed_sec) if elapsed_sec is not None else max(0.5, min(15.0, time.time() - room.get("q_started_at", time.time())))
            points = (100 + max(0, int((15.0 - spent) * 4))) if is_right else 0

            if str(qi) not in player["answers"]:
                player["answers"][str(qi)] = {"choice": int(choice), "right": is_right, "pts": points}
                player["score"] += points

            # Bot raqibi shu savolga javob beradi
            for bp in room["players"]:
                if bp.get("bot") and str(qi) not in bp["answers"]:
                    bot_right = random.random() < 0.7
                    bot_pts = (100 + random.randint(10, 45)) if bot_right else 0
                    bot_choice = q["a"] if bot_right else ((q["a"] + 1) % len(q["o"]))
                    bp["answers"][str(qi)] = {"choice": bot_choice, "right": bot_right, "pts": bot_pts}
                    bp["score"] += bot_pts

            room["q_started_at"] = time.time()
            n_q = len(room["questions"])
            if len(room["players"]) == 2 and all(len(p["answers"]) >= n_q for p in room["players"]):
                room["phase"] = "end"
                p1, p2 = room["players"][0], room["players"][1]
                if p1["score"] > p2["score"]:
                    room["winner"] = p1["u"]
                elif p2["score"] > p1["score"]:
                    room["winner"] = p2["u"]
                else:
                    room["winner"] = 0  # Durrang
                self._record_duel_result(room)

            return {
                "ok": True,
                "right": is_right,
                "correct": q["a"],
                "points": points,
                "score": player["score"],
                "duel": self._serialize_quiz(room, uid),
            }

    def _record_duel_result(self, room: Dict[str, Any]) -> None:
        if room.get("recorded"):
            return
        room["recorded"] = True
        winner = room.get("winner")
        for p in room["players"]:
            if p.get("bot"):
                continue
            key = str(p["u"])
            rec = self._persisted["users"].setdefault(key, {"id": p["u"], "name": p["name"], "games": 0, "wins": 0, "score": 0})
            rec["name"] = p["name"]
            rec["games"] += 1
            rec["score"] += int(p["score"])
            if winner == p["u"]:
                rec["wins"] += 1
        self._persisted["matches"].insert(0, {
            "code": room["code"],
            "winner": winner,
            "players": [{"u": p["u"], "n": p["name"], "score": p["score"]} for p in room["players"]],
            "ts": int(time.time()),
        })
        self._persisted["matches"] = self._persisted["matches"][:100]
        self._save_state()

    def _find_quiz_room(self, user_id: int = 0, code: str = "") -> Optional[Dict[str, Any]]:
        clean = str(code or "").strip().upper()
        if clean and clean in self.quiz_rooms:
            return self.quiz_rooms[clean]
        mapped = self.user_quiz_map.get(int(user_id))
        return self.quiz_rooms.get(mapped) if mapped else None

    def get_state(self, code_or_user_id: Any = "", user_id: int = 0) -> Dict[str, Any]:
        """Duel holatini kod yoki foydalanuvchi ID bo'yicha olish."""
        with _DUEL_LOCK:
            raw = str(code_or_user_id or "").strip().upper()
            room = self.quiz_rooms.get(raw)
            if not room and user_id:
                room = self._find_quiz_room(user_id=user_id)
            if not room:
                return {"ok": False, "error": "not_found"}
            return {"ok": True, "duel": self._serialize_quiz(room, user_id)}

    def _serialize_quiz(self, room: Dict[str, Any], viewer_id: int = 0) -> Dict[str, Any]:
        safe_qs = [{"q": q["q"], "o": q["o"], "cat": q.get("cat", "umumiy")} for q in room["questions"]]
        return {
            "code": room["code"],
            "topic": room["topic"],
            "vs_bot": room["vs_bot"],
            "phase": room["phase"],
            "winner": room["winner"],
            "time_limit": room["time_limit"],
            "players": [
                {"u": p["u"], "name": p["name"], "bot": p["bot"], "score": p["score"], "answered": len(p["answers"])}
                for p in room["players"]
            ],
            "questions": safe_qs,
            "me": int(viewer_id),
        }

    # ------------------------------------------------------------------ Taxta o'yinlari dueli (kattalar.js mosligi)
    def board_find(self, user_id: int, user_name: str, g: str = "chess") -> Dict[str, Any]:
        """Ochiq raqib izlash yoki yangi kutish xonasi ochish (chess/draughts/xo/domino/sea)."""
        uid = int(user_id)
        game = str(g or "chess").strip().lower()
        with _DUEL_LOCK:
            for r in self.board_rooms.values():
                if r["g"] == game and r.get("pub") and not r["ready"] and r["w_id"] != uid and r["b_id"] is None:
                    r["b_id"] = uid
                    r["b_name"] = str(user_name or "Raqib")[:40]
                    r["ready"] = True
                    r["ver"] += 1
                    self.user_board_map[uid] = r["id"]
                    ser = self._serialize_board(r, uid)
                    return {"ok": True, "room": ser, **ser}

            # Agar foydalanuvchining o'zi ochiq kutish xonasi bo'lsa shuni qaytaramiz
            old_rid = self.user_board_map.get(uid)
            if old_rid and old_rid in self.board_rooms and not self.board_rooms[old_rid]["ready"] and self.board_rooms[old_rid]["g"] == game:
                room = self.board_rooms[old_rid]
            else:
                created = self.board_create_code(uid, user_name, g=game, pub=True)
                room = self.board_rooms[created["id"]]

            waiting_n = sum(1 for r in self.board_rooms.values() if r["g"] == game and r.get("pub") and not r["ready"])
            return {"ok": True, "wait": True, "n": max(1, waiting_n), "id": room["id"], "code": room["code"], "ver": room["ver"], "ready": False}

    def board_create_code(self, user_id: int, user_name: str, g: str = "chess", pub: bool = False) -> Dict[str, Any]:
        """Do'st bilan o'ynash uchun 4 xonali raqamli duel xonasi ochish."""
        uid = int(user_id)
        game = str(g or "chess").strip().lower()
        with _DUEL_LOCK:
            code = self._gen_num_code({r["code"] for r in self.board_rooms.values()})
            rid = f"bd_{code}_{int(time.time() * 1000) % 10000}"
            room = {
                "id": rid,
                "code": code,
                "g": game,
                "pub": pub,
                "w_id": uid,
                "w_name": str(user_name or "O'yinchi 1")[:40],
                "b_id": None,
                "b_name": "",
                "turn": "w",
                "ver": 1,
                "ready": False,
                "moves": [],
                "s": None,
                "over": None,
                "away": False,
                "updated_at": time.time(),
            }
            self.board_rooms[rid] = room
            self.user_board_map[uid] = rid
            ser = self._serialize_board(room, uid)
            return {"ok": True, "room": ser, **ser}

    def board_join(self, user_id: int, user_name: str, code: str = "") -> Dict[str, Any]:
        """Kod orqali taxta dueliga qo'shilish."""
        uid = int(user_id)
        clean = str(code or "").strip().upper()
        with _DUEL_LOCK:
            room = next((r for r in self.board_rooms.values() if r["code"] == clean), None)
            if not room:
                return {"ok": False, "error": "not_found"}
            if room["w_id"] != uid:
                if room["b_id"] is not None and room["b_id"] != uid:
                    return {"ok": False, "error": "full"}
                room["b_id"] = uid
                room["b_name"] = str(user_name or "O'yinchi 2")[:40]
                room["ready"] = True
                room["ver"] += 1
            self.user_board_map[uid] = room["id"]
            ser = self._serialize_board(room, uid)
            return {"ok": True, "room": ser, **ser}

    def board_poll(self, user_id: int, ver: int = -1, room_id: str = "") -> Dict[str, Any]:
        uid = int(user_id)
        with _DUEL_LOCK:
            rid = room_id or self.user_board_map.get(uid, "")
            room = self.board_rooms.get(rid)
            if not room:
                return {"ok": True, "idle": True}
            if not room["ready"]:
                waiting_n = sum(1 for r in self.board_rooms.values() if r["g"] == room["g"] and r.get("pub") and not r["ready"])
                return {"ok": True, "wait": True, "n": max(1, waiting_n)}
            if int(ver) == int(room["ver"]):
                return {"ok": True, "same": True, "away": room["away"], "ver": room["ver"]}
            ser = self._serialize_board(room, uid)
            return {"ok": True, "room": ser, **ser}

    def board_move(self, user_id: int, move_data: Dict[str, Any]) -> Dict[str, Any]:
        uid = int(user_id)
        with _DUEL_LOCK:
            rid = str(move_data.get("id") or self.user_board_map.get(uid, ""))
            room = self.board_rooms.get(rid)
            if not room:
                return {"ok": False, "error": "no_room"}
            me_side = "w" if uid == room["w_id"] else "b"
            if move_data.get("m") is not None:
                room["moves"].append(move_data["m"])
            if move_data.get("n"):
                room["turn"] = move_data["n"]
            else:
                room["turn"] = "b" if me_side == "w" else "w"
            if "s" in move_data:
                room["s"] = move_data["s"]
            if "end" in move_data and move_data["end"] is not None:
                end_val = move_data["end"]
                if isinstance(end_val, dict):
                    room["over"] = end_val
                else:
                    room["over"] = {"win": end_val, "why": move_data.get("why") or "end"}
            room["ver"] += 1
            room["updated_at"] = time.time()
            ser = self._serialize_board(room, uid)
            return {"ok": True, "room": ser, **ser}

    def board_resign(self, user_id: int) -> Dict[str, Any]:
        uid = int(user_id)
        with _DUEL_LOCK:
            rid = self.user_board_map.pop(uid, "")
            room = self.board_rooms.get(rid)
            if not room:
                return {"ok": True}
            if not room["ready"]:
                self.board_rooms.pop(rid, None)
                return {"ok": True, "idle": True}
            win_side = "b" if uid == room["w_id"] else "w"
            room["over"] = {"win": win_side, "why": "resign"}
            room["ver"] += 1
            ser = self._serialize_board(room, uid)
            return {"ok": True, "room": ser, **ser}

    @staticmethod
    def _serialize_board(room: Dict[str, Any], uid: int) -> Dict[str, Any]:
        is_w = (uid == room["w_id"])
        return {
            "id": room["id"],
            "code": room["code"],
            "g": room["g"],
            "me": "w" if is_w else "b",
            "my": room["w_name"] if is_w else room["b_name"],
            "opp": room["b_name"] if is_w else room["w_name"],
            "turn": room["turn"],
            "ver": room["ver"],
            "ready": room["ready"],
            "moves": list(room["moves"]),
            "s": room["s"],
            "over": room["over"],
            "away": room["away"],
        }


duel_service = DuelService()
