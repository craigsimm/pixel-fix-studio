from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from pixel_fix.cleanup.components import remove_small_islands_detailed
from pixel_fix.palette.workspace import ColorWorkspace
from pixel_fix.types import LabelGrid

CLEANUP_MODE_OFF = "off"
CLEANUP_MODE_CONSERVATIVE = "conservative"
CLEANUP_MODE_BALANCED = "balanced"
CLEANUP_MODE_AGGRESSIVE = "aggressive"
CLEANUP_MODES = (
    CLEANUP_MODE_OFF,
    CLEANUP_MODE_CONSERVATIVE,
    CLEANUP_MODE_BALANCED,
    CLEANUP_MODE_AGGRESSIVE,
)
CLEANUP_OPTIONS = (
    ("Off", CLEANUP_MODE_OFF),
    ("Conservative", CLEANUP_MODE_CONSERVATIVE),
    ("Balanced", CLEANUP_MODE_BALANCED),
    ("Aggressive", CLEANUP_MODE_AGGRESSIVE),
)
CLEANUP_DISPLAY_TO_VALUE = {label: value for label, value in CLEANUP_OPTIONS}
CLEANUP_VALUE_TO_DISPLAY = {value: label for label, value in CLEANUP_OPTIONS}

VisibilityMask = tuple[tuple[bool, ...], ...] | list[list[bool]] | None


@dataclass(frozen=True)
class CleanupPreset:
    mode: str
    pre_passes: int
    min_neighbor_support: int
    max_current_support: int
    min_score_gain: int
    direct_snap_distance: float
    bridge_distance: float
    min_bridge_span: float
    island_size: int
    diagonal_passes: int


@dataclass(frozen=True)
class CleanupResult:
    labels: LabelGrid
    changed_pixels: int


_PRESETS = {
    CLEANUP_MODE_OFF: CleanupPreset(
        mode=CLEANUP_MODE_OFF,
        pre_passes=0,
        min_neighbor_support=0,
        max_current_support=0,
        min_score_gain=0,
        direct_snap_distance=0.0,
        bridge_distance=0.0,
        min_bridge_span=0.0,
        island_size=1,
        diagonal_passes=0,
    ),
    CLEANUP_MODE_CONSERVATIVE: CleanupPreset(
        mode=CLEANUP_MODE_CONSERVATIVE,
        pre_passes=1,
        min_neighbor_support=4,
        max_current_support=1,
        min_score_gain=2,
        direct_snap_distance=0.050,
        bridge_distance=0.020,
        min_bridge_span=0.100,
        island_size=1,
        diagonal_passes=0,
    ),
    CLEANUP_MODE_BALANCED: CleanupPreset(
        mode=CLEANUP_MODE_BALANCED,
        pre_passes=2,
        min_neighbor_support=3,
        max_current_support=2,
        min_score_gain=1,
        direct_snap_distance=0.085,
        bridge_distance=0.030,
        min_bridge_span=0.090,
        island_size=2,
        diagonal_passes=1,
    ),
    CLEANUP_MODE_AGGRESSIVE: CleanupPreset(
        mode=CLEANUP_MODE_AGGRESSIVE,
        pre_passes=3,
        min_neighbor_support=2,
        max_current_support=2,
        min_score_gain=1,
        direct_snap_distance=0.120,
        bridge_distance=0.045,
        min_bridge_span=0.080,
        island_size=3,
        diagonal_passes=2,
    ),
}


def normalize_cleanup_mode(value: object) -> str:
    normalized = str(value or CLEANUP_MODE_OFF).strip().lower()
    if normalized not in _PRESETS:
        return CLEANUP_MODE_OFF
    return normalized


def cleanup_pre_palette(
    labels: LabelGrid,
    mode: str,
    *,
    workspace: ColorWorkspace | None = None,
    alpha_mask: VisibilityMask = None,
) -> LabelGrid:
    return cleanup_pre_palette_detailed(labels, mode, workspace=workspace, alpha_mask=alpha_mask).labels


def cleanup_pre_palette_detailed(
    labels: LabelGrid,
    mode: str,
    *,
    workspace: ColorWorkspace | None = None,
    alpha_mask: VisibilityMask = None,
) -> CleanupResult:
    preset = _PRESETS[normalize_cleanup_mode(mode)]
    current = [row[:] for row in labels]
    if preset.pre_passes <= 0 or not current:
        return CleanupResult(labels=current, changed_pixels=0)

    color_workspace = workspace or ColorWorkspace()
    visible = _normalize_visibility_mask(alpha_mask, len(current), len(current[0]) if current else 0)
    for _pass_index in range(preset.pre_passes):
        replacements: dict[tuple[int, int], int] = {}
        for y, row in enumerate(current):
            for x, _label in enumerate(row):
                if not visible[y][x]:
                    continue
                replacement = _choose_pre_cleanup_replacement(current, visible, x, y, preset, color_workspace)
                if replacement is not None and replacement != current[y][x]:
                    replacements[(x, y)] = replacement
        if not replacements:
            break
        for (x, y), replacement in replacements.items():
            current[y][x] = replacement
    return CleanupResult(labels=current, changed_pixels=_count_visible_differences(labels, current, visible))


def cleanup_post_palette(
    labels: LabelGrid,
    mode: str,
    *,
    alpha_mask: VisibilityMask = None,
) -> LabelGrid:
    return cleanup_post_palette_detailed(labels, mode, alpha_mask=alpha_mask).labels


def cleanup_post_palette_detailed(
    labels: LabelGrid,
    mode: str,
    *,
    alpha_mask: VisibilityMask = None,
) -> CleanupResult:
    preset = _PRESETS[normalize_cleanup_mode(mode)]
    current = [row[:] for row in labels]
    if not current or preset.mode == CLEANUP_MODE_OFF:
        return CleanupResult(labels=current, changed_pixels=0)

    visible = _normalize_visibility_mask(alpha_mask, len(current), len(current[0]) if current else 0)
    if preset.island_size > 1:
        current = _remove_small_visible_islands(current, visible, min_size=preset.island_size)
    for _pass_index in range(preset.diagonal_passes):
        current, changed = _resolve_diagonal_checkerboards(current, visible)
        if changed <= 0:
            break
    return CleanupResult(labels=current, changed_pixels=_count_visible_differences(labels, current, visible))


def _choose_pre_cleanup_replacement(
    labels: LabelGrid,
    visible: list[list[bool]],
    x: int,
    y: int,
    preset: CleanupPreset,
    workspace: ColorWorkspace,
) -> int | None:
    current_label = labels[y][x]
    neighbors = _neighbor_labels(labels, visible, x, y)
    if len(neighbors) < 3:
        return None

    neighbor_counts = Counter(neighbors)
    current_support = neighbor_counts.get(current_label, 0)
    current_score = _coherence_score(labels, visible, x, y, current_label)
    candidates = [(label, count) for label, count in neighbor_counts.most_common(3) if label != current_label]
    if not candidates:
        return None

    if len(neighbor_counts) == 1:
        only_label, only_count = candidates[0]
        if current_support == 0 and only_count >= max(preset.min_neighbor_support + 1, 5):
            if _label_distance(current_label, only_label, workspace) <= preset.direct_snap_distance:
                return only_label
        return None

    bridge_pair = tuple(label for label, count in candidates[:2] if count >= max(2, preset.min_neighbor_support - 1))
    best_target: int | None = None
    best_rank: tuple[int, int, int, float] | None = None
    for candidate_label, candidate_count in candidates[:2]:
        candidate_score = _coherence_score(labels, visible, x, y, candidate_label)
        score_gain = candidate_score - current_score
        if score_gain < preset.min_score_gain:
            continue
        direct_distance = _label_distance(current_label, candidate_label, workspace)
        reason_rank = 0
        if current_support <= preset.max_current_support:
            if candidate_count >= preset.min_neighbor_support and direct_distance <= preset.direct_snap_distance:
                reason_rank = 3
            elif len(bridge_pair) == 2 and _is_bridge_colour(current_label, bridge_pair[0], bridge_pair[1], preset, workspace):
                reason_rank = 2
            elif current_support == 0 and candidate_count >= max(preset.min_neighbor_support + 1, 5):
                reason_rank = 1
        if reason_rank <= 0:
            continue
        rank = (reason_rank, score_gain, candidate_count, -direct_distance)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_target = candidate_label
    return best_target


def _neighbor_labels(labels: LabelGrid, visible: list[list[bool]], x: int, y: int) -> list[int]:
    height = len(labels)
    width = len(labels[0]) if height else 0
    neighbors: list[int] = []
    for neighbor_y in range(max(0, y - 1), min(height, y + 2)):
        for neighbor_x in range(max(0, x - 1), min(width, x + 2)):
            if neighbor_x == x and neighbor_y == y:
                continue
            if not visible[neighbor_y][neighbor_x]:
                continue
            neighbors.append(labels[neighbor_y][neighbor_x])
    return neighbors


def _coherence_score(labels: LabelGrid, visible: list[list[bool]], x: int, y: int, candidate: int) -> int:
    height = len(labels)
    width = len(labels[0]) if height else 0
    score = 0
    for delta_x, delta_y, weight in (
        (-1, 0, 2),
        (1, 0, 2),
        (0, -1, 2),
        (0, 1, 2),
        (-1, -1, 1),
        (1, -1, 1),
        (-1, 1, 1),
        (1, 1, 1),
    ):
        neighbor_x = x + delta_x
        neighbor_y = y + delta_y
        if neighbor_x < 0 or neighbor_y < 0 or neighbor_x >= width or neighbor_y >= height:
            continue
        if not visible[neighbor_y][neighbor_x]:
            continue
        if labels[neighbor_y][neighbor_x] == candidate:
            score += weight
    return score


def _is_bridge_colour(
    current_label: int,
    first_label: int,
    second_label: int,
    preset: CleanupPreset,
    workspace: ColorWorkspace,
) -> bool:
    if first_label == second_label or current_label in {first_label, second_label}:
        return False
    first_oklab = workspace.label_to_oklab(first_label)
    second_oklab = workspace.label_to_oklab(second_label)
    current_oklab = workspace.label_to_oklab(current_label)
    segment = second_oklab - first_oklab
    segment_span = float(np.linalg.norm(segment))
    if segment_span < preset.min_bridge_span:
        return False
    projection = float(np.dot(current_oklab - first_oklab, segment) / max(np.dot(segment, segment), 1e-9))
    if projection <= 0.15 or projection >= 0.85:
        return False
    nearest = first_oklab + (segment * projection)
    bridge_distance = float(np.linalg.norm(current_oklab - nearest))
    if bridge_distance > preset.bridge_distance:
        return False
    first_distance = float(np.linalg.norm(current_oklab - first_oklab))
    second_distance = float(np.linalg.norm(current_oklab - second_oklab))
    return first_distance <= segment_span * 0.95 and second_distance <= segment_span * 0.95


def _label_distance(left: int, right: int, workspace: ColorWorkspace) -> float:
    left_oklab = workspace.label_to_oklab(left)
    right_oklab = workspace.label_to_oklab(right)
    delta = left_oklab - right_oklab
    lightness = abs(float(delta[0]))
    chroma = float(np.linalg.norm(delta[1:]))
    return lightness + chroma


def _remove_small_visible_islands(labels: LabelGrid, visible: list[list[bool]], *, min_size: int) -> LabelGrid:
    current = [row[:] for row in labels]
    visible_positions = [(x, y) for y, row in enumerate(visible) for x, is_visible in enumerate(row) if is_visible]
    if not visible_positions:
        return current

    background = 0x1000000
    proxy = [
        [current[y][x] if visible[y][x] else background for x in range(len(current[0]))]
        for y in range(len(current))
    ]
    cleaned = remove_small_islands_detailed(proxy, min_size=min_size, connectivity=8).labels
    for x, y in visible_positions:
        if cleaned[y][x] != background:
            current[y][x] = cleaned[y][x]
    return current


def _resolve_diagonal_checkerboards(labels: LabelGrid, visible: list[list[bool]]) -> tuple[LabelGrid, int]:
    height = len(labels)
    width = len(labels[0]) if height else 0
    replacements: dict[tuple[int, int], int] = {}
    for y in range(height - 1):
        for x in range(width - 1):
            if not (visible[y][x] and visible[y][x + 1] and visible[y + 1][x] and visible[y + 1][x + 1]):
                continue
            top_left = labels[y][x]
            top_right = labels[y][x + 1]
            bottom_left = labels[y + 1][x]
            bottom_right = labels[y + 1][x + 1]
            if top_left != bottom_right or top_right != bottom_left or top_left == top_right:
                continue
            support = Counter()
            for sample_y in range(max(0, y - 1), min(height, y + 3)):
                for sample_x in range(max(0, x - 1), min(width, x + 3)):
                    if x <= sample_x <= x + 1 and y <= sample_y <= y + 1:
                        continue
                    if not visible[sample_y][sample_x]:
                        continue
                    support[labels[sample_y][sample_x]] += 1
            top_left_support = support.get(top_left, 0)
            top_right_support = support.get(top_right, 0)
            if abs(top_left_support - top_right_support) < 2:
                continue
            dominant = top_left if top_left_support > top_right_support else top_right
            for offset_y in (0, 1):
                for offset_x in (0, 1):
                    point_x = x + offset_x
                    point_y = y + offset_y
                    if labels[point_y][point_x] != dominant:
                        replacements[(point_x, point_y)] = dominant
    if not replacements:
        return [row[:] for row in labels], 0
    updated = [row[:] for row in labels]
    for (x, y), label in replacements.items():
        updated[y][x] = label
    return updated, len(replacements)


def _normalize_visibility_mask(alpha_mask: VisibilityMask, height: int, width: int) -> list[list[bool]]:
    if alpha_mask is None:
        return [[True] * width for _ in range(height)]
    normalized: list[list[bool]] = []
    for y in range(height):
        row = alpha_mask[y] if y < len(alpha_mask) else ()
        normalized.append([bool(row[x]) if x < len(row) else False for x in range(width)])
    return normalized


def _count_visible_differences(before: LabelGrid, after: LabelGrid, visible: list[list[bool]]) -> int:
    changed = 0
    for y, row in enumerate(before):
        for x, value in enumerate(row):
            if visible[y][x] and after[y][x] != value:
                changed += 1
    return changed
