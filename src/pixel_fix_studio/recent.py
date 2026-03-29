from __future__ import annotations

import json
import os
from pathlib import Path

from .models import RecentProjectItem

PIXEL_FIX_APP_DIR_NAME = "pixel-fix"
PIXEL_FIX_SETTINGS_FILE = "settings.json"
THUMBNAIL_SUFFIXES = {".png", ".bmp", ".gif", ".webp", ".jpg", ".jpeg"}


def pixel_fix_settings_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / PIXEL_FIX_APP_DIR_NAME / PIXEL_FIX_SETTINGS_FILE
    return Path.home() / f".{PIXEL_FIX_APP_DIR_NAME}" / PIXEL_FIX_SETTINGS_FILE


def load_recent_project_items() -> list[RecentProjectItem]:
    path = pixel_fix_settings_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get("recent_files")
    if not isinstance(raw, list):
        return []
    items: list[RecentProjectItem] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, str) or not entry.strip():
            continue
        candidate = Path(entry)
        normalized = str(candidate).lower()
        if normalized in seen or not candidate.exists() or not candidate.is_file():
            continue
        seen.add(normalized)
        items.append(
            RecentProjectItem(
                path=candidate.resolve(),
                name=candidate.name,
                detail=str(candidate.resolve()),
                thumbnail_supported=candidate.suffix.lower() in THUMBNAIL_SUFFIXES,
            )
        )
    return items
