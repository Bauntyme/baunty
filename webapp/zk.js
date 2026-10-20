/* ✨ Bauntys — umumiy dizayn qatlami: jonli girih-ipak fon (WebGL), bo'lim almashganda siljuvchi indikator,
   kirish animatsiyasi, kino "tasodifiy" g'ildiragi va TOP qatori uchun 3D karusel.
   Bo'limlar (music/books/...) o'zgarmaydi — bu fayl faqat ularning ustidan bezak qo'shadi va hech narsani buzmaydi:
   biror narsa ishlamasa (WebGL yo'q, eski telefon) — jimgina oddiy fonga qaytadi. */
(() => {
"use strict";
const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
const body = document.body;
const tg = window.Telegram && Telegram.WebApp;
const haptic = (k) => { try { k === "ok" ? tg.HapticFeedback.notificationOccurred("success") : tg.HapticFeedback.impactOccurred(k || "light"); } catch (e) {} };
body.classList.add("zk");

// ------------------------------------------------------------------ bo'lim ranglari
const PAL = {
  kino:  {c: ["#2A0B1E", "#C8344C", "#EDB54E"], acc: "#F2B84B", ink: "#2A1500"},
  music: {c: ["#03202A", "#1FA8AE", "#2F6BFF"], acc: "#3EE6D6", ink: "#02221F"},
  books: {c: ["#0A1240", "#2440C8", "#EDB54E"], acc: "#F0B43C", ink: "#2A1A00"},
  games: {c: ["#2A1000", "#FF7A1A", "#FF2E7E"], acc: "#FFB020", ink: "#2A1400"},
  story: {c: ["#170730", "#8B5CFF", "#FF77BC"], acc: "#FF8CC8", ink: "#2A0018"},
  docs:  {c: ["#071A24", "#1F7A8C", "#F2B84B"], acc: "#F2C14E", ink: "#241800"},
  tv:    {c: ["#120A2A", "#5B3FB8", "#45E8CB"], acc: "#7FE3D3", ink: "#06221F"},
  fx:    {c: ["#04201A", "#1C8F6A", "#2440C8"], acc: "#4FE0A6", ink: "#04261A"},
  food:  {c: ["#2A0B12", "#C8344C", "#F2B84B"], acc: "#FF7A59", ink: "#2A0A05"},
  quiz:  {c: ["#120A3A", "#5B3FD8", "#12A99A"], acc: "#8F7CFF", ink: "#14093A"},
  prava: {c: ["#0B1114", "#2B3A40", "#C99A2E"], acc: "#FFC53A", ink: "#2A1E00"},
};
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
const modeNow = () => body.dataset.zkm || "kino";
let colT = PAL.kino.c.map(hex), colC = colT.map((a) => a.slice()), lastMode = "";
function applyMode(m) {
  const p = PAL[m] || PAL.kino;
  colT = p.c.map(hex);
  const r = document.documentElement.style;
  r.setProperty("--zk-acc", p.acc); r.setProperty("--zk-ink", p.ink);
  try { tg && tg.setHeaderColor && tg.setHeaderColor(p.c[0]); tg && tg.setBackgroundColor && tg.setBackgroundColor("#070B1F"); } catch (e) {}
}

// ------------------------------------------------------------------ jonli fon (WebGL)
const cv = document.createElement("canvas");
cv.id = "zkbg"; cv.setAttribute("aria-hidden", "true");
body.prepend(cv);
const FS = `precision mediump float;
uniform vec2 r;uniform float t;uniform vec3 c1,c2,c3;uniform vec2 tp;uniform float tt;uniform vec2 tilt;
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1.,0.)),f.x),mix(h(i+vec2(0.,1.)),h(i+vec2(1.,1.)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*n(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}
float girih(vec2 p){vec2 q=fract(p)-.5;
 float d1=abs(max(abs(q.x),abs(q.y))-.24);
 vec2 s=vec2(q.x+q.y,q.x-q.y)*.70710678;
 float d2=abs(max(abs(s.x),abs(s.y))-.24);
 float d3=abs(abs(q.x)+abs(q.y)-.5);
 float d4=abs(length(q)-.09);
 return min(min(d1,d2),min(d3,d4));}
void main(){
 vec2 uv=gl_FragCoord.xy/r;
 vec2 p=(gl_FragCoord.xy-.5*r)/r.y;
 vec2 ps=p+tilt*.04;
 float tm=t*.05;
 vec2 q=vec2(fbm(ps*1.5+vec2(tm,0.)),fbm(ps*1.5+vec2(3.1,-tm)));
 float f=fbm(ps*1.25+q*1.7+vec2(tm*1.4,-tm*.8));
 vec3 col=mix(c1,c2,smoothstep(.28,.8,f));
 col=mix(col,c3,smoothstep(.52,.95,q.x*f*1.7)*.6);
 col*=.34+.5*f;
 col+=(1.-smoothstep(0.,.07,abs(f-.56)))*.16*mix(c3,vec3(1.),.3);
 vec2 gp=(p+tilt*.02)*5.2;
 float lw=5.2*2.2/r.y;
 float g=girih(gp);
 float ln=1.-smoothstep(0.,lw,g);
 float d=length(p-tp);
 float wave=exp(-pow((d-tt*.85)*6.,2.))*exp(-tt*1.3);
 float rev=.035+.03*sin(t*.7+p.y*2.5+p.x*1.5)+wave*1.4;
 col+=ln*rev*mix(c3,vec3(1.,.93,.78),.35)*.6+wave*.14*c2;
 col*=1.-.62*pow(length(uv-vec2(.5,.45))*1.2,2.2);
 gl_FragColor=vec4(col,1.);
}`;
let gl = null, U = {}, ok = false;
try {
  gl = cv.getContext("webgl", {antialias: false, alpha: false, depth: false, stencil: false, powerPreference: "low-power"});
  if (gl) {
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error("shader"); return s; };
    const pr = gl.createProgram();
    gl.attachShader(pr, sh(gl.VERTEX_SHADER, "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}"));
    gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error("link");
    gl.useProgram(pr);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, "a"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    ["r", "t", "c1", "c2", "c3", "tp", "tt", "tilt"].forEach((k) => U[k] = gl.getUniformLocation(pr, k));
    cv.addEventListener("webglcontextlost", (e) => { e.preventDefault(); ok = false; body.classList.add("zk-nogl"); });
    ok = true;
  }
} catch (e) { ok = false; }
if (!ok) body.classList.add("zk-nogl");

let W = 0, H = 0;
function resize() {
  W = innerWidth; H = innerHeight;
  const k = Math.min(devicePixelRatio || 1, 2) * (slow > 20 ? .33 : .5);
  cv.width = Math.max(1, Math.round(W * k)); cv.height = Math.max(1, Math.round(H * k));
  if (ok) gl.viewport(0, 0, cv.width, cv.height);
  dirty = true;
}
let ripple = {x: 0, y: 0, t0: -99}, tiltT = {x: 0, y: 0}, tiltC = {x: 0, y: 0}, dirty = true, touched = performance.now(), slow = 0;
const poke = () => { touched = performance.now(); };
["pointerdown", "pointermove", "keydown"].forEach((ev) => addEventListener(ev, poke, {passive: true}));
addEventListener("scroll", poke, {passive: true, capture: true});
addEventListener("pointerdown", (e) => {
  ripple = {x: (e.clientX - W / 2) / H, y: (H / 2 - e.clientY) / H, t0: performance.now() / 1000};
}, {passive: true});
addEventListener("pointermove", (e) => { tiltT = {x: (e.clientX / W - .5) * 2, y: (e.clientY / H - .5) * 2}; }, {passive: true});
addEventListener("resize", resize);
resize();

// To'liq ekranli oyna (pleyer, o'quvchi, TV, o'yin) ochiq bo'lsa — fon ko'rinmaydi, chizish to'xtaydi (batareya)
const covered = () => document.hidden ||
  !!document.querySelector("#tvp.open,#det.open,.m-player.open,.m-rec.open") ||
  body.classList.contains("rd-on") || (window.ZGames && body.classList.contains("g-on") && ZGames.busy && ZGames.busy());

let last = 0, frames = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const m = modeNow();
  if (m !== lastMode) { lastMode = m; applyMode(m); dirty = true; }
  if (!ok) return;
  if (covered()) return;
  const moving = !RM;
  if (!moving && !dirty && now - ripple.t0 * 1000 > 2500) return;
  // faol paytda ~30 kadr/s, jim turganda ~12 kadr/s (batareya); sekin telefonda yanada kam
  const gap = (now - touched < 8000 ? 33 : 80) * (slow > 20 ? 1.8 : 1);
  if (now - last < gap) return;
  if (last && now - last < 400) { if (now - last > gap + 45) { if (++slow === 21) resize(); } else if (slow > 0 && slow < 20) slow--; }
  const dt = Math.min(4, (now - last) / 16.7); last = now;
  for (let k = 0; k < 3; k++) for (let j = 0; j < 3; j++) colC[k][j] += (colT[k][j] - colC[k][j]) * Math.min(1, .05 * dt);
  tiltC.x += (tiltT.x - tiltC.x) * .05 * dt; tiltC.y += (tiltT.y - tiltC.y) * .05 * dt;
  const ts = now / 1000;
  gl.uniform2f(U.r, cv.width, cv.height);
  gl.uniform1f(U.t, RM ? 20 : ts);
  gl.uniform3fv(U.c1, colC[0]); gl.uniform3fv(U.c2, colC[1]); gl.uniform3fv(U.c3, colC[2]);
  gl.uniform2f(U.tp, ripple.x, ripple.y);
  gl.uniform1f(U.tt, ts - ripple.t0);
  gl.uniform2f(U.tilt, tiltC.x, -tiltC.y);
  gl.drawArrays(gl.TRIANGLES, 0, 6);
  if (++frames > 2) dirty = false;
}
applyMode(modeNow());
requestAnimationFrame(frame);

// ------------------------------------------------------------------ bo'limlar paneli: siljuvchi indikator
const SEG_SEL = "#seg,.m-seg,.bx-seg,.sx-seg,.gx-seg,.dx-seg,.fx-seg,.fd-seg,.qz-seg";
let prevRect = null;
function decorate(seg) {
  const on = seg.querySelector("button.on");
  if (!on || seg.offsetParent === null) return false;
  let ind = seg.querySelector(":scope>.zk-ind");
  const fresh = !ind;
  if (fresh) { ind = document.createElement("i"); ind.className = "zk-ind"; ind.setAttribute("aria-hidden", "true"); seg.prepend(ind); }
  const sr = seg.getBoundingClientRect(), br = on.getBoundingClientRect();
  const x = br.left - sr.left + seg.scrollLeft, w = br.width;
  const key = `${x.toFixed(1)}:${w.toFixed(1)}`;
  if (ind.dataset.k === key) return fresh;
  ind.dataset.k = key;
  ind.style.transform = `translateX(${x}px)`; ind.style.width = w + "px";
  if (fresh && prevRect && !RM && prevRect.m !== modeNow()) {
    const fx = prevRect.left - sr.left + seg.scrollLeft;
    ind.animate([{transform: `translateX(${fx}px)`, width: prevRect.width + "px"}, {transform: `translateX(${x}px)`, width: w + "px"}],
      {duration: 520, easing: "cubic-bezier(.34,1.4,.64,1)"});
  }
  prevRect = {left: br.left, width: w, m: modeNow()};
  if (br.right > sr.right - 8 || br.left < sr.left + 8) {
    try { on.scrollIntoView({inline: "center", block: "nearest", behavior: fresh ? "auto" : "smooth"}); } catch (e) {}
  }
  return fresh;
}
let segQueued = false, lastHdr = "";
function scanSegs() {
  if (segQueued) return; segQueued = true;
  requestAnimationFrame(() => {
    segQueued = false;
    let home = false;
    document.querySelectorAll(SEG_SEL).forEach((sg) => { if (sg.offsetParent !== null) home = true; if (decorate(sg)) lastHdr = ""; });
    // bo'lim bosh sahifasida Telegram sarlavhasi ham fon rangida (ba'zi bo'limlar o'zinikini qo'yadi)
    body.classList.toggle("zk-home", home);
    if (home) donRoom();
    if (home) { const c = (PAL[modeNow()] || PAL.kino).c[0]; if (c !== lastHdr) { lastHdr = c; try { tg && tg.setHeaderColor && tg.setHeaderColor(c); } catch (e) {} } } else lastHdr = "";
    flowScan();
  });
}
new MutationObserver(scanSegs).observe(body, {childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"]});
addEventListener("resize", () => { document.querySelectorAll(".zk-ind").forEach((i) => { i.dataset.k = ""; }); scanSegs(); });
document.addEventListener("click", (e) => { if (e.target.closest(SEG_SEL)) haptic("light"); }, true);

// ------------------------------------------------------------------ kino: TOP qatori — 3D karusel
function flowScan() {
  document.querySelectorAll("#main .row:not(.zk-flow)").forEach((row) => {
    if (!row.querySelector(".card")) return;
    row.classList.add("zk-flow");
    const upd = () => {
      const r = row.getBoundingClientRect(), mid = r.left + r.width / 2;
      row.querySelectorAll(".card").forEach((c) => {
        const b = c.getBoundingClientRect(), d = Math.max(-1.6, Math.min(1.6, (b.left + b.width / 2 - mid) / (b.width * 1.15)));
        const a = Math.abs(d);
        c.style.transform = RM ? "" : `perspective(700px) rotateY(${(-d * 24).toFixed(1)}deg) scale(${(1 - Math.min(a, 1) * .1).toFixed(3)})`;
        c.style.zIndex = String(10 - Math.round(a * 3));
        c.classList.toggle("zk-mid", a < .5);
      });
    };
    row.addEventListener("scroll", () => requestAnimationFrame(upd), {passive: true});
    requestAnimationFrame(upd);
  });
}

// ------------------------------------------------------------------ kino: tasodifiy kino g'ildiragi
function slotHTML() {
  const d = document.createElement("div");
  d.className = "zk-slot"; d.id = "zkslot"; d.hidden = true; d.setAttribute("role", "dialog"); d.setAttribute("aria-label", "Tasodifiy kino");
  d.innerHTML = `<b class="zk-slot-t">Taqdir tanlaydi</b><div class="zk-slot-w"><div class="zk-slot-s" id="zkstrip"></div></div><span class="zk-slot-n" id="zkslotn" aria-live="polite"></span>`;
  body.appendChild(d);
  return d;
}
let spinning = false;
window.ZK_spin = (items, open) => {
  if (spinning || !items || !items.length) return;
  spinning = true;
  const slot = document.getElementById("zkslot") || slotHTML(), strip = document.getElementById("zkstrip");
  const N = Math.min(26, Math.max(8, items.length + 2)), pick = items[Math.floor(Math.random() * items.length)];
  const poster = (it) => `<div class="zk-slot-i">${it.i ? `<img src="p/${it.c}_s.webp?v=${it.i}" alt="" decoding="async">` : ""}<span>${String(it.t).replace(/[&<>]/g, "")}</span></div>`;
  let html = "";
  for (let i = 0; i < N; i++) html += poster(i === N - 1 ? pick : items[Math.floor(Math.random() * items.length)]);
  strip.innerHTML = html;
  document.getElementById("zkslotn").textContent = "";
  slot.hidden = false; requestAnimationFrame(() => slot.classList.add("on"));
  const hgt = strip.firstElementChild.getBoundingClientRect().height || 270, dist = (N - 1) * hgt;
  const tick = setInterval(() => haptic("light"), 120);
  const done = () => {
    clearInterval(tick); haptic("ok");
    document.getElementById("zkslotn").textContent = pick.t;
    ripple = {x: 0, y: 0, t0: performance.now() / 1000};
    setTimeout(() => { slot.classList.remove("on"); setTimeout(() => { slot.hidden = true; spinning = false; open(pick); }, 260); }, 850);
  };
  if (RM || !strip.animate) { strip.style.transform = `translateY(-${dist}px)`; done(); return; }
  const a = strip.animate([
    {transform: "translateY(0)", filter: "blur(0px)"},
    {transform: `translateY(-${Math.round(dist * .3)}px)`, filter: "blur(6px)", offset: .25},
    {transform: `translateY(-${Math.round(dist * .93)}px)`, filter: "blur(1.5px)", offset: .75},
    {transform: `translateY(-${dist}px)`, filter: "blur(0px)"}], {duration: 2400, easing: "cubic-bezier(.25,.7,.25,1)", fill: "forwards"});
  a.onfinish = done;
};

// ------------------------------------------------------------------ 💛 Donat: tepa o'ngda tugma → karta oynasi
const HEART = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 21s-7.6-4.6-9.5-9.3C1.2 8.3 3.5 4.8 7 4.8c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3 3.5 0 5.8 3.5 4.5 6.9C19.6 16.4 12 21 12 21z"/></svg>';
const escH = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
let don = null, donIx = 0;
const FOREIGN = ["Visa", "Mastercard"];
const donCards = () => (don && Array.isArray(don.cards) && don.cards.length ? don.cards : (don && don.num ? [{num: don.num, name: don.name, net: don.net}] : []));
// tugma tepa o'ngda turadi: bo'lim sarlavha qatorining (tablar + o'ng tugmalar) o'ng tomonidan joy bo'shatamiz
function donRoom() {
  const pill = document.getElementById("zkdon");
  if (!pill || !pill.offsetWidth) return;
  const edge = pill.getBoundingClientRect().left - 8;
  document.querySelectorAll(SEG_SEL).forEach((sg) => {
    const row = sg.parentElement;
    if (!row || sg.offsetParent === null) return;
    if (row.dataset.zkpr === undefined) row.dataset.zkpr = parseFloat(getComputedStyle(row).paddingRight) || 0;
    const r = row.getBoundingClientRect(), need = Math.ceil(r.right - edge);
    const pad = Math.max(+row.dataset.zkpr, need);
    if (Math.abs((parseFloat(row.style.paddingRight) || 0) - pad) > 1) {
      row.style.paddingRight = pad + "px"; row.style.boxSizing = "border-box";
      const ind = sg.querySelector(":scope>.zk-ind"); if (ind) ind.dataset.k = "";
      decorate(sg);
    }
  });
}
const donTrack = (t) => { try { fetch("api/donate/ev", {method: "POST", headers: {"Content-Type": "application/json", "X-Init-Data": (tg && tg.initData) || ""}, body: JSON.stringify({t})}).catch(() => {}); } catch (e) {} };
function donSheet() {
  let el = document.getElementById("zkdonsheet");
  if (el) return el;
  el = document.createElement("div");
  el.id = "zkdonsheet"; el.className = "zk-donbg"; el.hidden = true;
  el.innerHTML = `<div class="zk-dons" role="dialog" aria-modal="true" aria-labelledby="zkdont">
    <i class="grip" aria-hidden="true"></i>
    <div class="dh"><span class="hz">${HEART}</span><span class="dt"><b id="zkdont">Botni qo'llab-quvvatlang</b><small>Har bir hissa botni yaxshilaydi</small></span>
      <button class="dcl" type="button" aria-label="Yopish"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div>
    <div class="zk-dtabs" id="zkdontabs" role="tablist" hidden></div>
    <div class="zk-card" id="zkdoncard"><svg class="gir" viewBox="-60 -60 120 120" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="2"><rect x="-36" y="-36" width="72" height="72"/><rect x="-36" y="-36" width="72" height="72" transform="rotate(45)"/><circle r="16"/></g></svg>
      <i class="glow" aria-hidden="true"></i>
      <div class="ct"><span>BAUNTYS · DONAT</span><b id="zkdonnet"></b></div><i class="chip" aria-hidden="true"></i>
      <div class="num" id="zkdonnum"></div><div class="hold"><span id="zkdonname"></span><span id="zkdonhold">karta egasi</span></div></div>
    <button class="zk-copy" type="button" id="zkdoncopy"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="3"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg><span>Karta raqamini nusxalash</span></button>
    <div class="zk-done" id="zkdondone" hidden role="status"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 5 5 9-10"/></svg><span>Nusxa olindi — to'lov ilovangizga qo'ying</span></div>
    <div class="zk-note"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg><span id="zkdontext"></span></div>
    <p class="zk-thx">Rahmat! Siz bilan bot yanada zo'r bo'ladi 💛</p></div>`;
  body.appendChild(el);
  const close = () => { el.classList.remove("on"); setTimeout(() => { el.hidden = true; }, 280); };
  el.addEventListener("click", (e) => {
    if (e.target === el || e.target.closest(".dcl")) { close(); return; }
    const tb = e.target.closest("[data-dc]");
    if (tb) { donIx = +tb.dataset.dc; donPaint(true); haptic("light"); }
  });
  addEventListener("keydown", (e) => { if (e.key === "Escape" && !el.hidden) close(); });
  el.querySelector("#zkdoncopy").addEventListener("click", () => {
    const raw = ((donCards()[donIx] || {}).num || "").replace(/\D/g, "");
    const ok = () => { el.querySelector("#zkdondone").hidden = false; haptic("ok"); donTrack("copy"); };
    const fallback = () => {
      try {
        const t = document.createElement("textarea"); t.value = raw; t.setAttribute("readonly", ""); t.style.cssText = "position:fixed;opacity:0;left:-99px";
        body.appendChild(t); t.select(); const done = document.execCommand("copy"); t.remove();
        if (done) { ok(); return; }
      } catch (e) {}
      const n = el.querySelector("#zkdonnum"); const r = document.createRange(); r.selectNodeContents(n);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
      el.querySelector("#zkdondone span").textContent = "Raqam belgilandi — «Nusxalash»ni bosing"; el.querySelector("#zkdondone").hidden = false;
    };
    try { navigator.clipboard.writeText(raw).then(ok, fallback); } catch (e) { fallback(); }
  });
  return el;
}
// bir nechta karta (masalan Uzcard + chet elliklar uchun Visa) — tepada tanlash tugmalari
function donPaint(swap) {
  const el = donSheet(), cards = donCards(), c = cards[donIx] || cards[0] || {};
  const foreign = FOREIGN.includes(c.net);
  const tabs = el.querySelector("#zkdontabs");
  tabs.hidden = cards.length < 2;
  tabs.innerHTML = cards.map((k, i) => {
    const f = FOREIGN.includes(k.net);
    return `<button type="button" role="tab" data-dc="${i}" aria-selected="${i === donIx}"${i === donIx ? ' class="on"' : ""}>` +
      `<span aria-hidden="true">${f ? "🌍" : "🇺🇿"}</span>${escH(k.net || "Karta")}${f ? "<small>chet eldan</small>" : ""}</button>`;
  }).join("");
  const card = el.querySelector("#zkdoncard");
  card.classList.toggle("intl", foreign);
  if (swap && !RM) card.animate([{transform: "rotateY(14deg) scale(.96)", opacity: .4}, {transform: "none", opacity: 1}], {duration: 360, easing: "cubic-bezier(.2,1.2,.4,1)"});
  el.querySelector("#zkdonnum").textContent = c.num || "";
  el.querySelector("#zkdonnet").textContent = c.net || "";
  el.querySelector("#zkdonname").textContent = (c.name || "").toUpperCase();
  el.querySelector("#zkdonhold").textContent = foreign ? "card holder" : "karta egasi";
  el.querySelector("#zkdoncopy span").textContent = foreign ? "Karta raqamini nusxalash · Copy" : "Karta raqamini nusxalash";
  el.querySelector("#zkdondone span").textContent = foreign ? "Nusxa olindi · Copied" : "Nusxa olindi — to'lov ilovangizga qo'ying";
  el.querySelector("#zkdondone").hidden = true;
}
function openDonate() {
  if (!don) return;
  const el = donSheet();
  if (donIx >= donCards().length) donIx = 0;
  donPaint(false);
  const tx = String(don.text || ""), cut = tx.indexOf(".");
  el.querySelector("#zkdontext").innerHTML = cut > 0 && cut < 60 ? `<b>${escH(tx.slice(0, cut + 1))}</b>${escH(tx.slice(cut + 1))}` : escH(tx);
  el.hidden = false; requestAnimationFrame(() => el.classList.add("on"));
  haptic("light"); donTrack("open");
}
fetch("api/donate").then((r) => r.json()).then((d) => {
  if (!d || !d.on || !(d.num || (d.cards && d.cards.length))) return;
  don = d;
  const b = document.createElement("button");
  b.type = "button"; b.id = "zkdon"; b.className = "zk-don"; b.setAttribute("aria-label", "Donat — botni qo'llab-quvvatlash");
  b.innerHTML = `<span class="hz">${HEART}</span><span>Donat</span>`;
  b.addEventListener("click", openDonate);
  body.appendChild(b); body.classList.add("zk-don-on");
  requestAnimationFrame(donRoom);
}).catch(() => {});

// ------------------------------------------------------------------ kirish animatsiyasi
const sp = document.getElementById("zksplash");
if (sp) {
  const t0 = performance.now();
  const end = () => {
    if (!sp.isConnected) return;
    sp.classList.add("out");
    document.body.classList.remove("splashing");
    ripple = {x: 0, y: 0, t0: performance.now() / 1000};
    setTimeout(() => sp.remove(), 650);
  };
  sp.addEventListener("pointerdown", end);
  const MIN = RM ? 900 : 2500;
  const wait = () => { const el = performance.now() - t0; el > MIN ? end() : setTimeout(end, MIN - el); };
  if (document.readyState === "complete") wait(); else addEventListener("load", wait);
  setTimeout(end, 4000);
}
})();


// --- Test & Backward Compatibility Helpers ---
window.updateFlowCenter = function() { try { if (window.ZK_updateFlow) window.ZK_updateFlow(); } catch(e){} };
window.initFlow = function() { try { if (window.ZK_initFlow) window.ZK_initFlow(); } catch(e){} };
window.spinRoulette = function(pool, cb) { if (window.ZK_spin) return window.ZK_spin(pool, cb); if (pool && pool.length) cb(pool[0]); };
window.updateIndicator = function() { try { const seg = document.getElementById("seg"); if (seg && seg._zkUpdate) seg._zkUpdate(); } catch(e){} };
window.initSplash = function() { try { const sp = document.getElementById("zksplash"); if (sp) sp.classList.add("out");
    document.body.classList.remove("splashing"); } catch(e){} };
