"""Video goruntu kaynaklari - coklu kaynak zinciri.

Sira: lokal klasor -> Pexels (anahtar) -> Pixabay (anahtar) ->
Pollinations AI gorsel + Ken Burns (ANAHTARSIZ son kaynak, asla bos kalmaz).
"""

from __future__ import annotations

import random
import time
import urllib.parse
from pathlib import Path

import requests

from .config import HEADERS, POLITE_DELAY, REQUEST_TIMEOUT

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/videos/"
POLLINATIONS_IMAGE_URL = "https://image.pollinations.ai/prompt/"
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


def from_pixabay(
    queries: list[str],
    api_key: str,
    dest_dir: Path,
    count: int,
    aspect: str = "9:16",
) -> list[Path]:
    """Pixabay video API'sinden (ucretsiz anahtar) stok goruntu indirir."""
    if not api_key:
        raise FootageError("Pixabay API anahtari yok")
    dest_dir.mkdir(parents=True, exist_ok=True)
    picked: list[Path] = []
    seen: set[int] = set()
    per_query = max(1, count // max(1, len(queries)) + 1)

    for query in queries:
        if len(picked) >= count:
            break
        _polite()
        params = {"key": api_key, "q": query, "per_page": per_query * 2, "safesearch": "true"}
        try:
            resp = requests.get(
                PIXABAY_SEARCH_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException as exc:
            raise FootageError(f"Pixabay istegi hatasi: {exc}") from exc
        if resp.status_code in (400, 401, 403):
            raise FootageError("Pixabay API anahtari gecersiz")
        if resp.status_code == 429:
            raise FootageError("Pixabay limit asimi (429); biraz bekleyin")
        if resp.status_code != 200:
            raise FootageError(f"Pixabay HTTP {resp.status_code}")
        try:
            hits = resp.json().get("hits") or []
        except ValueError as exc:
            raise FootageError("Pixabay yaniti JSON degil") from exc

        for hit in hits:
            if len(picked) >= count:
                break
            vid = int(hit.get("id") or 0)
            if not vid or vid in seen:
                continue
            url, width, height = _pick_pixabay_file(hit.get("videos") or {}, aspect)
            if not url:
                continue
            seen.add(vid)
            dest = dest_dir / f"pixabay_{vid}.mp4"
            if dest.exists() and dest.stat().st_size > 10_000:
                picked.append(dest)
                continue
            try:
                picked.append(_download(url, dest))
            except FootageError:
                continue

    if not picked:
        raise FootageError("Pixabay sonuc bulunamadi; kelimeleri degistirin")
    return picked


def _pick_pixabay_file(videos: dict, aspect: str) -> tuple[str, int, int]:
    best: tuple[int, str, int, int] = (0, "", 0, 0)
    for item in videos.values():
        url = item.get("url") or ""
        w = int(item.get("width") or 0)
        h = int(item.get("height") or 0)
        if not url or not w or not h:
            continue
        if aspect == "9:16" and h < w:
            continue
        if aspect == "16:9" and w < h:
            continue
        score = w * h
        if score > best[0]:
            best = (score, url, w, h)
    if best[1]:
        return best[1], best[2], best[3]
    for item in videos.values():
        url = item.get("url") or ""
        if url:
            return url, int(item.get("width") or 0), int(item.get("height") or 0)
    return "", 0, 0


def _ai_image_size(aspect: str) -> tuple[int, int]:
    return {"9:16": (768, 1344), "16:9": (1344, 768), "1:1": (1024, 1024)}.get(
        aspect, (768, 1344)
    )


def _still_to_clip(img: Path, dest: Path, size: tuple[int, int], dur: float = 3.4) -> Path:
    """Tek bir gorseli Ken Burns (yavas zoom) ile klip'e cevirir."""
    import subprocess

    from .assemble import ffmpeg_exe

    w, h = size
    frames = max(30, int(dur * 30))
    vf = (
        f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,"
        f"crop={w * 2}:{h * 2},"
        f"zoompan=z='min(zoom+0.0011,1.22)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={w}x{h}:fps=30,format=yuv420p"
    )
    cmd = [
        ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(img), "-vf", vf, "-frames:v", str(frames),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an", str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size < 10_000:
        dest.unlink(missing_ok=True)
        raise FootageError(f"Ken Burns klip uretilemedi: {(proc.stderr or '')[-300:]}")
    return dest


def from_ai_images(
    queries: list[str],
    dest_dir: Path,
    count: int,
    aspect: str = "9:16",
) -> list[Path]:
    """ANAHTARSIZ son kaynak: Pollinations ile gorsel uret, Ken Burns ile klip yap."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    size = _ai_image_size(aspect)
    picked: list[Path] = []
    pool = list(queries) or ["cinematic abstract background"]
    random.shuffle(pool)

    for i in range(count):
        query = pool[i % len(pool)]
        dest = dest_dir / f"aivis_{i:02d}.mp4"
        if dest.exists() and dest.stat().st_size > 10_000:
            picked.append(dest)
            continue
        prompt = (
            f"{query}, cinematic b-roll still, natural light, shallow depth of field, "
            "photorealistic, high detail, no text"
        )
        url = (
            POLLINATIONS_IMAGE_URL
            + urllib.parse.quote(prompt)
            + f"?width={size[0]}&height={size[1]}&nologo=true&seed={random.randint(1, 10**6)}&model=flux"
        )
        img = dest_dir / f"aivis_{i:02d}.jpg"
        last_err = ""
        for attempt in range(2):
            try:
                _download(url, img)
                last_err = ""
                break
            except FootageError as exc:
                last_err = str(exc)
                time.sleep(3 + attempt * 3)
        if last_err:
            raise FootageError(f"AI gorsel indirilemedi ({query!r}): {last_err}")
        try:
            picked.append(_still_to_clip(img, dest, size))
        except FootageError:
            continue

    if len(picked) < count:
        raise FootageError("AI gorsel klip uretimi basarisiz oldu")
    return picked


def gather(
    queries: list[str],
    *,
    pexels_key: str = "",
    pixabay_key: str = "",
    footage_dir: str | Path | None = None,
    dest_dir: Path,
    count: int = 6,
    aspect: str = "9:16",
    allow_ai: bool = True,
) -> list[Path]:
    """Kaynak zinciri: lokal -> Pexels -> Pixabay -> AI gorsel (asla bos kalmaz)."""
    if footage_dir:
        return from_local(Path(footage_dir), count)

    problems: list[str] = []
    if pexels_key:
        try:
            return from_pexels(queries, pexels_key, dest_dir, count, aspect)
        except FootageError as exc:
            problems.append(f"Pexels: {exc}")
    else:
        problems.append("Pexels: anahtar yok (https://www.pexels.com/api/)")

    if pixabay_key:
        try:
            return from_pixabay(queries, pixabay_key, dest_dir, count, aspect)
        except FootageError as exc:
            problems.append(f"Pixabay: {exc}")
    else:
        problems.append("Pixabay: anahtar yok (https://pixabay.com/api/docs/)")

    if allow_ai:
        try:
            return from_ai_images(queries, dest_dir, count, aspect)
        except FootageError as exc:
            problems.append(f"AI gorsel: {exc}")

    raise FootageError(
        "Goruntu kaynagi bulunamadi:\n  - "
        + "\n  - ".join(problems)
        + "\nCozumler: --pexels-key / --pixabay-key (ucretsiz), --footage-dir C:\\klasor "
        "ya da AI gorselleri acik tutun (varsayilan acik)"
    )
