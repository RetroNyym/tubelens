"""footage.py birim testleri (ag gerektirmez)."""

from pathlib import Path

import pytest

from tubelens import footage
from tubelens import hf as hf_mod


def _noise_jpeg() -> bytes:
    import os

    return b"\xff\xd8\xff\xe0" + os.urandom(40_000)


def _fake_clip(img, dest, size, dur=3.4):
    path = Path(dest)
    path.write_bytes(b"x" * 20_000)
    return path


def test_ai_image_size_by_aspect():
    assert footage._ai_image_size("9:16") == (768, 1344)
    assert footage._ai_image_size("16:9") == (1344, 768)
    assert footage._ai_image_size("1:1") == (1024, 1024)
    assert footage._ai_image_size("4:3") == (1344, 1008)
    assert footage._ai_image_size("3:4") == (1008, 1344)


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


def test_pick_file_4_3_landscape_3_4_portrait():
    files = [
        {"link": "landscape.mp4", "width": 1920, "height": 1080},
        {"link": "portrait.mp4", "width": 1080, "height": 1920},
    ]
    assert footage._pick_file(files, "4:3") == "landscape.mp4"
    assert footage._pick_file(files, "3:4") == "portrait.mp4"


def test_pick_file_4_3_mismatch_is_soft_preference():
    files = [{"link": "portrait.mp4", "width": 1080, "height": 1920}]
    assert footage._pick_file(files, "4:3") == "portrait.mp4"
    files = [{"link": "landscape.mp4", "width": 1920, "height": 1080}]
    assert footage._pick_file(files, "3:4") == "landscape.mp4"


def test_pick_pixabay_file_4_3_orientation():
    videos = {
        "large": {"url": "p.mp4", "width": 1080, "height": 1920},
        "medium": {"url": "l.mp4", "width": 1920, "height": 1080},
    }
    assert footage._pick_pixabay_file(videos, "4:3")[0] == "l.mp4"
    assert footage._pick_pixabay_file(videos, "3:4")[0] == "p.mp4"
    url, _, _ = footage._pick_pixabay_file({"only": {"url": "q.mp4", "width": 500, "height": 900}}, "4:3")
    assert url == "q.mp4"


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
            allow_web=False,
        )
    message = str(exc.value)
    assert "Pexels" in message and "Pixabay" in message


def test_gather_chain_order_web_before_ltx(tmp_path, monkeypatch):
    """Kaynak zinciri: web gorsel aramasi LTX'ten ONCE denenir (dokumanla ayni)."""
    order: list[str] = []

    def fake_web(queries, dest_dir, count, aspect="9:16"):
        order.append("web")
        raise footage.FootageError("web bos")

    def fake_ltx(queries, dest_dir, count, aspect="9:16", token=""):
        order.append("ltx")
        raise footage.FootageError("ltx bos")

    def fake_ai(queries, dest_dir, count, aspect="9:16", hf_token=""):
        order.append("ai")
        return [tmp_path / "aivis_00.mp4"]

    monkeypatch.setattr(footage, "from_web_images", fake_web)
    monkeypatch.setattr(footage, "from_ltx_video", fake_ltx)
    monkeypatch.setattr(footage, "from_ai_images", fake_ai)
    clips = footage.gather(
        ["kahve"],
        dest_dir=tmp_path,
        count=2,
        allow_web=True,
        allow_ltx=True,
        allow_ai=True,
    )
    assert order == ["web", "ltx", "ai"]
    assert clips == [tmp_path / "aivis_00.mp4"]


def test_from_local_photos_become_clips(tmp_path):
    """Fotograflar kabul edilir; Ken Burns ile klip'e cevrilir (anahtarsiz)."""
    import os

    from PIL import Image

    img = tmp_path / "urun.jpg"
    # gurultulu goruntu: x264 kucultemez, klip >10KB olur
    Image.frombytes("RGB", (300, 400), os.urandom(300 * 400 * 3)).save(img, "JPEG")
    clips = footage.from_local(tmp_path, 1, dest_dir=tmp_path / "cl", aspect="9:16")
    assert len(clips) == 1
    assert clips[0].suffix == ".mp4"
    assert clips[0].stat().st_size > 10_000


def test_from_local_rejects_empty_folder(tmp_path):
    with pytest.raises(footage.FootageError) as exc:
        footage.from_local(tmp_path, 2)
    assert "video/fotograf" in str(exc.value)


def test_gather_passes_hf_token_to_from_ai_images(tmp_path, monkeypatch):
    captured: dict = {}

    def fake_from_ai(queries, dest_dir, count, aspect="9:16", hf_token=""):
        captured.update(
            queries=queries,
            dest_dir=dest_dir,
            count=count,
            aspect=aspect,
            hf_token=hf_token,
        )
        return [tmp_path / "aivis_00.mp4"]

    monkeypatch.setattr(footage, "from_ai_images", fake_from_ai)
    clips = footage.gather(
        ["kahve"],
        dest_dir=tmp_path,
        count=2,
        aspect="4:3",
        allow_web=False,
        allow_ltx=False,
        hf_token="hf_token_burada",
    )
    assert clips == [tmp_path / "aivis_00.mp4"]
    assert captured["hf_token"] == "hf_token_burada"
    assert captured["aspect"] == "4:3"
    assert captured["count"] == 2


def test_from_ai_images_prefers_hf_with_token(tmp_path, monkeypatch):
    hf_calls: list[dict] = []
    polite: list[int] = []

    def fake_generate(prompt, dest, *, aspect="9:16", token="", timeout=90):
        hf_calls.append({"prompt": prompt, "aspect": aspect, "token": token})
        path = Path(dest)
        path.write_bytes(_noise_jpeg())
        return path

    def fail_download(url, dest):
        raise AssertionError("Pollinations yolu kullanilmamali: " + str(url))

    monkeypatch.setattr(footage, "_polite", lambda: polite.append(1))
    monkeypatch.setattr(hf_mod, "generate_image", fake_generate)
    monkeypatch.setattr(footage, "_download", fail_download)
    monkeypatch.setattr(footage, "_still_to_clip", _fake_clip)

    clips = footage.from_ai_images(["kahve", "ofis"], tmp_path, 2, "4:3", hf_token="hf_tok")
    assert len(clips) == 2
    assert len(hf_calls) == 2
    assert all(call["token"] == "hf_tok" for call in hf_calls)
    assert all(call["aspect"] == "4:3" for call in hf_calls)
    assert polite, "HF isteklerinden once _polite() uygulanmali"


def test_from_ai_images_without_token_skips_hf(tmp_path, monkeypatch):
    downloads: list[str] = []

    def fail_generate(*a, **kw):
        raise AssertionError("token yokken HF cagirilmamali")

    def fake_download(url, dest):
        downloads.append(str(url))
        path = Path(dest)
        path.write_bytes(_noise_jpeg())
        return path

    monkeypatch.setattr(footage, "_polite", lambda: None)
    monkeypatch.setattr(hf_mod, "generate_image", fail_generate)
    monkeypatch.setattr(footage, "_download", fake_download)
    monkeypatch.setattr(footage, "_still_to_clip", _fake_clip)

    clips = footage.from_ai_images(["kahve"], tmp_path, 1, "9:16")
    assert len(clips) == 1
    assert len(downloads) == 1


def test_from_ai_images_hf_error_falls_back_to_pollinations(tmp_path, monkeypatch):
    hf_calls: list[str] = []
    downloads: list[str] = []

    def boom(prompt, dest, **kw):
        hf_calls.append(str(kw.get("token")))
        raise hf_mod.HfImageError("token gecersiz")

    def fake_download(url, dest):
        downloads.append(str(url))
        path = Path(dest)
        path.write_bytes(_noise_jpeg())
        return path

    monkeypatch.setattr(footage, "_polite", lambda: None)
    monkeypatch.setattr(hf_mod, "generate_image", boom)
    monkeypatch.setattr(footage, "_download", fake_download)
    monkeypatch.setattr(footage, "_still_to_clip", _fake_clip)

    clips = footage.from_ai_images(
        ["kahve", "ofis"], tmp_path, 2, "9:16", hf_token="bozuk_token"
    )
    assert len(clips) == 2
    assert len(downloads) == 2
    assert len(hf_calls) == 1, "ilk HF hatasindan sonra yadege dusulur"
    assert all(path.name.startswith("aivis_") for path in clips)
