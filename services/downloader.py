"""
Universal media yuklab olish xizmati (yt-dlp asosida)
Instagram, TikTok, YouTube, Snapchat, Facebook va boshqalar
"""
import asyncio
import json
import logging
import os
import re
import urllib.request
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List
import yt_dlp
from config import config

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    success: bool
    file_path: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None
    file_size: Optional[int] = None
    thumbnail: Optional[str] = None
    direct_url: Optional[str] = None
    error: Optional[str] = None


class MediaDownloader:
    """Universal media yuklab oluvchi klass."""

    def __init__(self, download_dir: Optional[Path] = None):
        self.download_dir = download_dir or config.download_path

    def _sync_download_video(self, url: str) -> DownloadResult:
        """Sinxron video yuklab olish funksiyasi (thread ichida bajariladi)."""
        file_prefix = str(uuid.uuid4())[:8]
        output_template = str(self.download_dir / f"{file_prefix}_%(title).50s.%(ext)s")

        # Telegram bot fayl yuborish chegarasi: 50MB
        max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
        ffmpeg_bin = config.ffmpeg_path

        ydl_opts: Dict[str, Any] = {
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "max_filesize": max_bytes,
            "socket_timeout": 30,
            "retries": 3,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "mweb"]
                },
                "tiktok": {
                    "api_hostname": "api22-normal-c-useast2a.tiktokv.com"
                }
            },
            # Instagram, TikTok va YouTube uchun user-agent
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = ffmpeg_bin
            ydl_opts["format"] = "best[filesize<=48M]/bestvideo[filesize<=30M]+bestaudio[filesize<=15M]/best[ext=mp4]/best"
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = "best[ext=mp4][filesize<=48M]/best[filesize<=48M]/best"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    # Zaxira usullarga o'tish
                    return self._try_video_fallbacks(url, file_prefix, "Media ma'lumotlarini olib bo'lmadi.")

                # Carousel yoki playlist bo'lsa birinchi elementni olish
                if info.get("_type") == "playlist" and "entries" in info and info["entries"]:
                    info = info["entries"][0]

                # Yuklab olingan fayl yo'lini topish
                downloaded_file = None
                if "requested_downloads" in info and info["requested_downloads"]:
                    downloaded_file = info["requested_downloads"][0].get("filepath")
                elif "_filename" in info:
                    downloaded_file = info.get("_filename")

                if not downloaded_file or not Path(downloaded_file).is_file():
                    # Prefix bo'yicha papkadan qidirish
                    matches = list(self.download_dir.glob(f"{file_prefix}_*"))
                    if matches:
                        downloaded_file = str(matches[0])

                if not downloaded_file or not Path(downloaded_file).is_file():
                    fallback_res = self._try_video_fallbacks(url, file_prefix, "Fayl topilmadi.")
                    if fallback_res.success:
                        return fallback_res
                    return DownloadResult(success=False, error="Fayl yuklab olindi, lekin fayl topilmadi.")

                file_stat = Path(downloaded_file).stat()
                file_size = file_stat.st_size

                # Hajm tekshiruvi (50MB dan katta bo'lsa)
                if file_size > max_bytes:
                    return DownloadResult(
                        success=False,
                        file_path=downloaded_file,
                        file_size=file_size,
                        error=f"Fayl hajmi ({file_size // (1024*1024)} MB) Telegram cheklovidan (50 MB) oshib ketdi."
                    )

                return DownloadResult(
                    success=True,
                    file_path=downloaded_file,
                    title=info.get("title", "Video"),
                    duration=info.get("duration"),
                    file_size=file_size,
                    thumbnail=info.get("thumbnail"),
                    direct_url=info.get("url"),
                )

        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e)
            logger.warning(f"yt-dlp yuklab olish xatoligi: {err_msg}. Zaxira kanallar tekshirilmoqda...")
            fallback_res = self._try_video_fallbacks(url, file_prefix, err_msg)
            if fallback_res.success:
                return fallback_res

            if "Private video" in err_msg or "login" in err_msg.lower():
                return DownloadResult(success=False, error="Ushbu media yopiq (shaxsiy) hisobga tegishli.")
            return DownloadResult(success=False, error=f"Yuklab olishda xatolik: {err_msg[:100]}")
        except Exception as e:
            logger.exception(f"Kutilmagan xatolik: {e}")
            fallback_res = self._try_video_fallbacks(url, file_prefix, str(e))
            if fallback_res.success:
                return fallback_res
            return DownloadResult(success=False, error=f"Kutilmagan xatolik yuz berdi: {str(e)[:100]}")

    def _try_video_fallbacks(self, url: str, file_prefix: str, original_err: str) -> DownloadResult:
        """Video yuklab olishda barcha platformalar uchun zaxira mexanizmlar."""
        clean_url = url.strip()

        # 1. YouTube bo'lsa: Invidious va Piped
        if "youtube.com" in clean_url or "youtu.be" in clean_url:
            logger.info("YouTube zaxira kanali (Invidious) ishga tushirilmoqda...")
            inv_res = self._download_via_invidious(clean_url, is_audio=False, file_prefix=file_prefix)
            if inv_res and inv_res.success:
                return inv_res

        # 2. TikTok bo'lsa: TikWM suv belgisiz API
        if "tiktok.com" in clean_url:
            logger.info("TikTok zaxira kanali (TikWM) ishga tushirilmoqda...")
            tik_res = self._download_via_tikwm(clean_url, is_audio=False, file_prefix=file_prefix)
            if tik_res and tik_res.success:
                return tik_res

        # 3. Universal Cobalt API (YouTube, TikTok, Instagram, Snapchat, Facebook)
        logger.info("Universal Cobalt zaxira kanali ishga tushirilmoqda...")
        cobalt_res = self._download_via_cobalt(clean_url, is_audio=False, file_prefix=file_prefix)
        if cobalt_res and cobalt_res.success:
            return cobalt_res

        return DownloadResult(success=False, error=f"Yuklab olishda xatolik: {original_err[:100]}")

    def _sync_download_audio(self, url: str) -> DownloadResult:
        """Sinxron audio (MP3) ajratib olish funksiyasi."""
        file_prefix = str(uuid.uuid4())[:8]
        clean_url = url.strip()

        # To'g'ridan-to'g'ri MP3/audio havola bo'lsa (masalan Deezer preview yoki to'g'ridan-to'g'ri CDN)
        if clean_url.startswith("http") and (clean_url.endswith(".mp3") or clean_url.endswith(".m4a") or "preview" in clean_url or "deezer" in clean_url):
            direct_res = self._download_direct_stream(clean_url, is_audio=True, file_prefix=file_prefix)
            if direct_res and direct_res.success:
                return direct_res

        # Agar ytsearch so'rovi bo'lsa, uni oldindan to'g'ridan-to'g'ri YouTube video URL ga aylantirish
        effective_url = clean_url
        if clean_url.startswith("ytsearch"):
            query_part = re.sub(r"^ytsearch\d*:", "", clean_url).replace(" audio", "").strip()
            video_id = self._find_youtube_video_id(query_part)
            if video_id:
                effective_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"ytsearch so'rovi to'g'ridan-to'g'ri URL ga o'girildi: {effective_url}")

        output_template = str(self.download_dir / f"{file_prefix}_%(title).50s.%(ext)s")
        max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
        ffmpeg_bin = config.ffmpeg_path

        ydl_opts: Dict[str, Any] = {
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "max_filesize": max_bytes,
            "socket_timeout": 30,
            "retries": 3,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "mweb"]
                }
            },
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = ffmpeg_bin
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(effective_url, download=True)
                if not info:
                    return self._try_audio_fallbacks(effective_url, file_prefix, "Audio ma'lumotlarini olib bo'lmadi.")

                if info.get("_type") == "playlist" and "entries" in info and info["entries"]:
                    info = info["entries"][0]

                # Faylni topish
                matches = list(self.download_dir.glob(f"{file_prefix}_*.mp3"))
                if not matches:
                    matches = list(self.download_dir.glob(f"{file_prefix}_*"))

                if not matches:
                    fallback_res = self._try_audio_fallbacks(effective_url, file_prefix, "Audio fayli topilmadi.")
                    if fallback_res.success:
                        return fallback_res
                    return DownloadResult(success=False, error="Audio fayli topilmadi.")

                downloaded_file = str(matches[0])
                file_size = Path(downloaded_file).stat().st_size

                return DownloadResult(
                    success=True,
                    file_path=downloaded_file,
                    title=info.get("title", "Audio"),
                    duration=info.get("duration"),
                    file_size=file_size,
                    thumbnail=info.get("thumbnail"),
                )
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"Audio ajratishda xatolik: {err_msg}. Invidious/Cobalt fallback tekshirilmoqda...")
            fallback_res = self._try_audio_fallbacks(effective_url, file_prefix, err_msg)
            if fallback_res.success:
                return fallback_res
            return DownloadResult(success=False, error=f"Audio ajratib olinmadi: {err_msg[:100]}")

    def _try_audio_fallbacks(self, url: str, file_prefix: str, original_err: str) -> DownloadResult:
        """Audio ajratib olishda Invidious, Piped va Cobalt zaxira yo'llari."""
        clean_url = url.strip()

        # Agar YouTube havolasi bo'lsa
        if "youtube.com" in clean_url or "youtu.be" in clean_url or re.search(r"[a-zA-Z0-9_-]{11}", clean_url):
            inv_res = self._download_via_invidious(clean_url, is_audio=True, file_prefix=file_prefix)
            if inv_res and inv_res.success:
                return inv_res

        # TikTok audio
        if "tiktok.com" in clean_url:
            tik_res = self._download_via_tikwm(clean_url, is_audio=True, file_prefix=file_prefix)
            if tik_res and tik_res.success:
                return tik_res

        # Cobalt audio
        cobalt_res = self._download_via_cobalt(clean_url, is_audio=True, file_prefix=file_prefix)
        if cobalt_res and cobalt_res.success:
            return cobalt_res

        return DownloadResult(success=False, error=f"Audio ajratib olinmadi: {original_err[:100]}")

    def _find_youtube_video_id(self, query: str) -> Optional[str]:
        """Qo'shiq nomi bo'yicha YouTube dan 11 belgili video ID ni bir zumda topish (<400ms)."""
        clean_q = query.strip()
        if not clean_q:
            return None
        try:
            enc_q = urllib.parse.quote(f"{clean_q} audio")
            req = urllib.request.Request(
                f"https://www.youtube.com/results?search_query={enc_q}",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                matches = re.findall(r"/watch\?v=([a-zA-Z0-9_-]{11})", html)
                if matches:
                    return matches[0]
                matches_json = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                if matches_json:
                    return matches_json[0]
        except Exception as e:
            logger.debug(f"YouTube video ID qidiruv xatosi: {e}")
        return None

    def _download_via_tikwm(
        self,
        url: str,
        is_audio: bool = False,
        file_prefix: Optional[str] = None
    ) -> Optional[DownloadResult]:
        """TikTok videoni suv belgisiz (no-watermark) yoki MP3 audiosini TikWM orqali olish."""
        prefix = file_prefix or str(uuid.uuid4())[:8]
        try:
            api_url = f"https://www.tikwm.com/api/?url={urllib.parse.quote(url)}"
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("code") == 0 and "data" in data:
                    t_data = data["data"]
                    title = t_data.get("title", "TikTok Media")
                    duration = t_data.get("duration")
                    thumbnail = t_data.get("cover")
                    stream_url = t_data.get("music") if is_audio else (t_data.get("play") or t_data.get("wmplay"))

                    if stream_url:
                        res = self._download_direct_stream(
                            url=stream_url,
                            is_audio=is_audio,
                            file_prefix=prefix,
                            title=title
                        )
                        if res and res.success:
                            res.duration = duration
                            res.thumbnail = thumbnail
                            return res
        except Exception as e:
            logger.info(f"TikWM API xatoligi: {e}")
        return None

    def _download_direct_stream(
        self,
        url: str,
        is_audio: bool = True,
        file_prefix: Optional[str] = None,
        title: str = "Audio"
    ) -> Optional[DownloadResult]:
        """To'g'ridan-to'g'ri MP3/MP4 havolasidan yuklab olish (chunked stream)."""
        prefix = file_prefix or str(uuid.uuid4())[:8]
        ext = ".mp3" if is_audio else ".mp4"
        clean_title = re.sub(r'[\\/*?:"<>|]', "", title)[:40].strip() or ("audio" if is_audio else "video")
        target_path = self.download_dir / f"{prefix}_{clean_title}{ext}"
        max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "*/*"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_downloaded = 0
                with open(target_path, "wb") as f:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        total_downloaded += len(chunk)
                        if total_downloaded > max_bytes:
                            target_path.unlink(missing_ok=True)
                            return DownloadResult(
                                success=False,
                                error=f"Fayl hajmi ({total_downloaded // (1024 * 1024)} MB) Telegram cheklovidan oshib ketdi."
                            )
                        f.write(chunk)

            if target_path.exists() and target_path.stat().st_size > 0:
                file_size = target_path.stat().st_size
                return DownloadResult(
                    success=True,
                    file_path=str(target_path),
                    title=title,
                    file_size=file_size,
                    direct_url=url
                )
        except Exception as e:
            logger.warning(f"To'g'ridan-to'g'ri yuklab olish xatoligi: {e}")
            target_path.unlink(missing_ok=True)

        return None

    def _download_via_invidious(
        self,
        url: str,
        is_audio: bool = False,
        file_prefix: Optional[str] = None
    ) -> Optional[DownloadResult]:
        """Invidious va Piped ochiq API lari orqali YouTube dan yuklab olish."""
        clean_url = url.strip()
        m = re.search(r"(?:v=|\/|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})", clean_url)
        if not m:
            return None
        video_id = m.group(1)

        invidious_hosts = [
            "https://invidious.f5.si",
            "https://invidious.projectsegfau.lt",
        ]
        for host in invidious_hosts:
            try:
                api_url = f"{host}/api/v1/videos/{video_id}"
                req = urllib.request.Request(
                    api_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        title = data.get("title", "YouTube Media")
                        duration = data.get("lengthSeconds")
                        thumbnail = None
                        if data.get("videoThumbnails"):
                            thumbnail = data["videoThumbnails"][0].get("url")

                        stream_url = None
                        if is_audio:
                            for f in data.get("adaptiveFormats", []):
                                if "audio" in f.get("type", "") and f.get("url"):
                                    stream_url = f.get("url")
                                    break
                        else:
                            for f in data.get("formatStreams", []):
                                if "video/mp4" in f.get("type", "") and f.get("url"):
                                    stream_url = f.get("url")
                                    break
                            if not stream_url:
                                for f in data.get("adaptiveFormats", []):
                                    if "video/mp4" in f.get("type", "") and f.get("url"):
                                        stream_url = f.get("url")
                                        break

                        if stream_url:
                            res = self._download_direct_stream(
                                url=stream_url,
                                is_audio=is_audio,
                                file_prefix=file_prefix,
                                title=title
                            )
                            if res and res.success:
                                res.duration = duration
                                res.thumbnail = thumbnail
                                return res
            except Exception as e:
                logger.info(f"Invidious yuklab olish xatoligi ({host}): {e}")

        # Piped fallback
        piped_endpoints = [
            f"https://api.piped.private.coffee/streams/{video_id}",
        ]
        for ep in piped_endpoints:
            try:
                req = urllib.request.Request(ep, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        title = data.get("title", "YouTube Media")
                        duration = data.get("duration")
                        thumbnail = data.get("thumbnailUrl")
                        stream_url = None
                        if is_audio and data.get("audioStreams"):
                            stream_url = data["audioStreams"][0].get("url")
                        elif not is_audio and data.get("videoStreams"):
                            for vs in data["videoStreams"]:
                                if not vs.get("videoOnly") and vs.get("url"):
                                    stream_url = vs["url"]
                                    break
                            if not stream_url and data["videoStreams"]:
                                stream_url = data["videoStreams"][0].get("url")

                        if stream_url:
                            res = self._download_direct_stream(
                                url=stream_url,
                                is_audio=is_audio,
                                file_prefix=file_prefix,
                                title=title
                            )
                            if res and res.success:
                                res.duration = duration
                                res.thumbnail = thumbnail
                                return res
            except Exception as e:
                logger.info(f"Piped yuklab olish xatoligi ({ep}): {e}")

        return None

    def _download_via_cobalt(
        self,
        url: str,
        is_audio: bool = False,
        file_prefix: Optional[str] = None
    ) -> Optional[DownloadResult]:
        """Cobalt API zaxira xizmati orqali media yuklab olish (ko'p manzilli zaxira tizimi)."""
        clean_url = url.strip()
        # Agar ytsearch so'rovi bo'lsa, YouTube video ID sini aniqlash
        if clean_url.startswith("ytsearch"):
            query_part = re.sub(r"^ytsearch\d*:", "", clean_url).replace(" audio", "").strip()
            video_id = self._find_youtube_video_id(query_part)
            if video_id:
                clean_url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                return None

        # Cobalt API manzil(lar)i
        cobalt_endpoints = [
            os.getenv("COBALT_API_URL", "").strip(),
            "https://api.cobalt.tools",
            "https://cobalt-api.kwiatekm.tokyo",
            "https://cobalt.canine.tools",
            "https://api.server.v0.pw",
        ]
        cobalt_endpoints = [ep for ep in cobalt_endpoints if ep]

        payload = {
            "url": clean_url,
            "downloadMode": "audio" if is_audio else "auto",
        }
        if is_audio:
            payload["audioFormat"] = "mp3"

        for base_url in cobalt_endpoints:
            try:
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
                api_key = os.getenv("COBALT_API_KEY", "").strip()
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                req = urllib.request.Request(
                    base_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        stream_url = data.get("url")
                        if stream_url:
                            res = self._download_direct_stream(
                                url=stream_url,
                                is_audio=is_audio,
                                file_prefix=file_prefix,
                                title="Media"
                            )
                            if res and res.success:
                                return res
            except Exception as e:
                logger.info(f"Cobalt nusxasiga ulanishda xatolik ({base_url}): {e}")

        return None

    async def download_direct_audio(self, url: str, title: str = "Audio") -> DownloadResult:
        """To'g'ridan-to'g'ri audio havolasini asinxron yuklab olish."""
        res = await asyncio.to_thread(self._download_direct_stream, url, True, None, title)
        if res and res.success:
            return res
        return DownloadResult(success=False, error="Audio yuklab olinmadi.")

    async def download_video(self, url: str) -> DownloadResult:
        """Asinxron video yuklab olish."""
        return await asyncio.to_thread(self._sync_download_video, url)

    async def download_audio(self, url: str) -> DownloadResult:
        """Asinxron audio yuklab olish."""
        return await asyncio.to_thread(self._sync_download_audio, url)


# Yagona downloader nusxasi
media_downloader = MediaDownloader()
