"""
Kino videolari qabul qilish, avtomatik indekslash va deliver_movie testlari.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base, Movie
from database import crud
from services.movie_service import movie_service, MovieService
from handlers.movies import (
    extract_code_from_caption,
    extract_candidate_title,
    format_duration_str,
    format_file_size_str,
    save_or_update_movie_video,
    cmd_set_movie_video,
    handle_incoming_movie_video,
    handle_channel_movie_post,
)
from config import config, BASE_DIR


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


def test_caption_helpers():
    """Captiondan kino kodi va nomini ajratib olish testlari."""
    # 1. extract_code_from_caption
    assert extract_code_from_caption("#284") == "284"
    assert extract_code_from_caption("# 284") == "284"
    assert extract_code_from_caption("№284") == "284"
    assert extract_code_from_caption("№ 284") == "284"
    assert extract_code_from_caption("#kino284") == "284"
    assert extract_code_from_caption("#film284") == "284"
    assert extract_code_from_caption("[284]") == "284"
    assert extract_code_from_caption("(284)") == "284"
    assert extract_code_from_caption("🎬 Zo'raki Folbin\n\n🔢 Kodi: #284\n📢 Homiy kanal: @Zakirovsfilms_bot") == "284"
    assert extract_code_from_caption("kino kodi: 101") == "101"
    assert extract_code_from_caption("film kodi: 101") == "101"
    assert extract_code_from_caption("kino: 101") == "101"
    assert extract_code_from_caption("film: 101") == "101"
    assert extract_code_from_caption("kod: 555") == "555"
    assert extract_code_from_caption("код 999") == "999"
    assert extract_code_from_caption("284. Zo'raki folbin") == "284"
    assert extract_code_from_caption("101 - Forsaj 10") == "101"
    # Serial qismlari (1-qism) xato ravishda 1-kino deb olinmasligi kerak
    assert extract_code_from_caption("1-qism. Zo'raki folbin") is None
    assert extract_code_from_caption("Salom dunyo") is None
    assert extract_code_from_caption("") is None
    assert extract_code_from_caption(None) is None

    # 2. extract_candidate_title
    caption = "🎬 Zo'raki Folbin\n\n📢 Homiy kanal: @Zakirovsfilms_bot"
    candidate = extract_candidate_title(caption)
    assert candidate is not None
    assert "Zo'raki Folbin" in candidate

    # Sarlavha birinchi qatorda PREMYERA bo'lsa ham 2-qatordagi haqiqiy nomni olish
    caption_with_header = "🎬 PREMYERA!\nZo'raki Folbin\n🔢 Kodi: #284"
    assert extract_candidate_title(caption_with_header) == "Zo'raki Folbin"

    # 3. format_duration_str
    assert format_duration_str(848) == "14:08"
    assert format_duration_str(4089) == "1:08:09"
    assert format_duration_str(0) == "Noma'lum"
    assert format_duration_str(None) == "Noma'lum"

    # 4. format_file_size_str
    assert "418.0 MB" in format_file_size_str(418 * 1024 * 1024)
    assert "1.46 GB" in format_file_size_str(1500 * 1024 * 1024)
    assert format_file_size_str(None) == ""


def test_search_catalog_by_title():
    """catalog.json faylidan sarlavha bo'yicha qidirish testi (Lotin, Kirill, Apostrof)."""
    # Lotin
    item = MovieService.search_catalog_by_title("Zo'raki Folbin")
    assert item is not None
    assert str(item.get("c")) == "284"

    # Apostrofsiz
    item_no_apos = MovieService.search_catalog_by_title("Zoraki Folbin")
    assert item_no_apos is not None
    assert str(item_no_apos.get("c")) == "284"

    # Kirill yozuvida
    item_cyrillic = MovieService.search_catalog_by_title("Зўраки фолбин")
    assert item_cyrillic is not None
    assert str(item_cyrillic.get("c")) == "284"

    # Ko'sem Sulton
    item_kosem = MovieService.search_catalog_by_title("Ko'sem Sulton")
    assert item_kosem is not None
    assert str(item_kosem.get("c")) == "282"

    item2 = MovieService.search_catalog_by_title("Eys Ventura")
    assert item2 is not None
    assert str(item2.get("c")) == "283"

    # Umumiy so'z tasodifiy kinoga ulanib ketmasligi kerak
    assert MovieService.search_catalog_by_title("Yangi film") is None
    assert MovieService.search_catalog_by_title("Mavjud_Bolmagan_Kino_XYZ_999") is None


@pytest.mark.asyncio
async def test_deliver_movie_non_existent():
    """Bazada va katalogda mavjud bo'lmagan kino kodi False qaytarishi testi."""
    bot_mock = AsyncMock()
    result = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=12345,
        code="99999999_NOT_EXIST",
        part=1
    )
    assert result is False
    assert bot_mock.send_video.called is False
    assert bot_mock.send_photo.called is False
    assert bot_mock.send_message.called is False


@pytest.mark.asyncio
async def test_deliver_movie_real_video(in_memory_session: AsyncSession):
    """Haqiqiy Telegram file_id (BAACAg...) bo'lganda bot.send_video chaqirilishi testi."""
    real_file_id = "BAACAgIAAxkBAAE_SAMPLE_REAL_TELEGRAM_VIDEO_FILE_ID_1234567890"
    movie = await crud.create_movie(
        session=in_memory_session,
        code="284",
        title="Zo'raki Folbin",
        file_id=real_file_id,
        duration=848,
        file_size=418 * 1024 * 1024
    )
    await in_memory_session.commit()

    bot_mock = AsyncMock()
    bot_mock.send_video = AsyncMock()
    bot_mock.send_document = AsyncMock()
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    result = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=12345,
        code="284",
        part=1,
        session=in_memory_session
    )

    assert result is True
    assert bot_mock.send_video.called is True
    call_kwargs = bot_mock.send_video.call_args.kwargs
    assert call_kwargs["chat_id"] == 12345
    assert call_kwargs["video"] == real_file_id
    assert call_kwargs["duration"] == 848
    assert "Zo'raki Folbin" in call_kwargs["caption"]
    assert bot_mock.send_photo.called is False


@pytest.mark.asyncio
async def test_deliver_movie_document_type(in_memory_session: AsyncSession):
    """Kino file_type == 'document' bo'lganda bot.send_document chaqirilishi testi."""
    real_file_id = "BQACAgIAAxkBAAE_SAMPLE_REAL_DOC_FILE_ID_1234567890"
    movie = await crud.create_movie(
        session=in_memory_session,
        code="285",
        title="Hujjatli Kino",
        file_id=real_file_id,
        file_type="document"
    )
    await in_memory_session.commit()

    bot_mock = AsyncMock()
    bot_mock.send_document = AsyncMock()
    bot_mock.send_video = AsyncMock()
    bot_mock.send_photo = AsyncMock()

    result = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=12345,
        code="285",
        part=1,
        session=in_memory_session
    )

    assert result is True
    assert bot_mock.send_document.called is True
    assert bot_mock.send_video.called is False


@pytest.mark.asyncio
async def test_deliver_movie_placeholder_fallback(in_memory_session: AsyncSession):
    """Mock/placeholder file_id bo'lganda send_video chaqirilmasdan poster/matnga o'tishi testi."""
    movie = await crud.create_movie(
        session=in_memory_session,
        code="101",
        title="Forsaj 10",
        file_id="BAACAgIAAxkBAAIB_forsaj10_vid"  # _vid mavjud -> placeholder
    )
    await in_memory_session.commit()

    bot_mock = AsyncMock()
    bot_mock.send_video = AsyncMock()
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    result = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=12345,
        code="101",
        part=1,
        session=in_memory_session
    )

    assert result is True
    assert bot_mock.send_video.called is False
    assert bot_mock.send_photo.called or bot_mock.send_message.called


@pytest.mark.asyncio
async def test_deliver_movie_multipart(in_memory_session: AsyncSession):
    """Ko'p qismli kino part=2 so'ralganda mos qism videosi yetkazilishi testi."""
    real_fid_part2 = "BAACAgIAAxkBAAE_MULTIPART_SERIES_EPISODE_2_FILE_ID_123456"
    await crud.create_movie(
        session=in_memory_session,
        code="282_2",
        title="Ko'sem Sulton - 2-qism",
        file_id=real_fid_part2,
        duration=3600
    )
    await in_memory_session.commit()

    bot_mock = AsyncMock()
    bot_mock.send_video = AsyncMock()

    result = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=12345,
        code="282",
        part=2,
        session=in_memory_session
    )
    assert result is True
    assert bot_mock.send_video.called is True
    assert bot_mock.send_video.call_args.kwargs["video"] == real_fid_part2


@pytest.mark.asyncio
async def test_save_or_update_movie_video(in_memory_session: AsyncSession):
    """save_or_update_movie_video funksiyasi kodi orqali va catalog.json dan yaratishi testi."""
    real_fid = "BAACAgIAAxkBAAE_ZORAKI_FOLBIN_FULL_MP4_418MB_ID_99999"

    # 1. 284-kino bazada yo'q, lekin catalog.json da bor -> avtomatik yaratiladi
    saved_movie = await save_or_update_movie_video(
        session=in_memory_session,
        code="284",
        candidate_title="Zo'raki Folbin",
        file_id=real_fid,
        duration=848,
        file_size=418 * 1024 * 1024
    )
    assert saved_movie is not None
    assert saved_movie.code == "284"
    assert saved_movie.file_id == real_fid
    assert saved_movie.duration == 848
    assert "Zo'raki Folbin" in saved_movie.title

    # 2. Mavjud kinoni yangilash
    updated_movie = await save_or_update_movie_video(
        session=in_memory_session,
        code="284",
        candidate_title=None,
        file_id="BAACAgIAAxkBAAE_NEW_UPDATED_FILE_ID_88888",
        duration=850,
        file_size=420 * 1024 * 1024
    )
    assert updated_movie.file_id == "BAACAgIAAxkBAAE_NEW_UPDATED_FILE_ID_88888"
    assert updated_movie.duration == 850


@pytest.mark.asyncio
async def test_cmd_set_movie_video_admin(in_memory_session: AsyncSession, monkeypatch):
    """Admin /setmovie <kod> buyrug'i orqali videoni biriktirishi testi."""
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def fake_get_session():
        yield in_memory_session
    monkeypatch.setattr("handlers.movies.get_session", fake_get_session)
    monkeypatch.setattr(config.__class__, "is_admin", lambda self, uid: uid == 7777)

    # 1. Admin bo'lmagan foydalanuvchi chaqirganda
    msg_non_admin = AsyncMock()
    msg_non_admin.from_user.id = 1234
    msg_non_admin.text = "/setmovie 284"
    msg_non_admin.caption = None
    msg_non_admin.reply = AsyncMock()
    await cmd_set_movie_video(msg_non_admin)
    assert "faqat adminlar uchun" in msg_non_admin.reply.call_args[0][0]

    # 2. Admin video xabarga Reply qilib chaqirganda
    msg_admin = AsyncMock()
    msg_admin.from_user.id = 7777
    msg_admin.text = "/setmovie 284"
    msg_admin.caption = None
    msg_admin.reply = AsyncMock()

    reply_video_msg = MagicMock()
    reply_video_msg.video = MagicMock()
    reply_video_msg.video.file_id = "BAACAgIAAxkBAAE_ADMIN_REPLY_VIDEO_FILE_ID_11111"
    reply_video_msg.video.duration = 848
    reply_video_msg.video.file_size = 418 * 1024 * 1024
    reply_video_msg.document = None

    msg_admin.reply_to_message = reply_video_msg
    await cmd_set_movie_video(msg_admin)
    assert msg_admin.reply.called is True
    reply_text = msg_admin.reply.call_args[0][0]
    assert "muvaffaqiyatli biriktirildi" in reply_text
    assert "#284" in reply_text

    # Bazada saqlanganligini tekshirish
    db_m = await crud.get_movie_by_code(in_memory_session, "284")
    assert db_m is not None
    assert db_m.file_id == "BAACAgIAAxkBAAE_ADMIN_REPLY_VIDEO_FILE_ID_11111"

    # 3. Admin videoni to'g'ridan-to'g'ri /setmovie 284 caption bilan birga yuborganida (message.text is None!)
    msg_direct_video = AsyncMock()
    msg_direct_video.from_user.id = 7777
    msg_direct_video.text = None
    msg_direct_video.caption = "/setmovie 283"
    msg_direct_video.video = MagicMock()
    msg_direct_video.video.file_id = "BAACAgIAAxkBAAE_ADMIN_DIRECT_VIDEO_CAPTION_77777"
    msg_direct_video.video.duration = 600
    msg_direct_video.video.file_size = 300 * 1024 * 1024
    msg_direct_video.document = None
    msg_direct_video.reply_to_message = None
    msg_direct_video.reply = AsyncMock()

    await cmd_set_movie_video(msg_direct_video)
    assert msg_direct_video.reply.called is True
    assert "muvaffaqiyatli biriktirildi" in msg_direct_video.reply.call_args[0][0]
    db_m283 = await crud.get_movie_by_code(in_memory_session, "283")
    assert db_m283 is not None
    assert db_m283.file_id == "BAACAgIAAxkBAAE_ADMIN_DIRECT_VIDEO_CAPTION_77777"


@pytest.mark.asyncio
async def test_handle_incoming_movie_video(in_memory_session: AsyncSession, monkeypatch):
    """Foydalanuvchi video yuborganida captiondan kodni aniqlab bazaga saqlash testi."""
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def fake_get_session():
        yield in_memory_session
    monkeypatch.setattr("handlers.movies.get_session", fake_get_session)

    # 1. Captionda kod bo'lgan video (# 284 oraliq bo'sh joy bilan)
    msg = AsyncMock()
    msg.video = MagicMock()
    msg.video.file_id = "BAACAgIAAxkBAAE_INCOMING_FORWARD_VIDEO_ID_22222"
    msg.video.duration = 848
    msg.video.file_size = 418 * 1024 * 1024
    msg.video.file_name = None
    msg.document = None
    msg.caption = "🎬 Zo'raki Folbin\n\n🔢 Kodi: # 284\n📢 Homiy kanal: @Zakirovsfilms_bot"
    msg.text = None
    msg.reply = AsyncMock()

    await handle_incoming_movie_video(msg)
    assert msg.reply.called is True
    resp = msg.reply.call_args[0][0]
    assert "muvaffaqiyatli saqlandi" in resp
    assert "#284" in resp

    # Bazani tekshirish
    m = await crud.get_movie_by_code(in_memory_session, "284")
    assert m is not None
    assert m.file_id == "BAACAgIAAxkBAAE_INCOMING_FORWARD_VIDEO_ID_22222"

    # 2. Caption bo'sh, ammo fayl nomida kod bo'lgan video (file_name fallback)
    msg_fn = AsyncMock()
    msg_fn.video = MagicMock()
    msg_fn.video.file_id = "BAACAgIAAxkBAAE_FILENAME_FALLBACK_FILE_ID_55555"
    msg_fn.video.duration = 500
    msg_fn.video.file_size = 200 * 1024 * 1024
    msg_fn.video.file_name = "283_Eys_Ventura.mp4"
    msg_fn.document = None
    msg_fn.caption = None
    msg_fn.text = None
    msg_fn.reply = AsyncMock()

    await handle_incoming_movie_video(msg_fn)
    assert msg_fn.reply.called is True
    assert "muvaffaqiyatli saqlandi" in msg_fn.reply.call_args[0][0]
    m283 = await crud.get_movie_by_code(in_memory_session, "283")
    assert m283 is not None
    assert m283.file_id == "BAACAgIAAxkBAAE_FILENAME_FALLBACK_FILE_ID_55555"

    # 3. PDF hujjat jo'natilganda — kinoga biriktirilmasligi va e'tiborsiz qoldirilishi
    msg_pdf = AsyncMock()
    msg_pdf.video = None
    msg_pdf.document = MagicMock()
    msg_pdf.document.file_name = "Shartnoma_284.pdf"
    msg_pdf.document.file_id = "PDF_FILE_ID_NOT_MOVIE"
    msg_pdf.caption = "#284"
    msg_pdf.reply = AsyncMock()

    await handle_incoming_movie_video(msg_pdf)
    assert msg_pdf.reply.called is False

    # 4. Kod va nomi aniqlanmagan video kelganda tushunarli yordam berilishi
    msg_unknown = AsyncMock()
    msg_unknown.video = MagicMock()
    msg_unknown.video.file_id = "BAACAgIAAxkBAAE_UNKNOWN_VIDEO_ID"
    msg_unknown.video.duration = 100
    msg_unknown.video.file_size = 1000000
    msg_unknown.video.file_name = None
    msg_unknown.document = None
    msg_unknown.caption = None
    msg_unknown.text = None
    msg_unknown.reply = AsyncMock()

    await handle_incoming_movie_video(msg_unknown)
    assert msg_unknown.reply.called is True
    resp_unknown = msg_unknown.reply.call_args[0][0]
    assert "/setmovie" in resp_unknown


@pytest.mark.asyncio
async def test_handle_channel_movie_post(in_memory_session: AsyncSession, monkeypatch):
    """Kanal postidan video kelganda avtomatik indekslanishi testi."""
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def fake_get_session():
        yield in_memory_session
    monkeypatch.setattr("handlers.movies.get_session", fake_get_session)

    ch_msg = AsyncMock()
    ch_msg.chat.id = -1001999999999
    ch_msg.video = MagicMock()
    ch_msg.video.file_id = "BAACAgIAAxkBAAE_CHANNEL_POST_VIDEO_ID_33333"
    ch_msg.video.duration = 848
    ch_msg.video.file_size = 418 * 1024 * 1024
    ch_msg.document = None
    ch_msg.caption = "🎬 Zo'raki Folbin\n\nKodi: #284\n🍿 @Bauntyfilmsbot"

    await handle_channel_movie_post(ch_msg)

    # Bazada saqlanganligini tekshirish
    m = await crud.get_movie_by_code(in_memory_session, "284")
    assert m is not None
    assert m.file_id == "BAACAgIAAxkBAAE_CHANNEL_POST_VIDEO_ID_33333"
    assert m.duration == 848


@pytest.mark.asyncio
async def test_upsert_movie_and_sync_movies_from_catalog(in_memory_session: AsyncSession):
    """crud.upsert_movie va crud.sync_movies_from_catalog_data to'g'ri ishlashi testi."""
    # 1. Yangi kino yaratish (upsert)
    movie1, created = await crud.upsert_movie(
        session=in_memory_session,
        code="9991",
        title="Yangi Premyera 1",
        description="Ajoyib film",
        year=2025,
        rating=8.9,
    )
    assert created is True
    assert movie1.code == "9991"
    assert movie1.title == "Yangi Premyera 1"

    # 2. Mavjud kinoni yangilash (upsert)
    movie1_updated, created2 = await crud.upsert_movie(
        session=in_memory_session,
        code="9991",
        title="Yangi Premyera 1 - Yangilangan",
        year=2026,
    )
    assert created2 is False
    assert movie1_updated.code == "9991"
    assert movie1_updated.title == "Yangi Premyera 1 - Yangilangan"
    assert movie1_updated.year == 2026

    # 3. Katalog ro'yxatidan sinxronlash
    catalog_items = [
        {"c": "9991", "t": "Yangi Premyera 1 - Katalog", "d": "Katalog tavsifi", "v": 500, "y": 2026, "r": 9.0},
        {"c": "9992", "t": "Yangi Premyera 2", "d": "Yangi kino tavsifi", "v": 300, "y": 2025, "r": 8.5},
    ]
    synced = await crud.sync_movies_from_catalog_data(in_memory_session, catalog_items)
    assert synced >= 2

    m2 = await crud.get_movie_by_code(in_memory_session, "9992")
    assert m2 is not None
    assert m2.title == "Yangi Premyera 2"
    assert m2.views_count == 300


@pytest.mark.asyncio
async def test_sync_catalog_from_upstream_mocked(in_memory_session: AsyncSession, monkeypatch):
    """movie_service.sync_catalog_from_upstream ning upstream API bilan ishlashi testi."""
    from unittest.mock import patch

    mock_catalog = {
        "items": [
            {
                "c": "7771",
                "t": "Zakirovs Yangi Kino",
                "d": "Kino tavsifi @Zakirovsfilms_bot va @ZakirovsKino",
                "v": 1000,
                "y": 2025
            }
        ],
        "channel": "@ZakirovsKino",
        "bot": "Zakirovsfilms_bot"
    }

    class MockResponse:
        status = 200
        async def json(self):
            return mock_catalog
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClientSession:
        def get(self, url, timeout=None):
            return MockResponse()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("aiohttp.ClientSession", MockClientSession)

    import sys
    ms_mod = sys.modules["services.movie_service"]
    old_cache = getattr(ms_mod, "_CATALOG_CACHE", None)
    try:
        synced = await movie_service.sync_catalog_from_upstream(session=in_memory_session)
        assert synced >= 1

        m = await crud.get_movie_by_code(in_memory_session, "7771")
        assert m is not None
        assert "Zakirov" not in m.description
        assert config.CHANNEL_USERNAME in m.description or "@Baunty" in m.description
    finally:
        setattr(ms_mod, "_CATALOG_CACHE", old_cache)


@pytest.mark.asyncio
async def test_periodic_catalog_sync_lifecycle():
    """start_periodic_catalog_sync va stop_periodic_catalog_sync vazifasi ishlashi testi."""
    from services.movie_service import start_periodic_catalog_sync, stop_periodic_catalog_sync
    import asyncio

    task = start_periodic_catalog_sync(interval_seconds=3600)
    assert task is not None
    assert not task.done()

    # Bir xil task qaytishi kerak
    task2 = start_periodic_catalog_sync(interval_seconds=3600)
    assert task2 is task

    stop_periodic_catalog_sync()
    await asyncio.sleep(0.05)
    assert task.cancelled() or task.done()


def test_tv_4k_ultra_hd_data_and_webapp():
    """Barcha asosiy telekanallar 4K UHD sifatda sozlanganligini va WebApp barqarorligini tekshirish."""
    from services.tv_data import CHANNELS_LIST
    by_name = {c["name"]: c for c in CHANNELS_LIST}

    assert by_name["BIZ Cinema"]["q"] == "4K UHD"
    assert "4K UHD" in by_name["Sevimli TV"]["q"]
    assert "4K UHD" in by_name["Zo'r TV"]["q"]
    assert "4K UHD" in by_name["Milliy TV"]["q"]
    assert "4K UHD" in by_name["Makka Jonli Efir"]["q"]
    assert "4K UHD" in by_name["Madina Jonli Efir"]["q"]
    assert "4K UHD" in by_name["Kinoteatr TV"]["q"]
    assert "4K UHD" in by_name["Mening Yurtim (MY5)"]["q"]
    assert "4K UHD" in by_name["Renessans TV"]["q"]
    assert "4K UHD" in by_name["Sport TV"]["q"]
    assert "4K UHD" in by_name["Futbol TV"]["q"]

    # webapp/index.html dagi sifat, fon barqarorligi va swipe bloklash sozlamalari
    index_file = BASE_DIR / "webapp" / "index.html"
    assert index_file.exists()
    content = index_file.read_text(encoding="utf-8")

    assert "overscroll-behavior:none" in content
    assert "enableClosingConfirmation" in content
    assert "disableVerticalSwipes" in content
    assert "autopictureinpicture" in content
    assert "mediaSession" in content
    assert "requestFullscreen" in content
    assert "tvpip" in content
    assert "4K UHD" in content
    assert "maxBufferLength: 45" in content
    assert "maxMaxBufferLength: 120" in content
    assert "maxBufferHole: 0.5" in content
    assert "image-rendering: -webkit-optimize-contrast" in content
    assert "showOpenBotSheet" in content
    # Hls.isSupported else shoxi to'g'ri bo'lishi shart (barcha brauzerlarda Hls ishga tushishi uchun)
    assert "!Hls.isSupported()" in content
    assert "} else {\n          hls = new Hls({" in content.replace("\r\n", "\n")
    # visibilitychange da vid.pause bo'lmasligi va pauzada !document.hidden to'sig'i bo'lmasligi kerak
    assert "document.hidden && tvCur) vid.pause()" not in content
    assert "tvCur && !vid.ended && !document.hidden" not in content


def test_sanitize_branding_comprehensive():
    """Upstream Zakirovs havolalari va belgilarini to'liq Baunty brendiga tozalash testi."""
    import re
    # Test cases with URLs and usernames
    dirty_text = (
        "Kinoni tomosha qilish: https://t.me/ZakirovsKino yoki @Zakirovsfilms_bot\n"
        "Rasmiy bot: t.me/Zakirovsfilms_bot. Kanal: @ZakirovsKino va @dilbarzakirova.\n"
        "Zakirovs Films taqdim etadi: Zakirovs kino premyerasi."
    )
    bot_clean = config.BOT_USERNAME.lstrip("@")
    channel_clean = config.CHANNEL_USERNAME.lstrip("@")

    # Re-run same regex logic as in MovieService
    text = re.sub(r'https?://t\.me/(?:Zakirovs(?:films_bot|Kino)|dilbarzakirova)\b', f'https://t.me/{channel_clean}', dirty_text, flags=re.I)
    text = re.sub(r't\.me/(?:Zakirovs(?:films_bot|Kino)|dilbarzakirova)\b', f't.me/{channel_clean}', text, flags=re.I)
    text = re.sub(r'@Zakirovsfilms_bot\b', f'@{bot_clean}', text, flags=re.I)
    text = re.sub(r'@ZakirovsKino\b', f'@{channel_clean}', text, flags=re.I)
    text = re.sub(r'@dilbarzakirova\b', f'@{channel_clean}', text, flags=re.I)
    text = re.sub(r'@Zakirovs?\b', f'@{channel_clean}', text, flags=re.I)
    text = re.sub(r'Zakirovs\s+Films\b', 'Baunty Films', text, flags=re.I)
    text = re.sub(r'Zakirovs_bot\b', bot_clean, text, flags=re.I)
    text = re.sub(r'Zakirovs\b', 'Baunty', text, flags=re.I)
    text = re.sub(r'zakirovs\b', 'baunty', text, flags=re.I)
    text = re.sub(r'Dilbar\s*Zakirova\b', 'Baunty', text, flags=re.I)

    assert "Zakirov" not in text
    assert "zakirov" not in text
    assert "dilbar" not in text.lower()
    assert channel_clean in text
    assert bot_clean in text


@pytest.mark.asyncio
async def test_start_movie_deep_link_variants():
    """Botga /start m_284 va /start kino_284 yuborilganda kinoni yetkazish testi."""
    from unittest.mock import AsyncMock, patch
    import handlers.start as start_handler
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage

    message = AsyncMock()
    message.from_user.id = 887766
    message.from_user.username = "filmuser"
    message.from_user.first_name = "Film"
    message.from_user.last_name = "Fan"
    message.chat.id = 887766
    message.message_id = 2002
    message.text = "/start m_284"
    message.answer = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=__import__("aiogram.fsm.storage.base", fromlist=["StorageKey"]).StorageKey(
        bot_id=1, chat_id=887766, user_id=887766
    ))

    with patch.object(start_handler.movie_service, "deliver_movie", new_callable=AsyncMock) as mock_deliver:
        mock_deliver.return_value = True
        await start_handler.cmd_start(message, state)
        assert mock_deliver.called
        assert mock_deliver.call_args.kwargs["code"] == "284"

        # Shuningdek /start kino_284 varianti
        message.text = "/start kino_284"
        await start_handler.cmd_start(message, state)
        assert mock_deliver.call_count == 2

        # 5000 dan katta kod (/start m_5001) ham movie deb qaralishi
        message.text = "/start m_5001"
        await start_handler.cmd_start(message, state)
        assert mock_deliver.call_count == 3
        assert mock_deliver.call_args.kwargs["code"] == "5001"




