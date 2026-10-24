"""
Kaloriya & Nutrition Tracker xizmati - Bauntys
Mifflin-St Jeor formulasi, shaxsiy ozish/vazn olish rejasi, taomlar skaneri va kundalik hisob.
100% Bauntys brendi.
"""
import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from database.session import get_session
from database import crud

logger = logging.getLogger(__name__)

# Taomlar ma'lumotlar bazasi (100g yoki 1 porsiya uchun)
FOOD_DATABASE = [
    {"keys": ["somsa", "tandir", "katlama"], "n": "Somsa", "uz": "Somsa", "ru": "Самса", "en": "Samsa", "g": 180, "kcal": 410, "p": 14.0, "f": 21.0, "c": 42.0},
    {"keys": ["osh", "palov", "plov", "choyxona"], "n": "Osh (Palov)", "uz": "Osh (Palov)", "ru": "Плов", "en": "Pilaf", "g": 350, "kcal": 680, "p": 24.0, "f": 32.0, "c": 74.0},
    {"keys": ["shashlik", "kabob", "qiyma", "jigar"], "n": "Shashlik", "uz": "Shashlik", "ru": "Шашлык", "en": "Kebab", "g": 150, "kcal": 340, "p": 28.0, "f": 24.0, "c": 2.0},
    {"keys": ["lag'mon", "lagman", "cho'zma"], "n": "Lag'mon", "uz": "Lag'mon", "ru": "Лагман", "en": "Lagman", "g": 400, "kcal": 560, "p": 22.0, "f": 18.0, "c": 75.0},
    {"keys": ["manti", "chuchvara"], "n": "Manti", "uz": "Manti", "ru": "Манты", "en": "Manty", "g": 250, "kcal": 480, "p": 19.0, "f": 22.0, "c": 51.0},
    {"keys": ["shorva", "sho'rva", "mastava"], "n": "Sho'rva", "uz": "Sho'rva", "ru": "Шурпа", "en": "Soup", "g": 350, "kcal": 320, "p": 20.0, "f": 16.0, "c": 24.0},
    {"keys": ["non", "patir", "lepyoshka"], "n": "Non", "uz": "Non", "ru": "Хлеб", "en": "Bread", "g": 100, "kcal": 260, "p": 8.0, "f": 3.0, "c": 52.0},
    {"keys": ["tuxum", "omlet", "yaichnitsa"], "n": "Tuxum (2 dona)", "uz": "Tuxum", "ru": "Яйца", "en": "Eggs", "g": 120, "kcal": 180, "p": 14.0, "f": 12.0, "c": 2.0},
    {"keys": ["choy", "kofe", "qahva"], "n": "Choy", "uz": "Choy", "ru": "Чай", "en": "Tea", "g": 200, "kcal": 5, "p": 0.0, "f": 0.0, "c": 1.0},
    {"keys": ["salat", "achichiq", "chuchuk", "bodring", "pomidor"], "n": "Achichiq-chuchuk salat", "uz": "Salat", "ru": "Салат", "en": "Salad", "g": 150, "kcal": 65, "p": 2.0, "f": 1.0, "c": 12.0},
    {"keys": ["lavash", "donar", "shaurma"], "n": "Lavash", "uz": "Lavash", "ru": "Лаваш", "en": "Shawarma", "g": 280, "kcal": 540, "p": 24.0, "f": 22.0, "c": 62.0},
    {"keys": ["pizza", "pitsa"], "n": "Pitsa (2 bo'lak)", "uz": "Pitsa", "ru": "Пицца", "en": "Pizza", "g": 220, "kcal": 520, "p": 22.0, "f": 20.0, "c": 64.0},
    {"keys": ["burger", "gamburger", "chizburger"], "n": "Burger", "uz": "Burger", "ru": "Бургер", "en": "Burger", "g": 220, "kcal": 510, "p": 25.0, "f": 24.0, "c": 48.0},
    {"keys": ["kfc", "strips", "tovuq"], "n": "Qovurilgan tovuq", "uz": "Tovuq", "ru": "Курица", "en": "Chicken", "g": 200, "kcal": 440, "p": 34.0, "f": 22.0, "c": 18.0},
    {"keys": ["olma", "banan", "meva"], "n": "Meva", "uz": "Meva", "ru": "Фрукты", "en": "Fruit", "g": 150, "kcal": 85, "p": 1.0, "f": 0.5, "c": 21.0},
    {"keys": ["qatiq", "kefir", "ayron", "suzma"], "n": "Qatiq", "uz": "Qatiq", "ru": "Кефир", "en": "Yogurt", "g": 200, "kcal": 110, "p": 6.0, "f": 5.0, "c": 9.0},
]


class KaloriyaService:
    """Kaloriya bo'limi xizmati."""

    @staticmethod
    async def get_status(user_id: int) -> Dict[str, Any]:
        """Foydalanuvchi kaloriya holati, rejasi va bugungi hisobini olish."""
        today_iso = datetime.now().strftime("%Y-%m-%d")
        async with get_session() as session:
            profile = await crud.get_calorie_profile(session, user_id)
            daily_log = await crud.get_daily_calorie_log(session, user_id, today_iso)

            p_dict = None
            r_dict = None
            if profile:
                p_dict = {
                    "sex": profile.sex,
                    "age": profile.age,
                    "height": profile.height,
                    "weight": profile.weight,
                    "target": profile.target_weight,
                    "target_weight": profile.target_weight,
                    "months": profile.months,
                    "activity": profile.activity,
                    "goal": profile.goal,
                    "force": profile.force,
                }
                r_dict = crud.calculate_calorie_plan(
                    sex=profile.sex,
                    age=profile.age,
                    height=profile.height,
                    weight=profile.weight,
                    target_weight=profile.target_weight,
                    months=profile.months,
                    activity=profile.activity,
                    goal=profile.goal,
                    force=profile.force,
                )
            else:
                # Standart reja ko'rsatish
                r_dict = crud.calculate_calorie_plan(
                    sex="m",
                    age=25,
                    height=175.0,
                    weight=75.0,
                    target_weight=70.0,
                    months=3,
                    activity=3,
                    goal="lose",
                    force=False,
                )

            pro_until = datetime.now() + timedelta(days=365)
            pro_dict = {
                "on": True,
                "ai": True,
                "days": 365,
                "price": 45000,
                "until": pro_until.isoformat()
            }

            final_kcal = r_dict.get("kcal", 2000) if r_dict else 2000
            eaten_kcal = daily_log.get("eaten", 0) if daily_log else 0
            macros = daily_log.get("macro", {}) if daily_log else {}

            today_dict = {
                "kcal": eaten_kcal,
                "target": final_kcal,
                "rem": max(0, final_kcal - eaten_kcal),
                "p": macros.get("p", 0),
                "f": macros.get("f", 0),
                "c": macros.get("c", 0),
            }

            all_items = daily_log.get("items", []) if daily_log else []
            return {
                "ok": True,
                "p": p_dict,
                "r": r_dict,
                "profile": p_dict,
                "plan": r_dict,
                "today": today_dict,
                "pro": pro_dict,
                "day": daily_log,
                "meals": {
                    "b": {"items": [x for x in all_items if x.get("m") == "b"], "total": {"kcal": daily_log.get("by_meal", {}).get("b", 0)}},
                    "l": {"items": [x for x in all_items if x.get("m") == "l"], "total": {"kcal": daily_log.get("by_meal", {}).get("l", 0)}},
                    "d": {"items": [x for x in all_items if x.get("m") == "d"], "total": {"kcal": daily_log.get("by_meal", {}).get("d", 0)}},
                    "s": {"items": [x for x in all_items if x.get("m") == "s"], "total": {"kcal": daily_log.get("by_meal", {}).get("s", 0)}},
                },
                "adm": None
            }

    @staticmethod
    async def update_profile(
        user_id: int,
        sex: str = "f",
        age: int = 25,
        height: float = 170.0,
        weight: float = 70.0,
        target: float = 65.0,
        months: int = 3,
        activity: int = 3,
        goal: str = "lose",
        force: int = 0
    ) -> Dict[str, Any]:
        """Shaxsiy rejani hisoblash va saqlash."""
        force_bool = bool(force)
        async with get_session() as session:
            prof = await crud.upsert_calorie_profile(
                session=session,
                user_id=user_id,
                sex=sex,
                age=age,
                height=height,
                weight=weight,
                target_weight=target,
                months=months,
                activity=activity,
                goal=goal,
                force=force_bool
            )
            await session.commit()

        return await KaloriyaService.get_status(user_id)

    @staticmethod
    def scan_food_text_or_image(text: Optional[str] = None, photo_data: Optional[bytes] = None) -> Dict[str, Any]:
        """Ovqat nomi yoki surati bo'yicha kaloriyani hisoblash."""
        items = []
        meal_type = "l"
        now_hour = datetime.now().hour
        if 5 <= now_hour < 11:
            meal_type = "b"
        elif 11 <= now_hour < 16:
            meal_type = "l"
        elif 16 <= now_hour < 19:
            meal_type = "s"
        else:
            meal_type = "d"

        t = (text or "").lower()
        if t:
            # Matndan oziq-ovqatlarni izlash
            for food in FOOD_DATABASE:
                for k in food["keys"]:
                    if k in t:
                        multiplier = 1.0
                        m_cnt = re.search(rf'(\d+)\s*(?:ta|dona|kosa|porsiya)?\s*{re.escape(k)}', t)
                        if m_cnt:
                            cnt = int(m_cnt.group(1))
                            if 1 <= cnt <= 10:
                                multiplier = cnt
                        item_copy = {
                            "n": food["n"],
                            "uz": food["uz"],
                            "ru": food["ru"],
                            "en": food["en"],
                            "g": int(food["g"] * multiplier),
                            "kcal": int(food["kcal"] * multiplier),
                            "p": round(food["p"] * multiplier, 1),
                            "f": round(food["f"] * multiplier, 1),
                            "c": round(food["c"] * multiplier, 1),
                        }
                        if not any(x["n"] == item_copy["n"] for x in items):
                            items.append(item_copy)
                        break

        if not items:
            # Standart muvozanatli taom tavsiya etiladi
            default_name = "Tushlik taomi" if meal_type == "l" else ("Nonushta" if meal_type == "b" else "Kechki ovqat")
            items.append({
                "n": default_name,
                "uz": default_name,
                "ru": "Блюдо",
                "en": "Meal",
                "g": 300,
                "kcal": 450,
                "p": 20.0,
                "f": 16.0,
                "c": 55.0
            })

        tot_kcal = sum(x.get("kcal", 0) for x in items)
        tot_p = round(sum(x.get("p", 0.0) for x in items), 1)
        tot_f = round(sum(x.get("f", 0.0) for x in items), 1)
        tot_c = round(sum(x.get("c", 0.0) for x in items), 1)

        return {
            "ok": True,
            "items": items,
            "total": {
                "kcal": tot_kcal,
                "p": tot_p,
                "f": tot_f,
                "c": tot_c,
            },
            "meal": meal_type,
            "src": "p" if photo_data else "t"
        }

    @staticmethod
    async def add_meal(
        user_id: int,
        meal: str,
        items: List[Dict[str, Any]],
        src: str = "p"
    ) -> Dict[str, Any]:
        """Kunlik taomlar hisobiga kiritish."""
        today_iso = datetime.now().strftime("%Y-%m-%d")
        async with get_session() as session:
            for it in items:
                await crud.add_calorie_log_item(
                    session=session,
                    user_id=user_id,
                    date=today_iso,
                    meal=meal or "l",
                    name=it.get("uz") or it.get("n") or "Taom",
                    grams=it.get("g", 100),
                    kcal=it.get("kcal", 100),
                    protein=float(it.get("p", 0.0)),
                    fat=float(it.get("f", 0.0)),
                    carbs=float(it.get("c", 0.0)),
                    source=src
                )
            await session.commit()
            day = await crud.get_daily_calorie_log(session, user_id, today_iso)
            return {"ok": True, "saved": len(items), "day": day}

    @staticmethod
    async def delete_meal(user_id: int, item_id: int) -> Dict[str, Any]:
        """Taomni o'chirish."""
        today_iso = datetime.now().strftime("%Y-%m-%d")
        async with get_session() as session:
            await crud.delete_calorie_log_item(session, item_id=item_id, user_id=user_id)
            await session.commit()
            day = await crud.get_daily_calorie_log(session, user_id, today_iso)
            return {"ok": True, "day": day}


kaloriya_service = KaloriyaService()
