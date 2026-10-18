"""
1:1 "Samarqand tuni" dizayn tizimi, animatsiyalar, 3D Coverflow,
Oltin kubik ruletkasi, Bauntys brendi va vinil grammofon pleyeri testlari.
"""
from pathlib import Path
import pytest
from aiohttp.test_utils import TestClient, TestServer
from services.web_server import create_web_app
from services.tv_data import CHANNELS_LIST

BASE_DIR = Path(__file__).resolve().parent.parent


def test_samarqand_tuni_design_tokens_and_keyframes():
    """zk.css mavjudligi, CSS o'zgaruvchilari, dot-matrix va barcha 7+ keyframes animatsiyalari."""
    zk_css_path = BASE_DIR / "webapp" / "zk.css"
    assert zk_css_path.exists(), "webapp/zk.css fayli mavjud bo'lishi shart"
    css = zk_css_path.read_text(encoding="utf-8")

    # 1. CSS o'zgaruvchilari
    assert "--zk-night: #070B1F" in css or "--zk-night" in css
    assert "--zk-panel: #0E1330" in css or "--zk-panel" in css
    assert "--zk-panel2: #151B40" in css or "--zk-panel2" in css
    assert "--zk-cream: #F6EEDC" in css or "--zk-cream" in css
    assert "--zk-acc: #F2B84B" in css or "--zk-acc" in css
    assert "--zk-ink: #2A1500" in css or "--zk-ink" in css
    assert "--zk-line: rgba(246, 238, 220, 0.14)" in css or "--zk-line" in css

    # 2. Dot-matrix fon teksturasi
    assert "body.zk::after" in css
    assert "radial-gradient" in css

    # 3. Barcha talab qilingan @keyframes animatsiyalari
    assert "@keyframes zkroll" in css, "zkroll animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zkin" in css, "zkin animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes sh" in css, "sh animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes msh" in css, "msh animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zkspin" in css, "zkspin animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zkeq" in css, "zkeq animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zkdraw" in css, "zkdraw animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zkturn" in css, "zkturn animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zslogo" in css, "zslogo animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zsshine" in css, "zsshine animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zkring" in css, "zkring animatsiyasi mavjud bo'lishi shart"
    assert "@keyframes zkdrop" in css, "zkdrop animatsiyasi mavjud bo'lishi shart"


def test_top10_coverflow_and_3d_cards():
    """Top 10 Coverflow 3D karuseli, oltin raqamlar, badge va sarlavhalar."""
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    zk_js = (BASE_DIR / "webapp" / "zk.js").read_text(encoding="utf-8")

    # 1. CSS da .zk-flow, .zk-mid, .rank
    assert ".zk-flow" in zk_css
    assert ".zk-flow .card" in zk_css
    assert ".zk-flow .card.zk-mid" in zk_css
    assert ".zk-flow .rank" in zk_css
    assert "Unbounded" in zk_css
    assert "-webkit-text-stroke" in zk_css

    # 2. index.html da Coverflow elementlari va sarlavha
    assert "zk-flow" in index_html
    assert "zk-top10-h" in index_html
    assert "🔥 Top" in index_html
    assert "eng ko'p ko'rilgan" in index_html

    # 3. zk.js da Coverflow center kalkulyatsiyasi
    assert "updateFlowCenter" in zk_js
    assert "initFlow" in zk_js


def test_golden_dice_and_slot_roulette():
    """Oltin kubik tugmasi va to'liq ekranli slot-ruletka modal oynasi."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    zk_js = (BASE_DIR / "webapp" / "zk.js").read_text(encoding="utf-8")
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")

    # 1. Kubik tugmasi
    assert 'id="zkDice"' in index_html
    assert "zk-dice" in index_html
    assert ".zk-dice" in zk_css

    # 2. Slot-ruletka modali
    assert 'id="zkSlot"' in index_html
    assert 'id="zkSlotReel"' in index_html
    assert 'id="zkSlotClose"' in index_html
    assert 'id="zkSlotSpinBtn"' in index_html
    assert ".zk-slot" in zk_css

    # 3. zk.js spin ruletka funksiyasi
    assert "spinRoulette" in zk_js
    assert "window.ZK_spin" in zk_js


def test_header_bauntys_branding_and_indicator():
    """Headerda Bauntys bot logotipi, matni, splash ekran va siljuvchi indikator."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    logo_svg = BASE_DIR / "webapp" / "logo.svg"
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")
    zk_js = (BASE_DIR / "webapp" / "zk.js").read_text(encoding="utf-8")

    # 1. Bauntys rasmi / SVG mavjudligi
    assert logo_svg.exists(), "webapp/logo.svg mavjud bo'lishi shart"
    assert "logo.svg" in index_html

    # 2. Header profil va Bauntys yozuvi
    assert "zk-brand-bar" in index_html
    assert "Bauntys" in index_html
    assert "zk-brand-avatar-wrap" in index_html

    # 3. Siljuvchi indikator (.zk-ind)
    assert 'id="zkInd"' in index_html
    assert ".zk-ind" in zk_css
    assert "updateIndicator" in zk_js

    # 4. Splash ekrani (#zksplash)
    assert 'id="zksplash"' in index_html
    assert ".zk-splash" in zk_css
    assert "zk-splash-rings" in index_html
    assert "zk-splash-shine" in index_html
    assert "initSplash" in zk_js


def test_music_vinyl_gramophone_and_audio():
    """Musiqa pleyerida vinil grammofon (.m-deck, .dk-disc, .dk-arm), mini pleyer va seekbar."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")
    music_js = (BASE_DIR / "webapp" / "music.js").read_text(encoding="utf-8")

    # 1. HTML ichida vinil grammofon
    assert 'id="mdeck"' in index_html
    assert 'id="dkdisc"' in index_html
    assert 'id="dkarm"' in index_html
    assert 'id="mbig"' in index_html
    assert 'id="mwave"' in index_html
    assert 'id="mmini"' in index_html
    assert 'id="mplayer"' in index_html

    # 2. zk.css da vinil grammofon stillari
    assert ".m-deck" in zk_css
    assert ".dk-disc" in zk_css
    assert ".dk-arm" in zk_css
    assert ".dk-pivot" in zk_css
    assert ".dk-needle" in zk_css
    assert "zkspin" in zk_css

    # 3. music.js da grammofon holati yangilanishi
    assert 'deck.classList.toggle("playing"' in music_js


def test_4k_tv_preserved():
    """4K Live TV o'z joyida saqlanganligi va 154 ta kanal to'liq ishlashi."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    assert len(CHANNELS_LIST) >= 150, "Kamida 150 ta telekanal bo'lishi kerak"
    assert 'id="tvp"' in index_html
    assert 'id="fsbar"' in index_html
    assert 'id="vboxfs"' in index_html
    assert "4K UHD" in index_html


def test_white_label_no_branding_leaks():
    """Barcha yangi fayllarda mutlaqo eski brend (Zakirovs) qolmaganligi."""
    for fn in ["zk.css", "zk.js", "logo.svg", "index.html"]:
        p = BASE_DIR / "webapp" / fn
        if p.exists():
            content = p.read_text(encoding="utf-8")
            assert "zakirov" not in content.lower(), f"{fn} da eski brend nomi aniqlandi!"


@pytest.mark.asyncio
async def test_handle_music_play_always_returns_playable_stream():
    """handle_music_play endpointi har doim web audio pleyer uchun yaroqli audio oqim qaytarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # To'g'ridan-to'g'ri MP3 audio bilan so'rov
        resp = await client.post("/api/music/play", json={
            "id": "1001",
            "t": "Test Song",
            "a": "Test Artist",
            "u": "https://cdn.example.com/stream.mp3"
        })
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert data["url"] == "https://cdn.example.com/stream.mp3"

        # Deezer ID bilan so'rov
        resp_dz = await client.post("/api/music/play", json={
            "id": "1109731",
            "t": "Lose Yourself",
            "a": "Eminem",
            "s": "dz"
        })
        assert resp_dz.status == 200
        data_dz = await resp_dz.json()
        assert data_dz["ok"] is True
        assert "http" in data_dz["url"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_root_static_file_serving_for_zk_assets():
    """/zk.css, /zk.js, /logo.svg, /logo.webp barchasi root orqali 200 OK qaytarishi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        for fname in ["zk.css", "zk.js", "logo.svg", "logo.webp"]:
            resp = await client.get(f"/{fname}")
            assert resp.status == 200, f"/{fname} 200 qaytarishi kerak, ammo {resp.status} qaytdi"
            body = await resp.read()
            assert len(body) > 0, f"/{fname} bo'sh bo'lmasligi kerak"
    finally:
        await client.close()


def test_slim_top_player_and_webgl_octagram():
    """#mtop slim pleyer paneli, paintTop, WebGL #zkbg va zksplash octagram girih yulduzi."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")
    zk_js = (BASE_DIR / "webapp" / "zk.js").read_text(encoding="utf-8")
    music_js = (BASE_DIR / "webapp" / "music.js").read_text(encoding="utf-8")

    # 1. #mtop slim pleyer paneli
    assert 'id="mtop"' in index_html
    assert 'class="mt-open"' in index_html
    assert 'id="mtcv"' in index_html
    assert 'id="mtt"' in index_html
    assert 'id="mta"' in index_html
    assert 'id="mtplay"' in index_html
    assert 'id="mtx"' in index_html
    assert 'id="mtpr"' in index_html
    assert ".m-top" in zk_css
    assert "paintTop" in music_js

    # 2. Splash octagram girih yulduzi (8 burchakli girih yulduzi: rect + rotate(45))
    assert 'viewBox="-60 -60 120 120"' in index_html
    assert 'rotate(45)' in index_html
    assert "zkdraw" in zk_css
    assert "zkturn" in zk_css

    # 3. WebGL jonli ipak-girih shaderi
    assert 'cv.id = "zkbg"' in zk_js or 'getElementById("zkbg")' in zk_js
    assert "webgl" in zk_js
    assert "createShader" in zk_js
    assert "createProgram" in zk_js
    assert ".zk-bg-canvas" in zk_css or "#zkbg" in zk_css


