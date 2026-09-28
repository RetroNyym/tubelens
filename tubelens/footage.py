"""Video goruntu kaynaklari: Pexels (ucretsiz anahtar) veya lokal klasor.

MoneyPrinterTurbo tarzi pipeline icin stok/lorek goruntuleri hazirlar.
"""

from __future__ import annotations

import random
import time
from pathlib import Path

import requests

from .config import HEADERS, POLITE_DELAY, REQUEST_TIMEOUT

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}

_last_call = 0.0


class FootageError(RuntimeError):
    pass


def _polite() -> None:
    global _last_call
    wait = POLITE_DELAY - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def _download(url: str, dest: Path) -> Path:
    _polite()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT * 3, stream=True)
    except requests.RequestException as exc:
        raise FootageError(f"Indirme hatasi: {exc}") from exc
    if resp.status_code != 200:
        raise FootageError(f"Indirme HTTP {resp.status_code}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with tmp.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                fh.write(chunk)
    tmp.replace(dest)
    if dest.stat().st_size < 10_000:
        dest.unlink(missing_ok=True)
        raise FootageError("Indirilen dosya cok kucuk (reklam/sayfa HTML'i olabilir)")
    return dest


def from_local(folder: Path, count: int) -> list[Path]:
    """Lokal klasordeki videolari rastgele sectirir."""
    if not folder.is_dir():
        raise FootageError(f"Goruntu klasoru bulunamadi: {folder}")
    pool = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if not pool:
        raise FootageError(f"{folder} icinde desteklenen video dosyasi yok")
    random.shuffle(pool)
    picked = pool[:count]
    while len(picked) < count and len(pool) > 1:
        picked.extend(pool[: count - len(picked)])
    return picked


def _pick_file(files: list[dict], aspect: str) -> str | None:
    scored: list[tuple[int, str]] = []
    for item in files:
        url = item.get("link") or ""
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        if not url or not width or not height:
            continue
        if aspect == "9:16" and height < width:
            continue
        if aspect == "16:9" and width < height:
            continue
        score = width
        if width >= 1920 or height >= 1920:
            score += 2000
        if str(item.get("quality") or "").lower() in ("hd", "uhd", "2k", "4k"):
            score += 1000
        scored.append((score, url))
    if not scored:
        for item in files:
            url = item.get("link") or ""
            if url:
                scored.append((int(item.get("width") or 0), url))
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]


def from_pexels(
    queries: list[str],
    api_key: str,
    dest_dir: Path,
    count: int,
    aspect: str = "9:16",
) -> list[Path]:
    """Pexels arama API'sinden (ucretsiz) stok goruntu indirir."""
    if not api_key:
        raise FootageError("Pexels API anahtari yok")
    orientation = {"9:16": "portrait", "16:9": "landscape"}.get(aspect, "")
    dest_dir.mkdir(parents=True, exist_ok=True)
    picked: list[Path] = []
    seen_ids: set[int] = set()
    per_query = max(1, count // max(1, len(queries)) + 1)

    for query in queries:
        if len(picked) >= count:
            break
        _polite()
        params = {"query": query, "per_page": per_query * 2}
        if orientation:
            params["orientation"] = orientation
        try:
            resp = requests.get(
                PEXELS_SEARCH_URL,
                params=params,
                headers={"Authorization": api_key, **HEADERS},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise FootageError(f"Pexels istegi hatasi: {exc}") from exc
        if resp.status_code == 401:
            raise FootageError("Pexels API anahtari gecersiz (401)")
        if resp.status_code == 429:
            raise FootageError("Pexels limit asimi (429); biraz bekleyip tekrar deneyin")
        if resp.status_code != 200:
            raise FootageError(f"Pexels HTTP {resp.status_code}")
        try:
            photos = resp.json().get("videos") or []
        except ValueError as exc:
            raise FootageError("Pexels yaniti JSON degil") from exc

        for photo in photos:
            if len(picked) >= count:
                break
            vid = int(photo.get("id") or 0)
            if vid in seen_ids:
                continue
            url = _pick_file(photo.get("video_files") or [], aspect)
            if not url:
                continue
            seen_ids.add(vid)
            dest = dest_dir / f"pexels_{vid}.mp4"
            if dest.exists() and dest.stat().st_size > 10_000:
                picked.append(dest)
                continue
            try:
                picked.append(_download(url, dest))
            except FootageError:
                continue

    if not picked:
        raise FootageError(
            "Pexels sonuc bulunamadi; kelimeleri degistirin ya da --footage-dir ile "
            "kendi goruntulerinizi verin"
        )
    return picked


def gather(
    queries: list[str],
    *,
    pexels_key: str = "",
    footage_dir: str | Path | None = None,
    dest_dir: Path,
    count: int = 6,
    aspect: str = "9:16",
) -> list[Path]:
    """Kaynak secimi: lokal klasor varsa o, yoksa Pexels."""
    if footage_dir:
        return from_local(Path(footage_dir), count)
    if not pexels_key:
        raise FootageError(
            "Goruntu kaynagi yok. Iki ucretsiz secenek:\n"
            "  1) https://www.pexels.com/api/ ucretsiz anahtari alin ve\n"
            "     python -m tubelens video <konu> --pexels-key ANAHTAR   (bir kez, kaydedilir)\n"
            "  2) kendi videolarinizi verin: --footage-dir C:\\klasor"
        )
    return from_pexels(queries, pexels_key, dest_dir, count, aspect)
