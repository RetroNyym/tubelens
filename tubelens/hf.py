"""Hugging Face router uzerinden FLUX/SD gorsel uretimi (token'li, coklu uc).

ai-video-studio'daki providers/hf.py modulunun TubeLens'e tasinmis surumudur;
FLUX ve Stable Diffusion endpoint'leri sirayla denenir, hepsi basarisizsa
HfImageError firlatilir. Uretim footage zincirinde Pollinations yedegine dusurur.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from .config import HEADERS, REQUEST_TIMEOUT

ENDPOINTS = (
    "https://router.huggingface.co/nscale/black-forest-labs/FLUX.1-schnell",
    "https://router.huggingface.co/fal-ai/krea-2/turbo",
    "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
    "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-3-medium-diffusers",
)

SIZES: dict[str, tuple[int, int]] = {
    "9:16": (768, 1344),
    "16:9": (1344, 768),
    "1:1": (1024, 1024),
    "4:3": (1344, 1008),
    "3:4": (1008, 1344),
}


class HfImageError(RuntimeError):
    """HF gorsel uretimi basarisiz: token yok/gecersiz ya da tum uc noktalar denendi."""


def image_size(aspect: str) -> tuple[int, int]:
    """Aspect oranini HF istek piksel boyutuna cevirir."""
    return SIZES.get(aspect, SIZES["9:16"])


def _looks_like_image(data: bytes) -> bool:
    return bool(data) and (
        data[:3] == b"\xff\xd8\xff"
        or data[:8] == b"\x89PNG\r\n\x1a\n"
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )


def _error_detail(data: bytes, content_type: str) -> str:
    if "json" in content_type or data[:1] in (b"{", b"["):
        return data[:160].decode("utf-8", "replace")
    return "gorsel olmayan yanit"


def generate_image(
    prompt: str,
    dest: str | Path,
    *,
    aspect: str = "9:16",
    token: str = "",
    timeout: int = 90,
) -> Path:
    """FLUX/SD endpoint'lerini sirayla deneyip gorseli dest dosyasina yazar.

    Token bossa HfImageError firlatir; token gecersizse (401/402/403) diger
    endpoint'ler denenmeden, degilse hepsi denendikten sonra hata dondurulur.
    """
    token = (token or "").strip()
    if not token:
        raise HfImageError("HF token yok; huggingface.co/settings/tcrets adresinden alin")
    if not timeout:
        timeout = REQUEST_TIMEOUT
    width, height = image_size(aspect)
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = json.dumps(
        {
            "inputs": str(prompt or ""),
            "parameters": {"width": width, "height": height, "num_inference_steps": 4},
        }
    ).encode("utf-8")
    last = "bilinmeyen hata"
    auth_failed = False
    for url in ENDPOINTS:
        try:
            resp = requests.post(url, headers=headers, data=payload, timeout=timeout)
        except requests.RequestException as exc:
            last = str(exc) or exc.__class__.__name__
            continue
        if resp.status_code in (401, 402, 403):
            auth_failed = True
            last = f"HTTP {resp.status_code} (token gecersiz veya kota dolu)"
            break
        if resp.status_code != 200:
            last = f"HTTP {resp.status_code} -> {url}"
            continue
        data = resp.content
        if _looks_like_image(data):
            out = Path(dest)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            return out
        last = _error_detail(data, str(resp.headers.get("Content-Type") or ""))
    if auth_failed:
        raise HfImageError("HF token gecersiz veya kota dolu: " + str(last))
    raise HfImageError(
        "HF gorsel uretilemedi (tum endpoint'ler denendi): " + str(last)
    )
