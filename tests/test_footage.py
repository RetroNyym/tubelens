"""footage.py birim testleri (ag gerektirmez)."""

import pytest

from tubelens import footage


def test_ai_image_size_by_aspect():
    assert footage._ai_image_size("9:16") == (768, 1344)
    assert footage._ai_image_size("16:9") == (1344, 768)
    assert footage._ai_image_size("1:1") == (1024, 1024)


def test_pick_file_prefers_matching_aspect():
    files = [
        {"link": "landscape.mp4", "width": 1920, "height": 1080},
        {"link": "portrait.mp4", "width": 1080, "height": 1920},
    ]
    assert footage._pick_file(files, "9:16") == "portrait.mp4"
    assert footage._pick_file(files, "16:9") == "landscape.mp4"


def test_pick_file_falls_back_to_any():
    files = [{"link": "x.mp4", "width": 0, "height": 0}]
    assert footage._pick_file(files, "9:16") == "x.mp4"
    assert footage._pick_file([], "9:16") is None


def test_pick_pixabay_file_aspect_filter():
    videos = {
        "large": {"url": "p.mp4", "width": 1080, "height": 1920},
        "medium": {"url": "l.mp4", "width": 1920, "height": 1080},
    }
    url, _, _ = footage._pick_pixabay_file(videos, "9:16")
    assert url == "p.mp4"
    url, _, _ = footage._pick_pixabay_file(videos, "16:9")
    assert url == "l.mp4"


def test_from_local_missing_folder():
    with pytest.raises(footage.FootageError):
        footage.from_local(footage.Path("yok-boyle-klasor"), 4)


def test_gather_no_keys_no_ai_fails_cleanly(tmp_path):
    with pytest.raises(footage.FootageError) as exc:
        footage.gather(
            ["kahve"],
            dest_dir=tmp_path,
            count=2,
            allow_ai=False,
        )
    message = str(exc.value)
    assert "Pexels" in message and "Pixabay" in message
