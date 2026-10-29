"""Mafia, Rasxod, Kaloriya va Telegram Cloud Media integratsiya testlari.
100% Bauntys brendi.
"""

import pytest
import pytest_asyncio
import datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from database.models import (
    Base,
    Movie,
    MovieFile,
    Expense,
    ExpenseBudget,
    UserCalorieProfile,
    CalorieLogItem,
    MafiaGameRecord,
)
from database import crud
from services.rasxod_service import rasxod_service
from services.kaloriya_service import kaloriya_service
from services.mafia_service import mafia_service, MafiaRoom
from services.movie_service import movie_service, MovieService
from services.web_server import (
    handle_rasxod_api,
    handle_kaloriya_api,
    handle_mafia_api,
    handle_send_to_chat,
    create_web_app,
)
from handlers.start import cmd_start
from handlers.mafia import cmd_mafia, cb_mafia_quick, cb_mafia_rules, cb_mafia_stats
from handlers.rasxod import cmd_rasxod, cmd_budget, cb_rasxod_month, cb_rasxod_today, cb_rasxod_help
from handlers.kaloriya import cmd_kaloriya, cb_kal_today, cb_kal_search_hint, cb_kal_profile
from handlers.movies import handle_channel_movie_post
from config import config


@pytest_asyncio.fixture
async def in_memory_session():
    """In-memory SQLite testi uchun fixture."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


def make_session_ctx(session_obj):
    @asynccontextmanager
    async def _ctx():
        yield session_obj
        await session_obj.commit()
    return _ctx


# =====================================================================
# 1. RASXOD (EXPENSE TRACKER) TESTLARI
# =====================================================================

def test_rasxod_text_parsing_and_category_detection():
    """Matndan xarajat miqdori va toifasini ajratish testi."""
    parsed = crud.parse_expense_text("non 8 ming, taksi 25000, obed 45k va benzin 1.5 mln")
    assert len(parsed) == 4

    # 1. Non 8 ming -> food (8000)
    assert parsed[0]["a"] == 8000
    assert "non" in parsed[0]["n"]
    assert parsed[0]["c"] == "food"

    # 2. Taksi 25000 -> transport (25000)
    assert parsed[1]["a"] == 25000
    assert "taksi" in parsed[1]["n"]
    assert parsed[1]["c"] == "transport"

    # 3. Obed 45k -> food (45000)
    assert parsed[2]["a"] == 45000
    assert "obed" in parsed[2]["n"]
    assert parsed[2]["c"] == "food"

    # 4. Benzin 1.5 mln -> transport (1500000)
    assert parsed[3]["a"] == 1500000
    assert "benzin" in parsed[3]["n"]
    assert parsed[3]["c"] == "transport"


@pytest.mark.asyncio
async def test_rasxod_crud_and_monthly_summary(in_memory_session: AsyncSession):
    """Rasxod CRUD operatsiyalari va oylik statistika hisoblash testi."""
    user_id = 12345
    today_str = datetime.date.today().isoformat()
    month_str = datetime.date.today().strftime("%Y-%m")

    # 1. Xarajat qo'shish
    exp1 = await crud.add_expense(
        session=in_memory_session,
        user_id=user_id,
        amount=50000,
        note="Taksi xarajati",
        category="transport",
        date_str=today_str
    )
    exp2 = await crud.add_expense(
        session=in_memory_session,
        user_id=user_id,
        amount=150000,
        note="Supermarket non va oziq-ovqat",
        category="food",
        date_str=today_str
    )
    assert exp1.id is not None
    assert exp2.id is not None

    # 2. Byudjet o'rnatish
    await crud.set_expense_budget(in_memory_session, user_id=user_id, month=month_str, amount=1000000)
    b = await crud.get_expense_budget(in_memory_session, user_id=user_id, month=month_str)
    assert b == 1000000

    # 3. Oylik hisobotni tekshirish
    summary = await crud.get_monthly_expense_summary(in_memory_session, user_id=user_id, year_month=month_str)
    assert summary["total"] == 200000
    assert summary["budget"] == 1000000
    assert summary["n"] == 2

    # 4. Xarajatni tahrirlash va o'chirish
    edited = await crud.edit_expense(in_memory_session, expense_id=exp1.id, user_id=user_id, amount=60000, note="Taksi yangilangan", date=today_str)
    assert edited is True

    deleted = await crud.delete_expense(in_memory_session, expense_id=exp2.id, user_id=user_id)
    assert deleted is True

    items = await crud.get_expenses(in_memory_session, user_id=user_id, month=month_str)
    assert len(items) == 1
    assert items[0].amount == 60000


@pytest.mark.asyncio
async def test_rasxod_service_and_api(in_memory_session: AsyncSession):
    """Rasxod servisi va Web Server API endpointlari testi."""
    ctx = make_session_ctx(in_memory_session)
    with patch("services.rasxod_service.get_session", ctx), \
         patch("database.session.get_session", ctx):

        user_id = 998877

        # 1. Text orqali xarajatlar kiritish
        add_res = await rasxod_service.add_expenses_from_text(user_id=user_id, text="non 10 ming, kofe 25k")
        assert add_res["ok"] is True
        assert len(add_res["saved"]) == 2

        # 2. Home ma'lumotlarini olish
        home = await rasxod_service.get_home(user_id=user_id)
        assert home["ok"] is True
        assert home["spent"] == 35000

        # 3. Web API /api/rasxod/home
        req = make_mocked_request("GET", f"/api/rasxod/home?user_id={user_id}")
        resp = await handle_rasxod_api(req)
        assert resp.status == 200
        import json
        data = json.loads(resp.text)
        assert data["ok"] is True
        assert data["spent"] == 35000


@pytest.mark.asyncio
async def test_rasxod_bot_handlers(in_memory_session: AsyncSession):
    """Rasxod bot komandalari va callbacklari testi."""
    ctx = make_session_ctx(in_memory_session)
    with patch("services.rasxod_service.get_session", ctx), \
         patch("database.session.get_session", ctx):

        message = AsyncMock()
        message.from_user.id = 555111
        message.from_user.first_name = "Ali"
        message.text = "/rasxod"

        await cmd_rasxod(message)
        assert message.answer.called
        sent_text = message.answer.call_args[0][0]
        assert "Baunty Rasxod" in sent_text

        # /budget komandasi
        message.text = "/budget 2500000"
        await cmd_budget(message)
        assert "Oylik byudjet belgilandi" in message.answer.call_args[0][0]

        # callback rasxod:help
        call = AsyncMock()
        call.from_user.id = 555111
        call.data = "rasxod:help"
        await cb_rasxod_help(call)
        assert call.message.edit_text.called


# =====================================================================
# 2. KALORIYA (NUTRITION TRACKER) TESTLARI
# =====================================================================

def test_calorie_profile_math_and_plan():
    """Mifflin-St Jeor formulasi va makroslar hisoblash testi."""
    plan_male = crud.calculate_calorie_plan(
        sex="m",
        age=25,
        height=180.0,
        weight=85.0,
        target_weight=75.0,
        months=3,
        activity=3,
        goal="lose"
    )
    assert plan_male["bmr"] > 1700
    assert plan_male["tdee"] > plan_male["bmr"]
    assert plan_male["kcal"] < plan_male["tdee"]  # Ozish uchun defitsit
    assert plan_male["macro"]["p"] > 0
    assert plan_male["macro"]["f"] > 0
    assert plan_male["macro"]["c"] > 0

    plan_female = crud.calculate_calorie_plan(
        sex="f",
        age=22,
        height=165.0,
        weight=50.0,
        target_weight=55.0,
        months=2,
        activity=2,
        goal="gain"
    )
    assert plan_female["kcal"] > plan_female["tdee"]  # Vazn yig'ish uchun profitsit


@pytest.mark.asyncio
async def test_kaloriya_crud_and_service(in_memory_session: AsyncSession):
    """Kaloriya CRUD va servisi testi."""
    ctx = make_session_ctx(in_memory_session)
    with patch("services.kaloriya_service.get_session", ctx), \
         patch("database.session.get_session", ctx):

        user_id = 444333

        # 1. Profilni yangilash
        prof = await kaloriya_service.update_profile(
            user_id=user_id,
            sex="m",
            age=28,
            height=175.0,
            weight=78.0,
            target=70.0,
            months=3,
            activity=3,
            goal="lose"
        )
        assert prof["ok"] is True
        assert prof["profile"]["target_weight"] == 70.0

        # 2. Taomni skanerlash / tahlil qilish
        scan_res = kaloriya_service.scan_food_text_or_image("osh 300g va non 100 gr")
        assert scan_res["ok"] is True
        assert len(scan_res["items"]) >= 2
        assert scan_res["total"]["kcal"] > 500

        # 3. Taom qo'shish
        add_res = await kaloriya_service.add_meal(
            user_id=user_id,
            meal="l",
            items=scan_res["items"]
        )
        assert add_res["ok"] is True
        assert add_res["saved"] >= 2

        # 4. Statusni tekshirish
        status = await kaloriya_service.get_status(user_id=user_id)
        assert status["ok"] is True
        assert status["today"]["kcal"] > 500
        assert len(status["meals"]["l"]["items"]) >= 2

        # 5. Web API /api/kal/status
        req = make_mocked_request("GET", f"/api/kal/status?user_id={user_id}")
        resp = await handle_kaloriya_api(req)
        assert resp.status == 200


@pytest.mark.asyncio
async def test_kaloriya_bot_handlers(in_memory_session: AsyncSession):
    """Kaloriya bot komandalari va callbacklari testi."""
    ctx = make_session_ctx(in_memory_session)
    with patch("services.kaloriya_service.get_session", ctx), \
         patch("database.session.get_session", ctx):

        message = AsyncMock()
        message.from_user.id = 777222
        message.from_user.first_name = "Diyor"
        message.text = "/kaloriya"

        await cmd_kaloriya(message)
        assert message.answer.called
        sent = message.answer.call_args[0][0]
        assert "Baunty Kaloriya" in sent

        call = AsyncMock()
        call.from_user.id = 777222
        call.data = "kal:search_hint"
        await cb_kal_search_hint(call)
        assert call.message.edit_text.called


# =====================================================================
# 3. MAFIA (ONLINE MULTIPLAYER ENGINE) TESTLARI
# =====================================================================

def test_mafia_engine_and_roles():
    """Mafia o'yin tizimi, rollar taqsimoti va xonalar testi."""
    service = mafia_service
    u1, u2, u3, u4, u5 = 101, 102, 103, 104, 105

    # 1. Xona yaratish
    c_res = service.create_room(user_id=u1, user_name="Host1", room_name="Test Xona", max_players=6)
    room_id = c_res["room"]["id"]
    assert room_id is not None

    # 2. O'yinchilarni qo'shish
    service.join_room(user_id=u2, user_name="Player2", room_id=room_id)
    service.join_room(user_id=u3, user_name="Player3", room_id=room_id)
    service.join_room(user_id=u4, user_name="Player4", room_id=room_id)
    service.join_room(user_id=u5, user_name="Player5", room_id=room_id)

    # 3. Chat xabari yuborish
    msg_res = service.send_chat_message(user_id=u2, user_name="Player2", text="Hammaga salom!")
    assert msg_res["ok"] is True

    # 4. O'yinni boshlash
    start_res = service.start_game(user_id=u1)
    assert start_res["ok"] is True
    assert start_res["room"]["phase"] in ("night", "morning", "day")

    # Rollar taqsimlanganini tekshirish
    room = service.get_room(room_id)
    assert room is not None
    roles = [p["role"] for p in room.players]
    assert len(roles) == 5
    assert "don" in roles or "maf" in roles
    assert "doc" in roles
    assert "kom" in roles

    # 5. Ovoz berish
    room.phase = "vote"
    vote_res = service.vote(user_id=u2, target_id=u3)
    assert vote_res["ok"] is True


@pytest.mark.asyncio
async def test_mafia_api_and_bot_handlers():
    """Mafia Web API va bot komandalari testi."""
    # 1. Web API /api/mafia/home
    req = make_mocked_request("GET", "/api/mafia/home?user_id=101")
    resp = await handle_mafia_api(req)
    assert resp.status == 200
    import json
    data = json.loads(resp.text)
    assert data["ok"] is True
    assert "rooms" in data

    # 2. Bot handler /mafia
    message = AsyncMock()
    message.from_user.id = 101
    message.from_user.first_name = "Sardor"
    message.text = "/mafia"
    await cmd_mafia(message)
    assert message.answer.called
    sent_text = message.answer.call_args[0][0]
    assert "Baunty Mafia" in sent_text

    # 3. Bot callback mafia:rules va mafia:stats
    call = AsyncMock()
    call.from_user.id = 101
    call.from_user.first_name = "Sardor"
    call.data = "mafia:rules"
    await cb_mafia_rules(call)
    assert call.message.edit_text.called

    call.data = "mafia:stats"
    await cb_mafia_stats(call)
    assert call.message.edit_text.called


# =====================================================================
# 4. TELEGRAM CLOUD STORAGE & MEDIA DELIVERY TESTLARI
# =====================================================================

@pytest.mark.asyncio
async def test_storage_channel_post_ingestion(in_memory_session: AsyncSession):
    """Storage channel -1004254432863 ga post tushganda avtomatik video indekslanishi testi."""
    ctx = make_session_ctx(in_memory_session)
    with patch("handlers.movies.get_session", ctx), \
         patch("database.session.get_session", ctx):

        # Storage kanal posti mock
        msg = AsyncMock()
        msg.chat.id = -1004254432863
        msg.chat.username = "BauntyFilms"
        msg.video = MagicMock(
            file_id="BAACAgIAAxkBAAIB_cloud_vid_12345",
            duration=7200,
            file_size=1500 * 1024 * 1024,
            file_name="Taksi_1_718.mp4"
        )
        msg.document = None
        msg.caption = "#718 Taksi 1 (1998) 1080p Full HD"
        msg.text = None

        await handle_channel_movie_post(msg)

        # Bazada saqlanganini tekshirish
        m = await crud.get_movie_by_code(in_memory_session, "718")
        assert m is not None
        assert m.file_id == "BAACAgIAAxkBAAIB_cloud_vid_12345"

        mf = await crud.get_movie_file(in_memory_session, "718", 1)
        assert mf is not None
        assert mf.file_id == "BAACAgIAAxkBAAIB_cloud_vid_12345"


@pytest.mark.asyncio
async def test_deliver_movie_sends_media_from_cloud(in_memory_session: AsyncSession):
    """Kino so'ralganda link o'rniga haqiqiy video media bot.send_video orqali yuborilishi testi."""
    # 1. Bazaga kino va Telegram Cloud file_id kiritish
    await crud.upsert_movie(
        session=in_memory_session,
        code="718",
        title="Taksi 1",
        description="Fransuz komediya klassikasi",
        file_id="BAACAgIAAxkBAAIB_taxi1_cloud_fid",
        file_type="video",
        duration=5400,
        views_count=100
    )
    await crud.save_movie_file(
        session=in_memory_session,
        movie_code="718",
        part=1,
        file_id="BAACAgIAAxkBAAIB_taxi1_cloud_fid",
        file_type="video",
        duration=5400
    )
    await in_memory_session.commit()

    bot = AsyncMock()
    delivered = await MovieService._deliver_movie_impl(
        bot=bot,
        chat_id=12345678,
        code="718",
        part=1,
        session=in_memory_session
    )
    assert delivered is True
    # Haqiqiy media yuborilganini tekshirish
    assert bot.send_video.called
    kwargs = bot.send_video.call_args[1]
    assert kwargs["video"] == "BAACAgIAAxkBAAIB_taxi1_cloud_fid"
    assert "Baunty" in kwargs["caption"]
    assert "Zakirov" not in kwargs["caption"]


@pytest.mark.asyncio
async def test_web_app_routes_registered():
    """aiohttp web application barcha yangi marshrutlarni to'liq qamrab olgani testi."""
    app = create_web_app()
    routes = [r.resource.canonical for r in app.router.routes() if hasattr(r, "resource") and hasattr(r.resource, "canonical")]

    # Rasxod, Kaloriya va Mafia marshrutlari ro'yxatda mavjudligini tasdiqlash
    assert "/api/rasxod" in routes or any("/api/rasxod" in r for r in routes)
    assert "/api/kal" in routes or any("/api/kal" in r for r in routes)
    assert "/api/mafia" in routes or any("/api/mafia" in r for r in routes)


def make_mock_json_request(method: str, path: str, data=None):
    req = make_mocked_request(method, path)
    if data is not None:
        req.json = AsyncMock(return_value=data)
    else:
        req.json = AsyncMock(return_value={})
    return req


@pytest.mark.asyncio
async def test_mafia_api_detailed_actions_and_protocol():
    """Mafia API: look, join by code, act, vote, skip, chat va to_dict_for_user protokoli testi."""
    import json
    service = mafia_service
    # 1. Xona yaratish
    create_req = make_mock_json_request("POST", "/api/mafia/create?user_id=201&user_name=Host201", {"name": "VIP Mafia", "max": 6})
    create_resp = await handle_mafia_api(create_req)
    assert create_resp.status == 200
    create_data = json.loads(create_resp.text)
    assert create_data["ok"] is True
    room_dict = create_data["room"]
    room_code = room_dict["code"]
    assert len(room_code) == 4 and room_code.isdigit()

    # 2. Xonaga kod orqali qo'shilish (join with code)
    join_req = make_mock_json_request("POST", "/api/mafia/join?user_id=202&user_name=Player202", {"code": room_code})
    join_resp = await handle_mafia_api(join_req)
    assert join_resp.status == 200
    assert json.loads(join_resp.text)["ok"] is True

    # Boshqa o'yinchilarni qo'shish
    service.join_room(user_id=203, user_name="Player203", room_id=room_dict["id"])
    service.join_room(user_id=204, user_name="Player204", room_id=room_dict["id"])
    service.join_room(user_id=205, user_name="Player205", room_id=room_dict["id"])

    # 3. api/mafia/look (qahramon va rang tanlash)
    look_req = make_mock_json_request("POST", "/api/mafia/look?user_id=202", {"lk": "taksi", "c": 3})
    look_resp = await handle_mafia_api(look_req)
    assert look_resp.status == 200
    assert json.loads(look_resp.text)["ok"] is True
    # O'yinchining lk va c qiymatini tekshirish
    room = service.get_room(room_dict["id"])
    p202 = next(p for p in room.players if p["id"] == 202)
    assert p202["lk"] == "taksi"
    assert p202["c"] == 3

    # 4. O'yinni boshlash
    start_req = make_mock_json_request("POST", "/api/mafia/start?user_id=201")
    start_resp = await handle_mafia_api(start_req)
    assert start_resp.status == 200
    start_data = json.loads(start_resp.text)
    assert start_data["ok"] is True
    r_state = start_data["room"]

    # Protocol maydonlari mavjudligini tasdiqlash
    expected_keys = {
        "id", "code", "ver", "phase", "left", "day", "me", "host", "in", "alive",
        "role", "role_info", "min", "pub", "group", "players", "targets", "acted",
        "kmode", "myvote", "mafv", "skip", "skipped", "cond", "checks", "ch", "chat", "mid", "winner"
    }
    assert expected_keys.issubset(r_state.keys())
    for pl in r_state["players"]:
        assert {"id", "n", "lk", "c", "alive", "host", "v"}.issubset(pl.keys())

    # 5. api/mafia/act (tungi harakat)
    act_req = make_mock_json_request("POST", "/api/mafia/act?user_id=201", {"t": 203, "m": "act"})
    act_resp = await handle_mafia_api(act_req)
    assert act_resp.status == 200
    act_data = json.loads(act_resp.text)
    assert act_data["ok"] is True
    assert "room" in act_data

    # 6. api/mafia/skip
    skip_req = make_mock_json_request("POST", "/api/mafia/skip?user_id=202")
    skip_resp = await handle_mafia_api(skip_req)
    assert skip_resp.status == 200
    assert json.loads(skip_resp.text)["ok"] is True

    # 7. api/mafia/vote (ovoz berish uchun vote fazasiga o'tkazamiz)
    room.phase = "vote"
    vote_req = make_mock_json_request("POST", "/api/mafia/vote?user_id=202", {"t": 203})
    vote_resp = await handle_mafia_api(vote_req)
    assert vote_resp.status == 200
    vote_data = json.loads(vote_resp.text)
    assert vote_data["ok"] is True
    p203 = next(p for p in vote_data["room"]["players"] if p["id"] == 203)
    assert 202 in p203["v"]

    # 8. api/mafia/chat (ch va t parametrlarini qabul qilish)
    chat_req = make_mock_json_request("POST", "/api/mafia/chat?user_id=201&user_name=Host201", {"ch": "all", "t": "Men tinch aholiman!", "e": "🕵️"})
    chat_resp = await handle_mafia_api(chat_req)
    assert chat_resp.status == 200
    chat_data = json.loads(chat_resp.text)
    assert chat_data["ok"] is True
    assert any("Men tinch aholiman!" in m["t"] for m in chat_data["room"]["chat"])


@pytest.mark.asyncio
async def test_kaloriya_receipt_and_admin_endpoints(in_memory_session: AsyncSession):
    """Kaloriya: api/kal/receipt va api/kal/adm/* endpointlari testi."""
    import json
    ctx = make_session_ctx(in_memory_session)
    with patch("services.kaloriya_service.get_session", ctx), \
         patch("database.session.get_session", ctx):

        user_id = 881122

        # 1. api/kal/receipt (chek yuklanganda get_status formatida qaytishi)
        rec_req = make_mock_json_request("POST", f"/api/kal/receipt?user_id={user_id}", {"receipt": "Payme check #12345"})
        rec_resp = await handle_kaloriya_api(rec_req)
        assert rec_resp.status == 200
        rec_data = json.loads(rec_resp.text)
        assert rec_data["ok"] is True
        assert rec_data["pro"]["on"] is True
        assert "p" in rec_data
        assert "r" in rec_data
        assert "day" in rec_data

        # 2. api/kal/adm/items
        adm_items_req = make_mock_json_request("GET", f"/api/kal/adm/items?user_id={user_id}")
        adm_items_resp = await handle_kaloriya_api(adm_items_req)
        assert adm_items_resp.status == 200
        adm_items_data = json.loads(adm_items_resp.text)
        assert adm_items_data["ok"] is True
        assert "items" in adm_items_data

        # 3. api/kal/adm/stats
        adm_stats_req = make_mock_json_request("GET", f"/api/kal/adm/stats?user_id={user_id}")
        adm_stats_resp = await handle_kaloriya_api(adm_stats_req)
        assert adm_stats_resp.status == 200
        adm_stats_data = json.loads(adm_stats_resp.text)
        assert adm_stats_data["ok"] is True
        assert "stats" in adm_stats_data


@pytest.mark.asyncio
async def test_send_to_chat_part_parameter():
    """api/send-to-chat kino qismini (part) deliver_movie ga to'g'ri yetkazish testi."""
    import json
    mock_bot = AsyncMock()
    with patch("services.web_server.movie_service.deliver_movie", new_callable=AsyncMock) as mock_deliver, \
         patch("services.web_server._bot_instance", mock_bot):
        mock_deliver.return_value = True

        req = make_mock_json_request("POST", "/api/send_to_chat", {"user_id": 123456, "code": "718", "part": 3})
        resp = await handle_send_to_chat(req)
        assert resp.status == 200
        data = json.loads(resp.text)
        assert data["ok"] is True

        assert mock_deliver.called
        kwargs = mock_deliver.call_args[1]
        assert kwargs["code"] == "718"
        assert kwargs["part"] == 3


@pytest.mark.asyncio
async def test_mafia_deep_link_start_flow(in_memory_session: AsyncSession):
    """/start maf_7777 deep link orqali cmd_mafia chaqirilishi va startapp parametri uzatilishi testi."""
    ctx = make_session_ctx(in_memory_session)
    with patch("database.session.get_session", ctx), \
         patch("handlers.start.get_session", ctx):

        msg = AsyncMock()
        msg.from_user.id = 665544
        msg.from_user.first_name = "Botir"
        msg.from_user.username = "botir_test"
        msg.from_user.last_name = None
        msg.text = "/start maf_7777"
        msg.chat.id = 665544
        msg.message_id = 999

        state = AsyncMock()
        await cmd_start(msg, state)

        assert msg.answer.called
        call_args = msg.answer.call_args
        sent_text = call_args[0][0]
        reply_markup = call_args[1].get("reply_markup")

        assert "Baunty Mafia" in sent_text
        assert "#7777" in sent_text
        assert reply_markup is not None
        # WebApp tugmasida startapp=maf_7777 bo'lishini tekshirish
        web_app_btn = reply_markup.inline_keyboard[0][0]
        assert "startapp=maf_7777" in web_app_btn.web_app.url


def test_kaloriya_multilingual_queries_and_non_food_rejection():
    """Eda AI: Ruscha, O'zbekcha va Inglizcha taom so'rovlari hamda non-food rasmlarni rad etish testi."""
    from PIL import Image
    import io

    # 1. Ruscha so'rovlar
    res_ru1 = kaloriya_service.scan_food_text_or_image(text="плов 300г")
    assert res_ru1["ok"] is True
    assert res_ru1["items"][0]["n"] == "Osh (Palov)"
    assert res_ru1["items"][0]["g"] == 300
    assert res_ru1["items"][0]["kcal"] > 500

    res_ru2 = kaloriya_service.scan_food_text_or_image(text="шашлык 200 грамм")
    assert res_ru2["ok"] is True
    assert res_ru2["items"][0]["n"] == "Shashlik"
    assert res_ru2["items"][0]["g"] == 200

    res_ru3 = kaloriya_service.scan_food_text_or_image(text="2 самсы")
    assert res_ru3["ok"] is True
    assert res_ru3["items"][0]["n"] == "Somsa"
    assert res_ru3["items"][0]["g"] == 360

    # 2. Shirinliklar va ichimliklar (Medovik, tort, qahva)
    res_sweet = kaloriya_service.scan_food_text_or_image(text="1 bo'lak medovik va qora choy")
    assert res_sweet["ok"] is True
    assert len(res_sweet["items"]) == 2
    assert any("Medovik" in it["n"] for it in res_sweet["items"])
    assert any("Choy" in it["n"] for it in res_sweet["items"])

    # 3. Yeyilmaydigan matn filtri
    res_non = kaloriya_service.scan_food_text_or_image(text="telefon sotiladi")
    assert res_non["ok"] is False
    assert res_non["error"] == "not_food"

    res_non_ru = kaloriya_service.scan_food_text_or_image(text="куплю машину или ноутбук")
    assert res_non_ru["ok"] is False
    assert res_non_ru["error"] == "not_food"

    # 4. Yeyilmaydigan rasm filtri (qora ekran, sovuq ko'k ekran, oq qog'oz)
    img_black = Image.new("RGB", (80, 80), color=(0, 0, 0))
    buf_black = io.BytesIO()
    img_black.save(buf_black, format="JPEG")
    res_img_black = kaloriya_service.scan_food_text_or_image(photo_data=buf_black.getvalue())
    assert res_img_black["ok"] is False
    assert res_img_black["error"] == "not_food"

    img_blue = Image.new("RGB", (80, 80), color=(15, 60, 240))
    buf_blue = io.BytesIO()
    img_blue.save(buf_blue, format="JPEG")
    res_img_blue = kaloriya_service.scan_food_text_or_image(photo_data=buf_blue.getvalue())
    assert res_img_blue["ok"] is False
    assert res_img_blue["error"] == "not_food"


@pytest.mark.asyncio
async def test_book_covers_webp_url_and_fast_proxy_fallback():
    """Kitoblar muqovalari uchun WebP formati va asset proxy tekshiruvi."""
    from services.book_service import get_book_cover_url
    from services.web_server import handle_book_asset_proxy

    # 1. get_book_cover_url WebP formatini qaytarishi
    cover_url = get_book_cover_url({"id": "1", "title": "O'tkan kunlar"})
    assert cover_url.endswith("/bk/1/cover_l.webp")

    # 2. handle_book_asset_proxy diskdagi WebP muqovani ultra-tezkor qaytarishi
    req = make_mocked_request("GET", "/bk/1/cover_l.webp")
    req.match_info["tail"] = "1/cover_l.webp"
    resp = await handle_book_asset_proxy(req)
    assert resp.status == 200
    assert resp.content_type == "image/webp"
    assert len(resp.body) > 1000

    # 3. Agar mijoz cover.jpg so'rasa ham, mavjud cover_l.webp ni zudlik bilan berishi
    req_jpg = make_mocked_request("GET", "/bk/1/cover.jpg")
    req_jpg.match_info["tail"] = "1/cover.jpg"
    resp_jpg = await handle_book_asset_proxy(req_jpg)
    assert resp_jpg.status == 200
    assert len(resp_jpg.body) > 1000

