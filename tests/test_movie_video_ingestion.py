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


def test_caption_helpers():
    """Captiondan kino kodi va nomini ajratib olish testlari."""
    # 1. extract_code_from_caption
    assert extract_code_from_caption("#284") == "284"
    assert extract_code_from_caption("№284") == "284"
    assert extract_code_from_caption("[284]") == "284"
    assert extract_code_from_caption("(284)") == "284"
    assert extract_code_from_caption("🎬 Zo'raki Folbin\n\n🔢 Kodi: #284\n📢 Homiy kanal: @Zakirovsfilms_bot") == "284"
    assert extract_code_from_caption("kino kodi: 101") == "101"
    assert extract_code_from_caption("kod: 555") == "555"
    assert extract_code_from_caption("код 999") == "999"
    assert extract_code_from_caption("284. Zo'raki folbin") == "284"
    assert extract_code_from_caption("101 - Forsaj 10") == "101"
    assert extract_code_from_caption("Salom dunyo") is None
    assert extract_code_from_caption("") is None
    assert extract_code_from_caption(None) is None

    # 2. extract_candidate_title
    caption = "🎬 Zo'raki Folbin\n\n📢 Homiy kanal: @Zakirovsfilms_bot"
    candidate = extract_candidate_title(caption)
    assert candidate is not None
    assert "Zo'raki Folbin" in candidate

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
    """catalog.json faylidan sarlavha bo'yicha qidirish testi."""
    item = MovieService.search_catalog_by_title("Zo'raki Folbin")
    assert item is not None
    assert str(item.get("c")) == "284"

    item2 = MovieService.search_catalog_by_title("Eys Ventura")
    assert item2 is not None
    assert str(item2.get("c")) == "283"

    assert MovieService.search_catalog_by_title("Mavjud_Bolmagan_Kino_XYZ_999") is None


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
    # send_video argumentlarini tekshirish
    call_kwargs = bot_mock.send_video.call_args.kwargs
    assert call_kwargs["chat_id"] == 12345
    assert call_kwargs["video"] == real_file_id
    assert call_kwargs["duration"] == 848
    assert "Zo'raki Folbin" in call_kwargs["caption"]
    # Photo yuborilmaganligiga ishonch hosil qilish
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
    # Placeholder bo'lgani sababli send_video chaqirilmasligi kerak
    assert bot_mock.send_video.called is False
    # send_photo yoki send_message chaqirilishi kerak
    assert bot_mock.send_photo.called or bot_mock.send_message.called


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
    # Monkeypatch get_session to return in_memory_session
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def fake_get_session():
        yield in_memory_session
    monkeypatch.setattr("handlers.movies.get_session", fake_get_session)

    # Monkeypatch admin tekshiruvi
    monkeypatch.setattr(config.__class__, "is_admin", lambda self, uid: uid == 7777)

    # 1. Admin bo'lmagan foydalanuvchi chaqirganda
    msg_non_admin = AsyncMock()
    msg_non_admin.from_user.id = 1234
    msg_non_admin.text = "/setmovie 284"
    msg_non_admin.reply = AsyncMock()
    await cmd_set_movie_video(msg_non_admin)
    assert "faqat adminlar uchun" in msg_non_admin.reply.call_args[0][0]

    # 2. Admin video xabarga Reply qilib chaqirganda
    msg_admin = AsyncMock()
    msg_admin.from_user.id = 7777
    msg_admin.text = "/setmovie 284"
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


@pytest.mark.asyncio
async def test_handle_incoming_movie_video(in_memory_session: AsyncSession, monkeypatch):
    """Foydalanuvchi video yuborganida captiondan kodni aniqlab bazaga saqlash testi."""
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def fake_get_session():
        yield in_memory_session
    monkeypatch.setattr("handlers.movies.get_session", fake_get_session)

    # 1. Captionda kod bo'lgan video
    msg = AsyncMock()
    msg.video = MagicMock()
    msg.video.file_id = "BAACAgIAAxkBAAE_INCOMING_FORWARD_VIDEO_ID_22222"
    msg.video.duration = 848
    msg.video.file_size = 418 * 1024 * 1024
    msg.document = None
    msg.caption = "🎬 Zo'raki Folbin\n\n🔢 Kodi: #284\n📢 Homiy kanal: @Zakirovsfilms_bot"
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

    # 2. Kod va nomi aniqlanmagan video kelganda tushunarli yordam berilishi
    msg_unknown = AsyncMock()
    msg_unknown.video = MagicMock()
    msg_unknown.video.file_id = "BAACAgIAAxkBAAE_UNKNOWN_VIDEO_ID"
    msg_unknown.video.duration = 100
    msg_unknown.video.file_size = 1000000
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

