"""
Asilmedia batch catalog sync, Telegram Cloud file_id pool,
va Web App LCP optimallashtirish testlari.
100% Bauntys brendi.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base, Movie, MovieFile
from database import crud
from services.movie_service import movie_service, MovieService
from services.asilmedia_service import asilmedia_service
from handlers.movies import save_or_update_movie_video, cmd_debug_optimize_lcp
from handlers.admin import cmd_sync_catalog_asilmedia
from config import config


@pytest_asyncio.fixture
async def in_memory_session():
    """In-memory SQLite testi uchun alohida session fixture."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_movie_file_crud_save_and_get(in_memory_session: AsyncSession):
    """MovieFile jadvaliga file_id saqlash va olish testi."""
    # 1. Yangi file_id saqlash
    mf = await crud.save_movie_file(
        session=in_memory_session,
        movie_code="718",
        part=1,
        file_id="BAACAgIAAxkBAAIB_taxi1_fid",
        file_type="video",
        file_size=550 * 1024 * 1024,
        duration=5400,
        quality="1080p",
    )
    await in_memory_session.commit()
    assert mf is not None
    assert mf.movie_code == "718"
    assert mf.part == 1
    assert mf.file_id == "BAACAgIAAxkBAAIB_taxi1_fid"
    assert mf.quality == "1080p"

    # 2. get_movie_file orqali tekshirish
    fetched = await crud.get_movie_file(in_memory_session, "718", 1)
    assert fetched is not None
    assert fetched.file_id == "BAACAgIAAxkBAAIB_taxi1_fid"

    # 3. file_id yangilash
    updated = await crud.save_movie_file(
        session=in_memory_session,
        movie_code="718",
        part=1,
        file_id="BAACAgIAAxkBAAIB_taxi1_updated_fid",
        quality="1440p",
    )
    await in_memory_session.commit()
    assert updated.file_id == "BAACAgIAAxkBAAIB_taxi1_updated_fid"
    assert updated.quality == "1440p"


@pytest.mark.asyncio
async def test_deliver_movie_cloud_pool_fast_path(in_memory_session: AsyncSession):
    """deliver_movie Telegram Cloud pool orqali file_id ni tezkor yuborishi testi."""
    real_fid = "BAACAgIAAxkDAAIC_cloud_pool_fid_valid_real_telegram_12345"
    # Bazaga kino va file_id keshini kiritish
    await crud.save_movie_file(
        session=in_memory_session,
        movie_code="718",
        part=1,
        file_id=real_fid,
    )
    movie = Movie(
        code="718",
        title="Taksi 1",
        file_id=real_fid,
        file_type="video",
        views_count=100,
        downloads_count=50,
    )
    in_memory_session.add(movie)
    await in_memory_session.commit()

    bot = AsyncMock()
    fake_sent_msg = MagicMock()
    fake_sent_msg.video = MagicMock(file_id=real_fid)
    fake_sent_msg.document = None
    bot.send_video.return_value = fake_sent_msg

    sent = await movie_service.deliver_movie(
        bot=bot,
        chat_id=12345,
        code="718",
        part=1,
        session=in_memory_session,
    )
    assert sent is True
    # send_video to'g'ridan-to'g'ri cloud pool dagi file_id bilan chaqirilganini tekshirish
    assert bot.send_video.called
    call_kwargs = bot.send_video.call_args[1]
    assert call_kwargs["video"] == real_fid


@pytest.mark.asyncio
async def test_save_or_update_movie_video_saves_to_movie_files(in_memory_session: AsyncSession):
    """save_or_update_movie_video chaqirilganda movie_files ga ham saqlanishi testi."""
    db_m = await save_or_update_movie_video(
        session=in_memory_session,
        code="999_2",
        candidate_title=None,
        file_id="BAACAgIAAxkBAAIB_series_999_p2",
        file_type="video",
        duration=3200,
        file_size=400 * 1024 * 1024,
    )
    assert db_m is not None
    assert db_m.code == "999_2"

    # movie_files jadvalida part 2 sifatida saqlanganini tekshiramiz
    mf = await crud.get_movie_file(in_memory_session, "999", 2)
    assert mf is not None
    assert mf.file_id == "BAACAgIAAxkBAAIB_series_999_p2"
    assert mf.part == 2


@pytest.mark.asyncio
async def test_sync_catalog_from_asilmedia_batch(in_memory_session: AsyncSession, tmp_path, monkeypatch):
    """sync_catalog_from_asilmedia batch qabul qilib bazaga va keshga yozishi testi."""
    d_dir = tmp_path / "data"
    d_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("config.BASE_DIR", tmp_path)
    mock_batch = [
        {
            "id": "8881",
            "title": "Chaqmoqdek Tezkor Film",
            "year": 2024,
            "poster": "https://asilmedia.org/p/8881.jpg",
            "is_series": False,
            "genres": ["Jangari", "Triller"],
            "description": "Zo'r film",
            "total_parts": 1,
            "views": 3000,
        },
        {
            "id": "8882",
            "title": "Yulduzlar Aro Serial",
            "year": 2024,
            "poster": "https://asilmedia.org/p/8882.jpg",
            "is_series": True,
            "genres": ["Fantastika"],
            "description": "Zo'r serial",
            "total_parts": 8,
            "views": 4500,
        }
    ]

    with patch.object(asilmedia_service, "fetch_catalog_batch", new_callable=AsyncMock) as mock_fetch, \
         patch.object(MovieService, "sync_movie_from_asilmedia", new_callable=AsyncMock) as mock_sync_single:
        mock_fetch.return_value = mock_batch
        mock_sync_single.return_value = {"success": True, "episodes": 1}

        count = await movie_service.sync_catalog_from_asilmedia(
            limit=2,
            pages=2,
            session=in_memory_session,
            download_files=False,
        )

        assert count > 0
        mock_fetch.assert_called_once_with(pages=2)
        # Bazada yaratilganini tekshiramiz
        m1 = await crud.get_movie_by_code(in_memory_session, "8881")
        assert m1 is not None
        assert "Chaqmoqdek" in m1.title


@pytest.mark.asyncio
async def test_cmd_debug_optimize_lcp():
    """/debug-optimize-lcp komandasi to'g'ri diagnostika va tavsiyalarni qaytarishi testi."""
    message = AsyncMock()
    message.reply = AsyncMock()
    await cmd_debug_optimize_lcp(message)

    assert message.reply.called
    call_args = message.reply.call_args
    reply_text = call_args[0][0]
    assert "LCP" in reply_text
    assert "fetchpriority" in reply_text
    assert "161-97-96-58.sslip.io" in reply_text
    assert "asilmedia.org" in reply_text


@pytest.mark.asyncio
async def test_cmd_sync_catalog_asilmedia_admin():
    """/sync_catalog_asilmedia admin komandasining ishlashi va hisoboti testi."""
    message = AsyncMock()
    message.from_user.id = 12345
    message.text = "/sync_catalog_asilmedia 3"
    status_msg = AsyncMock()
    message.reply.return_value = status_msg

    with patch("handlers.admin.is_admin_check", return_value=True), \
         patch.object(movie_service, "sync_catalog_from_asilmedia", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = 15
        await cmd_sync_catalog_asilmedia(message)

        assert message.reply.called
        assert status_msg.edit_text.called
        edit_text = status_msg.edit_text.call_args[0][0]
        assert "15 ta" in edit_text
        assert "3 ta" in edit_text


@pytest.mark.asyncio
async def test_movie_file_unique_constraint_and_part_formats(in_memory_session: AsyncSession):
    """MovieFile compound unique constraint va har xil part formatlari (718-2, 718p2) testi."""
    # 1. Hyphen formatida saqlash (718-2)
    mf1 = await crud.save_movie_file(
        session=in_memory_session,
        movie_code="718-2",
        part=1,
        file_id="BAACAgIAAxkBAAE_SAMPLE_REAL_TELEGRAM_FID_718_P2",
    )
    await in_memory_session.commit()
    assert mf1.movie_code == "718"
    assert mf1.part == 2

    # 2. get_movie_file ("718", 2) va ("718_2", 1) orqali olish
    fetched = await crud.get_movie_file(in_memory_session, "718", 2)
    assert fetched is not None
    assert fetched.file_id == "BAACAgIAAxkBAAE_SAMPLE_REAL_TELEGRAM_FID_718_P2"

    fetched_alt = await crud.get_movie_file(in_memory_session, "718_2")
    assert fetched_alt is not None
    assert fetched_alt.file_id == "BAACAgIAAxkBAAE_SAMPLE_REAL_TELEGRAM_FID_718_P2"

    # 3. Modelda UniqueConstraint mavjudligini tekshirish
    from database.models import MovieFile
    constraints = [c for c in MovieFile.__table__.constraints if getattr(c, "columns", None)]
    has_uq = any(set(col.name for col in c.columns) == {"movie_code", "part"} for c in constraints)
    assert has_uq, "MovieFile jadvalida (movie_code, part) bo'yicha compound UniqueConstraint mavjud bo'lishi shart"


def test_is_valid_telegram_file_id_validation():
    """is_valid_telegram_file_id haqiqiy va qalbaki file_id larni to'g'ri ajratishi testi."""
    # Qalbaki / mock / seed / placeholder file_id lar
    assert MovieService.is_valid_telegram_file_id("BAACAgIAAxkBAAIB_forsaj10_vid") is False
    assert MovieService.is_valid_telegram_file_id("BAACAgIAAxkBAAIB_mov_8881_vid") is False
    assert MovieService.is_valid_telegram_file_id("BAACAgIAAxkBAAE_TAXI_1_REAL_FID") is False
    assert MovieService.is_valid_telegram_file_id("mock_fid_12345678901234567890") is False
    assert MovieService.is_valid_telegram_file_id("https://cdn.example.com/video.mp4") is False
    assert MovieService.is_valid_telegram_file_id("") is False
    assert MovieService.is_valid_telegram_file_id(None) is False
    assert MovieService.is_valid_telegram_file_id("short_fid") is False

    # Haqiqiy Telegram file_id lar
    assert MovieService.is_valid_telegram_file_id("BAACAgIAAxkDAAIC_cloud_pool_fid_valid_real_telegram_12345") is True
    assert MovieService.is_valid_telegram_file_id("BAACAgIAAxkBAAIB_real_video_uploaded_by_telegram_12345678") is True


@pytest.mark.asyncio
async def test_cmd_browser_zakirovs_analysis():
    """/browser @Zakirovsfilms_bot ni toliq organ buyrug'i arxitektura tahlilini qaytarishi testi."""
    from handlers.movies import cmd_browser
    message = AsyncMock()
    message.text = "/browser @Zakirovsfilms_bot ni toliq organ"
    message.reply = AsyncMock()

    await cmd_browser(message)

    assert message.reply.called
    reply_text = message.reply.call_args[0][0]
    assert "Arxitektura Tahlili" in reply_text
    assert "Asilmedia.org" in reply_text
    assert "Telegram Cloud Pool" in reply_text

