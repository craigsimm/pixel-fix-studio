"""Cleanup utilities for downsampled and palette-mapped label grids."""

from .components import IslandCleanupResult, remove_small_islands, remove_small_islands_detailed
from .filters import (
    CLEANUP_DISPLAY_TO_VALUE,
    CLEANUP_MODE_AGGRESSIVE,
    CLEANUP_MODE_BALANCED,
    CLEANUP_MODE_CONSERVATIVE,
    CLEANUP_MODE_OFF,
    CLEANUP_MODES,
    CLEANUP_OPTIONS,
    CLEANUP_VALUE_TO_DISPLAY,
    CleanupPreset,
    CleanupResult,
    cleanup_post_palette,
    cleanup_post_palette_detailed,
    cleanup_pre_palette,
    cleanup_pre_palette_detailed,
    normalize_cleanup_mode,
)

__all__ = [
    "CLEANUP_DISPLAY_TO_VALUE",
    "CLEANUP_MODE_AGGRESSIVE",
    "CLEANUP_MODE_BALANCED",
    "CLEANUP_MODE_CONSERVATIVE",
    "CLEANUP_MODE_OFF",
    "CLEANUP_MODES",
    "CLEANUP_OPTIONS",
    "CLEANUP_VALUE_TO_DISPLAY",
    "CleanupPreset",
    "CleanupResult",
    "IslandCleanupResult",
    "cleanup_post_palette",
    "cleanup_post_palette_detailed",
    "cleanup_pre_palette",
    "cleanup_pre_palette_detailed",
    "normalize_cleanup_mode",
    "remove_small_islands",
    "remove_small_islands_detailed",
]
