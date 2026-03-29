from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from pixel_fix_3d.textures import load_texture_bytes, load_texture_library


def test_texture_library_loads_sizes_and_skips_duplicates(tmp_path: Path) -> None:
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(image_a)
    Image.new("RGBA", (64, 32), (0, 255, 0, 255)).save(image_b)

    textures, errors = load_texture_library([image_a, image_b, image_a])
    assert not errors
    assert [entry.size for entry in textures] == [(16, 16), (64, 32)]


def test_texture_library_reports_invalid_images(tmp_path: Path) -> None:
    broken = tmp_path / "broken.png"
    broken.write_text("not an image", encoding="utf-8")
    textures, errors = load_texture_library([broken])
    assert textures == []
    assert errors


def test_load_texture_bytes_creates_in_memory_texture() -> None:
    image = Image.new("RGBA", (8, 4), (10, 20, 30, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    entry = load_texture_bytes(buffer.getvalue(), texture_id="memory:test", name="test.png")
    assert entry.path is None
    assert entry.size == (8, 4)
    assert entry.texture_id == "memory:test"
