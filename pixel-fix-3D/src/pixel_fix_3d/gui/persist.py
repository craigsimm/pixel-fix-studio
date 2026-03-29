from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

APP_DIR_NAME = "pixel-fix-studio-3d"
SETTINGS_FILE_NAME = "settings.json"


@dataclass(frozen=True)
class AppPreferences:
    show_floor_grid: bool = True
    show_face_highlight: bool = True
    lighting_intensity: float = 1.0
    autorotate_speed: float = 1.0
    background_enabled: bool = False
    background_image_path: str = ""


def get_app_storage_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME}"


def ensure_storage_dir() -> Path:
    path = get_app_storage_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return get_app_storage_dir() / SETTINGS_FILE_NAME


def load_app_state() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_app_preferences(data: Mapping[str, Any] | None = None) -> AppPreferences:
    raw = data.get("preferences") if isinstance(data, Mapping) else None
    if not isinstance(raw, Mapping):
        raw = {}
    return AppPreferences(
        show_floor_grid=_read_bool(raw, "show_floor_grid", True),
        show_face_highlight=_read_bool(raw, "show_face_highlight", True),
        lighting_intensity=_read_float(raw, "lighting_intensity", 1.0),
        autorotate_speed=_read_float(raw, "autorotate_speed", 1.0),
        background_enabled=_read_bool(raw, "background_enabled", False),
        background_image_path=_read_str(raw, "background_image_path", ""),
    )


def app_preferences_to_dict(preferences: AppPreferences) -> dict[str, Any]:
    return {
        "show_floor_grid": preferences.show_floor_grid,
        "show_face_highlight": preferences.show_face_highlight,
        "lighting_intensity": preferences.lighting_intensity,
        "autorotate_speed": preferences.autorotate_speed,
        "background_enabled": preferences.background_enabled,
        "background_image_path": preferences.background_image_path,
    }


def save_app_state(data: dict[str, Any]) -> None:
    ensure_storage_dir()
    settings_path().write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _read_bool(data: Mapping[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    return value if isinstance(value, bool) else default


def _read_str(data: Mapping[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    return value if isinstance(value, str) else default


def _read_float(data: Mapping[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    if isinstance(value, (int, float)):
        return float(value)
    return default
