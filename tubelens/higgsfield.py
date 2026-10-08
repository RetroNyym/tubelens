"""Higgsfield API istemcisi - metinden video (anahtarli).

ai-video-studio'daki higgsfield istemcisinin TubeLens'e tasinmis surumudur.
Anahtar: parametre ("id:secret") ya da ortam degiskenleri HIGGSFIELD_API_KEY /
HIGGSFIELD_KEY_ID + HIGGSFIELD_KEY_SECRET ile verilir.
Akis: POST /<model> -> request id -> durum yoklamasi -> medya URL -> indirme.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from .config import REQUEST_TIMEOUT, USER_AGENT

BASE = "https://api.higgsfield.ai"
ENV_KEY = "HIGGSFIELD_API_KEY"
ENV_KEY_ID = "HIGGSFIELD_KEY_ID"
ENV_KEY_SECRET = "HIGGSFIELD_KEY_SECRET"
DEFAULT_MODEL = "bytedance/seedance-2.0/text-to-video"


class HiggsfieldError(RuntimeError):
    pass


def resolve_key(api_key: str = "") -> str:
    """'id:secret' biciminde anahtari parametre ya da ortam degiskenlerinden alir."""
    raw = (api_key or os.environ.get(ENV_KEY) or "").strip()
    if raw:
        return raw
    key_id = (os.environ.get(ENV_KEY_ID) or "").strip()
    secret = (os.environ.get(ENV_KEY_SECRET) or "").strip()
    return f"{key_id}:{secret}" if key_id and secret else ""


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": "Key " + key, "User-Agent": USER_AGENT}


def _find_media_url(obj):
    if isinstance(obj, str):
        low = obj.lower()
        if obj.startswith("http") and any(
            x in low for x in (".mp4", ".webm", ".mov", "/video", "cdn")
        ):
            return obj
        return None
    if isinstance(obj, dict):
        for k in ("video_url", "output_url", "download_url", "result_url", "url", "uri", "href"):
            v = obj.get(k)
            if isinstance(v, str) and v.startswith("http"):
                low = v.lower()
                if k in ("url", "uri", "href") and not any(
                    x in low for x in (".mp4", ".webm", ".mov", "cdn", "/output", "/video")
                ):
                    continue
                return v
        for v in obj.values():
            found = _find_media_url(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_media_url(v)
            if found:
                return found
    return None


def _get_json(url: str, key: str) -> dict:
    try:
        resp = requests.get(url, headers=_headers(key), timeout=40)
    except requests.RequestException as exc:
        raise HiggsfieldError(f"Higgsfield istegi hatasi: {exc}") from exc
    if resp.status_code != 200:
        raise HiggsfieldError(f"Higgsfield HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise HiggsfieldError(f"Higgsfield yaniti JSON degil: {resp.text[:200]}") from exc


def _poll(
    key: str,
    rid: str,
    status_url: str,
    *,
    timeout: float = 900.0,
    interval: float = 6.0,
    log=None,
) -> str:
    """Istek tamamlanana dek durum yoklar; medya URL'ini dondurur."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _get_json(status_url, key)
        status = str(data.get("status") or "").lower()
        if log:
            log(f"higgsfield {rid}: {status or data}")
        if status in ("completed", "complete", "succeeded", "success", "done", "ready"):
            url = _find_media_url(data)
            if not url:
                url = _find_media_url(_get_json(f"{BASE}/requests/{rid}", key))
            if not url:
                raise HiggsfieldError(
                    "Tamamlandi ama video url bulunamadi: " + json.dumps(data)[:400]
                )
            return str(url)
        if status in ("failed", "error", "cancelled", "canceled"):
            raise HiggsfieldError(str(data.get("error") or json.dumps(data)[:300]))
        time.sleep(interval)
    raise HiggsfieldError("Zaman asimi (video hala hazir degil)")


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
        raise HiggsfieldError(f"Video indirme hatasi: {exc}") from exc
    if resp.status_code != 200:
        raise HiggsfieldError(f"Video indirme HTTP {resp.status_code}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                fh.write(chunk)
    if not path.exists() or path.stat().st_size < 1024:
        raise HiggsfieldError("Indirilen video bos")
    return path


def generate(
    prompt: str,
    dest: str | Path,
    *,
    duration: float = 5.0,
    aspect: str = "16:9",
    resolution: str = "720p",
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    log=None,
) -> Path:
    """Higgsfield ile metinden video klip uretir (anahtar gerekli)."""
    key = resolve_key(api_key)
    if not key:
        raise HiggsfieldError(
            f"Higgsfield API anahtari gerekli ({ENV_KEY}='id:secret')"
        )
    payload = {
        "prompt": prompt,
        "duration": int(duration),
        "aspect_ratio": aspect,
        "resolution": resolution,
        "generate_audio": True,
    }
    try:
        resp = requests.post(
            f"{BASE}/{model}",
            json=payload,
            headers=_headers(key),
            timeout=90,
        )
    except requests.RequestException as exc:
        raise HiggsfieldError(f"Higgsfield istegi hatasi: {exc}") from exc
    if resp.status_code in (401, 403):
        raise HiggsfieldError("Higgsfield anahtari gecersiz (401/403)")
    if resp.status_code != 200:
        raise HiggsfieldError(f"Higgsfield HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise HiggsfieldError(f"Higgsfield yaniti JSON degil: {resp.text[:200]}") from exc
    rid = data.get("request_id") or data.get("id") or data.get("job_id")
    if not rid:
        raise HiggsfieldError("Request id alinamadi: " + json.dumps(data)[:300])
    status_url = data.get("status_url") or f"{BASE}/requests/{rid}/status"
    if log:
        log(f"higgsfield istegi alindi: {rid}")
    url = _poll(key, str(rid), str(status_url), log=log)
    return _download(url, dest)
