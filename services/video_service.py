"""
Video xizmati (Dumaloq video - video note konvertori)
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional
from config import config

logger = logging.getLogger(__name__)

class VideoService:
    """Videolarni qayta ishlash xizmati."""

    @staticmethod
    async def convert_to_round_video(input_path: str) -> Optional[str]:
        """
        Videoni kvadrat (1:1) o'lchamga qirqib, Telegram dumaloq video xabari
        (video note - 384x384, mp4, aac) formatiga o'tkazadi.
        """
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            logger.error("ffmpeg topilmadi, video konvertatsiya qilib bo'lmaydi.")
            return None

        output_path = str(config.download_path / f"round_{uuid.uuid4().hex[:8]}.mp4")

        # ffmpeg buyrug'i: kvadratga qirqish, 384x384 o'lcham, h264/aac, 1-soniyada konvertatsiya (ultrafast, zerolatency, threads 0)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-threads", "0",
            "-i", input_path,
            "-t", "60",
            "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384:flags=fast_bilinear",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "64k",
            "-ac", "1",
            "-ar", "44100",
            "-movflags", "+faststart",
            output_path
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            else:
                logger.error(f"ffmpeg xatoligi: {stderr.decode(errors='ignore')}")
                return None
        except Exception as e:
            logger.exception(f"Video konvertatsiyasida xatolik: {e}")
            return None


video_service = VideoService()
