"""avatar.py - Konusma-Avatar modu testleri (ag gerektirmez, HTTP sahtelenir)."""

import argparse
import json
from pathlib import Path

import pytest

from tubelens import avatar

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"x" * 4096


def _image(tmp_path: Path) -> Path:
    img = tmp_path / "karakter.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 200)
    return img


def _audio(tmp_path: Path) -> Path:
    audio = tmp_path / "ses.mp3"
    audio.write_bytes(b"ID3" + b"\x00" * 2000)
    return audio


def _write(dest):
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(VIDEO_BYTES)
    return path


def _record(monkeypatch, calls, ok_on=None):
    """Uc saglayiciyi da kaydeden sahte kurulum; ok_on adi basarili olur."""

    def make(name):
        def run(image, audio, dest, *a, **kw):
            calls.append(name)
            if ok_on == name:
                return _write(dest)
            raise avatar.AvatarError(name + " kapali")

        return run

    monkeypatch.setattr(avatar, "_latentsync_avatar", make("latentsync"))
    monkeypatch.setattr(avatar, "_hedra_avatar", make("hedra"))
    monkeypatch.setattr(avatar, "_viggle_avatar", make("viggle"))


def _no_keys(monkeypatch):
    monkeypatch.delenv("HEDRA_API_KEY", raising=False)
    monkeypatch.delenv("VIGGLE_API_KEY", raising=False)


def test_text_triggers_synthesis(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    img = _image(tmp_path)
    seen = {}

    def fake_synth(text, out_path, voice=None, **kw):
        seen.update(text=text, voice=voice, out=Path(out_path), kw=kw)
        Path(out_path).write_bytes(b"ID3" + b"\x00" * 2000)
        return []

    monkeypatch.setattr(avatar, "synthesize", fake_synth)
    calls = []
    _record(monkeypatch, calls, ok_on="latentsync")
    out = avatar.make_avatar(
        img, tmp_path / "out",
        text="Merhaba dunya", voice="tr-TR-EmelNeural", lang="tr",
        tts_engine="edge",
    )
    assert seen["text"] == "Merhaba dunya"
    assert seen["voice"] == "tr-TR-EmelNeural"
    assert seen["kw"]["engine"] == "edge"
    assert seen["out"] == tmp_path / "out" / "audio.mp3"
    assert seen["out"].exists()
    assert out == tmp_path / "out" / "video.mp4"
    assert calls == ["latentsync"]


def test_fallback_order(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    monkeypatch.setenv("HEDRA_API_KEY", "hk")
    img = _image(tmp_path)
    audio = _audio(tmp_path)
    calls = []
    _record(monkeypatch, calls, ok_on="viggle")
    out = avatar.make_avatar(
        img, tmp_path / "out", audio_path=audio, viggle_key="vk"
    )
    assert calls == ["latentsync", "hedra", "viggle"]
    assert out.exists()
    meta = json.loads((tmp_path / "out" / "meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "viggle"
    assert meta["mode"] == "avatar"


def test_auto_skips_providers_without_keys(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    img = _image(tmp_path)
    audio = _audio(tmp_path)
    calls = []
    _record(monkeypatch, calls)
    with pytest.raises(avatar.AvatarError) as exc:
        avatar.make_avatar(img, tmp_path / "out", audio_path=audio)
    assert calls == ["latentsync"]
    assert "latentsync:" in str(exc.value)


def test_avatar_error_lists_providers(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    monkeypatch.setenv("HEDRA_API_KEY", "hk")
    img = _image(tmp_path)
    audio = _audio(tmp_path)
    calls = []
    _record(monkeypatch, calls)
    with pytest.raises(avatar.AvatarError) as exc:
        avatar.make_avatar(
            img, tmp_path / "out", audio_path=audio, viggle_key="vk"
        )
    message = str(exc.value)
    assert calls == ["latentsync", "hedra", "viggle"]
    for name in ("latentsync", "hedra", "viggle"):
        assert name + ":" in message
    assert "Cozumler" in message


def test_explicit_provider_forces_one(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    monkeypatch.setenv("HEDRA_API_KEY", "hk")
    img = _image(tmp_path)
    audio = _audio(tmp_path)
    calls = []
    _record(monkeypatch, calls, ok_on="hedra")
    out = avatar.make_avatar(
        img, tmp_path / "out", audio_path=audio, provider="hedra"
    )
    assert calls == ["hedra"]
    meta = json.loads((tmp_path / "out" / "meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "hedra"


def test_unknown_provider_raises(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    img = _image(tmp_path)
    audio = _audio(tmp_path)
    with pytest.raises(avatar.AvatarError) as exc:
        avatar.make_avatar(
            img, tmp_path / "out", audio_path=audio, provider="yok-boyle"
        )
    assert "Bilinmeyen saglayici" in str(exc.value)


def test_missing_audio_and_text_raises(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    img = _image(tmp_path)
    with pytest.raises(avatar.AvatarError) as exc:
        avatar.make_avatar(img, tmp_path / "out")
    assert "Ses gerekli" in str(exc.value)


def test_missing_image_raises(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    with pytest.raises(avatar.AvatarError) as exc:
        avatar.make_avatar(tmp_path / "yok.png", tmp_path / "out")
    assert "Gorsel bulunamadi" in str(exc.value)


def test_missing_audio_file_raises(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    img = _image(tmp_path)
    with pytest.raises(avatar.AvatarError) as exc:
        avatar.make_avatar(img, tmp_path / "out", audio_path=tmp_path / "yok.mp3")
    assert "Ses dosyasi bulunamadi" in str(exc.value)


def test_hedra_without_key_raises(monkeypatch, tmp_path):
    _no_keys(monkeypatch)
    with pytest.raises(avatar.AvatarError) as exc:
        avatar._hedra_avatar("img.png", "a.mp3", tmp_path / "v.mp4")
    assert "HEDRA_API_KEY" in str(exc.value)


def test_viggle_animation_requires_key(monkeypatch, tmp_path):
    _no_keys(monkeypatch)
    img = _image(tmp_path)
    audio = _audio(tmp_path)
    with pytest.raises(Exception) as exc:
        avatar._viggle_avatar(img, audio, tmp_path / "out" / "video.mp4")
    assert "anahtar" in str(exc.value)


def test_default_out_under_video_dir(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    monkeypatch.setattr(avatar, "VIDEO_DIR", tmp_path)
    img = _image(tmp_path)
    audio = _audio(tmp_path)
    calls = []
    _record(monkeypatch, calls, ok_on="latentsync")
    out = avatar.make_avatar(img, None, audio_path=audio)
    assert out.parent.parent == tmp_path
    assert out.name == "video.mp4"
    assert out.parent.name.endswith("-karakter")
    meta = json.loads((out.parent / "meta.json").read_text(encoding="utf-8"))
    assert meta["mode"] == "avatar"
    assert meta["title"] == "karakter"


def test_out_path_accepts_file(tmp_path, monkeypatch):
    _no_keys(monkeypatch)
    img = _image(tmp_path)
    audio = _audio(tmp_path)
    calls = []
    _record(monkeypatch, calls, ok_on="latentsync")
    dest = tmp_path / "o" / "avatar.mp4"
    out = avatar.make_avatar(img, dest, audio_path=audio)
    assert out == dest
    assert (dest.parent / "meta.json").exists()


def test_register_avatar_subparser():
    parser = argparse.ArgumentParser(prog="tubelens")
    sub = parser.add_subparsers(dest="cmd", required=True)
    avatar.register(sub)
    args = parser.parse_args(
        [
            "avatar",
            "--image", "yuz.png",
            "--audio", "ses.mp3",
            "--text", "merhaba",
            "--voice", "tr-TR-EmelNeural",
            "--lang", "tr",
            "--tts-engine", "edge",
            "--provider", "latentsync",
            "--hf-token", "tok",
            "--viggle-key", "vk",
            "--openai-key", "ok",
            "--elevenlabs-key", "ek",
            "--out", "cikti",
        ]
    )
    assert args.func is avatar.cmd_avatar
    assert args.image == "yuz.png"
    assert args.audio == "ses.mp3"
    assert args.text == "merhaba"
    assert args.voice == "tr-TR-EmelNeural"
    assert args.lang == "tr"
    assert args.tts_engine == "edge"
    assert args.provider == "latentsync"
    assert args.hf_token == "tok"
    assert args.viggle_key == "vk"
    assert args.openai_key == "ok"
    assert args.elevenlabs_key == "ek"
    assert args.out == "cikti"


def test_register_avatar_requires_image():
    parser = argparse.ArgumentParser(prog="tubelens")
    sub = parser.add_subparsers(dest="cmd", required=True)
    avatar.register(sub)
    with pytest.raises(SystemExit):
        parser.parse_args(["avatar"])


def test_cmd_avatar_prints_steps(tmp_path, monkeypatch, capsys):
    def fake(image_path, out_path=None, **kw):
        return _write(Path(out_path) / "video.mp4")

    monkeypatch.setattr(avatar, "make_avatar", fake)
    args = argparse.Namespace(
        image=str(tmp_path / "y.png"), audio=None, text="merhaba",
        voice=None, lang="tr", tts_engine="edge", provider="auto",
        hf_token="", viggle_key="", openai_key="", elevenlabs_key="",
        out=str(tmp_path / "out"),
    )
    assert avatar.cmd_avatar(args) == 0
    out = capsys.readouterr().out
    assert "[1/3]" in out and "[2/3]" in out and "[3/3]" in out
    assert str(tmp_path / "out" / "video.mp4") in out


def test_cmd_avatar_requires_audio_or_text(capsys):
    args = argparse.Namespace(
        image="y.png", audio=None, text=None, voice=None, lang="tr",
        tts_engine="edge", provider="auto", hf_token="", viggle_key="",
        openai_key="", elevenlabs_key="", out=None,
    )
    assert avatar.cmd_avatar(args) == 2
    assert "HATA" in capsys.readouterr().err
