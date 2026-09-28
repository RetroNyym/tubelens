"""Marka varliklari: logo PNG, favicon, imza."""

from __future__ import annotations

from pathlib import Path

from tubelens import brand


def test_svg_is_inline_svg():
    assert brand.SVG.startswith("<svg")
    assert "linearGradient" in brand.SVG
    assert "5b8cff" in brand.SVG  # panel rengiyle ayni ton


def test_favicon_data_uri():
    assert brand.FAVICON.startswith("data:image/svg+xml,")
    assert "%23" in brand.FAVICON  # # kacirilmis (CSS url icin)
    assert '"' not in brand.FAVICON.split(",", 1)[1][:10]


def test_signature_line():
    assert "TubeLens" in brand.SIGNATURE_LINE
    assert brand.SIGNATURE_LINE not in brand.SIGNATURE_LINE * 0 + ""


def test_logo_png(tmp_path: Path):
    try:
        out = brand.logo_png(tmp_path / "logo.png", size=128)
    except ImportError:
        import pytest

        pytest.skip("Pillow yok")
    data = out.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert out.stat().st_size > 500
    # tekrar cagri dosyayi uzerine yazar
    out2 = brand.logo_png(tmp_path / "logo.png", size=128)
    assert out2 == out


def test_ensure_logo_png(tmp_path: Path):
    try:
        out = brand.ensure_logo_png(tmp_path / "branding" / "logo.png")
    except ImportError:
        import pytest

        pytest.skip("Pillow yok")
    assert out is not None and out.exists()
    # ikinci cagri mevcut dosyayi kullanir
    assert brand.ensure_logo_png(out) == out
