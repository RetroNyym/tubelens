"""viggle.py istemci testleri (ag gerektirmez, HTTP sahtelenir)."""

from pathlib import Path

import pytest

from tubelens import viggle

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"v" * 4096


class _Resp:
    def __init__(self, status_code=200, data=None, content=b"", text=""):
        self.status_code = status_code
        self._data = data
        self.content = content
        self.text = text or ("" if data is None else str(data))

    def json(self):
        if self._data is None:
            raise ValueError("JSON degil")
        return self._data

    def iter_content(self, chunk_size=1024):
        if self.content:
            yield self.content


def _no_key(monkeypatch):
    monkeypatch.delenv("VIGGLE_API_KEY", raising=False)


def test_text_to_video_requires_key(monkeypatch, tmp_path):
    _no_key(monkeypatch)
    with pytest.raises(viggle.ViggleError) as exc:
        viggle.text_to_video("deneme", tmp_path / "v.mp4")
    assert "anahtar" in str(exc.value)


def test_animate_requires_key(monkeypatch, tmp_path):
    _no_key(monkeypatch)
    with pytest.raises(viggle.ViggleError) as exc:
        viggle.animate(tmp_path / "yok.png", tmp_path / "v.mp4")
    assert "anahtar" in str(exc.value)


def test_resolve_key_from_env(monkeypatch):
    _no_key(monkeypatch)
    assert viggle.resolve_key("") == ""
    monkeypatch.setenv("VIGGLE_API_KEY", "  gizli-anahtar  ")
    assert viggle.resolve_key("") == "gizli-anahtar"
    assert viggle.resolve_key("parametre") == "parametre"


def test_env_key_reaches_request(monkeypatch, tmp_path):
    monkeypatch.setenv("VIGGLE_API_KEY", "env-key")
    with pytest.raises(viggle.ViggleError) as exc:
        viggle.animate(tmp_path / "yok.png", tmp_path / "v.mp4")
    assert "Gorsel okunamadi" in str(exc.value)


def test_text_to_video_happy_path(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, **kw):
        calls.append(("post", url, kw))
        return _Resp(data={"id": "vid-1"})

    def fake_get(url, **kw):
        calls.append(("get", url, kw))
        if url.endswith("/videos/vid-1"):
            return _Resp(data={"status": "ready", "video_url": "https://cdn/x.mp4"})
        return _Resp(content=VIDEO_BYTES)

    monkeypatch.setattr(viggle.requests, "post", fake_post)
    monkeypatch.setattr(viggle.requests, "get", fake_get)
    dest = tmp_path / "v.mp4"
    out = viggle.text_to_video(
        "selam dunya", dest, duration=4, aspect="9:16", api_key="k1"
    )
    assert out == dest
    assert dest.read_bytes() == VIDEO_BYTES
    assert calls[0][0] == "post"
    assert calls[0][1] == viggle.BASE + "/videos"
    assert calls[0][2]["data"]["prompt"] == "selam dunya"
    assert calls[0][2]["data"]["aspect_ratio"] == "9:16"
    assert calls[0][2]["headers"]["Authorization"] == "Bearer k1"
    assert any(c[1].endswith("/videos/vid-1") for c in calls)


def test_poll_failed_status_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        viggle.requests, "post", lambda url, **kw: _Resp(data={"id": "vid-2"})
    )
    monkeypatch.setattr(
        viggle.requests,
        "get",
        lambda url, **kw: _Resp(data={"status": "failed", "error": "kota doldu"}),
    )
    with pytest.raises(viggle.ViggleError) as exc:
        viggle.text_to_video("deneme", tmp_path / "v.mp4", api_key="k1")
    assert "kota doldu" in str(exc.value)


def test_ready_without_url_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        viggle.requests, "post", lambda url, **kw: _Resp(data={"id": "vid-3"})
    )
    monkeypatch.setattr(
        viggle.requests, "get", lambda url, **kw: _Resp(data={"status": "ready"})
    )
    with pytest.raises(viggle.ViggleError) as exc:
        viggle.text_to_video("deneme", tmp_path / "v.mp4", api_key="k1")
    assert "video_url" in str(exc.value)


def test_animate_happy_path(monkeypatch, tmp_path):
    img = tmp_path / "karakter.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 200)
    captured = {}

    def fake_post(url, **kw):
        captured.update(url=url, kw=kw)
        return _Resp(data={"id": "anim-1"})

    def fake_get(url, **kw):
        if url.endswith("/videos/anim-1"):
            return _Resp(data={"status": "ready", "url": "https://cdn/a.mp4"})
        return _Resp(content=VIDEO_BYTES)

    monkeypatch.setattr(viggle.requests, "post", fake_post)
    monkeypatch.setattr(viggle.requests, "get", fake_get)
    dest = tmp_path / "out" / "v.mp4"
    out = viggle.animate(img, dest, prompt="natural idle motion", api_key="k1")
    assert out == dest
    assert dest.stat().st_size == len(VIDEO_BYTES)
    assert captured["url"] == viggle.BASE + "/videos"
    files = captured["kw"]["files"]
    assert "character_image" in files
    assert files["character_image"][2] == "image/png"
    assert captured["kw"]["data"]["prompt"] == "natural idle motion"


def test_download_too_small_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        viggle.requests, "post", lambda url, **kw: _Resp(data={"id": "vid-4"})
    )
    monkeypatch.setattr(
        viggle.requests,
        "get",
        lambda url, **kw: (
            _Resp(data={"status": "ready", "video_url": "https://cdn/x.mp4"})
            if url.endswith("/videos/vid-4")
            else _Resp(content=b"html")
        ),
    )
    with pytest.raises(viggle.ViggleError) as exc:
        viggle.text_to_video("deneme", tmp_path / "v.mp4", api_key="k1")
    assert "bos" in str(exc.value)


def test_post_http_error_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        viggle.requests, "post", lambda url, **kw: _Resp(status_code=401)
    )
    with pytest.raises(viggle.ViggleError) as exc:
        viggle.text_to_video("deneme", tmp_path / "v.mp4", api_key="k1")
    assert "gecersiz" in str(exc.value)
