/* 📚 Bauntys Kutubxonasi — Books Module (window.ZBooks) */
(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  const inTg = !!(tg && tg.initData);
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));

  // Qidiruv: lotin <-> kirill normallashtirish
  const CYR = {
    "а":"a","б":"b","в":"v","г":"g","ғ":"g","д":"d","е":"e","ё":"yo","ж":"j","з":"z","и":"i","й":"y","к":"k",
    "қ":"q","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ў":"o","ф":"f","х":"x","ҳ":"h",
    "ц":"ts","ч":"ch","ш":"sh","щ":"sh","ъ":"","ы":"i","ь":"","э":"e","ю":"yu","я":"ya"
  };
  const norm = (s) => String(s || "").toLowerCase()
    .replace(/[а-яёғқўҳ]/g, (ch) => CYR[ch] ?? ch)
    .replace(/[ʻʼ'`’‘´]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();

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
  let activeSub = "home"; // "home" (Kutubxona), "search" (Qidiruv), "shelf" (Javonim)
  let activeLang = "all"; // "all", "uz", "en", "ru"
  let activeCategory = "all"; // "all", "pop", "badiiy", "biznes", "psixologiya", "diniy", "tarix", "bolalar"
  let searchQuery = "";
  let booksList = [];
  let booksById = new Map();
  let currentBook = null;
  let isReaderOpen = false;
  let isDetailOpen = false;
  let readerFontSize = 16;
  let readerTheme = "dark"; // dark, sepia, white
  let savedFavorites = lsGet("baunty_bk_favs", []);
  let isLoadingBooks = false;
  let loadError = false;

  // ---------- Ma'lumotlarni yuklash ----------
  async function fetchBooks() {
    if (isLoadingBooks) return booksList;
    isLoadingBooks = true;
    loadError = false;
    try {
      const res = await fetch("api/books", { cache: "no-store" });
      const data = await res.json();
      booksList = data.items || [];
      booksById.clear();
      booksList.forEach((b) => {
        const idStr = String(b.id);
        booksById.set(idStr, b);
        b._n = norm(`${b.title} ${b.author} ${b.description}`);
      });
      // Stale favoritlarni tozalash
      savedFavorites = savedFavorites.filter((id) => booksById.has(String(id)));
      lsSet("baunty_bk_favs", savedFavorites);
      isLoadingBooks = false;
      return booksList;
    } catch (e) {
      console.warn("Kitoblarni yuklab bo'lmadi:", e);
      isLoadingBooks = false;
      loadError = true;
      return [];
    }
  }

  // ---------- Skeleton yuklanish holati ----------
  function renderSkeleton(container) {
    if (!container) return;
    container.innerHTML = `
      <div class="bk-view">
        <div class="bk-hero" style="opacity:.6">
          <div class="bk-hero-info">
            <h2>Bugun nima o'qiymiz?</h2>
            <p>Bauntys Kutubxonasi — 3 tilda kitoblar • bepul mutolaa</p>
          </div>
          <span class="bk-hero-badge">Yuklanmoqda…</span>
        </div>
        <div class="bk-sec">
          <div class="bk-sec-h"><h2>&nbsp;</h2></div>
          <div class="bk-shelf">
            ${Array.from({length: 6}, () => `
              <div class="bk-card bk-sk">
                <div class="bk-cover bk-sk-cover"></div>
                <div class="bk-sk-line" style="width:80%"></div>
                <div class="bk-sk-line" style="width:55%"></div>
              </div>
            `).join("")}
          </div>
        </div>
      </div>
    `;
  }

  // ---------- Yordamchi kitob kartochkasi HTML ----------
  function bookCardHTML(b, rank = null) {
    const isPop = b.popular || (b.views && b.views > 60000);
    const isFav = savedFavorites.includes(String(b.id));
    return `
      <button class="bk-card" data-bid="${esc(b.id)}" type="button">
        <div class="bk-cover">
          ${isPop && !rank ? `<span class="bk-badge-pop">🔥 XIT</span>` : ""}
          <span class="bk-badge-fmt">${esc(b.format || "PDF")}</span>
          ${isFav ? `<span class="bk-badge-fav">★</span>` : ""}
          <div class="bk-ph">
            <span class="bk-ph-icon">📖</span>
            <span class="bk-ph-title">${esc(b.title)}</span>
          </div>
          ${b.cover ? `<img src="${esc(b.cover)}" alt="${esc(b.title)}" loading="lazy" decoding="async" onload="this.classList.add('ok')">` : ""}
          ${rank ? `<span class="bk-rank">${rank}</span>` : ""}
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
  }

  // ---------- Gorizontal javon (Carousel) HTML ----------
  function shelfHTML(title, subtitle, list, isTop10 = false) {
    if (!list || !list.length) return "";
    return `
      <div class="bk-sec">
        <div class="bk-sec-h">
          <div>
            <h2>${title}</h2>
            ${subtitle ? `<span class="bk-sec-sub">${subtitle}</span>` : ""}
          </div>
          <span class="bk-sec-count">${list.length} ta</span>
        </div>
        <div class="bk-shelf">
          ${list.map((b, idx) => bookCardHTML(b, isTop10 ? (idx + 1) : null)).join("")}
        </div>
      </div>
    `;
  }

  // ---------- Asosiy DOM Ko'rinishi ----------
  function renderView() {
    const main = $("main");
    if (!main) return;

    // Pastki Sub-tablar paneli
    ensureSubTabsBar();

    // 1. Kutubxona bosh sahifasi (Home / Shelves)
    if (activeSub === "home") {
      renderHome(main);
    }
    // 2. Qidiruv sahifasi (Search / Grid)
    else if (activeSub === "search") {
      renderSearchPage(main);
    }
    // 3. Mening Javonim (Favorites Shelf)
    else if (activeSub === "shelf") {
      renderMyShelf(main);
    }

    bindCardEvents();
  }

  // ---------- 1. Kutubxona Javonlari Ko'rinishi ----------
  function renderHome(container) {
    const langs = [
      { id: "all", label: "Hammasi" },
      { id: "uz", label: "🇺🇿 O'zbek" },
      { id: "en", label: "🇬🇧 English" },
      { id: "ru", label: "🇷🇺 Русский" }
    ];

    let langsHtml = langs.map((l) =>
      `<button class="bk-lang${activeLang === l.id ? " on" : ""}" data-l="${l.id}">${l.label}</button>`
    ).join("");

    container.innerHTML = `
      <div class="bk-view">
        <div class="bk-hero">
          <div class="bk-hero-info">
            <h2>Bugun nima o'qiymiz?</h2>
            <p>Bauntys Kutubxonasi — 3 tilda kitoblar • bepul mutolaa</p>
          </div>
          <span class="bk-hero-badge">${booksList.length}+ Kitob</span>
        </div>

        <label class="bk-search" id="bkSearchBox">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          <input id="bkQuery" type="search" inputmode="search" autocomplete="off" placeholder="Kitob, muallif yoki janr..." value="${esc(searchQuery)}">
          <button class="bk-clr" id="bkClr" type="button" aria-label="Tozalash">✕</button>
        </label>

        <div class="bk-langs" id="bkLangsBar">${langsHtml}</div>

        <div id="bkContentArea"></div>
      </div>
    `;

    bindSearchAndLangInputs();
    renderHomeShelves();
  }

  function renderHomeShelves() {
    const area = $("bkContentArea");
    if (!area) return;

    if (loadError && !booksList.length) {
      area.innerHTML = `
        <div class="empty">
          <div class="big">📶</div>
          <b>Kitoblarni yuklab bo'lmadi</b>
          Internet aloqasini tekshirib, qayta urinib ko'ring.<br><br>
          <button class="cta" style="max-width:200px" id="bkRetryBtn">🔄 Qayta urinish</button>
        </div>
      `;
      const rb = $("bkRetryBtn");
      if (rb) rb.onclick = async () => {
        renderSkeleton($("main"));
        await fetchBooks();
        renderView();
      };
      return;
    }

    // Agar qidiruv kiritilgan bo'lsa, javonlar o'rniga qidiruv natijalarini ko'rsatamiz
    if (searchQuery) {
      renderSearchResultsGrid(area);
      return;
    }

    let baseList = booksList;
    if (activeLang !== "all") {
      baseList = baseList.filter((b) => b.lang === activeLang);
    }

    // 1. 🔥 Haftalik TOP-10
    const top10 = [...baseList].sort((a, b) => (b.views || 0) - (a.views || 0)).slice(0, 10);

    // 2. 🇺🇿 O'zbek adabiyoti durdonalari
    const uzClassic = baseList.filter((b) =>
      b.lang === "uz" && (b.category === "badiiy" || b.category === "tarix" || [
        "Abdulla Qodiriy", "Abdulhamid Cho'lpon", "Tohir Malik", "Xudoyberdi To'xtaboyev", "Amir Temur", "Shayx Muhammad Sodiq Muhammad Yusuf", "Ahmad Lutfiy Qozonchi"
      ].includes(b.author))
    );

    // 3. 🌍 Jahon adabiyoti durdonalari
    const worldClassic = baseList.filter((b) =>
      b.category === "badiiy" && (b.lang !== "uz" || ["5", "20"].includes(String(b.id)) || ["Paulo Koelo", "Ernest Xeminguey"].includes(b.author))
    );

    // 4. 💼 Biznes va Psixologiya
    const bizPsi = baseList.filter((b) => b.category === "biznes" || b.category === "psixologiya");

    // 5. 🏛 Tarixiy asarlar
    const historyBooks = baseList.filter((b) =>
      b.category === "tarix" || (b.category === "diniy" && b.year < 2010) || ["1", "2", "7", "12", "14"].includes(String(b.id))
    );

    // 6. 🧸 Bolalar adabiyoti
    const kidsBooks = baseList.filter((b) =>
      b.category === "bolalar" || ["15", "16", "25", "32"].includes(String(b.id))
    );

    // Tilga mos sarlavhalar
    let topTitle = "🔥 Haftalik TOP-10";
    let topSub = "eng ko'p mutolaa qilingan sara kitoblar";
    let litTitle = "🇺🇿 O'zbek adabiyoti durdonalari";
    let litSub = "milliy adabiyotimizning nodir asarlari";

    if (activeLang === "en") {
      topTitle = "🔥 Top English Bestsellers";
      topSub = "most read and highly acclaimed masterpieces";
      litTitle = "📖 Fiction & Literature Classics";
      litSub = "world-renowned fiction and essential reading";
    } else if (activeLang === "ru") {
      topTitle = "🔥 Топ недели на русском";
      topSub = "самые читаемые бестселлеры и шедевры";
      litTitle = "📖 Шедевры русской и мировой классики";
      litSub = "великие романы и бессмертные произведения";
    }

    area.innerHTML = `
      ${shelfHTML(topTitle, topSub, top10, true)}
      ${uzClassic.length && activeLang !== "en" && activeLang !== "ru" ? shelfHTML(litTitle, litSub, uzClassic) : ""}
      ${worldClassic.length ? shelfHTML(activeLang === "all" ? "🌍 Jahon adabiyoti durdonalari" : litTitle, activeLang === "all" ? "dunyo bestsellerlari va sara badiiy asarlar" : litSub, worldClassic) : ""}
      ${bizPsi.length ? shelfHTML("💼 Biznes va Psixologiya", "shaxsiy rivojlanish, moliya va yetakchilik", bizPsi) : ""}
      ${historyBooks.length ? shelfHTML("🏛 Tarixiy asarlar", "o'tmish saboqlari va buyuk allomalar merosi", historyBooks) : ""}
      ${kidsBooks.length ? shelfHTML("🧸 Bolalar adabiyoti", "qiziqarli sarguzashtlar va tarbiyaviy ertaklar", kidsBooks) : ""}
    `;

    bindCardEvents();
  }

  // ---------- 2. Qidiruv Sahifasi Ko'rinishi ----------
  function renderSearchPage(container) {
    const langs = [
      { id: "all", label: "Hammasi" },
      { id: "uz", label: "🇺🇿 O'zbek" },
      { id: "en", label: "🇬🇧 English" },
      { id: "ru", label: "🇷🇺 Русский" }
    ];

    const chips = [
      { id: "all", label: "📚 Barchasi" },
      { id: "pop", label: "🔥 Ommabop" },
      { id: "badiiy", label: "📖 Badiiy" },
      { id: "biznes", label: "💼 Biznes" },
      { id: "psixologiya", label: "🧠 Psixologiya" },
      { id: "diniy", label: "🕌 Diniy" },
      { id: "tarix", label: "📜 Tarix" },
      { id: "bolalar", label: "🧸 Bolalar" }
    ];

    let langsHtml = langs.map((l) =>
      `<button class="bk-lang${activeLang === l.id ? " on" : ""}" data-l="${l.id}">${l.label}</button>`
    ).join("");

    let chipsHtml = chips.map((c) =>
      `<button class="bk-chip${activeCategory === c.id ? " on" : ""}" data-c="${c.id}">${c.label}</button>`
    ).join("");

    container.innerHTML = `
      <div class="bk-view">
        <label class="bk-search" id="bkSearchBox">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          <input id="bkQuery" type="search" inputmode="search" autocomplete="off" placeholder="Kitob, muallif yoki janr..." value="${esc(searchQuery)}">
          <button class="bk-clr" id="bkClr" type="button" aria-label="Tozalash">✕</button>
        </label>

        <div class="bk-langs" id="bkLangsBar">${langsHtml}</div>
        <div class="bk-chips" id="bkChipsBar">${chipsHtml}</div>

        <div id="bkContentArea"></div>
      </div>
    `;

    bindSearchAndLangInputs();
    bindCategoryChips();
    renderSearchResultsGrid($("bkContentArea"));
  }

  // ---------- 3. Mening Javonim Sahifasi Ko'rinishi ----------
  function renderMyShelf(container) {
    const langs = [
      { id: "all", label: "Hammasi" },
      { id: "uz", label: "🇺🇿 O'zbek" },
      { id: "en", label: "🇬🇧 English" },
      { id: "ru", label: "🇷🇺 Русский" }
    ];

    let langsHtml = langs.map((l) =>
      `<button class="bk-lang${activeLang === l.id ? " on" : ""}" data-l="${l.id}">${l.label}</button>`
    ).join("");

    container.innerHTML = `
      <div class="bk-view">
        <div class="bk-hero">
          <div class="bk-hero-info">
            <h2>🔖 Mening Javonim</h2>
            <p>Saqlangan va mutolaa qilinayotgan sevimli kitoblaringiz</p>
          </div>
          <span class="bk-hero-badge" id="bkShelfBadge">${savedFavorites.length} ta</span>
        </div>

        <div class="bk-langs" id="bkLangsBar">${langsHtml}</div>

        <div id="bkContentArea"></div>
      </div>
    `;

    bindSearchAndLangInputs();
    renderShelfFavoritesGrid($("bkContentArea"));
  }

  // ---------- Qidiruv natijalarini Grid ko'rinishida chiqarish ----------
  function renderSearchResultsGrid(target) {
    if (!target) return;

    let list = booksList;

    if (activeLang !== "all") {
      list = list.filter((b) => b.lang === activeLang);
    }

    if (activeCategory === "pop") {
      list = list.filter((b) => b.popular || (b.views && b.views > 50000));
    } else if (activeCategory !== "all") {
      list = list.filter((b) => b.category === activeCategory);
    }

    if (searchQuery) {
      const qNorm = norm(searchQuery);
      const qWords = qNorm.split(" ").filter(Boolean);
      list = list.filter((b) => {
        const raw = `${b.title} ${b.author} ${b.description}`.toLowerCase();
        const bNorm = b._n || norm(raw);
        return qWords.every((w) => bNorm.includes(w) || raw.includes(w));
      });
    }

    if (!list.length) {
      target.innerHTML = `
        <div class="empty" style="grid-column: 1/-1">
          <div class="big">🔍</div>
          <b>Hech qanday kitob topilmadi</b>
          Boshqa nom yoki muallif bilan qidirib ko'ring.
        </div>
      `;
      return;
    }

    target.innerHTML = `
      <div class="bk-sec-h">
        <h2>${searchQuery ? `«${esc(searchQuery)}» bo'yicha natijalar` : "Barcha kitoblar"}</h2>
        <span class="bk-sec-count">${list.length} ta</span>
      </div>
      <div class="bk-grid">
        ${list.map((b) => bookCardHTML(b)).join("")}
      </div>
    `;

    bindCardEvents();
  }

  // ---------- Saqlanganlar Gridi ----------
  function renderShelfFavoritesGrid(target) {
    if (!target) return;

    let list = booksList.filter((b) => savedFavorites.includes(String(b.id)));

    if (activeLang !== "all") {
      list = list.filter((b) => b.lang === activeLang);
    }

    if (!list.length) {
      target.innerHTML = `
        <div class="empty" style="grid-column: 1/-1">
          <div class="big">🔖</div>
          <b>Javoningiz hozircha bo'sh</b>
          Katalogdan kitob tanlab, «Saqlash» tugmasini bosing — barcha sevimli asarlaringiz shu yerda yig'iladi.<br><br>
          <button class="cta" style="max-width:220px;margin:0 auto" id="bkGoHomeBtn">📚 Kitoblarni ko'rish</button>
        </div>
      `;
      const btn = $("bkGoHomeBtn");
      if (btn) btn.onclick = () => {
        haptic();
        activeSub = "home";
        renderView();
      };
      return;
    }

    target.innerHTML = `
      <div class="bk-sec-h">
        <h2>Saqlangan kitoblaringiz</h2>
        <span class="bk-sec-count">${list.length} ta</span>
      </div>
      <div class="bk-grid">
        ${list.map((b) => bookCardHTML(b)).join("")}
      </div>
    `;

    bindCardEvents();
  }

  // ---------- Qidiruv va Til Filtrlari Hodisalari ----------
  function bindSearchAndLangInputs() {
    const inp = $("bkQuery");
    const clr = $("bkClr");
    const sBox = $("bkSearchBox");

    if (inp && sBox) {
      if (searchQuery) sBox.classList.add("has");
      let st;
      inp.addEventListener("input", (e) => {
        searchQuery = e.target.value.trim();
        sBox.classList.toggle("has", !!searchQuery);
        clearTimeout(st);
        st = setTimeout(() => {
          if (activeSub === "home") renderHomeShelves();
          else if (activeSub === "search") renderSearchResultsGrid($("bkContentArea"));
        }, 120);
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") inp.blur();
      });
    }

    if (clr && inp && sBox) {
      clr.onclick = (e) => {
        e.preventDefault();
        inp.value = "";
        searchQuery = "";
        sBox.classList.remove("has");
        if (activeSub === "home") renderHomeShelves();
        else if (activeSub === "search") renderSearchResultsGrid($("bkContentArea"));
      };
    }

    const langsBar = $("bkLangsBar");
    if (langsBar) {
      langsBar.addEventListener("click", (e) => {
        const btn = e.target.closest(".bk-lang");
        if (!btn) return;
        haptic();
        activeLang = btn.dataset.l;
        langsBar.querySelectorAll(".bk-lang").forEach((b) => b.classList.toggle("on", b === btn));
        if (activeSub === "home") renderHomeShelves();
        else if (activeSub === "search") renderSearchResultsGrid($("bkContentArea"));
        else if (activeSub === "shelf") renderShelfFavoritesGrid($("bkContentArea"));
      });
    }
  }

  function bindCategoryChips() {
    const chipsBar = $("bkChipsBar");
    if (chipsBar) {
      chipsBar.addEventListener("click", (e) => {
        const btn = e.target.closest(".bk-chip");
        if (!btn) return;
        haptic();
        activeCategory = btn.dataset.c;
        chipsBar.querySelectorAll(".bk-chip").forEach((b) => b.classList.toggle("on", b === btn));
        renderSearchResultsGrid($("bkContentArea"));
      });
    }
  }

  function bindCardEvents() {
    document.querySelectorAll(".bk-card[data-bid]").forEach((btn) => {
      btn.onclick = () => {
        const id = btn.dataset.bid;
        const book = booksById.get(String(id));
        if (book) openDetail(book);
      };
    });
  }

  // ---------- Pastki Sub-tablar Paneli (Floating Bar) ----------
  function ensureSubTabsBar() {
    let bar = $("bkSubTabs");
    if (!bar) {
      bar = document.createElement("nav");
      bar.id = "bkSubTabs";
      bar.className = "bk-subtabs";
      document.body.appendChild(bar);
    }

    const favCount = savedFavorites.length;
    bar.innerHTML = `
      <button class="bk-subtab${activeSub === "home" ? " on" : ""}" data-sub="home" type="button">
        <span class="bk-sub-icon">📚</span>
        <span class="bk-sub-label">Kutubxona</span>
      </button>
      <button class="bk-subtab${activeSub === "search" ? " on" : ""}" data-sub="search" type="button">
        <span class="bk-sub-icon">🔍</span>
        <span class="bk-sub-label">Qidiruv</span>
      </button>
      <button class="bk-subtab${activeSub === "shelf" ? " on" : ""}" data-sub="shelf" type="button">
        <span class="bk-sub-icon">🔖</span>
        <span class="bk-sub-label">Javonim</span>
        <span class="bk-sub-count" id="bkShelfCount" style="display:${favCount > 0 ? "inline-block" : "none"}">${favCount}</span>
      </button>
    `;
    bar.style.display = "flex";

    bar.querySelectorAll(".bk-subtab").forEach((btn) => {
      btn.onclick = () => {
        const target = btn.dataset.sub;
        if (activeSub === target) return;
        haptic();
        activeSub = target;
        renderView();
        window.scrollTo({ top: 0, behavior: "smooth" });
      };
    });
  }

  // ---------- Kitob Tafsilotlari Modali (Detail Sheet) ----------
  function ensureDetailModal() {
    let det = $("bkDetModal");
    if (det) return det;

    det = document.createElement("section");
    det.id = "bkDetModal";
    det.className = "bk-det";
    det.setAttribute("aria-modal", "true");
    det.innerHTML = `
      <button class="bk-det-close" id="bkDetClose" type="button">✕</button>
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
          <button class="bk-btn-read" id="bkBtnRead" type="button">📖 Mutolaa qilish (O'qish)</button>
          <button class="bk-btn-send" id="bkBtnSend" type="button">📥 Bot chatiga olish (PDF)</button>
          <div class="bk-btn-row">
            <button class="bk-btn-sec" id="bkBtnFav" type="button">⭐ Saqlash</button>
            <button class="bk-btn-sec" id="bkBtnShare" type="button">🔗 Do'stlarga ulashish</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(det);

    $("bkDetClose").onclick = closeDetail;

    return det;
  }

  function openDetail(book) {
    if (!book) return;
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
        <button class="bk-tool-btn" id="bkReaderBack" type="button">‹ Chiqish</button>
        <span class="bk-reader-title" id="bkReaderTitle">Kitob</span>
        <div class="bk-reader-tools">
          <button class="bk-tool-btn" id="bkFontDown" title="Kichraytirish" type="button">A-</button>
          <button class="bk-tool-btn" id="bkFontUp" title="Kattalashtirish" type="button">A+</button>
          <button class="bk-tool-btn" id="bkThemeToggle" title="Mavzu" type="button">🎨</button>
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
    if (!book) return;
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
      <div class="bk-reader-text" id="bkReaderText" style="font-size:${readerFontSize}px;letter-spacing:.2px;white-space:pre-line">
        ${esc(sample)}
      </div>
      <div class="bk-reader-box" style="margin-top:40px;padding:20px;border-radius:14px;background:rgba(255,255,255,0.06);text-align:center">
        <b>To'liq asarni bot chatida o'qishni xohlaysizmi?</b><br>
        <span style="font-size:13px;opacity:.8">Quyidagi tugma orqali to'liq PDF kitobni shaxsiy xabarlaringizga qabul qiling:</span><br><br>
        <button class="bk-btn-read" id="bkReaderSendBtn" style="max-width:260px;margin:0 auto" type="button">📥 Bot chatiga yuborish</button>
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
    if (inTg) {
      if (isDetailOpen) {
        tg.BackButton.show();
      } else if (window.ZK_canHideBack && window.ZK_canHideBack()) {
        tg.BackButton.hide();
      }
    }
  }

  function adjustFontSize(delta) {
    readerFontSize = Math.min(26, Math.max(13, readerFontSize + delta));
    const textEl = $("bkReaderText");
    if (textEl) {
      textEl.style.fontSize = `${readerFontSize}px`;
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

    // Pastki sub-tablar belgisini yangilash
    const countEl = $("bkShelfCount");
    if (countEl) {
      countEl.textContent = savedFavorites.length;
      countEl.style.display = savedFavorites.length > 0 ? "inline-block" : "none";
    }
    const badgeEl = $("bkShelfBadge");
    if (badgeEl) {
      badgeEl.textContent = `${savedFavorites.length} ta`;
    }

    if (activeSub === "shelf") {
      renderShelfFavoritesGrid($("bkContentArea"));
    }
  }

  function shareBook(book) {
    haptic();
    const shareUrl = `https://t.me/share/url?url=https://t.me/${botName}?start=b_${book.id}&text=${encodeURIComponent(book.title + " — ajoyib kitob! Bauntys Kutubxonasida bepul o'qing.")}`;
    if (inTg && tg.openTelegramLink) {
      tg.openTelegramLink(shareUrl);
    } else {
      window.open(shareUrl, "_blank");
    }
  }

  // ---------- Telegram BackButton & Keyboard listener ----------
  if (inTg) {
    tg.BackButton.onClick(() => {
      if (isReaderOpen) {
        closeReader();
        return;
      }
      if (isDetailOpen) {
        closeDetail();
        return;
      }
    });
  }

  window.addEventListener("popstate", () => {
    if (isReaderOpen) {
      closeReader();
    } else if (isDetailOpen) {
      closeDetail();
    }
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (isReaderOpen) closeReader();
      else if (isDetailOpen) closeDetail();
    }
  });

  // ---------- Ochiq API (window.ZBooks) ----------
  window.ZBooks = {
    open: async () => {
      if (!booksList.length) {
        renderSkeleton($("main"));
        await fetchBooks();
      }
      renderView();
    },
    close: () => {
      closeReader();
      closeDetail();
      const bar = $("bkSubTabs");
      if (bar) bar.style.display = "none";
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
    openDetail: async (id) => {
      if (!booksList.length) {
        renderSkeleton($("main"));
        await fetchBooks();
        renderView();
      }
      const book = booksById.get(String(id));
      if (book) openDetail(book);
    },
    search: async (query) => {
      searchQuery = query || "";
      activeSub = "search";
      if (!booksList.length) {
        renderSkeleton($("main"));
        await fetchBooks();
      }
      renderView();
    }
  };
})();
