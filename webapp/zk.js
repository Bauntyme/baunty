/* ===================================================================
   🎲 Bauntys Mini App — Samarqand Tuni va Interaktiv Modullar (zk.js)
   Jonli girih-ipak WebGL foni, 3D Coverflow, Oltin Kubik Ruletkasi,
   Splash va Siljuvchi Indikator
   =================================================================== */

(() => {
  "use strict";

  const RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const body = document.body;
  const tg = window.Telegram && Telegram.WebApp;
  const haptic = (k) => {
    try {
      if (!tg || !tg.HapticFeedback) return;
      if (k === "ok") tg.HapticFeedback.notificationOccurred("success");
      else if (k === "err") tg.HapticFeedback.notificationOccurred("error");
      else if (k === "hit") tg.HapticFeedback.impactOccurred("medium");
      else tg.HapticFeedback.selectionChanged();
    } catch (e) {}
  };

  body.classList.add("zk");

  // ------------------------------------------------------------------ 1. Bo'lim ranglari va rejimlari
  const PAL = {
    kino:  { c: ["#070B1F", "#C8344C", "#EDB54E"], acc: "#F2B84B", ink: "#2A1500" },
    music: { c: ["#0E1330", "#1FA8AE", "#2F6BFF"], acc: "#3EE6D6", ink: "#02221F" },
    books: { c: ["#0A1240", "#2440C8", "#EDB54E"], acc: "#F0B43C", ink: "#2A1A00" },
    games: { c: ["#2A1000", "#FF7A1A", "#FF2E7E"], acc: "#FFB020", ink: "#2A1400" },
    story: { c: ["#170730", "#8B5CFF", "#FF77BC"], acc: "#FF8CC8", ink: "#2A0018" },
    docs:  { c: ["#071A24", "#1F7A8C", "#F2B84B"], acc: "#F2C14E", ink: "#241800" },
    tv:    { c: ["#120A2A", "#5B3FB8", "#45E8CB"], acc: "#7FE3D3", ink: "#06221F" },
  };

  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const modeNow = () => body.dataset.zkm || "kino";
  let colT = PAL.kino.c.map(hex), colC = colT.map((a) => a.slice()), lastMode = "";

  function applyMode(m) {
    const p = PAL[m] || PAL.kino;
    colT = p.c.map(hex);
    const r = document.documentElement.style;
    r.setProperty("--zk-acc", p.acc);
    r.setProperty("--zk-ink", p.ink);
    try {
      if (tg && tg.setHeaderColor) tg.setHeaderColor(p.c[0]);
      if (tg && tg.setBackgroundColor) tg.setBackgroundColor("#070B1F");
    } catch (e) {}
  }

  // ------------------------------------------------------------------ 2. Jonli fon (WebGL Samarqand Tuni)
  let cv = document.getElementById("zkbg");
  if (!cv) {
    cv = document.createElement("canvas");
    cv.id = "zkbg";
    cv.setAttribute("aria-hidden", "true");
    body.prepend(cv);
  }

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
    gl = cv.getContext("webgl", { antialias: false, alpha: false, depth: false, stencil: false, powerPreference: "low-power" });
    if (gl) {
      const sh = (type, src) => {
        const s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error("shader");
        return s;
      };
      const pr = gl.createProgram();
      gl.attachShader(pr, sh(gl.VERTEX_SHADER, "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}"));
      gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(pr);
      if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error("link");
      gl.useProgram(pr);
      gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(pr, "a");
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      ["r", "t", "c1", "c2", "c3", "tp", "tt", "tilt"].forEach((k) => U[k] = gl.getUniformLocation(pr, k));
      cv.addEventListener("webglcontextlost", (e) => { e.preventDefault(); ok = false; body.classList.add("zk-nogl"); });
      ok = true;
    }
  } catch (e) {
    ok = false;
  }
  if (!ok) body.classList.add("zk-nogl");

  let W = 0, H = 0, slow = 0, dirty = true, touched = performance.now();
  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    const k = Math.min(window.devicePixelRatio || 1, 2) * (slow > 20 ? 0.33 : 0.5);
    cv.width = Math.max(1, Math.round(W * k));
    cv.height = Math.max(1, Math.round(H * k));
    if (ok && gl) gl.viewport(0, 0, cv.width, cv.height);
    dirty = true;
  }

  let ripple = { x: 0, y: 0, t0: -99 }, tiltT = { x: 0, y: 0 }, tiltC = { x: 0, y: 0 };
  const poke = () => { touched = performance.now(); };
  ["pointerdown", "pointermove", "keydown"].forEach((ev) => window.addEventListener(ev, poke, { passive: true }));
  window.addEventListener("scroll", poke, { passive: true, capture: true });
  window.addEventListener("pointerdown", (e) => {
    ripple = { x: (e.clientX - W / 2) / H, y: (H / 2 - e.clientY) / H, t0: performance.now() / 1000 };
  }, { passive: true });
  window.addEventListener("pointermove", (e) => {
    tiltT = { x: (e.clientX / W - 0.5) * 2, y: (e.clientY / H - 0.5) * 2 };
  }, { passive: true });
  window.addEventListener("resize", resize);
  resize();

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
    const gap = (now - touched < 8000 ? 33 : 80) * (slow > 20 ? 1.8 : 1);
    if (now - last < gap) return;
    if (last && now - last < 400) {
      if (now - last > gap + 45) { if (++slow === 21) resize(); }
      else if (slow > 0 && slow < 20) slow--;
    }
    const dt = Math.min(4, (now - last) / 16.7);
    last = now;
    for (let k = 0; k < 3; k++) {
      for (let j = 0; j < 3; j++) {
        colC[k][j] += (colT[k][j] - colC[k][j]) * Math.min(1, 0.05 * dt);
      }
    }
    tiltC.x += (tiltT.x - tiltC.x) * 0.05 * dt;
    tiltC.y += (tiltT.y - tiltC.y) * 0.05 * dt;
    const ts = now / 1000;
    gl.uniform2f(U.r, cv.width, cv.height);
    gl.uniform1f(U.t, RM ? 20 : ts);
    gl.uniform3fv(U.c1, colC[0]);
    gl.uniform3fv(U.c2, colC[1]);
    gl.uniform3fv(U.c3, colC[2]);
    gl.uniform2f(U.tp, ripple.x, ripple.y);
    gl.uniform1f(U.tt, ts - ripple.t0);
    gl.uniform2f(U.tilt, tiltC.x, -tiltC.y);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    if (++frames > 2) dirty = false;
  }
  applyMode(modeNow());
  requestAnimationFrame(frame);

  // ------------------------------------------------------------------ 3. Siljuvchi Indikator (.zk-ind)
  const SEG_SEL = "#seg,.m-seg,.bx-seg,.sx-seg,.gx-seg,.dx-seg";
  let prevRect = null;

  function updateIndicator(btn) {
    if (!btn) {
      document.querySelectorAll(SEG_SEL).forEach(decorate);
      return;
    }
    const seg = btn.closest(SEG_SEL) || btn.parentElement;
    if (!seg) return;
    let ind = seg.querySelector(":scope>.zk-ind") || document.getElementById("zkInd");
    if (!ind) {
      ind = document.createElement("div");
      ind.className = "zk-ind";
      ind.id = "zkInd";
      seg.prepend(ind);
    }
    const sr = seg.getBoundingClientRect();
    const br = btn.getBoundingClientRect();
    const x = br.left - sr.left + seg.scrollLeft;
    const w = br.width;
    ind.style.width = `${w}px`;
    ind.style.transform = `translateX(${x}px)`;
  }

  function decorate(seg) {
    const on = seg.querySelector("button.on");
    if (!on || seg.offsetParent === null) return false;
    let ind = seg.querySelector(":scope>.zk-ind");
    const fresh = !ind;
    if (fresh) {
      ind = document.createElement("div");
      ind.className = "zk-ind";
      ind.id = "zkInd";
      ind.setAttribute("aria-hidden", "true");
      seg.prepend(ind);
    }
    const sr = seg.getBoundingClientRect();
    const br = on.getBoundingClientRect();
    const x = br.left - sr.left + seg.scrollLeft;
    const w = br.width;
    const key = `${x.toFixed(1)}:${w.toFixed(1)}`;
    if (ind.dataset.k === key) return fresh;
    ind.dataset.k = key;
    ind.style.transform = `translateX(${x}px)`;
    ind.style.width = `${w}px`;
    if (fresh && prevRect && !RM && prevRect.m !== modeNow()) {
      const fx = prevRect.left - sr.left + seg.scrollLeft;
      ind.animate([
        { transform: `translateX(${fx}px)`, width: `${prevRect.width}px` },
        { transform: `translateX(${x}px)`, width: `${w}px` }
      ], { duration: 420, easing: "cubic-bezier(.34,1.4,.64,1)" });
    }
    prevRect = { left: br.left, width: w, m: modeNow() };
    if (br.right > sr.right - 8 || br.left < sr.left + 8) {
      try { on.scrollIntoView({ inline: "center", block: "nearest", behavior: fresh ? "auto" : "smooth" }); } catch (e) {}
    }
    return fresh;
  }

  let segQueued = false;
  function scanSegs() {
    if (segQueued) return;
    segQueued = true;
    requestAnimationFrame(() => {
      segQueued = false;
      document.querySelectorAll(SEG_SEL).forEach(decorate);
      flowScan();
    });
  }

  new MutationObserver(scanSegs).observe(body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden", "class"] });
  window.addEventListener("resize", () => {
    document.querySelectorAll(".zk-ind").forEach((i) => { i.dataset.k = ""; });
    scanSegs();
  });
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(`${SEG_SEL} button`);
    if (btn) {
      haptic("hit");
      setTimeout(() => updateIndicator(btn), 20);
    }
  }, true);

  // ------------------------------------------------------------------ 4. Top 10 Coverflow 3D Karusel
  function updateFlowCenter(flow) {
    if (!flow) flow = document.getElementById("zkFlow") || document.querySelector(".row.zk-flow");
    if (!flow) return;
    const r = flow.getBoundingClientRect();
    const mid = r.left + r.width / 2;
    const cards = flow.querySelectorAll(".card");
    let closest = null, minDiff = Infinity;

    cards.forEach((c) => {
      const b = c.getBoundingClientRect();
      const center = b.left + b.width / 2;
      const diff = Math.abs(mid - center);
      if (diff < minDiff) { minDiff = diff; closest = c; }
      const d = Math.max(-1.6, Math.min(1.6, (center - mid) / (b.width * 1.15)));
      const a = Math.abs(d);
      c.style.transform = RM ? "" : `perspective(700px) rotateY(${(-d * 22).toFixed(1)}deg) scale(${(1 - Math.min(a, 1) * 0.1).toFixed(3)})`;
      c.style.zIndex = String(10 - Math.round(a * 3));
    });

    cards.forEach((c) => c.classList.toggle("zk-mid", c === closest));
  }

  function initFlow(flow) {
    if (!flow) flow = document.getElementById("zkFlow") || document.querySelector(".row.zk-flow");
    if (!flow) return;
    flow.classList.add("zk-flow");
    let scrollTimeout;
    const onScroll = () => {
      updateFlowCenter(flow);
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => updateFlowCenter(flow), 60);
    };
    flow.removeEventListener("scroll", onScroll);
    flow.addEventListener("scroll", onScroll, { passive: true });
    requestAnimationFrame(() => updateFlowCenter(flow));
  }

  function flowScan() {
    document.querySelectorAll("#main .row:not(.zk-flow)").forEach((row) => {
      if (!row.querySelector(".card")) return;
      initFlow(row);
    });
  }

  // ------------------------------------------------------------------ 5. Oltin Kubik Ruletkasi (.zk-slot & ZK_spin)
  let spinning = false;

  function spinRoulette(itemsList, onSelectCallback) {
    const items = itemsList || window.ZK_ITEMS || [];
    if (!items || !items.length) {
      if (window.toast) window.toast("Katalog yuklanmoqda…");
      return;
    }
    if (spinning) return;
    spinning = true;

    let slot = document.getElementById("zkSlot") || document.getElementById("zkslot");
    if (!slot) {
      slot = document.createElement("section");
      slot.className = "zk-slot";
      slot.id = "zkSlot";
      slot.setAttribute("aria-modal", "true");
      slot.innerHTML = `<div class="zk-slot-backdrop"></div>
        <div class="zk-slot-modal">
          <button class="zk-slot-close" id="zkSlotClose" aria-label="Yopish">✕</button>
          <div class="zk-slot-header">
            <div style="font-size:36px;margin-bottom:4px">🎲</div>
            <h2>Tasodifiy Kino</h2>
            <p>Omadingizni sinab ko'ring!</p>
          </div>
          <div class="zk-slot-window">
            <div class="zk-slot-pointer"></div>
            <div class="zk-slot-reel" id="zkSlotReel"></div>
          </div>
          <button class="zk-slot-spin-btn" id="zkSlotSpinBtn">🎲 Yana aylantirish</button>
        </div>`;
      body.appendChild(slot);
    }

    const reel = slot.querySelector("#zkSlotReel") || slot.querySelector(".zk-slot-reel") || slot.querySelector(".zk-slot-s");
    const closeBtn = slot.querySelector("#zkSlotClose") || slot.querySelector(".zk-slot-close");
    const spinBtn = slot.querySelector("#zkSlotSpinBtn") || slot.querySelector(".zk-slot-spin-btn");

    haptic("hit");
    slot.removeAttribute("hidden");
    slot.classList.add("open");
    slot.classList.add("on");

    const winnerIdx = Math.floor(Math.random() * items.length);
    const winner = items[winnerIdx];
    const N = 22;
    const stopAt = N - 4;
    let reelHTML = "";

    for (let i = 0; i < N; i++) {
      const it = (i === stopAt) ? winner : items[Math.floor(Math.random() * items.length)];
      const img = it.i ? `<img src="p/${it.c}_s.webp?v=${it.i}" alt="">` : "";
      reelHTML += `<div class="zk-slot-item" data-idx="${i}">
        ${img || `<div class="ph">${it.t || "Kino"}</div>`}
        <span class="badge">#${it.c}</span>
        ${it.p > 1 ? `<span class="parts">${it.p} qism</span>` : ""}
      </div>`;
    }

    if (reel) {
      reel.style.transition = "none";
      reel.style.transform = "translateY(0px)";
      reel.innerHTML = reelHTML;
    }

    requestAnimationFrame(() => {
      const itemHeight = 172;
      const targetY = -(stopAt * itemHeight - 20);
      let tickCount = 0;
      const tick = setInterval(() => {
        haptic("hit");
        if (++tickCount > 18) clearInterval(tick);
      }, 150);

      if (reel) {
        reel.style.transition = "transform 3.0s cubic-bezier(0.12, 0.8, 0.22, 1)";
        reel.style.transform = `translateY(${targetY}px)`;
      }

      setTimeout(() => {
        clearInterval(tick);
        haptic("ok");
        spinning = false;

        if (reel) {
          const winnerCard = reel.querySelector(`[data-idx="${stopAt}"]`);
          if (winnerCard) {
            winnerCard.style.boxShadow = "0 0 35px #F2B84B, 0 0 15px #FFF";
            winnerCard.style.border = "2px solid #F2B84B";
          }
        }

        setTimeout(() => {
          slot.classList.remove("open");
          slot.classList.remove("on");
          setTimeout(() => slot.setAttribute("hidden", ""), 250);
          if (typeof onSelectCallback === "function") {
            onSelectCallback(winner);
          } else if (typeof window.openDetail === "function") {
            window.openDetail(winner);
          }
        }, 850);
      }, 3150);
    });

    const closeHandler = () => {
      spinning = false;
      slot.classList.remove("open");
      slot.classList.remove("on");
      setTimeout(() => slot.setAttribute("hidden", ""), 250);
    };

    if (closeBtn) closeBtn.onclick = closeHandler;
    if (spinBtn) spinBtn.onclick = () => {
      if (!spinning) spinRoulette(items, onSelectCallback);
    };
  }

  // ------------------------------------------------------------------ 6. Splash Ochilish Ekrani (#zksplash)
  function initSplash() {
    const splash = document.getElementById("zksplash");
    if (!splash) return;

    const endSplash = () => {
      if (!splash.classList.contains("hide") && !splash.classList.contains("out")) {
        splash.classList.add("hide");
        splash.classList.add("out");
        ripple = { x: 0, y: 0, t0: performance.now() / 1000 };
        setTimeout(() => {
          splash.style.display = "none";
          try { splash.remove(); } catch (e) {}
        }, 550);
      }
    };

    setTimeout(endSplash, 1800);
    splash.addEventListener("click", endSplash);
    splash.addEventListener("pointerdown", endSplash);
  }

  // Global eksport
  window.ZK = {
    updateIndicator,
    updateFlowCenter,
    initFlow,
    spin: spinRoulette,
    initSplash
  };
  window.ZK_spin = (items, onSelect) => spinRoulette(items || window.ZK_ITEMS, onSelect);

  document.addEventListener("DOMContentLoaded", () => {
    initSplash();
    scanSegs();
    flowScan();
  });
})();
