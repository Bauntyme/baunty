"""
Database CRUD funksiyalari testi (Async SQLite in-memory)
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
from database import crud


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
        title="Zakirovs Kino",
        invite_link="https://t.me/ZakirovsKino"
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
