"""
Yetkazish (Deliv) Backend Xizmati - Bauntys (@BauntyCinemabot)
Mahalliy hamkor do'konlar, kuryer buyurtmasi yaratish, BNT-XXXX kuzatuv kodi,
jonli bosqichlar (Qabul qilindi -> Tayyorlanmoqda -> Yo'lda -> Yetkazildi) va JSON saqlash.
"""
import os
import json
import time
import random
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

_DELIV_LOCK = threading.RLock()
_DELIV_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "deliv_state.json",
)

DELIVERY_STEPS = [
    {"key": "accepted", "title": "Qabul qilindi", "ic": "📥", "desc": "Buyurtmangiz tizimga kiritildi va operatorga uzatildi."},
    {"key": "preparing", "title": "Tayyorlanmoqda", "ic": "📦", "desc": "Hamkor do'konda mahsulotlar yig'ilmoqda."},
    {"key": "on_the_way", "title": "Yo'lda", "ic": "🛵", "desc": "Kuryer buyurtmani olib manzilingiz tomon yo'lga chiqdi."},
    {"key": "delivered", "title": "Yetkazildi", "ic": "✅", "desc": "Buyurtma muvaffaqiyatli topshirildi."},
]

DELIVERY_CATEGORIES = [
    {"id": "all", "name": "Barchasi", "ic": "✨"},
    {"id": "taom", "name": "Taomlar", "ic": "🍽"},
    {"id": "bozor", "name": "Oziq-ovqat", "ic": "🛒"},
    {"id": "dorixona", "name": "Dorixona", "ic": "💊"},
    {"id": "texnika", "name": "Texnika", "ic": "📱"},
    {"id": "kitob", "name": "Kitob va sovg'a", "ic": "🎁"},
    {"id": "kuryer", "name": "Kuryer pochta", "ic": "📮"},
]

PARTNER_STORES: List[Dict[str, Any]] = [
    {
        "id": "baunty_milliy",
        "name": "Choyxona №1 · Milliy Taomlar",
        "cat": "taom",
        "eta": "25–35 daq",
        "fee": 12000,
        "rating": 4.9,
        "addr": "Chilonzor tumani, 9-kvartal",
        "items": [
            {"id": "bm_1", "name": "Toshkent oshi (1 porsiya)", "price": 42000, "ic": "🍛"},
            {"id": "bm_2", "name": "Qo'y qiyma shashlik (2 dona)", "price": 38000, "ic": "🍢"},
            {"id": "bm_3", "name": "Tandir somsa go'shtli (3 dona)", "price": 36000, "ic": "🥐"},
            {"id": "bm_4", "name": "Achichuk salati + choy", "price": 18000, "ic": "🍅"},
        ],
    },
    {
        "id": "baunty_pizza",
        "name": "Baunty Burger & Pizza",
        "cat": "taom",
        "eta": "20–30 daq",
        "fee": 10000,
        "rating": 4.8,
        "addr": "Amir Temur shoh ko'chasi, 45",
        "items": [
            {"id": "bp_1", "name": "Pepperoni Pizza 32cm", "price": 78000, "ic": "🍕"},
            {"id": "bp_2", "name": "Double Beef Burger + Fri", "price": 54000, "ic": "🍔"},
            {"id": "bp_3", "name": "Tovuqli Lavash + Cola 0.5", "price": 46000, "ic": "🌯"},
        ],
    },
    {
        "id": "yashil_bozor",
        "name": "Yashil Bozor · Fresh Market",
        "cat": "bozor",
        "eta": "30–45 daq",
        "fee": 15000,
        "rating": 4.9,
        "addr": "Yunusobod, Markaz-4",
        "items": [
            {"id": "yb_1", "name": "Haftalik sabzavot savati (5 kg)", "price": 65000, "ic": "🥬"},
            {"id": "yb_2", "name": "Fermer sut mahsulotlari to'plami", "price": 48000, "ic": "🥛"},
            {"id": "yb_3", "name": "Toshkent non va patir to'plami (4 dona)", "price": 24000, "ic": "🫓"},
        ],
    },
    {
        "id": "shifo_24",
        "name": "Shifo 24/7 Dorixonasi",
        "cat": "dorixona",
        "eta": "15–25 daq",
        "fee": 8000,
        "rating": 4.9,
        "addr": "Shayxontohur, Navoiy ko'chasi, 18",
        "items": [
            {"id": "sd_1", "name": "Uy tibbiyot qutichasi to'plami", "price": 92000, "ic": "🩹"},
            {"id": "sd_2", "name": "Vitamin C + D3 immunitet majmuasi", "price": 68000, "ic": "💊"},
            {"id": "sd_3", "name": "Raqamli termometr va antiseptik", "price": 55000, "ic": "🌡"},
        ],
    },
    {
        "id": "tech_hub",
        "name": "Baunty Gadget & Aksessuar",
        "cat": "texnika",
        "eta": "35–50 daq",
        "fee": 18000,
        "rating": 4.8,
        "addr": "Malika savdo majmuasi, B-12",
        "items": [
            {"id": "th_1", "name": "Tezkor USB-C 65W zaryadlovchi", "price": 185000, "ic": "🔌"},
            {"id": "th_2", "name": "Simsiz quloqchin TWS Pro", "price": 240000, "ic": "🎧"},
            {"id": "th_3", "name": "Powerbank 20000 mAh", "price": 290000, "ic": "🔋"},
        ],
    },
    {
        "id": "kitob_olam",
        "name": "Baunty Kitob va Sovg'alar",
        "cat": "kitob",
        "eta": "40–60 daq",
        "fee": 12000,
        "rating": 5.0,
        "addr": "Mustaqillik maydoni, 7",
        "items": [
            {"id": "ko_1", "name": "Abdulla Qodiriy — O'tkan kunlar (Hadya nashri)", "price": 75000, "ic": "📘"},
            {"id": "ko_2", "name": "Sovg'abop bloknot va metall ruchka", "price": 62000, "ic": "🖋"},
        ],
    },
]

COURIERS_POOL = [
    {"name": "Sardorbek T.", "phone": "+998 90 342-18-09", "vehicle": "Skuter"},
    {"name": "Jasur M.", "phone": "+998 93 511-40-22", "vehicle": "Elektrovelosiped"},
    {"name": "Bobur R.", "phone": "+998 99 714-63-15", "vehicle": "Matiz Express"},
    {"name": "Azizbek K.", "phone": "+998 97 228-91-04", "vehicle": "Damas Kuryer"},
]


class DelivService:
    """Yetkazish va kuryer kuzatuvi xizmati (JSON saqlash bilan)."""

    def _load_state(self) -> Dict[str, Any]:
        with _DELIV_LOCK:
            if not os.path.exists(_DELIV_STATE_PATH):
                return {"orders": []}
            try:
                with open(_DELIV_STATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("orders"), list):
                    return data
            except Exception as e:
                logger.warning(f"Deliv holatini yuklashda xatolik: {e}")
            return {"orders": []}

    def _save_state(self, data: Dict[str, Any]) -> None:
        with _DELIV_LOCK:
            os.makedirs(os.path.dirname(_DELIV_STATE_PATH), exist_ok=True)
            tmp = f"{_DELIV_STATE_PATH}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _DELIV_STATE_PATH)

    def _generate_tracking_code(self, existing_codes: set) -> str:
        for _ in range(50):
            code = f"BNT-{random.randint(1000, 9999)}"
            if code not in existing_codes:
                return code
        return f"BNT-{int(time.time()) % 100000}"

    def list_stores(self, category: str = "", query: str = "") -> Dict[str, Any]:
        """Hamkor do'konlar ro'yxatini toifa va qidiruv bo'yicha olish."""
        cat = (category or "").strip().lower()
        q = (query or "").strip().lower()
        res = []
        for s in PARTNER_STORES:
            if cat and cat != "all" and s["cat"] != cat:
                continue
            if q:
                hay = f"{s['name']} {s['addr']} {' '.join(i['name'] for i in s['items'])}".lower()
                if q not in hay:
                    continue
            res.append(s)
        return {"ok": True, "categories": DELIVERY_CATEGORIES, "stores": res}

    def get_home(self, user_id: int = 0) -> Dict[str, Any]:
        """Deliv mini-ilovasi bosh sahifasi ma'lumotlari."""
        orders = self.list_orders(user_id=user_id).get("orders", [])
        return {
            "ok": True,
            "categories": DELIVERY_CATEGORIES,
            "stores": PARTNER_STORES,
            "steps": DELIVERY_STEPS,
            "orders": orders,
        }

    def create_order(
        self,
        user_id: int,
        user_name: str = "Buyurtmachi",
        address: str = "",
        phone: str = "",
        items: Optional[List[Dict[str, Any]]] = None,
        pickup: str = "",
        store_id: str = "",
        note: str = "",
        payment: str = "naqd",
    ) -> Dict[str, Any]:
        """Yangi yetkazish buyurtmasini yaratish va BNT-XXXX kuzatuv kodi berish."""
        clean_addr = str(address or "").strip()
        clean_phone = str(phone or "").strip()
        if len(clean_addr) < 4:
            return {"ok": False, "error": "address_required", "msg": "Yetkazish manzilini aniq kiriting."}
        if len(clean_phone) < 7:
            return {"ok": False, "error": "phone_required", "msg": "Bog'lanish uchun telefon raqamingizni kiriting."}

        store = next((s for s in PARTNER_STORES if s["id"] == store_id), None)
        clean_pickup = str(pickup or "").strip() or (store["addr"] if store else "Toshkent shahar markazi")
        store_name = store["name"] if store else ("Kuryer pochta" if not store_id else store_id)
        delivery_fee = int(store["fee"]) if store else 15000

        norm_items: List[Dict[str, Any]] = []
        for raw_it in (items or []):
            if isinstance(raw_it, dict):
                nm = str(raw_it.get("name") or raw_it.get("title") or "").strip()
                qty = max(1, int(raw_it.get("qty", 1) or 1))
                price = max(0, int(raw_it.get("price", 0) or 0))
                if nm:
                    norm_items.append({"name": nm, "qty": qty, "price": price})
            elif isinstance(raw_it, str) and raw_it.strip():
                norm_items.append({"name": raw_it.strip(), "qty": 1, "price": 0})

        if not norm_items:
            return {"ok": False, "error": "items_required", "msg": "Kamida bitta mahsulot yoki jo'natma nomini kiriting."}

        subtotal = sum(it["qty"] * it["price"] for it in norm_items)
        total = subtotal + delivery_fee
        courier = random.choice(COURIERS_POOL)
        now_ts = int(time.time())
        now_label = datetime.fromtimestamp(now_ts).strftime("%H:%M")

        with _DELIV_LOCK:
            state = self._load_state()
            existing_codes = {o.get("code") for o in state["orders"]}
            code = self._generate_tracking_code(existing_codes)
            order = {
                "id": code,
                "code": code,
                "user_id": int(user_id or 0),
                "user_name": str(user_name or "Buyurtmachi")[:60],
                "store_id": store_id or "custom",
                "store_name": store_name,
                "pickup": clean_pickup,
                "address": clean_addr,
                "phone": clean_phone,
                "items": norm_items,
                "note": str(note or "").strip()[:300],
                "payment": payment if payment in ("naqd", "karta", "click", "payme") else "naqd",
                "subtotal": subtotal,
                "delivery_fee": delivery_fee,
                "total": total,
                "step": 0,
                "status_key": DELIVERY_STEPS[0]["key"],
                "status_title": DELIVERY_STEPS[0]["title"],
                "cancelled": False,
                "courier": courier,
                "eta": store["eta"] if store else "30–45 daq",
                "created_at": now_ts,
                "updated_at": now_ts,
                "timeline": [
                    {
                        "step": 0,
                        "key": DELIVERY_STEPS[0]["key"],
                        "title": DELIVERY_STEPS[0]["title"],
                        "at": now_ts,
                        "time": now_label,
                    }
                ],
            }
            state["orders"].insert(0, order)
            state["orders"] = state["orders"][:500]
            self._save_state(state)

        return {"ok": True, "code": code, "order": order}

    def list_orders(self, user_id: int = 0) -> Dict[str, Any]:
        """Foydalanuvchining buyurtmalari ro'yxatini qaytarish (user_id=0 bo'lsa barchasi)."""
        state = self._load_state()
        orders = state.get("orders", [])
        if user_id:
            orders = [o for o in orders if int(o.get("user_id", 0)) == int(user_id)]
        return {"ok": True, "orders": orders, "steps": DELIVERY_STEPS}

    def get_order(self, code_or_id: str, user_id: int = 0) -> Dict[str, Any]:
        """Kuzatuv kodi (BNT-XXXX) bo'yicha buyurtmani topish."""
        clean = str(code_or_id or "").strip().upper()
        state = self._load_state()
        for o in state.get("orders", []):
            if str(o.get("code", "")).upper() == clean or str(o.get("id", "")).upper() == clean:
                if user_id and int(o.get("user_id", 0)) not in (0, int(user_id)):
                    continue
                return {"ok": True, "order": o, "steps": DELIVERY_STEPS}
        return {"ok": False, "error": "not_found", "msg": "Bunday kuzatuv kodi bilan buyurtma topilmadi."}

    def advance_status(self, code_or_id: str, step: Optional[int] = None) -> Dict[str, Any]:
        """Buyurtma holatini keyingi bosqichga o'tkazish (Qabul qilindi -> Tayyorlanmoqda -> Yo'lda -> Yetkazildi)."""
        clean = str(code_or_id or "").strip().upper()
        now_ts = int(time.time())
        now_label = datetime.fromtimestamp(now_ts).strftime("%H:%M")

        with _DELIV_LOCK:
            state = self._load_state()
            target = None
            for o in state.get("orders", []):
                if str(o.get("code", "")).upper() == clean or str(o.get("id", "")).upper() == clean:
                    target = o
                    break
            if not target:
                return {"ok": False, "error": "not_found"}
            if target.get("cancelled"):
                return {"ok": False, "error": "cancelled"}

            cur_step = int(target.get("step", 0))
            next_step = cur_step + 1 if step is None else int(step)
            next_step = max(0, min(len(DELIVERY_STEPS) - 1, next_step))
            if next_step != cur_step:
                meta = DELIVERY_STEPS[next_step]
                target["step"] = next_step
                target["status_key"] = meta["key"]
                target["status_title"] = meta["title"]
                target["updated_at"] = now_ts
                target.setdefault("timeline", []).append({
                    "step": next_step,
                    "key": meta["key"],
                    "title": meta["title"],
                    "at": now_ts,
                    "time": now_label,
                })
                self._save_state(state)
            return {"ok": True, "order": target}

    def cancel_order(self, code_or_id: str, user_id: int = 0) -> Dict[str, Any]:
        """Hali yo'lga chiqmagan buyurtmani bekor qilish."""
        clean = str(code_or_id or "").strip().upper()
        with _DELIV_LOCK:
            state = self._load_state()
            for o in state.get("orders", []):
                if str(o.get("code", "")).upper() == clean or str(o.get("id", "")).upper() == clean:
                    if user_id and int(o.get("user_id", 0)) not in (0, int(user_id)):
                        return {"ok": False, "error": "forbidden"}
                    if int(o.get("step", 0)) >= 2:
                        return {"ok": False, "error": "already_dispatched", "msg": "Kuryer allaqachon yo'lga chiqqan."}
                    o["cancelled"] = True
                    o["status_key"] = "cancelled"
                    o["status_title"] = "Bekor qilindi"
                    o["updated_at"] = int(time.time())
                    self._save_state(state)
                    return {"ok": True, "order": o}
        return {"ok": False, "error": "not_found"}


deliv_service = DelivService()
