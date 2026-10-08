"""hfspace.py ek fonksiyonlari - available / upload / lipsync / image_to_video (ag yok)."""

from pathlib import Path

import pytest

from tubelens import hfspace


def _clear_probe(monkeypatch):
    monkeypatch.setattr(hfspace, "_probe_cache", {})


def test_available_false_on_style_error(monkeypatch):
    _clear_probe(monkeypatch)

    def boom(space):
        raise hfspace.HfSpaceError("asili")

    monkeypatch.setattr(hfspace, "_style", boom)
    assert hfspace.available("ornek/space") is False
    assert hfspace.available("ornek/space") is False  # cache'lenir


def test_available_never_raises(monkeypatch):
    _clear_probe(monkeypatch)
    monkeypatch.setattr(hfspace, "_style", lambda space: 1 / 0)
    assert hfspace.available("x/y") is False


def test_available_true_and_cached(monkeypatch):
    _clear_probe(monkeypatch)
    calls = []

    def style(space):
        calls.append(space)
        return "5", "https://ornek.hf.space"

    monkeypatch.setattr(hfspace, "_style", style)
    assert hfspace.available("a/b", token="hf_x") is True
    assert hfspace.available("a/b") is True
    assert calls == ["a/b"]


def test_upload_missing_file_raises_before_network(tmp_path):
    with pytest.raises(hfspace.HfSpaceError):
        hfspace.upload(hfspace.LTX_SPACE, tmp_path / "yok.png")


def test_filedata_shape():
    assert hfspace._filedata("x/y.png") == {
        "path": "x/y.png",
        "meta": {"_type": "gradio.FileData"},
    }


def test_lipsync_endpoint_and_data(monkeypatch, tmp_path):
    uploads = []

    def fake_upload(space, path, token=None):
        uploads.append((space, str(path), token))
        return "up-" + Path(path).name

    captured = {}

    def fake_call(space, endpoint, inputs, token=None, timeout=600):
        captured.update(space=space, endpoint=endpoint, inputs=inputs, token=token)
        return {"video": {"url": "/file/x.mp4"}}

    monkeypatch.setattr(hfspace, "upload", fake_upload)
    monkeypatch.setattr(hfspace, "call", fake_call)
    monkeypatch.setattr(
        hfspace, "_download_result",
        lambda space, payload, dest, token=None: Path(dest),
    )
    dest = tmp_path / "out.mp4"
    out = hfspace.lipsync(
        tmp_path / "yuz.png", tmp_path / "ses.mp3", dest, token="hf_x"
    )
    assert out == dest
    assert captured["space"] == hfspace.LATENTSYNC_SPACE
    assert captured["endpoint"] == "/generate_lip_sync_video"
    assert captured["token"] == "hf_x"
    assert captured["inputs"] == [
        {"path": "up-yuz.png", "meta": {"_type": "gradio.FileData"}},
        {"path": "up-ses.mp3", "meta": {"_type": "gradio.FileData"}},
    ]
    assert [u[0] for u in uploads] == [
        hfspace.LATENTSYNC_SPACE,
        hfspace.LATENTSYNC_SPACE,
    ]


def test_image_to_video_builds_ltx_inputs(monkeypatch, tmp_path):
    monkeypatch.setattr(hfspace, "upload", lambda space, path, token=None: "up-img")
    captured = {}

    def fake_call(space, endpoint, inputs, token=None, timeout=600):
        captured.update(space=space, endpoint=endpoint, inputs=inputs, token=token)
        return {"video": {"url": "/file/x.mp4"}}

    monkeypatch.setattr(hfspace, "call", fake_call)
    monkeypatch.setattr(
        hfspace, "_download_result",
        lambda space, payload, dest, token=None: Path(dest),
    )
    dest = tmp_path / "o.mp4"
    out = hfspace.image_to_video(
        "img.png", dest, duration=12.0, aspect="9:16", token="hf_t", prompt="kahve"
    )
    assert out == dest
    assert captured["space"] == hfspace.LTX_SPACE
    assert captured["endpoint"] == "/image_to_video"
    assert captured["token"] == "hf_t"
    data = captured["inputs"]
    assert data[0] == "kahve"
    assert data[1] == hfspace.NEGATIVE
    assert data[2] == hfspace._filedata("up-img")
    assert data[4:6] == [1024, 576]  # h, w (9:16)
    assert data[6] == "image-to-video"
    assert data[7] == 8.5  # sure 8.5'ye kisaltildi


def test_text_to_video_still_uses_text_endpoint(monkeypatch, tmp_path):
    captured = {}

    def fake_call(space, endpoint, inputs, token=None, timeout=600):
        captured.update(space=space, endpoint=endpoint, inputs=inputs)
        return {"video": {"url": "/file/x.mp4"}}

    monkeypatch.setattr(hfspace, "call", fake_call)
    monkeypatch.setattr(
        hfspace, "_download_result",
        lambda space, payload, dest, token=None: Path(dest),
    )
    dest = tmp_path / "o.mp4"
    hfspace.text_to_video("deneme", dest, duration=4.0, aspect="16:9")
    assert captured["endpoint"] == "/text_to_video"
    assert captured["inputs"][6] == "text-to-video"
    assert captured["inputs"][4:6] == [576, 1024]  # h, w (16:9)


def test_resolve_token_prefers_explicit_then_env(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    assert hfspace._resolve_token(None) is None
    monkeypatch.setenv("HF_TOKEN", "hf_env")
    assert hfspace._resolve_token(None) == "hf_env"
    assert hfspace._resolve_token("") == "hf_env"
    assert hfspace._resolve_token("hf_explicit") == "hf_explicit"


def test_text_to_video_falls_back_to_env_token(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_TOKEN", "hf_env")
    captured = {}

    def fake_call(space, endpoint, inputs, token=None, timeout=600):
        captured.update(token=token)
        return {"video": {"url": "/file/x.mp4"}}

    monkeypatch.setattr(hfspace, "call", fake_call)
    monkeypatch.setattr(
        hfspace, "_download_result",
        lambda space, payload, dest, token=None: Path(dest),
    )
    hfspace.text_to_video("deneme", tmp_path / "o.mp4")
    assert captured["token"] == "hf_env"


def test_call_extracts_error_detail_from_json_sse(monkeypatch):
    monkeypatch.setattr(
        hfspace, "_style", lambda space: ("5", "https://x.hf.space")
    )

    class _Resp:
        status_code = 200

        def json(self):
            return {"event_id": "e1"}

        text = ""

    monkeypatch.setattr(hfspace.requests, "post", lambda *a, **k: _Resp())

    class _Sse:
        text = (
            "event: error\n"
            'data: {"error": "You have exhausted your maximum quota"}\n'
        )

    monkeypatch.setattr(hfspace.requests, "get", lambda *a, **k: _Sse())
    with pytest.raises(hfspace.HfSpaceError) as exc:
        hfspace.call("a/b", "/text_to_video", [], token=None, timeout=5)
    message = str(exc.value)
    assert "exhausted your maximum quota" in message


def test_call_null_error_detail_gives_quota_hint(monkeypatch):
    monkeypatch.setattr(
        hfspace, "_style", lambda space: ("5", "https://x.hf.space")
    )

    class _Resp:
        status_code = 200

        def json(self):
            return {"event_id": "e1"}

        text = ""

    monkeypatch.setattr(hfspace.requests, "post", lambda *a, **k: _Resp())

    class _Sse:
        text = "event: error\ndata: null\n"

    monkeypatch.setattr(hfspace.requests, "get", lambda *a, **k: _Sse())
    with pytest.raises(hfspace.HfSpaceError) as exc:
        hfspace.call("a/b", "/text_to_video", [], token=None, timeout=5)
    message = str(exc.value)
    assert "HF token" in message
