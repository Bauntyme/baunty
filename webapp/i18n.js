/* 🌐 Mini App tili: uz (asl), ru, en.
   Til: localStorage «zk_lang» → Telegram language_code → uz. Server (/api/sub → lang) bilan moslanadi.
   Tarjima: i18n_ru.js / i18n_en.js lug'ati (aniq matn → tarjima) + qoidalar (regex). Ilova o'zbekcha chizadi,
   MutationObserver har yangi matn tugunini, placeholder/title'ni va Telegram oynalarini lug'at bo'yicha almashtiradi.
   Kodda to'g'ridan-to'g'ri: ZK_T("o'zbekcha", "русский", "english"). */
(function () {
  "use strict";
  var LANGS = {uz: 1, ru: 1, en: 1};
  var lang = "";
  try { lang = localStorage.getItem("zk_lang") || ""; } catch (e) {}
  try { var q = new URLSearchParams(location.search).get("lang"); if (q && LANGS[q]) lang = q; } catch (e) {}
  if (!LANGS[lang]) {
    var c = "";
    try { c = (window.Telegram.WebApp.initDataUnsafe.user.language_code || "").slice(0, 2).toLowerCase(); } catch (e) {}
    lang = /^(ru|uk|be|kk|ky|tg)$/.test(c) ? "ru" : c === "en" ? "en" : "uz";
  }
  window.ZK_LANG = lang;
  document.documentElement.lang = lang;
  window.ZK_T = function (uz, ru, en) {
    if (lang === "ru" && ru != null) return ru;
    if (lang === "en" && en != null) return en;
    return uz;
  };
  window.ZK_LANG_NAMES = {uz: "🇺🇿 O'zbekcha", ru: "🇷🇺 Русский", en: "🇬🇧 English"};

  window.ZK_setLang = function (l, noReload) {
    if (!LANGS[l]) return;
    try { localStorage.setItem("zk_lang", l); } catch (e) {}
    var done = function () { if (!noReload && l !== lang) location.reload(); };
    var init = "";
    try { init = window.Telegram.WebApp.initData || ""; } catch (e) {}
    if (!init) { done(); return; }
    try {
      fetch("api/lang", {method: "POST", headers: {"Content-Type": "application/json", "X-Init-Data": init},
        body: JSON.stringify({lang: l})}).then(done, done);
    } catch (e) { done(); }
  };

  if (lang === "uz") { window.ZK_tr = function (s) { return s; }; return; }

  var D = {}, R = [], ready = false;
  function tr(s) {
    if (!s || s.length > 400) return null;
    var t = s.trim();
    if (!t) return null;
    var v = D[t];
    if (v == null) {
      if (!/[A-Za-zʻʼ']{2}/.test(t)) return null;
      for (var i = 0; i < R.length; i++) {
        if (R[i][0].test(t)) { v = t.replace(R[i][0], R[i][1]); break; }
      }
      if (v == null) return null;
    }
    return t === s ? v : s.replace(t, function () { return v; });
  }
  window.ZK_tr = function (s) { var v = ready ? tr(String(s)) : null; return v == null ? s : v; };

  var ATTRS = ["placeholder", "title", "aria-label", "data-ph"];
  function walk(n) {
    if (n.nodeType === 3) {
      var v = tr(n.nodeValue);
      if (v != null && v !== n.nodeValue) n.nodeValue = v;
      return;
    }
    if (n.nodeType !== 1) return;
    var tg = n.tagName;
    if (tg === "SCRIPT" || tg === "STYLE" || tg === "TEXTAREA" || tg === "svg" || n.isContentEditable) return;
    if (n.hasAttribute && n.hasAttribute("data-notr")) return;
    for (var a = 0; a < ATTRS.length; a++) {
      var av = n.getAttribute(ATTRS[a]);
      if (av) { var w = tr(av); if (w != null && w !== av) n.setAttribute(ATTRS[a], w); }
    }
    if (tg === "INPUT" && (n.type === "button" || n.type === "submit") && n.value) {
      var iv = tr(n.value); if (iv != null) n.value = iv;
    }
    for (var ch = n.firstChild; ch; ch = ch.nextSibling) walk(ch);
  }

  function hookTelegram() {
    var W;
    try { W = window.Telegram.WebApp; } catch (e) { return; }
    if (!W) return;
    var wrap = function (name, fix) {
      var f = W[name];
      if (typeof f !== "function") return;
      W[name] = function () { var a = Array.prototype.slice.call(arguments); fix(a); return f.apply(W, a); };
    };
    var T = window.ZK_tr;
    wrap("showAlert", function (a) { a[0] = T(a[0]); });
    wrap("showConfirm", function (a) { a[0] = T(a[0]); });
    wrap("showPopup", function (a) {
      var p = a[0];
      if (p && typeof p === "object") {
        p = Object.assign({}, p);
        if (p.title) p.title = T(p.title);
        if (p.message) p.message = T(p.message);
        if (p.buttons) p.buttons = p.buttons.map(function (b) { return b && b.text ? Object.assign({}, b, {text: T(b.text)}) : b; });
        a[0] = p;
      }
    });
    var MB = W.MainButton;
    if (MB && typeof MB.setText === "function") {
      var st = MB.setText;
      MB.setText = function (t) { return st.call(MB, T(t)); };
      if (typeof MB.setParams === "function") {
        var sp = MB.setParams;
        MB.setParams = function (p) { if (p && p.text) p = Object.assign({}, p, {text: T(p.text)}); return sp.call(MB, p); };
      }
    }
  }
  var oa = window.alert, oc = window.confirm;
  window.alert = function (m) { return oa.call(window, window.ZK_tr(m)); };
  window.confirm = function (m) { return oc.call(window, window.ZK_tr(m)); };

  window.ZK_DICT_LOAD = function (dict, rules) {
    D = dict || {};
    R = (rules || []).map(function (r) { return [new RegExp(r[0]), r[1]]; });
    ready = true;
    hookTelegram();
    walk(document.documentElement);
    try {
      new MutationObserver(function (ms) {
        for (var i = 0; i < ms.length; i++) {
          var m = ms[i];
          if (m.type === "characterData") { walk(m.target); continue; }
          if (m.type === "attributes") { if (m.target.nodeType === 1) { var av = m.target.getAttribute(m.attributeName); var w = tr(av); if (w != null && w !== av) m.target.setAttribute(m.attributeName, w); } continue; }
          for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]);
        }
      }).observe(document.documentElement, {childList: true, subtree: true, characterData: true,
        attributes: true, attributeFilter: ATTRS});
    } catch (e) {}
    try { document.title = window.ZK_tr(document.title); } catch (e) {}
  };
})();
