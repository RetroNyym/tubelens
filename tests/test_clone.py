"""Klon hatti (transcript -> clone_script -> draft) testleri - ag disi."""

from __future__ import annotations

import json
from argparse import Namespace

import pytest

from tubelens import llm, youtube


# ---------------------------------------------------------------- transcript

_PLAYER_HTML = """
<html><script>
var ytInitialPlayerResponse = {"captions":{"playerCaptionsTracklistRenderer":{
 "captionTracks":[
  {"baseUrl":"https://www.youtube.com/timedtext?v=x&lang=en","languageCode":"en"},
  {"baseUrl":"https://www.youtube.com/timedtext?v=x&lang=tr","languageCode":"tr"}
 ]}},"videoDetails":{"title":"Kaynak"}};
</script></html>
"""

_JSON3 = {
    "events": [
        {"segs": [{"utf8": "Merhaba "}, {"utf8": "dunya"}]},
        {"segs": [{"utf8": "ikinci satir"}]},
    ]
}


def test_get_transcript_parses_json3(monkeypatch):
    monkeypatch.setattr(youtube, "_get", lambda *a, **k: _PLAYER_HTML)

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return _JSON3

    monkeypatch.setattr(youtube.requests, "get", lambda *a, **k: _Resp())
    text = youtube.get_transcript("https://www.youtube.com/watch?v=abcdefghijk")
    assert text == "Merhaba dunya ikinci satir"


def test_get_transcript_missing_captions(monkeypatch):
    html = '<script>var ytInitialPlayerResponse = {"videoDetails":{}};</script>'
    monkeypatch.setattr(youtube, "_get", lambda *a, **k: html)
    assert youtube.get_transcript("abcdefghijk") == ""


# ---------------------------------------------------------------- clone_script


def test_clone_script_schema(monkeypatch):
    captured = {}

    def fake_chat(prompt, **kwargs):
        captured["prompt"] = prompt
        return json.dumps(
            {
                "title": "Yeni Klon Baslik",
                "script": "Birinci paragraf.\n\nIkinci paragraf.",
                "video_terms": ["mystery", "dark room"],
                "description": "aciklama",
                "tags": ["tag"],
                "hashtags": ["#x"],
            }
        )

    monkeypatch.setattr(llm, "chat", fake_chat)
    source = {
        "title": "Rakip Video",
        "description": "Rakip aciklamasi",
        "transcript": "Rakip soyle diyor: ...",
        "views": 500000,
    }
    out = llm.clone_script(source, aspect="16:9", duration=60)
    assert out["title"] == "Yeni Klon Baslik"
    assert len(out["paragraphs"]) == 2
    assert out["video_terms"] == ["mystery", "dark room"]

    prompt = captured["prompt"]
    assert "Rakip Video" in prompt  # kaynak baslik prompt'ta
    assert "Rakip soyle diyor" in prompt  # transcript prompt'ta
    assert "kopya" in prompt.lower()  # birebir kopya yasagi
    assert "16:9" in prompt and "60 sn" in prompt


def test_clone_script_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky_chat(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise llm.LLMError("kuyruk dolu (429)")
        return json.dumps({"title": "T", "script": "metin " * 10, "video_terms": ["a"]})

    monkeypatch.setattr(llm, "chat", flaky_chat)
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    out = llm.clone_script({"title": "x"})
    assert out["title"] == "T"
    assert calls["n"] == 3


# ---------------------------------------------------------------- cli

def test_video_script_file_reads_draft(tmp_path, monkeypatch, capsys):
    from tubelens import cli

    draft = {
        "script": {
            "title": "Klon Baslik",
            "script": "Klon senaryo metni burada.",
            "paragraphs": ["Klon senaryo metni burada."],
            "video_terms": ["klip"],
            "description": "",
            "tags": [],
            "hashtags": [],
        }
    }
    script_file = tmp_path / "clone_draft.json"
    script_file.write_text(json.dumps(draft), encoding="utf-8")

    def fail_generate(*a, **k):
        raise AssertionError("LLM cagirilmamali (script-file modu)")

    monkeypatch.setattr(llm, "generate_script", fail_generate)

    code = cli.main(
        [
            "video",
            "--script-file", str(script_file),
            "--script-only",
            "--out", str(tmp_path / "cikti"),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "dosyadan yuklendi" in out
    saved = json.loads((tmp_path / "cikti" / "script.json").read_text(encoding="utf-8"))
    assert saved["title"] == "Klon Baslik"


def test_video_requires_topic_or_script_file():
    from tubelens import cli

    with pytest.raises(SystemExit):
        cli.main(["video"])


def test_cmd_clone_writes_draft(tmp_path, monkeypatch):
    from tubelens import cli, config

    source = {
        "id": "abcdefghijk",
        "url": "https://www.youtube.com/watch?v=abcdefghijk",
        "title": "Kaynak Video",
        "channel": "Kanal",
        "views": 100000,
        "length_seconds": 90,
    }
    monkeypatch.setattr(youtube, "get_video", lambda *a, **k: dict(source))
    monkeypatch.setattr(youtube, "get_transcript", lambda *a, **k: "transkript metni")
    monkeypatch.setattr(
        llm,
        "clone_script",
        lambda src, **k: {
            "title": "Klon",
            "script": "metin",
            "paragraphs": ["metin"],
            "video_terms": ["a"],
            "description": "",
            "tags": [],
            "hashtags": [],
        },
    )
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    args = Namespace(url="https://youtu.be/abcdefghijk", lang="tr", aspect="9:16", duration=0)
    code = cli.cmd_clone(args)
    assert code == 0
    draft_path = tmp_path / "clone_draft.json"
    assert draft_path.exists()
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert draft["source"]["title"] == "Kaynak Video"
    assert draft["script"]["title"] == "Klon"
    assert draft["duration"] == 81  # 90 * 0.9 yuvarlandi


def test_fix_dash_positional():
    from tubelens.cli import _fix_dash_positional

    assert _fix_dash_positional(["clone", "-kENU5WGw4k"]) == [
        "clone", "--", "-kENU5WGw4k",
    ]
    assert _fix_dash_positional(["clone", "-kX", "--duration", "30"]) == [
        "clone", "--duration", "30", "--", "-kX",
    ]
    assert _fix_dash_positional(["scan", "@k", "--limit", "5"]) == [
        "scan", "@k", "--limit", "5",
    ]
    assert _fix_dash_positional(["clone", "https://youtu.be/x"]) == [
        "clone", "https://youtu.be/x",
    ]
    assert _fix_dash_positional(["video", "-weird"]) == ["video", "-weird"]
