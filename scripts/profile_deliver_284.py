import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from services.movie_service import movie_service
from database.session import init_db

async def main():
    await init_db()
    bot_mock = AsyncMock()
    sent_mock = MagicMock()
    sent_mock.video = MagicMock(file_id="BAACAgIAAxkBAAE_SAMPLE_REAL_717", duration=90, file_size=12000000)
    bot_mock.send_video = AsyncMock(return_value=sent_mock)
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    t0 = time.time()
    print("Starting deliver_movie for code 284...")
    res = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=12345678,
        code="284",
        part=1
    )
    t1 = time.time()
    print(f"deliver_movie returned {res} in {t1 - t0:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
