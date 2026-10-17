"""
Anonim Instagram Story ko'rish xizmati
"""
import re
import logging
from typing import Optional, List, Dict, Any
from services.downloader import MediaDownloader, DownloadResult

logger = logging.getLogger(__name__)


class StoryService:
    """Instagram hikoyalarini (stories) anonim yuklab olish servisi."""

    def __init__(self):
        self.downloader = MediaDownloader()

    def clean_username(self, raw_input: str) -> str:
        """Kiritilgan matndan Instagram username'ni tozalab oladi."""
        text = raw_input.strip()
        # Agar URL bo'lsa
        if "instagram.com" in text:
            match = re.search(r"instagram\.com/(?:stories/)?([a-zA-Z0-9_\.]+)", text)
            if match:
                return match.group(1).rstrip("/")
        # @ belgisini olib tashlash
        return text.lstrip("@").strip()

    async def fetch_story(self, target: str) -> DownloadResult:
        """
        Instagram story yoki profil videosini anonim yuklab oladi.
        target: username yoki story havolasi
        """
        target_clean = target.strip()
        if "instagram.com/stories/" in target_clean and re.search(r"stories/[^/]+/\d+", target_clean):
            result = await self.downloader.download_video(target_clean)
            if result.success:
                return result

        username = self.clean_username(target)
        if not username:
            return DownloadResult(success=False, error="Instagram foydalanuvchi nomi noto'g'ri kiritildi.")

        # Story URL
        story_url = f"https://www.instagram.com/stories/{username}/"

        # Downloader orqali urinib ko'rish
        result = await self.downloader.download_video(story_url)

        if not result.success:
            # Agar to'g'ridan-to'g'ri story chiqmasa, oxirgi reels yoki post orqali
            profile_url = f"https://www.instagram.com/{username}/"
            logger.info(f"Story topilmadi, profile orqali harakat qilinmoqda: {profile_url}")
            result = await self.downloader.download_video(profile_url)

        return result


story_service = StoryService()
