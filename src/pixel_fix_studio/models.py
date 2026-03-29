from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LauncherSettings:
    pixel_fix_2d_install_dir: str = ""
    pixel_fix_3d_install_dir: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "pixel_fix_2d_install_dir": self.pixel_fix_2d_install_dir,
            "pixel_fix_3d_install_dir": self.pixel_fix_3d_install_dir,
        }


@dataclass(frozen=True)
class RecentProjectItem:
    path: Path
    name: str
    detail: str
    thumbnail_supported: bool


@dataclass(frozen=True)
class LibraryFolderNode:
    path: Path
    key: str
    label: str
    parent_key: str | None


@dataclass(frozen=True)
class PaletteItem:
    path: Path
    name: str
    folder: Path
    colors: tuple[int, ...]
    error: str | None = None


@dataclass(frozen=True)
class TextureItem:
    path: Path
    name: str
    folder: Path
    size: tuple[int, int] | None
    error: str | None = None


@dataclass(frozen=True)
class AppInstallation:
    key: str
    display_name: str
    install_root: Path | None
    executable_path: Path | None
    manifest_path: Path | None
    data_root: Path | None
    mode: str | None
    installed: bool
    detail: str
    launch_detail: str
    missing_app_message: str
