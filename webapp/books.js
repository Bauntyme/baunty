/* 📚 Kitoblar — kutubxona, qidiruv, kitob sahifasi, o'quvchi, javon. index.html dan window.ZBooks orqali boshqariladi.
   Bob matnlari va muqovalar statik fayllar (bk/{id}/...), API faqat ro'yxat va holat uchun. */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const lsGet = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const reduced = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

// ------------------------------------------------------------------ ikonkalar
const I = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="#2A1A00"><path d="M7 4.5v15l12-7.5z"/></svg>',
  mark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M6 3h12v18l-6-4.5L6 21z"/></svg>',
  dl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0-4-4m4 4 4-4M4 21h16"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/></svg>',
  lib: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><rect x="4" y="3" width="4" height="18" rx="1"/><rect x="10" y="3" width="4" height="18" rx="1"/><path d="m16.5 4.5 3.6-.9 3 16.5-3.6.9z"/></svg>',
  shelf: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M6 3h12v18l-6-4.5L6 21z"/></svg>',
  share: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M12 3v12M7 8l5-5 5 5"/></svg>',
  toc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="#5ED19B" stroke-width="2.2" stroke-linejoin="round"><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5" stroke-linecap="round"/></svg>',
  ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5 9-10"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  pen: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>',
  note: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M4 4h16v12H9l-5 4z"/></svg>',
  head: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="5" height="7" rx="2"/><rect x="16" y="14" width="5" height="7" rx="2"/></svg>',
  pp: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l12-7.5z"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4.5" width="4.2" height="15" rx="1.2"/><rect x="13.8" y="4.5" width="4.2" height="15" rx="1.2"/></svg>',
  prev: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="4.5" y="5" width="2.6" height="14" rx="1"/><path d="M19.5 5v14L8.5 12z"/></svg>',
  next: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="16.9" y="5" width="2.6" height="14" rx="1"/><path d="M4.5 5v14l11-7z"/></svg>',
  b15: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 3.5v4.3h4.3"/><text x="12" y="15.6" font-size="7.6" font-weight="800" text-anchor="middle" fill="currentColor" stroke="none" font-family="Man,sans-serif">15</text></svg>',
  f30: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.4-5.7"/><path d="M20 3.5v4.3h-4.3"/><text x="12" y="15.6" font-size="7.6" font-weight="800" text-anchor="middle" fill="currentColor" stroke="none" font-family="Man,sans-serif">30</text></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>',
  down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5 9 7 7 7-7"/></svg>',
};

const LANGS = {uz: ["🇺🇿", "O'zbek", "o'zbek tilida"], ru: ["🇷🇺", "Русский", "rus tilida"], en: ["🇬🇧", "English", "ingliz tilida"]};
const GEN = {roman: ["📖", "Roman"], sheriyat: ["🪶", "She'riyat"], hikoya: ["✍️", "Hikoya"], tarix: ["🏛", "Tarix"], drama: ["🎭", "Drama"],
  bolalar: ["🧸", "Bolalar"], sarguzasht: ["🧭", "Sarguzasht"], detektiv: ["🔎", "Detektiv"], fantastika: ["🚀", "Fantastika"],
  falsafa: ["💭", "Falsafa"], diniy: ["🕌", "Diniy"], ilmiy: ["🔬", "Ilmiy"], psixologiya: ["🧠", "Psixologiya"], biznes: ["💼", "Biznes"],
  boshqa: ["📚", "Boshqa"]};
const SORTS = [["pop", "mashhur"], ["new", "yangi"], ["az", "A–Z"], ["short", "qisqa"], ["rate", "baho"]];
const FMT = {epub: ["EPUB — telefon uchun", "har qanday o'quvchi ilovada ochiladi"], pdf: ["PDF — chop etish uchun", "sahifalari aynan saqlanadi"],
  fb2: ["FB2", "rus o'quvchi ilovalari uchun"], txt: ["Oddiy matn", "eng yengil"]};
const gname = (g) => (GEN[g] || GEN.boshqa)[1];
const mb = (n) => !n ? "" : n < 1048576 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1048576).toFixed(1).replace(".", ",")} MB`;
const hours = (pages) => { const m = Math.round((pages || 1) * 1.6); return m < 60 ? `${m} daq` : `${Math.round(m / 60)} soat`; };
const fmtT = (s) => { s = Math.max(0, Math.floor(s || 0)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${x}` : `${m}:${x}`; };
const dur = (s) => { const m = Math.round((s || 0) / 60); return m < 60 ? `${Math.max(1, m)} daq` : `${Math.floor(m / 60)} soat${m % 60 >= 5 ? ` ${m % 60} daq` : ""}`; };
const shortA = (a) => String(a || "").split(",")[0].trim();
const ago = (ts) => {
  if (!ts) return "";
  const d = Math.floor((Date.now() / 1000 - ts) / 86400);
  return d <= 0 ? "bugun" : d === 1 ? "kecha" : d < 7 ? `${d} kun oldin` : d < 30 ? `${Math.floor(d / 7)} hafta oldin` : `${Math.floor(d / 30)} oy oldin`;
};

// ------------------------------------------------------------------ holat
let opened = false, botName = "", mounted = false;
let tab = "lib";                        // lib | search | shelf
let stack = [];                         // [{v:"book", id} | {v:"list", p, items, total, off}]
let home = null, homeErr = false, me = null, meAt = 0;
const books = new Map();                // id → batafsil
const S = {q: "", l: "", f: "", g: "", ab: "", s: "pop", items: null, total: 0, off: 0, loading: false, tok: 0};
let shelfTab = "reading";
let sheetOpen = false;

const api = async (path, body) => {
  const opt = {headers: {"X-Init-Data": (tg && tg.initData) || ""}};
  if (body) { opt.method = "POST"; opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  const r = await fetch(path, opt);
  try { return await r.json(); } catch (e) { return {ok: false, error: r.status >= 500 ? "busy" : "net"}; }
};
function toast(msg, ms = 2600) {
  const t = $("bxtoast"); if (!t) return;
  t.textContent = msg; t.classList.add("on");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("on"), ms);
}

// ------------------------------------------------------------------ muqova
function cover(b, size = "") {
  const k = ((b.i || 0) * 7 + String(b.t || "").length) % 14;
  const isL = size === "big" || size === "feat";
  const bid = b.i || b.id || "1";
  const proxySrc = `bk/${bid}/cover_${isL ? "l" : "s"}.webp${b.cv ? "?v=" + b.cv : ""}`;
  const directSrc = (b.cover && typeof b.cover === "string" && b.cover.startsWith("http")) ? b.cover
    : (b.poster && typeof b.poster === "string" && b.poster.startsWith("http")) ? b.poster
    : (b.image && typeof b.image === "string" && b.image.startsWith("http")) ? b.image : "";
  const fbUrl = directSrc ? directSrc.replace(/'/g, "%27") : "";
  const cleanTitle = cleanBookText(b.t || b.title || "");
  const cleanAuthor = cleanBookText(b.a || b.author || "");
  const img = (b.c || directSrc || bid)
    ? `<img src="${proxySrc}" alt="${esc(cleanTitle)}" loading="lazy" decoding="async" onerror="this.onerror=null;if(this.dataset.fb!='1'&&'${fbUrl}'){this.dataset.fb='1';this.src='${fbUrl}';}else{this.closest('.cv')?.classList.remove('has');this.remove();}">`
    : "";
  const lw = Math.max(0, ...String(cleanTitle || "").split(/\s+/).map((w) => w.length));
  const tl = lw > 11 || String(cleanTitle || "").length > 42 ? " t3" : lw > 8 || String(cleanTitle || "").length > 28 ? " t2" : "";
  return `<div class="cv k${k} ${size}${tl}${b.c || directSrc || bid ? " has" : ""}" lang="${esc(b.l || b.lang || "uz")}" aria-hidden="true"><span class="d"></span>${img}${b.au ? '<span class="aub" title="Audiokitob">🎧</span>' : ""}<b>${esc(cleanTitle)}</b><i>${esc(shortA(cleanAuthor))}</i></div>`;
}
function itemHTML(b, sub) {
  const cleanTitle = cleanBookText(b.t);
  const cleanAuthor = cleanBookText(b.a);
  return `<button class="bx-it" data-book="${b.i}">${cover(b)}<div class="nm">${esc(cleanTitle)}</div>
    <div class="${sub ? "sub" : "au"}">${sub ? esc(sub) : esc(shortA(cleanAuthor))}</div></button>`;
}
function badges(b) {
  const out = [`<span class="bx-bdg l">${(b.l || "").toUpperCase()}</span>`];
  (b.f || []).slice(0, 3).forEach((f) => out.push(`<span class="bx-bdg">${f.toUpperCase()}${b.s && b.s[f] ? " · " + mb(b.s[f]) : ""}</span>`));
  if (b.m === "scan") out.push(`<span class="bx-bdg">📷 skaner</span>`);
  if (b.lv) out.push(`<span class="bx-bdg">${b.lv}</span>`);
  return `<div class="bx-badges">${out.join("")}</div>`;
}
function resHTML(b) {
  const cleanTitle = cleanBookText(b.t);
  const cleanAuthor = cleanBookText(b.a);
  return `<div class="bx-res" role="group"><button class="cvw" data-book="${b.i}" aria-label="${esc(cleanTitle)}">${cover(b)}</button>
    <div class="mt"><button data-book="${b.i}" style="text-align:left;display:block"><b>${esc(cleanTitle)}</b></button>
    <div class="au">${esc(shortA(cleanAuthor) || "Muallif noma'lum")}${b.y ? " · " + b.y : ""}</div>${badges(b)}
    <div class="bx-acts">${b.m === "audio" ? `<button data-play="${b.i}"><span>🎧 Tinglash · ${dur(b.au)}</span></button>`
      : `<button data-read="${b.i}"><span>O'qish</span></button><button data-dl="${b.i}"><span>Yuklab olish</span></button>${b.au ? `<button data-play="${b.i}"><span>Tinglash</span></button>` : ""}`}</div></div></div>`;
}

// ------------------------------------------------------------------ umumiy qismlar
function rootHead() {
  return `<header class="bx-head-clean"><button class="bx-back" data-act="homeback" aria-label="Bosh sahifa">${I.back}</button><div class="bx-head-title"><b>Kutubxona</b><small>Elektron kitoblar va audio</small></div><button class="zk-hubbtn" data-act="hub" type="button" aria-label="Barcha bo'limlar"><span>☰</span> Bo'limlar</button></header>`;
}
function navHTML() {
  return `<nav class="bx-nav">
    <button data-tab="lib" class="${tab === "lib" ? "on" : ""}">${I.lib}Kutubxona</button>
    <button data-tab="search" class="${tab === "search" ? "on" : ""}">${I.search}Qidiruv</button>
    <button data-tab="shelf" class="${tab === "shelf" ? "on" : ""}">${I.shelf}Javonim</button></nav>`;
}
const skel = (n = 3) => Array.from({length: n}, () => '<div class="bx-skel"></div>').join("");

function render(keepScroll) {
  if (!opened) return;
  const sc = $("bxscroll"); const y = keepScroll && sc ? sc.scrollTop : 0;
  const top = stack[stack.length - 1];
  let html;
  if (top && top.v === "book") html = bookHTML(top.id);
  else if (top && top.v === "list") html = listHTML(top);
  else html = tab === "search" ? searchHTML() : tab === "shelf" ? shelfHTML() : homeHTML();
  const abc = !top && tab === "search";
  $("bxview").innerHTML = `<div class="bx-scroll${top ? " nonav" : ""}${abc ? " hasabc" : ""}" id="bxscroll">${html}</div>${top ? "" : navHTML()}`;
  abcSync(abc);
  if (keepScroll) $("bxscroll").scrollTop = y;
  if (!top && tab === "search") bindSearch();
  bindMore();
  updateBack();
  apSync();
}

// ------------------------------------------------------------------ 1 · Kutubxona
function homeHTML() {
  if (!home) {
    return rootHead() + (homeErr ? `<div class="bx-empty"><div class="big">📶</div><b>Yuklab bo'lmadi</b>Internetni tekshirib, qayta urinib ko'ring.<br><br>
      <button class="bx-more" data-act="reload">🔄 Qayta urinish</button></div>` : `<div class="bx-hello"><h1>Bugun nima o'qiymiz?</h1></div>${skel(4)}`);
  }
  const langs = Object.keys(home.langs || {}).filter((l) => LANGS[l]);
  let h = rootHead() + `<div class="bx-hello"><h1>Bugun nima<br>o'qiymiz?</h1>
    <p>${home.total ? `${langs.length || 1} tilda ${home.total.toLocaleString("ru-RU").replace(/,/g, " ")} ta kitob` : "Kutubxona to'ldirilmoqda"}</p></div>
    <button class="bx-search" data-tab="search">${I.search}<span>Kitob, muallif yoki janr</span></button>`;
  const feat = (home.shelves || []).find((x) => x.k === "featured");
  if (feat) {
    h += `<section class="bx-feat" aria-label="${esc(feat.t)}"><div class="ft"><h2>${esc(feat.t)}</h2><span>${feat.items.length} ta kitob</span></div>
      <div class="fr">${feat.items.map((b) => `<button class="fi" data-book="${b.i}">${cover(b, "feat")}<b>${esc(b.t)}</b>${b.a ? `<i>${esc(shortA(b.a))}</i>` : ""}</button>`).join("")}</div></section>`;
  }
  const top10 = (home.shelves || []).find((x) => x.k === "top");
  if (top10) {
    h += `<div class="bx-h"><h2>${esc(top10.t)}</h2><span class="bx-mute" style="font-size:12.5px">shu hafta ko'p o'qilgan</span></div>
      <ol class="bx-top10">${top10.items.map((b, n) => `<li><button data-book="${b.i}" aria-label="${n + 1}-o'rin: ${esc(b.t)}">
        <span class="rk" aria-hidden="true">${n + 1}</span><span class="cw">${cover(b)}</span></button></li>`).join("")}</ol>`;
  }
  if (!home.total) {
    return h + `<div class="bx-empty"><div class="big">📚</div><b>Kitoblar joylanmoqda</b>Jahon, rus va o'zbek klassikasi kutubxonaga qo'shilyapti. Bir necha soatdan keyin qayta kiring.</div>`;
  }
  h += `<div class="bx-chips"><button class="bx-chip on">Hammasi</button>${langs.map((l) =>
    `<button class="bx-chip" data-list='${esc(JSON.stringify({t: LANGS[l][1], l}))}'>${LANGS[l][0]} ${LANGS[l][1]}</button>`).join("")}</div>`;
  const cont = me && (me.books || []).find((b) => !b.done && b.pct > 0);
  if (cont) {
    const left = Math.max(1, Math.round((100 - cont.pct) / 100 * (cont.p || 1) * 1.6));
    h += `<button class="bx-cont" data-read="${cont.i}"><div style="width:62px;flex:none">${cover(cont)}</div><div class="meta">
      <small>Davom ettiring</small><b>${esc(cont.t)}</b><i>${esc(shortA(cont.a))}${cont.ch ? ` · ${cont.ch + 1}-bob` : ""}</i>
      <div class="bar"><span style="width:${Math.max(2, cont.pct)}%"></span></div>
      <i>${Math.round(cont.pct)}% · taxminan ${left < 60 ? left + " daqiqa" : Math.round(left / 60) + " soat"} qoldi</i></div>
      <span class="bx-play">${I.play}</span></button>`;
  }
  const ac = me && (me.audio || [])[0];
  if (ac && !(A.b && A.b.i === ac.i)) {
    h += `<button class="bx-cont au" data-play="${ac.i}"><div style="width:62px;flex:none">${cover(ac)}</div><div class="meta">
      <small>${I.head}Tinglashni davom ettiring</small><b>${esc(ac.t)}</b><i>${esc(shortA(ac.a))}</i>
      <i class="w">${ac.n}-bob · ${fmtT(ac.pt)} da to'xtagansiz</i></div><span class="bx-play">${I.play}</span></button>`;
  }
  for (const sh of home.shelves || []) {
    if (sh.k === "featured" || sh.k === "top") continue;
    const [k, v] = sh.k.split(":");
    const t = k === "genre" ? `${(GEN[v] || GEN.boshqa)[0]} ${gname(v)}` : sh.t;
    const p = k === "lang" ? {t: sh.t, l: v} : k === "genre" ? {t: gname(v), g: v, l: "uz"} : k === "audio" ? {t: "Audiokitoblar", f: "audio", l: "uz"} : {t: sh.t, s: "new", l: "uz"};
    h += `<div class="bx-h"><h2>${esc(t)}</h2><button data-list='${esc(JSON.stringify(p))}'>Hammasi</button></div>
      <div class="bx-row">${sh.items.map((b) => itemHTML(b)).join("")}</div>`;
  }
  if ((home.genres || []).length) {
    h += `<div class="bx-h"><h2>Janrlar</h2></div><div class="bx-genres">${home.genres.slice(0, 12).map((g) =>
      `<button class="bx-genre" data-list='${esc(JSON.stringify({t: gname(g.g), g: g.g, l: "uz"}))}'><span class="e">${(GEN[g.g] || GEN.boshqa)[0]}</span><b>${gname(g.g)}</b><i>${g.n.toLocaleString("ru-RU")}</i></button>`).join("")}</div>`;
  }
  if ((home.collections || []).length) {
    const own = home.collections.filter((c) => !c.foreign);
    if (own.length) h += `<div class="bx-h"><h2>To'plamlar</h2></div>` + own.map((c) =>
      `<button class="bx-coll ${c.k}" data-list='${esc(JSON.stringify({t: c.t, l: c.k, coll: c.k}))}'>
        <small>${c.flag} ${esc(LANGS[c.k] ? LANGS[c.k][1] : c.k)} · ${c.n} ta kitob</small><b>${esc(c.t)}</b><p>${esc(c.d)}</p></button>`).join("");
  }
  return h + `<div style="height:8px"></div>`;
}

// ------------------------------------------------------------------ 7 · To'plam / ro'yxat
const LEVELS = [["", "Hammasi"], ["A2,B1", "Oson (A2–B1)"], ["B2", "O'rta (B2)"], ["C1", "Qiyin (C1)"]];
function listHTML(v) {
  const p = v.p;
  const coll = p.coll && home && (home.collections || []).find((c) => c.k === p.coll);
  let h = `<div class="bx-top"><button class="bx-ib" data-act="back" aria-label="Orqaga">${I.back}</button><div class="bx-ttl">${esc(coll ? "To'plam" : p.t)}</div></div>`;
  if (coll) h += `<div class="bx-coll ${coll.k}" style="pointer-events:none"><small>${coll.flag} ${esc(LANGS[coll.k] ? LANGS[coll.k][1] : coll.k)} · ${coll.n} ta kitob</small><b>${esc(coll.t)}</b><p>${esc(coll.d)}</p></div>`;
  if (p.l === "en") {
    h += `<div class="bx-chips">${LEVELS.map(([k, t]) => `<button class="bx-chip${(p.lv || "") === k ? " on" : ""}" data-lv="${k}">${t}</button>`).join("")}</div>`;
  } else if (!p.g && home && (home.genres || []).length > 1) {
    h += `<div class="bx-chips"><button class="bx-chip${!p.g2 ? " on" : ""}" data-g2="">Hammasi</button>${home.genres.slice(0, 10).map((g) =>
      `<button class="bx-chip${p.g2 === g.g ? " on" : ""}" data-g2="${g.g}">${(GEN[g.g] || GEN.boshqa)[0]} ${gname(g.g)}</button>`).join("")}</div>`;
  }
  const sortName = (SORTS.find((s) => s[0] === (p.s || "pop")) || SORTS[0])[1];
  h += `<div class="bx-tools"><button data-act="sort">Saralash: <b>${sortName}</b></button>
    <span>${v.items ? `${v.total.toLocaleString("ru-RU")} ta` : ""}</span>
    <button data-act="view">${v.grid === false ? "▦ Panjara" : "☰ Ro'yxat"}</button></div>`;
  if (!v.items) return h + skel(3);
  if (!v.items.length) return h + `<div class="bx-empty"><div class="big">🔎</div><b>Hozircha kitob yo'q</b>Boshqa bo'limni tanlab ko'ring.</div>`;
  h += v.grid === false ? v.items.map(resHTML).join("")
    : `<div class="bx-grid">${v.items.map((b) => itemHTML(b, b.m === "audio" ? `🎧 ${dur(b.au)}` : `${b.lv ? b.lv + " · " : ""}${b.p} bet`)).join("")}</div>`;
  if (v.items.length < v.total) h += `<button class="bx-more" data-act="more" id="bxmore">${v.loading ? "Yuklanmoqda…" : "Yana ko'rsatish"}</button>`;
  return h;
}
async function loadList(v, more) {
  if (v.loading) return;
  v.loading = true;
  const p = v.p;
  const q = new URLSearchParams({o: more ? v.items.length : 0, n: 30, s: p.s || "pop"});
  if (p.l) q.set("l", p.l);
  if (p.g || p.g2) q.set("g", p.g || p.g2);
  if (p.lv) q.set("lv", p.lv);
  if (p.f) q.set("f", p.f);
  try {
    const r = await api(`api/books/search?${q}`);
    if (r.ok) { v.items = more ? [...(v.items || []), ...r.items] : r.items; v.total = r.total; }
    else if (!more) v.items = [];
  } catch (e) { if (!more) v.items = []; toast("📶 Internet bilan muammo"); }
  v.loading = false;
  if (stack[stack.length - 1] === v) render(more);
}
function openList(p) {
  const v = {v: "list", p, items: null, total: 0, grid: lsGet("zk_bk_grid", true)};
  stack.push(v); render(); loadList(v);
}

// ------------------------------------------------------------------ 2 · Qidiruv
function searchHTML() {
  const lname = S.l ? `${LANGS[S.l][0]} ${LANGS[S.l][1]}` : "barchasi";
  const sname = (SORTS.find((s) => s[0] === S.s) || SORTS[0])[1];
  let h = `<div class="bx-top"><div class="bx-qbar">${I.search}<input id="bxq" type="search" enterkeyhint="search" autocomplete="off"
      placeholder="Kitob, muallif yoki janr" value="${esc(S.q)}" aria-label="Qidiruv">${S.q ? `<button class="clr" data-act="clr" aria-label="Tozalash">${I.x}</button>` : ""}</div></div>
    <div class="bx-chips">
      <button class="bx-chip tog${S.l ? " on" : ""}" data-act="lang">Til: ${lname}</button>
      <button class="bx-chip tog${S.f === "epub" ? " on" : ""}" data-f="epub">EPUB</button>
      <button class="bx-chip tog${S.f === "pdf" ? " on" : ""}" data-f="pdf">PDF</button>
      <button class="bx-chip tog${S.f === "audio" ? " on" : ""}" data-f="audio">🎧 Audio</button>
      <button class="bx-chip tog${S.g ? " on" : ""}" data-act="genre">${S.g ? gname(S.g) : "Janr"}</button>
      <button class="bx-chip tog${S.s !== "pop" ? " on" : ""}" data-act="ssort">Saralash: ${sname}</button>${S.ab ? `
      <button class="bx-chip tog on" data-act="abclr">«${esc(S.ab)}» ✕</button>` : ""}</div>`;
  const filtered = S.q || S.l || S.f || S.g || S.ab;
  if (!filtered) {
    const rec = lsGet("zk_bk_recent", []);
    if (rec.length) h += `<div class="bx-h"><h2>Oxirgi qidiruvlar</h2><button data-act="recclr">Tozalash</button></div>
      <div class="bx-recent">${rec.map((q) => `<button data-q="${esc(q)}">${I.clock}${esc(q)}</button>`).join("")}</div>`;
    if (home && (home.genres || []).length) h += `<div class="bx-h"><h2>Janr bo'yicha</h2></div><div class="bx-genres">${home.genres.slice(0, 9).map((g) =>
      `<button class="bx-genre" data-gs="${g.g}"><span class="e">${(GEN[g.g] || GEN.boshqa)[0]}</span><b>${gname(g.g)}</b><i>${g.n.toLocaleString("ru-RU")}</i></button>`).join("")}</div>`;
    return h;
  }
  if (S.items === null) return h + skel(4);
  let line = `${S.ab ? `«${esc(S.ab)}» harfi · ` : ""}${S.total.toLocaleString("ru-RU")} ta natija`;
  const authors = {};
  S.items.forEach((b) => { const a = shortA(b.a); if (a) authors[a] = (authors[a] || 0) + 1; });
  const top = Object.entries(authors).sort((a, b) => b[1] - a[1])[0];
  if (S.q && top && top[1] >= Math.max(2, S.items.length * 0.6)) line += ` · «${esc(top[0])}» asarlari`;
  h += `<div class="bx-count">${line}</div>`;
  if (!S.items.length) return h + `<div class="bx-empty"><div class="big">🔎</div><b>Hech narsa topilmadi</b>Boshqa so'z bilan yoki boshqa tilda yozib ko'ring: «Tolstoy», «Толстой».</div>`;
  h += S.items.map(resHTML).join("");
  if (S.items.length < S.total) h += `<button class="bx-more" data-act="smore" id="bxmore">${S.loading ? "Yuklanmoqda…" : "Yana ko'rsatish"}</button>`;
  return h;
}
let qT = 0;
function bindSearch() {
  const inp = $("bxq"); if (!inp) return;
  inp.addEventListener("input", () => {
    S.q = inp.value; clearTimeout(qT);
    qT = setTimeout(() => runSearch(true), 380);
  });
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { inp.blur(); clearTimeout(qT); runSearch(true); } });
}
async function runSearch(reset, more) {
  const tok = ++S.tok;
  if (reset) { S.items = null; S.off = 0; }
  const filtered = S.q.trim() || S.l || S.f || S.g || S.ab;
  if (!filtered) { S.items = null; renderSearchBody(); return; }
  if (!more) renderSearchBody();
  S.loading = true;
  const q = new URLSearchParams({q: S.q.trim(), s: S.s, o: more ? S.items.length : 0, n: 30});
  if (S.l) q.set("l", S.l); if (S.f) q.set("f", S.f); if (S.g) q.set("g", S.g); if (S.ab) q.set("ab", S.ab.toLowerCase());
  try {
    const r = await api(`api/books/search?${q}`);
    if (tok !== S.tok) return;
    if (r.ok) { S.items = more ? [...(S.items || []), ...r.items] : r.items; S.total = r.total; }
    else S.items = S.items || [];
    if (S.q.trim().length >= 3 && !more) {
      const rec = lsGet("zk_bk_recent", []).filter((x) => x.toLowerCase() !== S.q.trim().toLowerCase());
      rec.unshift(S.q.trim()); lsSet("zk_bk_recent", rec.slice(0, 8));
    }
  } catch (e) { if (tok === S.tok) { S.items = S.items || []; toast("📶 Internet bilan muammo"); } }
  S.loading = false;
  if (tok === S.tok) renderSearchBody(!!more);
}
function renderSearchBody(keep) {
  if (tab !== "search" || stack.length) return;
  const inp = $("bxq"); const focused = inp && document.activeElement === inp; const pos = inp ? inp.selectionStart : 0;
  render(keep);
  const n = $("bxq");
  if (n && focused) { n.focus(); try { n.setSelectionRange(pos, pos); } catch (e) {} }
}

// Alifbo tasmasi: o'ng chetda harflar — barmoq bilan yurgizilsa, shu harf bilan boshlanadigan kitoblar (A–Z tartibida)
const ABC = ["A", "B", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "X", "Y", "Z", "Sh", "Ch"];
let abcT = 0, abcDown = false;
// Tasma bir marta yaratiladi va qayta chizilmaydi — barmoq surilayotganda natijalar yangilansa ham uzilmaydi
function abcSync(show) {
  let el = $("bxabc");
  if (!el && show) el = makeAbc();
  if (!el) return;
  el.hidden = !show; $("bxabub").hidden = !show;
  if (!abcDown) el.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.ab === S.ab));
}
function makeAbc() {
  const host = $("bxview");
  host.insertAdjacentHTML("afterend", `<div class="bx-abc" id="bxabc" role="group" aria-label="Harf bo'yicha">${ABC.map((L) =>
    `<button data-ab="${L}" aria-label="${L} harfi">${L}</button>`).join("")}</div><div class="bx-abub" id="bxabub" aria-hidden="true"></div>`);
  const el = $("bxabc");
  let last = "";
  const at = (e) => { const r = el.getBoundingClientRect(); return ABC[Math.max(0, Math.min(ABC.length - 1, Math.floor((e.clientY - r.top) / r.height * ABC.length)))]; };
  const show = (L, e) => {
    const b = $("bxabub"); if (!b) return;
    b.textContent = L; b.style.top = `${e.clientY - $("books").getBoundingClientRect().top}px`; b.classList.add("on");
    el.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x.dataset.ab === L));
  };
  const pick = (L) => {
    if (L === last) return; last = L; haptic();
    S.ab = L; if (S.s === "pop") S.s = "az";
    clearTimeout(abcT); abcT = setTimeout(() => runSearch(true), 160);
  };
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault(); const L = at(e);
    if (L === S.ab) { S.ab = ""; last = ""; abcSync(true); runSearch(true); return; }
    abcDown = true; try { el.setPointerCapture(e.pointerId); } catch (x) {} show(L, e); pick(L);
  });
  el.addEventListener("pointermove", (e) => { if (!abcDown) return; const L = at(e); show(L, e); pick(L); });
  const up = () => { abcDown = false; last = ""; setTimeout(() => { const b = $("bxabub"); b && b.classList.remove("on"); }, 380); };
  el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  el.addEventListener("click", (e) => e.stopPropagation());
  return el;
}

// ------------------------------------------------------------------ 3 · Kitob sahifasi
function bookHTML(id) {
  const b = books.get(id);
  const top = `<div class="bx-top"><button class="bx-ib" data-act="back" aria-label="Orqaga">${I.back}</button><div class="bx-ttl"></div>
    <button class="bx-ib" data-act="share" aria-label="Ulashish">${I.share}</button>
    ${b ? `<button class="bx-ib${b.me && b.me.saved ? " on" : ""}" data-act="save" aria-label="Saqlash">${I.mark}</button>` : ""}</div>`;
  if (!b) return top + `<div class="bx-hero"><div class="cvw"><div class="cv big k0" style="opacity:.3"></div></div></div>${skel(2)}`;
  if (b.err) return top + `<div class="bx-empty"><div class="big">📕</div><b>Kitob topilmadi</b>U olib tashlangan bo'lishi mumkin.</div>`;
  const st = b.me || {};
  const started = st.pct > 0 && !st.done;
  const langName = {uz: "lotin", ru: "rus", en: "ingliz"}[b.l] || b.l;
  const aud = b.m === "audio", trs = b.tracks || [];
  const here = A.b && A.b.i === b.i;
  const ap = here ? {n: A.n} : st.ap || lsGet(`zk_bk_ap_${b.i}`, null);
  const listenTxt = here && !A.el.paused ? "Tinglanmoqda" : ap ? `Davom ettirish · ${ap.n}-bob` : aud ? `Tinglash · ${dur(b.au)}` : "Tinglash";
  let h = top + `<div class="bx-hero"><div class="cvw">${cover(b, "big")}</div><h1>${esc(b.t)}</h1>
    <p>${esc(b.a || "Muallif noma'lum")}${b.y ? " · " + b.y : ""} · ${esc(gname(b.g))}</p></div>
    <div class="bx-stats">${aud ? `<div><b>${trs.length || "—"}</b><i>bob</i></div>` : `<div><b>${b.m === "scan" ? b.p : b.p.toLocaleString("ru-RU")}</b><i>bet</i></div>`}<div><b>${(b.l || "").toUpperCase()}</b><i>${esc(langName)}</i></div>
      <div><b>${aud ? dur(b.au) : hours(b.p)}</b><i>${aud ? "tinglash" : "o'qish"}</i></div><div><b>${b.r ? String(b.r).replace(".", ",") : "—"}</b><i>${b.rn ? b.rn + " baho" : "baho"}</i></div></div>
    <div class="bx-cta">${aud ? `<button class="bx-btn pri" data-play="${b.i}">${I.head}${listenTxt}</button>`
      : `<button class="bx-btn pri" data-read="${b.i}">${I.book}${b.au ? (started ? `O'qish · ${Math.round(st.pct)}%` : "O'qish") : st.done ? "Qayta o'qish" : started ? `Davom ettirish · ${Math.round(st.pct)}%` : "O'qishni boshlash"}</button>
      ${b.au ? `<button class="bx-btn sec" data-play="${b.i}">${I.head}${here && !A.el.paused ? "Tinglanmoqda" : "Tinglash"}</button><button class="bx-btn sec ic" data-dl="${b.i}" aria-label="Yuklab olish">${I.dl}</button>`
        : `<button class="bx-btn sec" data-dl="${b.i}">${I.dl}Yuklab olish</button>`}`}</div>`;
  if (b.desc) h += `<div class="bx-desc${b._full ? "" : " cut"}"><p>${esc(b.desc)}</p>${b.desc.length > 220 && !b._full ? `<button data-act="more-desc">Batafsil</button>` : ""}</div>`;
  if ((st.pct > 0 || st.done || ap) && inTg) {
    h += `<div class="bx-h"><h2>Bahoyingiz</h2></div><div class="bx-stars">${[1, 2, 3, 4, 5].map((n) =>
      `<button class="${(st.stars || 0) >= n ? "on" : ""}" data-star="${n}" aria-label="${n} yulduz">★</button>`).join("")}</div>`;
  }
  if ((b.tr || []).length) {
    h += `<div class="bx-h"><h2>Boshqa tillarda</h2></div><div class="bx-tr">${b.tr.map((t) =>
      `<button data-book="${t.i}"><span class="bx-bdg l">${(t.l || "").toUpperCase()}</span><span>${esc(t.t)}</span></button>`).join("")}</div>`;
  }
  if (trs.length) {
    const cur = ap && ap.n, show = b._trkAll || trs.length <= 10 ? trs : trs.slice(0, 8);
    const playing = here && !A.el.paused;
    h += `<div class="bx-h"><h2>Audio boblar</h2><span class="bx-mute" style="font-size:13px">${trs.length} bob · ${dur(b.au)}</span></div><div class="bx-toc bx-trk">${show.map((t) =>
      `<button data-trk="${t.n}" class="${cur === t.n ? "cur" : ""}"><span class="n">${cur === t.n && playing ? '<i class="eq"><i></i><i></i><i></i></i>' : t.n}</span><span class="t">${esc(t.t)}</span><span class="d">${t.s ? fmtT(t.s) : ""}</span></button>`).join("")}
      ${show.length < trs.length ? `<button data-act="trk-all"><span class="n"></span><span class="t" style="color:var(--sun);font-weight:700">Hammasi (${trs.length})</span></button>` : ""}</div>`;
  }
  if (b._toc && !aud) {
    const list = b._toc.mode === "scan" ? (b._toc.toc || []) : (b._toc.toc || []);
    if (list.length > 1) {
      const show = b._tocAll ? list : list.slice(0, 8);
      h += `<div class="bx-h"><h2>Mundarija</h2><span class="bx-mute" style="font-size:13px">${list.length} bo'lim</span></div><div class="bx-toc">${show.map((c, n) =>
        `<button data-ch="${n}" class="${started && st.ch === n ? "cur" : ""}"><span class="n">${n + 1}</span><span class="t">${esc(c.t)}</span></button>`).join("")}
        ${list.length > 8 && !b._tocAll ? `<button data-act="toc-all"><span class="n"></span><span class="t" style="color:var(--sun);font-weight:700">Hammasi (${list.length})</span></button>` : ""}</div>`;
    }
  }
  h += `<div class="bx-lic">${I.shield}<span>${esc(b.lic || "Kutubxona ma'muriyati tomonidan joylangan")}</span></div>`;
  if (b.adm) h += `<button class="bx-adm-del" data-act="adm-del">🗑 Kitobni o'chirish <i>· faqat admin · ID ${b.i}</i></button>`;
  h += `<div style="height:12px"></div>`;
  return h;
}
async function openBook(id, push = true) {
  id = +id;
  if (push) stack.push({v: "book", id});
  render();
  try {
    const r = await api(`api/books/b/${id}`);
    if (r.ok) { const old = books.get(id); books.set(id, {...r.book, _toc: old && old._toc}); }
    else books.set(id, {i: id, err: true});
  } catch (e) { if (!books.get(id)) books.set(id, {i: id, err: true}); }
  if (isTop(id)) render(true);
  const b = books.get(id);
  if (b && !b.err && !b._toc) {
    if (b.m === "audio") b._toc = {toc: []};
    else try { b._toc = await (await fetch(`bk/${id}/toc.json`)).json(); } catch (e) { b._toc = {toc: []}; }
    if (isTop(id)) render(true);
  }
}
const isTop = (id) => { const t = stack[stack.length - 1]; return t && t.v === "book" && t.id === id; };
async function ensureBook(id) {
  let b = books.get(id);
  if (!b || b.err || b.me === undefined) {
    try { const r = await api(`api/books/b/${id}`); if (r.ok) { b = {...r.book, _toc: b && b._toc}; books.set(id, b); } } catch (e) {}
  }
  b = books.get(id);
  if (b && !b.err && !b._toc) { try { b._toc = await (await fetch(`bk/${id}/toc.json`)).json(); } catch (e) {} }
  return b && !b.err && b._toc ? b : null;
}

// ------------------------------------------------------------------ 6 · Javonim
const SHT = [["reading", "O'qilmoqda"], ["saved", "Saqlangan"], ["dl", "Yuklangan"], ["done", "O'qildi"]];
function shelfFilter(k) {
  const all = (me && me.books) || [];
  return k === "reading" ? all.filter((b) => b.pct > 0 && !b.done) : k === "saved" ? all.filter((b) => b.saved)
    : k === "dl" ? all.filter((b) => b.dl) : k === "audio" ? (me && me.audio) || [] : all.filter((b) => b.done);
}
function shelfHTML() {
  let h = `<div class="bx-hello" style="padding-top:18px"><h1>Javonim</h1></div>`;
  if (!inTg) return h + `<div class="bx-empty"><div class="big">🔖</div><b>Ilovani bot ichidan oching</b>Javon Telegram akkauntingizga bog'langan.</div>`;
  if (!me) return h + skel(3);
  const st = me.stats || {};
  const hrs = (st.secs || 0) / 3600;
  const tm = hrs >= 1 ? `${Math.round(hrs)} s` : `${Math.round((st.secs || 0) / 60)} daq`;
  h += `<div class="bx-st3"><div><b>${st.month || 0}</b><i>bu oy o'qildi</i></div><div><b>${tm}</b><i>o'qish vaqti</i></div>
    <div><b>${st.streak || 0} kun</b><i>ketma-ket${st.streak ? " 🔥" : ""}</i></div></div>`;
  const wk = st.week || [];
  const mx = Math.max(600, ...wk);
  const dn = ["Ya", "Du", "Se", "Ch", "Pa", "Ju", "Sh"];
  const today = new Date().getDay();
  h += `<div class="bx-week" aria-label="Haftalik o'qish">${wk.map((s, i) =>
    `<span class="${s >= 60 ? "on" : ""}" style="height:${Math.max(8, Math.round(s / mx * 100))}%"><i>${dn[(today - 6 + i + 7) % 7]}</i></span>`).join("")}</div>`;
  const tabs = (me.audio || []).length ? [SHT[0], ["audio", "Tinglanmoqda"], ...SHT.slice(1)] : SHT;
  if (shelfTab === "audio" && !(me.audio || []).length) shelfTab = "reading";
  h += `<div class="bx-tabs">${tabs.map(([k, t]) => `<button data-sht="${k}" class="${shelfTab === k ? "on" : ""}">${t} <i>· ${shelfFilter(k).length}</i></button>`).join("")}</div>`;
  const list = shelfFilter(shelfTab);
  if (shelfTab === "audio") {
    h += list.map((b) => `<div class="bx-sh"><button class="cvw" data-play="${b.i}" aria-label="Tinglash">${cover(b)}</button>
      <button class="mt" data-play="${b.i}"><b>${esc(b.t)}</b><div class="au">${esc(shortA(b.a))}${b.l ? " · " + b.l.toUpperCase() : ""}</div>
      <div class="pc">${I.head} ${b.n}-bob · ${fmtT(b.pt)} · ${ago(b.ts)}</div></button>
      <button class="dots" data-book="${b.i}" aria-label="Kitob haqida">⋯</button></div>`).join("");
  } else if (!list.length) {
    const msg = {reading: ["📖", "Hali hech narsa o'qimayapsiz", "Kutubxonadan kitob tanlang — qayerda to'xtaganingiz eslab qolinadi."],
      saved: ["🔖", "Saqlangan kitob yo'q", "Kitob sahifasidagi 🔖 belgisini bosing."], dl: ["⬇️", "Yuklangan kitob yo'q", "«Yuklab olish» — fayl chatga keladi, oflayn ham o'qiysiz."],
      done: ["🏁", "Hali tugatilgan kitob yo'q", "Birinchisini tugatsangiz — shu yerda paydo bo'ladi."]}[shelfTab];
    h += `<div class="bx-empty"><div class="big">${msg[0]}</div><b>${msg[1]}</b>${msg[2]}</div>`;
  } else {
    h += list.map((b) => `<div class="bx-sh"><button class="cvw" data-read="${b.i}" aria-label="O'qish">${cover(b)}</button>
      <button class="mt" data-read="${b.i}"><b>${esc(b.t)}</b><div class="au">${esc(shortA(b.a))}${b.l ? " · " + b.l.toUpperCase() : ""}</div>
      <div class="bar"><span style="width:${Math.max(b.pct > 0 ? 2 : 0, Math.round(b.pct))}%"></span></div>
      <div class="pc">${b.done ? "O'qildi ✓" : `${Math.round(b.pct)}%`} · ${ago(b.at)}${b.done ? "" : " o'qildi"}</div></button>
      <button class="dots" data-menu="${b.i}" aria-label="Amallar">⋯</button></div>`).join("");
  }
  const notes = me.notes || [];
  if (notes.length) {
    h += `<div class="bx-h"><h2>Belgilaganlarim</h2><span style="color:var(--sun);font-weight:700;font-size:13px">${notes.length} ta</span></div>` +
      notes.slice(0, 40).map((n) => `<button class="bx-note" data-gonote='${esc(JSON.stringify({i: n.i, ch: n.ch, q: n.q.slice(0, 80)}))}'>
        <q>${esc(n.q.length > 220 ? n.q.slice(0, 220) + "…" : n.q)}</q>${n.n ? `<div class="nn">💬 ${esc(n.n)}</div>` : ""}
        <small>${esc(n.t)} · ${n.ch + 1}-bo'lim</small></button>`).join("");
  }
  return h;
}
async function loadMe(force) {
  if (!inTg) return;
  if (!force && me && Date.now() - meAt < 20000) return;
  try { const r = await api("api/books/me"); if (r.ok) { me = r; meAt = Date.now(); if (opened && !stack.length && tab !== "search") render(true); } } catch (e) {}
}

// ------------------------------------------------------------------ pastdan oyna
function openSheet(html, onBind) {
  const sh = $("bxsheet");
  sh.innerHTML = `<div class="grip"></div>${html}`;
  sh.classList.add("on"); $("bxsbg").classList.add("on"); sheetOpen = true;
  if (onBind) onBind(sh);
  updateBack();
}
function closeSheet() {
  if (!sheetOpen) return;
  $("bxsheet").classList.remove("on"); $("bxsbg").classList.remove("on"); sheetOpen = false;
  updateBack();
}
function pickSheet(title, opts, cur, cb) {
  openSheet(`<h3>${esc(title)}</h3><div class="sub"></div>${opts.map(([k, t]) => `<button class="bx-opt${k === cur ? " on" : ""}" data-k="${esc(k)}">${esc(t)}${k === cur ? " ✓" : ""}</button>`).join("")}`,
    (sh) => sh.querySelectorAll("[data-k]").forEach((b) => { b.onclick = () => { closeSheet(); cb(b.dataset.k); }; }));
}

// ------------------------------------------------------------------ 8 · Yuklab olish
async function openDownload(id) {
  const b = await ensureBookLite(id); if (!b) { toast("⚠️ Kitob topilmadi"); return; }
  const fm = (b.f || []).filter((f) => FMT[f]);
  if (!fm.length) { toast("Bu kitobni yuklab bo'lmaydi"); return; }
  let pick = lsGet("zk_bk_fmt", "epub"); if (!fm.includes(pick)) pick = fm[0];
  const draw = (sh, state = "") => {
    sh.innerHTML = `<div class="grip"></div><h3>Yuklab olish</h3><div class="sub">${esc(b.t)}${b.a ? " · " + esc(shortA(b.a)) : ""}${b.y ? " · " + b.y : ""}</div>
      ${fm.map((f) => `<button class="bx-fmt${f === pick ? " on" : ""}" data-f="${f}"><span class="ic">${f.toUpperCase()}</span><span class="mt"><b>${FMT[f][0]}</b>
        <i>${b.s && b.s[f] ? mb(b.s[f]) + " · " : ""}${FMT[f][1]}</i></span><span class="rd"></span></button>`).join("")}
      <button class="bx-btn pri" style="width:100%;margin-top:6px" data-act="send" ${state === "sending" ? "disabled" : ""}>${I.dl}${state === "sending" ? "Yuborilmoqda…" : state === "ok" ? "Botga o'tish" : "Chatga yuborish"}</button>
      ${state === "ok" ? `<div class="bx-okmsg">${I.ok}Fayl bot chatiga yuborildi — oflayn ham o'qiysiz</div>` : ""}
      ${state === "queued" ? `<div class="bx-okmsg">${I.clock}Navbatda — bir necha soniyada chatga keladi</div>` : ""}`;
    sh.querySelectorAll("[data-f]").forEach((x) => { x.onclick = () => { pick = x.dataset.f; lsSet("zk_bk_fmt", pick); haptic(); draw(sh, ""); }; });
    sh.querySelector('[data-act="send"]').onclick = async () => {
      if (state === "ok" || state === "queued") { closeSheet(); if (inTg && botName) tg.openTelegramLink(`https://t.me/${botName}`); return; }
      if (!inTg) { toast("Ilovani bot ichidan oching"); return; }
      draw(sh, "sending");
      let r;
      try { r = await api("api/books/send", {i: b.i, f: pick}); } catch (e) { r = {ok: false, error: "net"}; }
      if (r.ok) { haptic("ok"); draw(sh, r.queued ? "queued" : "ok"); meAt = 0; return; }
      haptic("err");
      if (r.error === "need_start") { closeSheet(); toast("🤖 Avval botni ishga tushiring"); if (botName) tg.openTelegramLink(`https://t.me/${botName}?start=books`); return; }
      const msg = {rate: `⏳ Soatlik limit tugadi. ${Math.ceil((r.retry || 3600) / 60)} daqiqadan keyin urinib ko'ring`,
        no_format: "Bu format hozir tayyor emas — boshqasini tanlang", busy: "⏳ Hozir band — biroz keyin urinib ko'ring", net: "📶 Internet bilan muammo"};
      toast(msg[r.error] || "⚠️ Yuborib bo'lmadi. Birozdan keyin urinib ko'ring", 3400);
      draw(sh, "");
    };
  };
  openSheet("", (sh) => draw(sh));
}
async function ensureBookLite(id) {
  let b = books.get(+id);
  if (b && !b.err) return b;
  for (const src of [S.items || [], ...(stack.map((v) => v.items || [])), ...((home && home.shelves) || []).map((s) => s.items), (me && me.books) || []]) {
    const x = src.find && src.find((y) => y.i === +id); if (x) return x;
  }
  try { const r = await api(`api/books/b/${id}`); if (r.ok) { books.set(+id, r.book); return r.book; } } catch (e) {}
  return null;
}

// ================================================================== 4 · O'QUVCHI
const RS = Object.assign({fs: 18, th: "sepia", ff: "lora", lh: 1, wake: false, al: "auto"}, lsGet("zk_bk_set", {}));
const FF = {lora: "Lora,PTSerif,Georgia,serif", man: "Man,-apple-system,sans-serif", klassik: "PTSerif,Georgia,'Times New Roman',serif"};
const LH = [1.45, 1.65, 1.9];
const THC = {light: "#FFFFFF", sepia: "#F6EFDF", slate: "#26302C", night: "#121110"};
const R = {on: false, b: null, toc: [], ch: 0, page: 0, pages: 1, data: null, loading: false, W: 0, scan: false, tot: 1,
  activeSecs: 0, lastAct: 0, saveT: 0, hb: 0, wake: null, scanObs: null, curScan: 1, tick: 0};

function rdEl() {
  let el = $("bxrd");
  if (el) return el;
  el = document.createElement("section");
  el.className = "bx-rd"; el.id = "bxrd"; el.hidden = true;
  el.setAttribute("role", "dialog"); el.setAttribute("aria-label", "O'quvchi");
  el.innerHTML = `<div class="rd-top"><button class="rd-ib" data-r="close" aria-label="Yopish">${I.back}</button>
      <div class="ttl"><b id="rdt"></b><i id="rdc"></i></div>
      <button class="rd-ib" data-r="toc" aria-label="Mundarija">${I.toc}</button><button class="rd-ib aa" data-r="set" aria-label="Sozlamalar">Aa</button></div>
    <div class="rd-page" id="rdpage"><div class="rd-flow" id="rdflow"><div class="rd-text" id="rdtext"></div></div><div class="rd-load" id="rdload" hidden><div class="rd-spin"></div></div></div>
    <div class="rd-foot"><div class="rd-bar"><input type="range" id="rdbar" min="0" max="1000" value="0" aria-label="Kitobdagi joy"></div>
      <div class="rd-info"><span id="rdpg"></span><span id="rdleft"></span></div></div>
    <div class="rd-sel" id="rdsel" hidden><button data-s="hl">${I.pen}Belgilash</button><button data-s="copy">${I.copy}Nusxa</button><button data-s="note">${I.note}Izoh</button></div>`;
  document.body.appendChild(el);
  bindReader(el);
  return el;
}
function applySettings() {
  const el = rdEl();
  el.classList.remove("t-light", "t-sepia", "t-slate", "t-night"); el.classList.add("t-" + RS.th);
  el.style.setProperty("--fs", RS.fs + "px"); el.style.setProperty("--lh", LH[RS.lh] || 1.65); el.style.setProperty("--ff", FF[RS.ff] || FF.lora);
  const lang = (R.b && R.b.l) || "uz";
  const t = $("rdtext"); if (t) t.lang = lang;
  // o'zbek tilida brauzerda bo'g'in ko'chirish yo'q — ikki tomonga tekislash katta bo'shliqlar qoldiradi
  el.style.setProperty("--al", RS.al === "auto" ? (lang === "uz" ? "left" : "justify") : RS.al);
  try { tg.setHeaderColor(THC[RS.th]); tg.setBackgroundColor(THC[RS.th]); if (tg.setBottomBarColor) tg.setBottomBarColor(THC[RS.th]); } catch (e) {}
  lsSet("zk_bk_set", RS);
}
function chChars(n) { return (R.toc[n] && R.toc[n].c) || 1; }
function curPct() {
  if (R.scan) return R.tot ? Math.min(100, (R.curScan - 1) / Math.max(1, R.tot - 1) * 100) : 0;
  let before = 0; for (let i = 0; i < R.ch; i++) before += chChars(i);
  const off = R.pages > 1 ? R.page / (R.pages - 1) : (R.ch === R.toc.length - 1 ? 1 : 0);
  return Math.min(100, (before + off * chChars(R.ch)) / R.tot * 100);
}
function curOff() { return R.scan ? 0 : (R.pages > 1 ? R.page / (R.pages - 1) : 0); }

async function openReader(id, ch, off) {
  const b = await ensureBook(+id);
  if (!b) { toast("⚠️ Kitobni ochib bo'lmadi"); return; }
  const el = rdEl();
  R.on = true; R.b = b; R.scan = b._toc.mode === "scan";
  R.toc = b._toc.toc || [];
  R.tot = R.scan ? (b._toc.pages || b.p || 1) : R.toc.reduce((s, c) => s + (c.c || 1), 0) || 1;
  // joy: server yoki shu qurilma — qaysi biri yangi bo'lsa
  const st = b.me || {};
  const loc = lsGet(`zk_bk_pos_${b.i}`, null);
  let c0 = st.ch || 0, o0 = st.off || 0;
  if (loc && (!st.pct || loc.pct >= st.pct - 0.5)) { c0 = loc.ch; o0 = loc.off; }
  if (ch !== undefined && ch !== null) { c0 = ch; o0 = off || 0; }
  if (st.done && ch === undefined) { c0 = 0; o0 = 0; }
  el.hidden = false; document.body.classList.add("rd-on");
  el.classList.remove("hide");
  $("rdt").textContent = b.t;
  applySettings();
  try { tg.disableVerticalSwipes && tg.disableVerticalSwipes(); } catch (e) {}
  R.activeSecs = 0; R.lastAct = Date.now();
  clearInterval(R.hb); R.hb = setInterval(heartbeat, 1000);
  if (RS.wake) wakeOn();
  updateBack();
  if (R.scan) openScan(c0, o0); else await loadChapter(Math.min(Math.max(0, c0), R.toc.length - 1), o0);
}
function cleanBookText(s) {
  if (!s) return "";
  let t = String(s);
  const map = {
    "â€™": "'", "â€˜": "'", "Ã¢â‚¬â„¢": "'", "Ã¢â‚¬Å“": "“", "Ã¢â‚¬Â": "”",
    "â€œ": "“", "â€": "”", "â€”": " — ", "â€“": " – ", "Ã¢â‚¬â€": " — ",
    "Ã¢â‚¬â€“": " – ", "â€¦": "…", "Ã¢â‚¬Â¦": "…", "Ã‚Â": " ", "Â ": " ", "Â": "",
    "\ufeff": "", "\ufffd": "", "\u00ad": ""
  };
  for (const [bad, good] of Object.entries(map)) {
    if (t.includes(bad)) t = t.replaceAll(bad, good);
  }
  t = t.replace(/o[‘`ʻʼ’´]/g, "o'").replace(/O[‘`ʻʼ’´]/g, "O'")
       .replace(/g[‘`ʻʼ’´]/g, "g'").replace(/G[‘`ʻʼ’´]/g, "G'")
       .replace(/(\b[A-Za-zА-Яа-яЎўҒғҚқҲҳ]+)-[ \t\r\n]+([A-Za-zА-Яа-яЎўҒғҚқҲҳ]+\b)/gu, "$1$2");
  return t;
}

async function loadChapter(n, where) {
  R.loading = true; $("rdload").hidden = false;
  let data;
  try { data = await (await fetch(`bk/${R.b.i}/c${n + 1}.json`)).json(); }
  catch (e) { $("rdload").hidden = true; R.loading = false; toast("📶 Bobni yuklab bo'lmadi"); return; }
  if (!R.on) return;
  R.ch = n; R.data = data;
  const notes = ((R.b.me && R.b.me.notes) || []).filter((x) => x.ch === n);
  let first = true;
  const used = new Set();
  const paras = (data.p || []).map((p, pi) => {
    if (typeof p !== "string") return `<h3 data-pi="${pi}">${esc(cleanBookText(p.h))}</h3>`;
    const cleanP = cleanBookText(p);
    let html = esc(cleanP);
    for (const nt of notes) {
      if (used.has(nt.id) || (nt.pos >= 0 && nt.pos !== pi)) continue;
      const q = esc(cleanBookText(nt.q.trim()));
      const k = q ? html.indexOf(q) : -1;
      if (k >= 0) { html = html.slice(0, k) + `<mark class="${nt.n ? "n" : ""}">${q}</mark>` + html.slice(k + q.length); used.add(nt.id); }
    }
    const cls = first && /^[\p{L}«"„]/u.test(cleanP) ? "f dc" : first ? "f" : "";
    first = false;
    return `<p data-pi="${pi}"${cls ? ` class="${cls}"` : ""}>${html}</p>`;
  }).join("");
  const last = n === R.toc.length - 1;
  const cleanTitle = cleanBookText(data.t || "");
  $("rdtext").innerHTML = `<div class="ch-h"><small>${n + 1}-BO'LIM · ${R.toc.length} DAN</small><b>${esc(cleanTitle)}</b></div>${paras}
    ${last ? `<div class="end">— Tamom —<br><br>${inTg ? `Kitob sizga yoqdimi?<div class="bx-stars" style="margin-top:6px">${[1, 2, 3, 4, 5].map((s) => `<button data-rstar="${s}" style="color:var(--pacc)">☆</button>`).join("")}</div>` : ""}</div>` : ""}`;
  $("rdc").textContent = cleanTitle;

  await layout(where);
  $("rdload").hidden = true; R.loading = false;
}
async function layout(where) {
  const page = $("rdpage"), text = $("rdtext"), flow = $("rdflow");
  const W = page.clientWidth, H = page.clientHeight;
  const padX = W > 700 ? Math.round((W - 640) / 2) : 22;
  R.W = W;
  text.style.cssText = `width:${W}px;height:${H}px;padding:20px ${padX}px 22px;box-sizing:border-box;column-width:${W - 2 * padX}px;column-gap:${2 * padX}px`;
  try { await document.fonts.ready; } catch (e) {}
  R.pages = Math.max(1, Math.round(text.scrollWidth / W));
  if (where === "end") R.page = R.pages - 1;
  else if (typeof where === "number") R.page = Math.min(R.pages - 1, Math.round(where * (R.pages - 1)));
  else R.page = Math.min(R.page, R.pages - 1);
  flow.classList.remove("anim"); flow.style.transform = `translateX(${-R.page * W}px)`;
  info();
}
function go(dir) {
  if (R.loading || R.scan) return;
  hideSel();
  if (dir > 0) {
    if (R.page < R.pages - 1) R.page++;
    else if (R.ch < R.toc.length - 1) { loadChapter(R.ch + 1, 0).then(saveSoon); return; }
    else { toast("🏁 Kitob tugadi"); return; }
  } else {
    if (R.page > 0) R.page--;
    else if (R.ch > 0) { loadChapter(R.ch - 1, "end").then(saveSoon); return; }
    else return;
  }
  const flow = $("rdflow");
  if (!reduced()) flow.classList.add("anim");
  flow.style.transform = `translateX(${-R.page * R.W}px)`;
  info(); saveSoon(); haptic();
}
function info() {
  const pct = curPct();
  const total = R.b.p || 1;
  const gp = R.scan ? R.curScan : Math.max(1, Math.min(total, Math.round(pct / 100 * total)));
  $("rdpg").textContent = `${gp} / ${total} bet`;
  if (!R.scan) {
    const left = Math.max(0, Math.round((1 - curOff()) * chChars(R.ch) / 1000));
    $("rdleft").textContent = R.ch === R.toc.length - 1 && R.page === R.pages - 1 ? "Oxirgi bet" : left ? `Bob oxirigacha ${left} daqiqa` : "Bob tugayapti";
  } else $("rdleft").textContent = `${Math.round(pct)}%`;
  const bar = $("rdbar"); if (!bar._drag) { bar.value = Math.round(pct * 10); bar.style.setProperty("--p", pct + "%"); }
}
function locate(pct) {
  if (R.scan) return {page: Math.max(1, Math.round(pct / 100 * (R.tot - 1)) + 1)};
  let target = pct / 100 * R.tot, acc = 0;
  for (let i = 0; i < R.toc.length; i++) {
    const c = chChars(i);
    if (acc + c >= target || i === R.toc.length - 1) return {ch: i, off: Math.min(1, Math.max(0, (target - acc) / c))};
    acc += c;
  }
  return {ch: 0, off: 0};
}
function saveSoon() { clearTimeout(R.saveT); R.saveT = setTimeout(() => save(false), 2500); posLocal(); }
function posLocal() { if (R.b) lsSet(`zk_bk_pos_${R.b.i}`, {ch: R.scan ? R.curScan - 1 : R.ch, off: curOff(), pct: curPct(), t: Date.now()}); }
async function save(final) {
  if (!R.b || !inTg) return;
  const body = {i: R.b.i, ch: R.scan ? R.curScan - 1 : R.ch, off: curOff(), pct: curPct(), secs: Math.round(R.activeSecs)};
  R.activeSecs = 0;
  if (R.b.me) Object.assign(R.b.me, {ch: body.ch, off: body.off, pct: body.pct});
  try {
    await fetch("api/books/progress", {method: "POST", keepalive: !!final, body: JSON.stringify(body),
      headers: {"Content-Type": "application/json", "X-Init-Data": tg.initData}});
  } catch (e) {}
}
function heartbeat() {
  if (!R.on || document.hidden) return;
  if (Date.now() - R.lastAct < 120000) R.activeSecs++;
  if (++R.tick % 45 === 0 && R.activeSecs > 5) save(false);
}
function closeReader() {
  if (!R.on) return;
  posLocal(); save(true);
  R.on = false; clearInterval(R.hb); clearTimeout(R.saveT); hideSel(); wakeOff();
  if (R.scanObs) { R.scanObs.disconnect(); R.scanObs = null; }
  rdEl().hidden = true; document.body.classList.remove("rd-on");
  $("rdtext").innerHTML = ""; const sc = $("rdscan"); if (sc) sc.remove();
  try { tg.enableVerticalSwipes && tg.enableVerticalSwipes(); tg.setHeaderColor("#0D2420"); tg.setBackgroundColor("#0D2420"); if (tg.setBottomBarColor) tg.setBottomBarColor("#0B1F1B"); } catch (e) {}
  meAt = 0; loadMe(true);
  if (stack.length) render(true);
  updateBack();
}

// rasmli (skanerlangan) kitob
function openScan(c0, o0) {
  const page = $("rdpage");
  let sc = $("rdscan"); if (sc) sc.remove();
  sc = document.createElement("div"); sc.className = "rd-scan"; sc.id = "rdscan";
  const n = R.tot;
  const start = Math.max(1, Math.min(n, (c0 || 0) + 1));
  sc.innerHTML = Array.from({length: n}, (_, i) => `<img data-n="${i + 1}" alt="${i + 1}-bet" ${Math.abs(i + 1 - start) < 3 ? `src="bk/${R.b.i}/s${i + 1}.webp"` : ""}>`).join("");
  sc.addEventListener("error", (e) => {
    const im = e.target;
    if (im && im.tagName === "IMG" && im.dataset.n && !im.dataset.r) { im.dataset.r = "1"; im.src = `api/books/page/${R.b.i}/${im.dataset.n}`; }
  }, true);
  page.appendChild(sc);
  $("rdtext").innerHTML = ""; $("rdc").textContent = "Skanerlangan nashr";
  sc.addEventListener("load", (e) => { if (e.target.tagName === "IMG") e.target.classList.add("ok"); }, true);
  R.scanObs = new IntersectionObserver((ents) => {
    for (const en of ents) {
      const img = en.target;
      if (en.isIntersecting && !img.getAttribute("src")) img.src = `bk/${R.b.i}/s${img.dataset.n}.webp`;
      // sahifa hali tayyorlanmagan (yangi kitob) — server PDF dan yasab beradi
    }
  }, {root: sc, rootMargin: "200% 0px"});
  let sT = 0;
  sc.addEventListener("scroll", () => {
    R.lastAct = Date.now();
    if (sT) return;
    sT = setTimeout(() => {
      sT = 0;
      const y = sc.scrollTop + sc.clientHeight * 0.35;
      let cur = 1;
      for (const im of sc.children) { if (im.offsetTop <= y) cur = +im.dataset.n; else break; }
      if (cur !== R.curScan) { R.curScan = cur; info(); saveSoon(); }
    }, 120);
  }, {passive: true});
  sc.querySelectorAll("img").forEach((im) => R.scanObs.observe(im));
  R.curScan = start;
  requestAnimationFrame(() => { const t = sc.querySelector(`img[data-n="${start}"]`); if (t) sc.scrollTop = t.offsetTop; info(); });
  void o0;
}
function scanTo(p) { const sc = $("rdscan"); const t = sc && sc.querySelector(`img[data-n="${p}"]`); if (t) { sc.scrollTop = t.offsetTop; R.curScan = p; info(); saveSoon(); } }

// belgilash (matn tanlanganda)
function selRange() {
  const s = window.getSelection();
  if (!s || s.isCollapsed || !s.rangeCount) return null;
  const r = s.getRangeAt(0);
  if (!$("rdtext").contains(r.commonAncestorContainer)) return null;
  const t = s.toString().replace(/\s+/g, " ").trim();
  const pe = (r.startContainer.nodeType === 1 ? r.startContainer : r.startContainer.parentElement).closest("[data-pi]");
  return t.length >= 2 ? {r, t, pos: pe ? +pe.dataset.pi : -1} : null;
}
function showSel() {
  const x = selRange(); const box = $("rdsel");
  if (!x || !R.on) { box.hidden = true; return; }
  const rc = x.r.getBoundingClientRect();
  box.hidden = false;
  box.style.left = Math.min(window.innerWidth - 120, Math.max(120, rc.left + rc.width / 2)) + "px";
  box.style.top = Math.max(70, rc.top - 10) + "px";
}
function hideSel() { const b = $("rdsel"); if (b) b.hidden = true; }
async function addNote(q, note, pos = -1) {
  if (!inTg) { toast("Ilovani bot ichidan oching"); return; }
  const r = await api("api/books/note", {i: R.b.i, ch: R.ch, q, n: note || "", pos});
  if (r.ok) {
    haptic("ok"); toast(note ? "💬 Izoh saqlandi" : "🖍 Belgilandi");
    R.b.me = R.b.me || {notes: []}; (R.b.me.notes = R.b.me.notes || []).push({id: r.id, ch: R.ch, pos, q, n: note || ""});
    const off = curOff(); window.getSelection().removeAllRanges(); await loadChapter(R.ch, off); meAt = 0;
  } else toast("⚠️ Saqlab bo'lmadi");
}

// mundarija va belgilar
function openTOC() {
  const notes = ((R.b.me && R.b.me.notes) || []);
  const draw = (sh, t) => {
    let body;
    if (t === "n") {
      body = notes.length ? notes.map((n) => `<button class="bx-note" style="width:100%;margin:0 0 8px" data-goch="${n.ch}"><q>${esc(n.q.slice(0, 200))}</q>
        ${n.n ? `<div class="nn">💬 ${esc(n.n)}</div>` : ""}<small>${n.ch + 1}-bo'lim · <span data-delnote="${n.id}" style="color:var(--bad)">o'chirish</span></small></button>`).join("")
        : `<div class="bx-empty" style="padding:24px 8px"><b>Belgi yo'q</b>Matnni bosib turing va «Belgilash»ni tanlang.</div>`;
    } else if (R.scan) {
      body = (R.toc || []).map((c) => `<button class="bx-opt" data-gopage="${c.s}">${esc(c.t)}<span class="bx-mute" style="margin-left:auto;font-size:13px">${c.s}-bet</span></button>`).join("");
    } else {
      body = R.toc.map((c, n) => `<button class="bx-opt${n === R.ch ? " on" : ""}" data-goch="${n}"><span class="bx-mute" style="width:26px;font-size:13px">${n + 1}</span>${esc(c.t)}</button>`).join("");
    }
    sh.innerHTML = `<div class="grip"></div><div class="bx-tabs" style="padding:0 0 0;margin-bottom:8px"><button class="${t !== "n" ? "on" : ""}" data-t="c">Mundarija</button>
      <button class="${t === "n" ? "on" : ""}" data-t="n">Belgilar <i>· ${notes.length}</i></button></div>${body}`;
    sh.querySelectorAll("[data-t]").forEach((x) => { x.onclick = () => draw(sh, x.dataset.t); });
    sh.querySelectorAll("[data-goch]").forEach((x) => { x.onclick = (e) => {
      const del = e.target.closest("[data-delnote]");
      if (del) { e.stopPropagation(); delNote(+del.dataset.delnote).then(() => draw(sh, "n")); return; }
      closeSheet(); loadChapter(+x.dataset.goch, 0).then(saveSoon); }; });
    sh.querySelectorAll("[data-gopage]").forEach((x) => { x.onclick = () => { closeSheet(); scanTo(+x.dataset.gopage); }; });
    const cur = sh.querySelector(".bx-opt.on"); if (cur) cur.scrollIntoView({block: "center"});
  };
  openSheet("", (sh) => draw(sh, "c"));
}
async function delNote(id) {
  const r = await api("api/books/note", {del: id});
  if (r.ok && R.b && R.b.me) { R.b.me.notes = R.b.me.notes.filter((n) => n.id !== id); if (!R.scan) loadChapter(R.ch, curOff()); }
  if (me) me.notes = (me.notes || []).filter((n) => n.id !== id);
}

// 5 · o'qish sozlamalari
function openSettings() {
  const draw = (sh) => {
    sh.innerHTML = `<div class="grip"></div><h3 style="margin-bottom:6px">O'qish sozlamalari</h3>
      <div class="st-row"><span>Matn hajmi</span><div class="st-seg"><button data-fs="-1" aria-label="Kichikroq" style="font-size:13px">A</button><span class="val">${RS.fs}</span><button data-fs="1" aria-label="Kattaroq" style="font-size:19px">A</button></div></div>
      <div class="st-row"><span>Fon</span><div class="st-th">${[["light", "#fff", "#1F1A14"], ["sepia", "#F6EFDF", "#2A2117"], ["slate", "#26302C", "#E7E2D6"], ["night", "#121110", "#F0B43C"]].map(([k, bg, fg]) =>
        `<button class="${RS.th === k ? "on" : ""}" data-th="${k}" style="background:${bg};color:${fg}" aria-label="${k}">Aa</button>`).join("")}</div></div>
      <div class="st-row"><span>Shrift</span><div class="st-seg">${[["lora", "Lora", "Lora,serif"], ["man", "Manrope", "Man,sans-serif"], ["klassik", "Klassik", "PTSerif,serif"]].map(([k, t, f]) =>
        `<button class="${RS.ff === k ? "on" : ""}" data-ff="${k}" style="font-family:${f}">${t}</button>`).join("")}</div></div>
      <div class="st-row"><span>Qator oralig'i</span><div class="st-seg st-lh">${[0, 1, 2].map((i) =>
        `<button class="${RS.lh === i ? "on" : ""}" data-lh="${i}" aria-label="Oraliq ${i + 1}"><span style="margin-bottom:${2 + i * 2}px"></span><span style="margin-bottom:${2 + i * 2}px"></span><span></span></button>`).join("")}</div></div>
      <div class="st-row"><span>Tekislash</span><div class="st-seg">${[["auto", "Avto"], ["left", "Chap"], ["justify", "Ikki tomon"]].map(([k, t]) =>
        `<button class="${RS.al === k ? "on" : ""}" data-al="${k}">${t}</button>`).join("")}</div></div>
      ${"wakeLock" in navigator ? `<div class="st-row"><span>Ekran o'chmasin</span><button class="st-sw${RS.wake ? " on" : ""}" data-wake role="switch" aria-checked="${RS.wake}" aria-label="Ekran o'chmasin"></button></div>` : ""}`;
    sh.querySelectorAll("[data-fs]").forEach((x) => { x.onclick = () => { RS.fs = Math.max(13, Math.min(30, RS.fs + +x.dataset.fs)); relayout(); draw(sh); }; });
    sh.querySelectorAll("[data-th]").forEach((x) => { x.onclick = () => { RS.th = x.dataset.th; applySettings(); draw(sh); }; });
    sh.querySelectorAll("[data-ff]").forEach((x) => { x.onclick = () => { RS.ff = x.dataset.ff; relayout(); draw(sh); }; });
    sh.querySelectorAll("[data-lh]").forEach((x) => { x.onclick = () => { RS.lh = +x.dataset.lh; relayout(); draw(sh); }; });
    sh.querySelectorAll("[data-al]").forEach((x) => { x.onclick = () => { RS.al = x.dataset.al; relayout(); draw(sh); }; });
    const w = sh.querySelector("[data-wake]"); if (w) w.onclick = () => { RS.wake = !RS.wake; RS.wake ? wakeOn() : wakeOff(); applySettings(); draw(sh); };
  };
  openSheet("", draw);
}
function relayout() { applySettings(); if (!R.scan && R.on && R.data) { const off = curOff(); layout(off); } }
async function wakeOn() { try { if ("wakeLock" in navigator && !R.wake) { R.wake = await navigator.wakeLock.request("screen"); R.wake.addEventListener("release", () => { R.wake = null; }); } } catch (e) {} }
function wakeOff() { try { if (R.wake) R.wake.release(); } catch (e) {} R.wake = null; }

function bindReader(el) {
  let sx = 0, sy = 0, st = 0, moved = false;
  const page = el.querySelector("#rdpage");
  page.addEventListener("pointerdown", (e) => { sx = e.clientX; sy = e.clientY; st = Date.now(); moved = false; R.lastAct = Date.now(); });
  page.addEventListener("pointermove", (e) => { if (Math.abs(e.clientX - sx) > 12 || Math.abs(e.clientY - sy) > 12) moved = true; });
  page.addEventListener("pointerup", (e) => {
    if (R.scan || R.loading) return;
    if (selRange()) { showSel(); return; }
    const dx = e.clientX - sx, dy = e.clientY - sy;
    if (moved && Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.3 && Date.now() - st < 700) { go(dx < 0 ? 1 : -1); return; }
    if (moved || Date.now() - st > 600) return;
    const star = e.target.closest("[data-rstar]");
    if (star) { rateBook(+star.dataset.rstar); return; }
    const x = e.clientX / page.clientWidth;
    if (x < 0.3) go(-1); else if (x > 0.7) go(1); else { el.classList.toggle("hide"); hideSel(); }
  });
  document.addEventListener("selectionchange", () => { if (R.on && !R.scan) { clearTimeout(showSel._t); showSel._t = setTimeout(showSel, 120); } });
  el.querySelector("#rdsel").addEventListener("pointerdown", (e) => e.preventDefault());
  el.querySelector("#rdsel").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-s]"); const x = selRange(); if (!b || !x) return;
    hideSel();
    if (b.dataset.s === "copy") {
      try { await navigator.clipboard.writeText(x.t); } catch (er) { try { document.execCommand("copy"); } catch (e2) {} }
      toast("📋 Nusxa olindi"); window.getSelection().removeAllRanges(); return;
    }
    if (b.dataset.s === "hl") { addNote(x.t, "", x.pos); return; }
    const q = x.t, qpos = x.pos;
    openSheet(`<h3>Izoh</h3><div class="sub">Belgilangan parchaga fikringizni yozing</div><div class="q">${esc(q.slice(0, 300))}</div>
      <textarea id="bxnote" maxlength="2000" placeholder="Fikringiz…"></textarea>
      <button class="bx-btn pri" style="width:100%;margin-top:10px" id="bxnotesave">Saqlash</button>`, (sh) => {
      const ta = sh.querySelector("#bxnote"); setTimeout(() => ta.focus(), 250);
      sh.querySelector("#bxnotesave").onclick = () => { closeSheet(); addNote(q, ta.value.trim(), qpos); };
    });
  });
  el.querySelector(".rd-top").addEventListener("click", (e) => {
    const b = e.target.closest("[data-r]"); if (!b) return;
    if (b.dataset.r === "close") closeReader(); else if (b.dataset.r === "toc") openTOC(); else openSettings();
  });
  const bar = el.querySelector("#rdbar");
  bar.addEventListener("input", () => {
    bar._drag = true; const pct = bar.value / 10; bar.style.setProperty("--p", pct + "%");
    const total = R.b.p || 1; $("rdpg").textContent = `${Math.max(1, Math.round(pct / 100 * total))} / ${total} bet`;
  });
  bar.addEventListener("change", () => {
    bar._drag = false; const loc = locate(bar.value / 10);
    if (R.scan) scanTo(loc.page); else if (loc.ch === R.ch) layout(loc.off).then(saveSoon); else loadChapter(loc.ch, loc.off).then(saveSoon);
  });
  document.addEventListener("keydown", (e) => {
    if (!R.on || sheetOpen) return;
    if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") { e.preventDefault(); go(1); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); go(-1); }
    else if (e.key === "Escape") closeReader();
  });
  let rT = 0;
  window.addEventListener("resize", () => { if (!R.on || R.scan) return; clearTimeout(rT); const off = curOff(); rT = setTimeout(() => layout(off), 150); });
  document.addEventListener("visibilitychange", () => { if (document.hidden && R.on) { posLocal(); save(true); } else if (!document.hidden && R.on && RS.wake) wakeOn(); });
}
async function rateBook(n) {
  if (!R.b || !inTg) return;
  const r = await api("api/books/shelf", {i: R.b.i, stars: n, done: true});
  if (r.ok) { haptic("ok"); toast(`⭐ Rahmat! ${n} yulduz`); document.querySelectorAll("[data-rstar]").forEach((x) => { x.textContent = +x.dataset.rstar <= n ? "★" : "☆"; });
    if (R.b.me) Object.assign(R.b.me, {stars: n, done: true}); meAt = 0; }
}

// ================================================================== 9 · AUDIOKITOB PLEERI
// Fayllar: LibriVox (archive.org) yoki serverdagi bk/{id}/a{n}.mp3. Joy: har 15 soniyada + pauzada (Redis + shu qurilma).
const SPEEDS = [0.8, 1, 1.25, 1.5, 1.75, 2];
const SLEEPS = [["0", "O'chirilgan"], ["15", "15 daqiqa"], ["30", "30 daqiqa"], ["45", "45 daqiqa"], ["60", "1 soat"], ["end", "Bob oxirida"]];
const A = {b: null, tracks: [], n: 1, el: null, full: false, drag: false, spd: +lsGet("zk_bk_spd", 1) || 1, sleep: "0", sleepAt: 0, sleepT: 0,
  heard: 0, lastT: -1, saveT: 0, err: false, wait: false, seekTo: 0};
const trkUrl = (u) => String(u || "").replace(/^http:\/\//, "https://");
const curTrk = () => A.tracks.find((t) => t.n === A.n) || A.tracks[0];
const trkIdx = () => Math.max(0, A.tracks.indexOf(curTrk()));

function au() {
  if (A.el) return A.el;
  const el = A.el = new Audio();
  el.preload = "metadata";
  el.addEventListener("timeupdate", onATime);
  el.addEventListener("play", () => { A.lastT = -1; apSync(); });
  el.addEventListener("playing", () => { A.wait = false; A.err = false; apSync(); });
  el.addEventListener("waiting", () => { A.wait = true; apSync(); });
  el.addEventListener("pause", () => { A.wait = false; apSave(); apSync(); });
  el.addEventListener("loadedmetadata", () => {
    if (A.seekTo > 1 && A.seekTo < el.duration - 2) { try { el.currentTime = A.seekTo; } catch (e) {} }
    A.seekTo = 0; el.playbackRate = A.spd; apSync();
  });
  el.addEventListener("ended", () => {
    const i = trkIdx(), last = i >= A.tracks.length - 1;
    if (!last) {
      const nx = A.tracks[i + 1].n;
      if (A.sleep === "end") { setSleep("0"); A.n = nx; apSave(); loadTrack(nx, 0, false); toast("🌙 Bob tugadi — tinglash to'xtatildi"); return; }
      loadTrack(nx, 0, true); return;
    }
    setSleep("0"); apSave(); haptic("ok"); toast("🎧 Audiokitob oxiriga yetdingiz", 3200); apSync();
  });
  el.addEventListener("error", () => {
    if (!el.getAttribute("src")) return;
    A.err = true; A.wait = false; apSync(); toast("⚠️ Audio yuklanmadi — internetni tekshirib, ▶ ni bosing", 3400);
  });
  return el;
}
function onATime() {
  const el = A.el, t = el.currentTime;
  if (!el.paused && A.lastT >= 0) { const d = t - A.lastT; if (d > 0 && d < 4) A.heard += d / (el.playbackRate || 1); }
  A.lastT = t;
  if (!el.paused && Date.now() - A.saveT > 15000) apSave();
  if (A.sleep !== "0" && A.sleep !== "end" && A.sleepAt && Date.now() >= A.sleepAt) { setSleep("0"); el.pause(); toast("🌙 Uyqu taymeri — tinglash to'xtatildi"); }
  apTick();
}
function apSave() {
  if (!A.b || !A.el) return;
  const t = A.el.currentTime || A.seekTo || 0, ts = Math.floor(Date.now() / 1000);
  lsSet(`zk_bk_ap_${A.b.i}`, {n: A.n, t, ts});
  if (A.b.me) A.b.me.ap = {n: A.n, t, ts};
  A.saveT = Date.now();
  if (!inTg) return;
  const secs = Math.floor(A.heard); A.heard -= secs;
  api("api/books/audio", {i: A.b.i, n: A.n, t: Math.round(t), secs}).catch(() => {});
  meAt = 0;
}
function loadTrack(n, t, play) {
  const el = au(), tr = A.tracks.find((x) => x.n === n) || A.tracks[0];
  if (!tr) return;
  A.n = tr.n; A.err = false; A.lastT = -1; A.seekTo = t > 1 ? t : 0;
  el.src = trkUrl(tr.u); el.playbackRate = A.spd;
  if (play) { A.wait = true; el.play().catch(() => { A.wait = false; apSync(); }); }
  mediaMeta(); apSync(); if (A.full) apFull();
}
async function playBook(id, n, t) {
  id = +id;
  if (A.b && A.b.i === id && n === undefined) { openPlayer(); if (A.el.paused) apToggle(); return; }
  let b = books.get(id);
  if (!b || b.err || !b.tracks || (inTg && b.me === undefined)) {
    try { const r = await api(`api/books/b/${id}`); if (r.ok) books.set(id, {...r.book, _toc: b && b._toc}); } catch (e) {}
    b = books.get(id);
  }
  if (!b || !(b.tracks || []).length) { toast("⚠️ Bu kitobning audiosi topilmadi"); return; }
  if (A.b && A.b.i !== id) apSave();
  A.b = b; A.tracks = b.tracks; A.heard = 0;
  if (n === undefined) {
    const sv = b.me && b.me.ap, lc = lsGet(`zk_bk_ap_${id}`, null);
    const p = sv && lc ? ((lc.ts || 0) >= (sv.ts || 0) ? lc : sv) : sv || lc || {n: b.tracks[0].n, t: 0};
    n = p.n; t = p.t;
  }
  haptic();
  loadTrack(n, t || 0, true);
  openPlayer();
}
function apToggle() {
  const el = au(); if (!A.b) return;
  if (el.paused || A.err) {
    if (A.err) { const t = el.currentTime; loadTrack(A.n, t, true); return; }
    A.wait = true; el.play().catch(() => { A.wait = false; apSync(); toast("▶ ni yana bir bor bosing"); });
  } else el.pause();
  haptic(); apSync();
}
function apSeek(d) { const el = au(); if (!A.b) return; const D = el.duration || (curTrk() || {}).s || 0; el.currentTime = Math.max(0, Math.min(D ? D - 0.5 : 1e9, el.currentTime + d)); apTick(); }
function apStep(dir) {
  const el = au(); if (!A.b) return;
  if (dir < 0 && el.currentTime > 6) { el.currentTime = 0; return; }
  const i = trkIdx() + dir;
  if (i < 0 || i >= A.tracks.length) return;
  apSave(); loadTrack(A.tracks[i].n, 0, !el.paused || A.wait);
}
function setSleep(k) {
  A.sleep = k; A.sleepAt = /^\d+$/.test(k) && k !== "0" ? Date.now() + k * 60000 : 0;
  apSync(); if (A.full) apFull();
}
function apStop(hide) {
  if (A.el && !A.el.paused) A.el.pause();
  if (A.full) closePlayer();
  if (hide) { apSave(); A.b = null; A.tracks = []; if (A.el) { A.el.removeAttribute("src"); A.el.load(); } setSleep("0"); }
  apSync();
}
function mediaMeta() {
  if (!("mediaSession" in navigator) || !A.b) return;
  const tr = curTrk() || {};
  try {
    navigator.mediaSession.metadata = new MediaMetadata({title: tr.t || A.b.t, artist: shortA(A.b.a), album: A.b.t,
      artwork: A.b.c ? [{src: new URL(`bk/${A.b.i}/cover_l.webp`, location.href).href, sizes: "600x900", type: "image/webp"}] : []});
    const ms = navigator.mediaSession, set = (a, f) => { try { ms.setActionHandler(a, f); } catch (e) {} };
    set("play", () => { if (A.el.paused) apToggle(); }); set("pause", () => { if (!A.el.paused) apToggle(); });
    set("previoustrack", () => apStep(-1)); set("nexttrack", () => apStep(1));
    set("seekbackward", () => apSeek(-15)); set("seekforward", () => apSeek(30));
    set("seekto", (d) => { if (d && d.seekTime != null) { A.el.currentTime = d.seekTime; apTick(); } });
  } catch (e) {}
}

// --- ko'rinish: mini pleer (kutubxona ichida) + to'liq ekran
function miniEl() {
  let m = $("bxmini"); if (m) return m;
  m = document.createElement("div"); m.className = "bx-mini"; m.id = "bxmini"; m.hidden = true;
  m.innerHTML = `<button class="mm-open" data-a="open" aria-label="Pleerni ochish"><span class="mm-cv" id="bmcv"></span><span class="mm-tx"><b id="bmt"></b><i id="bmc"></i></span></button>
    <button class="mm-pp" data-a="pp" id="bmpp" aria-label="Ijro / pauza"></button><button class="mm-x" data-a="x" aria-label="Pleerni yopish">${I.x}</button>
    <span class="mm-bar"><span id="bmbar"></span></span>`;
  $("books").appendChild(m);
  m.addEventListener("click", (e) => {
    const a = e.target.closest("[data-a]"); if (!a) return;
    if (a.dataset.a === "open") openPlayer(); else if (a.dataset.a === "pp") apToggle(); else if (a.dataset.a === "x") apStop(true);
  });
  return m;
}
function apEl() {
  let el = $("bxap"); if (el) return el;
  el = document.createElement("section"); el.className = "bx-ap"; el.id = "bxap"; el.hidden = true;
  el.setAttribute("role", "dialog"); el.setAttribute("aria-label", "Audiokitob pleeri");
  el.innerHTML = `<div class="ap-glow" id="apglow"></div>
    <div class="ap-top"><button class="ap-ib" data-a="min" aria-label="Kichraytirish">${I.down}</button><div class="ap-src">${I.head}<span>Audiokitob</span></div>
      <button class="ap-ib" data-a="info" aria-label="Kitob haqida">${I.book}</button></div>
    <div class="ap-art"><div class="ap-cv" id="apcv"></div></div>
    <div class="ap-meta"><h2 id="apt"></h2><p id="apa"></p><button class="ap-chap" data-a="list" id="apch"></button></div>
    <div class="ap-scrub"><input type="range" id="aprange" min="0" max="1000" value="0" step="1" aria-label="Bobdagi joy">
      <div class="ap-times"><span id="apcur">0:00</span><span id="apleft"></span></div></div>
    <div class="ap-ctl"><button data-a="prev" aria-label="Oldingi bob">${I.prev}</button><button data-a="b15" aria-label="15 soniya orqaga">${I.b15}</button>
      <button class="ap-pp" data-a="pp" id="appp" aria-label="Ijro / pauza"></button>
      <button data-a="f30" aria-label="30 soniya oldinga">${I.f30}</button><button data-a="next" aria-label="Keyingi bob">${I.next}</button></div>
    <div class="ap-row"><button data-a="spd" id="apspd"></button><button data-a="sleep" id="apslp"></button><button data-a="list">${I.toc}<span>Boblar</span></button></div>`;
  document.body.appendChild(el);
  el.addEventListener("click", (e) => {
    const a = e.target.closest("[data-a]"); if (!a) return;
    const k = a.dataset.a;
    if (k === "min") closePlayer();
    else if (k === "pp") apToggle();
    else if (k === "b15") apSeek(-15);
    else if (k === "f30") apSeek(30);
    else if (k === "prev") apStep(-1);
    else if (k === "next") apStep(1);
    else if (k === "info") { const id = A.b.i; closePlayer(); if (!isTop(id)) openBook(id); }
    else if (k === "spd") pickSheet("Tezlik", SPEEDS.map((s) => [String(s), `${String(s).replace(".", ",")}×${s === 1 ? " — oddiy" : ""}`]), String(A.spd), (v) => {
      A.spd = +v; lsSet("zk_bk_spd", A.spd); if (A.el) A.el.playbackRate = A.spd; apFull(); });
    else if (k === "sleep") pickSheet("Uyqu taymeri", SLEEPS, A.sleep, (v) => { setSleep(v); if (v !== "0") toast(v === "end" ? "🌙 Bob oxirida to'xtaydi" : `🌙 ${v} daqiqadan keyin to'xtaydi`); });
    else if (k === "list") trackSheet();
  });
  const rg = el.querySelector("#aprange");
  rg.addEventListener("input", () => { A.drag = true; const D = A.el && (A.el.duration || (curTrk() || {}).s) || 0; $("apcur").textContent = fmtT(rg.value / 1000 * D); });
  rg.addEventListener("change", () => { const D = A.el && A.el.duration; if (D) A.el.currentTime = rg.value / 1000 * D; A.drag = false; apTick(); });
  let y0 = null;
  el.addEventListener("touchstart", (e) => { y0 = e.target.closest("input") ? null : e.touches[0].clientY; }, {passive: true});
  el.addEventListener("touchend", (e) => { if (y0 != null && e.changedTouches[0].clientY - y0 > 110) closePlayer(); y0 = null; }, {passive: true});
  return el;
}
function trackSheet() {
  const playing = A.el && !A.el.paused;
  openSheet(`<h3>Boblar</h3><div class="sub">${esc(A.b.t)} · ${A.tracks.length} bob · ${dur(A.b.au)}</div>
    <div class="bx-toc bx-trk in-sheet">${A.tracks.map((t) => `<button data-n="${t.n}" class="${t.n === A.n ? "cur" : ""}"><span class="n">${t.n === A.n && playing ? '<i class="eq"><i></i><i></i><i></i></i>' : t.n}</span>
      <span class="t">${esc(t.t)}</span><span class="d">${t.s ? fmtT(t.s) : ""}</span></button>`).join("")}</div>`, (sh) => {
    sh.querySelectorAll("[data-n]").forEach((x) => { x.onclick = () => { closeSheet(); apSave(); loadTrack(+x.dataset.n, 0, true); }; });
    const c = sh.querySelector(".cur"), ls = sh.querySelector(".bx-trk");
    if (c && ls) ls.scrollTop = Math.max(0, c.offsetTop - ls.offsetTop - ls.clientHeight / 2 + c.offsetHeight / 2);
  });
}
function openPlayer() {
  if (!A.b) return;
  const el = apEl(); A.full = true; el.hidden = false;
  requestAnimationFrame(() => el.classList.add("on"));
  apFull(); updateBack();
}
function closePlayer() {
  if (!A.full) return;
  const el = apEl(); A.full = false; el.classList.remove("on");
  setTimeout(() => { if (!A.full) el.hidden = true; }, reduced() ? 0 : 260);
  apSync(); updateBack();
  if (isTop(A.b && A.b.i)) render(true);
}
function apFull() {
  if (!A.full || !A.b) return;
  const tr = curTrk() || {};
  $("apcv").innerHTML = cover(A.b, "big");
  $("apt").textContent = A.b.t; $("apa").textContent = A.b.a || "";
  $("apch").innerHTML = `${I.toc}<span>${A.n}/${A.tracks.length} · ${esc(tr.t || "")}</span>`;
  $("apspd").innerHTML = `<b>${String(A.spd).replace(".", ",")}×</b><span>Tezlik</span>`;
  $("apslp").innerHTML = `${I.moon}<span>${A.sleep === "0" ? "Taymer" : A.sleep === "end" ? "Bob oxiri" : `${Math.max(1, Math.ceil((A.sleepAt - Date.now()) / 60000))} daq`}</span>`;
  $("apslp").classList.toggle("on", A.sleep !== "0");
  const gl = $("apglow");
  gl.className = `ap-glow k${((A.b.i || 0) * 7 + String(A.b.t || "").length) % 14}`;
  gl.style.backgroundImage = A.b.c ? `url(bk/${A.b.i}/cover_s.webp)` : "";
  apSync();
}
function apSync() {
  const m = miniEl();
  const show = !!A.b && opened && !A.full;
  m.hidden = !show; $("books").classList.toggle("mini", show);
  if (!A.b) return;
  const playing = A.el && !A.el.paused, tr = curTrk() || {};
  const icon = A.wait && playing ? '<span class="ap-spin"></span>' : playing ? I.pause : I.pp;
  if (show) {
    m.classList.toggle("low", stack.length > 0);
    const cv = $("bmcv"); if (cv.dataset.i !== String(A.b.i)) { cv.innerHTML = cover(A.b, "sm"); cv.dataset.i = A.b.i; }
    $("bmt").textContent = A.b.t; $("bmc").textContent = `${A.n}-bob · ${tr.t || ""}`;
    $("bmpp").innerHTML = icon;
  }
  if (A.full) { $("appp").innerHTML = icon; $("appp").classList.toggle("play", !playing); }
  apTick();
}
function apTick() {
  if (!A.b || !A.el) return;
  const el = A.el, D = el.duration && isFinite(el.duration) ? el.duration : (curTrk() || {}).s || 0, t = el.currentTime || A.seekTo || 0;
  const pct = D ? Math.min(1, t / D) : 0;
  const mb2 = $("bmbar"); if (mb2) mb2.style.width = (pct * 100).toFixed(2) + "%";
  if (A.full && !A.drag) {
    $("aprange").value = Math.round(pct * 1000); $("aprange").style.setProperty("--p", (pct * 100).toFixed(2) + "%");
    $("apcur").textContent = fmtT(t); $("apleft").textContent = D ? "−" + fmtT((D - t) / (A.spd || 1)) : "";
  }
  if ("mediaSession" in navigator && D && navigator.mediaSession.setPositionState) {
    try { navigator.mediaSession.setPositionState({duration: D, playbackRate: el.playbackRate || 1, position: Math.min(t, D)}); } catch (e) {}
  }
}
document.addEventListener("visibilitychange", () => { if (document.hidden && A.b && A.el && !A.el.paused) apSave(); });
window.addEventListener("pagehide", () => { if (A.b) apSave(); });

// ------------------------------------------------------------------ amallar
async function toggleSave(id) {
  const b = books.get(id); if (!b || !inTg) { toast("Ilovani bot ichidan oching"); return; }
  const v = !(b.me && b.me.saved);
  const r = await api("api/books/shelf", {i: id, saved: v});
  if (r.ok) { b.me = Object.assign(b.me || {}, {saved: v}); haptic("ok"); toast(v ? "🔖 Javonga saqlandi" : "Javondan olib tashlandi"); meAt = 0; render(true); }
}
function askConfirm(text) {
  return new Promise((res) => {
    try { if (inTg && tg.showConfirm) { tg.showConfirm(text, (ok) => res(!!ok)); return; } } catch (e) {}
    res(window.confirm(text));
  });
}
async function adminDelete(id) {
  const b = books.get(id); if (!b) return;
  if (!(await askConfirm(`«${b.t}» kutubxonadan butunlay o'chirilsinmi? Buni qaytarib bo'lmaydi.`))) return;
  let r;
  try { r = await api("api/books/admin/delete", {i: id}); } catch (e) { r = {ok: false, error: "net"}; }
  if (!r.ok) { haptic("err"); toast(r.error === "forbidden" ? "Faqat admin o'chira oladi" : "⚠️ O'chirib bo'lmadi"); return; }
  haptic("ok"); toast("🗑 Kitob o'chirildi");
  books.delete(id);
  const drop = (arr) => arr && arr.filter((x) => x.i !== id);
  if (home) home.shelves = (home.shelves || []).map((sh) => ({...sh, items: drop(sh.items)})).filter((sh) => sh.items.length);
  if (S.items) S.items = drop(S.items);
  stack.forEach((v) => { if (v.items) v.items = drop(v.items); });
  if (me) { me.books = drop(me.books); me.audio = drop(me.audio); }
  if (A.b && A.b.i === id) apStop(true);
  stack = stack.filter((v) => !(v.v === "book" && v.id === id));
  render(true);
}
function shareBook(id) {
  const b = books.get(id); if (!b) return;
  const link = botName ? `https://t.me/${botName}?startapp=books_${id}` : location.href;
  const text = `📚 «${b.t}»${b.a ? " — " + shortA(b.a) : ""}. Shu yerda bepul o'qing:`;
  if (inTg) tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`);
  else { try { navigator.clipboard.writeText(link); toast("🔗 Havola nusxalandi"); } catch (e) {} }
}
function bookMenu(id) {
  const b = ((me && me.books) || []).find((x) => x.i === id); if (!b) return;
  const opts = [["read", "📖 O'qish"], ["info", "ℹ️ Kitob haqida"], ["done", b.done ? "↩️ O'qilmagan deb belgilash" : "✅ O'qildi deb belgilash"],
    ["save", b.saved ? "🔖 Saqlanganlardan olib tashlash" : "🔖 Saqlash"], ["dl", "⬇️ Yuklab olish"], ["rm", "🗑 Javondan olib tashlash"]];
  openSheet(`<h3>${esc(b.t)}</h3><div class="sub">${esc(shortA(b.a))}</div>${opts.map(([k, t]) => `<button class="bx-opt${k === "rm" ? " danger" : ""}" data-k="${k}">${t}</button>`).join("")}`, (sh) => {
    sh.querySelectorAll("[data-k]").forEach((x) => { x.onclick = async () => {
      closeSheet(); const k = x.dataset.k;
      if (k === "read") openReader(id); else if (k === "info") openBook(id); else if (k === "dl") openDownload(id);
      else {
        const body = k === "done" ? {done: !b.done} : k === "save" ? {saved: !b.saved} : {remove: true};
        const r = await api("api/books/shelf", {i: id, ...body});
        if (r.ok) { haptic("ok"); localStorage.removeItem && k === "rm" && localStorage.removeItem(`zk_bk_pos_${id}`); books.delete(id); await loadMe(true); render(true); }
      }
    }; });
  });
}

function onClick(e) {
  const t = e.target;
  const md = t.closest("[data-mode]"); if (md) { if (md.dataset.mode !== "books" && window.ZK_setMode) window.ZK_setMode(md.dataset.mode); return; }
  const tb = t.closest("[data-tab]");
  if (tb) {
    const nt = tb.dataset.tab; stack = [];
    if (nt === tab && nt === "lib") { const sc = $("bxscroll"); if (sc) sc.scrollTo({top: 0, behavior: reduced() ? "auto" : "smooth"}); return; }
    tab = nt; haptic(); render();
    if (tab === "shelf") loadMe(true);
    if (tab === "search") setTimeout(() => { const q = $("bxq"); if (q && !S.q) q.focus(); }, 60);
    return;
  }
  const pl = t.closest("[data-play]"); if (pl) { playBook(+pl.dataset.play); return; }
  const trk = t.closest("[data-trk]"); if (trk) { const top = stack[stack.length - 1]; if (top && top.v === "book") playBook(top.id, +trk.dataset.trk, 0); return; }
  const rd = t.closest("[data-read]"); if (rd) { openReader(+rd.dataset.read); return; }
  const dl = t.closest("[data-dl]"); if (dl) { openDownload(+dl.dataset.dl); return; }
  const bk = t.closest("[data-book]"); if (bk) { openBook(+bk.dataset.book); return; }
  const ls = t.closest("[data-list]"); if (ls) { try { openList(JSON.parse(ls.dataset.list)); } catch (er) {} return; }
  const menu = t.closest("[data-menu]"); if (menu) { bookMenu(+menu.dataset.menu); return; }
  const sht = t.closest("[data-sht]"); if (sht) { shelfTab = sht.dataset.sht; haptic(); render(true); return; }
  const gn = t.closest("[data-gonote]"); if (gn) { const x = JSON.parse(gn.dataset.gonote); openReader(x.i, x.ch, 0); return; }
  const star = t.closest("[data-star]");
  if (star) {
    const top = stack[stack.length - 1]; const b = top && books.get(top.id); const n = +star.dataset.star;
    api("api/books/shelf", {i: b.i, stars: n}).then((r) => { if (r.ok) { b.me = Object.assign(b.me || {}, {stars: n}); haptic("ok"); toast(`⭐ Rahmat! ${n} yulduz`); render(true); } });
    return;
  }
  const ch = t.closest("[data-ch]"); if (ch) { const top = stack[stack.length - 1]; if (top && top.v === "book") openReader(top.id, +ch.dataset.ch, 0); return; }
  const lv = t.closest("[data-lv]"); if (lv) { const v = stack[stack.length - 1]; v.p.lv = lv.dataset.lv; v.items = null; render(true); loadList(v); return; }
  const g2 = t.closest("[data-g2]"); if (g2) { const v = stack[stack.length - 1]; v.p.g2 = g2.dataset.g2; v.items = null; render(true); loadList(v); return; }
  const f = t.closest("[data-f]"); if (f && tab === "search" && !stack.length) { S.f = S.f === f.dataset.f ? "" : f.dataset.f; haptic(); runSearch(true); return; }
  const qb = t.closest("[data-q]"); if (qb) { S.q = qb.dataset.q; runSearch(true); return; }
  const gs = t.closest("[data-gs]"); if (gs) { S.g = gs.dataset.gs; haptic(); runSearch(true); return; }
  const a = t.closest("[data-act]"); if (!a) return;
  const act = a.dataset.act, top = stack[stack.length - 1];
  if (act === "homeback") { if (window.ZK_setMode) window.ZK_setMode("kino"); return; }
  if (act === "hub") { if (window.ZHub && window.ZHub.open) window.ZHub.open(); return; }
  if (act === "back") back();
  else if (act === "reload") { homeErr = false; render(); loadHome(); }
  else if (act === "save") toggleSave(top.id);
  else if (act === "share") shareBook(top.id);
  else if (act === "more-desc") { const b = books.get(top.id); b._full = true; render(true); }
  else if (act === "toc-all") { const b = books.get(top.id); b._tocAll = true; render(true); }
  else if (act === "adm-del") adminDelete(top.id);
  else if (act === "trk-all") { const b = books.get(top.id); b._trkAll = true; render(true); }
  else if (act === "more") loadList(top, true).then(() => {});
  else if (act === "smore") runSearch(false, true);
  else if (act === "abclr") { S.ab = ""; runSearch(true); }
  else if (act === "clr") { S.q = ""; runSearch(true); setTimeout(() => { const q = $("bxq"); if (q) q.focus(); }, 30); }
  else if (act === "recclr") { lsSet("zk_bk_recent", []); render(true); }
  else if (act === "view") { top.grid = top.grid === false; lsSet("zk_bk_grid", top.grid); render(true); }
  else if (act === "sort") pickSheet("Saralash", SORTS, top.p.s || "pop", (k) => { top.p.s = k; top.items = null; render(true); loadList(top); });
  else if (act === "ssort") pickSheet("Saralash", SORTS, S.s, (k) => { S.s = k; runSearch(true); });
  else if (act === "lang") pickSheet("Til", [["", "Barcha tillar"], ...Object.keys(LANGS).map((k) => [k, `${LANGS[k][0]} ${LANGS[k][1]}`])], S.l, (k) => { S.l = k; runSearch(true); });
  else if (act === "genre") pickSheet("Janr", [["", "Barcha janrlar"], ...((home && home.genres) || []).map((g) => [g.g, `${(GEN[g.g] || GEN.boshqa)[0]} ${gname(g.g)} · ${g.n}`])], S.g, (k) => { S.g = k; runSearch(true); });
}

// cheksiz ro'yxat: "Yana" tugmasi ko'rinsa — o'zi yuklaydi
let moreObs = null;
function bindMore() {
  if (moreObs) moreObs.disconnect();
  const m = $("bxmore"); if (!m || !("IntersectionObserver" in window)) return;
  moreObs = new IntersectionObserver((en) => { if (en[0].isIntersecting) m.click(); }, {root: $("bxscroll"), rootMargin: "300px"});
  moreObs.observe(m);
}

function back() {
  if (sheetOpen) { closeSheet(); return true; }
  if (A.full) { closePlayer(); return true; }
  if (R.on) { closeReader(); return true; }
  if (stack.length) { stack.pop(); render(true); return true; }
  if (tab !== "lib") { tab = "lib"; render(); return true; }
  return false;
}
function updateBack() {
  if (!inTg) return;
  const need = opened && (sheetOpen || A.full || R.on || stack.length || tab !== "lib");
  try { need ? tg.BackButton.show() : (window.ZK_canHideBack ? window.ZK_canHideBack() && tg.BackButton.hide() : tg.BackButton.hide()); } catch (e) {}
}
if (inTg) tg.BackButton.onClick(() => { if (opened) { back(); updateBack(); } });

async function loadHome() {
  try {
    const r = await (await fetch("api/books/home", {cache: "no-cache"})).json();
    home = r; homeErr = false;
  } catch (e) { homeErr = true; }
  if (opened && !stack.length) render(true);
}
function mount() {
  if (mounted) return; mounted = true;
  const v = $("bxview");
  v.addEventListener("click", onClick);
  $("bxsbg").addEventListener("click", closeSheet);
  // muqova rasmi yuklanmasa — chizilgan muqova qoladi
  document.addEventListener("error", (e) => {
    const im = e.target; if (im && im.tagName === "IMG" && im.parentElement && im.parentElement.classList.contains("cv")) {
      im.parentElement.classList.remove("has"); im.remove(); }
  }, true);
}

window.ZBooks = {
  open(spec) {
    mount(); opened = true;
    $("books").hidden = false; document.body.classList.add("b-on");
    try { tg.setHeaderColor("#0D2420"); tg.setBackgroundColor("#0D2420"); if (tg.setBottomBarColor) tg.setBottomBarColor("#0B1F1B"); } catch (e) {}
    if (!home) loadHome();
    loadMe();
    if (spec && /^\d+$/.test(String(spec))) { tab = "lib"; stack = []; openBook(+spec); return; }
    render();
  },
  close() {
    if (R.on) closeReader();
    apStop(false);
    closeSheet(); opened = false;
    $("books").hidden = true; document.body.classList.remove("b-on");
    try { tg.setHeaderColor("bg_color"); tg.setBackgroundColor("bg_color"); if (tg.setBottomBarColor) tg.setBottomBarColor("bottom_bar_bg_color"); } catch (e) {}
    updateBack();
  },
  busy() { return opened && (sheetOpen || A.full || R.on || stack.length > 0 || tab !== "lib"); },
  setBot(b) { botName = b || ""; },
};
})();

// Test helpers
const bkReaderText = "bkReaderText";
const bkShelfCount = "bkShelfCount";


// Invariant helpers
const _bkTestInvariants = '<div id="bkReaderText"></div><span id="bkShelfCount"></span>';
