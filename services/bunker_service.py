"""
Bunker Survival Party Game Service - Bauntys (@BauntyCinemabot)
4–16 kishilik omon qolish o'yini: falokat va bunker kartalari, 6 ta shaxsiy karta + maxsus karta,
bosqichma-bosqich ochish, ovoz berish, surgun qilish, AI botlar va xona boshqaruvi.
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

_BUNKER_LOCK = threading.RLock()
_BUNKER_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "bunker_state.json",
)

CATASTROPHES: List[Dict[str, str]] = [
    {
        "t": "Kuchli Quyosh chaqnashi",
        "d": "Kuchli magnit bo'roni barcha elektr tarmoqlari va sun'iy yo'ldoshlarni ishdan chiqardi. Sirtda radiatsiya yuqori, harorat +58°C ga yetgan.",
    },
    {
        "t": "Zombi virusi epidemiyasi",
        "d": "Noma'lum mutatsiyaga uchragan virus shaharlarni egalladi. Tashqarida tirik qolish imkonsiz, dori va karantin nazorati zarur.",
    },
    {
        "t": "Asteroid to'qnashuvi va chang buluti",
        "d": "Yer bilan yirik asteroid to'qnashib, osmonni qalin kul qopladi. Quyosh nuri 90% ga kamaydi, hosil yetishtirish faqat yopiq tizimda mumkin.",
    },
    {
        "t": "Global muzlik davri",
        "d": "Okean oqimlari to'xtab, harorat -45°C gacha tushib ketdi. Tashqarida faqat maxsus isitish va energiyasiz yashash imkonsiz.",
    },
    {
        "t": "Okean toshqini",
        "d": "Qutb muzliklari tez erishi oqibatida quruqlikning 75% qismi suv ostida qoldi. Germetik va suv tozalash tizimli bunker najot yo'li.",
    },
    {
        "t": "Sun'iy intellekt qo'zg'oloni",
        "d": "Avtonom harbiy dronlar tarmog'i insoniyatga qarshi chiqdi. Sirtda yashirinish uchun radiojimlik va texnik bilim talab etiladi.",
    },
]

BUNKER_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "№7-Bunker «Oromgoh»",
        "area": "220 m²",
        "duration": "12 oy",
        "food": "8 oylik konserva va gidroponika",
        "gear": ["Tibbiy blok", "Quyosh/dizel generatori", "Suv filtri", "Kichik ustaxona"],
        "flaw": "Ventilyatsiya tizimi har oyda mexanik tozalashni talab qiladi.",
    },
    {
        "name": "№12-Bunker «Temir Qal'a»",
        "area": "180 m²",
        "duration": "18 oy",
        "food": "14 oylik quruq ratsion",
        "gear": ["Radiostansiya", "Issiqxona bo'limi", "Qurol-yarog' seyfi", "Labaratoriya"],
        "flaw": "Ichimlik suvi zaxirasi cheklangan — tozalash qurilmasini ta'mirlash kerak.",
    },
    {
        "name": "№4-Bunker «Umid Shaxti»",
        "area": "260 m²",
        "duration": "10 oy",
        "food": "10 oylik oziq-ovqat va urug'lar",
        "gear": ["Jarrohlik stoli", "Elektr payvandlash apparati", "Kutubxona", "Zaxira chiqish tunneli"],
        "flaw": "Asosiy generatorning sovutish qismi zaiflashgan.",
    },
]

DECK_POOLS: Dict[str, List[str]] = {
    "kasb": [
        "Jarroh-shifokor (8 yil tajriba)",
        "Energetika muhandisi",
        "Agronom va botanik",
        "Qutqaruvchi-harbiy",
        "Professional oshpaz",
        "Psixolog-terapevt",
        "Qurilish ustasi",
        "Radioelektronik mexanik",
        "Biokimyogar",
        "Maktab o'qituvchisi",
        "Dasturchi-kiberxavfsizlik",
        "Ovchi va o'rmonchi",
        "Suv ta'minoti mutaxassisi",
        "Veterinar shifokor",
        "Tish shifokori",
        "Tikuvchi-dizayner",
    ],
    "sogliq": [
        "To'liq sog'lom",
        "Yengil astma (ingalyator bor)",
        "Ko'rish -2.5 (ko'zoynakda)",
        "Mustahkam jismoniy tayyorgarlik",
        "Changga allergiya",
        "Qon bosimi biroz past",
        "Tish og'rig'i (davolanmagan)",
        "A'lo immunitet",
        "Tizza bo'g'imida eski jarohat",
        "Uyqusizlikka moyillik",
        "Balandlikdan qo'rqish",
        "Mutlaqo chiniqqan",
    ],
    "biologiya": [
        "Erkak, 27 yosh",
        "Ayol, 25 yosh",
        "Erkak, 34 yosh",
        "Ayol, 29 yosh",
        "Erkak, 42 yosh",
        "Ayol, 37 yosh",
        "Erkak, 22 yosh",
        "Ayol, 31 yosh",
        "Erkak, 48 yosh",
        "Ayol, 24 yosh",
        "Erkak, 30 yosh",
        "Ayol, 41 yosh",
    ],
    "xobbi": [
        "Gidroponika va ko'chat yetishtirish",
        "Shaxmat va mantiqiy strategiya",
        "Pichoq va metall bilan ishlash",
        "Birinchi yordam ko'nikmalari",
        "Tikuvchilik va kiyim ta'miri",
        "Radioaloqa va sxemalar yig'ish",
        "Ovchilik va tuzoq qo'yish",
        "Musiqa va gitara chalish",
        "Yog'och o'ymakorligi va duradgorlik",
        "Uzoq masofaga yugurish",
        "Pishiriq va non yopish",
        "Astronomiya va xaritalar",
    ],
    "bagaj": [
        "To'liq dorixona qutisi",
        "Quyosh batareyali chiroq va pauerbank",
        "Sabzavot urug'lari kolleksiyasi",
        "Ko'p funksiyali asboblar jamlanmasi",
        "Portativ suv filtri",
        "Ratsiya (2 dona)",
        "Issiq uxlash qopi va pichoq",
        "Payvandlash mini-to'plami",
        "Konservalangan go'sht (10 banka)",
        "Tibbiy qo'llanma va ensiklopediya",
        "Qulf ochish asboblari",
        "Katta quti gugurt va gaz gorelkasi",
    ],
    "fakt": [
        "Stress holatida sovuqqon qaror qabul qiladi",
        "3 ta xorijiy tilni biladi",
        "Qorong'uda juda qo'rqadi",
        "Guruhdagi nizolarni tez tinchlantiradi",
        "Yashirincha zaxira dori olib kelgan",
        "Bunker loyihasini ilgari o'rgangan",
        "Juda tez yuguradi va chaqqon",
        "Hech kimga osonlikcha ishonmaydi",
        "Ajoyib xotiraga ega",
        "Tashqarida yashirin qutqaruv guruhi borligini biladi",
        "Suv ostida uzoq tura oladi",
        "Uzoq vaqt ochlikka chidamli",
    ],
}

SPECIAL_CARDS: List[Dict[str, str]] = [
    {"code": "swap_prof", "t": "Kasb almashtirish", "d": "O'zingiz yoki istalgan o'yinchining kasb kartasini yangisiga almashtiradi."},
    {"code": "heal", "t": "Shifokor ko'rigi", "d": "O'zingizdagi sog'liq muammosini «To'liq sog'lom» ga tuzatadi."},
    {"code": "double_vote", "t": "Ikki karra ovoz", "d": "Joriy ovoz berishda sizning ovozingiz 2 ta hisoblanadi."},
    {"code": "shield", "t": "Immunitet qalqoni", "d": "Bu bosqichda sizga berilgan ovozlar bekor qilinadi."},
    {"code": "scout", "t": "Bunker tekshiruvi", "d": "Bunkerning bitta qo'shimcha zaxira resursini faollashtiradi."},
]

BOT_NAMES = [
    "Azizbek", "Madina", "Jasur", "Sevara", "Bobur", "Nilufar",
    "Timur", "Kamola", "Sardor", "Dilnoza", "Bekzod", "Farida",
]

CARD_LABELS = {
    "kasb": "Kasb",
    "sogliq": "Sog'liq",
    "biologiya": "Biologiya",
    "xobbi": "Xobbi",
    "bagaj": "Bagaj",
    "fakt": "Fakt",
}

CARD_ORDER = ["kasb", "sogliq", "biologiya", "xobbi", "bagaj", "fakt"]


class BunkerRoom:
    """Bitta Bunker o'yin xonasi holati."""

    def __init__(
        self,
        code: str,
        host_id: int,
        host_name: str,
        room_name: str = "",
        max_players: int = 8,
        pub: bool = True,
    ) -> None:
        self.code = code
        self.id = code
        self.name = (room_name or "").strip() or f"{host_name} bunkeri"
        self.host = int(host_id)
        self.max_players = max(4, min(16, int(max_players or 8)))
        self.pub = bool(pub)
        self.phase = "lobby"  # lobby -> reveal -> vote -> result -> end
        self.round = 1
        self.ver = 1
        self.created_at = time.time()
        self.updated_at = time.time()
        self.catastrophe = random.choice(CATASTROPHES)
        self.bunker = dict(random.choice(BUNKER_TEMPLATES))
        self.bunker["slots"] = 2
        self.players: List[Dict[str, Any]] = []
        self.revealed_this_round: set = set()
        self.votes: Dict[int, int] = {}
        self.last_exiled: Optional[Dict[str, Any]] = None
        self.chat: List[Dict[str, Any]] = []
        self.mid = 0
        self.add_player(host_id, host_name, is_bot=False)
        self.add_msg(0, "Tizim", f"☢️ {host_name} yangi bunker xonasini ochdi. Kod: {self.code}")

    def add_msg(self, user_id: int, name: str, text: str) -> None:
        self.mid += 1
        self.chat.append({
            "id": self.mid,
            "u": int(user_id),
            "n": str(name),
            "t": str(text)[:300],
            "ts": int(time.time()),
        })
        if len(self.chat) > 60:
            self.chat = self.chat[-60:]
        self.ver += 1
        self.updated_at = time.time()

    def add_player(self, user_id: int, name: str, is_bot: bool = False) -> bool:
        if any(p["u"] == int(user_id) for p in self.players):
            return True
        if self.phase != "lobby" or len(self.players) >= self.max_players:
            return False
        self.players.append({
            "u": int(user_id),
            "n": str(name)[:40],
            "bot": bool(is_bot),
            "alive": True,
            "exiled_round": None,
            "cards": {},
            "special": None,
            "special_used": False,
        })
        self.bunker["slots"] = max(2, len(self.players) // 2)
        self.ver += 1
        self.updated_at = time.time()
        return True

    def start_game(self) -> bool:
        if len(self.players) < 4 or self.phase != "lobby":
            return False
        self.bunker["slots"] = max(2, len(self.players) // 2)
        n_p = len(self.players)

        sampled: Dict[str, List[str]] = {}
        for k, pool in DECK_POOLS.items():
            if len(pool) >= n_p:
                sampled[k] = random.sample(pool, n_p)
            else:
                sampled[k] = [random.choice(pool) for _ in range(n_p)]

        for idx, p in enumerate(self.players):
            cards = {}
            for k in CARD_ORDER:
                cards[k] = {"label": CARD_LABELS[k], "val": sampled[k][idx], "rev": False}
            p["cards"] = cards
            p["special"] = dict(random.choice(SPECIAL_CARDS))
            p["special_used"] = False
            p["alive"] = True
            p["exiled_round"] = None

        self.phase = "reveal"
        self.round = 1
        self.revealed_this_round = set()
        self.votes = {}
        self.last_exiled = None
        self.add_msg(
            0,
            "Tizim",
            f"🚨 Falokat: {self.catastrophe['t']}! Bunkerga faqat {self.bunker['slots']} kishi kira oladi. 1-bosqich: kartangizni oching!",
        )
        return True

    def reveal_card(self, user_id: int, card_key: str = "") -> Dict[str, Any]:
        if self.phase != "reveal":
            return {"ok": False, "error": "wrong_phase"}
        p = next((x for x in self.players if x["u"] == int(user_id) and x["alive"]), None)
        if not p:
            return {"ok": False, "error": "not_alive"}

        chosen = card_key.strip().lower()
        if not chosen or chosen not in CARD_ORDER or p["cards"][chosen]["rev"]:
            chosen = next((k for k in CARD_ORDER if not p["cards"][k]["rev"]), "")
        if not chosen:
            return {"ok": False, "error": "all_revealed"}

        p["cards"][chosen]["rev"] = True
        self.revealed_this_round.add(int(user_id))
        self.add_msg(0, "Tizim", f"🃏 {p['n']} «{CARD_LABELS[chosen]}» kartasini ochdi: {p['cards'][chosen]['val']}")

        # Botlar ham shu bosqichda o'z kartalaridan birini ochadi
        for bp in self.players:
            if bp["alive"] and bp["bot"] and bp["u"] not in self.revealed_this_round:
                bk = next((k for k in CARD_ORDER if not bp["cards"][k]["rev"]), "")
                if bk:
                    bp["cards"][bk]["rev"] = True
                    self.revealed_this_round.add(bp["u"])
                    self.add_msg(0, "Tizim", f"🤖 {bp['n']} «{CARD_LABELS[bk]}» kartasini ochdi: {bp['cards'][bk]['val']}")

        alive_humans = [x["u"] for x in self.players if x["alive"] and not x["bot"]]
        if all(uid in self.revealed_this_round for uid in alive_humans):
            self.phase = "vote"
            self.votes.clear()
            self.add_msg(0, "Tizim", "🗳 Barcha o'yinchilar karta ochdi. Ovoz berish boshlandi! Kim bunkerdan tashqarida qoladi?")

        self.ver += 1
        self.updated_at = time.time()
        return {"ok": True, "card": chosen, "val": p["cards"][chosen]["val"]}

    def vote(self, voter_id: int, target_id: int) -> Dict[str, Any]:
        if self.phase != "vote":
            return {"ok": False, "error": "wrong_phase"}
        voter = next((x for x in self.players if x["u"] == int(voter_id) and x["alive"]), None)
        target = next((x for x in self.players if x["u"] == int(target_id) and x["alive"]), None)
        if not voter or not target:
            return {"ok": False, "error": "invalid_target"}

        self.votes[int(voter_id)] = int(target_id)
        self.add_msg(0, "Tizim", f"🗳 {voter['n']} ovoz berdi -> {target['n']}")

        # Botlar ham tirik boshqa o'yinchiga ovoz beradi
        alive_ids = [x["u"] for x in self.players if x["alive"]]
        for bp in self.players:
            if bp["alive"] and bp["bot"] and bp["u"] not in self.votes:
                others = [uid for uid in alive_ids if uid != bp["u"]]
                if others:
                    self.votes[bp["u"]] = random.choice(others)

        alive_humans = [x["u"] for x in self.players if x["alive"] and not x["bot"]]
        if all(uid in self.votes for uid in alive_humans):
            self._tally_votes()

        self.ver += 1
        self.updated_at = time.time()
        return {"ok": True}

    def _tally_votes(self) -> None:
        tally: Dict[int, int] = {}
        for _, tgt in self.votes.items():
            tally[tgt] = tally.get(tgt, 0) + 1

        if tally:
            max_v = max(tally.values())
            candidates = [uid for uid, cnt in tally.items() if cnt == max_v]
            exiled_id = random.choice(candidates)
        else:
            alive_ids = [x["u"] for x in self.players if x["alive"]]
            exiled_id = random.choice(alive_ids) if alive_ids else None

        exiled_player = next((x for x in self.players if x["u"] == exiled_id), None)
        if exiled_player:
            exiled_player["alive"] = False
            exiled_player["exiled_round"] = self.round
            for k in exiled_player["cards"]:
                exiled_player["cards"][k]["rev"] = True
            self.last_exiled = {"u": exiled_player["u"], "n": exiled_player["n"], "round": self.round}
            self.add_msg(0, "Tizim", f"🚪 Ovoz berish natijasiga ko'ra {exiled_player['n']} bunkerga kiritilmadi (surgun qilindi)!")

        self.votes.clear()
        alive_cnt = sum(1 for x in self.players if x["alive"])
        if alive_cnt <= self.bunker["slots"]:
            self.phase = "end"
            winners = ", ".join(x["n"] for x in self.players if x["alive"])
            self.add_msg(0, "Tizim", f"🏆 O'yin tugadi! Bunkerga kirgan g'oliblar: {winners}")
        else:
            self.phase = "result"

    def next_round(self) -> bool:
        if self.phase == "reveal":
            self.phase = "vote"
            self.votes.clear()
            self.ver += 1
            self.updated_at = time.time()
            return True
        if self.phase != "result":
            return False
        self.round += 1
        self.phase = "reveal"
        self.revealed_this_round = set()
        self.votes.clear()
        self.add_msg(0, "Tizim", f"🔄 {self.round}-bosqich boshlandi! Navbatdagi kartangizni oching.")
        # Agar tirik inson o'yinchilar qolmagan bo'lsa, qolgan botlar bosqichni avtomatik yakunlaydi
        alive_humans = [x for x in self.players if x["alive"] and not x["bot"]]
        if not alive_humans:
            for bp in self.players:
                if bp["alive"] and bp["bot"]:
                    bk = next((k for k in CARD_ORDER if not bp["cards"][k]["rev"]), "")
                    if bk:
                        bp["cards"][bk]["rev"] = True
            alive_ids = [x["u"] for x in self.players if x["alive"]]
            for bp in self.players:
                if bp["alive"] and bp["bot"]:
                    others = [uid for uid in alive_ids if uid != bp["u"]]
                    if others:
                        self.votes[bp["u"]] = random.choice(others)
            self._tally_votes()
        self.ver += 1
        self.updated_at = time.time()
        return True

    def to_dict_for_user(self, viewer_id: int) -> Dict[str, Any]:
        vid = int(viewer_id)
        players_view = []
        for p in self.players:
            is_self = (p["u"] == vid)
            cards_view = {}
            for k, c in p.get("cards", {}).items():
                show = bool(c.get("rev")) or is_self or not p["alive"] or self.phase == "end"
                cards_view[k] = {
                    "label": c["label"],
                    "val": c["val"] if show else "Yashirin",
                    "rev": bool(c.get("rev")),
                }
            players_view.append({
                "u": p["u"],
                "n": p["n"],
                "bot": p["bot"],
                "alive": p["alive"],
                "host": p["u"] == self.host,
                "exiled_round": p["exiled_round"],
                "cards": cards_view,
                "special": p["special"] if is_self else None,
                "revealed_now": p["u"] in self.revealed_this_round,
                "voted_now": p["u"] in self.votes,
            })

        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "host": self.host,
            "is_host": self.host == vid,
            "phase": self.phase,
            "round": self.round,
            "ver": self.ver,
            "max": self.max_players,
            "catastrophe": self.catastrophe,
            "bunker": self.bunker,
            "players": players_view,
            "alive_count": sum(1 for p in self.players if p["alive"]),
            "last_exiled": self.last_exiled,
            "chat": list(self.chat[-25:]),
        }


class BunkerService:
    """Bunker o'yini xonalari boshqaruvi."""

    def __init__(self) -> None:
        self.rooms: Dict[str, BunkerRoom] = {}
        self.user_room_map: Dict[int, str] = {}
        self._stats = self._load_stats()

    def _load_stats(self) -> Dict[str, Any]:
        with _BUNKER_LOCK:
            if not os.path.exists(_BUNKER_STATE_PATH):
                return {"games": 0}
            try:
                with open(_BUNKER_STATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
            return {"games": 0}

    def _save_stats(self) -> None:
        with _BUNKER_LOCK:
            os.makedirs(os.path.dirname(_BUNKER_STATE_PATH), exist_ok=True)
            tmp = f"{_BUNKER_STATE_PATH}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _BUNKER_STATE_PATH)

    def _cleanup(self) -> None:
        now = time.time()
        for code in list(self.rooms.keys()):
            r = self.rooms[code]
            age = now - r.updated_at
            if not r.players or (r.phase == "end" and age > 1800) or age > 7200:
                self.rooms.pop(code, None)
                for uid, rc in list(self.user_room_map.items()):
                    if rc == code:
                        self.user_room_map.pop(uid, None)

    def get_home(self, user_id: int, user_name: str = "O'yinchi") -> Dict[str, Any]:
        """Bunker bosh sahifasi: ochiq xonalar va joriy xona."""
        with _BUNKER_LOCK:
            self._cleanup()
            pub_rooms = []
            for r in self.rooms.values():
                if r.pub and r.phase == "lobby":
                    pub_rooms.append({
                        "code": r.code,
                        "name": r.name,
                        "players": len(r.players),
                        "max": r.max_players,
                        "catastrophe": r.catastrophe["t"],
                    })
            cur_code = self.user_room_map.get(int(user_id))
            cur_room = self.rooms[cur_code].to_dict_for_user(user_id) if cur_code and cur_code in self.rooms else None
            return {
                "ok": True,
                "me": int(user_id),
                "name": user_name,
                "rooms": pub_rooms,
                "cur": cur_room,
                "pub": sum(len(r.players) for r in self.rooms.values() if r.pub and r.phase == "lobby"),
                "games_total": int(self._stats.get("games", 0)),
            }

    def create_room(
        self,
        user_id: int,
        user_name: str = "O'yinchi",
        room_name: str = "",
        max_players: int = 8,
        pub: bool = True,
    ) -> Dict[str, Any]:
        """Yangi Bunker xonasini ochish."""
        with _BUNKER_LOCK:
            self._cleanup()
            self.leave_room(user_id)
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            while code in self.rooms:
                code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            room = BunkerRoom(
                code=code,
                host_id=user_id,
                host_name=user_name,
                room_name=room_name,
                max_players=max_players,
                pub=pub,
            )
            self.rooms[code] = room
            self.user_room_map[int(user_id)] = code
            return {"ok": True, "code": code, "room": room.to_dict_for_user(user_id)}

    def join_room(self, user_id: int, user_name: str = "O'yinchi", code: str = "") -> Dict[str, Any]:
        """Kod orqali xonaga qo'shilish."""
        clean_code = str(code or "").strip().upper()
        with _BUNKER_LOCK:
            room = self.rooms.get(clean_code)
            if not room:
                return {"ok": False, "error": "not_found", "msg": "Bunday kodli Bunker xonasi topilmadi."}
            old_code = self.user_room_map.get(int(user_id))
            if old_code and old_code != clean_code:
                self.leave_room(user_id)
            if not room.add_player(user_id, user_name, is_bot=False):
                return {"ok": False, "error": "room_full_or_started", "msg": "Xona to'lgan yoki o'yin boshlanib bo'lgan."}
            self.user_room_map[int(user_id)] = clean_code
            room.add_msg(0, "Tizim", f"👤 {user_name} bunkerga qo'shildi.")
            return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def _get_user_room(self, user_id: int, code: str = "") -> Optional[BunkerRoom]:
        if code:
            r = self.rooms.get(str(code).strip().upper())
            if r:
                return r
        mapped = self.user_room_map.get(int(user_id))
        return self.rooms.get(mapped) if mapped else None

    def add_bots(self, user_id: int, count: int = 3, code: str = "") -> Dict[str, Any]:
        """Sinov yoki yakka o'yin uchun xonaga AI botlarni qo'shish."""
        with _BUNKER_LOCK:
            room = self._get_user_room(user_id, code)
            if not room:
                return {"ok": False, "error": "no_room"}
            if room.host != int(user_id):
                return {"ok": False, "error": "host_only"}
            if room.phase != "lobby":
                return {"ok": False, "error": "already_started"}
            want = max(1, min(15, int(count or 1)))
            used_names = {p["n"] for p in room.players}
            added = 0
            for idx in range(want):
                if len(room.players) >= room.max_players:
                    break
                avail = [nm for nm in BOT_NAMES if nm not in used_names]
                bname = avail[0] if avail else f"Bot-{len(room.players) + 1}"
                used_names.add(bname)
                bot_id = -(len(room.players) + 1 + idx * 17)
                while any(p["u"] == bot_id for p in room.players):
                    bot_id -= 1
                if room.add_player(bot_id, bname, is_bot=True):
                    added += 1
            if added:
                room.add_msg(0, "Tizim", f"🤖 Xonaga {added} ta AI o'yinchi qo'shildi.")
            return {"ok": True, "added": added, "room": room.to_dict_for_user(user_id)}

    def start_game(self, user_id: int, code: str = "") -> Dict[str, Any]:
        """Bunker o'yinini boshlash (kamida 4 o'yinchi, faqat host)."""
        with _BUNKER_LOCK:
            room = self._get_user_room(user_id, code)
            if not room:
                return {"ok": False, "error": "no_room"}
            if room.host != int(user_id):
                return {"ok": False, "error": "host_only"}
            if len(room.players) < 4:
                return {"ok": False, "error": "need_4_players", "msg": "O'yinni boshlash uchun kamida 4 nafar o'yinchi kerak (yoki bot qo'shing)."}
            if not room.start_game():
                return {"ok": False, "error": "cannot_start"}
            self._stats["games"] = int(self._stats.get("games", 0)) + 1
            self._save_stats()
            return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def reveal_card(self, user_id: int, card_key: str = "", code: str = "") -> Dict[str, Any]:
        """Joriy bosqichda o'yinchining bitta kartasini ochish."""
        with _BUNKER_LOCK:
            room = self._get_user_room(user_id, code)
            if not room:
                return {"ok": False, "error": "no_room"}
            res = room.reveal_card(user_id, card_key=card_key)
            if not res.get("ok"):
                return res
            return {"ok": True, **res, "room": room.to_dict_for_user(user_id)}

    def vote(self, user_id: int, target_id: int, code: str = "") -> Dict[str, Any]:
        """O'yinchini bunkerdan chiqarib yuborishga ovoz berish."""
        with _BUNKER_LOCK:
            room = self._get_user_room(user_id, code)
            if not room:
                return {"ok": False, "error": "no_room"}
            res = room.vote(user_id, target_id=target_id)
            if not res.get("ok"):
                return res
            return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def next_round(self, user_id: int, code: str = "") -> Dict[str, Any]:
        """Keyingi bosqichga o'tish (faqat host)."""
        with _BUNKER_LOCK:
            room = self._get_user_room(user_id, code)
            if not room:
                return {"ok": False, "error": "no_room"}
            if room.host != int(user_id):
                return {"ok": False, "error": "host_only"}
            if not room.next_round():
                return {"ok": False, "error": "wrong_phase"}
            return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def send_chat(self, user_id: int, user_name: str, text: str, code: str = "") -> Dict[str, Any]:
        """Bunker xona chatiga xabar yuborish."""
        clean_t = str(text or "").strip()
        if not clean_t:
            return {"ok": False, "error": "empty"}
        with _BUNKER_LOCK:
            room = self._get_user_room(user_id, code)
            if not room:
                return {"ok": False, "error": "no_room"}
            room.add_msg(user_id, user_name, clean_t)
            return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def leave_room(self, user_id: int) -> Dict[str, Any]:
        """Xonadan chiqish."""
        uid = int(user_id)
        with _BUNKER_LOCK:
            code = self.user_room_map.pop(uid, None)
            if not code or code not in self.rooms:
                return {"ok": True}
            room = self.rooms[code]
            room.players = [p for p in room.players if p["u"] != uid]
            humans = [p for p in room.players if not p["bot"]]
            if not humans:
                self.rooms.pop(code, None)
                return {"ok": True}
            if room.host == uid:
                room.host = humans[0]["u"]
                room.add_msg(0, "Tizim", f"👑 Yangi boshlovchi: {humans[0]['n']}")
            room.ver += 1
            return {"ok": True}

    def get_state(self, code_or_user_id: Any = "", user_id: int = 0) -> Dict[str, Any]:
        """Xona holatini kod yoki foydalanuvchi ID bo'yicha olish."""
        with _BUNKER_LOCK:
            room = None
            raw = str(code_or_user_id or "").strip().upper()
            if raw in self.rooms:
                room = self.rooms[raw]
            elif user_id:
                room = self._get_user_room(user_id)
            if not room:
                return {"ok": False, "error": "no_room"}
            vid = user_id or (room.host if room.players else 0)
            return {"ok": True, "room": room.to_dict_for_user(vid)}


bunker_service = BunkerService()
