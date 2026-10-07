"""Anahtarsiz web gorsel aramasi - Bing / Openverse / Wikimedia.

Verilen sorguyla alakali fotograflari bulur; footage modulu bunlari
Ken Burns ile klip'e cevirir. Hicbir API anahtari gerektirmez.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from urllib.parse import urlparse

import requests

from .config import HEADERS, REQUEST_TIMEOUT, USER_AGENT

BAD_EXT = (".svg", ".gif", ".webm", ".mp4", ".avi", ".mov", ".bmp", ".tif", ".tiff")
WATERMARK_HOSTS = (
    "dreamstime.",
    "shutterstock.",
    "alamy.",
    "123rf.",
    "istockphoto.",
    "gettyimages.",
    "depositphotos.",
    "bigstockphoto.",
    "canstockphoto.",
    "vecteezy.",
    "vectorstock.",
    "pond5.",
    "agefotostock.",
)


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip())[:160]


def _blocked(url: str) -> bool:
    low = url.lower()
    host = urlparse(low).netloc
    if any(bad in host for bad in WATERMARK_HOSTS):
        return True
    return low.split("?")[0].endswith(BAD_EXT)


def _bing(query: str) -> list[tuple[str, int, int]]:
    q = urllib.parse.quote(query)
    url = (
        "https://www.bing.com/images/async?q="
        + q
        + "&first=1&count=35&relp=35&mkt=en-US&adlt=off&mmasync=1"
    )
    headers = {
        **HEADERS,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.bing.com/images/search?q=" + q,
    }
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT * 2)
    resp.raise_for_status()
    text = resp.text
    found = re.findall(r'"murl":"(.*?)"', text)
    if not found:
        found = re.findall(r"murl&quot;:&quot;(.*?)&quot;", text)
    out: list[tuple[str, int, int]] = []
    for raw in found:
        u = raw.replace("\\u002f", "/").replace("\\/", "/")
        if u.startswith("http"):
            out.append((u, 0, 0))
    return out


def _openverse(query: str) -> list[tuple[str, int, int]]:
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
        {"q": query, "page_size": 20, "license_type": "all-cc", "mature": "false"}
    )
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    out: list[tuple[str, int, int]] = []
    for item in data.get("results") or []:
        u = item.get("url") or ""
        if u.startswith("http"):
            out.append((u, int(item.get("width") or 0), int(item.get("height") or 0)))
    return out


def _wikimedia(query: str) -> list[tuple[str, int, int]]:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": "filetype:bitmap " + query,
            "gsrnamespace": "6",
            "gsrlimit": "12",
            "prop": "imageinfo",
            "iiprop": "url|size",
            "iiurlwidth": "1280",
            "format": "json",
        }
    )
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    pages = ((resp.json().get("query") or {}).get("pages") or {})
    items = sorted(pages.values(), key=lambda p: p.get("index") or 999)
    out: list[tuple[str, int, int]] = []
    for page in items:
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        u = info.get("thumburl") or info.get("url")
        if u:
            out.append(
                (
                    u,
                    int(info.get("thumbwidth") or info.get("width") or 0),
                    int(info.get("thumbheight") or info.get("height") or 0),
                )
            )
    return out


SOURCES = (
    ("bing", _bing),
    ("openverse", _openverse),
    ("wikimedia", _wikimedia),
)


def search(
    query: str, min_width: int = 640, min_height: int = 360
) -> tuple[bytes, str, str] | None:
    """Sorguyla alakali fotograf indirir; (bayt, kaynak, url) veya None dondurur."""
    q = _clean_query(query)
    if not q:
        return None
    for name, fn in SOURCES:
        try:
            candidates = fn(q)
        except (requests.RequestException, ValueError):
            continue
        tried = 0
        for u, width, height in candidates:
            if _blocked(u):
                continue
            if width and width < min_width:
                continue
            if height and height < min_height:
                continue
            tried += 1
            if tried > 6:
                break
            try:
                resp = requests.get(u, headers=HEADERS, timeout=REQUEST_TIMEOUT * 2)
            except requests.RequestException:
                continue
            if resp.status_code != 200:
                continue
            data = resp.content
            if _looks_like_image(data) and 8_000 < len(data) < 6_000_000:
                return data, name, u
    return None


def _looks_like_image(data: bytes) -> bool:
    if not data:
        return False
    if data[:3] == b"\xff\xd8\xff":
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
