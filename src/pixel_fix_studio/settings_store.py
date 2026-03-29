from __future__ import annotations

import json
import os
from pathlib import Path

from .launcher_apps import detect_default_install_dirs as detect_known_install_dirs, validate_install_dir
from .models import LauncherSettings

APP_DIR_NAME = "pixel-fix-studio"
SETTINGS_FILE_NAME = "settings.json"


def get_app_storage_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME}"


def ensure_storage_dir() -> Path:
    path = get_app_storage_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def launcher_settings_path() -> Path:
    return get_app_storage_dir() / SETTINGS_FILE_NAME


def load_launcher_settings() -> LauncherSettings:
    path = launcher_settings_path()
    if not path.exists():
        return LauncherSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LauncherSettings()
    return LauncherSettings(
        pixel_fix_2d_install_dir=_coerce_str(data.get("pixel_fix_2d_install_dir") or data.get("pixel_fix_2d_dir")),
        pixel_fix_3d_install_dir=_coerce_str(data.get("pixel_fix_3d_install_dir") or data.get("pixel_fix_3d_dir")),
    )


def save_launcher_settings(settings: LauncherSettings) -> None:
    ensure_storage_dir()
    launcher_settings_path().write_text(
        json.dumps(settings.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def detect_default_install_dirs(project_root: Path) -> LauncherSettings:
    return detect_known_install_dirs(project_root)


def resolve_initial_settings(project_root: Path, saved: LauncherSettings) -> LauncherSettings:
    valid_two_d, _ = validate_pixel_fix_2d_install_dir(saved.pixel_fix_2d_install_dir)
    valid_three_d, _ = validate_pixel_fix_3d_install_dir(saved.pixel_fix_3d_install_dir)
    return LauncherSettings(
        pixel_fix_2d_install_dir=str(valid_two_d) if valid_two_d is not None else "",
        pixel_fix_3d_install_dir=str(valid_three_d) if valid_three_d is not None else "",
    )


def validate_pixel_fix_2d_install_dir(path_value: str | Path | None) -> tuple[Path | None, str]:
    installation = validate_install_dir(path_value, "pixel_fix_2d")
    return installation.install_root, installation.detail


def validate_pixel_fix_3d_install_dir(path_value: str | Path | None) -> tuple[Path | None, str]:
    installation = validate_install_dir(path_value, "pixel_fix_3d")
    return installation.install_root, installation.detail


def preferred_repo_python(repo_dir: Path) -> Path | None:
    python_path = repo_dir / ".venv" / "Scripts" / "python.exe"
    if python_path.exists() and python_path.is_file():
        return python_path.resolve()
    return None


def _coerce_str(value: object) -> str:
    return value if isinstance(value, str) else ""
