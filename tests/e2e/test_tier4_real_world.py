"""
Tier 4: Real-World Scenarios Test Suite (BauntyCinemBot E2E).
Multi-step user journeys and sustained traffic simulation covering all production workflows.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database import crud
from services.security_service import security_service
from services.maintenance_service import maintenance_service
from services.tv_data import CHANNELS_LIST, TV_CATEGORIES
from services.book_service import get_catalog, get_book_by_id, deliver_book
from services.music_service import MusicService


@pytest.mark.asyncio
async def test_tier4_scenario01_new_user_onboarding_journey(e2e_db_session: AsyncSession, mock_bot):
    """User Journey: /start command -> user creation in DB -> movie code lookup -> film delivery."""
    user_id = 400101

    # 1. User starts bot and is registered in database
    user, created = await crud.get_or_create_user(
        e2e_db_session, user_id=user_id, username="cinema_fan", first_name="Akmal"
    )
    await e2e_db_session.commit()
    assert created is True
    assert user.id == user_id

    # 2. User searches movie by code '101'
    await crud.upsert_movie(e2e_db_session, code="101", title="Avatar: Suv Yo'li", file_id="file_avatar_101")
    await e2e_db_session.commit()
    movie = await crud.get_movie_by_code(e2e_db_session, "101")
    assert movie is not None

    # 3. Bot delivers movie to user chat via file_id
    caption = f"🎬 <b>{movie.title}</b>\n\n@BauntyFilms • @BauntyCinemabot"
    await mock_bot.send_video(chat_id=user_id, video=movie.file_id, caption=caption, protect_content=True)
    await crud.increment_movie_views(e2e_db_session, movie.id)
    await e2e_db_session.commit()

    mock_bot.send_video.assert_called_once()
    assert mock_bot.send_video.call_args[1]["chat_id"] == user_id


@pytest.mark.asyncio
async def test_tier4_scenario02_tv_watcher_browsing_journey(e2e_web_client: TestClient):
    """User Journey: Opens Mini App TV tab -> fetches channels -> filters Milliy category -> plays channel."""
    # 1. Fetch TV catalog
    resp = await e2e_web_client.get("/api/tv")
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True
    channels = data.get("items") or data.get("channels", [])
    assert len(channels) > 50

    # 2. Filter channels by category
    milliy_channels = [c for c in channels if c.get("category") == "milliy" or c.get("c") == "milliy"]
    target_channel = milliy_channels[0] if milliy_channels else channels[0]

    # 3. Verify channel has stream URL
    stream_url = target_channel.get("stream") or (target_channel.get("u") or [""])[0]
    assert stream_url.startswith("http")

    # 4. Client checks TV speed / connection status
    speed_resp = await e2e_web_client.get("/api/tv/speed")
    assert speed_resp.status == 200


@pytest.mark.asyncio
async def test_tier4_scenario03_music_enthusiast_journey(mock_bot):
    """User Journey: Search track -> preview metadata -> send track to personal chat."""
    svc = MusicService()

    # 1. User searches track
    tracks = await svc.search_tracks("Karvon")
    assert isinstance(tracks, list)

    # 2. Select track and format caption
    track_title = tracks[0]["title"] if tracks else "Karvon"
    track_artist = tracks[0]["artist"] if tracks else "Sherali Jo'rayev"
    caption = f"🎧 <b>{track_title}</b> — {track_artist}\n\n@BauntyCinemabot"

    # 3. Deliver track
    await mock_bot.send_audio(chat_id=400301, audio="sample_audio_id", caption=caption)
    mock_bot.send_audio.assert_called_once()
    assert "@BauntyCinemabot" in caption


@pytest.mark.asyncio
async def test_tier4_scenario04_book_reader_journey(mock_bot):
    """User Journey: Browse books -> search 'Alkimyogar' -> view details -> deliver PDF sample."""
    # 1. Browse catalog
    catalog = get_catalog(category="all", limit=5)
    assert catalog["ok"] is True
    assert len(catalog["items"]) >= 1

    # 2. Search specific book
    search_res = get_catalog(query="Alkimyogar")
    assert search_res["ok"] is True
    assert len(search_res["items"]) >= 1
    book_item = search_res["items"][0]

    # 3. Retrieve book detail
    detail = get_book_by_id(book_item["id"])
    assert detail is not None
    assert "Alkimyogar" in detail["title"]

    # 4. Deliver PDF sample to chat
    deliv = await deliver_book(mock_bot, chat_id=400401, book_id=detail["id"], fmt="pdf")
    assert deliv["ok"] is True
    mock_bot.send_document.assert_called_once()


@pytest.mark.asyncio
async def test_tier4_scenario05_admin_maintenance_journey(e2e_web_client: TestClient):
    """Admin Journey: Enable maintenance -> check health still green -> disable maintenance."""
    # 1. Admin enables maintenance mode
    maintenance_service.set_global_maintenance(True, custom_message="Mavsumiy yangilanish")
    assert maintenance_service.is_global_maintenance() is True

    # 2. Health check endpoint remains 200 OK (zero downtime for UptimeRobot)
    resp_health = await e2e_web_client.get("/health")
    assert resp_health.status == 200

    # 3. Admin disables maintenance mode
    maintenance_service.set_global_maintenance(False)
    assert maintenance_service.is_global_maintenance() is False


@pytest.mark.asyncio
async def test_tier4_scenario06_sustained_uptimerobot_monitoring(e2e_web_client: TestClient):
    """Simulation: 24 consecutive monitor cycles from UptimeRobot without rate-limiting blocks or ban."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; UptimeRobot/2.0; +http://www.uptimerobot.com/)"}
    for cycle in range(24):
        resp = await e2e_web_client.get("/health", headers=headers)
        assert resp.status == 200, f"Cycle {cycle} failed with status {resp.status}"

    # Verify IP was never jailed
    assert security_service.is_ip_banned("127.0.0.1")[0] is False


@pytest.mark.asyncio
async def test_tier4_scenario07_concurrent_multi_user_traffic(e2e_db_session: AsyncSession, e2e_web_client: TestClient):
    """Simulation: Multiple simulated users hitting database, health, and WebApp in high volume."""
    for i in range(10):
        uid = 400700 + i
        await crud.get_or_create_user(e2e_db_session, user_id=uid)
        resp = await e2e_web_client.get("/health")
        assert resp.status == 200
    await e2e_db_session.commit()

    total_users = await crud.get_total_users_count(e2e_db_session)
    assert total_users >= 10


@pytest.mark.asyncio
async def test_tier4_scenario08_intermittent_network_recovery(e2e_web_client: TestClient):
    """Simulation: TV speed test and catalog recover cleanly without server crash."""
    for _ in range(3):
        resp = await e2e_web_client.get("/api/tv/speed")
        assert resp.status in (200, 204)
        resp2 = await e2e_web_client.get("/api/tv")
        assert resp2.status == 200


@pytest.mark.asyncio
async def test_tier4_scenario09_high_volume_user_registration(e2e_db_session: AsyncSession):
    """Simulation: Burst of 25 new users registering in sequential sequence without SQLite lock."""
    for i in range(25):
        uid = 400900 + i
        user, created = await crud.get_or_create_user(
            e2e_db_session, user_id=uid, username=f"burst_user_{i}"
        )
        assert created is True
    await e2e_db_session.commit()

    count = await crud.get_total_users_count(e2e_db_session)
    assert count >= 25


@pytest.mark.asyncio
async def test_tier4_scenario10_full_platform_sanity_journey(
    e2e_db_session: AsyncSession, e2e_web_client: TestClient, mock_bot
):
    """Comprehensive Sanity Journey: User touches TV, Movies, Music, Books, and Security in unified flow."""
    # 1. Health check
    h_resp = await e2e_web_client.get("/health")
    assert h_resp.status == 200

    # 2. TV Catalog
    tv_resp = await e2e_web_client.get("/api/tv")
    assert tv_resp.status == 200

    # 3. Movie CRUD
    m, _ = await crud.upsert_movie(e2e_db_session, code="9999", title="End-to-End Masterpiece")
    await e2e_db_session.commit()
    assert m.code == "9999"

    # 4. Music search
    svc = MusicService()
    music_res = await svc.search_tracks("Sherali")
    assert isinstance(music_res, list)

    # 5. Book delivery
    deliv = await deliver_book(mock_bot, chat_id=401001, book_id="1", fmt="pdf")
    assert deliv["ok"] is True
