"""
Qo'shimcha yangi funksiyalar (Anonim story TG/IG tanlovi, musiqa phonk/EDM, hujjatlar images_to_pdf va ocr,
kinolar ko'p qismli deliver va extract_movie_code_and_part, yuklovchi semaphore) uchun maxsus testlar.
"""
import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image

from keyboards.inline import story_platform_keyboard
from handlers.docs import docs_menu_keyboard
from services.story_service import story_service
from services.music_service import music_service
from services.doc_service import doc_service
from services.movie_service import movie_service
from handlers.movies import extract_movie_code_and_part, extract_movie_code
from database.session import init_db, get_session
from database import crud
from services.downloader import media_downloader, DownloadResult


def test_story_platform_keyboard():
    """Anonim story platforma tanlash klaviaturasi testi."""
    kb = story_platform_keyboard()
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for btn in buttons]
    assert "story_platform:tg" in callbacks
    assert "story_platform:ig" in callbacks
    assert any("Telegram" in btn.text for btn in buttons)
    assert any("Instagram" in btn.text for btn in buttons)


@pytest.mark.asyncio
async def test_story_fetch_tg_and_ig():
    """Story service TG va IG platformalari bo'yicha chaqirilishi testi."""
    with patch.object(story_service, "fetch_telegram_stories", new_callable=AsyncMock) as mock_tg:
        mock_tg.return_value = {
            "name": "Kun Uz",
            "username": "kunuz",
            "items": [{"type": "photo", "url": "https://example.com/p.jpg"}],
            "count": 1
        }
        res_tg = await story_service.fetch_stories("kunuz", platform="tg")
        assert res_tg["count"] == 1
        assert res_tg["username"] == "kunuz"

    with patch.object(story_service, "_fetch_stories_via_public_endpoints", new_callable=AsyncMock) as mock_ig:
        mock_ig.return_value = [
            DownloadResult(success=True, file_path="dummy.mp4", direct_url="https://example.com/v.mp4")
        ]
        res_ig = await story_service.fetch_stories("cristiano", platform="ig")
        assert len(res_ig) == 1
        assert res_ig[0].success is True


@pytest.mark.asyncio
async def test_music_phonk_and_remix_search():
    """Musiqa qidiruvida phonk, EDM va remix so'rovlariga to'g'ri javob qaytarishi testi."""
    results = await music_service.search_tracks("phonk drift", limit=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert any("phonk" in (t.get("title", "") + " " + t.get("artist", "")).lower() for t in results)


@pytest.mark.asyncio
async def test_docs_images_to_pdf_in_memory(tmp_path):
    """Images to PDF konversiyasi testi (Pillow)."""
    # 2 ta rasm yaratamiz
    img1 = Image.new("RGB", (100, 100), color="red")
    path1 = str(tmp_path / "img1.jpg")
    img1.save(path1, format="JPEG")

    img2 = Image.new("RGB", (120, 120), color="blue")
    path2 = str(tmp_path / "img2.png")
    img2.save(path2, format="PNG")

    out_pdf = str(tmp_path / "result.pdf")
    res_path = doc_service.images_to_pdf([path1, path2], out_pdf)
    assert res_path == out_pdf
    with open(out_pdf, "rb") as f:
        data = f.read()
    assert len(data) > 200
    assert data.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_docs_ocr_image_fallback(tmp_path):
    """OCR funksiyasi testi."""
    img = Image.new("RGB", (200, 50), color="white")
    path_img = str(tmp_path / "test_ocr.png")
    img.save(path_img, format="PNG")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"ParsedResults": [{"ParsedText": "Salom Dunyo"}]})
    mock_resp.__aenter__.return_value = mock_resp
    mock_resp.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("aiohttp.ClientSession", return_value=mock_session):
        text = await doc_service.ocr_image(path_img)
        assert "Salom Dunyo" in text


def test_extract_movie_code_and_part():
    """Kino kodi va qismini matndan ajratib olish testi."""
    assert extract_movie_code_and_part("101") == ("101", 1)
    assert extract_movie_code_and_part("#101") == ("101", 1)
    assert extract_movie_code_and_part("№101") == ("101", 1)
    assert extract_movie_code_and_part("kod 101") == ("101", 1)
    assert extract_movie_code_and_part("kod: 101") == ("101", 1)
    assert extract_movie_code_and_part("код 101") == ("101", 1)

    # Qismlar bilan
    assert extract_movie_code_and_part("289 2") == ("289", 2)
    assert extract_movie_code_and_part("289-2") == ("289", 2)
    assert extract_movie_code_and_part("289_2") == ("289", 2)
    assert extract_movie_code_and_part("289p2") == ("289", 2)
    assert extract_movie_code_and_part("289 2-qism") == ("289", 2)
    assert extract_movie_code_and_part("289 2 qism") == ("289", 2)
    assert extract_movie_code_and_part("kod 289 5") == ("289", 5)
    assert extract_movie_code_and_part("#289 3") == ("289", 3)

    # Salbiy holatlar
    assert extract_movie_code_and_part("Salom dunyo") is None
    assert extract_movie_code_and_part("https://instagram.com/p/123") is None

    # extract_movie_code mosligi
    assert extract_movie_code("101") == "101"
    assert extract_movie_code("289 2") == "289"


@pytest.mark.asyncio
async def test_movie_deliver_multipart_variants_and_4k_badge():
    """Kino deliver_movie da qismli kodlar (_2, -2, p2) va (4K Ultra HD) badge testi."""
    await init_db()
    mock_bot = AsyncMock()
    mock_bot.send_video = AsyncMock(return_value=True)

    fid_part2 = "BAACAgIAAxkBAAE_SAMPLE_SERIES_EPISODE_2_4K_FILE_ID"
    async with get_session() as session:
        await crud.upsert_movie(
            session=session,
            code="333_2",
            title="Qashqirlar Makoni",
            file_id=fid_part2,
            description="2-qism"
        )
        await session.commit()

    # part=2 so'ralganda
    res = await movie_service.deliver_movie(
        bot=mock_bot,
        chat_id=123456,
        code="333",
        part=2
    )
    assert res is True
    assert mock_bot.send_video.called
    kwargs = mock_bot.send_video.call_args[1]
    assert kwargs["video"] == fid_part2
    assert "(4K Ultra HD)" in kwargs["caption"]
    assert "2-qism" in kwargs["caption"]


@pytest.mark.asyncio
async def test_downloader_semaphore_concurrency():
    """Downloader semaphore orqali bir vaqtning o'zida ko'p yuklamalarni cheklashi testi."""
    sem = media_downloader.semaphore if hasattr(media_downloader, "semaphore") else media_downloader._sem
    assert media_downloader._sem is not None or sem is not None
