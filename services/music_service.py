"""
Qo'shiq qidirish va yuklab olish xizmati (Deezer API + iTunes API + yt-dlp)
"""
import asyncio
import json
import logging
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from pathlib import Path
import aiohttp
from config import config, BASE_DIR
from services.downloader import MediaDownloader, DownloadResult, media_downloader

logger = logging.getLogger(__name__)


class MusicService:
    """Musiqa qidiruv va yuklab olish servisi."""

    def __init__(self):
        self.downloader = media_downloader

    async def search_tracks(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Tarona, Deezer va iTunes ochiq API lari orqali qo'shiqlarni keng va juda tez qidiradi (1-2 soniyada).
        Dastlab Tarona va Deezer orqali, so'ngra iTunes va lokal kesh orqali natijalarni to'ldiradi.
        """
        clean_q = str(query or "").strip()
        if not clean_q:
            return []

        # 1. Tarona, Deezer va iTunes ochiq API larini parallel (bir vaqtda) ishga tushirish
        tasks = [
            self._search_tarona(clean_q, limit=limit),
            self._search_deezer(clean_q, limit=limit),
            self._search_itunes(clean_q, limit=limit),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tarona_tracks = results[0] if isinstance(results[0], list) else []
        deezer_tracks = results[1] if isinstance(results[1], list) else []
        itunes_tracks = results[2] if isinstance(results[2], list) else []

        # 2. Lokal katalog (data/music_home.json) qidiruvi
        local_tracks = self._search_local_home(clean_q, limit=limit)

        # Barcha manbalarni birlashtirish va takrorlarni olib tashlash
        seen_keys = set()
        merged: List[Dict[str, Any]] = []

        for tr in (tarona_tracks or []) + (deezer_tracks or []) + (itunes_tracks or []) + (local_tracks or []):
            k = f"{tr.get('artist', '').lower()}|{tr.get('title', '').lower()}"
            if k not in seen_keys:
                seen_keys.add(k)
                merged.append(tr)
                if len(merged) >= limit:
                    break

        if merged:
            return merged

        # 3. Agar barcha ochiq API lar bo'sh bo'lsa, YouTube fallback
        return await self._fallback_youtube_search(clean_q, limit=limit)

    async def _search_tarona(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Tarona / Muzfm o'zbek musiqa bazasi orqali qo'shiqlarni qidirish."""
        clean_q = query.strip()
        if not clean_q:
            return []

        search_urls = [
            f"https://muzfm.uz/search?q={urllib.parse.quote(clean_q)}",
            f"https://muzfm.org/search?q={urllib.parse.quote(clean_q)}",
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uz,en;q=0.9",
        }

        for url in search_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        if resp.status == 200:
                            if not hasattr(resp, "text"):
                                continue
                            text_raw = resp.text() if callable(resp.text) else resp.text
                            html = await text_raw if asyncio.iscoroutine(text_raw) else str(text_raw)
                            if not isinstance(html, str) or len(html) < 200 or "track-item" not in html:
                                continue

                            track_blocks = re.findall(
                                r'<div class="track-item[^"]*js-item"[^>]*>.*?(?=<div class="track-item|$)',
                                html,
                                re.DOTALL
                            )
                            tracks: List[Dict[str, Any]] = []
                            for b in track_blocks:
                                id_m = re.search(r'data-songid="([^"]+)"', b)
                                link_m = re.search(r'<a[^>]+class="track-link"[^>]+href="([^"]+)"', b)
                                artist_m = re.search(r'<div class="track-subtitle artist[^>]*>\s*([^<]+)\s*</div>', b)
                                title_m = re.search(r'<div class="track-title song[^>]*>\s*([^<]+)\s*</div>', b)
                                time_m = re.search(r'<div class="track-time time">\s*([^<]+)\s*</div>', b)
                                img_m = re.search(r'<img[^>]+src="([^"]+)"', b)

                                if link_m and title_m:
                                    artist = artist_m.group(1).strip() if artist_m else "Noma'lum"
                                    title = title_m.group(1).strip()
                                    link = link_m.group(1).strip()
                                    song_id = id_m.group(1) if id_m else re.sub(r'[^a-zA-Z0-9_-]', '', link.split('/')[-1])
                                    dur_str = time_m.group(1).strip() if time_m else "0"
                                    dur_sec = 0
                                    if ":" in dur_str:
                                        parts = dur_str.split(":")
                                        if len(parts) == 2:
                                            dur_sec = int(parts[0]) * 60 + int(parts[1])
                                        elif len(parts) == 3:
                                            dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

                                    cover = img_m.group(1).strip() if img_m else None
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
                            if tracks:
                                return tracks
            except Exception as e:
                logger.debug(f"Tarona qidiruv xatosi ({url}): {e}")

        return []

    async def _resolve_tarona_direct_mp3(self, link_or_track: Any) -> Optional[str]:
        """Tarona sahifasi havolasidan to'g'ridan-to'g'ri .mp3 audio URL ni ajratib olish."""
        target_url = link_or_track
        if isinstance(link_or_track, dict):
            u = link_or_track.get("u") or link_or_track.get("preview") or link_or_track.get("link")
            target_url = str(u or "")

        if not target_url or not target_url.startswith("http"):
            return None

        # Agar allaqachon to'g'ridan-to'g'ri .mp3 havola bo'lsa
        if ".mp3" in target_url:
            return target_url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(target_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        if hasattr(resp, "text"):
                            text_raw = resp.text() if callable(resp.text) else resp.text
                            html = await text_raw if asyncio.iscoroutine(text_raw) else str(text_raw)
                            mp3_m = re.search(r'href="([^"]+\.mp3[^"]*)"', html)
                            if not mp3_m:
                                mp3_m = re.search(r'src="([^"]+\.mp3[^"]*)"', html)
                            if not mp3_m:
                                mp3_m = re.search(r'https?://[^\s"\'<>]+\.mp3', html)
                            if mp3_m:
                                return mp3_m.group(1) if "(" in str(mp3_m.re) else mp3_m.group(0)
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
                         home_data.get("fresh", []))
            q_lower = query.lower()
            matches = []
            seen = set()
            for it in all_items:
                t = it.get("t", "")
                a = it.get("a", "")
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
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "ios", "mweb"]
                    }
                },
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                results = []
                if info and "entries" in info:
                    for entry in info["entries"]:
                        title = entry.get("title", "Noma'lum")
                        artist = entry.get("uploader", "YouTube")
                        duration = entry.get("duration", 0)
                        yt_id = entry.get("id")
                        results.append({
                            "id": yt_id,
                            "title": title,
                            "artist": artist,
                            "duration": duration,
                            "preview": None,
                            "cover": f"https://i.ytimg.com/vi/{yt_id}/mqdefault.jpg" if yt_id else None,
                            "link": entry.get("url"),
                            "t": title,
                            "a": artist,
                            "d": duration,
                            "c": f"https://i.ytimg.com/vi/{yt_id}/mqdefault.jpg" if yt_id else None,
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
            preview_url = track_info.get("preview") or track_info.get("u")
            track_title = track_info.get("title") or track_info.get("t") or search_query
            track_artist = track_info.get("artist") or track_info.get("a") or ""
            yt_id = track_info.get("y") or (track_info.get("id") if track_info.get("s") == "yt" else None)

        # 1. Agar to'g'ridan-to'g'ri audio URL bo'lsa (masalan Deezer preview yoki to'g'ridan-to'g'ri CDN)
        if search_query.startswith("http") and (search_query.endswith(".mp3") or "preview" in search_query or "deezer" in search_query):
            res = await self.downloader.download_direct_audio(search_query, title=track_title)
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

        # 4. Agar YouTube bot-detection / 429 tufayli ishlamasa va trekda preview bo'lsa:
        if preview_url and str(preview_url).startswith("http"):
            logger.info(f"YouTube xatosi, mavjud audio preview yuklanmoqda: {preview_url}")
            direct_res = await self.downloader.download_direct_audio(str(preview_url), title=track_title)
            if direct_res.success:
                return direct_res

        # 5. Tarona bazasidan to'liq MP3 qidirib yuklab olish
        tarona_fallback = await self._download_tarona_mp3(search_query, title=track_title)
        if tarona_fallback and tarona_fallback.success:
            return tarona_fallback

        # 6. Deezer qidiruvidan preview topishga urinish
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

        # 5. iTunes qidiruvidan preview topishga urinish
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
