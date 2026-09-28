"""TubeLens markasi: logo (SVG + PNG) ve urun imzasi.

SVG panel/rapor HTML'inde gomulu kullanilir; PNG video filigraani
icin Pillow ile uretilir (Pillow yoksa filigran sessizce atlanir).
"""

from __future__ import annotations

from pathlib import Path

NAME = "TubeLens"
SIGNATURE = "TubeLens ile üretildi"
SIGNATURE_LINE = "— TubeLens ile üretildi"

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<defs><linearGradient id="tl" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#5b8cff"/><stop offset="1" stop-color="#8c5bff"/>'
    "</linearGradient></defs>"
    '<circle cx="32" cy="32" r="26" fill="none" stroke="url(#tl)" stroke-width="5.5"/>'
    '<circle cx="32" cy="32" r="15.5" fill="url(#tl)"/>'
    '<path d="M27.5 24.8 L41.5 32 L27.5 39.2 Z" fill="#0f1115" opacity=".9"/>'
    '<circle cx="21.5" cy="21.5" r="3.2" fill="#fff" opacity=".5"/>'
    "</svg>"
)

FAVICON = "data:image/svg+xml," + (
    SVG.replace("<", "%3C").replace(">", "%3E").replace('"', "'")
    .replace("#", "%23").replace("\n", "")
)


def logo_png(path: Path, size: int = 512) -> Path:
    """Video filigraani icin seffaf PNG logo cizer (Pillow gerekir)."""
    from PIL import Image, ImageDraw  # noqa: PLC0415 - istege bagli bagimlilik

    scale = size / 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    ring = (91, 140, 255, 235)
    ring_w = int(44 * scale)
    r_out = int(200 * scale)
    c = size // 2
    box = (c - r_out, c - r_out, c + r_out, c + r_out)
    draw.ellipse(box, outline=ring, width=ring_w)

    r_in = int(120 * scale)
    draw.ellipse(
        (c - r_in, c - r_in, c + r_in, c + r_in), fill=(122, 112, 255, 238)
    )

    tri = [
        (int(218 * scale), int(196 * scale)),
        (int(332 * scale), int(256 * scale)),
        (int(218 * scale), int(316 * scale)),
    ]
    draw.polygon(tri, fill=(15, 17, 21, 230))

    hl = int(26 * scale)
    hx, hy = int(172 * scale), int(172 * scale)
    draw.ellipse((hx - hl, hy - hl, hx + hl, hy + hl), fill=(255, 255, 255, 130))

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


def ensure_logo_png(path: Path | None = None) -> Path | None:
    """Logo PNG yoksa uretir; Pillow yoksa None dondurur (filigran atlanir)."""
    if path is None:
        from .config import VIDEO_DIR  # noqa: PLC0415 - donuk import kacinir

        path = VIDEO_DIR / "branding" / "logo.png"
    if path.exists():
        return path
    try:
        return logo_png(path)
    except ImportError:
        return None
