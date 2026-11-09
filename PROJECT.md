# Project: BauntyCinemBot

## Architecture
BauntyCinemBot is an asynchronous Telegram Bot and Mini App platform built with:
- **Aiogram 3.17+**: Bot event handling, dispatching, routing, and middlewares.
- **aiohttp 3.9+**: Unified web application server on port 8080 hosting the Mini App SPA and REST endpoints.
- **SQLAlchemy 2.0+ (asyncio)**: Dual database backend supporting SQLite (`aiosqlite`) and PostgreSQL (`asyncpg`).
- **Media & Streaming Engine**:
  - HLS / M3U8 TV channel streaming with direct-first CORS playback and async stream proxy.
  - Telegram Cloud Pool `file_id` instant movie delivery (0 MB server disk overhead).
  - Multi-engine music search (Deezer, iTunes, Tarona, SoundCloud, Invidious) + Shazam audio recognition + Mini App dual-audio preload player.
  - Books module with 3,390 items, 3,391 pre-cached local cover directories, dynamic Pillow/SVG cover generators, and WebApp reader.
- **Security & Reliability Layer**:
  - Sliding-window IP rate limiter, WAF threat inspection, and auto-ban jail.
  - Bot-level throttling and subscription middlewares.
  - Zero-downtime keepalive service with Render.com NAT auto-whitelist.

---

## Feature Inventory
All features identified during the Phase 0 Survey across requirements R1–R5:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Uptime & Keepalive Path Whitelisting | Whitelist `/`, `/webapp`, `/webapp/`, `/index.html` in `SlidingWindowRateLimiter` alongside `/health` | M1 | Survey 1 (R1) |
| 2 | WAF Auto-Ban False Positive Elimination | Allow monitoring user-agents and CLI probes on health and root endpoints without jailing into AutoBanJail | M1 | Survey 1 (R1) |
| 3 | Render NAT Egress IP Collision Prevention | Prevent internal keepalive ping requests and shared Render NAT gateway IPs from being locked out | M1 | Survey 1 (R1) |
| 4 | Non-Punitive User Throttling | Remove cooldown reset on early hits in `ThrottlingMiddleware` to prevent persistent button-tap lockouts | M1 | Survey 1 (R1) |
| 5 | Negative Ban Check Caching | Cache `is_banned == False` in `BotSecurityMiddleware` for 30s-60s to prevent redundant DB queries per update | M1 | Survey 1 (R1) |
| 6 | Syntax & Import Flaw Resolution | Add missing `from typing import Any` in `handlers/books.py` and fix any unhandled exceptions across bot handlers | M1 | Survey 1 (R1) |
| 7 | Atomic Concurrency in `get_or_create_user` | Implement safe retry / savepoint rollback on `IntegrityError` to eliminate `users_pkey` duplicate key crash | M2 | Survey 1 (R5) |
| 8 | Atomic Concurrency in Movie Upserts | Fix race conditions in `upsert_movie` and `save_movie_file` during parallel sync/catalog preloading | M2 | Survey 1 (R5) |
| 9 | SQLite Pool & PRAGMA Optimization | Replace `NullPool` with bounded connection pool and configure `PRAGMA auto_vacuum = INCREMENTAL` & WAL checkpoints | M2 | Survey 1 (R5) |
| 10 | Periodic Storage Pruning Task | Implement background pruning for `download_logs` (>30d) and inactive game records to prevent disk bloat | M2 | Survey 1 (R5) |
| 11 | Docker Build Asset Optimization | Add `.dockerignore` excluding `scratch/`, `data/videos/*.mp4`, and debug caches, saving 130+ MB in container | M2 | Survey 1 (R5) |
| 12 | Direct-First CORS TV Streaming | Enable direct HLS playback for CORS-enabled streams (`stream3.cinerama.uz`) with automatic proxy fallback on error | M3 | Survey 2 (R2) |
| 13 | TV Proxy Pool & Timeout Tuning | Increase proxy connection pool limits, add fast connect timeouts, and cancel upstream requests on client drop | M3 | Survey 2 (R2) |
| 14 | Removal of Blocking Pre-Speed Check | Eliminate `< 1.0 Mbps` hard playback stop in WebApp, moving speed checks to async telemetry | M3 | Survey 2 (R2) |
| 15 | TV Catalog Sanitization & Health Check | Fix dead channels (Ruxsor TV 1040, Nasaf TV), enforce `https://`, and implement dynamic failure auto-failover | M3 | Survey 2 (R2) |
| 16 | HLS.js Buffer & Stalling Optimization | Tune client buffer lengths (maxBufferLength 15s) and replace currentTime jumps with clean recovery | M3 | Survey 2 (R2) |
| 17 | Movie 1-to-1 Replication & Deep Linking | Support `/start <code>`, numeric lookups, franchise codes (`718`, `717`, `287`, `1500`), serial parts navigation | M4 | Survey 3 (R3) |
| 18 | Telegram Cloud Pool Movie Delivery | Deliver full films instantly via cached `file_id` with 0 MB server disk overhead | M4 | Survey 3 (R3) |
| 19 | Music Multi-Engine Search & Shazam | Search across Deezer, iTunes, Tarona, SoundCloud; Shazam audio recognition for voice/audio notes | M4 | Survey 3 (R3) |
| 20 | Mini App Dual-Audio Preload Player | Gapless playback engine, moods filter, playlists, procedural Uzbek atlas cover, and `/api/music/send` to chat | M4 | Survey 3 (R3) |
| 21 | Strict BauntyCinemBot Brand Purity | Regex sanitization replacing all `@Zakirovs*` branding with `@BauntyCinemabot` and `@BauntyFilms` | M4 | Survey 3 (R3) |
| 22 | Books Catalog & Local Cover Caching | 3,390 books metadata in `data/books.json` and 3,391 pre-cached local cover sets in `data/bk/` | M4 | Survey 3 (R4) |
| 23 | Async Book Remote Fetching | Replace synchronous `urllib.request.urlopen` in `services/book_service.py` with async `aiohttp` client session | M4 | Survey 3 (R4) |
| 24 | Book Reading & Document Delivery | In-chat reading excerpts, WebApp multi-chapter reader, and PDF/EPUB document delivery with thumbnail | M4 | Survey 3 (R4) |
| 25 | Package Manifest Alignment | Add missing runtime dependencies (`shazamio>=0.8.0`, `reportlab>=4.0.0`) to `requirements.txt` | M4 | Survey 3 (R4) |
| 26 | Full Opaque-Box E2E Test Suite | 4-tier requirement-driven test suite verifying R1-R5 without internal implementation coupling | M5 | E2E Track |
| 27 | Adversarial Hardening (Tier 5) | White-box adversarial testing identifying untested paths and stress-testing edge cases | M5 | Implementation |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | `M1_security_ratelimit_errors` | Features 1, 2, 3, 4, 5, 6 (R1: Rate limiting, UptimeRobot IP blocking, WAF rules, throttling, and syntax fixes) | None | DONE |
| M2 | `M2_database_concurrency_bloat` | Features 7, 8, 9, 10, 11 (R5: Concurrency race condition fixes, SQLite pooling, storage maintenance, .dockerignore) | None | DONE |
| M3 | `M3_tv_streaming_connectivity` | Features 12, 13, 14, 15, 16 (R2: TV channel streaming, direct-first CORS, proxy tuning, health service, buffer recovery) | M1 | DONE |
| M4 | `M4_media_books_integration` | Features 17, 18, 19, 20, 21, 22, 23, 24, 25 (R3 & R4: Movies, music, books async service, branding, dependencies) | M1, M2 | DONE |
| M5 | `M5_e2e_verification_hardening` | Features 26, 27 (Final Milestone: 100% E2E test pass across Tiers 1-4 + Tier 5 adversarial hardening) | M1, M2, M3, M4, TEST_READY | DONE |
| E2E | `E2E_Testing_Track` | Requirement-driven test suite design across Tiers 1-4, publishing TEST_READY.md | None (Parallel) | DONE |

---

## Interface Contracts

### Security Middleware ↔ WebApp Endpoints
- Health paths (`/health`, `/ping`, `/healthz`, `/status`, `/`, `/webapp/`, `/index.html`) must return HTTP 200 without rate limiting or IP banning.
- Uptime monitor probes (HEAD/GET with standard monitoring User-Agents or empty User-Agent on health paths) must never be entered into `AutoBanJail`.

### Database Concurrency ↔ Bot Handlers
- `crud.get_or_create_user(session, user_id, ...)`: Returns `Tuple[User, bool]`. MUST NOT raise `IntegrityError` under concurrent invocations for the same user ID.
- `crud.upsert_movie(session, movie_data)`: Returns `Movie`. MUST NOT raise unique constraint violations on `movies.code`.
- `crud.is_user_banned(session, user_id)`: Cached in memory for 30s to avoid per-event DB queries.

### TV Streaming Engine ↔ WebApp Player
- `/api/tv`: Returns JSON `{ok: true, channels: [...], categories: [...]}` with cached ETag.
- Direct stream URLs on CORS-enabled domains (`stream3.cinerama.uz`) are played directly in HLS.js. On error, fallback to `/api/tv/stream?url=<encoded_url>`.
- `/api/tv/stream`: Returns chunked `video/mp2t` or rewritten `.m3u8` playlist with CORS headers.

### External Media & Books ↔ WebApp / Telegram
- `/api/books/{id}`: Returns book metadata in <10ms from in-memory cache/disk.
- `book_service.get_book_by_id`: Uses non-blocking async `aiohttp` session (no synchronous `urllib.request.urlopen`).
- All user-facing movie, music, and book captions strictly use `@BauntyCinemabot` and `@BauntyFilms`.

---

## Code Layout
- `main.py`: Application entry point, dispatcher, and background tasks.
- `config.py`: Application settings (`pydantic-settings`).
- `database/`:
  - `models.py`: Declarative SQLAlchemy models.
  - `session.py`: Async engine and session management.
  - `crud.py`: Database operations and queries.
- `middlewares/`:
  - `security.py`: Telegram bot security middleware.
  - `throttling.py`: Telegram event throttling.
  - `subscription.py`: Channel subscription validation.
- `services/`:
  - `security_service.py`: WebApp WAF, rate limiter, and IP ban jail.
  - `web_server.py`: aiohttp REST endpoints and static file server.
  - `keepalive_service.py`: Zero-downtime ping loop.
  - `tv_data.py`: TV channels catalog and fallback streams.
  - `tv_room_service.py`: TV watch party room management.
  - `movie_service.py`: Movie catalog sync, franchise mapping, and delivery.
  - `music_service.py`: Multi-engine music search and audio recognition.
  - `book_service.py`: Books catalog, cover generation, and PDF/EPUB delivery.
- `handlers/`: Telegram message and callback handlers (`start.py`, `movies.py`, `music.py`, `books.py`, `tvroom.py`, `admin.py`, etc.).
- `keyboards/`: Inline and reply keyboard markup builders.
- `webapp/`: WebApp frontend assets (HTML, CSS, JS bundles).
- `data/`: Static catalogs (`books.json`, `music_home.json`, `catalog.json`) and assets (`bk/`).
- `tests/`: Automated pytest suites.
