"""
🚗 Prava (Haydovchilik guvohnomasi imtihoni), SubGate, Donat va Kinolarni video sifatida yetkazish testlari.
To'liq oq brendlangan: Bauntys (@Bauntyfilmsbot va @BauntyFilms).
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp.test_utils import TestClient, TestServer
from config import config, BASE_DIR
from database.session import init_db, get_session
from services.prava_service import prava_service, TOPICS_LIST
from services.web_server import create_web_app, set_bot_instance
from services.movie_service import movie_service, MovieService


def test_prava_service_core_data():
    """Prava xizmati ma'lumotlar bazasi va YHQ talablariga mosligini tekshirish."""
    # 1. Mavzular soni 12 ta
    assert len(TOPICS_LIST) == 12
    # 2. Biletlar soni 125 ta
    assert prava_service.total_bilets == 125
    # 3. Savollar soni 1235 ta
    assert len(prava_service._all_questions) == 1235
    # 4. Barcha savollarda to'g'ri javob indeksi va kamida 2 ta variant mavjud
    for q in prava_service._all_questions[:50]:
        assert "id" in q
        assert "q" in q and len(q["q"]) > 5
        assert "o" in q and len(q["o"]) >= 2
        assert "a" in q and 0 <= q["a"] < len(q["o"])


def test_prava_service_home_and_sets():
    """Prava bosh sahifa ma'lumotlari va savollar to'plamlari (bilet, mavzu, tasodifiy) testi."""
    home = prava_service.get_home_data(user_id=98765)
    assert home["ok"] is True
    assert home["total"] == 1235
    assert len(home["bilets"]) == 125
    assert len(home["topics"]) == 12
    assert "exam" in home
    assert home["exam"]["n"] == 20
    assert home["exam"]["min"] == 25
    assert home["exam"]["err"] == 2

    # Bilet to'plami (b=1)
    bilet_set = prava_service.get_set(kind="b", arg=1, user_id=98765)
    assert bilet_set["ok"] is True
    assert len(bilet_set["qs"]) == 10
    # Xavfsizlik: mijozga oldindan to'g'ri javob "a" yuborilmasligi shart
    for q in bilet_set["qs"]:
        assert "a" not in q
        assert "id" in q and "q" in q and "o" in q

    # Mavzu to'plami (t=0)
    topic_set = prava_service.get_set(kind="t", arg=0, user_id=98765)
    assert topic_set["ok"] is True
    assert len(topic_set["qs"]) > 0

    # Tasodifiy to'plam
    rnd_set = prava_service.get_set(kind="rnd", arg=0, user_id=98765)
    assert rnd_set["ok"] is True
    assert len(rnd_set["qs"]) == 20


def test_prava_answer_verification_and_score():
    """Savol javobini serverda tekshirish va bilet natijasini saqlash testi."""
    user_id = 998877

    # 1-savol to'g'ri javobi
    q1 = prava_service._all_questions[0]
    right_ans = q1["a"]
    wrong_ans = (right_ans + 1) % len(q1["o"])

    # To'g'ri javob berish
    res_right = prava_service.check_answer(q_id=1, choice=right_ans, user_id=user_id)
    assert res_right["ok"] is True
    assert res_right["right"] is True
    assert res_right["a"] == right_ans

    # Noto'g'ri javob berish
    res_wrong = prava_service.check_answer(q_id=1, choice=wrong_ans, user_id=user_id)
    assert res_wrong["ok"] is True
    assert res_wrong["right"] is False

    # Bilet natijasini saqlash
    sb = prava_service.save_bilet_score(bilet_num=1, score=9, user_id=user_id)
    assert sb["ok"] is True

    # Bosh sahifada ushbu bilet natijasi ko'rinishi
    home = prava_service.get_home_data(user_id=user_id)
    b1 = next(b for b in home["bilets"] if b["b"] == 1)
    assert b1["s"] == 9


def test_prava_exam_lifecycle():
    """20 talik rasmiy imtihon simulyatsiyasi (boshlash, javob berish, yakunlash)."""
    user_id = 112233
    exam_start = prava_service.start_exam(user_id=user_id)
    assert exam_start["ok"] is True
    assert len(exam_start["qs"]) == 20
    assert exam_start["max_err"] == 2
    assert exam_start["ends"] > 0

    # 1-savolga javob berish
    ans_res = prava_service.answer_exam(question_idx=0, choice=0, user_id=user_id)
    assert ans_res["ok"] is True
    assert "right" in ans_res
    assert "err" in ans_res

    # Imtihonni yakunlash
    finish_res = prava_service.finish_exam(user_id=user_id)
    assert finish_res["ok"] is True
    assert finish_res["finished"] is True
    assert "passed" in finish_res
    assert finish_res["n"] == 20


@pytest.mark.asyncio
async def test_prava_web_api_endpoints():
    """Web Server Prava API yo'llari (/api/prava/* va /webapp/api/prava/*) to'g'ri ishlashi testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. GET /api/prava/home
        r_home = await client.get("/api/prava/home")
        assert r_home.status == 200
        d_home = await r_home.json()
        assert d_home["ok"] is True
        assert d_home["total"] == 1235

        # Alias /webapp/api/prava/home
        r_home_alias = await client.get("/webapp/api/prava/home")
        assert r_home_alias.status == 200

        # 2. GET /api/prava/set?k=b&a=1
        r_set = await client.get("/api/prava/set?k=b&a=1")
        assert r_set.status == 200
        d_set = await r_set.json()
        assert d_set["ok"] is True
        assert len(d_set["qs"]) == 10

        # 3. POST /api/prava/ans
        r_ans = await client.post("/api/prava/ans", json={"id": 1, "c": 0})
        assert r_ans.status == 200
        d_ans = await r_ans.json()
        assert d_ans["ok"] is True
        assert "right" in d_ans

        # 4. POST /api/prava/bilet
        r_bl = await client.post("/api/prava/bilet", json={"b": 1, "s": 10})
        assert r_bl.status == 200
        d_bl = await r_bl.json()
        assert d_bl["ok"] is True

        # 5. POST /api/prava/exam/start
        r_ex_start = await client.post("/api/prava/exam/start", json={})
        assert r_ex_start.status == 200
        d_ex_start = await r_ex_start.json()
        assert d_ex_start["ok"] is True
        assert len(d_ex_start["qs"]) == 20

        # 6. POST /api/prava/exam/ans
        r_ex_ans = await client.post("/api/prava/exam/ans", json={"k": 0, "c": 0})
        assert r_ex_ans.status == 200
        d_ex_ans = await r_ex_ans.json()
        assert d_ex_ans["ok"] is True

        # 7. POST /api/prava/exam/finish
        r_ex_fin = await client.post("/api/prava/exam/finish", json={})
        assert r_ex_fin.status == 200
        d_ex_fin = await r_ex_fin.json()
        assert d_ex_fin["ok"] is True
        assert d_ex_fin["finished"] is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_sub_and_donate_api_endpoints():
    """/api/sub va /api/donate endpointlari to'g'ri va oq brendlangan holda ishlashi testi."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. GET /api/sub
        r_sub = await client.get("/api/sub")
        assert r_sub.status == 200
        d_sub = await r_sub.json()
        assert d_sub["ok"] is True
        assert "sub" in d_sub

        # 2. GET /api/donate
        r_don = await client.get("/api/donate")
        assert r_don.status == 200
        d_don = await r_don.json()
        assert d_don["ok"] is True
        assert d_don["on"] is True
        assert "Bauntys" in d_don["text"] or "Bauntys" in d_don["name"]
        # Zero branding leaks
        don_str = json.dumps(d_don)
        assert "Zakirov" not in don_str
        assert "dilbar" not in don_str.lower()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_start_prava_deep_link_and_command():
    """Botda /start prava, /start exam va /prava komandalari to'g'ri ishlashi testi."""
    from handlers.start import cmd_start, cmd_prava
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage

    message = AsyncMock()
    message.from_user.id = 554433
    message.from_user.username = "test_driver"
    message.from_user.first_name = "Haydovchi"
    message.from_user.last_name = ""
    message.chat.id = 554433
    message.message_id = 9001
    message.answer = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=__import__("aiogram.fsm.storage.base", fromlist=["StorageKey"]).StorageKey(
        bot_id=1, chat_id=554433, user_id=554433
    ))

    # 1. /start prava
    message.text = "/start prava"
    await cmd_start(message, state)
    assert message.answer.called is True
    ans_text = message.answer.call_args[0][0]
    assert "Haydovchilik guvohnomasi" in ans_text
    assert "1235 ta" in ans_text
    ans_kb = message.answer.call_args.kwargs.get("reply_markup")
    assert ans_kb is not None
    web_app_btn = ans_kb.inline_keyboard[0][0]
    assert "Prava" in web_app_btn.text
    assert "m=prava" in web_app_btn.web_app.url

    # 2. /start exam
    message.answer.reset_mock()
    message.text = "/start exam"
    await cmd_start(message, state)
    assert message.answer.called is True
    ans_kb2 = message.answer.call_args.kwargs.get("reply_markup")
    assert "prava=exam" in ans_kb2.inline_keyboard[0][0].web_app.url

    # 3. /prava
    message.answer.reset_mock()
    message.text = "/prava"
    await cmd_prava(message)
    assert message.answer.called is True
    ans_cmd = message.answer.call_args[0][0]
    assert "Prava" in ans_cmd


@pytest.mark.asyncio
async def test_movie_video_delivery_real_stream():
    """Katalogdagi ixtiyoriy kino va uning qismlari uchun haqiqiy video yuborilishi testi."""
    await init_db()
    bot_mock = AsyncMock()
    sent_video_mock = MagicMock()
    sent_video_mock.video = MagicMock(file_id="BAACAgIAAxkBAAE_SAMPLE_REAL_PERSISTED_TELEGRAM_FID_717", duration=888, file_size=129000000)
    bot_mock.send_video = AsyncMock(return_value=sent_video_mock)
    bot_mock.send_photo = AsyncMock()
    bot_mock.send_message = AsyncMock()

    # Attack on Titan (katalogda 717, 54 qism) 1-qism so'ralganda
    res1 = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=889900,
        code="717",
        part=1
    )
    assert res1 is True
    assert bot_mock.send_video.called is True
    assert bot_mock.send_photo.called is False
    call_kwargs = bot_mock.send_video.call_args.kwargs
    assert call_kwargs["supports_streaming"] is True
    assert ".mp4" in str(call_kwargs["video"]) or "BAAC" in str(call_kwargs["video"])
    assert "Attack on Titan" in call_kwargs["caption"]
    assert "(4K Ultra HD)" in call_kwargs["caption"]

    # 2-qism so'ralganda
    bot_mock.send_video.reset_mock()
    res2 = await movie_service.deliver_movie(
        bot=bot_mock,
        chat_id=889900,
        code="717",
        part=2
    )
    assert res2 is True
    assert bot_mock.send_video.called is True
    assert bot_mock.send_photo.called is False
    call_kwargs2 = bot_mock.send_video.call_args.kwargs
    assert "2-qism" in call_kwargs2["caption"]
    assert call_kwargs2["supports_streaming"] is True
