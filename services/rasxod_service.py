"""
Rasxod (Expense tracker) xizmati - Bauntys
Kunlik va oylik xarajatlar daftari, byudjet, toifalar va tahlillar.
100% Bauntys brendi.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from database.session import get_session
from database import crud

logger = logging.getLogger(__name__)


class RasxodService:
    """Rasxod biznes logikasi."""

    @staticmethod
    async def get_home(user_id: int, year_month: Optional[str] = None) -> Dict[str, Any]:
        """Oylik xarajatlar bosh sahifasi tahlili."""
        async with get_session() as session:
            return await crud.get_monthly_expense_summary(session, user_id=user_id, year_month=year_month)

    @staticmethod
    async def add_expenses_from_text(user_id: int, text: str) -> Dict[str, Any]:
        """Matndan xarajatlarni ajratib bazaga saqlash."""
        parsed = crud.parse_expense_text(text)
        if not parsed:
            # Agar raqam topilmasa, xato qaytarish
            return {"ok": False, "error": "no_amount"}

        today_iso = datetime.now().strftime("%Y-%m-%d")
        saved_items = []
        async with get_session() as session:
            for item in parsed:
                exp = await crud.add_expense(
                    session=session,
                    user_id=user_id,
                    amount=item["a"],
                    note=item["n"],
                    category=item["c"],
                    date=today_iso,
                    source="t"
                )
                saved_items.append({
                    "id": exp.id,
                    "e": item["e"],
                    "n": exp.note,
                    "a": exp.amount,
                    "c": exp.category,
                    "d": exp.date
                })
            await session.commit()

        return {
            "ok": True,
            "items": saved_items,
            "saved": saved_items,
            "day": today_iso
        }

    @staticmethod
    async def get_list(
        user_id: int,
        month: Optional[str] = None,
        category: Optional[str] = None,
        before_id: Optional[int] = None,
        limit: int = 60
    ) -> Dict[str, Any]:
        """Xarajatlar tarixi ro'yxati."""
        async with get_session() as session:
            items = await crud.get_expenses(
                session=session,
                user_id=user_id,
                month=month,
                category=category,
                before_id=before_id,
                limit=limit
            )
            res = []
            for it in items:
                cat_info = crud.CATEGORY_MAP.get(it.category, crud.CATEGORY_MAP["other"])
                res.append({
                    "id": it.id,
                    "e": cat_info["e"],
                    "n": it.note,
                    "a": it.amount,
                    "c": it.category,
                    "d": it.date,
                    "src": it.source
                })
            return {"ok": True, "items": res}

    @staticmethod
    async def edit(
        user_id: int,
        expense_id: int,
        amount: int,
        note: str,
        date: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Xarajatni tahrirlash."""
        async with get_session() as session:
            success = await crud.edit_expense(
                session=session,
                expense_id=expense_id,
                user_id=user_id,
                amount=amount,
                note=note,
                date=date,
                category=category
            )
            if success:
                await session.commit()
                return {"ok": True}
            return {"ok": False, "error": "not_found"}

    @staticmethod
    async def delete(user_id: int, expense_id: int) -> Dict[str, Any]:
        """Xarajatni o'chirish."""
        async with get_session() as session:
            success = await crud.delete_expense(session, expense_id=expense_id, user_id=user_id)
            if success:
                await session.commit()
                return {"ok": True}
            return {"ok": False, "error": "not_found"}

    @staticmethod
    async def set_budget(user_id: int, amount: int, month: Optional[str] = None) -> Dict[str, Any]:
        """Oylik byudjet o'rnatish."""
        if not month:
            month = datetime.now().strftime("%Y-%m")
        async with get_session() as session:
            await crud.set_expense_budget(session, user_id=user_id, month=month, amount=amount)
            await session.commit()
            return {"ok": True, "budget": amount}


rasxod_service = RasxodService()
