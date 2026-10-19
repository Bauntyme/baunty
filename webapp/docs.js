/* 📄 Hujjatlar — Mini App bo'limi («qog'oz va siyoh»). index.html dan window.ZDocs orqali boshqariladi. */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success")
  : t === "err" ? tg.HapticFeedback.notificationOccurred("error")
  : t === "hit" ? tg.HapticFeedback.impactOccurred("medium") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const lsGet = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const toast = (t, ms = 2400) => { const el = $("toast"); el.textContent = t; el.classList.add("on");
  clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove("on"), ms); };
const mb = (n) => !n ? "" : n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1048576).toFixed(1).replace(".", ",")} MB`;

const ICO = {
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  up: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7 9l5-5 5 5M4 20h16"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 3 10 14M21 3l-7 18-4-7-7-4z"/></svg>',
  swap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
};
const KLABEL = {pdf: "PDF", word: "DOC", text: "TXT", ppt: "PPT", excel: "XLS", image: "JPG", zip: "ZIP"};
const LANG = {uz: "O'zbek", ru: "Rus", en: "Ingliz"};
const FLAG = {uz: "🇺🇿", ru: "🇷🇺", en: "🇬🇧"};
const TOOLS = {
  topdf: {n: "Hujjatni PDF qilish", d: "Word, PowerPoint, Excel", k: "word", ic: "W", accept: ".doc,.docx,.odt,.rtf,.txt,.ppt,.pptx,.odp,.pps,.ppsx,.xls,.xlsx,.ods,.csv", multi: true},
  img2pdf: {n: "Rasmlardan PDF", d: "Bitta yoki ko'p rasm → 1 fayl", k: "image", ic: "JPG", accept: "image/*", multi: true},
  pdf2jpg: {n: "PDF → rasm", d: "Har sahifa alohida JPG", k: "pdf", ic: "PDF", accept: ".pdf,application/pdf"},
  pdf2txt: {n: "PDF → matn", d: "Nusxa olsa bo'ladigan matn", k: "text", ic: "TXT", accept: ".pdf,application/pdf"},
  split: {n: "Sahifalarni ajratish", d: "Keraklisini tanlab oling", k: "pdf", ic: "✂", accept: ".pdf,application/pdf"},
  ocr: {n: "Rasmdan matn", d: "Suratdagi yozuvni o'qish", k: "image", ic: "OCR", accept: "image/*"},
  translate: {n: "Tarjima", d: "", accept: ".pdf,.doc,.docx,.odt,.rtf,.txt"},
  translit: {n: "Kirill ↔ Lotin", d: "", accept: ".pdf,.doc,.docx,.odt,.rtf,.txt"},
  todocx: {n: "Word qilib olish"},
};
const KIND_EXT = {pdf: [".pdf"], word: [".doc", ".docx", ".odt", ".rtf", ".docm", ".dot", ".dotx"], text: [".txt"],
  ppt: [".ppt", ".pptx", ".odp", ".pps", ".ppsx", ".pptm"], excel: [".xls", ".xlsx", ".ods", ".csv", ".xlsm"],
  image: [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".gif"]};
const kindOf = (name) => { const n = String(name || "").toLowerCase(); for (const [k, ex] of Object.entries(KIND_EXT)) if (ex.some((e) => n.endsWith(e))) return k; return null; };
const TOOL_KINDS = {topdf: ["word", "text", "ppt", "excel"], img2pdf: ["image"], pdf2jpg: ["pdf"], pdf2txt: ["pdf"], split: ["pdf"],
  ocr: ["image"], todocx: ["text"], translate: ["pdf", "word", "text"], translit: ["pdf", "word", "text"]};
const TR_EXT = [".pdf", ".docx", ".doc", ".odt", ".rtf", ".txt"];
const trOk = (f) => TR_EXT.some((e) => f.name.toLowerCase().endsWith(e));

let cfg = {stamp: true, max_mb: 50, translate: true, max_images: 50};
let bot = "", opened = false, mounted = false;
const files = new Map();                       // fid → meta
const stack = [];
let recent = lsGet("zk_drec", []);

// =================================================================== tarmoq
async function api(path, body) {
  try {
    const r = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body ? {"Content-Type": "application/json"} : {}),
      body: body ? JSON.stringify(body) : undefined});
    if (r.status === 401) return {ok: false, error: "auth"};
    if (r.status === 413) return {ok: false, error: "too_large"};
    return await r.json();
  } catch (e) { return {ok: false, error: "network"}; }
}
function upload(file, onProgress) {
  return new Promise((ok) => {
    const x = new XMLHttpRequest();
    x.open("POST", "api/docs/upload");
    x.setRequestHeader("X-Init-Data", inTg ? tg.initData : "");
    x.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
    x.onload = () => { try { ok(x.status === 413 ? {ok: false, error: "too_large"} : JSON.parse(x.responseText)); } catch (e) { ok({ok: false, error: "network"}); } };
    x.onerror = () => ok({ok: false, error: "network"});
    let name = file.name || "";
    if (!kindOf(name) && (file.type || "").startsWith("image/")) name = (name || "rasm") + "." + ((file.type.split("/")[1] || "jpg").replace("jpeg", "jpg"));
    const fd = new FormData(); fd.append("file", file, name || "fayl");
    x.send(fd);
  });
}
const ERR = {
  network: "📶 Internet bilan muammo. Qayta urinib ko'ring",
  auth: "⚠️ Ilovani yopib, qayta oching",
  rate: "⏳ Juda ko'p so'rov — birozdan keyin urinib ko'ring",
  expired: "⌛ Fayl muddati tugadi — qaytadan yuklang",
  type: "⚠️ Bu amal uchun mos fayl emas",
  too_large: "📦 Fayl juda katta",
  empty: "⚠️ Fayl bo'sh",
  translate_off: "🌐 Tarjima hozircha sozlanmagan — tez orada",
  bad_pages: "⚠️ Sahifalarni tanlang",
  bad_target: "⚠️ Tarjima tilini tanlang",
};
const errText = (r) => r.error === "rate" && r.per_hour ? `⏳ Soatiga ko'pi bilan ${r.per_hour} ta hujjat. Birozdan keyin davom eting` : (ERR[r.error] || "😔 Xatolik. Qayta urinib ko'ring");

// =================================================================== rasmlar va eskizlar
const thumbUrl = (f, i = 0) => f && f.thumbs > i ? `api/docs/t/${f.fid}/${i}` : "";
function sheet(f, i, w, h, num) {
  const u = thumbUrl(f, i);
  return `<div class="sh" style="width:${w}px;height:${h}px">${u ? `<img src="${u}" alt="" loading="lazy" decoding="async">` : `<div class="ln"></div>`}${num ? `<span class="num">${num}</span>` : ""}</div>`;
}
document.addEventListener("load", (e) => { const t = e.target; if (t.tagName === "IMG" && t.closest(".dx")) t.classList.add("ok"); }, true);
document.addEventListener("error", (e) => { const t = e.target; if (t.tagName === "IMG" && t.closest(".dx .sh")) t.replaceWith(Object.assign(document.createElement("div"), {className: "ln"})); }, true);
const fic = (k, sm) => `<div class="fic ${k || "text"}${sm ? " sm" : ""}">${KLABEL[k] || "FAYL"}</div>`;
function fileDesc(f) {
  const p = [];
  if (f.size) p.push(mb(f.size));
  if (f.pages) p.push(f.kind === "ppt" ? `${f.pages} slayd` : f.kind === "excel" ? `${f.pages} varaq` : `${f.pages} sahifa`);
  if (f.kind === "image" && f.w) p.push(`${f.w}×${f.h}`);
  return p.join(" · ");
}
const scriptLabel = (f) => f.lang === "uz" && f.script ? (f.script === "cyrl" ? "Kirill yozuvi" : "Lotin yozuvi") : f.lang ? `${LANG[f.lang]} tili` : "";

// =================================================================== ko'rinishlar
function segHTML() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["docs", "Hujjatlar"]];
  return `<div class="dx-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "docs" ? "on" : ""}">${l}</button>`).join("")}</div>`;
}
const bar = (title, left = "back", right = "") => `<div class="dx-bar"><button class="dx-ib" data-nav="${left}">${ICO[left === "home" ? "x" : left]}</button>
  <span class="dx-ttl">${esc(title)}</span>${right ? `<button class="dx-ib" data-nav="${right}">${ICO[right]}</button>` : '<span style="width:40px"></span>'}</div>`;

function vHome() {
  const tiles = ["topdf", "img2pdf", "pdf2jpg", "pdf2txt", "split", "ocr"].map((k) => { const t = TOOLS[k];
    return `<button class="dx-tool" data-tool="${k}"><div class="fic ${t.k} sm">${t.ic}</div><div><b>${t.n}</b><small>${t.d}</small></div></button>`; }).join("");
  const rec = recent.slice(0, 5).map((r) => `<div class="dx-row">${fic(r.k)}<div class="t"><b>${esc(r.name)}</b><small>${esc(r.desc)}</small></div><small>${ago(r.at)}</small></div>`).join("");
  return {html: `<div class="dx-bar">${segHTML()}</div>
    <h1 class="dx-h" style="font-size:27px">Hujjat bilan<br>nima qilamiz?</h1>
    <button class="dx-drop" data-pick="">
      <span class="glow"></span>
      <span class="art"><span style="left:0;top:12px;transform:rotate(-11deg)">${sheet(null, 0, 48, 64)}</span>
        <span style="left:26px;top:4px;transform:rotate(3deg)">${sheet(null, 0, 48, 64)}</span>
        <span style="left:56px;top:18px;transform:rotate(13deg)"><div class="fic pdf" style="width:42px;height:54px">PDF</div></span></span>
      <span style="flex:1;position:relative"><b>Faylni tanlang</b><small>Turini o'zim aniqlayman va eng kerakli amalni taklif qilaman</small>
        <span class="go">${ICO.up} Yuklash</span></span>
    </button>
    <button class="dx-band" data-tool="translate"><span class="aa">Aa</span><span style="flex:1"><b>Tarjima va Kirill ↔ Lotin</b>
      <small>Jadval, shrift, rasmlar joyida qoladi</small></span><span class="l">UZ·RU·EN</span></button>
    <div class="dx-sec"><h3>Barcha amallar</h3></div>
    <div class="dx-tools">${tiles}</div>
    ${rec ? `<div class="dx-sec"><h3>Oxirgi fayllar</h3><button data-clr="1">Tozalash</button></div>${rec}` : ""}
    <p class="dx-p" style="text-align:center;color:var(--mute);font-size:12px;padding:22px 30px 0">Fayllar 3 soatdan keyin serverdan butunlay o'chiriladi · ${cfg.max_mb} MB gacha</p>`};
}
function ago(t) {
  const s = (Date.now() / 1000) - t;
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} daq`;
  if (s < 86400) return `${Math.round(s / 3600)} soat`;
  return s < 172800 ? "Kecha" : `${Math.round(s / 86400)} kun`;
}

// ---------- yuklanmoqda
function vUploading(v) {
  const rows = v.items.map((it) => `<div class="dx-card dx-q ${it.err ? "error" : it.done ? "done" : "now"}">${fic(kindOf(it.name), true)}
    <div class="t"><b>${esc(it.name)}</b><small>${it.err ? esc(it.err) : it.done ? "Yuklandi" : `${Math.round((it.p || 0) * 100)}% · ${mb(it.size)}`}</small>
    ${!it.done && !it.err ? `<div class="prog" style="margin-top:7px;height:5px"><i style="width:${Math.round((it.p || 0) * 100)}%"></i></div>` : ""}</div>
    ${it.err ? "" : it.done ? '<span class="tick">✓</span>' : '<span class="spin ink"></span>'}</div>`).join("");
  return {html: bar("Yuklanmoqda", "home") + `<h1 class="dx-h">Fayl yuklanmoqda…</h1><div class="dx-list" style="padding-top:16px">${rows}</div>`};
}

// ---------- fayl tanlandi — aqlli tavsiya
function suggestions(f) {
  const s = [];
  const uzScript = f.lang === "uz" && f.script;
  if (["word", "text", "ppt", "excel"].includes(f.kind)) s.push({tool: "topdf", n: "PDF qilish", d: "Shrift va jadvallar o'zgarmaydi", main: 1});
  if (f.kind === "image") { s.push({tool: "img2pdf", n: "PDF qilish", d: "Rasm A4 varaqqa joylanadi", main: 1}); s.push({tool: "ocr", n: "Rasmdan matn olish", d: "Suratdagi yozuvni nusxalash mumkin bo'ladi", ico: "OCR", bg: "#EFE3F3", fg: "#7A2E8E"}); }
  if (trOk(f) && TOOL_KINDS.translate.includes(f.kind)) {
    if (uzScript) s.push({tool: "translit", to: f.script === "cyrl" ? "latn" : "cyrl", n: f.script === "cyrl" ? "Lotin yozuviga o'girish" : "Kirill yozuviga o'girish",
      d: `${f.script === "cyrl" ? "Kirillcha" : "Lotincha"} aniqlandi — bir bosishda`, ico: f.script === "cyrl" ? "Ўa" : "Aў", bg: "#FBEFD3", fg: "#9A6A0B", main: f.kind === "pdf" && !s.length && f.script === "cyrl"});
    s.push({tool: "translate", n: "Tarjima qilish", d: "O'zbek ↔ Rus ↔ Ingliz", ico: "Aa", bg: "#E3ECFB", fg: "#2F5BD8", main: f.kind === "pdf" && !s.some((x) => x.main) && cfg.translate});
  }
  if (f.kind === "pdf") {
    s.push({tool: "pdf2jpg", n: "PDF → rasm", d: "Har sahifa alohida JPG", ico: "JPG", bg: "#EFE3F3", fg: "#7A2E8E"});
    if ((f.pages || 0) > 1) s.push({tool: "split", n: "Sahifalarni ajratish", d: `${f.pages} sahifadan keraklisini oling`, ico: "✂", bg: "#F6E1DE", fg: "#D2463A"});
    s.push({tool: "pdf2txt", n: "Matnini olish", d: "Nusxa olsa bo'ladigan matn", ico: "TXT", bg: "#E6E8EF", fg: "#4A5170"});
  }
  if (!s.some((x) => x.main) && s[0]) s[0].main = 1;
  return s;
}
function sugHTML(x, f) {
  const icon = x.main ? fic(x.tool === "topdf" || x.tool === "img2pdf" ? "pdf" : f.kind, true)
    : `<span class="ico" style="background:${x.bg};color:${x.fg}">${x.ico}</span>`;
  return `<button class="dx-sug${x.main ? " main" : ""}" data-run="${x.tool}" data-to="${x.to || ""}">${icon}
    <span style="flex:1"><b>${x.n}</b><small>${x.d}</small></span>${x.main ? '<span class="ar">→</span>' : ""}</button>`;
}
function vFile(v) {
  const f = files.get(v.fid);
  if (!f) return vHome();
  const s = suggestions(f);
  const main = s.filter((x) => x.main || ["translit", "translate", "ocr"].includes(x.tool)).slice(0, 3);
  const rest = s.filter((x) => !main.includes(x));
  const th = f.thumbs ? `<div class="thumbs">${Array.from({length: Math.min(f.thumbs, 8)}, (_, i) => sheet(f, i, 58, f.kind === "image" ? 76 : 80, f.kind === "image" ? "" : i + 1)).join("")}</div>` : "";
  const warn = scriptLabel(f);
  return {html: bar("Fayl tanlandi", "back", "x") + `
    <div class="dx-card dx-file"><div class="hd">${fic(f.kind)}<div style="flex:1;min-width:0"><b>${esc(f.name)}</b>
      <small>${esc(fileDesc(f))}${warn ? ` · <span class="warn">${esc(warn)}</span>` : ""}</small></div></div>${th}</div>
    ${f.broken ? `<div class="dx-info" style="background:#F6E1DE;color:#8C2B22">⚠️ Fayl buzilgan ko'rinadi — natija chiqmasligi mumkin</div>` : ""}
    <div class="dx-sec"><h3>Tavsiya qilamiz</h3><span>shu fayl uchun</span></div>
    <div class="dx-list">${main.map((x) => sugHTML(x, f)).join("")}</div>
    ${rest.length ? `<div class="dx-chips" style="padding-top:14px">${rest.map((x) => `<button class="dx-chip" data-run="${x.tool}">${x.n}</button>`).join("")}</div>` : ""}`};
}

// ---------- tarjima
function vTranslate(v) {
  const f = files.get(v.fid);
  const src = v.source || f.lang || "ru";
  const tgts = [["uz", "latn", "O'zbek (lotin)"], ["uz", "cyrl", "Ўзбек (кирилл)"], ["ru", "", "Rus"], ["en", "", "English"]]
    .filter(([l, sc]) => l !== src || (l === "uz" && sc && sc !== (f.script || "latn") && false));
  if (!tgts.some(([l, sc]) => l === v.target && (l !== "uz" || sc === v.script))) { const [l, sc] = tgts[0]; v.target = l; v.script = sc || "latn"; }
  const pv = !cfg.translate ? `<div class="dx-info" style="background:#FBEFD3;color:#6E4B05">🌐 Tarjima hozircha sozlanmagan — tez orada ishga tushadi</div>`
    : !f.sample ? "" : `<div class="dx-sec" style="padding-top:16px"><h3>Oldindan ko'ring</h3><span>1-sahifa</span></div>
    <div class="dx-card dx-pv"><div><small>ASL MATN</small><p>${esc((f.sample || "").slice(0, 220))}…</p></div>
    <div><small>TARJIMA</small>${v.pv ? `<p style="font-weight:600">${esc(v.pv.slice(0, 260))}…</p>` : v.pvErr ? `<p style="color:var(--mute)">Ko'rinishni olib bo'lmadi — tarjima baribir ishlaydi</p>` : '<div class="sk"></div><div class="sk" style="width:70%"></div>'}</div></div>`;
  return {html: bar("Tarjima") + `<h1 class="dx-h">Qaysi tilga<br>tarjima qilamiz?</h1>
    <div class="dx-langs"><div class="dx-lang"><small>Fayl tili${f.lang && !v.source ? " · aniqlandi" : ""}</small><b>${FLAG[src]} ${LANG[src]}</b></div>
      <span class="dx-ib" style="background:var(--ink);color:var(--paper)">${ICO.swap}</span>
      <div class="dx-lang on"><small>Tarjima tili</small><b>${FLAG[v.target]} ${LANG[v.target]}${v.target === "uz" ? (v.script === "cyrl" ? " (kir.)" : "") : ""}</b></div></div>
    <div class="dx-chips">${tgts.map(([l, sc, lab]) => `<button class="dx-chip${l === v.target && (l !== "uz" || sc === v.script) ? " on" : ""}" data-tgt="${l}" data-sc="${sc}">${lab}</button>`).join("")}</div>
    <div style="padding:14px 18px 0;color:var(--mute);font-size:12.5px;font-weight:700">Fayl tili noto'g'ri aniqlangan bo'lsa:</div>
    <div class="dx-chips" style="padding-top:8px">${["uz", "ru", "en"].map((l) => `<button class="dx-chip${l === src ? " on" : ""}" data-src="${l}">${FLAG[l]} ${LANG[l]}</button>`).join("")}</div>
    ${pv}
    <div class="dx-info">✓ Jadvallar, shriftlar va rasmlar joyida qoladi</div>`,
  foot: `<button class="dx-btn ink" data-go="translate"${cfg.translate ? "" : " disabled"}>Tarjima qilish${f.pages ? ` · ${f.pages} sahifa` : ""}</button>
    <div class="note">${f.kind === "pdf" ? "Eng aniq natija Word (.docx) faylda bo'ladi · " : ""}tayyor fayl chatga keladi</div>`};
}
let pvTimer = null;
function loadPreview(v) {
  const f = files.get(v.fid);
  if (!cfg.translate || !f || !f.sample) return;
  const key = `${v.source || f.lang}|${v.target}|${v.script}`;
  if (v.pvKey === key) return;
  v.pvKey = key; v.pv = ""; v.pvErr = false;
  clearTimeout(pvTimer);
  pvTimer = setTimeout(async () => {
    const r = await api("api/docs/preview", {fid: v.fid, target: v.target, script: v.script, source: v.source || undefined});
    if (v.pvKey !== key) return;
    if (r.ok) v.pv = r.out; else v.pvErr = true;
    if (top() === v) render(true);
  }, 250);
}

// ---------- sahifalarni ajratish
function vSplit(v) {
  const f = files.get(v.fid);
  const n = f.pages || 0;
  const tiles = Array.from({length: Math.min(n, 400)}, (_, i) => { const p = i + 1, on = v.sel.has(p);
    return `<button class="dx-pg${on ? " on" : ""}" data-pg="${p}"><span class="ck">${on ? "✓" : ""}</span>${sheet(i < (f.thumbs || 0) ? f : null, i, 72, 96, p).replace('style="width:72px;height:96px"', "")}</button>`; }).join("");
  return {html: bar("Sahifalarni ajratish") + `<h1 class="dx-h">Qaysi sahifalar<br>kerak?</h1>
    <div class="dx-range"><input id="dxrange" inputmode="numeric" autocomplete="off" placeholder="Masalan: 1-3, 7" value="${esc(v.spec || "")}">
      <button class="dx-chip" data-sel="odd">Toq</button><button class="dx-chip" data-sel="even">Juft</button></div>
    <div class="dx-chips" style="padding-top:10px"><button class="dx-chip" data-sel="all">Hammasi</button><button class="dx-chip" data-sel="none">Tozalash</button>
      <span style="margin-left:auto;align-self:center;color:var(--mute);font-weight:700;font-size:13px">${n} sahifa</span></div>
    <div class="dx-pages">${tiles}</div>
    <div class="dx-chips" style="padding-top:16px"><button class="dx-chip${v.mode !== "each" ? " on" : ""}" data-mode2="one">Bitta PDF qilib</button>
      <button class="dx-chip${v.mode === "each" ? " on" : ""}" data-mode2="each">Har biri alohida</button></div>`,
  foot: `<button class="dx-btn ink" data-go="split"${v.sel.size ? "" : " disabled"}>${v.sel.size ? `${v.sel.size} ta sahifani olish` : "Sahifalarni tanlang"}</button>`};
}
function specOf(sel) {
  const a = [...sel].sort((x, y) => x - y), out = [];
  for (let i = 0; i < a.length; i++) { let j = i; while (j + 1 < a.length && a[j + 1] === a[j] + 1) j++; out.push(i === j ? `${a[i]}` : `${a[i]}-${a[j]}`); i = j; }
  return out.join(", ");
}
function parseSpec(s, n) {
  const sel = new Set();
  for (const ch of String(s).split(/[,\s;]+/)) {
    const m = ch.match(/^(\d+)\s*[-–]\s*(\d+)$/);
    if (m) { let a = +m[1], b = +m[2]; if (a > b) [a, b] = [b, a]; for (let p = Math.max(1, a); p <= Math.min(n, b); p++) sel.add(p); }
    else if (/^\d+$/.test(ch) && +ch >= 1 && +ch <= n) sel.add(+ch);
  }
  return sel;
}

// ---------- rasmlardan PDF
function vImages(v) {
  const tiles = v.items.map((it, i) => { const f = it.fid && files.get(it.fid);
    return `<div class="dx-im${v.drag === i ? " drag" : ""}" data-im="${i}">${f && f.thumbs ? `<img src="${thumbUrl(f)}" alt="">` : ""}
      <span class="n">${i + 1}</span><button class="x" data-rm="${i}" aria-label="O'chirish">${ICO.x}</button>
      ${!it.fid && !it.err ? `<span class="up"><i style="width:${Math.round((it.p || 0) * 100)}%"></i></span>` : ""}</div>`; }).join("");
  const ready = v.items.filter((x) => x.fid).length, busy = v.items.some((x) => !x.fid && !x.err);
  return {html: bar("Rasmlardan PDF") + `<h1 class="dx-h">${v.items.length} ta rasm —<br>bitta PDF</h1>
    <p class="dx-p">Tartibini o'zgartirish uchun rasmni bosib turib suring</p>
    <div class="dx-imgs" id="dximgs">${tiles}${v.items.length < cfg.max_images ? `<button class="dx-add" data-pick="img2pdf+">${ICO.plus}Qo'shish</button>` : ""}</div>
    <div style="padding:16px 18px 0;color:var(--mute);font-size:13px;font-weight:700">Sahifa o'lchami</div>
    <div class="dx-chips" style="padding-top:10px"><button class="dx-chip${v.size !== "fit" ? " on" : ""}" data-size="a4">A4</button>
      <button class="dx-chip${v.size === "fit" ? " on" : ""}" data-size="fit">Rasm o'lchamida</button></div>`,
  foot: `<button class="dx-btn ink" data-go="img2pdf"${ready && !busy ? "" : " disabled"}>${busy ? "Rasmlar yuklanmoqda…" : `PDF yaratish · ${ready} sahifa`}</button>`};
}

// ---------- jarayon / tayyor / xato
function vJob(v) {
  const j = v.job;
  if (!j) return {html: bar("", "home") + `<div class="dx-empty" style="padding-top:120px"><span class="spin ink" style="display:inline-block;width:34px;height:34px"></span></div>`};
  if (j.state === "done") return vDone(v);
  if (j.state === "error") return vError({title: "Bajarib bo'lmadi", text: j.error, retry: true});
  const f = files.get((j.fids || [])[0]);
  const pg = j.pages && j.pages[1] ? j.pages : null;
  const pct = pg ? Math.round(pg[0] * 100 / pg[1]) : (j.pct ?? null);
  const steps = (j.steps || []).map((s, i) => { const st = i < j.step ? "done" : i === j.step ? "now" : "wait";
    return `<div class="${st === "now" ? "now" : st === "wait" ? "wait-row" : ""}">${st === "done" ? '<span class="tick">✓</span>' : st === "now" ? '<span class="spin"></span>' : '<span class="wait"></span>'}
      <b>${esc(s)}</b>${st === "now" && pct != null && j.pct != null ? `<span class="pc">${pct}%</span>` : ""}</div>`; }).join("");
  const ring = pg ? `<div class="ring" style="--p:${pct}"><div><b>${pg[0]}/${pg[1]}</b><small>sahifa</small></div></div>`
    : pct != null ? `<div class="ring" style="--p:${pct}"><div><b>${pct}%</b><small>bajarildi</small></div></div>`
    : `<div class="ring indet"><div><b style="font-size:14px">${j.state === "queued" ? "Navbat" : "…"}</b></div></div>`;
  const title = {topdf: "PDF qilinmoqda", img2pdf: "PDF yig'ilmoqda", pdf2jpg: "Rasmga aylanmoqda", pdf2txt: "Matn olinmoqda", split: "Ajratilmoqda",
    ocr: "Yozuv o'qilmoqda", todocx: "Word yig'ilmoqda", translate: "Tarjima qilinmoqda", translit: "Yozuv o'girilmoqda"}[j.tool] || "Ishlanmoqda";
  return {html: bar(title, "home") + `<div class="dx-stage">
      <div class="back">${sheet(f, 1, 170, 228)}</div>
      <div class="front"><div style="position:relative">${sheet(f, 0, 192, 262)}<div class="scan-tint"></div><div class="scan"></div></div></div>
      ${ring}</div><div class="steps">${steps}</div>`,
  foot: `<div class="note">Ilovani yopsangiz ham — tayyor fayl chatga keladi</div>`, nofoot: true};
}
function chainFor(rf) {
  if (!rf) return [];
  const out = [];
  if (rf.kind === "text") out.push(["todocx", "Word qilib olish"]);
  if (rf.kind === "pdf" || rf.kind === "word") {
    if (rf.lang === "uz" && rf.script) out.push(["translit", rf.script === "cyrl" ? "Lotinga o'girish" : "Kirillga o'girish", rf.script === "cyrl" ? "latn" : "cyrl"]);
    if (trOk(rf) && cfg.translate) out.push(["translate", "Tarjima"]);
  }
  if (rf.kind === "word") out.push(["topdf", "PDF qilish"]);
  if (rf.kind === "pdf" && out.length < 2) out.push(["pdf2jpg", "PDF → rasm"]);
  return out.slice(0, 2);
}
function vDone(v) {
  const j = v.job, r = j.result || {}, rf = (r.files || [])[0];
  const f = files.get((j.fids || [])[0]) || rf;
  const name = rf ? rf.name : (f && f.name) || "Natija";
  const chips = [];
  const pages = (rf && rf.pages) || r.pages;
  if (pages && rf && rf.kind === "pdf") chips.push(`${pages} sahifa`);
  if (r.text_len != null) chips.push(`${r.text_len.toLocaleString("ru-RU")} belgi`);
  if (r.in_size && r.out_size && rf && rf.kind !== "text") chips.push(`${mb(r.in_size)} → <b class="dx-ok">${mb(r.out_size)}</b>`);
  if (r.secs != null) chips.push(`${r.secs < 1 ? "1" : Math.round(r.secs)} soniya`);
  const stampOn = cfg.stamp && !v.noAnim;
  const label = {pdf: "PDF", word: "WORD", text: "MATN", image: "JPG", zip: "ZIP"}[rf && rf.kind] || "FAYL";
  const art = r.text != null ? "" : `<div class="dx-done${cfg.stamp ? "" : " nostamp"}"><div class="halo"></div>
      <div class="p1">${sheet(f && f.thumbs > 1 ? f : null, 1, 200, 272)}</div>
      <div class="p2">${sheet(rf && rf.thumbs ? rf : f, 0, 214, 292)}</div>
      ${cfg.stamp ? `<div class="stamp${stampOn ? " drop" : ""}"><span class="a">BAUNTYS</span><span class="b">TAYYOR</span><span class="c">✓ ${label}</span></div>
      ${[[330, 228, 6], [348, 262, 4], [190, 352, 5], [338, 372, 7], [206, 236, 3]].map(([x, y, s]) => `<i class="blot${stampOn ? " on" : ""}" style="left:calc(50% + ${x - 195}px);top:${y}px;width:${s}px;height:${s}px${stampOn ? "" : ";opacity:.55"}"></i>`).join("")}` : ""}</div>`;
  const text = r.text != null ? `<div style="padding-top:8px"></div>${cfg.stamp ? "" : ""}<h1 class="dx-donet" style="padding-top:10px">Matn tayyor</h1>
    <div class="dx-card dx-text" id="dxtext">${esc(r.text || "")}${r.text_len > (r.text || "").length ? "\n…" : ""}</div>` : `<h1 class="dx-donet">${esc(name)}<br>tayyor</h1>`;
  const chain = chainFor(rf);
  const notes = (r.notes || []).map((n) => `<div class="dx-info" style="background:#FBEFD3;color:#6E4B05">ℹ️ ${esc(n)}</div>`).join("");
  return {html: bar("", "home") + art + text + `<div class="dx-meta">${chips.map((c) => `<span class="dx-chip">${c}</span>`).join("")}</div>
    <div class="dx-sent"><span class="tick">✓</span> Chatga yuborildi</div>${notes}`,
  foot: (r.text != null ? `<div class="row2" style="margin-bottom:8px"><button class="dx-btn ink" data-copy="1">${ICO.copy} Nusxa olish</button>
      ${chain.length ? `<button class="dx-btn ghost" data-chain="${chain[0][0]}" data-fid="${rf.fid}">${chain[0][1]}</button>` : ""}</div>
      <button class="dx-btn ghost" data-nav="chat">${ICO.send} Chatga o'tish</button>`
    : `<button class="dx-btn ink" data-nav="chat">${ICO.send} Chatga o'tish</button>
      ${chain.length ? `<div class="row2" style="margin-top:8px">${chain.map(([t, l, to]) => `<button class="dx-btn ghost" data-chain="${t}" data-to="${to || ""}" data-fid="${rf.fid}">${l}</button>`).join("")}</div>` : ""}`)};
}
function vError(v) {
  const lock = `<div class="dx-lock"><div class="w"><div style="position:absolute;left:14px;top:0;transform:rotate(-5deg)">${sheet(null, 0, 120, 160)}</div>
    <div class="k">${v.icon || "😔"}</div></div></div>`;
  return {html: bar("", "home") + lock + `<h1 class="dx-c">${esc(v.title || "Xatolik")}</h1><p class="dx-cp">${esc(v.text || "")}</p>
    ${v.tips ? `<div class="dx-sec" style="padding-top:22px"><h3>Nima qilish mumkin</h3></div><div class="dx-list">${v.tips.map(([ic, b, s]) =>
      `<div class="dx-card" style="border-radius:16px;padding:12px 14px;display:flex;gap:12px;align-items:center"><span style="font-size:20px">${ic}</span><div><b style="font-size:14px;display:block">${b}</b><small style="color:var(--mute);font-size:12.5px">${s}</small></div></div>`).join("")}</div>` : ""}`,
  foot: `<button class="dx-btn ink" data-nav="home">Boshqa fayl tanlash</button>`};
}
function vPassword(v) {
  const f = files.get(v.fid);
  return {html: bar(f ? f.name : "", "back") + `<div class="dx-lock"><div class="w"><div style="position:absolute;left:14px;top:0;transform:rotate(-5deg)">${sheet(null, 0, 120, 160)}</div>
    <div class="k"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#F3EEE3" stroke-width="2.2" stroke-linecap="round"><rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg></div></div></div>
    <h1 class="dx-c">Fayl parol bilan<br>himoyalangan</h1>
    <p class="dx-cp">Parolni kiriting — faqat shu fayl uchun ishlatiladi va saqlanmaydi</p>
    <div class="dx-pw${v.bad ? " bad" : ""}"><input id="dxpw" type="password" autocomplete="off" enterkeyhint="go" placeholder="Parol"><button data-pwshow="1">Ko'rsatish</button></div>
    <div class="dx-err">${v.bad ? "Parol noto'g'ri — qayta urinib ko'ring" : ""}</div>`,
  foot: `<button class="dx-btn ink" data-go="unlock">Ochish</button>`};
}
function vQueue(v) {
  const list = v.jobs;
  const done = list.filter((x) => x.job && x.job.state === "done").length, err = list.filter((x) => x.err || (x.job && x.job.state === "error")).length;
  const pct = Math.round((done + err) * 100 / Math.max(1, list.length));
  const rows = list.map((x) => { const j = x.job, st = x.err ? "error" : !j ? "queued" : j.state === "running" ? "now" : j.state;
    const k = kindOf(x.name);
    const sub = x.err ? x.err : !j ? "Navbatda" : j.state === "done" ? `PDF · ${mb((j.result || {}).out_size)}` : j.state === "error" ? j.error : j.state === "queued" ? "Navbatda" : (j.steps || [])[j.step] || "Ishlanmoqda";
    return `<div class="dx-card dx-q ${st}">${fic(k, true)}<div class="t"><b>${esc(x.name)}</b><small>${esc(sub)}</small>
      ${st === "now" ? `<div class="prog indet" style="margin-top:7px;height:5px"><i></i></div>` : ""}</div>
      ${st === "done" ? '<span class="tick">✓</span>' : st === "now" ? '<span class="spin ink"></span>' : st === "error" ? '<span style="color:var(--red);font-weight:800">!</span>' : '<span class="wait"></span>'}</div>`; }).join("");
  const all = done + err === list.length;
  return {html: bar(`${list.length} ta fayl`, "home") + `<h1 class="dx-h">${all ? "Hammasi tayyor" : "Hammasi PDF bo'ladi"}</h1>
    <div style="padding:14px 18px 0"><div style="display:flex;justify-content:space-between;font-weight:800;font-size:13px;margin-bottom:8px"><span>${done} tasi tayyor${err ? ` · ${err} ta xato` : ""}</span><span class="dx-ok">${pct}%</span></div>
    <div class="prog"><i style="width:${pct}%;background:linear-gradient(90deg,var(--eme),var(--ink))"></i></div></div>
    <div class="dx-list" style="padding-top:14px">${rows}</div>`,
  foot: `<button class="dx-btn ${all ? "ink" : "ghost"}" data-nav="chat">${ICO.send} ${all ? "Chatga o'tish" : "Tayyorlari chatga kelyapti"}</button>`};
}

const VIEWS = {home: vHome, uploading: vUploading, file: vFile, translate: vTranslate, split: vSplit, images: vImages,
  job: vJob, error: vError, password: vPassword, queue: vQueue};
const top = () => stack[stack.length - 1];
function render(keep = false) {
  const v = top(); if (!v) return;
  const sc = $("dxscroll"), st = keep ? sc.scrollTop : 0;
  const out = VIEWS[v.v](v);
  $("dxview").innerHTML = out.html;
  $("dxfoot").innerHTML = out.foot || "";
  sc.classList.toggle("nofoot", !out.foot);
  sc.scrollTop = st;
  if (v.v === "translate") loadPreview(v);
  if (v.v === "split") bindSplit(v);
  if (v.v === "password") setTimeout(() => $("dxpw") && $("dxpw").focus(), 80);
  updateBack();
}
function push(v, replace = false) { if (replace) stack.pop(); stack.push(v); render(); haptic(); }
function goHome() { stopPoll(); stack.length = 1; render(); }
function pop() { if (stack.length <= 1) return false; const v = stack.pop(); if (v.v === "job" || v.v === "queue") stopPoll();
  while (stack.length > 1 && ["uploading", "password"].includes(top().v)) stack.pop();
  render(true); return true; }

// =================================================================== fayl tanlash va yuklash
let pickIntent = "";
function pick(intent) {
  pickIntent = intent || "";
  const inp = $("dxfile");
  const t = TOOLS[intent.replace("+", "")];
  inp.accept = t && t.accept ? t.accept : ".pdf,.doc,.docx,.odt,.rtf,.txt,.ppt,.pptx,.odp,.xls,.xlsx,.ods,.csv,image/*";
  inp.multiple = !intent || !!(t && t.multi);
  inp.value = "";
  inp.click();
}
async function onPicked(list) {
  const intent = pickIntent; pickIntent = "";
  let arr = [...list];
  if (!arr.length) return;
  const maxB = cfg.max_mb * 1048576;
  const big = arr.filter((f) => f.size > maxB);
  if (big.length && big.length === arr.length) {
    haptic("err");
    push({v: "error", icon: "📦", title: "Fayl juda katta", text: `${big[0].name} — ${mb(big[0].size)}. Ilova orqali ${cfg.max_mb} MB gacha fayl yuklash mumkin.`,
      tips: [["✂️", "Qismlarga bo'ling", "Katta PDF'ni kompyuterda bir necha qismga bo'lib yuklang"], ["🗜", "Siqib yuboring", "Rasmlarni kichikroq o'lchamda saqlang"]]});
    return;
  }
  if (big.length) toast(`📦 ${big.length} ta fayl ${cfg.max_mb} MB dan katta — tashlab ketildi`);
  arr = arr.filter((f) => f.size <= maxB);
  const tool = intent.replace("+", "");
  const bad = arr.filter((f) => !kindOf(f.name) && !(f.type || "").startsWith("image/") || (tool && TOOL_KINDS[tool] && !TOOL_KINDS[tool].includes(kindOf(f.name) || ((f.type || "").startsWith("image/") ? "image" : ""))));
  if (bad.length === arr.length) { haptic("err"); toast("⚠️ Bu turdagi fayl bilan ishlay olmayman"); return; }
  if (bad.length) toast(`⚠️ ${bad.length} ta mos bo'lmagan fayl tashlab ketildi`);
  arr = arr.filter((f) => !bad.includes(f));
  const isImg = (f) => kindOf(f.name) === "image" || (f.type || "").startsWith("image/");
  // Rasmlar → PDF yig'uvchi
  if (intent === "img2pdf+" && top().v === "images") return addImages(top(), arr);
  if (tool === "img2pdf" || (!tool && arr.length > 1 && arr.every(isImg))) {
    const v = {v: "images", items: [], size: "a4"}; push(v); return addImages(v, arr);
  }
  // Bir nechta hujjat → navbat (hammasi PDF)
  if (arr.length > 1) {
    const docs = arr.filter((f) => TOOL_KINDS.topdf.includes(kindOf(f.name)));
    if (!docs.length) { toast("ℹ️ Bir nechta fayl birga faqat Word/PPT/Excel → PDF uchun. Bittasini tanlang."); return; }
    if (docs.length < arr.length) toast("ℹ️ Faqat Word/PPT/Excel fayllar PDF qilinadi");
    return startQueue(docs);
  }
  const file = arr[0];
  const up = {v: "uploading", items: [{name: file.name, size: file.size, p: 0}]};
  push(up);
  const r = await upload(file, (p) => { up.items[0].p = p; if (top() === up) render(true); });
  if (top() !== up) return;
  if (!r.ok) { haptic("err"); up.items[0].err = errText(r); render(true); setTimeout(() => { if (top() === up) pop(); }, 1800); return; }
  const f = r.file; files.set(f.fid, f);
  stack.pop();
  afterUpload(f, tool, intent);
}
function afterUpload(f, tool, intent) {
  if (f.needs_pass) { push({v: "password", fid: f.fid, then: tool}); return; }
  if (!tool) { push({v: "file", fid: f.fid}); return; }
  openTool(tool, f);
}
function openTool(tool, f, extra = {}) {
  if (!TOOL_KINDS[tool].includes(f.kind) || ((tool === "translate" || tool === "translit") && !trOk(f))) { toast(ERR.type); push({v: "file", fid: f.fid}); return; }
  if (tool === "translate") { push({v: "translate", fid: f.fid, target: f.lang === "uz" ? "ru" : "uz", script: "latn"}); return; }
  if (tool === "split") {
    if (!f.pages) { toast("⚠️ PDF sahifalarini o'qib bo'lmadi"); return; }
    push({v: "split", fid: f.fid, sel: new Set(), mode: "one", spec: ""}); return;
  }
  if (tool === "img2pdf") { push({v: "images", items: [{fid: f.fid, name: f.name, size: f.size}], size: "a4"}); return; }
  run(tool, [f.fid], extra);
}
async function addImages(v, arr) {
  const room = cfg.max_images - v.items.length;
  if (arr.length > room) { toast(`ℹ️ Ko'pi bilan ${cfg.max_images} ta rasm`); arr = arr.slice(0, Math.max(0, room)); }
  const its = arr.map((f) => ({name: f.name, size: f.size, p: 0, file: f}));
  v.items.push(...its); render(true);
  // 3 tadan parallel yuklash
  let i = 0;
  const worker = async () => { while (i < its.length) { const it = its[i++];
    const r = await upload(it.file, (p) => { it.p = p; if (top() === v) paintUp(v); });
    delete it.file;
    if (r.ok && r.file.kind === "image") { files.set(r.file.fid, r.file); it.fid = r.file.fid; }
    else { it.err = errText(r); const k = v.items.indexOf(it); if (k >= 0) v.items.splice(k, 1); toast(`⚠️ ${it.name}: ${it.err}`); }
    if (top() === v) render(true); } };
  await Promise.all([worker(), worker(), worker()]);
}
function paintUp(v) {
  v.items.forEach((it, i) => { const el = document.querySelector(`.dx-im[data-im="${i}"] .up i`); if (el) el.style.width = `${Math.round((it.p || 0) * 100)}%`; });
}

// =================================================================== ishni boshlash va kuzatish
async function run(tool, fids, options = {}, btn = null) {
  if (!inTg) { toast("📱 Telegram ichida oching"); return; }
  if (btn) btn.classList.add("busy");
  const r = await api("api/docs/run", {tool, fids, options});
  if (btn) btn.classList.remove("busy");
  if (!r.ok) {
    haptic("err");
    if (r.error === "need_start") { toast("🤖 Avval botni ishga tushiring"); if (bot) tg.openTelegramLink(`https://t.me/${bot}?start=docs`); return; }
    if (r.error === "needs_pass") { push({v: "password", fid: r.fid, then: tool}); return; }
    if (r.error === "expired") { toast(ERR.expired, 3000); goHome(); return; }
    toast(errText(r), 3200); return;
  }
  // tanlash ekranlari (tarjima, sahifalar, rasmlar) stekdan olinadi — «orqaga» bosh sahifaga qaytaradi
  while (stack.length > 1 && ["translate", "split", "images", "uploading", "password"].includes(top().v)) stack.pop();
  const v = {v: "job", id: r.job.id, job: r.job};
  push(v); haptic("hit");
  poll();
}
let pollT = null;
function stopPoll() { clearTimeout(pollT); pollT = null; }
async function poll() {
  stopPoll();
  const v = top();
  if (!v || !opened) return;
  if (v.v === "job") {
    if (v.job && (v.job.state === "done" || v.job.state === "error")) return;
    const r = await api(`api/docs/job/${v.id}`);
    if (top() !== v) return;
    if (r.ok) {
      const was = v.job && v.job.state;
      v.job = r.job;
      if (r.job.state === "done" && was !== "done") onDone(v);
      else if (r.job.state === "error" && was !== "error") { haptic("err"); render(true); }
      else render(true);
    } else if (r.error === "expired") { v.job = {state: "error", error: "Ish ma'lumoti topilmadi — qaytadan urinib ko'ring"}; render(true); return; }
  } else if (v.v === "queue") {
    let pending = false;
    await Promise.all(v.jobs.map(async (x) => {
      if (!x.id || (x.job && (x.job.state === "done" || x.job.state === "error"))) return;
      pending = true;
      const r = await api(`api/docs/job/${x.id}`);
      if (r.ok) x.job = r.job;
    }));
    if (top() !== v) return;
    render(true);
    const all = v.jobs.every((x) => x.err || (x.job && (x.job.state === "done" || x.job.state === "error")));
    if (all) { haptic("ok"); return; }
    if (!pending && v.starting) { pollT = setTimeout(poll, 600); return; }
  } else return;
  pollT = setTimeout(poll, 900);
}
function onDone(v) {
  const j = v.job, r = j.result || {}, rf = (r.files || [])[0];
  (r.files || []).forEach((f) => files.set(f.fid, f));
  const src = files.get((j.fids || [])[0]);
  const desc = {topdf: "PDF qilindi", img2pdf: `${(j.fids || []).length} ta rasm → PDF`, pdf2jpg: "PDF → rasm", pdf2txt: "Matn olindi", split: "Sahifalar ajratildi",
    ocr: "Rasmdan matn", todocx: "Word qilindi", translate: `Tarjima${j.options && j.options.target ? ` → ${LANG[j.options.target]}` : ""}`, translit: "Kirill ↔ Lotin"}[j.tool] || "";
  recent = [{name: (j.tool === "img2pdf" && rf ? rf.name : (src && src.name)) || (rf && rf.name) || "Hujjat", k: (rf && rf.kind) || (src && src.kind) || "pdf", desc, at: Math.floor(Date.now() / 1000)}, ...recent].slice(0, 12);
  lsSet("zk_drec", recent);
  render(true);
  if (cfg.stamp && r.text == null) setTimeout(() => haptic("hit"), 210);
  setTimeout(() => haptic("ok"), cfg.stamp ? 420 : 0);
  v.noAnim = true;   // qayta chizilganda muhr yana tushmasin
}
async function startQueue(arr) {
  const v = {v: "queue", jobs: arr.map((f) => ({name: f.name, size: f.size, file: f})), starting: true};
  push(v);
  poll();
  for (const x of v.jobs) {
    const r = await upload(x.file, () => {});
    delete x.file;
    if (!r.ok) { x.err = errText(r); continue; }
    files.set(r.file.fid, r.file);
    if (r.file.needs_pass) { x.err = "Parol bilan himoyalangan"; continue; }
    const q = await api("api/docs/run", {tool: "topdf", fids: [r.file.fid], options: {}});
    if (!q.ok) { x.err = q.error === "need_start" ? "Avval botni ishga tushiring" : errText(q); continue; }
    x.id = q.job.id; x.job = q.job;
    if (top() === v) render(true);
  }
  v.starting = false;
  if (top() === v && !pollT) poll();
}

// =================================================================== sahifalar va surish
function bindSplit(v) {
  const inp = $("dxrange");
  if (!inp) return;
  inp.addEventListener("input", () => {
    const f = files.get(v.fid); v.spec = inp.value; v.sel = parseSpec(inp.value, f.pages || 0);
    document.querySelectorAll(".dx-pg").forEach((el) => { const on = v.sel.has(+el.dataset.pg); el.classList.toggle("on", on); el.querySelector(".ck").textContent = on ? "✓" : ""; });
    $("dxfoot").innerHTML = VIEWS.split(v).foot;
  });
}
// Surish: tinglovchilar bir marta (document'da). Qayta chizish o'rniga element DOM ichida ko'chiriladi —
// shunda barmoq ostidagi element yo'qolmaydi va sudrash uzilmaydi.
let drag = null;   // {el, i, timer, sx, sy, on}
function dragTargetIndex(x, y) {
  const el = document.elementFromPoint(x, y), t = el && el.closest(".dx-im");
  return t ? [...t.parentNode.querySelectorAll(".dx-im")].indexOf(t) : -1;
}
function dragMove(x, y) {
  const v = top(); if (!drag || !drag.on || !v || v.v !== "images") return;
  const to = dragTargetIndex(x, y);
  if (to < 0 || to === drag.i || to >= v.items.length) return;
  const [it] = v.items.splice(drag.i, 1); v.items.splice(to, 0, it);
  const grid = drag.el.parentNode, tiles = [...grid.querySelectorAll(".dx-im")];
  const ref = to > drag.i ? tiles[to].nextSibling : tiles[to];
  grid.insertBefore(drag.el, ref);
  drag.i = to; v.drag = to;
  grid.querySelectorAll(".dx-im").forEach((el, k) => { el.dataset.im = k; el.querySelector(".n").textContent = k + 1; el.querySelector(".x").dataset.rm = k; });
  haptic();
}
function dragEnd() {
  if (!drag) return;
  clearTimeout(drag.timer);
  if (drag.on) { drag.el.classList.remove("drag"); const v = top(); if (v) v.drag = null; }
  drag = null;
}
document.addEventListener("touchstart", (e) => {
  const t = e.target.closest && e.target.closest("#docs .dx-im");
  if (!t || e.target.closest(".x")) return;
  const p = e.touches[0];
  drag = {el: t, i: [...t.parentNode.querySelectorAll(".dx-im")].indexOf(t), sx: p.clientX, sy: p.clientY, on: false};
  drag.timer = setTimeout(() => { if (drag) { drag.on = true; t.classList.add("drag"); haptic(); } }, 260);
}, {passive: true});
document.addEventListener("touchmove", (e) => {
  if (!drag) return;
  const p = e.touches[0];
  if (!drag.on) { if (Math.abs(p.clientX - drag.sx) + Math.abs(p.clientY - drag.sy) > 10) dragEnd(); return; }
  e.preventDefault();
  dragMove(p.clientX, p.clientY);
}, {passive: false});
document.addEventListener("touchend", dragEnd);
document.addEventListener("touchcancel", dragEnd);
document.addEventListener("mousedown", (e) => {
  const t = e.target.closest && e.target.closest("#docs .dx-im");
  if (!t || e.target.closest(".x")) return;
  drag = {el: t, i: [...t.parentNode.querySelectorAll(".dx-im")].indexOf(t), on: true};
  t.classList.add("drag");
});
document.addEventListener("mousemove", (e) => { if (drag && drag.on && !e.touches) dragMove(e.clientX, e.clientY); });
document.addEventListener("mouseup", dragEnd);

// =================================================================== hodisalar
document.addEventListener("click", async (e) => {
  const t = e.target;
  if (!t.closest("#docs")) return;
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "docs" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  const nav = t.closest("[data-nav]");
  if (nav) { const n = nav.dataset.nav;
    if (n === "back") pop(); else if (n === "home" || n === "x") goHome();
    else if (n === "chat") { haptic(); try { tg.close(); } catch (x) {} }
    return; }
  const pk = t.closest("[data-pick]");
  if (pk) { haptic(); pick(pk.dataset.pick); return; }
  const tl = t.closest("[data-tool]");
  if (tl) { haptic(); pick(tl.dataset.tool); return; }
  if (t.closest("[data-clr]")) { recent = []; lsSet("zk_drec", []); render(true); return; }
  const v = top();
  const rn = t.closest("[data-run]");
  if (rn && v.v === "file") { const f = files.get(v.fid); const tool = rn.dataset.run;
    if (tool === "translit") { run("translit", [f.fid], rn.dataset.to ? {to: rn.dataset.to} : {}, rn); return; }
    openTool(tool, f); return; }
  const ch = t.closest("[data-chain]");
  if (ch) { const f = files.get(ch.dataset.fid); if (!f) { toast(ERR.expired); return; }
    const tool = ch.dataset.chain;
    if (tool === "translit") run("translit", [f.fid], ch.dataset.to ? {to: ch.dataset.to} : {}, ch);
    else if (tool === "translate" || tool === "split") { stack.length = 1; openTool(tool, f); }
    else run(tool, [f.fid], {}, ch);
    return; }
  if (t.closest("[data-copy]")) { const r = (v.job && v.job.result) || {}; copyText(r.text || ""); return; }
  // tarjima
  const tg2 = t.closest("[data-tgt]");
  if (tg2 && v.v === "translate") { v.target = tg2.dataset.tgt; v.script = tg2.dataset.sc || "latn"; haptic(); render(true); return; }
  const sr = t.closest("[data-src]");
  if (sr && v.v === "translate") { v.source = sr.dataset.src; haptic(); render(true); return; }
  // sahifalar
  const pg = t.closest("[data-pg]");
  if (pg && v.v === "split") { const p = +pg.dataset.pg; v.sel.has(p) ? v.sel.delete(p) : v.sel.add(p); v.spec = specOf(v.sel); haptic(); render(true); return; }
  const sl = t.closest("[data-sel]");
  if (sl && v.v === "split") { const n = files.get(v.fid).pages || 0, k = sl.dataset.sel;
    v.sel = new Set(k === "none" ? [] : Array.from({length: n}, (_, i) => i + 1).filter((p) => k === "all" || (k === "odd" ? p % 2 : p % 2 === 0)));
    v.spec = specOf(v.sel); haptic(); render(true); return; }
  const m2 = t.closest("[data-mode2]");
  if (m2 && v.v === "split") { v.mode = m2.dataset.mode2; haptic(); render(true); return; }
  // rasmlar
  const rm = t.closest("[data-rm]");
  if (rm && v.v === "images") { v.items.splice(+rm.dataset.rm, 1); haptic(); if (!v.items.length) pop(); else render(true); return; }
  const sz = t.closest("[data-size]");
  if (sz && v.v === "images") { v.size = sz.dataset.size; haptic(); render(true); return; }
  // parol
  if (t.closest("[data-pwshow]")) { const i = $("dxpw"); i.type = i.type === "password" ? "text" : "password"; return; }
  const go = t.closest("[data-go]");
  if (go) { const g = go.dataset.go;
    if (g === "translate") run("translate", [v.fid], {target: v.target, script: v.script, source: v.source}, go);
    else if (g === "split") run("split", [v.fid], {pages: [...v.sel].sort((a, b) => a - b), mode: v.mode}, go);
    else if (g === "img2pdf") run("img2pdf", v.items.filter((x) => x.fid).map((x) => x.fid), {size: v.size}, go);
    else if (g === "unlock") unlock(v, go);
  }
});
document.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id === "dxpw") { const v = top(); if (v && v.v === "password") unlock(v, null); } });
async function unlock(v, btn) {
  const pw = ($("dxpw") || {}).value || "";
  if (!pw) { haptic("err"); return; }
  if (btn) btn.classList.add("busy");
  const r = await api("api/docs/unlock", {fid: v.fid, password: pw});
  if (btn) btn.classList.remove("busy");
  if (r.ok) { haptic("ok"); files.set(r.file.fid, r.file); stack.pop(); afterUpload(r.file, v.then || "", ""); return; }
  haptic("err");
  if (r.error === "bad_password") { v.bad = true; render(true); return; }
  toast(errText(r));
}
async function copyText(s) {
  try { await navigator.clipboard.writeText(s); haptic("ok"); toast("📋 Nusxa olindi", 1400); return; } catch (e) {}
  const el = $("dxtext");
  if (el) { const rg = document.createRange(); rg.selectNodeContents(el); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(rg);
    try { document.execCommand("copy"); toast("📋 Nusxa olindi", 1400); } catch (x) { toast("Matnni bosib turib nusxa oling"); } }
}

// =================================================================== Telegram «Orqaga»
function updateBack() {
  if (!inTg) return;
  try { (opened && stack.length > 1) ? tg.BackButton.show() : (window.ZK_canHideBack ? window.ZK_canHideBack() && tg.BackButton.hide() : tg.BackButton.hide()); } catch (e) {}
}
if (inTg) tg.BackButton.onClick(() => { if (!opened) return; const v = top(); if (v && (v.v === "job" || v.v === "queue")) goHome(); else pop(); });
document.addEventListener("visibilitychange", () => { if (!document.hidden && opened && !pollT) poll(); });

async function loadCfg() {
  const r = await api("api/docs/config");
  if (r.ok) cfg = Object.assign(cfg, r);
}

window.ZDocs = {
  open() {
    if (!mounted) {
      mounted = true; stack.push({v: "home"});
      $("dxfile").addEventListener("change", (e) => onPicked(e.target.files || []));
      loadCfg().then(() => { if (opened && top().v === "home") render(true); });
    }
    opened = true;
    $("docs").hidden = false; document.body.classList.add("d-on");
    try { tg.setHeaderColor("#F3EEE3"); tg.setBackgroundColor("#F3EEE3"); if (tg.setBottomBarColor) tg.setBottomBarColor("#F3EEE3"); } catch (e) {}
    render(true);
    if (!pollT) poll();
  },
  close() {
    opened = false; stopPoll();
    $("docs").hidden = true; document.body.classList.remove("d-on");
    try { tg.setHeaderColor("bg_color"); tg.setBackgroundColor("bg_color"); if (tg.setBottomBarColor) tg.setBottomBarColor("bottom_bar_bg_color"); } catch (e) {}
    updateBack();
  },
  setBot(b) { bot = b || ""; },
  busy() { return opened && stack.length > 1; },
};
})();
