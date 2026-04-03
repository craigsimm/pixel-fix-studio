from pathlib import Path

from PIL import Image
import pytest

from pixel_fix.gui.layers import (
    RasterLayer,
    add_layer_above_active,
    composite_layer_images,
    delete_active_layer,
    make_layer_document,
    move_active_layer_down,
    move_active_layer_up,
    next_layer_name,
    rename_active_layer,
    set_active_layer_locked,
    set_active_layer_visibility,
)
from pixel_fix.gui.processing import ProcessResult, ProcessStats
from pixel_fix.pipeline import PipelinePreparedResult


def _make_result(labels: list[list[int]], *, alpha_mask: tuple[tuple[bool, ...], ...] | None = None) -> ProcessResult:
    height = len(labels)
    width = len(labels[0]) if height else 0
    unique_count = len({value for row in labels for value in row})
    return ProcessResult(
        grid=[[((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF) for value in row] for row in labels],
        width=width,
        height=height,
        stats=ProcessStats(
            stage="downsample",
            pixel_width=1,
            resize_method="nearest",
            input_size=(width, height),
            output_size=(width, height),
            initial_color_count=unique_count,
            color_count=unique_count,
            elapsed_seconds=0.0,
        ),
        prepared_input=PipelinePreparedResult(
            reduced_labels=labels,
            pixel_width=1,
            grid_method="manual",
            input_size=(width, height),
            initial_color_count=unique_count,
        ),
        display_palette_labels=tuple(sorted({value for row in labels for value in row})),
        alpha_mask=alpha_mask,
    )


def test_layer_operations_cover_create_delete_rename_reorder_and_flags() -> None:
    base = RasterLayer(id="base", name="Layer 1", downsample_result=_make_result([[0x112233]]))
    document = make_layer_document(width=1, height=1, layers=[base], active_layer_id="base")

    created = add_layer_above_active(
        document,
        RasterLayer(id="new", name=next_layer_name(document), downsample_result=_make_result([[0x445566]])),
    )
    assert [layer.id for layer in created.layers] == ["new", "base"]
    assert created.active_layer_id == "new"

    renamed = rename_active_layer(created, "Foreground")
    assert renamed.active_layer.name == "Foreground"

    hidden = set_active_layer_visibility(renamed, False)
    assert hidden.active_layer.visible is False

    locked = set_active_layer_locked(hidden, True)
    assert locked.active_layer.locked is True

    moved_down = move_active_layer_down(locked)
    assert [layer.id for layer in moved_down.layers] == ["base", "new"]
    assert moved_down.active_layer_id == "new"

    moved_up = move_active_layer_up(moved_down)
    assert [layer.id for layer in moved_up.layers] == ["new", "base"]

    deleted = delete_active_layer(moved_up)
    assert [layer.id for layer in deleted.layers] == ["base"]
    assert deleted.active_layer_id == "base"


def test_delete_active_layer_rejects_last_layer() -> None:
    document = make_layer_document(
        width=1,
        height=1,
        layers=[RasterLayer(id="base", name="Layer 1", downsample_result=_make_result([[0x112233]]))],
        active_layer_id="base",
    )

    with pytest.raises(ValueError):
        delete_active_layer(document)


def test_composite_layer_images_uses_top_row_as_frontmost_and_skips_hidden_layers() -> None:
    top = RasterLayer(id="top", name="Top", downsample_result=_make_result([[0xFF0000]]))
    bottom = RasterLayer(id="bottom", name="Bottom", downsample_result=_make_result([[0x0000FF]]))
    document = make_layer_document(width=1, height=1, layers=[top, bottom], active_layer_id="top")

    rendered = {
        "top": Image.new("RGBA", (1, 1), (255, 0, 0, 255)),
        "bottom": Image.new("RGBA", (1, 1), (0, 0, 255, 255)),
    }

    composited = composite_layer_images(document, rendered)

    assert composited is not None
    assert composited.getpixel((0, 0)) == (255, 0, 0, 255)

    hidden_document = make_layer_document(
        width=1,
        height=1,
        layers=[RasterLayer(id="top", name="Top", downsample_result=top.downsample_result, visible=False), bottom],
        active_layer_id="top",
    )
    hidden_composite = composite_layer_images(hidden_document, rendered)
    assert hidden_composite is not None
    assert hidden_composite.getpixel((0, 0)) == (0, 0, 255, 255)
