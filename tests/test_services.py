"""
Services testi (Story username tozalash, downloader ob'ektlari)
"""
from services.story_service import story_service
from services.downloader import DownloadResult


def test_story_username_cleaning():
    cases = [
        ("cristiano", "cristiano"),
        ("@cristiano", "cristiano"),
        ("https://www.instagram.com/cristiano/", "cristiano"),
        ("https://instagram.com/stories/cristiano/", "cristiano"),
        ("https://www.instagram.com/stories/shaxzoda_muxammedova/12345678/", "shaxzoda_muxammedova"),
        ("@leomessi", "leomessi"),
    ]
    for raw, expected in cases:
        assert story_service.clean_username(raw) == expected


def test_download_result_dataclass():
    res = DownloadResult(
        success=True,
        file_path="/tmp/video.mp4",
        title="Test Video",
        duration=60,
        file_size=1024 * 1024 * 10
    )
    assert res.success is True
    assert res.duration == 60
    assert res.file_size == 10485760
