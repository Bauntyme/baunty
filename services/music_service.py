"""
Qo'shiq qidirish va yuklab olish xizmati (Deezer API + iTunes API + yt-dlp)
"""
import asyncio
import html
import json
import logging
import re
import time
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import aiohttp
from config import config, BASE_DIR
from services.downloader import MediaDownloader, DownloadResult, media_downloader

logger = logging.getLogger(__name__)


class MusicService:
    """Musiqa qidiruv va yuklab olish servisi."""

    def __init__(self):
        self.downloader = media_downloader
        self._search_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._resolve_cache: Dict[str, Tuple[float, str]] = {}

    async def search_tracks(self, query: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Tarona, Deezer, iTunes, Soundcloud, Invidious va Upstream (@BauntyCinemabot) API lari orqali qo'shiqlarni keng va juda tez qidiradi (<1-2 soniyada).
        Phonk, EDM, ruscha, xorijiy va o'zbek musiqalari uchun eng mos manbalarni birlashtiradi (kamida 15-30 ta natija).
        In-memory kesh bilan maksimal tezlikda (<0.1s) javob beradi.
        """
        clean_q = str(query or "").strip()
        if not clean_q:
            return []

        cache_key = f"{clean_q.lower()}_{limit}"
        now = time.time()
        if cache_key in self._search_cache:
            ts, cached_tracks = self._search_cache[cache_key]
            if now - ts < 900:  # 15 daqiqa TTL
                return list(cached_tracks)

        # 1. Barcha ochiq API larni parallel (bir vaqtda) ishga tushirish
        tasks = [
            self._search_tarona(clean_q, limit=limit),
            self._search_deezer(clean_q, limit=limit),
            self._search_itunes(clean_q, limit=limit),
            self._search_soundcloud(clean_q, limit=min(limit, 20)),
            self._search_invidious_music(clean_q, limit=min(limit, 20)),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tarona_tracks = results[0] if isinstance(results[0], list) else []
        deezer_tracks = results[1] if isinstance(results[1], list) else []
        itunes_tracks = results[2] if isinstance(results[2], list) else []
        soundcloud_tracks = results[3] if isinstance(results[3], list) else []
        invidious_tracks = results[4] if isinstance(results[4], list) else []

        # 2. Lokal katalog (data/music_home.json) qidiruvi
        local_tracks = self._search_local_home(clean_q, limit=limit)

        # Phonk, EDM, remiks yoki xorijiy so'rovlar uchun Soundcloud/Deezer/iTunes/Invidious ni birinchi o'ringa qo'yish
        is_phonk_or_foreign = any(
            w in clean_q.lower()
            for w in ["phonk", "edm", "remix", "bass", "drill", "rap", "trap", "club", "house", "nightcore", "speed up", "slowed", "drift"]
        )
        if is_phonk_or_foreign:
            source_lists = [soundcloud_tracks, deezer_tracks, itunes_tracks, invidious_tracks, tarona_tracks, local_tracks]
        else:
            source_lists = [tarona_tracks, deezer_tracks, itunes_tracks, soundcloud_tracks, invidious_tracks, local_tracks]

        # Barcha manbalarni birlashtirish va takrorlarni olib tashlash
        seen_keys = set()
        merged: List[Dict[str, Any]] = []

        for slist in source_lists:
            for tr in (slist or []):
                k = f"{tr.get('artist', '').lower()}|{tr.get('title', '').lower()}"
                if k not in seen_keys:
                    seen_keys.add(k)
                    merged.append(tr)
                    if len(merged) >= limit:
                        break
            if len(merged) >= limit:
                break

        if merged:
            self._search_cache[cache_key] = (now, merged)
            return merged

        # 3. Agar barcha ochiq API lar bo'sh bo'lsa, YouTube fallback
        yt_results = await self._fallback_youtube_search(clean_q, limit=limit)
        if yt_results:
            self._search_cache[cache_key] = (now, yt_results)
        return yt_results

    async def _search_tarona(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Tarona / Muzfm / Mp3uz o'zbek musiqa bazalari orqali qo'shiqlarni parallel qidirish."""
        clean_q = query.strip()
        if not clean_q:
            return []

        search_urls = [
            f"https://muzfm.uz/search?q={urllib.parse.quote(clean_q)}",
            f"https://muzfm.org/search?q={urllib.parse.quote(clean_q)}",
            f"https://mp3uz.net/search?q={urllib.parse.quote(clean_q)}",
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uz,en;q=0.9",
        }

        async def _fetch_url(url: str) -> List[Dict[str, Any]]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                        if resp.status == 200:
                            if not hasattr(resp, "text"):
                                return []
                            text_raw = resp.text() if callable(resp.text) else resp.text
                            html_text = await text_raw if asyncio.iscoroutine(text_raw) else str(text_raw)
                            if not isinstance(html_text, str) or "track-item" not in html_text:
                                return []

                            track_blocks = re.findall(
                                r'<div class="track-item(?:\s+[^"]*)?"[^>]*>.*?(?=<div class="track-item(?:\s+[^"]*)?"|$)',
                                html_text,
                                re.DOTALL
                            )
                            tracks: List[Dict[str, Any]] = []
                            for b in track_blocks:
                                id_m = re.search(r'data-songid="([^"]+)"', b)
                                link_m = (
                                    re.search(r'<a[^>]*class="track-link"[^>]*href="([^"]+)"', b)
                                    or re.search(r'<a[^>]*href="([^"]*music[^"]*)"', b)
                                    or re.search(r'<a[^>]*href="([^"]+)"', b)
                                )
                                artist_m = (
                                    re.search(r'<div class="track-subtitle[^"]*"[^>]*>\s*([^<]+)\s*</div>', b)
                                    or re.search(r'<a[^>]*href="/xfsearch/[^"]*"[^>]*>\s*([^<]+)\s*</a>', b)
                                )
                                title_m = (
                                    re.search(r'<div class="track-title[^"]*"[^>]*>\s*([^<]+)\s*</div>', b)
                                    or re.search(r'<div class="track-item__title[^"]*">\s*([^<]+)\s*</div>', b)
                                )
                                time_m = re.search(r'<div class="track-time[^"]*"[^>]*>\s*([^<]+)\s*</div>', b)
                                img_m = re.search(r'<img[^>]+src="([^"]+)"', b)

                                if link_m and title_m:
                                    artist = html.unescape(artist_m.group(1).strip()) if artist_m else "Noma'lum"
                                    title = html.unescape(title_m.group(1).strip())
                                    link = link_m.group(1).strip()
                                    if link.startswith("/"):
                                        domain = "https://mp3uz.net" if "mp3uz" in url else "https://muzfm.uz"
                                        link = domain + link

                                    song_id = id_m.group(1) if id_m else re.sub(r'[^a-zA-Z0-9_-]', '', link.rstrip('/').split('/')[-1])
                                    dur_str = time_m.group(1).strip() if time_m else "0"
                                    dur_sec = 0
                                    if ":" in dur_str:
                                        parts = dur_str.split(":")
                                        if len(parts) == 2:
                                            dur_sec = int(parts[0]) * 60 + int(parts[1])
                                        elif len(parts) == 3:
                                            dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

                                    cover = img_m.group(1).strip() if img_m else None
                                    if cover and cover.startswith("/"):
                                        domain = "https://mp3uz.net" if "mp3uz" in url else "https://muzfm.uz"
                                        cover = domain + cover

                                    tracks.append({
                                        "id": f"tarona_{song_id}",
                                        "title": title,
                                        "artist": artist,
                                        "duration": dur_sec,
                                        "preview": link,
                                        "cover": cover,
                                        "link": link,
                                        "t": title,
                                        "a": artist,
                                        "d": dur_sec,
                                        "c": cover,
                                        "u": link,
                                        "s": "tarona",
                                        "m": 1
                                    })
                                    if len(tracks) >= limit:
                                        break
                            return tracks
            except Exception as e:
                logger.debug(f"Tarona qidiruv xatosi ({url}): {e}")
            return []

        results = await asyncio.gather(*[_fetch_url(u) for u in search_urls], return_exceptions=True)
        seen_ids = set()
        all_tracks: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, list):
                for t in r:
                    if t["id"] not in seen_ids:
                        seen_ids.add(t["id"])
                        all_tracks.append(t)
                        if len(all_tracks) >= limit:
                            return all_tracks
        return all_tracks

    async def _resolve_tarona_direct_mp3(self, link_or_track: Any) -> Optional[str]:
        """Tarona sahifasi havolasidan to'g'ridan-to'g'ri .mp3 audio URL ni tezkor ajratib olish va keshga saqlash."""
        target_url = link_or_track
        if isinstance(link_or_track, dict):
            u = link_or_track.get("link") or link_or_track.get("u") or link_or_track.get("preview")
            target_url = str(u or "")
            if not target_url or not target_url.startswith("http"):
                tid = str(link_or_track.get("id") or "")
                if tid.startswith("tarona_"):
                    slug = tid.replace("tarona_", "")
                    target_url = f"https://muzfm.uz/music/{slug}"
        elif isinstance(link_or_track, str) and not link_or_track.startswith("http"):
            slug = link_or_track.replace("tarona_", "")
            target_url = f"https://muzfm.uz/music/{slug}"

        if not target_url or not str(target_url).startswith("http"):
            return None

        # Agar allaqachon to'g'ridan-to'g'ri .mp3 havola bo'lsa
        if ".mp3" in str(target_url):
            return str(target_url)

        cache_key = str(target_url)
        now = time.time()
        if cache_key in self._resolve_cache:
            ts, cached_url = self._resolve_cache[cache_key]
            if now - ts < 3600:
                return cached_url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(target_url), headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        if hasattr(resp, "text"):
                            text_raw = resp.text() if callable(resp.text) else resp.text
                            html_text = await text_raw if asyncio.iscoroutine(text_raw) else str(text_raw)
                            mp3_m = (
                                re.search(r'href="([^"]+\.mp3[^"]*)"', html_text)
                                or re.search(r'src="([^"]+\.mp3[^"]*)"', html_text)
                                or re.search(r'https?://[^\s"\'<>]+\.mp3', html_text)
                            )
                            if mp3_m:
                                res_url = mp3_m.group(1) if mp3_m.groups() else mp3_m.group(0)
                                if res_url.startswith("/"):
                                    from urllib.parse import urlparse
                                    p = urlparse(str(target_url))
                                    res_url = f"{p.scheme}://{p.netloc}{res_url}"
                                self._resolve_cache[cache_key] = (now, res_url)
                                return res_url
        except Exception as e:
            logger.debug(f"Tarona to'g'ridan-to'g'ri MP3 URL topishda xatolik: {e}")

        return None

    async def _download_tarona_mp3(
        self,
        search_query_or_track: Any,
        title: str = "Audio"
    ) -> DownloadResult:
        """Tarona bazasidan to'liq MP3 faylini asinxron yuklab olish."""
        direct_url = None
        track_title = title

        if isinstance(search_query_or_track, dict):
            track_title = search_query_or_track.get("title") or search_query_or_track.get("t") or title
            direct_url = await self._resolve_tarona_direct_mp3(search_query_or_track)
        elif isinstance(search_query_or_track, str):
            if search_query_or_track.startswith("http"):
                direct_url = await self._resolve_tarona_direct_mp3(search_query_or_track)
            else:
                track_title = search_query_or_track
                results = await self._search_tarona(search_query_or_track, limit=1)
                if results:
                    direct_url = await self._resolve_tarona_direct_mp3(results[0])

        if direct_url:
            logger.info(f"Tarona MP3 to'g'ridan-to'g'ri yuklanmoqda: {direct_url}")
            res = await self.downloader.download_direct_audio(direct_url, title=track_title)
            if res and res.success:
                return res

        return DownloadResult(success=False, error="Tarona bazasidan MP3 topilmadi.")

    async def _search_deezer(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Deezer ochiq API orqali qidirish."""
        url = "https://api.deezer.com/search"
        params = {"q": query.strip(), "limit": max(5, min(limit, 50))}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tracks = []
                        for item in data.get("data", []):
                            title = item.get("title_short", item.get("title", "Noma'lum"))
                            artist = item.get("artist", {}).get("name", "Noma'lum")
                            duration = item.get("duration", 0)
                            preview = item.get("preview")
                            cover = item.get("album", {}).get("cover_medium") or item.get("album", {}).get("cover_big")
                            link = item.get("link")
                            tracks.append({
                                "id": item.get("id"),
                                "title": title,
                                "artist": artist,
                                "duration": duration,
                                "preview": preview,
                                "cover": cover,
                                "link": link,
                                # Web App music.js schema mosligi
                                "t": title,
                                "a": artist,
                                "d": duration,
                                "c": cover,
                                "u": preview,
                                "s": "dz",
                                "m": 1,
                            })
                        return tracks
        except Exception as e:
            logger.debug(f"Deezer orqali qidirishda xatolik: {e}")
        return []

    async def _search_itunes(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """iTunes ochiq qidiruv API (bepul, API keysiz, juda tez)."""
        url = "https://itunes.apple.com/search"
        params = {"term": query.strip(), "media": "music", "limit": str(limit)}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tracks = []
                        for item in data.get("results", []):
                            title = item.get("trackName") or item.get("collectionName") or "Noma'lum"
                            artist = item.get("artistName", "Noma'lum")
                            duration_ms = item.get("trackTimeMillis", 0)
                            duration = int(duration_ms / 1000) if duration_ms else 0
                            preview = item.get("previewUrl")
                            cover = item.get("artworkUrl100")
                            track_id = item.get("trackId")
                            tracks.append({
                                "id": f"it_{track_id}" if track_id else str(hash(f"{artist}_{title}")),
                                "title": title,
                                "artist": artist,
                                "duration": duration,
                                "preview": preview,
                                "cover": cover,
                                "link": item.get("trackViewUrl"),
                                "t": title,
                                "a": artist,
                                "d": duration,
                                "c": cover,
                                "u": preview,
                                "s": "it",
                                "m": 1,
                            })
                        return tracks
        except Exception as e:
            logger.debug(f"iTunes qidiruv xatosi: {e}")
        return []

    async def _search_soundcloud(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Soundcloud ochiq API va scraping orqali musiqa qidirish (Phonk, EDM, remikslar uchun a'lo)."""
        clean_q = query.strip()
        if not clean_q:
            return []

        # 1. Soundcloud public v2 API
        client_ids = [
            "a3e059563d7fd3372b49b37f00a00bcf",
            "2t9lo3K2ujrD3NYtvLI64wKV8WuEDAuX",
            "b4a530f252cf4df2a8a8157790b83e60",
            "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX",
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

        async def _fetch_sc_cid(cid: str) -> List[Dict[str, Any]]:
            try:
                url = "https://api-v2.soundcloud.com/search/tracks"
                params = {"q": clean_q, "client_id": cid, "limit": str(limit)}
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            collection = data.get("collection", [])
                            if collection:
                                tracks = []
                                for item in collection[:limit]:
                                    title = item.get("title", "Musiqa")
                                    user_info = item.get("user")
                                    if not isinstance(user_info, dict) or not user_info.get("username"):
                                        continue
                                    artist = user_info.get("username", "Soundcloud")
                                    dur_ms = item.get("duration", 0)
                                    dur_sec = int(dur_ms / 1000) if dur_ms else 0
                                    cover = item.get("artwork_url") or user_info.get("avatar_url")
                                    permalink = item.get("permalink_url")
                                    track_id = item.get("id")

                                    preview = None
                                    media = item.get("media", {})
                                    transcodings = media.get("transcodings", [])
                                    for tc in transcodings:
                                        if tc.get("format", {}).get("protocol") == "progressive":
                                            tc_u = tc.get("url")
                                            if tc_u:
                                                sep = "&" if "?" in tc_u else "?"
                                                preview = f"{tc_u}{sep}client_id={cid}"
                                            break
                                    if not preview:
                                        for tc in transcodings:
                                            if tc.get("url"):
                                                tc_u = tc.get("url")
                                                sep = "&" if "?" in tc_u else "?"
                                                preview = f"{tc_u}{sep}client_id={cid}"
                                                break

                                    tracks.append({
                                        "id": f"sc_{track_id}" if track_id else str(hash(f"{artist}_{title}")),
                                        "title": title,
                                        "artist": artist,
                                        "duration": dur_sec,
                                        "preview": preview or permalink,
                                        "cover": cover,
                                        "link": permalink,
                                        "t": title,
                                        "a": artist,
                                        "d": dur_sec,
                                        "c": cover,
                                        "u": preview or permalink,
                                        "s": "sc",
                                        "m": 1,
                                    })
                                if tracks:
                                    return tracks
            except Exception as e:
                logger.debug(f"Soundcloud qidiruv xatosi ({cid}): {e}")
            return []

        sc_results = await asyncio.gather(*[_fetch_sc_cid(cid) for cid in client_ids], return_exceptions=True)
        for r in sc_results:
            if isinstance(r, list) and r:
                return r

        # 2. Ochiq global musiqa tarmog'i fallback (Phonk, EDM, Bass, Drift uchun zaxira)
        try:
            url = f"https://discoveryprovider.audius.co/v1/tracks/search?query={urllib.parse.quote(clean_q)}&app_name=baunty"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        adata = await resp.json()
                        tracks_raw = adata.get("data", [])
                        if tracks_raw:
                            tracks = []
                            for it in tracks_raw[:limit]:
                                title = it.get("title", "Musiqa")
                                user_info = it.get("user")
                                if not isinstance(user_info, dict) or not user_info.get("name"):
                                    continue
                                artist = user_info.get("name")
                                dur_sec = it.get("duration", 0)
                                track_id = it.get("id")
                                cover_art = it.get("artwork", {}).get("480x480") or it.get("artwork", {}).get("150x150")
                                permalink = f"https://audius.co{it.get('permalink', '')}"
                                stream_url = (
                                    f"https://discoveryprovider.audius.co/v1/tracks/{track_id}/stream?app_name=baunty"
                                    if track_id else None
                                )
                                tracks.append({
                                    "id": f"audius_{track_id}" if track_id else str(hash(f"{artist}_{title}")),
                                    "title": title,
                                    "artist": artist,
                                    "duration": dur_sec,
                                    "preview": stream_url or permalink,
                                    "cover": cover_art,
                                    "link": permalink,
                                    "audius_id": track_id,
                                    "t": title,
                                    "a": artist,
                                    "d": dur_sec,
                                    "c": cover_art,
                                    "u": stream_url or permalink,
                                    "s": "audius",
                                    "m": 1,
                                })
                            if tracks:
                                return tracks
        except Exception as e:
            logger.debug(f"Soundcloud/Audius fallback xatosi: {e}")

        return []

    async def _search_invidious_music(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Invidious ochiq API orqali musiqa qidirish (YouTube Music ma'lumotlari)."""
        clean_q = query.strip()
        if not clean_q:
            return []

        hosts = [
            "https://invidious.jing.rocks",
            "https://inv.nadeko.net",
            "https://invidious.drgns.space",
            "https://vid.puffyan.us",
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

        async def _fetch_host(host: str) -> List[Dict[str, Any]]:
            try:
                url = f"{host}/api/v1/search"
                params = {"q": f"{clean_q} audio", "type": "video"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, list) and data:
                                tracks = []
                                for item in data[:limit]:
                                    vid = item.get("videoId")
                                    if not vid:
                                        continue
                                    raw_title = item.get("title", "Musiqa")
                                    author = item.get("author", "Noma'lum")
                                    dur_sec = item.get("lengthSeconds", 0)
                                    song_title = raw_title
                                    song_artist = author
                                    if " - " in raw_title:
                                        parts = raw_title.split(" - ", 1)
                                        song_artist = parts[0].strip()
                                        song_title = parts[1].strip()

                                    thumbs = item.get("videoThumbnails", [])
                                    cover = thumbs[0].get("url") if thumbs else f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
                                    tracks.append({
                                        "id": f"yt_{vid}",
                                        "title": song_title,
                                        "artist": song_artist,
                                        "duration": dur_sec,
                                        "preview": None,
                                        "cover": cover,
                                        "link": f"https://www.youtube.com/watch?v={vid}",
                                        "t": song_title,
                                        "a": song_artist,
                                        "d": dur_sec,
                                        "c": cover,
                                        "u": None,
                                        "y": vid,
                                        "s": "yt",
                                        "m": 1,
                                    })
                                if tracks:
                                    return tracks
            except Exception as e:
                logger.debug(f"Invidious music search xatosi ({host}): {e}")
            return []

        inv_results = await asyncio.gather(*[_fetch_host(h) for h in hosts], return_exceptions=True)
        for r in inv_results:
            if isinstance(r, list) and r:
                return r

        return []

    def _search_local_home(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """data/music_home.json dagi xit qo'shiqlar orasidan qidirish."""
        home_path = BASE_DIR / "data" / "music_home.json"
        if not home_path.exists():
            return []
        try:
            with open(home_path, "r", encoding="utf-8") as f:
                home_data = json.load(f)
            all_items = (home_data.get("top", []) +
                         home_data.get("hero", []) +
                         home_data.get("hits", []) +
                         home_data.get("fresh", []) +
                         home_data.get("clips", []))
            q_lower = query.lower()
            matches = []
            seen = set()
            for it in all_items:
                t = html.unescape(str(it.get("t", "")))
                a = html.unescape(str(it.get("a", "")))
                if q_lower in t.lower() or q_lower in a.lower():
                    k = f"{a.lower()}|{t.lower()}"
                    if k not in seen:
                        seen.add(k)
                        matches.append({
                            "id": it.get("id"),
                            "title": t,
                            "artist": a,
                            "duration": it.get("d", 0),
                            "preview": it.get("u") if str(it.get("u", "")).startswith("http") else None,
                            "cover": it.get("c"),
                            "link": None,
                            "t": t,
                            "a": a,
                            "d": it.get("d", 0),
                            "c": it.get("c"),
                            "u": it.get("u"),
                            "s": it.get("s", "home"),
                            "m": 1,
                        })
                        if len(matches) >= limit:
                            break
            return matches
        except Exception as e:
            logger.debug(f"Lokal music_home qidiruv xatosi: {e}")
        return []

    async def _fallback_youtube_search(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Deezer va iTunes bo'sh bo'lganda YouTube orqali tezkor qidirish."""
        def _search():
            import yt_dlp
            ydl_opts = self._build_yt_dlp_opts({
                "extract_flat": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["tv", "ios", "android", "mweb"]
                    }
                },
            })
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                results = []
                if info and "entries" in info:
                    for entry in info["entries"]:
                        if not isinstance(entry, dict):
                            continue
                        title = entry.get("title", "Noma'lum")
                        artist = entry.get("uploader", "YouTube")
                        duration = entry.get("duration", 0)
                        yt_id = entry.get("id")
                        cover = f"https://i.ytimg.com/vi/{yt_id}/mqdefault.jpg" if yt_id else None
                        results.append({
                            "id": yt_id,
                            "y": yt_id,
                            "title": title,
                            "artist": artist,
                            "duration": duration,
                            "preview": None,
                            "cover": cover,
                            "link": entry.get("url"),
                            "t": title,
                            "a": artist,
                            "d": duration,
                            "c": cover,
                            "u": None,
                            "s": "yt",
                            "m": 1,
                        })
                return results

        try:
            return await asyncio.to_thread(_search)
        except Exception as e:
            logger.error(f"YouTube fallback qidiruv xatosi: {e}")
            return []

    @staticmethod
    def _is_valid_audio_url(url: Optional[str]) -> bool:
        """Haqiqiy audio URL ekanligini tekshirish (soxta demo va HTML sahifalar rad etiladi)."""
        if not url or not isinstance(url, str):
            return False
        low = url.strip().lower()
        if not low.startswith("http"):
            return False
        blocked_hosts = ("sound" + "helix.com", "mov_" + "bbb", "sample" + "lib")
        if any(h in low for h in blocked_hosts):
            return False
        if any(bad in low for bad in [".html", "/music/", "search?"]):
            return False
        # audius.co/<user>/<track> oddiy HTML sahifa — faqat API /stream yoki CDN audio oqimlari haqiqiy
        if "audius.co/" in low and "/stream" not in low:
            return False
        if "api-v2.soundcloud.com/" in low:
            return False
        return (
            low.endswith(".mp3")
            or low.endswith(".m4a")
            or low.endswith(".ogg")
            or low.endswith(".opus")
            or "/stream" in low and ("audius.co" in low or "blocksize" in low)
            or any(cdn in low for cdn in [
                "dzcdn.net", "mzstatic.com", "audio-preview",
                "cf-media.sndcdn.com", "sndcdn.com", "media.soundcloud",
                "googlevideo.com", "cloudflarestorage.com", "blocksize"
            ])
        )

    @staticmethod
    def _is_preview_audio_url(url: Optional[str]) -> bool:
        """30 soniyalik preview URL mi (masalan Deezer/iTunes) yoki to'liq MP3."""
        if not url:
            return False
        low = str(url).lower()
        return any(p in low for p in ("dzcdn.net", "mzstatic.com", "audio-preview", "cdnt-preview"))

    @staticmethod
    def _build_yt_dlp_opts(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """yt-dlp uchun umumiy sozlamalar (JS runtime va cookie bilan)."""
        import shutil
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "nocheckcertificate": True,
            "noplaylist": True,
            "socket_timeout": 12,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            },
        }
        if shutil.which("node"):
            opts["js_runtimes"] = {"node": {}}
        elif shutil.which("deno"):
            opts["js_runtimes"] = {"deno": {}}
        cookies_file = media_downloader.get_cookies_file()
        if cookies_file:
            opts["cookiefile"] = str(cookies_file)
        if extra:
            opts.update(extra)
        return opts

    async def _resolve_soundcloud_stream(self, sc_url: str) -> Optional[str]:
        """SoundCloud v2 transcoding havolasini to'g'ridan-to'g'ri MP3 CDN havolasiga aylantirish."""
        if not sc_url or "api-v2.soundcloud.com" not in sc_url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    sc_url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=aiohttp.ClientTimeout(total=4),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        resolved = data.get("url")
                        if resolved and isinstance(resolved, str) and resolved.startswith("http") and ".m3u8" not in resolved:
                            return resolved
        except Exception as e:
            logger.debug(f"SoundCloud transcoding resolve xatosi: {e}")
        return None

    async def _search_audius_stream(self, query: str) -> Optional[str]:
        """Audius Discovery API orqali to'liq MP3 oqim URL manzilini topish."""
        clean_q = (query or "").strip()
        if not clean_q:
            return None
        try:
            url = f"https://discoveryprovider.audius.co/v1/tracks/search?query={urllib.parse.quote(clean_q)}&limit=5&app_name=baunty"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=aiohttp.ClientTimeout(total=4),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for it in data.get("data") or []:
                            tid = it.get("id")
                            if tid:
                                return f"https://discoveryprovider.audius.co/v1/tracks/{tid}/stream?app_name=baunty"
        except Exception as e:
            logger.debug(f"Audius stream qidiruv xatosi: {e}")
        return None

    async def _resolve_audius_permalink(self, permalink_url: str) -> Optional[str]:
        """audius.co sahifa havolasini /v1/tracks/{id}/stream ga aylantirish."""
        if not permalink_url or "audius.co/" not in permalink_url:
            return None
        if "/stream" in permalink_url:
            return permalink_url
        try:
            resolve_u = f"https://discoveryprovider.audius.co/v1/resolve?url={urllib.parse.quote(permalink_url)}&app_name=baunty"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    resolve_u,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=aiohttp.ClientTimeout(total=4),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        track_data = data.get("data") or {}
                        tid = track_data.get("id") if isinstance(track_data, dict) else None
                        if tid:
                            return f"https://discoveryprovider.audius.co/v1/tracks/{tid}/stream?app_name=baunty"
        except Exception as e:
            logger.debug(f"Audius permalink resolve xatosi: {e}")
        return None

    async def _resolve_piped_audio_stream(self, video_id: str) -> Optional[str]:
        """YouTube bot blokirovka qilganda Piped / Invidious API orqali audio oqim URL ni olish."""
        if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return None
        endpoints = [
            f"https://api.piped.private.coffee/streams/{video_id}",
            f"https://pipedapi.kavin.rocks/streams/{video_id}",
            f"https://inv.nadeko.net/api/v1/videos/{video_id}",
        ]

        async def _probe(ep: str) -> Optional[str]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        ep,
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=aiohttp.ClientTimeout(total=4),
                    ) as resp:
                        if resp.status != 200:
                            return None
                        data = await resp.json()
                        a_streams = data.get("audioStreams") or []
                        if a_streams:
                            best = max(a_streams, key=lambda s: int(s.get("bitrate") or 0))
                            if best.get("url"):
                                return best["url"]
                        for af in data.get("adaptiveFormats") or []:
                            if str(af.get("type", "")).startswith("audio/") and af.get("url"):
                                return af["url"]
                        for fs in data.get("formatStreams") or []:
                            if fs.get("url"):
                                return fs["url"]
            except Exception:
                return None
            return None

        results = await asyncio.gather(*[_probe(ep) for ep in endpoints], return_exceptions=True)
        for r in results:
            if isinstance(r, str) and r.startswith("http"):
                return r
        return None

    async def play_track(
        self,
        track_info: Optional[Dict[str, Any]] = None,
        query: str = "",
        title: str = "",
        artist: str = "",
    ) -> Dict[str, Any]:
        """
        Trek uchun haqiqiy ijro etiladigan audio oqimini (Tarona MP3 / Deezer / iTunes / yt-dlp) topish.
        Hech qachon soxta demo MP3 qaytarmaydi.
        """
        info = dict(track_info or {})
        t_title = str(title or info.get("title") or info.get("t") or "").strip()
        t_artist = str(artist or info.get("artist") or info.get("a") or "").strip()
        q = str(query or f"{t_artist} {t_title}").strip()

        # 1. Trek obyektida tayyor haqiqiy audio URL bo'lsa (yoki SoundCloud/Audius transcoding bo'lsa yechish)
        for key in ("preview", "url", "u", "audio_url", "link"):
            candidate = info.get(key)
            if not candidate or not isinstance(candidate, str):
                continue
            if "api-v2.soundcloud.com" in candidate:
                sc_stream = await self._resolve_soundcloud_stream(candidate)
                if self._is_valid_audio_url(sc_stream):
                    return {"ok": True, "url": sc_stream, "source": "sc"}
            elif "audius.co/" in candidate.lower() and "/stream" not in candidate.lower():
                au_stream = await self._resolve_audius_permalink(candidate)
                if self._is_valid_audio_url(au_stream):
                    return {"ok": True, "url": au_stream, "source": "audius"}
            elif self._is_valid_audio_url(candidate):
                return {"ok": True, "url": candidate, "source": info.get("s") or "direct"}

        # 2. Tarona sahifa havolasi bo'lsa, to'g'ridan-to'g'ri MP3 ni yechish
        raw_u = str(info.get("u") or info.get("link") or "")
        page_url = info.get("page_url") or (
            raw_u if raw_u.startswith("http") and (
                info.get("s") == "tarona"
                or any(dom in raw_u.lower() for dom in ("tarona", "muzfm", "mp3uz"))
            ) else None
        )
        if page_url:
            direct_mp3 = await self._resolve_tarona_direct_mp3(page_url)
            if self._is_valid_audio_url(direct_mp3):
                return {"ok": True, "url": direct_mp3, "source": "tarona"}

        # 3. Tarona / Deezer / iTunes qidiruvlari orqali real preview/MP3 olish
        if q:
            tarona_hits = await self._search_tarona(q, limit=3)
            for hit in tarona_hits:
                u = hit.get("preview") or hit.get("u") or ""
                if self._is_valid_audio_url(u):
                    return {"ok": True, "url": u, "source": "tarona"}
                if hit.get("page_url"):
                    resolved = await self._resolve_tarona_direct_mp3(hit["page_url"])
                    if self._is_valid_audio_url(resolved):
                        return {"ok": True, "url": resolved, "source": "tarona"}

            deezer_hits = await self._search_deezer(q, limit=3)
            for hit in deezer_hits:
                dz = hit.get("preview") or hit.get("u")
                if self._is_valid_audio_url(dz):
                    return {"ok": True, "url": dz, "source": "deezer"}

            itunes_hits = await self._search_itunes(q, limit=3)
            for hit in itunes_hits:
                it = hit.get("preview") or hit.get("u")
                if self._is_valid_audio_url(it):
                    return {"ok": True, "url": it, "source": "itunes"}

        # 4. yt-dlp orqali YouTube audio stream URL olish (JS runtime + multi-client fallback)
        yt_id = info.get("y") or (info.get("id") if info.get("s") == "yt" else None)
        if yt_id or q:
            try:
                import yt_dlp
                has_yt_id = bool(yt_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", str(yt_id)))
                target = f"https://www.youtube.com/watch?v={yt_id}" if has_yt_id else f"ytsearch1:{q} audio"

                def _extract_stream() -> Optional[str]:
                    client_sets = [
                        ["tv", "ios", "android", "mweb"],
                        ["android", "web"],
                    ]
                    for clients in client_sets:
                        try:
                            opts = self._build_yt_dlp_opts({
                                "format": "bestaudio/best",
                                "skip_download": True,
                                "extractor_args": {"youtube": {"player_client": clients}},
                            })
                            with yt_dlp.YoutubeDL(opts) as ydl:
                                data = ydl.extract_info(target, download=False)
                                if isinstance(data, dict) and data.get("entries"):
                                    data = data["entries"][0]
                                if isinstance(data, dict) and data.get("url"):
                                    return data["url"]
                        except Exception:
                            continue
                    return None

                stream_url = await asyncio.to_thread(_extract_stream)
                if stream_url and str(stream_url).startswith("http"):
                    return {"ok": True, "url": stream_url, "source": "yt_dlp"}
            except Exception as e:
                logger.debug(f"yt-dlp stream extraction xatoligi: {e}")

            # 5. Agar YouTube ID ma'lum bo'lsa va yt-dlp bloklansa, Piped/Invidious audio oqimini sinash
            if yt_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", str(yt_id)):
                piped_url = await self._resolve_piped_audio_stream(str(yt_id))
                if piped_url:
                    return {"ok": True, "url": piped_url, "source": "piped"}

        return {
            "ok": False,
            "error": "stream_not_found",
            "msg": "Ushbu trek uchun haqiqiy audio oqimi topilmadi.",
        }

    async def download_track_mp3(
        self,
        search_query: str,
        track_info: Optional[Dict[str, Any]] = None
    ) -> DownloadResult:
        """
        Qo'shiq nomi bo'yicha to'liq MP3 faylini YouTube yoki zaxira ochiq audio orqali yuklab olish.
        """
        preview_url = None
        track_title = search_query
        track_artist = ""
        yt_id = None

        if track_info:
            cand = track_info.get("preview") or track_info.get("u") or track_info.get("url")
            preview_url = cand if self._is_valid_audio_url(cand) else None
            track_title = track_info.get("title") or track_info.get("t") or search_query
            track_artist = track_info.get("artist") or track_info.get("a") or ""
            yt_id = track_info.get("y") or (track_info.get("id") if track_info.get("s") == "yt" else None)

        # 1. Agar to'g'ridan-to'g'ri to'liq audio URL bo'lsa (30s preview bundan mustasno — uni YouTube/Tarona/Audius dan keyin ishlatamiz)
        direct_candidate = search_query if self._is_valid_audio_url(search_query) else None
        if not direct_candidate and track_info:
            for k in ("url", "u", "preview", "link"):
                v = track_info.get(k)
                if not v or not isinstance(v, str):
                    continue
                if "api-v2.soundcloud.com" in v:
                    v = await self._resolve_soundcloud_stream(v)
                elif "audius.co/" in v.lower() and "/stream" not in v.lower():
                    v = await self._resolve_audius_permalink(v)
                if self._is_valid_audio_url(v) and not self._is_preview_audio_url(v):
                    direct_candidate = v
                    break

        if direct_candidate:
            res = await self.downloader.download_direct_audio(direct_candidate, title=track_title)
            if res.success:
                return res

        # 2. Agar trek Tarona bazasiga tegishli bo'lsa (to'g'ridan-to'g'ri to'liq MP3 olish)
        if track_info and (track_info.get("s") == "tarona" or str(track_info.get("id", "")).startswith("tarona_")):
            tarona_res = await self._download_tarona_mp3(track_info, title=track_title)
            if tarona_res and tarona_res.success:
                return tarona_res

        # 3. To'g'ridan-to'g'ri YouTube video URL yoki aniqlangan video ID orqali yuklash
        target_yt_url = None
        if yt_id and len(str(yt_id)) == 11:
            target_yt_url = f"https://www.youtube.com/watch?v={yt_id}"
        else:
            found_id = self.downloader._find_youtube_video_id(search_query)
            if found_id:
                target_yt_url = f"https://www.youtube.com/watch?v={found_id}"
            else:
                target_yt_url = f"ytsearch1:{search_query} audio"

        res = await self.downloader.download_audio(target_yt_url)
        if res.success and res.file_path:
            return res

        # 4. Tarona bazasidan to'liq MP3 qidirib yuklab olish (30s previewdan ustun!)
        tarona_fallback = await self._download_tarona_mp3(search_query, title=track_title)
        if tarona_fallback and tarona_fallback.success:
            return tarona_fallback

        # 5. Audius Discovery orqali to'liq MP3 zaxira qidiruvi
        audius_url = await self._search_audius_stream(search_query)
        if audius_url:
            au_res = await self.downloader.download_direct_audio(audius_url, title=track_title)
            if au_res.success:
                return au_res

        # 6. Agar YouTube / to'liq manbalar ishlamasa va trekda haqiqiy audio preview bo'lsa:
        if preview_url and self._is_valid_audio_url(preview_url):
            logger.info(f"To'liq manbalar ishlamadi, mavjud audio preview yuklanmoqda: {preview_url}")
            direct_res = await self.downloader.download_direct_audio(str(preview_url), title=track_title)
            if direct_res.success:
                return direct_res

        # 7. Deezer qidiruvidan preview topishga urinish
        try:
            deezer_tracks = await self._search_deezer(search_query, limit=1)
            if deezer_tracks and deezer_tracks[0].get("preview"):
                dz_preview = deezer_tracks[0]["preview"]
                logger.info(f"Deezer preview orqali yuklanmoqda: {dz_preview}")
                direct_res = await self.downloader.download_direct_audio(dz_preview, title=track_title)
                if direct_res.success:
                    return direct_res
        except Exception as e:
            logger.warning(f"Deezer fallback xatoligi: {e}")

        # 8. iTunes qidiruvidan preview topishga urinish
        try:
            itunes_tracks = await self._search_itunes(search_query, limit=1)
            if itunes_tracks and itunes_tracks[0].get("preview"):
                it_preview = itunes_tracks[0]["preview"]
                logger.info(f"iTunes preview orqali yuklanmoqda: {it_preview}")
                direct_res = await self.downloader.download_direct_audio(it_preview, title=track_title)
                if direct_res.success:
                    return direct_res
        except Exception as e:
            logger.warning(f"iTunes fallback xatoligi: {e}")

        # Agar barcha usullar natija bermasa, dastlabki yt-dlp xatosini qaytarish
        return res

    async def recognize_audio(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Ovozli xabar yoki audio fayldan qo'shiqni aniqlash (Shazam).
        """
        try:
            from shazamio import Shazam
            shazam = Shazam()
            out = await shazam.recognize(file_path)
            track = out.get("track")
            if not track:
                return None
            return {
                "id": track.get("key", str(hash(track.get("title", "")))),
                "title": track.get("title", "Noma'lum"),
                "artist": track.get("subtitle", "Noma'lum"),
                "genre": track.get("genres", {}).get("primary", "Musiqa"),
                "cover": track.get("images", {}).get("coverart"),
            }
        except Exception as e:
            logger.error(f"Shazam aniqlash xatoligi: {e}")
            return None


music_service = MusicService()
