"""Viggle API istemcisi - metinden video ve karakter animasyonu (anahtarli).

ai-video-studio'daki viggle istemcisinin TubeLens'e tasinmis surumudur.
Anahtar: parametre ile ya da ortam degiskeni VIGGLE_API_KEY ile verilir.
Akis: POST /videos -> durum yoklamasi -> video_url -> dosyaya indirme.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from .config import REQUEST_TIMEOUT, USER_AGENT

BASE = "https://apis.viggle.ai/v1"
ENV_KEY = "VIGGLE_API_KEY"


class ViggleError(RuntimeError):
    pass


def resolve_key(api_key: str = "") -> str:
    """Verilen anahtari ya da VIGGLE_API_KEY ortam degiskenini dondurur."""
    return (api_key or os.environ.get(ENV_KEY) or "").strip()


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + key, "User-Agent": USER_AGENT}


def _post_multipart(
    url: str,
    key: str,
    *,
    fields: dict | None = None,
    files: dict | None = None,
    timeout: int = 120,
) -> dict:
    try:
        resp = requests.post(
            url,
            data=fields or {},
            files=files or None,
            headers=_headers(key),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise ViggleError(f"Viggle istegi hatasi: {exc}") from exc
    if resp.status_code in (401, 403):
        raise ViggleError("Viggle anahtari gecersiz (401/403)")
    if resp.status_code == 429:
        raise ViggleError("Viggle limit asimi (429); biraz bekleyin")
    if resp.status_code != 200:
        raise ViggleError(f"Viggle HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise ViggleError(f"Viggle yaniti JSON degil: {resp.text[:200]}") from exc


def _poll(key: str, vid: str, *, timeout: float = 900.0, interval: float = 5.0,
          log=None) -> str:
    """Video hazir olana dek durum yoklar; sonuc URL'ini dondurur."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{BASE}/videos/{vid}", headers=_headers(key), timeout=40
            )
        except requests.RequestException as exc:
            raise ViggleError(f"Viggle durum sorgusu hatasi: {exc}") from exc
        if resp.status_code != 200:
            raise ViggleError(f"Viggle durum HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise ViggleError(f"Viggle durum yaniti JSON degil: {resp.text[:200]}") from exc
        status = data.get("status")
        progress = data.get("progress")
        if log:
            note = f"viggle {vid}: {status}" + (f" %{progress}" if progress is not None else "")
            log(note)
        if status == "ready":
            url = data.get("video_url") or data.get("url")
            if not url:
                raise ViggleError("Hazir ama video_url yok: " + json.dumps(data)[:300])
            return str(url)
        if status in ("failed", "cancelled"):
            raise ViggleError(str(data.get("error") or data.get("message") or status))
        time.sleep(interval)
    raise ViggleError("Zaman asimi (video hala hazir degil)")


def _download(url: str, dest: str | Path) -> Path:
    path = Path(dest)
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT * 30,
            stream=True,
        )
    except requests.RequestException as exc:
        raise ViggleError(f"Video indirme hatasi: {exc}") from exc
    if resp.status_code != 200:
        raise ViggleError(f"Video indirme HTTP {resp.status_code}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                fh.write(chunk)
    if not path.exists() or path.stat().st_size < 1024:
        raise ViggleError("Indirilen video bos")
    return path


def text_to_video(
    prompt: str,
    dest: str | Path,
    *,
    duration: float = 5.0,
    aspect: str = "16:9",
    api_key: str = "",
    resolution: str = "768p",
    quality: str = "low",
    log=None,
) -> Path:
    """Viggle ile metinden kisa video klip uretir (anahtar gerekli)."""
    key = resolve_key(api_key)
    if not key:
        raise ViggleError(
            f"Viggle API anahtari gerekli ({ENV_KEY} veya api_key parametresi)"
        )
    fields = {
        "prompt": prompt,
        "quality": quality,
        "duration_s": str(max(3, min(15, int(duration)))),
        "resolution": resolution,
        "aspect_ratio": aspect,
        "enhance": "true",
        "watermark": "false",
    }
    data = _post_multipart(BASE + "/videos", key, fields=fields, timeout=90)
    vid = data.get("id")
    if not vid:
        raise ViggleError("Video id alinamadi: " + json.dumps(data)[:300])
    if log:
        log(f"viggle istegi alindi: {vid}")
    url = _poll(key, str(vid), log=log)
    return _download(url, dest)


def animate(
    image_path: str | Path,
    dest: str | Path,
    *,
    prompt: str = "",
    api_key: str = "",
    log=None,
) -> Path:
    """Karakter gorselini Viggle ile hareketlendirir (ses sonradan eklenir)."""
    key = resolve_key(api_key)
    if not key:
        raise ViggleError(
            f"Viggle API anahtari gerekli ({ENV_KEY} veya api_key parametresi)"
        )
    path = Path(image_path)
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ViggleError(f"Gorsel okunamadi: {path}") from exc
    ctype = "image/png" if content[:4] == b"\x89PNG" else "image/jpeg"
    fields = {"watermark": "false"}
    if prompt:
        fields["prompt"] = prompt
    files = {"character_image": (path.name, content, ctype)}
    data = _post_multipart(BASE + "/videos", key, fields=fields, files=files, timeout=120)
    vid = data.get("id")
    if not vid:
        raise ViggleError("Animasyon id alinamadi: " + json.dumps(data)[:300])
    if log:
        log(f"viggle animasyon istegi alindi: {vid}")
    url = _poll(key, str(vid), log=log)
    return _download(url, dest)
