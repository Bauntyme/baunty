/* 🧑 O'yinlar → «Kattalar»: ♟ Shaxmat, ⛀ Shashka, ❌⭕ X-O, 🁫 Domino, 🚢 Dengiz jangi.
   Hammasi telefonning o'zida: kompyuter (4 daraja) yoki bitta telefonda 2 kishi. Serverga so'rov yo'q.
   games.js «Kattalar» tugmasida window.ZAdult.home(el) ni chaqiradi; o'yin ichida «Orqaga» — ZAdult.back(). */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const T = window.ZK_T || ((u) => u);
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : t === "hit" ? tg.HapticFeedback.impactOccurred("medium") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const lsGet = (k, d) => { try { const v = JSON.parse(localStorage.getItem(k) || "null"); return v == null ? d : v; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const rnd = (n) => Math.floor(Math.random() * n);
const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = rnd(i + 1); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const BACK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>';

let root = null, segHtml = "", audHtml = "", game = null, timers = [];
const later = (fn, ms) => { const id = setTimeout(fn, ms); timers.push(id); return id; };
const clearTimers = () => { timers.forEach(clearTimeout); timers = []; };
const stats = lsGet("ka_stats", {});
function record(id, res) { const s = stats[id] || (stats[id] = {w: 0, l: 0, d: 0}); s[res] = (s[res] || 0) + 1; lsSet("ka_stats", stats); }

// ------------------------------------------------------------------ ovoz
let ac = null;
function tone(f, d = .08, type = "triangle", vol = .14, when = 0) {
  try {
    ac = ac || new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === "suspended") ac.resume();
    const t = ac.currentTime + when, o = ac.createOscillator(), g = ac.createGain();
    o.type = type; o.frequency.value = f;
    g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + .01); g.gain.exponentialRampToValueAtTime(.0001, t + d);
    o.connect(g).connect(ac.destination); o.start(t); o.stop(t + d + .03);
  } catch (e) {}
}
const sfx = {move: () => tone(420, .07, "sine", .16), cap: () => { tone(220, .09, "square", .07); tone(160, .12, "triangle", .12, .04); },
  win: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, .2, "triangle", .16, i * .1)), lose: () => [392, 330, 262].forEach((f, i) => tone(f, .25, "sine", .14, i * .14)),
  splash: () => tone(180, .25, "sine", .12), boom: () => { tone(90, .35, "sawtooth", .12); tone(60, .4, "square", .06, .05); }};

const GAMES = [
  {id: "chess", n: T("Shaxmat", "Шахматы", "Chess"), ic: "♞", d: T("Kompyuter (4 daraja) yoki 2 kishi", "Компьютер (4 уровня) или вдвоём", "Computer (4 levels) or 2 players"), c: "#3A2C17"},
  {id: "draughts", n: T("Shashka", "Шашки", "Draughts"), ic: "⛂", d: T("Rus qoidalari: olish majburiy, damka uzoq yuradi", "Русские правила: бить обязательно", "Russian rules: capture is mandatory"), c: "#21362A"},
  {id: "xo", n: T("X-O", "Крестики-нолики", "Tic-tac-toe"), ic: "✕", d: T("3×3 — kompyuter yoki do'st bilan", "3×3 — с компьютером или другом", "3×3 — vs computer or friend"), c: "#1F2E4A"},
  {id: "domino", n: T("Domino", "Домино", "Dominoes"), ic: "🁫", d: T("Bozordan olib — 101 ochkogacha", "С базаром — до 101 очка", "Draw game — to 101 points"), c: "#3A1E1E"},
  {id: "sea", n: T("Dengiz jangi", "Морской бой", "Battleship"), ic: "🚢", d: T("10×10, kemalarni toping va cho'ktiring", "10×10 — найди и потопи корабли", "10×10 — find and sink the fleet"), c: "#12324A"},
];

// ------------------------------------------------------------------ umumiy chizish
function wrap(inner) { root.innerHTML = `<div class="ka">${inner}</div>`; }
function bar(title, right) {
  return `<div class="ka-bar"><button class="ka-back" data-kh aria-label="${T("Orqaga", "Назад", "Back")}">${BACK}</button><b class="ka-h">${title}</b><span class="ka-r">${right || ""}</span></div>`;
}
function homeHtml() {
  return `<div class="ka">${segHtml}${audHtml}
   <div class="ka-hero"><b>${T("Aql o'yinlari", "Игры для ума", "Mind games")}</b><span>${T("Kompyuterga qarshi yoki bitta telefonda do'stingiz bilan", "Против компьютера или вдвоём на одном телефоне", "Versus the computer or a friend on one phone")}</span></div>
   <div class="ka-grid">${GAMES.map((g) => { const s = stats[g.id]; return `<button class="ka-tile" data-kg="${g.id}" style="--c:${g.c}">
     <span class="ic">${g.ic}</span><span class="tx"><b>${g.n}</b><small>${g.d}</small>${s && (s.w || s.l) ? `<em>🏆 ${s.w} · ${s.l} ${T("mag'lub", "пораж.", "lost")}</em>` : ""}</span></button>`; }).join("")}</div>
   <p class="ka-fine">${T("Reklama yo'q. Natijalar shu telefonda saqlanadi.", "Без рекламы. Результаты хранятся на этом телефоне.", "No ads. Results are saved on this phone.")}</p></div>`;
}
function setup(id, title, opts) {
  // o'yin oldidan: rejim va daraja
  const o = lsGet("ka_opt_" + id, {mode: "cpu", lvl: 2, side: "w"});
  game = {id, setup: true, o};
  const lv = (n, l) => `<button class="${o.lvl === n ? "on" : ""}" data-klvl="${n}">${l}</button>`;
  wrap(bar(title) + `<div class="ka-setup">
    <div class="ka-lh">${T("Kim bilan?", "С кем?", "Opponent")}</div>
    <div class="ka-seg3"><button class="${o.mode === "cpu" ? "on" : ""}" data-kmode="cpu">🤖 ${T("Kompyuter", "Компьютер", "Computer")}</button>${opts.two === false ? "" : `<button class="${o.mode === "two" ? "on" : ""}" data-kmode="two">👥 ${T("1 telefonda", "Вдвоём", "Same phone")}</button>`}<button class="${o.mode === "net" ? "on" : ""}" data-kmode="net">🌐 ${T("Onlayn", "Онлайн", "Online")}</button></div>
    ${o.mode === "net" ? netSetupHtml() : ""}
    ${o.mode === "cpu" ? `<div class="ka-lh">${T("Daraja", "Уровень", "Level")}</div><div class="ka-seg4">${lv(1, T("Oson", "Легко", "Easy"))}${lv(2, T("O'rta", "Средне", "Medium"))}${lv(3, T("Qiyin", "Сложно", "Hard"))}${lv(4, T("Usta", "Мастер", "Master"))}</div>
      ${opts.side ? `<div class="ka-lh">${T("Rangingiz", "Ваш цвет", "Your colour")}</div><div class="ka-seg2"><button class="${o.side === "w" ? "on" : ""}" data-kside="w">⚪ ${T("Oq", "Белые", "White")}</button><button class="${o.side === "b" ? "on" : ""}" data-kside="b">⚫ ${T("Qora", "Чёрные", "Black")}</button></div>` : ""}` : ""}
    ${o.mode === "net" ? "" : `<button class="ka-cta" data-kstart>▶ ${T("Boshlash", "Начать", "Start")}</button>`}
    ${opts.rules ? `<div class="ka-rules">${opts.rules}</div>` : ""}</div>`);
}
function resultHtml(kind, text) {
  const ic = kind === "w" ? "🏆" : kind === "l" ? "😔" : "🤝";
  return `<div class="ka-res ${kind}"><b>${ic} ${text}</b><div class="ka-row"><button class="ka-cta" data-kagain>🔁 ${T("Yana", "Ещё", "Again")}</button><button class="ka-ghost" data-kh>${T("O'yinlar", "Игры", "Games")}</button></div></div>`;
}

// =================================================================== ♞ SHAXMAT
const PV = {p: 100, n: 320, b: 330, r: 500, q: 900, k: 0};
const PST = {
  p: [0,0,0,0,0,0,0,0, 50,50,50,50,50,50,50,50, 10,10,20,30,30,20,10,10, 5,5,10,25,25,10,5,5, 0,0,0,20,20,0,0,0, 5,-5,-10,0,0,-10,-5,5, 5,10,10,-20,-20,10,10,5, 0,0,0,0,0,0,0,0],
  n: [-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,0,0,0,0,-20,-40, -30,0,10,15,15,10,0,-30, -30,5,15,20,20,15,5,-30, -30,0,15,20,20,15,0,-30, -30,5,10,15,15,10,5,-30, -40,-20,0,5,5,0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50],
  b: [-20,-10,-10,-10,-10,-10,-10,-20, -10,0,0,0,0,0,0,-10, -10,0,5,10,10,5,0,-10, -10,5,5,10,10,5,5,-10, -10,0,10,10,10,10,0,-10, -10,10,10,10,10,10,10,-10, -10,5,0,0,0,0,5,-10, -20,-10,-10,-10,-10,-10,-10,-20],
  r: [0,0,0,0,0,0,0,0, 5,10,10,10,10,10,10,5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, 0,0,0,5,5,0,0,0],
  q: [-20,-10,-10,-5,-5,-10,-10,-20, -10,0,0,0,0,0,0,-10, -10,0,5,5,5,5,0,-10, -5,0,5,5,5,5,0,-5, 0,0,5,5,5,5,0,-5, -10,5,5,5,5,5,0,-10, -10,0,5,0,0,0,0,-10, -20,-10,-10,-5,-5,-10,-10,-20],
  k: [-30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30, -20,-30,-30,-40,-40,-30,-30,-20, -10,-20,-20,-20,-20,-20,-20,-10, 20,20,0,0,0,0,20,20, 20,30,10,0,0,10,30,20],
};
const isW = (p) => p && p === p.toUpperCase();
const sideOf = (p) => (p ? (isW(p) ? "w" : "b") : null);
const KN = [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]];
const KG = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
const DIAG = [[-1, -1], [-1, 1], [1, -1], [1, 1]], ORTH = [[-1, 0], [1, 0], [0, -1], [0, 1]];
function chessStart() {
  const b = "rnbqkbnrpppppppp" + " ".repeat(32) + "PPPPPPPPRNBQKBNR";
  return {b: b.split("").map((c) => (c === " " ? "" : c)), side: "w", cr: "KQkq", ep: -1, half: 0};
}
function attacked(b, sq, by) {
  const r = sq >> 3, f = sq & 7;
  const at = (rr, ff) => (rr >= 0 && rr < 8 && ff >= 0 && ff < 8 ? b[rr * 8 + ff] : null);
  const own = (p, t) => p && sideOf(p) === by && p.toLowerCase() === t;
  const pd = by === "w" ? 1 : -1;
  if (own(at(r + pd, f - 1), "p") || own(at(r + pd, f + 1), "p")) return true;
  for (const [dr, df] of KN) if (own(at(r + dr, f + df), "n")) return true;
  for (const [dr, df] of KG) if (own(at(r + dr, f + df), "k")) return true;
  for (const [dirs, ts] of [[DIAG, "bq"], [ORTH, "rq"]]) {
    for (const [dr, df] of dirs) {
      let rr = r + dr, ff = f + df;
      while (rr >= 0 && rr < 8 && ff >= 0 && ff < 8) {
        const p = b[rr * 8 + ff];
        if (p) { if (sideOf(p) === by && ts.includes(p.toLowerCase())) return true; break; }
        rr += dr; ff += df;
      }
    }
  }
  return false;
}
const kingSq = (b, s) => b.indexOf(s === "w" ? "K" : "k");
const inCheck = (st, s) => attacked(st.b, kingSq(st.b, s), s === "w" ? "b" : "w");
function pseudo(st, capsOnly) {
  const b = st.b, s = st.side, out = [];
  const add = (f, t, extra) => { const c = b[t]; if (capsOnly && !c && !(extra && extra.ep)) return; out.push(Object.assign({f, t, p: b[f], c}, extra)); };
  for (let i = 0; i < 64; i++) {
    const p = b[i];
    if (!p || sideOf(p) !== s) continue;
    const r = i >> 3, f = i & 7, t = p.toLowerCase();
    if (t === "p") {
      const d = s === "w" ? -1 : 1, start = s === "w" ? 6 : 1, last = s === "w" ? 0 : 7;
      const one = (r + d) * 8 + f;
      if (r + d >= 0 && r + d < 8 && !b[one] && !capsOnly) {
        if (r + d === last) add(i, one, {pr: s === "w" ? "Q" : "q"}); else add(i, one);
        const two = (r + 2 * d) * 8 + f;
        if (r === start && !b[two]) add(i, two, {dbl: true});
      }
      for (const df of [-1, 1]) {
        const ff = f + df, rr = r + d;
        if (ff < 0 || ff > 7 || rr < 0 || rr > 7) continue;
        const tq = rr * 8 + ff;
        if (b[tq] && sideOf(b[tq]) !== s) { if (rr === last) add(i, tq, {pr: s === "w" ? "Q" : "q"}); else add(i, tq); }
        else if (tq === st.ep) add(i, tq, {ep: true, c: s === "w" ? "p" : "P"});
      }
    } else if (t === "n" || t === "k") {
      for (const [dr, df] of t === "n" ? KN : KG) {
        const rr = r + dr, ff = f + df;
        if (rr < 0 || rr > 7 || ff < 0 || ff > 7) continue;
        const q = rr * 8 + ff;
        if (!b[q] || sideOf(b[q]) !== s) add(i, q);
      }
      if (t === "k" && !capsOnly) {
        const opp = s === "w" ? "b" : "w", home = s === "w" ? 60 : 4;
        if (i === home && !attacked(b, i, opp)) {
          const K = s === "w" ? "K" : "k", Q = s === "w" ? "Q" : "q";
          if (st.cr.includes(K) && !b[i + 1] && !b[i + 2] && b[i + 3] === (s === "w" ? "R" : "r") && !attacked(b, i + 1, opp) && !attacked(b, i + 2, opp)) add(i, i + 2, {cs: "k"});
          if (st.cr.includes(Q) && !b[i - 1] && !b[i - 2] && !b[i - 3] && b[i - 4] === (s === "w" ? "R" : "r") && !attacked(b, i - 1, opp) && !attacked(b, i - 2, opp)) add(i, i - 2, {cs: "q"});
        }
      }
    } else {
      const dirs = t === "b" ? DIAG : t === "r" ? ORTH : DIAG.concat(ORTH);
      for (const [dr, df] of dirs) {
        let rr = r + dr, ff = f + df;
        while (rr >= 0 && rr < 8 && ff >= 0 && ff < 8) {
          const q = rr * 8 + ff;
          if (b[q]) { if (sideOf(b[q]) !== s) add(i, q); break; }
          add(i, q);
          rr += dr; ff += df;
        }
      }
    }
  }
  return out;
}
function make(st, m) {
  const b = st.b.slice(), s = st.side;
  b[m.t] = m.pr || b[m.f]; b[m.f] = "";
  if (m.ep) b[m.t + (s === "w" ? 8 : -8)] = "";
  if (m.cs === "k") { b[m.t - 1] = b[m.t + 1]; b[m.t + 1] = ""; }
  if (m.cs === "q") { b[m.t + 1] = b[m.t - 2]; b[m.t - 2] = ""; }
  let cr = st.cr;
  const strip = (sq) => { if (sq === 60) cr = cr.replace("K", "").replace("Q", ""); if (sq === 4) cr = cr.replace("k", "").replace("q", "");
    if (sq === 63) cr = cr.replace("K", ""); if (sq === 56) cr = cr.replace("Q", ""); if (sq === 7) cr = cr.replace("k", ""); if (sq === 0) cr = cr.replace("q", ""); };
  strip(m.f); strip(m.t);
  return {b, side: s === "w" ? "b" : "w", cr, ep: m.dbl ? (m.f + m.t) >> 1 : -1, half: m.c || m.p.toLowerCase() === "p" ? 0 : st.half + 1};
}
function legal(st) { return pseudo(st).filter((m) => !inCheck(make(st, m), st.side)); }
function evalChess(st) {
  let sc = 0;
  for (let i = 0; i < 64; i++) {
    const p = st.b[i];
    if (!p) continue;
    const t = p.toLowerCase();
    const v = PV[t] + PST[t][isW(p) ? i : (7 - (i >> 3)) * 8 + (i & 7)];
    sc += isW(p) ? v : -v;
  }
  return st.side === "w" ? sc : -sc;
}
const mvv = (m) => (m.c ? PV[m.c.toLowerCase()] * 10 - PV[m.p.toLowerCase()] / 10 : 0) + (m.pr ? 800 : 0);
let deadline = 0, aborted = false, nodes = 0;
function quiesce(st, a, b, d) {
  const sp = evalChess(st);
  if (sp >= b) return b;
  if (sp > a) a = sp;
  if (d <= 0) return a;
  const ms = pseudo(st, true).sort((x, y) => mvv(y) - mvv(x));
  for (const m of ms) {
    const n = make(st, m);
    if (inCheck(n, st.side)) continue;
    const s = -quiesce(n, -b, -a, d - 1);
    if (s >= b) return b;
    if (s > a) a = s;
  }
  return a;
}
function search(st, depth, a, b, ply) {
  if ((++nodes & 1023) === 0 && performance.now() > deadline) aborted = true;
  if (aborted) return 0;
  if (depth <= 0) return quiesce(st, a, b, 4);
  const ms = pseudo(st).sort((x, y) => mvv(y) - mvv(x));
  let any = false;
  for (const m of ms) {
    const n = make(st, m);
    if (inCheck(n, st.side)) continue;
    any = true;
    const s = -search(n, depth - 1, -b, -a, ply + 1);
    if (aborted) return 0;
    if (s >= b) return b;
    if (s > a) a = s;
  }
  if (!any) return inCheck(st, st.side) ? -100000 + ply : 0;
  return a;
}
function chessAI(st, lvl) {
  const ms = shuffle(legal(st));
  if (!ms.length) return null;
  if (lvl === 1 && Math.random() < .35) return ms[rnd(ms.length)];
  const budget = [0, 120, 450, 1100, 2200][lvl];
  deadline = performance.now() + budget; aborted = false; nodes = 0;
  let best = ms[0];
  for (let d = 1; d <= 6; d++) {
    let bd = null, bs = -Infinity;
    const ord = [best].concat(ms.filter((m) => m !== best));
    for (const m of ord) {
      const s = -search(make(st, m), d - 1, -Infinity, -bs === Infinity ? Infinity : -bs, 1);
      if (aborted) break;
      if (s > bs) { bs = s; bd = m; }
    }
    if (aborted) break;
    if (bd) best = bd;
    if (lvl <= 2 && d >= lvl + 1) break;
  }
  return best;
}
// donalar — o'zimiz chizgan SVG (shrift har xil telefonda har xil ko'rinmasin)
const PIECE = {
  p: '<circle cx="22.5" cy="15" r="5.5"/><path d="M17 21h11l-2 6c3 2 5 5 5 9H14c0-4 2-7 5-9z"/><rect x="11" y="36" width="23" height="4" rx="1.5"/>',
  r: '<path d="M12 9h4v3h3V9h7v3h3V9h4v7l-3 2v14l3 3v2H12v-2l3-3V18l-3-2z"/><rect x="10" y="37" width="25" height="4" rx="1.5"/>',
  n: '<path d="M14 37c0-8 3-11 8-15-4 1-6 0-8 2-2-1-3-4-1-6 4-6 9-10 15-10 6 1 9 7 9 15 0 6-1 10-1 14z"/><circle cx="21" cy="14" r="1.6" class="e"/><rect x="11" y="36" width="25" height="5" rx="1.5"/>',
  b: '<circle cx="22.5" cy="8" r="2.8"/><path d="M22.5 11c-6 4-8 9-8 13 0 3 2 5 4 6h8c2-1 4-3 4-6 0-4-2-9-8-13z"/><path d="M24 17l-4 5" class="e" stroke-width="1.6"/><path d="M15 31h15l1 4H14z"/><rect x="10" y="36" width="25" height="4" rx="1.5"/>',
  q: '<circle cx="9" cy="11" r="2.4"/><circle cx="16" cy="8" r="2.4"/><circle cx="22.5" cy="7" r="2.4"/><circle cx="29" cy="8" r="2.4"/><circle cx="36" cy="11" r="2.4"/><path d="M9 13l4 15h19l4-15-6 9-3-12-4 12-4-12-3 12z"/><path d="M13 29h19l1 5H12z"/><rect x="10" y="36" width="25" height="4" rx="1.5"/>',
  k: '<path d="M21 3h3v4h3v3h-3v4h-3v-4h-3V7h3z"/><path d="M22.5 15c-8 0-13 4-12 9 1 4 3 6 3 8h18c0-2 2-4 3-8 1-5-4-9-12-9z"/><path d="M13 33h19l1 3H12z"/><rect x="10" y="37" width="25" height="4" rx="1.5"/>',
};
const pieceSvg = (p) => `<svg viewBox="0 0 45 45" class="pc ${isW(p) ? "w" : "b"}">${PIECE[p.toLowerCase()]}</svg>`;
function chessNew() {
  const o = game.o;
  game = {id: "chess", o, st: chessStart(), sel: -1, last: null, hist: [], over: null, me: o.mode === "cpu" ? o.side : null, think: false, caps: {w: [], b: []}};
  drawChess();
  if (game.me && game.me !== "w") later(chessCpu, 400);
}
function chessStatus() {
  const st = game.st, ms = legal(st);
  if (!ms.length) return inCheck(st, st.side) ? "mate" : "stale";
  if (st.half >= 100) return "fifty";
  const left = st.b.filter(Boolean);
  if (left.length === 2) return "draw";
  return null;
}
function chessDo(m, remote) {
  game.ply = (game.ply || 0) + 1;
  if (m.c) game.caps[sideOf(m.p)].push(m.c);
  game.hist.push({st: game.st, caps: {w: game.caps.w.slice(), b: game.caps.b.slice()}, last: game.last});
  game.st = make(game.st, m);
  game.last = m; game.sel = -1;
  m.c ? sfx.cap() : sfx.move(); haptic();
  const s = chessStatus();
  if (s) {
    game.over = s;
    if (s === "mate") {
      const winner = game.st.side === "w" ? "b" : "w";
      if (game.me) { record("chess", winner === game.me ? "w" : "l"); winner === game.me ? sfx.win() : sfx.lose(); } else sfx.win();
    } else if (game.me) record("chess", "d");
  }
  if (game.net && !remote) netSend({f: m.f, t: m.t, pr: m.pr ? 1 : 0}, s ? (s === "mate" ? sideOf(m.p) : "d") : null, s);
  drawChess();
  if (!game.net && !game.over && game.me && game.st.side !== game.me) later(chessCpu, 250);
}
function chessCpu() {
  if (!game || game.id !== "chess" || game.over) return;
  game.think = true; drawChess();
  later(() => {
    const m = chessAI(game.st, game.o.lvl);
    game.think = false;
    if (m) chessDo(m);
  }, 60);
}
function drawChess() {
  const g = game, st = g.st, flip = g.me === "b";
  const moves = g.sel >= 0 ? legal(st).filter((m) => m.f === g.sel) : [];
  const tg2 = new Set(moves.map((m) => m.t));
  const chk = inCheck(st, st.side) ? kingSq(st.b, st.side) : -1;
  let cells = "";
  for (let k = 0; k < 64; k++) {
    const i = flip ? 63 - k : k, r = i >> 3, f = i & 7, light = (r + f) % 2 === 0, p = st.b[i];
    const cls = ["sq", light ? "l" : "d", g.last && (g.last.f === i || g.last.t === i) ? "lm" : "", g.sel === i ? "sel" : "", i === chk ? "chk" : "", tg2.has(i) ? (p ? "cap" : "mv") : ""].join(" ");
    const co = (flip ? f === 7 : f === 0) ? `<i class="co r">${8 - r}</i>` : "";
    const cf = (flip ? r === 0 : r === 7) ? `<i class="co f">${"abcdefgh"[f]}</i>` : "";
    cells += `<button class="${cls}" data-csq="${i}">${co}${cf}${p ? pieceSvg(p) : ""}</button>`;
  }
  const capRow = (s) => g.caps[s].map((c) => pieceSvg(c)).join("");
  const who = (s) => (g.net ? netWho(s) : g.me ? (s === g.me ? T("Siz", "Вы", "You") : `🤖 ${["", T("Oson", "Легко", "Easy"), T("O'rta", "Средне", "Medium"), T("Qiyin", "Сложно", "Hard"), T("Usta", "Мастер", "Master")][g.o.lvl]}`) : (s === "w" ? T("Oqlar", "Белые", "White") : T("Qoralar", "Чёрные", "Black")));
  const topS = flip ? "w" : "b", botS = flip ? "b" : "w";
  let res = "";
  if (g.netOver && !g.over) res = netResHtml(g);
  else if (g.over) {
    if (g.over === "mate") { const wnr = st.side === "w" ? "b" : "w"; res = resultHtml(g.me ? (wnr === g.me ? "w" : "l") : "w", g.me ? (wnr === g.me ? T("Mat! Siz yutdingiz", "Мат! Вы выиграли", "Checkmate! You win") : (g.net ? T("Mat. Raqib yutdi", "Мат. Победил соперник", "Checkmate. Opponent wins") : T("Mat. Kompyuter yutdi", "Мат. Победил компьютер", "Checkmate. Computer wins"))) : (wnr === "w" ? T("Mat! Oqlar yutdi", "Мат! Белые победили", "Checkmate! White wins") : T("Mat! Qoralar yutdi", "Мат! Чёрные победили", "Checkmate! Black wins"))); }
    else res = resultHtml("d", g.over === "stale" ? T("Pat — durang", "Пат — ничья", "Stalemate — draw") : T("Durang", "Ничья", "Draw"));
  }
  wrap(bar("♞ " + T("Shaxmat", "Шахматы", "Chess"), g.net ? netPill(g, st.side) : g.think ? `<span class="ka-think">🤖 ${T("o'ylayapti…", "думает…", "thinking…")}</span>` : chk >= 0 && !g.over ? `<span class="ka-pill r">${T("Shoh!", "Шах!", "Check!")}</span>` : "") + `
   <div class="ka-pl ${st.side === topS && !g.over ? "on" : ""}"><b>${who(topS)}</b><span class="caps">${capRow(topS)}</span></div>
   <div class="ka-board chess">${cells}</div>
   <div class="ka-pl ${st.side === botS && !g.over ? "on" : ""}"><b>${who(botS)}</b><span class="caps">${capRow(botS)}</span></div>
   ${g.net ? netCtl(g) : `<div class="ka-row"><button class="ka-ghost" data-kundo${!g.hist.length || g.think ? " disabled" : ""}>↩️ ${T("Qaytarish", "Отменить", "Undo")}</button><button class="ka-ghost" data-knew>🔄 ${T("Yangi o'yin", "Новая игра", "New game")}</button></div>`}${res}`);
}
function chessTap(i) {
  const g = game;
  if (g.over || g.netOver || g.think || (g.me && g.st.side !== g.me)) return;
  const p = g.st.b[i];
  if (g.sel >= 0) {
    const m = legal(g.st).find((x) => x.f === g.sel && x.t === i);
    if (m) { chessDo(m); return; }
  }
  if (p && sideOf(p) === g.st.side) { g.sel = g.sel === i ? -1 : i; haptic(); drawChess(); return; }
  g.sel = -1; drawChess();
}
function chessUndo() {
  const g = game;
  if (!g.hist.length || g.think) return;
  const n = g.me && g.hist.length >= 2 && g.st.side === g.me ? 2 : 1;
  for (let k = 0; k < n && g.hist.length; k++) { const h = g.hist.pop(); g.st = h.st; g.caps = h.caps; g.last = h.last; }
  g.over = null; g.sel = -1; drawChess();
  if (g.me && g.st.side !== g.me) later(chessCpu, 300);
}

// =================================================================== ⛂ SHASHKA (rus qoidalari)
const dark = (r, f) => (r + f) % 2 === 1;
function drStart() {
  const b = Array(64).fill("");
  for (let r = 0; r < 8; r++) for (let f = 0; f < 8; f++) if (dark(r, f)) { if (r < 3) b[r * 8 + f] = "b"; else if (r > 4) b[r * 8 + f] = "w"; }
  return {b, side: "w"};
}
const own = (p, s) => p && p.toLowerCase() === s;
const isKing = (p) => p === "W" || p === "B";
function drCaptures(st) {
  const b = st.b, s = st.side, opp = s === "w" ? "b" : "w", res = [];
  const lastRow = s === "w" ? 0 : 7;
  function dfs(bd, sq, king, path, caps) {
    const r = sq >> 3, f = sq & 7;
    let found = false;
    for (const [dr, df] of DIAG) {
      if (!king) {
        const r1 = r + dr, f1 = f + df, r2 = r + 2 * dr, f2 = f + 2 * df;
        if (r2 < 0 || r2 > 7 || f2 < 0 || f2 > 7) continue;
        const mid = r1 * 8 + f1, to = r2 * 8 + f2;
        if (own(bd[mid], opp) && !caps.includes(mid) && !bd[to]) {
          found = true;
          const nb = bd.slice(); nb[to] = nb[sq]; nb[sq] = "";
          const prom = r2 === lastRow;
          dfs(nb, to, prom, path.concat(to), caps.concat(mid));
        }
      } else {
        let rr = r + dr, ff = f + df, enemy = -1;
        while (rr >= 0 && rr < 8 && ff >= 0 && ff < 8) {
          const q = rr * 8 + ff;
          if (enemy < 0) {
            if (bd[q]) { if (own(bd[q], opp) && !caps.includes(q)) enemy = q; else break; }
          } else {
            if (bd[q]) break;
            found = true;
            const nb = bd.slice(); nb[q] = nb[sq]; nb[sq] = "";
            dfs(nb, q, true, path.concat(q), caps.concat(enemy));
          }
          rr += dr; ff += df;
        }
      }
    }
    if (!found && caps.length) res.push({path, caps, prom: king && !isKing(b[path[0]])});
  }
  for (let i = 0; i < 64; i++) if (own(b[i], s)) dfs(b, i, isKing(b[i]), [i], []);
  return res;
}
function drMoves(st) {
  const caps = drCaptures(st);
  if (caps.length) return caps;
  const b = st.b, s = st.side, out = [], fwd = s === "w" ? -1 : 1, lastRow = s === "w" ? 0 : 7;
  for (let i = 0; i < 64; i++) {
    if (!own(b[i], s)) continue;
    const r = i >> 3, f = i & 7;
    if (isKing(b[i])) {
      for (const [dr, df] of DIAG) { let rr = r + dr, ff = f + df; while (rr >= 0 && rr < 8 && ff >= 0 && ff < 8 && !b[rr * 8 + ff]) { out.push({path: [i, rr * 8 + ff], caps: []}); rr += dr; ff += df; } }
    } else {
      for (const df of [-1, 1]) { const rr = r + fwd, ff = f + df; if (rr >= 0 && rr < 8 && ff >= 0 && ff < 8 && !b[rr * 8 + ff]) out.push({path: [i, rr * 8 + ff], caps: [], prom: rr === lastRow}); }
    }
  }
  return out;
}
function drMake(st, m) {
  const b = st.b.slice(), from = m.path[0], to = m.path[m.path.length - 1];
  let p = b[from];
  b[from] = "";
  m.caps.forEach((c) => { b[c] = ""; });
  if (m.prom || (!isKing(p) && (to >> 3) === (st.side === "w" ? 0 : 7))) p = p.toUpperCase();
  b[to] = p;
  return {b, side: st.side === "w" ? "b" : "w"};
}
function drEval(st) {
  let s = 0;
  for (let i = 0; i < 64; i++) {
    const p = st.b[i];
    if (!p) continue;
    const r = i >> 3, f = i & 7;
    let v = isKing(p) ? 320 : 100 + (p === "w" ? (7 - r) * 4 : r * 4);
    if (f === 0 || f === 7) v += 4;
    s += own(p, "w") ? v : -v;
  }
  return st.side === "w" ? s : -s;
}
function drSearch(st, d, a, b) {
  if ((++nodes & 511) === 0 && performance.now() > deadline) aborted = true;
  if (aborted) return 0;
  const ms = drMoves(st);
  if (!ms.length) return -100000 - d;
  if (d <= 0 && !ms[0].caps.length) return drEval(st);
  if (d <= -6) return drEval(st);
  for (const m of ms) {
    const s = -drSearch(drMake(st, m), d - 1, -b, -a);
    if (aborted) return 0;
    if (s >= b) return b;
    if (s > a) a = s;
  }
  return a;
}
function drAI(st, lvl) {
  const ms = shuffle(drMoves(st));
  if (!ms.length) return null;
  if (lvl === 1 && Math.random() < .4) return ms[rnd(ms.length)];
  deadline = performance.now() + [0, 150, 450, 1000, 2000][lvl]; aborted = false; nodes = 0;
  let best = ms[0];
  for (let d = 1; d <= 12; d++) {
    let bd = null, bs = -Infinity;
    for (const m of [best].concat(ms.filter((x) => x !== best))) {
      const s = -drSearch(drMake(st, m), d - 1, -Infinity, -bs === Infinity ? Infinity : -bs);
      if (aborted) break;
      if (s > bs) { bs = s; bd = m; }
    }
    if (aborted) break;
    if (bd) best = bd;
    if (lvl === 2 && d >= 3) break;
  }
  return best;
}
function drNew() {
  const o = game.o;
  game = {id: "draughts", o, st: drStart(), sel: -1, last: null, hist: [], over: null, me: o.mode === "cpu" ? o.side : null, think: false};
  drawDr();
  if (game.me && game.me !== "w") later(drCpu, 400);
}
function drDo(m, remote) {
  game.ply = (game.ply || 0) + 1;
  game.hist.push({st: game.st, last: game.last});
  game.st = drMake(game.st, m); game.last = m; game.sel = -1;
  m.caps.length ? sfx.cap() : sfx.move(); haptic();
  if (!drMoves(game.st).length) {
    const winner = game.st.side === "w" ? "b" : "w";
    game.over = winner;
    if (game.me) { record("draughts", winner === game.me ? "w" : "l"); winner === game.me ? sfx.win() : sfx.lose(); } else sfx.win();
  }
  if (game.net && !remote) netSend({p: m.path}, game.over || null, game.over ? "end" : null);
  drawDr();
  if (!game.net && !game.over && game.me && game.st.side !== game.me) later(drCpu, 300);
}
function drCpu() {
  if (!game || game.id !== "draughts" || game.over) return;
  game.think = true; drawDr();
  later(() => { const m = drAI(game.st, game.o.lvl); game.think = false; if (m) drDo(m); }, 60);
}
function drawDr() {
  const g = game, st = g.st, flip = g.me === "b";
  const all = drMoves(st), mine = g.sel >= 0 ? all.filter((m) => m.path[0] === g.sel) : [];
  const dest = new Set(mine.map((m) => m.path[m.path.length - 1]));
  const must = new Set(all.length && all[0].caps.length ? all.map((m) => m.path[0]) : []);
  const lastSq = g.last ? new Set(g.last.path) : new Set();
  let cells = "";
  for (let k = 0; k < 64; k++) {
    const i = flip ? 63 - k : k, r = i >> 3, f = i & 7, p = st.b[i];
    const cls = ["sq", dark(r, f) ? "d" : "l", lastSq.has(i) ? "lm" : "", g.sel === i ? "sel" : "", dest.has(i) ? "mv" : "", must.has(i) && !g.over && (!g.me || st.side === g.me) ? "must" : ""].join(" ");
    cells += `<button class="${cls}" data-dsq="${i}">${p ? `<span class="dc ${own(p, "w") ? "w" : "b"}${isKing(p) ? " k" : ""}">${isKing(p) ? "♛" : ""}</span>` : ""}</button>`;
  }
  const count = (s) => st.b.filter((p) => own(p, s)).length;
  const who = (s) => (g.net ? netWho(s) : g.me ? (s === g.me ? T("Siz", "Вы", "You") : "🤖 " + T("Kompyuter", "Компьютер", "Computer")) : (s === "w" ? T("Oqlar", "Белые", "White") : T("Qoralar", "Чёрные", "Black")));
  const topS = flip ? "w" : "b", botS = flip ? "b" : "w";
  const res = g.netOver && !g.over ? netResHtml(g) : g.over ? resultHtml(g.me ? (g.over === g.me ? "w" : "l") : "w", g.me ? (g.over === g.me ? T("Siz yutdingiz!", "Вы победили!", "You win!") : g.net ? T("Raqib yutdi", "Победил соперник", "Opponent wins") : T("Kompyuter yutdi", "Победил компьютер", "Computer wins")) : (g.over === "w" ? T("Oqlar yutdi!", "Белые победили!", "White wins!") : T("Qoralar yutdi!", "Чёрные победили!", "Black wins!"))) : "";
  const hint = !g.over && all.length && all[0].caps.length && (!g.me || st.side === g.me) ? `<p class="ka-hint r">⚡ ${T("Olish majburiy!", "Бить обязательно!", "Capture is mandatory!")}</p>` : "";
  wrap(bar("⛂ " + T("Shashka", "Шашки", "Draughts"), g.net ? netPill(g, st.side) : g.think ? `<span class="ka-think">🤖 ${T("o'ylayapti…", "думает…", "thinking…")}</span>` : "") + `
   <div class="ka-pl ${st.side === topS && !g.over ? "on" : ""}"><b>${who(topS)}</b><span class="cnt">${count(topS)} ⛀</span></div>
   <div class="ka-board drafts">${cells}</div>
   <div class="ka-pl ${st.side === botS && !g.over ? "on" : ""}"><b>${who(botS)}</b><span class="cnt">${count(botS)} ⛀</span></div>
   ${hint}${g.net ? netCtl(g) : `<div class="ka-row"><button class="ka-ghost" data-kundo${!g.hist.length || g.think ? " disabled" : ""}>↩️ ${T("Qaytarish", "Отменить", "Undo")}</button><button class="ka-ghost" data-knew>🔄 ${T("Yangi o'yin", "Новая игра", "New game")}</button></div>`}${res}`);
}
function drTap(i) {
  const g = game;
  if (g.over || g.netOver || g.think || (g.me && g.st.side !== g.me)) return;
  const all = drMoves(g.st);
  if (g.sel >= 0) {
    const m = all.find((x) => x.path[0] === g.sel && x.path[x.path.length - 1] === i);
    if (m) { drDo(m); return; }
  }
  if (all.some((m) => m.path[0] === i)) { g.sel = g.sel === i ? -1 : i; haptic(); drawDr(); return; }
  if (own(g.st.b[i], g.st.side)) { haptic("err"); }
  g.sel = -1; drawDr();
}
function drUndo() {
  const g = game;
  if (!g.hist.length || g.think) return;
  const n = g.me && g.hist.length >= 2 && g.st.side === g.me ? 2 : 1;
  for (let k = 0; k < n && g.hist.length; k++) { const h = g.hist.pop(); g.st = h.st; g.last = h.last; }
  g.over = null; g.sel = -1; drawDr();
  if (g.me && g.st.side !== g.me) later(drCpu, 300);
}

// =================================================================== ✕ X-O
const LINES = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]];
const xoWin = (b) => { for (const l of LINES) if (b[l[0]] && b[l[0]] === b[l[1]] && b[l[0]] === b[l[2]]) return {s: b[l[0]], l}; return b.every(Boolean) ? {s: "d"} : null; };
function xoMinimax(b, me, turn, dp = 0) {
  const w = xoWin(b);
  if (w) return w.s === "d" ? 0 : w.s === me ? 10 - dp : dp - 10;
  const sc = [];
  for (let i = 0; i < 9; i++) if (!b[i]) { b[i] = turn; sc.push(xoMinimax(b, me, turn === "X" ? "O" : "X", dp + 1)); b[i] = ""; }
  return turn === me ? Math.max(...sc) : Math.min(...sc);
}
function xoAI(b, me, lvl) {
  const free = b.map((v, i) => (v ? -1 : i)).filter((i) => i >= 0);
  if (lvl === 1 || (lvl === 2 && Math.random() < .45)) {
    for (const s of [me, me === "X" ? "O" : "X"]) for (const i of free) { const c = b.slice(); c[i] = s; if (xoWin(c) && xoWin(c).s === s && lvl > 1) return i; }
    return free[rnd(free.length)];
  }
  let best = free[0], bs = -Infinity;
  for (const i of shuffle(free)) { b[i] = me; const s = xoMinimax(b, me, me === "X" ? "O" : "X"); b[i] = ""; if (s > bs) { bs = s; best = i; } }
  return best;
}
function xoNew() {
  const o = game.o;
  const sc = game.score || {X: 0, O: 0, d: 0};
  const first = game.first === "O" ? "X" : "O";
  game = {id: "xo", o, b: Array(9).fill(""), turn: game.first ? first : "X", first: game.first ? first : "X", me: o.mode === "cpu" ? "X" : null, over: null, score: sc};
  drawXo();
  if (game.me && game.turn !== game.me) later(xoCpu, 450);
}
function xoDo(i, remote) {
  const g = game;
  g.ply = (g.ply || 0) + 1;
  g.b[i] = g.turn; sfx.move(); haptic();
  const w = xoWin(g.b);
  if (w) {
    g.over = w; g.score[w.s] = (g.score[w.s] || 0) + 1;
    if (g.me) { record("xo", w.s === "d" ? "d" : w.s === g.me ? "w" : "l"); w.s === g.me ? sfx.win() : w.s !== "d" ? sfx.lose() : 0; } else if (w.s !== "d") sfx.win();
  } else g.turn = g.turn === "X" ? "O" : "X";
  if (g.net && !remote) netSend({i}, w ? (w.s === "d" ? "d" : w.s === "X" ? "w" : "b") : null, w ? "end" : null);
  drawXo();
  if (!g.net && !g.over && g.me && g.turn !== g.me) later(xoCpu, 380);
}
function xoCpu() { if (!game || game.id !== "xo" || game.over) return; xoDo(xoAI(game.b.slice(), game.turn, game.o.lvl)); }
function drawXo() {
  const g = game;
  const win = g.over && g.over.l ? new Set(g.over.l) : new Set();
  const cells = g.b.map((v, i) => `<button class="xo ${v ? v.toLowerCase() : ""} ${win.has(i) ? "win" : ""}" data-xo="${i}">${v === "X" ? '<svg viewBox="0 0 40 40"><path d="M9 9l22 22M31 9L9 31"/></svg>' : v === "O" ? '<svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="12"/></svg>' : ""}</button>`).join("");
  const name = (s) => (g.net ? (s === g.me ? T("Siz", "Вы", "You") : "🌐 " + g.net.opp) : g.me ? (s === g.me ? T("Siz", "Вы", "You") : "🤖") : s);
  let res = "";
  if (g.netOver && !g.over) res = netResHtml(g);
  else if (g.over) {
    const s = g.over.s;
    res = resultHtml(s === "d" ? "d" : g.me ? (s === g.me ? "w" : "l") : "w", s === "d" ? T("Durang", "Ничья", "Draw") : g.me ? (s === g.me ? T("Siz yutdingiz!", "Вы победили!", "You win!") : g.net ? T("Raqib yutdi", "Победил соперник", "Opponent wins") : T("Kompyuter yutdi", "Победил компьютер", "Computer wins")) : `${s} ${T("yutdi!", "победил!", "wins!")}`);
  }
  wrap(bar("✕ X-O", g.net ? netPill(g, g.turn === "X" ? "w" : "b") : `<span class="ka-pill">✕ ${g.score.X} · ${g.score.d} · ${g.score.O} ◯</span>`) + `
   <div class="ka-turn">${g.over ? "" : `${T("Navbat", "Ход", "Turn")}: <b class="${g.turn.toLowerCase()}">${g.turn}</b> ${g.me ? `(${name(g.turn)})` : ""}`}</div>
   <div class="ka-xo">${cells}</div>
   ${g.net ? netCtl(g) : `<div class="ka-row"><button class="ka-ghost" data-knew>🔄 ${T("Yangi raund", "Новый раунд", "New round")}</button></div>`}${res}`);
}

// =================================================================== 🁫 DOMINO (bozordan olib, 101 gacha)
const tilesAll = () => { const a = []; for (let i = 0; i <= 6; i++) for (let j = i; j <= 6; j++) a.push([i, j]); return a; };
const pips = (t) => t[0] + t[1];
const PIPPOS = {0: [], 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8]};
const half = (n) => `<span class="dh">${Array.from({length: 9}, (_, k) => `<i${PIPPOS[n].includes(k) ? ' class="on"' : ""}></i>`).join("")}</span>`;
const tileHtml = (t, cls = "", attr = "") => `<span class="dt ${t[0] === t[1] ? "dbl" : ""} ${cls}" ${attr}>${half(t[0])}<b></b>${half(t[1])}</span>`;
function dmNew(keepScore) {
  const o = game.o;
  const score = keepScore && game.score ? game.score : {me: 0, cpu: 0};
  const deck = shuffle(tilesAll());
  const g = {id: "domino", o, me: deck.splice(0, 7), cpu: deck.splice(0, 7), pile: deck, chain: [], ends: null, turn: null, over: null, score, sel: -1, msg: "", passes: 0};
  // eng katta «dubl» kimda bo'lsa — o'sha boshlaydi
  let starter = "me", bestD = -1;
  for (const [who, h] of [["me", g.me], ["cpu", g.cpu]]) for (const t of h) if (t[0] === t[1] && t[0] > bestD) { bestD = t[0]; starter = who; }
  g.turn = starter;
  g.msg = starter === "me" ? T("Siz boshlaysiz", "Вы начинаете", "You start") : T("Kompyuter boshlaydi", "Компьютер начинает", "Computer starts");
  game = g;
  drawDm();
  if (g.turn === "cpu") later(dmCpu, 700);
}
const fits = (g, t) => {
  if (!g.chain.length) return ["L"];
  const s = [];
  if (t[0] === g.ends[0] || t[1] === g.ends[0]) s.push("L");
  if (t[0] === g.ends[1] || t[1] === g.ends[1]) s.push("R");
  return s;
};
function dmPlace(g, who, idx, side) {
  const hand = g[who], t = hand.splice(idx, 1)[0];
  if (!g.chain.length) { g.chain.push(t.slice()); g.ends = [t[0], t[1]]; }
  else if (side === "L") { const o = t[1] === g.ends[0] ? [t[0], t[1]] : [t[1], t[0]]; g.chain.unshift(o); g.ends[0] = o[0]; }
  else { const o = t[0] === g.ends[1] ? [t[0], t[1]] : [t[1], t[0]]; g.chain.push(o); g.ends[1] = o[1]; }
  g.passes = 0; sfx.move(); haptic();
}
function dmEnd(winner, blocked) {
  const g = game;
  const mp = g.me.reduce((s, t) => s + pips(t), 0), cp = g.cpu.reduce((s, t) => s + pips(t), 0);
  if (blocked) winner = mp < cp ? "me" : cp < mp ? "cpu" : null;
  const pts = winner === "me" ? cp : winner === "cpu" ? mp : 0;
  if (winner) g.score[winner] += pts;
  g.over = {winner, pts, blocked, match: g.score.me >= 101 ? "me" : g.score.cpu >= 101 ? "cpu" : null};
  if (g.over.match) { record("domino", g.over.match === "me" ? "w" : "l"); g.over.match === "me" ? sfx.win() : sfx.lose(); } else winner === "me" ? sfx.win() : sfx.lose();
  drawDm();
}
function dmAfter(who) {
  const g = game;
  if (!g[who].length) { dmEnd(who); return; }
  const canMe = g.me.some((t) => fits(g, t).length), canCpu = g.cpu.some((t) => fits(g, t).length);
  if (!g.pile.length && !canMe && !canCpu) { dmEnd(null, true); return; }
  g.turn = who === "me" ? "cpu" : "me";
  drawDm();
  if (g.turn === "cpu") later(dmCpu, 750);
}
function dmCpu() {
  const g = game;
  if (!g || g.id !== "domino" || g.over) return;
  const opts = [];
  g.cpu.forEach((t, i) => fits(g, t).forEach((s) => opts.push({i, s, v: pips(t) + (t[0] === t[1] ? 4 : 0)})));
  if (!opts.length) {
    if (g.pile.length) { g.cpu.push(g.pile.pop()); g.msg = T("Kompyuter bozordan oldi", "Компьютер взял из базара", "Computer drew a tile"); drawDm(); later(dmCpu, 450); return; }
    g.msg = T("Kompyuter yurolmadi — o'tkazdi", "Компьютер пропускает", "Computer passes");
    dmAfter("cpu"); return;
  }
  const lvlPick = game.o.lvl <= 1 ? opts[rnd(opts.length)] : opts.sort((a, b) => b.v - a.v)[0];
  dmPlace(g, "cpu", lvlPick.i, lvlPick.s);
  g.msg = "";
  dmAfter("cpu");
}
function drawDm() {
  const g = game;
  const myTurn = g.turn === "me" && !g.over;
  const can = myTurn && g.me.some((t) => fits(g, t).length);
  const chain = g.chain.map((t, k) => tileHtml(t, "ch" + (k === 0 || k === g.chain.length - 1 ? " end" : ""))).join("");
  const hand = g.me.map((t, i) => { const f = myTurn ? fits(g, t) : []; return tileHtml(t, `hand ${f.length ? "ok" : "no"} ${g.sel === i ? "sel" : ""}`, `data-dmt="${i}" role="button"`); }).join("");
  const sel = g.sel >= 0 ? fits(g, g.me[g.sel]) : [];
  let res = "";
  if (g.over) {
    const o = g.over;
    const txt = o.match ? (o.match === "me" ? T("101 ochko! O'yinni yutdingiz", "101 очко! Вы выиграли партию", "101 points! You win the match") : T("Kompyuter partiyani yutdi", "Компьютер выиграл партию", "Computer wins the match"))
      : o.winner === "me" ? `${T("Raund sizniki", "Раунд ваш", "Round is yours")}: +${o.pts}` : o.winner === "cpu" ? `${T("Raund kompyuterniki", "Раунд за компьютером", "Computer takes the round")}: +${o.pts}` : T("Yopiq o'yin — durang", "Рыба — ничья", "Blocked — draw");
    res = `<div class="ka-res ${o.winner === "me" ? "w" : o.winner ? "l" : "d"}"><b>${o.blocked ? "🐟 " : ""}${txt}</b><div class="ka-row"><button class="ka-cta" data-kdmnext>${o.match ? "🔁 " + T("Yangi partiya", "Новая партия", "New match") : "▶ " + T("Keyingi raund", "Следующий раунд", "Next round")}</button><button class="ka-ghost" data-kh>${T("O'yinlar", "Игры", "Games")}</button></div></div>`;
  }
  wrap(bar("🁫 " + T("Domino", "Домино", "Dominoes"), `<span class="ka-pill">${T("Siz", "Вы", "You")} ${g.score.me} : ${g.score.cpu} 🤖</span>`) + `
   <div class="ka-pl ${g.turn === "cpu" && !g.over ? "on" : ""}"><b>🤖 ${T("Kompyuter", "Компьютер", "Computer")}</b><span class="dmback">${g.cpu.map(() => "<i></i>").join("")}</span></div>
   <div class="ka-table"><div class="dchain" id="kadch">${chain || `<span class="ka-fine">${T("Stol bo'sh — birinchi toshni qo'ying", "Стол пуст — положите первую кость", "Empty table — place the first tile")}</span>`}</div>
    <div class="dinfo">🧺 ${T("Bozor", "Базар", "Boneyard")}: <b>${g.pile.length}</b>${g.msg ? ` · ${g.msg}` : ""}</div></div>
   ${sel.length > 1 ? `<div class="ka-row"><button class="ka-cta" data-kdmside="L">⬅ ${T("Chapga", "Влево", "Left")}</button><button class="ka-cta" data-kdmside="R">${T("O'ngga", "Вправо", "Right")} ➡</button></div>` : ""}
   <div class="ka-pl ${myTurn ? "on" : ""}"><b>${T("Siz", "Вы", "You")}</b>${myTurn && !can ? `<button class="ka-pill g" data-kdmdraw>${g.pile.length ? "🧺 " + T("Bozordan olish", "Взять из базара", "Draw") : "⏭ " + T("O'tkazish", "Пропустить", "Pass")}</button>` : `<span class="ka-fine">${myTurn ? T("Mos toshni bosing", "Нажмите подходящую кость", "Tap a matching tile") : ""}</span>`}</div>
   <div class="dhand">${hand}</div>${res}`);
  const ch = document.getElementById("kadch");
  if (ch) ch.scrollLeft = ch.scrollWidth / 2 - ch.clientWidth / 2;
}
function dmTap(i) {
  const g = game;
  if (g.over || g.turn !== "me") return;
  const f = fits(g, g.me[i]);
  if (!f.length) { haptic("err"); return; }
  if (f.length === 1) { g.sel = -1; dmPlace(g, "me", i, f[0]); g.msg = ""; dmAfter("me"); return; }
  g.sel = i; haptic(); drawDm();
}

// =================================================================== 🚢 DENGIZ JANGI
const FLEET = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1];
function seaPlace() {
  for (let tries = 0; tries < 200; tries++) {
    const grid = Array(100).fill(0), ships = [];
    let ok = true;
    for (const len of FLEET) {
      let placed = false;
      for (let k = 0; k < 300 && !placed; k++) {
        const hor = Math.random() < .5, r = rnd(hor ? 10 : 11 - len), c = rnd(hor ? 11 - len : 10);
        const cells = Array.from({length: len}, (_, j) => (hor ? r * 10 + c + j : (r + j) * 10 + c));
        const clear = cells.every((q) => { const qr = Math.floor(q / 10), qc = q % 10; for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) { const rr = qr + dr, cc = qc + dc; if (rr >= 0 && rr < 10 && cc >= 0 && cc < 10 && grid[rr * 10 + cc]) return false; } return true; });
        if (clear) { const id = ships.length + 1; cells.forEach((q) => { grid[q] = id; }); ships.push({cells, hits: 0}); placed = true; }
      }
      if (!placed) { ok = false; break; }
    }
    if (ok) return {grid, ships, shots: Array(100).fill(0)};      // shots: 0 — yo'q, 1 — xato, 2 — tegdi, 3 — cho'kdi
  }
  return null;
}
function seaNew() {
  const o = game.o;
  game = {id: "sea", o, mine: seaPlace(), enemy: seaPlace(), turn: "me", over: null, ready: false, ai: {targets: [], hits: []}, msg: ""};
  drawSea();
}
function seaShoot(board, q) {
  if (board.shots[q]) return null;
  const id = board.grid[q];
  if (!id) { board.shots[q] = 1; return "miss"; }
  const sh = board.ships[id - 1];
  sh.hits++; board.shots[q] = 2;
  if (sh.hits === sh.cells.length) {
    sh.cells.forEach((c) => { board.shots[c] = 3; const cr = Math.floor(c / 10), cc = c % 10;
      for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) { const rr = cr + dr, c2 = cc + dc; if (rr >= 0 && rr < 10 && c2 >= 0 && c2 < 10 && !board.shots[rr * 10 + c2]) board.shots[rr * 10 + c2] = 1; } });
    return board.ships.every((s) => s.hits === s.cells.length) ? "all" : "sunk";
  }
  return "hit";
}
function seaAI() {
  const g = game, b = g.mine, ai = g.ai;
  const free = (q) => q >= 0 && q < 100 && !b.shots[q];
  let q = -1;
  const open = ai.hits.filter((h) => b.shots[h] === 2);
  if (open.length && g.o.lvl > 1) {
    const cand = [];
    if (open.length >= 2) {
      const hor = Math.floor(open[0] / 10) === Math.floor(open[1] / 10), s = open.slice().sort((a, c) => a - c);
      const st = hor ? 1 : 10, lo = s[0] - st, hi = s[s.length - 1] + st;
      if (free(lo) && (!hor || Math.floor(lo / 10) === Math.floor(s[0] / 10))) cand.push(lo);
      if (free(hi) && (!hor || Math.floor(hi / 10) === Math.floor(s[0] / 10))) cand.push(hi);
    }
    if (!cand.length) for (const h of open) for (const d of [-1, 1, -10, 10]) { const n = h + d; if (free(n) && !(Math.abs(d) === 1 && Math.floor(n / 10) !== Math.floor(h / 10))) cand.push(n); }
    if (cand.length) q = cand[rnd(cand.length)];
  }
  if (q < 0) {
    let pool = [];
    for (let i = 0; i < 100; i++) if (free(i) && (g.o.lvl < 3 || (Math.floor(i / 10) + i % 10) % 2 === 0)) pool.push(i);
    if (!pool.length) for (let i = 0; i < 100; i++) if (free(i)) pool.push(i);
    q = pool[rnd(pool.length)];
  }
  const r = seaShoot(b, q);
  if (r === "hit") ai.hits.push(q);
  if (r === "sunk" || r === "all") ai.hits = [];
  if (r === "miss") { sfx.splash(); g.turn = "me"; g.msg = T("Kompyuter adashdi — navbat sizda", "Компьютер промахнулся — ваш ход", "Computer missed — your turn"); drawSea(); return; }
  sfx.boom(); haptic("hit");
  if (r === "all") { g.over = "cpu"; record("sea", "l"); sfx.lose(); drawSea(); return; }
  g.msg = r === "sunk" ? T("Kompyuter kemangizni cho'ktirdi!", "Компьютер потопил ваш корабль!", "Computer sank your ship!") : T("Kompyuter tekkizdi!", "Компьютер попал!", "Computer hit!");
  drawSea(); later(seaAI, 650);
}
function seaGrid(board, enemy, small) {
  let h = "";
  for (let q = 0; q < 100; q++) {
    const s = board.shots[q], ship = board.grid[q];
    const cls = ["sc", s === 1 ? "miss" : s === 2 ? "hit" : s === 3 ? "sunk" : "", !enemy && ship ? "ship" : ""].join(" ");
    h += enemy && !game.over && !game.netOver && game.ready ? `<button class="${cls}" data-sea="${q}">${s === 2 || s === 3 ? "✕" : s === 1 ? "•" : ""}</button>` : `<span class="${cls}">${s === 2 || s === 3 ? "✕" : s === 1 ? "•" : ""}</span>`;
  }
  return `<div class="ka-sea ${small ? "small" : ""}">${h}</div>`;
}
function drawSea() {
  const g = game;
  const left = (b) => b.ships.filter((s) => s.hits < s.cells.length).length;
  let res = "";
  if (g.over) res = resultHtml(g.over === "me" ? "w" : "l", g.over === "me" ? T("Butun flotni cho'ktirdingiz!", "Вы потопили весь флот!", "You sank the whole fleet!") : T("Flotingiz cho'kdi", "Ваш флот потоплен", "Your fleet is sunk"));
  if (!g.ready) {
    wrap(bar("🚢 " + T("Dengiz jangi", "Морской бой", "Battleship")) + `<div class="ka-turn">${T("Kemalaringiz joylashuvi", "Расстановка ваших кораблей", "Your fleet")}</div>${seaGrid(g.mine, false, false)}
     <div class="ka-row"><button class="ka-ghost" data-kseashuffle>🔀 ${T("Aralashtirish", "Перемешать", "Shuffle")}</button><button class="ka-cta" data-kseago>⚓ ${T("Jangga!", "В бой!", "Battle!")}</button></div>
     <p class="ka-fine">${T("1 ta 4 katakli, 2 ta 3 katakli, 3 ta 2 katakli, 4 ta 1 katakli kema. Kemalar bir-biriga tegmaydi.", "1×4, 2×3, 3×2, 4×1. Корабли не касаются друг друга.", "1×4, 2×3, 3×2, 4×1 ships. Ships never touch.")}</p>`);
    return;
  }
  wrap(bar("🚢 " + T("Dengiz jangi", "Морской бой", "Battleship"), `<span class="ka-pill">${T("Dushman", "Враг", "Enemy")}: ${left(g.enemy)} 🚢</span>`) + `
   <div class="ka-turn">${g.over ? "" : g.turn === "me" ? `🎯 ${T("Navbat sizda — dushman maydonini bosing", "Ваш ход — стреляйте", "Your turn — fire!")}` : `🤖 ${T("Kompyuter otmoqda…", "Компьютер стреляет…", "Computer is firing…")}`}</div>
   ${seaGrid(g.enemy, true, false)}
   ${g.msg ? `<p class="ka-hint">${g.msg}</p>` : ""}
   <div class="ka-turn small">${T("Sizning flotingiz", "Ваш флот", "Your fleet")} · ${left(g.mine)} 🚢</div>${seaGrid(g.mine, false, true)}${res}`);
}
function seaTap(q) {
  const g = game;
  if (g.over || g.turn !== "me" || g.enemy.shots[q]) return;
  const r = seaShoot(g.enemy, q);
  if (r === "miss") { sfx.splash(); g.turn = "cpu"; g.msg = T("Adashdingiz", "Мимо", "Miss"); drawSea(); later(seaAI, 700); return; }
  sfx.boom(); haptic("hit");
  if (r === "all") { g.over = "me"; record("sea", "w"); sfx.win(); drawSea(); return; }
  g.msg = r === "sunk" ? T("Kema cho'kdi! Yana oting", "Корабль потоплен! Стреляйте ещё", "Ship sunk! Fire again") : T("Tegdi! Yana oting", "Попал! Ещё выстрел", "Hit! Fire again");
  drawSea();
}


// =================================================================== 🌐 ONLAYN (boshqa mijoz bilan)
let netTimer = null;
async function api(path, body) {
  try {
    const r = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store",
      headers: Object.assign({"X-Init-Data": tg ? tg.initData || "" : ""}, body ? {"Content-Type": "application/json"} : {}),
      body: body ? JSON.stringify(body) : undefined});
    if (r.status === 401) return {ok: false, error: "auth"};
    if (r.status >= 500) return {ok: false, error: "server"};
    return await r.json();
  } catch (e) { return {ok: false, error: "network"}; }
}
const NERR = () => ({auth: T("Ilovani bot ichida oching", "Откройте приложение внутри бота", "Open the app inside the bot"),
  network: T("Internet bilan muammo", "Проблема с интернетом", "Connection problem"), server: T("Server band — qayta urining", "Сервер занят — повторите", "Server busy — try again"),
  nocode: T("Bunday kod topilmadi yoki o'yin boshlangan", "Код не найден или игра уже началась", "Code not found or game already started"),
  banned: T("Siz bloklangansiz", "Вы заблокированы", "You are blocked"), busy: T("Qayta urining", "Попробуйте ещё раз", "Try again")});
function netSetupHtml() {
  return `<div class="ka-net">
    <button class="ka-cta" data-knfind>🔎 ${T("Raqib qidirish", "Найти соперника", "Find an opponent")}</button>
    <p class="ka-fine c">${T("Hozir qidirayotgan boshqa o'yinchi bilan avtomatik ulanasiz", "Вас соединит с другим игроком, который тоже ищет", "You'll be paired with another player who is searching")}</p>
    <div class="ka-lh">${T("Yoki do'stingiz bilan — kod orqali", "Или с другом — по коду", "Or with a friend — by code")}</div>
    <button class="ka-ghost w" data-kncode>🔢 ${T("Kod yaratish", "Создать код", "Create a code")}</button>
    <div class="ka-codein"><input id="kacode" inputmode="numeric" pattern="[0-9]*" maxlength="4" placeholder="${T("Kodni kiriting", "Введите код", "Enter code")}" autocomplete="off"><button class="ka-cta" data-knjoin>${T("Ulanish", "Войти", "Join")}</button></div>
    ${game && game.err ? `<p class="ka-hint r">${game.err}</p>` : ""}</div>`;
}
function netStop() { if (netTimer) { clearInterval(netTimer); netTimer = null; } }
function netPollStart() { netStop(); netTimer = setInterval(netPoll, 1300); }
function netLeave() { netStop(); api("api/duel/resign", {}); }
function openGame2(id, e) { const o = game.o; openGame(id); game.err = e; game.o = o; const box = root.querySelector(".ka-net"); if (box) box.insertAdjacentHTML("beforeend", `<p class="ka-hint r">${e}</p>`); }
async function netFind() {
  const id = game.id, o = game.o;
  game = {id, o, netPhase: "find", n: 0};
  netWaitDraw();
  const r = await api("api/duel/find", {g: id});
  if (!game || game.id !== id || game.netPhase !== "find") return;
  if (!r.ok) { game = {id, o, setup: true}; openGame2(id, NERR()[r.error] || NERR().server); return; }
  if (r.room) { netStart(r.room); return; }
  game.n = r.n || 1; netWaitDraw(); netPollStart();
}
async function netCode() {
  const id = game.id, o = game.o;
  const r = await api("api/duel/code", {g: id});
  if (!r.ok || !r.room) { openGame2(id, NERR()[r.error] || NERR().server); return; }
  game = {id, o, netPhase: "code", code: r.room.code, ver: r.room.ver};
  netWaitDraw(); netPollStart();
}
async function netJoin(code) {
  const id = game.id;
  if (code.length !== 4) { openGame2(id, T("4 xonali kodni kiriting", "Введите 4-значный код", "Enter the 4-digit code")); return; }
  const r = await api("api/duel/join", {code});
  if (!r.ok || !r.room) { openGame2(id, NERR()[r.error] || NERR().server); return; }
  if (r.room.g !== id) { openGame(r.room.g); }
  netStart(r.room);
}
function netShare() {
  const g = game, txt = T(`Men bilan ${TITLE[g.id]} o'ynang! O'yinlar → Kattalar → ${TITLE[g.id]} → 🌐 Onlayn → kod: ${g.code}`, `Сыграем в ${TITLE[g.id]}! Игры → Взрослые → 🌐 Онлайн → код: ${g.code}`, `Play ${TITLE[g.id]} with me! Code: ${g.code}`);
  try { tg.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(location.origin) + "&text=" + encodeURIComponent(txt)); } catch (e) { try { navigator.clipboard.writeText(txt); } catch (e2) {} }
}
function netWaitDraw() {
  const g = game;
  if (g.netPhase === "find") {
    wrap(bar(TITLE[g.id]) + `<div class="ka-wait"><div class="ka-radar"><i></i><i></i><b>🌐</b></div>
      <b class="t">${T("Raqib qidirilmoqda…", "Ищем соперника…", "Looking for an opponent…")}</b>
      <span id="kanq">${g.n > 1 ? T(`Navbatda: ${g.n} kishi`, `В очереди: ${g.n}`, `In queue: ${g.n}`) : T("Boshqa o'yinchi kirishi bilan o'yin boshlanadi", "Игра начнётся, как только зайдёт другой игрок", "The game starts as soon as another player joins")}</span>
      <button class="ka-ghost" data-kncancel>✖️ ${T("Bekor qilish", "Отмена", "Cancel")}</button></div>`);
  } else {
    wrap(bar(TITLE[g.id]) + `<div class="ka-wait"><span>${T("Do'stingizga shu kodni yuboring", "Отправьте другу этот код", "Send this code to your friend")}</span>
      <div class="ka-code">${g.code.split("").map((d) => `<i>${d}</i>`).join("")}</div>
      <div class="ka-row"><button class="ka-ghost" data-kncopy>📋 ${T("Nusxa", "Копировать", "Copy")}</button><button class="ka-cta" data-knshare>📤 ${T("Yuborish", "Отправить", "Share")}</button></div>
      <span class="ka-fine c">${T("Do'stingiz: O'yinlar → Kattalar → shu o'yin → 🌐 Onlayn → kodni kiritadi. Kod 15 daqiqa amal qiladi.", "Друг: Игры → Взрослые → эта игра → 🌐 Онлайн → вводит код. Код действует 15 минут.", "Your friend: Games → Adults → this game → 🌐 Online → enter the code. Valid 15 min.")}</span>
      <div class="ka-dots"><i></i><i></i><i></i></div>
      <button class="ka-ghost" data-kncancel>✖️ ${T("Bekor qilish", "Отмена", "Cancel")}</button></div>`);
  }
}
async function netPoll() {
  const g = game;
  if (!g || !(g.netPhase || g.net)) { netStop(); return; }
  if (g._busy) return;
  g._busy = true;
  const r = await api("api/duel/poll?v=" + (g.net ? g.net.ver : -1));
  g._busy = false;
  if (game !== g || !r.ok) return;
  if (r.wait && g.netPhase === "find") { if (r.n !== g.n) { g.n = r.n; const el = document.getElementById("kanq"); if (el && r.n > 1) el.textContent = T(`Navbatda: ${r.n} kishi`, `В очереди: ${r.n}`, `In queue: ${r.n}`); } return; }
  if (r.idle) { if (g.netPhase) { netStop(); openGame2(g.id, T("Qidiruv to'xtadi — qayta urining", "Поиск остановлен — попробуйте снова", "Search stopped — try again")); } return; }
  if (r.same) { if (g.net && !!r.away !== !!g.net.away) { g.net.away = r.away; netRedraw(); } return; }
  if (!r.room) return;
  if (g.netPhase) { if (r.room.ready) netStart(r.room); return; }
  netApply(r.room);
}
function netStart(room) {
  const id = room.g, o = (game && game.o) || lsGet("ka_opt_" + id, {mode: "net", lvl: 2, side: "w"});
  if (id === "chess") game = {id, o, st: chessStart(), sel: -1, last: null, hist: [], over: null, me: room.me, think: false, caps: {w: [], b: []}};
  else if (id === "draughts") game = {id, o, st: drStart(), sel: -1, last: null, hist: [], over: null, me: room.me, think: false};
  else if (id === "xo") game = {id, o, b: Array(9).fill(""), turn: "X", first: "X", me: room.me === "w" ? "X" : "O", over: null, score: {X: 0, O: 0, d: 0}};
  else if (id === "domino") game = {id, o, sel: -1, me: room.me};
  else game = {id, o, ready: true, me: room.me};
  game.net = room; game.ply = 0;
  haptic("ok"); tone(660, .12, "triangle", .15); tone(880, .16, "triangle", .15, .1);
  top(); netApply(room, true); netPollStart();
}
function netApply(room, first) {
  const g = game;
  if (!g || !g.net || g.net.id !== room.id) return;
  const prevTurn = g.net.turn;
  g.net = room;
  if (g.id === "chess") {
    while (g.ply < room.moves.length) { const mv = room.moves[g.ply]; const m = legal(g.st).find((x) => x.f === mv.f && x.t === mv.t); if (!m) { netRebuild(room); return; } chessDo(m, true); }
  } else if (g.id === "draughts") {
    while (g.ply < room.moves.length) { const mv = room.moves[g.ply]; const m = drMoves(g.st).find((x) => x.path.join() === (mv.p || []).join()); if (!m) { netRebuild(room); return; } drDo(m, true); }
  } else if (g.id === "xo") {
    while (g.ply < room.moves.length) { const i = room.moves[g.ply].i; if (g.b[i]) { netRebuild(room); return; } xoDo(i, true); }
  } else {
    const old = g.s; g.s = room.s;
    if (!first && old && room.s && room.s.last && JSON.stringify(old.last) !== JSON.stringify(room.s.last)) netSfx(g, room.s.last);
  }
  if (room.over && !g.netOver) {
    g.netOver = room.over;
    const win = room.over.win;
    if (!g.over) { record(g.id, !win ? "d" : win === room.me ? "w" : "l"); win === room.me ? sfx.win() : win ? sfx.lose() : 0; }
    netStop();
  } else if (!first && prevTurn !== room.turn && room.turn === room.me) haptic();
  netRedraw();
}
function netRebuild(room) { netStop(); const o = game.o; game = {o}; netStart(room); }
function netRedraw() {
  const g = game;
  ({chess: drawChess, draughts: drawDr, xo: drawXo, domino: dmNetDraw, sea: seaNetDraw})[g.id]();
}
async function netSend(m, end, why) {
  const g = game, room = g.net;
  const r = await api("api/duel/move", {id: room.id, m, n: g.ply - 1, end: end || undefined, why: why || undefined});
  if (game !== g) return;
  if (!r.ok) { if (r.room) netRebuild(r.room); else netToast(NERR()[r.error] || NERR().server); return; }
  netApply(r.room);
}
async function netAct(m) {
  const g = game;
  if (g._acting) return;
  g._acting = true;
  const r = await api("api/duel/move", {id: g.net.id, m, n: 0});
  g._acting = false;
  if (game !== g) return;
  if (r.room) netApply(r.room);
  if (!r.ok && r.error !== "turn") netToast(NERR()[r.error] || NERR().server);
}
async function netResign() {
  const g = game;
  if (!g.armedR || Date.now() - g.armedR > 3500) { g.armedR = Date.now(); haptic("err"); netToast(T("Taslim bo'lish uchun yana bosing", "Нажмите ещё раз, чтобы сдаться", "Tap again to resign")); return; }
  const r = await api("api/duel/resign", {});
  if (game === g && r.room) netApply(r.room);
}
function netToast(text) {
  const el = root && root.querySelector(".ka-r");
  if (el) { el.innerHTML = `<span class="ka-pill r">${text}</span>`; later(() => { if (game && (game.net || game.netPhase)) { const e2 = root.querySelector(".ka-r"); if (e2 && e2.textContent === text) netRedrawSafe(); } }, 2600); }
}
function netRedrawSafe() { if (game && game.net) netRedraw(); }
function netWho(s) { const g = game; return s === g.net.me ? "🙂 " + T("Siz", "Вы", "You") + (g.net.my ? ` · ${esc(g.net.my)}` : "") : "🌐 " + esc(g.net.opp || T("Raqib", "Соперник", "Opponent")); }
const esc = (x) => String(x || "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
function netPill(g, side) {
  if (g.netOver || g.over) return "";
  if (g.net.away) return `<span class="ka-pill r">📴 ${T("Raqib aloqada emas", "Соперник не в сети", "Opponent offline")}</span>`;
  return side === g.net.me ? `<span class="ka-pill g">🎯 ${T("Sizning navbat", "Ваш ход", "Your move")}</span>` : `<span class="ka-think">⏳ ${T("Raqib o'ylayapti", "Соперник думает", "Opponent's move")}</span>`;
}
function netCtl(g) {
  return g.netOver || g.over ? "" : `<div class="ka-row"><button class="ka-ghost" data-knresign>🏳️ ${T("Taslim bo'lish", "Сдаться", "Resign")}</button></div>`;
}
function netResHtml(g) {
  const o = g.netOver, me = g.net.me, win = o.win;
  const why = {resign: win === me ? T("Raqib taslim bo'ldi", "Соперник сдался", "Opponent resigned") : T("Siz taslim bo'ldingiz", "Вы сдались", "You resigned"),
    left: win === me ? T("Raqib o'yindan chiqib ketdi", "Соперник покинул игру", "Opponent left") : T("Aloqa uzildi", "Связь потеряна", "Connection lost"),
    closed: T("O'yin yopildi", "Игра закрыта", "Game closed")}[o.why];
  const text = !win ? T("Durang", "Ничья", "Draw") : win === me ? T("Siz yutdingiz!", "Вы победили!", "You win!") : T("Raqib yutdi", "Победил соперник", "Opponent wins");
  return `<div class="ka-res ${!win ? "d" : win === me ? "w" : "l"}"><b>${!win ? "🤝" : win === me ? "🏆" : "😔"} ${text}</b>${why ? `<p class="ka-fine c">${why}</p>` : ""}<div class="ka-row"><button class="ka-cta" data-knagain>🔁 ${T("Yangi raqib", "Новый соперник", "New opponent")}</button><button class="ka-ghost" data-kh>${T("O'yinlar", "Игры", "Games")}</button></div></div>`;
}
function netSfx(g, last) {
  if (g.id === "sea") { last.r === "miss" ? sfx.splash() : (sfx.boom(), haptic("hit")); }
  else if (last.a === "play") sfx.move();
}
// ---- 🁫 domino (holat serverda)
function dmFits(s, t) {
  if (!s.chain.length) return ["L"];
  const o = [];
  if (t[0] === s.ends[0] || t[1] === s.ends[0]) o.push("L");
  if (t[0] === s.ends[1] || t[1] === s.ends[1]) o.push("R");
  return o;
}
function dmNetDraw() {
  const g = game, s = g.s, me = g.net.me, over = g.netOver;
  const myTurn = s.turn === me && !over;
  const can = myTurn && s.hand.some((t) => dmFits(s, t).length);
  const chain = s.chain.map((t, k) => tileHtml(t, "ch" + (k === 0 || k === s.chain.length - 1 ? " end" : ""))).join("");
  const hand = s.hand.map((t, i) => { const f = myTurn ? dmFits(s, t) : []; return tileHtml(t, `hand ${f.length ? "ok" : "no"} ${g.sel === i ? "sel" : ""}`, `data-dmt="${i}" role="button"`); }).join("");
  const sel = g.sel >= 0 && s.hand[g.sel] ? dmFits(s, s.hand[g.sel]) : [];
  const lastTxt = s.last && s.last.by !== me ? ({draw: T("Raqib bozordan oldi", "Соперник взял из базара", "Opponent drew"), pass: T("Raqib o'tkazdi", "Соперник пропустил", "Opponent passed"), fish: T("Yopiq o'yin", "Рыба", "Blocked")}[s.last.a] || "") : "";
  let res = "";
  if (over) {
    res = netResHtml(g);
    if (s.pips) res = res.replace("</b>", `</b><p class="ka-fine c">${T("Ochkolar", "Очки", "Pips")}: ${T("siz", "вы", "you")} ${s.pips.me} · ${T("raqib", "соперник", "opponent")} ${s.pips.opp}</p>`);
  }
  wrap(bar(TITLE.domino, netPill(g, s.turn)) + `
   <div class="ka-pl ${s.turn !== me && !over ? "on" : ""}"><b>${netWho(me === "w" ? "b" : "w")}</b><span class="dmback">${over && s.oppHand ? s.oppHand.map((t) => tileHtml(t, "mini")).join("") : Array.from({length: s.opp}, () => "<i></i>").join("")}</span></div>
   <div class="ka-table"><div class="dchain" id="kadch">${chain || `<span class="ka-fine">${T("Stol bo'sh", "Стол пуст", "Empty table")}</span>`}</div>
    <div class="dinfo">🧺 ${T("Bozor", "Базар", "Boneyard")}: <b>${s.pile}</b>${lastTxt ? ` · ${lastTxt}` : ""}</div></div>
   ${sel.length > 1 ? `<div class="ka-row"><button class="ka-cta" data-kdmside="L">⬅ ${T("Chapga", "Влево", "Left")}</button><button class="ka-cta" data-kdmside="R">${T("O'ngga", "Вправо", "Right")} ➡</button></div>` : ""}
   <div class="ka-pl ${myTurn ? "on" : ""}"><b>${netWho(me)}</b>${myTurn && !can ? `<button class="ka-pill g" data-kdmdraw>${s.pile ? "🧺 " + T("Bozordan olish", "Взять из базара", "Draw") : "⏭ " + T("O'tkazish", "Пропустить", "Pass")}</button>` : `<span class="ka-fine">${myTurn ? T("Mos toshni bosing", "Нажмите подходящую кость", "Tap a matching tile") : ""}</span>`}</div>
   <div class="dhand">${hand}</div>${over ? "" : netCtl(g)}${res}`);
  const ch = document.getElementById("kadch");
  if (ch) ch.scrollLeft = ch.scrollWidth / 2 - ch.clientWidth / 2;
}
function dmNetTap(i) {
  const g = game, s = g.s;
  if (g.netOver || s.turn !== g.net.me) return;
  const f = dmFits(s, s.hand[i]);
  if (!f.length) { haptic("err"); return; }
  if (f.length === 1) { dmNetPlay(i, f[0]); return; }
  g.sel = i; haptic(); dmNetDraw();
}
function dmNetPlay(i, e) { const g = game; if (i < 0 || !g.s.hand[i]) return; const t = g.s.hand[i]; g.sel = -1; sfx.move(); netAct({a: "play", t, e}); }
// ---- 🚢 dengiz jangi (kemalar serverda)
function seaNetDraw() {
  const g = game, s = g.s, me = g.net.me, over = g.netOver;
  const mine = {grid: s.mine, shots: s.onMe}, enemy = {grid: Array(100).fill(0), shots: s.onEnemy};
  const myTurn = s.turn === me && !over;
  const L = s.last;
  const msg = L ? (L.by === me ? ({miss: T("Adashdingiz", "Мимо", "Miss"), hit: T("Tegdi! Yana oting", "Попал! Ещё выстрел", "Hit! Fire again"), sunk: T("Kema cho'kdi! Yana oting", "Корабль потоплен! Ещё", "Ship sunk! Fire again")}[L.r])
    : ({miss: T("Raqib adashdi", "Соперник промахнулся", "Opponent missed"), hit: T("Raqib tekkizdi!", "Соперник попал!", "Opponent hit!"), sunk: T("Raqib kemangizni cho'ktirdi!", "Соперник потопил ваш корабль!", "Opponent sank your ship!")}[L.r])) : "";
  g.ready = true;
  wrap(bar(TITLE.sea, netPill(g, s.turn)) + `
   <div class="ka-turn">${over ? "" : myTurn ? `🎯 ${T("Navbat sizda — raqib maydonini bosing", "Ваш ход — стреляйте", "Your turn — fire!")}` : `⏳ ${esc(g.net.opp)} ${T("otmoqda…", "стреляет…", "is firing…")}`} · ${T("Raqib", "Враг", "Enemy")}: ${s.leftEnemy} 🚢</div>
   ${seaGrid(enemy, myTurn, false)}
   ${msg ? `<p class="ka-hint">${msg}</p>` : ""}
   <div class="ka-turn small">${T("Sizning flotingiz", "Ваш флот", "Your fleet")} · ${s.leftMe} 🚢</div>${seaGrid(mine, false, true)}${over ? netResHtml(g) : netCtl(g)}`);
}
function seaNetTap(q) {
  const g = game;
  if (g.netOver || g.s.turn !== g.net.me || g.s.onEnemy[q]) return;
  netAct({q});
}

// =================================================================== boshqaruv
const RULES = {
  chess: T("Klassik qoidalar: rokirovka, «o'tib olish», piyoda oxirgi qatorda farzinga aylanadi. Qaytarish tugmasi bor.", "Классические правила: рокировка, взятие на проходе, превращение в ферзя.", "Classic rules: castling, en passant, promotion to queen."),
  draughts: T("Rus shashkasi: oddiy tosh oldinga yuradi, orqaga ham ola oladi; olish majburiy va bir yurishda bir nechta tosh olinadi; oxirgi qatorga yetgan tosh damka bo'ladi va uzoq yuradi.", "Русские шашки: бить обязательно, можно бить назад, дамка ходит далеко.", "Russian draughts: capturing is mandatory, men capture backwards, kings fly."),
  xo: T("Bir qatorga 3 ta belgini birinchi bo'lib tergan yutadi.", "Выигрывает тот, кто первым поставит 3 в ряд.", "Three in a row wins."),
  domino: T("Har kimda 7 tosh. Uchlariga mos toshni qo'yasiz; mos tosh bo'lmasa — bozordan olasiz. Toshi birinchi tugagan raqib toshlaridagi ochkolarni oladi. 101 ochkoga yetgan yutadi.", "По 7 костей. Ставьте подходящие, иначе берите из базара. Кто первым избавился — забирает очки соперника. До 101.", "7 tiles each. Match the ends or draw. First out scores the opponent's pips. First to 101 wins."),
  sea: T("Navbat bilan otasiz. Tekkizsangiz — yana otasiz. Butun flotni birinchi cho'ktirgan yutadi.", "Стреляете по очереди. Попали — стреляете ещё. Кто первым потопит флот — победил.", "Take turns firing. A hit gives another shot. Sink the whole fleet first."),
};
const TITLE = {chess: "♞ " + T("Shaxmat", "Шахматы", "Chess"), draughts: "⛂ " + T("Shashka", "Шашки", "Draughts"), xo: "✕ X-O", domino: "🁫 " + T("Domino", "Домино", "Dominoes"), sea: "🚢 " + T("Dengiz jangi", "Морской бой", "Battleship")};
const top = () => { const sc = document.getElementById("gxscroll"); if (sc) sc.scrollTop = 0; };
function openGame(id) {
  clearTimers(); top();
  if (id === "chess") setup(id, TITLE[id], {side: true, rules: RULES[id]});
  else if (id === "draughts") setup(id, TITLE[id], {side: true, rules: RULES[id]});
  else if (id === "xo") setup(id, TITLE[id], {rules: RULES[id]});
  else if (id === "domino") setup(id, TITLE[id], {two: false, rules: RULES[id]});
  else if (id === "sea") setup(id, TITLE[id], {two: false, rules: RULES[id]});
  haptic();
}
function start() {
  const id = game.id, o = game.o;
  lsSet("ka_opt_" + id, o);
  if (o.mode === "two" && (id === "domino" || id === "sea")) o.mode = "cpu";
  top();
  ({chess: chessNew, draughts: drNew, xo: xoNew, domino: dmNew, sea: seaNew})[id]();
}
function onClick(e) {
  const t = e.target;
  if (!root || !t.closest || !root.contains(t) || !t.closest(".ka")) return;
  let el;
  if ((el = t.closest("[data-kg]"))) { openGame(el.dataset.kg); return; }
  if (t.closest("[data-kh]")) { window.ZAdult.back(); return; }
  if (t.closest("[data-knfind]")) { netFind(); return; }
  if (t.closest("[data-kncode]")) { netCode(); return; }
  if (t.closest("[data-knjoin]")) { const v = (document.getElementById("kacode") || {}).value || ""; netJoin(v.replace(/\D/g, "")); return; }
  if (t.closest("[data-kncancel]")) { netLeave(); openGame(game.id); return; }
  if (t.closest("[data-knresign]")) { netResign(); return; }
  if (t.closest("[data-kncopy]")) { try { navigator.clipboard.writeText(game.code); haptic("ok"); } catch (e) {} return; }
  if (t.closest("[data-knshare]")) { netShare(); return; }
  if (game && game.setup) {
    if ((el = t.closest("[data-kmode]"))) { game.o.mode = el.dataset.kmode; openGameKeep(); return; }
    if ((el = t.closest("[data-klvl]"))) { game.o.lvl = +el.dataset.klvl; openGameKeep(); return; }
    if ((el = t.closest("[data-kside]"))) { game.o.side = el.dataset.kside; openGameKeep(); return; }
    if (t.closest("[data-kstart]")) { start(); return; }
    return;
  }
  if (!game) return;
  if (game.net && (t.closest("[data-kagain]") || t.closest("[data-knagain]"))) { netStop(); const id = game.id; openGame(id); return; }
  if (game.net && game.id === "domino") { if ((el = t.closest("[data-dmt]"))) { dmNetTap(+el.dataset.dmt); return; }
    if ((el = t.closest("[data-kdmside]"))) { dmNetPlay(game.sel, el.dataset.kdmside); return; }
    if (t.closest("[data-kdmdraw]")) { netAct(game.s.pile ? {a: "draw"} : {a: "pass"}); return; } }
  if (game.net && game.id === "sea") { if ((el = t.closest("[data-sea]"))) { seaNetTap(+el.dataset.sea); return; } }
  if (t.closest("[data-knew]") || t.closest("[data-kagain]")) { clearTimers(); if (game.id === "xo") xoNew(); else start2(); return; }
  if (t.closest("[data-kundo]")) { if (game.id === "chess") chessUndo(); else if (game.id === "draughts") drUndo(); return; }
  if ((el = t.closest("[data-csq]"))) { chessTap(+el.dataset.csq); return; }
  if ((el = t.closest("[data-dsq]"))) { drTap(+el.dataset.dsq); return; }
  if ((el = t.closest("[data-xo]"))) { const i = +el.dataset.xo; if (!game.over && !game.netOver && !game.b[i] && (!game.me || game.turn === game.me)) xoDo(i); return; }
  if ((el = t.closest("[data-dmt]"))) { dmTap(+el.dataset.dmt); return; }
  if ((el = t.closest("[data-kdmside]"))) { const g = game; if (g.sel >= 0) { const i = g.sel; g.sel = -1; dmPlace(g, "me", i, el.dataset.kdmside); g.msg = ""; dmAfter("me"); } return; }
  if (t.closest("[data-kdmdraw]")) { const g = game; if (g.pile.length) { g.me.push(g.pile.pop()); g.msg = ""; sfx.move(); drawDm(); } else { g.msg = T("Siz o'tkazdingiz", "Вы пропустили", "You passed"); dmAfter("me"); } return; }
  if (t.closest("[data-kdmnext]")) { clearTimers(); dmNew(!game.over.match); return; }
  if (t.closest("[data-kseashuffle]")) { game.mine = seaPlace(); haptic(); drawSea(); return; }
  if (t.closest("[data-kseago]")) { game.ready = true; haptic("ok"); drawSea(); return; }
  if ((el = t.closest("[data-sea]"))) { seaTap(+el.dataset.sea); return; }
}
function openGameKeep() { const id = game.id; const o = game.o; lsSet("ka_opt_" + id, o); openGame(id); }
function start2() { const id = game.id, o = game.o; game = {id, o}; start(); }
document.addEventListener("click", onClick);

window.ZAdult = {
  home(el, seg, aud) {
    if (el) root = el;
    if (seg != null) segHtml = seg;
    if (aud != null) audHtml = aud;
    if (game && (game.netPhase || (game.net && !game.netOver && !game.over))) netLeave();
    netStop(); clearTimers(); game = null;
    if (root) root.innerHTML = homeHtml();
    top();
  },
  busy() { return !!game; },
  back() {
    if (game && (game.net || game.netPhase) && !(game.netOver || game.over)) {
      if (game.netPhase || (game.armed && Date.now() - game.armed < 3500)) { netLeave(); openGame(game.id); return; }
      game.armed = Date.now(); haptic("err"); netToast(T("Chiqsangiz — taslim bo'lasiz. Yana bosing", "Выход = сдача. Нажмите ещё раз", "Leaving = resigning. Tap again")); return;
    }
    if (game && game.net) netStop();
    if (game && !game.setup && game.id) { clearTimers(); openGame(game.id); } else { clearTimers(); game = null; this.home(); }
  },
  stop() { if (game && (game.netPhase || (game.net && !game.netOver && !game.over))) netLeave(); netStop(); clearTimers(); game = null; },
  // testlar uchun
  _chess: {chessStart, legal, make, inCheck, chessAI}, _dr: {drStart, drMoves, drMake, drAI}, _xo: {xoWin, xoAI}, _sea: {seaPlace, seaShoot},
};
})();
