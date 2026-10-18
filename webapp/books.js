/* 📚 Baunty Kutubxonasi — Mini App Books Module (window.ZBooks) */
(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  const inTg = !!(tg && tg.initData);
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));

  const haptic = (type = "light") => {
    try {
      if (!tg || !tg.HapticFeedback) return;
      if (type === "ok") tg.HapticFeedback.notificationOccurred("success");
      else if (type === "err") tg.HapticFeedback.notificationOccurred("error");
      else if (type === "hit") tg.HapticFeedback.impactOccurred("medium");
      else tg.HapticFeedback.selectionChanged();
    } catch (e) {}
  };

  const toast = (text, ms = 2200) => {
    let el = $("toast");
    if (!el) return;
    el.textContent = text;
    el.classList.add("on");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.remove("on"), ms);
  };

  const lsGet = (key, def) => {
    try { return JSON.parse(localStorage.getItem(key) || "null") ?? def; }
    catch (e) { return def; }
  };
  const lsSet = (key, val) => {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {}
  };

  let botName = "Bauntyfilmsbot";
  let activeCategory = "all";
  let searchQuery = "";
  let booksList = [];
  let booksById = new Map();
  let currentBook = null;
  let isReaderOpen = false;
  let isDetailOpen = false;
  let readerFontSize = 16;
  let readerTheme = "dark"; // dark, sepia, white
  let savedFavorites = lsGet("baunty_bk_favs", []);

  // ---------- Ma'lumotlarni yuklash ----------
  async function fetchBooks() {
    try {
      const res = await fetch("api/books", { cache: "no-store" });
      const data = await res.json();
      booksList = data.items || [];
      booksById.clear();
      booksList.forEach((b) => booksById.set(String(b.id), b));
      return booksList;
    } catch (e) {
      console.warn("Kitoblarni yuklab bo'lmadi:", e);
      return [];
    }
  }

  // ---------- DOM yaratish ----------
  function renderView() {
    const main = $("main");
    if (!main) return;

    // Chips paneli
    const chips = [
      { id: "all", label: "📚 Barchasi" },
      { id: "pop", label: "🔥 Ommabop" },
      { id: "badiiy", label: "📖 Badiiy" },
      { id: "biznes", label: "💼 Biznes" },
      { id: "psixologiya", label: "🧠 Psixologiya" },
      { id: "diniy", label: "🕌 Diniy" },
      { id: "tarix", label: "📜 Tarix" },
      { id: "bolalar", label: "🧸 Bolalar" },
      { id: "fav", label: "⭐ Saqlanganlar" },
    ];

    let chipsHtml = chips.map((c) =>
      `<button class="bk-chip${activeCategory === c.id ? " on" : ""}" data-c="${c.id}">${c.label}</button>`
    ).join("");

    main.innerHTML = `
      <div class="bk-view">
        <div class="bk-hero">
          <div class="bk-hero-info">
            <h2>📚 Baunty Kutubxonasi</h2>
            <p>O'zbek va jahon adabiyoti durdonalari, biznes va psixologiya kitoblari</p>
          </div>
          <span class="bk-hero-badge">${booksList.length}+ Kitob</span>
        </div>

        <label class="bk-search" id="bkSearchBox">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          <input id="bkQuery" type="search" inputmode="search" autocomplete="off" placeholder="Kitob yoki muallif nomi…" value="${esc(searchQuery)}">
          <button class="bk-clr" id="bkClr" type="button">✕</button>
        </label>

        <div class="bk-chips" id="bkChipsBar">${chipsHtml}</div>

        <div id="bkGrid" class="bk-grid"></div>
      </div>
    `;

    // Event listenerlar
    const inp = $("bkQuery");
    const clr = $("bkClr");
    const sBox = $("bkSearchBox");

    if (inp) {
      if (searchQuery) sBox.classList.add("has");
      let st;
      inp.addEventListener("input", (e) => {
        searchQuery = e.target.value.trim();
        sBox.classList.toggle("has", !!searchQuery);
        clearTimeout(st);
        st = setTimeout(() => { renderGrid(); }, 120);
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") inp.blur();
      });
    }

    if (clr) {
      clr.onclick = (e) => {
        e.preventDefault();
        inp.value = "";
        searchQuery = "";
        sBox.classList.remove("has");
        renderGrid();
      };
    }

    const chipsBar = $("bkChipsBar");
    if (chipsBar) {
      chipsBar.addEventListener("click", (e) => {
        const btn = e.target.closest(".bk-chip");
        if (!btn) return;
        haptic();
        activeCategory = btn.dataset.c;
        chipsBar.querySelectorAll(".bk-chip").forEach((b) => b.classList.toggle("on", b === btn));
        renderGrid();
      });
    }

    renderGrid();
  }

  // ---------- Kartochkalar Gridini render qilish ----------
  function renderGrid() {
    const grid = $("bkGrid");
    if (!grid) return;

    let list = booksList;

    if (activeCategory === "fav") {
      list = list.filter((b) => savedFavorites.includes(String(b.id)));
    } else if (activeCategory === "pop") {
      list = list.filter((b) => b.popular || (b.views && b.views > 50000));
    } else if (activeCategory !== "all") {
      list = list.filter((b) => b.category === activeCategory);
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter((b) =>
        (b.title && b.title.toLowerCase().includes(q)) ||
        (b.author && b.author.toLowerCase().includes(q)) ||
        (b.description && b.description.toLowerCase().includes(q))
      );
    }

    const countEl = $("count");
    if (countEl) {
      countEl.textContent = `${list.length} ta kitob · bepul mutolaa`;
    }

    if (!list.length) {
      grid.innerHTML = activeCategory === "fav"
        ? `<div class="empty" style="grid-column: 1/-1"><div class="big">⭐</div><b>Hali kitob saqlamadingiz</b>Kitob tanlab, «Saqlash» tugmasini bosing.</div>`
        : `<div class="empty" style="grid-column: 1/-1"><div class="big">🔍</div><b>Kitob topilmadi</b>Boshqa nom yoki muallif bilan qidirib ko'ring.</div>`;
      return;
    }

    grid.innerHTML = list.map((b) => {
      const isPop = b.popular || (b.views && b.views > 60000);
      return `
        <button class="bk-card" data-bid="${esc(b.id)}">
          <div class="bk-cover">
            ${isPop ? `<span class="bk-badge-pop">🔥 XIT</span>` : ""}
            <span class="bk-badge-fmt">${esc(b.format || "PDF")}</span>
            <div class="bk-ph">
              <span class="bk-ph-icon">📖</span>
              <span class="bk-ph-title">${esc(b.title)}</span>
            </div>
            ${b.cover ? `<img src="${esc(b.cover)}" alt="${esc(b.title)}" loading="lazy" decoding="async" onload="this.classList.add('ok')">` : ""}
          </div>
          <div class="bk-title">${esc(b.title)}</div>
          <div class="bk-author">${esc(b.author)}</div>
          <div class="bk-meta-row">
            <span class="bk-rating">⭐ ${b.rating || "4.9"}</span>
            <span>•</span>
            <span>${b.pages || 200} bet</span>
          </div>
        </button>
      `;
    }).join("");

    grid.querySelectorAll(".bk-card").forEach((btn) => {
      btn.onclick = () => {
        const id = btn.dataset.bid;
        const book = booksById.get(String(id));
        if (book) openDetail(book);
      };
    });
  }

  // ---------- Kitob Tafsilotlari Modali ----------
  function ensureDetailModal() {
    let det = $("bkDetModal");
    if (det) return det;

    det = document.createElement("section");
    det.id = "bkDetModal";
    det.className = "bk-det";
    det.setAttribute("aria-modal", "true");
    det.innerHTML = `
      <button class="bk-det-close" id="bkDetClose">✕</button>
      <div class="bk-det-hero">
        <div class="bk-det-blur" id="bkDetBlur"></div>
        <div class="bk-det-cover">
          <img id="bkDetImg" src="" alt="">
        </div>
      </div>
      <div class="bk-det-body">
        <h2 class="bk-det-title" id="bkDetTitle"></h2>
        <div class="bk-det-author" id="bkDetAuthor"></div>
        <div class="bk-det-chips" id="bkDetChips"></div>
        <p class="bk-det-desc" id="bkDetDesc"></p>
        <div class="bk-det-actions">
          <button class="bk-btn-read" id="bkBtnRead">📖 Mutolaa qilish (O'qish)</button>
          <button class="bk-btn-send" id="bkBtnSend">📥 Bot chatiga olish (PDF)</button>
          <div class="bk-btn-row">
            <button class="bk-btn-sec" id="bkBtnFav">⭐ Saqlash</button>
            <button class="bk-btn-sec" id="bkBtnShare">🔗 Do'stlarga ulashish</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(det);

    $("bkDetClose").onclick = closeDetail;

    return det;
  }

  function openDetail(book) {
    currentBook = book;
    haptic();
    const det = ensureDetailModal();

    $("bkDetTitle").textContent = book.title;
    $("bkDetAuthor").textContent = `✍️ ${book.author}`;
    $("bkDetDesc").textContent = book.description || "Mazkur kitob haqida to'liq ma'lumot tez orada taqdim etiladi.";

    const img = $("bkDetImg");
    const blur = $("bkDetBlur");
    if (book.cover) {
      img.src = book.cover;
      blur.style.backgroundImage = `url('${book.cover}')`;
    } else {
      img.src = "";
      blur.style.backgroundImage = "";
    }

    const isFav = savedFavorites.includes(String(book.id));
    $("bkBtnFav").textContent = isFav ? "★ Saqlangan" : "⭐ Saqlash";

    $("bkDetChips").innerHTML = `
      <span class="bk-det-tag">📂 ${esc(book.category_name || "Badiiy")}</span>
      <span class="bk-det-tag">📄 ${book.pages || 200} sahifa</span>
      <span class="bk-det-tag">⭐ ${book.rating || 4.9} / 5.0</span>
      <span class="bk-det-tag">💾 ${book.format || "PDF"} (${book.size_mb || 2.5} MB)</span>
    `;

    $("bkBtnRead").onclick = () => openReader(book);
    $("bkBtnSend").onclick = () => sendBookToChat(book);
    $("bkBtnFav").onclick = () => toggleFavorite(book);
    $("bkBtnShare").onclick = () => shareBook(book);

    det.scrollTop = 0;
    det.classList.add("open");
    isDetailOpen = true;

    if (inTg) {
      tg.BackButton.show();
    }
  }

  function closeDetail() {
    const det = $("bkDetModal");
    if (det) det.classList.remove("open");
    isDetailOpen = false;
    currentBook = null;
    if (inTg && !isReaderOpen && window.ZK_canHideBack && window.ZK_canHideBack()) {
      tg.BackButton.hide();
    }
  }

  // ---------- Mutolaa Rejimi (In-App Reader) ----------
  function ensureReaderModal() {
    let r = $("bkReaderModal");
    if (r) return r;

    r = document.createElement("section");
    r.id = "bkReaderModal";
    r.className = "bk-reader theme-dark";
    r.setAttribute("aria-modal", "true");
    r.innerHTML = `
      <div class="bk-reader-bar">
        <button class="bk-tool-btn" id="bkReaderBack">‹ Chiqish</button>
        <span class="bk-reader-title" id="bkReaderTitle">Kitob</span>
        <div class="bk-reader-tools">
          <button class="bk-tool-btn" id="bkFontDown" title="Kichraytirish">A-</button>
          <button class="bk-tool-btn" id="bkFontUp" title="Kattalashtirish">A+</button>
          <button class="bk-tool-btn" id="bkThemeToggle" title="Mavzu">🎨</button>
        </div>
      </div>
      <div class="bk-reader-content" id="bkReaderContent"></div>
    `;
    document.body.appendChild(r);

    $("bkReaderBack").onclick = closeReader;
    $("bkFontDown").onclick = () => adjustFontSize(-1.5);
    $("bkFontUp").onclick = () => adjustFontSize(1.5);
    $("bkThemeToggle").onclick = cycleTheme;

    return r;
  }

  function openReader(book) {
    isReaderOpen = true;
    haptic();
    const r = ensureReaderModal();
    $("bkReaderTitle").textContent = book.title;

    const sample = book.sample_text || book.description || "";
    $("bkReaderContent").innerHTML = `
      <div style="text-align:center;margin-bottom:28px">
        <h2 style="font-size:24px;margin:0 0 6px">${esc(book.title)}</h2>
        <div style="font-size:15px;opacity:.7">✍️ ${esc(book.author)}</div>
      </div>
      <div style="font-size:${readerFontSize}px;letter-spacing:.2px;white-space:pre-line">
        ${esc(sample)}
      </div>
      <div style="margin-top:40px;padding:20px;border-radius:14px;background:rgba(255,255,255,0.06);text-align:center">
        <b>To'liq asarni bot chatida o'qishni xohlaysizmi?</b><br>
        <span style="font-size:13px;opacity:.8">Quyidagi tugma orqali to'liq PDF kitobni shaxsiy xabarlaringizga qabul qiling:</span><br><br>
        <button class="cta" id="bkReaderSendBtn" style="max-width:260px;margin:0 auto">📥 Bot chatiga yuborish</button>
      </div>
    `;

    $("bkReaderSendBtn").onclick = () => {
      sendBookToChat(book);
    };

    r.scrollTop = 0;
    r.classList.add("open");

    if (inTg) {
      tg.BackButton.show();
    }
  }

  function closeReader() {
    const r = $("bkReaderModal");
    if (r) r.classList.remove("open");
    isReaderOpen = false;
    if (inTg && !isDetailOpen && window.ZK_canHideBack && window.ZK_canHideBack()) {
      tg.BackButton.hide();
    }
  }

  function adjustFontSize(delta) {
    readerFontSize = Math.min(26, Math.max(13, readerFontSize + delta));
    const content = $("bkReaderContent");
    if (content) {
      const p = content.querySelector("div[style*='font-size']");
      if (p) p.style.fontSize = `${readerFontSize}px`;
    }
    haptic();
  }

  function cycleTheme() {
    const r = $("bkReaderModal");
    if (!r) return;
    if (readerTheme === "dark") readerTheme = "sepia";
    else if (readerTheme === "sepia") readerTheme = "white";
    else readerTheme = "dark";

    r.className = `bk-reader theme-${readerTheme} open`;
    toast(`Mavzu: ${readerTheme === "dark" ? "🌙 Tungi" : readerTheme === "sepia" ? "📜 Sepiya" : "☀️ Kunduzgi"}`);
    haptic();
  }

  // ---------- Chatga yuborish (POST /api/books/send) ----------
  async function sendBookToChat(book) {
    haptic("hit");
    const uid = (inTg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id)
      || (new URLSearchParams(window.location.search).get("user_id"))
      || "";

    const targetUrl = `https://t.me/${botName}?start=b_${book.id}`;

    if (!uid && !inTg) {
      toast("🤖 Bot chatiga yo'naltirilmoqda…", 2000);
      setTimeout(() => window.open(targetUrl, "_blank"), 300);
      return;
    }

    toast("⏳ Kitob tayyorlanmoqda…", 2000);

    try {
      const res = await fetch("api/books/send", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Init-Data": (inTg && tg.initData) ? tg.initData : ""
        },
        body: JSON.stringify({
          id: String(book.id),
          user_id: uid ? Number(uid) : undefined
        })
      });
      const data = await res.json();

      if (data.ok && data.delivered) {
        haptic("ok");
        toast(`✅ «${book.title}» bot chatiga yuborildi!`);
      } else if (data.action === "open_bot" || data.url) {
        const u = data.url || targetUrl;
        toast("🤖 Bot chatiga o'ting va kitobni oling", 2200);
        if (inTg && tg.openTelegramLink) tg.openTelegramLink(u);
        else window.open(u, "_blank");
      } else {
        haptic("err");
        toast("⚠️ Yuborib bo'lmadi. Bot chatini oching", 2600);
      }
    } catch (e) {
      haptic("err");
      toast("📶 Internet xatoligi. Qayta urinib ko'ring", 2400);
    }
  }

  // ---------- Sevimlilar / Do'stlarga ulashish ----------
  function toggleFavorite(book) {
    const id = String(book.id);
    if (savedFavorites.includes(id)) {
      savedFavorites = savedFavorites.filter((x) => x !== id);
      toast("Sevimlilardan olib tashlandi");
      $("bkBtnFav").textContent = "⭐ Saqlash";
    } else {
      savedFavorites.unshift(id);
      toast("⭐ Sevimlilarga saqlandi!");
      $("bkBtnFav").textContent = "★ Saqlangan";
    }
    lsSet("baunty_bk_favs", savedFavorites);
    haptic();
  }

  function shareBook(book) {
    haptic();
    const shareUrl = `https://t.me/share/url?url=https://t.me/${botName}?start=b_${book.id}&text=${encodeURIComponent(book.title + " — ajoyib kitob! Baunty Kutubxonasida bepul o'qing.")}`;
    if (inTg && tg.openTelegramLink) {
      tg.openTelegramLink(shareUrl);
    } else {
      window.open(shareUrl, "_blank");
    }
  }

  // ---------- Ochiq API (window.ZBooks) ----------
  window.ZBooks = {
    open: async () => {
      if (!booksList.length) {
        await fetchBooks();
      }
      renderView();
    },
    close: () => {
      closeReader();
      closeDetail();
    },
    busy: () => {
      if (isReaderOpen) {
        closeReader();
        return true;
      }
      if (isDetailOpen) {
        closeDetail();
        return true;
      }
      return false;
    },
    setBot: (name) => {
      if (name) botName = String(name).replace(/^@/, "");
    },
    openDetail: (id) => {
      const book = booksById.get(String(id));
      if (book) openDetail(book);
    },
    search: (query) => {
      searchQuery = query || "";
      const inp = $("bkQuery");
      if (inp) inp.value = searchQuery;
      renderGrid();
    }
  };
})();
