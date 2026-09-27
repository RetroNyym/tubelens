"""AI arama motorlarinda gorunurluk kontrolu.

Motorlar:
  - google   : Google sonuclari + AI Overview varligi
  - bing     : Bing Copilot/AI ozeti + sonuclar
  - ddg      : DuckDuckGo (HTML anonim) sonuclari
  - youtube  : YouTube ic arama siralamasi

Her motor icin: var mi (found), kacinci sırada (rank), AI ozetinde mi (in_ai).
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .config import HEADERS, POLITE_DELAY, REQUEST_TIMEOUT

_last_call = 0.0


class SearchError(RuntimeError):
    pass


def _polite() -> None:
    global _last_call
    wait = POLITE_DELAY - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def _fetch(url: str, params: dict | None = None) -> str:
    _polite()
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise SearchError(f"Ag hatasi: {exc}") from exc
    if resp.status_code != 200:
        raise SearchError(f"HTTP {resp.status_code} -> {url}")
    return resp.text


def _normalize(url: str) -> str:
    if url.startswith("/url?"):
        qs = parse_qs(urlparse(url).query)
        url = qs.get("q", [""])[0]
    parsed = urlparse(url if "//" in url else f"https://{url}")
    host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}".lower()


def _match_rank(items: list[dict[str, Any]], target_tokens: list[str]) -> int | None:
    """Hedef URL/ID parcalarina gore sirayi bulur (1 tabanli)."""
    if not target_tokens:
        return None
    for idx, item in enumerate(items, start=1):
        hay = str(item.get("url", "")).lower()
        for token in target_tokens:
            if token and token.lower() in hay:
                return idx
    return None


def _tokens_for(video: dict[str, Any]) -> list[str]:
    tokens = [video.get("id", ""), video.get("url", "")]
    channel_url = video.get("channel_url", "")
    if channel_url:
        tokens.append(channel_url)
    channel_id = video.get("channel_id", "")
    if channel_id:
        tokens.append(channel_id)
    return [t for t in tokens if t]


# ---------------------------------------------------------------- Google

def check_google(query: str, tokens: list[str]) -> dict[str, Any]:
    """Google organik sonuclar + AI Overview tespiti."""
    result: dict[str, Any] = {"engine": "google", "ok": False, "found": False, "rank": None, "in_ai": False, "error": None}
    try:
        html = _fetch(
            "https://www.google.com/search",
            params={"q": query, "hl": "tr", "num": 20, "filter": "0"},
        )
    except SearchError as exc:
        result["error"] = str(exc)
        return result

    low = html.lower()
    if "detected unusual traffic" in low or "unusual traffic" in low:
        result["error"] = "Google bot dogrulamasi (CAPTCHA) karsimiza cikti"
        return result
    if "enablejs" in low or "consent.google.com" in low:
        # Google bu oturumda sonuc vermiyor; 'bulunamadi' demek yanlis olur
        result["error"] = "Google bu oturumda JS/consent sayfasi dondurdu (sonuc yok sayildi)"
        return result

    soup = BeautifulSoup(html, "html.parser")
    links: list[dict[str, str]] = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if href.startswith("/url?") or href.startswith("http"):
            links.append({"url": href})
    # AI Overview kutusu
    ai_block = soup.select_one("#AI_overview, [data-ai-overview], div[jsname] div[aria-live]")
    html_lower = html.lower()
    ai_present = ("ai overview" in html_lower) or bool(
        re.search(r"data-sonic|ai-overview", html_lower)
    )

    rank = _match_rank(links, tokens)
    result.update(
        {
            "ok": True,
            "found": rank is not None,
            "rank": rank,
            "in_ai": bool(ai_present and rank is not None),
            "ai_present": ai_present,
            "total": len(links),
        }
    )
    if ai_block is not None and not ai_present:
        result["ai_present"] = True
    return result


# ---------------------------------------------------------------- Bing

def check_bing(query: str, tokens: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"engine": "bing", "ok": False, "found": False, "rank": None, "in_ai": False, "error": None}
    try:
        html = _fetch("https://www.bing.com/search", params={"q": query, "setlang": "tr", "count": 30})
    except SearchError as exc:
        result["error"] = str(exc)
        return result

    soup = BeautifulSoup(html, "html.parser")
    links: list[dict[str, str]] = []
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a[href]")
        if a:
            links.append({"url": a["href"]})
    if not links:
        # Bing bot tespiti yapinca alakasiz/decoy sonuc dondurur
        result["error"] = "Bing sonuc listesi dondurmedi (bot korumasi olabilir)"
        return result

    # yanit kutusu (AI / Copilot ozeti) - #b_pole icinde gelir
    answer = soup.select_one("#b_pole, #b_results .b_ans, .b_aiScore")
    answer_html = str(answer) if answer else ""
    rank = _match_rank(links, tokens)

    # alakasiz/decoy tespiti: sorgunun icerik kelimeleri ilk basliklarda gecmiyorsa
    # Bing bot korumasi alakasiz liste donduruyordur -> sonuc gectersiz sayilir
    query_words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 3][:4]
    titles = " ".join(
        (li.get_text(" ", strip=True).lower() for li in soup.select("li.b_algo h2")[:5])
    )
    relevant = any(w in titles for w in query_words) if query_words else True
    if not relevant:
        result["error"] = "Bing alakasiz/decoy sonuc dondurdu (bot korumasi)"
        return result

    result.update(
        {
            "ok": True,
            "found": rank is not None,
            "rank": rank,
            "in_ai": bool(answer_html)
            and any(t and t.lower() in answer_html.lower() for t in tokens),
            "ai_present": bool(answer_html),
            "total": len(links),
        }
    )
    return result


# ---------------------------------------------------------------- DuckDuckGo

def check_ddg(query: str, tokens: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"engine": "ddg", "ok": False, "found": False, "rank": None, "in_ai": False, "error": None}
    try:
        html = _fetch("https://html.duckduckgo.com/html/", params={"q": query})
    except SearchError as exc:
        result["error"] = str(exc)
        return result

    soup = BeautifulSoup(html, "html.parser")
    links: list[dict[str, str]] = []
    for a in soup.select("a.result__a[href]"):
        href = a["href"]
        # DDG yonlendirme linki: //duckduckgo.com/l/?uddg=<encoded>
        if "uddg=" in href:
            qs = parse_qs(urlparse(href).query)
            href = unquote(qs.get("uddg", [href])[0])
        links.append({"url": href})
    ai_block = soup.select_one(".result--ai, #zero_click_ai, .zci-text")
    rank = _match_rank(links, tokens)
    ai_html = str(ai_block) if ai_block else ""
    result.update(
        {
            "ok": True,
            "found": rank is not None,
            "rank": rank,
            "in_ai": bool(ai_html) and any(t and t.lower() in ai_html.lower() for t in tokens),
            "ai_present": bool(ai_html),
            "total": len(links),
        }
    )
    return result


# ---------------------------------------------------------------- YouTube

def check_youtube(query: str, video_id: str) -> dict[str, Any]:
    """YouTube ic arama + YouTube AI ozet gorunurlugu.

    in_ai_own  : videonun kendisi AI ozet uretiyor (genisletilebilir ozet kutusu)
    in_ai_text : videonun basligi AI ozet metninde geciyor
    """
    from .youtube import search_youtube

    result: dict[str, Any] = {
        "engine": "youtube", "ok": False, "found": False, "rank": None,
        "in_ai": False, "error": None,
    }
    try:
        results = search_youtube(query, limit=30)
    except Exception as exc:  # youtube.YouTubeError
        result["error"] = str(exc)
        return result

    rank = None
    in_ai_own = False
    in_ai_text = False
    for idx, item in enumerate(results, start=1):
        if item["id"] == video_id:
            rank = idx
            in_ai_own = bool(item.get("in_ai_own"))
            in_ai_text = bool(item.get("in_ai_text"))
            break

    ai_boxes = sum(1 for item in results if item.get("has_ai_summary"))
    result.update(
        {
            "ok": True,
            "found": rank is not None,
            "rank": rank,
            "in_ai": in_ai_own or in_ai_text,
            "in_ai_own": in_ai_own,
            "in_ai_text": in_ai_text,
            "ai_present": ai_boxes > 0,
            "ai_box_count": ai_boxes,
            "total": len(results),
        }
    )
    return result


def score_engine(engine: dict[str, Any]) -> float:
    """Motor bazli 0-100 skor."""
    if not engine.get("ok"):
        return 0.0
    if not engine.get("found"):
        return 15.0  # araniyor ama bulunamadi -> kismi gorunurluk sinyali
    rank = engine.get("rank") or 99
    base = max(30.0, 100.0 - (rank - 1) * 7.0)
    if engine.get("in_ai"):
        # AI ozetinde yer almak 2026'da en yuksek degerli sinyal
        base = min(100.0, base + 25.0)
    return round(base, 1)


def overall_score(engines: list[dict[str, Any]]) -> float:
    ok = [e for e in engines if e.get("ok")]
    if not ok:
        return 0.0
    weights = {"google": 0.35, "youtube": 0.30, "bing": 0.20, "ddg": 0.15}
    total_w = sum(weights.get(e["engine"], 0.1) for e in ok)
    if total_w == 0:
        return 0.0
    value = sum(score_engine(e) * weights.get(e["engine"], 0.1) for e in ok) / total_w
    return round(value, 1)


def run_checks(query: str, video: dict[str, Any]) -> dict[str, Any]:
    """Tum motorlarda tek anahtar kelime icin kontrol."""
    tokens = _tokens_for(video)
    engines = [
        check_google(query, tokens),
        check_youtube(query, video.get("id", "")),
        check_bing(query, tokens),
        check_ddg(query, tokens),
    ]
    return {
        "query": query,
        "video_id": video.get("id", ""),
        "engines": engines,
        "score": overall_score(engines),
    }
