"""Anahtarsiz LLM istemcisi (Pollinations) - MoneyPrinterTurbo tarzi senaryo uretimi.

API anahtari gerekmez; OpenAI uyumlu chat/completions uzerinden calisir.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

import requests

JSON_ENDPOINTS = (
    "https://text.pollinations.ai/openai",
    "https://gen.pollinations.ai/v1/chat/completions",
)
TEXT_ENDPOINT = "https://text.pollinations.ai/"

HEADERS = {"Content-Type": "application/json"}

LANG_NAMES = {
    "tr": "Turkce",
    "en": "English",
    "de": "Deutsch",
    "fr": "Francais",
    "es": "Espanol",
    "ar": "Arabic",
    "ru": "Russian",
}

SCRIPT_KEYS = ("title", "script", "video_terms", "description", "tags", "hashtags")


class LLMError(RuntimeError):
    pass


def chat(
    prompt: str,
    system: str | None = None,
    model: str = "openai",
    temperature: float = 0.9,
    timeout: int = 90,
    retries: int = 2,
    api_key: str = "",
) -> str:
    """Tek seferlik sohbet; OpenAI-uyumlu uc noktayi deneyip duz metin yedegine duser."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages, "temperature": temperature}
    headers = dict(HEADERS)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        for url in JSON_ENDPOINTS:
            try:
                resp = requests.post(
                    url, json=payload, headers=headers, timeout=timeout
                )
            except requests.RequestException as exc:
                last_err = exc
                continue
            if resp.status_code != 200:
                last_err = LLMError(f"HTTP {resp.status_code} -> {url}")
                continue
            try:
                content = resp.json()["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                last_err = exc
                continue
            content = str(content).strip() if content else ""
            if not content:
                last_err = LLMError("bos yanit geldi")
                continue
            if content.startswith('{"role"'):
                last_err = LLMError("model mesaj nesnesi dondurdu (bos icerik)")
                continue
            return content
        try:
            resp = requests.post(TEXT_ENDPOINT, json=payload, headers=headers, timeout=timeout)
            text = resp.text.strip()
            if resp.status_code == 200 and text and not text.startswith('{"role"'):
                return text
            last_err = LLMError(f"duz metin HTTP {resp.status_code}")
        except requests.RequestException as exc:
            last_err = exc
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    raise LLMError(f"LLM istekleri basarisiz: {last_err}")


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Senaryo JSON olarak okunamadi: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("Senaryo JSON nesnesi degil")
    return data


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    script = ""
    for key in ("script", "narration", "voiceover", "content", "text", "body"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            script = value.strip()
            break
    if not script:
        scenes = data.get("scenes") or data.get("paragrafs") or data.get("paragraphs")
        if isinstance(scenes, list):
            parts = []
            for scene in scenes:
                if isinstance(scene, str) and scene.strip():
                    parts.append(scene.strip())
                elif isinstance(scene, dict):
                    for key in ("narration", "voiceover", "text", "content", "scene"):
                        value = scene.get(key)
                        if isinstance(value, str) and value.strip():
                            parts.append(value.strip())
                            break
            script = "\n\n".join(parts)
    if not script:
        raise LLMError(f"Senaryoda anlatim metni yok (anahtarlar: {list(data)})")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", script) if p.strip()]
    terms = _as_list(data.get("video_terms") or data.get("videoTerms"))
    if not terms:
        words = [w for w in re.findall(r"[\w']+", script, flags=re.UNICODE) if len(w) > 4]
        terms = list(dict.fromkeys(w.lower() for w in words))[:8]
    return {
        "title": str(data.get("title") or "").strip(),
        "script": "\n\n".join(paragraphs),
        "paragraphs": paragraphs,
        "video_terms": terms[:12],
        "description": str(data.get("description") or "").strip(),
        "tags": _as_list(data.get("tags"))[:20],
        "hashtags": [h.lstrip("#") for h in _as_list(data.get("hashtags"))][:12],
    }


def generate_script(
    topic: str,
    lang: str = "tr",
    duration: int = 45,
    aspect: str = "9:16",
    style: str = "",
    api_key: str = "",
) -> dict[str, Any]:
    """Konudan MoneyPrinterTurbo tarzi video senaryosu uretir (JSON)."""
    lang_name = LANG_NAMES.get(lang, lang)
    target_words = max(40, int(duration * 2.4))
    style_line = f"Ton: {style}." if style else "Ton: akici ve merak uyandirici."
    system = "Profesyonel video senaristisin. Sadece gecerli JSON uydurursun, baska metin yazmazsin."
    prompt = (
        f"Konu: {topic}\n"
        f"Dil: {lang_name} | Format: {aspect} | Sure: ~{duration} sn (~{target_words} kelime)\n"
        f"{style_line}\n"
        "Ilk 3 saniyede dikkat ceken hook ile basla. SADECE JSON dondur:\n"
        '{"title":"...", "script":"paragraflari iki satir boslukla ayir", '
        '"video_terms":["ingilizce stok goruntu kelimesi"], '
        '"description":"...", "tags":["..."], "hashtags":["..."]}\n'
        "video_terms 6-10 adet Ingilizce stok goruntu arama kelimesi olsun."
    )
    last_err: LLMError | None = None
    for attempt in range(10):
        attempt_prompt = prompt if attempt == 0 else f"{prompt}\nTalep: {uuid.uuid4().hex[:8]}"
        try:
            raw = chat(attempt_prompt, system=system, api_key=api_key, retries=0)
            return _normalize(_extract_json(raw))
        except LLMError as exc:
            last_err = exc
            time.sleep(3 + attempt * 2)
    raise last_err or LLMError("senaryo uretilemedi")
