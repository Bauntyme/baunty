"""
Universal media yuklab olish xizmati (yt-dlp asosida)
Instagram, TikTok, YouTube, Snapchat, Facebook va boshqalar
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
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
                    return DownloadResult(success=False, error="Media ma'lumotlarini olib bo'lmadi.")

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
            logger.warning(f"yt-dlp yuklab olish xatoligi: {err_msg}")
            if "Private video" in err_msg or "login" in err_msg.lower():
                return DownloadResult(success=False, error="Ushbu media yopiq (shaxsiy) hisobga tegishli.")
            return DownloadResult(success=False, error=f"Yuklab olishda xatolik: {err_msg[:100]}")
        except Exception as e:
            logger.exception(f"Kutilmagan xatolik: {e}")
            return DownloadResult(success=False, error=f"Kutilmagan xatolik yuz berdi: {str(e)[:100]}")

    def _sync_download_audio(self, url: str) -> DownloadResult:
        """Sinxron audio (MP3) ajratib olish funksiyasi."""
        file_prefix = str(uuid.uuid4())[:8]
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
                info = ydl.extract_info(url, download=True)
                if not info:
                    return DownloadResult(success=False, error="Audio ma'lumotlarini olib bo'lmadi.")

                if info.get("_type") == "playlist" and "entries" in info and info["entries"]:
                    info = info["entries"][0]

                # Faylni topish
                matches = list(self.download_dir.glob(f"{file_prefix}_*.mp3"))
                if not matches:
                    # Boshqa extension bilan yuklangan bo'lishi mumkin
                    matches = list(self.download_dir.glob(f"{file_prefix}_*"))

                if not matches:
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
            logger.exception(f"Audio ajratish xatoligi: {e}")
            return DownloadResult(success=False, error=f"Audio ajratib olinmadi: {str(e)[:100]}")

    async def download_video(self, url: str) -> DownloadResult:
        """Asinxron video yuklab olish."""
        return await asyncio.to_thread(self._sync_download_video, url)

    async def download_audio(self, url: str) -> DownloadResult:
        """Asinxron audio yuklab olish."""
        return await asyncio.to_thread(self._sync_download_audio, url)


# Yagona downloader nusxasi
media_downloader = MediaDownloader()
