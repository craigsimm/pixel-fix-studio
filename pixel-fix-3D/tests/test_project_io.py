from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from pixel_fix_3d.project_io import Pfx3dError, extract_face_textures, load_pfx3d, save_pfx3d
from pixel_fix_3d.shapes import SHAPE_PRESETS_BY_KEY, recommended_texture_size
from pixel_fix_3d.textures import TextureEntry


def _png_bytes(size: tuple[int, int], color: tuple[int, int, int, int]) -> bytes:
    image = Image.new("RGBA", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _texture(texture_id: str, name: str, size: tuple[int, int], color: tuple[int, int, int, int]) -> TextureEntry:
    return TextureEntry(
        texture_id=texture_id,
        name=name,
        path=None,
        size=size,
        image=Image.new("RGBA", size, color),
    )


def test_pfx3d_roundtrip_preserves_shape_and_face_textures(tmp_path: Path) -> None:
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    output = tmp_path / "crate.pfx3d"
    textures = {
        0: _texture("front", "front.png", (16, 16), (255, 0, 0, 255)),
        1: _texture("back", "back.png", (32, 16), (0, 255, 0, 255)),
    }

    save_pfx3d(output, shape, textures)
    project = load_pfx3d(output)

    assert project.shape_key == "cube"
    assert len(project.faces) == len(shape.face_groups)
    assert tuple(face.texture_file for face in project.faces[:2]) == ("textures/00-front.png", "textures/01-back.png")
    assert project.faces[0].image.size == (16, 16)
    assert project.faces[1].image.size == (32, 16)
    assert project.faces[0].image.getpixel((0, 0)) == (255, 0, 0, 255)
    template_face = next(face for face in project.faces if face.face_id == 2)
    assert template_face.image.size == recommended_texture_size(shape.face_by_id(2))
    assert template_face.image.getpixel((0, 0)) == (128, 128, 128, 255)


def test_load_pfx3d_rejects_bad_archive(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pfx3d"
    broken.write_text("not zip", encoding="utf-8")
    with pytest.raises(Pfx3dError):
        load_pfx3d(broken)


def test_load_pfx3d_rejects_bad_json(tmp_path: Path) -> None:
    broken = tmp_path / "broken-json.pfx3d"
    with zipfile.ZipFile(broken, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", "{bad json")
    with pytest.raises(Pfx3dError):
        load_pfx3d(broken)


def test_load_pfx3d_rejects_unsupported_version(tmp_path: Path) -> None:
    invalid = tmp_path / "unsupported.pfx3d"
    manifest = {
        "format": "pfx3d",
        "version": 99,
        "shape_key": "cube",
        "faces": [],
    }
    with zipfile.ZipFile(invalid, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(manifest))
    with pytest.raises(Pfx3dError):
        load_pfx3d(invalid)


def test_load_pfx3d_rejects_unknown_shape(tmp_path: Path) -> None:
    invalid = tmp_path / "unknown-shape.pfx3d"
    manifest = {
        "format": "pfx3d",
        "version": 1,
        "shape_key": "unknown",
        "faces": [],
    }
    with zipfile.ZipFile(invalid, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(manifest))
    with pytest.raises(Pfx3dError):
        load_pfx3d(invalid)


def test_load_pfx3d_rejects_face_id_mismatch(tmp_path: Path) -> None:
    invalid = tmp_path / "bad-faces.pfx3d"
    manifest = {
        "format": "pfx3d",
        "version": 1,
        "shape_key": "cube",
        "faces": [
            {"face_id": 0, "face_label": "Front", "texture_file": "textures/00-front.png"},
            {"face_id": 99, "face_label": "Missing", "texture_file": "textures/99-missing.png"},
        ],
    }
    with zipfile.ZipFile(invalid, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(manifest))
        archive.writestr("textures/00-front.png", _png_bytes((16, 16), (255, 0, 0, 255)))
        archive.writestr("textures/99-missing.png", _png_bytes((16, 16), (0, 255, 0, 255)))
    with pytest.raises(Pfx3dError):
        load_pfx3d(invalid)


def test_load_pfx3d_rejects_missing_embedded_texture(tmp_path: Path) -> None:
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    manifest = {
        "format": "pfx3d",
        "version": 1,
        "shape_key": "cube",
        "faces": [
            {
                "face_id": face.face_id,
                "face_label": face.label,
                "texture_file": f"textures/{face.face_id:02d}.png",
            }
            for face in shape.face_groups
        ],
    }
    invalid = tmp_path / "missing-texture.pfx3d"
    with zipfile.ZipFile(invalid, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(manifest))
    with pytest.raises(Pfx3dError):
        load_pfx3d(invalid)


def test_extract_face_textures_writes_one_png_per_face_and_suffixes_directory(tmp_path: Path) -> None:
    shape = SHAPE_PRESETS_BY_KEY["box"]
    textures = {
        0: _texture("front", "front.png", (24, 24), (200, 20, 10, 255)),
    }

    export_a = extract_face_textures(tmp_path, shape, textures)
    export_b = extract_face_textures(tmp_path, shape, textures)

    assert export_a.name == "box_textures"
    assert export_b.name == "box_textures_2"
    written = sorted(path.name for path in export_a.glob("*.png"))
    assert len(written) == len(shape.face_groups)
    assert written[0] == "00-front.png"

    front_image = Image.open(export_a / "00-front.png")
    assert front_image.size == (24, 24)
    assert front_image.getpixel((0, 0)) == (200, 20, 10, 255)

    right_face = shape.face_by_id(2)
    assert right_face is not None
    right_image = Image.open(export_a / "02-right.png")
    assert right_image.size == recommended_texture_size(right_face)
    assert right_image.getpixel((0, 0)) == (128, 128, 128, 255)
