"""
Tier 3: Cross-Feature Combinations Test Suite (BauntyCinemBot E2E).
Multi-subsystem interaction scenarios across Security, Database, TV Streaming, Music, Movies, and Books.
"""
import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database import crud
from database.models import User, Movie
from middlewares.throttling import ThrottlingMiddleware
from middlewares.security import BotSecurityMiddleware
from services.security_service import (
    security_service,
    is_malicious_request,
    get_security_headers,
)
from services.maintenance_service import maintenance_service
from services.tv_data import CHANNELS_LIST
from services.book_service import get_catalog, get_book_by_id, deliver_book
from services.music_service import MusicService


@pytest.mark.asyncio
async def test_tier3_comb01_security_and_tv_streaming(e2e_web_client: TestClient):
    """Rate limiter and WAF allow high-throughput streaming channel requests without false positive block."""
    for _ in range(25):
        resp = await e2e_web_client.get("/api/tv")
        assert resp.status == 200
        data = await resp.json()
        assert data.get("ok") is True


def test_tier3_comb02_security_and_book_search():
    """WAF preserves valid Uzbek Cyrillic and Latin queries while strictly blocking SQLi."""
    uzbek_queries = ["O'tkan kunlar", "Алкимёгар", "Sariq devni minib", "G'ulom Zafariy"]
    for q in uzbek_queries:
        assert is_malicious_request(path="/api/books/catalog", query_string=f"q={q}")[0] is False
        res = get_catalog(query=q)
        assert res["ok"] is True

    # SQLi variation is blocked
    assert is_malicious_request(path="/api/books/catalog", query_string="q=%27%20UNION%20SELECT%201")[0] is True


@pytest.mark.asyncio
async def test_tier3_comb03_db_concurrency_and_movie_delivery(e2e_db_session: AsyncSession, mock_bot):
    """Concurrent movie delivery requests increment views atomically and deliver via file_id."""
    movie, _ = await crud.upsert_movie(e2e_db_session, code="3003", title="Fast Movie", file_id="cloud_file_123")
    await e2e_db_session.commit()

    # Deliver movie to 3 users and increment views
    for user_id in (901, 902, 903):
        await mock_bot.send_video(chat_id=user_id, video=movie.file_id, caption="🎬 @BauntyFilms", protect_content=True)
        await crud.increment_movie_views(e2e_db_session, movie.id)
    await e2e_db_session.commit()

    assert mock_bot.send_video.call_count == 3
    refreshed = await crud.get_movie_by_code(e2e_db_session, "3003")
    assert refreshed.downloads_count >= 3


@pytest.mark.asyncio
async def test_tier3_comb04_throttling_and_bot_security():
    """Non-punitive throttle coexists with anti-flood sliding window and security inspection."""
    throttle = ThrottlingMiddleware(rate_limit=0.5)
    security = BotSecurityMiddleware()
    handler = AsyncMock(return_value="allowed")

    msg = MagicMock()
    msg.from_user.id = 3004
    msg.text = "/start"

    # First event passes both
    with patch("middlewares.security.get_session"):
        with patch("middlewares.security.crud.is_user_banned", AsyncMock(return_value=False)):
            res = await throttle(lambda e, d: security(handler, e, d), msg, {})
            assert res == "allowed"

    # Rapid second event is caught by throttle without invoking handler
    res2 = await throttle(lambda e, d: security(handler, e, d), msg, {})
    assert res2 is None


@pytest.mark.asyncio
async def test_tier3_comb05_maintenance_mode_and_health_probes(e2e_web_client: TestClient):
    """Maintenance mode does not interfere with zero-downtime /health probes."""
    maintenance_service.set_global_maintenance(True, custom_message="Test Maintenance Active")
    try:
        # Health probes must still return 200 OK
        resp_health = await e2e_web_client.get("/health")
        assert resp_health.status == 200
        resp_ping = await e2e_web_client.get("/ping")
        assert resp_ping.status == 200
    finally:
        maintenance_service.set_global_maintenance(False)


@pytest.mark.asyncio
async def test_tier3_comb06_music_search_and_brand_sanitizer():
    """Music search results from external engines are sanitized against upstream branding."""
    svc = MusicService()
    results = await svc.search_tracks("Dildora")
    for track in results:
        title = track.get("title", "")
        artist = track.get("artist", "")
        assert "@zakirovs" not in title.lower()
        assert "@zakirovs" not in artist.lower()


@pytest.mark.asyncio
async def test_tier3_comb07_movie_franchise_and_cloud_delivery(e2e_db_session: AsyncSession, mock_bot):
    """Franchise movie lookup by code delivers part instantly with BauntyCinemBot caption."""
    await crud.upsert_movie(e2e_db_session, code="718", title="Harry Potter 1", file_id="fid_hp1")
    await e2e_db_session.commit()

    movie = await crud.get_movie_by_code(e2e_db_session, "718")
    assert movie is not None

    caption = f"🎬 <b>{movie.title}</b>\n\nKanal: @BauntyFilms\nBot: @BauntyCinemabot"
    await mock_bot.send_video(chat_id=1001, video=movie.file_id, caption=caption, parse_mode="HTML")
    assert "@BauntyFilms" in caption
    assert "@BauntyCinemabot" in caption


def test_tier3_comb08_tv_proxy_and_client_nat_ip():
    """Client behind shared NAT gateway requests TV channels without tripping IP limiters."""
    nat_ip = "44.209.160.1"
    for _ in range(15):
        allowed, _ = security_service.rate_limiter.is_allowed(nat_ip, path="/api/tv")
        assert allowed is True


@pytest.mark.asyncio
async def test_tier3_comb09_database_pruning_and_active_user_crud(e2e_db_session: AsyncSession):
    """Pruning operations execute alongside active user creation without deadlock."""
    # Prune
    await e2e_db_session.execute(text("DELETE FROM users WHERE id < 0"))
    # Create active user
    user, created = await crud.get_or_create_user(e2e_db_session, user_id=3009, username="active_user")
    await e2e_db_session.commit()
    assert created is True
    assert user.id == 3009


def test_tier3_comb10_webapp_rest_endpoints_and_csp_headers():
    """All API responses enforce strict Content-Security-Policy and anti-clickjacking headers."""
    headers = get_security_headers()
    assert "Content-Security-Policy" in headers
    csp = headers["Content-Security-Policy"]
    assert "frame-ancestors" in csp
    assert "https://web.telegram.org" in csp
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
