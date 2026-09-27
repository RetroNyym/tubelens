"""Freemium kota + çevrimdışı lisans anahtarı.

Model:
  * Ücretsiz planda toplam 5 sorgu var.
  * Bir "sorgu" = AI görünürlük kontrolünde bakılan bir anahtar kelime
    (scan --keywords a,b,c -> 3 sorgu). Kanal/videoların sayısı kota yakmaz.
  * Kota bittiğinde tarama ve rapor çalışır; yalnızca AI adımı durur ve
    satın alma mesajı gösterilir (aracın geri kalanı kullanılır kalır).
  * Lisans anahtarı imzalıdır (HMAC-SHA256) ve çevrimdışı doğrulanır;
    sunucu gerekmez. Anahtarı `python -m tubelens activate <ANAHTAR>` ile
    girersiniz, `python -m tubelens status` kalan hakkınızı gösterir.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ensure_dirs

FREE_QUERIES = 5
QUOTA_PATH = DATA_DIR / "quota.json"
PURCHASE_URL = "https://github.com/RetroNyym/tubelens#lisans"  # satin alma adresi

# Lisans imzaları için anahtar. Kod açık kaynaklı olduğu için bu değerin
# bilinirliği sorun değildir: anahtarı bilip yeni bir anahtar üretebilmek için
# zaten kodu değiştirmiş olursunuz (self-host modeli).
_SECRET = b"tubelens.freemium.v1"
_PREFIX = "TL1"


class QuotaExceeded(RuntimeError):
    """Ucretsiz sorgu hakki bitti ve gecerli lisans yok."""


# ---------------------------------------------------------------- dosya


def _empty() -> dict[str, Any]:
    return {"used": 0, "license": None, "history": []}


def load() -> dict:
    ensure_dirs()
    if not QUOTA_PATH.exists():
        return _empty()
    try:
        data = json.loads(QUOTA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    data.setdefault("used", 0)
    data.setdefault("license", None)
    data.setdefault("history", [])
    return data


def save(state: dict) -> None:
    ensure_dirs()
    QUOTA_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- lisans


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: bytes) -> str:
    return _b64e(hmac.new(_SECRET, payload, hashlib.sha256).digest()[:18])


def generate_key(days: int | None = None) -> str:
    """Satici icin anahtar uretir. days=None -> sinirsiz sure."""
    payload = {
        "k": secrets.token_hex(4),
        "exp": int(time.time() + days * 86400) if days else 0,
        "n": int(time.time()),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{_PREFIX}-{body}-{_sign(body.encode('ascii'))}"


def validate_key(key: str) -> dict:
    """Anahtari dogrular, payload dondurur. Gecersizse ValueError firlatir."""
    key = (key or "").strip()
    parts = key.split("-")
    if len(parts) != 3 or parts[0] != _PREFIX:
        raise ValueError("Anahtar biçimi hatalı (ör. TL1-...-... olmalı)")
    body, sig = parts[1], parts[2]
    if not hmac.compare_digest(sig, _sign(body.encode("ascii"))):
        raise ValueError("Anahtar imzası geçersiz")
    try:
        payload = json.loads(_b64d(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Anahtar içeriği okunamadı") from exc
    exp = int(payload.get("exp") or 0)
    if exp and exp < time.time():
        raise ValueError("Anahtarın süresi dolmuş")
    return payload


def activate(key: str) -> dict:
    """Anahtari dogrular ve lisansi kaydeder."""
    payload = validate_key(key)
    state = load()
    state["license"] = {
        "key_suffix": key.split("-")[-1][:6],
        "activated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "expires": payload.get("exp") or None,
    }
    save(state)
    return state["license"]


# ---------------------------------------------------------------- kota


def is_licensed(state: dict | None = None) -> bool:
    state = state if state is not None else load()
    return bool(state.get("license"))


def remaining(state: dict | None = None) -> int:
    state = state if state is not None else load()
    if state.get("license"):
        return -1  # sinirsiz
    return max(0, FREE_QUERIES - int(state.get("used", 0)))


def ensure(n: int = 1) -> None:
    """n sorgu harcamak icin yeterli hak var mi? Yoksa QuotaExceeded."""
    state = load()
    if state.get("license"):
        return
    used = int(state.get("used", 0))
    if used + n > FREE_QUERIES:
        left = max(0, FREE_QUERIES - used)
        raise QuotaExceeded(
            f"Ücretsiz sorgu hakkınız bitti ({used}/{FREE_QUERIES} kullanıldı, "
            f"kalan {left}).\n"
            f"Pro sürüme geçmek için lisans anahtarınızı girin:\n"
            f"  python -m tubelens activate <ANAHTAR>\n"
            f"Satın alma: {PURCHASE_URL}"
        )


def consume(n: int = 1, label: str = "") -> dict:
    """n sorgu harcar. Lisansli hesapta sayaci tutmaz (raporlama icin not eder)."""
    ensure(n)
    state = load()
    if not state.get("license"):
        state["used"] = int(state.get("used", 0)) + n
    else:
        hist = state.setdefault("history", [])
        hist.append({"n": n, "label": label[:60], "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        del hist[:-200]
    save(state)
    return state


def status_text() -> str:
    state = load()
    used = int(state.get("used", 0))
    lic = state.get("license")
    if lic:
        exp = lic.get("expires")
        exp_txt = (
            datetime.fromtimestamp(exp, timezone.utc).strftime("%Y-%m-%d") if exp else "süresiz"
        )
        lines = [
            "Lisans: PRO (aktif)",
            f"  anahtar sonu : ...{lic.get('key_suffix','')}",
            f"  aktivasyon   : {lic.get('activated_at','')}",
            f"  bitiş        : {exp_txt}",
            "  AI sorgu     : sınırsız",
        ]
        return "\n".join(lines)
    left = max(0, FREE_QUERIES - used)
    return (
        f"Lisans: ÜCRETSİZ PLAN\n"
        f"  kullanılan    : {used}/{FREE_QUERIES} sorgu\n"
        f"  kalan         : {left} sorgu\n"
        f"  pro için      : python -m tubelens activate <ANAHTAR>\n"
        f"  satın alma    : {PURCHASE_URL}"
    )


def summary_line(state: dict | None = None) -> str:
    """CLI altinda kisa kota gosterimi icin."""
    state = state if state is not None else load()
    if state.get("license"):
        return "kota: PRO (sınırsız)"
    used = int(state.get("used", 0))
    return f"kota: {max(0, FREE_QUERIES - used)}/{FREE_QUERIES} sorgu kaldı"
