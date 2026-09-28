"""Ortak test yardimcilari - tum testler OFFLINE calisir (ag istegi yok)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
