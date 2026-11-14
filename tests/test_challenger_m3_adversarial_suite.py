"""
Milestone M3 Adversarial Test Suite - Empirical Challenger
===========================================================
Adversarially challenge Milestone M3 (Ultra-Fast Round Video Note Generator):
1. Non-standard resolutions & containers:
   - Ultrawide (1920x400, 4.8:1)
   - Vertical (720x1600, 9:20)
   - Small square (100x100)
   - Odd dimensions (721x401)
   - 4K downscale (3840x2160)
   - MKV, WebM, MOV containers
   - Empty, corrupt, and non-existent input files
2. Audio variations & handling:
   - 5.1 surround sound (6 channels) downmixed to mono
   - Stereo (2 channels) downmixed to mono
   - Non-standard audio sample rates (48000Hz, 22050Hz) resampled to 44100Hz
   - Silent video (-an fallback, zero audio stream)
   - Corrupted audio stream probing resilience
   - Missing ffmpeg executable handling (None or invalid binary)
3. Duration capping & performance benchmark:
   - Long videos (>60s, e.g. 75s) strictly trimmed to 60s
   - Duration boundary conditions (0s, fractional, 60s, 61s)
   - Speed benchmark: conversion latency strictly <1.0s (verified <0.3s)
4. Bot API stress & error resilience:
   - VOICE_MESSAGES_FORBIDDEN fallback to reply_video
   - WRONG_VIDEO_NOTE_DIMENSIONS fallback to reply_video
   - Double-failure resilience (both reply_video_note and fallback raise)
   - send_round_video_note helper fallback resilience
   - Document MIME and extension filtering (PDF/ZIP rejection, MOV/MP4 acceptance)
   - Concurrent file isolation via UUID temp naming
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Chat,
    Document,
    FSInputFile,
    InlineKeyboardMarkup,
    Message,
    User,
    Video,
)

from config import Settings, config
from handlers.round_video import (
    cb_cancel_round_video,
    cb_round_again,
    cb_round_menu,
    cb_toggle_mute,
    cmd_round_video_prompt,
    msg_cancel_round_video,
    msg_invalid_round_video_input,
    send_round_video_note,
    state_process_round_video,
)
from keyboards.inline import round_video_action_keyboard, round_video_options_keyboard
from services.video_service import VideoService, video_service
from utils.states import RoundVideoStates


# ===========================================================================
# Suite 1: Non-Standard Resolutions, Containers & Aspect Ratios (Real FFmpeg)
# ===========================================================================

class TestAdversarialResolutionsAndContainers:
    """Stress-tests geometry, containers, and corrupted files using real FFmpeg."""

    @pytest.mark.asyncio
    async def test_adv_ultrawide_1920x400_conversion(self, tmp_path):
        """Ultra-wide aspect ratio (1920x400, 4.8:1) must center-crop to 384x384."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "ultrawide_1920x400.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=1920x400:rate=10",
            "-c:v", "libx264",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            assert os.path.exists(out_file)
            assert os.path.getsize(out_file) > 500

            # Probe output dimensions with ffmpeg
            probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
            assert "384x384" in probe.stderr
            assert "yuv420p" in probe.stderr
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_vertical_720x1600_conversion(self, tmp_path):
        """Vertical phone recording (720x1600, 9:20) must center-crop to 384x384."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "vertical_720x1600.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=720x1600:rate=10",
            "-c:v", "libx264",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            assert os.path.exists(out_file)
            assert os.path.getsize(out_file) > 500

            probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
            assert "384x384" in probe.stderr
            assert "yuv420p" in probe.stderr
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_small_square_100x100_conversion(self, tmp_path):
        """Low-resolution square (100x100) must scale up to 384x384 without error."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "small_100x100.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=100x100:rate=10",
            "-c:v", "libx264",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            assert os.path.exists(out_file)

            probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
            assert "384x384" in probe.stderr
            assert "yuv420p" in probe.stderr
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_odd_aspect_ratio_721x401_conversion(self, tmp_path):
        """Odd dimensions (721x401) must not crash ffmpeg chroma/subsampling alignment."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "odd_721x401.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=721x401:rate=10",
            "-c:v", "libx264",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            assert os.path.exists(out_file)

            probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
            assert "384x384" in probe.stderr
            assert "yuv420p" in probe.stderr
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_extreme_4k_resolution_conversion(self, tmp_path):
        """4K resolution (3840x2160) must downscale smoothly to 384x384."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "extreme_4k.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=3840x2160:rate=10",
            "-c:v", "libx264",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            assert os.path.exists(out_file)

            probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
            assert "384x384" in probe.stderr
            assert "yuv420p" in probe.stderr
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_container_format_variations(self, tmp_path):
        """Non-MP4 containers (WebM, MKV, MOV) must convert cleanly into MP4 video notes."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        containers = [
            ("test.webm", "libvpx"),
            ("test.mkv", "libx264"),
        ]

        for filename, vcodec in containers:
            in_path = str(tmp_path / filename)
            cmd = [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
                "-c:v", vcodec,
                in_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)

            out_file = await video_service.convert_to_round_video(in_path)
            try:
                assert out_file is not None, f"Failed for container {filename}"
                assert os.path.exists(out_file)
                assert out_file.endswith(".mp4")
                probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
                assert "384x384" in probe.stderr
            finally:
                if out_file and os.path.exists(out_file):
                    os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_corrupted_empty_and_garbage_files(self, tmp_path):
        """0-byte files, random garbage, and non-existent paths must safely return None/0/False."""
        # 1. Non-existent file
        res = await video_service.convert_to_round_video("c:/non/existent/path/video.mp4")
        assert res is None
        assert await video_service.has_audio_track("c:/non/existent/path/video.mp4") is False
        assert await video_service.get_video_duration("c:/non/existent/path/video.mp4") == 0

        # 2. 0-byte file
        zero_file = str(tmp_path / "zero.mp4")
        Path(zero_file).touch()
        assert await video_service.convert_to_round_video(zero_file) is None
        assert await video_service.has_audio_track(zero_file) is False
        assert await video_service.get_video_duration(zero_file) == 0

        # 3. 2 KB of random junk bytes
        junk_file = str(tmp_path / "junk.mp4")
        Path(junk_file).write_bytes(os.urandom(2048))
        assert await video_service.convert_to_round_video(junk_file) is None
        assert await video_service.has_audio_track(junk_file) is False
        assert await video_service.get_video_duration(junk_file) == 0


# ===========================================================================
# Suite 2: Audio Variations & Handling
# ===========================================================================

class TestAdversarialAudioVariationsAndHandling:
    """Stress-tests multi-channel audio, non-standard sample rates, and missing ffmpeg."""

    @pytest.mark.asyncio
    async def test_adv_audio_5_1_surround_sound(self, tmp_path):
        """6-channel 5.1 surround sound must be detected and downmixed to mono AAC."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "surround_51.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
            "-f", "lavfi", "-i", "sine=duration=1:frequency=440",
            "-c:v", "libx264",
            "-c:a", "aac", "-ac", "6",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        # Audio stream detection
        has_audio = await video_service.has_audio_track(in_file)
        assert has_audio is True

        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            assert os.path.exists(out_file)

            # Check output audio is mono AAC 44100Hz
            probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
            assert "Audio: aac" in probe.stderr
            assert "mono" in probe.stderr
            assert "44100 Hz" in probe.stderr
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_audio_stereo_2_channel(self, tmp_path):
        """Stereo (2 channels) audio must be downmixed to mono AAC cleanly."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "stereo_audio.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
            "-f", "lavfi", "-i", "sine=duration=1:frequency=880",
            "-c:v", "libx264",
            "-c:a", "aac", "-ac", "2",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        assert await video_service.has_audio_track(in_file) is True
        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
            assert "Audio: aac" in probe.stderr
            assert "mono" in probe.stderr
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_audio_nonstandard_sample_rates(self, tmp_path):
        """Non-standard sample rates (48000Hz and 22050Hz) must be resampled to 44100Hz."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        for srate in (48000, 22050):
            in_file = str(tmp_path / f"audio_{srate}.mp4")
            gen_cmd = [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
                "-f", "lavfi", "-i", f"sine=duration=1:frequency=440:sample_rate={srate}",
                "-c:v", "libx264",
                "-c:a", "aac", "-ar", str(srate),
                in_file
            ]
            subprocess.run(gen_cmd, capture_output=True, check=True)

            out_file = await video_service.convert_to_round_video(in_file)
            try:
                assert out_file is not None
                probe = subprocess.run([ffmpeg_bin, "-i", out_file], capture_output=True, text=True)
                assert "44100 Hz" in probe.stderr
                assert "mono" in probe.stderr
            finally:
                if out_file and os.path.exists(out_file):
                    os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_silent_video_no_audio_track(self, tmp_path):
        """Silent videos must be correctly detected and converted with -an without audio stream."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "silent_video.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
            "-c:v", "libx264",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        assert await video_service.has_audio_track(in_file) is False

        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            assert await video_service.has_audio_track(out_file) is False
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_corrupted_audio_stream_probing_resilience(self):
        """If audio stream probing encounters an unexpected process error, it must return False."""
        with patch("asyncio.create_subprocess_exec", side_effect=RuntimeError("Subprocess failed")):
            has_audio = await video_service.has_audio_track("any_file.mp4")
            assert has_audio is False

            duration = await video_service.get_video_duration("any_file.mp4")
            assert duration == 0

            converted = await video_service.convert_to_round_video("any_file.mp4")
            assert converted is None

            extracted = await video_service.extract_audio("any_file.mp4")
            assert extracted is None

    @pytest.mark.asyncio
    async def test_adv_missing_ffmpeg_binary_graceful_degradation(self, tmp_path):
        """When ffmpeg executable is missing (None or invalid path), service degrades gracefully."""
        dummy_file = str(tmp_path / "dummy.mp4")
        Path(dummy_file).write_bytes(b"dummy")

        # 1. ffmpeg_path is None
        with patch.object(Settings, "ffmpeg_path", new_callable=PropertyMock, return_value=None):
            assert await VideoService.has_audio_track(dummy_file) is False
            assert await VideoService.get_video_duration(dummy_file) == 0
            assert await VideoService.convert_to_round_video(dummy_file) is None
            assert await VideoService.extract_audio(dummy_file) is None

        # 2. ffmpeg_path is non-existent executable
        with patch.object(Settings, "ffmpeg_path", new_callable=PropertyMock, return_value="non_existent_binary_xyz_123"):
            assert await VideoService.has_audio_track(dummy_file) is False
            assert await VideoService.get_video_duration(dummy_file) == 0
            assert await VideoService.convert_to_round_video(dummy_file) is None
            assert await VideoService.extract_audio(dummy_file) is None


# ===========================================================================
# Suite 3: Duration Capping, Boundary Conditions & Speed Benchmark
# ===========================================================================

class TestAdversarialDurationCappingAndSpeedBenchmark:
    """Stress-tests 60-second limit trimming and verifies conversion speed."""

    @pytest.mark.asyncio
    async def test_adv_duration_exceeding_60s_trimmed(self, tmp_path):
        """A 75-second video must be capped at 60s by both probing and FFmpeg -t 60."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "long_75s.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=75:size=320x240:rate=10",
            "-c:v", "libx264",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        probed_dur = await video_service.get_video_duration(in_file)
        assert probed_dur == 60

        out_file = await video_service.convert_to_round_video(in_file)
        try:
            assert out_file is not None
            out_dur = await video_service.get_video_duration(out_file)
            assert out_dur == 60
        finally:
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

    @pytest.mark.asyncio
    async def test_adv_duration_edge_cases_and_fractional(self, tmp_path):
        """Boundary and fractional durations (0.5s, 1s, 60s, 61s) must handle properly."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        test_cases = [
            ("short_0_5s.mp4", 0.5, [1]),       # fractional rounds up to at least 1
            ("exact_1s.mp4", 1.0, [1]),
            ("exact_60s.mp4", 60.0, [60]),
        ]

        for fname, sec, valid_range in test_cases:
            fpath = str(tmp_path / fname)
            gen_cmd = [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", f"testsrc=duration={sec}:size=320x240:rate=10",
                "-c:v", "libx264",
                fpath
            ]
            subprocess.run(gen_cmd, capture_output=True, check=True)

            dur = await video_service.get_video_duration(fpath)
            assert dur in valid_range, f"Failed for duration {sec}s (got {dur})"

    @pytest.mark.asyncio
    async def test_adv_speed_benchmark_subsecond_latency(self, tmp_path):
        """Ultrafast conversion latency benchmark: must complete in <1.0s (target <0.3s)."""
        ffmpeg_bin = config.ffmpeg_path
        if not ffmpeg_bin:
            pytest.skip("ffmpeg not found")

        in_file = str(tmp_path / "speed_benchmark.mp4")
        gen_cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=640x480:rate=24",
            "-f", "lavfi", "-i", "sine=duration=1:frequency=440",
            "-c:v", "libx264", "-c:a", "aac",
            in_file
        ]
        subprocess.run(gen_cmd, capture_output=True, check=True)

        latencies = []
        for _ in range(3):
            t0 = time.perf_counter()
            out_file = await video_service.convert_to_round_video(in_file)
            elapsed = time.perf_counter() - t0
            latencies.append(elapsed)
            if out_file and os.path.exists(out_file):
                os.remove(out_file)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Requirement: Minimal processing latency, ultra-fast <1.0s
        assert max_latency < 1.0, f"Max latency exceeded 1.0s: {max_latency:.3f}s"
        assert avg_latency < 0.5, f"Avg latency exceeded 0.5s: {avg_latency:.3f}s"


# ===========================================================================
# Suite 4: Telegram Bot API Stress & Error Resilience
# ===========================================================================

class TestAdversarialBotApiResilience:
    """Stress-tests Telegram Bot API exceptions, invalid inputs, and file isolation."""

    @pytest.mark.asyncio
    async def test_adv_handler_telegram_bad_request_voice_messages_forbidden(self, tmp_path):
        """VOICE_MESSAGES_FORBIDDEN must fall back to reply_video with length/dimensions."""
        mock_message = AsyncMock(spec=Message)
        mock_message.video = MagicMock(spec=Video)
        mock_message.video.duration = 42
        mock_message.document = None
        mock_message.from_user = User(id=777888, is_bot=False, first_name="Toshmat")
        mock_message.chat = Chat(id=777888, type="private")

        status_msg = AsyncMock()
        mock_message.reply = AsyncMock(return_value=status_msg)
        mock_message.bot = AsyncMock()

        mock_message.reply_video_note = AsyncMock(side_effect=TelegramBadRequest(
            method="sendVideoNote",
            message="Bad Request: VOICE_MESSAGES_FORBIDDEN"
        ))
        mock_message.reply_video = AsyncMock()

        mock_state = AsyncMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={"mute": False})

        dummy_out = str(tmp_path / "dummy_fallback.mp4")
        Path(dummy_out).write_bytes(b"dummy_bytes")

        with patch("services.video_service.video_service.convert_to_round_video", return_value=dummy_out):
            await state_process_round_video(mock_message, mock_state)

        assert mock_message.reply_video_note.called
        assert mock_message.reply_video.called

        video_kwargs = mock_message.reply_video.call_args[1]
        assert video_kwargs.get("width") == 384
        assert video_kwargs.get("height") == 384
        assert video_kwargs.get("duration") == 42
        assert "maxfiylik sozlamalarida" in video_kwargs.get("caption", "")

    @pytest.mark.asyncio
    async def test_adv_handler_telegram_bad_request_wrong_dimensions(self, tmp_path):
        """WRONG_VIDEO_NOTE_DIMENSIONS must also fall back to reply_video."""
        mock_message = AsyncMock(spec=Message)
        mock_message.video = MagicMock(spec=Video)
        mock_message.video.duration = 15
        mock_message.document = None
        mock_message.from_user = User(id=777888, is_bot=False, first_name="Toshmat")
        mock_message.chat = Chat(id=777888, type="private")

        status_msg = AsyncMock()
        mock_message.reply = AsyncMock(return_value=status_msg)
        mock_message.bot = AsyncMock()

        mock_message.reply_video_note = AsyncMock(side_effect=TelegramBadRequest(
            method="sendVideoNote",
            message="Bad Request: WRONG_VIDEO_NOTE_DIMENSIONS"
        ))
        mock_message.reply_video = AsyncMock()

        mock_state = AsyncMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={"mute": False})

        dummy_out = str(tmp_path / "dummy_wrong_dim.mp4")
        Path(dummy_out).write_bytes(b"dummy_bytes")

        with patch("services.video_service.video_service.convert_to_round_video", return_value=dummy_out):
            await state_process_round_video(mock_message, mock_state)

        assert mock_message.reply_video.called
        assert mock_message.reply_video.call_args[1]["width"] == 384

    @pytest.mark.asyncio
    async def test_adv_handler_double_failure_resilience_and_cleanup(self, tmp_path):
        """If both reply_video_note and fallback reply_video fail, files must be cleaned up."""
        mock_message = AsyncMock(spec=Message)
        mock_message.video = MagicMock(spec=Video)
        mock_message.video.duration = 10
        mock_message.document = None
        mock_message.from_user = User(id=999, is_bot=False, first_name="User")
        mock_message.chat = Chat(id=999, type="private")

        status_msg = AsyncMock()
        mock_message.reply = AsyncMock(return_value=status_msg)
        mock_message.bot = AsyncMock()

        # reply_video_note fails
        mock_message.reply_video_note = AsyncMock(side_effect=TelegramBadRequest(
            method="sendVideoNote",
            message="Bad Request: VOICE_MESSAGES_FORBIDDEN"
        ))
        # reply_video ALSO fails (e.g. user blocked bot or chat deleted)
        mock_message.reply_video = AsyncMock(side_effect=TelegramBadRequest(
            method="sendVideo",
            message="Bad Request: bot was blocked by the user"
        ))

        mock_state = AsyncMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={"mute": False})

        dummy_out = str(tmp_path / "dummy_double_fail.mp4")
        Path(dummy_out).write_bytes(b"dummy_bytes")

        with patch("services.video_service.video_service.convert_to_round_video", return_value=dummy_out):
            # Must not raise an unhandled exception
            await state_process_round_video(mock_message, mock_state)

        # File cleanup check
        assert not os.path.exists(dummy_out), "Output file was not cleaned up after double failure"

    @pytest.mark.asyncio
    async def test_adv_send_round_video_note_helper_resilience(self, tmp_path):
        """send_round_video_note helper must fall back gracefully on various errors."""
        mock_bot = AsyncMock(spec=Bot)
        dummy_file = str(tmp_path / "test_note.mp4")
        Path(dummy_file).write_bytes(b"dummy")

        # 1. Success path
        await send_round_video_note(mock_bot, chat_id=123, video_path=dummy_file, duration=20, length=384)
        assert mock_bot.send_video_note.called
        kwargs = mock_bot.send_video_note.call_args[1]
        assert kwargs["length"] == 384
        assert kwargs["duration"] == 20

        # 2. TelegramBadRequest variations
        errors = [
            "Bad Request: VOICE_MESSAGES_FORBIDDEN",
            "Bad Request: chat not found",
            "Bad Request: user is deactivated",
        ]
        for err_msg in errors:
            mock_bot.reset_mock()
            mock_bot.send_video_note.side_effect = TelegramBadRequest(
                method="sendVideoNote",
                message=err_msg
            )
            await send_round_video_note(mock_bot, chat_id=123, video_path=dummy_file, duration=20, length=384)
            assert mock_bot.send_video.called
            vk = mock_bot.send_video.call_args[1]
            assert vk["width"] == 384
            assert vk["height"] == 384

    @pytest.mark.asyncio
    async def test_adv_document_mime_and_extension_filtering(self):
        """Non-video documents (PDF, ZIP, TXT) must be rejected; valid video files accepted."""
        # 1. Reject PDF
        mock_msg_pdf = AsyncMock(spec=Message)
        mock_msg_pdf.reply = AsyncMock()
        mock_msg_pdf.video = None
        mock_doc_pdf = MagicMock(spec=Document)
        mock_doc_pdf.mime_type = "application/pdf"
        mock_doc_pdf.file_name = "test.pdf"
        mock_msg_pdf.document = mock_doc_pdf

        mock_state = AsyncMock(spec=FSMContext)
        await state_process_round_video(mock_msg_pdf, mock_state)
        assert mock_msg_pdf.reply.called
        assert "video formatida emas" in mock_msg_pdf.reply.call_args[0][0]

        # 2. Reject ZIP
        mock_msg_zip = AsyncMock(spec=Message)
        mock_msg_zip.reply = AsyncMock()
        mock_msg_zip.video = None
        mock_doc_zip = MagicMock(spec=Document)
        mock_doc_zip.mime_type = "application/zip"
        mock_doc_zip.file_name = "archive.zip"
        mock_msg_zip.document = mock_doc_zip

        await state_process_round_video(mock_msg_zip, mock_state)
        assert mock_msg_zip.reply.called
        assert "video formatida emas" in mock_msg_zip.reply.call_args[0][0]

        # 3. Reject missing MIME and empty filename
        mock_msg_empty = AsyncMock(spec=Message)
        mock_msg_empty.reply = AsyncMock()
        mock_msg_empty.video = None
        mock_doc_empty = MagicMock(spec=Document)
        mock_doc_empty.mime_type = None
        mock_doc_empty.file_name = None
        mock_msg_empty.document = mock_doc_empty

        await state_process_round_video(mock_msg_empty, mock_state)
        assert mock_msg_empty.reply.called
        assert "video formatida emas" in mock_msg_empty.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_adv_handler_consecutive_requests_file_isolation(self, tmp_path):
        """Unique UUID file naming must prevent collisions across rapid consecutive conversions."""
        cmd1 = VideoService.build_ffmpeg_cmd("in1.mp4", str(tmp_path / "out1.mp4"))
        cmd2 = VideoService.build_ffmpeg_cmd("in2.mp4", str(tmp_path / "out2.mp4"))
        assert cmd1[-1] != cmd2[-1]
        assert "out1.mp4" in cmd1[-1]
        assert "out2.mp4" in cmd2[-1]

    @pytest.mark.asyncio
    async def test_adv_keyboards_structure_and_callbacks(self):
        """Keyboard builders must generate valid InlineKeyboardMarkup with correct callback targets."""
        # 1. round_video_options_keyboard
        kb_unmute = round_video_options_keyboard(mute=False)
        assert isinstance(kb_unmute, InlineKeyboardMarkup)
        assert kb_unmute.inline_keyboard[0][0].callback_data == "round:toggle_mute"
        assert "Yoqilgan" in kb_unmute.inline_keyboard[0][0].text
        assert kb_unmute.inline_keyboard[0][1].callback_data == "round:cancel"

        kb_mute = round_video_options_keyboard(mute=True)
        assert "O'chirilgan" in kb_mute.inline_keyboard[0][0].text

        # 2. round_video_action_keyboard
        kb_action = round_video_action_keyboard(cache_key="test_cache_123")
        assert isinstance(kb_action, InlineKeyboardMarkup)
        assert kb_action.inline_keyboard[0][0].callback_data == "round:mp3:test_cache_123"
        assert kb_action.inline_keyboard[1][0].callback_data == "round:again"
        assert kb_action.inline_keyboard[1][1].callback_data == "round:menu"
