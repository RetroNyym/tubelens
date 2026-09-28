"""Seslendirme motorlari.

Anahtarsiz : edge (varsayilan, kelime bazli zamanlama), gtts
Keyli      : openai (gpt-4o-mini-tts), elevenlabs (karakter bazli gercek zamanlama)
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from pathlib import Path

import requests

ENGINES = ("edge", "gtts", "openai", "elevenlabs")

DEFAULT_VOICES = {
    "tr": "tr-TR-ahmetNeural",
    "en": "en-US-ChristopherNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "es": "es-ES-ElviraNeural",
    "ar": "ar-SA-HamedNeural",
    "ru": "ru-RU-DmitryNeural",
}

GTTS_LANGS = {"tr": "tr", "en": "en", "de": "de", "fr": "fr", "es": "es", "ar": "ar", "ru": "ru"}

OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini-tts"
OPENAI_DEFAULT_VOICE = "alloy"

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps"
ELEVEN_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel (cok dilli)
ELEVEN_MODEL = "eleven_multilingual_v2"


class VoiceError(RuntimeError):
    pass


@dataclass
class Word:
    text: str
    start: float
    end: float


def default_voice(lang: str) -> str:
    return DEFAULT_VOICES.get(lang, DEFAULT_VOICES["en"])


async def _synthesize_async(
    text: str,
    out_path: Path,
    voice: str,
    rate: str,
    volume: str,
) -> list[Word]:
    import edge_tts

    comm = edge_tts.Communicate(
        text, voice, rate=rate, volume=volume, boundary="WordBoundary"
    )
    words: list[Word] = []
    with out_path.open("wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = float(chunk["offset"]) / 1e7
                end = start + float(chunk["duration"]) / 1e7
                words.append(Word(str(chunk["text"]).strip(), start, end))
    if out_path.stat().st_size < 1000:
        raise VoiceError("Ses dosyasi uretilmedi (Edge TTS servisine erisilememis olabilir)")
    return words


def _duration(path: Path) -> float:
    try:
        from mutagen.mp3 import MP3

        return float(MP3(str(path)).info.length)
    except Exception:  # noqa: BLE001
        return 0.0


def _estimate_words(text: str, duration: float) -> list[Word]:
    """Motor zamanlama vermiyorsa kelime uzunluklarina gore orantili tahmin."""
    tokens = text.split()
    if not tokens or duration <= 0:
        return []
    weights = [len(t) + 1 for t in tokens]
    total = float(sum(weights))
    words: list[Word] = []
    clock = 0.0
    for tok, w in zip(tokens, weights):
        span = duration * (w / total)
        words.append(Word(tok, round(clock, 3), round(clock + span, 3)))
        clock += span
    return words


def _gtts(text: str, out_path: Path, lang: str) -> list[Word]:
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise VoiceError("gTTS kurulu degil: pip install gTTS") from exc
    try:
        gTTS(text=text, lang=GTTS_LANGS.get(lang, "en"), slow=False).save(str(out_path))
    except Exception as exc:  # noqa: BLE001
        raise VoiceError(f"gTTS hatasi: {exc}") from exc
    if not out_path.exists() or out_path.stat().st_size < 1000:
        raise VoiceError("gTTS ses dosyasi uretilmedi")
    return _estimate_words(text, _duration(out_path))


def _openai(text: str, out_path: Path, voice: str | None, api_key: str, model: str) -> list[Word]:
    if not api_key:
        raise VoiceError(
            "OpenAI TTS icin anahtar gerekli: --openai-key veya panelde OpenAI anahtari"
        )
    body = {
        "model": model or OPENAI_DEFAULT_MODEL,
        "voice": voice or OPENAI_DEFAULT_VOICE,
        "input": text,
        "response_format": "mp3",
    }
    try:
        resp = requests.post(
            OPENAI_TTS_URL,
            json=body,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
    except requests.RequestException as exc:
        raise VoiceError(f"OpenAI TTS istegi hatasi: {exc}") from exc
    if resp.status_code in (401, 403):
        raise VoiceError("OpenAI anahtari gecersiz (401/403)")
    if resp.status_code == 429:
        raise VoiceError("OpenAI limit asimi (429); biraz bekleyin")
    if resp.status_code != 200:
        raise VoiceError(f"OpenAI TTS HTTP {resp.status_code}: {resp.text[:200]}")
    out_path.write_bytes(resp.content)
    if out_path.stat().st_size < 1000:
        raise VoiceError("OpenAI TTS bos yanit dondurdu")
    return _estimate_words(text, _duration(out_path))


def _elevenlabs(text: str, out_path: Path, voice_id: str | None, api_key: str) -> list[Word]:
    if not api_key:
        raise VoiceError(
            "ElevenLabs icin anahtar gerekli: --elevenlabs-key veya panelde ElevenLabs anahtari"
        )
    url = ELEVENLABS_URL.format(voice=voice_id or ELEVEN_DEFAULT_VOICE_ID)
    body = {"text": text, "model_id": ELEVEN_MODEL}
    try:
        resp = requests.post(
            url,
            json=body,
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            timeout=90,
        )
    except requests.RequestException as exc:
        raise VoiceError(f"ElevenLabs istegi hatasi: {exc}") from exc
    if resp.status_code in (401, 403):
        raise VoiceError("ElevenLabs anahtari gecersiz (401/403)")
    if resp.status_code == 429:
        raise VoiceError("ElevenLabs limit asimi (429); biraz bekleyin")
    if resp.status_code != 200:
        raise VoiceError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
        out_path.write_bytes(base64.b64decode(data.get("audio_base64") or ""))
        words = _alignment_words(text, data.get("alignment") or {})
    except (ValueError, KeyError) as exc:
        raise VoiceError(f"ElevenLabs yaniti ayrıştırılamadı: {exc}") from exc
    if not out_path.exists() or out_path.stat().st_size < 1000:
        raise VoiceError("ElevenLabs ses dosyasi uretilmedi")
    return words or _estimate_words(text, _duration(out_path))


def _alignment_words(text: str, alignment: dict) -> list[Word]:
    """ElevenLabs karakter zamanlarindan kelime zamanlarina cevirir."""
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not chars or len(chars) != len(starts) or len(starts) != len(ends):
        return []
    words: list[Word] = []
    offset = 0
    for token in text.split():
        idx = "".join(chars).find(token, offset)
        if idx < 0:
            return []
        words.append(Word(token, float(starts[idx]), float(ends[idx + len(token) - 1])))
        offset = idx + len(token)
    return words


def synthesize(
    text: str,
    out_path: Path,
    voice: str | None = None,
    *,
    engine: str = "edge",
    lang: str = "tr",
    rate: str = "+0%",
    volume: str = "+0%",
    openai_key: str = "",
    elevenlabs_key: str = "",
    model: str = "",
) -> list[Word]:
    """Metni secili motorla seslendirir; kelime zamanlamalarini (sn) dondurur."""
    if not text.strip():
        raise VoiceError("Seslendirilecek metin bos")
    engine = (engine or "edge").lower()
    if engine not in ENGINES:
        raise VoiceError(f"Bilinmeyen TTS motoru: {engine} (secenekler: {', '.join(ENGINES)})")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if engine == "edge":
        try:
            return asyncio.run(_synthesize_async(text, out_path, voice or default_voice(lang), rate, volume))
        except VoiceError:
            raise
        except Exception as exc:
            raise VoiceError(f"Edge TTS hatasi: {exc}") from exc
    if engine == "gtts":
        return _gtts(text, out_path, lang)
    if engine == "openai":
        return _openai(text, out_path, voice, openai_key, model)
    return _elevenlabs(text, out_path, voice, elevenlabs_key)
