"""
Test suite covering the distinct high-end Baunty Cinema brand star/diamond badge,
glowing neon backlight (#F2B84B gradient), TV favorites, card rating badges,
UI elements alignment, and frontend bundle integrity.
"""
from pathlib import Path
import subprocess
import pytest
from config import config
from keyboards.inline import movie_item_keyboard, movie_parts_keyboard
from handlers.start import cmd_start

BASE_DIR = Path(__file__).resolve().parent.parent


def test_baunty_star_badge_css_styling_and_glow():
    """Verify that webapp/zk.css and webapp/asil.css contain the glowing Baunty Cinema star/diamond badge."""
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")
    asil_css = (BASE_DIR / "webapp" / "asil.css").read_text(encoding="utf-8")

    # 1. Baunty star badge class
    assert "baunty-star-badge" in zk_css, "baunty-star-badge must be in zk.css"
    assert "baunty-star-badge" in asil_css, "baunty-star-badge must be in asil.css"

    # 2. Golden #F2B84B gradient & ink color
    assert "#F2B84B" in zk_css
    assert "#2A1500" in zk_css
    assert "linear-gradient" in zk_css

    # 3. Neon backlight / glow effects
    assert "box-shadow" in zk_css
    assert "bauntyStarGlow" in zk_css
    assert "@keyframes bauntyStarGlow" in zk_css
    assert "drop-shadow" in zk_css

    # 4. Baunty SVG star icon selector
    assert "baunty-star-svg" in zk_css
    assert "baunty-star-ico" in zk_css


def test_baunty_vip_and_code_badge():
    """Verify that VIP badge and code badges are customized for Baunty branding."""
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")

    assert "baunty-vip-badge" in zk_css
    assert "baunty-code-badge" in zk_css
    assert "backdrop-filter" in zk_css


def test_baunty_tv_favorite_star():
    """Verify that TV favorites use the custom Baunty golden star badge."""
    zk_css = (BASE_DIR / "webapp" / "zk.css").read_text(encoding="utf-8")
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    app_js = (BASE_DIR / "webapp" / "app.js").read_text(encoding="utf-8")

    # 1. CSS styling
    assert "baunty-fav-star" in zk_css
    assert "#tvfav.active" in zk_css

    # 2. HTML & JS markup using baunty-star-svg
    assert "baunty-fav-star" in index_html
    assert "baunty-star-svg" in index_html
    assert "baunty-fav-star" in app_js
    assert "baunty-star-svg" in app_js


def test_baunty_movie_cards_and_details_rendering():
    """Verify that movie cards and detail modal in index.html, app.js and asil.js render Baunty star badges."""
    index_html = (BASE_DIR / "webapp" / "index.html").read_text(encoding="utf-8")
    app_js = (BASE_DIR / "webapp" / "app.js").read_text(encoding="utf-8")
    asil_js = (BASE_DIR / "webapp" / "asil.js").read_text(encoding="utf-8")

    # 1. AsilMedia cards
    assert "baunty-star-badge" in asil_js
    assert "baunty-star-svg" in asil_js

    # 2. Local catalog card helper
    assert "starBadgeHTML" in index_html
    assert "baunty-star-badge" in index_html
    assert "starBadgeHTML" in app_js
    assert "baunty-star-badge" in app_js

    # 3. Detail modal badge
    assert "Baunty PRO" in index_html
    assert "Baunty PRO" in app_js


def test_bundle_frontend_distribution():
    """Verify that the production bundle in dist/ contains all new Baunty star/badge assets and valid syntax."""
    bundle_css = (BASE_DIR / "webapp" / "dist" / "bundle.min.css").read_text(encoding="utf-8")
    bundle_js = (BASE_DIR / "webapp" / "dist" / "bundle.min.js").read_text(encoding="utf-8")

    assert "baunty-star-badge" in bundle_css
    assert "bauntyStarGlow" in bundle_css
    assert "baunty-star-badge" in bundle_js
    assert "baunty-star-svg" in bundle_js

    # Verify Node.js syntax check
    res = subprocess.run(["node", "--check", str(BASE_DIR / "webapp" / "dist" / "bundle.min.js")], capture_output=True, text=True)
    assert res.returncode == 0, f"Node.js syntax check failed: {res.stderr}"
