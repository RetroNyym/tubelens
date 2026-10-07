"""Hugging Face Space (Gradio) istemcisi - LTX metinden video, anahtarsiz.

ai-video-studio'daki hfspace istemcisinin TubeLens'e tasinmis surumudur.
Sadece LTX text-to-video kullanir; hata durumunda footage zinciri diger
kaynaklara (web gorseli / AI gorsel) duser.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import requests

from .config import REQUEST_TIMEOUT, USER_AGENT

LTX_SPACE = "Lightricks/ltx-video-distilled"
NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted"
HF_MODEL = "openai/gpt-oss-120b"
HF_ROUTER = "https://router.huggingface.co/v1/chat/completions"

_style_cache: dict[str, tuple[str, str]] = {}


class HfSpaceError(RuntimeError):
    pass


def _base(space: str) -> str:
    return "https://" + space.replace("/", "-").lower() + ".hf.space"


def _style(space: str) -> tuple[str, str]:
    cached = _style_cache.get(space)
    if cached:
        return cached
    base = _base(space)
    headers = {"User-Agent": USER_AGENT}
    for style, path in (("5", "/gradio_api/info"), ("4", "/info")):
        try:
            resp = requests.get(base + path, headers=headers, timeout=15)
            if resp.status_code == 200 and resp.content.lstrip()[:1] == b"{":
                _style_cache[space] = (style, base)
                return _style_cache[space]
        except requests.RequestException:
            continue
    raise HfSpaceError("Space erisilemiyor (asili/yanit yok): " + space)


def _prefix(space: str) -> tuple[str, str]:
    style, base = _style(space)
    return base, ("/gradio_api" if style == "5" else "")


def _hdr(token: str | None) -> dict[str, str]:
    return {"Authorization": "Bearer " + token} if token else {}


def call(
    space: str, endpoint: str, inputs: list, token: str | None = None, timeout: int = 600
):
    """Gradio /call uzerinden SSE ile sonuc bekler ve payload dondurur."""
    base, prefix = _prefix(space)
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = "Bearer " + token
    resp = requests.post(
        base + prefix + "/call" + endpoint,
        json={"data": inputs},
        headers=headers,
        timeout=REQUEST_TIMEOUT * 3,
    )
    if resp.status_code != 200:
        raise HfSpaceError(f"{space} {endpoint} baslatilamadi (HTTP {resp.status_code})")
    try:
        event_id = resp.json()["event_id"]
    except (ValueError, KeyError) as exc:
        raise HfSpaceError(
            f"{space} {endpoint} baslatilamadi: " + resp.text[:200]
        ) from exc
    sse = requests.get(
        f"{base}{prefix}/call{endpoint}/{event_id}",
        headers=_hdr(token),
        timeout=timeout,
    )
    text = sse.text
    m_err = re.search(r"event: error\s*\ndata:\s*(.*)", text)
    if m_err:
        detail = m_err.group(1).strip()[:300]
        if detail in ("null", "None", '""', ""):
            detail = (
                "space GPU hatasi veya anonim kota doldu (hata mesaji gizli); "
                "HF token girin veya biraz bekleyin"
            )
        raise HfSpaceError(f"{space} hatasi: {detail}")
    m_ok = re.search(r"event: complete\s*\ndata:\s*(.*)", text, re.S)
    if not m_ok:
        raise HfSpaceError(f"{space} sonuc donmedi")
    raw = m_ok.group(1).strip().splitlines()[0] if m_ok.group(1).strip() else ""
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HfSpaceError(f"{space} sonuc cozulemedi: {raw[:200]}") from exc
    if payload is None:
        raise HfSpaceError(f"{space} bos sonuc dondu")
    return payload


def _find_file(obj):
    if isinstance(obj, dict):
        if obj.get("path") or obj.get("url"):
            return obj
        for value in obj.values():
            found = _find_file(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_file(item)
            if found:
                return found
    return None


def _download_result(space: str, payload, dest: str | Path, token: str | None = None) -> Path:
    item = _find_file(payload)
    if not item:
        raise HfSpaceError(f"{space} sonucunda video bulunamadi")
    base, prefix = _prefix(space)
    urls: list[str] = []
    if item.get("url"):
        u = item["url"]
        urls.append(u if u.startswith("http") else base + u)
    if item.get("path"):
        for p in (prefix + "/file=", "/file=", "/gradio_api/file="):
            urls.append(f"{base}{p}{item['path']}")
    dest_path = Path(dest)
    last = ""
    for u in dict.fromkeys(urls):
        try:
            resp = requests.get(
                u, headers=_hdr(token), timeout=REQUEST_TIMEOUT * 30, stream=True
            )
            if resp.status_code != 200:
                last = f"HTTP {resp.status_code}"
                continue
            with dest_path.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
            if dest_path.exists() and dest_path.stat().st_size > 2048:
                return dest_path
            last = "dosya bos"
        except requests.RequestException as exc:
            last = str(exc)
    raise HfSpaceError(f"{space} video indirilemedi: {last}")


def _ltx_size(aspect: str) -> tuple[int, int]:
    return {
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "1:1": (512, 512),
        "4:3": (768, 576),
        "3:4": (576, 768),
    }.get(aspect, (1024, 576))


def _ltx_duration(duration: float) -> float:
    try:
        value = float(duration)
    except (TypeError, ValueError):
        value = 4.0
    return max(0.3, min(8.5, value))


def text_to_video(
    prompt: str,
    dest: str | Path,
    duration: float = 4.0,
    aspect: str = "16:9",
    token: str | None = None,
) -> Path:
    """LTX Space ile metinden kisa video klip uretir (ZeroGPU, anahtarsiz)."""
    w, h = _ltx_size(aspect)
    data = [
        (prompt or "")[:700],
        NEGATIVE,
        None,
        None,
        h,
        w,
        "text-to-video",
        _ltx_duration(duration),
        9,
        42,
        False,
        1,
        True,
    ]
    payload = call(LTX_SPACE, "/text_to_video", data, token=token, timeout=600)
    return _download_result(LTX_SPACE, payload, dest, token=token)
