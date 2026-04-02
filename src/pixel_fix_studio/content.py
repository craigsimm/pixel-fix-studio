from __future__ import annotations

from dataclasses import dataclass

DEFAULT_STATUS = "Pixel-Fix Studio ready."
DEFAULT_STATUS_DETAIL = "Select a section from the left."


@dataclass(frozen=True)
class SidebarItemSpec:
    key: str
    label: str
    icon_kind: str
    accent_key: str
    description: str


@dataclass(frozen=True)
class LauncherCardSpec:
    key: str
    title: str
    accent_key: str
    icon_kind: str
    icon_asset_name: str | None
    launch_status: str


SIDEBAR_PRIMARY_ITEMS = (
    SidebarItemSpec(
        key="projects",
        label="Projects",
        icon_kind="folder",
        accent_key="cyan",
        description="Browse recent files and launcher shortcuts.",
    ),
    SidebarItemSpec(
        key="palettes",
        label="Palettes",
        icon_kind="palette",
        accent_key="cyan",
        description="Browse and organize Pixel-Fix 2D palettes.",
    ),
    SidebarItemSpec(
        key="textures",
        label="Textures",
        icon_kind="brick",
        accent_key="cyan",
        description="Browse and organize Pixel-Fix 3D textures.",
    ),
)

SIDEBAR_SECONDARY_ITEMS = (
    SidebarItemSpec(
        key="settings",
        label="Settings",
        icon_kind="gear",
        accent_key="cyan",
        description="Configure the Pixel-Fix 2D and Pixel-Fix 3D directories.",
    ),
    SidebarItemSpec(
        key="docs",
        label="Docs",
        icon_kind="question",
        accent_key="cyan",
        description="Documentation shortcuts are still placeholders.",
    ),
)

LAUNCHER_CARDS = (
    LauncherCardSpec(
        key="pixel_fix_2d",
        title="PIXEL-FIX 2D",
        accent_key="cyan",
        icon_kind="sprite",
        icon_asset_name="pixel-fix-2D-64px.png",
        launch_status="Pixel-Fix 2D launch remains unwired from the main launcher card.",
    ),
    LauncherCardSpec(
        key="pixel_fix_3d",
        title="PIXEL-FIX 3D",
        accent_key="cyan",
        icon_kind="voxel",
        icon_asset_name="pixel-fix-3D-64px.png",
        launch_status="Pixel-Fix 3D launch remains unwired from the main launcher card.",
    ),
)
