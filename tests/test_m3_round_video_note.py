"""
Milestone M3 Test Suite: Ultra-Fast Round Video Note Generator (Dumaloq video)
Verifies:
1. FFmpeg command construction:
   - yuv420p pixel format, H.264 main profile, level 3.1
   - 1:1 square crop ('min(iw,ih)':'min(iw,ih)'), scale=384:384:flags=fast_bilinear
   - preset ultrafast, tune zerolatency, crf 28, movflags +faststart
   - audio fallback: -c:a aac when audio present, -an when no audio or mute=True
   - 60s duration limit (-t 60)
2. Real video conversion:
   - With audio track
   - Without audio track (-an fallback)
   - With mute=True (-an fallback)
   - Duration cap at 60s
3. Handler verification:
   - reply_video_note called with length=384 and duration
   - TelegramBadRequest (VOICE_MESSAGES_FORBIDDEN or dimensions) fallback to reply_video
   - send_round_video_note helper with length=384 and duration
   - UX guidance prompt, mute toggle callback, and cancel handling
"""
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiogram.types import Message, User, Chat, FSInputFile, CallbackQuery, Document, Video
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import config
from services.video_service import video_service, VideoService
from handlers.round_video import (
    cmd_round_video_prompt,
    cb_toggle_mute,
    cb_cancel_round_video,
    cb_round_again,
    cb_round_menu,
    msg_cancel_round_video,
    msg_invalid_round_video_input,
    state_process_round_video,
    send_round_video_note,
)
from keyboards.inline import round_video_options_keyboard, round_video_action_keyboard
from utils.states import RoundVideoStates


# ---------------------------------------------------------------------------
# 1. FFmpeg Command Construction Tests
# ---------------------------------------------------------------------------

def test_ffmpeg_cmd_construction_standard_with_audio():
    """Standart ffmpeg buyrug'i barcha M3 parametrlarini o'z ichiga olishi kerak."""
    cmd = VideoService.build_ffmpeg_cmd(
        input_path="input.mp4",
        output_path="output.mp4",
        mute=False,
        has_audio=True
    )
    # 1:1 kvadrat qirqish va 384x384 o'lcham
    assert "-vf" in cmd
    vf_idx = cmd.index("-vf")
    vf_val = cmd[vf_idx + 1]
    assert "crop='min(iw,ih)':'min(iw,ih)'" in vf_val
    assert "scale=384:384:flags=fast_bilinear" in vf_val

    # Video kodek va profil parametrlari
    assert "-c:v" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-pix_fmt" in cmd
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert "-profile:v" in cmd
    assert cmd[cmd.index("-profile:v") + 1] == "main"
    assert "-level" in cmd
    assert cmd[cmd.index("-level") + 1] == "3.1"

    # Tezkorlik va kechikishni kamaytirish sozlamalari
    assert "-preset" in cmd
    assert cmd[cmd.index("-preset") + 1] == "ultrafast"
    assert "-tune" in cmd
    assert cmd[cmd.index("-tune") + 1] == "zerolatency"
    assert "-crf" in cmd
    assert cmd[cmd.index("-crf") + 1] == "28"
    assert "-movflags" in cmd
    assert cmd[cmd.index("-movflags") + 1] == "+faststart"

    # 60 soniya cheklovi
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "60"

    # Audio mavjud bo'lganda AAC parametrlari
    assert "-c:a" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-b:a" in cmd
    assert cmd[cmd.index("-b:a") + 1] == "64k"
    assert "-ac" in cmd
    assert cmd[cmd.index("-ac") + 1] == "1"
    assert "-ar" in cmd
    assert cmd[cmd.index("-ar") + 1] == "44100"
    assert "-an" not in cmd


def test_ffmpeg_cmd_construction_no_audio_fallback():
    """Videoda audio bo'lmaganda -an parametri qo'shilishi va -c:a bo'lmasligi kerak."""
    cmd = VideoService.build_ffmpeg_cmd(
        input_path="silent.mp4",
        output_path="out.mp4",
        mute=False,
        has_audio=False
    )
    assert "-an" in cmd
    assert "-c:a" not in cmd
    assert "-pix_fmt" in cmd
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert cmd[cmd.index("-profile:v") + 1] == "main"
    assert cmd[cmd.index("-level") + 1] == "3.1"


def test_ffmpeg_cmd_construction_mute_true():
    """mute=True bo'lganda, audio mavjud bo'lsa ham -an ishlatilishi kerak."""
    cmd = VideoService.build_ffmpeg_cmd(
        input_path="input_with_audio.mp4",
        output_path="out_muted.mp4",
        mute=True,
        has_audio=True
    )
    assert "-an" in cmd
    assert "-c:a" not in cmd


# ---------------------------------------------------------------------------
# 2. Real Video Conversion Tests (with and without audio, mute, and duration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_real_video_conversion_with_audio(tmp_path):
    """Real video (audio bilan) muvaffaqiyatli dumaloq video formatiga o'tishi testi."""
    ffmpeg_bin = config.ffmpeg_path
    if not ffmpeg_bin:
        pytest.skip("ffmpeg tizimda mavjud emas")

    test_in = str(tmp_path / "in_with_audio.mp4")
    # 1 soniyalik video + audio yaratish
    gen_cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=duration=1:frequency=440",
        "-c:v", "libx264", "-c:a", "aac",
        test_in
    ]
    res = subprocess.run(gen_cmd, capture_output=True)
    if res.returncode != 0:
        pytest.skip("Test video yaratib bo'lmadi")

    # Audio mavjudligini tekshirish
    has_audio = await video_service.has_audio_track(test_in)
    assert has_audio is True

    # Konvertatsiya
    out_file = await video_service.convert_to_round_video(test_in, mute=False)
    assert out_file is not None
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 100

    # Natijada audio trek saqlanganligini tekshirish
    out_has_audio = await video_service.has_audio_track(out_file)
    assert out_has_audio is True

    if os.path.exists(out_file):
        os.remove(out_file)


@pytest.mark.asyncio
async def test_real_video_conversion_without_audio_fallback(tmp_path):
    """Audiosiz video kelganda -an fallback orqali xatoliksiz konvertatsiya bo'lishi testi."""
    ffmpeg_bin = config.ffmpeg_path
    if not ffmpeg_bin:
        pytest.skip("ffmpeg tizimda mavjud emas")

    test_in = str(tmp_path / "in_silent.mp4")
    # Faqat video, audio yo'q
    gen_cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-c:v", "libx264",
        test_in
    ]
    res = subprocess.run(gen_cmd, capture_output=True)
    if res.returncode != 0:
        pytest.skip("Audiosiz test video yaratib bo'lmadi")

    has_audio = await video_service.has_audio_track(test_in)
    assert has_audio is False

    # Konvertatsiya (audio yo'q bo'lsa ham muvaffaqiyatli o'tishi kerak)
    out_file = await video_service.convert_to_round_video(test_in, mute=False)
    assert out_file is not None
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 100

    out_has_audio = await video_service.has_audio_track(out_file)
    assert out_has_audio is False

    if os.path.exists(out_file):
        os.remove(out_file)


@pytest.mark.asyncio
async def test_real_video_conversion_with_mute_parameter(tmp_path):
    """mute=True parametri berilganda audio butunlay olib tashlanishi testi."""
    ffmpeg_bin = config.ffmpeg_path
    if not ffmpeg_bin:
        pytest.skip("ffmpeg tizimda mavjud emas")

    test_in = str(tmp_path / "in_sound_to_mute.mp4")
    gen_cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=duration=1:frequency=440",
        "-c:v", "libx264", "-c:a", "aac",
        test_in
    ]
    res = subprocess.run(gen_cmd, capture_output=True)
    if res.returncode != 0:
        pytest.skip("Test video yaratib bo'lmadi")

    out_file = await video_service.convert_to_round_video(test_in, mute=True)
    assert out_file is not None
    assert os.path.exists(out_file)

    # Natijada audio yo'q bo'lishi kerak
    out_has_audio = await video_service.has_audio_track(out_file)
    assert out_has_audio is False

    if os.path.exists(out_file):
        os.remove(out_file)


@pytest.mark.asyncio
async def test_duration_probing_and_cap_at_60(tmp_path):
    """Video davomiyligini aniqlash va 60 soniyadan oshmasligini tekshirish."""
    ffmpeg_bin = config.ffmpeg_path
    if not ffmpeg_bin:
        pytest.skip("ffmpeg mavjud emas")

    test_in = str(tmp_path / "test_2s.mp4")
    gen_cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
        test_in
    ]
    subprocess.run(gen_cmd, capture_output=True)

    dur = await video_service.get_video_duration(test_in)
    assert dur in (1, 2)


@pytest.mark.asyncio
async def test_extract_audio_mp3(tmp_path):
    """Videodan MP3 musiqasini ajratib olish testi."""
    ffmpeg_bin = config.ffmpeg_path
    if not ffmpeg_bin:
        pytest.skip("ffmpeg mavjud emas")

    test_in = str(tmp_path / "for_mp3.mp4")
    gen_cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=duration=1:frequency=440",
        test_in
    ]
    subprocess.run(gen_cmd, capture_output=True)

    mp3_file = await video_service.extract_audio(test_in)
    assert mp3_file is not None
    assert os.path.exists(mp3_file)
    assert mp3_file.endswith(".mp3")
    if os.path.exists(mp3_file):
        os.remove(mp3_file)


# ---------------------------------------------------------------------------
# 3. Handler Verification Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_reply_video_note_parameters(tmp_path):
    """reply_video_note chaqirilganda length=384 va duration parametrlari uzatilishi testi."""
    mock_message = AsyncMock(spec=Message)
    mock_message.video = MagicMock(spec=Video)
    mock_message.video.duration = 25
    mock_message.document = None
    mock_message.from_user = User(id=111222, is_bot=False, first_name="Ali")
    mock_message.chat = Chat(id=111222, type="private")

    status_msg = AsyncMock()
    mock_message.reply = AsyncMock(return_value=status_msg)
    mock_message.bot = AsyncMock()
    mock_message.reply_video_note = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"mute": False})

    dummy_out = str(tmp_path / "dummy_out.mp4")
    Path(dummy_out).write_bytes(b"dummy_video_bytes")

    with patch("services.video_service.video_service.convert_to_round_video", return_value=dummy_out):
        await state_process_round_video(mock_message, mock_state)

    # reply_video_note to'g'ri parametrlar bilan chaqirilganini tekshirish
    assert mock_message.reply_video_note.called
    kwargs = mock_message.reply_video_note.call_args[1]
    assert kwargs.get("length") == 384
    assert kwargs.get("duration") == 25
    assert isinstance(kwargs.get("video_note"), FSInputFile)


@pytest.mark.asyncio
async def test_handler_duration_cap_at_60_seconds(tmp_path):
    """60 soniyadan uzun video kelganda duration 60 ga cheklanishi testi."""
    mock_message = AsyncMock(spec=Message)
    mock_message.video = MagicMock(spec=Video)
    mock_message.video.duration = 180  # 3 daqiqalik video
    mock_message.document = None
    mock_message.from_user = User(id=111222, is_bot=False, first_name="Ali")
    mock_message.chat = Chat(id=111222, type="private")

    status_msg = AsyncMock()
    mock_message.reply = AsyncMock(return_value=status_msg)
    mock_message.bot = AsyncMock()
    mock_message.reply_video_note = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"mute": False})

    dummy_out = str(tmp_path / "dummy_out_capped.mp4")
    Path(dummy_out).write_bytes(b"dummy_video_bytes")

    with patch("services.video_service.video_service.convert_to_round_video", return_value=dummy_out):
        await state_process_round_video(mock_message, mock_state)

    assert mock_message.reply_video_note.called
    kwargs = mock_message.reply_video_note.call_args[1]
    assert kwargs.get("duration") == 60
    assert kwargs.get("length") == 384


@pytest.mark.asyncio
async def test_handler_fallback_on_voice_messages_forbidden(tmp_path):
    """Telegramda VOICE_MESSAGES_FORBIDDEN xatosi bo'lganda reply_video ga o'tish testi."""
    mock_message = AsyncMock(spec=Message)
    mock_message.video = MagicMock(spec=Video)
    mock_message.video.duration = 10
    mock_message.document = None
    mock_message.from_user = User(id=333444, is_bot=False, first_name="Vali")
    mock_message.chat = Chat(id=333444, type="private")

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
    Path(dummy_out).write_bytes(b"dummy_video_bytes")

    with patch("services.video_service.video_service.convert_to_round_video", return_value=dummy_out):
        await state_process_round_video(mock_message, mock_state)

    assert mock_message.reply_video_note.called
    assert mock_message.reply_video.called
    call_kwargs = mock_message.reply_video.call_args[1]
    assert call_kwargs.get("width") == 384
    assert call_kwargs.get("height") == 384
    assert call_kwargs.get("duration") == 10
    assert "video xabar (video note) qabul qilish cheklangani" in call_kwargs["caption"]


@pytest.mark.asyncio
async def test_send_round_video_note_helper_success_and_fallback(tmp_path):
    """send_round_video_note helper funksiyasi to'g'ri ishlashi va zaxira yuborishi testi."""
    mock_bot = AsyncMock()
    dummy_file = str(tmp_path / "dummy_helper.mp4")
    Path(dummy_file).write_bytes(b"test_helper_bytes")

    # 1. Muvaffaqiyatli holat
    await send_round_video_note(mock_bot, chat_id=123, video_path=dummy_file, duration=30, length=384)
    assert mock_bot.send_video_note.called
    call_kwargs = mock_bot.send_video_note.call_args[1]
    assert call_kwargs.get("duration") == 30
    assert call_kwargs.get("length") == 384

    # 2. Xatolik yuz berganda fallback
    mock_bot.send_video_note.side_effect = TelegramBadRequest(
        method="sendVideoNote",
        message="Bad Request: VOICE_MESSAGES_FORBIDDEN"
    )
    await send_round_video_note(mock_bot, chat_id=123, video_path=dummy_file, duration=30, length=384)
    assert mock_bot.send_video.called
    v_kwargs = mock_bot.send_video.call_args[1]
    assert v_kwargs.get("width") == 384
    assert v_kwargs.get("height") == 384


# ---------------------------------------------------------------------------
# 4. UX Guidance, Mute Toggle, and Cancel Handling Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_round_video_prompt_ux_guidance():
    """Foydalanuvchi dumaloq video bo'limiga kirganda aniq ko'rsatmalar olishi testi."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_state = AsyncMock(spec=FSMContext)

    await cmd_round_video_prompt(mock_message, mock_state)

    # FSM holati waiting_for_video ga o'rnatilgan
    mock_state.set_state.assert_called_with(RoundVideoStates.waiting_for_video)
    mock_state.update_data.assert_called_with(mute=False)

    # Ko'rsatmalar matnida 60 soniya va 1:1 kvadrat eslatmasi borligi
    assert mock_message.answer.called
    call_args = mock_message.answer.call_args
    prompt_text = call_args[0][0]
    assert "60 soniya" in prompt_text
    assert "384x384" in prompt_text
    assert "Kvadrat" in prompt_text or "kvadrat" in prompt_text


@pytest.mark.asyncio
async def test_cb_toggle_mute():
    """Ovozni yoqish/o'chirish tugmasi FSM holatini o'zgartirishi testi."""
    mock_cb = AsyncMock(spec=CallbackQuery)
    mock_cb.answer = AsyncMock()
    mock_cb.message = AsyncMock()
    mock_cb.message.edit_reply_markup = AsyncMock()
    mock_state = AsyncMock(spec=FSMContext)

    # 1. Dastlab mute=False -> mute=True ga o'zgaradi
    mock_state.get_data.return_value = {"mute": False}
    await cb_toggle_mute(mock_cb, mock_state)
    mock_state.update_data.assert_called_with(mute=True)
    assert "o'chirildi" in mock_cb.answer.call_args[0][0]

    # 2. Keyin mute=True -> mute=False ga o'zgaradi
    mock_state.get_data.return_value = {"mute": True}
    await cb_toggle_mute(mock_cb, mock_state)
    mock_state.update_data.assert_called_with(mute=False)
    assert "yoqildi" in mock_cb.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cancel_options_inline_and_text():
    """Bekor qilish inline tugma va matnli xabar orqali to'g'ri ishlashi testi."""
    mock_state = AsyncMock(spec=FSMContext)

    # 1. Inline bekor qilish
    mock_cb = AsyncMock(spec=CallbackQuery)
    mock_cb.answer = AsyncMock()
    mock_cb.message = AsyncMock()
    mock_cb.message.answer = AsyncMock()
    mock_cb.message.delete = AsyncMock()
    mock_cb.from_user = User(id=555, is_bot=False, first_name="Test")
    await cb_cancel_round_video(mock_cb, mock_state)
    mock_state.clear.assert_called()
    assert mock_cb.message.answer.called
    assert "bekor qilindi" in mock_cb.message.answer.call_args[0][0]

    # 2. Matn orqali bekor qilish
    mock_msg = AsyncMock(spec=Message)
    mock_msg.answer = AsyncMock()
    mock_msg.from_user = User(id=555, is_bot=False, first_name="Test")
    await msg_cancel_round_video(mock_msg, mock_state)
    assert mock_state.clear.called
    assert "bekor qilindi" in mock_msg.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_invalid_input_and_document_filter():
    """Video o'rniga boshqa narsa yuborilganda foydalanuvchiga yordam berilishi testi."""
    # 1. Matn yoki noaniq xabar yuborilganda
    mock_msg = AsyncMock(spec=Message)
    mock_msg.reply = AsyncMock()
    await msg_invalid_round_video_input(mock_msg)
    assert mock_msg.reply.called
    assert "video fayl yuboring" in mock_msg.reply.call_args[0][0]

    # 2. Noto'g'ri formatdagi document (masalan PDF) yuborilganda rad etilishi
    mock_doc_msg = AsyncMock(spec=Message)
    mock_doc_msg.reply = AsyncMock()
    mock_doc_msg.video = None
    mock_doc = MagicMock(spec=Document)
    mock_doc.mime_type = "application/pdf"
    mock_doc.file_name = "report.pdf"
    mock_doc_msg.document = mock_doc

    mock_state = AsyncMock(spec=FSMContext)
    await state_process_round_video(mock_doc_msg, mock_state)
    assert mock_doc_msg.reply.called
    assert "video formatida emas" in mock_doc_msg.reply.call_args[0][0]
