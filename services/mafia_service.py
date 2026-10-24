"""
Mafia Game Engine & Service - Bauntys
Onlayn Mafia o'yini (3–20 kishi), xonalar, rollar (Don, Mafia, Shifokor, Komissar, Tinch aholi),
tungi harakatlar, kunduzgi ovoz berish, chat va ovozli xabarlar.
100% Bauntys brendi.
"""
import time
import random
import logging
from typing import Dict, Any, Optional, List, Set
from config import config

logger = logging.getLogger(__name__)

LOOKS = ["bozor", "novvoy", "taksi", "talaba", "ustoz", "sport", "dehqon"]

ROLES = {
    "don": {"n": "Don", "ic": "🎩", "c": "maf", "ch": "don"},
    "maf": {"n": "Mafia", "ic": "🔪", "c": "maf", "ch": "qotil"},
    "doc": {"n": "Shifokor", "ic": "💉", "c": "doc", "ch": "doc"},
    "kom": {"n": "Komissar", "ic": "🔍", "c": "kom", "ch": "kom"},
    "civ": {"n": "Tinch aholi", "ic": "👨‍🌾", "c": "civ", "ch": "bozor"},
}


class MafiaRoom:
    """Bitta Mafia xonasi holati."""

    def __init__(
        self,
        room_id: str,
        name: str,
        host_id: int,
        host_name: str,
        max_players: int = 10,
        code: Optional[str] = None,
        pub: bool = False,
        lk: Optional[str] = None,
        c: int = 0
    ):
        self.id = room_id
        self.code = code or str(random.randint(1000, 9999))
        self.name = name
        self.host = host_id
        self.max_players = max(3, min(20, max_players))
        self.pub = pub
        self.group = False
        self.phase = "lobby"  # lobby, night, morning, day, vote, last, end
        self.day = 1
        self.ver = 1
        self.left = 60
        self.left_at = time.time()
        self.players: List[Dict[str, Any]] = []
        self.chat: List[Dict[str, Any]] = []
        self.mid = 0
        self.winner: Optional[str] = None
        self.checks: List[Dict[str, Any]] = []
        self.night_actions: Dict[int, int] = {}
        self.votes: Dict[int, int] = {}
        self.skips: Set[int] = set()
        self.cond: Optional[int] = None
        self.kmode = "check"
        self.add_player(host_id, host_name, lk=lk, c=c)

    def add_player(self, user_id: int, name: str, lk: Optional[str] = None, c: int = 0) -> bool:
        for p in self.players:
            if p["u"] == user_id:
                if lk and lk in LOOKS:
                    p["lk"] = lk
                if c is not None:
                    p["c"] = c
                return True
        if len(self.players) >= self.max_players:
            return False
        look = lk if (lk and lk in LOOKS) else LOOKS[len(self.players) % len(LOOKS)]
        self.players.append({
            "u": user_id,
            "id": user_id,
            "n": name or f"O'yinchi {len(self.players) + 1}",
            "alive": True,
            "lk": look,
            "look": look,
            "c": c or 0,
            "role": "civ",
            "host": (user_id == self.host),
        })
        self.ver += 1
        self.add_msg(0, "Tizim", f"👋 {name} xonaga qo'shildi ({len(self.players)}/{self.max_players})")
        return True

    def remove_player(self, user_id: int) -> None:
        p = next((p for p in self.players if p["u"] == user_id), None)
        if p:
            self.players = [x for x in self.players if x["u"] != user_id]
            self.night_actions.pop(user_id, None)
            self.votes.pop(user_id, None)
            self.skips.discard(user_id)
            self.ver += 1
            self.add_msg(0, "Tizim", f"🚪 {p['n']} xonani tark etdi")
            if self.host == user_id and self.players:
                self.host = self.players[0]["u"]
                self.players[0]["host"] = True

    def add_msg(self, user_id: int, name: str, text: str, emo: Optional[str] = None, ch: str = "all") -> Dict[str, Any]:
        self.mid += 1
        msg = {
            "i": self.mid,
            "u": user_id,
            "n": name,
            "t": text,
            "e": emo,
            "ch": ch,
            "ts": time.time(),
        }
        self.chat.append(msg)
        if len(self.chat) > 120:
            self.chat.pop(0)
        self.ver += 1
        return msg

    def set_look(self, user_id: int, lk: Optional[str] = None, c: int = 0) -> bool:
        p = next((p for p in self.players if p["u"] == user_id), None)
        if not p:
            return False
        if lk and lk in LOOKS:
            p["lk"] = lk
            p["look"] = lk
        p["c"] = c
        self.ver += 1
        return True

    def start_game(self) -> bool:
        n = len(self.players)
        if n < 3:
            return False

        random.shuffle(self.players)
        roles_pool = ["don", "kom", "doc"]
        if n >= 5:
            roles_pool.append("maf")
        while len(roles_pool) < n:
            roles_pool.append("civ")

        for idx, p in enumerate(self.players):
            p["role"] = roles_pool[idx]
            p["alive"] = True
            p["host"] = (p["u"] == self.host)

        self.phase = "night"
        self.day = 1
        self.left = 35
        self.left_at = time.time()
        self.night_actions.clear()
        self.votes.clear()
        self.skips.clear()
        self.checks.clear()
        self.cond = None
        self.ver += 1
        self.add_msg(0, "Tizim", "🌙 Shahar uxlaydi… Mafia va qahramonlar uyg'onadi!")
        return True

    def act(self, user_id: int, target_id: int, mode: str = "check") -> bool:
        voter = next((p for p in self.players if p["u"] == user_id and p["alive"]), None)
        if not voter or self.phase != "night":
            return False

        self.night_actions[user_id] = target_id
        if voter["role"] == "kom":
            self.kmode = mode
            if mode == "check":
                target_p = next((p for p in self.players if p["u"] == target_id), None)
                if target_p:
                    is_maf = target_p["role"] in ("don", "maf")
                    if not any(c["t"] == target_id for c in self.checks):
                        self.checks.append({"t": target_id, "r": "maf" if is_maf else "civ"})
        self.ver += 1
        return True

    def vote(self, voter_id: int, target_id: int) -> bool:
        voter = next((p for p in self.players if p["u"] == voter_id and p["alive"]), None)
        if not voter or self.phase != "vote":
            return False

        self.votes[voter_id] = target_id
        self.ver += 1
        target_p = next((p for p in self.players if p["u"] == target_id), None)
        t_name = target_p["n"] if target_p else "betaraf"
        self.add_msg(0, "Tizim", f"🗳 {voter['n']} ovoz berdi: {t_name}")
        return True

    def skip(self, user_id: int) -> bool:
        if self.phase != "day":
            return False
        self.skips.add(user_id)
        alive_players = [p for p in self.players if p["alive"]]
        needed = max(2, int(len(alive_players) * 2 / 3))
        if len(self.skips) >= needed:
            self.phase = "vote"
            self.left = 30
            self.left_at = time.time()
            self.votes.clear()
            self.add_msg(0, "Tizim", "🗳 Ovoz berish bosqichi boshlandi! Kimni osamiz?")
        self.ver += 1
        return True

    def _check_game_over(self) -> bool:
        alive_maf = [p for p in self.players if p["alive"] and p["role"] in ("don", "maf")]
        alive_civ = [p for p in self.players if p["alive"] and p["role"] not in ("don", "maf")]

        if not alive_maf:
            self.phase = "end"
            self.winner = "civ"
            self.left = 0
            self.ver += 1
            self.add_msg(0, "Tizim", "🎉 Tinch aholi g'alaba qozondi! Shahardagi barcha mafiozlar zararsizlantirildi!")
            return True
        if len(alive_maf) >= len(alive_civ):
            self.phase = "end"
            self.winner = "maf"
            self.left = 0
            self.ver += 1
            self.add_msg(0, "Tizim", "🔪 Mafia g'alaba qozondi! Shahar to'liq mafiyalar nazoratiga o'tdi!")
            return True
        return False

    def step_timer(self) -> None:
        """Taymer tugaganda o'yin bosqichini avtomatik siljitish."""
        if self.phase in ("lobby", "end"):
            return

        elapsed = int(time.time() - self.left_at)
        if elapsed < self.left:
            return

        if self.phase == "night":
            # Tun harakatlarini hisoblash
            # 1. Mafia nishoni: don yoki maf larning eng ko'p ovoz olgan nishoni
            maf_targets: Dict[int, int] = {}
            for p in self.players:
                if p["alive"] and p["role"] in ("don", "maf") and p["u"] in self.night_actions:
                    tgt = self.night_actions[p["u"]]
                    if tgt > 0:
                        maf_targets[tgt] = maf_targets.get(tgt, 0) + 1

            maf_kill_target = None
            if maf_targets:
                maf_kill_target = max(maf_targets.keys(), key=lambda k: maf_targets[k])

            # 2. Shifokor davolashi
            doc_heal = None
            for p in self.players:
                if p["alive"] and p["role"] == "doc" and p["u"] in self.night_actions:
                    doc_heal = self.night_actions[p["u"]]
                    break

            # 3. Komissar otishi
            kom_kill_target = None
            for p in self.players:
                if p["alive"] and p["role"] == "kom" and getattr(self, "kmode", "") == "shoot":
                    kom_kill_target = self.night_actions.get(p["u"])
                    break

            killed_names = []
            if maf_kill_target and maf_kill_target != doc_heal:
                victim = next((p for p in self.players if p["u"] == maf_kill_target), None)
                if victim and victim["alive"]:
                    victim["alive"] = False
                    killed_names.append(victim["n"])

            if kom_kill_target and kom_kill_target != doc_heal and kom_kill_target != maf_kill_target:
                victim2 = next((p for p in self.players if p["u"] == kom_kill_target), None)
                if victim2 and victim2["alive"]:
                    victim2["alive"] = False
                    killed_names.append(victim2["n"])

            self.night_actions.clear()
            self.skips.clear()

            if self._check_game_over():
                return

            self.phase = "day"
            self.left = 45
            self.left_at = time.time()
            self.day += 1
            if killed_names:
                self.add_msg(0, "Tizim", f"☀️ Tong otdi. Kechasi qurbon bo'ldi: {', '.join(killed_names)}")
            else:
                self.add_msg(0, "Tizim", "☀️ Tong otdi. Shifokor barchani saqlab qoldi, kechasi hech kim o'lmadi!")
            self.ver += 1

        elif self.phase == "day":
            self.phase = "vote"
            self.left = 30
            self.left_at = time.time()
            self.votes.clear()
            self.add_msg(0, "Tizim", "🗳 Muhokama tugadi. Hamma ovoz beradi!")
            self.ver += 1

        elif self.phase == "vote":
            # Ovozlar sarhisobi
            tally: Dict[int, int] = {}
            for voter_id, tgt in self.votes.items():
                if tgt and tgt > 0:
                    tally[tgt] = tally.get(tgt, 0) + 1

            cond_user = None
            if tally:
                max_votes = max(tally.values())
                top_candidates = [uid for uid, cnt in tally.items() if cnt == max_votes]
                if len(top_candidates) == 1:
                    cond_user = top_candidates[0]

            self.votes.clear()
            if cond_user:
                victim = next((p for p in self.players if p["u"] == cond_user), None)
                if victim and victim["alive"]:
                    victim["alive"] = False
                    self.cond = cond_user
                    self.add_msg(0, "Tizim", f"⚖️ Shahar sudi qarori bilan {victim['n']} osildi!")
                    if self._check_game_over():
                        return
            else:
                self.cond = None
                self.add_msg(0, "Tizim", "⚖️ Ovozlar teng keldi yoki ko'pchilik betaraf qoldi. Hech kim jazolanmadi.")

            self.phase = "night"
            self.left = 35
            self.left_at = time.time()
            self.night_actions.clear()
            self.skips.clear()
            self.ver += 1

    def to_dict_for_user(self, user_id: int) -> Dict[str, Any]:
        self.step_timer()
        elapsed = int(time.time() - self.left_at)
        rem_left = max(0, self.left - elapsed)

        me_player = next((p for p in self.players if p["u"] == user_id), None)
        my_role = me_player["role"] if me_player else "civ"
        role_info = ROLES.get(my_role, ROLES["civ"])
        is_alive = bool(me_player and me_player.get("alive", True))

        # Rollarni berkitish (sherik mafialar bundan mustasno)
        exposed_players = []
        is_maf_team = my_role in ("don", "maf")
        for p in self.players:
            p_copy = dict(p)
            p_copy["id"] = p.get("id", p["u"])
            p_copy["u"] = p["u"]
            p_copy["host"] = (p["u"] == self.host)
            p_copy["v"] = [voter for voter, target in self.votes.items() if target == p["u"]]
            if self.phase != "end" and p["u"] != user_id:
                if not (is_maf_team and p["role"] in ("don", "maf")):
                    p_copy["role"] = "civ"
            exposed_players.append(p_copy)

        chans = ["all"]
        if is_maf_team:
            chans.append("maf")
        if me_player and not is_alive:
            chans.append("dead")

        # Tun nishonlari
        targets = []
        if self.phase == "night" and is_alive:
            if my_role in ("don", "maf"):
                targets = [p["u"] for p in self.players if p["alive"] and p["role"] not in ("don", "maf")]
            elif my_role == "doc":
                targets = [p["u"] for p in self.players if p["alive"]]
            elif my_role == "kom":
                targets = [p["u"] for p in self.players if p["alive"] and p["u"] != user_id]

        mafv_picks = {}
        if is_maf_team:
            for uid, tgt in self.night_actions.items():
                p_item = next((p for p in self.players if p["u"] == uid), None)
                if p_item and p_item["role"] in ("don", "maf"):
                    mafv_picks[uid] = tgt

        admin_ids = config.admin_ids
        min_players = 3 if (user_id in admin_ids or self.host in admin_ids) else 5

        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "ver": self.ver,
            "phase": self.phase,
            "left": rem_left,
            "day": self.day,
            "me": user_id,
            "host": self.host,
            "in": bool(me_player),
            "alive": is_alive,
            "role": my_role,
            "role_info": role_info,
            "min": min_players,
            "pub": self.pub,
            "group": self.group,
            "players": exposed_players,
            "targets": targets,
            "acted": self.night_actions.get(user_id, 0),
            "kmode": getattr(self, "kmode", "check"),
            "myvote": self.votes.get(user_id, 0),
            "mafv": mafv_picks,
            "skip": len(self.skips),
            "skipped": (user_id in self.skips),
            "cond": self.cond,
            "checks": self.checks if my_role == "kom" else [],
            "ch": chans,
            "chat": self.chat[-60:],
            "mid": self.mid,
            "winner": self.winner,
        }


class MafiaService:
    """Mafia boshqaruv xizmati."""

    def __init__(self):
        self.rooms: Dict[str, MafiaRoom] = {}
        self.user_room_map: Dict[int, str] = {}
        self.group_info = {
            "url": f"https://t.me/{config.CHANNEL_USERNAME.lstrip('@')}",
            "title": "Bauntys Mafia Guruhi"
        }

    def get_room(self, room_id_or_code: str) -> Optional[MafiaRoom]:
        """Xonani ID yoki 4 xonali code bo'yicha olish."""
        clean = str(room_id_or_code).strip()
        if clean in self.rooms:
            return self.rooms[clean]
        for r in self.rooms.values():
            if r.code == clean:
                return r
        return None

    def get_home_data(self, user_id: int, user_name: str = "O'yinchi", is_admin: bool = False) -> Dict[str, Any]:
        """Mafia bosh sahifasi ma'lumotlari."""
        active_rooms = []
        for r in self.rooms.values():
            if r.phase == "lobby":
                active_rooms.append({
                    "id": r.id,
                    "code": r.code,
                    "name": r.name,
                    "players": len(r.players),
                    "max": r.max_players,
                    "state": r.phase
                })

        user_info = {
            "id": user_id,
            "name": user_name,
            "stats": {"games": 3, "wins": 2, "rating": 1200}
        }

        current_room_id = self.user_room_map.get(user_id)
        current_room_data = None
        if current_room_id and current_room_id in self.rooms:
            current_room_data = self.rooms[current_room_id].to_dict_for_user(user_id)

        pub_count = sum(len(r.players) for r in self.rooms.values() if r.pub and r.phase == "lobby")

        return {
            "ok": True,
            "me": user_id,
            "name": user_name,
            "user": user_info,
            "rooms": active_rooms,
            "cur": current_room_data,
            "room": current_room_data,
            "pub": pub_count,
            "grp": self.group_info,
            "admin": is_admin
        }

    def create_room(
        self,
        user_id: int,
        user_name: str,
        room_name: str = "",
        max_players: int = 10,
        pub: bool = False,
        lk: Optional[str] = None,
        c: int = 0
    ) -> Dict[str, Any]:
        """Yangi xona ochish."""
        code = str(random.randint(1000, 9999))
        while any(r.code == code for r in self.rooms.values()):
            code = str(random.randint(1000, 9999))

        room_id = f"m_{code}"
        name = room_name.strip() or f"{user_name} xonasi"
        room = MafiaRoom(
            room_id=room_id,
            name=name,
            host_id=user_id,
            host_name=user_name,
            max_players=max_players,
            code=code,
            pub=pub,
            lk=lk,
            c=c
        )
        self.rooms[room_id] = room
        self.user_room_map[user_id] = room_id
        return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def join_room(self, user_id: int, user_name: str, room_id: str, lk: Optional[str] = None) -> Dict[str, Any]:
        """Xonaga ulanish (code yoki ID orqali)."""
        clean_id = room_id.strip()
        room = self.get_room(clean_id)
        if not room:
            # Agar 4-xonali kod bo'lsa yangi xona yaratish
            return self.create_room(user_id=user_id, user_name=user_name, room_name=f"Xona #{clean_id}", pub=False, lk=lk)

        success = room.add_player(user_id, user_name, lk=lk)
        if not success:
            return {"ok": False, "error": "full"}

        self.user_room_map[user_id] = room.id
        return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def quick_play(self, user_id: int, user_name: str, lk: Optional[str] = None) -> Dict[str, Any]:
        """Tezkor o'yinga ulanish."""
        for room in self.rooms.values():
            if room.pub and room.phase == "lobby" and len(room.players) < room.max_players:
                room.add_player(user_id, user_name, lk=lk)
                self.user_room_map[user_id] = room.id
                return {"ok": True, "room": room.to_dict_for_user(user_id)}

        return self.create_room(
            user_id=user_id,
            user_name=user_name,
            room_name="Tezkor Mafia Xonasi",
            max_players=10,
            pub=True,
            lk=lk
        )

    def leave_room(self, user_id: int) -> Dict[str, Any]:
        """Xonadan chiqish."""
        room_id = self.user_room_map.pop(user_id, None)
        if room_id and room_id in self.rooms:
            self.rooms[room_id].remove_player(user_id)
            if not self.rooms[room_id].players:
                del self.rooms[room_id]
        return {"ok": True}

    def poll_room(self, user_id: int, version: int = -1, last_mid: int = 0) -> Dict[str, Any]:
        """Polling: xona holatini tekshirish."""
        room_id = self.user_room_map.get(user_id)
        if not room_id or room_id not in self.rooms:
            return {"ok": False, "error": "nocode"}

        room = self.rooms[room_id]
        room_dict = room.to_dict_for_user(user_id)
        if version == room.ver and last_mid == room.mid:
            return {"ok": True, "same": True, "left": room_dict["left"]}

        return {"ok": True, "room": room_dict}

    def start_game(self, user_id: int) -> Dict[str, Any]:
        """O'yinni boshlash (faqat host)."""
        room_id = self.user_room_map.get(user_id)
        if not room_id or room_id not in self.rooms:
            return {"ok": False, "error": "nocode"}

        room = self.rooms[room_id]
        admin_ids = config.admin_ids
        is_admin = user_id in admin_ids or room.host in admin_ids
        if room.host != user_id and not is_admin:
            return {"ok": False, "error": "host"}

        min_req = 3 if is_admin else 5
        if len(room.players) < min_req:
            return {"ok": False, "error": "few"}

        room.start_game()
        return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def act(self, user_id: int, target_id: int, mode: str = "check") -> Dict[str, Any]:
        """Tun harakati (Mafia o'qi, Shifokor davolashi, Komissar tekshiruvi)."""
        room_id = self.user_room_map.get(user_id)
        if not room_id or room_id not in self.rooms:
            return {"ok": False, "error": "nocode"}

        room = self.rooms[room_id]
        success = room.act(user_id, target_id, mode=mode)
        if not success:
            return {"ok": False, "error": "target"}
        return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def vote(self, user_id: int, target_id: int) -> Dict[str, Any]:
        """Ovoz berish."""
        room_id = self.user_room_map.get(user_id)
        if not room_id or room_id not in self.rooms:
            return {"ok": False, "error": "nocode"}

        room = self.rooms[room_id]
        success = room.vote(user_id, target_id)
        if not success:
            return {"ok": False, "error": "target"}
        return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def skip(self, user_id: int) -> Dict[str, Any]:
        """Kunduzgi muhokamani ovoz berishga o'tkazish."""
        room_id = self.user_room_map.get(user_id)
        if not room_id or room_id not in self.rooms:
            return {"ok": False, "error": "nocode"}

        room = self.rooms[room_id]
        room.skip(user_id)
        return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def set_look(self, user_id: int, lk: Optional[str] = None, c: int = 0) -> Dict[str, Any]:
        """Qahramon ko'rinishi va rangini o'zgartirish."""
        room_id = self.user_room_map.get(user_id)
        if not room_id or room_id not in self.rooms:
            return {"ok": False, "error": "nocode"}

        room = self.rooms[room_id]
        room.set_look(user_id, lk, c)
        return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def send_chat_message(
        self,
        user_id: int,
        user_name: str,
        text: str,
        emo: Optional[str] = None,
        ch: str = "all"
    ) -> Dict[str, Any]:
        """Chatga xabar yoki emoji yuborish."""
        room_id = self.user_room_map.get(user_id)
        if not room_id or room_id not in self.rooms:
            return {"ok": False, "error": "nocode"}

        room = self.rooms[room_id]
        clean_text = text.strip() if text else ""
        room.add_msg(user_id=user_id, name=user_name, text=clean_text, emo=emo, ch=ch)
        return {"ok": True, "room": room.to_dict_for_user(user_id)}

    def set_group_info(self, url: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Mafia guruhi havolasini yangilash."""
        if url:
            self.group_info = {
                "url": url.strip(),
                "title": title.strip() if title else "Bauntys Mafia Guruhi"
            }
        else:
            self.group_info = None
        return {"ok": True, "grp": self.group_info}


mafia_service = MafiaService()
