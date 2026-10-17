"""
Kino xizmati (Qidiruv, kod orqali topish, statistika va yuborish)
"""
import os
import json
import logging
from typing import Optional, List, Tuple
from pathlib import Path
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from config import config, BASE_DIR
from database import crud
from database.models import Movie
from utils.helpers import format_movie_caption, format_movie_not_found
from keyboards.inline import movie_item_keyboard, movie_parts_keyboard

logger = logging.getLogger(__name__)

# Kesh
_CATALOG_CACHE: Optional[dict] = None


class MovieService:
    """Kinolar bilan ishlash logikasi."""

    @staticmethod
    def get_catalog_item(code: str) -> Optional[dict]:
        """Katalog keshidan yoki faylidan kino ma'lumotlarini olish."""
        global _CATALOG_CACHE
        clean_code = str(code).strip().lstrip("#№")
        code_num = int(clean_code) if clean_code.isdigit() else None

        catalog_path = BASE_DIR / "data" / "catalog.json"
        if _CATALOG_CACHE is None and catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    _CATALOG_CACHE = json.load(f)
            except Exception:
                pass

        if _CATALOG_CACHE:
            for it in _CATALOG_CACHE.get("items", []):
                if str(it.get("c")) == clean_code or it.get("c") == code_num:
                    return it
        return None

    @staticmethod
    async def find_by_code(session: AsyncSession, code: str) -> Optional[Movie]:
        """Kino kodi orqali kinoni topish."""
        return await crud.get_movie_by_code(session, code)

    @staticmethod
    async def search_by_title(session: AsyncSession, title: str, limit: int = 10) -> List[Movie]:
        """Nomi va tavsifi bo'yicha kinolarni aqlli qidirish (Lotin + Kirill)."""
        return await crud.smart_search_movies(session, title, limit=limit)

    @staticmethod
    async def get_by_genre(session: AsyncSession, genre: str, limit: int = 10, offset: int = 0) -> List[Movie]:
        """Janr bo'yicha kinolar ro'yxati."""
        return await crud.get_movies_by_genre(session, genre, limit=limit, offset=offset)

    @staticmethod
    async def get_genre_count(session: AsyncSession, genre: str) -> int:
        """Janr bo'yicha kinolar soni."""
        return await crud.get_movies_by_genre_count(session, genre)

    @staticmethod
    async def get_random(session: AsyncSession) -> Optional[Movie]:
        """Tasodifiy kino olish."""
        return await crud.get_random_movie(session)

    @staticmethod
    async def get_top(session: AsyncSession, limit: int = 10) -> List[Movie]:
        """Eng mashhur kinolar ro'yxati."""
        return await crud.get_top_movies(session, limit=limit)

    @staticmethod
    async def deliver_movie(
        bot: Bot,
        chat_id: int,
        code: str,
        part: int = 1,
        session: Optional[AsyncSession] = None,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """
        Foydalanuvchiga kinoni yuborish (Video, HD Poster yoki tafsilotlar bilan).
        100% oq brend: @Zakirovs o'rniga @Bauntyfilmsbot va @BauntyFilms.
        """
        clean_code = str(code).strip().lstrip("#№")
        cat_item = MovieService.get_catalog_item(clean_code)

        title = ""
        total_parts = 1
        description = ""
        if cat_item:
            title = cat_item.get("t", "").strip()
            total_parts = int(cat_item.get("p", 1))
            description = cat_item.get("d", "").strip()

        db_movie = None
        if session:
            db_movie = await crud.get_movie_by_code(session, clean_code)
        else:
            from database.session import get_session
            async with get_session() as s:
                db_movie = await crud.get_movie_by_code(s, clean_code)

        if db_movie:
            if not title:
                title = db_movie.title
            if not description:
                description = db_movie.description

        if not title:
            title = f"Kino #{clean_code}"

        # Sarlavha va klaviatura (@Zakirovsfilms_bot ga 1v1 mos)
        channel_user = config.CHANNEL_USERNAME
        if total_parts > 1:
            caption = f"🎬 <b>{title} — {part}-qism</b>\n\n📢 Homiy kanal: {channel_user}  🍿 Kinolarimiz: {channel_user}"
            reply_markup = movie_parts_keyboard(clean_code, total_parts=total_parts, current_part=part)
        else:
            caption = f"🎬 <b>{title}</b>\n\n📢 Homiy kanal: {channel_user}  🍿 Kinolarimiz: {channel_user}"
            reply_markup = movie_item_keyboard(clean_code)

        # 1. Haqiqiy video mavjud bo'lsa (mock/placeholder bo'lmagan)
        has_real_video = db_movie and db_movie.file_id and not db_movie.file_id.startswith("mov_") and not db_movie.file_id.startswith("BAACAg")
        if has_real_video:
            try:
                if db_movie.file_type == "document":
                    await bot.send_document(
                        chat_id=chat_id,
                        document=db_movie.file_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                        reply_to_message_id=reply_to_message_id
                    )
                else:
                    await bot.send_video(
                        chat_id=chat_id,
                        video=db_movie.file_id,
                        caption=caption,
                        parse_mode="HTML",
                        duration=db_movie.duration,
                        reply_markup=reply_markup,
                        reply_to_message_id=reply_to_message_id
                    )
                if session and db_movie:
                    await crud.increment_movie_views(session, db_movie.id)
                return True
            except Exception as e:
                logger.warning(f"Video yuborib bo'lmadi ({e}), poster bilan yuboriladi.")

        # 2. HD Poster rasmi orqali yuborish
        posters_dir = BASE_DIR / "data" / "posters"
        posters_dir.mkdir(parents=True, exist_ok=True)
        poster_path = posters_dir / f"{clean_code}_l.webp"

        if not poster_path.exists():
            for size in ["l", "s"]:
                try:
                    import urllib.request
                    url = f"https://161-97-96-58.sslip.io/p/{clean_code}_{size}.webp"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        if resp.status == 200:
                            with open(poster_path, "wb") as pf:
                                pf.write(resp.read())
                            break
                except Exception:
                    pass

        if poster_path.exists():
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=FSInputFile(poster_path),
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id
                )
                if session and db_movie:
                    await crud.increment_movie_views(session, db_movie.id)
                return True
            except Exception as ep:
                logger.warning(f"Poster yuborib bo'lmadi ({ep}), matn yuboriladi.")

        # 3. Matnli xabar ko'rinishida yuborish
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id
            )
            if session and db_movie:
                await crud.increment_movie_views(session, db_movie.id)
            return True
        except Exception as em:
            logger.error(f"Xabar yuborib bo'lmadi: {em}")
            return False

    @staticmethod
    async def send_movie_to_user(
        bot: Bot,
        chat_id: int,
        movie: Movie,
        session: AsyncSession,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """Kino kodi orqali foydalanuvchiga yuborish."""
        return await MovieService.deliver_movie(
            bot=bot,
            chat_id=chat_id,
            code=movie.code,
            part=1,
            session=session,
            reply_to_message_id=reply_to_message_id
        )


movie_service = MovieService()
