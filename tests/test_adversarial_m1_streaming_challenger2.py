"""
Adversarial Stress Test Suite for Milestone M1 (Challenger 2)
Focus Areas:
1. Fayllar Stream Token Expiration Detection (past, near-future cushion, far-future, missing, malformed).
2. Fayllar Token Stripping (multi-token, aliased params, tricky queries, unicode, malformed).
3. HTTP 410 Gone & 403 Forbidden Auto-Refresh & Retry during Video Stream Downloads.
4. Web Server handle_asil_stream Recovery (expired tokens, HEAD probe 410/403, timeout resilience, bad inputs).
5. Performance & Batch Resilience Stress Test.
"""
import os
import re
import time
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from config import BASE_DIR
from services.asilmedia_service import (
    AsilmediaService,
    asilmedia_service,
    strip_fayllar_token,
    needs_fayllar_sign,
)
from services.movie_service import MovieService
from services.web_server import handle_asil_stream


# ==============================================================================
# 1. ADVERSARIAL TOKEN EXPIRATION DETECTION (is_token_expired)
# ==============================================================================

class TestTokenExpirationDetection:
    """Stress-test timestamp scenarios against AsilmediaService.is_token_expired."""

    def test_past_timestamps_are_expired(self):
        """Past timestamps (epoch, historic, seconds ago) must strictly return True."""
        now = int(time.time())
        cases = [
            f"https://30.fayllar.com/video.mp4?token=abc&expires=0",
            f"https://30.fayllar.com/video.mp4?token=abc&expires=1",
            f"https://30.fayllar.com/video.mp4?token=abc&expires=1000000000",  # Year 2001
            f"https://30.fayllar.com/video.mp4?token=abc&expires=1600000000",  # Year 2020
            f"https://30.fayllar.com/video.mp4?token=abc&expires={now - 86400}", # 1 day ago
            f"https://30.fayllar.com/video.mp4?token=abc&expires={now - 3600}",  # 1 hour ago
            f"https://30.fayllar.com/video.mp4?token=abc&expires={now - 60}",    # 1 minute ago
            f"https://30.fayllar.com/video.mp4?token=abc&expires={now - 1}",     # 1 second ago
            f"https://30.fayllar.com/video.mp4?token=abc&expires={now}",         # Exact current second
        ]
        for url in cases:
            assert AsilmediaService.is_token_expired(url) is True, f"Failed for {url}"

    def test_near_future_safety_cushion_is_expired(self):
        """Tokens expiring within 30-second safety cushion must return True to prevent mid-stream failure."""
        now = int(time.time())
        cushion_cases = [
            now + 1,
            now + 5,
            now + 10,
            now + 20,
            now + 29,
            now + 30,  # Exactly boundary
        ]
        for ts in cushion_cases:
            url = f"https://30.fayllar.com/video.mp4?token=abc&expires={ts}"
            assert AsilmediaService.is_token_expired(url) is True, f"Expected expired within cushion: {ts}"

    def test_valid_future_timestamps_are_not_expired(self):
        """Tokens expiring comfortably in the future (>30s) must return False."""
        now = int(time.time())
        future_cases = [
            now + 31,
            now + 45,
            now + 60,
            now + 3600,       # 1 hour
            now + 86400,      # 1 day
            now + 86400 * 30, # 30 days
            now + 86400 * 365,# 1 year
        ]
        for ts in future_cases:
            url = f"https://30.fayllar.com/video.mp4?token=abc&expires={ts}"
            assert AsilmediaService.is_token_expired(url) is False, f"Expected active for {ts}"

    def test_alternative_expiration_parameter_alias(self):
        """Support parameter 'e' as expiration alias in addition to 'expires'."""
        now = int(time.time())
        past_url = f"https://30.fayllar.com/video.mp4?token=abc&e={now - 50}"
        future_url = f"https://30.fayllar.com/video.mp4?token=abc&e={now + 3600}"
        assert AsilmediaService.is_token_expired(past_url) is True
        assert AsilmediaService.is_token_expired(future_url) is False

    def test_malformed_and_edge_case_expiration_values(self):
        """Non-numeric, float, negative, or missing expires must not raise exceptions."""
        malformed = [
            "https://30.fayllar.com/video.mp4?token=abc",            # Missing expires
            "https://30.fayllar.com/video.mp4?token=abc&expires=",   # Empty expires
            "https://30.fayllar.com/video.mp4?token=abc&expires=abc",# Alphabetic
            "https://30.fayllar.com/video.mp4?token=abc&expires=null",# Null string
            "https://30.fayllar.com/video.mp4?token=abc&expires=1731600000.5", # Float
            "https://30.fayllar.com/video.mp4?token=abc&expires=-100", # Negative
            "https://30.fayllar.com/video.mp4",                     # No query at all
            "",                                                     # Empty
            "   ",                                                  # Whitespace
            None,                                                   # None
        ]
        for url in malformed:
            # Must safely return False without unhandled exception
            assert AsilmediaService.is_token_expired(url) is False


# ==============================================================================
# 2. ADVERSARIAL TOKEN STRIPPING (strip_fayllar_token)
# ==============================================================================

class TestTokenStrippingAdversarial:
    """Stress-test strip_fayllar_token with tricky, malformed, and multi-param URLs."""

    def test_basic_token_and_expires_removal(self):
        url = "https://30.fayllar.com/17638/1-qism.mp4?token=abc123xyz&expires=1731600000"
        expected = "https://30.fayllar.com/17638/1-qism.mp4"
        assert strip_fayllar_token(url) == expected

    def test_multiple_tokens_and_expires_params(self):
        url = "https://30.fayllar.com/video.mp4?token=first&token=second&expires=100&expires=200"
        expected = "https://30.fayllar.com/video.mp4"
        assert strip_fayllar_token(url) == expected

    def test_token_aliases_st_and_e_removal(self):
        url = "https://30.fayllar.com/video.mp4?st=sec_token_99&e=1731600000"
        expected = "https://30.fayllar.com/video.mp4"
        assert strip_fayllar_token(url) == expected

    def test_preserves_unrelated_query_parameters(self):
        url = "https://30.fayllar.com/video.mp4?v=1080p&token=secret&lang=uz&expires=99999&auth=1"
        stripped = strip_fayllar_token(url)
        assert "token" not in stripped
        assert "expires" not in stripped
        assert "v=1080p" in stripped
        assert "lang=uz" in stripped
        assert "auth=1" in stripped

    def test_special_characters_and_spaces_in_path(self):
        url = "https://30.fayllar.com/17638/Qasoskorlar%20(1-qism)%20[HD].mp4?token=xyz&expires=123"
        stripped = strip_fayllar_token(url)
        assert "token" not in stripped
        assert "expires" not in stripped
        assert "Qasoskorlar%20(1-qism)%20[HD].mp4" in stripped

    def test_cyrillic_in_path_and_query(self):
        url = "https://30.fayllar.com/files/тест_видео.mp4?nomi=тест&token=abc&expires=999"
        stripped = strip_fayllar_token(url)
        assert "token" not in stripped
        assert "expires" not in stripped
        assert "тест_видео.mp4" in stripped
        assert "nomi" in stripped

    def test_url_with_port_and_fragment(self):
        url = "https://30.fayllar.com:8443/video.mp4?token=abc&expires=123#t=30"
        stripped = strip_fayllar_token(url)
        assert "token" not in stripped
        assert "expires" not in stripped
        assert ":8443" in stripped
        assert stripped.endswith("#t=30")

    def test_empty_missing_query_and_none(self):
        assert strip_fayllar_token(None) == ""
        assert strip_fayllar_token("") == ""
        assert strip_fayllar_token("   ") == ""
        assert strip_fayllar_token("https://30.fayllar.com/video.mp4") == "https://30.fayllar.com/video.mp4"
        assert strip_fayllar_token("https://30.fayllar.com/video.mp4?") == "https://30.fayllar.com/video.mp4?"


# ==============================================================================
# 3. NEEDS_FAYLLAR_SIGN ADVERSARIAL MATRIX
# ==============================================================================

class TestNeedsFayllarSignAdversarial:
    """Stress-test needs_fayllar_sign across domain names, protocols, and states."""

    def test_am_protocol_always_needs_sign(self):
        assert needs_fayllar_sign("am:17638:abcdef123456") is True
        assert needs_fayllar_sign("AM:999:hash") is True
        assert needs_fayllar_sign("am:0:test") is True

    def test_unsigned_fayllar_domains(self):
        domains = [
            "https://30.fayllar.com/17638/1.mp4",
            "https://fayllar1.ru/kino/2.mp4",
            "http://cdn.fayllar.org/3.mp4",
            "https://server2.fayllar.uz/4.mp4",
        ]
        for u in domains:
            assert needs_fayllar_sign(u) is True

    def test_expired_signed_fayllar_domain(self):
        now = int(time.time())
        expired = f"https://30.fayllar.com/video.mp4?token=tok123&expires={now - 100}"
        assert needs_fayllar_sign(expired) is True

    def test_active_signed_fayllar_domain(self):
        now = int(time.time())
        active = f"https://30.fayllar.com/video.mp4?token=tok123&expires={now + 3600}"
        assert needs_fayllar_sign(active, force=False) is False
        # Force must override
        assert needs_fayllar_sign(active, force=True) is True

    def test_non_fayllar_domains_never_need_fayllar_sign(self):
        non_fayllar = [
            "https://youtube.com/watch?v=123",
            "https://vimeo.com/video.mp4",
            "https://mycdn.net/stream.mp4",
            "https://static.asilmedia.org/poster.jpg",
        ]
        for u in non_fayllar:
            assert needs_fayllar_sign(u, force=False) is False
            assert needs_fayllar_sign(u, force=True) is False


# ==============================================================================
# 4. DOWNLOAD_VIDEO_STREAM 410 GONE & 403 FORBIDDEN AUTO-REFRESH & RETRY
# ==============================================================================

class TestDownloadVideoStreamRecovery:
    """Stress-test download_video_stream when upstream returns 410 or 403."""

    @pytest.mark.asyncio
    async def test_upstream_410_gone_triggers_resign_and_retries_successfully(self, tmp_path):
        """Simulate upstream 410 Gone -> automatically strips token, re-signs, retries and saves video."""
        svc = AsilmediaService()
        initial_url = "https://30.fayllar.com/video.mp4?token=revoked_410&expires=1999999999"
        refreshed_url = "https://30.fayllar.com/video.mp4?token=brand_new_token&expires=2000000000"
        dest_file = tmp_path / "test_download.mp4"

        call_history = []

        class MockResponse:
            def __init__(self, status, url):
                self.status = status
                self.headers = {"Content-Type": "video/mp4", "Content-Length": "4096"}
                self.url = url

                async def iter_chunks(size):
                    # Valid MP4 header (ftyp box: 16 bytes) + 4080 payload bytes = 4096 bytes
                    yield b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00" + b"\x00" * 4080

                content = MagicMock()
                content.iter_chunked = iter_chunks
                self.content = content

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        def mocked_session_get(url, *args, **kwargs):
            call_history.append(url)
            if "revoked_410" in url:
                return MockResponse(410, url)
            else:
                return MockResponse(200, url)

        with patch.object(svc, "resolve_stream_url", return_value=refreshed_url) as mock_resolve, \
             patch("aiohttp.ClientSession.get", side_effect=mocked_session_get):
            res = await svc.download_video_stream(initial_url, destination_path=dest_file)

        assert res is not None
        assert res.exists()
        assert res.stat().st_size == 4096
        # Exactly 2 network calls: 1st failed with 410, 2nd succeeded with fresh token
        assert len(call_history) == 2
        assert "revoked_410" in call_history[0]
        assert "brand_new_token" in call_history[1]
        mock_resolve.assert_called_once_with("https://30.fayllar.com/video.mp4", force_refresh=True)

    @pytest.mark.asyncio
    async def test_upstream_403_forbidden_triggers_resign_and_retries_successfully(self, tmp_path):
        """Simulate upstream 403 Forbidden -> triggers same auto-refresh and succeeds."""
        svc = AsilmediaService()
        initial_url = "https://30.fayllar.com/video.mp4?token=forbidden_403&expires=1999999999"
        refreshed_url = "https://30.fayllar.com/video.mp4?token=brand_new_token_403&expires=2000000000"
        dest_file = tmp_path / "test_download_403.mp4"

        call_history = []

        class MockResponse:
            def __init__(self, status):
                self.status = status
                self.headers = {"Content-Type": "video/mp4", "Content-Length": "2048"}

                async def iter_chunks(size):
                    yield b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00" + b"\x01" * 2024

                content = MagicMock()
                content.iter_chunked = iter_chunks
                self.content = content

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        def mocked_session_get(url, *args, **kwargs):
            call_history.append(url)
            if "forbidden_403" in url:
                return MockResponse(403)
            return MockResponse(200)

        with patch.object(svc, "resolve_stream_url", return_value=refreshed_url) as mock_resolve, \
             patch("aiohttp.ClientSession.get", side_effect=mocked_session_get):
            res = await svc.download_video_stream(initial_url, destination_path=dest_file)

        assert res is not None
        assert res.exists()
        assert len(call_history) == 2
        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_410_recovery_aborts_when_resign_fails_or_returns_identical(self, tmp_path):
        """When re-signing returns None or the exact same failing URL, avoid infinite loops and return None."""
        svc = AsilmediaService()
        dest_file = tmp_path / "fail_download.mp4"
        url = "https://30.fayllar.com/video.mp4?token=dead&expires=100"

        class Mock410Response:
            def __init__(self):
                self.status = 410
                self.headers = {}
                self.content = MagicMock()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        # Case A: resolve_stream_url returns None
        with patch.object(svc, "resolve_stream_url", return_value=None), \
             patch("aiohttp.ClientSession.get", return_value=Mock410Response()):
            res_none = await svc.download_video_stream(url, destination_path=dest_file)
            assert res_none is None

        # Case B: resolve_stream_url returns the same URL
        with patch.object(svc, "resolve_stream_url", return_value=url), \
             patch("aiohttp.ClientSession.get", return_value=Mock410Response()):
            res_same = await svc.download_video_stream(url, destination_path=dest_file)
            assert res_same is None

    @pytest.mark.asyncio
    async def test_rejects_html_error_page_masquerading_as_200_ok(self, tmp_path):
        """If CDN returns 200 OK with Content-Type text/html (CDN error/blocked notice), it must reject it."""
        svc = AsilmediaService()
        dest_file = tmp_path / "html_fake.mp4"
        url = "https://30.fayllar.com/video.mp4?token=html_fake"

        class MockHtmlResponse:
            def __init__(self):
                self.status = 200
                self.headers = {"Content-Type": "text/html; charset=utf-8"}
                self.content = MagicMock()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        with patch("aiohttp.ClientSession.get", return_value=MockHtmlResponse()):
            res = await svc.download_video_stream(url, destination_path=dest_file)
            assert res is None


# ==============================================================================
# 5. WEB SERVER HANDLE_ASIL_STREAM RECOVERY TESTS
# ==============================================================================

class TestHandleAsilStreamRecovery:
    """Stress-test web_server.py:handle_asil_stream against expired tokens and 410 probes."""

    @pytest.mark.asyncio
    async def test_stream_request_with_expired_token_auto_refreshes(self):
        """When catalog provides an expired token, handler re-resolves and redirects (HTTPFound) to fresh URL."""
        req = make_mocked_request("GET", "/api/asil/stream?id=12345&part=1&quality=1080p")

        past_ts = int(time.time()) - 500
        expired_url = f"https://30.fayllar.com/12345/1.mp4?token=expired_t&expires={past_ts}"
        fresh_url = "https://30.fayllar.com/12345/1.mp4?token=fresh_t&expires=1999999999"

        stream_info = {
            "title": "Movie 12345",
            "quality_urls": {"1080p": expired_url},
            "stream_url": expired_url,
        }

        with patch.object(MovieService, "get_movie_stream_info", return_value=stream_info), \
             patch.object(asilmedia_service, "resolve_stream_url", return_value=fresh_url) as mock_resolve:
            with pytest.raises(web.HTTPFound) as exc_info:
                await handle_asil_stream(req)

        assert exc_info.value.location == fresh_url
        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_request_with_unsigned_fayllar_url_auto_signs(self):
        """When catalog provides an unsigned Fayllar URL, handler recognizes needs_fayllar_sign and signs it."""
        req = make_mocked_request("GET", "/api/asil/stream?id=12345&part=1&quality=720p")

        unsigned_url = "https://30.fayllar.com/12345/1_720p.mp4"
        signed_url = "https://30.fayllar.com/12345/1_720p.mp4?token=new_sig&expires=1999999999"

        stream_info = {
            "title": "Movie 12345",
            "quality_urls": {"720p": unsigned_url},
            "stream_url": unsigned_url,
        }

        with patch.object(MovieService, "get_movie_stream_info", return_value=stream_info), \
             patch.object(asilmedia_service, "resolve_stream_url", return_value=signed_url) as mock_resolve:
            with pytest.raises(web.HTTPFound) as exc_info:
                await handle_asil_stream(req)

        assert exc_info.value.location == signed_url
        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_head_probe_410_gone_triggers_secondary_recovery(self):
        """If token appears valid in query but upstream returns 410 Gone on HEAD probe, re-resolve and redirect."""
        req = make_mocked_request("GET", "/api/asil/stream?id=54321&part=2")

        future_ts = int(time.time()) + 3600
        revoked_url = f"https://30.fayllar.com/54321/2.mp4?token=revoked_early&expires={future_ts}"
        refreshed_url = "https://30.fayllar.com/54321/2.mp4?token=newly_issued&expires=1999999999"

        stream_info = {
            "title": "Series 54321",
            "quality_urls": {"1080p": revoked_url},
            "stream_url": revoked_url,
        }

        class MockHeadResponse:
            def __init__(self, status):
                self.status = status

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        with patch.object(MovieService, "get_movie_stream_info", return_value=stream_info), \
             patch("aiohttp.ClientSession.head", return_value=MockHeadResponse(410)), \
             patch.object(asilmedia_service, "resolve_stream_url", return_value=refreshed_url) as mock_resolve:
            with pytest.raises(web.HTTPFound) as exc_info:
                await handle_asil_stream(req)

        assert exc_info.value.location == refreshed_url
        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_head_probe_403_forbidden_triggers_secondary_recovery(self):
        """If token appears valid in query but upstream returns 403 Forbidden on HEAD probe, re-resolve and redirect."""
        req = make_mocked_request("GET", "/api/asil/stream?id=54321&part=2")

        future_ts = int(time.time()) + 3600
        forbidden_url = f"https://30.fayllar.com/54321/2.mp4?token=forbidden_early&expires={future_ts}"
        refreshed_url = "https://30.fayllar.com/54321/2.mp4?token=newly_issued_403&expires=1999999999"

        stream_info = {
            "title": "Series 54321",
            "quality_urls": {"1080p": forbidden_url},
            "stream_url": forbidden_url,
        }

        class MockHeadResponse:
            def __init__(self, status):
                self.status = status

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        with patch.object(MovieService, "get_movie_stream_info", return_value=stream_info), \
             patch("aiohttp.ClientSession.head", return_value=MockHeadResponse(403)), \
             patch.object(asilmedia_service, "resolve_stream_url", return_value=refreshed_url) as mock_resolve:
            with pytest.raises(web.HTTPFound) as exc_info:
                await handle_asil_stream(req)

        assert exc_info.value.location == refreshed_url
        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_head_probe_timeout_or_network_error_degrades_gracefully(self):
        """If HEAD probe to Fayllar times out, handler must not crash with 500; redirects to chosen_url."""
        req = make_mocked_request("GET", "/api/asil/stream?id=54321&part=1")

        future_ts = int(time.time()) + 3600
        url = f"https://30.fayllar.com/54321/1.mp4?token=valid_token&expires={future_ts}"

        stream_info = {
            "title": "Series 54321",
            "quality_urls": {"1080p": url},
            "stream_url": url,
        }

        with patch.object(MovieService, "get_movie_stream_info", return_value=stream_info), \
             patch("aiohttp.ClientSession.head", side_effect=asyncio.TimeoutError("Probe timeout")):
            with pytest.raises(web.HTTPFound) as exc_info:
                await handle_asil_stream(req)

        # Redirected safely without 500 error
        assert exc_info.value.location == url

    @pytest.mark.asyncio
    async def test_malformed_and_missing_id_parameters(self):
        """Requests with missing or empty ID parameters return 400 Bad Request."""
        for q in ["", "?part=1", "?id=", "?code=%20%20"]:
            req = make_mocked_request("GET", f"/api/asil/stream{q}")
            resp = await handle_asil_stream(req)
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_tricky_id_formatting_and_nonexistent_movie(self):
        """ID with # or № prefix is sanitized; nonexistent stream returns 404."""
        req = make_mocked_request("GET", "/api/asil/stream?id=%23%E2%84%96999999&part=invalid_part")

        with patch.object(MovieService, "get_movie_stream_info", return_value=None):
            resp = await handle_asil_stream(req)

        assert resp.status == 404


# ==============================================================================
# 6. HIGH-THROUGHPUT BATCH PERFORMANCE & STRESS TEST
# ==============================================================================

def test_batch_token_stripping_and_expiry_performance():
    """Verify high-throughput batch processing: 10,000 URLs parsed, stripped, and checked in < 1 second."""
    now = int(time.time())
    urls = [
        f"https://30.fayllar.com/{i % 1000}/part_{(i % 50) + 1}.mp4?token=tok_{i}&expires={now + (i % 200 - 50)}&v=1080p"
        for i in range(10_000)
    ]

    t0 = time.perf_counter()
    for u in urls:
        is_exp = AsilmediaService.is_token_expired(u)
        clean = strip_fayllar_token(u)
        needs = needs_fayllar_sign(u)
    duration = time.perf_counter() - t0

    assert duration < 1.0, f"Batch performance too slow: took {duration:.3f}s for 10,000 operations"
