"""
Kino xizmati (Qidiruv, kod orqali topish, statistika va yuborish)
"""
import logging
from typing import Optional, List, Tuple
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from database import crud
from database.models import Movie
from utils.helpers import format_movie_caption, format_movie_not_found
from keyboards.inline import movie_item_keyboard

logger = logging.getLogger(__name__)


class MovieService:
    """Kinolar bilan ishlash logikasi."""

    @staticmethod
    async def find_by_code(session: AsyncSession, code: str) -> Optional[Movie]:
        """Kino kodi orqali kinoni topish."""
        return await crud.get_movie_by_code(session, code)

    @staticmethod
    async def search_by_title(session: AsyncSession, title: str, limit: int = 10) -> List[Movie]:
        """Nomi bo'yicha kinolarni qidirish."""
        return await crud.search_movies_by_title(session, title, limit=limit)

    @staticmethod
    async def get_by_genre(session: AsyncSession, genre: str, limit: int = 10) -> List[Movie]:
        """Janr bo'yicha kinolar ro'yxati."""
        return await crud.get_movies_by_genre(session, genre, limit=limit)

    @staticmethod
    async def get_random(session: AsyncSession) -> Optional[Movie]:
        """Tasodifiy kino olish."""
        return await crud.get_random_movie(session)

    @staticmethod
    async def get_top(session: AsyncSession, limit: int = 10) -> List[Movie]:
        """Eng mashhur kinolar ro'yxati."""
        return await crud.get_top_movies(session, limit=limit)

    @staticmethod
    async def send_movie_to_user(
        bot: Bot,
        chat_id: int,
        movie: Movie,
        session: AsyncSession,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """
        Foydalanuvchiga kinoni yuborish (file_id orqali) va ko'rishlar sonini oshirish.
        """
        caption = format_movie_caption(movie)
        reply_markup = movie_item_keyboard(movie.code)

        try:
            if movie.file_type == "document":
                await bot.send_document(
                    chat_id=chat_id,
                    document=movie.file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id
                )
            else:
                await bot.send_video(
                    chat_id=chat_id,
                    video=movie.file_id,
                    caption=caption,
                    parse_mode="HTML",
                    duration=movie.duration,
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id
                )

            # Ko'rishlar va yuklamalar sonini oshirish
            await crud.increment_movie_views(session, movie.id)
            await crud.increment_movie_downloads(session, movie.id)
            await crud.log_download(session, user_id=chat_id, platform="movie", query_or_url=movie.code)
            return True

        except Exception as e:
            logger.error(f"Kinoni yuborishda xatolik (movie_id={movie.id}, code={movie.code}): {e}")
            # Agar video sifatida yuborib bo'lmasa, document sifatida urinib ko'rish
            try:
                await bot.send_document(
                    chat_id=chat_id,
                    document=movie.file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id
                )
                await crud.increment_movie_views(session, movie.id)
                return True
            except Exception as e2:
                logger.error(f"Document sifatida ham yuborib bo'lmadi: {e2}")
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ Kechirasiz, kino faylini yuborishda texnik xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.",
                    reply_to_message_id=reply_to_message_id
                )
                return False


movie_service = MovieService()
