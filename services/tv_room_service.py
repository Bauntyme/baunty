"""
Tv Xona (TV Watch Party Room) Service - Bauntys
Do'stlar bilan birgalikda 4K / HD jonli telekanallarni tomosha qilish,
kanalni sinxronlashtirish, matnli chat, tezkor reaksiyalar va
shovqinsiz WebRTC audio/ovozli chat xonalari.
100% Bauntys brendi.
"""
from __future__ import annotations

import time
import random
import logging
from typing import Dict, Any, Optional, List, Set
from services.tv_data import CHANNELS_LIST, TV_CATEGORIES

logger = logging.getLogger(__name__)

# Standart boshlang'ich kanal: Zo'r TV HD (4K UHD / 1080p 60fps)
DEFAULT_CHANNEL_ID = 4


def _find_channel(channel_id: Any) -> Dict[str, Any]:
    """CHANNELS_LIST ichidan kanalni topish yoki standart Zo'r TV ni qaytarish."""
    if channel_id is not None:
        ch_str = str(channel_id).strip().lower()
        for ch in CHANNELS_LIST:
            id_val = str(ch.get("id") if ch.get("id") is not None else ch.get("i", "")).strip().lower()
            name_val = str(ch.get("name") or ch.get("n", "")).strip().lower()
            if id_val == ch_str or name_val == ch_str:
                backups = [item[1] for item in ch.get("u", []) if len(item) > 1 and item[1]]
                return {
                    "id": ch.get("id") or ch.get("i"),
                    "name": ch.get("name") or ch.get("n", "TV"),
                    "logo": ch.get("logo", "📺"),
                    "l": ch.get("l", ""),
                    "desc": ch.get("desc", ""),
                    "stream": ch.get("stream", ""),
                    "backups": backups,
                    "q": ch.get("q", "4K UHD / 1080p 60fps"),
                    "category": ch.get("category") or ch.get("k", "xususiy"),
                }

    # Standart kanalni qidirish (Zo'r TV id=4)
    for ch in CHANNELS_LIST:
        if ch.get("id") == DEFAULT_CHANNEL_ID or ch.get("i") == DEFAULT_CHANNEL_ID:
            backups = [item[1] for item in ch.get("u", []) if len(item) > 1 and item[1]]
            return {
                "id": ch.get("id") or ch.get("i"),
                "name": ch.get("name") or ch.get("n", "Zo'r TV"),
                "logo": ch.get("logo", "⚡"),
                "l": ch.get("l", "https://i.imgur.com/NuzyhVM.png"),
                "desc": ch.get("desc", "Ko'ngilochar loyihalar va premyeralar (4K UHD)"),
                "stream": ch.get("stream", "https://stream3.cinerama.uz/1016/tracks-v1a1/mono.ts.m3u8"),
                "backups": backups,
                "q": ch.get("q", "4K UHD / 1080p 60fps"),
                "category": ch.get("category") or ch.get("k", "xususiy"),
            }

    if CHANNELS_LIST:
        ch = CHANNELS_LIST[0]
        backups = [item[1] for item in ch.get("u", []) if len(item) > 1 and item[1]]
        return {
            "id": ch.get("id") or ch.get("i", 4),
            "name": ch.get("name") or ch.get("n", "Zo'r TV"),
            "logo": ch.get("logo", "⚡"),
            "l": ch.get("l", "https://i.imgur.com/NuzyhVM.png"),
            "desc": ch.get("desc", ""),
            "stream": ch.get("stream", "https://stream3.cinerama.uz/1016/tracks-v1a1/mono.ts.m3u8"),
            "backups": backups,
            "q": ch.get("q", "4K UHD"),
            "category": ch.get("category", "xususiy"),
        }

    return {
        "id": 4,
        "name": "Zo'r TV HD",
        "logo": "⚡",
        "l": "https://i.imgur.com/NuzyhVM.png",
        "desc": "Ko'ngilochar loyihalar va premyeralar (4K UHD)",
        "stream": "https://stream3.cinerama.uz/1016/tracks-v1a1/mono.ts.m3u8",
        "backups": ["https://stream3.cinerama.uz/1016/playlist.m3u8"],
        "q": "4K UHD / 1080p 60fps",
        "category": "xususiy",
    }


def normalize_room_code(code: str) -> str:
    """Xona kodini tozalash va standart 'tv_1234' formatiga keltirish."""
    c = str(code or "").strip().lower()
    c = c.replace("tvroom_", "").replace("tvxona_", "").replace("tv_", "")
    # Harflar va raqamlarni saqlash
    cleaned = "".join(ch for ch in c if ch.isalnum())
    if not cleaned or cleaned in ("tvroom", "tvxona", "main"):
        cleaned = "main"
    return f"tv_{cleaned}"


class TvRoom:
    """Bitta TV tomosha partiyasi (Watch Party) xonasi holati."""

    def __init__(
        self,
        room_id: str,
        name: str,
        host_id: int,
        host_name: str,
        channel_id: Optional[int] = None,
        username: str = "",
        photo_url: str = "",
        pub: bool = True,
        max_viewers: int = 50,
    ):
        self.id = room_id  # Masalan: tv_1234
        self.code = room_id.replace("tv_", "")
        self.name = name or f"{host_name}ning TV Xonasi"
        self.host_id = host_id
        self.host_name = host_name
        self.pub = pub
        self.max_viewers = max(2, min(200, max_viewers))
        self.created_at = time.time()
        self.last_active = time.time()
        self.version = 1

        # Joriy telekanal
        self.channel = _find_channel(channel_id)

        # Qatnashuvchilar: user_id -> dict
        self.participants: Dict[int, Dict[str, Any]] = {}
        # Chat xabarlari
        self.chat: List[Dict[str, Any]] = []
        self._next_msg_id = 1
        # WebRTC & Ovozli signalizatsiya xabarlari
        self.signals: List[Dict[str, Any]] = []
        self._last_signal_ts: float = 0.0

        # Hostni birinchi qatnashuvchi sifatida qo'shish
        self.add_participant(
            user_id=host_id,
            name=host_name,
            username=username,
            photo_url=photo_url,
            role="host",
        )

    def add_participant(
        self,
        user_id: int,
        name: str,
        username: str = "",
        photo_url: str = "",
        role: str = "viewer",
    ) -> Dict[str, Any]:
        """Xonaga yangi tomoshabin yoki hostni qo'shish."""
        self.last_active = time.time()
        is_host = (user_id == self.host_id) or (role == "host")

        if user_id in self.participants:
            p = self.participants[user_id]
            p["name"] = name or p["name"]
            p["username"] = username or p.get("username", "")
            if photo_url:
                p["photo_url"] = photo_url
            p["last_seen"] = time.time()
            if is_host:
                p["role"] = "host"
            return p

        # Yangi qatnashuvchi
        actual_role = "host" if is_host else "viewer"
        p_data = {
            "user_id": user_id,
            "id": user_id,
            "name": name or f"Tomoshabin {len(self.participants) + 1}",
            "username": username or "",
            "photo_url": photo_url or "",
            "role": actual_role,
            "mic_active": False,
            "speaking": False,
            "joined_at": time.time(),
            "last_seen": time.time(),
        }
        self.participants[user_id] = p_data
        self.version += 1

        # Tizim xabari
        self.add_chat_message(
            user_id=0,
            name="Tizim",
            text=f"👋 {p_data['name']} xonaga qo'shildi",
            system=True,
        )
        return p_data

    def remove_participant(self, user_id: int) -> bool:
        """Foydalanuvchini xonadan chiqarish."""
        self.last_active = time.time()
        p = self.participants.pop(user_id, None)
        if not p:
            return False

        self.version += 1
        self.add_chat_message(
            user_id=0,
            name="Tizim",
            text=f"🚪 {p['name']} xonani tark etdi",
            system=True,
        )

        # Agar xonadan host chiqib ketgan bo'lsa, qolgan birinchi odamni yangi host qilish
        if user_id == self.host_id and self.participants:
            next_host_id = next(iter(self.participants))
            self.host_id = next_host_id
            self.participants[next_host_id]["role"] = "host"
            self.host_name = self.participants[next_host_id]["name"]
            self.add_chat_message(
                user_id=0,
                name="Tizim",
                text=f"👑 Yangi xona boshqaruvchisi: {self.host_name}",
                system=True,
            )

        return True

    def change_channel(self, user_id: int, channel_id: Any) -> Tuple[bool, str]:
        """Kanalni o'zgartirish va hamma uchun sinxronlash."""
        self.last_active = time.time()
        # Faqat host yoki ommaviy/asosiy xonada (tv_main) istalgan ishtirokchiga ruxsat beriladi
        is_allowed = (
            user_id == self.host_id
            or self.id == "tv_main"
            or self.host_id in (7777777, 0)
        )
        if not is_allowed:
            return False, "Faqat xona boshqaruvchisi kanalni o'zgartirishi mumkin!"

        new_ch = _find_channel(channel_id)
        if not new_ch:
            return False, "Telekanal topilmadi!"

        self.channel = new_ch
        self.version += 1

        self.add_chat_message(
            user_id=0,
            name="Tizim",
            text=f"📺 Telekanal o'zgartirildi: {new_ch['name']} ({new_ch.get('q', '4K UHD')})",
            system=True,
        )
        return True, "Kanal yangilandi"

    def set_mic_state(self, user_id: int, active: bool, speaking: Optional[bool] = None) -> bool:
        """Mikrofon faolligi va gapirish holatini yangilash."""
        if user_id not in self.participants:
            return False
        p = self.participants[user_id]
        changed = (p["mic_active"] != active)
        p["mic_active"] = active
        if speaking is not None:
            p["speaking"] = speaking
        p["last_seen"] = time.time()
        if changed:
            self.version += 1
        return True

    def add_chat_message(
        self,
        user_id: int,
        name: str,
        text: str,
        reaction: Optional[str] = None,
        username: str = "",
        photo_url: str = "",
        system: bool = False,
    ) -> Dict[str, Any]:
        """Xonaga yangi chat xabari yoki reaksiya qo'shish."""
        self.last_active = time.time()
        msg_id = self._next_msg_id
        self._next_msg_id += 1

        msg = {
            "id": msg_id,
            "user_id": user_id,
            "name": name,
            "username": username,
            "photo_url": photo_url,
            "text": text.strip() if text else "",
            "reaction": reaction or "",
            "system": system,
            "ts": time.time(),
        }
        self.chat.append(msg)
        # Oxirgi 100 ta xabarni saqlash
        if len(self.chat) > 100:
            self.chat = self.chat[-100:]
        self.version += 1
        return msg

    def add_signal(self, from_uid: int, to_uid: Any, signal_type: str, data: Any) -> Dict[str, Any]:
        """WebRTC audio signalini qo'shish (offer, answer, candidate, speaking)."""
        now = time.time()
        if now <= self._last_signal_ts:
            now = self._last_signal_ts + 0.0001
        self._last_signal_ts = now
        self.last_active = now
        sig = {
            "from": from_uid,
            "to": to_uid,  # user_id yoki "all"
            "type": signal_type,
            "data": data,
            "ts": now,
        }
        self.signals.append(sig)
        # 45 soniyadan eski signallarni tozalash
        cutoff = now - 45
        self.signals = [s for s in self.signals if s["ts"] >= cutoff]
        return sig

    def get_signals_for_user(self, user_id: int, since_ts: float = 0.0) -> List[Dict[str, Any]]:
        """Foydalanuvchiga tegishli signallarni olish."""
        u_str = str(user_id)
        return [
            s for s in self.signals
            if s["ts"] > since_ts and str(s.get("from")) != u_str and (s.get("to") == "all" or str(s.get("to")) == u_str)
        ]

    def to_dict(self, current_user_id: Optional[int] = None) -> Dict[str, Any]:
        """Xona holatini frontend uchun to'liq serializatsiya qilish."""
        participants_list = list(self.participants.values())
        # Sort: Host first, then active mics, then name
        participants_list.sort(key=lambda p: (0 if p["role"] == "host" else 1, 0 if p.get("mic_active") else 1, p["name"]))

        is_me_host = bool(current_user_id and current_user_id == self.host_id)

        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "host_id": self.host_id,
            "host_name": self.host_name,
            "is_host": is_me_host,
            "pub": self.pub,
            "channel": self.channel,
            "participants": participants_list,
            "count": len(participants_list),
            "max": self.max_viewers,
            "chat": self.chat[-50:],
            "version": self.version,
            "created_at": self.created_at,
            "audio_constraints": {
                "echoCancellation": True,
                "noiseSuppression": True,
                "autoGainControl": True,
            },
        }


class TvRoomService:
    """TV Watch Party Xonalarini boshqarish servisi."""

    def __init__(self):
        self._rooms: Dict[str, TvRoom] = {}
        # Foydalanuvchi qaysi xonada: user_id -> room_id
        self._user_room_map: Dict[int, str] = {}
        self._seed_default_rooms()

    def _seed_default_rooms(self) -> None:
        """Avtomatik 1 ta ommaviy standart Bauntys TV Lounge xonasini yaratish."""
        default_code = "tv_main"
        room = TvRoom(
            room_id=default_code,
            name="🇺🇿 Bauntys Rasmiy TV Xonasi (Zo'r TV 4K)",
            host_id=7777777,
            host_name="Bauntys TV",
            channel_id=DEFAULT_CHANNEL_ID,
            username="BauntyCinemabot",
            photo_url="https://i.imgur.com/NuzyhVM.png",
            pub=True,
        )
        self._rooms[default_code] = room

    def create_room(
        self,
        user_id: int,
        user_name: str,
        room_name: str = "",
        channel_id: Optional[int] = None,
        username: str = "",
        photo_url: str = "",
        custom_code: Optional[str] = None,
        pub: bool = True,
    ) -> Dict[str, Any]:
        """Yangi TV Xona ochish."""
        if custom_code:
            code = normalize_room_code(custom_code)
        else:
            # 4 xonali noyob raqam
            rand_digits = random.randint(1000, 9999)
            code = f"tv_{rand_digits}"
            attempts = 0
            while code in self._rooms and attempts < 20:
                rand_digits = random.randint(1000, 9999)
                code = f"tv_{rand_digits}"
                attempts += 1

        # Agar foydalanuvchi oldin boshqa xonada bo'lsa, undan chiqarish
        self.leave_room(user_id)

        room = TvRoom(
            room_id=code,
            name=room_name.strip() if room_name else f"{user_name}ning TV Xonasi",
            host_id=user_id,
            host_name=user_name,
            channel_id=channel_id,
            username=username,
            photo_url=photo_url,
            pub=pub,
        )
        self._rooms[code] = room
        self._user_room_map[user_id] = code

        logger.info(f"Yangi TV xona ochildi: {code} (Host: {user_name}, ID: {user_id})")
        return {"ok": True, "room": room.to_dict(current_user_id=user_id)}

    def join_room(
        self,
        room_code: str,
        user_id: int,
        user_name: str,
        username: str = "",
        photo_url: str = "",
    ) -> Dict[str, Any]:
        """Xonaga qo'shilish."""
        normalized = normalize_room_code(room_code)
        room = self._rooms.get(normalized)
        if not room:
            # Balki boshqa prefiksiz qidirilayotgandir
            for r_id, r_obj in self._rooms.items():
                if r_obj.code == room_code or r_id == room_code:
                    room = r_obj
                    normalized = r_id
                    break

        if not room:
            return {"ok": False, "error": "room_not_found", "message": "Bunday TV Xona topilmadi!"}

        # Agar oldin boshqa xonada bo'lsa, undan chiqish (agar o'sha xona bo'lmasa)
        cur_room = self._user_room_map.get(user_id)
        if cur_room and cur_room != normalized:
            self.leave_room(user_id)

        room.add_participant(
            user_id=user_id,
            name=user_name,
            username=username,
            photo_url=photo_url,
            role="viewer" if user_id != room.host_id else "host",
        )
        self._user_room_map[user_id] = normalized

        return {"ok": True, "room": room.to_dict(current_user_id=user_id)}

    def leave_room(self, user_id: int, room_code: Optional[str] = None) -> Dict[str, Any]:
        """Xonadan chiqish."""
        target_id = None
        if room_code:
            target_id = normalize_room_code(room_code)
        elif user_id in self._user_room_map:
            target_id = self._user_room_map[user_id]

        if not target_id or target_id not in self._rooms:
            self._user_room_map.pop(user_id, None)
            return {"ok": True, "message": "Xonada emassiz"}

        room = self._rooms[target_id]
        room.remove_participant(user_id)
        self._user_room_map.pop(user_id, None)

        # Agar xona bo'sh qolsa va asosiy tv_main bo'lmasa, uni o'chirish
        if not room.participants and target_id != "tv_main":
            self._rooms.pop(target_id, None)
            logger.info(f"Bo'sh TV xona o'chirildi: {target_id}")

        return {"ok": True, "message": "Xonadan chiqdingiz"}

    def get_room_state(self, room_code: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Xonaning joriy holatini olish."""
        normalized = normalize_room_code(room_code)
        room = self._rooms.get(normalized)
        if not room:
            for r_id, r_obj in self._rooms.items():
                if r_obj.code == room_code or r_id == room_code:
                    room = r_obj
                    break

        if not room:
            return {"ok": False, "error": "room_not_found", "message": "Xona topilmadi"}

        if user_id and user_id in room.participants:
            room.participants[user_id]["last_seen"] = time.time()

        return {"ok": True, "room": room.to_dict(current_user_id=user_id)}

    def change_channel(self, room_code: str, user_id: int, channel_id: int) -> Dict[str, Any]:
        """Xona kanalini o'zgartirish."""
        normalized = normalize_room_code(room_code)
        room = self._rooms.get(normalized)
        if not room:
            return {"ok": False, "error": "room_not_found"}

        ok, msg = room.change_channel(user_id, channel_id)
        if not ok:
            return {"ok": False, "error": "permission_denied", "message": msg}

        return {"ok": True, "channel": room.channel, "room": room.to_dict(current_user_id=user_id)}

    def send_chat(
        self,
        room_code: str,
        user_id: int,
        user_name: str,
        text: str,
        reaction: Optional[str] = None,
        username: str = "",
        photo_url: str = "",
    ) -> Dict[str, Any]:
        """Chatga xabar yuborish."""
        normalized = normalize_room_code(room_code)
        room = self._rooms.get(normalized)
        if not room:
            return {"ok": False, "error": "room_not_found"}

        msg = room.add_chat_message(
            user_id=user_id,
            name=user_name,
            text=text,
            reaction=reaction,
            username=username,
            photo_url=photo_url,
        )
        return {"ok": True, "message": msg, "version": room.version}

    def send_signal(
        self,
        room_code: str,
        from_uid: int,
        to_uid: Any,
        signal_type: str,
        data: Any,
    ) -> Dict[str, Any]:
        """WebRTC / Ovoz signali yuborish."""
        normalized = normalize_room_code(room_code)
        room = self._rooms.get(normalized)
        if not room:
            return {"ok": False, "error": "room_not_found"}

        if signal_type in ("mic_active", "mic_state"):
            is_active = bool(data.get("active", False)) if isinstance(data, dict) else bool(data)
            speaking = bool(data.get("speaking", False)) if isinstance(data, dict) else None
            room.set_mic_state(from_uid, is_active, speaking)

        sig = room.add_signal(from_uid, to_uid, signal_type, data)
        return {"ok": True, "signal": sig}

    def get_signals(
        self,
        room_code: str,
        user_id: int,
        since_ts: float = 0.0,
    ) -> Dict[str, Any]:
        """Foydalanuvchiga yuborilgan signallarni olish."""
        normalized = normalize_room_code(room_code)
        room = self._rooms.get(normalized)
        if not room:
            return {"ok": False, "error": "room_not_found", "signals": []}

        signals = room.get_signals_for_user(user_id, since_ts)
        return {"ok": True, "signals": signals}

    def list_public_rooms(self) -> List[Dict[str, Any]]:
        """Barcha ommaviy faol TV xonalar ro'yxati."""
        out = []
        for r in self._rooms.values():
            if r.pub:
                out.append({
                    "id": r.id,
                    "code": r.code,
                    "name": r.name,
                    "host_name": r.host_name,
                    "channel_name": r.channel.get("name", "TV"),
                    "channel_logo": r.channel.get("logo", "📺"),
                    "channel_q": r.channel.get("q", "4K UHD"),
                    "viewers_count": len(r.participants),
                    "created_at": r.created_at,
                })
        # Qatnashuvchilar soni bo'yicha saralash
        out.sort(key=lambda x: x["viewers_count"], reverse=True)
        return out

    def get_channels_list(self) -> List[Dict[str, Any]]:
        """Xonalar uchun mavjud barcha telekanallar ro'yxati."""
        curated = []
        for ch in CHANNELS_LIST:
            curated.append({
                "id": ch.get("id") or ch.get("i"),
                "name": ch.get("name") or ch.get("n", "TV"),
                "desc": ch.get("desc", ""),
                "logo": ch.get("logo", "📺"),
                "l": ch.get("l", ""),
                "stream": ch.get("stream", ""),
                "q": ch.get("q", "4K UHD / 1080p 60fps"),
                "category": ch.get("category") or ch.get("k", "milliy"),
            })
        return curated


# Global servis nusxasi
tv_room_service = TvRoomService()
