"""
Keyboards testi
"""
from keyboards.default import main_menu_keyboard, cancel_keyboard, admin_reply_keyboard
from keyboards.inline import (
    subscription_keyboard,
    movie_menu_keyboard,
    genres_keyboard,
    movie_item_keyboard,
    media_download_keyboard,
    GENRES_LIST,
)
from database.models import SponsorChannel


def test_main_menu_keyboard_user():
    kb = main_menu_keyboard(is_admin=False)
    button_texts = [btn.text for row in kb.keyboard for btn in row]
    # 8 ta doimiy reply tugma tekshiruvi:
    assert "🎬 K I N O — kod orqali qidirish" in button_texts
    assert "📄 Hujjatlar" in button_texts
    assert "⭕️ Dumaloq video" in button_texts
    assert "👀 Anonim story" in button_texts
    assert "💌 Anonim savollar" in button_texts
    assert "🎁 Do'st taklif qilish" in button_texts
    assert "👥 Guruhlarim" in button_texts
    assert "💬 Xato va fikrlar" in button_texts
    # Qo'shimchalar
    assert "🎬 Kino" in button_texts
    assert "🎵 Qo'shiq topish" in button_texts
    assert "📥 Media yuklash" in button_texts
    assert "👑 Admin Panel" not in button_texts


def test_main_menu_keyboard_admin():
    kb = main_menu_keyboard(is_admin=True)
    button_texts = [btn.text for row in kb.keyboard for btn in row]
    assert "👑 Admin Panel" in button_texts


def test_cancel_keyboard():
    kb = cancel_keyboard()
    button_texts = [btn.text for row in kb.keyboard for btn in row]
    assert "❌ Bekor qilish" in button_texts


def test_subscription_keyboard():
    channel = SponsorChannel(
        id=1,
        channel_id="-1001",
        title="Test Channel",
        invite_link="https://t.me/test_channel",
        is_active=True
    )
    kb = subscription_keyboard([channel])
    button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Test Channel" in t for t in button_texts)
    assert any("Obunani tekshirish" in t for t in button_texts)


def test_genres_keyboard():
    kb = genres_keyboard()
    button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Jangari" in t for t in button_texts)
    assert any("Komediya" in t for t in button_texts)


def test_movie_item_keyboard():
    kb = movie_item_keyboard("101")
    urls = [btn.url for row in kb.inline_keyboard for btn in row if btn.url]
    assert any("movie_101" in u for u in urls)


def test_media_download_keyboard():
    kb = media_download_keyboard("tok123")
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
    assert "dl_audio:tok123" in callbacks
    assert "dl_shazam:tok123" in callbacks


def test_admin_detail_and_edit_keyboards():
    from keyboards.inline import admin_movie_detail_keyboard, movie_edit_keyboard, admin_settings_keyboard
    kb_detail = admin_movie_detail_keyboard("105")
    callbacks_detail = [btn.callback_data for row in kb_detail.inline_keyboard for btn in row if btn.callback_data]
    assert "admin:movie:edit:105" in callbacks_detail
    assert "admin:movie:del_direct:105" in callbacks_detail
    assert "get_movie:105" in callbacks_detail

    kb_edit = movie_edit_keyboard("105")
    callbacks_edit = [btn.callback_data for row in kb_edit.inline_keyboard for btn in row if btn.callback_data]
    assert "admin:medit:title:105" in callbacks_edit
    assert "admin:medit:media:105" in callbacks_edit

    kb_settings = admin_settings_keyboard()
    callbacks_settings = [btn.callback_data for row in kb_settings.inline_keyboard for btn in row if btn.callback_data]
    assert "admin:menu" in callbacks_settings

