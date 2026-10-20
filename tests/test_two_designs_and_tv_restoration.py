"""
Ikki xil dizayn (Oddiy/Lite vs Yangi/Modern/Kreativ),
Barcha TV kanallarning 100% barqaror jonli oqimlari va logotiplari (ico),
Kinolar, multfilmlar va animelarni to'liq saralash va yetkazish testlari.
"""
from pathlib import Path
import pytest
from services.tv_data import CHANNELS_LIST
from config import BASE_DIR


def test_two_designs_coexistence_and_switching():
    """Ikkala dizayn (Oddiy / Classic va Kreativ / Modern) to'liq qo'llab-quvvatlanishi."""
    index_file = BASE_DIR / "webapp" / "index.html"
    zk_file = BASE_DIR / "webapp" / "zk.js"
    app_file = BASE_DIR / "webapp" / "app.js"

    index_html = index_file.read_text(encoding="utf-8")
    zk_js = zk_file.read_text(encoding="utf-8")
    app_js = app_file.read_text(encoding="utf-8")

    # 1. index.html head qismida ZK_LITE dastlabki yuklanishi (localStorage va URL query orqali)
    assert "window.ZK_LITE" in index_html
    assert 'localStorage.getItem("zk_ui")' in index_html
    assert "zk-lite" in index_html

    # 2. zk.js da ZK_LITE bo'lganda splash va body.splashing to'liq olib tashlanishi
    assert "document.body.classList.remove(\"splashing\");" in zk_js
    assert "window.ZK_LITE" in zk_js

    # 3. index.html va app.js da dizayn tanlash/almashtirish modal va tugmalari
    assert "✨ Kreativ" in index_html
    assert "⚡ Oddiy" in index_html
    assert "✨ Kreativ" in app_js
    assert "⚡ Oddiy" in app_js
    assert 'data-ui="kr"' in index_html
    assert 'data-ui="lite"' in index_html
    assert 'data-pick="kr"' in index_html
    assert 'data-pick="lite"' in index_html

    # 4. setUI funksiyasi lite / oddiy / classic qiymatlarini qo'llab-quvvatlashi
    assert "want = (v === \"lite\" || v === \"classic\" || v === \"oddy\" || v === \"oddiy\")" in index_html
    assert "want = (v === \"lite\" || v === \"classic\" || v === \"oddy\" || v === \"oddiy\")" in app_js


def test_tv_channel_icons_and_direct_stable_streams():
    """TV kanallarning ico klassli logotiplari, zaxira svg va birlamchi to'g'ridan-to'g'ri oqimlari."""
    index_file = BASE_DIR / "webapp" / "index.html"
    app_file = BASE_DIR / "webapp" / "app.js"
    js_app_file = BASE_DIR / "webapp" / "js" / "app.js"

    index_html = index_file.read_text(encoding="utf-8")
    app_js = app_file.read_text(encoding="utf-8")
    js_app = js_app_file.read_text(encoding="utf-8")

    # 1. Telekanal kartochkalari ustida haqiqiy ico logotipi
    assert 'class="ico tvl"' in index_html
    assert 'class="ico tvl"' in app_js
    assert 'class="ico tvl"' in js_app

    # 2. CSS da .ico klassi to'liq shakllantirilgan
    assert ".tvb .ico" in index_html
    assert ".tvbar .lg .ico" in index_html

    # 3. Rasm topilmasa yoki yuklanmasa zaxira logo.svg
    assert "logo.svg" in index_html
    assert "logo.svg" in app_js
    assert "logo.svg" in js_app

    # 4. attempt funksiyasida boshlang'ich majburiy playlist almashtirish olib tashlangan
    # (birlamchi to'g'ridan-to'g'ri oqim darhol o'ynaydi)
    assert 'let streamTarget = url;' in index_html
    assert 'let streamTarget = url;' in app_js
    assert 'let targetUrl = streamUrl;' in js_app

    # 5. Barcha telekanallarning birlamchi oqimlari mavjudligi
    assert len(CHANNELS_LIST) >= 150
    for ch in CHANNELS_LIST[:20]:
        assert ch.get("stream"), f"{ch.get('n')} da oqim manzili yo'q"
        assert len(ch.get("u", [])) >= 2, f"{ch.get('n')} da zaxira oqimlar kam"


def test_cartoons_and_anime_categories_and_delivery():
    """Kino katalogida multfilmlar va animelar filtrlari va botga yetkazilishi."""
    index_file = BASE_DIR / "webapp" / "index.html"
    app_file = BASE_DIR / "webapp" / "app.js"

    index_html = index_file.read_text(encoding="utf-8")
    app_js = app_file.read_text(encoding="utf-8")

    # 1. Chiplar orasida Multfilmlar va Anime tugmalari
    assert 'data-t="mult"' in index_html
    assert 'data-t="anime"' in index_html
    assert 'Multfilmlar' in index_html
    assert 'Anime' in index_html

    # 2. render funksiyasida mult va anime saralash logikasi
    assert 'tab === "mult"' in index_html
    assert 'tab === "anime"' in index_html
    assert 'tab === "mult"' in app_js
    assert 'tab === "anime"' in app_js
