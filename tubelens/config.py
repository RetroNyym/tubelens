"""Yollar, basliklar ve sabitler."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
STORE_PATH = DATA_DIR / "store.json"
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "product_catalog.json"

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
