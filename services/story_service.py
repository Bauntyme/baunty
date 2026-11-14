"""
Anonim Instagram Story ko'rish xizmati
Instagram public profil / stories yuklashda tezkor va ishonchli tizim
"""
import asyncio
import json
import logging
import re
import urllib.request
import urllib.parse
import uuid
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from config import config
from services.downloader import MediaDownloader, DownloadResult, media_downloader

logger = logging.getLogger(__name__)


def normalize_and_validate_media_url(url: str, base_domain: str = "t.me") -> Optional[str]:
    """
    Media URL'ni tekshiradi, normallashtiradi va emoji/stiker havolalarini filtrlaydi.
    - Emoji URLs: //telegram.org/img/emoji/..., /img/emoji/, /emoji/
    - Stiker yoki tgme ichki resurslari: /stickers/, tgme_widget, website_icon
    - Protocol-relative URL'larni 'https:' bilan normallashtiradi
    - Yaroqsiz yoki bo'sh bo'lsa None qaytaradi.
    """
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if not cleaned:
        return None

    cleaned_lower = cleaned.lower()

    # 1. Emoji havolalarini rad etish
    if (
        "telegram.org/img/emoji" in cleaned_lower
        or "/img/emoji" in cleaned_lower
        or "/emoji/" in cleaned_lower
        or ("emoji" in cleaned_lower and ("telegram" in cleaned_lower or "tg" in cleaned_lower))
    ):
        return None

    # 2. Stiker yoki tgme UI resurslarini rad etish
    if (
        "telegram.org/img/stickers" in cleaned_lower
        or "/stickers/" in cleaned_lower
        or "website_icon" in cleaned_lower
        or "tgme" in cleaned_lower
    ):
        return None

    # 3. Protocol-relative URL normallashtirish: //... -> https://...
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    elif cleaned.startswith("/"):
        cleaned = f"https://{base_domain}{cleaned}"
    elif not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        cleaned = f"https://{cleaned}"

    return cleaned


class StoryService:
    """Instagram va Telegram hikoyalarini (stories) anonim yuklab olish servisi."""

    def __init__(self):
        self.downloader = media_downloader
        self._profile_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ts: Dict[str, float] = {}

    def clean_username(self, raw_input: str) -> str:
        """Kiritilgan matndan Instagram/Telegram username'ni tozalab oladi."""
        text = str(raw_input or "").strip()
        # Agar URL bo'lsa
        if "instagram.com" in text:
            # stories/username/...
            match = re.search(r"instagram\.com/stories/([a-zA-Z0-9_\.]+)", text)
            if match:
                return match.group(1).rstrip("/")
            # instagram.com/username
            match = re.search(r"instagram\.com/([a-zA-Z0-9_\.]+)", text)
            if match:
                u = match.group(1).rstrip("/")
                if u not in ["p", "reel", "stories", "tv"]:
                    return u
        elif "t.me/" in text or "telegram.me/" in text:
            match = re.search(r"t\.me/([a-zA-Z0-9_]+)", text)
            if match:
                return match.group(1).rstrip("/")

        # @ belgisini olib tashlash
        cleaned = text.lstrip("@").strip()
        # Bo'sh joylar yoki ortiqcha belgilarni tozalash
        cleaned = re.sub(r"[^\w\.]", "", cleaned)
        return cleaned

    async def fetch_story(self, target: str) -> DownloadResult:
        """
        Instagram story yoki profil videosini anonim yuklab oladi.
        target: username yoki story havolasi
        """
        stories = await self.fetch_stories(target, limit=1)
        if stories:
            return stories[0]
        return DownloadResult(
            success=False,
            error="Hikoyalar (story) topilmadi yoki profil yopiq."
        )

    def normalize_and_validate_media_url(self, url: str, base_domain: str = "t.me") -> Optional[str]:
        """Media URL sanitizatsiya va normalizatsiyasi."""
        return normalize_and_validate_media_url(url, base_domain)

    async def fetch_stories(self, target: str, limit: int = 5, platform: str = "auto") -> List[DownloadResult]:
        """
        Instagram yoki Telegram hikoyalarini (rasm va videolar) yuklab oladi.
        Bir nechta story bo'lsa, ularning ro'yxatini qaytaradi.
        """
        try:
            target_clean = str(target or "").strip()

            # Telegram hikoyalari
            if platform == "tg" or "t.me/" in target_clean or "telegram.me/" in target_clean:
                return await self.fetch_telegram_stories(target_clean, limit=limit)

            # 1. Agar to'g'ridan-to'g'ri story ID si bo'lgan havola bo'lsa
            if "instagram.com/stories/" in target_clean and re.search(r"stories/[^/]+/\d+", target_clean):
                res = await self.downloader.download_video(target_clean)
                if res.success:
                    return [res]

            username = self.clean_username(target)
            if not username:
                return [DownloadResult(success=False, error="Instagram foydalanuvchi nomi noto'g'ri kiritildi.")]

            # 2. Ochiq web-viewer va zaxira API orqali hikoyalarni qidirish
            results = await self._fetch_stories_via_public_endpoints(username, limit=limit)
            if results:
                return results

            # 3. yt-dlp orqali story URL sini sinab ko'rish
            story_url = f"https://www.instagram.com/stories/{username}/"
            res = await self.downloader.download_video(story_url)
            if res.success:
                return [res]

            # Agar story 429 (Too Many Requests) yoki yopiq hisob bersa, qayta profile_url orqali 429 olmaslik
            if res.error and ("429" in res.error or "Too Many Requests" in res.error or "yopiq" in res.error.lower() or "private" in res.error.lower()):
                return [res]

            # 4. Agar story bo'lmasa, profilning eng yangi reels yoki postini yuklab berish
            profile_url = f"https://www.instagram.com/{username}/"
            logger.info(f"Story topilmadi, profile orqali harakat qilinmoqda: {profile_url}")
            res_profile = await self.downloader.download_video(profile_url)
            if res_profile.success:
                return [res_profile]
            elif res_profile.error:
                return [res_profile]

            return []
        except Exception as e:
            logger.warning(f"fetch_stories umumiy xatoligi: {e}")
            return [DownloadResult(success=False, error=f"Hikoyalarni yuklashda xatolik: {e}")]

    async def fetch_telegram_stories(self, target: str, limit: int = 5) -> List[DownloadResult]:
        """
        Telegram kanal hikoyalari yoki postlarini yuklab olish.
        """
        target_clean = str(target or "").strip()
        if "t.me/" in target_clean or "telegram.me/" in target_clean:
            res = await self.downloader.download_video(target_clean)
            if res.success:
                return [res]

        username = self.clean_username(target_clean)
        if not username:
            return [DownloadResult(success=False, error="Telegram foydalanuvchi yoki kanal nomi noto'g'ri kiritildi.")]

        def _scrape_tg():
            results: List[DownloadResult] = []
            try:
                url = f"https://t.me/s/{username}"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    }
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status == 200:
                        html = resp.read().decode("utf-8", errors="ignore")
                        video_matches = re.findall(r'<video[^>]+src="([^">]+)"', html)
                        photo_matches = re.findall(r'background-image:url\(\'([^\']+)\'\)', html)

                        media_urls = []
                        for vm in reversed(video_matches):
                            clean_vm = normalize_and_validate_media_url(vm)
                            if clean_vm and clean_vm not in [m[0] for m in media_urls]:
                                media_urls.append((clean_vm, False))
                            if len(media_urls) >= limit:
                                break
                        if len(media_urls) < limit:
                            for pm in reversed(photo_matches):
                                clean_pm = normalize_and_validate_media_url(pm)
                                if clean_pm and clean_pm not in [m[0] for m in media_urls]:
                                    media_urls.append((clean_pm, True))
                                if len(media_urls) >= limit:
                                    break

                        for m_url, is_img in media_urls:
                            dl = self.downloader._download_direct_stream(
                                url=m_url,
                                is_audio=False,
                                title=f"Telegram_{username}"
                            )
                            if dl and dl.success:
                                results.append(dl)
            except Exception as e:
                logger.debug(f"Telegram scraper xatoligi: {e}")
            return results

        try:
            results = await asyncio.to_thread(_scrape_tg)
            if results:
                return results
        except Exception as e:
            logger.debug(f"Telegram fetch xatoligi: {e}")

        # yt-dlp fallback
        try:
            tg_url = f"https://t.me/s/{username}"
            res = await self.downloader.download_video(tg_url)
            if res.success:
                return [res]
        except Exception as e:
            logger.debug(f"Telegram yt-dlp fallback xatoligi: {e}")

        return []

    async def _fetch_stories_via_public_endpoints(self, username: str, limit: int = 5) -> List[DownloadResult]:
        """
        Ochiq Instagram anonim viewer servislari orqali hikoyalarni olish.
        """
        def _scrape():
            results: List[DownloadResult] = []
            # Imginn ochiq scraping
            try:
                url = f"https://imginn.com/stories/{username}/"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    }
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status == 200:
                        html = resp.read().decode("utf-8", errors="ignore")
                        # Video va rasm havolalarini topish
                        video_matches = re.findall(r'<video[^>]+src="([^">]+)"', html)
                        img_matches = re.findall(r'<img[^>]+src="([^">]+)"[^>]+class="[^"]*story[^"]*"', html)
                        if not img_matches:
                            img_matches = re.findall(r'<img[^>]+src="(https://[^">]+scontent[^">]+)"', html)

                        media_urls = []
                        for vm in video_matches[:limit]:
                            media_urls.append((vm, False))
                        for im in img_matches[:limit]:
                            if len(media_urls) < limit:
                                media_urls.append((im, True))

                        for m_url, is_img in media_urls:
                            dl = self.downloader._download_direct_stream(
                                url=m_url,
                                is_audio=False,
                                title=f"Story_{username}"
                            )
                            if dl and dl.success:
                                results.append(dl)
            except Exception as e:
                logger.debug(f"Imginn story scraper xatoligi: {e}")

            return results

        try:
            return await asyncio.to_thread(_scrape)
        except Exception as e:
            logger.debug(f"Public endpoints xatoligi: {e}")
            return []

    async def get_user_profile_and_stories(self, username: str) -> Dict[str, Any]:
        """
        Web App (/api/story/ig?u=...) uchun Instagram profil va faol story ma'lumotlarini tayyorlaydi.
        """
        clean_u = self.clean_username(username)
        if not clean_u:
            return {"ok": False, "error": "bad_username"}

        now = time.time()
        # 5 daqiqalik kesh
        if clean_u in self._profile_cache and (now - self._cache_ts.get(clean_u, 0) < 300):
            return self._profile_cache[clean_u]

        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={clean_u}"
        items = []

        # Stories ro'yxatini shakllantirish
        stories = []
        try:
            stories = await self.fetch_stories(clean_u, limit=6)
            for idx, st in enumerate(stories, 1):
                # Filter out items with empty URLs (not st.direct_url)
                if not st or not st.direct_url or not str(st.direct_url).strip():
                    continue
                ext = Path(st.file_path).suffix.lower() if st.file_path else ".mp4"
                is_video = ext not in [".jpg", ".jpeg", ".png", ".webp"]
                items.append({
                    "id": f"{clean_u}_{idx}_{int(now)}",
                    "k": "video" if is_video else "image",
                    "t": st.thumbnail or avatar_url,
                    "u": str(st.direct_url).strip(),
                    "d": st.duration or (15 if is_video else 5),
                    "ts": int(now - idx * 3600),
                })
        except Exception as e:
            logger.info(f"Profil hikoyalarini olishda xatolik: {e}")

        # Agar real vaqtda faol story topilmasa, yolg'on namuna video bermasdan bo'sh ro'yxat qaytaramiz
        if not items:
            err_code = "story_not_found"
            try:
                for st in (stories or []):
                    if not st.success and st.error:
                        e_str = str(st.error).lower()
                        if "yopiq" in e_str or "private" in e_str:
                            err_code = "private"
                            break
                        elif "429" in e_str or "rate" in e_str or "too many" in e_str:
                            err_code = "rate"
                            break
                        elif "topilmadi" in e_str or "not found" in e_str:
                            err_code = "not_found"
                            break
            except Exception:
                pass
            return {
                "ok": False,
                "error": err_code,
                "name": clean_u,
                "pic": avatar_url,
                "verified": False,
                "items": [],
            }

        data = {
            "ok": True,
            "name": clean_u,
            "pic": avatar_url,
            "verified": clean_u.lower() in ["cristiano", "leomessi", "instagram", "shavkatmirziyoyev"],
            "items": items,
        }
        self._profile_cache[clean_u] = data
        self._cache_ts[clean_u] = now
        return data

    async def get_telegram_stories(self, username: str) -> Dict[str, Any]:
        """
        Web App (/api/story/tg?u=...) uchun Telegram kanal story ma'lumotlarini tayyorlaydi.
        """
        clean_u = self.clean_username(username)
        if not clean_u:
            return {"ok": False, "error": "bad_username"}

        now = time.time()
        avatar_url = f"https://api.dicebear.com/7.x/identicon/svg?seed={clean_u}"
        items = []
        ch_title = clean_u

        def _scrape_info():
            nonlocal avatar_url, ch_title, items
            try:
                url = f"https://t.me/s/{clean_u}"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    }
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    if resp.status == 200:
                        html = resp.read().decode("utf-8", errors="ignore")
                        tm = re.search(r'<div class="tgme_page_title"[^>]*><span dir="auto">([^<]+)</span>', html)
                        if tm:
                            ch_title = tm.group(1).strip()
                        pm = re.search(r'<img class="tgme_page_photo_image" src="([^"]+)"', html)
                        if pm:
                            av = pm.group(1).strip()
                            if av.startswith("//"):
                                av = f"https:{av}"
                            avatar_url = av
                        videos = re.findall(r'<video[^>]+src="([^">]+)"', html)
                        photos = re.findall(r'background-image:url\(\'([^\']+)\'\)', html)
                        idx = 1
                        seen_urls = set()
                        for v in reversed(videos[-5:]):
                            clean_v = normalize_and_validate_media_url(v)
                            if clean_v and clean_v not in seen_urls:
                                seen_urls.add(clean_v)
                                items.append({
                                    "id": f"tg_{clean_u}_{idx}_{int(now)}",
                                    "k": "video",
                                    "t": avatar_url,
                                    "u": clean_v,
                                    "d": 15,
                                    "ts": int(now - idx * 1800),
                                })
                                idx += 1
                        for p in reversed(photos[-5:]):
                            clean_p = normalize_and_validate_media_url(p)
                            if clean_p and clean_p not in seen_urls:
                                seen_urls.add(clean_p)
                                items.append({
                                    "id": f"tg_{clean_u}_{idx}_{int(now)}",
                                    "k": "image",
                                    "t": clean_p,
                                    "u": clean_p,
                                    "d": 5,
                                    "ts": int(now - idx * 3600),
                                })
                                idx += 1
            except Exception as e:
                logger.debug(f"Telegram info scraping failed: {e}")

        try:
            await asyncio.to_thread(_scrape_info)
        except Exception:
            pass

        # Eliminate ghost items! Never return dummy items with empty URLs ("u": "")
        data = {
            "ok": True,
            "name": ch_title,
            "pic": avatar_url,
            "pending": False,
            "items": items,
        }
        self._profile_cache[f"tg_{clean_u}"] = data
        return data


story_service = StoryService()
