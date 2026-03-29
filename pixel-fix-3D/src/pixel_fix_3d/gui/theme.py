from __future__ import annotations

import ctypes
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

APP_NAME = "Pixel-Fix Studio 3D"
APP_BG = "#222323"
APP_SURFACE_BG = "#2B2D2D"
APP_HOVER_BG = "#343838"
APP_ACCENT = "#7FD9F8"
APP_BORDER = "#F0F6F0"
APP_TEXT = "#F0F6F0"
APP_MUTED_TEXT = "#8D968D"
APP_PANEL_BG = "#262828"
APP_VIEWPORT_BG = "#171919"
PIXEL_FONT_FAMILY = "pixelmix"
HEADER_FONT_FAMILY = PIXEL_FONT_FAMILY
UI_FONT_SIZE = 6
HEADER_FONT_SIZE = 6


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


def configure_ttk_theme(root: tk.Tk, ui_font: tkfont.Font, header_font: tkfont.Font) -> None:
    root.configure(background=APP_BG)
    root.option_add("*Font", ui_font)
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

    style.configure(".", background=APP_BG, foreground=APP_TEXT, font=ui_font)
    style.configure("TFrame", background=APP_BG)
    style.configure("Panel.TFrame", background=APP_PANEL_BG)
    style.configure("TLabel", background=APP_BG, foreground=APP_TEXT)
    style.configure("Muted.TLabel", background=APP_BG, foreground=APP_MUTED_TEXT)
    style.configure("Panel.TLabel", background=APP_PANEL_BG, foreground=APP_TEXT)
    style.configure("SectionTitle.TLabel", background=APP_BG, foreground=APP_TEXT, font=header_font)
    style.configure("Title.TLabel", background=APP_BG, foreground=APP_ACCENT, font=header_font)
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
    style.configure("TLabelframe.Label", background=APP_BG, foreground=APP_TEXT, font=header_font)
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
    style.configure("Compact.TButton", padding=(4, 2))
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
        "Selected.TButton",
        background=APP_ACCENT,
        foreground=APP_BG,
        bordercolor=APP_ACCENT,
        darkcolor=APP_ACCENT,
        lightcolor=APP_ACCENT,
    )
    style.map(
        "Selected.TButton",
        background=[("pressed", APP_ACCENT), ("active", APP_ACCENT)],
        foreground=[("pressed", APP_BG), ("active", APP_BG)],
        bordercolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT)],
        darkcolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT)],
        lightcolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT)],
    )
    style.configure(
        "ToolButton.TButton",
        background=APP_SURFACE_BG,
        foreground=APP_TEXT,
        bordercolor=APP_SURFACE_BG,
        borderwidth=0,
        darkcolor=APP_SURFACE_BG,
        lightcolor=APP_SURFACE_BG,
        padding=(0, 0),
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
        padding=(0, 0),
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
        padding=(0, 0),
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
        "Texture.TButton",
        anchor=tk.W,
        justify=tk.LEFT,
        padding=(6, 6),
    )
    style.configure(
        "TextureSelected.TButton",
        background=APP_ACCENT,
        foreground=APP_BG,
        bordercolor=APP_ACCENT,
        darkcolor=APP_ACCENT,
        lightcolor=APP_ACCENT,
        anchor=tk.W,
        justify=tk.LEFT,
        padding=(6, 6),
    )
    style.map(
        "TextureSelected.TButton",
        background=[("pressed", APP_ACCENT), ("active", APP_ACCENT)],
        foreground=[("pressed", APP_BG), ("active", APP_BG)],
        bordercolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT)],
        darkcolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT)],
        lightcolor=[("pressed", APP_ACCENT), ("active", APP_ACCENT)],
    )
    style.configure("Status.TFrame", background=APP_SURFACE_BG)
    style.configure("Status.TLabel", background=APP_SURFACE_BG, foreground=APP_TEXT)
    style.configure("StatusMuted.TLabel", background=APP_SURFACE_BG, foreground=APP_MUTED_TEXT)
