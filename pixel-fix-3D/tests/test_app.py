from __future__ import annotations

import tkinter as tk

import numpy as np
import pytest
from PIL import Image

import pixel_fix_3d.gui.app as app_module
from pixel_fix_3d.gui.persist import AppPreferences
from pixel_fix_3d.project_io import Pfx3dFaceTexture, Pfx3dProject


def _collect_widget_texts(widget: tk.Misc) -> list[str]:
    texts: list[str] = []
    try:
        text = str(widget.cget("text"))
    except tk.TclError:
        text = ""
    if text:
        texts.append(text)
    for child in widget.winfo_children():
        texts.extend(_collect_widget_texts(child))
    return texts


@pytest.fixture
def built_app(monkeypatch: pytest.MonkeyPatch) -> tuple[tk.Tk, app_module.PixelFixStudio3DApp]:
    monkeypatch.setattr(app_module, "load_app_state", lambda: {})
    monkeypatch.setattr(app_module, "save_app_state", lambda _data: None)
    monkeypatch.setattr(app_module.PixelFixStudio3DApp, "_configure_window_icon", lambda self: None)
    monkeypatch.setattr(app_module.PixelFixStudio3DApp, "_render_viewport", lambda self: None)
    monkeypatch.setattr(app_module.PixelFixStudio3DApp, "_run_autorotate", lambda self: None)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    app = app_module.PixelFixStudio3DApp(root)
    root.update_idletasks()
    try:
        yield root, app
    finally:
        if root.winfo_exists():
            root.destroy()


def test_camera_distance_to_zoom_percent_rounds_to_nearest_five() -> None:
    assert app_module.camera_distance_to_zoom_percent(4.25) == 100
    assert app_module.camera_distance_to_zoom_percent(2.0) == 215
    assert app_module.camera_distance_to_zoom_percent(8.0) == 55
    assert app_module.camera_distance_to_zoom_percent(4.5) == 95


def test_ui_chrome_matches_toolbar_and_panel_requirements(built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp]) -> None:
    _root, app = built_app
    texts = _collect_widget_texts(app.root)

    assert app.left_panel.cget("text") == "MODELS"
    assert app.center_panel.cget("text") == "VIEWPORT"
    assert app.right_panel.cget("text") == "TEXTURES"
    assert "PRESET MODELS" in texts
    assert "CONTROLS" in texts
    assert "VIEW" in texts
    assert "VIEWPORT" in texts
    assert "Pixel-Fix Studio 3D" not in texts
    assert "Single-shape low poly texturing tool" not in texts
    assert set(app.shape_buttons) == {
        "cube",
        "box",
        "tall_box",
        "plane_2d",
        "wedge",
        "ramp",
        "cylinder",
        "roof",
        "table",
        "chair",
        "car",
    }
    assert "stairs" not in app.shape_buttons
    assert hasattr(app, "toolbar_new_button")
    assert hasattr(app, "toolbar_open_button")
    assert hasattr(app, "toolbar_save_button")
    assert hasattr(app, "toolbar_settings_button")
    assert hasattr(app, "extract_textures_button")
    assert hasattr(app, "export_glb_button")
    assert app.load_textures_button.cget("text") == "Load Texture..."
    assert app.toolbar_zoom_var.get() == "100%"
    assert not hasattr(app, "zoom_in_button")
    assert not hasattr(app, "zoom_out_button")


def test_startup_preloads_builtin_texture_library(built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp]) -> None:
    _root, app = built_app

    builtin_names = {entry.name for entry in app._builtin_texture_entries}
    assert {"brick.png", "crate.png", "metal.png", "tiles.png"}.issubset(builtin_names)
    assert "demo.png" not in builtin_names
    assert len(app.texture_entries) == len(app._builtin_texture_entries)


def test_model_view_and_rotate_controls_update_state(built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp]) -> None:
    _root, app = built_app

    app._set_shape("roof")
    assert app.editor_state.shape_key == "roof"
    assert app.shape_buttons["roof"].cget("style") == "ToolButtonActive.TButton"

    app._snap_view("bottom")
    assert app.editor_state.camera.pitch < 0.0

    app._toggle_rotating_view()
    assert app._autorotate_active is True
    assert app.rotate_view_button.cget("style") == "ToolButtonActive.TButton"
    assert app.shape_buttons["roof"].instate(("disabled",))

    app._toggle_rotating_view()
    assert app._autorotate_active is False
    assert app.rotate_view_button.cget("style") == "ToolButton.TButton"
    assert not app.shape_buttons["roof"].instate(("disabled",))


def test_zoom_readout_tracks_wheel_zoom(built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp]) -> None:
    _root, app = built_app

    app._apply_zoom(-0.25)
    assert app.toolbar_zoom_var.get() == "105%"

    app._apply_zoom(-2.0)
    assert app.toolbar_zoom_var.get() == "215%"

    app._apply_zoom(6.0)
    assert app.toolbar_zoom_var.get() == "55%"


def test_toolbar_save_exports_current_shape_to_pfx3d(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, app = built_app
    calls: list[tuple[object, object, object]] = []

    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **_kwargs: "C:/tmp/test.pfx3d")
    monkeypatch.setattr(app_module, "save_pfx3d", lambda path, shape, textures: calls.append((path, shape.key, dict(textures))))

    app.toolbar_save_button.invoke()

    assert calls
    saved_path, saved_shape, saved_textures = calls[0]
    assert saved_path == "C:/tmp/test.pfx3d"
    assert saved_shape == "cube"
    assert len(saved_textures) == 0


def test_toolbar_open_loads_project_and_replaces_session(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, app = built_app
    app.texture_entries.append(
        app_module.TextureEntry(
            texture_id="custom:old",
            name="old.png",
            path=None,
            size=(8, 8),
            image=Image.new("RGBA", (8, 8), (255, 0, 0, 255)),
        )
    )
    app.texture_lookup["custom:old"] = app.texture_entries[-1]
    app.editor_state = app_module.replace(
        app.editor_state,
        face_texture_assignments={"box": {0: "custom:old"}},
    )
    project = Pfx3dProject(
        shape_key="roof",
        faces=(
            Pfx3dFaceTexture(
                face_id=0,
                face_label="Bottom",
                texture_file="textures/00-bottom.png",
                image=Image.new("RGBA", (16, 16), (20, 30, 40, 255)),
            ),
            Pfx3dFaceTexture(
                face_id=1,
                face_label="Left Wall",
                texture_file="textures/01-left-wall.png",
                image=Image.new("RGBA", (24, 16), (50, 60, 70, 255)),
            ),
            Pfx3dFaceTexture(
                face_id=2,
                face_label="Right Wall",
                texture_file="textures/02-right-wall.png",
                image=Image.new("RGBA", (24, 16), (80, 90, 100, 255)),
            ),
            Pfx3dFaceTexture(
                face_id=3,
                face_label="Left Roof",
                texture_file="textures/03-left-roof.png",
                image=Image.new("RGBA", (32, 16), (110, 120, 130, 255)),
            ),
            Pfx3dFaceTexture(
                face_id=4,
                face_label="Right Roof",
                texture_file="textures/04-right-roof.png",
                image=Image.new("RGBA", (32, 16), (140, 150, 160, 255)),
            ),
            Pfx3dFaceTexture(
                face_id=5,
                face_label="Front Gable",
                texture_file="textures/05-front-gable.png",
                image=Image.new("RGBA", (24, 24), (170, 180, 190, 255)),
            ),
            Pfx3dFaceTexture(
                face_id=6,
                face_label="Back Gable",
                texture_file="textures/06-back-gable.png",
                image=Image.new("RGBA", (24, 24), (200, 210, 220, 255)),
            ),
        ),
    )
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **_kwargs: "C:/tmp/roof.pfx3d")
    monkeypatch.setattr(app_module, "load_pfx3d", lambda _path: project)

    app.toolbar_open_button.invoke()

    assert app.editor_state.shape_key == "roof"
    assert app.editor_state.selected_face_id is None
    assert app.editor_state.selected_face_ids == ()
    assert set(app.editor_state.face_texture_assignments) == {"roof"}
    assert len(app.texture_entries) == len(app._builtin_texture_entries) + len(project.faces)
    assert "custom:old" not in app.texture_lookup
    assert app.toolbar_zoom_var.get() == "100%"


def test_extract_textures_button_is_present_and_disabled_during_rotate(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
) -> None:
    _root, app = built_app

    assert not app.extract_textures_button.instate(("disabled",))
    assert not app.export_glb_button.instate(("disabled",))
    app._toggle_rotating_view()
    assert app.extract_textures_button.instate(("disabled",))
    assert app.export_glb_button.instate(("disabled",))
    app._toggle_rotating_view()
    assert not app.extract_textures_button.instate(("disabled",))
    assert not app.export_glb_button.instate(("disabled",))


def test_extract_textures_button_exports_current_shape(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, app = built_app
    calls: list[tuple[object, object, object]] = []

    monkeypatch.setattr(app_module.filedialog, "askdirectory", lambda **_kwargs: "C:/tmp")
    monkeypatch.setattr(
        app_module,
        "extract_face_textures",
        lambda path, shape, textures: calls.append((path, shape.key, dict(textures))) or app_module.Path("C:/tmp/cube_textures"),
    )

    app.extract_textures_button.invoke()

    assert calls
    extracted_path, extracted_shape, extracted_textures = calls[0]
    assert extracted_path == "C:/tmp"
    assert extracted_shape == "cube"
    assert len(extracted_textures) == 0


def test_load_textures_defaults_to_app_texture_library_directory(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, app = built_app
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        app_module.filedialog,
        "askopenfilename",
        lambda **kwargs: captured.update(kwargs) or "",
    )

    app._load_textures()

    expected_dir = app._default_texture_directory()
    assert captured["initialdir"] == str(expected_dir)


def test_export_glb_button_exports_current_shape(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, app = built_app
    calls: list[tuple[object, object, object]] = []

    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **_kwargs: "C:/tmp/test.glb")
    monkeypatch.setattr(app_module, "export_glb", lambda path, shape, textures: calls.append((path, shape.key, dict(textures))))

    app.export_glb_button.invoke()

    assert calls
    export_path, export_shape, export_textures = calls[0]
    assert export_path == "C:/tmp/test.glb"
    assert export_shape == "cube"
    assert len(export_textures) == 0


def test_load_texture_copies_png_into_texture_directory_and_refreshes_library(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: app_module.Path,
) -> None:
    _root, app = built_app
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    source = tmp_path / "source.png"
    Image.new("RGBA", (12, 10), (12, 34, 56, 255)).save(source)

    monkeypatch.setattr(app, "_default_texture_directory", lambda: texture_dir)
    app._builtin_texture_entries = app._default_texture_entries()
    app._reset_texture_library()
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **_kwargs: str(source))

    app._load_textures()

    copied = texture_dir / "source.png"
    assert copied.exists()
    assert {entry.name for entry in app.texture_entries} == {"source.png"}
    assert app.editor_state.status_message == "Loaded source.png."


def test_selected_texture_uses_texture_specific_active_style(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
) -> None:
    _root, app = built_app
    first_entry = app.texture_entries[0]
    app.editor_state = app_module.replace(
        app.editor_state,
        selected_face_id=0,
        face_texture_assignments={"cube": {0: first_entry.texture_id}},
    )

    app._refresh_texture_buttons()

    selected = next(
        child
        for child in app.texture_inner.winfo_children()
        if isinstance(child, app_module.ttk.Button) and child.cget("text").startswith(first_entry.name)
    )
    assert selected.cget("style") == "TextureSelected.TButton"


def test_shift_click_toggles_multi_face_selection(built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp]) -> None:
    _root, app = built_app
    face_ids = np.zeros((app_module.VIEWPORT_HEIGHT, app_module.VIEWPORT_WIDTH), dtype=np.int32)
    face_ids[:, 200:] = 1
    app.last_render_face_ids = face_ids
    app.viewport_display_rect = (0, 0, app_module.VIEWPORT_WIDTH, app_module.VIEWPORT_HEIGHT)

    app._pick_face(10, 10)
    assert app.editor_state.selected_face_ids == (0,)

    app._pick_face(240, 10, toggle=True)
    assert app.editor_state.selected_face_ids == (0, 1)
    assert app.editor_state.selected_face_id == 1

    app._pick_face(240, 10, toggle=True)
    assert app.editor_state.selected_face_ids == (0,)
    assert app.editor_state.selected_face_id == 0


def test_shift_click_empty_space_keeps_selection(built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp]) -> None:
    _root, app = built_app
    app.editor_state = app_module.replace(app.editor_state, selected_face_id=0, selected_face_ids=(0,))
    app.last_render_face_ids = np.zeros((app_module.VIEWPORT_HEIGHT, app_module.VIEWPORT_WIDTH), dtype=np.int32)
    app.viewport_display_rect = (0, 0, app_module.VIEWPORT_WIDTH, app_module.VIEWPORT_HEIGHT)

    app._pick_face(app_module.VIEWPORT_WIDTH + 10, 10, toggle=True)

    assert app.editor_state.selected_face_ids == (0,)
    assert app.editor_state.selected_face_id == 0


def test_ctrl_a_selects_all_faces_and_toggles_clear(built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp]) -> None:
    _root, app = built_app

    app._on_select_all_shortcut()
    assert app.editor_state.selected_face_ids == tuple(face.face_id for face in app._shape().face_groups)

    app._on_select_all_shortcut()
    assert app.editor_state.selected_face_ids == ()
    assert app.editor_state.selected_face_id is None


def test_texture_context_menu_reflects_selection_and_2d_availability(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, app = built_app
    texture_id = app.texture_entries[0].texture_id
    monkeypatch.setattr(app_module, "read_pixel_fix_2d_session", lambda: None)
    monkeypatch.setattr(app_module, "locate_pixel_fix_2d", lambda: None)

    menu = app._build_texture_context_menu(texture_id)

    assert menu.entrycget(0, "label") == "Apply"
    assert menu.entrycget(0, "state") == tk.DISABLED
    assert menu.entrycget(1, "label") == "Edit in Pixel-Fix 2D"
    assert menu.entrycget(1, "state") == tk.DISABLED

    app.editor_state = app_module.replace(app.editor_state, selected_face_id=0, selected_face_ids=(0, 1))
    monkeypatch.setattr(app_module, "read_pixel_fix_2d_session", lambda: {"pid": 1, "port": 1234})
    menu = app._build_texture_context_menu(texture_id)

    assert menu.entrycget(0, "state") == tk.NORMAL
    assert menu.entrycget(1, "state") == tk.NORMAL


def test_context_menu_apply_updates_all_selected_faces(built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp]) -> None:
    _root, app = built_app
    texture = app.texture_entries[0]
    app.editor_state = app_module.replace(app.editor_state, selected_face_id=0, selected_face_ids=(0, 1))

    app._apply_texture_to_selected_faces(texture.texture_id)

    assert app.editor_state.face_texture_assignments["cube"][0] == texture.texture_id
    assert app.editor_state.face_texture_assignments["cube"][1] == texture.texture_id
    assert app.editor_state.selected_face_id == 0


def test_duplicate_texture_entry_uses_numbered_suffix(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _root, app = built_app
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    Image.new("RGBA", (8, 8), (10, 20, 30, 255)).save(texture_dir / "source.png")
    monkeypatch.setattr(app, "_default_texture_directory", lambda: texture_dir)
    app._builtin_texture_entries = app._default_texture_entries()
    app._reset_texture_library()

    app._duplicate_texture_entry(app.texture_entries[0].texture_id)

    assert (texture_dir / "source (1).png").exists()


def test_rename_texture_entry_remaps_assignments(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _root, app = built_app
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    original_path = texture_dir / "source.png"
    Image.new("RGBA", (8, 8), (10, 20, 30, 255)).save(original_path)
    monkeypatch.setattr(app, "_default_texture_directory", lambda: texture_dir)
    app._builtin_texture_entries = app._default_texture_entries()
    app._reset_texture_library()
    texture_id = app.texture_entries[0].texture_id
    app.editor_state = app_module.replace(app.editor_state, face_texture_assignments={"cube": {0: texture_id}})
    monkeypatch.setattr(app_module.simpledialog, "askstring", lambda *args, **kwargs: "renamed")

    app._rename_texture_entry(texture_id)

    renamed_path = texture_dir / "renamed.png"
    assert renamed_path.exists()
    assert app.editor_state.face_texture_assignments["cube"][0] == str(renamed_path.resolve()).lower()


def test_delete_texture_entry_removes_file_and_clears_assignments(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _root, app = built_app
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    original_path = texture_dir / "source.png"
    Image.new("RGBA", (8, 8), (10, 20, 30, 255)).save(original_path)
    monkeypatch.setattr(app, "_default_texture_directory", lambda: texture_dir)
    app._builtin_texture_entries = app._default_texture_entries()
    app._reset_texture_library()
    texture_id = app.texture_entries[0].texture_id
    app.editor_state = app_module.replace(app.editor_state, face_texture_assignments={"cube": {0: texture_id}})
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda **_kwargs: True)

    app._delete_texture_entry(texture_id)

    assert not original_path.exists()
    assert app.editor_state.face_texture_assignments == {}


def test_edit_texture_in_pixel_fix_2d_uses_running_session_before_launch(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _root, app = built_app
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    original_path = texture_dir / "source.png"
    Image.new("RGBA", (8, 8), (10, 20, 30, 255)).save(original_path)
    monkeypatch.setattr(app, "_default_texture_directory", lambda: texture_dir)
    app._builtin_texture_entries = app._default_texture_entries()
    app._reset_texture_library()
    calls: list[str] = []
    monkeypatch.setattr(app_module, "send_open_path_to_pixel_fix_2d", lambda path: calls.append(str(path)) or True)
    monkeypatch.setattr(app_module, "launch_pixel_fix_2d", lambda _path: (_ for _ in ()).throw(AssertionError("launch should not run")))

    app._edit_texture_in_pixel_fix_2d(app.texture_entries[0].texture_id)

    assert calls == [str(original_path)]


def test_duplicate_texture_materializes_transient_project_texture(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _root, app = built_app
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    transient = app_module.TextureEntry(
        texture_id="pfx3d:roof:0:front.png",
        name="front.png",
        path=None,
        size=(8, 8),
        image=Image.new("RGBA", (8, 8), (120, 80, 40, 255)),
    )
    app._builtin_texture_entries = []
    app.texture_entries = [transient]
    app.texture_lookup = {transient.texture_id: transient}
    app.editor_state = app_module.replace(app.editor_state, face_texture_assignments={"cube": {0: transient.texture_id}})
    monkeypatch.setattr(app, "_default_texture_directory", lambda: texture_dir)

    app._duplicate_texture_entry(transient.texture_id)

    materialized_path = texture_dir / "front.png"
    duplicate_path = texture_dir / "front (1).png"
    assert materialized_path.exists()
    assert duplicate_path.exists()
    assert app.editor_state.face_texture_assignments["cube"][0] == str(materialized_path.resolve()).lower()


def test_settings_button_opens_preferences_window_with_expected_sections(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
) -> None:
    root, app = built_app

    app.toolbar_settings_button.invoke()
    root.update_idletasks()
    texts = _collect_widget_texts(app._preferences_window)

    assert app._preferences_window is not None
    assert app._preferences_window.title() == "Preferences"
    assert "PREFERENCES" in texts
    assert "General" in texts
    assert "Viewport" in texts
    assert "Background" in texts
    assert "Lighting Intensity" in texts
    assert "Rotate View Speed" in texts
    assert "Apply" in texts
    assert "Cancel" in texts


def test_preferences_apply_updates_live_state_and_persists(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _root, app = built_app
    saved_states: list[dict[str, object]] = []
    image_path = tmp_path / "background.png"
    Image.new("RGBA", (4, 4), (20, 40, 80, 255)).save(image_path)
    monkeypatch.setattr(app_module, "save_app_state", lambda data: saved_states.append(data))

    app.open_preferences_window()
    assert app._preferences_show_floor_grid_var is not None
    assert app._preferences_show_face_highlight_var is not None
    assert app._preferences_background_enabled_var is not None
    assert app._preferences_background_image_path_var is not None
    app._preferences_show_floor_grid_var.set(False)
    app._preferences_show_face_highlight_var.set(False)
    assert app._preferences_lighting_intensity_var is not None
    assert app._preferences_autorotate_speed_var is not None
    app._preferences_lighting_intensity_var.set("125%")
    app._preferences_autorotate_speed_var.set("125%")
    app._preferences_background_enabled_var.set(True)
    app._preferences_background_image_path_var.set(str(image_path))

    app._apply_preferences_window_changes()

    assert app.preferences == AppPreferences(
        show_floor_grid=False,
        show_face_highlight=False,
        lighting_intensity=1.25,
        autorotate_speed=1.25,
        background_enabled=True,
        background_image_path=str(image_path),
    )
    assert saved_states
    assert saved_states[-1]["preferences"] == {
        "show_floor_grid": False,
        "show_face_highlight": False,
        "lighting_intensity": 1.25,
        "autorotate_speed": 1.25,
        "background_enabled": True,
        "background_image_path": str(image_path),
    }
    assert app._preferences_window is None


def test_preferences_dirty_close_can_be_cancelled(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, app = built_app
    prompts: list[str] = []
    monkeypatch.setattr(
        app_module.messagebox,
        "askyesno",
        lambda **_kwargs: prompts.append("asked") or False,
    )

    app.open_preferences_window()
    assert app._preferences_show_floor_grid_var is not None
    app._preferences_show_floor_grid_var.set(False)

    closed = app._close_preferences_window()

    assert closed is False
    assert prompts == ["asked"]
    assert app._preferences_window is not None
    assert app.preferences == AppPreferences()


def test_preferences_reset_defaults_restores_dialog_values(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
) -> None:
    _root, app = built_app

    app.open_preferences_window()
    assert app._preferences_show_floor_grid_var is not None
    assert app._preferences_show_face_highlight_var is not None
    assert app._preferences_background_enabled_var is not None
    assert app._preferences_background_image_path_var is not None
    assert app._preferences_lighting_intensity_var is not None
    assert app._preferences_autorotate_speed_var is not None
    app._preferences_show_floor_grid_var.set(False)
    app._preferences_show_face_highlight_var.set(False)
    app._preferences_lighting_intensity_var.set("125%")
    app._preferences_autorotate_speed_var.set("125%")
    app._preferences_background_enabled_var.set(True)
    app._preferences_background_image_path_var.set("C:/tmp/background.png")

    app._reset_preferences_dialog_defaults()

    assert app._preferences_show_floor_grid_var.get() is True
    assert app._preferences_show_face_highlight_var.get() is True
    assert app._preferences_lighting_intensity_var.get() == "100%"
    assert app._preferences_autorotate_speed_var.get() == "100%"
    assert app._preferences_background_enabled_var.get() is False
    assert app._preferences_background_image_path_var.get() == ""


def test_opening_preferences_while_rotating_restores_camera(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
) -> None:
    _root, app = built_app
    original_camera = app.editor_state.camera

    app._toggle_rotating_view()
    assert app._autorotate_active is True

    app.open_preferences_window()

    assert app._autorotate_active is False
    assert app.editor_state.camera == original_camera
    assert app._preferences_window is not None


def test_autorotate_speed_preference_changes_yaw_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "load_app_state", lambda: {})
    monkeypatch.setattr(app_module, "save_app_state", lambda _data: None)
    monkeypatch.setattr(app_module.PixelFixStudio3DApp, "_configure_window_icon", lambda self: None)
    monkeypatch.setattr(app_module.PixelFixStudio3DApp, "_render_viewport", lambda self: None)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    try:
        app = app_module.PixelFixStudio3DApp(root)
        app.preferences = AppPreferences(autorotate_speed=1.25)
        app._autorotate_active = True
        old_yaw = app.editor_state.camera.yaw
        monkeypatch.setattr(root, "after", lambda _ms, _callback: "after-id")

        app._run_autorotate()

        assert app.editor_state.camera.yaw == pytest.approx(old_yaw + (app_module.AUTOROTATE_YAW_STEP * 1.25))
        assert app._autorotate_job == "after-id"
    finally:
        if root.winfo_exists():
            root.destroy()


def test_saved_preferences_reload_on_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_module,
        "load_app_state",
        lambda: {
            "last_shape_key": "cube",
            "preferences": {
                "show_floor_grid": False,
                "show_face_highlight": False,
                "lighting_intensity": 1.25,
                "autorotate_speed": 0.75,
                "background_enabled": True,
                "background_image_path": "C:/tmp/bg.png",
            },
        },
    )
    monkeypatch.setattr(app_module, "save_app_state", lambda _data: None)
    monkeypatch.setattr(app_module.PixelFixStudio3DApp, "_configure_window_icon", lambda self: None)
    monkeypatch.setattr(app_module.PixelFixStudio3DApp, "_render_viewport", lambda self: None)
    monkeypatch.setattr(app_module.PixelFixStudio3DApp, "_run_autorotate", lambda self: None)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    try:
        app = app_module.PixelFixStudio3DApp(root)
        assert app.preferences == AppPreferences(
            show_floor_grid=False,
            show_face_highlight=False,
            lighting_intensity=1.25,
            autorotate_speed=0.75,
            background_enabled=True,
            background_image_path="C:/tmp/bg.png",
        )
    finally:
        if root.winfo_exists():
            root.destroy()


def test_viewport_background_array_stretches_png_and_invalid_path_falls_back(
    built_app: tuple[tk.Tk, app_module.PixelFixStudio3DApp],
    tmp_path,
) -> None:
    _root, app = built_app
    image_path = tmp_path / "background.png"
    image = Image.new("RGBA", (2, 1))
    image.putpixel((0, 0), (255, 0, 0, 255))
    image.putpixel((1, 0), (0, 255, 0, 255))
    image.save(image_path)

    app.preferences = AppPreferences(background_enabled=True, background_image_path=str(image_path))
    app._invalidate_viewport_background_cache()
    rgb = app._viewport_background_array()

    assert rgb is not None
    assert rgb.shape == (app_module.VIEWPORT_HEIGHT, app_module.VIEWPORT_WIDTH, 3)
    assert tuple(int(value) for value in rgb[app_module.VIEWPORT_HEIGHT // 2, 8]) == (255, 0, 0)
    assert tuple(int(value) for value in rgb[app_module.VIEWPORT_HEIGHT // 2, app_module.VIEWPORT_WIDTH - 8]) == (0, 255, 0)

    app.preferences = AppPreferences(background_enabled=True, background_image_path=str(image_path.with_name("missing.png")))
    app._invalidate_viewport_background_cache()
    assert app._viewport_background_array() is None
