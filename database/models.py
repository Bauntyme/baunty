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
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utc_now() -> datetime:
    """Offset-naive UTC datetime — PostgreSQL va SQLite uchun 100% mos."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=False)  # Telegram user ID
    username = Column(String(128), nullable=True)
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    referral_count = Column(Integer, default=0, nullable=False)
    referral_points = Column(Integer, default=0, nullable=False)
    referred_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_active = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def __repr__(self):
        return f"<User id={self.id} username={self.username} is_admin={self.is_admin}>"


class AnonymousMessage(Base):
    __tablename__ = "anonymous_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(BigInteger, index=True, nullable=False)
    recipient_id = Column(BigInteger, index=True, nullable=False)
    message_text = Column(Text, nullable=False)
    reply_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<AnonymousMessage from={self.sender_id} to={self.recipient_id}>"


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    username = Column(String(128), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<Feedback user={self.user_id}>"


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_id = Column(String(255), nullable=True, default="")
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


class MovieFile(Base):
    __tablename__ = "movie_files"
    __table_args__ = (
        UniqueConstraint("movie_code", "part", name="uq_movie_files_code_part"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    movie_code = Column(String(64), index=True, nullable=False)
    part = Column(Integer, default=1, nullable=False)
    file_id = Column(String(255), nullable=True, default="")
    file_type = Column(String(32), default="video", nullable=False)  # video yoki document
    file_size = Column(BigInteger, nullable=True)
    duration = Column(Integer, nullable=True)  # soniyalarda
    quality = Column(String(32), default="1080p", nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<MovieFile movie_code={self.movie_code} part={self.part}>"


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
