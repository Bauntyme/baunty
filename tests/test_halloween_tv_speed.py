import pytest
import re
from pathlib import Path
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from services.web_server import create_web_app

class TestTVSpeedAndHalloween(AioHTTPTestCase):
    async def get_application(self):
        return create_web_app()

    async def test_speed_endpoint_get_default(self):
        client = self.client
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = await client.get("/api/tv/speed", headers=headers)
        assert resp.status == 200
        assert resp.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate, max-age=0"
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "X-Server-Time-Ms" in resp.headers
        body = await resp.read()
        assert len(body) == 65536

    async def test_speed_endpoint_custom_and_clamped_bytes(self):
        client = self.client
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        # Test custom bytes
        resp = await client.get("/api/tv/speed?bytes=32768", headers=headers)
        assert resp.status == 200
        body = await resp.read()
        assert len(body) == 32768

        # Test minimum clamp (1024)
        resp_min = await client.get("/api/tv/speed?bytes=10", headers=headers)
        assert resp_min.status == 200
        assert len(await resp_min.read()) == 1024

        # Test maximum clamp (524288)
        resp_max = await client.get("/api/tv/speed?bytes=2000000", headers=headers)
        assert resp_max.status == 200
        assert len(await resp_max.read()) == 524288

        # Test invalid bytes fallback
        resp_inv = await client.get("/api/tv/speed?bytes=invalid", headers=headers)
        assert resp_inv.status == 200
        assert len(await resp_inv.read()) == 65536

    async def test_speed_endpoint_options_cors(self):
        client = self.client
        resp = await client.options("/api/tv/speed")
        assert resp.status in (200, 204)
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    async def test_speed_endpoint_head_method(self):
        client = self.client
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = await client.head("/api/tv/speed", headers=headers)
        assert resp.status == 200
        assert resp.headers.get("Content-Length") == "65536"

    async def test_speed_endpoint_webapp_prefix(self):
        client = self.client
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = await client.get("/webapp/api/tv/speed", headers=headers)
        assert resp.status == 200
        assert len(await resp.read()) == 65536

    def test_frontend_speed_detection_and_threshold_logic(self):
        index_html = Path("webapp/index.html").read_text(encoding="utf-8")
        app_js = Path("webapp/app.js").read_text(encoding="utf-8")
        tvroom_js = Path("webapp/tvroom.js").read_text(encoding="utf-8")
        tv_room_js = Path("webapp/tv_room.js").read_text(encoding="utf-8")

        for code, name in [(index_html, "index.html"), (app_js, "app.js")]:
            assert "getAccurateNetworkSpeed" in code, f"Missing getAccurateNetworkSpeed in {name}"
            assert "currentSpeed < 1.0" in code, f"Missing 1.0 Mbps minimum block in {name}"
            assert "Internet tezligi juda past" in code, f"Missing speed warning in {name}"
            assert "Kamida 1 Mbps" in code, f"Missing min 1 Mbps text in {name}"
            assert "hls.startLevel = _isSlow ? slowIdx : targetIdx;" in code, f"Missing adaptive start in {name}"

        for code, name in [(tvroom_js, "tvroom.js"), (tv_room_js, "tv_room.js")]:
            assert "getAccurateNetworkSpeed" in code, f"Missing getAccurateNetworkSpeed in {name}"
            assert "speedMbps < 1.0" in code, f"Missing 1.0 Mbps check in {name}"
            assert "abrEwmaDefaultEstimate: speedMbps < 2.0 ? 1200000 : 2500000" in code, f"Missing abr default in {name}"
            assert "🎃" in code and "👻" in code and "🦇" in code and "🍬" in code, f"Missing Halloween emoji in {name}"

    def test_halloween_ui_and_animations(self):
        zk_css = Path("webapp/zk.css").read_text(encoding="utf-8")
        tvroom_css = Path("webapp/tvroom.css").read_text(encoding="utf-8")
        tv_room_css = Path("webapp/tv_room.css").read_text(encoding="utf-8")
        index_html = Path("webapp/index.html").read_text(encoding="utf-8")

        assert "@keyframes hwMistPulse" in zk_css
        assert "@keyframes hwBatFly1" in zk_css
        assert "@keyframes hwBatFly2" in zk_css
        assert "@keyframes hwPumpkinPulse" in zk_css
        assert "@keyframes hwZombieWalk" in zk_css
        assert "@keyframes hwZombieClaw" in zk_css
        assert "@keyframes hwBtnFlameGrad" in zk_css
        assert ".hw-mist-layer" in zk_css
        assert ".hw-bats-opening" in zk_css
        assert ".hw-pumpkin-glow" in zk_css
        assert ".hw-zombie-walker" in zk_css
        assert ".hw-zombie-hand" in zk_css
        assert ".hw-ghost" in zk_css
        assert ".hw-spiderweb" in zk_css

        assert "hw-mist-layer" in index_html
        assert "hw-bats-opening" in index_html
        assert "hw-pumpkin-glow" in index_html
        assert "hw-zombie-walker" in index_html
        assert "hw-zombie-hand" in index_html
        assert "hw-ghost" in index_html
        assert "Bauntys Halloween" in index_html

        assert ".tvr-head" in tvroom_css and ".tvr-head" in tv_room_css
        assert "#FF7518" in tvroom_css and "#9D4EDD" in tvroom_css
        assert tvroom_css == tv_room_css, "tvroom.css and tv_room.css must match"
