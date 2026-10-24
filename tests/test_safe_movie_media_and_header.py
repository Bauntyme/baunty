import os
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, Video, Document

from services.movie_service import MovieService, _DOWNLOAD_SEMAPHORE
from config import BASE_DIR


def test_header_css_classes_exist():
    """Verify clean dedicated headers and scrollable segment classes exist in stylesheets."""
    # Check mafia.css
    mafia_css = (BASE_DIR / "webapp" / "mafia.css").read_text(encoding="utf-8")
    assert ".mf-head-clean" in mafia_css
    assert ".mf-seg" in mafia_css

    # Check kaloriya.css
    kal_css = (BASE_DIR / "webapp" / "kaloriya.css").read_text(encoding="utf-8")
    assert ".kl-head-clean" in kal_css
    assert ".kl-seg" in kal_css

    # Check rasxod.css
    rasxod_css = (BASE_DIR / "webapp" / "rasxod.css").read_text(encoding="utf-8")
    assert ".rx-head-clean" in rasxod_css
    assert ".rx-seg" in rasxod_css

    # Check zk.css
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")
    assert ".mf-seg" in zk_css
    assert ".rx-seg" in zk_css
    assert ".kl-seg" in zk_css

    # Check index.html seg styles
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    assert "overflow-x:auto" in index_html or "overflow-x: auto" in index_html
    assert "white-space:nowrap" in index_html or "white-space: nowrap" in index_html


def test_submodule_headers_use_clean_markup():
    """Verify mafia.js, kaloriya.js, and rasxod.js render clean dedicated headers."""
    mafia_js = (BASE_DIR / "webapp" / "mafia.js").read_text(encoding="utf-8")
    assert "mf-head-clean" in mafia_js
    assert "homeback" in mafia_js
    assert "window.ZHub" in mafia_js

    kal_js = (BASE_DIR / "webapp" / "kaloriya.js").read_text(encoding="utf-8")
    assert "kl-head-clean" in kal_js
    assert "rootHead()" in kal_js
    assert "homeback" in kal_js

    rasxod_js = (BASE_DIR / "webapp" / "rasxod.js").read_text(encoding="utf-8")
    assert "rx-head-clean" in rasxod_js
    assert "rootHead()" in rasxod_js
    assert "homeback" in rasxod_js


def test_hub_selector_and_click_delegation():
    """Verify SEG selector excludes sub-module segments and delegated click listener exists."""
    app_js = (BASE_DIR / "webapp" / "app.js").read_text(encoding="utf-8")
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")

    # Both app.js and index.html should not inject buttons into .mf-seg, .rx-seg, .kl-seg
    assert ".mf-seg" not in app_js.split("const SEG =")[1].split(";")[0]
    assert ".mf-seg" not in index_html.split("const SEG =")[1].split(";")[0]

    # Delegated click listener exists
    assert 'closest(".zk-hubbtn")' in app_js
    assert 'closest(".zk-hubbtn")' in index_html


@pytest.mark.asyncio
async def test_download_semaphore_is_single_concurrency():
    """Verify strict single-concurrency lock is configured."""
    assert isinstance(_DOWNLOAD_SEMAPHORE, asyncio.Semaphore)
    # Acquire and check that second acquire blocks if timeout
    assert _DOWNLOAD_SEMAPHORE._value == 1


@pytest.mark.asyncio
async def test_download_and_upload_media_double_check_cache():
    """If movie file was already cached by a parallel request, send immediately from cloud."""
    bot = AsyncMock()
    mock_session = AsyncMock()

    cached_item = MagicMock()
    cached_item.file_id = "BAACAgIAAxkBAAIBYWRlYWxfaWQyMDI2X3ZlcmlmaWVk"
    cached_item.file_type = "video"
    cached_item.duration = 7200

    with patch("database.crud.get_movie_file", new_callable=AsyncMock) as mock_get_mf:
        mock_get_mf.return_value = cached_item

        res = await MovieService.download_and_upload_media_on_demand(
            bot=bot,
            chat_id=123456,
            code="718",
            part=1,
            source_url="https://sample.com/movie.mp4",
            caption="Test Caption",
            session=mock_session
        )

        assert bot.send_video.called
        assert bot.send_video.call_args[1]["video"] == cached_item.file_id
        assert bot.send_video.call_args[1]["chat_id"] == 123456


@pytest.mark.asyncio
async def test_download_and_upload_streaming_and_cleanup_on_success():
    """Verify chunked download, upload, DB persistence, and finally cleanup."""
    bot = AsyncMock()
    mock_session = AsyncMock()

    # Mock response message from Telegram
    mock_sent_msg = MagicMock(spec=Message)
    mock_video = MagicMock(spec=Video)
    mock_video.file_id = "BAACAgIAAxkBAAI_NEW_FILE_ID_UPLOADED_12345"
    mock_video.duration = 3600
    mock_video.file_size = 50000000
    mock_sent_msg.video = mock_video
    mock_sent_msg.document = None
    bot.send_video.return_value = mock_sent_msg

    # Mock aiohttp stream
    chunks = [b"A" * (512 * 1024), b"B" * (512 * 1024)]  # total 1MB

    class MockContent:
        async def iter_chunked(self, n):
            for c in chunks:
                yield c

    class MockResp:
        status = 200
        content = MockContent()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def get(self, url):
            return MockResp()

    v_dir = BASE_DIR / "data" / "videos"
    temp_target = v_dir / "temp_download_9999_1.mp4"

    with patch("database.crud.get_movie_file", new_callable=AsyncMock) as mock_get_mf, \
         patch("database.crud.get_movie_by_code", new_callable=AsyncMock) as mock_get_m, \
         patch("aiohttp.ClientSession", side_effect=MockSession), \
         patch("database.crud.set_movie_video", new_callable=AsyncMock) as mock_set_vid, \
         patch("database.crud.save_movie_file", new_callable=AsyncMock) as mock_save_mf:

        mock_get_mf.return_value = None
        mock_get_m.return_value = None

        res = await MovieService.download_and_upload_media_on_demand(
            bot=bot,
            chat_id=55555,
            code="9999",
            part=1,
            source_url="https://example.com/test_movie.mp4",
            caption="Test Caption",
            session=mock_session,
            display_title="Test Movie #9999"
        )

        assert res == mock_sent_msg
        assert bot.send_video.called

        # Verify DB persistence
        assert mock_set_vid.called
        assert mock_set_vid.call_args[1]["file_id"] == "BAACAgIAAxkBAAI_NEW_FILE_ID_UPLOADED_12345"
        assert mock_save_mf.called
        assert mock_save_mf.call_args[1]["file_id"] == "BAACAgIAAxkBAAI_NEW_FILE_ID_UPLOADED_12345"

        # Verify temp file cleanup in finally block
        assert not temp_target.exists()


@pytest.mark.asyncio
async def test_download_and_upload_cleanup_on_error():
    """Verify temporary file is guaranteed deleted in finally block even if upload fails."""
    bot = AsyncMock()
    mock_session = AsyncMock()
    bot.send_video.side_effect = RuntimeError("Network error during upload")
    bot.send_document.side_effect = RuntimeError("Document fallback error")

    chunks = [b"Z" * (200 * 1024)]

    class MockContent:
        async def iter_chunked(self, n):
            for c in chunks:
                yield c

    class MockResp:
        status = 200
        content = MockContent()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def get(self, url):
            return MockResp()

    v_dir = BASE_DIR / "data" / "videos"
    temp_target = v_dir / "temp_download_8888_1.mp4"

    with patch("database.crud.get_movie_file", new_callable=AsyncMock) as mock_get_mf, \
         patch("database.crud.get_movie_by_code", new_callable=AsyncMock) as mock_get_m, \
         patch("aiohttp.ClientSession", side_effect=MockSession):

        mock_get_mf.return_value = None
        mock_get_m.return_value = None

        res = await MovieService.download_and_upload_media_on_demand(
            bot=bot,
            chat_id=55555,
            code="8888",
            part=1,
            source_url="https://example.com/err_movie.mp4",
            caption="Test Caption",
            session=mock_session
        )

        assert res is None
        # Must be deleted despite errors
        assert not temp_target.exists()


@pytest.mark.asyncio
async def test_deliver_movie_impl_falls_back_to_on_demand_when_url_send_fails():
    """When direct send_video via URL fails, deliver_movie should trigger on-demand downloader."""
    bot = AsyncMock()
    mock_session = AsyncMock()

    # Direct send_video with URL raises Telegram error
    bot.send_video.side_effect = Exception("TelegramBadRequest: wrong file identifier / HTTP URL specified")

    mock_movie = MagicMock()
    mock_movie.id = 1
    mock_movie.code = "123"
    mock_movie.title = "Test Movie"
    mock_movie.description = "Test Desc"
    mock_movie.file_id = ""

    mock_downloaded_msg = MagicMock()

    with patch("database.crud.get_movie_by_code", new_callable=AsyncMock) as mock_get_m, \
         patch("database.crud.get_movie_file", new_callable=AsyncMock) as mock_get_mf, \
         patch.object(MovieService, "resolve_video_source", return_value={"url": "https://cdn.example.com/movie.mp4"}), \
         patch.object(MovieService, "download_and_upload_media_on_demand", new_callable=AsyncMock) as mock_dl:

        mock_get_m.return_value = mock_movie
        mock_get_mf.return_value = None
        mock_dl.return_value = mock_downloaded_msg

        result = await MovieService._deliver_movie_impl(
            bot=bot,
            chat_id=111,
            code="123",
            part=1,
            session=mock_session
        )

        assert result is True
        assert mock_dl.called


def test_movie_keyboards_download_button_uses_callback_data():
    """Verify 'Yuklab olish' uses callback_data instead of bare URL to deliver media in Telegram."""
    from keyboards.inline import movie_item_keyboard, movie_parts_keyboard

    # Test movie_item_keyboard
    kb = movie_item_keyboard("777", download_url="https://server.example.com/download/777.mp4")
    dl_btns = [btn for row in kb.inline_keyboard for btn in row if "Yuklab olish" in btn.text]
    assert len(dl_btns) == 1
    assert dl_btns[0].callback_data == "download_movie:777:1"
    assert dl_btns[0].url is None

    # Test movie_parts_keyboard
    parts_kb = movie_parts_keyboard("777", total_parts=5, current_part=3, download_url="https://server.example.com/download/777_3.mp4")
    parts_dl_btns = [btn for row in parts_kb.inline_keyboard for btn in row if "Yuklab olish" in btn.text]
    assert len(parts_dl_btns) == 1
    assert parts_dl_btns[0].callback_data == "download_movie:777:3"
    assert parts_dl_btns[0].url is None


@pytest.mark.asyncio
async def test_download_and_upload_media_double_check_cache_in_movies_table():
    """If movie file was already cached in movies table, deliver immediately from cloud."""
    bot = AsyncMock()
    mock_session = AsyncMock()

    cached_movie = MagicMock()
    cached_movie.file_id = "BAACAgIAAxkBAAIBYWRlYWxfaWQyMDI2X21vdmllc192ZXJpZmllZA"
    cached_movie.file_type = "video"
    cached_movie.duration = 5400

    with patch("database.crud.get_movie_file", new_callable=AsyncMock) as mock_get_mf, \
         patch("database.crud.get_movie_by_code", new_callable=AsyncMock) as mock_get_m:

        mock_get_mf.return_value = None
        mock_get_m.return_value = cached_movie

        res = await MovieService.download_and_upload_media_on_demand(
            bot=bot,
            chat_id=123456,
            code="555",
            part=1,
            source_url="https://sample.com/movie555.mp4",
            caption="Test Caption",
            session=mock_session
        )

        assert bot.send_video.called
        assert bot.send_video.call_args[1]["video"] == cached_movie.file_id
        assert bot.send_video.call_args[1]["chat_id"] == 123456

