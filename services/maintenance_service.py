"""
services/maintenance_service.py
Bot va Web App uchun Profilaktika va Yangilanish (Maintenance Mode) xizmati.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from config import BASE_DIR

logger = logging.getLogger(__name__)

MAINTENANCE_FILE = BASE_DIR / "data" / "maintenance.json"

MAINTENANCE_TEMPLATES: List[str] = [
    "🛠️ Bo'limda texnik yangilanish olib borilmoqda. Tez orada qaytamiz!",
    "🚀 Yangi zo'r funksiyalar qo'shilmoqda, bir oz kuting!",
    "⚡ Tezlik va sifatni oshirish bo'yicha profilaktika ketmoqda.",
    "✨ Server optimallashtirilmoqda — 15 daqiqadan so'ng ishga tushadi.",
    "🎯 Yangi sara kontentlar yuklanmoqda... Marhamat, kuting!",
]

PAGE_EMOJIS: Dict[str, str] = {
    "kino": "🎬",
    "music": "🎧",
    "books": "📚",
    "games": "🧸",
    "story": "👻",
    "docs": "📄",
    "quiz": "🧠",
    "food": "🍲",
    "fx": "💱",
    "tv": "📺",
}

PAGE_NAMES: Dict[str, str] = {
    "kino": "Kinolar",
    "music": "Musiqa",
    "books": "Kitoblar",
    "games": "O'yinlar",
    "story": "Story",
    "docs": "Hujjatlar",
    "quiz": "Viktorina",
    "food": "Taomlar",
    "fx": "Kurs",
    "tv": "TV",
}

DEFAULT_STATE: Dict[str, Any] = {
    "global": {
        "enabled": False,
        "active": False,
        "message_idx": 0,
        "message": MAINTENANCE_TEMPLATES[0],
    },
    "pages": {
        page_id: {
            "enabled": False,
            "active": False,
            "message_idx": 0,
            "message": MAINTENANCE_TEMPLATES[0],
        }
        for page_id in PAGE_EMOJIS
    },
}

_CACHE: Optional[Dict[str, Any]] = None


class MaintenanceService:
    """Profilaktika holatini boshqarish xizmati."""

    @classmethod
    def get_state(cls) -> Dict[str, Any]:
        """Holatni yuklash va keshlashtirish."""
        global _CACHE
        if _CACHE is not None:
            return _CACHE

        if MAINTENANCE_FILE.exists():
            try:
                with open(MAINTENANCE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # To'liq kalitlar mavjudligini ta'minlash
                    if "global" not in data:
                        data["global"] = dict(DEFAULT_STATE["global"])
                    is_g = bool(data["global"].get("enabled", False) or data["global"].get("active", False))
                    data["global"]["enabled"] = is_g
                    data["global"]["active"] = is_g
                    if "pages" not in data:
                        data["pages"] = dict(DEFAULT_STATE["pages"])
                    for p in PAGE_EMOJIS:
                        if p not in data["pages"]:
                            data["pages"][p] = dict(DEFAULT_STATE["pages"][p])
                        is_p = bool(data["pages"][p].get("enabled", False) or data["pages"][p].get("active", False))
                        data["pages"][p]["enabled"] = is_p
                        data["pages"][p]["active"] = is_p
                    _CACHE = data
                    return _CACHE
            except Exception as e:
                logger.error(f"maintenance.json o'qishda xatolik: {e}")

        _CACHE = json.loads(json.dumps(DEFAULT_STATE))
        cls.save_state(_CACHE)
        return _CACHE

    @classmethod
    def save_state(cls, state: Dict[str, Any]) -> None:
        """Holatni faylga saqlash."""
        global _CACHE
        _CACHE = state
        try:
            MAINTENANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MAINTENANCE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"maintenance.json saqlashda xatolik: {e}")
        try:
            from services.web_server import clear_catalog_cache
            clear_catalog_cache()
        except Exception:
            pass

    @classmethod
    def is_global_maintenance(cls) -> bool:
        """Butun tizim profilaktikada ekanligini tekshirish."""
        state = cls.get_state()
        g = state.get("global", {})
        return bool(g.get("enabled", False) or g.get("active", False))

    @classmethod
    def get_global_message(cls) -> str:
        """Global profilaktika xabarini olish."""
        state = cls.get_state()
        return state.get("global", {}).get("message") or MAINTENANCE_TEMPLATES[0]

    @classmethod
    def set_global_maintenance(cls, enabled: bool, message_idx: int = 0, custom_message: Optional[str] = None) -> None:
        """Global profilaktika holatini o'zgartirish."""
        state = cls.get_state()
        msg = custom_message or (
            MAINTENANCE_TEMPLATES[message_idx]
            if 0 <= message_idx < len(MAINTENANCE_TEMPLATES)
            else MAINTENANCE_TEMPLATES[0]
        )
        state["global"]["enabled"] = enabled
        state["global"]["active"] = enabled
        state["global"]["message_idx"] = message_idx
        state["global"]["message"] = msg
        cls.save_state(state)

    @classmethod
    def is_page_maintenance(cls, page_id: str) -> bool:
        """Alohida Web App sahifasi profilaktikada ekanligini tekshirish."""
        state = cls.get_state()
        g = state.get("global", {})
        if g.get("enabled", False) or g.get("active", False):
            return True
        p = state.get("pages", {}).get(page_id, {})
        return bool(p.get("enabled", False) or p.get("active", False))

    @classmethod
    def get_page_message(cls, page_id: str) -> str:
        """Sahifa profilaktika xabarini olish."""
        state = cls.get_state()
        g = state.get("global", {})
        if g.get("enabled", False) or g.get("active", False):
            return state.get("global", {}).get("message") or MAINTENANCE_TEMPLATES[0]
        page_info = state.get("pages", {}).get(page_id, {})
        return page_info.get("message") or MAINTENANCE_TEMPLATES[0]

    @classmethod
    def set_page_maintenance(
        cls, page_id: str, enabled: bool, message_idx: int = 0, custom_message: Optional[str] = None
    ) -> None:
        """Alohida sahifa profilaktikasini sozlash."""
        state = cls.get_state()
        if page_id not in state["pages"]:
            state["pages"][page_id] = dict(DEFAULT_STATE["pages"].get(page_id, {
                "enabled": False,
                "active": False,
                "message_idx": 0,
                "message": MAINTENANCE_TEMPLATES[0],
            }))
        msg = custom_message or (
            MAINTENANCE_TEMPLATES[message_idx]
            if 0 <= message_idx < len(MAINTENANCE_TEMPLATES)
            else MAINTENANCE_TEMPLATES[0]
        )
        state["pages"][page_id]["enabled"] = enabled
        state["pages"][page_id]["active"] = enabled
        state["pages"][page_id]["message_idx"] = message_idx
        state["pages"][page_id]["message"] = msg
        cls.save_state(state)


maintenance_service = MaintenanceService()
