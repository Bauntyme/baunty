"""
Ma'lumotlar bazasi bilan ishlash funksiyalari (CRUD)
"""
import re
import asyncio
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any, Set
from sqlalchemy import select, update, delete, func, desc, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    User, Movie, MovieFile, UserWatchProgress, SponsorChannel, DownloadLog, BotSetting,
    AnonymousMessage, AnonQuestionProfile, AnonBlockedSender,
    Feedback, Expense, ExpenseBudget, UserCalorieProfile,
    CalorieLogItem, MafiaGameRecord, utc_now
)
from utils.translit import get_both_scripts, get_actor_variants

logger = logging.getLogger(__name__)


# ==========================================
# FOYDALANUVCHILAR (USERS)
# ==========================================

async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    is_admin: bool = False,
) -> Tuple[User, bool]:
    """Foydalanuvchini oladi yoki yangisini yaratadi. (user, created) qaytaradi."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Ma'lumotlarni yangilash
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            changed = True
        user.last_active = utc_now()
        if changed:
            await session.flush()
        return user, False
    else:
        new_user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin,
            is_banned=False,
            created_at=utc_now(),
            last_active=utc_now(),
        )
        try:
            async with session.begin_nested():
                session.add(new_user)
                await session.flush()
            return new_user, True
        except IntegrityError:
            # Parallel so'rov natijasida foydalanuvchi allaqachon yaratilgan
            for _ in range(5):
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                if user:
                    break
                await asyncio.sleep(0.05)
            if user:
                changed = False
                if username and user.username != username:
                    user.username = username
                    changed = True
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    changed = True
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    changed = True
                user.last_active = utc_now()
                if changed:
                    await session.flush()
                return user, False
            raise


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    """Foydalanuvchini ID bo'yicha olish."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_user_activity(session: AsyncSession, user_id: int) -> None:
    """Foydalanuvchining so'nggi faollik vaqtini yangilash."""
    stmt = update(User).where(User.id == user_id).values(last_active=utc_now())
    await session.execute(stmt)


async def get_user_language(session: AsyncSession, user_id: int) -> str:
    """Foydalanuvchi tanlagan tilni olish (default: 'uz')."""
    stmt = select(User.language).where(User.id == user_id)
    result = await session.execute(stmt)
    lang = result.scalar_one_or_none()
    return lang or "uz"


async def set_user_language(session: AsyncSession, user_id: int, language: str) -> bool:
    """Foydalanuvchi tilini yangilash ('uz', 'oz', 'ru')."""
    clean_lang = language.lower() if language in ("uz", "oz", "ru") else "uz"
    user = await get_user(session, user_id)
    if not user:
        await get_or_create_user(session, user_id=user_id)
    stmt = update(User).where(User.id == user_id).values(language=clean_lang)
    await session.execute(stmt)
    await session.commit()
    return True


async def get_total_users_count(session: AsyncSession) -> int:
    """Jami ro'yxatdan o'tgan foydalanuvchilar soni."""
    stmt = select(func.count(User.id))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_today_users_count(session: AsyncSession) -> int:
    """Bugun qo'shilgan yangi foydalanuvchilar soni."""
    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(User.id)).where(User.created_at >= today_start)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_active_users_24h_count(session: AsyncSession) -> int:
    """Oxirgi 24 soatda faol bo'lgan foydalanuvchilar soni."""
    last_24h = utc_now() - timedelta(hours=24)
    stmt = select(func.count(User.id)).where(User.last_active >= last_24h)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_all_user_ids(session: AsyncSession, include_banned: bool = False) -> List[int]:
    """Barcha foydalanuvchilar ID larini olish (xabarnoma uchun)."""
    stmt = select(User.id)
    if not include_banned:
        stmt = stmt.where(User.is_banned == False)
    result = await session.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def set_user_ban_status(session: AsyncSession, user_id: int, is_banned: bool) -> bool:
    """Foydalanuvchini bloklash yoki blokdan chiqarish."""
    stmt = update(User).where(User.id == user_id).values(is_banned=is_banned)
    result = await session.execute(stmt)
    return result.rowcount > 0


async def is_user_banned(session: AsyncSession, user_id: int) -> bool:
    """Foydalanuvchi bloklanganligini tekshirish."""
    stmt = select(User.is_banned).where(User.id == user_id)
    result = await session.execute(stmt)
    return bool(result.scalar_one_or_none())


# ==========================================
# KINOLAR (MOVIES)
# ==========================================

async def create_movie(
    session: AsyncSession,
    code: str,
    title: str,
    file_id: str,
    description: Optional[str] = None,
    file_type: str = "video",
    file_size: Optional[int] = None,
    duration: Optional[int] = None,
    genres: str = "Barcha",
    year: Optional[int] = None,
    rating: Optional[float] = None,
    poster_file_id: Optional[str] = None,
) -> Movie:
    """Yangi kino yaratish."""
    movie = Movie(
        code=str(code).strip(),
        title=title.strip(),
        file_id=file_id.strip(),
        description=description.strip() if description else None,
        file_type=file_type,
        file_size=file_size,
        duration=duration,
        genres=genres.strip() if genres else "Barcha",
        year=year,
        rating=rating,
        poster_file_id=poster_file_id,
        created_at=utc_now(),
    )
    session.add(movie)
    await session.flush()
    return movie


async def get_movie_by_code(session: AsyncSession, code: str) -> Optional[Movie]:
    """Kino kodini qidirish (masalan: 123, 405)."""
    stmt = select(Movie).where(Movie.code == str(code).strip())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_movie_by_id(session: AsyncSession, movie_id: int) -> Optional[Movie]:
    """Kinoni ichki ID bo'yicha olish."""
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def search_movies_by_title(
    session: AsyncSession,
    query: str,
    limit: int = 10,
    offset: int = 0
) -> List[Movie]:
    """Nomi yoki tavsifi bo'yicha kinolarni qidirish."""
    search_pattern = f"%{query.strip()}%"
    stmt = (
        select(Movie)
        .where(
            or_(
                Movie.title.ilike(search_pattern),
                Movie.description.ilike(search_pattern),
                Movie.genres.ilike(search_pattern)
            )
        )
        .order_by(desc(Movie.views_count))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_movies_by_genre(
    session: AsyncSession,
    genre: str,
    limit: int = 10,
    offset: int = 0
) -> List[Movie]:
    """Janr bo'yicha kinolar ro'yxati."""
    pattern = f"%{genre.strip()}%"
    stmt = (
        select(Movie)
        .where(Movie.genres.ilike(pattern))
        .order_by(desc(Movie.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_movies_by_genre_count(
    session: AsyncSession,
    genre: str
) -> int:
    """Janr bo'yicha jami kinolar soni."""
    pattern = f"%{genre.strip()}%"
    stmt = select(func.count(Movie.id)).where(Movie.genres.ilike(pattern))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_movies_by_year(
    session: AsyncSession,
    year: int,
    limit: int = 10,
    offset: int = 0
) -> List[Movie]:
    """Yili bo'yicha kinolar ro'yxati."""
    stmt = (
        select(Movie)
        .where(Movie.year == year)
        .order_by(desc(Movie.views_count), desc(Movie.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_movies_by_year_count(
    session: AsyncSession,
    year: int
) -> int:
    """Yili bo'yicha jami kinolar soni."""
    stmt = select(func.count(Movie.id)).where(Movie.year == year)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_movies_by_actor(
    session: AsyncSession,
    actor: str,
    limit: int = 10,
    offset: int = 0
) -> List[Movie]:
    """Aktyor bo'yicha kinolar ro'yxati (nomi va tavsifidan, Lotin hamda Kirill)."""
    clean_actor = actor.strip()
    if not clean_actor:
        return []
    variants = get_actor_variants(clean_actor)
    conditions = []
    for v in variants:
        pat = f"%{v}%"
        conditions.append(Movie.title.ilike(pat))
        conditions.append(Movie.description.ilike(pat))
    stmt = (
        select(Movie)
        .where(or_(*conditions))
        .order_by(desc(Movie.views_count), desc(Movie.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_movies_by_actor_count(
    session: AsyncSession,
    actor: str
) -> int:
    """Aktyor bo'yicha kinolar soni (Lotin hamda Kirill)."""
    clean_actor = actor.strip()
    if not clean_actor:
        return 0
    variants = get_actor_variants(clean_actor)
    conditions = []
    for v in variants:
        pat = f"%{v}%"
        conditions.append(Movie.title.ilike(pat))
        conditions.append(Movie.description.ilike(pat))
    stmt = select(func.count(Movie.id)).where(or_(*conditions))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_random_movie(session: AsyncSession) -> Optional[Movie]:
    """Tasodifiy kinoni olish."""
    stmt = select(Movie).order_by(func.random()).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_top_movies(session: AsyncSession, limit: int = 10) -> List[Movie]:
    """Eng ko'p ko'rilgan kinolar ro'yxati."""
    stmt = (
        select(Movie)
        .order_by(desc(Movie.views_count), desc(Movie.downloads_count))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_all_movies(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0
) -> List[Movie]:
    """Barcha kinolar ro'yxati (admin yoki sahifalash uchun)."""
    stmt = select(Movie).order_by(desc(Movie.id)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_total_movies_count(session: AsyncSession) -> int:
    """Bazada mavjud jami kinolar soni."""
    stmt = select(func.count(Movie.id))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def update_movie(
    session: AsyncSession,
    code: str,
    **kwargs: Any
) -> Optional[Movie]:
    """Kinoni tahrirlash."""
    movie = await get_movie_by_code(session, code)
    if not movie:
        return None

    for key, value in kwargs.items():
        if hasattr(movie, key) and value is not None:
            setattr(movie, key, value)

    await session.flush()
    return movie


async def set_movie_video(
    session: AsyncSession,
    code: str,
    file_id: str,
    file_type: str = "video",
    duration: Optional[int] = None,
    file_size: Optional[int] = None,
    title: Optional[str] = None,
) -> Optional[Movie]:
    """Kinoga haqiqiy video file_id yoki video manbasini biriktirish."""
    clean_code = str(code).strip()
    movie = await get_movie_by_code(session, clean_code)
    dur_val = int(duration) if isinstance(duration, (int, float)) else None
    fsize_val = int(file_size) if isinstance(file_size, (int, float)) else None
    fid_str = str(file_id).strip()
    if not fid_str or fid_str.startswith("<") or fid_str.lower() in ("none", "null"):
        fid_str = ""

    if not movie:
        movie = Movie(
            code=clean_code,
            title=title.strip() if title else f"Kino #{clean_code}",
            file_id=fid_str,
            file_type=file_type,
            duration=dur_val,
            file_size=fsize_val,
            created_at=utc_now()
        )
        session.add(movie)
        await session.flush()

    if fid_str:
        is_new_url = fid_str.startswith("http://") or fid_str.startswith("https://")
        curr_is_real_fid = _is_real_telegram_file_id(movie.file_id)
        if not (is_new_url and curr_is_real_fid):
            movie.file_id = fid_str

        # Telegram Cloud pool: movie_files jadvaliga ham saqlab qo'yish
        try:
            m_part = 1
            b_code = clean_code
            m_match = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", clean_code, re.IGNORECASE)
            if m_match:
                b_code = m_match.group(1)
                m_part = int(m_match.group(2))
            elif "_" in clean_code:
                parts_split = clean_code.split("_")
                if len(parts_split) == 2 and parts_split[1].isdigit():
                    b_code = parts_split[0]
                    m_part = int(parts_split[1])
            save_fid = movie.file_id if (is_new_url and curr_is_real_fid) else fid_str
            await save_movie_file(
                session=session,
                movie_code=b_code,
                part=m_part,
                file_id=save_fid,
                file_type=file_type,
                duration=dur_val,
                file_size=fsize_val
            )
        except Exception:
            pass

    movie.file_type = file_type
    if title:
        movie.title = title.strip()
    if dur_val is not None:
        movie.duration = dur_val
    if fsize_val is not None:
        movie.file_size = fsize_val
    await session.flush()
    return movie


def _is_real_telegram_file_id(fid: Optional[str]) -> bool:
    """Tekshirish: string haqiqiy Telegram Cloud file_id mi (stream URL yoki placeholder emas)."""
    if not fid:
        return False
    s = str(fid).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return False
    if s.startswith("<") or s.lower() in ("none", "null", "false", "0"):
        return False
    if any(w in s.lower() for w in ["sample", "test", "mock", "placeholder", "fake"]):
        return False
    return len(s) >= 20


async def save_movie_file(
    session: AsyncSession,
    movie_code: str,
    part: int = 1,
    file_id: str = "",
    file_type: str = "video",
    file_size: Optional[int] = None,
    duration: Optional[int] = None,
    quality: str = "1080p",
) -> MovieFile:
    """Har bir qism uchun Telegram Cloud file_id sini movie_files jadvalida keshlab saqlash."""
    clean_code = str(movie_code).strip().lstrip("#№")
    m_part = int(part) if part is not None else 1
    m_match = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", clean_code, re.IGNORECASE)
    if m_match and m_part == 1:
        clean_code = m_match.group(1)
        m_part = int(m_match.group(2))

    stmt = (
        select(MovieFile)
        .where(MovieFile.movie_code == clean_code, MovieFile.part == m_part)
        .order_by(MovieFile.id.desc())
    )
    res = await session.execute(stmt)
    mf = res.scalars().first()
    dur_val = int(duration) if isinstance(duration, (int, float)) else None
    fsize_val = int(file_size) if isinstance(file_size, (int, float)) else None
    fid_str = str(file_id).strip()
    if not fid_str or fid_str.startswith("<") or fid_str.lower() in ("none", "null"):
        fid_str = ""

    is_stream_url = bool(fid_str and (fid_str.startswith("http://") or fid_str.startswith("https://")))

    async def _sync_to_movies_table(effective_fid: Optional[str] = None) -> None:
        target_fid = effective_fid or fid_str
        if not target_fid:
            return
        try:
            target_codes = []
            if m_part == 1:
                target_codes.append(clean_code)
                target_codes.append(f"{clean_code}_1")
            else:
                target_codes.append(f"{clean_code}_{m_part}")

            for t_code in target_codes:
                m_row = await get_movie_by_code(session, t_code)
                if m_row:
                    m_curr_has_real = _is_real_telegram_file_id(m_row.file_id)
                    t_is_stream = bool(target_fid and (target_fid.startswith("http://") or target_fid.startswith("https://")))
                    if not (t_is_stream and m_curr_has_real):
                        m_row.file_id = target_fid
                    m_row.file_type = file_type
                    if dur_val is not None:
                        m_row.duration = dur_val
                    if fsize_val is not None:
                        m_row.file_size = fsize_val
        except Exception as sync_err:
            logger.debug(f"Dual-table sync to movies table in save_movie_file: {sync_err}")

    if mf:
        curr_has_real_fid = _is_real_telegram_file_id(mf.file_id)
        if fid_str and not (is_stream_url and curr_has_real_fid):
            mf.file_id = fid_str
        mf.file_type = file_type
        if dur_val is not None:
            mf.duration = dur_val
        if fsize_val is not None:
            mf.file_size = fsize_val
        if quality:
            mf.quality = quality
        sync_fid = mf.file_id if curr_has_real_fid else fid_str
        await _sync_to_movies_table(effective_fid=sync_fid)
        await session.flush()
        return mf
    else:
        # Yangi MovieFile yozuvi yaratishda agar stream URL kelsa va movies jadvalida haqiqiy file_id bo'lsa, o'shandan foydalanish
        if is_stream_url:
            m_existing = await get_movie_by_code(session, clean_code)
            if m_existing and _is_real_telegram_file_id(m_existing.file_id):
                fid_str = m_existing.file_id
                is_stream_url = False

        new_mf = MovieFile(
            movie_code=clean_code,
            part=m_part,
            file_id=fid_str,
            file_type=file_type,
            file_size=fsize_val,
            duration=dur_val,
            quality=quality,
            created_at=utc_now(),
        )
        try:
            async with session.begin_nested():
                session.add(new_mf)
                await session.flush()
            await _sync_to_movies_table(effective_fid=fid_str)
            return new_mf
        except IntegrityError:
            # Parallel sinxronizatsiya sababli movie_file yaratilgan
            for _ in range(10):
                try:
                    await session.rollback()
                except Exception:
                    pass
                stmt = (
                    select(MovieFile)
                    .where(MovieFile.movie_code == clean_code, MovieFile.part == m_part)
                    .order_by(MovieFile.id.desc())
                )
                res = await session.execute(stmt)
                mf = res.scalars().first()
                if mf:
                    break
                await asyncio.sleep(0.05)
            if mf:
                curr_has_real_fid = _is_real_telegram_file_id(mf.file_id)
                if fid_str and not (is_stream_url and curr_has_real_fid):
                    mf.file_id = fid_str
                mf.file_type = file_type
                if dur_val is not None:
                    mf.duration = dur_val
                if fsize_val is not None:
                    mf.file_size = fsize_val
                if quality:
                    mf.quality = quality
                sync_fid = mf.file_id if curr_has_real_fid else fid_str
                await _sync_to_movies_table(effective_fid=sync_fid)
                await session.flush()
                return mf
            raise


async def get_movie_file(
    session: AsyncSession,
    movie_code: str,
    part: int = 1,
) -> Optional[MovieFile]:
    """Kinoning ma'lum qismi uchun saqlangan Telegram file_id sini olish."""
    clean_code = str(movie_code).strip().lstrip("#№")
    m_part = int(part) if part is not None else 1
    m_match = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", clean_code, re.IGNORECASE)
    if m_match and m_part == 1:
        clean_code = m_match.group(1)
        m_part = int(m_match.group(2))

    stmt = (
        select(MovieFile)
        .where(MovieFile.movie_code == clean_code, MovieFile.part == m_part)
        .order_by(MovieFile.id.desc())
    )
    res = await session.execute(stmt)
    return res.scalars().first()


async def record_user_watched_episode(
    session: AsyncSession,
    user_id: int,
    movie_code: str,
    part: int = 1,
) -> None:
    """Foydalanuvchi ko'rgan/yuklab olgan kino yoki serial qismini saqlash."""
    clean_code = str(movie_code).strip().lstrip("#№")
    m_part = int(part) if part is not None else 1
    m_match = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", clean_code, re.IGNORECASE)
    if m_match and m_part == 1:
        clean_code = m_match.group(1)
        m_part = int(m_match.group(2))
    u_id = int(user_id)

    stmt = select(UserWatchProgress).where(
        UserWatchProgress.user_id == u_id,
        UserWatchProgress.movie_code == clean_code,
        UserWatchProgress.part == m_part,
    )
    res = await session.execute(stmt)
    record = res.scalars().first()
    if record:
        record.updated_at = utc_now()
        await session.flush()
    else:
        new_record = UserWatchProgress(
            user_id=u_id,
            movie_code=clean_code,
            part=m_part,
            updated_at=utc_now(),
        )
        try:
            async with session.begin_nested():
                session.add(new_record)
                await session.flush()
        except IntegrityError:
            res = await session.execute(stmt)
            rec = res.scalars().first()
            if rec:
                rec.updated_at = utc_now()
                await session.flush()


async def get_user_watched_episodes(
    session: AsyncSession,
    user_id: int,
    movie_code: str,
) -> Set[int]:
    """Foydalanuvchi ko'rgan barcha qismlar raqamlari to'plamini (set) qaytarish."""
    clean_code = str(movie_code).strip().lstrip("#№")
    m_match = re.match(r"^(\d+)[\s_\-pP]+(?:qism|part)?(\d+)$", clean_code, re.IGNORECASE)
    if m_match:
        clean_code = m_match.group(1)
    u_id = int(user_id)

    stmt = select(UserWatchProgress.part).where(
        UserWatchProgress.user_id == u_id,
        UserWatchProgress.movie_code == clean_code,
    )
    res = await session.execute(stmt)
    parts = res.scalars().all()
    return set(parts)



async def sync_movie_asilmedia_parts(
    session: AsyncSession,
    code: str,
    episodes: Dict[int, Any],
    base_title: Optional[str] = None
) -> int:
    """
    Asilmedia dan olingan barcha qismlarni (1..N) bazaga 'code_part' ko'rinishida saqlash.
    Mavjud haqiqiy Telegram file_id lar xavfsiz saqlab qolinadi.
    """
    clean_code = str(code).strip()
    synced = 0
    for part_num, ep in episodes.items():
        p_code = f"{clean_code}_{part_num}" if int(part_num) > 1 else clean_code
        url = ep.get("url") if isinstance(ep, dict) else getattr(ep, "url", None)
        label = ep.get("label") if isinstance(ep, dict) else getattr(ep, "label", f"{part_num}-qism")
        title = f"{base_title} — {part_num}-qism" if base_title and len(episodes) > 1 else (base_title or label)
        if url:
            await set_movie_video(
                session=session,
                code=p_code,
                file_id=url,
                file_type="video",
                title=title
            )
            synced += 1
    return synced


async def delete_movie(session: AsyncSession, code: str) -> bool:
    """Kinoni kod bo'yicha o'chirish."""
    stmt = delete(Movie).where(Movie.code == str(code).strip())
    result = await session.execute(stmt)
    return result.rowcount > 0


async def increment_movie_views(session: AsyncSession, movie_id: int) -> None:
    """Ko'rishlar sonini 1 taga oshirish."""
    stmt = (
        update(Movie)
        .where(Movie.id == movie_id)
        .values(views_count=Movie.views_count + 1)
    )
    await session.execute(stmt)


async def increment_movie_downloads(session: AsyncSession, movie_id: int) -> None:
    """Yuklab olishlar sonini 1 taga oshirish."""
    stmt = (
        update(Movie)
        .where(Movie.id == movie_id)
        .values(downloads_count=Movie.downloads_count + 1)
    )
    await session.execute(stmt)


def _is_placeholder_file_id(file_id: Optional[str]) -> bool:
    """Soxta yoki bo'sh Telegram file_id ekanligini tekshirish."""
    s = (file_id or "").strip()
    return (
        not s
        or s.startswith("BAACAgIAAxkBAAIB_")
        or s.startswith("BAAE_")
        or "_REAL_FID" in s
        or s.endswith("_vid")
    )


async def upsert_movie(
    session: AsyncSession,
    code: str,
    title: str,
    file_id: Optional[str] = None,
    description: Optional[str] = None,
    file_type: str = "video",
    file_size: Optional[int] = None,
    duration: Optional[int] = None,
    genres: str = "Barcha",
    year: Optional[int] = None,
    rating: Optional[float] = None,
    poster_file_id: Optional[str] = None,
    views_count: Optional[int] = None,
    downloads_count: Optional[int] = None,
) -> Tuple[Movie, bool]:
    """Kinoni yaratadi yoki mavjud bo'lsa yangilaydi (upsert). (movie, created) qaytaradi."""
    clean_code = str(code).strip()
    movie = await get_movie_by_code(session, clean_code)
    if movie:
        if title:
            movie.title = title.strip()
        if description is not None:
            movie.description = description.strip() if description else None
        if genres:
            movie.genres = genres.strip()
        if year:
            movie.year = year
        if rating:
            movie.rating = rating
        if poster_file_id:
            movie.poster_file_id = poster_file_id
        if file_id and _is_placeholder_file_id(movie.file_id):
            movie.file_id = file_id.strip()
        if views_count is not None and views_count > movie.views_count:
            movie.views_count = views_count
        if downloads_count is not None and downloads_count > movie.downloads_count:
            movie.downloads_count = downloads_count
        await session.flush()
        return movie, False
    else:
        new_movie = Movie(
            code=clean_code,
            title=title.strip() if title else f"Kino #{clean_code}",
            description=description.strip() if description else None,
            file_id=file_id.strip() if file_id else "",
            file_type=file_type,
            file_size=file_size or (1024 * 1024 * 550),
            duration=duration or (95 * 60),
            genres=genres.strip() if genres else "Kino, Komediya, O'zbek kino",
            year=year or 2024,
            rating=rating or 8.0,
            poster_file_id=poster_file_id,
            views_count=views_count or 150,
            downloads_count=downloads_count or 50,
            created_at=utc_now(),
        )
        try:
            async with session.begin_nested():
                session.add(new_movie)
                await session.flush()
            return new_movie, True
        except IntegrityError:
            # Parallel sinxronizatsiya sababli kino kodi allaqachon yaratilgan
            for _ in range(5):
                movie = await get_movie_by_code(session, clean_code)
                if movie:
                    break
                await asyncio.sleep(0.05)
            if movie:
                if title:
                    movie.title = title.strip()
                if description is not None:
                    movie.description = description.strip() if description else None
                if genres:
                    movie.genres = genres.strip()
                if year:
                    movie.year = year
                if rating:
                    movie.rating = rating
                if poster_file_id:
                    movie.poster_file_id = poster_file_id
                if file_id and _is_placeholder_file_id(movie.file_id):
                    movie.file_id = file_id.strip()
                if views_count is not None and views_count > movie.views_count:
                    movie.views_count = views_count
                if downloads_count is not None and downloads_count > movie.downloads_count:
                    movie.downloads_count = downloads_count
                await session.flush()
                return movie, False
            raise


async def sync_movies_from_catalog_data(
    session: AsyncSession,
    catalog_items: List[Dict[str, Any]]
) -> int:
    """
    Katalog ma'lumotlarini (items list) 'movies' jadvali bilan tezkor sinxronlash.
    Yangi kinolarni kiritadi, mavjudlarining sarlavha, tavsif va statistikasini yangilaydi.
    Haqiqiy file_id larni saqlab qoladi.
    """
    if not catalog_items:
        return 0

    stmt = select(Movie)
    res = await session.execute(stmt)
    existing_movies = {m.code: m for m in res.scalars().all()}

    synced_count = 0
    to_add = []

    for it in catalog_items:
        raw_code = it.get("c")
        if raw_code is None:
            continue
        code = str(raw_code).strip()
        if not code:
            continue

        title = str(it.get("t", f"Kino #{code}")).strip()
        desc = str(it.get("d", "")).strip() or None
        views = int(it.get("v", 150))
        downloads = views // 3
        genres = str(it.get("g") or "Kino, Komediya, O'zbek kino").strip()
        year = int(it.get("y")) if it.get("y") else 2024
        rating = float(it.get("r")) if it.get("r") else 8.0

        if code in existing_movies:
            m = existing_movies[code]
            changed = False
            if title and m.title != title:
                m.title = title
                changed = True
            if desc and m.description != desc:
                m.description = desc
                changed = True
            if views > m.views_count:
                m.views_count = views
                changed = True
            if downloads > m.downloads_count:
                m.downloads_count = downloads
                changed = True
            if changed:
                synced_count += 1
        else:
            new_m = Movie(
                code=code,
                title=title,
                description=desc,
                file_id="",
                file_type="video",
                file_size=1024 * 1024 * 550,
                duration=95 * 60,
                genres=genres,
                year=year,
                rating=rating,
                views_count=views,
                downloads_count=downloads,
                created_at=utc_now(),
            )
            to_add.append(new_m)
            existing_movies[code] = new_m
            synced_count += 1

    if to_add:
        res = session.add_all(to_add)
        if asyncio.iscoroutine(res):
            await res
    await session.commit()
    return synced_count



# ==========================================
# HOMIY KANALLAR (SPONSOR CHANNELS)
# ==========================================

async def add_sponsor_channel(
    session: AsyncSession,
    channel_id: str,
    title: str,
    invite_link: str,
    username: Optional[str] = None,
) -> SponsorChannel:
    """Majburiy obuna kanalini qo'shish."""
    # Agar mavjud bo'lsa yangilash
    stmt = select(SponsorChannel).where(SponsorChannel.channel_id == str(channel_id).strip())
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.title = title.strip()
        existing.invite_link = invite_link.strip()
        if username:
            existing.username = username.strip().lstrip("@")
        existing.is_active = True
        await session.flush()
        return existing

    new_channel = SponsorChannel(
        channel_id=str(channel_id).strip(),
        title=title.strip(),
        username=username.strip().lstrip("@") if username else None,
        invite_link=invite_link.strip(),
        is_active=True,
        created_at=utc_now(),
    )
    session.add(new_channel)
    await session.flush()
    return new_channel


async def remove_sponsor_channel(session: AsyncSession, channel_id: str) -> bool:
    """Majburiy obuna kanalini o'chirish."""
    stmt = delete(SponsorChannel).where(SponsorChannel.channel_id == str(channel_id).strip())
    result = await session.execute(stmt)
    return result.rowcount > 0


async def get_active_sponsor_channels(session: AsyncSession) -> List[SponsorChannel]:
    """Aktiv bo'lgan homiy kanallar ro'yxati."""
    stmt = (
        select(SponsorChannel)
        .where(SponsorChannel.is_active == True)
        .order_by(SponsorChannel.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_all_sponsor_channels(session: AsyncSession) -> List[SponsorChannel]:
    """Barcha homiy kanallar ro'yxati."""
    stmt = select(SponsorChannel).order_by(SponsorChannel.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def toggle_sponsor_channel(session: AsyncSession, channel_id: str, is_active: bool) -> bool:
    """Kanal aktiv holatini yoqish/o'chirish."""
    stmt = (
        update(SponsorChannel)
        .where(SponsorChannel.channel_id == str(channel_id).strip())
        .values(is_active=is_active)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


# ==========================================
# YUKLAB OLISH STATISTIKASI (DOWNLOAD LOGS)
# ==========================================

async def log_download(
    session: AsyncSession,
    user_id: int,
    platform: str,
    query_or_url: Optional[str] = None,
) -> DownloadLog:
    """Yuklab olish amalini qayd qilish."""
    log = DownloadLog(
        user_id=user_id,
        platform=platform.lower(),
        query_or_url=query_or_url,
        created_at=utc_now(),
    )
    session.add(log)
    await session.flush()
    return log


async def get_total_downloads_count(session: AsyncSession) -> int:
    """Jami yuklamalar soni."""
    stmt = select(func.count(DownloadLog.id))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_downloads_stats_by_platform(session: AsyncSession) -> Dict[str, int]:
    """Platformalar bo'yicha yuklamalar statistikasi."""
    stmt = (
        select(DownloadLog.platform, func.count(DownloadLog.id))
        .group_by(DownloadLog.platform)
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.fetchall()}


async def prune_old_download_logs(session: AsyncSession, days: int = 30) -> int:
    """Belgilangan kundan (default 30 kun) eski download_logs yozuvlarini o'chirish."""
    cutoff = utc_now() - timedelta(days=days)
    stmt = delete(DownloadLog).where(DownloadLog.created_at < cutoff)
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount or 0


# ==========================================
# BOT SOZLAMALARI (BOT SETTINGS)
# ==========================================

async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    """Bot sozlamasini olish."""
    stmt = select(BotSetting.value).where(BotSetting.key == key)
    result = await session.execute(stmt)
    val = result.scalar_one_or_none()
    return val if val is not None else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    """Bot sozlamasini saqlash yoki yangilash."""
    stmt = select(BotSetting).where(BotSetting.key == key)
    result = await session.execute(stmt)
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = str(value)
    else:
        new_setting = BotSetting(key=key, value=str(value))
        session.add(new_setting)
    await session.flush()


# ==========================================
# REFERALLAR (REFERRALS)
# ==========================================

async def add_referral(
    session: AsyncSession,
    referrer_id: int,
    new_user_id: int,
    points: int = 10
) -> bool:
    """Yangi foydalanuvchini taklif qilgan odamga referal ball va hisob yozish."""
    if referrer_id == new_user_id:
        return False

    stmt = select(User).where(User.id == new_user_id)
    res = await session.execute(stmt)
    new_user = res.scalar_one_or_none()

    if not new_user or new_user.referred_by is not None:
        return False

    stmt_ref = select(User).where(User.id == referrer_id)
    res_ref = await session.execute(stmt_ref)
    referrer = res_ref.scalar_one_or_none()

    if not referrer:
        return False

    new_user.referred_by = referrer_id
    referrer.referral_count = (referrer.referral_count or 0) + 1
    referrer.referral_points = (referrer.referral_points or 0) + points
    await session.flush()
    return True


async def get_referral_stats(session: AsyncSession, user_id: int) -> Tuple[int, int]:
    """Foydalanuvchining taklif qilgan do'stlari soni va to'plagan ballarini qaytaradi."""
    stmt = select(User.referral_count, User.referral_points).where(User.id == user_id)
    res = await session.execute(stmt)
    row = res.fetchone()
    if not row:
        return (0, 0)
    return (row[0] or 0, row[1] or 0)


# ==========================================
# ANONIM SAVOLLAR VA XABARLAR
# ==========================================

async def create_anonymous_message(
    session: AsyncSession,
    sender_id: int,
    recipient_id: int,
    text: str
) -> AnonymousMessage:
    """Yangi anonim xabar yaratish."""
    msg = AnonymousMessage(
        sender_id=sender_id,
        recipient_id=recipient_id,
        message_text=text.strip(),
        created_at=utc_now(),
    )
    session.add(msg)
    await session.flush()
    return msg


async def get_anonymous_message(session: AsyncSession, msg_id: int) -> Optional[AnonymousMessage]:
    """ID bo'yicha anonim xabarni olish."""
    stmt = select(AnonymousMessage).where(AnonymousMessage.id == msg_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


_ANON_TOKEN_ALPHABET = string.ascii_letters + string.digits


def generate_anon_token(length: int = 10) -> str:
    """Anonim savollar uchun kriptografik noyob havola tokeni yaratish (masalan: sWSam9ZaAU)."""
    return "".join(secrets.choice(_ANON_TOKEN_ALPHABET) for _ in range(length))


async def _allocate_unique_anon_token(session: AsyncSession, exclude_token: Optional[str] = None) -> str:
    for _ in range(8):
        cand = generate_anon_token(10)
        if exclude_token and cand == exclude_token:
            continue
        exists_stmt = select(AnonQuestionProfile.user_id).where(AnonQuestionProfile.token == cand)
        res = await session.execute(exists_stmt)
        if res.scalar_one_or_none() is None:
            return cand
    return generate_anon_token(12)


async def get_or_create_anon_profile(session: AsyncSession, user_id: int) -> AnonQuestionProfile:
    """Foydalanuvchining anonim savollar profilini olish yoki yangisini yaratish."""
    stmt = select(AnonQuestionProfile).where(AnonQuestionProfile.user_id == int(user_id))
    res = await session.execute(stmt)
    prof = res.scalar_one_or_none()
    if prof:
        return prof

    token = await _allocate_unique_anon_token(session)
    prof = AnonQuestionProfile(
        user_id=int(user_id),
        token=token,
        is_accepting=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(prof)
    try:
        async with session.begin_nested():
            await session.flush()
        return prof
    except IntegrityError:
        res2 = await session.execute(stmt)
        existing = res2.scalar_one_or_none()
        if existing:
            return existing
        raise


async def regenerate_anon_token(session: AsyncSession, user_id: int) -> AnonQuestionProfile:
    """Eski havolani bekor qilib yangi noyob anonim savol tokenini yaratish."""
    prof = await get_or_create_anon_profile(session, user_id)
    new_token = await _allocate_unique_anon_token(session, exclude_token=prof.token)
    prof.token = new_token
    prof.updated_at = utc_now()
    await session.flush()
    return prof


async def set_anon_accepting(session: AsyncSession, user_id: int, accepting: bool) -> AnonQuestionProfile:
    """Anonim savollar qabul qilish holatini (yoqilgan / to'xtatilgan) yangilash."""
    prof = await get_or_create_anon_profile(session, user_id)
    prof.is_accepting = bool(accepting)
    prof.updated_at = utc_now()
    await session.flush()
    return prof


async def resolve_anon_target(session: AsyncSession, raw_token: str) -> Optional[Tuple[int, bool]]:
    """?start=q_<token> dan qabul qiluvchi user_id va qabul holatini aniqlash."""
    clean = str(raw_token or "").strip()
    if clean.startswith("q_"):
        clean = clean[2:].strip()
    if not clean or len(clean) > 32:
        return None

    stmt = select(AnonQuestionProfile).where(AnonQuestionProfile.token == clean)
    res = await session.execute(stmt)
    prof = res.scalar_one_or_none()
    if prof:
        return (int(prof.user_id), bool(prof.is_accepting))

    # Eski q_<user_id> formati faqat profil/token hali yaratilmagan foydalanuvchilar uchun ishlaydi
    if clean.isdigit():
        uid = int(clean)
        prof_stmt = select(AnonQuestionProfile.user_id).where(AnonQuestionProfile.user_id == uid)
        existing_prof = (await session.execute(prof_stmt)).scalar_one_or_none()
        if existing_prof is None:
            user_obj = await get_user(session, uid)
            if user_obj:
                return (uid, True)
    return None


async def get_anon_stats(session: AsyncSession, user_id: int) -> Tuple[int, int]:
    """Qabul qilingan savollar soni va bloklangan yuboruvchilar sonini qaytarish."""
    uid = int(user_id)
    recv_stmt = select(func.count(AnonymousMessage.id)).where(AnonymousMessage.recipient_id == uid)
    blk_stmt = select(func.count(AnonBlockedSender.id)).where(AnonBlockedSender.recipient_id == uid)
    recv_count = int((await session.execute(recv_stmt)).scalar() or 0)
    blk_count = int((await session.execute(blk_stmt)).scalar() or 0)
    return (recv_count, blk_count)


async def is_anon_sender_blocked(session: AsyncSession, recipient_id: int, sender_id: int) -> bool:
    """Yuboruvchi qabul qiluvchi tomonidan bloklanganligini tekshirish."""
    stmt = select(AnonBlockedSender.id).where(
        AnonBlockedSender.recipient_id == int(recipient_id),
        AnonBlockedSender.sender_id == int(sender_id),
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none() is not None


async def block_anon_sender(session: AsyncSession, recipient_id: int, sender_id: int) -> bool:
    """Anonim yuboruvchini bloklash. Yangi blok qo'shilsa True qaytaradi."""
    rec_id, snd_id = int(recipient_id), int(sender_id)
    if await is_anon_sender_blocked(session, rec_id, snd_id):
        return False
    row = AnonBlockedSender(recipient_id=rec_id, sender_id=snd_id, created_at=utc_now())
    session.add(row)
    try:
        async with session.begin_nested():
            await session.flush()
        return True
    except IntegrityError:
        return False


async def unblock_anon_sender(session: AsyncSession, recipient_id: int, sender_id: int) -> bool:
    """Bloklangan anonim yuboruvchini blokdan chiqarish."""
    stmt = delete(AnonBlockedSender).where(
        AnonBlockedSender.recipient_id == int(recipient_id),
        AnonBlockedSender.sender_id == int(sender_id),
    )
    res = await session.execute(stmt)
    await session.flush()
    return (res.rowcount or 0) > 0


# ==========================================
# FIKR VA SHIKOYATLAR (FEEDBACK)
# ==========================================

async def create_feedback(
    session: AsyncSession,
    user_id: int,
    username: Optional[str],
    message: str
) -> Feedback:
    """Foydalanuvchi fikrini saqlash."""
    fb = Feedback(
        user_id=user_id,
        username=username,
        message=message.strip(),
        created_at=utc_now(),
    )
    session.add(fb)
    await session.flush()
    return fb


# ==========================================
# AQLLI QIDIRUV (SMART SEARCH: LOTIN + KIRILL)
# ==========================================

async def smart_search_movies(
    session: AsyncSession,
    query: str,
    limit: int = 20,
    offset: int = 0
) -> List[Movie]:
    """
    Kino nomi, janri va tavsifi bo'yicha Lotin hamda Kirill yozuvlarida aqlli qidiruv.
    Masalan: 'forsaj' -> 'Forsaj' va 'Форсаж' ikkalasini ham topadi.
    """
    clean_q = query.strip()
    if not clean_q:
        return await get_all_movies(session, limit=limit, offset=offset)

    # Agar raqam bo'lsa (kino kodi)
    if clean_q.isdigit():
        movie_by_code = await get_movie_by_code(session, clean_q)
        if movie_by_code:
            return [movie_by_code]

    lat_q, cyr_q = get_both_scripts(clean_q)
    pat_orig = f"%{clean_q}%"
    pat_lat = f"%{lat_q}%"
    pat_cyr = f"%{cyr_q}%"

    conditions = [
        Movie.title.ilike(pat_orig),
        Movie.title.ilike(pat_lat),
        Movie.title.ilike(pat_cyr),
        Movie.description.ilike(pat_orig),
        Movie.description.ilike(pat_lat),
        Movie.description.ilike(pat_cyr),
        Movie.genres.ilike(pat_orig),
        Movie.genres.ilike(pat_lat),
        Movie.genres.ilike(pat_cyr),
    ]

    stmt = (
        select(Movie)
        .where(or_(*conditions))
        .order_by(desc(Movie.views_count), desc(Movie.rating))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ==========================================
# 💰 RASXOD (EXPENSE TRACKER)
# ==========================================

EXPENSE_CATEGORIES_META = [
    {"c": "food", "n": "Oziq-ovqat", "e": "🍔", "col": "#FF6B6B"},
    {"c": "transport", "n": "Transport", "e": "🚕", "col": "#4D96FF"},
    {"c": "communal", "n": "Kommunal", "e": "💡", "col": "#FFD93D"},
    {"c": "shopping", "n": "Xaridlar", "e": "🛍", "col": "#6BCB77"},
    {"c": "family", "n": "Oila", "e": "👨‍👩‍👧", "col": "#9D4EDD"},
    {"c": "other", "n": "Boshqa", "e": "📦", "col": "#9AA0B4"},
]

CATEGORY_MAP = {c["c"]: c for c in EXPENSE_CATEGORIES_META}


def detect_expense_category(text: str) -> str:
    """Xarajat matniga qarab toifani aniqlaydi."""
    t = text.lower()
    if any(w in t for w in ["non", "osh", "choy", "suv", "tushlik", "obed", "kechki", "go'sht", "gosht", "somsa", "shashlik", "market", "kola", "qahva", "kofe", "kafe", "restoran", "ovqat", "lavash", "donar", "shirinlik", "nonushta", "pishiriq"]):
        return "food"
    if any(w in t for w in ["taksi", "benzin", "metan", "propan", "avtobus", "metro", "yandeks", "yandex", "yo'lkira", "yolkira", "zapravka", "moy", "propan", "mashina", "parkovka"]):
        return "transport"
    if any(w in t for w in ["svet", "gaz", "issiqlik", "wifi", "internet", "kommunal", "musor", "kvartira", "ijara", "uy"]):
        return "communal"
    if any(w in t for w in ["kiyim", "oyoq", "poyabzal", "bozor", "magazin", "telefon", "noutbuk", "texnika", "aptek", "dori", "parfum", "kitob"]):
        return "shopping"
    if any(w in t for w in ["dadam", "onam", "ota", "ona", "bola", "bog'cha", "bogcha", "maktab", "repititor", "kurs", "to'y", "toy", "ehson", "sovg'a", "sovga", "xotin", "singlim", "ukam", "aka"]):
        return "family"
    return "other"


def parse_expense_text(text: str) -> List[Dict[str, Any]]:
    """
    Foydalanuvchi yozgan tabiiy matndan xarajatlarni ajratadi.
    Masalan: «non 8 ming, taksi 25000», «obedga 45 ming ketdi»
    """
    items = []
    # Vergul, nuqta-vergul, 'va' bog'lovchisi yoki yangi qator bilan ajratish
    chunks = re.split(r'[,;\n]+|\s+va\s+', text, flags=re.IGNORECASE)
    for chunk in chunks:
        ch = chunk.strip()
        if not ch:
            continue

        # Raqamlarni aniqlash
        # «8 ming», «25k», «120 000», «1.5 mln»
        m_mln = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:mln|million)\b', ch, re.IGNORECASE)
        m_ming = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:ming|k)\b', ch, re.IGNORECASE)
        m_digits = re.search(r'(\d[\d\s\.,]*\d|\d+)', ch)

        amount = 0
        if m_mln:
            val_str = m_mln.group(1).replace(",", ".")
            amount = int(float(val_str) * 1_000_000)
            note = ch[:m_mln.start()] + ch[m_mln.end():]
        elif m_ming:
            val_str = m_ming.group(1).replace(",", ".")
            amount = int(float(val_str) * 1_000)
            note = ch[:m_ming.start()] + ch[m_ming.end():]
        elif m_digits:
            clean_digits = re.sub(r'[\s\.,]', '', m_digits.group(1))
            if clean_digits.isdigit():
                amount = int(clean_digits)
            note = ch[:m_digits.start()] + ch[m_digits.end():]
        else:
            continue

        if amount <= 0 or amount > 1_000_000_000:
            continue

        # Noteni tozalash
        note = re.sub(r'\b(?:som|so\'m|uzs|ketdi|berdim|sarf|boldi|bo\'ldi|ga)\b', '', note, flags=re.IGNORECASE).strip()
        note = re.sub(r'\s+', ' ', note)
        if not note:
            note = "Xarajat"

        category = detect_expense_category(f"{note} {ch}")
        cat_info = CATEGORY_MAP.get(category, CATEGORY_MAP["other"])
        items.append({
            "a": amount,
            "n": note[:80],
            "c": category,
            "e": cat_info["e"],
        })
    return items


async def add_expense(
    session: AsyncSession,
    user_id: int,
    amount: int,
    note: str,
    category: Optional[str] = None,
    date: Optional[str] = None,
    date_str: Optional[str] = None,
    source: str = "t",
) -> Expense:
    """Xarajat qo'shish."""
    d_val = date or date_str or datetime.now().strftime("%Y-%m-%d")
    if not category:
        category = detect_expense_category(note)

    expense = Expense(
        user_id=user_id,
        amount=amount,
        note=note,
        category=category,
        date=d_val,
        source=source,
    )
    session.add(expense)
    await session.flush()
    return expense


async def get_expenses(
    session: AsyncSession,
    user_id: int,
    month: Optional[str] = None,
    category: Optional[str] = None,
    before_id: Optional[int] = None,
    limit: int = 60,
) -> List[Expense]:
    """Xarajatlar ro'yxatini olish."""
    stmt = select(Expense).where(Expense.user_id == user_id)
    if month:
        stmt = stmt.where(Expense.date.startswith(month))
    if category:
        stmt = stmt.where(Expense.category == category)
    if before_id:
        stmt = stmt.where(Expense.id < before_id)
    stmt = stmt.order_by(desc(Expense.date), desc(Expense.id)).limit(limit)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_expense_by_id(session: AsyncSession, expense_id: int, user_id: int) -> Optional[Expense]:
    """Bitta xarajatni ID bo'yicha olish."""
    stmt = select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def edit_expense(
    session: AsyncSession,
    expense_id: int,
    user_id: int,
    amount: int,
    note: str,
    date: str,
    category: Optional[str] = None,
) -> bool:
    """Xarajatni tahrirlash."""
    exp = await get_expense_by_id(session, expense_id, user_id)
    if not exp:
        return False
    exp.amount = amount
    exp.note = note
    exp.date = date
    if category:
        exp.category = category
    await session.flush()
    return True


async def delete_expense(session: AsyncSession, expense_id: int, user_id: int) -> bool:
    """Xarajatni o'chirish."""
    exp = await get_expense_by_id(session, expense_id, user_id)
    if not exp:
        return False
    await session.delete(exp)
    await session.flush()
    return True


async def set_expense_budget(session: AsyncSession, user_id: int, month: str, amount: int) -> ExpenseBudget:
    """Oylik byudjet o'rnatish."""
    stmt = select(ExpenseBudget).where(ExpenseBudget.user_id == user_id, ExpenseBudget.month == month)
    res = await session.execute(stmt)
    b = res.scalar_one_or_none()
    if b:
        b.amount = amount
    else:
        b = ExpenseBudget(user_id=user_id, month=month, amount=amount)
        session.add(b)
    await session.flush()
    return b


async def get_expense_budget(session: AsyncSession, user_id: int, month: str) -> Optional[int]:
    """Oylik byudjet miqdorini olish."""
    stmt = select(ExpenseBudget.amount).where(ExpenseBudget.user_id == user_id, ExpenseBudget.month == month)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_monthly_expense_summary(
    session: AsyncSession,
    user_id: int,
    year_month: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mini App rasxod.js uchun to'liq oylik xarajatlar tahlili:
    Donut chart, by_day hisobot, kategoriyalar taqsimoti, byudjet, top xarajat.
    """
    now = datetime.now()
    if not year_month:
        year_month = now.strftime("%Y-%m")

    y, m = map(int, year_month.split("-"))
    today_iso = now.strftime("%Y-%m-%d")
    is_current_month = (y == now.year and m == now.month)

    # 1. Ushbu oydagi barcha xarajatlar
    stmt = select(Expense).where(Expense.user_id == user_id, Expense.date.startswith(year_month))
    res = await session.execute(stmt)
    expenses = list(res.scalars().all())

    # 2. O'tgan oydagi umumiy xarajat
    prev_y = y if m > 1 else y - 1
    prev_m = m - 1 if m > 1 else 12
    prev_ym = f"{prev_y}-{prev_m:02d}"
    prev_stmt = select(func.sum(Expense.amount)).where(Expense.user_id == user_id, Expense.date.startswith(prev_ym))
    prev_res = await session.execute(prev_stmt)
    prev_total = prev_res.scalar() or 0

    # 3. Hisoblashlar
    total = sum(x.amount for x in expenses)
    by_day: Dict[str, int] = {}
    cat_sums: Dict[str, int] = {}
    cat_counts: Dict[str, int] = {}
    top_item: Optional[Expense] = None

    today_total = 0
    for x in expenses:
        by_day[x.date] = by_day.get(x.date, 0) + x.amount
        cat_sums[x.category] = cat_sums.get(x.category, 0) + x.amount
        cat_counts[x.category] = cat_counts.get(x.category, 0) + 1
        if x.date == today_iso:
            today_total += x.amount
        if not top_item or x.amount > top_item.amount:
            top_item = x

    # Kunlik o'rtacha
    days_count = now.day if is_current_month else 30
    avg_daily = int(total / max(1, days_count))

    # Foiz o'zgarishi
    change = None
    if prev_total > 0:
        change = round(((total - prev_total) / prev_total) * 100, 1)

    # Kategoriyalar ro'yxati (eng kattasidan boshlab)
    cats_list = []
    for c_meta in EXPENSE_CATEGORIES_META:
        cid = c_meta["c"]
        s_val = cat_sums.get(cid, 0)
        if s_val > 0 or len(expenses) == 0:
            pct = round((s_val / total * 100)) if total > 0 else 0
            cats_list.append({
                "c": cid,
                "n": c_meta["n"],
                "e": c_meta["e"],
                "col": c_meta["col"],
                "s": s_val,
                "p": pct,
                "k": cat_counts.get(cid, 0),
                "prev": None,
            })
    cats_list.sort(key=lambda x: x["s"], reverse=True)

    # Byudjet
    budget_val = await get_expense_budget(session, user_id, year_month)

    # Max day
    max_day_item = None
    if by_day:
        best_d = max(by_day.keys(), key=lambda d: by_day[d])
        max_day_item = {"day": best_d, "s": by_day[best_d]}

    top_dict = None
    if top_item:
        cat_info = CATEGORY_MAP.get(top_item.category, CATEGORY_MAP["other"])
        top_dict = {
            "e": cat_info["e"],
            "note": top_item.note,
            "a": top_item.amount,
            "day": top_item.date,
        }

    advice = "Xarajatlaringiz nazorat ostida! Oylik byudjetingizga amal qiling."
    if budget_val and total > budget_val:
        advice = f"Diqqat: Oylik byudjetingizdan {total - budget_val:,} so'm oshib ketdi."

    return {
        "ok": True,
        "m": m,
        "y": y,
        "cur": is_current_month,
        "days": days_count,
        "today_iso": today_iso,
        "total": total,
        "spent": total,
        "budget": budget_val or 0,
        "today": today_total,
        "avg": avg_daily,
        "change": change,
        "n": len(expenses),
        "active_days": len(by_day),
        "advice": advice,
        "by_day": by_day,
        "cats": cats_list,
        "meta": EXPENSE_CATEGORIES_META,
        "top": top_dict,
        "max_day": max_day_item,
        "prev": prev_total,
    }


# ==========================================
# 🥗 KALORIYA (NUTRITION & CALORIE TRACKER)
# ==========================================

async def get_calorie_profile(session: AsyncSession, user_id: int) -> Optional[UserCalorieProfile]:
    """Foydalanuvchi kaloriya profilini olish."""
    stmt = select(UserCalorieProfile).where(UserCalorieProfile.user_id == user_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def upsert_calorie_profile(
    session: AsyncSession,
    user_id: int,
    sex: str = "f",
    age: int = 25,
    height: float = 170.0,
    weight: float = 70.0,
    target_weight: float = 65.0,
    months: int = 3,
    activity: int = 3,
    goal: str = "lose",
    force: bool = False,
) -> UserCalorieProfile:
    """Kaloriya profilini yaratish yoki yangilash."""
    p = await get_calorie_profile(session, user_id)
    if not p:
        p = UserCalorieProfile(
            user_id=user_id,
            sex=sex,
            age=age,
            height=height,
            weight=weight,
            target_weight=target_weight,
            months=months,
            activity=activity,
            goal=goal,
            force=force,
            is_pro=True,
            pro_until=datetime.now() + timedelta(days=365),
        )
        session.add(p)
    else:
        p.sex = sex
        p.age = age
        p.height = height
        p.weight = weight
        p.target_weight = target_weight
        p.months = months
        p.activity = activity
        p.goal = goal
        p.force = force
        p.is_pro = True
    await session.flush()
    return p


def calculate_calorie_plan(
    sex: str,
    age: int,
    height: float,
    weight: float,
    target_weight: float,
    months: int = 3,
    activity: int = 3,
    goal: str = "lose",
    force: bool = False,
) -> Dict[str, Any]:
    """
    Mifflin–St Jeor formulasi asosida kunlik kaloriya va makronutrientlar rejasini hisoblash.
    """
    # 1. BMR (Basal Metabolic Rate)
    if sex.lower() == "m":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # 2. Faollik koeffitsienti
    act_mult = {1: 1.2, 3: 1.55, 4: 1.725}.get(activity, 1.55)
    tdee = bmr * act_mult

    # 3. Maqsadga moslashtirish
    diff = abs(weight - target_weight)
    min_months = max(1, round(diff / 3.5)) if diff > 0 else 1

    floor_kcal = 1500 if sex.lower() == "m" else 1200
    if goal == "lose":
        target_kcal = tdee - 500
        pace = -0.5
        status = "ok" if (months >= min_months or not months) else ("tight" if months >= min_months - 1 else "forced" if force else "no")
    elif goal == "gain":
        target_kcal = tdee + 400
        pace = 0.4
        status = "ok"
    else:
        target_kcal = tdee
        pace = 0.0
        status = "ok"

    if status == "forced":
        target_kcal = max(floor_kcal, tdee - 750 if goal == "lose" else tdee + 600)

    final_kcal = max(floor_kcal, int(round(target_kcal)))
    bmi = round(weight / ((height / 100) ** 2), 1) if height > 0 else 22.0

    # Makrolar (Oqsil, Yog', Uglevod)
    p_g = int(round(weight * (1.8 if goal == "lose" else 1.6)))
    f_g = int(round(weight * 0.9))
    c_kcal = max(0, final_kcal - (p_g * 4 + f_g * 9))
    c_g = int(round(c_kcal / 4))

    # Suv normasi (ml)
    water_ml = int(round(weight * 35))

    weeks = max(1, int(round((months or min_months) * 4.345)))
    expect = diff if status in ("ok", "tight") else min(diff, round((months or 1) * 3.0, 1))

    return {
        "kcal": final_kcal,
        "bmr": int(round(bmr)),
        "tdee": int(round(tdee)),
        "bmi": bmi,
        "water": water_ml,
        "pace": pace,
        "note": "teen" if age < 18 else ("under" if bmi < 18.5 else ""),
        "plan": {
            "target": target_weight,
            "weeks": weeks,
            "status": status,
            "diff": round(diff, 1),
            "months": months or min_months,
            "expect": expect,
            "min_months": min_months,
            "active_months": max(1, min_months - 1),
            "floor": floor_kcal,
            "healthy": [round(18.5 * ((height / 100) ** 2), 1), round(24.9 * ((height / 100) ** 2), 1)],
        },
        "meals": [
            {"k": "b", "e": "🌅", "kcal": int(round(final_kcal * 0.25))},
            {"k": "l", "e": "☀️", "kcal": int(round(final_kcal * 0.35))},
            {"k": "s", "e": "🍎", "kcal": int(round(final_kcal * 0.15))},
            {"k": "d", "e": "🌙", "kcal": int(round(final_kcal * 0.25))},
        ],
        "macro": {"p": p_g, "f": f_g, "c": c_g},
    }


async def add_calorie_log_item(
    session: AsyncSession,
    user_id: int,
    date: str,
    meal: str,
    name: str,
    grams: int,
    kcal: int,
    protein: float,
    fat: float,
    carbs: float,
    source: str = "p",
) -> CalorieLogItem:
    """Kunlik taom yozuvini qo'shish."""
    item = CalorieLogItem(
        user_id=user_id,
        date=date,
        meal=meal,
        name=name,
        grams=grams,
        kcal=kcal,
        protein=protein,
        fat=fat,
        carbs=carbs,
        source=source,
    )
    session.add(item)
    await session.flush()
    return item


async def get_daily_calorie_log(
    session: AsyncSession,
    user_id: int,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Kunlik kaloriya va makronutrientlar hisobi."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    stmt = select(CalorieLogItem).where(CalorieLogItem.user_id == user_id, CalorieLogItem.date == date).order_by(CalorieLogItem.id)
    res = await session.execute(stmt)
    items = list(res.scalars().all())

    eaten = sum(x.kcal for x in items)
    by_meal: Dict[str, int] = {}
    tot_p = sum(x.protein for x in items)
    tot_f = sum(x.fat for x in items)
    tot_c = sum(x.carbs for x in items)

    items_list = []
    for x in items:
        by_meal[x.meal] = by_meal.get(x.meal, 0) + x.kcal
        items_list.append({
            "id": x.id,
            "m": x.meal,
            "n": x.name,
            "g": x.grams,
            "kcal": x.kcal,
            "p": int(round(x.protein)),
            "f": int(round(x.fat)),
            "c": int(round(x.carbs)),
            "src": x.source,
        })

    return {
        "eaten": eaten,
        "items": items_list,
        "by_meal": by_meal,
        "macro": {"p": int(round(tot_p)), "f": int(round(tot_f)), "c": int(round(tot_c))},
    }


async def delete_calorie_log_item(session: AsyncSession, item_id: int, user_id: int) -> bool:
    """Taom yozuvini o'chirish."""
    stmt = select(CalorieLogItem).where(CalorieLogItem.id == item_id, CalorieLogItem.user_id == user_id)
    res = await session.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        return False
    await session.delete(item)
    await session.flush()
    return True


# ==========================================
# 🕵️ MAFIA GAME STATS & STORAGE
# ==========================================

async def record_mafia_game(
    session: AsyncSession,
    room_id: str,
    winner: str,
    total_players: int = 0,
    days_count: int = 0,
) -> MafiaGameRecord:
    """Mafia o'yin yakunini saqlash."""
    rec = MafiaGameRecord(
        room_id=room_id,
        winner=winner,
        total_players=total_players,
        days_count=days_count,
    )
    session.add(rec)
    await session.flush()
    return rec


async def prune_old_game_records(session: AsyncSession, days: int = 60) -> int:
    """Belgilangan kundan (default 60 kun) eski mafia_game_records yozuvlarini o'chirish."""
    cutoff = utc_now() - timedelta(days=days)
    stmt = delete(MafiaGameRecord).where(MafiaGameRecord.created_at < cutoff)
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount or 0


