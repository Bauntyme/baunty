/* 🍲 Taomlar — Mini App bo'limi: «Bugun nima pishiramiz?» (Rishton lagani), retseptlar, pishirish rejimi, admin tahriri.
   index.html dan window.ZFood orqali boshqariladi (open / close / busy / show). */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : t === "hit" ? tg.HapticFeedback.impactOccurred("medium") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
const MEALS = [["b", "🌅", "Nonushta"], ["l", "☀️", "Tushlik"], ["d", "🌙", "Kechki"]];
const MEAL_TO = {b: "nonushtaga", l: "tushlikka", d: "kechki ovqatga"};
const KINDS = [["", "Hammasi"], ["milliy", "🇺🇿 Milliy"], ["jahon", "🌍 Jahon"], ["salat", "🥗 Salat"], ["shirin", "🍰 Shirinlik"], ["fav", "❤️ Sevimli"]];
const LEVEL = {1: "Oson", 2: "O'rta", 3: "Qiyin"};
const ICO = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>',
  heart: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 21s-7.6-4.6-9.5-9.3C1.2 8.3 3.5 4.8 7 4.8c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3 3.5 0 5.8 3.5 4.5 6.9C19.6 16.4 12 21 12 21z"/></svg>',
  heartO: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 21s-7.6-4.6-9.5-9.3C1.2 8.3 3.5 4.8 7 4.8c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3 3.5 0 5.8 3.5 4.5 6.9C19.6 16.4 12 21 12 21z"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
};

let items = null, loading = null, opened = false, mounted = false;
let me = {admin: false, fav: []}, meal = (() => { const h = (new Date().getUTCHours() + 5) % 24; return h >= 5 && h < 11 ? "b" : h < 16 ? "l" : "d"; })();
let kind = "", q = "", seen = [], spinning = false, rot = 0;
const full = new Map();
const stack = [{v: "home"}];
const top = () => stack[stack.length - 1];

// ------------------------------------------------------------------ yordamchilar
async function api(path, body, form) {
  try {
    const r = await fetch(path, {method: body || form ? "POST" : "GET", cache: "no-store",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body ? {"Content-Type": "application/json"} : {}),
      body: form || (body ? JSON.stringify(body) : undefined)});
    if (r.status === 401) return {ok: false, error: "auth"};
    return await r.json();
  } catch (e) { return {ok: false, error: "network"}; }
}
function load(force) {
  if (loading && !force) return loading;
  loading = api("api/food").then((r) => { if (r.ok) items = r.items; return items; }).finally(() => { loading = null; });
  return loading;
}
async function getFull(id) {
  if (full.has(id)) return full.get(id);
  const r = await api(`api/food/r/${id}`);
  if (r.ok) full.set(id, r.r);
  return r.ok ? r.r : null;
}
const mins = (m) => m >= 60 ? `${Math.floor(m / 60)} s${m % 60 ? ` ${m % 60} d` : ""}` : `${m} daq`;
const mealsTxt = (ml) => MEALS.filter(([k]) => ml.includes(k)).map(([, , n]) => n.toLowerCase()).join(", ");
const kindTxt = (k) => (KINDS.find(([x]) => x === k) || ["", ""])[1];
function pic(x, big) {
  if (x.pv) return `<img src="rc/${x.id}${big ? "" : "_s"}.webp?v=${x.pv}" alt="" loading="lazy" decoding="async">`;
  return `<span class="em" aria-hidden="true">${esc(x.e || "🍲")}</span>`;
}
const bg = (x) => `background:radial-gradient(circle at 50% 62%,${shade(x.c, 70)},${x.c} 58%,${shade(x.c, -55)})`;
function shade(hex, p) {
  const n = parseInt(String(hex || "#C27A2E").slice(1), 16) || 0xC27A2E;
  const f = (v) => Math.max(0, Math.min(255, Math.round(p > 0 ? v + (255 - v) * p / 100 : v * (1 + p / 100))));
  return "#" + [n >> 16, (n >> 8) & 255, n & 255].map(f).map((v) => v.toString(16).padStart(2, "0")).join("");
}
function qty(q0, unit, k) {
  if (q0 == null) return esc(unit || "");
  let v = q0 * k;
  if (/dona|bosh|tishcha|bo'lak|banka|shox|bog'/.test(unit)) v = Math.max(0.5, Math.round(v * 2) / 2);
  else v = v >= 100 ? Math.round(v / 10) * 10 : v >= 10 ? Math.round(v) : Math.round(v * 10) / 10;
  return `${String(v).replace(".", ",")} ${esc(unit || "")}`.trim();
}
const pool = () => (items || []).filter((x) => x.ml.includes(meal));
function backBar(title) {
  return `<div class="fd-top"><button class="fd-back" data-act="back" aria-label="Orqaga">${ICO.back}</button><b>${title}</b></div>`;
}

// ------------------------------------------------------------------ 🏠 bosh sahifa
function segHtml() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["food", "Taomlar"]];
  return `<div class="fd-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "food" ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`;
}
function laganSvg() {
  return `<svg class="rim" viewBox="0 0 250 250" aria-hidden="true"><defs><pattern id="fdpt" width="28" height="28" patternUnits="userSpaceOnUse" patternTransform="rotate(12)">
    <path d="M14 2c4 6 4 10 0 12-4-2-4-6 0-12zM14 26c-4-6-4-10 0-12 4 2 4 6 0 12z" fill="#2F5FD0"/><circle cx="2" cy="14" r="2.5" fill="#F2B84B"/><circle cx="26" cy="14" r="2.5" fill="#F2B84B"/></pattern></defs>
    <circle cx="125" cy="125" r="122" fill="#F6EEDC"/><circle cx="125" cy="125" r="118" fill="url(#fdpt)"/><circle cx="125" cy="125" r="118" fill="none" stroke="#1D3E8F" stroke-width="5"/>
    <circle cx="125" cy="125" r="72" fill="#F6EEDC" stroke="#1D3E8F" stroke-width="4"/></svg>`;
}
function viewHome() {
  if (!items) return `<div class="fd-bar">${segHtml()}</div><div class="fd-load"><i></i><i></i><i></i></div>`;
  const p = pool();
  const around = [...p].sort(() => Math.random() - 0.5).slice(0, 4);
  const favs = new Set(me.fav);
  const qq = q.trim().toLowerCase();
  const list = items.filter((x) => (kind === "fav" ? favs.has(x.id) : !kind || x.k === kind) && (!qq || x.t.toLowerCase().includes(qq)));
  const center = around[0];
  return `<div class="fd-bar">${segHtml()}</div>
  <h1 class="fd-hi">Bugun nima pishiramiz?<span>Mahalni tanlang — lagan aylanib, taom tanlab beradi</span></h1>
  <div class="fd-meal" role="tablist">${MEALS.map(([k, ic, n]) => `<button data-meal="${k}" role="tab" aria-selected="${k === meal}" class="${k === meal ? "on" : ""}">${ic} ${n}</button>`).join("")}</div>
  <div class="fd-lagan" id="fdlagan">
    <div class="spinr" id="fdrim" style="transform:rotate(${rot}deg)">${laganSvg()}</div>
    <div class="dish" id="fddish" style="${center ? bg(center) : ""}">${center ? pic(center) : "🍲"}</div><i class="ptr" aria-hidden="true"></i>
    ${around.map((x, i) => `<span class="ch c${i}">${esc(x.e)} ${esc(x.t)}</span>`).join("")}
  </div>
  <button class="fd-spin" data-act="spin"${p.length ? "" : " disabled"}>🎲 Tasodifiy tanlash <small>· ${p.length} ta ${MEALS.find(([k]) => k === meal)[2].toLowerCase()}</small></button>
  <div class="fd-lh"><span>Hamma taomlar</span><small>${items.length} ta</small></div>
  <label class="fd-q">${ICO.search}<input id="fdq" type="search" placeholder="Taom nomi…" value="${esc(q)}" autocomplete="off" aria-label="Taom qidirish"></label>
  <div class="fd-kinds">${KINDS.map(([k, n]) => `<button data-kind="${k}" class="${k === kind ? "on" : ""}">${n}</button>`).join("")}</div>
  ${me.admin ? `<button class="fd-add" data-act="new">＋ Yangi taom qo'shish</button>` : ""}
  <div class="fd-grid" id="fdgrid">${gridHtml(list)}</div>`;
}
function gridHtml(list) {
  if (!list.length) return `<p class="fd-empty">${kind === "fav" ? "Sevimli taomlar hali yo'q — retseptdagi 🤍 ni bosing." : "Hech narsa topilmadi."}</p>`;
  return list.map((x) => `<button class="fd-card" data-open="${x.id}"><span class="ph" style="${bg(x)}">${pic(x)}<i>${mins(x.mn)}</i></span>
    <b>${esc(x.t)}</b><small>${esc(mealsTxt(x.ml))} · ${LEVEL[x.lv] || ""}</small></button>`).join("");
}
async function spin() {
  if (spinning) return;
  const p = pool();
  if (!p.length) return;
  spinning = true; haptic("hit");
  const rim = $("fdrim"), dish = $("fddish");
  const req = api(`api/food/random?m=${meal}&ex=${seen.slice(-20).join(",")}`);
  rot += 900 + Math.floor(Math.random() * 360);
  if (rim) { rim.style.transition = RM ? "none" : "transform 1.9s cubic-bezier(.17,.67,.2,1)"; rim.style.transform = `rotate(${rot}deg)`; }
  let n = 0;
  const t = RM ? null : setInterval(() => { const x = p[n++ % p.length]; if (dish) { dish.style.cssText = bg(x); dish.innerHTML = pic(x); } if (n % 3 === 0) haptic(); }, 110);
  const [r] = await Promise.all([req, new Promise((ok) => setTimeout(ok, RM ? 200 : 1900))]);
  if (t) clearInterval(t);
  spinning = false;
  if (!r.ok || !r.r) { haptic("err"); return; }
  full.set(r.r.id, r.r); seen.push(r.r.id);
  if (dish) { dish.style.cssText = bg(r.r); dish.innerHTML = pic(r.r); dish.classList.add("land"); }
  haptic("ok");
  setTimeout(() => go({v: "res", id: r.r.id, hint: r.r.hint}), RM ? 0 : 450);
}

// ------------------------------------------------------------------ 🎲 natija
function viewRes(v) {
  const r = full.get(v.id);
  if (!r) return backBar("Lagan") + `<div class="fd-load"><i></i><i></i><i></i></div>`;
  const prev = seen.slice(0, -1).slice(-3).reverse().map((id) => (items || []).find((x) => x.id === id)).filter(Boolean);
  return backBar("Lagan") + `<h2 class="fd-h2">Bugun ${MEAL_TO[meal]} —<span>Yoqmasa — yana aylantiring</span></h2>
  <div class="fd-res">
    <div class="hero" style="${bg(r)}">${pic(r, true)}<span class="tag">${kindTxt(r.k)}</span>${r.ck >= 5 ? `<span class="tag t2">⭐ ${r.ck} marta pishirilgan</span>` : ""}</div>
    <div class="rb"><h3>${esc(r.t)}</h3>${r.d ? `<p>${esc(r.d)}</p>` : ""}
      <div class="facts"><div><b>${mins(r.mn)}</b><small>vaqt</small></div><div><b>${LEVEL[r.lv]}</b><small>qiyinligi</small></div><div><b>${r.sv} kishi</b><small>porsiya</small></div></div>
      ${r.tip ? `<div class="tip"><i>💡</i><span><b>Maslahat:</b> ${esc(r.tip)}</span></div>` : ""}
      ${v.hint ? `<p class="hint">${esc(v.hint)}</p>` : ""}
      <div class="acts"><button class="a1" data-open="${r.id}" data-cook="1">👩‍🍳 Pishiraman</button><button class="a2" data-act="again">🎲 Boshqasi</button></div></div>
  </div>
  ${prev.length ? `<div class="fd-prev">Avvalgilari: ${prev.map((x) => `<button data-open="${x.id}">${esc(x.e)} ${esc(x.t)}</button>`).join("")}</div>` : ""}`;
}
async function again() {
  haptic("hit");
  const r = await api(`api/food/random?m=${meal}&ex=${seen.slice(-20).join(",")}`);
  if (!r.ok || !r.r) { haptic("err"); return; }
  full.set(r.r.id, r.r); seen.push(r.r.id);
  top().id = r.r.id; top().hint = r.r.hint; render(); $("fdscroll").scrollTop = 0;
}

// ------------------------------------------------------------------ 📖 retsept
function viewRecipe(v) {
  const r = full.get(v.id);
  if (!r) return backBar("Retsept") + `<div class="fd-load"><i></i><i></i><i></i></div>`;
  const sv = v.sv || r.sv, k = sv / r.sv;
  v.have = v.have || {};
  const fav = me.fav.includes(r.id);
  const body = v.tab === "st"
    ? `<ol class="fd-steps">${r.st.map((s, i) => `<li><b>${i + 1}</b><p>${esc(s.t)}${s.m ? ` <span class="tm">⏱ ${s.m} daq</span>` : ""}</p></li>`).join("")}</ol>`
    : `<div class="fd-srv"><span>Necha kishiga?</span><span class="st"><button data-sv="-1" aria-label="Kamaytirish">−</button><b>${sv}</b><button data-sv="1" aria-label="Ko'paytirish">+</button></span></div>
      ${r.ing.map(([n, q0, u], i) => `<button class="fd-ing${v.have[i] ? " done" : ""}" data-ing="${i}" aria-pressed="${!!v.have[i]}"><i>${v.have[i] ? "✓" : ""}</i><span>${esc(n)}</span><b>${qty(q0, u, k)}</b></button>`).join("")}
      ${inTg ? `<button class="fd-shop" data-act="shop">🛒 ${Object.values(v.have).some(Boolean) ? "Yetmaganini" : "Ro'yxatni"} botga yuborish</button>` : ""}`;
  return `<div class="fd-rhero" style="${bg(r)}">${pic(r, true)}<button class="rb1" data-act="back" aria-label="Orqaga">${ICO.back}</button>
      ${inTg ? `<button class="rb2${fav ? " on" : ""}" data-act="fav" aria-label="Sevimli">${fav ? ICO.heart : ICO.heartO}</button>` : ""}</div>
  <div class="fd-rsheet"><h2>${esc(r.t)}</h2>
    <div class="meta"><span>⏱ ${mins(r.mn)}</span><span>🔥 ${LEVEL[r.lv]}</span><span>🍽 ${esc(mealsTxt(r.ml))}</span></div>
    ${r.d ? `<p class="desc">${esc(r.d)}</p>` : ""}
    <div class="fd-tabs" role="tablist"><button data-tab="ing" class="${v.tab !== "st" ? "on" : ""}" role="tab">Masalliqlar · ${r.ing.length}</button><button data-tab="st" class="${v.tab === "st" ? "on" : ""}" role="tab">Tayyorlash · ${r.st.length} qadam</button></div>
    ${body}
    ${r.tip ? `<div class="tip"><i>💡</i><span>${esc(r.tip)}</span></div>` : ""}
    ${me.admin ? `<div class="fd-adm"><button data-act="edit">✏️ Tahrirlash</button><button data-act="hide">🙈 Yashirish</button></div>` : ""}
  </div>
  <div class="fd-foot"><button class="fd-go" data-act="cookmode">▶ Bosqichma-bosqich pishirish</button></div>`;
}

// ------------------------------------------------------------------ 👩‍🍳 pishirish rejimi
let timer = null;
function viewCook(v) {
  const r = full.get(v.id), s = r.st[v.i], last = v.i === r.st.length - 1;
  const left = v.left ?? (s.m ? s.m * 60 : 0);
  return backBar(esc(r.t)) + `<div class="fd-cook">
    <div class="prog"><i style="width:${(v.i + 1) / r.st.length * 100}%"></i></div>
    <small>${v.i + 1}-qadam · ${r.st.length} tadan</small>
    <p class="txt">${esc(s.t)}</p>
    ${s.m ? `<div class="tmr${v.run ? " run" : ""}${left === 0 && v.started ? " done" : ""}"><b id="fdtm">${fmtT(left)}</b>
      <button data-act="timer">${v.run ? "⏸ To'xtatish" : left === 0 && v.started ? "✓ Tayyor" : v.started ? "▶ Davom etish" : `▶ ${s.m} daqiqa taymer`}</button></div>` : ""}
    <div class="nav"><button data-act="prev"${v.i ? "" : " disabled"}>← Oldingi</button>
      <button class="nx" data-act="${last ? "done" : "next"}">${last ? "✓ Tayyor!" : "Keyingi →"}</button></div></div>`;
}
const fmtT = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
function tick() {
  const v = top();
  if (v.v !== "cook" || !v.run) return;
  v.left = Math.max(0, (v.left ?? 0) - 1);
  const el = $("fdtm"); if (el) el.textContent = fmtT(v.left);
  if (v.left === 0) { v.run = false; clearInterval(timer); timer = null; haptic("ok"); try { tg.HapticFeedback.notificationOccurred("warning"); } catch (e) {} render(); }
}

// ------------------------------------------------------------------ ✏️ admin tahriri
function viewEdit(v) {
  const r = v.id ? full.get(v.id) : null;
  const f = v.f || (v.f = r ? {t: r.t, k: r.k, ml: r.ml, mn: r.mn, sv: r.sv, lv: r.lv, e: r.e, c: r.c, d: r.d, tip: r.tip,
    ing: r.ing.map(([n, q0, u]) => q0 == null ? `${n} — ${u}` : `${n} — ${String(q0).replace(".", ",")} ${u}`.trim()).join("\n"),
    st: r.st.map((s) => (s.m ? `[${s.m}] ` : "") + s.t).join("\n")} : {t: "", k: "milliy", ml: meal, mn: 30, sv: 4, lv: 1, e: "🍲", c: "#C27A2E", d: "", tip: "", ing: "", st: ""});
  const prev = v.preview || (r && r.pv ? `rc/${r.id}.webp?v=${r.pv}` : "");
  return backBar(r ? "Taomni tahrirlash" : "Yangi taom") + `<form class="fd-form" id="fdform" onsubmit="return false">
    <label class="up" style="${prev ? "" : bg(f)}">${prev ? `<img src="${esc(prev)}" alt="">` : `<span class="em">${esc(f.e)}</span>`}
      <span class="lb">📷 ${prev ? "Rasmni almashtirish" : "Rasm qo'shish"}</span><input type="file" id="fdphoto" accept="image/*" hidden></label>
    <label class="ff">Nomi<input name="t" value="${esc(f.t)}" maxlength="120" placeholder="Masalan: Qovoqli manti" required></label>
    <div class="ff">Qaysi mahalga?<div class="pills">${MEALS.map(([k, ic, n]) => `<button type="button" data-fml="${k}" class="${f.ml.includes(k) ? "on" : ""}">${ic} ${n}</button>`).join("")}</div></div>
    <div class="ff">Turi<div class="pills">${KINDS.filter(([k]) => k && k !== "fav").map(([k, n]) => `<button type="button" data-fk="${k}" class="${f.k === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
    <div class="ff">Qiyinligi<div class="pills">${[1, 2, 3].map((l) => `<button type="button" data-flv="${l}" class="${+f.lv === l ? "on" : ""}">${LEVEL[l]}</button>`).join("")}</div></div>
    <div class="row3"><label class="ff">Vaqt (daq)<input name="mn" inputmode="numeric" value="${esc(f.mn)}"></label>
      <label class="ff">Necha kishi<input name="sv" inputmode="numeric" value="${esc(f.sv)}"></label>
      <label class="ff">Belgi<input name="e" value="${esc(f.e)}" maxlength="8"></label></div>
    <label class="ff">Qisqa tavsif<textarea name="d" rows="2" maxlength="600">${esc(f.d)}</textarea></label>
    <label class="ff">Masalliqlar <small>— har biri yangi qatorda: «Mol go'shti — 1 kg», «Tuz — ta'bga»</small><textarea name="ing" rows="7">${esc(f.ing)}</textarea></label>
    <label class="ff">Tayyorlash <small>— har qadam yangi qatorda; taymer uchun boshiga [15]</small><textarea name="st" rows="7">${esc(f.st)}</textarea></label>
    <label class="ff">💡 Maslahat <small>(ixtiyoriy)</small><textarea name="tip" rows="2" maxlength="400">${esc(f.tip)}</textarea></label>
    ${v.err ? `<p class="err" role="alert">${esc(v.err)}</p>` : ""}
    <button type="button" class="fd-save" data-act="save"${v.busy ? " disabled" : ""}>${v.busy ? "Saqlanmoqda…" : "✓ Saqlash"}</button></form>`;
}
function readForm() {
  const v = top(), fm = $("fdform"); if (!fm) return;
  for (const el of fm.querySelectorAll("[name]")) v.f[el.name] = el.value;
}
async function saveEdit() {
  const v = top(); readForm();
  v.busy = true; v.err = ""; render();
  const fd = new FormData();
  fd.append("data", new Blob([JSON.stringify(Object.assign({id: v.id || 0}, v.f))], {type: "application/json"}));
  if (v.file) fd.append("photo", v.file, v.file.name || "rasm.jpg");
  const r = await api("api/food/admin/save", null, fd);
  v.busy = false;
  if (!r.ok) { v.err = r.error === "auth" ? "Faqat admin" : r.error || "Saqlab bo'lmadi"; haptic("err"); render(); return; }
  haptic("ok"); full.set(r.id, r.r); await load(true);
  stack.pop();
  if (top().v === "recipe" && top().id === r.id) render(); else go({v: "recipe", id: r.id});
  if (r.warn) alert(r.warn);
}

// ------------------------------------------------------------------ chizish va boshqaruv
function render() {
  const v = top(), el = $("fdview");
  if (!el) return;
  el.innerHTML = v.v === "home" ? viewHome() : v.v === "res" ? viewRes(v) : v.v === "recipe" ? viewRecipe(v) : v.v === "cook" ? viewCook(v) : viewEdit(v);
  $("food").dataset.v = v.v;
  updateBack();
}
function go(v) { stack.push(v); haptic(); render(); $("fdscroll").scrollTop = 0; }
function back() {
  if (stack.length > 1) { const was = stack.pop(); if (was.v === "cook" && timer) { clearInterval(timer); timer = null; } render(); }
}
function updateBack() {
  if (!tg || !tg.BackButton) return;
  try {
    if (opened && stack.length > 1) tg.BackButton.show();
    else if (opened && (!window.ZK_canHideBack || window.ZK_canHideBack())) tg.BackButton.hide();
  } catch (e) {}
}
async function openRecipe(id, cookIt) {
  go({v: "recipe", id, tab: "ing"});
  if (!full.has(id)) { await getFull(id); if (top().v === "recipe" && top().id === id) render(); }
  if (cookIt && inTg) api("api/food/cook", {id});
}

function onClick(e) {
  const t = e.target;
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "food" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  const m = t.closest("[data-meal]");
  if (m) { meal = m.dataset.meal; haptic(); render(); return; }
  const kd = t.closest("[data-kind]");
  if (kd) { kind = kd.dataset.kind; haptic(); document.querySelectorAll("#fdview [data-kind]").forEach((b) => b.classList.toggle("on", b === kd)); refreshGrid(); return; }
  const o = t.closest("[data-open]");
  if (o) { openRecipe(+o.dataset.open, !!o.dataset.cook); return; }
  const tb = t.closest("[data-tab]");
  if (tb) { top().tab = tb.dataset.tab; haptic(); render(); return; }
  const sv = t.closest("[data-sv]");
  if (sv) { const v = top(), r = full.get(v.id); v.sv = Math.max(1, Math.min(30, (v.sv || r.sv) + +sv.dataset.sv)); haptic(); render(); return; }
  const ing = t.closest("[data-ing]");
  if (ing) { const v = top(); v.have[ing.dataset.ing] = !v.have[ing.dataset.ing]; haptic(); render(); return; }
  const fml = t.closest("[data-fml]");
  if (fml) { readForm(); const f = top().f, k = fml.dataset.fml; f.ml = f.ml.includes(k) ? f.ml.replace(k, "") : f.ml + k; haptic(); render(); return; }
  const fk = t.closest("[data-fk]");
  if (fk) { readForm(); top().f.k = fk.dataset.fk; haptic(); render(); return; }
  const flv = t.closest("[data-flv]");
  if (flv) { readForm(); top().f.lv = +flv.dataset.flv; haptic(); render(); return; }
  const a = t.closest("[data-act]");
  if (!a) return;
  const act = a.dataset.act, v = top();
  if (act === "back") back();
  else if (act === "spin") spin();
  else if (act === "again") again();
  else if (act === "new") go({v: "edit"});
  else if (act === "edit") go({v: "edit", id: v.id});
  else if (act === "save") saveEdit();
  else if (act === "hide") {
    if (confirm("Bu taom ro'yxatdan yashirilsinmi?")) api("api/food/admin/hide", {id: v.id}).then((r) => { if (r.ok) { load(true).then(() => { stack.length = 1; render(); }); } });
  } else if (act === "fav") {
    api("api/food/fav", {id: v.id}).then((r) => { if (r.ok) { me.fav = r.fav; haptic(r.on ? "ok" : ""); render(); } });
  } else if (act === "shop") {
    const r = full.get(v.id), names = Object.values(v.have).some(Boolean) ? r.ing.filter((_, i) => !v.have[i]).map(([n]) => n) : null;
    a.disabled = true;
    api("api/food/shop", {id: v.id, sv: v.sv || r.sv, names}).then((res) => {
      a.textContent = res.ok ? "✓ Ro'yxat botga yuborildi" : "Yuborib bo'lmadi — botni ishga tushiring"; haptic(res.ok ? "ok" : "err");
    });
  } else if (act === "cookmode") go({v: "cook", id: v.id, i: 0});
  else if (act === "next" || act === "prev") {
    if (timer) { clearInterval(timer); timer = null; }
    v.i += act === "next" ? 1 : -1; v.left = undefined; v.run = false; v.started = false; render();
  } else if (act === "timer") {
    const s = full.get(v.id).st[v.i];
    if (v.left === 0 && v.started) return;
    if (v.run) { v.run = false; clearInterval(timer); timer = null; }
    else { v.left = v.left ?? s.m * 60; v.run = true; v.started = true; clearInterval(timer); timer = setInterval(tick, 1000); }
    haptic(); render();
  } else if (act === "done") {
    if (timer) { clearInterval(timer); timer = null; }
    haptic("ok"); stack.pop(); render();
    const el = document.createElement("div"); el.className = "fd-toast"; el.textContent = "🍽 Yoqimli ishtaha!";
    $("food").appendChild(el); setTimeout(() => el.remove(), 2200);
  }
}
function refreshGrid() {
  const g = $("fdgrid"); if (!g || !items) return;
  const favs = new Set(me.fav), qq = q.trim().toLowerCase();
  g.innerHTML = gridHtml(items.filter((x) => (kind === "fav" ? favs.has(x.id) : !kind || x.k === kind) && (!qq || x.t.toLowerCase().includes(qq))));
}

if (tg && tg.BackButton) tg.BackButton.onClick(() => { if (opened && stack.length > 1) back(); });

window.ZFood = {
  open() {
    if (!mounted) {
      mounted = true;
      const root = $("food");
      root.addEventListener("click", onClick);
      root.addEventListener("input", (e) => { if (e.target.id === "fdq") { q = e.target.value; refreshGrid(); } });
      root.addEventListener("change", (e) => {
        if (e.target.id !== "fdphoto" || !e.target.files || !e.target.files[0]) return;
        const v = top(); readForm(); v.file = e.target.files[0];
        if (v.preview) URL.revokeObjectURL(v.preview);
        v.preview = URL.createObjectURL(v.file); render();
      });
      if (inTg) api("api/food/me").then((r) => { if (r.ok) { me = r; if (opened && top().v === "home") render(); } });
    }
    opened = true;
    $("food").hidden = false; document.body.classList.add("fd-on");
    render();
    if (!items) load().then(() => { if (opened) render(); });
  },
  close() {
    opened = false;
    $("food").hidden = true; document.body.classList.remove("fd-on");
    updateBack();
  },
  show(id) { load().then(() => openRecipe(+id)); },
  busy() { return opened && stack.length > 1; },
};
})();
