"""
Parity and integrity tests for Bauntys services & mini apps:
- Zero 161-97-96-58 / SoundHelix / zakirov leaks
- Real Unicode PDF generation (book_service, doc_service)
- Per-user persistence (books, prava, mafia, food, deliv, bunker, duel)
- Kaloriya honest food-image estimate without fake medovik/osh RGB guessing
"""
import io
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def test_bunker_full_game_flow(tmp_path, monkeypatch):
    import services.bunker_service as bunker_mod

    monkeypatch.setattr(bunker_mod, "_BUNKER_STATE_PATH", str(tmp_path / "bunker_state.json"))
    svc = bunker_mod.BunkerService()

    created = svc.create_room(1001, "Sardor", "Bunker Alpha", max_players=6, pub=True)
    assert created["ok"] is True
    code = created["code"]
    assert len(code) == 4

    bots = svc.add_bots(1001, count=3, code=code)
    assert bots["ok"] is True
    assert bots["added"] == 3
    assert len(bots["room"]["players"]) == 4

    started = svc.start_game(1001, code=code)
    assert started["ok"] is True
    room = started["room"]
    assert room["phase"] == "reveal"
    assert len(room["players"]) == 4

    self_player = next(p for p in room["players"] if p["u"] == 1001)
    assert set(self_player["cards"].keys()) == {"kasb", "sogliq", "biologiya", "xobbi", "bagaj", "fakt"}
    assert "special" in self_player and self_player["special"]["t"]

    rev = svc.reveal_card(1001, card_key="kasb", code=code)
    assert rev["ok"] is True
    assert rev["card"] == "kasb"
    assert rev["room"]["phase"] == "vote"

    target = next(p for p in rev["room"]["players"] if p["u"] != 1001 and p["alive"])
    voted = svc.vote(1001, target_id=target["u"], code=code)
    assert voted["ok"] is True
    after_vote = voted["room"]
    assert after_vote["phase"] in ("result", "end")
    exiled = [p for p in after_vote["players"] if not p["alive"]]
    assert len(exiled) == 1

    # Verify stats persist cleanly once game reaches end
    rounds_guard = 0
    while after_vote["phase"] != "end" and rounds_guard < 10:
        rounds_guard += 1
        nxt = svc.next_round(1001, code=code)
        assert nxt["ok"] is True
        after_vote = nxt["room"]
        if after_vote["phase"] == "end":
            break
        self_alive = next((p["alive"] for p in after_vote["players"] if p["u"] == 1001), False)
        if self_alive and after_vote["phase"] == "reveal":
            rev2 = svc.reveal_card(1001, code=code)
            assert rev2["ok"] is True
            after_vote = rev2["room"]
        if self_alive and after_vote["phase"] == "vote":
            tgt2 = next(p for p in after_vote["players"] if p["u"] != 1001 and p["alive"])
            voted2 = svc.vote(1001, target_id=tgt2["u"], code=code)
            assert voted2["ok"] is True
            after_vote = voted2["room"]

    assert after_vote["phase"] == "end"
    assert (tmp_path / "bunker_state.json").exists()


def test_deliv_order_create_and_tracking_persistence(tmp_path, monkeypatch):
    import services.deliv_service as deliv_mod

    state_file = tmp_path / "deliv_state.json"
    monkeypatch.setattr(deliv_mod, "_DELIV_STATE_PATH", str(state_file))
    svc = deliv_mod.DelivService()

    home = svc.get_home(user_id=2001)
    assert home["ok"] is True
    assert len(home["stores"]) >= 4
    assert len(home["steps"]) == 4

    created = svc.create_order(
        user_id=2001,
        user_name="Dilnoza",
        address="Chilonzor tumani, 9-kvartal, 14-uy",
        phone="+998901112233",
        items=[{"name": "Toshkent oshi", "qty": 2, "price": 42000}],
        store_id="baunty_milliy",
        payment="naqd",
    )
    assert created["ok"] is True
    code = created["code"]
    assert code.startswith("BNT-")
    assert created["order"]["step"] == 0
    assert created["order"]["status_title"] == "Qabul qilindi"

    expected_titles = ["Tayyorlanmoqda", "Yo'lda", "Yetkazildi"]
    for idx, title in enumerate(expected_titles, start=1):
        res = svc.advance_status(code)
        assert res["ok"] is True
        assert res["order"]["step"] == idx
        assert res["order"]["status_title"] == title

    # Reload via fresh instance from persisted JSON
    svc_reloaded = deliv_mod.DelivService()
    tracked = svc_reloaded.get_order(code, user_id=2001)
    assert tracked["ok"] is True
    assert tracked["order"]["status_title"] == "Yetkazildi"
    assert len(tracked["order"]["timeline"]) == 4


def test_food_catalog_random_wheel_and_persistence(tmp_path, monkeypatch):
    import services.food_service as food_mod

    state_file = tmp_path / "food_state.json"
    monkeypatch.setattr(food_mod, "_FOOD_STATE_PATH", str(state_file))
    svc = food_mod.FoodService()

    cat = svc.get_catalog(user_id=3001)
    assert cat["ok"] is True
    assert cat["total"] >= 18
    required_keys = {"id", "t", "e", "c", "k", "ml", "mn", "lv", "sv", "d", "tip", "ing", "st"}
    for recipe in cat["items"]:
        assert required_keys.issubset(recipe.keys())
        assert len(recipe["ing"]) >= 2
        assert len(recipe["st"]) >= 2

    rnd = svc.get_random(meal="b", exclude_ids=[5, 11])
    assert rnd["ok"] is True
    assert "b" in rnd["r"]["ml"]
    assert rnd["r"]["id"] not in (5, 11)

    fav_res = svc.toggle_fav(3001, 1)
    assert fav_res["ok"] is True
    assert fav_res["on"] is True
    assert 1 in fav_res["fav"]

    cook_res = svc.mark_cook(3001, 1)
    assert cook_res["ok"] is True
    before_ck = svc.get_recipe(1)["ck"]
    assert cook_res["ck"] == before_ck

    # Reload persisted favorites & cooks
    svc2 = food_mod.FoodService()
    me = svc2.get_user_me(3001)
    assert 1 in me["fav"]
    assert svc2.get_recipe(1)["ck"] == before_ck


def test_duel_create_answer_score_and_pvp(tmp_path, monkeypatch):
    import services.duel_service as duel_mod

    state_file = tmp_path / "duel_state.json"
    monkeypatch.setattr(duel_mod, "_DUEL_STATE_PATH", str(state_file))
    svc = duel_mod.DuelService()

    bot_match = svc.create_duel(4001, "Temur", topic="mixed", vs_bot=True, num_questions=5)
    assert bot_match["ok"] is True
    code = bot_match["code"]
    assert bot_match["duel"]["phase"] == "active"
    assert len(bot_match["duel"]["questions"]) == 5

    raw_room = svc.quiz_rooms[code]
    for qi in range(5):
        correct_idx = raw_room["questions"][qi]["a"]
        ans = svc.submit_answer(4001, q_idx=qi, choice=correct_idx, code=code, elapsed_sec=2.0)
        assert ans["ok"] is True
        assert ans["right"] is True
        assert ans["points"] > 100

    final_state = svc.get_state(code, user_id=4001)
    assert final_state["ok"] is True
    assert final_state["duel"]["phase"] == "end"
    assert final_state["duel"]["winner"] is not None
    assert state_file.exists()

    # Test 2-player PvP room join
    pvp = svc.create_duel(4002, "Nodira", vs_bot=False, num_questions=5)
    assert pvp["duel"]["phase"] == "lobby"
    joined = svc.join_duel(4003, "Kamol", code=pvp["code"])
    assert joined["ok"] is True
    assert joined["duel"]["phase"] == "active"
    assert len(joined["duel"]["players"]) == 2


def test_book_service_unicode_pdf_and_user_state_persistence(tmp_path, monkeypatch):
    import services.book_service as book_mod

    src = Path(book_mod.__file__).read_text(encoding="utf-8")
    assert "161-97-96-58" not in src
    assert "_fetch_upstream_book_aiohttp" not in src

    pdf_bytes = book_mod.create_book_pdf_sample(
        {
            "id": 9901,
            "title": "O'tkan kunlar — Ўткан кунлар",
            "author": "Abdulla Qodiriy",
            "category": "badiiy",
            "lang": "uz",
            "year": 1926,
            "pages": 320,
            "desc": "O'zbek romanchiligi durdonasi: ў, қ, ғ, ҳ va кирилл матни.",
        }
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000

    state_file = tmp_path / "books_state.json"
    monkeypatch.setattr(book_mod, "_BOOKS_STATE_PATH", str(state_file))

    book_mod.save_user_progress(5001, 1, ch=3, off=0.45, pct=62.5, secs=120)
    book_mod.toggle_shelf(5001, 1, saved=True, stars=5)
    note_res = book_mod.add_note(5001, 1, ch=3, q="Iqtibos", note="Ajoyib badiiy asar!", pos=12)
    assert note_res["ok"] is True

    me = book_mod.get_user_book_me(5001, 1)
    assert me["ch"] == 3
    assert me["pct"] == 62.5
    assert me["saved"] is True
    assert me["stars"] == 5
    assert len(me["notes"]) == 1

    full_state = book_mod.get_user_state(5001)
    assert full_state["stats"]["secs"] == 120
    assert any(str(b["i"]) == "1" for b in full_state["shelf"])

    del_res = book_mod.delete_note(5001, note_res["id"])
    assert del_res["deleted"] is True
    assert book_mod.get_user_book_me(5001, 1)["notes"] == []


def test_doc_service_cyrillic_pdf(tmp_path):
    from services.doc_service import doc_service

    out_pdf = tmp_path / "uzbek_cyrillic_sample.pdf"
    res_path = doc_service.create_simple_pdf(
        title="Ўзбекистон Маданияти — Ҳисобот",
        text=(
            "Бу ҳужжат ўзбек кирилл (ў, қ, ғ, ҳ, А-Я) ва лотин (o', g', sh, ch) "
            "ҳарфларини тўғри PDF кўринишида сақлашни текширади."
        ),
        output_path=str(out_pdf),
    )
    assert os.path.exists(res_path)
    data = Path(res_path).read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 500


@pytest.mark.asyncio
async def test_music_no_soundhelix_and_honest_play_track(monkeypatch):
    import inspect
    import services.music_data as mdata
    from services.music_service import music_service

    data_src = Path(mdata.__file__).read_text(encoding="utf-8")
    svc_src = Path(inspect.getfile(music_service.__class__)).read_text(encoding="utf-8")
    banned_demo = "sound" + "helix"
    assert banned_demo not in data_src.lower()
    assert banned_demo not in svc_src.lower()
    assert "161-97-96-58" not in svc_src

    for t in mdata.TOP_50_TRACKS:
        url = str(t.get("url") or "")
        assert banned_demo not in url.lower()

    # Empty/demo track without resolvers should return honest stream_not_found error
    monkeypatch.setattr(music_service, "_search_tarona", AsyncMock(return_value=[]))
    monkeypatch.setattr(music_service, "_search_deezer", AsyncMock(return_value=[]))
    monkeypatch.setattr(music_service, "_search_itunes", AsyncMock(return_value=[]))

    class _EmptyYDL:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, *args, **kwargs):
            return None

    import types
    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=_EmptyYDL))

    failed = await music_service.play_track(
        track_info={"title": "Test", "artist": "Artist", "url": f"https://www.{banned_demo}.com/examples/mp3/Track-1.mp3"},
        title="Test",
        artist="Artist",
    )
    assert failed["ok"] is False
    assert failed["error"] == "stream_not_found"

    # Real preview URL returned by resolver should succeed cleanly
    monkeypatch.setattr(
        music_service,
        "_search_itunes",
        AsyncMock(return_value=[{
            "title": "Yomg'ir",
            "artist": "Konsta",
            "preview": "https://audio-ssl.itunes.apple.com/sample.m4a",
            "u": "https://audio-ssl.itunes.apple.com/sample.m4a",
        }]),
    )
    resolved = await music_service.play_track(title="Yomg'ir", artist="Konsta")
    assert resolved["ok"] is True
    assert resolved["url"] == "https://audio-ssl.itunes.apple.com/sample.m4a"


def test_prava_60_unique_questions_local_image_and_persistence(tmp_path, monkeypatch):
    import services.prava_service as prava_mod

    assert len(prava_mod.SEED_QUESTIONS) >= 60
    unique_prompts = {q["q"].strip() for q in prava_mod.SEED_QUESTIONS}
    assert len(unique_prompts) >= 60
    topics_covered = {int(q["t"]) for q in prava_mod.SEED_QUESTIONS}
    assert topics_covered == set(range(12))

    stats_file = tmp_path / "prava_stats.json"
    monkeypatch.setattr(prava_mod, "_PRAVA_STATS_PATH", stats_file)
    svc = prava_mod.PravaService()

    for q in svc._all_questions:
        assert "(#" not in q["q"]

    img_bytes = svc.generate_question_image_bytes(1)
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 1000
    assert img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP"

    svg = svc.generate_question_svg(1)
    assert svg.startswith("<svg") and "</svg>" in svg

    q1 = svc._all_questions[0]
    svc.check_answer(q1["id"], q1["a"], user_id=6001)
    svc.save_bilet_score(1, 9, user_id=6001)
    assert stats_file.exists()

    svc_reloaded = prava_mod.PravaService()
    home = svc_reloaded.get_home_data(user_id=6001)
    assert home["img"] >= 700
    assert home["solved"] >= 1
    assert home["bilets"][0]["s"] == 9


def test_kaloriya_honest_image_estimate_without_api_key(monkeypatch):
    from PIL import Image
    from services.kaloriya_service import kaloriya_service

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Synthetic textured warm food-colored image (different quadrants so not blank/monochrome)
    img = Image.new("RGB", (120, 120), (195, 130, 75))
    for x in range(120):
        for y in range(120):
            img.putpixel((x, y), ((170 + (x * 7) % 60), (105 + (y * 5) % 55), (50 + ((x + y) * 3) % 45)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    res = kaloriya_service.scan_food_text_or_image(photo_data=buf.getvalue())
    assert res["ok"] is True
    assert res["estimated"] is True
    assert res["needs_confirmation"] is True
    assert res["editable"] is True
    assert "Tahrirlash" in res.get("hint_prompt", "")
    names_lower = " ".join(str(i.get("name", "")).lower() for i in res.get("items", []))
    assert "medovik" not in names_lower
    assert "osh" not in names_lower


def test_mafia_real_stats_and_stale_room_cleanup(tmp_path, monkeypatch):
    import services.mafia_service as mafia_mod

    stats_file = tmp_path / "mafia_stats.json"
    monkeypatch.setattr(mafia_mod, "_MAFIA_STATS_PATH", str(stats_file))
    svc = mafia_mod.MafiaService()

    # Never return hardcoded fake 3 games / 2 wins / 1200 rating
    init_stats = svc.get_user_stats(7001, "Bobur")
    assert init_stats["games"] == 0
    assert init_stats["wins"] == 0
    assert init_stats["rating"] == 1000

    room_res = svc.create_room(7001, "Bobur", "Test Xona", pub=True)
    assert room_res["ok"] is True
    room = svc.rooms[room_res["room"]["id"]]
    svc.join_room(7002, "Jasur", room.id)
    for p in room.players:
        p["role"] = "civ" if p["u"] == 7001 else "maf"
    svc._record_game_end(room, "civ")

    svc2 = mafia_mod.MafiaService()
    saved = svc2.get_user_stats(7001, "Bobur")
    assert saved["games"] == 1
    assert saved["wins"] == 1
    assert saved["rating"] > 1000

    # Stale lobby room cleanup removes expired rooms cleanly
    stale_room_res = svc2.create_room(7009, "Eski", "Stale", pub=True)
    stale_room = svc2.rooms[stale_room_res["room"]["id"]]
    stale_room.left_at = time.time() - 5000
    if hasattr(stale_room, "last_activity"):
        stale_room.last_activity = time.time() - 5000
    removed = svc2.cleanup_stale_rooms(lobby_ttl=100)
    assert removed >= 1
    assert stale_room.id not in svc2.rooms


@pytest.mark.asyncio
async def test_web_server_parity_endpoints(tmp_path, monkeypatch):
    """End-to-end aiohttp TestClient parity check for all core & ported endpoints."""
    import io
    from PIL import Image
    from aiohttp.test_utils import TestClient, TestServer
    import services.web_server as ws
    import services.bunker_service as bunker_mod
    import services.deliv_service as deliv_mod
    import services.duel_service as duel_mod
    import services.book_service as book_mod
    import services.food_service as food_mod

    # Isolate mutable JSON state files in tmp_path
    monkeypatch.setattr(bunker_mod, "_BUNKER_STATE_PATH", str(tmp_path / "bunker_api.json"))
    monkeypatch.setattr(deliv_mod, "_DELIV_STATE_PATH", str(tmp_path / "deliv_api.json"))
    monkeypatch.setattr(duel_mod, "_DUEL_STATE_PATH", str(tmp_path / "duel_api.json"))
    monkeypatch.setattr(book_mod, "_BOOKS_STATE_PATH", tmp_path / "books_state.json")
    monkeypatch.setattr(food_mod, "_FOOD_STATE_PATH", str(tmp_path / "food_state.json"))

    bunker_mod.bunker_service.__init__()
    deliv_mod.deliv_service.__init__()
    duel_mod.duel_service.__init__()
    food_mod.food_service.__init__()

    # Clear FX alert memory for clean deterministic assertion
    ws._FX_ALERTS_BY_USER.clear()

    app = ws.create_web_app()
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        # 1. /api/catalog & feature flags
        r_cat = await client.get("/api/catalog")
        assert r_cat.status == 200
        d_cat = await r_cat.json()
        assert d_cat["ok"] is True
        assert d_cat["bunker"] is True
        assert d_cat["deliv"] is True
        assert d_cat["duel"] is True
        item_101 = next((x for x in d_cat.get("items", []) if str(x.get("c")) == "101"), None)
        assert item_101 is not None and int(item_101.get("p", 0)) == 8

        # 2. /api/movies/101 & /api/asil/item?id=101
        r_mov = await client.get("/api/movies/101")
        assert r_mov.status == 200
        d_mov = await r_mov.json()
        assert d_mov["ok"] is True
        assert d_mov["p"] == 8 and d_mov["parts"] == 8

        r_asil = await client.get("/api/asil/item?id=101")
        assert r_asil.status == 200
        d_asil = await r_asil.json()
        assert d_asil["ok"] is True
        assert int(d_asil["item"]["parts"]) >= 8
        assert len(d_asil["item"]["files"]) >= 8

        # 3. /api/bunker/*
        r_bnk_c = await client.post("/api/bunker/create?user_id=9101", json={"name": "Sinov Bunker", "max": 6, "pub": True})
        assert r_bnk_c.status == 200
        d_bnk_c = await r_bnk_c.json()
        assert d_bnk_c["ok"] is True
        bnk_code = d_bnk_c["code"]

        r_bnk_b = await client.post("/api/bunker/bot?user_id=9101", json={"code": bnk_code, "count": 3})
        assert (await r_bnk_b.json())["ok"] is True
        r_bnk_s = await client.post("/api/bunker/start?user_id=9101", json={"code": bnk_code})
        assert (await r_bnk_s.json())["room"]["phase"] == "reveal"
        r_bnk_h = await client.get("/api/bunker/home?user_id=9101")
        assert (await r_bnk_h.json())["ok"] is True

        # 4. /api/deliv/*
        r_dlv_o = await client.post("/api/deliv/order?user_id=9102", json={
            "addr": "Amir Temur 1", "phone": "+998901234567",
            "items": [{"id": "osh", "title": "Osh", "price": 45000, "qty": 1}],
            "pay": "naqd",
        })
        assert r_dlv_o.status == 200
        d_dlv_o = await r_dlv_o.json()
        assert d_dlv_o["ok"] is True
        oid = d_dlv_o["order"]["id"]
        r_dlv_h = await client.get("/api/deliv/home?user_id=9102")
        assert (await r_dlv_h.json())["ok"] is True
        r_dlv_a = await client.post("/api/deliv/advance?user_id=9102", json={"id": oid})
        assert (await r_dlv_a.json())["ok"] is True

        # 5. /api/food*
        r_food = await client.get("/api/food?user_id=9103")
        d_food = await r_food.json()
        assert d_food["ok"] is True and len(d_food["items"]) > 0
        rec_id = d_food["items"][0]["id"]
        assert (await (await client.get(f"/api/food/r/{rec_id}?user_id=9103")).json())["ok"] is True
        assert (await (await client.post("/api/food/fav?user_id=9103", json={"id": rec_id})).json())["ok"] is True
        assert (await (await client.get("/api/food/me?user_id=9103")).json())["ok"] is True

        # 6. /api/duel/*
        assert (await (await client.get("/api/duel?user_id=9104")).json())["ok"] is True
        d_duel = await (await client.post("/api/duel/code?user_id=9104", json={"g": "chess", "pub": True})).json()
        assert d_duel["ok"] is True and d_duel["code"]
        assert (await (await client.get("/api/duel/poll?user_id=9104")).json())["ok"] is True

        fid = None
        out_fid = None
        # 7. /api/docs/* (config, multipart upload -> img2pdf run -> job poll)
        assert (await (await client.get("/api/docs/config")).json())["ok"] is True
        img = Image.new("RGB", (60, 60), (40, 80, 160))
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        import aiohttp
        form = aiohttp.FormData()
        form.add_field("file", img_buf.getvalue(), filename="test_doc.png", content_type="image/png")
        d_up = await (await client.post("/api/docs/upload", data=form)).json()
        assert d_up["ok"] is True
        fid = d_up["file"]["fid"]
        d_run = await (await client.post("/api/docs/run", json={"tool": "img2pdf", "fids": [fid]})).json()
        assert d_run["ok"] is True and len(d_run["job"]["result"]["files"]) == 1
        out_fid = d_run["job"]["result"]["files"][0]["fid"]
        jid = d_run["job"]["id"]
        d_job = await (await client.get(f"/api/docs/job/{jid}")).json()
        assert d_job["ok"] is True and d_job["job"]["state"] == "done"

        # 8. /api/books/*
        d_bhome = await (await client.get("/api/books/home")).json()
        assert d_bhome["ok"] is True and len(d_bhome["items"]) > 0
        first_bid = d_bhome["items"][0]["i"]
        assert (await (await client.post("/api/books/shelf?user_id=9105", json={"i": first_bid, "saved": True})).json())["ok"] is True
        assert (await (await client.post("/api/books/progress?user_id=9105", json={"i": first_bid, "ch": 2, "pct": 35.0, "secs": 60})).json())["ok"] is True
        assert (await (await client.post("/api/books/note?user_id=9105", json={"i": first_bid, "ch": 1, "q": "Iqtibos", "n": "Izoh"})).json())["ok"] is True
        assert (await (await client.post("/api/books/audio?user_id=9105", json={"i": first_bid, "n": 1, "t": 120, "secs": 30})).json())["ok"] is True
        d_bme = await (await client.get("/api/books/me?user_id=9105")).json()
        assert d_bme["ok"] is True and len(d_bme["shelf"]) == 1 and len(d_bme["notes"]) == 1 and len(d_bme["audio"]) == 1
        d_bdet = await (await client.get(f"/api/books/b/{first_bid}?user_id=9105")).json()
        assert d_bdet["ok"] is True and d_bdet["book"]["me"]["saved"] is True
        assert (await client.get(f"/api/books/page/{first_bid}/9999")).status == 404
        assert (await client.post("/api/books/admin/delete", json={"i": first_bid}, headers={"X-Require-Strict-Admin": "1"})).status == 403

        # 9. /api/fx*
        d_fx = await (await client.get("/api/fx")).json()
        assert d_fx["ok"] is True
        assert (await (await client.post("/api/fx/alerts?user_id=9106", json={"c": "USD", "op": "lt", "v": 13000})).json())["ok"] is True
        d_fxa = await (await client.get("/api/fx/alerts?user_id=9106")).json()
        assert len(d_fxa["items"]) == 1 and d_fxa["items"][0]["c"] == "USD"
        assert (await (await client.get("/api/fx/h/USD")).json())["ok"] is True
        assert (await (await client.get("/api/fx/banks/USD")).json())["ok"] is True

        # 10. /api/reklama (dynamic user count, never hardcoded 250000)
        class _FakeSessionCM:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def scalar(self, *args, **kwargs):
                return 42

        monkeypatch.setattr(ws, "get_session", lambda: _FakeSessionCM())
        d_rek = await (await client.get("/api/reklama")).json()
        assert d_rek["ok"] is True and d_rek["users"] == 42 and d_rek["users"] != 250000

        # 11. /api/story (no fake mov_bbb.mp4)
        assert (await client.get("/api/story")).status == 400
        monkeypatch.setattr(ws.story_service, "get_user_profile_and_stories", AsyncMock(return_value={"ok": False, "error": "story_not_found", "items": []}))
        r_st = await client.get("/api/story?username=unknown_user")
        assert r_st.status == 404
        assert "mov_bbb" not in await r_st.text()

        # 12. /prava/1.webp
        r_pv = await client.get("/prava/1.webp")
        assert r_pv.status == 200
        pv_bytes = await r_pv.read()
        assert pv_bytes[:4] == b"RIFF" and pv_bytes[8:12] == b"WEBP"
    finally:
        for clean_id in (locals().get("fid"), locals().get("out_fid")):
            if clean_id:
                for p in (ws.BASE_DIR / "data" / "docs_tmp").glob(f"{clean_id}*"):
                    p.unlink(missing_ok=True)
        await client.close()
