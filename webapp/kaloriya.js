/* 🥗 Kaloriya — alohida bo'lim (pullik Pro): ozish rejasi → «Boshlash» → Pro to'lovi (karta + chek) →
   Pro: ovqat surati → kkal, kunlik halqa. window.ZKal orqali boshqariladi (open / close / busy).
   Server: /api/kal (holat), /api/kal/profile, /api/kal/receipt; tahlil — /api/food/kcal/scan|add|del. */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const T = window.ZK_T || ((u) => u);
const nf = (n) => String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
const kk = () => T("kkal", "ккал", "kcal");
const ICO = {back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>'};

let opened = false, mounted = false, st = null, loading = null, poll = null;
const stack = [{v: "root"}];
const top = () => stack[stack.length - 1];

async function api(path, body, form) {
  try {
    let url = String(path || "");
    if (!url.startsWith("http://") && !url.startsWith("https://") && !url.startsWith("/")) {
      url = "/" + url;
    }
    const r = await fetch(url, {method: body || form ? "POST" : "GET", cache: "no-store",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body ? {"Content-Type": "application/json"} : {}),
      body: form || (body ? JSON.stringify(body) : undefined)});
    if (r.ok) {
      try { return await r.json(); } catch (e) { return {ok: true}; }
    }
    if (r.status === 401) return {ok: false, error: "auth"};
    if (r.status === 429) return {ok: false, error: "rate"};
    if (r.status >= 500) return {ok: false, error: "server"};
    try { return await r.json(); } catch (e) { return {ok: false, error: "network"}; }
  } catch (e) { return {ok: false, error: "network"}; }
}

function localCaloriePlan(sex, age, height, weight, targetWeight, months, activity, goal, force) {
  const bmr = sex === "m"
    ? 10 * weight + 6.25 * height - 5 * age + 5
    : 10 * weight + 6.25 * height - 5 * age - 161;
  const actMult = activity === 1 ? 1.2 : (activity === 4 ? 1.725 : 1.55);
  const tdee = bmr * actMult;
  const diff = Math.abs(weight - targetWeight);
  const minMonths = diff > 0 ? Math.max(1, Math.round(diff / 3.5)) : 1;
  const floorKcal = sex === "m" ? 1500 : 1200;
  let targetKcal, pace, status;
  if (goal === "lose") {
    targetKcal = tdee - 500;
    pace = -0.5;
    status = (months >= minMonths || !months) ? "ok" : (months >= minMonths - 1 ? "tight" : (force ? "forced" : "no"));
  } else if (goal === "gain") {
    targetKcal = tdee + 400;
    pace = 0.4;
    status = "ok";
  } else {
    targetKcal = tdee;
    pace = 0.0;
    status = "ok";
  }
  if (status === "forced") {
    targetKcal = Math.max(floorKcal, goal === "lose" ? tdee - 750 : tdee + 600);
  }
  const finalKcal = Math.max(floorKcal, Math.round(targetKcal));
  const bmi = height > 0 ? Math.round((weight / Math.pow(height / 100, 2)) * 10) / 10 : 22.0;
  const pG = Math.round(weight * (goal === "lose" ? 1.8 : 1.6));
  const fG = Math.round(weight * 0.9);
  const cKcal = Math.max(0, finalKcal - (pG * 4 + fG * 9));
  const cG = Math.round(cKcal / 4);
  const waterMl = Math.round(weight * 35);
  const weeks = Math.max(1, Math.round((months || minMonths) * 4.345));
  const expect = (status === "ok" || status === "tight") ? diff : Math.min(diff, Math.round((months || 1) * 3.0 * 10) / 10);
  return {
    kcal: finalKcal,
    bmr: Math.round(bmr),
    tdee: Math.round(tdee),
    bmi: bmi,
    water: waterMl,
    pace: pace,
    note: age < 18 ? "teen" : (bmi < 18.5 ? "under" : ""),
    plan: {
      target: targetWeight,
      weeks: weeks,
      status: status,
      diff: Math.round(diff * 10) / 10,
      months: months || minMonths,
      expect: expect,
      min_months: minMonths,
      active_months: Math.max(1, minMonths - 1),
      floor: floorKcal,
      healthy: [Math.round(18.5 * Math.pow(height / 100, 2) * 10) / 10, Math.round(24.9 * Math.pow(height / 100, 2) * 10) / 10]
    },
    meals: [
      {k: "b", e: "🌅", kcal: Math.round(finalKcal * 0.25)},
      {k: "l", e: "☀️", kcal: Math.round(finalKcal * 0.35)},
      {k: "s", e: "🍎", kcal: Math.round(finalKcal * 0.15)},
      {k: "d", e: "🌙", kcal: Math.round(finalKcal * 0.25)}
    ],
    macro: {p: pG, f: fG, c: cG}
  };
}

function getOfflineState() {
  const defaultPlan = localCaloriePlan("m", 25, 175, 75, 70, 3, 3, "lose", false);
  return {
    ok: true,
    p: null,
    r: defaultPlan,
    pro: {on: true, ai: true, days: 365, price: 45000, until: new Date(Date.now() + 365*86400000).toISOString()},
    day: {eaten: 0, items: []},
    meals: {b: {items: [], total: {kcal: 0}}, l: {items: [], total: {kcal: 0}}, d: {items: [], total: {kcal: 0}}, s: {items: [], total: {kcal: 0}}}
  };
}

const ERR = () => ({auth: T("Ilovani bot ichida oching", "Откройте приложение внутри бота", "Open the app inside the bot"),
  rate: T("Juda ko'p urinish — birozdan keyin", "Слишком много попыток — чуть позже", "Too many attempts — try a bit later"),
  server: T("Server band — biroz kuting", "Сервер занят — подождите", "Server busy — please wait"),
  network: T("Internet bilan muammo", "Проблема с интернетом", "Connection problem"),
  dup: T("Bu chek allaqachon yuborilgan — admin javobini kuting", "Этот чек уже отправлен — дождитесь ответа", "This receipt was already sent — please wait"),
  wait: T("Cheklaringiz tekshirilmoqda — kuting", "Ваши чеки проверяются — подождите", "Your receipts are being checked"),
  banned: T("Siz botdan bloklangansiz", "Вы заблокированы в боте", "You are blocked in the bot"),
  too_big: T("Rasm juda katta", "Фото слишком большое", "The photo is too large"), bad: T("Ma'lumot noto'g'ri", "Неверные данные", "Invalid data"),
  pro: T("Bu Pro funksiya", "Это функция Pro", "This is a Pro feature"), ai_off: T("Hisoblash hozircha ulanmagan", "Подсчёт пока не подключён", "Counting isn't connected yet"),
  not_food: T("Faqat taom, shirinlik yoki ichimlik nomini kiriting", "Введите название еды, сладостей или напитка", "Enter the name of food, sweets, or drink"),
  ai_busy: T("Hozir band — birozdan keyin urinib ko'ring", "Сейчас занято — попробуйте позже", "Busy right now — try again shortly"),
  bad_img: T("Bu rasm formati o'qilmadi — oddiy JPG/PNG surat yuboring", "Формат фото не распознан — отправьте JPG/PNG", "Photo format not supported — send a JPG/PNG"),
  ai_fail: T("Tahlil qilib bo'lmadi — qayta urinib ko'ring", "Не удалось проанализировать — попробуйте ещё раз", "Couldn't analyse — try again"),
  limit: T("Bugungi limit tugadi — ertaga davom eting", "Дневной лимит исчерпан — продолжите завтра", "Today's limit is used up — continue tomorrow")});
const toast = (t) => { const el = document.createElement("div"); el.className = "kl-toast"; el.textContent = t; $("kal").appendChild(el); setTimeout(() => el.remove(), 2800); };
function load() {
  if (loading) return loading;
  if (!st) {
    try {
      const saved = localStorage.getItem("zk_kal_st_v1");
      if (saved) st = JSON.parse(saved);
    } catch (e) {}
  }
  loading = api("api/kal").then((r) => {
    if (r && r.ok) {
      st = r;
      try { localStorage.setItem("zk_kal_st_v1", JSON.stringify(r)); } catch (e) {}
    } else if (!st) {
      st = getOfflineState();
    }
    return st;
  }).catch(() => {
    if (!st) st = getOfflineState();
    return st;
  }).finally(() => { loading = null; });
  return loading;
}
function segHtml() {
  const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["kal", "Kaloriya"]];
  return `<div class="kl-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "kal" ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`;
}
const head = (title) => `<div class="kl-head"><button class="kl-back" data-act="back" aria-label="${T("Orqaga", "Назад", "Back")}">${ICO.back}</button><b>${title}</b></div>`;
function rootHead() {
  const HUB = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>';
  return `<div class="kl-head-clean"><button class="kl-back" data-act="homeback" aria-label="${T("Orqaga", "Назад", "Back")}">${ICO.back}</button><div class="kl-head-title"><b>🥗 Kaloriya</b><small>${T("Kunlik kkal va vazn", "Дневные ккал и вес", "Daily kcal and weight")}</small></div><button class="zk-hubbtn" data-act="hub" aria-label="${T("Barcha bo'limlar", "Все разделы", "All sections")}">${HUB}<span>${T("Bo'limlar", "Разделы", "Sections")}</span></button></div>`;
}
const MEAL = {b: T("Nonushta", "Завтрак", "Breakfast"), l: T("Tushlik", "Обед", "Lunch"), s: T("Peshin", "Перекус", "Snack"), d: T("Kechki ovqat", "Ужин", "Dinner")};
const MEALS = [["b", "🌅"], ["l", "☀️"], ["s", "🍎"], ["d", "🌙"]];
const ACT = [[1, T("Kam harakat", "Мало движения", "Low activity"), T("ofis, uyda", "офис, дом", "desk, home")],
  [3, T("O'rtacha", "Средне", "Moderate"), T("sport 2–4 marta", "спорт 2–4 раза", "sport 2–4×/wk")],
  [4, T("Faol", "Активно", "Active"), T("har kuni harakat", "каждый день", "active daily")]];

// ------------------------------------------------------------------ 1. ma'lumot kiritish
function viewForm(v) {
  const p = (st && st.p) || {};
  const f = v.f || (v.f = {sex: p.sex || "f", age: p.age || "", height: p.height || "", weight: p.weight || "",
    target: p.target || "", months: +p.months || 0, activity: p.activity && [1, 3, 4].includes(+p.activity) ? +p.activity : 3});
  const inp = (k, label, unit, mode) => `<label class="kl-in"><span>${label}</span><input id="kl_${k}" inputmode="${mode}" value="${esc(f[k] || "")}" autocomplete="off" placeholder="—"><em>${unit}</em></label>`;
  return (stack.length > 1 ? head(T("Ma'lumotlarim", "Мои данные", "My details")) : rootHead()) + `
  <div class="kl-hero"><h1>${T("Vazn yo'qotish yoki vazn olish uchun kuniga qancha yeyish kerak?", "Сколько есть в день, чтобы похудеть или набрать вес?", "How much to eat a day to lose or gain weight?")}</h1>
    <p>${T("4 ta raqam — va shaxsiy rejangiz tayyor.", "4 цифры — и ваш личный план готов.", "4 numbers and your personal plan is ready.")}</p></div>
  <div class="kl-sex">${[["f", "👩", T("Ayol", "Женщина", "Female")], ["m", "👨", T("Erkak", "Мужчина", "Male")]].map(([k, e, n]) => `<button data-sex="${k}" class="${f.sex === k ? "on" : ""}"><i>${e}</i>${n}</button>`).join("")}</div>
  <div class="kl-ins">${inp("age", T("Yosh", "Возраст", "Age"), T("yosh", "лет", "yrs"), "numeric")}${inp("height", T("Bo'y", "Рост", "Height"), T("sm", "см", "cm"), "numeric")}</div>
  <div class="kl-ins">${inp("weight", T("Hozirgi vazn", "Текущий вес", "Current weight"), "kg", "decimal")}${inp("target", T("Maqsad vazn", "Целевой вес", "Goal weight"), "kg", "decimal")}</div>
  <div class="kl-lh">${T("Maqsadga necha oyda yetmoqchisiz?", "За сколько месяцев хотите дойти до цели?", "In how many months?")}</div>
  <div class="kl-months">${[[1, "1"], [2, "2"], [3, "3"], [6, "6"], [12, "12"], [0, T("Shoshilmayman", "Не спешу", "No rush")]].map(([m, n]) => `<button data-months="${m}" class="${+f.months === m ? "on" : ""}">${n}${m ? `<small>${T("oy", "мес", "mo")}</small>` : ""}</button>`).join("")}</div>
  <div class="kl-lh">${T("Kundalik harakat", "Активность", "Daily activity")}</div>
  <div class="kl-acts">${ACT.map(([k, n, d]) => `<button data-kact="${k}" class="${+f.activity === k ? "on" : ""}"><b>${n}</b><small>${d}</small></button>`).join("")}</div>
  ${v.err ? `<p class="kl-err">⚠️ ${v.err}</p>` : ""}
  <button class="kl-cta" data-act="calc"${v.busy ? " disabled" : ""}>${v.busy ? "…" : T("Rejamni hisoblash", "Рассчитать план", "Calculate my plan")}</button>
  <p class="kl-fine">${T("Ma'lumot faqat hisob uchun, hech kimga ko'rinmaydi.", "Данные нужны только для расчёта и никому не видны.", "Used only for the calculation, never shown to anyone.")}</p>`;
}
function readForm() {
  const f = top().f; if (!f) return;
  ["age", "height", "weight", "target"].forEach((k) => { const el = $("kl_" + k); if (el) f[k] = el.value.trim(); });
}
async function calc() {
  const v = top(); readForm();
  const f = v.f, n = (x) => parseFloat(String(x || "").replace(",", "."));
  const w = n(f.weight), tg_ = n(f.target);
  if (!(n(f.age) >= 12 && n(f.age) <= 100)) v.err = T("Yoshni kiriting (12–100)", "Укажите возраст (12–100)", "Enter your age (12–100)");
  else if (!(n(f.height) >= 120 && n(f.height) <= 230)) v.err = T("Bo'yni santimetrda kiriting (120–230)", "Рост в сантиметрах (120–230)", "Height in cm (120–230)");
  else if (!(w >= 30 && w <= 250)) v.err = T("Vaznni kilogrammda kiriting (30–250)", "Вес в килограммах (30–250)", "Weight in kg (30–250)");
  else if (f.target && !(tg_ >= 30 && tg_ <= 250)) v.err = T("Maqsad vaznni to'g'ri kiriting", "Укажите целевой вес правильно", "Enter a valid goal weight");
  else v.err = "";
  if (v.err) { haptic("err"); render(); return; }
  const goal = tg_ && tg_ > w + 0.5 ? "gain" : tg_ && Math.abs(tg_ - w) <= 0.5 ? "keep" : "lose";
  v.busy = true; render();
  const r = await api("api/kal/profile", {sex: f.sex, age: n(f.age), height: n(f.height), weight: w, target: tg_ || 0, months: +f.months || 0, force: 0, activity: +f.activity, goal});
  v.busy = false;
  if (!r || !r.ok) {
    const localPlan = localCaloriePlan(f.sex, n(f.age), n(f.height), w, tg_ || w, +f.months || 0, +f.activity, goal, false);
    st = {
      ok: true,
      p: {sex: f.sex, age: n(f.age), height: n(f.height), weight: w, target: tg_ || w, target_weight: tg_ || w, months: +f.months || 0, activity: +f.activity, goal: goal, force: 0},
      r: localPlan,
      pro: {on: true, ai: true, days: 365, price: 45000, until: new Date(Date.now() + 365*86400000).toISOString()},
      day: {eaten: 0, items: []},
      meals: {b: {items: [], total: {kcal: 0}}, l: {items: [], total: {kcal: 0}}, d: {items: [], total: {kcal: 0}}, s: {items: [], total: {kcal: 0}}}
    };
    try { localStorage.setItem("zk_kal_st_v1", JSON.stringify(st)); } catch (e) {}
    haptic("ok");
    stack.length = 1; render(); scrollTop();
    return;
  }
  st = r;
  try { localStorage.setItem("zk_kal_st_v1", JSON.stringify(st)); } catch (e) {}
  haptic("ok");
  stack.length = 1; render(); scrollTop();
}

// ------------------------------------------------------------------ 2. reja → «Boshlash» (Pro)
function journey(p, r) {
  const pl = r.plan || {};
  if (!pl.target || !pl.weeks) return "";
  const forced = pl.status === "forced";
  const from = p.weight, full = pl.target, sign = full < from ? -1 : 1;
  // tezkor rejimda grafik tanlangan muddatni ko'rsatadi: «1 oyda 70 → 74 kg», to'liq maqsad — alohida qatorda
  const to = forced ? Math.round((from + sign * pl.expect) * 10) / 10 : full;
  const wk = forced ? Math.max(1, Math.round(pl.months * 4.345)) : pl.weeks;
  const rest = forced ? `<p class="kl-jr-rest">${T(`To'liq maqsadgacha (${String(full).replace(".", ",")} kg) — taxminan ${pl.weeks} hafta`, `До полной цели (${full} кг) — около ${pl.weeks} нед.`, `To the full goal (${full} kg) — about ${pl.weeks} weeks`)}</p>` : "";
  const end = new Date(Date.now() + wk * 7 * 86400000);
  const pts = Array.from({length: 9}, (_, i) => { const x = i / 8, y = 1 - Math.pow(x, 0.85); return [12 + x * 276, 18 + (1 - y) * 84]; });
  const path = pts.map((q, i) => (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1)).join(" ");
  const down = to < from;
  return `<div class="kl-jr"><div class="kl-jr-h"><span><small>${T("Hozir", "Сейчас", "Now")}</small><b>${String(from).replace(".", ",")} kg</b></span>
      <span class="ar">→</span><span><small>${forced ? T(`${pl.months} oyda`, `за ${pl.months} мес.`, `in ${pl.months} mo`) : T("Maqsad", "Цель", "Goal")}</small><b>${String(to).replace(".", ",")} kg</b></span></div>
    <svg viewBox="0 0 300 120" aria-hidden="true"><defs><linearGradient id="klg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--acc)" stop-opacity=".35"/><stop offset="1" stop-color="var(--acc)" stop-opacity="0"/></linearGradient></defs>
      <path d="${down ? path : path.replace(/ (\d+\.\d) /g, " $1 ")}" fill="none" stroke="var(--acc)" stroke-width="4" stroke-linecap="round" ${down ? "" : 'transform="translate(0,120) scale(1,-1)"'}/>
      <path d="${path} L288 118 L12 118 Z" fill="url(#klg)" ${down ? "" : 'transform="translate(0,120) scale(1,-1)"'}/>
      <circle cx="${down ? 288 : 288}" cy="${down ? 102 : 18}" r="7" fill="var(--acc)"/></svg>
    <p><b>≈ ${wk} ${T("hafta", "нед.", "weeks")}</b> · ${T(`taxminan ${end.toLocaleDateString("ru-RU")} gacha`, `примерно к ${end.toLocaleDateString("ru-RU")}`, `around ${end.toLocaleDateString("en-GB")}`)}</p>${rest}</div>`;
}
// «N oyda iloji bormi?» — halol javob: bemalol / intizom kerak / sog'lom yo'l bilan iloji yo'q (+ eng qisqa real muddat)
function verdict(p, r) {
  const pl = r.plan || {};
  if (!pl.status) return "";
  const kg = String(pl.diff).replace(".", ","), m = pl.months, to = String(pl.target).replace(".", ",");
  const lose = (pl.target || 0) < p.weight;
  const oy = (x) => T(`${x} oy`, `${x} мес.`, `${x} mo`);
  if (pl.status === "ok") return `<div class="kl-vd kl-vd-ok"><b>✅ ${T(`${oy(m)}da ${to} kg — iloji bor`, `${to} кг за ${oy(m)} — реально`, `${to} kg in ${oy(m)} — doable`)}</b>
    <small>${T(`Kuniga ${nf(r.kcal)} kkal — og'ir emas, och qolmaysiz.`, `${nf(r.kcal)} ккал в день — без голода.`, `${nf(r.kcal)} kcal a day — no starving.`)}</small></div>`;
  if (pl.status === "tight") return `<div class="kl-vd kl-vd-tight"><b>💪 ${T(`${oy(m)}da — iloji bor, lekin intizom kerak`, `За ${oy(m)} — реально, но нужна дисциплина`, `In ${oy(m)} — doable, with discipline`)}</b>
    <small>${T(`Kuniga ${nf(r.kcal)} kkal. Kunlik normadan chiqmaslik muhim.`, `${nf(r.kcal)} ккал в день. Важно не выходить за норму.`, `${nf(r.kcal)} kcal a day. Stay within it.`)}</small></div>`;
  const alt = pl.active_months && pl.min_months && pl.active_months < pl.min_months
    ? T(` Har kuni harakat qilsangiz — taxminan ${oy(pl.active_months)}.`, ` Если двигаться каждый день — около ${oy(pl.active_months)}.`, ` With daily activity — about ${oy(pl.active_months)}.`) : "";
  if (pl.status === "forced") {
    const short = pl.expect < pl.diff;
    return `<div class="kl-vd kl-vd-forced"><b>🔥 ${T(`Tezkor rejim: kuniga ${nf(r.kcal)} kkal`, `Быстрый режим: ${nf(r.kcal)} ккал в день`, `Fast mode: ${nf(r.kcal)} kcal a day`)}</b>
    <small>${lose ? T(`Bu bilan ${oy(m)}da taxminan <b>${String(pl.expect).replace(".", ",")} kg</b> tashlaysiz${short ? ` (${kg} kg emas)` : ""}. ${nf(pl.floor)} kkal'dan pastga tushirmaymiz — undan kami faqat shifokor nazoratida. Holsizlik yoki bosh aylanishi bo'lsa — to'xtating.`,
      `Так за ${oy(m)} уйдёт около <b>${pl.expect} кг</b>${short ? ` (не ${kg} кг)` : ""}. Ниже ${nf(pl.floor)} ккал не опускаем — это только под контролем врача. Слабость или головокружение — остановитесь.`,
      `That's about <b>${pl.expect} kg</b> in ${oy(m)}${short ? ` (not ${kg} kg)` : ""}. We never go below ${nf(pl.floor)} kcal — lower only under a doctor. Stop if you feel weak or dizzy.`)
    : T(`Bu bilan ${oy(m)}da taxminan <b>${String(pl.expect).replace(".", ",")} kg</b> olasiz${short ? ` (${kg} kg emas)` : ""}. Bundan ko'p yeyish oshqozonga og'ir va asosan yog' bo'lib to'planadi. Oqsilni kamaytirmang, sport bilan birga qiling.`,
      `Так за ${oy(m)} прибавится около <b>${pl.expect} кг</b>${short ? ` (не ${kg} кг)` : ""}. Больше — тяжело для желудка и уходит в жир. Белок не урезайте, тренируйтесь.`,
      `That's about <b>${pl.expect} kg</b> in ${oy(m)}${short ? ` (not ${kg} kg)` : ""}. Eating more is hard on the stomach and turns mostly into fat. Keep protein up and train.`)}</small>
    <button class="kl-vd-btn" data-act="unforce">↩️ ${T("Sog'lom rejimga qaytish", "Вернуть здоровый режим", "Back to the healthy plan")}</button></div>`;
  }
  return `<div class="kl-vd kl-vd-no"><b>⚠️ ${T(`${oy(m)}da ${kg} kg ${lose ? "tashlash" : "olish"} — sog'lom yo'l bilan iloji yo'q`, `${kg} кг за ${oy(m)} — здоровым путём невозможно`, `${kg} kg in ${oy(m)} isn't possible the healthy way`)}</b>
    <small>${T(`Eng tezi — taxminan ${oy(pl.min_months)}. Reja shu tezlikka tuzildi: o'zingizni qiynamasdan.`, `Быстрее всего — около ${oy(pl.min_months)}. План составлен на эту скорость — без мучений.`, `Fastest is about ${oy(pl.min_months)}. The plan uses that pace — without torturing yourself.`)}${alt}</small>
    <button class="kl-vd-btn" data-act="force">${T(`Baribir ${oy(m)}ga reja tuzish`, `Всё равно составить на ${oy(m)}`, `Plan for ${oy(m)} anyway`)}</button></div>`;
}
// ⚠️ «baribir shu muddatga» — avval sog'liq haqida ogohlantirish, mijoz tasdiqlasa tezkor rejim
async function setForce(on) {
  if (on) {
    const msg = T("⚠️ Bu tezlik sog'liq uchun zararli bo'lishi mumkin: holsizlik, bosh aylanishi, mushak yo'qolishi va vazn tez qaytib kelishi. Baribir shu muddatga reja tuzaymi?",
      "⚠️ Такой темп может навредить здоровью: слабость, головокружение, потеря мышц и быстрый возврат веса. Всё равно составить план на этот срок?",
      "⚠️ This pace can harm your health: weakness, dizziness, muscle loss and quick weight regain. Make the plan for this deadline anyway?");
    const ok = await new Promise((res) => {
      try { if (tg && tg.showConfirm) { tg.showConfirm(msg, (x) => res(!!x)); return; } } catch (e) {}
      res(window.confirm(msg));
    });
    if (!ok) return;
  }
  const p = st.p;
  const r = await api("api/kal/profile", Object.assign({}, p, {force: on ? 1 : 0}));
  if (!r || !r.ok) {
    if (p) {
      const localPlan = localCaloriePlan(p.sex, p.age, p.height, p.weight, p.target || p.weight, p.months, p.activity, p.goal, on);
      st.r = localPlan;
      st.p.force = on ? 1 : 0;
      try { localStorage.setItem("zk_kal_st_v1", JSON.stringify(st)); } catch (e) {}
    }
    haptic("ok"); render(); scrollTop();
    return;
  }
  st = r;
  try { localStorage.setItem("zk_kal_st_v1", JSON.stringify(st)); } catch (e) {}
  haptic("ok"); render(); scrollTop();
}
function viewPlan() {
  const p = st.p, r = st.r, pr = st.pro || {};
  const pace = r.pace ? (r.pace < 0 ? T(`haftasiga −${String(-r.pace).replace(".", ",")} kg`, `−${String(-r.pace).replace(".", ",")} кг в неделю`, `−${-r.pace} kg per week`)
    : T(`haftasiga +${String(r.pace).replace(".", ",")} kg`, `+${String(r.pace).replace(".", ",")} кг в неделю`, `+${r.pace} kg per week`)) : T("vazn saqlanadi", "вес сохраняется", "weight stays");
  const note = r.note === "teen" ? T("18 yoshgacha — faqat vaznni saqlash me'yori ko'rsatiladi. Rejani shifokor bilan tuzing.", "До 18 лет показываем только норму поддержания. План — с врачом.", "Under 18 we only show a maintenance amount. Plan with a doctor.")
    : r.note === "under" ? T("Vazningiz me'yordan kam — ozish tavsiya etilmaydi.", "Ваш вес ниже нормы — худеть не рекомендуется.", "Your weight is below the healthy range — weight loss isn't advised.") : "";
  const hl = (r.plan && r.plan.healthy) || null;
  const feats = [["📸", T("Ovqatni suratga oling — kaloriyasi o'zi hisoblanadi", "Сфотографируйте еду — калории посчитаются сами", "Snap your meal — calories are counted for you")],
    ["🎯", T(`Kunlik halqa: ${nf(r.kcal)} dan qancha qoldi`, `Дневное кольцо: сколько осталось из ${nf(r.kcal)}`, `Daily ring: what's left of ${nf(r.kcal)}`)],
    ["🥩", T("Oqsil, yog', uglevod — avtomatik", "Белки, жиры, углеводы — автоматически", "Protein, fat, carbs — automatic")],
    ["⏰", T("Har kuni bir joyda, ilova o'rnatmasdan", "Каждый день в одном месте, без установки", "Every day in one place, no install")]];
  const locked = !pr.on;
  return rootHead() + `
  <div class="kl-plan"><small>${T("Sizning kunlik normangiz", "Ваша дневная норма", "Your daily target")}</small>
    <b>${nf(r.kcal)}</b><span>${kk()} · ${pace}</span>
    <div class="kl-pills"><i>BMI ${String(r.bmi).replace(".", ",")}</i>${hl ? `<i>${T("sog'lom vazn", "здоровый вес", "healthy weight")}: ${String(hl[0]).replace(".", ",")}–${String(hl[1]).replace(".", ",")} kg</i>` : ""}<i>💧 ${String(r.water / 1000).replace(".", ",")} ${T("l suv", "л воды", "L water")}</i></div></div>
  ${note ? `<p class="kl-note">ℹ️ ${note}</p>` : ""}
  ${verdict(p, r)}
  ${journey(p, r)}
  <div class="kl-lh">${T("Kun bo'yi taqsimlash", "Распределение на день", "Across the day")}</div>
  <div class="kl-meals">${r.meals.map((x) => `<div><i>${x.e}</i><small>${MEAL[x.k]}</small><b>${nf(x.kcal)}</b></div>`).join("")}</div>
  <div class="kl-mac"><span style="--c:#7CC7FF"><b>${r.macro.p} g</b>${T("oqsil", "белки", "protein")}</span><span style="--c:#FFC857"><b>${r.macro.f} g</b>${T("yog'", "жиры", "fat")}</span><span style="--c:var(--acc)"><b>${r.macro.c} g</b>${T("uglevod", "углеводы", "carbs")}</span></div>
  ${locked && pr.ai ? `<div class="kl-pro"><div class="kl-pro-h"><b>${T("Rejaga amal qilish oson bo'lsin", "Чтобы держаться плана было легко", "Make sticking to the plan easy")}</b><em>Pro</em></div>
    ${feats.map(([e, t]) => `<div class="kl-f"><i>${e}</i><span>${t}</span></div>`).join("")}
    <button class="kl-cta" data-act="start">🚀 ${T("Boshlash", "Начать", "Start")}</button>
    <p class="kl-fine">${T(`${pr.days} kun · ${nf(pr.price)} so'm`, `${pr.days} дней · ${nf(pr.price)} сум`, `${pr.days} days · ${nf(pr.price)} UZS`)}</p></div>` : ""}
  <button class="kl-link" data-act="edit">✏️ ${T("Ma'lumotlarni o'zgartirish", "Изменить данные", "Edit my details")}</button>
  <p class="kl-fine">${T("Hisob taxminiy (Mifflin–St Jeor). Kasallik, homiladorlik yoki emizish davrida shifokor bilan maslahatlashing.", "Расчёт примерный (Миффлин–Сан Жеор). При болезнях, беременности или кормлении — посоветуйтесь с врачом.", "Estimate (Mifflin–St Jeor). If ill, pregnant or breastfeeding, check with a doctor.")}</p>`;
}

// ------------------------------------------------------------------ 👑 admin panel (faqat pro-adminlar)
const AF = () => [["act", T("Faol", "Активные", "Active")], ["soon", T("Tugayapti", "Истекают", "Ending")],
  ["end", T("Tugagan", "Истёкшие", "Expired")], ["all", T("Hammasi", "Все", "All")]];
const AV = ["#C8344C", "#5B3FD8", "#E07A1F", "#1E8E62", "#2E6FD8", "#8A3FA8", "#B8892A", "#C2417F"];
const dd = (iso, y) => iso ? new Date(iso).toLocaleDateString("ru-RU", y ? {day: "2-digit", month: "2-digit", year: "numeric"} : {day: "2-digit", month: "2-digit"}) : "—";
const ini = (x) => esc(((x.n || x.u || "?").trim()[0] || "?").toUpperCase());
const avHtml = (x, cls) => `<i class="ka-av${cls ? " " + cls : ""}" style="background:${AV[x.id % AV.length]}">${ini(x)}</i>`;
const kun = (n) => T(`${n} kun`, `${n} дн.`, `${n} d`);
function adminCard() {
  const a = st && st.adm;
  if (!a) return "";
  return `<button class="ka-card" data-act="adm"><i>👑</i><span><b>${T("Admin panel", "Админ-панель", "Admin panel")}</b>
    <small>${T(`${a.act} faol obunachi · bugun +${a.today}`, `${a.act} активных · сегодня +${a.today}`, `${a.act} active · today +${a.today}`)}</small></span>
    ${a.wait ? `<em data-act="await">${T(`${a.wait} chek`, `${a.wait} чек.`, `${a.wait} receipts`)}</em>` : ""}<u>›</u></button>`;
}
function rowHtml(x) {
  const cls = x.d <= 0 ? "ka-end" : x.d <= 3 ? "ka-soon" : "ka-ok";   // «soon» — ilovada band klass nomi
  return `<button class="ka-u" data-uid="${x.id}">${avHtml(x)}<span class="ka-m"><b>${esc(x.n || (x.u ? "@" + x.u : "ID " + x.id))}</b>
    <small>${x.u ? "@" + esc(x.u) + " · " : ""}${x.id}</small></span><span class="ka-d ${cls}"><b>${dd(x.until)}</b><small>${x.d > 0 ? kun(x.d) : T("tugagan", "истекла", "expired")}</small></span></button>`;
}
function listHtml(v) {
  if (v.busy && !v.items) return `<div class="kl-dots"><i></i><i></i><i></i></div>`;
  if (v.err) return `<p class="kl-err">⚠️ ${v.err}</p>`;
  if (!v.items || !v.items.length) return `<p class="kl-empty">${v.q ? T("Topilmadi", "Не найдено", "Nothing found") : T("Bu ro'yxat bo'sh", "Список пуст", "This list is empty")}</p>`;
  return v.items.map(rowHtml).join("") + (v.items.length >= 500 ? `<p class="kl-fine">${T("Birinchi 500 tasi — qidiruvdan foydalaning", "Первые 500 — используйте поиск", "First 500 — use search")}</p>` : "");
}
function statsHtml(s) {
  s = s || {};
  return `<div class="ka-st"><div class="g"><b>${s.act ?? "…"}</b><small>${T("faol", "активных", "active")}</small></div>
    <div><b>+${s.today ?? 0}</b><small>${T("bugun", "сегодня", "today")}</small></div>
    <div class="w"><b>${s.soon ?? 0}</b><small>${T("3 kunda tugaydi", "истекают за 3 дня", "end in 3 days")}</small></div>
    <button class="r" data-act="await"><b>${s.wait ?? 0}</b><small>${T("chek kutmoqda", "чеков ждут", "receipts waiting")} ›</small></button></div>`;
}
function chipsHtml(v) {
  const s = v.stats || {};
  return AF().map(([k, l]) => `<button data-af="${k}" class="${v.f === k ? "on" : ""}">${l}${s[k] != null ? ` <em>${s[k]}</em>` : ""}</button>`).join("");
}
function sheetHtml(v) {
  const u = v.sel;
  if (!u) return "";
  const pct = u.on ? Math.min(100, Math.round(u.d / 90 * 100)) : 0;
  const hist = (u.hist || []).map((h) => `<div><b>${esc(h.a)}${h.by ? ` · ${esc(h.by)}` : ""}</b><span>${new Date(h.t * 1000).toLocaleString("ru-RU", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"})}</span></div>`).join("");
  const dis = v.work ? " disabled" : "";
  return `<div class="ka-dim" data-act="aclose"></div><div class="ka-sheet"><i class="ka-grab"></i>
    <div class="ka-who">${avHtml(u, "big")}<span><b>${esc(u.n || (u.u ? "@" + u.u : "ID " + u.id))}</b><small>${u.u ? "@" + esc(u.u) : T("username yo'q", "без username", "no username")}${u.bot ? "" : " · ⚠️ " + T("botni ochmagan", "не открывал бота", "never opened the bot")}</small>
      <button class="ka-cp" data-acp="${u.id}">🆔 ${u.id} · ${T("nusxa", "копия", "copy")}</button></span></div>
    <div class="ka-left ${u.on ? "" : "off"}"><div><b>${u.on ? kun(u.d) : T("Pro yo'q", "Нет Pro", "No Pro")}</b><span>${u.on ? T(`Pro faol<br>${dd(u.until, 1)} gacha`, `Pro активен<br>до ${dd(u.until, 1)}`, `Pro active<br>until ${dd(u.until, 1)}`) : u.until ? T(`${dd(u.until, 1)} da tugagan`, `истекла ${dd(u.until, 1)}`, `expired ${dd(u.until, 1)}`) : ""}</span></div><i><em style="width:${pct}%"></em></i></div>
    <div class="ka-lbl">➕ ${T("Qo'shish", "Добавить", "Add")}</div>
    <div class="ka-btns">${[1, 2, 3].map((m) => `<button data-chg="${m}"${dis}>+${m} ${T("oy", "мес", "mo")}</button>`).join("")}</div>
    ${u.on ? `<div class="ka-lbl">➖ ${T("Kamaytirish", "Уменьшить", "Reduce")} <span>— ${T("adashib ko'p berilgan bo'lsa", "если выдали лишнее", "if too much was given")}</span></div>
    <div class="ka-btns minus">${[1, 2, 3].map((m) => `<button data-chg="-${m}"${dis}>−${m} ${T("oy", "мес", "mo")}</button>`).join("")}</div>` : ""}
    ${hist ? `<div class="ka-lbl">${T("Tarix", "История", "History")}</div><div class="ka-hist">${hist}</div>` : ""}
    ${u.on ? `<button class="ka-cancel" data-act="acancel"${dis}>🚫 ${T("Obunani bekor qilish", "Отменить подписку", "Cancel subscription")}</button>` : ""}</div>`;
}
function viewAdm(v) {
  return `${head("👑 " + T("Obunachilar", "Подписчики", "Subscribers"))}
  <div id="kast">${statsHtml(v.stats || st.adm)}</div>
  <div class="ka-srch">🔎<input id="kaq" type="search" value="${esc(v.q || "")}" placeholder="${T("Ism, @username yoki ID", "Имя, @username или ID", "Name, @username or ID")}" autocomplete="off"></div>
  <div class="ka-chips" id="kachips">${chipsHtml(v)}</div>
  <div id="kalist">${listHtml(v)}</div>
  <div class="ka-pad"></div>
  <button class="ka-fab" data-act="aadd"><b>＋</b> ${T("Obuna qo'shish", "Добавить подписку", "Add subscription")}</button>
  ${sheetHtml(v)}`;
}
function admPaint(v) {   // qidiruvda input fokusi yo'qolmasin — faqat ro'yxat qismlari yangilanadi
  if (top() !== v || !$("kalist")) return render();
  $("kalist").innerHTML = listHtml(v); $("kast").innerHTML = statsHtml(v.stats || st.adm); $("kachips").innerHTML = chipsHtml(v);
}
let admTimer = null;
function admLoad(v) {
  v.busy = true; v.err = "";
  const seq = (v.seq || 0) + 1; v.seq = seq;
  api(`api/kal/adm/list?f=${v.f}&q=${encodeURIComponent(v.q || "")}`).then((r) => {
    if (v.seq !== seq) return;
    v.busy = false;
    if (r.ok) { v.items = r.items; v.stats = r.stats; st.adm = r.stats; } else v.err = ERR()[r.error] || ERR().server;
    admPaint(v);
  });
}
async function admOpenUser(v, id) {
  haptic();
  const r = await api(`api/kal/adm/user?q=${id}`);
  if (!r.ok) { toast(r.error === "nouser" ? T("Foydalanuvchi topilmadi", "Пользователь не найден", "User not found") : ERR()[r.error] || ERR().server); return; }
  v.sel = r.user; render();
}
function admAfter(v, r, okText) {
  v.work = false;
  if (!r.ok) { haptic("err"); toast(r.error === "nosub" ? T("Pro yo'q", "Нет Pro", "No Pro") : ERR()[r.error] || ERR().server); render(); return; }
  haptic("ok"); st.adm = r.stats; v.stats = r.stats;
  if (v.v === "adm") { v.sel = r.user; const it = (v.items || []).find((x) => x.id === r.user.id); if (it) { it.until = r.user.until; it.d = r.user.d; } }
  toast(okText(r.user) + (r.sent ? " · " + T("mijozga xabar bordi", "клиент уведомлён", "client notified") : ""));
  render();
}
async function admChange(v, uid, m, notify) {
  if (v.work) return;
  v.work = true; render();
  const r = await api("api/kal/adm/change", {id: uid, m, notify: notify !== false});
  admAfter(v, r, (u) => `${m > 0 ? "✅ +" + m : "➖ −" + -m} ${T("oy", "мес", "mo")} · ${u.on ? T(`${dd(u.until, 1)} gacha`, `до ${dd(u.until, 1)}`, `until ${dd(u.until, 1)}`) : T("Pro tugadi", "Pro закончился", "Pro ended")}`);
  return r;
}
function confirmBox(text, cb) {
  try { if (tg && tg.showConfirm) { tg.showConfirm(text, (ok) => { if (ok) cb(); }); return; } } catch (e) { /* eski versiya */ }
  if (window.confirm(text)) cb();
}
function viewAdd(v) {
  const u = v.found, m = v.m || 1;
  const base = u && u.on ? new Date(u.until) : new Date();
  const nu = new Date(base.getTime() + m * ((st.pro && st.pro.days) || 30) * 86400000);
  const look = v.look ? `<div class="kl-dots"><i></i><i></i><i></i></div>` : u ? `<div class="ka-found">${avHtml(u)}<span><b>${esc(u.n || (u.u ? "@" + u.u : "ID " + u.id))}</b>
      <small class="${u.on ? (u.d <= 3 ? "w" : "g") : ""}">${u.on ? T(`Pro: ${dd(u.until, 1)} gacha · ${kun(u.d)}`, `Pro: до ${dd(u.until, 1)} · ${kun(u.d)}`, `Pro: until ${dd(u.until, 1)} · ${kun(u.d)}`) : T("Pro yo'q", "Нет Pro", "No Pro")}</small></span><em>${T("Topildi ✓", "Найден ✓", "Found ✓")}</em></div>`
    : v.q && v.q.length >= 3 && v.miss ? `<p class="kl-err">⚠️ ${T("Bunday foydalanuvchi topilmadi. Mijoz botni kamida bir marta ochgan bo'lishi kerak.", "Пользователь не найден. Клиент должен хотя бы раз открыть бота.", "User not found. The client must have opened the bot at least once.")}</p>` : "";
  return `${head(T("Obuna qo'shish", "Добавить подписку", "Add subscription"))}
  <input id="kaid" class="ka-fld" inputmode="text" value="${esc(v.q || "")}" placeholder="${T("ID yoki @username", "ID или @username", "ID or @username")}" autocomplete="off">
  <p class="ka-hint">${T("Mijozning Telegram ID si yoki @username. Mijoz botni kamida bir marta ochgan bo'lishi kerak.", "Telegram ID клиента или @username. Клиент должен хотя бы раз открыть бота.", "The client's Telegram ID or @username. They must have opened the bot at least once.")}</p>
  ${look}
  <div class="ka-lbl">${T("Necha oy?", "Сколько месяцев?", "How many months?")}</div>
  <div class="ka-mo">${[1, 2, 3, 6, 12].map((k) => `<button data-am="${k}" class="${k === m ? "on" : ""}"><b>${k}</b><small>${T("oy", "мес", "mo")}</small></button>`).join("")}</div>
  ${u ? `<div class="ka-res"><span><small>${T("Yangi muddat", "Новый срок", "New end date")}</small><b>${T(`${dd(nu.toISOString(), 1)} gacha`, `до ${dd(nu.toISOString(), 1)}`, `until ${dd(nu.toISOString(), 1)}`)}</b></span><span><small>${T("Qo'shiladi", "Добавится", "Adds")}</small><b class="g">+${m * ((st.pro && st.pro.days) || 30)} ${T("kun", "дн.", "d")}</b></span></div>` : ""}
  <button class="ka-tgl" data-act="anotify"><span><b>${T("Mijozga xabar yuborish", "Уведомить клиента", "Notify the client")}</b><small>${T(`«Sizga ${m} oylik obuna berildi»`, `«Вам выдана подписка на ${m} мес.»`, `"You got a ${m}-month subscription"`)}</small></span><i class="${v.notify !== false ? "on" : ""}"></i></button>
  <p class="ka-note">${T("Faol obuna bo'lsa — qolgan muddat ustiga qo'shiladi. Har bir o'zgarish tarixga kim va qachon qilgani bilan yoziladi.", "Если подписка активна — срок добавится к оставшемуся. Каждое изменение пишется в историю.", "If active, the time is added on top. Every change is logged with who and when.")}</p>
  <div class="ka-pad"></div>
  <button class="kl-cta ka-give" data-act="agive"${u && !v.work ? "" : " disabled"}>✅ ${T(`${m} oylik obuna berish`, `Выдать подписку на ${m} мес.`, `Give ${m}-month subscription`)}</button>`;
}
let addTimer = null;
function addLook(v) {
  clearTimeout(addTimer);
  const q = (v.q || "").trim();
  v.found = null; v.miss = false;
  if (q.replace(/^@/, "").length < 3) { v.look = false; render(); return; }
  v.look = true; render();
  addTimer = setTimeout(async () => {
    const r = await api(`api/kal/adm/user?q=${encodeURIComponent(q)}`);
    if ((v.q || "").trim() !== q) return;
    v.look = false; v.found = r.ok ? r.user : null; v.miss = !r.ok;
    render();
  }, 450);
}

// ------------------------------------------------------------------ 🧾 kutilayotgan cheklar
const blobs = {};
function loadImg(pid) {
  if (blobs[pid]) return;
  blobs[pid] = "…";
  fetch(`api/kal/adm/photo?pid=${pid}`, {headers: {"X-Init-Data": inTg ? tg.initData : ""}, cache: "no-store"})
    .then((r) => r.ok ? r.blob() : Promise.reject(r.status))
    .then((b) => { blobs[pid] = b.type === "application/pdf" ? "pdf" : URL.createObjectURL(b); const el = document.querySelector(`[data-ph="${pid}"]`); if (el) el.outerHTML = photoHtml(pid); })
    .catch(() => { blobs[pid] = "err"; const el = document.querySelector(`[data-ph="${pid}"]`); if (el) el.outerHTML = photoHtml(pid); });
}
function photoHtml(pid) {
  const b = blobs[pid];
  if (!b || b === "…") return `<div class="ka-ph" data-ph="${pid}"><div class="kl-dots"><i></i><i></i><i></i></div></div>`;
  if (b === "pdf") return `<div class="ka-ph none" data-ph="${pid}">📄 PDF — ${T("to'lovlar kanalida ko'ring", "смотрите в канале платежей", "see the payments channel")}</div>`;
  if (b === "err") return `<div class="ka-ph none" data-ph="${pid}">⚠️ ${T("Rasmni yuklab bo'lmadi", "Не удалось загрузить фото", "Couldn't load the photo")}</div>`;
  return `<button class="ka-ph" data-ph="${pid}" data-zoom="${pid}"><img src="${b}" alt=""><span>🔍</span></button>`;
}
function waitHtml(x, v) {
  const busy = v.work === x.pid;
  const ago = (() => { const m = Math.max(0, Math.round((Date.now() - new Date(x.t).getTime()) / 60000)); return m < 60 ? T(`${m} daq oldin`, `${m} мин назад`, `${m} min ago`) : m < 1440 ? T(`${Math.round(m / 60)} soat oldin`, `${Math.round(m / 60)} ч назад`, `${Math.round(m / 60)} h ago`) : dd(x.t); })();
  return `<div class="ka-rc${busy ? " busy" : ""}" id="rc${x.pid}">
    <div class="ka-rh">${avHtml(x)}<span class="ka-m"><b>${esc(x.n || (x.u ? "@" + x.u : "ID " + x.id))}</b><small>${x.u ? "@" + esc(x.u) + " · " : ""}${x.id}</small></span><span class="ka-t">#${x.pid}<small>${ago}</small></span></div>
    ${x.dup ? `<p class="ka-warn">🚨 ${T(`Bu chek avval #${x.dup} to'lovda yuborilgan!`, `Этот чек уже был в платеже #${x.dup}!`, `This receipt was already used in #${x.dup}!`)}</p>` : ""}
    ${x.d > 0 ? `<p class="ka-info">⭐ ${T(`Hozir Pro: ${dd(x.until, 1)} gacha · ${kun(x.d)}`, `Сейчас Pro: до ${dd(x.until, 1)} · ${kun(x.d)}`, `Pro now: until ${dd(x.until, 1)} · ${kun(x.d)}`)}</p>` : ""}
    ${x.img ? photoHtml(x.pid) : ""}
    ${x.note ? `<p class="ka-ai">🤖 ${esc(x.note)}</p>` : ""}
    <div class="ka-btns ok">${[1, 2, 3].map((m) => `<button data-dec="${x.pid}:1:${m}"${busy ? " disabled" : ""}>✅ ${m} ${T("oy", "мес", "mo")}</button>`).join("")}</div>
    <button class="ka-bad" data-dec="${x.pid}:0:1"${busy ? " disabled" : ""}>⚠️ ${T("Shubhali — qayta so'rash", "Сомнительный — запросить снова", "Doubtful — ask again")}</button></div>`;
}
function viewWait(v) {
  const list = v.items == null ? `<div class="kl-dots"><i></i><i></i><i></i></div>`
    : !v.items.length ? `<div class="ka-done"><b>🎉</b><p>${T("Kutilayotgan chek yo'q", "Нет чеков в ожидании", "No receipts waiting")}</p></div>`
    : v.items.map((x) => waitHtml(x, v)).join("");
  return `${head("🧾 " + T("Cheklar", "Чеки", "Receipts") + (v.items && v.items.length ? ` <em class="ka-cnt">${v.items.length}</em>` : ""))}
  <p class="ka-hint">${T("Bank ilovasida pul tushganini tekshirib, tugmani bosing. Mijozga xabar avtomatik boradi.", "Проверьте поступление в банке и нажмите кнопку. Клиент получит сообщение.", "Check the money arrived in your bank app, then tap. The client is notified.")}</p>
  ${v.err ? `<p class="kl-err">⚠️ ${v.err}</p>` : ""}${list}${v.zoom ? `<button class="ka-zoom" data-act="unzoom"><img src="${blobs[v.zoom]}" alt=""></button>` : ""}`;
}
function waitLoad(v) {
  api("api/kal/adm/wait").then((r) => {
    if (r.ok) { v.items = r.items; st.adm = r.stats; r.items.forEach((x) => { if (x.img) loadImg(x.pid); }); } else v.err = ERR()[r.error] || ERR().server;
    if (top() === v) render();
  });
}
async function decideRc(v, pid, ok, m, force) {
  if (v.work) return;
  v.work = pid; render();
  const r = await api("api/kal/adm/decide", {pid, ok, m, force: !!force});
  v.work = null;
  if (r.error === "twin") {
    render();
    confirmBox(T(`Bu mijozga #${r.twin} chek bo'yicha Pro berilgan (cheklar bir vaqtda yuborilgan). Bitta to'lov ikki marta kelgan bo'lishi mumkin. Baribir ${m} oy berilsinmi?`,
      `Этому клиенту уже выдан Pro по чеку #${r.twin} (чеки пришли одновременно). Всё равно выдать ${m} мес.?`,
      `This client already got Pro from receipt #${r.twin} (sent at the same time). Give ${m} mo anyway?`), () => decideRc(v, pid, ok, m, true));
    return;
  }
  if (!r.ok && r.error !== "done") { haptic("err"); toast(ERR()[r.error] || ERR().server); render(); return; }
  haptic(ok ? "ok" : "err");
  if (r.stats) { st.adm = r.stats; }
  toast(r.error === "done" ? T("Bu chek allaqachon ko'rib chiqilgan", "Этот чек уже рассмотрен", "Already handled")
    : r.dup ? T(`🔁 Takror chek (#${r.dup}) — yopildi, Pro qo'shilmadi`, `🔁 Повтор (#${r.dup}) — закрыт без Pro`, `🔁 Duplicate (#${r.dup}) — closed, no Pro`)
    : ok ? T(`✅ Tasdiqlandi · ${m} oy · ${dd(r.until, 1)} gacha`, `✅ Подтверждено · ${m} мес · до ${dd(r.until, 1)}`, `✅ Approved · ${m} mo · until ${dd(r.until, 1)}`)
    : T("⚠️ Shubhali — mijozdan qayta chek so'raldi", "⚠️ Сомнительный — клиент пришлёт снова", "⚠️ Doubtful — client asked to resend"));
  const el = $("rc" + pid);
  if (el) el.classList.add("gone");
  setTimeout(() => { v.items = (v.items || []).filter((x) => x.pid !== pid); if (top() === v) render(); }, 260);
}

// ------------------------------------------------------------------ 3. to'lov (karta + chek)
function viewPay(v) {
  const pr = st.pro || {}, pay = pr.pay;
  const cards = pr.cards || [];
  const status = pay && pay.status === "wait"
    ? `<div class="kl-stat"><b>⏳ ${T("Chekingiz tekshirilmoqda", "Чек проверяется", "Your receipt is being checked")}</b><small>${T("Odatda bir necha daqiqa. Tasdiqlangach Pro shu yerda o'zi ochiladi va botga xabar keladi.", "Обычно несколько минут. После подтверждения Pro откроется здесь, а в бот придёт сообщение.", "Usually a few minutes. Once confirmed, Pro opens here and the bot messages you.")}</small></div>`
    : pay && pay.status === "bad"
      ? `<div class="kl-stat kl-stat-bad"><b>⚠️ ${T("Chek shubhali deb topildi", "Чек вызвал сомнения", "The receipt looked doubtful")}</b><small>${T("To'lov chekini qaytadan, aniq (summa va sana ko'rinadigan) qilib yuklang.", "Загрузите чек ещё раз — чётко, с суммой и датой.", "Upload the receipt again — clear, with amount and date visible.")}</small></div>` : "";
  return head(T("Pro'ni ochish", "Открыть Pro", "Unlock Pro")) + `
  <div class="kl-price"><b>${nf(pr.price)}</b><span>${T("so'm", "сум", "UZS")}</span><small>${T(`${pr.days} kun uchun · avtomatik yechilmaydi`, `за ${pr.days} дней · без автосписания`, `for ${pr.days} days · no auto-renewal`)}</small></div>
  ${status}
  ${!cards.length ? `<p class="kl-note">⏳ ${T("To'lov tez orada ochiladi.", "Оплата скоро откроется.", "Payment opens soon.")}</p>` : `
  <div class="kl-step"><i>1</i><span>${T("Shu kartalardan biriga o'tkazing", "Переведите на одну из карт", "Transfer to one of these cards")}</span></div>
  ${cards.map((c, i) => `<div class="kl-card ${c.k}"><div><small>${c.k === "uz" ? "🇺🇿 " : "🌍 "}${esc(c.net || (c.k === "uz" ? "Uzcard / Humo" : "Visa / Mastercard"))}</small>
      <b>${esc(c.num)}</b><em>${esc(c.name || "")}</em></div><button data-copy="${i}">${v.copied === i ? "✓" : T("Nusxa", "Копир.", "Copy")}</button></div>`).join("")}
  <div class="kl-step"><i>2</i><span>${T("To'lov chekini (skrinshot) yuklang", "Загрузите чек (скриншот)", "Upload the receipt (screenshot)")}</span></div>
  ${pay && pay.status === "wait" ? "" : `<label class="kl-cta kl-up">📎 ${v.up ? T("Yuklanmoqda…", "Загрузка…", "Uploading…") : T("Chekni yuklash", "Загрузить чек", "Upload receipt")}<input type="file" id="klrcpt" accept="image/*" hidden${v.up ? " disabled" : ""}></label>`}
  <div class="kl-step"><i>3</i><span>${T("Admin tekshiradi — Pro shu yerda ochiladi", "Админ проверит — Pro откроется здесь", "An admin checks it — Pro opens here")}</span></div>
  ${v.err ? `<p class="kl-err">⚠️ ${v.err}</p>` : ""}
  ${pr.bot ? `<button class="kl-link" data-act="bot">${T("yoki chekni botga yuboring →", "или отправьте чек боту →", "or send the receipt to the bot →")}</button>` : ""}`}`;
}
async function uploadReceipt(file) {
  const v = top();
  v.up = true; v.err = ""; render();
  const s = await shrink(file, 1600);
  const fd = new FormData(); fd.append("photo", s.blob, "chek.jpg");
  const r = await api("api/kal/receipt", null, fd);
  v.up = false;
  if (!r.ok) { v.err = ERR()[r.error] || ERR().server; haptic("err"); render(); return; }
  st = r; haptic("ok"); render(); startPoll();
}
function startPoll() {
  stopPoll();
  if (!(st && st.pro && st.pro.pay && st.pro.pay.status === "wait")) return;
  poll = setInterval(async () => {
    if (!opened || document.hidden) return;
    const was = st && st.pro && st.pro.on;
    const r = await api("api/kal");
    if (!r.ok) return;
    st = r;
    if (r.pro.on && !was) { stopPoll(); haptic("ok"); stack.length = 1; render(); toast(T("🎉 Pro faollashdi!", "🎉 Pro активирован!", "🎉 Pro is active!")); return; }
    if (!(r.pro.pay && r.pro.pay.status === "wait")) { stopPoll(); render(); }
  }, 15000);
}
function stopPoll() { if (poll) { clearInterval(poll); poll = null; } }

// ------------------------------------------------------------------ 4. Pro: kunlik hisob
function viewTrack(v) {
  const r = st.r, pr = st.pro;
  const d = st.day || {eaten: 0, items: [], by_meal: {}, macro: {p: 0, f: 0, c: 0}};
  const goal = r.kcal, left = goal - d.eaten, pct = Math.min(100, Math.round(d.eaten / goal * 100)), over = left < 0;
  const bar = (k, n, col) => `<div class="kl-mb"><span>${n}</span><i><em style="width:${Math.min(100, Math.round(((d.macro && d.macro[k]) || 0) / Math.max(1, (r.macro && r.macro[k]) || 1) * 100))}%;background:${col}"></em></i><small>${(d.macro && d.macro[k]) || 0}/${(r.macro && r.macro[k]) || 0}</small></div>`;
  const list = d.items.length ? MEALS.map(([mk, e]) => {
    const its = d.items.filter((x) => x.m === mk);
    if (!its.length) return "";
    return `<div class="kl-ml"><span>${e} ${MEAL[mk]}</span><b>${nf(d.by_meal[mk] || 0)}</b></div>` +
      its.map((x) => `<div class="kl-it"><span>${x.src === "p" ? "📸" : "✍️"} ${esc(x.n)}${x.g ? ` <small>${x.g} g</small>` : ""}</span><b>${nf(x.kcal)}</b><button data-del="${x.id}" aria-label="${T("O'chirish", "Удалить", "Delete")}">✕</button></div>`).join("");
  }).join("") : `<p class="kl-empty">${T("Bugun hali hech narsa qo'shilmagan. Birinchi ovqatni suratga oling 👇", "Сегодня пока пусто. Сфотографируйте первую еду 👇", "Nothing logged yet today. Snap your first meal 👇")}</p>`;
  const u = pr.until ? new Date(pr.until) : null;
  return rootHead() + `
  <div class="kl-today"><div class="kl-ring" style="--p:${pct};--c:${over ? "#FF7A59" : "var(--acc)"}"><b>${nf(d.eaten)}</b><small>/ ${nf(goal)} ${kk()}</small></div>
    <div class="kl-sum"><b class="${over ? "over" : ""}">${over ? T(`${nf(-left)} kkal oshdi`, `+${nf(-left)} ккал сверх`, `${nf(-left)} kcal over`) : T(`Yana ${nf(left)} kkal`, `Ещё ${nf(left)} ккал`, `${nf(left)} kcal left`)}</b>
      ${bar("p", T("Oqsil", "Белки", "Protein"), "#7CC7FF")}${bar("f", T("Yog'", "Жиры", "Fat"), "#FFC857")}${bar("c", T("Uglevod", "Углев.", "Carbs"), "var(--acc)")}</div></div>
  <div class="kl-acts2"><label class="kl-cam">📸 ${T("Ovqatni suratga olish", "Сфотографировать еду", "Snap a meal")}<input type="file" id="klfile" accept="image/*" capture="environment" hidden></label>
    <button class="kl-txt" data-act="txt" aria-label="${T("Yozib qo'shish", "Добавить текстом", "Add by text")}">✍️</button></div>
  ${v.txt ? `<div class="kl-tin"><input id="kltext" placeholder="${T("Masalan: 2 ta somsa va choy", "Например: 2 самсы и чай", "e.g. 2 samsa and tea")}" autocomplete="off"><button data-act="send">${T("Hisoblash", "Посчитать", "Count")}</button></div>` : ""}
  <div class="kl-list">${list}</div>
  <div class="kl-foot"><button class="kl-link" data-act="plan">📋 ${T("Rejam", "Мой план", "My plan")}</button><button class="kl-link" data-act="edit">✏️ ${T("Ma'lumotlar", "Данные", "Details")}</button></div>
  ${u ? `<p class="kl-fine">⭐ Pro · ${T(`${u.toLocaleDateString("ru-RU")} gacha`, `до ${u.toLocaleDateString("ru-RU")}`, `until ${u.toLocaleDateString("en-GB")}`)}</p>` : ""}`;
}
function viewScan(v) {
  const h = head(T("Ovqat tahlili", "Анализ еды", "Meal analysis"));
  const back = `<button class="kl-cta" data-act="back">${T("Orqaga", "Назад", "Back")}</button>`;
  if (v.busy) return h + `<div class="kl-wait">${v.preview ? `<img src="${v.preview}" alt="">` : ""}<div class="kl-dots"><i></i><i></i><i></i></div><p>${T("Taom hisoblanmoqda…", "Считаем блюдо…", "Counting the meal…")}</p></div>`;
  if (v.err) return h + `<div class="kl-wait"><p class="kl-err">⚠️ ${v.err}</p>${back}</div>`;
  if (!v.items.length) return h + `<div class="kl-wait">${v.preview ? `<img src="${v.preview}" alt="">` : ""}<p>${T("Rasmda ovqat topilmadi. Yaqinroqdan, yorug' joyda suratga oling.", "Еда на фото не найдена. Снимите ближе, при хорошем свете.", "No food found. Shoot closer, in good light.")}</p>${back}</div>`;
  const tot = v.items.reduce((a, x) => a + x.kcal, 0);
  return h + `${v.preview ? `<div class="kl-pv"><img src="${v.preview}" alt=""></div>` : ""}
    <div class="kl-tot"><small>${T("Jami", "Итого", "Total")}</small><b>${nf(tot)} ${kk()}</b></div>
    <div class="kl-items">${v.items.map((x, i) => `<div class="kl-si"><span><b>${esc(x.n)}</b><small>${x.p}/${x.f}/${x.c} g</small></span>
      <span class="g"><button data-g="${i}:-1">−</button><em>${x.g} g</em><button data-g="${i}:1">+</button></span><b class="k">${nf(x.kcal)}</b><button class="x" data-x="${i}">✕</button></div>`).join("")}</div>
    <div class="kl-mealpick">${MEALS.map(([k, e]) => `<button data-meal="${k}" class="${v.meal === k ? "on" : ""}">${e} ${MEAL[k]}</button>`).join("")}</div>
    <p class="kl-fine">${T("Taxminiy hisob ±20%. Porsiya boshqacha bo'lsa — grammni −/+ bilan to'g'rilang.", "Примерный подсчёт ±20%. Поправьте граммы −/+, если порция другая.", "Estimate ±20%. Adjust grams with −/+ if needed.")}</p>
    <button class="kl-cta" data-act="add"${v.adding ? " disabled" : ""}>✅ ${T("Kunlikka qo'shish", "Добавить в день", "Add to today")}</button>`;
}
function shrink(file, max) {
  return new Promise((ok) => {
    const url = URL.createObjectURL(file), img = new Image();
    img.onload = () => {
      const k = Math.min(1, (max || 1024) / Math.max(img.width, img.height));
      const c = document.createElement("canvas"); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      const g = c.getContext("2d");
      g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);   // shaffof PNG chek JPEG da qop-qora bo'lmasin
      g.drawImage(img, 0, 0, c.width, c.height);
      c.toBlob((b) => { URL.revokeObjectURL(url); ok({blob: b || file, preview: c.toDataURL("image/jpeg", 0.6)}); }, "image/jpeg", 0.82);
    };
    img.onerror = () => { URL.revokeObjectURL(url); ok({blob: file, preview: ""}); };
    img.src = url;
  });
}
async function scan(file, text) {
  const v = {v: "scan", busy: true, items: [], meal: "l", preview: ""};
  go(v);
  let r;
  if (file) {
    const s = await shrink(file, 1024); v.preview = s.preview; render();
    const fd = new FormData(); fd.append("photo", s.blob, "meal.jpg");
    r = await api("api/food/kcal/scan", null, fd);
  } else r = await api("api/food/kcal/scan", {text});
  v.busy = false;
  if (!r.ok) { v.err = (ERR()[r.error] || ERR().ai_fail) + (r.detail ? " · " + r.detail : ""); haptic("err"); if (top() === v) render(); return; }
  v.items = r.items.map((x) => Object.assign({}, x, {_g: x.g || 100, _k: x.kcal, _p: x.p, _f: x.f, _c: x.c}));
  v.meal = r.meal || "l"; v.src = r.src; haptic("ok");
  if (top() === v) render();
}
function scaleItem(x, g) {
  const k = g / Math.max(1, x._g);
  x.g = g; x.kcal = Math.round(x._k * k); x.p = Math.round(x._p * k); x.f = Math.round(x._f * k); x.c = Math.round(x._c * k);
}
async function addScan() {
  const v = top();
  if (v.adding || !v.items.length) return;
  v.adding = true; render();
  let r = null;
  try {
    r = await api("api/food/kcal/add", {meal: v.meal, src: v.src || "p", items: v.items.map(({uz, ru, en, g, kcal, p, f, c}) => ({uz, ru, en, g, kcal, p, f, c}))});
  } catch (e) {}
  v.adding = false;
  if (r && r.ok && r.day) {
    st.day = r.day;
  } else {
    if (!st.day) st.day = {eaten: 0, items: [], by_meal: {}, macro: {p: 0, f: 0, c: 0}};
    if (!st.day.by_meal) st.day.by_meal = {};
    if (!st.day.macro) st.day.macro = {p: 0, f: 0, c: 0};
    v.items.forEach((it, idx) => {
      const addedKcal = it.kcal || 0;
      st.day.eaten = (st.day.eaten || 0) + addedKcal;
      st.day.by_meal[v.meal] = (st.day.by_meal[v.meal] || 0) + addedKcal;
      st.day.macro.p = (st.day.macro.p || 0) + (it.p || 0);
      st.day.macro.f = (st.day.macro.f || 0) + (it.f || 0);
      st.day.macro.c = (st.day.macro.c || 0) + (it.c || 0);
      st.day.items.push({
        id: Date.now() + idx,
        m: v.meal,
        src: v.src || "p",
        n: it.uz || it.ru || it.en || "Taom",
        g: it.g || 100,
        kcal: addedKcal,
        p: it.p || 0,
        f: it.f || 0,
        c: it.c || 0
      });
    });
  }
  try { localStorage.setItem("zk_kal_st_v1", JSON.stringify(st)); } catch (e) {}
  haptic("ok"); stack.pop(); render(); scrollTop();
}

// ------------------------------------------------------------------ chizish va boshqaruv
function scrollTop() { const s = $("klscroll"); if (s) s.scrollTop = 0; }
function render() {
  const el = $("klview");
  if (!el) return;
  const v = top();
  let html;
  if (!st) { load().then(() => { if (opened) render(); }); html = `${rootHead()}<div class="kl-dots big"><i></i><i></i><i></i></div>`; }
  else if (v.v === "root") {
    html = !st.p ? viewForm(v) : st.pro && st.pro.on && st.pro.ai ? viewTrack(v) : viewPlan();
    const bar = rootHead();
    if (st.adm) html = html.indexOf(bar) === 0 ? bar + adminCard() + html.slice(bar.length) : adminCard() + html;
  }
  else if (v.v === "adm") html = viewAdm(v);
  else if (v.v === "ada") html = viewAdd(v);
  else if (v.v === "adw") html = viewWait(v);
  else if (v.v === "edit") html = viewForm(v);
  else if (v.v === "plan") html = head(T("Rejam", "Мой план", "My plan")) + viewPlan().replace(/^<div class="kl-head-clean">[\s\S]*?<\/div>/, "");
  else if (v.v === "pay") html = viewPay(v);
  else if (v.v === "scan") html = viewScan(v);
  else html = "";
  const ae = document.activeElement, fid = ae && ae.id && el.contains(ae) && ae.tagName === "INPUT" ? ae.id : "";
  const sel = fid ? [ae.selectionStart, ae.selectionEnd] : null;
  el.innerHTML = html;
  if (fid && $(fid)) { const i = $(fid); i.focus(); try { i.setSelectionRange(sel[0], sel[1]); } catch (e) { /* type=search */ } }   // yozayotganda fokus yo'qolmasin
  $("kal").dataset.v = v.v;
  updateBack();
}
function go(v) { stack.push(v); haptic(); render(); scrollTop(); }
function back() {
  if (top().sel) { top().sel = null; render(); return; }      // avval mijoz kartochkasi yopiladi
  if (top().zoom) { top().zoom = null; render(); return; }
  if (stack.length > 1) { const w = stack.pop(); if (w.v === "pay") stopPoll(); if ((w.v === "ada" || w.v === "adw") && top().v === "adm") admLoad(top()); render(); }
  else {
    if (window.ZK_setMode) window.ZK_setMode("kino");
    else window.ZKal.close();
  }
}
function updateBack() {
  if (!tg || !tg.BackButton) return;
  try {
    if (opened) tg.BackButton.show();
    else if (!window.ZK_canHideBack || window.ZK_canHideBack()) tg.BackButton.hide();
  } catch (e) {}
}
function onClick(e) {
  const t = e.target;
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "kal" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  const sx = t.closest("[data-sex]");
  if (sx) { readForm(); top().f.sex = sx.dataset.sex; haptic(); render(); return; }
  const ka = t.closest("[data-kact]");
  if (ka) { readForm(); top().f.activity = +ka.dataset.kact; haptic(); render(); return; }
  const km = t.closest("[data-months]");
  if (km) { readForm(); top().f.months = +km.dataset.months; haptic(); render(); return; }
  const cp = t.closest("[data-copy]");
  if (cp) {
    const c = st.pro.cards[+cp.dataset.copy], num = String(c.num || "").replace(/\s/g, "");
    const done = () => { top().copied = +cp.dataset.copy; haptic("ok"); render(); toast(T("Karta raqami nusxalandi", "Номер карты скопирован", "Card number copied")); };
    try { navigator.clipboard.writeText(num).then(done, done); } catch (er) { done(); }
    return;
  }
  const g = t.closest("[data-g]");
  if (g) { const [i, d] = g.dataset.g.split(":").map(Number), x = top().items[i]; if (x) { const s = Math.max(10, Math.round(x._g * 0.1 / 10) * 10); scaleItem(x, Math.max(s, Math.min(3000, x.g + d * s))); haptic(); render(); } return; }
  const x = t.closest("[data-x]");
  if (x) { top().items.splice(+x.dataset.x, 1); haptic(); render(); return; }
  const ml = t.closest("[data-meal]");
  if (ml) { top().meal = ml.dataset.meal; haptic(); render(); return; }
  const af = t.closest("[data-af]");
  if (af) { const v = top(); v.f = af.dataset.af; v.items = null; haptic(); admLoad(v); admPaint(v); return; }
  const ui = t.closest("[data-uid]");
  if (ui) { admOpenUser(top(), +ui.dataset.uid); return; }
  const ch = t.closest("[data-chg]");
  if (ch) {
    const v = top(), m = +ch.dataset.chg;
    if (!v.sel) return;
    if (m < 0) confirmBox(T(`${v.sel.n || v.sel.id} — ${-m} oy kamaytirilsinmi?`, `${v.sel.n || v.sel.id} — уменьшить на ${-m} мес.?`, `Reduce ${v.sel.n || v.sel.id} by ${-m} mo?`), () => admChange(v, v.sel.id, m));
    else admChange(v, v.sel.id, m);
    return;
  }
  const dc = t.closest("[data-dec]");
  if (dc) {
    const [pid, ok, m] = dc.dataset.dec.split(":").map(Number), v = top();
    if (ok) decideRc(v, pid, true, m);
    else confirmBox(T(`#${pid} — chek shubhali deb qaytarilsinmi? Mijozdan qayta chek so'raladi.`, `#${pid} — отметить как сомнительный? Клиента попросят прислать снова.`, `#${pid} — mark as doubtful? The client will be asked to resend.`), () => decideRc(v, pid, false, 1));
    return;
  }
  const zm = t.closest("[data-zoom]");
  if (zm) { top().zoom = +zm.dataset.zoom; haptic(); render(); return; }
  const am = t.closest("[data-am]");
  if (am) { top().m = +am.dataset.am; haptic(); render(); return; }
  const acp = t.closest("[data-acp]");
  if (acp) { const s = acp.dataset.acp, done = () => { haptic("ok"); toast(T("ID nusxalandi", "ID скопирован", "ID copied")); }; try { navigator.clipboard.writeText(s).then(done, done); } catch (er) { done(); } return; }
  const dl = t.closest("[data-del]");
  if (dl) {
    const delId = +dl.dataset.del;
    const removeLocal = () => {
      if (st && st.day && st.day.items) {
        const itemIdx = st.day.items.findIndex((x) => x.id === delId);
        if (itemIdx >= 0) {
          const it = st.day.items[itemIdx];
          st.day.items.splice(itemIdx, 1);
          st.day.eaten = Math.max(0, (st.day.eaten || 0) - (it.kcal || 0));
          if (st.day.by_meal && st.day.by_meal[it.m]) {
            st.day.by_meal[it.m] = Math.max(0, st.day.by_meal[it.m] - (it.kcal || 0));
          }
          if (st.day.macro) {
            st.day.macro.p = Math.max(0, (st.day.macro.p || 0) - (it.p || 0));
            st.day.macro.f = Math.max(0, (st.day.macro.f || 0) - (it.f || 0));
            st.day.macro.c = Math.max(0, (st.day.macro.c || 0) - (it.c || 0));
          }
        }
      }
      try { localStorage.setItem("zk_kal_st_v1", JSON.stringify(st)); } catch (e) {}
      haptic(); render();
    };
    api("api/food/kcal/del", {id: delId}).then((r) => {
      if (r && r.ok && r.day) {
        st.day = r.day;
        try { localStorage.setItem("zk_kal_st_v1", JSON.stringify(st)); } catch (e) {}
        haptic(); render();
      } else {
        removeLocal();
      }
    }).catch(removeLocal);
    return;
  }
  const a = t.closest("[data-act]");
  if (!a) return;
  const act = a.dataset.act, v = top();
  if (act === "back") back();
  else if (act === "homeback") {
    if (window.ZK_setMode) window.ZK_setMode("kino");
    else window.ZKal.close();
  }
  else if (act === "hub") {
    if (window.ZHub) window.ZHub.open("kal");
  }
  else if (act === "calc") calc();
  else if (act === "force") setForce(true);
  else if (act === "unforce") setForce(false);
  else if (act === "edit") go({v: "edit"});
  else if (act === "plan") go({v: "plan"});
  else if (act === "start") { go({v: "pay"}); startPoll(); }
  else if (act === "bot") { const url = `https://t.me/${st.pro.bot}?start=pro`; try { tg.openTelegramLink(url); } catch (er) { location.href = url; } }
  else if (act === "txt") { v.txt = !v.txt; haptic(); render(); if (v.txt) setTimeout(() => { const i = $("kltext"); if (i) i.focus(); }, 50); }
  else if (act === "send") { const i = $("kltext"), s = i ? i.value.trim() : ""; if (s.length >= 2) { v.txt = false; scan(null, s); } }
  else if (act === "add") addScan();
  else if (act === "await") { const w = {v: "adw"}; go(w); waitLoad(w); }
  else if (act === "unzoom") { v.zoom = null; render(); }
  else if (act === "adm") { const w = {v: "adm", f: "act", q: ""}; go(w); admLoad(w); }
  else if (act === "aclose") { v.sel = null; render(); }
  else if (act === "aadd") go({v: "ada", m: 1, notify: true});
  else if (act === "anotify") { v.notify = v.notify === false; haptic(); render(); }
  else if (act === "acancel" && v.sel) {
    const u = v.sel;
    confirmBox(T(`${u.n || u.id} — obuna bekor qilinsinmi? Pro darhol yopiladi.`, `${u.n || u.id} — отменить подписку? Pro закроется сразу.`, `Cancel ${u.n || u.id}'s subscription? Pro closes immediately.`), async () => {
      if (v.work) return;
      v.work = true; render();
      const r = await api("api/kal/adm/cancel", {id: u.id, notify: true});
      admAfter(v, r, () => "🚫 " + T("Obuna bekor qilindi", "Подписка отменена", "Subscription cancelled"));
    });
  }
  else if (act === "agive" && v.found && !v.work) {
    admChange(v, v.found.id, v.m || 1, v.notify).then((r) => { if (r && r.ok) { v.found = r.user; v.q = ""; v.found = null; back(); } });
  }
}
if (tg && tg.BackButton) tg.BackButton.onClick(() => { if (opened) back(); });

window.ZKal = {
  open() {
    if (!mounted) {
      mounted = true;
      const root = $("kal");
      root.addEventListener("click", onClick);
      root.addEventListener("change", (e) => {
        const f = e.target.files && e.target.files[0];
        if (!f) return;
        e.target.value = "";
        if (e.target.id === "klfile") scan(f);
        else if (e.target.id === "klrcpt") uploadReceipt(f);
      });
      root.addEventListener("input", (e) => {
        if (e.target.id === "kaq") { const v = top(); v.q = e.target.value; clearTimeout(admTimer); admTimer = setTimeout(() => admLoad(v), 300); }
        else if (e.target.id === "kaid") {
          const v = top(); v.q = e.target.value; addLook(v);
        }
      });
      root.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id === "kltext") { e.preventDefault(); const b = root.querySelector('[data-act="send"]'); if (b) b.click(); } });
    }
    opened = true;
    $("kal").hidden = false; document.body.classList.add("kl-on");
    render();
    load().then(() => { if (opened) { render(); if (top().v === "pay") startPoll(); } });
  },
  close() {
    opened = false; stopPoll();
    $("kal").hidden = true; document.body.classList.remove("kl-on");
    updateBack();
  },
  busy() { return opened && stack.length > 1; },
};
})();
