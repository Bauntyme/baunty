"""
Qo'shiq qidirish va yuklab olish xizmati (Deezer API + yt-dlp)
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import aiohttp
from config import config
from services.downloader import MediaDownloader, DownloadResult

logger = logging.getLogger(__name__)


class MusicService:
    """Musiqa qidiruv va yuklab olish servisi."""

    def __init__(self):
        self.downloader = MediaDownloader()

    async def search_tracks(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Deezer ochiq API orqali qo'shiqlarni qidiradi (10 dan 25 tagacha natija).
        API kalit talab qilmaydi va juda tez javob beradi.
        """
        url = "https://api.deezer.com/search"
        params = {"q": query.strip(), "limit": max(5, min(limit, 50))}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
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
                        if tracks:
                            return tracks
                    else:
                        logger.warning(f"Deezer API javob kodi: {resp.status}")
        except Exception as e:
            logger.error(f"Deezer orqali qidirishda xatolik: {e}")

        # Agar Deezer ishlamasa, YouTube fallback qidiruv
        return await self._fallback_youtube_search(query, limit=limit)

    async def _fallback_youtube_search(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Deezer ishlamay qolganda YouTube orqali qidirish (fallback)."""
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

        if track_info:
            preview_url = track_info.get("preview") or track_info.get("u")
            track_title = track_info.get("title") or track_info.get("t") or search_query
            track_artist = track_info.get("artist") or track_info.get("a") or ""

        # 1. Agar to'g'ridan-to'g'ri audio URL bo'lsa (masalan Deezer preview)
        if search_query.startswith("http") and (search_query.endswith(".mp3") or "preview" in search_query or "deezer" in search_query):
            res = await self.downloader.download_direct_audio(search_query, title=track_title)
            if res.success:
                return res

        # 2. YouTube orqali yuklab olishga urinish (mobile player_client bilan)
        yt_search_url = f"ytsearch1:{search_query} audio"
        res = await self.downloader.download_audio(yt_search_url)
        if res.success and res.file_path:
            return res

        # 3. Agar YouTube bot-detection / 429 tufayli ishlamasa va trekda preview bo'lsa:
        if preview_url and preview_url.startswith("http"):
            logger.info(f"YouTube xatosi, Deezer audio preview yuklanmoqda: {preview_url}")
            direct_res = await self.downloader.download_direct_audio(preview_url, title=track_title)
            if direct_res.success:
                return direct_res

        # 4. Deezer qidiruvidan preview topishga urinish
        try:
            deezer_tracks = await self.search_tracks(search_query, limit=1)
            if deezer_tracks and deezer_tracks[0].get("preview"):
                dz_preview = deezer_tracks[0]["preview"]
                logger.info(f"Deezer preview orqali yuklanmoqda: {dz_preview}")
                direct_res = await self.downloader.download_direct_audio(dz_preview, title=track_title)
                if direct_res.success:
                    return direct_res
        except Exception as e:
            logger.warning(f"Deezer fallback xatoligi: {e}")

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
                "share_url": track.get("url"),
                "raw": track,
            }
        except ImportError:
            logger.info("Shazamio moduli o'rnatilmagan (yengil rejim). Audio aniqlash o'tkazib yuborildi.")
            return None
        except Exception as e:
            logger.error(f"Shazam orqali aniqlashda xatolik: {e}")
            return None


music_service = MusicService()
