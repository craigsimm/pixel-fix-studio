from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from pixel_fix_3d.renderer import RenderOptions, SoftwareRenderer, sample_texture_nearest
from pixel_fix_3d.shapes import SHAPE_PRESETS_BY_KEY
from pixel_fix_3d.state import CameraState
from pixel_fix_3d.textures import TextureEntry


def test_sample_texture_nearest_uses_exact_pixels() -> None:
    texture = np.array(
        [
            [[255, 0, 0, 255], [0, 255, 0, 255]],
            [[0, 0, 255, 255], [255, 255, 0, 255]],
        ],
        dtype=np.uint8,
    )
    assert np.array_equal(sample_texture_nearest(texture, 0.0, 0.0), np.array([255, 0, 0, 255], dtype=np.uint8))
    assert np.array_equal(sample_texture_nearest(texture, 1.0, 0.0), np.array([0, 255, 0, 255], dtype=np.uint8))
    assert np.array_equal(sample_texture_nearest(texture, 0.0, 1.0), np.array([0, 0, 255, 255], dtype=np.uint8))
    assert np.array_equal(sample_texture_nearest(texture, 1.0, 1.0), np.array([255, 255, 0, 255], dtype=np.uint8))


def test_renderer_face_id_buffer_matches_front_face() -> None:
    renderer = SoftwareRenderer(width=64, height=64)
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    result = renderer.render(shape=shape, camera=CameraState(yaw=0.0, pitch=0.0, distance=4.25), textures_by_face={})
    face_id = int(result.face_id_buffer[32, 32])
    assert shape.face_by_id(face_id).label == "Front"
    visible_ids = set(int(value) for value in np.unique(result.face_id_buffer) if value >= 0)
    assert visible_ids == {0}


def test_renderer_applies_assigned_texture_to_front_face() -> None:
    renderer = SoftwareRenderer(width=64, height=64)
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    texture_entry = TextureEntry(
        texture_id="solid",
        name="solid.png",
        path=Path("solid.png"),
        size=(1, 1),
        image=Image.new("RGBA", (1, 1), (200, 50, 25, 255)),
    )
    result = renderer.render(
        shape=shape,
        camera=CameraState(yaw=0.0, pitch=0.0, distance=4.25),
        textures_by_face={0: texture_entry},
    )
    pixel = np.asarray(result.image)[32, 32]
    assert pixel[0] > pixel[1]
    assert pixel[0] > pixel[2]


def test_renderer_respects_requested_output_size() -> None:
    renderer = SoftwareRenderer(width=96, height=48)
    result = renderer.render(
        shape=SHAPE_PRESETS_BY_KEY["cube"],
        camera=CameraState(),
        textures_by_face={},
    )
    assert result.image.size == (96, 48)
    assert result.face_id_buffer.shape == (48, 96)


def test_renderer_floor_grid_changes_background_without_affecting_picking() -> None:
    renderer = SoftwareRenderer(width=64, height=64)
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    no_grid = renderer.render(
        shape=shape,
        camera=CameraState(),
        textures_by_face={},
        options=RenderOptions(show_floor_grid=False, show_face_highlight=False),
    )
    with_grid = renderer.render(
        shape=shape,
        camera=CameraState(),
        textures_by_face={},
        options=RenderOptions(show_floor_grid=True, show_face_highlight=False),
    )
    no_grid_pixels = np.asarray(no_grid.image)
    with_grid_pixels = np.asarray(with_grid.image)

    assert np.array_equal(no_grid.face_id_buffer, with_grid.face_id_buffer)
    assert np.any(np.any(no_grid_pixels != with_grid_pixels, axis=2))
    assert np.any(np.any(no_grid_pixels[with_grid.face_id_buffer < 0] != with_grid_pixels[with_grid.face_id_buffer < 0], axis=1))


def test_renderer_respects_background_buffer() -> None:
    renderer = SoftwareRenderer(width=32, height=24)
    background = np.zeros((24, 32, 3), dtype=np.uint8)
    background[:, :, 0] = 12
    background[:, :, 1] = 34
    background[:, :, 2] = 56
    result = renderer.render(
        shape=SHAPE_PRESETS_BY_KEY["cube"],
        camera=CameraState(),
        textures_by_face={},
        options=RenderOptions(show_floor_grid=False, background_rgb=background),
    )
    pixel = np.asarray(result.image)[0, 0]
    assert np.array_equal(pixel, np.array([12, 34, 56], dtype=np.uint8))


def test_renderer_can_disable_selected_face_highlight() -> None:
    renderer = SoftwareRenderer(width=64, height=64)
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    unhighlighted = renderer.render(
        shape=shape,
        camera=CameraState(yaw=0.0, pitch=0.0, distance=4.25),
        textures_by_face={},
        selected_face_id=0,
        options=RenderOptions(show_floor_grid=False, show_face_highlight=False),
    )
    highlighted = renderer.render(
        shape=shape,
        camera=CameraState(yaw=0.0, pitch=0.0, distance=4.25),
        textures_by_face={},
        selected_face_id=0,
        options=RenderOptions(show_floor_grid=False, show_face_highlight=True),
    )
    assert not np.array_equal(np.asarray(unhighlighted.image)[32, 32], np.asarray(highlighted.image)[32, 32])


def test_renderer_applies_lighting_intensity() -> None:
    renderer = SoftwareRenderer(width=64, height=64)
    shape = SHAPE_PRESETS_BY_KEY["cube"]
    flatter = renderer.render(
        shape=shape,
        camera=CameraState(),
        textures_by_face={},
        options=RenderOptions(show_floor_grid=False, show_face_highlight=False, lighting_intensity=0.5),
    )
    higher_contrast = renderer.render(
        shape=shape,
        camera=CameraState(),
        textures_by_face={},
        options=RenderOptions(show_floor_grid=False, show_face_highlight=False, lighting_intensity=1.5),
    )
    flatter_pixels = np.asarray(flatter.image, dtype=np.float64)
    higher_contrast_pixels = np.asarray(higher_contrast.image, dtype=np.float64)
    flatter_mask = flatter.face_id_buffer >= 0
    higher_contrast_mask = higher_contrast.face_id_buffer >= 0
    flatter_luma = flatter_pixels[flatter_mask].mean(axis=1)
    higher_contrast_luma = higher_contrast_pixels[higher_contrast_mask].mean(axis=1)

    assert float(higher_contrast_luma.std()) > float(flatter_luma.std())
    assert float(higher_contrast_luma.std()) >= float(flatter_luma.std()) * 1.4
