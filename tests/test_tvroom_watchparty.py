"""
Tv Xona (TV Watch Party) testlari
Room management, channel sync, chat & reactions, WebRTC voice signaling,
API endpoints, and Bot handlers.
100% Bauntys brendi.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from services.tv_room_service import (
    tv_room_service,
    TvRoom,
    TvRoomService,
    normalize_room_code,
    DEFAULT_CHANNEL_ID,
)
from services.web_server import handle_tvroom_api, create_web_app
from handlers.tvroom import (
    cmd_tvroom,
    handle_tvroom_start,
    cb_tvroom_main,
    cb_tvroom_quick,
    cb_tvroom_list,
    cb_tvroom_channels,
    get_tvroom_keyboard,
)
from handlers.start import cmd_start


# =====================================================================
# 1. SERVICES: TV ROOM SERVICE TESTLARI
# =====================================================================

def test_normalize_room_code():
    """Xona kodlarini turli formatlardan standart tv_... formatiga normallashtirish."""
    assert normalize_room_code("tvroom_1234") == "tv_1234"
    assert normalize_room_code("tvxona_5678") == "tv_5678"
    assert normalize_room_code("tv_9999") == "tv_9999"
    assert normalize_room_code("4321") == "tv_4321"
    assert normalize_room_code("PARTY") == "tv_party"


def test_tv_room_creation_and_defaults():
    """Yangi xona yaratilganda standart 4K kanal va host to'g'ri o'rnatilishi."""
    srv = TvRoomService()
    res = srv.create_room(
        user_id=1001,
        user_name="Alisher",
        username="alisher_dev",
        photo_url="https://example.com/avatar.jpg",
        room_name="Alisherning TV Zali",
        pub=True,
    )
    assert res["ok"] is True
    room = res["room"]
    assert room["host_id"] == 1001
    assert room["host_name"] == "Alisher"
    assert room["name"] == "Alisherning TV Zali"
    assert len(room["participants"]) == 1
    assert room["participants"][0]["role"] == "host"
    assert room["participants"][0]["username"] == "alisher_dev"

    # Standart kanal tekshiruvi: Zo'r TV HD (id: 4 yoki 4K UHD)
    ch = room["channel"]
    assert ch["id"] == DEFAULT_CHANNEL_ID
    assert "Zo'r" in ch["name"]
    assert "stream" in ch
    assert "q" in ch

    # Audio constraints tekshiruvi
    ac = room["audio_constraints"]
    assert ac["echoCancellation"] is True
    assert ac["noiseSuppression"] is True
    assert ac["autoGainControl"] is True


def test_tv_room_join_and_leave():
    """Xonaga tomoshabinlar qo'shilishi va chiqib ketishi."""
    srv = TvRoomService()
    create_res = srv.create_room(
        user_id=2001,
        user_name="HostUser",
        custom_code="room77",
    )
    code = create_res["room"]["id"]

    # Viewer 1 qo'shilishi
    join1 = srv.join_room(code, user_id=3001, user_name="Viewer1", username="v1")
    assert join1["ok"] is True
    assert join1["room"]["count"] == 2
    viewers = [p for p in join1["room"]["participants"] if p["user_id"] == 3001]
    assert len(viewers) == 1
    assert viewers[0]["role"] == "viewer"

    # Viewer 2 qo'shilishi
    join2 = srv.join_room(code, user_id=3002, user_name="Viewer2", username="v2")
    assert join2["ok"] is True
    assert join2["room"]["count"] == 3

    # Chiqish testi
    leave1 = srv.leave_room(user_id=3001, room_code=code)
    assert leave1["ok"] is True
    st = srv.get_room_state(code)
    assert st["room"]["count"] == 2


def test_tv_room_host_departure_promotes_next():
    """Host chiqib ketganda qolgan birinchi qatnashuvchi yangi host bo'lishi."""
    srv = TvRoomService()
    create_res = srv.create_room(user_id=5001, user_name="OldHost", custom_code="succ1")
    code = create_res["room"]["id"]

    srv.join_room(code, user_id=5002, user_name="NewHostCandidate")
    srv.join_room(code, user_id=5003, user_name="Viewer")

    # OldHost chiqib ketadi
    srv.leave_room(user_id=5001, room_code=code)

    st = srv.get_room_state(code)
    assert st["ok"] is True
    room = st["room"]
    assert room["host_id"] == 5002
    assert room["host_name"] == "NewHostCandidate"
    p5002 = next(p for p in room["participants"] if p["user_id"] == 5002)
    assert p5002["role"] == "host"


def test_tv_room_channel_synchronization():
    """Faqat xona hosti kanalni o'zgartira olishi va sinxronlash."""
    srv = TvRoomService()
    create_res = srv.create_room(user_id=6001, user_name="SyncHost", custom_code="sync1")
    code = create_res["room"]["id"]
    srv.join_room(code, user_id=6002, user_name="Viewer")

    # Viewer kanalni o'zgartirishga urinsa: rad etilishi kerak
    res_viewer = srv.change_channel(code, user_id=6002, channel_id=3)
    assert res_viewer["ok"] is False
    assert res_viewer["error"] == "permission_denied"

    # Host kanalni o'zgartirsa (masalan id=3, Sevimli TV): muvaffaqiyatli
    res_host = srv.change_channel(code, user_id=6001, channel_id=3)
    assert res_host["ok"] is True
    assert res_host["channel"]["id"] == 3
    assert "Sevimli" in res_host["channel"]["name"]

    # State orqali tekshirish: hamma uchun o'zgargan
    st = srv.get_room_state(code, user_id=6002)
    assert st["room"]["channel"]["id"] == 3


def test_tv_room_chat_and_quick_reactions():
    """Xona chati va tezkor reaksiyalar yuborilishi."""
    srv = TvRoomService()
    create_res = srv.create_room(user_id=7001, user_name="ChatHost", custom_code="chat1")
    code = create_res["room"]["id"]

    # Oddiy matnli xabar
    m1 = srv.send_chat(code, user_id=7001, user_name="ChatHost", text="Salom hammaga! Zo'r kino ketyapti")
    assert m1["ok"] is True
    assert m1["message"]["text"] == "Salom hammaga! Zo'r kino ketyapti"

    # Tezkor reaksiya
    m2 = srv.send_chat(code, user_id=7001, user_name="ChatHost", text="", reaction="🔥")
    assert m2["ok"] is True
    assert m2["message"]["reaction"] == "🔥"

    st = srv.get_room_state(code)
    # Chatda kamida 3 ta xabar bor (1 ta join tizim xabari + 2 ta yangi xabar)
    assert len(st["room"]["chat"]) >= 3


def test_tv_room_voice_signaling_and_mic_state():
    """WebRTC ovozli signalizatsiya va mikrofon holati boshqaruvi."""
    srv = TvRoomService()
    create_res = srv.create_room(user_id=8001, user_name="VoiceHost", custom_code="voice1")
    code = create_res["room"]["id"]
    srv.join_room(code, user_id=8002, user_name="VoicePeer")

    # 1. Mikrofonni faollashtirish signali
    sig_mic = srv.send_signal(
        room_code=code,
        from_uid=8002,
        to_uid="all",
        signal_type="mic_state",
        data={"active": True, "speaking": True},
    )
    assert sig_mic["ok"] is True

    # Tekshirish: qatnashuvchida mic_active va speaking True bo'lishi
    st = srv.get_room_state(code)
    p8002 = next(p for p in st["room"]["participants"] if p["user_id"] == 8002)
    assert p8002["mic_active"] is True
    assert p8002["speaking"] is True

    # 2. WebRTC Offer signali yuborish
    sig_offer = srv.send_signal(
        room_code=code,
        from_uid=8001,
        to_uid=8002,
        signal_type="offer",
        data={"sdp": "v=0..."},
    )
    assert sig_offer["ok"] is True

    # 3. Signallarni qabul qilish (8002 uchun)
    incoming = srv.get_signals(code, user_id=8002, since_ts=0.0)
    assert incoming["ok"] is True
    offers = [s for s in incoming["signals"] if s["type"] == "offer"]
    assert len(offers) == 1
    assert offers[0]["from"] == 8001


def test_tv_room_public_list_and_channels():
    """Ommaviy xonalar va kanallar ro'yxatini olish."""
    srv = TvRoomService()
    channels = srv.get_channels_list()
    assert len(channels) >= 10
    assert any(c["id"] == 3 for c in channels)

    publics = srv.list_public_rooms()
    assert len(publics) >= 1


# =====================================================================
# 2. WEB SERVER API TESTLARI
# =====================================================================

@pytest.mark.asyncio
async def test_api_tvroom_home_and_channels():
    """GET /api/tvroom va /api/tvroom/channels endpointlari."""
    # 1. GET /api/tvroom
    req_home = make_mocked_request("GET", "/api/tvroom")
    resp_home = await handle_tvroom_api(req_home)
    assert resp_home.status == 200
    import json
    data_home = json.loads(resp_home.body)
    assert data_home["ok"] is True
    assert "rooms" in data_home
    assert "channels" in data_home

    # 2. GET /api/tvroom/channels
    req_ch = make_mocked_request("GET", "/api/tvroom/channels")
    resp_ch = await handle_tvroom_api(req_ch)
    assert resp_ch.status == 200
    data_ch = json.loads(resp_ch.body)
    assert data_ch["ok"] is True
    assert len(data_ch["channels"]) > 0


@pytest.mark.asyncio
async def test_api_tvroom_full_lifecycle():
    """API orqali xona ochish, kirish, kanal almashtirish, chat, signal va chiqish."""
    import json

    # 1. POST /api/tvroom/create
    req_create = make_mocked_request(
        "POST",
        "/api/tvroom/create",
        payload=json.dumps({"name": "Test Party Room", "code": "party99"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp_create = await handle_tvroom_api(req_create)
    assert resp_create.status == 200
    data_create = json.loads(resp_create.body)
    assert data_create["ok"] is True
    room_code = data_create["room"]["id"]

    # 2. POST /api/tvroom/join
    req_join = make_mocked_request(
        "POST",
        "/api/tvroom/join",
        payload=json.dumps({"code": room_code, "user_name": "TestFriend"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp_join = await handle_tvroom_api(req_join)
    assert resp_join.status == 200
    data_join = json.loads(resp_join.body)
    assert data_join["ok"] is True

    # 3. GET /api/tvroom/state?room=...
    req_state = make_mocked_request("GET", f"/api/tvroom/state?room={room_code}")
    resp_state = await handle_tvroom_api(req_state)
    assert resp_state.status == 200
    data_state = json.loads(resp_state.body)
    assert data_state["ok"] is True, f"State failed: {data_state}"
    assert data_state["room"]["id"] == room_code

    # 4. POST /api/tvroom/channel
    req_ch = make_mocked_request(
        "POST",
        "/api/tvroom/channel",
        payload=json.dumps({"room": room_code, "channel_id": 4}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp_ch = await handle_tvroom_api(req_ch)
    assert resp_ch.status == 200

    # 5. POST /api/tvroom/chat
    req_msg = make_mocked_request(
        "POST",
        "/api/tvroom/chat",
        payload=json.dumps({"room": room_code, "text": "Ajoyib efir!", "reaction": "👏"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp_msg = await handle_tvroom_api(req_msg)
    assert resp_msg.status == 200
    data_msg = json.loads(resp_msg.body)
    assert data_msg["ok"] is True

    # 6. POST & GET /api/tvroom/signal
    req_sig = make_mocked_request(
        "POST",
        "/api/tvroom/signal",
        payload=json.dumps({"room": room_code, "type": "mic_state", "data": {"active": True}}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp_sig = await handle_tvroom_api(req_sig)
    assert resp_sig.status == 200

    req_sig_get = make_mocked_request("GET", f"/api/tvroom/signal?room={room_code}&since=0")
    resp_sig_get = await handle_tvroom_api(req_sig_get)
    assert resp_sig_get.status == 200

    # 7. POST /api/tvroom/leave
    req_leave = make_mocked_request(
        "POST",
        "/api/tvroom/leave",
        payload=json.dumps({"room": room_code}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp_leave = await handle_tvroom_api(req_leave)
    assert resp_leave.status == 200
    data_leave = json.loads(resp_leave.body)
    assert data_leave["ok"] is True


@pytest.mark.asyncio
async def test_webapp_alias_routing():
    """/webapp/api/tvroom/... prefiksi bilan so'rovlar ham to'liq ishlashi."""
    import json
    req = make_mocked_request("GET", "/webapp/api/tvroom/channels")
    resp = await handle_tvroom_api(req)
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["ok"] is True


# =====================================================================
# 3. BOT HANDLERS & DEEP LINK TESTLARI
# =====================================================================

@pytest.mark.asyncio
async def test_bot_cmd_tvroom():
    """/tvroom va /tvxona komandasi botda to'g'ri ishlashi."""
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 999111
    msg.from_user.first_name = "Jasur"
    msg.from_user.username = "jasur_uz"
    msg.text = "/tvroom"
    msg.answer = AsyncMock()

    await cmd_tvroom(msg)
    msg.answer.assert_called_once()
    args, kwargs = msg.answer.call_args
    assert "Tv Xona" in args[0]
    kb = kwargs["reply_markup"]
    assert any("Tv Xona" in btn.text for row in kb.inline_keyboard for btn in row)


@pytest.mark.asyncio
async def test_bot_cmd_tvroom_with_code():
    """/tvroom 1234 orqali muayyan xona bilan chaqirilganda."""
    msg = MagicMock()
    msg.from_user = MagicMock(id=999222, first_name="Rustam", username="rustam_99")
    msg.text = "/tvroom 1234"
    msg.answer = AsyncMock()

    await cmd_tvroom(msg)
    msg.answer.assert_called_once()
    args, kwargs = msg.answer.call_args
    assert "#1234" in args[0]
    kb = kwargs["reply_markup"]
    assert any("#1234" in btn.text for row in kb.inline_keyboard for btn in row)


@pytest.mark.asyncio
async def test_bot_deep_link_start_tvroom():
    """/start tvroom_4821 orqali botga kirganda to'g'ridan-to'g'ri xonaga yo'naltirish."""
    msg = MagicMock()
    msg.from_user = MagicMock(id=999333, first_name="Botir", username="botir_tg")
    msg.answer = AsyncMock()

    await handle_tvroom_start(msg, "tvroom_4821")
    msg.answer.assert_called_once()
    args, kwargs = msg.answer.call_args
    assert "taklif qildi" in args[0]
    assert "#4821" in args[0]
    kb = kwargs["reply_markup"]
    assert any("Kirish" in btn.text for row in kb.inline_keyboard for btn in row)


@pytest.mark.asyncio
async def test_bot_callbacks():
    """Tv Xona callback menyularining ishlashi."""
    call = MagicMock()
    call.from_user = MagicMock(id=999444, first_name="Aziz", username="aziz_01")
    call.message = MagicMock()
    call.message.edit_text = AsyncMock()
    call.answer = AsyncMock()

    # 1. tvroom:main
    await cb_tvroom_main(call)
    call.message.edit_text.assert_called()

    # 2. tvroom:quick
    await cb_tvroom_quick(call)
    call.message.edit_text.assert_called()

    # 3. tvroom:list
    await cb_tvroom_list(call)
    call.message.edit_text.assert_called()

    # 4. tvroom:channels
    await cb_tvroom_channels(call)
    call.message.edit_text.assert_called()


@pytest.mark.asyncio
async def test_bot_deep_link_start_tv_code():
    """/start tv_7788 kabi xona havolalari ham to'g'ridan-to'g'ri Tv Xonaga yo'nalishi."""
    msg = MagicMock()
    msg.from_user = MagicMock(id=999555, first_name="Doston", username="doston_uz")
    msg.answer = AsyncMock()

    await handle_tvroom_start(msg, "tv_7788")
    msg.answer.assert_called_once()
    args, kwargs = msg.answer.call_args
    assert "#7788" in args[0]
    kb = kwargs["reply_markup"]
    assert any("Kirish" in btn.text for row in kb.inline_keyboard for btn in row)


@pytest.mark.asyncio
async def test_api_tvroom_user_extraction_from_body_and_query():
    """API chaqiruvlarida user_id, username, photo_url to'g'ri o'qilishi va qatnashuvchiga biriktirilishi."""
    import json
    req = make_mocked_request(
        "POST",
        "/api/tvroom/create",
        payload=json.dumps({
            "name": "Avatar Test Room",
            "user_id": 888999,
            "user_name": "Bobur",
            "username": "bobur_avatar",
            "photo_url": "https://cdn.telegram.org/file/bobur.jpg",
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp = await handle_tvroom_api(req)
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["ok"] is True
    p = data["room"]["participants"][0]
    assert p["user_id"] == 888999
    assert p["username"] == "bobur_avatar"
    assert p["photo_url"] == "https://cdn.telegram.org/file/bobur.jpg"


@pytest.mark.asyncio
async def test_webrtc_full_mesh_signaling_exchange():
    """WebRTC mesh: Offer, Answer, ICE Candidate va Speaking signallari to'liq almashinuvi."""
    srv = TvRoomService()
    c_res = srv.create_room(user_id=111, user_name="PeerA", custom_code="mesh1")
    code = c_res["room"]["id"]
    srv.join_room(code, user_id=222, user_name="PeerB")

    # 1. PeerA -> PeerB ga Offer yuboradi
    srv.send_signal(
        room_code=code,
        from_uid=111,
        to_uid=222,
        signal_type="offer",
        data={"sdp": "v=0...offer"},
    )

    # 2. PeerB o'ziga kelgan offerni qabul qiladi
    b_sigs = srv.get_signals(code, user_id=222)
    offers = [s for s in b_sigs["signals"] if s["type"] == "offer"]
    assert len(offers) == 1
    assert offers[0]["data"]["sdp"] == "v=0...offer"

    # 3. PeerB -> PeerA ga Answer yuboradi
    srv.send_signal(
        room_code=code,
        from_uid=222,
        to_uid=111,
        signal_type="answer",
        data={"sdp": "v=0...answer"},
    )

    # 4. PeerA answerni qabul qiladi
    a_sigs = srv.get_signals(code, user_id=111)
    answers = [s for s in a_sigs["signals"] if s["type"] == "answer"]
    assert len(answers) == 1
    assert answers[0]["data"]["sdp"] == "v=0...answer"

    # 5. ICE Candidate almashinuvi
    srv.send_signal(
        room_code=code,
        from_uid=111,
        to_uid=222,
        signal_type="candidate",
        data={"candidate": "candidate:1 1 UDP ..."},
    )
    b_sigs2 = srv.get_signals(code, user_id=222, since_ts=offers[0]["ts"])
    candidates = [s for s in b_sigs2["signals"] if s["type"] == "candidate"]
    assert len(candidates) == 1


@pytest.mark.asyncio
async def test_cmd_start_deep_link_routing_to_tvroom():
    """cmd_start orqali /start tvroom_1234 va /start tv_5678 chaqirilganda to'g'ri ishlashi."""
    from handlers.start import cmd_start

    # Mock message & FSMContext
    msg = MagicMock()
    msg.from_user = MagicMock(id=999666, first_name="Nodir", username="nodir_dev")
    msg.text = "/start tvroom_1234"
    msg.answer = AsyncMock()
    state = MagicMock()
    state.clear = AsyncMock()

    with patch("handlers.tvroom.handle_tvroom_start", new_callable=AsyncMock) as mock_handle:
        await cmd_start(msg, state)
        mock_handle.assert_called_once_with(msg, "tvroom_1234")

    # Mock tv_5678
    msg.text = "/start tv_5678"
    with patch("handlers.tvroom.handle_tvroom_start", new_callable=AsyncMock) as mock_handle2:
        await cmd_start(msg, state)
        mock_handle2.assert_called_once_with(msg, "tv_5678")



@pytest.mark.asyncio
async def test_tvroom_guide_and_controls():
    """Tv Xona to'liq qo'llanmasi, ulashish (share), va yangi menyu tugmalari testi."""
    from handlers.tvroom import (
        cb_tvroom_guide,
        cb_tvroom_code_prompt,
        msg_tvroom_direct_code,
        get_tvroom_keyboard,
    )

    call = MagicMock()
    call.from_user = MagicMock(id=999777, first_name="Jamshid", username="jamshid")
    call.message = MagicMock()
    call.message.edit_text = AsyncMock()
    call.answer = AsyncMock()

    # 1. Guide callback
    await cb_tvroom_guide(call)
    call.message.edit_text.assert_called()
    guide_text = call.message.edit_text.call_args[0][0]
    assert "Qo'llanmasi" in guide_text
    assert "Sinxron" in guide_text
    assert "ovozli" in guide_text.lower()

    # 2. Code prompt callback
    await cb_tvroom_code_prompt(call)
    call.message.edit_text.assert_called()
    prompt_text = call.message.edit_text.call_args[0][0]
    assert "xona kodini" in prompt_text.lower()

    # 3. Rich keyboard buttons
    kb = get_tvroom_keyboard("8822")
    flat_btns = [btn for row in kb.inline_keyboard for btn in row]
    btn_texts = [b.text for b in flat_btns]
    assert any("Kirish (#8822)" in t for t in btn_texts)
    assert any("Yangi Tv Xona ochish" in t for t in btn_texts)
    assert any("Kod orqali kirish" in t for t in btn_texts)
    assert any("Do'stlarni taklif qilish" in t for t in btn_texts)
    assert any("Tv Xona qo'llanmasi" in t for t in btn_texts)
    assert any("Ochiq xonalar" in t for t in btn_texts)

    # Share URL check
    share_btn = next(b for b in flat_btns if "Do'stlarni taklif qilish" in b.text)
    assert share_btn.url is not None
    assert "t.me/share/url" in share_btn.url
    assert "8822" in share_btn.url

    # 4. Direct message room code
    msg = MagicMock()
    msg.from_user = MagicMock(id=999777, first_name="Jamshid")
    msg.text = "8822"
    msg.answer = AsyncMock()

    handled = await msg_tvroom_direct_code(msg)
    assert handled is True
    msg.answer.assert_called_once()
    assert "#8822" in msg.answer.call_args[0][0]

    # Hashtag code (#room12)
    msg_hash = MagicMock()
    msg_hash.from_user = MagicMock(id=999777, first_name="Jamshid")
    msg_hash.text = "#room12"
    msg_hash.answer = AsyncMock()
    assert await msg_tvroom_direct_code(msg_hash) is True
    assert "#room12" in msg_hash.answer.call_args[0][0]

    # Common command words must not be intercepted
    msg_cmd = MagicMock()
    msg_cmd.text = "start"
    assert await msg_tvroom_direct_code(msg_cmd) is False
    msg_cmd.text = "kino"
    assert await msg_tvroom_direct_code(msg_cmd) is False

