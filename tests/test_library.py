from pathlib import Path

from PIL import Image

from pixel_fix_studio.app import build_palette_preview_image
from pixel_fix_studio.library import (
    create_library_folder,
    delete_library_item,
    import_palette_file,
    list_library_folders,
    list_palette_items,
    list_texture_items,
    move_library_item,
)

VALID_GPL = """GIMP Palette
Name: Test
Columns: 4
#
  0   0   0\tBlack
255 255 255\tWhite
"""


def test_palette_library_mutations_work_within_root(tmp_path: Path) -> None:
    root = tmp_path / "palettes"
    root.mkdir()
    destination_folder = create_library_folder(root, root, "Custom")
    source = tmp_path / "sample.gpl"
    source.write_text(VALID_GPL, encoding="utf-8")

    imported = import_palette_file(root, root, source)
    items = list_palette_items(root)
    moved = move_library_item(root, imported, destination_folder)

    assert [item.name for item in items] == ["sample.gpl"]
    assert items[0].colors == (0x000000, 0xFFFFFF)
    assert moved.parent == destination_folder

    delete_library_item(root, moved)

    assert not moved.exists()
    nodes = list_library_folders(root)
    assert [node.label for node in nodes] == ["palettes", "Custom"]


def test_texture_library_reports_valid_and_invalid_images(tmp_path: Path) -> None:
    root = tmp_path / "textures"
    root.mkdir()
    Image.new("RGBA", (8, 4), "#ff00ff").save(root / "good.png")
    (root / "bad.png").write_text("not an image", encoding="utf-8")

    items = {item.name: item for item in list_texture_items(root)}

    assert items["good.png"].size == (8, 4)
    assert items["good.png"].error is None
    assert items["bad.png"].size is None
    assert items["bad.png"].error is not None


def test_palette_preview_handles_large_palette_without_invalid_rectangles() -> None:
    colors = tuple(index & 0xFFFFFF for index in range(256))

    image = build_palette_preview_image(colors, (80, 48), background="#2B2D2D")

    assert image.size == (80, 48)
