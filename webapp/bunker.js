/* ☢️ Bunker — Omon qolish o'yini mini-ilovasi (Bauntys Space UI).
   <section class="bnk" id="bunker" hidden><div id="bnkview"></div></section> ichiga chiziladi.
   window.ZBunker = { open, close, openRoom } */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };

let opened = false;
let home = null;
let room = null;
let pollTimer = null;
let busy = false;
let toastMsg = "";
let toastT = 0;

function ensureStyles() {
  if ($("bnk-fallback-css")) return;
  const st = document.createElement("style");
  st.id = "bnk-fallback-css";
  st.textContent = `
    .bnk{position:fixed;inset:0;z-index:1050;background:radial-gradient(circle at top,#1c2541 0%,#0b1021 62%,#070a14 100%);color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;flex-direction:column;overflow:hidden}
    .bnk[hidden]{display:none!important}
    .bnk-wrap{flex:1;overflow-y:auto;padding:12px 14px 86px;max-width:680px;width:100%;margin:0 auto;box-sizing:border-box}
    .bnk-top{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 14px;background:rgba(15,23,42,.82);backdrop-filter:blur(14px);border-bottom:1px solid rgba(255,255,255,.08)}
    .bnk-top h2{margin:0;font-size:17px;font-weight:800;letter-spacing:.2px;display:flex;align-items:center;gap:7px}
    .bnk-ib{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);color:#f8fafc;border-radius:12px;padding:7px 11px;font-size:13px;font-weight:700;cursor:pointer}
    .bnk-card{background:rgba(30,41,59,.68);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:14px;margin-bottom:12px;backdrop-filter:blur(10px)}
    .bnk-hero{background:linear-gradient(135deg,rgba(245,158,11,.18),rgba(239,68,68,.15));border-color:rgba(245,158,11,.3)}
    .bnk-btn{background:linear-gradient(135deg,#f59e0b,#ea580c);color:#fff;border:none;border-radius:12px;padding:10px 14px;font-weight:700;font-size:14px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:6px}
    .bnk-btn.sec{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.14);color:#e2e8f0}
    .bnk-btn.danger{background:linear-gradient(135deg,#ef4444,#b91c1c)}
    .bnk-btn:disabled{opacity:.5;cursor:not-allowed}
    .bnk-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
    .bnk-inp{background:rgba(15,23,42,.8);border:1px solid rgba(255,255,255,.16);color:#fff;border-radius:11px;padding:10px 12px;font-size:14px;flex:1;min-width:120px;box-sizing:border-box}
    .bnk-badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;font-weight:800;text-transform:uppercase;background:rgba(245,158,11,.2);color:#fbbf24;border:1px solid rgba(245,158,11,.3)}
    .bnk-badge.ok{background:rgba(16,185,129,.2);color:#34d399;border-color:rgba(16,185,129,.35)}
    .bnk-badge.dead{background:rgba(239,68,68,.2);color:#fca5a5;border-color:rgba(239,68,68,.35)}
    .bnk-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(142px,1fr));gap:8px;margin-top:8px}
    .bnk-slot{background:rgba(15,23,42,.68);border:1px solid rgba(255,255,255,.09);border-radius:12px;padding:9px 10px;text-align:left;color:#f1f5f9}
    .bnk-slot small{display:block;font-size:11px;color:#94a3b8;margin-bottom:2px}
    .bnk-slot b{font-size:13px;line-height:1.3;display:block}
    .bnk-slot.rev{border-color:rgba(16,185,129,.45);background:rgba(6,78,59,.24)}
    .bnk-slot.pick{cursor:pointer;border-color:rgba(245,158,11,.45)}
    .bnk-chat{max-height:175px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;margin:8px 0}
    .bnk-msg{font-size:12.5px;line-height:1.35;background:rgba(15,23,42,.55);padding:6px 10px;border-radius:10px}
    .bnk-msg.sys{color:#fbbf24;background:rgba(245,158,11,.1)}
    .bnk-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1e293b;border:1px solid rgba(245,158,11,.4);color:#fff;padding:9px 16px;border-radius:999px;font-size:13px;font-weight:600;z-index:99;box-shadow:0 8px 28px rgba(0,0,0,.4)}
  `;
  document.head.appendChild(st);
}

function toast(msg) {
  toastMsg = msg;
  clearTimeout(toastT);
  toastT = setTimeout(() => { toastMsg = ""; render(); }, 2800);
  render();
}

async function api(path, body) {
  const opt = {headers: {"X-Init-Data": (tg && tg.initData) || ""}};
  if (body) {
    opt.method = "POST";
    opt.body = JSON.stringify(body);
    opt.headers["Content-Type"] = "application/json";
  }
  const r = await fetch(path, opt);
  try { return await r.json(); } catch (e) { return {ok: false, error: "net"}; }
}

function hostEl() {
  const sec = $("bunker");
  if (!sec) return null;
  let v = $("bnkview");
  if (!v) {
    v = document.createElement("div");
    v.id = "bnkview";
    v.className = "bnk-wrap";
    sec.appendChild(v);
  }
  return v;
}

async function refreshHome() {
  const r = await api("api/bunker/home");
  if (r.ok) {
    home = r;
    if (r.cur) room = r.cur;
  }
  render();
}

async function pollState() {
  if (!opened || !room) return;
  const r = await api(`api/bunker/state?code=${encodeURIComponent(room.code)}`);
  if (r.ok && r.room) {
    room = r.room;
    render();
  }
}

function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(pollState, 2500);
}

function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}

function phaseLabel(ph) {
  return {
    lobby: "Kutish xonasi",
    reveal: "Karta ochish",
    vote: "Ovoz berish",
    result: "Bosqich natijasi",
    end: "O'yin yakunlandi",
  }[ph] || ph;
}

function renderLobby() {
  const rooms = (home && home.rooms) || [];
  return `
    <div class="bnk-card bnk-hero">
      <div class="bnk-badge">4–16 o'yinchi · Bauntys</div>
      <h3 style="margin:8px 0 6px;font-size:19px">☢️ Bunker — Omon qolish o'yini</h3>
      <p style="margin:0 0 12px;font-size:13px;color:#cbd5e1;line-height:1.45">
        Yerda global falokat yuz berdi. Bunkerda joy cheklangan! O'z kasbingiz, sog'lig'ingiz va bagajingizni himoya qiling — eng foydali jamoa omon qoladi.
      </p>
      <div class="bnk-row">
        <input class="bnk-inp" id="bnk-rname" placeholder="Xona nomi (ixtiyoriy)" maxlength="32">
        <select class="bnk-inp" id="bnk-rmax" style="max-width:110px">
          <option value="6">6 kishi</option>
          <option value="8" selected>8 kishi</option>
          <option value="12">12 kishi</option>
          <option value="16">16 kishi</option>
        </select>
        <button class="bnk-btn" data-act="create">+ Xona ochish</button>
      </div>
    </div>

    <div class="bnk-card">
      <div style="font-weight:700;margin-bottom:8px;font-size:14px">🔑 Kod bilan qo'shilish</div>
      <div class="bnk-row">
        <input class="bnk-inp" id="bnk-jcode" placeholder="4 belgili kod (masalan: A7K2)" maxlength="6" style="text-transform:uppercase">
        <button class="bnk-btn sec" data-act="join-input">Kirish</button>
      </div>
    </div>

    <div class="bnk-card">
      <div class="bnk-row" style="justify-content:space-between;margin-bottom:8px">
        <b style="font-size:14px">🌐 Ochiq xonalar</b>
        <button class="bnk-ib" data-act="refresh">↻ Yangilash</button>
      </div>
      ${rooms.length ? rooms.map((rm) => `
        <div class="bnk-row" style="justify-content:space-between;padding:8px 0;border-top:1px solid rgba(255,255,255,.07)">
          <div>
            <b>${esc(rm.name)}</b> <span class="bnk-badge">${esc(rm.code)}</span>
            <div style="font-size:12px;color:#94a3b8">${esc(rm.catastrophe)} · ${rm.players}/${rm.max}</div>
          </div>
          <button class="bnk-btn sec" data-join="${esc(rm.code)}">Qo'shilish</button>
        </div>
      `).join("") : `<div style="font-size:13px;color:#94a3b8">Hozircha ochiq xona yo'q. Yangi xona ochib AI botlar bilan darhol boshlang!</div>`}
    </div>
  `;
}

function renderRoom() {
  const me = room.players.find((p) => p.u === (home && home.me)) || room.players.find((p) => p.host) || room.players[0];
  const alive = room.players.filter((p) => p.alive);
  const b = room.bunker || {};
  const cat = room.catastrophe || {};

  let actionBlock = "";
  if (room.phase === "lobby") {
    actionBlock = `
      <div class="bnk-card">
        <div class="bnk-row" style="justify-content:space-between;margin-bottom:10px">
          <div>
            <b>Xona kodi: <span class="bnk-badge">${esc(room.code)}</span></b>
            <div style="font-size:12.5px;color:#94a3b8;margin-top:4px">O'yinchilar: ${room.players.length}/${room.max} (kamida 4 kishi)</div>
          </div>
          <button class="bnk-btn sec" data-act="leave">Chiqish</button>
        </div>
        ${room.is_host ? `
          <div class="bnk-row">
            <button class="bnk-btn sec" data-act="bots">🤖 +3 AI bot qo'shish</button>
            <button class="bnk-btn" data-act="start" ${room.players.length < 4 ? "disabled" : ""}>🚀 O'yinni boshlash</button>
          </div>
        ` : `<div style="font-size:13px;color:#cbd5e1">Boshlovchi o'yinni boshlashini kuting…</div>`}
      </div>
    `;
  } else if (room.phase === "reveal" && me && me.alive) {
    const cards = Object.entries(me.cards || {});
    actionBlock = `
      <div class="bnk-card bnk-hero">
        <b>🃏 ${room.round}-bosqich: bitta kartangizni oching</b>
        <div style="font-size:12.5px;color:#cbd5e1;margin:4px 0 8px">Ochilmagan kartalardan birini tanlang — qolganlar uning qiymatini ko'radi.</div>
        <div class="bnk-grid">
          ${cards.map(([k, c]) => `
            <button class="bnk-slot ${c.rev ? "rev" : "pick"}" ${c.rev ? "disabled" : `data-rev="${esc(k)}"`}>
              <small>${esc(c.label)} ${c.rev ? "✓ Ochilgan" : "· Ochish"}</small>
              <b>${esc(c.val)}</b>
            </button>
          `).join("")}
        </div>
      </div>
    `;
  } else if (room.phase === "vote" && me && me.alive) {
    actionBlock = `
      <div class="bnk-card bnk-hero">
        <b>🗳 Ovoz berish bosqichi</b>
        <div style="font-size:12.5px;color:#cbd5e1;margin:4px 0 10px">Kim bunker uchun foydasiz? Chiqarib yuborish uchun ovoz bering:</div>
        <div class="bnk-row">
          ${alive.filter((p) => p.u !== me.u).map((p) => `
            <button class="bnk-btn danger" data-vote="${p.u}">${esc(p.n)}</button>
          `).join("")}
        </div>
      </div>
    `;
  } else if (room.phase === "result") {
    const ex = room.last_exiled;
    actionBlock = `
      <div class="bnk-card">
        <b>📊 ${room.round}-bosqich yakuni</b>
        <p style="margin:6px 0 10px;font-size:13.5px;color:#fca5a5">${ex ? `🚪 ${esc(ex.n)} bunkerdan chiqarildi.` : "Bosqich yakunlandi."}</p>
        ${room.is_host ? `<button class="bnk-btn" data-act="next">Keyingi bosqich →</button>` : `<div style="font-size:12.5px;color:#94a3b8">Boshlovchi keyingi bosqichni boshlaydi…</div>`}
      </div>
    `;
  } else if (room.phase === "end") {
    actionBlock = `
      <div class="bnk-card" style="border-color:rgba(16,185,129,.45);background:rgba(6,78,59,.3)">
        <b style="font-size:16px">🏆 O'yin tugadi! Bunkerga kirganlar:</b>
        <div style="margin:8px 0;font-size:14px;color:#a7f3d0">${alive.map((p) => `✅ ${esc(p.n)}`).join(" · ")}</div>
        <button class="bnk-btn sec" data-act="leave">Bosh sahifaga qaytish</button>
      </div>
    `;
  }

  return `
    <div class="bnk-card">
      <div class="bnk-row" style="justify-content:space-between;margin-bottom:6px">
        <span class="bnk-badge">${esc(phaseLabel(room.phase))} · ${room.round}-bosqich</span>
        <button class="bnk-ib" data-act="leave">✕ Chiqish</button>
      </div>
      <div style="font-weight:800;font-size:15px;color:#fbbf24">🚨 ${esc(cat.t || "")}</div>
      <div style="font-size:12.5px;color:#cbd5e1;margin:4px 0 8px">${esc(cat.d || "")}</div>
      <div style="font-size:12px;color:#94a3b8;padding-top:8px;border-top:1px solid rgba(255,255,255,.08)">
        <b>${esc(b.name || "Bunker")}</b> · Joy: <b>${b.slots || 2}</b>/${room.players.length} · ${esc(b.area || "")} · ${esc(b.duration || "")}<br>
        Zaxira: ${esc(b.food || "")} · Jihozlar: ${esc((b.gear || []).join(", "))}
      </div>
    </div>

    ${actionBlock}

    <div class="bnk-card">
      <b style="font-size:14px">👥 O'yinchilar (${alive.length} tirik / ${room.players.length} jami)</b>
      ${room.players.map((p) => `
        <div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,.08);opacity:${p.alive ? 1 : .58}">
          <div class="bnk-row" style="justify-content:space-between">
            <b>${p.bot ? "🤖 " : "👤 "}${esc(p.n)}${me && p.u === me.u ? " (Siz)" : ""}${p.host ? " 👑" : ""}</b>
            <span class="bnk-badge ${p.alive ? "ok" : "dead"}">${p.alive ? "O'yinda" : `Surgun (${p.exiled_round || "?"})`}</span>
          </div>
          ${room.phase !== "lobby" ? `
            <div class="bnk-grid">
              ${Object.values(p.cards || {}).map((c) => `
                <div class="bnk-slot ${c.rev ? "rev" : ""}">
                  <small>${esc(c.label)}</small>
                  <b>${esc(c.val)}</b>
                </div>
              `).join("")}
            </div>
          ` : ""}
        </div>
      `).join("")}
    </div>

    <div class="bnk-card">
      <b style="font-size:13.5px">💬 Bunker chati</b>
      <div class="bnk-chat" id="bnkchat">
        ${(room.chat || []).map((m) => `<div class="bnk-msg ${m.u === 0 ? "sys" : ""}">${m.u ? `<b>${esc(m.n)}:</b> ` : ""}${esc(m.t)}</div>`).join("")}
      </div>
      <div class="bnk-row">
        <input class="bnk-inp" id="bnk-msg" placeholder="Dalil yoki izoh yozing..." maxlength="200">
        <button class="bnk-btn sec" data-act="chat">Yuborish</button>
      </div>
    </div>
  `;
}

function render() {
  const sec = $("bunker");
  if (!sec || !opened) return;
  const host = hostEl();
  if (!host) return;
  const body = room ? renderRoom() : renderLobby();
  sec.innerHTML = `
    <div class="bnk-top">
      <button class="bnk-ib" data-act="back">← Orqaga</button>
      <h2>☢️ Bunker</h2>
      <button class="bnk-ib" data-act="hub">☰ Bo'limlar</button>
    </div>
    <div class="bnk-wrap" id="bnkview">${body}</div>
    ${toastMsg ? `<div class="bnk-toast">${esc(toastMsg)}</div>` : ""}
  `;
  const ch = $("bnkchat");
  if (ch) ch.scrollTop = ch.scrollHeight;
}

async function handleAction(e) {
  const btn = e.target.closest("button");
  if (!btn || busy) return;
  const act = btn.dataset.act;
  if (act === "back") { close(); if (window.ZK_setMode) window.ZK_setMode("kino"); return; }
  if (act === "hub") { if (window.ZHub && window.ZHub.open) window.ZHub.open("bunker"); return; }
  if (act === "refresh") { refreshHome(); return; }

  busy = true;
  try {
    if (act === "create") {
      const name = ($("bnk-rname") && $("bnk-rname").value) || "";
      const maxP = +($("bnk-rmax") && $("bnk-rmax").value) || 8;
      const r = await api("api/bunker/create", {name, max: maxP, pub: true});
      if (r.ok) { room = r.room; haptic("ok"); toast(`☢️ Xona ochildi: ${r.code}`); }
      else toast("⚠️ Xona ochib bo'lmadi");
    } else if (act === "join-input" || btn.dataset.join) {
      const code = btn.dataset.join || ($("bnk-jcode") && $("bnk-jcode").value) || "";
      const r = await api("api/bunker/join", {code});
      if (r.ok) { room = r.room; haptic("ok"); }
      else toast(r.msg || "⚠️ Xonaga kirib bo'lmadi");
    } else if (act === "bots") {
      const r = await api("api/bunker/bot", {code: room.code, count: 3});
      if (r.ok) { room = r.room; haptic("ok"); }
      else toast("⚠️ Bot qo'shib bo'lmadi");
    } else if (act === "start") {
      const r = await api("api/bunker/start", {code: room.code});
      if (r.ok) { room = r.room; haptic("ok"); }
      else toast(r.msg || "⚠️ Kamida 4 o'yinchi kerak");
    } else if (btn.dataset.rev) {
      const r = await api("api/bunker/reveal", {code: room.code, card: btn.dataset.rev});
      if (r.ok) { room = r.room; haptic("ok"); }
    } else if (btn.dataset.vote) {
      const r = await api("api/bunker/vote", {code: room.code, target: +btn.dataset.vote});
      if (r.ok) { room = r.room; haptic("ok"); }
    } else if (act === "next") {
      const r = await api("api/bunker/next", {code: room.code});
      if (r.ok) { room = r.room; }
    } else if (act === "leave") {
      await api("api/bunker/leave", {});
      room = null;
      await refreshHome();
    } else if (act === "chat") {
      const inp = $("bnk-msg");
      const text = inp ? inp.value.trim() : "";
      if (text) {
        const r = await api("api/bunker/chat", {code: room.code, text});
        if (r.ok) { room = r.room; }
      }
    }
  } finally {
    busy = false;
    render();
  }
}

function bindRoot() {
  const sec = $("bunker");
  if (!sec || sec.dataset.bound) return;
  sec.dataset.bound = "1";
  sec.addEventListener("click", handleAction);
  sec.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target && e.target.id === "bnk-msg") {
      const btn = sec.querySelector('[data-act="chat"]');
      if (btn) btn.click();
    }
  });
}

function open() {
  ensureStyles();
  bindRoot();
  const sec = $("bunker");
  if (sec) sec.hidden = false;
  document.body.classList.add("bnk-on");
  opened = true;
  render();
  refreshHome();
  startPolling();
}

function close() {
  opened = false;
  stopPolling();
  document.body.classList.remove("bnk-on");
  const sec = $("bunker");
  if (sec) sec.hidden = true;
}

async function openRoom(code) {
  open();
  if (code) {
    const r = await api("api/bunker/join", {code});
    if (r.ok) { room = r.room; render(); }
  }
}

window.ZBunker = {open, close, openRoom};
})();
