import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from unittest.mock import AsyncMock, MagicMock, patch

from services.web_server import create_web_app
from services.security_service import security_service, get_security_headers


class TestHeadersAndEndpointsAudit(AioHTTPTestCase):
    async def get_application(self):
        return create_web_app()

    @unittest_run_loop
    async def test_security_headers_and_cors(self):
        """Security and CORS headers must be present and correctly configured."""
        resp = await self.client.get("/api/catalog")
        assert resp.status == 200

        headers = resp.headers
        # CORS headers
        assert headers.get("Access-Control-Allow-Origin") == "*"
        assert "GET" in headers.get("Access-Control-Allow-Methods", "")
        assert "POST" in headers.get("Access-Control-Allow-Methods", "")
        assert "OPTIONS" in headers.get("Access-Control-Allow-Methods", "")
        assert headers.get("Access-Control-Max-Age") == "86400"
        assert "X-Init-Data" in headers.get("Access-Control-Allow-Headers", "")

        # Security headers
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "SAMEORIGIN"
        csp = headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://t.me;" in csp

    @unittest_run_loop
    async def test_options_preflight(self):
        """OPTIONS preflight requests should return CORS headers with 200 or 204."""
        resp = await self.client.options("/api/catalog")
        assert resp.status in (200, 204)
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")
        assert resp.headers.get("Access-Control-Max-Age") == "86400"

    @unittest_run_loop
    async def test_catalog_etag_and_304(self):
        """Catalog should produce ETag and handle If-None-Match with 304 Not Modified."""
        resp1 = await self.client.get("/api/catalog")
        assert resp1.status == 200
        etag = resp1.headers.get("ETag")
        assert etag is not None and len(etag) > 0

        # Send If-None-Match
        resp2 = await self.client.get("/api/catalog", headers={"If-None-Match": etag})
        assert resp2.status == 304

    @unittest_run_loop
    async def test_tv_etag_and_304(self):
        """TV endpoint should produce ETag and return 304 for unchanged client cache."""
        resp1 = await self.client.get("/api/tv")
        assert resp1.status == 200
        data = await resp1.json()
        assert data.get("ok") is True
        etag = resp1.headers.get("ETag")
        assert etag is not None

        resp2 = await self.client.get("/api/tv", headers={"If-None-Match": etag})
        assert resp2.status == 304

    @unittest_run_loop
    async def test_music_home_etag_and_304(self):
        """Music home should produce ETag and return 304 for unchanged client cache."""
        resp1 = await self.client.get("/api/music/home")
        assert resp1.status == 200
        data = await resp1.json()
        assert data.get("ok") is True
        etag = resp1.headers.get("ETag")
        assert etag is not None

        resp2 = await self.client.get("/api/music/home", headers={"If-None-Match": etag})
        assert resp2.status == 304

    @unittest_run_loop
    async def test_static_bundle_etag_and_304(self):
        """Static bundle JS and CSS should return ETags and handle 304."""
        resp1 = await self.client.get("/bundle.min.js")
        assert resp1.status == 200
        etag = resp1.headers.get("ETag")
        assert etag is not None

        resp2 = await self.client.get("/bundle.min.js", headers={"If-None-Match": etag})
        assert resp2.status == 304

    @unittest_run_loop
    async def test_send_endpoints(self):
        """Both /api/send and /api/send_to_chat and their /webapp counterparts should work."""
        # GET /api/send
        resp_get = await self.client.get("/api/send")
        assert resp_get.status == 200
        data_get = await resp_get.json()
        assert data_get.get("ok") is True
        assert data_get.get("service") == "send"

        # GET /webapp/api/send
        resp_webapp_get = await self.client.get("/webapp/api/send")
        assert resp_webapp_get.status == 200

        # POST /api/send with mock bot and deliver_movie
        mock_bot = AsyncMock()
        with patch("services.web_server._bot_instance", mock_bot), \
             patch("services.web_server.movie_service.deliver_movie", new_callable=AsyncMock) as mock_deliv:
            mock_deliv.return_value = True
            resp_post = await self.client.post("/api/send", json={"user_id": 123456, "code": "99999"})
            assert resp_post.status == 200
            data_post = await resp_post.json()
            assert data_post.get("ok") is True

    @unittest_run_loop
    async def test_docs_endpoints(self):
        """Docs config and root endpoints should return ok: True."""
        resp_cfg = await self.client.get("/api/docs/config")
        assert resp_cfg.status == 200
        data_cfg = await resp_cfg.json()
        assert data_cfg.get("ok") is True
        assert data_cfg.get("stamp") is True

        resp_root = await self.client.get("/api/docs")
        assert resp_root.status == 200
        data_root = await resp_root.json()
        assert data_root.get("ok") is True
        assert "tools" in data_root

        # /webapp alias
        resp_webapp_cfg = await self.client.get("/webapp/api/docs/config")
        assert resp_webapp_cfg.status == 200

    @unittest_run_loop
    async def test_lang_endpoint(self):
        """Language settings endpoint should handle GET and POST."""
        resp_get = await self.client.get("/api/lang?lang=ru")
        assert resp_get.status == 200
        data_get = await resp_get.json()
        assert data_get.get("ok") is True
        assert data_get.get("lang") == "ru"

        resp_post = await self.client.post("/api/lang", json={"lang": "en"})
        assert resp_post.status == 200
        data_post = await resp_post.json()
        assert data_post.get("ok") is True
        assert data_post.get("lang") == "en"

    @unittest_run_loop
    async def test_watch_endpoints(self):
        """Watch GET and POST should be available."""
        resp_get = await self.client.get("/api/watch")
        assert resp_get.status == 200
        data_get = await resp_get.json()
        assert data_get.get("ok") is True

        resp_post = await self.client.post("/api/watch", json={"code": "100"})
        assert resp_post.status == 200

    @unittest_run_loop
    async def test_donate_and_sub_endpoints(self):
        """Donate and sub endpoints should respond properly."""
        resp_don_get = await self.client.get("/api/donate/ev")
        assert resp_don_get.status == 200
        data_don = await resp_don_get.json()
        assert data_don.get("ok") is True

        resp_don_post = await self.client.post("/api/donate", json={})
        assert resp_don_post.status == 200

        resp_sub_get = await self.client.get("/api/sub")
        assert resp_sub_get.status == 200

        resp_sub_post = await self.client.post("/api/sub", json={})
        assert resp_sub_post.status == 200

    @unittest_run_loop
    async def test_games_and_tv_me_ok_field(self):
        """Games, TV me, and movies responses should contain ok: True."""
        resp_games = await self.client.get("/api/games")
        assert resp_games.status == 200
        data_games = await resp_games.json()
        assert data_games.get("ok") is True

        resp_tv_me = await self.client.get("/api/tv/me")
        assert resp_tv_me.status == 200
        data_tv_me = await resp_tv_me.json()
        assert data_tv_me.get("ok") is True

        resp_movies = await self.client.get("/api/movies")
        assert resp_movies.status == 200
        data_movies = await resp_movies.json()
        assert data_movies.get("ok") is True

    @unittest_run_loop
    async def test_asil_and_prava_endpoints(self):
        """Asil and Prava endpoints should return ok: True."""
        resp_asil = await self.client.get("/api/asil")
        assert resp_asil.status == 200
        data_asil = await resp_asil.json()
        assert data_asil.get("ok") is True

        resp_prava = await self.client.get("/api/prava")
        assert resp_prava.status == 200
        data_prava = await resp_prava.json()
        assert data_prava.get("ok") is True

    @unittest_run_loop
    async def test_all_api_and_webapp_api_aliases_post_and_get(self):
        """Test GET and POST for all endpoints and /webapp/api/ aliases."""
        endpoints = [
            "/api",
            "/api/catalog",
            "/api/tv",
            "/api/music",
            "/api/music/home",
            "/api/games",
            "/api/story",
            "/api/docs",
            "/api/books",
            "/api/fx",
            "/api/maintenance",
            "/api/lang",
            "/api/prava",
            "/api/asil",
            "/api/rasxod",
            "/api/kal",
            "/api/mafia",
        ]
        for ep in endpoints:
            # Direct GET
            resp = await self.client.get(ep)
            assert resp.status == 200, f"GET {ep} failed with {resp.status}"
            data = await resp.json()
            assert data.get("ok") is True or "items" in data or "service" in data

            # Direct POST
            resp_post = await self.client.post(ep, json={})
            assert resp_post.status == 200, f"POST {ep} failed with {resp_post.status}"

            # /webapp/api alias GET
            webapp_ep = f"/webapp{ep}"
            resp_wa = await self.client.get(webapp_ep)
            assert resp_wa.status == 200, f"GET {webapp_ep} failed with {resp_wa.status}"

            # /webapp/api alias POST
            resp_wa_post = await self.client.post(webapp_ep, json={})
            assert resp_wa_post.status == 200, f"POST {webapp_ep} failed with {resp_wa_post.status}"

    @unittest_run_loop
    async def test_movies_database_fallback_resilience(self):
        """When database raises an exception, handle_get_movies must seamlessly fallback to catalog.json."""
        with patch("services.web_server.get_session", side_effect=Exception("Database connection timeout")):
            resp = await self.client.get("/api/movies")
            assert resp.status == 200
            data = await resp.json()
            assert data.get("ok") is True
            assert isinstance(data.get("items"), list)
            assert len(data.get("items")) > 0

            # Test detail fallback
            first_code = data["items"][0]["code"]
            resp_detail = await self.client.get(f"/api/movies/{first_code}")
            assert resp_detail.status == 200
            data_detail = await resp_detail.json()
            assert data_detail.get("ok") is True
            assert str(data_detail.get("code")) == str(first_code)

