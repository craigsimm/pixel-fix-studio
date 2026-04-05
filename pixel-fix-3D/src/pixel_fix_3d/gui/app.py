from __future__ import annotations

import math
import shutil
import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import numpy as np
from PIL import Image, ImageTk

from ..glb_export import GlbExportError, export_glb
from ..project_io import Pfx3dError, Pfx3dProject, extract_face_textures, load_pfx3d, save_pfx3d
from ..pixel_fix_2d_bridge import (
    launch_pixel_fix_2d,
    locate_pixel_fix_2d,
    read_pixel_fix_2d_session,
    send_open_path_to_pixel_fix_2d,
)
from ..renderer import BACKGROUND_RGB, RenderOptions, SoftwareRenderer
from ..shapes import SHAPE_PRESETS_BY_KEY, ShapePreset, recommended_texture_size
from ..state import (
    DEFAULT_CAMERA_DISTANCE,
    EditorState,
    assign_texture_to_faces,
    assign_texture_to_selected_face,
    clear_selection,
    clear_selected_face_texture,
    clear_shape_textures,
    reset_camera,
    rotate_camera,
    select_face,
    set_shape,
    snap_camera_view,
    toggle_face_in_selection,
    toggle_select_all_faces,
    zoom_camera,
)
from ..textures import TextureEntry, build_thumbnail, load_texture_bytes, load_texture_library
from .persist import AppPreferences, app_preferences_to_dict, load_app_preferences, load_app_state, save_app_state
from .theme import (
    APP_ACCENT,
    APP_BG,
    APP_BORDER,
    APP_NAME,
    APP_MUTED_TEXT,
    APP_PANEL_BG,
    APP_SURFACE_BG,
    APP_TEXT,
    HEADER_FONT_FAMILY,
    HEADER_FONT_SIZE,
    PIXEL_FONT_FAMILY,
    UI_FONT_SIZE,
    configure_ttk_theme,
    load_font_family,
)
from .tooltips import Tooltip

WINDOW_WIDTH = 1480
WINDOW_HEIGHT = 900
VIEWPORT_WIDTH = 272
VIEWPORT_HEIGHT = 204
EVENT_STATE_SHIFT_MASK = 0x0001
TEXTURE_THUMBNAIL_SIZE = 48
AUTOROTATE_INTERVAL_MS = 50
AUTOROTATE_YAW_STEP = 0.1
TOOL_BUTTON_WIDTH = 40
TOOL_BUTTON_HEIGHT = 40
TOOLBAR_ZOOM_WIDTH = 78
PREFERENCES_WINDOW_WIDTH = 620
PREFERENCES_WINDOW_HEIGHT = 480
PREFERENCES_NAV_WIDTH = 172
PREFERENCES_PAGE_GENERAL = "General"
PREFERENCES_PAGE_VIEWPORT = "Viewport"
PREFERENCES_PAGE_BACKGROUND = "Background"
PREFERENCES_PAGE_ORDER = (
    PREFERENCES_PAGE_GENERAL,
    PREFERENCES_PAGE_VIEWPORT,
    PREFERENCES_PAGE_BACKGROUND,
)
LIGHTING_INTENSITY_OPTIONS = (
    ("25%", 0.25),
    ("50%", 0.5),
    ("75%", 0.75),
    ("100%", 1.0),
    ("125%", 1.25),
)
AUTOROTATE_SPEED_OPTIONS = (
    ("25%", 0.25),
    ("50%", 0.5),
    ("75%", 0.75),
    ("100%", 1.0),
    ("125%", 1.25),
)
SUPPORTED_TEXTURE_SUFFIXES = (".png",)

MODEL_BUTTON_SPECS = (
    ("cube", "Cube", "icon_cube.png"),
    ("box", "Box", "icon_box.png"),
    ("tall_box", "Tall Box", "icon_tall_box.png"),
    ("plane_2d", "2D Plane", "icon_plane.png"),
    ("wedge", "Wedge", "icon_wedge.png"),
    ("ramp", "Ramp", "icon_ramp.png"),
    ("cylinder", "8-Sided Cylinder", "icon_8_sided_cylinder.png"),
    ("roof", "Roof", "icon_roof.png"),
    ("table", "Table", "icon_table.png"),
    ("chair", "Chair", "icon_chair.png"),
    ("car", "Car", "icon_car.png"),
)

VIEW_BUTTON_SPECS = (
    ("left", "Left View", "icon_view_left.png"),
    ("right", "Right View", "icon_view_right.png"),
    ("top", "Top View", "icon_view_top.png"),
    ("bottom", "Bottom View", "icon_view_bottom.png"),
    ("backleft", "Back Left View", "icon_view_backleft.png"),
    ("backright", "Back Right View", "icon_view_backright.png"),
)

VIEW_LABELS = {
    "iso": "Iso",
    "front": "Front",
    "back": "Back",
    "left": "Left",
    "right": "Right",
    "top": "Top",
    "bottom": "Bottom",
    "backleft": "Back Left",
    "backright": "Back Right",
}


@dataclass(frozen=True)
class PreferencesDialogState:
    preferences: AppPreferences


def camera_distance_to_zoom_percent(distance: float) -> int:
    safe_distance = max(distance, 0.001)
    percent = (DEFAULT_CAMERA_DISTANCE / safe_distance) * 100.0
    return max(5, int(5 * math.floor((percent / 5.0) + 0.5)))


class PixelFixStudio3DApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.renderer = SoftwareRenderer(width=VIEWPORT_WIDTH, height=VIEWPORT_HEIGHT)
        persisted = load_app_state()
        self.preferences = load_app_preferences(persisted)
        initial_shape_key = str(persisted.get("last_shape_key", "cube"))
        if initial_shape_key not in SHAPE_PRESETS_BY_KEY:
            initial_shape_key = "cube"
        initial_state = EditorState(face_texture_assignments=self._default_face_texture_assignments())
        self.editor_state = set_shape(initial_state, initial_shape_key, SHAPE_PRESETS_BY_KEY[initial_shape_key].label)

        self.texture_entries: list[TextureEntry] = []
        self.texture_lookup: dict[str, TextureEntry] = {}
        self._builtin_texture_entries: list[TextureEntry] = []
        self.texture_button_images: dict[str, ImageTk.PhotoImage] = {}
        self.texture_buttons: dict[str, ttk.Button] = {}
        self.shape_buttons: dict[str, ttk.Button] = {}
        self.view_buttons: dict[str, ttk.Button] = {}
        self._tool_button_assets: dict[str, str] = {}
        self._tool_button_icons: dict[tuple[str, bool], ImageTk.PhotoImage] = {}
        self._tool_button_widgets: dict[str, ttk.Button] = {}
        self._tool_button_frames: dict[str, tk.Frame] = {}
        self._tooltips: list[Tooltip] = []
        self.toolbar_zoom_var = tk.StringVar(value="")
        self.viewport_photo: ImageTk.PhotoImage | None = None
        self.last_render_face_ids = None
        self.viewport_display_rect = (0, 0, 0, 0)
        self._viewport_background_cache_key: tuple[bool, str] | None = None
        self._viewport_background_cache_rgb: np.ndarray | None = None
        self._autorotate_active = False
        self._autorotate_job: str | None = None
        self._autorotate_restore_camera = None
        self._autorotate_restore_face_id: int | None = None
        self._autorotate_restore_face_ids: tuple[int, ...] = ()
        self._texture_context_menu: tk.Menu | None = None
        self._preferences_window: tk.Toplevel | None = None
        self._preferences_nav_buttons: dict[str, ttk.Button] = {}
        self._preferences_pages: dict[str, ttk.Frame] = {}
        self._preferences_selected_page = PREFERENCES_PAGE_GENERAL
        self._preferences_original_state: PreferencesDialogState | None = None
        self._preferences_show_floor_grid_var: tk.BooleanVar | None = None
        self._preferences_show_face_highlight_var: tk.BooleanVar | None = None
        self._preferences_lighting_intensity_var: tk.StringVar | None = None
        self._preferences_autorotate_speed_var: tk.StringVar | None = None
        self._preferences_background_enabled_var: tk.BooleanVar | None = None
        self._preferences_background_image_path_var: tk.StringVar | None = None
        self._preferences_background_path_entry: ttk.Entry | None = None
        self._preferences_background_browse_button: ttk.Button | None = None
        self._preferences_background_clear_button: ttk.Button | None = None

        self._drag_origin: tuple[int, int] | None = None
        self._drag_last: tuple[int, int] | None = None
        self._dragging = False

        self._load_builtin_textures()
        self._configure_window_icon()
        self._configure_theme()
        self._build_ui()
        self.root.bind("<Control-a>", self._on_select_all_shortcut)
        self.root.bind("<Control-A>", self._on_select_all_shortcut)
        self._restore_window_geometry(persisted.get("window_geometry"))
        self._update_interaction_states()
        self._refresh_texture_buttons()
        self._refresh_status()
        self.root.after_idle(self._render_viewport)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _resource_path(self, relative_path: str) -> Path:
        if hasattr(sys, "_MEIPASS"):
            base = Path(getattr(sys, "_MEIPASS")) / "pixel_fix_3d" / "resources"
        else:
            base = Path(__file__).resolve().parents[1] / "resources"
        return base / relative_path

    def _data_path(self, relative_path: str) -> Path:
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).resolve().parent / "data"
        else:
            base = Path(__file__).resolve().parents[3] / "data"
        path = base / relative_path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _asset_path(self, asset_name: str) -> Path:
        packaged = self._resource_path(f"assets/{asset_name}")
        if not hasattr(sys, "_MEIPASS"):
            project_assets = Path(__file__).resolve().parents[3] / "assets" / asset_name
            if project_assets.is_file():
                return project_assets
        return packaged

    def _default_texture_directory(self) -> Path:
        data_textures = self._data_path("textures")
        resource_textures = self._resource_path("textures")
        needs_seed = not any(
            candidate.is_file() and candidate.suffix.lower() in SUPPORTED_TEXTURE_SUFFIXES
            for candidate in data_textures.iterdir()
        )
        if needs_seed and resource_textures.exists():
            for texture_path in resource_textures.glob("*.png"):
                destination = data_textures / texture_path.name
                if not destination.exists():
                    shutil.copy2(texture_path, destination)
        return data_textures

    def _configure_window_icon(self) -> None:
        ico_path = self._resource_path("icons/pixel-fix-studio-3d.ico")
        png_path = self._resource_path("icons/pixel-fix-3D-32px.png")
        if ico_path.exists():
            try:
                self.root.iconbitmap(default=str(ico_path))
            except tk.TclError:
                pass
        if png_path.exists():
            try:
                self.root.iconphoto(True, tk.PhotoImage(file=str(png_path)))
            except tk.TclError:
                pass

    def _default_texture_entries(self) -> list[TextureEntry]:
        startup_texture_paths: list[Path] = []
        startup_texture_dir = self._default_texture_directory()
        if startup_texture_dir.exists():
            for candidate in sorted(startup_texture_dir.iterdir(), key=lambda path: path.name.lower()):
                if not candidate.is_file() or candidate.suffix.lower() not in SUPPORTED_TEXTURE_SUFFIXES:
                    continue
                startup_texture_paths.append(candidate)
        startup_entries, _errors = load_texture_library(startup_texture_paths)
        return startup_entries

    def _load_builtin_textures(self) -> None:
        self._builtin_texture_entries = self._default_texture_entries()
        self.texture_entries = list(self._builtin_texture_entries)
        self.texture_lookup = {entry.texture_id: entry for entry in self._builtin_texture_entries}

    def _default_face_texture_assignments(self) -> dict[str, dict[int, str]]:
        return {}

    def _reset_texture_library(self, extra_entries: list[TextureEntry] | None = None) -> None:
        self.texture_entries = list(self._builtin_texture_entries)
        self.texture_lookup = {entry.texture_id: entry for entry in self._builtin_texture_entries}
        for entry in extra_entries or []:
            if entry.texture_id in self.texture_lookup:
                continue
            self.texture_entries.append(entry)
            self.texture_lookup[entry.texture_id] = entry

    def _configure_theme(self) -> None:
        ui_font_family = load_font_family(self.root, self._resource_path("fonts/pixelmix.ttf"), PIXEL_FONT_FAMILY)
        header_font_family = load_font_family(self.root, self._resource_path("fonts/pixelmix.ttf"), HEADER_FONT_FAMILY)
        self.ui_font = tkfont.Font(root=self.root, name="PixelFixStudio3DBaseFont", family=ui_font_family, size=UI_FONT_SIZE)
        self.header_font = tkfont.Font(
            root=self.root,
            name="PixelFixStudio3DHeaderFont",
            family=header_font_family,
            size=HEADER_FONT_SIZE,
        )
        configure_ttk_theme(self.root, self.ui_font, self.header_font)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        self._build_top_toolbar(outer)

        body = ttk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True)

        self.left_panel = ttk.LabelFrame(body, text="MODELS")
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.center_panel = ttk.LabelFrame(body, text="VIEWPORT")
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        self.right_panel = ttk.LabelFrame(body, text="TEXTURES")
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

        self.status_bar = ttk.Frame(outer, style="Status.TFrame", padding=(8, 6))
        self.status_bar.pack(fill=tk.X, pady=(8, 0))
        self.status_message_var = tk.StringVar(value=self.editor_state.status_message)
        self.status_detail_var = tk.StringVar()
        ttk.Label(self.status_bar, textvariable=self.status_message_var, style="Status.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(self.status_bar, textvariable=self.status_detail_var, style="StatusMuted.TLabel").pack(side=tk.RIGHT)

    def _build_top_toolbar(self, parent: ttk.Frame) -> None:
        self.top_toolbar = ttk.Frame(parent)
        self.top_toolbar.pack(fill=tk.X, pady=(0, 8))

        self.top_toolbar_row = ttk.Frame(self.top_toolbar)
        self.top_toolbar_row.pack(anchor=tk.W)

        toolbar_buttons = (
            ("toolbar_new_button", "icon_new.png", lambda: self._show_toolbar_placeholder_message("New"), "New"),
            ("toolbar_open_button", "icon_open.png", self._open_project, "Open"),
            ("toolbar_save_button", "icon_save.png", self._save_project, "Save"),
            ("toolbar_settings_button", "icon_settings.png", self.open_preferences_window, "Settings"),
        )
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

        zoom_shell = tk.Frame(
            self.top_toolbar_row,
            width=TOOLBAR_ZOOM_WIDTH,
            height=TOOL_BUTTON_HEIGHT,
            bg=APP_BORDER,
            bd=0,
            highlightthickness=0,
        )
        zoom_shell.pack(side=tk.LEFT, padx=(8, 0))
        zoom_shell.pack_propagate(False)
        self.toolbar_zoom_label = tk.Label(
            zoom_shell,
            textvariable=self.toolbar_zoom_var,
            justify=tk.CENTER,
            background=APP_SURFACE_BG,
            foreground=APP_TEXT,
            font=self.ui_font,
        )
        self.toolbar_zoom_label.place(x=1, y=1, width=TOOLBAR_ZOOM_WIDTH - 2, height=TOOL_BUTTON_HEIGHT - 2)
        self._tooltips.append(Tooltip(self.toolbar_zoom_label, "Zoom"))

    def _build_left_panel(self) -> None:
        panel = ttk.Frame(self.left_panel, padding=8)
        panel.pack(fill=tk.Y, expand=True)

        ttk.Label(panel, text="PRESET MODELS", style="SectionTitle.TLabel").pack(anchor=tk.W)
        model_grid = ttk.Frame(panel)
        model_grid.pack(anchor=tk.W, pady=(4, 0))
        for index, (shape_key, tooltip_text, asset_name) in enumerate(MODEL_BUTTON_SPECS):
            cell, button = self._create_tool_button(
                f"shape_{shape_key}_button",
                model_grid,
                asset_name,
                lambda value=shape_key: self._set_shape(value),
                tooltip_text,
            )
            cell.grid(row=index // 2, column=index % 2, padx=(0, 4 if index % 2 == 0 else 0), pady=(0, 4))
            model_grid.grid_columnconfigure(index % 2, minsize=TOOL_BUTTON_WIDTH)
            self.shape_buttons[shape_key] = button

        ttk.Label(panel, text="CONTROLS", style="SectionTitle.TLabel").pack(anchor=tk.W, pady=(12, 4))
        self.reset_camera_button = ttk.Button(panel, text="Reset Camera", command=self._reset_camera)
        self.reset_camera_button.pack(fill=tk.X, pady=(0, 4))
        self.clear_selected_face_button = ttk.Button(panel, text="Clear Selected Face", command=self._clear_selected_face_texture)
        self.clear_selected_face_button.pack(fill=tk.X, pady=(0, 4))
        self.clear_shape_textures_button = ttk.Button(panel, text="Clear Shape Textures", command=self._clear_shape_textures)
        self.clear_shape_textures_button.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(panel, text="VIEW", style="SectionTitle.TLabel").pack(anchor=tk.W, pady=(12, 4))
        view_grid = ttk.Frame(panel)
        view_grid.pack(anchor=tk.W)
        for index, (view_key, tooltip_text, asset_name) in enumerate(VIEW_BUTTON_SPECS):
            cell, button = self._create_tool_button(
                f"view_{view_key}_button",
                view_grid,
                asset_name,
                lambda value=view_key: self._snap_view(value),
                tooltip_text,
            )
            cell.grid(row=index // 2, column=index % 2, padx=(0, 4 if index % 2 == 0 else 0), pady=(0, 4))
            view_grid.grid_columnconfigure(index % 2, minsize=TOOL_BUTTON_WIDTH)
            self.view_buttons[view_key] = button

        rotate_row = ttk.Frame(panel)
        rotate_row.pack(anchor=tk.W, pady=(4, 0))
        rotate_cell, self.rotate_view_button = self._create_tool_button(
            "rotate_view_button",
            rotate_row,
            "icon_rotate.png",
            self._toggle_rotating_view,
            "Rotate View",
        )
        rotate_cell.pack(side=tk.LEFT)

        ttk.Label(panel, text="VIEWPORT", style="SectionTitle.TLabel").pack(anchor=tk.W, pady=(12, 4))
        ttk.Label(
            panel,
            text="Left drag: orbit\nWheel: zoom\nClick: select face\nRotate View: 360 preview lock",
            style="Muted.TLabel",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _build_center_panel(self) -> None:
        panel = ttk.Frame(self.center_panel, padding=8)
        panel.pack(fill=tk.BOTH, expand=True)
        self.viewport_canvas = tk.Canvas(
            panel,
            background=APP_PANEL_BG,
            bd=0,
            highlightthickness=0,
        )
        self.viewport_canvas.pack(fill=tk.BOTH, expand=True)
        self.viewport_canvas.bind("<Configure>", lambda _event: self._render_viewport())
        self.viewport_canvas.bind("<ButtonPress-1>", self._on_viewport_press)
        self.viewport_canvas.bind("<B1-Motion>", self._on_viewport_drag)
        self.viewport_canvas.bind("<ButtonRelease-1>", self._on_viewport_release)
        self.viewport_canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.viewport_canvas.bind("<Button-4>", lambda _event: self._apply_zoom(-0.25))
        self.viewport_canvas.bind("<Button-5>", lambda _event: self._apply_zoom(0.25))

    def _build_right_panel(self) -> None:
        panel = ttk.Frame(self.right_panel, padding=8)
        panel.pack(fill=tk.BOTH, expand=True)

        self.face_summary_var = tk.StringVar(value="No face selected.")
        self.texture_summary_var = tk.StringVar(value="No texture assigned.")
        ttk.Label(panel, textvariable=self.face_summary_var, style="SectionTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(panel, textvariable=self.texture_summary_var, style="Muted.TLabel").pack(anchor=tk.W, pady=(2, 8))
        self.load_textures_button = ttk.Button(panel, text="Load Texture...", command=self._load_textures)
        self.load_textures_button.pack(fill=tk.X)
        self.extract_textures_button = ttk.Button(panel, text="Extract Textures...", command=self._extract_textures)
        self.extract_textures_button.pack(fill=tk.X, pady=(4, 0))
        self.export_glb_button = ttk.Button(panel, text="Export GLB...", command=self._export_glb)
        self.export_glb_button.pack(fill=tk.X, pady=(4, 0))

        texture_scroll_shell = ttk.Frame(panel)
        texture_scroll_shell.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.texture_canvas = tk.Canvas(texture_scroll_shell, background=APP_BG, bd=0, highlightthickness=0, yscrollincrement=12)
        self.texture_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(texture_scroll_shell, orient=tk.VERTICAL, command=self.texture_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.texture_canvas.configure(yscrollcommand=scrollbar.set)

        self.texture_inner = ttk.Frame(self.texture_canvas)
        self.texture_canvas_window = self.texture_canvas.create_window((0, 0), window=self.texture_inner, anchor=tk.NW)
        self.texture_inner.bind("<Configure>", self._on_texture_frame_configure)
        self.texture_canvas.bind("<Configure>", self._on_texture_canvas_configure)

    def _on_texture_frame_configure(self, _event: tk.Event) -> None:
        self.texture_canvas.configure(scrollregion=self.texture_canvas.bbox("all"))

    def _on_texture_canvas_configure(self, event: tk.Event) -> None:
        self.texture_canvas.itemconfigure(self.texture_canvas_window, width=event.width)

    def _shape(self) -> ShapePreset:
        return SHAPE_PRESETS_BY_KEY[self.editor_state.shape_key]

    def _face_label(self, face_id: int | None) -> str | None:
        if face_id is None:
            return None
        face = self._shape().face_by_id(face_id)
        return face.label if face is not None else None

    def _face_texture_target(self, face_id: int | None) -> str | None:
        if face_id is None:
            return None
        face = self._shape().face_by_id(face_id)
        if face is None:
            return None
        width, height = recommended_texture_size(face)
        return f"{width}x{height}"

    def _all_face_ids(self) -> tuple[int, ...]:
        return tuple(face.face_id for face in self._shape().face_groups)

    def _transient_texture_entries(self, *, exclude_texture_ids: set[str] | None = None) -> list[TextureEntry]:
        excluded = exclude_texture_ids or set()
        return [
            entry
            for entry in self.texture_entries
            if entry.path is None and entry.texture_id not in excluded
        ]

    def _reload_texture_library(self, *, exclude_transient_ids: set[str] | None = None) -> None:
        self._builtin_texture_entries = self._default_texture_entries()
        self._reset_texture_library(self._transient_texture_entries(exclude_texture_ids=exclude_transient_ids))

    def _next_available_texture_path(self, directory: Path, desired_name: str) -> Path:
        base_name = Path(desired_name).name or "texture.png"
        stem = Path(base_name).stem.strip() or "texture"
        candidate = directory / f"{stem}.png"
        if not candidate.exists():
            return candidate
        suffix_index = 1
        while True:
            candidate = directory / f"{stem} ({suffix_index}).png"
            if not candidate.exists():
                return candidate
            suffix_index += 1

    def _replace_texture_assignments(self, old_texture_id: str, new_texture_id: str | None) -> int:
        changed_count = 0
        assignments: dict[str, dict[int, str]] = {}
        for shape_key, shape_assignments in self.editor_state.face_texture_assignments.items():
            updated_shape: dict[int, str] = {}
            for face_id, texture_id in shape_assignments.items():
                if texture_id == old_texture_id:
                    changed_count += 1
                    if new_texture_id is not None:
                        updated_shape[face_id] = new_texture_id
                else:
                    updated_shape[face_id] = texture_id
            if updated_shape:
                assignments[shape_key] = updated_shape
        if changed_count:
            self.editor_state = replace(self.editor_state, face_texture_assignments=assignments)
        return changed_count

    def _ensure_file_backed_texture_entry(self, texture_id: str) -> TextureEntry | None:
        entry = self.texture_lookup.get(texture_id)
        if entry is None:
            return None
        if entry.path is not None and entry.path.exists():
            return entry
        target_dir = self._default_texture_directory()
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._next_available_texture_path(target_dir, entry.name)
        entry.image.save(target_path, format="PNG")
        self._reload_texture_library(exclude_transient_ids={texture_id})
        new_entry = self.texture_lookup.get(str(target_path.resolve()).lower())
        if new_entry is None:
            return None
        self._replace_texture_assignments(texture_id, new_entry.texture_id)
        return new_entry

    def _apply_texture_to_selected_faces(self, texture_id: str) -> None:
        if self._autorotate_active:
            return
        texture = self.texture_lookup.get(texture_id)
        if texture is None:
            return
        self.editor_state = assign_texture_to_faces(
            self.editor_state,
            texture.texture_id,
            texture.name,
            self.editor_state.selected_face_ids,
        )
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._render_viewport()

    def _can_open_texture_in_pixel_fix_2d(self) -> bool:
        return read_pixel_fix_2d_session() is not None or locate_pixel_fix_2d() is not None

    def _edit_texture_in_pixel_fix_2d(self, texture_id: str) -> None:
        if self._autorotate_active:
            return
        entry = self._ensure_file_backed_texture_entry(texture_id)
        if entry is None or entry.path is None:
            self.editor_state = replace(self.editor_state, status_message="Unable to prepare that texture for editing.")
            self._refresh_status()
            return
        if send_open_path_to_pixel_fix_2d(entry.path):
            self.editor_state = replace(self.editor_state, status_message=f"Sent {entry.name} to Pixel-Fix 2D.")
        elif launch_pixel_fix_2d(entry.path):
            self.editor_state = replace(self.editor_state, status_message=f"Opened {entry.name} in Pixel-Fix 2D.")
        else:
            self.editor_state = replace(self.editor_state, status_message="Pixel-Fix 2D is not installed.")
        self._refresh_texture_buttons()
        self._refresh_status()

    def _duplicate_texture_entry(self, texture_id: str) -> None:
        if self._autorotate_active:
            return
        entry = self._ensure_file_backed_texture_entry(texture_id)
        if entry is None or entry.path is None:
            self.editor_state = replace(self.editor_state, status_message="Unable to duplicate that texture.")
            self._refresh_status()
            return
        target_path = self._next_available_texture_path(self._default_texture_directory(), entry.path.name)
        try:
            shutil.copy2(entry.path, target_path)
        except OSError as exc:
            self.editor_state = replace(self.editor_state, status_message=f"Duplicate failed: {exc}")
        else:
            self._reload_texture_library()
            self.editor_state = replace(
                self.editor_state,
                status_message=f"Duplicated {entry.name} as {target_path.name}.",
            )
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()

    def _rename_texture_entry(self, texture_id: str) -> None:
        if self._autorotate_active:
            return
        entry = self._ensure_file_backed_texture_entry(texture_id)
        if entry is None or entry.path is None:
            self.editor_state = replace(self.editor_state, status_message="Unable to rename that texture.")
            self._refresh_status()
            return
        new_stem = simpledialog.askstring(
            "Rename Texture",
            "Enter a new texture name:",
            initialvalue=entry.path.stem,
            parent=self.root,
        )
        if new_stem is None:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            self.editor_state = replace(self.editor_state, status_message="Texture names cannot be empty.")
            self._refresh_status()
            return
        if any(character in new_stem for character in '<>:"/\\\\|?*'):
            self.editor_state = replace(self.editor_state, status_message="Texture names cannot include invalid filename characters.")
            self._refresh_status()
            return
        target_path = entry.path.with_name(f"{new_stem}.png")
        if target_path.resolve() == entry.path.resolve():
            return
        if target_path.exists():
            self.editor_state = replace(self.editor_state, status_message=f"{target_path.name} already exists.")
            self._refresh_status()
            return
        try:
            entry.path.rename(target_path)
        except OSError as exc:
            self.editor_state = replace(self.editor_state, status_message=f"Rename failed: {exc}")
        else:
            self._replace_texture_assignments(entry.texture_id, str(target_path.resolve()).lower())
            self._reload_texture_library()
            self.editor_state = replace(self.editor_state, status_message=f"Renamed {entry.name} to {target_path.name}.")
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()

    def _delete_texture_entry(self, texture_id: str) -> None:
        if self._autorotate_active:
            return
        entry = self._ensure_file_backed_texture_entry(texture_id)
        if entry is None or entry.path is None:
            self.editor_state = replace(self.editor_state, status_message="Unable to delete that texture.")
            self._refresh_status()
            return
        should_delete = messagebox.askyesno(
            title="Delete Texture?",
            message=f"Delete {entry.name} permanently from the textures folder?\n\nThis cannot be undone.",
            parent=self.root,
        )
        if not should_delete:
            return
        try:
            entry.path.unlink()
        except OSError as exc:
            self.editor_state = replace(self.editor_state, status_message=f"Delete failed: {exc}")
        else:
            cleared_assignments = self._replace_texture_assignments(entry.texture_id, None)
            self._reload_texture_library(exclude_transient_ids={entry.texture_id})
            if cleared_assignments:
                message = f"Deleted {entry.name} and cleared {cleared_assignments} face assignments."
            else:
                message = f"Deleted {entry.name}."
            self.editor_state = replace(self.editor_state, status_message=message)
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._render_viewport()

    def _build_texture_context_menu(self, texture_id: str) -> tk.Menu:
        if self._texture_context_menu is not None:
            self._texture_context_menu.destroy()
        entry = self.texture_lookup.get(texture_id)
        menu = tk.Menu(self.root, tearoff=False)
        can_apply = entry is not None and bool(self.editor_state.selected_face_ids) and not self._autorotate_active
        can_manage = entry is not None and not self._autorotate_active
        can_edit_2d = can_manage and self._can_open_texture_in_pixel_fix_2d()
        menu.add_command(
            label="Apply",
            command=lambda: self._apply_texture_to_selected_faces(texture_id),
            state=tk.NORMAL if can_apply else tk.DISABLED,
        )
        menu.add_command(
            label="Edit in Pixel-Fix 2D",
            command=lambda: self._edit_texture_in_pixel_fix_2d(texture_id),
            state=tk.NORMAL if can_edit_2d else tk.DISABLED,
        )
        menu.add_separator()
        menu.add_command(
            label="Duplicate",
            command=lambda: self._duplicate_texture_entry(texture_id),
            state=tk.NORMAL if can_manage else tk.DISABLED,
        )
        menu.add_command(
            label="Rename",
            command=lambda: self._rename_texture_entry(texture_id),
            state=tk.NORMAL if can_manage else tk.DISABLED,
        )
        menu.add_command(
            label="Delete",
            command=lambda: self._delete_texture_entry(texture_id),
            state=tk.NORMAL if can_manage else tk.DISABLED,
        )
        self._texture_context_menu = menu
        return menu

    def _show_texture_context_menu(self, event: tk.Event, texture_id: str) -> str:
        menu = self._build_texture_context_menu(texture_id)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _zoom_display_value(self) -> str:
        return f"{camera_distance_to_zoom_percent(self.editor_state.camera.distance)}%"

    def _show_toolbar_placeholder_message(self, action_label: str) -> None:
        self.editor_state = replace(self.editor_state, status_message=f"{action_label} is not implemented yet.")
        self._refresh_status()

    def _capture_preferences_state(self) -> PreferencesDialogState:
        return PreferencesDialogState(preferences=self.preferences)

    def _set_preferences_dialog_state(self, state: PreferencesDialogState) -> None:
        if self._preferences_show_floor_grid_var is not None:
            self._preferences_show_floor_grid_var.set(state.preferences.show_floor_grid)
        if self._preferences_show_face_highlight_var is not None:
            self._preferences_show_face_highlight_var.set(state.preferences.show_face_highlight)
        if self._preferences_lighting_intensity_var is not None:
            self._preferences_lighting_intensity_var.set(self._lighting_intensity_display(state.preferences.lighting_intensity))
        if self._preferences_autorotate_speed_var is not None:
            self._preferences_autorotate_speed_var.set(self._autorotate_speed_display(state.preferences.autorotate_speed))
        if self._preferences_background_enabled_var is not None:
            self._preferences_background_enabled_var.set(state.preferences.background_enabled)
        if self._preferences_background_image_path_var is not None:
            self._preferences_background_image_path_var.set(state.preferences.background_image_path)
        self._update_preferences_background_controls()

    def _read_preferences_dialog_state(self) -> PreferencesDialogState:
        original = self._preferences_original_state or self._capture_preferences_state()
        return PreferencesDialogState(
            preferences=AppPreferences(
                show_floor_grid=bool(self._preferences_show_floor_grid_var.get())
                if self._preferences_show_floor_grid_var is not None
                else original.preferences.show_floor_grid,
                show_face_highlight=bool(self._preferences_show_face_highlight_var.get())
                if self._preferences_show_face_highlight_var is not None
                else original.preferences.show_face_highlight,
                lighting_intensity=self._lighting_intensity_value(self._preferences_lighting_intensity_var.get())
                if self._preferences_lighting_intensity_var is not None
                else original.preferences.lighting_intensity,
                autorotate_speed=self._autorotate_speed_value(self._preferences_autorotate_speed_var.get())
                if self._preferences_autorotate_speed_var is not None
                else original.preferences.autorotate_speed,
                background_enabled=bool(self._preferences_background_enabled_var.get())
                if self._preferences_background_enabled_var is not None
                else original.preferences.background_enabled,
                background_image_path=(self._preferences_background_image_path_var.get().strip())
                if self._preferences_background_image_path_var is not None
                else original.preferences.background_image_path,
            )
        )

    def _preferences_dialog_is_dirty(self) -> bool:
        if self._preferences_original_state is None:
            return False
        return self._read_preferences_dialog_state() != self._preferences_original_state

    def _refresh_preferences_nav_styles(self) -> None:
        for page_name, button in self._preferences_nav_buttons.items():
            button.configure(
                style="PreferencesNavActive.TButton"
                if page_name == self._preferences_selected_page
                else "PreferencesNav.TButton"
            )

    def _select_preferences_page(self, page_name: str) -> None:
        if page_name not in self._preferences_pages:
            return
        self._preferences_selected_page = page_name
        for name, frame in self._preferences_pages.items():
            if name == page_name:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
        self._refresh_preferences_nav_styles()

    def _destroy_preferences_window(self) -> None:
        window = self._preferences_window
        if window is not None and hasattr(window, "winfo_exists") and window.winfo_exists():
            window.destroy()
        self._preferences_window = None
        self._preferences_nav_buttons = {}
        self._preferences_pages = {}
        self._preferences_original_state = None
        self._preferences_show_floor_grid_var = None
        self._preferences_show_face_highlight_var = None
        self._preferences_lighting_intensity_var = None
        self._preferences_autorotate_speed_var = None
        self._preferences_background_enabled_var = None
        self._preferences_background_image_path_var = None
        self._preferences_background_path_entry = None
        self._preferences_background_browse_button = None
        self._preferences_background_clear_button = None

    def _close_preferences_window(self, *, force: bool = False) -> bool:
        if not force and self._preferences_dialog_is_dirty():
            should_discard = messagebox.askyesno(
                title="Discard Preference Changes?",
                message="Discard unsaved preference changes?",
                parent=self._preferences_window,
            )
            if not should_discard:
                return False
        self._destroy_preferences_window()
        return True

    def _apply_preferences_window_changes(self) -> None:
        state = self._read_preferences_dialog_state()
        self.preferences = state.preferences
        self._invalidate_viewport_background_cache()
        status_message = "Preferences updated."
        if (
            self.preferences.background_enabled
            and self.preferences.background_image_path
            and self._viewport_background_array() is None
        ):
            status_message = "Preferences updated. Background image could not be loaded."
        self.editor_state = replace(self.editor_state, status_message=status_message)
        self._persist_app_state()
        self._refresh_status()
        self._render_viewport()
        self._preferences_original_state = state
        self._close_preferences_window(force=True)

    def _reset_preferences_dialog_defaults(self) -> None:
        self._set_preferences_dialog_state(PreferencesDialogState(preferences=AppPreferences()))

    @staticmethod
    def _lighting_intensity_display(value: float) -> str:
        label, _value = min(LIGHTING_INTENSITY_OPTIONS, key=lambda option: abs(option[1] - value))
        return label

    @staticmethod
    def _lighting_intensity_value(label: str) -> float:
        for option_label, value in LIGHTING_INTENSITY_OPTIONS:
            if option_label == label:
                return value
        return 1.0

    @staticmethod
    def _autorotate_speed_display(value: float) -> str:
        label, _value = min(AUTOROTATE_SPEED_OPTIONS, key=lambda option: abs(option[1] - value))
        return label

    @staticmethod
    def _autorotate_speed_value(label: str) -> float:
        for option_label, value in AUTOROTATE_SPEED_OPTIONS:
            if option_label == label:
                return value
        return 1.0

    def _browse_preferences_background_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Viewport Background",
            filetypes=[("PNG Images", "*.png"), ("All files", "*.*")],
        )
        if not path:
            return
        if self._preferences_background_image_path_var is not None:
            self._preferences_background_image_path_var.set(path)
        if self._preferences_background_enabled_var is not None:
            self._preferences_background_enabled_var.set(True)
        self._update_preferences_background_controls()

    def _clear_preferences_background_image(self) -> None:
        if self._preferences_background_image_path_var is not None:
            self._preferences_background_image_path_var.set("")
        if self._preferences_background_enabled_var is not None:
            self._preferences_background_enabled_var.set(False)
        self._update_preferences_background_controls()

    def _update_preferences_background_controls(self) -> None:
        has_path = bool(self._preferences_background_image_path_var and self._preferences_background_image_path_var.get().strip())
        clear_state = tk.NORMAL if has_path else tk.DISABLED
        if self._preferences_background_clear_button is not None:
            self._preferences_background_clear_button.configure(state=clear_state)

    def open_preferences_window(self) -> None:
        if self._autorotate_active:
            self._stop_autorotate()
        window = self._preferences_window
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

        self._preferences_show_floor_grid_var = tk.BooleanVar(window, value=original_state.preferences.show_floor_grid)
        self._preferences_show_face_highlight_var = tk.BooleanVar(window, value=original_state.preferences.show_face_highlight)
        self._preferences_lighting_intensity_var = tk.StringVar(
            window,
            value=self._lighting_intensity_display(original_state.preferences.lighting_intensity),
        )
        self._preferences_autorotate_speed_var = tk.StringVar(
            window,
            value=self._autorotate_speed_display(original_state.preferences.autorotate_speed),
        )
        self._preferences_background_enabled_var = tk.BooleanVar(window, value=original_state.preferences.background_enabled)
        self._preferences_background_image_path_var = tk.StringVar(window, value=original_state.preferences.background_image_path)

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
        ttk.Button(action_row, text="Apply", command=self._apply_preferences_window_changes).pack(side=tk.RIGHT)
        ttk.Button(action_row, text="Cancel", command=self._close_preferences_window).pack(side=tk.RIGHT, padx=(0, 8))

        self._preferences_nav_buttons = {}
        self._preferences_pages = {}

        def build_page(title: str) -> ttk.Frame:
            frame = ttk.Frame(page_container)
            ttk.Label(frame, text=title.upper()).pack(anchor=tk.W, pady=(0, 8))
            self._preferences_pages[title] = frame
            return frame

        general_page = build_page(PREFERENCES_PAGE_GENERAL)
        ttk.Button(general_page, text="Reset Preferences to Defaults", command=self._reset_preferences_dialog_defaults).pack(
            anchor=tk.W,
            pady=(0, 8),
        )
        ttk.Label(
            general_page,
            text="These preferences are app-wide and will be restored automatically on the next launch.",
            style="Muted.TLabel",
            wraplength=340,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        viewport_page = build_page(PREFERENCES_PAGE_VIEWPORT)
        ttk.Checkbutton(
            viewport_page,
            text="Show floor grid",
            variable=self._preferences_show_floor_grid_var,
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            viewport_page,
            text="Show selected face highlight",
            variable=self._preferences_show_face_highlight_var,
        ).pack(anchor=tk.W, pady=(6, 0))
        ttk.Label(viewport_page, text="Lighting Intensity").pack(anchor=tk.W, pady=(10, 0))
        for label, _value in LIGHTING_INTENSITY_OPTIONS:
            ttk.Radiobutton(
                viewport_page,
                text=label,
                value=label,
                variable=self._preferences_lighting_intensity_var,
            ).pack(anchor=tk.W)
        ttk.Label(viewport_page, text="Rotate View Speed").pack(anchor=tk.W, pady=(10, 0))
        for label, _value in AUTOROTATE_SPEED_OPTIONS:
            ttk.Radiobutton(
                viewport_page,
                text=label,
                value=label,
                variable=self._preferences_autorotate_speed_var,
            ).pack(anchor=tk.W)
        ttk.Label(
            viewport_page,
            text="The floor grid sits just below the model so the bottom face is easier to read.",
            style="Muted.TLabel",
            wraplength=340,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))

        background_page = build_page(PREFERENCES_PAGE_BACKGROUND)
        ttk.Checkbutton(
            background_page,
            text="Enable background image",
            variable=self._preferences_background_enabled_var,
            command=self._update_preferences_background_controls,
        ).pack(anchor=tk.W)
        ttk.Label(background_page, text="PNG File").pack(anchor=tk.W, pady=(10, 0))
        self._preferences_background_path_entry = tk.Entry(
            background_page,
            textvariable=self._preferences_background_image_path_var,
            font=self.ui_font,
            background=APP_SURFACE_BG,
            foreground=APP_TEXT,
            insertbackground=APP_TEXT,
            readonlybackground=APP_SURFACE_BG,
            disabledforeground=APP_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=APP_BORDER,
            highlightcolor=APP_BORDER,
        )
        self._preferences_background_path_entry.pack(anchor=tk.W, fill=tk.X)
        self._preferences_background_path_entry.configure(state="readonly")
        background_actions = ttk.Frame(background_page)
        background_actions.pack(anchor=tk.W, pady=(8, 0))
        self._preferences_background_browse_button = ttk.Button(
            background_actions,
            text="Browse...",
            command=self._browse_preferences_background_image,
        )
        self._preferences_background_browse_button.pack(side=tk.LEFT)
        self._preferences_background_clear_button = ttk.Button(
            background_actions,
            text="Clear",
            command=self._clear_preferences_background_image,
        )
        self._preferences_background_clear_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            background_page,
            text="The image stays static and is stretched to fill the viewport.",
            style="Muted.TLabel",
            wraplength=340,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(10, 0))

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

    def _invalidate_viewport_background_cache(self) -> None:
        self._viewport_background_cache_key = None
        self._viewport_background_cache_rgb = None

    def _viewport_background_array(self) -> np.ndarray | None:
        key = (self.preferences.background_enabled, self.preferences.background_image_path)
        if key == self._viewport_background_cache_key:
            return self._viewport_background_cache_rgb
        self._viewport_background_cache_key = key
        self._viewport_background_cache_rgb = None
        if not self.preferences.background_enabled or not self.preferences.background_image_path:
            return None
        try:
            with Image.open(self.preferences.background_image_path) as source:
                rgba = source.convert("RGBA").resize((VIEWPORT_WIDTH, VIEWPORT_HEIGHT), Image.Resampling.NEAREST)
        except (OSError, ValueError):
            return None
        base = Image.new("RGBA", (VIEWPORT_WIDTH, VIEWPORT_HEIGHT), (*BACKGROUND_RGB.tolist(), 255))
        composited = Image.alpha_composite(base, rgba).convert("RGB")
        self._viewport_background_cache_rgb = np.asarray(composited, dtype=np.uint8)
        return self._viewport_background_cache_rgb

    def _persist_app_state(self) -> None:
        save_app_state(
            {
                "last_shape_key": self.editor_state.shape_key,
                "window_geometry": self.root.geometry(),
                "preferences": app_preferences_to_dict(self.preferences),
            }
        )

    def _save_project(self) -> None:
        if self._autorotate_active:
            return
        target = filedialog.asksaveasfilename(
            title="Save Pixel-Fix Studio 3D Project",
            defaultextension=".pfx3d",
            filetypes=[("Pixel-Fix Studio 3D Project", "*.pfx3d"), ("All files", "*.*")],
        )
        if not target:
            return
        try:
            save_pfx3d(target, self._shape(), self._assigned_textures_for_shape())
        except (OSError, Pfx3dError) as exc:
            self.editor_state = replace(self.editor_state, status_message=f"Save failed: {exc}")
        else:
            self.editor_state = replace(self.editor_state, status_message=f"Saved {Path(target).name}.")
        self._refresh_status()

    def _open_project(self) -> None:
        if self._autorotate_active:
            return
        source = filedialog.askopenfilename(
            title="Open Pixel-Fix Studio 3D Project",
            filetypes=[("Pixel-Fix Studio 3D Project", "*.pfx3d"), ("All files", "*.*")],
        )
        if not source:
            return
        try:
            project = load_pfx3d(source)
            loaded_entries = self._project_texture_entries(project, Path(source))
            assignments = {
                project.shape_key: {
                    face.face_id: loaded_entries[index].texture_id
                    for index, face in enumerate(project.faces)
                }
            }
            new_state = EditorState(face_texture_assignments=assignments)
            shape = SHAPE_PRESETS_BY_KEY[project.shape_key]
            new_state = set_shape(new_state, project.shape_key, shape.label)
            new_state = replace(new_state, status_message=f"Loaded {Path(source).name}.")
        except (OSError, Pfx3dError) as exc:
            self.editor_state = replace(self.editor_state, status_message=f"Open failed: {exc}")
            self._refresh_status()
            return

        self._reset_texture_library(loaded_entries)
        self.editor_state = new_state
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._render_viewport()

    def _extract_textures(self) -> None:
        if self._autorotate_active:
            return
        destination = filedialog.askdirectory(
            title="Extract Face Textures",
            mustexist=True,
        )
        if not destination:
            return
        try:
            export_dir = extract_face_textures(destination, self._shape(), self._assigned_textures_for_shape())
        except (OSError, Pfx3dError) as exc:
            self.editor_state = replace(self.editor_state, status_message=f"Extract failed: {exc}")
        else:
            self.editor_state = replace(self.editor_state, status_message=f"Extracted textures to {export_dir.name}.")
        self._refresh_status()

    def _export_glb(self) -> None:
        if self._autorotate_active:
            return
        target = filedialog.asksaveasfilename(
            title="Export Pixel-Fix Studio 3D Model",
            defaultextension=".glb",
            filetypes=[("glTF Binary", "*.glb"), ("All files", "*.*")],
        )
        if not target:
            return
        try:
            export_glb(target, self._shape(), self._assigned_textures_for_shape())
        except (OSError, GlbExportError) as exc:
            self.editor_state = replace(self.editor_state, status_message=f"GLB export failed: {exc}")
        else:
            self.editor_state = replace(self.editor_state, status_message=f"Exported {Path(target).name}.")
        self._refresh_status()

    def _project_texture_entries(self, project: Pfx3dProject, source_path: Path) -> list[TextureEntry]:
        entries: list[TextureEntry] = []
        source_name = source_path.stem.lower()
        for face in project.faces:
            entries.append(
                load_texture_bytes(
                    self._png_bytes(face.image),
                    texture_id=f"pfx3d:{source_name}:{face.face_id}:{Path(face.texture_file).name.lower()}",
                    name=Path(face.texture_file).name,
                    path=None,
                )
            )
        return entries

    def _set_shape(self, shape_key: str) -> None:
        if self._autorotate_active:
            return
        shape = SHAPE_PRESETS_BY_KEY[shape_key]
        self.editor_state = set_shape(self.editor_state, shape_key, shape.label)
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._render_viewport()

    def _reset_camera(self) -> None:
        if self._autorotate_active:
            return
        shape = self._shape()
        self.editor_state = replace(
            self.editor_state,
            camera=reset_camera(),
            status_message=f"Reset camera for {shape.label}.",
        )
        self._refresh_status()
        self._render_viewport()

    def _snap_view(self, view_name: str) -> None:
        if self._autorotate_active:
            return
        view_label = VIEW_LABELS.get(view_name, view_name.replace("_", " ").title())
        self.editor_state = replace(
            self.editor_state,
            camera=snap_camera_view(self.editor_state.camera, view_name),
            status_message=f"Snapped camera to {view_label} view.",
        )
        self._refresh_status()
        self._render_viewport()

    def _toggle_rotating_view(self) -> None:
        if self._autorotate_active:
            self._stop_autorotate()
            return
        self._autorotate_active = True
        self._autorotate_restore_camera = self.editor_state.camera
        self._autorotate_restore_face_id = self.editor_state.selected_face_id
        self._autorotate_restore_face_ids = self.editor_state.selected_face_ids
        self.editor_state = replace(
            self.editor_state,
            selected_face_id=None,
            selected_face_ids=(),
            status_message="Rotating view enabled. Editing and selection are locked.",
        )
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._run_autorotate()

    def _stop_autorotate(self) -> None:
        if self._autorotate_job is not None:
            self.root.after_cancel(self._autorotate_job)
            self._autorotate_job = None
        self._autorotate_active = False
        restored_camera = self._autorotate_restore_camera or self.editor_state.camera
        self.editor_state = replace(
            self.editor_state,
            camera=restored_camera,
            selected_face_id=self._autorotate_restore_face_id,
            selected_face_ids=self._autorotate_restore_face_ids,
            status_message="Rotating view disabled.",
        )
        self._autorotate_restore_camera = None
        self._autorotate_restore_face_id = None
        self._autorotate_restore_face_ids = ()
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._render_viewport()

    def _run_autorotate(self) -> None:
        if not self._autorotate_active:
            return
        self.editor_state = replace(
            self.editor_state,
            camera=rotate_camera(self.editor_state.camera, AUTOROTATE_YAW_STEP * self.preferences.autorotate_speed, 0.0),
        )
        self._render_viewport()
        self._autorotate_job = self.root.after(AUTOROTATE_INTERVAL_MS, self._run_autorotate)

    def _load_textures(self) -> None:
        if self._autorotate_active:
            return
        source = filedialog.askopenfilename(
            title="Load pixel texture",
            filetypes=[("PNG Images", "*.png"), ("All files", "*.*")],
            initialdir=str(self._default_texture_directory()),
        )
        if not source:
            return
        try:
            target = self._import_texture_file(Path(source))
        except (OSError, ValueError) as exc:
            self.editor_state = replace(self.editor_state, status_message=f"Load failed: {exc}")
        else:
            self._reload_texture_library()
            self.editor_state = replace(self.editor_state, status_message=f"Loaded {target.name}.")
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()

    def _import_texture_file(self, source_path: Path) -> Path:
        if source_path.suffix.lower() != ".png":
            raise ValueError("Only PNG textures are supported.")
        target_dir = self._default_texture_directory()
        target_dir.mkdir(parents=True, exist_ok=True)

        source_resolved = source_path.resolve()
        target_dir_resolved = target_dir.resolve()
        if source_resolved.parent == target_dir_resolved:
            return source_resolved

        target = self._next_available_texture_path(target_dir, source_path.name)
        if target.exists() and target.resolve() == source_resolved:
            return target.resolve()
        shutil.copy2(source_resolved, target)
        return target.resolve()

    def _refresh_shape_buttons(self) -> None:
        enabled = not self._autorotate_active
        for shape_key in self.shape_buttons:
            self._set_tool_button_state(
                f"shape_{shape_key}_button",
                active=shape_key == self.editor_state.shape_key,
                enabled=enabled,
            )

    def _refresh_view_buttons(self) -> None:
        enabled = not self._autorotate_active
        for view_key in self.view_buttons:
            self._set_tool_button_state(f"view_{view_key}_button", active=False, enabled=enabled)
        self._set_tool_button_state("rotate_view_button", active=self._autorotate_active, enabled=True)

    def _refresh_texture_buttons(self) -> None:
        if self._texture_context_menu is not None:
            self._texture_context_menu.destroy()
            self._texture_context_menu = None
        for child in list(self.texture_inner.winfo_children()):
            child.destroy()
        self.texture_button_images.clear()
        self.texture_buttons.clear()

        if not self.texture_entries:
            ttk.Label(
                self.texture_inner,
                text="No textures loaded.\nUse Load Texture... to build the library.",
                style="Muted.TLabel",
                justify=tk.LEFT,
            ).pack(anchor=tk.W, fill=tk.X)
            return

        current_texture_id = self.editor_state.texture_for_face(self.editor_state.selected_face_id)
        for entry in self.texture_entries:
            photo = ImageTk.PhotoImage(build_thumbnail(entry.image, size=TEXTURE_THUMBNAIL_SIZE))
            self.texture_button_images[entry.texture_id] = photo
            button = ttk.Button(
                self.texture_inner,
                text=f"{entry.name}\n{entry.size[0]}x{entry.size[1]}",
                image=photo,
                compound=tk.LEFT,
                style="TextureSelected.TButton" if entry.texture_id == current_texture_id else "Texture.TButton",
                command=lambda texture_id=entry.texture_id: self._assign_texture(texture_id),
                state=tk.DISABLED if self._autorotate_active else tk.NORMAL,
            )
            button.pack(fill=tk.X, pady=(0, 4))
            button.bind(
                "<Button-3>",
                lambda event, texture_id=entry.texture_id: self._show_texture_context_menu(event, texture_id),
            )
            self.texture_buttons[entry.texture_id] = button

    def _update_interaction_states(self) -> None:
        disabled = tk.DISABLED if self._autorotate_active else tk.NORMAL
        self.reset_camera_button.configure(state=disabled)
        self.clear_selected_face_button.configure(state=disabled)
        self.clear_shape_textures_button.configure(state=disabled)
        self.load_textures_button.configure(state=disabled)
        self.extract_textures_button.configure(state=disabled)
        self.export_glb_button.configure(state=disabled)
        self._refresh_shape_buttons()
        self._refresh_view_buttons()
        self._set_tool_button_state("toolbar_new_button", active=False, enabled=True)
        self._set_tool_button_state("toolbar_open_button", active=False, enabled=not self._autorotate_active)
        self._set_tool_button_state("toolbar_save_button", active=False, enabled=not self._autorotate_active)
        self._set_tool_button_state("toolbar_settings_button", active=False, enabled=True)

    def _assigned_textures_for_shape(self) -> dict[int, TextureEntry]:
        assignments = self.editor_state.face_texture_assignments.get(self.editor_state.shape_key, {})
        result: dict[int, TextureEntry] = {}
        for face_id, texture_id in assignments.items():
            entry = self.texture_lookup.get(texture_id)
            if entry is not None:
                result[face_id] = entry
        return result

    def _render_viewport(self) -> None:
        canvas_width = max(1, self.viewport_canvas.winfo_width())
        canvas_height = max(1, self.viewport_canvas.winfo_height())
        render = self.renderer.render(
            shape=self._shape(),
            camera=self.editor_state.camera,
            textures_by_face=self._assigned_textures_for_shape(),
            selected_face_ids=self.editor_state.selected_face_ids,
            options=RenderOptions(
                show_floor_grid=self.preferences.show_floor_grid,
                show_face_highlight=self.preferences.show_face_highlight,
                lighting_intensity=self.preferences.lighting_intensity,
                background_rgb=self._viewport_background_array(),
            ),
        )
        self.last_render_face_ids = render.face_id_buffer

        scale = min(canvas_width / VIEWPORT_WIDTH, canvas_height / VIEWPORT_HEIGHT)
        display_width = max(1, int(VIEWPORT_WIDTH * scale))
        display_height = max(1, int(VIEWPORT_HEIGHT * scale))
        offset_x = (canvas_width - display_width) // 2
        offset_y = (canvas_height - display_height) // 2
        self.viewport_display_rect = (offset_x, offset_y, display_width, display_height)

        scaled = render.image.resize((display_width, display_height), Image.Resampling.NEAREST)
        self.viewport_photo = ImageTk.PhotoImage(scaled)
        self.viewport_canvas.delete("all")
        self.viewport_canvas.create_rectangle(0, 0, canvas_width, canvas_height, fill=APP_PANEL_BG, outline=APP_PANEL_BG)
        self.viewport_canvas.create_image(offset_x, offset_y, image=self.viewport_photo, anchor=tk.NW)

    def _refresh_status(self) -> None:
        shape = self._shape()
        selection_count = len(self.editor_state.selected_face_ids)
        face_label = self._face_label(self.editor_state.selected_face_id)
        face_target = self._face_texture_target(self.editor_state.selected_face_id)
        texture_text = "None"
        texture_size = "-"
        texture_id = self.editor_state.texture_for_face(self.editor_state.selected_face_id)
        if texture_id is not None and texture_id in self.texture_lookup:
            entry = self.texture_lookup[texture_id]
            texture_text = entry.name
            texture_size = f"{entry.size[0]}x{entry.size[1]}"
        face_detail = face_label or "None"
        if selection_count > 1 and face_label is not None:
            face_detail = f"{selection_count} selected (active: {face_label})"
        self.status_message_var.set(self.editor_state.status_message)
        self.status_detail_var.set(
            f"Shape: {shape.label}   Face: {face_detail}   Target: {face_target or '-'}   Texture: {texture_text}   Size: {texture_size}"
        )
        self.toolbar_zoom_var.set(self._zoom_display_value())
        if face_label is None:
            self.face_summary_var.set("No face selected.")
        elif selection_count > 1:
            self.face_summary_var.set(f"{selection_count} faces selected (active: {face_label})   Target: {face_target}")
        else:
            self.face_summary_var.set(f"{face_label}   Target: {face_target}")
        self.texture_summary_var.set("No texture assigned." if texture_text == "None" else f"{texture_text}  {texture_size}")

    def _assign_texture(self, texture_id: str) -> None:
        if self._autorotate_active:
            return
        texture = self.texture_lookup.get(texture_id)
        if texture is None:
            return
        face_label = self._face_label(self.editor_state.selected_face_id)
        self.editor_state = assign_texture_to_selected_face(self.editor_state, texture.texture_id, texture.name, face_label)
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._render_viewport()

    def _clear_selected_face_texture(self) -> None:
        if self._autorotate_active:
            return
        self.editor_state = clear_selected_face_texture(self.editor_state, self._face_label(self.editor_state.selected_face_id))
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._render_viewport()

    def _clear_shape_textures(self) -> None:
        if self._autorotate_active:
            return
        self.editor_state = clear_shape_textures(self.editor_state, self._shape().label)
        self._refresh_texture_buttons()
        self._update_interaction_states()
        self._refresh_status()
        self._render_viewport()

    def _on_viewport_press(self, event: tk.Event) -> None:
        if self._autorotate_active:
            return
        self._drag_origin = (event.x, event.y)
        self._drag_last = (event.x, event.y)
        self._dragging = False

    def _on_viewport_drag(self, event: tk.Event) -> None:
        if self._autorotate_active:
            return
        if self._drag_origin is None or self._drag_last is None:
            return
        total_dx = event.x - self._drag_origin[0]
        total_dy = event.y - self._drag_origin[1]
        if not self._dragging and ((total_dx * total_dx) + (total_dy * total_dy) >= 16):
            self._dragging = True
        if not self._dragging:
            return
        step_dx = event.x - self._drag_last[0]
        step_dy = event.y - self._drag_last[1]
        self._drag_last = (event.x, event.y)
        self.editor_state = replace(
            self.editor_state,
            camera=rotate_camera(self.editor_state.camera, step_dx * 0.015, -step_dy * 0.015),
        )
        self._render_viewport()

    def _on_viewport_release(self, event: tk.Event) -> None:
        if self._autorotate_active:
            return
        if not self._dragging:
            self._pick_face(event.x, event.y, toggle=bool(event.state & EVENT_STATE_SHIFT_MASK))
        self._drag_origin = None
        self._drag_last = None
        self._dragging = False

    def _pick_face(self, canvas_x: int, canvas_y: int, *, toggle: bool = False) -> None:
        if self._autorotate_active:
            return
        if self.last_render_face_ids is None:
            return
        display_x, display_y, display_width, display_height = self.viewport_display_rect
        if display_width <= 0 or display_height <= 0:
            return
        if not (display_x <= canvas_x < display_x + display_width and display_y <= canvas_y < display_y + display_height):
            if not toggle:
                self.editor_state = clear_selection(self.editor_state)
        else:
            normalized_x = (canvas_x - display_x) / display_width
            normalized_y = (canvas_y - display_y) / display_height
            buffer_x = min(VIEWPORT_WIDTH - 1, max(0, int(normalized_x * VIEWPORT_WIDTH)))
            buffer_y = min(VIEWPORT_HEIGHT - 1, max(0, int(normalized_y * VIEWPORT_HEIGHT)))
            face_id = int(self.last_render_face_ids[buffer_y, buffer_x])
            resolved_face_id = face_id if face_id >= 0 else None
            face_label = self._face_label(resolved_face_id)
            if resolved_face_id is None:
                if not toggle:
                    self.editor_state = clear_selection(self.editor_state)
            elif toggle:
                self.editor_state = toggle_face_in_selection(self.editor_state, resolved_face_id, face_label)
            else:
                self.editor_state = select_face(self.editor_state, resolved_face_id, face_label)
        self._refresh_texture_buttons()
        self._refresh_status()
        self._render_viewport()

    def _on_select_all_shortcut(self, _event: tk.Event | None = None) -> str:
        if self._autorotate_active:
            return "break"
        focus_widget = self.root.focus_get()
        if focus_widget is not None:
            try:
                if focus_widget.winfo_toplevel() is not self.root:
                    return "break"
            except tk.TclError:
                return "break"
        self.editor_state = toggle_select_all_faces(self.editor_state, self._all_face_ids(), self._shape().label)
        self._refresh_texture_buttons()
        self._refresh_status()
        self._render_viewport()
        return "break"

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        if self._autorotate_active:
            return
        self._apply_zoom(-0.25 if event.delta > 0 else 0.25)

    def _apply_zoom(self, delta_distance: float) -> None:
        if self._autorotate_active:
            return
        self.editor_state = replace(self.editor_state, camera=zoom_camera(self.editor_state.camera, delta_distance))
        self._refresh_status()
        self._render_viewport()

    def _png_bytes(self, image: Image.Image) -> bytes:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _tool_button_icon(self, asset_name: str, *, disabled: bool = False) -> ImageTk.PhotoImage:
        cache_key = (asset_name, disabled)
        cached_icon = self._tool_button_icons.get(cache_key)
        if cached_icon is not None:
            return cached_icon

        fitted = Image.new("RGBA", (TOOL_BUTTON_WIDTH - 2, TOOL_BUTTON_HEIGHT - 2), (0, 0, 0, 0))
        asset_path = self._asset_path(asset_name)
        if asset_path.exists():
            with Image.open(asset_path) as source:
                rgba = source.convert("RGBA")
                rgba.thumbnail((TOOL_BUTTON_WIDTH - 10, TOOL_BUTTON_HEIGHT - 10), Image.Resampling.NEAREST)
                if disabled:
                    alpha = rgba.getchannel("A").point(lambda value: (value * 3) // 4)
                    rgba = rgba.copy()
                    rgba.putalpha(alpha)
                offset_x = (fitted.width - rgba.width) // 2
                offset_y = (fitted.height - rgba.height) // 2
                fitted.paste(rgba, (offset_x, offset_y), rgba)
        cached_icon = ImageTk.PhotoImage(fitted, master=self.root)
        self._tool_button_icons[cache_key] = cached_icon
        return cached_icon

    def _create_tool_button(
        self,
        widget_name: str,
        parent: tk.Misc,
        asset_name: str,
        command: object,
        tooltip_text: str,
    ) -> tuple[tk.Frame, ttk.Button]:
        cell = tk.Frame(parent, width=TOOL_BUTTON_WIDTH, height=TOOL_BUTTON_HEIGHT, bg=APP_BORDER, bd=0, highlightthickness=0)
        cell.grid_propagate(False)
        cell.pack_propagate(False)
        button = ttk.Button(
            cell,
            image=self._tool_button_icon(asset_name),
            command=command if callable(command) else None,
            style="ToolButton.TButton",
        )
        button.place(x=1, y=1, width=TOOL_BUTTON_WIDTH - 2, height=TOOL_BUTTON_HEIGHT - 2)
        self._tool_button_assets[widget_name] = asset_name
        self._tool_button_widgets[widget_name] = button
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
        return button

    def _set_tool_button_state(self, widget_name: str, *, active: bool, enabled: bool) -> None:
        frame = self._tool_button_frames.get(widget_name)
        button = self._tool_button_widgets.get(widget_name)
        asset_name = self._tool_button_assets.get(widget_name)
        if frame is None or button is None or asset_name is None:
            return
        frame.configure(bg=APP_ACCENT if active and enabled else APP_BORDER)
        button.configure(
            style="ToolButtonActive.TButton" if active and enabled else "ToolButton.TButton" if enabled else "ToolButtonDisabled.TButton",
            image=self._tool_button_icon(asset_name, disabled=not enabled),
        )
        if enabled:
            button.state(("!disabled",))
        else:
            button.state(("disabled",))

    def _restore_window_geometry(self, geometry: str | None) -> None:
        if geometry:
            try:
                self.root.geometry(geometry)
            except tk.TclError:
                pass

    def _on_close(self) -> None:
        if self._autorotate_job is not None:
            self.root.after_cancel(self._autorotate_job)
            self._autorotate_job = None
        self._close_preferences_window(force=True)
        self._persist_app_state()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    PixelFixStudio3DApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
