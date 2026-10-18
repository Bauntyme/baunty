/* ===================================================================
   🎲 ZK Mini App — Samarqand Tuni va Interaktiv Modullar (zk.js)
   Coverflow, Oltin Kubik Ruletkasi, Splash va Siljuvchi Indikator
   =================================================================== */

(() => {
  "use strict";

  const tg = window.Telegram && Telegram.WebApp;
  const haptic = (t) => {
    try {
      if (!tg || !tg.HapticFeedback) return;
      if (t === "ok") tg.HapticFeedback.notificationOccurred("success");
      else if (t === "err") tg.HapticFeedback.notificationOccurred("error");
      else if (t === "hit") tg.HapticFeedback.impactOccurred("medium");
      else tg.HapticFeedback.selectionChanged();
    } catch (e) {}
  };

  // 1. Siljuvchi Indikator (.zk-ind)
  function updateIndicator(btn) {
    const ind = document.getElementById("zkInd");
    if (!ind || !btn) return;
    const parent = btn.parentElement;
    if (!parent) return;

    const bRect = btn.getBoundingClientRect();
    const pRect = parent.getBoundingClientRect();
    const left = bRect.left - pRect.left + parent.scrollLeft;

    ind.style.width = `${bRect.width}px`;
    ind.style.transform = `translateX(${left}px)`;
  }

  // 2. Coverflow markazdagi kartochkani aniqlash (.zk-mid)
  function updateFlowCenter(flow) {
    if (!flow) flow = document.getElementById("zkFlow");
    if (!flow) return;

    const rect = flow.getBoundingClientRect();
    const center = rect.left + rect.width / 2;
    const cards = flow.querySelectorAll(".card");

    let closest = null;
    let minDiff = Infinity;

    cards.forEach((card) => {
      const cRect = card.getBoundingClientRect();
      const cCenter = cRect.left + cRect.width / 2;
      const diff = Math.abs(center - cCenter);
      if (diff < minDiff) {
        minDiff = diff;
        closest = card;
      }
    });

    cards.forEach((c) => {
      c.classList.toggle("zk-mid", c === closest);
    });
  }

  function initFlow(flow) {
    if (!flow) return;
    let scrollTimeout;
    const onScroll = () => {
      updateFlowCenter(flow);
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => updateFlowCenter(flow), 80);
    };

    flow.removeEventListener("scroll", onScroll);
    flow.addEventListener("scroll", onScroll, { passive: true });
    setTimeout(() => updateFlowCenter(flow), 60);
  }

  // 3. Oltin Kubik Ruletkasi (.zk-slot & ZK_spin)
  let isSpinning = false;
  let spinTimer = null;

  function spinRoulette(itemsList, onSelectCallback) {
    const items = itemsList || window.ZK_ITEMS || [];
    if (!items || !items.length) {
      if (window.toast) window.toast("Katalog yuklanmoqda…");
      return;
    }
    if (isSpinning) return;

    const slot = document.getElementById("zkSlot");
    const reel = document.getElementById("zkSlotReel");
    const closeBtn = document.getElementById("zkSlotClose");
    const spinBtn = document.getElementById("zkSlotSpinBtn");
    if (!slot || !reel) return;

    haptic("hit");
    isSpinning = true;
    slot.removeAttribute("hidden");
    slot.classList.add("open");

    // Tasodifiy g'olibni tanlash
    const winnerIdx = Math.floor(Math.random() * items.length);
    const winner = items[winnerIdx];

    // 22 ta elementli ruletka zanjiri
    const count = 22;
    const stopAt = count - 4; // g'olib o'rtadagi chiziqqa tushadi
    let reelHTML = "";

    for (let i = 0; i < count; i++) {
      const it = (i === stopAt) ? winner : items[Math.floor(Math.random() * items.length)];
      const img = it.i ? `<img src="p/${it.c}_s.webp?v=${it.i}" alt="">` : "";
      reelHTML += `<div class="zk-slot-item" data-idx="${i}">
        ${img || `<div class="ph">${it.t || "Kino"}</div>`}
        <span class="badge">#${it.c}</span>
        ${it.p > 1 ? `<span class="parts">${it.p} qism</span>` : ""}
      </div>`;
    }

    reel.style.transition = "none";
    reel.style.transform = "translateY(0px)";
    reel.innerHTML = reelHTML;

    // Tezkor aylanib boshlash
    requestAnimationFrame(() => {
      // Element balandligi: 160px + 12px gap = 172px
      const itemHeight = 172;
      const targetY = -(stopAt * itemHeight - 20);

      // Haptic effektlar zanjiri
      let hCount = 0;
      const hInterval = setInterval(() => {
        haptic("hit");
        hCount++;
        if (hCount > 18) clearInterval(hInterval);
      }, 160);

      reel.style.transition = "transform 3.2s cubic-bezier(0.12, 0.8, 0.22, 1)";
      reel.style.transform = `translateY(${targetY}px)`;

      clearTimeout(spinTimer);
      spinTimer = setTimeout(() => {
        clearInterval(hInterval);
        haptic("ok");
        isSpinning = false;

        const winnerCard = reel.querySelector(`[data-idx="${stopAt}"]`);
        if (winnerCard) {
          winnerCard.style.boxShadow = "0 0 35px #F2B84B, 0 0 15px #FFF";
          winnerCard.style.border = "2px solid #F2B84B";
        }

        setTimeout(() => {
          slot.classList.remove("open");
          setTimeout(() => slot.setAttribute("hidden", ""), 250);
          if (typeof onSelectCallback === "function") {
            onSelectCallback(winner);
          } else if (typeof window.openDetail === "function") {
            window.openDetail(winner);
          }
        }, 850);
      }, 3350);
    });

    const closeHandler = () => {
      clearTimeout(spinTimer);
      isSpinning = false;
      slot.classList.remove("open");
      setTimeout(() => slot.setAttribute("hidden", ""), 250);
    };

    if (closeBtn) closeBtn.onclick = closeHandler;
    if (spinBtn) spinBtn.onclick = () => {
      if (!isSpinning) spinRoulette(items, onSelectCallback);
    };
  }

  // 4. Splash ochilish ekrani
  function initSplash() {
    const splash = document.getElementById("zksplash");
    if (!splash) return;

    const closeSplash = () => {
      if (!splash.classList.contains("hide")) {
        splash.classList.add("hide");
        setTimeout(() => {
          splash.style.display = "none";
        }, 450);
      }
    };

    // 1.2 soniyada silliq yo'qolishi
    setTimeout(closeSplash, 1200);
    splash.addEventListener("click", closeSplash);
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
  });
})();
