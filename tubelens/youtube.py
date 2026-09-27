"""YouTube verisi toplayici - Data API anahtari gerektirmez.

watch sayfasi ve kanal sayfalari HTML'inden ytInitialPlayerResponse /
ytInitialData JSON'u parse edilir.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import quote, urlparse

import requests

from .config import HEADERS, POLITE_DELAY, REQUEST_RETRIES, REQUEST_TIMEOUT

_last_call = 0.0

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class YouTubeError(RuntimeError):
    pass


def _get(url: str, params: dict | None = None) -> str:
    """Politik gecikme + tekrar denemeli GET."""
    global _last_call
    for attempt in range(REQUEST_RETRIES + 1):
        wait = POLITE_DELAY - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            _last_call = time.time()
            if resp.status_code == 200:
                return resp.text
            if resp.status_code in (429, 503) and attempt < REQUEST_RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            raise YouTubeError(f"HTTP {resp.status_code} -> {url}")
        except requests.RequestException as exc:
            if attempt == REQUEST_RETRIES:
                raise YouTubeError(f"Ag hatasi: {exc}") from exc
            time.sleep(1.5 * (attempt + 1))
    raise YouTubeError("Istek basarisiz")


def _extract_json(html: str, marker: str) -> dict:
    """HTML icinde `marker = { ... }` bloğunu dengeli süslü parantez ile ayiklar."""
    idx = html.find(marker)
    if idx < 0:
        raise YouTubeError(f"{marker} bulunamadi (YouTube sayfa bicimini degistirmis olabilir)")
    start = html.find("{", idx)
    if start < 0:
        raise YouTubeError(f"{marker} icin JSON baslangici yok")
    depth = 0
    in_str = False
    escape = False
    for pos in range(start, len(html)):
        ch = html[pos]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = html[start : pos + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError as exc:
                    raise YouTubeError(f"JSON parse hatasi: {exc}") from exc
    raise YouTubeError(f"{marker} JSON'u kapatilamadi")


def extract_video_id(url_or_id: str) -> str:
    """Farkli YouTube URL bicimlerinden video ID cikarir."""
    value = url_or_id.strip()
    if VIDEO_ID_RE.match(value):
        return value
    parsed = urlparse(value if "//" in value else f"https://{value}")
    host = (parsed.netloc or "").lower().removeprefix("www.").removeprefix("m.")
    qs = parsed.query
    if "v" in dict(
        part.split("=", 1) for part in qs.split("&") if "=" in part
    ):
        vid = dict(part.split("=", 1) for part in qs.split("&") if "=" in part)["v"]
        if VIDEO_ID_RE.match(vid):
            return vid
    parts = [p for p in parsed.path.split("/") if p]
    if host in ("youtu.be",) and parts and VIDEO_ID_RE.match(parts[0]):
        return parts[0]
    if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v") and VIDEO_ID_RE.match(parts[1]):
        return parts[1]
    if parts and VIDEO_ID_RE.match(parts[-1]):
        return parts[-1]
    raise YouTubeError(f"Video ID cikarilamadi: {url_or_id}")


def _simple_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if "simpleText" in node:
            return node["simpleText"]
        if "runs" in node:
            return "".join(r.get("text", "") for r in node["runs"])
        for key in ("text", "content"):
            if key in node and isinstance(node[key], str):
                return node[key]
    return ""


def _walk(node: Any):
    """Icindeki tum dict'leri gezer."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def parse_number(text: str) -> int:
    """'1.234 izlenme' / '12K views' / '3,4 mn' -> int (tahmini)."""
    if not text:
        return 0
    cleaned = text.lower().replace("\xa0", " ")
    mult = 1
    for token, factor in (
        ("milyar", 1_000_000_000), ("mn", 1_000_000), ("m", 1_000_000),
        ("b", 1_000_000_000), ("k", 1_000),
    ):
        if token in cleaned:
            mult = factor
            break
    match = re.search(r"[\d]+([.,]\d+)?", cleaned.replace(" ", ""))
    if not match:
        return 0
    number = float(match.group(0).replace(",", "."))
    return int(number * mult)


def get_video(url_or_id: str) -> dict[str, Any]:
    """Video temel bilgisi + aciklama + baglantilar + shopping etiketleri."""
    vid = extract_video_id(url_or_id)
    html = _get(f"https://www.youtube.com/watch?v={vid}")

    try:
        player = _extract_json(html, "ytInitialPlayerResponse = ")
    except YouTubeError:
        # Bazi videolarda bu deyim bos; buyuk olasilikla HTML'de baska bicimdedir
        match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{)", html)
        if not match:
            raise YouTubeError("ytInitialPlayerResponse bulunamadi (video gizli/silinmis olabilir)")
        player = _extract_json(html[match.start() :], "ytInitialPlayerResponse = ")
    details = player.get("videoDetails", {})
    micro = player.get("microformat", {}).get("playerMicroformatRenderer", {})

    description = details.get("shortDescription", "") or ""
    links = sorted(set(re.findall(r"https?://[^\s\"'<>]+", description)))

    # Shopping etiketleri (YouTube Shopping) ytInitialData icinde
    shopping_tags: list[dict[str, str]] = []
    try:
        data = _extract_json(html, "var ytInitialData = ")
    except YouTubeError:
        data = {}
    for node in _walk(data):
        if "videoDescriptionProductListRenderer" in node:
            products = node["videoDescriptionProductListRenderer"].get("products", [])
            for prod in products:
                detail = prod.get("productDetails", {}) or {}
                title = _simple_text(detail.get("title")) or detail.get("title", "")
                url = detail.get("url") or detail.get("canonicalUrl", "")
                shopping_tags.append({"title": str(title), "url": str(url)})
        if "shoppingCartRenderer" in node:
            pass  # bilgi amacli, ayrri islenmiyor

    view_count = parse_number(details.get("viewCountText", "") or "")
    if not view_count:
        view_count = parse_number(micro.get("viewCount", "") or "")

    keywords = details.get("keywords", []) or []
    return {
        "id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": details.get("title", ""),
        "channel": details.get("author", ""),
        "channel_id": details.get("channelId", ""),
        "channel_url": micro.get("ownerProfileUrl", ""),
        "description": description,
        "description_len": len(description),
        "links": links,
        "shopping_tags": shopping_tags,
        "views": view_count,
        "length_seconds": int(details.get("lengthSeconds", 0) or 0),
        "published": micro.get("publishDate", "") or micro.get("uploadDate", ""),
        "category": micro.get("category", ""),
        "keywords": keywords,
        "family_safe": micro.get("familySafe", True),
    }


def _ai_summary_texts(vr: dict) -> list[str]:
    """Bir videoRenderer icine gomulu YouTube AI ozet metinlerini toplar."""
    texts: list[str] = []
    meta = vr.get("expandableMetadata", {})
    if not isinstance(meta, dict):
        return texts
    for node in _walk(meta):
        if "videoSummaryContentViewModel" in node:
            for para in node["videoSummaryContentViewModel"].get("paragraphs", []):
                for sub in _walk(para):
                    content = sub.get("content")
                    if isinstance(content, str) and content.strip():
                        texts.append(content)
    return texts


def search_youtube(query: str, limit: int = 30) -> list[dict]:
    """YouTube arama sonuclarini (sirali) ceker.

    Her sonuca iki AI sinyali eklenir:
      in_ai_own  : bu videonun kendisi YouTube AI ozeti uretiyor (expandableMetadata)
      in_ai_text : videonun basligi/kimligi baska bir videonun AI ozetinde geciyor
    """
    html = _get("https://www.youtube.com/results", params={"search_query": query, "hl": "tr", "gl": "TR"})
    data = _extract_json(html, "var ytInitialData = ")

    results: list[dict] = []
    seen: set[str] = set()
    all_summaries: list[str] = []
    for node in _walk(data):
        vr = node.get("videoRenderer")
        if not isinstance(vr, dict):
            continue
        vid = vr.get("videoId", "")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        summaries = _ai_summary_texts(vr)
        all_summaries.extend(summaries)
        results.append(
            {
                "id": vid,
                "title": _simple_text(vr.get("title")),
                "channel": _simple_text(vr.get("ownerText")),
                "views": _simple_text(vr.get("viewCountText")),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "has_ai_summary": bool(summaries),
            }
        )
        if len(results) >= limit:
            break

    # AI ozet metinlerinin tamamina karsi tum sonuclari tekrar degerlendir
    blob = " ".join(all_summaries).lower()
    for item in results:
        title = (item.get("title") or "").lower().strip()
        item["in_ai_text"] = bool(title and len(title) > 12 and title in blob)
        item["in_ai_own"] = item.get("has_ai_summary", False)
    return results


def get_channel_id(handle_or_url: str) -> str:
    """@handle veya kanal URL'inden channel ID (UC...) bulur.

    Once `<link rel="canonical">` / `channelMetadataRenderer.externalId`
    kullanilir; bunlar kanalin kendisine aittir. Duz `UC...` regex'i reklam ya
    da oneri kanalina ait bir ID yakalayabildigi icin son care olarak kalir.
    """
    value = handle_or_url.strip()
    if value.startswith("UC") and len(value) == 24:
        return value
    if not value.startswith("http"):
        value = f"https://www.youtube.com/{'@' + handle_or_url.lstrip('@')}"
    html = _get(value)

    match = re.search(r'<link rel="canonical" href="[^"]*/channel/(UC[\w-]{22})"', html)
    if match:
        return match.group(1)
    match = re.search(r'"externalId"\s*:\s*"(UC[\w-]{22})"', html)
    if match:
        return match.group(1)
    match = re.search(r'"channelMetadataRenderer"[\s\S]{0,400}?"channelId"\s*:\s*"(UC[\w-]{22})"', html)
    if match:
        return match.group(1)
    match = re.search(r'"channelId"\s*:\s*"(UC[\w-]{22})"', html)
    if match:
        return match.group(1)
    raise YouTubeError(f"Kanal ID bulunamadi: {handle_or_url}")


def _parse_views(label: str) -> str:
    """'4.1 million views' -> '4.1M' (kisa gosterim)."""
    match = re.search(r"([\d.,]+)\s*(billion|million|thousand|B|M|K|milyar|milyon|bin)", label, re.I)
    if not match:
        return ""
    number = match.group(1)
    suffix = match.group(2)[0].upper()
    return f"{number}{suffix}"


def _lockup_video(node: dict) -> dict[str, Any] | None:
    """Yeni kanal/arama arayuzundeki lockupViewModel'i video kaydina cevirir."""
    lm = node.get("lockupViewModel")
    if not isinstance(lm, dict):
        return None
    vid = lm.get("contentId", "") or ""
    if not VIDEO_ID_RE.match(vid):
        return None  # playlist / Shorts raf satiri vb.
    if lm.get("contentType") not in (None, "LOCKUP_CONTENT_TYPE_VIDEO"):
        return None

    title = ""
    views = ""
    published = ""
    meta = lm.get("metadata") or {}
    meta = meta.get("lockupMetadataViewModel", {}) if isinstance(meta, dict) else {}
    if isinstance(meta, dict):
        title = _simple_text(meta.get("title"))
        md = meta.get("metadata") or {}
        rows = md.get("contentMetadataViewModel", {}).get("metadataRows", []) if isinstance(md, dict) else []
        for row in rows:
            for part in row.get("metadataParts", []) or []:
                text = part.get("text") if isinstance(part, dict) else None
                label = _simple_text(text)
                a11y = part.get("accessibilityLabel", "") if isinstance(part, dict) else ""
                if re.search(r"g[öo]r[üu]nt[üu]leme|views", a11y or label, re.I):
                    views = label or _parse_views(a11y)
                elif re.search(r"ago|önce|once", a11y or label, re.I):
                    published = label
    if not title:
        # Thumbnail yedeği: /vi/<videoId>/... -> baslik yoksa id ile devam
        title = vid

    duration = ""
    image = lm.get("contentImage") or {}
    image = image.get("thumbnailViewModel", {}) if isinstance(image, dict) else {}
    overlays = image.get("overlays") if isinstance(image, dict) else None
    for overlay in overlays or []:
        bottom = overlay.get("thumbnailBottomOverlayViewModel", {})
        for badge in bottom.get("badges", []) or []:
            text = badge.get("thumbnailBadgeViewModel", {}).get("text", "")
            if re.match(r"^\d+:\d{2}(:\d{2})?$", text or ""):
                duration = text
    return {
        "id": vid,
        "title": title,
        "views": views,
        "views_raw": _parse_views(views),
        "published": published,
        "duration": duration,
        "url": f"https://www.youtube.com/watch?v={vid}",
    }


def get_channel_title(handle_or_url: str) -> str:
    """Kanalin gorunur adini (channelMetadataRenderer.title) ceker."""
    value = handle_or_url.strip()
    if not value.startswith("http"):
        value = f"https://www.youtube.com/{'@' + handle_or_url.lstrip('@')}"
    html = _get(value)
    match = re.search(r'"channelMetadataRenderer"\s*:\s*\{[\s\S]{0,400}?"title"\s*:\s*"([^"]+)"', html)
    if match:
        return match.group(1)
    match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if match:
        return match.group(1).removesuffix(" - YouTube")
    return ""


def get_channel_videos(handle_or_url: str, limit: int = 15) -> list[dict[str, Any]]:
    """Kanalin son videolarini (playlist sekmesi) ceker.

    YouTube artik kanal listelerini `videoRenderer` yerine `lockupViewModel`
    olarak sunuyor; iki bicim de desteklenir.
    """
    value = handle_or_url.strip()
    if not value.startswith("http"):
        value = f"https://www.youtube.com/{value if value.startswith('@') else '@' + value.lstrip('@')}"
    html = _get(value, params={"view": "0", "sort": "dd"})
    data = _extract_json(html, "var ytInitialData = ")
    videos: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _push(vid: str, title: str, views: str, extra: dict | None = None) -> None:
        if not vid or vid in seen:
            return
        seen.add(vid)
        item = {
            "id": vid,
            "title": title,
            "views": views,
            "url": f"https://www.youtube.com/watch?v={vid}",
        }
        if extra:
            item.update(extra)
        videos.append(item)

    for node in _walk(data):
        if len(videos) >= limit:
            break
        parsed = _lockup_video(node)
        if parsed:
            _push(parsed["id"], parsed["title"], parsed["views"], parsed)
            continue
        inner = node.get("videoRenderer")
        if isinstance(inner, dict):
            vid = inner.get("videoId", "")
            _push(vid, _simple_text(inner.get("title")), _simple_text(inner.get("viewCountText")))
    return videos[:limit]
