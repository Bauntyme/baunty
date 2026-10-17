"""
Helpers testi (URL regex, platform aniqlash, movie formatlash)
"""
import pytest
from utils.helpers import (
    extract_media_url,
    detect_platform,
    cache_url,
    get_cached_url,
    format_movie_caption,
    format_movie_not_found,
)
from database.models import Movie


def test_extract_media_url_instagram():
    urls = [
        "https://www.instagram.com/reel/C123456789/",
        "https://instagram.com/p/ABCDEFGHIJ/",
        "Qarang: https://www.instagram.com/reel/Cxyz987/ zo'r ekan",
        "https://instagr.am/reel/DA123456/",
    ]
    for text in urls:
        extracted = extract_media_url(text)
        assert extracted is not None
        assert "instagram.com" in extracted or "instagr.am" in extracted
        assert detect_platform(extracted) == "Instagram"


def test_extract_media_url_tiktok():
    urls = [
        "https://www.tiktok.com/@user/video/7123456789012345678",
        "https://vm.tiktok.com/ZMxxxxxx/",
        "https://vt.tiktok.com/ZSxxxxxx/",
    ]
    for text in urls:
        extracted = extract_media_url(text)
        assert extracted is not None
        assert "tiktok.com" in extracted
        assert detect_platform(extracted) == "TikTok"


def test_extract_media_url_youtube():
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/abcdef12345",
    ]
    for text in urls:
        extracted = extract_media_url(text)
        assert extracted is not None
        assert detect_platform(extracted) == "YouTube"


def test_extract_media_url_snapchat():
    urls = [
        "https://www.snapchat.com/spotlight/W7q0nw3AAZgAGmxm",
        "https://snapchat.com/add/username",
    ]
    for text in urls:
        extracted = extract_media_url(text)
        assert extracted is not None
        assert detect_platform(extracted) == "Snapchat"


def test_extract_media_url_none():
    assert extract_media_url("Salom bot, yaxshimisiz?") is None
    assert extract_media_url("12345") is None
    assert extract_media_url("") is None


def test_url_caching():
    url = "https://www.instagram.com/reel/C123456789/?igsh=test"
    token = cache_url(url)
    assert len(token) <= 10
    cached = get_cached_url(token)
    assert cached == url


def test_movie_caption_formatting():
    movie = Movie(
        code="101",
        title="Forsaj 10",
        genres="Jangari, Triller",
        year=2023,
        rating=7.5,
        views_count=150,
        description="Dom Toretto va uning oilasi..."
    )
    caption = format_movie_caption(movie)
    assert "Forsaj 10" in caption
    assert "101" in caption
    assert "Jangari" in caption
    assert "2023" in caption
    assert "7.5" in caption
    assert "@ZakirovsKino" in caption


def test_movie_not_found_formatting():
    text = format_movie_not_found("999")
    assert "999" in text
    assert "@ZakirovsKino" in text


def test_extract_media_url_edge_cases():
    text_with_newlines = "Mana bu videoni ko'ring:\nhttps://www.instagram.com/reel/C123456789/?igsh=MWFqenR0&utm_source=qr\nZo'r ekan!"
    assert extract_media_url(text_with_newlines) is not None

    text_with_emojis = "🔥🔥 https://vt.tiktok.com/ZS123456/ 🔥🔥"
    assert extract_media_url(text_with_emojis) is not None

    uppercase_url = "HTTPS://WWW.TIKTOK.COM/@USER/VIDEO/7123456789012345678"
    assert extract_media_url(uppercase_url) is not None


def test_movie_caption_minimal():
    movie = Movie(
        code="500",
        title="Nomsiz film",
        genres=None,
        year=None,
        rating=None,
        views_count=0,
        description=None
    )
    caption = format_movie_caption(movie)
    assert "Nomsiz film" in caption
    assert "500" in caption
    assert "Noma'lum" in caption

