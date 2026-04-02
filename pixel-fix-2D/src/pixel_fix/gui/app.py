from __future__ import annotations

import argparse
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

from pixel_fix.palette.io import load_palette, save_palette
from pixel_fix.palette.adjust import PaletteAdjustments, adjust_palette_labels, adjust_structured_palette
from pixel_fix.palette.advanced import structured_palette_from_override
from pixel_fix.palette.catalog import PaletteCatalogEntry, discover_palette_catalog
from pixel_fix.palette.color_modes import extract_unique_colors
from pixel_fix.palette.edit import generate_ramp_palette_labels, merge_palette_labels
from pixel_fix.palette.model import StructuredPalette, clone_structured_palette
from pixel_fix.palette.quantize import (
    generate_palette as generate_override_palette,
    generate_palette_source,
    is_structured_quantizer,
)
from pixel_fix.palette.sort import (
    PALETTE_SELECT_DIRECT_MODES,
    PALETTE_SELECT_HUE_MODES,
    PALETTE_SELECT_LABELS,
    PALETTE_SELECT_MODES,
    PALETTE_SELECT_SIMILARITY_NEAR_DUPLICATES,
    PALETTE_SELECT_SPECIAL_MODES,
    PALETTE_SORT_CHROMA,
    PALETTE_SORT_HUE,
    PALETTE_SORT_LABELS,
    PALETTE_SORT_LIGHTNESS,
    PALETTE_SORT_MODES,
    PALETTE_SORT_SATURATION,
    PALETTE_SORT_TEMPERATURE,
    select_palette_indices,
    sort_palette_labels,
)
from pixel_fix.palette.workspace import ColorWorkspace
from pixel_fix.pipeline import PipelineConfig, PipelinePreparedResult
from pixel_fix.resample import resize_labels, target_size_for_pixel_width

from .persist import (
    append_process_log,
    coerce_selection_threshold,
    deserialize_settings,
    diff_snapshots,
    load_app_state,
    make_process_snapshot,
    save_app_state,
    serialize_settings,
)
from .processing import (
    BRUSH_SHAPE_ROUND,
    BRUSH_SHAPE_SQUARE,
    BRUSH_WIDTH_DEFAULT,
    BRUSH_WIDTH_MAX,
    CANVAS_RESIZE_ANCHOR_BOTTOM,
    CANVAS_RESIZE_ANCHOR_BOTTOM_LEFT,
    CANVAS_RESIZE_ANCHOR_BOTTOM_RIGHT,
    CANVAS_RESIZE_ANCHOR_CENTER,
    CANVAS_RESIZE_ANCHOR_LEFT,
    CANVAS_RESIZE_ANCHOR_RIGHT,
    CANVAS_RESIZE_ANCHOR_TOP,
    CANVAS_RESIZE_ANCHOR_TOP_LEFT,
    CANVAS_RESIZE_ANCHOR_TOP_RIGHT,
    CanvasResizeSpec,
    IMAGE_FILTER_STRENGTH_DEFAULT,
    IMAGE_FILTER_STRENGTH_MAX,
    INDEXED_COLOR_DITHER_DIFFUSION,
    INDEXED_COLOR_DITHER_NONE,
    INDEXED_COLOR_FORCED_BLACK_AND_WHITE,
    INDEXED_COLOR_FORCED_NONE,
    INDEXED_COLOR_FORCED_PALETTES,
    INDEXED_COLOR_FORCED_PRIMARIES,
    INDEXED_COLOR_PALETTE_LOCAL_ADAPTIVE,
    INDEXED_COLOR_PALETTE_LOCAL_PERCEPTUAL,
    INDEXED_COLOR_PALETTE_LOCAL_SELECTIVE,
    IndexedColorProcessResult,
    IndexedColorSettings,
    OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_BRIGHT,
    OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK,
    OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT,
    PixelSelectionBounds,
    ProcessResult,
    ProcessStats,
    RGBGrid,
    SelectionPayload,
    add_exterior_outline,
    apply_blur,
    apply_bucket_fill,
    apply_cut_selection,
    apply_delete_selection,
    apply_eraser_operation,
    apply_eraser_operations,
    apply_ellipse_operation,
    apply_flip_horizontal,
    apply_flip_vertical,
    apply_line_operation,
    apply_pencil_operation,
    apply_pencil_operations,
    apply_rectangle_operation,
    apply_rotate,
    apply_sharpen,
    apply_transparency_fill,
    brush_footprint,
    composite_selection_payload,
    display_resize_method,
    downsample_image,
    extract_selection_payload,
    flip_selection_payload_horizontal,
    flip_selection_payload_vertical,
    grid_to_pil_image,
    image_to_rgb_grid,
    labels_to_rgb,
    load_png_rgba_image,
    process_result_from_original,
    process_result_to_rgba_image,
    rasterize_polygon_selection_mask,
    rasterize_rectangle_selection_mask,
    reduce_indexed_color,
    remove_exterior_outline,
    reduce_palette_image,
    rotate_selection_payload,
    resize_canvas_result,
    selection_mask_bounds,
    rgb_to_labels,
)
from .ai_image_generate import generate_image_png_bytes_with_auto_install
from .ai_image_models import coerce_selected_model, get_model_option, models_for_keys
from .state import PreviewSettings, SettingsSession
from .theme import (
    APP_ACCENT,
    APP_BG,
    APP_BORDER,
    APP_HOVER_BG,
    HEADER_FONT_FAMILY,
    HEADER_FONT_SIZE,
    APP_MUTED_TEXT,
    APP_SURFACE_BG,
    APP_TEXT,
    PIXEL_FONT_FAMILY,
    UI_FONT_SIZE,
    load_font_family,
)
from .tooltips import Tooltip
from .zoom import ZOOM_PRESETS, choose_fit_zoom, clamp_zoom, zoom_in, zoom_out

OPEN_HAND_CURSOR = "hand2"
CLOSED_HAND_CURSOR = "fleur"
MAX_PALETTE_SWATCHES = 1024
PALETTE_SWATCH_SIZE = 18
PALETTE_SWATCH_COLOUR_SIZE = 16
PALETTE_SWATCH_GAP = 0
PALETTE_COLUMN_CONTENT_PADDING = 6
PALETTE_ACTION_GAP = 3
PALETTE_ACTION_ICON_BUTTON_SIZE = 26
PALETTE_ACTION_ICON_OFFSET = (-2, -2)
PALETTE_BROWSER_WIDTH = 320
PALETTE_BROWSER_HEIGHT = 360
PALETTE_BROWSER_MARGIN = 12
PALETTE_BROWSER_GAP = 8
PALETTE_BROWSER_SWATCH_STRIP_COUNT = 8
PALETTE_BROWSER_SWATCH_STRIP_SIZE = 8
NEW_IMAGE_WINDOW_WIDTH = 360
NEW_IMAGE_DEFAULT_SIZE = 256
NEW_IMAGE_LOCK_BUTTON_SIZE = 21
NEW_IMAGE_LOCK_ICON_SIZE = 17
CANVAS_SIZE_WINDOW_WIDTH = 340
CANVAS_SIZE_WINDOW_HEIGHT = 270
INDEXED_COLOR_WINDOW_WIDTH = 360
INDEXED_COLOR_WINDOW_HEIGHT = 270
PREFERENCES_WINDOW_WIDTH = 620
PREFERENCES_WINDOW_HEIGHT = 480
PREFERENCES_NAV_WIDTH = 172
PREFERENCES_PAGE_GENERAL = "General"
PREFERENCES_PAGE_RESIZE = "Resize Method"
PREFERENCES_PAGE_PALETTE_REDUCTION = "Palette Reduction Method"
PREFERENCES_PAGE_COLOUR_RAMP = "Colour Ramp"
PREFERENCES_PAGE_DITHERING = "Dithering Method"
PREFERENCES_PAGE_SELECTION_THRESHOLD = "Selection Threshold"
PREFERENCES_PAGE_MOUSE_BUTTONS = "Mouse Buttons"
PREFERENCES_PAGE_AI_IMAGE = "AI Image"
PREFERENCES_PAGE_ORDER = (
    PREFERENCES_PAGE_GENERAL,
    PREFERENCES_PAGE_RESIZE,
    PREFERENCES_PAGE_PALETTE_REDUCTION,
    PREFERENCES_PAGE_COLOUR_RAMP,
    PREFERENCES_PAGE_DITHERING,
    PREFERENCES_PAGE_SELECTION_THRESHOLD,
    PREFERENCES_PAGE_MOUSE_BUTTONS,
    PREFERENCES_PAGE_AI_IMAGE,
)
OVERLAY_GRID_COLOUR = "#3F4444"
SECTION_CONTENT_PADDING = 8
TOOL_BUTTON_PADDING = (0, 0)
TOOL_BUTTON_WIDTH = 40
TOOL_BUTTON_HEIGHT = 40
TOOLS_SIDEBAR_WIDTH = 252
TOOLS_SIDEBAR_WRAP_LENGTH = 220
PALETTE_COLUMN_DEFAULT_WIDTH = 184
PALETTE_COLUMN_MIN_WIDTH = 172
PALETTE_COLUMN_WIDTH_RATIO = 0.115
ACTIVE_COLOR_SLOT_PRIMARY = "primary"
ACTIVE_COLOR_SLOT_SECONDARY = "secondary"
ACTIVE_COLOR_DEFAULT_LABEL = 0xFFFFFF
ACTIVE_COLOR_BACK_BOUNDS = (2, 2, 17, 17)
ACTIVE_COLOR_FRONT_BOUNDS = (12, 12, 27, 27)
ACTIVE_COLOR_PREVIEW_PLACEHOLDER_FRONT = (0, 255, 0, 255)
ACTIVE_COLOR_PREVIEW_PLACEHOLDER_BACK = (0, 255, 255, 255)
ACTIVE_COLOR_PREVIEW_TEMPLATE_NONE = "current_no_transparent.png"
NEW_IMAGE_BACKGROUND_TRANSPARENT = "transparent"
NEW_IMAGE_BACKGROUND_BLACK = "black"
NEW_IMAGE_BACKGROUND_WHITE = "white"
NEW_IMAGE_BACKGROUND_OPTIONS = (
    ("Transparent", NEW_IMAGE_BACKGROUND_TRANSPARENT),
    ("Black", NEW_IMAGE_BACKGROUND_BLACK),
    ("White", NEW_IMAGE_BACKGROUND_WHITE),
)
NEW_IMAGE_BACKGROUND_DISPLAY_TO_VALUE = {label: value for label, value in NEW_IMAGE_BACKGROUND_OPTIONS}
NEW_IMAGE_BACKGROUND_VALUE_TO_DISPLAY = {value: label for label, value in NEW_IMAGE_BACKGROUND_OPTIONS}
ACTIVE_COLOR_PREVIEW_TEMPLATE_FRONT_TRANSPARENT = "current_transparent_primary.png"
ACTIVE_COLOR_PREVIEW_TEMPLATE_BACK_TRANSPARENT = "current_transparent_secondary.png"
DEFAULT_PALETTE_RESOURCE = "palettes/default.gpl"
MAX_RECENT_FILES = 10
MAX_KEY_COLORS = 24
SELECTION_THRESHOLD_OPTIONS = tuple(range(10, 101, 10))
PALETTE_SORT_OPTIONS = (
    (PALETTE_SORT_LABELS[PALETTE_SORT_LIGHTNESS], PALETTE_SORT_LIGHTNESS),
    (PALETTE_SORT_LABELS[PALETTE_SORT_HUE], PALETTE_SORT_HUE),
    (PALETTE_SORT_LABELS[PALETTE_SORT_SATURATION], PALETTE_SORT_SATURATION),
    (PALETTE_SORT_LABELS[PALETTE_SORT_CHROMA], PALETTE_SORT_CHROMA),
    (PALETTE_SORT_LABELS[PALETTE_SORT_TEMPERATURE], PALETTE_SORT_TEMPERATURE),
)
PALETTE_SELECT_OPTIONS = tuple((PALETTE_SELECT_LABELS[mode], mode) for mode in PALETTE_SELECT_DIRECT_MODES)
PALETTE_SELECT_HUE_OPTIONS = tuple((PALETTE_SELECT_LABELS[mode].removeprefix("Hue (").removesuffix(")"), mode) for mode in PALETTE_SELECT_HUE_MODES)
PALETTE_SELECT_SPECIAL_OPTIONS = tuple((PALETTE_SELECT_LABELS[mode], mode) for mode in PALETTE_SELECT_SPECIAL_MODES)

RESIZE_OPTIONS = (
    ("Nearest Neighbor", "nearest"),
    ("Bilinear Interpolation", "bilinear"),
    ("RotSprite", "rotsprite"),
)
QUANTIZER_OPTIONS = (
    ("Median Cut", "median-cut"),
    ("K-Means Clustering", "kmeans"),
    ("RampForge-8", "rampforge-8"),
)
DITHER_OPTIONS = (
    ("None", "none"),
    ("Ordered (Bayer)", "ordered"),
    ("Blue Noise", "blue-noise"),
)
GENERATED_SHADES_OPTIONS = (2, 4, 6, 8, 10)
RAMP_CONTRAST_OPTIONS = tuple(range(10, 101, 10))
COLOR_MODE_OPTIONS = (
    ("RGBA", "rgba"),
    ("Indexed", "indexed"),
    ("Grayscale", "grayscale"),
)

RESIZE_DISPLAY_TO_VALUE = {label: value for (label, value) in RESIZE_OPTIONS}
RESIZE_VALUE_TO_DISPLAY = {value: label for (label, value) in RESIZE_OPTIONS}
QUANTIZER_DISPLAY_TO_VALUE = {label: value for (label, value) in QUANTIZER_OPTIONS}
QUANTIZER_VALUE_TO_DISPLAY = {value: label for (label, value) in QUANTIZER_OPTIONS}
DITHER_DISPLAY_TO_VALUE = {label: value for (label, value) in DITHER_OPTIONS}
DITHER_VALUE_TO_DISPLAY = {value: label for (label, value) in DITHER_OPTIONS}
COLOR_MODE_DISPLAY_TO_VALUE = {label: value for (label, value) in COLOR_MODE_OPTIONS}
COLOR_MODE_VALUE_TO_DISPLAY = {value: label for (label, value) in COLOR_MODE_OPTIONS}
INDEXED_COLOR_PALETTE_OPTIONS = (
    ("Local (Perceptual)", INDEXED_COLOR_PALETTE_LOCAL_PERCEPTUAL),
    ("Local (Selective)", INDEXED_COLOR_PALETTE_LOCAL_SELECTIVE),
    ("Local (Adaptive)", INDEXED_COLOR_PALETTE_LOCAL_ADAPTIVE),
)
INDEXED_COLOR_FORCED_OPTIONS = (
    ("None", INDEXED_COLOR_FORCED_NONE),
    ("Black and White", INDEXED_COLOR_FORCED_BLACK_AND_WHITE),
    ("Primaries", INDEXED_COLOR_FORCED_PRIMARIES),
)
INDEXED_COLOR_DITHER_OPTIONS = (
    ("None", INDEXED_COLOR_DITHER_NONE),
    ("Diffusion", INDEXED_COLOR_DITHER_DIFFUSION),
)
INDEXED_COLOR_PALETTE_DISPLAY_TO_VALUE = {label: value for (label, value) in INDEXED_COLOR_PALETTE_OPTIONS}
INDEXED_COLOR_PALETTE_VALUE_TO_DISPLAY = {value: label for (label, value) in INDEXED_COLOR_PALETTE_OPTIONS}
INDEXED_COLOR_FORCED_DISPLAY_TO_VALUE = {label: value for (label, value) in INDEXED_COLOR_FORCED_OPTIONS}
INDEXED_COLOR_FORCED_VALUE_TO_DISPLAY = {value: label for (label, value) in INDEXED_COLOR_FORCED_OPTIONS}
INDEXED_COLOR_DITHER_DISPLAY_TO_VALUE = {label: value for (label, value) in INDEXED_COLOR_DITHER_OPTIONS}
INDEXED_COLOR_DITHER_VALUE_TO_DISPLAY = {value: label for (label, value) in INDEXED_COLOR_DITHER_OPTIONS}
OUTLINE_COLOUR_MODE_PALETTE = "palette"
OUTLINE_COLOUR_MODE_ADAPTIVE = "adaptive"
OUTLINE_ADAPTIVE_DARKEN_DEFAULT = 60
OUTLINE_COLOUR_MODE_LABELS = {
    OUTLINE_COLOUR_MODE_PALETTE: "Selected",
    OUTLINE_COLOUR_MODE_ADAPTIVE: "Adaptive",
}
CANVAS_TOOL_MODE_PALETTE_PICK = "palette-pick"
CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK = "active-color-pick"
CANVAS_TOOL_MODE_TRANSPARENCY_PICK = "transparency-pick"
CANVAS_TOOL_MODE_BUCKET = "bucket"
CANVAS_TOOL_MODE_PENCIL = "pencil"
CANVAS_TOOL_MODE_ERASER = "eraser"
CANVAS_TOOL_MODE_ELLIPSE = "ellipse"
CANVAS_TOOL_MODE_RECTANGLE = "rectangle"
CANVAS_TOOL_MODE_LINE = "line"
CANVAS_TOOL_MODE_SELECT = "select"
CANVAS_TOOL_MODE_POLYGON_LASSO = "polygon-lasso"
_LASSO_CLOSE_RADIUS_PX = 8
CANVAS_TOOL_MODE_GRADIENT = "gradient"
CANVAS_TOOL_MODE_BLUR = "blur"
CANVAS_TOOL_MODE_SHARPEN = "sharpen"
CANVAS_TOOL_MODE_ROTATE = "rotate"
CANVAS_TOOL_MODE_ADD_OUTLINE = "add-outline"
CANVAS_TOOL_MODE_REMOVE_OUTLINE = "remove-outline"
MOUSE_BUTTON_ACTION_VIEW_ORIGINAL = "view-original"
MOUSE_BUTTON_ACTION_SAMPLE_COLOR = "sample-color"
MOUSE_BUTTON_ACTION_SWAP_COLORS = "swap-colors"
MOUSE_BUTTON_ACTION_ERASER = "eraser"
MOUSE_BUTTON_ACTION_OPTIONS = (
    ("View Original", MOUSE_BUTTON_ACTION_VIEW_ORIGINAL),
    ("Sample Color", MOUSE_BUTTON_ACTION_SAMPLE_COLOR),
    ("Swap Colors", MOUSE_BUTTON_ACTION_SWAP_COLORS),
    ("Eraser", MOUSE_BUTTON_ACTION_ERASER),
)
MOUSE_BUTTON_ACTION_VALUES = {value for _, value in MOUSE_BUTTON_ACTION_OPTIONS}
MOUSE_BUTTON_DEFAULT_RIGHT_ACTION = MOUSE_BUTTON_ACTION_VIEW_ORIGINAL
MOUSE_BUTTON_DEFAULT_MIDDLE_ACTION = MOUSE_BUTTON_ACTION_SAMPLE_COLOR
CANVAS_MOUSE_BUTTON_MIDDLE = 2
CANVAS_MOUSE_BUTTON_RIGHT = 3
OUTLINE_REMOVE_DIRECTION_LABELS = {
    OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK: "Dark",
    OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_BRIGHT: "Bright",
}
CANVAS_RESIZE_DIMENSION_MIN = 1
CANVAS_RESIZE_DIMENSION_MAX = 4096
CANVAS_RESIZE_ANCHOR_LABELS = {
    CANVAS_RESIZE_ANCHOR_TOP_LEFT: "top-left",
    CANVAS_RESIZE_ANCHOR_TOP: "top",
    CANVAS_RESIZE_ANCHOR_TOP_RIGHT: "top-right",
    CANVAS_RESIZE_ANCHOR_LEFT: "left",
    CANVAS_RESIZE_ANCHOR_CENTER: "center",
    CANVAS_RESIZE_ANCHOR_RIGHT: "right",
    CANVAS_RESIZE_ANCHOR_BOTTOM_LEFT: "bottom-left",
    CANVAS_RESIZE_ANCHOR_BOTTOM: "bottom",
    CANVAS_RESIZE_ANCHOR_BOTTOM_RIGHT: "bottom-right",
}
EVENT_STATE_SHIFT_MASK = 0x0001
EVENT_STATE_CONTROL_MASK = 0x0004
ROTATE_DIRECTION_90_CW = "90-cw"
ROTATE_DIRECTION_180 = "180"
ROTATE_DIRECTION_90_CCW = "90-ccw"
ROTATE_DIRECTION_LABELS = {
    ROTATE_DIRECTION_90_CW: "90° CW",
    ROTATE_DIRECTION_180: "180°",
    ROTATE_DIRECTION_90_CCW: "90° CCW",
}
ROTATE_DIRECTION_TO_TURNS = {
    ROTATE_DIRECTION_90_CW: 1,
    ROTATE_DIRECTION_180: 2,
    ROTATE_DIRECTION_90_CCW: 3,
}


@dataclass
class CanvasDisplay:
    image_left: int
    image_top: int
    display_width: int
    display_height: int
    sample_image: Image.Image | None


@dataclass
class PaletteUndoState:
    palette_result: ProcessResult | None
    downsample_display_image: Image.Image | None
    palette_display_image: Image.Image | None
    image_state: str
    last_successful_process_snapshot: dict[str, object] | None
    active_palette: list[int] | None
    active_palette_source: str
    active_palette_path: str | None
    advanced_palette_preview: StructuredPalette | None
    transparent_colors: tuple[int, ...]
    settings: PreviewSettings
    downsample_result: ProcessResult | None = None
    palette_sort_reset_labels: tuple[int, ...] = ()
    palette_sort_reset_source: str | None = None
    palette_sort_reset_path: str | None = None


@dataclass
class CanvasMouseActionState:
    button: int
    action: str


@dataclass(frozen=True)
class ImageSelectionState:
    mask: tuple[tuple[bool, ...], ...]
    bounds: PixelSelectionBounds
    outline_points: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class FloatingSelectionState:
    payload: SelectionPayload
    left: int
    top: int
    base_result: ProcessResult
    restore_result: ProcessResult
    source_bounds: PixelSelectionBounds | None = None


@dataclass(frozen=True)
class ClipboardSelectionState:
    payload: SelectionPayload
    bounds: PixelSelectionBounds | None = None


@dataclass(frozen=True)
class PreferencesDialogState:
    settings: PreviewSettings
    checkerboard: bool
    overlay_grid: bool
    selection_threshold: int
    right_mouse_action: str
    middle_mouse_action: str
    openai_api_key: str
    gemini_api_key: str
    image_generation_model: str


@dataclass(frozen=True)
class IndexedColorDialogSnapshot:
    palette_state: PaletteUndoState
    source_result: ProcessResult
    view_value: str
    quick_compare_active: bool
    status_text: str


@dataclass(frozen=True)
class CanvasSizeDialogState:
    width: int
    height: int
    anchor: str


class PixelFixGui:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pixel-Fix")
        self.root.geometry("1660x920")
        self._configure_window_icon()
        self._configure_theme()

        persisted = load_app_state()
        persisted_settings = deserialize_settings(persisted.get("settings"))
        self.session = SettingsSession(
            replace(
                persisted_settings,
                palette_brightness=0,
                palette_contrast=100,
                palette_hue=0,
                palette_saturation=100,
            )
        )
        self.source_path: Path | None = None
        self.original_grid: RGBGrid | None = None
        self.original_display_image: Image.Image | None = None
        self.downsample_result: ProcessResult | None = None
        self.palette_result: ProcessResult | None = None
        self.downsample_display_image: Image.Image | None = None
        self.palette_display_image: Image.Image | None = None
        self.comparison_original_image: Image.Image | None = None
        self._comparison_original_key: tuple[object, ...] | None = None
        self.prepared_input_cache = None
        self.prepared_input_cache_key: tuple[object, ...] | None = None
        self.workspace = ColorWorkspace()
        self.active_palette: list[int] | None = None
        self.active_palette_source = ""
        self.active_palette_path: str | None = None
        self.transparent_colors: set[int] = set()
        self.advanced_palette_preview: StructuredPalette | None = None
        self.canvas_tool_mode: str | None = None
        self.palette_add_pick_mode = False
        self.transparency_pick_mode = False
        self._brush_stroke_active = False
        self._brush_stroke_last_point: tuple[int, int] | None = None
        self._brush_stroke_changed_pixels = 0
        self._brush_stroke_tool_mode: str | None = None
        self._shape_drag_active = False
        self._shape_preview_anchor: tuple[int, int] | None = None
        self._shape_preview_current: tuple[int, int] | None = None
        self._shape_preview_tool_mode: str | None = None
        self._shape_preview_constrained = False
        self._mouse_button_action_state: CanvasMouseActionState | None = None
        self._palette_selection_indices: set[int] = set()
        self._palette_selection_anchor_index: int | None = None
        self._palette_ctrl_drag_active = False
        self._palette_ctrl_drag_anchor_index: int | None = None
        self._palette_ctrl_drag_indices: set[int] = set()
        self._palette_ctrl_drag_initial_selection: set[int] = set()
        self._palette_hit_regions: list[tuple[int, int, int, int]] = []
        self._displayed_palette: list[int] = []
        self._adjusted_palette_cache_key: tuple[object, ...] | None = None
        self._adjusted_palette_cache: StructuredPalette | None = None
        self._palette_sort_reset_labels: list[int] | None = None
        self._palette_sort_reset_source: str | None = None
        self._palette_sort_reset_path: str | None = None
        self.builtin_palette_entries = discover_palette_catalog(self._resource_path("palettes"))
        self._builtin_palette_by_path = {str(entry.path): entry for entry in self.builtin_palette_entries}
        self._builtin_palette_preview_entry: PaletteCatalogEntry | None = None
        self.last_output_path = persisted.get("last_output_path")
        self.last_successful_process_snapshot = persisted.get("last_successful_process_snapshot")
        self.recent_files = self._normalize_recent_files(persisted.get("recent_files"))
        self.openai_api_key = str(persisted.get("openai_api_key", "") or "")
        self.gemini_api_key = str(persisted.get("gemini_api_key", "") or "")
        self.image_generation_model = str(persisted.get("image_generation_model", "") or "")
        self.image_generation_model = coerce_selected_model(
            self.image_generation_model,
            openai_key=self.openai_api_key,
            gemini_key=self.gemini_api_key,
        )
        self.image_state = "loaded_original"

        self.zoom = clamp_zoom(int(persisted.get("zoom", 100)))
        self.pan_x = 0
        self.pan_y = 0
        self.dragging = False
        self.drag_origin = (0, 0)
        self.drag_pan_start = (0, 0)
        self.quick_compare_active = False
        self._display_context: CanvasDisplay | None = None
        self._image_ref: ImageTk.PhotoImage | None = None
        self._tool_button_icons: dict[tuple[str, bool], ImageTk.PhotoImage] = {}
        self._tool_button_assets: dict[str, str] = {}
        self._tool_button_enabled: dict[str, bool] = {}
        self._tool_button_frames: dict[str, tk.Frame] = {}
        self._palette_action_button_icons: dict[tuple[str, bool], ImageTk.PhotoImage] = {}
        self._palette_action_button_assets: dict[str, str] = {}
        self._palette_action_button_enabled: dict[str, bool] = {}
        self._active_color_preview_templates: dict[str, Image.Image] = {}
        self._active_color_preview_image_ref: ImageTk.PhotoImage | None = None
        self._pick_preview_sample: tuple[int, int, int] | None = None
        self._image_selection: ImageSelectionState | None = None
        self._floating_selection: FloatingSelectionState | None = None
        self._selection_clipboard: ClipboardSelectionState | None = None
        self._selection_drag_active = False
        self._selection_drag_anchor: tuple[int, int] | None = None
        self._selection_drag_current: tuple[int, int] | None = None
        self._floating_selection_drag_origin: tuple[int, int] | None = None
        self._floating_selection_drag_start: tuple[int, int] | None = None
        self._lasso_points: list[tuple[int, int]] = []
        self._lasso_hover_point: tuple[int, int] | None = None
        self._palette_browser_window: tk.Toplevel | None = None
        self._palette_browser_search_var = tk.StringVar(value="")
        self._palette_browser_displayed_entries: list[PaletteCatalogEntry] = []
        self._palette_browser_root_bind_ids: dict[str, str] = {}
        self._palette_browser_empty_label: tk.Widget | None = None
        self._palette_browser_search_trace_id: str | None = None
        self._preferences_window: tk.Toplevel | None = None
        self._preferences_nav_buttons: dict[str, ttk.Button] = {}
        self._preferences_pages: dict[str, tk.Widget] = {}
        self._preferences_selected_page = PREFERENCES_PAGE_GENERAL
        self._preferences_original_state: PreferencesDialogState | None = None
        self._preferences_checkerboard_var: tk.BooleanVar | None = None
        self._preferences_overlay_grid_var: tk.BooleanVar | None = None
        self._preferences_downsample_mode_var: tk.StringVar | None = None
        self._preferences_quantizer_var: tk.StringVar | None = None
        self._preferences_generated_shades_var: tk.StringVar | None = None
        self._preferences_contrast_bias_var: tk.DoubleVar | None = None
        self._preferences_palette_dither_var: tk.StringVar | None = None
        self._preferences_selection_threshold_var: tk.IntVar | None = None
        self._preferences_right_mouse_action_var: tk.StringVar | None = None
        self._preferences_middle_mouse_action_var: tk.StringVar | None = None
        self._preferences_openai_key_var: tk.StringVar | None = None
        self._preferences_gemini_key_var: tk.StringVar | None = None
        self._preferences_ai_model_id_var: tk.StringVar | None = None
        self._preferences_ai_model_combobox: ttk.Combobox | None = None
        self._preferences_ai_model_hint_label: ttk.Label | None = None
        self._preferences_openai_key_trace_id: str | None = None
        self._preferences_gemini_key_trace_id: str | None = None
        self._ai_generate_window: tk.Toplevel | None = None
        self._ai_generate_cancel_event: threading.Event | None = None
        self._new_image_window: tk.Toplevel | None = None
        self._new_image_width_var: tk.StringVar | None = None
        self._new_image_height_var: tk.StringVar | None = None
        self._new_image_locked_var: tk.BooleanVar | None = None
        self._new_image_background_var: tk.StringVar | None = None
        self._new_image_width_trace_id: str | None = None
        self._new_image_height_trace_id: str | None = None
        self._new_image_lock_button: tk.Button | None = None
        self._new_image_lock_icons: dict[bool, ImageTk.PhotoImage] = {}
        self._new_image_syncing_dimensions = False
        self._canvas_size_window: tk.Toplevel | None = None
        self._canvas_size_width_var: tk.StringVar | None = None
        self._canvas_size_height_var: tk.StringVar | None = None
        self._canvas_size_anchor_var: tk.StringVar | None = None
        self._canvas_size_locked_var: tk.BooleanVar | None = None
        self._canvas_size_width_trace_id: str | None = None
        self._canvas_size_height_trace_id: str | None = None
        self._canvas_size_lock_button: tk.Button | None = None
        self._canvas_size_syncing_dimensions = False
        self._indexed_color_window: tk.Toplevel | None = None
        self._indexed_color_snapshot: IndexedColorDialogSnapshot | None = None
        self._indexed_color_last_settings = IndexedColorSettings()
        self._indexed_color_preview_after_id: str | None = None
        self._indexed_color_preview_request_id = 0
        self._indexed_color_preview_result: IndexedColorProcessResult | None = None
        self._indexed_color_preview_result_key: tuple[object, ...] | None = None
        self._indexed_color_syncing_controls = False
        self._indexed_color_palette_var: tk.StringVar | None = None
        self._indexed_color_colors_var: tk.IntVar | None = None
        self._indexed_color_forced_var: tk.StringVar | None = None
        self._indexed_color_dither_var: tk.StringVar | None = None
        self._indexed_color_amount_var: tk.IntVar | None = None
        self._indexed_color_preview_var: tk.BooleanVar | None = None
        self._indexed_color_amount_spinbox: ttk.Spinbox | None = None
        self._indexed_color_ok_button: ttk.Button | None = None
        self._tooltips: list[Tooltip] = []
        self._persist_after_id: str | None = None
        self._suspend_control_events = False
        self._palette_undo_state: PaletteUndoState | None = None
        self._palette_redo_state: PaletteUndoState | None = None
        primary_label, secondary_label, transparent_slot, active_slot = self._initial_active_color_state(persisted)
        self.primary_color_label = primary_label
        self.secondary_color_label = secondary_label
        self.transparent_color_slot = transparent_slot
        self.active_color_slot = active_slot

        self.view_var = tk.StringVar(value=str(persisted.get("view_mode", "original")))
        if self.view_var.get() not in {"original", "processed"}:
            self.view_var.set("original")
        self.selection_threshold_var = tk.IntVar(value=coerce_selection_threshold(persisted.get("selection_threshold", 30)))
        self.pixel_width_var = tk.IntVar()
        self.downsample_mode_var = tk.StringVar()
        self.palette_reduction_colors_var = tk.IntVar()
        self.generated_shades_var = tk.StringVar()
        self.auto_detect_count_var = tk.StringVar()
        self.contrast_bias_var = tk.DoubleVar()
        self.palette_brightness_var = tk.IntVar()
        self.palette_contrast_var = tk.IntVar()
        self.palette_hue_var = tk.IntVar()
        self.palette_saturation_var = tk.IntVar()
        self.palette_dither_var = tk.StringVar()
        self.input_mode_var = tk.StringVar()
        self.output_mode_var = tk.StringVar()
        self.quantizer_var = tk.StringVar()
        self.dither_var = tk.StringVar()
        self.checkerboard_var = tk.BooleanVar(value=bool(persisted.get("checkerboard", False)))
        self.overlay_grid_var = tk.BooleanVar(value=bool(persisted.get("overlay_grid", False)))
        self.right_mouse_action_var = tk.StringVar(
            value=self._coerce_mouse_button_action(
                persisted.get("right_mouse_action"),
                default=MOUSE_BUTTON_DEFAULT_RIGHT_ACTION,
            )
        )
        self.middle_mouse_action_var = tk.StringVar(
            value=self._coerce_mouse_button_action(
                persisted.get("middle_mouse_action"),
                default=MOUSE_BUTTON_DEFAULT_MIDDLE_ACTION,
            )
        )
        self.outline_pixel_perfect_var = tk.BooleanVar(value=bool(persisted.get("outline_pixel_perfect", True)))
        self.outline_colour_mode_var = tk.StringVar(value=self._initial_outline_colour_mode(persisted))
        self.outline_colour_mode_display_var = tk.StringVar(
            value=OUTLINE_COLOUR_MODE_LABELS[self._initial_outline_colour_mode(persisted)]
        )
        self.outline_adaptive_darken_percent_var = tk.IntVar(
            value=self._coerce_outline_adaptive_darken_percent(persisted.get("outline_adaptive_darken_percent", OUTLINE_ADAPTIVE_DARKEN_DEFAULT))
        )
        self.outline_add_generated_colours_var = tk.BooleanVar(value=bool(persisted.get("outline_add_generated_colours", False)))
        self.outline_remove_brightness_threshold_enabled_var = tk.BooleanVar(
            value=bool(persisted.get("outline_remove_brightness_threshold_enabled", False))
        )
        self.outline_remove_brightness_threshold_percent_var = tk.IntVar(
            value=self._coerce_outline_remove_brightness_threshold_percent(
                persisted.get("outline_remove_brightness_threshold_percent", OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT)
            )
        )
        self.outline_remove_brightness_threshold_direction_var = tk.StringVar(
            value=self._coerce_outline_remove_brightness_direction(
                persisted.get("outline_remove_brightness_threshold_direction", OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK)
            )
        )
        self.outline_remove_brightness_direction_display_var = tk.StringVar(
            value=OUTLINE_REMOVE_DIRECTION_LABELS[
                self._coerce_outline_remove_brightness_direction(
                    persisted.get("outline_remove_brightness_threshold_direction", OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK)
                )
            ]
        )
        self.brush_width_var = tk.IntVar(value=self._coerce_brush_width(persisted.get("brush_width", BRUSH_WIDTH_DEFAULT)))
        self.brush_shape_var = tk.StringVar(value=self._coerce_brush_shape(persisted.get("brush_shape", BRUSH_SHAPE_SQUARE)).title())
        self.blur_strength_var = tk.IntVar(
            value=self._coerce_image_filter_strength(persisted.get("blur_strength", IMAGE_FILTER_STRENGTH_DEFAULT))
        )
        self.sharpen_strength_var = tk.IntVar(
            value=self._coerce_image_filter_strength(persisted.get("sharpen_strength", IMAGE_FILTER_STRENGTH_DEFAULT))
        )
        self.image_filter_strength_var = tk.IntVar(value=self.blur_strength_var.get())
        self.rotate_direction_var = tk.StringVar(value=ROTATE_DIRECTION_90_CW)
        self.rotate_direction_display_var = tk.StringVar(value=ROTATE_DIRECTION_LABELS[ROTATE_DIRECTION_90_CW])
        self.process_status_var = tk.StringVar(value="Open a PNG image to begin.")
        self.scale_info_var = tk.StringVar(value="Open an image to set the pixel size.")
        self.palette_info_var = tk.StringVar(value="Palette: none")
        self.image_info_var = tk.StringVar(value="No image  -  100%")
        self.pick_preview_var = tk.StringVar(value="")
        self.pick_preview_rgb_var = tk.StringVar(value="")
        self.pick_preview_position_var = tk.StringVar(value="")
        self.options_helper_var = tk.StringVar(value="Select a tool to see its options.")
        self.palette_brightness_value_var = tk.StringVar(value="0%")
        self.palette_contrast_value_var = tk.StringVar(value="0%")
        self.palette_hue_value_var = tk.StringVar(value="0%")
        self.palette_saturation_value_var = tk.StringVar(value="0%")
        self.palette_dropdown_var = tk.StringVar(value="Built-in palettes")
        self.toolbar_zoom_var = tk.StringVar(value=f"{self.zoom}%")

        self._menu_items: dict[str, tk.Menu] = {}
        self._build_menu_bar()
        self._build_top_toolbar()
        self._build_layout()
        if not self._restore_active_palette(persisted):
            self._load_default_palette()
        self._sync_controls_from_settings(self.session.current)
        self._update_scale_info()
        self._update_palette_strip()
        self._refresh_active_color_preview()
        self._update_image_info()
        self._refresh_action_states()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_window_icon(self) -> None:
        ico_path = self._resource_path("icons/pixel-fix-studio.ico")
        if ico_path.exists():
            try:
                self.root.iconbitmap(default=str(ico_path))
            except tk.TclError:
                pass
        icon_path = self._resource_path("icons/pixel-fix-2D-32px.png")
        if icon_path.exists():
            try:
                self.root.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
            except tk.TclError:
                pass

    @staticmethod
    def _resource_path(name: str) -> Path:
        if hasattr(sys, "_MEIPASS"):
            return Path(getattr(sys, "_MEIPASS")) / "pixel_fix" / "resources" / name
        return Path(__file__).resolve().parents[1] / "resources" / name

    @staticmethod
    def _data_path(name: str) -> Path:
        if getattr(sys, "frozen", False):
            root = Path(sys.executable).resolve().parent
        else:
            root = Path(__file__).resolve().parents[3]
        path = root / "data" / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _configure_theme(self) -> None:
        self.ui_font_family = load_font_family(self.root, self._resource_path("fonts/pixelmix.ttf"), PIXEL_FONT_FAMILY)
        self.ui_header_font_family = load_font_family(self.root, self._resource_path("fonts/pixelmix.ttf"), HEADER_FONT_FAMILY)
        self.ui_font = tkfont.Font(root=self.root, name="PixelFixBaseFont", family=self.ui_font_family, size=UI_FONT_SIZE)
        self.ui_header_font = tkfont.Font(
            root=self.root,
            name="PixelFixHeaderFont",
            family=self.ui_header_font_family,
            size=HEADER_FONT_SIZE,
        )
        self.root.configure(background=APP_BG)
        self.root.option_add("*Font", self.ui_font)
        self.root.option_add("*Background", APP_BG)
        self.root.option_add("*Foreground", APP_TEXT)
        self.root.option_add("*highlightBackground", APP_BORDER)
        self.root.option_add("*highlightColor", APP_BORDER)
        self.root.option_add("*insertBackground", APP_TEXT)
        self.root.option_add("*selectBackground", APP_HOVER_BG)
        self.root.option_add("*selectForeground", APP_TEXT)
        self.root.option_add("*TCombobox*Listbox.background", APP_SURFACE_BG)
        self.root.option_add("*TCombobox*Listbox.foreground", APP_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", APP_HOVER_BG)
        self.root.option_add("*TCombobox*Listbox.selectForeground", APP_TEXT)
        self.root.option_add("*TCombobox*Listbox.highlightBackground", APP_BORDER)
        self.root.option_add("*TCombobox*Listbox.highlightColor", APP_BORDER)

        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=APP_BG, foreground=APP_TEXT, font=self.ui_font)
        style.configure("TFrame", background=APP_BG)
        style.configure("TLabel", background=APP_BG, foreground=APP_TEXT)
        style.configure(
            "TLabelframe",
            background=APP_BG,
            foreground=APP_TEXT,
            bordercolor=APP_BORDER,
            borderwidth=1,
            darkcolor=APP_BORDER,
            lightcolor=APP_BORDER,
            relief=tk.SOLID,
        )
        style.configure("TLabelframe.Label", background=APP_BG, foreground=APP_TEXT, font=self.ui_header_font)
        style.configure(
            "TButton",
            background=APP_SURFACE_BG,
            foreground=APP_TEXT,
            bordercolor=APP_BORDER,
            darkcolor=APP_BORDER,
            lightcolor=APP_BORDER,
            padding=(6, 4),
        )
        style.map(
            "TButton",
            background=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
            foreground=[("pressed", APP_BG), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_ACCENT), ("active", APP_BORDER)],
            darkcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            lightcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
        )
        style.configure(
            "TMenubutton",
            background=APP_SURFACE_BG,
            foreground=APP_TEXT,
            bordercolor=APP_BORDER,
            darkcolor=APP_BORDER,
            lightcolor=APP_BORDER,
            arrowcolor=APP_TEXT,
            padding=(6, 4),
        )
        style.map(
            "TMenubutton",
            background=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
            foreground=[("pressed", APP_BG), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            darkcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            lightcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            arrowcolor=[("pressed", APP_BG), ("disabled", APP_MUTED_TEXT)],
        )
        style.configure("Compact.TButton", padding=(4, 2))
        style.configure("Compact.TMenubutton", padding=(4, 2))
        style.configure(
            "PreferencesNav.TButton",
            background=APP_SURFACE_BG,
            foreground=APP_TEXT,
            bordercolor=APP_BORDER,
            darkcolor=APP_BORDER,
            lightcolor=APP_BORDER,
            padding=(8, 6),
            anchor=tk.W,
        )
        style.map(
            "PreferencesNav.TButton",
            background=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
            foreground=[("pressed", APP_BG), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            darkcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            lightcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
        )
        style.configure(
            "PreferencesNavActive.TButton",
            background=APP_ACCENT,
            foreground=APP_BG,
            bordercolor=APP_ACCENT,
            darkcolor=APP_ACCENT,
            lightcolor=APP_ACCENT,
            padding=(8, 6),
            anchor=tk.W,
        )
        style.map(
            "PreferencesNavActive.TButton",
            background=[("pressed", APP_ACCENT), ("active", APP_ACCENT), ("disabled", APP_BG)],
            foreground=[("pressed", APP_BG), ("active", APP_BG), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT), ("disabled", APP_BORDER)],
            darkcolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT), ("disabled", APP_BORDER)],
            lightcolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT), ("disabled", APP_BORDER)],
        )
        style.configure(
            "TEntry",
            fieldbackground=APP_SURFACE_BG,
            foreground=APP_TEXT,
            insertcolor=APP_TEXT,
            bordercolor=APP_BORDER,
            darkcolor=APP_BORDER,
            lightcolor=APP_BORDER,
            padding=(6, 4),
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", APP_BG), ("readonly", APP_SURFACE_BG)],
            foreground=[("disabled", APP_MUTED_TEXT)],
            bordercolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
            darkcolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
            lightcolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=APP_SURFACE_BG,
            background=APP_SURFACE_BG,
            foreground=APP_TEXT,
            arrowcolor=APP_TEXT,
            bordercolor=APP_BORDER,
            darkcolor=APP_BORDER,
            lightcolor=APP_BORDER,
            insertcolor=APP_TEXT,
            padding=(6, 4),
        )
        style.map(
            "TCombobox",
            fieldbackground=[
                ("disabled", APP_BG),
                ("readonly", APP_SURFACE_BG),
                ("focus", APP_SURFACE_BG),
            ],
            background=[
                ("disabled", APP_BG),
                ("readonly", APP_SURFACE_BG),
                ("active", APP_SURFACE_BG),
            ],
            foreground=[
                ("disabled", APP_MUTED_TEXT),
                ("readonly", APP_TEXT),
            ],
            arrowcolor=[
                ("disabled", APP_MUTED_TEXT),
                ("readonly", APP_TEXT),
            ],
            bordercolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
            darkcolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
            lightcolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
        )
        style.configure("Compact.TEntry", padding=(4, 2))
        style.configure("Compact.TSpinbox", arrowsize=9, padding=(3, 1))
        style.configure(
            "PaletteActionIcon.TButton",
            background=APP_SURFACE_BG,
            foreground=APP_TEXT,
            bordercolor=APP_BORDER,
            borderwidth=1,
            darkcolor=APP_BORDER,
            lightcolor=APP_BORDER,
            padding=(0, 0),
            relief=tk.FLAT,
        )
        style.map(
            "PaletteActionIcon.TButton",
            background=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
            foreground=[("pressed", APP_BG), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            darkcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            lightcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
        )
        style.configure(
            "PaletteActionIconDisabled.TButton",
            background=APP_SURFACE_BG,
            foreground=APP_MUTED_TEXT,
            bordercolor=APP_BORDER,
            borderwidth=1,
            darkcolor=APP_BORDER,
            lightcolor=APP_BORDER,
            padding=(0, 0),
            relief=tk.FLAT,
        )
        style.map(
            "PaletteActionIconDisabled.TButton",
            background=[("pressed", APP_SURFACE_BG), ("active", APP_SURFACE_BG), ("disabled", APP_SURFACE_BG)],
            foreground=[("pressed", APP_MUTED_TEXT), ("active", APP_MUTED_TEXT), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_BORDER), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            darkcolor=[("pressed", APP_BORDER), ("active", APP_BORDER), ("disabled", APP_BORDER)],
            lightcolor=[("pressed", APP_BORDER), ("active", APP_BORDER), ("disabled", APP_BORDER)],
        )
        style.configure(
            "ToolButton.TButton",
            background=APP_SURFACE_BG,
            foreground=APP_TEXT,
            bordercolor=APP_SURFACE_BG,
            borderwidth=0,
            darkcolor=APP_SURFACE_BG,
            lightcolor=APP_SURFACE_BG,
            padding=TOOL_BUTTON_PADDING,
            relief=tk.FLAT,
        )
        style.map(
            "ToolButton.TButton",
            background=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
            foreground=[("pressed", APP_BG), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
            darkcolor=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
            lightcolor=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
        )
        style.configure(
            "ToolButtonDisabled.TButton",
            background=APP_SURFACE_BG,
            foreground=APP_MUTED_TEXT,
            bordercolor=APP_SURFACE_BG,
            borderwidth=0,
            darkcolor=APP_SURFACE_BG,
            lightcolor=APP_SURFACE_BG,
            padding=TOOL_BUTTON_PADDING,
            relief=tk.FLAT,
        )
        style.map(
            "ToolButtonDisabled.TButton",
            background=[("pressed", APP_SURFACE_BG), ("active", APP_SURFACE_BG), ("disabled", APP_SURFACE_BG)],
            foreground=[("pressed", APP_MUTED_TEXT), ("active", APP_MUTED_TEXT), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_SURFACE_BG), ("active", APP_SURFACE_BG), ("disabled", APP_SURFACE_BG)],
            darkcolor=[("pressed", APP_SURFACE_BG), ("active", APP_SURFACE_BG), ("disabled", APP_SURFACE_BG)],
            lightcolor=[("pressed", APP_SURFACE_BG), ("active", APP_SURFACE_BG), ("disabled", APP_SURFACE_BG)],
        )
        style.configure(
            "ToolButtonActive.TButton",
            background=APP_ACCENT,
            foreground=APP_BG,
            bordercolor=APP_ACCENT,
            darkcolor=APP_ACCENT,
            lightcolor=APP_ACCENT,
            borderwidth=0,
            padding=TOOL_BUTTON_PADDING,
            relief=tk.FLAT,
        )
        style.map(
            "ToolButtonActive.TButton",
            background=[("pressed", APP_ACCENT), ("active", APP_ACCENT), ("disabled", APP_BG)],
            foreground=[("pressed", APP_BG), ("active", APP_BG), ("disabled", APP_MUTED_TEXT)],
            bordercolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT), ("disabled", APP_BORDER)],
            darkcolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT), ("disabled", APP_BORDER)],
            lightcolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT), ("disabled", APP_BORDER)],
        )
        style.configure(
            "TCheckbutton",
            background=APP_BG,
            foreground=APP_TEXT,
            indicatorbackground=APP_BG,
            indicatorforeground=APP_TEXT,
            upperbordercolor=APP_BORDER,
            lowerbordercolor=APP_BORDER,
            padding=(2, 2),
        )
        style.map(
            "TCheckbutton",
            background=[("active", APP_BG), ("disabled", APP_BG)],
            foreground=[("disabled", APP_MUTED_TEXT)],
            indicatorbackground=[("disabled", APP_BG), ("pressed", APP_ACCENT), ("selected", APP_ACCENT)],
            indicatorforeground=[("disabled", APP_MUTED_TEXT), ("selected", APP_BG)],
            upperbordercolor=[("disabled", APP_BORDER), ("pressed", APP_ACCENT), ("selected", APP_ACCENT), ("active", APP_BORDER)],
            lowerbordercolor=[("disabled", APP_BORDER), ("pressed", APP_ACCENT), ("selected", APP_ACCENT), ("active", APP_BORDER)],
        )
        style.configure(
            "TRadiobutton",
            background=APP_BG,
            foreground=APP_TEXT,
            indicatorbackground=APP_BG,
            indicatorforeground=APP_TEXT,
            upperbordercolor=APP_BORDER,
            lowerbordercolor=APP_BORDER,
            padding=(2, 2),
        )
        style.map(
            "TRadiobutton",
            background=[("active", APP_BG), ("disabled", APP_BG)],
            foreground=[("disabled", APP_MUTED_TEXT)],
            indicatorbackground=[("disabled", APP_BG), ("pressed", APP_ACCENT), ("selected", APP_ACCENT)],
            indicatorforeground=[("disabled", APP_MUTED_TEXT), ("selected", APP_BG)],
            upperbordercolor=[("disabled", APP_BORDER), ("pressed", APP_ACCENT), ("selected", APP_ACCENT), ("active", APP_BORDER)],
            lowerbordercolor=[("disabled", APP_BORDER), ("pressed", APP_ACCENT), ("selected", APP_ACCENT), ("active", APP_BORDER)],
        )
        style.configure(
            "TSpinbox",
            arrowsize=10,
            arrowcolor=APP_TEXT,
            bordercolor=APP_BORDER,
            darkcolor=APP_BORDER,
            fieldbackground=APP_SURFACE_BG,
            foreground=APP_TEXT,
            lightcolor=APP_BORDER,
            padding=(4, 2),
        )
        style.map(
            "TSpinbox",
            arrowcolor=[("disabled", APP_MUTED_TEXT)],
            fieldbackground=[("disabled", APP_BG), ("readonly", APP_SURFACE_BG)],
            foreground=[("disabled", APP_MUTED_TEXT)],
            bordercolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
            darkcolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
            lightcolor=[("disabled", APP_BORDER), ("focus", APP_BORDER)],
        )

    def _new_menu(self, master: tk.Misc) -> tk.Menu:
        return tk.Menu(
            master,
            tearoff=False,
            activebackground=APP_HOVER_BG,
            activeforeground=APP_TEXT,
            background=APP_BG,
            bd=0,
            disabledforeground=APP_MUTED_TEXT,
            fg=APP_TEXT,
            font=self.ui_font,
            relief=tk.FLAT,
            selectcolor=APP_ACCENT,
        )

    @staticmethod
    def _coerce_outline_colour_mode(value: object) -> str:
        normalized = str(value or OUTLINE_COLOUR_MODE_PALETTE).strip().lower()
        if normalized == OUTLINE_COLOUR_MODE_ADAPTIVE:
            return OUTLINE_COLOUR_MODE_ADAPTIVE
        return OUTLINE_COLOUR_MODE_PALETTE

    @staticmethod
    def _coerce_outline_adaptive_darken_percent(value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = OUTLINE_ADAPTIVE_DARKEN_DEFAULT
        return max(0, min(100, parsed))

    @staticmethod
    def _coerce_outline_remove_brightness_threshold_percent(value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT
        return max(0, min(100, parsed))

    @staticmethod
    def _coerce_outline_remove_brightness_direction(value: object) -> str:
        normalized = str(value or OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK).strip().lower()
        if normalized == OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_BRIGHT:
            return OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_BRIGHT
        return OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK

    @staticmethod
    def _coerce_brush_width(value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = BRUSH_WIDTH_DEFAULT
        return max(1, min(BRUSH_WIDTH_MAX, parsed))

    @staticmethod
    def _coerce_brush_shape(value: object) -> str:
        normalized = str(value or BRUSH_SHAPE_SQUARE).strip().lower()
        if normalized == BRUSH_SHAPE_ROUND:
            return BRUSH_SHAPE_ROUND
        return BRUSH_SHAPE_SQUARE

    @staticmethod
    def _coerce_image_filter_strength(value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = IMAGE_FILTER_STRENGTH_DEFAULT
        return max(1, min(IMAGE_FILTER_STRENGTH_MAX, parsed))

    @classmethod
    def _initial_outline_colour_mode(cls, persisted: dict[str, object]) -> str:
        if "outline_colour_mode" in persisted:
            return cls._coerce_outline_colour_mode(persisted.get("outline_colour_mode"))
        return OUTLINE_COLOUR_MODE_ADAPTIVE if bool(persisted.get("outline_adaptive", False)) else OUTLINE_COLOUR_MODE_PALETTE

    def _build_menu_bar(self) -> None:
        menubar = self._new_menu(self.root)

        file_menu = self._new_menu(menubar)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_image)
        self.recent_menu = self._new_menu(file_menu)
        file_menu.add_cascade(label="Recent", menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_processed_image)
        file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_processed_image_as)
        file_menu.add_command(label="Canvas Size...", command=self.open_canvas_size_window)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        palette_menu = self._new_menu(menubar)
        input_menu = self._new_menu(palette_menu)
        for label, _value in COLOR_MODE_OPTIONS:
            input_menu.add_radiobutton(label=label, value=label, variable=self.input_mode_var, command=self._on_settings_changed)
        output_menu = self._new_menu(palette_menu)
        for label, _value in COLOR_MODE_OPTIONS:
            output_menu.add_radiobutton(label=label, value=label, variable=self.output_mode_var, command=self._on_settings_changed)
        built_in_menu = self._new_menu(palette_menu)
        add_colour_menu = self._new_menu(palette_menu)
        sort_menu = self._new_menu(palette_menu)
        add_colour_menu.add_command(label="Pick From Original", command=self._start_palette_add_pick_mode)
        add_colour_menu.add_command(label="Enter Hex Code...", command=self._prompt_add_palette_color_hex)
        palette_menu.add_cascade(label="Input Mode", menu=input_menu)
        palette_menu.add_cascade(label="Output Mode", menu=output_menu)
        palette_menu.add_separator()
        palette_menu.add_cascade(label="Built-in Palettes", menu=built_in_menu)
        palette_menu.add_cascade(label="Add Colour", menu=add_colour_menu)
        palette_menu.add_cascade(label="Sort Current Palette", menu=sort_menu)
        palette_menu.add_command(label="Load Palette...", command=self.load_palette_file)
        palette_menu.add_command(label="Save Current Palette...", command=self.save_palette_file)
        menubar.add_cascade(label="Palette", menu=palette_menu)

        edit_menu = self._new_menu(menubar)
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self._cut_image_selection)
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self._copy_image_selection)
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self._paste_image_selection)
        edit_menu.add_separator()
        edit_menu.add_command(label="Delete Selection", accelerator="Delete", command=self._delete_image_selection)
        edit_menu.add_command(label="Deselect", accelerator="Esc", command=self._deselect_image_selection)
        edit_menu.add_command(label="Commit Selection", accelerator="Enter", command=self._commit_floating_selection)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        transform_menu = self._new_menu(menubar)
        transform_menu.add_command(label="Flip Horizontal", command=self._flip_image_horizontal)
        transform_menu.add_command(label="Flip Vertical", command=self._flip_image_vertical)
        transform_menu.add_separator()
        transform_menu.add_command(label="Rotate 90° CW", command=lambda: self._apply_rotation_turns(1))
        transform_menu.add_command(label="Rotate 180°", command=lambda: self._apply_rotation_turns(2))
        transform_menu.add_command(label="Rotate 90° CCW", command=lambda: self._apply_rotation_turns(3))
        menubar.add_cascade(label="Transform", menu=transform_menu)

        select_menu = self._new_menu(menubar)
        select_hue_menu = self._new_menu(select_menu)
        for label, mode in PALETTE_SELECT_OPTIONS:
            select_menu.add_command(label=label, command=lambda value=mode: self.select_current_palette(value))
        select_menu.add_cascade(label="Hue", menu=select_hue_menu)
        for label, mode in PALETTE_SELECT_HUE_OPTIONS:
            select_hue_menu.add_command(label=label, command=lambda value=mode: self.select_current_palette(value))
        for label, mode in PALETTE_SELECT_SPECIAL_OPTIONS:
            select_menu.add_command(label=label, command=lambda value=mode: self.select_current_palette(value))
        menubar.add_cascade(label="Select", menu=select_menu)

        self._menu_bar = menubar
        self.root.config(menu=menubar)
        self._menu_items["file"] = file_menu
        self._menu_items["palette"] = palette_menu
        self._menu_items["edit"] = edit_menu
        self._menu_items["transform"] = transform_menu
        self._menu_items["select"] = select_menu
        self._menu_items["select_hue"] = select_hue_menu
        self._menu_items["palette_input"] = input_menu
        self._menu_items["palette_output"] = output_menu
        self._menu_items["built_in_palettes"] = built_in_menu
        self._menu_items["palette_add"] = add_colour_menu
        self._menu_items["palette_sort"] = sort_menu
        self._populate_builtin_palette_menu()
        self._populate_palette_sort_menu()
        self._refresh_recent_menu()

    def _build_top_toolbar(self) -> None:
        self.top_toolbar = ttk.Frame(self.root)
        self.top_toolbar.pack(fill=tk.X, padx=10, pady=(10, 0))

        self.top_toolbar_row = ttk.Frame(self.top_toolbar)
        self.top_toolbar_row.pack(anchor=tk.W)

        toolbar_buttons = (
            ("toolbar_new_button", "icon_new.png", self.open_new_image_window, "New"),
            ("toolbar_open_button", "icon_open.png", self.open_image, "Open"),
            ("toolbar_save_button", "icon_save.png", self.save_processed_image, "Save"),
            ("toolbar_cut_button", "icon_cut.png", self._cut_image_selection, "Cut"),
            ("toolbar_copy_button", "icon_copy.png", self._copy_image_selection, "Copy"),
            ("toolbar_paste_button", "icon_paste.png", self._paste_image_selection, "Paste"),
            ("toolbar_undo_button", "icon_undo.png", self.undo, "Undo"),
            ("toolbar_redo_button", "icon_redo.png", self.redo, "Redo"),
            (
                "toolbar_canvas_size_button",
                "icon_canvas.png",
                self.open_canvas_size_window,
                "Canvas Size",
            ),
            ("toolbar_rotate_button", "icon_rotate.png", self._toggle_rotate_mode, "Rotate"),
            (
                "toolbar_view_original_button",
                "icon_view_original.png",
                lambda: self._set_view_from_toolbar("original"),
                "View Original",
            ),
            (
                "toolbar_view_processed_button",
                "icon_view_processed.png",
                lambda: self._set_view_from_toolbar("processed"),
                "View Current",
            ),
            (
                "toolbar_ai_generate_button",
                "icon_ai.png",
                self.open_ai_generate_window,
                "Generate image…",
            ),
            (
                "toolbar_indexed_color_button",
                "icon_indexed_color.png",
                self.open_indexed_color_window,
                "Indexed Color",
            ),
            (
                "toolbar_preferences_button",
                "icon_settings.png",
                self.open_preferences_window,
                "Preferences",
            ),
        )
        self._toolbar_button_order: tuple[str, ...] = tuple(widget_name for widget_name, _asset_name, _command, _tooltip in toolbar_buttons)
        for index, (widget_name, asset_name, command, tooltip_text) in enumerate(toolbar_buttons):
            setattr(
                self,
                widget_name,
                self._create_toolbar_button(
                    widget_name,
                    self.top_toolbar_row,
                    asset_name,
                    command,
                    tooltip_text,
                    padx=(0, 4 if index < len(toolbar_buttons) - 1 else 0),
                ),
            )
        self._toolbar_zoom_values = tuple(f"{value}%" for value in ZOOM_PRESETS) + ("Fit",)
        self.toolbar_zoom_var.set(self._toolbar_zoom_display_value())
        self.toolbar_zoom_dropdown = ttk.Combobox(
            self.top_toolbar_row,
            textvariable=self.toolbar_zoom_var,
            values=self._toolbar_zoom_values,
            width=8,
            state="readonly",
        )
        self.toolbar_zoom_dropdown.pack(side=tk.LEFT, padx=(8, 0))
        self.toolbar_zoom_dropdown.bind("<<ComboboxSelected>>", self._on_toolbar_zoom_selected)
        self._tooltips.append(Tooltip(self.toolbar_zoom_dropdown, "Zoom"))

    def _build_layout(self) -> None:
        self.body = ttk.Frame(self.root)
        self.body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 10))

        sidebar = ttk.Frame(self.body, width=TOOLS_SIDEBAR_WIDTH)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sidebar.pack_propagate(False)

        scale_section = self._create_section(sidebar, "Pixel scale")
        row = ttk.Frame(scale_section)
        row.pack(fill=tk.X)
        self.pixel_width_spinbox = ttk.Spinbox(row, from_=1, to=512, textvariable=self.pixel_width_var, width=8, command=self._on_settings_changed)
        self.pixel_width_spinbox.pack(side=tk.LEFT)
        self.downsample_button = ttk.Button(row, text="Downsample", command=self.downsample_current_image)
        self.downsample_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(scale_section, textvariable=self.scale_info_var, wraplength=TOOLS_SIDEBAR_WRAP_LENGTH).pack(
            anchor=tk.W,
            pady=(6, 0),
        )
        self.options_section = self._create_section(sidebar, "Options")
        self.options_helper_label = ttk.Label(
            self.options_section,
            textvariable=self.options_helper_var,
            wraplength=TOOLS_SIDEBAR_WRAP_LENGTH,
            justify=tk.LEFT,
        )
        self.brush_width_row = ttk.Frame(self.options_section)
        ttk.Label(self.brush_width_row, text="Pixel Width").pack(side=tk.LEFT)
        self.brush_width_spinbox = ttk.Spinbox(
            self.brush_width_row,
            from_=1,
            to=BRUSH_WIDTH_MAX,
            textvariable=self.brush_width_var,
            width=5,
            command=self._on_brush_width_changed,
        )
        self.brush_width_spinbox.pack(side=tk.LEFT, padx=(8, 0))
        self.brush_shape_row = ttk.Frame(self.options_section)
        ttk.Label(self.brush_shape_row, text="Brush Shape").pack(side=tk.LEFT)
        self.brush_shape_dropdown_button = ttk.Menubutton(
            self.brush_shape_row,
            textvariable=self.brush_shape_var,
        )
        self.brush_shape_dropdown_button.pack(side=tk.LEFT, padx=(10, 0))
        self.brush_shape_dropdown_menu = self._new_menu(self.brush_shape_dropdown_button)
        for shape in (BRUSH_SHAPE_SQUARE, BRUSH_SHAPE_ROUND):
            display_value = shape.title()
            self.brush_shape_dropdown_menu.add_command(
                label=display_value,
                command=lambda value=display_value: self._select_brush_shape(value),
            )
        self.brush_shape_dropdown_button.configure(menu=self.brush_shape_dropdown_menu)
        self.pick_preview_empty_label = ttk.Label(
            self.options_section,
            text="Hover over the processed preview to inspect a pixel.",
            wraplength=TOOLS_SIDEBAR_WRAP_LENGTH,
            justify=tk.LEFT,
        )
        self.pick_preview_frame = ttk.Frame(self.options_section)
        self.pick_preview_swatch = tk.Label(
            self.pick_preview_frame,
            width=2,
            height=1,
            bg=APP_SURFACE_BG,
            fg=APP_TEXT,
            relief=tk.SOLID,
            bd=1,
        )
        self.pick_preview_swatch.pack(side=tk.LEFT)
        self.pick_preview_hex_label = ttk.Label(self.pick_preview_frame, textvariable=self.pick_preview_var, width=7)
        self.pick_preview_hex_label.pack(side=tk.LEFT, padx=(4, 0))
        self.pick_preview_rgb_label = ttk.Label(self.pick_preview_frame, textvariable=self.pick_preview_rgb_var, width=14)
        self.pick_preview_rgb_label.pack(side=tk.LEFT, padx=(6, 0))
        self.pick_preview_position_label = ttk.Label(self.pick_preview_frame, textvariable=self.pick_preview_position_var, width=8)
        self.pick_preview_position_label.pack(side=tk.LEFT, padx=(6, 0))
        self.outline_pixel_perfect_row = ttk.Frame(self.options_section)
        self.outline_pixel_perfect_toggle = ttk.Checkbutton(
            self.outline_pixel_perfect_row,
            text="Pixel Perfect",
            variable=self.outline_pixel_perfect_var,
            command=self._on_outline_pixel_perfect_changed,
        )
        self.outline_pixel_perfect_toggle.pack(side=tk.LEFT)
        self.outline_colour_mode_row = ttk.Frame(self.options_section)
        ttk.Label(self.outline_colour_mode_row, text="Outline Colour").pack(side=tk.LEFT)
        self.outline_colour_mode_dropdown_button = ttk.Menubutton(
            self.outline_colour_mode_row,
            textvariable=self.outline_colour_mode_display_var,
        )
        self.outline_colour_mode_dropdown_button.pack(side=tk.LEFT, padx=(10, 0))
        self.outline_colour_mode_dropdown_menu = self._new_menu(self.outline_colour_mode_dropdown_button)
        for value, label in OUTLINE_COLOUR_MODE_LABELS.items():
            self.outline_colour_mode_dropdown_menu.add_command(
                label=label,
                command=lambda mode=value: self._select_outline_colour_mode(mode),
            )
        self.outline_colour_mode_dropdown_button.configure(menu=self.outline_colour_mode_dropdown_menu)
        self.outline_adaptive_row = ttk.Frame(self.options_section)
        self.outline_adaptive_darken_label = ttk.Label(self.outline_adaptive_row, text="Darken %")
        self.outline_adaptive_darken_label.pack(side=tk.LEFT)
        self.outline_adaptive_darken_spinbox = ttk.Spinbox(
            self.outline_adaptive_row,
            from_=0,
            to=100,
            textvariable=self.outline_adaptive_darken_percent_var,
            width=5,
            command=self._on_outline_adaptive_darken_changed,
        )
        self.outline_adaptive_darken_spinbox.pack(side=tk.LEFT, padx=(8, 0))
        self.outline_add_generated_colours_row = ttk.Frame(self.options_section)
        self.outline_add_generated_colours_toggle = ttk.Checkbutton(
            self.outline_add_generated_colours_row,
            text="Add Generated Colours",
            variable=self.outline_add_generated_colours_var,
            command=self._on_outline_add_generated_colours_changed,
        )
        self.outline_add_generated_colours_toggle.pack(side=tk.LEFT)
        self.outline_remove_threshold_row = ttk.Frame(self.options_section)
        self.outline_remove_brightness_threshold_toggle = ttk.Checkbutton(
            self.outline_remove_threshold_row,
            text="Brightness Threshold",
            variable=self.outline_remove_brightness_threshold_enabled_var,
            command=self._on_outline_remove_brightness_threshold_enabled_changed,
        )
        self.outline_remove_brightness_threshold_toggle.pack(side=tk.LEFT)
        self.outline_remove_brightness_threshold_spinbox = ttk.Spinbox(
            self.outline_remove_threshold_row,
            from_=0,
            to=100,
            textvariable=self.outline_remove_brightness_threshold_percent_var,
            width=5,
            command=self._on_outline_remove_brightness_threshold_percent_changed,
        )
        self.outline_remove_brightness_threshold_spinbox.pack(side=tk.LEFT, padx=(8, 0))
        self.outline_remove_direction_row = ttk.Frame(self.options_section)
        ttk.Label(self.outline_remove_direction_row, text="Dark/Bright").pack(side=tk.LEFT)
        self.outline_remove_brightness_direction_dropdown_button = ttk.Menubutton(
            self.outline_remove_direction_row,
            textvariable=self.outline_remove_brightness_direction_display_var,
        )
        self.outline_remove_brightness_direction_dropdown_button.pack(side=tk.LEFT, padx=(10, 0))
        self.outline_remove_brightness_direction_dropdown_menu = self._new_menu(
            self.outline_remove_brightness_direction_dropdown_button
        )
        for value, label in OUTLINE_REMOVE_DIRECTION_LABELS.items():
            self.outline_remove_brightness_direction_dropdown_menu.add_command(
                label=label,
                command=lambda direction=value: self._select_outline_remove_brightness_direction(direction),
            )
        self.outline_remove_brightness_direction_dropdown_button.configure(
            menu=self.outline_remove_brightness_direction_dropdown_menu
        )
        self.image_filter_strength_row = ttk.Frame(self.options_section)
        ttk.Label(self.image_filter_strength_row, text="Strength").pack(side=tk.LEFT)
        self.image_filter_strength_spinbox = ttk.Spinbox(
            self.image_filter_strength_row,
            from_=1,
            to=IMAGE_FILTER_STRENGTH_MAX,
            textvariable=self.image_filter_strength_var,
            width=5,
            command=self._on_image_filter_strength_changed,
        )
        self.image_filter_strength_spinbox.pack(side=tk.LEFT, padx=(8, 0))
        self.rotate_direction_row = ttk.Frame(self.options_section)
        ttk.Label(self.rotate_direction_row, text="Rotate").pack(side=tk.LEFT)
        self.rotate_direction_dropdown_button = ttk.Menubutton(
            self.rotate_direction_row,
            textvariable=self.rotate_direction_display_var,
        )
        self.rotate_direction_dropdown_button.pack(side=tk.LEFT, padx=(10, 0))
        self.rotate_direction_dropdown_menu = self._new_menu(self.rotate_direction_dropdown_button)
        for value, label in ROTATE_DIRECTION_LABELS.items():
            self.rotate_direction_dropdown_menu.add_command(
                label=label,
                command=lambda direction=value: self._select_rotate_direction(direction),
            )
        self.rotate_direction_dropdown_button.configure(menu=self.rotate_direction_dropdown_menu)
        self.options_apply_row = ttk.Frame(self.options_section)
        self.options_apply_button = ttk.Button(self.options_apply_row, text="Apply", command=self._apply_selected_tool_options)
        self.options_apply_button.pack(side=tk.LEFT)

        tools_section = self._create_section(sidebar, "Tools", fill_x=False, anchor=tk.W)
        tool_grid = ttk.Frame(tools_section)
        tool_grid.pack(anchor=tk.W, pady=(4, 0))
        select_cell, self.select_button = self._create_tool_button(
            "select_button",
            tool_grid,
            "icon_select.png",
            self._toggle_select_mode,
            "Selection",
        )
        polygon_lasso_cell, self.polygon_lasso_button = self._create_tool_button(
            "polygon_lasso_button",
            tool_grid,
            "icon_poly_lasso.png",
            self._toggle_polygon_lasso_mode,
            "Polygonal Lasso",
        )
        pencil_cell, self.pencil_button = self._create_tool_button("pencil_button", tool_grid, "icon_pencil.png", self._toggle_pencil_mode, "Pencil")
        eraser_cell, self.eraser_button = self._create_tool_button("eraser_button", tool_grid, "icon_eraser.png", self._toggle_eraser_mode, "Eraser")
        palette_picker_cell, self.palette_picker_button = self._create_tool_button(
            "palette_picker_button",
            tool_grid,
            "icon_eyedrop.png",
            self._toggle_active_color_pick_mode,
            "Colour Picker",
        )
        bucket_cell, self.bucket_button = self._create_tool_button(
            "bucket_button",
            tool_grid,
            "icon_bucket.png",
            self._toggle_bucket_mode,
            "Bucket",
        )
        circle_cell, self.circle_button = self._create_tool_button(
            "circle_button",
            tool_grid,
            "icon_circle.png",
            self._toggle_ellipse_mode,
            "Ellipse",
        )
        square_cell, self.square_button = self._create_tool_button(
            "square_button",
            tool_grid,
            "icon_square.png",
            self._toggle_rectangle_mode,
            "Rectangle",
        )
        line_cell, self.line_button = self._create_tool_button(
            "line_button",
            tool_grid,
            "icon_line.png",
            self._toggle_line_mode,
            "Line",
        )
        gradient_cell, self.gradient_button = self._create_tool_button(
            "gradient_button",
            tool_grid,
            "icon_gradient.png",
            self._toggle_gradient_mode,
            "Gradient",
        )
        blur_cell, self.blur_button = self._create_tool_button(
            "blur_button",
            tool_grid,
            "icon_blur.png",
            self._toggle_blur_mode,
            "Blur",
        )
        sharpen_cell, self.sharpen_button = self._create_tool_button(
            "sharpen_button",
            tool_grid,
            "icon_sharpen.png",
            self._toggle_sharpen_mode,
            "Sharpen",
        )
        flip_horizontal_cell, self.flip_horizontal_button = self._create_tool_button(
            "flip_horizontal_button",
            tool_grid,
            "icon_flip_horizontal.png",
            self._flip_image_horizontal,
            "Flip Horizontal",
        )
        flip_vertical_cell, self.flip_vertical_button = self._create_tool_button(
            "flip_vertical_button",
            tool_grid,
            "icon_flip_vertical.png",
            self._flip_image_vertical,
            "Flip Vertical",
        )
        add_outline_cell, self.add_outline_button = self._create_tool_button(
            "add_outline_button",
            tool_grid,
            "icon_outline_add.png",
            self._toggle_add_outline_mode,
            "Add Outline",
        )
        remove_outline_cell, self.remove_outline_button = self._create_tool_button(
            "remove_outline_button",
            tool_grid,
            "icon_outline_remove.png",
            self._toggle_remove_outline_mode,
            "Remove Outline",
        )
        transparency_cell, self.active_color_transparent_button = self._create_tool_button(
            "active_color_transparent_button",
            tool_grid,
            "icon_transparency.png",
            self._make_active_color_transparent,
            "Make Active Colour Transparent",
        )
        swap_cell, self.swap_active_colors_button = self._create_tool_button(
            "swap_active_colors_button",
            tool_grid,
            "icon_palette_swap.png",
            self._swap_active_colors,
            "Swap Primary And Secondary Colours",
        )
        for index, cell in enumerate(
            (
                select_cell,
                polygon_lasso_cell,
                pencil_cell,
                eraser_cell,
                palette_picker_cell,
                bucket_cell,
                circle_cell,
                square_cell,
                line_cell,
                gradient_cell,
                blur_cell,
                sharpen_cell,
                flip_horizontal_cell,
                flip_vertical_cell,
                add_outline_cell,
                remove_outline_cell,
                transparency_cell,
                swap_cell,
            )
        ):
            row_index, column_index = divmod(index, 2)
            cell.grid(
                row=row_index,
                column=column_index,
                sticky="nw",
                padx=0,
                pady=0,
            )
        for column_index in range(2):
            tool_grid.grid_columnconfigure(column_index, minsize=TOOL_BUTTON_WIDTH)
        active_color_controls = ttk.Frame(tools_section, width=TOOL_BUTTON_WIDTH * 2, height=TOOL_BUTTON_HEIGHT)
        active_color_controls.pack(anchor=tk.W, pady=(8, 0))
        active_color_controls.pack_propagate(False)
        self.active_color_preview_label = tk.Label(
            active_color_controls,
            background=APP_BG,
            bd=0,
            highlightthickness=0,
        )
        self.active_color_preview_label.place(x=TOOL_BUTTON_WIDTH, rely=0.5, anchor=tk.CENTER)
        self.active_color_preview_label.bind("<ButtonPress-1>", self._on_active_color_preview_click)
        self.options_section.pack_forget()
        self.options_section.pack(fill=tk.X, pady=(0, 10))

        self.palette_column = ttk.Frame(self.body, width=PALETTE_COLUMN_DEFAULT_WIDTH)
        self.palette_column.pack(side=tk.RIGHT, fill=tk.Y)
        self._lock_palette_column_width()
        self.palette_column.grid_rowconfigure(0, weight=3)
        self.palette_column.grid_rowconfigure(1, weight=2)
        self.palette_column.grid_columnconfigure(0, weight=1)

        workspace = ttk.Frame(self.body)
        workspace.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.palette_frame = ttk.LabelFrame(self.palette_column, text="PALETTE")
        self.palette_frame.grid(row=0, column=0, sticky="nsew")
        self.palette_frame.grid_rowconfigure(0, weight=1)
        self.palette_frame.grid_columnconfigure(0, weight=1)
        palette_swatches = ttk.Frame(self.palette_frame)
        palette_swatches.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=PALETTE_COLUMN_CONTENT_PADDING,
            pady=(PALETTE_COLUMN_CONTENT_PADDING, PALETTE_COLUMN_CONTENT_PADDING),
        )
        palette_swatches.grid_rowconfigure(0, weight=1)
        palette_swatches.grid_columnconfigure(0, weight=1)
        self.palette_canvas = tk.Canvas(palette_swatches, background=APP_BG, bd=0, highlightthickness=0)
        self.palette_canvas.grid(row=0, column=0, sticky="nsew")
        self.palette_scrollbar = ttk.Scrollbar(palette_swatches, orient=tk.VERTICAL, command=self.palette_canvas.yview)
        self.palette_scrollbar.grid(row=0, column=1, sticky="ns")
        self.palette_canvas.configure(yscrollcommand=self.palette_scrollbar.set)
        self.palette_canvas.bind("<Configure>", lambda _event: self._update_palette_strip(), add="+")
        self.palette_canvas.bind("<ButtonPress-1>", self._on_palette_canvas_click)
        self.palette_canvas.bind("<B1-Motion>", self._on_palette_canvas_drag)
        self.palette_canvas.bind("<ButtonRelease-1>", self._on_palette_canvas_release)
        self.palette_canvas.bind("<Double-Button-1>", self._on_palette_canvas_double_click)
        self.palette_canvas.bind("<ButtonPress-3>", self._on_palette_canvas_right_click)
        self.palette_canvas.bind("<MouseWheel>", self._on_palette_mouse_wheel, add="+")
        self.palette_dropdown_button = ttk.Button(
            self.palette_frame,
            textvariable=self.palette_dropdown_var,
            style="Compact.TButton",
            width=12,
            command=self._toggle_palette_browser,
        )
        self.palette_dropdown_button.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=PALETTE_COLUMN_CONTENT_PADDING,
            pady=(0, PALETTE_COLUMN_CONTENT_PADDING),
        )
        self._refresh_palette_browser_button_state()
        palette_actions = ttk.Frame(self.palette_frame)
        palette_actions.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=PALETTE_COLUMN_CONTENT_PADDING,
            pady=(0, PALETTE_COLUMN_CONTENT_PADDING),
        )
        palette_actions_top = ttk.Frame(palette_actions)
        palette_actions_top.pack(fill=tk.X)
        self.add_palette_color_button = ttk.Button(
            palette_actions_top,
            text="+",
            width=2,
            style="Compact.TButton",
            command=self._toggle_palette_add_pick_mode,
        )
        self.add_palette_color_button.grid(row=0, column=0, sticky="ew")
        self.remove_palette_color_button = ttk.Button(
            palette_actions_top,
            text="-",
            width=2,
            style="Compact.TButton",
            command=self._remove_selected_palette_colors,
        )
        self.remove_palette_color_button.grid(row=0, column=1, sticky="ew", padx=(PALETTE_ACTION_GAP, 0))
        self.reduce_palette_button = ttk.Button(
            palette_actions_top,
            text="Apply",
            style="Compact.TButton",
            command=self.reduce_palette_current_image,
        )
        self.reduce_palette_button.grid(row=0, column=2, sticky="ew", padx=(PALETTE_ACTION_GAP, 0))
        for index in range(3):
            palette_actions_top.grid_columnconfigure(index, weight=1)
        palette_actions_middle = ttk.Frame(palette_actions)
        palette_actions_middle.pack(fill=tk.X, pady=(PALETTE_ACTION_GAP, 0))
        merge_palette_cell, self.merge_palette_button = self._create_palette_action_icon_button(
            "merge_palette_button",
            palette_actions_middle,
            "icon_merge.png",
            self._merge_selected_palette_colors,
            "Merge selected palette colours",
        )
        merge_palette_cell.pack(side=tk.LEFT)
        ramp_palette_cell, self.ramp_palette_button = self._create_palette_action_icon_button(
            "ramp_palette_button",
            palette_actions_middle,
            "icon_ramp.png",
            self._ramp_selected_palette_colors,
            "Append ramps from selected palette colours",
        )
        ramp_palette_cell.pack(side=tk.LEFT, padx=(PALETTE_ACTION_GAP, 0))
        palette_sort_row = ttk.Frame(palette_actions)
        palette_sort_row.pack(fill=tk.X, pady=(PALETTE_ACTION_GAP, 0))
        ttk.Label(palette_sort_row, text="Sort:", style="Compact.TLabel").pack(side=tk.LEFT)
        self._palette_sort_display_labels = ["Sort..."] + [label for label, _mode in PALETTE_SORT_OPTIONS]
        self.palette_sort_var = tk.StringVar(value=self._palette_sort_display_labels[0])
        self.palette_sort_combobox = ttk.Combobox(
            palette_sort_row,
            textvariable=self.palette_sort_var,
            values=self._palette_sort_display_labels,
            state="readonly",
            width=22,
        )
        self.palette_sort_combobox.pack(side=tk.LEFT, padx=(PALETTE_ACTION_GAP, 0), fill=tk.X, expand=True)
        self.palette_sort_combobox.bind("<<ComboboxSelected>>", self._on_palette_sort_combobox_changed)
        palette_actions_bottom = ttk.Frame(palette_actions)
        palette_actions_bottom.pack(fill=tk.X, pady=(PALETTE_ACTION_GAP, 0))
        self.select_all_palette_button = ttk.Button(
            palette_actions_bottom,
            text="All",
            style="Compact.TButton",
            command=self._select_all_palette_colors,
        )
        self.select_all_palette_button.grid(row=0, column=0, sticky="ew")
        self.clear_palette_selection_button = ttk.Button(
            palette_actions_bottom,
            text="None",
            style="Compact.TButton",
            command=self._clear_palette_selection,
        )
        self.clear_palette_selection_button.grid(row=0, column=1, sticky="ew", padx=(PALETTE_ACTION_GAP, 0))
        self.invert_palette_selection_button = ttk.Button(
            palette_actions_bottom,
            text="Invert",
            style="Compact.TButton",
            command=self._invert_palette_selection,
        )
        self.invert_palette_selection_button.grid(row=0, column=2, sticky="ew", padx=(PALETTE_ACTION_GAP, 0))
        for index in range(3):
            palette_actions_bottom.grid_columnconfigure(index, weight=1)

        adjust_section = self._create_section(self.palette_column, "Adjust")
        adjust_section.pack_forget()
        adjust_section.configure(padding=PALETTE_COLUMN_CONTENT_PADDING)
        adjust_section.grid(row=1, column=0, sticky="nsew", pady=(PALETTE_COLUMN_CONTENT_PADDING, 0))
        reduction_row = ttk.Frame(adjust_section)
        reduction_row.pack(fill=tk.X)
        self.palette_reduction_spinbox = ttk.Spinbox(
            reduction_row,
            from_=1,
            to=256,
            textvariable=self.palette_reduction_colors_var,
            style="Compact.TSpinbox",
            width=6,
            command=self._on_settings_changed,
        )
        self.palette_reduction_spinbox.pack(side=tk.LEFT)
        self.generate_override_palette_button = ttk.Button(
            reduction_row,
            text="Reduce",
            style="Compact.TButton",
            command=self.generate_palette_from_image,
        )
        self.generate_override_palette_button.pack(side=tk.LEFT, padx=(PALETTE_COLUMN_CONTENT_PADDING, 0))
        self.palette_adjustment_controls: list[tk.Scale] = []
        self.palette_brightness_scale = self._create_palette_adjustment_row(
            adjust_section,
            label="Brightness",
            variable=self.palette_brightness_var,
            value_var=self.palette_brightness_value_var,
            from_=-100,
            to=100,
        )
        self.palette_contrast_scale = self._create_palette_adjustment_row(
            adjust_section,
            label="Contrast",
            variable=self.palette_contrast_var,
            value_var=self.palette_contrast_value_var,
            from_=-100,
            to=100,
        )
        self.palette_hue_scale = self._create_palette_adjustment_row(
            adjust_section,
            label="Hue",
            variable=self.palette_hue_var,
            value_var=self.palette_hue_value_var,
            from_=-180,
            to=180,
        )
        self.palette_saturation_scale = self._create_palette_adjustment_row(
            adjust_section,
            label="Saturation",
            variable=self.palette_saturation_var,
            value_var=self.palette_saturation_value_var,
            from_=-100,
            to=100,
        )
        self.body.bind("<Configure>", self._on_body_configure, add="+")
        self.root.after_idle(lambda: self._update_palette_column_width(max(self.body.winfo_width(), self.root.winfo_width())))

        content_row = ttk.Frame(workspace)
        content_row.pack(fill=tk.BOTH, expand=True)

        preview_frame = ttk.Frame(content_row)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(preview_frame, background=APP_BG, bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        zoom_controls = ttk.Frame(preview_frame)
        zoom_controls.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor=tk.SE)
        zoom_out_cell, self.zoom_out_button = self._create_tool_button(
            "zoom_out_button",
            zoom_controls,
            "icon_zoom_out.png",
            lambda: self._set_zoom(zoom_out(self.zoom)),
            "Zoom Out",
        )
        zoom_out_cell.pack(side=tk.LEFT)
        zoom_in_cell, self.zoom_in_button = self._create_tool_button(
            "zoom_in_button",
            zoom_controls,
            "icon_zoom_in.png",
            lambda: self._set_zoom(zoom_in(self.zoom)),
            "Zoom In",
        )
        zoom_in_cell.pack(side=tk.LEFT)

        self.status = ttk.Frame(self.root)
        self.status.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Label(self.status, textvariable=self.process_status_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        status_right = ttk.Frame(self.status)
        status_right.pack(side=tk.RIGHT)
        ttk.Label(status_right, textvariable=self.image_info_var).pack(side=tk.RIGHT)

        self.canvas.bind("<Configure>", lambda _event: self.redraw_canvas())
        self.canvas.bind("<MouseWheel>", self._on_zoom_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind(
            "<ButtonPress-2>",
            lambda event: self._on_canvas_assigned_button_press(event, CANVAS_MOUSE_BUTTON_MIDDLE),
        )
        self.canvas.bind(
            "<B2-Motion>",
            lambda event: self._on_canvas_assigned_button_drag(event, CANVAS_MOUSE_BUTTON_MIDDLE),
        )
        self.canvas.bind(
            "<ButtonRelease-2>",
            lambda event: self._on_canvas_assigned_button_release(event, CANVAS_MOUSE_BUTTON_MIDDLE),
        )
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Leave>", self._on_canvas_leave)
        self.canvas.bind(
            "<ButtonPress-3>",
            lambda event: self._on_canvas_assigned_button_press(event, CANVAS_MOUSE_BUTTON_RIGHT),
        )
        self.canvas.bind(
            "<B3-Motion>",
            lambda event: self._on_canvas_assigned_button_drag(event, CANVAS_MOUSE_BUTTON_RIGHT),
        )
        self.canvas.bind(
            "<ButtonRelease-3>",
            lambda event: self._on_canvas_assigned_button_release(event, CANVAS_MOUSE_BUTTON_RIGHT),
        )

        self.pixel_width_spinbox.bind("<KeyRelease>", self._on_settings_changed, add="+")
        self.pixel_width_spinbox.bind("<<Increment>>", self._on_settings_changed, add="+")
        self.pixel_width_spinbox.bind("<<Decrement>>", self._on_settings_changed, add="+")
        self.palette_reduction_spinbox.bind("<KeyRelease>", self._on_settings_changed, add="+")
        self.palette_reduction_spinbox.bind("<<Increment>>", self._on_settings_changed, add="+")
        self.palette_reduction_spinbox.bind("<<Decrement>>", self._on_settings_changed, add="+")
        self.brush_width_spinbox.bind("<KeyRelease>", self._on_brush_width_changed, add="+")
        self.brush_width_spinbox.bind("<<Increment>>", self._on_brush_width_changed, add="+")
        self.brush_width_spinbox.bind("<<Decrement>>", self._on_brush_width_changed, add="+")
        self.image_filter_strength_spinbox.bind("<KeyRelease>", self._on_image_filter_strength_changed, add="+")
        self.image_filter_strength_spinbox.bind("<<Increment>>", self._on_image_filter_strength_changed, add="+")
        self.image_filter_strength_spinbox.bind("<<Decrement>>", self._on_image_filter_strength_changed, add="+")
        self.outline_adaptive_darken_spinbox.bind("<KeyRelease>", self._on_outline_adaptive_darken_changed, add="+")
        self.outline_adaptive_darken_spinbox.bind("<<Increment>>", self._on_outline_adaptive_darken_changed, add="+")
        self.outline_adaptive_darken_spinbox.bind("<<Decrement>>", self._on_outline_adaptive_darken_changed, add="+")
        self.outline_remove_brightness_threshold_spinbox.bind(
            "<KeyRelease>",
            self._on_outline_remove_brightness_threshold_percent_changed,
            add="+",
        )
        self.outline_remove_brightness_threshold_spinbox.bind(
            "<<Increment>>",
            self._on_outline_remove_brightness_threshold_percent_changed,
            add="+",
        )
        self.outline_remove_brightness_threshold_spinbox.bind(
            "<<Decrement>>",
            self._on_outline_remove_brightness_threshold_percent_changed,
            add="+",
        )

        self._update_palette_adjustment_labels()
        self._refresh_outline_control_states()
        self._bind_shortcuts()

    def _create_section(
        self,
        parent: ttk.Frame,
        title: str,
        *,
        fill_x: bool = True,
        anchor: str | None = None,
    ) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=title.upper(), padding=SECTION_CONTENT_PADDING)
        pack_kwargs: dict[str, object] = {"pady": (0, 10)}
        if fill_x:
            pack_kwargs["fill"] = tk.X
        if anchor is not None:
            pack_kwargs["anchor"] = anchor
        frame.pack(**pack_kwargs)
        return frame

    @staticmethod
    def _coerce_active_color_label(value: object, default: int = ACTIVE_COLOR_DEFAULT_LABEL) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(0, min(0xFFFFFF, parsed))

    @staticmethod
    def _coerce_active_color_slot(value: object) -> str:
        normalized = str(value or "").strip().lower()
        if normalized == ACTIVE_COLOR_SLOT_SECONDARY:
            return ACTIVE_COLOR_SLOT_SECONDARY
        return ACTIVE_COLOR_SLOT_PRIMARY

    @classmethod
    def _coerce_transparent_color_slot(cls, value: object) -> str | None:
        normalized = str(value or "").strip().lower()
        if normalized in {ACTIVE_COLOR_SLOT_PRIMARY, ACTIVE_COLOR_SLOT_SECONDARY}:
            return normalized
        return None

    @classmethod
    def _initial_active_color_state(cls, persisted: dict[str, object]) -> tuple[int, int, str | None, str]:
        primary_label = cls._coerce_active_color_label(persisted.get("primary_color_label"), ACTIVE_COLOR_DEFAULT_LABEL)
        secondary_label = cls._coerce_active_color_label(persisted.get("secondary_color_label"), ACTIVE_COLOR_DEFAULT_LABEL)
        default_transparent = ACTIVE_COLOR_SLOT_SECONDARY if "transparent_color_slot" not in persisted else None
        transparent_slot = cls._coerce_transparent_color_slot(persisted.get("transparent_color_slot", default_transparent))
        active_slot = cls._coerce_active_color_slot(persisted.get("active_color_slot"))
        return (primary_label, secondary_label, transparent_slot, active_slot)

    @staticmethod
    def _other_active_color_slot(slot: str) -> str:
        if slot == ACTIVE_COLOR_SLOT_SECONDARY:
            return ACTIVE_COLOR_SLOT_PRIMARY
        return ACTIVE_COLOR_SLOT_SECONDARY

    def _active_color_slot_value(self) -> str:
        return self._coerce_active_color_slot(getattr(self, "active_color_slot", ACTIVE_COLOR_SLOT_PRIMARY))

    def _transparent_color_slot_value(self) -> str | None:
        return self._coerce_transparent_color_slot(getattr(self, "transparent_color_slot", None))

    def _slot_color_label(self, slot: str) -> int:
        if self._coerce_active_color_slot(slot) == ACTIVE_COLOR_SLOT_SECONDARY:
            return self._coerce_active_color_label(getattr(self, "secondary_color_label", ACTIVE_COLOR_DEFAULT_LABEL))
        return self._coerce_active_color_label(getattr(self, "primary_color_label", ACTIVE_COLOR_DEFAULT_LABEL))

    def _slot_is_transparent(self, slot: str) -> bool:
        return self._transparent_color_slot_value() == self._coerce_active_color_slot(slot)

    def _set_slot_color_label(self, slot: str, label: int) -> None:
        normalized_slot = self._coerce_active_color_slot(slot)
        if normalized_slot == ACTIVE_COLOR_SLOT_SECONDARY:
            self.secondary_color_label = self._coerce_active_color_label(label)
        else:
            self.primary_color_label = self._coerce_active_color_label(label)

    def _set_active_color_slot(self, slot: str, *, persist: bool = True) -> None:
        self.active_color_slot = self._coerce_active_color_slot(slot)
        self._refresh_active_color_preview()
        if persist:
            self._schedule_state_persist_if_ready()

    def _schedule_state_persist_if_ready(self) -> None:
        root = getattr(self, "root", None)
        if root is None or not hasattr(root, "after"):
            return
        self._schedule_state_persist()

    def _assign_palette_color_to_slot(self, slot: str, label: int) -> None:
        normalized_slot = self._coerce_active_color_slot(slot)
        self._set_slot_color_label(normalized_slot, label)
        if self._transparent_color_slot_value() == normalized_slot:
            self.transparent_color_slot = None
        self._refresh_active_color_preview()
        self._schedule_state_persist_if_ready()
        self._refresh_action_states()

    def _swap_active_colors(self) -> None:
        primary_label = self._slot_color_label(ACTIVE_COLOR_SLOT_PRIMARY)
        secondary_label = self._slot_color_label(ACTIVE_COLOR_SLOT_SECONDARY)
        self.primary_color_label = secondary_label
        self.secondary_color_label = primary_label
        transparent_slot = self._transparent_color_slot_value()
        if transparent_slot is not None:
            self.transparent_color_slot = self._other_active_color_slot(transparent_slot)
        self._refresh_active_color_preview()
        self._schedule_state_persist_if_ready()
        self._refresh_action_states()

    def _make_active_color_transparent(self) -> None:
        self.transparent_color_slot = self._active_color_slot_value()
        self._refresh_active_color_preview()
        self._schedule_state_persist_if_ready()
        self._refresh_action_states()

    def _rendered_active_color_slots(self) -> tuple[str, str]:
        front_slot = self._active_color_slot_value()
        return front_slot, self._other_active_color_slot(front_slot)

    def _active_color_preview_template_name(self) -> str:
        front_slot, back_slot = self._rendered_active_color_slots()
        if self._slot_is_transparent(front_slot):
            return ACTIVE_COLOR_PREVIEW_TEMPLATE_FRONT_TRANSPARENT
        if self._slot_is_transparent(back_slot):
            return ACTIVE_COLOR_PREVIEW_TEMPLATE_BACK_TRANSPARENT
        return ACTIVE_COLOR_PREVIEW_TEMPLATE_NONE

    def _active_color_preview_template(self, asset_name: str) -> Image.Image:
        cached = self._active_color_preview_templates.get(asset_name)
        if cached is not None:
            return cached.copy()
        asset_path = self._resource_path(f"assets/{asset_name}")
        with Image.open(asset_path) as image:
            template = image.convert("RGBA")
        self._active_color_preview_templates[asset_name] = template
        return template.copy()

    @staticmethod
    def _label_to_rgba(label: int) -> tuple[int, int, int, int]:
        return ((label >> 16) & 0xFF, (label >> 8) & 0xFF, label & 0xFF, 255)

    def _build_active_color_preview_image(self) -> Image.Image:
        front_slot, back_slot = self._rendered_active_color_slots()
        image = self._active_color_preview_template(self._active_color_preview_template_name())
        front_colour = self._label_to_rgba(self._slot_color_label(front_slot))
        back_colour = self._label_to_rgba(self._slot_color_label(back_slot))
        pixels = image.load()
        for y in range(image.height):
            for x in range(image.width):
                pixel = pixels[x, y]
                if pixel == ACTIVE_COLOR_PREVIEW_PLACEHOLDER_FRONT:
                    pixels[x, y] = front_colour
                elif pixel == ACTIVE_COLOR_PREVIEW_PLACEHOLDER_BACK:
                    pixels[x, y] = back_colour
        return image

    def _refresh_active_color_preview(self) -> None:
        widget = getattr(self, "active_color_preview_label", None)
        if widget is None or not hasattr(widget, "configure"):
            return
        image = ImageTk.PhotoImage(self._build_active_color_preview_image(), master=self.root)
        self._active_color_preview_image_ref = image
        widget.configure(image=image)

    def _active_color_preview_hit_slot(self, x: int, y: int) -> str | None:
        front_slot, back_slot = self._rendered_active_color_slots()
        front_x0, front_y0, front_x1, front_y1 = ACTIVE_COLOR_FRONT_BOUNDS
        if front_x0 <= x <= front_x1 and front_y0 <= y <= front_y1:
            return front_slot
        back_x0, back_y0, back_x1, back_y1 = ACTIVE_COLOR_BACK_BOUNDS
        if back_x0 <= x <= back_x1 and back_y0 <= y <= back_y1:
            return back_slot
        return None

    def _on_active_color_preview_click(self, event: tk.Event) -> None:
        slot = self._active_color_preview_hit_slot(event.x, event.y)
        if slot is None:
            return
        self._set_active_color_slot(slot)

    def _tool_button_icon(self, asset_name: str, *, disabled: bool = False) -> ImageTk.PhotoImage:
        cache_key = (asset_name, disabled)
        cached_icon = self._tool_button_icons.get(cache_key)
        if cached_icon is not None:
            return cached_icon
        asset_path = self._resource_path(f"assets/{asset_name}")
        with Image.open(asset_path) as image:
            rgba = image.convert("RGBA")
            if disabled:
                alpha = rgba.getchannel("A").point(lambda value: (value * 3) // 4)
                rgba = rgba.copy()
                rgba.putalpha(alpha)
            fitted = Image.new("RGBA", (TOOL_BUTTON_WIDTH - 2, TOOL_BUTTON_HEIGHT - 2), (0, 0, 0, 0))
            offset_x = (fitted.width - rgba.width) // 2
            offset_y = (fitted.height - rgba.height) // 2
            fitted.paste(rgba, (offset_x, offset_y), rgba)
            cached_icon = ImageTk.PhotoImage(fitted, master=self.root)
        self._tool_button_icons[cache_key] = cached_icon
        return cached_icon

    def _palette_action_button_icon(self, asset_name: str, *, disabled: bool = False) -> ImageTk.PhotoImage:
        cache_key = (asset_name, disabled)
        cached_icon = self._palette_action_button_icons.get(cache_key)
        if cached_icon is not None:
            return cached_icon
        asset_path = self._resource_path(f"assets/{asset_name}")
        with Image.open(asset_path) as image:
            rgba = image.convert("RGBA")
            if disabled:
                alpha = rgba.getchannel("A").point(lambda value: (value * 3) // 4)
                rgba = rgba.copy()
                rgba.putalpha(alpha)
            fitted = Image.new(
                "RGBA",
                (PALETTE_ACTION_ICON_BUTTON_SIZE - 2, PALETTE_ACTION_ICON_BUTTON_SIZE - 2),
                (0, 0, 0, 0),
            )
            offset_x = (fitted.width - rgba.width) // 2 + PALETTE_ACTION_ICON_OFFSET[0]
            offset_y = (fitted.height - rgba.height) // 2 + PALETTE_ACTION_ICON_OFFSET[1]
            fitted.paste(rgba, (offset_x, offset_y), rgba)
            cached_icon = ImageTk.PhotoImage(fitted, master=self.root)
        self._palette_action_button_icons[cache_key] = cached_icon
        return cached_icon

    def _create_tool_button(
        self,
        widget_name: str,
        parent: ttk.Frame,
        asset_name: str,
        command: object,
        tooltip_text: str,
    ) -> tuple[tk.Frame, ttk.Button]:
        cell = tk.Frame(parent, width=TOOL_BUTTON_WIDTH, height=TOOL_BUTTON_HEIGHT, bg=APP_BORDER, bd=0, highlightthickness=0)
        cell.grid_propagate(False)
        self._tool_button_assets[widget_name] = asset_name
        self._tool_button_enabled[widget_name] = True
        button = ttk.Button(
            cell,
            image=self._tool_button_icon(asset_name),
            command=lambda name=widget_name, callback=command: self._invoke_tool_button(name, callback),
            style="ToolButton.TButton",
        )
        button.place(x=1, y=1, width=TOOL_BUTTON_WIDTH - 2, height=TOOL_BUTTON_HEIGHT - 2)
        button.bind(
            "<ButtonPress-1>",
            lambda event, name=widget_name: "break" if not self._tool_button_enabled.get(name, True) else None,
            add="+",
        )
        self._tool_button_frames[widget_name] = cell
        self._tooltips.append(Tooltip(button, tooltip_text))
        return cell, button

    def _create_toolbar_button(
        self,
        widget_name: str,
        parent: ttk.Frame,
        asset_name: str,
        command: object,
        tooltip_text: str,
        *,
        padx: tuple[int, int] = (0, 0),
    ) -> ttk.Button:
        cell, button = self._create_tool_button(widget_name, parent, asset_name, command, tooltip_text)
        cell.pack(side=tk.LEFT, padx=padx)
        setattr(self, f"{widget_name}_cell", cell)
        return button

    def _create_palette_action_icon_button(
        self,
        widget_name: str,
        parent: ttk.Frame,
        asset_name: str,
        command: object,
        tooltip_text: str,
    ) -> tuple[tk.Frame, ttk.Button]:
        cell = tk.Frame(
            parent,
            width=PALETTE_ACTION_ICON_BUTTON_SIZE,
            height=PALETTE_ACTION_ICON_BUTTON_SIZE,
            bg=APP_BORDER,
            bd=0,
            highlightthickness=0,
        )
        cell.pack_propagate(False)
        self._palette_action_button_assets[widget_name] = asset_name
        self._palette_action_button_enabled[widget_name] = True
        button = ttk.Button(
            cell,
            image=self._palette_action_button_icon(asset_name),
            command=lambda name=widget_name, callback=command: self._invoke_palette_action_button(name, callback),
            style="PaletteActionIcon.TButton",
        )
        button.place(
            x=1,
            y=1,
            width=PALETTE_ACTION_ICON_BUTTON_SIZE - 2,
            height=PALETTE_ACTION_ICON_BUTTON_SIZE - 2,
        )
        button.bind(
            "<ButtonPress-1>",
            lambda event, name=widget_name: "break" if not self._palette_action_button_enabled.get(name, True) else None,
            add="+",
        )
        self._tooltips.append(Tooltip(button, tooltip_text))
        return cell, button

    def _invoke_tool_button(self, widget_name: str, command: object) -> None:
        if not self._tool_button_enabled.get(widget_name, True):
            return
        if callable(command):
            command()

    def _invoke_palette_action_button(self, widget_name: str, command: object) -> None:
        if not self._palette_action_button_enabled.get(widget_name, True):
            return
        if callable(command):
            command()

    def _set_tool_button_enabled(self, widget_name: str, enabled: bool) -> None:
        if not hasattr(self, "_tool_button_enabled"):
            self._tool_button_enabled = {}
        self._tool_button_enabled[widget_name] = enabled
        widget = getattr(self, widget_name, None)
        if widget is None or not hasattr(widget, "configure"):
            return
        if isinstance(widget, ttk.Button):
            asset_name = getattr(self, "_tool_button_assets", {}).get(widget_name)
            if asset_name is not None:
                widget.configure(image=self._tool_button_icon(asset_name, disabled=not enabled))
            if hasattr(widget, "state"):
                widget.state(("!disabled",))
            return
        widget.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def _set_toolbar_zoom_enabled(self, enabled: bool) -> None:
        widget = getattr(self, "toolbar_zoom_dropdown", None)
        if widget is not None and hasattr(widget, "configure"):
            widget.configure(state="readonly" if enabled else tk.DISABLED)

    def _set_palette_action_button_enabled(self, widget_name: str, enabled: bool) -> None:
        if not hasattr(self, "_palette_action_button_enabled"):
            self._palette_action_button_enabled = {}
        self._palette_action_button_enabled[widget_name] = enabled
        widget = getattr(self, widget_name, None)
        if widget is None or not hasattr(widget, "configure"):
            return
        asset_name = getattr(self, "_palette_action_button_assets", {}).get(widget_name)
        if asset_name is None:
            widget.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            return
        widget.configure(
            image=self._palette_action_button_icon(asset_name, disabled=not enabled),
            style="PaletteActionIcon.TButton" if enabled else "PaletteActionIconDisabled.TButton",
        )
        widget_state = getattr(widget, "state", None)
        if callable(widget_state):
            widget_state(("!disabled",))

    def _create_palette_adjustment_row(
        self,
        parent: ttk.LabelFrame,
        *,
        label: str,
        variable: tk.IntVar,
        value_var: tk.StringVar,
        from_: int,
        to: int,
    ) -> tk.Scale:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(row, text=label).pack(side=tk.LEFT)
        ttk.Label(row, textvariable=value_var).pack(side=tk.RIGHT)
        scale = tk.Scale(
            parent,
            from_=from_,
            to=to,
            orient=tk.HORIZONTAL,
            resolution=1,
            showvalue=False,
            variable=variable,
            command=self._on_palette_adjustment_scale,
            activebackground=APP_HOVER_BG,
            background=APP_BG,
            fg=APP_TEXT,
            highlightthickness=0,
            relief=tk.FLAT,
            sliderrelief=tk.FLAT,
            troughcolor=APP_SURFACE_BG,
        )
        scale.pack(fill=tk.X)
        self.palette_adjustment_controls.append(scale)
        return scale

    def _on_body_configure(self, event: tk.Event) -> None:
        self._update_palette_column_width(event.width)

    def _lock_palette_column_width(self) -> None:
        if not hasattr(self, "palette_column"):
            return
        self.palette_column.pack_propagate(False)
        self.palette_column.grid_propagate(False)

    def _update_palette_column_width(self, body_width: int) -> None:
        palette_width = max(PALETTE_COLUMN_MIN_WIDTH, round(body_width * PALETTE_COLUMN_WIDTH_RATIO))
        if hasattr(self, "palette_column"):
            self.palette_column.configure(width=palette_width)

    def _on_palette_adjustment_scale(self, _value: str | None = None) -> None:
        self._update_palette_adjustment_labels()
        self._on_settings_changed()

    def _update_palette_adjustment_labels(self) -> None:
        self.palette_brightness_value_var.set(f"{int(self.palette_brightness_var.get())}%")
        self.palette_contrast_value_var.set(f"{int(self.palette_contrast_var.get())}%")
        self.palette_hue_value_var.set(f"{int(self.palette_hue_var.get())}%")
        self.palette_saturation_value_var.set(f"{int(self.palette_saturation_var.get())}%")

    def _clear_processed_results(self) -> None:
        self.downsample_result = None
        self.palette_result = None
        self.downsample_display_image = None
        self.palette_display_image = None
        self.prepared_input_cache = None
        self.prepared_input_cache_key = None
        self.transparent_colors = set()
        self._palette_selection_indices = set()
        self._palette_selection_anchor_index = None
        self._clear_canvas_selection_state()

    def _palette_adjustments(self, settings: PreviewSettings | None = None) -> PaletteAdjustments:
        session = getattr(self, "session", None)
        current = settings or getattr(session, "current", PreviewSettings())
        return PaletteAdjustments(
            brightness=current.palette_brightness,
            contrast=current.palette_contrast,
            hue=current.palette_hue,
            saturation=current.palette_saturation,
        )

    def _current_palette_source_labels(self) -> tuple[list[int], str]:
        active_palette = getattr(self, "active_palette", None)
        if active_palette:
            return list(active_palette), getattr(self, "active_palette_source", "") or "Active"
        advanced_palette_preview = getattr(self, "advanced_palette_preview", None)
        if advanced_palette_preview is not None:
            return advanced_palette_preview.labels(), advanced_palette_preview.source_label or "Generated"
        current = self._current_output_result()
        if current is None:
            return ([], "none")
        if current.structured_palette is not None:
            source = current.structured_palette.source_label or current.stats.stage.title()
            return current.structured_palette.labels(), source
        if current.display_palette_labels:
            return list(current.display_palette_labels), current.stats.stage.title()
        return ([], "none")

    def _adjusted_palette_cache_token(self, adjustments: PaletteAdjustments) -> tuple[object, ...]:
        selection = tuple(sorted(self._palette_adjustment_selection_indices() or ()))
        current = self._current_output_result()
        return (
            adjustments.brightness,
            adjustments.contrast,
            adjustments.hue,
            adjustments.saturation,
            selection,
            id(getattr(self, "active_palette", None)) if getattr(self, "active_palette", None) is not None else None,
            id(getattr(self, "advanced_palette_preview", None)) if getattr(self, "advanced_palette_preview", None) is not None else None,
            id(current) if current is not None else None,
            id(current.structured_palette) if current is not None and current.structured_palette is not None else None,
        )

    def _current_base_structured_palette(self) -> StructuredPalette | None:
        workspace = getattr(self, "workspace", None) or ColorWorkspace()
        active_palette = getattr(self, "active_palette", None)
        if active_palette:
            return structured_palette_from_override(
                active_palette,
                workspace=workspace,
                source_label=getattr(self, "active_palette_source", "") or "Active",
            )
        advanced_palette_preview = getattr(self, "advanced_palette_preview", None)
        if advanced_palette_preview is not None:
            return clone_structured_palette(advanced_palette_preview)
        current = self._current_output_result()
        if current is not None and current.structured_palette is not None:
            return clone_structured_palette(current.structured_palette)
        if current is not None and current.display_palette_labels:
            return structured_palette_from_override(
                list(current.display_palette_labels),
                workspace=workspace,
                source_label=current.stats.stage.title(),
            )
        return None

    def _current_adjusted_structured_palette(self, settings: PreviewSettings | None = None) -> StructuredPalette | None:
        adjustments = self._palette_adjustments(settings)
        cache_key = self._adjusted_palette_cache_token(adjustments)
        cached_key = getattr(self, "_adjusted_palette_cache_key", None)
        cached_palette = getattr(self, "_adjusted_palette_cache", None)
        if cached_key == cache_key and cached_palette is not None:
            return clone_structured_palette(cached_palette)
        base_palette = self._current_base_structured_palette()
        if base_palette is None or base_palette.palette_size() == 0:
            self._adjusted_palette_cache_key = cache_key
            self._adjusted_palette_cache = None
            return None
        if adjustments.is_neutral():
            adjusted_palette = base_palette
        else:
            adjusted_palette = adjust_structured_palette(
                base_palette,
                adjustments,
                workspace=getattr(self, "workspace", None) or ColorWorkspace(),
                selected_indices=self._palette_adjustment_selection_indices(),
            )
        self._adjusted_palette_cache_key = cache_key
        self._adjusted_palette_cache = clone_structured_palette(adjusted_palette)
        return adjusted_palette

    def _has_palette_source(self) -> bool:
        palette, _source = self._current_palette_source_labels()
        return bool(palette)

    def _adjusted_palette_source_label(self, palette: StructuredPalette, settings: PreviewSettings | None = None) -> str:
        source = palette.source_label or "Palette"
        if self._palette_adjustments(settings).is_neutral():
            return source
        if self._palette_adjustment_selection_indices():
            return f"{source} (Adjusted Selection)"
        return f"{source} (Adjusted)"

    def _palette_adjustment_selection_indices(self) -> set[int] | None:
        palette, _source = self._current_palette_source_labels()
        if not palette:
            return None
        selection = getattr(self, "_palette_selection_indices", set())
        valid = {index for index in selection if 0 <= index < len(palette)}
        return valid or None

    def _reset_palette_adjustments_to_neutral(self) -> None:
        if not hasattr(self, "session"):
            return
        neutral = replace(
            self.session.current,
            palette_brightness=0,
            palette_contrast=100,
            palette_hue=0,
            palette_saturation=100,
        )
        self.session.current = neutral
        self._sync_controls_from_settings(neutral)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _event: self.open_image())
        self.root.bind("<Control-s>", lambda _event: self.save_processed_image())
        self.root.bind("<Control-S>", lambda _event: self.save_processed_image_as())
        self.root.bind("<Control-z>", lambda _event: self.undo())
        self.root.bind("<Control-y>", lambda _event: self.redo())
        self.root.bind("<Control-Y>", lambda _event: self.redo())
        self.root.bind("<Control-c>", lambda _event: self._copy_image_selection())
        self.root.bind("<Control-x>", lambda _event: self._cut_image_selection())
        self.root.bind("<Control-v>", lambda _event: self._paste_image_selection())
        self.root.bind("<Delete>", lambda _event: self._delete_image_selection())
        self.root.bind("<Escape>", self._on_escape_key, add="+")
        self.root.bind("<Return>", self._on_return_key, add="+")
        self.root.bind("<BackSpace>", self._on_backspace_key, add="+")
        self.root.bind("<F5>", lambda _event: self.downsample_current_image())
        self.root.bind("<F6>", lambda _event: self.reduce_palette_current_image())
        self.root.bind("<Control-1>", lambda _event: self._set_view("original"))
        self.root.bind("<Control-2>", lambda _event: self._set_view("processed"))
        self.root.bind("<Control-0>", lambda _event: self.zoom_fit())
        self.root.bind("<Control-equal>", lambda _event: self._set_zoom(zoom_in(self.zoom)))
        self.root.bind("<Control-minus>", lambda _event: self._set_zoom(zoom_out(self.zoom)))

    def _on_escape_key(self, _event: tk.Event | None = None) -> str | None:
        if self._cancel_polygon_lasso():
            self.process_status_var.set("Cancelled the polygonal lasso.")
            return "break"
        if self._cancel_floating_selection():
            return "break"
        if getattr(self, "_image_selection", None) is not None:
            self._clear_canvas_selection()
            return "break"
        return None

    def _on_return_key(self, _event: tk.Event | None = None) -> str | None:
        if self._commit_floating_selection():
            return "break"
        return None

    def _on_backspace_key(self, _event: tk.Event | None = None) -> str | None:
        if self._canvas_tool_mode_value() != CANVAS_TOOL_MODE_POLYGON_LASSO or not self._lasso_points:
            return None
        self._lasso_points.pop()
        if not self._lasso_points:
            self._lasso_hover_point = None
            self._lasso_hover_point_canvas = None
        self._redraw_selection_overlays_only()
        self._refresh_action_states()
        return "break"

    def open_image(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PNG images", "*.png")])
        if path:
            self._open_image_path(Path(path))

    def _open_image_path(self, path: Path) -> None:
        try:
            self.source_path = path
            self.original_display_image = load_png_rgba_image(str(path))
            self.original_grid = image_to_rgb_grid(self.original_display_image)
            self.comparison_original_image = None
            self._comparison_original_key = None
            self._clear_processed_results()
            self.transparent_colors = set()
            self._palette_selection_indices = set()
            self._palette_selection_anchor_index = None
            self._palette_hit_regions = []
            self._displayed_palette = []
            self._set_pick_mode(None)
            self._clear_palette_undo_state()
            self._clear_palette_redo_state()
            self.quick_compare_active = False
            self._mouse_button_action_state = None
            self.pan_x = 0
            self.pan_y = 0
            original_result = process_result_from_original(self.original_display_image, self.original_grid)
            self.downsample_result = original_result
            self.prepared_input_cache = original_result.prepared_input
            self.prepared_input_cache_key = ("original", path)
            self._refresh_output_display_images()
            self.image_state = "processed_current"
            self._record_recent_file(path)
            self._set_view("processed")
            self.process_status_var.set(
                f"Loaded {path.name}: {self.original_display_image.width}x{self.original_display_image.height}. You can edit directly or adjust pixel size and downsample."
            )
            self.root.update_idletasks()
            self.zoom_fit()
            self._update_scale_info()
            self._update_palette_strip()
            self.redraw_canvas()
            self._refresh_action_states()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed to load image", str(exc))

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.delete(0, tk.END)
        if not self.recent_files:
            self.recent_menu.add_command(label="(empty)", state=tk.DISABLED)
            return
        for path in self.recent_files:
            self.recent_menu.add_command(label=path, command=lambda value=path: self._open_recent(value))

    def _open_recent(self, path_value: str) -> None:
        path = Path(path_value)
        if not path.exists():
            messagebox.showwarning("Missing file", f"Recent file not found:\n{path}")
            self.recent_files = [item for item in self.recent_files if item != path_value]
            self._refresh_recent_menu()
            self._schedule_state_persist()
            return
        self._open_image_path(path)

    def _record_recent_file(self, path: Path) -> None:
        normalized = str(path)
        self.recent_files = [item for item in self.recent_files if item != normalized]
        self.recent_files.insert(0, normalized)
        self.recent_files = self.recent_files[:MAX_RECENT_FILES]
        self._refresh_recent_menu()
        self._schedule_state_persist()

    def _populate_builtin_palette_menu(self) -> None:
        menu = self._menu_items["built_in_palettes"]
        menu.delete(0, tk.END)
        if not self.builtin_palette_entries:
            menu.add_command(label="(none)", state=tk.DISABLED)
            return

        submenus: dict[tuple[str, ...], tk.Menu] = {(): menu}
        for entry in self.builtin_palette_entries:
            parent_path: tuple[str, ...] = ()
            parent_menu = menu
            for folder_label in entry.menu_path:
                parent_path = (*parent_path, folder_label)
                if parent_path not in submenus:
                    submenu = self._new_menu(parent_menu)
                    parent_menu.add_cascade(label=folder_label, menu=submenu)
                    submenus[parent_path] = submenu
                parent_menu = submenus[parent_path]
            parent_menu.add_command(label=entry.label, command=lambda value=entry: self._select_builtin_palette(value))

    def _clear_builtin_palette_preview(self) -> None:
        if getattr(self, "_builtin_palette_preview_entry", None) is None:
            return
        self._builtin_palette_preview_entry = None
        self._update_palette_strip()

    def _update_palette_dropdown_label(self) -> None:
        variable = getattr(self, "palette_dropdown_var", None)
        if variable is None:
            return
        active_path = getattr(self, "active_palette_path", None)
        if active_path:
            entry = self._builtin_palette_by_path.get(str(active_path))
            if entry is not None:
                variable.set(entry.source_label)
                return
        variable.set("Built-in palettes")

    def _refresh_palette_browser_button_state(self) -> None:
        button = getattr(self, "palette_dropdown_button", None)
        if button is None or not hasattr(button, "configure"):
            return
        button.configure(state=tk.NORMAL if self.builtin_palette_entries else tk.DISABLED)
        self._update_palette_dropdown_label()

    def _toggle_palette_browser(self) -> None:
        if getattr(self, "_palette_browser_window", None) is None:
            self._open_palette_browser()
        else:
            self._close_palette_browser()

    def _open_palette_browser(self) -> None:
        if getattr(self, "_palette_browser_window", None) is not None:
            self._position_palette_browser()
            return
        button = getattr(self, "palette_dropdown_button", None)
        if button is None or not self.builtin_palette_entries:
            return
        browser = tk.Toplevel(self.root, bg=APP_BORDER, bd=0, highlightthickness=0)
        browser.withdraw()
        browser.overrideredirect(True)
        browser.transient(self.root)
        browser.bind("<Escape>", self._on_palette_browser_escape, add="+")
        self._palette_browser_window = browser

        shell = tk.Frame(browser, bg=APP_BORDER, bd=0, highlightthickness=0)
        shell.pack(fill=tk.BOTH, expand=True)
        content = tk.Frame(shell, bg=APP_BG, bd=0, highlightthickness=0)
        content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        search_entry = ttk.Entry(content, textvariable=self._palette_browser_search_var, style="Compact.TEntry")
        search_entry.pack(fill=tk.X, padx=8, pady=(8, 6))
        search_entry.bind("<Escape>", self._on_palette_browser_escape, add="+")
        search_entry.bind("<Enter>", lambda _event: self._clear_builtin_palette_preview(), add="+")
        self._bind_palette_browser_mouse_wheel(search_entry)
        self._palette_browser_search_entry = search_entry

        list_shell = tk.Frame(content, bg=APP_BG, bd=0, highlightthickness=0)
        list_shell.pack(fill=tk.BOTH, expand=True, padx=8)
        list_canvas = tk.Canvas(list_shell, bg=APP_BG, bd=0, highlightthickness=0)
        list_canvas.configure(yscrollincrement=20)
        list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar = ttk.Scrollbar(list_shell, orient=tk.VERTICAL, command=list_canvas.yview)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        list_canvas.configure(yscrollcommand=list_scrollbar.set)
        list_inner = tk.Frame(list_canvas, bg=APP_BG, bd=0, highlightthickness=0)
        list_window = list_canvas.create_window((0, 0), window=list_inner, anchor="nw")
        list_inner.bind(
            "<Configure>",
            lambda _event, canvas=list_canvas: canvas.configure(scrollregion=canvas.bbox("all") or (0, 0, 0, 0)),
            add="+",
        )
        list_canvas.bind(
            "<Configure>",
            lambda event, canvas=list_canvas, window_id=list_window: canvas.itemconfigure(window_id, width=event.width),
            add="+",
        )
        list_canvas.bind("<MouseWheel>", self._on_palette_browser_mouse_wheel, add="+")
        list_canvas.bind("<Leave>", lambda _event: self._clear_builtin_palette_preview(), add="+")
        list_inner.bind("<Leave>", lambda _event: self._clear_builtin_palette_preview(), add="+")
        self._bind_palette_browser_mouse_wheel(list_shell)
        self._bind_palette_browser_mouse_wheel(list_canvas)
        self._bind_palette_browser_mouse_wheel(list_scrollbar)
        self._bind_palette_browser_mouse_wheel(list_inner)
        self._palette_browser_list_canvas = list_canvas
        self._palette_browser_list_inner = list_inner

        footer = tk.Frame(content, bg=APP_BG, bd=0, highlightthickness=0)
        footer.pack(fill=tk.X, padx=8, pady=(6, 8))
        footer.bind("<Enter>", lambda _event: self._clear_builtin_palette_preview(), add="+")
        self._bind_palette_browser_mouse_wheel(footer)
        load_button = ttk.Button(footer, text="Load Palette...", style="Compact.TButton", command=self._load_palette_file_from_browser)
        load_button.pack(side=tk.LEFT)
        close_button = ttk.Button(footer, text="Close", style="Compact.TButton", command=self._close_palette_browser)
        close_button.pack(side=tk.RIGHT)
        load_button.bind("<Enter>", lambda _event: self._clear_builtin_palette_preview(), add="+")
        close_button.bind("<Enter>", lambda _event: self._clear_builtin_palette_preview(), add="+")
        self._bind_palette_browser_mouse_wheel(load_button)
        self._bind_palette_browser_mouse_wheel(close_button)

        self._refresh_palette_browser_rows()
        self._position_palette_browser()
        browser.deiconify()
        browser.lift()
        search_entry.focus_set()

        self._bind_palette_browser_root_clicks()
        if getattr(self, "_palette_browser_search_trace_id", None) is None:
            self._palette_browser_search_trace_id = self._palette_browser_search_var.trace_add(
                "write",
                lambda *_args: self._refresh_palette_browser_rows(),
            )

    def _close_palette_browser(self) -> None:
        browser = getattr(self, "_palette_browser_window", None)
        if browser is None:
            return
        self._unbind_palette_browser_root_clicks()
        self._clear_builtin_palette_preview()
        self._palette_browser_displayed_entries = []
        self._palette_browser_empty_label = None
        self._palette_browser_window = None
        for attribute_name in (
            "_palette_browser_search_entry",
            "_palette_browser_list_canvas",
            "_palette_browser_list_inner",
        ):
            if hasattr(self, attribute_name):
                setattr(self, attribute_name, None)
        if browser.winfo_exists():
            browser.destroy()

    def _bind_palette_browser_root_clicks(self) -> None:
        root = getattr(self, "root", None)
        if root is None:
            return
        self._unbind_palette_browser_root_clicks()
        for sequence in ("<ButtonPress-1>", "<ButtonPress-2>", "<ButtonPress-3>"):
            bind_id = root.bind(sequence, self._on_palette_browser_root_click, add="+")
            self._palette_browser_root_bind_ids[sequence] = bind_id

    def _unbind_palette_browser_root_clicks(self) -> None:
        root = getattr(self, "root", None)
        if root is None:
            self._palette_browser_root_bind_ids = {}
            return
        for sequence, bind_id in list(getattr(self, "_palette_browser_root_bind_ids", {}).items()):
            root.unbind(sequence, bind_id)
        self._palette_browser_root_bind_ids = {}

    def _palette_browser_contains_widget(self, widget: object) -> bool:
        browser = getattr(self, "_palette_browser_window", None)
        if browser is None:
            return False
        current = widget
        while current is not None:
            if current == browser:
                return True
            current = getattr(current, "master", None)
        return False

    def _button_contains_widget(self, widget: object, button_name: str) -> bool:
        button = getattr(self, button_name, None)
        current = widget
        while current is not None:
            if current == button:
                return True
            current = getattr(current, "master", None)
        return False

    def _on_palette_browser_root_click(self, event: tk.Event | None = None) -> None:
        widget = getattr(event, "widget", None)
        if self._palette_browser_contains_widget(widget) or self._button_contains_widget(widget, "palette_dropdown_button"):
            return
        self._close_palette_browser()

    def _on_palette_browser_escape(self, _event: tk.Event | None = None) -> str:
        self._close_palette_browser()
        return "break"

    def _position_palette_browser(self) -> None:
        browser = getattr(self, "_palette_browser_window", None)
        button = getattr(self, "palette_dropdown_button", None)
        root = getattr(self, "root", None)
        if browser is None or button is None or root is None:
            return
        root.update_idletasks()
        width, height, x_position, y_position = self._compute_palette_browser_geometry()
        browser.geometry(f"{width}x{height}+{x_position}+{y_position}")

    def _compute_palette_browser_geometry(self) -> tuple[int, int, int, int]:
        button = getattr(self, "palette_dropdown_button", None)
        root = getattr(self, "root", None)
        if button is None or root is None:
            return (PALETTE_BROWSER_WIDTH, PALETTE_BROWSER_HEIGHT, PALETTE_BROWSER_MARGIN, PALETTE_BROWSER_MARGIN)
        screen_width = max(PALETTE_BROWSER_WIDTH + (PALETTE_BROWSER_MARGIN * 2), int(root.winfo_screenwidth()))
        screen_height = max(PALETTE_BROWSER_HEIGHT + (PALETTE_BROWSER_MARGIN * 2), int(root.winfo_screenheight()))
        width = min(PALETTE_BROWSER_WIDTH, screen_width - (PALETTE_BROWSER_MARGIN * 2))
        height = min(PALETTE_BROWSER_HEIGHT, screen_height - (PALETTE_BROWSER_MARGIN * 2))
        button_x = int(button.winfo_rootx())
        button_y = int(button.winfo_rooty())
        button_width = int(button.winfo_width())
        button_height = int(button.winfo_height())
        x_position = button_x - width - PALETTE_BROWSER_GAP
        y_position = button_y
        if x_position < PALETTE_BROWSER_MARGIN:
            x_position = max(
                PALETTE_BROWSER_MARGIN,
                min(button_x + button_width - width, screen_width - width - PALETTE_BROWSER_MARGIN),
            )
            y_position = button_y + button_height + PALETTE_BROWSER_GAP
            if y_position + height > screen_height - PALETTE_BROWSER_MARGIN:
                y_position = button_y - height - PALETTE_BROWSER_GAP
        x_position = max(PALETTE_BROWSER_MARGIN, min(x_position, screen_width - width - PALETTE_BROWSER_MARGIN))
        y_position = max(PALETTE_BROWSER_MARGIN, min(y_position, screen_height - height - PALETTE_BROWSER_MARGIN))
        return width, height, x_position, y_position

    def _filtered_builtin_palette_groups(self, query: str | None = None) -> list[tuple[str, list[PaletteCatalogEntry]]]:
        normalized_query = (query or "").strip().lower()
        grouped: dict[str, list[PaletteCatalogEntry]] = {}
        ordered_groups: list[str] = []
        for entry in self.builtin_palette_entries:
            category = " / ".join(entry.menu_path) if entry.menu_path else "General"
            haystack = f"{entry.label} {' / '.join(entry.menu_path)}".lower()
            if normalized_query and normalized_query not in haystack:
                continue
            if category not in grouped:
                grouped[category] = []
                ordered_groups.append(category)
            grouped[category].append(entry)
        return [(category, grouped[category]) for category in ordered_groups if grouped[category]]

    def _refresh_palette_browser_rows(self) -> None:
        container = getattr(self, "_palette_browser_list_inner", None)
        if container is None:
            return
        for child in list(container.winfo_children()):
            child.destroy()
        self._palette_browser_displayed_entries = []
        self._palette_browser_empty_label = None

        groups = self._filtered_builtin_palette_groups(self._palette_browser_search_var.get())
        if not groups:
            self._clear_builtin_palette_preview()
            empty_label = tk.Label(
                container,
                text="No palettes match your search.",
                bg=APP_BG,
                fg=APP_MUTED_TEXT,
                anchor="w",
                justify=tk.LEFT,
            )
            empty_label.pack(fill=tk.X, padx=4, pady=(4, 0))
            self._palette_browser_empty_label = empty_label
            return

        for category, entries in groups:
            header = tk.Label(
                container,
                text=category,
                bg=APP_BG,
                fg=APP_MUTED_TEXT,
                anchor="w",
                justify=tk.LEFT,
            )
            header.pack(fill=tk.X, padx=4, pady=(6, 2))
            self._bind_palette_browser_mouse_wheel(header)
            for entry in entries:
                self._palette_browser_displayed_entries.append(entry)
                row = tk.Frame(container, bg=APP_SURFACE_BG, bd=0, highlightthickness=0)
                row.pack(fill=tk.X, padx=0, pady=(0, 4))
                swatch_strip = tk.Canvas(
                    row,
                    width=PALETTE_BROWSER_SWATCH_STRIP_COUNT * PALETTE_BROWSER_SWATCH_STRIP_SIZE,
                    height=PALETTE_BROWSER_SWATCH_STRIP_SIZE,
                    bg=APP_SURFACE_BG,
                    bd=0,
                    highlightthickness=0,
                )
                swatch_strip.pack(side=tk.LEFT, padx=(6, 6), pady=6)
                self._bind_palette_browser_mouse_wheel(row)
                self._bind_palette_browser_mouse_wheel(swatch_strip)
                for index, label in enumerate(entry.colors[:PALETTE_BROWSER_SWATCH_STRIP_COUNT]):
                    x0 = index * PALETTE_BROWSER_SWATCH_STRIP_SIZE
                    swatch_strip.create_rectangle(
                        x0,
                        0,
                        x0 + PALETTE_BROWSER_SWATCH_STRIP_SIZE,
                        PALETTE_BROWSER_SWATCH_STRIP_SIZE,
                        fill=f"#{label:06X}",
                        outline="",
                    )
                text_frame = tk.Frame(row, bg=APP_SURFACE_BG, bd=0, highlightthickness=0)
                text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), pady=4)
                name_label = tk.Label(
                    text_frame,
                    text=entry.label,
                    bg=APP_SURFACE_BG,
                    fg=APP_TEXT,
                    anchor="w",
                    justify=tk.LEFT,
                )
                name_label.pack(fill=tk.X)
                self._bind_palette_browser_mouse_wheel(text_frame)
                self._bind_palette_browser_mouse_wheel(name_label)
                path_text = " / ".join(entry.menu_path) if entry.menu_path else "General"
                path_label = tk.Label(
                    text_frame,
                    text=path_text,
                    bg=APP_SURFACE_BG,
                    fg=APP_MUTED_TEXT,
                    anchor="w",
                    justify=tk.LEFT,
                )
                path_label.pack(fill=tk.X)
                self._bind_palette_browser_mouse_wheel(path_label)
                for widget in (row, swatch_strip, text_frame, name_label, path_label):
                    widget.bind("<Enter>", lambda _event, value=entry: self._preview_builtin_palette(value), add="+")
                    widget.bind("<ButtonPress-1>", lambda _event, value=entry: self._select_builtin_palette_from_browser(value), add="+")
        if getattr(self, "_builtin_palette_preview_entry", None) not in self._palette_browser_displayed_entries:
            self._clear_builtin_palette_preview()

    def _preview_builtin_palette(self, entry: PaletteCatalogEntry | None) -> None:
        if entry is None:
            self._clear_builtin_palette_preview()
            return
        if getattr(self, "_builtin_palette_preview_entry", None) == entry:
            return
        self._builtin_palette_preview_entry = entry
        self._update_palette_strip()

    def _bind_palette_browser_mouse_wheel(self, widget: tk.Misc | None) -> None:
        if widget is None:
            return
        widget.bind("<MouseWheel>", self._on_palette_browser_mouse_wheel, add="+")

    def _select_builtin_palette_from_browser(self, entry: PaletteCatalogEntry) -> None:
        self._close_palette_browser()
        self._select_builtin_palette(entry)

    def _load_palette_file_from_browser(self) -> None:
        self._close_palette_browser()
        self.load_palette_file()

    def _on_palette_browser_mouse_wheel(self, event: tk.Event) -> str:
        canvas = getattr(self, "_palette_browser_list_canvas", None)
        if canvas is None:
            return "break"
        delta = getattr(event, "delta", 0)
        if delta == 0:
            return "break"
        canvas.yview_scroll(-1 if delta > 0 else 1, "units")
        return "break"

    def _on_palette_mouse_wheel(self, event: tk.Event) -> str:
        canvas = getattr(self, "palette_canvas", None)
        if canvas is None:
            return "break"
        delta = getattr(event, "delta", 0)
        if delta == 0:
            return "break"
        canvas.yview_scroll(-1 if delta > 0 else 1, "units")
        return "break"

    def _populate_palette_sort_menu(self) -> None:
        menu = self._menu_items["palette_sort"]
        menu.delete(0, tk.END)
        for label, mode in PALETTE_SORT_OPTIONS:
            menu.add_command(label=label, command=lambda value=mode: self.sort_current_palette(value))
        if self._palette_sort_reset_labels is not None:
            menu.add_separator()
            menu.add_command(label="Reset To Source Order", command=self.reset_palette_sort_order)

    def _restore_active_palette(self, persisted: dict[str, object]) -> bool:
        path_value = persisted.get("active_palette_path")
        if not isinstance(path_value, str) or not path_value:
            return False

        resolved_path = self._resolve_palette_path(path_value)
        if resolved_path is None:
            return False

        entry = self._builtin_palette_by_path.get(resolved_path)
        try:
            palette = list(entry.colors) if entry is not None else load_palette(Path(resolved_path))
        except Exception:  # noqa: BLE001
            return False

        source_value = persisted.get("active_palette_source")
        if entry is not None:
            source = f"Built-in: {entry.source_label}"
        elif isinstance(source_value, str) and source_value:
            source = source_value
        else:
            source = f"Loaded: {Path(resolved_path).name}"
        self._set_active_palette(palette, source, resolved_path)
        return True

    def _load_default_palette(self) -> bool:
        resolved_path = self._resolve_palette_path(self._resource_path(DEFAULT_PALETTE_RESOURCE))
        if resolved_path is None:
            return False
        entry = self._builtin_palette_by_path.get(resolved_path)
        try:
            palette = list(entry.colors) if entry is not None else load_palette(Path(resolved_path))
        except Exception:  # noqa: BLE001
            return False
        source = f"Built-in: {entry.source_label}" if entry is not None else f"Loaded: {Path(resolved_path).name}"
        self._set_active_palette(palette, source, resolved_path)
        return True

    @staticmethod
    def _resolve_palette_path(path_value: str | Path | None) -> str | None:
        if path_value in (None, ""):
            return None
        path = Path(path_value)
        if not path.exists():
            return None
        return str(path.resolve())

    def _set_active_palette(
        self,
        palette: list[int] | tuple[int, ...] | None,
        source: str,
        path_value: str | None,
    ) -> None:
        self.active_palette = list(palette) if palette else None
        self.active_palette_source = source
        self.active_palette_path = path_value
        self._palette_selection_indices = set()
        self._palette_selection_anchor_index = None
        self._update_palette_dropdown_label()
        if not source.startswith("Sorted:"):
            self._palette_sort_reset_labels = None
            self._palette_sort_reset_source = None
            self._palette_sort_reset_path = None
        if hasattr(self, "_menu_items") and "palette_sort" in self._menu_items:
            self._populate_palette_sort_menu()

    def _apply_active_palette(
        self,
        palette: list[int] | tuple[int, ...] | None,
        source: str,
        path_value: str | None,
        *,
        message: str | None,
        mark_stale: bool = True,
        capture_undo: bool = False,
    ) -> None:
        if capture_undo:
            self._capture_palette_undo_state()
        else:
            self._clear_palette_undo_state()
            self._clear_palette_redo_state()
        self._set_active_palette(palette, source, path_value)
        if mark_stale:
            self._mark_output_stale(message)
        elif message:
            self.process_status_var.set(message)
        self._update_palette_strip()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _set_structured_palette_preview(self, palette: StructuredPalette | None) -> None:
        self._set_active_palette(None, "", None)
        self.advanced_palette_preview = clone_structured_palette(palette)
        if hasattr(self, "_menu_items") and "palette_sort" in self._menu_items:
            self._populate_palette_sort_menu()

    def _apply_structured_palette_preview(
        self,
        palette: StructuredPalette,
        *,
        message: str | None,
        mark_stale: bool = True,
        capture_undo: bool = False,
    ) -> None:
        if capture_undo:
            self._capture_palette_undo_state()
        else:
            self._clear_palette_undo_state()
            self._clear_palette_redo_state()
        self._set_structured_palette_preview(palette)
        if mark_stale:
            self._mark_output_stale(message)
        elif message:
            self.process_status_var.set(message)
        self._update_palette_strip()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _select_builtin_palette(self, entry: PaletteCatalogEntry) -> None:
        self._clear_builtin_palette_preview()
        message = f"Selected built-in palette {entry.label} ({len(entry.colors)} colours). Click Apply Palette to use it."
        self._apply_active_palette(
            entry.colors,
            f"Built-in: {entry.source_label}",
            str(entry.path),
            message=message,
        )

    def clear_active_palette(self) -> None:
        if not self.active_palette:
            return
        self._apply_active_palette(None, "", None, message="Cleared the active palette.")
        self._update_palette_strip()

    def _selection_threshold_percent(self) -> int:
        return coerce_selection_threshold(self.selection_threshold_var.get())

    def _on_selection_threshold_changed(self) -> None:
        threshold = self._selection_threshold_percent()
        if self.selection_threshold_var.get() != threshold:
            self.selection_threshold_var.set(threshold)
        self.process_status_var.set(f"Selection threshold set to {threshold}%.")
        self._schedule_state_persist()
        self._refresh_action_states()

    def select_current_palette(self, mode: str) -> None:
        if mode not in PALETTE_SELECT_MODES:
            raise ValueError(f"Unsupported palette selection mode: {mode}")
        palette, _source = self._get_display_palette()
        if not palette:
            self.process_status_var.set("There is no current palette to select.")
            return
        threshold = self._selection_threshold_percent()
        indices = select_palette_indices(palette, mode, threshold, self.workspace)
        if hasattr(self, "_reset_palette_ctrl_drag_state"):
            self._reset_palette_ctrl_drag_state()
        self._palette_selection_indices = set(indices)
        self._palette_selection_anchor_index = indices[0] if indices else None
        self._update_palette_strip()
        self._refresh_action_states()
        if mode == PALETTE_SELECT_SIMILARITY_NEAR_DUPLICATES and not indices:
            self.process_status_var.set(f"No near-duplicate palette colours found at {threshold}%.")
            return
        label = PALETTE_SELECT_LABELS[mode]
        count = len(indices)
        self.process_status_var.set(f"Selected {count} palette colour{'s' if count != 1 else ''} by {label} at {threshold}%.")

    def sort_current_palette(self, mode: str) -> None:
        if mode not in PALETTE_SORT_MODES:
            raise ValueError(f"Unsupported palette sort mode: {mode}")
        palette, _source = self._get_display_palette()
        if not palette:
            self.process_status_var.set("There is no current palette to sort.")
            return
        if self._palette_sort_reset_labels is None:
            reset_source = self._palette_sort_source()
            if reset_source is not None:
                self._palette_sort_reset_labels = list(reset_source[0])
                self._palette_sort_reset_source = reset_source[1]
                self._palette_sort_reset_path = reset_source[2]
        sorted_palette = sort_palette_labels(palette, mode, self.workspace)
        label = PALETTE_SORT_LABELS[mode]
        self._apply_active_palette(
            sorted_palette,
            f"Sorted: {label}",
            None,
            message=f"Sorted current palette by {label}. Click Apply Palette to update the preview.",
            capture_undo=True,
        )

    def _on_palette_sort_combobox_changed(self, _event: object = None) -> None:
        selected = self.palette_sort_var.get()
        mode_map = {label: mode for label, mode in PALETTE_SORT_OPTIONS}
        mode = mode_map.get(selected)
        if mode is not None:
            self.sort_current_palette(mode)
        self.palette_sort_var.set(self._palette_sort_display_labels[0])

    def reset_palette_sort_order(self) -> None:
        if self._palette_sort_reset_labels is None:
            self.process_status_var.set("There is no source palette order to restore.")
            return
        source = self._palette_sort_reset_source or "Source"
        self._apply_active_palette(
            list(self._palette_sort_reset_labels),
            source,
            self._palette_sort_reset_path,
            message=f"Reset current palette to source order from {source}. Click Apply Palette to update the preview.",
            capture_undo=True,
        )

    def _palette_sort_source(self) -> tuple[list[int], str, str | None] | None:
        if self.active_palette is not None and self.active_palette_path is not None:
            return (list(self.active_palette), self.active_palette_source or "Active", self.active_palette_path)
        if self.active_palette is not None and not self.active_palette_source.startswith(("Sorted:", "Edited Palette")):
            return (list(self.active_palette), self.active_palette_source or "Active", self.active_palette_path)
        if self.advanced_palette_preview is not None:
            return (
                self.advanced_palette_preview.labels(),
                self.advanced_palette_preview.source_label or "Generated",
                None,
            )
        current = self._current_output_result()
        if current is None:
            return None
        if current.structured_palette is not None:
            return (
                current.structured_palette.labels(),
                current.structured_palette.source_label or current.stats.stage.title(),
                None,
            )
        if current.display_palette_labels:
            return (list(current.display_palette_labels), current.stats.stage.title(), None)
        return None

    @staticmethod
    def _coerce_canvas_tool_mode(value: object) -> str | None:
        normalized = str(value or "").strip().lower()
        if normalized in {
            CANVAS_TOOL_MODE_PALETTE_PICK,
            CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK,
            CANVAS_TOOL_MODE_TRANSPARENCY_PICK,
            CANVAS_TOOL_MODE_BUCKET,
            CANVAS_TOOL_MODE_PENCIL,
            CANVAS_TOOL_MODE_ERASER,
            CANVAS_TOOL_MODE_ELLIPSE,
            CANVAS_TOOL_MODE_RECTANGLE,
            CANVAS_TOOL_MODE_LINE,
            CANVAS_TOOL_MODE_SELECT,
            CANVAS_TOOL_MODE_POLYGON_LASSO,
            CANVAS_TOOL_MODE_GRADIENT,
            CANVAS_TOOL_MODE_BLUR,
            CANVAS_TOOL_MODE_SHARPEN,
            CANVAS_TOOL_MODE_ROTATE,
            CANVAS_TOOL_MODE_ADD_OUTLINE,
            CANVAS_TOOL_MODE_REMOVE_OUTLINE,
        }:
            return normalized
        return None

    @staticmethod
    def _coerce_mouse_button_action(value: object, *, default: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in MOUSE_BUTTON_ACTION_VALUES:
            return normalized
        return default

    def _mouse_button_action(self, button: int) -> str:
        if button == CANVAS_MOUSE_BUTTON_MIDDLE:
            variable = getattr(self, "middle_mouse_action_var", None)
            default = MOUSE_BUTTON_DEFAULT_MIDDLE_ACTION
        else:
            variable = getattr(self, "right_mouse_action_var", None)
            default = MOUSE_BUTTON_DEFAULT_RIGHT_ACTION
        getter = getattr(variable, "get", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = default
        return self._coerce_mouse_button_action(value, default=default)

    def _select_mouse_button_action(self, button: int, action: str) -> None:
        default = MOUSE_BUTTON_DEFAULT_MIDDLE_ACTION if button == CANVAS_MOUSE_BUTTON_MIDDLE else MOUSE_BUTTON_DEFAULT_RIGHT_ACTION
        normalized = self._coerce_mouse_button_action(action, default=default)
        variable = getattr(
            self,
            "middle_mouse_action_var" if button == CANVAS_MOUSE_BUTTON_MIDDLE else "right_mouse_action_var",
            None,
        )
        setter = getattr(variable, "set", None)
        if callable(setter):
            setter(normalized)
        self._schedule_state_persist_if_ready()

    def _canvas_tool_mode_value(self) -> str | None:
        mode = self._coerce_canvas_tool_mode(getattr(self, "canvas_tool_mode", None))
        if mode is not None:
            return mode
        if getattr(self, "palette_add_pick_mode", False):
            return CANVAS_TOOL_MODE_PALETTE_PICK
        if getattr(self, "transparency_pick_mode", False):
            return CANVAS_TOOL_MODE_TRANSPARENCY_PICK
        return None

    @staticmethod
    def _is_outline_tool_mode(mode: str | None) -> bool:
        return mode in {CANVAS_TOOL_MODE_ADD_OUTLINE, CANVAS_TOOL_MODE_REMOVE_OUTLINE}

    @staticmethod
    def _is_crosshair_tool_mode(mode: str | None) -> bool:
        return mode in {
            CANVAS_TOOL_MODE_PALETTE_PICK,
            CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK,
            CANVAS_TOOL_MODE_TRANSPARENCY_PICK,
            CANVAS_TOOL_MODE_BUCKET,
            CANVAS_TOOL_MODE_PENCIL,
            CANVAS_TOOL_MODE_ERASER,
            CANVAS_TOOL_MODE_ELLIPSE,
            CANVAS_TOOL_MODE_RECTANGLE,
            CANVAS_TOOL_MODE_LINE,
            CANVAS_TOOL_MODE_SELECT,
            CANVAS_TOOL_MODE_POLYGON_LASSO,
        }

    def _options_tool_mode(self) -> str | None:
        mode = self._canvas_tool_mode_value()
        if mode in {
            CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK,
            CANVAS_TOOL_MODE_BUCKET,
            CANVAS_TOOL_MODE_PENCIL,
            CANVAS_TOOL_MODE_ERASER,
            CANVAS_TOOL_MODE_ELLIPSE,
            CANVAS_TOOL_MODE_RECTANGLE,
            CANVAS_TOOL_MODE_LINE,
            CANVAS_TOOL_MODE_GRADIENT,
            CANVAS_TOOL_MODE_BLUR,
            CANVAS_TOOL_MODE_SHARPEN,
            CANVAS_TOOL_MODE_ROTATE,
            CANVAS_TOOL_MODE_ADD_OUTLINE,
            CANVAS_TOOL_MODE_REMOVE_OUTLINE,
        }:
            return mode
        return None

    @staticmethod
    def _is_selection_tool_mode(mode: str | None) -> bool:
        return mode in {CANVAS_TOOL_MODE_SELECT, CANVAS_TOOL_MODE_POLYGON_LASSO}

    def _set_canvas_tool_mode(self, mode: str | None) -> None:
        normalized = self._coerce_canvas_tool_mode(mode)
        previous_mode = self._canvas_tool_mode_value()
        had_shape_preview = getattr(self, "_shape_drag_active", False)
        if (
            getattr(self, "_floating_selection", None) is not None
            and normalized not in {CANVAS_TOOL_MODE_SELECT, CANVAS_TOOL_MODE_POLYGON_LASSO, CANVAS_TOOL_MODE_ROTATE}
        ):
            self._commit_floating_selection()
        if previous_mode == CANVAS_TOOL_MODE_POLYGON_LASSO and normalized != CANVAS_TOOL_MODE_POLYGON_LASSO:
            self._cancel_polygon_lasso()
        self.canvas_tool_mode = normalized
        self.palette_add_pick_mode = normalized == CANVAS_TOOL_MODE_PALETTE_PICK
        self.transparency_pick_mode = normalized == CANVAS_TOOL_MODE_TRANSPARENCY_PICK
        self._reset_brush_stroke_state()
        self._reset_shape_preview_state()
        self._reset_selection_drag_state()
        self._set_pick_preview(None)
        if normalized == CANVAS_TOOL_MODE_PALETTE_PICK:
            self._set_view("original")
            self.process_status_var.set("Click the original preview to add a colour to the current palette.")
        elif normalized == CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK:
            self._set_view("processed")
            self.process_status_var.set("Click the processed preview to set the active colour.")
        elif normalized == CANVAS_TOOL_MODE_TRANSPARENCY_PICK:
            self._set_view("processed")
            self.process_status_var.set("Click the processed preview to remove a connected region.")
        elif normalized == CANVAS_TOOL_MODE_BUCKET:
            self._set_view("processed")
            self.process_status_var.set("Click the processed preview to fill a connected region with the primary colour.")
        elif normalized == CANVAS_TOOL_MODE_PENCIL:
            self._set_view("processed")
            self.process_status_var.set("Click and drag on the processed preview to draw with the primary colour.")
        elif normalized == CANVAS_TOOL_MODE_ERASER:
            self._set_view("processed")
            self.process_status_var.set("Click and drag on the processed preview to erase pixels to transparency.")
        elif normalized == CANVAS_TOOL_MODE_ELLIPSE:
            self._set_view("processed")
            self.process_status_var.set("Click and drag on the processed preview to draw an ellipse. Hold Shift to constrain to a circle.")
        elif normalized == CANVAS_TOOL_MODE_RECTANGLE:
            self._set_view("processed")
            self.process_status_var.set("Click and drag on the processed preview to draw a rectangle. Hold Shift to constrain to a square.")
        elif normalized == CANVAS_TOOL_MODE_LINE:
            self._set_view("processed")
            self.process_status_var.set("Click and drag on the processed preview to draw a line.")
        elif normalized == CANVAS_TOOL_MODE_SELECT:
            self._set_view("processed")
            self.process_status_var.set("Click and drag to create a rectangular selection, or drag an existing selection to move it.")
        elif normalized == CANVAS_TOOL_MODE_POLYGON_LASSO:
            self._set_view("processed")
            self.process_status_var.set("Click to add lasso points. Click the first point again or double-click to finish. Press Esc to cancel.")
        elif normalized == CANVAS_TOOL_MODE_GRADIENT:
            self._set_view("processed")
            self.process_status_var.set("Gradient tool is not implemented yet.")
        elif normalized == CANVAS_TOOL_MODE_BLUR:
            self._set_view("processed")
            self._sync_image_filter_strength_control(CANVAS_TOOL_MODE_BLUR)
            self.process_status_var.set("Blur selected. Adjust strength and click Apply.")
        elif normalized == CANVAS_TOOL_MODE_SHARPEN:
            self._set_view("processed")
            self._sync_image_filter_strength_control(CANVAS_TOOL_MODE_SHARPEN)
            self.process_status_var.set("Sharpen selected. Adjust strength and click Apply.")
        elif normalized == CANVAS_TOOL_MODE_ROTATE:
            self._set_view("processed")
            self.process_status_var.set("Choose a rotation and click Apply.")
        elif normalized == CANVAS_TOOL_MODE_ADD_OUTLINE:
            self._set_view("processed")
            self.process_status_var.set("Adjust add outline options, then click Apply.")
        elif normalized == CANVAS_TOOL_MODE_REMOVE_OUTLINE:
            self._set_view("processed")
            self.process_status_var.set("Adjust remove outline options, then click Apply.")
        if had_shape_preview and hasattr(self, "redraw_canvas"):
            self.redraw_canvas()
        canvas = getattr(self, "canvas", None)
        if canvas is not None and hasattr(canvas, "configure") and not getattr(self, "dragging", False):
            canvas.configure(cursor=self._cursor_for_pointer())
        self._refresh_tool_options_panel()
        self._refresh_tool_button_styles()

    def _set_pick_mode(self, mode: str | None) -> None:
        translated = {
            "palette": CANVAS_TOOL_MODE_PALETTE_PICK,
            "transparency": CANVAS_TOOL_MODE_TRANSPARENCY_PICK,
            None: None,
        }.get(mode, None)
        self._set_canvas_tool_mode(translated)

    def _set_options_helper_text(self, value: str) -> None:
        variable = getattr(self, "options_helper_var", None)
        setter = getattr(variable, "set", None)
        if callable(setter):
            setter(value)

    @staticmethod
    def _set_packed(widget: object, visible: bool, **pack_kwargs: object) -> None:
        if widget is None:
            return
        pack_forget = getattr(widget, "pack_forget", None)
        pack = getattr(widget, "pack", None)
        winfo_manager = getattr(widget, "winfo_manager", None)
        if visible:
            if callable(pack):
                manager = winfo_manager() if callable(winfo_manager) else ""
                if not manager:
                    pack(**pack_kwargs)
        elif callable(pack_forget):
            pack_forget()

    @staticmethod
    def _coerce_new_image_background(value: object) -> str:
        normalized = str(value or NEW_IMAGE_BACKGROUND_TRANSPARENT).strip().lower()
        if normalized in NEW_IMAGE_BACKGROUND_VALUE_TO_DISPLAY:
            return normalized
        return NEW_IMAGE_BACKGROUND_DISPLAY_TO_VALUE.get(str(value or "").strip(), NEW_IMAGE_BACKGROUND_TRANSPARENT)

    def _new_image_lock_icon(self, locked: bool) -> ImageTk.PhotoImage:
        cached_icon = self._new_image_lock_icons.get(locked)
        if cached_icon is not None:
            return cached_icon
        asset_path = self._resource_path("assets/icon_lock.png")
        with Image.open(asset_path) as image:
            rgba = image.convert("RGBA")
            if not locked:
                alpha = rgba.getchannel("A").point(lambda value: value // 2 if value else 0)
                rgba = rgba.copy()
                rgba.putalpha(alpha)
            fitted = Image.new("RGBA", (NEW_IMAGE_LOCK_ICON_SIZE, NEW_IMAGE_LOCK_ICON_SIZE), (0, 0, 0, 0))
            offset_x = (fitted.width - rgba.width) // 2
            offset_y = (fitted.height - rgba.height) // 2
            fitted.paste(rgba, (offset_x, offset_y), rgba)
            cached_icon = ImageTk.PhotoImage(fitted, master=self.root)
        self._new_image_lock_icons[locked] = cached_icon
        return cached_icon

    def _refresh_new_image_lock_button(self) -> None:
        button = getattr(self, "_new_image_lock_button", None)
        if button is None or not hasattr(button, "configure"):
            return
        locked = bool(self._new_image_locked_var.get()) if self._new_image_locked_var is not None else True
        button.configure(
            image=self._new_image_lock_icon(locked),
            background=APP_HOVER_BG if locked else APP_SURFACE_BG,
            activebackground=APP_HOVER_BG,
            relief=tk.FLAT,
        )

    def _sync_new_image_dimensions(self, source: str) -> None:
        if self._new_image_syncing_dimensions:
            return
        if self._new_image_locked_var is None or not self._new_image_locked_var.get():
            return
        source_var = self._new_image_width_var if source == "width" else self._new_image_height_var
        target_var = self._new_image_height_var if source == "width" else self._new_image_width_var
        if source_var is None or target_var is None:
            return
        self._new_image_syncing_dimensions = True
        try:
            target_var.set(source_var.get())
        finally:
            self._new_image_syncing_dimensions = False

    def _toggle_new_image_lock(self) -> None:
        if self._new_image_locked_var is None:
            return
        self._new_image_locked_var.set(not self._new_image_locked_var.get())
        if self._new_image_locked_var.get():
            self._sync_new_image_dimensions("width")
        self._refresh_new_image_lock_button()

    def _destroy_new_image_window(self) -> None:
        window = getattr(self, "_new_image_window", None)
        width_var = getattr(self, "_new_image_width_var", None)
        height_var = getattr(self, "_new_image_height_var", None)
        width_trace_id = getattr(self, "_new_image_width_trace_id", None)
        height_trace_id = getattr(self, "_new_image_height_trace_id", None)
        if width_var is not None and width_trace_id is not None:
            try:
                width_var.trace_remove("write", width_trace_id)
            except (tk.TclError, ValueError):
                pass
        if height_var is not None and height_trace_id is not None:
            try:
                height_var.trace_remove("write", height_trace_id)
            except (tk.TclError, ValueError):
                pass
        self._new_image_window = None
        self._new_image_width_var = None
        self._new_image_height_var = None
        self._new_image_locked_var = None
        self._new_image_background_var = None
        self._new_image_width_trace_id = None
        self._new_image_height_trace_id = None
        self._new_image_lock_button = None
        self._new_image_syncing_dimensions = False
        if window is not None and hasattr(window, "winfo_exists") and window.winfo_exists():
            try:
                window.grab_release()
            except Exception:
                pass
            window.destroy()

    def _create_blank_canvas_document(self, width: int, height: int, background: str) -> None:
        fill_mode = self._coerce_new_image_background(background)
        fill_label = 0xFFFFFF if fill_mode == NEW_IMAGE_BACKGROUND_WHITE else 0x000000
        fill_rgb = ((fill_label >> 16) & 0xFF, (fill_label >> 8) & 0xFF, fill_label & 0xFF)
        fill_alpha = 0 if fill_mode == NEW_IMAGE_BACKGROUND_TRANSPARENT else 255
        original_image = Image.new("RGBA", (width, height), (*fill_rgb, fill_alpha))
        grid: RGBGrid = [[fill_rgb for _ in range(width)] for _ in range(height)]
        labels = [[fill_label for _ in range(width)] for _ in range(height)]
        prepared_input = PipelinePreparedResult(
            reduced_labels=labels,
            pixel_width=1,
            grid_method="manual",
            input_size=(width, height),
            initial_color_count=1,
        )
        visible_palette = () if fill_mode == NEW_IMAGE_BACKGROUND_TRANSPARENT else (fill_label,)
        alpha_mask = tuple(tuple(False for _ in range(width)) for _ in range(height)) if fill_mode == NEW_IMAGE_BACKGROUND_TRANSPARENT else None
        color_count = 0 if fill_mode == NEW_IMAGE_BACKGROUND_TRANSPARENT else 1
        result = ProcessResult(
            grid=grid,
            width=width,
            height=height,
            stats=ProcessStats(
                stage="downsample",
                pixel_width=1,
                resize_method="nearest",
                input_size=(width, height),
                output_size=(width, height),
                initial_color_count=1,
                color_count=color_count,
                elapsed_seconds=0.0,
            ),
            prepared_input=prepared_input,
            display_palette_labels=visible_palette,
            alpha_mask=alpha_mask,
        )

        self.source_path = Path("Untitled.png")
        self.last_output_path = None
        self.last_successful_process_snapshot = None
        self.original_display_image = original_image
        self.original_grid = grid
        self.comparison_original_image = None
        self._comparison_original_key = None
        self.downsample_result = result
        self.palette_result = None
        self.downsample_display_image = None
        self.palette_display_image = None
        self.prepared_input_cache = prepared_input
        self.prepared_input_cache_key = None
        self.transparent_colors = set()
        self._palette_selection_indices = set()
        self._palette_selection_anchor_index = None
        self._palette_hit_regions = []
        self._displayed_palette = []
        self._builtin_palette_preview_entry = None
        self._set_pick_mode(None)
        self._set_active_palette(None, "", None)
        self.advanced_palette_preview = None
        self._clear_palette_undo_state()
        self._clear_palette_redo_state()
        self._reset_palette_adjustments_to_neutral()
        self._clear_canvas_selection_state()
        self.quick_compare_active = False
        self._mouse_button_action_state = None
        self.pan_x = 0
        self.pan_y = 0
        self.image_state = "processed_current"
        self._refresh_output_display_images()
        self._set_view("processed")
        self.process_status_var.set(
            f"Created a {width}x{height} {NEW_IMAGE_BACKGROUND_VALUE_TO_DISPLAY[fill_mode].lower()} canvas. Draw on it immediately or save it with Save As."
        )
        self.root.update_idletasks()
        self.zoom_fit()
        self._update_scale_info()
        self._update_palette_strip()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _commit_new_image_dialog(self) -> None:
        window = getattr(self, "_new_image_window", None)
        try:
            width = int(self._new_image_width_var.get()) if self._new_image_width_var is not None else NEW_IMAGE_DEFAULT_SIZE
            height = int(self._new_image_height_var.get()) if self._new_image_height_var is not None else NEW_IMAGE_DEFAULT_SIZE
        except (TypeError, ValueError):
            messagebox.showerror("Invalid canvas size", "Width and Height must be whole numbers.", parent=window)
            return
        if not (CANVAS_RESIZE_DIMENSION_MIN <= width <= CANVAS_RESIZE_DIMENSION_MAX):
            messagebox.showerror(
                "Invalid canvas size",
                f"Width must be between {CANVAS_RESIZE_DIMENSION_MIN} and {CANVAS_RESIZE_DIMENSION_MAX}.",
                parent=window,
            )
            return
        if not (CANVAS_RESIZE_DIMENSION_MIN <= height <= CANVAS_RESIZE_DIMENSION_MAX):
            messagebox.showerror(
                "Invalid canvas size",
                f"Height must be between {CANVAS_RESIZE_DIMENSION_MIN} and {CANVAS_RESIZE_DIMENSION_MAX}.",
                parent=window,
            )
            return
        background = self._coerce_new_image_background(
            self._new_image_background_var.get() if self._new_image_background_var is not None else NEW_IMAGE_BACKGROUND_TRANSPARENT
        )
        if self.original_grid is not None:
            if not messagebox.askyesno(
                "Replace current image?",
                "Creating a new image will replace the current image in the editor.\n\nContinue?",
                parent=window,
            ):
                return
        self._create_blank_canvas_document(width, height, background)
        self._destroy_new_image_window()

    def open_new_image_window(self) -> None:
        if self.image_state == "processing":
            self.process_status_var.set("New Image is unavailable while processing.")
            return
        existing = getattr(self, "_new_image_window", None)
        if existing is not None and hasattr(existing, "winfo_exists") and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        window = tk.Toplevel(self.root, bg=APP_BORDER, bd=0, highlightthickness=0)
        window.withdraw()
        window.title("New image")
        window.transient(self.root)
        window.resizable(False, False)
        self._new_image_window = window
        self._new_image_width_var = tk.StringVar(window, value=str(NEW_IMAGE_DEFAULT_SIZE))
        self._new_image_height_var = tk.StringVar(window, value=str(NEW_IMAGE_DEFAULT_SIZE))
        self._new_image_locked_var = tk.BooleanVar(window, value=True)
        self._new_image_background_var = tk.StringVar(
            window,
            value=NEW_IMAGE_BACKGROUND_VALUE_TO_DISPLAY[NEW_IMAGE_BACKGROUND_TRANSPARENT],
        )
        self._new_image_width_trace_id = self._new_image_width_var.trace_add("write", lambda *_args: self._sync_new_image_dimensions("width"))
        self._new_image_height_trace_id = self._new_image_height_var.trace_add("write", lambda *_args: self._sync_new_image_dimensions("height"))

        window.protocol("WM_DELETE_WINDOW", self._destroy_new_image_window)
        window.bind("<Escape>", lambda _event: self._destroy_new_image_window(), add="+")
        window.bind("<Return>", lambda _event: self._commit_new_image_dialog(), add="+")

        shell = tk.Frame(window, bg=APP_BORDER, bd=0, highlightthickness=0)
        shell.pack(fill=tk.BOTH, expand=True)
        content = tk.Frame(shell, bg=APP_BG, bd=0, highlightthickness=0)
        content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        inner = ttk.Frame(content)
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        body = ttk.Frame(inner)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(body)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))

        canvas_frame = ttk.LabelFrame(left, text="Canvas")
        canvas_frame.pack(fill=tk.X)
        ttk.Label(canvas_frame, text="Width").grid(row=0, column=0, sticky="w", padx=(8, 6), pady=(8, 4))
        ttk.Label(canvas_frame, text="Height").grid(row=0, column=2, sticky="w", padx=(6, 6), pady=(8, 4))
        width_entry = ttk.Entry(canvas_frame, textvariable=self._new_image_width_var, width=7)
        width_entry.grid(row=1, column=0, sticky="w", padx=(8, 6), pady=(0, 8))
        ttk.Label(canvas_frame, text="x").grid(row=1, column=1, sticky="w", padx=4, pady=(0, 8))
        height_entry = ttk.Entry(canvas_frame, textvariable=self._new_image_height_var, width=7)
        height_entry.grid(row=1, column=2, sticky="w", padx=(6, 6), pady=(0, 8))
        lock_cell = tk.Frame(
            canvas_frame,
            width=NEW_IMAGE_LOCK_BUTTON_SIZE,
            height=NEW_IMAGE_LOCK_BUTTON_SIZE,
            bg=APP_BORDER,
            bd=0,
            highlightthickness=0,
        )
        lock_cell.grid(row=1, column=3, sticky="w", padx=(0, 8), pady=(0, 8))
        lock_cell.grid_propagate(False)
        self._new_image_lock_button = tk.Button(
            lock_cell,
            image=self._new_image_lock_icon(True),
            command=self._toggle_new_image_lock,
            bg=APP_HOVER_BG,
            activebackground=APP_HOVER_BG,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
            cursor="hand2",
            padx=0,
            pady=0,
        )
        self._new_image_lock_button.pack(fill=tk.BOTH, expand=True)

        background_frame = ttk.LabelFrame(left, text="Background")
        background_frame.pack(fill=tk.X, pady=(12, 0))
        background_combo = ttk.Combobox(
            background_frame,
            textvariable=self._new_image_background_var,
            values=tuple(label for label, _value in NEW_IMAGE_BACKGROUND_OPTIONS),
            state="readonly",
            width=18,
        )
        background_combo.pack(anchor=tk.W, padx=8, pady=8)

        ttk.Button(right, text="OK", command=self._commit_new_image_dialog).pack(fill=tk.X)
        ttk.Button(right, text="Cancel", command=self._destroy_new_image_window).pack(fill=tk.X, pady=(8, 0))

        self.root.update_idletasks()
        window_height = window.winfo_reqheight()
        x_pos = self.root.winfo_rootx() + max(20, (self.root.winfo_width() - NEW_IMAGE_WINDOW_WIDTH) // 2)
        y_pos = self.root.winfo_rooty() + max(20, (self.root.winfo_height() - window_height) // 2)
        window.geometry(f"{NEW_IMAGE_WINDOW_WIDTH}x{window_height}+{x_pos}+{y_pos}")
        window.deiconify()
        window.grab_set()
        window.focus_force()
        width_entry.focus_set()
        width_entry.selection_range(0, tk.END)

    def _show_toolbar_placeholder_message(self, label: str) -> None:
        self.process_status_var.set(f"{label} is not implemented yet.")

    @staticmethod
    def _coerce_canvas_resize_dimension(value: object, *, fallback: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = fallback
        return max(CANVAS_RESIZE_DIMENSION_MIN, min(CANVAS_RESIZE_DIMENSION_MAX, parsed))

    @staticmethod
    def _coerce_canvas_resize_anchor(value: object) -> str:
        normalized = str(value or CANVAS_RESIZE_ANCHOR_CENTER).strip().lower()
        if normalized in CANVAS_RESIZE_ANCHOR_LABELS:
            return normalized
        return CANVAS_RESIZE_ANCHOR_CENTER

    def _current_canvas_size_dialog_state(self) -> CanvasSizeDialogState:
        current = self._current_output_result()
        width = current.width if current is not None else CANVAS_RESIZE_DIMENSION_MIN
        height = current.height if current is not None else CANVAS_RESIZE_DIMENSION_MIN
        return CanvasSizeDialogState(width=width, height=height, anchor=CANVAS_RESIZE_ANCHOR_CENTER)

    def _refresh_canvas_size_lock_button(self) -> None:
        button = getattr(self, "_canvas_size_lock_button", None)
        if button is None or not hasattr(button, "configure"):
            return
        locked = bool(self._canvas_size_locked_var.get()) if self._canvas_size_locked_var is not None else True
        button.configure(
            image=self._new_image_lock_icon(locked),
            background=APP_HOVER_BG if locked else APP_SURFACE_BG,
            activebackground=APP_HOVER_BG,
            relief=tk.FLAT,
        )

    def _sync_canvas_size_dimensions(self, source: str) -> None:
        if self._canvas_size_syncing_dimensions:
            return
        if self._canvas_size_locked_var is None or not self._canvas_size_locked_var.get():
            return
        source_var = self._canvas_size_width_var if source == "width" else self._canvas_size_height_var
        target_var = self._canvas_size_height_var if source == "width" else self._canvas_size_width_var
        if source_var is None or target_var is None:
            return
        self._canvas_size_syncing_dimensions = True
        try:
            target_var.set(source_var.get())
        finally:
            self._canvas_size_syncing_dimensions = False

    def _toggle_canvas_size_lock(self) -> None:
        if self._canvas_size_locked_var is None:
            return
        self._canvas_size_locked_var.set(not self._canvas_size_locked_var.get())
        if self._canvas_size_locked_var.get():
            self._sync_canvas_size_dimensions("width")
        self._refresh_canvas_size_lock_button()

    def _set_canvas_size_dialog_state(self, state: CanvasSizeDialogState) -> None:
        if self._canvas_size_width_var is not None:
            self._canvas_size_width_var.set(str(self._coerce_canvas_resize_dimension(state.width, fallback=state.width)))
        if self._canvas_size_height_var is not None:
            self._canvas_size_height_var.set(str(self._coerce_canvas_resize_dimension(state.height, fallback=state.height)))
        if self._canvas_size_anchor_var is not None:
            self._canvas_size_anchor_var.set(self._coerce_canvas_resize_anchor(state.anchor))

    def _read_canvas_size_dialog_state(self) -> CanvasSizeDialogState:
        current = self._current_output_result()
        fallback_width = current.width if current is not None else CANVAS_RESIZE_DIMENSION_MIN
        fallback_height = current.height if current is not None else CANVAS_RESIZE_DIMENSION_MIN
        width_value = self._canvas_size_width_var.get() if self._canvas_size_width_var is not None else fallback_width
        height_value = self._canvas_size_height_var.get() if self._canvas_size_height_var is not None else fallback_height
        anchor_value = self._canvas_size_anchor_var.get() if self._canvas_size_anchor_var is not None else CANVAS_RESIZE_ANCHOR_CENTER
        return CanvasSizeDialogState(
            width=self._coerce_canvas_resize_dimension(width_value, fallback=fallback_width),
            height=self._coerce_canvas_resize_dimension(height_value, fallback=fallback_height),
            anchor=self._coerce_canvas_resize_anchor(anchor_value),
        )

    def _close_canvas_size_window(self) -> None:
        window = getattr(self, "_canvas_size_window", None)
        width_var = getattr(self, "_canvas_size_width_var", None)
        height_var = getattr(self, "_canvas_size_height_var", None)
        width_trace_id = getattr(self, "_canvas_size_width_trace_id", None)
        height_trace_id = getattr(self, "_canvas_size_height_trace_id", None)
        if width_var is not None and width_trace_id is not None:
            try:
                width_var.trace_remove("write", width_trace_id)
            except (tk.TclError, ValueError):
                pass
        if height_var is not None and height_trace_id is not None:
            try:
                height_var.trace_remove("write", height_trace_id)
            except (tk.TclError, ValueError):
                pass
        self._canvas_size_window = None
        self._canvas_size_width_var = None
        self._canvas_size_height_var = None
        self._canvas_size_anchor_var = None
        self._canvas_size_locked_var = None
        self._canvas_size_width_trace_id = None
        self._canvas_size_height_trace_id = None
        self._canvas_size_lock_button = None
        self._canvas_size_syncing_dimensions = False
        if window is not None and hasattr(window, "winfo_exists") and window.winfo_exists():
            try:
                window.grab_release()
            except Exception:
                pass
            window.destroy()

    def _commit_canvas_size_dialog(self) -> None:
        current = self._current_output_result()
        window = getattr(self, "_canvas_size_window", None)
        if current is None:
            self.process_status_var.set("Create a processed image before resizing the canvas.")
            self._close_canvas_size_window()
            return
        try:
            width = int(self._canvas_size_width_var.get()) if self._canvas_size_width_var is not None else current.width
            height = int(self._canvas_size_height_var.get()) if self._canvas_size_height_var is not None else current.height
        except (TypeError, ValueError):
            messagebox.showerror("Invalid canvas size", "Width and Height must be whole numbers.", parent=window)
            return
        if not (CANVAS_RESIZE_DIMENSION_MIN <= width <= CANVAS_RESIZE_DIMENSION_MAX):
            messagebox.showerror(
                "Invalid canvas size",
                f"Width must be between {CANVAS_RESIZE_DIMENSION_MIN} and {CANVAS_RESIZE_DIMENSION_MAX}.",
                parent=window,
            )
            return
        if not (CANVAS_RESIZE_DIMENSION_MIN <= height <= CANVAS_RESIZE_DIMENSION_MAX):
            messagebox.showerror(
                "Invalid canvas size",
                f"Height must be between {CANVAS_RESIZE_DIMENSION_MIN} and {CANVAS_RESIZE_DIMENSION_MAX}.",
                parent=window,
            )
            return
        anchor = self._coerce_canvas_resize_anchor(
            self._canvas_size_anchor_var.get() if self._canvas_size_anchor_var is not None else CANVAS_RESIZE_ANCHOR_CENTER
        )
        if width == current.width and height == current.height:
            self.process_status_var.set("Canvas size unchanged.")
            self._close_canvas_size_window()
            return
        self._apply_canvas_size(CanvasResizeSpec(width=width, height=height, anchor=anchor))
        self._close_canvas_size_window()

    def open_canvas_size_window(self) -> None:
        if self.image_state == "processing":
            self.process_status_var.set("Canvas Size is unavailable while processing.")
            return
        if self._current_output_result() is None or self._current_output_image() is None:
            self.process_status_var.set("Create a processed image before resizing the canvas.")
            return
        existing = getattr(self, "_canvas_size_window", None)
        if existing is not None and hasattr(existing, "winfo_exists") and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        window = tk.Toplevel(self.root, bg=APP_BORDER, bd=0, highlightthickness=0)
        window.withdraw()
        window.title("Canvas Size")
        window.transient(self.root)
        window.resizable(False, False)
        self._canvas_size_window = window
        self._canvas_size_width_var = tk.StringVar(window)
        self._canvas_size_height_var = tk.StringVar(window)
        self._canvas_size_anchor_var = tk.StringVar(window)
        self._canvas_size_locked_var = tk.BooleanVar(window, value=True)
        self._set_canvas_size_dialog_state(self._current_canvas_size_dialog_state())
        self._canvas_size_width_trace_id = self._canvas_size_width_var.trace_add("write", lambda *_args: self._sync_canvas_size_dimensions("width"))
        self._canvas_size_height_trace_id = self._canvas_size_height_var.trace_add("write", lambda *_args: self._sync_canvas_size_dimensions("height"))

        window.protocol("WM_DELETE_WINDOW", self._close_canvas_size_window)
        window.bind("<Escape>", lambda _event: self._close_canvas_size_window(), add="+")
        window.bind("<Return>", lambda _event: self._commit_canvas_size_dialog(), add="+")

        shell = tk.Frame(window, bg=APP_BORDER, bd=0, highlightthickness=0)
        shell.pack(fill=tk.BOTH, expand=True)
        content = tk.Frame(shell, bg=APP_BG, bd=0, highlightthickness=0)
        content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        inner = ttk.Frame(content)
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        body = ttk.Frame(inner)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(body)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))

        size_frame = ttk.LabelFrame(left, text="Canvas")
        size_frame.pack(fill=tk.X)
        ttk.Label(size_frame, text="Width").grid(row=0, column=0, sticky="w", padx=(8, 6), pady=(8, 4))
        ttk.Label(size_frame, text="Height").grid(row=0, column=2, sticky="w", padx=(6, 6), pady=(8, 4))
        width_spinbox = ttk.Spinbox(
            size_frame,
            from_=CANVAS_RESIZE_DIMENSION_MIN,
            to=CANVAS_RESIZE_DIMENSION_MAX,
            textvariable=self._canvas_size_width_var,
            width=8,
        )
        width_spinbox.grid(row=1, column=0, sticky="w", padx=(8, 6), pady=(0, 8))
        ttk.Label(size_frame, text="x").grid(row=1, column=1, sticky="w", padx=4, pady=(0, 8))
        height_spinbox = ttk.Spinbox(
            size_frame,
            from_=CANVAS_RESIZE_DIMENSION_MIN,
            to=CANVAS_RESIZE_DIMENSION_MAX,
            textvariable=self._canvas_size_height_var,
            width=8,
        )
        height_spinbox.grid(row=1, column=2, sticky="w", padx=(6, 6), pady=(0, 8))
        lock_cell = tk.Frame(
            size_frame,
            width=NEW_IMAGE_LOCK_BUTTON_SIZE,
            height=NEW_IMAGE_LOCK_BUTTON_SIZE,
            bg=APP_BORDER,
            bd=0,
            highlightthickness=0,
        )
        lock_cell.grid(row=1, column=3, sticky="w", padx=(0, 8), pady=(0, 8))
        lock_cell.grid_propagate(False)
        self._canvas_size_lock_button = tk.Button(
            lock_cell,
            image=self._new_image_lock_icon(True),
            command=self._toggle_canvas_size_lock,
            bg=APP_HOVER_BG,
            activebackground=APP_HOVER_BG,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
            cursor="hand2",
            padx=0,
            pady=0,
        )
        self._canvas_size_lock_button.pack(fill=tk.BOTH, expand=True)

        anchor_frame = ttk.LabelFrame(left, text="Anchor")
        anchor_frame.pack(fill=tk.X, pady=(12, 0))
        anchor_cells = (
            ("TL", CANVAS_RESIZE_ANCHOR_TOP_LEFT),
            ("T", CANVAS_RESIZE_ANCHOR_TOP),
            ("TR", CANVAS_RESIZE_ANCHOR_TOP_RIGHT),
            ("L", CANVAS_RESIZE_ANCHOR_LEFT),
            ("C", CANVAS_RESIZE_ANCHOR_CENTER),
            ("R", CANVAS_RESIZE_ANCHOR_RIGHT),
            ("BL", CANVAS_RESIZE_ANCHOR_BOTTOM_LEFT),
            ("B", CANVAS_RESIZE_ANCHOR_BOTTOM),
            ("BR", CANVAS_RESIZE_ANCHOR_BOTTOM_RIGHT),
        )
        for index, (label, value) in enumerate(anchor_cells):
            row_index, column_index = divmod(index, 3)
            ttk.Radiobutton(anchor_frame, text=label, value=value, variable=self._canvas_size_anchor_var).grid(
                row=row_index,
                column=column_index,
                sticky="nsew",
                padx=4,
                pady=4,
            )
            anchor_frame.grid_columnconfigure(column_index, weight=1)

        ttk.Label(left, text="New space: Transparent", foreground=APP_MUTED_TEXT).pack(anchor=tk.W, pady=(12, 0))

        ttk.Button(right, text="OK", command=self._commit_canvas_size_dialog).pack(fill=tk.X)
        ttk.Button(right, text="Cancel", command=self._close_canvas_size_window).pack(fill=tk.X, pady=(8, 0))

        self.root.update_idletasks()
        x_pos = self.root.winfo_rootx() + max(20, (self.root.winfo_width() - CANVAS_SIZE_WINDOW_WIDTH) // 2)
        y_pos = self.root.winfo_rooty() + max(20, (self.root.winfo_height() - CANVAS_SIZE_WINDOW_HEIGHT) // 2)
        window.geometry(f"{CANVAS_SIZE_WINDOW_WIDTH}x{CANVAS_SIZE_WINDOW_HEIGHT}+{x_pos}+{y_pos}")
        window.deiconify()
        window.grab_set()
        window.focus_force()
        width_spinbox.focus_set()
        self._refresh_canvas_size_lock_button()

    def _toolbar_zoom_display_value(self) -> str:
        return f"{clamp_zoom(self.zoom)}%"

    def _sync_toolbar_zoom_dropdown(self) -> None:
        variable = getattr(self, "toolbar_zoom_var", None)
        if variable is not None:
            variable.set(self._toolbar_zoom_display_value())

    def _on_toolbar_zoom_selected(self, _event: tk.Event | None = None) -> None:
        variable = getattr(self, "toolbar_zoom_var", None)
        getter = getattr(variable, "get", None)
        selected = getter() if callable(getter) else variable
        if selected == "Fit":
            self.zoom_fit()
            return
        try:
            zoom_value = int(str(selected).rstrip("%"))
        except (TypeError, ValueError):
            self._sync_toolbar_zoom_dropdown()
            return
        self._set_zoom(zoom_value)

    def _capture_preferences_state(self) -> PreferencesDialogState:
        return PreferencesDialogState(
            settings=self.session.current,
            checkerboard=bool(self.checkerboard_var.get()),
            overlay_grid=bool(self.overlay_grid_var.get()),
            selection_threshold=self._selection_threshold_percent(),
            right_mouse_action=self._mouse_button_action(CANVAS_MOUSE_BUTTON_RIGHT),
            middle_mouse_action=self._mouse_button_action(CANVAS_MOUSE_BUTTON_MIDDLE),
            openai_api_key=self.openai_api_key,
            gemini_api_key=self.gemini_api_key,
            image_generation_model=self.image_generation_model,
        )

    def _set_preferences_dialog_state(self, state: PreferencesDialogState) -> None:
        if self._preferences_checkerboard_var is not None:
            self._preferences_checkerboard_var.set(state.checkerboard)
        if self._preferences_overlay_grid_var is not None:
            self._preferences_overlay_grid_var.set(state.overlay_grid)
        if self._preferences_downsample_mode_var is not None:
            self._preferences_downsample_mode_var.set(
                RESIZE_VALUE_TO_DISPLAY.get(state.settings.downsample_mode, RESIZE_OPTIONS[0][0])
            )
        if self._preferences_quantizer_var is not None:
            self._preferences_quantizer_var.set(
                QUANTIZER_VALUE_TO_DISPLAY.get(state.settings.quantizer, QUANTIZER_OPTIONS[0][0])
            )
        if self._preferences_generated_shades_var is not None:
            self._preferences_generated_shades_var.set(str(state.settings.generated_shades))
        if self._preferences_contrast_bias_var is not None:
            self._preferences_contrast_bias_var.set(state.settings.contrast_bias)
        if self._preferences_palette_dither_var is not None:
            self._preferences_palette_dither_var.set(
                DITHER_VALUE_TO_DISPLAY.get(state.settings.palette_dither_mode, DITHER_OPTIONS[0][0])
            )
        if self._preferences_selection_threshold_var is not None:
            self._preferences_selection_threshold_var.set(state.selection_threshold)
        if self._preferences_right_mouse_action_var is not None:
            self._preferences_right_mouse_action_var.set(state.right_mouse_action)
        if self._preferences_middle_mouse_action_var is not None:
            self._preferences_middle_mouse_action_var.set(state.middle_mouse_action)
        if self._preferences_openai_key_var is not None:
            self._preferences_openai_key_var.set(state.openai_api_key)
        if self._preferences_gemini_key_var is not None:
            self._preferences_gemini_key_var.set(state.gemini_api_key)
        if self._preferences_ai_model_id_var is not None:
            self._preferences_ai_model_id_var.set(state.image_generation_model)
        self._sync_preferences_ai_model_combobox()

    def _read_preferences_dialog_state(self) -> PreferencesDialogState:
        original = self._preferences_original_state or self._capture_preferences_state()
        settings = original.settings
        generated_shades_raw = original.settings.generated_shades
        if self._preferences_generated_shades_var is not None:
            try:
                generated_shades_raw = int(self._preferences_generated_shades_var.get() or generated_shades_raw)
            except (TypeError, ValueError):
                generated_shades_raw = original.settings.generated_shades
        generated_shades = max(min(GENERATED_SHADES_OPTIONS), min(max(GENERATED_SHADES_OPTIONS), generated_shades_raw))
        if generated_shades not in GENERATED_SHADES_OPTIONS:
            generated_shades = min(GENERATED_SHADES_OPTIONS, key=lambda value: abs(value - generated_shades))

        contrast_bias_raw = original.settings.contrast_bias
        if self._preferences_contrast_bias_var is not None:
            try:
                contrast_bias_raw = float(self._preferences_contrast_bias_var.get() or contrast_bias_raw)
            except (TypeError, ValueError):
                contrast_bias_raw = original.settings.contrast_bias
        contrast_options = tuple(value / 100.0 for value in RAMP_CONTRAST_OPTIONS)
        contrast_bias = min(contrast_options, key=lambda value: abs(value - contrast_bias_raw))

        updated_settings = replace(
            settings,
            downsample_mode=RESIZE_DISPLAY_TO_VALUE.get(
                self._preferences_downsample_mode_var.get() if self._preferences_downsample_mode_var is not None else "",
                settings.downsample_mode,
            ),
            quantizer=QUANTIZER_DISPLAY_TO_VALUE.get(
                self._preferences_quantizer_var.get() if self._preferences_quantizer_var is not None else "",
                settings.quantizer,
            ),
            generated_shades=generated_shades,
            contrast_bias=contrast_bias,
            palette_dither_mode=DITHER_DISPLAY_TO_VALUE.get(
                self._preferences_palette_dither_var.get() if self._preferences_palette_dither_var is not None else "",
                settings.palette_dither_mode,
            ),
        )
        selection_value = original.selection_threshold
        if self._preferences_selection_threshold_var is not None:
            selection_value = coerce_selection_threshold(self._preferences_selection_threshold_var.get())
        openai_var = getattr(self, "_preferences_openai_key_var", None)
        gemini_var = getattr(self, "_preferences_gemini_key_var", None)
        openai_key = str(openai_var.get()) if openai_var is not None else original.openai_api_key
        gemini_key = str(gemini_var.get()) if gemini_var is not None else original.gemini_api_key
        model_id = original.image_generation_model
        combo = getattr(self, "_preferences_ai_model_combobox", None)
        if combo is not None:
            label = combo.get()
            for m in models_for_keys(openai_key=openai_key, gemini_key=gemini_key):
                if m.label == label:
                    model_id = m.id
                    break
            else:
                available = models_for_keys(openai_key=openai_key, gemini_key=gemini_key)
                if available:
                    model_id = available[0].id
                else:
                    model_id = ""
        model_id = coerce_selected_model(model_id, openai_key=openai_key, gemini_key=gemini_key)

        return PreferencesDialogState(
            settings=updated_settings,
            checkerboard=bool(self._preferences_checkerboard_var.get()) if self._preferences_checkerboard_var is not None else original.checkerboard,
            overlay_grid=bool(self._preferences_overlay_grid_var.get()) if self._preferences_overlay_grid_var is not None else original.overlay_grid,
            selection_threshold=selection_value,
            right_mouse_action=self._coerce_mouse_button_action(
                self._preferences_right_mouse_action_var.get() if self._preferences_right_mouse_action_var is not None else original.right_mouse_action,
                default=MOUSE_BUTTON_DEFAULT_RIGHT_ACTION,
            ),
            middle_mouse_action=self._coerce_mouse_button_action(
                self._preferences_middle_mouse_action_var.get() if self._preferences_middle_mouse_action_var is not None else original.middle_mouse_action,
                default=MOUSE_BUTTON_DEFAULT_MIDDLE_ACTION,
            ),
            openai_api_key=openai_key,
            gemini_api_key=gemini_key,
            image_generation_model=model_id,
        )

    def _preferences_dialog_is_dirty(self) -> bool:
        if self._preferences_original_state is None:
            return False
        return self._read_preferences_dialog_state() != self._preferences_original_state

    def _refresh_preferences_nav_styles(self) -> None:
        for page_name, button in getattr(self, "_preferences_nav_buttons", {}).items():
            if hasattr(button, "configure"):
                button.configure(
                    style="PreferencesNavActive.TButton" if page_name == self._preferences_selected_page else "PreferencesNav.TButton"
                )

    def _select_preferences_page(self, page_name: str) -> None:
        if page_name not in self._preferences_pages:
            return
        self._preferences_selected_page = page_name
        for name, frame in self._preferences_pages.items():
            if hasattr(frame, "pack_forget"):
                frame.pack_forget()
            if name == page_name and hasattr(frame, "pack"):
                frame.pack(fill=tk.BOTH, expand=True)
        self._refresh_preferences_nav_styles()

    def _destroy_preferences_window(self) -> None:
        window = getattr(self, "_preferences_window", None)
        if window is not None and hasattr(window, "grab_current") and window.grab_current() == window:
            window.grab_release()
        openai_var = self._preferences_openai_key_var
        gemini_var = self._preferences_gemini_key_var
        openai_tid = self._preferences_openai_key_trace_id
        gemini_tid = self._preferences_gemini_key_trace_id
        if openai_var is not None and openai_tid is not None:
            try:
                openai_var.trace_remove("write", openai_tid)
            except (tk.TclError, ValueError):
                pass
        if gemini_var is not None and gemini_tid is not None:
            try:
                gemini_var.trace_remove("write", gemini_tid)
            except (tk.TclError, ValueError):
                pass
        self._preferences_openai_key_trace_id = None
        self._preferences_gemini_key_trace_id = None
        if window is not None and hasattr(window, "winfo_exists") and window.winfo_exists():
            window.destroy()
        self._preferences_window = None
        self._preferences_nav_buttons = {}
        self._preferences_pages = {}
        self._preferences_original_state = None
        self._preferences_checkerboard_var = None
        self._preferences_overlay_grid_var = None
        self._preferences_downsample_mode_var = None
        self._preferences_quantizer_var = None
        self._preferences_generated_shades_var = None
        self._preferences_contrast_bias_var = None
        self._preferences_palette_dither_var = None
        self._preferences_selection_threshold_var = None
        self._preferences_right_mouse_action_var = None
        self._preferences_middle_mouse_action_var = None
        self._preferences_openai_key_var = None
        self._preferences_gemini_key_var = None
        self._preferences_ai_model_id_var = None
        self._preferences_ai_model_combobox = None
        self._preferences_ai_model_hint_label = None

    def _close_preferences_window(self, *, force: bool = False) -> bool:
        if not force and self._preferences_dialog_is_dirty():
            confirmed = messagebox.askyesno(
                "Discard changes?",
                "You have unsaved preference changes. Close without saving?",
                parent=self._preferences_window,
            )
            if not confirmed:
                return False
        self._destroy_preferences_window()
        return True

    def _apply_preferences_window_changes(self) -> None:
        state = self._read_preferences_dialog_state()
        previous_settings = self.session.current
        current_state = self._capture_preferences_state()

        self.checkerboard_var.set(state.checkerboard)
        self.overlay_grid_var.set(state.overlay_grid)
        self.selection_threshold_var.set(state.selection_threshold)
        self.right_mouse_action_var.set(state.right_mouse_action)
        self.middle_mouse_action_var.set(state.middle_mouse_action)
        self.openai_api_key = state.openai_api_key
        self.gemini_api_key = state.gemini_api_key
        self.image_generation_model = coerce_selected_model(
            state.image_generation_model,
            openai_key=self.openai_api_key,
            gemini_key=self.gemini_api_key,
        )

        if state.settings != previous_settings:
            self.session.apply(**vars(state.settings))
            self._sync_controls_from_settings(state.settings)
            self._handle_settings_transition(previous_settings, state.settings)
        else:
            if state.checkerboard != current_state.checkerboard or state.overlay_grid != current_state.overlay_grid:
                self.redraw_canvas()
            if (
                state.selection_threshold != current_state.selection_threshold
                or state.right_mouse_action != current_state.right_mouse_action
                or state.middle_mouse_action != current_state.middle_mouse_action
                or state.checkerboard != current_state.checkerboard
                or state.overlay_grid != current_state.overlay_grid
                or state.openai_api_key != current_state.openai_api_key
                or state.gemini_api_key != current_state.gemini_api_key
                or state.image_generation_model != current_state.image_generation_model
            ):
                self.process_status_var.set("Preferences updated.")
                self._schedule_state_persist()
                self._refresh_action_states()

        self._preferences_original_state = state
        self._close_preferences_window(force=True)

    def _on_preferences_ai_keys_changed(self) -> None:
        self._sync_preferences_ai_model_combobox()

    def _on_preferences_ai_model_combo_selected(self, _event: tk.Event | None = None) -> None:
        combo = self._preferences_ai_model_combobox
        if combo is None or self._preferences_openai_key_var is None or self._preferences_gemini_key_var is None:
            return
        label = combo.get()
        openai_k = self._preferences_openai_key_var.get()
        gemini_k = self._preferences_gemini_key_var.get()
        for m in models_for_keys(openai_key=openai_k, gemini_key=gemini_k):
            if m.label == label and self._preferences_ai_model_id_var is not None:
                self._preferences_ai_model_id_var.set(m.id)
                return

    def _sync_preferences_ai_model_combobox(self) -> None:
        combo = getattr(self, "_preferences_ai_model_combobox", None)
        if combo is None:
            return
        hint = getattr(self, "_preferences_ai_model_hint_label", None)
        openai_k = self._preferences_openai_key_var.get() if self._preferences_openai_key_var else ""
        gemini_k = self._preferences_gemini_key_var.get() if self._preferences_gemini_key_var else ""
        options = models_for_keys(openai_key=openai_k, gemini_key=gemini_k)
        labels = [m.label for m in options]
        combo["values"] = labels
        if not labels:
            combo.set("")
            combo.configure(state="disabled")
            if hint is not None:
                hint.configure(text="Enter at least one API key to choose a model.")
            if self._preferences_ai_model_id_var is not None:
                self._preferences_ai_model_id_var.set("")
            return
        combo.configure(state="readonly")
        if hint is not None:
            hint.configure(text="")
        want_id = (self._preferences_ai_model_id_var.get() or "").strip() if self._preferences_ai_model_id_var else ""
        id_to_label = {m.id: m.label for m in options}
        if want_id not in id_to_label:
            want_id = options[0].id
            if self._preferences_ai_model_id_var is not None:
                self._preferences_ai_model_id_var.set(want_id)
        combo.set(id_to_label[want_id])

    def _generations_dir(self) -> Path:
        return self._data_path("generations")

    def open_preferences_window(self) -> None:
        if self.image_state == "processing":
            self.process_status_var.set("Preferences are unavailable while processing.")
            return
        window = getattr(self, "_preferences_window", None)
        if window is not None and hasattr(window, "winfo_exists") and window.winfo_exists():
            window.lift()
            window.focus_force()
            return

        original_state = self._capture_preferences_state()
        self._preferences_original_state = original_state
        self._preferences_selected_page = PREFERENCES_PAGE_GENERAL

        window = tk.Toplevel(self.root, bg=APP_BORDER, bd=0, highlightthickness=0)
        window.withdraw()
        window.title("Preferences")
        window.resizable(False, False)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self._close_preferences_window)
        window.bind("<Escape>", lambda _event: self._close_preferences_window(), add="+")
        self._preferences_window = window

        self._preferences_checkerboard_var = tk.BooleanVar(window, value=original_state.checkerboard)
        self._preferences_overlay_grid_var = tk.BooleanVar(window, value=original_state.overlay_grid)
        self._preferences_downsample_mode_var = tk.StringVar(
            window, value=RESIZE_VALUE_TO_DISPLAY.get(original_state.settings.downsample_mode, RESIZE_OPTIONS[0][0])
        )
        self._preferences_quantizer_var = tk.StringVar(
            window, value=QUANTIZER_VALUE_TO_DISPLAY.get(original_state.settings.quantizer, QUANTIZER_OPTIONS[0][0])
        )
        self._preferences_generated_shades_var = tk.StringVar(window, value=str(original_state.settings.generated_shades))
        self._preferences_contrast_bias_var = tk.DoubleVar(window, value=original_state.settings.contrast_bias)
        self._preferences_palette_dither_var = tk.StringVar(
            window, value=DITHER_VALUE_TO_DISPLAY.get(original_state.settings.palette_dither_mode, DITHER_OPTIONS[0][0])
        )
        self._preferences_selection_threshold_var = tk.IntVar(window, value=original_state.selection_threshold)
        self._preferences_right_mouse_action_var = tk.StringVar(window, value=original_state.right_mouse_action)
        self._preferences_middle_mouse_action_var = tk.StringVar(window, value=original_state.middle_mouse_action)
        self._preferences_openai_key_var = tk.StringVar(window, value=original_state.openai_api_key)
        self._preferences_gemini_key_var = tk.StringVar(window, value=original_state.gemini_api_key)
        self._preferences_ai_model_id_var = tk.StringVar(window, value=original_state.image_generation_model)
        self._preferences_openai_key_trace_id = self._preferences_openai_key_var.trace_add(
            "write",
            lambda *_a: self._on_preferences_ai_keys_changed(),
        )
        self._preferences_gemini_key_trace_id = self._preferences_gemini_key_var.trace_add(
            "write",
            lambda *_a: self._on_preferences_ai_keys_changed(),
        )

        shell = tk.Frame(window, bg=APP_BORDER, bd=0, highlightthickness=0)
        shell.pack(fill=tk.BOTH, expand=True)
        content = tk.Frame(shell, bg=APP_BG, bd=0, highlightthickness=0)
        content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        body = ttk.Frame(content)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 8))
        nav = ttk.Frame(body, width=PREFERENCES_NAV_WIDTH)
        nav.pack(side=tk.LEFT, fill=tk.Y)
        nav.pack_propagate(False)
        ttk.Label(nav, text="PREFERENCES").pack(anchor=tk.W, pady=(0, 8))
        divider = tk.Frame(body, bg=APP_BORDER, width=1)
        divider.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 12))
        right = ttk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        page_container = ttk.Frame(right)
        page_container.pack(fill=tk.BOTH, expand=True)
        action_row = ttk.Frame(right)
        action_row.pack(fill=tk.X, pady=(12, 0))
        apply_button = ttk.Button(action_row, text="Apply", command=self._apply_preferences_window_changes)
        apply_button.pack(side=tk.RIGHT)
        cancel_button = ttk.Button(action_row, text="Cancel", command=self._close_preferences_window)
        cancel_button.pack(side=tk.RIGHT, padx=(0, 8))

        self._preferences_nav_buttons = {}
        self._preferences_pages = {}

        def build_page(title: str) -> ttk.Frame:
            frame = ttk.Frame(page_container)
            ttk.Label(frame, text=title.upper()).pack(anchor=tk.W, pady=(0, 8))
            self._preferences_pages[title] = frame
            return frame

        general_page = build_page(PREFERENCES_PAGE_GENERAL)
        ttk.Checkbutton(general_page, text="Checkerboard background", variable=self._preferences_checkerboard_var).pack(anchor=tk.W)
        ttk.Checkbutton(general_page, text="Overlay grid", variable=self._preferences_overlay_grid_var).pack(anchor=tk.W, pady=(6, 0))
        ttk.Label(
            general_page,
            text="Overlay grid appears only on the processed preview when zoom is 400% or higher.",
            wraplength=340,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))

        resize_page = build_page(PREFERENCES_PAGE_RESIZE)
        for label, _value in RESIZE_OPTIONS:
            ttk.Radiobutton(resize_page, text=label, value=label, variable=self._preferences_downsample_mode_var).pack(anchor=tk.W)

        quantizer_page = build_page(PREFERENCES_PAGE_PALETTE_REDUCTION)
        for label, _value in QUANTIZER_OPTIONS:
            ttk.Radiobutton(quantizer_page, text=label, value=label, variable=self._preferences_quantizer_var).pack(anchor=tk.W)

        ramp_page = build_page(PREFERENCES_PAGE_COLOUR_RAMP)
        ttk.Label(ramp_page, text="Ramp Steps").pack(anchor=tk.W)
        for value in GENERATED_SHADES_OPTIONS:
            ttk.Radiobutton(
                ramp_page,
                text=str(value),
                value=str(value),
                variable=self._preferences_generated_shades_var,
            ).pack(anchor=tk.W)
        ttk.Label(ramp_page, text="Ramp Contrast").pack(anchor=tk.W, pady=(10, 0))
        for value in RAMP_CONTRAST_OPTIONS:
            contrast_value = value / 100.0
            ttk.Radiobutton(
                ramp_page,
                text=f"{value}%",
                value=contrast_value,
                variable=self._preferences_contrast_bias_var,
            ).pack(anchor=tk.W)

        dither_page = build_page(PREFERENCES_PAGE_DITHERING)
        for label, _value in DITHER_OPTIONS:
            ttk.Radiobutton(dither_page, text=label, value=label, variable=self._preferences_palette_dither_var).pack(anchor=tk.W)

        threshold_page = build_page(PREFERENCES_PAGE_SELECTION_THRESHOLD)
        for value in SELECTION_THRESHOLD_OPTIONS:
            ttk.Radiobutton(
                threshold_page,
                text=f"{value}%",
                value=value,
                variable=self._preferences_selection_threshold_var,
            ).pack(anchor=tk.W)

        mouse_page = build_page(PREFERENCES_PAGE_MOUSE_BUTTONS)
        ttk.Label(mouse_page, text="Right Mouse Button").pack(anchor=tk.W)
        for label, value in MOUSE_BUTTON_ACTION_OPTIONS:
            ttk.Radiobutton(
                mouse_page,
                text=label,
                value=value,
                variable=self._preferences_right_mouse_action_var,
            ).pack(anchor=tk.W)
        ttk.Label(mouse_page, text="Middle Mouse Button").pack(anchor=tk.W, pady=(10, 0))
        for label, value in MOUSE_BUTTON_ACTION_OPTIONS:
            ttk.Radiobutton(
                mouse_page,
                text=label,
                value=value,
                variable=self._preferences_middle_mouse_action_var,
            ).pack(anchor=tk.W)

        ai_page = build_page(PREFERENCES_PAGE_AI_IMAGE)
        ttk.Label(ai_page, text="OpenAI API key").pack(anchor=tk.W)
        ttk.Entry(ai_page, textvariable=self._preferences_openai_key_var, show="*", width=50).pack(anchor=tk.W, fill=tk.X)
        ttk.Label(
            ai_page,
            text="Gemini API key (Google AI Studio / Gemini API for Imagen)",
            wraplength=340,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(10, 0))
        ttk.Entry(ai_page, textvariable=self._preferences_gemini_key_var, show="*", width=50).pack(anchor=tk.W, fill=tk.X)
        ttk.Label(ai_page, text="Image generation model").pack(anchor=tk.W, pady=(10, 0))
        self._preferences_ai_model_combobox = ttk.Combobox(ai_page, state="readonly", width=46)
        self._preferences_ai_model_combobox.pack(anchor=tk.W, fill=tk.X)
        self._preferences_ai_model_combobox.bind("<<ComboboxSelected>>", self._on_preferences_ai_model_combo_selected)
        self._preferences_ai_model_hint_label = ttk.Label(
            ai_page,
            text="",
            wraplength=340,
            justify=tk.LEFT,
            foreground=APP_MUTED_TEXT,
        )
        self._preferences_ai_model_hint_label.pack(anchor=tk.W, pady=(6, 0))

        for page_name in PREFERENCES_PAGE_ORDER:
            button = ttk.Button(
                nav,
                text=page_name,
                style="PreferencesNav.TButton",
                command=lambda value=page_name: self._select_preferences_page(value),
            )
            button.pack(fill=tk.X, pady=(0, 4))
            self._preferences_nav_buttons[page_name] = button

        self._select_preferences_page(PREFERENCES_PAGE_GENERAL)
        self._set_preferences_dialog_state(original_state)

        self.root.update_idletasks()
        x_pos = self.root.winfo_rootx() + max(20, (self.root.winfo_width() - PREFERENCES_WINDOW_WIDTH) // 2)
        y_pos = self.root.winfo_rooty() + max(20, (self.root.winfo_height() - PREFERENCES_WINDOW_HEIGHT) // 2)
        window.geometry(f"{PREFERENCES_WINDOW_WIDTH}x{PREFERENCES_WINDOW_HEIGHT}+{x_pos}+{y_pos}")
        window.deiconify()
        window.grab_set()
        window.focus_force()

    @staticmethod
    def _indexed_color_settings_key(settings: IndexedColorSettings) -> tuple[object, ...]:
        return (
            settings.palette_method,
            settings.colors,
            settings.forced_palette,
            settings.dither_mode,
            settings.diffusion_amount,
        )

    def _indexed_color_forced_minimum(self, forced_value: str) -> int:
        return len(INDEXED_COLOR_FORCED_PALETTES.get(forced_value, ()))

    def _read_indexed_color_dialog_settings(self) -> IndexedColorSettings:
        default = getattr(self, "_indexed_color_last_settings", IndexedColorSettings())
        palette_method = INDEXED_COLOR_PALETTE_DISPLAY_TO_VALUE.get(
            self._indexed_color_palette_var.get() if self._indexed_color_palette_var is not None else "",
            default.palette_method,
        )
        forced_palette = INDEXED_COLOR_FORCED_DISPLAY_TO_VALUE.get(
            self._indexed_color_forced_var.get() if self._indexed_color_forced_var is not None else "",
            default.forced_palette,
        )
        dither_mode = INDEXED_COLOR_DITHER_DISPLAY_TO_VALUE.get(
            self._indexed_color_dither_var.get() if self._indexed_color_dither_var is not None else "",
            default.dither_mode,
        )
        try:
            colors = int(self._indexed_color_colors_var.get() if self._indexed_color_colors_var is not None else default.colors)
        except Exception:
            colors = default.colors
        try:
            diffusion_amount = int(
                self._indexed_color_amount_var.get() if self._indexed_color_amount_var is not None else default.diffusion_amount
            )
        except Exception:
            diffusion_amount = default.diffusion_amount
        colors = max(2, min(256, colors))
        colors = max(colors, self._indexed_color_forced_minimum(forced_palette))
        diffusion_amount = max(0, min(100, diffusion_amount))
        preview_enabled = bool(self._indexed_color_preview_var.get()) if self._indexed_color_preview_var is not None else default.preview_enabled
        return IndexedColorSettings(
            palette_method=palette_method,
            colors=colors,
            forced_palette=forced_palette,
            dither_mode=dither_mode,
            diffusion_amount=diffusion_amount,
            preview_enabled=preview_enabled,
        )

    def _sync_indexed_color_dialog_controls(self, settings: IndexedColorSettings) -> None:
        self._indexed_color_syncing_controls = True
        try:
            if self._indexed_color_palette_var is not None:
                self._indexed_color_palette_var.set(
                    INDEXED_COLOR_PALETTE_VALUE_TO_DISPLAY.get(settings.palette_method, INDEXED_COLOR_PALETTE_OPTIONS[0][0])
                )
            if self._indexed_color_colors_var is not None:
                self._indexed_color_colors_var.set(settings.colors)
            if self._indexed_color_forced_var is not None:
                self._indexed_color_forced_var.set(
                    INDEXED_COLOR_FORCED_VALUE_TO_DISPLAY.get(settings.forced_palette, INDEXED_COLOR_FORCED_OPTIONS[0][0])
                )
            if self._indexed_color_dither_var is not None:
                self._indexed_color_dither_var.set(
                    INDEXED_COLOR_DITHER_VALUE_TO_DISPLAY.get(settings.dither_mode, INDEXED_COLOR_DITHER_OPTIONS[0][0])
                )
            if self._indexed_color_amount_var is not None:
                self._indexed_color_amount_var.set(settings.diffusion_amount)
            if self._indexed_color_preview_var is not None:
                self._indexed_color_preview_var.set(settings.preview_enabled)
        finally:
            self._indexed_color_syncing_controls = False
        self._refresh_indexed_color_amount_state()

    def _refresh_indexed_color_amount_state(self) -> None:
        spinbox = getattr(self, "_indexed_color_amount_spinbox", None)
        if spinbox is None or not hasattr(spinbox, "configure"):
            return
        settings = self._read_indexed_color_dialog_settings()
        spinbox.configure(state="normal" if settings.dither_mode == INDEXED_COLOR_DITHER_DIFFUSION else "disabled")

    def _current_indexed_color_source_result(self) -> ProcessResult | None:
        current = self._current_output_result()
        image = self._current_output_image()
        if current is None or image is None:
            return None
        rgba = image.convert("RGBA")
        rgb_grid = image_to_rgb_grid(rgba)
        width, height = rgba.size
        alpha_values = list(rgba.getchannel("A").getdata())
        alpha_mask_rows = (
            [
                [alpha_values[(row_index * width) + column_index] > 0 for column_index in range(width)]
                for row_index in range(height)
            ]
            if height
            else []
        )
        alpha_mask = None
        if any(not visible for row in alpha_mask_rows for visible in row):
            alpha_mask = tuple(tuple(row) for row in alpha_mask_rows)
        visible_labels = {
            (red << 16) | (green << 8) | blue
            for row_index, row in enumerate(rgb_grid)
            for column_index, (red, green, blue) in enumerate(row)
            if alpha_mask is None or alpha_mask[row_index][column_index]
        }
        return ProcessResult(
            grid=rgb_grid,
            width=width,
            height=height,
            stats=replace(current.stats, output_size=(width, height), color_count=len(visible_labels)),
            prepared_input=current.prepared_input,
            display_palette_labels=current.display_palette_labels,
            structured_palette=None,
            alpha_mask=alpha_mask,
        )

    def _capture_indexed_color_snapshot(self) -> IndexedColorDialogSnapshot | None:
        source_result = self._current_indexed_color_source_result()
        if source_result is None:
            return None
        return IndexedColorDialogSnapshot(
            palette_state=self._capture_palette_state(),
            source_result=source_result,
            view_value=self.view_var.get(),
            quick_compare_active=self.quick_compare_active,
            status_text=self.process_status_var.get(),
        )

    def _restore_indexed_color_snapshot(self) -> None:
        snapshot = getattr(self, "_indexed_color_snapshot", None)
        if snapshot is None:
            return
        self._restore_palette_state(snapshot.palette_state)
        self.quick_compare_active = snapshot.quick_compare_active
        self._apply_view_selection(snapshot.view_value, persist=False)
        self.process_status_var.set(snapshot.status_text)
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._refresh_action_states()

    def _apply_indexed_color_preview_result(self, preview: IndexedColorProcessResult) -> None:
        self.palette_result = preview.result
        self.palette_display_image = process_result_to_rgba_image(preview.result)
        self._set_active_palette(list(preview.palette_labels), preview.source_label, None)
        self.advanced_palette_preview = None
        self.transparent_colors = set()
        self.image_state = "processed_current"
        self.quick_compare_active = False
        self._apply_view_selection("processed", persist=False)
        self.process_status_var.set(f"Previewing {preview.source_label}.")
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._refresh_action_states()

    def _cancel_pending_indexed_color_preview(self) -> None:
        after_id = getattr(self, "_indexed_color_preview_after_id", None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        self._indexed_color_preview_after_id = None
        self._indexed_color_preview_request_id += 1

    def _run_indexed_color_preview(self) -> None:
        self._indexed_color_preview_after_id = None
        snapshot = getattr(self, "_indexed_color_snapshot", None)
        window = getattr(self, "_indexed_color_window", None)
        if snapshot is None or window is None or not window.winfo_exists():
            return
        settings = self._read_indexed_color_dialog_settings()
        self._indexed_color_last_settings = settings
        if not settings.preview_enabled:
            self._indexed_color_preview_result = None
            self._indexed_color_preview_result_key = None
            self._restore_indexed_color_snapshot()
            return
        request_id = self._indexed_color_preview_request_id + 1
        self._indexed_color_preview_request_id = request_id
        self.process_status_var.set("Previewing Indexed Color...")
        source_result = snapshot.source_result

        def worker() -> None:
            try:
                preview = reduce_indexed_color(source_result, settings, workspace=getattr(self, "workspace", None))
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self.root.after(0, lambda: self._finish_indexed_color_preview_error(request_id, message))
                return
            self.root.after(0, lambda: self._finish_indexed_color_preview(request_id, settings, preview))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_indexed_color_preview(self, request_id: int, settings: IndexedColorSettings, preview: IndexedColorProcessResult) -> None:
        window = getattr(self, "_indexed_color_window", None)
        if window is None or not window.winfo_exists():
            return
        if request_id != getattr(self, "_indexed_color_preview_request_id", 0):
            return
        self._indexed_color_preview_result = preview
        self._indexed_color_preview_result_key = self._indexed_color_settings_key(settings)
        self._apply_indexed_color_preview_result(preview)

    def _finish_indexed_color_preview_error(self, request_id: int, message: str) -> None:
        window = getattr(self, "_indexed_color_window", None)
        if window is None or not window.winfo_exists():
            return
        if request_id != getattr(self, "_indexed_color_preview_request_id", 0):
            return
        self._restore_indexed_color_snapshot()
        messagebox.showerror("Indexed Color failed", message, parent=window)

    def _schedule_indexed_color_preview(self) -> None:
        if getattr(self, "_indexed_color_syncing_controls", False):
            return
        settings = self._read_indexed_color_dialog_settings()
        self._sync_indexed_color_dialog_controls(settings)
        self._indexed_color_last_settings = settings
        self._cancel_pending_indexed_color_preview()
        if not settings.preview_enabled:
            self._indexed_color_preview_result = None
            self._indexed_color_preview_result_key = None
            self._restore_indexed_color_snapshot()
            return
        self._indexed_color_preview_after_id = self.root.after(120, self._run_indexed_color_preview)

    def _close_indexed_color_window(self) -> None:
        self._cancel_pending_indexed_color_preview()
        window = getattr(self, "_indexed_color_window", None)
        self._indexed_color_window = None
        self._indexed_color_snapshot = None
        self._indexed_color_preview_result = None
        self._indexed_color_preview_result_key = None
        self._indexed_color_palette_var = None
        self._indexed_color_colors_var = None
        self._indexed_color_forced_var = None
        self._indexed_color_dither_var = None
        self._indexed_color_amount_var = None
        self._indexed_color_preview_var = None
        self._indexed_color_amount_spinbox = None
        self._indexed_color_ok_button = None
        if window is not None and hasattr(window, "winfo_exists") and window.winfo_exists():
            try:
                window.grab_release()
            except Exception:
                pass
            window.destroy()

    def _cancel_indexed_color_dialog(self) -> None:
        try:
            self._indexed_color_last_settings = self._read_indexed_color_dialog_settings()
        except Exception:
            pass
        self._restore_indexed_color_snapshot()
        self._close_indexed_color_window()

    def _commit_indexed_color_dialog(self) -> None:
        snapshot = getattr(self, "_indexed_color_snapshot", None)
        if snapshot is None:
            self._close_indexed_color_window()
            return
        settings = self._read_indexed_color_dialog_settings()
        self._indexed_color_last_settings = settings
        preview = getattr(self, "_indexed_color_preview_result", None)
        preview_key = getattr(self, "_indexed_color_preview_result_key", None)
        if preview is None or preview_key != self._indexed_color_settings_key(settings):
            try:
                preview = reduce_indexed_color(snapshot.source_result, settings, workspace=getattr(self, "workspace", None))
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Indexed Color failed", str(exc), parent=self._indexed_color_window)
                return
        self._palette_undo_state = snapshot.palette_state
        self._clear_palette_redo_state()
        self.palette_result = preview.result
        self._set_active_palette(list(preview.palette_labels), preview.source_label, None)
        self.advanced_palette_preview = None
        self.transparent_colors = set()
        self._reset_palette_adjustments_to_neutral()
        self._refresh_output_display_images()
        self.image_state = "processed_current"
        self.quick_compare_active = False
        self._set_view("processed")
        self.process_status_var.set(
            f"Applied {preview.source_label} with {preview.result.stats.color_count} colours in {preview.result.stats.elapsed_seconds:.2f}s."
        )
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()
        self._close_indexed_color_window()

    def open_indexed_color_window(self) -> None:
        if self.image_state == "processing":
            self.process_status_var.set("Indexed Color is unavailable while processing.")
            return
        if self._current_output_result() is None or self._current_output_image() is None:
            self.process_status_var.set("Create a processed image before opening Indexed Color.")
            return
        if self._canvas_interaction_active():
            self.process_status_var.set("Finish the active canvas action before opening Indexed Color.")
            return
        existing = getattr(self, "_indexed_color_window", None)
        if existing is not None and hasattr(existing, "winfo_exists") and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        snapshot = self._capture_indexed_color_snapshot()
        if snapshot is None:
            self.process_status_var.set("Indexed Color needs a processed image.")
            return
        self._indexed_color_snapshot = snapshot
        self._indexed_color_preview_result = None
        self._indexed_color_preview_result_key = None
        settings = replace(
            self._indexed_color_last_settings,
            colors=max(
                self._indexed_color_last_settings.colors,
                self._indexed_color_forced_minimum(self._indexed_color_last_settings.forced_palette),
            ),
        )
        self._indexed_color_last_settings = settings

        window = tk.Toplevel(self.root, bg=APP_BORDER, bd=0, highlightthickness=0)
        window.withdraw()
        window.title("Indexed Color")
        window.transient(self.root)
        window.resizable(False, False)
        self._indexed_color_window = window
        self._indexed_color_palette_var = tk.StringVar(window)
        self._indexed_color_colors_var = tk.IntVar(window)
        self._indexed_color_forced_var = tk.StringVar(window)
        self._indexed_color_dither_var = tk.StringVar(window)
        self._indexed_color_amount_var = tk.IntVar(window)
        self._indexed_color_preview_var = tk.BooleanVar(window)
        self._sync_indexed_color_dialog_controls(settings)

        window.protocol("WM_DELETE_WINDOW", self._cancel_indexed_color_dialog)
        window.bind("<Escape>", lambda _event: self._cancel_indexed_color_dialog(), add="+")
        window.bind("<Return>", lambda _event: self._commit_indexed_color_dialog(), add="+")

        shell = tk.Frame(window, bg=APP_BORDER, bd=0, highlightthickness=0)
        shell.pack(fill=tk.BOTH, expand=True)
        content = tk.Frame(shell, bg=APP_BG, bd=0, highlightthickness=0)
        content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        inner = ttk.Frame(content)
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        body = ttk.Frame(inner)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(body)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))

        palette_frame = ttk.LabelFrame(left, text="Palette")
        palette_frame.pack(fill=tk.X)
        ttk.Label(palette_frame, text="Palette:").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        palette_combo = ttk.Combobox(
            palette_frame,
            textvariable=self._indexed_color_palette_var,
            values=tuple(label for label, _value in INDEXED_COLOR_PALETTE_OPTIONS),
            state="readonly",
            width=18,
        )
        palette_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 4))
        ttk.Label(palette_frame, text="Colors:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        colors_spinbox = ttk.Spinbox(
            palette_frame,
            from_=2,
            to=256,
            textvariable=self._indexed_color_colors_var,
            width=8,
        )
        colors_spinbox.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=4)
        ttk.Label(palette_frame, text="Forced:").grid(row=2, column=0, sticky="w", padx=8, pady=(4, 8))
        forced_combo = ttk.Combobox(
            palette_frame,
            textvariable=self._indexed_color_forced_var,
            values=tuple(label for label, _value in INDEXED_COLOR_FORCED_OPTIONS),
            state="readonly",
            width=18,
        )
        forced_combo.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(4, 8))

        preview_toggle = ttk.Checkbutton(
            right,
            text="Preview",
            variable=self._indexed_color_preview_var,
            command=self._schedule_indexed_color_preview,
        )
        preview_toggle.pack(anchor=tk.W, pady=(0, 8))

        options_frame = ttk.LabelFrame(left, text="Options")
        options_frame.pack(fill=tk.X, pady=(12, 0))
        ttk.Label(options_frame, text="Dither:").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        dither_combo = ttk.Combobox(
            options_frame,
            textvariable=self._indexed_color_dither_var,
            values=tuple(label for label, _value in INDEXED_COLOR_DITHER_OPTIONS),
            state="readonly",
            width=18,
        )
        dither_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 4))
        ttk.Label(options_frame, text="Amount:").grid(row=1, column=0, sticky="w", padx=8, pady=(4, 8))
        self._indexed_color_amount_spinbox = ttk.Spinbox(
            options_frame,
            from_=0,
            to=100,
            textvariable=self._indexed_color_amount_var,
            width=8,
        )
        self._indexed_color_amount_spinbox.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(4, 8))
        ttk.Label(options_frame, text="%").grid(row=1, column=1, sticky="w", padx=(60, 0), pady=(4, 8))

        self._indexed_color_ok_button = ttk.Button(right, text="OK", command=self._commit_indexed_color_dialog)
        self._indexed_color_ok_button.pack(fill=tk.X)
        ttk.Button(right, text="Cancel", command=self._cancel_indexed_color_dialog).pack(fill=tk.X, pady=(8, 0))

        palette_frame.grid_columnconfigure(1, weight=1)
        options_frame.grid_columnconfigure(1, weight=1)
        for widget in (palette_combo, colors_spinbox, forced_combo, dither_combo, self._indexed_color_amount_spinbox):
            widget.bind("<<ComboboxSelected>>", lambda _event: self._schedule_indexed_color_preview(), add="+")
            widget.bind("<KeyRelease>", lambda _event: self._schedule_indexed_color_preview(), add="+")
            widget.bind("<<Increment>>", lambda _event: self._schedule_indexed_color_preview(), add="+")
            widget.bind("<<Decrement>>", lambda _event: self._schedule_indexed_color_preview(), add="+")

        self._refresh_indexed_color_amount_state()
        self.root.update_idletasks()
        x_pos = self.root.winfo_rootx() + max(20, (self.root.winfo_width() - INDEXED_COLOR_WINDOW_WIDTH) // 2)
        y_pos = self.root.winfo_rooty() + max(20, (self.root.winfo_height() - INDEXED_COLOR_WINDOW_HEIGHT) // 2)
        window.geometry(f"{INDEXED_COLOR_WINDOW_WIDTH}x{INDEXED_COLOR_WINDOW_HEIGHT}+{x_pos}+{y_pos}")
        window.deiconify()
        window.grab_set()
        window.focus_force()
        self._schedule_indexed_color_preview()

    def open_ai_generate_window(self) -> None:
        if self.image_state == "processing":
            self.process_status_var.set("Image generation is unavailable while processing.")
            return
        existing = getattr(self, "_ai_generate_window", None)
        if existing is not None and hasattr(existing, "winfo_exists") and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        window = tk.Toplevel(self.root, bg=APP_BORDER, bd=0, highlightthickness=0)
        window.withdraw()
        window.title("Generate image")
        window.transient(self.root)
        window.resizable(True, True)
        self._ai_generate_window = window
        self._ai_generate_cancel_event = threading.Event()

        def close_dialog() -> None:
            if self._ai_generate_cancel_event is not None:
                self._ai_generate_cancel_event.set()
            if window.winfo_exists():
                window.destroy()
            self._ai_generate_window = None
            self._ai_generate_cancel_event = None

        window.protocol("WM_DELETE_WINDOW", close_dialog)
        window.bind("<Escape>", lambda _e: close_dialog(), add="+")

        shell = tk.Frame(window, bg=APP_BORDER, bd=0, highlightthickness=0)
        shell.pack(fill=tk.BOTH, expand=True)
        content = tk.Frame(shell, bg=APP_BG, bd=0, highlightthickness=0)
        content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        inner = ttk.Frame(content)
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        ttk.Label(inner, text="PROMPT").pack(anchor=tk.W, pady=(0, 4))
        text_frame = ttk.Frame(inner)
        text_frame.pack(fill=tk.BOTH, expand=True)
        prompt_widget = scrolledtext.ScrolledText(
            text_frame,
            height=6,
            width=52,
            wrap=tk.WORD,
            bg=APP_SURFACE_BG,
            fg=APP_TEXT,
            insertbackground=APP_TEXT,
            highlightthickness=1,
            highlightbackground=APP_BORDER,
            highlightcolor=APP_BORDER,
            relief=tk.FLAT,
            font=self.ui_font,
        )
        prompt_widget.pack(fill=tk.BOTH, expand=True)
        prompt_widget.insert("1.0", "A pixel art image of ")
        prompt_widget.focus_set()

        progress = ttk.Progressbar(inner, mode="indeterminate", length=360)
        progress.pack(fill=tk.X, pady=(8, 0))
        progress.pack_forget()

        action_row = ttk.Frame(inner)
        action_row.pack(fill=tk.X, pady=(12, 0))

        def set_generating(active: bool) -> None:
            if active:
                progress.pack(fill=tk.X, pady=(8, 0))
                progress.start(12)
                generate_btn.configure(state=tk.DISABLED)
                prompt_widget.configure(state=tk.DISABLED)
            else:
                progress.stop()
                progress.pack_forget()
                generate_btn.configure(state=tk.NORMAL)
                prompt_widget.configure(state=tk.NORMAL)

        def on_generate() -> None:
            prompt_text = prompt_widget.get("1.0", tk.END).strip()
            if not prompt_text:
                messagebox.showwarning("Prompt required", "Enter a prompt before generating.", parent=window)
                return
            model_id = coerce_selected_model(
                self.image_generation_model,
                openai_key=self.openai_api_key,
                gemini_key=self.gemini_api_key,
            )
            if not model_id:
                messagebox.showerror(
                    "Model not configured",
                    "Add an API key in Preferences → AI Image and choose a model.",
                    parent=window,
                )
                return
            option = get_model_option(model_id)
            if option is None:
                messagebox.showerror("Invalid model", "The selected model is not available.", parent=window)
                return
            api_key = self.openai_api_key.strip() if option.provider == "openai" else self.gemini_api_key.strip()
            if not api_key:
                messagebox.showerror(
                    "API key required",
                    "The selected model needs a matching API key in Preferences → AI Image.",
                    parent=window,
                )
                return
            if self.original_grid is not None:
                if not messagebox.askyesno(
                    "Replace current image?",
                    "Generating will replace the current image in the editor.\n\nContinue?",
                    parent=window,
                ):
                    return
            cancel_ev = self._ai_generate_cancel_event
            if cancel_ev is None:
                return
            cancel_ev.clear()
            set_generating(True)

            def worker() -> None:
                try:
                    png_bytes = generate_image_png_bytes_with_auto_install(
                        internal_model_id=model_id,
                        api_key=api_key,
                        prompt=prompt_text,
                    )
                except Exception as exc:  # noqa: BLE001
                    msg = str(exc)
                    self.root.after(0, lambda m=msg: _finish_error(m))
                    return
                if cancel_ev.is_set():
                    return
                try:
                    out_dir = self._generations_dir()
                    out_dir.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    out_path = out_dir / f"generation-{stamp}.png"
                    out_path.write_bytes(png_bytes)
                except Exception as exc:  # noqa: BLE001
                    msg = f"Failed to save image: {exc}"
                    self.root.after(0, lambda m=msg: _finish_error(m))
                    return
                if cancel_ev.is_set():
                    try:
                        out_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    return
                self.root.after(0, lambda p=out_path: _finish_ok(p))

            def _finish_error(message: str) -> None:
                if not window.winfo_exists():
                    return
                set_generating(False)
                messagebox.showerror("Image generation failed", message, parent=window)

            def _finish_ok(path: Path) -> None:
                if not window.winfo_exists():
                    return
                if self._ai_generate_cancel_event is not None and self._ai_generate_cancel_event.is_set():
                    return
                set_generating(False)
                close_dialog()
                self._open_image_path(path)

            threading.Thread(target=worker, daemon=True).start()

        generate_btn = ttk.Button(action_row, text="Generate", command=on_generate)
        generate_btn.pack(side=tk.RIGHT)
        cancel_btn = ttk.Button(action_row, text="Cancel", command=close_dialog)
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 8))

        self.root.update_idletasks()
        w, h = 440, 320
        x_pos = self.root.winfo_rootx() + max(20, (self.root.winfo_width() - w) // 2)
        y_pos = self.root.winfo_rooty() + max(20, (self.root.winfo_height() - h) // 2)
        window.geometry(f"{w}x{h}+{x_pos}+{y_pos}")
        window.deiconify()
        window.focus_force()

    def _refresh_pick_preview_widgets(self) -> None:
        preview_frame = getattr(self, "pick_preview_frame", None)
        empty_label = getattr(self, "pick_preview_empty_label", None)
        active = self._options_tool_mode() == CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK
        sample = getattr(self, "_pick_preview_sample", None)
        self._set_packed(preview_frame, active and sample is not None, fill=tk.X, pady=(4, 0))
        self._set_packed(empty_label, active and sample is None, anchor=tk.W, pady=(4, 0))

    def _can_select_outline_tool(self) -> bool:
        return self._current_output_result() is not None and self.image_state != "processing"

    def _can_apply_add_outline_tool(self) -> bool:
        if not self._can_select_outline_tool():
            return False
        return self._outline_adaptive_enabled() or self._selected_palette_outline_label() is not None

    def _can_apply_remove_outline_tool(self) -> bool:
        return self._can_select_outline_tool()

    def _can_apply_image_filter_tool(self, mode: str | None = None) -> bool:
        normalized_mode = mode or self._options_tool_mode()
        if normalized_mode not in {CANVAS_TOOL_MODE_BLUR, CANVAS_TOOL_MODE_SHARPEN}:
            return False
        return self._current_output_result() is not None and self.image_state != "processing"

    def _image_filter_strength(self, mode: str | None = None) -> int:
        normalized_mode = mode or self._options_tool_mode() or CANVAS_TOOL_MODE_BLUR
        variable = self.sharpen_strength_var if normalized_mode == CANVAS_TOOL_MODE_SHARPEN else self.blur_strength_var
        getter = getattr(variable, "get", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = IMAGE_FILTER_STRENGTH_DEFAULT
        return self._coerce_image_filter_strength(value)

    def _set_image_filter_strength(self, mode: str, strength: int) -> None:
        normalized_mode = CANVAS_TOOL_MODE_SHARPEN if mode == CANVAS_TOOL_MODE_SHARPEN else CANVAS_TOOL_MODE_BLUR
        variable = self.sharpen_strength_var if normalized_mode == CANVAS_TOOL_MODE_SHARPEN else self.blur_strength_var
        setter = getattr(variable, "set", None)
        normalized_strength = self._coerce_image_filter_strength(strength)
        current_getter = getattr(variable, "get", None)
        current_value = current_getter() if callable(current_getter) else variable
        if callable(setter) and current_value != normalized_strength:
            setter(normalized_strength)

    def _sync_image_filter_strength_control(self, mode: str | None = None) -> None:
        normalized_mode = mode or self._options_tool_mode()
        if normalized_mode not in {CANVAS_TOOL_MODE_BLUR, CANVAS_TOOL_MODE_SHARPEN}:
            return
        variable = getattr(self, "image_filter_strength_var", None)
        setter = getattr(variable, "set", None)
        if callable(setter):
            setter(self._image_filter_strength(normalized_mode))

    def _refresh_tool_options_panel(self) -> None:
        for widget_name in (
            "options_helper_label",
            "brush_width_row",
            "brush_shape_row",
            "pick_preview_empty_label",
            "pick_preview_frame",
            "image_filter_strength_row",
            "rotate_direction_row",
            "outline_pixel_perfect_row",
            "outline_colour_mode_row",
            "outline_adaptive_row",
            "outline_add_generated_colours_row",
            "outline_remove_threshold_row",
            "outline_remove_direction_row",
            "options_apply_row",
        ):
            self._set_packed(getattr(self, widget_name, None), False)

        mode = self._options_tool_mode()
        show_helper = False
        helper_text = ""

        if mode is None:
            show_helper = True
            helper_text = "Select a tool to see its options."
        elif mode == CANVAS_TOOL_MODE_BUCKET:
            show_helper = True
            helper_text = "Bucket has no options."
        elif mode in {CANVAS_TOOL_MODE_PENCIL, CANVAS_TOOL_MODE_ERASER}:
            self._set_packed(getattr(self, "brush_width_row", None), True, fill=tk.X, pady=(4, 0))
            self._set_packed(getattr(self, "brush_shape_row", None), True, fill=tk.X, pady=(6, 0))
        elif mode == CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK:
            self._refresh_pick_preview_widgets()
        elif mode == CANVAS_TOOL_MODE_SELECT:
            show_helper = True
            helper_text = "Drag to create a rectangular selection. Drag inside a selection to move it."
        elif mode == CANVAS_TOOL_MODE_POLYGON_LASSO:
            show_helper = True
            helper_text = "Click to add points, click the first point again or double-click to finish, Backspace to remove the last point."
        elif mode in {CANVAS_TOOL_MODE_ELLIPSE, CANVAS_TOOL_MODE_RECTANGLE, CANVAS_TOOL_MODE_LINE}:
            self._set_packed(getattr(self, "brush_width_row", None), True, fill=tk.X, pady=(4, 0))
        elif mode == CANVAS_TOOL_MODE_GRADIENT:
            show_helper = True
            helper_text = "Gradient tool is not implemented yet."
        elif mode == CANVAS_TOOL_MODE_BLUR:
            self._sync_image_filter_strength_control(CANVAS_TOOL_MODE_BLUR)
            self._set_packed(getattr(self, "image_filter_strength_row", None), True, fill=tk.X, pady=(4, 0))
            self._set_packed(getattr(self, "options_apply_row", None), True, fill=tk.X, pady=(8, 0))
            show_helper = True
            helper_text = "Blur softens the whole processed image. Use strength 1-3 and click Apply."
        elif mode == CANVAS_TOOL_MODE_SHARPEN:
            self._sync_image_filter_strength_control(CANVAS_TOOL_MODE_SHARPEN)
            self._set_packed(getattr(self, "image_filter_strength_row", None), True, fill=tk.X, pady=(4, 0))
            self._set_packed(getattr(self, "options_apply_row", None), True, fill=tk.X, pady=(8, 0))
            show_helper = True
            helper_text = "Sharpen boosts edge contrast across the whole processed image. Use strength 1-3 and click Apply."
        elif mode == CANVAS_TOOL_MODE_ROTATE:
            self._set_packed(getattr(self, "rotate_direction_row", None), True, fill=tk.X, pady=(4, 0))
            self._set_packed(getattr(self, "options_apply_row", None), True, fill=tk.X, pady=(8, 0))
            show_helper = True
            helper_text = "Rotate the whole image or the active selection in 90° increments."
        elif mode == CANVAS_TOOL_MODE_ADD_OUTLINE:
            self._set_packed(getattr(self, "brush_width_row", None), True, fill=tk.X, pady=(4, 0))
            self._set_packed(getattr(self, "outline_pixel_perfect_row", None), True, fill=tk.X, pady=(6, 0))
            self._set_packed(getattr(self, "outline_colour_mode_row", None), True, fill=tk.X, pady=(6, 0))
            if self._outline_adaptive_enabled():
                self._set_packed(getattr(self, "outline_adaptive_row", None), True, fill=tk.X, pady=(6, 0))
                self._set_packed(getattr(self, "outline_add_generated_colours_row", None), True, fill=tk.X, pady=(6, 0))
            elif not self._can_apply_add_outline_tool():
                show_helper = True
                helper_text = "Select exactly one palette colour to use Selected outline colour."
            self._set_packed(getattr(self, "options_apply_row", None), True, fill=tk.X, pady=(8, 0))
        elif mode == CANVAS_TOOL_MODE_REMOVE_OUTLINE:
            self._set_packed(getattr(self, "brush_width_row", None), True, fill=tk.X, pady=(4, 0))
            self._set_packed(getattr(self, "outline_pixel_perfect_row", None), True, fill=tk.X, pady=(6, 0))
            self._set_packed(getattr(self, "outline_remove_threshold_row", None), True, fill=tk.X, pady=(6, 0))
            if self._outline_remove_brightness_threshold_enabled():
                self._set_packed(getattr(self, "outline_remove_direction_row", None), True, fill=tk.X, pady=(6, 0))
            self._set_packed(getattr(self, "options_apply_row", None), True, fill=tk.X, pady=(8, 0))

        if show_helper:
            self._set_options_helper_text(helper_text)
            self._set_packed(getattr(self, "options_helper_label", None), True, anchor=tk.W, pady=(4, 0))

    def _apply_selected_tool_options(self) -> None:
        mode = self._options_tool_mode()
        if mode == CANVAS_TOOL_MODE_ADD_OUTLINE:
            self._add_outline_from_selection()
        elif mode == CANVAS_TOOL_MODE_REMOVE_OUTLINE:
            self._remove_outline()
        elif mode == CANVAS_TOOL_MODE_BLUR:
            self._apply_blur_tool()
        elif mode == CANVAS_TOOL_MODE_SHARPEN:
            self._apply_sharpen_tool()
        elif mode == CANVAS_TOOL_MODE_ROTATE:
            self._apply_selected_rotation()

    def _brush_width(self) -> int:
        variable = getattr(self, "brush_width_var", None)
        if variable is None:
            return BRUSH_WIDTH_DEFAULT
        getter = getattr(variable, "get", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = BRUSH_WIDTH_DEFAULT
        return self._coerce_brush_width(value)

    def _brush_shape(self) -> str:
        variable = getattr(self, "brush_shape_var", None)
        if variable is None:
            return BRUSH_SHAPE_SQUARE
        getter = getattr(variable, "get", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = BRUSH_SHAPE_SQUARE
        return self._coerce_brush_shape(value)

    def _on_image_filter_strength_changed(self, _event: tk.Event | None = None) -> None:
        variable = getattr(self, "image_filter_strength_var", None)
        getter = getattr(variable, "get", None)
        setter = getattr(variable, "set", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = IMAGE_FILTER_STRENGTH_DEFAULT
        normalized = self._coerce_image_filter_strength(value)
        if callable(setter) and value != normalized:
            setter(normalized)
        mode = self._options_tool_mode()
        if mode in {CANVAS_TOOL_MODE_BLUR, CANVAS_TOOL_MODE_SHARPEN}:
            self._set_image_filter_strength(mode, normalized)
        self._schedule_state_persist()

    def _reset_brush_stroke_state(self) -> None:
        self._brush_stroke_active = False
        self._brush_stroke_last_point = None
        self._brush_stroke_changed_pixels = 0
        self._brush_stroke_tool_mode = None

    def _canvas_interaction_active(self) -> bool:
        return (
            getattr(self, "_brush_stroke_active", False)
            or getattr(self, "_shape_drag_active", False)
            or getattr(self, "_selection_drag_active", False)
            or getattr(self, "dragging", False)
            or getattr(self, "quick_compare_active", False)
            or getattr(self, "_mouse_button_action_state", None) is not None
        )

    def _reset_shape_preview_state(self) -> None:
        self._shape_drag_active = False
        self._shape_preview_anchor = None
        self._shape_preview_current = None
        self._shape_preview_tool_mode = None
        self._shape_preview_constrained = False

    def _reset_selection_drag_state(self) -> None:
        self._selection_drag_active = False
        self._selection_drag_anchor = None
        self._selection_drag_current = None
        self._floating_selection_drag_origin = None
        self._floating_selection_drag_start = None

    @staticmethod
    def _is_brush_tool_mode(mode: str | None) -> bool:
        return mode in {CANVAS_TOOL_MODE_PENCIL, CANVAS_TOOL_MODE_ERASER}

    @staticmethod
    def _is_shape_tool_mode(mode: str | None) -> bool:
        return mode in {CANVAS_TOOL_MODE_ELLIPSE, CANVAS_TOOL_MODE_RECTANGLE, CANVAS_TOOL_MODE_LINE}

    def _brush_tool_mode_active(self) -> bool:
        return self._is_brush_tool_mode(self._canvas_tool_mode_value())

    def _shape_tool_mode_active(self) -> bool:
        return self._is_shape_tool_mode(self._canvas_tool_mode_value())

    @staticmethod
    def _brush_tool_display_name(mode: str | None) -> str:
        if mode == CANVAS_TOOL_MODE_ERASER:
            return "Eraser"
        return "Pencil"

    @staticmethod
    def _shape_tool_display_name(mode: str | None, *, constrained: bool = False) -> str:
        if mode == CANVAS_TOOL_MODE_LINE:
            return "Line"
        if mode == CANVAS_TOOL_MODE_ELLIPSE:
            return "Circle" if constrained else "Ellipse"
        return "Square" if constrained else "Rectangle"

    def _selected_palette_brush_label(self) -> int | None:
        if self._slot_is_transparent(ACTIVE_COLOR_SLOT_PRIMARY):
            return None
        return self._slot_color_label(ACTIVE_COLOR_SLOT_PRIMARY)

    def _primary_brush_uses_transparency(self) -> bool:
        return self._slot_is_transparent(ACTIVE_COLOR_SLOT_PRIMARY)

    def _shape_fill_label(self) -> int | None:
        if self._slot_is_transparent(ACTIVE_COLOR_SLOT_SECONDARY):
            return None
        return self._slot_color_label(ACTIVE_COLOR_SLOT_SECONDARY)

    @staticmethod
    def _event_has_shift(event: tk.Event | object) -> bool:
        return bool(int(getattr(event, "state", 0) or 0) & EVENT_STATE_SHIFT_MASK)

    @staticmethod
    def _constrain_shape_endpoint(
        anchor: tuple[int, int],
        point: tuple[int, int],
        *,
        image_width: int,
        image_height: int,
    ) -> tuple[int, int]:
        anchor_x, anchor_y = anchor
        point_x, point_y = point
        delta_x = point_x - anchor_x
        delta_y = point_y - anchor_y
        sign_x = -1 if delta_x < 0 else 1
        sign_y = -1 if delta_y < 0 else 1
        max_x = anchor_x if sign_x < 0 else max(0, image_width - 1 - anchor_x)
        max_y = anchor_y if sign_y < 0 else max(0, image_height - 1 - anchor_y)
        size = min(max(abs(delta_x), abs(delta_y)), max_x, max_y)
        return (anchor_x + (size * sign_x), anchor_y + (size * sign_y))

    def _resolved_shape_preview_endpoint(self, result: ProcessResult) -> tuple[int, int] | None:
        anchor = getattr(self, "_shape_preview_anchor", None)
        current = getattr(self, "_shape_preview_current", None)
        if anchor is None or current is None:
            return None
        if not getattr(self, "_shape_preview_constrained", False):
            return current
        if getattr(self, "_shape_preview_tool_mode", None) not in {
            CANVAS_TOOL_MODE_ELLIPSE,
            CANVAS_TOOL_MODE_RECTANGLE,
        }:
            return current
        return self._constrain_shape_endpoint(anchor, current, image_width=result.width, image_height=result.height)

    def _editable_palette_labels(self) -> list[int]:
        palette, _source = self._get_display_palette()
        return list(palette)

    @staticmethod
    def _parse_hex_palette_colour(value: str) -> int:
        normalized = value.strip().upper()
        if normalized.startswith("#"):
            normalized = normalized[1:]
        if len(normalized) != 6 or any(character not in "0123456789ABCDEF" for character in normalized):
            raise ValueError("Enter a colour in #RRGGBB format.")
        return int(normalized, 16)

    def _apply_palette_edit(self, palette: list[int], message: str) -> None:
        self._palette_selection_indices = set()
        self._palette_selection_anchor_index = None
        self._apply_active_palette(
            palette,
            "Edited Palette",
            None,
            message=message,
            capture_undo=True,
        )

    def _add_colour_to_current_palette(self, label: int) -> bool:
        palette = self._editable_palette_labels()
        if label in palette:
            self.process_status_var.set(f"#{label:06X} is already in the current palette.")
            return False
        palette.append(label)
        self._apply_palette_edit(palette, f"Added #{label:06X} to the current palette. Click Apply Palette to update the preview.")
        return True

    def _remove_selected_palette_colors(self) -> None:
        palette = self._editable_palette_labels()
        if not palette:
            self.process_status_var.set("There is no current palette to edit.")
            return
        selected = sorted(index for index in self._palette_selection_indices if 0 <= index < len(palette))
        if not selected:
            self.process_status_var.set("Select one or more palette colours to remove.")
            return
        remaining = [label for index, label in enumerate(palette) if index not in set(selected)]
        removed_count = len(palette) - len(remaining)
        self._apply_palette_edit(
            remaining,
            f"Removed {removed_count} palette colour{'s' if removed_count != 1 else ''}. Click Apply Palette to update the preview.",
        )

    def _start_palette_add_pick_mode(self) -> None:
        if self.original_display_image is None or self.image_state == "processing":
            self.process_status_var.set("Open an image before adding colours to the current palette.")
            return
        self._set_canvas_tool_mode(CANVAS_TOOL_MODE_PALETTE_PICK)
        self._refresh_action_states()

    def _start_active_color_pick_mode(self) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before picking a colour.")
            return
        self._set_canvas_tool_mode(CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK)
        self._refresh_action_states()

    def _toggle_palette_add_pick_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_PALETTE_PICK:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Palette colour pick cancelled.")
        else:
            self._start_palette_add_pick_mode()
            return
        self._refresh_action_states()

    def _toggle_active_color_pick_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Active colour pick cancelled.")
        else:
            self._start_active_color_pick_mode()
            return
        self._refresh_action_states()

    def _prompt_add_palette_color_hex(self) -> None:
        value = simpledialog.askstring("Add Palette Colour", "Enter a hex colour (#RRGGBB):", parent=self.root)
        if value is None:
            return
        try:
            label = self._parse_hex_palette_colour(value)
        except ValueError as exc:
            messagebox.showerror("Invalid colour", str(exc))
            return
        self._add_colour_to_current_palette(label)
        self._refresh_action_states()

    def _palette_is_override_mode(self) -> bool:
        return self.active_palette is not None

    def _selected_palette_indices(self, palette: list[int]) -> list[int]:
        return sorted(index for index in self._palette_selection_indices if 0 <= index < len(palette))

    def _toggle_transparency_pick_mode(self) -> None:
        if self._current_output_image() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before making colours transparent.")
            return
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_TRANSPARENCY_PICK:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Transparency pick cancelled.")
        else:
            self._set_canvas_tool_mode(CANVAS_TOOL_MODE_TRANSPARENCY_PICK)
        self._refresh_action_states()

    def _start_pencil_mode(self) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before drawing.")
            return
        if self._selected_palette_brush_label() is None and not self._primary_brush_uses_transparency():
            self.process_status_var.set("Set a non-transparent primary colour to draw.")
            return
        self._set_canvas_tool_mode(CANVAS_TOOL_MODE_PENCIL)
        self._refresh_action_states()

    def _toggle_pencil_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_PENCIL:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Pencil cancelled.")
        else:
            self._start_pencil_mode()
            return
        self._refresh_action_states()

    def _start_bucket_mode(self) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before filling.")
            return
        if self._selected_palette_brush_label() is None and not self._primary_brush_uses_transparency():
            self.process_status_var.set("Set a non-transparent primary colour to fill.")
            return
        self._set_canvas_tool_mode(CANVAS_TOOL_MODE_BUCKET)
        self._refresh_action_states()

    def _toggle_bucket_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_BUCKET:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Bucket cancelled.")
        else:
            self._start_bucket_mode()
            return
        self._refresh_action_states()

    def _toggle_eraser_mode(self) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before erasing.")
            return
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_ERASER:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Eraser cancelled.")
        else:
            self._set_canvas_tool_mode(CANVAS_TOOL_MODE_ERASER)
        self._refresh_action_states()

    def _start_shape_tool_mode(self, mode: str, *, action_name: str) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set(f"Create a processed image before drawing a {action_name.lower()}.")
            return
        if self._selected_palette_brush_label() is None:
            self.process_status_var.set(f"Set a non-transparent primary colour to draw a {action_name.lower()}.")
            return
        self._set_canvas_tool_mode(mode)
        self._refresh_action_states()

    def _toggle_ellipse_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_ELLIPSE:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Ellipse cancelled.")
        else:
            self._start_shape_tool_mode(CANVAS_TOOL_MODE_ELLIPSE, action_name="Ellipse")
            return
        self._refresh_action_states()

    def _toggle_rectangle_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_RECTANGLE:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Rectangle cancelled.")
        else:
            self._start_shape_tool_mode(CANVAS_TOOL_MODE_RECTANGLE, action_name="Rectangle")
            return
        self._refresh_action_states()

    def _toggle_line_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_LINE:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Line cancelled.")
        else:
            self._start_shape_tool_mode(CANVAS_TOOL_MODE_LINE, action_name="Line")
            return
        self._refresh_action_states()

    def _toggle_gradient_mode(self) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before using gradient.")
            return
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_GRADIENT:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Gradient cancelled.")
        else:
            self._set_canvas_tool_mode(CANVAS_TOOL_MODE_GRADIENT)
        self._refresh_action_states()

    def _start_image_filter_tool_mode(self, mode: str, *, action_name: str) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set(f"Create a processed image before using {action_name.lower()}.")
            return
        self._set_canvas_tool_mode(mode)
        self._refresh_action_states()

    def _toggle_blur_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_BLUR:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Blur cancelled.")
        else:
            self._start_image_filter_tool_mode(CANVAS_TOOL_MODE_BLUR, action_name="Blur")
            return
        self._refresh_action_states()

    def _toggle_sharpen_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_SHARPEN:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Sharpen cancelled.")
        else:
            self._start_image_filter_tool_mode(CANVAS_TOOL_MODE_SHARPEN, action_name="Sharpen")
            return
        self._refresh_action_states()

    def _start_outline_tool_mode(self, mode: str, *, action_name: str) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set(f"Create a processed image before using {action_name.lower()}.")
            return
        self._set_canvas_tool_mode(mode)
        self._refresh_action_states()

    def _toggle_add_outline_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_ADD_OUTLINE:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Add outline cancelled.")
        else:
            self._start_outline_tool_mode(CANVAS_TOOL_MODE_ADD_OUTLINE, action_name="Add Outline")
            return
        self._refresh_action_states()

    def _toggle_remove_outline_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_REMOVE_OUTLINE:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Remove outline cancelled.")
        else:
            self._start_outline_tool_mode(CANVAS_TOOL_MODE_REMOVE_OUTLINE, action_name="Remove Outline")
            return
        self._refresh_action_states()

    def _selection_mask(self) -> tuple[tuple[bool, ...], ...] | None:
        selection = getattr(self, "_image_selection", None)
        return None if selection is None else selection.mask

    def _selection_bounds(self) -> PixelSelectionBounds | None:
        selection = getattr(self, "_image_selection", None)
        return None if selection is None else selection.bounds

    def _clear_canvas_selection_state(self) -> None:
        self._image_selection = None
        self._floating_selection = None
        self._lasso_points = []
        self._lasso_hover_point = None
        self._lasso_hover_point_canvas = None
        self._reset_selection_drag_state()

    def _clear_image_selection(self) -> None:
        self._image_selection = None

    def _set_image_selection(
        self,
        mask: tuple[tuple[bool, ...], ...] | list[list[bool]] | None,
        *,
        outline_points: tuple[tuple[int, int], ...] | list[tuple[int, int]] = (),
    ) -> None:
        bounds = selection_mask_bounds(mask)
        if bounds is None:
            self._image_selection = None
            return
        normalized_mask = tuple(tuple(bool(value) for value in row) for row in mask)
        selected_pixels = sum(1 for row in normalized_mask for value in row if value)
        if selected_pixels <= 1:
            self._image_selection = None
            return
        self._image_selection = ImageSelectionState(
            mask=normalized_mask,
            bounds=bounds,
            outline_points=tuple((int(x), int(y)) for x, y in outline_points),
        )

    def _set_rect_selection_for_bounds(self, bounds: PixelSelectionBounds | None) -> None:
        current = self._current_output_result()
        if current is None or bounds is None:
            self._image_selection = None
            return
        mask = rasterize_rectangle_selection_mask(
            current.width,
            current.height,
            bounds.left,
            bounds.top,
            bounds.right - 1,
            bounds.bottom - 1,
        )
        self._set_image_selection(mask, outline_points=self._selection_outline_points_for_bounds(bounds))

    @staticmethod
    def _selection_outline_points_for_bounds(bounds: PixelSelectionBounds) -> tuple[tuple[int, int], ...]:
        return (
            (bounds.left, bounds.top),
            (bounds.right, bounds.top),
            (bounds.right, bounds.bottom),
            (bounds.left, bounds.bottom),
        )

    def _selection_contains_point(self, image_x: int, image_y: int) -> bool:
        selection = getattr(self, "_image_selection", None)
        if selection is None:
            return False
        if image_y < 0 or image_y >= len(selection.mask):
            return False
        if image_x < 0 or image_x >= len(selection.mask[image_y]):
            return False
        return bool(selection.mask[image_y][image_x])

    def _floating_selection_contains_point(self, image_x: int, image_y: int) -> bool:
        floating = getattr(self, "_floating_selection", None)
        if floating is None:
            return False
        local_x = image_x - floating.left
        local_y = image_y - floating.top
        if local_x < 0 or local_y < 0 or local_x >= floating.payload.width or local_y >= floating.payload.height:
            return False
        alpha_mask = floating.payload.alpha_mask
        return True if alpha_mask is None else bool(alpha_mask[local_y][local_x])

    @staticmethod
    def _clamp_payload_position(
        image_width: int,
        image_height: int,
        payload: SelectionPayload,
        left: int,
        top: int,
    ) -> tuple[int, int]:
        min_left = min(0, image_width - payload.width)
        max_left = max(0, image_width - payload.width)
        min_top = min(0, image_height - payload.height)
        max_top = max(0, image_height - payload.height)
        return max(min_left, min(max_left, int(left))), max(min_top, min(max_top, int(top)))

    def _selection_centered_position(
        self,
        payload: SelectionPayload,
        *,
        reference_bounds: PixelSelectionBounds | None = None,
    ) -> tuple[int, int]:
        current = self._current_output_result()
        if current is None:
            return 0, 0
        if reference_bounds is None:
            left = (current.width - payload.width) // 2
            top = (current.height - payload.height) // 2
        else:
            left = reference_bounds.left + ((reference_bounds.width - payload.width) // 2)
            top = reference_bounds.top + ((reference_bounds.height - payload.height) // 2)
        return self._clamp_payload_position(current.width, current.height, payload, left, top)

    def _sync_downsample_after_canvas_edit(self, updated: ProcessResult) -> ProcessResult:
        if getattr(self, "palette_result", None) is not None:
            return updated
        prepared_input = self._prepared_input_from_result(updated)
        self.prepared_input_cache = prepared_input
        self.prepared_input_cache_key = None
        return replace(updated, prepared_input=prepared_input)

    def _refresh_after_canvas_edit(self, status_text: str) -> None:
        self.process_status_var.set(status_text)
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _lasso_hover_is_near_start(self, image_width: int, image_height: int) -> bool:
        if len(getattr(self, "_lasso_points", [])) < 3:
            return False
        hover = getattr(self, "_lasso_hover_point_canvas", None)
        if hover is None:
            return False
        start = self._lasso_points[0]
        sx = self._image_x_to_canvas(start[0] + 0.5, image_width)
        sy = self._image_y_to_canvas(start[1] + 0.5, image_height)
        return (hover[0] - sx) ** 2 + (hover[1] - sy) ** 2 <= _LASSO_CLOSE_RADIUS_PX ** 2

    def _cancel_polygon_lasso(self) -> bool:
        if not getattr(self, "_lasso_points", []) and getattr(self, "_lasso_hover_point", None) is None:
            return False
        self._lasso_points = []
        self._lasso_hover_point = None
        self._lasso_hover_point_canvas = None
        self._reset_selection_drag_state()
        self._redraw_selection_overlays_only()
        self._refresh_action_states()
        return True

    def _clear_canvas_selection(self, status_text: str = "Selection cleared.") -> bool:
        has_selection = bool(
            getattr(self, "_image_selection", None) is not None
            or getattr(self, "_floating_selection", None) is not None
            or getattr(self, "_lasso_points", [])
            or getattr(self, "_lasso_hover_point", None) is not None
        )
        if not has_selection:
            return False
        self._clear_canvas_selection_state()
        self.process_status_var.set(status_text)
        self.redraw_canvas()
        self._refresh_action_states()
        return True

    def _finalize_polygon_lasso(self) -> bool:
        current = self._current_output_result()
        if current is None:
            return False
        points = list(getattr(self, "_lasso_points", []))
        while len(points) >= 2 and points[-1] == points[-2]:
            points.pop()
        if len(points) < 3:
            self.process_status_var.set("Polygonal lasso needs at least three points.")
            return False
        mask = rasterize_polygon_selection_mask(current.width, current.height, points)
        if mask is None:
            self.process_status_var.set("Polygonal lasso selection is empty.")
            return False
        self._floating_selection = None
        self._set_image_selection(mask, outline_points=tuple(points))
        self._lasso_points = []
        self._lasso_hover_point = None
        self._lasso_hover_point_canvas = None
        if self._image_selection is None:
            self.process_status_var.set("Single-pixel selections are ignored.")
        else:
            self.process_status_var.set("Polygonal lasso selection created.")
        self.redraw_canvas()
        self._refresh_action_states()
        return True

    def _lift_current_selection(self) -> bool:
        current = self._current_output_result()
        selection = getattr(self, "_image_selection", None)
        if current is None or selection is None:
            return False
        payload, bounds = extract_selection_payload(current, selection.mask)
        if payload is None or bounds is None:
            return False
        base_result, _changed = apply_delete_selection(current, selection.mask)
        self._floating_selection = FloatingSelectionState(
            payload=payload,
            left=bounds.left,
            top=bounds.top,
            base_result=base_result,
            restore_result=current,
            source_bounds=bounds,
        )
        self._image_selection = None
        return True

    def _copy_image_selection(self) -> None:
        current = self._current_output_result()
        if current is None:
            self.process_status_var.set("Create a processed image before copying a selection.")
            return
        payload: SelectionPayload | None = None
        bounds: PixelSelectionBounds | None = None
        if getattr(self, "_floating_selection", None) is not None:
            payload = self._floating_selection.payload
            bounds = PixelSelectionBounds(
                left=self._floating_selection.left,
                top=self._floating_selection.top,
                right=self._floating_selection.left + self._floating_selection.payload.width,
                bottom=self._floating_selection.top + self._floating_selection.payload.height,
            )
        elif self._selection_mask() is not None:
            payload, bounds = extract_selection_payload(current, self._selection_mask())
        if payload is None:
            self.process_status_var.set("Select an area before copying.")
            return
        self._selection_clipboard = ClipboardSelectionState(payload=payload, bounds=bounds)
        self.process_status_var.set("Copied the current selection.")
        self._refresh_action_states()

    def _cut_image_selection(self) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before cutting a selection.")
            return
        floating = getattr(self, "_floating_selection", None)
        if floating is not None:
            self._selection_clipboard = ClipboardSelectionState(
                payload=floating.payload,
                bounds=PixelSelectionBounds(
                    left=floating.left,
                    top=floating.top,
                    right=floating.left + floating.payload.width,
                    bottom=floating.top + floating.payload.height,
                ),
            )
            if floating.source_bounds is None:
                self._floating_selection = None
                self.process_status_var.set("Copied the floating selection to the clipboard.")
                self.redraw_canvas()
                self._refresh_action_states()
                return
            self._capture_palette_undo_state()
            self._clear_palette_redo_state()
            updated = self._sync_downsample_after_canvas_edit(floating.base_result)
            self.transparent_colors = set()
            self._set_current_output_result(updated)
            self._refresh_output_display_images()
            self._floating_selection = None
            self._set_rect_selection_for_bounds(floating.source_bounds)
            self._refresh_after_canvas_edit("Cut the current selection. Press Undo to restore it.")
            return
        selection_mask = self._selection_mask()
        if selection_mask is None:
            self.process_status_var.set("Select an area before cutting.")
            return
        updated, payload, bounds, changed = apply_cut_selection(current, selection_mask)
        if payload is None or bounds is None:
            self.process_status_var.set("Select an area before cutting.")
            return
        self._selection_clipboard = ClipboardSelectionState(payload=payload, bounds=bounds)
        if changed <= 0:
            self.process_status_var.set("Copied the selection. Selected pixels were already transparent.")
            self._refresh_action_states()
            return
        self._capture_palette_undo_state()
        self._clear_palette_redo_state()
        updated = self._sync_downsample_after_canvas_edit(updated)
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self._set_rect_selection_for_bounds(bounds)
        self._refresh_after_canvas_edit("Cut the current selection. Press Undo to restore it.")

    def _delete_image_selection(self) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before deleting a selection.")
            return
        floating = getattr(self, "_floating_selection", None)
        if floating is not None:
            if floating.source_bounds is None:
                self._floating_selection = None
                self.process_status_var.set("Deleted the floating selection preview.")
                self.redraw_canvas()
                self._refresh_action_states()
                return
            self._capture_palette_undo_state()
            self._clear_palette_redo_state()
            updated = self._sync_downsample_after_canvas_edit(floating.base_result)
            self.transparent_colors = set()
            self._set_current_output_result(updated)
            self._refresh_output_display_images()
            self._floating_selection = None
            self._set_rect_selection_for_bounds(floating.source_bounds)
            self._refresh_after_canvas_edit("Deleted the current selection. Press Undo to restore it.")
            return
        selection_mask = self._selection_mask()
        bounds = self._selection_bounds()
        if selection_mask is None or bounds is None:
            self.process_status_var.set("Select an area before deleting.")
            return
        updated, changed = apply_delete_selection(current, selection_mask)
        if changed <= 0:
            self.process_status_var.set("Selected pixels are already transparent.")
            return
        self._capture_palette_undo_state()
        self._clear_palette_redo_state()
        updated = self._sync_downsample_after_canvas_edit(updated)
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self._set_rect_selection_for_bounds(bounds)
        self._refresh_after_canvas_edit("Deleted the current selection. Press Undo to restore it.")

    def _paste_image_selection(self) -> None:
        current = self._current_output_result()
        clipboard = getattr(self, "_selection_clipboard", None)
        if current is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before pasting.")
            return
        if clipboard is None:
            self.process_status_var.set("The internal clipboard is empty.")
            return
        if getattr(self, "_floating_selection", None) is not None:
            self._commit_floating_selection()
        payload = clipboard.payload
        reference_bounds = clipboard.bounds or self._selection_bounds()
        if reference_bounds is not None:
            left, top = self._clamp_payload_position(current.width, current.height, payload, reference_bounds.left, reference_bounds.top)
        else:
            left, top = self._selection_centered_position(payload)
        self._set_view("processed")
        self._clear_image_selection()
        self._floating_selection = FloatingSelectionState(
            payload=payload,
            left=left,
            top=top,
            base_result=current,
            restore_result=current,
            source_bounds=None,
        )
        self._set_canvas_tool_mode(CANVAS_TOOL_MODE_SELECT)
        self.process_status_var.set("Pasted the clipboard as a floating selection. Drag it to reposition before committing.")
        self.redraw_canvas()
        self._refresh_action_states()

    def _commit_floating_selection(self, *_args: object) -> bool:
        floating = getattr(self, "_floating_selection", None)
        if floating is None:
            return False
        updated, bounds, changed = composite_selection_payload(
            floating.base_result,
            floating.payload,
            left=floating.left,
            top=floating.top,
        )
        self._floating_selection = None
        if changed <= 0:
            self._set_rect_selection_for_bounds(bounds if floating.source_bounds is not None else None)
            self.redraw_canvas()
            self._refresh_action_states()
            return False
        self._capture_palette_undo_state()
        self._clear_palette_redo_state()
        updated = self._sync_downsample_after_canvas_edit(updated)
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self._set_rect_selection_for_bounds(bounds)
        self._refresh_after_canvas_edit("Committed the floating selection. Press Undo to restore it.")
        return True

    def _cancel_floating_selection(self) -> bool:
        floating = getattr(self, "_floating_selection", None)
        if floating is None:
            return False
        source_bounds = floating.source_bounds
        self._floating_selection = None
        self._set_rect_selection_for_bounds(source_bounds)
        self.process_status_var.set("Cancelled the floating selection.")
        self.redraw_canvas()
        self._refresh_action_states()
        return True

    def _deselect_image_selection(self) -> None:
        if self._cancel_polygon_lasso():
            self.process_status_var.set("Cancelled the polygonal lasso.")
            return
        if getattr(self, "_floating_selection", None) is not None:
            self._commit_floating_selection()
        if getattr(self, "_image_selection", None) is None:
            self.process_status_var.set("There is no active selection.")
            return
        self._image_selection = None
        self.process_status_var.set("Selection cleared.")
        self.redraw_canvas()
        self._refresh_action_states()

    def _start_select_mode(self) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before selecting pixels.")
            return
        self._set_canvas_tool_mode(CANVAS_TOOL_MODE_SELECT)
        self._refresh_action_states()

    def _toggle_select_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_SELECT:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Selection tool cancelled.")
        else:
            self._start_select_mode()
            return
        self._refresh_action_states()

    def _start_polygon_lasso_mode(self) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before using polygonal lasso.")
            return
        self._set_canvas_tool_mode(CANVAS_TOOL_MODE_POLYGON_LASSO)
        self._refresh_action_states()

    def _toggle_polygon_lasso_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_POLYGON_LASSO:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Polygonal lasso cancelled.")
        else:
            self._start_polygon_lasso_mode()
            return
        self._refresh_action_states()

    def _start_rotate_mode(self) -> None:
        if self._current_output_result() is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before rotating.")
            return
        self._set_canvas_tool_mode(CANVAS_TOOL_MODE_ROTATE)
        self._refresh_action_states()

    def _toggle_rotate_mode(self) -> None:
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_ROTATE:
            self._set_canvas_tool_mode(None)
            self.process_status_var.set("Rotate cancelled.")
        else:
            self._start_rotate_mode()
            return
        self._refresh_action_states()

    def _select_rotate_direction(self, direction: str) -> None:
        normalized = direction if direction in ROTATE_DIRECTION_LABELS else ROTATE_DIRECTION_90_CW
        self.rotate_direction_var.set(normalized)
        self.rotate_direction_display_var.set(ROTATE_DIRECTION_LABELS[normalized])
        self._refresh_tool_options_panel()

    def _rotation_turns(self) -> int:
        return ROTATE_DIRECTION_TO_TURNS.get(self.rotate_direction_var.get(), 1)

    def _transform_floating_selection(
        self,
        transform: object,
        *,
        action_name: str,
    ) -> bool:
        floating = getattr(self, "_floating_selection", None)
        if floating is None:
            return False
        if not callable(transform):
            return False
        payload = transform(floating.payload)
        left = floating.left + ((floating.payload.width - payload.width) // 2)
        top = floating.top + ((floating.payload.height - payload.height) // 2)
        base_result = floating.base_result
        left, top = self._clamp_payload_position(base_result.width, base_result.height, payload, left, top)
        self._floating_selection = replace(floating, payload=payload, left=left, top=top)
        self.process_status_var.set(f"{action_name} applied to the floating selection.")
        self.redraw_canvas()
        self._refresh_action_states()
        return True

    def _transform_static_selection(
        self,
        transform: object,
        *,
        action_name: str,
    ) -> bool:
        current = self._current_output_result()
        selection = getattr(self, "_image_selection", None)
        if current is None or selection is None or not callable(transform):
            return False
        payload, bounds = extract_selection_payload(current, selection.mask)
        if payload is None or bounds is None:
            return False
        base_result, removed = apply_delete_selection(current, selection.mask)
        transformed = transform(payload)
        left, top = self._selection_centered_position(transformed, reference_bounds=bounds)
        updated, transformed_bounds, changed = composite_selection_payload(base_result, transformed, left=left, top=top)
        if changed <= 0 and removed <= 0:
            return False
        self._capture_palette_undo_state()
        self._clear_palette_redo_state()
        updated = self._sync_downsample_after_canvas_edit(updated)
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self._set_rect_selection_for_bounds(transformed_bounds)
        self._refresh_after_canvas_edit(f"{action_name} applied to the current selection. Press Undo to restore it.")
        return True

    def _apply_whole_image_transform(
        self,
        transform: object,
        *,
        action_name: str,
    ) -> bool:
        current = self._current_output_result()
        if current is None or not callable(transform):
            return False
        updated, changed = transform(current)
        if changed <= 0:
            return False
        self._capture_palette_undo_state()
        self._clear_palette_redo_state()
        updated = self._sync_downsample_after_canvas_edit(updated)
        self.transparent_colors = set()
        self._clear_canvas_selection_state()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self.comparison_original_image = None
        self._comparison_original_key = None
        self._refresh_after_canvas_edit(f"{action_name} applied to the image. Press Undo to restore it.")
        return True

    def _flip_image_horizontal(self) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before flipping.")
            return
        self._set_view("processed")
        if self._transform_floating_selection(flip_selection_payload_horizontal, action_name="Flip horizontal"):
            return
        if self._transform_static_selection(flip_selection_payload_horizontal, action_name="Flip horizontal"):
            return
        if not self._apply_whole_image_transform(apply_flip_horizontal, action_name="Flip horizontal"):
            self.process_status_var.set("Nothing changed.")

    def _flip_image_vertical(self) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before flipping.")
            return
        self._set_view("processed")
        if self._transform_floating_selection(flip_selection_payload_vertical, action_name="Flip vertical"):
            return
        if self._transform_static_selection(flip_selection_payload_vertical, action_name="Flip vertical"):
            return
        if not self._apply_whole_image_transform(apply_flip_vertical, action_name="Flip vertical"):
            self.process_status_var.set("Nothing changed.")

    def _apply_rotation_turns(self, turns: int) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            self.process_status_var.set("Create a processed image before rotating.")
            return
        self._set_view("processed")
        if self._transform_floating_selection(lambda payload: rotate_selection_payload(payload, turns), action_name="Rotate"):
            return
        if self._transform_static_selection(lambda payload: rotate_selection_payload(payload, turns), action_name="Rotate"):
            return
        if not self._apply_whole_image_transform(lambda result: apply_rotate(result, turns), action_name="Rotate"):
            self.process_status_var.set("Nothing changed.")

    def _apply_selected_rotation(self) -> None:
        self._apply_rotation_turns(self._rotation_turns())

    def _select_outline_colour_mode(self, mode: str) -> None:
        variable = getattr(self, "outline_colour_mode_var", None)
        setter = getattr(variable, "set", None)
        if callable(setter):
            setter(mode)
        self._on_outline_colour_mode_changed()

    def _select_outline_remove_brightness_direction(self, direction: str) -> None:
        variable = getattr(self, "outline_remove_brightness_threshold_direction_var", None)
        setter = getattr(variable, "set", None)
        if callable(setter):
            setter(direction)
        self._on_outline_remove_brightness_threshold_direction_changed()

    def _merge_selected_palette_colors(self) -> None:
        palette = self._editable_palette_labels()
        if not palette:
            self.process_status_var.set("There is no current palette to edit.")
            return
        selected = self._selected_palette_indices(palette)
        if len(selected) < 2:
            self.process_status_var.set("Select 2 or more palette colours to merge.")
            return
        merged_label = merge_palette_labels([palette[index] for index in selected], workspace=self.workspace)
        selected_set = set(selected)
        first_selected = selected[0]
        merged_palette: list[int] = []
        for index, label in enumerate(palette):
            if index == first_selected:
                merged_palette.append(merged_label)
            if index not in selected_set:
                merged_palette.append(label)
        self._apply_palette_edit(
            merged_palette,
            f"Merged {len(selected)} palette colour{'s' if len(selected) != 1 else ''} into #{merged_label:06X}. Click Apply Palette to update the preview.",
        )

    def _ramp_selected_palette_colors(self) -> None:
        palette = self._editable_palette_labels()
        if not palette:
            self.process_status_var.set("There is no current palette to edit.")
            return
        selected = self._selected_palette_indices(palette)
        if not selected:
            self.process_status_var.set("Select one or more palette colours to ramp.")
            return
        try:
            settings = self._read_settings_from_controls(strict=False)
        except Exception:
            settings = getattr(getattr(self, "session", None), "current", PreviewSettings())
        ramp_labels = generate_ramp_palette_labels(
            [palette[index] for index in selected],
            generated_shades=settings.generated_shades,
            contrast_bias=settings.contrast_bias,
            workspace=self.workspace,
        )
        if not ramp_labels:
            self.process_status_var.set("No ramp colours were generated from the selection.")
            return
        updated_palette = palette + ramp_labels
        self._apply_palette_edit(
            updated_palette,
            f"Appended {len(ramp_labels)} ramp colour{'s' if len(ramp_labels) != 1 else ''} from {len(selected)} selected palette colour{'s' if len(selected) != 1 else ''}. Click Apply Palette to update the preview.",
        )

    def _on_palette_settings_changed(self, _event: tk.Event | None = None) -> None:
        self._on_settings_changed(_event)

    def _displayed_structured_palette(self) -> StructuredPalette | None:
        return self._current_adjusted_structured_palette()

    def _active_pick_view(self) -> str | None:
        mode = self._canvas_tool_mode_value()
        if mode == CANVAS_TOOL_MODE_PALETTE_PICK:
            return "original"
        if mode in {CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK, CANVAS_TOOL_MODE_TRANSPARENCY_PICK}:
            return "processed"
        return None

    def _sample_visible_preview_label(self, canvas_x: int, canvas_y: int) -> int | None:
        if getattr(self, "original_display_image", None) is None:
            return None
        return self._sample_label_from_preview(canvas_x, canvas_y, view=self._get_effective_view())

    def _set_pick_preview(self, sampled: tuple[int, int, int] | int | None) -> None:
        preview_var = getattr(self, "pick_preview_var", None)
        preview_swatch = getattr(self, "pick_preview_swatch", None)
        if preview_var is None:
            return
        rgb_var = getattr(self, "pick_preview_rgb_var", None)
        position_var = getattr(self, "pick_preview_position_var", None)
        if sampled is None:
            self._pick_preview_sample = None
            preview_var.set("")
            if rgb_var is not None and hasattr(rgb_var, "set"):
                rgb_var.set("")
            if position_var is not None and hasattr(position_var, "set"):
                position_var.set("")
            self._refresh_pick_preview_widgets()
            return
        if isinstance(sampled, tuple):
            image_x, image_y, label = sampled
        else:
            image_x = -1
            image_y = -1
            label = int(sampled)
        self._pick_preview_sample = (image_x, image_y, label)
        hex_value = f"#{label:06X}"
        preview_var.set(hex_value)
        if preview_swatch is not None and hasattr(preview_swatch, "configure"):
            preview_swatch.configure(bg=hex_value)
        if rgb_var is not None and hasattr(rgb_var, "set"):
            red = (label >> 16) & 0xFF
            green = (label >> 8) & 0xFF
            blue = label & 0xFF
            rgb_var.set(f"RGB {red},{green},{blue}")
        if position_var is not None and hasattr(position_var, "set"):
            position_var.set(f"X{image_x} Y{image_y}" if image_x >= 0 and image_y >= 0 else "")
        self._refresh_pick_preview_widgets()

    def _update_pick_preview(self, canvas_x: int, canvas_y: int) -> None:
        pick_view = self._active_pick_view()
        if pick_view is None:
            self._set_pick_preview(None)
            return
        sampled = self._sample_point_from_preview(canvas_x, canvas_y, view=pick_view)
        self._set_pick_preview(sampled)

    def _preview_image_coordinates(self, canvas_x: int, canvas_y: int, *, view: str, clamp: bool = False) -> tuple[int, int] | None:
        if self._display_context is None or self._get_effective_view() != view:
            return None
        if not clamp and not self._point_is_over_image(canvas_x, canvas_y):
            return None
        width = self._display_context.sample_image.width if self._display_context.sample_image is not None else 0
        height = self._display_context.sample_image.height if self._display_context.sample_image is not None else 0
        if width <= 0 or height <= 0:
            return None
        relative_x = (canvas_x - self._display_context.image_left) / max(1, self._display_context.display_width)
        relative_y = (canvas_y - self._display_context.image_top) / max(1, self._display_context.display_height)
        image_x = min(width - 1, max(0, int(relative_x * width)))
        image_y = min(height - 1, max(0, int(relative_y * height)))
        return image_x, image_y

    def _sample_point_from_preview(self, canvas_x: int, canvas_y: int, *, view: str) -> tuple[int, int, int] | None:
        coordinates = self._preview_image_coordinates(canvas_x, canvas_y, view=view)
        if coordinates is None or self._display_context is None or self._display_context.sample_image is None:
            return None
        image_x, image_y = coordinates
        pixel = self._display_context.sample_image.getpixel((image_x, image_y))
        if len(pixel) >= 4 and int(pixel[3]) == 0:
            return None
        red, green, blue = pixel[:3]
        return image_x, image_y, (int(red) << 16) | (int(green) << 8) | int(blue)

    def _sample_label_from_preview(self, canvas_x: int, canvas_y: int, *, view: str) -> int | None:
        sampled = self._sample_point_from_preview(canvas_x, canvas_y, view=view)
        if sampled is None:
            return None
        return sampled[2]

    def _add_transparent_region(self, image_x: int, image_y: int, label: int) -> bool:
        current = self._current_output_result()
        if current is None:
            return False
        updated, changed = apply_transparency_fill(current, image_x, image_y)
        if changed <= 0:
            self.process_status_var.set("That region is already transparent.")
            return False
        self._capture_palette_undo_state()
        if getattr(self, "palette_result", None) is not None:
            self.palette_result = updated
        else:
            self.downsample_result = updated
        self._refresh_output_display_images()
        self.process_status_var.set(
            f"Made {changed} pixel{'s' if changed != 1 else ''} of #{label:06X} transparent. Press Undo to restore it."
        )
        self.redraw_canvas()
        self._refresh_action_states()
        return True

    def _fill_bucket_region(self, image_x: int, image_y: int) -> bool:
        current = self._current_output_result()
        if current is None:
            return False
        if self._primary_brush_uses_transparency():
            red, green, blue = current.grid[image_y][image_x]
            return self._add_transparent_region(image_x, image_y, (red << 16) | (green << 8) | blue)
        label = self._selected_palette_brush_label()
        if label is None:
            return False
        updated, changed = apply_bucket_fill(current, image_x, image_y, label)
        if changed <= 0:
            self.process_status_var.set("That region already uses the primary colour.")
            return False
        self._capture_palette_undo_state()
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self.process_status_var.set(
            f"Filled {changed} pixel{'s' if changed != 1 else ''} with #{label:06X}. Press Undo to restore it."
        )
        self.redraw_canvas()
        self._refresh_action_states()
        return True

    def _apply_brush_stroke(self, image_x: int, image_y: int) -> int:
        current = self._current_output_result()
        if current is None:
            return 0
        mode = getattr(self, "_brush_stroke_tool_mode", None) or self._canvas_tool_mode_value()
        width = self._brush_width()
        shape = self._brush_shape()
        if mode == CANVAS_TOOL_MODE_PENCIL:
            label = self._selected_palette_brush_label()
            if label is None:
                if not self._primary_brush_uses_transparency():
                    return 0
                updated, changed = apply_eraser_operation(current, image_x, image_y, width=width, shape=shape)
            else:
                updated, changed = apply_pencil_operation(current, image_x, image_y, label, width=width, shape=shape)
        elif mode == CANVAS_TOOL_MODE_ERASER:
            updated, changed = apply_eraser_operation(current, image_x, image_y, width=width, shape=shape)
        else:
            return 0
        if changed <= 0:
            return 0
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self.redraw_canvas()
        return changed

    def _start_brush_stroke(self, mode: str, image_x: int, image_y: int) -> None:
        self._brush_stroke_active = True
        self._brush_stroke_tool_mode = mode
        self._brush_stroke_last_point = None
        self._brush_stroke_changed_pixels = 0
        self._capture_palette_undo_state()
        self._record_brush_stroke(image_x, image_y)
        self.canvas.configure(cursor="crosshair")

    def _drag_active_brush_stroke(self, event: tk.Event) -> bool:
        if not getattr(self, "_brush_stroke_active", False):
            return False
        coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
        if coordinates is None:
            return False
        image_x, image_y = coordinates
        self._record_brush_stroke(image_x, image_y)
        return True

    def _finish_active_brush_stroke(self) -> bool:
        if not getattr(self, "_brush_stroke_active", False):
            return False
        changed = int(getattr(self, "_brush_stroke_changed_pixels", 0) or 0)
        if changed > 0:
            mode = getattr(self, "_brush_stroke_tool_mode", None)
            tool_name = self._brush_tool_display_name(mode)
            self.process_status_var.set(
                f"{tool_name} changed {changed} pixel{'s' if changed != 1 else ''}. Press Undo to restore it."
            )
            self._refresh_action_states()
        else:
            clear_undo = getattr(self, "_clear_palette_undo_state", None)
            if callable(clear_undo):
                clear_undo()
        self._reset_brush_stroke_state()
        self.canvas.configure(cursor=self._cursor_for_pointer())
        return True

    def _refresh_current_output_display_image(self) -> None:
        current = self._current_output_result()
        updated_image = self._build_output_display_image(current)
        if getattr(self, "palette_result", None) is not None:
            self.palette_display_image = updated_image
        else:
            self.downsample_display_image = updated_image

    def _apply_brush_segment(self, points: list[tuple[int, int]]) -> int:
        current = self._current_output_result()
        if current is None or not points:
            return 0
        mode = getattr(self, "_brush_stroke_tool_mode", None) or self._canvas_tool_mode_value()
        width = self._brush_width()
        shape = self._brush_shape()
        if mode == CANVAS_TOOL_MODE_PENCIL:
            label = self._selected_palette_brush_label()
            if label is None:
                if not self._primary_brush_uses_transparency():
                    return 0
                updated, changed = apply_eraser_operations(current, points, width=width, shape=shape)
            else:
                updated, changed = apply_pencil_operations(current, points, label=label, width=width, shape=shape)
        elif mode == CANVAS_TOOL_MODE_ERASER:
            updated, changed = apply_eraser_operations(current, points, width=width, shape=shape)
        else:
            return 0
        if changed <= 0:
            return 0
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_current_output_display_image()
        self.redraw_canvas()
        return changed

    @staticmethod
    def _interpolate_brush_points(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        x0, y0 = start
        x1, y1 = end
        delta_x = abs(x1 - x0)
        delta_y = abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = delta_x - delta_y
        points: list[tuple[int, int]] = []
        while True:
            points.append((x0, y0))
            if x0 == x1 and y0 == y1:
                return points
            doubled_error = error * 2
            if doubled_error > -delta_y:
                error -= delta_y
                x0 += step_x
            if doubled_error < delta_x:
                error += delta_x
                y0 += step_y

    def _record_brush_stroke(self, image_x: int, image_y: int) -> None:
        last_point = getattr(self, "_brush_stroke_last_point", None)
        points = [(image_x, image_y)] if last_point is None else self._interpolate_brush_points(last_point, (image_x, image_y))
        changed = self._apply_brush_segment(points)
        if isinstance(changed, int) and changed > 0:
            self._brush_stroke_changed_pixels += changed
        self._brush_stroke_last_point = (image_x, image_y)

    def _shape_preview_active(self) -> bool:
        return (
            getattr(self, "_shape_drag_active", False)
            and getattr(self, "_shape_preview_anchor", None) is not None
            and getattr(self, "_shape_preview_current", None) is not None
            and self._is_shape_tool_mode(getattr(self, "_shape_preview_tool_mode", None))
        )

    def _shape_preview_operation(self) -> tuple[ProcessResult | None, int]:
        current = self._current_output_result()
        outline_label = self._selected_palette_brush_label()
        if current is None or outline_label is None or not self._shape_preview_active():
            return None, 0
        anchor = getattr(self, "_shape_preview_anchor", None)
        endpoint = self._resolved_shape_preview_endpoint(current)
        if anchor is None or endpoint is None:
            return None, 0
        anchor_x, anchor_y = anchor
        endpoint_x, endpoint_y = endpoint
        fill_label = self._shape_fill_label()
        preview_mode = getattr(self, "_shape_preview_tool_mode", None)
        if preview_mode == CANVAS_TOOL_MODE_ELLIPSE:
            return apply_ellipse_operation(
                current,
                anchor_x,
                anchor_y,
                endpoint_x,
                endpoint_y,
                outline_label,
                fill_label=fill_label,
                width=self._brush_width(),
            )
        if preview_mode == CANVAS_TOOL_MODE_RECTANGLE:
            return apply_rectangle_operation(
                current,
                anchor_x,
                anchor_y,
                endpoint_x,
                endpoint_y,
                outline_label,
                fill_label=fill_label,
                width=self._brush_width(),
            )
        if preview_mode == CANVAS_TOOL_MODE_LINE:
            return apply_line_operation(
                current,
                anchor_x,
                anchor_y,
                endpoint_x,
                endpoint_y,
                outline_label,
                width=self._brush_width(),
            )
        return None, 0

    def _shape_preview_image(self) -> Image.Image | None:
        preview_result, _changed = self._shape_preview_operation()
        if preview_result is None:
            return None
        return self._build_output_display_image(preview_result, transparent_colors_override=set())

    def _selected_palette_outline_label(self) -> int | None:
        displayed = getattr(self, "_displayed_palette", [])
        selected = sorted(index for index in getattr(self, "_palette_selection_indices", set()) if 0 <= index < len(displayed))
        if len(selected) != 1:
            return None
        return displayed[selected[0]]

    def _outline_pixel_perfect_enabled(self) -> bool:
        variable = getattr(self, "outline_pixel_perfect_var", None)
        if variable is None:
            return True
        getter = getattr(variable, "get", None)
        if callable(getter):
            return bool(getter())
        return bool(variable)

    def _outline_colour_mode(self) -> str:
        variable = getattr(self, "outline_colour_mode_var", None)
        if variable is None:
            return OUTLINE_COLOUR_MODE_PALETTE
        getter = getattr(variable, "get", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = OUTLINE_COLOUR_MODE_PALETTE
        return self._coerce_outline_colour_mode(value)

    def _outline_adaptive_enabled(self) -> bool:
        return self._outline_colour_mode() == OUTLINE_COLOUR_MODE_ADAPTIVE

    def _outline_adaptive_darken_percent(self) -> int:
        variable = getattr(self, "outline_adaptive_darken_percent_var", None)
        if variable is None:
            return OUTLINE_ADAPTIVE_DARKEN_DEFAULT
        getter = getattr(variable, "get", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = OUTLINE_ADAPTIVE_DARKEN_DEFAULT
        return self._coerce_outline_adaptive_darken_percent(value)

    def _outline_add_generated_colours_enabled(self) -> bool:
        variable = getattr(self, "outline_add_generated_colours_var", None)
        if variable is None:
            return False
        getter = getattr(variable, "get", None)
        if callable(getter):
            try:
                return bool(getter())
            except Exception:
                return False
        return bool(variable)

    def _outline_remove_brightness_threshold_enabled(self) -> bool:
        variable = getattr(self, "outline_remove_brightness_threshold_enabled_var", None)
        if variable is None:
            return False
        getter = getattr(variable, "get", None)
        if callable(getter):
            try:
                return bool(getter())
            except Exception:
                return False
        return bool(variable)

    def _outline_remove_brightness_threshold_percent(self) -> int:
        variable = getattr(self, "outline_remove_brightness_threshold_percent_var", None)
        if variable is None:
            return OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT
        getter = getattr(variable, "get", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = OUTLINE_REMOVE_BRIGHTNESS_THRESHOLD_DEFAULT
        return self._coerce_outline_remove_brightness_threshold_percent(value)

    def _outline_remove_brightness_threshold_direction(self) -> str:
        variable = getattr(self, "outline_remove_brightness_threshold_direction_var", None)
        if variable is None:
            return OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK
        getter = getattr(variable, "get", None)
        try:
            value = getter() if callable(getter) else variable
        except Exception:
            value = OUTLINE_REMOVE_BRIGHTNESS_DIRECTION_DARK
        return self._coerce_outline_remove_brightness_direction(value)

    def _outline_remove_brightness_threshold_description(self) -> str:
        direction = self._outline_remove_brightness_threshold_direction()
        threshold = self._outline_remove_brightness_threshold_percent()
        return f"{direction} brightness threshold at {threshold}%"

    def _refresh_brush_control_states(self) -> None:
        busy = getattr(self, "image_state", "") == "processing"
        has_output = self._current_output_result() is not None if hasattr(self, "_current_output_result") else False
        can_erase = has_output and not busy
        has_primary_brush = False
        if hasattr(self, "_selected_palette_brush_label"):
            has_primary_brush = self._selected_palette_brush_label() is not None
        transparent_primary = self._primary_brush_uses_transparency() if hasattr(self, "_primary_brush_uses_transparency") else False
        can_brush = can_erase and (has_primary_brush or transparent_primary)
        can_shape_draw = can_erase and has_primary_brush
        self._set_tool_button_enabled("bucket_button", can_brush)
        self._set_tool_button_enabled("pencil_button", can_brush)
        self._set_tool_button_enabled("eraser_button", can_erase)
        self._set_tool_button_enabled("circle_button", can_shape_draw)
        self._set_tool_button_enabled("square_button", can_shape_draw)
        self._set_tool_button_enabled("line_button", can_shape_draw)
        self._set_tool_button_enabled("gradient_button", can_erase)
        spinbox = getattr(self, "brush_width_spinbox", None)
        if spinbox is not None and hasattr(spinbox, "configure"):
            spinbox.configure(state="normal" if can_erase else "disabled")
        dropdown = getattr(self, "brush_shape_dropdown_button", None)
        if dropdown is not None and hasattr(dropdown, "configure"):
            dropdown.configure(state=tk.NORMAL if can_erase else tk.DISABLED)

    def _refresh_outline_control_states(self) -> None:
        adaptive = self._outline_adaptive_enabled()
        remove_threshold = self._outline_remove_brightness_threshold_enabled()
        busy = getattr(self, "image_state", "") == "processing"
        has_output = self._current_output_result() is not None if hasattr(self, "_current_output_result") else False
        mode_state = tk.NORMAL if has_output and not busy else tk.DISABLED
        adaptive_state = "normal" if adaptive and has_output and not busy else "disabled"
        remove_threshold_state = "normal" if remove_threshold and has_output and not busy else "disabled"
        pixel_perfect_toggle = getattr(self, "outline_pixel_perfect_toggle", None)
        if pixel_perfect_toggle is not None and hasattr(pixel_perfect_toggle, "configure"):
            pixel_perfect_toggle.configure(state=mode_state)
        for widget_name in (
            "outline_colour_mode_dropdown_button",
            "outline_palette_mode_button",
            "outline_adaptive_mode_button",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None and hasattr(widget, "configure"):
                widget.configure(state=mode_state)
        toggle = getattr(self, "outline_add_generated_colours_toggle", None)
        if toggle is not None and hasattr(toggle, "configure"):
            toggle.configure(state=tk.NORMAL if adaptive and has_output and not busy else tk.DISABLED)
        label = getattr(self, "outline_adaptive_darken_label", None)
        if label is not None and hasattr(label, "configure"):
            label.configure(state=tk.NORMAL if adaptive and has_output and not busy else tk.DISABLED)
        spinbox = getattr(self, "outline_adaptive_darken_spinbox", None)
        if spinbox is not None and hasattr(spinbox, "configure"):
            spinbox.configure(state=adaptive_state)
        remove_toggle = getattr(self, "outline_remove_brightness_threshold_toggle", None)
        if remove_toggle is not None and hasattr(remove_toggle, "configure"):
            remove_toggle.configure(state=mode_state)
        remove_spinbox = getattr(self, "outline_remove_brightness_threshold_spinbox", None)
        if remove_spinbox is not None and hasattr(remove_spinbox, "configure"):
            remove_spinbox.configure(state=remove_threshold_state)
        for widget_name in (
            "outline_remove_brightness_direction_dropdown_button",
            "outline_remove_brightness_direction_dark_button",
            "outline_remove_brightness_direction_bright_button",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None and hasattr(widget, "configure"):
                widget.configure(state=remove_threshold_state)
        apply_button = getattr(self, "options_apply_button", None)
        if apply_button is not None and hasattr(apply_button, "configure"):
            apply_enabled = False
            mode = self._options_tool_mode()
            if mode == CANVAS_TOOL_MODE_ADD_OUTLINE:
                apply_enabled = self._can_apply_add_outline_tool()
            elif mode == CANVAS_TOOL_MODE_REMOVE_OUTLINE:
                apply_enabled = self._can_apply_remove_outline_tool()
            elif mode == CANVAS_TOOL_MODE_ROTATE:
                apply_enabled = self._current_output_result() is not None and self.image_state != "processing"
            apply_button.configure(state=tk.NORMAL if apply_enabled else tk.DISABLED)

    def _refresh_image_filter_control_states(self) -> None:
        busy = getattr(self, "image_state", "") == "processing"
        has_output = self._current_output_result() is not None if hasattr(self, "_current_output_result") else False
        state = "normal" if has_output and not busy else "disabled"
        spinbox = getattr(self, "image_filter_strength_spinbox", None)
        if spinbox is not None and hasattr(spinbox, "configure"):
            spinbox.configure(state=state)
        apply_button = getattr(self, "options_apply_button", None)
        if apply_button is not None and hasattr(apply_button, "configure"):
            mode = self._options_tool_mode()
            if mode in {CANVAS_TOOL_MODE_BLUR, CANVAS_TOOL_MODE_SHARPEN}:
                apply_button.configure(state=tk.NORMAL if self._can_apply_image_filter_tool(mode) else tk.DISABLED)

    def _on_brush_width_changed(self, _event: tk.Event | None = None) -> None:
        width = self._brush_width()
        variable = getattr(self, "brush_width_var", None)
        getter = getattr(variable, "get", None)
        setter = getattr(variable, "set", None)
        if variable is not None and callable(getter) and callable(setter) and getter() != width:
            setter(width)
        self._schedule_state_persist()

    def _select_brush_shape(self, value: str) -> None:
        variable = getattr(self, "brush_shape_var", None)
        setter = getattr(variable, "set", None)
        if variable is not None and callable(setter):
            setter(value)
        self._on_brush_shape_changed()

    def _on_brush_shape_changed(self) -> None:
        shape = self._brush_shape()
        variable = getattr(self, "brush_shape_var", None)
        getter = getattr(variable, "get", None)
        setter = getattr(variable, "set", None)
        display_value = shape.title()
        if variable is not None and callable(getter) and callable(setter) and getter() != display_value:
            setter(display_value)
        self._schedule_state_persist()

    def _set_current_output_result(self, result: ProcessResult) -> None:
        if getattr(self, "palette_result", None) is not None:
            self.palette_result = result
        else:
            self.downsample_result = result

    def _prepared_input_from_result(self, result: ProcessResult) -> PipelinePreparedResult:
        labels = rgb_to_labels(result.grid)
        return PipelinePreparedResult(
            reduced_labels=labels,
            pixel_width=max(1, int(result.stats.pixel_width)),
            grid_method=result.prepared_input.grid_method,
            input_size=(result.width, result.height),
            initial_color_count=len(extract_unique_colors(labels)),
        )

    def _apply_canvas_size(self, spec: CanvasResizeSpec) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            return
        anchor = self._coerce_canvas_resize_anchor(spec.anchor)
        if spec.width == current.width and spec.height == current.height:
            self.process_status_var.set("Canvas size unchanged.")
            return

        self._capture_palette_undo_state()
        self._clear_palette_redo_state()

        base_source = self.downsample_result if self.downsample_result is not None else current
        resized_base = resize_canvas_result(base_source, spec)
        prepared_input = self._prepared_input_from_result(resized_base)
        self.downsample_result = replace(resized_base, prepared_input=prepared_input)

        if self.palette_result is not None:
            resized_palette = resize_canvas_result(self.palette_result, spec)
            self.palette_result = replace(resized_palette, prepared_input=prepared_input)

        self.prepared_input_cache = prepared_input
        self.prepared_input_cache_key = None
        self.transparent_colors = set()
        self.comparison_original_image = None
        self._comparison_original_key = None
        self.quick_compare_active = False
        self.image_state = "processed_current"
        self._refresh_output_display_images()
        self._set_view("processed")
        anchor_label = CANVAS_RESIZE_ANCHOR_LABELS.get(anchor, "center")
        self.process_status_var.set(
            f"Resized canvas to {spec.width}x{spec.height} from the {anchor_label} anchor. Press Undo to restore it."
        )
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _add_outline_from_selection(self) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            return
        adaptive = self._outline_adaptive_enabled()
        outline_label: int | None = 0
        if not adaptive:
            outline_label = self._selected_palette_outline_label()
            if outline_label is None:
                self.process_status_var.set("Select exactly one palette colour to add an outline.")
                return
        pixel_perfect = self._outline_pixel_perfect_enabled()
        darken_percent = self._outline_adaptive_darken_percent()
        width = self._brush_width()
        updated, changed, generated_labels = add_exterior_outline(
            current,
            outline_label if outline_label is not None else 0,
            transparent_labels=getattr(self, "transparent_colors", set()),
            pixel_perfect=pixel_perfect,
            adaptive=adaptive,
            adaptive_darken_percent=darken_percent,
            width=width,
            workspace=getattr(self, "workspace", None),
        )
        if changed <= 0:
            if adaptive:
                if pixel_perfect:
                    self.process_status_var.set("No adaptive pixel-perfect exterior outline pixels were available to add.")
                else:
                    self.process_status_var.set("No adaptive exterior outline pixels were available to add.")
            elif pixel_perfect:
                self.process_status_var.set("No pixel-perfect exterior outline pixels were available to add.")
            else:
                self.process_status_var.set("No exterior outline pixels were available to add.")
            return
        self._capture_palette_undo_state()
        appended_count = 0
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        if adaptive and self._outline_add_generated_colours_enabled():
            editable_palette = self._editable_palette_labels()
            if editable_palette:
                existing = set(editable_palette)
                appended_labels = [label for label in generated_labels if label not in existing]
                if appended_labels:
                    previous_selection = set(getattr(self, "_palette_selection_indices", set()))
                    previous_anchor = getattr(self, "_palette_selection_anchor_index", None)
                    self._set_active_palette(editable_palette + appended_labels, "Edited Palette", None)
                    self._palette_selection_indices = {
                        index for index in previous_selection if 0 <= index < len(getattr(self, "active_palette", []) or [])
                    }
                    anchor = previous_anchor if isinstance(previous_anchor, int) else None
                    self._palette_selection_anchor_index = (
                        anchor if anchor is not None and 0 <= anchor < len(getattr(self, "active_palette", []) or []) else None
                    )
                    appended_count = len(appended_labels)
        self._refresh_output_display_images()
        self._set_view("processed")
        if adaptive:
            palette_clause = (
                f" Added {appended_count} generated palette colour{'s' if appended_count != 1 else ''} to the current palette."
                if appended_count
                else ""
            )
            if pixel_perfect:
                self.process_status_var.set(
                    f"Added adaptive pixel-perfect outline to {changed} pixel{'s' if changed != 1 else ''} at {darken_percent}% darkening."
                    f"{palette_clause} Press Undo to restore it."
                )
            else:
                self.process_status_var.set(
                    f"Added adaptive outline to {changed} pixel{'s' if changed != 1 else ''} at {darken_percent}% darkening."
                    f"{palette_clause} Press Undo to restore it."
                )
        elif pixel_perfect:
            self.process_status_var.set(
                f"Added pixel-perfect outline to {changed} pixel{'s' if changed != 1 else ''} with #{outline_label:06X}. Press Undo to restore it."
            )
        else:
            self.process_status_var.set(
                f"Added outline to {changed} pixel{'s' if changed != 1 else ''} with #{outline_label:06X}. Press Undo to restore it."
            )
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._refresh_action_states()

    def _remove_outline(self) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            return
        pixel_perfect = self._outline_pixel_perfect_enabled()
        brightness_threshold_enabled = self._outline_remove_brightness_threshold_enabled()
        brightness_threshold_percent = self._outline_remove_brightness_threshold_percent()
        brightness_threshold_direction = self._outline_remove_brightness_threshold_direction()
        width = self._brush_width()
        updated, changed = remove_exterior_outline(
            current,
            transparent_labels=getattr(self, "transparent_colors", set()),
            pixel_perfect=pixel_perfect,
            brightness_threshold_enabled=brightness_threshold_enabled,
            brightness_threshold_percent=brightness_threshold_percent,
            brightness_threshold_direction=brightness_threshold_direction,
            width=width,
            workspace=getattr(self, "workspace", None),
        )
        if changed <= 0:
            if brightness_threshold_enabled:
                if pixel_perfect:
                    self.process_status_var.set(
                        f"No pixel-perfect edge pixels met the {self._outline_remove_brightness_threshold_description()}."
                    )
                else:
                    self.process_status_var.set(
                        f"No exterior outline pixels met the {self._outline_remove_brightness_threshold_description()}."
                    )
            elif pixel_perfect:
                self.process_status_var.set("No pixel-perfect edge pixels were found to remove.")
            else:
                self.process_status_var.set("No exterior outline pixels were found to remove.")
            return
        self._capture_palette_undo_state()
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self._set_view("processed")
        if brightness_threshold_enabled:
            if pixel_perfect:
                self.process_status_var.set(
                    f"Removed {changed} pixel-perfect edge pixel{'s' if changed != 1 else ''} using the "
                    f"{self._outline_remove_brightness_threshold_description()}. Press Undo to restore it."
                )
            else:
                self.process_status_var.set(
                    f"Removed {changed} outline pixel{'s' if changed != 1 else ''} using the "
                    f"{self._outline_remove_brightness_threshold_description()}. Press Undo to restore it."
                )
        elif pixel_perfect:
            self.process_status_var.set(
                f"Removed {changed} pixel-perfect edge pixel{'s' if changed != 1 else ''}. Press Undo to restore it."
            )
        else:
            self.process_status_var.set(f"Removed {changed} outline pixel{'s' if changed != 1 else ''}. Press Undo to restore it.")
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._refresh_action_states()

    def _apply_blur_tool(self) -> None:
        self._apply_image_filter_tool(CANVAS_TOOL_MODE_BLUR, action_name="Blur")

    def _apply_sharpen_tool(self) -> None:
        self._apply_image_filter_tool(CANVAS_TOOL_MODE_SHARPEN, action_name="Sharpen")

    def _apply_image_filter_tool(self, mode: str, *, action_name: str) -> None:
        current = self._current_output_result()
        if current is None or self.image_state == "processing":
            return
        strength = self._image_filter_strength(mode)
        if mode == CANVAS_TOOL_MODE_SHARPEN:
            updated, changed = apply_sharpen(current, strength)
        else:
            updated, changed = apply_blur(current, strength)
        if changed <= 0:
            self.process_status_var.set(f"{action_name} at strength {strength} did not change the current image.")
            return
        self._capture_palette_undo_state()
        self._clear_palette_redo_state()
        self.transparent_colors = set()
        self._set_current_output_result(updated)
        self._refresh_output_display_images()
        self._set_view("processed")
        self.process_status_var.set(f"Applied {action_name} at strength {strength}. Press Undo to restore it.")
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()

    def extract_unique_palette(self) -> None:
        source_grid = self._palette_source_grid()
        if source_grid is None:
            return
        palette = extract_unique_colors(rgb_to_labels(source_grid))
        self._apply_active_palette(
            palette,
            "Extracted",
            None,
            message=f"Extracted {len(palette)} colours. Click Apply Palette to update the preview.",
        )

    def generate_palette_from_image(self) -> None:
        try:
            settings = self._read_settings_from_controls(strict=False)
        except Exception:
            settings = self.session.current
        self.session.current = settings
        self._generate_override_palette_from_settings(settings)

    def _generate_override_palette_from_settings(self, settings: PreviewSettings) -> None:
        if self.image_state == "processing":
            return
        source_labels = self._override_palette_source_labels()
        method = settings.quantizer
        label = QUANTIZER_VALUE_TO_DISPLAY.get(method, method)
        structured_quantizer = is_structured_quantizer(method)
        if source_labels is None:
            if structured_quantizer:
                self.process_status_var.set(f"Downsample the image before generating a {label} palette.")
            else:
                self.process_status_var.set("Downsample the image before generating an override palette.")
            return
        if structured_quantizer:
            try:
                palette_source = generate_palette_source(
                    source_labels,
                    0,
                    method=method,
                    workspace=getattr(self, "workspace", None),
                    source_label=f"Generated: {label}",
                )
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(f"Failed to generate {label}", str(exc))
                return
            if not isinstance(palette_source, StructuredPalette) or palette_source.palette_size() <= 0:
                self.process_status_var.set(f"No colours were generated for the {label} palette.")
                return
            self._apply_structured_palette_preview(
                palette_source,
                message=(
                    f"Generated a {palette_source.palette_size()}-colour {label} palette across "
                    f"{len(palette_source.ramps)} ramps. Click Apply Palette to use it."
                ),
            )
            return
        palette_size = self._override_palette_target_size(source_labels, settings)
        if palette_size <= 0:
            self.process_status_var.set("No colours are available to build an override palette.")
            return
        try:
            palette = generate_override_palette(source_labels, palette_size, method=method)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed to generate override palette", str(exc))
            return
        if not palette:
            self.process_status_var.set("No colours were generated for the override palette.")
            return
        self._apply_active_palette(
            palette,
            f"Generated Override: {label}",
            None,
            message=f"Generated a {len(palette)}-colour override palette with {label}. Click Apply Palette to use it.",
        )

    def load_palette_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[
                ("GIMP Palette", "*.gpl"),
                ("Palette files", "*.gpl *.json"),
                ("Palette JSON", "*.json"),
            ]
        )
        if not path:
            return
        try:
            palette = load_palette(Path(path))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed to load palette", str(exc))
            return
        resolved_path = self._resolve_palette_path(path) or str(Path(path))
        self._apply_active_palette(
            palette,
            f"Loaded: {Path(path).name}",
            resolved_path,
            message=f"Loaded palette from {Path(path).name}. Click Apply Palette to update the preview.",
        )

    def save_palette_file(self) -> None:
        palette, _source = self._get_display_palette()
        if not palette:
            return
        path = filedialog.asksaveasfilename(defaultextension=".gpl", filetypes=[("GIMP Palette", "*.gpl")])
        if not path:
            return
        try:
            save_palette(Path(path), palette)
            self.process_status_var.set(f"Saved palette to {Path(path).name}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed to save palette", str(exc))

    def downsample_current_image(self) -> None:
        if self.original_grid is None or self.source_path is None:
            return
        try:
            settings = self._read_settings_from_controls(strict=True)
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        self.session.current = settings
        snapshot_palette, snapshot_source = self._get_display_palette()
        snapshot = make_process_snapshot(settings, snapshot_palette, self.active_palette_path, snapshot_source)
        changes = diff_snapshots(self.last_successful_process_snapshot, snapshot)
        source_size = (len(self.original_grid[0]), len(self.original_grid)) if self.original_grid else (0, 0)

        self._set_pick_mode(None)
        self.image_state = "processing"
        self.quick_compare_active = False
        self.process_status_var.set("Preparing input...")
        self._refresh_action_states()
        config = self._build_pipeline_config(settings)

        def progress_callback(_percent: int, message: str) -> None:
            self.root.after(0, lambda: self.process_status_var.set(message))

        def worker() -> None:
            try:
                result = downsample_image(
                    self.original_grid or [],
                    config,
                    progress_callback=progress_callback,
                )
                self.root.after(0, lambda: self._handle_downsample_success(result, snapshot, changes, source_size, self._build_prepare_cache_key(settings)))
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self.root.after(0, lambda message=message: self._handle_stage_failure(message, changes, source_size))

        threading.Thread(target=worker, daemon=True).start()

    def reduce_palette_current_image(self) -> None:
        if self.prepared_input_cache is None or self.source_path is None:
            self.process_status_var.set("Downsample the image before applying a palette.")
            return
        adjusted_palette = self._current_adjusted_structured_palette()
        if adjusted_palette is None or adjusted_palette.palette_size() == 0:
            self.process_status_var.set("Create, load, or adjust a palette before applying it.")
            return
        try:
            settings = self._read_settings_from_controls(strict=True)
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        self.session.current = settings
        snapshot_palette, snapshot_source = self._get_display_palette()
        snapshot = make_process_snapshot(settings, snapshot_palette, self.active_palette_path, snapshot_source)
        changes = diff_snapshots(self.last_successful_process_snapshot, snapshot)
        source_size = (len(self.original_grid[0]), len(self.original_grid)) if self.original_grid else (0, 0)
        self._capture_palette_undo_state()

        self._set_pick_mode(None)
        self.image_state = "processing"
        self.quick_compare_active = False
        self.process_status_var.set("Applying palette...")
        self._refresh_action_states()
        config = self._build_pipeline_config(settings)
        apply_override_palette: list[int] | None = None
        apply_override_source: str | None = None
        apply_override_path: str | None = None
        apply_structured_palette: StructuredPalette | None = None
        if self._palette_is_override_mode() or adjusted_palette.source_mode == "override":
            apply_override_palette = adjusted_palette.labels()
            apply_override_source = adjusted_palette.source_label or self.active_palette_source or "Override"
            apply_override_path = self.active_palette_path if self.active_palette is not None else None
        else:
            apply_structured_palette = adjusted_palette

        def progress_callback(_percent: int, message: str) -> None:
            self.root.after(0, lambda: self.process_status_var.set(message))

        def worker() -> None:
            try:
                result = reduce_palette_image(
                    self.prepared_input_cache,
                    config,
                    palette_override=apply_override_palette,
                    structured_palette=apply_structured_palette,
                    progress_callback=progress_callback,
                )
                self.root.after(
                    0,
                    lambda: self._handle_palette_success(
                        result,
                        snapshot,
                        changes,
                        source_size,
                        applied_override_palette=apply_override_palette,
                        applied_override_source=apply_override_source,
                        applied_override_path=apply_override_path,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self.root.after(0, lambda message=message: self._handle_stage_failure(message, changes, source_size))

        threading.Thread(target=worker, daemon=True).start()

    def save_processed_image(self) -> None:
        if self.image_state != "processed_current":
            return
        if not self.last_output_path:
            self.save_processed_image_as()
            return
        self._save_processed_png(Path(self.last_output_path))

    def save_processed_image_as(self) -> None:
        if self.image_state != "processed_current":
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG images", "*.png")])
        if not path:
            return
        self._save_processed_png(Path(path))

    def undo(self) -> None:
        if self._undo_palette_application():
            return
        history = getattr(getattr(self, "session", None), "history", None)
        can_undo = getattr(history, "can_undo", None)
        if not callable(can_undo) or not can_undo():
            self.process_status_var.set("Nothing to undo.")
            return
        previous = self.session.current
        restored = self.session.undo()
        self._sync_controls_from_settings(restored)
        self._handle_settings_transition(previous, restored, "Settings restored from undo.")

    def redo(self) -> None:
        if self._redo_palette_application():
            return
        history = getattr(getattr(self, "session", None), "history", None)
        can_redo = getattr(history, "can_redo", None)
        if not callable(can_redo) or not can_redo():
            self.process_status_var.set("Nothing to redo.")
            return
        previous = self.session.current
        restored = self.session.redo()
        self._sync_controls_from_settings(restored)
        self._handle_settings_transition(previous, restored, "Settings restored from redo.")

    def _capture_palette_state(self) -> PaletteUndoState:
        return PaletteUndoState(
            palette_result=getattr(self, "palette_result", None),
            downsample_result=getattr(self, "downsample_result", None),
            downsample_display_image=self.downsample_display_image.copy() if getattr(self, "downsample_display_image", None) is not None else None,
            palette_display_image=self.palette_display_image.copy() if getattr(self, "palette_display_image", None) is not None else None,
            image_state=self.image_state,
            last_successful_process_snapshot=dict(self.last_successful_process_snapshot) if isinstance(self.last_successful_process_snapshot, dict) else self.last_successful_process_snapshot,
            active_palette=list(self.active_palette) if getattr(self, "active_palette", None) is not None else None,
            active_palette_source=getattr(self, "active_palette_source", ""),
            active_palette_path=getattr(self, "active_palette_path", None),
            advanced_palette_preview=clone_structured_palette(getattr(self, "advanced_palette_preview", None)),
            transparent_colors=tuple(sorted(getattr(self, "transparent_colors", set()))),
            settings=self.session.current,
            palette_sort_reset_labels=tuple(getattr(self, "_palette_sort_reset_labels", None) or ()),
            palette_sort_reset_source=getattr(self, "_palette_sort_reset_source", None),
            palette_sort_reset_path=getattr(self, "_palette_sort_reset_path", None),
        )

    def _capture_palette_undo_state(self) -> None:
        self._palette_undo_state = self._capture_palette_state()
        self._clear_palette_redo_state()

    def _clear_palette_undo_state(self) -> None:
        self._palette_undo_state = None

    def _clear_palette_redo_state(self) -> None:
        self._palette_redo_state = None

    def _restore_palette_state(self, state: PaletteUndoState) -> None:
        self.downsample_result = state.downsample_result
        self.palette_result = state.palette_result
        self.downsample_display_image = state.downsample_display_image.copy() if state.downsample_display_image is not None else None
        self.palette_display_image = state.palette_display_image.copy() if state.palette_display_image is not None else None
        self.prepared_input_cache = self.downsample_result.prepared_input if self.downsample_result is not None else None
        self.prepared_input_cache_key = None
        self.image_state = state.image_state
        self.last_successful_process_snapshot = (
            dict(state.last_successful_process_snapshot) if isinstance(state.last_successful_process_snapshot, dict) else state.last_successful_process_snapshot
        )
        self._set_active_palette(state.active_palette, state.active_palette_source, state.active_palette_path)
        self.advanced_palette_preview = clone_structured_palette(state.advanced_palette_preview)
        self.transparent_colors = set(state.transparent_colors)
        self._palette_sort_reset_labels = list(state.palette_sort_reset_labels) if state.palette_sort_reset_labels else None
        self._palette_sort_reset_source = state.palette_sort_reset_source
        self._palette_sort_reset_path = state.palette_sort_reset_path
        self.session.current = state.settings
        self._sync_controls_from_settings(state.settings)
        self.comparison_original_image = None
        self._comparison_original_key = None
        self._clear_canvas_selection_state()
        if hasattr(self, "_menu_items") and "palette_sort" in self._menu_items:
            self._populate_palette_sort_menu()
        self.quick_compare_active = False

    def _undo_palette_application(self) -> bool:
        if self._palette_undo_state is None:
            return False
        self._palette_redo_state = self._capture_palette_state()
        state = self._palette_undo_state
        self._restore_palette_state(state)
        self._clear_palette_undo_state()
        self.process_status_var.set("Reverted the last image change.")
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()
        return True

    def _redo_palette_application(self) -> bool:
        if self._palette_redo_state is None:
            return False
        self._palette_undo_state = self._capture_palette_state()
        state = self._palette_redo_state
        self._restore_palette_state(state)
        self._clear_palette_redo_state()
        self.process_status_var.set("Reapplied the last undone image change.")
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()
        return True

    def _build_output_display_image(
        self,
        result: ProcessResult | None,
        *,
        transparent_colors_override: set[int] | None = None,
    ) -> Image.Image | None:
        if result is None:
            return None
        image = Image.new("RGBA", (result.width, result.height))
        if result.width <= 0 or result.height <= 0:
            return image
        alpha_mask = result.alpha_mask
        transparent = getattr(self, "transparent_colors", set()) if transparent_colors_override is None else transparent_colors_override
        display_adjustments = self._output_display_label_adjustments(result)
        data: list[tuple[int, int, int, int]] = []
        for y, row in enumerate(result.grid):
            for x, (red, green, blue) in enumerate(row):
                label = (red << 16) | (green << 8) | blue
                adjusted_label = display_adjustments.get(label, label)
                red = (adjusted_label >> 16) & 0xFF
                green = (adjusted_label >> 8) & 0xFF
                blue = adjusted_label & 0xFF
                is_visible = True if alpha_mask is None else bool(alpha_mask[y][x])
                alpha = 0 if (not is_visible or label in transparent) else 255
                data.append((red, green, blue, alpha))
        image.putdata(data)
        return image

    def _output_display_label_adjustments(self, result: ProcessResult | None) -> dict[int, int]:
        if result is None:
            return {}
        adjustments = self._palette_adjustments()
        if adjustments.is_neutral():
            return {}
        label_order: list[int] = []
        seen_labels: set[int] = set()
        for row in result.grid:
            for red, green, blue in row:
                label = (red << 16) | (green << 8) | blue
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                label_order.append(label)
        if not label_order:
            return {}
        selected_indices = self._output_display_adjustment_indices(label_order)
        adjusted_labels = adjust_palette_labels(
            label_order,
            adjustments,
            workspace=getattr(self, "workspace", None),
            selected_indices=selected_indices,
        )
        return {
            original: adjusted
            for original, adjusted in zip(label_order, adjusted_labels, strict=False)
            if adjusted != original
        }

    def _output_display_adjustment_indices(self, labels: list[int]) -> set[int] | None:
        selected_palette_indices = self._palette_adjustment_selection_indices()
        if not selected_palette_indices:
            return None
        palette_labels, _source = self._current_palette_source_labels()
        if not palette_labels:
            return None
        selected_labels = {
            palette_labels[index]
            for index in selected_palette_indices
            if 0 <= index < len(palette_labels)
        }
        if not selected_labels:
            return None
        matching_indices = {
            index
            for index, label in enumerate(labels)
            if label in selected_labels
        }
        return matching_indices or None

    def _refresh_output_display_images(self) -> None:
        self.downsample_display_image = self._build_output_display_image(getattr(self, "downsample_result", None))
        self.palette_display_image = self._build_output_display_image(getattr(self, "palette_result", None))

    def _handle_downsample_success(
        self,
        result: ProcessResult,
        snapshot: dict[str, object],
        changes: list[str],
        source_size: tuple[int, int],
        cache_key: tuple[object, ...],
    ) -> None:
        self.downsample_result = result
        self.palette_result = None
        self.transparent_colors = set()
        self._palette_selection_indices = set()
        self._clear_canvas_selection_state()
        self._refresh_output_display_images()
        self.comparison_original_image = None
        self._comparison_original_key = None
        self.prepared_input_cache = result.prepared_input
        self.prepared_input_cache_key = cache_key
        self.image_state = "processed_current"
        self.last_successful_process_snapshot = snapshot
        self._clear_palette_undo_state()
        self._clear_palette_redo_state()
        self._set_view("processed")
        self.root.update_idletasks()
        self.zoom_fit()
        status_message = f"Downsampled to {result.width}x{result.height} with {display_resize_method(result.stats.resize_method)} in {result.stats.elapsed_seconds:.2f}s."
        self.process_status_var.set(status_message)
        append_process_log(
            source_path_value=str(self.source_path),
            source_size=source_size,
            processed_size=result.stats.output_size,
            color_count=result.stats.color_count,
            changes=changes,
            success=True,
            message="Downsample complete",
        )
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _handle_palette_success(
        self,
        result: ProcessResult,
        snapshot: dict[str, object],
        changes: list[str],
        source_size: tuple[int, int],
        *,
        applied_override_palette: list[int] | None = None,
        applied_override_source: str | None = None,
        applied_override_path: str | None = None,
    ) -> None:
        self.palette_result = result
        self._palette_selection_indices = set()
        if applied_override_palette is not None:
            self._set_active_palette(applied_override_palette, applied_override_source or "Override", applied_override_path)
            self.advanced_palette_preview = None
        elif result.structured_palette is not None and result.structured_palette.source_mode != "override":
            self.advanced_palette_preview = result.structured_palette
        self.transparent_colors = set()
        self._clear_canvas_selection_state()
        self._refresh_output_display_images()
        self._reset_palette_adjustments_to_neutral()
        self.image_state = "processed_current"
        self.last_successful_process_snapshot = snapshot
        self._clear_palette_redo_state()
        self._set_view("processed")
        self.root.update_idletasks()
        self.zoom_fit()
        self.process_status_var.set(
            f"Applied {result.stats.palette_strategy} palette with {result.stats.color_count} colours across {max(result.stats.ramp_count, 1)} ramps in {result.stats.elapsed_seconds:.2f}s."
        )
        append_process_log(
            source_path_value=str(self.source_path),
            source_size=source_size,
            processed_size=result.stats.output_size,
            color_count=result.stats.color_count,
            changes=changes,
            success=True,
            message="Palette application complete",
        )
        self._update_palette_strip()
        self._update_image_info()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _handle_stage_failure(self, message: str, changes: list[str], source_size: tuple[int, int]) -> None:
        self._clear_palette_undo_state()
        self._clear_palette_redo_state()
        self._clear_canvas_selection_state()
        self.image_state = "processed_stale" if self._current_output_result() is not None else "loaded_original"
        self.process_status_var.set(message)
        append_process_log(
            source_path_value=str(self.source_path) if self.source_path is not None else "unknown",
            source_size=source_size,
            processed_size=None,
            color_count=None,
            changes=changes,
            success=False,
            message=message,
        )
        messagebox.showerror("Processing failed", message)
        self._refresh_action_states()

    def _save_processed_png(self, path: Path) -> None:
        image = self._current_output_image()
        if image is None:
            return
        image.save(path, format="PNG")
        self.last_output_path = str(path)
        self.process_status_var.set(f"Saved image to {path.name}")
        self._schedule_state_persist()
        self._refresh_action_states()

    def redraw_canvas(self) -> None:
        self.canvas.delete("all")
        sample_image = self._get_sample_image()
        self._display_context = None
        if sample_image is None:
            text = "Open an image to begin."
            self.canvas.create_text(
                max(self.canvas.winfo_width() // 2, 200),
                max(self.canvas.winfo_height() // 2, 150),
                text=text,
                fill=APP_TEXT,
                font=self.ui_font,
            )
            self._update_image_info()
            return

        base_width = max(1, sample_image.width)
        base_height = max(1, sample_image.height)
        display_width = max(1, round(base_width * (self.zoom / 100)))
        display_height = max(1, round(base_height * (self.zoom / 100)))
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        self._clamp_pan(display_width, display_height, canvas_width, canvas_height)
        image_left = (canvas_width - display_width) // 2 if display_width <= canvas_width else -self.pan_x
        image_top = (canvas_height - display_height) // 2 if display_height <= canvas_height else -self.pan_y
        self._display_context = CanvasDisplay(image_left, image_top, display_width, display_height, sample_image)

        rendered = self._render_display_image(sample_image, display_width, display_height)
        self._image_ref = ImageTk.PhotoImage(rendered, master=self.root)
        self.canvas.create_image(image_left, image_top, image=self._image_ref, anchor=tk.NW)
        self._draw_overlay_grid(image_left, image_top, base_width, base_height, display_width, display_height)
        self._draw_canvas_selection_overlays()
        self._update_image_info()

    def _render_display_image(self, sample_image: Image.Image, display_width: int, display_height: int) -> Image.Image:
        background = self._build_background(sample_image.size)
        composited = Image.alpha_composite(background, sample_image.convert("RGBA"))
        return composited.resize((display_width, display_height), Image.Resampling.NEAREST)

    def _build_background(self, size: tuple[int, int]) -> Image.Image:
        width, height = size
        if width <= 0 or height <= 0:
            return Image.new("RGBA", (1, 1), (34, 35, 35, 255))
        if not self.checkerboard_var.get():
            return Image.new("RGBA", size, (34, 35, 35, 255))
        background = Image.new("RGBA", size, (34, 35, 35, 255))
        draw = ImageDraw.Draw(background)
        for y in range(0, height, 8):
            for x in range(0, width, 8):
                if ((x // 8) + (y // 8)) % 2 == 0:
                    draw.rectangle((x, y, x + 7, y + 7), fill=(48, 52, 52, 255))
        return background

    def _overlay_grid_enabled(self) -> bool:
        variable = getattr(self, "overlay_grid_var", None)
        getter = getattr(variable, "get", None)
        try:
            return bool(getter()) if callable(getter) else bool(variable)
        except Exception:
            return False

    def _should_draw_overlay_grid(self) -> bool:
        return (
            self._overlay_grid_enabled()
            and self.zoom >= 400
            and self._get_effective_view() == "processed"
            and self._current_output_result() is not None
        )

    def _draw_overlay_grid(
        self,
        image_left: int,
        image_top: int,
        image_width: int,
        image_height: int,
        display_width: int,
        display_height: int,
    ) -> None:
        if not self._should_draw_overlay_grid():
            return
        for x in range(1, max(1, image_width)):
            x_position = image_left + round((x / max(image_width, 1)) * display_width)
            self.canvas.create_line(
                x_position,
                image_top,
                x_position,
                image_top + display_height,
                fill=OVERLAY_GRID_COLOUR,
            )
        for y in range(1, max(1, image_height)):
            y_position = image_top + round((y / max(image_height, 1)) * display_height)
            self.canvas.create_line(
                image_left,
                y_position,
                image_left + display_width,
                y_position,
                fill=OVERLAY_GRID_COLOUR,
            )

    def _selection_payload_preview_image(self, payload: SelectionPayload) -> Image.Image:
        image = Image.new("RGBA", (payload.width, payload.height))
        alpha_mask = payload.alpha_mask
        if payload.width <= 0 or payload.height <= 0:
            return image
        image.putdata(
            [
                (red, green, blue, 255 if alpha_mask is None or alpha_mask[row_index][column_index] else 0)
                for row_index, row in enumerate(payload.grid)
                for column_index, (red, green, blue) in enumerate(row)
            ]
        )
        return image

    def _floating_selection_preview_image(self) -> Image.Image | None:
        floating = getattr(self, "_floating_selection", None)
        if floating is None:
            return None
        base_image = self._build_output_display_image(floating.base_result, transparent_colors_override=set())
        if base_image is None:
            return None
        payload_image = self._selection_payload_preview_image(floating.payload)
        preview = base_image.copy()
        preview.paste(payload_image, (floating.left, floating.top), payload_image)
        return preview

    def _draw_canvas_selection_overlays(self) -> None:
        if self._display_context is None or self._get_effective_view() != "processed":
            return
        current = self._current_output_result()
        if current is None:
            return
        if getattr(self, "_selection_drag_anchor", None) is not None and getattr(self, "_selection_drag_current", None) is not None:
            anchor_x, anchor_y = self._selection_drag_anchor
            current_x, current_y = self._selection_drag_current
            preview_bounds = PixelSelectionBounds(
                left=min(anchor_x, current_x),
                top=min(anchor_y, current_y),
                right=max(anchor_x, current_x) + 1,
                bottom=max(anchor_y, current_y) + 1,
            )
            self._draw_selection_rectangle_overlay(preview_bounds, current.width, current.height)
        selection = getattr(self, "_image_selection", None)
        if selection is not None and getattr(self, "_floating_selection", None) is None:
            if selection.outline_points:
                self._draw_selection_polygon_overlay(selection.outline_points, current.width, current.height)
            else:
                self._draw_selection_rectangle_overlay(selection.bounds, current.width, current.height)
        floating = getattr(self, "_floating_selection", None)
        if floating is not None:
            floating_bounds = PixelSelectionBounds(
                left=floating.left,
                top=floating.top,
                right=floating.left + floating.payload.width,
                bottom=floating.top + floating.payload.height,
            )
            self._draw_selection_rectangle_overlay(floating_bounds, current.width, current.height)
        if self._canvas_tool_mode_value() == CANVAS_TOOL_MODE_POLYGON_LASSO and self._lasso_points:
            self._draw_polygon_lasso_preview(current.width, current.height)

    def _redraw_selection_overlays_only(self) -> None:
        self.canvas.delete("selection")
        self._draw_canvas_selection_overlays()

    def _draw_selection_rectangle_overlay(self, bounds: PixelSelectionBounds, image_width: int, image_height: int) -> None:
        x0 = self._image_x_to_canvas(bounds.left, image_width)
        y0 = self._image_y_to_canvas(bounds.top, image_height)
        x1 = self._image_x_to_canvas(bounds.right, image_width)
        y1 = self._image_y_to_canvas(bounds.bottom, image_height)
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#FFFFFF", width=1, dash=(4, 4), dashoffset=0, tags=("selection",))
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#000000", width=1, dash=(4, 4), dashoffset=4, tags=("selection",))

    def _draw_selection_polygon_overlay(
        self,
        points: tuple[tuple[int, int], ...] | list[tuple[int, int]],
        image_width: int,
        image_height: int,
    ) -> None:
        if len(points) < 2:
            return
        canvas_points: list[int] = []
        for point_x, point_y in points:
            canvas_points.extend(
                (
                    self._image_x_to_canvas(point_x + 0.5, image_width),
                    self._image_y_to_canvas(point_y + 0.5, image_height),
                )
            )
        if len(points) < 3:
            self.canvas.create_line(*canvas_points, fill="#FFFFFF", width=1, dash=(4, 4), tags=("selection",))
            self.canvas.create_line(*canvas_points, fill="#000000", width=1, dash=(4, 4), dashoffset=4, tags=("selection",))
            return
        self.canvas.create_polygon(*canvas_points, outline="#FFFFFF", fill="", width=1, dash=(4, 4), dashoffset=0, tags=("selection",))
        self.canvas.create_polygon(*canvas_points, outline="#000000", fill="", width=1, dash=(4, 4), dashoffset=4, tags=("selection",))

    def _draw_polygon_lasso_preview(self, image_width: int, image_height: int) -> None:
        hover_point = getattr(self, "_lasso_hover_point", None)
        near_start = self._lasso_hover_is_near_start(image_width, image_height)
        if len(self._lasso_points) >= 2:
            self._draw_selection_polygon_overlay(self._lasso_points, image_width, image_height)
        point_x, point_y = self._lasso_points[0]
        center_x = self._image_x_to_canvas(point_x + 0.5, image_width)
        center_y = self._image_y_to_canvas(point_y + 0.5, image_height)
        r = _LASSO_CLOSE_RADIUS_PX
        if len(self._lasso_points) >= 3:
            fill_color = "#FFFFFF" if near_start else ""
            outline_color = "#FFFFFF"
            self.canvas.create_oval(
                center_x - r, center_y - r, center_x + r, center_y + r,
                fill=fill_color, outline=outline_color, width=1, dash=(3, 3),
                tags=("selection",),
            )
        else:
            self.canvas.create_oval(
                center_x - 2, center_y - 2, center_x + 2, center_y + 2,
                fill="#FFFFFF", outline="", tags=("selection",),
            )
        if hover_point is None:
            return
        last_point = self._lasso_points[-1]
        if hover_point == last_point and not near_start:
            return
        if near_start:
            end_x = center_x
            end_y = center_y
        else:
            end_x = self._image_x_to_canvas(hover_point[0] + 0.5, image_width)
            end_y = self._image_y_to_canvas(hover_point[1] + 0.5, image_height)
        self.canvas.create_line(
            self._image_x_to_canvas(last_point[0] + 0.5, image_width),
            self._image_y_to_canvas(last_point[1] + 0.5, image_height),
            end_x, end_y,
            fill="#FFFFFF", dash=(4, 4), tags=("selection",),
        )
        self.canvas.create_line(
            self._image_x_to_canvas(last_point[0] + 0.5, image_width),
            self._image_y_to_canvas(last_point[1] + 0.5, image_height),
            end_x, end_y,
            fill="#000000", dash=(4, 4), dashoffset=4, tags=("selection",),
        )

    def _get_effective_view(self) -> str:
        if self.quick_compare_active and self.view_var.get() == "processed":
            return "original"
        return self.view_var.get()

    def _get_sample_image(self) -> Image.Image | None:
        if self.original_display_image is None:
            return None
        if self._get_effective_view() == "original":
            return self._get_comparison_original_image()
        preview_image = self._shape_preview_image()
        if preview_image is not None:
            return preview_image
        floating_preview = self._floating_selection_preview_image()
        if floating_preview is not None:
            return floating_preview
        return self._current_output_image()

    def _current_output_result(self) -> ProcessResult | None:
        return getattr(self, "palette_result", None) or getattr(self, "downsample_result", None)

    def _current_output_image(self) -> Image.Image | None:
        return getattr(self, "palette_display_image", None) or getattr(self, "downsample_display_image", None)

    def _get_comparison_original_image(self) -> Image.Image | None:
        if self.original_display_image is None:
            return None
        current = self._current_output_result()
        if current is None or self.original_grid is None:
            return self.original_display_image
        key = (
            current.stats.pixel_width,
            current.stats.resize_method,
            current.width,
            current.height,
        )
        if self._comparison_original_key != key or self.comparison_original_image is None:
            resized = resize_labels(
                rgb_to_labels(self.original_grid),
                current.stats.pixel_width,
                method=current.stats.resize_method,
            )
            self.comparison_original_image = grid_to_pil_image(labels_to_rgb(resized)).convert("RGBA")
            self._comparison_original_key = key
        return self.comparison_original_image

    def _palette_source_grid(self) -> RGBGrid | None:
        if self.downsample_result is not None:
            return self.downsample_result.grid
        return self.original_grid

    def _override_palette_source_labels(self) -> list[list[int]] | None:
        if self.prepared_input_cache is None:
            return None
        return self.prepared_input_cache.reduced_labels

    def _override_palette_target_size(self, labels: list[list[int]], settings: PreviewSettings) -> int:
        unique_count = len(extract_unique_colors(labels))
        if unique_count <= 0:
            return 0
        target = settings.palette_reduction_colors
        return max(1, min(target, unique_count))

    def _on_canvas_press(self, event: tk.Event) -> None:
        if getattr(self, "_mouse_button_action_state", None) is not None:
            return
        mode = self._canvas_tool_mode_value()
        if getattr(self, "original_display_image", None) is None and mode is None:
            return
        if mode == CANVAS_TOOL_MODE_SELECT:
            coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
            if getattr(self, "_floating_selection", None) is not None and coordinates is not None:
                if self._floating_selection_contains_point(*coordinates):
                    self._selection_drag_active = True
                    self._floating_selection_drag_origin = coordinates
                    self._floating_selection_drag_start = (self._floating_selection.left, self._floating_selection.top)
                    self.canvas.configure(cursor=CLOSED_HAND_CURSOR)
                    return
                self._commit_floating_selection()
            if coordinates is None:
                return
            if self._selection_contains_point(*coordinates) and self._lift_current_selection():
                self._selection_drag_active = True
                self._floating_selection_drag_origin = coordinates
                self._floating_selection_drag_start = (self._floating_selection.left, self._floating_selection.top)
                self.redraw_canvas()
                self.canvas.configure(cursor=CLOSED_HAND_CURSOR)
                self._refresh_action_states()
                return
            self._clear_image_selection()
            self._selection_drag_active = True
            self._selection_drag_anchor = coordinates
            self._selection_drag_current = coordinates
            self._redraw_selection_overlays_only()
            self.canvas.configure(cursor="crosshair")
            self._refresh_action_states()
            return
        if mode == CANVAS_TOOL_MODE_POLYGON_LASSO:
            coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
            if not self._lasso_points:
                if getattr(self, "_floating_selection", None) is not None and coordinates is not None:
                    if self._floating_selection_contains_point(*coordinates):
                        self._selection_drag_active = True
                        self._floating_selection_drag_origin = coordinates
                        self._floating_selection_drag_start = (self._floating_selection.left, self._floating_selection.top)
                        self.canvas.configure(cursor=CLOSED_HAND_CURSOR)
                        return
                    self._commit_floating_selection()
                if coordinates is not None and self._selection_contains_point(*coordinates) and self._lift_current_selection():
                    self._selection_drag_active = True
                    self._floating_selection_drag_origin = coordinates
                    self._floating_selection_drag_start = (self._floating_selection.left, self._floating_selection.top)
                    self.redraw_canvas()
                    self.canvas.configure(cursor=CLOSED_HAND_CURSOR)
                    self._refresh_action_states()
                    return
                self._clear_image_selection()
            if getattr(self, "_floating_selection", None) is not None:
                self._commit_floating_selection()
            if coordinates is None:
                return
            self._lasso_hover_point_canvas = (event.x, event.y)
            current = self._current_output_result()
            iw = current.width if current is not None else 0
            ih = current.height if current is not None else 0
            if len(self._lasso_points) >= 3 and self._lasso_hover_is_near_start(iw, ih):
                self._finalize_polygon_lasso()
                return
            if not self._lasso_points or self._lasso_points[-1] != coordinates:
                self._lasso_points.append(coordinates)
            self._lasso_hover_point = coordinates
            self._redraw_selection_overlays_only()
            self._refresh_action_states()
            return
        if mode == CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK:
            sampled = self._sample_label_from_preview(event.x, event.y, view="processed")
            if sampled is not None:
                self._assign_palette_color_to_slot(self._active_color_slot_value(), sampled)
                self._set_canvas_tool_mode(None)
                self._refresh_action_states()
            return
        if mode == CANVAS_TOOL_MODE_PALETTE_PICK:
            sampled = self._sample_label_from_preview(event.x, event.y, view="original")
            if sampled is not None:
                self._add_colour_to_current_palette(sampled)
                self._set_canvas_tool_mode(None)
                self._refresh_action_states()
            return
        if mode == CANVAS_TOOL_MODE_TRANSPARENCY_PICK:
            sampled = self._sample_point_from_preview(event.x, event.y, view="processed")
            if sampled is not None:
                image_x, image_y, label = sampled
                self._add_transparent_region(image_x, image_y, label)
                self._set_canvas_tool_mode(None)
                self._refresh_action_states()
            return
        if mode == CANVAS_TOOL_MODE_BUCKET:
            coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
            if coordinates is not None:
                image_x, image_y = coordinates
                self._fill_bucket_region(image_x, image_y)
            return
        if self._is_brush_tool_mode(mode):
            coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
            if coordinates is None:
                return
            image_x, image_y = coordinates
            self._start_brush_stroke(mode, image_x, image_y)
            return
        if self._is_shape_tool_mode(mode):
            coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
            if coordinates is None:
                return
            self._shape_drag_active = True
            self._shape_preview_anchor = coordinates
            self._shape_preview_current = coordinates
            self._shape_preview_tool_mode = mode
            self._shape_preview_constrained = self._event_has_shift(event)
            self._capture_palette_undo_state()
            self.redraw_canvas()
            self.canvas.configure(cursor="crosshair")
            return
        if not self._point_is_over_image(event.x, event.y):
            return
        self.dragging = True
        self.drag_origin = (event.x, event.y)
        self.drag_pan_start = (self.pan_x, self.pan_y)
        self.canvas.configure(cursor=CLOSED_HAND_CURSOR)

    def _on_canvas_drag(self, event: tk.Event) -> None:
        if getattr(self, "_brush_stroke_active", False) and self._is_brush_tool_mode(getattr(self, "_brush_stroke_tool_mode", None)):
            self._drag_active_brush_stroke(event)
            return
        if getattr(self, "_shape_drag_active", False) and self._is_shape_tool_mode(getattr(self, "_shape_preview_tool_mode", None)):
            coordinates = self._preview_image_coordinates(event.x, event.y, view="processed", clamp=True)
            if coordinates is None:
                return
            self._shape_preview_current = coordinates
            self._shape_preview_constrained = self._event_has_shift(event)
            self.redraw_canvas()
            return
        if getattr(self, "_selection_drag_active", False):
            if getattr(self, "_floating_selection_drag_origin", None) is not None and getattr(self, "_floating_selection", None) is not None:
                coordinates = self._preview_image_coordinates(event.x, event.y, view="processed", clamp=True)
                if coordinates is None:
                    return
                origin_x, origin_y = self._floating_selection_drag_origin
                start_left, start_top = self._floating_selection_drag_start or (self._floating_selection.left, self._floating_selection.top)
                next_left = start_left + (coordinates[0] - origin_x)
                next_top = start_top + (coordinates[1] - origin_y)
                next_left, next_top = self._clamp_payload_position(
                    self._floating_selection.base_result.width,
                    self._floating_selection.base_result.height,
                    self._floating_selection.payload,
                    next_left,
                    next_top,
                )
                self._floating_selection = replace(self._floating_selection, left=next_left, top=next_top)
                self.redraw_canvas()
                return
            if getattr(self, "_selection_drag_anchor", None) is not None:
                coordinates = self._preview_image_coordinates(event.x, event.y, view="processed", clamp=True)
                if coordinates is None:
                    return
                self._selection_drag_current = coordinates
                self._redraw_selection_overlays_only()
                return
        if not self.dragging or self._display_context is None:
            return
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        if self._display_context.display_width > canvas_width:
            self.pan_x = max(0, self.drag_pan_start[0] - (event.x - self.drag_origin[0]))
        if self._display_context.display_height > canvas_height:
            self.pan_y = max(0, self.drag_pan_start[1] - (event.y - self.drag_origin[1]))
        self.redraw_canvas()

    def _on_canvas_release(self, event: tk.Event) -> None:
        if getattr(self, "_brush_stroke_active", False):
            self._finish_active_brush_stroke()
            return
        if getattr(self, "_shape_drag_active", False):
            if hasattr(event, "x") and hasattr(event, "y"):
                coordinates = self._preview_image_coordinates(event.x, event.y, view="processed", clamp=True)
                if coordinates is not None:
                    self._shape_preview_current = coordinates
            self._shape_preview_constrained = self._event_has_shift(event)
            updated, changed = self._shape_preview_operation()
            if updated is not None and changed > 0:
                mode = getattr(self, "_shape_preview_tool_mode", None)
                constrained = bool(getattr(self, "_shape_preview_constrained", False))
                tool_name = self._shape_tool_display_name(mode, constrained=constrained)
                self.transparent_colors = set()
                self._set_current_output_result(updated)
                self._refresh_output_display_images()
                self.process_status_var.set(
                    f"{tool_name} changed {changed} pixel{'s' if changed != 1 else ''}. Press Undo to restore it."
                )
                self._refresh_action_states()
            else:
                clear_undo = getattr(self, "_clear_palette_undo_state", None)
                if callable(clear_undo):
                    clear_undo()
            self._reset_shape_preview_state()
            self.redraw_canvas()
            self.canvas.configure(cursor=self._cursor_for_pointer())
            return
        if getattr(self, "_selection_drag_active", False):
            current = self._current_output_result()
            if current is not None and getattr(self, "_selection_drag_anchor", None) is not None:
                coordinates = self._preview_image_coordinates(event.x, event.y, view="processed", clamp=True)
                if coordinates is not None:
                    self._selection_drag_current = coordinates
                anchor = self._selection_drag_anchor
                endpoint = self._selection_drag_current or anchor
                mask = rasterize_rectangle_selection_mask(current.width, current.height, anchor[0], anchor[1], endpoint[0], endpoint[1])
                if mask is None:
                    self._clear_image_selection()
                    self.process_status_var.set("Selection cleared.")
                else:
                    bounds = selection_mask_bounds(mask)
                    self._set_image_selection(
                        mask,
                        outline_points=() if bounds is None else self._selection_outline_points_for_bounds(bounds),
                    )
                    if self._image_selection is None:
                        self.process_status_var.set("Single-pixel selections are ignored.")
                    else:
                        self.process_status_var.set("Rectangular selection created.")
            self._reset_selection_drag_state()
            self.dragging = False
            self.redraw_canvas()
            self.canvas.configure(cursor=self._cursor_for_pointer())
            self._refresh_action_states()
            return
        self.dragging = False
        self.canvas.configure(cursor=self._cursor_for_pointer())

    def _on_canvas_motion(self, event: tk.Event) -> None:
        mode = self._canvas_tool_mode_value()
        if self.dragging:
            self.canvas.configure(cursor=CLOSED_HAND_CURSOR)
        elif getattr(self, "_selection_drag_active", False):
            self.canvas.configure(cursor=CLOSED_HAND_CURSOR if getattr(self, "_floating_selection_drag_origin", None) is not None else "crosshair")
        elif mode == CANVAS_TOOL_MODE_SELECT:
            self._set_pick_preview(None)
            coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
            if coordinates is not None and (
                self._selection_contains_point(*coordinates) or self._floating_selection_contains_point(*coordinates)
            ):
                self.canvas.configure(cursor=OPEN_HAND_CURSOR)
            else:
                self.canvas.configure(cursor="crosshair")
        elif mode == CANVAS_TOOL_MODE_POLYGON_LASSO:
            self._set_pick_preview(None)
            coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
            next_hover = coordinates if coordinates is not None else None
            self._lasso_hover_point_canvas = (event.x, event.y) if coordinates is not None else None
            if next_hover != getattr(self, "_lasso_hover_point", None):
                self._lasso_hover_point = next_hover
                if self._lasso_points:
                    self._redraw_selection_overlays_only()
            if not self._lasso_points and coordinates is not None and (
                self._selection_contains_point(*coordinates) or self._floating_selection_contains_point(*coordinates)
            ):
                self.canvas.configure(cursor=OPEN_HAND_CURSOR)
            else:
                current = self._current_output_result()
                iw = current.width if current is not None else 0
                ih = current.height if current is not None else 0
                if self._lasso_hover_is_near_start(iw, ih):
                    self.canvas.configure(cursor="hand2")
                else:
                    self.canvas.configure(cursor="crosshair")
        elif mode == CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK:
            self.canvas.configure(cursor="crosshair")
            self._update_pick_preview(event.x, event.y)
        elif self._is_crosshair_tool_mode(mode):
            self._set_pick_preview(None)
            self.canvas.configure(cursor="crosshair")
        else:
            self._set_pick_preview(None)
            self.canvas.configure(cursor=OPEN_HAND_CURSOR if self._point_is_over_image(event.x, event.y) else "")

    def _on_canvas_leave(self, _event: tk.Event) -> None:
        self._set_pick_preview(None)
        if getattr(self, "_lasso_hover_point", None) is not None:
            self._lasso_hover_point = None
            self._lasso_hover_point_canvas = None
            if self._lasso_points:
                self._redraw_selection_overlays_only()
        if not self.dragging and not getattr(self, "_brush_stroke_active", False):
            self.canvas.configure(cursor="")

    def _on_canvas_double_click(self, event: tk.Event) -> None:
        if self._canvas_tool_mode_value() != CANVAS_TOOL_MODE_POLYGON_LASSO:
            return
        coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
        if coordinates is None or len(self._lasso_points) < 3:
            return
        if coordinates != self._lasso_points[0] and len(self._lasso_points) >= 4 and self._lasso_points[-1] == coordinates:
            self._lasso_points.pop()
        self._finalize_polygon_lasso()

    def _start_quick_compare(self) -> bool:
        if (
            self.view_var.get() != "processed"
            or self._current_output_image() is None
            or getattr(self, "_brush_stroke_active", False)
            or getattr(self, "_shape_drag_active", False)
            or getattr(self, "_selection_drag_active", False)
            or getattr(self, "_floating_selection", None) is not None
            or bool(getattr(self, "_lasso_points", []))
            or getattr(self, "dragging", False)
        ):
            return False
        self.quick_compare_active = True
        self.redraw_canvas()
        return True

    def _stop_quick_compare(self) -> bool:
        if not self.quick_compare_active:
            return False
        self.quick_compare_active = False
        self.redraw_canvas()
        return True

    def _on_quick_compare_press(self, _event: tk.Event) -> None:
        self._start_quick_compare()

    def _on_quick_compare_release(self, _event: tk.Event) -> None:
        self._stop_quick_compare()

    def _on_canvas_assigned_button_press(self, event: tk.Event, button: int) -> None:
        if self._canvas_interaction_active():
            return
        if button == CANVAS_MOUSE_BUTTON_RIGHT and self._clear_canvas_selection():
            return
        action = self._mouse_button_action(button)
        if action == MOUSE_BUTTON_ACTION_VIEW_ORIGINAL:
            if self._start_quick_compare():
                self._mouse_button_action_state = CanvasMouseActionState(button, action)
            return
        if action == MOUSE_BUTTON_ACTION_SAMPLE_COLOR:
            sampled = self._sample_visible_preview_label(event.x, event.y)
            if sampled is not None:
                self._assign_palette_color_to_slot(self._active_color_slot_value(), sampled)
            return
        if action == MOUSE_BUTTON_ACTION_SWAP_COLORS:
            self._swap_active_colors()
            return
        if action != MOUSE_BUTTON_ACTION_ERASER:
            return
        if self._get_effective_view() != "processed" or self._current_output_result() is None:
            return
        coordinates = self._preview_image_coordinates(event.x, event.y, view="processed")
        if coordinates is None:
            return
        image_x, image_y = coordinates
        self._mouse_button_action_state = CanvasMouseActionState(button, action)
        self._start_brush_stroke(CANVAS_TOOL_MODE_ERASER, image_x, image_y)

    def _on_canvas_assigned_button_drag(self, event: tk.Event, button: int) -> None:
        state = getattr(self, "_mouse_button_action_state", None)
        if state is None or state.button != button or state.action != MOUSE_BUTTON_ACTION_ERASER:
            return
        self._drag_active_brush_stroke(event)

    def _on_canvas_assigned_button_release(self, _event: tk.Event, button: int) -> None:
        state = getattr(self, "_mouse_button_action_state", None)
        if state is None or state.button != button:
            return
        self._mouse_button_action_state = None
        if state.action == MOUSE_BUTTON_ACTION_VIEW_ORIGINAL:
            self._stop_quick_compare()
        elif state.action == MOUSE_BUTTON_ACTION_ERASER:
            self._finish_active_brush_stroke()

    def _cursor_for_pointer(self) -> str:
        mode = self._canvas_tool_mode_value()
        if mode == CANVAS_TOOL_MODE_SELECT:
            coordinates = self._preview_image_coordinates(
                self.canvas.winfo_pointerx() - self.canvas.winfo_rootx(),
                self.canvas.winfo_pointery() - self.canvas.winfo_rooty(),
                view="processed",
            )
            if coordinates is not None and (
                self._selection_contains_point(*coordinates) or self._floating_selection_contains_point(*coordinates)
            ):
                return OPEN_HAND_CURSOR
            return "crosshair"
        if self._is_crosshair_tool_mode(mode):
            return "crosshair"
        return OPEN_HAND_CURSOR if self._point_is_over_image() else ""

    def _palette_hit_test(self, x: int, y: int) -> tuple[int, int] | None:
        for index, (x0, y0, x1, y1) in enumerate(self._palette_hit_regions):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return index, self._displayed_palette[index]
        return None

    def _reset_palette_ctrl_drag_state(self) -> None:
        self._palette_ctrl_drag_active = False
        self._palette_ctrl_drag_anchor_index = None
        self._palette_ctrl_drag_indices = set()
        self._palette_ctrl_drag_initial_selection = set()

    def _finalize_palette_ctrl_drag(self, *, toggle_if_single: bool) -> None:
        if not getattr(self, "_palette_ctrl_drag_active", False):
            return
        drag_indices = set(getattr(self, "_palette_ctrl_drag_indices", set()))
        initial_selection = set(getattr(self, "_palette_ctrl_drag_initial_selection", set()))
        anchor_index = getattr(self, "_palette_ctrl_drag_anchor_index", None)
        updated_selection = set(getattr(self, "_palette_selection_indices", set()))
        updated_anchor = getattr(self, "_palette_selection_anchor_index", None)
        if len(drag_indices) <= 1 and toggle_if_single:
            index = next(iter(drag_indices), None)
            if index is not None:
                updated_selection = set(initial_selection)
                if index in updated_selection:
                    updated_selection.remove(index)
                else:
                    updated_selection.add(index)
                updated_anchor = index if updated_selection else None
        else:
            updated_selection = initial_selection | drag_indices
            updated_anchor = anchor_index if updated_selection else None
        changed = (
            updated_selection != getattr(self, "_palette_selection_indices", set())
            or updated_anchor != getattr(self, "_palette_selection_anchor_index", None)
        )
        self._palette_selection_indices = updated_selection
        self._palette_selection_anchor_index = updated_anchor
        self._reset_palette_ctrl_drag_state()
        if changed:
            self._update_palette_strip()
            self._refresh_action_states()

    def _on_palette_canvas_click(self, event: tk.Event) -> None:
        hit = self._palette_hit_test(event.x, event.y)
        self._reset_palette_ctrl_drag_state()
        assigned_primary = False
        if hit is None:
            self._palette_selection_indices = set()
            self._palette_selection_anchor_index = None
        else:
            index, label = hit
            state = int(getattr(event, "state", 0))
            ctrl_down = bool(state & 0x0004)
            shift_down = bool(state & 0x0001)
            anchor = getattr(self, "_palette_selection_anchor_index", None)
            if ctrl_down and not shift_down:
                self._palette_ctrl_drag_active = True
                self._palette_ctrl_drag_anchor_index = index
                self._palette_ctrl_drag_indices = {index}
                self._palette_ctrl_drag_initial_selection = set(self._palette_selection_indices)
                return
            if shift_down and anchor is not None:
                start = min(anchor, index)
                end = max(anchor, index)
                range_selection = set(range(start, end + 1))
                if ctrl_down:
                    self._palette_selection_indices |= range_selection
                else:
                    self._palette_selection_indices = range_selection
            elif ctrl_down:
                if index in self._palette_selection_indices:
                    self._palette_selection_indices.remove(index)
                else:
                    self._palette_selection_indices.add(index)
                self._palette_selection_anchor_index = index
            else:
                self._palette_selection_indices = {index}
                self._palette_selection_anchor_index = index
                self._assign_palette_color_to_slot(ACTIVE_COLOR_SLOT_PRIMARY, label)
                assigned_primary = True
        self._update_palette_strip()
        if not assigned_primary:
            self._refresh_action_states()

    def _on_palette_canvas_drag(self, event: tk.Event) -> None:
        if not getattr(self, "_palette_ctrl_drag_active", False):
            return
        state = int(getattr(event, "state", 0))
        if not (state & 0x0004):
            self._finalize_palette_ctrl_drag(toggle_if_single=False)
            return
        hit = self._palette_hit_test(event.x, event.y)
        if hit is None:
            return
        index, _label = hit
        drag_indices = set(getattr(self, "_palette_ctrl_drag_indices", set()))
        if index in drag_indices:
            return
        drag_indices.add(index)
        self._palette_ctrl_drag_indices = drag_indices
        self._palette_selection_indices = set(getattr(self, "_palette_ctrl_drag_initial_selection", set())) | drag_indices
        self._palette_selection_anchor_index = getattr(self, "_palette_ctrl_drag_anchor_index", None)
        self._update_palette_strip()
        self._refresh_action_states()

    def _on_palette_canvas_release(self, _event: tk.Event) -> None:
        self._finalize_palette_ctrl_drag(toggle_if_single=True)

    def _on_palette_canvas_double_click(self, event: tk.Event) -> None:
        self._on_palette_canvas_click(event)

    def _on_palette_canvas_right_click(self, event: tk.Event) -> None:
        hit = self._palette_hit_test(event.x, event.y)
        self._reset_palette_ctrl_drag_state()
        if hit is None:
            self._palette_selection_indices = set()
            self._palette_selection_anchor_index = None
            self._update_palette_strip()
            self._refresh_action_states()
            return
        _index, label = hit
        self._assign_palette_color_to_slot(ACTIVE_COLOR_SLOT_SECONDARY, label)

    def _select_all_palette_colors(self) -> None:
        if not self._displayed_palette:
            self.process_status_var.set("There is no current palette to select.")
            return
        self._palette_selection_indices = set(range(len(self._displayed_palette)))
        self._palette_selection_anchor_index = 0 if self._displayed_palette else None
        self._update_palette_strip()
        self._refresh_action_states()
        self.process_status_var.set(f"Selected {len(self._palette_selection_indices)} palette colours.")

    def _clear_palette_selection(self) -> None:
        if not self._palette_selection_indices:
            return
        self._palette_selection_indices = set()
        self._palette_selection_anchor_index = None
        self._update_palette_strip()
        self._refresh_action_states()

    def _invert_palette_selection(self) -> None:
        if not self._displayed_palette:
            self.process_status_var.set("There is no current palette to select.")
            return
        all_indices = set(range(len(self._displayed_palette)))
        current_selection = {
            index for index in getattr(self, "_palette_selection_indices", set()) if 0 <= index < len(self._displayed_palette)
        }
        inverted = all_indices - current_selection
        self._palette_selection_indices = inverted
        self._palette_selection_anchor_index = min(inverted) if inverted else None
        self._update_palette_strip()
        self._refresh_action_states()
        self.process_status_var.set(f"Inverted palette selection. {len(inverted)} palette colour{'s' if len(inverted) != 1 else ''} selected.")

    def _point_is_over_image(self, x: int | None = None, y: int | None = None) -> bool:
        if self._display_context is None:
            return False
        px = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx() if x is None else x
        py = self.canvas.winfo_pointery() - self.canvas.winfo_rooty() if y is None else y
        return (
            self._display_context.image_left <= px <= self._display_context.image_left + self._display_context.display_width
            and self._display_context.image_top <= py <= self._display_context.image_top + self._display_context.display_height
        )

    def _on_zoom_wheel(self, event: tk.Event) -> None:
        if self.original_display_image is None:
            return
        self._set_zoom(zoom_in(self.zoom) if event.delta > 0 else zoom_out(self.zoom))

    def _set_zoom(self, value: int) -> None:
        self.zoom = clamp_zoom(value)
        self._sync_toolbar_zoom_dropdown()
        self.redraw_canvas()
        self._schedule_state_persist()

    def zoom_fit(self) -> None:
        sample_image = self._get_sample_image() or self.original_display_image
        if sample_image is None:
            self._sync_toolbar_zoom_dropdown()
            return
        self.zoom = choose_fit_zoom(sample_image.width, sample_image.height, max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()))
        self.pan_x = 0
        self.pan_y = 0
        self._sync_toolbar_zoom_dropdown()
        self.redraw_canvas()
        self._schedule_state_persist()

    def _clamp_pan(self, display_width: int, display_height: int, canvas_width: int, canvas_height: int) -> None:
        self.pan_x = min(max(self.pan_x, 0), max(0, display_width - canvas_width))
        self.pan_y = min(max(self.pan_y, 0), max(0, display_height - canvas_height))

    def _apply_view_selection(self, value: str, *, persist: bool) -> None:
        if value != "processed":
            if getattr(self, "_floating_selection", None) is not None:
                self._commit_floating_selection()
            if getattr(self, "_lasso_points", []):
                self._cancel_polygon_lasso()
        self.view_var.set("processed" if value == "processed" else "original")
        self.redraw_canvas()
        self._refresh_tool_button_styles()
        if persist:
            self._schedule_state_persist()

    def _on_view_changed(self) -> None:
        self._apply_view_selection(self.view_var.get(), persist=True)

    def _set_view(self, value: str) -> None:
        self._apply_view_selection(value, persist=False)

    def _set_view_from_toolbar(self, value: str) -> None:
        self._apply_view_selection(value, persist=True)

    def _update_scale_info(self) -> None:
        if self.original_display_image is None:
            self.scale_info_var.set("Open an image to set the pixel size.")
            return
        pixel_width = max(1, int(self.pixel_width_var.get() or self.session.current.pixel_width))
        output_width, output_height = target_size_for_pixel_width(self.original_display_image.width, self.original_display_image.height, pixel_width)
        self.scale_info_var.set(f"Pixel size: {pixel_width} px  Output: {output_width}x{output_height}")

    def _current_image_colour_count(self) -> int | None:
        current = self._current_output_result()
        if current is not None:
            return getattr(current.stats, "color_count", None)
        original_grid = getattr(self, "original_grid", None)
        if not original_grid:
            return None
        return len({colour for row in original_grid for colour in row})

    def _update_palette_strip(self) -> None:
        if hasattr(self, "_menu_items") and "palette_sort" in self._menu_items:
            self._populate_palette_sort_menu()
        self.palette_canvas.delete("all")
        self._palette_hit_regions = []
        preview_entry = getattr(self, "_builtin_palette_preview_entry", None)
        preview_active = preview_entry is not None
        if preview_entry is not None:
            palette = list(preview_entry.colors)
            source = f"Preview: {preview_entry.source_label}"
        else:
            palette, source = self._get_display_palette()
        if not palette:
            self._displayed_palette = []
            if not preview_active:
                self._palette_selection_indices = set()
                self._palette_selection_anchor_index = None
            palette_frame = getattr(self, "palette_frame", None)
            if palette_frame is not None and hasattr(palette_frame, "configure"):
                palette_frame.configure(text="PALETTE")
            self.palette_info_var.set("Palette: none")
            self.palette_canvas.yview_moveto(0)
            self.palette_canvas.configure(scrollregion=(0, 0, 0, 0))
            return
        displayed = palette[:MAX_PALETTE_SWATCHES]
        self._displayed_palette = list(displayed)
        display_selection = {index for index in self._palette_selection_indices if 0 <= index < len(displayed)}
        if not preview_active:
            self._palette_selection_indices = display_selection
        anchor_index = getattr(self, "_palette_selection_anchor_index", None)
        if not preview_active and anchor_index is not None and anchor_index >= len(displayed):
            self._palette_selection_anchor_index = None
        suffix = "" if len(displayed) == len(palette) else f" (showing first {len(displayed)})"
        selected_count = len(display_selection)
        selection_suffix = f", {selected_count} selected" if selected_count else ""
        palette_frame = getattr(self, "palette_frame", None)
        if palette_frame is not None and hasattr(palette_frame, "configure"):
            palette_frame.configure(text=f"PALETTE ({len(palette)})")
        self.palette_info_var.set(f"Palette: {source} ({len(palette)} colours{selection_suffix}){suffix}")
        scrollbar = getattr(self, "palette_scrollbar", None)
        scrollbar_width = scrollbar.winfo_width() if scrollbar is not None and scrollbar.winfo_ismapped() else 0
        available_width = max(PALETTE_SWATCH_SIZE, self.palette_canvas.winfo_width() - scrollbar_width)
        columns = max(1, available_width // PALETTE_SWATCH_SIZE)
        fill_inset = max(0, (PALETTE_SWATCH_SIZE - PALETTE_SWATCH_COLOUR_SIZE) // 2)
        for index, colour in enumerate(displayed):
            row = index // columns
            col = index % columns
            x0 = col * PALETTE_SWATCH_SIZE
            y0 = row * PALETTE_SWATCH_SIZE
            x1 = x0 + PALETTE_SWATCH_SIZE - 1
            y1 = y0 + PALETTE_SWATCH_SIZE - 1
            selected = index in display_selection
            border_colour = APP_ACCENT if selected else APP_BG
            self.palette_canvas.create_rectangle(x0, y0, x1, y1, fill=border_colour, outline="")
            self.palette_canvas.create_rectangle(
                x0 + fill_inset,
                y0 + fill_inset,
                x0 + fill_inset + PALETTE_SWATCH_COLOUR_SIZE - 1,
                y0 + fill_inset + PALETTE_SWATCH_COLOUR_SIZE - 1,
                fill=f"#{colour:06x}",
                outline="",
            )
            self._palette_hit_regions.append((x0, y0, x1, y1))
        total_rows = ((len(displayed) - 1) // columns) + 1
        self.palette_canvas.configure(scrollregion=(0, 0, columns * PALETTE_SWATCH_SIZE, total_rows * PALETTE_SWATCH_SIZE))

    def _get_display_palette(self) -> tuple[list[int], str]:
        palette, source = self._current_palette_source_labels()
        if not palette:
            return ([], "none")
        return palette, source

    def _update_image_info(self) -> None:
        filename = self.source_path.name if self.source_path is not None else "No image"
        current = self._current_output_result()
        if current is not None:
            resolution = f"{current.width}x{current.height}"
        elif self.original_display_image is not None:
            resolution = f"{self.original_display_image.width}x{self.original_display_image.height}"
        else:
            resolution = "-"
        colour_count = self._current_image_colour_count()
        colour_text = f"{colour_count} colours" if colour_count is not None else "-"
        self.image_info_var.set(f"{filename}  {resolution}  {colour_text}  {self.zoom}%")

    def _read_settings_from_controls(self, *, strict: bool) -> PreviewSettings:
        pixel_width = max(1, int(self.pixel_width_var.get()))
        if strict and pixel_width <= 0:
            raise ValueError("Pixel size must be at least 1.")
        return PreviewSettings(
            pixel_width=pixel_width,
            downsample_mode=RESIZE_DISPLAY_TO_VALUE.get(self.downsample_mode_var.get(), "nearest"),
            palette_reduction_colors=max(1, min(256, int(self.palette_reduction_colors_var.get() or 16))),
            generated_shades=max(2, min(10, int(self.generated_shades_var.get() or 4))),
            auto_detect_count=max(1, min(MAX_KEY_COLORS, int(self.auto_detect_count_var.get() or MAX_KEY_COLORS))),
            contrast_bias=max(0.1, min(1.0, float(self.contrast_bias_var.get() or 1.0))),
            palette_brightness=max(-100, min(100, int(self.palette_brightness_var.get() or 0))),
            palette_contrast=max(0, min(200, int(self.palette_contrast_var.get() or 0) + 100)),
            palette_hue=max(-180, min(180, int(self.palette_hue_var.get() or 0))),
            palette_saturation=max(0, min(200, int(self.palette_saturation_var.get() or 0) + 100)),
            palette_dither_mode=DITHER_DISPLAY_TO_VALUE.get(self.palette_dither_var.get(), "none"),
            input_mode=COLOR_MODE_DISPLAY_TO_VALUE.get(self.input_mode_var.get(), "rgba"),
            output_mode=COLOR_MODE_DISPLAY_TO_VALUE.get(self.output_mode_var.get(), "rgba"),
            quantizer=QUANTIZER_DISPLAY_TO_VALUE.get(self.quantizer_var.get(), QUANTIZER_OPTIONS[0][1]),
            dither_mode=DITHER_DISPLAY_TO_VALUE.get(self.dither_var.get(), "none"),
        )

    def _sync_controls_from_settings(self, settings: PreviewSettings) -> None:
        self._suspend_control_events = True
        try:
            self.pixel_width_var.set(settings.pixel_width)
            self.downsample_mode_var.set(RESIZE_VALUE_TO_DISPLAY.get(settings.downsample_mode, RESIZE_OPTIONS[0][0]))
            self.palette_reduction_colors_var.set(settings.palette_reduction_colors)
            self.generated_shades_var.set(str(settings.generated_shades))
            self.auto_detect_count_var.set(str(settings.auto_detect_count))
            self.contrast_bias_var.set(settings.contrast_bias)
            self.palette_brightness_var.set(settings.palette_brightness)
            self.palette_contrast_var.set(settings.palette_contrast - 100)
            self.palette_hue_var.set(settings.palette_hue)
            self.palette_saturation_var.set(settings.palette_saturation - 100)
            self.palette_dither_var.set(DITHER_VALUE_TO_DISPLAY.get(settings.palette_dither_mode, DITHER_OPTIONS[0][0]))
            self.input_mode_var.set(COLOR_MODE_VALUE_TO_DISPLAY.get(settings.input_mode, COLOR_MODE_OPTIONS[0][0]))
            self.output_mode_var.set(COLOR_MODE_VALUE_TO_DISPLAY.get(settings.output_mode, COLOR_MODE_OPTIONS[0][0]))
            self.quantizer_var.set(QUANTIZER_VALUE_TO_DISPLAY.get(settings.quantizer, QUANTIZER_OPTIONS[0][0]))
            self.dither_var.set(DITHER_VALUE_TO_DISPLAY.get(settings.dither_mode, DITHER_OPTIONS[0][0]))
        finally:
            self._suspend_control_events = False
        self._update_palette_adjustment_labels()

    def _on_settings_changed(self, _event: tk.Event | None = None) -> None:
        if self._suspend_control_events or self.image_state == "processing":
            return
        try:
            previous = self.session.current
            updated = self._read_settings_from_controls(strict=False)
        except Exception:
            return
        if updated == previous:
            self._update_scale_info()
            return
        self.session.apply(**vars(updated))
        self._handle_settings_transition(previous, updated)

    def _handle_settings_transition(self, previous: PreviewSettings, updated: PreviewSettings, message: str | None = None) -> None:
        downsample_changed = (
            previous.pixel_width != updated.pixel_width
            or previous.downsample_mode != updated.downsample_mode
            or previous.input_mode != updated.input_mode
        )
        ramp_generation_changed = (
            previous.generated_shades != updated.generated_shades
            or previous.contrast_bias != updated.contrast_bias
        )
        auto_detect_changed = previous.auto_detect_count != updated.auto_detect_count
        palette_reduction_changed = (
            previous.palette_reduction_colors != updated.palette_reduction_colors
            or previous.quantizer != updated.quantizer
        )
        palette_adjustment_changed = (
            previous.palette_brightness != updated.palette_brightness
            or previous.palette_contrast != updated.palette_contrast
            or previous.palette_hue != updated.palette_hue
            or previous.palette_saturation != updated.palette_saturation
        )
        palette_apply_changed = (
            previous.palette_dither_mode != updated.palette_dither_mode
            or previous.output_mode != updated.output_mode
            or previous.dither_mode != updated.dither_mode
        )
        if downsample_changed:
            self._clear_palette_undo_state()
            self.prepared_input_cache = None
            self.prepared_input_cache_key = None
            message = message or "Downsample settings changed. Click Downsample to update the preview."
        elif ramp_generation_changed:
            self.process_status_var.set("Ramp settings changed. Select palette colours and click Ramp to append new ramps.")
            self._schedule_state_persist()
            self._refresh_action_states()
            return
        elif auto_detect_changed:
            self.process_status_var.set(f"Auto-detect count set to {updated.auto_detect_count}.")
            self._schedule_state_persist()
            self._refresh_action_states()
            return
        elif palette_reduction_changed:
            self.process_status_var.set("Palette reduction settings changed. Click Reduce Palette to rebuild the palette.")
            self._schedule_state_persist()
            self._refresh_action_states()
            return
        elif palette_adjustment_changed:
            self._clear_palette_undo_state()
            self._refresh_output_display_images()
            if self._current_output_result() is not None:
                if self._palette_adjustment_selection_indices():
                    self.process_status_var.set("Selected image colours updated.")
                else:
                    self.process_status_var.set("Image adjustment settings updated.")
            else:
                self.process_status_var.set("Image adjustment settings updated.")
            self._update_palette_adjustment_labels()
            self._update_scale_info()
            self._update_palette_strip()
            self.redraw_canvas()
            self._schedule_state_persist()
            self._refresh_action_states()
            return
        elif palette_apply_changed:
            self._clear_palette_undo_state()
            message = message or "Palette settings changed. Click Apply Palette to update the preview."
        self._mark_output_stale(message)
        self._update_palette_adjustment_labels()
        self._update_scale_info()
        self._update_palette_strip()
        self.redraw_canvas()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _mark_output_stale(self, message: str | None = None) -> None:
        if self.image_state == "processing":
            return
        if self._current_output_result() is not None:
            self.image_state = "processed_stale"
        elif getattr(self, "original_grid", None) is not None:
            self.image_state = "loaded_original"
        if message:
            self.process_status_var.set(message)

    def _build_pipeline_config(self, settings: PreviewSettings) -> PipelineConfig:
        palette_labels, _source = self._current_palette_source_labels()
        return PipelineConfig(
            pixel_width=settings.pixel_width,
            downsample_mode=settings.downsample_mode,
            colors=max(1, len(palette_labels) if palette_labels else settings.palette_reduction_colors),
            palette_strategy="override" if self._palette_is_override_mode() else "advanced",
            key_colors=(),
            generated_shades=settings.generated_shades,
            contrast_bias=settings.contrast_bias,
            palette_dither_mode=settings.palette_dither_mode,
            input_mode=settings.input_mode,
            output_mode=settings.output_mode,
            quantizer=settings.quantizer,
            dither_mode=settings.dither_mode,
        )

    def _current_quantizer_value(self) -> str:
        quantizer_var = getattr(self, "quantizer_var", None)
        if quantizer_var is not None:
            try:
                value = QUANTIZER_DISPLAY_TO_VALUE.get(quantizer_var.get(), "")
            except Exception:
                value = ""
            if value:
                return value
        session = getattr(self, "session", None)
        current = getattr(session, "current", None)
        if current is not None:
            return current.quantizer
        return QUANTIZER_OPTIONS[0][1]

    @staticmethod
    def _build_prepare_cache_key(settings: PreviewSettings) -> tuple[object, ...]:
        return (
            settings.pixel_width,
            settings.downsample_mode,
            settings.input_mode,
        )

    def _refresh_action_states(self) -> None:
        busy = self.image_state == "processing"
        has_image = self.original_grid is not None
        has_output = self._current_output_result() is not None
        has_downsample = self.prepared_input_cache is not None
        has_palette_source = self._has_palette_source()
        can_save = self.image_state == "processed_current" and has_output
        has_palette_selection = bool(self._palette_selection_indices)
        has_static_selection = getattr(self, "_image_selection", None) is not None
        has_floating_selection = getattr(self, "_floating_selection", None) is not None
        has_image_selection = has_static_selection or has_floating_selection
        has_selection_clipboard = getattr(self, "_selection_clipboard", None) is not None
        valid_palette_selection = [
            index for index in getattr(self, "_palette_selection_indices", set()) if 0 <= index < len(getattr(self, "_displayed_palette", []))
        ]
        has_single_palette_selection = len(valid_palette_selection) == 1
        adaptive_outline = self._outline_adaptive_enabled()
        can_merge_palette = has_palette_source and len(valid_palette_selection) >= 2 and not busy
        can_ramp_palette = has_palette_source and len(valid_palette_selection) >= 1 and not busy
        history = getattr(getattr(self, "session", None), "history", None)
        history_can_undo = getattr(history, "can_undo", None)
        history_can_redo = getattr(history, "can_redo", None)
        can_undo = (getattr(self, "_palette_undo_state", None) is not None) or (callable(history_can_undo) and history_can_undo())
        can_redo = (getattr(self, "_palette_redo_state", None) is not None) or (callable(history_can_redo) and history_can_redo())
        for widget_name, enabled in (
            ("downsample_button", has_image and not busy),
            ("generate_override_palette_button", has_downsample and not busy),
            ("reduce_palette_button", has_downsample and not busy and has_palette_source),
            ("add_palette_color_button", has_image and not busy),
            ("merge_palette_button", can_merge_palette),
            ("ramp_palette_button", can_ramp_palette),
            ("select_all_palette_button", has_palette_source and not busy),
            ("clear_palette_selection_button", has_palette_selection and not busy),
            ("invert_palette_selection_button", has_palette_source and not busy),
            ("remove_palette_color_button", has_palette_source and has_palette_selection and not busy),
        ):
            if widget_name in getattr(self, "_palette_action_button_assets", {}):
                self._set_palette_action_button_enabled(widget_name, enabled)
                continue
            widget = getattr(self, widget_name, None)
            if widget is not None and hasattr(widget, "configure"):
                widget.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        self._set_tool_button_enabled("palette_picker_button", has_output and not busy)
        self._set_tool_button_enabled("select_button", has_output and not busy)
        self._set_tool_button_enabled("polygon_lasso_button", has_output and not busy)
        self._set_tool_button_enabled("add_outline_button", has_output and not busy)
        self._set_tool_button_enabled("remove_outline_button", has_output and not busy)
        self._set_tool_button_enabled("blur_button", has_output and not busy)
        self._set_tool_button_enabled("sharpen_button", has_output and not busy)
        self._set_tool_button_enabled("flip_horizontal_button", has_output and not busy)
        self._set_tool_button_enabled("flip_vertical_button", has_output and not busy)
        self._set_tool_button_enabled("zoom_in_button", has_image and not busy)
        self._set_tool_button_enabled("zoom_out_button", has_image and not busy)
        self._set_tool_button_enabled("toolbar_new_button", True)
        self._set_tool_button_enabled("toolbar_open_button", True)
        self._set_tool_button_enabled("toolbar_save_button", can_save)
        self._set_tool_button_enabled("toolbar_cut_button", has_image_selection and not busy)
        self._set_tool_button_enabled("toolbar_copy_button", has_image_selection and not busy)
        self._set_tool_button_enabled("toolbar_paste_button", has_output and has_selection_clipboard and not busy)
        self._set_tool_button_enabled("toolbar_undo_button", can_undo and not busy)
        self._set_tool_button_enabled("toolbar_redo_button", can_redo and not busy)
        self._set_tool_button_enabled("toolbar_canvas_size_button", has_output and not busy)
        self._set_tool_button_enabled("toolbar_rotate_button", has_output and not busy)
        self._set_tool_button_enabled("toolbar_view_original_button", has_image and not busy)
        self._set_tool_button_enabled("toolbar_view_processed_button", has_output and not busy)
        self._set_tool_button_enabled("toolbar_indexed_color_button", has_output and not busy)
        self._set_tool_button_enabled("toolbar_preferences_button", not busy)
        self._set_toolbar_zoom_enabled(has_image and not busy)
        pixel_width_spinbox = getattr(self, "pixel_width_spinbox", None)
        if pixel_width_spinbox is not None and hasattr(pixel_width_spinbox, "configure"):
            pixel_width_spinbox.configure(state="normal" if has_image and not busy else "disabled")
        palette_reduction_spinbox = getattr(self, "palette_reduction_spinbox", None)
        if palette_reduction_spinbox is not None and hasattr(palette_reduction_spinbox, "configure"):
            palette_reduction_spinbox.configure(
                state="normal" if has_image and not busy and not is_structured_quantizer(self._current_quantizer_value()) else "disabled"
            )
        adjustment_state = tk.NORMAL if has_output and not busy else tk.DISABLED
        for control in getattr(self, "palette_adjustment_controls", []):
            control.configure(state=adjustment_state)
        sort_combobox = getattr(self, "palette_sort_combobox", None)
        if sort_combobox is not None:
            sort_combobox.configure(state="readonly" if has_palette_source and not busy else "disabled")
        file_menu = self._menu_items.get("file")
        if file_menu is not None:
            file_menu.entryconfigure("Save", state=tk.NORMAL if can_save else tk.DISABLED)
            file_menu.entryconfigure("Save As...", state=tk.NORMAL if can_save else tk.DISABLED)
            file_menu.entryconfigure("Canvas Size...", state=tk.NORMAL if has_output and not busy else tk.DISABLED)
        palette_menu = self._menu_items.get("palette")
        if palette_menu is not None:
            palette_menu.entryconfigure("Input Mode", state=tk.NORMAL if not busy else tk.DISABLED)
            palette_menu.entryconfigure("Output Mode", state=tk.NORMAL if not busy else tk.DISABLED)
            palette_menu.entryconfigure("Built-in Palettes", state=tk.NORMAL if not busy else tk.DISABLED)
            palette_menu.entryconfigure("Add Colour", state=tk.NORMAL if not busy else tk.DISABLED)
            palette_menu.entryconfigure(
                "Sort Current Palette",
                state=tk.NORMAL if self._has_palette_source() and not busy else tk.DISABLED,
            )
            palette_menu.entryconfigure("Load Palette...", state=tk.NORMAL if not busy else tk.DISABLED)
            palette_menu.entryconfigure(
                "Save Current Palette...",
                state=tk.NORMAL if self._has_palette_source() and not busy else tk.DISABLED,
            )
        edit_menu = self._menu_items.get("edit")
        if edit_menu is not None:
            edit_menu.entryconfigure("Cut", state=tk.NORMAL if has_image_selection and not busy else tk.DISABLED)
            edit_menu.entryconfigure("Copy", state=tk.NORMAL if has_image_selection and not busy else tk.DISABLED)
            edit_menu.entryconfigure("Paste", state=tk.NORMAL if has_output and has_selection_clipboard and not busy else tk.DISABLED)
            edit_menu.entryconfigure("Delete Selection", state=tk.NORMAL if has_image_selection and not busy else tk.DISABLED)
            edit_menu.entryconfigure(
                "Deselect",
                state=tk.NORMAL if (has_image_selection or bool(getattr(self, "_lasso_points", []))) and not busy else tk.DISABLED,
            )
            edit_menu.entryconfigure("Commit Selection", state=tk.NORMAL if has_floating_selection and not busy else tk.DISABLED)
        transform_menu = self._menu_items.get("transform")
        if transform_menu is not None:
            transform_menu.entryconfigure("Flip Horizontal", state=tk.NORMAL if has_output and not busy else tk.DISABLED)
            transform_menu.entryconfigure("Flip Vertical", state=tk.NORMAL if has_output and not busy else tk.DISABLED)
            transform_menu.entryconfigure("Rotate 90° CW", state=tk.NORMAL if has_output and not busy else tk.DISABLED)
            transform_menu.entryconfigure("Rotate 180°", state=tk.NORMAL if has_output and not busy else tk.DISABLED)
            transform_menu.entryconfigure("Rotate 90° CCW", state=tk.NORMAL if has_output and not busy else tk.DISABLED)
        if hasattr(self, "_menu_bar"):
            self._menu_bar.entryconfigure("Select", state=tk.NORMAL if has_palette_source and not busy else tk.DISABLED)
        palette_add_menu = self._menu_items.get("palette_add")
        if palette_add_menu is not None:
            palette_add_menu.entryconfigure("Pick From Original", state=tk.NORMAL if has_image and not busy else tk.DISABLED)
            palette_add_menu.entryconfigure("Enter Hex Code...", state=tk.NORMAL if not busy else tk.DISABLED)
        self._refresh_brush_control_states()
        self._refresh_outline_control_states()
        self._refresh_image_filter_control_states()
        self._refresh_tool_options_panel()
        self._refresh_tool_button_styles()

    def _refresh_tool_button_styles(self) -> None:
        tool_mode = self._canvas_tool_mode_value()
        view_var = getattr(self, "view_var", None)
        view_getter = getattr(view_var, "get", None)
        current_view = view_getter() if callable(view_getter) else None
        active_states = {
            "select_button": tool_mode == CANVAS_TOOL_MODE_SELECT,
            "polygon_lasso_button": tool_mode == CANVAS_TOOL_MODE_POLYGON_LASSO,
            "bucket_button": tool_mode == CANVAS_TOOL_MODE_BUCKET,
            "pencil_button": tool_mode == CANVAS_TOOL_MODE_PENCIL,
            "eraser_button": tool_mode == CANVAS_TOOL_MODE_ERASER,
            "circle_button": tool_mode == CANVAS_TOOL_MODE_ELLIPSE,
            "square_button": tool_mode == CANVAS_TOOL_MODE_RECTANGLE,
            "line_button": tool_mode == CANVAS_TOOL_MODE_LINE,
            "gradient_button": tool_mode == CANVAS_TOOL_MODE_GRADIENT,
            "blur_button": tool_mode == CANVAS_TOOL_MODE_BLUR,
            "sharpen_button": tool_mode == CANVAS_TOOL_MODE_SHARPEN,
            "palette_picker_button": tool_mode == CANVAS_TOOL_MODE_ACTIVE_COLOR_PICK,
            "add_outline_button": tool_mode == CANVAS_TOOL_MODE_ADD_OUTLINE,
            "remove_outline_button": tool_mode == CANVAS_TOOL_MODE_REMOVE_OUTLINE,
            "toolbar_rotate_button": tool_mode == CANVAS_TOOL_MODE_ROTATE,
            "toolbar_view_original_button": current_view == "original",
            "toolbar_view_processed_button": current_view == "processed",
        }
        enabled_map = getattr(self, "_tool_button_enabled", {})
        for widget_name, active in active_states.items():
            widget = getattr(self, widget_name, None)
            enabled = enabled_map.get(widget_name, True)
            border_frame = getattr(self, "_tool_button_frames", {}).get(widget_name)
            if border_frame is not None and hasattr(border_frame, "configure"):
                border_frame.configure(bg=APP_ACCENT if active and enabled else APP_BORDER)
            if widget is not None and hasattr(widget, "configure"):
                if active and enabled:
                    widget.configure(style="ToolButtonActive.TButton")
                elif enabled:
                    widget.configure(style="ToolButton.TButton")
                else:
                    widget.configure(style="ToolButtonDisabled.TButton")

    def _image_x_to_canvas(self, value: int, image_width: int) -> int:
        if self._display_context is None:
            return 0
        return self._display_context.image_left + round((value / max(image_width, 1)) * self._display_context.display_width)

    def _image_y_to_canvas(self, value: int, image_height: int) -> int:
        if self._display_context is None:
            return 0
        return self._display_context.image_top + round((value / max(image_height, 1)) * self._display_context.display_height)

    def _on_overlay_changed(self) -> None:
        self.redraw_canvas()
        self._schedule_state_persist()

    def _on_outline_pixel_perfect_changed(self) -> None:
        self._refresh_tool_options_panel()
        self._schedule_state_persist()

    def _on_outline_colour_mode_changed(self) -> None:
        mode = self._outline_colour_mode()
        if getattr(self, "outline_colour_mode_var", None) is not None and self.outline_colour_mode_var.get() != mode:
            self.outline_colour_mode_var.set(mode)
        display_var = getattr(self, "outline_colour_mode_display_var", None)
        if display_var is not None and hasattr(display_var, "set"):
            display_var.set(OUTLINE_COLOUR_MODE_LABELS[mode])
        self._refresh_outline_control_states()
        self._refresh_tool_options_panel()
        self._schedule_state_persist()
        self._refresh_action_states()

    def _on_outline_adaptive_darken_changed(self, _event: tk.Event | None = None) -> None:
        percent = self._outline_adaptive_darken_percent()
        if getattr(self, "outline_adaptive_darken_percent_var", None) is not None and self.outline_adaptive_darken_percent_var.get() != percent:
            self.outline_adaptive_darken_percent_var.set(percent)
        self._schedule_state_persist()

    def _on_outline_add_generated_colours_changed(self) -> None:
        self._schedule_state_persist()

    def _on_outline_remove_brightness_threshold_enabled_changed(self) -> None:
        self._refresh_outline_control_states()
        self._refresh_tool_options_panel()
        self._schedule_state_persist()

    def _on_outline_remove_brightness_threshold_percent_changed(self, _event: tk.Event | None = None) -> None:
        threshold = self._outline_remove_brightness_threshold_percent()
        variable = getattr(self, "outline_remove_brightness_threshold_percent_var", None)
        getter = getattr(variable, "get", None)
        setter = getattr(variable, "set", None)
        if variable is not None and callable(getter) and callable(setter) and getter() != threshold:
            setter(threshold)
        self._schedule_state_persist()

    def _on_outline_remove_brightness_threshold_direction_changed(self) -> None:
        direction = self._outline_remove_brightness_threshold_direction()
        variable = getattr(self, "outline_remove_brightness_threshold_direction_var", None)
        getter = getattr(variable, "get", None)
        setter = getattr(variable, "set", None)
        if variable is not None and callable(getter) and callable(setter) and getter() != direction:
            setter(direction)
        display_var = getattr(self, "outline_remove_brightness_direction_display_var", None)
        if display_var is not None and hasattr(display_var, "set"):
            display_var.set(OUTLINE_REMOVE_DIRECTION_LABELS[direction])
        self._refresh_tool_options_panel()
        self._schedule_state_persist()

    def _schedule_state_persist(self) -> None:
        if self._persist_after_id is not None:
            self.root.after_cancel(self._persist_after_id)
        self._persist_after_id = self.root.after(200, self._persist_state)

    def _persist_state(self) -> None:
        self._persist_after_id = None
        settings_data = serialize_settings(self.session.current)
        for field in ("palette_brightness", "palette_contrast", "palette_hue", "palette_saturation"):
            settings_data.pop(field, None)
        save_app_state(
            {
                "settings": settings_data,
                "last_output_path": self.last_output_path,
                "last_successful_process_snapshot": self.last_successful_process_snapshot,
                "zoom": self.zoom,
                "selection_threshold": self._selection_threshold_percent(),
                "checkerboard": self.checkerboard_var.get(),
                "overlay_grid": self._overlay_grid_enabled(),
                "outline_pixel_perfect": self._outline_pixel_perfect_enabled(),
                "outline_colour_mode": self._outline_colour_mode(),
                "outline_adaptive_darken_percent": self._outline_adaptive_darken_percent(),
                "outline_add_generated_colours": self._outline_add_generated_colours_enabled(),
                "outline_remove_brightness_threshold_enabled": self._outline_remove_brightness_threshold_enabled(),
                "outline_remove_brightness_threshold_percent": self._outline_remove_brightness_threshold_percent(),
                "outline_remove_brightness_threshold_direction": self._outline_remove_brightness_threshold_direction(),
                "brush_width": self._brush_width(),
                "brush_shape": self._brush_shape(),
                "blur_strength": self._image_filter_strength(CANVAS_TOOL_MODE_BLUR),
                "sharpen_strength": self._image_filter_strength(CANVAS_TOOL_MODE_SHARPEN),
                "view_mode": self.view_var.get(),
                "right_mouse_action": self._mouse_button_action(CANVAS_MOUSE_BUTTON_RIGHT),
                "middle_mouse_action": self._mouse_button_action(CANVAS_MOUSE_BUTTON_MIDDLE),
                "primary_color_label": self._slot_color_label(ACTIVE_COLOR_SLOT_PRIMARY),
                "secondary_color_label": self._slot_color_label(ACTIVE_COLOR_SLOT_SECONDARY),
                "transparent_color_slot": self._transparent_color_slot_value(),
                "active_color_slot": self._active_color_slot_value(),
                "active_palette_source": self.active_palette_source,
                "active_palette_path": self.active_palette_path,
                "recent_files": self.recent_files,
                "openai_api_key": self.openai_api_key,
                "gemini_api_key": self.gemini_api_key,
                "image_generation_model": self.image_generation_model,
            }
        )

    def _on_close(self) -> None:
        if self._persist_after_id is not None:
            self.root.after_cancel(self._persist_after_id)
        self._persist_state()
        self.root.destroy()

    @staticmethod
    def _normalize_recent_files(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str)]


def parse_gui_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--open", dest="open_path")
    return parser.parse_args(list(sys.argv[1:] if argv is None else argv))


def schedule_initial_open(app: PixelFixGui, open_path_value: str | None) -> None:
    if not open_path_value:
        return
    path = Path(open_path_value)

    def _open_initial() -> None:
        if not path.exists():
            messagebox.showwarning("Missing file", f"Startup file not found:\n{path}")
            return
        app._open_image_path(path)

    app.root.after_idle(_open_initial)


def main() -> int:
    args = parse_gui_args()
    root = tk.Tk()
    app = PixelFixGui(root)
    schedule_initial_open(app, args.open_path)
    root.mainloop()
    return 0
