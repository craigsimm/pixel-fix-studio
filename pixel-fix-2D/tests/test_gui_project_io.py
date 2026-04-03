from pathlib import Path

from pixel_fix.gui.layers import RasterLayer, make_layer_document
from pixel_fix.gui.processing import ProcessResult, ProcessStats
from pixel_fix.gui.project_io import load_layer_project, save_layer_project
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
            stage="palette",
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


def test_project_save_and_load_round_trips_layers(tmp_path: Path) -> None:
    transparent_mask = ((True, False), (True, True))
    document = make_layer_document(
        width=2,
        height=2,
        layers=[
            RasterLayer(
                id="top",
                name="Top",
                downsample_result=_make_result([[0xFF0000, 0x00FF00], [0x0000FF, 0xFFFFFF]], alpha_mask=transparent_mask),
                palette_result=_make_result([[0xFF0000, 0x00FF00], [0x0000FF, 0xFFFFFF]], alpha_mask=transparent_mask),
                visible=True,
                locked=False,
            ),
            RasterLayer(
                id="bottom",
                name="Bottom",
                downsample_result=_make_result([[0x111111, 0x222222], [0x333333, 0x444444]]),
                visible=False,
                locked=True,
            ),
        ],
        active_layer_id="bottom",
    )

    project_path = tmp_path / "roundtrip.pfx2d"
    save_layer_project(project_path, document)

    restored = load_layer_project(project_path)

    assert restored.width == 2
    assert restored.height == 2
    assert restored.active_layer_id == "bottom"
    assert restored.project_path == project_path
    assert [layer.name for layer in restored.layers] == ["Top", "Bottom"]
    assert [layer.visible for layer in restored.layers] == [True, False]
    assert [layer.locked for layer in restored.layers] == [False, True]
    assert restored.layers[0].current_result.alpha_mask == transparent_mask
    assert restored.layers[0].current_result.grid[0][0] == (255, 0, 0)
    assert restored.layers[1].current_result.grid[1][1] == (68, 68, 68)
