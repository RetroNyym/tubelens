"""llm.py birim testleri (ag gerektirmez)."""

import pytest

from tubelens.llm import LLMError, _as_list, _extract_json, _normalize


def test_extract_json_code_fence():
    raw = 'Burada metin var.\n```json\n{"title": "Merhaba", "script": "Ses metni"}\n```'
    data = _extract_json(raw)
    assert data["title"] == "Merhaba"


def test_extract_json_surrounding_text():
    raw = 'isim: {"title": "X", "script": "Y"} son metin'
    data = _extract_json(raw)
    assert data["script"] == "Y"


def test_extract_json_invalid_raises():
    with pytest.raises(LLMError):
        _extract_json("kesilmis { json")
    with pytest.raises(LLMError):
        _extract_json("[1, 2, 3]")


def test_as_list():
    assert _as_list("tek") == ["tek"]
    assert _as_list("  ") == []
    assert _as_list(["a", "", "b"]) == ["a", "b"]
    assert _as_list(None) == []
    assert _as_list(42) == []


def test_normalize_full_payload():
    out = _normalize(
        {
            "title": "Baslik",
            "script": "Birinci paragraf.\n\nIkinci paragraf.",
            "description": "Aciklama",
            "tags": ["a", "b"],
            "hashtags": ["#x", "#y"],
            "video_terms": ["kahve", "demleme"],
        }
    )
    assert out["title"] == "Baslik"
    assert len(out["paragraphs"]) == 2
    assert out["video_terms"][:2] == ["kahve", "demleme"]
    assert out["hashtags"] == ["x", "y"]
    assert out["tags"] == ["a", "b"]


def test_normalize_terms_fallback_from_script():
    out = _normalize({"script": "sabah koşusu faydaları üzerine uzun bir anlatım"})
    assert out["video_terms"]
    assert all(isinstance(t, str) for t in out["video_terms"])


def test_normalize_scenes_list():
    out = _normalize(
        {"scenes": [{"narration": "Bir"}, {"voiceover": "Iki"}], "title": "T"}
    )
    assert out["paragraphs"] == ["Bir", "Iki"]


def test_normalize_missing_script_raises():
    with pytest.raises(LLMError):
        _normalize({"title": "sadece baslik"})
