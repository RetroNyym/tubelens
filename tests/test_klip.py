"""klip.py - Metinden Klip modu testleri (ag gerektirmez, HTTP sahtelenir)."""

import argparse
import json
from pathlib import Path

import pytest

from tubelens import higgsfield, klip

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"x" * 4096


def _write(dest):
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(VIDEO_BYTES)
    return path


def _record(monkeypatch, calls, ok_on=None):
    """Dort saglayiciyi da kaydeden sahte kurulum; ok_on adi basarili olur."""

    def make(name):
        def run(prompt, dest, **kw):
            calls.append(name)
            if ok_on == name:
                return _write(dest)
            raise RuntimeError(name + " patladi")

        return run

    monkeypatch.setattr(klip.hfspace, "text_to_video", make("ltx"))
    monkeypatch.setattr(klip, "_pollinations_video", make("pollinations"))
    monkeypatch.setattr(klip, "_pexels_clip", make("pexels"))
    monkeypatch.setattr(klip.viggle, "text_to_video", make("viggle"))
    monkeypatch.setattr(klip.higgsfield, "generate", make("higgsfield"))


def _no_env(monkeypatch):
    for name in ("POLLINATIONS_API_KEY", "VIGGLE_API_KEY", "HIGGSFIELD_API_KEY",
                 "HIGGSFIELD_KEY_ID", "HIGGSFIELD_KEY_SECRET", "PEXELS_API_KEY",
                 "HF_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(klip, "load_video_config", lambda: {})


def test_auto_picks_ltx_first(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    calls = []
    _record(monkeypatch, calls, ok_on="ltx")
    out = klip.make_clip(
        "kahve demleme", tmp_path / "cikti",
        duration=3.0, aspect="9:16",
        viggle_key="vk", higgsfield_key="hk",
    )
    assert calls == ["ltx"]
    assert out == tmp_path / "cikti" / "video.mp4"
    assert out.exists()


def test_auto_skips_key_providers_without_keys(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    calls = []
    _record(monkeypatch, calls)
    with pytest.raises(klip.KlipError) as exc:
        klip.make_clip("deneme", tmp_path / "cikti")
    assert calls == ["ltx", "pollinations"]
    message = str(exc.value)
    assert "ltx:" in message and "pollinations:" in message


def test_auto_includes_keyed_providers(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    calls = []
    _record(monkeypatch, calls, ok_on="higgsfield")
    klip.make_clip(
        "deneme", tmp_path / "cikti",
        viggle_key="vk", higgsfield_key="id:secret",
    )
    assert calls == ["ltx", "pollinations", "viggle", "higgsfield"]


def test_auto_includes_pexels_when_key_saved(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    monkeypatch.setattr(klip, "load_video_config", lambda: {"pexels_api_key": "pk"})
    calls = []
    _record(monkeypatch, calls, ok_on="pexels")
    out = klip.make_clip("deneme", tmp_path / "cikti", duration=3.0)
    assert calls == ["ltx", "pollinations", "pexels"]
    assert out.exists()


def test_auto_pexels_falls_through_when_others_fail(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    monkeypatch.setattr(klip, "load_video_config", lambda: {"pexels_api_key": "pk"})
    calls = []
    _record(monkeypatch, calls)
    with pytest.raises(klip.KlipError) as exc:
        klip.make_clip("deneme", tmp_path / "cikti")
    assert calls == ["ltx", "pollinations", "pexels"]
    message = str(exc.value)
    assert "pexels:" in message
    assert "HF_TOKEN" in message and "PEXELS_API_KEY" in message


def test_explicit_provider_forces_one(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    calls = []
    _record(monkeypatch, calls, ok_on="viggle")
    out = klip.make_clip("deneme", tmp_path / "cikti", provider="viggle")
    assert calls == ["viggle"]
    meta = json.loads((tmp_path / "cikti" / "meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "viggle"


def test_all_providers_fail_raises_kliperror(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    calls = []
    _record(monkeypatch, calls)
    with pytest.raises(klip.KlipError) as exc:
        klip.make_clip(
            "deneme", tmp_path / "cikti",
            viggle_key="vk", higgsfield_key="id:secret",
        )
    message = str(exc.value)
    assert calls == ["ltx", "pollinations", "viggle", "higgsfield"]
    for name in ("ltx", "pollinations", "viggle", "higgsfield"):
        assert name + ":" in message


def test_unknown_provider_raises(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    with pytest.raises(klip.KlipError) as exc:
        klip.make_clip("deneme", tmp_path / "cikti", provider="yok-boyle")
    assert "Bilinmeyen saglayici" in str(exc.value)


def test_empty_prompt_raises(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    with pytest.raises(klip.KlipError):
        klip.make_clip("   ", tmp_path / "cikti")


def test_meta_json_written(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    calls = []
    _record(monkeypatch, calls, ok_on="ltx")
    out = klip.make_clip(
        "Kahve nasil yapilir?", tmp_path / "klip-cikti",
        duration=5.0, aspect="4:3", style="belgesel",
    )
    meta = json.loads((tmp_path / "klip-cikti" / "meta.json").read_text(encoding="utf-8"))
    assert meta == {
        "mode": "klip",
        "title": "Kahve nasil yapilir?",
        "duration_sec": 5.0,
        "aspect": "4:3",
        "provider": "ltx",
    }
    assert out.name == "video.mp4"
    assert out.read_bytes() == VIDEO_BYTES


def test_default_out_dir_under_video_dir(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    monkeypatch.setattr(klip, "VIDEO_DIR", tmp_path)
    calls = []
    _record(monkeypatch, calls, ok_on="ltx")
    out = klip.make_clip("Merhaba Dunya")
    assert out.parent.parent == tmp_path
    assert out.name == "video.mp4"
    assert out.parent.name.endswith("-merhaba-dunya")
    assert (out.parent / "meta.json").exists()


def test_style_appended_to_prompt(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    seen = []

    def fake(prompt, dest, **kw):
        seen.append(prompt)
        return _write(dest)

    monkeypatch.setattr(klip.hfspace, "text_to_video", fake)
    klip.make_clip("kahve", tmp_path / "c", style="sinematik")
    assert seen == ["kahve, sinematik"]


def test_pollinations_video_requires_key(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    with pytest.raises(klip.KlipError) as exc:
        klip._pollinations_video("deneme", tmp_path / "v.mp4")
    assert "POLLINATIONS_API_KEY" in str(exc.value)


def test_pexels_clip_requires_key(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    with pytest.raises(klip.KlipError) as exc:
        klip._pexels_clip("deneme", tmp_path / "v.mp4")
    assert "Pexels" in str(exc.value)
    assert "PEXELS_API_KEY" in str(exc.value)


def test_resolve_pexels_key_order(monkeypatch):
    _no_env(monkeypatch)
    assert klip._resolve_pexels_key("") == ""
    monkeypatch.setenv("PEXELS_API_KEY", "env-key")
    assert klip._resolve_pexels_key("") == "env-key"
    assert klip._resolve_pexels_key("arg-key") == "arg-key"


def test_pexels_clip_trims_and_renames(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    src = tmp_path / "pexels_123.mp4"
    src.write_bytes(VIDEO_BYTES)
    monkeypatch.setattr(klip.footage, "from_pexels", lambda *a, **k: [src])
    seen = {}

    def fake_ffmpeg(args, timeout=1800):
        seen["args"] = args
        seen["timeout"] = timeout
        Path(args[-1]).write_bytes(VIDEO_BYTES)
        return ""

    monkeypatch.setattr(klip.assemble, "run_ffmpeg", fake_ffmpeg)
    dest = tmp_path / "video.mp4"
    out = klip._pexels_clip(
        "drone", dest, duration=4.0, aspect="9:16", api_key="pk"
    )
    assert out == dest
    args = seen["args"]
    assert "-t" in args and "4" in args[args.index("-t") + 1]
    vf = args[args.index("-vf") + 1]
    assert "pad=720:1280" in vf
    assert not src.exists()  # kaynak silinir, sadece kesilmis klip kalir


def test_higgsfield_requires_key(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    with pytest.raises(higgsfield.HiggsfieldError) as exc:
        higgsfield.generate("deneme", tmp_path / "v.mp4")
    assert "anahtar" in str(exc.value)


def test_higgsfield_resolve_key_from_env(monkeypatch):
    _no_env(monkeypatch)
    assert higgsfield.resolve_key("") == ""
    monkeypatch.setenv("HIGGSFIELD_API_KEY", "kid:ksecret")
    assert higgsfield.resolve_key("") == "kid:ksecret"
    monkeypatch.delenv("HIGGSFIELD_API_KEY")
    monkeypatch.setenv("HIGGSFIELD_KEY_ID", "kid2")
    monkeypatch.setenv("HIGGSFIELD_KEY_SECRET", "s2")
    assert higgsfield.resolve_key("") == "kid2:s2"


def test_register_klip_subparser():
    parser = argparse.ArgumentParser(prog="tubelens")
    sub = parser.add_subparsers(dest="cmd", required=True)
    klip.register(sub)
    args = parser.parse_args(
        [
            "klip", "bir klip",
            "--duration", "6",
            "--aspect", "9:16",
            "--provider", "ltx",
            "--style", "belgesel",
            "--hf-token", "tok",
            "--viggle-key", "vk",
            "--higgsfield-key", "hk",
            "--out", "cikti-klasoru",
        ]
    )
    assert args.func is klip.cmd_klip
    assert args.prompt == "bir klip"
    assert args.duration == 6.0
    assert args.aspect == "9:16"
    assert args.provider == "ltx"
    assert args.style == "belgesel"
    assert args.hf_token == "tok"
    assert args.viggle_key == "vk"
    assert args.higgsfield_key == "hk"
    assert args.out == "cikti-klasoru"


def test_register_klip_rejects_bad_aspect():
    parser = argparse.ArgumentParser(prog="tubelens")
    sub = parser.add_subparsers(dest="cmd", required=True)
    klip.register(sub)
    with pytest.raises(SystemExit):
        parser.parse_args(["klip", "x", "--aspect", "7:9"])


def test_cmd_klip_prints_steps(tmp_path, monkeypatch, capsys):
    def fake(prompt, out_dir=None, **kw):
        return _write(Path(out_dir) / "video.mp4")

    monkeypatch.setattr(klip, "make_clip", fake)
    args = argparse.Namespace(
        prompt="bir klip", duration=4.0, aspect="16:9", provider="auto",
        style="", hf_token="", pexels_key="", viggle_key="", higgsfield_key="",
        out=str(tmp_path / "cikti"),
    )
    assert klip.cmd_klip(args) == 0
    out = capsys.readouterr().out
    assert "[1/2]" in out and "[2/2]" in out
    assert str(tmp_path / "cikti" / "video.mp4") in out


def test_cmd_klip_reports_error(tmp_path, monkeypatch, capsys):
    def boom(prompt, out_dir=None, **kw):
        raise klip.KlipError("tum saglayicilar kapali")

    monkeypatch.setattr(klip, "make_clip", boom)
    args = argparse.Namespace(
        prompt="bir klip", duration=4.0, aspect="16:9", provider="auto",
        style="", hf_token="", pexels_key="", viggle_key="", higgsfield_key="",
        out=str(tmp_path / "cikti"),
    )
    assert klip.cmd_klip(args) == 3
    captured = capsys.readouterr()
    assert "HATA" in captured.err
