"""
Bauntys Bot - Asosiy konfiguratsiya moduli
"""
import os
from pathlib import Path
from typing import List, Optional, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str = Field(default="9047244772:AAHevPLbK9Uz_NQ0AtcemQqpA0C5OgXtkgw")
    BOT_USERNAME: str = Field(default="BauntyCinemabot")
    CHANNEL_USERNAME: str = Field(default="@BauntyFilms")

    # Mahalliy Telegram Bot API Server (2000 MB gacha video yuklash)
    LOCAL_BOT_API_URL: Optional[str] = Field(default=None)
    BOT_API_SERVER: Optional[str] = Field(default=None)

    # Adminlar
    ADMIN_IDS_RAW: str = Field(default="", alias="ADMIN_IDS")

    # Ma'lumotlar bazasi
    DB_TYPE: str = Field(default="sqlite")  # 'sqlite' yoki 'postgres'
    DATABASE_URL: Optional[str] = Field(default=None)

    # Maxfiy kino kanali (ixtiyoriy)
    STORAGE_CHANNEL_ID: Optional[str] = Field(default="-1004254432863")

    # Yuklab olish parametrlari
    DOWNLOAD_DIR: str = Field(default="temp_downloads")
    MAX_FILE_SIZE_MB: int = Field(default=50)
    RATE_LIMIT_SECONDS: float = Field(default=1.0)
    # Web Server & Mini App (Render.com mosligi)
    PORT: int = Field(default=8080)
    HOST: str = Field(default="0.0.0.0")
    WEBAPP_URL: str = Field(default="https://baunty-cinema.onrender.com/")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def model_post_init(self, __context: Any) -> None:
        resolved = self.local_bot_api_url_resolved
        if resolved:
            if not self.LOCAL_BOT_API_URL:
                self.LOCAL_BOT_API_URL = resolved
            if not self.BOT_API_SERVER:
                self.BOT_API_SERVER = resolved

    @property
    def local_bot_api_url_resolved(self) -> Optional[str]:
        """Mahalliy Bot API Server URLini aniqlaydi (LOCAL_BOT_API_URL yoki BOT_API_SERVER)."""
        url = (
            self.LOCAL_BOT_API_URL
            or self.BOT_API_SERVER
            or os.getenv("LOCAL_BOT_API_URL")
            or os.getenv("BOT_API_SERVER")
        )
        if url and str(url).strip():
            clean_url = str(url).strip()
            if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
                clean_url = f"http://{clean_url}"
            return clean_url.rstrip("/")
        return None

    @property
    def is_local_bot_api(self) -> bool:
        """Mahalliy Telegram Bot API Server sozlanganligini tekshiradi."""
        return bool(self.local_bot_api_url_resolved)

    @property
    def max_upload_bytes(self) -> int:
        """Maksimal ruxsat etilgan video yuklash hajmi (baytlarda):
        Mahalliy Bot API Server mavjud bo'lsa 2000 MB (2000 * 1024 * 1024),
        aks holda standart 50 MB limit.
        """
        if self.is_local_bot_api:
            return 2000 * 1024 * 1024
        limit_mb = self.MAX_FILE_SIZE_MB if (self.MAX_FILE_SIZE_MB and self.MAX_FILE_SIZE_MB > 0) else 50
        return limit_mb * 1024 * 1024

    @property
    def max_upload_mb(self) -> int:
        """Maksimal ruxsat etilgan video yuklash hajmi MB da."""
        return self.max_upload_bytes // (1024 * 1024)

    @property
    def webapp_url_resolved(self) -> str:
        """Render.com yoki muhit o'zgaruvchilaridan WebApp HTTPS URLini aniqlaydi."""
        url = self.WEBAPP_URL.strip() if self.WEBAPP_URL else ""
        if not url:
            url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
        if not url:
            url = "https://baunty-cinema.onrender.com/"
        if url:
            if not url.startswith("http://") and not url.startswith("https://"):
                url = f"https://{url}"
        return url

    @property
    def admin_ids(self) -> List[int]:
        """Vergul bilan ajratilgan admin ID larini int list ko'rinishida qaytaradi."""
        if not self.ADMIN_IDS_RAW:
            return []
        ids = []
        for x in self.ADMIN_IDS_RAW.split(","):
            x_clean = x.strip()
            if x_clean.isdigit() or (x_clean.startswith("-") and x_clean[1:].isdigit()):
                ids.append(int(x_clean))
        return ids

    @property
    def db_url(self) -> str:
        """Ma'lumotlar bazasi ulanish URLini aniqlaydi."""
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            url = self.DATABASE_URL.strip()
            if url.startswith("postgres://"):
                url = "postgresql+asyncpg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://"):]
            if "sslmode=" in url:
                url = url.replace("sslmode=require", "ssl=require").replace("sslmode=prefer", "ssl=prefer")
            if "sqlite" in url:
                # sqlite:///path yoki sqlite+aiosqlite:///path ni to'g'ri absolute qilish
                prefix = "sqlite+aiosqlite:///" if "aiosqlite" in url else "sqlite:///"
                raw_path = url.split(prefix)[-1]
                path = Path(raw_path)
                if not path.is_absolute():
                    path = (BASE_DIR / path).resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                return f"{prefix}{path.as_posix()}"
            return url

        if self.DB_TYPE.lower() == "postgres":
            return "postgresql+asyncpg://postgres:postgres@localhost:5432/baunty_db"
        else:
            db_path = (BASE_DIR / "data" / "bot.db").resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{db_path.as_posix()}"

    @property
    def download_path(self) -> Path:
        """Vaqtinchalik yuklab olish papkasi yo'li."""
        path = BASE_DIR / self.DOWNLOAD_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    def is_admin(self, user_id: int) -> bool:
        """Foydalanuvchi admin ekanligini tekshiradi."""
        return user_id in self.admin_ids

    @property
    def ffmpeg_path(self) -> Optional[str]:
        """ffmpeg ijro fayli yo'lini topadi (PATH yoki imageio-ffmpeg)."""
        import shutil
        found = shutil.which("ffmpeg")
        if found:
            return found
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None


# Global konfiguratsiya ob'ekti
config = Settings()
