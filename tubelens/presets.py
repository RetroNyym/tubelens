"""Hazir gorsel/ton presetleri - LLM stil satirina ve AI gorsel prompt'una eklenir.

PRESETS degerleri senaryo (LLM) isteklerine, visual_suffix degerleri ise
gorsel modeli (FLUX/SD/Pollinations) isteklerine eklenir; gorsel modelleri
Ingilizce stil metniyle daha tutarli calisir.
"""

from __future__ import annotations

PRESETS: dict[str, str] = {
    "sinematik": "sinematik goruntu: genis aci, derinlik, film graini, dramatik isik",
    "anime": "anime tarzi, cesur cizgiler, parlak renkler",
    "2d": "2D cel animasyon, duz renkler, kalin kontur",
    "3d": "3D Pixar tarzi, yumusak isik, yuvarlak formlar",
    "minimal": "minimalist, temiz kompozisyon, bol bosluk, pastel tonlar",
    "belgesel": "belgesel tarzi, dogal isik, gercekci, sakin anlatim",
}

VISUAL: dict[str, str] = {
    "sinematik": (
        "cinematic still, wide angle, deep depth of field, film grain, dramatic lighting"
    ),
    "anime": "anime style, bold clean lineart, vivid colors",
    "2d": "2D cel animation, flat colors, thick outlines",
    "3d": "3D Pixar style render, soft lighting, rounded friendly shapes",
    "minimal": "minimalist composition, clean background, generous negative space, pastel tones",
    "belgesel": "documentary photograph, natural light, realistic, calm mood",
}

PRESET_CHOICES: list[str] = list(PRESETS)


def _key(preset: str) -> str:
    return str(preset or "").strip().lower()


def resolve(preset: str, extra_style: str = "") -> str:
    """Preset metni ile kullanici ek stilini birlestirir.

    Preset bos ya da bilinmiyorsa sadece extra_style doner; ek stil de bossa
    preset degeri yalniz doner.
    """
    base = PRESETS.get(_key(preset), "")
    extra = str(extra_style or "").strip()
    return ", ".join(part for part in (base, extra) if part)


def visual_suffix(preset: str) -> str:
    """AI gorsel modeli icin Ingilizce stil son eki (prompt sonuna eklenir)."""
    return VISUAL.get(_key(preset), "")
