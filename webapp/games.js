/* 🧸 Bolajonlar o'yinlari — 10 ta mini o'yin. index.html dan window.ZGames orqali boshqariladi.
   Hammasi telefonning o'zida ishlaydi: serverga so'rov yo'q, reklama yo'q. Ovozlar WebAudio bilan sintez qilinadi. */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success")
  : t === "err" ? tg.HapticFeedback.notificationOccurred("error")
  : t === "hit" ? tg.HapticFeedback.impactOccurred("light") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const lsGet = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const rnd = (n) => Math.floor(Math.random() * n);
const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = rnd(i + 1); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const pickN = (a, n) => shuffle(a).slice(0, n);
const reduced = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

// =================================================================== ovoz (WebAudio)
let ac = null;
function ctx() {
  try {
    if (!ac) ac = new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === "suspended") ac.resume();
  } catch (e) { ac = null; }
  return ac;
}
function tone(freq, dur = 0.3, type = "sine", vol = 0.25, when = 0, slideTo = null) {
  const c = ctx(); if (!c) return;
  const t = c.currentTime + when, o = c.createOscillator(), g = c.createGain();
  o.type = type; o.frequency.setValueAtTime(freq, t);
  if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.015);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(c.destination); o.start(t); o.stop(t + dur + 0.05);
}
const sfx = {
  ok() { [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.18, "triangle", 0.2, i * 0.08)); },
  err() { tone(220, 0.25, "square", 0.08); tone(180, 0.3, "square", 0.08, 0.12); },
  pop() { tone(900, 0.12, "triangle", 0.25, 0, 300); },
  tap() { tone(660, 0.06, "sine", 0.12); },
  flip() { tone(500, 0.08, "triangle", 0.12, 0, 700); },
  win() { [523, 659, 784, 659, 784, 1047].forEach((f, i) => tone(f, 0.22, "triangle", 0.22, i * 0.11)); },
  step() { tone(440 + rnd(80), 0.05, "sine", 0.08); },
};
// Hayvon ovozlari — multfilmcha uslubida sintez (tashqi audio fayl yo'q)
function voice(c, {type = "sawtooth", f0, f1, dur, vol = 0.25, vib = 0, vibRate = 6, lp = 1800, when = 0}) {
  const t = c.currentTime + when, o = c.createOscillator(), g = c.createGain(), fl = c.createBiquadFilter();
  o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.linearRampToValueAtTime(f1, t + dur);
  if (vib) { const l = c.createOscillator(), lg = c.createGain(); l.frequency.value = vibRate; lg.gain.value = vib; l.connect(lg).connect(o.frequency); l.start(t); l.stop(t + dur + 0.1); }
  fl.type = "lowpass"; fl.frequency.value = lp;
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.06);
  g.gain.setValueAtTime(vol, t + dur * 0.7); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(fl).connect(g).connect(c.destination); o.start(t); o.stop(t + dur + 0.1);
}
function noise(c, dur, when, freq, vol = 0.3) {
  const t = c.currentTime + when, b = c.createBuffer(1, Math.ceil(c.sampleRate * dur), c.sampleRate), d = b.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length);
  const s = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
  s.buffer = b; f.type = "bandpass"; f.frequency.value = freq; f.Q.value = 2; g.gain.value = vol;
  s.connect(f).connect(g).connect(c.destination); s.start(t);
}
const CALL = {
  sigir(c) { voice(c, {f0: 150, f1: 105, dur: 1.4, vol: 0.32, lp: 700, vib: 2}); },
  mushuk(c) { voice(c, {type: "triangle", f0: 620, f1: 880, dur: 0.35, vol: 0.25, lp: 3000});
    voice(c, {type: "triangle", f0: 880, f1: 480, dur: 0.45, vol: 0.25, lp: 3000, when: 0.33, vib: 15, vibRate: 9}); },
  kuchuk(c) { [0, 0.32].forEach((w) => { voice(c, {type: "square", f0: 330, f1: 170, dur: 0.16, vol: 0.18, lp: 1200, when: w}); noise(c, 0.12, w, 700, 0.25); }); },
  xoroz(c) { [[600, 760, 0.16], [760, 900, 0.16], [900, 1150, 0.22], [1150, 700, 0.6]].reduce((w, [a, b, d]) => {
    voice(c, {type: "sawtooth", f0: a, f1: b, dur: d, vol: 0.14, lp: 2600, vib: 25, vibRate: 22, when: w}); return w + d; }, 0); },
  qoy(c) { voice(c, {f0: 330, f1: 300, dur: 1.0, vol: 0.22, lp: 1500, vib: 22, vibRate: 7}); },
  ordak(c) { [0, 0.28, 0.56].forEach((w) => voice(c, {type: "square", f0: 480, f1: 380, dur: 0.18, vol: 0.13, lp: 1100, when: w})); },
};
// Matnni o'qib berish — faqat telefonda o'zbekcha ovoz bo'lsa (bo'lmasa jim: noto'g'ri talaffuz bolani chalg'itadi)
let uzVoice = null;
function findVoice() { try { uzVoice = speechSynthesis.getVoices().find((v) => /^uz/i.test(v.lang)) || null; } catch (e) {} }
try { findVoice(); speechSynthesis.onvoiceschanged = findVoice; } catch (e) {}
function say(text) {
  if (!uzVoice) return false;
  try { speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.voice = uzVoice; u.lang = uzVoice.lang; u.rate = 0.9; speechSynthesis.speak(u); return true; } catch (e) { return false; }
}

// =================================================================== rasmlar
const STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5l2.9 6 6.6.8-4.9 4.5 1.3 6.5L12 17.1 6.1 20.3l1.3-6.5L2.5 9.3l6.6-.8z" fill="#FFC93C" stroke="#E0A500" stroke-width="1.2" stroke-linejoin="round"/></svg>';
const BACK = '<svg viewBox="0 0 24 24" fill="none" stroke="#1D2A5B" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>';
const SPK = '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10v4h4l5 4V6L8 10z" fill="#fff"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/><path d="M19 6a8.5 8.5 0 0 1 0 12"/></svg>';
const ARW = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;

// Hayvon yuzi: [bosh rangi, quloqlar (orqada), quloq rangi, burun/tumshuq, burun rangi, qo'shimcha (oldida)]
const ANIMAL = {
  mushuk: {n: "Mushukcha", c: "#FFB020", ears: "M12 22 L16 4 L27 15 Z M48 22 L44 4 L33 15 Z", ec: "#FFB020",
    nose: "M27 37 L33 37 L30 41 Z", nc: "#E5487F", extra: '<path d="M8 38 H20 M8 43 H20 M40 38 H52 M40 43 H52" stroke="#1D2A5B" stroke-width="1.6" stroke-linecap="round"/>'},
  kuchuk: {n: "Kuchukcha", c: "#C99A6B", ears: "M10 18 C2 24 6 42 15 39 L17 21 Z M50 18 C58 24 54 42 45 39 L43 21 Z", ec: "#7E5432",
    nose: "M25 38 a5 3.5 0 1 0 10 0 a5 3.5 0 1 0 -10 0 Z", nc: "#1D2A5B", extra: '<path d="M30 44 v3" stroke="#1D2A5B" stroke-width="2"/>'},
  quyon: {n: "Quyoncha", c: "#F4F1FF", ears: "M20 20 C13 -2 23 -4 26 16 Z M40 20 C47 -2 37 -4 34 16 Z", ec: "#C9C3E6",
    nose: "M28 37 a2.5 2 0 1 0 5 0 a2.5 2 0 1 0 -5 0 Z", nc: "#F7A8B8", extra: '<path d="M30 39 v4 M27 44 h6" stroke="#1D2A5B" stroke-width="1.6" stroke-linecap="round"/>'},
  ayiq: {n: "Ayiqcha", c: "#B07A4F", ears: "M14 12 a8 8 0 1 0 0.1 0 Z M46 12 a8 8 0 1 0 0.1 0 Z", ec: "#8A5A35",
    nose: "M22 40 a8 6 0 1 0 16 0 a8 6 0 1 0 -16 0 Z", nc: "#E8C9A6", extra: '<circle cx="30" cy="38" r="2.6" fill="#1D2A5B"/>'},
  qurbaqa: {n: "Qurbaqa", c: "#3BB273", ears: "M14 20 a8 8 0 1 0 0.1 0 Z M46 20 a8 8 0 1 0 0.1 0 Z", ec: "#3BB273",
    nose: "M20 41 Q30 49 40 41", nc: "none", extra: '<path d="M20 41 Q30 49 40 41" fill="none" stroke="#1D2A5B" stroke-width="2.2" stroke-linecap="round"/><circle cx="14" cy="18" r="4" fill="#fff"/><circle cx="46" cy="18" r="4" fill="#fff"/>'},
  joja: {n: "Jo'ja", c: "#FFE14D", ears: "M26 14 C24 6 30 4 30 12 C31 5 37 6 34 14 Z", ec: "#FFC21F",
    nose: "M26 37 L34 37 L30 43 Z", nc: "#FF8A1F", extra: ""},
  sigir: {n: "Sigir", c: "#FFFFFF", ears: "M4 24 L17 18 L15 30 Z M56 24 L43 18 L45 30 Z M18 16 C15 6 20 5 23 15 Z M42 16 C45 6 40 5 37 15 Z", ec: "#1D2A5B",
    nose: "M17 42 a13 8 0 1 0 26 0 a13 8 0 1 0 -26 0 Z", nc: "#F7A8B8", extra: '<circle cx="24" cy="42" r="2" fill="#B5576C"/><circle cx="36" cy="42" r="2" fill="#B5576C"/><path d="M37 18 a7 6 0 1 0 8 6" fill="#1D2A5B"/>'},
  xoroz: {n: "Xo'roz", c: "#FFB020", ears: "M22 16 C19 2 28 2 28 11 C30 0 39 2 35 16 Z", ec: "#FF4B3E",
    nose: "M26 36 L34 36 L30 44 Z", nc: "#FF8A1F", extra: '<path d="M28 44 C26 52 34 52 32 44 Z" fill="#FF4B3E"/>'},
  qoy: {n: "Qo'zichoq", c: "#F1EEE6", ears: "M6 27 a8 5 0 1 0 13 0 Z M41 27 a8 5 0 1 0 13 0 Z", ec: "#C9C3B4",
    nose: "M27 39 a3 2 0 1 0 6 0 a3 2 0 1 0 -6 0 Z", nc: "#1D2A5B", extra: '<circle cx="19" cy="16" r="7" fill="#E4DFD3"/><circle cx="30" cy="12" r="8" fill="#E4DFD3"/><circle cx="41" cy="16" r="7" fill="#E4DFD3"/>'},
  ordak: {n: "O'rdak", c: "#FFFFFF", ears: "", ec: "none",
    nose: "M20 39 Q30 34 40 39 Q30 47 20 39 Z", nc: "#FF8A1F", extra: '<path d="M30 14 C28 8 34 8 33 13" fill="none" stroke="#C9C3B4" stroke-width="3" stroke-linecap="round"/>'},
};
function animalSVG(k) {
  const a = ANIMAL[k];
  return `<svg viewBox="0 0 60 60" aria-hidden="true">${a.ears ? `<path d="${a.ears}" fill="${a.ec}"/>` : ""}
    <circle cx="30" cy="34" r="20" fill="${a.c}" stroke="#E2DCCF" stroke-width="${a.c === "#FFFFFF" || a.c === "#F4F1FF" || a.c === "#F1EEE6" ? 1.5 : 0}"/>
    <circle cx="23" cy="30" r="3" fill="#1D2A5B"/><circle cx="37" cy="30" r="3" fill="#1D2A5B"/>
    <circle cx="24" cy="29" r="1" fill="#fff"/><circle cx="38" cy="29" r="1" fill="#fff"/>
    ${a.nc !== "none" ? `<path d="${a.nose}" fill="${a.nc}"/>` : ""}${a.extra}</svg>`;
}
const BALLOON = (c) => `<svg viewBox="0 0 96 150" aria-hidden="true"><path d="M48 112 C44 125 54 132 46 148" fill="none" stroke="#5C6A99" stroke-width="2"/>
  <ellipse cx="48" cy="56" rx="42" ry="52" fill="${c}"/><ellipse cx="32" cy="34" rx="9" ry="15" fill="#fff" opacity=".45"/><path d="M42 106 L54 106 L48 114 Z" fill="${c}"/></svg>`;
const APPLE = (c = "#FF4B3E") => `<svg viewBox="0 0 54 58" aria-hidden="true"><path d="M27 12 C27 6 30 3 34 2" fill="none" stroke="#6B4423" stroke-width="3" stroke-linecap="round"/>
  <path d="M30 8 C38 2 46 6 44 10 C38 12 33 11 30 8 Z" fill="#7ED957"/><path d="M27 16 C14 8 2 18 4 32 C6 48 18 58 27 52 C36 58 48 48 50 32 C52 18 40 8 27 16 Z" fill="${c}"/>
  <ellipse cx="16" cy="26" rx="4" ry="7" fill="#fff" opacity=".5"/></svg>`;

// =================================================================== o'yinlar ro'yxati
const GAMES = [
  {id: "sharcha", n: "Sharcha portlat", age: "3–6 yosh", bg: "#BFE6FF", c1: "#FFD6D0", c2: "#FF6B57", edge: "#8CC4E8", ic: BALLOON("#FF6B57")},
  {id: "juftlik", n: "Juftini top", age: "4–8 yosh", bg: "#D9F2E3", c1: "#D9F2E3", c2: "#3BB273", edge: "#9ED6B5", ic: animalSVG("mushuk")},
  {id: "poyezd", n: "Alifbo poyezdi", age: "5–7 yosh", bg: "#E6DFFF", c1: "#E6DFFF", c2: "#7A5CFA", edge: "#B8A9F5",
    ic: '<svg viewBox="0 0 84 84" aria-hidden="true"><rect x="6" y="30" width="72" height="34" rx="10" fill="#7A5CFA"/><rect x="44" y="12" width="28" height="26" rx="6" fill="#7A5CFA"/><rect x="50" y="18" width="16" height="12" rx="3" fill="#fff"/><circle cx="24" cy="68" r="9" fill="#1D2A5B"/><circle cx="60" cy="68" r="9" fill="#1D2A5B"/><text x="24" y="54" font-size="20" font-weight="800" fill="#fff" text-anchor="middle" font-family="Bal,sans-serif">A</text></svg>'},
  {id: "sanoq", n: "Mevalarni sana", age: "3–6 yosh", bg: "#FFF0C2", c1: "#FFF0C2", c2: "#E0A500", edge: "#EBCB6B", ic: APPLE()},
  {id: "boyoq", n: "Bo'yoqchi", age: "3–8 yosh", bg: "#FFDDEB", c1: "#FFDDEB", c2: "#E5487F", edge: "#F2A9C6",
    ic: '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M30 6 L42 18 L22 38 L10 26 Z" fill="#E5487F"/><path d="M10 26 L22 38 L12 42 Q4 44 6 36 Z" fill="#FFB020"/><path d="M30 6 L42 18" stroke="#1D2A5B" stroke-width="3" stroke-linecap="round"/></svg>'},
  {id: "shakl", n: "Shakllar", age: "2–5 yosh", bg: "#D6EEFF", c1: "#D6EEFF", c2: "#2E86DE", edge: "#96C9EE",
    ic: '<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="15" cy="15" r="10" fill="#FF6B57"/><rect x="26" y="5" width="18" height="18" rx="4" fill="#2E86DE"/><path d="M15 27 L26 45 L4 45 Z" fill="#3BB273"/><path d="M35 26l2.9 6 6.6.8-4.9 4.5 1.3 6.5-5.9-3.2-5.9 3.2 1.3-6.5-4.9-4.5 6.6-.8z" fill="#FFC93C"/></svg>'},
  {id: "ovoz", n: "Kim ovoz chiqardi?", age: "2–5 yosh", bg: "#FFE3CC", c1: "#FFE3CC", c2: "#E67E22", edge: "#F2B98A", ic: animalSVG("sigir")},
  {id: "labirint", n: "Quyoncha yo'li", age: "4–8 yosh", bg: "#D9F2E3", c1: "#D9F2E3", c2: "#2E9E60", edge: "#9ED6B5", ic: animalSVG("quyon")},
  {id: "kiyin", n: "Ob-havoga kiyin", age: "3–6 yosh", bg: "#E6DFFF", c1: "#E6DFFF", c2: "#6A4FE0", edge: "#B8A9F5",
    ic: '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 28 Q10 6 24 6 Q38 6 40 28 Z" fill="#FF4B3E"/><rect x="5" y="26" width="38" height="9" rx="4.5" fill="#fff" stroke="#E2DCCF"/><circle cx="24" cy="5" r="5" fill="#fff" stroke="#E2DCCF"/></svg>'},
  {id: "pianino", n: "Kichkina pianino", age: "2–7 yosh", bg: "#FFD6D0", c1: "#FFD6D0", c2: "#E0533F", edge: "#F2A99E",
    ic: '<svg viewBox="0 0 48 48" aria-hidden="true"><rect x="4" y="8" width="40" height="7" rx="3.5" fill="#FF4B3E"/><rect x="7" y="18" width="34" height="7" rx="3.5" fill="#FFC21F"/><rect x="10" y="28" width="28" height="7" rx="3.5" fill="#3BB273"/><rect x="13" y="38" width="22" height="7" rx="3.5" fill="#2E86DE"/></svg>'},
];
const GBY = Object.fromEntries(GAMES.map((g) => [g.id, g]));

// =================================================================== holat
let opened = false, mounted = false, cur = null;    // cur — ochiq o'yin id
let stars = lsGet("zk_gstars", 0);
let played = lsGet("zk_gplayed", {});
let S = {};                                         // joriy o'yin holati
const timers = new Set();
const later = (fn, ms) => { const t = setTimeout(() => { timers.delete(t); fn(); }, ms); timers.add(t); return t; };
const clearTimers = () => { timers.forEach(clearTimeout); timers.clear();
  if (S.raf) cancelAnimationFrame(S.raf); if (S.tick) clearInterval(S.tick); };

function addStar(n = 1) {
  stars += n; lsSet("zk_gstars", stars);
  if (cur) { played[cur] = (played[cur] || 0) + n; lsSet("zk_gplayed", played); }
  const el = document.querySelector(".gx-stars");
  if (el) { el.querySelector("b").textContent = stars; el.classList.remove("pulse"); void el.offsetWidth; el.classList.add("pulse"); }
}
function yay(text = "Barakalla!", n = 1) {
  addStar(n); sfx.win(); haptic("ok");
  const box = document.createElement("div");
  box.className = "gx-yay";
  const cols = ["#FF6B57", "#FFC93C", "#3BB273", "#2E86DE", "#7A5CFA", "#E5487F"];
  box.innerHTML = `<div class="ycard">${STAR}<b class="b">${text}</b></div>` + (reduced() ? "" : Array.from({length: 26}, (_, i) =>
    `<i style="background:${cols[i % 6]};--dx:${rnd(360) - 180}px;--dy:${rnd(360) - 220}px;--r:${rnd(720)}deg"></i>`).join(""));
  $("games").appendChild(box);
  setTimeout(() => box.remove(), 1300);   // o'yindan chiqilsa ham albatta yo'qoladi
}
function wrong(el) {
  sfx.err(); haptic("err");
  if (el) { el.classList.remove("wig"); void el.offsetWidth; el.classList.add("wig"); }
}

// =================================================================== chizish
function segHTML() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["games", "O'yinlar"]];
  return `<div class="gx-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "games" ? "on" : ""}">${l}</button>`).join("")}</div>`;
}
const starsHTML = () => `<div class="gx-stars" aria-label="Yulduzchalar: ${stars}">${STAR}<b class="b">${stars}</b></div>`;
function bar(g, right = "") {
  return `<div class="gx-bar"><button class="gx-back" data-home aria-label="Orqaga">${BACK}</button>
    <div class="gx-title b">${g.n}</div>${right || starsHTML()}</div>`;
}
function setBg(c, edge) {
  const el = $("games"); el.style.setProperty("--bg", c); el.style.setProperty("--edge", edge || "#9CCBEA");
  const n = parseInt(c.slice(1), 16), lum = ((n >> 16) * 299 + ((n >> 8) & 255) * 587 + (n & 255) * 114) / 1000;
  el.classList.toggle("dark", lum < 110);
  try { tg.setHeaderColor(c); tg.setBackgroundColor(c); if (tg.setBottomBarColor) tg.setBottomBarColor(c); } catch (e) {}
}

const CATS = [["all", "Hammasi"], ["new", "Yangi"], ["harakat", "Harakatli"], ["aql", "Aqlli"], ["musiqa", "Musiqa"], ["sport", "Sport"], ["ijod", "Ijodiy"], ["hayvon", "Hayvonlar"]];
let homeCat = lsGet("zk_gcat", "all");
function renderHome() {
  setBg("#DFF3FF");
  const tile = (g) => `<button class="gx-tile" data-game="${g.id}" style="--c1:${g.c1};--c2:${g.c2}">${g.v3 ? '<em class="g-new">Yangi</em>' : ""}
      <span class="ic">${g.ic}</span><b class="b">${g.n}</b><small>${g.age}${played[g.id] ? ` · ${played[g.id]} ★` : ""}</small></button>`;
  const pet = lsGet("zk_gpet", null);
  const petMsg = pet ? petMood(petLoad()) : "Menga ism qo'yilgan: Dumboq. Keling, tanishamiz!";
  const list = GAMES.filter((g) => g.id !== "kuchuk" && (homeCat === "all" || (homeCat === "new" ? g.v3 : g.cat === homeCat)));
  $("gxview").innerHTML = `<div class="gx-bar">${segHTML()}${starsHTML()}</div>
    <div class="g-hero"><span class="av">${ANOR()}</span>
      <div class="bub"><b class="b">Salom! Men Anorjon.</b><span>${GAMES.length} ta o'yin seni kutyapti!</span></div>
      ${chestReady() ? `<button class="g-chest" data-chest aria-label="Kunlik sovg'a sandiqchasi"><svg viewBox="0 0 60 56" aria-hidden="true"><rect x="6" y="22" width="48" height="30" rx="6" fill="#B5651D"/><path d="M6 24 Q30 2 54 24 Z" fill="#D9822B"/><rect x="26" y="20" width="8" height="32" fill="#FFC93C"/><rect x="24" y="26" width="12" height="10" rx="2" fill="#FFE66D"/></svg><i>1</i></button>` : ""}</div>
    <button class="g-petcard" data-game="kuchuk"><span class="ic">${PUP(false)}</span><span class="tx"><b class="b">Mening kuchukcham</b><small>${petMsg}</small></span>
      <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width:26px;height:26px;flex:none"><path d="M9 5l7 7-7 7"/></svg></button>
    <div class="g-cats">${CATS.map(([k, l]) => `<button class="b${homeCat === k ? " on" : ""}" data-cat="${k}">${l}</button>`).join("")}</div>
    <div class="gx-grid">${list.map(tile).join("")}</div>
    <div class="gx-parent"><svg viewBox="0 0 24 24" fill="none" stroke="#FFC93C" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>
      Reklama yo'q, tashqi havola yo'q — bola faqat o'yinlarni ko'radi</div>`;
}

function open(id) {
  clearTimers(); cur = id; S = {};
  const g = GBY[id];
  setBg(g.bg, g.edge);
  ctx();
  START[id]();
  $("gxscroll").scrollTop = 0;
  updateBack();
}
function home() { document.querySelectorAll(".gx-yay").forEach((x) => x.remove()); clearTimers(); cur = null; S = {}; try { speechSynthesis.cancel(); } catch (e) {} renderHome(); $("gxscroll").scrollTop = 0; updateBack(); }
const view = (html) => { $("gxview").innerHTML = html; };

// =================================================================== 1. Sharcha portlat
const ABC = "A B D E F G H I J K L M N O P Q R S T U V X Y Z".split(" ");
const BCOL = ["#FF6B57", "#7A5CFA", "#3BB273", "#FFB020", "#E5487F", "#2E86DE"];
const SLOTS = [[6, 20], [138, 70], [262, 10], [30, 230], [160, 280], [268, 210]];
function sharchaRound() {
  const g = GBY.sharcha, target = ABC[rnd(ABC.length)];
  const others = pickN(ABC.filter((x) => x !== target), 3);
  const letters = shuffle([target, target, target, ...others]);
  S.target = target; S.left = 3;
  const w = Math.min(window.innerWidth, 480), k = (w - 16) / 374;
  view(bar(g) + `<div class="gx-q"><button class="say" data-say aria-label="Qayta eshitish">${SPK}</button>
      <b class="b">«<em>${target}</em>» harfli sharchalarni portlat!</b></div>
    <div class="g-sky" id="gsky"><div class="g-ground"></div>${letters.map((l, i) => `<button class="g-bal" data-bal="${l}" aria-label="${l} harfli sharcha"
      style="left:${Math.round(SLOTS[i][0] * k + 8)}px;top:${SLOTS[i][1] + 10}px;--t:${(2.4 + Math.random() * 1.6).toFixed(1)}s;animation-delay:-${(Math.random() * 2).toFixed(1)}s">
      ${BALLOON(BCOL[i])}<span class="b">${l}</span></button>`).join("")}</div>
    <div class="gx-dots">${Array.from({length: 5}, (_, i) => `<i class="${i < (S.round || 0) ? "on" : ""}"></i>`).join("")}</div>`);
  say(`${target} harfli sharchalarni portlat`);
}
const START = {};
START.sharcha = () => { S.round = 0; sharchaRound(); };
function onBalloon(b) {
  if (b.classList.contains("pop")) return;
  if (b.dataset.bal !== S.target) { wrong(b); return; }
  b.classList.add("pop"); sfx.pop(); haptic("hit"); b.disabled = true;
  if (--S.left > 0) return;
  S.round++;
  if (S.round >= 5) { yay("Zo'r! 5 ta raund", 2); later(() => { S.round = 0; sharchaRound(); }, 1500); }
  else { sfx.ok(); haptic("ok"); addStar(1); later(sharchaRound, 700); }
}

// =================================================================== 2. Juftini top
START.juftlik = () => {
  const kinds = pickN(["mushuk", "kuchuk", "quyon", "ayiq", "qurbaqa", "joja", "sigir", "xoroz", "qoy", "ordak"], 6);
  S.cards = shuffle([...kinds, ...kinds]).map((k) => ({k, open: false, got: false}));
  S.first = null; S.lock = false; S.pairs = 0; S.moves = 0;
  drawJuftlik();
};
function drawJuftlik() {
  const g = GBY.juftlik;
  view(bar(g, `<div class="gx-pill b">${S.pairs} / 6 juft</div>`) +
    `<div class="gx-h b">Bir xil hayvonlarni top</div>
    <div class="g-cards">${S.cards.map((c, i) => `<button class="g-card${c.open ? " open" : ""}${c.got ? " got" : ""}" data-card="${i}" aria-label="${c.open || c.got ? ANIMAL[c.k].n : "Yopiq karta"}">
      <span class="in"><span class="fa">${STAR.replace('fill="#FFC93C" stroke="#E0A500"', 'fill="#fff" stroke="none" opacity=".85"')}</span><span class="ba">${animalSVG(c.k)}</span></span></button>`).join("")}</div>
    <div class="gx-fill"></div>
    <div style="text-align:center;color:var(--ink2);padding:14px 0 22px">Urinishlar: <b class="b">${S.moves}</b></div>`);
}
function onCard(el) {
  const i = +el.dataset.card, c = S.cards[i];
  if (S.lock || c.open || c.got) return;
  c.open = true; el.classList.add("open"); sfx.flip(); haptic();
  el.setAttribute("aria-label", ANIMAL[c.k].n);
  if (S.first === null) { S.first = i; return; }
  const a = S.cards[S.first]; S.moves++;
  if (a.k === c.k) {
    a.got = c.got = true; a.open = c.open = false; S.first = null; S.pairs++;
    later(() => { sfx.ok(); drawJuftlik(); if (S.pairs === 6) { yay("Hammasini topding!", 2); later(START.juftlik, 1700); } }, 350);
  } else {
    S.lock = true;
    later(() => { a.open = c.open = false; S.first = null; S.lock = false; drawJuftlik(); }, 900);
  }
}

// =================================================================== 3. Alifbo poyezdi
const WCOL = ["#3BB273", "#2E86DE", "#E5487F", "#FFB020"];
START.poyezd = () => { S.st = 1; poyezdRound(); };
function poyezdRound() {
  const g = GBY.poyezd, s = rnd(ABC.length - 3), seq = ABC.slice(s, s + 4), hole = 1 + rnd(3);
  S.answer = seq[hole];
  const ch = shuffle([S.answer, ...pickN(ABC.filter((x) => x !== S.answer), 2)]);
  view(bar(g, `<div class="gx-pill b">${S.st}-bekat</div>`) +
    `<div class="gx-h b">Bo'sh vagonga qaysi harf tushadi?</div>
    <div class="g-train"><div class="g-rail"></div><div class="g-cars" id="gcars">
      ${seq.map((l, i) => `<div class="g-wag"><div class="box b${i === hole ? " vacant" : ""}" ${i === hole ? 'id="ghole"' : `style="background:${WCOL[i]}"`}>${i === hole ? "" : l}</div>
        <i class="w" style="left:8px"></i><i class="w" style="right:8px"></i></div>`).join("")}
      <svg width="84" height="104" viewBox="0 0 84 104" aria-hidden="true"><rect x="6" y="34" width="72" height="50" rx="12" fill="#FF6B57"/><rect x="40" y="10" width="32" height="34" rx="6" fill="#FF6B57"/>
        <rect x="46" y="16" width="20" height="16" rx="4" fill="#fff"/><rect x="14" y="16" width="14" height="22" rx="3" fill="#1D2A5B"/>
        <circle cx="26" cy="90" r="11" fill="#1D2A5B" stroke="#fff" stroke-width="4"/><circle cx="62" cy="90" r="11" fill="#1D2A5B" stroke="#fff" stroke-width="4"/></svg>
    </div></div>
    <div class="gx-fill"></div>
    <div class="g-tray"><div class="hint">To'g'ri harfni bos</div><div class="g-ch3">
      ${ch.map((l, i) => `<button class="gx-big b" data-pick="${l}" style="--c1:${["#FFB020", "#7A5CFA", "#2E86DE"][i]};--c2:${["#C98500", "#5536D6", "#1C62A8"][i]}" aria-label="${l} harfi">${l}</button>`).join("")}</div></div>`);
}
function onPoyezd(b) {
  if (S.lock) return;
  if (b.dataset.pick !== S.answer) { wrong(b); return; }
  S.lock = true;
  const h = $("ghole"); h.classList.remove("vacant"); h.style.background = "#7A5CFA"; h.textContent = S.answer;
  sfx.ok(); haptic("ok");
  later(() => { $("gcars") && $("gcars").classList.add("go"); tone(300, 0.5, "sawtooth", 0.06, 0, 500); }, 450);
  later(() => { S.st++; S.lock = false; if (S.st % 5 === 1) yay("Poyezd manzilga yetdi!"); else addStar(1); poyezdRound(); }, 1600);
}

// =================================================================== 4. Mevalarni sana
const TREE_SPOTS = [[120, 80], [220, 60], [290, 150], [70, 200], [180, 190], [250, 240], [130, 270], [40, 120], [300, 70]];
START.sanoq = () => { S.q = 0; S.ok = 0; sanoqRound(); };
function sanoqRound() {
  const g = GBY.sanoq, n = 1 + rnd(Math.min(9, 3 + S.q)), kind = rnd(3);
  const color = ["#FF4B3E", "#FFC21F", "#7ED957"][kind];
  S.n = n;
  const opts = shuffle([n, ...pickN([1, 2, 3, 4, 5, 6, 7, 8, 9].filter((x) => x !== n), 3)]);
  view(bar(g, `<div class="gx-pill b">${S.q + 1} / 10</div>`) +
    `<div class="gx-h b">Daraxtda nechta ${kind === 1 ? "sariq" : kind === 2 ? "yashil" : "qizil"} olma bor?</div>
    <div class="g-tree"><svg width="390" height="400" viewBox="0 0 390 400" aria-hidden="true"><rect x="176" y="250" width="38" height="150" rx="10" fill="#9C6B3E"/>
      <circle cx="195" cy="170" r="120" fill="#3BB273"/><circle cx="110" cy="200" r="70" fill="#34A267"/><circle cx="285" cy="195" r="72" fill="#34A267"/>
      <ellipse cx="195" cy="390" rx="150" ry="12" fill="#EBCB6B"/></svg>
      ${pickN(TREE_SPOTS, n).map(([x, y]) => `<span class="g-fruit" style="left:calc(50% - 195px + ${Math.round(x)}px);top:${y}px;animation-delay:-${(Math.random() * 2).toFixed(1)}s">${APPLE(color)}</span>`).join("")}</div>
    <div class="gx-fill"></div>
    <div class="g-ch4">${opts.map((v) => `<button class="gx-big b" data-num="${v}" aria-label="${v}">${v}</button>`).join("")}</div>`);
}
function onSanoq(b) {
  if (S.lock) return;
  if (+b.dataset.num !== S.n) { wrong(b); return; }
  S.lock = true; b.style.setProperty("--c1", "#3BB273"); b.style.setProperty("--c2", "#2A8A55"); b.style.color = "#fff";
  sfx.ok(); haptic("ok");
  later(() => { S.lock = false; S.q++; if (S.q >= 10) { yay("10 tadan 10!", 2); S.q = 0; } else addStar(1); sanoqRound(); }, 800);
}

// =================================================================== 5. Bo'yoqchi
const PALETTE = [["Qizil", "#FF4B3E"], ["To'q sariq", "#FFB020"], ["Sariq", "#FFE14D"], ["Yashil", "#3BB273"], ["Havorang", "#4FC3F7"],
  ["Ko'k", "#2E86DE"], ["Binafsha", "#7A5CFA"], ["Pushti", "#E5487F"], ["Jigarrang", "#9C6B3E"], ["Oq", "#FFFFFF"]];
const PICS = {
  baliq: {n: "Baliq", svg: `<svg viewBox="0 0 330 330" role="img" aria-label="Baliqcha"><g stroke="#1D2A5B" stroke-width="5" stroke-linejoin="round" stroke-linecap="round">
    <rect data-r="suv" x="4" y="4" width="322" height="322" rx="20" fill="#fff"/>
    <path data-r="dum" d="M245 150 L315 90 L305 150 L315 210 Z" fill="#fff"/>
    <ellipse data-r="tana" cx="155" cy="150" rx="110" ry="80" fill="#fff"/>
    <path data-r="suzgich" d="M135 75 Q165 20 215 85 Z" fill="#fff"/>
    <path data-r="chiziq" d="M180 120 Q205 150 180 180 L170 180 Q190 150 170 120 Z" fill="#fff"/>
    <circle data-r="koz" cx="93" cy="135" r="16" fill="#fff"/><circle cx="97" cy="135" r="6" fill="#1D2A5B" stroke="none"/>
    <path d="M57 170 Q71 180 85 172" fill="none"/>
    <path data-r="osimlik" d="M40 326 C30 280 60 270 50 230 C70 260 60 290 70 326 Z" fill="#fff"/>
    <circle data-r="pufak" cx="265" cy="50" r="13" fill="#fff"/><circle data-r="pufak2" cx="290" cy="22" r="8" fill="#fff"/></g></svg>`},
  uy: {n: "Uy", svg: `<svg viewBox="0 0 330 330" role="img" aria-label="Uycha"><g stroke="#1D2A5B" stroke-width="5" stroke-linejoin="round">
    <rect data-r="osmon" x="4" y="4" width="322" height="250" rx="20" fill="#fff"/>
    <rect data-r="yer" x="4" y="250" width="322" height="76" rx="12" fill="#fff"/>
    <circle data-r="quyosh" cx="270" cy="60" r="32" fill="#fff"/>
    <path data-r="tom" d="M60 150 L165 60 L270 150 Z" fill="#fff"/>
    <rect data-r="devor" x="80" y="150" width="170" height="120" fill="#fff"/>
    <rect data-r="eshik" x="145" y="195" width="44" height="75" rx="6" fill="#fff"/>
    <rect data-r="deraza" x="96" y="170" width="38" height="38" rx="4" fill="#fff"/>
    <rect data-r="deraza2" x="200" y="170" width="38" height="38" rx="4" fill="#fff"/>
    <path data-r="daraxt" d="M290 250 C250 250 255 180 290 175 C320 180 325 250 290 250 Z" fill="#fff"/></g></svg>`},
  gul: {n: "Gul", svg: `<svg viewBox="0 0 330 330" role="img" aria-label="Gul"><g stroke="#1D2A5B" stroke-width="5" stroke-linejoin="round">
    <rect data-r="fon" x="4" y="4" width="322" height="322" rx="20" fill="#fff"/>
    <path data-r="poya" d="M160 160 L170 160 L172 310 L158 310 Z" fill="#fff"/>
    <path data-r="barg" d="M165 250 C120 230 100 260 110 280 C140 285 160 270 165 250 Z" fill="#fff"/>
    <path data-r="barg2" d="M168 220 C210 195 235 225 225 245 C195 250 175 240 168 220 Z" fill="#fff"/>
    <circle data-r="b1" cx="165" cy="80" r="34" fill="#fff"/><circle data-r="b2" cx="225" cy="120" r="34" fill="#fff"/>
    <circle data-r="b3" cx="200" cy="185" r="34" fill="#fff"/><circle data-r="b4" cx="130" cy="185" r="34" fill="#fff"/>
    <circle data-r="b5" cx="105" cy="120" r="34" fill="#fff"/><circle data-r="markaz" cx="165" cy="135" r="34" fill="#fff"/>
    <path data-r="kapalak" d="M262 40 C240 20 230 50 260 58 C230 66 240 96 262 76 Z M266 40 C288 20 298 50 268 58 C298 66 288 96 266 76 Z" fill="#fff"/></g></svg>`},
};
START.boyoq = () => { S.pic = S.pic || "baliq"; S.col = S.col || "#FFB020"; S.fills = lsGet("zk_gpaint", {}); drawBoyoq(); };
function drawBoyoq() {
  const g = GBY.boyoq, f = S.fills[S.pic] || {};
  view(bar(g, `<button class="gx-back" data-clear aria-label="Tozalash" style="margin-left:auto"><svg viewBox="0 0 24 24" fill="none" stroke="#1D2A5B" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg></button>`) +
    `<div class="g-pics">${Object.entries(PICS).map(([k, p]) => `<button class="b${k === S.pic ? " on" : ""}" data-pic="${k}">${p.n}</button>`).join("")}</div>
    <div class="g-paper" id="gpaper">${PICS[S.pic].svg}</div>
    <div class="gx-fill"></div>
    <div class="g-pal">${PALETTE.map(([n, c]) => `<button data-col="${c}" class="${c === S.col ? "on" : ""}" style="background:${c}" aria-label="${n}"></button>`).join("")}</div>`);
  $("gpaper").querySelectorAll("[data-r]").forEach((el) => { if (f[el.dataset.r]) el.setAttribute("fill", f[el.dataset.r]); });
}
function onPaint(el) {
  const r = el.dataset.r;
  el.setAttribute("fill", S.col); sfx.tap(); haptic();
  const f = S.fills[S.pic] = S.fills[S.pic] || {};
  const was = Object.keys(f).length;
  f[r] = S.col; lsSet("zk_gpaint", S.fills);
  const total = $("gpaper").querySelectorAll("[data-r]").length;
  if (was < total && Object.keys(f).length === total) later(() => yay("Ajoyib rasm!"), 200);
}

// =================================================================== 6. Shakllar
const SHAPES = {
  doira: {n: "Doira", c: "#FF6B57", d: '<circle cx="50" cy="50" r="44" fill="C"/>'},
  kvadrat: {n: "Kvadrat", c: "#2E86DE", d: '<rect x="8" y="8" width="84" height="84" rx="12" fill="C"/>'},
  uchburchak: {n: "Uchburchak", c: "#3BB273", d: '<path d="M50 8 L94 88 L6 88 Z" fill="C" stroke="C" stroke-width="8" stroke-linejoin="round"/>'},
  yulduz: {n: "Yulduz", c: "#FFC93C", d: '<path d="M50 6l12 25 27.5 3.4-20.4 18.8 5.4 27.2L50 67 25.5 80.4l5.4-27.2L10.5 34.4 38 31z" fill="C" stroke="C" stroke-width="5" stroke-linejoin="round"/>'},
  yurak: {n: "Yurak", c: "#E5487F", d: '<path d="M50 88 C10 60 4 34 22 20 C36 10 48 20 50 30 C52 20 64 10 78 20 C96 34 90 60 50 88 Z" fill="C"/>'},
  oy: {n: "Oy", c: "#7A5CFA", d: '<path d="M62 8 A44 44 0 1 0 92 70 A34 34 0 1 1 62 8 Z" fill="C"/>'},
};
const shapeSVG = (k, color) => `<svg viewBox="0 0 100 100" aria-hidden="true">${SHAPES[k].d.replace(/C"/g, `${color}"`)}</svg>`;
START.shakl = () => {
  S.holes = pickN(Object.keys(SHAPES), 4); S.queue = shuffle(S.holes); S.done = []; drawShakl();
};
function drawShakl() {
  const g = GBY.shakl, piece = S.queue[0];
  view(bar(g, `<div class="gx-pill b">${S.done.length} / 4</div>`) +
    `<div class="gx-h b">Shaklni o'z uyachasiga joyla</div>
    <div class="g-board">${S.holes.map((k) => `<button class="g-hole" data-hole="${k}" aria-label="${SHAPES[k].n} uyachasi">
      ${shapeSVG(k, S.done.includes(k) ? SHAPES[k].c : "#7E5432")}</button>`).join("")}</div>
    <div class="gx-fill"></div>
    <div class="g-tray"><div class="hint">${piece ? `Bu — <b class="b">${SHAPES[piece].n.toLowerCase()}</b>. Qaysi uyachaga tushadi?` : "Hammasi joyida!"}</div>
      <div class="g-piece">${piece ? shapeSVG(piece, SHAPES[piece].c) : STAR}</div></div>`);
}
function onHole(b) {
  const k = b.dataset.hole, piece = S.queue[0];
  if (!piece || S.done.includes(k)) return;
  if (k !== piece) { wrong(b); return; }
  S.done.push(k); S.queue.shift(); sfx.ok(); haptic("ok"); drawShakl();
  if (!S.queue.length) { yay("Hammasi joyida!"); later(START.shakl, 1600); }
}

// =================================================================== 7. Kim ovoz chiqardi?
const VOICED = Object.keys(CALL);
START.ovoz = () => { S.score = 0; ovozRound(); };
function ovozRound() {
  const g = GBY.ovoz, four = pickN(VOICED, 4);
  S.target = four[rnd(4)];
  view(bar(g) + `<button class="g-spk" id="gspk" data-spk aria-label="Ovozni tinglash">${SPK}</button>
    <div class="gx-h b" style="text-align:center;margin-top:34px">Tingla va hayvonni bos</div>
    <div class="gx-fill" style="min-height:16px"></div>
    <div class="g-ani">${four.map((k) => `<button data-ani="${k}" aria-label="${ANIMAL[k].n}">${animalSVG(k)}<b class="b">${ANIMAL[k].n}</b></button>`).join("")}</div>`);
  later(playCall, 500);
}
function playCall() {
  const c = ctx(); if (!c || !S.target) return;
  CALL[S.target](c);
  const s = $("gspk"); if (s) { s.classList.remove("g-ringing"); void s.offsetWidth; s.classList.add("g-ringing"); }
}
function onAnimal(b) {
  if (S.lock) return;
  if (b.dataset.ani !== S.target) { wrong(b); return; }
  S.lock = true; b.style.boxShadow = "0 0 0 5px #3BB273, 0 6px 0 #F2B98A"; sfx.ok(); haptic("ok");
  S.score++;
  later(() => { S.lock = false; if (S.score % 5 === 0) yay("Qulog'ing o'tkir!"); else addStar(1); ovozRound(); }, 900);
}

// =================================================================== 8. Quyoncha yo'li (labirint)
function makeMaze(cols, rows) {
  const cells = Array.from({length: rows}, () => Array.from({length: cols}, () => ({n: true, s: true, e: true, w: true, v: false})));
  const stack = [[0, 0]]; cells[0][0].v = true;
  while (stack.length) {
    const [x, y] = stack[stack.length - 1];
    const nb = [[0, -1, "n", "s"], [0, 1, "s", "n"], [1, 0, "e", "w"], [-1, 0, "w", "e"]]
      .map(([dx, dy, a, b]) => [x + dx, y + dy, a, b]).filter(([nx, ny]) => nx >= 0 && ny >= 0 && nx < cols && ny < rows && !cells[ny][nx].v);
    if (!nb.length) { stack.pop(); continue; }
    const [nx, ny, a, b] = nb[rnd(nb.length)];
    cells[y][x][a] = false; cells[ny][nx][b] = false; cells[ny][nx].v = true; stack.push([nx, ny]);
  }
  return cells;
}
START.labirint = () => { S.lvl = S.lvl || 1; labRound(); };
function labRound() {
  const cols = Math.min(4 + S.lvl, 9), rows = Math.min(5 + S.lvl, 11);
  S.maze = makeMaze(cols, rows); S.cols = cols; S.rows = rows; S.pos = [0, 0]; S.trail = [[0, 0]]; S.lock = false;
  drawLab();
}
function drawLab() {
  const g = GBY.labirint, cs = 40, W = S.cols * cs, H = S.rows * cs;
  let walls = "";
  S.maze.forEach((row, y) => row.forEach((c, x) => {
    const X = x * cs, Y = y * cs;
    if (c.n) walls += `M${X} ${Y}h${cs}`; if (c.w) walls += `M${X} ${Y}v${cs}`;
    if (y === S.rows - 1 && c.s) walls += `M${X} ${Y + cs}h${cs}`; if (x === S.cols - 1 && c.e) walls += `M${X + cs} ${Y}v${cs}`;
  }));
  const [px, py] = S.pos, half = cs / 2;
  view(bar(g, `<div class="gx-pill b">${S.lvl}-daraja</div>`) +
    `<div class="gx-h b">Quyonchani sabzigacha olib bor</div>
    <div class="g-maze" id="gmaze"><svg viewBox="-6 -6 ${W + 12} ${H + 12}" role="img" aria-label="Labirint">
      <rect x="-6" y="-6" width="${W + 12}" height="${H + 12}" rx="14" fill="#EAF8EF"/>
      <path d="${S.trail.map(([x, y], i) => `${i ? "L" : "M"}${x * cs + half} ${y * cs + half}`).join("")}" fill="none" stroke="#FFB020" stroke-width="6" stroke-dasharray="2 10" stroke-linecap="round"/>
      <path d="${walls}" stroke="#2E9E60" stroke-width="6" stroke-linecap="round" fill="none"/>
      <g transform="translate(${(S.cols - 1) * cs + 8} ${(S.rows - 1) * cs + 4}) scale(.6)"><path d="M18 4 C14 -4 8 -2 12 6 M20 4 C22 -6 30 -4 24 6" fill="none" stroke="#3BB273" stroke-width="4" stroke-linecap="round"/>
        <path d="M8 8 H32 L20 52 Z" fill="#FF8A1F"/></g>
      <g transform="translate(${px * cs + 2} ${py * cs + 2}) scale(.6)">${animalSVG("quyon").replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "")}</g>
    </svg></div>
    <div class="gx-fill"></div>
    <div class="g-pad"><span></span><button data-mv="0,-1" aria-label="Yuqoriga">${ARW("M5 15l7-7 7 7")}</button><span></span>
      <button data-mv="-1,0" aria-label="Chapga">${ARW("M15 5l-7 7 7 7")}</button><button data-mv="0,1" aria-label="Pastga">${ARW("M5 9l7 7 7-7")}</button>
      <button data-mv="1,0" aria-label="O'ngga">${ARW("M9 5l7 7-7 7")}</button></div>`);
  bindSwipe();
}
function move(dx, dy) {
  if (S.lock) return;
  const [x, y] = S.pos, c = S.maze[y][x];
  const blocked = (dy === -1 && c.n) || (dy === 1 && c.s) || (dx === 1 && c.e) || (dx === -1 && c.w);
  if (blocked) { wrong($("gmaze")); return; }
  S.pos = [x + dx, y + dy];
  const prev = S.trail[S.trail.length - 2];
  if (prev && prev[0] === S.pos[0] && prev[1] === S.pos[1]) S.trail.pop(); else S.trail.push(S.pos.slice());
  sfx.step(); haptic();
  drawLab();
  if (S.pos[0] === S.cols - 1 && S.pos[1] === S.rows - 1) {
    S.lock = true; yay("Sabzi topildi!");
    later(() => { S.lvl++; labRound(); }, 1500);
  }
}
function bindSwipe() {
  const el = $("gmaze"); if (!el) return;
  let sx = 0, sy = 0;
  el.addEventListener("touchstart", (e) => { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, {passive: true});
  el.addEventListener("touchend", (e) => {
    const dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
    Math.abs(dx) > Math.abs(dy) ? move(dx > 0 ? 1 : -1, 0) : move(0, dy > 0 ? 1 : -1);
  });
}

// =================================================================== 9. Ob-havoga kiyin
const WEAR = {
  shapka: {n: "Shapka", c: "#FF4B3E", d: "M8 30 Q10 8 24 8 Q38 8 40 30 Z M6 30 H42 V38 H6 Z"},
  sharf: {n: "Sharf", c: "#3BB273", d: "M6 14 H42 V24 H6 Z M28 24 H38 V44 H28 Z"},
  kurtka: {n: "Kurtka", c: "#2E86DE", d: "M16 6 L24 12 L32 6 L44 14 L40 22 L36 20 V44 H12 V20 L8 22 L4 14 Z"},
  qolqop: {n: "Qo'lqop", c: "#FFB020", d: "M14 44 V22 Q14 10 24 10 Q34 10 34 22 V44 Z M34 26 Q42 22 42 30 L36 34 Z"},
  shortik: {n: "Shortik", c: "#E5487F", d: "M8 8 H40 L42 40 H28 L24 22 L20 40 H6 Z"},
  kepka: {n: "Kepka", c: "#7A5CFA", d: "M8 30 Q8 10 26 10 Q40 10 40 30 Z M30 30 H46 V34 H30 Z"},
  kozoynak: {n: "Ko'zoynak", c: "#1D2A5B", d: "M4 20 H44 V24 H40 Q40 34 32 34 Q26 34 26 24 H22 Q22 34 16 34 Q8 34 8 24 H4 Z"},
  futbolka: {n: "Futbolka", c: "#FFC21F", d: "M16 6 L24 10 L32 6 L44 14 L40 22 L36 20 V42 H12 V20 L8 22 L4 14 Z"},
  soyabon: {n: "Soyabon", c: "#E5487F", d: "M4 24 Q24 -2 44 24 Z M23 24 H25 V40 Q25 45 20 44"},
  etik: {n: "Etik", c: "#3BB273", d: "M14 4 H28 V30 H42 V44 H14 Z"},
  plashch: {n: "Plashch", c: "#FFB020", d: "M18 4 H30 L42 44 H6 Z"},
};
const WEATHER = [
  {k: "qor", t: "Bugun qor yog'yapti!", s: "Issiq kiyimlarni tanla", bg: "#6A4FE0", need: ["shapka", "sharf", "kurtka", "qolqop"],
    ic: '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/><path d="M10 4.5l2 1.5 2-1.5M10 19.5l2-1.5 2 1.5"/>'},
  {k: "quyosh", t: "Bugun juda issiq!", s: "Yozgi kiyimlarni tanla", bg: "#E0A500", need: ["shortik", "kepka", "kozoynak", "futbolka"],
    ic: '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>'},
  {k: "yomgir", t: "Bugun yomg'ir yog'yapti!", s: "Ho'l bo'lmaslik uchun nima kerak?", bg: "#2E86DE", need: ["soyabon", "etik", "plashch"],
    ic: '<path d="M6 14a4 4 0 0 1 .5-8 6 6 0 0 1 11 2 3.5 3.5 0 0 1 .5 6z"/><path d="M8 17l-1 3M12 17l-1 3M16 17l-1 3"/>'},
];
START.kiyin = () => { S.wi = S.wi === undefined ? 0 : (S.wi + 1) % WEATHER.length; kiyinRound(); };
function kiyinRound() {
  const w = WEATHER[S.wi];
  const extra = pickN(Object.keys(WEAR).filter((k) => !w.need.includes(k)), 6 - w.need.length);
  S.items = shuffle([...w.need, ...extra]); S.on = [];
  drawKiyin();
}
function drawKiyin() {
  const g = GBY.kiyin, w = WEATHER[S.wi], on = (k) => S.on.includes(k);
  const kid = `<svg viewBox="0 0 270 280" role="img" aria-label="Bola: ${S.on.map((k) => WEAR[k].n).join(", ") || "hali kiyinmagan"}">
    <ellipse cx="135" cy="268" rx="100" ry="10" fill="rgba(29,42,91,.12)"/>
    <rect x="100" y="150" width="70" height="90" rx="20" fill="${on("kurtka") ? "#2E86DE" : on("futbolka") ? "#FFC21F" : on("plashch") ? "#FFB020" : "#E8E4F7"}"/>
    <rect x="108" y="230" width="22" height="34" rx="8" fill="${on("shortik") ? "#F6C9A0" : "#2E86DE"}"/><rect x="140" y="230" width="22" height="34" rx="8" fill="${on("shortik") ? "#F6C9A0" : "#2E86DE"}"/>
    ${on("shortik") ? '<path d="M100 222 H170 L172 248 H138 L135 236 L132 248 H98 Z" fill="#E5487F"/>' : ""}
    ${on("etik") ? '<rect x="104" y="246" width="30" height="22" rx="6" fill="#3BB273"/><rect x="136" y="246" width="30" height="22" rx="6" fill="#3BB273"/>' : ""}
    <rect x="80" y="160" width="20" height="58" rx="10" fill="${on("kurtka") ? "#2E86DE" : "#F6C9A0"}"/><rect x="170" y="160" width="20" height="58" rx="10" fill="${on("kurtka") ? "#2E86DE" : "#F6C9A0"}"/>
    ${on("qolqop") ? '<circle cx="90" cy="220" r="12" fill="#FFB020"/><circle cx="180" cy="220" r="12" fill="#FFB020"/>' : ""}
    <circle cx="135" cy="105" r="48" fill="#F6C9A0"/>
    <circle cx="118" cy="105" r="5" fill="#1D2A5B"/><circle cx="152" cy="105" r="5" fill="#1D2A5B"/>
    ${on("kozoynak") ? '<path d="M104 98 H166 V104 H162 Q162 118 150 118 Q140 118 140 104 H130 Q130 118 120 118 Q108 118 108 104 H104 Z" fill="#1D2A5B"/>' : ""}
    <path d="M120 126 Q135 ${S.on.length >= w.need.length ? 140 : 132} 150 126" fill="none" stroke="#1D2A5B" stroke-width="4" stroke-linecap="round"/>
    ${on("shapka") ? '<path d="M85 92 Q90 36 135 36 Q180 36 185 92 Z" fill="#FF4B3E"/><rect x="80" y="84" width="110" height="18" rx="9" fill="#fff"/><circle cx="135" cy="32" r="12" fill="#fff"/>' : on("kepka") ? '<path d="M90 86 Q92 50 135 50 Q170 50 178 86 Z" fill="#7A5CFA"/><rect x="150" y="80" width="56" height="10" rx="5" fill="#7A5CFA"/>' : '<path d="M92 86 Q100 56 135 56 Q170 56 178 86 Q160 70 135 72 Q110 70 92 86 Z" fill="#6B4423"/>'}
    ${on("sharf") ? '<path d="M92 146 Q135 164 178 146 L178 162 Q135 180 92 162 Z" fill="#3BB273"/><rect x="156" y="156" width="18" height="48" rx="6" fill="#3BB273"/>' : ""}
    ${on("soyabon") ? '<path d="M150 70 Q210 10 262 70 Z" fill="#E5487F"/><path d="M206 70 V200" stroke="#1D2A5B" stroke-width="4"/>' : ""}
    ${on("plashch") ? '<path d="M100 150 H170 L182 236 H88 Z" fill="#FFB020" opacity=".9"/>' : ""}</svg>`;
  view(bar(g) + `<div class="g-wx" style="background:${w.bg}"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" aria-hidden="true">${w.ic}</svg>
      <div><b class="b">${w.t}</b><span>${w.s}</span></div></div>
    <div class="g-kid">${kid}</div><div class="gx-fill"></div>
    <div class="g-wear">${S.items.map((k) => `<button data-wear="${k}" class="${on(k) ? "on" : ""}" aria-label="${WEAR[k].n}" aria-pressed="${on(k)}">
      <svg viewBox="0 0 48 48" aria-hidden="true"><path d="${WEAR[k].d}" fill="${WEAR[k].c}" stroke="${WEAR[k].c}" stroke-width="1" stroke-linejoin="round"/></svg>${WEAR[k].n}</button>`).join("")}</div>`);
}
function onWear(b) {
  const k = b.dataset.wear, w = WEATHER[S.wi];
  if (S.on.includes(k) || S.lock) return;
  if (!w.need.includes(k)) { wrong(b); return; }
  S.on.push(k); sfx.ok(); haptic("ok"); drawKiyin();
  if (w.need.every((x) => S.on.includes(x))) { S.lock = true; yay("Endi sayrga chiqsa bo'ladi!"); later(() => { S.lock = false; START.kiyin(); }, 1700); }
}

// =================================================================== 10. Kichkina pianino
const NOTES = [["Do", 523.25], ["Re", 587.33], ["Mi", 659.25], ["Fa", 698.46], ["Sol", 783.99], ["Lya", 880], ["Si", 987.77], ["Do", 1046.5]];
const KCOL = ["#FF4B3E", "#FF8A1F", "#FFC21F", "#3BB273", "#1FB5C9", "#2E86DE", "#7A5CFA", "#E5487F"];
const SONGS = [
  {n: "«Yulduzcha» kuyi", seq: [0, 0, 4, 4, 5, 5, 4, 3, 3, 2, 2, 1, 1, 0]},
  {n: "«Gamma» — pastdan yuqoriga", seq: [0, 1, 2, 3, 4, 5, 6, 7, 7, 6, 5, 4, 3, 2, 1, 0]},
];
START.pianino = () => { S.mode = S.mode || "free"; S.song = S.song || 0; S.i = 0; drawPiano(); };
function drawPiano() {
  const g = GBY.pianino, song = SONGS[S.song], next = S.mode === "song" ? song.seq[S.i] : -1;
  view(bar(g) + `<div class="g-mode"><button class="b${S.mode === "free" ? " on" : ""}" data-pmode="free">Erkin chal</button>
      <button class="b${S.mode === "song" ? " on" : ""}" data-pmode="song">Kuy o'rgan</button></div>
    ${S.mode === "song" ? `<div class="g-song"><small>${song.n} · <button data-nsong style="text-decoration:underline">boshqasi</button></small><div>
      ${song.seq.map((n, i) => `<span class="b${i < S.i ? " ok" : i === S.i ? " cur" : ""}">${NOTES[n][0]}</span>`).join("")}</div></div>` : ""}
    <div class="g-xylo">${NOTES.map(([n], i) => `<button class="g-key b${i === next ? " next" : ""}" data-key="${i}" style="width:${100 - i * 6}%;background:${KCOL[i]}" aria-label="${n} notasi">
      <i></i>${n}<i></i></button>`).join("")}</div>`);
}
function onKey(b) {
  const i = +b.dataset.key;
  tone(NOTES[i][1], 0.9, "sine", 0.3); tone(NOTES[i][1] * 2, 0.4, "sine", 0.06);
  haptic("hit"); b.classList.add("hit"); later(() => b.classList.remove("hit"), 140);
  if (S.mode !== "song") return;
  const seq = SONGS[S.song].seq;
  if (i !== seq[S.i]) return;
  S.i++;
  if (S.i >= seq.length) { later(() => { yay("Sen haqiqiy musiqachisan!", 2); S.i = 0; drawPiano(); }, 500); return; }
  drawPiano();
}

// =================================================================== 2-TO'PLAM: Anorjon bilan
const ANOR = (mood = "") => `<svg viewBox="0 0 100 105" aria-hidden="true"><path d="M38 22 L42 8 L50 17 L58 8 L62 22 Z" fill="#B3263A"/>
  <path d="M58 14 C66 4 78 8 76 14 C70 18 62 17 58 14 Z" fill="#3BB273"/><circle cx="50" cy="58" r="38" fill="#FF4D5E"/>
  <ellipse cx="33" cy="38" rx="7" ry="11" fill="#fff" opacity=".35"/>
  <circle cx="37" cy="56" r="11" fill="#fff"/><circle cx="63" cy="56" r="11" fill="#fff"/>
  <circle cx="39" cy="58" r="6.5" fill="#1D2A5B"/><circle cx="65" cy="58" r="6.5" fill="#1D2A5B"/>
  <circle cx="41" cy="55" r="2.4" fill="#fff"/><circle cx="67" cy="55" r="2.4" fill="#fff"/>
  <ellipse cx="25" cy="72" rx="6" ry="4" fill="#FF9AA8"/><ellipse cx="75" cy="72" rx="6" ry="4" fill="#FF9AA8"/>
  ${mood === "wow" ? '<ellipse cx="50" cy="78" rx="7" ry="8" fill="#7A1F2B"/>' : '<path d="M40 73 Q50 85 60 73 Z" fill="#7A1F2B"/>'}
  <ellipse cx="36" cy="98" rx="9" ry="5" fill="#B3263A"/><ellipse cx="64" cy="98" rx="9" ry="5" fill="#B3263A"/></svg>`;
const COIN = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#FFC93C" stroke="#E0A500" stroke-width="2"/><path d="M12 7v10" stroke="#E0A500" stroke-width="2" stroke-linecap="round"/></svg>';
const PUP = (sleep) => `<svg viewBox="0 0 120 124" role="img" aria-label="Kuchukcha Dumboq${sleep ? " uxlayapti" : ""}">
  <ellipse cx="60" cy="118" rx="40" ry="6" fill="rgba(0,0,0,.12)"/>
  <path d="M86 92 Q108 84 104 66" fill="none" stroke="#E8B07A" stroke-width="8" stroke-linecap="round" class="g-tail"/>
  <ellipse cx="60" cy="92" rx="30" ry="24" fill="#E8B07A"/><ellipse cx="60" cy="98" rx="16" ry="14" fill="#FFF1DE"/>
  <ellipse cx="42" cy="114" rx="9" ry="6" fill="#E8B07A"/><ellipse cx="78" cy="114" rx="9" ry="6" fill="#E8B07A"/>
  <path d="M22 26 C6 32 10 64 26 62 L32 32 Z" fill="#7E5432"/><path d="M98 26 C114 32 110 64 94 62 L88 32 Z" fill="#7E5432"/>
  <circle cx="60" cy="46" r="34" fill="#E8B07A"/><ellipse cx="60" cy="60" rx="18" ry="13" fill="#FFF1DE"/>
  ${sleep ? '<path d="M40 41 Q46 46 52 41 M68 41 Q74 46 80 41" fill="none" stroke="#1D2A5B" stroke-width="3" stroke-linecap="round"/>'
    : '<circle cx="46" cy="40" r="7" fill="#1D2A5B"/><circle cx="74" cy="40" r="7" fill="#1D2A5B"/><circle cx="48.5" cy="37.5" r="2.5" fill="#fff"/><circle cx="76.5" cy="37.5" r="2.5" fill="#fff"/>'}
  <ellipse cx="60" cy="53" rx="7" ry="5" fill="#1D2A5B"/>
  ${sleep ? "" : '<path d="M53 62 Q60 68 67 62" fill="none" stroke="#1D2A5B" stroke-width="2.5" stroke-linecap="round"/><path d="M57 64 Q60 74 63 64 Z" fill="#FF6B8A"/>'}
  <ellipse cx="34" cy="54" rx="5" ry="3" fill="#FF9AA8"/><ellipse cx="86" cy="54" rx="5" ry="3" fill="#FF9AA8"/>
  <path d="M40 78 Q60 86 80 78 L80 84 Q60 92 40 84 Z" fill="#FF4D5E"/><circle cx="60" cy="88" r="4" fill="#FFC93C"/></svg>`;

const GAMES2 = [
  {id: "kuchuk", n: "Mening kuchukcham", age: "Har kuni bog'la", bg: "#FFD6E5", c1: "#FFD6E5", c2: "#E5487F", edge: "#E59BB8", ic: PUP(false), v2: 1},
  {id: "mushuk", n: "Sakrovchi mushuk", age: "4–9 yosh", bg: "#FFB347", c1: "#FFE3C2", c2: "#C97500", edge: "#C97500", v2: 1,
    ic: '<svg viewBox="0 0 60 60" aria-hidden="true"><path d="M14 22 L18 4 L30 16 Z M46 22 L42 4 L30 16 Z" fill="#FF9F1C"/><circle cx="30" cy="32" r="22" fill="#FF9F1C"/><circle cx="23" cy="29" r="4" fill="#1D2A5B"/><circle cx="37" cy="29" r="4" fill="#1D2A5B"/><path d="M26 38 Q30 42 34 38" fill="none" stroke="#1D2A5B" stroke-width="2.5" stroke-linecap="round"/></svg>'},
  {id: "savat", n: "Mevalarni ushla", age: "3–8 yosh", bg: "#8EE4AF", c1: "#D9F2E3", c2: "#2A8A55", edge: "#2A8A55", v2: 1,
    ic: '<svg viewBox="0 0 60 60" aria-hidden="true"><path d="M6 30 H54 L48 54 H12 Z" fill="#C9813E"/><circle cx="20" cy="24" r="9" fill="#FF4B3E"/><circle cx="34" cy="20" r="9" fill="#FFC21F"/><circle cx="44" cy="26" r="8" fill="#7A5CFA"/></svg>'},
  {id: "qushcha", n: "Qushchani uchir", age: "5–10 yosh", bg: "#6FD3F7", c1: "#D6F3FF", c2: "#0E8FB0", edge: "#2B9FCC", v2: 1,
    ic: '<svg viewBox="0 0 60 60" aria-hidden="true"><ellipse cx="28" cy="32" rx="22" ry="19" fill="#FFE14D"/><path d="M12 32 Q2 20 14 18 Q20 26 18 34 Z" fill="#FFB020"/><circle cx="38" cy="26" r="7" fill="#fff"/><circle cx="40" cy="27" r="4" fill="#1D2A5B"/><path d="M46 32 L58 35 L46 39 Z" fill="#FF8A1F"/></svg>'},
  {id: "poyga", n: "Avtomobil poygasi", age: "4–10 yosh", bg: "#5BC06A", c1: "#D9F2E3", c2: "#2E9E60", edge: "#2E9E60", v2: 1,
    ic: '<svg viewBox="0 0 60 60" aria-hidden="true"><rect x="16" y="4" width="28" height="52" rx="9" fill="#FF4D5E"/><rect x="20" y="14" width="20" height="13" rx="4" fill="#BFE6FF"/><rect x="20" y="36" width="20" height="10" rx="3" fill="#BFE6FF"/><rect x="12" y="10" width="5" height="12" rx="2" fill="#1D2A5B"/><rect x="43" y="10" width="5" height="12" rx="2" fill="#1D2A5B"/><rect x="12" y="38" width="5" height="12" rx="2" fill="#1D2A5B"/><rect x="43" y="38" width="5" height="12" rx="2" fill="#1D2A5B"/></svg>'},
  {id: "tort", n: "Tort yasash", age: "3–8 yosh", bg: "#FFE1F0", c1: "#FFE1F0", c2: "#D13F86", edge: "#F2A9C6", v2: 1,
    ic: '<svg viewBox="0 0 60 60" aria-hidden="true"><rect x="10" y="34" width="40" height="18" rx="5" fill="#B5651D"/><rect x="10" y="32" width="40" height="7" rx="3.5" fill="#FF8FC1"/><rect x="16" y="20" width="28" height="14" rx="4" fill="#FFF1DE"/><rect x="16" y="18" width="28" height="6" rx="3" fill="#FF8FC1"/><rect x="28" y="6" width="4" height="12" rx="2" fill="#23C4E8"/><path d="M30 0 q4 4 0 7 q-4 -3 0 -7Z" fill="#FFB020"/></svg>'},
  {id: "puzzle", n: "Puzzle", age: "4–9 yosh", bg: "#2E86DE", c1: "#D6EEFF", c2: "#1C62A8", edge: "#1C62A8", v2: 1,
    ic: '<svg viewBox="0 0 60 60" aria-hidden="true"><rect x="6" y="6" width="22" height="22" rx="4" fill="#FF4D5E"/><rect x="32" y="6" width="22" height="22" rx="4" fill="#FFC93C"/><rect x="6" y="32" width="22" height="22" rx="4" fill="#3BB273"/><rect x="34" y="34" width="22" height="22" rx="4" fill="#2E86DE" transform="rotate(12 45 45)"/></svg>'},
  {id: "farq", n: "Farqini top", age: "5–10 yosh", bg: "#FF4D5E", c1: "#FFD6D9", c2: "#B3263A", edge: "#B3263A", v2: 1,
    ic: '<svg viewBox="0 0 60 60" aria-hidden="true"><circle cx="26" cy="26" r="16" fill="none" stroke="#1D2A5B" stroke-width="5"/><path d="M38 38 L52 52" stroke="#1D2A5B" stroke-width="6" stroke-linecap="round"/><circle cx="26" cy="26" r="9" fill="#FFC93C"/></svg>'},
  {id: "osh", n: "Osh pishir", age: "4–9 yosh", bg: "#FFE3C2", c1: "#FFE3C2", c2: "#B35C10", edge: "#E3A86B", v2: 1,
    ic: '<svg viewBox="0 0 60 60" aria-hidden="true"><path d="M8 24 H52 Q50 52 30 52 Q10 52 8 24 Z" fill="#3A3F52"/><ellipse cx="30" cy="24" rx="23" ry="6" fill="#C97B3A"/><g fill="#FF8A1F"><rect x="18" y="20" width="6" height="4" rx="2"/><rect x="32" y="22" width="6" height="4" rx="2"/></g><path d="M22 14 q-4 -6 0 -10 M32 14 q-4 -6 0 -10" fill="none" stroke="#9AA3B8" stroke-width="3" stroke-linecap="round"/></svg>'},
  {id: "soya", n: "Soya o'yini", age: "2–6 yosh", bg: "#1D2A5B", c1: "#E3E6F5", c2: "#0B1238", edge: "#0B1238", v2: 1,
    ic: '<svg viewBox="0 0 160 130" aria-hidden="true"><g fill="#1D2A5B"><ellipse cx="80" cy="74" rx="52" ry="36"/><circle cx="118" cy="56" r="26"/><path d="M136 62 Q152 80 142 108 Q138 114 134 108 Q142 86 128 72 Z"/><rect x="40" y="96" width="18" height="30" rx="7"/><rect x="92" y="98" width="18" height="28" rx="7"/></g></svg>'},
];
GAMES.push(...GAMES2);
GAMES2.forEach((g) => { GBY[g.id] = g; });

const today = () => new Date().toISOString().slice(0, 10);
function speech(text, mood) {
  return `<div class="g-say"><span class="av">${ANOR(mood)}</span><b class="b">${text}</b></div>`;
}

// ------------------------------------------------------------------ Arkada dvigateli (canvas)
function arcade(cfg) {
  const box = $("gcan"); if (!box) return;
  const cv = document.createElement("canvas"), dpr = Math.min(2, window.devicePixelRatio || 1);
  const W = box.clientWidth, H = box.clientHeight;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px";
  box.appendChild(cv);
  const c = cv.getContext("2d"); c.scale(dpr, dpr);
  const rec = lsGet("zk_grec", {});
  const g = {W, H, t: 0, over: false, ready: true, score: 0, best: rec[cfg.id] || 0};
  S.ag = g;
  const restart = () => { Object.assign(g, {t: 0, over: false, ready: true, score: 0}); cfg.init(g); $("gover").hidden = true; };
  const finish = (good) => {
    if (g.over) return;
    g.over = true; if (good) { sfx.win(); haptic("ok"); } else { sfx.err(); haptic("err"); }
    const sc = Math.floor(g.score), newBest = sc > g.best;
    if (newBest) { g.best = sc; rec[cfg.id] = sc; lsSet("zk_grec", rec); }
    const st = cfg.stars(sc);
    if (st) addStar(st);
    later(() => {
      const o = $("gover"); if (!o) return;
      o.innerHTML = `<div class="box2">${newBest && sc ? `<div class="nb b">Yangi rekord!</div>` : ""}
        <div class="sc b">${sc}${cfg.unit || ""}</div><div class="bs">Eng yaxshisi: ${g.best}${cfg.unit || ""}${st ? ` · +${st} ★` : ""}</div>
        <button class="gx-btn b" data-again>Yana o'ynash</button></div>`;
      o.hidden = false;
    }, 450);
  };
  g.finish = finish;
  cfg.init(g);
  let last = performance.now();
  const loop = (now) => {
    const dt = Math.min(0.033, (now - last) / 1000); last = now;
    if (!g.over && !g.ready) { g.t += dt; cfg.step(g, dt); }
    else if (g.ready && cfg.idle) cfg.idle(g, dt);
    cfg.draw(g, c);
    S.raf = requestAnimationFrame(loop);
  };
  S.raf = requestAnimationFrame(loop);
  const pos = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener("pointerdown", (e) => {
    e.preventDefault(); ctx();
    if (g.over) return;
    if (g.ready) { g.ready = false; $("ghint") && ($("ghint").style.opacity = "0"); }
    const [x, y] = pos(e); g.down = true; g.sx = x; g.sy = y; g.downAt = performance.now(); cfg.tap && cfg.tap(g, x, y); cfg.drag && cfg.drag(g, x, y);
  });
  cv.addEventListener("pointermove", (e) => { if (cfg.drag && (g.down || e.pointerType === "mouse")) { const [x, y] = pos(e); cfg.drag(g, x, y); } });
  ["pointerup", "pointercancel", "pointerleave"].forEach((ev) => cv.addEventListener(ev, (e) => {
    if (!g.down) return;
    g.down = false; if (cfg.release && !g.over && !g.ready) { const [x, y] = pos(e); cfg.release(g, x, y); } }));
  S.again = restart;
}
const rr = (c, x, y, w, h, r) => { c.beginPath(); c.roundRect ? c.roundRect(x, y, w, h, r) : c.rect(x, y, w, h); c.fill(); };
const circ = (c, x, y, r, col) => { c.fillStyle = col; c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); };
function arcadeView(g, hud, hint, h = 0) {
  view(bar(g, hud) + `<div class="g-can" id="gcan" ${h ? `style="flex:none;height:${h}px"` : ""}>
    <div class="g-hint b" id="ghint">${hint}</div><div class="g-over" id="gover" hidden></div></div>`);
}
const hit = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

// ------------------------------------------------------------------ 1. Mening kuchukcham (tamagochi)
const NEEDS = [["food", "Ovqat", "#FF4D5E"], ["sleep", "Uyqu", "#7A5CFA"], ["play", "O'yin", "#3BB273"], ["clean", "Tozalik", "#23C4E8"]];
const DECAY = {food: 7, sleep: 5, play: 6, clean: 4};       // soatiga kamayish
function petLoad() {
  const now = Date.now();
  const p = lsGet("zk_gpet", null) || {food: 55, sleep: 75, play: 45, clean: 80, ts: now, born: now, asleep: false, day: "", got: 0};
  const h = Math.min(48, (now - p.ts) / 3600000);
  for (const k of Object.keys(DECAY)) {
    if (k === "sleep" && p.asleep) p.sleep = Math.min(100, p.sleep + h * 25);
    else p[k] = Math.max(0, p[k] - h * DECAY[k]);
  }
  if (p.asleep && p.sleep >= 100) p.asleep = false;
  p.ts = now;
  if (p.day !== today()) { p.day = today(); p.got = 0; }
  return p;
}
const petSave = (p) => lsSet("zk_gpet", p);
function petMood(p) {
  if (p.asleep) return "Xrr... Xrr... (uxlayapti)";
  const low = NEEDS.map(([k]) => [k, p[k]]).sort((a, b) => a[1] - b[1])[0];
  if (low[1] >= 70) return ["Seni juda yaxshi ko'raman!", "Bugun ajoyib kun!", "Men baxtliman!"][rnd(3)];
  return {food: "Qornim och! Suyakcha bera olasanmi?", sleep: "Uyqum keldi...", play: "Zerikdim, keling o'ynaymiz!", clean: "Cho'milgim kelyapti!"}[low[0]];
}
START.kuchuk = () => { S.pet = petLoad(); petSave(S.pet); drawPet(); S.tick = setInterval(() => { if (cur === "kuchuk") { S.pet = petLoad(); petSave(S.pet); drawPet(true); } }, 15000); };
function drawPet(soft) {
  const g = GBY.kuchuk, p = S.pet, days = Math.max(1, Math.ceil((Date.now() - p.born) / 86400000));
  const html = bar(g, starsHTML()) + `<div class="g-room${p.asleep ? " night" : ""}">
    <div class="g-needs">${NEEDS.map(([k, l, c]) => `<div><span>${l}</span><i><em style="width:${Math.round(p[k])}%;background:${c}"></em></i></div>`).join("")}</div>
    <div class="g-petbox"><div class="g-bub b">${petMood(p)}</div><div class="g-pet" id="gpet">${PUP(p.asleep)}</div><div class="g-fx" id="gfx"></div></div>
    <div class="g-days">Dumboq bilan ${days}-kun</div></div>
    <div class="g-acts">${[["food", "Ovqat", "#FF4D5E", "#B3263A", "M6 18 a5 5 0 1 1 6 -6 L28 28 a5 5 0 1 1 -6 6 a5 5 0 1 1 -6 -6 Z"],
      ["clean", "Cho'mil", "#23C4E8", "#0E8FB0", "M20 4 C26 14 32 20 32 26 a12 12 0 0 1 -24 0 C8 20 14 14 20 4 Z"],
      ["play", "O'yna", "#3BB273", "#2A8A55", "M20 4 a16 16 0 1 0 0.1 0 Z"],
      ["sleep", p.asleep ? "Uyg'ot" : "Uxla", "#7A5CFA", "#5536D6", "M26 4 A16 16 0 1 0 36 26 A12 12 0 1 1 26 4 Z"]]
      .map(([k, l, c1, c2, d]) => `<button class="gx-big b" data-pet="${k}" style="--c1:${c1};--c2:${c2}" aria-label="${l}"${p.asleep && k !== "sleep" ? " disabled" : ""}>
        <svg viewBox="0 0 40 40" aria-hidden="true"><path d="${d}" fill="#fff"/></svg><span>${l}</span></button>`).join("")}</div>`;
  if (soft && $("gpet")) { const b = document.querySelector(".g-bub"); if (b) b.textContent = petMood(p);
    document.querySelectorAll(".g-needs em").forEach((e, i) => { e.style.width = Math.round(p[NEEDS[i][0]]) + "%"; }); return; }
  view(html);
}
function onPet(k) {
  const p = S.pet = petLoad();
  const fx = (sym) => { const f = $("gfx"); if (!f) return; f.innerHTML = sym; f.classList.remove("on"); void f.offsetWidth; f.classList.add("on"); };
  if (k === "sleep") { p.asleep = !p.asleep; petSave(p); sfx.tap(); drawPet(); return; }
  if (p.asleep) return;
  const before = p[k];
  if (k === "food") { p.food = Math.min(100, p.food + 30); fx('<svg viewBox="0 0 40 40"><path d="M6 18 a5 5 0 1 1 6 -6 L28 28 a5 5 0 1 1 -6 6 a5 5 0 1 1 -6 -6 Z" fill="#fff" stroke="#E2DCCF" stroke-width="2"/></svg>');
    [300, 360, 300].forEach((f, i) => tone(f, 0.08, "square", 0.06, i * 0.12)); }
  if (k === "clean") { p.clean = Math.min(100, p.clean + 40); fx('<svg viewBox="0 0 60 40"><circle cx="12" cy="20" r="9" fill="#BFE6FF"/><circle cx="32" cy="12" r="7" fill="#BFE6FF"/><circle cx="48" cy="24" r="10" fill="#BFE6FF"/></svg>');
    [800, 1000, 1200].forEach((f, i) => tone(f, 0.08, "sine", 0.1, i * 0.07)); }
  if (k === "play") { p.play = Math.min(100, p.play + 30); p.food = Math.max(0, p.food - 6); p.clean = Math.max(0, p.clean - 5);
    fx('<svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="16" fill="#FF4D5E"/><path d="M6 14 Q20 24 34 14 M6 26 Q20 16 34 26" stroke="#fff" stroke-width="3" fill="none"/></svg>');
    CALL.kuchuk(ctx()); }
  haptic("ok");
  const pe = $("gpet"); if (pe) { pe.classList.remove("hop"); void pe.offsetWidth; pe.classList.add("hop"); }
  if (before < 70 && p.got < 8) { p.got++; addStar(1); }
  petSave(p); drawPet(true);
  if (NEEDS.every(([n]) => p[n] >= 90) && before < 90) later(() => yay("Dumboq juda baxtli!"), 400);
}

// ------------------------------------------------------------------ 2. Sakrovchi mushukcha (runner)
START.mushuk = () => {
  arcadeView(GBY.mushuk, `<div class="gx-pill b" id="gsc">0 m</div>`, "Ekranni bos — sakra!<br><small>Ikki marta bossang — baland sakraydi</small>");
  arcade({id: "mushuk", unit: " m", stars: (s) => (s >= 400 ? 3 : s >= 200 ? 2 : s >= 60 ? 1 : 0),
    init(g) { g.gy = g.H - 96; Object.assign(g, {cat: {x: 60, y: g.gy - 52, w: 56, h: 52, vy: 0, j: 0}, obs: [], fish: [], sp: 250, next: 1.4, nf: 0.8, fishN: 0, hill: 0}); },
    tap(g) { const k = g.cat; if (k.j < 2) { k.vy = k.j ? -700 : -800; k.j++; tone(k.j === 1 ? 520 : 700, 0.12, "triangle", 0.15, 0, 900); } },
    step(g, dt) {
      const k = g.cat; g.sp = Math.min(560, g.sp + dt * 9); g.score += dt * g.sp / 40; g.hill += dt * g.sp * 0.25;
      k.vy += 2300 * dt; k.y += k.vy * dt; if (k.y >= g.gy - k.h) { k.y = g.gy - k.h; k.vy = 0; k.j = 0; }
      g.next -= dt; if (g.next <= 0) { const big = Math.random() < 0.35; g.obs.push({x: g.W + 20, y: g.gy - (big ? 64 : 44), w: big ? 40 : 44, h: big ? 64 : 44, big}); g.next = 0.9 + Math.random() * 1.1 - Math.min(0.35, g.t / 120); }
      g.nf -= dt; if (g.nf <= 0) { const y0 = g.gy - 90 - rnd(120); for (let i = 0; i < 3; i++) g.fish.push({x: g.W + 20 + i * 34, y: y0 - Math.sin(i / 2 * Math.PI) * 30, w: 28, h: 18}); g.nf = 2.2 + Math.random() * 1.5; }
      g.obs.forEach((o) => { o.x -= g.sp * dt; }); g.fish.forEach((f) => { f.x -= g.sp * dt; });
      g.obs = g.obs.filter((o) => o.x > -60); g.fish = g.fish.filter((f) => f.x > -40 && !f.got);
      const box = {x: k.x + 8, y: k.y + 8, w: k.w - 16, h: k.h - 10};
      if (g.obs.some((o) => hit(box, {x: o.x + 4, y: o.y + 4, w: o.w - 8, h: o.h - 4}))) g.finish();
      g.fish.forEach((f) => { if (!f.got && hit(box, f)) { f.got = true; g.fishN++; g.score += 5; tone(1200, 0.06, "sine", 0.12); } });
      const s = $("gsc"); if (s) s.textContent = `${Math.floor(g.score)} m`;
    },
    draw(g, c) {
      const {W, H} = g;
      c.fillStyle = "#FFB347"; c.fillRect(0, 0, W, H); circ(c, W - 80, 90, 50, "#FFE66D");
      c.fillStyle = "#FF8C42"; c.beginPath(); c.moveTo(0, g.gy); for (let x = 0; x <= W; x += 20) c.lineTo(x, g.gy - 70 - Math.sin((x + g.hill * 0.5) / 70) * 30); c.lineTo(W, g.gy); c.fill();
      c.fillStyle = "#5BC06A"; c.fillRect(0, g.gy, W, H - g.gy); c.fillStyle = "#3E9E4E"; c.fillRect(0, g.gy, W, 12);
      g.obs.forEach((o) => { c.fillStyle = o.big ? "#2E9E60" : "#B5651D"; rr(c, o.x, o.y, o.w, o.h, 8);
        if (!o.big) { c.strokeStyle = "#8A4A12"; c.lineWidth = 4; c.beginPath(); c.moveTo(o.x + 6, o.y + 6); c.lineTo(o.x + o.w - 6, o.y + o.h - 6); c.moveTo(o.x + o.w - 6, o.y + 6); c.lineTo(o.x + 6, o.y + o.h - 6); c.stroke(); } });
      g.fish.forEach((f) => { c.fillStyle = "#23C4E8"; c.beginPath(); c.ellipse(f.x + 11, f.y + 9, 11, 8, 0, 0, 7); c.fill(); c.beginPath(); c.moveTo(f.x + 20, f.y + 9); c.lineTo(f.x + 28, f.y + 2); c.lineTo(f.x + 28, f.y + 16); c.fill(); });
      const k = g.cat, bob = k.j ? 0 : Math.sin(g.t * 18) * 2;
      c.save(); c.translate(k.x, k.y + bob);
      c.fillStyle = "#FF9F1C"; c.beginPath(); c.ellipse(26, 36, 24, 15, 0, 0, 7); c.fill();
      c.strokeStyle = "#FF9F1C"; c.lineWidth = 7; c.lineCap = "round"; c.beginPath(); c.moveTo(4, 32); c.quadraticCurveTo(-10, 18, 0, 8); c.stroke();
      c.beginPath(); c.moveTo(34, 10); c.lineTo(38, -6); c.lineTo(46, 6); c.moveTo(56, 10); c.lineTo(54, -6); c.lineTo(46, 4); c.fill();
      circ(c, 46, 18, 16, "#FF9F1C"); circ(c, 41, 16, 3.6, "#1D2A5B"); circ(c, 52, 16, 3.6, "#1D2A5B"); circ(c, 42, 15, 1.2, "#fff"); circ(c, 53, 15, 1.2, "#fff");
      c.fillStyle = "#FF6B8A"; c.beginPath(); c.moveTo(45, 22); c.lineTo(49, 22); c.lineTo(47, 25); c.fill();
      c.restore();
      c.fillStyle = "rgba(29,42,91,.85)"; rr(c, 12, 12, 86, 32, 16); c.fillStyle = "#fff"; c.font = "800 16px Bal, sans-serif"; c.fillText(`Baliq: ${g.fishN}`, 24, 34);
    },
  });
};

// ------------------------------------------------------------------ 3. Mevalarni ushla
const FRUITS = [["#FF4B3E", 18], ["#FFC21F", 17], ["#7A5CFA", 16], ["#7ED957", 17], ["#FF8A1F", 18]];
START.savat = () => {
  arcadeView(GBY.savat, `<div class="gx-pill b" id="gsc">0</div>`, "Savatni barmoq bilan sur<br><small>Toshni ushlama!</small>");
  arcade({id: "savat", stars: (s) => (s >= 60 ? 3 : s >= 30 ? 2 : s >= 10 ? 1 : 0),
    init(g) { Object.assign(g, {bx: g.W / 2, items: [], lives: 3, next: 0.5, fall: 170}); },
    drag(g, x) { g.bx = Math.max(55, Math.min(g.W - 55, x)); },
    step(g, dt) {
      g.fall = Math.min(430, g.fall + dt * 6);
      g.next -= dt; if (g.next <= 0) { const rock = Math.random() < Math.min(0.28, 0.1 + g.t / 300); const f = FRUITS[rnd(FRUITS.length)];
        g.items.push({x: 24 + Math.random() * (g.W - 48), y: -30, r: rock ? 18 : f[1], col: rock ? "#8A8F9C" : f[0], rock, rot: Math.random() * 6}); g.next = Math.max(0.35, 0.9 - g.t / 90); }
      const by = g.H - 70;
      g.items.forEach((it) => { it.y += g.fall * dt; it.rot += dt * 2;
        if (!it.done && it.y + it.r > by && it.y < by + 26 && Math.abs(it.x - g.bx) < 60) { it.done = true;
          if (it.rock) { g.lives--; sfx.err(); haptic("err"); if (g.lives <= 0) g.finish(); } else { g.score++; tone(700 + rnd(300), 0.08, "triangle", 0.15); haptic("hit"); } } });
      g.items = g.items.filter((it) => !it.done && it.y < g.H + 40);
      const s = $("gsc"); if (s) s.textContent = g.score;
    },
    draw(g, c) {
      const {W, H} = g;
      c.fillStyle = "#8EE4AF"; c.fillRect(0, 0, W, H); c.fillStyle = "#3BB273"; c.beginPath(); c.moveTo(0, 0); c.lineTo(W, 0);
      for (let x = W; x >= 0; x -= 40) c.lineTo(x, 50 + Math.sin(x / 30) * 14); c.fill();
      c.fillStyle = "#F4B26B"; c.fillRect(0, H - 40, W, 40);
      g.items.forEach((it) => { c.save(); c.translate(it.x, it.y); c.rotate(it.rock ? 0 : Math.sin(it.rot) * 0.3);
        circ(c, 0, 0, it.r, it.col);
        if (!it.rock) { circ(c, -it.r * 0.35, -it.r * 0.35, it.r * 0.25, "rgba(255,255,255,.45)"); c.fillStyle = "#3BB273"; c.beginPath(); c.ellipse(5, -it.r - 2, 7, 3.5, -0.5, 0, 7); c.fill(); }
        else { circ(c, -5, -6, 5, "#B4B9C4"); }
        c.restore(); });
      const by = H - 70; c.fillStyle = "#C9813E"; c.beginPath(); c.moveTo(g.bx - 58, by); c.lineTo(g.bx + 58, by); c.lineTo(g.bx + 46, by + 44); c.lineTo(g.bx - 46, by + 44); c.fill();
      c.fillStyle = "#A8662A"; rr(c, g.bx - 62, by - 6, 124, 12, 6);
      for (let i = 0; i < 3; i++) { c.fillStyle = i < g.lives ? "#FF4D5E" : "rgba(29,42,91,.25)"; c.beginPath(); const x = 22 + i * 30, y = 24;
        c.moveTo(x, y + 8); c.bezierCurveTo(x - 14, y - 4, x - 6, y - 14, x, y - 5); c.bezierCurveTo(x + 6, y - 14, x + 14, y - 4, x, y + 8); c.fill(); }
    },
  });
};

// ------------------------------------------------------------------ 4. Qushchani uchir
START.qushcha = () => {
  arcadeView(GBY.qushcha, `<div class="gx-pill b" id="gsc">0</div>`, "Bos — qushcha yuqoriga uchadi");
  arcade({id: "qushcha", stars: (s) => (s >= 20 ? 3 : s >= 10 ? 2 : s >= 3 ? 1 : 0),
    init(g) { Object.assign(g, {b: {x: 90, y: g.H / 2, vy: 0}, pipes: [], next: 1.2, gap: 200}); },
    idle(g) { g.b.y = g.H / 2 + Math.sin(performance.now() / 300) * 10; },
    tap(g) { g.b.vy = -430; tone(640, 0.08, "triangle", 0.12, 0, 900); },
    step(g, dt) {
      const b = g.b; b.vy += 1350 * dt; b.y += b.vy * dt; if (b.y < 20) { b.y = 20; b.vy = 0; }
      if (b.y > g.H - 70) g.finish();
      g.next -= dt; if (g.next <= 0) { const gap = Math.max(160, g.gap - g.score * 2); const top = 60 + Math.random() * (g.H - 200 - gap); g.pipes.push({x: g.W + 10, top, gap, w: 70}); g.next = 1.65; }
      g.pipes.forEach((p) => { p.x -= 150 * dt; if (!p.pass && p.x + p.w < b.x) { p.pass = true; g.score++; sfx.tap(); } });
      g.pipes = g.pipes.filter((p) => p.x > -80);
      const bb = {x: b.x - 18, y: b.y - 16, w: 36, h: 32};
      if (g.pipes.some((p) => hit(bb, {x: p.x, y: 0, w: p.w, h: p.top}) || hit(bb, {x: p.x, y: p.top + p.gap, w: p.w, h: g.H}))) g.finish();
      const s = $("gsc"); if (s) s.textContent = g.score;
    },
    draw(g, c) {
      const {W, H} = g;
      c.fillStyle = "#6FD3F7"; c.fillRect(0, 0, W, H);
      c.fillStyle = "#fff"; [[60, 90], [260, 180], [150, 300]].forEach(([x, y]) => { c.beginPath(); c.ellipse((x - g.t * 20) % (W + 120) + 60, y, 40, 15, 0, 0, 7); c.fill(); });
      g.pipes.forEach((p) => { c.fillStyle = "#3BB273"; rr(c, p.x, -20, p.w, p.top + 20, 14); rr(c, p.x, p.top + p.gap, p.w, H, 14);
        c.fillStyle = "#2E9E60"; rr(c, p.x - 8, p.top - 30, p.w + 16, 30, 12); rr(c, p.x - 8, p.top + p.gap, p.w + 16, 30, 12); });
      c.fillStyle = "#5BC06A"; c.fillRect(0, H - 54, W, 54);
      const b = g.b; c.save(); c.translate(b.x, b.y); c.rotate(Math.max(-0.5, Math.min(0.9, b.vy / 600)));
      c.fillStyle = "#FFE14D"; c.beginPath(); c.ellipse(0, 0, 22, 19, 0, 0, 7); c.fill();
      c.fillStyle = "#FFB020"; c.beginPath(); c.ellipse(-8, 3 + Math.sin(g.t * 30) * 4, 11, 7, -0.4, 0, 7); c.fill();
      circ(c, 9, -6, 7, "#fff"); circ(c, 11, -5, 4, "#1D2A5B");
      c.fillStyle = "#FF8A1F"; c.beginPath(); c.moveTo(18, 0); c.lineTo(30, 3); c.lineTo(18, 8); c.fill(); c.restore();
      if (!g.ready && !g.over) { c.fillStyle = "#fff"; c.font = "800 64px Bal, sans-serif"; c.textAlign = "center"; c.fillText(g.score, W / 2, 90); c.textAlign = "start"; }
    },
  });
};

// ------------------------------------------------------------------ 5. Avtomobil poygasi
START.poyga = () => {
  arcadeView(GBY.poyga, `<div class="gx-pill b" id="gsc">0</div>`, "Chapga yoki o'ngga bos<br><small>Tangalarni yig', mashinalarga urilma</small>");
  arcade({id: "poyga", stars: (s) => (s >= 80 ? 3 : s >= 40 ? 2 : s >= 12 ? 1 : 0),
    init(g) { const rw = Math.min(g.W - 40, 270); Object.assign(g, {rx: (g.W - rw) / 2, rw, lane: 1, carX: 0, objs: [], sp: 260, next: 0.8, off: 0, coins: 0}); g.carX = g.rx + rw / 6; },
    tap(g, x) { g.lane = Math.max(0, Math.min(2, g.lane + (x < g.W / 2 ? -1 : 1))); tone(500, 0.05, "sine", 0.1); },
    step(g, dt) {
      g.sp = Math.min(620, g.sp + dt * 10); g.off = (g.off + g.sp * dt) % 80; g.score += dt * 2;
      const lw = g.rw / 3, target = g.rx + lw * g.lane + lw / 2; g.carX += (target - g.carX) * Math.min(1, dt * 14);
      g.next -= dt; if (g.next <= 0) { const l = rnd(3), coin = Math.random() < 0.45;
        g.objs.push({l, y: -100, coin, col: ["#2E86DE", "#FF9F1C", "#7A5CFA", "#3BB273"][rnd(4)]}); if (coin && Math.random() < 0.5) g.objs.push({l, y: -170, coin: true}); g.next = Math.max(0.45, 1.1 - g.t / 100); }
      const cy = g.H - 150;
      g.objs.forEach((o) => { o.y += g.sp * dt * (o.coin ? 1 : 0.75);
        const ox = g.rx + lw * o.l + lw / 2;
        if (!o.done && Math.abs(ox - g.carX) < lw * 0.6 && o.y + (o.coin ? 14 : 90) > cy + 10 && o.y < cy + 96) {
          if (o.coin) { o.done = true; g.coins++; g.score += 3; tone(1100, 0.07, "triangle", 0.14); } else g.finish(); } });
      g.objs = g.objs.filter((o) => !o.done && o.y < g.H + 120);
      const s = $("gsc"); if (s) s.textContent = Math.floor(g.score);
    },
    draw(g, c) {
      const {W, H} = g;
      c.fillStyle = "#5BC06A"; c.fillRect(0, 0, W, H);
      c.fillStyle = "#4A4F63"; c.fillRect(g.rx, 0, g.rw, H); c.fillStyle = "#fff"; c.fillRect(g.rx - 6, 0, 6, H); c.fillRect(g.rx + g.rw, 0, 6, H);
      const lw = g.rw / 3; c.fillStyle = "#FFE66D";
      for (let i = 1; i < 3; i++) for (let y = -80 + g.off; y < H; y += 80) rr(c, g.rx + lw * i - 3, y, 6, 44, 3);
      const car = (x, y, col, me) => { c.fillStyle = "#1D2A5B"; [[-30, 14], [24, 14], [-30, 62], [24, 62]].forEach(([dx, dy]) => rr(c, x + dx, y + dy, 7, 20, 3));
        c.fillStyle = col; rr(c, x - 26, y, 52, 96, 16); c.fillStyle = "#BFE6FF"; rr(c, x - 18, y + (me ? 20 : 56), 36, 22, 6); rr(c, x - 18, y + (me ? 60 : 20), 36, 16, 5); };
      g.objs.forEach((o) => { const ox = g.rx + lw * o.l + lw / 2;
        if (o.coin) { circ(c, ox, o.y, 14, "#FFC93C"); c.strokeStyle = "#E0A500"; c.lineWidth = 3; c.beginPath(); c.arc(ox, o.y, 14, 0, 7); c.stroke(); }
        else car(ox, o.y, o.col, false); });
      car(g.carX, H - 150, "#FF4D5E", true);
      c.fillStyle = "rgba(29,42,91,.85)"; rr(c, 12, 12, 92, 32, 16); c.fillStyle = "#fff"; c.font = "800 16px Bal, sans-serif"; c.fillText(`Tanga: ${g.coins}`, 24, 34);
    },
  });
};

// ------------------------------------------------------------------ 6. Tort yasash
const LAYER = [["Shokolad", "#B5651D"], ["Vanil", "#FFF1DE"], ["Qulupnay", "#FF8FC1"], ["Yalpiz", "#9FE8C4"], ["Limon", "#FFE66D"]];
const KREM = [["Pushti", "#FF8FC1"], ["Oq", "#FFFFFF"], ["Shokolad", "#7E4A1E"], ["Ko'k", "#9BD7FF"], ["Binafsha", "#C7B6FF"]];
const BEZAK = [["Qulupnay", "q"], ["Sepma", "s"], ["Konfet", "k"], ["Yulduzcha", "y"]];
START.tort = () => { S.cake = {layers: [], krem: null, bezak: [], sham: 0}; S.step = 0; drawTort(); };
function cakeSVG() {
  const k = S.cake, n = k.layers.length, out = [];
  const plateY = 330; let y = plateY;
  out.push(`<ellipse cx="160" cy="${plateY + 8}" rx="140" ry="20" fill="#fff"/><ellipse cx="160" cy="${plateY + 2}" rx="140" ry="20" fill="#F5F0FF"/>`);
  const tops = [];
  k.layers.forEach((col, i) => { const w = 220 - i * 46, h = 62, x = 160 - w / 2; y -= h;
    out.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="16" fill="${col}" stroke="rgba(0,0,0,.08)" stroke-width="2"/>`);
    if (k.krem) out.push(`<path d="M${x} ${y + 14} ${Array.from({length: 8}, (_, j) => `Q${x + w / 16 * (2 * j + 1)} ${y + 32} ${x + w / 8 * (j + 1)} ${y + 14}`).join(" ")} V${y + 4} H${x} Z" fill="${k.krem}"/><rect x="${x}" y="${y - 3}" width="${w}" height="18" rx="9" fill="${k.krem}"/>`);
    tops.push([x, y, w]); });
  if (!n) out.push(`<text x="160" y="250" text-anchor="middle" font-family="Bal, sans-serif" font-size="20" font-weight="800" fill="#D13F86">Birinchi qavatni tanla</text>`);
  const t = tops[tops.length - 1];
  if (t) {
    const [x, ty, w] = t;
    k.bezak.forEach((b) => {
      for (let i = 0; i < 4; i++) { const cx = x + w * (i + 0.5) / 4, cy = ty - 2;
        if (b === "q") out.push(`<path d="M${cx - 9} ${cy} q-2 -16 9 -16 q11 0 9 16 q-9 10 -18 0Z" fill="#FF4B3E"/><path d="M${cx - 6} ${cy - 16} l6 -6 6 6Z" fill="#3BB273"/>`);
        if (b === "k") out.push(`<circle cx="${cx}" cy="${cy - 8}" r="8" fill="${["#23C4E8", "#FFC93C", "#7A5CFA", "#3BB273"][i]}"/>`);
        if (b === "y") out.push(`<path d="M${cx} ${cy - 22}l3 6 7 .8-5 4.6 1.4 6.6-6.4-3.4-6.4 3.4 1.4-6.6-5-4.6 7-.8z" fill="#FFC93C"/>`); }
      if (b === "s") k.layers.forEach((_, i) => { const [lx, ly, lw] = tops[i]; for (let j = 0; j < 10; j++) out.push(`<rect x="${lx + 10 + (j * 37) % (lw - 20)}" y="${ly + 26 + (j * 13) % 26}" width="8" height="3" rx="1.5" fill="${["#FF4B3E", "#FFC93C", "#23C4E8", "#7A5CFA"][j % 4]}" transform="rotate(${j * 37 % 90 - 45} ${lx + 14 + (j * 37) % (lw - 20)} ${ly + 28 + (j * 13) % 26})"/>`); });
    });
    for (let i = 0; i < k.sham; i++) { const cx = 160 - (k.sham - 1) * 14 + i * 28, cy = ty - (k.bezak.length ? 22 : 4);
      out.push(`<rect x="${cx - 4}" y="${cy - 40}" width="8" height="40" rx="3" fill="${["#23C4E8", "#FF6FB5", "#3BB273", "#7A5CFA", "#FFB020"][i]}"/><path class="g-flame" d="M${cx} ${cy - 58} q8 10 0 16 q-8 -6 0 -16Z" fill="#FF8A1F"/>`); }
  }
  return `<svg viewBox="0 0 320 360" role="img" aria-label="Siz yasagan tort">${out.join("")}</svg>`;
}
function drawTort() {
  const g = GBY.tort, k = S.cake, st = S.step;
  const STEPS = ["Qavat", "Krem", "Bezak", "Sham"];
  let opts = "", hint = "", next = "";
  if (st === 0) { hint = `Qavat ta'mini tanla (${k.layers.length}/3)`; opts = LAYER.map(([n, c]) => `<button class="g-opt" data-cake="layer" data-v="${c}" aria-label="${n}"><span style="background:${c}"></span>${n}</button>`).join("");
    if (k.layers.length) next = `<button class="gx-btn b" data-cnext>${k.layers.length < 3 ? "Shu yetarli — keyingi" : "Keyingi"}</button>`; }
  if (st === 1) { hint = "Krem rangini tanla"; opts = KREM.map(([n, c]) => `<button class="g-opt${k.krem === c ? " on" : ""}" data-cake="krem" data-v="${c}" aria-label="${n}"><span style="background:${c};border-radius:50%"></span>${n}</button>`).join("");
    if (k.krem) next = `<button class="gx-btn b" data-cnext>Keyingi</button>`; }
  if (st === 2) { hint = "Bezak qo'sh (bir nechta mumkin)"; opts = BEZAK.map(([n, v]) => `<button class="g-opt${k.bezak.includes(v) ? " on" : ""}" data-cake="bezak" data-v="${v}" aria-label="${n}"><span class="ic-${v}"></span>${n}</button>`).join("");
    next = `<button class="gx-btn b" data-cnext>Keyingi</button>`; }
  if (st === 3) { hint = `Nechta sham? (${k.sham})`; opts = [1, 2, 3, 4, 5].map((n) => `<button class="g-opt${k.sham === n ? " on" : ""}" data-cake="sham" data-v="${n}" aria-label="${n} ta sham"><b class="b" style="font-size:26px">${n}</b></button>`).join("");
    if (k.sham) next = `<button class="gx-btn b" data-cdone style="background:#E5487F">Tort tayyor!</button>`; }
  if (st === 4) { hint = "Tug'ilgan kuning bilan!"; next = `<button class="gx-btn b" data-cnew>Yangi tort yasash</button>`; }
  view(bar(g) + `<div class="g-steps">${STEPS.map((s, i) => `<span class="${i < st ? "ok" : i === st ? "cur" : ""}">${s}</span>`).join("")}</div>
    <div class="g-cake">${cakeSVG()}</div><div class="gx-fill"></div>
    <div class="g-tray"><div class="hint b" style="font-size:17px;color:var(--ink)">${hint}</div>${opts ? `<div class="g-opts">${opts}</div>` : ""}${next ? `<div style="margin-top:12px">${next}</div>` : ""}</div>`);
}
function onCake(el) {
  const k = S.cake, t = el.dataset.cake, v = el.dataset.v; sfx.tap(); haptic();
  if (t === "layer" && k.layers.length < 3) { k.layers.push(v); if (k.layers.length === 3) S.step = 1; }
  if (t === "krem") k.krem = v;
  if (t === "bezak") k.bezak = k.bezak.includes(v) ? k.bezak.filter((x) => x !== v) : [...k.bezak, v];
  if (t === "sham") k.sham = +v;
  drawTort();
}
function happyBirthday() {
  const N = {G: 392, A: 440, B: 494, C: 523, D: 587, E: 659, F: 698, G2: 784};
  const m = [["G", .3], ["G", .2], ["A", .5], ["G", .5], ["C", .5], ["B", .9], ["G", .3], ["G", .2], ["A", .5], ["G", .5], ["D", .5], ["C", .9]];
  let w = 0; m.forEach(([n, d]) => { tone(N[n], d * 0.95, "triangle", 0.2, w); w += d; });
}

// ------------------------------------------------------------------ 7. Puzzle
const SCENES = [
  `<rect width="300" height="300" fill="#9BE3F7"/><circle cx="240" cy="60" r="34" fill="#FFE14D"/><ellipse cx="70" cy="60" rx="40" ry="16" fill="#fff"/>
   <path d="M0 200 Q80 160 150 195 T300 185 V300 H0 Z" fill="#5BC06A"/><g transform="translate(100 112)">${ANOR().replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "")}</g>
   <g fill="#FF6FB5"><circle cx="40" cy="250" r="14"/><circle cx="260" cy="240" r="14"/></g><g fill="#FFE14D"><circle cx="40" cy="250" r="6"/><circle cx="260" cy="240" r="6"/></g>`,
  `<rect width="300" height="300" fill="#23C4E8"/><path d="M0 230 Q75 210 150 230 T300 230 V300 H0Z" fill="#F4D58D"/>
   <g transform="translate(60 80)"><ellipse cx="90" cy="70" rx="90" ry="58" fill="#FFB020"/><path d="M170 70 L220 30 L214 70 L220 110Z" fill="#FF6B57"/><circle cx="50" cy="60" r="12" fill="#fff"/><circle cx="53" cy="60" r="6" fill="#1D2A5B"/>
   <path d="M90 30 Q110 70 90 110" fill="none" stroke="#FF6B57" stroke-width="8"/></g><g fill="#fff" opacity=".7"><circle cx="40" cy="50" r="10"/><circle cx="60" cy="30" r="6"/><circle cx="250" cy="60" r="8"/></g>
   <path d="M30 300 C20 260 50 250 40 220 C60 250 50 270 60 300Z" fill="#3BB273"/><path d="M250 300 C240 250 270 240 260 210 C280 240 270 270 280 300Z" fill="#3BB273"/>`,
  `<rect width="300" height="300" fill="#1D2A5B"/><circle cx="230" cy="70" r="40" fill="#FFE66D"/><circle cx="250" cy="60" r="34" fill="#1D2A5B"/>
   <g fill="#fff"><circle cx="40" cy="40" r="3"/><circle cx="120" cy="80" r="2"/><circle cx="70" cy="130" r="3"/><circle cx="180" cy="30" r="2"/><circle cx="280" cy="150" r="3"/></g>
   <path d="M0 240 Q100 200 200 230 T300 220 V300 H0Z" fill="#2E9E60"/><g transform="translate(120 130)"><rect x="0" y="40" width="70" height="60" fill="#FFE66D"/><path d="M-10 44 L35 6 L80 44Z" fill="#FF6B57"/><rect x="25" y="62" width="20" height="38" fill="#B5651D"/><rect x="6" y="52" width="14" height="14" fill="#FFC93C"/></g>`,
];
START.puzzle = () => { S.sc = S.sc === undefined ? 0 : (S.sc + 1) % SCENES.length; S.sel = -1; do { S.order = shuffle([0, 1, 2, 3, 4, 5, 6, 7, 8]); } while (S.order.every((v, i) => v === i)); drawPuzzle(); };
function drawPuzzle() {
  const g = GBY.puzzle, ok = S.order.filter((v, i) => v === i).length;
  view(bar(g, `<div class="gx-pill b">${ok} / 9</div>`) + `<div class="gx-h b" style="color:#fff">Ikkita bo'lakni bos — joyi almashadi</div>
    <div class="g-pz">${S.order.map((v, i) => `<button class="g-tile2${S.sel === i ? " sel" : ""}${v === i ? " ok" : ""}" data-pz="${i}" aria-label="${i + 1}-katak">
      <svg viewBox="${(v % 3) * 100} ${Math.floor(v / 3) * 100} 100 100" aria-hidden="true">${SCENES[S.sc]}</svg></button>`).join("")}</div>
    <div class="gx-fill"></div><div class="g-pzref"><span class="b">Namuna:</span><svg viewBox="0 0 300 300" aria-hidden="true">${SCENES[S.sc]}</svg></div>`);
}
function onPz(el) {
  const i = +el.dataset.pz;
  if (S.sel < 0) { S.sel = i; sfx.tap(); haptic(); drawPuzzle(); return; }
  if (S.sel !== i) { [S.order[S.sel], S.order[i]] = [S.order[i], S.order[S.sel]]; sfx.flip(); haptic("hit"); }
  S.sel = -1; drawPuzzle();
  if (S.order.every((v, k) => v === k)) { S.lock = true; yay("Rasm yig'ildi!", 2); later(START.puzzle, 1700); }
}

// ------------------------------------------------------------------ 8. Farqini top
const FEAT = [
  {k: "sun", hx: 250, hy: 45, a: '<circle cx="250" cy="45" r="24" fill="#FFE14D"/>', b: '<circle cx="250" cy="45" r="24" fill="#FF9F1C"/>'},
  {k: "cloud", hx: 70, hy: 45, a: '<ellipse cx="70" cy="45" rx="32" ry="13" fill="#fff"/>', b: ""},
  {k: "roof", hx: 140, hy: 85, a: '<path d="M80 100 L140 55 L200 100 Z" fill="#FF6B57"/>', b: '<path d="M80 100 L140 55 L200 100 Z" fill="#3BB273"/>'},
  {k: "door", hx: 141, hy: 154, a: '<rect x="128" y="130" width="26" height="48" rx="4" fill="#2E86DE"/>', b: '<rect x="128" y="130" width="26" height="48" rx="4" fill="#7A5CFA"/>'},
  {k: "win", hx: 170, hy: 124, a: '<rect x="160" y="114" width="20" height="20" rx="3" fill="#9BE3F7"/>', b: ""},
  {k: "apple", hx: 236, hy: 104, a: '<circle cx="236" cy="104" r="6" fill="#FF4B3E"/>', b: ""},
  {k: "flower", hx: 70, hy: 196, a: '<circle cx="70" cy="196" r="9" fill="#FF6FB5"/><circle cx="70" cy="196" r="3.5" fill="#FFE14D"/>', b: ""},
  {k: "bird", hx: 150, hy: 30, a: '<path d="M138 30 q6 -8 12 0 q6 -8 12 0" fill="none" stroke="#1D2A5B" stroke-width="3" stroke-linecap="round"/>', b: ""},
  {k: "chim", hx: 172, hy: 64, a: '<rect x="165" y="56" width="14" height="24" fill="#B5651D"/>', b: ""},
  {k: "cat", hx: 30, hy: 160, a: '<g transform="translate(16 146)"><path d="M4 10 L6 0 L12 6Z M24 10 L22 0 L16 6Z" fill="#FF9F1C"/><circle cx="14" cy="14" r="11" fill="#FF9F1C"/><circle cx="10" cy="13" r="2" fill="#1D2A5B"/><circle cx="18" cy="13" r="2" fill="#1D2A5B"/></g>', b: ""},
];
START.farq = () => { S.diff = pickN(FEAT.map((f) => f.k), 5); S.found = []; drawFarq(); };
function farqSVG(variant) {
  const marks = S.found.map((k) => { const f = FEAT.find((x) => x.k === k); return `<circle cx="${f.hx}" cy="${f.hy}" r="24" fill="none" stroke="#3BB273" stroke-width="5"/>`; }).join("");
  return `<svg viewBox="0 0 300 230" ${variant ? 'id="gfarq" role="img" aria-label="Ikkinchi rasm — farqlarni shu yerdan bos"' : 'role="img" aria-label="Birinchi rasm"'}>
    <rect width="300" height="230" fill="#BFE6FF"/><rect x="0" y="170" width="300" height="60" fill="#5BC06A"/>
    <rect x="90" y="100" width="100" height="78" fill="#FFE66D"/><rect x="100" y="114" width="20" height="20" rx="3" fill="#9BE3F7"/>
    <rect x="240" y="120" width="12" height="56" fill="#9C6B3E"/><circle cx="246" cy="110" r="28" fill="#3BB273"/>
    <circle cx="40" cy="190" r="9" fill="#FF6FB5"/><circle cx="40" cy="190" r="3.5" fill="#FFE14D"/>
    ${FEAT.map((f) => (variant && S.diff.includes(f.k) ? f.b : f.a)).join("")}${marks}</svg>`;
}
function drawFarq() {
  const g = GBY.farq;
  view(bar(g, `<div class="gx-pill b">${S.found.length} / 5</div>`) + `<div class="g-farq">${farqSVG(false)}</div><div class="g-farq">${farqSVG(true)}</div>
    <div class="gx-fill"></div><div class="g-farqf"><b class="b">${S.found.length ? `${S.found.length} ta topildi!` : "Pastki rasmda 5 ta farq bor"}</b>
    <button class="gx-btn b" data-fhelp style="background:#FFC93C;color:#1D2A5B">Yordam</button></div>`);
}
function onFarq(e) {
  const svg = $("gfarq"); if (!svg) return;
  const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * 300, y = (e.clientY - r.top) / r.height * 230;
  const f = FEAT.find((q) => S.diff.includes(q.k) && !S.found.includes(q.k) && Math.hypot(q.hx - x, q.hy - y) < 30);
  if (!f) { wrong(svg.parentElement); return; }
  S.found.push(f.k); sfx.ok(); haptic("ok"); drawFarq();
  if (S.found.length === 5) { yay("Hammasini topding!", 2); later(START.farq, 1800); }
}

// ------------------------------------------------------------------ 9. Osh pishir
const ING = {gosht: {n: "Go'sht", c: "#B3263A"}, piyoz: {n: "Piyoz", c: "#F3E1B8"}, sabzi: {n: "Sabzi", c: "#FF8A1F"}, guruch: {n: "Guruch", c: "#FFFFFF"}, zira: {n: "Zira", c: "#9C6B3E"}};
const ING_IC = {
  gosht: '<path d="M10 24 C10 12 30 8 38 16 C46 24 40 38 26 38 C16 38 10 32 10 24Z" fill="#B3263A"/><circle cx="20" cy="24" r="5" fill="#FFF1DE"/>',
  piyoz: '<path d="M24 6 C34 16 40 24 38 32 C36 42 12 42 10 32 C8 24 14 16 24 6Z" fill="#F3E1B8"/><path d="M24 6 V40 M17 14 Q14 30 20 40 M31 14 Q34 30 28 40" stroke="#D9BE85" stroke-width="2" fill="none"/>',
  sabzi: '<path d="M16 12 H32 L24 44 Z" fill="#FF8A1F"/><path d="M20 12 C16 4 22 2 24 10 C26 2 32 4 28 12 Z" fill="#3BB273"/>',
  guruch: '<path d="M6 28 Q24 44 42 28 Z" fill="#E8E2D2"/><g fill="#fff"><ellipse cx="16" cy="26" rx="3" ry="2"/><ellipse cx="24" cy="24" rx="3" ry="2"/><ellipse cx="32" cy="26" rx="3" ry="2"/><ellipse cx="20" cy="22" rx="3" ry="2"/><ellipse cx="28" cy="21" rx="3" ry="2"/></g>',
  zira: '<path d="M14 14 H34 V40 Q24 46 14 40 Z" fill="#9C6B3E"/><rect x="12" y="8" width="24" height="7" rx="2" fill="#E2DCCF"/>',
};
const OSH_STEPS = ["gosht", "piyoz", "sabzi", "zira", "guruch", "dam"];
START.osh = () => { S.st = 0; S.added = []; S.chop = 0; S.chopping = false; drawOsh(); };
function drawOsh(msg) {
  const g = GBY.osh, cur = OSH_STEPS[S.st];
  const say = msg || (cur === "dam" ? "Endi qopqoqni yop — dam yesin!" : cur ? `Endi ${ING[cur].n.toLowerCase()} solamiz!` : "Osh tayyor! Osh bo'lsin!");
  const inPot = S.added.map((k, i) => `<g fill="${ING[k].c}">${Array.from({length: 5}, (_, j) => `<ellipse cx="${100 + ((j * 47 + i * 23) % 120)}" cy="${186 + ((j * 7 + i * 3) % 12)}" rx="${k === "guruch" ? 60 : 9}" ry="${k === "guruch" ? 9 : 5}"/>`).join("")}</g>`).join("");
  const done = S.st >= OSH_STEPS.length;
  view(bar(g) + `<div class="g-steps">${["Go'sht", "Piyoz", "Sabzi", "Zira", "Guruch", "Dam"].map((s, i) => `<span class="${i < S.st ? "ok" : i === S.st ? "cur" : ""}">${s}</span>`).join("")}</div>
    ${speech(say)}
    <div class="g-pot"><svg viewBox="0 0 320 300" role="img" aria-label="Qozon">
      ${S.lid || done ? '<g fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" opacity=".85"><path class="g-steam" d="M120 110 q-14 -22 0 -40 q14 -18 0 -40"/><path class="g-steam" d="M160 100 q-14 -22 0 -40 q14 -18 0 -40"/><path class="g-steam" d="M200 110 q-14 -22 0 -40 q14 -18 0 -40"/></g>' : ""}
      <rect x="40" y="250" width="240" height="44" rx="14" fill="#8A5A35"/>
      <path d="M55 170 H265 Q260 290 160 290 Q60 290 55 170 Z" fill="#3A3F52"/>
      <path class="g-fire" d="M70 294 q8 -30 18 -6 q6 -24 15 0 q10 -30 20 0 q8 -22 16 0 q10 -30 18 0 q8 -20 16 0 q10 -30 18 0 q8 -24 16 0 q8 -30 18 0 q8 -22 16 0 q8 -26 18 0 Z" fill="#FF8A1F"/>
      <path class="g-fire" d="M100 294 q6 -16 12 0 q6 -18 12 0 M150 294 q6 -18 12 0 q6 -14 12 0 M200 294 q6 -18 12 0" fill="#FFE14D"/><ellipse cx="160" cy="170" rx="108" ry="24" fill="#2A2E3D"/>
      <ellipse cx="160" cy="172" rx="96" ry="18" fill="${S.added.includes("guruch") ? "#F1E3C2" : "#C97B3A"}"/>${inPot}
      ${S.lid || done ? '<path d="M50 168 Q160 110 270 168 Z" fill="#555B72"/><circle cx="160" cy="126" r="9" fill="#2A2E3D"/>' : ""}</svg></div>
    <div class="gx-fill"></div>
    ${S.chopping ? `<div class="g-tray"><div class="hint b" style="font-size:17px;color:var(--ink)">Sabzini to'g'ra! (${S.chop}/5)</div>
      <button class="g-board2" data-chop aria-label="Sabzini to'g'rash"><svg viewBox="0 0 220 80" aria-hidden="true"><rect x="0" y="20" width="220" height="56" rx="14" fill="#E8C27A"/>
        <path d="M${30 + S.chop * 26} 36 H190 L200 48 L190 60 H${30 + S.chop * 26} Z" fill="#FF8A1F"/><path d="M190 40 C200 30 210 34 204 46" fill="#3BB273"/>
        ${Array.from({length: S.chop}, (_, i) => `<ellipse cx="${30 + i * 26}" cy="${48 + (i % 2) * 6}" rx="10" ry="8" fill="#FF8A1F"/>`).join("")}</svg></button></div>`
    : done ? `<div class="g-tray" style="text-align:center"><button class="gx-btn b" data-onew>Yana pishirish</button></div>`
    : cur === "dam" ? `<div class="g-tray" style="text-align:center"><button class="gx-btn b" data-lid ${S.lid ? "disabled" : ""}>${S.lid ? "Dam yeyapti…" : "Qopqoqni yopish"}</button></div>`
    : `<div class="g-tray"><div class="g-opts">${shuffle(Object.keys(ING)).map((k) => `<button class="g-opt" data-ing="${k}" aria-label="${ING[k].n}"><svg viewBox="0 0 48 48" aria-hidden="true">${ING_IC[k]}</svg>${ING[k].n}</button>`).join("")}</div></div>`}`);
}
function onIng(k) {
  if (OSH_STEPS[S.st] !== k) { wrong(document.querySelector(`[data-ing="${k}"]`)); drawOshSay(`Hali emas! Avval ${ING[OSH_STEPS[S.st]].n.toLowerCase()}.`); return; }
  if (k === "sabzi") { S.chopping = true; sfx.tap(); drawOsh("Sabzini mayda to'g'ra!"); return; }
  S.added.push(k); S.st++; sfx.ok(); haptic("ok"); tone(180, 0.4, "sawtooth", 0.04); drawOsh();
}
function drawOshSay(t) { const b = document.querySelector(".g-say b"); if (b) b.textContent = t; }
function onChop() {
  S.chop++; tone(300 + S.chop * 40, 0.05, "square", 0.08); haptic("hit");
  if (S.chop >= 5) { S.chopping = false; S.added.push("sabzi"); S.st++; sfx.ok(); drawOsh(); return; }
  drawOsh("Chiq-chiq-chiq!");
}
function onLid() {
  S.lid = true; drawOsh("Kutamiz… 3… 2… 1…"); tone(200, 1.6, "sine", 0.05);
  later(() => { S.st++; drawOsh(); yay("Osh tayyor!", 2); }, 2600);
}

// ------------------------------------------------------------------ 10. Soya o'yini
function shadowSVG(k) {
  const a = ANIMAL[k];
  return `<svg viewBox="0 0 60 60" role="img" aria-label="Kimningdir soyasi">${a.ears ? `<path d="${a.ears}" fill="#0B1238"/>` : ""}<circle cx="30" cy="34" r="20" fill="#0B1238"/>
    ${k === "xoroz" || k === "ordak" || k === "joja" ? `<path d="${a.nose}" fill="#0B1238" transform="translate(${k === "ordak" ? 14 : 12} 0)"/>` : ""}${k === "qoy" ? '<circle cx="19" cy="16" r="7" fill="#0B1238"/><circle cx="30" cy="12" r="8" fill="#0B1238"/><circle cx="41" cy="16" r="7" fill="#0B1238"/>' : ""}
    ${k === "mushuk" ? '<path d="M6 38 H18 M6 43 H18 M42 38 H54 M42 43 H54" stroke="#0B1238" stroke-width="2" stroke-linecap="round"/>' : ""}</svg>`;
}
START.soya = () => { S.r = 0; S.ok = 0; soyaRound(); };
function soyaRound() {
  const g = GBY.soya, three = pickN(Object.keys(ANIMAL), 3);
  S.target = three[rnd(3)]; S.lock = false;
  view(bar(g, `<div class="gx-pill b">${S.r + 1} / 10</div>`) + `<div class="gx-h b" style="color:#fff;text-align:center">Bu kimning soyasi?</div>
    <div class="g-shadow"><div class="beam"></div>${shadowSVG(S.target)}</div><div class="gx-fill"></div>
    <div class="g-ani3">${three.map((k) => `<button data-soy="${k}" aria-label="${ANIMAL[k].n}">${animalSVG(k)}<b class="b">${ANIMAL[k].n}</b></button>`).join("")}</div>`);
}
function onSoya(b) {
  if (S.lock) return;
  if (b.dataset.soy !== S.target) { wrong(b); return; }
  S.lock = true; b.classList.add("ok"); sfx.ok(); haptic("ok");
  const sh = document.querySelector(".g-shadow svg"); if (sh) sh.outerHTML = animalSVG(S.target);
  if (CALL[S.target]) later(() => CALL[S.target](ctx()), 200);
  S.r++; S.ok++;
  later(() => { if (S.r >= 10) { yay("10 tadan 10!", 2); S.r = 0; } else addStar(1); soyaRound(); }, 1300);
}

// ------------------------------------------------------------------ kunlik sandiqcha
function chestReady() { return lsGet("zk_gchest", "") !== today(); }
function openChest() {
  if (!chestReady()) return;
  lsSet("zk_gchest", today());
  yay("Kunlik sovg'a: +3 ★", 3); renderHome();
}

// =================================================================== 3-TO'PLAM: 30 ta o'yin
const ACT = {};
ACT.reset = () => { haptic(); clearTimers(); const id = cur; S = {}; START[id](); };
const RESET = '<button class="gx-back g-rst" data-act="reset" aria-label="Qaytadan boshlash"><svg viewBox="0 0 24 24" fill="none" stroke="#1D2A5B" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12a8 8 0 1 0 2.5-5.8"/><path d="M4 4v5h5"/></svg></button>';
const hud = (txt, id = "gsc") => `<div class="g-hud"><div class="gx-pill b" id="${id}">${txt}</div>${RESET}</div>`;
const setTxt = (id, v) => { const e = $(id); if (e) e.textContent = v; };
const STARP = (c, x, y, r, col) => { c.fillStyle = col; c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr2 = i % 2 ? r * 0.45 : r; c.lineTo(x + Math.cos(a) * rr2, y + Math.sin(a) * rr2); } c.fill(); };
const ICO = (body, vb = "0 0 60 60") => `<svg viewBox="${vb}" aria-hidden="true">${body}</svg>`;

// Kategoriyalar (eski o'yinlar uchun ham)
Object.entries({sharcha: "aql", juftlik: "aql", poyezd: "aql", sanoq: "aql", boyoq: "ijod", shakl: "aql", ovoz: "musiqa", labirint: "aql", kiyin: "ijod",
  pianino: "musiqa", kuchuk: "hayvon", mushuk: "harakat", savat: "harakat", qushcha: "harakat", poyga: "harakat", tort: "ijod", puzzle: "aql",
  farq: "aql", osh: "ijod", soya: "aql"}).forEach(([k, c]) => { if (GBY[k]) GBY[k].cat = c; });

const G3 = [];
function reg(id, n, cat, age, bg, c1, c2, ic, start) {
  const g = {id, n, cat, age, bg, c1, c2, edge: c2, ic, v3: 1};
  G3.push(g); GAMES.push(g); GBY[id] = g; START[id] = start;
}

// ------------------------------------------------------------------ 1. Ajdahochani boq
const DRAGON = (chew) => `<svg viewBox="0 0 160 160" role="img" aria-label="Ajdahocha">
  <ellipse cx="80" cy="150" rx="50" ry="7" fill="rgba(0,0,0,.12)"/>
  <path d="M112 112 Q150 110 146 80 Q140 98 120 96 Z" fill="#7ED957"/>
  <path d="M40 60 L18 34 L46 44 Z M120 60 L142 34 L114 44 Z" fill="#B48CFF"/>
  <ellipse cx="80" cy="110" rx="40" ry="34" fill="#5CCB6B"/><ellipse cx="80" cy="118" rx="24" ry="22" fill="#D7F7C8"/>
  <path d="M52 92 Q30 80 34 104 Z M108 92 Q130 80 126 104 Z" fill="#B48CFF"/>
  <circle cx="80" cy="62" r="40" fill="#5CCB6B"/>
  <path d="M62 26 l6 -14 6 14Z M80 22 l6 -16 6 16Z M98 26 l6 -14 6 14Z" fill="#FFC93C"/>
  <circle cx="64" cy="58" r="12" fill="#fff"/><circle cx="96" cy="58" r="12" fill="#fff"/>
  <circle cx="66" cy="60" r="7" fill="#1D2A5B"/><circle cx="98" cy="60" r="7" fill="#1D2A5B"/><circle cx="68" cy="57" r="2.5" fill="#fff"/><circle cx="100" cy="57" r="2.5" fill="#fff"/>
  <ellipse cx="54" cy="78" rx="6" ry="4" fill="#FF9AA8"/><ellipse cx="106" cy="78" rx="6" ry="4" fill="#FF9AA8"/>
  ${chew ? '<ellipse cx="80" cy="84" rx="12" ry="6" fill="#7A1F2B"/>' : '<path d="M66 80 Q80 94 94 80 Z" fill="#7A1F2B"/><path d="M72 81 l3 5 3 -5Z M84 81 l3 5 3 -5Z" fill="#fff"/>'}
  <circle cx="74" cy="72" r="2" fill="#2A8A55"/><circle cx="86" cy="72" r="2" fill="#2A8A55"/></svg>`;
const DFOOD = [["olma", "Olma", 18, 6, '<circle cx="24" cy="27" r="16" fill="#FF4B3E"/><path d="M24 11 q2 -6 8 -6" stroke="#6B4423" stroke-width="3" fill="none"/><ellipse cx="32" cy="8" rx="6" ry="3" fill="#7ED957"/>'],
  ["rezavor", "Rezavor", 12, 12, '<g fill="#7A5CFA"><circle cx="18" cy="22" r="8"/><circle cx="30" cy="22" r="8"/><circle cx="24" cy="33" r="8"/></g><path d="M24 14 V6" stroke="#3BB273" stroke-width="3"/>'],
  ["pechenye", "Sehrli pechenye", 8, 22, '<circle cx="24" cy="24" r="17" fill="#E8B07A"/><g fill="#7E4A1E"><circle cx="18" cy="19" r="3"/><circle cx="29" cy="27" r="3"/><circle cx="20" cy="31" r="2.5"/></g><path d="M38 8 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="#FFC93C"/>']];
reg("ajdaho", "Ajdahochani boq", "hayvon", "3–7 yosh", "#E3F7D6", "#E3F7D6", "#2E9E60", ICO(DRAGON(false).replace(/^<svg[^>]*>/, "").replace("</svg>", ""), "0 0 160 160"), () => {
  const d = lsGet("zk_gdrag", {hun: 40, hap: 50, ts: Date.now(), day: "", got: 0});
  const h = Math.min(48, (Date.now() - d.ts) / 3600000); d.hun = Math.max(0, d.hun - h * 8); d.hap = Math.max(0, d.hap - h * 5); d.ts = Date.now();
  if (d.day !== today()) { d.day = today(); d.got = 0; }
  S.d = d; drawDragon();
});
function drawDragon(chew) {
  const g = GBY.ajdaho, d = S.d;
  const msg = chew ? "Nyam-nyam!" : d.hun < 40 ? "Qornim och! Meni boqasanmi?" : d.hap < 50 ? "Sehrli pechenye bormi?" : "Rahmat, do'stim! Men baxtliman!";
  view(bar(g, hud(`${Math.round(d.hap)}% ♥`)) + `<div class="g-needs g-needs2"><div><span>Ochlik</span><i><em style="width:${Math.round(d.hun)}%;background:#FF4D5E"></em></i></div>
    <div><span>Kayfiyat</span><i><em style="width:${Math.round(d.hap)}%;background:#FFC93C"></em></i></div></div>
    <div class="g-bub b" style="margin:12px auto 0">${msg}</div>
    <div class="g-dragon${chew ? " chew" : ""}" id="gdrag">${DRAGON(chew)}</div><div class="gx-fill"></div>
    <div class="g-tray"><div class="hint">Ovqatni bos — ajdahocha yeydi</div><div class="g-opts" style="grid-template-columns:repeat(3,1fr)">
    ${DFOOD.map(([k, n, , , ic]) => `<button class="g-opt" data-act="dfeed" data-k="${k}" aria-label="${n}"><svg viewBox="0 0 48 48" aria-hidden="true">${ic}</svg>${n}</button>`).join("")}</div></div>`);
}
ACT.dfeed = (el) => {
  if (S.chewing) return;
  const f = DFOOD.find((x) => x[0] === el.dataset.k), d = S.d;
  d.hun = Math.min(100, d.hun + f[2]); d.hap = Math.min(100, d.hap + f[3]); lsSet("zk_gdrag", d);
  S.chewing = true; drawDragon(true); [0, 0.18, 0.36].forEach((w) => tone(260, 0.1, "square", 0.06, w));
  haptic("hit");
  if (d.got < 10) { d.got++; addStar(1); lsSet("zk_gdrag", d); }
  later(() => { S.chewing = false; drawDragon(false); if (d.hun >= 95 && d.hap >= 95) yay("Ajdahocha juda baxtli!"); }, 900);
};

// ------------------------------------------------------------------ 2. Bog'bon bola
const POT = (st, wet) => `<svg viewBox="0 0 100 130" aria-hidden="true">
  ${st >= 1 && st < 2 ? '<ellipse cx="50" cy="66" rx="6" ry="4" fill="#8A5A35"/>' : ""}
  ${st >= 2 ? '<path d="M50 70 V40" stroke="#3BB273" stroke-width="5" stroke-linecap="round"/><path d="M50 52 Q36 40 30 48 Q40 56 50 54 Z M50 46 Q64 34 70 42 Q60 50 50 48 Z" fill="#5BC06A"/>' : ""}
  ${st >= 3 ? '<path d="M50 40 V14" stroke="#3BB273" stroke-width="5"/><g fill="#FF6FB5"><circle cx="50" cy="4" r="10"/><circle cx="62" cy="14" r="10"/><circle cx="56" cy="27" r="10"/><circle cx="44" cy="27" r="10"/><circle cx="38" cy="14" r="10"/></g><circle cx="50" cy="16" r="8" fill="#FFE14D"/>' : ""}
  <ellipse cx="50" cy="70" rx="38" ry="9" fill="${wet ? "#5A3A20" : "#8A5A35"}"/>
  <path d="M10 70 H90 L80 126 H20 Z" fill="#E86A2C"/><rect x="6" y="64" width="88" height="14" rx="6" fill="#FF8C42"/>
  ${wet ? '<g fill="#4FC3F7"><circle cx="30" cy="60" r="3"/><circle cx="70" cy="58" r="3"/></g>' : ""}</svg>`;
const GTOOLS = [["urug", "Urug'", '<g fill="#8A5A35"><ellipse cx="16" cy="26" rx="5" ry="7"/><ellipse cx="30" cy="20" rx="5" ry="7"/><ellipse cx="32" cy="34" rx="5" ry="7"/></g>'],
  ["suv", "Suv", '<path d="M8 20 H30 V40 H8 Z" fill="#23C4E8"/><path d="M30 24 L44 14" stroke="#23C4E8" stroke-width="5" stroke-linecap="round"/><path d="M12 20 Q20 6 28 20" fill="none" stroke="#23C4E8" stroke-width="4"/>'],
  ["quyosh", "Quyosh", '<circle cx="24" cy="24" r="10" fill="#FFC93C"/><g stroke="#FFC93C" stroke-width="3" stroke-linecap="round"><path d="M24 4v5M24 39v5M4 24h5M39 24h5M10 10l4 4M34 34l4 4M10 38l4-4M34 14l4-4"/></g>']];
reg("bogbon", "Bog'bon bola", "hayvon", "3–7 yosh", "#DFF6C9", "#DFF6C9", "#5BA33A", ICO('<path d="M10 30 H50 L44 56 H16 Z" fill="#E86A2C"/><path d="M30 30 V14" stroke="#3BB273" stroke-width="4"/><g fill="#FF6FB5"><circle cx="30" cy="8" r="6"/><circle cx="37" cy="14" r="6"/><circle cx="23" cy="14" r="6"/></g><circle cx="30" cy="13" r="4" fill="#FFE14D"/>'), () => {
  S.pots = lsGet("zk_ggarden", [{st: 0}, {st: 0}, {st: 0}]); S.tool = "urug"; drawGarden();
  S.tick = setInterval(() => { if (cur !== "bogbon") return; let ch = false;
    S.pots.forEach((p) => { if (p.wet && Date.now() >= p.at) { p.st = Math.min(3, p.st + 1); p.wet = false; ch = true; } });
    if (ch) { lsSet("zk_ggarden", S.pots); sfx.ok(); drawGarden(); } }, 500);
});
function drawGarden() {
  const g = GBY.bogbon, msg = { urug: "Bo'sh tuvakka urug' ek", suv: "Urug' yoki nihol bor tuvakni sug'or", quyosh: "Quyosh — gullar tezroq o'sadi!" }[S.tool];
  view(bar(g, hud(`${S.pots.filter((p) => p.st === 3).length} gul`)) + speech(msg) +
    `<div class="g-garden">${S.pots.map((p, i) => `<button class="g-pot2" data-act="gpot" data-i="${i}" aria-label="${i + 1}-tuvak">${POT(p.st, p.wet)}
      <span class="lbl">${["Bo'sh", "Urug'", "Nihol", "Gul — terib ol!"][p.st]}${p.wet ? " · o'syapti" : ""}</span></button>`).join("")}</div>
    <div class="gx-fill"></div><div class="g-tray"><div class="g-opts" style="grid-template-columns:repeat(3,1fr)">
    ${GTOOLS.map(([k, n, ic]) => `<button class="g-opt${S.tool === k ? " on" : ""}" data-act="gtool" data-k="${k}" aria-label="${n}"><svg viewBox="0 0 48 48" aria-hidden="true">${ic}</svg>${n}</button>`).join("")}</div></div>`);
}
ACT.gtool = (el) => { S.tool = el.dataset.k; haptic(); drawGarden(); };
ACT.gpot = (el) => {
  const p = S.pots[+el.dataset.i];
  if (p.st === 3) { p.st = 0; p.wet = false; addStar(1); sfx.win(); haptic("ok"); }
  else if (S.tool === "urug" && p.st === 0) { p.st = 1; sfx.tap(); }
  else if (S.tool === "suv" && p.st >= 1 && !p.wet) { p.wet = true; p.at = Date.now() + 5000; tone(900, 0.3, "sine", 0.06, 0, 400); }
  else if (S.tool === "quyosh" && p.wet) { p.at = Math.min(p.at, Date.now() + 800); sfx.tap(); }
  else { wrong(el); return; }
  lsSet("zk_ggarden", S.pots); drawGarden();
};

// ------------------------------------------------------------------ 3. Qurbaqa sakrashi
reg("qurbaqa", "Qurbaqa sakrashi", "harakat", "4–9 yosh", "#7FD8D2", "#D6F5F2", "#1F9E94", ICO('<ellipse cx="30" cy="40" rx="24" ry="10" fill="#3BB273"/><circle cx="30" cy="30" r="14" fill="#5BC06A"/><circle cx="22" cy="20" r="6" fill="#5BC06A"/><circle cx="38" cy="20" r="6" fill="#5BC06A"/><circle cx="22" cy="20" r="3" fill="#1D2A5B"/><circle cx="38" cy="20" r="3" fill="#1D2A5B"/><path d="M22 34 Q30 40 38 34" stroke="#1D2A5B" stroke-width="2" fill="none"/>'), () => {
  arcadeView(GBY.qurbaqa, hud("0"), "Bosib tur — kuch yig'iladi<br><small>Qo'yib yubor — qurbaqa sakraydi</small>");
  arcade({id: "qurbaqa", stars: (s) => (s >= 25 ? 3 : s >= 12 ? 2 : s >= 4 ? 1 : 0),
    init(g) { g.pads = [{x: 70, r: 42}]; let x = 70; for (let i = 0; i < 40; i++) { x += 110 + rnd(110); g.pads.push({x, r: 34 + rnd(14), star: Math.random() < 0.5}); }
      Object.assign(g, {fx: 70, fy: 0, jump: null, pow: 0, cam: 0, pad: 0}); },
    tap(g) { if (!g.jump) g.charging = true; },
    release(g) { if (!g.charging || g.jump) return; g.charging = false; const d = 60 + g.pow * 300; g.jump = {x0: g.fx, x1: g.fx + d, t: 0}; g.pow = 0; tone(500, 0.15, "triangle", 0.14, 0, 900); },
    step(g, dt) {
      if (g.charging) g.pow = Math.min(1, g.pow + dt * 0.9);
      if (g.jump) { const j = g.jump; j.t += dt * 1.8; const k = Math.min(1, j.t); g.fx = j.x0 + (j.x1 - j.x0) * k; g.fy = -Math.sin(k * Math.PI) * 110;
        if (k >= 1) { g.jump = null; g.fy = 0;
          const p = g.pads.find((q) => Math.abs(q.x - g.fx) < q.r);
          if (!p) { g.splash = 1; tone(160, 0.4, "sine", 0.2, 0, 60); g.finish(); return; }
          const idx = g.pads.indexOf(p);
          if (idx > g.pad) { g.score += idx - g.pad; if (Math.abs(p.x - g.fx) < 10) { g.score += 2; sfx.ok(); } else sfx.tap(); if (p.star) { p.star = false; g.score += 3; tone(1200, 0.08, "sine", 0.15); } g.pad = idx; }
          g.fx = p.x; } }
      g.cam += (g.fx - 80 - g.cam) * Math.min(1, dt * 4); setTxt("gsc", Math.floor(g.score));
    },
    draw(g, c) {
      const {W, H} = g, wy = H * 0.62;
      c.fillStyle = "#BFEFFF"; c.fillRect(0, 0, W, wy); c.fillStyle = "#3FB8D9"; c.fillRect(0, wy, W, H - wy);
      c.fillStyle = "rgba(255,255,255,.35)"; for (let i = 0; i < 6; i++) rr(c, ((i * 97 - g.cam * 0.5) % (W + 60) + W + 60) % (W + 60) - 30, wy + 40 + i * 30, 50, 6, 3);
      g.pads.forEach((p) => { const x = p.x - g.cam; if (x < -60 || x > W + 60) return;
        c.fillStyle = "#2A8A55"; c.beginPath(); c.ellipse(x, wy + 22, p.r, p.r * 0.42, 0, 0, 7); c.fill();
        c.fillStyle = "#6FD07A"; c.beginPath(); c.ellipse(x, wy + 18, p.r, p.r * 0.4, 0, 0.35, Math.PI * 2 - 0.05); c.lineTo(x, wy + 18); c.fill();
        if (p.star) STARP(c, x, wy - 40, 13, "#FFC93C"); });
      const x = g.fx - g.cam, y = wy + 8 + g.fy;
      if (!g.splash || !g.over) { c.fillStyle = "#5BC06A"; c.beginPath(); c.ellipse(x, y - 12, 22, 16, 0, 0, 7); c.fill();
        circ(c, x - 9, y - 28, 7, "#5BC06A"); circ(c, x + 9, y - 28, 7, "#5BC06A"); circ(c, x - 9, y - 28, 3.5, "#1D2A5B"); circ(c, x + 9, y - 28, 3.5, "#1D2A5B");
        c.strokeStyle = "#1D2A5B"; c.lineWidth = 2; c.beginPath(); c.arc(x, y - 16, 6, 0.2, Math.PI - 0.2); c.stroke(); }
      if (g.charging) { c.fillStyle = "rgba(29,42,91,.2)"; rr(c, W / 2 - 80, 24, 160, 16, 8); c.fillStyle = g.pow > 0.8 ? "#FF4D5E" : "#FFC93C"; rr(c, W / 2 - 80, 24, 160 * g.pow, 16, 8); }
    },
  });
});

// ------------------------------------------------------------------ 4. Asalari sayohati
reg("asalari", "Asalari sayohati", "harakat", "4–9 yosh", "#C9F2A8", "#F1FBE5", "#5BA33A", ICO('<ellipse cx="30" cy="34" rx="18" ry="14" fill="#FFC93C"/><path d="M24 22 V46 M34 22 V46" stroke="#1D2A5B" stroke-width="5"/><ellipse cx="24" cy="18" rx="10" ry="7" fill="#DFF3FF"/><ellipse cx="38" cy="18" rx="10" ry="7" fill="#DFF3FF"/><circle cx="44" cy="32" r="3" fill="#1D2A5B"/>'), () => {
  arcadeView(GBY.asalari, hud("0"), "Bos — asalari qanot qoqadi<br><small>Gullardan nektar yig', o'rgimchakdan qoch</small>");
  arcade({id: "asalari", stars: (s) => (s >= 80 ? 3 : s >= 40 ? 2 : s >= 10 ? 1 : 0),
    init(g) { Object.assign(g, {b: {x: 90, y: g.H / 2, vy: 0}, obs: [], fl: [], next: 1, nf: 0.6}); },
    idle(g) { g.b.y = g.H / 2 + Math.sin(performance.now() / 250) * 8; },
    tap(g) { g.b.vy = -360; tone(300, 0.06, "sawtooth", 0.05); },
    step(g, dt) {
      const b = g.b; b.vy += 1000 * dt; b.y += b.vy * dt; if (b.y < 24) { b.y = 24; b.vy = 0; } if (b.y > g.H - 40) g.finish();
      const sp = 150 + Math.min(120, g.t * 3);
      g.next -= dt; if (g.next <= 0) { const top = Math.random() < 0.5; g.obs.push({x: g.W + 30, y: top ? 60 + rnd(g.H * 0.3) : g.H * 0.5 + rnd(g.H * 0.3), top, bird: !top && Math.random() < 0.5}); g.next = 1.3 + Math.random(); }
      g.nf -= dt; if (g.nf <= 0) { g.fl.push({x: g.W + 20, y: 60 + rnd(g.H - 160)}); g.nf = 0.9 + Math.random() * 0.8; }
      g.obs.forEach((o) => { o.x -= sp * dt * (o.bird ? 1.4 : 1); }); g.fl.forEach((f) => { f.x -= sp * dt; });
      g.obs = g.obs.filter((o) => o.x > -40); g.fl = g.fl.filter((f) => f.x > -30 && !f.got);
      if (g.obs.some((o) => Math.hypot(o.x - b.x, o.y - b.y) < 32)) g.finish();
      g.fl.forEach((f) => { if (!f.got && Math.hypot(f.x - b.x, f.y - b.y) < 34) { f.got = true; g.score += 5; tone(1000 + rnd(400), 0.07, "triangle", 0.12); } });
      g.score += dt; setTxt("gsc", Math.floor(g.score));
    },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#C9F2A8"; c.fillRect(0, 0, W, H); c.fillStyle = "#9FE08F"; c.fillRect(0, H - 50, W, 50);
      g.fl.forEach((f) => { c.fillStyle = "#FF6FB5"; for (let i = 0; i < 5; i++) { const a = i * 1.256; circ(c, f.x + Math.cos(a) * 9, f.y + Math.sin(a) * 9, 7, "#FF6FB5"); } circ(c, f.x, f.y, 6, "#FFE14D"); });
      g.obs.forEach((o) => { if (o.top) { c.strokeStyle = "#5C6A99"; c.lineWidth = 2; c.beginPath(); c.moveTo(o.x, 0); c.lineTo(o.x, o.y); c.stroke(); circ(c, o.x, o.y, 15, "#1D2A5B");
          c.strokeStyle = "#1D2A5B"; c.lineWidth = 3; for (let i = -1; i <= 1; i += 2) for (let k = 0; k < 3; k++) { c.beginPath(); c.moveTo(o.x, o.y); c.lineTo(o.x + i * 22, o.y - 8 + k * 9); c.stroke(); }
          circ(c, o.x - 5, o.y - 3, 3, "#fff"); circ(c, o.x + 5, o.y - 3, 3, "#fff"); }
        else if (o.bird) { c.fillStyle = "#7A5CFA"; c.beginPath(); c.ellipse(o.x, o.y, 20, 13, 0, 0, 7); c.fill(); c.fillStyle = "#FF8A1F"; c.beginPath(); c.moveTo(o.x - 20, o.y); c.lineTo(o.x - 30, o.y + 3); c.lineTo(o.x - 20, o.y + 6); c.fill(); circ(c, o.x - 10, o.y - 4, 3, "#fff"); }
        else { c.fillStyle = "#8A5A35"; rr(c, o.x - 6, o.y, 12, H, 4); } });
      const b = g.b; c.save(); c.translate(b.x, b.y); c.rotate(Math.max(-0.4, Math.min(0.6, b.vy / 700)));
      c.fillStyle = "rgba(223,243,255,.9)"; c.beginPath(); c.ellipse(-4, -14 - Math.abs(Math.sin(g.t * 40)) * 5, 10, 7, 0, 0, 7); c.ellipse(8, -14 - Math.abs(Math.cos(g.t * 40)) * 5, 10, 7, 0, 0, 7); c.fill();
      c.fillStyle = "#FFC93C"; c.beginPath(); c.ellipse(0, 0, 18, 13, 0, 0, 7); c.fill(); c.fillStyle = "#1D2A5B"; c.fillRect(-6, -12, 5, 24); c.fillRect(4, -12, 5, 24);
      circ(c, 14, -3, 3, "#1D2A5B"); c.restore();
    },
  });
});

// ------------------------------------------------------------------ 5. Tungi o'rmon
const NIGHT = [["Boyo'g'li", (c, x, y) => { c.fillStyle = "#B07A4F"; c.beginPath(); c.ellipse(x, y, 22, 28, 0, 0, 7); c.fill(); circ(c, x - 9, y - 8, 9, "#FFE66D"); circ(c, x + 9, y - 8, 9, "#FFE66D"); circ(c, x - 9, y - 8, 4, "#1D2A5B"); circ(c, x + 9, y - 8, 4, "#1D2A5B"); c.fillStyle = "#FF8A1F"; c.beginPath(); c.moveTo(x - 4, y); c.lineTo(x + 4, y); c.lineTo(x, y + 7); c.fill(); }],
  ["Tulki", (c, x, y) => { c.fillStyle = "#FF8A1F"; c.beginPath(); c.moveTo(x - 22, y - 20); c.lineTo(x - 12, y - 4); c.lineTo(x + 12, y - 4); c.lineTo(x + 22, y - 20); c.lineTo(x + 16, y + 6); c.lineTo(x, y + 20); c.lineTo(x - 16, y + 6); c.fill(); circ(c, x - 7, y, 3, "#1D2A5B"); circ(c, x + 7, y, 3, "#1D2A5B"); circ(c, x, y + 15, 3, "#1D2A5B"); }],
  ["Tipratikan", (c, x, y) => { c.fillStyle = "#6B4423"; c.beginPath(); for (let i = 0; i <= 8; i++) { const a = Math.PI + i * Math.PI / 8; c.lineTo(x + Math.cos(a) * (i % 2 ? 22 : 30), y + Math.sin(a) * (i % 2 ? 18 : 26)); } c.fill(); c.fillStyle = "#E8B07A"; c.beginPath(); c.ellipse(x + 20, y - 2, 12, 9, 0, 0, 7); c.fill(); circ(c, x + 24, y - 4, 2.5, "#1D2A5B"); circ(c, x + 31, y, 2.5, "#1D2A5B"); }],
  ["Quyon", (c, x, y) => { c.fillStyle = "#F4F1FF"; c.beginPath(); c.ellipse(x - 7, y - 26, 5, 14, 0, 0, 7); c.ellipse(x + 7, y - 26, 5, 14, 0, 0, 7); c.fill(); circ(c, x, y, 18, "#F4F1FF"); circ(c, x - 6, y - 3, 3, "#1D2A5B"); circ(c, x + 6, y - 3, 3, "#1D2A5B"); circ(c, x, y + 5, 3, "#FF9AA8"); }],
  ["Yaltiroq qo'ng'iz", (c, x, y) => { circ(c, x, y, 18, "rgba(255,240,120,.45)"); circ(c, x, y, 8, "#FFF27A"); c.fillStyle = "#1D2A5B"; c.beginPath(); c.ellipse(x, y - 9, 6, 5, 0, 0, 7); c.fill(); }]];
reg("tungi", "Tungi o'rmon", "aql", "4–9 yosh", "#141B3D", "#E3E6F5", "#0B1238", ICO('<rect width="60" height="60" rx="12" fill="#1D2A5B"/><circle cx="30" cy="30" r="18" fill="#FFE66D" opacity=".35"/><circle cx="25" cy="27" r="6" fill="#FFE66D"/><circle cx="37" cy="27" r="6" fill="#FFE66D"/><circle cx="25" cy="27" r="2.5" fill="#1D2A5B"/><circle cx="37" cy="27" r="2.5" fill="#1D2A5B"/>'), () => {
  arcadeView(GBY.tungi, hud("0 / 5"), "Barmog'ingni sur — chiroq yonadi<br><small>Yashiringan hayvonni ko'rsang, bos!</small>");
  arcade({id: "tungi", stars: (s) => (s >= 5 ? 3 : s >= 3 ? 2 : s >= 1 ? 1 : 0),
    init(g) { g.an = NIGHT.map((a, i) => ({k: i, x: 50 + rnd(g.W - 100), y: 90 + (i * (g.H - 180)) / 5 + rnd(40), found: false})); Object.assign(g, {lx: g.W / 2, ly: g.H / 2, left: 30}); },
    drag(g, x, y) { g.lx = x; g.ly = y; },
    tap(g, x, y) { g.lx = x; g.ly = y; const a = g.an.find((q) => !q.found && Math.hypot(q.x - x, q.y - y) < 40);
      if (a) { a.found = true; g.score++; sfx.ok(); haptic("ok"); g.say = NIGHT[a.k][0] + " topildi!"; g.sayT = 1.5; if (g.score >= 5) g.finish(true); } },
    step(g, dt) { g.left = Math.max(0, 30 - g.t); if (g.sayT) g.sayT = Math.max(0, g.sayT - dt); if (g.left <= 0) g.finish(g.score >= 3); setTxt("gsc", `${g.score} / 5 · ${Math.ceil(g.left)}s`); },
    draw(g, c) {
      const {W, H} = g;
      c.fillStyle = "#24305E"; c.fillRect(0, 0, W, H);
      c.fillStyle = "#1B5E3B"; for (let i = 0; i < 6; i++) { const x = i * W / 5; c.beginPath(); c.moveTo(x - 50, H); c.lineTo(x, H * 0.25 + (i % 2) * 60); c.lineTo(x + 50, H); c.fill(); }
      g.an.forEach((a) => { NIGHT[a.k][1](c, a.x, a.y); if (a.found) { c.strokeStyle = "#3BB273"; c.lineWidth = 4; c.beginPath(); c.arc(a.x, a.y, 36, 0, 7); c.stroke(); } });
      c.save(); c.fillStyle = "rgba(5,8,25,.94)"; c.beginPath(); c.rect(0, 0, W, H); c.arc(g.lx, g.ly, 70, 0, Math.PI * 2, true); c.fill("evenodd");
      const gr = c.createRadialGradient(g.lx, g.ly, 40, g.lx, g.ly, 74); gr.addColorStop(0, "rgba(5,8,25,0)"); gr.addColorStop(1, "rgba(5,8,25,.94)");
      c.fillStyle = gr; c.beginPath(); c.arc(g.lx, g.ly, 74, 0, 7); c.fill(); c.restore();
      g.an.forEach((a) => { if (a.found) NIGHT[a.k][1](c, a.x, a.y); });
      if (g.sayT) { c.fillStyle = "#fff"; rr(c, W / 2 - 110, 20, 220, 40, 20); c.fillStyle = "#1D2A5B"; c.font = "800 18px Bal, sans-serif"; c.textAlign = "center"; c.fillText(g.say, W / 2, 47); c.textAlign = "start"; }
    },
  });
});

// ------------------------------------------------------------------ 6. Dinozavr yugurishi
reg("dino", "Dinozavr yugurishi", "harakat", "4–10 yosh", "#FFE6B3", "#FFF1D6", "#C97500", ICO('<path d="M14 44 V30 Q14 16 30 16 H40 Q48 16 48 24 V30 H36 V44 H30 V36 H22 V44 Z" fill="#3BB273"/><circle cx="40" cy="22" r="2.5" fill="#1D2A5B"/><path d="M14 34 L4 40 L14 38 Z" fill="#3BB273"/>'), () => {
  arcadeView(GBY.dino, hud("0 m"), "Bos — dinozavr sakraydi!");
  arcade({id: "dino", unit: " m", stars: (s) => (s >= 400 ? 3 : s >= 200 ? 2 : s >= 60 ? 1 : 0),
    init(g) { g.gy = g.H - 110; Object.assign(g, {d: {x: 50, y: g.gy - 64, w: 60, h: 64, vy: 0, on: true}, obs: [], sp: 260, next: 1.3, cl: 0}); },
    tap(g) { if (g.d.on) { g.d.vy = -820; g.d.on = false; tone(400, 0.12, "square", 0.08, 0, 700); } },
    step(g, dt) {
      const d = g.d; g.sp = Math.min(600, g.sp + dt * 10); g.score += dt * g.sp / 40; g.cl += dt * g.sp;
      d.vy += 2400 * dt; d.y += d.vy * dt; if (d.y >= g.gy - d.h) { d.y = g.gy - d.h; d.vy = 0; d.on = true; }
      g.next -= dt; if (g.next <= 0) { const fly = g.t > 15 && Math.random() < 0.3;
        g.obs.push(fly ? {x: g.W + 20, y: g.gy - 70 - rnd(20), w: 50, h: 26, fly} : {x: g.W + 20, y: g.gy - 56, w: 30 + rnd(14), h: 56}); g.next = 0.9 + Math.random() * 1.1 - Math.min(0.3, g.t / 150); }
      g.obs.forEach((o) => { o.x -= g.sp * dt * (o.fly ? 1.2 : 1); }); g.obs = g.obs.filter((o) => o.x > -70);
      const box = {x: d.x + 12, y: d.y + 8, w: d.w - 24, h: d.h - 10};
      if (g.obs.some((o) => hit(box, {x: o.x + 4, y: o.y + 4, w: o.w - 8, h: o.h - 6}))) g.finish();
      setTxt("gsc", `${Math.floor(g.score)} m`);
    },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#FFE6B3"; c.fillRect(0, 0, W, H); circ(c, W - 70, 80, 36, "#FFB347");
      c.fillStyle = "#F4C27A"; c.beginPath(); c.moveTo(0, g.gy); for (let x = 0; x <= W; x += 30) c.lineTo(x, g.gy - 50 - Math.sin((x + g.cl * 0.3) / 60) * 24); c.lineTo(W, g.gy); c.fill();
      c.fillStyle = "#D99A4E"; c.fillRect(0, g.gy, W, H - g.gy); c.fillStyle = "#B57A35"; for (let x = -(g.cl % 40); x < W; x += 40) rr(c, x, g.gy + 18, 18, 5, 2);
      g.obs.forEach((o) => { if (o.fly) { c.fillStyle = "#7A5CFA"; c.beginPath(); c.moveTo(o.x, o.y + 13); c.lineTo(o.x + 25, o.y + (Math.sin(g.t * 14) > 0 ? -6 : 26)); c.lineTo(o.x + 50, o.y + 13); c.fill(); circ(c, o.x + 8, o.y + 10, 8, "#7A5CFA"); }
        else { c.fillStyle = "#2E9E60"; rr(c, o.x + o.w / 2 - 8, o.y, 16, o.h, 8); rr(c, o.x, o.y + 18, 10, 22, 5); rr(c, o.x + o.w - 10, o.y + 10, 10, 22, 5); } });
      const d = g.d, lg = d.on ? Math.sin(g.t * 22) * 6 : 0; c.fillStyle = "#3BB273";
      rr(c, d.x + 14, d.y + 50 + Math.max(0, lg), 10, 14, 4); rr(c, d.x + 32, d.y + 50 + Math.max(0, -lg), 10, 14, 4);
      c.beginPath(); c.ellipse(d.x + 28, d.y + 38, 22, 18, 0, 0, 7); c.fill(); c.beginPath(); c.moveTo(d.x + 8, d.y + 34); c.lineTo(d.x - 10, d.y + 46); c.lineTo(d.x + 10, d.y + 46); c.fill();
      rr(c, d.x + 30, d.y, 34, 26, 10); circ(c, d.x + 52, d.y + 9, 3.5, "#1D2A5B"); c.fillStyle = "#fff"; c.fillRect(d.x + 48, d.y + 20, 14, 3);
      c.fillStyle = "#2A8A55"; for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(d.x + 14 + i * 9, d.y + 22); c.lineTo(d.x + 18 + i * 9, d.y + 14); c.lineTo(d.x + 22 + i * 9, d.y + 22); c.fill(); }
    },
  });
});

// ------------------------------------------------------------------ 7. Sharchani balandlat
reg("balandlat", "Sharchani balandlat", "harakat", "4–9 yosh", "#BFE6FF", "#DFF3FF", "#2B9FCC", ICO('<ellipse cx="30" cy="22" rx="18" ry="20" fill="#FF4D5E"/><path d="M30 2 V42" stroke="#FFC93C" stroke-width="4"/><path d="M22 42 L26 50 H34 L38 42" stroke="#8A5A35" stroke-width="2" fill="none"/><rect x="24" y="50" width="12" height="8" rx="2" fill="#B5651D"/>'), () => {
  arcadeView(GBY.balandlat, hud("0 m"), "Pastdagi shamolchilarni bos<br><small>Sharcha tikonlarga tegmasin!</small>");
  arcade({id: "balandlat", unit: " m", stars: (s) => (s >= 300 ? 3 : s >= 150 ? 2 : s >= 40 ? 1 : 0),
    init(g) { Object.assign(g, {b: {x: g.W / 2, y: g.H * 0.55, vx: 0, vy: 0}, cam: 0, top: 0, sp: []}); for (let i = 1; i < 60; i++) g.sp.push({y: -i * 170, x: Math.random() < 0.5 ? 0 : 1, w: 90 + rnd(70)}); },
    tap(g, x) { const b = g.b, z = x < g.W / 3 ? -1 : x > g.W * 2 / 3 ? 1 : 0; b.vy = -330; b.vx += -z * 120; g.puff = {z, t: 0.3}; tone(220, 0.15, "sawtooth", 0.05, 0, 120); },
    step(g, dt) {
      const b = g.b; b.vy += 260 * dt; b.vy = Math.min(b.vy, 170); b.vx *= 1 - dt * 1.5; b.x += b.vx * dt; b.y += b.vy * dt;
      if (b.x < 26) { b.x = 26; b.vx = 40; } if (b.x > g.W - 26) { b.x = g.W - 26; b.vx = -40; }
      const target = b.y - g.H * 0.55; if (target < g.cam) g.cam += (target - g.cam) * Math.min(1, dt * 3);
      if (b.y - g.cam > g.H - 90) g.finish();
      g.score = Math.max(g.score, Math.floor(-(b.y - g.H * 0.55) / 8)); if (g.puff) g.puff.t -= dt;
      for (const s of g.sp) { const sx = s.x ? g.W - s.w : 0; if (b.y - 30 < s.y + 22 && b.y + 26 > s.y && b.x + 20 > sx && b.x - 20 < sx + s.w) { g.finish(); break; } }
      setTxt("gsc", `${g.score} m`);
    },
    draw(g, c) {
      const {W, H} = g; const sky = Math.min(1, g.score / 400); c.fillStyle = `rgb(${191 - sky * 120},${230 - sky * 140},255)`; c.fillRect(0, 0, W, H);
      c.save(); c.translate(0, -g.cam);
      g.sp.forEach((s) => { if (s.y - g.cam < -60 || s.y - g.cam > H + 40) return; const sx = s.x ? W - s.w : 0;
        c.fillStyle = "#E8E4F7"; rr(c, sx, s.y, s.w, 22, 11); c.fillStyle = "#8A8F9C";
        for (let i = 0; i < s.w; i += 14) { c.beginPath(); c.moveTo(sx + i, s.y + 22); c.lineTo(sx + i + 7, s.y + 34); c.lineTo(sx + i + 14, s.y + 22); c.fill(); } });
      const b = g.b; c.strokeStyle = "#8A5A35"; c.lineWidth = 2; c.beginPath(); c.moveTo(b.x - 14, b.y + 12); c.lineTo(b.x - 8, b.y + 34); c.moveTo(b.x + 14, b.y + 12); c.lineTo(b.x + 8, b.y + 34); c.stroke();
      c.fillStyle = "#FF4D5E"; c.beginPath(); c.ellipse(b.x, b.y - 8, 26, 30, 0, 0, 7); c.fill(); c.fillStyle = "#FFC93C"; c.fillRect(b.x - 4, b.y - 38, 8, 58);
      c.fillStyle = "#B5651D"; rr(c, b.x - 10, b.y + 32, 20, 14, 3); c.restore();
      ["#23C4E8", "#7A5CFA", "#23C4E8"].forEach((col, i) => { const x = W * (i + 0.5) / 3; c.fillStyle = col; rr(c, x - 34, H - 64, 68, 50, 16);
        c.strokeStyle = "#fff"; c.lineWidth = 4; c.beginPath(); c.arc(x, H - 39, 14, 0, 7); c.stroke();
        if (g.puff && g.puff.t > 0 && g.puff.z === i - 1) { c.fillStyle = "rgba(255,255,255,.7)"; [0, 1, 2].forEach((k) => circ(c, x + (k - 1) * 12, H - 80 - k * 10, 8, "rgba(255,255,255,.7)")); } });
    },
  });
});

// ------------------------------------------------------------------ 8. Kubikni joyla (Block Fit)
const PIECES = [[[0, 0]], [[0, 0], [1, 0]], [[0, 0], [0, 1]], [[0, 0], [1, 0], [2, 0]], [[0, 0], [0, 1], [0, 2]], [[0, 0], [1, 0], [0, 1], [1, 1]],
  [[0, 0], [0, 1], [1, 1]], [[1, 0], [0, 1], [1, 1]], [[0, 0], [1, 0], [2, 0], [1, 1]], [[0, 0], [1, 0], [0, 1]]];
const PCOL = ["#FF4D5E", "#FFB020", "#3BB273", "#2E86DE", "#7A5CFA", "#E5487F", "#23C4E8"];
const BN = 7;
reg("blokfit", "Kubikni joyla", "aql", "5–10 yosh", "#EDE7FF", "#EDE7FF", "#5536D6", ICO('<g><rect x="6" y="6" width="22" height="22" rx="5" fill="#FF4D5E"/><rect x="32" y="6" width="22" height="22" rx="5" fill="#FFB020"/><rect x="6" y="32" width="22" height="22" rx="5" fill="#3BB273"/><rect x="32" y="32" width="22" height="22" rx="5" fill="#2E86DE"/></g>'), () => {
  S.grid = Array.from({length: BN * BN}, () => null); S.q = []; S.sel = 0; S.pts = 0; bfRefill(); drawBF();
});
function bfRefill() { S.q = [0, 1, 2].map(() => ({p: PIECES[rnd(PIECES.length)], c: PCOL[rnd(PCOL.length)]})); S.sel = 0; }
const bfFits = (p, cx, cy) => p.every(([x, y]) => { const X = cx + x, Y = cy + y; return X < BN && Y < BN && !S.grid[Y * BN + X]; });
const bfAny = (p) => { for (let y = 0; y < BN; y++) for (let x = 0; x < BN; x++) if (bfFits(p, x, y)) return true; return false; };
function drawBF() {
  const g = GBY.blokfit;
  view(bar(g, hud(`${S.pts}`)) + `<div class="gx-h b">Shaklni tanla, keyin katakni bos</div>
    <div class="g-bf">${S.grid.map((c, i) => `<button data-act="bfcell" data-i="${i}" aria-label="Katak ${i + 1}" style="${c ? `background:${c};box-shadow:inset 0 -5px 0 rgba(0,0,0,.18)` : ""}"></button>`).join("")}</div>
    <div class="gx-fill"></div><div class="g-tray"><div class="g-bfq">${S.q.map((q, i) => q ? `<button class="${S.sel === i ? "on" : ""}" data-act="bfsel" data-i="${i}" aria-label="${i + 1}-shakl">
      <span style="grid-template-columns:repeat(${Math.max(...q.p.map((v) => v[0])) + 1},18px)">${Array.from({length: (Math.max(...q.p.map((v) => v[1])) + 1) * (Math.max(...q.p.map((v) => v[0])) + 1)}, (_, k) => {
        const w = Math.max(...q.p.map((v) => v[0])) + 1, x = k % w, y = Math.floor(k / w); return `<i style="${q.p.some((v) => v[0] === x && v[1] === y) ? `background:${q.c}` : "visibility:hidden"}"></i>`; }).join("")}</span></button>` : "<span></span>").join("")}</div></div>`);
}
ACT.bfsel = (el) => { S.sel = +el.dataset.i; haptic(); drawBF(); };
ACT.bfcell = (el) => {
  const q = S.q[S.sel]; if (!q) return;
  const i = +el.dataset.i, cx = i % BN, cy = Math.floor(i / BN);
  if (!bfFits(q.p, cx, cy)) { wrong(el); return; }
  q.p.forEach(([x, y]) => { S.grid[(cy + y) * BN + cx + x] = q.c; }); S.pts += q.p.length; sfx.tap(); haptic("hit");
  S.q[S.sel] = null;
  const full = []; for (let r = 0; r < BN; r++) if ([...Array(BN)].every((_, k) => S.grid[r * BN + k])) for (let k = 0; k < BN; k++) full.push(r * BN + k);
  for (let k = 0; k < BN; k++) if ([...Array(BN)].every((_, r) => S.grid[r * BN + k])) for (let r = 0; r < BN; r++) full.push(r * BN + k);
  if (full.length) { new Set(full).forEach((j) => { S.grid[j] = null; }); S.pts += full.length * 2; sfx.win(); addStar(1); }
  if (S.q.every((x) => !x)) bfRefill(); else S.sel = S.q.findIndex((x) => x);
  drawBF();
  if (!S.q.some((x) => x && bfAny(x.p))) { later(() => { yay(`Joy qolmadi! ${S.pts} ochko`, S.pts >= 60 ? 2 : 1); later(START.blokfit, 1600); }, 300); }
};

// ------------------------------------------------------------------ 9. Imorat qur
reg("imorat", "Imorat qur", "harakat", "4–10 yosh", "#FFE1C7", "#FFE1C7", "#E86A2C", ICO('<rect x="16" y="40" width="28" height="14" rx="3" fill="#2E86DE"/><rect x="18" y="26" width="24" height="14" rx="3" fill="#FFB020"/><rect x="21" y="12" width="20" height="14" rx="3" fill="#FF4D5E"/><path d="M30 2 V12" stroke="#1D2A5B" stroke-width="2"/>'), () => {
  arcadeView(GBY.imorat, hud("0 qavat"), "Bos — blok tushadi<br><small>Pastdagisiga aniq tushir!</small>");
  arcade({id: "imorat", unit: " qavat", stars: (s) => (s >= 20 ? 3 : s >= 10 ? 2 : s >= 4 ? 1 : 0),
    init(g) { const w = Math.min(200, g.W * 0.55); g.tower = [{x: (g.W - w) / 2, w, c: "#8A5A35"}]; Object.assign(g, {bw: w, bx: 0, dir: 1, sp: 160, fall: null, cam: 0, bh: 34}); },
    tap(g) { if (g.fall) return; g.fall = {x: g.bx, y: 70, w: g.bw}; },
    step(g, dt) {
      const top = g.tower[g.tower.length - 1], baseY = g.H - 60 - g.tower.length * g.bh;
      if (!g.fall) { g.bx += g.dir * g.sp * dt; if (g.bx < 0) { g.bx = 0; g.dir = 1; } if (g.bx + g.bw > g.W) { g.bx = g.W - g.bw; g.dir = -1; } }
      else { const f = g.fall; f.y += 900 * dt; const land = baseY - g.cam;
        if (f.y >= land) { const L = Math.max(f.x, top.x), R = Math.min(f.x + f.w, top.x + top.w);
          if (R - L <= 6) { g.finish(); return; }
          let nx = L, nw = R - L; if (Math.abs(f.x - top.x) < 6) { nx = top.x; nw = top.w; sfx.ok(); g.score++; } else tone(400, 0.08, "square", 0.08);
          g.tower.push({x: nx, w: nw, c: PCOL[g.tower.length % PCOL.length]}); g.score++; g.bw = nw; g.fall = null; g.sp = Math.min(380, g.sp + 12); } }
      const want = Math.max(0, g.tower.length * g.bh - (g.H * 0.5)); g.cam += (want - g.cam) * Math.min(1, dt * 4);
      setTxt("gsc", `${g.tower.length - 1} qavat`);
    },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#FFE1C7"; c.fillRect(0, 0, W, H); circ(c, W - 60, 120 + g.cam * 0.2, 30, "#FFC93C");
      c.save(); c.translate(0, g.cam);
      c.fillStyle = "#5BC06A"; c.fillRect(0, H - 60, W, 400);
      g.tower.forEach((b, i) => { const y = H - 60 - (i + 1) * g.bh; c.fillStyle = b.c; rr(c, b.x, y, b.w, g.bh - 2, 6);
        c.fillStyle = "rgba(255,255,255,.6)"; for (let k = b.x + 10; k < b.x + b.w - 14; k += 26) rr(c, k, y + 9, 12, 12, 2); });
      c.restore();
      c.strokeStyle = "#1D2A5B"; c.lineWidth = 3; c.beginPath(); c.moveTo(0, 30); c.lineTo(W, 30); c.stroke();
      if (!g.fall) { c.beginPath(); c.moveTo(g.bx + g.bw / 2, 30); c.lineTo(g.bx + g.bw / 2, 70); c.stroke(); c.fillStyle = PCOL[g.tower.length % PCOL.length]; rr(c, g.bx, 70, g.bw, g.bh - 2, 6); }
      else { c.fillStyle = PCOL[g.tower.length % PCOL.length]; rr(c, g.fall.x, g.fall.y, g.fall.w, g.bh - 2, 6); }
    },
  });
});

// ------------------------------------------------------------------ 10. Shaklni birlashtir (nuqtadan-nuqtaga)
const DOTS = [
  {n: "Yulduz", c: "#FFC93C", p: [[150, 20], [185, 105], [278, 110], [205, 168], [232, 260], [150, 208], [68, 260], [95, 168], [22, 110], [115, 105]]},
  {n: "Yurak", c: "#FF4D5E", p: [[150, 85], [190, 40], [245, 45], [275, 100], [250, 165], [150, 260], [50, 165], [25, 100], [55, 45], [110, 40]]},
  {n: "Uycha", c: "#2E86DE", p: [[60, 260], [60, 140], [150, 40], [240, 140], [240, 260], [180, 260], [180, 190], [120, 190], [120, 260]]},
  {n: "Baliq", c: "#FF8A1F", p: [[30, 150], [90, 80], [170, 70], [230, 130], [285, 80], [275, 150], [285, 220], [230, 170], [170, 230], [90, 220]]},
  {n: "Olmos", c: "#7A5CFA", p: [[150, 20], [250, 110], [150, 270], [50, 110]]},
];
reg("nuqta", "Shaklni birlashtir", "aql", "3–8 yosh", "#1D2A5B", "#E3E6F5", "#0B1238", ICO('<rect width="60" height="60" rx="12" fill="#1D2A5B"/><path d="M14 44 L30 12 L46 44 Z" fill="none" stroke="#FFC93C" stroke-width="3"/><g fill="#fff"><circle cx="14" cy="44" r="4"/><circle cx="30" cy="12" r="4"/><circle cx="46" cy="44" r="4"/></g>'), () => {
  S.sh = S.sh === undefined ? 0 : (S.sh + 1) % DOTS.length; S.k = 1; drawDots();
});
function drawDots(done) {
  const g = GBY.nuqta, d = DOTS[S.sh], pts = d.p, k = S.k;
  const path = pts.slice(0, k).map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join(" ") + (done ? " Z" : "");
  view(bar(g, hud(`${d.n}`)) + `<div class="gx-h b" style="color:#fff;text-align:center">${done ? `${d.n} tayyor!` : `Nuqtalarni tartib bilan bos: ${k + 1 > pts.length ? 1 : k + 1}`}</div>
    <div class="g-dots"><svg viewBox="0 0 300 290" role="img" aria-label="${d.n} shakli">
      ${done ? `<path d="${path}" fill="${d.c}" class="g-fillin"/>` : ""}
      <path d="${path}" fill="none" stroke="${d.c}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
      ${!done ? pts.map(([x, y], i) => `<g data-act="dot" data-i="${i}" style="cursor:pointer">
        <circle cx="${x}" cy="${y}" r="22" fill="transparent"/><circle cx="${x}" cy="${y}" r="${i === k % pts.length ? 13 : 10}" fill="${i < k ? d.c : "#fff"}" class="${i === k % pts.length ? "g-next" : ""}"/>
        <text x="${x}" y="${y - 17}" text-anchor="middle" font-family="Bal,sans-serif" font-size="15" font-weight="800" fill="#fff">${i + 1}</text></g>`).join("") : ""}</svg></div>
    <div class="gx-fill"></div>${done ? `<div class="g-tray" style="text-align:center"><button class="gx-btn b" data-act="reset">Keyingi shakl</button></div>` : ""}`);
}
ACT.dot = (el) => {
  const pts = DOTS[S.sh].p, i = +el.dataset.i, need = S.k % pts.length;
  if (i !== need) { wrong(el.closest(".g-dots")); return; }
  tone(400 + S.k * 60, 0.12, "triangle", 0.16); haptic("hit");
  if (i === 0) { drawDots(true); yay(`${DOTS[S.sh].n}!`); return; }
  S.k++; drawDots();
};

// ------------------------------------------------------------------ 11. Muvozanat
reg("muvozanat", "Muvozanat", "aql", "4–9 yosh", "#E8F3FF", "#E8F3FF", "#2E86DE", ICO('<path d="M30 10 V50" stroke="#8A5A35" stroke-width="4"/><path d="M8 18 H52" stroke="#1D2A5B" stroke-width="4" stroke-linecap="round"/><path d="M4 30 Q12 40 20 30 Z M40 30 Q48 40 56 30 Z" fill="#FFC93C"/><rect x="20" y="50" width="20" height="6" rx="3" fill="#8A5A35"/>'), () => {
  S.toy = 2 + rnd(9); S.right = []; S.lvl = S.lvl || 1; drawBal();
});
function drawBal() {
  const g = GBY.muvozanat, R = S.right.reduce((a, b) => a + b, 0), diff = R - S.toy, ang = Math.max(-18, Math.min(18, diff * 3));
  const ok = diff === 0;
  view(bar(g, hud(`${R} / ${S.toy} kg`)) + speech(ok ? "Muvozanat! Barakalla!" : diff < 0 ? `O'ng tomon yengil — yana ${-diff} kg kerak` : `Ko'p bo'ldi! ${diff} kg ortiqcha`) +
    `<div class="g-scale"><svg viewBox="0 0 320 260" role="img" aria-label="Tarozi">
      <rect x="150" y="60" width="20" height="170" rx="6" fill="#8A5A35"/><rect x="100" y="226" width="120" height="20" rx="10" fill="#6B4423"/>
      <g style="transform:rotate(${ang}deg);transform-origin:160px 64px;transition:transform .5s cubic-bezier(.3,1.5,.5,1)">
        <rect x="30" y="58" width="260" height="12" rx="6" fill="#1D2A5B"/><circle cx="160" cy="64" r="10" fill="#FFC93C"/>
        <g style="transform:rotate(${-ang}deg);transform-origin:50px 64px;transition:transform .5s"><path d="M50 64 L20 120 M50 64 L80 120" stroke="#5C6A99" stroke-width="2"/><path d="M10 120 Q50 150 90 120 Z" fill="#FFC93C"/>
          <g transform="translate(28 72)"><circle cx="22" cy="10" r="9" fill="#B07A4F"/><circle cx="8" cy="4" r="5" fill="#B07A4F"/><circle cx="36" cy="4" r="5" fill="#B07A4F"/><ellipse cx="22" cy="34" rx="16" ry="14" fill="#B07A4F"/><circle cx="19" cy="9" r="1.6" fill="#1D2A5B"/><circle cx="25" cy="9" r="1.6" fill="#1D2A5B"/></g>
          <text x="50" y="146" text-anchor="middle" font-family="Bal,sans-serif" font-weight="800" font-size="15" fill="#1D2A5B">${S.toy} kg</text></g>
        <g style="transform:rotate(${-ang}deg);transform-origin:270px 64px;transition:transform .5s"><path d="M270 64 L240 120 M270 64 L300 120" stroke="#5C6A99" stroke-width="2"/><path d="M230 120 Q270 150 310 120 Z" fill="#FFC93C"/>
          ${S.right.map((w, i) => `<rect x="${244 + (i % 3) * 18}" y="${100 - Math.floor(i / 3) * 16}" width="16" height="15" rx="3" fill="${{1: "#3BB273", 2: "#2E86DE", 5: "#FF4D5E"}[w]}"/><text x="${252 + (i % 3) * 18}" y="${112 - Math.floor(i / 3) * 16}" text-anchor="middle" font-size="10" font-weight="800" fill="#fff" font-family="Bal,sans-serif">${w}</text>`).join("")}</g>
      </g></svg></div><div class="gx-fill"></div>
    <div class="g-tray"><div class="g-opts" style="grid-template-columns:repeat(4,1fr)">
      ${[[1, "#3BB273"], [2, "#2E86DE"], [5, "#FF4D5E"]].map(([w, c]) => `<button class="g-opt" data-act="bw" data-w="${w}" aria-label="${w} kilogramm"><span style="background:${c};height:34px;width:44px;display:flex;align-items:center;justify-content:center;color:#fff;font:800 18px Bal,sans-serif">${w}</span>${w} kg</button>`).join("")}
      <button class="g-opt" data-act="bundo" aria-label="Oxirgisini olib tashlash"><svg viewBox="0 0 24 24" fill="none" stroke="#1D2A5B" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg>Olish</button></div></div>`);
}
ACT.bw = (el) => { if (S.right.length >= 9) return; S.right.push(+el.dataset.w); tone(300 + S.right.length * 30, 0.1, "triangle", 0.12); haptic();
  drawBal(); if (S.right.reduce((a, b) => a + b, 0) === S.toy) { yay("Muvozanat!"); later(START.muvozanat, 1600); } };
ACT.bundo = () => { S.right.pop(); sfx.tap(); drawBal(); };

// ------------------------------------------------------------------ 12. Sehrli rang palitrasi
const PRIM = {qizil: "#FF3B3B", sariq: "#FFD21F", kok: "#2E6FDE", oq: "#FFFFFF"};
const MIX = {"qizil+sariq": ["To'q sariq", "#FF8A1F"], "kok+sariq": ["Yashil", "#3BB273"], "kok+qizil": ["Binafsha", "#8A4FD6"],
  "oq+qizil": ["Pushti", "#FF9AC1"], "kok+oq": ["Havorang", "#8FD3FF"], "oq+sariq": ["Och sariq", "#FFF1A6"]};
reg("palitra", "Sehrli rang palitrasi", "ijod", "4–8 yosh", "#FFF6E0", "#FFF6E0", "#E0A500", ICO('<circle cx="30" cy="30" r="24" fill="#fff" stroke="#E2DCCF" stroke-width="2"/><circle cx="20" cy="22" r="6" fill="#FF3B3B"/><circle cx="34" cy="18" r="6" fill="#FFD21F"/><circle cx="42" cy="30" r="6" fill="#2E6FDE"/><circle cx="24" cy="38" r="6" fill="#3BB273"/>'), () => {
  const keys = Object.keys(MIX); S.target = keys[rnd(keys.length)]; S.bowl = []; drawPal();
});
function drawPal(res) {
  const g = GBY.palitra, [tn, tc] = MIX[S.target], bowlCol = S.bowl.length === 2 ? (MIX[[...S.bowl].sort().join("+")] || ["", "#9C6B3E"])[1] : S.bowl.length ? PRIM[S.bowl[0]] : "#F1EEE6";
  view(bar(g, hud(`${played.palitra || 0} ★`)) + speech(res || `«${tn}» rangini yasaymiz! Qaysi ikki rang kerak?`) +
    `<div class="g-mixrow"><div class="g-target"><span style="background:${tc}"></span><b class="b">${tn}</b></div>
      <svg class="g-bowl" viewBox="0 0 160 110" aria-label="Aralashtirish kosasi" role="img"><ellipse cx="80" cy="30" rx="72" ry="16" fill="#E8E2D2"/><path d="M8 30 Q16 104 80 104 Q144 104 152 30 Z" fill="#fff" stroke="#E2DCCF" stroke-width="3"/>
      <ellipse cx="80" cy="34" rx="62" ry="12" fill="${bowlCol}" style="transition:fill .5s"/></svg></div>
    <div class="gx-fill"></div><div class="g-tray"><div class="hint">Bo'yoq tubini bos — kosaga quyiladi</div><div class="g-opts" style="grid-template-columns:repeat(4,1fr)">
    ${Object.entries(PRIM).map(([k, c]) => `<button class="g-opt" data-act="pour" data-k="${k}" aria-label="${k}"><svg viewBox="0 0 48 48" aria-hidden="true"><rect x="14" y="4" width="20" height="10" rx="3" fill="#8A8F9C"/><path d="M10 14 H38 V40 Q24 48 10 40 Z" fill="${c}" stroke="#E2DCCF" stroke-width="2"/></svg>${k[0].toUpperCase() + k.slice(1)}</button>`).join("")}</div></div>`);
}
ACT.pour = (el) => {
  if (S.bowl.length >= 2 || S.lock) return;
  const k = el.dataset.k; if (S.bowl.includes(k)) { wrong(el); return; }
  S.bowl.push(k); tone(500 + S.bowl.length * 200, 0.2, "sine", 0.14, 0, 300); haptic();
  if (S.bowl.length < 2) { drawPal(); return; }
  const key = [...S.bowl].sort().join("+"), got = MIX[key];
  S.lock = true;
  if (key === S.target) { drawPal(`Ajoyib! ${got[0]} chiqdi!`); yay(got[0] + "!"); later(() => { S.lock = false; START.palitra(); }, 1700); }
  else { drawPal(`Bu ${got ? got[0].toLowerCase() : "boshqa rang"} bo'ldi. Qayta urinib ko'r!`); sfx.err(); later(() => { S.lock = false; S.bowl = []; drawPal(); }, 1800); }
};

// ------------------------------------------------------------------ 13. Barabanchi
const DRUMS = [["Katta baraban", "#FF4D5E", (c) => { voice(c, {type: "sine", f0: 120, f1: 40, dur: 0.35, vol: 0.6, lp: 400}); }],
  ["Kichik baraban", "#FFB020", (c) => { noise(c, 0.18, 0, 1800, 0.5); voice(c, {type: "triangle", f0: 220, f1: 160, dur: 0.12, vol: 0.2, lp: 2000}); }],
  ["Likopcha", "#3BB273", (c) => { noise(c, 0.06, 0, 8000, 0.35); }],
  ["Tom", "#2E86DE", (c) => { voice(c, {type: "sine", f0: 200, f1: 110, dur: 0.3, vol: 0.45, lp: 900}); }],
  ["Tarelka", "#7A5CFA", (c) => { noise(c, 0.9, 0, 6000, 0.3); }]];
reg("baraban", "Barabanchi", "musiqa", "2–8 yosh", "#2B1F4D", "#EDE7FF", "#5536D6", ICO('<ellipse cx="30" cy="36" rx="22" ry="14" fill="#FF4D5E"/><ellipse cx="30" cy="30" rx="22" ry="10" fill="#FFE1E5"/><path d="M12 10 L26 26 M48 10 L34 26" stroke="#B5651D" stroke-width="4" stroke-linecap="round"/>'), () => {
  S.rec = null; S.recOn = false; S.play = false; drawDrum();
});
function drawDrum() {
  const g = GBY.baraban;
  view(bar(g, hud(S.recOn ? "● Yozilmoqda" : S.rec ? `${S.rec.length} zarb` : "Erkin")) +
    `<div class="g-drums">${DRUMS.map(([n, c], i) => `<button class="g-pad${i === 0 ? " big" : ""}" data-act="drum" data-i="${i}" style="--c:${c}" aria-label="${n}"><span class="ring"></span><b class="b">${n}</b></button>`).join("")}</div>
    <div class="gx-fill"></div><div class="g-tray"><div class="g-opts" style="grid-template-columns:repeat(2,1fr)">
      <button class="g-opt${S.recOn ? " on" : ""}" data-act="drec"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="#FF4D5E"/></svg>${S.recOn ? "To'xtatish" : "Yozib olish"}</button>
      <button class="g-opt" data-act="dplay" ${S.rec && S.rec.length ? "" : "disabled"}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4 L20 12 L7 20 Z" fill="#3BB273"/></svg>Eshittirish</button></div></div>`);
}
function hitDrum(i, el) {
  const c = ctx(); if (c) DRUMS[i][2](c); haptic("hit");
  const b = el || document.querySelector(`[data-act="drum"][data-i="${i}"]`);
  if (b) { b.classList.remove("hit"); void b.offsetWidth; b.classList.add("hit"); }
}
ACT.drum = (el) => { const i = +el.dataset.i; hitDrum(i, el); if (S.recOn) S.rec.push([performance.now() - S.t0, i]); };
ACT.drec = () => { if (S.recOn) { S.recOn = false; if (S.rec.length >= 4) addStar(1); } else { S.recOn = true; S.rec = []; S.t0 = performance.now(); } drawDrum(); };
ACT.dplay = () => { if (!S.rec) return; S.rec.forEach(([t, i]) => later(() => hitDrum(i), t)); };

// ------------------------------------------------------------------ 14. Ovozli o'yin (nota qushchasi)
const P5 = [["Do", 523, "#FF4B3E"], ["Re", 587, "#FF8A1F"], ["Mi", 659, "#FFC21F"], ["Fa", 698, "#3BB273"], ["Sol", 784, "#2E86DE"]];
reg("pitch", "Ovozli o'yin", "musiqa", "3–8 yosh", "#E6DFFF", "#E6DFFF", "#5536D6", ICO('<g><rect x="6" y="34" width="8" height="20" rx="3" fill="#FF4B3E"/><rect x="18" y="24" width="8" height="30" rx="3" fill="#FFC21F"/><rect x="30" y="14" width="8" height="40" rx="3" fill="#3BB273"/><rect x="42" y="28" width="8" height="26" rx="3" fill="#2E86DE"/></g>'), () => {
  view(bar(GBY.pitch, hud("0")) + `<div class="g-can" id="gcan" style="margin-bottom:8px"><div class="g-hint b" id="ghint">Nota tugmalarini bos<br><small>Qushcha yulduzlarni yeydi</small></div><div class="g-over" id="gover" hidden></div></div>
    <div class="g-notes">${P5.map(([n, , c], i) => `<button class="b" data-act="pnote" data-i="${i}" style="background:${c}" aria-label="${n} notasi">${n}</button>`).join("")}</div>`);
  arcade({id: "pitch", stars: (s) => (s >= 30 ? 3 : s >= 15 ? 2 : s >= 5 ? 1 : 0),
    init(g) { Object.assign(g, {lane: 2, by: 0, st: [], next: 0.5, miss: 0}); g.by = laneY(g, 2); },
    step(g, dt) {
      g.by += (laneY(g, g.lane) - g.by) * Math.min(1, dt * 12);
      g.next -= dt; if (g.next <= 0) { g.st.push({x: g.W + 20, l: rnd(5)}); g.next = Math.max(0.7, 1.5 - g.t / 60); }
      const sp = 120 + Math.min(100, g.t * 2);
      g.st.forEach((s) => { s.x -= sp * dt; if (!s.got && Math.abs(s.x - 80) < 22 && s.l === g.lane) { s.got = true; g.score++; tone(P5[s.l][1] * 2, 0.1, "sine", 0.12); } });
      g.st.forEach((s) => { if (!s.got && !s.gone && s.x < 40) { s.gone = true; g.miss++; } });
      g.st = g.st.filter((s) => s.x > -30 && !s.got); if (g.miss >= 6) g.finish(g.score >= 10); setTxt("gsc", `${g.score} · ${6 - g.miss} ♥`);
    },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#2B1F4D"; c.fillRect(0, 0, W, H);
      P5.forEach(([, , col], i) => { const y = laneY(g, i); c.fillStyle = col + "33"; c.fillRect(0, y - 2, W, 4); c.fillStyle = col; rr(c, 6, y - 14, 10, 28, 5); });
      for (let i = 0; i < 18; i++) { const h = 10 + Math.abs(Math.sin(g.t * 6 + i)) * 40; c.fillStyle = "rgba(255,255,255,.08)"; rr(c, i * W / 18 + 2, H - h, W / 18 - 4, h, 3); }
      g.st.forEach((s) => STARP(c, s.x, laneY(g, s.l), 14, "#FFC93C"));
      const y = g.by; c.fillStyle = "#FFE14D"; c.beginPath(); c.ellipse(80, y, 22, 18, 0, 0, 7); c.fill(); circ(c, 88, y - 6, 6, "#fff"); circ(c, 90, y - 5, 3.5, "#1D2A5B");
      c.fillStyle = "#FF8A1F"; c.beginPath(); c.moveTo(100, y); c.lineTo(112, y + 3); c.lineTo(100, y + 7); c.fill();
      c.fillStyle = "#FFB020"; c.beginPath(); c.ellipse(72, y + 2 + Math.sin(g.t * 30) * 4, 10, 6, -0.4, 0, 7); c.fill();
    },
  });
});
const laneY = (g, i) => g.H * 0.12 + (4 - i) * (g.H * 0.76) / 4;
ACT.pnote = (el) => { const i = +el.dataset.i; tone(P5[i][1], 0.4, "triangle", 0.2); haptic("hit");
  const g = S.ag; if (!g || g.over) return; if (g.ready) { g.ready = false; const h = $("ghint"); if (h) h.style.opacity = "0"; } g.lane = i; };

// ------------------------------------------------------------------ 15. Sanashni o'rgan (raqamli pufaklar)
reg("raqam", "Sanashni o'rgan", "aql", "3–7 yosh", "#C9F0FF", "#DFF6FF", "#1C8FB8", ICO('<circle cx="22" cy="24" r="16" fill="#23C4E8" opacity=".8"/><circle cx="40" cy="40" r="14" fill="#FF6FB5" opacity=".8"/><text x="22" y="30" text-anchor="middle" font-size="16" font-weight="800" fill="#fff" font-family="Bal,sans-serif">5</text><text x="40" y="45" text-anchor="middle" font-size="14" font-weight="800" fill="#fff" font-family="Bal,sans-serif">8</text>'), () => {
  arcadeView(GBY.raqam, hud("0"), "Aytilgan raqamli pufakni portlat!");
  arcade({id: "raqam", stars: (s) => (s >= 25 ? 3 : s >= 12 ? 2 : s >= 4 ? 1 : 0),
    init(g) { Object.assign(g, {bub: [], next: 0, lives: 3, max: 10}); g.target = 1 + rnd(10); say(`${g.target} ni portlat`); },
    tap(g, x, y) { const b = g.bub.find((q) => !q.pop && Math.hypot(q.x - x, q.y - y) < q.r + 6); if (!b) return;
      if (b.n === g.target) { b.pop = 0.3; g.score++; sfx.pop(); haptic("hit"); g.max = Math.min(20, 10 + Math.floor(g.score / 4)); g.target = 1 + rnd(g.max); say(`${g.target} ni portlat`); if (!g.bub.some((q) => q.n === g.target)) g.next = 0; }
      else { b.shake = 0.4; sfx.err(); } },
    step(g, dt) {
      g.next -= dt; if (g.next <= 0) { const n = Math.random() < 0.4 ? g.target : 1 + rnd(g.max); g.bub.push({n, x: 40 + rnd(g.W - 80), y: g.H + 40, r: 30 + rnd(10), c: PCOL[rnd(PCOL.length)], sp: 50 + rnd(30) + g.score * 2}); g.next = 0.9; }
      g.bub.forEach((b) => { b.y -= b.sp * dt; if (b.pop) b.pop -= dt; if (b.shake) b.shake = Math.max(0, b.shake - dt);
        if (!b.pop && b.y < -40 && b.n === g.target && !b.lost) { b.lost = true; g.lives--; sfx.err(); if (g.lives <= 0) g.finish(g.score >= 8); } });
      g.bub = g.bub.filter((b) => b.y > -50 && !(b.pop !== undefined && b.pop <= 0)); setTxt("gsc", `${g.score} · ${g.lives} ♥`);
    },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#C9F0FF"; c.fillRect(0, 0, W, H);
      g.bub.forEach((b) => { const s = b.pop ? 1 + (0.3 - b.pop) * 3 : 1, dx = b.shake ? Math.sin(b.shake * 60) * 5 : 0;
        c.globalAlpha = b.pop ? b.pop / 0.3 : 0.92; circ(c, b.x + dx, b.y, b.r * s, b.c); circ(c, b.x + dx - b.r * 0.35, b.y - b.r * 0.35, b.r * 0.22, "rgba(255,255,255,.6)");
        c.fillStyle = "#fff"; c.font = `800 ${b.r}px Bal, sans-serif`; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(b.n, b.x + dx, b.y + 2); c.globalAlpha = 1; });
      c.textBaseline = "alphabetic"; c.fillStyle = "#1D2A5B"; rr(c, W / 2 - 100, 14, 200, 52, 26); c.fillStyle = "#fff"; c.font = "800 26px Bal, sans-serif"; c.textAlign = "center"; c.fillText(`${g.target} ni top!`, W / 2, 50); c.textAlign = "start";
    },
  });
});

// ------------------------------------------------------------------ 16. Matematik meva
const FRT = [["olma", "#FF4B3E"], ["nok", "#FFC21F"], ["olxo'ri", "#7A5CFA"], ["yashil olma", "#7ED957"]];
reg("matem", "Matematik meva", "aql", "5–8 yosh", "#FFF0C2", "#FFF0C2", "#C98500", ICO('<circle cx="16" cy="30" r="10" fill="#FF4B3E"/><text x="30" y="36" text-anchor="middle" font-size="18" font-weight="800" fill="#1D2A5B" font-family="Bal,sans-serif">+</text><circle cx="44" cy="30" r="10" fill="#FF4B3E"/>'), () => { S.q = 0; mathRound(); });
function mathRound() {
  const g = GBY.matem, plus = S.q < 5 || Math.random() < 0.6, a = 1 + rnd(5), b = plus ? 1 + rnd(5) : 1 + rnd(a), ans = plus ? a + b : a - b, f = FRT[rnd(FRT.length)];
  S.ans = ans; S.lock = false;
  const ch = shuffle([ans, ...pickN([...Array(11).keys()].filter((x) => x !== ans), 2)]);
  const fr = (n, cross) => Array.from({length: n}, (_, i) => `<span class="g-fr${cross && i >= n - cross ? " x" : ""}">${APPLE(f[1])}</span>`).join("");
  view(bar(g, hud(`${S.q + 1} / 10`)) + `<div class="g-eq">${plus ? `<div>${fr(a)}</div><b class="b">+</b><div>${fr(b)}</div>` : `<div>${fr(a, b)}</div><b class="b">−</b><div class="b g-num">${b}</div>`}<b class="b">=</b><b class="b g-q">?</b></div>
    <div class="g-eqtxt b">${a} ${plus ? "+" : "−"} ${b} = ?</div><div class="gx-fill"></div>
    <div class="g-ch3 g-mch">${ch.map((v) => `<button class="gx-big b" data-act="mans" data-v="${v}" style="--c1:#fff;--c2:#EBCB6B;color:#1D2A5B" aria-label="${v}">${v}</button>`).join("")}</div>`);
}
ACT.mans = (el) => {
  if (S.lock) return;
  if (+el.dataset.v !== S.ans) { wrong(el); return; }
  S.lock = true; el.style.setProperty("--c1", "#3BB273"); el.style.color = "#fff"; sfx.ok(); haptic("ok");
  const q = document.querySelector(".g-q"); if (q) q.textContent = S.ans;
  later(() => { S.q++; if (S.q >= 10) { yay("Matematik!", 2); S.q = 0; } else addStar(1); mathRound(); }, 900);
};

// ------------------------------------------------------------------ 17. Sehrli qo'ng'iroqlar (Simon)
const BELLS = [["Qizil", "#FF4D5E", 392], ["Yashil", "#3BB273", 523], ["Sariq", "#FFC93C", 659], ["Ko'k", "#2E86DE", 784]];
const BELL = (c) => `<svg viewBox="0 0 60 60" aria-hidden="true"><path d="M30 6 C18 6 14 18 14 30 V40 L8 46 H52 L46 40 V30 C46 18 42 6 30 6 Z" fill="${c}"/><circle cx="30" cy="50" r="6" fill="#FFC93C"/><ellipse cx="22" cy="20" rx="4" ry="8" fill="#fff" opacity=".4"/></svg>`;
reg("qongiroq", "Sehrli qo'ng'iroqlar", "musiqa", "4–10 yosh", "#2B1F4D", "#EDE7FF", "#5536D6", ICO(BELL("#FFC93C").replace(/^<svg[^>]*>/, "").replace("</svg>", "")), () => { S.seq = []; S.inp = 0; S.busy = true; drawBells("Tingla va eslab qol!"); later(simonNext, 700); });
function drawBells(msg) {
  view(bar(GBY.qongiroq, hud(`${Math.max(0, S.seq.length - 1)} ball`)) + `<div class="gx-h b" style="color:#fff;text-align:center" id="gsimon">${msg}</div>
    <div class="g-bells">${BELLS.map(([n, c], i) => `<button data-act="bell" data-i="${i}" aria-label="${n} qo'ng'iroq">${BELL(c)}</button>`).join("")}</div><div class="gx-fill"></div>`);
}
function ring(i) { const b = document.querySelector(`[data-act="bell"][data-i="${i}"]`); tone(BELLS[i][2], 0.5, "sine", 0.25); tone(BELLS[i][2] * 2, 0.3, "sine", 0.05);
  if (b) { b.classList.add("g-ringb"); later(() => b.classList.remove("g-ringb"), 380); } }
function simonNext() {
  S.seq.push(rnd(4)); S.inp = 0; S.busy = true; setTxt("gsimon", "Tingla…");
  S.seq.forEach((v, k) => later(() => ring(v), 650 * k + 300));
  later(() => { S.busy = false; setTxt("gsimon", "Endi sen takrorla!"); }, 650 * S.seq.length + 300);
}
ACT.bell = (el) => {
  if (S.busy) return;
  const i = +el.dataset.i; ring(i); haptic("hit");
  if (i !== S.seq[S.inp]) { S.busy = true; sfx.err(); const sc = S.seq.length - 1; setTxt("gsimon", `Adashding! Natija: ${sc}`); if (sc >= 3) addStar(sc >= 8 ? 3 : sc >= 5 ? 2 : 1); later(START.qongiroq, 1800); return; }
  S.inp++;
  if (S.inp === S.seq.length) { S.busy = true; setTxt("gsimon", "Barakalla!"); later(() => { drawBells("Barakalla!"); simonNext(); }, 700); }
};

// ------------------------------------------------------------------ 18. Musiqiy yulduzcha
const MELODY = [0, 0, 4, 4, 5, 5, 4, 3, 3, 2, 2, 1, 1, 0, 4, 4, 3, 3, 2, 2, 1, 4, 4, 3, 3, 2, 2, 1, 0, 0, 4, 4, 5, 5, 4, 3, 3, 2, 2, 1, 1, 0];
const MNOTE = [523, 587, 659, 698, 784, 880];
reg("notayulduz", "Musiqiy yulduzcha", "musiqa", "4–9 yosh", "#1D2A5B", "#E3E6F5", "#0B1238", ICO('<rect width="60" height="60" rx="12" fill="#1D2A5B"/><path d="M30 8l5 10 11 1.5-8 7.5 2 11-10-5.5-10 5.5 2-11-8-7.5 11-1.5z" fill="#FFC93C"/><rect x="8" y="46" width="44" height="6" rx="3" fill="#FF6FB5"/>'), () => {
  arcadeView(GBY.notayulduz, hud("0"), "Yulduz pastdagi chiziqqa yetganda<br>o'sha yo'lakni bos!");
  arcade({id: "notayulduz", stars: (s) => (s >= 36 ? 3 : s >= 24 ? 2 : s >= 10 ? 1 : 0),
    init(g) { Object.assign(g, {st: MELODY.map((n, i) => ({l: n % 3, n, y: -i * 70 - 40})), i: 0, combo: 0, fl: [0, 0, 0]}); },
    tap(g, x) { const l = Math.min(2, Math.floor(x / (g.W / 3))), zy = g.H - 120; g.fl[l] = 0.2;
      const s = g.st.find((q) => !q.done && q.l === l && Math.abs(q.y - zy) < 46);
      if (s) { s.done = true; g.score++; g.combo++; tone(MNOTE[s.n], 0.35, "triangle", 0.22); haptic("hit"); } else { g.combo = 0; tone(150, 0.08, "square", 0.05); } },
    step(g, dt) { const sp = 140; g.st.forEach((s) => { s.y += sp * dt; if (!s.done && !s.miss && s.y > g.H - 60) { s.miss = true; g.combo = 0; } });
      g.fl = g.fl.map((f) => Math.max(0, f - dt)); if (g.st.every((s) => s.done || s.miss)) g.finish(g.score >= MELODY.length * 0.6); setTxt("gsc", `${g.score} / ${MELODY.length}`); },
    draw(g, c) {
      const {W, H} = g, lw = W / 3; c.fillStyle = "#1D2A5B"; c.fillRect(0, 0, W, H);
      ["#FF6FB5", "#23C4E8", "#FFC93C"].forEach((col, i) => { c.fillStyle = g.fl[i] ? col + "55" : "rgba(255,255,255,.04)"; c.fillRect(i * lw + 2, 0, lw - 4, H);
        c.strokeStyle = col; c.lineWidth = 4; c.beginPath(); c.arc(i * lw + lw / 2, H - 120, 30, 0, 7); c.stroke(); });
      g.st.forEach((s) => { if (s.done || s.y < -30 || s.y > H + 30) return; STARP(c, s.l * lw + lw / 2, s.y, 24, s.miss ? "#5C6A99" : ["#FF6FB5", "#23C4E8", "#FFC93C"][s.l]); });
      if (g.combo >= 3) { c.fillStyle = "#fff"; c.font = "800 22px Bal, sans-serif"; c.textAlign = "center"; c.fillText(`${g.combo} ketma-ket!`, W / 2, 40); c.textAlign = "start"; }
    },
  });
});

// ------------------------------------------------------------------ 19. Basketbolchi
reg("basket", "Basketbolchi", "sport", "5–10 yosh", "#FFE3C2", "#FFE3C2", "#E86A2C", ICO('<circle cx="30" cy="36" r="18" fill="#FF8A1F"/><path d="M12 36 H48 M30 18 V54 M17 24 Q30 36 17 48 M43 24 Q30 36 43 48" stroke="#1D2A5B" stroke-width="2" fill="none"/><rect x="18" y="4" width="24" height="5" rx="2" fill="#FF4D5E"/>'), () => {
  arcadeView(GBY.basket, hud("0 / 10"), "To'pni pastga torting va qo'yib yuboring<br><small>yoki tepaga suring</small>");
  arcade({id: "basket", stars: (s) => (s >= 7 ? 3 : s >= 4 ? 2 : s >= 2 ? 1 : 0),
    init(g) { Object.assign(g, {ball: null, shots: 0, hx: g.W / 2, aim: null, msg: 0}); g.home = {x: g.W / 2, y: g.H - 90}; },
    tap(g, x, y) { if (!g.ball) g.aim = {x, y}; },
    drag(g, x, y) { if (g.aim) g.aim = {x, y}; },
    release(g, x, y) { const v = g.aim && !g.ball ? bv(g, x, y) : null; g.aim = null; if (!v) return;
      g.ball = {x: g.home.x, y: g.home.y, vx: v[0], vy: v[1], passed: false}; g.shots++; tone(300, 0.08, "triangle", 0.1); },
    step(g, dt) {
      g.hx = g.W / 2 + Math.sin(g.t * (0.8 + g.score * 0.08)) * (g.W * 0.28);
      const hy = 150, b = g.ball;
      if (b) { b.vy += 1300 * dt; b.x += b.vx * dt; b.y += b.vy * dt;
        if (b.vy > 0 && !b.passed && b.y > hy - 8 && b.y < hy + 20) { b.passed = true; if (Math.abs(b.x - g.hx) < 34) { b.scored = true; g.score++; sfx.ok(); haptic("ok"); g.msg = 1; } }
        if (b.y > g.H + 40 || b.x < -40 || b.x > g.W + 40) { g.ball = null; if (g.shots >= 10) g.finish(g.score >= 4); } }
      if (g.msg) g.msg = Math.max(0, g.msg - dt); setTxt("gsc", `${g.score} / 10 · ${10 - g.shots} to'p`);
    },
    draw(g, c) {
      const {W, H} = g, hy = 150; c.fillStyle = "#FFE3C2"; c.fillRect(0, 0, W, H); c.fillStyle = "#E8B07A"; c.fillRect(0, H - 50, W, 50);
      c.fillStyle = "#fff"; rr(c, g.hx - 56, hy - 92, 112, 76, 8); c.strokeStyle = "#FF4D5E"; c.lineWidth = 4; c.strokeRect(g.hx - 22, hy - 54, 44, 34);
      c.strokeStyle = "#fff"; c.lineWidth = 2; for (let i = -3; i <= 3; i++) { c.beginPath(); c.moveTo(g.hx + i * 10, hy); c.lineTo(g.hx + i * 7, hy + 34); c.stroke(); }
      c.fillStyle = "#FF4D5E"; rr(c, g.hx - 36, hy - 4, 72, 8, 4);
      const b = g.ball || g.home; circ(c, b.x, b.y, 22, "#FF8A1F"); c.strokeStyle = "#1D2A5B"; c.lineWidth = 2; c.beginPath(); c.moveTo(b.x - 22, b.y); c.lineTo(b.x + 22, b.y); c.moveTo(b.x, b.y - 22); c.lineTo(b.x, b.y + 22); c.stroke();
      const v = g.aim ? bv(g, g.aim.x, g.aim.y) : null;
      if (v) { let x = g.home.x, y = g.home.y, vx = v[0], vy = v[1];
        for (let i = 0; i < 16; i++) { vy += 1300 * 0.04; x += vx * 0.04; y += vy * 0.04; circ(c, x, y, 4, "rgba(29,42,91,.35)"); } }
      if (g.msg) { c.fillStyle = "#3BB273"; c.font = "800 34px Bal, sans-serif"; c.textAlign = "center"; c.fillText("Savat!", W / 2, H / 2); c.textAlign = "start"; }
    },
  });
});

function bv(g, x, y) {
  let dx = x - g.sx, dy = y - g.sy; if (Math.hypot(dx, dy) < 25) return null;
  if (dy > 0) { dx = -dx; dy = -dy; }                      // pastga tortish = rogatka
  const p = Math.max(0.55, Math.min(1.25, Math.hypot(dx, dy) / 160)), vy = -(820 + p * 330);
  return [Math.max(-420, Math.min(420, dx / Math.max(30, -dy) * -vy * 0.55)), vy];
}

// ------------------------------------------------------------------ 20. Futbolchi (penalti)
reg("futbol", "Futbolchi", "sport", "4–10 yosh", "#5BC06A", "#D9F2E3", "#2A8A55", ICO('<circle cx="30" cy="34" r="18" fill="#fff" stroke="#1D2A5B" stroke-width="2"/><path d="M30 24 l8 6 -3 9 h-10 l-3 -9 z" fill="#1D2A5B"/><path d="M8 10 H52 V18" stroke="#fff" stroke-width="3" fill="none"/>'), () => {
  arcadeView(GBY.futbol, hud("0 / 5"), "Darvozaning istalgan joyini bos!<br><small>Darvozabon yo'q tomonga tep</small>");
  arcade({id: "futbol", stars: (s) => (s >= 5 ? 3 : s >= 3 ? 2 : s >= 1 ? 1 : 0),
    init(g) { Object.assign(g, {kx: g.W / 2, shot: null, n: 0, res: null, rt: 0}); g.gl = {x: 30, y: 70, w: g.W - 60, h: 150}; },
    tap(g, x, y) { const G = g.gl; if (g.shot || g.res) return; if (x < G.x || x > G.x + G.w || y < G.y || y > G.y + G.h + 40) return;
      g.shot = {tx: Math.max(G.x + 12, Math.min(G.x + G.w - 12, x)), ty: Math.max(G.y + 14, Math.min(G.y + G.h - 10, y)), t: 0}; g.n++; tone(200, 0.1, "square", 0.1); },
    step(g, dt) {
      const G = g.gl; g.kx = G.x + G.w / 2 + Math.sin(g.t * (1.6 + g.n * 0.25)) * (G.w / 2 - 34);
      if (g.shot) { g.shot.t += dt * 2.2; if (g.shot.t >= 1) { const saved = Math.abs(g.shot.tx - g.kx) < 46 && g.shot.ty > G.y + 20;
          g.res = saved ? "Ushlab qoldi!" : "GOL!"; g.rt = 1.2; if (!saved) { g.score++; sfx.win(); haptic("ok"); } else sfx.err(); g.shot.done = true; g.shot = null; } }
      if (g.res) { g.rt -= dt; if (g.rt <= 0) { g.res = null; if (g.n >= 5) g.finish(g.score >= 3); } }
      setTxt("gsc", `${g.score} / 5`);
    },
    draw(g, c) {
      const {W, H} = g, G = g.gl; c.fillStyle = "#5BC06A"; c.fillRect(0, 0, W, H);
      for (let i = 0; i < 8; i++) { c.fillStyle = i % 2 ? "#4FB35E" : "#5BC06A"; c.fillRect(0, i * H / 8, W, H / 8); }
      c.strokeStyle = "rgba(255,255,255,.35)"; c.lineWidth = 1; for (let x = G.x; x <= G.x + G.w; x += 16) { c.beginPath(); c.moveTo(x, G.y); c.lineTo(x, G.y + G.h); c.stroke(); }
      for (let y = G.y; y <= G.y + G.h; y += 16) { c.beginPath(); c.moveTo(G.x, y); c.lineTo(G.x + G.w, y); c.stroke(); }
      c.strokeStyle = "#fff"; c.lineWidth = 8; c.beginPath(); c.moveTo(G.x, G.y + G.h); c.lineTo(G.x, G.y); c.lineTo(G.x + G.w, G.y); c.lineTo(G.x + G.w, G.y + G.h); c.stroke();
      c.strokeStyle = "rgba(255,255,255,.7)"; c.lineWidth = 3; c.strokeRect(G.x - 20, G.y + G.h, G.w + 40, 1);
      const kx = g.kx, ky = G.y + G.h - 60; c.fillStyle = "#FFC93C"; rr(c, kx - 22, ky, 44, 54, 14); circ(c, kx, ky - 12, 16, "#F6C9A0");
      c.fillStyle = "#FFC93C"; rr(c, kx - 46, ky + 4, 26, 12, 6); rr(c, kx + 20, ky + 4, 26, 12, 6); circ(c, kx - 6, ky - 14, 2.5, "#1D2A5B"); circ(c, kx + 6, ky - 14, 2.5, "#1D2A5B");
      let bx = W / 2, by = H - 130, br = 22; if (g.shot) { const t = g.shot.t; bx = W / 2 + (g.shot.tx - W / 2) * t; by = (H - 130) + (g.shot.ty - (H - 130)) * t - Math.sin(t * Math.PI) * 40; br = 22 - t * 9; }
      circ(c, bx, by, br, "#fff"); c.fillStyle = "#1D2A5B"; c.beginPath(); for (let i = 0; i < 5; i++) { const a = -Math.PI / 2 + i * 1.2566; c.lineTo(bx + Math.cos(a) * br * 0.4, by + Math.sin(a) * br * 0.4); } c.fill();
      if (g.res) { c.fillStyle = g.res === "GOL!" ? "#FFC93C" : "#fff"; c.font = "800 44px Bal, sans-serif"; c.textAlign = "center"; c.fillText(g.res, W / 2, G.y + G.h + 90); c.textAlign = "start"; }
    },
  });
});

// ------------------------------------------------------------------ 21. Tennis
reg("tennis", "Tennis ustasi", "sport", "5–10 yosh", "#7FCF8A", "#D9F2E3", "#2A8A55", ICO('<circle cx="22" cy="22" r="14" fill="none" stroke="#2E86DE" stroke-width="5"/><path d="M32 32 L48 50" stroke="#8A5A35" stroke-width="6" stroke-linecap="round"/><circle cx="44" cy="16" r="7" fill="#DFFF4D"/>'), () => {
  arcadeView(GBY.tennis, hud("0 : 0"), "Raketkangni barmoq bilan sur<br><small>5 ochko yiqqan g'olib</small>");
  arcade({id: "tennis", stars: (s) => (s >= 5 ? 3 : s >= 3 ? 2 : s >= 1 ? 1 : 0),
    init(g) { Object.assign(g, {px: g.W / 2, ax: g.W / 2, me: 0, ai: 0, pw: 96}); serve(g, 1); },
    drag(g, x) { g.px = Math.max(g.pw / 2, Math.min(g.W - g.pw / 2, x)); },
    step(g, dt) {
      const b = g.b; if (g.wait > 0) { g.wait -= dt; return; }
      b.x += b.vx * dt; b.y += b.vy * dt;
      if (b.x < 12 || b.x > g.W - 12) { b.vx = -b.vx; b.x = Math.max(12, Math.min(g.W - 12, b.x)); }
      const aisp = 170 + g.me * 25; g.ax += Math.max(-aisp * dt, Math.min(aisp * dt, b.x - g.ax)); g.ax = Math.max(g.pw / 2, Math.min(g.W - g.pw / 2, g.ax));
      const py = g.H - 60, ay = 60;
      if (b.vy > 0 && b.y > py - 12 && b.y < py + 6 && Math.abs(b.x - g.px) < g.pw / 2 + 10) { b.vy = -Math.abs(b.vy) * 1.04; b.vx += (b.x - g.px) * 4; tone(600, 0.06, "square", 0.1); haptic("hit"); }
      if (b.vy < 0 && b.y < ay + 12 && b.y > ay - 6 && Math.abs(b.x - g.ax) < g.pw / 2 + 6) { b.vy = Math.abs(b.vy); b.vx += (b.x - g.ax) * 3 + (Math.random() - 0.5) * 120; tone(500, 0.06, "square", 0.1); }
      if (b.y < -20) { g.me++; g.score = g.me; sfx.ok(); serve(g, 1); } if (b.y > g.H + 20) { g.ai++; sfx.err(); serve(g, -1); }
      if (g.me >= 5 || g.ai >= 5) g.finish(g.me >= 5); setTxt("gsc", `${g.me} : ${g.ai}`);
    },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#3B8F4E"; c.fillRect(0, 0, W, H); c.fillStyle = "#4FA866"; c.fillRect(20, 20, W - 40, H - 40);
      c.strokeStyle = "#fff"; c.lineWidth = 3; c.strokeRect(20, 20, W - 40, H - 40); c.beginPath(); c.moveTo(20, H / 2); c.lineTo(W - 20, H / 2); c.stroke(); c.beginPath(); c.moveTo(W / 2, 20); c.lineTo(W / 2, H - 20); c.stroke();
      c.fillStyle = "#FF4D5E"; rr(c, g.ax - g.pw / 2, 48, g.pw, 14, 7); c.fillStyle = "#2E86DE"; rr(c, g.px - g.pw / 2, H - 66, g.pw, 14, 7);
      circ(c, g.b.x, g.b.y, 11, "#DFFF4D"); c.strokeStyle = "#fff"; c.lineWidth = 2; c.beginPath(); c.arc(g.b.x - 5, g.b.y, 8, -0.8, 0.8); c.stroke();
      c.fillStyle = "rgba(255,255,255,.85)"; c.font = "800 44px Bal, sans-serif"; c.textAlign = "center"; c.fillText(g.ai, W / 2, H / 2 - 30); c.fillText(g.me, W / 2, H / 2 + 66); c.textAlign = "start";
    },
  });
});
function serve(g, dir) { g.b = {x: g.W / 2, y: g.H / 2, vx: (Math.random() - 0.5) * 220, vy: dir * -(260 + g.me * 12)}; g.wait = 0.8; }

// ------------------------------------------------------------------ 22. Quvnoq boks
reg("boks", "Quvnoq boks", "sport", "4–10 yosh", "#FFD6D9", "#FFD6D9", "#B3263A", ICO('<path d="M10 30 Q10 14 26 14 H32 Q42 14 42 26 V36 Q42 46 30 46 H22 Q10 46 10 36 Z" fill="#FF4D5E"/><rect x="16" y="44" width="20" height="10" rx="3" fill="#fff"/>'), () => {
  arcadeView(GBY.boks, hud("0"), "Nishon qaysi tomonda chiqsa,<br>o'sha qo'lqopni bos!");
  arcade({id: "boks", stars: (s) => (s >= 40 ? 3 : s >= 25 ? 2 : s >= 10 ? 1 : 0),
    init(g) { Object.assign(g, {tg: null, next: 0.5, punch: [0, 0], left: 30, bag: 0}); },
    tap(g, x, y) { const side = x < g.W / 2 ? 0 : 1; g.punch[side] = 0.18;
      if (g.tg && g.tg.side === side) { g.score += g.tg.gold ? 3 : 1; g.tg = null; g.next = 0.25; g.bag = 0.3; noise(ctx(), 0.1, 0, 300, 0.6); haptic("hit"); }
      else { tone(160, 0.08, "square", 0.05); } },
    step(g, dt) { g.left = Math.max(0, 30 - g.t); g.punch = g.punch.map((p) => Math.max(0, p - dt)); g.bag = Math.max(0, g.bag - dt);
      if (g.tg) { g.tg.t -= dt; if (g.tg.t <= 0) g.tg = null; } else { g.next -= dt; if (g.next <= 0) g.tg = {side: rnd(2), t: Math.max(0.55, 1.2 - g.t / 40), gold: Math.random() < 0.15}; }
      if (g.left <= 0) g.finish(g.score >= 10); setTxt("gsc", `${g.score} · ${Math.ceil(g.left)}s`); },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#FFD6D9"; c.fillRect(0, 0, W, H); c.fillStyle = "#E8A6B0"; c.fillRect(0, H * 0.62, W, H);
      c.strokeStyle = "#B3263A"; c.lineWidth = 4; [0.2, 0.3, 0.4].forEach((k) => { c.beginPath(); c.moveTo(0, H * k); c.lineTo(W, H * k); c.stroke(); });
      const sw = Math.sin(g.bag * 30) * 10; c.save(); c.translate(W / 2 + sw, 0); c.strokeStyle = "#5C6A99"; c.lineWidth = 3; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 70); c.stroke();
      c.fillStyle = "#B3263A"; rr(c, -46, 70, 92, 190, 40); c.fillStyle = "#FF4D5E"; rr(c, -46, 110, 92, 26, 6); c.restore();
      if (g.tg) { const x = g.tg.side ? W * 0.78 : W * 0.22, y = H * 0.32; circ(c, x, y, 40, g.tg.gold ? "#FFC93C" : "#fff"); circ(c, x, y, 26, "#FF4D5E"); circ(c, x, y, 12, g.tg.gold ? "#FFC93C" : "#fff"); }
      [0, 1].forEach((s) => { const x = s ? W * 0.75 : W * 0.25, y = H - 110 - g.punch[s] * 300; c.fillStyle = "#FF4D5E";
        c.beginPath(); c.ellipse(x, y, 56, 50, 0, 0, 7); c.fill(); c.fillStyle = "#fff"; rr(c, x - 36, y + 38, 72, 30, 8); c.fillStyle = "#B3263A"; c.beginPath(); c.ellipse(x + (s ? -28 : 28), y - 6, 18, 22, 0, 0, 7); c.fill(); });
    },
  });
});

// ------------------------------------------------------------------ 23. Skeytbordchi
reg("skeyt", "Skeytbordchi", "sport", "5–10 yosh", "#C7B6FF", "#EDE7FF", "#5536D6", ICO('<rect x="10" y="40" width="40" height="7" rx="3.5" fill="#FF4D5E"/><circle cx="18" cy="51" r="4" fill="#1D2A5B"/><circle cx="42" cy="51" r="4" fill="#1D2A5B"/><circle cx="30" cy="14" r="7" fill="#F6C9A0"/><rect x="25" y="20" width="10" height="18" rx="4" fill="#2E86DE"/>'), () => {
  arcadeView(GBY.skeyt, hud("0"), "Chapga/o'ngga sur — yo'lak almashadi<br><small>Tepaga sur — o'rindiqdan sakraydi</small>");
  arcade({id: "skeyt", stars: (s) => (s >= 120 ? 3 : s >= 60 ? 2 : s >= 20 ? 1 : 0),
    init(g) { const rw = Math.min(g.W - 30, 300); Object.assign(g, {rx: (g.W - rw) / 2, rw, lane: 1, sx2: 0, ob: [], sp: 240, next: 1, jump: 0, off: 0, coins: 0}); g.sx2 = g.rx + rw / 2; },
    release(g, x, y) { const dx = x - g.sx, dy = y - g.sy;
      if (dy < -30 && Math.abs(dy) > Math.abs(dx)) { if (!g.jump) { g.jump = 0.7; tone(500, 0.15, "triangle", 0.12, 0, 900); } return; }
      const dir = Math.abs(dx) > 30 ? Math.sign(dx) : (x < g.W / 2 ? -1 : 1); g.lane = Math.max(0, Math.min(2, g.lane + dir)); tone(420, 0.05, "sine", 0.1); },
    step(g, dt) {
      g.sp = Math.min(560, g.sp + dt * 8); g.off = (g.off + g.sp * dt) % 60; g.score += dt * 3; if (g.jump) g.jump = Math.max(0, g.jump - dt);
      const lw = g.rw / 3; g.sx2 += (g.rx + lw * g.lane + lw / 2 - g.sx2) * Math.min(1, dt * 14);
      g.next -= dt; if (g.next <= 0) { const k = Math.random(); g.ob.push({l: rnd(3), y: -60, t: k < 0.35 ? "coin" : k < 0.7 ? "bench" : "cone"}); g.next = Math.max(0.45, 1 - g.t / 120); }
      const py = g.H - 140;
      g.ob.forEach((o) => { o.y += g.sp * dt; const ox = g.rx + lw * o.l + lw / 2;
        if (!o.done && Math.abs(ox - g.sx2) < lw * 0.5 && Math.abs(o.y - py) < 30) {
          if (o.t === "coin") { o.done = true; g.coins++; g.score += 5; tone(1100, 0.07, "triangle", 0.12); }
          else if (o.t === "bench" && g.jump > 0.1) { o.done = true; g.score += 3; }
          else { g.finish(); } } });
      g.ob = g.ob.filter((o) => !o.done && o.y < g.H + 60); setTxt("gsc", `${Math.floor(g.score)}`);
    },
    draw(g, c) {
      const {W, H} = g, lw = g.rw / 3; c.fillStyle = "#C7B6FF"; c.fillRect(0, 0, W, H); c.fillStyle = "#B8C2D9"; c.fillRect(g.rx, 0, g.rw, H);
      c.fillStyle = "#fff"; for (let i = 1; i < 3; i++) for (let y = -60 + g.off; y < H; y += 60) rr(c, g.rx + lw * i - 2, y, 4, 30, 2);
      g.ob.forEach((o) => { const x = g.rx + lw * o.l + lw / 2;
        if (o.t === "coin") { circ(c, x, o.y, 14, "#FFC93C"); c.strokeStyle = "#E0A500"; c.lineWidth = 3; c.beginPath(); c.arc(x, o.y, 14, 0, 7); c.stroke(); }
        else if (o.t === "bench") { c.fillStyle = "#B5651D"; rr(c, x - lw * 0.42, o.y - 10, lw * 0.84, 20, 6); c.fillStyle = "#8A4A12"; rr(c, x - lw * 0.36, o.y + 8, 8, 12, 2); rr(c, x + lw * 0.36 - 8, o.y + 8, 8, 12, 2); }
        else { c.fillStyle = "#FF8A1F"; c.beginPath(); c.moveTo(x, o.y - 24); c.lineTo(x + 18, o.y + 16); c.lineTo(x - 18, o.y + 16); c.fill(); c.fillStyle = "#fff"; c.fillRect(x - 10, o.y - 2, 20, 6); } });
      const x = g.sx2, y = g.H - 140, j = g.jump ? Math.sin((0.7 - g.jump) / 0.7 * Math.PI) : 0, s = 1 + j * 0.35;
      c.fillStyle = "rgba(0,0,0,.15)"; c.beginPath(); c.ellipse(x, y + 26, 22, 8, 0, 0, 7); c.fill();
      c.save(); c.translate(x, y - j * 20); c.scale(s, s);
      c.fillStyle = "#FF4D5E"; rr(c, -12, -8, 24, 52, 10); c.fillStyle = "#1D2A5B"; rr(c, -16, -2, 6, 10, 2); rr(c, 10, -2, 6, 10, 2); rr(c, -16, 30, 6, 10, 2); rr(c, 10, 30, 6, 10, 2);
      c.fillStyle = "#2E86DE"; rr(c, -14, 0, 28, 30, 10); circ(c, 0, -4, 12, "#6B4423"); circ(c, 0, 4, 10, "#F6C9A0"); c.restore();
    },
  });
});

// ------------------------------------------------------------------ 24. Suvchini boshqar
reg("suvchi", "Suvchini boshqar", "harakat", "4–9 yosh", "#2FA8D8", "#D6F3FF", "#0E8FB0", ICO('<rect width="60" height="60" rx="12" fill="#2FA8D8"/><ellipse cx="30" cy="32" rx="16" ry="9" fill="#FFC93C"/><circle cx="18" cy="30" r="7" fill="#F6C9A0"/><g fill="#fff" opacity=".7"><circle cx="46" cy="16" r="4"/><circle cx="40" cy="10" r="2.5"/></g>'), () => {
  arcadeView(GBY.suvchi, hud("0"), "Bosib tur — yuqoriga suzadi<br><small>Qo'yib yuborsang — cho'kadi</small>");
  arcade({id: "suvchi", stars: (s) => (s >= 60 ? 3 : s >= 30 ? 2 : s >= 10 ? 1 : 0),
    init(g) { Object.assign(g, {y: g.H / 2, vy: 0, ox: 100, it: [], next: 0.6}); },
    step(g, dt) {
      g.vy += (g.down ? -700 : 420) * dt; g.vy = Math.max(-260, Math.min(240, g.vy)); g.y += g.vy * dt;
      if (g.y < 40) { g.y = 40; g.vy = 0; } if (g.y > g.H - 50) { g.y = g.H - 50; g.vy = 0; }
      g.ox -= dt * 5; if (g.ox <= 0) g.finish(g.score >= 15);
      const sp = 140 + Math.min(120, g.t * 2.5);
      g.next -= dt; if (g.next <= 0) { const k = Math.random(); g.it.push({x: g.W + 30, y: 60 + rnd(g.H - 120), t: k < 0.4 ? "bub" : k < 0.55 ? "chest" : "urch"}); g.next = 0.55 + Math.random() * 0.5; }
      g.it.forEach((o) => { o.x -= sp * dt; if (!o.done && Math.hypot(o.x - 80, o.y - g.y) < 32) { o.done = true;
        if (o.t === "bub") { g.ox = Math.min(100, g.ox + 15); g.score += 1; tone(900, 0.06, "sine", 0.12); }
        else if (o.t === "chest") { g.score += 10; sfx.ok(); } else g.finish(g.score >= 15); } });
      g.it = g.it.filter((o) => o.x > -40 && !o.done); setTxt("gsc", `${g.score}`);
    },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#2FA8D8"; c.fillRect(0, 0, W, H); c.fillStyle = "#2696C4"; c.fillRect(0, H * 0.5, W, H); c.fillStyle = "#F4D58D"; c.fillRect(0, H - 30, W, 30);
      for (let i = 0; i < 5; i++) { c.fillStyle = "#3BB273"; const x = ((i * 120 - g.t * 60) % (W + 120) + W + 120) % (W + 120) - 60; c.beginPath(); c.moveTo(x, H - 30); c.quadraticCurveTo(x - 20, H - 90, x + 4, H - 130); c.quadraticCurveTo(x + 14, H - 80, x + 12, H - 30); c.fill(); }
      g.it.forEach((o) => { if (o.t === "bub") { c.strokeStyle = "rgba(255,255,255,.9)"; c.lineWidth = 3; c.beginPath(); c.arc(o.x, o.y, 14, 0, 7); c.stroke(); circ(c, o.x - 5, o.y - 5, 3, "#fff"); }
        else if (o.t === "chest") { c.fillStyle = "#B5651D"; rr(c, o.x - 20, o.y - 10, 40, 26, 5); c.fillStyle = "#D9822B"; rr(c, o.x - 20, o.y - 18, 40, 12, 6); c.fillStyle = "#FFC93C"; c.fillRect(o.x - 4, o.y - 14, 8, 14); }
        else { circ(c, o.x, o.y, 14, "#5A2A6E"); c.strokeStyle = "#5A2A6E"; c.lineWidth = 3; for (let a = 0; a < 6.28; a += 0.52) { c.beginPath(); c.moveTo(o.x, o.y); c.lineTo(o.x + Math.cos(a) * 24, o.y + Math.sin(a) * 24); c.stroke(); } } });
      const y = g.y; c.save(); c.translate(80, y); c.rotate(Math.max(-0.4, Math.min(0.4, g.vy / 600)));
      c.fillStyle = "#FFC93C"; rr(c, -30, -8, 50, 18, 9); circ(c, 26, 0, 12, "#F6C9A0"); c.fillStyle = "#FF4D5E"; rr(c, 18, -12, 18, 7, 3);
      c.fillStyle = "rgba(191,230,255,.8)"; rr(c, 24, -6, 14, 8, 3); c.fillStyle = "#F6C9A0"; rr(c, -48, -4 + Math.sin(g.t * 12) * 6, 20, 6, 3); c.restore();
      c.fillStyle = "rgba(255,255,255,.4)"; rr(c, 16, 14, 120, 16, 8); c.fillStyle = g.ox < 25 ? "#FF4D5E" : "#fff"; rr(c, 16, 14, 1.2 * g.ox, 16, 8);
      c.fillStyle = "#1D2A5B"; c.font = "800 12px Bal, sans-serif"; c.fillText("Havo", 140, 27);
    },
  });
});

// ------------------------------------------------------------------ 25. Oltin izlovchi
reg("oltin", "Oltin izlovchi", "harakat", "5–10 yosh", "#8A5A35", "#F1E3C2", "#6B4423", ICO('<rect width="60" height="60" rx="12" fill="#8A5A35"/><path d="M30 6 V30" stroke="#1D2A5B" stroke-width="3"/><path d="M22 30 L30 38 L38 30" stroke="#1D2A5B" stroke-width="3" fill="none"/><path d="M20 44 L30 40 L40 44 L36 54 H24 Z" fill="#23C4E8"/><circle cx="14" cy="48" r="6" fill="#FFC93C"/>'), () => {
  arcadeView(GBY.oltin, hud("0"), "Ilmoq to'g'ri tomonga qaraganda bos!<br><small>60 soniyada ko'proq oltin yig'</small>");
  arcade({id: "oltin", stars: (s) => (s >= 600 ? 3 : s >= 350 ? 2 : s >= 150 ? 1 : 0),
    init(g) { g.it = []; for (let i = 0; i < 12; i++) { const k = Math.random(); const t = k < 0.35 ? "gold" : k < 0.55 ? "big" : k < 0.75 ? "gem" : "rock";
        g.it.push({x: 40 + rnd(g.W - 80), y: g.H * 0.35 + rnd(g.H * 0.55), t, r: {gold: 16, big: 26, gem: 12, rock: 22}[t], v: {gold: 50, big: 150, gem: 120, rock: 10}[t], w: {gold: 1, big: 2.6, gem: 0.8, rock: 2.2}[t]}); }
      Object.assign(g, {ang: 0, st: "swing", len: 40, got: null, left: 60}); },
    tap(g) { if (g.st === "swing") { g.st = "out"; tone(300, 0.1, "square", 0.08); } },
    step(g, dt) {
      g.left = Math.max(0, 60 - g.t); if (g.left <= 0) { g.finish(g.score >= 150); return; }
      const ox = g.W / 2, oy = 80;
      if (g.st === "swing") { g.ang = Math.sin(g.t * 1.6) * 1.2; }
      else if (g.st === "out") { g.len += 380 * dt; const hx = ox + Math.sin(g.ang) * g.len, hy = oy + Math.cos(g.ang) * g.len;
        const t = g.it.find((o) => !o.taken && Math.hypot(o.x - hx, o.y - hy) < o.r + 8);
        if (t) { t.taken = true; g.got = t; g.st = "in"; tone(200, 0.15, "triangle", 0.12); } else if (hx < 0 || hx > g.W || hy > g.H) g.st = "in"; }
      else { g.len -= (g.got ? 300 / g.got.w : 500) * dt; if (g.got) { g.got.x = ox + Math.sin(g.ang) * (g.len + g.got.r); g.got.y = oy + Math.cos(g.ang) * (g.len + g.got.r); }
        if (g.len <= 40) { g.len = 40; g.st = "swing"; if (g.got) { g.score += g.got.v; g.got.gone = true; g.got.t === "rock" ? tone(120, 0.2, "square", 0.08) : sfx.ok(); g.got = null;
          if (g.it.filter((o) => !o.gone).length < 4) for (let i = 0; i < 5; i++) { const t = ["gold", "gem", "big", "rock"][rnd(4)]; g.it.push({x: 40 + rnd(g.W - 80), y: g.H * 0.4 + rnd(g.H * 0.5), t, r: {gold: 16, big: 26, gem: 12, rock: 22}[t], v: {gold: 50, big: 150, gem: 120, rock: 10}[t], w: {gold: 1, big: 2.6, gem: 0.8, rock: 2.2}[t]}); } } } }
      setTxt("gsc", `${g.score} · ${Math.ceil(g.left)}s`);
    },
    draw(g, c) {
      const {W, H} = g, ox = W / 2, oy = 80; c.fillStyle = "#BFE6FF"; c.fillRect(0, 0, W, 100); c.fillStyle = "#8A5A35"; c.fillRect(0, 100, W, H);
      c.fillStyle = "#7A4E2D"; for (let i = 0; i < 30; i++) circ(c, (i * 73) % W, 130 + (i * 131) % (H - 140), 4 + (i % 3), "#7A4E2D");
      g.it.forEach((o) => { if (o.gone) return; if (o.t === "gold" || o.t === "big") { c.fillStyle = "#FFC93C"; c.beginPath(); c.ellipse(o.x, o.y, o.r, o.r * 0.8, 0.3, 0, 7); c.fill(); circ(c, o.x - o.r * 0.3, o.y - o.r * 0.3, o.r * 0.25, "#FFF1A6"); }
        else if (o.t === "gem") { c.fillStyle = "#23C4E8"; c.beginPath(); c.moveTo(o.x, o.y - o.r); c.lineTo(o.x + o.r, o.y - o.r * 0.2); c.lineTo(o.x, o.y + o.r); c.lineTo(o.x - o.r, o.y - o.r * 0.2); c.fill(); }
        else { c.fillStyle = "#8A8F9C"; c.beginPath(); c.ellipse(o.x, o.y, o.r, o.r * 0.75, 0, 0, 7); c.fill(); } });
      const hx = ox + Math.sin(g.ang) * g.len, hy = oy + Math.cos(g.ang) * g.len; c.strokeStyle = "#1D2A5B"; c.lineWidth = 3; c.beginPath(); c.moveTo(ox, oy); c.lineTo(hx, hy); c.stroke();
      c.save(); c.translate(hx, hy); c.rotate(-g.ang); c.lineWidth = 5; c.beginPath(); c.moveTo(-12, 0); c.lineTo(-6, 12); c.moveTo(12, 0); c.lineTo(6, 12); c.moveTo(-12, 0); c.lineTo(12, 0); c.stroke(); c.restore();
      c.fillStyle = "#B5651D"; rr(c, ox - 40, 52, 80, 30, 8); circ(c, ox, 36, 16, "#F6C9A0"); c.fillStyle = "#FFC93C"; rr(c, ox - 16, 16, 32, 10, 4); circ(c, ox - 5, 36, 2.5, "#1D2A5B"); circ(c, ox + 5, 36, 2.5, "#1D2A5B");
    },
  });
});

// ------------------------------------------------------------------ 26. Supermarket kassa
const GOODS = [["Sut", '<rect x="14" y="10" width="20" height="32" rx="3" fill="#fff" stroke="#2E86DE" stroke-width="3"/><path d="M14 18 L20 8 H28 L34 18" fill="#2E86DE"/>'],
  ["Non", '<ellipse cx="24" cy="28" rx="20" ry="13" fill="#E8B07A"/><path d="M12 24 L16 30 M22 22 L26 30 M32 24 L36 30" stroke="#B5651D" stroke-width="2.5"/>'],
  ["Olma", '<circle cx="24" cy="28" r="15" fill="#FF4B3E"/><path d="M24 13 q2 -6 8 -6" stroke="#6B4423" stroke-width="3" fill="none"/>'],
  ["Koptok", '<circle cx="24" cy="26" r="16" fill="#FFC93C"/><path d="M8 26 H40 M24 10 V42" stroke="#FF4D5E" stroke-width="3"/>'],
  ["Ayiqcha", '<circle cx="14" cy="12" r="6" fill="#B07A4F"/><circle cx="34" cy="12" r="6" fill="#B07A4F"/><circle cx="24" cy="22" r="13" fill="#B07A4F"/><circle cx="20" cy="20" r="2" fill="#1D2A5B"/><circle cx="28" cy="20" r="2" fill="#1D2A5B"/><ellipse cx="24" cy="40" rx="12" ry="7" fill="#B07A4F"/>'],
  ["Sharbat", '<rect x="14" y="12" width="20" height="30" rx="4" fill="#FF8A1F"/><rect x="22" y="4" width="3" height="10" fill="#1D2A5B"/>']];
const MONEY = [[500, "#C9A86B"], [1000, "#7FB7E8"], [2000, "#E8A6B0"], [5000, "#8EDBB0"]];
const som = (n) => n.toLocaleString("ru-RU").replace(/ /g, " ") + " so'm";
reg("kassa", "Supermarket kassa", "aql", "5–9 yosh", "#DFF6E8", "#DFF6E8", "#2A8A55", ICO('<rect x="8" y="22" width="44" height="30" rx="5" fill="#2E86DE"/><rect x="14" y="10" width="26" height="14" rx="3" fill="#1D2A5B"/><text x="27" y="21" text-anchor="middle" font-size="8" fill="#3BF07A" font-family="monospace">5000</text><rect x="14" y="30" width="32" height="6" rx="2" fill="#fff"/>'), () => { S.n = 0; kassaRound(); });
function kassaRound() { const k = GOODS[rnd(GOODS.length)]; S.item = k; S.price = (1 + rnd(16)) * 500; S.paid = []; S.lock = false; drawKassa(); }
function drawKassa(msg) {
  const g = GBY.kassa, sum = S.paid.reduce((a, b) => a + b, 0);
  view(bar(g, hud(`${S.n} xaridor`)) + speech(msg || `Narxi ${som(S.price)}. Aniq shuncha pul ber!`) +
    `<div class="g-shop"><div class="g-item"><svg viewBox="0 0 48 48" aria-hidden="true">${S.item[1]}</svg><b class="b">${S.item[0]}</b><span class="tag b">${som(S.price)}</span></div>
      <div class="g-till"><div class="scr">${som(sum)}</div><div class="g-paid">${S.paid.map((m) => `<i style="background:${MONEY.find((x) => x[0] === m)[1]}">${m}</i>`).join("")}</div></div></div>
    <div class="gx-fill"></div><div class="g-tray"><div class="g-opts" style="grid-template-columns:repeat(2,1fr)">
      ${MONEY.map(([v, c]) => `<button class="g-opt g-bill" data-act="pay" data-v="${v}" style="--bc:${c}" aria-label="${som(v)}"><span class="b">${v.toLocaleString("ru-RU").replace(/ /g, " ")}</span>so'm</button>`).join("")}</div>
      <button class="gx-btn b" data-act="payclr" style="margin-top:10px;background:#8A8F9C">Pulni qaytarib olish</button></div>`);
}
ACT.pay = (el) => {
  if (S.lock) return; const v = +el.dataset.v; S.paid.push(v); tone(700, 0.06, "triangle", 0.12); haptic();
  const sum = S.paid.reduce((a, b) => a + b, 0);
  if (sum === S.price) { S.lock = true; drawKassa("To'landi! Rahmat, xaridingiz uchun!"); [880, 1175].forEach((f, i) => tone(f, 0.15, "triangle", 0.2, i * 0.12)); later(() => { S.n++; if (S.n % 5 === 0) yay("Zo'r kassir!", 2); else addStar(1); kassaRound(); }, 1300); }
  else if (sum > S.price) { drawKassa(`Ko'p berding: ${som(sum)}. Pulni qaytarib ol va qayta sana`); sfx.err(); }
  else drawKassa(`Yana ${som(S.price - sum)} kerak`);
};
ACT.payclr = () => { S.paid = []; sfx.tap(); drawKassa(); };

// ------------------------------------------------------------------ 27. Muzqaymoq do'koni
const CONES = [["Vafli", "#E8B07A"], ["Shokoladli", "#7E4A1E"]];
const SCOOPS = [["Vanil", "#FFF4D6"], ["Qulupnay", "#FF9AC1"], ["Shokolad", "#8A5A35"], ["Yalpiz", "#9FE8C4"], ["Limon", "#FFE66D"]];
const TOPS = [["Gilos", "c"], ["Sepma", "s"], ["Hech narsa", "n"]];
function iceSVG(o) {
  const cone = CONES.find((x) => x[0] === o.cone);
  let s = `<svg viewBox="0 0 120 170" aria-hidden="true">`;
  if (cone) s += `<path d="M30 92 L60 166 L90 92 Z" fill="${cone[1]}"/><path d="M40 100 L80 140 M80 100 L46 150 M34 110 L70 160" stroke="rgba(0,0,0,.15)" stroke-width="3"/>`;
  (o.sc || []).forEach((n, i) => { const c = SCOOPS.find((x) => x[0] === n)[1]; s += `<circle cx="60" cy="${80 - i * 30}" r="30" fill="${c}"/><path d="M32 ${88 - i * 30} q7 8 14 0 q7 8 14 0 q7 8 14 0 q7 8 14 0" fill="${c}"/>`; });
  const topY = 80 - Math.max(0, (o.sc || []).length - 1) * 30 - 30;
  if (o.top === "Gilos") s += `<circle cx="60" cy="${topY - 4}" r="9" fill="#E0213B"/><path d="M60 ${topY - 12} q4 -12 12 -14" stroke="#3BB273" stroke-width="2.5" fill="none"/>`;
  if (o.top === "Sepma" && (o.sc || []).length) for (let i = 0; i < 10; i++) s += `<rect x="${38 + (i * 17) % 44}" y="${topY + 12 + (i * 7) % 18}" width="7" height="3" rx="1.5" fill="${PCOL[i % 7]}" transform="rotate(${i * 40} ${41 + (i * 17) % 44} ${topY + 14 + (i * 7) % 18})"/>`;
  return s + "</svg>";
}
reg("muzqaymoq", "Muzqaymoq do'koni", "ijod", "3–8 yosh", "#FFE1F0", "#FFE1F0", "#D13F86", ICO('<path d="M18 30 L30 56 L42 30 Z" fill="#E8B07A"/><circle cx="30" cy="24" r="13" fill="#FF9AC1"/><circle cx="30" cy="10" r="5" fill="#E0213B"/>'), () => { S.served = 0; iceOrder(); });
function iceOrder() {
  const n = 1 + rnd(Math.min(3, 1 + Math.floor(S.served / 2)));
  S.ord = {cone: CONES[rnd(2)][0], sc: Array.from({length: n}, () => SCOOPS[rnd(SCOOPS.length)][0]), top: TOPS[rnd(3)][0]};
  S.cur = {cone: null, sc: [], top: null}; S.who = pickN(Object.keys(ANIMAL), 1)[0]; S.lock = false; drawIce();
}
function drawIce(msg) {
  const g = GBY.muzqaymoq, o = S.ord, c = S.cur;
  const step = !c.cone ? "cone" : c.sc.length < 3 && !c.top ? "sc" : "top";
  view(bar(g, hud(`${S.served} buyurtma`)) + `<div class="g-order"><span class="who">${animalSVG(S.who)}</span><div class="bub2"><b class="b">${ANIMAL[S.who].n}:</b>
      <span>${o.cone} konus, ${o.sc.join(" + ")}${o.top !== "Hech narsa" ? `, ustiga ${o.top.toLowerCase()}` : ""}</span><span class="mini">${iceSVG(o)}</span></div></div>
    ${msg ? `<div class="gx-h b" style="text-align:center">${msg}</div>` : ""}
    <div class="g-ice">${iceSVG(c)}</div><div class="gx-fill"></div>
    <div class="g-tray"><div class="hint b" style="font-size:16px;color:var(--ink)">${!c.cone ? "1. Konusni tanla" : !c.top ? "2. Sharcha qo'sh (ketma-ket), keyin bezak" : "Tayyor bo'lsa — topshir!"}</div>
      <div class="g-opts" style="grid-template-columns:repeat(${!c.cone ? 2 : !c.top ? 4 : 3},1fr)">
      ${!c.cone ? CONES.map(([n, col]) => `<button class="g-opt" data-act="icone" data-v="${n}"><span style="background:${col};clip-path:polygon(0 0,100% 0,50% 100%);height:30px"></span>${n}</button>`).join("")
        : !c.top ? SCOOPS.slice(0, 5).map(([n, col]) => `<button class="g-opt" data-act="iscoop" data-v="${n}" ${c.sc.length >= 3 ? "disabled" : ""}><span style="background:${col};border-radius:50%;width:32px;height:32px"></span>${n}</button>`).join("") + TOPS.map(([n]) => `<button class="g-opt" data-act="itop" data-v="${n}">${n === "Hech narsa" ? "Bezaksiz" : n}</button>`).join("")
        : ""}</div>
      ${c.cone ? `<div style="display:flex;gap:8px;margin-top:10px"><button class="gx-btn b" data-act="iclear" style="background:#8A8F9C;flex:1">Qaytadan</button><button class="gx-btn b" data-act="iserve" style="background:#D13F86;flex:2">Topshirish</button></div>` : ""}</div>`);
  void step;
}
ACT.icone = (el) => { S.cur.cone = el.dataset.v; sfx.tap(); drawIce(); };
ACT.iscoop = (el) => { if (S.cur.sc.length >= 3) return; S.cur.sc.push(el.dataset.v); tone(600 + S.cur.sc.length * 100, 0.1, "sine", 0.14); drawIce(); };
ACT.itop = (el) => { S.cur.top = el.dataset.v; sfx.tap(); drawIce(); };
ACT.iclear = () => { S.cur = {cone: null, sc: [], top: null}; drawIce(); };
ACT.iserve = () => {
  if (S.lock) return; const o = S.ord, c = S.cur;
  const ok = c.cone === o.cone && c.sc.join() === o.sc.join() && (c.top || "Hech narsa") === o.top;
  if (!ok) { sfx.err(); haptic("err"); drawIce("Buyurtma boshqacha edi — qayta qarab chiq!"); return; }
  S.lock = true; S.served++; CALL[S.who] ? CALL[S.who](ctx()) : sfx.ok(); drawIce("Mazali! Rahmat!");
  later(() => { if (S.served % 4 === 0) yay("Eng zo'r muzqaymoqchi!", 2); else addStar(1); iceOrder(); }, 1400);
};

// ------------------------------------------------------------------ 28. O'yinchoq savatchasi
reg("oyinchoq", "O'yinchoq savatchasi", "harakat", "3–8 yosh", "#FFF0C2", "#FFF0C2", "#C98500", ICO('<path d="M10 24 H50 L44 46 H16 Z" fill="#2E86DE"/><circle cx="20" cy="52" r="4" fill="#1D2A5B"/><circle cx="40" cy="52" r="4" fill="#1D2A5B"/><circle cx="30" cy="14" r="8" fill="#FF4D5E"/>'), () => {
  arcadeView(GBY.oyinchoq, hud("0"), "Aravachani barmoq bilan sur<br><small>Axlatni ushlama!</small>");
  arcade({id: "oyinchoq", stars: (s) => (s >= 60 ? 3 : s >= 30 ? 2 : s >= 10 ? 1 : 0),
    init(g) { Object.assign(g, {cx: g.W / 2, it: [], next: 0.4, lives: 3, fall: 170}); },
    drag(g, x) { g.cx = Math.max(55, Math.min(g.W - 55, x)); },
    step(g, dt) {
      g.fall = Math.min(420, g.fall + dt * 6);
      g.next -= dt; if (g.next <= 0) { const bad = Math.random() < Math.min(0.3, 0.12 + g.t / 250); g.it.push({x: 30 + rnd(g.W - 60), y: -30, t: bad ? ["kan", "banan"][rnd(2)] : ["koptok", "ordak", "ayiq", "kub"][rnd(4)], bad, r: 0}); g.next = Math.max(0.35, 0.85 - g.t / 90); }
      const cy = g.H - 80;
      g.it.forEach((o) => { o.y += g.fall * dt; o.r += dt * 3;
        if (!o.done && o.y > cy - 10 && o.y < cy + 26 && Math.abs(o.x - g.cx) < 58) { o.done = true; if (o.bad) { g.lives--; sfx.err(); haptic("err"); if (g.lives <= 0) g.finish(g.score >= 10); } else { g.score++; tone(700 + rnd(400), 0.08, "triangle", 0.14); } } });
      g.it = g.it.filter((o) => !o.done && o.y < g.H + 40); setTxt("gsc", `${g.score} · ${g.lives} ♥`);
    },
    draw(g, c) {
      const {W, H} = g; c.fillStyle = "#FFF0C2"; c.fillRect(0, 0, W, H); c.fillStyle = "#8A8F9C"; c.fillRect(0, 0, W, 34); c.fillStyle = "#5C6A99"; for (let x = -(g.t * 60 % 30); x < W; x += 30) c.fillRect(x, 26, 14, 8);
      c.fillStyle = "#E8C27A"; c.fillRect(0, H - 40, W, 40);
      g.it.forEach((o) => { c.save(); c.translate(o.x, o.y); c.rotate(Math.sin(o.r) * 0.4);
        if (o.t === "koptok") { circ(c, 0, 0, 17, "#FFC93C"); c.strokeStyle = "#FF4D5E"; c.lineWidth = 3; c.beginPath(); c.moveTo(-17, 0); c.lineTo(17, 0); c.stroke(); }
        else if (o.t === "ordak") { c.fillStyle = "#FFE14D"; c.beginPath(); c.ellipse(0, 4, 18, 12, 0, 0, 7); c.fill(); circ(c, 9, -8, 9, "#FFE14D"); c.fillStyle = "#FF8A1F"; c.beginPath(); c.moveTo(16, -8); c.lineTo(24, -5); c.lineTo(16, -3); c.fill(); circ(c, 11, -10, 2, "#1D2A5B"); }
        else if (o.t === "ayiq") { circ(c, -9, -12, 6, "#B07A4F"); circ(c, 9, -12, 6, "#B07A4F"); circ(c, 0, -2, 14, "#B07A4F"); circ(c, -4, -4, 2, "#1D2A5B"); circ(c, 4, -4, 2, "#1D2A5B"); }
        else if (o.t === "kub") { c.fillStyle = "#7A5CFA"; rr(c, -15, -15, 30, 30, 5); c.fillStyle = "#fff"; c.font = "800 18px Bal, sans-serif"; c.textAlign = "center"; c.fillText("A", 0, 6); c.textAlign = "start"; }
        else if (o.t === "kan") { c.fillStyle = "#8A8F9C"; rr(c, -11, -16, 22, 32, 4); c.fillStyle = "#5C6A99"; c.fillRect(-11, -4, 22, 6); }
        else { c.fillStyle = "#C9B23A"; c.beginPath(); c.moveTo(-16, -6); c.quadraticCurveTo(0, 18, 16, -6); c.quadraticCurveTo(0, 8, -16, -6); c.fill(); c.fillStyle = "#6B4423"; c.fillRect(-18, -9, 5, 5); }
        c.restore(); });
      const x = g.cx, y = g.H - 80; c.fillStyle = "#2E86DE"; c.beginPath(); c.moveTo(x - 56, y); c.lineTo(x + 56, y); c.lineTo(x + 44, y + 40); c.lineTo(x - 44, y + 40); c.fill();
      c.strokeStyle = "#fff"; c.lineWidth = 2; for (let i = -40; i <= 40; i += 16) { c.beginPath(); c.moveTo(x + i, y + 4); c.lineTo(x + i * 0.8, y + 36); c.stroke(); }
      circ(c, x - 34, y + 48, 7, "#1D2A5B"); circ(c, x + 34, y + 48, 7, "#1D2A5B");
      for (let i = 0; i < 3; i++) { c.fillStyle = i < g.lives ? "#FF4D5E" : "rgba(29,42,91,.25)"; const hx = 22 + i * 28, hy = 56; c.beginPath(); c.moveTo(hx, hy + 8); c.bezierCurveTo(hx - 14, hy - 4, hx - 6, hy - 14, hx, hy - 5); c.bezierCurveTo(hx + 6, hy - 14, hx + 14, hy - 4, hx, hy + 8); c.fill(); }
    },
  });
});

// ------------------------------------------------------------------ 29. Puzzle 3x3 (sirpanuvchi)
reg("slayd", "Sirpanchiq puzzle", "aql", "6–10 yosh", "#2E86DE", "#D6EEFF", "#1C62A8", ICO('<rect x="4" y="4" width="16" height="16" rx="3" fill="#FF4D5E"/><rect x="22" y="4" width="16" height="16" rx="3" fill="#FFC93C"/><rect x="40" y="4" width="16" height="16" rx="3" fill="#3BB273"/><rect x="4" y="22" width="16" height="16" rx="3" fill="#7A5CFA"/><rect x="40" y="22" width="16" height="16" rx="3" fill="#23C4E8"/><rect x="4" y="40" width="16" height="16" rx="3" fill="#E5487F"/><rect x="22" y="40" width="16" height="16" rx="3" fill="#FF8A1F"/><rect x="22" y="22" width="16" height="16" rx="3" fill="none" stroke="#fff" stroke-dasharray="3 3"/>'), () => {
  S.sc = S.sc === undefined ? 0 : (S.sc + 1) % SCENES.length; S.b = [0, 1, 2, 3, 4, 5, 6, 7, 8]; S.mv = 0;
  for (let k = 0, e = 8, prev = -1; k < 80; k++) { const nb = slideNb(e).filter((x) => x !== prev); const j = nb[rnd(nb.length)]; [S.b[e], S.b[j]] = [S.b[j], S.b[e]]; prev = e; e = j; }
  drawSlide();
});
function slideNb(e) { const x = e % 3, y = Math.floor(e / 3), r = []; if (x > 0) r.push(e - 1); if (x < 2) r.push(e + 1); if (y > 0) r.push(e - 3); if (y < 2) r.push(e + 3); return r; }
function drawSlide(done) {
  const g = GBY.slayd;
  view(bar(g, hud(`${S.mv} yurish`)) + `<div class="gx-h b" style="color:#fff">Bo'sh joy yonidagi bo'lakni bos</div>
    <div class="g-pz g-slide">${S.b.map((v, i) => v === 8 && !done ? `<span class="g-empty2"></span>` : `<button class="g-tile2" data-act="slide" data-i="${i}" aria-label="${v + 1}-bo'lak">
      <svg viewBox="${(v % 3) * 100} ${Math.floor(v / 3) * 100} 100 100" aria-hidden="true">${SCENES[S.sc]}</svg></button>`).join("")}</div>
    <div class="gx-fill"></div><div class="g-pzref"><span class="b">Namuna:</span><svg viewBox="0 0 300 300" aria-hidden="true">${SCENES[S.sc]}</svg>
    ${done ? `<button class="gx-btn b" data-act="reset" style="margin-left:auto;height:46px">Keyingisi</button>` : ""}</div>`);
}
ACT.slide = (el) => {
  const i = +el.dataset.i, e = S.b.indexOf(8);
  if (!slideNb(e).includes(i)) { wrong(el); return; }
  [S.b[e], S.b[i]] = [S.b[i], S.b[e]]; S.mv++; sfx.flip(); haptic();
  const done = S.b.every((v, k) => v === k); drawSlide(done);
  if (done) yay(`${S.mv} yurishda yig'ding!`, S.mv < 60 ? 3 : 2);
};

// ------------------------------------------------------------------ 30. Nishonga tekkaz
reg("nishon", "Nishonga tekkaz", "sport", "4–10 yosh", "#DFF3FF", "#DFF3FF", "#2B9FCC", ICO('<circle cx="30" cy="30" r="24" fill="#fff"/><circle cx="30" cy="30" r="18" fill="#FF4D5E"/><circle cx="30" cy="30" r="12" fill="#fff"/><circle cx="30" cy="30" r="6" fill="#FF4D5E"/><path d="M50 10 L32 28" stroke="#2E86DE" stroke-width="4" stroke-linecap="round"/>'), () => {
  arcadeView(GBY.nishon, hud("0"), "Nishon o'rtaga kelganda bos —<br>so'rg'ichli o'q uchadi!");
  arcade({id: "nishon", stars: (s) => (s >= 70 ? 3 : s >= 45 ? 2 : s >= 20 ? 1 : 0),
    init(g) { Object.assign(g, {tx: g.W / 2, dart: null, left: 10, stuck: [], msg: null, mt: 0}); },
    tap(g) { if (g.dart || g.left <= 0) return; g.dart = {y: g.H - 120}; g.left--; tone(500, 0.1, "triangle", 0.12, 0, 900); },
    step(g, dt) {
      const sp = 1.2 + (10 - g.left) * 0.12; g.tx = g.W / 2 + Math.sin(g.t * sp) * (g.W * 0.33);
      const ty = 170;
      if (g.dart) { g.dart.y -= 900 * dt; if (g.dart.y <= ty) { const d = Math.abs(g.W / 2 - g.tx), pts = d < 12 ? 10 : d < 26 ? 5 : d < 40 ? 2 : 0;
          g.score += pts; g.msg = pts ? `+${pts}` : "Tegmadi!"; g.mt = 0.8; if (pts) { g.stuck.push(g.W / 2 - g.tx); pts === 10 ? sfx.win() : sfx.ok(); haptic("hit"); } else sfx.err();
          g.dart = null; if (g.left <= 0) later(() => g.finish(g.score >= 20), 700); } }
      if (g.mt) g.mt = Math.max(0, g.mt - dt); setTxt("gsc", `${g.score} · ${g.left} o'q`);
    },
    draw(g, c) {
      const {W, H} = g, ty = 170; c.fillStyle = "#DFF3FF"; c.fillRect(0, 0, W, H); c.fillStyle = "#9FE08F"; c.fillRect(0, H - 80, W, 80);
      c.fillStyle = "#8A5A35"; c.fillRect(g.tx - 4, ty, 8, H - 80 - ty);
      [[56, "#fff"], [44, "#FF4D5E"], [32, "#fff"], [20, "#FF4D5E"], [9, "#FFC93C"]].forEach(([r, col]) => circ(c, g.tx, ty, r, col));
      g.stuck.forEach((o) => { c.fillStyle = "#2E86DE"; rr(c, g.tx + o - 3, ty, 6, 30, 3); circ(c, g.tx + o, ty, 6, "#FF8A1F"); });
      c.strokeStyle = "rgba(29,42,91,.5)"; c.lineWidth = 2; c.setLineDash([6, 6]); c.beginPath(); c.moveTo(W / 2, ty - 70); c.lineTo(W / 2, H - 140); c.stroke(); c.setLineDash([]);
      c.strokeStyle = "#1D2A5B"; c.lineWidth = 3; c.beginPath(); c.arc(W / 2, ty, 64, 0, 7); c.moveTo(W / 2 - 74, ty); c.lineTo(W / 2 - 54, ty); c.moveTo(W / 2 + 54, ty); c.lineTo(W / 2 + 74, ty); c.stroke();
      const dy = g.dart ? g.dart.y : H - 120; if (g.left > 0 || g.dart) { c.fillStyle = "#2E86DE"; rr(c, W / 2 - 4, dy, 8, 54, 4); circ(c, W / 2, dy, 9, "#FF8A1F"); c.fillStyle = "#FFC93C"; c.beginPath(); c.moveTo(W / 2 - 12, dy + 54); c.lineTo(W / 2, dy + 40); c.lineTo(W / 2 + 12, dy + 54); c.fill(); }
      c.fillStyle = "#5C6A99"; rr(c, W / 2 - 40, H - 70, 80, 40, 14);
      if (g.mt) { c.fillStyle = g.msg === "+10" ? "#FFB020" : "#1D2A5B"; c.font = "800 34px Bal, sans-serif"; c.textAlign = "center"; c.fillText(g.msg, W / 2, ty + 120); c.textAlign = "start"; }
    },
  });
});

// =================================================================== hodisalar
document.addEventListener("click", (e) => {
  const t = e.target;
  if (!t.closest || !t.closest("#games")) return;
  ctx();
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "games" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  if (t.closest("[data-home]")) { haptic(); home(); return; }
  const gm = t.closest("[data-game]"); if (gm) { haptic(); open(gm.dataset.game); return; }
  if (t.closest("[data-chest]")) { openChest(); return; }
  { const c = t.closest("[data-cat]"); if (c) { homeCat = c.dataset.cat; lsSet("zk_gcat", homeCat); haptic(); renderHome(); return; } }
  if (!cur) return;
  let el;
  if ((el = t.closest("[data-act]")) && ACT[el.dataset.act]) return ACT[el.dataset.act](el, e);
  if ((el = t.closest("[data-say]"))) { if (!say(`${S.target} harfli sharchalarni portlat`)) tone(784, 0.2, "triangle", 0.2); return; }
  if ((el = t.closest("[data-bal]"))) return onBalloon(el);
  if ((el = t.closest("[data-card]"))) return onCard(el);
  if ((el = t.closest("[data-pick]"))) return onPoyezd(el);
  if ((el = t.closest("[data-num]"))) return onSanoq(el);
  if ((el = t.closest("[data-pic]"))) { S.pic = el.dataset.pic; haptic(); drawBoyoq(); return; }
  if ((el = t.closest("[data-col]"))) { S.col = el.dataset.col; haptic(); sfx.tap();
    document.querySelectorAll(".g-pal button").forEach((x) => x.classList.toggle("on", x === el)); return; }
  if (t.closest("[data-clear]")) { delete S.fills[S.pic]; lsSet("zk_gpaint", S.fills); haptic(); drawBoyoq(); return; }
  if ((el = t.closest("#gpaper [data-r]"))) return onPaint(el);
  if ((el = t.closest("[data-hole]"))) return onHole(el);
  if (t.closest("[data-spk]")) return playCall();
  if ((el = t.closest("[data-ani]"))) return onAnimal(el);
  if ((el = t.closest("[data-mv]"))) { const [dx, dy] = el.dataset.mv.split(",").map(Number); return move(dx, dy); }
  if ((el = t.closest("[data-wear]"))) return onWear(el);
  if (t.closest("[data-again]")) { if (S.again) { haptic(); S.again(); } return; }
  if ((el = t.closest("[data-pet]"))) return onPet(el.dataset.pet);
  if ((el = t.closest("[data-cake]"))) return onCake(el);
  if (t.closest("[data-cnext]")) { S.step++; haptic(); sfx.tap(); drawTort(); return; }
  if (t.closest("[data-cdone]")) { S.step = 4; drawTort(); happyBirthday(); later(() => yay("Mazali tort!", 2), 300); return; }
  if (t.closest("[data-cnew]")) { START.tort(); return; }
  if ((el = t.closest("[data-pz]"))) return onPz(el);
  if (t.closest("#gfarq")) return onFarq(e);
  if (t.closest("[data-fhelp]")) { const f = FEAT.find((q) => S.diff.includes(q.k) && !S.found.includes(q.k)); const svg = $("gfarq");
    if (f && svg) { svg.insertAdjacentHTML("beforeend", `<circle cx="${f.hx}" cy="${f.hy}" r="28" fill="none" stroke="#FFC93C" stroke-width="5" stroke-dasharray="6 6"/>`); haptic(); } return; }
  if ((el = t.closest("[data-ing]"))) return onIng(el.dataset.ing);
  if (t.closest("[data-chop]")) return onChop();
  if (t.closest("[data-lid]")) return onLid();
  if (t.closest("[data-onew]")) { S.lid = false; START.osh(); return; }
  if ((el = t.closest("[data-soy]"))) return onSoya(el);
  if ((el = t.closest("[data-pmode]"))) { S.mode = el.dataset.pmode; S.i = 0; haptic(); drawPiano(); return; }
  if (t.closest("[data-nsong]")) { S.song = (S.song + 1) % SONGS.length; S.i = 0; haptic(); drawPiano(); return; }
});
// Pianino: barmoq tekkan zahoti chalinsin (click 300 ms kechikishisiz)
document.addEventListener("pointerdown", (e) => {
  const b = e.target.closest && e.target.closest(".g-key");
  if (!b || !opened || cur !== "pianino") return;
  e.preventDefault(); ctx(); onKey(b);
});
document.addEventListener("keydown", (e) => {
  if (!opened || cur !== "labirint") return;
  const m = {ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0]}[e.key];
  if (m) { e.preventDefault(); move(...m); }
});

// =================================================================== Telegram «Orqaga»
function updateBack() {
  if (!inTg) return;
  try { (opened && cur) ? tg.BackButton.show() : (window.ZK_canHideBack ? window.ZK_canHideBack() && tg.BackButton.hide() : tg.BackButton.hide()); } catch (e) {}
}
if (inTg) tg.BackButton.onClick(() => { if (opened && cur) home(); });

window.ZGames = {
  open(id) {
    mounted = true; opened = true;
    $("games").hidden = false; document.body.classList.add("g-on");
    if (id && GBY[id]) open(id); else if (cur) open(cur); else renderHome();
    updateBack();
  },
  close() {
    opened = false; clearTimers(); try { speechSynthesis.cancel(); } catch (e) {}
    $("games").hidden = true; document.body.classList.remove("g-on");
    try { tg.setHeaderColor("bg_color"); tg.setBackgroundColor("bg_color"); if (tg.setBottomBarColor) tg.setBottomBarColor("bottom_bar_bg_color"); } catch (e) {}
    cur = null; updateBack();
  },
  busy() { return opened && !!cur; },
  ids: GAMES.map((g) => g.id),
};
void mounted;
})();
