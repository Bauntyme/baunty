/* 💸 Rasxod — kunlik xarajatlar daftari (Mini App).
   index.html dan window.ZRasxod orqali boshqariladi (open / close / busy / start).
   Matn serverda ajratiladi (/api/rasxod/add — «non 8 ming, taksi 25000»), ovoz — o'z serverimizdagi Whisper
   — faqat matn. Har kimning xarajati faqat o'ziga ko'rinadi (Telegram initData). */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const fmt = (n) => String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
const short = (n) => n >= 1e6 ? (Math.round(n / 1e4) / 100).toString().replace(".", ",") + " mln" : n >= 1e4 ? Math.round(n / 1000) + " ming" : fmt(n);
const _T = window.ZK_T || ((u) => u);
const OY = _T(["", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktabr", "noyabr", "dekabr"],
  ["", "январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"],
  ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]);
const HAFTA = _T(["Ya", "Du", "Se", "Ch", "Pa", "Ju", "Sh"], ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"], ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]);
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const ICO = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>',
  next: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m9 5 7 7-7 7"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg>',
};

let opened = false, mounted = false, home = null, meta = {}, ym = null, busy = false;
const stack = [{v: "home"}];
const top = () => stack[stack.length - 1];

async function api(path, body, raw) {
  try {
    const r = await fetch(path, {method: body ? "POST" : "GET", cache: "no-store",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body && !raw ? {"Content-Type": "application/json"} : {}, raw ? {"Content-Type": raw} : {}),
      body: body ? (raw ? body : JSON.stringify(body)) : undefined});
    if (r.status === 401) return {ok: false, error: "Ilovani bot ichida oching"};
    if (r.status === 429) return {ok: false, error: "Juda ko'p so'rov — biroz kuting"};
    if (r.status === 413) return {ok: false, error: "Ovoz juda uzun — 1 daqiqagacha"};
    if (r.status >= 500) return {ok: false, error: "Server band — biroz kuting"};
    return await r.json();
  } catch (e) { return {ok: false, error: "Internet aloqasini tekshiring"}; }
}
const ERR = {no_amount: "Summani topa olmadim. Masalan: «non 8 ming, taksi 25000»", income: "Bu daromadga o'xshaydi — daftar faqat xarajatlarni hisoblaydi",
  limit: "Bugun juda ko'p yozuv qo'shildi"};
const toast = (t, long) => { const el = document.createElement("div"); el.className = "rx-toast"; el.innerHTML = t; $("rasxod").appendChild(el); setTimeout(() => el.remove(), long ? 4200 : 2600); };
const ymStr = () => `${ym[0]}-${String(ym[1]).padStart(2, "0")}`;
const isCur = () => { const d = new Date(Date.now() + (new Date().getTimezoneOffset() + 300) * 60000); return ym[0] === d.getFullYear() && ym[1] === d.getMonth() + 1; };
const cat = (c) => meta[c] || {e: "📦", n: "Boshqa", col: "#9AA0B4"};
function dayName(iso) {
  const t = home && home.today_iso, d = new Date(iso + "T00:00:00");
  if (iso === t) return "Bugun";
  const y = new Date(t + "T00:00:00"); y.setDate(y.getDate() - 1);
  if (d.getTime() === y.getTime()) return "Kecha";
  return `${d.getDate()}-${OY[d.getMonth() + 1]}, ${HAFTA[d.getDay()]}`;
}
function segHtml() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["rasxod", "Rasxod"]];
  return `<div class="rx-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "rasxod" ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`;
}
function head(title, right) {
  return `<div class="rx-head"><button class="rx-back" data-act="back" aria-label="Orqaga">${ICO.back}</button><b>${title}</b>${right || ""}</div>`;
}

// ------------------------------------------------------------------ 🏠 bosh sahifa
function donut(cats, total) {
  let acc = 0;
  const stops = cats.map((c) => { const a = acc; acc += c.s / total * 100; return `${c.col} ${a.toFixed(2)}% ${acc.toFixed(2)}%`; }).join(",");
  const legend = cats.slice(0, 5).map((c) => `<div><i style="background:${c.col}"></i>${esc(c.n)}<em>${c.p}%</em></div>`).join("")
    + (cats.length > 5 ? `<div><i style="background:#9AA0B4"></i>Qolganlari<em>${100 - cats.slice(0, 5).reduce((s, c) => s + c.p, 0)}%</em></div>` : "");
  return `<div class="rx-donut"><div class="dn" style="background:conic-gradient(${stops})"><span><small>${OY[ym[1]]}</small><b>${short(total)}</b></span></div><div class="lg">${legend}</div></div>`;
}
function catRows(cats) {
  const max = cats.length ? cats[0].s : 1;
  return cats.map((c) => `<button class="rx-cat" data-cat="${c.c}"><span class="e" style="background:${c.col}24">${c.e}</span><span class="m"><b>${esc(c.n)}<span>${fmt(c.s)}</span></b>
    <small>${c.p}% · ${c.k} ta yozuv${c.prev ? ` · o'tgan oy ${short(c.prev)}` : ""}</small><span class="tr"><i style="width:${Math.max(3, c.s / max * 100)}%;background:${c.col}"></i></span></span></button>`).join("");
}
function viewHome() {
  const h = home;
  const bar = `<div class="rx-bar">${segHtml()}</div>`;
  if (!h) return bar + `<div class="rx-load"><i></i><i></i><i></i></div>`;
  const cur = h.cur;
  const mon = `<div class="rx-mon"><button data-act="mprev" aria-label="Oldingi oy">${ICO.back}</button><span>${cap(OY[h.m])} ${h.y}</span><button data-act="mnext" aria-label="Keyingi oy" ${cur ? "disabled" : ""}>${ICO.next}</button></div>`;
  let budget = "";
  if (h.budget) {
    const pct = Math.min(100, h.total / h.budget * 100), left = h.budget - h.total;
    budget = `<div class="rx-bud ${left < 0 ? "over" : pct > 85 ? "warn" : ""}"><i style="width:${pct}%"></i></div>
      <div class="rx-bl"><button data-act="budget">Byudjet ${fmt(h.budget)} ✎</button><span>${left >= 0 ? `Qoldi ${fmt(left)}` : `${fmt(-left)} oshdi`}</span></div>`;
  } else if (cur) budget = `<button class="rx-setbud" data-act="budget">💰 Oylik byudjet qo'yish</button>`;
  const ch = h.change == null ? "—" : `${h.change > 0 ? "+" : ""}${h.change}%`;
  const kp = `<div class="rx-kp">${cur ? `<div><b>${fmt(h.today)}</b><small>bugun</small></div>` : `<div><b>${h.n}</b><small>yozuv</small></div>`}
    <div><b>${fmt(h.avg)}</b><small>kunlik o'rtacha</small></div><div><b class="${h.change > 0 ? "up" : h.change < 0 ? "dw" : ""}">${ch}</b><small>o'tgan oyga nisbatan</small></div></div>`;
  const tot = `<div class="rx-tot"><small>${cur ? `${cap(OY[h.m])}, ${h.days} kunda` : `${cap(OY[h.m])} ${h.y} — jami`}</small>
    <div class="big">${fmt(h.total)} <span>so'm</span></div>${budget}${kp}</div>`;
  if (!h.total) {
    return bar + mon + tot + `<div class="rx-empty"><div class="em">💸</div><b>${cur ? "Birinchi xarajatni yozing" : "Bu oyda xarajat yozilmagan"}</b>
      ${cur ? `<p>Pastdagi qatorga oddiy qilib yozing — summani va turini o'zim ajrataman:</p>
      <div class="ex"><button data-ex="non 8 ming, taksi 25000">non 8 ming, taksi 25000</button><button data-ex="obedga 45 ming ketdi">obedga 45 ming ketdi</button><button data-ex="kecha svetga 120 ming">kecha svetga 120 ming</button></div>` : ""}</div>`;
  }
  return bar + mon + tot + donut(h.cats, h.total)
    + `<div class="rx-lh"><span>Turlari bo'yicha</span><button data-act="hist">Hammasi ›</button></div>${catRows(h.cats)}`
    + (h.advice ? `<div class="rx-tip">${esc(h.advice)}</div>` : "")
    + `<div class="rx-two"><button data-act="report">🗓 Oy hisoboti</button><button data-act="hist">📜 Tarix</button></div>`;
}

// ------------------------------------------------------------------ 🗓 oy hisoboti
function viewReport() {
  const h = home;
  if (!h) return head("Hisobot") + `<div class="rx-load"><i></i><i></i><i></i></div>`;
  const max = h.cats.length ? h.cats[0].s : 1;
  const days = Object.keys(h.by_day).sort();
  const dmax = Math.max(1, ...days.map((d) => h.by_day[d]));
  const avg = h.avg;
  const nd = new Date(h.y, h.m, 0).getDate(), lastDay = h.cur ? new Date(h.today_iso + "T00:00:00").getDate() : nd;
  let cols = "";
  for (let i = 1; i <= nd; i++) {
    const iso = `${h.y}-${String(h.m).padStart(2, "0")}-${String(i).padStart(2, "0")}`, v = h.by_day[iso] || 0;
    cols += `<i class="${i > lastDay ? "fut" : v > avg * 1.6 ? "hi" : ""}" style="height:${v ? Math.max(4, v / dmax * 100) : 2}%" title="${i}: ${fmt(v)}"></i>`;
  }
  const t = h.top, md = h.max_day;
  return head(`${cap(OY[h.m])} hisoboti`)
    + `<div class="rx-tot"><small>Jami xarajat</small><div class="big">${fmt(h.total)} <span>so'm</span></div>
       <div class="rx-bl" style="margin-top:4px"><span>${h.n} ta yozuv · ${h.active_days} kun</span>${h.budget ? `<span class="${h.total > h.budget ? "up" : "dw"}">byudjet ${h.total > h.budget ? "+" : "−"}${fmt(Math.abs(h.budget - h.total))}</span>` : ""}</div></div>`
    + `<div class="rx-lh"><span>Kunlar bo'yicha</span></div><div class="rx-days">${cols}</div><div class="rx-dl"><span>1</span><span>${Math.ceil(nd / 2)}</span><span>${nd}</span></div>`
    + `<div class="rx-lh"><span>Qayerga ketdi</span></div>`
    + h.cats.map((c) => `<div class="rx-hb"><span>${c.e} ${esc(c.n)}</span><span class="t"><i style="width:${Math.max(3, c.s / max * 100)}%;background:${c.col}"></i></span><em>${short(c.s)}</em></div>`).join("")
    + `<div class="rx-cmp">${t ? `<div><small>Eng katta xarajat</small><b>${t.e} ${esc(t.note)}</b><small>${fmt(t.a)} · ${dayName(t.day).toLowerCase()}</small></div>` : ""}
       ${md ? `<div><small>Eng qimmat kun</small><b>${dayName(md.day)}</b><small>${fmt(md.s)} so'm</small></div>` : ""}
       <div><small>O'tgan oyga nisbatan</small><b class="${h.change > 0 ? "up" : "dw"}">${h.change == null ? "—" : `${h.change > 0 ? "+" : ""}${h.change}% ${h.change > 0 ? "↑" : "↓"}`}</b><small>${h.prev ? `${short(h.prev)} edi` : "ma'lumot yo'q"}</small></div>
       <div><small>Kunlik o'rtacha</small><b>${fmt(h.avg)}</b><small>so'm</small></div></div>`
    + (h.advice ? `<div class="rx-tip">${esc(h.advice)}</div>` : "");
}

// ------------------------------------------------------------------ 📜 tarix
function viewHist(v) {
  const chips = `<div class="rx-flt"><button data-flt="" class="${!v.cat ? "on" : ""}">Hammasi</button>${(home ? home.cats : []).map((c) => `<button data-flt="${c.c}" class="${v.cat === c.c ? "on" : ""}">${c.e} ${esc(c.n)}</button>`).join("")}</div>`;
  if (!v.items) return head("Tarix", `<span class="rx-sub">${cap(OY[ym[1]])}</span>`) + chips + `<div class="rx-load"><i></i><i></i><i></i></div>`;
  if (!v.items.length) return head("Tarix", `<span class="rx-sub">${cap(OY[ym[1]])}</span>`) + chips + `<div class="rx-empty"><b>Yozuv yo'q</b></div>`;
  const groups = {};
  v.items.forEach((x) => { (groups[x.d] = groups[x.d] || []).push(x); });
  const html = Object.keys(groups).sort().reverse().map((d) => {
    const s = groups[d].reduce((a, x) => a + x.a, 0);
    return `<div class="rx-day"><span>${dayName(d)}</span><span>${fmt(s)}</span></div>` + groups[d].map((x) => `<button class="rx-it" data-edit="${x.id}">
      <span class="e" style="background:${cat(x.c).col}24">${x.e}</span><span class="m"><b>${esc(x.n)}${x.src === "v" ? ' <i title="ovoz">🎙</i>' : ""}</b><small>${esc(cat(x.c).n)}</small></span><em>${fmt(x.a)}</em></button>`).join("");
  }).join("");
  return head("Tarix", `<span class="rx-sub">${cap(OY[ym[1]])}</span>`) + chips + html + (v.more ? `<button class="rx-more" data-act="more">Yana ko'rsatish</button>` : "");
}
async function loadHist(append) {
  const v = top();
  if (v.v !== "hist") return;
  const before = append && v.items && v.items.length ? v.items[v.items.length - 1].id : 0;
  const r = await api(`api/rasxod/list?m=${ymStr()}&cat=${v.cat || ""}${before ? `&before=${before}` : ""}`);
  if (!r.ok) { toast(esc(r.error || "Yuklab bo'lmadi")); return; }
  v.items = append ? (v.items || []).concat(r.items) : r.items;
  v.more = r.items.length >= 60;
  if (top() === v) render();
}

// ------------------------------------------------------------------ ✏️ tahrirlash oynasi
function sheet(html) {
  closeSheet();
  const el = document.createElement("div");
  el.className = "rx-sheet"; el.id = "rxsheet";
  el.innerHTML = `<div class="rx-sbg" data-act="sclose"></div><div class="rx-card"><i class="grab"></i>${html}</div>`;
  $("rasxod").appendChild(el);
  requestAnimationFrame(() => el.classList.add("in"));
}
function closeSheet() { const s = $("rxsheet"); if (s) s.remove(); }
function editSheet(x) {
  const cats = Object.keys(meta).map((c) => `<button data-pc="${c}" class="${c === x.c ? "on" : ""}"><span>${meta[c].e}</span>${esc(meta[c].n)}</button>`).join("");
  sheet(`<h3>Xarajatni tahrirlash</h3>
    <label>Summa<input id="rxa" inputmode="numeric" value="${fmt(x.a)}"></label>
    <label>Izoh<input id="rxn" maxlength="80" value="${esc(x.n)}"></label>
    <label>Sana<input id="rxd" type="date" value="${x.d}" max="${home ? home.today_iso : ""}"></label>
    <div class="rx-pcs">${cats}</div>
    <div class="rx-sbtn"><button class="del" data-act="sdel" data-id="${x.id}">🗑 O'chirish</button><button class="save" data-act="ssave" data-id="${x.id}">Saqlash</button></div>`);
}
function budgetSheet() {
  sheet(`<h3>💰 Oylik byudjet</h3><p>Oyiga qancha sarflashni rejalashtirasiz? Qolgan summa bosh sahifada ko'rinib turadi.</p>
    <label>Summa<input id="rxb" inputmode="numeric" placeholder="4 000 000" value="${home && home.budget ? fmt(home.budget) : ""}"></label>
    <div class="rx-sbtn">${home && home.budget ? `<button class="del" data-act="bclear">Olib tashlash</button>` : ""}<button class="save" data-act="bsave">Saqlash</button></div>`);
  setTimeout(() => { const i = $("rxb"); if (i) i.focus(); }, 250);
}
const digits = (s) => +String(s || "").replace(/\D/g, "");

// ------------------------------------------------------------------ ➕ qo'shish: matn va ovoz
function inputBar() {
  return `<div class="rx-inp${busy ? " busy" : ""}" id="rxinp">
    <input id="rxq" placeholder="Xarajat yozing: «non 8 ming»" enterkeyhint="send" autocomplete="off" maxlength="500">
    <button class="go" data-act="go" id="rxgo" aria-label="Yuborish" ${busy ? "disabled" : ""}>${ICO.send}</button></div>`;
}
function drawInput() {
  const old = $("rxinp"), keep = $("rxq") ? $("rxq").value : "";
  const wrap = document.createElement("div"); wrap.innerHTML = inputBar();
  const el = wrap.firstElementChild;
  if (old) old.replaceWith(el); else $("rasxod").appendChild(el);
  const q = $("rxq");
  q.value = keep;
  q.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); sendText(); } });
  el.hidden = top().v !== "home" && top().v !== "hist";
}
function savedToast(r) {
  const list = r.items.map((x) => `${x.e} ${esc(x.n)} — <b>${fmt(x.a)}</b>`).join("<br>");
  toast(`✅ ${r.items.length > 1 ? `${r.items.length} ta yozildi` : "Yozildi"}<br>${list}`
    + (r.day && home && r.day !== home.today_iso ? `<br>📅 ${dayName(r.day)}` : ""), true);
}
async function afterSave() {
  if (!isCur()) { const d = new Date(home.today_iso + "T00:00:00"); ym = [d.getFullYear(), d.getMonth() + 1]; }
  await refresh();
  if (top().v === "hist") { top().items = null; render(); loadHist(); }
}
async function sendText() {
  const q = $("rxq");
  const text = q ? q.value.trim() : "";
  if (!text) { if (q) q.focus(); return; }
  if (busy) return;
  busy = true;
  const r = await api("api/rasxod/add", {text});
  busy = false;
  if (!r.ok) { haptic("err"); toast(esc(ERR[r.error] || r.error || "Xato")); return; }
  q.value = ""; haptic("ok"); savedToast(r); drawInput();
  await afterSave();
}
// ------------------------------------------------------------------ navigatsiya
function render() {
  const v = top(), el = $("rxview");
  if (!el) return;
  const views = {home: viewHome, hist: viewHist, report: viewReport};
  el.innerHTML = (views[v.v] || viewHome)(v);
  $("rasxod").dataset.v = v.v;
  const inp = $("rxinp"); if (inp) inp.hidden = v.v === "report";
  updateBack();
}
function go(v) { stack.push(v); haptic(); render(); $("rxscroll").scrollTop = 0; if (v.v === "hist") loadHist(); }
function back() { if ($("rxsheet")) { closeSheet(); return; } if (stack.length <= 1) return; stack.pop(); render(); }
function updateBack() {
  if (!tg || !tg.BackButton) return;
  try {
    if (opened && stack.length > 1) tg.BackButton.show();
    else if (opened && (!window.ZK_canHideBack || window.ZK_canHideBack())) tg.BackButton.hide();
  } catch (e) {}
}
async function refresh() {
  const r = await api(`api/rasxod/home?m=${ymStr()}`);
  if (r.ok) {
    home = r; meta = {}; (r.meta || []).forEach((x) => { meta[x.c] = x; });
    if (opened) { render(); drawInput(); }
  } else if (!home && opened && top().v === "home") $("rxview").innerHTML = `<div class="rx-bar">${segHtml()}</div><div class="rx-empty"><b>${esc(r.error || "Yuklab bo'lmadi")}</b><br><br><button class="rx-more" data-act="reload">Qayta urinish</button></div>`;
}
function findItem(id) { const v = stack.find((s) => s.v === "hist"); return v && v.items ? v.items.find((x) => x.id === id) : null; }

async function onClick(e) {
  const t = e.target;
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "rasxod" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  const ex = t.closest("[data-ex]"); if (ex) { const q = $("rxq"); if (q) { q.value = ex.dataset.ex; q.dispatchEvent(new Event("input")); q.focus(); } return; }
  const c = t.closest("[data-cat]"); if (c) { go({v: "hist", cat: c.dataset.cat}); return; }
  const f = t.closest("[data-flt]"); if (f) { const v = top(); v.cat = f.dataset.flt; v.items = null; haptic(); render(); loadHist(); return; }
  const ed = t.closest("[data-edit]"); if (ed) { const x = findItem(+ed.dataset.edit); if (x) { haptic(); editSheet(x); } return; }
  const pc = t.closest("[data-pc]"); if (pc) { pc.parentNode.querySelectorAll("[data-pc]").forEach((b) => b.classList.toggle("on", b === pc)); haptic(); return; }
  const b = t.closest("[data-act]");
  if (!b) return;
  const act = b.dataset.act;
  if (act === "back") back();
  else if (act === "reload") { render(); refresh(); }
  else if (act === "hist") go({v: "hist", cat: ""});
  else if (act === "report") go({v: "report"});
  else if (act === "more") loadHist(true);
  else if (act === "budget") budgetSheet();
  else if (act === "sclose") closeSheet();
  else if (act === "mprev" || act === "mnext") {
    let [y, m] = ym; m += act === "mprev" ? -1 : 1; if (m < 1) { m = 12; y--; } if (m > 12) { m = 1; y++; }
    ym = [y, m]; home = null; haptic(); render(); refresh();
  }
  else if (act === "go") sendText();
  else if (act === "ssave") {
    const id = +b.dataset.id, on = $("rxsheet").querySelector("[data-pc].on");
    const r = await api("api/rasxod/edit", {id, a: digits($("rxa").value), n: $("rxn").value, d: $("rxd").value, c: on ? on.dataset.pc : ""});
    if (!r.ok) { toast("Saqlab bo'lmadi"); return; }
    haptic("ok"); closeSheet(); toast("✅ Saqlandi"); await afterSave();
  }
  else if (act === "sdel") {
    const id = +b.dataset.id;
    const r = await api("api/rasxod/del", {id});
    if (!r.ok) { toast("O'chirib bo'lmadi"); return; }
    haptic("ok"); closeSheet(); toast("🗑 O'chirildi"); await afterSave();
  }
  else if (act === "bsave" || act === "bclear") {
    const a = act === "bclear" ? 0 : digits($("rxb").value);
    const r = await api("api/rasxod/budget", {a});
    if (!r.ok) { toast("Saqlab bo'lmadi"); return; }
    haptic("ok"); closeSheet(); toast(a ? `✅ Byudjet: ${fmt(a)} so'm` : "Byudjet olib tashlandi"); refresh();
  }
}

if (tg && tg.BackButton) tg.BackButton.onClick(() => { if (opened && (stack.length > 1 || $("rxsheet"))) back(); });

window.ZRasxod = {
  open() {
    if (!mounted) { mounted = true; $("rasxod").addEventListener("click", onClick); }
    if (!ym) { const d = new Date(Date.now() + (new Date().getTimezoneOffset() + 300) * 60000); ym = [d.getFullYear(), d.getMonth() + 1]; }
    opened = true;
    $("rasxod").hidden = false; document.body.classList.add("rx-on");
    render(); drawInput();
    refresh();
  },
  start(param) { if (param === "hist") go({v: "hist", cat: ""}); else if (param === "report") go({v: "report"}); },
  close() {
    opened = false;
    closeSheet();
    $("rasxod").hidden = true; document.body.classList.remove("rx-on");
    updateBack();
  },
  busy() { return opened && (stack.length > 1 || !!$("rxsheet")); },
};
})();
