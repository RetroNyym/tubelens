"""Edge TTS ile anahtarsiz seslendirme + kelime bazli zamanlamalar.

Microsoft Edge'in ucretsiz TTS servisi kullanilir; API anahtari gerekmez.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import edge_tts

DEFAULT_VOICES = {
    "tr": "tr-TR-ahmetNeural",
    "en": "en-US-ChristopherNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "es": "es-ES-ElviraNeural",
    "ar": "ar-SA-HamedNeural",
    "ru": "ru-RU-DmitryNeural",
}


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


def synthesize(
    text: str,
    out_path: Path,
    voice: str,
    rate: str = "+0%",
    volume: str = "+0%",
) -> list[Word]:
    """Metni seslendirir; kelime zamanlamalarini (saniye) dondurur."""
    if not text.strip():
        raise VoiceError("Seslendirilecek metin bos")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        words = asyncio.run(_synthesize_async(text, out_path, voice, rate, volume))
    except VoiceError:
        raise
    except Exception as exc:
        raise VoiceError(f"Edge TTS hatasi: {exc}") from exc
    return words
