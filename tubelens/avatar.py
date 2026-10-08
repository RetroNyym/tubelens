"""Konusma-avatar modu - statik gorsel + ses ile dudak senkron video uretir.

Saglayici sirasi (provider=auto):
  1. latentsync - hfspace.lipsync (HF Space, anahtarsiz/kota; --hf-token onerilir)
  2. hedra      - Hedra avatar API (anahtar: HEDRA_API_KEY)
  3. viggle     - viggle.animate + ses mux (anahtar: --viggle-key / VIGGLE_API_KEY)

audio_path yoksa text verilir; metin voice.synthesize ile seslendirilir.
Hepsi basarsiz olursa AvatarError, footage.FootageError gibi toplanan sorun
listesini mesaj olarak dondurur. Cikti: videos/<zaman>-<slug>/video.mp4 +
yanina meta.json (galeri okur).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from . import hfspace, viggle
from .config import USER_AGENT, VIDEO_DIR, ensure_dirs
from .klip import _slugify
from .voice import VoiceError, synthesize

HEDRA_BASE = "https://api.hedra.com/v3"
HEDRA_ENV_KEY = "HEDRA_API_KEY"
HEDRA_PROMPT = "A person speaking directly to the camera, natural expressions"
HEDRA_ASPECTS = ("16:9", "9:16", "1:1", "4:3", "3:4")
PROVIDERS = ("latentsync", "hedra", "viggle")
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv"}


class AvatarError(RuntimeError):
    pass


def _hedra_headers(key: str) -> dict[str, str]:
    return {"Authorization": "Key " + key, "User-Agent": USER_AGENT}


def _hedra_upload(key: str, path: str | Path) -> str:
    import mimetypes

    p = Path(path)
    try:
        content = p.read_bytes()
    except OSError as exc:
        raise AvatarError(f"Hedra yukleme dosyasi okunamadi: {p}") from exc
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    import requests

    try:
        resp = requests.post(
            HEDRA_BASE + "/files",
            files={"file": (p.name, content, ctype)},
            headers=_hedra_headers(key),
            timeout=180,
        )
    except requests.RequestException as exc:
        raise AvatarError(f"Hedra yukleme hatasi: {exc}") from exc
    if resp.status_code != 200:
        raise AvatarError(f"Hedra yukleme HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise AvatarError(f"Hedra yaniti JSON degil: {resp.text[:200]}") from exc
    url = data.get("url")
    if not url:
        raise AvatarError("Hedra upload url alinamadi: " + json.dumps(data)[:300])
    return str(url)


def _hedra_poll(key: str, job_id: str, *, timeout: float = 1200.0, interval: float = 6.0) -> str:
    import time

    import requests

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{HEDRA_BASE}/jobs/{job_id}/status",
                headers=_hedra_headers(key),
                timeout=40,
            )
        except requests.RequestException as exc:
            raise AvatarError(f"Hedra durum sorgusu hatasi: {exc}") from exc
        if resp.status_code != 200:
            raise AvatarError(f"Hedra durum HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise AvatarError(f"Hedra durum yaniti JSON degil: {resp.text[:200]}") from exc
        status = data.get("status")
        if status == "COMPLETED":
            try:
                detail = requests.get(
                    f"{HEDRA_BASE}/jobs/{job_id}", headers=_hedra_headers(key), timeout=40
                ).json()
            except ValueError as exc:
                raise AvatarError("Hedra is detayi JSON degil") from exc
            for item in detail.get("outputs") or []:
                if isinstance(item, dict) and item.get("url"):
                    return str(item["url"])
            raise AvatarError("Hedra cikti url yok: " + json.dumps(detail)[:400])
        if status == "FAILED":
            raise AvatarError(str(data.get("error") or json.dumps(data)[:300]))
        time.sleep(interval)
    raise AvatarError("Hedra zaman asimi")


def _download(url: str, dest: str | Path) -> Path:
    import requests

    from .config import REQUEST_TIMEOUT

    path = Path(dest)
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT * 30,
            stream=True,
        )
    except requests.RequestException as exc:
        raise AvatarError(f"Video indirme hatasi: {exc}") from exc
    if resp.status_code != 200:
        raise AvatarError(f"Video indirme HTTP {resp.status_code}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                fh.write(chunk)
    if not path.exists() or path.stat().st_size < 1024:
        raise AvatarError("Indirilen video bos")
    return path


def _latentsync_avatar(
    image_path: str | Path, audio_path: str | Path, dest: str | Path, token: str = ""
) -> Path:
    """LatentSync Space ile gorsel + ses uzerinden dudak senkron video."""
    if not hfspace.available(hfspace.LATENTSYNC_SPACE, token or None):
        raise AvatarError(
            "LatentSync space erisilemiyor (HF kotasi/aside olabilir); "
            "--hf-token ile ucretsiz token verin ya da baska saglayici deneyin"
        )
    hfspace.lipsync(image_path, audio_path, dest, token=token or None)
    return Path(dest)


def _hedra_avatar(
    image_path: str | Path,
    audio_path: str | Path,
    dest: str | Path,
    *,
    key: str = "",
    prompt: str = HEDRA_PROMPT,
    aspect: str = "16:9",
) -> Path:
    """Hedra ile gorsel + sesten konusma-avatar video (anahtar gerekli)."""
    k = (key or os.environ.get(HEDRA_ENV_KEY) or "").strip()
    if not k:
        raise AvatarError(f"Hedra API anahtari gerekli ({HEDRA_ENV_KEY})")
    image_url = _hedra_upload(k, image_path)
    audio_url = _hedra_upload(k, audio_path)
    payload = {
        "input": {
            "prompt": prompt,
            "aspect_ratio": aspect if aspect in HEDRA_ASPECTS else "16:9",
            "resolution": "720p",
            "start_image": {"source": "url", "url": image_url},
            "audio": {"source": "url", "url": audio_url},
        }
    }
    import requests

    try:
        resp = requests.post(
            HEDRA_BASE + "/models/hedra-avatar",
            json=payload,
            headers=_hedra_headers(k),
            timeout=90,
        )
    except requests.RequestException as exc:
        raise AvatarError(f"Hedra istegi hatasi: {exc}") from exc
    if resp.status_code in (401, 403):
        raise AvatarError("Hedra anahtari gecersiz (401/403)")
    if resp.status_code != 200:
        raise AvatarError(f"Hedra HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise AvatarError(f"Hedra yaniti JSON degil: {resp.text[:200]}") from exc
    job_id = data.get("job_id")
    if not job_id:
        raise AvatarError("Hedra job id alinamadi: " + json.dumps(data)[:300])
    url = _hedra_poll(k, str(job_id))
    return _download(url, dest)


def _mux_audio(video: str | Path, audio: str | Path, dest: str | Path) -> Path:
    """Hareketli goruntuye seslendirmeyi ekler (ffmpeg ile ses mux)."""
    from .assemble import run_ffmpeg

    src = Path(video)
    tmp = Path(dest).with_name("mux-tmp.mp4")
    run_ffmpeg(
        [
            "-i", str(src),
            "-i", str(audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(tmp),
        ]
    )
    tmp.replace(Path(dest))
    return Path(dest)


def _viggle_avatar(
    image_path: str | Path,
    audio_path: str | Path,
    dest: str | Path,
    *,
    key: str = "",
    prompt: str = "natural idle motion, talking",
) -> Path:
    """Viggle ile karakteri hareketlendirir, sonra sesi mux eder."""
    anim = Path(dest).with_name("viggle-hareket.mp4")
    viggle.animate(image_path, anim, prompt=prompt, api_key=key)
    return _mux_audio(anim, audio_path, dest)


def _order(provider: str, *, viggle_key: str = "") -> list[str]:
    """Verilen provider icin denenecek saglayici listesini uretir."""
    name = (provider or "auto").strip().lower()
    name = {"hf": "latentsync"}.get(name, name)
    if name != "auto":
        if name not in PROVIDERS:
            raise AvatarError(
                f"Bilinmeyen saglayici: {provider} (secenekler: auto, "
                + ", ".join(PROVIDERS)
                + ")"
            )
        return [name]
    order = ["latentsync"]
    if (os.environ.get(HEDRA_ENV_KEY) or "").strip():
        order.append("hedra")
    if viggle.resolve_key(viggle_key):
        order.append("viggle")
    return order


def _audio_seconds(path: str | Path) -> float:
    """Ses suresini (sn) okur; okunamazsa 0.0 dondurur."""
    try:
        from mutagen.mp3 import MP3

        return round(float(MP3(str(path)).info.length), 2)
    except Exception:
        return 0.0


def _resolve_out(out_path: str | Path | None, image_path: Path) -> Path:
    """out_path dosya ise onu, klasor ise icindeki video.mp4'u dondurur."""
    if not out_path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return VIDEO_DIR / f"{stamp}-{_slugify(image_path.stem)}" / "video.mp4"
    p = Path(out_path)
    if p.suffix.lower() in VIDEO_SUFFIXES:
        return p
    return p / "video.mp4"


def make_avatar(
    image_path: str | Path,
    out_path: str | Path | None = None,
    *,
    audio_path: str | Path | None = None,
    text: str | None = None,
    voice: str | None = None,
    lang: str = "tr",
    tts_engine: str = "edge",
    provider: str = "auto",
    token: str = "",
    viggle_key: str = "",
    openai_key: str = "",
    elevenlabs_key: str = "",
) -> Path:
    """Gorsel + sesten konusma-avatar video uretir; video.mp4 yolunu dondurur.

    audio_path yoksa text seslendirilir (voice parametresi ses adi).
    out_path klasor ise icine video.mp4 yazilir; verilmezse
    videos/<zaman>-<slug>/video.mp4 kullanilir ve yanina meta.json birakilir.
    """
    image = Path(image_path)
    if not image.is_file():
        raise AvatarError(f"Gorsel bulunamadi: {image}")
    target = _resolve_out(out_path, image)

    if audio_path:
        audio = Path(audio_path)
        if not audio.is_file():
            raise AvatarError(f"Ses dosyasi bulunamadi: {audio}")
    elif (text or "").strip():
        audio = target.parent / "audio.mp3"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            synthesize(
                text.strip(),
                audio,
                voice,
                engine=(tts_engine or "edge").lower(),
                lang=lang,
                openai_key=openai_key,
                elevenlabs_key=elevenlabs_key,
            )
        except VoiceError as exc:
            raise AvatarError(f"Seslendirme hatasi: {exc}") from exc
    else:
        raise AvatarError("Ses gerekli: --audio dosyasi ya da --text metni verin")

    order = _order(provider, viggle_key=viggle_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    used = ""
    for name in order:
        try:
            if name == "latentsync":
                _latentsync_avatar(image, audio, target, token=token)
            elif name == "hedra":
                _hedra_avatar(image, audio, target)
            else:
                _viggle_avatar(image, audio, target, key=viggle_key)
            used = name
            break
        except Exception as exc:
            problems.append(f"{name}: {exc}")

    if not used:
        raise AvatarError(
            "Avatar video uretilemedi:\n  - "
            + "\n  - ".join(problems)
            + "\nCozumler: --hf-token (LatentSync), "
            + f"{HEDRA_ENV_KEY}, --viggle-key ya da --provider ile farkli "
            "saglayici deneyin"
        )
    if not target.exists() or target.stat().st_size == 0:
        raise AvatarError(f"{used} sonuc dosyasi olusturmadi: {target}")

    title = (text or "").strip() or image.stem
    meta = {
        "mode": "avatar",
        "title": title,
        "duration_sec": _audio_seconds(audio),
        "provider": used,
    }
    (target.parent / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """'avatar' alt komutunu argparse'a ekler (cli.main icin)."""
    p = subparsers.add_parser("avatar", help="gorsel + sesten konusma-avatar video uret")
    p.add_argument("--image", required=True, help="karakter gorseli (png/jpg)")
    p.add_argument("--audio", help="seslendirme dosyasi (mp3); yoksa --text gerekli")
    p.add_argument("--text", help="seslendirilecek metin (--audio yerine uretilir)")
    p.add_argument("--voice", help="ses adi (orn. tr-TR-EmelNeural)")
    p.add_argument("--lang", default="tr", help="metin dili (varsayilan tr)")
    p.add_argument(
        "--tts-engine",
        choices=["edge", "gtts", "openai", "elevenlabs"],
        default="edge",
        help="seslendirme motoru (varsayilan edge)",
    )
    p.add_argument(
        "--provider",
        default="auto",
        help="saglayici: auto, latentsync, hedra, viggle (varsayilan auto)",
    )
    p.add_argument("--hf-token", default="", help="Hugging Face token (LatentSync kotasi)")
    p.add_argument("--viggle-key", default="", help="Viggle API anahtari")
    p.add_argument("--openai-key", default="", help="OpenAI API anahtari (openai TTS icin)")
    p.add_argument("--elevenlabs-key", default="", help="ElevenLabs API anahtari")
    p.add_argument("--out", help="cikti dosyasi/klasoru (varsayilan videos/<zaman>-<slug>)")
    p.set_defaults(func=cmd_avatar)
    return p


def cmd_avatar(args: argparse.Namespace) -> int:
    """CLI: avatar uretir, adimlari ve son dosya yolunu basar."""
    ensure_dirs()
    if not args.audio and not args.text:
        print("  HATA: --audio ya da --text gerekli", file=sys.stderr)
        return 2
    if args.audio:
        print(f"[1/3] Ses dosyasi kullaniliyor: {args.audio}")
    else:
        print(f"[1/3] Seslendirme uretiliyor (motor={args.tts_engine})")
    print(f"[2/3] Avatar uretiliyor (saglayici={args.provider}): {args.image}")
    try:
        path = make_avatar(
            args.image,
            args.out or None,
            audio_path=args.audio,
            text=args.text,
            voice=args.voice,
            lang=args.lang,
            tts_engine=args.tts_engine,
            provider=args.provider,
            token=args.hf_token,
            viggle_key=args.viggle_key,
            openai_key=args.openai_key,
            elevenlabs_key=args.elevenlabs_key,
        )
    except AvatarError as exc:
        print(f"  HATA: {exc}", file=sys.stderr)
        return 3
    print(f"[3/3] Avatar hazir: {path}")
    return 0
