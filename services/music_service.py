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

    async def search_tracks(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Deezer ochiq API orqali qo'shiqlarni qidiradi.
        API kalit talab qilmaydi va juda tez javob beradi.
        """
        url = "https://api.deezer.com/search"
        params = {"q": query.strip(), "limit": limit}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tracks = []
                        for item in data.get("data", []):
                            tracks.append({
                                "id": item.get("id"),
                                "title": item.get("title_short", item.get("title", "Noma'lum")),
                                "artist": item.get("artist", {}).get("name", "Noma'lum"),
                                "duration": item.get("duration", 0),
                                "preview": item.get("preview"),  # 30 soniyalik MP3 havola
                                "cover": item.get("album", {}).get("cover_medium"),
                                "link": item.get("link"),
                            })
                        return tracks
                    else:
                        logger.warning(f"Deezer API javob kodi: {resp.status}")
        except Exception as e:
            logger.error(f"Deezer orqali qidirishda xatolik: {e}")

        # Agar Deezer ishlamasa, yt-dlp fallback qidiruv
        return await self._fallback_youtube_search(query, limit=limit)

    async def _fallback_youtube_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Deezer ishlamay qolganda YouTube orqali qidirish (fallback)."""
        def _search():
            import yt_dlp
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                results = []
                if info and "entries" in info:
                    for entry in info["entries"]:
                        results.append({
                            "id": entry.get("id"),
                            "title": entry.get("title", "Noma'lum"),
                            "artist": entry.get("uploader", "YouTube"),
                            "duration": entry.get("duration", 0),
                            "preview": None,
                            "cover": None,
                            "link": entry.get("url"),
                        })
                return results

        try:
            return await asyncio.to_thread(_search)
        except Exception as e:
            logger.error(f"YouTube fallback qidiruv xatosi: {e}")
            return []

    async def download_track_mp3(self, search_query: str) -> DownloadResult:
        """
        Qo'shiq nomi bo'yicha to'liq MP3 faylini YouTube orqali yuklab olish.
        """
        yt_search_url = f"ytsearch1:{search_query} audio"
        return await self.downloader.download_audio(yt_search_url)


music_service = MusicService()
