/* ⭐ Kirish animatsiyasi — ES5 (eski WebView'da ham ishlaydi). Birinchi marta: Bauntys yulduzi hikoyasi
   (shodon odamcha → Telegram → Bauntys → koinot), keyin: qisqa (≈2.6 s). Har qanday xatoda — darhol ochiladi. */
(function () {
  var root = document.getElementById("zkintro");
  if (!root) return;
  window.ZK_INTRO_RUN = true;
  var done = false, timers = [], anims = [], skyGen = 0, metAt = 1e12, fullRun = false;
  var $ = function (id) { return document.getElementById(id); };
  function kill() {
    if (done) return; done = true;
    if (fullRun) { try { localStorage.setItem("zk_intro3", "1"); } catch (e) {} }
    for (var i = 0; i < timers.length; i++) clearTimeout(timers[i]);
    root.classList.add("zi-fade");
    setTimeout(function () { if (root.parentNode) root.parentNode.removeChild(root); }, 520);
    try { document.dispatchEvent(new Event("zk:intro-done")); } catch (e) {}
  }
  try {
    var q = ""; try { q = location.search; } catch (e) {}
    if (/nosplash/.test(q)) { root.parentNode.removeChild(root); return; }
    var RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var LITE = !!window.ZK_LITE, WEAK = !!window.ZK_WEAK || LITE;
    if (RM || LITE) { kill(); return; }
    var lang = "uz";
    try { lang = localStorage.getItem("zk_lang") || ""; } catch (e) {}
    if (!lang) { try { lang = (Telegram.WebApp.initDataUnsafe.user.language_code || "").slice(0, 2); } catch (e) {} }
    lang = lang === "ru" || lang === "en" ? lang : "uz";
    var T3 = function (u, r, e) { return lang === "ru" ? r : lang === "en" ? e : u; };
    var CAPS = [
      [T3("Bu — <i>Bauntys</i> yulduzi", "Это — звезда <i>Bauntys</i>", "This is the <i>Bauntys</i> star"),
       T3("Oddiy yulduz emas: ichida 3 ta ma'no yashiringan", "Не простая звезда: внутри спрятаны 3 смысла", "Not just a star: it hides 3 meanings")],
      ['<i style="color:#8fe600">' + T3("Shodon odamcha", "Счастливый человечек", "A happy person") + "</i>",
       T3("Yulduz — qo'llarini ko'tarib raqsga tushayotgan xursand inson. Bu — siz!", "Звезда — радостный человек, танцующий с поднятыми руками. Это — вы!", "The star is a joyful person dancing with raised arms. That's you!")],
      ['<i style="color:#2aa3ef">Telegram</i> ' + T3("belgisi", "— символ", "sign"),
       T3("Yulduz ichida — uchayotgan qog'oz samolyotcha. Hammasi @BauntyCinemabot ichida", "Внутри звезды — бумажный самолётик. Всё — внутри @BauntyCinemabot", "Inside the star is a paper plane. Everything lives inside @BauntyCinemabot")],
      ['<i style="color:#ffa50f">Bauntys</i> — ' + T3("koinot olami", "космическая вселенная", "space universe"),
       T3("Kinolar, jonli TV, Bunker, musiqa va o'yinlar — barchasi bitta yulduz ostida", "Кино, живое ТВ, Бункер, музыка и игры — всё под одной звездой", "Movies, live TV, Bunker, music and games — all under one star")]
    ];
    var capEl = $("zi-cap");
    if (capEl && capEl.children && capEl.children.length >= 4) {
      for (var c = 0; c < 4; c++) capEl.children[c].innerHTML = "<b>" + CAPS[c][0] + "</b><small>" + CAPS[c][1] + "</small>";
    }
    var skipEl = $("zi-skip");
    if (skipEl) {
      skipEl.textContent = T3("O'tkazib yuborish ›", "Пропустить ›", "Skip ›");
      skipEl.onclick = function (e) { if (e && e.stopPropagation) e.stopPropagation(); kill(); };
    }
    var st = $("zi-st") ? $("zi-st").getBoundingClientRect() : {bottom: 260};
    if ($("zi-end")) $("zi-end").style.top = Math.round(st.bottom + 30) + "px";

    var seen = false; try { seen = localStorage.getItem("zk_intro3") === "1"; } catch (e) {}
    var full = !seen;
    try { if (/introfull/.test(q) || localStorage.getItem("zk_intro_again") === "1") { full = true; localStorage.removeItem("zk_intro_again"); } } catch (e) {}
    fullRun = full;
    if (!full) root.className += " zi-short";
    timers.push(setTimeout(kill, full ? 25000 : 6000));

    var COLS = ["#ffa50f", "#8fe600", "#b000ff", "#127fff", "#ff5a00", "#ff00b4", "#00e5ff", "#00fb76", "#f00000"];
    var DPR = WEAK ? 1 : Math.min(2, window.devicePixelRatio || 1);

    function bez(x1, y1, x2, y2) {
      return function (t) {
        if (t <= 0 || t >= 1) return t;
        var lo = 0, hi = 1, m, x;
        for (var i = 0; i < 18; i++) {
          m = (lo + hi) / 2;
          x = 3 * (1 - m) * (1 - m) * m * x1 + 3 * (1 - m) * m * m * x2 + m * m * m;
          if (x < t) lo = m; else hi = m;
        }
        m = (lo + hi) / 2;
        return 3 * (1 - m) * (1 - m) * m * y1 + 3 * (1 - m) * m * m * y2 + m * m * m;
      };
    }
    function ease(e) {
      if (!e || e === "linear") return function (t) { return t; };
      if (e === "ease-in") return bez(.42, 0, 1, 1);
      if (e === "ease-out") return bez(0, 0, .58, 1);
      if (e === "ease-in-out") return bez(.42, 0, .58, 1);
      var m = /cubic-bezier\(([^)]+)\)/.exec(e);
      if (m) { var v = m[1].split(","); return bez(+v[0], +v[1], +v[2], +v[3]); }
      return bez(.25, .1, .25, 1);
    }
    function ptf(str) {
      var o = {x: 0, y: 0, r: 0, sx: 1, sy: 1};
      if (!str || str === "none") return o;
      var re = /(\w+)\(([^)]*)\)/g, m;
      while ((m = re.exec(str))) {
        var a = m[2].split(/[,\s]+/).filter(function (q2) { return q2 !== ""; }).map(parseFloat), f = m[1];
        if (f === "translate") { o.x += a[0] || 0; o.y += a[1] || 0; }
        else if (f === "translateX") o.x += a[0];
        else if (f === "translateY") o.y += a[0];
        else if (f === "rotate") o.r += a[0];
        else if (f === "scale") { o.sx *= a[0]; o.sy *= (a.length > 1 ? a[1] : a[0]); }
        else if (f === "scaleX") o.sx *= a[0];
        else if (f === "scaleY") o.sy *= a[0];
      }
      return o;
    }
    var running = [], loopOn = false;
    function setP(el, k, v) {
      if (k === "transform") {
        var t = "translate(" + v.x.toFixed(2) + "px," + v.y.toFixed(2) + "px) rotate(" + v.r.toFixed(2) + "deg) scale(" + v.sx.toFixed(4) + "," + v.sy.toFixed(4) + ")";
        el.style.transform = t; el.style.webkitTransform = t;
      } else if (k === "opacity") {
        el.style.opacity = v;
        if (el.getAttribute && el.getAttribute("opacity") !== null) el.removeAttribute("opacity");
      } else if (k === "strokeDashoffset") {
        el.style.strokeDashoffset = v;
      } else if (k === "letterSpacing") {
        el.style.letterSpacing = v + "em";
        el.style.paddingLeft = v + "em";
      }
    }
    function val(k, x) { if (k === "transform") return ptf(x); return parseFloat(x); }
    function lerp(k, a, b, t) {
      if (k === "transform") return {x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, r: a.r + (b.r - a.r) * t, sx: a.sx + (b.sx - a.sx) * t, sy: a.sy + (b.sy - a.sy) * t};
      return a + (b - a) * t;
    }
    function tick() {
      var now = Date.now(), alive = [];
      for (var i = 0; i < running.length; i++) {
        var a = running[i], e = (now - a.t0) / a.dur;
        if (e < 0) { if (a.fill === "both") a.apply(0); alive.push(a); continue; }
        if (e >= 1) { a.apply(1); if (a.onfinish) { try { a.onfinish(); } catch (er) {} } continue; }
        a.apply(e); alive.push(a);
      }
      running = alive;
      if (running.length && !done) requestAnimationFrame(tick); else loopOn = false;
    }
    function A(el, kf, o) {
      if (!el) return null;
      var props = {}, n = kf.length, i, k;
      for (i = 0; i < n; i++) {
        var off = kf[i].offset != null ? kf[i].offset : (n > 1 ? i / (n - 1) : 1);
        for (k in kf[i]) if (k !== "offset") (props[k] = props[k] || []).push({o: off, v: val(k, kf[i][k])});
      }
      for (k in props) {
        var L = props[k];
        if (L[0].o > 0) L.unshift({o: 0, v: L[0].v});
        if (L[L.length - 1].o < 1) L.push({o: 1, v: L[L.length - 1].v});
      }
      var ez = ease(o.easing || "cubic-bezier(.22,1,.36,1)");
      var a = {
        t0: Date.now() + (o.delay || 0), dur: Math.max(1, o.duration || 1), fill: o.fill || "both", onfinish: null,
        apply: function (e) {
          var t = ez(e);
          for (var key in props) {
            var P = props[key], j = 0;
            while (j < P.length - 2 && t > P[j + 1].o) j++;
            var A0 = P[j], B0 = P[j + 1], span = B0.o - A0.o || 1;
            setP(el, key, lerp(key, A0.v, B0.v, Math.max(0, Math.min(1, (t - A0.o) / span))));
          }
        }
      };
      if (a.fill === "none") {
        var oa = a.apply, oldT = el.style.transform;
        a.apply = function (e) { oa(e); if (e >= 1) { el.style.transform = oldT; el.style.webkitTransform = oldT; } };
      }
      if (a.fill === "both" && !(o.delay > 0)) a.apply(0);
      running.push(a); anims.push(a);
      if (!loopOn) { loopOn = true; requestAnimationFrame(tick); }
      return a;
    }
    function at(ms, fn) { timers.push(setTimeout(function () { if (!done) fn(); }, ms)); }
    function dot(n) { var d = $("zi-dots") ? $("zi-dots").children : []; for (var i = 0; i < d.length; i++) d[i].className = i === n ? "on" : ""; }
    function capShow(n, t0, len) {
      if (!capEl || !capEl.children[n]) return;
      var el = capEl.children[n]; at(t0, function () { dot(n); });
      A(el, [{opacity: 0, transform: "translateY(14px)"}, {opacity: 1, transform: "none"}], {duration: 600, delay: t0});
      A(el, [{opacity: 1, transform: "none"}, {opacity: 0, transform: "translateY(-10px)"}], {duration: 450, delay: t0 + len - 450, fill: "forwards", easing: "ease-in"});
    }

    var ROCK = new Image(); ROCK.src = "rock.webp";
    function glare() {
      var s = document.createElement("canvas"), z = 64, h = 32; s.width = s.height = z; var x = s.getContext("2d");
      var g = x.createRadialGradient(h, h, 0, h, h, h); g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(.12, "rgba(255,255,255,.75)");
      g.addColorStop(.35, "rgba(200,220,255,.15)"); g.addColorStop(1, "rgba(0,0,0,0)"); x.fillStyle = g; x.fillRect(0, 0, z, z);
      x.globalCompositeOperation = "lighter";
      var l = x.createLinearGradient(0, h, z, h); l.addColorStop(0, "rgba(255,255,255,0)"); l.addColorStop(.5, "rgba(255,255,255,.9)"); l.addColorStop(1, "rgba(255,255,255,0)");
      x.fillStyle = l; x.fillRect(0, h - .6, z, 1.2);
      l = x.createLinearGradient(h, 0, h, z); l.addColorStop(0, "rgba(255,255,255,0)"); l.addColorStop(.5, "rgba(255,255,255,.9)"); l.addColorStop(1, "rgba(255,255,255,0)");
      x.fillStyle = l; x.fillRect(h - .6, 0, 1.2, z);
      return s;
    }
    function nebula(W, H) {
      var s = document.createElement("canvas"); s.width = W; s.height = H;
      var x = s.getContext("2d"), N = [["rgba(110,60,200,.32)", .25, .2, .55], ["rgba(30,90,200,.28)", .8, .35, .5], ["rgba(200,50,140,.18)", .6, .75, .45], ["rgba(20,160,170,.16)", .15, .7, .4]];
      for (var i = 0; i < N.length; i++) {
        var n = N[i], g = x.createRadialGradient(W * n[1], H * n[2], 0, W * n[1], H * n[2], Math.max(W, H) * n[3]);
        g.addColorStop(0, n[0]); g.addColorStop(1, "rgba(0,0,0,0)"); x.fillStyle = g; x.fillRect(0, 0, W, H);
      }
      var k = WEAK ? 600 : 1400;
      for (i = 0; i < k; i++) {
        var u = Math.random(), v = (Math.random() + Math.random() + Math.random() - 1.5) * .16;
        x.fillStyle = "rgba(255,255,255," + (Math.random() * .5).toFixed(2) + ")";
        x.fillRect(W * (1.1 - u * 1.2) + v * W * .6, H * u + v * H * .3, (Math.random() < .9 ? 1 : 1.6) * DPR, DPR);
      }
      return s;
    }
    function sky() {
      var gen = ++skyGen, cv = $("zi-sky");
      if (!cv) return;
      var ctx = cv.getContext("2d"), W = cv.width = Math.round(innerWidth * DPR), H = cv.height = Math.round(innerHeight * DPR), t0 = Date.now();
      var neb = nebula(W, H), gl = glare(), sts = [], big = [], mt = [], em = [], SC = ["#ffffff", "#cfe0ff", "#a9c8ff", "#fff1d6", "#ffd9b0", "#ffc7a8"], i;
      var NS = WEAK ? 140 : 320, NB = WEAK ? 10 : 22, NR = WEAK ? 6 : 10, NSH = WEAK ? 6 : 14, EMX = WEAK ? 90 : 260;
      for (i = 0; i < NS; i++) sts.push({v: (.15 + Math.random() * .55) * DPR, x: Math.random() * W, y: Math.random() * H, r: (Math.random() < .85 ? Math.random() * 1.1 + .4 : Math.random() * 1.8 + 1.2) * DPR, c: SC[Math.random() * SC.length | 0], p: Math.random() * 6.3, s: .5 + Math.random() * 2.5});
      for (i = 0; i < NB; i++) big.push({v: (.3 + Math.random() * .4) * DPR, x: Math.random() * W, y: Math.random() * H, z: (10 + Math.random() * 26) * DPR, p: Math.random() * 6.3, s: .6 + Math.random() * 1.6});
      var SZ = [130, 60, 90, 45, 150, 70, 100, 55, 120, 80], k2 = Math.min(1, innerWidth / 390) * DPR;
      for (i = 0; i < NR; i++) {
        var sz = SZ[i] * (.8 + Math.random() * .4) * k2, a = Math.PI * (.62 + Math.random() * .12), v = (2.6 + Math.random() * 2.4 + (140 - SZ[i]) / 60) * DPR;
        mt.push({t: i * 400 + Math.random() * 200, rock: 1, sz: sz, x: W * (.3 + Math.random()) + sz, y: -sz - Math.random() * H * .35, vx: Math.cos(a) * v, vy: Math.sin(a) * v, rot: Math.random() * 6.3, vr: (Math.random() - .5) * .03});
      }
      for (i = 0; i < NSH; i++) {
        a = Math.PI * (.6 + Math.random() * .15); v = (11 + Math.random() * 7) * DPR;
        mt.push({t: i * 320 + Math.random() * 250, x: W * (.2 + Math.random() * 1.1), y: -20 - Math.random() * H * .4, vx: Math.cos(a) * v, vy: Math.sin(a) * v, len: (120 + Math.random() * 160) * DPR});
      }
      function f() {
        if (gen !== skyGen || done) return;
        var now = Date.now(), el = now - t0, fade = Math.min(1, el / 900), j, o;
        ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1; ctx.clearRect(0, 0, W, H);
        ctx.globalAlpha = fade; ctx.drawImage(neb, 0, 0);
        for (j = 0; j < sts.length; j++) {
          o = sts[j]; o.y += o.v; o.x -= o.v * .35;
          if (o.y > H + 4) { o.y = -4; o.x = Math.random() * W * 1.2; }
          ctx.globalAlpha = fade * (.3 + .7 * Math.abs(Math.sin(o.p + el / 1000 * o.s)));
          ctx.fillStyle = o.c; ctx.beginPath(); ctx.arc(o.x, o.y, o.r, 0, 7); ctx.fill();
        }
        ctx.globalCompositeOperation = "lighter";
        for (j = 0; j < big.length; j++) {
          o = big[j]; o.y += o.v; o.x -= o.v * .35;
          if (o.y > H + 20) { o.y = -20; o.x = Math.random() * W * 1.2; }
          ctx.globalAlpha = fade * (.55 + .45 * Math.sin(o.p + el / 1000 * o.s));
          ctx.drawImage(gl, o.x - o.z / 2, o.y - o.z / 2, o.z, o.z);
        }
        var mel = now - metAt;
        for (j = 0; j < mt.length; j++) {
          o = mt[j]; if (mel < o.t) continue;
          var tt = (mel - o.t) / 16, x = o.x + o.vx * tt, y = o.y + o.vy * tt, n = Math.sqrt(o.vx * o.vx + o.vy * o.vy), ux = o.vx / n, uy = o.vy / n;
          if (o.rock) {
            if (y > H + o.sz * 2 || x < -o.sz * 3) continue;
            var L = o.sz * 3.2, R = o.sz * .42, px = -uy, py = ux, fl = 1 + .12 * Math.sin(el / 40 + j);
            var LY = [[1, 1, "rgba(255,70,0,.5)", "rgba(120,20,0,0)"], [.7, .75, "rgba(255,170,40,.7)", "rgba(255,90,0,0)"], [.38, .45, "rgba(255,250,210,.95)", "rgba(255,200,90,0)"]];
            for (var l2 = 0; l2 < 3; l2++) {
              var ly = LY[l2], w = R * ly[0] * fl, len = L * ly[1] * fl, tx = x - ux * len, ty = y - uy * len, g = ctx.createLinearGradient(x, y, tx, ty);
              g.addColorStop(0, ly[2]); g.addColorStop(1, ly[3]); ctx.globalAlpha = fade; ctx.fillStyle = g;
              ctx.beginPath(); ctx.moveTo(x + px * w, y + py * w);
              ctx.quadraticCurveTo(x - ux * len * .45 + px * w * .55, y - uy * len * .45 + py * w * .55, tx, ty);
              ctx.quadraticCurveTo(x - ux * len * .45 - px * w * .55, y - uy * len * .45 - py * w * .55, x - px * w, y - py * w);
              ctx.arc(x, y, w, Math.atan2(-py, -px), Math.atan2(py, px), false); ctx.fill();
            }
            var hg = ctx.createRadialGradient(x, y, 0, x, y, o.sz * 1.1); hg.addColorStop(0, "rgba(255,170,60,.55)"); hg.addColorStop(1, "rgba(255,80,0,0)");
            ctx.fillStyle = hg; ctx.beginPath(); ctx.arc(x, y, o.sz * 1.1, 0, 7); ctx.fill();
            if (em.length < EMX) for (var e2 = 0; e2 < 2; e2++) em.push({x: x - ux * R + (Math.random() - .5) * R, y: y - uy * R + (Math.random() - .5) * R, vx: o.vx * .15 + (Math.random() - .5) * 1.2 * DPR, vy: o.vy * .15 + (Math.random() - .5) * 1.2 * DPR, l: 1, r: (1 + Math.random() * 2.2 * (o.sz / 90 / DPR)) * DPR});
            ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = fade; ctx.save(); ctx.translate(x, y); ctx.rotate(o.rot + o.vr * tt);
            if (ROCK.complete && ROCK.naturalWidth) ctx.drawImage(ROCK, -o.sz / 2, -o.sz * .56, o.sz, o.sz * 1.12);
            ctx.restore(); ctx.globalCompositeOperation = "lighter";
          } else {
            if (y > H + 300) continue;
            var ex = x - ux * o.len, ey = y - uy * o.len, g2 = ctx.createLinearGradient(x, y, ex, ey);
            g2.addColorStop(0, "rgba(255,255,255,.95)"); g2.addColorStop(.2, "rgba(180,210,255,.5)"); g2.addColorStop(1, "rgba(120,160,255,0)");
            ctx.globalAlpha = fade; ctx.strokeStyle = g2; ctx.lineWidth = 1.6 * DPR; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(ex, ey); ctx.stroke();
            ctx.drawImage(gl, x - 7 * DPR, y - 7 * DPR, 14 * DPR, 14 * DPR);
          }
        }
        for (j = em.length - 1; j >= 0; j--) {
          o = em[j]; o.x += o.vx; o.y += o.vy; o.l -= .025;
          if (o.l <= 0) { em.splice(j, 1); continue; }
          ctx.globalAlpha = fade * o.l; ctx.fillStyle = o.l > .6 ? "#ffe08a" : "#ff6a1a";
          ctx.beginPath(); ctx.arc(o.x, o.y, o.r * o.l, 0, 7); ctx.fill();
        }
        ctx.globalCompositeOperation = "source-over";
        requestAnimationFrame(f);
      }
      requestAnimationFrame(f);
    }
    function burst() {
      var cv = $("zi-fx"); if (!cv || !$("zi-st")) return;
      var ctx = cv.getContext("2d"), W = cv.width = Math.round(innerWidth * DPR), H = cv.height = Math.round(innerHeight * DPR);
      var r = $("zi-st").getBoundingClientRect(), cx = (r.left + r.width / 2) * DPR, cy = (r.top + r.height / 2) * DPR, ps = [], n = WEAK ? 30 : 60;
      for (var k = 0; k < n; k++) {
        var a = Math.random() * Math.PI * 2, v = (2 + Math.random() * 6) * DPR;
        ps.push({x: cx, y: cy, vx: Math.cos(a) * v, vy: Math.sin(a) * v, r: (1.5 + Math.random() * 2.5) * DPR, c: COLS[k % COLS.length], l: 1, d: .01 + Math.random() * .012});
      }
      (function f() {
        if (done) return; ctx.clearRect(0, 0, W, H); var m = 0;
        for (var i = 0; i < ps.length; i++) {
          var p = ps[i]; if (p.l <= 0) continue; m++;
          p.x += p.vx; p.y += p.vy; p.vx *= .96; p.vy = p.vy * .96 + .05 * DPR; p.l -= p.d;
          ctx.globalAlpha = p.l > 0 ? p.l : 0; ctx.fillStyle = p.c; ctx.fillRect(p.x, p.y, p.r, p.r);
        }
        if (m) requestAnimationFrame(f); else ctx.clearRect(0, 0, W, H);
      })();
    }
    var SPT = [[55.2, 0], [45.2, 22.4], [66.2, 34], [67.4, 35.1], [0, 23.3], [27.3, 49.9], [56.9, 51.6], [25.4, 63.6], [4.4, 113.1], [55, 79.7], [99.8, 102.5], [83.1, 63.6], [70.6, 63.2], [100, 40.2], [73.2, 35.7]];
    function dance(dur) {
      var man = $("zi-man"), head = $("zi-head"), notes = $("zi-notes"), t0 = Date.now(), nt = 0, NS = ["♪", "♫", "♬", "❤"];
      if (!man || !head || !notes) return;
      (function f() {
        var now = Date.now(), e = (now - t0) / dur; if (e > 1 || done) return;
        var b = e * Math.PI * 7, j = Math.abs(Math.sin(b)), sq = 1 - .08 * j, p = [], i;
        for (i = 0; i < SPT.length; i++) p.push([SPT[i][0], SPT[i][1]]);
        var la = -14 - 12 * Math.sin(b), ra = -14 - 12 * Math.sin(b + Math.PI);
        p[4][0] -= 4; p[4][1] += la; p[13][0] += 4; p[13][1] += ra; p[5][1] += la * .25; p[14][1] += ra * .2;
        var lk = 8 * Math.sin(b * .5), rk = 8 * Math.sin(b * .5 + Math.PI);
        p[8][0] += lk; p[8][1] -= Math.max(0, lk); p[10][0] += rk; p[10][1] -= Math.max(0, rk);
        var sw = 7 * Math.sin(b * .5), up = -16 * j, d = "M";
        for (i = 0; i < p.length; i++) {
          var k = 1 - p[i][1] / 113;
          p[i][0] += sw * k; p[i][1] = p[i][1] * sq + up * (1 - p[i][1] / 160);
          d += (i ? " L" : "") + p[i][0].toFixed(1) + " " + p[i][1].toFixed(1);
        }
        man.setAttribute("d", d + "Z");
        head.setAttribute("transform", "translate(" + (p[0][0] + 1).toFixed(1) + " " + (p[0][1] + 15).toFixed(1) + ") rotate(" + (sw * 2).toFixed(1) + ")");
        if ($("zi-shd")) $("zi-shd").setAttribute("rx", (38 - 14 * j).toFixed(1));
        if (now - nt > 380) {
          nt = now;
          var n = document.createElementNS("http://www.w3.org/2000/svg", "text");
          n.textContent = NS[Math.random() * 4 | 0];
          n.setAttribute("x", (Math.random() < .5 ? -6 : 92) + Math.random() * 14);
          n.setAttribute("y", 40 + Math.random() * 40);
          notes.appendChild(n);
          var an = A(n, [{opacity: 0, transform: "translateY(0) scale(.6)"}, {opacity: 1, offset: .2}, {opacity: 0, transform: "translateY(-46px) scale(1.2)"}], {duration: 1400, easing: "ease-out"});
          if (an) (function (node) { an.onfinish = function () { if (node.parentNode) node.parentNode.removeChild(node); }; })(n);
        }
        requestAnimationFrame(f);
      })();
    }

    sky();
    A($("zi-ol"), [{strokeDashoffset: 100}, {strokeDashoffset: 0}], {duration: full ? 1600 : 800, delay: 150, easing: "cubic-bezier(.65,0,.35,1)"});
    A($("zi-st"), [{transform: "scale(.85) rotate(-12deg)", opacity: 0}, {transform: "none", opacity: 1}], {duration: 1100});
    var T = 1100;
    if (full) {
      capShow(0, 650, 2500); T = 3150;
      A($("zi-ol"), [{opacity: 1}, {opacity: 0}], {duration: 400, delay: T + 100, fill: "forwards"});
      A($("zi-mg"), [{opacity: 0, transform: "scale(.6)"}, {opacity: 1, transform: "none"}], {duration: 600, delay: T + 150, easing: "cubic-bezier(.3,1.6,.5,1)"});
      at(T + 150, function () { dance(3400); });
      A($("zi-mg"), [{opacity: 1}, {opacity: 0}], {duration: 450, delay: T + 3700, fill: "forwards"});
      A($("zi-ol"), [{opacity: 0}, {opacity: 1}], {duration: 450, delay: T + 3700, fill: "forwards"});
      capShow(1, T, 4200); T += 4200;
      A($("zi-pl"), [{opacity: 0, transform: "scale(.9)"}, {opacity: 1, transform: "none"}], {duration: 700, delay: T + 150});
      A($("zi-fly"), [{opacity: 0, transform: "translate(-60px,30px) scale(1.6)"}, {opacity: 1, offset: .2}, {opacity: 1, offset: .8}, {opacity: 0, transform: "translate(150px,-20px) scale(1.6)"}], {duration: 1800, delay: T + 500, easing: "ease-in-out"});
      capShow(2, T, 3100); T += 3100;
      A($("zi-zb"), [{opacity: 0, transform: "translate(30px,40px) rotate(40deg) scale(.4)"}, {opacity: 1, transform: "none"}], {duration: 1000, delay: T + 200, easing: "cubic-bezier(.3,1.4,.5,1)"});
      A($("zi-pl"), [{opacity: 1}, {opacity: 0}], {duration: 500, delay: T + 1300, fill: "forwards"});
      A($("zi-zb"), [{opacity: 1}, {opacity: 0}], {duration: 500, delay: T + 1300, fill: "forwards"});
      A($("zi-zz"), [{opacity: 0}, {opacity: 1, transform: "scale(1.08)", offset: .6}, {opacity: 1, transform: "none"}], {duration: 700, delay: T + 1200, easing: "ease-out"});
      A($("zi-zz"), [{opacity: 1}, {opacity: 0}], {duration: 450, delay: T + 3200, fill: "forwards"});
      capShow(3, T, 3600); T += 3600;
      at(T, function () { dot(-1); });
      A($("zi-dots"), [{opacity: 1}, {opacity: 0}], {duration: 400, delay: T, fill: "forwards"});
    }
    A($("zi-sf"), [{opacity: 0}, {opacity: 1}], {duration: 500, delay: T, easing: "ease-out"});
    A($("zi-ol"), [{opacity: 1}, {opacity: 0}], {duration: 500, delay: T + 300, fill: "forwards"});
    A($("zi-st"), [{transform: "scale(1)"}, {transform: "scale(1.12)", offset: .35}, {transform: "scale(1)"}], {duration: 800, delay: T, easing: "cubic-bezier(.3,1.5,.5,1)", fill: "none"});
    at(T + 150, burst);
    if (full) at(T - 600, function () { metAt = Date.now(); });
    A($("zi-w"), [{opacity: 0, transform: "translateY(14px)"}, {opacity: 1, transform: "none"}], {duration: 800, delay: T + 450});
    A($("zi-b"), [{opacity: 0, letterSpacing: ".8em"}, {opacity: 1, letterSpacing: ".22em"}], {duration: 850, delay: T + 800});
    at(T + (full ? 4200 : 1800), kill);
  } catch (err) {
    kill();
  }
})();
