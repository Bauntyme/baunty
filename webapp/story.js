/* 👻 Anonim Story — ochiq Instagram profillar va Telegram kanallar story'lari. index.html dan window.ZStory orqali boshqariladi.
   Story'ni bizning server oladi — egasi ko'ruvchilar ro'yxatida foydalanuvchini ko'rmaydi. Yopiq profillar ochilmaydi. */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const lsGet = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const reduced = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

// ------------------------------------------------------------------ ikonkalar
const I = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  dl: (c = "currentColor") => `<svg viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0-4-4m4 4 4-4M4 21h16"/></svg>`,
  link: '<svg viewBox="0 0 24 24" fill="none" stroke="#FF7DA8" stroke-width="2.4" stroke-linecap="round"><path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="#9C96BF" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
  anon: (c = "#3BD48A") => `<svg viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><path d="M4 20 20 4"/></svg>`,
  eye: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round"><g class="lid"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></g><path d="M4 20 20 4"/></svg>',
  ig: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg>',
  tg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21.5 4.2 2.9 11.4c-1.3.5-1.3 1.2-.2 1.6l4.8 1.5 1.8 5.6c.2.6.4.8.9.8.4 0 .6-.2.9-.5l2.3-2.2 4.8 3.5c.9.5 1.5.2 1.7-.8l3.1-14.6c.3-1.3-.5-1.9-1.5-1.1zM9.4 14.6l9-5.7-7.1 6.6-.3 3.1z"/></svg>',
  bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="#06210F" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5 9-10"/></svg>',
  okc: '<svg viewBox="0 0 24 24" fill="none" stroke="#3BD48A" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5 9-10"/></svg>',
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="#C9C3EA" stroke-width="2.2"><rect x="5" y="11" width="14" height="10" rx="3"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="#FF7DA8" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9" stroke-dasharray="4 3"/><path d="M12 8v4l2 2"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="#FFC24B" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4 2 20h20z"/><path d="M12 10v4M12 17h.01"/></svg>',
  ghost: '<svg viewBox="0 0 24 24" fill="none" stroke="#C9C3EA" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4M8 11h6"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="#fff"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>',
  vol: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 9a4 4 0 0 1 0 6"/></svg>',
  mute: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="m17 10 4 4m0-4-4 4"/></svg>',
  share: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M12 3v12M7 8l5-5 5 5"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  navStory: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/></svg>',
  navWatch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s-7-4.5-7-11a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 6.5-7 11-7 11z"/></svg>',
  verified: '<svg viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="10" fill="#2AABEE"/><path d="m8 12 3 3 5-6" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

// ------------------------------------------------------------------ holat
let opened = false, botName = "";
let tab = "home";                    // home | watch | saved
let plat = lsGet("zk_st_plat", "ig"), picked = false;   // picked: shu safar tarmoq tanlandimi (avval tanlov, keyin username)
let stack = [];                      // [{v:"profile", p, u}, {v:"hl", hid, title}]
let me = {watch: [], featured: [], tg: false, max: 15};
let prof = null;                     // joriy profil ma'lumoti {p,u,name,pic,items,err,hl}
let hlData = null;                   // joriy aktual {hid,title,items}
let selMode = false, sel = new Set();
let pollTok = 0;
const hist = () => lsGet("zk_st_hist", []);
const saved = () => lsGet("zk_st_saved", []);

const api = async (path, body) => {
  const opt = {headers: {"X-Init-Data": (tg && tg.initData) || ""}};
  if (body) { opt.method = "POST"; opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  const r = await fetch(path, opt);
  if (r.status === 401) return {ok: false, error: "auth"};
  return r.json();
};

function toast(t, ms = 2400) {
  let el = $("sxtoast");
  if (!el) { el = document.createElement("div"); el.id = "sxtoast"; el.className = "sx-toast"; document.body.appendChild(el); }
  el.textContent = t; el.classList.add("on");
  clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove("on"), ms);
}

// ------------------------------------------------------------------ yordamchilar
function parseInput(raw) {
  const s = String(raw || "").trim();
  if (!s) return null;
  let m = s.match(/instagram\.com\/(?:stories\/)?([A-Za-z0-9._]{1,30})/i);
  if (m && !/^(p|reel|reels|tv|explore|accounts|direct|about)$/i.test(m[1])) return {p: "ig", u: m[1], link: true};
  m = s.match(/t\.me\/(?:s\/)?([A-Za-z][A-Za-z0-9_]{3,31})/i);
  if (m) return {p: "tg", u: m[1], link: true};
  const u = s.replace(/^@/, "");
  if (plat === "ig" && /^[A-Za-z0-9._]{1,30}$/.test(u)) return {p: "ig", u};
  if (plat === "tg" && /^[A-Za-z][A-Za-z0-9_]{3,31}$/.test(u)) return {p: "tg", u};
  return {bad: true};
}
const initials = (s) => (String(s || "?").replace(/^@/, "").match(/[A-Za-z0-9А-Яа-яЁё]/g) || ["?"]).slice(0, 2).join("").toUpperCase();
const GRADS = ["#FFB86B,#FF6F8E,#6B3FA0", "#5FD3F3,#2E7FD9,#1C3C7A", "#2B2250,#7B3FE4,#F25DA2", "#0F3D3E,#1F8A70,#BFDB38", "#F9D976,#F39F86,#8E5BA6", "#EF476F,#7B2CBF,#3A0CA3"];
const grad = (s) => { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return `linear-gradient(135deg,${GRADS[h % GRADS.length]})`; };
function ring(p, u, pic, cls = "") {
  const bg = pic ? `background-image:url('${esc(pic)}')` : `background:${grad(u)}`;
  return `<div class="sx-ring ${p === "tg" ? "tg" : ""} ${cls}"><i style="${bg}">${pic ? "" : esc(initials(u))}</i></div>`;
}
const MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];
function ago(ts) {
  if (!ts) return "";
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} daqiqa oldin`;
  if (s < 86400) return `${Math.round(s / 3600)} soat oldin`;
  const d = new Date(ts * 1000);
  return `${d.getDate()}-${MONTHS[d.getMonth()]}`;
}
function dayKey(ts) {
  if (!ts) return "Story'lar";
  const d = new Date(ts * 1000), n = new Date();
  const t0 = new Date(n.getFullYear(), n.getMonth(), n.getDate()).getTime() / 1000;
  if (ts >= t0) return "Bugun";
  if (ts >= t0 - 86400) return "Kecha";
  return `${d.getDate()}-${MONTHS[d.getMonth()]}${d.getFullYear() !== n.getFullYear() ? " " + d.getFullYear() : ""}`;
}
const hhmm = (ts) => { if (!ts) return ""; const d = new Date(ts * 1000); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
const dur = (s) => s ? `0:${String(Math.min(59, s)).padStart(2, "0")}` : "";
const isWatched = (p, u) => me.watch.find((w) => w.p === p && w.u.toLowerCase() === String(u).toLowerCase());
function addHist(p, u, name) {
  const h = hist().filter((x) => !(x.p === p && x.u.toLowerCase() === u.toLowerCase()));
  h.unshift({p, u, name: name || ""}); lsSet("zk_st_hist", h.slice(0, 12));
}

// ------------------------------------------------------------------ chizish: umumiy
function segHTML() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["story", "Story"]];
  return `<div class="sx-segw"><div class="sx-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "story" ? "on" : ""}">${esc(l)}</button>`).join("")}</div></div>`;
}
function navHTML() {
  const n = me.watch.length;
  return `<nav class="sx-nav">
    <button data-tab="home" class="${tab === "home" ? "on" : ""}">${I.navStory}Story</button>
    <button data-tab="watch" class="${tab === "watch" ? "on" : ""}">${I.navWatch}Kuzatuv${n ? `<span class="n">${n}</span>` : ""}</button>
    <button data-tab="saved" class="${tab === "saved" ? "on" : ""}">${I.dl()}Yuklanganlar</button></nav>`;
}
function render() {
  if (!opened) return;
  const top = stack[stack.length - 1];
  $("story").classList.toggle("tgp", plat === "tg");
  let html;
  if (top && top.v === "profile") html = profileHTML();
  else if (top && top.v === "hl") html = hlHTML();
  else html = tab === "watch" ? watchHTML() : tab === "saved" ? savedHTML() : homeHTML();
  const bottom = selMode ? selbarHTML() : (top ? "" : navHTML());
  $("sxview").innerHTML = `<div class="sx-scroll${selMode ? " sel" : ""}" id="sxscroll">${html}</div>${bottom}`;
  if (!top && tab === "home") bindHome();
  updateBack();
}

// ------------------------------------------------------------------ bosh sahifa
function homeHTML() {
  const h = hist(), w = me.watch, f = me.featured.filter((x) => x.p === "ig" || me.tg);
  const ph = plat === "ig" ? "@username yoki profil havolasi" : "@kanal yoki t.me/ havolasi";
  return `${segHTML()}
  <div class="sx-hero"><div class="sx-hrow"><div class="sx-eye">${I.eye}</div>
    <span class="sx-chip ok" style="margin-top:6px"><i></i>Siz ko'rinmaysiz</span></div>
    <h2>Story'larni sezdirmasdan ko'ring</h2>
    <p>Profil egasi story'ni kim ko'rganini ko'rsa ham, ro'yxatda sizni ko'rmaydi</p></div>
  ${picked ? `<div class="sx-tabs" role="tablist">
    <button class="sx-tab ig${plat === "ig" ? " on" : ""}" data-plat="ig" role="tab" aria-selected="${plat === "ig"}">${I.ig}Instagram</button>
    <button class="sx-tab tg${plat === "tg" ? " on" : ""}" data-plat="tg" role="tab" aria-selected="${plat === "tg"}">${I.tg}Telegram</button></div>
  <form class="sx-inp sx-in" id="sxform" autocomplete="off">${I.search}
    <input id="sxq" type="text" inputmode="url" autocapitalize="off" spellcheck="false" placeholder="${ph}" aria-label="${ph}">
    <button class="sx-go" id="sxgo" type="submit" disabled>Ochish</button></form>
  <div class="sx-detect" id="sxdet" aria-live="polite"></div>` : `<div class="sx-h"><h3>Qaysi tarmoqdan?</h3></div>
  <div class="sx-pick" role="group" aria-label="Tarmoqni tanlang">
    <button class="sx-pc ig" data-plat="ig"><span class="ic">${I.ig}</span><b>Instagram</b><span>Ochiq profil story'lari</span></button>
    <button class="sx-pc tg" data-plat="tg"><span class="ic">${I.tg}</span><b>Telegram</b><span>Kanal va profil story'lari</span></button></div>`}
  ${w.length ? `<div class="sx-h"><h3>Kuzatuvdagilar</h3><button class="sx-link" data-tab="watch">Hammasi</button></div>
    <div class="sx-rings">${w.map((x) => `<button class="sx-av" data-open="${x.p}:${esc(x.u)}">${ring(x.p, x.title || x.u, "")}<small>${esc(x.title || x.u)}</small></button>`).join("")}</div>` : ""}
  ${h.length ? `<div class="sx-h"><h3>Oxirgi qidiruvlar</h3><button class="sx-link" data-clearhist>Tozalash</button></div>
    <div class="sx-hist">${h.map((x, i) => `<span class="sx-chip"><button data-open="${x.p}:${esc(x.u)}"><b>${x.p === "tg" ? "✈️ " : ""}${esc(x.u)}</b></button><button class="x" data-delhist="${i}" aria-label="O'chirish">✕</button></span>`).join("")}</div>` : ""}
  ${f.length ? `<div class="sx-h"><h3>Tavsiya</h3><span>ochiq sahifalar</span></div>
    <div class="sx-list">${f.map((x) => `<button class="sx-li" data-open="${x.p}:${esc(x.u)}">${ring(x.p, x.u, "")}<span class="t"><b>${esc(x.u)}</b><span>${x.p === "ig" ? "Instagram" : "Telegram"}</span></span><span class="sx-pill ${x.p}">${x.p.toUpperCase()}</span></button>`).join("")}</div>` : ""}
  ${!w.length && !h.length ? `<div class="sx-h"><h3>Qanday ishlaydi</h3></div>
    <div class="sx-list">
      <div class="sx-li"><span class="sx-pill ig">1</span><span class="t"><b>Username yoki havolani kiriting</b><span>instagram.com/... yoki t.me/... ni shunchaki qo'ying</span></span></div>
      <div class="sx-li"><span class="sx-pill ig">2</span><span class="t"><b>Story'larni shu yerda ko'ring</b><span>Bizning server ochadi — siz ko'rinmaysiz</span></span></div>
      <div class="sx-li"><span class="sx-pill ig">3</span><span class="t"><b>Kerakligini chatga yuklang</b><span>Rasm va videolar bot chatiga keladi</span></span></div></div>` : ""}
  <div class="sx-note">${I.lock.replace('stroke="#C9C3EA"', 'stroke="#9C96BF"')}<span>Faqat ochiq profillar. Yopiq profillar va «Yaqin do'stlar» story'lari ko'rinmaydi.${plat === "tg" && !me.tg ? " Telegram story'lari hozir vaqtincha ishlamayapti." : ""}</span></div>`;
}
function bindHome() {
  const q = $("sxq"); if (!q) return;
  const upd = () => {
    const r = parseInput(q.value), det = $("sxdet");
    $("sxgo").disabled = !r || r.bad;
    det.classList.toggle("bad", !!(r && r.bad));
    if (!r) det.innerHTML = "";
    else if (r.bad) det.textContent = plat === "ig" ? "Username faqat harf, raqam, nuqta va _ dan iborat" : "Kanal nomi kamida 5 belgi, harf bilan boshlanadi";
    else if (r.link) det.innerHTML = `${I.okc.replace("<svg", '<svg width="15" height="15"')} Havola tanildi: ${r.p === "ig" ? "Instagram" : "Telegram"} · @${esc(r.u)}`;
    else det.innerHTML = "";
  };
  q.addEventListener("input", upd);
  $("sxform").addEventListener("submit", (e) => {
    e.preventDefault();
    const r = parseInput(q.value);
    if (!r || r.bad) { haptic("err"); return; }
    q.blur(); openProfile(r.p, r.u);
  });
}

// ------------------------------------------------------------------ profil
function openProfile(p, u, push = true) {
  u = String(u).replace(/^@/, "");
  if (p === "ig") u = u.toLowerCase();
  if (p !== plat) { plat = p; lsSet("zk_st_plat", p); }
  picked = true;
  if (push) stack.push({v: "profile", p, u});
  selMode = false; sel.clear();
  prof = {p, u, name: "", pic: "", items: null, err: null, hl: null, pending: false};
  render(); $("sxscroll") && ($("sxscroll").scrollTop = 0);
  loadProfile(prof);
}
async function loadProfile(pr) {
  const tok = ++pollTok;
  try {
    if (pr.p === "ig") {
      const r = await api(`api/story/ig?u=${encodeURIComponent(pr.u)}`);
      if (prof !== pr) return;
      if (!r.ok) { pr.err = r.error; render(); return; }
      Object.assign(pr, {name: r.name, pic: r.pic, verified: r.verified, items: r.items || []});
      addHist("ig", pr.u, r.name);
      render();
      api(`api/story/ighl?u=${encodeURIComponent(pr.u)}`).then((h) => { if (prof === pr) { pr.hl = (h && h.items) || []; render(); } }).catch(() => {});
      return;
    }
    const t0 = Date.now();
    for (;;) {
      const r = await api(`api/story/tg?u=${encodeURIComponent(pr.u)}`);
      if (prof !== pr || tok !== pollTok) return;
      if (!r.ok) { pr.err = r.error; pr.wait = r.wait; render(); return; }
      if (!r.pending) {
        Object.assign(pr, {name: r.name, items: r.items || [], pending: false});
        addHist("tg", pr.u, r.name); render(); return;
      }
      if (!pr.pending) { pr.pending = true; render(); }
      if (Date.now() - t0 > 75000) { pr.err = "down"; render(); return; }
      await sleep(1500);
    }
  } catch (e) { if (prof === pr) { pr.err = "net"; render(); } }
}
const ERR = {
  private: [I.lock, "Bu profil yopiq", (u) => `@${u} story'larini faqat obunachilari ko'radi. Yopiq profillarni ochmaymiz.`, "Boshqa profil qidirish", "home"],
  not_found: [I.ghost, "Profil topilmadi", (u) => `@${u} degan profil yo'q yoki nomi o'zgargan. Yozilishini tekshiring.`, "Qayta qidirish", "home"],
  bad_username: [I.ghost, "Username noto'g'ri", () => "Faqat harf, raqam, nuqta va _ ishlatiladi.", "Qayta qidirish", "home"],
  rate: [I.warn, "Hozir javob kelmadi", (u, w) => w > 600
    ? `Telegram story ko'rishni vaqtincha chekladi. Taxminan ${w >= 3600 ? Math.ceil(w / 3600) + " soatdan" : Math.ceil(w / 60) + " daqiqadan"} keyin yana ishlaydi. Instagram story'lari hozir ham ochiladi.`
    : "So'rovlar ko'payib ketdi. 1–2 daqiqadan keyin qayta urinib ko'ring.", "Qayta urinish", "retry"],
  rate_user: [I.warn, "Biroz dam oling", () => "Bir soatlik limit tugadi. Birozdan keyin qayta urinib ko'ring.", "Bosh sahifaga", "home"],
  down: [I.warn, "Xizmat vaqtincha ishlamayapti", () => "Birozdan keyin qayta urinib ko'ring.", "Qayta urinish", "retry"],
  net: [I.warn, "Internet bilan muammo", () => "Ulanishni tekshirib, qayta urinib ko'ring.", "Qayta urinish", "retry"],
  auth: [I.warn, "Ilovani bot ichidan oching", () => "Bu bo'lim faqat Telegram ichida ishlaydi.", "Bosh sahifaga", "home"],
};
function stateHTML(code, u, wait) {
  const e = ERR[code] || ERR.down;
  return `<div class="sx-st"><div class="ic">${e[0]}</div><h4>${e[1]}</h4><p>${esc(e[2](u, +wait || 0))}</p>
    <button class="sx-btn sec" data-st="${e[4]}">${e[3]}</button></div>`;
}
function tileHTML(it, i, src) {
  const k = String(it.id);
  return `<button class="sx-th${sel.has(k) ? " on" : ""}" data-i="${i}" data-src="${src}" aria-label="${it.k === "video" ? "Video" : "Rasm"} story ${i + 1}"
    style="background-image:url('${esc(it.t)}')">${it.k === "video" ? '<span class="pl"></span>' : ""}<span class="ck">${I.check}</span>
    <em>${it.k === "video" && it.d ? dur(it.d) : hhmm(it.ts)}</em></button>`;
}
function groupsHTML(items, src, tgMode) {
  const groups = [];
  items.forEach((it, i) => {
    const key = tgMode ? (it.a ? "Faol · 24 soat" : "Profilda saqlangan") : dayKey(it.ts);
    let g = groups.find((x) => x.k === key); if (!g) { g = {k: key, list: []}; groups.push(g); }
    g.list.push([it, i]);
  });
  return groups.map((g) => `<div class="sx-grp"><b>${esc(g.k)}</b><span>${g.list.length} ta${g.k === "Bugun" && g.list.length ? " · oxirgisi " + ago(g.list[0][0].ts) : ""}</span></div>
    <div class="sx-grid">${g.list.map(([it, i]) => tileHTML(it, i, src)).join("")}</div>`).join("");
}
function profileHTML() {
  const pr = prof, w = isWatched(pr.p, pr.u);
  const top = `<div class="sx-top"><button class="sx-ib" data-back aria-label="Orqaga">${I.back}</button>
    <div class="sx-ttl">${esc(pr.p === "tg" ? (pr.name || pr.u) : pr.u)}</div>
    ${pr.items && pr.items.length ? `<button class="sx-link" data-selmode>${selMode ? "Bekor" : "Tanlash"}</button>` : `<span class="sx-pill ${pr.p}">${pr.p === "ig" ? "Instagram" : "Telegram"}</span>`}</div>`;
  if (pr.err) return top + stateHTML(pr.err, pr.u, pr.wait);
  if (!pr.items) {
    return top + `<div class="sx-pf">${ring(pr.p, pr.u, "", "sx-spin")}<div class="sx-stats"><div><b class="sx-skel" style="width:40px;height:20px;border-radius:6px"></b><span>story</span></div></div></div>
      ${pr.pending ? `<div class="sx-wait">Telegram'dan story'lar olinmoqda…<br>Kanal katta bo'lsa 10–20 soniya ketadi</div>` : ""}
      <div class="sx-grid" style="margin-top:18px">${Array.from({length: 6}, () => '<div class="sx-th sx-skel"></div>').join("")}</div>`;
  }
  const n = pr.items.length, act = pr.p === "tg" ? pr.items.filter((x) => x.a).length : n;
  const head = `<div class="sx-pf">${ring(pr.p, pr.u, pr.pic, n ? "" : "sx-seen")}
      <div class="sx-stats"><div><b>${n}</b><span>story</span></div>${pr.p === "tg" ? `<div><b>${act}</b><span>faol</span></div>` : ""}
      ${pr.hl && pr.hl.length ? `<div><b>${pr.hl.length}</b><span>aktual</span></div>` : ""}</div></div>
    <div class="sx-bio"><b>${esc(pr.name || "@" + pr.u)}${pr.verified ? I.verified : ""}</b>${pr.p === "ig" ? `@${esc(pr.u)} · ochiq profil` : `t.me/${esc(pr.u)}`}</div>
    <div class="sx-acts"><button class="sx-btn ${w ? "done" : pr.p === "tg" ? "tg" : "ig"}" data-watch>${I.bell}${w ? "Kuzatilyapti" : "Kuzatish"}</button>
      <button class="sx-btn sec" data-sendall ${n ? "" : "disabled"}>${I.dl()}Hammasi (${n})</button></div>`;
  const hls = pr.p === "ig" && pr.hl && pr.hl.length ? `<div class="sx-hls">${pr.hl.map((h) => `<button class="sx-hlc" data-hl="${esc(h.id)}"><span class="c"><i style="${h.c ? `background-image:url('${esc(h.c)}')` : `background:${grad(h.title)}`}"></i></span><small>${esc(h.title || "Aktual")}</small></button>`).join("")}</div>` : "";
  const body = n ? groupsHTML(pr.items, "p", pr.p === "tg")
    : `<div class="sx-st"><div class="ic" style="background:#FF3D7F1f">${I.clock}</div><h4>Hozir story yo'q</h4>
       <p>@${esc(pr.u)} oxirgi 24 soatda story qo'ymagan. Kuzatuvga qo'shsangiz, yangisi chiqishi bilan xabar beramiz.</p>
       ${w ? `<button class="sx-btn done" data-watch>${I.bell}Kuzatilyapti</button>` : `<button class="sx-btn ig" data-watch>${I.bell}Kuzatuvga qo'shish</button>`}</div>`;
  return top + head + hls + body;
}

// ------------------------------------------------------------------ aktual
function openHL(hid) {
  const h = (prof && prof.hl || []).find((x) => x.id === hid); if (!h) return;
  stack.push({v: "hl", hid, title: h.title});
  selMode = false; sel.clear();
  hlData = {hid, title: h.title, cover: h.c, n: h.n, items: null, err: null};
  render();
  const cur = hlData;
  api(`api/story/ighi?id=${encodeURIComponent(hid)}`).then((r) => {
    if (hlData !== cur) return;
    cur.items = (r && r.items) || []; if (!r || !r.ok) cur.err = (r && r.error) || "down"; render();
  }).catch(() => { if (hlData === cur) { cur.err = "net"; render(); } });
}
function hlHTML() {
  const h = hlData, vids = h.items ? h.items.filter((x) => x.k === "video").length : 0;
  const top = `<div class="sx-top"><button class="sx-ib" data-back aria-label="Orqaga">${I.back}</button><div class="sx-ttl">Aktual</div>
    ${h.items && h.items.length ? `<button class="sx-link" data-selmode>${selMode ? "Bekor" : "Tanlash"}</button>` : ""}</div>`;
  const hls = `<div class="sx-hls">${(prof.hl || []).map((x) => `<button class="sx-hlc${x.id === h.hid ? " on" : ""}" data-hl="${esc(x.id)}"><span class="c"><i style="${x.c ? `background-image:url('${esc(x.c)}')` : `background:${grad(x.title)}`}"></i></span><small>${esc(x.title || "Aktual")}</small></button>`).join("")}</div>`;
  const n = h.items ? h.items.length : h.n;
  const head = `<div class="sx-hlhead" style="margin-top:14px"><div class="big"><i style="${h.cover ? `background-image:url('${esc(h.cover)}')` : `background:${grad(h.title)}`}"></i></div>
    <div><h4>${esc(h.title || "Aktual")}</h4><p>${n || 0} ta story${h.items ? ` · ${vids} video, ${h.items.length - vids} rasm` : ""}<br>@${esc(prof.u)}</p></div></div>`;
  if (h.err && !(h.items && h.items.length)) return top + hls + head + stateHTML(h.err, prof.u);
  if (!h.items) return top + hls + head + `<div class="sx-grid" style="margin-top:14px">${Array.from({length: 6}, () => '<div class="sx-th sx-skel"></div>').join("")}</div>`;
  return top + hls + head + `<div class="sx-acts"><button class="sx-btn ig" data-playall>▶ Ketma-ket ko'rish</button>
    <button class="sx-btn sec" data-sendall>${I.dl()}Hammasi (${h.items.length})</button></div>
    <div class="sx-grid" style="margin-top:14px">${h.items.map((it, i) => tileHTML(it, i, "h")).join("")}</div>`;
}

// ------------------------------------------------------------------ tanlash va yuborish
function selbarHTML() {
  return `<div class="sx-selbar"><b>${sel.size ? `${sel.size} ta tanlandi` : "Story'larni belgilang"}</b>
    <button class="sx-btn pri" data-sendsel ${sel.size ? "" : "disabled"}>${I.dl("#100E1C")}Chatga yuklash</button></div>`;
}
function curList() { const top = stack[stack.length - 1]; return top && top.v === "hl" ? (hlData.items || []) : (prof && prof.items || []); }
async function send(ids, retry = false) {
  if (!inTg) { toast("Ilovani Telegram ichida oching"); return; }
  const top = stack[stack.length - 1], hid = top && top.v === "hl" ? hlData.hid : null;
  if (!ids.length) return;
  haptic();
  let r;
  try { r = await api("api/story/send", {p: prof.p, u: prof.u, ids: ids.map(String), hl: hid, recheck: retry}); }
  catch (e) { toast("Internet bilan muammo — qayta urinib ko'ring"); return; }
  if (r.ok) {
    haptic("ok");
    toast(r.dup ? "⏳ Allaqachon yuborilyapti" : `📥 ${ids.length} ta story chatga yuborilyapti`, 2800);
    const s = saved(); s.unshift({p: prof.p, u: prof.u, name: prof.name || "", n: ids.length, at: Math.floor(Date.now() / 1000), hl: hid ? hlData.title : ""});
    lsSet("zk_st_saved", s.slice(0, 40));
    selMode = false; sel.clear(); render();
    return;
  }
  haptic("err");
  if (r.error === "need_sub") return showSub(r.channels || [], ids);
  if (r.error === "need_start") { toast("🤖 Avval botni ishga tushiring"); if (botName) tg.openTelegramLink(`https://t.me/${botName}?start=story`); return; }
  const msg = {rate_user: "Bir soatda ko'pi bilan 40 marta yuklash mumkin", expired: "Ro'yxat eskirdi — profilni qayta oching",
    down: "Xizmat vaqtincha ishlamayapti", auth: "Ilovani bot ichidan oching"};
  toast(msg[r.error] || "Yuborib bo'lmadi, qayta urinib ko'ring", 3000);
}
function showSub(chans, ids) {
  let bg = $("sxsbg"), sh = $("sxsheet");
  if (!bg) {
    bg = document.createElement("div"); bg.id = "sxsbg"; bg.className = "sx-sbg"; document.body.appendChild(bg);
    sh = document.createElement("div"); sh.id = "sxsheet"; sh.className = "sx-sheet"; sh.setAttribute("role", "dialog"); document.body.appendChild(sh);
    bg.onclick = hideSub;
  }
  sh.innerHTML = `<h3>Bir qadam qoldi</h3><p>Story'larni olish uchun quyidagi kanal(lar)ga a'zo bo'ling, so'ng «Tekshirish»ni bosing.</p>
    ${chans.map((c, i) => `<button class="ch" data-u="${i}"><span>📢 ${esc(c.title)}</span><span>A'zo bo'lish ›</span></button>`).join("")}
    <button class="sx-btn pri" id="sxrecheck">A'zo bo'ldim — tekshirish</button>`;
  sh.querySelectorAll(".ch").forEach((b) => b.onclick = () => { const u = chans[+b.dataset.u].url; /^https:\/\/t\.me\//.test(u) ? tg.openTelegramLink(u) : tg.openLink(u); });
  $("sxrecheck").onclick = () => { hideSub(); send(ids, true); };
  requestAnimationFrame(() => { bg.classList.add("open"); sh.classList.add("open"); });
}
function hideSub() { $("sxsbg") && $("sxsbg").classList.remove("open"); $("sxsheet") && $("sxsheet").classList.remove("open"); }

// ------------------------------------------------------------------ kuzatuv
async function toggleWatch() {
  if (!inTg) { toast("Ilovani Telegram ichida oching"); return; }
  const pr = prof, w = isWatched(pr.p, pr.u);
  const ts = (pr.items || []).reduce((m, x) => Math.max(m, x.ts || 0), 0);
  haptic();
  const r = await api("api/story/watch", {p: pr.p, u: pr.u, title: pr.name || "", ts: ts || Math.floor(Date.now() / 1000), act: w ? "del" : "add"}).catch(() => null);
  if (!r) { toast("Internet bilan muammo"); return; }
  if (!r.ok) { toast(r.error === "watch_full" ? `Kuzatuvga ko'pi bilan ${r.max} ta profil qo'shiladi` : "Saqlab bo'lmadi"); return; }
  me.watch = r.watch; haptic("ok");
  toast(w ? "Kuzatuvdan olindi" : "🔔 Yangi story chiqsa, bot xabar beradi", 2600);
  render();
}
function watchHTML() {
  const w = me.watch;
  return `${segHTML()}<div class="sx-top"><div class="sx-ttl">Kuzatuv ro'yxati</div>
    <button class="sx-ib" data-tab="home" aria-label="Profil qo'shish">${I.plus}</button></div>
    <div style="padding:0 18px;color:var(--mute);font-size:13px">Yangi story chiqsa, bot sizga yozadi · ${w.length}/${me.max}</div>
    ${w.length ? `<div class="sx-list" style="margin-top:12px">${w.map((x) => `<div class="sx-li"><button style="display:contents" data-open="${x.p}:${esc(x.u)}">${ring(x.p, x.title || x.u, "")}
      <span class="t"><b>${esc(x.title || x.u)}</b><span>${x.p === "ig" ? "Instagram · @" + esc(x.u) : "Telegram · @" + esc(x.u)}</span></span></button>
      <button class="sx-tog${x.on ? " on" : ""}" data-notify="${x.p}:${esc(x.u)}" role="switch" aria-checked="${x.on}" aria-label="Xabar berish"></button>
      <button class="sx-del" data-unwatch="${x.p}:${esc(x.u)}" aria-label="Ro'yxatdan olib tashlash">${I.trash}</button></div>`).join("")}</div>`
    : `<div class="sx-st"><div class="ic">${I.navWatch.replace("currentColor", "#C9C3EA")}</div><h4>Ro'yxat bo'sh</h4>
       <p>Profilni oching va «Kuzatish»ni bosing — yangi story qo'yilishi bilan bot xabar beradi.</p>
       <button class="sx-btn ig" data-tab="home">Profil qidirish</button></div>`}
    <div class="sx-h"><h3>Botdan keladigan xabar</h3><span>namuna</span></div>
    <div class="sx-bub"><div class="h"><i></i>${esc(botName || "bot")}</div>
      <div class="msg">🔔 <b>profil_nomi</b> yangi story qo'ydi<div class="tt"><span>👁 Ko'rish</span><span>⬇️ Yuklash</span></div></div></div>`;
}
async function watchAct(spec, act, on) {
  const [p, u] = spec.split(/:(.+)/);
  const r = await api("api/story/watch", {p, u, act, on}).catch(() => null);
  if (r && r.ok) { me.watch = r.watch; render(); } else toast("Saqlab bo'lmadi");
}

// ------------------------------------------------------------------ yuklanganlar
function savedHTML() {
  const s = saved();
  return `${segHTML()}<div class="sx-top"><div class="sx-ttl">Yuklanganlar</div>${s.length ? '<button class="sx-link" data-clearsaved>Tozalash</button>' : ""}</div>
    <div style="padding:0 18px;color:var(--mute);font-size:13px">Chatga yuborilgan story'lar tarixi — fayllar bot chatida turadi</div>
    ${s.length ? `<div class="sx-list" style="margin-top:12px">${s.map((x) => `<button class="sx-li" data-open="${x.p}:${esc(x.u)}">${ring(x.p, x.name || x.u, "")}
      <span class="t"><b>${esc(x.name || x.u)}${x.hl ? " · " + esc(x.hl) : ""}</b><span>${x.n} ta story · ${ago(x.at)}</span></span>
      <span class="sx-pill ${x.p}">${x.p.toUpperCase()}</span></button>`).join("")}</div>
      ${botName ? `<div style="padding:14px 16px"><button class="sx-btn sec" style="width:100%" data-openbot>Bot chatini ochish</button></div>` : ""}`
    : `<div class="sx-st"><div class="ic">${I.dl("#C9C3EA")}</div><h4>Hali hech narsa yuklanmagan</h4>
       <p>Story'ni ochib «Chatga yuklash»ni bosing — fayl bot chatiga keladi va shu yerda tarix ko'rinadi.</p>
       <button class="sx-btn ig" data-tab="home">Story qidirish</button></div>`}`;
}

// ------------------------------------------------------------------ ko'ruvchi
const V = {list: [], i: 0, t0: 0, dur: 5000, raf: 0, paused: false, held: false, muted: lsGet("zk_st_mute", false), src: "p", el: null, ready: false, startY: null};
function openViewer(list, i, src) {
  V.list = list; V.i = i; V.src = src;
  let el = $("sxv");
  if (!el) { el = document.createElement("div"); el.id = "sxv"; el.className = "sx-v"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", "Story ko'ruvchi"); document.body.appendChild(el); bindViewer(el); }
  V.el = el; el.hidden = false; el.style.transform = ""; el.style.opacity = "";
  try { tg.setHeaderColor("#000000"); } catch (e) {}
  show(); updateBack();
}
function closeViewer() {
  if (!V.el || V.el.hidden) return;
  cancelAnimationFrame(V.raf); const v = V.el.querySelector("video"); if (v) { v.pause(); v.removeAttribute("src"); v.load(); }
  V.el.hidden = true; V.el.innerHTML = "";
  try { tg.setHeaderColor("#100E1C"); } catch (e) {}
  updateBack();
}
async function show() {
  cancelAnimationFrame(V.raf);
  const it = V.list[V.i], pr = prof; if (!it) return closeViewer();
  V.ready = false; V.paused = false; V.el.classList.remove("hold");
  const name = pr.p === "tg" ? (pr.name || pr.u) : pr.u;
  V.el.innerHTML = `<div class="media"><div class="sx-spin"></div></div><div class="shade"></div>
    <div class="sx-prog">${V.list.map((_, j) => `<i class="${j < V.i ? "d" : ""}"><b></b></i>`).join("")}</div>
    <div class="vh">${ring(pr.p, pr.u, pr.pic)}<div class="nm"><b>${esc(name)}</b><span>${esc(ago(it.ts))}${V.src === "h" ? " · " + esc(hlData.title) : ""}</span></div>
      ${it.k === "video" ? `<button data-vmute aria-label="Ovoz">${V.muted ? I.mute : I.vol}</button>` : ""}
      <button data-vclose aria-label="Yopish">${I.close}</button></div>
    <div class="anon">${I.anon()}Anonim ko'rilmoqda</div>
    <div class="paused">${I.pause}</div>
    <div class="tapl"></div><div class="tapr"></div>
    ${it.cap ? `<div class="cap">${esc(it.cap)}</div>` : ""}
    <div class="vbot"><button class="sx-btn pri" data-vsend>${I.dl("#100E1C")}Chatga yuklash</button>
      <button class="sx-btn glass" data-vshare>${I.share}Ulashish</button></div>`;
  const media = V.el.querySelector(".media"), idx = V.i;
  let src = it.s;
  if (pr.p === "tg" && it.k === "video") {
    if (it.big) { media.innerHTML = `<div style="color:#fff;text-align:center;padding:30px">Video juda katta — «Chatga yuklash» orqali oling</div>`; startTimer(5000); return; }
    src = await tgMedia(pr.u, it.id);
    if (V.i !== idx || V.el.hidden) return;
    if (!src) { media.innerHTML = `<div style="color:#fff;text-align:center;padding:30px">Videoni ochib bo'lmadi — «Chatga yuklash» orqali oling</div>`; startTimer(4000); return; }
  }
  if (it.k === "video") {
    const v = document.createElement("video");
    v.playsInline = true; v.setAttribute("playsinline", ""); v.muted = V.muted; v.preload = "auto"; v.poster = it.t; v.src = src;
    v.onloadeddata = () => { if (V.i !== idx) return; media.querySelector(".sx-spin")?.remove(); V.ready = true; v.play().catch(() => { v.muted = true; V.muted = true; v.play().catch(() => {}); }); startTimer((v.duration || it.d || 15) * 1000, v); };
    v.onended = () => next();
    v.onerror = () => { if (V.i === idx) { media.innerHTML = `<div style="color:#fff;text-align:center;padding:30px">Video yuklanmadi</div>`; startTimer(3000); } };
    media.appendChild(v);
  } else {
    const img = new Image(); img.alt = "";
    img.onload = () => { if (V.i !== idx) return; media.innerHTML = ""; media.appendChild(img); V.ready = true; startTimer(5000); };
    img.onerror = () => { if (V.i === idx) { media.innerHTML = `<div style="color:#fff;text-align:center;padding:30px">Rasm yuklanmadi</div>`; startTimer(3000); } };
    img.src = src;
  }
  // keyingisini oldindan yuklash
  const nx = V.list[V.i + 1];
  if (nx && nx.k === "photo") { const p = new Image(); p.src = nx.s; }
}
async function tgMedia(u, id) {
  const t0 = Date.now();
  for (;;) {
    const r = await api(`api/story/tgm?u=${encodeURIComponent(u)}&id=${id}`).catch(() => null);
    if (r && r.src) return r.src;
    if (!r || !r.ok || Date.now() - t0 > 45000 || V.el.hidden) return null;
    await sleep(1200);
  }
}
function startTimer(ms, video) {
  V.dur = ms; V.t0 = performance.now(); V.elapsed = 0;
  const bar = V.el.querySelectorAll(".sx-prog i b")[V.i];
  const tick = (now) => {
    if (!V.paused) {
      const p = video ? (video.currentTime / (video.duration || 1)) : Math.min(1, (V.elapsed + now - V.t0) / V.dur);
      if (bar) bar.style.width = (p * 100).toFixed(2) + "%";
      if (!video && p >= 1) { next(); return; }
    }
    V.raf = requestAnimationFrame(tick);
  };
  cancelAnimationFrame(V.raf); V.raf = requestAnimationFrame(tick);
}
function pause(on) {
  if (V.paused === on) return;
  V.paused = on; V.el.classList.toggle("hold", on);
  const v = V.el.querySelector("video");
  if (on) { V.elapsed += performance.now() - V.t0; if (v) v.pause(); }
  else { V.t0 = performance.now(); if (v && V.ready) v.play().catch(() => {}); }
}
function next() { if (V.i < V.list.length - 1) { V.i++; show(); } else closeViewer(); }
function prev() { if (V.i > 0) { V.i--; show(); } else { V.t0 = performance.now(); V.elapsed = 0; } }
function bindViewer(el) {
  let downAt = 0, sx = 0, sy = 0, holdT = 0, moved = false;
  el.addEventListener("pointerdown", (e) => {
    if (e.target.closest("button")) return;
    downAt = Date.now(); sx = e.clientX; sy = e.clientY; moved = false;
    holdT = setTimeout(() => pause(true), 220);
  });
  el.addEventListener("pointermove", (e) => {
    if (!downAt) return;
    const dy = e.clientY - sy, dx = e.clientX - sx;
    if (Math.abs(dy) > 12 || Math.abs(dx) > 12) { moved = true; clearTimeout(holdT); }
    if (dy > 0 && Math.abs(dy) > Math.abs(dx)) { el.style.transform = `translateY(${dy}px) scale(${1 - Math.min(dy, 300) / 1500})`; el.style.opacity = String(1 - Math.min(dy, 400) / 600); }
  });
  const up = (e) => {
    if (!downAt) return;
    clearTimeout(holdT);
    const dy = e.clientY - sy, dx = e.clientX - sx, quick = Date.now() - downAt < 220;
    downAt = 0;
    if (V.paused) pause(false);
    if (moved) {
      if (dy > 110 && Math.abs(dy) > Math.abs(dx)) { closeViewer(); return; }
      el.style.transform = ""; el.style.opacity = "";
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)) dx < 0 ? next() : prev();
      return;
    }
    if (!quick) return;
    if (e.target.closest(".tapl")) prev(); else if (e.target.closest(".tapr") || e.target.closest(".media")) next();
  };
  el.addEventListener("pointerup", up);
  el.addEventListener("pointercancel", (e) => { clearTimeout(holdT); downAt = 0; el.style.transform = ""; el.style.opacity = ""; if (V.paused) pause(false); void e; });
  el.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.hasAttribute("data-vclose")) closeViewer();
    else if (b.hasAttribute("data-vmute")) { V.muted = !V.muted; lsSet("zk_st_mute", V.muted); const v = el.querySelector("video"); if (v) v.muted = V.muted; b.innerHTML = V.muted ? I.mute : I.vol; }
    else if (b.hasAttribute("data-vsend")) { const it = V.list[V.i]; pause(true); send([String(it.id)]).finally(() => pause(false)); }
    else if (b.hasAttribute("data-vshare")) share();
  });
  document.addEventListener("keydown", (e) => {
    if (el.hidden) return;
    if (e.key === "Escape") closeViewer(); else if (e.key === "ArrowRight") next(); else if (e.key === "ArrowLeft") prev();
  });
}
function share() {
  const pr = prof;
  const sp = `st_${pr.p}_${pr.u.replace(/\./g, "-")}`;
  const link = botName ? `https://t.me/${botName}?startapp=${sp}` : (pr.p === "ig" ? `https://instagram.com/${pr.u}` : `https://t.me/${pr.u}`);
  const text = `👻 @${pr.u} story'larini anonim ko'ring`;
  try { tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`); }
  catch (e) { try { navigator.clipboard.writeText(link); toast("Havola nusxalandi"); } catch (e2) {} }
}

// ------------------------------------------------------------------ hodisalar
function back() {
  if (V.el && !V.el.hidden) { closeViewer(); return true; }
  if ($("sxsheet") && $("sxsheet").classList.contains("open")) { hideSub(); return true; }
  if (selMode) { selMode = false; sel.clear(); render(); return true; }
  if (stack.length) {
    const was = stack.pop(); pollTok++;
    if (was.v === "hl") hlData = null;
    const top = stack[stack.length - 1];
    if (top && top.v === "profile" && (!prof || prof.u !== top.u)) openProfile(top.p, top.u, false); else render();
    return true;
  }
  return false;
}
function onClick(e) {
  const t = e.target.closest("button, [data-open]"); if (!t || !$("sxview").contains(t)) return;
  const d = t.dataset;
  if (d.mode) { if (d.mode !== "story" && window.ZK_setMode) window.ZK_setMode(d.mode); return; }
  if (d.tab) { tab = d.tab; stack = []; prof = null; selMode = false; render(); if (tab === "home") setTimeout(() => $("sxq") && $("sxq").focus(), 50); return; }
  if (d.plat) {
    const first = !picked; plat = d.plat; picked = true; lsSet("zk_st_plat", plat); haptic(); render();
    if (first) setTimeout(() => { const q = $("sxq"); if (q) q.focus(); }, 80);
    return;
  }
  if (d.open) { const [p, u] = d.open.split(/:(.+)/); stack = []; openProfile(p, u); return; }
  if (t.hasAttribute("data-back")) { back(); return; }
  if (t.hasAttribute("data-clearhist")) { lsSet("zk_st_hist", []); render(); return; }
  if (d.delhist != null) { const h = hist(); h.splice(+d.delhist, 1); lsSet("zk_st_hist", h); render(); return; }
  if (t.hasAttribute("data-clearsaved")) { lsSet("zk_st_saved", []); render(); return; }
  if (t.hasAttribute("data-openbot")) { if (botName) tg.openTelegramLink(`https://t.me/${botName}`); return; }
  if (d.st === "home") { stack = []; prof = null; tab = "home"; render(); return; }
  if (d.st === "retry") { const top = stack[stack.length - 1]; if (top && top.v === "hl") { stack.pop(); openHL(top.hid); } else if (prof) openProfile(prof.p, prof.u, false); return; }
  if (t.hasAttribute("data-watch")) { toggleWatch(); return; }
  if (d.hl) { const top = stack[stack.length - 1]; if (top && top.v === "hl") stack.pop(); openHL(d.hl); return; }
  if (t.hasAttribute("data-selmode")) { selMode = !selMode; sel.clear(); haptic(); render(); return; }
  if (t.hasAttribute("data-sendall")) { send(curList().map((x) => String(x.id))); return; }
  if (t.hasAttribute("data-sendsel")) { send([...sel]); return; }
  if (t.hasAttribute("data-playall")) { openViewer(curList(), 0, "h"); return; }
  if (d.notify) { watchAct(d.notify, "notify", !t.classList.contains("on")); return; }
  if (d.unwatch) { watchAct(d.unwatch, "del"); return; }
  if (d.i != null) {
    const list = curList(), it = list[+d.i]; if (!it) return;
    if (selMode) { const k = String(it.id); sel.has(k) ? sel.delete(k) : sel.add(k); haptic(); t.classList.toggle("on", sel.has(k)); document.querySelector(".sx-selbar").outerHTML = selbarHTML(); return; }
    openViewer(list, +d.i, d.src);
  }
}
// uzoq bosish — tanlash rejimi
let lpT = 0;
function onDown(e) {
  const th = e.target.closest(".sx-th[data-i]"); if (!th || selMode) return;
  lpT = setTimeout(() => { selMode = true; sel.clear(); sel.add(String(curList()[+th.dataset.i].id)); haptic("ok"); render(); lpT = -1; }, 450);
}
function onUp(e) { if (lpT > 0) clearTimeout(lpT); if (lpT === -1) { e.preventDefault(); lpT = 0; } }

function updateBack() {
  if (!inTg) return;
  const need = opened && ((V.el && !V.el.hidden) || stack.length || selMode);
  try { need ? tg.BackButton.show() : (window.ZK_canHideBack ? window.ZK_canHideBack() && tg.BackButton.hide() : tg.BackButton.hide()); } catch (e) {}
}
if (inTg) tg.BackButton.onClick(() => { if (opened) { back(); updateBack(); } });

let mounted = false;
function mount() {
  if (mounted) return; mounted = true;
  const v = $("sxview");
  v.addEventListener("click", onClick);
  v.addEventListener("pointerdown", onDown);
  v.addEventListener("pointerup", onUp, true);
  v.addEventListener("pointercancel", () => clearTimeout(lpT));
  v.addEventListener("contextmenu", (e) => { if (e.target.closest(".sx-th")) e.preventDefault(); });
}
async function loadMe() {
  try { const r = await api("api/story/me"); if (r && r.ok) { me = {...me, ...r}; if (opened && !stack.length) render(); } } catch (e) {}
}

window.ZStory = {
  open(spec) {
    mount(); opened = true;
    $("story").hidden = false; document.body.classList.add("s-on");
    try { tg.setHeaderColor("#100E1C"); tg.setBackgroundColor("#100E1C"); if (tg.setBottomBarColor) tg.setBottomBarColor("#14121F"); } catch (e) {}
    loadMe();
    if (spec) {
      const m = String(spec).match(/^(ig|tg)[:_](.+)$/);
      if (m) { tab = "home"; stack = []; openProfile(m[1], m[1] === "ig" ? m[2].replace(/-/g, ".") : m[2]); return; }
    }
    render();
  },
  close() {
    opened = false; closeViewer(); hideSub(); pollTok++;
    $("story").hidden = true; document.body.classList.remove("s-on");
    try { tg.setHeaderColor("bg_color"); tg.setBackgroundColor("bg_color"); if (tg.setBottomBarColor) tg.setBottomBarColor("bottom_bar_bg_color"); } catch (e) {}
    updateBack();
  },
  busy() { return opened && (stack.length > 0 || selMode || !!(V.el && !V.el.hidden)); },
  setBot(b) { botName = b || ""; },
};
void reduced;
})();
