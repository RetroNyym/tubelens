"""assemble.py birim testleri (ffmpeg cagrisi yapilmaz)."""

from tubelens.assemble import words_to_srt
from tubelens.voice import Word


def test_words_to_srt_format():
    words = [
        Word("Merhaba", 0.0, 0.4),
        Word("dünya", 0.45, 0.9),
        Word("bugün", 1.0, 1.4),
        Word("güzel", 1.45, 1.8),
        Word("bir", 1.85, 2.0),
        Word("gün", 2.05, 2.3),
        Word("olacak", 2.35, 2.9),
    ]
    srt = words_to_srt(words, max_words=4, max_gap=0.6)
    cues = [b for b in srt.strip().split("\n\n") if b]
    assert len(cues) >= 2
    assert "-->" in srt
    assert "00:00:00,000 -->" in srt
    assert "Merhaba" in srt


def test_words_to_srt_empty():
    assert words_to_srt([]) == ""


def test_words_to_srt_single_word():
    srt = words_to_srt([Word("tek", 0.0, 0.5)])
    assert "tek" in srt
    assert srt.count("-->") == 1
