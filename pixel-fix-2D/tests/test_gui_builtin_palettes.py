from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

import pixel_fix.gui.app as app_module
from pixel_fix.gui.app import PixelFixGui
from pixel_fix.palette.sort import (
    PALETTE_SELECT_LABELS,
    PALETTE_SELECT_SIMILARITY_NEAR_DUPLICATES,
    PALETTE_SORT_LIGHTNESS,
)


def _write_gpl(path: Path, *entries: tuple[int, int, int, str]) -> None:
    lines = ["GIMP Palette", "Name: Example", "Columns: 4"]
    for red, green, blue, label in entries:
        lines.append(f"{red} {green} {blue} {label}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _create_palette_tree(root: Path) -> Path:
    palette_root = root / "palettes"
    package_dir = palette_root / "dawn"
    package_dir.mkdir(parents=True, exist_ok=True)
    _write_gpl(package_dir / "db16.gpl", (17, 34, 51, "dark"), (171, 205, 239, "light"))
    (package_dir / "package.json").write_text(
        json.dumps(
            {
                "displayName": "DawnBringer",
                "contributes": {"palettes": [{"id": "DB16", "path": "./db16.gpl"}]},
            }
        ),
        encoding="utf-8",
    )
    return palette_root


def _build_gui(monkeypatch, tmp_path: Path, persisted: dict[str, object] | None = None) -> PixelFixGui:
    palette_root = _create_palette_tree(tmp_path)
    packaged_resource_root = Path(app_module.__file__).resolve().parents[1] / "resources"

    def _resource_path(name: str) -> Path:
        resource_path = Path(name)
        if resource_path.parts and resource_path.parts[0] == "palettes":
            if len(resource_path.parts) == 1:
                return palette_root
            return palette_root.joinpath(*resource_path.parts[1:])
        return packaged_resource_root / resource_path

    monkeypatch.setattr("pixel_fix.gui.app.load_app_state", lambda: dict(persisted or {}))
    monkeypatch.setattr("pixel_fix.gui.app.save_app_state", lambda _data: None)
    monkeypatch.setattr(
        PixelFixGui,
        "_resource_path",
        staticmethod(_resource_path),
    )
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk is not available in this environment: {exc}")
    root.withdraw()
    gui = PixelFixGui(root)
    root.update_idletasks()
    return gui


def test_top_toolbar_is_created_above_main_body_with_expected_buttons(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        root_children = gui.root.winfo_children()
        assert root_children.index(gui.top_toolbar) < root_children.index(gui.body)
        assert str(gui.root.cget("menu"))
        assert gui._toolbar_button_order == (
            "toolbar_new_button",
            "toolbar_open_button",
            "toolbar_save_button",
            "toolbar_cut_button",
            "toolbar_copy_button",
            "toolbar_paste_button",
            "toolbar_undo_button",
            "toolbar_redo_button",
            "toolbar_canvas_size_button",
            "toolbar_rotate_button",
            "toolbar_ai_generate_button",
            "toolbar_indexed_color_button",
            "toolbar_adjustments_button",
            "toolbar_preferences_button",
        )
        assert gui.top_toolbar.pack_info()["fill"] == "x"
        assert gui.top_toolbar_row.pack_info()["anchor"] == "w"
        assert gui.top_toolbar_row.winfo_children() == [
            gui.toolbar_new_button_cell,
            gui.toolbar_open_button_cell,
            gui.toolbar_save_button_cell,
            gui.toolbar_cut_button_cell,
            gui.toolbar_copy_button_cell,
            gui.toolbar_paste_button_cell,
            gui.toolbar_undo_button_cell,
            gui.toolbar_redo_button_cell,
            gui.toolbar_canvas_size_button_cell,
            gui.toolbar_rotate_button_cell,
            gui.toolbar_ai_generate_button_cell,
            gui.toolbar_indexed_color_button_cell,
            gui.toolbar_adjustments_button_cell,
            gui.toolbar_preferences_button_cell,
            gui.toolbar_zoom_dropdown,
        ]
        assert gui.toolbar_zoom_dropdown.cget("values") == tuple(f"{value}%" for value in app_module.ZOOM_PRESETS) + ("Fit",)
    finally:
        gui.root.destroy()


def test_top_toolbar_buttons_invoke_expected_actions(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(PixelFixGui, "open_new_image_window", lambda self: calls.append("new"))
    monkeypatch.setattr(PixelFixGui, "open_image", lambda self: calls.append("open"))
    monkeypatch.setattr(PixelFixGui, "save_processed_image", lambda self: calls.append("save"))
    monkeypatch.setattr(PixelFixGui, "open_canvas_size_window", lambda self: calls.append("canvas"))
    monkeypatch.setattr(PixelFixGui, "open_indexed_color_window", lambda self: calls.append("indexed"))
    monkeypatch.setattr(PixelFixGui, "_toggle_adjustments_mode", lambda self: calls.append("adjust"))
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui.toolbar_new_button.invoke()
        gui.toolbar_open_button.invoke()
        gui.image_state = "processed_current"
        gui._current_output_result = lambda: SimpleNamespace(structured_palette=None, display_palette_labels=())
        gui._current_output_image = lambda: object()
        gui._refresh_action_states()
        gui.toolbar_save_button.invoke()
        gui.toolbar_canvas_size_button.invoke()
        gui.toolbar_indexed_color_button.invoke()
        gui.toolbar_adjustments_button.invoke()
        assert calls == ["new", "open", "save", "canvas", "indexed", "adjust"]

        gui.toolbar_preferences_button.invoke()
        assert gui._preferences_window is not None
        assert gui._preferences_window.winfo_exists() == 1
    finally:
        gui.root.destroy()


def test_builtin_palette_menu_uses_catalog_tree(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        top_level_labels = [
            gui._menu_bar.entrycget(index, "label")
            for index in range(gui._menu_bar.index("end") + 1)
        ]
        assert top_level_labels == ["File", "Palette", "Edit", "Transform", "Select"]
        builtins_menu = gui._menu_items["built_in_palettes"]
        assert builtins_menu.entrycget(0, "label") == "DawnBringer"
        folder_menu = builtins_menu.nametowidget(builtins_menu.entrycget(0, "menu"))
        assert folder_menu.entrycget(0, "label") == "DB16"
        palette_labels = [
            gui._menu_items["palette"].entrycget(index, "label")
            for index in range(gui._menu_items["palette"].index("end") + 1)
            if gui._menu_items["palette"].type(index) != "separator"
        ]
        assert "Generate Override Palette" not in palette_labels
        assert "Add Colour" in palette_labels
        assert "Sort Current Palette" in palette_labels
        assert gui._menu_items["palette"].entrycget("Sort Current Palette", "state") == "disabled"
        assert "Clear Active Palette" not in palette_labels
        assert "Save Current Palette..." in palette_labels
        sort_menu = gui._menu_items["palette_sort"]
        sort_labels = [
            sort_menu.entrycget(index, "label")
            for index in range(sort_menu.index("end") + 1)
            if sort_menu.type(index) != "separator"
        ]
        assert "Lightness (Dark -> Light)" in sort_labels
        assert "Hue (Red Wheel)" in sort_labels
        assert "Saturation (Low -> High)" in sort_labels
        assert "Chroma (Low -> High)" in sort_labels
        assert "Temperature (Cool -> Warm)" in sort_labels
        assert "Reset To Source Order" not in sort_labels
        select_menu = gui._menu_items["select"]
        select_labels = [select_menu.entrycget(index, "label") for index in range(select_menu.index("end") + 1)]
        similarity_label = PALETTE_SELECT_LABELS[PALETTE_SELECT_SIMILARITY_NEAR_DUPLICATES]
        assert "Hue" in select_labels
        assert similarity_label in select_labels
        assert select_labels.index("Hue") < select_labels.index(similarity_label)
        assert gui._menu_bar.entrycget("Select", "state") == "disabled"
    finally:
        gui.root.destroy()


def test_preferences_window_uses_persisted_assignments(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(
        monkeypatch,
        tmp_path,
        persisted={
            "right_mouse_action": app_module.MOUSE_BUTTON_ACTION_SWAP_COLORS,
            "middle_mouse_action": app_module.MOUSE_BUTTON_ACTION_ERASER,
            "checkerboard": True,
            "overlay_grid": True,
            "shortcut_bindings": {"undo": None, "open_file": "Ctrl+Shift+O"},
        },
    )
    try:
        gui.open_preferences_window()
        page_labels = [
            gui._preferences_nav_buttons[page_name].cget("text")
            for page_name in app_module.PREFERENCES_PAGE_ORDER
        ]
        assert page_labels == list(app_module.PREFERENCES_PAGE_ORDER)
        assert gui._preferences_checkerboard_var.get() is True
        assert gui._preferences_overlay_grid_var.get() is True
        assert gui._preferences_right_mouse_action_var.get() == app_module.MOUSE_BUTTON_ACTION_SWAP_COLORS
        assert gui._preferences_middle_mouse_action_var.get() == app_module.MOUSE_BUTTON_ACTION_ERASER
        file_menu = gui._menu_items["file"]
        assert file_menu.entrycget("Open...", "accelerator") == "Ctrl+O"
        assert file_menu.entrycget("Export...", "accelerator") == "Ctrl+E"
        assert gui._widget_tooltips["toolbar_open_button"].text.endswith("(Ctrl+O)")
    finally:
        gui.root.destroy()


def test_preferences_toolbar_opens_single_window(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui.toolbar_preferences_button.invoke()
        first_window = gui._preferences_window

        assert first_window is not None

        gui.open_preferences_window()
        assert gui._preferences_window is first_window

        gui.toolbar_preferences_button.invoke()
        assert gui._preferences_window is first_window
    finally:
        gui.root.destroy()


def test_indexed_color_toolbar_opens_single_window_with_defaults(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    monkeypatch.setattr(PixelFixGui, "_schedule_indexed_color_preview", lambda self: None)
    try:
        gui.image_state = "processed_current"
        gui._current_output_result = lambda: object()
        gui._current_output_image = lambda: Image.new("RGBA", (2, 2), (0, 0, 0, 255))
        gui._canvas_interaction_active = lambda: False
        gui._capture_indexed_color_snapshot = lambda: SimpleNamespace()

        gui.open_indexed_color_window()
        first_window = gui._indexed_color_window

        assert first_window is not None
        assert gui._indexed_color_palette_var.get() == "Local (Perceptual)"
        assert gui._indexed_color_colors_var.get() == 32
        assert gui._indexed_color_forced_var.get() == "None"
        assert gui._indexed_color_dither_var.get() == "None"
        assert gui._indexed_color_amount_var.get() == 100
        assert gui._indexed_color_preview_var.get() is True

        gui.open_indexed_color_window()
        assert gui._indexed_color_window is first_window
    finally:
        gui.root.destroy()


def test_canvas_size_toolbar_opens_single_window_with_defaults(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui.image_state = "processed_current"
        gui.downsample_result = SimpleNamespace(width=96, height=80)
        gui._current_output_result = lambda: gui.downsample_result
        gui._current_output_image = lambda: Image.new("RGBA", (96, 80), (0, 0, 0, 255))

        gui.open_canvas_size_window()
        first_window = gui._canvas_size_window

        assert first_window is not None
        assert gui._canvas_size_width_var.get() == "96"
        assert gui._canvas_size_height_var.get() == "80"
        assert gui._canvas_size_anchor_var.get() == app_module.CANVAS_RESIZE_ANCHOR_CENTER
        assert gui._canvas_size_locked_var.get() is True
        assert gui._canvas_size_lock_button.cget("relief") == tk.FLAT

        gui._canvas_size_width_var.set("120")
        assert gui._canvas_size_height_var.get() == "120"

        gui._toggle_canvas_size_lock()
        assert gui._canvas_size_lock_button.cget("relief") == tk.FLAT
        gui._canvas_size_width_var.set("140")
        assert gui._canvas_size_height_var.get() == "120"

        gui._toggle_canvas_size_lock()
        assert gui._canvas_size_lock_button.cget("relief") == tk.FLAT
        assert gui._canvas_size_height_var.get() == "140"

        gui.open_canvas_size_window()
        assert gui._canvas_size_window is first_window
    finally:
        gui.root.destroy()


def test_new_toolbar_opens_single_window_with_defaults(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui.open_new_image_window()
        first_window = gui._new_image_window
        gui.root.update_idletasks()

        assert first_window is not None
        assert gui._new_image_width_var.get() == "256"
        assert gui._new_image_height_var.get() == "256"
        assert gui._new_image_locked_var.get() is True
        assert gui._new_image_background_var.get() == "Transparent"
        assert gui._new_image_lock_button is not None
        assert gui._new_image_lock_button.cget("relief") == tk.FLAT

        gui.open_new_image_window()
        assert gui._new_image_window is first_window
    finally:
        gui.root.destroy()


def test_new_image_dialog_lock_and_commit_create_blank_canvas(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui.open_new_image_window()

        gui._toggle_new_image_lock()
        assert gui._new_image_lock_button.cget("relief") == tk.FLAT
        gui._new_image_width_var.set("48")
        gui._new_image_height_var.set("24")
        gui._new_image_background_var.set("White")
        gui._commit_new_image_dialog()

        assert gui._new_image_window is None
        assert gui.image_state == "processed_current"
        assert gui.source_path is not None
        assert gui.source_path.name == "Untitled.png"
        assert gui.downsample_result is not None
        assert gui.downsample_result.width == 48
        assert gui.downsample_result.height == 24
        assert gui.downsample_result.alpha_mask is None
        assert gui.palette_result is None
        assert gui.last_output_path is None
        assert gui.process_status_var.get() == "Created a 48x24 white canvas. Draw on it immediately or save it with Save As."
    finally:
        gui.root.destroy()


def test_preferences_apply_commits_changes_and_closes(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui.open_preferences_window()
        gui._preferences_checkerboard_var.set(True)
        gui._preferences_overlay_grid_var.set(True)
        gui._preferences_selection_threshold_var.set(60)
        gui._preferences_middle_mouse_action_var.set(app_module.MOUSE_BUTTON_ACTION_ERASER)

        gui._apply_preferences_window_changes()

        assert gui._preferences_window is None
        assert gui.checkerboard_var.get() is True
        assert gui.overlay_grid_var.get() is True
        assert gui.selection_threshold_var.get() == 60
        assert gui.middle_mouse_action_var.get() == app_module.MOUSE_BUTTON_ACTION_ERASER
    finally:
        gui.root.destroy()


def test_preferences_cancel_closes_immediately_when_unchanged(monkeypatch, tmp_path: Path) -> None:
    ask_calls: list[str] = []
    monkeypatch.setattr("pixel_fix.gui.app.messagebox.askyesno", lambda *args, **kwargs: ask_calls.append("ask") or True)
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui.open_preferences_window()

        assert gui._close_preferences_window() is True
        assert gui._preferences_window is None
        assert ask_calls == []
    finally:
        gui.root.destroy()


def test_preferences_cancel_confirms_when_dirty(monkeypatch, tmp_path: Path) -> None:
    answers = iter((False, True))
    gui = _build_gui(monkeypatch, tmp_path)
    monkeypatch.setattr("pixel_fix.gui.app.messagebox.askyesno", lambda *args, **kwargs: next(answers))
    try:
        gui.open_preferences_window()
        gui._preferences_overlay_grid_var.set(True)

        assert gui._close_preferences_window() is False
        assert gui._preferences_window is not None
        assert gui.overlay_grid_var.get() is False

        assert gui._close_preferences_window() is True
        assert gui._preferences_window is None
        assert gui.overlay_grid_var.get() is False
    finally:
        gui.root.destroy()


def test_selecting_builtin_palette_updates_preview_without_processing(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        entry = gui.builtin_palette_entries[0]
        gui._select_builtin_palette(entry)
        assert gui.active_palette == [0x112233, 0xABCDEF]
        assert gui.active_palette_path == str(entry.path)
        assert gui.palette_info_var.get() == "Palette: Built-in: DawnBringer / DB16 (2 colours)"
        assert gui._menu_items["palette"].entrycget("Sort Current Palette", "state") == "normal"
        assert gui._menu_bar.entrycget("Select", "state") == "normal"
        assert gui.downsample_result is None
        assert gui.palette_result is None
    finally:
        gui.root.destroy()


def test_opening_palette_browser_creates_popover_and_filters_results(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui._open_palette_browser()
        gui.root.update_idletasks()

        assert gui._palette_browser_window is not None
        assert gui._palette_browser_window.winfo_exists() == 1
        assert gui._palette_browser_displayed_entries == gui.builtin_palette_entries
        assert gui._palette_browser_empty_label is None

        gui._palette_browser_search_var.set("zzz")
        gui.root.update_idletasks()

        assert gui._palette_browser_displayed_entries == []
        assert gui._palette_browser_empty_label is not None

        gui._palette_browser_search_var.set("db16")
        gui.root.update_idletasks()

        assert gui._palette_browser_displayed_entries == gui.builtin_palette_entries
        assert gui._palette_browser_empty_label is None
    finally:
        gui.root.destroy()


def test_palette_browser_hover_preview_and_close_restore_active_palette(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        entry = gui.builtin_palette_entries[0]
        gui._select_builtin_palette(entry)
        gui._open_palette_browser()
        gui.root.update_idletasks()

        gui._preview_builtin_palette(entry)

        assert gui._builtin_palette_preview_entry == entry
        assert gui.palette_info_var.get() == "Palette: Preview: DawnBringer / DB16 (2 colours)"

        gui._close_palette_browser()

        assert gui._builtin_palette_preview_entry is None
        assert gui.palette_info_var.get() == "Palette: Built-in: DawnBringer / DB16 (2 colours)"
    finally:
        gui.root.destroy()


def test_palette_browser_selects_entry_and_closes(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        entry = gui.builtin_palette_entries[0]
        gui._open_palette_browser()
        gui.root.update_idletasks()

        gui._select_builtin_palette_from_browser(entry)

        assert gui._palette_browser_window is None
        assert gui.active_palette == [0x112233, 0xABCDEF]
        assert gui.active_palette_path == str(entry.path)
    finally:
        gui.root.destroy()


def test_palette_browser_closes_on_escape_and_outside_click(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        gui._open_palette_browser()
        gui.root.update_idletasks()
        assert gui._palette_browser_window is not None

        result = gui._on_palette_browser_escape()

        assert result == "break"
        assert gui._palette_browser_window is None

        gui._open_palette_browser()
        gui.root.update_idletasks()
        assert gui._palette_browser_window is not None

        gui._on_palette_browser_root_click(type("Event", (), {"widget": gui.root})())

        assert gui._palette_browser_window is None
    finally:
        gui.root.destroy()


def test_palette_browser_load_palette_footer_closes_and_delegates(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        calls: list[str] = []
        gui.load_palette_file = lambda: calls.append("load")
        gui._open_palette_browser()
        gui.root.update_idletasks()

        gui._load_palette_file_from_browser()

        assert gui._palette_browser_window is None
        assert calls == ["load"]
    finally:
        gui.root.destroy()


def test_sorting_builtin_palette_does_not_mutate_catalog_entry(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        entry = gui.builtin_palette_entries[0]
        original_colors = list(entry.colors)

        gui._select_builtin_palette(entry)
        gui.sort_current_palette(PALETTE_SORT_LIGHTNESS)

        assert list(entry.colors) == original_colors
        assert gui.active_palette is not None
        assert gui.active_palette_source == "Sorted: Lightness (Dark -> Light)"
        sort_menu = gui._menu_items["palette_sort"]
        sort_labels = [
            sort_menu.entrycget(index, "label")
            for index in range(sort_menu.index("end") + 1)
            if sort_menu.type(index) != "separator"
        ]
        assert "Reset To Source Order" in sort_labels
    finally:
        gui.root.destroy()


def test_persisted_builtin_palette_is_restored_on_startup(monkeypatch, tmp_path: Path) -> None:
    palette_root = _create_palette_tree(tmp_path)
    palette_path = str((palette_root / "dawn" / "db16.gpl").resolve())
    gui = _build_gui(
        monkeypatch,
        tmp_path,
        persisted={
            "active_palette_path": palette_path,
            "active_palette_source": "Built-in: DawnBringer / DB16",
        },
    )
    try:
        assert gui.active_palette == [0x112233, 0xABCDEF]
        assert gui.active_palette_source == "Built-in: DawnBringer / DB16"
        assert gui.active_palette_path == palette_path
        assert gui.palette_info_var.get() == "Palette: Built-in: DawnBringer / DB16 (2 colours)"
    finally:
        gui.root.destroy()


def test_palette_adjustment_sliders_start_neutral_even_when_persisted(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(
        monkeypatch,
        tmp_path,
        persisted={
            "settings": {
                "palette_brightness": 25,
                "palette_contrast": 140,
                "palette_hue": 15,
                "palette_saturation": 160,
            }
        },
    )
    try:
        assert gui.palette_brightness_var.get() == 0
        assert gui.palette_contrast_var.get() == 0
        assert gui.palette_hue_var.get() == 0
        assert gui.palette_saturation_var.get() == 0
        assert gui.session.current == app_module.PreviewSettings()
    finally:
        gui.root.destroy()


def test_legacy_outline_adaptive_flag_restores_adaptive_outline_mode(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(
        monkeypatch,
        tmp_path,
        persisted={"outline_adaptive": True},
    )
    try:
        assert gui._outline_adaptive_enabled() is True
        assert gui.outline_adaptive_darken_percent_var.get() == 60
        assert gui.outline_add_generated_colours_var.get() is False
    finally:
        gui.root.destroy()


def test_outline_remove_brightness_threshold_defaults_on_startup(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        assert gui.outline_remove_brightness_threshold_enabled_var.get() is False
        assert gui.outline_remove_brightness_threshold_percent_var.get() == 40
        assert gui.outline_remove_brightness_threshold_direction_var.get() == "dark"
    finally:
        gui.root.destroy()


def test_brush_settings_default_on_startup(monkeypatch, tmp_path: Path) -> None:
    gui = _build_gui(monkeypatch, tmp_path)
    try:
        assert gui.brush_width_var.get() == 1
        assert gui.brush_shape_var.get() == "Square"
    finally:
        gui.root.destroy()
