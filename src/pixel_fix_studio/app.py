from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

from . import __version__
from .content import (
    DEFAULT_STATUS,
    DEFAULT_STATUS_DETAIL,
    LAUNCHER_CARDS,
    SIDEBAR_PRIMARY_ITEMS,
    SIDEBAR_SECONDARY_ITEMS,
    LauncherCardSpec,
    SidebarItemSpec,
)
from .library import (
    TEXTURE_SUFFIXES,
    create_library_folder,
    delete_library_item,
    import_palette_file,
    import_texture_file,
    list_library_folders,
    list_palette_items,
    list_texture_items,
    move_library_item,
)
from .launcher_apps import build_launch_request, resolve_app_installation, runtime_root
from .models import AppInstallation, LauncherSettings, PaletteItem, RecentProjectItem, TextureItem
from .recent import load_recent_project_items
from .settings_store import (
    detect_default_install_dirs,
    launcher_settings_path,
    load_launcher_settings,
    resolve_initial_settings,
    save_launcher_settings,
    validate_pixel_fix_2d_install_dir,
    validate_pixel_fix_3d_install_dir,
)
from .theme import (
    APP_ACCENT,
    APP_BG,
    APP_BLACK,
    APP_BORDER,
    APP_GLOW_CYAN,
    APP_GLOW_PURPLE,
    APP_HOVER_BG,
    APP_MUTED_TEXT,
    APP_PANEL_BG,
    APP_SCANLINE,
    APP_STATUS_BG,
    APP_SURFACE_BG,
    APP_TEXT,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
    LauncherFonts,
    accent_from_key,
    build_fonts,
    configure_ttk_theme,
)
from .tooltips import Tooltip

OPEN_HAND_CURSOR = "hand2"
CARD_ICON_SIZE = 56
CARD_WIDTH = 250
CARD_HEIGHT = 150
RECENT_THUMBNAIL_SIZE = 32
ASSET_PREVIEW_SIZE = (80, 48)
ASSET_CARD_WIDTH = 112
ASSET_CARD_HEIGHT = 92
ASSET_TREE_WIDTH = 180

AssetItem = PaletteItem | TextureItem


@dataclass
class AssetBrowserWidgets:
    key: str
    title: str
    frame: tk.Frame
    message_var: tk.StringVar
    folder_var: tk.StringVar
    tree: ttk.Treeview
    preview_canvas: tk.Canvas
    preview_inner: tk.Frame
    preview_window: int
    add_button: ttk.Button
    new_folder_button: ttk.Button
    move_button: ttk.Button
    delete_button: ttk.Button
    refresh_button: ttk.Button
    tree_paths: dict[str, Path] = field(default_factory=dict)
    path_ids: dict[Path, str] = field(default_factory=dict)
    current_folder: Path | None = None
    selected_item_path: Path | None = None
    items_by_path: dict[Path, AssetItem] = field(default_factory=dict)
    last_canvas_width: int = 0


def mix_color(primary: str, secondary: str, factor: float) -> str:
    factor = max(0.0, min(1.0, factor))
    left = primary.lstrip("#")
    right = secondary.lstrip("#")
    values: list[int] = []
    for index in range(0, 6, 2):
        start = int(left[index:index + 2], 16)
        end = int(right[index:index + 2], 16)
        values.append(round(start + ((end - start) * factor)))
    return f"#{values[0]:02x}{values[1]:02x}{values[2]:02x}"


def draw_pixel_icon(canvas: tk.Canvas, icon_kind: str, accent: str, *, background: str) -> None:
    canvas.delete("all")
    width = int(canvas.cget("width"))
    height = int(canvas.cget("height"))
    scale = min(width, height) / 44.0
    pixel = lambda value: int(round(value * scale))
    light = mix_color(accent, APP_BORDER, 0.35)
    shadow = mix_color(accent, background, 0.45)

    if icon_kind == "folder":
        canvas.create_rectangle(pixel(6), pixel(16), width - pixel(6), height - pixel(10), fill=accent, outline=accent, width=0)
        canvas.create_rectangle(pixel(10), pixel(10), pixel(24), pixel(18), fill=accent, outline=accent, width=0)
        canvas.create_rectangle(pixel(8), pixel(18), width - pixel(8), height - pixel(12), fill=light, outline=light, width=0)
        return
    if icon_kind == "palette":
        blocks = (
            (pixel(6), pixel(6), pixel(18), pixel(18), accent),
            (pixel(20), pixel(6), pixel(32), pixel(18), light),
            (pixel(10), pixel(20), pixel(22), pixel(32), APP_BORDER),
            (pixel(24), pixel(20), pixel(36), pixel(32), shadow),
        )
        for x0, y0, x1, y1, color in blocks:
            canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color, width=0)
        return
    if icon_kind == "brick":
        for row, y in enumerate((pixel(6), pixel(16), pixel(26))):
            offset = 0 if row % 2 == 0 else pixel(8)
            for x in range(pixel(6) + offset, width - pixel(10), pixel(16)):
                canvas.create_rectangle(x, y, x + pixel(12), y + pixel(8), fill=accent, outline=accent, width=0)
        return
    if icon_kind == "gear":
        canvas.create_rectangle(pixel(14), pixel(14), width - pixel(14), height - pixel(14), fill=accent, outline=accent, width=0)
        teeth = (
            (pixel(20), pixel(4), pixel(28), pixel(14)),
            (pixel(20), height - pixel(14), pixel(28), height - pixel(4)),
            (pixel(4), pixel(20), pixel(14), pixel(28)),
            (width - pixel(14), pixel(20), width - pixel(4), pixel(28)),
        )
        for x0, y0, x1, y1 in teeth:
            canvas.create_rectangle(x0, y0, x1, y1, fill=accent, outline=accent, width=0)
        canvas.create_rectangle(pixel(20), pixel(20), width - pixel(20), height - pixel(20), fill=APP_SURFACE_BG, outline=APP_SURFACE_BG, width=0)
        return
    if icon_kind == "question":
        canvas.create_text(width / 2, height / 2, text="?", fill=accent, font=("TkFixedFont", max(8, pixel(16)), "bold"))
        return
    if icon_kind == "sprite":
        for row in range(3):
            for column in range(3):
                fill = accent if (row, column) != (1, 1) else APP_BORDER
                x0 = pixel(6) + (column * pixel(10))
                y0 = pixel(6) + (row * pixel(10))
                canvas.create_rectangle(x0, y0, x0 + pixel(8), y0 + pixel(8), fill=fill, outline=fill, width=0)
        canvas.create_line(pixel(30), pixel(24), pixel(40), pixel(14), fill=APP_BORDER, width=max(1, pixel(3)))
        canvas.create_rectangle(pixel(35), pixel(8), pixel(41), pixel(14), fill=APP_BORDER, outline=APP_BORDER, width=0)
        return
    if icon_kind == "voxel":
        canvas.create_polygon(pixel(20), pixel(6), pixel(34), pixel(14), pixel(20), pixel(22), pixel(6), pixel(14), fill=light, outline=light)
        canvas.create_polygon(pixel(6), pixel(14), pixel(20), pixel(22), pixel(20), pixel(38), pixel(6), pixel(30), fill=accent, outline=accent)
        canvas.create_polygon(pixel(20), pixel(22), pixel(34), pixel(14), pixel(34), pixel(30), pixel(20), pixel(38), fill=shadow, outline=shadow)
        return
    canvas.create_rectangle(pixel(8), pixel(8), width - pixel(8), height - pixel(8), fill=accent, outline=accent, width=0)
    canvas.create_rectangle(pixel(12), pixel(12), width - pixel(12), height - pixel(12), fill=light, outline=light, width=0)


def build_palette_preview_image(colors: tuple[int, ...], size: tuple[int, int], *, background: str) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, background)
    draw = ImageDraw.Draw(image)
    if not colors:
        draw.rectangle((0, 0, width - 1, height - 1), outline=APP_BORDER)
        draw.line((0, 0, width - 1, height - 1), fill=APP_ACCENT)
        draw.line((0, height - 1, width - 1, 0), fill=APP_ACCENT)
        return image

    color_count = len(colors)
    columns = min(8, max(1, color_count))
    rows = max(1, (color_count + columns - 1) // columns)

    for index, value in enumerate(colors):
        row = index // columns
        column = index % columns
        x0 = (column * width) // columns
        x1 = max(x0, (((column + 1) * width) // columns) - 1)
        y0 = (row * height) // rows
        y1 = max(y0, (((row + 1) * height) // rows) - 1)
        draw.rectangle((x0, y0, x1, y1), fill=f"#{value:06x}")
    return image


class SidebarItemWidget(tk.Frame):
    def __init__(self, parent: tk.Misc, *, spec: SidebarItemSpec, fonts: LauncherFonts, command) -> None:
        super().__init__(parent, bg=APP_BG, highlightthickness=0, bd=0)
        self.spec = spec
        self.command = command
        self.accent = accent_from_key(spec.accent_key)
        self.enabled = True
        self.selected = False
        self.hovered = False

        self.strip = tk.Frame(self, bg=APP_BG, width=5)
        self.strip.pack(side=tk.LEFT, fill=tk.Y)
        self.shell = tk.Frame(self, bg=APP_SURFACE_BG)
        self.shell.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.shell.pack_propagate(False)
        self.shell.configure(height=38)

        self.label = tk.Label(
            self.shell,
            text=spec.label,
            bg=APP_SURFACE_BG,
            fg=APP_TEXT,
            font=fonts.ui,
            cursor=OPEN_HAND_CURSOR,
            anchor=tk.W,
        )
        self.label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12)
        self._bind_tree((self, self.strip, self.shell, self.label))
        self._apply_state()

    def _bind_tree(self, widgets: tuple[tk.Misc, ...]) -> None:
        for widget in widgets:
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event: tk.Event) -> None:
        self.hovered = self.enabled
        self._apply_state()

    def _on_leave(self, _event: tk.Event) -> None:
        self.hovered = False
        self._apply_state()

    def _on_click(self, _event: tk.Event) -> None:
        if self.enabled:
            self.command()

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self._apply_state()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.hovered = False
        self._apply_state()

    def _apply_state(self) -> None:
        cursor = OPEN_HAND_CURSOR if self.enabled else "arrow"
        shell_bg = APP_SURFACE_BG
        if not self.enabled:
            shell_bg = APP_BG
        elif self.selected:
            shell_bg = mix_color(APP_SURFACE_BG, self.accent, 0.18)
        elif self.hovered:
            shell_bg = APP_HOVER_BG
        self.strip.configure(bg=self.accent if self.selected else APP_BG)
        self.shell.configure(bg=shell_bg)
        for widget in (self, self.strip, self.shell, self.label):
            widget.configure(cursor=cursor)
        self.label.configure(bg=shell_bg)


class LauncherCardWidget(tk.Frame):
    def __init__(self, parent: tk.Misc, *, spec: LauncherCardSpec, fonts: LauncherFonts, command) -> None:
        super().__init__(parent, bg=APP_BG, width=CARD_WIDTH, height=CARD_HEIGHT, highlightthickness=0, bd=0)
        self.pack_propagate(False)
        self.spec = spec
        self.accent = accent_from_key(spec.accent_key)
        self.command = command
        self.enabled = True
        self.hovered = False
        self._interactive_widgets: list[tk.Misc] = []

        self.border = tk.Frame(self, bg=APP_BORDER, highlightthickness=0, bd=0)
        self.border.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self.inner = tk.Frame(self.border, bg=APP_PANEL_BG, highlightthickness=0, bd=0)
        self.inner.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        title_row = tk.Frame(self.inner, bg=APP_PANEL_BG)
        title_row.pack(fill=tk.BOTH, expand=True, padx=16, pady=(16, 12))
        self.title_icon = tk.Canvas(
            title_row,
            width=CARD_ICON_SIZE,
            height=CARD_ICON_SIZE,
            bg=APP_PANEL_BG,
            highlightthickness=0,
            bd=0,
        )
        self.title_icon.pack(anchor=tk.CENTER, pady=(0, 10))
        draw_pixel_icon(self.title_icon, spec.icon_kind, self.accent, background=APP_PANEL_BG)
        self.title_label = tk.Label(
            title_row,
            text=spec.title,
            bg=APP_PANEL_BG,
            fg=APP_TEXT,
            font=fonts.ui,
            anchor=tk.CENTER,
            justify=tk.CENTER,
        )
        self.title_label.pack(anchor=tk.CENTER)
        self._bind_hover()
        self._apply_state()

    def _bind_hover(self) -> None:
        widgets = [self, self.border, self.inner, self.title_icon, self.title_label]
        self._interactive_widgets = widgets
        for widget in widgets:
            widget.configure(cursor=OPEN_HAND_CURSOR)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", self._on_click)

    def _on_click(self, _event: tk.Event) -> None:
        if self.enabled:
            self.command()

    def _on_enter(self, _event: tk.Event) -> None:
        self.hovered = True
        self._apply_state()

    def _on_leave(self, _event: tk.Event) -> None:
        self.hovered = False
        self._apply_state()

    def _apply_state(self) -> None:
        if self.enabled:
            border_color = self.accent if self.hovered else APP_BORDER
            inner_bg = APP_PANEL_BG
            text_color = APP_TEXT
            icon_accent = self.accent
            cursor = OPEN_HAND_CURSOR
        else:
            border_color = APP_BORDER
            inner_bg = APP_SURFACE_BG
            text_color = APP_MUTED_TEXT
            icon_accent = mix_color(self.accent, APP_BORDER, 0.65)
            cursor = "arrow"
        self.border.configure(bg=border_color)
        self.inner.configure(bg=inner_bg)
        self.title_icon.configure(bg=inner_bg)
        self.title_label.configure(bg=inner_bg, fg=text_color)
        for widget in (self, self.border, self.inner, self.title_icon, self.title_label):
            widget.configure(cursor=cursor)
        draw_pixel_icon(self.title_icon, self.spec.icon_kind, icon_accent, background=inner_bg)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.hovered = False
        self._apply_state()

    @property
    def interactive_widgets(self) -> list[tk.Misc]:
        return list(self._interactive_widgets)


class PixelFixStudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.project_root = Path(__file__).resolve().parents[2]
        self.runtime_root = runtime_root(self.project_root)
        self.root.title("Pixel-Fix Studio")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.resizable(False, False)
        self.root.configure(background=APP_BG)

        self.sidebar_widgets: dict[str, SidebarItemWidget] = {}
        self.launcher_cards: dict[str, LauncherCardWidget] = {}
        self.card_tooltips: dict[str, list[Tooltip]] = {}
        self.view_frames: dict[str, tk.Frame] = {}
        self.browser_views: dict[str, AssetBrowserWidgets] = {}
        self.app_installations: dict[str, AppInstallation] = {}
        self._active_launch_processes: dict[str, subprocess.Popen] = {}
        self._image_cache: dict[str, ImageTk.PhotoImage] = {}
        self.status_var = tk.StringVar(value=DEFAULT_STATUS)
        self.status_detail_var = tk.StringVar(value=DEFAULT_STATUS_DETAIL)
        self.selected_sidebar_key = SIDEBAR_PRIMARY_ITEMS[0].key
        self.selected_recent_path: Path | None = None
        self.recent_items: list[RecentProjectItem] = []

        saved_settings = load_launcher_settings()
        self.settings = resolve_initial_settings(self.project_root, saved_settings)
        if self.settings != saved_settings:
            save_launcher_settings(self.settings)

        self.pixel_fix_2d_dir_var = tk.StringVar(value=self.settings.pixel_fix_2d_install_dir)
        self.pixel_fix_3d_dir_var = tk.StringVar(value=self.settings.pixel_fix_3d_install_dir)
        self.pixel_fix_2d_validation_var = tk.StringVar(value="")
        self.pixel_fix_3d_validation_var = tk.StringVar(value="")
        self.pixel_fix_2d_env_var = tk.StringVar(value="")
        self.pixel_fix_3d_env_var = tk.StringVar(value="")
        self.pixel_fix_2d_dir_var.trace_add("write", self._on_settings_var_changed)
        self.pixel_fix_3d_dir_var.trace_add("write", self._on_settings_var_changed)

        self._configure_window_icon()
        self._configure_theme()
        self._build_ui()
        self._refresh_settings_validation()
        self._refresh_app_installations()
        self._show_view(self.selected_sidebar_key)
        self.root.bind("<Escape>", lambda _event: self.root.destroy())

    def _resource_path(self, relative_path: str) -> Path:
        if hasattr(sys, "_MEIPASS"):
            base = Path(getattr(sys, "_MEIPASS")) / "pixel_fix_studio" / "resources"
        else:
            base = Path(__file__).resolve().parent / "resources"
        return base / relative_path

    def _configure_window_icon(self) -> None:
        ico_path = self._resource_path("icons/pixel-fix-studio.ico")
        png_path = self._resource_path("icons/pixel-fix-studio.png")
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

    def _configure_theme(self) -> None:
        font_path = self._resource_path("fonts/pixelmix.ttf")
        self.fonts = build_fonts(self.root, font_path)
        configure_ttk_theme(self.root, self.fonts)

    def _load_photo(self, path: Path, *, size: tuple[int, int]) -> ImageTk.PhotoImage | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        cache_key = f"{path.resolve()}|{stat.st_mtime_ns}|{size[0]}x{size[1]}"
        cached = self._image_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            image = Image.open(path).convert("RGBA")
            image.thumbnail(size, Image.Resampling.NEAREST)
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            offset_x = (size[0] - image.width) // 2
            offset_y = (size[1] - image.height) // 2
            canvas.paste(image, (offset_x, offset_y), image)
            photo = ImageTk.PhotoImage(canvas, master=self.root)
        except OSError:
            return None
        self._image_cache[cache_key] = photo
        return photo

    def _photo_from_image(self, cache_key: str, image: Image.Image) -> ImageTk.PhotoImage:
        cached = self._image_cache.get(cache_key)
        if cached is not None:
            return cached
        photo = ImageTk.PhotoImage(image, master=self.root)
        self._image_cache[cache_key] = photo
        return photo

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=APP_BG)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._build_top_shell(outer)

        body = tk.Frame(outer, bg=APP_BG)
        body.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        sidebar = tk.Frame(body, bg=APP_SURFACE_BG, width=160)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        content = tk.Frame(body, bg=APP_BG)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        self._build_views(content)

        self._build_status_bar(outer)

    def _build_top_shell(self, parent: tk.Misc) -> None:
        top = tk.Frame(parent, bg=APP_BG)
        top.pack(fill=tk.X)

        title_row = tk.Frame(top, bg=APP_BG)
        title_row.pack(fill=tk.X)

        title_block = tk.Frame(title_row, bg=APP_BG)
        title_block.pack(side=tk.LEFT, anchor=tk.W)
        title_line = tk.Frame(title_block, bg=APP_BG)
        title_line.pack(anchor=tk.W)
        title_icon = self._load_photo(self._resource_path("icons/pixel-fix-studio.png"), size=(32, 32))
        if title_icon is not None:
            icon_label = tk.Label(title_line, image=title_icon, bg=APP_BG, bd=0)
            icon_label.image = title_icon
            icon_label.pack(side=tk.LEFT, padx=(0, 6))
        title_label = tk.Label(
            title_line,
            text="PIXEL-FIX STUDIO",
            bg=APP_BG,
            fg=APP_TEXT,
            font=self.fonts.title,
            anchor=tk.W,
        )
        title_label.pack(side=tk.LEFT)

        right_meta = tk.Frame(title_row, bg=APP_BG)
        right_meta.pack(side=tk.RIGHT, anchor=tk.E)
        version = tk.Label(
            right_meta,
            text=f"Version: {__version__}",
            bg=APP_BG,
            fg=APP_TEXT,
            font=self.fonts.menu,
        )
        version.pack(side=tk.LEFT)

    def _build_sidebar(self, parent: tk.Misc) -> None:
        top_group = tk.Frame(parent, bg=APP_SURFACE_BG)
        top_group.pack(fill=tk.X, pady=(12, 0))
        for spec in SIDEBAR_PRIMARY_ITEMS:
            widget = SidebarItemWidget(top_group, spec=spec, fonts=self.fonts, command=lambda value=spec: self._select_sidebar(value))
            widget.pack(fill=tk.X, pady=(0, 4))
            self.sidebar_widgets[spec.key] = widget

        spacer = tk.Frame(parent, bg=APP_SURFACE_BG)
        spacer.pack(fill=tk.BOTH, expand=True)

        bottom_group = tk.Frame(parent, bg=APP_SURFACE_BG)
        bottom_group.pack(fill=tk.X, pady=(0, 12))
        for spec in SIDEBAR_SECONDARY_ITEMS:
            widget = SidebarItemWidget(bottom_group, spec=spec, fonts=self.fonts, command=lambda value=spec: self._select_sidebar(value))
            widget.pack(fill=tk.X, pady=(0, 4))
            self.sidebar_widgets[spec.key] = widget

    def _build_views(self, parent: tk.Misc) -> None:
        projects = tk.Frame(parent, bg=APP_BG)
        self.view_frames["projects"] = projects
        self._build_projects_view(projects)

        palettes = tk.Frame(parent, bg=APP_BG)
        self.view_frames["palettes"] = palettes
        self.browser_views["palettes"] = self._build_asset_browser_view(palettes, key="palettes", title="Palettes")

        textures = tk.Frame(parent, bg=APP_BG)
        self.view_frames["textures"] = textures
        self.browser_views["textures"] = self._build_asset_browser_view(textures, key="textures", title="Textures")

        settings = tk.Frame(parent, bg=APP_BG)
        self.view_frames["settings"] = settings
        self._build_settings_view(settings)

        docs = tk.Frame(parent, bg=APP_BG)
        self.view_frames["docs"] = docs
        self._build_docs_view(docs)

    def _build_projects_view(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1, uniform="main")
        parent.grid_rowconfigure(1, weight=1, uniform="main")
        self._build_hero_area(parent)

        bottom = tk.Frame(parent, bg=APP_BG)
        bottom.grid(row=1, column=0, sticky="nsew")
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(0, weight=1)

        left_shell, left_body = self._make_panel(bottom, title="Recent Projects", title_bg=APP_BG, borderless_body=True)
        left_shell.grid(row=0, column=0, sticky="nsew")
        self.recent_projects_body = left_body

    def _build_hero_area(self, parent: tk.Misc) -> None:
        hero = tk.Frame(parent, bg=APP_BG)
        hero.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        self.hero_canvas = tk.Canvas(hero, bg=APP_BG, highlightthickness=0, bd=0)
        self.hero_canvas.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
        self.hero_canvas.bind("<Configure>", self._redraw_backdrop)

        card_row = tk.Frame(hero, bg=APP_BG)
        card_row.place(relx=0.5, rely=0.48, anchor=tk.CENTER)

        for index, spec in enumerate(LAUNCHER_CARDS):
            card = LauncherCardWidget(
                card_row,
                spec=spec,
                fonts=self.fonts,
                command=lambda value=spec: self._launch_from_card(value.key),
            )
            card.grid(row=0, column=index, padx=10)
            self.launcher_cards[spec.key] = card
            self.card_tooltips[spec.key] = [Tooltip(widget) for widget in card.interactive_widgets]

    def _build_asset_browser_view(self, parent: tk.Misc, *, key: str, title: str) -> AssetBrowserWidgets:
        shell, body = self._make_panel(parent, title=title)
        shell.pack(fill=tk.BOTH, expand=True)

        message_var = tk.StringVar(value="")
        tk.Label(
            body,
            textvariable=message_var,
            bg=APP_PANEL_BG,
            fg=APP_MUTED_TEXT,
            font=self.fonts.small,
            anchor=tk.W,
        ).pack(fill=tk.X, padx=8, pady=(8, 0))

        toolbar = tk.Frame(body, bg=APP_PANEL_BG)
        toolbar.pack(fill=tk.X, padx=8, pady=(8, 0))

        add_button = ttk.Button(toolbar, text="Add", command=lambda browser_key=key: self._add_asset_item(browser_key), style="Compact.TButton")
        add_button.pack(side=tk.LEFT)
        new_folder_button = ttk.Button(
            toolbar,
            text="New Folder",
            command=lambda browser_key=key: self._create_asset_folder(browser_key),
            style="Compact.TButton",
        )
        new_folder_button.pack(side=tk.LEFT, padx=(4, 0))
        move_button = ttk.Button(toolbar, text="Move To", command=lambda browser_key=key: self._move_selected_asset(browser_key), style="Compact.TButton")
        move_button.pack(side=tk.LEFT, padx=(4, 0))
        delete_button = ttk.Button(toolbar, text="Delete", command=lambda browser_key=key: self._delete_selected_asset(browser_key), style="Compact.TButton")
        delete_button.pack(side=tk.LEFT, padx=(4, 0))
        refresh_button = ttk.Button(toolbar, text="Refresh", command=lambda browser_key=key: self._refresh_asset_browser(browser_key), style="Compact.TButton")
        refresh_button.pack(side=tk.LEFT, padx=(4, 0))

        folder_var = tk.StringVar(value="")
        tk.Label(
            toolbar,
            textvariable=folder_var,
            bg=APP_PANEL_BG,
            fg=APP_MUTED_TEXT,
            font=self.fonts.small,
            anchor=tk.E,
        ).pack(side=tk.RIGHT)

        split = tk.Frame(body, bg=APP_PANEL_BG)
        split.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        split.grid_columnconfigure(1, weight=1)
        split.grid_rowconfigure(0, weight=1)

        tree_shell = tk.Frame(split, bg=APP_PANEL_BG, width=ASSET_TREE_WIDTH)
        tree_shell.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        tree_shell.pack_propagate(False)

        tree = ttk.Treeview(tree_shell, show="tree", selectmode="browse")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll = ttk.Scrollbar(tree_shell, orient=tk.VERTICAL, command=tree.yview)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.bind("<<TreeviewSelect>>", lambda _event, browser_key=key: self._on_asset_folder_selected(browser_key))

        preview_shell = tk.Frame(split, bg=APP_PANEL_BG)
        preview_shell.grid(row=0, column=1, sticky="nsew")
        preview_shell.grid_columnconfigure(0, weight=1)
        preview_shell.grid_rowconfigure(0, weight=1)

        preview_canvas = tk.Canvas(preview_shell, bg=APP_PANEL_BG, highlightthickness=0, bd=0)
        preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_shell, orient=tk.VERTICAL, command=preview_canvas.yview)
        preview_scroll.grid(row=0, column=1, sticky="ns")
        preview_canvas.configure(yscrollcommand=preview_scroll.set)

        preview_inner = tk.Frame(preview_canvas, bg=APP_PANEL_BG)
        preview_window = preview_canvas.create_window((0, 0), window=preview_inner, anchor=tk.NW)
        preview_inner.bind(
            "<Configure>",
            lambda _event, canvas=preview_canvas: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        preview_canvas.bind("<Configure>", lambda event, browser_key=key: self._on_asset_preview_canvas_configure(browser_key, event))

        return AssetBrowserWidgets(
            key=key,
            title=title,
            frame=shell,
            message_var=message_var,
            folder_var=folder_var,
            tree=tree,
            preview_canvas=preview_canvas,
            preview_inner=preview_inner,
            preview_window=preview_window,
            add_button=add_button,
            new_folder_button=new_folder_button,
            move_button=move_button,
            delete_button=delete_button,
            refresh_button=refresh_button,
        )

    def _build_settings_view(self, parent: tk.Misc) -> None:
        shell, body = self._make_panel(parent, title="Settings")
        shell.pack(fill=tk.BOTH, expand=True)
        body.grid_columnconfigure(1, weight=1)

        intro = tk.Label(
            body,
            text="Select custom Pixel-Fix 2D and Pixel-Fix 3D install folders.",
            bg=APP_PANEL_BG,
            fg=APP_TEXT,
            font=self.fonts.ui,
            anchor=tk.W,
        )
        intro.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 8))

        self._build_settings_repo_row(
            body,
            row_index=1,
            label="Pixel-Fix 2D",
            value_var=self.pixel_fix_2d_dir_var,
            validation_var=self.pixel_fix_2d_validation_var,
            env_var=self.pixel_fix_2d_env_var,
            browse_command=lambda: self._browse_repo_dir("2d"),
        )
        self._build_settings_repo_row(
            body,
            row_index=4,
            label="Pixel-Fix 3D",
            value_var=self.pixel_fix_3d_dir_var,
            validation_var=self.pixel_fix_3d_validation_var,
            env_var=self.pixel_fix_3d_env_var,
            browse_command=lambda: self._browse_repo_dir("3d"),
        )

        actions = tk.Frame(body, bg=APP_PANEL_BG)
        actions.grid(row=7, column=0, columnspan=3, sticky="w", padx=12, pady=(16, 12))
        ttk.Button(actions, text="Auto-detect", command=self._auto_detect_settings, style="Compact.TButton").pack(side=tk.LEFT)
        ttk.Button(actions, text="Save", command=self._save_settings, style="Compact.TButton").pack(side=tk.LEFT, padx=(6, 0))

        storage_label = tk.Label(
            body,
            text=f"Launcher settings: {launcher_settings_path()}",
            bg=APP_PANEL_BG,
            fg=APP_MUTED_TEXT,
            font=self.fonts.small,
            anchor=tk.W,
        )
        storage_label.grid(row=8, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))

    def _build_settings_repo_row(
        self,
        parent: tk.Misc,
        *,
        row_index: int,
        label: str,
        value_var: tk.StringVar,
        validation_var: tk.StringVar,
        env_var: tk.StringVar,
        browse_command,
    ) -> None:
        tk.Label(parent, text=label, bg=APP_PANEL_BG, fg=APP_TEXT, font=self.fonts.ui, anchor=tk.W).grid(
            row=row_index,
            column=0,
            sticky="w",
            padx=(12, 8),
            pady=(4, 0),
        )
        ttk.Entry(parent, textvariable=value_var).grid(row=row_index, column=1, sticky="ew", pady=(4, 0))
        ttk.Button(parent, text="Browse...", command=browse_command, style="Compact.TButton").grid(
            row=row_index,
            column=2,
            sticky="w",
            padx=(6, 12),
            pady=(4, 0),
        )
        tk.Label(parent, textvariable=validation_var, bg=APP_PANEL_BG, fg=APP_MUTED_TEXT, font=self.fonts.small, anchor=tk.W).grid(
            row=row_index + 1,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(0, 12),
            pady=(2, 0),
        )
        tk.Label(parent, textvariable=env_var, bg=APP_PANEL_BG, fg=APP_MUTED_TEXT, font=self.fonts.small, anchor=tk.W).grid(
            row=row_index + 2,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(0, 12),
            pady=(2, 0),
        )

    def _build_docs_view(self, parent: tk.Misc) -> None:
        shell, body = self._make_panel(parent, title="Docs")
        shell.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            body,
            text="Docs shortcuts are still placeholders in this build.",
            bg=APP_PANEL_BG,
            fg=APP_MUTED_TEXT,
            font=self.fonts.ui,
            anchor=tk.W,
            justify=tk.LEFT,
            padx=12,
            pady=12,
        ).pack(fill=tk.BOTH, expand=True)

    def _build_status_bar(self, parent: tk.Misc) -> None:
        status = tk.Frame(parent, bg=APP_STATUS_BG)
        status.pack(fill=tk.X, pady=(16, 0))
        left = tk.Label(
            status,
            textvariable=self.status_var,
            bg=APP_STATUS_BG,
            fg=APP_TEXT,
            font=self.fonts.ui,
            anchor=tk.W,
            padx=12,
            pady=8,
        )
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        right = tk.Label(
            status,
            textvariable=self.status_detail_var,
            bg=APP_STATUS_BG,
            fg=APP_MUTED_TEXT,
            font=self.fonts.small,
            anchor=tk.E,
            padx=12,
            pady=8,
        )
        right.pack(side=tk.RIGHT)

    def _make_panel(
        self,
        parent: tk.Misc,
        *,
        title: str,
        title_bg: str = APP_BLACK,
        borderless_body: bool = False,
    ) -> tuple[tk.Frame, tk.Frame]:
        shell = tk.Frame(parent, bg=APP_BG)
        title_label = tk.Label(
            shell,
            text=title,
            bg=title_bg,
            fg=APP_TEXT,
            font=self.fonts.section,
            anchor=tk.W,
            padx=12,
            pady=6,
        )
        title_label.pack(anchor=tk.W, pady=(0, 6))
        if borderless_body:
            body = tk.Frame(shell, bg=APP_BG)
            body.pack(fill=tk.BOTH, expand=True)
            return shell, body
        body_border = tk.Frame(shell, bg=APP_BORDER)
        body_border.pack(fill=tk.BOTH, expand=True)
        body = tk.Frame(body_border, bg=APP_PANEL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        return shell, body

    def _show_view(self, key: str) -> None:
        for frame in self.view_frames.values():
            frame.pack_forget()
        view = self.view_frames.get(key)
        if view is None:
            return
        view.pack(fill=tk.BOTH, expand=True)
        self.selected_sidebar_key = key
        self._refresh_sidebar()
        if key == "projects":
            self._refresh_recent_projects()
        elif key in {"palettes", "textures"}:
            self._refresh_asset_browser(key)
        elif key == "settings":
            self._refresh_settings_validation()

    def _refresh_sidebar(self) -> None:
        for sidebar_key, widget in self.sidebar_widgets.items():
            widget.set_selected(sidebar_key == self.selected_sidebar_key)

    def _select_sidebar(self, spec: SidebarItemSpec) -> None:
        self._show_view(spec.key)
        self._set_status(f"{spec.label} selected.", spec.description)

    def _refresh_recent_projects(self) -> None:
        for child in self.recent_projects_body.winfo_children():
            child.destroy()

        self.recent_items = load_recent_project_items()
        if self.recent_items and self.selected_recent_path not in {item.path for item in self.recent_items}:
            self.selected_recent_path = self.recent_items[0].path
        if not self.recent_items:
            self.selected_recent_path = None
            tk.Label(
                self.recent_projects_body,
                text="No recent projects found in Pixel-Fix 2D app data.",
                bg=APP_BG,
                fg=APP_MUTED_TEXT,
                font=self.fonts.ui,
                anchor=tk.W,
            ).pack(fill=tk.X, padx=12, pady=(8, 0))
            return

        list_frame = tk.Frame(self.recent_projects_body, bg=APP_BG)
        list_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(list_frame, bg=APP_BG, highlightthickness=0, bd=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = tk.Frame(canvas, bg=APP_BG)
        window_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        inner.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))

        for item in self.recent_items:
            selected = item.path == self.selected_recent_path
            self._build_recent_project_row(inner, item, selected=selected)

    def _build_recent_project_row(self, parent: tk.Misc, item: RecentProjectItem, *, selected: bool) -> None:
        border_color = APP_ACCENT if selected else APP_BORDER
        row_bg = APP_HOVER_BG if selected else APP_BG

        border = tk.Frame(parent, bg=border_color)
        border.pack(fill=tk.X, padx=8, pady=(0, 6))
        shell = tk.Frame(border, bg=row_bg)
        shell.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        thumbnail = self._load_photo(item.path, size=(RECENT_THUMBNAIL_SIZE, RECENT_THUMBNAIL_SIZE)) if item.thumbnail_supported else None
        thumb_label = tk.Label(shell, bg=APP_SURFACE_BG, bd=0)
        thumb_label.pack(side=tk.LEFT, padx=(6, 8), pady=6)
        if thumbnail is not None:
            thumb_label.configure(image=thumbnail)
            thumb_label.image = thumbnail
        else:
            thumb_label.configure(width=RECENT_THUMBNAIL_SIZE, height=RECENT_THUMBNAIL_SIZE, text=" ", bg=APP_SURFACE_BG)

        text_shell = tk.Frame(shell, bg=row_bg)
        text_shell.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=6)
        name_label = tk.Label(text_shell, text=item.name, bg=row_bg, fg=APP_TEXT, font=self.fonts.ui, anchor=tk.W, cursor=OPEN_HAND_CURSOR)
        name_label.pack(fill=tk.X)
        detail_label = tk.Label(
            text_shell,
            text=item.detail,
            bg=row_bg,
            fg=APP_MUTED_TEXT,
            font=self.fonts.small,
            anchor=tk.W,
            cursor=OPEN_HAND_CURSOR,
        )
        detail_label.pack(fill=tk.X, pady=(2, 0))

        open_button = ttk.Button(shell, text="Open", command=lambda value=item: self._open_recent_project(value), style="Compact.TButton")
        open_button.pack(side=tk.RIGHT, padx=6, pady=6)

        for widget in (border, shell, thumb_label, text_shell, name_label, detail_label):
            widget.bind("<Button-1>", lambda _event, value=item: self._select_recent_project(value))
            widget.bind("<Double-Button-1>", lambda _event, value=item: self._open_recent_project(value))

    def _select_recent_project(self, item: RecentProjectItem) -> None:
        self.selected_recent_path = item.path
        self._refresh_recent_projects()
        self._set_status(f"Selected: {item.name}", item.detail)

    def _open_recent_project(self, item: RecentProjectItem) -> None:
        if not item.path.exists():
            self._set_status("Recent project missing.", str(item.path))
            return
        installation = self._installation_for_key("pixel_fix_2d")
        if not installation.installed:
            messagebox.showerror("Pixel-Fix 2D not installed", installation.missing_app_message)
            self._show_view("settings")
            self._set_status("Pixel-Fix 2D is not installed.", installation.detail)
            return
        self._launch_installation(installation, open_path=item.path, success_message=f"Opening {item.name} in Pixel-Fix 2D.")

    def _asset_root(self, browser_key: str) -> Path | None:
        if browser_key == "palettes":
            installation = self._installation_for_key("pixel_fix_2d")
        else:
            installation = self._installation_for_key("pixel_fix_3d")
        if not installation.installed or installation.data_root is None or not installation.data_root.exists():
            return None
        return installation.data_root

    def _asset_missing_message(self, browser_key: str) -> str:
        if browser_key == "palettes":
            return "Install Pixel-Fix 2D or choose a valid install folder in Settings to browse palettes."
        return "Install Pixel-Fix 3D or choose a valid install folder in Settings to browse textures."

    def _refresh_asset_browser(self, browser_key: str, *, preserve_folder: Path | None = None, preserve_selection: Path | None = None) -> None:
        state = self.browser_views[browser_key]
        root = self._asset_root(browser_key)
        if root is None:
            state.message_var.set(self._asset_missing_message(browser_key))
            state.folder_var.set("")
            state.current_folder = None
            state.selected_item_path = None
            state.items_by_path.clear()
            state.tree_paths.clear()
            state.path_ids.clear()
            state.tree.delete(*state.tree.get_children())
            for child in state.preview_inner.winfo_children():
                child.destroy()
            self._update_asset_buttons(browser_key)
            return

        nodes = list_library_folders(root)
        state.tree.delete(*state.tree.get_children())
        state.tree_paths.clear()
        state.path_ids.clear()

        children_by_parent: dict[str | None, list[Path]] = {}
        labels_by_path: dict[Path, str] = {}
        keys_by_path: dict[Path, str] = {}
        for node in nodes:
            labels_by_path[node.path] = node.label
            keys_by_path[node.path] = node.key
            children_by_parent.setdefault(node.parent_key, []).append(node.path)

        path_to_tree_id: dict[Path, str] = {}

        def insert_children(parent_id: str, parent_key: str) -> None:
            for child_path in children_by_parent.get(parent_key, []):
                child_id = state.tree.insert(parent_id, tk.END, text=labels_by_path[child_path], open=True)
                path_to_tree_id[child_path] = child_id
                state.tree_paths[child_id] = child_path
                state.path_ids[child_path] = child_id
                insert_children(child_id, keys_by_path[child_path])

        root_node = nodes[0]
        root_id = state.tree.insert("", tk.END, text=state.title, open=True)
        state.tree_paths[root_id] = root_node.path
        state.path_ids[root_node.path] = root_id
        path_to_tree_id[root_node.path] = root_id
        insert_children(root_id, root_node.key)

        desired_folder = preserve_folder or state.current_folder or root
        if not self._is_within_root(root, desired_folder) or not desired_folder.exists():
            desired_folder = root
        state.current_folder = desired_folder.resolve()

        selected_id = path_to_tree_id.get(state.current_folder)
        if selected_id is not None:
            state.tree.selection_set(selected_id)
            state.tree.focus(selected_id)
        state.message_var.set(f"Root: {root}")
        relative = state.current_folder.relative_to(root)
        state.folder_var.set("Folder: /" if relative == Path(".") else f"Folder: /{relative.as_posix()}")
        state.selected_item_path = preserve_selection if preserve_selection and preserve_selection.exists() else state.selected_item_path
        self._refresh_asset_items(browser_key)

    def _on_asset_folder_selected(self, browser_key: str) -> None:
        state = self.browser_views[browser_key]
        selection = state.tree.selection()
        if not selection:
            return
        folder = state.tree_paths.get(selection[0])
        if folder is None:
            return
        state.current_folder = folder
        if state.selected_item_path is not None and state.selected_item_path.parent != folder:
            state.selected_item_path = None
        root = self._asset_root(browser_key)
        if root is not None:
            relative = folder.relative_to(root)
            state.folder_var.set("Folder: /" if relative == Path(".") else f"Folder: /{relative.as_posix()}")
        self._refresh_asset_items(browser_key)

    def _on_asset_preview_canvas_configure(self, browser_key: str, event: tk.Event) -> None:
        state = self.browser_views[browser_key]
        state.preview_canvas.itemconfigure(state.preview_window, width=event.width)
        if abs(event.width - state.last_canvas_width) >= 24:
            state.last_canvas_width = event.width
            if state.current_folder is not None:
                self._refresh_asset_items(browser_key)

    def _refresh_asset_items(self, browser_key: str) -> None:
        state = self.browser_views[browser_key]
        root = self._asset_root(browser_key)
        for child in state.preview_inner.winfo_children():
            child.destroy()
        if root is None or state.current_folder is None:
            self._update_asset_buttons(browser_key)
            return

        items = list_palette_items(state.current_folder) if browser_key == "palettes" else list_texture_items(state.current_folder)
        state.items_by_path = {item.path: item for item in items}
        if state.selected_item_path not in state.items_by_path:
            state.selected_item_path = None

        if not items:
            tk.Label(
                state.preview_inner,
                text=f"No {browser_key} found in this folder.",
                bg=APP_PANEL_BG,
                fg=APP_MUTED_TEXT,
                font=self.fonts.ui,
                anchor=tk.W,
            ).pack(fill=tk.X, padx=8, pady=8)
            self._update_asset_buttons(browser_key)
            return

        available_width = max(state.preview_canvas.winfo_width(), 360)
        columns = max(1, min(4, available_width // 128))
        for column in range(columns):
            state.preview_inner.grid_columnconfigure(column, weight=1)

        for index, item in enumerate(items):
            selected = item.path == state.selected_item_path
            row = index // columns
            column = index % columns
            self._build_asset_card(state.preview_inner, browser_key, item, selected=selected).grid(row=row, column=column, padx=4, pady=4, sticky="nw")

        self._update_asset_buttons(browser_key)

    def _build_asset_card(self, parent: tk.Misc, browser_key: str, item: AssetItem, *, selected: bool) -> tk.Frame:
        border = tk.Frame(parent, bg=APP_ACCENT if selected else APP_BORDER)
        shell = tk.Frame(border, bg=APP_PANEL_BG, width=ASSET_CARD_WIDTH, height=ASSET_CARD_HEIGHT)
        shell.pack(padx=1, pady=1)
        shell.pack_propagate(False)

        preview_label = tk.Label(shell, bg=APP_PANEL_BG, bd=0)
        preview_label.pack(pady=(6, 4))
        preview = self._palette_preview_photo(item) if isinstance(item, PaletteItem) else self._texture_preview_photo(item)
        if preview is not None:
            preview_label.configure(image=preview)
            preview_label.image = preview
        else:
            preview_label.configure(width=ASSET_PREVIEW_SIZE[0], height=ASSET_PREVIEW_SIZE[1], text=" ", bg=APP_SURFACE_BG)

        name_label = tk.Label(
            shell,
            text=item.name,
            bg=APP_PANEL_BG,
            fg=APP_TEXT,
            font=self.fonts.small,
            justify=tk.CENTER,
            wraplength=ASSET_CARD_WIDTH - 10,
            cursor=OPEN_HAND_CURSOR,
        )
        name_label.pack(fill=tk.X, padx=4)

        detail_label = tk.Label(
            shell,
            text=self._asset_item_detail(item),
            bg=APP_PANEL_BG,
            fg=APP_MUTED_TEXT,
            font=self.fonts.small,
            justify=tk.CENTER,
            wraplength=ASSET_CARD_WIDTH - 10,
            cursor=OPEN_HAND_CURSOR,
        )
        detail_label.pack(fill=tk.X, padx=4, pady=(2, 4))

        for widget in (border, shell, preview_label, name_label, detail_label):
            widget.configure(cursor=OPEN_HAND_CURSOR)
            widget.bind("<Button-1>", lambda _event, browser=browser_key, path=item.path: self._select_asset_item(browser, path))
        return border

    def _asset_item_detail(self, item: AssetItem) -> str:
        if isinstance(item, PaletteItem):
            if item.error:
                return item.error
            return f"{len(item.colors)} colours"
        if item.error:
            return item.error
        if item.size is None:
            return "Preview unavailable"
        return f"{item.size[0]}x{item.size[1]}"

    def _select_asset_item(self, browser_key: str, item_path: Path) -> None:
        state = self.browser_views[browser_key]
        state.selected_item_path = item_path
        self._refresh_asset_items(browser_key)
        self._set_status(f"Selected: {item_path.name}", str(item_path))

    def _update_asset_buttons(self, browser_key: str) -> None:
        state = self.browser_views[browser_key]
        root = self._asset_root(browser_key)
        has_root = root is not None and state.current_folder is not None
        has_selection = state.selected_item_path is not None
        state.add_button.configure(state=tk.NORMAL if has_root else tk.DISABLED)
        state.new_folder_button.configure(state=tk.NORMAL if has_root else tk.DISABLED)
        state.refresh_button.configure(state=tk.NORMAL if root is not None else tk.DISABLED)
        selection_state = tk.NORMAL if has_selection else tk.DISABLED
        state.move_button.configure(state=selection_state)
        state.delete_button.configure(state=selection_state)

    def _add_asset_item(self, browser_key: str) -> None:
        state = self.browser_views[browser_key]
        root = self._asset_root(browser_key)
        if root is None or state.current_folder is None:
            return
        if browser_key == "palettes":
            source = filedialog.askopenfilename(title="Add palette", filetypes=[("GPL palettes", "*.gpl")])
        else:
            source = filedialog.askopenfilename(
                title="Add texture",
                filetypes=[("Images", "*.png *.bmp *.gif *.webp *.jpg *.jpeg"), ("All files", "*.*")],
            )
        if not source:
            return
        try:
            destination = (
                import_palette_file(root, state.current_folder, Path(source))
                if browser_key == "palettes"
                else import_texture_file(root, state.current_folder, Path(source))
            )
        except (FileExistsError, FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror("Import failed", str(exc))
            self._set_status("Import failed.", str(exc))
            return
        self._refresh_asset_browser(browser_key, preserve_folder=destination.parent, preserve_selection=destination)
        self._set_status(f"Imported {destination.name}.", str(destination))

    def _create_asset_folder(self, browser_key: str) -> None:
        state = self.browser_views[browser_key]
        root = self._asset_root(browser_key)
        if root is None or state.current_folder is None:
            return
        name = simpledialog.askstring("New Folder", f"Create a new {browser_key[:-1]} folder:", parent=self.root)
        if name is None:
            return
        try:
            destination = create_library_folder(root, state.current_folder, name)
        except (FileExistsError, OSError, ValueError) as exc:
            messagebox.showerror("Create folder failed", str(exc))
            self._set_status("Create folder failed.", str(exc))
            return
        self._refresh_asset_browser(browser_key, preserve_folder=destination)
        self._set_status(f"Created folder {destination.name}.", str(destination))

    def _move_selected_asset(self, browser_key: str) -> None:
        state = self.browser_views[browser_key]
        root = self._asset_root(browser_key)
        if root is None or state.selected_item_path is None:
            return
        target = filedialog.askdirectory(title="Move to folder", initialdir=str(root), mustexist=True)
        if not target:
            return
        try:
            destination = move_library_item(root, state.selected_item_path, Path(target))
        except (FileExistsError, FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror("Move failed", str(exc))
            self._set_status("Move failed.", str(exc))
            return
        self._refresh_asset_browser(browser_key, preserve_folder=destination.parent, preserve_selection=destination)
        self._set_status(f"Moved {destination.name}.", str(destination))

    def _delete_selected_asset(self, browser_key: str) -> None:
        state = self.browser_views[browser_key]
        root = self._asset_root(browser_key)
        if root is None or state.selected_item_path is None:
            return
        target_path = state.selected_item_path
        if not messagebox.askyesno("Delete file", f"Delete {target_path.name} permanently?"):
            return
        try:
            delete_library_item(root, target_path)
        except (FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror("Delete failed", str(exc))
            self._set_status("Delete failed.", str(exc))
            return
        self._refresh_asset_browser(browser_key, preserve_folder=state.current_folder)
        self._set_status(f"Deleted {target_path.name}.", str(target_path))

    def _installation_for_key(self, app_key: str) -> AppInstallation:
        installation = self.app_installations.get(app_key)
        if installation is None:
            installation = resolve_app_installation(self.project_root, self.settings, app_key)
            self.app_installations[app_key] = installation
        return installation

    def _refresh_app_installations(self) -> None:
        for app_key in ("pixel_fix_2d", "pixel_fix_3d"):
            installation = resolve_app_installation(self.project_root, self.settings, app_key)
            self.app_installations[app_key] = installation
            card = self.launcher_cards.get(app_key)
            if card is not None:
                card.set_enabled(installation.installed)
            tooltips = self.card_tooltips.get(app_key, ())
            for tooltip in tooltips:
                tooltip.set_text("" if installation.installed else installation.missing_app_message)

    def _launch_from_card(self, app_key: str) -> None:
        installation = self._installation_for_key(app_key)
        if not installation.installed:
            self._set_status(installation.missing_app_message, installation.detail)
            return
        self._launch_installation(installation, success_message=f"Launching {installation.display_name}.")

    def _launch_installation(
        self,
        installation: AppInstallation,
        *,
        open_path: Path | None = None,
        success_message: str,
    ) -> None:
        existing_process = self._active_launch_processes.get(installation.key)
        if existing_process is not None and existing_process.poll() is None:
            detail = installation.launch_detail or f"PID: {existing_process.pid}"
            self._set_status(f"{installation.display_name} is already running.", detail)
            return
        self._active_launch_processes.pop(installation.key, None)
        try:
            request = build_launch_request(installation, open_path=open_path)
            process = subprocess.Popen(request.command, cwd=str(request.cwd), env=request.env)
        except (OSError, ValueError) as exc:
            messagebox.showerror(f"Failed to launch {installation.display_name}", str(exc))
            self._set_status(f"Failed to launch {installation.display_name}.", str(exc))
            return
        self._active_launch_processes[installation.key] = process
        detail = installation.launch_detail
        if process.pid:
            detail = f"{detail} | PID: {process.pid}" if detail else f"PID: {process.pid}"
        self._set_status(success_message, detail)

    def _browse_repo_dir(self, repo_key: str) -> None:
        initial_dir = self.pixel_fix_2d_dir_var.get().strip() if repo_key == "2d" else self.pixel_fix_3d_dir_var.get().strip()
        if not initial_dir:
            initial_dir = str(self.runtime_root)
        selected = filedialog.askdirectory(title="Select install folder", initialdir=initial_dir, mustexist=True)
        if not selected:
            return
        if repo_key == "2d":
            self.pixel_fix_2d_dir_var.set(selected)
        else:
            self.pixel_fix_3d_dir_var.set(selected)

    def _auto_detect_settings(self) -> None:
        detected = detect_default_install_dirs(self.project_root)
        self.pixel_fix_2d_dir_var.set(detected.pixel_fix_2d_install_dir)
        self.pixel_fix_3d_dir_var.set(detected.pixel_fix_3d_install_dir)
        self._refresh_settings_validation()
        self._set_status("Auto-detect complete.", "Bundled and source app folders scanned.")

    def _save_settings(self) -> None:
        two_d_repo, two_d_message = validate_pixel_fix_2d_install_dir(self.pixel_fix_2d_dir_var.get())
        three_d_repo, three_d_message = validate_pixel_fix_3d_install_dir(self.pixel_fix_3d_dir_var.get())

        if self.pixel_fix_2d_dir_var.get().strip() and two_d_repo is None:
            messagebox.showerror("Invalid Pixel-Fix 2D install folder", two_d_message)
            self._set_status("Settings not saved.", two_d_message)
            return
        if self.pixel_fix_3d_dir_var.get().strip() and three_d_repo is None:
            messagebox.showerror("Invalid Pixel-Fix 3D install folder", three_d_message)
            self._set_status("Settings not saved.", three_d_message)
            return

        self.settings = LauncherSettings(
            pixel_fix_2d_install_dir=str(two_d_repo) if two_d_repo is not None else "",
            pixel_fix_3d_install_dir=str(three_d_repo) if three_d_repo is not None else "",
        )
        save_launcher_settings(self.settings)
        self.pixel_fix_2d_dir_var.set(self.settings.pixel_fix_2d_install_dir)
        self.pixel_fix_3d_dir_var.set(self.settings.pixel_fix_3d_install_dir)
        self._refresh_settings_validation()
        self._refresh_app_installations()
        self._refresh_recent_projects()
        self._refresh_asset_browser("palettes")
        self._refresh_asset_browser("textures")
        self._set_status("Settings saved.", str(launcher_settings_path()))

    def _on_settings_var_changed(self, *_args: object) -> None:
        self._refresh_settings_validation()

    def _refresh_settings_validation(self) -> None:
        _two_d_repo, two_d_message = validate_pixel_fix_2d_install_dir(self.pixel_fix_2d_dir_var.get())
        _three_d_repo, three_d_message = validate_pixel_fix_3d_install_dir(self.pixel_fix_3d_dir_var.get())
        two_d_install = resolve_app_installation(
            self.project_root,
            LauncherSettings(pixel_fix_2d_install_dir=self.pixel_fix_2d_dir_var.get().strip(), pixel_fix_3d_install_dir=""),
            "pixel_fix_2d",
        )
        three_d_install = resolve_app_installation(
            self.project_root,
            LauncherSettings(pixel_fix_2d_install_dir="", pixel_fix_3d_install_dir=self.pixel_fix_3d_dir_var.get().strip()),
            "pixel_fix_3d",
        )
        self.pixel_fix_2d_validation_var.set(two_d_message if self.pixel_fix_2d_dir_var.get().strip() else two_d_install.detail)
        self.pixel_fix_3d_validation_var.set(three_d_message if self.pixel_fix_3d_dir_var.get().strip() else three_d_install.detail)
        self.pixel_fix_2d_env_var.set(two_d_install.launch_detail)
        self.pixel_fix_3d_env_var.set(three_d_install.launch_detail)

    def _palette_preview_photo(self, item: PaletteItem) -> ImageTk.PhotoImage:
        try:
            stat = item.path.stat()
            cache_key = f"palette|{item.path.resolve()}|{stat.st_mtime_ns}|{ASSET_PREVIEW_SIZE[0]}x{ASSET_PREVIEW_SIZE[1]}"
        except OSError:
            cache_key = f"palette|{item.path.resolve()}|missing"
        image = build_palette_preview_image(item.colors, ASSET_PREVIEW_SIZE, background=APP_SURFACE_BG)
        return self._photo_from_image(cache_key, image)

    def _texture_preview_photo(self, item: TextureItem) -> ImageTk.PhotoImage | None:
        return self._load_photo(item.path, size=ASSET_PREVIEW_SIZE)

    def _redraw_backdrop(self, event: tk.Event) -> None:
        width = max(200, int(event.width))
        height = max(200, int(event.height))
        self.hero_canvas.delete("all")
        self.hero_canvas.create_rectangle(0, 0, width, height, fill=APP_BG, outline="")
        for y in range(0, height, 6):
            self.hero_canvas.create_line(0, y, width, y, fill=APP_SCANLINE)

        cube_size = min(width, height) * 0.22
        center_x = width * 0.52
        center_y = height * 0.55
        left = center_x - cube_size * 0.5
        top = center_y - cube_size * 0.7
        front = (
            left,
            top + cube_size * 0.25,
            left + cube_size * 0.48,
            top,
            left + cube_size * 0.48,
            top + cube_size * 0.7,
            left,
            top + cube_size * 0.95,
        )
        right = (
            left + cube_size * 0.48,
            top,
            left + cube_size,
            top + cube_size * 0.25,
            left + cube_size,
            top + cube_size * 0.95,
            left + cube_size * 0.48,
            top + cube_size * 0.7,
        )
        top_face = (
            left,
            top + cube_size * 0.25,
            left + cube_size * 0.48,
            top,
            left + cube_size,
            top + cube_size * 0.25,
            left + cube_size * 0.52,
            top + cube_size * 0.5,
        )
        self.hero_canvas.create_polygon(front, fill=mix_color(APP_GLOW_CYAN, APP_BG, 0.28), outline="")
        self.hero_canvas.create_polygon(right, fill=mix_color(APP_GLOW_PURPLE, APP_BG, 0.28), outline="")
        self.hero_canvas.create_polygon(top_face, fill=mix_color(APP_ACCENT, APP_BORDER, 0.35), outline="")

        offset = cube_size * 0.24
        self.hero_canvas.create_polygon(
            tuple(value + (offset if index % 2 == 0 else offset * 0.75) for index, value in enumerate(front)),
            fill=mix_color(APP_GLOW_CYAN, APP_BG, 0.55),
            outline="",
        )
        self.hero_canvas.create_polygon(
            tuple(value + (offset if index % 2 == 0 else offset * 0.75) for index, value in enumerate(right)),
            fill=mix_color(APP_GLOW_PURPLE, APP_BG, 0.5),
            outline="",
        )

    def _set_status(self, message: str, detail: str) -> None:
        self.status_var.set(message)
        self.status_detail_var.set(detail)

    @staticmethod
    def _is_within_root(root: Path, candidate: Path) -> bool:
        try:
            candidate.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True


def main() -> int:
    root = tk.Tk()
    PixelFixStudioApp(root)
    root.mainloop()
    return 0
