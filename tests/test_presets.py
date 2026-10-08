"""presets.py birim testleri."""

from tubelens import presets


def test_all_six_presets_present():
    expected = ["sinematik", "anime", "2d", "3d", "minimal", "belgesel"]
    assert presets.PRESET_CHOICES == expected
    assert list(presets.PRESETS) == expected
    for key in expected:
        assert presets.PRESETS[key].strip()
        assert presets.VISUAL[key].strip()


def test_resolve_combines_preset_and_extra():
    text = presets.resolve("anime", "gece sehri")
    assert presets.PRESETS["anime"] in text
    assert "gece sehri" in text


def test_resolve_preset_only():
    assert presets.resolve("sinematik") == presets.PRESETS["sinematik"]
    assert presets.resolve("  belgesel  ") == presets.PRESETS["belgesel"]


def test_resolve_unknown_or_empty_preset_returns_extra():
    assert presets.resolve("", "yalniz stil") == "yalniz stil"
    assert presets.resolve("yok-boyle-preset", "ekstra") == "ekstra"
    assert presets.resolve("yok-boyle-preset") == ""


def test_visual_suffix_non_empty_for_all_presets():
    for key in presets.PRESET_CHOICES:
        suffix = presets.visual_suffix(key)
        assert suffix.strip()
        assert suffix.isascii()
    assert presets.visual_suffix("yok") == ""
    assert presets.visual_suffix("") == ""
