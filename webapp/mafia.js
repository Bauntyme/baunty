/* 🔪 Mafia — onlayn o'yin (3–20 kishi). Server: /api/mafia/*. window.ZMafia {open, close, busy, join(code)}.
   Qahramonlar — kod bilan chizilgan SVG (MCHAR). Bosqichlar serverda; bu fayl ko'rsatadi, animatsiya qiladi, chat yuritadi. */
(() => {
"use strict";
const tg = window.Telegram && Telegram.WebApp;
const inTg = !!(tg && tg.initData);
const T = window.ZK_T || ((u) => u);
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const haptic = (t) => { try { t === "ok" ? tg.HapticFeedback.notificationOccurred("success") : t === "err" ? tg.HapticFeedback.notificationOccurred("error") : t === "hit" ? tg.HapticFeedback.impactOccurred("heavy") : tg.HapticFeedback.selectionChanged(); } catch (e) {} };
const lsGet = (k, d) => { try { const v = JSON.parse(localStorage.getItem(k) || "null"); return v == null ? d : v; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };

// =================================================================== qahramonlar (SVG)
const MC = (() => {
let uid = 0;
const id = (p) => p + (++uid) + "m";
let VAR = null;
function face(o) {
  const g = id("sk"), s = o.skin, sd = o.skinD;
  const brow = {angry: ["M70 84 L94 92", "M130 84 L106 92"], calm: ["M70 86 Q82 80 94 86", "M106 86 Q118 80 130 86"], up: ["M70 84 Q82 76 94 82", "M106 82 Q118 76 130 84"]}[o.brow || "calm"];
  const mouth = {smirk: '<path d="M88 128 Q102 134 114 124" fill="none" stroke="#5A2A1E" stroke-width="3.2" stroke-linecap="round"/>',
    smile: '<path d="M84 122 Q100 140 116 122 Q100 130 84 122Z" fill="#7A2A22"/><path d="M88 124 Q100 130 112 124" fill="#fff"/>',
    flat: '<path d="M88 127 H112" stroke="#5A2A1E" stroke-width="3.2" stroke-linecap="round"/>',
    grin: '<path d="M82 120 Q100 144 118 120 Z" fill="#6A1E18"/><path d="M85 121 Q100 129 115 121" fill="#fff"/>'}[o.mouth || "flat"];
  const eye = (x) => o.glasses === "sun" ? "" : `<ellipse cx="${x}" cy="100" rx="9.5" ry="${o.squint ? 4.5 : 7.5}" fill="#fff"/><circle cx="${x + 1}" cy="100.5" r="${o.squint ? 3.6 : 5.2}" fill="${o.iris || "#3A2414"}"/><circle cx="${x + 1}" cy="100.5" r="2.4" fill="#0A0605"/><circle cx="${x + 3}" cy="98" r="1.6" fill="#fff"/>`;
  return `<defs><radialGradient id="${g}" cx=".42" cy=".38" r=".7"><stop offset="0" stop-color="${s}"/><stop offset=".75" stop-color="${s}"/><stop offset="1" stop-color="${sd}"/></radialGradient></defs>
   <rect x="88" y="132" width="24" height="26" fill="${sd}"/><ellipse cx="54" cy="104" rx="8" ry="12" fill="${sd}"/><ellipse cx="146" cy="104" rx="8" ry="12" fill="${sd}"/>
   <path d="M54 92 Q54 46 100 46 Q146 46 146 92 L144 112 Q138 146 100 150 Q62 146 56 112 Z" fill="url(#${g})"/>
   ${o.cheeks ? `<ellipse cx="72" cy="118" rx="9" ry="5" fill="#E07A6A" opacity=".35"/><ellipse cx="128" cy="118" rx="9" ry="5" fill="#E07A6A" opacity=".35"/>` : ""}
   ${eye(82)}${eye(118)}
   <path d="${brow[0]}" stroke="${o.browC || "#2A1A12"}" stroke-width="5" stroke-linecap="round" fill="none"/><path d="${brow[1]}" stroke="${o.browC || "#2A1A12"}" stroke-width="5" stroke-linecap="round" fill="none"/>
   <path d="M100 100 Q96 114 100 116 Q104 117 106 114" fill="none" stroke="${sd}" stroke-width="3" stroke-linecap="round"/>${mouth}`;
}
function body(o) {
  if (VAR) o = Object.assign({}, o, VAR);
  const c = id("cl"), c2 = o.cloth2 || o.cloth;
  return `<defs><linearGradient id="${c}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${o.cloth}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>
   <path d="M30 300 L34 210 Q40 168 78 156 L100 164 L122 156 Q160 168 166 210 L170 300 Z" fill="url(#${c})"/><path d="M34 210 Q40 168 78 156" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="3"/>`;
}
const rim = (col) => `<path d="M146 92 L144 112 Q138 146 100 150" fill="none" stroke="${col}" stroke-width="3.5" opacity=".75"/><path d="M166 210 L170 300" stroke="${col}" stroke-width="3.5" opacity=".6"/>`;
const C = {
  don: () => `${body({cloth: "#23232E", cloth2: "#0E0E14"})}<g opacity=".35" stroke="#8A8AA0" stroke-width="1.2">${[46, 62, 78, 122, 138, 154].map((x) => `<path d="M${x} 190 L${x - (x < 100 ? 6 : -6)} 300"/>`).join("")}</g>
   <path d="M78 156 L100 236 L122 156 L112 154 L100 170 L88 154 Z" fill="#0A0A0E"/><path d="M94 168 L100 162 L106 168 L104 230 L100 240 L96 230 Z" fill="#C21E2C"/>
   ${face({skin: "#E3B48E", skinD: "#B9845E", brow: "angry", mouth: "smirk", squint: 1})}<path d="M68 108 L76 128" stroke="#9A4A3A" stroke-width="2.6" stroke-linecap="round"/><path d="M86 118 Q100 112 114 118 Q100 116 86 118Z" fill="#2A1A12"/>
   <g><rect x="112" y="122" width="40" height="7" rx="3" fill="#7A4A26"/><rect x="146" y="122" width="7" height="7" rx="2" fill="#FF7A2A"/></g>
   <ellipse cx="100" cy="62" rx="74" ry="14" fill="#101016"/><path d="M50 62 Q52 20 100 18 Q148 20 150 62 Z" fill="#181820"/><path d="M52 52 H148 V62 H52Z" fill="#C21E2C"/>${rim("#FF5A63")}`,
  qotil: () => `${body({cloth: "#2E1E18", cloth2: "#120A08"})}<path d="M78 156 L100 200 L122 156" fill="#0A0A0A"/><path d="M60 172 L70 300 M140 172 L130 300" stroke="#4A2E22" stroke-width="5"/>
   ${face({skin: "#C99470", skinD: "#9A6A4A", brow: "angry", mouth: "flat", glasses: "sun"})}<rect x="66" y="92" width="30" height="17" rx="6" fill="#0A0A10"/><rect x="104" y="92" width="30" height="17" rx="6" fill="#0A0A10"/><path d="M96 98 H104" stroke="#0A0A10" stroke-width="4"/>
   <path d="M60 128 Q100 160 140 128 L142 150 Q100 172 58 150 Z" fill="#8A1420"/><path d="M52 78 Q50 34 100 30 Q150 34 148 78 Q100 64 52 78Z" fill="#14141A"/><path d="M52 78 Q100 64 148 78 L150 86 Q100 72 50 86Z" fill="#26262E"/>${rim("#FF5A63")}`,
  doc: () => `${body({cloth: "#F4F6FA", cloth2: "#C9D2DE"})}<path d="M78 156 L100 196 L122 156 Z" fill="#2FA36A"/><path d="M90 160 L100 196 L110 160 Z" fill="#E9F0F6"/>
   <path d="M74 160 Q60 200 84 216 Q100 224 116 216 Q140 200 126 160" fill="none" stroke="#2A2F3A" stroke-width="4"/><circle cx="100" cy="222" r="8" fill="#9AA6B4" stroke="#2A2F3A" stroke-width="3"/>
   <rect x="128" y="236" width="22" height="22" rx="4" fill="#fff"/><path d="M139 240 V254 M132 247 H146" stroke="#E0303C" stroke-width="5"/>
   <path d="M52 92 Q48 40 100 38 Q152 40 148 92 Q150 120 140 132 L136 100 Q126 66 100 64 Q74 66 64 100 L60 132 Q50 120 52 92Z" fill="#3A2216"/>
   ${face({skin: "#F2CCA8", skinD: "#C99A76", brow: "calm", mouth: "smile", cheeks: 1, iris: "#2A5A3A"})}<path d="M64 100 Q74 66 100 64 Q126 66 136 100 Q120 80 100 78 Q80 80 64 100Z" fill="#3A2216"/><circle cx="100" cy="40" r="15" fill="#3A2216"/>
   <g transform="translate(156 170) rotate(28)"><rect x="-6" y="-46" width="12" height="54" rx="3" fill="rgba(140,255,190,.35)" stroke="#E9F0F6" stroke-width="2.5"/><rect x="-5" y="-30" width="10" height="36" fill="#3FE58A"/><rect x="-9" y="8" width="18" height="5" fill="#E9F0F6"/></g>${rim("#58E08C")}`,
  kom: () => `${body({cloth: "#C9A46A", cloth2: "#7A5A30"})}<path d="M78 156 L100 210 L122 156" fill="#1E2A44"/><path d="M64 230 H136" stroke="#5A4020" stroke-width="7"/><rect x="92" y="224" width="16" height="13" rx="2" fill="#D9A84E"/>
   ${face({skin: "#D9A47C", skinD: "#A97650", brow: "up", mouth: "flat"})}<path d="M80 118 Q100 108 120 118 Q118 126 100 122 Q82 126 80 118Z" fill="#3A2416"/>
   <path d="M48 70 Q50 30 100 26 Q150 30 152 70 Z" fill="#1E2A44"/><path d="M42 70 H158 Q156 82 100 82 Q44 82 42 70Z" fill="#141C30"/><path d="M100 34 l7 12 l13 1 l-10 8 l3 13 l-13 -7 l-13 7 l3 -13 l-10 -8 l13 -1z" fill="#FFD15A"/>
   <g transform="translate(36 220)"><circle r="20" fill="rgba(190,230,255,.35)" stroke="#5A4020" stroke-width="6"/><path d="M14 14 L34 34" stroke="#3A2A16" stroke-width="9" stroke-linecap="round"/></g>${rim("#6AA8FF")}`,
  bozor: () => `${body({cloth: "#2D5E9E", cloth2: "#1A3460"})}<g>${[44, 58, 72, 128, 142, 156].map((x, i) => `<path d="M${x} 180 L${x + (x < 100 ? -4 : 4)} 300" stroke="${i % 2 ? "#E9B840" : "#3FB27A"}" stroke-width="5"/>`).join("")}</g>
   <path d="M78 156 L100 220 L122 156" fill="#F2EDE2"/><path d="M60 236 H140" stroke="#C21E2C" stroke-width="9"/>
   ${face({skin: "#D8A27A", skinD: "#A8724E", brow: "calm", mouth: "smile", cheeks: 1, squint: 1, browC: "#9A9A9A"})}<path d="M60 112 Q62 160 100 168 Q138 160 140 112 Q130 140 100 142 Q70 140 60 112Z" fill="#D9D6D0"/>
   <path d="M56 70 Q56 40 100 38 Q144 40 144 70 L146 76 H54Z" fill="#141418"/><g fill="#F4F4F4">${[[70, 56], [86, 50], [100, 48], [114, 50], [130, 56], [78, 66], [100, 62], [122, 66]].map(([x, y]) => `<path d="M${x} ${y - 5} q4 4 0 8 q-4 -4 0 -8z"/>`).join("")}</g>${rim("#FFC53D")}`,
  novvoy: () => `${body({cloth: "#F2EDE4", cloth2: "#CFC7B8"})}<path d="M62 196 H138 L142 300 H58Z" fill="#9A5A2A"/>
   ${face({skin: "#E8B38A", skinD: "#BC8660", brow: "up", mouth: "grin", cheeks: 1})}<path d="M84 118 Q100 110 116 118 Q114 124 100 121 Q86 124 84 118Z" fill="#2A1A12"/>
   <path d="M58 70 Q50 40 70 30 Q80 10 100 18 Q120 10 132 30 Q152 40 142 70 Z" fill="#fff" stroke="#E6E0D6" stroke-width="2"/><rect x="58" y="62" width="84" height="14" rx="4" fill="#F4F0E8"/>
   <g transform="translate(100 252)"><circle r="40" fill="#C8782E"/><circle r="40" fill="none" stroke="#9A5418" stroke-width="5"/><circle r="22" fill="#E4A35A"/></g>${rim("#FFC53D")}`,
  taksi: () => `${body({cloth: "#3A3A42", cloth2: "#16161A"})}<path d="M78 156 L100 186 L122 156" fill="#E9E9E9"/><path d="M84 166 L100 186 L116 166" fill="#F5C518"/><path d="M44 220 H156" stroke="#F5C518" stroke-width="6" stroke-dasharray="12 10"/>
   ${face({skin: "#CF9A72", skinD: "#9E6C4A", brow: "calm", mouth: "smirk"})}<path d="M78 120 Q90 112 100 118 Q110 112 122 120 Q112 128 100 122 Q88 128 78 120Z" fill="#1A120C"/>
   <path d="M54 76 Q54 36 100 34 Q146 36 146 76Z" fill="#F5C518"/><path d="M40 76 Q100 60 148 76 L146 84 Q100 72 42 86Z" fill="#D9A800"/><rect x="84" y="44" width="32" height="14" rx="4" fill="#16161A"/>${rim("#FFC53D")}`,
  talaba: () => `${body({cloth: "#7A5CFA", cloth2: "#4A2EB8"})}<path d="M92 180 V214 M108 180 V214" stroke="#F4F0FF" stroke-width="3"/>
   <path d="M50 96 Q46 38 100 36 Q154 38 150 96 Q148 140 156 176 Q142 160 140 120 L134 96 Q124 66 100 64 Q76 66 66 96 L60 120 Q58 160 44 176 Q52 140 50 96Z" fill="#1A1210"/>
   ${face({skin: "#EFC29C", skinD: "#C2906A", brow: "up", mouth: "smile", cheeks: 1})}<path d="M64 96 Q72 62 100 60 Q128 62 136 96 Q118 74 96 80 Q78 84 64 96Z" fill="#1A1210"/>
   <path d="M48 104 Q46 44 100 42 Q154 44 152 104" fill="none" stroke="#26262E" stroke-width="7"/><rect x="38" y="92" width="18" height="30" rx="8" fill="#FF4A8A"/><rect x="144" y="92" width="18" height="30" rx="8" fill="#FF4A8A"/>${rim("#FFC53D")}`,
  ustoz: () => `${body({cloth: "#2E8A7A", cloth2: "#1A5248"})}<path d="M78 156 L100 186 L122 156" fill="#F4EDE2"/><circle cx="100" cy="214" r="5" fill="#E9B840"/><circle cx="100" cy="236" r="5" fill="#E9B840"/>
   <path d="M52 96 Q48 40 100 38 Q152 40 148 96 L142 120 Q136 80 100 72 Q64 80 58 120Z" fill="#5A3A26"/>
   ${face({skin: "#EAC09A", skinD: "#BF8E68", brow: "up", mouth: "smile", cheeks: 1})}<path d="M60 100 Q70 64 100 62 Q130 64 140 100 Q120 76 100 76 Q80 76 60 100Z" fill="#5A3A26"/><circle cx="100" cy="36" r="16" fill="#5A3A26"/>
   <circle cx="82" cy="100" r="14" fill="none" stroke="#2A1A12" stroke-width="3.5"/><circle cx="118" cy="100" r="14" fill="none" stroke="#2A1A12" stroke-width="3.5"/><path d="M96 100 H104" stroke="#2A1A12" stroke-width="3.5"/>${rim("#FFC53D")}`,
  sport: () => `${body({cloth: "#E04A3A", cloth2: "#8A1E14"})}<path d="M56 180 L64 300 M144 180 L136 300" stroke="#fff" stroke-width="6"/><path d="M78 156 L100 176 L122 156" fill="#fff"/>
   ${face({skin: "#C68E64", skinD: "#976242", brow: "angry", mouth: "grin"})}<path d="M54 76 Q54 36 100 34 Q146 36 146 76Z" fill="#1E3A8A"/><path d="M100 76 Q140 66 172 80 L168 88 Q136 76 100 84Z" fill="#16296A"/>${rim("#FFC53D")}`,
  dehqon: () => `${body({cloth: "#6A8A3A", cloth2: "#3A521E"})}<path d="M78 156 L100 200 L122 156" fill="#E9DFC8"/><path d="M60 196 H140" stroke="#8A6A3A" stroke-width="6"/>
   ${face({skin: "#B9804E", skinD: "#8A5832", brow: "calm", mouth: "smile", squint: 1})}<path d="M80 118 Q100 110 120 118 Q110 124 100 120 Q90 124 80 118Z" fill="#3A2416"/>
   <ellipse cx="100" cy="64" rx="76" ry="16" fill="#E2C46A"/><path d="M60 62 Q62 30 100 28 Q138 30 140 62Z" fill="#EAD07A"/><path d="M60 56 H140" stroke="#8A5A2A" stroke-width="5"/>${rim("#FFC53D")}`,
  boyqush: () => `<path d="M40 300 Q30 170 100 140 Q170 170 160 300Z" fill="#5A4028"/><path d="M70 300 Q66 200 100 186 Q134 200 130 300Z" fill="#D8BE94"/>
   <ellipse cx="100" cy="100" rx="70" ry="64" fill="#6A4A2E"/><path d="M40 52 L56 84 L70 60Z M160 52 L144 84 L130 60Z" fill="#3A2614"/>
   <circle cx="74" cy="100" r="28" fill="#F2E2C2"/><circle cx="126" cy="100" r="28" fill="#F2E2C2"/><circle cx="74" cy="100" r="16" fill="#FFB020"/><circle cx="126" cy="100" r="16" fill="#FFB020"/>
   <circle cx="76" cy="100" r="8" fill="#0A0605"/><circle cx="128" cy="100" r="8" fill="#0A0605"/><circle cx="79" cy="96" r="3" fill="#fff"/><circle cx="131" cy="96" r="3" fill="#fff"/>
   <circle cx="126" cy="100" r="22" fill="none" stroke="#D9A84E" stroke-width="3"/><path d="M92 118 L100 136 L108 118Z" fill="#E0A030"/><path d="M76 160 L100 172 L124 160 L124 180 L100 168 L76 180Z" fill="#C21E2C"/>`,
};
return (k, v) => { VAR = v || null; const r = `<svg viewBox="0 0 200 300" xmlns="http://www.w3.org/2000/svg">${(C[k] || C.bozor)()}</svg>`; VAR = null; return r; };
})();
const PAL = [null, {cloth: "#8A2A5A", cloth2: "#4A1030"}, {cloth: "#2A6A8A", cloth2: "#123A4A"}, {cloth: "#6A4A2A", cloth2: "#3A2410"}];
const LOOKS = ["bozor", "novvoy", "taksi", "talaba", "ustoz", "sport", "dehqon"];
const LOOK_NAME = {bozor: T("Bozorchi", "Торговец", "Trader"), novvoy: T("Novvoy", "Пекарь", "Baker"), taksi: T("Taksichi", "Таксист", "Driver"),
  talaba: T("Talaba", "Студентка", "Student"), ustoz: T("Ustoz", "Учитель", "Teacher"), sport: T("Sportchi", "Спортсмен", "Athlete"), dehqon: T("Dehqon", "Фермер", "Farmer")};
const ROLE = {
  don: {n: T("Don", "Дон", "Don"), ic: "🎩", c: "maf", ch: "don", d: T("Mafia boshlig'i. Tunda oxirgi qarorni siz berasiz. Komissar sizni «tinch» deb ko'radi.", "Глава мафии. Ночью последнее слово за вами.", "Mafia boss. You make the final call at night.")},
  maf: {n: T("Mafia", "Мафия", "Mafia"), ic: "🔪", c: "maf", ch: "qotil", d: T("Har tunda sheriklaringiz bilan bitta qurbon tanlaysiz. Kunduzi o'zingizni oddiy aholidek tuting.", "Каждую ночь выбираете жертву вместе с напарниками.", "Pick a victim each night with your partners.")},
  doc: {n: T("Shifokor", "Доктор", "Doctor"), ic: "💉", c: "doc", ch: "doc", d: T("Har tunda bittasini o'limdan saqlaysiz. Ketma-ket bir odamni emas, o'zingizni — bir marta.", "Каждую ночь спасаете одного. Себя — один раз.", "Save one person each night. Yourself — once.")},
  kom: {n: T("Komissar", "Комиссар", "Commissioner"), ic: "🕵️", c: "kom", ch: "kom", d: T("Har tunda tanlaysiz: 🔍 bitta odamni tekshirish (mafia yoki tinch — faqat sizga) yoki 🔫 unga o'q uzish.", "Каждую ночь: проверить одного или выстрелить.", "Each night: check someone or shoot them.")},
  tans: {n: T("Tansoqchi", "Телохранитель", "Bodyguard"), ic: "🛡", c: "kom", ch: "sport", v: {cloth: "#1E3A8A", cloth2: "#0E1A40"}, d: T("Bitta odamni qo'riqlaysiz: unga otilsa, o'qni o'zingiz olasiz.", "Охраняете одного: пулю примете на себя.", "Guard one person: you take the bullet.")},
  serj: {n: T("Serjant", "Сержант", "Sergeant"), ic: "👮", c: "kom", ch: "kom", v: {cloth: "#2A3A5A", cloth2: "#121A2E"}, d: T("Komissar yordamchisi: uning tekshiruvlarini ko'rasiz, u o'lsa — o'rniga o'tasiz.", "Помощник комиссара, заменит его.", "Commissioner's aide; takes over if he dies.")},
  many: {n: T("Manyak", "Маньяк", "Maniac"), ic: "🪓", c: "many", ch: "qotil", v: {cloth: "#3A3A3A", cloth2: "#111"}, d: T("Yolg'iz o'ynaysiz: har tunda bittasini o'ldirasiz. Hammani yengsangiz — siz yutasiz.", "Играете один: убиваете каждую ночь.", "Solo: kill one each night. Outlast everyone.")},
  civ: {n: T("Tinch aholi", "Мирный житель", "Civilian"), ic: "👥", c: "civ", d: T("Kunduzi muhokama qilib, mafiyani toping va ovoz bilan osing.", "Днём найдите мафию и проголосуйте.", "Find the mafia by day and vote them out.")},
};
const isMaf = (r) => r === "don" || r === "maf";
const charOf = (p, role) => { const R = ROLE[role]; return R && R.ch ? MC(R.ch, R.v) : MC(p.lk, PAL[p.c || 0]); };

// =================================================================== ovoz va effekt
let ac = null;
function tone(f, d = .1, type = "triangle", vol = .15, when = 0) {
  try {
    ac = ac || new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === "suspended") ac.resume();
    const t = ac.currentTime + when, o = ac.createOscillator(), g = ac.createGain();
    o.type = type; o.frequency.setValueAtTime(f, t);
    g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + .01); g.gain.exponentialRampToValueAtTime(.0001, t + d);
    o.connect(g).connect(ac.destination); o.start(t); o.stop(t + d + .05);
  } catch (e) {}
}
function noise(d = .3, vol = .3, when = 0, hp = 800) {
  try {
    ac = ac || new (window.AudioContext || window.webkitAudioContext)();
    const len = Math.floor(ac.sampleRate * d), buf = ac.createBuffer(1, len, ac.sampleRate), ch = buf.getChannelData(0);
    for (let i = 0; i < len; i++) ch[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2);
    const s = ac.createBufferSource(), g = ac.createGain(), f = ac.createBiquadFilter();
    f.type = "highpass"; f.frequency.value = hp; s.buffer = buf; g.gain.value = vol;
    s.connect(f).connect(g).connect(ac.destination); s.start(ac.currentTime + when);
  } catch (e) {}
}
const SFX = {
  bang: () => { noise(.45, .5, 0, 200); tone(70, .4, "sawtooth", .2); },
  drum: () => { tone(90, .25, "sine", .35); noise(.1, .15, 0, 2000); },
  thud: () => { tone(55, .5, "square", .2); noise(.3, .3, 0, 100); },
  chime: () => [660, 880, 1320].forEach((f, i) => tone(f, .35, "sine", .12, i * .09)),
  sad: () => [392, 349, 311].forEach((f, i) => tone(f, .5, "sine", .12, i * .22)),
  win: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, .25, "triangle", .16, i * .11)),
  tick: () => tone(1200, .03, "square", .04),
  night: () => [330, 262, 220].forEach((f, i) => tone(f, .6, "sine", .1, i * .25)),
  msg: () => tone(980, .06, "sine", .06),
};

// =================================================================== API
async function api(path, body, form) {
  try {
    const r = await fetch(path, {method: body || form ? "POST" : "GET", cache: "no-store",
      headers: Object.assign({"X-Init-Data": inTg ? tg.initData : ""}, body ? {"Content-Type": "application/json"} : {}),
      body: form || (body ? JSON.stringify(body) : undefined)});
    if (r.status === 401) return {ok: false, error: "auth"};
    if (r.status >= 500) return {ok: false, error: "server"};
    return await r.json();
  } catch (e) { return {ok: false, error: "network"}; }
}
const ERR = () => ({auth: T("Ilovani bot ichida oching", "Откройте внутри бота", "Open inside the bot"), network: T("Internet bilan muammo", "Проблема с сетью", "Connection problem"),
  server: T("Server band — qayta urining", "Сервер занят", "Server busy"), nocode: T("Bunday xona topilmadi", "Комната не найдена", "Room not found"),
  full: T("Xona to'lgan (20 kishi)", "Комната заполнена", "Room is full"), few: T("Kamida 5 kishi kerak", "Нужно минимум 5 игроков", "At least 5 players needed"),
  host: T("Faqat xona egasi boshlaydi", "Начинает только хозяин", "Only the host can start"), banned: T("Siz bloklangansiz", "Вы заблокированы", "You are blocked"),
  rate: T("Sekinroq yozing", "Помедленнее", "Slow down"), chat: T("Hozir yozib bo'lmaydi", "Сейчас писать нельзя", "You can't write now"),
  target: T("Bu odamni tanlab bo'lmaydi", "Нельзя выбрать", "Can't pick this player"), checked: T("Bu odam allaqachon tekshirilgan", "Уже проверен", "Already checked"), done: T("Bu tun tanlov qilib bo'lgansiz", "Вы уже сделали ход", "You've already acted"), too_big: T("Ovozli xabar juda uzun", "Слишком длинное", "Too long")});

// =================================================================== holat
let opened = false, mounted = false, H = null, R = null, ver = -1, mid = 0, chat = [], pollT = null, tickT = null, leftAt = 0, left = 0;
let komMode = "check";
let tab = "all", seenKey = "", ovBusy = false, ovQueue = [], leaveArm = 0, sel = 0, lastBubble = {};
const me = () => R && R.players.find((p) => p.u === R.me);
const alive = () => (R ? R.players.filter((p) => p.alive) : []);
function toast(t) {
  const el = document.createElement("div"); el.className = "mf-toast"; el.textContent = t;
  document.body.appendChild(el); setTimeout(() => el.remove(), 2600);
}

function applyRoom(room) {
  if (!room) { R = null; ver = -1; mid = 0; chat = []; stopPoll(); render(); return; }
  const prevPhase = R && R.phase;
  if (!R || R.id !== room.id) { chat = []; mid = 0; seenKey = ""; tab = "all"; }
  R = room; ver = room.ver; left = room.left; leftAt = Date.now();
  if (room.chat && room.chat.length) {
    const known = new Set(chat.map((x) => x.i));
    const fresh = room.chat.filter((x) => !known.has(x.i));
    if (fresh.length) {
      chat = chat.concat(fresh).slice(-160);
      fresh.forEach((x) => { if (x.u !== room.me && x.ch === "all") lastBubble[x.u] = {t: x.t || (x.v ? "🎤 …" : x.e), at: Date.now()}; });
      if (prevPhase && fresh.some((x) => x.u !== room.me)) SFX.msg();
    }
    mid = Math.max(mid, room.mid);
  }
  if (prevPhase !== room.phase) {                 // bosqich almashdi — yozish mumkin bo'lgan chatga o'tamiz
    if (room.ch.includes("maf") && !room.ch.includes("all")) tab = "maf";
    else if (room.ch.includes("all")) tab = "all";
    else if (room.ch.includes("dead")) tab = "dead";
  }
  if (!R.ch.includes(tab) && !readable().includes(tab)) tab = readable()[0] || "all";
  render();
  transitions(prevPhase);
}
async function poll() {
  if (!opened || !R) return;
  const r = await api(`api/mafia/poll?v=${ver}&m=${mid}`);
  if (!opened) return;
  if (r.ok && r.same) { left = r.left; leftAt = Date.now(); return; }
  if (r.ok) applyRoom(r.room);
}
function startPoll() { stopPoll(); pollT = setInterval(poll, 1300); tickT = setInterval(timerTick, 250); }
function stopPoll() { if (pollT) clearInterval(pollT); if (tickT) clearInterval(tickT); pollT = tickT = null; }
function timerTick() {
  const el = $("mftime"); if (!el || !R) return;
  const s = Math.max(0, left - Math.floor((Date.now() - leftAt) / 1000));
  const txt = s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : `0:${String(s).padStart(2, "0")}`;
  if (el.textContent !== txt) { el.textContent = txt; if (s <= 5 && s > 0 && ["night", "vote", "last"].includes(R.phase)) SFX.tick(); }
}
async function post(path, body) {
  const r = await api("api/mafia/" + path, body || {});
  if (r.room) applyRoom(r.room);
  if (!r.ok) { haptic("err"); toast(ERR()[r.error] || ERR().server); }
  return r;
}

// =================================================================== ko'rinish
const PH = {lobby: T("Kutish zali", "Лобби", "Lobby"), roles: T("Rollar", "Роли", "Roles"), night: T("Tun", "Ночь", "Night"), morning: T("Tong", "Утро", "Morning"),
  day: T("Kun · muhokama", "День · обсуждение", "Day · talk"), vote: T("Ovoz berish", "Голосование", "Voting"), last: T("Oxirgi so'z", "Последнее слово", "Last words"),
  hang: T("Hukm", "Приговор", "Verdict"), end: T("O'yin tugadi", "Игра окончена", "Game over")};
const segHtml = () => { const segs = window.ZK_SEGS || [["kino", "Kinolar"], ["mafia", "Mafia"]]; return `<div class="mf-seg">${segs.map(([m, l]) => `<button data-mode="${m}" class="${m === "mafia" ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`; };
const BACK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>';

function render() {
  const root = $("mafia"); if (!root) return;
  root.dataset.ph = R ? R.phase : "home";
  if (!R) { renderHome(); updateBack(); return; }
  if (!$("mfroom")) {
    $("mfview").innerHTML = `<div id="mfroom"><div class="mf-top" id="mftop"></div><div class="mf-stage" id="mfstage"></div><div id="mfctrl"></div>
      <div class="mf-chat" id="mfchat"><div class="mf-tabs" id="mftabs"></div><div class="mf-feed" id="mffeed"></div>
      <div class="mf-emo" id="mfemo">${["😂", "😤", "🤔", "😱", "🔪", "🙏", "👍", "🤡"].map((e) => `<button data-emo="${e}">${e}</button>`).join("")}</div>
      <div class="mf-in" id="mfin"><input id="mftext" maxlength="300" autocomplete="off" enterkeyhint="send" placeholder="${T("Xabar yozing…", "Сообщение…", "Message…")}"><button class="mf-mic" id="mfmic" aria-label="🎤">🎤</button><button class="mf-send" data-a="send" aria-label="➤">➤</button></div></div></div>`;
  }
  renderTop(); renderStage(); renderCtrl(); renderChat();
  updateBack();
}

// ---------- 💬 rasmiy guruh havolasi (admin ✏️ bilan o'zgartiradi)
let grpEdit = false;
function grpHtml(h) {
  const g = h.grp;
  if (grpEdit && h.admin) return `<div class="mf-grp edit"><b>💬 ${T("Mafia guruhi havolasi", "Ссылка на группу Мафии", "Mafia group link")}</b>
    <input id="mfgurl" placeholder="https://t.me/... ${T("yoki", "или", "or")} @guruh" value="${esc(g ? g.url : "")}" autocomplete="off">
    <input id="mfgttl" placeholder="${T("Nomi (ixtiyoriy): Mafia Uzbekistan", "Название (необяз.)", "Title (optional)")}" maxlength="60" value="${esc(g ? g.title || "" : "")}" autocomplete="off">
    <div class="mf-two"><button class="mf-ghost" data-a="grpx">${T("Bekor", "Отмена", "Cancel")}</button><button class="mf-cta sm" data-a="grpsave">${T("Saqlash", "Сохранить", "Save")}</button></div>
    ${g ? `<button class="mf-grp-del" data-a="grpdel">🗑 ${T("Havolani olib tashlash", "Удалить ссылку", "Remove link")}</button>` : ""}</div>`;
  if (!g) return h.admin ? `<button class="mf-grp add" data-a="grpedit">＋ ${T("Mafia guruhi havolasini qo'shish", "Добавить ссылку на группу", "Add the Mafia group link")} <small>${T("faqat adminga ko'rinadi", "видно только админу", "admins only")}</small></button>` : "";
  return `<div class="mf-grpw"><button class="mf-grp" data-a="grpopen"><i>💬</i><span><b>${esc(g.title || T("Mafia guruhimiz", "Наша группа Мафии", "Our Mafia group"))}</b>
    <small>${T("O'yinchilar bilan tanishing, o'yinlarga yig'iling", "Знакомьтесь с игроками, собирайтесь на игры", "Meet players and gather for games")}</small></span><em>${T("Qo'shilish", "Вступить", "Join")} ›</em></button>
    ${h.admin ? `<button class="mf-grp-ed" data-a="grpedit" aria-label="${T("O'zgartirish", "Изменить", "Edit")}">✏️</button>` : ""}</div>`;
}

// ---------- uy
function renderHome() {
  const h = H || {};
  const st = h.st || {};
  const headHtml = `<div class="mf-head-clean"><button class="mf-back" data-a="homeback" aria-label="${T("Orqaga", "Назад", "Back")}">${BACK}</button><div class="mf-tt"><b>🕵️ Mafia</b><small>${T("Onlayn o'yin (3–20 kishi)", "Онлайн игра (3–20 чел)", "Online game (3–20 players)")}</small></div><button class="zk-hubbtn" data-a="hub" aria-label="${T("Barcha bo'limlar", "Все разделы", "All sections")}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg><span>${T("Bo'limlar", "Разделы", "Sections")}</span></button></div>`;
  $("mfview").innerHTML = headHtml + `
   <div class="mf-hero"><div class="mf-moon"></div><div class="mf-city"></div>
    <div class="mf-heroc">${[["don", 2, 22, 120], ["qotil", 22, 30, 108], ["doc", 52, 26, 112], ["kom", 76, 30, 104]].map(([k, x, y, w]) => `<div class="mf-hc" style="left:${x}%;top:${y}px;width:${w}px">${MC(k)}</div>`).join("")}</div>
    <div class="mf-logo"><b>MAF<span>I</span>A</b><small>${T("SHAHAR UXLAYDI · MAFIA UYG'ONADI", "ГОРОД ЗАСЫПАЕТ · ПРОСЫПАЕТСЯ МАФИЯ", "THE CITY SLEEPS · THE MAFIA WAKES")}</small></div></div>
   ${h.cur ? `<button class="mf-cta" data-a="resume">▶ ${T("O'yinga qaytish", "Вернуться в игру", "Back to game")} · ${h.cur.n} 👥</button>` : ""}
   <button class="mf-cta" data-a="quick">🎲 ${T("Tezkor o'yin", "Быстрая игра", "Quick game")}${h.pub ? ` · ${T("kutmoqda", "ждут", "waiting")}: ${h.pub}` : ""}</button>
   <p class="mf-fine">${T("Tasodifiy o'yinchilar bilan. 5 kishi yig'ilgach 30 soniyada boshlanadi.", "Со случайными игроками. Старт через 30 с после 5 игроков.", "With random players. Starts 30 s after 5 join.")}</p>
   <div class="mf-two"><button class="mf-ghost" data-a="create">🔢 ${T("Xona yaratish", "Создать комнату", "Create room")}</button><button class="mf-ghost" data-a="group">👥 ${T("Guruhda o'ynash", "В группе", "In a group")}</button></div>
   <div class="mf-code"><input id="mfcode" inputmode="numeric" maxlength="4" placeholder="${T("Xona kodi", "Код комнаты", "Room code")}"><button class="mf-cta sm" data-a="join">${T("Kirish", "Войти", "Join")}</button></div>
   ${grpHtml(h)}
   ${st.games ? `<div class="mf-stat"><div><b>${st.games}</b>${T("o'yin", "игр", "games")}</div><div><b>${st.wins || 0}</b>${T("g'alaba", "побед", "wins")}</div><div><b>${Math.round(100 * (st.wins || 0) / st.games)}%</b>${T("yutish", "побед", "win rate")}</div></div>` : ""}
   <details class="mf-rules"><summary>📖 ${T("Qoidalar", "Правила", "Rules")}</summary>
    <p>${T("🌙 Tunda: mafia bitta qurbon tanlaydi, 💉 shifokor bittasini davolaydi, 🕵️ komissar bittasini tekshiradi. ☀️ Kunduzi hamma muhokama qiladi va ovoz bilan bittasini osadi. Mafia qolmasa — aholi, mafia aholiga tenglashsa — mafia yutadi.", "Ночью мафия выбирает жертву, доктор лечит, комиссар проверяет. Днём все голосуют. Нет мафии — победа мирных, мафия сравнялась — победа мафии.", "At night the mafia picks a victim, the doctor heals, the commissioner checks. By day everyone votes someone out.")}</p>
    <p>${Object.keys(ROLE).map((k) => `${ROLE[k].ic} <b>${ROLE[k].n}</b> — ${ROLE[k].d}`).join("<br>")}</p></details>`;
}

// ---------- tepa
function renderTop() {
  const m = me();
  const role = R.role && ROLE[R.role];
  const timer = ["roles", "night", "morning", "day", "vote", "last", "hang"].includes(R.phase) || (R.phase === "lobby" && R.left);
  $("mftop").innerHTML = `<button class="mf-back" data-a="back" aria-label="back">${BACK}</button>
   <div class="mf-tt"><b>${{night: "🌙", morning: "🌅", day: "☀️", vote: "🗳", last: "🎙", hang: "⚖️", end: "🏁", lobby: "🔪", roles: "🃏"}[R.phase] || ""} ${PH[R.phase] || ""}${R.day && !["lobby", "end"].includes(R.phase) ? ` · ${R.day}` : ""}</b>
    <small>${R.code ? `${T("Xona", "Комната", "Room")} ${R.code} · ` : ""}👥 ${alive().length}/${R.players.length}${role ? ` · <i class="r-${role.c}">${role.ic} ${role.n}</i>` : !R.in ? ` · 👀 ${T("kuzatuvchi", "зритель", "spectator")}` : ""}${m && !m.alive ? " · 💀" : ""}</small></div>
   ${timer ? `<span class="mf-pill" id="mftime">0:00</span>` : ""}`;
  timerTick();
}

// ---------- sahna
function seatHtml(p, i, n) {
  const m = me();
  const myRole = R.role;
  const tgts = R.targets || [];
  const canPick = (R.phase === "night" && tgts.includes(p.u)) || (R.phase === "vote" && R.alive && p.alive && p.u !== R.me);
  const isMe = p.u === R.me;
  const mate = isMaf(myRole) && isMaf(p.role) && !isMe;
  const picked = (R.phase === "night" && R.acted === p.u) || (R.phase === "vote" && R.myvote === p.u);
  const mafPicks = R.mafv ? Object.values(R.mafv).filter((t) => t === p.u).length : 0;
  const role = p.role && ROLE[p.role];
  const cls = ["mf-p", p.alive ? "" : "dead", isMe ? "me" : "", mate ? "mate" : "", canPick ? "pick" : "", picked ? "sel" : "",
    R.phase === "night" && !isMe && !mate && p.alive ? "sleep" : "", R.cond === p.u ? "cond" : "", `pk-${myRole || "x"}`].join(" ");
  const b = lastBubble[p.u];
  const bub = b && Date.now() - b.at < 6000 && n <= 8 ? `<span class="mf-bub">${esc(b.t).slice(0, 60)}</span>` : "";
  const votes = p.v && p.v.length ? `<span class="mf-vc">🗳 ${p.v.length}</span>` : "";
  const mk = picked ? `<span class="mf-mk">${{don: "🎯", maf: "🎯", doc: "💉", kom: "🔍", tans: "🛡", many: "🪓"}[myRole] || "🗳"}</span>` : mafPicks ? `<span class="mf-mk sm">🎯${mafPicks}</span>` : "";
  const art = (isMe && role && role.ch) || (!p.alive && role && role.ch) || (R.phase === "end" && role && role.ch) ? charOf(p, p.role) : MC(p.lk, PAL[p.c || 0]);
  return `<button class="${cls}" data-p="${p.u}" ${canPick ? "" : "tabindex='-1'"}>${bub}<span class="mf-art">${art}</span>${mk}${votes}
    <span class="mf-nm">${p.host && R.phase === "lobby" ? "👑 " : ""}${esc(p.n)}${isMe ? ` · ${T("siz", "вы", "you")}` : ""}</span>
    ${role && (!p.alive || mate || R.phase === "end" || isMe) ? `<span class="mf-rl r-${role.c}">${role.ic} ${role.n}</span>` : ""}${!p.alive ? '<span class="mf-x">💀</span>' : ""}</button>`;
}
function renderStage() {
  const ps = R.players, n = ps.length;
  const big = n <= 8;
  const st = $("mfstage");
  st.className = `mf-stage ${big ? "mf-big" : "mf-many"} ph-${R.phase}`;
  if (big) {
    // stol atrofida yoy bo'ylab
    const pos = ps.map((p, i) => {
      const a = n === 1 ? 0 : (-70 + 140 * i / Math.max(1, n - 1)) * Math.PI / 180;
      return {x: 50 + Math.sin(a) * 43, y: 34 - Math.cos(a) * 26 + (Math.abs(Math.sin(a)) * 22)};
    });
    st.innerHTML = `<div class="mf-sky"><div class="mf-moon2"></div><div class="mf-sun2"></div></div><div class="mf-lamp"></div>
      ${ps.map((p, i) => `<div class="mf-seat" style="left:${pos[i].x}%;top:${pos[i].y}%;z-index:${10 + Math.round(pos[i].y)}">${seatHtml(p, i, n)}</div>`).join("")}
      <div class="mf-table"></div>${R.phase === "night" && R.alive && !(R.targets || []).length ? `<div class="mf-zz">😴 ${T("Siz uxlayapsiz… tong otishini kuting", "Вы спите… ждите утра", "You're asleep… wait for morning")}</div>` : ""}`;
  } else {
    st.innerHTML = `<div class="mf-sky"><div class="mf-moon2"></div><div class="mf-sun2"></div></div><div class="mf-grid">${ps.map((p, i) => seatHtml(p, i, n)).join("")}</div>
      ${R.phase === "night" && R.alive && !(R.targets || []).length ? `<div class="mf-zz">😴 ${T("Siz uxlayapsiz…", "Вы спите…", "You're asleep…")}</div>` : ""}`;
  }
}

// ---------- boshqaruv
function renderCtrl() {
  const m = me(), role = R.role;
  let h = "";
  if (R.phase === "lobby") {
    const isHost = R.host === R.me;
    h = `<div class="mf-card"><b>${R.group ? T("Guruh o'yini", "Игра группы", "Group game") : R.pub ? T("Tezkor o'yin", "Быстрая игра", "Quick game") : `${T("Xona kodi", "Код комнаты", "Room code")}: <span class="mf-codebig">${esc(R.code)}</span>`}</b>
      <small>${R.players.length < R.min ? T(`Yana ${R.min - R.players.length} kishi kerak (kamida ${R.min}).`, `Нужно ещё ${R.min - R.players.length}.`, `Need ${R.min - R.players.length} more.`) : R.left ? T("O'yin avtomatik boshlanadi", "Игра начнётся автоматически", "Starts automatically") : T("Hammasi tayyor bo'lsa — boshlang!", "Можно начинать!", "Ready to start!")}</small>
      ${!R.pub && !R.group ? `<div class="mf-two"><button class="mf-ghost" data-a="share">📤 ${T("Do'stlarni chaqirish", "Пригласить", "Invite")}</button><button class="mf-ghost" data-a="copy">📋 ${T("Kodni nusxalash", "Копировать", "Copy code")}</button></div>` : ""}</div>
     ${m ? `<div class="mf-lh">${T("Qahramoningiz", "Ваш персонаж", "Your character")}</div><div class="mf-looks">${LOOKS.map((k) => `<button data-look="${k}" class="${m.lk === k ? "on" : ""}">${MC(k, PAL[m.c || 0])}<i>${LOOK_NAME[k]}</i></button>`).join("")}</div>
       <div class="mf-cols">${PAL.map((v, i) => `<button data-col="${i}" class="${(m.c || 0) === i ? "on" : ""}" style="background:${v ? v.cloth : "#2D5E9E"}"></button>`).join("")}</div>` : ""}
     ${isHost || H && H.admin ? `<button class="mf-cta" data-a="start" ${R.players.length < (H && H.admin ? 3 : R.min) ? "disabled" : ""}>▶ ${T("Boshlash", "Начать", "Start")} · ${R.players.length}/20</button>` : `<p class="mf-fine c">⏳ ${T("Xona egasi boshlashini kuting", "Ждите, пока хозяин начнёт", "Waiting for the host")}</p>`}`;
  } else if (R.phase === "roles") {
    h = role ? `<div class="mf-card r-${ROLE[role].c}"><b>${ROLE[role].ic} ${T("Siz", "Вы", "You")} — ${ROLE[role].n}</b><small>${ROLE[role].d}</small></div>` : "";
  } else if (R.phase === "night") {
    if (!R.in) h = `<div class="mf-card"><b>🌙 ${T("Tun. Kuzatyapsiz", "Ночь. Вы наблюдаете", "Night. You're watching")}</b></div>`;
    else if (!R.alive) h = `<div class="mf-card"><b>👻 ${T("Siz o'ldingiz — kuzatyapsiz", "Вы мертвы — наблюдаете", "You're dead — watching")}</b><small>${T("O'liklar chatida gaplashing", "Общайтесь в чате мёртвых", "Chat with the dead")}</small></div>`;
    else if ((R.targets || []).length) {
      const ask = {don: T("Kimni otamiz? Oxirgi so'z sizda", "Кого убираем? Решаете вы", "Who dies? Your call"), maf: T("Qurbonni tanlang", "Выберите жертву", "Pick the victim"),
        doc: T("Kimni davolaysiz?", "Кого лечите?", "Who do you heal?"), kom: T("Kimni tekshirasiz?", "Кого проверяете?", "Who do you check?"),
        tans: T("Kimni qo'riqlaysiz?", "Кого охраняете?", "Who do you guard?"), many: T("Kimni o'ldirasiz?", "Кого убиваете?", "Who do you kill?")}[role];
      const t = R.acted ? R.players.find((p) => p.u === R.acted) : null;
      h = actList(role, ask, t);
    }
    if (R.checks && R.checks.length) h += checksHtml();
  } else if (R.phase === "morning") {
    h = `<div class="mf-card"><b>🦉 ${T("Boyqush tong xabarini o'qiyapti…", "Сова читает утренние новости…", "The owl reads the news…")}</b></div>`;
  } else if (R.phase === "day") {
    h = `<div class="mf-card"><b>☀️ ${T("Muhokama: mafia kim?", "Обсуждение: кто мафия?", "Who's the mafia?")}</b><small>${T("Chatda yozing yoki 🎤 gapiring. Keyin ovoz beriladi.", "Пишите или говорите 🎤. Затем голосование.", "Talk in chat or 🎤. Voting follows.")}</small>
      ${R.alive ? `<button class="mf-ghost w" data-a="skip" ${R.skipped ? "disabled" : ""}>⏭ ${T("Ovozga o'tish", "К голосованию", "Go to vote")} · ${R.skip}/${Math.ceil(alive().length * 2 / 3)}</button>` : ""}</div>`;
    if (R.checks && R.checks.length) h += checksHtml();
  } else if (R.phase === "vote") {
    h = voteList();
  } else if (R.phase === "last") {
    const c = R.players.find((p) => p.u === R.cond);
    h = `<div class="mf-card r-maf"><b>⚖️ ${c ? esc(c.n) : ""} — ${T("dorga!", "на виселицу!", "to the gallows!")}</b><small>${R.cond === R.me ? T("Oxirgi so'zingizni yozing yoki 🎤 ayting", "Ваше последнее слово", "Say your last words") : T("Oxirgi so'zini tinglang…", "Слушайте последнее слово…", "Listen to the last words…")}</small></div>` + voteBars();
  } else if (R.phase === "end") {
    h = endHtml(true);
  }
  $("mfctrl").innerHTML = h;
  const act = (R.phase === "night" && R.alive && (R.targets || []).length) || (R.phase === "vote" && R.alive);
  const room = $("mfroom");
  if (room) room.classList.toggle("actfirst", !!act);
  const k = R.phase + R.day;
  if (act && room && room.dataset.k !== k) { room.dataset.k = k; setTimeout(() => { try { $("mfscroll").scrollTo({top: 0, behavior: "smooth"}); } catch (e) {} }, 50); }
}
// ---- aniq tanlov ro'yxati: har qatorda qahramon + katta tugma (tun harakati va ovoz)
const ACT_BTN = {don: T("🎯 Otish", "🎯 Убить", "🎯 Shoot"), maf: T("🎯 Otish", "🎯 Убить", "🎯 Shoot"), doc: T("💉 Davolash", "💉 Лечить", "💉 Heal"),
  kom: T("🔍 Tekshirish", "🔍 Проверить", "🔍 Check"), tans: T("🛡 Qo'riqlash", "🛡 Охранять", "🛡 Guard"), many: T("🪓 O'ldirish", "🪓 Убить", "🪓 Kill")};
function actRow(p, label, picked, extra, cls) {
  return `<button class="mf-act ${picked ? "on" : ""} ${cls || ""}" data-p="${p.u}"><span class="mf-aa">${MC(p.lk, PAL[p.c || 0])}</span>
    <span class="mf-an"><b>${esc(p.n)}${p.u === R.me ? ` · ${T("siz", "вы", "you")}` : ""}</b>${extra ? `<small>${extra}</small>` : ""}</span>
    <span class="mf-ab">${picked ? "✅ " + T("Tanlandi", "Выбрано", "Picked") : label}</span></button>`;
}
function actList(role, ask, t) {
  const R0 = ROLE[role];
  const mv = R.mafv || {};
  const isKom = role === "kom";
  const shoot = isKom && komMode === "shoot";
  const checked = {};
  (R.checks || []).forEach((c) => { checked[c.t] = c.r; });
  const rows = R.targets.map((u) => R.players.find((p) => p.u === u)).filter(Boolean).map((p) => {
    if (isKom && !shoot && checked[p.u]) return actRow(p, "", false, `🔍 ${T("tekshirilgan", "проверен", "checked")}: ${checked[p.u] === "maf" ? "🔪 MAFIA" : "✅ " + T("tinch", "мирный", "innocent")}`, "ro");
    const by = Object.keys(mv).filter((k) => mv[k] === p.u && +k !== R.me).map((k) => { const q = R.players.find((x) => x.u === +k); return q ? esc(q.n) : "?"; });
    const extra = by.length ? `🔪 ${by.join(", ")} ${T("tanladi", "выбрал(и)", "picked")}` : isKom && checked[p.u] ? `🔍 ${checked[p.u] === "maf" ? "🔪 MAFIA" : "✅ " + T("tinch", "мирный", "innocent")}` : "";
    return actRow(p, shoot ? T("🔫 Otish", "🔫 Стрелять", "🔫 Shoot") : ACT_BTN[role], R.acted === p.u, extra, shoot ? "r-maf" : "r-" + R0.c);
  }).join("");
  const done = isKom && t;
  const modes = isKom && !done ? `<div class="mf-km"><button data-km="check" class="${shoot ? "" : "on"}">🔍 ${T("Tekshirish", "Проверить", "Check")}</button><button data-km="shoot" class="${shoot ? "on sh" : ""}">🔫 ${T("Otish", "Стрелять", "Shoot")}</button></div>
    <small class="mf-kmh">${shoot ? T("Komissar o'q uzadi — mafiyaga tegsa, shahar qutqariladi. Begunohga tegsa ham o'ladi!", "Комиссар стреляет — осторожно, можно убить мирного!", "The commissioner shoots — careful, innocents die too!") : T("Bitta odamning kimligini bilib olasiz — natija faqat sizga.", "Узнаете, кто это — результат только вам.", "Learn who someone is — only you see it.")}</small>` : "";
  const sub = t ? `✅ ${isKom ? (R.kmode === "shoot" ? "🔫 " + T("Otildi", "Выстрел", "Shot") : "🔍 " + T("Tekshirildi", "Проверено", "Checked")) + ": " : ""}${esc(t.n)}${done ? "" : " · " + T("boshqasini bossangiz — o'zgaradi", "можно сменить", "tap another to change")}` : T("Pastdagi ro'yxatdan bittasini tanlang 👇", "Выберите одного из списка 👇", "Pick one from the list 👇");
  return `<div class="mf-acth r-${R0.c}"><b>${R0.ic} ${isKom && !done ? T("Komissar: tekshirasizmi yoki otasizmi?", "Комиссар: проверить или стрелять?", "Commissioner: check or shoot?") : ask}</b>${modes}<small>${sub}</small></div>
   <div class="mf-acts">${done ? "" : rows}</div>`;
}
function voteList() {
  const total = alive().length;
  const voted = R.players.reduce((n, p) => n + (p.v ? p.v.length : 0), 0);
  const v = R.myvote > 0 ? R.players.find((p) => p.u === R.myvote) : null;
  const head = `<div class="mf-acth r-vote"><b>🗳 ${T("Ovoz berish: kimni osamiz?", "Голосование: кого казним?", "Vote: who do we hang?")}</b>
    <small>${R.alive ? (v ? `✅ ${T("Siz", "Вы", "You")} → ${esc(v.n)} · ${T("o'zgartirish mumkin", "можно сменить", "can change")}` : R.myvote === 0 ? T("Siz betaraf qoldingiz", "Вы воздержались", "You abstained") : T("Mafia deb o'ylagan odamingiz yonidagi «🗳 Ovoz» tugmasini bosing 👇", "Нажмите «🗳 Голос» рядом с подозреваемым 👇", "Tap «🗳 Vote» next to your suspect 👇")) : T("Siz ovoz bera olmaysiz — kuzatyapsiz", "Вы наблюдаете", "You are watching")}</small>
    <div class="mf-prog"><i style="width:${Math.round(100 * voted / Math.max(1, total))}%"></i><span>${voted}/${total} ${T("ovoz berdi", "проголосовали", "voted")}</span></div></div>`;
  const list = alive().filter((p) => p.u !== R.me).sort((a, b) => (b.v || []).length - (a.v || []).length).map((p) => {
    const who = (p.v || []).map((u) => { const q = R.players.find((x) => x.u === u); return q ? esc(q.n) : "?"; });
    const n = who.length;
    return actRow(p, T("🗳 Ovoz", "🗳 Голос", "🗳 Vote"), R.myvote === p.u, n ? `<em class="mf-vn">${n}</em> ${who.join(", ")}` : T("hali ovoz yo'q", "голосов нет", "no votes yet"), R.alive ? "r-vote" : "ro");
  }).join("");
  return head + `<div class="mf-acts">${list}${R.alive ? `<button class="mf-act abst ${R.myvote === 0 ? "on" : ""}" data-a="abstain"><span class="mf-aa e">🤐</span><span class="mf-an"><b>${T("Betaraf qolish", "Воздержаться", "Abstain")}</b><small>${T("hech kimga ovoz bermayman", "ни за кого", "no one")}</small></span><span class="mf-ab">${R.myvote === 0 ? "✅" : "—"}</span></button>` : ""}</div>`;
}
function checksHtml() {
  return `<div class="mf-card r-kom"><b>🔍 ${T("Tekshiruvlar", "Проверки", "Checks")}</b>${R.checks.map((c) => { const p = R.players.find((x) => x.u === c.t); return `<div class="mf-chk ${c.r}">${c.d}-${T("tun", "ночь", "night")}: <b>${esc(p ? p.n : "?")}</b> — ${c.r === "maf" ? "🔪 MAFIA" : "✅ " + T("tinch", "мирный", "innocent")}</div>`; }).join("")}</div>`;
}
function voteBars() {
  const rows = R.players.filter((p) => p.v && p.v.length).sort((a, b) => b.v.length - a.v.length);
  if (!rows.length) return "";
  const max = rows[0].v.length;
  return `<div class="mf-bars">${rows.map((p) => `<div class="mf-barr"><i style="width:${Math.round(100 * p.v.length / Math.max(max, 1))}%"></i><span class="mf-ba">${MC(p.lk, PAL[p.c || 0])}</span><b>${esc(p.n)}</b><span class="mf-who">${p.v.map((u) => { const q = R.players.find((x) => x.u === u); return `<em>${esc((q && q.n || "?").replace("@", "")[0] || "?")}</em>`; }).join("")}</span><strong>${p.v.length}</strong></div>`).join("")}</div>`;
}
function endHtml(inline) {
  const w = R.win;
  const t = {civ: T("🏆 Tinch aholi yutdi!", "🏆 Победили мирные!", "🏆 Civilians win!"), maf: T("🔪 Mafia yutdi!", "🔪 Победила мафия!", "🔪 Mafia wins!"), many: T("🪓 Manyak yutdi!", "🪓 Победил маньяк!", "🪓 The maniac wins!"), cancel: T("O'yin bekor qilindi", "Игра отменена", "Game cancelled")}[w] || "";
  const mine = R.role ? (isMaf(R.role) ? "maf" : R.role === "many" ? "many" : "civ") : "";
  const won = mine && mine === w;
  return `<div class="mf-card ${w === "civ" ? "r-doc" : w === "maf" ? "r-maf" : ""}"><b style="font-size:20px">${t}</b>${mine && w !== "cancel" ? `<small>${won ? "🎉 " + T("Siz yutdingiz!", "Вы победили!", "You won!") : "😔 " + T("Bu safar yutqazdingiz", "В этот раз поражение", "You lost this time")}</small>` : ""}</div>
   ${inline ? `<div class="mf-two"><button class="mf-cta" data-a="again">🔁 ${T("Yana o'ynash", "Ещё раз", "Play again")}</button><button class="mf-ghost" data-a="exit">${T("Chiqish", "Выйти", "Exit")}</button></div>` : ""}`;
}

// ---------- chat
function readable() {
  if (!R) return ["all"];
  const out = ["all"];
  if (isMaf(R.role) || R.phase === "end" && chat.some((x) => x.ch === "maf")) out.push("maf");
  if (!R.in || (R.in && !R.alive) || R.phase === "end" && chat.some((x) => x.ch === "dead")) out.push("dead");
  return out;
}
function renderChat() {
  const tabs = readable();
  const nm = {all: "💬 " + T("Umumiy", "Общий", "All"), maf: "🔪 " + T("Mafia", "Мафия", "Mafia"), dead: "👻 " + T("O'liklar", "Мёртвые", "Dead")};
  $("mftabs").innerHTML = tabs.length > 1 ? tabs.map((t) => `<button data-tab="${t}" class="${tab === t ? "on" : ""} t-${t}">${nm[t]}${chat.filter((x) => x.ch === t).length ? "" : ""}</button>`).join("") : `<span class="mf-tabt">${nm.all}</span>`;
  const can = R.ch.includes(tab);
  $("mfin").classList.toggle("off", !can);
  $("mfemo").classList.toggle("off", !can);
  const inp = $("mftext");
  if (inp) inp.placeholder = can ? (tab === "maf" ? T("Mafia chati — faqat sheriklar ko'radi", "Чат мафии", "Mafia chat") : T("Xabar yozing…", "Сообщение…", "Message…")) : (R.phase === "night" ? T("Tunda aholi jim…", "Ночью мирные молчат…", "Civilians sleep at night…") : T("Hozir yozib bo'lmaydi", "Сейчас нельзя", "Can't write now"));
  if (inp) inp.disabled = !can;
  const feed = $("mffeed");
  const list = chat.filter((x) => x.ch === tab).slice(-80);
  const key = tab + ":" + (list.length ? list[list.length - 1].i : 0) + ":" + list.length;
  if (feed.dataset.k === key) return;
  feed.dataset.k = key;
  const atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 60;
  feed.innerHTML = list.length ? list.map((x) => {
    const p = R.players.find((q) => q.u === x.u);
    const mine = x.u === R.me;
    const body = x.v ? `<button class="mf-voice" data-voice="${esc(x.v)}">▶ <span>▂▅▇▅▃▂▅▇▃▂</span> ${x.d ? x.d + "s" : ""}</button>` : x.e && !x.t ? `<span class="mf-bigemo">${esc(x.e)}</span>` : esc(x.t);
    return `<div class="mf-msg ${mine ? "mine" : ""}"><span class="mf-ma">${p ? MC(p.lk, PAL[p.c || 0]) : "👀"}</span><div class="mf-mt"><b>${esc(x.n || (p && p.n) || "?")}</b>${body}</div></div>`;
  }).join("") : `<p class="mf-fine c">${tab === "maf" ? T("Mafia chati bo'sh. Sherigingizga yozing.", "Пусто. Напишите напарнику.", "Empty. Text your partner.") : T("Hali xabar yo'q", "Сообщений нет", "No messages yet")}</p>`;
  if (atBottom || feed.dataset.first !== "1") { feed.scrollTop = feed.scrollHeight; feed.dataset.first = "1"; }
}
async function sendText() {
  const i = $("mftext"); if (!i) return;
  const t = i.value.trim(); if (!t) return;
  i.value = "";
  await post("chat", {ch: tab, t});
}

// 🎤 ovozli xabar: bir bosish — yozish boshlanadi, yana bosish — yuboriladi (30 s gacha)
let rec = null, recChunks = [], recAt = 0, recStream = null, recTimer = null, recCancel = false;
async function recToggle() {
  if (rec) { recStop(); return; }
  if (!R || !R.ch.includes(tab)) { toast(ERR().chat); return; }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) { toast(T("Bu telefonda ovoz yozib bo'lmaydi", "Запись недоступна", "Recording isn't supported here")); return; }
  try {
    recStream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
    const mt = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"].find((x) => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(x)) || "";
    rec = new MediaRecorder(recStream, mt ? {mimeType: mt} : undefined);
    recChunks = []; recAt = Date.now(); recCancel = false;
    rec.ondataavailable = (e) => { if (e.data && e.data.size) recChunks.push(e.data); };
    rec.onstop = upload;
    rec.start(500);
    const mic = $("mfmic"); mic.classList.add("rec"); haptic("ok");
    const inp = $("mftext"); if (inp) { inp.dataset.ph = inp.placeholder; inp.value = ""; }
    recTimer = setInterval(() => {
      const s = Math.floor((Date.now() - recAt) / 1000);
      if (inp) inp.placeholder = `🔴 ${T("Yozilmoqda", "Запись", "Recording")} 0:${String(s).padStart(2, "0")} — ${T("yuborish uchun ⏹ ni bosing", "нажмите ⏹", "tap ⏹ to send")}`;
      if (s >= 30) recStop();
    }, 250);
    mic.textContent = "⏹";
  } catch (e) { rec = null; toast(T("Mikrofonga ruxsat bering (Telegram sozlamalarida)", "Разрешите микрофон", "Allow microphone access")); }
}
function recStop() {
  if (!rec) return;
  clearInterval(recTimer);
  try { rec.requestData && rec.requestData(); } catch (e) {}
  try { rec.stop(); } catch (e) {}
  setTimeout(() => { try { recStream.getTracks().forEach((t) => t.stop()); } catch (e) {} }, 300);
  const mic = $("mfmic"); if (mic) { mic.classList.remove("rec"); mic.textContent = "🎤"; }
  const inp = $("mftext"); if (inp && inp.dataset.ph) inp.placeholder = inp.dataset.ph;
}
async function upload() {
  const r = rec; rec = null;
  const dur = Math.max(1, Math.round((Date.now() - recAt) / 1000));
  if (recCancel || !recChunks.length) return;
  const type = (r && r.mimeType) || (recChunks[0] && recChunks[0].type) || "audio/webm";
  const blob = new Blob(recChunks, {type});
  if (blob.size < 800) { toast(T("Juda qisqa — yana urinib ko'ring", "Слишком коротко", "Too short")); return; }
  const ext = /mp4|aac|m4a/.test(type) ? "m4a" : /ogg/.test(type) ? "ogg" : "webm";
  const fd = new FormData(); fd.append("ch", tab); fd.append("d", String(dur)); fd.append("a", blob, "v." + ext);
  toast("📤 " + T("Yuborilmoqda…", "Отправка…", "Sending…"));
  const res = await api("api/mafia/voice", null, fd);
  if (res.room) applyRoom(res.room);
  if (!res.ok) toast(ERR()[res.error] || ERR().server); else haptic("ok");
}
let player = null, playing = "";
function playVoice(tok, btn) {
  try {
    if (player) { player.pause(); document.querySelectorAll(".mf-voice.on").forEach((b) => b.classList.remove("on")); }
    if (playing === tok) { playing = ""; return; }
    player = new Audio("api/mafia/v/" + tok);
    player.preload = "auto";
    playing = tok;
    if (btn) btn.classList.add("on");
    player.onended = () => { playing = ""; if (btn) btn.classList.remove("on"); };
    player.onerror = () => { playing = ""; if (btn) btn.classList.remove("on"); toast(T("Ovozli xabarni ochib bo'lmadi", "Не удалось воспроизвести", "Couldn't play")); };
    const pr = player.play();
    if (pr && pr.catch) pr.catch(() => { playing = ""; if (btn) btn.classList.remove("on"); toast(T("Ovozni yoqish uchun yana bosing", "Нажмите ещё раз", "Tap again to play")); });
  } catch (e) {}
}

// =================================================================== animatsiyalar (overlay)
function ov(html, cls, ms, onEnd) {
  ovQueue.push({html, cls, ms, onEnd});
  if (!ovBusy) nextOv();
}
function nextOv() {
  const it = ovQueue.shift();
  const el = $("mfov");
  if (!it) { ovBusy = false; el.hidden = true; el.innerHTML = ""; return; }
  ovBusy = true; el.hidden = false; el.className = "mf-ov " + (it.cls || ""); el.innerHTML = it.html;
  if (typeof it.onEnd === "function" && it.ms === 0) { it.onEnd(el, nextOv); return; }
  setTimeout(() => { if (it.onEnd) it.onEnd(el); nextOv(); }, it.ms);
}
function transitions(prev) {
  const key = `${R.phase}:${R.day}`;
  if (key === seenKey) return;
  const first = !seenKey;
  seenKey = key;
  if (first && !["roles", "hang", "morning", "end"].includes(R.phase)) return;
  if (R.phase === "roles" && R.role) roleOv();
  else if (R.phase === "night" && !first) { SFX.night(); ov(`<div class="o-night"><div class="mf-moon3"></div><b>🌙 ${R.day + 1}-${T("tun", "ночь", "night")}</b><span>${T("Shahar uxlaydi… mafia uyg'onadi", "Город засыпает… просыпается мафия", "The city sleeps… the mafia wakes")}</span></div>`, "", 2200); }
  else if (R.phase === "morning") morningOv();
  else if (R.phase === "last") { SFX.drum(); haptic("hit"); }
  else if (R.phase === "hang") hangOv();
  else if (R.phase === "end" && R.win && R.win !== "cancel") { (R.win === (isMaf(R.role) ? "maf" : R.role === "many" ? "many" : "civ") ? SFX.win : SFX.sad)(); ov(`<div class="o-end">${endHtml(false)}<div class="o-roles">${R.players.map((p) => `<div class="${p.alive ? "" : "d"}"><span>${charOf(p, p.role)}</span><b>${esc(p.n)}</b><i class="r-${(ROLE[p.role] || ROLE.civ).c}">${(ROLE[p.role] || ROLE.civ).ic} ${(ROLE[p.role] || ROLE.civ).n}</i></div>`).join("")}</div><small>${T("Bosing — yopish", "Нажмите, чтобы закрыть", "Tap to close")}</small></div>`, "end", 6500); }
}
function roleOv() {
  const r = ROLE[R.role], m = me();
  SFX.chime(); haptic("ok");
  ov(`<div class="o-role"><div class="o-flip"><div class="o-back">?</div><div class="o-front r-${r.c}"><span class="o-art">${charOf(m || {lk: "bozor"}, R.role)}</span>
     <div class="o-nm"><small>${T("SIZNING ROLINGIZ", "ВАША РОЛЬ", "YOUR ROLE")}</small><b>${r.ic} ${r.n.toUpperCase()}</b><p>${r.d}</p>
     ${isMaf(R.role) ? `<p class="o-mates">🔪 ${T("Sheriklar", "Напарники", "Partners")}: ${R.players.filter((p) => isMaf(p.role) && p.u !== R.me).map((p) => esc(p.n)).join(", ") || "—"}</p>` : ""}</div></div></div></div>`, "role", 5200);
}
function morningOv() {
  const n = R.news || {};
  const dead = (n.dead || []).map((d) => R.players.find((p) => p.u === d.u)).filter(Boolean);
  if (dead.length) {
    setTimeout(() => { SFX.bang(); haptic("hit"); }, 600);
    ov(`<div class="o-morn"><div class="o-flash"></div><b class="o-bang">BANG!</b>${dead.map((p) => `<div class="o-victim"><span>${charOf(p, p.role)}</span></div>`).join("")}
      <div class="o-news"><small>🦉 ${T("TONG XABARI", "УТРЕННИЕ НОВОСТИ", "MORNING NEWS")}</small><b>${dead.map((p) => esc(p.n)).join(", ")} — ${T("o'ldirildi", "убит(а)", "killed")}</b><p>${dead.map((p) => `${esc(p.n)}: ${(ROLE[p.role] || ROLE.civ).ic} ${(ROLE[p.role] || ROLE.civ).n}`).join(" · ")}</p></div></div>`, "morn", 4600);
  } else if (n.saved) {
    setTimeout(() => { SFX.bang(); }, 500); setTimeout(() => { SFX.chime(); haptic("ok"); }, 1100);
    ov(`<div class="o-morn save"><b class="o-bang">BANG!</b><div class="o-shield"></div><b class="o-tirik">${T("TIRIK!", "ЖИВ!", "ALIVE!")}</b>
      <div class="o-news"><small>🦉 ${T("TONG XABARI", "УТРЕННИЕ НОВОСТИ", "MORNING NEWS")}</small><b>${T("Bu tun hech kim o'lmadi!", "Этой ночью никто не умер!", "Nobody died tonight!")}</b><p>💉 ${T("Shifokor kimnidir o'q ostidan olib qoldi", "Доктор кого-то спас", "The doctor saved someone")}</p></div></div>`, "morn", 4200);
  } else {
    SFX.chime();
    ov(`<div class="o-morn quiet"><span class="o-owl">${MC("boyqush")}</span><div class="o-news"><small>🦉 ${T("TONG XABARI", "УТРЕННИЕ НОВОСТИ", "MORNING NEWS")}</small><b>${T("Tinch tun o'tdi", "Тихая ночь", "A quiet night")}</b><p>${T("Hech kim o'lmadi. Mafia nima qilyapti ekan?", "Никто не умер. Что задумала мафия?", "Nobody died. What is the mafia up to?")}</p></div></div>`, "morn", 3400);
  }
}
function hangOv() {
  const h = R.hang;
  if (!h) { SFX.sad(); ov(`<div class="o-nohang"><b>⚖️ ${T("Hech kim osilmadi", "Никого не казнили", "Nobody was hanged")}</b><span>${T("Ovozlar teng bo'ldi — shahar ikkilandi", "Голоса разделились", "The vote was split")}</span></div>`, "", 2600); return; }
  const p = R.players.find((x) => x.u === h.u) || {lk: "bozor", n: "?"};
  const civ = MC(p.lk, PAL[p.c || 0]), r = ROLE[h.r] || ROLE.civ, maf = isMaf(h.r);
  ov(`<div class="o-hang"><div class="o-dusk"></div><svg class="o-gal" viewBox="0 0 390 520"><rect x="40" y="380" width="310" height="18" fill="#160808"/><rect x="60" y="398" width="14" height="122" fill="#160808"/><rect x="316" y="398" width="14" height="122" fill="#160808"/>
     <rect x="290" y="60" width="18" height="322" fill="#160808"/><rect x="170" y="52" width="138" height="18" fill="#160808"/><path d="M290 96l-40-34h16l28 24z" fill="#160808"/><path d="M196 70v60" stroke="#2A1408" stroke-width="4"/><ellipse cx="196" cy="146" rx="15" ry="18" fill="none" stroke="#2A1408" stroke-width="4"/>
     <g class="o-trap"><rect x="150" y="374" width="46" height="8" fill="#3A1A0C"/><rect x="196" y="374" width="46" height="8" fill="#3A1A0C"/></g></svg>
     <div class="o-cond">${civ}</div><span class="o-tag">${esc(p.n)}</span>
     <div class="o-crowd">${R.players.filter((x) => x.u !== h.u).slice(0, 6).map((x, i) => `<span style="left:${i * 17 - 4}%">${MC(x.lk)}</span>`).join("")}</div>
     <b class="o-count" id="mfcnt">3</b><div class="o-curtain"></div>
     <div class="o-reveal ${maf ? "maf" : "civ"}"><div class="o-rc"><span>${maf ? MC(r.ch, r.v) : civ}</span><div><small>${esc(p.n)} ${T("ASLIDA", "НА САМОМ ДЕЛЕ", "WAS")}</small><b>${r.ic} ${r.n.toUpperCase()} ${T("EDI!", "", "")}</b></div></div>
      <p>${maf ? T("To'g'ri topdingiz! 🎉", "Угадали! 🎉", "You got it! 🎉") : T("Begunoh odam osildi… 😞", "Казнили невиновного… 😞", "An innocent was hanged… 😞")}</p></div></div>`, "hang", 0, (el, done) => {
    const c = el.querySelector("#mfcnt");
    let n = 3;
    SFX.drum(); haptic("hit");
    const iv = setInterval(() => {
      n--;
      if (n > 0) { c.textContent = n; c.classList.remove("pop"); void c.offsetWidth; c.classList.add("pop"); SFX.drum(); haptic("hit"); return; }
      clearInterval(iv); c.remove();
      const hg = el.querySelector(".o-hang") || el;
      hg.classList.add("drop"); SFX.thud(); haptic("err");
      setTimeout(() => { hg.classList.add("rev"); (maf ? SFX.win : SFX.sad)(); }, 900);
      setTimeout(done, 4600);
    }, 1000);
  });
}

// =================================================================== hodisalar
async function loadHome() { const r = await api("api/mafia/home"); if (r.ok) { H = r; if (!R) render(); } }
async function enterWith(path, body) {
  const r = await api("api/mafia/" + path, body || {});
  if (!r.ok || !r.room) { haptic("err"); toast(ERR()[r.error] || ERR().server); return; }
  haptic("ok"); applyRoom(r.room); startPoll();
}
function onClick(e) {
  const t = e.target;
  const seg = t.closest("[data-mode]");
  if (seg) { if (seg.dataset.mode !== "mafia" && window.ZK_setMode) window.ZK_setMode(seg.dataset.mode); return; }
  if ($("mfov") && !$("mfov").hidden && t.closest("#mfov") && $("mfov").classList.contains("end")) { ovQueue = []; nextOv(); return; }
  let el;
  if ((el = t.closest("[data-p]"))) {
    const u = +el.dataset.p;
    if (!R) return;
    if (R.phase === "night" && (R.targets || []).includes(u)) { haptic(); post("act", R.role === "kom" ? {t: u, m: komMode} : {t: u}); }
    else if (R.phase === "vote" && R.alive && u !== R.me) { const p = R.players.find((x) => x.u === u); if (p && p.alive) { haptic(); post("vote", {t: u}); } }
    return;
  }
  if ((el = t.closest("[data-look]"))) { const m = me(); lsSet("mf_lk", el.dataset.look); post("look", {lk: el.dataset.look, c: m ? m.c : 0}); haptic(); return; }
  if ((el = t.closest("[data-col]"))) { const m = me(); post("look", {lk: m ? m.lk : "bozor", c: +el.dataset.col}); haptic(); return; }
  if ((el = t.closest("[data-km]"))) { komMode = el.dataset.km; haptic(); renderCtrl(); return; }
  if ((el = t.closest("[data-tab]"))) { tab = el.dataset.tab; haptic(); renderChat(); return; }
  if ((el = t.closest("[data-emo]"))) { post("chat", {ch: tab, e: el.dataset.emo}); haptic(); return; }
  if ((el = t.closest("[data-voice]"))) { playVoice(el.dataset.voice, el); return; }
  if (t.closest("#mfmic")) { recToggle(); return; }
  if (!(el = t.closest("[data-a]"))) return;
  const a = el.dataset.a;
  if (a === "homeback") { if (window.ZK_setMode) window.ZK_setMode("kino"); else if (window.ZMafia) window.ZMafia.close(); }
  else if (a === "hub") { if (window.ZHub) window.ZHub.open("mafia"); }
  else if (a === "quick") enterWith("quick", {lk: lsGet("mf_lk", "")});
  else if (a === "create") enterWith("create", {lk: lsGet("mf_lk", "")});
  else if (a === "join") { const v = ($("mfcode") || {}).value || ""; if (v.replace(/\D/g, "").length !== 4) { toast(T("4 xonali kodni kiriting", "Введите 4-значный код", "Enter the 4-digit code")); return; } enterWith("join", {code: v}); }
  else if (a === "resume") { api("api/mafia/poll?v=-1&m=0").then((r) => { if (r.ok && r.room) { applyRoom(r.room); startPoll(); } else loadHome(); }); }
  else if (a === "group") {
    const bot = (H && H.bot) || "";
    toast(T("Botni guruhga qo'shing va /mafia yozing", "Добавьте бота в группу и напишите /mafia", "Add the bot to a group and send /mafia"));
    try { if (window.ZK_BOT || bot) tg.openTelegramLink(`https://t.me/${window.ZK_BOT || bot}?startgroup=mafia`); } catch (er) {}
  }
  else if (a === "grpopen") { const g = H && H.grp; if (g) { haptic(); try { tg.openTelegramLink(g.url); } catch (er) { location.href = g.url; } } }
  else if (a === "grpedit") { grpEdit = true; haptic(); renderHome(); setTimeout(() => { const i = $("mfgurl"); if (i) i.focus(); }, 50); }
  else if (a === "grpx") { grpEdit = false; renderHome(); }
  else if (a === "grpsave" || a === "grpdel") {
    const url = a === "grpdel" ? "" : (($("mfgurl") || {}).value || "").trim(), title = (($("mfgttl") || {}).value || "").trim();
    api("api/mafia/grp", {url, title}).then((r) => {
      if (!r.ok) { haptic("err"); toast(r.error === "bad_link" ? T("Havola noto'g'ri — https://t.me/... yoki @guruh", "Неверная ссылка — https://t.me/... или @группа", "Bad link — use https://t.me/... or @group") : ERR()[r.error] || ERR().server); return; }
      haptic("ok"); grpEdit = false; if (H) H.grp = r.grp; renderHome();
      toast(r.grp ? T("✅ Saqlandi", "✅ Сохранено", "✅ Saved") : T("🗑 Olib tashlandi", "🗑 Удалено", "🗑 Removed"));
    });
  }
  else if (a === "start") post("start");
  else if (a === "skip") post("skip");
  else if (a === "abstain") post("vote", {t: 0});
  else if (a === "send") sendText();
  else if (a === "copy") { try { navigator.clipboard.writeText(R.code); } catch (er) {} haptic("ok"); toast(T("Kod nusxalandi", "Код скопирован", "Code copied")); }
  else if (a === "share") {
    const txt = T(`🔪 Men bilan Mafia o'ynang! Xona kodi: ${R.code}`, `🔪 Сыграем в Мафию! Код: ${R.code}`, `🔪 Play Mafia with me! Code: ${R.code}`);
    const rawBot = window.ZK_BOT || (H && H.bot) || (window.Telegram && Telegram.WebApp && Telegram.WebApp.initDataUnsafe && Telegram.WebApp.initDataUnsafe.bot_username) || "Bauntyfilmsbot";
    const cleanBot = rawBot.replace(/^@/, "");
    const link = cleanBot ? `https://t.me/${cleanBot}?start=mafia_${R.code}` : location.origin;
    try { tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(txt)}`); } catch (er) { try { navigator.clipboard.writeText(txt + " " + link); toast(T("Havola nusxalandi", "Ссылка скопирована", "Link copied")); } catch (e2) {} }
  }
  else if (a === "again") { const pub = R && R.pub; leave(true).then(() => enterWith(pub ? "quick" : "create", {lk: lsGet("mf_lk", "")})); }
  else if (a === "exit") leave(true);
  else if (a === "back") back();
}
async function leave(force) {
  stopPoll();
  await api("api/mafia/leave", {});
  R = null; ver = -1; chat = []; seenKey = "";
  ovQueue = []; if ($("mfov")) { $("mfov").hidden = true; ovBusy = false; }
  await loadHome(); render();
}
function back() {
  if (!R) return;
  const live = R.in && R.alive && !["lobby", "end"].includes(R.phase);
  if (live && Date.now() - leaveArm > 3500) { leaveArm = Date.now(); haptic("err"); toast(T("Chiqsangiz — o'yindan chiqarilasiz. Yana bosing", "Выход = выбывание. Нажмите ещё раз", "Leaving = out of the game. Tap again")); return; }
  leave(true);
}
function updateBack() {
  if (!inTg) return;
  try { opened ? tg.BackButton.show() : (window.ZK_canHideBack ? window.ZK_canHideBack() && tg.BackButton.hide() : tg.BackButton.hide()); } catch (e) {}
}
if (inTg) tg.BackButton.onClick(() => {
  if (!opened) return;
  if (R) back();
  else if (window.ZK_setMode) window.ZK_setMode("kino");
  else if (window.ZMafia) window.ZMafia.close();
});

window.ZMafia = {
  open() {
    if (!mounted) {
      mounted = true;
      const root = $("mafia");
      root.addEventListener("click", onClick);
      root.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id === "mftext") { e.preventDefault(); sendText(); } if (e.key === "Enter" && e.target.id === "mfcode") { e.preventDefault(); const b = root.querySelector('[data-a="join"]'); if (b) b.click(); } });
      setInterval(() => { if (opened && R && R.players.length <= 8 && Object.keys(lastBubble).length) { const now = Date.now(); let ch = false; for (const k in lastBubble) if (now - lastBubble[k].at > 6000) { delete lastBubble[k]; ch = true; } if (ch) renderStage(); } }, 1500);
    }
    opened = true;
    $("mafia").hidden = false; document.body.classList.add("mf-on");
    render();
    loadHome().then(() => api("api/mafia/poll?v=-1&m=0")).then((r) => { if (opened && r && r.ok && r.room) { applyRoom(r.room); startPoll(); } else render(); });
  },
  close() { opened = false; stopPoll(); recCancel = true; recStop(); $("mafia").hidden = true; document.body.classList.remove("mf-on"); updateBack(); },
  busy() { return opened && !!R; },
  join(code) { enterWith("join", {code: String(code)}); },
  _mc: MC,
  _demo(room, kind) { if (kind === "room") { applyRoom(room); return; } R = room; ({hang: hangOv, morning: morningOv, role: roleOv})[kind](); },   // vizual sinov uchun
};
})();
