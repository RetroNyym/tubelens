"""Yollar, basliklar ve sabitler."""

import json
import os
import sys
from pathlib import Path

# PyInstaller ile paketlendiginde (frozen) kaynak klasoru yazilabilir degildir;
# veri %LOCALAPPDATA%\TubeLens altina yazilir. Kaynak koddaysa reposu yanina.
if getattr(sys, "frozen", False):
    ROOT = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TubeLens"
else:
    ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
VIDEO_DIR = ROOT / "videos"
STORE_PATH = DATA_DIR / "store.json"
VIDEO_CONFIG_PATH = DATA_DIR / "video_config.json"
CATALOG_PATH = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / (
    "tubelens/data/product_catalog.json"
    if getattr(sys, "frozen", False)
    else "data/product_catalog.json"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
    "Referer": "https://www.youtube.com/",
}

REQUEST_TIMEOUT = 20
REQUEST_RETRIES = 2
POLITE_DELAY = 0.8  # istekler arasi bekleme (saniye)


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)


def load_video_config() -> dict:
    if VIDEO_CONFIG_PATH.exists():
        try:
            data = json.loads(VIDEO_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_video_config(cfg: dict) -> None:
    ensure_dirs()
    VIDEO_CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
