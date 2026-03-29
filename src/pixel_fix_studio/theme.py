from __future__ import annotations

import ctypes
import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

APP_BG = "#222323"
APP_SURFACE_BG = "#2B2D2D"
APP_HOVER_BG = "#343838"
APP_PANEL_BG = "#262828"
APP_PANEL_DARK = "#171919"
APP_BORDER = "#F0F6F0"
APP_TEXT = "#F0F6F0"
APP_MUTED_TEXT = "#8D968D"
APP_ACCENT = "#7FD9F8"
APP_PURPLE_ACCENT = "#7FD9F8"
APP_ORANGE_ACCENT = "#F3AE64"
APP_BLACK = "#111111"
APP_STATUS_BG = "#1A1B1B"
APP_SCANLINE = "#1E2020"
APP_GLASS = "#292B2B"
APP_GLOW_CYAN = "#52BFD6"
APP_GLOW_PURPLE = "#52BFD6"
PIXEL_FONT_FAMILY = "pixelmix"
UI_FONT_SIZE = 6
SMALL_FONT_SIZE = 6
MENU_FONT_SIZE = 6
SECTION_FONT_SIZE = 6
CARD_TITLE_FONT_SIZE = 6
BUTTON_FONT_SIZE = 6
TITLE_FONT_SIZE = 6
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 450
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 450


@dataclass(frozen=True)
class LauncherFonts:
    ui: tkfont.Font
    small: tkfont.Font
    menu: tkfont.Font
    section: tkfont.Font
    card_title: tkfont.Font
    button: tkfont.Font
    title: tkfont.Font


def load_font_family(root: tk.Misc, font_path: Path, family: str) -> str:
    if family.lower() in {name.lower() for name in tkfont.families(root)}:
        return family
    if sys.platform == "win32" and font_path.exists():
        added = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), 0x10, 0)
        if added:
            try:
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
            except OSError:
                pass
    if family.lower() in {name.lower() for name in tkfont.families(root)}:
        return family
    return "TkFixedFont"


def build_fonts(root: tk.Tk, font_path: Path) -> LauncherFonts:
    family = load_font_family(root, font_path, PIXEL_FONT_FAMILY)
    return LauncherFonts(
        ui=tkfont.Font(root=root, name="PixelFixStudioUIFont", family=family, size=UI_FONT_SIZE),
        small=tkfont.Font(root=root, name="PixelFixStudioSmallFont", family=family, size=SMALL_FONT_SIZE),
        menu=tkfont.Font(root=root, name="PixelFixStudioMenuFont", family=family, size=MENU_FONT_SIZE),
        section=tkfont.Font(root=root, name="PixelFixStudioSectionFont", family=family, size=SECTION_FONT_SIZE),
        card_title=tkfont.Font(root=root, name="PixelFixStudioCardTitleFont", family=family, size=CARD_TITLE_FONT_SIZE),
        button=tkfont.Font(root=root, name="PixelFixStudioButtonFont", family=family, size=BUTTON_FONT_SIZE),
        title=tkfont.Font(root=root, name="PixelFixStudioTitleFont", family=family, size=TITLE_FONT_SIZE),
    )


def configure_ttk_theme(root: tk.Tk, fonts: LauncherFonts) -> None:
    root.configure(background=APP_BG)
    root.option_add("*Font", fonts.ui)
    root.option_add("*Background", APP_BG)
    root.option_add("*Foreground", APP_TEXT)
    root.option_add("*highlightBackground", APP_BORDER)
    root.option_add("*highlightColor", APP_BORDER)
    root.option_add("*insertBackground", APP_TEXT)
    root.option_add("*selectBackground", APP_HOVER_BG)
    root.option_add("*selectForeground", APP_TEXT)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure(".", background=APP_BG, foreground=APP_TEXT, font=fonts.ui)
    style.configure("TFrame", background=APP_BG)
    style.configure("TLabel", background=APP_BG, foreground=APP_TEXT, font=fonts.ui)
    style.configure("Muted.TLabel", background=APP_BG, foreground=APP_MUTED_TEXT, font=fonts.small)
    style.configure("SectionTitle.TLabel", background=APP_BG, foreground=APP_TEXT, font=fonts.section)
    style.configure(
        "TEntry",
        fieldbackground=APP_SURFACE_BG,
        foreground=APP_TEXT,
        insertcolor=APP_TEXT,
        bordercolor=APP_BORDER,
        lightcolor=APP_BORDER,
        darkcolor=APP_BORDER,
        padding=(4, 2),
    )
    style.map(
        "TEntry",
        fieldbackground=[("readonly", APP_SURFACE_BG), ("disabled", APP_BG)],
        foreground=[("disabled", APP_MUTED_TEXT)],
        bordercolor=[("focus", APP_BORDER)],
        lightcolor=[("focus", APP_BORDER)],
        darkcolor=[("focus", APP_BORDER)],
    )
    style.configure(
        "Treeview",
        background=APP_SURFACE_BG,
        fieldbackground=APP_SURFACE_BG,
        foreground=APP_TEXT,
        bordercolor=APP_BORDER,
        lightcolor=APP_BORDER,
        darkcolor=APP_BORDER,
        rowheight=18,
        relief=tk.FLAT,
    )
    style.map(
        "Treeview",
        background=[("selected", APP_HOVER_BG)],
        foreground=[("selected", APP_TEXT)],
    )
    style.configure(
        "Treeview.Heading",
        background=APP_SURFACE_BG,
        foreground=APP_TEXT,
        bordercolor=APP_BORDER,
        lightcolor=APP_BORDER,
        darkcolor=APP_BORDER,
        relief=tk.FLAT,
    )
    style.configure(
        "TButton",
        background=APP_SURFACE_BG,
        foreground=APP_TEXT,
        bordercolor=APP_BORDER,
        darkcolor=APP_BORDER,
        lightcolor=APP_BORDER,
        padding=(6, 4),
        relief=tk.FLAT,
    )
    style.map(
        "TButton",
        background=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
        foreground=[("pressed", APP_BG), ("disabled", APP_MUTED_TEXT)],
        bordercolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
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
        relief=tk.FLAT,
    )
    style.map(
        "TMenubutton",
        background=[("pressed", APP_ACCENT), ("active", APP_HOVER_BG), ("disabled", APP_BG)],
        foreground=[("pressed", APP_BG), ("disabled", APP_MUTED_TEXT)],
        bordercolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
        darkcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
        lightcolor=[("pressed", APP_ACCENT), ("active", APP_BORDER), ("disabled", APP_BORDER)],
    )
    style.configure("Compact.TButton", padding=(4, 2))


def accent_from_key(accent_key: str) -> str:
    return APP_ACCENT
