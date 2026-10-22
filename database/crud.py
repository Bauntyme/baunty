"""
Ma'lumotlar bazasi bilan ishlash funksiyalari (CRUD)
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, update, delete, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Movie, SponsorChannel, DownloadLog, BotSetting, AnonymousMessage, Feedback, utc_now
from utils.translit import get_both_scripts


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
        session.add(new_user)
        await session.flush()
        return new_user, True


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    """Foydalanuvchini ID bo'yicha olish."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_user_activity(session: AsyncSession, user_id: int) -> None:
    """Foydalanuvchining so'nggi faollik vaqtini yangilash."""
    stmt = update(User).where(User.id == user_id).values(last_active=utc_now())
    await session.execute(stmt)


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
    if not fid_str or fid_str.startswith("<"):
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
        return movie

    if fid_str:
        movie.file_id = fid_str
    movie.file_type = file_type
    if title:
        movie.title = title.strip()
    if dur_val is not None:
        movie.duration = dur_val
    if fsize_val is not None:
        movie.file_size = fsize_val
    await session.flush()
    return movie


async def sync_movie_asilmedia_parts(
    session: AsyncSession,
    code: str,
    episodes: Dict[int, Any],
    base_title: Optional[str] = None
) -> int:
    """
    Asilmedia dan olingan barcha qismlarni (1..N) bazaga 'code_part' ko'rinishida saqlash.
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
        if file_id and (not movie.file_id or movie.file_id.startswith("BAACAgIAAxkBAAIB_")):
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
            file_id=file_id.strip() if file_id else f"BAACAgIAAxkBAAIB_mov_{clean_code}_vid",
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
        session.add(new_movie)
        await session.flush()
        return new_movie, True


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
                file_id=f"BAACAgIAAxkBAAIB_mov_{code}_vid",
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

