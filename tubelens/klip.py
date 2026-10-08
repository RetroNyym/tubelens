"""Metinden Klip modu - tek prompt'tan kisa video klip uretir.

Saglayici sirasi (provider=auto):
  1. ltx          - hfspace.text_to_video (HF ZeroGPU, anahtarsiz; kota dolabilir)
  2. pollinations - asagidaki _pollinations_video (anahtar: POLLINATIONS_API_KEY)
  3. viggle       - viggle.text_to_video (anahtar: --viggle-key / VIGGLE_API_KEY)
  4. higgsfield   - higgsfield.generate (anahtar: --higgsfield-key / HIGGSFIELD_API_KEY)

Explicit provider adi yalniz o saglayiciyi denetir. Hepsinin basilmasi halinde
KlipError, footage.FootageError gibi toplanan sorun listesini mesaj olarak
dondurur. Cikti: videos/<zaman>-<slug>/video.mp4 + meta.json (galeri okur).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

from . import hfspace, higgsfield, viggle
from .config import USER_AGENT, VIDEO_DIR, ensure_dirs

PROVIDERS = ("ltx", "pollinations", "viggle", "higgsfield")
ASPECTS = ("16:9", "9:16", "1:1", "4:3", "3:4")
POLLINATIONS_VIDEO_URL = "https://gen.pollinations.ai/video/"
POLLINATIONS_ENV_KEY = "POLLINATIONS_API_KEY"


class KlipError(RuntimeError):
    pass


def _slugify(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "klip"


def _pollinations_video(
    prompt: str,
    dest: str | Path,
    *,
    duration: float = 4.0,
    aspect: str = "16:9",
    api_key: str = "",
    timeout: int = 600,
) -> Path:
    """Pollinations video ucu (anahtarli; anahtar POLLINATIONS_API_KEY)."""
    key = (api_key or os.environ.get(POLLINATIONS_ENV_KEY) or "").strip()
    if not key:
        raise KlipError(
            f"Pollinations video icin API anahtari gerekli ({POLLINATIONS_ENV_KEY})"
        )
    url = (
        POLLINATIONS_VIDEO_URL
        + urllib.parse.quote(prompt, safe="")
        + f"?duration={int(duration)}&aspect_ratio={urllib.parse.quote(aspect)}"
    )
    try:
        resp = requests.get(
            url,
            headers={"Authorization": "Bearer " + key, "User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise KlipError(f"Pollinations video istegi hatasi: {exc}") from exc
    if resp.status_code != 200:
        raise KlipError(f"Pollinations video HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.content
    if data[4:8] != b"ftyp" and data[:4] != b"\x00\x00\x00\x18":
        if data[:1] in (b"{", b"<") or not data:
            raise KlipError(
                "Pollinations video donmedi: " + data[:200].decode("utf-8", "replace")
            )
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if path.stat().st_size < 1024:
        raise KlipError("Pollinations video bos dondu")
    return path


def _order(provider: str, *, viggle_key: str = "", higgsfield_key: str = "") -> list[str]:
    """Verilen provider icin denenecek saglayici listesini uretir."""
    name = (provider or "auto").strip().lower()
    name = {"ltx-video": "ltx", "hf": "ltx"}.get(name, name)
    if name != "auto":
        if name not in PROVIDERS:
            raise KlipError(
                f"Bilinmeyen saglayici: {provider} (secenekler: auto, "
                + ", ".join(PROVIDERS)
                + ")"
            )
        return [name]
    order = ["ltx", "pollinations"]
    if viggle.resolve_key(viggle_key):
        order.append("viggle")
    if higgsfield.resolve_key(higgsfield_key):
        order.append("higgsfield")
    return order


def _out_dir(out_dir: str | Path | None, prompt: str) -> Path:
    if out_dir:
        return Path(out_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return VIDEO_DIR / f"{stamp}-{_slugify(prompt)}"


def make_clip(
    prompt: str,
    out_dir: str | Path | None = None,
    *,
    duration: float = 4.0,
    aspect: str = "16:9",
    provider: str = "auto",
    style: str = "",
    hf_token: str = "",
    viggle_key: str = "",
    higgsfield_key: str = "",
) -> Path:
    """Prompt'tan video klip uretir; video.mp4 yolunu dondurur.

    out_dir verilmezse videos/<zaman>-<slug> klasorune yazar ve icine
    meta.json biraktirir (galeri bu dosyayi okur).
    """
    text = (prompt or "").strip()
    if not text:
        raise KlipError("Prompt bos olamaz")
    try:
        dur = float(duration)
    except (TypeError, ValueError) as exc:
        raise KlipError(f"Gecersiz sure: {duration!r}") from exc
    if dur <= 0:
        raise KlipError(f"Gecersiz sure: {dur}")
    order = _order(provider, viggle_key=viggle_key, higgsfield_key=higgsfield_key)
    full = ", ".join(p for p in (text, (style or "").strip()) if p)
    target = _out_dir(out_dir, text)
    target.mkdir(parents=True, exist_ok=True)
    dest = target / "video.mp4"

    problems: list[str] = []
    used = ""
    for name in order:
        try:
            if name == "ltx":
                hfspace.text_to_video(
                    full, dest, duration=min(dur, 8.5), aspect=aspect,
                    token=hf_token or None,
                )
            elif name == "pollinations":
                _pollinations_video(full, dest, duration=dur, aspect=aspect)
            elif name == "viggle":
                viggle.text_to_video(
                    full, dest, duration=dur, aspect=aspect, api_key=viggle_key
                )
            else:
                higgsfield.generate(
                    full, dest, duration=min(dur, 10), aspect=aspect,
                    api_key=higgsfield_key,
                )
            used = name
            break
        except Exception as exc:
            problems.append(f"{name}: {exc}")

    if not used:
        raise KlipError(
            "Klip uretilemedi:\n  - "
            + "\n  - ".join(problems)
            + "\nCozumler: --hf-token (LTX kotasi icin), "
            + f"{POLLINATIONS_ENV_KEY}, --viggle-key, --higgsfield-key "
            "ya da --provider ile farkli saglayici deneyin"
        )
    if not dest.exists() or dest.stat().st_size == 0:
        raise KlipError(f"{used} sonuc dosyasi olusturmadi: {dest}")

    meta = {
        "mode": "klip",
        "title": text,
        "duration_sec": round(dur, 2),
        "aspect": aspect,
        "provider": used,
    }
    (target / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return dest


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """'klip' alt komutunu argparse'a ekler (cli.main icin)."""
    p = subparsers.add_parser("klip", help="metinden kisa video klip uret")
    p.add_argument("prompt", help="klip aciklamasi / metinden video prompt'u")
    p.add_argument("--duration", type=float, default=4.0, help="klip suresi sn (varsayilan 4)")
    p.add_argument(
        "--aspect", choices=list(ASPECTS), default="16:9", help="video formati"
    )
    p.add_argument(
        "--provider",
        default="auto",
        help="saglayici: auto, ltx, pollinations, viggle, higgsfield (varsayilan auto)",
    )
    p.add_argument("--style", default="", help="stil eki (orn. belgesel, sinematik)")
    p.add_argument("--hf-token", default="", help="Hugging Face token (LTX/LatentSync kotasi)")
    p.add_argument("--viggle-key", default="", help="Viggle API anahtari")
    p.add_argument("--higgsfield-key", default="", help="Higgsfield anahtari (id:secret)")
    p.add_argument("--out", default="", help="cikti klasoru (varsayilan videos/<zaman>-<slug>)")
    p.set_defaults(func=cmd_klip)
    return p


def cmd_klip(args: argparse.Namespace) -> int:
    """CLI: klip uretir, adimlari ve son dosya yolunu basar."""
    ensure_dirs()
    print(
        f"[1/2] Metinden klip uretiliyor ({args.duration:g} sn, {args.aspect}, "
        f"saglayici={args.provider}): {args.prompt[:70]}"
    )
    try:
        path = make_clip(
            args.prompt,
            args.out or None,
            duration=args.duration,
            aspect=args.aspect,
            provider=args.provider,
            style=args.style,
            hf_token=args.hf_token,
            viggle_key=args.viggle_key,
            higgsfield_key=args.higgsfield_key,
        )
    except KlipError as exc:
        print(f"  HATA: {exc}", file=sys.stderr)
        return 3
    print(f"[2/2] Klip hazir: {path}")
    return 0
