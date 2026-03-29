from __future__ import annotations

import math
from dataclasses import dataclass

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
FACE_TEXTURE_PIXELS_PER_UNIT = 40.0
FACE_TEXTURE_SIZE_STEP = 8
FACE_TEXTURE_MIN_SIZE = 16


@dataclass(frozen=True)
class FaceGroup:
    face_id: int
    label: str
    vertices: tuple[Vec3, ...]
    uvs: tuple[Vec2, ...]


@dataclass(frozen=True)
class Triangle:
    face_id: int
    face_label: str
    positions: tuple[Vec3, Vec3, Vec3]
    uvs: tuple[Vec2, Vec2, Vec2]


@dataclass(frozen=True)
class ShapePreset:
    key: str
    label: str
    face_groups: tuple[FaceGroup, ...]

    def triangles(self) -> tuple[Triangle, ...]:
        tris: list[Triangle] = []
        for face in self.face_groups:
            for index in range(1, len(face.vertices) - 1):
                tris.append(
                    Triangle(
                        face_id=face.face_id,
                        face_label=face.label,
                        positions=(face.vertices[0], face.vertices[index], face.vertices[index + 1]),
                        uvs=(face.uvs[0], face.uvs[index], face.uvs[index + 1]),
                    )
                )
        return tuple(tris)

    def face_by_id(self, face_id: int) -> FaceGroup | None:
        for face in self.face_groups:
            if face.face_id == face_id:
                return face
        return None


def recommended_texture_size(face: FaceGroup) -> tuple[int, int]:
    vertices = face.vertices
    if len(vertices) < 3:
        return (FACE_TEXTURE_MIN_SIZE, FACE_TEXTURE_MIN_SIZE)
    origin = vertices[0]
    edge_u = _normalize(_subtract(vertices[1], origin))
    if edge_u is None:
        for candidate in vertices[2:]:
            edge_u = _normalize(_subtract(candidate, origin))
            if edge_u is not None:
                break
    if edge_u is None:
        return (FACE_TEXTURE_MIN_SIZE, FACE_TEXTURE_MIN_SIZE)

    normal = _normalize(_cross(_subtract(vertices[1], origin), _subtract(vertices[2], origin)))
    if normal is None:
        return (FACE_TEXTURE_MIN_SIZE, FACE_TEXTURE_MIN_SIZE)
    edge_v = _normalize(_cross(normal, edge_u))
    if edge_v is None:
        return (FACE_TEXTURE_MIN_SIZE, FACE_TEXTURE_MIN_SIZE)

    u_coords = [_dot(vertex, edge_u) for vertex in vertices]
    v_coords = [_dot(vertex, edge_v) for vertex in vertices]
    width_units = max(u_coords) - min(u_coords)
    height_units = max(v_coords) - min(v_coords)
    return (_snap_texture_dimension(width_units), _snap_texture_dimension(height_units))


def _snap_texture_dimension(size_units: float) -> int:
    raw_pixels = size_units * FACE_TEXTURE_PIXELS_PER_UNIT
    snapped = int(math.floor((raw_pixels / FACE_TEXTURE_SIZE_STEP) + 0.5) * FACE_TEXTURE_SIZE_STEP)
    return max(FACE_TEXTURE_MIN_SIZE, snapped)


def _subtract(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        (a[1] * b[2]) - (a[2] * b[1]),
        (a[2] * b[0]) - (a[0] * b[2]),
        (a[0] * b[1]) - (a[1] * b[0]),
    )


def _normalize(vector: Vec3) -> Vec3 | None:
    length = math.sqrt((vector[0] * vector[0]) + (vector[1] * vector[1]) + (vector[2] * vector[2]))
    if length <= 1e-9:
        return None
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _face(face_id: int, label: str, vertices: list[Vec3], uvs: list[Vec2] | None = None) -> FaceGroup:
    if uvs is None:
        uvs = _default_uvs(len(vertices))
    return FaceGroup(face_id=face_id, label=label, vertices=tuple(vertices), uvs=tuple(uvs))


def _face_outward(
    face_id: int,
    label: str,
    vertices: list[Vec3],
    *,
    reference_point: Vec3 = (0.0, 0.0, 0.0),
    uvs: list[Vec2] | None = None,
) -> FaceGroup:
    oriented_vertices = vertices
    oriented_uvs = uvs
    normal = _cross(_subtract(vertices[1], vertices[0]), _subtract(vertices[2], vertices[0]))
    centroid = (
        sum(vertex[0] for vertex in vertices) / len(vertices),
        sum(vertex[1] for vertex in vertices) / len(vertices),
        sum(vertex[2] for vertex in vertices) / len(vertices),
    )
    outward = _subtract(centroid, reference_point)
    if _dot(normal, outward) < 0.0:
        oriented_vertices = list(reversed(vertices))
        if uvs is not None:
            oriented_uvs = list(reversed(uvs))
    return _face(face_id=face_id, label=label, vertices=oriented_vertices, uvs=oriented_uvs)


def _default_uvs(count: int) -> list[Vec2]:
    if count == 3:
        return [(0.0, 1.0), (1.0, 1.0), (0.5, 0.0)]
    if count == 4:
        return [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    return [
        (
            0.5 + math.cos((2.0 * math.pi * index) / count) * 0.5,
            0.5 + math.sin((2.0 * math.pi * index) / count) * 0.5,
        )
        for index in range(count)
    ]


def _box_faces(half_x: float, half_y: float, half_z: float) -> list[tuple[str, list[Vec3]]]:
    return [
        ("Front", [(-half_x, -half_y, half_z), (half_x, -half_y, half_z), (half_x, half_y, half_z), (-half_x, half_y, half_z)]),
        ("Back", [(half_x, -half_y, -half_z), (-half_x, -half_y, -half_z), (-half_x, half_y, -half_z), (half_x, half_y, -half_z)]),
        ("Right", [(half_x, -half_y, half_z), (half_x, -half_y, -half_z), (half_x, half_y, -half_z), (half_x, half_y, half_z)]),
        ("Left", [(-half_x, -half_y, -half_z), (-half_x, -half_y, half_z), (-half_x, half_y, half_z), (-half_x, half_y, -half_z)]),
        ("Top", [(-half_x, half_y, half_z), (half_x, half_y, half_z), (half_x, half_y, -half_z), (-half_x, half_y, -half_z)]),
        ("Bottom", [(-half_x, -half_y, -half_z), (half_x, -half_y, -half_z), (half_x, -half_y, half_z), (-half_x, -half_y, half_z)]),
    ]


def _wheel_face_specs(
    *,
    label_prefix: str,
    center_x: float,
    center_y: float,
    center_z: float,
    half_width: float,
    radius_y: float,
    radius_z: float,
    segments: int = 8,
) -> list[tuple[str, list[Vec3], Vec3, list[Vec2] | None]]:
    ring: list[tuple[float, float]] = []
    for index in range(segments):
        angle = (2.0 * math.pi * index) / segments
        ring.append(
            (
                center_y + (math.sin(angle) * radius_y),
                center_z + (math.cos(angle) * radius_z),
            )
        )

    outer_x = center_x + half_width
    inner_x = center_x - half_width
    outer_ring = [(outer_x, y, z) for y, z in ring]
    inner_ring = [(inner_x, y, z) for y, z in ring]

    face_specs: list[tuple[str, list[Vec3], Vec3, list[Vec2] | None]] = []
    for index in range(segments):
        next_index = (index + 1) % segments
        face_specs.append(
            (
                f"{label_prefix} Side {index + 1}",
                [
                    outer_ring[index],
                    outer_ring[next_index],
                    inner_ring[next_index],
                    inner_ring[index],
                ],
                (center_x, center_y, center_z),
                None,
            )
        )

    cap_uvs = [
        (
            max(0.0, min(1.0, 0.5 + ((z - center_z) / (radius_z * 2.0)))),
            max(0.0, min(1.0, 0.5 + ((y - center_y) / (radius_y * 2.0)))),
        )
        for y, z in ring
    ]
    face_specs.append(
        (
            f"{label_prefix} Outer",
            outer_ring,
            (center_x, center_y, center_z),
            cap_uvs,
        )
    )
    face_specs.append(
        (
            f"{label_prefix} Inner",
            list(reversed(inner_ring)),
            (center_x, center_y, center_z),
            list(reversed(cap_uvs)),
        )
    )
    return face_specs


def _make_box(key: str, label: str, half_x: float, half_y: float, half_z: float) -> ShapePreset:
    face_groups = tuple(
        _face(face_id=index, label=face_label, vertices=vertices)
        for index, (face_label, vertices) in enumerate(_box_faces(half_x, half_y, half_z))
    )
    return ShapePreset(key=key, label=label, face_groups=face_groups)


def _make_wedge() -> ShapePreset:
    half_z = 0.7
    half_x = 0.9
    low_y = -0.7
    peak_y = 0.8
    front_a = (-half_x, low_y, half_z)
    front_b = (half_x, low_y, half_z)
    front_c = (0.0, peak_y, half_z)
    back_a = (-half_x, low_y, -half_z)
    back_b = (half_x, low_y, -half_z)
    back_c = (0.0, peak_y, -half_z)
    faces = (
        _face(0, "Bottom", [back_a, back_b, front_b, front_a]),
        _face(1, "Left Slope", [back_a, front_a, front_c, back_c]),
        _face(2, "Right Slope", [front_b, back_b, back_c, front_c]),
        _face(3, "Front Cap", [front_a, front_b, front_c]),
        _face(4, "Back Cap", [back_b, back_a, back_c]),
    )
    return ShapePreset(key="wedge", label="Wedge", face_groups=faces)


def _make_ramp() -> ShapePreset:
    half_x = 0.9
    half_z = 0.9
    bottom_y = -0.7
    front_y = -0.1
    back_y = 0.8
    faces = (
        _face(0, "Bottom", [(-half_x, bottom_y, -half_z), (half_x, bottom_y, -half_z), (half_x, bottom_y, half_z), (-half_x, bottom_y, half_z)]),
        _face(1, "Front", [(-half_x, bottom_y, half_z), (half_x, bottom_y, half_z), (half_x, front_y, half_z), (-half_x, front_y, half_z)]),
        _face(2, "Back", [(half_x, bottom_y, -half_z), (-half_x, bottom_y, -half_z), (-half_x, back_y, -half_z), (half_x, back_y, -half_z)]),
        _face(3, "Left", [(-half_x, bottom_y, -half_z), (-half_x, bottom_y, half_z), (-half_x, front_y, half_z), (-half_x, back_y, -half_z)]),
        _face(4, "Right", [(half_x, bottom_y, half_z), (half_x, bottom_y, -half_z), (half_x, back_y, -half_z), (half_x, front_y, half_z)]),
        _face(5, "Slope", [(-half_x, front_y, half_z), (half_x, front_y, half_z), (half_x, back_y, -half_z), (-half_x, back_y, -half_z)]),
    )
    return ShapePreset(key="ramp", label="Ramp", face_groups=faces)


def _make_cylinder() -> ShapePreset:
    radius = 0.8
    half_y = 0.8
    points_top: list[Vec3] = []
    points_bottom: list[Vec3] = []
    for index in range(8):
        angle = (2.0 * math.pi) - (2.0 * math.pi * index / 8.0)
        x = math.cos(angle) * radius
        z = math.sin(angle) * radius
        points_top.append((x, half_y, z))
        points_bottom.append((x, -half_y, z))
    faces: list[FaceGroup] = []
    for index in range(8):
        next_index = (index + 1) % 8
        faces.append(
            _face(
                index,
                f"Side {index + 1}",
                [
                    points_bottom[index],
                    points_bottom[next_index],
                    points_top[next_index],
                    points_top[index],
                ],
            )
        )
    top_uvs = [(0.5 + (x / (radius * 2.0)), 0.5 + (z / (radius * 2.0))) for x, _, z in points_top]
    bottom_uvs = [(0.5 + (x / (radius * 2.0)), 0.5 + (z / (radius * 2.0))) for x, _, z in points_bottom]
    faces.append(_face(8, "Top", points_top, top_uvs))
    faces.append(_face(9, "Bottom", list(reversed(points_bottom)), list(reversed(bottom_uvs))))
    return ShapePreset(key="cylinder", label="8-Sided Cylinder", face_groups=tuple(faces))


def _make_roof() -> ShapePreset:
    half_x = 0.9
    half_z = 0.8
    bottom_y = -0.7
    wall_y = 0.0
    roof_y = 0.8
    front_left_bottom = (-half_x, bottom_y, half_z)
    front_right_bottom = (half_x, bottom_y, half_z)
    front_right_wall = (half_x, wall_y, half_z)
    front_peak = (0.0, roof_y, half_z)
    front_left_wall = (-half_x, wall_y, half_z)
    back_left_bottom = (-half_x, bottom_y, -half_z)
    back_right_bottom = (half_x, bottom_y, -half_z)
    back_right_wall = (half_x, wall_y, -half_z)
    back_peak = (0.0, roof_y, -half_z)
    back_left_wall = (-half_x, wall_y, -half_z)
    faces = (
        _face(0, "Bottom", [back_left_bottom, back_right_bottom, front_right_bottom, front_left_bottom]),
        _face(1, "Left Wall", [back_left_bottom, front_left_bottom, front_left_wall, back_left_wall]),
        _face(2, "Right Wall", [front_right_bottom, back_right_bottom, back_right_wall, front_right_wall]),
        _face(3, "Left Roof", [back_left_wall, front_left_wall, front_peak, back_peak]),
        _face(4, "Right Roof", [front_right_wall, back_right_wall, back_peak, front_peak]),
        _face(5, "Front Gable", [front_left_bottom, front_right_bottom, front_right_wall, front_peak, front_left_wall]),
        _face(6, "Back Gable", [back_right_bottom, back_left_bottom, back_left_wall, back_peak, back_right_wall]),
    )
    return ShapePreset(key="roof", label="Roof", face_groups=faces)


def _make_car() -> ShapePreset:
    half_x = 0.70
    front_z = 1.1
    hood_z = 0.55
    roof_front_z = 0.15
    roof_back_z = -0.45
    rear_deck_z = -0.85
    back_z = -1.1
    bottom_y = -0.72
    front_top_y = -0.15
    hood_y = 0.0
    roof_y = 0.45
    rear_deck_y = 0.0
    back_top_y = -0.1

    front_left_bottom = (-half_x, bottom_y, front_z)
    front_right_bottom = (half_x, bottom_y, front_z)
    front_left_top = (-half_x, front_top_y, front_z)
    front_right_top = (half_x, front_top_y, front_z)
    hood_left = (-half_x, hood_y, hood_z)
    hood_right = (half_x, hood_y, hood_z)
    roof_front_left = (-half_x, roof_y, roof_front_z)
    roof_front_right = (half_x, roof_y, roof_front_z)
    roof_back_left = (-half_x, roof_y, roof_back_z)
    roof_back_right = (half_x, roof_y, roof_back_z)
    rear_deck_left = (-half_x, rear_deck_y, rear_deck_z)
    rear_deck_right = (half_x, rear_deck_y, rear_deck_z)
    back_left_top = (-half_x, back_top_y, back_z)
    back_right_top = (half_x, back_top_y, back_z)
    back_left_bottom = (-half_x, bottom_y, back_z)
    back_right_bottom = (half_x, bottom_y, back_z)

    body_face_specs: list[tuple[str, list[Vec3], Vec3, list[Vec2] | None]] = [
        ("Bottom", [back_left_bottom, back_right_bottom, front_right_bottom, front_left_bottom], (0.0, 0.0, 0.0), None),
        ("Front", [front_left_bottom, front_right_bottom, front_right_top, front_left_top], (0.0, 0.0, 0.0), None),
        ("Hood", [front_left_top, front_right_top, hood_right, hood_left], (0.0, 0.0, 0.0), None),
        ("Windshield", [hood_left, hood_right, roof_front_right, roof_front_left], (0.0, 0.0, 0.0), None),
        ("Roof", [roof_front_left, roof_front_right, roof_back_right, roof_back_left], (0.0, 0.0, 0.0), None),
        ("Rear Window", [roof_back_left, roof_back_right, rear_deck_right, rear_deck_left], (0.0, 0.0, 0.0), None),
        ("Trunk", [rear_deck_left, rear_deck_right, back_right_top, back_left_top], (0.0, 0.0, 0.0), None),
        ("Back", [back_right_bottom, back_left_bottom, back_left_top, back_right_top], (0.0, 0.0, 0.0), None),
        (
            "Right Side",
            [front_right_bottom, back_right_bottom, back_right_top, rear_deck_right, roof_back_right, roof_front_right, hood_right, front_right_top],
            (0.0, 0.0, 0.0),
            None,
        ),
        (
            "Left Side",
            [back_left_bottom, front_left_bottom, front_left_top, hood_left, roof_front_left, roof_back_left, rear_deck_left, back_left_top],
            (0.0, 0.0, 0.0),
            None,
        ),
    ]

    wheel_face_specs: list[tuple[str, list[Vec3], Vec3, list[Vec2] | None]] = []
    wheel_half_width = 0.09
    wheel_radius_y = 0.312
    wheel_radius_z = 0.286
    wheel_center_y = -0.78
    for label_prefix, center_x, center_z in (
        ("Front Right Wheel", 0.72, 0.60),
        ("Front Left Wheel", -0.72, 0.60),
        ("Rear Right Wheel", 0.72, -0.58),
        ("Rear Left Wheel", -0.72, -0.58),
    ):
        wheel_face_specs.extend(
            _wheel_face_specs(
                label_prefix=label_prefix,
                center_x=center_x,
                center_y=wheel_center_y,
                center_z=center_z,
                half_width=wheel_half_width,
                radius_y=wheel_radius_y,
                radius_z=wheel_radius_z,
            )
        )

    face_groups = tuple(
        _face_outward(
            face_id=index,
            label=face_label,
            vertices=vertices,
            reference_point=reference_point,
            uvs=uvs,
        )
        for index, (face_label, vertices, reference_point, uvs) in enumerate(body_face_specs + wheel_face_specs)
    )
    return ShapePreset(key="car", label="Car", face_groups=face_groups)


SHAPE_PRESETS: tuple[ShapePreset, ...] = (
    _make_box("cube", "Cube", 0.8, 0.8, 0.8),
    _make_box("box", "Box", 1.1, 0.65, 0.75),
    _make_box("tall_box", "Tall Box", 0.7, 1.2, 0.7),
    _make_wedge(),
    _make_ramp(),
    _make_cylinder(),
    _make_roof(),
    _make_car(),
)

SHAPE_PRESETS_BY_KEY = {shape.key: shape for shape in SHAPE_PRESETS}
