/* 🎬 Mini App asosiy skripti (avval index.html ichida edi): kino katalogi, TV, bo'limlar paneli, ishga tushirish.
   Eski telefonlar uchun legacy/ nusxasi yig'iladi (scripts/build_legacy.mjs). */
// \p{L} (Unicode harflar) Chrome 64+ da; eski WebView'da butun skript ochilmay qolmasligi uchun — xavfsiz yasaymiz
const _re = (src, flags, fallback) => { try { return new RegExp(src, flags); } catch (e) { return fallback; } };
const RE_NONWORD = _re("[^\\p{L}\\p{N}]+", "gu", /[^0-9A-Za-z\u00C0-\u024F\u0400-\u04FF\u02BB\u02BC]+/g);
const RE_NONNAME = _re("[^\\p{L}\\p{N} ]", "gu", /[^0-9A-Za-z\u00C0-\u024F\u0400-\u04FF\u02BB\u02BC ]/g);
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
if (!inTg) document.body.classList.add("no-tg");
if (tg) {
  tg.ready(); tg.expand();
  try { tg.setHeaderColor("bg_color"); tg.setBackgroundColor("bg_color"); } catch (e) {}
  try { if (tg.isVersionAtLeast("7.7")) tg.disableVerticalSwipes(); } catch (e) {}
}
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success")
  : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const fmt = (n) => n >= 1e6 ? (n/1e6).toFixed(1).replace(".0","") + "M" : n >= 1e3 ? (n/1e3).toFixed(1).replace(".0","") + "K" : String(n);

// ---------- ko'rilganlar (shu qurilmada) ----------
const SEEN_KEY = "zk_seen_v1";
let seen = {};
try { seen = JSON.parse(localStorage.getItem(SEEN_KEY) || "{}") || {}; } catch (e) { seen = {}; }
const markSeen = (c, p) => { (seen[c] = seen[c] || []).includes(p) || seen[c].push(p);
  try { localStorage.setItem(SEEN_KEY, JSON.stringify(seen)); } catch (e) {} };

// ---------- qidiruv: kirill → lotin, apostroflar ----------
const CYR = {"а":"a","б":"b","в":"v","г":"g","ғ":"g","д":"d","е":"e","ё":"yo","ж":"j","з":"z","и":"i","й":"y","к":"k",
  "қ":"q","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ў":"o","ф":"f","х":"x","ҳ":"h",
  "ц":"ts","ч":"ch","ш":"sh","щ":"sh","ъ":"","ы":"i","ь":"","э":"e","ю":"yu","я":"ya"};
const norm = (s) => String(s || "").toLowerCase().replace(/[а-яёғқўҳ]/g, (ch) => CYR[ch] ?? ch)
  .replace(/[ʻʼ'`’‘´]/g, "").replace(RE_NONWORD, " ").trim();

let items = [], byCode = new Map(), tab = "all", query = "", channel = "", botName = "", ASIL = false;

const posterHTML = (it, size, extra = "", isHero = false) => {
  const priority = isHero ? 'fetchpriority="high"' : (size === "s" ? 'loading="lazy"' : "");
  const img = it.i ? `<img src="p/${it.c}_${size}.webp?v=${it.i}" alt="${esc(it.t)}" decoding="async" ${priority} onload="this.classList.add('ok')" onerror="this.style.display='none'">` : "";
  const hue = (it.c * 47) % 360;
  return `<div class="pst"${it.i ? "" : ` style="background:linear-gradient(160deg,hsl(${hue} 45% 32%),hsl(${(hue+40)%360} 50% 14%))"`}>
    ${img || `<div class="ph">${esc(it.t)}</div>`}${extra}</div>`;
};
const cardHTML = (it, rank, isHero = false) => `<button class="card" data-c="${it.c}">${posterHTML(it, "s",
  `<span class="badge">#${it.c}</span>${it.p > 1 ? `<span class="parts">${it.p} qism</span>` : ""}` +
  (seen[it.c] ? `<span class="seen">✓</span>` : "") + (rank ? `<span class="rank">${rank}</span>` : ""), isHero || rank === 1)}
  <div class="ttl">${esc(it.t)}</div></button>`;

function skeleton() {
  $("main").innerHTML = `<div class="sec-h"><h2>&nbsp;</h2></div><div class="grid">` +
    Array.from({length: 12}, () => `<div class="card sk"><div class="pst"></div><div class="ttl"></div></div>`).join("") + "</div>";
}

let shown = [];
function render() {
  const m = $("main");
  if (ASIL && window.ZAsil) { ZAsil.render(m, query, tab); return; }
  let list = items;
  if (tab === "film") list = list.filter((x) => x.p <= 1);
  else if (tab === "ser") list = list.filter((x) => x.p > 1);
  else if (tab === "seen") list = list.filter((x) => seen[x.c]);
  else if (tab === "pop") list = [...list].sort((a, b) => b.v - a.v);
  else if (tab === "mult") list = list.filter((x) => /mult|multfilm|multik|multserial|panda|shrek|disney|pixar|ajdaho|maymoq|boss|madagaskar|muzlik|bahodir|alvasti|maugli|minion|qariya|avatar|simba|sher|ertak|krokodil|masha|ayiq/i.test(x.t + " " + (x.d || "")));
  else if (tab === "anime") list = list.filter((x) => /anime|titan|naruto|ghoul|hero|daha|bleach|one\s*piece|hunter|jujutsu|demon|saitama|death\s*note|dragon\s*ball|spirited|miyazaki|totoro|pokemon|ninja|samuray/i.test(x.t + " " + (x.d || "")));

  if (query) {
    const q = norm(query), digits = query.replace(/\D/g, "");
    const words = q.split(" ").filter(Boolean);
    const exact = digits && /^\d+$/.test(query.trim()) ? byCode.get(+digits) : null;
    list = list.filter((x) => x !== exact && (x._k.includes(q) || words.every((w) => x._k.includes(w)) ||
      (digits && String(x.c).startsWith(digits))));
    list.sort((a, b) => (b._n.startsWith(q) - a._n.startsWith(q)) || (b.v - a.v));
    if (exact) list.unshift(exact);
    shown = list;
    m.innerHTML = list.length
      ? `<div class="sec-h"><h2>Natijalar</h2><span>${list.length} ta</span></div><div class="grid">${list.map((x) => cardHTML(x)).join("")}</div>`
      : `<div class="empty"><div class="big">🔍</div><b>Hech narsa topilmadi</b>Boshqa nom bilan qidirib ko'ring yoki kino kodini botga yuboring.</div>`;
    return;
  }
  if (!list.length) {
    m.innerHTML = tab === "seen"
      ? `<div class="empty"><div class="big">🍿</div><b>Hali hech narsa ko'rmadingiz</b>Kino tanlang — u shu yerda belgilanib boradi.</div>`
      : `<div class="empty"><div class="big">🎬</div><b>Hozircha bo'sh</b></div>`;
    return;
  }
  shown = list;
  let html = "";
  if (tab === "all") {
    const top = [...items].filter((x) => x.v > 0).sort((a, b) => b.v - a.v).slice(0, 10);
    if (top.length >= 3) html += `<div class="sec-h"><h2>🔥 Top ${top.length}</h2><span>eng ko'p ko'rilgan</span></div>
      <div class="row">${top.map((x, i) => cardHTML(x, i + 1, i === 0)).join("")}</div>`;
  }
  const title = {all: "🆕 Yangi qo'shilganlar", pop: "🔥 Ommabop", film: "🎬 Filmlar", ser: "📺 Seriallar", mult: "🧸 Multfilmlar", anime: "🎌 Anime", seen: "✓ Ko'rganlarim"}[tab] || "🎬 Kinolar";
  html += `<div class="sec-h"><h2>${title}</h2><span>${list.length} ta</span></div>
    <div class="grid">${list.map((x, i) => cardHTML(x, null, i === 0 && tab !== "all")).join("")}</div>`;
  m.innerHTML = html;
}

// rasm yuklanganda silliq ko'rinadi; topilmasa — nomli fon
document.addEventListener("load", (e) => { if (e.target.tagName === "IMG") e.target.classList.add("ok"); }, true);
document.addEventListener("error", (e) => {
  const img = e.target;
  if (img.tagName !== "IMG" || !img.parentElement) return;
  if (img.classList.contains("tvl")) { img.remove(); return; }
  const it = byCode.get(+(img.closest("[data-c]")?.dataset.c || cur?.c));
  img.replaceWith(Object.assign(document.createElement("div"), {className: "ph", textContent: it ? it.t : ""}));
}, true);

// ---------- batafsil ----------
let cur = null, busy = false;
function openDetail(it, push = true) {
  cur = it; haptic();
  const big = it.i ? `p/${it.c}_l.webp?v=${it.i}` : "";
  $("hero").innerHTML = (big ? `<div class="blur" style="background-image:url('${big}')"></div>` : "") +
    posterHTML(it, "l", "", true);
  // Izohning birinchi qatori kino nomini takrorlasa — olib tashlanadi (sarlavhada bor)
  let desc = (it.d || "").trim();
  const first = desc.split("\n")[0];
  if (first && norm(first) === it._n) desc = desc.slice(first.length).trim();
  const parts = it.p > 1 ? `<div class="ph-h">📺 Qismlar</div><div class="pgrid">${
    Array.from({length: it.p}, (_, i) => `<button class="pbtn${seen[it.c]?.includes(i + 1) ? " seen" : ""}" data-p="${i + 1}">${i + 1}</button>`).join("")}</div>` : "";
  $("info").innerHTML = `<h2>${esc(it.t)}</h2>
    <div class="meta"><span>🔑 Kod: ${it.c}</span>${it.v ? `<span>👁 ${fmt(it.v)}</span>` : ""}${it.p > 1 ? `<span>📺 ${it.p} qism</span>` : ""}</div>
    ${desc ? `<p class="desc${desc.length > 320 ? " cut" : ""}" id="desc">${esc(desc)}</p>${desc.length > 320 ? `<button class="more" id="more">Ko'proq…</button>` : ""}` : ""}
    ${parts}`;
  $("det").scrollTop = 0;
  $("det").classList.add("open");
  document.body.classList.add("det-open");
  const label = it.p > 1 ? `▶️ ${nextPart(it)}-qismni ko'rish` : "▶️ Tomosha qilish";
  $("play").textContent = label;
  if (inTg) {
    tg.BackButton.show();
    const cs = getComputedStyle(document.documentElement), acc = cs.getPropertyValue("--zk-acc").trim(), ink = cs.getPropertyValue("--zk-ink").trim();
    tg.MainButton.setParams(Object.assign({text: label, is_visible: true, is_active: true}, /^#[0-9a-f]{6}$/i.test(acc) ? {color: acc, text_color: ink || "#000000"} : {}));
  }
  pushed = push;
  if (push) history.pushState({d: it.c}, "");
}
let pushed = false;
function refreshSeen(code) {
  document.querySelectorAll(`.card[data-c="${code}"] .pst`).forEach((p) => {
    if (seen[code] && !p.querySelector(".seen")) p.insertAdjacentHTML("beforeend", `<span class="seen">✓</span>`);
  });
}
function nextPart(it) {
  const s = seen[it.c] || [];
  for (let i = 1; i <= it.p; i++) if (!s.includes(i)) return i;
  return 1;
}
function closeDetail(fromPop = false) {
  if (!cur) return;
  cur = null; hideSheet();
  $("det").classList.remove("open");
  document.body.classList.remove("det-open");
  if (inTg) { tg.BackButton.hide(); tg.MainButton.hide(); }
  if (!fromPop && pushed) history.back();
  pushed = false;
  if (tab === "seen") render();
}

// ---------- tomosha qilish ----------
function toast(t, ms = 2200) {
  const el = $("toast"); el.textContent = t; el.classList.add("on");
  clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove("on"), ms);
}
function setBusy(on, part) {
  busy = on;
  if (inTg) on ? tg.MainButton.showProgress(false) : tg.MainButton.hideProgress();
  $("play").style.opacity = on ? .6 : 1;
  document.querySelectorAll(".pbtn").forEach((b) => b.classList.toggle("busy", on && +b.dataset.p === part));
}
async function watch(it, part, recheck = false) {
  if (busy) return;
  if (!inTg) { toast("📱 Kinoni olish uchun katalogni Telegram ichida oching"); return; }
  setBusy(true, part);
  let r;
  try {
    const res = await fetch("api/watch", {method: "POST",
      headers: {"Content-Type": "application/json", "X-Init-Data": tg.initData},
      body: JSON.stringify({c: it.c, p: part, code: it.c, part, recheck})});
    r = await res.json();
  } catch (e) { r = {ok: false, error: "network"}; }
  setBusy(false);
  if (r.ok) {
    haptic("ok"); markSeen(it.c, part); refreshSeen(it.c);
    if (it.p > 1) {
      document.querySelector(`.pbtn[data-p="${part}"]`)?.classList.add("seen");
      const label = `▶️ ${nextPart(it)}-qismni ko'rish`;
      $("play").textContent = label; tg.MainButton.setText(label);
      toast(r.queued ? `⏳ ${part}-qism navbatda — bir necha soniyada chatga keladi` : `✅ ${part}-qism chatga yuborildi`);
    } else {
      toast(r.queued ? "⏳ Kino navbatda — bir necha soniyada chatga keladi" : "✅ Kino chatga yuborildi");
      setTimeout(() => tg.close(), r.queued ? 1600 : 650);
    }
    return;
  }
  haptic("err");
  const msg = {
    not_found: "❌ Bu kino olib tashlangan",
    rate: `⏳ Juda ko'p so'rov. ${Math.ceil((r.retry || 600) / 60)} daqiqadan keyin urinib ko'ring`,
    auth: "⚠️ Sessiya eskirgan — katalogni yopib, qayta oching",
    network: "📶 Internet bilan muammo. Qayta urinib ko'ring",
    send_failed: "⚠️ Yuborib bo'lmadi. Birozdan keyin urinib ko'ring",
    busy: "⏳ Hozir juda ko'p odam kirdi — 5-10 soniyadan keyin qayta bosing",
  };
  if (r.error === "need_sub") return showSub(it, part, r.channels || []);
  if (r.error === "need_start") {
    toast("🤖 Botni ishga tushiryapmiz…");
    if (botName) return tg.openTelegramLink(`https://t.me/${botName}?start=kino_${it.c}`);
  }
  toast(msg[r.error] || msg.send_failed, 3200);
}

function showSub(it, part, chans) {
  $("sheet").innerHTML = `<h3>🔒 Bir qadam qoldi</h3><p>Kinoni olish uchun quyidagi kanal(lar)ga a'zo bo'ling, so'ng «Tekshirish» ni bosing.</p>
    ${chans.map((c, i) => `<button class="sbtn" data-u="${i}"><span>📢 ${esc(c.title)}</span><span>A'zo bo'lish ›</span></button>`).join("")}
    <button class="cta" id="recheck">✅ A'zo bo'ldim — tekshirish</button>`;
  $("sheet").querySelectorAll(".sbtn").forEach((b) => b.onclick = () => {
    const u = chans[+b.dataset.u].url;
    /^https:\/\/t\.me\//.test(u) ? tg.openTelegramLink(u) : tg.openLink(u);
  });
  $("recheck").onclick = () => { hideSheet(); watch(it, part, true); };
  $("sbg").classList.add("open"); $("sheet").classList.add("open");
}
function hideSheet() { $("sbg").classList.remove("open"); $("sheet").classList.remove("open"); }
$("sbg").onclick = hideSheet;

// ---------- hodisalar ----------
document.addEventListener("click", (e) => {
  const card = e.target.closest(".card[data-c]");
  if (card) { const it = byCode.get(+card.dataset.c); if (it) openDetail(it); return; }
  const pb = e.target.closest(".pbtn");
  if (pb && cur) { haptic(); watch(cur, +pb.dataset.p); return; }
  if (e.target.id === "more") { $("desc").classList.remove("cut"); e.target.remove(); }
});
$("play").onclick = () => cur && watch(cur, cur.p > 1 ? nextPart(cur) : 1);
$("dclose").onclick = () => closeDetail();
if (inTg) {
  tg.MainButton.onClick(() => cur && watch(cur, cur.p > 1 ? nextPart(cur) : 1));
  tg.BackButton.onClick(() => { if ((window.ZMusic && ZMusic.busy()) || (window.ZDocs && ZDocs.busy()) || (window.ZGames && ZGames.busy())) return; if (!tvCur) closeDetail(); });
}
window.addEventListener("popstate", () => { if (tvCur) closeTV(true); else if (cur) closeDetail(true); });

$("chips").addEventListener("click", (e) => {
  const b = e.target.closest(".chip"); if (!b) return;
  haptic();
  if (mode === "tv") tvCountry = b.dataset.t; else tab = b.dataset.t;
  $("chips").querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c === b));
  renderCur(); window.scrollTo({top: 0});
});
$("chips2").addEventListener("click", (e) => {
  const b = e.target.closest(".chip"); if (!b) return;
  haptic(); tvCat = b.dataset.t;
  $("chips2").querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c === b));
  renderTV(); window.scrollTo({top: 0});
});
let qt;
$("q").addEventListener("input", (e) => {
  query = e.target.value.trim();
  $("sbox").classList.toggle("has", !!query);
  clearTimeout(qt); qt = setTimeout(() => { renderCur(); window.scrollTo({top: 0}); }, 120);
});
$("q").addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
$("clr").onclick = (e) => { e.preventDefault(); $("q").value = ""; query = ""; $("sbox").classList.remove("has"); renderCur(); };
$("dice").onclick = (e) => {
  e.preventDefault();
  if (ASIL && mode === "kino" && window.ZAsil) { ZAsil.random(); return; }
  const pool = (mode === "kino" && shown.length ? shown : items).filter((x) => x && x.c);
  if (!pool.length) return;
  if (window.ZK_spin) window.ZK_spin(pool, (it) => openDetail(it)); else openDetail(pool[Math.floor(Math.random() * pool.length)]);
};
$("chan").onclick = () => { if (!channel) return; inTg ? tg.openTelegramLink(channel) : window.open(channel); };

// =================================================================== 📺 ONLAYN TV
const CAT = {ufc: "🥊 UFC & Jang", futbol: "⚽ Futbol & Sport", sport: "⚽ Barcha Sport", sports: "⚽ Barcha Sport",
  general: "📡 Umumiy", news: "📰 Yangiliklar", kids: "🧸 Bolalar", music: "🎵 Musiqa",
  movies: "🎬 Kino", series: "📺 Seriallar", entertainment: "🎭 Ko'ngilochar", documentary: "🌍 Hujjatli",
  religious: "🕌 Diniy", education: "📚 Ta'lim", culture: "🏛 Madaniyat", family: "👨‍👩‍👧 Oilaviy", comedy: "😂 Komediya",
  animation: "🎞 Multfilm", cooking: "🍳 Taomlar", travel: "✈️ Sayohat", auto: "🚗 Avto", business: "💼 Biznes",
  science: "🔬 Fan", outdoor: "🏕 Tabiat", lifestyle: "✨ Hayot tarzi", legislative: "🏛 Rasmiy", classic: "📼 Klassika",
  relax: "🌿 Dam olish", shop: "🛍 Savdo", weather: "🌦 Ob-havo"};
const FLAG = {uz: "🇺🇿 O'zbek", ru: "🇷🇺 Rus"};
let mode = "kino", tvItems = null, tvById = new Map(), tvCountry = "all", tvCat = "all", tvCur = null, tvList = [];
let tvSoon = false;
let hls = null, hlsLib = null, tvTimer = null, tvTry = 0, tvPushed = false;
const lsGet = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
let tvFav = lsGet("zk_tvfav", []), tvRec = lsGet("zk_tvrec", []);

function tvInitials(c) {
  const name = typeof c === "object" ? (c.n || c.name || "") : String(c);
  const ico = typeof c === "object" && c.logo ? c.logo : "";
  const w = String(name).replace(RE_NONNAME, "").trim().split(/\s+/);
  const t = (w.length > 1 ? w[0][0] + w[1][0] : (w[0] || "TV").slice(0, 3)).toUpperCase();
  let h = 0; for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) % 360;
  const d = document.createElement("div");
  d.className = "tvi";
  d.style = `background:linear-gradient(135deg,hsl(${h} 60% 45%),hsl(${(h + 40) % 360} 60% 30%))`;
  d.innerHTML = ico ? `<span class="tvi-ico" style="font-size:24px;line-height:1;margin-bottom:2px;display:block">${ico}</span><span style="font-size:12px;opacity:.9">${t}</span>` : t;
  return d;
}
const logoHTML = (c) => tvInitials(c).outerHTML +
  (c.l ? `<img class="ico tvl" src="${esc(c.l)}" alt="${esc(c.n)}" loading="lazy" decoding="async" referrerpolicy="no-referrer" onload="this.classList.add('ok')" onerror="this.onerror=null;this.src='api/tv/icon/${c.i}';this.classList.add('ok');">` : `<img class="ico tvl ok" src="api/tv/icon/${c.i}" alt="${esc(c.n)}" onerror="this.onerror=null;this.src='logo.svg';">`);
const tileHTML = (c) => `<button class="tv${tvCur && tvCur.i === c.i ? " cur" : ""}" data-tv="${esc(c.i)}"><div class="tvb">${logoHTML(c)}
  <span class="live">LIVE</span><span class="badge" style="top:auto;bottom:4px;right:4px;left:auto;font-size:9px;padding:2px 4px;background:rgba(0,0,0,.7);border:1px solid rgba(242,184,75,.6);color:#F2B84B;font-weight:800;border-radius:4px">1440p QHD</span>${tvFav.includes(c.i) ? `<span class="fav">⭐</span>` : ""}</div><div class="tvn">${c.logo ? `<span class="ch-ico" style="margin-right:2px">${c.logo}</span>` : ""}${esc(c.n)}</div></button>`;

function tvChips() {
  const cc = [...new Set(tvItems.map((x) => x.c))];
  $("chips").innerHTML = [["all", "Hammasi"], ...cc.map((c) => [c, FLAG[c] || c.toUpperCase()]), ["fav", "⭐ Sevimlilar"]]
    .map(([k, l]) => `<button class="chip${tvCountry === k ? " on" : ""}" data-t="${esc(k)}">${esc(l)}</button>`).join("");
  const cats = {};
  tvItems.forEach((x) => {
    cats[x.k] = (cats[x.k] || 0) + 1;
    if (x.categories) x.categories.forEach((catKey) => { cats[catKey] = (cats[catKey] || 0) + 1; });
  });
  const priority = ["ufc", "futbol"].filter((k) => cats[k]);
  const otherKeys = Object.keys(cats).filter((k) => !priority.includes(k) && (CAT[k] || cats[k] >= 2)).sort((a, b) => (cats[b] || 0) - (cats[a] || 0));
  const keys = [...priority, ...otherKeys];
  $("chips2").innerHTML = [["all", "Barcha janrlar"], ...keys.map((k) => [k, CAT[k] || k])]
    .map(([k, l]) => `<button class="chip s${tvCat === k ? " on" : ""}" data-t="${esc(k)}">${esc(l)}</button>`).join("");
}
function tvFiltered() {
  let l = tvItems;
  if (tvCountry === "fav") l = l.filter((x) => tvFav.includes(x.i));
  else if (tvCountry !== "all") l = l.filter((x) => x.c === tvCountry);
  if (tvCat !== "all") {
    l = l.filter((x) => x.k === tvCat || (x.categories && x.categories.includes(tvCat)) || (tvCat === "sport" && (x.k === "ufc" || x.k === "futbol" || x.k === "sport" || x.k === "sports" || (x.categories && (x.categories.includes("sport") || x.categories.includes("ufc") || x.categories.includes("futbol"))))));
  }
  if (query) {
    const q = norm(query), words = q.split(" ").filter(Boolean);
    l = l.filter((x) => words.every((w) => x._k.includes(w)));
    l = [...l].sort((a, b) => (b._k.startsWith(q) - a._k.startsWith(q)) || (b.v - a.v));
  }
  return l;
}
function renderTV() {
  if (tvSoon) return;
  const m = $("main");
  if (!tvItems) { skeletonTV(); return; }
  const l = tvFiltered();
  tvList = l;
  if (!l.length) {
    m.innerHTML = tvCountry === "fav" && !query
      ? `<div class="empty"><div class="big">⭐</div><b>Sevimli kanallar yo'q</b>Kanalni ochib ☆ ni bosing — shu yerda turadi.</div>`
      : `<div class="empty"><div class="big">📺</div><b>Kanal topilmadi</b>Boshqa nom bilan qidirib ko'ring.</div>`;
    return;
  }
  let html = "";
  if (!query && tvCountry === "all" && tvCat === "all") {
    const rec = tvRec.map((id) => tvById.get(id)).filter(Boolean).slice(0, 12);
    if (rec.length) html += `<div class="sec-h"><h2>🕘 Yaqinda ko'rilgan</h2></div><div class="row">${rec.map(tileHTML).join("")}</div>`;
    const top = [...tvItems].filter((x) => x.v > 0).sort((a, b) => b.v - a.v).slice(0, 12);
    if (top.length >= 4) html += `<div class="sec-h"><h2>🔥 Ko'p ko'rilayotgan</h2></div><div class="row">${top.map(tileHTML).join("")}</div>`;
  }
  const title = query ? "Natijalar" : tvCountry === "fav" ? "⭐ Sevimlilar" : (tvCat !== "all" ? (CAT[tvCat] || tvCat) : (FLAG[tvCountry] || "📺 Barcha kanallar"));
  html += `<div class="sec-h"><h2>${esc(title)}</h2><span>${l.length} ta</span></div><div class="tvgrid">${l.map(tileHTML).join("")}</div>`;
  m.innerHTML = html;
}
function skeletonTV() {
  $("main").innerHTML = `<div class="sec-h"><h2>&nbsp;</h2></div><div class="tvgrid">` +
    Array.from({length: 12}, () => `<div class="tv sk"><div class="tvb" style="background:var(--bg2)"></div><div class="ttl"></div></div>`).join("") + "</div>";
}
async function loadTV() {
  if (tvItems) return;
  skeletonTV();
  try {
    const r = await (await fetch("api/tv", {cache: "no-cache"})).json();
    tvItems = r.items || [];
  } catch (e) {
    $("main").innerHTML = `<div class="empty"><div class="big">📶</div><b>Kanallarni yuklab bo'lmadi</b>Internetni tekshiring.<br><br>
      <button class="cta" style="max-width:220px" id="tvreload">🔄 Qayta urinish</button></div>`;
    $("tvreload").onclick = () => loadTV();
    return;
  }
  tvItems.forEach((x) => {
    x._k = norm(x.n);
    tvById.set(x.i, x);
    tvById.set(String(x.i), x);
    if (x.id != null) {
      tvById.set(x.id, x);
      tvById.set(String(x.id), x);
    }
  });
  if (mode === "tv") { tvChips(); $("count").textContent = `${tvItems.length} ta kanal · jonli efir`; renderTV(); }
}
function setMode(m) {
  if (mode === m) return;
  try { if (window.ZHub) ZHub.used(m); } catch (e) {}
  const was = mode;
  mode = m; haptic(); document.body.dataset.zkm = m;
  document.body.classList.toggle("tvsoon", m === "tv" && tvSoon);
  $("seg").querySelectorAll && $("seg").querySelectorAll("button[data-m]").forEach((b) => b.classList.toggle("on", b.dataset.m === m));
  if (was === "tv") { try { closeTV(true); } catch (e) {} }
  if (was === "kino") { try { closeDetail(true); } catch (e) {} }
  try { if (window.ZAsil && ZAsil.close) ZAsil.close(); } catch (e) {}
  try { stopVideo(); } catch (e) {}
  if (was === "music" && window.ZMusic) { try { ZMusic.close(); } catch (e) {} }
  if (was === "docs" && window.ZDocs) { try { ZDocs.close(); } catch (e) {} }
  if (was === "games" && window.ZGames) { try { ZGames.close(); } catch (e) {} }
  if (was === "story" && window.ZStory) { try { ZStory.close(); } catch (e) {} }
  if (was === "books" && window.ZBooks) { try { ZBooks.close(); } catch (e) {} }
  if (was === "fx" && window.ZFx) { try { ZFx.close(); } catch (e) {} }
  if (was === "food" && window.ZFood) { try { ZFood.close(); } catch (e) {} }
  if (was === "quiz" && window.ZQuiz) { try { ZQuiz.close(); } catch (e) {} }
  if (was === "prava" && window.ZPrava) { try { ZPrava.close(); } catch (e) {} }
  if (was === "rasxod" && window.ZRasxod) { try { ZRasxod.close(); } catch (e) {} }
  if (was === "kal" && window.ZKal) { try { ZKal.close(); } catch (e) {} }
  if (was === "mafia" && window.ZMafia) { try { ZMafia.close(); } catch (e) {} }
  if (was === "tvroom" && window.ZTvRoom) { try { ZTvRoom.close(); } catch (e) {} }
  if (m === "music") { if (window.ZMusic) { try { ZMusic.open(); } catch (e) {} } return; }
  if (m === "docs") { if (window.ZDocs) { try { ZDocs.open(); } catch (e) {} } return; }
  if (m === "games") { if (window.ZGames) { try { ZGames.open(); } catch (e) {} } return; }
  if (m === "story") { if (window.ZStory) { try { ZStory.open(); } catch (e) {} } return; }
  if (m === "books") { if (window.ZBooks) { try { ZBooks.open(); } catch (e) {} } return; }
  if (m === "fx") { if (window.ZFx) { try { ZFx.open(); } catch (e) {} } return; }
  if (m === "food") { if (window.ZFood) { try { ZFood.open(); } catch (e) {} } return; }
  if (m === "quiz") { if (window.ZQuiz) { try { ZQuiz.open(); } catch (e) {} } return; }
  if (m === "prava") { if (window.ZPrava) { try { ZPrava.open(); } catch (e) {} } return; }
  if (m === "rasxod") { if (window.ZRasxod) { try { ZRasxod.open(); } catch (e) {} } return; }
  if (m === "kal") { if (window.ZKal) { try { ZKal.open(); } catch (e) {} } return; }
  if (m === "mafia") { if (window.ZMafia) { try { ZMafia.open(); } catch (e) {} } return; }
  if (m === "tvroom") { if (window.ZTvRoom) { try { ZTvRoom.open(); } catch (e) {} } return; }
  $("seg").querySelectorAll("button[data-m]").forEach((b) => b.classList.toggle("on", b.dataset.m === m));
  $("q").placeholder = m === "tv" ? "Kanal nomi…" : "Kino nomi yoki kodi…";
  $("chan").hidden = m === "tv" || !channel;
  $("chips2").hidden = m !== "tv";
  if (m === "tv") { try { loadHlsLib(); } catch (e) {} }
  if (m === "tv" && tvSoon) {
    $("chips2").hidden = true; $("chips").innerHTML = ""; $("count").textContent = "Jonli efir · tez kunda";
    $("main").innerHTML = `<div class="soon"><div class="soon-tv"><span></span><i>📺</i></div>
      <h2>TV tez kunda</h2>
      <p>O'zbek telekanallari va Makka–Madina jonli efirini tayyorlayapmiz. Ishga tushishi bilan botda xabar beramiz.</p>
      <button class="cta" id="soonback">🎬 Kinolarga qaytish</button></div>`;
    $("soonback").onclick = () => setMode("kino");
  } else if (m === "tv") {
    if (tvItems) { tvChips(); $("count").textContent = `${tvItems.length} ta kanal · jonli efir`; renderTV(); } else loadTV();
  } else {
    $("chips").innerHTML = ASIL ? ZAsil.chips() : KINO_CHIPS;
    $("chips").querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c.dataset.t === tab));
    $("count").textContent = ASIL ? ZAsil.countText() : `${items.length} ta kino · posterini bosing`;
    render();
  }
  window.scrollTo({top: 0});
}
const KINO_CHIPS = $("chips").innerHTML;
$("seg").addEventListener("click", (e) => { const b = e.target.closest("button[data-m]"); if (b) setMode(b.dataset.m); });
window.ZK_setMode = setMode;
window.ZK_canHideBack = () => !cur && !tvCur && !(window.ZTvRoom && ZTvRoom.busy()) && !(window.ZAsil && ZAsil.busy()) && !(window.ZMusic && ZMusic.busy()) && !(window.ZDocs && ZDocs.busy()) && !(window.ZGames && ZGames.busy()) && !(window.ZStory && ZStory.busy()) && !(window.ZBooks && ZBooks.busy()) && !(window.ZFx && ZFx.busy()) && !(window.ZFood && ZFood.busy()) && !(window.ZQuiz && ZQuiz.busy()) && !(window.ZPrava && ZPrava.busy()) && !(window.ZRasxod && ZRasxod.busy()) && !(window.ZKal && ZKal.busy()) && !(window.ZMafia && ZMafia.busy());
function renderCur() { mode === "tv" ? renderTV() : render(); }

// ---------- pleyer ----------
const vid = $("vid");
function tvState(s, msg) {
  $("vload").hidden = s !== "load"; $("verr").hidden = s !== "err";
  if (msg) (s === "err" ? $("verrt") : $("vmsg")).textContent = msg;
}
function stopVideo() {
  clearTimeout(tvTimer);
  const yt = $("yt"); if (!yt.hidden) { yt.src = "about:blank"; yt.hidden = true; } vid.hidden = false;
  if (hls) { try { hls.destroy(); } catch (e) {} hls = null; }
  vid.pause(); vid.removeAttribute("src"); try { vid.load(); } catch (e) {}
}
function loadHlsLib() {
  if (hlsLib) return hlsLib;
  hlsLib = new Promise((ok, bad) => {
    const sc = document.createElement("script");
    sc.src = "https://cdn.jsdelivr.net/npm/hls.js@1.5.13/dist/hls.min.js";
    sc.onload = () => ok(window.Hls); sc.onerror = () => { hlsLib = null; bad(new Error("hls")); };
    document.head.appendChild(sc);
  });
  return hlsLib;
}
const nativeHls = () => !!vid.canPlayType("application/vnd.apple.mpegurl") && /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent);
function report(c, idx, ok, bad = false) {
  if (!inTg) return;
  fetch("api/tv/report", {method: "POST", headers: {"Content-Type": "application/json", "X-Init-Data": tg.initData},
    body: JSON.stringify({id: c.i, i: idx, ok, bad})}).catch(() => {});
}
// YouTube rasmiy jonli efiri → embed manzili (aks holda null)
function ytEmbed(url) {
  let m = url.match(/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|live\/|embed\/)|youtu\.be\/)([\w-]{11})/);
  if (m) return `https://www.youtube.com/embed/${m[1]}`;
  m = url.match(/youtube\.com\/channel\/(UC[\w-]{22})/);
  if (m) return `https://www.youtube.com/embed/live_stream?channel=${m[1]}`;
  return null;
}
function attempt(url) {
  return new Promise(async (ok, bad) => {
    let done = false;
    const fin = (f, v) => { if (!done) { done = true; clearTimeout(tvTimer); vid.onplaying = vid.onerror = vid.oncanplay = vid.onloadeddata = vid.onloadedmetadata = vid.ontimeupdate = null; f(v); } };
    const _conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const _downlink = (_conn && _conn.downlink) ? _conn.downlink : 10;
    const _isSlow = Boolean(_conn && (_conn.saveData || _downlink < 2.0 || (_conn.effectiveType && /2g/.test(_conn.effectiveType))));
    if (_conn && (_downlink < 2.0 || /2g/.test(_conn.effectiveType || "")) && !window._tvSpeedWarned) {
      window._tvSpeedWarned = true;
      try { setTimeout(() => { toast("⚠️ Internet tezligi 2 Mbit/s dan past. 1440p QHD tiniq ko'rish uchun 2+ Mbit/s tavsiya etiladi.", 3200); }, 600); } catch (e) {}
    }
    tvTimer = setTimeout(() => fin(bad, "timeout"), _isSlow ? 3500 : 2000);
    vid.onplaying = () => fin(ok);
    vid.oncanplay = () => fin(ok);
    vid.onloadeddata = () => fin(ok);
    vid.onloadedmetadata = () => fin(ok);
    vid.ontimeupdate = () => { if (vid.currentTime > 0) fin(ok); };
    vid.onerror = () => fin(bad, "media");

    let streamTarget = url;
    if (!streamTarget.includes("/api/tv/stream") && streamTarget.includes("cinerama.uz") && streamTarget.includes("tracks-v1a1")) {
      streamTarget = streamTarget.replace("tracks-v1a1/mono.ts.m3u8", "playlist.m3u8").replace("tracks-v1a1/mono.m3u8", "playlist.m3u8");
    }

    try {
      if (nativeHls()) {
        vid.onloadstart = () => {
          clearTimeout(tvTimer);
          tvTimer = setTimeout(() => fin(bad, "timeout"), 12000);
        };
        vid.onloadedmetadata = () => {
          clearTimeout(tvTimer);
          fin(ok);
        };
        vid.src = streamTarget;
      }
      else {
        const Hls = await loadHlsLib();
        clearTimeout(tvTimer);
        tvTimer = setTimeout(() => fin(bad, "timeout"), _isSlow ? 5000 : 3500);
        if (!Hls.isSupported()) {
          vid.onloadstart = () => {
            clearTimeout(tvTimer);
            tvTimer = setTimeout(() => fin(bad, "timeout"), 12000);
          };
          vid.src = streamTarget;
        }
        else {
          hls = new Hls({
            enableWorker: true,
            startFragPrefetch: true,
            capLevelToPlayerSize: false,
            lowLatencyMode: false,
            liveSyncDurationCount: 2,
            liveMaxLatencyDurationCount: 5,
            maxBufferLength: 20,
            maxMaxBufferLength: 45,
            maxBufferHole: 0.5,
            maxBufferSize: 30 * 1024 * 1024,
            backBufferLength: 4,
            abrEwmaDefaultEstimate: _isSlow ? 1800000 : 2500000,
            testBandwidth: true,
            highBufferWatchdogPeriod: 1,
            nudgeOffset: 0.1,
            nudgeMaxRetry: 5,
            manifestLoadingTimeOut: 2000,
            manifestLoadingMaxRetry: 2,
            manifestLoadingRetryDelay: 500,
            levelLoadingTimeOut: 2000,
            levelLoadingMaxRetry: 2,
            levelLoadingRetryDelay: 500,
            fragLoadingTimeOut: 12000,
            fragLoadingMaxRetry: 3,
          });
          hls.on(Hls.Events.MANIFEST_LOADING, () => {
            clearTimeout(tvTimer);
            tvTimer = setTimeout(() => fin(bad, "manifest_timeout"), _isSlow ? 6000 : 4000);
          });
          let fallbackTried = false;
          let proxyTried = false;
          let netFatalRetries = 0;
          hls.on(Hls.Events.ERROR, (_, d) => {
            if (d.fatal) {
              if (!fallbackTried && streamTarget.includes("cinerama.uz")) {
                fallbackTried = true;
                const nextUrl = streamTarget.includes("tracks-v1a1")
                  ? streamTarget.replace("tracks-v1a1/mono.ts.m3u8", "playlist.m3u8").replace("tracks-v1a1/mono.m3u8", "playlist.m3u8")
                  : streamTarget.replace("playlist.m3u8", "tracks-v1a1/mono.ts.m3u8");
                if (nextUrl !== streamTarget) {
                  streamTarget = nextUrl;
                  try {
                    clearTimeout(tvTimer);
                    tvTimer = setTimeout(() => fin(bad, "timeout"), _isSlow ? 4500 : 3500);
                    hls.loadSource(streamTarget);
                    hls.startLoad();
                    return;
                  } catch (err) {}
                }
              }
              if (!proxyTried && !streamTarget.includes("/api/tv/stream")) {
                proxyTried = true;
                streamTarget = `/api/tv/stream?url=${encodeURIComponent(streamTarget)}`;
                try {
                  clearTimeout(tvTimer);
                  tvTimer = setTimeout(() => fin(bad, "timeout"), _isSlow ? 5000 : 4000);
                  hls.loadSource(streamTarget);
                  hls.startLoad();
                  return;
                } catch (err) {}
              }
              if (d.type === Hls.ErrorTypes.NETWORK_ERROR) {
                if (++netFatalRetries <= 2) {
                  try { hls.startLoad(); } catch (err) {}
                } else {
                  fin(bad, "network_fatal");
                }
              } else if (d.type === Hls.ErrorTypes.MEDIA_ERROR) {
                try { hls.recoverMediaError(); } catch (err) { fin(bad, d.type); }
              } else {
                fin(bad, d.type);
              }
            } else if (d.details === Hls.ErrorDetails.BUFFER_STALLED_ERROR) {
              try {
                if (vid.currentTime > 0) vid.currentTime += 0.1;
                if (vid.paused) vid.play().catch(() => {});
                if (hls && hls.currentLevel !== -1) {
                  hls.currentLevel = -1;
                }
              } catch (e) {}
            }
          });
          hls.on(Hls.Events.MANIFEST_LOADED, () => {
            clearTimeout(tvTimer);
            tvTimer = setTimeout(() => fin(bad, "buffer_timeout"), 12000);
          });
          hls.on(Hls.Events.FRAG_LOADED, () => {
            clearTimeout(tvTimer);
            tvTimer = setTimeout(() => fin(bad, "buffer_timeout"), 10000);
          });
          hls.on(Hls.Events.MANIFEST_PARSED, (_, data) => {
            clearTimeout(tvTimer);
            tvTimer = setTimeout(() => fin(bad, "buffer_timeout"), 12000);
            if (data && data.levels && data.levels.length > 0) {
              let targetIdx = data.levels.length - 1;
              let slowIdx = 0;
              let minFhdIdx = 0;
              for (let i = 0; i < data.levels.length; i++) {
                const h = data.levels[i].height || 0;
                if (h <= 720) slowIdx = i;
                if (h >= 1080 || h === 1440) {
                  if (minFhdIdx === 0) minFhdIdx = i;
                  targetIdx = i;
                }
              }
              hls.autoLevelCapping = -1;
              hls.startLevel = _isSlow ? slowIdx : slowIdx;
              hls.currentLevel = -1; // Adaptive, never lock!
              hls.minAutoLevel = 0;
            }
          });
          try {
            vid.style.filter = "contrast(1.06) saturate(1.05)";
            vid.style.webkitFilter = "contrast(1.06) saturate(1.05)";
            vid.style.imageRendering = "-webkit-optimize-contrast";
          } catch (e) {}
          hls.loadSource(streamTarget); hls.attachMedia(vid);
        }
      }
      vid.muted = false;
      vid.play().catch((err) => {
        if (err && err.name === "NotAllowedError") { vid.muted = true; $("unmute").hidden = false; vid.play().catch(() => {}); }
      });
    } catch (e) {
      if (url.includes("cinerama.uz")) {
        const altUrl = url.includes("tracks-v1a1")
          ? url.replace("tracks-v1a1/mono.ts.m3u8", "playlist.m3u8").replace("tracks-v1a1/mono.m3u8", "playlist.m3u8")
          : url.replace("playlist.m3u8", "tracks-v1a1/mono.ts.m3u8");
        if (altUrl !== url) {
          try {
            await attempt(altUrl);
            return;
          } catch (e2) {}
        }
      }
      fin(bad, "load");
    }
  });
}
let tvN = 0;
async function playTV(c, from = 0) {
  const my = ++tvTry;
  stopVideo(); tvState("load", "Efirga ulanmoqda…"); $("unmute").hidden = true;
  const streamList = Array.isArray(c.u) && c.u.length ? c.u : [[0, c.stream || c.u]];
  for (let n = from; n < streamList.length; n++) {
    const [idx, url] = streamList[n];
    tvN = n;
    if (n) tvState("load", `Zaxira efir sinalmoqda (${n + 1}/${streamList.length})…`);
    const emb = ytEmbed(url);
    if (emb) {
      vid.hidden = true; const yt = $("yt"); yt.hidden = false;
      yt.src = emb + (emb.includes("?") ? "&" : "?") + "autoplay=1&playsinline=1&rel=0&modestbranding=1";
      tvState("ok"); report(c, idx, true); return;
    }
    try {
      await attempt(url);
      if (my !== tvTry) return;
      tvState("ok"); report(c, idx, true); return;
    } catch (e) {
      if (my !== tvTry) return;
      report(c, idx, false);
      if (hls) { try { hls.destroy(); } catch (x) {} hls = null; }
    }
  }
  // Agar to'g'ridan-to'g'ri barcha manbalar ishlamasa, Bauntys proxy server orqali ulanish
  if (my === tvTry) {
    const primaryUrl = c.stream || (streamList[0] && streamList[0][1]);
    if (primaryUrl && !primaryUrl.includes("/api/tv/stream")) {
      const proxyUrl = `/api/tv/stream?url=${encodeURIComponent(primaryUrl)}`;
      try {
        tvState("load", "Tezkor zaxira orqali ulanmoqda…");
        await attempt(proxyUrl);
        if (my === tvTry) { tvState("ok"); report(c, 0, true); return; }
      } catch (e2) {}
    }
  }
  if (my === tvTry) { stopVideo(); tvState("err", "Bu kanal hozir efirda emas"); haptic("err"); }
}
function openTV(c, push = true) {
  tvCur = c; haptic();
  tvRec = [c.i, ...tvRec.filter((x) => x !== c.i)].slice(0, 20); lsSet("zk_tvrec", tvRec);
  $("tvname").innerHTML = `${esc(c.n)} <span class="badge-res">1440p QHD</span>`;
  $("tvlogo").innerHTML = logoHTML(c);
  $("tvfav").textContent = tvFav.includes(c.i) ? "⭐" : "☆";
  let same = (tvList.length ? tvList : tvItems).filter((x) => x.i !== c.i);
  if (same.length < 6) same = same.concat(tvItems.filter((x) => x.c === c.c && x.i !== c.i && !same.includes(x)));
  same = same.slice(0, 60);
  $("tvlist").innerHTML = same.map(tileHTML).join("");
  $("tvp").scrollTop = 0; $("tvp").classList.add("open");
  document.body.classList.add("tvp-open");
  if (inTg) { tg.BackButton.show(); tg.MainButton.hide(); } else $("tvx").style.display = "";
  if (push && !tvPushed) { history.pushState({tv: c.i}, ""); tvPushed = true; }
  playTV(c);
}
function closeTV(fromPop = false) {
  if (!tvCur) return;
  tvCur = null; tvTry++; stopVideo();
  $("tvp").classList.remove("open");
  document.body.classList.remove("tvp-open");
  if (inTg) tg.BackButton.hide();
  if (!fromPop && tvPushed) history.back();
  tvPushed = false;
  if (mode === "tv") renderTV();
}
function nextTV() {
  const l = tvList.length ? tvList : tvItems;
  const i = l.findIndex((x) => tvCur && x.i === tvCur.i);
  const n = l[(i + 1) % l.length];
  if (n) openTV(n, false);
}
$("vretry").onclick = () => tvCur && playTV(tvCur);
$("tvbad").onclick = () => {
  if (!tvCur) return;
  const c = tvCur, [idx] = c.u[tvN] || [0];
  report(c, idx, false, true); haptic("err");
  if (tvN + 1 < c.u.length) { toast("🙏 Rahmat! Boshqa efir sinalmoqda…", 1600); playTV(c, tvN + 1); }
  else { toast("🙏 Rahmat! Xabaringiz hisobga olindi", 1800); tvTry++; stopVideo(); tvState("err", "Bu kanalning boshqa efiri yo'q"); }
};
$("vnext").onclick = nextTV;
$("tvx").onclick = () => closeTV();
// 🗑 Admin: keraksiz kanalni shu yerning o'zidan o'chiradi (hamma uchun yo'qoladi)
let tvAdmin = false;
if (inTg) fetch("api/tv/me", {headers: {"X-Init-Data": tg.initData}}).then((r) => r.json())
  .then((r) => { tvAdmin = !!r.admin; $("tvdel").hidden = !tvAdmin; }).catch(() => {});
$("tvdel").onclick = () => {
  const c = tvCur;
  if (!c || !tvAdmin) return;
  const go = async () => {
    try {
      const r = await (await fetch("api/tv/hide", {method: "POST", headers: {"Content-Type": "application/json", "X-Init-Data": tg.initData},
        body: JSON.stringify({id: c.i})})).json();
      if (!r.ok) throw 0;
      tvItems = tvItems.filter((x) => x.i !== c.i); tvById.delete(c.i);
      closeTV(); tvChips(); $("count").textContent = `${tvItems.length} ta kanal · jonli efir`; renderTV();
      toast(`🗑 «${c.n}» o'chirildi`, 2000); haptic("ok");
    } catch (e) { toast("Kanalni o'chirib bo'lmadi", 2000); }
  };
  if (tg.showConfirm) tg.showConfirm(`«${c.n}» kanalini hamma uchun o'chirasizmi?\nQaytarish: botda /tvon ${c.n}`, (ok) => ok && go());
  else if (confirm(`«${c.n}» o'chirilsinmi?`)) go();
};
$("unmute").onclick = () => { vid.muted = false; $("unmute").hidden = true; vid.play().catch(() => {}); };
$("tvfav").onclick = () => {
  if (!tvCur) return;
  const id = tvCur.i;
  tvFav = tvFav.includes(id) ? tvFav.filter((x) => x !== id) : [id, ...tvFav];
  lsSet("zk_tvfav", tvFav); haptic();
  $("tvfav").textContent = tvFav.includes(id) ? "⭐" : "☆";
  toast(tvFav.includes(id) ? "⭐ Sevimlilarga qo'shildi" : "Sevimlilardan olib tashlandi", 1400);
};
$("tvfs").onclick = () => {
  const box = $("vbox");
  try {
    if (box.requestFullscreen) box.requestFullscreen().then(() => { try { screen.orientation.lock("landscape"); } catch (e) {} }).catch(() => vid.webkitEnterFullscreen && vid.webkitEnterFullscreen());
    else if (vid.webkitEnterFullscreen) vid.webkitEnterFullscreen();
  } catch (e) {}
};
document.addEventListener("click", (e) => {
  const hb = e.target.closest && e.target.closest('[data-act="homeback"], [data-a="homeback"]');
  if (hb) {
    if (window.ZK_setMode) window.ZK_setMode("kino");
    return;
  }
  const hub = e.target.closest && e.target.closest('[data-act="hub"], [data-a="hub"]');
  if (hub) {
    if (window.ZHub && window.ZHub.open) window.ZHub.open();
    return;
  }
  const t = e.target.closest("[data-tv]");
  if (!t) return;
  const rawId = t.dataset.tv;
  const c = tvById.get(rawId) || tvById.get(+rawId) || tvById.get(String(rawId)) || (tvItems && tvItems.find(x => String(x.i) === String(rawId) || String(x.id) === String(rawId)));
  if (!c) return;
  openTV(c, !tvCur);
});
if (inTg) tg.BackButton.onClick(() => { if (tvCur) closeTV(); });
document.addEventListener("visibilitychange", () => { if (document.hidden && tvCur) vid.pause(); });

// ---------- yuklash ----------
async function load() {
  skeleton();
  try {
    const r = await (await fetch("api/catalog", {cache: "no-cache"})).json();
    items = r.items || []; channel = r.channel || ""; botName = r.bot || "";
    tvSoon = !!r.tv_soon;
    ASIL = !!(r.asil && window.ZAsil);
    if (ASIL) {
      window.ZK_BOT = window.ZK_BOT || botName;
      channel = "";
      $("chips").innerHTML = ZAsil.chips();
    }
    if (!r.tv && !tvSoon) $("seg").querySelector('[data-m="tv"]')?.remove();  // TV vaqtincha o'chiq
    if (!r.music) $("seg").querySelector('[data-m="music"]')?.remove();
    if (!r.docs) $("seg").querySelector('[data-m="docs"]')?.remove();
    if (!r.games) $("seg").querySelector('[data-m="games"]')?.remove();
    if (!r.story) $("seg").querySelector('[data-m="story"]')?.remove();
    if (!r.books) $("seg").querySelector('[data-m="books"]')?.remove();
    if (!r.fx) $("seg").querySelector('[data-m="fx"]')?.remove();
    if (!r.food) $("seg").querySelector('[data-m="food"]')?.remove();
    if (!r.quiz) $("seg").querySelector('[data-m="quiz"]')?.remove();
    if (!r.prava) $("seg").querySelector('[data-m="prava"]')?.remove();
    window.ZK_SEGS = [...$("seg").querySelectorAll("button[data-m]")].map((b) => [b.dataset.m, b.textContent.replace(/^\S+\s/, "")]);
    // 3 va undan ko'p bo'lim — sig'ishi uchun belgilarsiz (🎬 🎧 📄) qisqa yozuv
    if (window.ZK_SEGS.length > 2) $("seg").querySelectorAll("button[data-m]").forEach((b) => { b.textContent = b.textContent.replace(/^\S+\s/, ""); });
    document.body.classList.toggle("seg4", window.ZK_SEGS.length > 3);   // 4 bo'lim — «Kanal» tugmasi o'rniga joy
    if (window.ZMusic) ZMusic.setBot(botName);
    if (window.ZDocs) ZDocs.setBot(botName);
    if (window.ZStory) ZStory.setBot(botName);
    if (window.ZBooks) ZBooks.setBot(botName);
    if (window.ZQuiz) ZQuiz.setBot(botName);
    if (window.ZK_SEGS.length < 2) $("seg").outerHTML = `<h1 style="font-size:21px;margin:0;font-weight:800;letter-spacing:-.3px">🎬 Kinolar</h1>`;
  } catch (e) {
    $("main").innerHTML = `<div class="empty"><div class="big">📶</div><b>Yuklab bo'lmadi</b>Internetni tekshiring.<br><br>
      <button class="cta" style="max-width:220px" onclick="location.reload()">🔄 Qayta urinish</button></div>`;
    $("count").textContent = "";
    return;
  }
  items.forEach((x) => { x._n = norm(x.t); x._k = x._n + " " + norm(x.d) + " " + x.c; byCode.set(x.c, x); });
  if (mode !== "kino") return;
  $("count").textContent = ASIL ? ZAsil.countText() : `${items.length} ta kino · posterini bosing`;
  $("chan").hidden = !channel;
  render();
  const _urlParams = new URLSearchParams(location.search);
  const sp = (tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param) || _urlParams.get("c") || _urlParams.get("movie") || _urlParams.get("m") || "";
  if (document.querySelector('#seg [data-m="games"]') && (/^games/i.test(sp) || new URLSearchParams(location.search).has("games"))) {
    const gid = sp.split("_")[1]; setMode("games"); if (gid && window.ZGames && ZGames.ids.includes(gid)) ZGames.open(gid); return; }
  const stq = new URLSearchParams(location.search).get("story");
  if (document.querySelector('#seg [data-m="story"]') && (/^st(ory)?(_|$)/i.test(sp) || stq !== null)) {
    setMode("story"); const spec = stq || sp.replace(/^st(ory)?_?/i, ""); if (spec && window.ZStory) ZStory.open(spec); return; }
  const bkq = new URLSearchParams(location.search).get("books");
  if (document.querySelector('#seg [data-m="books"]') && (/^(books|kitob)/i.test(sp) || bkq !== null)) {
    setMode("books"); const bid = (bkq || sp.replace(/^\D+_?/, "")).replace(/\D/g, ""); if (bid && window.ZBooks) ZBooks.open(bid); return; }
  const qzq = new URLSearchParams(location.search).get("quiz") || new URLSearchParams(location.search).get("qz");
  if (document.querySelector('#seg [data-m="quiz"]') && (/^(q\d{6}|qz\d+|quiz)/i.test(sp) || qzq !== null)) {
    setMode("quiz");
    const rawQ = qzq || sp;
    const cleanQ = String(rawQ || "").replace(/^quiz_/i, "").replace(/^qz_/i, "").replace(/^q_/i, "");
    if (cleanQ && cleanQ !== "1" && window.ZQuiz) ZQuiz.start(cleanQ);
    return;
  }
  const pvq = new URLSearchParams(location.search).get("prava");
  if (document.querySelector('#seg [data-m="prava"]') && (/^(prava|avto)/i.test(sp) || pvq !== null)) {
    setMode("prava"); if ((pvq === "exam" || /exam|imtihon/i.test(sp)) && window.ZPrava) ZPrava.start("exam"); return; }
  const fdq = new URLSearchParams(location.search).get("food");
  if (document.querySelector('#seg [data-m="food"]') && (/^(food|taom)/i.test(sp) || fdq !== null)) {
    setMode("food"); const rid = (fdq || sp.replace(/^\D+_?/, "")).replace(/\D/g, ""); if (rid && window.ZFood) ZFood.show(rid); return; }
  if (document.querySelector('#seg [data-m="fx"]') && (/^(fx|kurs)/i.test(sp) || new URLSearchParams(location.search).has("fx"))) { setMode("fx"); return; }
  if (document.querySelector('#seg [data-m="docs"]') && (/^docs/i.test(sp) || new URLSearchParams(location.search).has("docs"))) { setMode("docs"); return; }
  if (document.querySelector('#seg [data-m="music"]') && (/^(music|m$|m_)/i.test(sp) || new URLSearchParams(location.search).has("music"))) {
    setMode("music"); const mq = new URLSearchParams(location.search).get("q"); if (mq && window.ZMusic) ZMusic.search(mq); return; }
  if (document.querySelector('#seg [data-m="tvroom"]') && (/^(tvroom|tvxona|tvr_|tv_)/i.test(sp) || new URLSearchParams(location.search).has("tvroom") || new URLSearchParams(location.search).has("tvxona") || (new URLSearchParams(location.search).get("m") === "tvroom"))) {
    setMode("tvroom");
    const m_tv = String(sp).match(/^(?:tvroom_|tvxona_|tvr_|tv_)([a-zA-Z0-9_]+)$/i);
    const roomParam = new URLSearchParams(location.search).get("room") || (m_tv ? m_tv[1] : "");
    if (roomParam && !["tvroom", "tvxona", "main"].includes(roomParam.toLowerCase()) && window.ZTvRoom) {
      ZTvRoom.join(roomParam);
    }
    return;
  }
  if (document.querySelector('#seg [data-m="tv"]') && (/^tv($|_channel)/i.test(sp) || new URLSearchParams(location.search).has("tv") || (new URLSearchParams(location.search).get("m") === "tv"))) { setMode("tv"); return; }
  if (document.querySelector('#seg [data-m="rasxod"]') && (/^rasxod/i.test(sp) || new URLSearchParams(location.search).has("rasxod"))) { setMode("rasxod"); return; }
  if (document.querySelector('#seg [data-m="kal"]') && (/^(kal|kaloriya)/i.test(sp) || new URLSearchParams(location.search).has("kal"))) { setMode("kal"); return; }
  const _search = new URLSearchParams(location.search);
  const _mParam = _search.get("m");
  if (document.querySelector('#seg [data-m="mafia"]') && (/^(mafia|maf_)/i.test(sp) || _mParam === "mafia" || _search.has("mafia"))) {
    setMode("mafia");
    const mc = String(sp).match(/^(?:maf_|mafia_)?([a-zA-Z0-9]{3,10})$/i);
    const roomParam = _search.get("room") || _search.get("code") || (mc ? mc[1] : "");
    if (roomParam && window.ZMafia) ZMafia.join(roomParam);
    return;
  }
  if (/^(reklama|ads)/i.test(sp) || new URLSearchParams(location.search).has("reklama")) { ZHub.ads(); return; }
  const code = +String(sp).replace(/\D/g, "");
  const aq = new URLSearchParams(location.search).get("asil");
  if (ASIL && (aq || (/^(asil_|kino_)?\d+$/i.test(sp) && code))) { ZAsil.open(+(aq || code)); return; }
  if (code && byCode.has(code)) { openDetail(byCode.get(code), false); return; }
  const yq = _urlParams.get("year");
  const actq = _urlParams.get("actor");
  const qq = _urlParams.get("q");
  if (yq || actq || qq) {
    const searchVal = qq || actq || yq;
    if ($("q")) { $("q").value = searchVal; }
    query = searchVal;
    if ($("sbox")) $("sbox").classList.add("has");
    render();
    return;
  }
  if (!sp && !location.search.replace(/^\?/, "").split("&").some((x) => x && !/^(tgWebApp|nosplash)/.test(x))) ZHub.open("");
}
// ---------- 🔒 majburiy obuna: kanal(lar)ga a'zo bo'lmaguncha ilova yopiq ----------
const subGate = (() => {
  let el = null, busy = false, chans = [];
  const css = `#zkgate{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px;
    background:rgba(6,9,22,.94);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);color:#F6EEDC;font-family:Man,-apple-system,sans-serif}
    #zkgate .b{width:100%;max-width:400px;text-align:center}
    #zkgate .i{font-size:54px;line-height:1}#zkgate h2{margin:14px 0 6px;font:800 22px/1.2 Unb,-apple-system,sans-serif}
    #zkgate p{margin:0 0 18px;color:rgba(246,238,220,.68);font:500 14.5px/1.45 Man,sans-serif}
    #zkgate .ch{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:56px;margin-bottom:10px;padding:0 16px;
      border-radius:16px;border:0;background:rgba(246,238,220,.09);box-shadow:inset 0 0 0 1px rgba(246,238,220,.16);color:inherit;font:800 15px Man,sans-serif;cursor:pointer}
    #zkgate .ch em{font-style:normal;color:#F2B84B;font-size:13px}
    #zkgate .ok{width:100%;height:56px;margin-top:6px;border-radius:18px;border:0;background:#F2B84B;color:#2A1500;font:800 16px Man,sans-serif;cursor:pointer}
    #zkgate .ok:disabled{opacity:.6}`;
  function render(msg) {
    if (!el) {
      const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
      el = document.createElement("div"); el.id = "zkgate"; document.body.appendChild(el);
      el.addEventListener("click", (e) => {
        const c = e.target.closest("[data-ch]");
        if (c) { const u = chans[+c.dataset.ch].url; try { /^https:\/\/t\.me\//.test(u) ? tg.openTelegramLink(u) : tg.openLink(u); } catch (err) { location.href = u; } return; }
        if (e.target.closest(".ok")) check(true);
      });
    }
    el.innerHTML = `<div class="b"><div class="i">🔒</div><h2>Bir qadam qoldi</h2>
      <p>${msg || "Ilovadan foydalanish uchun kanal(lar)imizga a'zo bo'ling, so'ng «Tekshirish» ni bosing."}</p>
      ${chans.map((c, i) => `<button class="ch" data-ch="${i}"><span>📢 ${esc(c.title)}</span><em>A'zo bo'lish ›</em></button>`).join("")}
      <button class="ok">✅ A'zo bo'ldim — tekshirish</button></div>`;
    el.hidden = false;
    try { if (window.ZMusic) ZMusic.pause(); } catch (e) {}
  }
  async function check(force) {
    if (!inTg || busy) return;
    busy = true;
    const btn = el && el.querySelector(".ok"); if (btn) { btn.disabled = true; btn.textContent = "Tekshirilmoqda…"; }
    try {
      const r = await (await fetch("api/sub" + (force ? "?recheck=1" : ""), {cache: "no-store", headers: {"X-Init-Data": tg.initData}})).json();
      if (r && r.ok && !r.sub) { chans = r.channels || []; render(force ? "Hali a'zo bo'lmagansiz. Kanalga kiring, «Qo'shilish»ni bosing va qaytib keling." : ""); }
      else if (r && r.ok && el) { el.hidden = true; if (force) { try { tg.HapticFeedback.notificationOccurred("success"); } catch (e) {} } }
    } catch (e) { if (btn) { btn.disabled = false; btn.textContent = "✅ A'zo bo'ldim — tekshirish"; } }
    busy = false;
  }
  // kanalga o'tib qaytganda — avtomatik qayta tekshiramiz
  document.addEventListener("visibilitychange", () => { if (!document.hidden && el && !el.hidden) check(true); });
  // istalgan API «need_sub» qaytarsa (masalan, kanaldan chiqib ketgan bo'lsa) — darhol yopamiz
  const _f = window.fetch;
  window.fetch = function () {
    return _f.apply(this, arguments).then((resp) => { if (resp.status === 403 && (!el || el.hidden)) check(false); return resp; });
  };
  return {check};
})();
subGate.check(false);

// ---------- 🧭 Bosh ekran: hamma bo'limlar bir joyda + «☰ Bo'limlar» tugmasi + ko'rinish (✨ Kreativ / ⚡ Oddiy) ----------
const ZHub = (() => {
  const META = {
    kino: ["Kinolar", "Kodi bilan, posterlar", "🎬", "#E0465A,#7A1430"], music: ["Musiqa", "Top va qidiruv", "🎧", "#1FA8AE,#1B4FC9"],
    books: ["Kitoblar", "Audio ham bor", "📚", "#3D5BFF,#1A2780"], games: ["O'yinlar", "Bolalar uchun", "🧸", "#FF8A1F,#C2410C"],
    story: ["Story", "Anonim ko'rish", "👻", "#9B6BFF,#5B21B6"], docs: ["Hujjatlar", "PDF, tarjima", "📄", "#1F8C9E,#0E4F5A"],
    quiz: ["Viktorina", "Do'stlar bilan", "🧠", "#7C6CFF,#3B2BA8"], prava: ["Prava", "1235 savol", "🚗", "#E8A51F,#7A5200"],
    food: ["Taomlar", "Bugun nima?", "🍲", "#FF6B4A,#A3251A"], fx: ["Kurs", "Dollar, rubl", "💱", "#22B07D,#0B5E44"],
    tv: ["TV", "Jonli efir", "📺", "#6650D8,#2C1F7A"],
    tvroom: ["Tv Xona", "Do'stlar bilan TV", "📺", "#8B5CF6,#4C1D95"],
    mafia: ["Mafia", "Onlayn o'yin (3–20 kishi)", "🕵️", "#C21E2C,#1E1014"],
    rasxod: ["Rasxod", "Xarajatlar daftari", "💰", "#27AE60,#145A32"],
    kal: ["Kaloriya", "Kunlik kkal va vazn", "🥗", "#E67E22,#935116"],
  };
  const NEW = new Set(["prava", "tvroom"]);
  const SEG = "#seg";
  let el = null, open_ = false, from = "", don = null, ad = null, page = "";
  const live = {}, liveAt = {};
  const lite = () => !!window.ZK_LITE;
  // qaysi bo'lim qancha ishlatilgani — «Tez kirish» qatori shundan (faqat shu telefonda saqlanadi)
  const useGet = () => { try { return JSON.parse(localStorage.getItem("zk_use") || "{}") || {}; } catch (e) { return {}; } };
  function used(m) {
    if (!META[m]) return;
    const u = useGet(); u[m] = (u[m] || 0) + 1;
    try { localStorage.setItem("zk_use", JSON.stringify(u)); } catch (e) {}
  }
  function quick() {
    const u = useGet(), have = new Set(segs());
    return Object.keys(u).filter((m) => have.has(m) && u[m] >= 2).sort((a, b) => u[b] - u[a]).slice(0, 4);
  }
  // kartochkalarda jonli ma'lumot: kinolar soni, hozir chalayotgan qo'shiq, prava foizi, dollar kursi
  async function refreshLive() {
    const now = Date.now();
    try { if (items && items.length) live.kino = `${items.length} ta kino`; } catch (e) {}
    try { const t = window.ZMusic && ZMusic.nowTitle && ZMusic.nowTitle(); live.music = t ? `▶ ${t}` : ""; } catch (e) {}
    const jobs = [];
    if (segs().includes("prava") && inTg && !(now - (liveAt.prava || 0) < 60000)) {
      liveAt.prava = now;
      jobs.push(fetch("api/prava/home", {headers: {"X-Init-Data": tg.initData}}).then((r) => r.json()).then((h) => {
        if (h && h.ok && h.total) live.prava = h.solved ? `${Math.round(h.solved / h.total * 100)}% o'rganildi` : "1235 savol";
      }).catch(() => {}));
    }
    if (segs().includes("fx") && !(now - (liveAt.fx || 0) < 300000)) {
      liveAt.fx = now;
      jobs.push(fetch("api/fx").then((r) => r.json()).then((h) => {
        const u = h && (h.items || []).find((x) => x.c === "USD");
        if (u && u.r) live.fx = `$1 = ${String(Math.round(u.r)).replace(/\B(?=(\d{3})+(?!\d))/g, " ")} so'm`;
      }).catch(() => {}));
    }
    if (!(now - (liveAt.ad || 0) < 60000)) { liveAt.ad = now; loadAd(); }
    if (jobs.length) { await Promise.all(jobs); if (open_ && !page && window.ZK_UI_CHOSEN) render(); }
  }
  const segs = () => (window.ZK_SEGS && window.ZK_SEGS.length ? window.ZK_SEGS.map((x) => x[0]) : Object.keys(META)).filter((m) => META[m]);
  const name = () => { try { return (tg.initDataUnsafe.user.first_name || "").slice(0, 24); } catch (e) { return ""; } };
  function modeToggle() {
    return `<div class="hb-mode" role="group" aria-label="Ko'rinish"><button data-ui="kr" class="${lite() ? "" : "on"}">✨ Kreativ</button><button data-ui="lite" class="${lite() ? "on" : ""}">⚡ Oddiy</button></div>`;
  }
  function tiles() {
    const list = segs();
    return list.map((m, i) => {
      const [t, sub, emo, grad] = META[m];
      const g = grad.split(",");
      const here = from && from === m;
      return `<button class="hb-t${i === 0 && !lite() && list.length % 3 === 2 ? " wide" : ""}${here ? " here" : ""}" data-go="${m}" style="--g1:${g[0]};--g2:${g[1]}">
        <span class="ic" data-mode-ic="${m}"><em>${emo}</em></span><span class="tx"><b>${t}</b><small>${esc(live[m] || sub)}</small></span>${here ? '<span class="nw hr">Shu yerdasiz</span>' : NEW.has(m) ? '<span class="nw">YANGI</span>' : ""}</button>`;
    }).join("") + (don ? `<button class="hb-t don" data-act="don" style="--g1:#F2B84B;--g2:#B7791F"><span class="ic"><em>💛</em></span><span class="tx"><b>Donat</b><small>Botni qo'llab-quvvatlash</small></span></button>` : "");
  }
  function render() {
    if (!el) return;
    const playing = window.ZMusic && ZMusic._now && ZMusic._now();
    const q = quick();
    const qrow = q.length >= 2 ? `<div class="hb-lh">⚡ Tez kirish</div><div class="hb-quick">${q.map((m) => {
      const [t, sub, emo, grad] = META[m]; const g = grad.split(",");
      return `<button data-go="${m}" class="${from === m ? "here" : ""}" style="--g1:${g[0]};--g2:${g[1]}"><em>${emo}</em><b>${t}</b><small>${esc(live[m] || sub)}</small></button>`;
    }).join("")}</div><div class="hb-lh">Barcha bo'limlar</div>` : "";
    el.innerHTML = `${from ? '<div class="hb-grab" aria-hidden="true"><i></i></div>' : ""}<div class="hb-in">
      <div class="hb-head">${from ? `<button class="hb-x" data-act="close" aria-label="Yopish">✕</button>` : ""}
        <div class="hb-hi">${from ? "<b>Bo'limlar</b><small>Pastga surib yoping</small>" : `<b>Salom${name() ? ", " + esc(name()) : ""} 👋</b><small>Hamma bo'limlar shu yerda — tanlang</small>`}</div>${modeToggle()}</div>
      ${qrow}<div class="hb-grid">${tiles()}</div>${adCard()}
      ${playing ? `<button class="hb-cont" data-go="music"><span>🎧</span><span><b>Musiqa davom etmoqda</b><small>Pleyerga qaytish</small></span><em>›</em></button>` : ""}
      </div>`;
  }
  // 📣 Reklama: bosh ekranda karta + alohida sahifa (obunachilar soni — botning haqiqiy soni)
  const num = (n) => String(Math.max(0, n | 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  function adCard() {
    if (!ad || !ad.on) return "";
    return `<button class="hb-ad" data-act="ad"><span class="ic">📣</span><span><b>Reklama berish</b><small>${num(ad.users)} obunachiga e'loningiz</small></span><em>›</em></button>`;
  }
  function adPage() {
    page = "ad";
    const u = ad.user ? esc(ad.user) : "", ph = esc(ad.phone || "");
    const ini = (ad.user || "R").replace(/[^A-Za-z]/g, "").slice(0, 2).toUpperCase() || "R";
    el.innerHTML = `<div class="hb-in hb-adp">
      <div class="hb-head"><button class="hb-x" data-act="adback" aria-label="Orqaga">‹</button><div class="hb-hi"><b>Reklama</b></div></div>
      <div class="ad-hero"><h2>E'loningizni ${num(ad.users)} odam ko'rsin</h2>
        <p>Bot, Mini App va kanallarimiz orqali — kino, musiqa va o'yin ishqibozlariga.</p>
        <div class="ad-n"><b>${num(ad.users)}</b><small>bot obunachisi · har daqiqa yangilanadi</small></div></div>
      <div class="hb-lh">Reklama turlari</div>
      <div class="ad-fm">${(ad.formats || []).map((f) => `<div><i>${f.ic}</i><b>${esc(f.t)}</b><small>${esc(f.s)}</small></div>`).join("")}</div>
      <div class="ad-ct"><div class="who"><span class="av">${esc(ini)}</span><span><b>Reklama menejeri</b>${u ? `<small>@${u}</small>` : ""}<em>${esc(ad.hours || "")}</em></span></div>
        ${u ? `<button class="ad-b tgb" data-act="adtg"><span>✈️ Telegramda yozish</span><small>@${u}</small></button>` : ""}
        ${ph ? `<a class="ad-b call" href="tel:${ph}"><span>📞 Qo'ng'iroq qilish</span><small>${esc(ad.phone_fmt || ph)}</small></a>
        <button class="ad-cp" data-act="adcp">📋 Raqamni nusxalash</button>` : ""}</div></div>`;
    el.scrollTop = 0;
  }
  function loadAd(cb) {
    fetch("api/reklama").then((r) => r.json()).then((d) => { ad = d && d.ok ? d : null; if (cb) cb(); else if (open_ && !page && window.ZK_UI_CHOSEN) render(); }).catch(() => {});
  }
  function ads() {
    open("");
    if (ad && ad.on) adPage(); else loadAd(() => { if (ad && ad.on && open_) adPage(); });
  }
  function mount() {
    if (el) return;
    el = document.createElement("section");
    el.id = "zkhub"; el.className = "hb"; el.hidden = true;
    document.body.appendChild(el);
    // varaq rejimida: tashqariga (qorong'i fonga) bosish yoki pastga surish — yopadi
    let y0 = null, dy = 0;
    el.addEventListener("touchstart", (e) => {
      if (!el.classList.contains("hb-sheet")) return;
      const inner = el.querySelector(".hb-in");
      y0 = (inner && inner.scrollTop > 0 && !e.target.closest(".hb-grab,.hb-head")) ? null : e.touches[0].clientY; dy = 0;
    }, {passive: true});
    el.addEventListener("touchmove", (e) => {
      if (y0 == null) return;
      dy = Math.max(0, e.touches[0].clientY - y0);
      el.style.setProperty("--drag", dy + "px");
    }, {passive: true});
    el.addEventListener("touchend", () => {
      if (y0 == null) return;
      y0 = null; el.style.setProperty("--drag", "0px");
      if (dy > 90) { haptic(); close(); }
    });
    el.addEventListener("click", (e) => {
      const t = e.target;
      if (t === el && el.classList.contains("hb-sheet")) { close(); return; }
      const g = t.closest("[data-go]");
      if (g) { close(); haptic(); if (window.ZK_setMode) ZK_setMode(g.dataset.go); return; }
      const u = t.closest("[data-ui]");
      if (u) { setUI(u.dataset.ui); return; }
      const a = t.closest("[data-act]");
      if (a && a.dataset.act === "close") close();
      if (a && a.dataset.act === "don") donSheet();
      if (a && a.dataset.act === "ad" && ad) { haptic(); adPage(); return; }
      if (a && a.dataset.act === "adback") { haptic(); page = ""; if (window.ZK_UI_CHOSEN) render(); else picker(); return; }
      if (a && a.dataset.act === "adtg" && ad && ad.user) { haptic(); const url = "https://t.me/" + ad.user; try { tg.openTelegramLink(url); } catch (e2) { location.href = url; } return; }
      if (a && a.dataset.act === "adcp" && ad) {
        try { navigator.clipboard.writeText(ad.phone).then(() => { a.textContent = "✓ Nusxalandi"; }); } catch (e2) {}
        return;
      }
      const pk = t.closest("[data-pick]");
      if (pk) { el.querySelectorAll("[data-pick]").forEach((x) => x.classList.toggle("on", x === pk)); return; }
      if (t.closest("[data-pickgo]")) { const on = el.querySelector("[data-pick].on"); setUI(on ? on.dataset.pick : (lite() ? "lite" : "kr"), true); }
    });
  }
  function setUI(v, fromPicker) {
    try { localStorage.setItem("zk_ui", v); } catch (e) {}
    const want = (v === "lite" || v === "classic" || v === "oddy" || v === "oddiy");
    if (want !== lite()) {
      window.ZK_LITE = want;
      haptic();
      location.reload();
      return;
    }
    if (fromPicker) { window.ZK_UI_CHOSEN = true; render(); }
  }
  function picker() {
    const weakNote = window.ZK_WEAK ? "Telefoningiz uchun ⚡ Oddiy tavsiya qilinadi" : "Telefon sekin ishlasa — ⚡ Oddiy'ni tanlang";
    el.innerHTML = `<div class="hb-in hb-pick"><h2>Qaysi ko'rinish<br>sizga qulay?</h2>
      <p>Keyin «☰ Bo'limlar» orqali istalgan vaqt almashtirasiz.</p>
      <button class="opt${lite() ? "" : " on"}" data-pick="kr"><span class="pv k"><i></i><i></i><i></i></span><span><b>✨ Kreativ</b><small>Jonli fon, animatsiyalar, chiroyli effektlar</small><em>Yangi telefonlar uchun</em></span></button>
      <button class="opt${lite() ? " on" : ""}" data-pick="lite"><span class="pv o"><i></i><i></i><i></i></span><span><b>⚡ Oddiy</b><small>Yengil va tez, batareyani tejaydi</small><em>Eski / sekin telefonlar uchun</em></span></button>
      <button class="go" data-pickgo="1">Davom etish</button><div class="note">${weakNote}</div></div>`;
  }
  function open(fromMode) {
    mount();
    from = fromMode || ""; page = "";
    el.classList.toggle("hb-sheet", !!from);
    if (!window.ZK_UI_CHOSEN) picker(); else render();
    el.hidden = false; open_ = true;
    if (from && !lite()) { el.classList.remove("in"); void el.offsetWidth; el.classList.add("in"); }
    refreshLive();
    document.body.classList.add("hb-on");
    el.scrollTop = 0;
  }
  function close() {
    if (!el) return;
    el.hidden = true; open_ = false;
    document.body.classList.remove("hb-on");
  }
  // har bir bo'lim panelining boshiga «☰ Bo'limlar» tugmasi (bo'limlar o'zi chizadi — kuzatib qo'shamiz)
  const ICO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>';
  function addBtns() {
    document.querySelectorAll(SEG).forEach((sg) => {
      if (sg.querySelector(":scope>.zk-hubbtn")) return;
      const b = document.createElement("button");
      b.type = "button"; b.className = "zk-hubbtn"; b.setAttribute("aria-label", "Barcha bo'limlar");
      b.innerHTML = ICO + "<span>Bo'limlar</span>";
      b.addEventListener("click", (e) => { e.stopPropagation(); haptic(); open(document.body.dataset.zkm || "kino"); });
      sg.insertBefore(b, sg.firstChild);
    });
  }
  let q = false;
  new MutationObserver(() => { if (q) return; q = true; requestAnimationFrame(() => { q = false; addBtns(); }); })
    .observe(document.body, {childList: true, subtree: true});
  addBtns();
  document.addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest(".zk-hubbtn");
    if (b) { e.stopPropagation(); haptic(); open(document.body.dataset.zkm || "kino"); }
  });
  // ⚡ Oddiy rejimda donat — bosh ekrandagi karta orqali (Kreativ'da zk.js tepada tugma ko'rsatadi)
  if (lite()) fetch("api/donate").then((r) => r.json()).then((d) => { if (d && d.on && (d.num || (d.cards && d.cards.length))) { don = d; if (open_ && !page && window.ZK_UI_CHOSEN) render(); } }).catch(() => {});
  function donSheet() {
    const cards = don.cards && don.cards.length ? don.cards : [{num: don.num, name: don.name, net: don.net}];
    $("sheet").innerHTML = `<h3>💛 Botni qo'llab-quvvatlash</h3><p>${esc(don.text || "Har bir yordam bot rivojiga ketadi.")}</p>
      ${cards.map((c, i) => `<button class="sbtn" data-cp="${i}"><span>💳 ${esc(String(c.num || "").replace(/(\d{4})(?=\d)/g, "$1 "))}</span><span>${esc(c.name || "")} · nusxa</span></button>`).join("")}`;
    $("sheet").querySelectorAll("[data-cp]").forEach((b) => b.onclick = () => {
      const n = String(cards[+b.dataset.cp].num || "").replace(/\s/g, "");
      try { navigator.clipboard.writeText(n).then(() => { b.lastElementChild.textContent = "✓ Nusxalandi"; }); } catch (e) {}
    });
    close();
    $("sbg").classList.add("open"); $("sheet").classList.add("open");
  }
  return {open, close, used, ads, isOpen: () => open_};
})();
window.ZHub = ZHub;

load();
})();
