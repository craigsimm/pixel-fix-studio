from __future__ import annotations

import math

from pixel_fix_3d.shapes import SHAPE_PRESETS, SHAPE_PRESETS_BY_KEY, recommended_texture_size


EXPECTED_FACE_COUNTS = {
    "cube": 6,
    "box": 6,
    "tall_box": 6,
    "wedge": 5,
    "ramp": 6,
    "cylinder": 10,
    "roof": 7,
    "car": 50,
}

EXPECTED_SHAPE_ORDER = ("cube", "box", "tall_box", "wedge", "ramp", "cylinder", "roof", "car")


def _face_normal(vertices: tuple[tuple[float, float, float], ...]) -> tuple[float, float, float]:
    ax, ay, az = vertices[0]
    bx, by, bz = vertices[1]
    cx, cy, cz = vertices[2]
    ux, uy, uz = (bx - ax, by - ay, bz - az)
    vx, vy, vz = (cx - ax, cy - ay, cz - az)
    return (
        (uy * vz) - (uz * vy),
        (uz * vx) - (ux * vz),
        (ux * vy) - (uy * vx),
    )


def test_shape_face_counts() -> None:
    for key, expected_count in EXPECTED_FACE_COUNTS.items():
        assert len(SHAPE_PRESETS_BY_KEY[key].face_groups) == expected_count


def test_shape_registry_exposes_expected_presets() -> None:
    assert tuple(shape.key for shape in SHAPE_PRESETS) == EXPECTED_SHAPE_ORDER
    assert "stairs" not in SHAPE_PRESETS_BY_KEY


def test_every_face_has_matching_uvs_in_unit_range() -> None:
    for shape in SHAPE_PRESETS_BY_KEY.values():
        for face in shape.face_groups:
            assert len(face.vertices) == len(face.uvs)
            assert len(face.vertices) >= 3
            for u, v in face.uvs:
                assert 0.0 <= u <= 1.0
                assert 0.0 <= v <= 1.0


def test_face_winding_points_outward_for_origin_centered_shapes() -> None:
    origin_centered_shape_keys = ("cube", "box", "tall_box", "wedge", "ramp", "cylinder", "roof")
    for shape_key in origin_centered_shape_keys:
        shape = SHAPE_PRESETS_BY_KEY[shape_key]
        for face in shape.face_groups:
            nx, ny, nz = _face_normal(face.vertices)
            length = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
            assert length > 0.0
            centroid = tuple(sum(vertex[index] for vertex in face.vertices) / len(face.vertices) for index in range(3))
            dot = (nx * centroid[0]) + (ny * centroid[1]) + (nz * centroid[2])
            assert dot > 0.0, (shape.key, face.label, dot)


def test_face_winding_is_consistent_with_triangulation() -> None:
    for shape in SHAPE_PRESETS_BY_KEY.values():
        for face in shape.face_groups:
            nx, ny, nz = _face_normal(face.vertices)
            length = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
            assert length > 0.0
            for triangle in [triangle for triangle in shape.triangles() if triangle.face_id == face.face_id]:
                tx, ty, tz = _face_normal(triangle.positions)
                dot = (nx * tx) + (ny * ty) + (nz * tz)
                assert dot > 0.0, (shape.key, face.label, dot)


def test_face_ids_are_stable_and_unique() -> None:
    for shape in SHAPE_PRESETS_BY_KEY.values():
        face_ids = [face.face_id for face in shape.face_groups]
        assert face_ids == list(range(len(face_ids)))


def test_recommended_texture_sizes_match_basic_box_proportions() -> None:
    cube_front = SHAPE_PRESETS_BY_KEY["cube"].face_by_id(0)
    box_front = SHAPE_PRESETS_BY_KEY["box"].face_by_id(0)
    tall_box_front = SHAPE_PRESETS_BY_KEY["tall_box"].face_by_id(0)
    assert cube_front is not None
    assert box_front is not None
    assert tall_box_front is not None
    assert recommended_texture_size(cube_front) == (64, 64)
    assert recommended_texture_size(box_front) == (88, 56)
    assert recommended_texture_size(tall_box_front) == (56, 96)
