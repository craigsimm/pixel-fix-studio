from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from pygltflib import CLAMP_TO_EDGE, GLTF2, NEAREST

from pixel_fix_3d.glb_export import export_glb
from pixel_fix_3d.shapes import SHAPE_PRESETS_BY_KEY, recommended_texture_size
from pixel_fix_3d.textures import TextureEntry


def _texture(texture_id: str, name: str, size: tuple[int, int], color: tuple[int, int, int, int]) -> TextureEntry:
    return TextureEntry(
        texture_id=texture_id,
        name=name,
        path=None,
        size=size,
        image=Image.new("RGBA", size, color),
    )


def _embedded_image(gltf: GLTF2, image_index: int) -> Image.Image:
    blob = gltf.binary_blob()
    assert blob is not None
    image = gltf.images[image_index]
    assert image.bufferView is not None
    view = gltf.bufferViews[image.bufferView]
    data = blob[view.byteOffset : view.byteOffset + view.byteLength]
    with Image.open(BytesIO(data)) as decoded:
        return decoded.convert("RGBA").copy()


def _primitive_positions(gltf: GLTF2, primitive_index: int) -> np.ndarray:
    blob = gltf.binary_blob()
    assert blob is not None
    primitive = gltf.meshes[0].primitives[primitive_index]
    accessor = gltf.accessors[primitive.attributes.POSITION]
    view = gltf.bufferViews[accessor.bufferView]
    start = view.byteOffset + accessor.byteOffset
    stop = start + (accessor.count * 3 * 4)
    return np.frombuffer(blob[start:stop], dtype=np.float32).reshape(accessor.count, 3)


def test_export_glb_writes_valid_cube_scene_with_embedded_face_assets(tmp_path: Path) -> None:
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    output = tmp_path / "cube.glb"

    export_glb(output, shape, {})
    gltf = GLTF2.load_binary(output)

    assert gltf.scene == 0
    assert len(gltf.scenes) == 1
    assert gltf.scenes[0].nodes == [0]
    assert len(gltf.nodes) == 1
    assert len(gltf.meshes) == 1
    assert len(gltf.meshes[0].primitives) == len(shape.face_groups)
    assert len(gltf.images) == len(shape.face_groups)
    assert len(gltf.textures) == len(shape.face_groups)
    assert len(gltf.materials) == len(shape.face_groups)
    assert gltf.extensionsUsed == ["KHR_materials_unlit"]
    assert gltf.extensionsRequired == ["KHR_materials_unlit"]
    assert gltf.samplers[0].magFilter == NEAREST
    assert gltf.samplers[0].minFilter == NEAREST
    assert gltf.samplers[0].wrapS == CLAMP_TO_EDGE
    assert gltf.samplers[0].wrapT == CLAMP_TO_EDGE
    assert gltf.materials[0].extensions == {"KHR_materials_unlit": {}}

    mins = [positions[:, 1].min() for positions in (_primitive_positions(gltf, index) for index in range(len(shape.face_groups)))]
    assert min(mins) == 0.0

    template_image = _embedded_image(gltf, 0)
    assert template_image.size == recommended_texture_size(shape.face_groups[0])
    assert template_image.getpixel((0, 0)) == (128, 128, 128, 255)


def test_export_glb_preserves_assigned_face_texture_png_bytes(tmp_path: Path) -> None:
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    output = tmp_path / "textured.glb"
    textures = {
        0: _texture("front", "front.png", (16, 16), (255, 0, 0, 255)),
        1: _texture("back", "back.png", (24, 16), (0, 255, 0, 255)),
    }

    export_glb(output, shape, textures)
    gltf = GLTF2.load_binary(output)

    first = _embedded_image(gltf, 0)
    second = _embedded_image(gltf, 1)
    third = _embedded_image(gltf, 2)
    assert first.size == (16, 16)
    assert first.getpixel((0, 0)) == (255, 0, 0, 255)
    assert second.size == (24, 16)
    assert second.getpixel((0, 0)) == (0, 255, 0, 255)
    assert third.getpixel((0, 0)) == (128, 128, 128, 255)


def test_export_glb_shape_coverage_for_complex_presets(tmp_path: Path) -> None:
    for shape_key in ("plane_2d", "roof", "cylinder", "table", "chair", "car"):
        shape = SHAPE_PRESETS_BY_KEY[shape_key]
        output = tmp_path / f"{shape_key}.glb"

        export_glb(output, shape, {})
        gltf = GLTF2.load_binary(output)

        assert len(gltf.meshes) == 1
        assert len(gltf.meshes[0].primitives) == len(shape.face_groups)
        assert len(gltf.images) == len(shape.face_groups)
        assert len(gltf.materials) == len(shape.face_groups)
