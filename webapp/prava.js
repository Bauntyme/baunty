/* 🚗 Prava — haydovchilik guvohnomasi nazariy imtihoniga tayyorlanish (1235 savol, 125 bilet, 12 mavzu).
   index.html dan window.ZPrava orqali boshqariladi (open / close / busy / start).
   To'g'ri javob serverda tekshiriladi (/api/prava/ans) — mijozga oldindan yuborilmaydi. */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const ICO = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
  no: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M7 7l10 10M17 7 7 17"/></svg>',
  zoom: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/></svg>',
};

let opened = false, mounted = false, home = null, loading = false, tick = null, busyAns = false;
const stack = [{v: "home"}];
const top = () => stack[stack.length - 1];

async function api(path, body) {
  try {
    const r = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body ? {"Content-Type": "application/json"} : {}),
      body: body ? JSON.stringify(body) : undefined});
    if (r.status === 401) return {ok: false, error: "Ilovani bot ichida oching"};
    if (r.status === 429) return {ok: false, error: "Juda ko'p so'rov — biroz kuting", net: true};
    if (r.status >= 500) return {ok: false, error: "Server band — biroz kuting", net: true};
    return await r.json();
  } catch (e) { return {ok: false, error: "Internet aloqasini tekshiring", net: true}; }
}
const toast = (t) => { const el = document.createElement("div"); el.className = "pv-toast"; el.textContent = t; $("prava").appendChild(el); setTimeout(() => el.remove(), 2400); };
const fmt = (n) => String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
const mmss = (s) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, "0")}`;
function segHtml() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["prava", "Prava"]];
  return `<div class="pv-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "prava" ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`;
}
function head(title, sub = "", right = "") {
  return `<div class="pv-head"><button class="pv-back" data-act="back" aria-label="Orqaga">${ICO.back}</button><div class="tt"><b>${title}</b>${sub ? `<small>${sub}</small>` : ""}</div>${right}</div>`;
}
const stopTick = () => { clearInterval(tick); tick = null; };

// ------------------------------------------------------------------ 🏠 bosh sahifa
function ring(pct) {
  const r = 34, c = 2 * Math.PI * r;
  return `<svg class="pv-rg" viewBox="0 0 84 84" aria-hidden="true"><circle cx="42" cy="42" r="${r}" class="bg"/><circle cx="42" cy="42" r="${r}" class="fg" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - pct / 100)}"/></svg>`;
}
function viewHome() {
  const h = home;
  if (!h) return `<div class="pv-bar">${segHtml()}</div><div class="pv-load"><i></i><i></i><i></i></div>`;
  const pct = h.total ? Math.round(h.solved / h.total * 100) : 0;
  return `<div class="pv-bar">${segHtml()}</div>
  <h1 class="pv-hi">Prava imtihoni<span>Yoʻl harakati qoidalari · ${fmt(h.total)} savol · ${h.bilets.length} bilet</span></h1>
  <div class="pv-stat">
    <div class="pv-ring">${ring(pct)}<div><b>${pct}%</b><small>oʻrganildi</small></div></div>
    <div class="nums"><div><b>${fmt(h.solved)} <i>/ ${fmt(h.total)}</i></b><small>toʻgʻri yechilgan</small></div>
      <div><b>${h.streak ? `🔥 ${h.streak} kun` : "—"}</b><small>ketma-ket</small></div>
      <div><b>${h.exams ? `${h.passed} / ${h.exams}` : "—"}</b><small>imtihondan oʻtgan</small></div></div>
    <div class="ready"><span>Imtihonga tayyorlik</span><i><em style="width:${h.ready}%"></em></i><b>${h.ready}%</b></div>
  </div>
  <button class="pv-cta" data-act="exam"><span class="ic">⏱</span><span class="tx"><b>Imtihon topshirish</b><small>${h.exam.n} savol · ${h.exam.min} daqiqa · ${h.exam.err} tagacha xato</small></span><span class="ar">›</span></button>
  <div class="pv-tiles">
    <button class="tile" data-act="bilets"><i>🎫</i><b>Biletlar</b><small>${h.bilets.length} ta · ${h.bilets.filter((b) => b.s != null).length} tasi yechilgan</small></button>
    <button class="tile" data-act="topics"><i>📚</i><b>Mavzular</b><small>Belgilar, chorraha, tezlik…</small></button>
    <button class="tile${h.bad ? " warn" : ""}" data-act="bad"><i>❌</i><b>Xatolarim</b><small>${h.bad ? `${h.bad} ta savol — qayta ishlang` : "Hozircha xato yoʻq"}</small>${h.bad ? `<em>${h.bad}</em>` : ""}</button>
    <button class="tile" data-act="img"><i>🖼</i><b>Rasmli savollar</b><small>${fmt(h.img)} ta · tasodifiy 20</small></button>
  </div>
  <button class="pv-rnd" data-act="rnd">🎲 Tasodifiy 20 savol bilan mashq</button>`;
}

// ------------------------------------------------------------------ 🎫 biletlar / 📚 mavzular
function viewBilets(v) {
  const f = v.f || "all";
  const list = home.bilets.filter((b) => f === "all" || (f === "done" && b.s != null && b.s >= b.c - 1) || (f === "bad" && b.s != null && b.s < b.c - 1) || (f === "new" && b.s == null));
  const chip = (k, t) => `<button class="${f === k ? "on" : ""}" data-filter="${k}">${t}</button>`;
  return head("Biletlar", `${home.bilets.length} bilet · har birida 10 savol`) +
    `<div class="pv-chips">${chip("all", "Hammasi")}${chip("done", "Yechilgan")}${chip("bad", "Xatoli")}${chip("new", "Yechilmagan")}</div>
    <div class="pv-grid">${list.map((b) => {
      const cls = b.s == null ? "" : b.s >= b.c - 1 ? "ok" : b.s >= Math.ceil(b.c * .6) ? "mid" : "no";
      return `<button class="bl ${cls}" data-bilet="${b.b}"><b>${b.b}</b><small>${b.s == null ? "—" : `${b.s}/${b.c}`}</small></button>`;
    }).join("") || `<div class="pv-empty">Bu boʻlimda bilet yoʻq</div>`}</div>
    <div class="pv-legend"><span><i class="ok"></i>Oʻtdi</span><span><i class="mid"></i>Yaxshi</span><span><i class="no"></i>Yiqildi</span></div>`;
}
function viewTopics() {
  return head("Mavzular", "Har safar mavzudan tasodifiy 20 savol") +
    `<div class="pv-topics">${home.topics.map((t) => `<button class="tp" data-topic="${t.i}"><i>${t.ic}</i><span><b>${esc(t.n)}</b><small>${t.c} savol</small></span><em>›</em></button>`).join("")}</div>`;
}

// ------------------------------------------------------------------ ✍️ mashq (bilet / mavzu / xatolar / rasmli)
async function startSet(kind, arg, title) {
  if (loading) return;
  loading = true;
  const r = await api(`api/prava/set?k=${kind}&a=${arg || 0}`);
  loading = false;
  if (!r.ok) { toast(r.error === "not_found" ? "Topilmadi" : r.error); haptic("err"); return; }
  if (!r.qs.length) { toast(kind === "bad" ? "Xatolar yoʻq — barakalla! 🎉" : "Savol topilmadi"); return; }
  stopTick();
  go({v: "q", kind, arg, title, qs: r.qs, i: 0, ans: {}, score: 0});
}
function progressDashes(v) {
  return `<div class="pv-dash">${v.qs.map((q, k) => {
    const a = v.ans[k];
    return `<i class="${a ? (a.ok ? "ok" : "no") : k === v.i ? "cur" : ""}"></i>`;
  }).join("")}</div>`;
}
function qImage(q) {
  return q.img ? `<button class="pv-img" data-zoom="${esc(q.img)}"><img src="${esc(q.img)}" alt="Savol rasmi" loading="eager" decoding="async" onerror="this.parentElement.style.display='none'"><span>${ICO.zoom}</span></button>` : "";
}
function optionsHtml(q, a, attr) {
  return `<div class="pv-opts">${q.o.map((t, k) => {
    let cls = "", mark = "";
    if (a) {
      if (k === a.a) { cls = "ok"; mark = ICO.ok; }
      else if (k === a.c) { cls = "no"; mark = ICO.no; }
      else cls = "dim";
    }
    return `<button class="op ${cls}" ${attr}="${k}"${a ? " disabled" : ""}><i>F${k + 1}</i><span>${esc(t)}</span>${mark ? `<em>${mark}</em>` : ""}</button>`;
  }).join("")}</div>`;
}
function viewQ(v) {
  if (v.done) return viewQDone(v);
  const q = v.qs[v.i], a = v.ans[v.i];
  return head(esc(v.title), `${v.i + 1}-savol / ${v.qs.length}`) + progressDashes(v) + qImage(q) +
    `<p class="pv-q">${esc(q.q)}</p>` + optionsHtml(q, a, "data-opt") +
    (a ? `<div class="pv-next"><button class="pv-btn" data-act="next">${v.i + 1 < v.qs.length ? "Keyingi savol ›" : "Natijani koʻrish"}</button></div>` : "");
}
function viewQDone(v) {
  const n = v.qs.length, ok = v.score, pct = Math.round(ok / n * 100);
  const wrong = v.qs.map((q, k) => [q, v.ans[k], k]).filter(([, a]) => a && !a.ok);
  return head(esc(v.title), "Natija") +
    `<div class="pv-res ${pct >= 90 ? "pass" : "fail"}"><div class="big"><b>${ok}</b><small>/ ${n}</small></div>
      <h2>${pct >= 90 ? "Aʼlo! 🎉" : pct >= 70 ? "Yaxshi, lekin xatolar bor" : "Yana mashq qiling"}</h2>
      <p>${wrong.length ? `${wrong.length} ta xato «Xatolarim» boʻlimiga qoʻshildi.` : "Birorta ham xato yoʻq."}</p></div>
    ${wrong.length ? `<div class="pv-lh">Xatolar</div><div class="pv-wrong">${wrong.map(([q, a, k]) => `<button data-review="${k}"><i>${k + 1}</i><span>${esc(q.q)}</span><em>›</em></button>`).join("")}</div>` : ""}
    <div class="pv-two"><button class="pv-btn ghost" data-act="home">Bosh sahifa</button><button class="pv-btn" data-act="again">Qayta yechish</button></div>`;
}
async function answerQ(k) {
  const v = top();
  if (busyAns || v.v !== "q" || v.ans[v.i]) return;
  busyAns = true;
  const q = v.qs[v.i];
  const r = await api("api/prava/ans", {id: q.id, c: k});
  busyAns = false;
  if (!r.ok) { toast(r.error || "Xatolik"); return; }
  v.ans[v.i] = {c: k, a: r.a, ok: r.right};
  if (r.right) v.score++;
  haptic(r.right ? "ok" : "err");
  if (top() === v) render();
}
function nextQ() {
  const v = top();
  if (v.i + 1 < v.qs.length) { v.i++; render(); $("pvscroll").scrollTop = 0; return; }
  v.done = true;
  if (v.kind === "b") api("api/prava/bilet", {b: v.arg, s: v.score});
  render(); $("pvscroll").scrollTop = 0;
  if (home) refresh();
}
function viewReview(v) {
  const q = v.q, a = v.a;
  return head("Xato tahlili", esc(v.sub || "")) + qImage(q) + `<p class="pv-q">${esc(q.q)}</p>` + optionsHtml(q, a, "data-none") +
    `<div class="pv-note">✅ Toʻgʻri javob: <b>${esc(q.o[a.a])}</b></div>`;
}

// ------------------------------------------------------------------ ⏱ imtihon
async function startExam() {
  if (loading) return;
  if (!inTg) { toast("Ilovani bot ichida oching"); return; }
  loading = true;
  const r = await api("api/prava/exam/start", {});
  loading = false;
  if (!r.ok) { toast(r.error); haptic("err"); return; }
  stopTick();
  const skew = Date.now();
  go({v: "exam", qs: r.qs, i: 0, ans: {}, err: 0, ends: r.ends, maxErr: r.max_err, res: null, t0: skew});
  tick = setInterval(() => {
    const v = top();
    if (v.v !== "exam" || v.res) { stopTick(); return; }
    const left = (v.ends - Date.now()) / 1000;
    const el = $("pvtimer");
    if (el) { el.textContent = mmss(left); el.classList.toggle("low", left < 120); }
    if (left <= 0) { stopTick(); finishExam(); }
  }, 1000);
}
function viewExam(v) {
  if (v.res) return viewExamRes(v);
  const q = v.qs[v.i], a = v.ans[v.i];
  const left = (v.ends - Date.now()) / 1000;
  const dots = Array.from({length: v.maxErr + 1}, (_, k) => `<i class="${k < v.err ? "on" : ""}"></i>`).join("");
  return `<div class="pv-ehead"><button class="pv-back" data-act="quit" aria-label="Imtihondan chiqish">${ICO.close}</button>
      <b class="tm" id="pvtimer">${mmss(left)}</b><span class="er">Xato <em>${dots}</em></span></div>
    ${progressDashes(v)}${qImage(q)}<p class="pv-q"><span class="qn">${v.i + 1}/${v.qs.length}</span>${esc(q.q)}</p>${optionsHtml(q, a, "data-eopt")}
    ${a ? `<div class="pv-next"><button class="pv-btn" data-act="enext">${nextUnanswered(v) >= 0 ? "Keyingi savol ›" : "Yakunlash"}</button></div>` : ""}
    <div class="pv-nums">${v.qs.map((_, k) => { const x = v.ans[k]; return `<button class="${k === v.i ? "cur " : ""}${x ? (x.ok ? "ok" : "no") : ""}" data-goto="${k}">${k + 1}</button>`; }).join("")}</div>`;
}
function nextUnanswered(v) {
  for (let s = 1; s <= v.qs.length; s++) { const k = (v.i + s) % v.qs.length; if (!v.ans[k]) return k; }
  return -1;
}
async function answerExam(k) {
  const v = top();
  if (busyAns || v.v !== "exam" || v.res || v.ans[v.i]) return;
  busyAns = true;
  const idx = v.i;
  const r = await api("api/prava/exam/ans", {k: idx, c: k});
  busyAns = false;
  if (!r.ok) { toast(r.error === "no_exam" ? "Imtihon vaqti tugagan" : r.error); if (r.error === "no_exam") finishExam(); return; }
  v.ans[idx] = {c: k, a: r.a, ok: r.right};
  v.err = r.err;
  haptic(r.right ? "ok" : "err");
  if (r.result) { stopTick(); v.res = r.result; }
  if (top() === v) { render(); if (v.res) $("pvscroll").scrollTop = 0; }
  if (v.res && home) refresh();
}
async function finishExam() {
  const v = top();
  if (v.v !== "exam" || v.res) return;
  const r = await api("api/prava/exam/finish", {});
  stopTick();
  v.res = r.ok ? r : {finished: true, passed: false, reason: "quit", correct: Object.values(v.ans).filter((x) => x.ok).length, err: v.err, n: v.qs.length, sec: 0, wrong: []};
  if (top() === v) { render(); $("pvscroll").scrollTop = 0; }
  if (home) refresh();
}
function viewExamRes(v) {
  const r = v.res;
  const why = r.passed ? "Haqiqiy imtihonda ham shunday boʻlsa — guvohnoma sizniki." :
    r.reason === "errors" ? `${v.maxErr} tadan ortiq xato — imtihon toʻxtatildi.` :
    r.reason === "time" ? "Vaqt tugadi." : r.reason === "quit" ? "Imtihon yakunlanmadi." : `Xatolar ${v.maxErr} tadan oshmasligi kerak.`;
  const byId = Object.fromEntries(v.qs.map((q, k) => [q.id, [q, k]]));
  return `<div class="pv-res exam ${r.passed ? "pass" : "fail"}"><div class="big"><b>${r.correct}</b><small>/ ${r.n}</small></div>
      <h2>${r.passed ? "Oʻtdingiz! 🎉" : "Yiqildingiz"}</h2><p>${why}</p></div>
    <div class="pv-kpi"><div><b>${r.correct}</b><small>toʻgʻri</small></div><div><b>${r.err}</b><small>xato</small></div><div><b>${mmss(r.sec)}</b><small>vaqt</small></div></div>
    ${r.wrong && r.wrong.length ? `<div class="pv-lh">Xatolar tahlili</div><div class="pv-wrong">${r.wrong.map((w) => {
      const x = byId[w.id]; if (!x) return "";
      return `<button data-ereview="${x[1]}"><i>${x[1] + 1}</i><span>${esc(x[0].q)}</span><em>›</em></button>`; }).join("")}</div>` : ""}
    <div class="pv-two"><button class="pv-btn ghost" data-act="home">Bosh sahifa</button><button class="pv-btn" data-act="exam">Yana imtihon</button></div>`;
}

// ------------------------------------------------------------------ 🔍 rasmni kattalashtirish
function zoom(src) {
  const el = document.createElement("div");
  el.className = "pv-zoom";
  el.innerHTML = `<img src="${esc(src)}" alt=""><button aria-label="Yopish">${ICO.close}</button>`;
  el.addEventListener("click", () => el.remove());
  $("prava").appendChild(el);
  haptic();
}

// ------------------------------------------------------------------ navigatsiya
function render() {
  const v = top(), el = $("pvview");
  if (!el) return;
  const views = {home: viewHome, bilets: viewBilets, topics: viewTopics, q: viewQ, review: viewReview, exam: viewExam};
  el.innerHTML = (views[v.v] || viewHome)(v);
  $("prava").dataset.v = v.v;
  updateBack();
}
function go(v) { stack.push(v); haptic(); render(); $("pvscroll").scrollTop = 0; }
function back() {
  const v = top();
  if (stack.length <= 1) return;
  if (v.v === "exam" && !v.res && Object.keys(v.ans).length) {
    if (!confirm("Imtihonni yakunlaysizmi? Javob berilmagan savollar xato hisoblanmaydi, lekin imtihon oʻtmaydi.")) return;
    finishExam(); return;
  }
  if (v.v === "q" && !v.done && Object.keys(v.ans).length && !confirm("Mashqdan chiqasizmi?")) return;
  if (v.v === "exam") stopTick();
  stack.pop(); render();
  if (top().v === "home") refresh();
}
function updateBack() {
  if (!tg || !tg.BackButton) return;
  try {
    if (opened && stack.length > 1) tg.BackButton.show();
    else if (opened && (!window.ZK_canHideBack || window.ZK_canHideBack())) tg.BackButton.hide();
  } catch (e) {}
}
async function refresh() {
  const r = await api("api/prava/home");
  if (r.ok) { home = r; if (opened && top().v === "home") render(); }
  else if (!home && opened && top().v === "home") $("pvview").innerHTML = `<div class="pv-bar">${segHtml()}</div><div class="pv-empty">${esc(r.error || "Yuklab boʻlmadi")}<br><br><button class="pv-btn" data-act="reload">Qayta urinish</button></div>`;
}

function onClick(e) {
  const t = e.target;
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "prava" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  const z = t.closest("[data-zoom]"); if (z) { zoom(z.dataset.zoom); return; }
  const o = t.closest("[data-opt]"); if (o) { answerQ(+o.dataset.opt); return; }
  const eo = t.closest("[data-eopt]"); if (eo) { answerExam(+eo.dataset.eopt); return; }
  const gt = t.closest("[data-goto]"); if (gt) { const v = top(); v.i = +gt.dataset.goto; haptic(); render(); return; }
  const bl = t.closest("[data-bilet]"); if (bl) { startSet("b", +bl.dataset.bilet, `Bilet ${bl.dataset.bilet}`); return; }
  const tp = t.closest("[data-topic]"); if (tp) { const x = home.topics[+tp.dataset.topic]; startSet("t", x.i, x.n); return; }
  const fl = t.closest("[data-filter]"); if (fl) { top().f = fl.dataset.filter; haptic(); render(); return; }
  const rv = t.closest("[data-review]"); if (rv) { const v = top(), k = +rv.dataset.review; go({v: "review", q: v.qs[k], a: v.ans[k], sub: `${k + 1}-savol`}); return; }
  const er = t.closest("[data-ereview]"); if (er) { const v = top(), k = +er.dataset.ereview; go({v: "review", q: v.qs[k], a: v.ans[k], sub: `${k + 1}-savol`}); return; }
  const b = t.closest("[data-act]");
  if (!b) return;
  const act = b.dataset.act, v = top();
  if (act === "back") back();
  else if (act === "quit") back();
  else if (act === "home") { stopTick(); stack.length = 1; render(); refresh(); }
  else if (act === "reload") { render(); refresh(); }
  else if (act === "exam") { if (v.v === "exam") stack.pop(); startExam(); }
  else if (act === "bilets") go({v: "bilets", f: "all"});
  else if (act === "topics") go({v: "topics"});
  else if (act === "bad") startSet("bad", 0, "Xatolarim");
  else if (act === "img") startSet("img", 0, "Rasmli savollar");
  else if (act === "rnd") startSet("rnd", 0, "Tasodifiy 20");
  else if (act === "next") nextQ();
  else if (act === "again") { stack.pop(); startSet(v.kind, v.arg, v.title); }
  else if (act === "enext") { const k = nextUnanswered(v); if (k >= 0) { v.i = k; render(); $("pvscroll").scrollTop = 0; } else finishExam(); }
}

if (tg && tg.BackButton) tg.BackButton.onClick(() => { if (opened && stack.length > 1) back(); });

window.ZPrava = {
  open() {
    if (!mounted) { mounted = true; $("prava").addEventListener("click", onClick); }
    opened = true;
    $("prava").hidden = false; document.body.classList.add("pv-on");
    render();
    refresh();
  },
  start(param) {
    const p = String(param || "");
    if (p === "exam") startExam();
  },
  close() {
    opened = false;
    $("prava").hidden = true; document.body.classList.remove("pv-on");
    updateBack();
  },
  busy() { return opened && stack.length > 1; },
};
})();
