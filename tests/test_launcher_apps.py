from pathlib import Path

import pixel_fix_studio.launcher_apps as launcher_apps
from pixel_fix_studio.launcher_apps import build_launch_request, resolve_app_installation, validate_install_dir
from pixel_fix_studio.models import LauncherSettings


def _make_source_app(root: Path, *, data_folder: str, package_name: str) -> Path:
    root.mkdir(parents=True)
    (root / "data" / data_folder).mkdir(parents=True)
    (root / "src" / package_name).mkdir(parents=True)
    return root


def _make_bundled_app(root: Path, *, app_id: str, executable_name: str, data_folder: str) -> Path:
    root.mkdir(parents=True)
    (root / executable_name).write_text("", encoding="utf-8")
    (root / "data" / data_folder).mkdir(parents=True)
    (root / "app-manifest.json").write_text(
        (
            "{"
            f"\"app_id\": \"{app_id}\", "
            f"\"display_name\": \"{app_id}\", "
            "\"version\": \"1.0.0\", "
            f"\"executable\": \"{executable_name}\""
            "}"
        ),
        encoding="utf-8",
    )
    return root


def test_validate_install_dir_seeds_source_palette_library_from_resources(tmp_path: Path) -> None:
    source_root = tmp_path / "pixel-fix-2D"
    (source_root / "src" / "pixel_fix" / "resources" / "palettes" / "Curated").mkdir(parents=True)
    (source_root / "src" / "pixel_fix").mkdir(parents=True, exist_ok=True)
    palette_path = source_root / "src" / "pixel_fix" / "resources" / "palettes" / "Curated" / "db16.gpl"
    palette_path.write_text("GIMP Palette\n0 0 0 Black\n255 255 255 White\n", encoding="utf-8")

    installation = validate_install_dir(source_root, "pixel_fix_2d")

    seeded_palette = source_root / "data" / "palettes" / "Curated" / "db16.gpl"
    assert installation.installed is True
    assert seeded_palette.exists()


def test_resolve_app_installation_seeds_bundled_palette_library_from_resources(tmp_path: Path) -> None:
    studio_root = tmp_path / "pixel-fix-studio"
    bundled = _make_bundled_app(
        studio_root / "apps" / "pixel-fix-2d",
        app_id="pixel-fix-2d",
        executable_name="Pixel-Fix 2D.exe",
        data_folder="palettes",
    )
    resource_palette = bundled / "_internal" / "pixel_fix" / "resources" / "palettes" / "Curated"
    resource_palette.mkdir(parents=True)
    (resource_palette / "db16.gpl").write_text("GIMP Palette\n0 0 0 Black\n255 255 255 White\n", encoding="utf-8")

    installation = resolve_app_installation(studio_root, LauncherSettings(), "pixel_fix_2d")

    seeded_palette = bundled / "data" / "palettes" / "Curated" / "db16.gpl"
    assert installation.installed is True
    assert seeded_palette.exists()


def test_resolve_app_installation_prefers_bundled_apps_over_source(tmp_path: Path) -> None:
    studio_root = tmp_path / "pixel-fix-studio"
    _make_source_app(studio_root / "pixel-fix-2D", data_folder="palettes", package_name="pixel_fix")
    bundled = _make_bundled_app(
        studio_root / "apps" / "pixel-fix-2d",
        app_id="pixel-fix-2d",
        executable_name="Pixel-Fix 2D.exe",
        data_folder="palettes",
    )

    installation = resolve_app_installation(studio_root, LauncherSettings(), "pixel_fix_2d")

    assert installation.installed is True
    assert installation.mode == "bundled"
    assert installation.install_root == bundled.resolve()


def test_resolve_app_installation_uses_custom_install_when_defaults_missing(tmp_path: Path) -> None:
    studio_root = tmp_path / "pixel-fix-studio"
    studio_root.mkdir()
    custom = _make_bundled_app(
        tmp_path / "custom-3d",
        app_id="pixel-fix-3d",
        executable_name="Pixel-Fix 3D.exe",
        data_folder="textures",
    )

    installation = resolve_app_installation(
        studio_root,
        LauncherSettings(pixel_fix_3d_install_dir=str(custom)),
        "pixel_fix_3d",
    )

    assert installation.installed is True
    assert installation.mode == "custom"
    assert installation.install_root == custom.resolve()


def test_resolve_app_installation_reports_exact_missing_message(tmp_path: Path) -> None:
    studio_root = tmp_path / "pixel-fix-studio"
    studio_root.mkdir()

    installation = resolve_app_installation(studio_root, LauncherSettings(), "pixel_fix_2d")

    assert installation.installed is False
    assert installation.missing_app_message == "Pixel-Fix 2D is not installed."


def test_build_launch_request_for_source_2d_includes_open_argument(tmp_path: Path) -> None:
    source_root = _make_source_app(tmp_path / "pixel-fix-2D", data_folder="palettes", package_name="pixel_fix")
    installation = validate_install_dir(source_root, "pixel_fix_2d")
    project_file = tmp_path / "sprite.png"
    project_file.write_text("", encoding="utf-8")

    request = build_launch_request(installation, open_path=project_file)

    assert request.cwd == source_root.resolve()
    assert request.command[1:4] == ["-m", "pixel_fix.gui", "--open"]
    assert request.command[-1] == str(project_file)
    assert request.env is not None
    assert str(source_root / "src") in request.env["PYTHONPATH"]


def test_preferred_source_python_prefers_workspace_venv_for_combined_workspace(tmp_path: Path, monkeypatch) -> None:
    workspace_root = tmp_path / "pixel-fix-studio"
    source_root = _make_source_app(workspace_root / "pixel-fix-3D", data_folder="textures", package_name="pixel_fix_3d")
    (workspace_root / "src" / "pixel_fix_studio").mkdir(parents=True)

    workspace_python = workspace_root / ".venv" / "Scripts" / "python.exe"
    workspace_python.parent.mkdir(parents=True)
    workspace_python.write_text("", encoding="utf-8")

    local_python = source_root / ".venv" / "Scripts" / "python.exe"
    local_python.parent.mkdir(parents=True)
    local_python.write_text("", encoding="utf-8")

    current_python = tmp_path / "external-python" / "python.exe"
    current_python.parent.mkdir(parents=True)
    current_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(launcher_apps.sys, "executable", str(current_python))

    selected = launcher_apps.preferred_source_python(source_root)

    assert selected == workspace_python.resolve()


def test_preferred_source_python_prefers_local_venv_for_standalone_source_app(tmp_path: Path, monkeypatch) -> None:
    source_root = _make_source_app(tmp_path / "pixel-fix-3D", data_folder="textures", package_name="pixel_fix_3d")

    local_python = source_root / ".venv" / "Scripts" / "python.exe"
    local_python.parent.mkdir(parents=True)
    local_python.write_text("", encoding="utf-8")

    current_python = tmp_path / "shared-python" / "python.exe"
    current_python.parent.mkdir(parents=True)
    current_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(launcher_apps.sys, "executable", str(current_python))

    selected = launcher_apps.preferred_source_python(source_root)

    assert selected == local_python.resolve()
