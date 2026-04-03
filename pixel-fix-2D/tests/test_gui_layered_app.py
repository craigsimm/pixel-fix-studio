from types import SimpleNamespace

import pixel_fix.gui.app as app_module
from pixel_fix.gui.app import PixelFixGui
from pixel_fix.gui.layers import RasterLayer, make_layer_document
from pixel_fix.gui.processing import PixelSelectionBounds, ProcessResult, ProcessStats, SelectionPayload
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


def test_composite_document_image_flattens_visible_layers_with_active_adjustments() -> None:
    gui = PixelFixGui.__new__(PixelFixGui)
    gui.transparent_colors = set()
    gui.downsample_result = _make_result([[0xFF0000]])
    gui.palette_result = None
    gui._output_display_label_adjustments = lambda _result: {}
    gui.document = make_layer_document(
        width=1,
        height=1,
        layers=[
            RasterLayer(id="top", name="Top", downsample_result=_make_result([[0xFF0000]]), visible=True),
            RasterLayer(id="bottom", name="Bottom", downsample_result=_make_result([[0x0000FF]]), visible=True),
        ],
        active_layer_id="top",
    )

    composited = PixelFixGui._composite_document_image(gui)

    assert composited is not None
    assert composited.getpixel((0, 0)) == (255, 0, 0, 255)


def test_get_sample_image_hides_active_layer_while_quick_compare_active() -> None:
    gui = PixelFixGui.__new__(PixelFixGui)
    gui.transparent_colors = set()
    gui._output_display_label_adjustments = lambda _result: {}
    gui.quick_compare_active = True
    gui.view_var = SimpleNamespace(get=lambda: "processed")
    gui.original_display_image = None
    gui.document = make_layer_document(
        width=1,
        height=1,
        layers=[
            RasterLayer(id="top", name="Top", downsample_result=_make_result([[0xFF0000]]), visible=True),
            RasterLayer(id="bottom", name="Bottom", downsample_result=_make_result([[0x0000FF]]), visible=True),
        ],
        active_layer_id="top",
    )

    sample = PixelFixGui._get_sample_image(gui)

    assert sample is not None
    assert sample.getpixel((0, 0)) == (0, 0, 255, 255)


def test_fill_bucket_region_rejects_locked_active_layer() -> None:
    gui = PixelFixGui.__new__(PixelFixGui)
    gui.process_status_var = SimpleNamespace(value="", set=lambda value: setattr(gui.process_status_var, "value", value))
    gui.downsample_result = _make_result([[0x112233]])
    gui.palette_result = None
    gui.document = make_layer_document(
        width=1,
        height=1,
        layers=[RasterLayer(id="locked", name="Locked", downsample_result=gui.downsample_result, locked=True)],
        active_layer_id="locked",
    )

    changed = PixelFixGui._fill_bucket_region(gui, 0, 0)

    assert changed is False
    assert gui.process_status_var.value == "The active layer is locked. Unlock it before editing."


def test_apply_brush_segment_updates_composite_for_active_layer_above_locked_layer() -> None:
    gui = PixelFixGui.__new__(PixelFixGui)
    gui.transparent_colors = set()
    gui._output_display_label_adjustments = lambda _result: {}
    gui.redraw_canvas = lambda: None
    gui._brush_stroke_tool_mode = "pencil"
    gui._brush_width = lambda: 1
    gui._brush_shape = lambda: "square"
    gui._selected_palette_brush_label = lambda: 0xFF0000
    gui._canvas_tool_mode_value = lambda: "pencil"
    bottom = _make_result([[0x0000FF]])
    top = _make_result([[0x000000]], alpha_mask=((True,),))
    gui.downsample_result = top
    gui.palette_result = None
    gui.document = make_layer_document(
        width=1,
        height=1,
        layers=[
            RasterLayer(id="top", name="Layer 2", downsample_result=top, visible=True),
            RasterLayer(id="bottom", name="Layer 1", downsample_result=bottom, visible=True, locked=True),
        ],
        active_layer_id="top",
    )

    PixelFixGui._refresh_output_display_images(gui)
    changed = PixelFixGui._apply_brush_segment(gui, [(0, 0)])

    assert changed == 1
    assert gui.composite_display_image is not None
    assert gui.composite_display_image.getpixel((0, 0)) == (255, 0, 0, 255)


def test_lift_current_selection_rejects_locked_active_layer() -> None:
    gui = PixelFixGui.__new__(PixelFixGui)
    gui.process_status_var = SimpleNamespace(value="", set=lambda value: setattr(gui.process_status_var, "value", value))
    gui.downsample_result = _make_result([[0x112233, 0x445566], [0x778899, 0xAABBCC]])
    gui.palette_result = None
    gui.document = make_layer_document(
        width=2,
        height=2,
        layers=[RasterLayer(id="locked", name="Locked", downsample_result=gui.downsample_result, locked=True)],
        active_layer_id="locked",
    )
    gui._image_selection = app_module.ImageSelectionState(
        mask=((True, True), (False, False)),
        bounds=PixelSelectionBounds(left=0, top=0, right=2, bottom=1),
    )
    gui._floating_selection = None

    lifted = PixelFixGui._lift_current_selection(gui)

    assert lifted is False
    assert gui._floating_selection is None
    assert gui._image_selection is not None
    assert gui.process_status_var.value == "The active layer is locked. Unlock it before editing."


def test_select_mode_does_not_drag_floating_selection_on_locked_layer() -> None:
    gui = PixelFixGui.__new__(PixelFixGui)
    gui.process_status_var = SimpleNamespace(value="", set=lambda value: setattr(gui.process_status_var, "value", value))
    gui.canvas_tool_mode = app_module.CANVAS_TOOL_MODE_SELECT
    gui.palette_add_pick_mode = False
    gui.transparency_pick_mode = False
    gui._mouse_button_action_state = None
    gui.original_display_image = object()
    gui.dragging = False
    gui.canvas = SimpleNamespace(configure=lambda **_kwargs: None)
    gui._refresh_action_states = lambda: None
    gui.redraw_canvas = lambda: None
    gui._preview_image_coordinates = lambda *_args, **_kwargs: (0, 0)
    gui._floating_selection_contains_point = lambda *_args: True
    gui._selection_contains_point = lambda *_args: False
    gui.downsample_result = _make_result([[0x112233]])
    gui.palette_result = None
    gui.document = make_layer_document(
        width=1,
        height=1,
        layers=[RasterLayer(id="locked", name="Locked", downsample_result=gui.downsample_result, locked=True)],
        active_layer_id="locked",
    )
    gui._floating_selection = app_module.FloatingSelectionState(
        payload=SelectionPayload(
            grid=[[(0x11, 0x22, 0x33)]],
            alpha_mask=((True,),),
        ),
        left=0,
        top=0,
        base_result=gui.downsample_result,
        restore_result=gui.downsample_result,
    )
    gui._selection_drag_active = False
    gui._floating_selection_drag_origin = None
    gui._floating_selection_drag_start = None

    PixelFixGui._on_canvas_press(gui, SimpleNamespace(x=0, y=0))

    assert gui._selection_drag_active is False
    assert gui._floating_selection_drag_origin is None
    assert gui.process_status_var.value == "The active layer is locked. Unlock it before editing."
