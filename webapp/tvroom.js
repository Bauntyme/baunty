/* 📺 Tv Xona (TV Watch Party) — Bauntys
   Do'stlar bilan 4K jonli TV tomosha qilish, kanalni sinxronlashtirish,
   haqiqiy vaqtdagi chat, tezkor reaksiyalar va shovqinsiz WebRTC audio/ovozli chat.
   100% Bauntys brendi. */
(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  const inTg = !!(tg && tg.initData);
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const haptic = (t) => {
    try {
      if (t === "ok") tg.HapticFeedback.notificationOccurred("success");
      else if (t === "err") tg.HapticFeedback.notificationOccurred("error");
      else tg.HapticFeedback.selectionChanged();
    } catch (e) {}
  };

  // State
  let rootEl = null;
  let isOpen = false;
  let currentRoom = null;
  let lastVersion = 0;
  let lastMsgId = 0;
  let pollTimer = null;
  let hlsInstance = null;
  let hlsLibPromise = null;
  let allChannels = [];
  let publicRooms = [];
  let isChannelModalOpen = false;

  // WebRTC Mesh & Voice State
  let localAudioStream = null;
  let audioContext = null;
  let analyserNode = null;
  let audioAnimFrame = null;
  let isMicActive = false;
  let isSpeaking = false;
  const peerConnections = {}; // target_user_id -> RTCPeerConnection
  const remoteAudios = {}; // target_user_id -> HTMLAudioElement
  let lastSignalTs = 0;

  const rtcConfig = {
    iceServers: [
      { urls: "stun:stun.l.google.com:19302" },
      { urls: "stun:stun1.l.google.com:19302" },
      { urls: "stun:stun2.l.google.com:19302" }
    ]
  };

  function getUserProfile() {
    const u = (inTg && tg.initDataUnsafe && tg.initDataUnsafe.user) || {};
    return {
      user_id: u.id || 7271080503,
      user_name: [u.first_name, u.last_name].filter(Boolean).join(" ") || u.username || "Tomoshabin",
      username: u.username || "",
      photo_url: u.photo_url || ""
    };
  }

  // API yordamchisi
  async function api(endpoint, method = "GET", body = null) {
    const headers = { "Content-Type": "application/json" };
    if (inTg && tg.initData) {
      headers["X-Init-Data"] = tg.initData;
    }
    const profile = getUserProfile();
    let finalBody = body;
    if (body && method === "POST") {
      finalBody = Object.assign({}, profile, body);
    }
    const opts = { method, headers, cache: "no-store" };
    if (finalBody && method === "POST") {
      opts.body = JSON.stringify(finalBody);
    }
    try {
      const resp = await fetch(endpoint, opts);
      return await resp.json();
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }

  // HLS kutubxonasini yuklash
  function loadHls() {
    if (window.Hls) return Promise.resolve(window.Hls);
    if (hlsLibPromise) return hlsLibPromise;
    hlsLibPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/hls.js@1.5.13/dist/hls.min.js";
      script.onload = () => resolve(window.Hls);
      script.onerror = () => {
        hlsLibPromise = null;
        reject(new Error("Hls load error"));
      };
      document.head.appendChild(script);
    });
    return hlsLibPromise;
  }

  // Toast bildirishnoma
  function toast(msg, type = "info") {
    let t = $("tvr-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "tvr-toast";
      t.style.cssText = "position:fixed;top:60px;left:50%;transform:translateX(-50%);z-index:9999;background:rgba(22,17,46,0.92);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.15);color:#fff;padding:8px 16px;border-radius:999px;font-size:13px;font-weight:700;box-shadow:0 6px 20px rgba(0,0,0,0.5);pointer-events:none;transition:opacity .2s,transform .2s;";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = "1";
    t.style.transform = "translateX(-50%) translateY(0)";
    haptic(type === "err" ? "err" : "ok");
    clearTimeout(t._tm);
    t._tm = setTimeout(() => {
      t.style.opacity = "0";
      t.style.transform = "translateX(-50%) translateY(-10px)";
    }, 2400);
  }

  // DOM ni yaratish
  function ensureDOM() {
    if (rootEl) return;
    rootEl = document.createElement("section");
    rootEl.id = "tvroom";
    rootEl.className = "tvr";
    rootEl.hidden = true;
    document.body.appendChild(rootEl);
  }

  // Qo'llanma Modali
  function openGuideModal() {
    haptic();
    let m = $("tvr-guide-modal");
    if (!m) {
      m = document.createElement("div");
      m.id = "tvr-guide-modal";
      m.className = "tvr-modal";
      m.innerHTML = `
        <div class="tvr-sheet tvr-guide-sheet">
          <div class="tvr-sheet-head">
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-size:20px">ℹ️</span>
              <h3 style="margin:0;font-size:16px;font-weight:800">Tv Xona Qo'llanmasi</h3>
            </div>
            <button class="tvr-sheet-close" id="tvr-guide-close">✕</button>
          </div>
          <div class="tvr-guide-content">
            <div class="tvr-g-step">
              <div class="tvr-g-badge">1</div>
              <div class="tvr-g-body">
                <b>Tv Xona nima?</b>
                <p>Do'stlaringiz bilan birgalikda 4K telekanallarni bir vaqtda jonli tomosha qilish, ovozli suhbatlashish va fikr almashish xonasi.</p>
              </div>
            </div>
            <div class="tvr-g-step">
              <div class="tvr-g-badge">2</div>
              <div class="tvr-g-body">
                <b>Xona ochish yoki kirish</b>
                <p>«➕ Yangi Tv Xona Ochish» tugmasi orqali shaxsiy xonangizni oching yoki do'stingiz bergan 4-8 xonali kod orqali ulaning.</p>
              </div>
            </div>
            <div class="tvr-g-step">
              <div class="tvr-g-badge">3</div>
              <div class="tvr-g-body">
                <b>Do'stlarni chaqirish (Ulashish)</b>
                <p>Xona ichidagi <b>«✈️ Ulashish»</b> tugmasini bosing yoki xona kodi ustiga bosib nusxalang va Telegram orqali do'stlaringizga yuboring.</p>
              </div>
            </div>
            <div class="tvr-g-step">
              <div class="tvr-g-badge">4</div>
              <div class="tvr-g-body">
                <b>Sinxron TV efir va Kanallar</b>
                <p>Xona egasi (Host) kanalni o'zgartirsa, barcha a'zolarda efir bir vaqtda avtomatik sinxron almashadi.</p>
              </div>
            </div>
            <div class="tvr-g-step">
              <div class="tvr-g-badge">5</div>
              <div class="tvr-g-body">
                <b>Kristal Ovozli aloqa (Walkie-Talkie)</b>
                <p>Pastdagi <b>🎙 Mikrofon</b> tugmasi orqali shovqinsiz va aks-sadosiz jonli ovozli suhbatlashing hamda chatda fikr bildiring.</p>
              </div>
            </div>
            <button class="tvr-primary-btn" id="tvr-guide-ok" style="margin-top:14px;width:100%">
              Tushunarli, boshlash! ✨
            </button>
          </div>
        </div>
      `;
      document.body.appendChild(m);
      const closeGuide = () => { m.hidden = true; };
      m.querySelector("#tvr-guide-close").onclick = closeGuide;
      m.querySelector("#tvr-guide-ok").onclick = closeGuide;
      m.onclick = (e) => { if (e.target === m) closeGuide(); };
    }
    m.hidden = false;
  }

  // Boshqaruvchi / Lobby ko'rinishi
  function renderLobby() {
    ensureDOM();
    rootEl.innerHTML = `
      <div class="tvr-head">
        <div class="tvr-h-left">
          <button class="tvr-btn-back" id="tvr-back" data-act="homeback" aria-label="Orqaga">‹</button>
          <div class="tvr-h-info">
            <span class="tvr-h-title">📺 Tv Xona</span>
            <span class="tvr-h-sub">Do'stlar bilan tomosha partiyasi</span>
          </div>
        </div>
        <div class="tvr-h-right">
          <button class="tvr-btn-guide" id="tvr-btn-lobby-guide">ℹ️ Qo'llanma</button>
          <button class="zk-hubbtn" data-act="hub" aria-label="Barcha bo'limlar"><span>☰</span> Bo'limlar</button>
        </div>
      </div>

      <div class="tvr-lobby">
        <div class="tvr-lobby-hero">
          <div style="font-size:44px;margin-bottom:6px">📺✨</div>
          <h2>Do'stlar bilan TV ko'ring!</h2>
          <p>O'zingiz xona oching yoki do'stingiz bergan kod orqali kiring. Telekanal, chat va ovozli suhbat hamma uchun bir vaqtda sinxron ishlaydi.</p>
        </div>

        <button class="tvr-guide-card" id="tvr-guide-card">
          <div class="tvr-guide-card-icon">ℹ️</div>
          <div class="tvr-guide-card-text">
            <b>Tv Xona nima va qanday ishlatiladi?</b>
            <small>Do'stlar bilan TV ko'rish, taklif qilish va ovozli suhbat qo'llanmasi ›</small>
          </div>
        </button>

        <div class="tvr-action-card">
          <button class="tvr-primary-btn" id="tvr-btn-create">
            <span>➕</span> Yangi Tv Xona Ochish
          </button>

          <div style="display:flex;align-items:center;gap:10px;margin:4px 0">
            <div style="flex:1;height:1px;background:var(--tvr-border)"></div>
            <span style="font-size:12px;color:var(--tvr-sub);font-weight:700">YOKI KOD BILAN KIRISH</span>
            <div style="flex:1;height:1px;background:var(--tvr-border)"></div>
          </div>

          <div class="tvr-join-row">
            <input type="text" id="tvr-join-code" class="tvr-join-input" placeholder="Xona kodi (masalan: 1234)" maxlength="16">
            <button class="tvr-secondary-btn" id="tvr-btn-join">Kirish</button>
          </div>
        </div>

        <div class="tvr-public-title">
          <span>📋 Ommaviy Faol Xonalar</span>
          <span style="font-size:12px;color:var(--tvr-sub);font-weight:600">(${publicRooms.length} ta)</span>
        </div>

        <div class="tvr-rooms-grid" id="tvr-rooms-grid">
          ${renderPublicRoomsList()}
        </div>
      </div>
    `;

    bindLobbyEvents();
  }

  function renderPublicRoomsList() {
    if (!publicRooms || !publicRooms.length) {
      return `
        <div style="text-align:center;padding:24px 12px;color:var(--tvr-sub);background:var(--tvr-card);border-radius:16px;border:1px solid var(--tvr-border)">
          <div style="font-size:28px;margin-bottom:6px">🛋</div>
          <b>Hozircha ommaviy xonalar kam</b>
          <p style="font-size:12px;margin-top:4px">Birinchi bo'lib do'stlaringiz uchun yangi Tv Xona oching!</p>
        </div>
      `;
    }
    return publicRooms.map((r) => `
      <div class="tvr-room-item" data-code="${esc(r.id || r.code)}">
        <div class="tvr-r-info">
          <b class="tvr-r-name">${esc(r.name || "Tv Xona")}</b>
          <span class="tvr-r-ch">
            <span>${r.channel_logo || "📺"}</span>
            <span>${esc(r.channel_name || "TV")}</span>
            <span class="tvr-ch-quality">${esc(r.channel_q || "4K")}</span>
          </span>
        </div>
        <span class="tvr-r-users">👥 ${r.viewers_count || 1} kishi</span>
      </div>
    `).join("");
  }

  function bindLobbyEvents() {
    $("tvr-back").onclick = () => {
      haptic();
      close();
    };

    if ($("tvr-btn-lobby-guide")) $("tvr-btn-lobby-guide").onclick = openGuideModal;
    if ($("tvr-guide-card")) $("tvr-guide-card").onclick = openGuideModal;

    $("tvr-btn-create").onclick = async () => {
      haptic("ok");
      const name = inTg && tg.initDataUnsafe && tg.initDataUnsafe.user ? `${tg.initDataUnsafe.user.first_name}ning TV Xonasi` : "Do'stlar Tv Xonasi";
      const res = await api("api/tvroom/create", "POST", { name });
      if (res && res.ok && res.room) {
        currentRoom = res.room;
        renderRoom();
        startPolling();
        toast("Tv Xona ochildi! Do'stlaringizni taklif qiling 🎉", "ok");
      } else {
        toast("Xona ochishda xatolik yuz berdi", "err");
      }
    };

    $("tvr-btn-join").onclick = () => {
      const code = ($("tvr-join-code").value || "").trim();
      if (!code) {
        toast("Iltimos, xona kodini kiriting", "err");
        return;
      }
      join(code);
    };

    $("tvr-rooms-grid").onclick = (e) => {
      const item = e.target.closest("[data-code]");
      if (item) {
        join(item.dataset.code);
      }
    };
  }

  // Xonaga kirish
  async function join(code) {
    haptic();
    const res = await api("api/tvroom/join", "POST", { code });
    if (res && res.ok && res.room) {
      currentRoom = res.room;
      renderRoom();
      startPolling();
      toast(`Xonaga muvaffaqiyatli ulandingiz! (#${currentRoom.code})`, "ok");
    } else {
      toast(res.message || "Xona topilmadi", "err");
    }
  }

  // Xona ichki ko'rinishi (Watch Party Room)
  function renderRoom() {
    if (!currentRoom) return;
    ensureDOM();

    const ch = currentRoom.channel || {};
    const code = currentRoom.code || currentRoom.id.replace("tv_", "");
    const isHost = currentRoom.is_host;

    rootEl.innerHTML = `
      <div class="tvr-head">
        <div class="tvr-h-left">
          <button class="tvr-btn-back" id="tvr-leave" aria-label="Chiqish">‹</button>
          <div class="tvr-h-info">
            <span class="tvr-h-title">${esc(currentRoom.name)}</span>
            <span class="tvr-h-sub">
              <span class="tvr-badge-live"><i></i> JONLI</span>
              <span>· 👥 ${currentRoom.count || 1} kishi</span>
            </span>
          </div>
        </div>
        <div class="tvr-h-right">
          <button class="tvr-btn-guide-sm" id="tvr-btn-room-guide" title="Qo'llanma">ℹ️</button>
          <button class="tvr-room-pill" id="tvr-copy-code" title="Xona kodi">
            <span>🔑 #${esc(code)}</span>
          </button>
          <button class="tvr-btn-share" id="tvr-share">
            <span>✈️</span> Ulashish
          </button>
        </div>
      </div>

      <!-- TV Video Player (4K UHD) -->
      <div class="tvr-player-box" id="tvr-player-box">
        <video id="tvr-video" class="tvr-video" playsinline webkit-playsinline autoplay></video>

        <div class="tvr-loading" id="tvr-loading">
          <div class="tvr-spin"></div>
          <span id="tvr-load-text">4K UHD efir ulanmoqda…</span>
        </div>

        <div class="tvr-player-overlay" id="tvr-player-overlay">
          <div class="tvr-player-top">
            <div class="tvr-ch-info">
              ${ch.l ? `<img src="${esc(ch.l)}" class="tvr-ch-logo" alt="">` : `<span style="font-size:18px">${ch.logo || "📺"}</span>`}
              <span class="tvr-ch-name">${esc(ch.name || "Sevimli TV")}</span>
              <span class="tvr-ch-quality">${esc(ch.q || "4K UHD")}</span>
            </div>
            ${isHost ? `
              <button class="tvr-btn-chswitch" id="tvr-btn-chswitch">
                <span>🔄</span> Kanalni almashtirish
              </button>
            ` : `
              <button class="tvr-btn-chswitch" id="tvr-btn-chswitch" style="background:rgba(255,255,255,0.15)">
                <span>📋</span> Kanallar
              </button>
            `}
          </div>

          <div class="tvr-player-bottom">
            <div class="tvr-ctrl-group">
              <button class="tvr-pbtn" id="tvr-btn-play" aria-label="Play/Pause">⏸</button>
              <button class="tvr-pbtn" id="tvr-btn-mute" aria-label="Mute/Unmute">🔊</button>
            </div>
            <div class="tvr-ctrl-group">
              <button class="tvr-pbtn" id="tvr-btn-fs" aria-label="Fullscreen">⛶</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Tomoshabinlar qatori (Participants Strip) -->
      <div class="tvr-users-strip" id="tvr-users-strip">
        ${renderParticipantsStrip()}
      </div>

      <!-- Chat bo'limi -->
      <div class="tvr-chat-section">
        <div class="tvr-feed" id="tvr-feed">
          ${renderChatFeed()}
        </div>

        <!-- Tezkor Reaksiyalar -->
        <div class="tvr-quick-reacts">
          <button class="tvr-qbtn" data-r="🔥">🔥</button>
          <button class="tvr-qbtn" data-r="❤️">❤️</button>
          <button class="tvr-qbtn" data-r="😂">😂</button>
          <button class="tvr-qbtn" data-r="👏">👏</button>
          <button class="tvr-qbtn" data-r="🍿">🍿</button>
          <button class="tvr-qbtn" data-r="⚽">⚽</button>
          <button class="tvr-qbtn" data-r="🎉">🎉</button>
        </div>

        <!-- Xabar yozish va Ovoz boshqaruvi -->
        <div class="tvr-input-bar">
          <button class="tvr-mic-btn ${isMicActive ? "active" : ""}" id="tvr-mic-btn" title="Ovozli chatni yoqish / o'chirish">
            <span>${isMicActive ? "🎙" : "🎙"}</span>
          </button>

          <div class="tvr-inp-wrap">
            <input type="text" id="tvr-inp-msg" class="tvr-input" placeholder="Xabar yozing…" maxlength="300">
            <button class="tvr-send-btn" id="tvr-send-btn" aria-label="Yuborish">➤</button>
          </div>
        </div>
      </div>

      <!-- Kanal tanlash Modali (Drawer) -->
      <div class="tvr-modal" id="tvr-ch-modal" hidden>
        <div class="tvr-sheet">
          <div class="tvr-sheet-head">
            <h3>Telekanalni tanlang</h3>
            <button class="tvr-sheet-close" id="tvr-ch-close">✕</button>
          </div>
          <div class="tvr-sheet-search">
            <input type="text" id="tvr-ch-search" placeholder="Kanal nomini qidirish…">
          </div>
          <div class="tvr-sheet-list" id="tvr-ch-list">
            ${renderChannelsList()}
          </div>
        </div>
      </div>
    `;

    bindRoomEvents();
    initVideoPlayer();
  }

  function renderParticipantsStrip() {
    if (!currentRoom || !currentRoom.participants) return "";
    const pList = currentRoom.participants;
    const items = pList.map((p) => {
      const isHost = (p.role === "host") || (p.user_id === currentRoom.host_id);
      const isSpeaking = p.speaking || false;
      const isMic = p.mic_active || false;
      const initial = (p.name || p.username || "U")[0].toUpperCase();
      const displayName = p.name || (p.username ? "@" + p.username : "Tomoshabin");
      const handle = p.username ? "@" + p.username : (isHost ? "Boshqaruvchi" : "Tomoshabin");
      return `
        <div class="tvr-user-card ${isHost ? "host" : ""} ${isSpeaking ? "speaking" : ""}" data-uid="${p.user_id}" title="${esc(displayName)} (${esc(handle)})">
          <div class="tvr-av-wrap">
            ${p.photo_url ? `<img src="${esc(p.photo_url)}" class="tvr-av-img" alt="" onerror="this.style.display='none';if(this.nextElementSibling)this.nextElementSibling.style.display='flex'">` : ""}
            <span class="tvr-av-placeholder" style="${p.photo_url ? 'display:none' : ''}">${esc(initial)}</span>
            ${isHost ? `<span class="tvr-crown">👑</span>` : ""}
            <span class="tvr-mic-badge ${isMic ? "active" : ""}">${isMic ? "🎙" : "🔇"}</span>
          </div>
          <span class="tvr-u-name">${esc(displayName)}</span>
          <span class="tvr-u-handle">${esc(handle)}</span>
        </div>
      `;
    }).join("");

    return `
      <div class="tvr-add-friend" id="tvr-btn-invite" title="Do'stni taklif qilish">
        <span>+</span>
      </div>
      ${items}
    `;
  }

  function renderChatFeed() {
    if (!currentRoom || !currentRoom.chat || !currentRoom.chat.length) {
      return `
        <div class="tvr-msg system">
          <div class="tvr-msg-bubble">
            👋 Tv Xonaga xush kelibsiz! Do'stlaringiz bilan qiziqarli lahzalarni birga tomosha qiling.
          </div>
        </div>
      `;
    }

    const myId = inTg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

    return currentRoom.chat.map((m) => {
      if (m.system) {
        return `
          <div class="tvr-msg system">
            <div class="tvr-msg-bubble">${esc(m.text)}</div>
          </div>
        `;
      }
      const isMine = myId && (m.user_id === myId);
      const initial = (m.name || "U")[0].toUpperCase();
      return `
        <div class="tvr-msg ${isMine ? "mine" : ""}">
          ${m.photo_url ? `<img src="${esc(m.photo_url)}" class="tvr-msg-av" alt="">` : `<span class="tvr-msg-av">${esc(initial)}</span>`}
          <div class="tvr-msg-bubble">
            <div class="tvr-msg-sender">${esc(m.username ? "@" + m.username : m.name)}</div>
            ${m.reaction ? `<div class="tvr-msg-reaction">${esc(m.reaction)}</div>` : ""}
            ${m.text ? `<div class="tvr-msg-text">${esc(m.text)}</div>` : ""}
          </div>
        </div>
      `;
    }).join("");
  }

  function renderChannelsList(query = "") {
    if (!allChannels || !allChannels.length) return `<div style="text-align:center;padding:20px;color:var(--tvr-sub)">Kanallar yuklanmoqda…</div>`;
    const q = query.toLowerCase().trim();
    const list = q ? allChannels.filter((c) => (c.name || "").toLowerCase().includes(q) || (c.category || "").toLowerCase().includes(q)) : allChannels;
    const curId = currentRoom && currentRoom.channel ? currentRoom.channel.id : 0;

    return list.map((c) => {
      const isCur = (c.id === curId);
      return `
        <div class="tvr-ch-item ${isCur ? "active" : ""}" data-chid="${c.id}">
          <div class="tvr-ch-item-left">
            ${c.l ? `<img src="${esc(c.l)}" class="tvr-ch-item-logo" alt="">` : `<span style="font-size:20px;margin-right:4px">${c.logo || "📺"}</span>`}
            <div class="tvr-ch-item-meta">
              <span class="tvr-ch-item-name">${esc(c.name)}</span>
              <span class="tvr-ch-item-desc">${esc(c.desc || c.category || "Jonli efir")}</span>
            </div>
          </div>
          <span class="tvr-ch-item-badge">${esc(c.q || "4K UHD")}</span>
        </div>
      `;
    }).join("");
  }

  // Video Pleyerni ishga tushirish (HLS / m3u8)
  async function initVideoPlayer() {
    const video = $("tvr-video");
    const loader = $("tvr-loading");
    if (!video || !currentRoom || !currentRoom.channel) return;

    const streamUrl = currentRoom.channel.stream;
    if (!streamUrl) return;

    const backups = Array.isArray(currentRoom.channel.backups) ? currentRoom.channel.backups : [];
    let backupIdx = 0;

    if (loader) loader.hidden = false;

    // Avvalgi HLS obyektini tozalash
    if (hlsInstance) {
      try { hlsInstance.destroy(); } catch (e) {}
      hlsInstance = null;
    }

    const onPlayReady = () => {
      if (loader) loader.hidden = true;
      video.play().catch(() => {});
    };

    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari / iOS Native HLS
      video.src = streamUrl;
      video.addEventListener("loadedmetadata", onPlayReady, { once: true });
    } else {
      try {
        const HlsClass = await loadHls();
        if (HlsClass && HlsClass.isSupported()) {
          hlsInstance = new HlsClass({
            enableWorker: true,
            lowLatencyMode: true,
            backBufferLength: 30,
            maxBufferLength: 30,
            maxMaxBufferLength: 60,
            liveSyncDurationCount: 3,
            liveMaxLatencyDurationCount: 5,
          });
          hlsInstance.loadSource(streamUrl);
          hlsInstance.attachMedia(video);
          hlsInstance.on(HlsClass.Events.MANIFEST_PARSED, onPlayReady);
          hlsInstance.on(HlsClass.Events.ERROR, (event, data) => {
            if (data.fatal) {
              if (backupIdx < backups.length) {
                const nextUrl = backups[backupIdx++];
                hlsInstance.loadSource(nextUrl);
                hlsInstance.startLoad();
              } else {
                if (loader) loader.hidden = false;
                $("tvr-load-text").textContent = "Qayta ulanmoqda…";
                setTimeout(() => {
                  if (hlsInstance) hlsInstance.startLoad();
                }, 2000);
              }
            }
          });
        } else {
          video.src = streamUrl;
          video.addEventListener("loadedmetadata", onPlayReady, { once: true });
        }
      } catch (err) {
        video.src = streamUrl;
      }
    }
  }

  // Xona hodisalarini ulash
  function bindRoomEvents() {
    if ($("tvr-btn-room-guide")) $("tvr-btn-room-guide").onclick = openGuideModal;

    // Chiqish
    $("tvr-leave").onclick = async () => {
      haptic();
      await api("api/tvroom/leave", "POST", { room: currentRoom.id });
      stopPolling();
      stopMic();
      closeAllPeers();
      currentRoom = null;
      renderLobby();
      loadHomeData();
    };

    // Kodni nusxalash
    $("tvr-copy-code").onclick = () => {
      haptic("ok");
      const code = currentRoom.code || currentRoom.id.replace("tv_", "");
      try {
        navigator.clipboard.writeText(code).then(() => {
          toast(`Kopiya olindi: #${code}`, "ok");
        });
      } catch (e) {
        toast(`Xona kodi: #${code}`, "ok");
      }
    };

    // Do'stni chaqirish / Ulashish
    const shareAction = () => {
      haptic("ok");
      const code = currentRoom.code || currentRoom.id.replace("tv_", "");
      const botName = (window.BOT_USERNAME || "Bauntyfilmsbot").replace("@", "");
      const appLink = `https://t.me/${botName}?startapp=tvroom_${code}`;
      const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(appLink)}&text=${encodeURIComponent("📺 Do'stlarim, Bauntys Tv Xonada birga Zo'r TV 4K tomosha qilamiz! Kirish uchun bosing 👇")}`;
      try {
        if (inTg && tg.openTelegramLink) {
          tg.openTelegramLink(shareUrl);
        } else {
          window.open(shareUrl, "_blank");
        }
      } catch (e) {
        location.href = shareUrl;
      }
    };
    $("tvr-share").onclick = shareAction;
    if ($("tvr-btn-invite")) $("tvr-btn-invite").onclick = shareAction;

    // Kanal almashtirish modali
    $("tvr-btn-chswitch").onclick = () => {
      haptic();
      isChannelModalOpen = true;
      $("tvr-ch-modal").hidden = false;
      $("tvr-ch-list").innerHTML = renderChannelsList();
    };

    $("tvr-ch-close").onclick = () => {
      haptic();
      isChannelModalOpen = false;
      $("tvr-ch-modal").hidden = true;
    };

    $("tvr-ch-search").oninput = (e) => {
      $("tvr-ch-list").innerHTML = renderChannelsList(e.target.value);
    };

    $("tvr-ch-list").onclick = async (e) => {
      const item = e.target.closest("[data-chid]");
      if (!item) return;
      const chId = +item.dataset.chid;
      haptic("ok");
      isChannelModalOpen = false;
      $("tvr-ch-modal").hidden = true;

      // Agar host bo'lsa butun xonaga sinxronlash
      const res = await api("api/tvroom/channel", "POST", { room: currentRoom.id, channel_id: chId });
      if (res && res.ok && res.channel) {
        currentRoom.channel = res.channel;
        initVideoPlayer();
        toast(`Kanal o'zgartirildi: ${res.channel.name}`, "ok");
      } else {
        toast(res.message || "Faqat xona boshqaruvchisi kanalni o'zgartirishi mumkin", "err");
      }
    };

    // Video boshqaruvi
    const video = $("tvr-video");
    $("tvr-btn-play").onclick = () => {
      haptic();
      if (video.paused) {
        video.play();
        $("tvr-btn-play").textContent = "⏸";
      } else {
        video.pause();
        $("tvr-btn-play").textContent = "▶";
      }
    };

    $("tvr-btn-mute").onclick = () => {
      haptic();
      video.muted = !video.muted;
      $("tvr-btn-mute").textContent = video.muted ? "🔇" : "🔊";
    };

    $("tvr-btn-fs").onclick = () => {
      haptic();
      const box = $("tvr-player-box");
      if (!document.fullscreenElement) {
        if (box.requestFullscreen) box.requestFullscreen();
        else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
      } else {
        if (document.exitFullscreen) document.exitFullscreen();
      }
    };

    // Chat xabar yuborish
    const sendChatAction = async () => {
      const inp = $("tvr-inp-msg");
      const text = (inp.value || "").trim();
      if (!text) return;
      inp.value = "";
      haptic();
      const res = await api("api/tvroom/chat", "POST", { room: currentRoom.id, text });
      if (res && res.ok && res.message) {
        lastMsgId = res.message.id;
        if (!currentRoom.chat) currentRoom.chat = [];
        currentRoom.chat.push(res.message);
        $("tvr-feed").innerHTML = renderChatFeed();
        scrollChatToBottom();
      }
    };

    $("tvr-send-btn").onclick = sendChatAction;
    $("tvr-inp-msg").onkeydown = (e) => {
      if (e.key === "Enter") sendChatAction();
    };

    // Tezkor Reaksiyalar
    rootEl.querySelectorAll(".tvr-qbtn").forEach((btn) => {
      btn.onclick = async () => {
        const reaction = btn.dataset.r;
        haptic("ok");
        const res = await api("api/tvroom/chat", "POST", { room: currentRoom.id, reaction });
        if (res && res.ok && res.message) {
          lastMsgId = res.message.id;
          if (!currentRoom.chat) currentRoom.chat = [];
          currentRoom.chat.push(res.message);
          $("tvr-feed").innerHTML = renderChatFeed();
          scrollChatToBottom();
        }
      };
    });

    // Ovoz / Mikrofon toggle
    $("tvr-mic-btn").onclick = () => {
      toggleMic();
    };
  }

  function scrollChatToBottom() {
    const feed = $("tvr-feed");
    if (feed) {
      feed.scrollTop = feed.scrollHeight;
    }
  }

  // WebRTC Mesh Helper Functions
  function getOrCreatePeerConnection(targetUid) {
    if (peerConnections[targetUid]) {
      return peerConnections[targetUid];
    }
    const PeerClass = window.RTCPeerConnection || window.webkitRTCPeerConnection;
    if (!PeerClass) return null;

    try {
      const pc = new PeerClass(rtcConfig);
      peerConnections[targetUid] = pc;

      // Attach local audio track if mic is active
      if (localAudioStream) {
        localAudioStream.getAudioTracks().forEach((track) => {
          try { pc.addTrack(track, localAudioStream); } catch (e) {}
        });
      }

      // ICE candidates forwarding
      pc.onicecandidate = (event) => {
        if (event.candidate && currentRoom) {
          api("api/tvroom/signal", "POST", {
            room: currentRoom.id,
            to: targetUid,
            type: "candidate",
            data: event.candidate,
          });
        }
      };

      // Remote incoming audio stream playback
      pc.ontrack = (event) => {
        let audio = remoteAudios[targetUid];
        if (!audio) {
          audio = document.createElement("audio");
          audio.autoplay = true;
          audio.playsInline = true;
          audio.setAttribute("data-peer", targetUid);
          audio.style.display = "none";
          document.body.appendChild(audio);
          remoteAudios[targetUid] = audio;
        }
        if (event.streams && event.streams[0]) {
          audio.srcObject = event.streams[0];
        } else if (event.track) {
          audio.srcObject = new MediaStream([event.track]);
        }
        audio.play().catch(() => {});
      };

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "failed" || pc.connectionState === "closed") {
          closePeerConnection(targetUid);
        }
      };

      return pc;
    } catch (e) {
      return null;
    }
  }

  function closePeerConnection(uid) {
    const pc = peerConnections[uid];
    if (pc) {
      try { pc.close(); } catch (e) {}
      delete peerConnections[uid];
    }
    const audio = remoteAudios[uid];
    if (audio) {
      try {
        audio.pause();
        audio.srcObject = null;
        audio.remove();
      } catch (e) {}
      delete remoteAudios[uid];
    }
  }

  function closeAllPeers() {
    Object.keys(peerConnections).forEach((uid) => closePeerConnection(uid));
  }

  async function initiateCallsToParticipants() {
    if (!currentRoom || !currentRoom.participants || !localAudioStream) return;
    const myProfile = getUserProfile();
    for (const p of currentRoom.participants) {
      if (p.user_id !== myProfile.user_id) {
        try {
          const pc = getOrCreatePeerConnection(p.user_id);
          if (pc) {
            const offer = await pc.createOffer({ offerToReceiveAudio: true });
            await pc.setLocalDescription(offer);
            api("api/tvroom/signal", "POST", {
              room: currentRoom.id,
              to: p.user_id,
              type: "offer",
              data: offer,
            });
          }
        } catch (e) {}
      }
    }
  }

  async function handleIncomingSignal(sig) {
    if (!sig || !sig.from || !currentRoom) return;
    const fromUid = sig.from;
    const type = sig.type;
    const data = sig.data;

    if (type === "offer" && data) {
      try {
        const pc = getOrCreatePeerConnection(fromUid);
        if (pc) {
          await pc.setRemoteDescription(new RTCSessionDescription(data));
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          api("api/tvroom/signal", "POST", {
            room: currentRoom.id,
            to: fromUid,
            type: "answer",
            data: answer,
          });
        }
      } catch (e) {}
    } else if (type === "answer" && data) {
      try {
        const pc = peerConnections[fromUid];
        if (pc) {
          await pc.setRemoteDescription(new RTCSessionDescription(data));
        }
      } catch (e) {}
    } else if (type === "candidate" && data) {
      try {
        const pc = peerConnections[fromUid];
        if (pc) {
          await pc.addIceCandidate(new RTCIceCandidate(data));
        }
      } catch (e) {}
    } else if (type === "mic_state") {
      const active = data && (data.active !== undefined ? data.active : data);
      const card = rootEl ? rootEl.querySelector(`.tvr-user-card[data-uid="${fromUid}"]`) : null;
      if (card) {
        const badge = card.querySelector(".tvr-mic-badge");
        if (badge) {
          badge.classList.toggle("active", !!active);
          badge.textContent = active ? "🎙" : "🔇";
        }
      }
    } else if (type === "speaking") {
      const speaking = data && !!data.speaking;
      const card = rootEl ? rootEl.querySelector(`.tvr-user-card[data-uid="${fromUid}"]`) : null;
      if (card) {
        card.classList.toggle("speaking", speaking);
      }
    }
  }

  async function pollSignals() {
    if (!isOpen || !currentRoom) return;
    const profile = getUserProfile();
    const res = await api(`api/tvroom/signal?room=${encodeURIComponent(currentRoom.id)}&since=${lastSignalTs}&user_id=${profile.user_id}`);
    if (res && res.ok && Array.isArray(res.signals)) {
      for (const sig of res.signals) {
        if (sig.ts > lastSignalTs) lastSignalTs = sig.ts;
        await handleIncomingSignal(sig);
      }
    }
  }

  // 🎙 WebRTC / Audio capture with echoCancellation & noiseSuppression
  async function toggleMic() {
    if (isMicActive) {
      stopMic();
      toast("Mikrofon o'chirildi", "info");
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      toast("Ushbu qurilmada mikrofon qo'llab-quvvatlanmaydi", "err");
      return;
    }

    try {
      // Audio constraints: Echo cancellation, Noise suppression va Auto gain control
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
          sampleRate: 48000,
        },
        video: false,
      });

      localAudioStream = stream;
      isMicActive = true;
      haptic("ok");

      const btn = $("tvr-mic-btn");
      if (btn) btn.classList.add("active");

      // Signal yuborish
      if (currentRoom) {
        api("api/tvroom/signal", "POST", {
          room: currentRoom.id,
          type: "mic_state",
          data: { active: true, speaking: false },
        });
      }

      // Xonadagi barcha boshqa a'zolar bilan WebRTC P2P qo'ng'irog'ini o'rnatish
      initiateCallsToParticipants();

      // Ovoz balandligini aniqlash (speaking detector)
      setupSpeakingDetector(stream);
      toast("Ovozli suhbat faol! (Shovqinsiz & aks-sadosiz)", "ok");
    } catch (err) {
      isMicActive = false;
      const btn = $("tvr-mic-btn");
      if (btn) btn.classList.remove("active");
      toast("Mikrofonga ruxsat berilmadi", "err");
    }
  }

  function setupSpeakingDetector(stream) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      audioContext = new AudioCtx();
      const source = audioContext.createMediaStreamSource(stream);
      analyserNode = audioContext.createAnalyser();
      analyserNode.fftSize = 256;
      source.connect(analyserNode);

      const bufferLength = analyserNode.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const checkVolume = () => {
        if (!isMicActive) return;
        analyserNode.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const avg = sum / bufferLength;
        const nowSpeaking = avg > 28;

        if (nowSpeaking !== isSpeaking) {
          isSpeaking = nowSpeaking;
          if (currentRoom) {
            api("api/tvroom/signal", "POST", {
              room: currentRoom.id,
              type: "speaking",
              data: { speaking: isSpeaking },
            });
          }
        }
        audioAnimFrame = requestAnimationFrame(checkVolume);
      };
      checkVolume();
    } catch (e) {}
  }

  function stopMic() {
    isMicActive = false;
    isSpeaking = false;
    if (audioAnimFrame) cancelAnimationFrame(audioAnimFrame);
    if (localAudioStream) {
      localAudioStream.getTracks().forEach((tr) => tr.stop());
      localAudioStream = null;
    }
    if (audioContext) {
      try { audioContext.close(); } catch (e) {}
      audioContext = null;
    }
    closeAllPeers();
    const btn = $("tvr-mic-btn");
    if (btn) btn.classList.remove("active");

    if (currentRoom) {
      api("api/tvroom/signal", "POST", {
        room: currentRoom.id,
        type: "mic_state",
        data: { active: false, speaking: false },
      });
    }
  }

  // Real-time Polling & Sinxronizatsiya
  function startPolling() {
    stopPolling();
    pollTimer = setInterval(async () => {
      if (!isOpen || !currentRoom) return;

      const profile = getUserProfile();
      const res = await api(`api/tvroom/state?room=${encodeURIComponent(currentRoom.id)}&user_id=${profile.user_id}`);
      if (res && res.ok && res.room) {
        const nextRoom = res.room;
        // Kanal o'zgargan bo'lsa sinxron yangilash
        if (currentRoom.channel && nextRoom.channel && (currentRoom.channel.id !== nextRoom.channel.id || currentRoom.channel.stream !== nextRoom.channel.stream)) {
          currentRoom.channel = nextRoom.channel;
          initVideoPlayer();
          const ch = nextRoom.channel;
          const nameEl = rootEl.querySelector(".tvr-ch-name");
          if (nameEl) nameEl.textContent = ch.name || "TV";
          toast(`Kanal yangilandi: ${ch.name}`, "info");
        }

        // Qatnashuvchilar o'zgargan bo'lsa
        const prevCount = currentRoom.count || 0;
        currentRoom.participants = nextRoom.participants;
        currentRoom.count = nextRoom.count;
        currentRoom.host_id = nextRoom.host_id;
        const strip = $("tvr-users-strip");
        if (strip) {
          strip.innerHTML = renderParticipantsStrip();
          if ($("tvr-btn-invite")) {
            $("tvr-btn-invite").onclick = () => {
              const code = currentRoom.code || currentRoom.id.replace("tv_", "");
              const botName = (window.BOT_USERNAME || "Bauntyfilmsbot").replace("@", "");
              const appLink = `https://t.me/${botName}?startapp=tvroom_${code}`;
              const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(appLink)}&text=${encodeURIComponent("📺 Do'stlarim, Bauntys Tv Xonada birga Zo'r TV 4K tomosha qilamiz!")}`;
              if (inTg && tg.openTelegramLink) tg.openTelegramLink(shareUrl);
              else window.open(shareUrl, "_blank");
            };
          }
        }

        // Agar yangi qatnashuvchi qo'shilgan bo'lsa va mikrofon yoqiq bo'lsa
        if (isMicActive && currentRoom.count > prevCount) {
          initiateCallsToParticipants();
        }

        // Yangi chat xabarlari kelgan bo'lsa
        if (nextRoom.chat && nextRoom.chat.length) {
          const lastNewId = nextRoom.chat[nextRoom.chat.length - 1].id;
          if (lastNewId !== lastMsgId) {
            lastMsgId = lastNewId;
            currentRoom.chat = nextRoom.chat;
            const feed = $("tvr-feed");
            if (feed) {
              const isAtBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 70;
              feed.innerHTML = renderChatFeed();
              if (isAtBottom) scrollChatToBottom();
            }
          }
        }
      }

      // WebRTC signalizatsiyasini tekshirish
      await pollSignals();
    }, 1600);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // Boshlang'ich ma'lumotlarni yuklash (Kanallar & Ommaviy xonalar)
  async function loadHomeData() {
    const res = await api("api/tvroom");
    if (res && res.ok) {
      publicRooms = res.rooms || [];
      allChannels = res.channels || [];
      if (!currentRoom && isOpen) {
        const grid = $("tvr-rooms-grid");
        if (grid) grid.innerHTML = renderPublicRoomsList();
      }
    }
  }

  // Tashqi modul interfeysi
  function open(roomCode = "") {
    isOpen = true;
    document.body.classList.add("tvr-on");
    ensureDOM();
    rootEl.hidden = false;

    if (inTg && tg.BackButton) {
      tg.BackButton.show();
      tg.BackButton.onClick(() => {
        if (currentRoom) {
          api("api/tvroom/leave", "POST", { room: currentRoom.id });
          stopPolling();
          stopMic();
          currentRoom = null;
          renderLobby();
        } else {
          close();
        }
      });
    }

    if (roomCode) {
      join(roomCode);
    } else {
      renderLobby();
      loadHomeData();
    }
  }

  function close() {
    isOpen = false;
    stopPolling();
    stopMic();
    closeAllPeers();
    if (hlsInstance) {
      try { hlsInstance.destroy(); } catch (e) {}
      hlsInstance = null;
    }
    const video = $("tvr-video");
    if (video) {
      video.pause();
      video.removeAttribute("src");
    }
    if (rootEl) rootEl.hidden = true;
    document.body.classList.remove("tvr-on");
    currentRoom = null;

    if (inTg && tg.BackButton) {
      if (window.ZK_canHideBack && window.ZK_canHideBack()) {
        tg.BackButton.hide();
      }
    }
    if (window.ZK_setMode) {
      window.ZK_setMode("kino");
    }
  }

  function busy() {
    return isOpen && !!currentRoom;
  }

  window.ZTvRoom = {
    open,
    close,
    busy,
    join,
    create: (name) => api("api/tvroom/create", "POST", { name }),
    toggleMic,
    isOpen: () => isOpen,
  };
})();
