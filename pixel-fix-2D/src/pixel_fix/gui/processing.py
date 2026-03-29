from __future__ import annotations

from collections import Counter
from dataclasses import replace
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter

import numpy as np
from PIL import Image, ImageDraw

from pixel_fix.palette.model import StructuredPalette
from pixel_fix.palette.color_modes import extract_unique_colors
from pixel_fix.palette.quantize import median_cut_palette, top_k_palette
from pixel_fix.palette.workspace import (
    ColorWorkspace,
    hyab_distance,
    linear_to_oklab,
    oklab_to_oklch,
    oklch_to_oklab,
    srgb_to_linear,
)
from pixel_fix.pipeline import (
    PipelineConfig,
    PipelinePreparedResult,
    PipelineProgressCallback,
    PixelFixPipeline,
)
from pixel_fix.types import LabelGrid

RGB = tuple[int, int, int]
RGBGrid = list[list[RGB]]
BRUSH_SHAPE_SQUARE = "square"
BRUSH_SHAPE_ROUND = "round"
BRUSH_WIDTH_DEFAULT = 1
BRUSH_WIDTH_MIN = 1
BRUSH_WIDTH_MAX = 64
IMAGE_FILTER_STRENGTH_DEFAULT = 1
IMAGE_FILTER_STRENGTH_MIN = 1
IMAGE_FILTER_STRENGTH_MAX = 3
OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK = "dark"
OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_BRIGHT = "bright"
OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT = 40
INDEXED_COLOR_PALETTE_LOCAL_PERCEPTUAL = "local-perceptual"
INDEXED_COLOR_PALETTE_LOCAL_SELECTIVE = "local-selective"
INDEXED_COLOR_PALETTE_LOCAL_ADAPTIVE = "local-adaptive"
INDEXED_COLOR_FORCED_NONE = "none"
INDEXED_COLOR_FORCED_BLACK_AND_WHITE = "black-and-white"
INDEXED_COLOR_FORCED_PRIMARIES = "primaries"
INDEXED_COLOR_DITHER_NONE = "none"
INDEXED_COLOR_DITHER_DIFFUSION = "diffusion"
INDEXED_COLOR_PALETTE_LABELS = {
    INDEXED_COLOR_PALETTE_LOCAL_PERCEPTUAL: "Local (Perceptual)",
    INDEXED_COLOR_PALETTE_LOCAL_SELECTIVE: "Local (Selective)",
    INDEXED_COLOR_PALETTE_LOCAL_ADAPTIVE: "Local (Adaptive)",
}
INDEXED_COLOR_FORCED_LABELS = {
    INDEXED_COLOR_FORCED_NONE: "None",
    INDEXED_COLOR_FORCED_BLACK_AND_WHITE: "Black and White",
    INDEXED_COLOR_FORCED_PRIMARIES: "Primaries",
}
INDEXED_COLOR_FORCED_PALETTES = {
    INDEXED_COLOR_FORCED_NONE: (),
    INDEXED_COLOR_FORCED_BLACK_AND_WHITE: (0x000000, 0xFFFFFF),
    INDEXED_COLOR_FORCED_PRIMARIES: (0xFF0000, 0x00FF00, 0x0000FF, 0x00FFFF, 0xFF00FF, 0xFFFF00),
}


def rgb_to_labels(grid: RGBGrid) -> LabelGrid:
    return [[(r << 16) | (g << 8) | b for (r, g, b) in row] for row in grid]


def labels_to_rgb(grid: LabelGrid) -> RGBGrid:
    return [[((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF) for value in row] for row in grid]


@dataclass(frozen=True)
class ProcessStats:
    stage: str
    pixel_width: int
    resize_method: str
    input_size: tuple[int, int]
    output_size: tuple[int, int]
    initial_color_count: int
    color_count: int
    elapsed_seconds: float
    seed_count: int = 0
    ramp_count: int = 0
    palette_strategy: str = "advanced"
    effective_palette_size: int = 0
    histogram_size: int = 0
    palette_generation_seconds: float = 0.0
    mapping_seconds: float = 0.0


@dataclass(frozen=True)
class ProcessResult:
    grid: RGBGrid
    width: int
    height: int
    stats: ProcessStats
    prepared_input: PipelinePreparedResult
    display_palette_labels: tuple[int, ...] = ()
    structured_palette: StructuredPalette | None = None
    alpha_mask: tuple[tuple[bool, ...], ...] | None = None


@dataclass(frozen=True)
class IndexedColorSettings:
    palette_method: str = INDEXED_COLOR_PALETTE_LOCAL_PERCEPTUAL
    colors: int = 32
    forced_palette: str = INDEXED_COLOR_FORCED_NONE
    dither_mode: str = INDEXED_COLOR_DITHER_NONE
    diffusion_amount: int = 100
    preview_enabled: bool = True


@dataclass(frozen=True)
class IndexedColorProcessResult:
    result: ProcessResult
    palette_labels: tuple[int, ...]
    source_label: str


CANVAS_RESIZE_ANCHOR_TOP_LEFT = "top-left"
CANVAS_RESIZE_ANCHOR_TOP = "top"
CANVAS_RESIZE_ANCHOR_TOP_RIGHT = "top-right"
CANVAS_RESIZE_ANCHOR_LEFT = "left"
CANVAS_RESIZE_ANCHOR_CENTER = "center"
CANVAS_RESIZE_ANCHOR_RIGHT = "right"
CANVAS_RESIZE_ANCHOR_BOTTOM_LEFT = "bottom-left"
CANVAS_RESIZE_ANCHOR_BOTTOM = "bottom"
CANVAS_RESIZE_ANCHOR_BOTTOM_RIGHT = "bottom-right"
CANVAS_RESIZE_ANCHORS = (
    CANVAS_RESIZE_ANCHOR_TOP_LEFT,
    CANVAS_RESIZE_ANCHOR_TOP,
    CANVAS_RESIZE_ANCHOR_TOP_RIGHT,
    CANVAS_RESIZE_ANCHOR_LEFT,
    CANVAS_RESIZE_ANCHOR_CENTER,
    CANVAS_RESIZE_ANCHOR_RIGHT,
    CANVAS_RESIZE_ANCHOR_BOTTOM_LEFT,
    CANVAS_RESIZE_ANCHOR_BOTTOM,
    CANVAS_RESIZE_ANCHOR_BOTTOM_RIGHT,
)


@dataclass(frozen=True)
class CanvasResizeSpec:
    width: int
    height: int
    anchor: str = CANVAS_RESIZE_ANCHOR_CENTER


def apply_transparency_fill(result: ProcessResult, x: int, y: int) -> tuple[ProcessResult, int]:
    if result.width <= 0 or result.height <= 0:
        return result, 0
    if x < 0 or y < 0 or x >= result.width or y >= result.height:
        return result, 0
    current_mask = result.alpha_mask
    if current_mask is not None and not current_mask[y][x]:
        return result, 0
    target = result.grid[y][x]
    next_mask = [list(row) for row in current_mask] if current_mask is not None else [[True] * result.width for _ in range(result.height)]
    pending = [(x, y)]
    changed = 0
    while pending:
        px, py = pending.pop()
        if px < 0 or py < 0 or px >= result.width or py >= result.height:
            continue
        if not next_mask[py][px]:
            continue
        if result.grid[py][px] != target:
            continue
        next_mask[py][px] = False
        changed += 1
        pending.append((px - 1, py))
        pending.append((px + 1, py))
        pending.append((px, py - 1))
        pending.append((px, py + 1))
    if changed == 0:
        return result, 0
    return replace(result, alpha_mask=tuple(tuple(row) for row in next_mask)), changed


def apply_bucket_fill(result: ProcessResult, x: int, y: int, label: int) -> tuple[ProcessResult, int]:
    if result.width <= 0 or result.height <= 0:
        return result, 0
    if x < 0 or y < 0 or x >= result.width or y >= result.height:
        return result, 0
    current_mask = result.alpha_mask
    seed_visible = True if current_mask is None else bool(current_mask[y][x])
    target_rgb = _label_to_rgb(label)
    seed_rgb = result.grid[y][x]
    pending = [(x, y)]
    visited: set[tuple[int, int]] = set()
    changed_points: set[tuple[int, int]] = set()
    next_grid = [list(row) for row in result.grid]
    next_mask = [list(row) for row in current_mask] if current_mask is not None else None
    while pending:
        point_x, point_y = pending.pop()
        if point_x < 0 or point_y < 0 or point_x >= result.width or point_y >= result.height:
            continue
        point = (point_x, point_y)
        if point in visited:
            continue
        visited.add(point)
        point_visible = True if current_mask is None else bool(current_mask[point_y][point_x])
        if point_visible != seed_visible:
            continue
        if seed_visible and result.grid[point_y][point_x] != seed_rgb:
            continue
        current_rgb = result.grid[point_y][point_x]
        if (not point_visible) or current_rgb != target_rgb:
            next_grid[point_y][point_x] = target_rgb
            changed_points.add(point)
        if next_mask is not None and not point_visible:
            next_mask[point_y][point_x] = True
            changed_points.add(point)
        pending.append((point_x - 1, point_y))
        pending.append((point_x + 1, point_y))
        pending.append((point_x, point_y - 1))
        pending.append((point_x, point_y + 1))
    if not changed_points:
        return result, 0
    if next_mask is not None:
        return replace(result, grid=next_grid, alpha_mask=_normalize_alpha_mask(next_mask)), len(changed_points)
    return replace(result, grid=next_grid), len(changed_points)


def apply_rectangle_operation(
    result: ProcessResult,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    outline_label: int,
    *,
    fill_label: int | None,
    width: int = BRUSH_WIDTH_DEFAULT,
) -> tuple[ProcessResult, int]:
    return _apply_shape_operation(
        result,
        "rectangle",
        x0,
        y0,
        x1,
        y1,
        outline_label=outline_label,
        fill_label=fill_label,
        width=width,
    )


def apply_ellipse_operation(
    result: ProcessResult,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    outline_label: int,
    *,
    fill_label: int | None,
    width: int = BRUSH_WIDTH_DEFAULT,
) -> tuple[ProcessResult, int]:
    return _apply_shape_operation(
        result,
        "ellipse",
        x0,
        y0,
        x1,
        y1,
        outline_label=outline_label,
        fill_label=fill_label,
        width=width,
    )


def apply_line_operation(
    result: ProcessResult,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    outline_label: int,
    *,
    width: int = BRUSH_WIDTH_DEFAULT,
) -> tuple[ProcessResult, int]:
    return _apply_shape_operation(
        result,
        "line",
        x0,
        y0,
        x1,
        y1,
        outline_label=outline_label,
        fill_label=None,
        width=width,
    )


def brush_footprint(width: int = BRUSH_WIDTH_DEFAULT, shape: str = BRUSH_SHAPE_SQUARE) -> set[tuple[int, int]]:
    return set(_brush_footprint_offsets(width, shape))


@lru_cache(maxsize=None)
def _brush_footprint_offsets(width: int, shape: str) -> tuple[tuple[int, int], ...]:
    normalized_width = _coerce_brush_width(width)
    normalized_shape = _coerce_brush_shape(shape)
    if normalized_width == 1:
        return ((0, 0),)
    start = -(normalized_width // 2)
    offsets = range(start, start + normalized_width)
    if normalized_shape == BRUSH_SHAPE_SQUARE:
        return tuple((offset_x, offset_y) for offset_y in offsets for offset_x in offsets)
    radius = max(1.0, (normalized_width - 1) / 2.0)
    radius_squared = (radius * radius) + 0.25
    return tuple(
        (offset_x, offset_y)
        for offset_y in offsets
        for offset_x in offsets
        if (offset_x * offset_x) + (offset_y * offset_y) <= radius_squared
    )


def apply_pencil_operation(
    result: ProcessResult,
    x: int,
    y: int,
    label: int,
    *,
    width: int = BRUSH_WIDTH_DEFAULT,
    shape: str = BRUSH_SHAPE_SQUARE,
) -> tuple[ProcessResult, int]:
    return apply_pencil_operations(result, ((x, y),), label=label, width=width, shape=shape)


def apply_pencil_operations(
    result: ProcessResult,
    points: tuple[tuple[int, int], ...] | list[tuple[int, int]],
    *,
    label: int,
    width: int = BRUSH_WIDTH_DEFAULT,
    shape: str = BRUSH_SHAPE_SQUARE,
) -> tuple[ProcessResult, int]:
    return _apply_brush_operations(result, points, label=label, erase=False, width=width, shape=shape)


def apply_eraser_operation(
    result: ProcessResult,
    x: int,
    y: int,
    *,
    width: int = BRUSH_WIDTH_DEFAULT,
    shape: str = BRUSH_SHAPE_SQUARE,
) -> tuple[ProcessResult, int]:
    return apply_eraser_operations(result, ((x, y),), width=width, shape=shape)


def apply_eraser_operations(
    result: ProcessResult,
    points: tuple[tuple[int, int], ...] | list[tuple[int, int]],
    *,
    width: int = BRUSH_WIDTH_DEFAULT,
    shape: str = BRUSH_SHAPE_SQUARE,
) -> tuple[ProcessResult, int]:
    return _apply_brush_operations(result, points, label=None, erase=True, width=width, shape=shape)


def add_exterior_outline(
    result: ProcessResult,
    outline_label: int,
    *,
    transparent_labels: set[int] | None = None,
    pixel_perfect: bool = True,
    adaptive: bool = False,
    adaptive_darken_percent: int = 60,
    width: int = BRUSH_WIDTH_DEFAULT,
    workspace: ColorWorkspace | None = None,
) -> tuple[ProcessResult, int, tuple[int, ...]]:
    normalized_width = _coerce_brush_width(width)
    current = result
    total_changed = 0
    generated_labels: set[int] = set()
    color_workspace = workspace or ColorWorkspace()
    for _ in range(normalized_width):
        current, changed, generated = _add_exterior_outline_pass(
            current,
            outline_label,
            transparent_labels=transparent_labels,
            pixel_perfect=pixel_perfect,
            adaptive=adaptive,
            adaptive_darken_percent=adaptive_darken_percent,
            workspace=color_workspace,
        )
        if changed <= 0:
            break
        total_changed += changed
        generated_labels.update(generated)
    if total_changed == 0:
        return result, 0, ()
    return current, total_changed, tuple(sorted(generated_labels))


def _add_exterior_outline_pass(
    result: ProcessResult,
    outline_label: int,
    *,
    transparent_labels: set[int] | None = None,
    pixel_perfect: bool = True,
    adaptive: bool = False,
    adaptive_darken_percent: int = 60,
    workspace: ColorWorkspace,
) -> tuple[ProcessResult, int, tuple[int, ...]]:
    if result.width <= 0 or result.height <= 0:
        return result, 0, ()
    visible = _effective_visible_mask(result, transparent_labels)
    exterior = _exterior_transparent_mask(visible)
    outline_mask = _raw_exterior_outline_mask(visible, exterior)
    if pixel_perfect:
        outline_mask = _pixel_perfect_mask(outline_mask)
    next_grid = [list(row) for row in result.grid]
    next_mask = [row[:] for row in visible]
    changed = 0
    generated_labels: set[int] = set()
    outline_rgb = _label_to_rgb(outline_label)
    darken_percent = _coerce_outline_darken_percent(adaptive_darken_percent)
    for y in range(result.height):
        for x in range(result.width):
            if not outline_mask[y][x]:
                continue
            if adaptive:
                label = _adaptive_outline_label(result, visible, x, y, darken_percent=darken_percent, workspace=workspace)
                next_grid[y][x] = _label_to_rgb(label)
                generated_labels.add(label)
            else:
                next_grid[y][x] = outline_rgb
                generated_labels.add(outline_label)
            next_mask[y][x] = True
            changed += 1
    if changed == 0:
        return result, 0, ()
    return replace(result, grid=next_grid, alpha_mask=_normalize_alpha_mask(next_mask)), changed, tuple(sorted(generated_labels))


def _adaptive_outline_label(
    result: ProcessResult,
    visible: list[list[bool]],
    x: int,
    y: int,
    *,
    darken_percent: int,
    workspace: ColorWorkspace,
) -> int:
    labels = _sample_interior_neighbor_labels(result, visible, x, y)
    dominant = _select_dominant_color_label(labels)
    return _darken_label(dominant, darken_percent=darken_percent, workspace=workspace)


def remove_exterior_outline(
    result: ProcessResult,
    *,
    transparent_labels: set[int] | None = None,
    pixel_perfect: bool = True,
    brightness_threshold_enabled: bool = False,
    brightness_threshold_percent: int = OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT,
    brightness_threshold_direction: str = OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK,
    width: int = BRUSH_WIDTH_DEFAULT,
    workspace: ColorWorkspace | None = None,
) -> tuple[ProcessResult, int]:
    normalized_width = _coerce_brush_width(width)
    current = result
    total_changed = 0
    color_workspace = workspace or ColorWorkspace()
    for _ in range(normalized_width):
        current, changed = _remove_exterior_outline_pass(
            current,
            transparent_labels=transparent_labels,
            pixel_perfect=pixel_perfect,
            brightness_threshold_enabled=brightness_threshold_enabled,
            brightness_threshold_percent=brightness_threshold_percent,
            brightness_threshold_direction=brightness_threshold_direction,
            workspace=color_workspace,
        )
        if changed <= 0:
            break
        total_changed += changed
    if total_changed == 0:
        return result, 0
    return current, total_changed


def _remove_exterior_outline_pass(
    result: ProcessResult,
    *,
    transparent_labels: set[int] | None = None,
    pixel_perfect: bool = True,
    brightness_threshold_enabled: bool = False,
    brightness_threshold_percent: int = OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT,
    brightness_threshold_direction: str = OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK,
    workspace: ColorWorkspace,
) -> tuple[ProcessResult, int]:
    if result.width <= 0 or result.height <= 0:
        return result, 0
    visible = _effective_visible_mask(result, transparent_labels)
    exterior = _exterior_transparent_mask(visible)
    remove_mask = _raw_exterior_edge_mask(visible, exterior)
    if brightness_threshold_enabled:
        remove_mask = _filter_remove_mask_by_brightness(
            result,
            remove_mask,
            threshold_percent=brightness_threshold_percent,
            direction=brightness_threshold_direction,
            workspace=workspace,
        )
    if pixel_perfect:
        remove_mask = _pixel_perfect_mask(remove_mask)
    next_mask = [row[:] for row in visible]
    changed = 0
    for y in range(result.height):
        for x in range(result.width):
            if not remove_mask[y][x]:
                continue
            next_mask[y][x] = False
            changed += 1
    if changed == 0:
        return result, 0
    return replace(result, alpha_mask=_normalize_alpha_mask(next_mask)), changed


def _effective_visible_mask(result: ProcessResult, transparent_labels: set[int] | None = None) -> list[list[bool]]:
    blocked = transparent_labels or set()
    alpha_mask = result.alpha_mask
    visible: list[list[bool]] = []
    for y, row in enumerate(result.grid):
        visible_row: list[bool] = []
        for x, (red, green, blue) in enumerate(row):
            label = (red << 16) | (green << 8) | blue
            alpha_visible = True if alpha_mask is None else bool(alpha_mask[y][x])
            visible_row.append(alpha_visible and label not in blocked)
        visible.append(visible_row)
    return visible


def _sample_interior_neighbor_labels(result: ProcessResult, visible: list[list[bool]], x: int, y: int) -> list[int]:
    neighbors_8 = _collect_neighbor_labels(result, visible, x, y, include_diagonals=True)
    if neighbors_8:
        return neighbors_8
    neighbors_4 = _collect_neighbor_labels(result, visible, x, y, include_diagonals=False)
    if neighbors_4:
        return neighbors_4
    return _collect_nearest_visible_labels(result, visible, x, y)


def _collect_neighbor_labels(
    result: ProcessResult,
    visible: list[list[bool]],
    x: int,
    y: int,
    *,
    include_diagonals: bool,
) -> list[int]:
    labels: list[int] = []
    for neighbor_y in range(max(0, y - 1), min(result.height, y + 2)):
        for neighbor_x in range(max(0, x - 1), min(result.width, x + 2)):
            if neighbor_x == x and neighbor_y == y:
                continue
            if not include_diagonals and neighbor_x != x and neighbor_y != y:
                continue
            if not visible[neighbor_y][neighbor_x]:
                continue
            red, green, blue = result.grid[neighbor_y][neighbor_x]
            labels.append((red << 16) | (green << 8) | blue)
    return labels


def _collect_nearest_visible_labels(result: ProcessResult, visible: list[list[bool]], x: int, y: int) -> list[int]:
    max_radius = max(result.width, result.height)
    for radius in range(1, max_radius + 1):
        labels: list[int] = []
        min_x = max(0, x - radius)
        max_x = min(result.width - 1, x + radius)
        min_y = max(0, y - radius)
        max_y = min(result.height - 1, y + radius)
        for neighbor_y in range(min_y, max_y + 1):
            for neighbor_x in range(min_x, max_x + 1):
                if max(abs(neighbor_x - x), abs(neighbor_y - y)) != radius:
                    continue
                if not visible[neighbor_y][neighbor_x]:
                    continue
                red, green, blue = result.grid[neighbor_y][neighbor_x]
                labels.append((red << 16) | (green << 8) | blue)
        if labels:
            return labels
    return [0]


def _select_dominant_color_label(labels: list[int]) -> int:
    if not labels:
        return 0
    frequencies: dict[int, int] = {}
    for label in labels:
        frequencies[label] = frequencies.get(label, 0) + 1
    max_count = max(frequencies.values())
    candidates = [label for label, count in frequencies.items() if count == max_count]
    return min(candidates)


def _darken_label(label: int, *, darken_percent: int, workspace: ColorWorkspace) -> int:
    percent = _coerce_outline_darken_percent(darken_percent)
    if percent <= 0:
        return int(label)
    if percent >= 100:
        return 0
    oklab = workspace.label_to_oklab(int(label))
    oklch = oklab_to_oklch(np.asarray([oklab], dtype=np.float64))
    oklch[0, 0] = np.clip(oklch[0, 0] * (1.0 - (percent / 100.0)), 0.0, 1.0)
    darkened = oklch_to_oklab(oklch)[0]
    return workspace.oklab_to_label(darkened)


def _coerce_outline_darken_percent(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 60
    return max(0, min(100, parsed))


def _coerce_brush_width(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = BRUSH_WIDTH_DEFAULT
    return max(BRUSH_WIDTH_MIN, min(BRUSH_WIDTH_MAX, parsed))


def _coerce_brush_shape(value: object) -> str:
    normalized = str(value or BRUSH_SHAPE_SQUARE).strip().lower()
    if normalized == BRUSH_SHAPE_ROUND:
        return BRUSH_SHAPE_ROUND
    return BRUSH_SHAPE_SQUARE


def _coerce_outline_remove_brightness_threshold_percent(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT
    return max(0, min(100, parsed))


def _coerce_outline_remove_brightness_direction(value: object) -> str:
    normalized = str(value or OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK).strip().lower()
    if normalized == OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_BRIGHT:
        return OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_BRIGHT
    return OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK


def _filter_remove_mask_by_brightness(
    result: ProcessResult,
    remove_mask: list[list[bool]],
    *,
    threshold_percent: int,
    direction: str,
    workspace: ColorWorkspace,
) -> list[list[bool]]:
    filtered = [row[:] for row in remove_mask]
    threshold_lightness = _coerce_outline_remove_brightness_threshold_percent(threshold_percent) / 100.0
    normalized_direction = _coerce_outline_remove_brightness_direction(direction)
    for y in range(result.height):
        for x in range(result.width):
            if not remove_mask[y][x]:
                continue
            red, green, blue = result.grid[y][x]
            label = (red << 16) | (green << 8) | blue
            filtered[y][x] = _matches_outline_remove_brightness_threshold(
                label,
                threshold_lightness=threshold_lightness,
                direction=normalized_direction,
                workspace=workspace,
            )
    return filtered


def _matches_outline_remove_brightness_threshold(
    label: int,
    *,
    threshold_lightness: float,
    direction: str,
    workspace: ColorWorkspace,
) -> bool:
    lightness = float(workspace.label_to_oklab(int(label))[0])
    if direction == OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_BRIGHT:
        return lightness >= threshold_lightness
    return lightness <= threshold_lightness


def _label_to_rgb(label: int) -> RGB:
    return ((label >> 16) & 0xFF, (label >> 8) & 0xFF, label & 0xFF)


def _apply_shape_operation(
    result: ProcessResult,
    shape: str,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    outline_label: int,
    fill_label: int | None,
    width: int,
) -> tuple[ProcessResult, int]:
    if result.width <= 0 or result.height <= 0:
        return result, 0
    outline_points, fill_points = _rasterize_shape_points(
        shape,
        result.width,
        result.height,
        x0,
        y0,
        x1,
        y1,
        width=width,
    )
    if not outline_points and not fill_points:
        return result, 0
    current_mask = result.alpha_mask
    next_grid = [list(row) for row in result.grid]
    needs_mask_copy = current_mask is not None or fill_label is None
    next_mask = (
        [list(row) for row in current_mask]
        if current_mask is not None
        else ([[True] * result.width for _ in range(result.height)] if needs_mask_copy else None)
    )
    changed_points: set[tuple[int, int]] = set()
    if fill_points:
        _apply_shape_points(
            result,
            next_grid,
            next_mask,
            changed_points,
            fill_points,
            label=fill_label,
        )
    if outline_points:
        _apply_shape_points(
            result,
            next_grid,
            next_mask,
            changed_points,
            outline_points,
            label=outline_label,
        )
    if not changed_points:
        return result, 0
    if next_mask is not None:
        return replace(result, grid=next_grid, alpha_mask=_normalize_alpha_mask(next_mask)), len(changed_points)
    return replace(result, grid=next_grid), len(changed_points)


def _apply_shape_points(
    result: ProcessResult,
    next_grid: RGBGrid,
    next_mask: list[list[bool]] | None,
    changed_points: set[tuple[int, int]],
    points: set[tuple[int, int]],
    *,
    label: int | None,
) -> None:
    current_mask = result.alpha_mask
    target_rgb = _label_to_rgb(label) if label is not None else None
    for point_x, point_y in points:
        current_visible = True if current_mask is None else bool(current_mask[point_y][point_x])
        if label is None:
            if not current_visible:
                continue
            assert next_mask is not None
            next_mask[point_y][point_x] = False
            changed_points.add((point_x, point_y))
            continue
        assert target_rgb is not None
        if current_visible and result.grid[point_y][point_x] == target_rgb:
            continue
        next_grid[point_y][point_x] = target_rgb
        if next_mask is not None:
            next_mask[point_y][point_x] = True
        changed_points.add((point_x, point_y))


def _rasterize_shape_points(
    shape: str,
    image_width: int,
    image_height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    width: int,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    if image_width <= 0 or image_height <= 0:
        return set(), set()
    stroke_width = _coerce_brush_width(width)
    if shape == "line":
        line_mask = Image.new("1", (image_width, image_height), 0)
        line_draw = ImageDraw.Draw(line_mask)
        line_draw.line((int(x0), int(y0), int(x1), int(y1)), fill=1, width=stroke_width)
        return _mask_points(line_mask), set()
    left, right = sorted((int(x0), int(x1)))
    top, bottom = sorted((int(y0), int(y1)))
    fill_mask = Image.new("1", (image_width, image_height), 0)
    outline_mask = Image.new("1", (image_width, image_height), 0)
    fill_draw = ImageDraw.Draw(fill_mask)
    outline_draw = ImageDraw.Draw(outline_mask)
    bounds = (left, top, right, bottom)
    if shape == "ellipse":
        fill_draw.ellipse(bounds, fill=1)
        outline_draw.ellipse(bounds, outline=1, width=stroke_width)
    else:
        fill_draw.rectangle(bounds, fill=1)
        outline_draw.rectangle(bounds, outline=1, width=stroke_width)
    outline_points = _mask_points(outline_mask)
    fill_points = _mask_points(fill_mask) - outline_points
    return outline_points, fill_points


def _mask_points(mask: Image.Image) -> set[tuple[int, int]]:
    width, height = mask.size
    points: set[tuple[int, int]] = set()
    pixels = mask.load()
    for y in range(height):
        for x in range(width):
            if pixels[x, y]:
                points.add((x, y))
    return points


def _brush_points_in_bounds(
    result: ProcessResult,
    x: int,
    y: int,
    *,
    width: int,
    shape: str,
) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for offset_x, offset_y in _brush_footprint_offsets(_coerce_brush_width(width), _coerce_brush_shape(shape)):
        point_x = x + offset_x
        point_y = y + offset_y
        if point_x < 0 or point_y < 0 or point_x >= result.width or point_y >= result.height:
            continue
        points.append((point_x, point_y))
    return points


def _apply_brush_operations(
    result: ProcessResult,
    points: tuple[tuple[int, int], ...] | list[tuple[int, int]],
    *,
    label: int | None,
    erase: bool,
    width: int,
    shape: str,
) -> tuple[ProcessResult, int]:
    if result.width <= 0 or result.height <= 0:
        return result, 0
    if not points:
        return result, 0
    current_mask = result.alpha_mask
    target_rgb = _label_to_rgb(label) if label is not None else None
    changed_points: set[tuple[int, int]] = set()
    needs_mask_copy = erase or current_mask is not None
    for center_x, center_y in points:
        if center_x < 0 or center_y < 0 or center_x >= result.width or center_y >= result.height:
            continue
        for point_x, point_y in _brush_points_in_bounds(result, center_x, center_y, width=width, shape=shape):
            if (point_x, point_y) in changed_points:
                continue
            if erase:
                if current_mask is not None and not current_mask[point_y][point_x]:
                    continue
            else:
                assert target_rgb is not None
                is_visible = True if current_mask is None else bool(current_mask[point_y][point_x])
                if result.grid[point_y][point_x] == target_rgb and is_visible:
                    continue
            changed_points.add((point_x, point_y))
    if not changed_points:
        return result, 0
    next_grid = [list(row) for row in result.grid] if not erase else None
    next_mask = [list(row) for row in current_mask] if current_mask is not None else ([[True] * result.width for _ in range(result.height)] if needs_mask_copy else None)
    if erase:
        assert next_mask is not None
        for point_x, point_y in changed_points:
            next_mask[point_y][point_x] = False
        return replace(result, alpha_mask=_normalize_alpha_mask(next_mask)), len(changed_points)
    assert next_grid is not None and target_rgb is not None
    if next_mask is not None:
        for point_x, point_y in changed_points:
            next_grid[point_y][point_x] = target_rgb
            next_mask[point_y][point_x] = True
        return replace(result, grid=next_grid, alpha_mask=_normalize_alpha_mask(next_mask)), len(changed_points)
    for point_x, point_y in changed_points:
        next_grid[point_y][point_x] = target_rgb
    return replace(result, grid=next_grid), len(changed_points)


def _raw_exterior_outline_mask(visible: list[list[bool]], exterior: list[list[bool]]) -> list[list[bool]]:
    height = len(visible)
    width = len(visible[0]) if height else 0
    outline = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if visible[y][x] or not exterior[y][x]:
                continue
            outline[y][x] = _touches_visible_pixel(visible, x, y)
    return outline


def _raw_exterior_edge_mask(visible: list[list[bool]], exterior: list[list[bool]]) -> list[list[bool]]:
    height = len(visible)
    width = len(visible[0]) if height else 0
    edge = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if not visible[y][x]:
                continue
            edge[y][x] = _touches_exterior_space(exterior, x, y)
    return edge


def _exterior_transparent_mask(visible: list[list[bool]]) -> list[list[bool]]:
    height = len(visible)
    width = len(visible[0]) if height else 0
    exterior = [[False] * width for _ in range(height)]
    pending: list[tuple[int, int]] = []
    for x in range(width):
        pending.append((x, 0))
        pending.append((x, height - 1))
    for y in range(1, max(0, height - 1)):
        pending.append((0, y))
        pending.append((width - 1, y))
    while pending:
        x, y = pending.pop()
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        if exterior[y][x] or visible[y][x]:
            continue
        exterior[y][x] = True
        pending.append((x - 1, y))
        pending.append((x + 1, y))
        pending.append((x, y - 1))
        pending.append((x, y + 1))
    return exterior


def _touches_visible_pixel(visible: list[list[bool]], x: int, y: int) -> bool:
    height = len(visible)
    width = len(visible[0]) if height else 0
    for neighbor_y in range(max(0, y - 1), min(height, y + 2)):
        for neighbor_x in range(max(0, x - 1), min(width, x + 2)):
            if neighbor_x == x and neighbor_y == y:
                continue
            if visible[neighbor_y][neighbor_x]:
                return True
    return False


def _touches_exterior_space(exterior: list[list[bool]], x: int, y: int) -> bool:
    height = len(exterior)
    width = len(exterior[0]) if height else 0
    for neighbor_y in range(max(0, y - 1), min(height, y + 2)):
        for neighbor_x in range(max(0, x - 1), min(width, x + 2)):
            if neighbor_x == x and neighbor_y == y:
                continue
            if exterior[neighbor_y][neighbor_x]:
                return True
    return x == 0 or y == 0 or x == width - 1 or y == height - 1


def _pixel_perfect_mask(mask: list[list[bool]]) -> list[list[bool]]:
    cleaned = [row[:] for row in mask]
    height = len(cleaned)
    width = len(cleaned[0]) if height else 0
    if width == 0 or height == 0:
        return cleaned
    changed = True
    while changed:
        changed = False
        for phase in range(2):
            coordinates = [(x, y) for y in range(height) for x in range(width)]
            if phase == 1:
                coordinates.reverse()
            phase_changed = False
            for x, y in coordinates:
                if not _pixel_perfect_candidate(cleaned, x, y, phase):
                    continue
                cleaned[y][x] = False
                phase_changed = True
            changed = changed or phase_changed
    return cleaned


def _pixel_perfect_candidate(mask: list[list[bool]], x: int, y: int, phase: int) -> bool:
    if not mask[y][x]:
        return False
    north = y > 0 and mask[y - 1][x]
    east = x + 1 < len(mask[0]) and mask[y][x + 1]
    south = y + 1 < len(mask) and mask[y + 1][x]
    west = x > 0 and mask[y][x - 1]
    orthogonal = [north, east, south, west]
    active_neighbors = 0
    for neighbor_y in range(max(0, y - 1), min(len(mask), y + 2)):
        for neighbor_x in range(max(0, x - 1), min(len(mask[0]), x + 2)):
            if neighbor_x == x and neighbor_y == y:
                continue
            if mask[neighbor_y][neighbor_x]:
                active_neighbors += 1
    if active_neighbors < 2 or active_neighbors > 6:
        return False
    if sum(orthogonal) != 2:
        return False
    if (north and south) or (east and west):
        return False
    ring = orthogonal + [orthogonal[0]]
    transitions = sum((not current) and following for current, following in zip(ring, ring[1:]))
    if transitions != 1:
        return False
    if phase == 0:
        if north and east and south:
            return False
        if east and south and west:
            return False
    else:
        if north and east and west:
            return False
        if north and south and west:
            return False
    return _preserves_local_connectivity(mask, x, y)


def _preserves_local_connectivity(mask: list[list[bool]], x: int, y: int) -> bool:
    height = len(mask)
    width = len(mask[0]) if height else 0
    neighbors: list[tuple[int, int]] = []
    for neighbor_y in range(max(0, y - 1), min(height, y + 2)):
        for neighbor_x in range(max(0, x - 1), min(width, x + 2)):
            if neighbor_x == x and neighbor_y == y:
                continue
            if mask[neighbor_y][neighbor_x]:
                neighbors.append((neighbor_x, neighbor_y))
    if len(neighbors) <= 1:
        return True
    allowed = set(neighbors)
    pending = [neighbors[0]]
    visited: set[tuple[int, int]] = set()
    while pending:
        point = pending.pop()
        if point in visited:
            continue
        visited.add(point)
        px, py = point
        for neighbor_y in range(max(0, py - 1), min(height, py + 2)):
            for neighbor_x in range(max(0, px - 1), min(width, px + 2)):
                neighbor = (neighbor_x, neighbor_y)
                if neighbor in allowed and neighbor not in visited:
                    pending.append(neighbor)
    return len(visited) == len(allowed)


def _normalize_alpha_mask(mask: list[list[bool]]) -> tuple[tuple[bool, ...], ...] | None:
    if all(all(value for value in row) for row in mask):
        return None
    return tuple(tuple(row) for row in mask)


def grid_to_pil_image(grid: RGBGrid) -> Image.Image:
    height = len(grid)
    width = len(grid[0]) if height else 0
    image = Image.new("RGB", (width, height))
    if width == 0 or height == 0:
        return image
    image.putdata([pixel for row in grid for pixel in row])
    return image


def load_png_grid(path: str) -> RGBGrid:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        pixels = list(rgb.getdata())
    return [pixels[index : index + width] for index in range(0, width * height, width)] if height else []


def load_png_rgba_image(path: str) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA").copy()


def image_to_rgb_grid(image: Image.Image) -> RGBGrid:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = list(rgb.getdata())
    return [pixels[index : index + width] for index in range(0, width * height, width)] if height else []


def downsample_image(
    grid: RGBGrid,
    config: PipelineConfig,
    progress_callback: PipelineProgressCallback | None = None,
) -> ProcessResult:
    started = perf_counter()
    pipeline = PixelFixPipeline(config)
    prepared_input = pipeline.prepare_labels(
        rgb_to_labels(grid),
        progress_callback=progress_callback,
        grid_message=f"Downsampling with {display_resize_method(config.downsample_mode)}...",
    )
    display_palette_labels = tuple(extract_unique_colors(prepared_input.reduced_labels))
    rgb_grid = labels_to_rgb(prepared_input.reduced_labels)
    height = len(rgb_grid)
    width = len(rgb_grid[0]) if height else 0
    return ProcessResult(
        grid=rgb_grid,
        width=width,
        height=height,
        stats=ProcessStats(
            stage="downsample",
            pixel_width=prepared_input.pixel_width,
            resize_method=config.downsample_mode,
            input_size=prepared_input.input_size,
            output_size=(width, height),
            initial_color_count=prepared_input.initial_color_count,
            color_count=len(display_palette_labels),
            elapsed_seconds=perf_counter() - started,
        ),
        prepared_input=prepared_input,
        display_palette_labels=display_palette_labels,
    )


def reduce_palette_image(
    prepared_input: PipelinePreparedResult,
    config: PipelineConfig,
    palette_override: list[int] | None = None,
    structured_palette: StructuredPalette | None = None,
    progress_callback: PipelineProgressCallback | None = None,
) -> ProcessResult:
    started = perf_counter()
    pipeline = PixelFixPipeline(config)
    result = pipeline.run_prepared_labels(
        prepared_input,
        palette_override=palette_override,
        structured_palette=structured_palette,
        progress_callback=progress_callback,
    )
    output_palette_labels = tuple(extract_unique_colors(result.labels))
    display_palette_labels = tuple(result.structured_palette.labels()) if result.structured_palette is not None else output_palette_labels
    rgb_grid = labels_to_rgb(result.labels)
    height = len(rgb_grid)
    width = len(rgb_grid[0]) if height else 0
    return ProcessResult(
        grid=rgb_grid,
        width=width,
        height=height,
        stats=ProcessStats(
            stage="palette",
            pixel_width=result.pixel_width,
            resize_method=config.downsample_mode,
            input_size=prepared_input.input_size,
            output_size=(width, height),
            initial_color_count=prepared_input.initial_color_count,
            color_count=len(output_palette_labels),
            elapsed_seconds=perf_counter() - started,
            seed_count=result.seed_count,
            ramp_count=result.ramp_count,
            palette_strategy=result.structured_palette.source_mode if result.structured_palette is not None else config.palette_strategy,
            effective_palette_size=result.effective_palette_size,
            histogram_size=result.histogram_size,
            palette_generation_seconds=result.palette_generation_seconds,
            mapping_seconds=result.mapping_seconds,
        ),
        prepared_input=prepared_input,
        display_palette_labels=display_palette_labels,
        structured_palette=result.structured_palette,
    )


def reduce_indexed_color(
    result: ProcessResult,
    settings: IndexedColorSettings,
    *,
    workspace: ColorWorkspace | None = None,
) -> IndexedColorProcessResult:
    started = perf_counter()
    color_workspace = workspace or ColorWorkspace()
    labels = rgb_to_labels(result.grid)
    visibility = _indexed_color_visibility_mask(result)
    visible_labels = _flatten_visible_labels(labels, visibility)
    histogram_size = len(set(visible_labels))
    forced_labels = list(INDEXED_COLOR_FORCED_PALETTES.get(settings.forced_palette, ()))
    forced_labels = _dedupe_palette_labels(forced_labels)
    color_count = max(len(forced_labels), max(2, min(256, int(settings.colors))))
    palette_generation_started = perf_counter()
    generated_palette = _indexed_color_palette_for_visible_labels(
        visible_labels,
        color_count=color_count,
        palette_method=settings.palette_method,
        forced_labels=forced_labels,
        workspace=color_workspace,
    )
    palette_generation_seconds = perf_counter() - palette_generation_started
    mapping_started = perf_counter()
    if generated_palette:
        if settings.dither_mode == INDEXED_COLOR_DITHER_DIFFUSION:
            mapped = _apply_indexed_color_diffusion(
                labels,
                visibility,
                generated_palette,
                diffusion_amount=settings.diffusion_amount,
                workspace=color_workspace,
            )
        else:
            mapped = _map_indexed_color_labels(labels, visibility, generated_palette, workspace=color_workspace)
    else:
        mapped = [row[:] for row in labels]
    mapping_seconds = perf_counter() - mapping_started
    reduced_grid = labels_to_rgb(mapped)
    stage_label = INDEXED_COLOR_PALETTE_LABELS.get(settings.palette_method, settings.palette_method)
    color_total = len(generated_palette)
    return IndexedColorProcessResult(
        result=ProcessResult(
            grid=reduced_grid,
            width=result.width,
            height=result.height,
            stats=replace(
                result.stats,
                stage="indexed-color",
                output_size=(result.width, result.height),
                color_count=color_total,
                elapsed_seconds=perf_counter() - started,
                palette_strategy=f"indexed-color:{settings.palette_method}",
                effective_palette_size=color_total,
                histogram_size=histogram_size,
                palette_generation_seconds=palette_generation_seconds,
                mapping_seconds=mapping_seconds,
                ramp_count=0,
                seed_count=0,
            ),
            prepared_input=result.prepared_input,
            display_palette_labels=tuple(generated_palette),
            structured_palette=None,
            alpha_mask=result.alpha_mask,
        ),
        palette_labels=tuple(generated_palette),
        source_label=f"Indexed Color: {stage_label}",
    )


def process_result_to_rgba_image(result: ProcessResult) -> Image.Image:
    image = Image.new("RGBA", (result.width, result.height))
    if result.width <= 0 or result.height <= 0:
        return image
    alpha_mask = result.alpha_mask
    image.putdata(
        [
            (red, green, blue, 255 if alpha_mask is None or alpha_mask[y][x] else 0)
            for y, row in enumerate(result.grid)
            for x, (red, green, blue) in enumerate(row)
        ]
    )
    return image


def apply_blur(result: ProcessResult, strength: int) -> tuple[ProcessResult, int]:
    normalized_strength = _coerce_image_filter_strength(strength)
    if result.width <= 0 or result.height <= 0:
        return result, 0
    visible = _indexed_color_visibility_mask(result)
    if not any(any(row) for row in visible):
        return result, 0
    started = perf_counter()
    next_grid = [list(row) for row in result.grid]
    for _ in range(normalized_strength):
        next_grid = _apply_gaussian_blur_pass(next_grid, visible)
    changed = _count_visible_grid_changes(result.grid, next_grid, visible)
    if changed <= 0:
        return result, 0
    return (
        replace(
            result,
            grid=next_grid,
            stats=_filtered_process_stats(result, next_grid, visible, stage="tool-blur", elapsed_seconds=perf_counter() - started),
            display_palette_labels=tuple(_visible_palette_labels(next_grid, visible)),
        ),
        changed,
    )


def apply_sharpen(result: ProcessResult, strength: int) -> tuple[ProcessResult, int]:
    normalized_strength = _coerce_image_filter_strength(strength)
    if result.width <= 0 or result.height <= 0:
        return result, 0
    visible = _indexed_color_visibility_mask(result)
    if not any(any(row) for row in visible):
        return result, 0
    started = perf_counter()
    next_grid = [list(row) for row in result.grid]
    for _ in range(normalized_strength):
        blurred = _apply_gaussian_blur_pass(next_grid, visible)
        sharpened: RGBGrid = []
        for y in range(result.height):
            sharpened_row: list[RGB] = []
            for x in range(result.width):
                original_rgb = next_grid[y][x]
                if not visible[y][x]:
                    sharpened_row.append(original_rgb)
                    continue
                blurred_rgb = blurred[y][x]
                sharpened_row.append(
                    tuple(
                        _clamp_channel(round(channel + (0.35 * (channel - blurred_channel))))
                        for channel, blurred_channel in zip(original_rgb, blurred_rgb, strict=False)
                    )
                )
            sharpened.append(sharpened_row)
        next_grid = sharpened
    changed = _count_visible_grid_changes(result.grid, next_grid, visible)
    if changed <= 0:
        return result, 0
    return (
        replace(
            result,
            grid=next_grid,
            stats=_filtered_process_stats(result, next_grid, visible, stage="tool-sharpen", elapsed_seconds=perf_counter() - started),
            display_palette_labels=tuple(_visible_palette_labels(next_grid, visible)),
        ),
        changed,
    )


def resize_canvas_result(result: ProcessResult, spec: CanvasResizeSpec) -> ProcessResult:
    target_width = max(1, int(spec.width))
    target_height = max(1, int(spec.height))
    anchor = _coerce_canvas_resize_anchor(spec.anchor)
    if target_width == result.width and target_height == result.height:
        return result

    horizontal_alignment, vertical_alignment = _canvas_resize_anchor_alignment(anchor)
    source_x, target_x, copy_width = _canvas_resize_offsets(result.width, target_width, horizontal_alignment)
    source_y, target_y, copy_height = _canvas_resize_offsets(result.height, target_height, vertical_alignment)

    next_grid: RGBGrid = [[(0, 0, 0) for _ in range(target_width)] for _ in range(target_height)]
    current_mask = result.alpha_mask
    needs_alpha_mask = current_mask is not None or target_width > result.width or target_height > result.height
    next_mask = [[False for _ in range(target_width)] for _ in range(target_height)] if needs_alpha_mask else None

    for row_offset in range(copy_height):
        source_row_index = source_y + row_offset
        target_row_index = target_y + row_offset
        for column_offset in range(copy_width):
            source_column_index = source_x + column_offset
            target_column_index = target_x + column_offset
            next_grid[target_row_index][target_column_index] = result.grid[source_row_index][source_column_index]
            if next_mask is not None:
                next_mask[target_row_index][target_column_index] = (
                    True if current_mask is None else bool(current_mask[source_row_index][source_column_index])
                )

    normalized_mask = _normalize_alpha_mask(next_mask) if next_mask is not None else None
    visible = (
        [[True] * target_width for _ in range(target_height)]
        if normalized_mask is None
        else [[bool(value) for value in row] for row in normalized_mask]
    )
    display_palette_labels = tuple(_visible_palette_labels(next_grid, visible))
    return replace(
        result,
        grid=next_grid,
        width=target_width,
        height=target_height,
        stats=replace(
            result.stats,
            output_size=(target_width, target_height),
            color_count=len(display_palette_labels),
        ),
        display_palette_labels=display_palette_labels,
        alpha_mask=normalized_mask,
    )


def _indexed_color_visibility_mask(result: ProcessResult) -> list[list[bool]]:
    alpha_mask = result.alpha_mask
    if alpha_mask is None:
        return [[True] * result.width for _ in range(result.height)]
    return [[bool(value) for value in row] for row in alpha_mask]


def _flatten_visible_labels(labels: LabelGrid, visibility: list[list[bool]]) -> list[int]:
    return [label for y, row in enumerate(labels) for x, label in enumerate(row) if visibility[y][x]]


def _apply_gaussian_blur_pass(grid: RGBGrid, visible: list[list[bool]]) -> RGBGrid:
    height = len(grid)
    width = len(grid[0]) if height else 0
    kernel = (
        (1, 2, 1),
        (2, 4, 2),
        (1, 2, 1),
    )
    blurred: RGBGrid = []
    for y in range(height):
        row: list[RGB] = []
        for x in range(width):
            if not visible[y][x]:
                row.append(grid[y][x])
                continue
            red_total = 0
            green_total = 0
            blue_total = 0
            weight_total = 0
            for dy in range(-1, 2):
                sample_y = y + dy
                if sample_y < 0 or sample_y >= height:
                    continue
                for dx in range(-1, 2):
                    sample_x = x + dx
                    if sample_x < 0 or sample_x >= width or not visible[sample_y][sample_x]:
                        continue
                    weight = kernel[dy + 1][dx + 1]
                    sample_red, sample_green, sample_blue = grid[sample_y][sample_x]
                    red_total += sample_red * weight
                    green_total += sample_green * weight
                    blue_total += sample_blue * weight
                    weight_total += weight
            if weight_total <= 0:
                row.append(grid[y][x])
                continue
            row.append(
                (
                    round(red_total / weight_total),
                    round(green_total / weight_total),
                    round(blue_total / weight_total),
                )
            )
        blurred.append(row)
    return blurred


def _filtered_process_stats(
    result: ProcessResult,
    grid: RGBGrid,
    visible: list[list[bool]],
    *,
    stage: str,
    elapsed_seconds: float,
) -> ProcessStats:
    return replace(
        result.stats,
        stage=stage,
        output_size=(result.width, result.height),
        color_count=len(set(_visible_palette_labels(grid, visible))),
        elapsed_seconds=elapsed_seconds,
    )


def _visible_palette_labels(grid: RGBGrid, visible: list[list[bool]]) -> list[int]:
    labels: list[int] = []
    seen: set[int] = set()
    for y, row in enumerate(grid):
        for x, (red, green, blue) in enumerate(row):
            if not visible[y][x]:
                continue
            label = (red << 16) | (green << 8) | blue
            if label in seen:
                continue
            seen.add(label)
            labels.append(label)
    return labels


def _count_visible_grid_changes(before: RGBGrid, after: RGBGrid, visible: list[list[bool]]) -> int:
    changed = 0
    for y, row in enumerate(before):
        for x, rgb in enumerate(row):
            if visible[y][x] and after[y][x] != rgb:
                changed += 1
    return changed


def _coerce_image_filter_strength(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = IMAGE_FILTER_STRENGTH_DEFAULT
    return max(IMAGE_FILTER_STRENGTH_MIN, min(IMAGE_FILTER_STRENGTH_MAX, parsed))


def _coerce_canvas_resize_anchor(value: object) -> str:
    normalized = str(value or CANVAS_RESIZE_ANCHOR_CENTER).strip().lower()
    if normalized in CANVAS_RESIZE_ANCHORS:
        return normalized
    return CANVAS_RESIZE_ANCHOR_CENTER


def _canvas_resize_anchor_alignment(anchor: str) -> tuple[str, str]:
    normalized = _coerce_canvas_resize_anchor(anchor)
    horizontal = "center"
    vertical = "center"
    if "left" in normalized:
        horizontal = "start"
    elif "right" in normalized:
        horizontal = "end"
    if normalized.startswith("top"):
        vertical = "start"
    elif normalized.startswith("bottom"):
        vertical = "end"
    return horizontal, vertical


def _canvas_resize_offsets(source_size: int, target_size: int, alignment: str) -> tuple[int, int, int]:
    if target_size >= source_size:
        source_start = 0
        if alignment == "start":
            target_start = 0
        elif alignment == "end":
            target_start = target_size - source_size
        else:
            target_start = (target_size - source_size) // 2
        return source_start, target_start, source_size

    target_start = 0
    if alignment == "start":
        source_start = 0
    elif alignment == "end":
        source_start = source_size - target_size
    else:
        source_start = (source_size - target_size) // 2
    return source_start, target_start, target_size


def _clamp_channel(value: float) -> int:
    return max(0, min(255, int(value)))


def _dedupe_palette_labels(labels: list[int] | tuple[int, ...]) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    for label in labels:
        normalized = int(label)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _indexed_color_palette_for_visible_labels(
    visible_labels: list[int],
    *,
    color_count: int,
    palette_method: str,
    forced_labels: list[int],
    workspace: ColorWorkspace,
) -> list[int]:
    if not visible_labels and not forced_labels:
        return []
    filtered = [label for label in visible_labels if label not in set(forced_labels)]
    generated_target = max(0, color_count - len(forced_labels))
    if generated_target <= 0 or not filtered:
        return forced_labels[:color_count]
    if palette_method == INDEXED_COLOR_PALETTE_LOCAL_ADAPTIVE:
        generated = top_k_palette([filtered], generated_target)
    elif palette_method == INDEXED_COLOR_PALETTE_LOCAL_SELECTIVE:
        generated = median_cut_palette([filtered], generated_target)
    else:
        generated = _perceptual_weighted_kmeans_palette(filtered, generated_target, workspace=workspace)
    palette = _dedupe_palette_labels([*forced_labels, *generated])
    if len(palette) >= color_count:
        return palette[:color_count]
    counts = Counter(filtered)
    for label, _count in counts.most_common():
        if label in palette:
            continue
        palette.append(label)
        if len(palette) >= color_count:
            break
    return palette


def _perceptual_weighted_kmeans_palette(
    visible_labels: list[int],
    color_count: int,
    *,
    workspace: ColorWorkspace,
    iterations: int = 10,
) -> list[int]:
    if color_count <= 0 or not visible_labels:
        return []
    unique_labels, counts = np.unique(np.asarray(visible_labels, dtype=np.int64), return_counts=True)
    if unique_labels.size <= color_count:
        ordered = [
            int(label)
            for label, _count in sorted(zip(unique_labels.tolist(), counts.tolist(), strict=False), key=lambda item: item[1], reverse=True)
        ]
        return ordered[:color_count]
    points = workspace.labels_to_oklab(unique_labels)
    weights = counts.astype(np.float64)
    seed_indices = _weighted_kmeans_seed_indices(points, weights, color_count)
    centers = points[seed_indices].copy()
    assignments = np.zeros(unique_labels.size, dtype=np.int64)
    for _ in range(max(1, iterations)):
        distances = np.sum((points[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        next_assignments = np.argmin(distances, axis=1)
        if np.array_equal(next_assignments, assignments):
            break
        assignments = next_assignments
        for index in range(centers.shape[0]):
            mask = assignments == index
            if not np.any(mask):
                farthest = int(np.argmax(np.min(distances, axis=1) * weights))
                centers[index] = points[farthest]
                continue
            cluster_weights = weights[mask]
            centers[index] = np.average(points[mask], axis=0, weights=cluster_weights)
    palette: list[int] = []
    chosen: set[int] = set()
    for index in range(centers.shape[0]):
        distances = np.sum((points - centers[index]) ** 2, axis=1)
        for candidate_index in np.argsort(distances):
            label = int(unique_labels[int(candidate_index)])
            if label in chosen:
                continue
            chosen.add(label)
            palette.append(label)
            break
    if len(palette) < color_count:
        ordered = [
            int(label)
            for label, _count in sorted(zip(unique_labels.tolist(), counts.tolist(), strict=False), key=lambda item: item[1], reverse=True)
        ]
        for label in ordered:
            if label in chosen:
                continue
            chosen.add(label)
            palette.append(label)
            if len(palette) >= color_count:
                break
    return palette[:color_count]


def _weighted_kmeans_seed_indices(points: np.ndarray, weights: np.ndarray, color_count: int) -> np.ndarray:
    ordered = np.argsort(-weights)
    seed_indices: list[int] = [int(ordered[0])]
    while len(seed_indices) < color_count:
        selected = points[np.asarray(seed_indices, dtype=np.int64)]
        distances = np.min(np.sum((points[:, None, :] - selected[None, :, :]) ** 2, axis=2), axis=1)
        score = distances * weights
        score[np.asarray(seed_indices, dtype=np.int64)] = -1.0
        next_index = int(np.argmax(score))
        if next_index in seed_indices:
            break
        seed_indices.append(next_index)
    while len(seed_indices) < color_count:
        next_index = int(ordered[len(seed_indices)])
        if next_index not in seed_indices:
            seed_indices.append(next_index)
    return np.asarray(seed_indices[:color_count], dtype=np.int64)


def _map_indexed_color_labels(
    labels: LabelGrid,
    visibility: list[list[bool]],
    palette_labels: list[int],
    *,
    workspace: ColorWorkspace,
) -> LabelGrid:
    if not palette_labels:
        return [row[:] for row in labels]
    palette_array = np.asarray(palette_labels, dtype=np.int64)
    palette_oklab = workspace.labels_to_oklab(palette_array)
    mapping = _indexed_color_label_mapping(labels, visibility, palette_array, palette_oklab, workspace=workspace)
    return [
        [mapping.get(label, label) if visibility[y][x] else label for x, label in enumerate(row)]
        for y, row in enumerate(labels)
    ]


def _indexed_color_label_mapping(
    labels: LabelGrid,
    visibility: list[list[bool]],
    palette_array: np.ndarray,
    palette_oklab: np.ndarray,
    *,
    workspace: ColorWorkspace,
) -> dict[int, int]:
    unique_visible = np.asarray(sorted({label for y, row in enumerate(labels) for x, label in enumerate(row) if visibility[y][x]}), dtype=np.int64)
    if unique_visible.size == 0:
        return {}
    visible_oklab = workspace.labels_to_oklab(unique_visible)
    distances = hyab_distance(visible_oklab[:, None, :], palette_oklab[None, :, :])
    nearest = palette_array[np.argmin(distances, axis=1)]
    return {int(label): int(mapped) for label, mapped in zip(unique_visible.tolist(), nearest.tolist(), strict=False)}


def _apply_indexed_color_diffusion(
    labels: LabelGrid,
    visibility: list[list[bool]],
    palette_labels: list[int],
    *,
    diffusion_amount: int,
    workspace: ColorWorkspace,
) -> LabelGrid:
    if not palette_labels:
        return [row[:] for row in labels]
    palette_array = np.asarray(palette_labels, dtype=np.int64)
    palette_oklab = workspace.labels_to_oklab(palette_array)
    palette_srgb = workspace.labels_to_srgb(palette_array)
    work = workspace.labels_to_srgb(np.asarray(labels, dtype=np.int64))
    out = [row[:] for row in labels]
    factor = max(0.0, min(1.0, float(diffusion_amount) / 100.0))
    for y in range(len(labels)):
        for x in range(len(labels[0]) if labels else 0):
            if not visibility[y][x]:
                continue
            current_rgb = np.clip(work[y, x], 0.0, 1.0)
            current_oklab = linear_to_oklab(srgb_to_linear(current_rgb.reshape(1, 3)))[0]
            distances = hyab_distance(palette_oklab, current_oklab.reshape(1, 3))
            nearest_index = int(np.argmin(distances))
            out[y][x] = int(palette_array[nearest_index])
            error = (current_rgb - palette_srgb[nearest_index]) * factor
            if factor <= 0.0:
                continue
            for offset_x, offset_y, weight in ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)):
                next_x = x + offset_x
                next_y = y + offset_y
                if next_x < 0 or next_y < 0 or next_y >= len(labels) or next_x >= len(labels[next_y]):
                    continue
                if not visibility[next_y][next_x]:
                    continue
                work[next_y, next_x] += error * weight
    return out


def process_image(
    grid: RGBGrid,
    config: PipelineConfig,
    palette_override: list[int] | None = None,
    structured_palette: StructuredPalette | None = None,
    progress_callback: PipelineProgressCallback | None = None,
    prepared_input: PipelinePreparedResult | None = None,
) -> ProcessResult:
    prepared = prepared_input
    if prepared is None:
        downsampled = downsample_image(grid, config, progress_callback=progress_callback)
        prepared = downsampled.prepared_input
    elif progress_callback is not None:
        progress_callback(10, "Preparing input")
        progress_callback(35, "Reusing downsampled image...")
    return reduce_palette_image(
        prepared,
        config,
        palette_override=palette_override,
        structured_palette=structured_palette,
        progress_callback=progress_callback,
    )


def display_resize_method(value: str) -> str:
    mapping = {
        "nearest": "Nearest Neighbor",
        "bilinear": "Bilinear Interpolation",
        "rotsprite": "RotSprite",
    }
    return mapping.get(value, value.title())
