/**
 * Bauntyfilms Mini App Asosiy Dasturi
 * Telegram WebApp integratsiyasi, multimedia pleyerlar va API aloqasi
 */

const App = {
    tg: window.Telegram?.WebApp || null,
    userId: null,
    currentTab: 'movies',
    movies: [],
    musicTracks: [],
    currentTrackIndex: 0,
    isPlaying: false,
    audioElement: new Audio(),
    hls: null,

    init() {
        // Telegram WebApp sozlamalari
        if (this.tg) {
            this.tg.ready();
            this.tg.expand();
            if (this.tg.initDataUnsafe?.user?.id) {
                this.userId = this.tg.initDataUnsafe.user.id;
            }
        }
        if (!this.userId) {
            this.userId = 123456789; // Fallback / Local test ID
        }

        this.bindEvents();
        this.loadMovies();
        this.loadMusic();
        this.loadTV();
        this.loadGames();
    },

    bindEvents() {
        // Tab switching
        document.querySelectorAll('.nav-tab-item').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                const target = tab.getAttribute('data-target');
                this.switchTab(target);
            });
        });

        // Search inputs
        const searchInput = document.getElementById('main-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const val = e.target.value.trim();
                const clearBtn = document.getElementById('search-clear-btn');
                if (clearBtn) clearBtn.style.display = val ? 'block' : 'none';
                this.handleSearch(val);
            });
        }

        const clearBtn = document.getElementById('search-clear-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                const input = document.getElementById('main-search-input');
                if (input) {
                    input.value = '';
                    clearBtn.style.display = 'none';
                    this.handleSearch('');
                }
            });
        }

        // Audio element events
        this.audioElement.addEventListener('timeupdate', () => {
            const fill = document.getElementById('player-progress-fill');
            if (fill && this.audioElement.duration) {
                const pct = (this.audioElement.currentTime / this.audioElement.duration) * 100;
                fill.style.width = `${pct}%`;
            }
        });

        this.audioElement.addEventListener('ended', () => {
            this.playNextTrack();
        });
    },

    switchTab(tabId) {
        window.soundEngine?.playClick();
        this.currentTab = tabId;

        document.querySelectorAll('.nav-tab-item').forEach(t => t.classList.remove('active'));
        const activeNav = document.querySelector(`.nav-tab-item[data-target="${tabId}"]`);
        if (activeNav) activeNav.classList.add('active');

        document.querySelectorAll('.app-section').forEach(s => s.classList.remove('active'));
        const activeSec = document.getElementById(`section-${tabId}`);
        if (activeSec) activeSec.classList.add('active');

        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    handleSearch(query) {
        if (this.currentTab === 'movies') {
            this.loadMovies(query);
        } else if (this.currentTab === 'music') {
            this.loadMusic(query);
        } else if (this.currentTab === 'tv') {
            this.loadTV(query);
        } else if (this.currentTab === 'games') {
            this.loadGames(query);
        }
    },

    // ==========================================
    // 1. KINOLAR BO'LIMI
    // ==========================================
    async loadMovies(query = '', genre = 'Barchasi') {
        const container = document.getElementById('movies-grid');
        if (!container) return;
        container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #94a3b8;"><i class="fas fa-spinner fa-spin fa-2x"></i><p style="margin-top: 10px;">Kinolar yuklanmoqda...</p></div>`;

        try {
            let url = `/api/movies?limit=60`;
            if (query) url += `&q=${encodeURIComponent(query)}`;
            if (genre && genre !== 'Barchasi') url += `&genre=${encodeURIComponent(genre)}`;

            const res = await fetch(url);
            const data = await res.json();
            this.movies = data.items || [];

            if (this.movies.length === 0) {
                container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #94a3b8;"><p style="font-size: 36px;">🎬</p><p>Kechirasiz, kinolar topilmadi.</p></div>`;
                return;
            }

            container.innerHTML = this.movies.map(m => `
                <div class="movie-card" onclick="App.openMovieDetail('${m.code}')">
                    <div class="movie-poster-box">
                        <div class="movie-poster-fallback">
                            <span>🎬</span>
                            <span style="font-size: 11px; margin-top: 6px; color: #94a3b8;">${m.year || ''}</span>
                        </div>
                        <div class="movie-badge-code">№ ${m.code}</div>
                        <div class="movie-badge-rating">⭐ ${m.rating || '7.5'}</div>
                    </div>
                    <div class="movie-info">
                        <div class="movie-title">${m.title}</div>
                        <div class="movie-meta">
                            <span>${m.genres?.split(',')[0] || 'Kino'}</span>
                            <span>${m.views_count ? m.views_count.toLocaleString() : '10k'} 👁️</span>
                        </div>
                    </div>
                </div>
            `).join('');

        } catch (err) {
            console.error('Kinolar yuklashda xatolik:', err);
            container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #ef4444;"><p>Yuklashda xatolik yuz berdi</p></div>`;
        }
    },

    filterGenre(genre, btn) {
        window.soundEngine?.playClick();
        document.querySelectorAll('#genres-container .filter-chip').forEach(c => c.classList.remove('active'));
        if (btn) btn.classList.add('active');
        this.loadMovies('', genre);
    },

    openMovieDetail(code) {
        window.soundEngine?.playClick();
        const movie = this.movies.find(m => m.code === code);
        if (!movie) return;

        const modal = document.getElementById('movie-modal');
        const content = document.getElementById('movie-modal-body');

        content.innerHTML = `
            <div style="text-align: center; margin-bottom: 16px;">
                <div style="font-size: 48px; margin-bottom: 8px;">🎬</div>
                <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 6px;">${movie.title}</h2>
                <div style="display: flex; justify-content: center; gap: 8px; font-size: 12px; color: #94a3b8;">
                    <span style="background: rgba(59,130,246,0.15); color: #60a5fa; padding: 2px 8px; border-radius: 4px;">Kodi: ${movie.code}</span>
                    <span>📅 ${movie.year || 'Noma\'lum'}</span>
                    <span>⭐ ${movie.rating || '7.5'}/10</span>
                    <span>⏱️ ${movie.duration ? movie.duration + ' daqiqa' : 'To\'liq'}</span>
                </div>
            </div>
            <div style="background: rgba(30,41,59,0.5); padding: 12px; border-radius: 12px; margin-bottom: 16px;">
                <p style="font-size: 13.5px; line-height: 1.5; color: #cbd5e1;">${movie.description || 'Sara film. Bot orqali to\'liq HD formatda tomosha qilishingiz mumkin.'}</p>
            </div>
            <div style="display: flex; flex-direction: column; gap: 10px;">
                <button class="btn-primary-action" style="padding: 14px; font-size: 15px;" onclick="App.sendMovieToChat('${movie.code}')">
                    ▶️ Tomosha qilish (Chatga yuborish)
                </button>
                <button class="btn-secondary-action" onclick="App.closeModal('movie-modal')">
                    Yopish
                </button>
            </div>
        `;

        modal.classList.add('active');
    },

    async sendMovieToChat(code) {
        window.soundEngine?.playCoin();
        const tgUser = this.tg?.initDataUnsafe?.user?.id;
        const targetBot = "Bauntyfilmsbot";
        if (!tgUser) {
            const targetUrl = `https://t.me/${targetBot}?start=m_${code}`;
            if (this.tg?.openTelegramLink) {
                this.tg.openTelegramLink(targetUrl);
            } else {
                window.open(targetUrl, "_blank");
            }
            return;
        }
        try {
            const res = await fetch('/api/send_to_chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Init-Data': this.tg?.initData || ''
                },
                body: JSON.stringify({ user_id: tgUser, type: 'movie', code: code })
            });
            const data = await res.json();
            if (data.success) {
                alert(`🎉 Film Telegram chatga yuborildi!`);
                this.closeModal('movie-modal');
                if (this.tg?.close) {
                    // Ixtiyoriy: mini appni yopib chatga qaytish
                }
            } else {
                const targetUrl = `https://t.me/${targetBot}?start=m_${code}`;
                if (confirm((data.error || 'Yuborishda xatolik') + "\nBot chatini ochishni xohlaysizmi?")) {
                    if (this.tg?.openTelegramLink) this.tg.openTelegramLink(targetUrl);
                    else window.open(targetUrl, "_blank");
                }
            }
        } catch (e) {
            alert('Server bilan bog\'lanishda xatolik');
        }
    },

    // ==========================================
    // 2. MUSIQA BO'LIMI
    // ==========================================
    async loadMusic(query = '', category = 'top50', mood = 'all') {
        const container = document.getElementById('music-tracks-list');
        if (!container) return;

        try {
            let url = `/api/music?category=${category}&mood=${mood}`;
            if (query) url += `&q=${encodeURIComponent(query)}`;

            const res = await fetch(url);
            const data = await res.json();
            this.musicTracks = data.items || [];

            container.innerHTML = this.musicTracks.map((t, idx) => `
                <div class="track-item ${this.currentTrackIndex === idx && this.isPlaying ? 'playing' : ''}" onclick="App.playTrack(${idx})">
                    <img src="${t.cover}" class="track-cover" alt="cover">
                    <div class="track-details">
                        <div class="track-title">${t.title}</div>
                        <div class="track-artist">${t.artist}</div>
                    </div>
                    <div class="track-actions" onclick="event.stopPropagation()">
                        <span style="font-size: 12px; color: #94a3b8;">${t.duration}</span>
                        <button class="btn-send-tg" onclick="App.sendMusicToChat('${t.title}', '${t.artist}')">📤 Chat</button>
                    </div>
                </div>
            `).join('');

        } catch (err) {
            console.error('Musiqa yuklashda xatolik:', err);
        }
    },

    filterMusicMood(mood, btn) {
        window.soundEngine?.playClick();
        document.querySelectorAll('#moods-container .filter-chip').forEach(c => c.classList.remove('active'));
        if (btn) btn.classList.add('active');
        this.loadMusic('', 'top50', mood);
    },

    playTrack(index) {
        window.soundEngine?.playClick();
        const track = this.musicTracks[index];
        if (!track) return;

        this.currentTrackIndex = index;
        this.audioElement.src = track.url;
        this.audioElement.play().catch(e => console.log('Audio autoplay blocked:', e));
        this.isPlaying = true;

        const player = document.getElementById('sticky-audio-player');
        if (player) player.classList.add('visible');

        const titleEl = document.getElementById('player-title');
        const artistEl = document.getElementById('player-artist');
        const coverEl = document.getElementById('player-cover');
        const playBtn = document.getElementById('player-btn-play');

        if (titleEl) titleEl.innerText = track.title;
        if (artistEl) artistEl.innerText = track.artist;
        if (coverEl) coverEl.src = track.cover;
        if (playBtn) playBtn.innerHTML = '<i class="fas fa-pause"></i>';

        document.querySelectorAll('.track-item').forEach((item, idx) => {
            if (idx === index) item.classList.add('playing');
            else item.classList.remove('playing');
        });
    },

    togglePlayPause() {
        if (!this.audioElement.src) return;
        const playBtn = document.getElementById('player-btn-play');
        if (this.audioElement.paused) {
            this.audioElement.play();
            this.isPlaying = true;
            if (playBtn) playBtn.innerHTML = '<i class="fas fa-pause"></i>';
        } else {
            this.audioElement.pause();
            this.isPlaying = false;
            if (playBtn) playBtn.innerHTML = '<i class="fas fa-play"></i>';
        }
    },

    playNextTrack() {
        let nextIdx = (this.currentTrackIndex + 1) % this.musicTracks.length;
        this.playTrack(nextIdx);
    },

    playPrevTrack() {
        let prevIdx = (this.currentTrackIndex - 1 + this.musicTracks.length) % this.musicTracks.length;
        this.playTrack(prevIdx);
    },

    async runShazam() {
        window.soundEngine?.playJump();
        const btn = document.getElementById('shazam-btn');
        if (btn) btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Eshitilmoqda...`;

        try {
            const res = await fetch('/api/music/shazam', { method: 'POST' });
            const data = await res.json();
            if (data.success && data.track) {
                alert(`🎉 Qo'shiq aniqlandi:\n${data.track.artist} - ${data.track.title}`);
                // Avtomatik o'sha qo'shiqni ijro etish
                this.musicTracks.unshift(data.track);
                this.playTrack(0);
            }
        } catch (e) {
            alert('Shazam audio qidiruvida xatolik yuz berdi');
        } finally {
            if (btn) btn.innerHTML = `<i class="fas fa-microphone"></i> Shazam`;
        }
    },

    async sendMusicToChat(title, artist) {
        window.soundEngine?.playCoin();
        try {
            const res = await fetch('/api/send_to_chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Init-Data': this.tg?.initData || ''
                },
                body: JSON.stringify({ user_id: this.userId, type: 'music', title: title, artist: artist })
            });
            const data = await res.json();
            alert(data.message || 'Musiqa Telegram chatga yuborildi!');
        } catch (e) {
            alert('Xatolik yuz berdi');
        }
    },

    // ==========================================
    // 3. JONLI TV BO'LIMI
    // ==========================================
    async loadTV(query = '', category = 'all') {
        const container = document.getElementById('channels-grid');
        if (!container) return;

        try {
            let url = `/api/tv?category=${category}`;
            if (query) url += `&q=${encodeURIComponent(query)}`;

            const res = await fetch(url);
            const data = await res.json();
            const channels = data.items || [];

            container.innerHTML = channels.map(c => `
                <div class="channel-card" onclick="App.playTVChannel('${c.name}', '${c.stream}', this)">
                    <div class="channel-logo">${c.logo}</div>
                    <div class="channel-info">
                        <h4>${c.name}</h4>
                        <p>${c.desc}</p>
                    </div>
                </div>
            `).join('');

        } catch (err) {
            console.error('TV yuklashda xatolik:', err);
        }
    },

    filterTVCategory(cat, btn) {
        window.soundEngine?.playClick();
        document.querySelectorAll('#tv-categories-container .filter-chip').forEach(c => c.classList.remove('active'));
        if (btn) btn.classList.add('active');
        this.loadTV('', cat);
    },

    playTVChannel(name, streamUrl, el) {
        window.soundEngine?.playClick();
        document.querySelectorAll('.channel-card').forEach(c => c.classList.remove('active'));
        if (el) el.classList.add('active');

        const nameEl = document.getElementById('tv-current-channel-name');
        if (nameEl) nameEl.innerText = name;

        const video = document.getElementById('tv-video-player');
        if (!video) return;

        let targetUrl = streamUrl;
        if (streamUrl.includes('cinerama.uz') && streamUrl.includes('playlist.m3u8')) {
            targetUrl = streamUrl.replace('playlist.m3u8', 'tracks-v1a1/mono.ts.m3u8');
        }

        if (window.Hls && window.Hls.isSupported()) {
            if (this.hls) this.hls.destroy();
            this.hls = new window.Hls({
                testBandwidth: false,
                startLevel: -1,
                abrEwmaDefaultEstimate: 35000000,
                abrEwmaDefaultEstimateMax: 80000000,
                capLevelToPlayerSize: false,
                enableWorker: true,
                liveSyncDurationCount: 3,
                liveMaxLatencyDurationCount: 10,
                maxBufferLength: 45,
                maxMaxBufferLength: 120,
                maxBufferSize: 120 * 1024 * 1024,
                maxBufferHole: 0.5,
                highBufferWatchdogPeriod: 2,
                nudgeOffset: 0.1,
                nudgeMaxRetry: 5,
                backBufferLength: 15,
                startFragPrefetch: true
            });
            this.hls.loadSource(targetUrl);
            this.hls.attachMedia(video);
            this.hls.on(window.Hls.Events.MANIFEST_LOADED, (e, data) => {
                if (data && data.levels && data.levels.length) {
                    let bestIdx = 0, maxScore = -1;
                    for (let i = 0; i < data.levels.length; i++) {
                        const l = data.levels[i];
                        const s = (l.height || 0) * 100000 + (l.bitrate || 0);
                        if (s > maxScore) { maxScore = s; bestIdx = i; }
                    }
                    try {
                        this.hls.startLevel = bestIdx;
                        this.hls.loadLevel = bestIdx;
                        this.hls.nextLoadLevel = bestIdx;
                        this.hls.minAutoLevel = Math.max(0, bestIdx - 1);
                    } catch (err) {}
                }
            });
            this.hls.on(window.Hls.Events.MANIFEST_PARSED, (e, data) => {
                if (data && data.levels && data.levels.length) {
                    let bestIdx = 0, maxScore = -1;
                    for (let i = 0; i < data.levels.length; i++) {
                        const l = data.levels[i];
                        const s = (l.height || 0) * 100000 + (l.bitrate || 0);
                        if (s > maxScore) { maxScore = s; bestIdx = i; }
                    }
                    try {
                        this.hls.startLevel = bestIdx;
                        this.hls.loadLevel = bestIdx;
                        this.hls.nextLoadLevel = bestIdx;
                        this.hls.minAutoLevel = Math.max(0, bestIdx - 1);
                    } catch (err) {}
                }
                video.play().catch(e => console.log('Video autoplay blocked:', e));
            });
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = targetUrl;
            video.play().catch(e => console.log('Video autoplay blocked:', e));
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    // ==========================================
    // 4. O'YINLAR BO'LIMI
    // ==========================================
    async loadGames(query = '') {
        const container = document.getElementById('games-grid');
        if (!container) return;

        try {
            let url = `/api/games`;
            if (query) url += `?q=${encodeURIComponent(query)}`;

            const res = await fetch(url);
            const data = await res.json();
            const games = data.games || [];

            container.innerHTML = games.map(g => `
                <div class="game-item-card" onclick="App.openGame('${g.id}', '${g.title}')">
                    <div class="game-icon-circle">${g.icon}</div>
                    <div class="game-card-title">${g.title}</div>
                    <div class="game-card-category">${g.category} • ⭐ ${g.rating}</div>
                </div>
            `).join('');

        } catch (err) {
            console.error('O\'yinlar yuklashda xatolik:', err);
        }
    },

    openGame(gameId, title) {
        window.soundEngine?.playClick();
        const modal = document.getElementById('game-modal');
        const container = document.getElementById('game-container');
        const titleEl = document.getElementById('game-modal-title');

        if (titleEl) titleEl.innerText = title;
        modal.classList.add('active');

        if (window.GameRunner) {
            window.GameRunner.init(container, gameId);
        }
    },

    async claimChest() {
        window.soundEngine?.playCoin();
        try {
            const res = await fetch('/api/games/chest/claim', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert(data.message);
                const coinEl = document.getElementById('user-coins-display');
                if (coinEl) coinEl.innerText = data.new_coins;
            }
        } catch (e) {
            alert('Sandiqni ochishda xatolik');
        }
    },

    async petAction(action) {
        window.soundEngine?.playClick();
        try {
            const res = await fetch('/api/games/pet/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: action })
            });
            const data = await res.json();
            if (data.success) {
                alert(data.message);
                const pet = data.pet;
                const hEl = document.getElementById('pet-hunger-fill');
                const eEl = document.getElementById('pet-energy-fill');
                const pEl = document.getElementById('pet-happy-fill');
                const lEl = document.getElementById('pet-level-text');

                if (hEl) hEl.style.width = `${pet.hunger}%`;
                if (eEl) eEl.style.width = `${pet.energy}%`;
                if (pEl) pEl.style.width = `${pet.happiness}%`;
                if (lEl) lEl.innerText = `${pet.level}-daraja`;
            }
        } catch (e) {
            alert('Uy hayvoni bilan muloqotda xatolik');
        }
    },

    // ==========================================
    // 5. STORY BO'LIMI
    // ==========================================
    async viewStory() {
        window.soundEngine?.playClick();
        const input = document.getElementById('story-username-input');
        const username = input ? input.value.trim() : '';
        if (!username) {
            alert('Instagram yoki Telegram profil nomini kiriting!');
            return;
        }

        const container = document.getElementById('story-preview-container');
        container.innerHTML = `<div style="text-align: center; padding: 20px;"><i class="fas fa-spinner fa-spin fa-2x"></i><p style="margin-top: 10px;">Hikoyalar yuklanmoqda...</p></div>`;

        try {
            const res = await fetch(`/api/story?username=${encodeURIComponent(username)}`);
            const data = await res.json();
            const stories = data.stories || [];

            container.innerHTML = `
                <div style="background: rgba(30,41,59,0.7); border-radius: 14px; padding: 16px; margin-top: 14px;">
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 14px;">
                        <img src="${data.avatar}" style="width: 48px; height: 48px; border-radius: 50%; border: 2px solid #3b82f6;">
                        <div>
                            <h4 style="font-size: 15px;">@${data.username}</h4>
                            <span style="font-size: 12px; color: #10b981;">● Faol hikoyalar mavjud (${stories.length} ta)</span>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        ${stories.map(s => `
                            <div style="position: relative; border-radius: 10px; overflow: hidden; background: #000;">
                                <img src="${s.media_url}" style="width: 100%; height: 160px; object-fit: cover;">
                                <span style="position: absolute; bottom: 6px; left: 6px; font-size: 10px; background: rgba(0,0,0,0.6); padding: 2px 6px; border-radius: 4px;">${s.timestamp}</span>
                            </div>
                        `).join('')}
                    </div>
                    <button class="btn-primary-action" style="width: 100%; margin-top: 14px; padding: 12px;" onclick="alert('Hikoya yuklab olindi!')">
                        📥 Barcha hikoyalarni yuklab olish
                    </button>
                </div>
            `;
        } catch (e) {
            container.innerHTML = `<p style="color: #ef4444; text-align: center; margin-top: 14px;">Hikoyalarni yuklab bo'lmadi.</p>`;
        }
    },

    // ==========================================
    // 6. HUJJATLAR BO'LIMI
    // ==========================================
    async convertDocText(target) {
        window.soundEngine?.playClick();
        const input = document.getElementById('docs-translit-input');
        const text = input ? input.value.trim() : '';
        if (!text) return;

        try {
            const res = await fetch('/api/docs/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, target: target })
            });
            const data = await res.json();
            const output = document.getElementById('docs-translit-output');
            if (output) output.value = data.result || '';
        } catch (e) {
            alert('Transliteratsiyada xatolik');
        }
    },

    copyTranslit() {
        const output = document.getElementById('docs-translit-output');
        if (output && output.value) {
            navigator.clipboard.writeText(output.value);
            window.soundEngine?.playCoin();
            alert('Nusxalandi!');
        }
    },

    async generatePDF() {
        window.soundEngine?.playCoin();
        const title = document.getElementById('docs-pdf-title')?.value.trim() || 'Hujjat';
        const body = document.getElementById('docs-pdf-body')?.value.trim() || 'Matn';

        try {
            const res = await fetch('/api/docs/pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: title, text: body })
            });
            if (res.ok) {
                const blob = await res.blob();
                const element = document.createElement('a');
                element.href = URL.createObjectURL(blob);
                element.download = `${title}.pdf`;
                document.body.appendChild(element);
                element.click();
                document.body.removeChild(element);
                alert('PDF muvaffaqiyatli yaratildi va yuklab olindi!');
                return;
            }
        } catch (e) {
            console.error('PDF generatsiyasida xatolik:', e);
        }
        alert('PDF yaratishda xatolik yuz berdi');
    },

    closeModal(modalId) {
        window.soundEngine?.playClick();
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.remove('active');
        if (modalId === 'game-modal' && window.GameRunner) {
            window.GameRunner.stop();
        }
    }
};

window.addEventListener('DOMContentLoaded', () => {
    App.init();
});
