"""
Katalogdagi barcha 179+ kinolarni PostgreSQL bazasi bilan tezkor sinxronlash.
"""
import sys
import json
import asyncio
from pathlib import Path

# Kodirovka
sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database.session import get_session
from database.models import Movie
from sqlalchemy import select


async def sync():
    catalog_path = BASE_DIR / "data" / "catalog.json"
    if not catalog_path.exists():
        print("data/catalog.json topilmadi!")
        return

    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    print(f"Katalogda {len(items)} ta kino mavjud. Bazaga ulanilmoqda...", flush=True)

    async with get_session() as session:
        # Barcha mavjud kinolarni bitta so'rovda olish
        res = await session.execute(select(Movie))
        existing_movies = {m.code: m for m in res.scalars().all()}
        print(f"Bazada {len(existing_movies)} ta mavjud kino topildi.", flush=True)

        updated = 0
        inserted = 0

        for it in items:
            code = str(it.get("c", "")).strip()
            title = it.get("t", "").strip()
            desc = it.get("d", "").strip()
            views = int(it.get("v", 0))

            if code in existing_movies:
                m = existing_movies[code]
                m.title = title
                m.description = desc
                m.views_count = max(m.views_count, views)
                updated += 1
            else:
                m = Movie(
                    code=code,
                    title=title,
                    description=desc,
                    file_id=f"mov_{code}_placeholder",
                    views_count=views,
                    genres="Barcha"
                )
                session.add(m)
                inserted += 1

        await session.commit()
        print(f"Muvaffaqiyatli yakunlandi! Yangilandi: {updated}, Yangi qo'shildi: {inserted}", flush=True)


if __name__ == "__main__":
    asyncio.run(sync())
