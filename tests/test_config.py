"""
Config testi
"""
import pytest
from config import Settings, BASE_DIR


def test_settings_admin_ids_parsing():
    settings = Settings(
        BOT_TOKEN="test_token",
        ADMIN_IDS="12345, 67890, 99999",
        DB_TYPE="sqlite"
    )
    assert settings.admin_ids == [12345, 67890, 99999]
    assert settings.is_admin(12345) is True
    assert settings.is_admin(67890) is True
    assert settings.is_admin(11111) is False


def test_settings_db_url_sqlite():
    settings = Settings(
        BOT_TOKEN="test_token",
        DB_TYPE="sqlite",
        DATABASE_URL=""
    )
    assert "sqlite+aiosqlite:///" in settings.db_url
    assert "data/bot.db" in settings.db_url


def test_settings_db_url_postgres():
    settings = Settings(
        BOT_TOKEN="test_token",
        DB_TYPE="postgres",
        DATABASE_URL=""
    )
    assert "postgresql+asyncpg://" in settings.db_url


def test_settings_download_path():
    settings = Settings(
        BOT_TOKEN="test_token",
        DOWNLOAD_DIR="temp_downloads_test"
    )
    path = settings.download_path
    assert path.exists()
    # clean up test dir
    path.rmdir()
