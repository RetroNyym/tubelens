"""Uzaktan lisans doğrulama - LemonSqueezy License API.

Satın alma akışı:
  Müşteri ödeme yapar -> LemonSqueezy anahtar üretir -> kullanıcı
  `python -m tubelens activate <ANAHTAR>` der -> bu modül anahtarı
  LemonSqueezy'de aktive eder (instance = bu bilgisayar) ve dönen
  `license_key` + `instance_id` bilgilerini `data/quota.json`'a yazar.

Doğrulama kuralları:
  * Çevrimiçi validate en fazla `RECHECK_DAYS` günde bir yapılır
    (scan/report açılışında; bayat ise tek istek atılır).
  * API'ye ulaşılamazsa (kota / çevrimdışı / kesinti) son başarılı
    doğrulamadan itibaren `GRACE_DAYS` günlük tolerans tanınır.
  * Anahtar `expired` / `disabled` / `deactivated` ise lisans düşer ve
    kullanıcı ücretsiz plana döner.
  * `python -m tubelens deactivate` bu bilgisayardaki aktivasyonu
    serbest bırakır (activation limitini sıfırlar).

API: POST https://api.lemonsqueezy.com/v1/licenses/{activate|validate|deactivate}
     -H "Accept: application/json" -d license_key=... (form-urlencoded)
     60 istek/dakika hız sınırı vardır.
"""

from __future__ import annotations

import socket
import time
from datetime import datetime, timezone
from typing import Any

import requests

API_BASE = "https://api.lemonsqueezy.com/v1/licenses"
TIMEOUT = 15
RECHECK_DAYS = 7     # kac gunde bir cevrimici dogrulama
GRACE_DAYS = 30      # cevrimdisi tolerans suresi


class LicenseError(RuntimeError):
    """Lisans API'den olumsuz yanit (anahtar gecersiz / limit / kapali)."""


def _now() -> int:
    return int(time.time())


def _iso(ts: int | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def _post(action: str, payload: dict[str, str]) -> dict[str, Any]:
    """Lisans API'ye form-encoded POST atar."""
    url = f"{API_BASE}/{action}"
    try:
        resp = requests.post(
            url,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise LicenseError(f"agasbaglantisi: {exc}") from exc  # ag hatasi (grace icin)
    try:
        body = resp.json()
    except ValueError as exc:
        raise LicenseError(f"API gecersiz yanit (HTTP {resp.status_code})") from exc
    if resp.status_code >= 400:
        detail = body.get("error") if isinstance(body, dict) else None
        raise LicenseError(str(detail or f"HTTP {resp.status_code}"))
    if not isinstance(body, dict):
        raise LicenseError("API gecersiz govde")
    body["_http"] = resp.status_code
    return body


def is_network_error(exc: LicenseError) -> bool:
    """Hata bir ag/altyapi hatasi mi? (bunda grace uygulanir)"""
    return str(exc).startswith("agasbaglantisi")


def _instance_name() -> str:
    try:
        host = socket.gethostname() or "bilgisayar"
    except OSError:
        host = "bilgisayar"
    return f"tubelens@{host}"[:60]


def activate(key: str, instance_name: str | None = None) -> dict[str, Any]:
    """Anahtari LemonSqueezy'de aktive eder, yerel lisans kaydi dondurur."""
    body = _post(
        "activate",
        {"license_key": key.strip(), "instance_name": instance_name or _instance_name()},
    )
    if not body.get("activated"):
        raise LicenseError(str(body.get("error") or "Anahtar aktive edilemedi"))
    lk = body.get("license_key") or {}
    inst = body.get("instance") or {}
    meta = body.get("meta") or {}
    if lk.get("status") in ("expired", "disabled"):
        raise LicenseError(f"Anahtar durumu: {lk.get('status')}")
    expires_at = None
    if lk.get("expires_at"):
        try:
            expires_at = int(
                datetime.fromisoformat(str(lk["expires_at"]).replace("Z", "+00:00")).timestamp()
            )
        except ValueError:
            expires_at = None
    return {
        "mode": "online",
        "provider": "lemonsqueezy",
        "key": key.strip(),
        "instance_id": inst.get("id", ""),
        "key_id": lk.get("id"),
        "status": lk.get("status", ""),
        "product": meta.get("product_name", ""),
        "customer": meta.get("customer_name", "") or meta.get("customer_email", ""),
        "activated_at": _now(),
        "checked_at": _now(),
        "expires_at": expires_at,
        "key_suffix": (key.strip()[-6:]),
    }


def validate(lic: dict[str, Any]) -> dict[str, Any]:
    """Kayitli lisansi cevrimici dogrular; guncellenmis kayit dondurur.

    Hata firlatir:
      LicenseError (grace disi) -> lisans dusmeli
    Ag hatasi LicenseError olarak firlatir, `is_network_error` ile ayirt edilir.
    """
    payload = {"license_key": lic.get("key", "")}
    if lic.get("instance_id"):
        payload["instance_id"] = lic["instance_id"]
    body = _post("validate", payload)
    if not body.get("valid"):
        raise LicenseError(str(body.get("error") or "Anahtar gecersiz"))
    lk = body.get("license_key") or {}
    if lk.get("status") in ("expired", "disabled"):
        raise LicenseError(f"Anahtar durumu: {lk.get('status')}")
    updated = dict(lic)
    updated["checked_at"] = _now()
    updated["status"] = lk.get("status", updated.get("status", ""))
    if lk.get("expires_at"):
        try:
            updated["expires_at"] = int(
                datetime.fromisoformat(str(lk["expires_at"]).replace("Z", "+00:00")).timestamp()
            )
        except ValueError:
            pass
    return updated


def deactivate(lic: dict[str, Any]) -> bool:
    """Bu bilgisayardaki aktivasyonu serbest birakir (activation limiti icin)."""
    if not lic.get("key"):
        return False
    payload = {"license_key": lic["key"]}
    if lic.get("instance_id"):
        payload["instance_id"] = lic["instance_id"]
    try:
        body = _post("deactivate", payload)
    except LicenseError:
        return False
    return bool(body.get("deactivated"))


def check_stale(lic: dict[str, Any]) -> tuple[bool, dict[str, Any], str]:
    """Kayitli lisansi bayatliga gore dogrular.

    Donus: (gecerli mi, guncellenmis kayit, mesaj)
      - gecerli=True  -> lisans kullanilabilir
      - gecerli=False -> lisans dusmeli (mesaj aciklayicidir)
    """
    now = _now()
    checked = int(lic.get("checked_at") or 0)
    age_days = (now - checked) / 86400 if checked else 9999
    grace_ok = age_days <= GRACE_DAYS

    if lic.get("mode") != "online":
        # yerel (HMAC) anahtar: bayatlasmaya dayanikli, cevrimdisi dogrulanir
        exp = int(lic.get("expires_at") or 0)
        if exp and now > exp:
            return False, lic, "Yerel lisans süresi doldu."
        return True, lic, "Yerel lisans geçerli (çevrimdışı)."

    if age_days < RECHECK_DAYS:
        return True, lic, f"Son doğrulama {age_days:.0f} gün önce."

    try:
        updated = validate(lic)
        return True, updated, f"Çevrimiçi doğrulandı ({_iso(updated['checked_at'])})."
    except LicenseError as exc:
        if is_network_error(exc):
            if grace_ok:
                return (
                    True,
                    lic,
                    f"API'ye ulaşılamadı; {GRACE_DAYS} günlük tolerans içinde "
                    f"son doğrulama {age_days:.0f} gün önce.",
                )
            return False, lic, (
                f"API'ye ulaşılamıyor ve son doğrulamanın üzerinden "
                f"{age_days:.0f} gün geçti ({GRACE_DAYS} gün tolerans aşıldı)."
            )
        return False, lic, f"Lisans doğrulanamadı: {exc}"
