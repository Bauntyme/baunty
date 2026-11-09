"""
Database CRUD funksiyalari testi (Async SQLite in-memory)
"""
import os
import asyncio
import tempfile
from datetime import timedelta
import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool
from database.models import Base, DownloadLog, MafiaGameRecord, utc_now
from database import crud
from database.session import execute_incremental_vacuum, execute_wal_checkpoint, engine as app_engine



@pytest_asyncio.fixture
async def async_session():
    """In-memory SQLite testi uchun alohida session fixture."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_user_crud(async_session: AsyncSession):
    # 1. Yaratish
    user, created = await crud.get_or_create_user(
        session=async_session,
        user_id=12345678,
        username="test_user",
        first_name="Test",
        last_name="User"
    )
    await async_session.commit()
    assert created is True
    assert user.id == 12345678

    # 2. Mavjud foydalanuvchini olish
    user2, created2 = await crud.get_or_create_user(
        session=async_session,
        user_id=12345678,
        username="updated_user"
    )
    await async_session.commit()
    assert created2 is False
    assert user2.username == "updated_user"

    # 3. Foydalanuvchilar soni
    count = await crud.get_total_users_count(async_session)
    assert count == 1

    # 4. Ban qilish
    await crud.set_user_ban_status(async_session, 12345678, True)
    await async_session.commit()
    assert await crud.is_user_banned(async_session, 12345678) is True


@pytest.mark.asyncio
async def test_movie_crud(async_session: AsyncSession):
    # 1. Kino yaratish
    movie = await crud.create_movie(
        session=async_session,
        code="101",
        title="Avatar 2",
        file_id="BAACAgIAAxkBAAE...",
        description="Pandora olami",
        genres="Fantastika, Sarguzasht",
        year=2022,
        rating=7.8
    )
    await async_session.commit()
    assert movie.code == "101"
    assert movie.title == "Avatar 2"

    # 2. Kod orqali olish
    found = await crud.get_movie_by_code(async_session, "101")
    assert found is not None
    assert found.title == "Avatar 2"

    # 3. Nomi bo'yicha qidirish
    search_res = await crud.search_movies_by_title(async_session, "Avatar")
    assert len(search_res) == 1
    assert search_res[0].code == "101"

    # 4. Janr bo'yicha olish va sanash
    genre_res = await crud.get_movies_by_genre(async_session, "Fantastika")
    assert len(genre_res) == 1
    genre_cnt = await crud.get_movies_by_genre_count(async_session, "Fantastika")
    assert genre_cnt == 1

    # 5. Tahrirlash (update_movie)
    updated = await crud.update_movie(async_session, "101", title="Avatar: Suv Yo'li", year=2023)
    await async_session.commit()
    assert updated is not None
    assert updated.title == "Avatar: Suv Yo'li"
    assert updated.year == 2023

    # 6. Ko'rishlar sonini oshirish
    await crud.increment_movie_views(async_session, movie.id)
    await async_session.commit()
    updated_movie = await crud.get_movie_by_code(async_session, "101")
    assert updated_movie.views_count == 1

    # 7. O'chirish
    deleted = await crud.delete_movie(async_session, "101")
    await async_session.commit()
    assert deleted is True
    assert await crud.get_movie_by_code(async_session, "101") is None


@pytest.mark.asyncio
async def test_sponsor_channel_crud(async_session: AsyncSession):
    # 1. Kanal qo'shish
    ch = await crud.add_sponsor_channel(
        session=async_session,
        channel_id="-100123456789",
        title="Baunty Films",
        invite_link="https://t.me/BauntyFilms"
    )
    await async_session.commit()
    assert ch.channel_id == "-100123456789"

    # 2. Faol kanallarni olish
    active = await crud.get_active_sponsor_channels(async_session)
    assert len(active) == 1

    # 3. Toggle qilish
    await crud.toggle_sponsor_channel(async_session, "-100123456789", False)
    await async_session.commit()
    active_after = await crud.get_active_sponsor_channels(async_session)
    assert len(active_after) == 0

    # 4. O'chirish
    await crud.remove_sponsor_channel(async_session, "-100123456789")
    await async_session.commit()
    all_ch = await crud.get_all_sponsor_channels(async_session)
    assert len(all_ch) == 0


@pytest.mark.asyncio
async def test_anonymous_message_and_feedback_crud(async_session: AsyncSession):
    """Anonim xabar va fikr-mulohazalar CRUD amallari testi."""
    # Anonim xabar yaratish
    msg = await crud.create_anonymous_message(
        session=async_session,
        sender_id=111,
        recipient_id=222,
        text="Salom, bu test anonim xabar!"
    )
    await async_session.commit()
    assert msg.id is not None
    assert msg.sender_id == 111
    assert msg.recipient_id == 222
    assert "test anonim" in msg.message_text

    # Xabarni olish
    fetched = await crud.get_anonymous_message(async_session, msg.id)
    assert fetched is not None
    assert fetched.message_text == msg.message_text

    # Feedback yaratish
    fb = await crud.create_feedback(
        session=async_session,
        user_id=111,
        username="test_author",
        message="Yaxshi bot ekan, rahmat!"
    )
    await async_session.commit()
    assert fb.id is not None
    assert fb.user_id == 111
    assert "Yaxshi bot" in fb.message


@pytest.mark.asyncio
async def test_storage_maintenance_prune_download_logs(async_session: AsyncSession):
    """30 kundan eski download loglarini tozalash testi."""
    now = utc_now()
    old_log = await crud.log_download(async_session, 101, "youtube", "https://youtube.com/watch?v=1")
    old_log.created_at = now - timedelta(days=45)
    recent_log = await crud.log_download(async_session, 102, "instagram", "https://instagram.com/p/2")
    recent_log.created_at = now - timedelta(days=5)
    await async_session.commit()

    pruned_count = await crud.prune_old_download_logs(async_session, days=30)
    await async_session.commit()
    assert pruned_count == 1

    remaining_count = await crud.get_total_downloads_count(async_session)
    assert remaining_count == 1


@pytest.mark.asyncio
async def test_storage_maintenance_prune_game_records(async_session: AsyncSession):
    """60 kundan eski mafia o'yin yozuvlarini tozalash testi."""
    now = utc_now()
    old_game = await crud.record_mafia_game(async_session, "room_old", "civ", 6, 2)
    old_game.created_at = now - timedelta(days=75)
    recent_game = await crud.record_mafia_game(async_session, "room_recent", "maf", 8, 3)
    recent_game.created_at = now - timedelta(days=15)
    await async_session.commit()

    pruned_count = await crud.prune_old_game_records(async_session, days=60)
    await async_session.commit()
    assert pruned_count == 1

    stmt = select(func.count(MafiaGameRecord.id))
    result = await async_session.execute(stmt)
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_concurrent_user_creation_no_integrity_error():
    """Bir vaqtda bir xil user_id uchun so'rovlar kelganda IntegrityError chiqmasligi testi."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=10,
        max_overflow=20,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def worker(idx: int):
        async with session_maker() as s:
            user, created = await crud.get_or_create_user(s, 777888, username=f"user_{idx}")
            await s.commit()
            return user.id, created

    results = await asyncio.gather(*[worker(i) for i in range(10)])
    assert all(r[0] == 777888 for r in results)
    created_count = sum(1 for r in results if r[1] is True)
    assert created_count == 1

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_concurrent_upsert_movie_no_integrity_error():
    """Bir vaqtda bir xil kodli film upsert qilinganda IntegrityError chiqmasligi testi."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=10,
        max_overflow=20,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def worker(idx: int):
        async with session_maker() as s:
            movie, created = await crud.upsert_movie(s, "5001", f"Paralel Kino {idx}")
            await s.commit()
            return movie.code, created

    results = await asyncio.gather(*[worker(i) for i in range(10)])
    assert all(r[0] == "5001" for r in results)
    created_count = sum(1 for r in results if r[1] is True)
    assert created_count == 1

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_concurrent_save_movie_file_no_integrity_error():
    """Bir vaqtda bir xil qism uchun file_id saqlanganda unikal cheklov to'qnashmasligi testi."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=10,
        max_overflow=20,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def worker(idx: int):
        async with session_maker() as s:
            mf = await crud.save_movie_file(s, "5001", 1, f"cloud_file_id_{idx}")
            await s.commit()
            return mf.movie_code, mf.part

    results = await asyncio.gather(*[worker(i) for i in range(10)])
    assert all(r == ("5001", 1) for r in results)

    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_sqlite_pool_and_pragma_helpers(async_session: AsyncSession):
    """SQLite havzasi va PRAGMA yordamchi funksiyalari testi."""
    # Engine connection pool bounded QueuePool ekanligini tasdiqlash
    pool_class_name = type(app_engine.pool).__name__
    assert "QueuePool" in pool_class_name or "AsyncAdaptedQueuePool" in pool_class_name

    # PRAGMA helperlarini xatosiz bajarilishini tekshirish
    await execute_incremental_vacuum(pages=100, session=async_session)
    await execute_wal_checkpoint(mode="TRUNCATE", session=async_session)

