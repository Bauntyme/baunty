"""
Video xizmati (Dumaloq video - video note konvertori)
"""
import asyncio
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional, List
from config import config

logger = logging.getLogger(__name__)


class VideoService:
    """Videolarni qayta ishlash xizmati."""

    @classmethod
    def build_ffmpeg_cmd(
        cls,
        input_path: str,
        output_path: str,
        mute: bool = False,
        has_audio: bool = True
    ) -> List[str]:
        """
        Dumaloq video note uchun ffmpeg buyrug'ini shakllantiradi.
        - 1:1 kvadratga qirqish va 384x384 o'lchamga keltirish
        - yuv420p piksel formati, H.264 main profile, level 3.1
        - ultrafast va zerolatency sozlamalari (tezkor konvertatsiya <1s)
        - audio trek mavjud bo'lsa aac, aks holda yoki mute=True bo'lsa -an
        """
        ffmpeg_bin = config.ffmpeg_path or "ffmpeg"
        cmd = [
            ffmpeg_bin,
            "-y",
            "-threads", "0",
            "-i", input_path,
            "-t", "60",
            "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384:flags=fast_bilinear",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-profile:v", "main",
            "-level", "3.1",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-crf", "28",
        ]
        if mute or not has_audio:
            cmd.append("-an")
        else:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "64k",
                "-ac", "1",
                "-ar", "44100",
            ])
        cmd.extend(["-movflags", "+faststart", output_path])
        return cmd

    @staticmethod
    async def has_audio_track(input_path: str) -> bool:
        """Video faylida audio oqimi (stream) mavjudligini tekshiradi."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin or not os.path.exists(input_path):
            return False
        try:
            process = await asyncio.create_subprocess_exec(
                ffmpeg_bin,
                "-i", input_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            err_text = stderr.decode(errors="ignore")
            return bool(re.search(r"Stream\s+#\d+:\d+.*:\s*Audio:", err_text) or "Audio:" in err_text)
        except Exception as e:
            logger.warning(f"Audio tekshiruvida xatolik: {e}")
            return False

    @staticmethod
    async def get_video_duration(input_path: str) -> int:
        """Video davomiyligini (soniyalarda, max 60s) aniqlaydi."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin or not os.path.exists(input_path):
            return 0
        try:
            process = await asyncio.create_subprocess_exec(
                ffmpeg_bin,
                "-i", input_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            err_text = stderr.decode(errors="ignore")
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err_text)
            if match:
                h, m, s = match.groups()
                dur = int(float(h) * 3600 + float(m) * 60 + float(s))
                return max(1, min(dur, 60))
            return 0
        except Exception as e:
            logger.warning(f"Davomiylik tekshiruvida xatolik: {e}")
            return 0

    @classmethod
    async def convert_to_round_video(
        cls,
        input_path: str,
        output_path: Optional[str] = None,
        mute: bool = False
    ) -> Optional[str]:
        """
        Videoni kvadrat (1:1) o'lchamga qirqib, Telegram dumaloq video xabari
        (video note - 384x384, mp4, yuv420p, profile main, level 3.1) formatiga o'tkazadi.
        """
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            logger.error("ffmpeg topilmadi, video konvertatsiya qilib bo'lmaydi.")
            return None

        if not os.path.exists(input_path):
            logger.error(f"Kiritilgan video fayl topilmadi: {input_path}")
            return None

        out_path = output_path or str(config.download_path / f"round_{uuid.uuid4().hex[:8]}.mp4")

        has_audio = False
        if not mute:
            has_audio = await cls.has_audio_track(input_path)

        cmd = cls.build_ffmpeg_cmd(
            input_path=input_path,
            output_path=out_path,
            mute=mute,
            has_audio=has_audio
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return out_path
            else:
                logger.error(f"ffmpeg xatoligi: {stderr.decode(errors='ignore')}")
                return None
        except Exception as e:
            logger.exception(f"Video konvertatsiyasida xatolik: {e}")
            return None

    @classmethod
    async def extract_audio(
        cls,
        input_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """Video fayldan audio trekni (MP3) ajratib oladi."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin or not os.path.exists(input_path):
            return None
        out_path = output_path or str(config.download_path / f"audio_{uuid.uuid4().hex[:8]}.mp3")
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", input_path,
            "-vn",
            "-c:a", "libmp3lame",
            "-q:a", "2",
            out_path
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            if process.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return out_path
            return None
        except Exception as e:
            logger.exception(f"Audio ajratishda xatolik: {e}")
            return None


video_service = VideoService()
