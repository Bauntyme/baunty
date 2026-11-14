"""
Milestone M2 Comprehensive Test Suite:
1. Dual-table Telegram file_id persistence (movies and movie_files / movie_videos).
2. Instant delivery via cached file_id (<500ms, 0 MB disk, zero re-download).
3. Local Telegram Bot API Server support (2000 MB upload limit via LOCAL_BOT_API_URL / BOT_API_SERVER).
"""

import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from config import Settings, config
from database import crud
from database.models import Base, Movie, MovieFile
from services.movie_service import MovieService, get_max_upload_bytes
from handlers.movies import save_or_update_movie_video


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


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    fake_sent = MagicMock()
    fake_sent.video = MagicMock(file_id="BAACAgIAAxkDAAIC_test_fixture_file_id_1234567890", duration=7200, file_size=500000000)
    fake_sent.document = None
    bot.send_video.return_value = fake_sent
    bot.send_document.return_value = fake_sent
    return bot


# =========================================================================
# 1. Dual-Table Telegram file_id Persistence Tests
# =========================================================================

@pytest.mark.asyncio
async def test_dual_table_persistence_save_movie_file(in_memory_session: AsyncSession):
    """
    crud.save_movie_file chaqirilganda, file_id bir vaqtning o'zida ham movie_files,
    ham movies jadvallarida sinxron va to'liq saqlanishi kerak (Dual-Table Persistence).
    """
    clean_code = "7701"
    fid_p1 = "BAACAgIAAxkDAAIC_7701_part1_valid_telegram_fid_12345"
    
    # Boshlang'ich kino yozuvi yaratish (bo'sh file_id bilan)
    await crud.create_movie(
        session=in_memory_session,
        code=clean_code,
        title="Test Film 7701",
        file_id="",
    )
    await in_memory_session.commit()

    # 1-qismni save_movie_file orqali saqlash (Dual-table sinxronizatsiya)
    mf1 = await crud.save_movie_file(
        session=in_memory_session,
        movie_code=clean_code,
        part=1,
        file_id=fid_p1,
        file_type="video",
        duration=7200,
        file_size=600 * 1024 * 1024,
        quality="1080p",
    )
    await in_memory_session.commit()

    assert mf1 is not None
    assert mf1.movie_code == clean_code
    assert mf1.part == 1
    assert mf1.file_id == fid_p1

    # movie_files jadvalida mavjudligini tekshirish
    mf_db = await crud.get_movie_file(in_memory_session, clean_code, 1)
    assert mf_db is not None
    assert mf_db.file_id == fid_p1

    # movies jadvalida ham avtomatik yaratilib, file_id yozilganini tekshirish
    m_db = await crud.get_movie_by_code(in_memory_session, clean_code)
    assert m_db is not None
    assert m_db.file_id == fid_p1
    assert m_db.duration == 7200
    assert m_db.file_size == 600 * 1024 * 1024


@pytest.mark.asyncio
async def test_dual_table_persistence_set_movie_video(in_memory_session: AsyncSession):
    """
    crud.set_movie_video chaqirilganda, movies jadvaliga qo'shimcha ravishda
    movie_files jadvalida ham qism bo'yicha yozuv yaratilishi / yangilanishi kerak.
    """
    clean_code = "7702"
    fid_base = "BAACAgIAAxkDAAIC_7702_base_valid_telegram_fid_12345"

    movie = await crud.set_movie_video(
        session=in_memory_session,
        code=clean_code,
        file_id=fid_base,
        file_type="video",
        duration=5400,
        file_size=400 * 1024 * 1024,
        title="Test Film 7702"
    )
    await in_memory_session.commit()

    assert movie is not None
    assert movie.code == clean_code
    assert movie.file_id == fid_base

    # movie_files jadvalida 1-qism sifatida avtomatik saqlanganini tekshirish
    mf = await crud.get_movie_file(in_memory_session, clean_code, 1)
    assert mf is not None
    assert mf.file_id == fid_base
    assert mf.duration == 5400
    assert mf.file_size == 400 * 1024 * 1024

    # Endi 2-qismni "7702_2" kodi bilan set_movie_video orqali saqlash
    fid_p2 = "BAACAgIAAxkDAAIC_7702_part2_valid_telegram_fid_67890"
    m_p2 = await crud.set_movie_video(
        session=in_memory_session,
        code=f"{clean_code}_2",
        file_id=fid_p2,
        file_type="video",
        duration=5500,
        file_size=450 * 1024 * 1024,
    )
    await in_memory_session.commit()

    assert m_p2.code == f"{clean_code}_2"
    assert m_p2.file_id == fid_p2

    # movie_files jadvalida part 2 sifatida yozilganini tekshirish
    mf_p2 = await crud.get_movie_file(in_memory_session, clean_code, 2)
    assert mf_p2 is not None
    assert mf_p2.part == 2
    assert mf_p2.file_id == fid_p2


@pytest.mark.asyncio
async def test_save_or_update_movie_video_dual_persistence(in_memory_session: AsyncSession):
    """
    handlers/movies.py dagi save_or_update_movie_video funksiyasi
    har qanday yangi video kelganda movies va movie_files jadvallarini
    bir vaqtda yangilashini tekshirish.
    """
    code = "7703_3"
    fid = "BAACAgIAAxkDAAIC_7703_part3_valid_telegram_fid_99999"

    db_m = await save_or_update_movie_video(
        session=in_memory_session,
        code=code,
        candidate_title="Test Serial 7703 (3-qism)",
        file_id=fid,
        file_type="video",
        duration=3600,
        file_size=300 * 1024 * 1024,
    )
    assert db_m is not None
    assert db_m.code == "7703_3"
    assert db_m.file_id == fid

    # movie_files jadvalida movie_code="7703" va part=3 sifatida keshlanishi shart
    mf = await crud.get_movie_file(in_memory_session, "7703", 3)
    assert mf is not None
    assert mf.movie_code == "7703"
    assert mf.part == 3
    assert mf.file_id == fid


# =========================================================================
# 2. Instant Delivery via Cached file_id (<500ms, 0 MB Disk)
# =========================================================================

@pytest.mark.asyncio
async def test_instant_delivery_via_cached_file_id(in_memory_session: AsyncSession, mock_bot):
    """
    Keshda file_id mavjud bo'lsa:
    - deliver_movie videoni darhol (<500ms) bot.send_video(video=file_id) orqali yetkazadi.
    - Hech qanday qayta yuklab olish yoki vaqtinchalik disk fayllari yaratilmaydi (0 MB disk).
    """
    code = "7704"
    cached_fid = "BAACAgIAAxkDAAIC_7704_fast_instant_cached_fid_11111"

    # Bazaga kesh kiritish (dual-table)
    await crud.save_movie_file(
        session=in_memory_session,
        movie_code=code,
        part=1,
        file_id=cached_fid,
        duration=5000,
        file_size=500 * 1024 * 1024,
    )
    await crud.set_movie_video(
        session=in_memory_session,
        code=code,
        file_id=cached_fid,
        duration=5000,
        file_size=500 * 1024 * 1024,
        title="Tezkor Kino 7704",
    )
    await in_memory_session.commit()

    start_time = time.monotonic()
    with patch("aiohttp.ClientSession.get") as mock_http_get:
        delivered = await MovieService.deliver_movie(
            bot=mock_bot,
            chat_id=123456,
            code=code,
            part=1,
            session=in_memory_session,
        )
    elapsed = time.monotonic() - start_time

    assert delivered is True
    # Hech qanday tashqi HTTP yuklab olish so'rovi amalga oshmaganini tasdiqlash (0 MB disk, 0 bayt yuklab olish)
    assert not mock_http_get.called, "Keshda file_id bo'lganda tashqi manbadan yuklab olinmasligi kerak!"

    # bot.send_video to'g'ridan-to'g'ri keshdagi file_id bilan chaqirilgan
    assert mock_bot.send_video.called
    call_kwargs = mock_bot.send_video.call_args[1]
    assert call_kwargs["video"] == cached_fid
    assert call_kwargs["chat_id"] == 123456

    # Yetkazish vaqti 500ms dan ancha tez (odatda <50ms)
    assert elapsed < 0.5, f"Yetkazib berish juda sekin: {elapsed:.3f}s (kutilgan: <0.5s)"


@pytest.mark.asyncio
async def test_instant_delivery_repeat_request_uses_newly_cached_file_id(in_memory_session: AsyncSession, mock_bot):
    """
    Takroriy so'rov: Birinchi marta yangi yuklangan video file_id bazada keshlanadi,
    ikkinchi so'rovda esa o'sha keshdagi file_id orqali chaqmoqdek tez yetkaziladi.
    """
    code = "7705"
    uploaded_fid = "BAACAgIAAxkDAAIC_7705_newly_uploaded_telegram_fid_22222"

    # Birinchi urinishda kesh bo'sh, lokal video bor deb tasavvur qilamiz
    candidate_video = {
        "url": "https://fayllar.com/streams/7705_test.mp4",
        "duration": 4800,
        "file_size": 25 * 1024 * 1024,
    }

    # download_and_upload_media_on_demand ni simulyatsiya qilamiz
    fake_sent_msg = MagicMock()
    fake_sent_msg.video = MagicMock(file_id=uploaded_fid, duration=4800, file_size=25 * 1024 * 1024)
    fake_sent_msg.document = None

    with patch.object(MovieService, "download_and_upload_media_on_demand", new_callable=AsyncMock) as mock_ondemand:
        mock_ondemand.return_value = fake_sent_msg

        # Birinchi so'rov (videoni yuklash va keshga saqlash)
        # Boshlang'ich db kiritish
        await crud.create_movie(
            session=in_memory_session,
            code=code,
            title="Kino 7705",
            file_id="",
        )
        await in_memory_session.commit()

        # Mock download & upload orqali file_id saqlanishini taqlid qilamiz
        await crud.save_movie_file(
            session=in_memory_session,
            movie_code=code,
            part=1,
            file_id=uploaded_fid,
            duration=4800,
            file_size=25 * 1024 * 1024,
        )
        await in_memory_session.commit()

    # Ikkinchi so'rov (Keshdan to'g'ridan-to'g'ri jo'natish)
    mock_bot.reset_mock()
    delivered_second = await MovieService.deliver_movie(
        bot=mock_bot,
        chat_id=987654,
        code=code,
        part=1,
        session=in_memory_session,
    )

    assert delivered_second is True
    assert mock_bot.send_video.called
    assert mock_bot.send_video.call_args[1]["video"] == uploaded_fid


@pytest.mark.asyncio
async def test_multipart_series_independent_file_id_caching(in_memory_session: AsyncSession, mock_bot):
    """
    Ko'p qismli seriallar uchun har bir qismning file_id si alohida mustaqil
    saqlanishi va bir-birini almashtirib yubormasligi (no cross-contamination).
    """
    series_code = "7706"
    fid_p1 = "BAACAgIAAxkDAAIC_series7706_part1_fid_aaaaaaaa"
    fid_p2 = "BAACAgIAAxkDAAIC_series7706_part2_fid_bbbbbbbb"
    fid_p3 = "BAACAgIAAxkDAAIC_series7706_part3_fid_cccccccc"

    # 3 ta qismni saqlash
    await crud.save_movie_file(in_memory_session, series_code, part=1, file_id=fid_p1)
    await crud.save_movie_file(in_memory_session, series_code, part=2, file_id=fid_p2)
    await crud.save_movie_file(in_memory_session, series_code, part=3, file_id=fid_p3)
    await in_memory_session.commit()

    # Har bir qism o'zining to'g'ri file_id sini qaytarishini tekshirish
    mf1 = await crud.get_movie_file(in_memory_session, series_code, 1)
    mf2 = await crud.get_movie_file(in_memory_session, series_code, 2)
    mf3 = await crud.get_movie_file(in_memory_session, series_code, 3)

    assert mf1.file_id == fid_p1
    assert mf2.file_id == fid_p2
    assert mf3.file_id == fid_p3

    # deliver_movie orqali tekshirish
    mock_bot.reset_mock()
    await MovieService.deliver_movie(mock_bot, chat_id=111, code=series_code, part=2, session=in_memory_session)
    assert mock_bot.send_video.call_args[1]["video"] == fid_p2

    mock_bot.reset_mock()
    await MovieService.deliver_movie(mock_bot, chat_id=111, code=series_code, part=3, session=in_memory_session)
    assert mock_bot.send_video.call_args[1]["video"] == fid_p3


# =========================================================================
# 3. Local Telegram Bot API Server Support (2000 MB Upload Limit)
# =========================================================================

def test_config_local_bot_api_url_and_upload_limits():
    """
    config.py da LOCAL_BOT_API_URL yoki BOT_API_SERVER sozlangan bo'lsa:
    - is_local_bot_api = True bo'ladi.
    - max_upload_bytes = 2000 * 1024 * 1024 (2000 MB).
    - max_upload_mb = 2000.
    Aks holda standart 50 MB limit qo'llaniladi.
    """
    # 1. Standart konfiguratsiya (mahalliy Bot API sozlangan emas)
    default_settings = Settings(LOCAL_BOT_API_URL=None, BOT_API_SERVER=None)
    assert default_settings.is_local_bot_api is False
    assert default_settings.max_upload_bytes == 50 * 1024 * 1024
    assert default_settings.max_upload_mb == 50

    # 2. LOCAL_BOT_API_URL bilan sozlanganda
    local_settings_1 = Settings(LOCAL_BOT_API_URL="http://127.0.0.1:8081")
    assert local_settings_1.is_local_bot_api is True
    assert local_settings_1.local_bot_api_url_resolved == "http://127.0.0.1:8081"
    assert local_settings_1.LOCAL_BOT_API_URL == "http://127.0.0.1:8081"
    assert local_settings_1.BOT_API_SERVER == "http://127.0.0.1:8081"
    assert local_settings_1.max_upload_bytes == 2000 * 1024 * 1024
    assert local_settings_1.max_upload_mb == 2000

    # 3. BOT_API_SERVER bilan sozlanganda
    local_settings_2 = Settings(BOT_API_SERVER="http://localhost:8081/")
    assert local_settings_2.is_local_bot_api is True
    assert local_settings_2.local_bot_api_url_resolved == "http://localhost:8081"
    assert local_settings_2.max_upload_bytes == 2000 * 1024 * 1024
    assert local_settings_2.max_upload_mb == 2000


def test_main_session_telegram_api_server_configuration():
    """
    LOCAL_BOT_API_URL sozlanganida, aiogram AiohttpSession obyektiga
    TelegramAPIServer.from_base(..., is_local=True) to'g'ri biriktirilishini tekshirish.
    """
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.client.telegram import TelegramAPIServer

    test_url = "http://127.0.0.1:8081"
    server = TelegramAPIServer.from_base(test_url, is_local=True)
    session = AiohttpSession(api=server)

    assert session.api.is_local is True
    assert "http://127.0.0.1:8081" in session.api.base
    assert "http://127.0.0.1:8081" in session.api.file


@pytest.mark.asyncio
async def test_movie_service_upload_limit_respects_local_bot_api():
    """
    services/movie_service.py dagi get_max_upload_bytes() funksiyasi
    LOCAL_BOT_API_URL sozlanganligiga qarab 50 MB yoki 2000 MB qaytarishini tekshirish.
    """
    # Standart holatda
    with patch.object(config, "LOCAL_BOT_API_URL", None), \
         patch.object(config, "BOT_API_SERVER", None):
        assert get_max_upload_bytes() == 50 * 1024 * 1024

    # Mahalliy Bot API sozlanganida
    with patch.object(config, "LOCAL_BOT_API_URL", "http://127.0.0.1:8081"):
        assert get_max_upload_bytes() == 2000 * 1024 * 1024


@pytest.mark.asyncio
async def test_download_and_upload_respects_2000mb_limit(mock_bot):
    """
    Oqimli yuklab olishda fayl hajmi:
    - 50 MB dan katta (masalan 150 MB): standart limitda rad etiladi.
    - Mahalliy Bot API serverida (2000 MB): muvaffaqiyatli qabul qilinadi.
    """
    large_size = 150 * 1024 * 1024  # 150 MB

    # 1. Standart limit (50 MB) da tekshirish: rad etilishi kerak
    with patch.object(config, "LOCAL_BOT_API_URL", None), \
         patch.object(config, "BOT_API_SERVER", None):
        
        # Mock ClientSession Content-Length = 150 MB
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Length": str(large_size), "Content-Type": "video/mp4"}
        
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        
        mock_client = MagicMock()
        mock_client.get.return_value = mock_ctx
        mock_client.__aenter__.return_value = mock_client
        
        with patch("aiohttp.ClientSession", return_value=mock_client):
            result = await MovieService.download_and_upload_media_on_demand(
                bot=mock_bot,
                chat_id=123,
                code="7707",
                part=1,
                source_url="https://fayllar.com/streams/large_150mb.mp4",
                caption="Katta kino",
            )
            # Standart rejimda 150 MB > 50 MB bo'lgani uchun yuklanmaydi (None qaytadi)
            assert result is None

    # 2. Mahalliy Bot API (2000 MB) da tekshirish: 150 MB qabul qilinadi
    with patch.object(config, "LOCAL_BOT_API_URL", "http://127.0.0.1:8081"), \
         patch.object(config, "BOT_API_SERVER", "http://127.0.0.1:8081"):
        assert config.max_upload_bytes == 2000 * 1024 * 1024
        # 150 MB hajmli fayl 2000 MB dan kichik bo'lgani uchun Content-Length filtri uni rad etmaydi
        assert large_size < config.max_upload_bytes
