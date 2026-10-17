/* 🎧 Musiqa — Mini App bo'limi (Atlas uslubi). index.html dan window.ZMusic orqali boshqariladi. */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success")
  : t === "err" ? tg.HapticFeedback.notificationOccurred("error")
  : t === "hit" ? tg.HapticFeedback.impactOccurred("light") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const lsGet = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const toast = (t, ms = 2200) => { const el = $("toast"); el.textContent = t; el.classList.add("on");
  clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove("on"), ms); };
const dur = (s) => { s = Math.max(0, Math.floor(s || 0)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}` : `${m}:${String(x).padStart(2, "0")}`; };
const hash = (s) => { let h = 2166136261; for (const c of String(s)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
const rnd = (seed) => () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

const P = {mag: "#E0337A", saf: "#F7B32B", eme: "#18A999", ind: "#4B47D6", sky: "#5FB4FF", plum: "#7A2E8E", ivory: "#F6E7C8"};
const ICON = {
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.14v13.72a1 1 0 0 0 1.52.85l11-6.86a1 1 0 0 0 0-1.7l-11-6.86A1 1 0 0 0 8 5.14z"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4.5" width="4.2" height="15" rx="1.4"/><rect x="13.8" y="4.5" width="4.2" height="15" rx="1.4"/></svg>',
  next: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M5 6.2v11.6a1 1 0 0 0 1.55.83l8.7-5.8a1 1 0 0 0 0-1.66l-8.7-5.8A1 1 0 0 0 5 6.2z"/><rect x="16.6" y="5" width="2.6" height="14" rx="1.2"/></svg>',
  prev: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.2v11.6a1 1 0 0 1-1.55.83l-8.7-5.8a1 1 0 0 1 0-1.66l8.7-5.8A1 1 0 0 1 19 6.2z"/><rect x="4.8" y="5" width="2.6" height="14" rx="1.2"/></svg>',
  shuffle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h4v4M4 20 20 4M20 16v4h-4M15 15l5 5M4 4l5 5"/></svg>',
  repeat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/></svg>',
  down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>',
  dots: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2.5" width="6" height="12" rx="3" fill="#fff"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3.5"/></svg>',
  heart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 7.9 3.6 4.5 7 4.5c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3 3.4 0 5.6 3.4 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z"/></svg>',
  dl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 10.5 12 15.5l5-5M5 20h14"/></svg>',
  share: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7.5 7.5 12 3l4.5 4.5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>',
  queue: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 6h12M4 12h12M4 18h8"/><path d="M17 15.5v5l4-2.5z" fill="currentColor"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.2-4 4.3-6 8-6s6.8 2 8 6"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  addq: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 6h12M4 12h8M4 18h8M18 12v8M14 16h8"/></svg>',
};

// =================================================================== atlas (ikat) naqshi
const _ikat = new Map();
function ikat(cols, seed = 1, w = 240, h = 240, dens = 3) {
  const key = cols.join() + seed + w + h + dens;
  if (_ikat.has(key)) return _ikat.get(key);
  const r = rnd(seed * 7919 + 13), colw = w / dens; let sh = "";
  for (let i = 0; i < dens; i++) {
    const c = cols[i % (cols.length - 1)], c2 = cols[(i + 1) % (cols.length - 1)], x = i * colw + colw / 2;
    let y = -40 - r() * 30;
    while (y < h + 40) {
      const hh = 46 + r() * 34, ww = colw * (0.55 + r() * 0.4);
      sh += `<polygon points="${x},${y} ${x + ww / 2},${y + hh / 2} ${x},${y + hh} ${x - ww / 2},${y + hh / 2}" fill="${c}"/>` +
        `<polygon points="${x},${y + hh * .3} ${x + ww / 4},${y + hh / 2} ${x},${y + hh * .7} ${x - ww / 4},${y + hh / 2}" fill="${c2}"/>`;
      y += hh - 6;
    }
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">` +
    `<defs><filter id="f" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency="0.02 0.25" numOctaves="2" seed="${seed % 97}"/>` +
    `<feDisplacementMap in="SourceGraphic" scale="14" xChannelSelector="R" yChannelSelector="G"/><feGaussianBlur stdDeviation="0.8 2.2"/></filter></defs>` +
    `<rect width="100%" height="100%" fill="${cols[cols.length - 1]}"/><g filter="url(#f)">${sh}</g></svg>`;
  const uri = `url('data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg).replace(/'/g, "%27")}')`;
  _ikat.set(key, uri);
  return uri;
}
const PALS = [[P.mag, P.saf, P.ind, "#2a0f3d"], [P.eme, P.ivory, P.plum, "#0f2a33"], [P.saf, P.mag, P.eme, "#3a1408"],
  [P.sky, P.ind, P.saf, "#121640"], [P.plum, P.saf, P.sky, "#200d2e"], [P.mag, P.eme, P.ivory, "#2b0b1c"]];
const ikatFor = (s, w, h, d) => { const hsh = hash(s); return ikat(PALS[hsh % PALS.length], hsh % 1000 + 1, w, h, d); };

// =================================================================== trek ma'lumotlari
const JUNK = /[([](?=[^)\]]*(?:official|video|audio|lyric|клип|clip|\bmv\b|\bhd\b|\b4k\b|премьер|premiere|visuali[sz]er|текст|rasmiy|tizer|teaser|music\s*video|full\s*version|\bnew\b|yangi\s*klip|\d{4}\s*$))[^)\]]*[)\]]/gi;
function parse(it) {
  if (it._p) return it._p;
  if (it.m) { it._p = {song: it.t || "—", artist: it.a || "Noma'lum ijrochi"}; return it._p; }   // YouTube Music: aniq ma'lumot
  let t = String(it.t || "").replace(JUNK, " ").replace(/#[^\s#]+/g, " ").replace(/\s*[|｜].*$/, "")
    .replace(/[“”«»"]/g, "").replace(/\s{2,}/g, " ").trim();
  let ch = String(it.a || "").replace(/\s*-\s*topic$/i, "").replace(/vevo$/i, "")
    .replace(/\b(official|music|channel|rasmiy|tv|kanal|канал|music\s*uz)\b/gi, "").replace(/\s{2,}/g, " ").trim();
  let song = t, artist = ch;
  const m = t.split(/\s+[-–—]\s+/);
  if (m.length >= 2 && m[0].length <= 60) { artist = m[0].trim(); song = m.slice(1).join(" - ").trim(); }
  if (!song) song = it.t || "—";
  it._p = {song, artist: artist || "Noma'lum ijrochi"};
  return it._p;
}
const keyOf = (it) => `${it.s || "yt"}_${it.id}`;
const slim = (it) => { const o = {id: it.id, t: it.t, a: it.a, d: it.d, s: it.s || "yt", u: it.u};
  if (it.c) o.c = it.c; if (it.m) o.m = 1; if (it.al) o.al = it.al; if (it.y) o.y = it.y; if (it.lib) o.lib = 1; return o; };
const ytOf = (it) => (it.s || "yt") === "yt" ? it.id : it.y || "";
const thumb = (it, big) => it.c ? (big ? it.c.replace(/=w\d+-h\d+/, "=w544-h544") : it.c) : ytOf(it) ? `https://i.ytimg.com/vi/${ytOf(it)}/${big ? "hqdefault" : "mqdefault"}.jpg` : "";
function coverHTML(it, cls = "", big = false) {
  const src = thumb(it, big);
  return `<div class="m-cv ${cls}" style="background-image:${ikatFor(it.id, 120, 120)}">${src
    ? `<img src="${esc(src)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer"${big ? ' data-big="1"' : ""}>` : ""}</div>`;
}
// hqdefault — 4:3 (yuqori/pastki qora chiziq). Katta muqova uchun markazdan kvadrat kesamiz.
document.addEventListener("load", (e) => {
  const img = e.target;
  if (img.tagName !== "IMG" || !img.closest(".m-cv")) return;
  if (img.naturalWidth <= 120 && img.src.includes("ytimg")) { img.remove(); return; }  // "rasm yo'q" zaglushkasi
  if (img.dataset.big && img.src.includes("ytimg")) img.style.cssText = "transform:scale(1.34)";
  img.classList.add("ok");
}, true);
document.addEventListener("error", (e) => { const img = e.target; if (img.tagName === "IMG" && img.closest(".m-cv")) img.remove(); }, true);

// =================================================================== holat
let favs = lsGet("zk_mfav", []), hist = lsGet("zk_mhist", []), recentQ = lsGet("zk_mq", []);
const isFav = (it) => favs.some((x) => keyOf(x) === keyOf(it));
function toggleFav(it) {
  const k = keyOf(it), on = !isFav(it);
  favs = on ? [slim(it), ...favs].slice(0, 500) : favs.filter((x) => keyOf(x) !== k);
  lsSet("zk_mfav", favs); haptic(on ? "ok" : "hit");
  toast(on ? "❤️ Saqlanganlarga qo'shildi" : "Saqlanganlardan olib tashlandi", 1400);
  return on;
}
function addHist(it) {
  const k = keyOf(it);
  hist = [slim(it), ...hist.filter((x) => keyOf(x) !== k)].slice(0, 120);
  lsSet("zk_mhist", hist);
}

let home = null, bot = "", opened = false, mounted = false;
const stack = [];               // ko'rinishlar: {v:"home"|"search"|"list", ...}
const lists = new Map();        // ro'yxat id → treklar (qatorlarni bosish uchun)
let listSeq = 0;
const regList = (arr) => { const id = "L" + (++listSeq); lists.set(id, arr); if (lists.size > 40) lists.delete(lists.keys().next().value); return id; };

async function api(path, opts = {}) {
  const headers = Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, opts.json ? {"Content-Type": "application/json"} : {});
  const r = await fetch(path, {method: opts.json || opts.body ? "POST" : "GET", headers,
    body: opts.json ? JSON.stringify(opts.json) : opts.body, signal: opts.signal});
  if (r.status === 401) return {ok: false, error: "auth"};
  return r.json();
}
const searchCache = new Map();
async function search(q, n = 15, signal) {
  const k = n + ":" + q.toLowerCase();
  if (searchCache.has(k)) return searchCache.get(k);
  const r = await api(`api/music/search?q=${encodeURIComponent(q)}&n=${n}`, {signal});
  if (!r.ok) throw new Error(r.error || "err");
  searchCache.set(k, r.items);
  return r.items;
}

// =================================================================== audio dvigatel
const audio = new Audio();
audio.preload = "auto";
audio.setAttribute("playsinline", "");
let queue = [], qi = -1, qName = "", shuffle = lsGet("zk_mshuf", false), repeat = lsGet("zk_mrep", 0);  // 0 yo'q, 1 hammasi, 2 bitta
let order = [], loadingKey = "", token = 0, unlocked = false, failStreak = 0;
const urlCache = new Map();     // kalit → {url, at}
const URL_TTL = 5 * 3600e3;

// iOS: birinchi bosishda audio "ochiladi" — keyin tarmoqdan kelgan qo'shiq o'zi boshlanadi
const SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
function unlock() {
  if (unlocked) return;
  unlocked = true;
  try { if (!audio.src) { audio.src = SILENT; const p = audio.play(); p && p.then(() => audio.pause()).catch(() => {}); } } catch (e) {}
}

async function prepare(it, signal) {
  const k = keyOf(it), c = urlCache.get(k);
  if (c && Date.now() - c.at < URL_TTL) return c.url;
  const r = await api("api/music/play", {json: slim(it), signal});
  if (!r.ok) { const e = new Error(r.error || "err"); e.code = r.error; throw e; }
  urlCache.set(k, {url: r.url, at: Date.now()});
  return r.url;
}

function buildOrder(start) {
  order = queue.map((_, i) => i);
  if (shuffle) {
    order.splice(order.indexOf(start), 1);
    for (let i = order.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [order[i], order[j]] = [order[j], order[i]]; }
    order.unshift(start);
  }
}
const pos = () => order.indexOf(qi);
const peekNext = () => { const p = pos(); if (p < 0) return null; if (p + 1 < order.length) return queue[order[p + 1]]; return repeat === 1 && order.length > 1 ? queue[order[0]] : null; };

function playList(list, i = 0, name = "") {
  unlock();
  queue = list.map(slim); qName = name; buildOrder(i);
  load(i);
}
const cur = () => queue[qi] || null;

async function load(i, autoplay = true) {
  const it = queue[i]; if (!it) return;
  qi = i; const my = ++token;
  loadingKey = keyOf(it);
  addHist(it);
  audio.pause();
  setLoading(true); paintAll(); updateMedia(it);
  let url;
  try { url = await prepare(it); }
  catch (e) {
    if (my !== token) return;
    setLoading(false); loadingKey = ""; paintAll();
    const msg = {rate: "⏳ Juda ko'p tinglandi — birozdan keyin urinib ko'ring", auth: "⚠️ Ilovani yopib, qayta oching",
      too_long: "Bu juda uzun yozuv", too_large: "Fayl juda katta"}[e.code];
    if (msg) { toast(msg, 3000); haptic("err"); return; }
    failStreak++;
    if (failStreak <= 3 && peekNext()) { toast("😔 Bu qo'shiq ochilmadi — keyingisi", 1800); next(true); }
    else { toast("😔 Qo'shiqni ochib bo'lmadi. Internetni tekshiring", 3000); haptic("err"); failStreak = 0; }
    return;
  }
  if (my !== token) return;
  audio.src = url;
  audio.currentTime = 0;
  if (autoplay) {
    try { await audio.play(); failStreak = 0; }
    catch (e) { if (my === token) { setLoading(false); loadingKey = ""; paintAll(); } }
  }
  prefetchNext();
}
function prefetchNext() {
  const n = peekNext();
  if (n && !urlCache.has(keyOf(n))) setTimeout(() => prepare(n).catch(() => {}), 1500);
}
function next(auto = false) {
  if (!queue.length) return;
  const p = pos();
  if (!auto && audio.currentTime > 0 && repeat === 2) { /* qo'lda "keyingi" — bitta takrorlashdan chiqadi */ }
  let np = p + 1;
  if (np >= order.length) {
    if (repeat === 1 || !auto) np = 0; else { audio.pause(); audio.currentTime = 0; paintAll(); return; }
  }
  load(order[np]);
}
function prev() {
  if (!queue.length) return;
  if (audio.currentTime > 4) { audio.currentTime = 0; return; }
  const p = pos();
  load(order[p > 0 ? p - 1 : (repeat === 1 ? order.length - 1 : 0)]);
}
function toggle() {
  unlock();
  if (!cur()) return;
  if (loadingKey) return;
  if (audio.paused) {
    if (!audio.src || audio.src === SILENT || audio.error) { load(qi); return; }
    audio.play().catch(() => load(qi));
  } else audio.pause();
  haptic("hit");
}
audio.addEventListener("playing", () => { setLoading(false); loadingKey = ""; paintAll(); });
audio.addEventListener("waiting", () => { if (!audio.paused) setLoading(true); });
audio.addEventListener("pause", paintAll);
audio.addEventListener("play", paintAll);
audio.addEventListener("ended", () => {
  if (repeat === 2) { audio.currentTime = 0; audio.play().catch(() => {}); return; }
  next(true);
});
audio.addEventListener("error", () => {
  if (!cur() || !audio.src || audio.src === SILENT) return;
  // imzo eskirgan yoki fayl keshdan o'chgan — qaytadan tayyorlab, shu joydan davom etamiz
  const k = keyOf(cur()), at = audio.currentTime;
  if (urlCache.has(k)) {
    urlCache.delete(k);
    const my = token;
    prepare(cur()).then((u) => { if (my !== token) return; audio.src = u; audio.currentTime = at; audio.play().catch(() => {}); })
      .catch(() => { setLoading(false); loadingKey = ""; paintAll(); });
  } else { setLoading(false); loadingKey = ""; paintAll(); }
});
let lastPaint = 0;
audio.addEventListener("timeupdate", () => {
  const now = performance.now(); if (now - lastPaint < 240) return; lastPaint = now;
  paintProgress();
});
audio.addEventListener("loadedmetadata", paintProgress);

// Lock-screen / bildirishnoma boshqaruvi
function updateMedia(it) {
  if (!("mediaSession" in navigator) || !it) return;
  const p = parse(it), art = thumb(it, true);
  try {
    navigator.mediaSession.metadata = new MediaMetadata({title: p.song, artist: p.artist, album: qName || "Zakirovs Musiqa",
      artwork: art ? [{src: art, sizes: "480x360", type: "image/jpeg"}] : []});
  } catch (e) {}
}
if ("mediaSession" in navigator) {
  const ms = navigator.mediaSession, set = (a, f) => { try { ms.setActionHandler(a, f); } catch (e) {} };
  set("play", () => toggle()); set("pause", () => audio.pause());
  set("nexttrack", () => next()); set("previoustrack", () => prev());
  set("seekto", (d) => { if (d.seekTime != null) audio.currentTime = d.seekTime; });
}

// =================================================================== chizish (holatni yangilash)
let isLoading = false;
function setLoading(on) { isLoading = on; $("mpplay").classList.toggle("load", on); }
const playing = () => !audio.paused && !isLoading;
function paintAll() {
  const it = cur(), k = it ? keyOf(it) : "";
  // ro'yxatlardagi joriy qator
  document.querySelectorAll(".m-tr").forEach((r) => {
    const on = r.dataset.k === k;
    r.classList.toggle("cur", on);
    r.classList.toggle("load", on && !!loadingKey);
    const eq = r.querySelector(".m-eq");
    if (on && !eq) { const d = r.querySelector(".d"); d && (d.outerHTML = `<span class="m-eq"><i></i><i></i><i></i><i></i></span>`); }
    const e2 = r.querySelector(".m-eq"); if (e2) e2.classList.toggle("on", on && playing());
    if (!on && eq) eq.outerHTML = `<span class="d">${r.dataset.d || ""}</span>`;
  });
  // mini pleyer
  const mini = $("mmini");
  document.body.classList.toggle("m-hasmini", !!it);
  if (!it) { mini.hidden = true; $("mus").classList.add("nomini"); return; }
  mini.hidden = false; $("mus").classList.remove("nomini");
  const p = parse(it);
  if (mini.dataset.k !== k) {
    mini.dataset.k = k;
    $("mmcv").outerHTML = coverHTML(it).replace('class="m-cv ', 'id="mmcv" class="m-cv ');
    $("mmt").textContent = p.song; $("mma").textContent = p.artist;
  }
  const pi = playing() || isLoading ? ICON.pause : ICON.play;
  if ($("mmplay").innerHTML !== pi) $("mmplay").innerHTML = pi;
  paintPlayer();
}
function paintPlayer() {
  const it = cur(); if (!it) return;
  const k = keyOf(it), p = parse(it), pl = $("mplayer");
  if (pl.dataset.k !== k) {
    pl.dataset.k = k;
    $("mbig").outerHTML = coverHTML(it, "m-big", true).replace('class="m-cv ', 'id="mbig" class="m-cv ');
    const bg = thumb(it, false);
    $("mbgc").style.backgroundImage = bg ? `url('${bg}'),${ikatFor(it.id, 120, 120)}` : ikatFor(it.id, 120, 120);
    $("mpt").textContent = p.song; $("mpa").textContent = p.artist;
    $("mpheart").classList.toggle("on", isFav(it));
    waveSeed = hash(it.id); drawWave();
    $("mpsrc").textContent = qName ? `${qName}` : "Hozir ijroda";
  }
  $("mbig").classList.toggle("paused", !playing() && !isLoading);
  const pi = playing() || isLoading ? ICON.pause : ICON.play;
  if ($("mpplay").innerHTML !== pi) $("mpplay").innerHTML = pi;
  $("mpshuf").classList.toggle("on", shuffle);
  $("mprep").classList.toggle("on", repeat > 0); $("mprep").classList.toggle("one", repeat === 2);
  const n = peekNext();
  $("mpnext").hidden = !n;
  if (n && $("mpnext").dataset.k !== keyOf(n)) {
    $("mpnext").dataset.k = keyOf(n);
    const np = parse(n);
    $("mpnext").innerHTML = coverHTML(n) + `<div class="t"><small>Keyingisi</small><b>${esc(np.song)} · ${esc(np.artist)}</b></div>${ICON.next.replace("<svg", '<svg style="width:20px;height:20px;color:var(--m-mute)"')}`;
  }
  paintProgress();
}
function paintProgress() {
  const d = audio.duration && isFinite(audio.duration) ? audio.duration : (cur()?.d || 0);
  const t = scrubbing ? scrubT : audio.currentTime || 0;
  const f = d ? Math.min(1, t / d) : 0;
  $("mmpr").style.width = (f * 100).toFixed(2) + "%";
  if (!$("mplayer").classList.contains("open")) return;
  $("mpcur").textContent = dur(t); $("mpdur").textContent = d ? dur(d) : "--:--";
  waveF = f; drawWave();
}

// ---------- to'lqin (waveform) ----------
let waveSeed = 1, waveF = 0, scrubbing = false, scrubT = 0;
function drawWave() {
  const cv = $("mwave"); if (!cv) return;
  const W = cv.clientWidth, H = cv.clientHeight; if (!W) return;
  const dpr = Math.min(3, window.devicePixelRatio || 1);
  if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  const bw = 3, gap = 2, n = Math.floor((W + gap) / (bw + gap)), r = rnd(waveSeed);
  let prev = .5;
  for (let i = 0; i < n; i++) {
    const env = Math.sin(Math.PI * (i + 2) / (n + 4)) * .55 + .45;
    prev = prev * .45 + r() * .55;
    const h = Math.max(4, H * env * (.25 + prev * .75));
    g.fillStyle = (i + .5) / n <= waveF ? P.saf : "rgba(255,255,255,.22)";
    const x = i * (bw + gap), y = (H - h) / 2;
    g.beginPath(); g.roundRect ? g.roundRect(x, y, bw, h, 1.5) : g.rect(x, y, bw, h); g.fill();
  }
}
function waveScrub(e, end) {
  const cv = $("mwave"), rc = cv.getBoundingClientRect();
  const d = audio.duration && isFinite(audio.duration) ? audio.duration : 0;
  if (!d) return;
  const f = Math.min(1, Math.max(0, (e.clientX - rc.left) / rc.width));
  scrubT = f * d; waveF = f; drawWave(); $("mpcur").textContent = dur(scrubT);
  if (end) { audio.currentTime = scrubT; scrubbing = false; }
}

// =================================================================== ko'rinishlar
const greet = () => { const h = new Date().getHours(); return h < 5 ? "Xayrli tun" : h < 11 ? "Xayrli tong" : h < 17 ? "Xayrli kun" : "Xayrli kech"; };
const firstName = () => { try { return (tg.initDataUnsafe.user.first_name || "").trim(); } catch (e) { return ""; } };
const MOODS = [
  {n: "To'y", e: "💃", q: ["o'zbek to'y qo'shiqlari", "to'y uchun o'zbekcha xit qo'shiqlar", "o'zbek to'y raqs qo'shiqlari"], bg: P.mag, fg: "#fff", pal: [P.saf, P.ivory, P.mag]},
  {n: "Yo'lda", e: "🚗", q: ["yo'l uchun o'zbekcha qo'shiqlar", "mashinada eshitiladigan o'zbek qo'shiqlar", "o'zbek xit qo'shiqlar 2026"], bg: P.saf, fg: "#2a1600", pal: [P.mag, P.ind, P.saf]},
  {n: "Sevgi", e: "💜", q: ["sevgi haqida o'zbek qo'shiqlari", "o'zbek muhabbat qo'shiqlari", "o'zbek lirik qo'shiqlar"], bg: P.plum, fg: "#fff", pal: [P.mag, P.sky, P.plum]},
  {n: "Sport", e: "🔥", q: ["sport uchun energiya qo'shiqlar", "o'zbek tezkor raqs qo'shiqlari", "workout motivation songs"], bg: P.eme, fg: "#04231f", pal: [P.ivory, P.ind, P.eme]},
  {n: "Tinchlik", e: "🌙", q: ["tinchlantiruvchi o'zbek qo'shiqlari", "o'zbek sokin qo'shiqlar", "o'zbek mumtoz qo'shiqlar"], bg: P.ind, fg: "#fff", pal: [P.sky, P.saf, P.ind]},
  {n: "Retro", e: "📼", q: ["eski o'zbek qo'shiqlari", "90-yillar o'zbek estrada qo'shiqlari", "sovet davri o'zbek qo'shiqlari"], bg: P.ivory, fg: "#3a1a08", pal: [P.mag, P.eme, P.ivory]},
];
const okLen = (x) => !x.d || (x.d >= 50 && x.d <= 1200);   // kayfiyat/mix: mikslar va qisqa kliplarsiz

function trackRow(it, i, lid, numbered = false) {
  const p = parse(it), k = keyOf(it), d = it.d ? dur(it.d) : "";
  return `<button class="m-tr" data-l="${lid}" data-i="${i}" data-k="${esc(k)}" data-d="${d}">` +
    (numbered ? `<span class="n">${i + 1}</span>` : "") + coverHTML(it) +
    `<div class="t"><b>${esc(p.song)}</b><small>${it.lib ? '<i class="m-lib">⚡</i>' : ""}${esc(p.artist)}</small></div><span class="d">${d}</span>` +
    `<span class="m-more" data-more="1" role="button" aria-label="Amallar">${ICON.dots}</span></button>`;
}
const listHTML = (arr, lid, numbered) => `<div class="m-list">${arr.map((x, i) => trackRow(x, i, lid, numbered)).join("")}</div>`;
const skel = (n = 6) => Array.from({length: n}, () => '<div class="m-sk"></div>').join("");

function segHTML() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["music", "Musiqa"]];
  return `<div class="m-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "music" ? "on" : ""}">${l}</button>`).join("")}</div>`;
}

function renderHome() {
  const name = firstName();
  const top = home?.top || null;
  const topId = top ? regList(top) : "";
  const recent = hist.slice(0, 15), recId = regList(recent);
  const artists = topArtists();
  const mixDesc = artists.length ? `${artists.slice(0, 3).join(", ")} va o'xshashlari` : "Bugun botda eng ko'p tinglanayotgan qo'shiqlar";
  const hero = home?.hero || [], heroId = regList(hero);
  const slides = hero.map((x, i) => { const p = parse(x), src = thumb(x, true);
    return `<button class="m-hs" data-l="${heroId}" data-i="${i}" style="background-image:${src ? `url('${esc(src)}'),` : ""}${ikatFor(x.id, 390, 230, 5)}">
      <span class="sh"></span><span class="tx"><span class="k">🔥 Kun xiti · ${i + 1}</span><b class="m-h">${esc(p.song)}</b><small>${esc(p.artist)}</small></span>
      <span class="m-play">${ICON.play}</span></button>`; }).join("");
  let h = `<div class="m-bar">${segHTML()}<button class="m-ib" data-go="search" aria-label="Qidirish">${ICON.search}</button></div>
    <h1 class="m-h m-greet">${greet()}${name ? `,<br>${esc(name)}` : ""}</h1>
    <div class="m-car" id="mcar"><button class="m-hero" id="mmix" style="background-image:${ikat([P.mag, P.saf, P.ind, P.eme, "#1d0c33"], 11, 390, 230, 6)}">
      <div class="tx"><div class="k">Siz uchun tuzildi</div><h2 class="m-h">Atlas<br>mix</h2><p>${esc(mixDesc)}</p></div>
      <span class="m-play">${ICON.play}</span></button>${slides}</div>
    ${hero.length ? `<div class="m-dots" id="mdots">${[0, ...hero].map((_, i) => `<i${i ? "" : ' class="on"'}></i>`).join("")}</div>` : ""}
    ${shelf("🔥 O'zbek xitlari", home?.hits, "big")}
    ${artistsShelf(home?.artists)}
    <div class="m-sec"><h3 class="m-h">Kayfiyatga qarab</h3></div>
    <div class="m-moods">${MOODS.map((m, i) => `<button class="m-tile" data-mood="${i}" style="background:${m.bg};color:${m.fg}">
      <i style="background-image:${ikat([...m.pal, m.bg], 30 + i, 60, 90, 1)}"></i><span>${m.n} ${m.e}</span></button>`).join("")}</div>`;
  h += shelf("🆕 Yangi qo'shiqlar", home?.fresh, "big") + shelf("🎬 Kliplardagi qo'shiqlar", home?.clips, "wide");
  if (recent.length) h += `<div class="m-sec"><h3 class="m-h">Yaqinda tinglangan</h3><button data-go="hist">Hammasi</button></div>
    <div class="m-hrow">${recent.map((x, i) => { const p = parse(x); return `<button class="m-card" data-l="${recId}" data-i="${i}">${coverHTML(x)}<b>${esc(p.song)}</b><small>${esc(p.artist)}</small></button>`; }).join("")}</div>`;
  if (favs.length) h += `<div class="m-sec"><h3 class="m-h">Saqlanganlar</h3><button data-go="favs">${favs.length} ta ›</button></div>
    ${listHTML(favs.slice(0, 3), regList(favs))}`;
  h += `<div class="m-sec"><h3 class="m-h">Haftalik top</h3><span>Botda eng ko'p</span></div>`;
  if (!top) h += skel(5);
  else if (!top.length) h += `<div class="m-empty" style="padding:20px">Hozircha ro'yxat bo'sh — birinchi bo'lib tinglang!</div>`;
  else h += listHTML(top.slice(0, 15), topId, true) +
    (top.length > 15 ? `<div style="padding:6px 18px"><button class="m-btn ghost" style="width:100%" data-go="top">Barcha ${top.length} ta</button></div>` : "");
  return h;
}
// Katta muqovali gorizontal javon (big — kvadrat 150px, wide — klip kadri 16:9)
function shelf(title, items, kind) {
  if (!home) return `<div class="m-sec"><h3 class="m-h">${title}</h3></div><div class="m-hrow">${Array.from({length: 3}, () => `<div class="m-card ${kind}"><div class="m-cv m-skc"></div></div>`).join("")}</div>`;
  if (!items || items.length < 3) return "";
  const lid = regList(items);
  return `<div class="m-sec"><h3 class="m-h">${title}</h3><button data-shelf="${lid}" data-title="${esc(title.replace(/^\S+\s/, ""))}">Hammasi</button></div>
    <div class="m-hrow">${items.map((x, i) => { const p = parse(x), src = kind === "wide" ? `https://i.ytimg.com/vi/${ytOf(x)}/mqdefault.jpg` : thumb(x, true);
      return `<button class="m-card ${kind}" data-l="${lid}" data-i="${i}"><div class="m-cv" style="background-image:${ikatFor(x.id, 150, 150)}">
        ${src ? `<img src="${esc(src)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer"${kind === "wide" ? ' data-wide="1"' : ""}>` : ""}
        <span class="pl">${ICON.play}</span>${x.lib ? '<span class="lb">⚡</span>' : ""}</div><b>${esc(p.song)}</b><small>${esc(p.artist)}</small></button>`; }).join("")}</div>`;
}
function artistsShelf(list) {
  if (!list || list.length < 3) return "";
  return `<div class="m-sec"><h3 class="m-h">🎤 Mashhur ijrochilar</h3></div><div class="m-hrow">${list.map((a) => {
    const src = a.it ? thumb(a.it, true) : "";
    return `<button class="m-art" data-artist="${esc(a.n)}"><div class="m-cv" style="background-image:${ikatFor(a.n, 120, 120)}">${src ? `<img src="${esc(src)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}</div><b>${esc(a.n)}</b></button>`; }).join("")}</div>`;
}
let carTimer = null;
function startCarousel() {
  clearInterval(carTimer);
  const car = $("mcar"); if (!car) return;
  const n = car.children.length; if (n < 2) return;
  let touched = false;
  const sync = () => { const i = Math.round(car.scrollLeft / car.clientWidth);
    document.querySelectorAll("#mdots i").forEach((d, k) => d.classList.toggle("on", k === i)); };
  car.addEventListener("scroll", () => { clearTimeout(car._t); car._t = setTimeout(sync, 60); }, {passive: true});
  car.addEventListener("touchstart", () => { touched = true; }, {passive: true});
  carTimer = setInterval(() => {
    if (!document.body.contains(car)) { clearInterval(carTimer); return; }
    if (touched || document.hidden || playerOpen || !opened) return;
    const i = Math.round(car.scrollLeft / car.clientWidth);
    car.scrollTo({left: ((i + 1) % n) * car.clientWidth, behavior: "smooth"});
  }, 5000);
}
function topArtists() {
  const cnt = new Map();
  for (const x of [...favs.slice(0, 40), ...hist.slice(0, 60)]) {
    const a = parse(x).artist; if (!a || a === "Noma'lum ijrochi") continue;
    cnt.set(a, (cnt.get(a) || 0) + 1);
  }
  return [...cnt.entries()].sort((a, b) => b[1] - a[1]).map((x) => x[0]).slice(0, 4);
}

function renderSearch(v) {
  const q = v.q || "";
  let body;
  if (!q) body = recentQ.length
    ? `<div class="m-sec"><h3 class="m-h">Oxirgi qidiruvlar</h3><button data-clrq="1">Tozalash</button></div><div class="m-chips">${recentQ.map((x) => `<button class="m-chip" data-q="${esc(x)}">${esc(x)}</button>`).join("")}</div>`
    : `<div class="m-empty"><div class="ic">🎧</div><b>Qo'shiq yoki ijrochi</b>Nomini yozing — topib, shu yerning o'zida eshittiramiz.<br><br>
      <button class="m-btn ghost" data-recopen="1">🎙 Eshittirib topish</button></div>`;
  else if (v.err) body = `<div class="m-empty"><div class="ic">📶</div><b>Qidirib bo'lmadi</b>${v.err === "rate" ? "Juda tez qidiryapsiz — bir daqiqa kuting." : "Internetni tekshirib, qayta urinib ko'ring."}</div>`;
  else if (!v.items) body = skel(8);
  else if (!v.items.length) body = `<div class="m-empty"><div class="ic">🔍</div><b>Hech narsa topilmadi</b>Nomini boshqacha yozib ko'ring yoki qo'shiqni eshittirib toping.<br><br>
      <button class="m-btn ghost" data-recopen="1">🎙 Eshittirib topish</button></div>`;
  else { const lid = regList(v.items); v.lid = lid; body = `<div style="height:6px"></div>` + listHTML(v.items, lid) +
    (v.more ? `<div style="padding:10px 18px"><button class="m-btn ghost" style="width:100%" data-smore="1">${v.moreBusy ? "Yuklanmoqda…" : "Yana natijalar"}</button></div>` : ""); }
  return `<div class="m-bar"><button class="m-ib" data-back="1" aria-label="Orqaga">${ICON.back}</button>
    <label class="m-search${q ? " has" : ""}" id="msbox">${ICON.search}<input id="mq" type="search" enterkeyhint="search" autocomplete="off" placeholder="Qo'shiq yoki ijrochi…" value="${esc(q)}"><button class="x" id="mqx" type="button" aria-label="Tozalash">✕</button></label></div>${body}`;
}

function renderList(v) {
  const items = v.items;
  const lid = items ? regList(items) : "";
  v.lid = lid;
  const banner = v.bg || ikatFor(v.title, 390, 280, 5);
  let h = `<div class="m-bar over"><button class="m-ib" data-back="1" aria-label="Orqaga">${ICON.back}</button></div>
    <div class="m-ban" style="background-image:${banner}"><div class="tx"><h1 class="m-h">${esc(v.title)}</h1><p>${esc(v.sub || (items ? `${items.length} ta qo'shiq` : "Yuklanmoqda…"))}</p></div></div>`;
  if (v.err) return h + `<div class="m-empty"><div class="ic">📶</div><b>Yuklab bo'lmadi</b><button class="m-btn saf" data-retry="1" style="margin-top:14px">Qayta urinish</button></div>`;
  if (!items) return h + skel(8);
  if (!items.length) return h + `<div class="m-empty"><div class="ic">${v.emptyIc || "🎵"}</div><b>${esc(v.emptyT || "Bo'sh")}</b>${esc(v.emptyS || "")}</div>`;
  h += `<div class="m-acts"><button class="m-btn saf" data-playall="0">${ICON.play} Hammasini tinglash</button>
    <button class="m-btn ghost sq" data-playall="1" aria-label="Aralash">${ICON.shuffle}</button></div>`;
  return h + `<div class="m-sec" style="padding-top:18px"><h3 class="m-h">${esc(v.listT || "Qo'shiqlar")}</h3></div>` + listHTML(items, lid, !!v.numbered);
}

function render(keepScroll = false) {
  const v = stack[stack.length - 1]; if (!v) return;
  const sc = $("mscroll");
  $("mview").innerHTML = v.v === "home" ? renderHome() : v.v === "search" ? renderSearch(v) : renderList(v);
  sc.scrollTop = keepScroll ? (v.st || 0) : 0;
  $("mus").classList.toggle("nofab", v.v !== "home");
  paintAll(); updateBack();
  if (v.v === "search") bindSearch(v);
  if (v.v === "home") startCarousel(); else clearInterval(carTimer);
}
function push(v) {
  const top = stack[stack.length - 1]; if (top) top.st = $("mscroll").scrollTop;
  stack.push(v); render(); haptic();
}
function pop() {
  if (stack.length <= 1) return false;
  stack.pop(); render(true); return true;
}

// ---------- qidiruv ----------
let sTimer = null, sCtl = null;
function bindSearch(v) {
  const inp = $("mq");
  if (!v.q) setTimeout(() => inp.focus(), 60);
  inp.addEventListener("input", () => {
    const q = inp.value.trim(); $("msbox").classList.toggle("has", !!q);
    clearTimeout(sTimer); sTimer = setTimeout(() => runSearch(v, q), 450);
  });
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { clearTimeout(sTimer); inp.blur(); runSearch(v, inp.value.trim(), true); } });
  $("mqx").onclick = (e) => { e.preventDefault(); inp.value = ""; v.q = ""; v.items = null; v.err = ""; render(); };
}
async function runSearch(v, q, commit = false) {
  if (q === v.q && v.items && !commit) return;
  if (sCtl) sCtl.abort();
  v.q = q; v.items = null; v.err = "";
  if (q.length < 2) { if (!q) { v.q = ""; rerenderSearchBody(v); } return; }
  rerenderSearchBody(v);
  const ctl = sCtl = new AbortController();
  try {
    const items = await search(q, 30, ctl.signal);
    v.more = items.length >= 25;
    if (ctl !== sCtl) return;
    v.items = items;
    if (items.length) { recentQ = [q, ...recentQ.filter((x) => x.toLowerCase() !== q.toLowerCase())].slice(0, 8); lsSet("zk_mq", recentQ); }
  } catch (e) { if (e.name === "AbortError") return; v.err = e.message === "rate" ? "rate" : "net"; }
  rerenderSearchBody(v);
}
async function searchMore() {
  const v = stack[stack.length - 1];
  if (!v || v.v !== "search" || !v.items || v.moreBusy) return;
  v.moreBusy = true; const st = $("mscroll").scrollTop; rerenderSearchBody(v); $("mscroll").scrollTop = st;
  const q = v.q;
  try {
    const all = await search(q, 50);
    if (v.q !== q) return;
    const have = new Set(v.items.map(keyOf));
    v.items = v.items.concat(all.filter((x) => !have.has(keyOf(x))));
  } catch (e) { toast("📶 Yuklab bo'lmadi"); }
  v.moreBusy = false; v.more = false;
  if (stack[stack.length - 1] === v) { rerenderSearchBody(v); $("mscroll").scrollTop = st; }
}
function rerenderSearchBody(v) {
  if (stack[stack.length - 1] !== v) return;
  const inp = $("mq"), had = document.activeElement === inp, val = inp ? inp.value : v.q, sel = inp ? inp.selectionStart : 0;
  render();
  const n = $("mq"); n.value = val; $("msbox").classList.toggle("has", !!val);
  if (had) { n.focus(); try { n.setSelectionRange(sel, sel); } catch (e) {} }
}

// ---------- ro'yxatlar ----------
// Bir nechta so'rov natijalari navbatma-navbat qo'shiladi, takrorlar olib tashlanadi
async function multi(qs, n = 40, filter = okLen) {
  const pools = await Promise.all(qs.map((q) => search(q, n).catch(() => [])));
  if (pools.every((p) => !p.length)) throw new Error("net");
  const seen = new Set(), out = [];
  for (let i = 0; i < n; i++) for (const p of pools) {
    const x = p[i]; if (!x || !filter(x)) continue;
    const k = keyOf(x), tk = parse(x).song.toLowerCase() + "|" + parse(x).artist.toLowerCase();
    if (seen.has(k) || seen.has(tk)) continue;
    seen.add(k); seen.add(tk); out.push(x);
  }
  return out;
}
async function openQuery(title, q, extra = {}) {
  const qs = Array.isArray(q) ? q : [q];
  const v = Object.assign({v: "list", title, items: null, load: () => multi(qs)}, extra);
  push(v); fill(v);
}
async function fill(v) {
  v.err = ""; v.items = null;
  try { v.items = await v.load(); } catch (e) { v.err = "net"; }
  if (stack.includes(v)) { if (stack[stack.length - 1] === v) render(true); }
}
function openArtist(name) {
  if (!name || name === "Noma'lum ijrochi") return;
  closePlayer();
  openQuery(name, name, {sub: "Ijrochi", listT: "Eng mashhur qo'shiqlari", bg: ikatFor(name, 390, 280, 5), numbered: true,
    load: async () => {
      const low = name.toLowerCase();
      const mineF = (x) => okLen(x) && (parse(x).artist.toLowerCase().includes(low) || String(x.t).toLowerCase().includes(low));
      const mine = await multi([name, `${name} qo'shiqlari`, `${name} yangi qo'shiq`, `${name} audio`], 50, mineF);
      return mine.length >= 4 ? mine : (await search(name, 50)).filter(okLen);
    }});
}
async function atlasMix() {
  const btn = $("mmix"); if (!btn || btn.classList.contains("busy")) return;
  unlock(); btn.classList.add("busy"); haptic();
  try {
    const arts = topArtists().slice(0, 3);
    let pools = arts.length ? await Promise.all(arts.map((a) => search(a, 30).catch(() => []))) : [];
    pools = pools.map((p) => p.filter(okLen));
    const seen = new Set(), mix = [];
    for (let i = 0; i < 30; i++) for (const p of pools) { const x = p[i]; if (x && !seen.has(keyOf(x))) { seen.add(keyOf(x)); mix.push(x); } }
    for (const x of [...favs].sort(() => Math.random() - .5).slice(0, 8)) if (!seen.has(keyOf(x))) { seen.add(keyOf(x)); mix.splice(Math.floor(Math.random() * (mix.length + 1)), 0, x); }
    for (const x of (home?.top || [])) if (mix.length < 50 && !seen.has(keyOf(x))) { seen.add(keyOf(x)); mix.push(x); }
    if (!mix.length) { toast("Hali mix tayyor emas — biror qo'shiq tinglang"); return; }
    if (!arts.length) mix.sort(() => Math.random() - .5);
    playList(mix.slice(0, 80), 0, "Atlas mix");
    openPlayer();
  } finally { btn.classList.remove("busy"); }
}

// =================================================================== to'liq pleyer
let playerOpen = false;
function openPlayer() {
  if (!cur()) return;
  playerOpen = true; $("mplayer").dataset.k = ""; $("mpnext").dataset.k = "";
  $("mplayer").classList.add("open"); document.body.classList.add("m-hidemini");
  requestAnimationFrame(() => { paintPlayer(); drawWave(); });
  updateBack(); haptic();
}
function closePlayer() {
  if (!playerOpen) return;
  playerOpen = false; $("mplayer").classList.remove("open"); document.body.classList.remove("m-hidemini");
  updateBack();
}

// =================================================================== chatga yuborish / ulashish
async function sendToChat(it) {
  if (!inTg) { toast("📱 Telegram ichida oching"); return; }
  haptic();
  let r;
  try { r = await api("api/music/send", {json: slim(it)}); } catch (e) { r = {ok: false, error: "network"}; }
  if (r.ok) { haptic("ok"); toast(r.dup ? "⏳ Allaqachon yuborilmoqda…" : "✅ MP3 chatga yuborilmoqda — botni oching", 2600); return; }
  if (r.error === "need_start" && bot && ytOf(it)) { tg.openTelegramLink(`https://t.me/${bot}?start=m_${ytOf(it)}`); return; }
  haptic("err");
  toast({rate: "⏳ Juda ko'p so'rov — birozdan keyin", auth: "⚠️ Ilovani yopib, qayta oching"}[r.error] || "⚠️ Yuborib bo'lmadi, qayta urinib ko'ring", 3000);
}
function share(it) {
  if (!ytOf(it) || !bot) { toast("Bu qo'shiqni ulashib bo'lmaydi"); return; }
  const p = parse(it), link = `https://t.me/${bot}?start=m_${ytOf(it)}`;
  const text = `🎧 ${p.artist} — ${p.song}\nBir bosishda tinglang 👇`;
  const u = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
  inTg ? tg.openTelegramLink(u) : window.open(u, "_blank");
}

// =================================================================== pastki oyna
let sheetOpen = false;
function openSheet(html) {
  $("msheet").innerHTML = html; $("msheet").scrollTop = 0;
  $("msbg").classList.add("open"); $("msheet").classList.add("open"); sheetOpen = true; updateBack();
}
function closeSheet() {
  if (!sheetOpen) return;
  $("msbg").classList.remove("open"); $("msheet").classList.remove("open"); sheetOpen = false; updateBack();
}
let sheetItem = null;
function actionsSheet(it) {
  sheetItem = it; const p = parse(it), fav = isFav(it);
  openSheet(`<div class="hd">${coverHTML(it)}<div><b>${esc(p.song)}</b><small>${esc(p.artist)}${it.d ? " · " + dur(it.d) : ""}</small></div></div>
    <button class="m-act" data-act="send">${ICON.dl}Chatga MP3 olish</button>
    <button class="m-act" data-act="next">${ICON.addq}Keyingi bo'lib ijro etish</button>
    <button class="m-act" data-act="fav">${ICON.heart}${fav ? "Saqlanganlardan olib tashlash" : "Saqlab qo'yish"}</button>
    <button class="m-act" data-act="artist">${ICON.user}Ijrochi: ${esc(p.artist)}</button>
    ${ytOf(it) ? `<button class="m-act" data-act="share">${ICON.share}Do'stga yuborish</button>` : ""}`);
}
function queueSheet() {
  const p = pos();
  const up = order.slice(Math.max(0, p)).map((i) => queue[i]).slice(0, 80);
  const lid = regList(up);
  openSheet(`<h3 class="m-h">Navbat${qName ? " · " + esc(qName) : ""}</h3>` +
    `<div class="m-list" style="padding:0">${up.map((x, i) => trackRow(x, i, lid).replace('data-l=', 'data-q="1" data-l=')).join("")}</div>`);
  paintAll();
}

// =================================================================== qo'shiqni aniqlash
let rec = null, recOpen = false, recFound = null;
function openRec() {
  recOpen = true; recFound = null; unlock();
  $("mrec").classList.add("open"); updateBack();
  if (playing()) { audio.pause(); rec_resume = true; } else rec_resume = false;
  startListening();
}
let rec_resume = false;
function recUI(state, title, sub) {
  const el = $("mrec");
  el.classList.toggle("listen", state === "listen"); el.classList.toggle("think", state === "think");
  $("mrect").textContent = title; $("mrecs").textContent = sub || "";
}
function foundUI(html, msg = false) {
  const f = $("mfound"); f.className = "m-found" + (msg ? " msg" : ""); f.innerHTML = html;
  requestAnimationFrame(() => f.classList.add("on"));
}
async function startListening() {
  const f = $("mfound"); f.className = "m-found"; f.innerHTML = "";
  if (!inTg) { recUI("", "Telegram ichida oching", ""); return; }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) return noMic();
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}}); }
  catch (e) { return noMic(e && e.name === "NotAllowedError"); }
  if (!recOpen) { stream.getTracks().forEach((t) => t.stop()); return; }
  const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm", "audio/ogg;codecs=opus"].find((m) => { try { return MediaRecorder.isTypeSupported(m); } catch (e) { return false; } }) || "";
  let mr;
  try { mr = new MediaRecorder(stream, mime ? {mimeType: mime, audioBitsPerSecond: 96000} : undefined); }
  catch (e) { stream.getTracks().forEach((t) => t.stop()); return noMic(); }
  const chunks = [];
  rec = {mr, stream, timer: null, stopped: false};
  mr.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
  mr.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    if (!recOpen || rec?.cancel) return;
    identify(new Blob(chunks, {type: mr.mimeType || mime || "audio/webm"}));
  };
  // ovoz darajasiga qarab markaz "nafas oladi"
  try {
    const AC = window.AudioContext || window.webkitAudioContext, ac = new AC(), an = ac.createAnalyser();
    ac.createMediaStreamSource(stream).connect(an); an.fftSize = 256; const buf = new Uint8Array(an.frequencyBinCount);
    rec.ac = ac;
    const tick = () => { if (!rec || rec.stopped) { ac.close().catch(() => {}); return; }
      an.getByteTimeDomainData(buf); let m = 0; for (const b of buf) m = Math.max(m, Math.abs(b - 128));
      $("mrecbtn").style.transform = `scale(${1 + Math.min(.18, m / 400)})`; requestAnimationFrame(tick); };
    tick();
  } catch (e) {}
  mr.start(500); haptic("hit");
  let left = 11;
  recUI("listen", "Tinglayapman", "Telefonni musiqa chalinayotgan tomonga yaqinlashtiring");
  rec.timer = setInterval(() => {
    left--;
    if (left <= 3 && left > 0) $("mrecs").textContent = `Yana ${left} soniya…`;
    if (left <= 0) stopListening();
  }, 1000);
}
function stopListening(cancel = false) {
  if (!rec || rec.stopped) return;
  rec.stopped = true; rec.cancel = cancel; clearInterval(rec.timer);
  $("mrecbtn").style.transform = "";
  try { rec.mr.state !== "inactive" ? rec.mr.stop() : rec.stream.getTracks().forEach((t) => t.stop()); } catch (e) {}
  if (cancel) rec.stream.getTracks().forEach((t) => t.stop());
}
async function identify(blob) {
  recUI("think", "Qidiryapman", "Qo'shiqni aniqlayapman…");
  let r;
  try {
    const res = await fetch("api/music/recognize", {method: "POST", headers: {"X-Init-Data": tg.initData, "Content-Type": blob.type || "application/octet-stream"}, body: blob});
    r = await res.json();
  } catch (e) { r = {ok: false, error: "network"}; }
  if (!recOpen) return;
  if (r.ok) {
    haptic("ok");
    const it = r.items && r.items[0];
    recFound = it || null;
    recUI("", "Mana u!", "");
    const cov = r.cover ? `<div class="m-cv" style="background-image:url('${esc(r.cover)}')"></div>` : it ? coverHTML(it) : `<div class="m-cv" style="background-image:${ikatFor(r.title, 120, 120)}"></div>`;
    foundUI(`${cov}<div class="t"><div class="k">Topildi</div><div class="nm">${esc(r.title)}</div><div class="ar">${esc(r.artist || "")}</div></div>
      ${it ? `<div class="bs"><button data-rec="play">▶ Tinglash</button><button data-rec="send">Chatga olish</button></div>` : ""}`);
    if (it && r.cover) it.c = r.cover;
    return;
  }
  haptic("err");
  if (r.error === "not_found") { recUI("", "Topilmadi", "Musiqa aniqroq eshitiladigan joyda yana urinib ko'ring"); foundUI(`<p>Shovqin kamroq joyda, telefonni manbaga yaqinroq tuting.</p><button data-rec="again">🎙 Qayta tinglash</button>`, true); return; }
  recUI("", "Aniqlab bo'lmadi", r.error === "rate" ? "Juda ko'p urinish — birozdan keyin" : "Internetni tekshirib, qayta urinib ko'ring");
  foundUI(`<button data-rec="again">🎙 Qayta urinish</button>`, true);
}
function noMic(denied = false) {
  recUI("", denied ? "Mikrofonga ruxsat berilmadi" : "Mikrofon ishlamadi",
    "Qo'shiqni botga ovozli xabar qilib yuboring — darhol topib beraman");
  foundUI(`<p>🎙 Botga 10–15 soniyalik ovozli xabar yuboring</p><button data-rec="bot">Botni ochish</button>${denied ? `<button data-rec="again">Qayta urinish</button>` : ""}`, true);
}
function closeRec() {
  if (!recOpen) return;
  recOpen = false; stopListening(true); rec = null;
  $("mrec").classList.remove("open", "listen", "think"); updateBack();
  if (rec_resume && cur()) audio.play().catch(() => {});
}

// =================================================================== Telegram "Orqaga"
function updateBack() {
  if (!inTg) return;
  const need = playerOpen || recOpen || sheetOpen || (opened && stack.length > 1);
  try { need ? tg.BackButton.show() : (window.ZK_canHideBack ? window.ZK_canHideBack() && tg.BackButton.hide() : tg.BackButton.hide()); } catch (e) {}
}
function onBack() {
  if (sheetOpen) closeSheet();
  else if (recOpen) closeRec();
  else if (playerOpen) closePlayer();
  else if (opened && stack.length > 1) pop();
  else return false;
  return true;
}
if (inTg) tg.BackButton.onClick(() => { onBack(); });

// =================================================================== hodisalar
function itemFromRow(r) {
  const l = lists.get(r.dataset.l); if (!l) return null;
  return {list: l, i: +r.dataset.i};
}
document.addEventListener("click", (e) => {
  const t = e.target;
  if (!t.closest(".mus,.m-mini,.m-player,.m-rec,.m-sheet,.m-sbg")) return;
  unlock();
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "music" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  const art = t.closest("[data-artist]");
  if (art) { haptic(); openArtist(art.dataset.artist); return; }
  const sh = t.closest("[data-shelf]");
  if (sh) { const items = lists.get(sh.dataset.shelf) || []; push({v: "list", title: sh.dataset.title, items, sub: `${items.length} ta qo'shiq`}); return; }
  const row = t.closest(".m-tr,.m-card[data-l],.m-hs[data-l]");
  if (row) {
    const x = itemFromRow(row); if (!x) return;
    const it = x.list[x.i];
    if (t.closest("[data-more]")) { haptic(); actionsSheet(it); return; }
    if (row.dataset.q) {               // navbatdan tanlash
      const qidx = queue.findIndex((y) => keyOf(y) === keyOf(it));
      closeSheet(); if (qidx >= 0) { load(qidx); } return;
    }
    if (cur() && keyOf(cur()) === keyOf(it) && !loadingKey) { if (audio.paused) toggle(); openPlayer(); return; }
    const v = stack[stack.length - 1];
    const name = v.v === "list" ? v.title : v.v === "search" ? `«${v.q}» qidiruvi` : t.closest(".m-hs") ? "Kun xitlari" : t.closest(".m-hrow") ? ((t.closest(".m-hrow").previousElementSibling || {}).textContent || "").replace("Hammasi", "").trim() : "Haftalik top";
    playList(x.list, x.i, name); haptic("hit");
    return;
  }
  const go = t.closest("[data-go]");
  if (go) {
    const g = go.dataset.go;
    if (g === "search") push({v: "search", q: "", items: null});
    else if (g === "top") push({v: "list", title: "Haftalik top", sub: "Shu hafta botda eng ko'p tinglangan va yuklangan", items: home?.top || [], numbered: true, listT: "Top qo'shiqlar",
      bg: ikat([P.saf, P.mag, P.ind, "#1d0c33"], 77, 390, 280, 5)});
    else if (g === "favs") push({v: "list", title: "Saqlanganlar", items: favs, emptyIc: "❤️", emptyT: "Hali hech narsa saqlanmagan", emptyS: "Qo'shiq yonidagi ⋯ yoki pleyerdagi ♥ ni bosing.",
      bg: ikat([P.mag, P.plum, P.saf, "#2b0b1c"], 5, 390, 280, 5)});
    else if (g === "hist") push({v: "list", title: "Yaqinda tinglangan", items: hist, emptyT: "Tarix bo'sh",
      bg: ikat([P.sky, P.ind, P.eme, "#121640"], 9, 390, 280, 5)});
    return;
  }
  const mood = t.closest("[data-mood]");
  if (mood) { const m = MOODS[+mood.dataset.mood]; openQuery(`${m.n} ${m.e}`, m.q, {sub: "Kayfiyat to'plami", bg: ikat([...m.pal, m.bg], 40 + +mood.dataset.mood, 390, 280, 5)}); return; }
  if (t.closest("#mmix")) { atlasMix(); return; }
  if (t.closest("[data-recopen]")) { openRec(); return; }
  if (t.closest("[data-smore]")) { searchMore(); return; }
  if (t.closest("[data-back]")) { pop(); return; }
  if (t.closest("[data-retry]")) { const v = stack[stack.length - 1]; if (v.load) { render(); fill(v); } return; }
  const pa = t.closest("[data-playall]");
  if (pa) { const v = stack[stack.length - 1]; if (!v.items?.length) return;
    if (pa.dataset.playall === "1") { shuffle = true; lsSet("zk_mshuf", true); playList(v.items, Math.floor(Math.random() * v.items.length), v.title); }
    else { if (shuffle) { shuffle = false; lsSet("zk_mshuf", false); } playList(v.items, 0, v.title); }
    openPlayer(); return; }
  const q = t.closest("[data-q]");
  if (q) { const v = stack[stack.length - 1]; $("mq").value = q.dataset.q; runSearch(v, q.dataset.q, true); return; }
  if (t.closest("[data-clrq]")) { recentQ = []; lsSet("zk_mq", []); render(); return; }
  const act = t.closest("[data-act]");
  if (act && sheetItem) {
    const it = sheetItem, a = act.dataset.act; closeSheet();
    if (a === "send") sendToChat(it);
    else if (a === "fav") { toggleFav(it); if (cur() && keyOf(cur()) === keyOf(it)) $("mpheart").classList.toggle("on", isFav(it)); const v = stack[stack.length - 1]; if (v.v === "home" || v.title === "Saqlanganlar") { if (v.title === "Saqlanganlar") v.items = favs; render(true); } }
    else if (a === "artist") openArtist(parse(it).artist);
    else if (a === "share") share(it);
    else if (a === "next") {
      if (!cur()) { playList([it], 0, ""); return; }
      const k = keyOf(it), ex = queue.findIndex((y) => keyOf(y) === k);
      if (ex === qi) return;
      let idx = ex;
      if (ex < 0) { queue.push(slim(it)); idx = queue.length - 1; } else order.splice(order.indexOf(ex), 1);
      order.splice(pos() + 1, 0, idx);
      toast("➕ Keyingi bo'lib ijro etiladi", 1400); paintPlayer();
    }
    return;
  }
  const rb = t.closest("[data-rec]");
  if (rb) {
    const a = rb.dataset.rec;
    if (a === "again") startListening();
    else if (a === "bot") { if (bot) tg.openTelegramLink(`https://t.me/${bot}`); try { tg.close(); } catch (x) {} }
    else if (a === "play" && recFound) { const it = recFound; closeRec(); playList([it], 0, "Topilgan qo'shiq"); openPlayer(); }
    else if (a === "send" && recFound) sendToChat(recFound);
    return;
  }
});

function wire() {
  $("mfab").onclick = () => { haptic(); openRec(); };
  $("mrecx").onclick = () => closeRec();
  $("mrecbtn").onclick = () => { if (rec && !rec.stopped) stopListening(); else if (!rec || rec.stopped) { if (!$("mrec").classList.contains("think")) startListening(); } };
  $("mmini").addEventListener("click", (e) => {
    if (e.target.closest("#mmplay")) { toggle(); return; }
    if (e.target.closest("#mmnext")) { haptic("hit"); next(); return; }
    openPlayer();
  });
  $("mpdown").onclick = closePlayer;
  $("mpplay").onclick = toggle;
  $("mpnextb").onclick = () => { haptic("hit"); next(); };
  $("mpprev").onclick = () => { haptic("hit"); prev(); };
  $("mpshuf").onclick = () => { shuffle = !shuffle; lsSet("zk_mshuf", shuffle); if (queue.length) buildOrder(qi); $("mpnext").dataset.k = ""; haptic(); paintPlayer();
    toast(shuffle ? "🔀 Aralash ijro" : "Ketma-ket ijro", 1100); prefetchNext(); };
  $("mprep").onclick = () => { repeat = (repeat + 1) % 3; lsSet("zk_mrep", repeat); haptic(); paintPlayer();
    toast(["Takrorlash o'chiq", "🔁 Ro'yxat takrorlanadi", "🔂 Shu qo'shiq takrorlanadi"][repeat], 1200); $("mpnext").dataset.k = ""; paintPlayer(); };
  $("mpheart").onclick = () => { const it = cur(); if (!it) return; const on = toggleFav(it); const h = $("mpheart"); h.classList.toggle("on", on); h.classList.remove("pop"); void h.offsetWidth; h.classList.add("pop"); };
  $("mpa").onclick = () => { const it = cur(); if (it) { if (!opened && window.ZK_setMode) window.ZK_setMode("music"); openArtist(parse(it).artist); } };
  $("mpsend").onclick = () => cur() && sendToChat(cur());
  $("mpshare").onclick = () => cur() && share(cur());
  $("mpq").onclick = () => queue.length && queueSheet();
  $("mpmore").onclick = () => cur() && actionsSheet(cur());
  $("mpnext").onclick = () => { haptic("hit"); next(); };
  $("msbg").onclick = closeSheet;
  const wv = $("mwave");
  wv.addEventListener("pointerdown", (e) => { if (!audio.duration) return; scrubbing = true; wv.setPointerCapture(e.pointerId); waveScrub(e); haptic(); });
  wv.addEventListener("pointermove", (e) => { if (scrubbing) waveScrub(e); });
  wv.addEventListener("pointerup", (e) => { if (scrubbing) waveScrub(e, true); });
  wv.addEventListener("pointercancel", () => { scrubbing = false; paintProgress(); });
  window.addEventListener("resize", () => { if (playerOpen) drawWave(); });
  // pleyerni pastga surib yopish
  let sy = null;
  $("mplayer").addEventListener("touchstart", (e) => {
    // faqat eng tepada turganda pastga surish pleyerni yopadi (aks holda bu oddiy aylantirish)
    if (e.target.closest(".m-wave") || $("mplayer").querySelector(".m-pbody").scrollTop > 0) { sy = null; return; }
    sy = e.touches[0].clientY; }, {passive: true});
  $("mplayer").addEventListener("touchend", (e) => { if (sy != null && e.changedTouches[0].clientY - sy > 110) closePlayer(); sy = null; }, {passive: true});
}

async function loadHome() {
  try {
    const r = await (await fetch("api/music/home", {cache: "no-cache"})).json();
    home = {top: r.top || [], hero: r.hero || [], hits: r.hits || [], fresh: r.fresh || [], clips: r.clips || [], artists: r.artists || []};
  } catch (e) { home = {top: []}; }
  const v = stack[0];
  if (opened && v && stack.length === 1) render(true);
}

window.ZMusic = {
  open() {
    if (!mounted) { mounted = true; wire(); stack.push({v: "home"}); loadHome(); }
    opened = true;
    $("mus").hidden = false; document.body.classList.add("m-on");
    try { tg.setHeaderColor("#16132E"); tg.setBackgroundColor("#16132E"); if (tg.setBottomBarColor) tg.setBottomBarColor("#16132E"); } catch (e) {}
    render(true);
  },
  close() {
    opened = false; closeSheet();
    $("mus").hidden = true; document.body.classList.remove("m-on");
    try { tg.setHeaderColor("bg_color"); tg.setBackgroundColor("bg_color"); if (tg.setBottomBarColor) tg.setBottomBarColor("bottom_bar_bg_color"); } catch (e) {}
    updateBack();
  },
  setBot(b) { bot = b || ""; },
  search(q) {
    q = String(q || "").trim().slice(0, 80); if (!q) return;
    const v = {v: "search", q, items: null}; stack.length = 1; stack.push(v); render(); runSearch(v, q, true);
  },
  busy() { return playerOpen || recOpen || sheetOpen || (opened && stack.length > 1); },
  pause() { audio.pause(); },
};
})();
