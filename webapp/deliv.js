/* 📦 Yetkazish (Deliv) — Hamkor do'konlar, buyurtma berish va BNT-XXXX jonli kuryer kuzatuvi.
   <section class="dlv" id="deliv" hidden><div id="dlvview"></div></section> ichiga chiziladi.
   window.ZDeliv = { open, close } */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const fmtSum = (n) => Number(n || 0).toLocaleString("ru-RU") + " so'm";
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };

let opened = false;
let tab = "stores"; // stores | order | track
let cat = "all";
let data = {categories: [], stores: [], orders: [], steps: []};
let cart = []; // [{id, name, price, qty, store_id, store_name}]
let trackedOrder = null;
let toastMsg = "";
let toastT = 0;

function ensureStyles() {
  if ($("dlv-fallback-css")) return;
  const st = document.createElement("style");
  st.id = "dlv-fallback-css";
  st.textContent = `
    .dlv{position:fixed;inset:0;z-index:1050;background:radial-gradient(circle at top,#112926 0%,#09121a 60%,#060b10 100%);color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;flex-direction:column;overflow:hidden}
    .dlv[hidden]{display:none!important}
    .dlv-top{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 14px;background:rgba(9,18,26,.86);backdrop-filter:blur(14px);border-bottom:1px solid rgba(255,255,255,.08)}
    .dlv-top h2{margin:0;font-size:17px;font-weight:800}
    .dlv-ib{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);color:#f8fafc;border-radius:12px;padding:7px 11px;font-size:13px;font-weight:700;cursor:pointer}
    .dlv-wrap{flex:1;overflow-y:auto;padding:12px 14px 86px;max-width:680px;width:100%;margin:0 auto;box-sizing:border-box}
    .dlv-tabs{display:flex;gap:6px;margin-bottom:12px}
    .dlv-tab{flex:1;padding:9px 10px;border-radius:12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.09);color:#cbd5e1;font-weight:700;font-size:13px;cursor:pointer}
    .dlv-tab.on{background:linear-gradient(135deg,#10b981,#059669);color:#fff;border-color:transparent}
    .dlv-chips{display:flex;gap:6px;overflow-x:auto;padding-bottom:8px;margin-bottom:8px}
    .dlv-chip{white-space:nowrap;padding:7px 12px;border-radius:999px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);color:#e2e8f0;font-size:12.5px;font-weight:600;cursor:pointer}
    .dlv-chip.on{background:#10b981;color:#052e16;font-weight:800}
    .dlv-card{background:rgba(15,23,42,.74);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:14px;margin-bottom:12px}
    .dlv-item{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid rgba(255,255,255,.07)}
    .dlv-btn{background:linear-gradient(135deg,#10b981,#059669);color:#fff;border:none;border-radius:11px;padding:9px 13px;font-weight:700;font-size:13.5px;cursor:pointer}
    .dlv-btn.sec{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.12)}
    .dlv-inp{width:100%;box-sizing:border-box;background:rgba(9,18,26,.85);border:1px solid rgba(255,255,255,.16);color:#fff;border-radius:11px;padding:10px 12px;font-size:14px;margin-bottom:8px}
    .dlv-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:10px 0}
    .dlv-step{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:7px 5px;text-align:center;font-size:11px;color:#94a3b8}
    .dlv-step.done{background:rgba(16,185,129,.22);border-color:rgba(16,185,129,.5);color:#a7f3d0;font-weight:700}
    .dlv-row{display:flex;gap:8px;align-items:center}
    .dlv-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#0f172a;border:1px solid rgba(16,185,129,.45);color:#fff;padding:9px 16px;border-radius:999px;font-size:13px;font-weight:600;z-index:99}
  `;
  document.head.appendChild(st);
}

function toast(msg) {
  toastMsg = msg;
  clearTimeout(toastT);
  toastT = setTimeout(() => { toastMsg = ""; render(); }, 2800);
  render();
}

async function api(path, body) {
  const opt = {headers: {"X-Init-Data": (tg && tg.initData) || ""}};
  if (body) {
    opt.method = "POST";
    opt.body = JSON.stringify(body);
    opt.headers["Content-Type"] = "application/json";
  }
  const r = await fetch(path, opt);
  try { return await r.json(); } catch (e) { return {ok: false, error: "net"}; }
}

async function loadHome() {
  const r = await api("api/deliv/home");
  if (r.ok) {
    data = r;
    if (!trackedOrder && r.orders && r.orders.length) trackedOrder = r.orders[0];
  }
  render();
}

function addToCart(storeId, itemId) {
  const store = (data.stores || []).find((s) => s.id === storeId);
  if (!store) return;
  const it = (store.items || []).find((x) => x.id === itemId);
  if (!it) return;
  const ex = cart.find((c) => c.id === itemId);
  if (ex) ex.qty += 1;
  else cart.push({id: it.id, name: it.name, price: it.price, qty: 1, store_id: store.id, store_name: store.name});
  haptic("ok");
  toast(`🛒 «${it.name}» savatchaga qo'shildi`);
}

function storesHTML() {
  const cats = data.categories || [];
  const stores = (data.stores || []).filter((s) => cat === "all" || s.cat === cat);
  return `
    <div class="dlv-chips">
      ${cats.map((c) => `<button class="dlv-chip${cat === c.id ? " on" : ""}" data-cat="${esc(c.id)}">${esc(c.ic)} ${esc(c.name)}</button>`).join("")}
    </div>
    ${stores.map((s) => `
      <div class="dlv-card">
        <div class="dlv-row" style="justify-content:space-between;margin-bottom:6px">
          <div>
            <b style="font-size:15px">${esc(s.name)}</b>
            <div style="font-size:12px;color:#94a3b8">${esc(s.addr)} · ⏱ ${esc(s.eta)} · ⭐ ${s.rating} · Yetkazish: ${fmtSum(s.fee)}</div>
          </div>
        </div>
        ${(s.items || []).map((it) => `
          <div class="dlv-item">
            <div>
              <span style="margin-right:6px">${esc(it.ic)}</span><b>${esc(it.name)}</b>
              <div style="font-size:12.5px;color:#34d399;margin-top:2px">${fmtSum(it.price)}</div>
            </div>
            <button class="dlv-btn" data-add="${esc(s.id)}:${esc(it.id)}">+ Qo'shish</button>
          </div>
        `).join("")}
      </div>
    `).join("")}
  `;
}

function orderFormHTML() {
  const sum = cart.reduce((a, x) => a + x.price * x.qty, 0);
  return `
    <div class="dlv-card">
      <b style="font-size:15px">🛒 Savatcha va Jo'natma</b>
      ${cart.length ? `
        <div style="margin:8px 0">
          ${cart.map((c, i) => `
            <div class="dlv-item">
              <div><b>${esc(c.name)}</b> × ${c.qty}<div style="font-size:12px;color:#94a3b8">${esc(c.store_name)}</div></div>
              <div class="dlv-row">
                <span style="font-size:13px">${fmtSum(c.price * c.qty)}</span>
                <button class="dlv-ib" data-rm="${i}">✕</button>
              </div>
            </div>
          `).join("")}
          <div style="margin-top:8px;font-size:13.5px;color:#34d399"><b>Mahsulotlar: ${fmtSum(sum)}</b> (+ yetkazish haqi)</div>
        </div>
      ` : `
        <div style="font-size:12.5px;color:#94a3b8;margin:6px 0">Savatcha bo'sh — istalgan posilka yoki buyum nomini quyida yozishingiz mumkin:</div>
        <input class="dlv-inp" id="dlv-custom" placeholder="Nimani yetkazish kerak? (masalan: Kalit va hujjatlar)">
      `}
      <input class="dlv-inp" id="dlv-pickup" placeholder="Olib ketish manzili (ixtiyoriy)">
      <input class="dlv-inp" id="dlv-addr" placeholder="Yetkazib berish manzili *">
      <input class="dlv-inp" id="dlv-phone" placeholder="Telefon raqam (+998 ...) *">
      <input class="dlv-inp" id="dlv-note" placeholder="Kuryer uchun izoh (podyezd, qavat...)">
      <button class="dlv-btn" style="width:100%" data-act="submit">🚀 Buyurtma berish (Bauntys Express)</button>
    </div>
  `;
}

function orderCardHTML(o) {
  const steps = data.steps || [
    {key: "accepted", title: "Qabul qilindi", ic: "📥"},
    {key: "preparing", title: "Tayyorlanmoqda", ic: "📦"},
    {key: "on_the_way", title: "Yo'lda", ic: "🛵"},
    {key: "delivered", title: "Yetkazildi", ic: "✅"},
  ];
  const st = Number(o.step || 0);
  const c = o.courier || {};
  return `
    <div class="dlv-card">
      <div class="dlv-row" style="justify-content:space-between">
        <div>
          <b style="font-size:16px;color:#34d399">${esc(o.code)}</b>
          <div style="font-size:12.5px;color:#94a3b8">${esc(o.store_name)} · ${esc(o.address)}</div>
        </div>
        <span style="font-size:12px;font-weight:700;padding:4px 9px;border-radius:999px;background:rgba(16,185,129,.2);color:#a7f3d0">${esc(o.status_title)}</span>
      </div>
      <div class="dlv-steps">
        ${steps.map((s, idx) => `<div class="dlv-step${idx <= st && !o.cancelled ? " done" : ""}">${esc(s.ic)}<br>${esc(s.title)}</div>`).join("")}
      </div>
      <div style="font-size:12.5px;color:#cbd5e1;margin-bottom:8px">
        Mahsulotlar: ${(o.items || []).map((x) => `${esc(x.name)}×${x.qty}`).join(", ")}<br>
        Kuryer: <b>${esc(c.name || "Tayinlanmoqda")}</b> (${esc(c.vehicle || "")} · ${esc(c.phone || "")}) · Jami: <b>${fmtSum(o.total)}</b>
      </div>
      <div class="dlv-row">
        ${!o.cancelled && st < 3 ? `<button class="dlv-btn sec" data-adv="${esc(o.code)}">⏩ Keyingi bosqich</button>` : ""}
        ${!o.cancelled && st < 2 ? `<button class="dlv-ib" data-cancel="${esc(o.code)}">Bekor qilish</button>` : ""}
      </div>
    </div>
  `;
}

function trackHTML() {
  const orders = data.orders || [];
  return `
    <div class="dlv-card">
      <div class="dlv-row">
        <input class="dlv-inp" style="margin:0;text-transform:uppercase" id="dlv-find" placeholder="Kuzatuv kodi (masalan: BNT-1234)">
        <button class="dlv-btn" data-act="find">Izlash</button>
      </div>
    </div>
    ${trackedOrder ? orderCardHTML(trackedOrder) : ""}
    <div style="font-weight:700;font-size:14px;margin:8px 0">📋 Buyurtmalarim (${orders.length})</div>
    ${orders.length ? orders.map(orderCardHTML).join("") : `<div class="dlv-card" style="color:#94a3b8;font-size:13px">Hali buyurtmalar yo'q. Do'konlardan mahsulot tanlab buyurtma bering!</div>`}
  `;
}

function render() {
  const sec = $("deliv");
  if (!sec || !opened) return;
  const cartCnt = cart.reduce((a, x) => a + x.qty, 0);
  const body = tab === "stores" ? storesHTML() : tab === "order" ? orderFormHTML() : trackHTML();
  sec.innerHTML = `
    <div class="dlv-top">
      <button class="dlv-ib" data-act="back">← Orqaga</button>
      <h2>📦 Bauntys Deliv</h2>
      <button class="dlv-ib" data-act="hub">☰ Bo'limlar</button>
    </div>
    <div class="dlv-wrap" id="dlvview">
      <div class="dlv-tabs">
        <button class="dlv-tab${tab === "stores" ? " on" : ""}" data-tab="stores">🏪 Do'konlar</button>
        <button class="dlv-tab${tab === "order" ? " on" : ""}" data-tab="order">🛒 Buyurtma${cartCnt ? ` (${cartCnt})` : ""}</button>
        <button class="dlv-tab${tab === "track" ? " on" : ""}" data-tab="track">🛵 Kuzatuv</button>
      </div>
      ${body}
    </div>
    ${toastMsg ? `<div class="dlv-toast">${esc(toastMsg)}</div>` : ""}
  `;
}

async function onClick(e) {
  const btn = e.target.closest("button");
  if (!btn) return;
  const act = btn.dataset.act;
  if (act === "back") { close(); if (window.ZK_setMode) window.ZK_setMode("kino"); return; }
  if (act === "hub") { if (window.ZHub && window.ZHub.open) window.ZHub.open("deliv"); return; }
  if (btn.dataset.tab) { tab = btn.dataset.tab; render(); return; }
  if (btn.dataset.cat) { cat = btn.dataset.cat; render(); return; }
  if (btn.dataset.add) {
    const [sid, iid] = btn.dataset.add.split(":");
    addToCart(sid, iid);
    return;
  }
  if (btn.dataset.rm !== undefined) {
    cart.splice(+btn.dataset.rm, 1);
    render();
    return;
  }
  if (act === "submit") {
    const addr = ($("dlv-addr") && $("dlv-addr").value.trim()) || "";
    const phone = ($("dlv-phone") && $("dlv-phone").value.trim()) || "";
    const pickup = ($("dlv-pickup") && $("dlv-pickup").value.trim()) || "";
    const note = ($("dlv-note") && $("dlv-note").value.trim()) || "";
    const customItem = ($("dlv-custom") && $("dlv-custom").value.trim()) || "";
    const items = cart.length ? cart.map((c) => ({name: c.name, qty: c.qty, price: c.price}))
      : (customItem ? [{name: customItem, qty: 1, price: 25000}] : []);
    const storeId = cart.length ? cart[0].store_id : "";
    const r = await api("api/deliv/order", {address: addr, phone, pickup, note, items, store_id: storeId});
    if (r.ok && r.order) {
      haptic("ok");
      cart = [];
      trackedOrder = r.order;
      tab = "track";
      toast(`✅ Buyurtma qabul qilindi: ${r.code}`);
      await loadHome();
    } else toast(r.msg || "⚠️ Manzil, telefon va mahsulotni to'ldiring");
    return;
  }
  if (act === "find") {
    const code = ($("dlv-find") && $("dlv-find").value.trim()) || "";
    if (!code) return;
    const r = await api(`api/deliv/track?code=${encodeURIComponent(code)}`);
    if (r.ok && r.order) { trackedOrder = r.order; render(); }
    else toast(r.msg || "Buyurtma topilmadi");
    return;
  }
  if (btn.dataset.adv) {
    const r = await api("api/deliv/advance", {code: btn.dataset.adv});
    if (r.ok && r.order) { trackedOrder = r.order; haptic("ok"); await loadHome(); }
    return;
  }
  if (btn.dataset.cancel) {
    const r = await api("api/deliv/cancel", {code: btn.dataset.cancel});
    if (r.ok && r.order) { trackedOrder = r.order; await loadHome(); }
  }
}

function bindRoot() {
  const sec = $("deliv");
  if (!sec || sec.dataset.bound) return;
  sec.dataset.bound = "1";
  sec.addEventListener("click", onClick);
}

function open() {
  ensureStyles();
  bindRoot();
  const sec = $("deliv");
  if (sec) sec.hidden = false;
  document.body.classList.add("dlv-on");
  opened = true;
  render();
  loadHome();
}

function close() {
  opened = false;
  document.body.classList.remove("dlv-on");
  const sec = $("deliv");
  if (sec) sec.hidden = true;
}

window.ZDeliv = {open, close};
})();
