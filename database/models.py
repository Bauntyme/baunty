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


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    amount = Column(BigInteger, nullable=False)  # so'm
    note = Column(String(255), nullable=False)  # "non", "taksi 25000"
    category = Column(String(64), default="other", nullable=False)  # food, transport, shopping, communal, family, other
    date = Column(String(32), index=True, nullable=False)  # YYYY-MM-DD
    source = Column(String(16), default="t", nullable=False)  # "t" (text) or "v" (voice)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<Expense user_id={self.user_id} amount={self.amount} note={self.note}>"


class ExpenseBudget(Base):
    __tablename__ = "expense_budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "month", name="uq_user_month_budget"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    month = Column(String(16), index=True, nullable=False)  # YYYY-MM
    amount = Column(BigInteger, nullable=False)  # rejalashtirilgan oylik byudjet
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<ExpenseBudget user_id={self.user_id} month={self.month} amount={self.amount}>"


class UserCalorieProfile(Base):
    __tablename__ = "user_calorie_profiles"

    user_id = Column(BigInteger, primary_key=True, autoincrement=False)
    sex = Column(String(16), default="f", nullable=False)  # "f" or "m"
    age = Column(Integer, default=25, nullable=False)
    height = Column(Float, default=170.0, nullable=False)  # cm
    weight = Column(Float, default=70.0, nullable=False)  # kg
    target_weight = Column(Float, default=65.0, nullable=False)  # kg
    months = Column(Integer, default=3, nullable=False)
    activity = Column(Integer, default=3, nullable=False)  # 1 (low), 3 (moderate), 4 (active)
    goal = Column(String(32), default="lose", nullable=False)  # "lose", "keep", "gain"
    force = Column(Boolean, default=False, nullable=False)
    is_pro = Column(Boolean, default=True, nullable=False)  # 100% Pro faollashtirilgan
    pro_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def __repr__(self):
        return f"<UserCalorieProfile user_id={self.user_id} goal={self.goal}>"


class CalorieLogItem(Base):
    __tablename__ = "calorie_log_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    date = Column(String(32), index=True, nullable=False)  # YYYY-MM-DD
    meal = Column(String(16), default="l", nullable=False)  # "b" (breakfast), "l" (lunch), "s" (snack), "d" (dinner)
    name = Column(String(255), nullable=False)
    grams = Column(Integer, default=100, nullable=False)
    kcal = Column(Integer, nullable=False)
    protein = Column(Float, default=0.0, nullable=False)
    fat = Column(Float, default=0.0, nullable=False)
    carbs = Column(Float, default=0.0, nullable=False)
    source = Column(String(16), default="p", nullable=False)  # "p" (photo) or "t" (text)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<CalorieLogItem user_id={self.user_id} name={self.name} kcal={self.kcal}>"


class MafiaGameRecord(Base):
    __tablename__ = "mafia_game_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(64), index=True, nullable=False)
    winner = Column(String(32), nullable=False)  # "civ", "maf", "many", "cancel"
    total_players = Column(Integer, default=0, nullable=False)
    days_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self):
        return f"<MafiaGameRecord room={self.room_id} winner={self.winner}>"

