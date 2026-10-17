from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    Float,
    DateTime,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=False)  # Telegram user ID
    username = Column(String(128), nullable=True)
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_active = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def __repr__(self):
        return f"<User id={self.id} username={self.username} is_admin={self.is_admin}>"


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_id = Column(String(255), nullable=False)
    file_type = Column(String(32), default="video", nullable=False)  # video yoki document
    file_size = Column(BigInteger, nullable=True)
    duration = Column(Integer, nullable=True)  # soniyalarda
    genres = Column(String(255), default="Barcha", nullable=False)
    year = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    poster_file_id = Column(String(255), nullable=True)
    views_count = Column(Integer, default=0, nullable=False)
    downloads_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<Movie code={self.code} title={self.title}>"


class SponsorChannel(Base):
    __tablename__ = "sponsor_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String(64), unique=True, nullable=False)  # masalan, -1001234567890 yoki @kanal
    title = Column(String(255), nullable=False)
    username = Column(String(128), nullable=True)
    invite_link = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<SponsorChannel title={self.title} channel_id={self.channel_id}>"


class DownloadLog(Base):
    __tablename__ = "download_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    platform = Column(String(64), nullable=False)  # instagram, tiktok, youtube, snapchat, music, story
    query_or_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<DownloadLog user={self.user_id} platform={self.platform}>"


class BotSetting(Base):
    __tablename__ = "bot_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)

    def __repr__(self):
        return f"<BotSetting {self.key}={self.value}>"
