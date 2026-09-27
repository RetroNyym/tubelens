"""YouTube Shopping / affiliate baglanti analizi.

Bir videonun aciklamasindaki linkleri:
  - affiliate mi?
  - hangi programa ait?
  - eksik firsat var mi?  (or. inceleme videosu ama hic link yok)
  - disclosure (reklam/sponsor aciklamasi) var mi?
  - shopping etiketi (YouTube Shopping) ekilmis mi?

cikti: bulgular + gelir firsat skoru
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from .config import CATALOG_PATH

_DISCLOSURE_PATTERNS = [
    r"#\s*ad\b", r"#sponsored", r"reklam", r"sponsor(lu|luk|ed)", r"\baffiliate\b",
    r"ortaklik linki", r"link affiliation", r"ucretli isbirligi", r"isbirligi cercevesinde",
    r"komisyon aliyorum", r"komisyon kazaniyorum", r"paid partnership", r"#reklam",
    r"amazon associate", r"amazon ortagi",
]

_SPAMMY_PATTERNS = [r"bedava takipci", r"takipci satin al", r"kumar", r"bet\b", r"1xbet", r"bahis"]


def load_catalog() -> dict[str, Any]:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"programs": [], "topic_to_program": {}, "affiliate_url_patterns": []}


def _host(url: str) -> str:
    try:
        return urlparse(url if "//" in url else f"https://{url}").netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def detect_program(url: str, catalog: dict[str, Any]) -> str | None:
    low = url.lower()
    host = _host(url)
    for program in catalog.get("programs", []):
        for domain in program.get("domains", []):
            if domain.lower() in host or domain.lower() in low:
                return program["name"]
    for pattern in catalog.get("affiliate_url_patterns", []):
        if pattern.lower() in low:
            return "Tespit edilmis affiliate pattern"
    return None


def is_affiliate_link(url: str, catalog: dict[str, Any]) -> bool:
    return detect_program(url, catalog) is not None


def find_disclosures(description: str) -> list[str]:
    found = []
    low = description.lower()
    for pattern in _DISCLOSURE_PATTERNS:
        if re.search(pattern, low, re.IGNORECASE):
            found.append(pattern)
    return found


def find_spam(description: str) -> list[str]:
    return [p for p in _SPAMMY_PATTERNS if re.search(p, description, re.IGNORECASE)]


def guess_topics(video: dict[str, Any], catalog: dict[str, Any]) -> list[str]:
    """Baslik + aciklama + anahtar kelimelerden konu tespiti."""
    text = " ".join(
        [
            video.get("title", ""),
            video.get("description", "")[:1500],
            " ".join(video.get("keywords", []) or []),
        ]
    ).lower()
    topics = []
    for topic in catalog.get("topic_to_program", {}):
        if topic.lower() in text:
            topics.append(topic)
    return topics[:8]


def suggested_programs(topics: list[str], catalog: dict[str, Any]) -> list[str]:
    mapping = catalog.get("topic_to_program", {})
    programs: list[str] = []
    for topic in topics:
        for name in mapping.get(topic, []):
            if name not in programs:
                programs.append(name)
    return programs


def analyze(video: dict[str, Any]) -> dict[str, Any]:
    """Video icin affiliate/shopping bulgulari uretir."""
    catalog = load_catalog()
    description = video.get("description", "") or ""
    links = video.get("links", []) or []

    classified = []
    for url in links:
        program = detect_program(url, catalog)
        classified.append({"url": url, "host": _host(url), "program": program, "is_affiliate": bool(program)})

    affiliate_links = [c for c in classified if c["is_affiliate"]]
    external_links = [c for c in classified if not c["is_affiliate"]]
    disclosures = find_disclosures(description)
    spam = find_spam(description)
    topics = guess_topics(video, catalog)
    suggested = suggested_programs(topics, catalog)
    shopping_tags = video.get("shopping_tags", []) or []

    findings: list[str] = []
    misses: list[str] = []

    if not links:
        misses.append("Açıklamada hiç link yok - ziyaretçiyi dışarı taşıyacak hiyerarşi yok")
    if not affiliate_links:
        misses.append("Affiliate / ortaklık linki bulunamadı - gösterge bazlı kazanç kaçırılıyor")
    if topics and suggested and not affiliate_links:
        misses.append(
            f"Konu ({', '.join(topics[:3])}) ile uyumlu programlar öneriliyor: {', '.join(suggested[:3])}"
        )
    if topics and not shopping_tags:
        misses.append("YouTube Shopping etiketi yok - videoda ürün etiketleme yapılmamış")
    if len(description) < 300:
        misses.append("Açıklama çok kısa (300 karakter altı) - YouTube Shopping ve SEO için yetersiz")
    if not disclosures and affiliate_links:
        misses.append("Affiliate link var ama reklam/sponsor disclosure metni YOK - politika riski")
    if disclosures and affiliate_links:
        findings.append("Reklam disclosure + affiliate link birlikte mevcut (uyumlu)")
    if shopping_tags:
        findings.append(f"YouTube Shopping etiketi mevcut: {len(shopping_tags)} ürün")
    if affiliate_links:
        findings.append(f"{len(affiliate_links)} affiliate link tespit edildi")
    if spam:
        findings.append(f"Spam/yasaklı içerik sinyali: {', '.join(spam)} - dikkat")

    # gelir firsat skoru (0-100)
    score = 0
    score += 25 if links else 0
    score += 30 if affiliate_links else 0
    score += 15 if disclosures else 0
    score += 20 if shopping_tags else 0
    score += 10 if len(description) >= 300 else 0
    score = min(100, score)

    return {
        "video_id": video.get("id", ""),
        "title": video.get("title", ""),
        "views": video.get("views", 0),
        "link_count": len(links),
        "affiliate_links": affiliate_links,
        "external_links": external_links,
        "disclosures": disclosures,
        "spam_signals": spam,
        "topics": topics,
        "suggested_programs": suggested,
        "shopping_tags": shopping_tags,
        "findings": findings,
        "misses": misses,
        "opportunity_score": score,
    }


def channel_summary(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    """Kanal genelinde ozet metrikler."""
    if not analyses:
        return {"videos": 0, "avg_score": 0, "total_affiliate_links": 0, "videos_without_links": 0}
    total_links = sum(len(a["affiliate_links"]) for a in analyses)
    no_links = sum(1 for a in analyses if a["link_count"] == 0)
    avg = round(sum(a["opportunity_score"] for a in analyses) / len(analyses), 1)
    return {
        "videos": len(analyses),
        "avg_score": avg,
        "total_affiliate_links": total_links,
        "videos_without_links": no_links,
        "videos_missing_disclosure": sum(1 for a in analyses if a["affiliate_links"] and not a["disclosures"]),
        "videos_missing_shopping_tags": sum(1 for a in analyses if not a["shopping_tags"]),
    }
