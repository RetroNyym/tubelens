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
)
TEXT_ENDPOINT = "https://text.pollinations.ai/"
HF_ROUTER = "https://router.huggingface.co/v1/chat/completions"
HF_MODEL = "openai/gpt-oss-120b"

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


def _nested_content(text: str) -> str:
    """'{"role":...,"content":"..."}' gibi nesne metinlerinden content'i cikarir."""
    try:
        data = json.loads(text)
    except ValueError:
        return ""
    if isinstance(data, dict):
        inner = data.get("content")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            inner = msg.get("content")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


def chat(
    prompt: str,
    system: str | None = None,
    model: str = "openai-fast",
    temperature: float = 0.9,
    timeout: int = 90,
    retries: int = 2,
    api_key: str = "",
    max_tokens: int = 1600,
    hf_token: str = "",
) -> str:
    """Tek seferlik sohbet; OpenAI-uyumlu uc noktayi deneyip duz metin yedegine duser."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # GPT-OSS reasoning modunda uzun dusunme alani content'i sikiyor ve
        # yanit bos kalabiliyor; low ile reasoning kisalir, content'e yer acilir.
        "reasoning_effort": "low",
    }
    headers = dict(HEADERS)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Hugging Face Router: token varsa once ucretsiz krediden dene;
    # basarisizsa Pollinations'a sessizce dusulur.
    if hf_token:
        try:
            resp = requests.post(
                HF_ROUTER,
                json={
                    "model": HF_MODEL,
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
                headers={**HEADERS, "Authorization": f"Bearer {hf_token}"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                content = ""
                try:
                    content = resp.json()["choices"][0]["message"]["content"]
                except (ValueError, KeyError, IndexError):
                    content = ""
                if content and content.strip():
                    return content.strip()
        except requests.RequestException:
            pass

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
                if resp.status_code == 429:
                    # Pollinations anonim: IP basina 1 isteklik kuyruk var.
                    # Kuyruk bosalsin diye uzun bekle, diger uclari de dene.
                    last_err = LLMError("kuyruk dolu (429)")
                    time.sleep(8)
                    continue
                last_err = LLMError(f"HTTP {resp.status_code} -> {url}")
                continue
            try:
                d = resp.json()
                content = d["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                last_err = exc
                continue
            content = str(content).strip() if content else ""
            if not content:
                reasoning = ""
                try:
                    reasoning = str(d["choices"][0]["message"].get("reasoning") or "")
                except (KeyError, IndexError, TypeError):
                    pass
                last_err = LLMError(
                    "bos yanit geldi"
                    + (f" (reasoning {len(reasoning)} karakter doldu)" if reasoning else "")
                )
                continue
            if content.startswith('{"role"'):
                # model nesne dondurdu: icinde gercek content olabilir
                inner = _nested_content(content)
                if inner:
                    return inner
                last_err = LLMError("model mesaj nesnesi dondurdu (bos icerik)")
                continue
            return content
        try:
            resp = requests.post(TEXT_ENDPOINT, json=payload, headers=headers, timeout=timeout)
            text = resp.text.strip()
            if resp.status_code == 429:
                last_err = LLMError("kuyruk dolu (429)")
                time.sleep(8)
            elif resp.status_code == 200 and text:
                if text.startswith('{"role"'):
                    inner = _nested_content(text)
                    if inner:
                        return inner
                    last_err = LLMError("duz metin: bos icerikli mesaj nesnesi")
                elif text.lstrip().startswith("{"):
                    return text  # duz metin JSON senaryo -> extract edilir
                else:
                    last_err = LLMError(f"duz metin JSON degil (HTTP 200, {len(text)} karakter)")
            else:
                last_err = LLMError(f"duz metin HTTP {resp.status_code}")
        except requests.RequestException as exc:
            last_err = exc
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    raise LLMError(f"LLM istekleri basarisiz: {last_err}")


def _strip_trailing_commas(text: str) -> str:
    """String disinde kalan ve kapanis isaretinden onceki virgulleri siler."""
    out: list[str] = []
    in_str, esc = False, False
    i = 0
    while i < len(text):
        ch = text[i]
        if esc:
            esc = False
            out.append(ch)
        elif ch == "\\":
            esc = True
            out.append(ch)
        elif ch == '"':
            in_str = not in_str
            out.append(ch)
        elif ch == "," and not in_str:
            j = i + 1
            while j < len(text) and text[j] in " \t\r\n":
                j += 1
            if j >= len(text) or text[j] in "}]":
                i += 1  # virgulu birakma
                continue
            out.append(ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _repair_json(text: str) -> dict[str, Any] | None:
    """Kesik JSON'u (token sinirinda kesilmis yanit) kapatmayi dener.

    Acik string'i ve container'lari kapatir, sondaki virgulleri temizler.
    Kurtulamazsa None dondurur.
    """
    candidate = text.strip()
    for _ in range(3):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
            return None
        except json.JSONDecodeError:
            pass
        # 1) acikta kalan string'i kapat
        in_str, esc = False, False
        for ch in candidate:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
        if in_str:
            candidate += '"'
        # 2) acik { [ ] } dengesini tamamla
        stack: list[str] = []
        in_str, esc = False, False
        for ch in candidate:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in "}]":
                if stack and stack[-1] == ch:
                    stack.pop()
        if not in_str:
            candidate = _strip_trailing_commas(candidate)
            candidate += "".join(reversed(stack))
    try:
        data = json.loads(candidate)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        repaired = _repair_json(text)
        if repaired is not None:
            return repaired
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


_JSON_SCHEMA = (
    '{"title":"...", "script":"paragraflari iki satir boslukla ayir", '
    '"video_terms":["ingilizce stok goruntu kelimesi"], '
    '"description":"...", "tags":["..."], "hashtags":["..."]}\n'
    "video_terms 6-10 adet Ingilizce stok goruntu arama kelimesi olsun."
)


def _request_script(
    prompt: str,
    system: str,
    target_words: int,
    api_key: str = "",
    hf_token: str = "",
) -> dict[str, Any]:
    """Prompt ile senaryo JSON'u iste; kesik yanit / 429 icin token butceli retry."""
    # Yanit sinirinda kesilmesin: hedef kelimeye gore token butcesi ver.
    # Not: reasoning_effort=low ile dusunme alani kisalir; butce content icin
    # alan acar. Servis ~4000'e kadar kabul ediyor (1600 ustu gectigimizde
    # HTTP hatasi idi; simdi low effort ile zaten oturuyor).
    token_budget = min(2400, target_words * 8 + 600)
    last_err: LLMError | None = None
    for attempt in range(10):
        attempt_prompt = prompt if attempt == 0 else f"{prompt}\nTalep: {uuid.uuid4().hex[:8]}"
        try:
            raw = chat(
                attempt_prompt,
                system=system,
                api_key=api_key,
                retries=0,
                max_tokens=token_budget,
                model="openai-fast",
                hf_token=hf_token,
            )
            return _normalize(_extract_json(raw))
        except LLMError as exc:
            last_err = exc
            time.sleep(3 + attempt * 2)
    raise last_err or LLMError("senaryo uretilemedi")


def generate_script(
    topic: str,
    lang: str = "tr",
    duration: int = 45,
    aspect: str = "9:16",
    style: str = "",
    api_key: str = "",
    hf_token: str = "",
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
        + _JSON_SCHEMA
    )
    return _request_script(prompt, system, target_words, api_key, hf_token=hf_token)


def clone_script(
    source: dict[str, Any],
    aspect: str = "9:16",
    duration: int = 45,
    lang: str = "tr",
    api_key: str = "",
    hf_token: str = "",
) -> dict[str, Any]:
    """Kaynak videonun YAPISINI ogrenip ayni yapiyla ozgun senaryo uretir.

    Kaynak: {title, description, transcript, views}
    Cikti: generate_script ile ayni JSON semasi.
    """
    title = str(source.get("title") or "").strip()
    description = str(source.get("description") or "")[:1200]
    transcript = str(source.get("transcript") or "")[:4000]
    views = int(source.get("views") or 0)
    lang_name = LANG_NAMES.get(lang, lang)
    target_words = max(40, int(duration * 2.4))
    system = (
        "Profesyonel video senaristisin. Sadece gecerli JSON uydurursun, baska metin yazmazsin."
    )
    prompt = (
        "Asagidaki basari videosunun YAPISINI analiz et (hook, akis, tempo, kapanis) ve "
        "AYNI YAPIYI kullanarak YENI, OZGUN bir senaryo uret.\n"
        "KURALLAR:\n"
        "- Birebir kopya YASAK: en az %30 farkli aci, ornek ve cumle kur.\n"
        "- Kaynak metinden sozdizimi veya tek cumle kopyalama.\n"
        f"- Dil: {lang_name} | Format: {aspect} | Sure: ~{duration} sn (~{target_words} kelime)\n\n"
        f"KAYNAK BASLIK: {title}\n"
        f"KAYNAK IZLENME: {views}\n"
        f"KAYNAK ACIKLAMA:\n{description or '(yok)'}\n\n"
        f"KAYNAK TRANSCRIPT:\n{transcript or '(transcript yok - basliga ve aciklamaya gore yorum yap)'}\n\n"
        "SADECE JSON dondur:\n" + _JSON_SCHEMA
    )
    return _request_script(prompt, system, target_words, api_key, hf_token=hf_token)
