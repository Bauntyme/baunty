"""
Bauntys Bot - Asosiy konfiguratsiya moduli
"""
import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str = Field(default="YOUR_BOT_TOKEN_HERE")
    BOT_USERNAME: str = Field(default="Bauntyfilmsbot")
    CHANNEL_USERNAME: str = Field(default="@BauntyFilms")

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
    WEBAPP_URL: str = Field(default="https://baunty.onrender.com")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def webapp_url_resolved(self) -> str:
        """Render.com yoki muhit o'zgaruvchilaridan WebApp HTTPS URLini aniqlaydi."""
        url = self.WEBAPP_URL.strip() if self.WEBAPP_URL else os.getenv("RENDER_EXTERNAL_URL", "").strip()
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
