"""Freemium kota + cevrimdisi lisans anahtari.

Model:
  * Ucretsiz planda toplam 5 sorgu var.
  * Bir "sorgu" = AI gorunurluk kontrolunde bakilan bir anahtar kelime
    (scan --keywords a,b,c -> 3 sorgu). Kanal/videolarin sayisi kota yakmaz.
  * Kota bittiginde tarama ve rapor calisir, sadece AI kontrolu durur ve
    satin alma mesaji gosterilir (arac kismen kullanilabilir kalir).
  * Lisans anahtari imzalidir (HMAC-SHA256) ve cevrimdisi dogrulanir;
    sunucu gerekmez. Anahtari `python -m tubelens activate <ANAHTAR>` ile
    girersiniz; `status` komutu kalan hakki gosterir.
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

# Lisans imzalari icin anahtar. Kod acik kaynakli oldugu icin bilinirlik bir
# sorun degildir: anahtari bilmek yeni anahtar uretmenize izin verir, ancak
# bunu yapabilmek icin zaten kodu degistirmis olursunuz (self-host model).
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
        raise ValueError("Anahtar bicimi hatali (ornegin TL1-...-... olmali)")
    body, sig = parts[1], parts[2]
    if not hmac.compare_digest(sig, _sign(body.encode("ascii"))):
        raise ValueError("Anahtar imzasi gecersiz")
    try:
        payload = json.loads(_b64d(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Anahtar icerigi okunamadi") from exc
    exp = int(payload.get("exp") or 0)
    if exp and exp < time.time():
        raise ValueError("Anahtarin suresi dolmus")
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
            f"Ucretsiz sorgu hakkiniz bitti ({used}/{FREE_QUERIES} kullanildi, "
            f"kalan {left}).\n"
            f"Pro surume gecmek icin lisans anahtarinizi girin:\n"
            f"  python -m tubelens activate <ANAHTAR>\n"
            f"Satin alma: {PURCHASE_URL}"
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
            datetime.fromtimestamp(exp, timezone.utc).strftime("%Y-%m-%d") if exp else "suresiz"
        )
        lines = [
            "Lisans: PRO (aktif)",
            f"  anahtar sonu : ...{lic.get('key_suffix','')}",
            f"  aktivasyon   : {lic.get('activated_at','')}",
            f"  bitis        : {exp_txt}",
            "  AI sorgu     : sinirsiz",
        ]
        return "\n".join(lines)
    left = max(0, FREE_QUERIES - used)
    return (
        f"Lisans: UCRETSIZ PLAN\n"
        f"  kullanilan    : {used}/{FREE_QUERIES} sorgu\n"
        f"  kalan         : {left} sorgu\n"
        f"  pro icin      : python -m tubelens activate <ANAHTAR>\n"
        f"  satin alma    : {PURCHASE_URL}"
    )


def summary_line(state: dict | None = None) -> str:
    """CLI altinda kisa kota gosterimi icin."""
    state = state if state is not None else load()
    if state.get("license"):
        return "kota: PRO (sinirsiz)"
    used = int(state.get("used", 0))
    return f"kota: {max(0, FREE_QUERIES - used)}/{FREE_QUERIES} sorgu kaldi"
