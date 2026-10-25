/* 💱 Kurs — Mini App bo'limi: Markaziy bank kursi, banklar, kalkulyator, grafik, «kurs o'zgarsa xabar ber».
   index.html dan window.ZFx orqali boshqariladi (open / close / busy). */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const lsGet = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
const BANK_CODES = ["USD", "EUR", "RUB", "GBP", "KZT", "CHF", "JPY", "CNY"];
const MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];
const DAYS = ["Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"];
const SYM = {USD: "$", EUR: "€", RUB: "₽", GBP: "£", KZT: "₸", CNY: "¥", JPY: "¥", TRY: "₺", KRW: "₩", UZS: "so'm"};
const ICO = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>',
  swap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 4v16M4 16l4 4 4-4M16 20V4M20 8l-4-4-4 4"/></svg>',
  calc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/></svg>',
  bank: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10 12 4l9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/></svg>',
  del: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
};

let data = null, loading = null, opened = false, mounted = false, flapDone = false, showAll = false;
let alertsCache = null;
const stack = [{v: "home"}];
const top = () => stack[stack.length - 1];

// ------------------------------------------------------------------ formatlash
function fmt(v, dec) {
  if (v == null || !isFinite(v)) return "—";
  const d = dec ?? (Math.abs(v) >= 1000 ? (v % 1 ? 2 : 0) : Math.abs(v) >= 10 ? 2 : 2);
  let [i, f] = Math.abs(v).toFixed(d).split(".");
  i = i.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  if (f && /^0+$/.test(f) && dec == null) f = "";
  return (v < 0 ? "−" : "") + i + (f ? "," + f : "");
}
const flag = (c) => c === "EUR" ? "🇪🇺" : c === "UZS" ? "🇺🇿" : /^[A-Z]{3}$/.test(c) && c[0] !== "X"
  ? String.fromCodePoint(...[...c.slice(0, 2)].map((x) => 0x1F1A5 + x.charCodeAt(0))) : "🏳️";
const byCode = (c) => (data && data.items || []).find((x) => x.c === c);
const unit = (c) => { if (c === "UZS") return 1; const x = byCode(c); return x ? x.r / (x.n || 1) : null; };
const nm = (c) => c === "UZS" ? "O'zbek so'mi" : (byCode(c) || {}).nm || c;
function dateLabel(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return `${DAYS[d.getDay()]}, ${d.getDate()}-${MONTHS[d.getMonth()]}`;
}
const shortDate = (iso) => { const d = new Date(iso + "T00:00:00"); return `${d.getDate()}-${MONTHS[d.getMonth()]}`; };

// ------------------------------------------------------------------ tarmoq
async function api(path, body) {
  try {
    const r = await fetch(path, {method: body ? "POST" : "GET", cache: body ? "no-store" : "default",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body ? {"Content-Type": "application/json"} : {}),
      body: body ? JSON.stringify(body) : undefined});
    if (r.status === 401) return {ok: false, error: "auth"};
    return await r.json();
  } catch (e) { return {ok: false, error: "network"}; }
}
function loadHome(force) {
  if (loading && !force) return loading;
  loading = api("api/fx").then((r) => { if (r && r.items) data = r; return data; }).finally(() => { loading = null; });
  return loading;
}
async function loadAlerts() {
  if (!inTg) return [];
  const r = await api("api/fx/alerts");
  alertsCache = r.ok ? r.items : [];
  return alertsCache;
}

// ------------------------------------------------------------------ kichik qismlar
function rootHead() {
  return `<header class="fx-head-clean"><button class="fx-back" data-act="homeback" aria-label="Bosh sahifa">${ICO.back}</button><div class="fx-head-title"><b>Valyuta Kurslari</b><small>Markaziy bank va tijorat banklari</small></div><button class="zk-hubbtn" data-act="hub" type="button" aria-label="Barcha bo'limlar"><span>☰</span> Bo'limlar</button></header>`;
}
function spark(vals, w, h, up) {
  if (!vals || vals.length < 2) return `<svg class="sp" viewBox="0 0 ${w} ${h}" aria-hidden="true"></svg>`;
  const mn = Math.min(...vals), mx = Math.max(...vals), span = mx - mn || 1;
  const d = vals.map((v, i) => `${i ? "L" : "M"}${(i / (vals.length - 1) * w).toFixed(1)},${(3 + (1 - (v - mn) / span) * (h - 6)).toFixed(1)}`).join("");
  return `<svg class="sp ${up ? "u" : "d"}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><path d="${d}"/></svg>`;
}
const chg = (d, cls = "") => {
  if (!d) return `<span class="fx-chg z ${cls}">• 0</span>`;
  return `<span class="fx-chg ${d > 0 ? "u" : "d"} ${cls}">${d > 0 ? "▲" : "▼"} ${fmt(Math.abs(d))}</span>`;
};
function backBar(title, extra = "") {
  return `<div class="fx-top"><button class="fx-back" data-act="back" aria-label="Orqaga">${ICO.back}</button>
    <div class="fx-tt">${extra}<b>${title}</b></div></div>`;
}

// ------------------------------------------------------------------ 🏠 bosh sahifa
function viewHome() {
  if (!data) {
    return `${rootHead()}<div class="fx-load"><i></i><i></i><i></i></div>
      <p class="fx-empty">${loading ? "Kurslar yuklanmoqda…" : "Kurslar hali yuklanmagan. Birozdan keyin qayta oching."}</p>`;
  }
  const usd = byCode("USD") || data.items[0];
  const [ip, fp] = fmt(usd.r, 2).split(",");
  const digits = [...ip].map((ch) => ch === " " ? '<span class="g"></span>' : `<span data-d="${ch}">${ch}</span>`).join("");
  const b = (data.best || {})[usd.c];
  const rest = data.items.filter((x) => x !== usd);
  const list = showAll ? rest : rest.slice(0, 7);
  const prev = usd.r - usd.d;
  return `${rootHead()}
  <div class="fx-date"><span>${esc(dateLabel(data.date))}</span><span class="fx-live"><i></i>Markaziy bank</span></div>
  <div class="fx-board" data-cur="${usd.c}" role="button" tabindex="0">
    <div class="bh"><span class="fl">${flag(usd.c)}</span><div><b>${usd.n > 1 ? usd.n + " " : "1 "}${esc(usd.nm)}</b><small>${usd.c} · rasmiy kurs</small></div>${chg(usd.d, "pill")}</div>
    <div class="flap" aria-label="${fmt(usd.r, 2)} so'm">${digits}<em>,${fp} so'm</em></div>
    <div class="bf"><span>Kecha <b>${fmt(prev, 2)}</b></span><span>MB · ${esc(shortDate(data.date))}</span></div>
  </div>
  ${b ? `<div class="fx-bk" data-banks="${usd.c}" role="button" tabindex="0">
      <div><small>Bankda sotsangiz</small><b>${b.buy ? fmt(b.buy.v) : "—"}</b><i>${esc(b.buy ? b.buy.bank : "")}</i></div>
      <div><small>Bankdan olsangiz</small><b>${b.sell ? fmt(b.sell.v) : "—"}</b><i>${esc(b.sell ? b.sell.bank : "")}</i></div>
      <span class="ar">›</span></div>` : ""}
  <div class="fx-lh"><span>Boshqa valyutalar</span>${rest.length > 7 ? `<button data-act="all">${showAll ? "Qisqaroq" : `Hammasi (${rest.length})`} ›</button>` : ""}</div>
  <div class="fx-list">${list.map((x) => `<button class="fx-row" data-cur="${x.c}">
      <span class="fl">${flag(x.c)}</span><span class="n"><b>${x.n > 1 ? x.n + " " : ""}${x.c}</b><small>${esc(x.nm)}</small></span>
      ${spark(x.sp, 58, 26, (x.sp || []).length > 1 ? x.sp[x.sp.length - 1] >= x.sp[0] : x.d >= 0)}
      <span class="v"><b>${fmt(x.r)}</b>${chg(x.d)}</span></button>`).join("")}</div>
  <p class="fx-src">Manba: O'zbekiston Respublikasi Markaziy banki · har kuni yangilanadi</p>
  <div class="fx-foot"><button class="fx-cta" data-act="conv">${ICO.calc}<span>Kalkulyator</span><i>100 ${SYM[usd.c] || usd.c} = ${fmt(usd.r / usd.n * 100, 0)} so'm</i></button></div>`;
}
function flap() {
  if (flapDone || RM) { flapDone = true; return; }
  flapDone = true;
  document.querySelectorAll("#fxview .flap span[data-d]").forEach((s, i) => {
    const fin = s.dataset.d; let n = 0;
    const t = setInterval(() => {
      if (++n > 7 + i * 2) { clearInterval(t); s.textContent = fin; s.classList.add("land"); return; }
      s.textContent = String((+fin + n) % 10); s.classList.toggle("flip");
    }, 55);
  });
}

// ------------------------------------------------------------------ 📈 valyuta sahifasi
const hist = {};
async function loadHist(c, d) {
  const k = c + d;
  if (!hist[k]) { const r = await api(`api/fx/h/${c}?d=${d}`); hist[k] = r.ok ? r.pts : []; }
  return hist[k];
}
function viewCur(v) {
  const x = byCode(v.c);
  if (!x) return backBar("Valyuta") + `<p class="fx-empty">Bu valyuta topilmadi.</p>`;
  const pct = x.r - x.d ? x.d / (x.r - x.d) * 100 : 0;
  const al = (alertsCache || []).filter((a) => a.c === x.c);
  return backBar(`${esc(x.nm)} · ${x.c}`, `<span class="fl sm">${flag(x.c)}</span>`) + `
  <div class="fx-big"><b>${fmt(x.r)}</b><small>so'm${x.n > 1 ? ` · ${x.n} ${x.c}` : ""}</small></div>
  <div class="fx-chgl ${x.d > 0 ? "u" : x.d < 0 ? "d" : ""}">${x.d > 0 ? "▲" : x.d < 0 ? "▼" : "•"} ${fmt(Math.abs(x.d))} (${pct >= 0 ? "+" : "−"}${fmt(Math.abs(pct), 2)}%) bugun</div>
  <div class="fx-chart" id="fxchart"><div class="fx-load sm"><i></i><i></i><i></i></div></div>
  <div class="fx-per" role="tablist">${[[7, "7 kun"], [30, "30 kun"], [90, "3 oy"], [365, "1 yil"]].map(([d, l]) =>
    `<button data-per="${d}" role="tab" aria-selected="${d === v.d}" class="${d === v.d ? "on" : ""}">${l}</button>`).join("")}</div>
  <div class="fx-stats" id="fxstats"></div>
  ${BANK_CODES.includes(x.c) ? `<button class="fx-link" data-banks="${x.c}">${ICO.bank}<span>Banklarda ${x.c} kursi</span><i>›</i></button>` : ""}
  <div class="fx-alert">
    <div class="ah"><span class="bell">🔔</span><div><b>Kurs o'zgarsa xabar beraman</b><small>Markaziy bank kursi chegaraga yetganda bot sizga yozadi</small></div></div>
    ${al.map((a) => `<div class="al"><span>${a.op === "gt" ? "▲ oshsa" : "▼ tushsa"}: <b>${fmt(a.v)} so'm</b></span><button data-delal="${a.id}" aria-label="O'chirish">${ICO.del}</button></div>`).join("")}
    ${inTg ? `<div class="af"><input id="fxalv" inputmode="decimal" autocomplete="off" aria-label="Chegara kurs" value="${fmt(Math.round(x.r * (v.op === "gt" ? 1.01 : 0.99)), 0).replace(/ /g, " ")}">
      <div class="op"><button data-op="lt" class="${v.op !== "gt" ? "on" : ""}">tushsa</button><button data-op="gt" class="${v.op === "gt" ? "on" : ""}">oshsa</button></div></div>
      <button class="fx-btn" data-act="addal">🔔 Eslatma qo'yish</button>` : `<p class="fx-note">Eslatma qo'yish uchun ilovani bot ichida oching.</p>`}
  </div>
  <p class="fx-src">Manba: O'zbekiston Respublikasi Markaziy banki · cbu.uz</p>`;
}
async function drawChart(v) {
  const box = $("fxchart"); if (!box) return;
  const pts = await loadHist(v.c, v.d);
  if (top() !== v || !$("fxchart")) return;
  const st = $("fxstats");
  if (!pts || pts.length < 2) {
    box.innerHTML = `<p class="fx-empty sm">Grafik uchun tarix yig'ilmoqda — birozdan keyin to'ladi.</p>`; if (st) st.innerHTML = ""; return;
  }
  const W = box.clientWidth || 340, H = 200, P = 14;
  const vals = pts.map((p) => p[1]), mn = Math.min(...vals), mx = Math.max(...vals), span = mx - mn || 1;
  const X = (i) => i / (pts.length - 1) * W, Y = (y) => P + (1 - (y - mn) / span) * (H - 2 * P);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
  const up = vals[vals.length - 1] >= vals[0];
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="${up ? "u" : "d"}" role="img" aria-label="Kurs grafigi">
    <defs><linearGradient id="fxg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-opacity=".32"/><stop offset="1" stop-opacity="0"/></linearGradient></defs>
    ${[0.25, 0.5, 0.75].map((f) => `<line class="gl" x1="0" x2="${W}" y1="${H * f}" y2="${H * f}"/>`).join("")}
    <path class="ar" d="${line}L${W},${H}L0,${H}Z"/><path class="ln" d="${line}"/>
    <line class="cur" id="fxcl" y1="0" y2="${H}" x1="-9" x2="-9"/><circle class="dot" id="fxdot" r="5.5" cx="${X(pts.length - 1)}" cy="${Y(vals[vals.length - 1])}"/></svg>
    <div class="fx-tip" id="fxtip" hidden></div>`;
  const svg = box.querySelector("svg"), tip = $("fxtip"), cl = $("fxcl"), dot = $("fxdot");
  const at = (e) => {
    const r = svg.getBoundingClientRect(), i = Math.max(0, Math.min(pts.length - 1, Math.round((e.clientX - r.left) / r.width * (pts.length - 1))));
    const x = X(i), y = Y(pts[i][1]);
    cl.setAttribute("x1", x); cl.setAttribute("x2", x); dot.setAttribute("cx", x); dot.setAttribute("cy", y);
    tip.hidden = false; tip.innerHTML = `${fmt(pts[i][1])}<small>${esc(shortDate(pts[i][0]))}</small>`;
    tip.style.left = Math.max(0, Math.min(W - 96, x - 48)) + "px"; tip.style.top = Math.max(0, y - 54) + "px";
  };
  let last = -1;
  svg.addEventListener("pointerdown", (e) => { at(e); haptic(); });
  svg.addEventListener("pointermove", (e) => { if (e.buttons || e.pointerType === "mouse") { at(e); const i = Math.round(e.offsetX / W * (pts.length - 1)); if (i !== last) { last = i; } } });
  svg.addEventListener("pointerleave", () => { tip.hidden = true; cl.setAttribute("x1", -9); cl.setAttribute("x2", -9); dot.setAttribute("cx", X(pts.length - 1)); dot.setAttribute("cy", Y(vals[vals.length - 1])); });
  const ch = (vals[vals.length - 1] - vals[0]) / vals[0] * 100;
  if (st) st.innerHTML = `<div><small>Eng past</small><b>${fmt(mn, mn >= 1000 ? 0 : 2)}</b></div><div><small>Eng yuqori</small><b>${fmt(mx, mx >= 1000 ? 0 : 2)}</b></div>
    <div><small>Davr ichida</small><b class="${ch >= 0 ? "u" : "d"}">${ch >= 0 ? "+" : "−"}${fmt(Math.abs(ch), 1)}%</b></div>`;
}

// ------------------------------------------------------------------ 🏦 banklar
const banksCache = {};
function viewBanks(v) {
  const codes = BANK_CODES.filter((c) => byCode(c));
  const b = banksCache[v.c];
  const word = {USD: "Dollar", EUR: "Yevro", RUB: "Rubl", GBP: "Funt", KZT: "Tenge", CHF: "Frank", JPY: "Iyena", CNY: "Yuan"}[v.c] || v.c;
  let body;
  if (!b) body = `<div class="fx-load"><i></i><i></i><i></i></div>`;
  else if (!b.rows.some((r) => r.b || r.s)) body = `<p class="fx-empty">Banklar kursi hali yuklanmagan yoki bu valyutani banklar ko'rsatmayapti.</p>`;
  else {
    const bb = b.best || {};
    const rows = [...b.rows].sort((p, q) => (q.b || 0) - (p.b || 0) || (p.s || 9e9) - (q.s || 9e9));
    body = `<div class="fx-best">
      <div class="bc sell"><small>${word} sotmoqchimisiz?</small><p>Eng qimmat oladi</p><b>${bb.buy ? fmt(bb.buy.v) : "—"}</b><i>${esc(bb.buy ? bb.buy.bank : "")}</i></div>
      <div class="bc buy"><small>${word} olmoqchimisiz?</small><p>Eng arzon sotadi</p><b>${bb.sell ? fmt(bb.sell.v) : "—"}</b><i>${esc(bb.sell ? bb.sell.bank : "")}</i></div></div>
      <div class="fx-th"><span>Bank</span><span>Oladi</span><span>Sotadi</span></div>
      ${rows.map((r) => `<div class="fx-tr"><span><i style="background:${esc(r.col)}">${esc(r.n[0])}</i>${esc(r.n)}</span>
        <b class="${bb.buy && r.b === bb.buy.v ? "hi" : ""}">${r.b ? fmt(r.b) : "—"}</b><b class="${bb.sell && r.s === bb.sell.v ? "hi" : ""}">${r.s ? fmt(r.s) : "—"}</b></div>`).join("")}`;
  }
  const x = byCode(v.c);
  return backBar("Banklarda kurs") + `<div class="fx-cs" role="tablist">${codes.map((c) => `<button data-bc="${c}" role="tab" aria-selected="${c === v.c}" class="${c === v.c ? "on" : ""}">${flag(c)} ${c}</button>`).join("")}</div>
    ${body}<p class="fx-src">Banklarning o'z saytidan · har 30 daqiqada${x ? ` · MB: ${fmt(x.r)}` : ""}<br>Bankdagi aniq kurs amal bajarilayotgan paytda belgilanadi.</p>`;
}
async function loadBanks(c) {
  const r = await api(`api/fx/banks/${c}`);
  banksCache[c] = r.ok ? r : {rows: []};
  if (opened && top().v === "banks" && top().c === c) render();
}

// ------------------------------------------------------------------ 🧮 kalkulyator
let conv = lsGet("zk_fxconv", {a: "USD", b: "UZS", s: "100"}), fresh = true;   // fresh: birinchi bosish eski summani almashtiradi
function convVals() {
  const ua = unit(conv.a), ub = unit(conv.b);
  const amt = parseFloat(String(conv.s).replace(",", ".")) || 0;
  return {amt, res: ua && ub ? amt * ua / ub : null, ua, ub};
}
function quick(c) {
  const u = unit(c) || 1;
  if (c === "UZS") return [100000, 500000, 1000000, 5000000];
  const base = u > 5000 ? [10, 100, 500, 1000] : u > 500 ? [100, 500, 1000, 5000] : u > 50 ? [1000, 5000, 10000, 50000] : [10000, 50000, 100000, 500000];
  return base;
}
function viewConv() {
  const {res} = convVals();
  const ua = unit(conv.a), ub = unit(conv.b);
  const one = ua && ub ? ua / ub : null;
  const bnk = conv.b === "UZS" && banksRange(conv.a);
  return backBar("Valyuta kalkulyatori") + `<h2 class="fx-h2">Qancha bo'ladi?</h2><p class="fx-sub">Raqam yozing — darhol hisoblanadi</p>
  <div class="fx-box act"><div class="l"><span>Menda bor</span><span>${esc(nm(conv.a))}</span></div>
    <div class="m"><button class="cur" data-pick="a"><i>${flag(conv.a)}</i>${conv.a} ▾</button><span class="amt" id="fxamt">${esc(conv.s ? fmt(+conv.s.replace(",", "."), conv.s.includes(",") ? Math.min(2, conv.s.split(",")[1].length) : 0) : "0")}${conv.s.endsWith(",") ? "," : ""}<i class="caret"></i></span></div></div>
  <button class="fx-swap" data-act="swap" aria-label="Almashtirish">${ICO.swap}</button>
  <div class="fx-box"><div class="l"><span>Olaman</span><span>${esc(nm(conv.b))}</span></div>
    <div class="m"><button class="cur" data-pick="b"><i>${flag(conv.b)}</i>${conv.b} ▾</button><span class="amt res" id="fxres">${res == null ? "—" : fmt(res, res >= 100 ? 0 : 2)}</span></div></div>
  <div class="fx-rate"><span>1 ${conv.a} = ${one == null ? "—" : fmt(one, one >= 100 ? 2 : 4)} ${conv.b === "UZS" ? "so'm" : conv.b} (MB)</span>${bnk ? `<span>Bankda: ${bnk}</span>` : ""}</div>
  <div class="fx-qs">${quick(conv.a).map((q) => `<button data-q="${q}">${fmt(q, 0)} ${SYM[conv.a] && conv.a !== "UZS" ? SYM[conv.a] : ""}</button>`).join("")}</div>
  <div class="fx-kp">${["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "⌫"].map((k) => `<button data-k="${k}" class="${k === "," || k === "⌫" ? "x" : ""}" aria-label="${k === "⌫" ? "O'chirish" : k}">${k}</button>`).join("")}</div>`;
}
function banksRange(c) {
  const b = (data && data.best || {})[c];
  return b && b.buy && b.sell ? `${fmt(b.buy.v)} – ${fmt(b.sell.v)}` : "";
}
function key(k) {
  let s = conv.s || "";
  if (fresh && k !== "⌫") s = "";
  fresh = false;
  if (k === "⌫") s = s.slice(0, -1);
  else if (k === ",") { if (!s.includes(",")) s = (s || "0") + ","; }
  else {
    if (s.includes(",") && s.split(",")[1].length >= 2) return;
    if (s.replace(",", "").length >= 12) return;
    s = s === "0" ? k : s + k;
  }
  conv.s = s; lsSet("zk_fxconv", conv); haptic();
  paintConv();
}
function paintConv() {
  const {res} = convVals();
  const a = $("fxamt"), r = $("fxres");
  if (!a || !r) { render(); return; }
  const s = conv.s;
  a.innerHTML = esc(s ? fmt(+s.replace(",", "."), s.includes(",") ? Math.min(2, s.split(",")[1].length) : 0) : "0") + (s.endsWith(",") ? "," : "") + '<i class="caret"></i>';
  r.textContent = res == null ? "—" : fmt(res, res >= 100 ? 0 : 2);
}
function pickSheet(side) {
  const codes = ["UZS", ...(data.items || []).map((x) => x.c)];
  const el = document.createElement("div");
  el.className = "fx-pick"; el.innerHTML = `<div class="ps" role="dialog" aria-modal="true" aria-label="Valyuta tanlash"><i class="grip"></i><b>Valyutani tanlang</b>
    <div class="pl">${codes.map((c) => `<button data-pc="${c}" class="${conv[side] === c ? "on" : ""}"><span class="fl">${flag(c)}</span><span><b>${c}</b><small>${esc(nm(c))}</small></span></button>`).join("")}</div></div>`;
  $("fx").appendChild(el);
  requestAnimationFrame(() => el.classList.add("on"));
  const close = () => { el.classList.remove("on"); setTimeout(() => el.remove(), 250); };
  el.addEventListener("click", (e) => {
    const b = e.target.closest("[data-pc]");
    if (b) {
      const c = b.dataset.pc, other = side === "a" ? "b" : "a";
      if (conv[other] === c) conv[other] = conv[side];
      conv[side] = c; lsSet("zk_fxconv", conv); haptic(); close(); render(); return;
    }
    if (e.target === el) close();
  });
}

// ------------------------------------------------------------------ chizish va boshqaruv
function render() {
  const v = top(), el = $("fxview");
  if (!el) return;
  el.innerHTML = v.v === "home" ? viewHome() : v.v === "cur" ? viewCur(v) : v.v === "banks" ? viewBanks(v) : viewConv();
  $("fx").dataset.v = v.v;
  if (v.v === "home" && data) flap();
  if (v.v === "cur") drawChart(v);
  updateBack();
}
function go(v) { stack.push(v); haptic(); render(); $("fxscroll").scrollTop = 0; }
function back() { if (stack.length > 1) { stack.pop(); render(); } }
function updateBack() {
  if (!tg || !tg.BackButton) return;
  try {
    if (opened && stack.length > 1) tg.BackButton.show();
    else if (opened && (!window.ZK_canHideBack || window.ZK_canHideBack())) tg.BackButton.hide();
  } catch (e) {}
}

function onClick(e) {
  const t = e.target;
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "fx" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  const a = t.closest("[data-act]");
  if (a) {
    const act = a.dataset.act;
    if (act === "homeback") { if (window.ZK_setMode) window.ZK_setMode("kino"); return; }
    if (act === "hub") { if (window.ZHub && window.ZHub.open) window.ZHub.open(); return; }
    if (act === "back") back();
    else if (act === "conv") { fresh = true; go({v: "conv"}); }
    else if (act === "all") { showAll = !showAll; haptic(); render(); }
    else if (act === "swap") { [conv.a, conv.b] = [conv.b, conv.a]; lsSet("zk_fxconv", conv); haptic(); render(); }
    else if (act === "addal") addAlert();
    return;
  }
  const c = t.closest("[data-cur]");
  if (c) { go({v: "cur", c: c.dataset.cur, d: 30, op: "lt"}); return; }
  const bk = t.closest("[data-banks]");
  if (bk) { go({v: "banks", c: bk.dataset.banks}); loadBanks(bk.dataset.banks); return; }
  const bc = t.closest("[data-bc]");
  if (bc) { top().c = bc.dataset.bc; haptic(); render(); if (!banksCache[bc.dataset.bc]) loadBanks(bc.dataset.bc); return; }
  const per = t.closest("[data-per]");
  if (per) { top().d = +per.dataset.per; haptic(); render(); return; }
  const op = t.closest("[data-op]");
  if (op) { top().op = op.dataset.op; document.querySelectorAll("#fxview [data-op]").forEach((b) => b.classList.toggle("on", b === op)); haptic(); return; }
  const del = t.closest("[data-delal]");
  if (del) { api("api/fx/alerts", {del: del.dataset.delal}).then((r) => { if (r.ok) { alertsCache = r.items; render(); } }); haptic(); return; }
  const k = t.closest("[data-k]");
  if (k) { key(k.dataset.k); return; }
  const q = t.closest("[data-q]");
  if (q) { conv.s = q.dataset.q; fresh = true; lsSet("zk_fxconv", conv); haptic(); paintConv(); return; }
  const p = t.closest("[data-pick]");
  if (p) { pickSheet(p.dataset.pick); }
}
async function addAlert() {
  const v = top(), inp = $("fxalv");
  const val = parseFloat(String(inp && inp.value || "").replace(/[\s ]/g, "").replace(",", "."));
  if (!val || val <= 0) { haptic("err"); inp && inp.focus(); return; }
  const r = await api("api/fx/alerts", {c: v.c, op: v.op || "lt", v: val});
  if (r.ok) { alertsCache = r.items; haptic("ok"); render(); }
  else { haptic("err"); alert(r.error === "limit" ? "Ko'pi bilan 5 ta eslatma qo'yish mumkin." : r.error === "auth" ? "Ilovani bot ichida qayta oching." : "Saqlab bo'lmadi, qayta urinib ko'ring."); }
}

if (tg && tg.BackButton) tg.BackButton.onClick(() => { if (opened && stack.length > 1) back(); });

window.ZFx = {
  open() {
    if (!mounted) {
      mounted = true;
      $("fx").addEventListener("click", onClick);
      $("fx").addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.matches("[role=button]")) { e.preventDefault(); e.target.click(); } });
      addEventListener("keydown", (e) => {
        if (!opened || top().v !== "conv" || e.target.tagName === "INPUT") return;
        if (/^[0-9]$/.test(e.key)) key(e.key); else if (e.key === "Backspace") key("⌫"); else if (e.key === "," || e.key === ".") key(",");
      });
    }
    opened = true;
    $("fx").hidden = false; document.body.classList.add("fx-on");
    render();
    if (!data || Date.now() / 1000 - (data.at || 0) > 1800) loadHome(true).then(() => { if (opened) render(); });
    if (alertsCache === null) loadAlerts().then(() => { if (opened && top().v === "cur") render(); });
  },
  close() {
    opened = false;
    $("fx").hidden = true; document.body.classList.remove("fx-on");
    updateBack();
  },
  busy() { return opened && stack.length > 1; },
};
})();
