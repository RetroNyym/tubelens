"""voice.py birim testleri (ag gerektirmez - gercek TTS cagrilari test edilmez)."""

import pytest

from tubelens.voice import (
    ENGINES,
    VoiceError,
    Word,
    _alignment_words,
    _estimate_words,
    default_voice,
    synthesize,
)


def test_engines_catalog():
    assert ENGINES == ("edge", "gtts", "openai", "elevenlabs")


def test_default_voice_per_lang():
    assert default_voice("tr") == "tr-TR-ahmetNeural"
    assert default_voice("zz").startswith("en-")


def test_estimate_words_covers_duration():
    words = _estimate_words("bir iki uc dort bes", 10.0)
    assert len(words) == 5
    assert words[0].start == 0.0
    assert words[-1].end == pytest.approx(10.0, abs=0.05)
    for prev, cur in zip(words, words[1:]):
        assert cur.start >= prev.end - 1e-6


def test_estimate_words_empty():
    assert _estimate_words("   ", 10.0) == []
    assert _estimate_words("metin", 0.0) == []


def test_alignment_words_from_character_timing():
    text = "gun dogdu"
    alignment = {
        "characters": list(text),
        "character_start_times_seconds": [0.0 + i * 0.1 for i in range(len(text))],
        "character_end_times_seconds": [0.1 + i * 0.1 for i in range(len(text))],
    }
    words = _alignment_words(text, alignment)
    assert [w.text for w in words] == ["gun", "dogdu"]
    assert words[0].start == 0.0
    assert words[1].end == pytest.approx(0.1 + (len(text) - 1) * 0.1)


def test_alignment_words_bad_payload_returns_empty():
    assert _alignment_words("x", {}) == []
    assert _alignment_words("abc", {"characters": ["a"], "character_start_times_seconds": []}) == []


def test_synthesize_rejects_empty_text(tmp_path):
    with pytest.raises(VoiceError):
        synthesize("   ", tmp_path / "a.mp3", engine="edge")


def test_synthesize_rejects_unknown_engine(tmp_path):
    with pytest.raises(VoiceError):
        synthesize("merhaba", tmp_path / "a.mp3", engine="yok-boyle")


def test_openai_without_key_raises_before_network(tmp_path):
    with pytest.raises(VoiceError):
        synthesize("merhaba", tmp_path / "a.mp3", engine="openai", openai_key="")


def test_elevenlabs_without_key_raises_before_network(tmp_path):
    with pytest.raises(VoiceError):
        synthesize("merhaba", tmp_path / "a.mp3", engine="elevenlabs", elevenlabs_key="")


def test_word_dataclass():
    w = Word("selam", 1.0, 1.5)
    assert (w.text, w.start, w.end) == ("selam", 1.0, 1.5)
