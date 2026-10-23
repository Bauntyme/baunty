/* 🎬 Kinolar — AsilMedia hamkor katalogi (Mini App). app.js «kino» rejimida, catalog.asil bo'lsa ishlatadi.
   Katalog: /api/asil/home|list|search|item. Fayl: /api/asil/send → bot foydalanuvchiga yuboradi.
   Tuzilishi: qidiruv ostida doim ko'rinadigan janrlar tasmasi (#chips), Hammasi/Filmlar/Seriallar,
   «Hafta kinosi» karuseli, janr/davlat sahifasi (saralash + yil, cheksiz yuklash — faqat oxiriga qo'shiladi),
   barcha janrlar plitkalari va davlatlar. Har bir ko'rinishning scroll joyi eslab qolinadi. */
(function () {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const T = window.ZK_T || ((u) => u);
const NB = (n) => (+n || 0).toLocaleString("ru-RU");
const norm = (s) => String(s || "").toLowerCase().replace(/[^a-zа-яё]/g, "");
const REDUCE = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
const YEAR = new Date().getFullYear();

let home = null, homeP = null, main = null, q = "", qT = null;
let homeTyp = "all";
let view = {k: "home", typ: "all", srt: "def"};
const cache = new Map();          // ro'yxatlar (janr/davlat/turi bo'yicha) — orqaga qaytilganda qayta yuklanmaydi
const scrollMem = {};             // ko'rinish → scrollY
let det = null;

async function api(path, body) {
  try {
    const r = await fetch(path, {method: body ? "POST" : "GET", cache: body ? "no-store" : "default",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body ? {"Content-Type": "application/json"} : {}),
      body: body ? JSON.stringify(body) : undefined});
    if (r.status === 401) return {ok: false, error: "auth"};
    if (r.status >= 500) return {ok: false, error: "down"};
    return await r.json();
  } catch (e) { return {ok: false, error: "network"}; }
}
function toast(t) {
  const el = document.createElement("div"); el.className = "as-toast"; el.textContent = t;
  document.body.appendChild(el); setTimeout(() => el.remove(), 3200);
}
const ERR = (e) => ({network: T("Internet bilan muammo", "Проблема с интернетом", "Connection problem"),
  down: T("Katalog hozir javob bermayapti — birozdan keyin", "Каталог не отвечает — попробуйте позже", "The catalogue isn't responding — try later"),
  busy: T("Hozir navbat ko'p — 1 daqiqadan keyin", "Сейчас очередь — через минуту", "Busy right now — try in a minute"),
  not_ready: T("Bu fayl hali tayyor emas — keyinroq", "Файл ещё не готов — позже", "This file isn't ready yet"),
  not_found: T("Kino topilmadi", "Фильм не найден", "Movie not found"),
  paused: T("🎬 Kino yuborish vaqtincha ishlamayapti — 10–15 daqiqadan keyin urinib ko'ring", "🎬 Отправка временно не работает — попробуйте через 10–15 минут", "🎬 Sending is temporarily unavailable — try again in 10–15 min"),
  auth: T("Ilovani bot ichida oching", "Откройте приложение в боте", "Open the app inside the bot"),
  banned: T("Siz botdan bloklangansiz", "Вы заблокированы", "You are blocked")}[e] || T("Xatolik — qayta urinib ko'ring", "Ошибка — попробуйте снова", "Error — try again"));

// ------------------------------------------------------------------ janr / davlat ko'rinishi (emoji + rang)
const GEN = [
  [/jangari|boevik|боевик|action/, "💥", "#FF4D4D", "#6B0F0F"],
  [/melodram|мелодрам/, "💞", "#FF6BB5", "#7A1A4A"],
  [/komed|комед|comedy/, "😂", "#FFC93D", "#7A560A"],
  [/drama|драм/, "🎭", "#B37BFF", "#3D1A7A"],
  [/qorqinch|ujas|ужас|horror/, "👻", "#7D8BA3", "#141A24"],
  [/triller|триллер|thriller/, "🔪", "#E0566B", "#3A0B16"],
  [/detektiv|детектив/, "🕵️", "#3DB5FF", "#0E3A6B"],
  [/kriminal|крими/, "🚔", "#5A7BFF", "#101C55"],
  [/multserial|multfilm|mult|мульт|animat|cartoon/, "🧸", "#FFB03D", "#8A4A0E"],
  [/fentez|fantaz|фэнтез|fantasy/, "🧙", "#9D5BFF", "#2A0F55"],
  [/fantast|фантаст|scifi/, "🚀", "#7B6BFF", "#1A1260"],
  [/anime|аниме/, "🌸", "#FF8FC8", "#6B1A4A"],
  [/sarguzasht|приключ|advent/, "🧭", "#2ECC9A", "#0B4A36"],
  [/tarix|истор|histor/, "🏛️", "#C9A26B", "#4A3214"],
  [/harbiy|urush|воен/, "🎖️", "#8FA35A", "#2A3312"],
  [/oilaviy|семей|family/, "👨‍👩‍👧", "#5BD1FF", "#0F4A6B"],
  [/bolalar|детск|kids/, "🧒", "#FFD84D", "#8A6A0E"],
  [/hujjatli|документ|docum/, "📹", "#8AA0B8", "#1E2A38"],
  [/sport|спорт/, "⚽", "#3DDC84", "#0B4A26"],
  [/musiq|myuzikl|музык|мюзикл/, "🎵", "#FF7AE0", "#5A1A55"],
  [/biograf|биограф/, "📜", "#D9B26B", "#4A3A14"],
  [/vestern|вестерн|western/, "🤠", "#D98A4A", "#4A250E"],
  [/romant|роман/, "💘", "#FF5C8A", "#5A0F2A"],
  [/turk|турец/, "🇹🇷", "#E5484D", "#5A0F12"],
  [/hind|индий/, "🇮🇳", "#FF9F43", "#6B3A0E"],
  [/korey|корей/, "🇰🇷", "#5B8CFF", "#14286B"],
  [/serial|сериал/, "📺", "#3DD6FF", "#0E4A8A"],
];
const PAL = [["#FF6B3D", "#8A1E0E"], ["#3DD6FF", "#0E4A8A"], ["#B37BFF", "#3D1A7A"], ["#2ECC9A", "#0B4A36"], ["#FFC93D", "#7A560A"], ["#FF6BB5", "#7A1A4A"], ["#5B8CFF", "#14286B"]];
function hashPal(n) { let h = 0; for (const ch of n) h = (h * 31 + ch.charCodeAt(0)) | 0; return PAL[Math.abs(h) % PAL.length]; }
function gStyle(name) {
  const n = norm(name);
  for (const g of GEN) if (g[0].test(n)) return {e: g[1], a: g[2], b: g[3]};
  const p = hashPal(n); return {e: "🎬", a: p[0], b: p[1]};
}
const FL = [[/turkman|туркмен/, "🇹🇲"], [/turk|турц/, "🇹🇷"], [/korea|korey|корея|корей/, "🇰🇷"], [/aqsh|amerika|usa|сша|америк/, "🇺🇸"],
  [/hindiston|india|индия|индий/, "🇮🇳"], [/rossiya|росси/, "🇷🇺"], [/ozbek|uzbek|узбек/, "🇺🇿"], [/yapon|япон|japan/, "🇯🇵"], [/xitoy|китай|china/, "🇨🇳"],
  [/fransiya|франц|france/, "🇫🇷"], [/britaniya|angliya|англи|британ/, "🇬🇧"], [/ispaniya|испан/, "🇪🇸"], [/italiya|итал/, "🇮🇹"], [/germaniya|герман/, "🇩🇪"],
  [/kanada|канад/, "🇨🇦"], [/avstraliya|австрал/, "🇦🇺"], [/qozog|kazax|казах/, "🇰🇿"], [/eron|иран/, "🇮🇷"], [/misr|египет/, "🇪🇬"],
  [/braziliya|бразил/, "🇧🇷"], [/meksika|мексик/, "🇲🇽"], [/tailand|таиланд/, "🇹🇭"], [/ukraina|украин/, "🇺🇦"], [/pokiston|пакист/, "🇵🇰"],
  [/filippin|филип/, "🇵🇭"], [/indoneziya|индонез/, "🇮🇩"], [/shvetsiya|швец/, "🇸🇪"], [/norvegiya|норвег/, "🇳🇴"], [/daniya|дания/, "🇩🇰"],
  [/polsha|польш/, "🇵🇱"], [/gonkong|гонконг/, "🇭🇰"], [/tayvan|тайван/, "🇹🇼"], [/belgiya|бельг/, "🇧🇪"], [/niderland|gollandiya|нидерл/, "🇳🇱"],
  [/irlandiya|ирланд/, "🇮🇪"], [/zelandiya|зеланд/, "🇳🇿"], [/argentina|аргент/, "🇦🇷"], [/qirgiz|кыргыз|киргиз/, "🇰🇬"], [/tojik|тадж/, "🇹🇯"],
  [/ozarbayjon|азерб/, "🇦🇿"], [/arab|араб/, "🇸🇦"]];
function flag(name) { const n = norm(name); for (const f of FL) if (f[0].test(n)) return f[1]; return "🌍"; }

// ------------------------------------------------------------------ kartochkalar
const posterHTML = (x) => `<div class="pst">${x.p ? `<img src="${esc(x.p)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : `<div class="ph">${esc(x.t)}</div>`}
  ${x.imdb ? `<span class="badge as-imdb">★ ${esc(x.imdb)}</span>` : ""}${x.type === "serial" ? `<span class="parts">${T("Serial", "Сериал", "Series")}</span>` : ""}${x.ok === false ? `<span class="seen as-soon">⏳</span>` : ""}</div>`;
const cardHTML = (x) => `<button class="card" data-aid="${x.id}">${posterHTML(x)}<div class="ttl">${esc(x.t)}</div>
  <div class="as-sub">${[x.y, (x.g || [])[0]].filter(Boolean).map(esc).join(" · ")}</div></button>`;
const allBtn = (go, typ) => `<button class="as-all" data-go="${go}"${typ ? ` data-gtyp="${typ}"` : ""}>${T("Hammasi", "Все", "All")} ›</button>`;
const rowHTML = (title, arr, go, typ) => arr && arr.length ? `<div class="sec-h"><h2>${title}</h2>${go ? allBtn(go, typ) : ""}</div>
  <div class="row">${arr.map(cardHTML).join("")}</div>` : "";
const skelCards = (n) => Array.from({length: n || 12}, () => `<div class="card sk"><div class="pst"></div><div class="ttl"></div></div>`).join("");
const skel = (n) => `<div class="grid">${skelCards(n)}</div>`;
const empty = (big, b, t) => `<div class="empty"><div class="big">${big}</div><b>${b}</b>${t || ""}</div>`;
const dots = () => `<div class="as-dots"><i></i><i></i><i></i></div>`;
const retryBtn = () => `<br><br><button class="cta" style="max-width:220px" data-as="retry">🔄 ${T("Qayta urinish", "Повторить", "Retry")}</button>`;
const ctHTML = (c) => `<button class="as-ct" data-c="${esc(c.s)}" data-cn="${esc(c.n)}"><i>${flag(c.n)}</i><b>${esc(c.n)}</b>${c.c ? `<small>${NB(c.c)}</small>` : ""}</button>`;
const collHTML = (c) => `<button class="as-cl" data-coll="${esc(c.s)}" data-cn="${esc(c.t)}"><div class="as-cov">${[0, 1, 2, 3].map((i) => c.cov && c.cov[i]
  ? `<img src="${esc(c.cov[i])}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : "<span></span>").join("")}</div>
  <b>${esc(c.t)}</b><small>${NB(c.c)} ${T("ta kino", "фильмов", "titles")}</small></button>`;
const byCount = (a) => (a || []).slice().sort((x, y) => (+y.c || 0) - (+x.c || 0));

// ------------------------------------------------------------------ janrlar tasmasi (qidiruv ostida, #chips)
function selKey() { return view.k === "genre" ? "g:" + view.s : view.k === "country" ? "" : view.k === "coll" ? "colls" : view.k; }
const gItem = (k, e, n, a, b, cur) => `<button class="as-g${k === cur ? " on" : ""}" data-g="${esc(k)}" aria-pressed="${k === cur}"><i style="background:linear-gradient(140deg,${a},${b})">${e}</i><b>${esc(n)}</b></button>`;
function chips() {
  const cur = selKey();
  let h = gItem("home", "🏠", T("Asosiy", "Главная", "Home"), "#5A6478", "#1A202C", cur)
    + gItem("pop", "🔥", T("Ommabop", "Популярное", "Popular"), "#FF6B3D", "#8A1E0E", cur)
    + gItem("new", "🆕", T("Yangi", "Новые", "New"), "#3DD6FF", "#0E4A8A", cur)
    + gItem("colls", "📚", T("To'plamlar", "Подборки", "Collections"), "#F2B84B", "#7A4A0E", cur);
  if (home) {
    h += byCount(home.genres).slice(0, 12).map((g) => { const st = gStyle(g.n); return gItem("g:" + g.s, st.e, g.n, st.a, st.b, cur); }).join("");
  } else {
    h += Array.from({length: 5}, () => `<span class="as-g sk"><i></i><b>&nbsp;</b></span>`).join("");
  }
  return h + gItem("all", "🗂", T("Barchasi", "Все жанры", "All genres"), "#4A5568", "#171923", cur);
}
function kinoMode() { return !document.body.dataset.zkm || document.body.dataset.zkm === "kino"; }
function paintStrip() {
  const c = $("chips");
  if (!c || !kinoMode() || !window.ZAsil) return;
  const left = c.scrollLeft;
  c.innerHTML = chips();
  c.scrollLeft = left;
}
function centerStrip() {
  const c = $("chips"); if (!c) return;
  const on = c.querySelector(".as-g.on"); if (!on) return;
  const want = on.offsetLeft - (c.clientWidth - on.offsetWidth) / 2;
  c.scrollTo({left: Math.max(0, want), behavior: REDUCE ? "auto" : "smooth"});
}
function countText() { return T("AsilMedia katalogi · posterini bosing", "Каталог AsilMedia · нажмите на постер", "AsilMedia catalogue · tap a poster"); }

// ------------------------------------------------------------------ navigatsiya
const vkey = (v) => [v.k, v.s || "", v.typ, v.srt].join("|");
function go(v, keepScroll) {
  scrollMem[vkey(view)] = window.scrollY;
  view = Object.assign({typ: homeTyp, srt: "def"}, v);
  haptic();
  paintStrip(); paint();
  if (!keepScroll) window.scrollTo(0, scrollMem[vkey(view)] || 0);
  centerStrip();
}
const typesHTML = (cur) => `<div class="as-types">${[["all", T("Hammasi", "Все", "All")], ["film", "🎬 " + T("Filmlar", "Фильмы", "Movies")], ["serial", "📺 " + T("Seriallar", "Сериалы", "Series")]]
  .map(([k, l]) => `<button data-typ="${k}" class="${k === cur ? "on" : ""}">${l}</button>`).join("")}</div>`;

// ------------------------------------------------------------------ bosh sahifa
function loadHome() {
  if (!homeP) homeP = api("api/asil/home").then((r) => { if (r.ok) { home = r; home.genres = home.genres || []; home.countries = home.countries || []; } else homeP = null; return r; });
  return homeP;
}
const fTyp = (arr, t) => t === "all" ? (arr || []) : (arr || []).filter((x) => x.type === t);
function heroHTML(arr) {
  if (!arr.length) return "";
  return `<div class="as-hero" id="ashero">${arr.map((x, i) => `<div class="as-slide" data-aid="${x.id}" role="button">
    ${x.p ? `<div class="as-hbg" style="background-image:url('${esc(x.p)}')"></div>` : ""}<div class="as-hsh"></div>
    ${x.p ? `<img class="as-hp" src="${esc(x.p)}" alt=""${i ? ' loading="lazy"' : ""} decoding="async" referrerpolicy="no-referrer">` : ""}
    <div class="as-htx"><small>🏆 ${i ? T(`Hafta topi №${i + 1}`, `Топ недели №${i + 1}`, `Week's top #${i + 1}`) : T("Hafta kinosi", "Фильм недели", "Movie of the week")}</small>
      <h3>${esc(x.t)}</h3><p>${[x.y, (x.g || [])[0], x.imdb ? "★ " + x.imdb : "", x.type === "serial" ? T("Serial", "Сериал", "Series") : ""].filter(Boolean).map(esc).join(" · ")}</p></div>
    <span class="as-hbt">📥 ${T("Botga yuborish", "Отправить в бота", "Send to bot")}</span></div>`).join("")}</div>
    ${arr.length > 1 ? `<div class="as-hdots" id="ashdots">${arr.map((_, i) => `<i class="${i ? "" : "on"}"></i>`).join("")}</div>` : ""}`;
}
function viewHome() {
  if (!home) {
    loadHome().then((r) => {
      if (view.k !== "home" || !main) return;
      if (r.ok) { paintStrip(); paint(); } else if (kinoMode() && q.length < 2) main.innerHTML = empty("📶", ERR(r.error), retryBtn());
    });
    return typesHTML(homeTyp) + `<div class="as-hsk"></div><div class="sec-h"><h2>&nbsp;</h2></div><div class="row">${skelCards(4)}</div>`;
  }
  const t = homeTyp;
  const pop = fTyp(home.pop, t);
  const heroes = (pop.length ? pop : fTyp(t === "serial" ? home.serial : home.film, t)).slice(0, 5);
  const rest = pop.length - heroes.length >= 4 ? pop.slice(heroes.length) : pop;
  const cts = byCount(home.countries).slice(0, 14);
  return typesHTML(t) + heroHTML(heroes)
    + `<div id="ashcoll">${homeCollsHTML()}</div>`
    + rowHTML("🔥 " + T("Ommabop — 7 kun", "Популярное — 7 дней", "Popular — 7 days"), rest, "pop")
    + (t !== "serial" ? rowHTML("🆕 " + T("Yangi filmlar", "Новые фильмы", "New movies"), home.film, "new", "film") : "")
    + (t !== "film" ? rowHTML("📺 " + T("Yangi seriallar", "Новые сериалы", "New series"), home.serial, "new", "serial") : "")
    + (cts.length ? `<div class="sec-h"><h2>🌍 ${T("Davlatlar", "Страны", "Countries")}</h2>${allBtn("all")}</div><div class="row as-ctrow">${cts.map(ctHTML).join("")}</div>` : "")
    + `<p class="as-src">${T("Kinolar", "Фильмы", "Movies")} · <b>AsilMedia</b> ${T("hamkorligida", "в партнёрстве", "partner catalogue")}</p>`;
}

// Bosh sahifadagi «Kolleksiyalar» qatori — ilova har ochilganda boshqa to'plamlar (tasodifiy tartib, keshlanmaydi)
let hColls = null, hCollsP = null;
function homeCollsHTML() {
  if (!hColls) {
    if (!hCollsP) hCollsP = api("api/asil/colls?limit=10").then((r) => {
      hColls = r.ok ? r.items : [];
      if (r.ok && r.groups && r.groups.length && !collGroups) collGroups = r.groups;
      const el = $("ashcoll"); if (el) el.innerHTML = homeCollsHTML();
    });
    return `<div class="as-clsk"></div>`;
  }
  return hColls.length ? `<div class="sec-h"><h2>📚 ${T("Kolleksiyalar", "Подборки", "Collections")}</h2>${allBtn("colls")}</div>
    <div class="row as-clrow">${hColls.map(collHTML).join("")}</div>` : "";
}

// «Hafta kinosi» karuseli: 5 soniyada o'zi suriladi; barmoq tegsa / kino ochiq / ekrandan tashqarida — to'xtaydi
let heroT = null, heroTouch = 0, heroRaf = 0;
function startHero() {
  clearInterval(heroT); heroT = null;
  const h = $("ashero"); if (!h || h.children.length < 2) return;
  const touched = () => { heroTouch = Date.now(); };
  h.addEventListener("touchstart", touched, {passive: true});
  h.addEventListener("pointerdown", touched, {passive: true});
  h.addEventListener("wheel", touched, {passive: true});
  h.addEventListener("scroll", () => {
    if (heroRaf) return;
    heroRaf = requestAnimationFrame(() => {
      heroRaf = 0;
      const d = $("ashdots"); if (!d || !h.clientWidth) return;
      const i = Math.round(h.scrollLeft / h.clientWidth);
      Array.prototype.forEach.call(d.children, (el, k) => el.classList.toggle("on", k === i));
    });
  }, {passive: true});
  if (REDUCE) return;
  heroT = setInterval(() => {
    const el = $("ashero");
    if (!el) { clearInterval(heroT); heroT = null; return; }
    if (document.hidden || det || Date.now() - heroTouch < 8000) return;
    const r = el.getBoundingClientRect();
    if (r.bottom < 60 || r.top > window.innerHeight) return;
    const w = el.clientWidth, n = el.children.length, i = Math.round(el.scrollLeft / w);
    el.scrollTo({left: ((i + 1) % n) * w, behavior: "smooth"});
  }, 5000);
}

// ------------------------------------------------------------------ ro'yxat sahifasi (Ommabop / Yangi / janr / davlat)
function curL() {
  const key = [view.k, view.s || "", view.typ].join("|");
  let L = cache.get(key);
  if (!L) {
    L = {key, raw: [], ids: new Set(), page: 0, more: true, busy: false, err: "", rv: 0, dry: 0};
    cache.set(key, L);
    if (cache.size > 10) cache.delete(cache.keys().next().value);
  }
  return L;
}
function shape(arr) {
  const s = view.srt;
  if (typeof s === "number") return arr.filter((x) => +x.y === s);
  if (s === "imdb") return arr.slice().sort((a, b) => (+b.imdb || 0) - (+a.imdb || 0));
  return arr;
}
function listHead() {
  let e, n, sub, a, b, back = "home", backL = T("Asosiy", "Главная", "Home");
  const gl = (arr) => (arr || []).find((g) => g.s === view.s);
  if (view.k === "coll") {
    const m = curL().meta || {}, p = hashPal(norm(view.s));
    return `<div class="as-ghead" style="background:linear-gradient(130deg,${p[0]},${p[1]})"><div class="as-gi">📚</div><h2>${esc(m.t || view.n)}</h2>
      <p>${m.c ? `${NB(m.c)} ${T("ta kino", "фильмов", "titles")}` : T("Kolleksiya", "Подборка", "Collection")}${m.gn ? " · " + esc(m.gn) : ""}</p>
      <button class="as-back" data-go="colls">‹ ${T("Kolleksiyalar", "Подборки", "Collections")}</button></div>`;
  }
  if (view.k === "pop") { e = "🔥"; n = T("Ommabop", "Популярное", "Popular"); sub = T("So'nggi 7 kunda eng ko'p ko'rilganlar", "Самое смотрибельное за 7 дней", "Most watched in the last 7 days"); [a, b] = ["#FF6B3D", "#8A1E0E"]; }
  else if (view.k === "new") { e = "🆕"; n = T("Yangi qo'shilganlar", "Новинки", "Just added"); sub = T("Saytga eng so'nggi qo'shilgan kinolar", "Последние добавленные", "Latest additions"); [a, b] = ["#3DD6FF", "#0E4A8A"]; }
  else {
    const isG = view.k === "genre";
    const g = gl(home && (isG ? home.genres : home.countries));
    const st = isG ? gStyle(view.n) : (() => { const p = hashPal(norm(view.n)); return {e: flag(view.n), a: p[0], b: p[1]}; })();
    e = st.e; a = st.a; b = st.b; n = view.n;
    sub = g && g.c ? `${NB(g.c)} ${T("ta kino", "фильмов", "titles")}` : T("Har kuni yangilanadi", "Обновляется ежедневно", "Updated daily");
    back = "all"; backL = isG ? T("Janrlar", "Жанры", "Genres") : T("Davlatlar", "Страны", "Countries");
  }
  return `<div class="as-ghead" style="background:linear-gradient(130deg,${a},${b})"><div class="as-gi">${e}</div><h2>${esc(n)}</h2><p>${sub}</p>
    <button class="as-back" data-go="${back}">‹ ${backL}</button></div>`;
}
function sortHTML() {
  const first = view.k === "pop" ? "🔥 " + T("Ommabop", "Популярное", "Popular") : "🆕 " + T("Yangi", "Новые", "New");
  const opts = [["def", first], ["imdb", "★ IMDb"]].concat([0, 1, 2, 3].map((d) => [YEAR - d, String(YEAR - d)]));
  return `<div class="as-sort">${opts.map(([k, l]) => `<button data-srt="${k}" class="${view.srt === k ? "on" : ""}">${l}</button>`).join("")}</div>`;
}
const introHTML = () => { const m = curL().meta; return `<p class="as-intro" id="asintro">${m && m.intro ? esc(m.intro) : ""}</p>`; };
function viewList() {
  if (view.k === "coll") return listHead() + introHTML() + `<div class="grid as-grid" id="asgrid"></div><div class="as-foot" id="asfoot"></div>`;
  return listHead() + typesHTML(view.typ) + sortHTML() + `<div class="grid as-grid" id="asgrid"></div><div class="as-foot" id="asfoot"></div>`;
}
let io = null;
function renderGrid() {
  const L = curL(), g = $("asgrid"); if (!g) return;
  L.rv++;
  g.innerHTML = shape(L.raw).map(cardHTML).join("");
  foot();
  if (!L.raw.length && L.more && !L.busy && !L.err) fill();
}
function foot() {
  const L = curL(), f = $("asfoot"), g = $("asgrid"); if (!f || !g) return;
  const vis = g.children.length;
  if (io) io.disconnect();
  if (L.busy) { f.innerHTML = vis ? dots() : skel(9); return; }
  if (L.err) { f.innerHTML = vis ? `<div class="as-more"><button class="cta as-morebtn" data-as="more">🔄 ${T("Qayta urinish", "Повторить", "Retry")}</button></div>` : empty("📶", ERR(L.err), retryBtn()); return; }
  if (!L.more) {
    const txt = view.k === "coll" && L.meta && L.meta.text ? `<div class="as-ctext">${esc(L.meta.text)}</div>` : "";
    f.innerHTML = vis ? `${txt}<p class="as-end">${T("Hammasi ko'rsatildi", "Это всё", "That's everything")} · ${vis} ${T("ta", "шт.", "titles")}</p>`
      : empty("🎞", T("Bu tanlov bo'yicha kino yo'q", "По этому фильтру ничего нет", "Nothing matches this filter"), T("Boshqa yil yoki turni tanlang", "Выберите другой год или тип", "Pick another year or type"));
    return;
  }
  if (L.dry >= 2) {
    f.innerHTML = `${vis ? "" : empty("🔎", T(`${view.srt} — hozircha topilmadi`, `${view.srt} — пока не найдено`, `${view.srt} — nothing yet`))}<div class="as-more"><button class="cta as-morebtn" data-as="more">${T("Yana qidirish", "Искать дальше", "Keep searching")}</button></div>`;
    return;
  }
  f.innerHTML = `<div class="as-sent" id="assent"></div>`;
  if (!("IntersectionObserver" in window)) { f.innerHTML = `<div class="as-more"><button class="cta as-morebtn" data-as="more">${T("Yana ko'rsatish", "Показать ещё", "Show more")}</button></div>`; return; }
  if (!io) io = new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting)) (view.k === "colls" ? cfill : fill)(); }, {rootMargin: "900px 0px"});
  io.observe($("assent"));
}
async function fill() {
  const L = curL();
  if (L.busy || !L.more || L.dry >= 2) return;
  L.busy = true; L.err = "";
  foot();
  const v = view, s = v.srt, rv = L.rv, before = L.raw.length;
  const isYear = typeof s === "number";
  const maxP = s === "imdb" ? (before < 90 ? Math.max(1, Math.ceil((90 - before) / 30)) : 2) : isYear ? 6 : 1;
  let n = 0;
  const batch = [];
  while (L.more && n < maxP) {
    let url;
    if (v.k === "coll") url = "api/asil/coll?" + new URLSearchParams({slug: v.s, page: L.page + 1});
    else {
      const p = new URLSearchParams({kind: v.k === "pop" ? "popular" : v.k === "new" ? "latest" : v.k, page: L.page + 1});
      if (v.s) p.set("slug", v.s);
      if (v.typ !== "all") p.set("type", v.typ);
      url = "api/asil/list?" + p;
    }
    const r = await api(url);
    if (!r.ok) { L.err = r.error; break; }
    if (r.coll && !L.meta) {
      L.meta = r.coll;
      const h = main && main.querySelector(".as-ghead");
      if (h && curL() === L) { h.outerHTML = listHead(); const ii = $("asintro"); if (ii) ii.outerHTML = introHTML(); }
    }
    L.page = r.page; L.more = !!r.more && r.items.length > 0;
    const fresh = r.items.filter((x) => x && !L.ids.has(x.id));
    fresh.forEach((x) => L.ids.add(x.id));
    L.raw.push(...fresh); batch.push(...fresh); n++;
    if (isYear && view.srt === s && shape(batch).length >= 12) break;
  }
  L.busy = false;
  if (isYear && !L.err) L.dry = shape(batch).length ? 0 : L.dry + 1;
  if (curL() !== L || !$("asgrid") || q.length >= 2) return;   // boshqa sahifaga o'tildi — ma'lumot keshda qoladi
  if (L.rv !== rv || view !== v || view.srt !== s || (s === "imdb" && before < 90)) { renderGrid(); return; }
  $("asgrid").insertAdjacentHTML("beforeend", shape(batch).map(cardHTML).join(""));   // faqat oxiriga — scroll sakramaydi
  foot();
}
function setSort(s) {
  if (view.srt === s) return;
  haptic();
  view.srt = s;
  const L = curL(); L.dry = 0;
  main.querySelectorAll(".as-sort button").forEach((b) => b.classList.toggle("on", b.dataset.srt === String(s)));
  renderGrid();
  const sb = main.querySelector(".as-sort"), top = document.querySelector("header.top");
  if (sb) {
    const y = sb.getBoundingClientRect().top - (top ? top.offsetHeight : 0) - 8;
    if (y < 0) window.scrollTo(0, Math.max(0, window.scrollY + y));
  }
}

// ------------------------------------------------------------------ kolleksiyalar (bo'limlar + tasodifiy tartib, seed bilan sahifalash)
let collGroups = null, collGrp = "";
const CS = new Map();
function cst() {
  let st = CS.get(collGrp);
  if (!st) { st = {items: [], ids: new Set(), page: 0, seed: null, more: true, busy: false, err: ""}; CS.set(collGrp, st); }
  return st;
}
function viewColls() {
  const gs = collGroups || [];
  const tabs = [["", T("Hammasi", "Все", "All")]].concat(gs.map((g) => [g.s, g.n]));
  return `<div class="sec-h"><h2>📚 ${T("Kolleksiyalar", "Подборки", "Collections")}</h2><span>${gs.length ? NB(gs.reduce((a, g) => a + (+g.c || 0), 0)) + " " + T("ta", "", "") : ""}</span></div>
    <div class="as-sort as-cgroups">${tabs.map(([k, l]) => `<button data-cg="${esc(k)}" class="${k === collGrp ? "on" : ""}">${esc(l)}</button>`).join("")}</div>
    <div class="as-cgrid" id="ascgrid"></div><div class="as-foot" id="asfoot"></div>`;
}
function renderColls() {
  const st = cst(), g = $("ascgrid"); if (!g) return;
  g.innerHTML = st.items.map(collHTML).join("");
  cfoot();
}
function cfoot() {
  const st = cst(), f = $("asfoot"), g = $("ascgrid"); if (!f || !g) return;
  if (io) io.disconnect();
  if (st.busy) { f.innerHTML = g.children.length ? dots() : `<div class="as-cgrid">${Array.from({length: 6}, () => '<div class="as-cl sk"><div class="as-cov"></div></div>').join("")}</div>`; return; }
  if (st.err) { f.innerHTML = g.children.length ? `<div class="as-more"><button class="cta as-morebtn" data-as="cmore">🔄 ${T("Qayta urinish", "Повторить", "Retry")}</button></div>` : empty("📶", ERR(st.err), `<br><br><button class="cta" style="max-width:220px" data-as="cmore">🔄 ${T("Qayta urinish", "Повторить", "Retry")}</button>`); return; }
  if (!st.more) { f.innerHTML = g.children.length ? "" : empty("📚", T("Hozircha kolleksiya yo'q", "Подборок пока нет", "No collections yet")); return; }
  f.innerHTML = `<div class="as-sent" id="assent"></div>`;
  if (!("IntersectionObserver" in window)) { f.innerHTML = `<div class="as-more"><button class="cta as-morebtn" data-as="cmore">${T("Yana ko'rsatish", "Показать ещё", "Show more")}</button></div>`; return; }
  if (!io) io = new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting)) (view.k === "colls" ? cfill : fill)(); }, {rootMargin: "900px 0px"});
  io.observe($("assent"));
}
async function cfill() {
  const st = cst();
  if (st.busy || !st.more) return;
  st.busy = true; st.err = "";
  cfoot();
  const p = new URLSearchParams({limit: 20, page: st.page + 1});
  if (collGrp) p.set("group", collGrp);
  if (st.seed) p.set("seed", st.seed);            // o'sha tasodifiy tartib — sahifalar aralashmaydi, takrorlanmaydi
  const r = await api("api/asil/colls?" + p);
  st.busy = false;
  if (!r.ok) st.err = r.error;
  else {
    st.page = r.page; st.more = !!r.more && r.items.length > 0; st.seed = st.seed || r.seed;
    if (r.groups && r.groups.length && !collGroups) {
      collGroups = r.groups;
      const bar = main && main.querySelector(".as-cgroups");
      if (bar && view.k === "colls") { const tmp = document.createElement("div"); tmp.innerHTML = viewColls(); bar.replaceWith(tmp.querySelector(".as-cgroups")); }
    }
    const fresh = r.items.filter((x) => !st.ids.has(x.s));
    fresh.forEach((x) => st.ids.add(x.s));
    st.items.push(...fresh);
    if (cst() === st && view.k === "colls" && $("ascgrid")) $("ascgrid").insertAdjacentHTML("beforeend", fresh.map(collHTML).join(""));
  }
  if (cst() === st && view.k === "colls") cfoot();
}

// ------------------------------------------------------------------ barcha janrlar + davlatlar
function viewAll() {
  if (!home) { loadHome().then((r) => { if (view.k === "all") { if (r.ok) { paintStrip(); paint(); } else main.innerHTML = empty("📶", ERR(r.error), retryBtn()); } }); return skel(8); }
  const gs = byCount(home.genres), cs = byCount(home.countries);
  return `<div class="sec-h"><h2>🎭 ${T("Barcha janrlar", "Все жанры", "All genres")}</h2><span>${gs.length} ${T("ta", "", "")}</span></div>
    <div class="as-tiles">${gs.map((g) => { const st = gStyle(g.n); return `<button class="as-tl" data-gs="${esc(g.s)}" data-gn="${esc(g.n)}" style="background:linear-gradient(140deg,${st.a},${st.b})"><b>${esc(g.n)}</b>${g.c ? `<small>${NB(g.c)} ${T("ta", "", "")}</small>` : ""}<i>${st.e}</i></button>`; }).join("")}</div>
    ${cs.length ? `<div class="sec-h"><h2>🌍 ${T("Davlatlar", "Страны", "Countries")}</h2><span>${cs.length} ${T("ta", "", "")}</span></div><div class="as-ctry">${cs.map(ctHTML).join("")}</div>` : ""}`;
}

// ------------------------------------------------------------------ qidiruv
let search = {q: "", items: null, busy: false};
function viewSearch() {
  if (search.q !== q) {
    clearTimeout(qT);
    const want = q;
    search = {q, items: null, busy: true};
    qT = setTimeout(() => api("api/asil/search?q=" + encodeURIComponent(want)).then((r) => {
      if (search.q !== want) return;
      search.busy = false; search.items = r.ok ? r.items : []; search.err = r.ok ? "" : r.error; paint();
    }), 350);
    return skel(6);
  }
  if (search.busy || !search.items) return skel(6);
  if (search.err) return empty("📶", ERR(search.err));
  return search.items.length
    ? `<div class="sec-h"><h2>${T("Natijalar", "Результаты", "Results")}</h2><span>${search.items.length}</span></div><div class="grid">${search.items.map(cardHTML).join("")}</div>`
    : empty("🔍", T("Hech narsa topilmadi", "Ничего не найдено", "Nothing found"), T("Boshqacha yozib ko'ring yoki kino kodini kiriting", "Попробуйте иначе или введите код", "Try another spelling or the movie code"));
}

function paint() {
  if (!main || !kinoMode()) return;
  if (io) io.disconnect();
  if (q.length >= 2) { main.innerHTML = viewSearch(); return; }
  if (view.k === "home") { main.innerHTML = viewHome(); startHero(); }
  else if (view.k === "all") main.innerHTML = viewAll();
  else if (view.k === "colls") { main.innerHTML = viewColls(); renderColls(); if (!cst().items.length) cfill(); }
  else { main.innerHTML = viewList(); renderGrid(); }
}

// ------------------------------------------------------------------ batafsil
function ensureDet() {
  if ($("asdet")) return;
  const d = document.createElement("div");
  d.className = "det as-det"; d.id = "asdet";
  d.innerHTML = `<button class="as-x" data-as="close" aria-label="${T("Yopish", "Закрыть", "Close")}">✕</button><div id="asdv"></div>`;
  document.body.appendChild(d);
  d.addEventListener("click", onDetClick);
}
async function openItem(id) {
  ensureDet();
  det = {id, it: null, season: 0, busy: {}};
  $("asdv").innerHTML = `<div class="as-dots big"><i></i><i></i><i></i></div>`;
  requestAnimationFrame(() => $("asdet").classList.add("open"));
  document.body.classList.add("as-detopen");
  try { tg.BackButton.show(); } catch (e) {}
  haptic();
  const r = await api("api/asil/item?id=" + id);
  if (!det || det.id !== id) return;
  if (!r.ok) { $("asdv").innerHTML = empty("📶", ERR(r.error)); return; }
  det.it = r.item;
  if (r.item.seasons && r.item.seasons.length) det.season = r.item.seasons[0].n;
  paintDet();
}
function closeDet() {
  if (!det) return false;
  det = null;
  const d = $("asdet"); if (d) d.classList.remove("open");
  document.body.classList.remove("as-detopen");
  try { if (!window.ZK_canHideBack || window.ZK_canHideBack()) tg.BackButton.hide(); } catch (e) {}
  return true;
}
const fileBtn = (f, label) => `<button class="as-f${f.ok ? "" : " off"}" data-slot="${f.s}"${f.ok ? "" : " disabled"}>
  <b>📥 ${esc(f.q || label || T("Fayl", "Файл", "File"))}</b><small>${f.mb ? (f.mb >= 1024 ? (f.mb / 1024).toFixed(1) + " GB" : f.mb + " MB") : ""}${f.parts > 1 ? ` · ${f.parts} ${T("bo'lak", "частей", "parts")}` : ""}${f.tr ? " · " + esc(f.tr) : ""}${f.ok ? "" : " · " + T("tayyorlanmoqda", "готовится", "preparing")}</small></button>`;
function paintDet() {
  const x = det.it;
  const meta = [x.y, x.dur, x.lang].filter(Boolean).map(esc).join(" · ");
  let files = "";
  if (x.seasons) {
    const ss = x.seasons;
    const cur = ss.find((s) => s.n === det.season) || ss[0];
    files = `${ss.length > 1 ? `<div class="as-seas">${ss.map((s) => `<button data-season="${s.n}" class="${s.n === cur.n ? "on" : ""}">${s.n ? s.n + "-" + T("fasl", "сезон", "season") : T("Qismlar", "Серии", "Episodes")}</button>`).join("")}</div>` : ""}
      <div class="as-eps">${cur.eps.map((e) => `<div class="as-ep"><span>${esc(e.name || e.e + "-" + T("qism", "серия", "ep."))}</span><div>${e.f.map((f) => fileBtn(f)).join("")}</div></div>`).join("")}</div>`;
  } else {
    files = (x.files || []).length ? `<div class="as-files">${x.files.map((f) => fileBtn(f)).join("")}</div>` : `<p class="as-note">${T("Fayl hali yuklanmagan", "Файл ещё не загружен", "No file yet")}</p>`;
  }
  $("asdv").innerHTML = `<div class="hero">${x.p ? `<div class="blur" style="background-image:url('${esc(x.p)}')"></div>` : ""}${posterHTML(x)}</div>
    <div class="as-body"><h1>${esc(x.t)}</h1>${x.alt ? `<p class="as-alt">${esc(x.alt)}</p>` : ""}
    <p class="as-meta">${meta}${x.imdb ? ` · <b class="as-im">IMDb ${esc(x.imdb)}</b>` : ""}</p>
    <div class="as-tags">${(x.g || []).concat(x.c || []).map((t) => `<span>${esc(t)}</span>`).join("")}</div>
    <div class="as-lbl">📥 ${T("Telegram'ga yuborish", "Отправить в Telegram", "Send to Telegram")} <small>${T("— bot sizga faylni yuboradi", "— бот пришлёт файл", "— the bot sends you the file")}</small></div>
    ${files}
    ${x.watch ? `<button class="as-watch" data-as="watch">▶️ ${T("Saytda tomosha qilish", "Смотреть на сайте", "Watch on the website")}</button>` : ""}
    ${x.desc ? `<p class="as-desc">${esc(x.desc)}</p>` : ""}
    <p class="as-src">${T("Kino kodi", "Код фильма", "Movie code")}: <b>${x.id}</b> · AsilMedia</p></div>`;
}
async function send(slot, btn, recheck) {
  if (!det || !det.it || det.busy[slot]) return;
  det.busy[slot] = 1; if (btn) btn.classList.add("busy");
  const r = await api("api/asil/send", {id: det.it.id, slot, recheck: !!recheck});
  if (det) delete det.busy[slot];
  if (btn) btn.classList.remove("busy");
  if (r.ok) {
    haptic("ok");
    toast(r.dup ? T("⏳ Yuborilmoqda — botni oching", "⏳ Отправляется — откройте бота", "⏳ On its way — open the bot")
      : T("✅ Kino botga yuborildi — chatni oching", "✅ Фильм отправлен в бота", "✅ Sent to the bot — open the chat"));
    return;
  }
  haptic("err");
  if (r.error === "need_start" && window.ZK_BOT) { try { tg.openTelegramLink(`https://t.me/${window.ZK_BOT}?start=kino`); } catch (e) {} toast(T("Avval botni ishga tushiring", "Сначала запустите бота", "Start the bot first")); return; }
  if (r.error === "need_sub") {
    const chs = r.channels || [];
    $("asdv").insertAdjacentHTML("afterbegin", `<div class="as-sub-box"><b>📢 ${T("Kanallarga obuna bo'ling", "Подпишитесь на каналы", "Subscribe to the channels")}</b>
      ${chs.map((c) => `<a class="as-chan" data-url="${esc(c.url)}">${esc(c.title)} ›</a>`).join("")}
      <button class="cta" data-recheck="${slot}">✅ ${T("Obuna bo'ldim", "Я подписался", "I've subscribed")}</button></div>`);
    $("asdet").scrollTop = 0;
    return;
  }
  if (r.error === "rate") { toast(T(`⏳ Limit — ${Math.ceil((r.retry || 600) / 60)} daqiqadan keyin`, `⏳ Лимит — через ${Math.ceil((r.retry || 600) / 60)} мин`, `⏳ Limit — try in ${Math.ceil((r.retry || 600) / 60)} min`)); return; }
  toast(ERR(r.error));
}
function onDetClick(e) {
  const t = e.target;
  const sl = t.closest("[data-slot]");
  if (sl) { haptic(); send(+sl.dataset.slot, sl); return; }
  const se = t.closest("[data-season]");
  if (se && det) { det.season = +se.dataset.season; haptic(); paintDet(); return; }
  const rc = t.closest("[data-recheck]");
  if (rc) { const b = t.closest(".as-sub-box"); if (b) b.remove(); send(+rc.dataset.recheck, null, true); return; }
  const ch = t.closest("[data-url]");
  if (ch) { try { tg.openTelegramLink(ch.dataset.url); } catch (er) { window.open(ch.dataset.url); } return; }
  const a = t.closest("[data-as]");
  if (!a) return;
  if (a.dataset.as === "close") closeDet();
  else if (a.dataset.as === "watch" && det && det.it) { try { tg.openLink(det.it.watch); } catch (er) { window.open(det.it.watch); } }
}

// ------------------------------------------------------------------ hodisalar

// ------------------------------------------------------------------ hodisalar
document.addEventListener("click", (e) => {
  const sg = e.target.closest && e.target.closest("#chips .as-g[data-g]");
  if (sg) { onStrip(sg.dataset.g); return; }
  if (!main || !main.contains(e.target)) return;
  const c = e.target.closest("[data-aid]");
  if (c) { e.stopPropagation(); openItem(+c.dataset.aid); return; }
  const g = e.target.closest("[data-gs]");
  if (g) { go({k: "genre", s: g.dataset.gs, n: g.dataset.gn}); return; }
  const cl = e.target.closest("[data-coll]");
  if (cl) { go({k: "coll", s: cl.dataset.coll, n: cl.dataset.cn}); return; }
  const cg = e.target.closest("[data-cg]");
  if (cg) {
    if (cg.dataset.cg === collGrp) return;
    haptic(); collGrp = cg.dataset.cg;
    main.querySelectorAll(".as-cgroups button").forEach((b) => b.classList.toggle("on", b === cg));
    renderColls(); if (!cst().items.length) cfill();
    return;
  }
  const ct = e.target.closest("[data-c]");
  if (ct) { go({k: "country", s: ct.dataset.c, n: ct.dataset.cn}); return; }
  const gt = e.target.closest("[data-go]");
  if (gt) { go(gt.dataset.gtyp ? {k: gt.dataset.go, typ: gt.dataset.gtyp} : {k: gt.dataset.go}); return; }
  const ty = e.target.closest("[data-typ]");
  if (ty) {
    const t = ty.dataset.typ;
    if (view.k === "home") { if (homeTyp === t) return; homeTyp = t; view.typ = t; haptic(); const y = window.scrollY; paint(); window.scrollTo(0, y); }
    else if (view.typ !== t) go(Object.assign({}, view, {typ: t}), true);
    return;
  }
  const so = e.target.closest("[data-srt]");
  if (so) { const v = so.dataset.srt; setSort(/^\d+$/.test(v) ? +v : v); return; }
  const a = e.target.closest("[data-as]");
  if (!a) return;
  if (a.dataset.as === "cmore") { cst().err = ""; cfill(); return; }
  if (a.dataset.as === "more") { const L = curL(); L.dry = 0; L.err = ""; fill(); }
  else if (a.dataset.as === "retry") { homeP = null; const L = curL(); L.err = ""; L.dry = 0; paint(); }
}, true);
function onStrip(k) {
  if (q.length >= 2) { const i = $("q"); if (i) { i.value = ""; i.dispatchEvent(new Event("input", {bubbles: true})); } q = ""; }
  const v = k === "home" || k === "pop" || k === "new" || k === "all" || k === "colls" ? {k}
    : (() => { const s = k.slice(2), g = home && home.genres.find((x) => x.s === s); return {k: "genre", s, n: g ? g.n : s}; })();
  if (vkey(Object.assign({typ: homeTyp, srt: "def"}, v)) === vkey(view) || (v.k === view.k && (v.s || "") === (view.s || ""))) {
    haptic(); window.scrollTo({top: 0, behavior: REDUCE ? "auto" : "smooth"}); return;
  }
  go(v);
}
if (tg && tg.BackButton) tg.BackButton.onClick(() => { closeDet(); });
document.addEventListener("visibilitychange", () => { if (!document.hidden) heroTouch = Date.now() - 4000; });

window.ZAsil = {
  chips, countText,
  render(el, query) { main = el; q = (query || "").trim(); paint(); },
  open: openItem, close: closeDet,
  busy() { return !!det; },
  random() {
    const pool = (q.length >= 2 ? search.items : view.k === "home" ? (home && home.pop) : view.k === "all" ? null : shape(curL().raw)) || [];
    if (pool.length) openItem(pool[Math.floor(Math.random() * pool.length)].id);
  },
};
})();
