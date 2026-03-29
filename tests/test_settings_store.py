import json
from pathlib import Path

from pixel_fix_studio.models import LauncherSettings
from pixel_fix_studio.settings_store import (
    detect_default_install_dirs,
    load_launcher_settings,
    resolve_initial_settings,
    save_launcher_settings,
    validate_pixel_fix_2d_install_dir,
    validate_pixel_fix_3d_install_dir,
)


def _make_source_app(root: Path, *, data_folder: str, package_name: str) -> Path:
    root.mkdir(parents=True)
    (root / "data" / data_folder).mkdir(parents=True)
    (root / "src" / package_name).mkdir(parents=True)
    return root


def test_detect_default_install_dirs_finds_child_source_layout(tmp_path: Path) -> None:
    studio_root = tmp_path / "pixel-fix-studio"
    studio_root.mkdir()
    two_d = _make_source_app(studio_root / "pixel-fix-2D", data_folder="palettes", package_name="pixel_fix")
    three_d = _make_source_app(studio_root / "pixel-fix-3D", data_folder="textures", package_name="pixel_fix_3d")

    detected = detect_default_install_dirs(studio_root)

    assert detected.pixel_fix_2d_install_dir == str(two_d.resolve())
    assert detected.pixel_fix_3d_install_dir == str(three_d.resolve())


def test_resolve_initial_settings_keeps_valid_custom_install_dirs(tmp_path: Path) -> None:
    two_d = _make_source_app(tmp_path / "custom-2d", data_folder="palettes", package_name="pixel_fix")
    three_d = _make_source_app(tmp_path / "custom-3d", data_folder="textures", package_name="pixel_fix_3d")

    resolved = resolve_initial_settings(
        tmp_path / "pixel-fix-studio",
        LauncherSettings(
            pixel_fix_2d_install_dir=str(two_d),
            pixel_fix_3d_install_dir=str(three_d),
        ),
    )

    assert resolved.pixel_fix_2d_install_dir == str(two_d.resolve())
    assert resolved.pixel_fix_3d_install_dir == str(three_d.resolve())


def test_validate_install_dir_rejects_missing_data_folder(tmp_path: Path) -> None:
    broken = tmp_path / "pixel-fix-2D"
    broken.mkdir()
    (broken / "src" / "pixel_fix").mkdir(parents=True)

    valid_root, message = validate_pixel_fix_2d_install_dir(broken)

    assert valid_root is None
    assert message == "Missing data/palettes folder."


def test_load_launcher_settings_supports_legacy_keys(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings_dir = tmp_path / "pixel-fix-studio"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text(
        json.dumps(
            {
                "pixel_fix_2d_dir": "C:/legacy/pixel-fix",
                "pixel_fix_3d_dir": "C:/legacy/pixel-fix-3D",
            }
        ),
        encoding="utf-8",
    )

    loaded = load_launcher_settings()

    assert loaded.pixel_fix_2d_install_dir == "C:/legacy/pixel-fix"
    assert loaded.pixel_fix_3d_install_dir == "C:/legacy/pixel-fix-3D"


def test_save_and_load_launcher_settings_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = LauncherSettings(
        pixel_fix_2d_install_dir="C:/pixel-fix-2D",
        pixel_fix_3d_install_dir="C:/pixel-fix-3D",
    )

    save_launcher_settings(settings)

    assert load_launcher_settings() == settings
