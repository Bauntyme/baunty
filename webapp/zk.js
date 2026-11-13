/* ✨ Bauntys — umumiy dizayn qatlami ("Samarqand tuni"): koinot WebGL foni, 2D yulduzlar va meteoritlar,
   bo'lim almashganda siljuvchi indikator, tasodifiy kino g'ildiragi, TOP karusel va Donat oynasi. */
(() => {
"use strict";
const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
const body = document.body;
const tg = window.Telegram && window.Telegram.WebApp;
const haptic = (k) => { try { k === "ok" ? tg.HapticFeedback.notificationOccurred("success") : tg.HapticFeedback.impactOccurred(k || "light"); } catch (e) {} };
const escH = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

// ------------------------------------------------------------------ 💛 Donat karta oynasi (Kreativ va Oddiy rejimda ham ishlaydi)
const HEART = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 21s-7.6-4.6-9.5-9.3C1.2 8.3 3.5 4.8 7 4.8c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3 3.5 0 5.8 3.5 4.5 6.9C19.6 16.4 12 21 12 21z"/></svg>';
let don = null, donIx = 0;
const FOREIGN = ["Visa", "Mastercard"];
const donCards = () => (don && Array.isArray(don.cards) && don.cards.length ? don.cards : (don && don.num ? [{num: don.num, name: don.name, net: don.net}] : []));
const donTrack = (t) => { try { fetch("api/donate/ev", {method: "POST", headers: {"Content-Type": "application/json", "X-Init-Data": (tg && tg.initData) || ""}, body: JSON.stringify({t})}).catch(() => {}); } catch (e) {} };

function donSheet() {
  let el = document.getElementById("zkdonsheet");
  if (el) return el;
  el = document.createElement("div");
  el.id = "zkdonsheet"; el.className = "zk-donbg"; el.hidden = true;
  el.innerHTML = `<div class="zk-dons" role="dialog" aria-modal="true" aria-labelledby="zkdont">
    <i class="grip" aria-hidden="true"></i>
    <button class="zdcl" type="button" aria-label="Yopish"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
    <div class="zdh"><span class="hz">${HEART}</span><span class="zdt"><b id="zkdont">Botni qo'llab-quvvatlang</b><small>Har bir hissa botni yaxshilaydi</small></span></div>
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
    if (e.target === el || e.target.closest(".zdcl")) { close(); return; }
    const tb = e.target.closest("[data-dc]");
    if (tb) { donIx = +tb.dataset.dc; donPaint(true); haptic("light"); }
  });
  addEventListener("keydown", (e) => { if (e.key === "Escape" && !el.hidden) close(); });
  el.querySelector("#zkdoncopy").addEventListener("click", () => {
    const raw = ((donCards()[donIx] || {}).num || "").replace(/\D/g, "");
    const okCopy = () => { el.querySelector("#zkdondone").hidden = false; haptic("ok"); donTrack("copy"); };
    const fallback = () => {
      try {
        const t = document.createElement("textarea"); t.value = raw; t.setAttribute("readonly", ""); t.style.cssText = "position:fixed;opacity:0;left:-99px";
        body.appendChild(t); t.select(); const copied = document.execCommand("copy"); t.remove();
        if (copied) { okCopy(); return; }
      } catch (e) {}
      const n = el.querySelector("#zkdonnum"), r = document.createRange(); r.selectNodeContents(n);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
      el.querySelector("#zkdondone span").textContent = "Raqam belgilandi — «Nusxalash»ni bosing";
      el.querySelector("#zkdondone").hidden = false;
    };
    try { navigator.clipboard.writeText(raw).then(okCopy, fallback); } catch (e) { fallback(); }
  });
  return el;
}

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
  if (swap && !RM && card.animate) card.animate([{transform: "rotateY(14deg) scale(.96)", opacity: .4}, {transform: "none", opacity: 1}], {duration: 360, easing: "cubic-bezier(.2,1.2,.4,1)"});
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

fetch("api/donate?lang=" + encodeURIComponent(window.ZK_LANG || "uz")).then((r) => r.json()).then((d) => {
  if (!d || !d.on || !(d.num || (d.cards && d.cards.length))) return;
  don = d;
  window.ZK_openDonate = openDonate;
}).catch(() => {});

if (window.ZK_LITE) {
  const s = document.getElementById("zksplash"); if (s) s.remove();
  const zi = document.getElementById("zkintro"); if (zi) zi.remove();
  return;
}
body.classList.add("zk");

// ------------------------------------------------------------------ bo'lim koinot ranglari
const PAL = {
  kino:   {c: ["#140A02", "#FFA50F", "#FF5A3D"], acc: "#F2B84B", ink: "#2A1500"},
  music:  {c: ["#0E0420", "#B000FF", "#FF5A00"], acc: "#E17BFF", ink: "#1E0030"},
  books:  {c: ["#030C24", "#127FFF", "#A8D8FF"], acc: "#6FB8FF", ink: "#001A3A"},
  games:  {c: ["#170700", "#FF5A00", "#FFB020"], acc: "#FFB020", ink: "#2A1400"},
  story:  {c: ["#0F0322", "#B030FF", "#FF77BC"], acc: "#D48CFF", ink: "#2A0018"},
  docs:   {c: ["#011418", "#00C8E0", "#7FF3FF"], acc: "#4FE6F5", ink: "#002830"},
  tv:     {c: ["#020C22", "#0A8EFF", "#46ACFF"], acc: "#6FC0FF", ink: "#001A3A"},
  tvroom: {c: ["#040924", "#4F46E5", "#38BDF8"], acc: "#60A5FA", ink: "#04122E"},
  bunker: {c: ["#091318", "#059669", "#F59E0B"], acc: "#34D399", ink: "#032217"},
  deliv:  {c: ["#081402", "#8FE600", "#FFB02E"], acc: "#B4FF3A", ink: "#102000"},
  dlv:    {c: ["#081402", "#8FE600", "#FFB02E"], acc: "#B4FF3A", ink: "#102000"},
  duel:   {c: ["#170510", "#E11D48", "#F97316"], acc: "#FB7185", ink: "#2A0410"},
  fx:     {c: ["#02160D", "#00C45A", "#6DFFB0"], acc: "#4FE0A6", ink: "#04261A"},
  food:   {c: ["#081402", "#8FE600", "#FFB02E"], acc: "#B4FF3A", ink: "#102000"},
  quiz:   {c: ["#0A0828", "#8A84FF", "#C9C6FF"], acc: "#AAA6FF", ink: "#14093A"},
  prava:  {c: ["#160A04", "#D4835C", "#FFC53A"], acc: "#E8A27F", ink: "#2A1E00"},
  rasxod: {c: ["#02160D", "#00FB76", "#C6FFDE"], acc: "#4FF0A0", ink: "#00240F"},
  kal:    {c: ["#021612", "#14D9A0", "#B4FF3A"], acc: "#5EF0C8", ink: "#002A1E"},
  mafia:  {c: ["#030205", "#5A0610", "#FF2E3A"], acc: "#FF4A55", ink: "#fff"},
};
const palOf = (m) => PAL[m] || PAL.kino;
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
const modeNow = () => body.dataset.zkm || "kino";
let colT = palOf("kino").c.map(hex), colC = colT.map((a) => a.slice()), lastMode = "", mfT = 0, mfC = 0;

function applyMode(m) {
  const p = palOf(m);
  colT = p.c.map(hex);
  mfT = m === "mafia" ? 1 : 0;
  const r = document.documentElement.style;
  r.setProperty("--zk-acc", p.acc); r.setProperty("--zk-ink", p.ink);
  try { tg && tg.setHeaderColor && tg.setHeaderColor(p.c[0]); tg && tg.setBackgroundColor && tg.setBackgroundColor("#070B1F"); } catch (e) {}
}

// ------------------------------------------------------------------ jonli koinot foni (WebGL + Canvas2D fallback)
const cv = document.createElement("canvas");
cv.id = "zkbg"; cv.setAttribute("aria-hidden", "true");
body.prepend(cv);
const FS = `precision mediump float;
uniform vec2 r;uniform float t;uniform vec3 c1,c2,c3;uniform vec2 tp;uniform float tt;uniform vec2 tilt;uniform float mf;
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1.,0.)),f.x),mix(h(i+vec2(0.,1.)),h(i+vec2(1.,1.)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*n(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}
void main(){
 vec2 uv=gl_FragCoord.xy/r;
 vec2 p=(gl_FragCoord.xy-.5*r)/r.y;
 vec2 ps=p+tilt*.03;
 float tm=t*.018;
 vec2 q=vec2(fbm(ps*1.1+vec2(tm,0.)),fbm(ps*1.1+vec2(5.2,-tm)));
 float f=fbm(ps*1.5+q*2.1+vec2(-tm*1.3,tm*.7));
 float band=exp(-pow((ps.y+ps.x*.55)*2.1,2.));
 vec3 col=vec3(.008,.011,.03)+c1*.55;
 col+=c2*pow(f,2.3)*(.42+.7*band);
 col+=c3*pow(clamp(q.x*f*1.3,0.,1.),3.)*.8;
 col+=vec3(.5,.56,.78)*band*.07*f;
 float dust=fbm(ps*4.+vec2(tm*3.,0.));col*=.82+.3*smoothstep(.35,.75,dust);
 if(mf>.01){
  vec2 mp=ps-vec2(-.17,-.27);float d=length(mp);
  float moon=smoothstep(.115,.108,d);
  float cr=fbm(mp*16.+3.);
  vec3 mc=mix(vec3(.62,.07,.06),vec3(.95,.25,.16),smoothstep(.12,-.1,mp.x+mp.y))*(1.-.45*cr);
  col=mix(col,mc,moon*mf);
  col+=vec3(.7,.06,.05)*(exp(-d*5.5)*.55+exp(-d*14.)*.4)*mf*(1.-moon);
  float fog=fbm(vec2(ps.x*1.6-t*.025,ps.y*2.6+t*.01));
  col+=vec3(.32,.03,.05)*fog*smoothstep(.15,-.55,ps.y)*mf;
 }
 float dd=length(p-tp);
 float wave=exp(-pow((dd-tt*.85)*6.,2.))*exp(-tt*1.3);
 col+=wave*.16*mix(c3,vec3(1.),.4);
 col*=1.-.5*pow(length(uv-vec2(.5,.45))*1.2,2.2);
 gl_FragColor=vec4(col,1.);
}`;

let gl = null, U = {}, ok = false, bg2d = null;
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
    ["r", "t", "c1", "c2", "c3", "tp", "tt", "tilt", "mf"].forEach((k) => U[k] = gl.getUniformLocation(pr, k));
    cv.addEventListener("webglcontextlost", (e) => { e.preventDefault(); ok = false; body.classList.add("zk-nogl"); });
    ok = true;
  }
} catch (e) { ok = false; }

if (!ok) {
  body.classList.add("zk-nogl");
  if (!gl) { try { bg2d = cv.getContext("2d"); } catch (e) { bg2d = null; } }
}

function drawNebulaFallback(m) {
  if (!bg2d || !cv.width || !cv.height) return;
  const p = palOf(m), W0 = cv.width, H0 = cv.height;
  bg2d.fillStyle = "#070B1F";
  bg2d.fillRect(0, 0, W0, H0);
  const g1 = bg2d.createRadialGradient(W0 * .2, H0 * .15, 0, W0 * .2, H0 * .15, Math.max(W0, H0) * .7);
  g1.addColorStop(0, p.c[1] + "55"); g1.addColorStop(1, "transparent");
  bg2d.fillStyle = g1; bg2d.fillRect(0, 0, W0, H0);
  const g2 = bg2d.createRadialGradient(W0 * .85, H0 * .75, 0, W0 * .85, H0 * .75, Math.max(W0, H0) * .65);
  g2.addColorStop(0, p.c[2] + "44"); g2.addColorStop(1, "transparent");
  bg2d.fillStyle = g2; bg2d.fillRect(0, 0, W0, H0);
}

// ------------------------------------------------------------------ 🌠 yulduzlar va meteoritlar (2D, ko'rshapalaklar yo'q)
const sky = (() => {
  const c = document.createElement("canvas");
  c.id = "zksky"; c.setAttribute("aria-hidden", "true");
  cv.after(c);
  const x = c.getContext("2d");
  const ROCK = new Image(); ROCK.src = "rock.webp";
  const SC = ["#ffffff", "#cfe0ff", "#a9c8ff", "#fff1d6", "#ffd9b0"];
  let w = 0, h = 0, d = 1, st = [], big = [], mt = [], em = [], nextRock = 0, nextShoot = 0;
  const glare = (() => {
    const g = document.createElement("canvas"), z = 64, m = 32; g.width = g.height = z; const k = g.getContext("2d");
    const rg = k.createRadialGradient(m, m, 0, m, m, m); rg.addColorStop(0, "rgba(255,255,255,1)"); rg.addColorStop(.12, "rgba(255,255,255,.7)");
    rg.addColorStop(.35, "rgba(200,220,255,.14)"); rg.addColorStop(1, "rgba(0,0,0,0)"); k.fillStyle = rg; k.fillRect(0, 0, z, z);
    k.globalCompositeOperation = "lighter";
    let l = k.createLinearGradient(0, m, z, m); l.addColorStop(0, "rgba(255,255,255,0)"); l.addColorStop(.5, "rgba(255,255,255,.85)"); l.addColorStop(1, "rgba(255,255,255,0)");
    k.fillStyle = l; k.fillRect(0, m - .6, z, 1.2);
    l = k.createLinearGradient(m, 0, m, z); l.addColorStop(0, "rgba(255,255,255,0)"); l.addColorStop(.5, "rgba(255,255,255,.85)"); l.addColorStop(1, "rgba(255,255,255,0)");
    k.fillStyle = l; k.fillRect(m - .6, 0, 1.2, z); return g;
  })();
  function size(lowPower) {
    d = lowPower ? 1 : Math.min(2, devicePixelRatio || 1);
    w = c.width = Math.round(innerWidth * d); h = c.height = Math.round(innerHeight * d);
    const n = Math.round(Math.min(260, innerWidth * innerHeight / 1500) * (lowPower ? .55 : 1));
    st = []; for (let i = 0; i < n; i++) st.push({x: Math.random() * w, y: Math.random() * h, v: (.04 + Math.random() * .22) * d,
      r: (Math.random() < .86 ? .4 + Math.random() * 1 : 1.2 + Math.random() * 1.4) * d, c: SC[Math.random() * SC.length | 0], p: Math.random() * 6.3, s: .4 + Math.random() * 2});
    big = []; for (let i = 0; i < (lowPower ? 6 : 14); i++) big.push({x: Math.random() * w, y: Math.random() * h, v: (.08 + Math.random() * .2) * d, z: (9 + Math.random() * 20) * d, p: Math.random() * 6.3, s: .5 + Math.random() * 1.5});
  }
  function rock(now) {
    const sz = (38 + Math.random() * 62) * d * Math.min(1, innerWidth / 390), a = Math.PI * (.62 + Math.random() * .12), v = (2.4 + Math.random() * 2) * d;
    mt.push({t0: now, rock: 1, sz, x: w * (.35 + Math.random() * .9) + sz, y: -sz * 1.5, vx: Math.cos(a) * v, vy: Math.sin(a) * v, rot: Math.random() * 6.3, vr: (Math.random() - .5) * .03});
  }
  function shoot(now) {
    const a = Math.PI * (.6 + Math.random() * .15), v = (10 + Math.random() * 6) * d;
    mt.push({t0: now, x: w * (.2 + Math.random() * 1.1), y: -20 - Math.random() * h * .3, vx: Math.cos(a) * v, vy: Math.sin(a) * v, len: (90 + Math.random() * 130) * d});
  }
  let sized = false;
  return {
    resize(lowPower) { size(lowPower); sized = true; },
    draw(now, dt, mf) {
      if (!x) return;
      if (!sized) size(false);
      x.globalCompositeOperation = "source-over"; x.globalAlpha = 1; x.clearRect(0, 0, w, h);
      const k = now;
      for (const o of st) { o.y += o.v * dt; o.x -= o.v * .3 * dt; if (o.y > h + 4) { o.y = -4; o.x = Math.random() * w * 1.15; }
        x.globalAlpha = (.3 + .7 * Math.abs(Math.sin(o.p + k / 1000 * o.s))) * (1 - mf * .35);
        x.fillStyle = mf > .5 && o.r > 1.2 * d ? "#ffd0c8" : o.c; x.beginPath(); x.arc(o.x, o.y, o.r, 0, 7); x.fill(); }
      x.globalCompositeOperation = "lighter";
      for (const o of big) { o.y += o.v * dt; o.x -= o.v * .3 * dt; if (o.y > h + 20) { o.y = -20; o.x = Math.random() * w * 1.15; }
        x.globalAlpha = (.5 + .5 * Math.sin(o.p + k / 1000 * o.s)) * (1 - mf * .4); x.drawImage(glare, o.x - o.z / 2, o.y - o.z / 2, o.z, o.z); }
      if (!nextShoot) { nextShoot = k + 2500; nextRock = k + 5000; }
      if (k > nextShoot) { shoot(k); nextShoot = k + 4000 + Math.random() * 4000; }
      if (mf < .5 && k > nextRock) { rock(k); nextRock = k + 7000 + Math.random() * 6000; }
      for (let i = mt.length - 1; i >= 0; i--) { const o = mt[i];
        o.x += o.vx * dt; o.y += o.vy * dt; const n = Math.hypot(o.vx, o.vy), ux = o.vx / n, uy = o.vy / n;
        if (o.rock) {
          if (o.y > h + o.sz * 3 || o.x < -o.sz * 4) { mt.splice(i, 1); continue; }
          const L = o.sz * 3.2, R = o.sz * .42, px = -uy, py = ux, fl = 1 + .12 * Math.sin(k / 40 + i);
          for (const [wk, lk, c0, c1] of [[1, 1, "rgba(255,70,0,.5)", "rgba(120,20,0,0)"], [.7, .75, "rgba(255,170,40,.7)", "rgba(255,90,0,0)"], [.38, .45, "rgba(255,250,210,.95)", "rgba(255,200,90,0)"]]) {
            const ww = R * wk * fl, len = L * lk * fl, tx = o.x - ux * len, ty = o.y - uy * len, g = x.createLinearGradient(o.x, o.y, tx, ty);
            g.addColorStop(0, c0); g.addColorStop(1, c1); x.globalAlpha = 1; x.fillStyle = g; x.beginPath(); x.moveTo(o.x + px * ww, o.y + py * ww);
            x.quadraticCurveTo(o.x - ux * len * .45 + px * ww * .55, o.y - uy * len * .45 + py * ww * .55, tx, ty);
            x.quadraticCurveTo(o.x - ux * len * .45 - px * ww * .55, o.y - uy * len * .45 - py * ww * .55, o.x - px * ww, o.y - py * ww);
            x.arc(o.x, o.y, ww, Math.atan2(-py, -px), Math.atan2(py, px), false); x.fill();
          }
          const hg = x.createRadialGradient(o.x, o.y, 0, o.x, o.y, o.sz * 1.1); hg.addColorStop(0, "rgba(255,170,60,.5)"); hg.addColorStop(1, "rgba(255,80,0,0)");
          x.fillStyle = hg; x.beginPath(); x.arc(o.x, o.y, o.sz * 1.1, 0, 7); x.fill();
          if (em.length < 120) em.push({x: o.x - ux * R, y: o.y - uy * R, vx: o.vx * .15 + (Math.random() - .5) * d, vy: o.vy * .15 + (Math.random() - .5) * d, l: 1, r: (1 + Math.random() * 1.8) * d});
          x.globalCompositeOperation = "source-over"; x.save(); x.translate(o.x, o.y); x.rotate(o.rot + o.vr * (k - o.t0) / 16);
          if (ROCK.complete && ROCK.naturalWidth) x.drawImage(ROCK, -o.sz / 2, -o.sz * .56, o.sz, o.sz * 1.12);
          x.restore(); x.globalCompositeOperation = "lighter";
        } else {
          if (o.y > h + 300) { mt.splice(i, 1); continue; }
          const ex = o.x - ux * o.len, ey = o.y - uy * o.len, g = x.createLinearGradient(o.x, o.y, ex, ey);
          const red = mf > .5;
          g.addColorStop(0, "rgba(255,255,255,.95)"); g.addColorStop(.2, red ? "rgba(255,120,110,.5)" : "rgba(180,210,255,.5)"); g.addColorStop(1, "rgba(120,160,255,0)");
          x.globalAlpha = 1; x.strokeStyle = g; x.lineWidth = 1.5 * d; x.beginPath(); x.moveTo(o.x, o.y); x.lineTo(ex, ey); x.stroke();
          x.drawImage(glare, o.x - 6 * d, o.y - 6 * d, 12 * d, 12 * d);
        }
      }
      for (let i = em.length - 1; i >= 0; i--) { const p = em[i]; p.x += p.vx * dt; p.y += p.vy * dt; p.l -= .025 * dt; if (p.l <= 0) { em.splice(i, 1); continue; }
        x.globalAlpha = p.l; x.fillStyle = p.l > .6 ? "#ffe08a" : "#ff6a1a"; x.beginPath(); x.arc(p.x, p.y, p.r * p.l, 0, 7); x.fill(); }
      x.globalCompositeOperation = "source-over";
    },
  };
})();

let W = 0, H = 0;
function resize() {
  W = innerWidth; H = innerHeight;
  const k = Math.min(devicePixelRatio || 1, 2) * (slow > 20 ? .33 : .5);
  cv.width = Math.max(1, Math.round(W * k)); cv.height = Math.max(1, Math.round(H * k));
  if (ok) gl.viewport(0, 0, cv.width, cv.height);
  else drawNebulaFallback(modeNow());
  sky.resize(slow > 20);
  dirty = true;
}
let ripple = {x: 0, y: 0, t0: -99}, tiltT = {x: 0, y: 0}, tiltC = {x: 0, y: 0}, dirty = true, touched = performance.now(), slow = 0;
const poke = () => { touched = performance.now(); };
["pointerdown", "pointermove", "keydown"].forEach((ev) => addEventListener(ev, poke, {passive: true}));
let scrollT = -1e9;
addEventListener("scroll", () => { poke(); scrollT = performance.now(); }, {passive: true, capture: true});
addEventListener("pointerdown", (e) => {
  ripple = {x: (e.clientX - W / 2) / H, y: (H / 2 - e.clientY) / H, t0: performance.now() / 1000};
}, {passive: true});
addEventListener("pointermove", (e) => { tiltT = {x: (e.clientX / W - .5) * 2, y: (e.clientY / H - .5) * 2}; }, {passive: true});
addEventListener("resize", resize);
resize();

const covered = () => document.hidden ||
  !!document.querySelector("#tvp.open,#det.open,.m-player.open,.m-rec.open") ||
  body.classList.contains("rd-on") ||
  (window.ZGames && body.classList.contains("g-on") && ZGames.busy && ZGames.busy()) ||
  (window.ZTvRoom && document.querySelector("#tvroom:not([hidden])") && ZTvRoom.busy && ZTvRoom.busy());

let last = 0, frames = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const m = modeNow();
  if (m !== lastMode) { lastMode = m; applyMode(m); if (!ok) drawNebulaFallback(m); dirty = true; }
  if (covered()) return;
  if (now - scrollT < 260) return;
  const moving = !RM;
  if (!moving && !dirty && now - ripple.t0 * 1000 > 2500) return;
  const gap = (now - touched < 8000 ? 33 : 80) * (slow > 20 ? 1.8 : 1);
  if (now - last < gap) return;
  if (last && now - last < 400) { if (now - last > gap + 45) { if (++slow === 21) resize(); } else if (slow > 0 && slow < 20) slow--; }
  const dt = Math.min(4, (now - last) / 16.7); last = now;
  for (let k = 0; k < 3; k++) for (let j = 0; j < 3; j++) colC[k][j] += (colT[k][j] - colC[k][j]) * Math.min(1, .05 * dt);
  mfC += (mfT - mfC) * Math.min(1, .05 * dt);
  sky.draw(now, dt, mfC);
  if (!ok) return;
  tiltC.x += (tiltT.x - tiltC.x) * .05 * dt; tiltC.y += (tiltT.y - tiltC.y) * .05 * dt;
  const ts = now / 1000;
  gl.uniform2f(U.r, cv.width, cv.height);
  gl.uniform1f(U.t, RM ? 20 : ts);
  gl.uniform3fv(U.c1, colC[0]); gl.uniform3fv(U.c2, colC[1]); gl.uniform3fv(U.c3, colC[2]);
  gl.uniform2f(U.tp, ripple.x, ripple.y);
  gl.uniform1f(U.tt, ts - ripple.t0);
  gl.uniform2f(U.tilt, tiltC.x, -tiltC.y);
  gl.uniform1f(U.mf, mfC);
  gl.drawArrays(gl.TRIANGLES, 0, 6);
  if (++frames > 2) dirty = false;
}
applyMode(modeNow());
requestAnimationFrame(frame);

// ------------------------------------------------------------------ bo'limlar paneli: siljuvchi indikator
const SEG_SEL = "#seg,.m-seg,.bx-seg,.sx-seg,.gx-seg,.dx-seg,.fx-seg,.fd-seg,.qz-seg,.pv-seg,.rx-seg,.kl-seg,.mf-seg,.bnk-seg,.dl-seg,.dlv-seg,.tvr-seg";
let prevRect = null;
function decorate(seg) {
  const on = seg.querySelector("button.on");
  if (!on || seg.offsetParent === null) return false;
  let ind = seg.querySelector(":scope>.zk-ind");
  const fresh = !ind;
  if (fresh) { ind = document.createElement("i"); ind.className = "zk-ind"; ind.setAttribute("aria-hidden", "true"); seg.prepend(ind); }
  if (fresh) {
    const s0 = seg.getBoundingClientRect(), b0 = on.getBoundingClientRect();
    if (b0.right > s0.right - 8 || b0.left < s0.left + 8) seg.scrollLeft += (b0.left + b0.width / 2) - (s0.left + s0.width / 2);
  }
  const sr = seg.getBoundingClientRect(), br = on.getBoundingClientRect();
  const x = br.left - sr.left + seg.scrollLeft, w = br.width;
  const key = `${x.toFixed(1)}:${w.toFixed(1)}`;
  if (ind.dataset.k === key) return fresh;
  ind.dataset.k = key;
  ind.style.transform = `translateX(${x}px)`; ind.style.width = w + "px";
  if (fresh && prevRect && !RM && prevRect.m !== modeNow() && ind.animate) {
    const fx = prevRect.left - sr.left + seg.scrollLeft;
    ind.animate([{transform: `translateX(${fx}px)`, width: prevRect.width + "px"}, {transform: `translateX(${x}px)`, width: w + "px"}],
      {duration: 360, easing: "cubic-bezier(.22,.9,.3,1)"});
  }
  prevRect = {left: br.left, width: w, m: modeNow()};
  if (!fresh && (br.right > sr.right - 8 || br.left < sr.left + 8)) {
    try { seg.scrollTo({left: seg.scrollLeft + (br.left + br.width / 2) - (sr.left + sr.width / 2), behavior: "smooth"}); } catch (e) {}
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
    body.classList.toggle("zk-home", home);
    if (home) { const c = palOf(modeNow()).c[0]; if (c !== lastHdr) { lastHdr = c; try { tg && tg.setHeaderColor && tg.setHeaderColor(c); } catch (e) {} } } else lastHdr = "";
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
window.ZK_updateFlow = flowScan;
window.ZK_initFlow = flowScan;

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

// ------------------------------------------------------------------ kirish ekrani fallback (#zksplash)
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
  const MIN = RM ? 0 : 300;
  const wait = () => { const el = performance.now() - t0; el >= MIN ? end() : setTimeout(end, MIN - el); };
  if (document.readyState === "complete" || document.readyState === "interactive") wait(); else addEventListener("DOMContentLoaded", wait);
  setTimeout(end, 1200);
}
})();

// --- Test & Backward Compatibility Helpers ---
window.updateFlowCenter = function() { try { if (window.ZK_updateFlow) window.ZK_updateFlow(); } catch (e) {} };
window.initFlow = function() { try { if (window.ZK_initFlow) window.ZK_initFlow(); } catch (e) {} };
window.spinRoulette = function(pool, cb) { if (window.ZK_spin) return window.ZK_spin(pool, cb); if (pool && pool.length) cb(pool[0]); };
window.updateIndicator = function() { try { const seg = document.getElementById("seg"); if (seg && seg._zkUpdate) seg._zkUpdate(); } catch (e) {} };
window.initSplash = function() { try { const sp = document.getElementById("zksplash"); if (sp) sp.classList.add("out"); document.body.classList.remove("splashing"); } catch (e) {} };
