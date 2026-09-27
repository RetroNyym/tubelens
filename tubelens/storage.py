"""JSON tabanli yerel veri deposu (kurulum gerektirmez)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import STORE_PATH, ensure_dirs

EMPTY = {
    "videos": {},
    "ai_checks": [],
    "runs": [],
    "updated_at": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> dict[str, Any]:
    ensure_dirs()
    if STORE_PATH.exists():
        try:
            data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    store = {**EMPTY, **data}
    store.setdefault("videos", {})
    store.setdefault("ai_checks", [])
    store.setdefault("runs", [])
    return store


def save(store: dict[str, Any]) -> None:
    ensure_dirs()
    store["updated_at"] = _now()
    tmp = STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE_PATH)


def upsert_video(store: dict[str, Any], video: dict[str, Any]) -> None:
    vid = video.get("id")
    if not vid:
        return
    video["updated_at"] = _now()
    store["videos"][vid] = video


def add_ai_check(store: dict[str, Any], check: dict[str, Any]) -> None:
    check["ts"] = _now()
    store["ai_checks"].append(check)
    # son 500 kontrolu sakla
    if len(store["ai_checks"]) > 500:
        store["ai_checks"] = store["ai_checks"][-500:]


def add_run(store: dict[str, Any], run: dict[str, Any]) -> None:
    run["ts"] = _now()
    store["runs"].append(run)
    if len(store["runs"]) > 100:
        store["runs"] = store["runs"][-100:]
