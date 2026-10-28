/* 🧠 Viktorina — Mini App bo'limi: yakka o'yin, kunlik savol, jonli xona (kod bilan), o'z viktorinangizni tuzish.
   index.html dan window.ZQuiz orqali boshqariladi (open / close / busy / start / setBot). */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : t === "hit" ? tg.HapticFeedback.impactOccurred("heavy") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
const SH = [  // javob tugmalari: rang + belgi (joylashuv bo'yicha)
  ["a", '<path d="M12 1.5l2.6 4.2 4.8-1.1-1.1 4.8 4.2 2.6-4.2 2.6 1.1 4.8-4.8-1.1L12 22.5l-2.6-4.2-4.8 1.1 1.1-4.8L1.5 12l4.2-2.6-1.1-4.8 4.8 1.1z"/>', "yulduz"],
  ["b", '<path d="M15.5 2.5A10 10 0 1 0 21.5 17 8 8 0 1 1 15.5 2.5z"/>', "oy"],
  ["c", '<path d="M12 2s7 7.6 7 12.5a7 7 0 0 1-14 0C5 9.6 12 2 12 2z"/>', "tomchi"],
  ["d", '<path d="M12 1.8 21 7v10l-9 5.2L3 17V7z"/>', "olti burchak"],
];
const shape = (i) => `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${SH[i % 4][1]}</svg>`;
const ICO = {back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>'};

let bot = "", opened = false, mounted = false, home = null, me = null, daily = null;
const stack = [{v: "home"}];
const top = () => stack[stack.length - 1];
let poll = null, tick = null;

// ------------------------------------------------------------------ yordamchilar
async function api(path, body) {
  try {
    const r = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body ? {"Content-Type": "application/json"} : {}), body: body ? JSON.stringify(body) : undefined});
    if (r.status === 401) return {ok: false, error: "Ilovani bot ichida oching"};
    return await r.json();
  } catch (e) { return {ok: false, error: "Internet aloqasini tekshiring"}; }
}
const toast = (t) => { const el = document.createElement("div"); el.className = "qz-toast"; el.textContent = t; $("quiz").appendChild(el); setTimeout(() => el.remove(), 2400); };
const fmt = (n) => String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
function backBar(title, right = "") { return `<div class="qz-top"><button class="qz-back" data-act="back" aria-label="Orqaga">${ICO.back}</button><b>${title}</b>${right}</div>`; }
function rootHead() {
  const HUB = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>';
  return `<div class="qz-head-clean"><button class="qz-back" data-act="homeback" aria-label="Orqaga">${ICO.back}</button><div class="qz-head-title"><b>🧠 Viktorina</b><small>Bilim sinovi va duel</small></div><button class="zk-hubbtn" data-act="hub" aria-label="Barcha bo'limlar">${HUB}<span>Bo'limlar</span></button></div>`;
}
function segHtml() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["quiz", "Viktorina"]];
  return `<div class="qz-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "quiz" ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`;
}
const roomLink = (pin) => {
  const cleanBot = (bot || (window.Telegram && Telegram.WebApp && Telegram.WebApp.initDataUnsafe && Telegram.WebApp.initDataUnsafe.bot_username) || "BauntyCinemabot").replace(/^@/, "");
  return `https://t.me/${cleanBot}?start=quiz_${pin}`;
};
function stopLoops() { clearTimeout(poll); poll = null; clearInterval(tick); tick = null; }

// ------------------------------------------------------------------ 🏠 bosh sahifa
function viewHome() {
  const tps = home ? home.topics : [];
  const d = daily;
  return `${rootHead()}
  <h1 class="qz-hi">Bilimingizni sinang<span>Yakka o'ynang yoki do'stlaringiz, o'quvchilaringiz bilan bellashing</span></h1>
  <div class="qz-modes"><button class="md solo" data-act="solopick"><i>🎯</i><b>Yakka o'yin</b><small>10 savol · haftalik reyting</small></button>
    <button class="md room" data-act="setup"><i>👥</i><b>Xona ochish</b><small>Kod bilan chaqiring — cheksiz odam</small></button></div>
  <form class="qz-pin" data-form="pin" autocomplete="off"><input id="qzpin" inputmode="numeric" maxlength="6" placeholder="Xona kodi: 482917" aria-label="Xona kodi"><button type="submit">Kirish</button></form>
  ${d ? dailyCard(d) : ""}
  <div class="qz-lh"><span>Mavzular</span><button data-act="weekly">🏆 Haftalik reyting ›</button></div>
  <div class="qz-cats">${tps.map((t) => `<button class="cat" data-solo="${t.k}"${t.c ? "" : " disabled"}><i>${t.ic}</i><b>${esc(t.n)}</b><small>${t.c} savol</small></button>`).join("") || `<div class="qz-load"><i></i><i></i><i></i></div>`}
    <button class="cat mix" data-solo="mix"><i>🎲</i><b>Aralash</b><small>hamma mavzudan</small></button></div>
  <div class="qz-lh"><span>Mening viktorinalarim</span><button data-act="new">＋ Yangi tuzish</button></div>
  ${me && me.mine && me.mine.length ? `<div class="qz-list">${me.mine.map(qcard).join("")}</div>`
    : `<button class="qz-make" data-act="new"><b>✏️ O'z viktorinangizni tuzing</b><small>Dars, sinf yoki do'stlar uchun — savollarni yozing yoki matndan nusxalab qo'ying</small></button>`}
  ${home && home.popular && home.popular.length ? `<div class="qz-lh"><span>Ommabop viktorinalar</span></div><div class="qz-list">${home.popular.map(qcard).join("")}</div>` : ""}`;
}
function qcard(z) {
  return `<button class="qz-qc" data-quiz="${z.id}"><span class="ic">${z.ic}</span><span class="tx"><b>${esc(z.t)}</b><small>${z.n} savol · ${z.src === "seed" ? "Bauntys" : esc(z.a || "Foydalanuvchi")}${z.pl ? ` · ${fmt(z.pl)} marta o'ynalgan` : ""}${z.vis === "link" ? " · 🔒 faqat havola" : ""}</small></span><i>›</i></button>`;
}
function dailyCard(d) {
  if (d.done) {
    const pick = d.q.o.find(([i]) => i === d.my), right = d.q.o.find(([i]) => i === d.c);
    return `<div class="qz-daily done"><div class="dh"><i>🔥</i><b>Kunlik savol</b><em>${d.streak} kun ketma-ket</em></div><p>${esc(d.q.t)}</p>
      <div class="dr ${d.ok ? "ok" : "no"}">${d.ok ? "✓ To'g'ri" : `✗ Siz: ${esc(pick ? pick[1] : "—")}`} · javob: <b>${esc(right ? right[1] : "")}</b></div>
      <small>${fmt(d.n)} kishi javob berdi · ${d.pct}% topdi · ertaga yangi savol</small></div>`;
  }
  return `<div class="qz-daily"><div class="dh"><i>🔥</i><b>Kunlik savol</b><em>${d.streak ? `${d.streak} kun ketma-ket` : `${fmt(d.n)} kishi javob berdi`}</em></div><p>${esc(d.q.t)}</p>
    <div class="dopts">${d.q.o.map(([i, t], k) => `<button class="an ${SH[k % 4][0]}" data-daily="${i}">${shape(k)}<span>${esc(t)}</span></button>`).join("")}</div></div>`;
}

// ------------------------------------------------------------------ 🎯 yakka o'yin
function viewSoloPick() {
  return backBar("Yakka o'yin — mavzu tanlang") + `<div class="qz-cats big">${(home ? home.topics : []).map((t) => `<button class="cat" data-solo="${t.k}"${t.c ? "" : " disabled"}><i>${t.ic}</i><b>${esc(t.n)}</b><small>${t.c} savol</small></button>`).join("")}
    <button class="cat mix" data-solo="mix"><i>🎲</i><b>Aralash</b><small>hamma mavzudan</small></button></div>`;
}
async function soloStart(tp, id) {
  const r = await api("api/quiz/solo/start", id ? {id} : {tp});
  if (!r.ok) { toast(r.error); haptic("err"); return; }
  stopLoops();
  go({v: "solo", sid: r.sid, title: r.title, total: r.total, i: 0, q: r.q, score: 0, res: null, t0: Date.now(), streak: 0, tp, qid: id});
  startSoloTimer();
}
function viewSolo(v) {
  if (v.final) return viewSoloFinal(v);
  const q = v.q, res = v.res;
  return `<div class="qz-qbar"><button class="qz-x" data-act="back" aria-label="Chiqish">✕</button><span>${v.i + 1} / ${v.total}</span><span class="pt">⭐ ${fmt(v.score)}</span></div>
  <div class="qz-prog">${Array.from({length: v.total}, (_, k) => `<i class="${k < v.i ? "d" : k === v.i ? "c" : ""}"></i>`).join("")}</div>
  ${res ? "" : timerRing()}
  <p class="qz-qt${res ? " small" : ""}">${esc(q.t)}</p>
  <div class="qz-ans">${q.o.map(([orig, t], k) => {
    const cls = !res ? "" : orig === res.c ? " right" : orig === res.my ? " wrong" : " dim";
    return `<button class="an ${SH[k % 4][0]}${cls}" data-sa="${orig}"${res ? " disabled" : ""}>${shape(k)}<span>${esc(t)}</span></button>`;
  }).join("")}</div>
  ${res ? `<div class="qz-res ${res.right ? "ok" : "no"}"><b>${res.right ? "To'g'ri! 🎉" : res.my === -1 ? "Vaqt tugadi ⏰" : "Noto'g'ri"}</b>
      ${res.right ? `<span class="pts">+${fmt(res.pts)}</span>` : ""}${res.streak >= 2 ? `<small>🔥 ${res.streak} ta ketma-ket</small>` : ""}</div>
    <div class="qz-row"><button class="qz-rep" data-rep="${res.qid}">⚠️ Savolda xato</button><button class="qz-next" data-act="snext">${res.last ? "Natijani ko'rish" : "Keyingi savol →"}</button></div>` : ""}`;
}
function viewSoloFinal(v) {
  const f = v.final;
  return backBar(esc(v.title)) + `<div class="qz-final"><div class="big">${f.ok >= f.n * 0.8 ? "🏆" : f.ok >= f.n / 2 ? "👏" : "💪"}</div>
    <h2>${fmt(f.score)} ball</h2><p>${f.ok >= f.n * 0.8 ? "Zo'r natija!" : f.ok >= f.n / 2 ? "Yaxshi! Yana bir bor urinib ko'ring." : "Mashq qilsangiz, albatta oshadi!"}</p>
    <div class="qz-stats"><div><b>${f.ok}/${f.n}</b><small>to'g'ri</small></div><div><b>${String(f.avg).replace(".", ",")} s</b><small>o'rtacha tezlik</small></div><div><b>🔥 ${f.best}</b><small>eng uzun seriya</small></div></div>
    <p class="rk">🏆 Haftalik reytingda <b>${f.rank}-o'rin</b></p>
    <div class="qz-row"><button class="qz-next" data-act="replay">🔄 Yana o'ynash</button><button class="qz-sec" data-act="weekly">🏆 Reyting</button></div></div>`;
}
const timerRing = () => `<div class="qz-timer" id="qztimer"><svg viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="44" class="bg"/><circle cx="50" cy="50" r="44" class="fg" id="qzring" stroke-dasharray="276.5" stroke-dashoffset="0"/></svg><b id="qzsec"></b></div>`;
function paintTimer(leftMs, durMs) {
  const s = $("qzsec"), ring = $("qzring");
  if (!s) return;
  const sec = Math.ceil(Math.max(0, leftMs) / 1000);
  s.textContent = sec;
  if (ring) ring.style.strokeDashoffset = String(276.5 * (1 - Math.max(0, leftMs) / Math.max(1, durMs)));
  $("qztimer").classList.toggle("low", sec <= 5);
}
function startSoloTimer() {
  clearInterval(tick);
  const v = top(), dur = v.q.s * 1000;
  v.t0 = Date.now();
  paintTimer(dur, dur);
  tick = setInterval(() => {
    const cur = top();
    if (cur !== v || cur.res) { clearInterval(tick); return; }
    const left = dur - (Date.now() - v.t0);
    paintTimer(left, dur);
    if (left <= 0) { clearInterval(tick); soloAnswer(-1); }
  }, 200);
}
async function soloAnswer(orig) {
  const v = top();
  if (v.v !== "solo" || v.res || v.busy) return;
  v.busy = true; clearInterval(tick);
  const r = await api("api/quiz/solo/answer", {sid: v.sid, i: v.i, o: orig});
  v.busy = false;
  if (!r.ok) { toast(r.error); return; }
  v.res = Object.assign(r, {my: orig}); v.score = r.score;
  haptic(r.right ? "ok" : "err"); render();
}
async function soloNext() {
  const v = top();
  if (v.res && v.res.last && v.res.final) { v.final = v.res.final; render(); return; }
  const r = await api("api/quiz/solo/next", {sid: v.sid});
  if (!r.ok) { toast(r.error || "Xatolik yuz berdi"); return; }
  if (r.final) { v.final = r.final; render(); return; }
  if (!r.q) {
    v.final = (v.res && v.res.final) ? v.res.final : {ok: 0, n: v.total || 10, score: v.score || 0, avg: 0, best: v.streak || 0, rank: 1};
    render();
    return;
  }
  Object.assign(v, {i: r.i ?? (v.i + 1), q: r.q, res: null}); render(); startSoloTimer();
}

// ------------------------------------------------------------------ 👥 xona ochish / qo'shilish
function viewSetup(v) {
  v.n = v.n || 10; v.s = v.s || 20; v.hp = v.hp ?? true;
  const src = v.id ? `<div class="qz-src"><span>📋</span><b>${esc(v.title || "Viktorina")}</b><button data-act="srcclear">O'zgartirish</button></div>`
    : `<div class="qz-cats">${(home ? home.topics : []).map((t) => `<button class="cat${v.tp === t.k ? " on" : ""}" data-stp="${t.k}"${t.c ? "" : " disabled"}><i>${t.ic}</i><b>${esc(t.n)}</b><small>${t.c} savol</small></button>`).join("")}
      <button class="cat mix${v.tp === "mix" ? " on" : ""}" data-stp="mix"><i>🎲</i><b>Aralash</b><small>hamma mavzu</small></button></div>
      ${me && me.mine && me.mine.length ? `<p class="qz-or">yoki o'zingiz tuzgan viktorina:</p><div class="qz-list">${me.mine.map((z) => `<button class="qz-qc" data-sid="${z.id}" data-stitle="${esc(z.t)}"><span class="ic">${z.ic}</span><span class="tx"><b>${esc(z.t)}</b><small>${z.n} savol</small></span><i>›</i></button>`).join("")}</div>` : ""}`;
  return backBar("Xona ochish") + `<p class="qz-lbl">Savollar</p>${src}
    ${v.id ? "" : `<p class="qz-lbl">Savollar soni</p><div class="qz-pills">${[5, 10, 15, 20].map((n) => `<button data-sn="${n}" class="${v.n === n ? "on" : ""}">${n}</button>`).join("")}</div>`}
    <p class="qz-lbl">Har savolga vaqt</p><div class="qz-pills">${[10, 20, 30, 60].map((s) => `<button data-ss="${s}" class="${v.s === s ? "on" : ""}">${s} s</button>`).join("")}</div>
    <button class="qz-toggle${v.hp ? " on" : ""}" data-act="hp" role="switch" aria-checked="${v.hp}"><span><b>Men ham o'ynayman</b><small>${v.hp ? "Siz ham javob berasiz" : "O'qituvchi rejimi: faqat boshqarasiz, ekranni o'quvchilarga ko'rsatasiz"}</small></span><i></i></button>
    <div class="qz-foot"><button class="qz-go" data-act="create"${v.id || v.tp ? "" : " disabled"}>👥 Xonani ochish</button></div>`;
}
async function createRoom() {
  const v = top();
  const r = await api("api/quiz/room", v.id ? {id: v.id, s: v.s, hp: v.hp} : {tp: v.tp, n: v.n, s: v.s, hp: v.hp});
  if (!r.ok) { toast(r.error); haptic("err"); return; }
  haptic("ok");
  stack.pop();
  enterRoom(r.pin);
}
function viewJoin(v) {
  return backBar(`Xona ${esc(v.pin)}`) + `<form class="qz-join" data-form="join"><div class="big">🧠</div><h2>Xonaga kirish</h2><p>O'yinda ko'rinadigan ismingiz:</p>
    <input id="qzname" maxlength="24" value="${esc(v.name || "")}" autocomplete="off" aria-label="Ism"><button type="submit" class="qz-go">▶ Kirish</button>
    ${v.err ? `<p class="err">${esc(v.err)}</p>` : ""}</form>`;
}
async function joinRoom(pin, name) {
  const r = await api(`api/quiz/room/${pin}/join`, {name});
  if (!r.ok) { const v = top(); if (v.v === "join") { v.err = r.error; render(); } else toast(r.error); haptic("err"); return; }
  haptic("ok"); stack.pop(); enterRoom(pin);
}
function enterRoom(pin) {
  stopLoops();
  go({v: "room", pin, st: null});
  pollRoom();
}

// ------------------------------------------------------------------ 🎮 jonli xona
async function pollRoom() {
  clearTimeout(poll);
  const v = top();
  if (!opened || v.v !== "room") return;
  const st = await api(`api/quiz/room/${v.pin}`);
  if (top() !== v) return;
  if (!st.ok) { v.err = st.error; render(); return; }
  const changed = !v.st || st.rev !== v.st.rev || st.phase !== v.st.phase || st.qi !== v.st.qi;
  st.recv = Date.now();
  const prevPhase = v.st && v.st.phase;
  v.st = st;
  if (!st.joined && !st.host) { stack.pop(); go({v: "join", pin: v.pin, name: me ? me.name : ""}); return; }
  if (changed) {
    if (st.phase === "q" && prevPhase !== "q") { v.picked = null; haptic("hit"); }
    if (st.phase === "r" && prevPhase === "q") haptic(st.my && st.my.ok ? "ok" : "err");
    render();
  }
  if (st.phase === "q") startRoomTimer(); else { clearInterval(tick); tick = null; }
  if (st.phase !== "end") poll = setTimeout(pollRoom, st.phase === "lobby" ? 1500 : 800);
}
function startRoomTimer() {
  if (tick) return;
  tick = setInterval(() => {
    const v = top();
    if (v.v !== "room" || !v.st || v.st.phase !== "q") { clearInterval(tick); tick = null; return; }
    const st = v.st, el = Date.now() - st.recv;
    const startIn = st.starts_in - el;
    const box = $("qzwait"), opts = $("qzopts");
    if (startIn > 0) { if (box) box.textContent = Math.ceil(startIn / 1000); return; }
    if (box && !box.hidden) { box.hidden = true; if (opts) opts.classList.remove("hold"); }
    paintTimer(st.left - el, st.dur);
  }, 150);
}
function viewRoom(v) {
  const st = v.st;
  if (v.err) return backBar("Xona") + `<p class="qz-empty">${esc(v.err)}</p>`;
  if (!st) return backBar(`Xona ${esc(v.pin)}`) + `<div class="qz-load"><i></i><i></i><i></i></div>`;
  if (st.phase === "lobby") return viewLobby(v, st);
  if (st.phase === "end") return viewEnd(v, st);
  return viewRoomQ(v, st);
}
function viewLobby(v, st) {
  const link = roomLink(st.pin);
  return backBar(esc(st.title)) + `<p class="qz-cap">${st.host ? "Shu kodni ayting yoki havolani yuboring" : "O'yin boshlanishini kuting…"}</p>
    <div class="qz-bigpin" aria-label="Xona kodi ${st.pin}">${[...st.pin].map((d) => `<span>${d}</span>`).join("")}</div>
    ${st.host && link ? `<div class="qz-row"><button class="qz-tgshare" data-act="share">✈️ Telegramda chaqirish</button><button class="qz-sec" data-act="copy">🔗 Havola</button></div>` : ""}
    <div class="qz-lh"><span>Qo'shilganlar</span><small class="qz-live">● ${st.players} kishi</small></div>
    <div class="qz-ppl">${(st.list || []).map((p) => `<span class="pp${p.me ? " me" : ""}"><i style="background:${p.col}">${p.av}</i>${esc(p.n)}</span>`).join("") || `<p class="qz-empty sm">Hali hech kim yo'q — kodni ulashing</p>`}</div>
    ${st.host ? `<div class="qz-foot"><button class="qz-go" data-host="start"${st.players ? "" : " disabled"}>▶ O'yinni boshlash · ${st.players}/50 kishi</button></div>`
      : `<div class="qz-wait">🎮 Siz o'yindasiz! Boshlovchi o'yinni boshlashini kuting</div>`}`;
}
function viewRoomQ(v, st) {
  const q = st.q, rv = st.reveal, my = st.my;
  const startIn = st.starts_in - (Date.now() - st.recv);
  const canAnswer = st.phase === "q" && st.joined && !my;
  const picked = my ? my.o : v.picked;
  let res = "";
  if (rv) {
    const ok = my && my.ok;
    res = st.joined ? `<div class="qz-res ${ok ? "ok" : "no"}"><b>${!my ? "Javob bermadingiz ⏰" : ok ? "To'g'ri! 🎉" : "Noto'g'ri"}</b>${ok ? `<span class="pts">+${fmt(my.p)}</span>` : ""}
      ${st.me ? `<small>${st.me.rank}-o'rin · ${fmt(st.me.score)} ball${st.me.streak >= 2 ? ` · 🔥 ${st.me.streak}` : ""}</small>` : ""}</div>` : "";
    const nx = Math.max(0, Math.ceil((st.next_in - (Date.now() - st.recv)) / 1000));
    res += `<div class="qz-auto">${st.last ? "🏁 Yakuniy natija" : "⏭ Keyingi savol"} — ${nx} s</div>`;
    res += `<div class="qz-lh"><span>Reyting</span><small>${st.last ? "Oxirgi savol edi" : `${st.total - st.qi - 1} ta savol qoldi`}</small></div>
      <div class="qz-board">${rv.top.map((p, i) => `<div class="lr${st.me && p.u && i + 1 === st.me.rank ? " me" : ""}"><span class="n">${i + 1}</span><span class="av" style="background:${p.col}">${p.av}</span><b>${esc(p.n)}</b><span class="s">${fmt(p.s)}</span><span class="mv ${p.mv > 0 ? "up" : p.mv < 0 ? "dn" : ""}">${p.mv > 0 ? "▲" + p.mv : p.mv < 0 ? "▼" + -p.mv : "—"}</span></div>`).join("")}</div>`;
  }
  const total = rv ? Object.values(rv.counts).reduce((a, b) => a + b, 0) : 0;
  return `<div class="qz-qbar"><button class="qz-x" data-act="back" aria-label="Chiqish">✕</button><span>Savol ${st.qi + 1} / ${st.total}</span><span class="pt">${st.me ? `⭐ ${fmt(st.me.score)}` : `👥 ${st.players}`}</span></div>
    <div class="qz-prog">${Array.from({length: st.total}, (_, k) => `<i class="${k < st.qi ? "d" : k === st.qi ? "c" : ""}"></i>`).join("")}</div>
    ${st.phase === "q" ? `<div class="qz-waitn" id="qzwait"${startIn > 0 ? "" : " hidden"}>${Math.max(1, Math.ceil(startIn / 1000))}</div>${timerRing()}` : ""}
    <p class="qz-qt${rv ? " small" : ""}">${esc(q.t)}</p>
    <div class="qz-ans${startIn > 0 && st.phase === "q" ? " hold" : ""}" id="qzopts">${q.o.map(([orig, t], k) => {
      let cls = "";
      if (rv) cls = orig === rv.c ? " right" : orig === picked ? " wrong" : " dim";
      else if (picked != null) cls = orig === picked ? " picked" : " dim";
      const cnt = rv ? `<em>${rv.counts[orig] || 0}</em>` : "";
      return `<button class="an ${SH[k % 4][0]}${cls}" data-ra="${orig}"${canAnswer && picked == null ? "" : " disabled"}>${shape(k)}<span>${esc(t)}</span>${cnt}</button>`;
    }).join("")}</div>
    ${st.phase === "q" ? `<div class="qz-who"><span>✋ ${st.answered} / ${st.players} javob berdi</span>${picked != null ? "<span>✓ Javobingiz qabul qilindi</span>" : ""}</div>` : ""}
    ${rv && total ? "" : ""}${res}
    ${st.host ? `<div class="qz-foot">${st.phase === "q" ? `<button class="qz-go sec" data-host="skip">⏭ Natijani hozir ochish</button>`
      : `<button class="qz-go" data-host="${st.last ? "next" : "next"}">${st.last ? "🏁 Yakuniy natija" : "Keyingi savol →"}</button>`}</div>` : ""}`;
}
function viewEnd(v, st) {
  const p = st.podium || [];
  const slot = (i, cls) => p[i] ? `<div class="pd ${cls}">${i === 0 ? '<span class="crown">👑</span>' : ""}<span class="av" style="background:${p[i].col}">${p[i].av}</span><b>${esc(p[i].n)}</b><small>${fmt(p[i].s)}</small><div class="bl">${i + 1}</div></div>` : `<div class="pd ${cls} empty"></div>`;
  return backBar(esc(st.title)) + `<div class="qz-conf" aria-hidden="true">${RM ? "" : Array.from({length: 40}, (_, i) => `<i style="left:${(i * 37) % 100}%;animation-delay:${(i % 10) * 0.15}s;background:${["#8F7CFF", "#E0465A", "#F0A92E", "#12A99A", "#2F6BFF"][i % 5]}"></i>`).join("")}</div>
    <h2 class="qz-endh">O'yin tugadi!</h2><p class="qz-cap">${st.players} ishtirokchi · ${st.total} savol</p>
    <div class="qz-podium">${slot(1, "p2")}${slot(0, "p1")}${slot(2, "p3")}</div>
    ${st.me ? `<div class="qz-stats"><div><b>${st.me.rank}</b><small>o'rningiz</small></div><div><b>${st.me.ok}/${st.total}</b><small>to'g'ri</small></div><div><b>${fmt(st.me.score)}</b><small>ball</small></div></div>` : ""}
    ${p.length > 3 ? `<div class="qz-board">${p.slice(3).map((x, i) => `<div class="lr"><span class="n">${i + 4}</span><span class="av" style="background:${x.col}">${x.av}</span><b>${esc(x.n)}</b><span class="s">${fmt(x.s)}</span></div>`).join("")}</div>` : ""}
    <div class="qz-row"><button class="qz-next" data-act="tohome">🏠 Bosh sahifa</button>${st.host ? `<button class="qz-sec" data-act="setup">🔄 Yangi xona</button>` : ""}</div>`;
}
async function roomAnswer(orig) {
  const v = top();
  if (v.picked != null || !v.st || v.st.phase !== "q") return;
  v.picked = orig; haptic("hit"); render();
  const r = await api(`api/quiz/room/${v.pin}/answer`, {qi: v.st.qi, o: orig});
  if (!r.ok) { toast(r.error); }
  pollRoom();
}
async function hostAct(act) {
  const v = top();
  const r = await api(`api/quiz/room/${v.pin}/host`, {act});
  if (!r.ok) toast(r.error); else haptic("hit");
  pollRoom();
}

// ------------------------------------------------------------------ 🏆 haftalik reyting
function viewWeekly(v) {
  const w = v.data;
  return backBar("Haftalik reyting") + `<p class="qz-cap">Yakka o'yin ballari · har dushanba yangilanadi</p>
    ${!w ? `<div class="qz-load"><i></i><i></i><i></i></div>` : !w.rows.length ? `<p class="qz-empty">Bu hafta hali hech kim o'ynamadi — birinchi bo'ling!</p>`
      : `<div class="qz-board">${w.rows.map((p, i) => `<div class="lr${p.me ? " me" : ""}"><span class="n">${i < 3 ? ["🥇", "🥈", "🥉"][i] : i + 1}</span><span class="av" style="background:${p.col}">${p.av}</span><b>${esc(p.n)}</b><span class="s">${fmt(p.s)}</span></div>`).join("")}</div>
      ${w.me && w.me.rank > w.rows.length ? `<p class="qz-cap">Siz: ${w.me.rank}-o'rin · ${fmt(w.me.s)} ball</p>` : ""}`}
    <div class="qz-foot"><button class="qz-go" data-act="solopick">🎯 O'ynash</button></div>`;
}

// ------------------------------------------------------------------ 📋 viktorina sahifasi
function viewQuiz(v) {
  const z = v.z;
  if (!z) return backBar("Viktorina") + `<div class="qz-load"><i></i><i></i><i></i></div>`;
  const own = me && (z.own === me.uid || me.admin) && z.qs;
  return backBar(esc(z.t)) + `<div class="qz-qhead"><span class="ic">${z.ic}</span><div><b>${esc(z.t)}</b><small>${z.n} savol · ${z.src === "seed" ? "Bauntys" : esc(z.a)}${z.pl ? ` · ${fmt(z.pl)} marta o'ynalgan` : ""}</small></div></div>
    <div class="qz-acts"><button class="qz-go" data-act="qroom">👥 Xona ochish</button><button class="qz-next" data-act="qsolo">🎯 O'zim o'ynayman</button></div>
    ${own ? `<div class="qz-acts"><button class="qz-sec" data-act="qedit">✏️ Tahrirlash</button><button class="qz-sec" data-act="qshare">📤 Ulashish</button><button class="qz-sec danger" data-act="qdel">🗑</button></div>
      <p class="qz-lbl">Savollar</p><ol class="qz-qlist">${z.qs.map((q) => `<li><b>${esc(q.t)}</b><span>${q.o.map((o, i) => `<em class="${i === q.c ? "c" : ""}">${esc(o)}</em>`).join("")}</span></li>`).join("")}</ol>` : ""}`;
}

// ------------------------------------------------------------------ ✏️ muharrir
const blankQ = () => ({t: "", o: ["", "", "", ""], c: 0, s: 20});
function viewEdit(v) {
  const f = v.f;
  return backBar(f.id ? "Viktorinani tahrirlash" : "Yangi viktorina") + `<form class="qz-form" data-form="edit" autocomplete="off" onsubmit="return false">
    <label class="ff">Nomi<input data-f="t" value="${esc(f.t)}" maxlength="120" placeholder="Masalan: 7-sinf, Tarix — 3-mavzu"></label>
    <div class="ff">Mavzu<div class="qz-pills wrap">${(home ? home.topics : []).map((t) => `<button type="button" data-ftp="${t.k}" class="${f.tp === t.k ? "on" : ""}">${t.ic} ${esc(t.n)}</button>`).join("")}</div></div>
    <button type="button" class="qz-toggle${f.vis === "public" ? " on" : ""}" data-act="vis" role="switch" aria-checked="${f.vis === "public"}"><span><b>Hammaga ochiq</b><small>${f.vis === "public" ? "Ommabop ro'yxatda ko'rinadi, savollar umumiy bazaga qo'shiladi" : "Faqat siz ochgan xonada o'ynaladi"}</small></span><i></i></button>
    <div class="qz-lh"><span>Savollar · ${f.qs.length}</span><button type="button" data-act="bulk">📋 Matndan qo'shish</button></div>
    ${f.qs.map((q, i) => `<div class="qz-qe" data-qi="${i}"><div class="qh"><b>${i + 1}</b><select data-qs="${i}" aria-label="Vaqt">${[10, 20, 30, 60].map((s) => `<option value="${s}"${q.s === s ? " selected" : ""}>${s} s</option>`).join("")}</select><button type="button" data-qdel="${i}" aria-label="Savolni o'chirish">🗑</button></div>
      <textarea data-qt="${i}" rows="2" maxlength="300" placeholder="Savol matni">${esc(q.t)}</textarea>
      ${q.o.map((o, k) => `<div class="op ${SH[k][0]}"><button type="button" class="ok${q.c === k ? " on" : ""}" data-qc="${i}:${k}" aria-label="To'g'ri javob">${q.c === k ? "✓" : ""}</button><input data-qo="${i}:${k}" value="${esc(o)}" maxlength="120" placeholder="${k < 2 ? "Variant" : "Variant (ixtiyoriy)"} ${k + 1}"></div>`).join("")}</div>`).join("")}
    <button type="button" class="qz-add" data-act="addq">＋ Savol qo'shish</button>
    ${v.err ? `<p class="err" role="alert">${esc(v.err)}</p>` : ""}
    <div class="qz-foot"><button type="button" class="qz-go" data-act="save"${v.busy ? " disabled" : ""}>${v.busy ? "Saqlanmoqda…" : "✓ Saqlash"}</button></div></form>`;
}
function readEdit() {
  const v = top(); if (v.v !== "edit") return;
  const f = v.f, root = $("qzview");
  const t = root.querySelector("[data-f=t]"); if (t) f.t = t.value;
  root.querySelectorAll("[data-qt]").forEach((el) => { f.qs[+el.dataset.qt].t = el.value; });
  root.querySelectorAll("[data-qo]").forEach((el) => { const [i, k] = el.dataset.qo.split(":").map(Number); f.qs[i].o[k] = el.value; });
  root.querySelectorAll("[data-qs]").forEach((el) => { f.qs[+el.dataset.qs].s = +el.value; });
}
async function saveEdit() {
  const v = top(); readEdit();
  const qs = v.f.qs.map((q) => {
    const opts = q.o.map((o, k) => [o.trim(), k]).filter(([o]) => o);
    const c = opts.findIndex(([, k]) => k === q.c);
    return {t: q.t, o: opts.map(([o]) => o), c: Math.max(0, c), s: q.s};
  }).filter((q) => q.t.trim() && q.o.length >= 2);
  v.busy = true; v.err = ""; render();
  const r = await api("api/quiz/save", Object.assign({}, v.f, {qs}));
  v.busy = false;
  if (!r.ok) { v.err = r.error; haptic("err"); render(); return; }
  haptic("ok"); toast("✓ Saqlandi");
  await loadMe();
  stack.pop();
  openQuiz(r.quiz.id, true);
}
function bulkSheet() {
  const el = document.createElement("div");
  el.className = "qz-sheet";
  el.innerHTML = `<div class="ps" role="dialog" aria-modal="true" aria-label="Matndan qo'shish"><b>📋 Matndan qo'shish</b>
    <p>Savollarni nusxalab qo'ying. Har savol bo'sh qator bilan ajraladi, to'g'ri javob oldiga <b>*</b> qo'ying:</p>
    <pre>1. O'zbekiston poytaxti?\na) Samarqand\n*b) Toshkent\nc) Buxoro</pre>
    <textarea id="qzbulk" rows="9" placeholder="Shu yerga qo'ying…"></textarea>
    <div class="qz-row"><button class="qz-sec" data-x="1">Bekor</button><button class="qz-next" data-ok="1">Qo'shish</button></div></div>`;
  $("quiz").appendChild(el);
  el.addEventListener("click", async (e) => {
    if (e.target === el || e.target.closest("[data-x]")) { el.remove(); return; }
    if (!e.target.closest("[data-ok]")) return;
    const r = await api("api/quiz/parse", {text: $("qzbulk").value});
    if (!r.ok || !r.qs.length) { toast("Savol topilmadi — namunadagidek yozing"); haptic("err"); return; }
    const v = top(); readEdit();
    v.f.qs = v.f.qs.filter((q) => q.t.trim()).concat(r.qs.map((q) => ({t: q.t, o: q.o.concat(["", "", ""]).slice(0, 4), c: q.c, s: q.s})));
    el.remove(); haptic("ok"); toast(`✓ ${r.qs.length} ta savol qo'shildi`); render();
  });
}

// ------------------------------------------------------------------ chizish va boshqaruv
function render() {
  const v = top(), el = $("qzview");
  if (!el) return;
  const views = {home: viewHome, solopick: viewSoloPick, solo: viewSolo, setup: viewSetup, join: viewJoin, room: viewRoom,
    weekly: viewWeekly, quiz: viewQuiz, edit: viewEdit};
  el.innerHTML = (views[v.v] || viewHome)(v);
  $("quiz").dataset.v = v.v;
  updateBack();
}
function go(v) { stack.push(v); haptic(); render(); $("qzscroll").scrollTop = 0; }
function back() {
  const v = top();
  if (stack.length <= 1) return;
  if ((v.v === "solo" && !v.final && v.i > 0) || (v.v === "room" && v.st && ["q", "r"].includes(v.st.phase))) {
    if (!confirm("O'yindan chiqasizmi?")) return;
  }
  stopLoops(); stack.pop(); render();
  if (top().v === "home") refresh();
}
function updateBack() {
  if (!tg || !tg.BackButton) return;
  try {
    if (opened && stack.length > 1) tg.BackButton.show();
    else if (opened && (!window.ZK_canHideBack || window.ZK_canHideBack())) tg.BackButton.hide();
  } catch (e) {}
}
async function loadMe() {
  if (!inTg) return;
  const r = await api("api/quiz/me");
  if (r.ok) me = r;
  try { me.uid = tg.initDataUnsafe.user.id; } catch (e) {}
}
async function refresh() {
  const [h, d] = await Promise.all([api("api/quiz/home"), api("api/quiz/daily"), loadMe()]);
  if (h.ok) home = h;
  if (d && d.ok) daily = d.d;
  if (opened && top().v === "home") render();
}
async function openQuiz(id, replace) {
  const v = {v: "quiz", id, z: null};
  if (replace && top().v === "quiz") stack.pop();
  go(v);
  const r = await api(`api/quiz/q/${id}`);
  if (top() !== v) return;
  if (!r.ok) { toast(r.error); back(); return; }
  v.z = r.quiz; render();
}
function share(text, url) {
  const u = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
  try { tg.openTelegramLink(u); } catch (e) { window.open(u, "_blank"); }
}

function onClick(e) {
  const t = e.target;
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "quiz" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  const g = (sel) => t.closest(sel);
  let b;
  if ((b = g("[data-solo]"))) { soloStart(b.dataset.solo); return; }
  if ((b = g("[data-sa]"))) { soloAnswer(+b.dataset.sa); return; }
  if ((b = g("[data-ra]"))) { roomAnswer(+b.dataset.ra); return; }
  if ((b = g("[data-host]"))) { hostAct(b.dataset.host); return; }
  if ((b = g("[data-daily]"))) { api("api/quiz/daily", {o: +b.dataset.daily}).then((r) => { if (r.ok) { daily = r.d; haptic(r.d.ok ? "ok" : "err"); render(); } else toast(r.error); }); return; }
  if ((b = g("[data-rep]"))) { api("api/quiz/report", {qid: +b.dataset.rep}); b.disabled = true; b.textContent = "✓ Rahmat, tekshiramiz"; return; }
  if ((b = g("[data-quiz]"))) { openQuiz(+b.dataset.quiz); return; }
  if ((b = g("[data-stp]"))) { const v = top(); v.tp = b.dataset.stp; haptic(); render(); return; }
  if ((b = g("[data-sid]"))) { const v = top(); v.id = +b.dataset.sid; v.title = b.dataset.stitle; haptic(); render(); return; }
  if ((b = g("[data-sn]"))) { top().n = +b.dataset.sn; haptic(); render(); return; }
  if ((b = g("[data-ss]"))) { top().s = +b.dataset.ss; haptic(); render(); return; }
  if ((b = g("[data-ftp]"))) { readEdit(); top().f.tp = b.dataset.ftp; haptic(); render(); return; }
  if ((b = g("[data-qc]"))) { readEdit(); const [i, k] = b.dataset.qc.split(":").map(Number); top().f.qs[i].c = k; haptic(); render(); return; }
  if ((b = g("[data-qdel]"))) { readEdit(); const f = top().f; f.qs.splice(+b.dataset.qdel, 1); if (!f.qs.length) f.qs.push(blankQ()); haptic(); render(); return; }
  if (!(b = g("[data-act]"))) return;
  const act = b.dataset.act, v = top();
  if (act === "back") back();
  else if (act === "homeback") {
    if (window.ZK_setMode) window.ZK_setMode("kino");
    else if (window.ZQuiz) window.ZQuiz.close();
  }
  else if (act === "hub") {
    if (window.ZHub) window.ZHub.open("");
  }
  else if (act === "tohome") { stopLoops(); stack.length = 1; render(); refresh(); }
  else if (act === "solopick") go({v: "solopick"});
  else if (act === "setup") { if (!inTg) { toast("Ilovani bot ichida oching"); return; } stopLoops(); go({v: "setup"}); }
  else if (act === "weekly") { const w = {v: "weekly", data: null}; go(w); api("api/quiz/weekly").then((r) => { if (r.ok) { w.data = r; if (top() === w) render(); } }); }
  else if (act === "new") { if (!inTg) { toast("Ilovani bot ichida oching"); return; } go({v: "edit", f: {t: "", tp: "umumiy", vis: "public", qs: [blankQ()]}}); }
  else if (act === "snext") soloNext();
  else if (act === "replay") { stack.pop(); soloStart(v.tp || "mix", v.qid || 0); }
  else if (act === "srcclear") { v.id = 0; v.title = ""; render(); }
  else if (act === "hp") { v.hp = !v.hp; haptic(); render(); }
  else if (act === "create") createRoom();
  else if (act === "share") share(`🧠 «${v.st.title}» viktorinasiga qo'shiling! Xona kodi: ${v.st.pin}`, roomLink(v.st.pin));
  else if (act === "copy") { const l = roomLink(v.st.pin); try { navigator.clipboard.writeText(l).then(() => toast("✓ Havola nusxalandi")); } catch (e) { toast(l); } }
  else if (act === "qroom") go({v: "setup", id: v.z.id, title: v.z.t});
  else if (act === "qsolo") soloStart("", v.z.id);
  else if (act === "qedit") go({v: "edit", f: {id: v.z.id, t: v.z.t, tp: v.z.tp, vis: v.z.vis, qs: v.z.qs.map((q) => ({t: q.t, o: q.o.concat(["", "", ""]).slice(0, 4), c: q.c, s: q.s}))}});
  else if (act === "qshare") share(`🧠 «${v.z.t}» — ${v.z.n} savolli viktorina. O'ynab ko'ring!`, bot ? `https://t.me/${bot}?startapp=qz${v.z.id}` : "");
  else if (act === "qdel") { if (confirm("Viktorina o'chirilsinmi?")) api("api/quiz/delete", {id: v.z.id}).then((r) => { if (r.ok) { toast("O'chirildi"); stack.length = 1; render(); refresh(); } }); }
  else if (act === "vis") { readEdit(); v.f.vis = v.f.vis === "public" ? "link" : "public"; haptic(); render(); }
  else if (act === "addq") { readEdit(); v.f.qs.push(blankQ()); haptic(); render(); setTimeout(() => { const all = document.querySelectorAll("[data-qt]"); if (all.length) all[all.length - 1].focus(); }, 50); }
  else if (act === "bulk") bulkSheet();
  else if (act === "save") saveEdit();
}
function onSubmit(e) {
  const f = e.target.closest("[data-form]");
  if (!f) return;
  e.preventDefault();
  if (f.dataset.form === "pin") {
    const pin = ($("qzpin").value || "").replace(/\D/g, "");
    if (pin.length !== 6) { toast("Kod 6 ta raqamdan iborat"); haptic("err"); return; }
    if (!inTg) { toast("Ilovani bot ichida oching"); return; }
    go({v: "join", pin, name: me ? me.name : ""});
  } else if (f.dataset.form === "join") {
    const n = ($("qzname").value || "").trim();
    if (!n) { $("qzname").focus(); return; }
    joinRoom(top().pin, n);
  }
}

if (tg && tg.BackButton) tg.BackButton.onClick(() => { if (opened && stack.length > 1) back(); });
document.addEventListener("visibilitychange", () => { if (!document.hidden && opened && top().v === "room") pollRoom(); });

window.ZQuiz = {
  open(param) {
    if (!mounted) {
      mounted = true;
      const root = $("quiz");
      root.addEventListener("click", onClick);
      root.addEventListener("submit", onSubmit);
    }
    opened = true;
    $("quiz").hidden = false; document.body.classList.add("qz-on");
    render();
    refresh();
    if (top().v === "room") pollRoom();
  },
  start(param) {
    const raw = String(param || "").trim();
    const p = raw.replace(/^(?:quiz_|qz_|q_)/i, "");
    const go2 = () => {
      if (/^\d{6}$/.test(p)) { stack.length = 1; go({v: "join", pin: p, name: me ? me.name : ""}); }
      else if (/^z\d+$/i.test(p)) { stack.length = 1; openQuiz(+p.slice(1)); }
      else if (p === "new") { stack.length = 1; go({v: "edit", f: {t: "", tp: "umumiy", vis: "public", qs: [blankQ()]}}); }
    };
    loadMe().then(go2);
  },
  close() {
    opened = false; stopLoops();
    $("quiz").hidden = true; document.body.classList.remove("qz-on");
    updateBack();
  },
  setBot(b) { bot = b || ""; },
  busy() { return opened && stack.length > 1; },
};
})();
