from pixel_fix.cleanup import (
    cleanup_post_palette_detailed,
    cleanup_pre_palette_detailed,
    remove_small_islands,
)
from pixel_fix.palette.workspace import ColorWorkspace


WHITE = 0xF4F4F4
BLACK = 0x151515
MID = 0x8C8C8C
NOISE = 0xEFE9E4
BLUE = 0x3366AA


def test_remove_small_island_relabels_singletons() -> None:
    grid = [
        [1, 1, 1],
        [1, 2, 1],
        [1, 1, 1],
    ]
    out = remove_small_islands(grid, min_size=2, connectivity=8)
    assert out[1][1] == 1


def test_cleanup_pre_palette_hardens_blurry_line() -> None:
    grid = [
        [WHITE, WHITE, WHITE, WHITE, WHITE],
        [WHITE, MID, BLACK, MID, WHITE],
        [WHITE, MID, BLACK, MID, WHITE],
        [WHITE, MID, BLACK, MID, WHITE],
        [WHITE, WHITE, WHITE, WHITE, WHITE],
    ]

    cleaned = cleanup_pre_palette_detailed(grid, "balanced", workspace=ColorWorkspace())

    assert cleaned.changed_pixels >= 2
    assert all(label != MID for row in cleaned.labels for label in row)
    assert [row[2] for row in cleaned.labels[1:4]] == [BLACK, BLACK, BLACK]


def test_cleanup_pre_palette_removes_jpeg_like_speckle_without_flattening_clean_region() -> None:
    grid = [
        [WHITE, WHITE, WHITE, BLUE],
        [WHITE, NOISE, WHITE, BLUE],
        [WHITE, WHITE, WHITE, BLUE],
        [WHITE, WHITE, WHITE, BLUE],
    ]

    cleaned = cleanup_pre_palette_detailed(grid, "balanced", workspace=ColorWorkspace())

    assert cleaned.labels[1][1] == WHITE
    assert all(row[3] == BLUE for row in cleaned.labels)


def test_cleanup_pre_palette_skips_invisible_pixels() -> None:
    grid = [
        [WHITE, MID, BLACK],
        [WHITE, MID, BLACK],
        [WHITE, MID, BLACK],
    ]
    alpha_mask = (
        (True, False, True),
        (True, False, True),
        (True, False, True),
    )

    cleaned = cleanup_pre_palette_detailed(grid, "aggressive", workspace=ColorWorkspace(), alpha_mask=alpha_mask)

    assert cleaned.labels == grid
    assert cleaned.changed_pixels == 0


def test_cleanup_pre_palette_preserves_clean_pixel_art_when_off_or_conservative() -> None:
    grid = [
        [BLACK, BLACK, WHITE, WHITE],
        [BLACK, BLACK, WHITE, WHITE],
        [BLUE, BLUE, WHITE, WHITE],
        [BLUE, BLUE, WHITE, WHITE],
    ]

    off = cleanup_pre_palette_detailed(grid, "off", workspace=ColorWorkspace())
    conservative = cleanup_pre_palette_detailed(grid, "conservative", workspace=ColorWorkspace())

    assert off.labels == grid
    assert off.changed_pixels == 0
    assert conservative.labels == grid
    assert conservative.changed_pixels == 0


def test_cleanup_modes_are_monotonic_for_candidate_pixels() -> None:
    grid = [
        [WHITE, WHITE, WHITE, WHITE, WHITE],
        [WHITE, MID, BLACK, MID, WHITE],
        [WHITE, NOISE, MID, NOISE, WHITE],
        [WHITE, MID, BLACK, MID, WHITE],
        [WHITE, WHITE, WHITE, WHITE, WHITE],
    ]
    workspace = ColorWorkspace()

    conservative = cleanup_pre_palette_detailed(grid, "conservative", workspace=workspace)
    balanced = cleanup_pre_palette_detailed(grid, "balanced", workspace=workspace)
    aggressive = cleanup_pre_palette_detailed(grid, "aggressive", workspace=workspace)

    assert conservative.changed_pixels <= balanced.changed_pixels <= aggressive.changed_pixels


def test_cleanup_post_palette_removes_islands_and_checkerboards() -> None:
    grid = [
        [BLACK, BLACK, BLACK, BLACK],
        [BLACK, BLACK, WHITE, BLACK],
        [BLACK, WHITE, BLACK, BLACK],
        [BLACK, BLACK, BLACK, BLACK],
    ]

    cleaned = cleanup_post_palette_detailed(grid, "aggressive")

    assert cleaned.changed_pixels >= 2
    assert cleaned.labels[1][1] == BLACK
    assert cleaned.labels[1][2] == BLACK
    assert cleaned.labels[2][1] == BLACK
    assert cleaned.labels[2][2] == BLACK
