import json
from pathlib import Path

from PIL import Image

from pixel_fix_studio.recent import load_recent_project_items


def test_load_recent_project_items_filters_missing_and_duplicate_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings_dir = tmp_path / "pixel-fix"
    settings_dir.mkdir(parents=True)

    existing = tmp_path / "recent.png"
    Image.new("RGBA", (4, 4), "#00ffff").save(existing)
    missing = tmp_path / "missing.png"
    settings_path = settings_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"recent_files": [str(existing), str(missing), str(existing)]}),
        encoding="utf-8",
    )

    items = load_recent_project_items()

    assert [item.path for item in items] == [existing.resolve()]
    assert items[0].thumbnail_supported is True
