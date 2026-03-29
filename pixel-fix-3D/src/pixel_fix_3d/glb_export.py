from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Mapping

import numpy as np
from PIL import Image
from pygltflib import (
    ARRAY_BUFFER,
    CLAMP_TO_EDGE,
    ELEMENT_ARRAY_BUFFER,
    FLOAT,
    GLTF2,
    NEAREST,
    SCALAR,
    TRIANGLES,
    UNSIGNED_SHORT,
    VEC2,
    VEC3,
    Accessor,
    Asset,
    Attributes,
    Buffer,
    BufferView,
    Image as GltfImage,
    Material,
    Mesh,
    Node,
    PbrMetallicRoughness,
    Primitive,
    Sampler,
    Scene,
    Texture,
    TextureInfo,
)

from .project_io import build_pfx3d_project
from .shapes import ShapePreset
from .textures import TextureEntry

GLB_UNLIT_EXTENSION = "KHR_materials_unlit"
GLB_MIME_TYPE = "image/png"


class GlbExportError(ValueError):
    pass


@dataclass(frozen=True)
class _FacePrimitiveBundle:
    face_id: int
    face_label: str
    texture_name: str
    image_bytes: bytes
    positions: np.ndarray
    normals: np.ndarray
    uvs: np.ndarray
    indices: np.ndarray


def export_glb(path: str | Path, shape: ShapePreset, textures_by_face: Mapping[int, TextureEntry]) -> None:
    bundles = _build_face_primitive_bundles(shape, textures_by_face)
    if not bundles:
        raise GlbExportError("Shape has no exportable geometry.")

    gltf = GLTF2(asset=Asset(version="2.0", generator="Pixel-Fix Studio 3D"))
    gltf.extensionsUsed = [GLB_UNLIT_EXTENSION]
    gltf.extensionsRequired = [GLB_UNLIT_EXTENSION]
    gltf.samplers.append(
        Sampler(
            magFilter=NEAREST,
            minFilter=NEAREST,
            wrapS=CLAMP_TO_EDGE,
            wrapT=CLAMP_TO_EDGE,
        )
    )

    blob = bytearray()
    mesh = Mesh(name=shape.label, primitives=[])
    for bundle in bundles:
        position_accessor = _append_float_accessor(
            gltf=gltf,
            blob=blob,
            values=bundle.positions,
            accessor_type=VEC3,
            target=ARRAY_BUFFER,
            include_bounds=True,
        )
        normal_accessor = _append_float_accessor(
            gltf=gltf,
            blob=blob,
            values=bundle.normals,
            accessor_type=VEC3,
            target=ARRAY_BUFFER,
        )
        uv_accessor = _append_float_accessor(
            gltf=gltf,
            blob=blob,
            values=bundle.uvs,
            accessor_type=VEC2,
            target=ARRAY_BUFFER,
        )
        index_accessor = _append_uint16_accessor(
            gltf=gltf,
            blob=blob,
            values=bundle.indices,
            target=ELEMENT_ARRAY_BUFFER,
        )
        image_view = _append_buffer_view(gltf=gltf, blob=blob, data=bundle.image_bytes)
        image_index = len(gltf.images)
        gltf.images.append(
            GltfImage(
                bufferView=image_view,
                mimeType=GLB_MIME_TYPE,
                name=bundle.texture_name,
            )
        )
        texture_index = len(gltf.textures)
        gltf.textures.append(Texture(sampler=0, source=image_index, name=bundle.texture_name))
        material_index = len(gltf.materials)
        gltf.materials.append(
            Material(
                name=bundle.face_label,
                alphaMode="BLEND",
                doubleSided=False,
                pbrMetallicRoughness=PbrMetallicRoughness(
                    baseColorTexture=TextureInfo(index=texture_index, texCoord=0),
                    baseColorFactor=[1.0, 1.0, 1.0, 1.0],
                    metallicFactor=0.0,
                    roughnessFactor=1.0,
                ),
                extensions={GLB_UNLIT_EXTENSION: {}},
            )
        )
        mesh.primitives.append(
            Primitive(
                attributes=Attributes(
                    POSITION=position_accessor,
                    NORMAL=normal_accessor,
                    TEXCOORD_0=uv_accessor,
                ),
                indices=index_accessor,
                material=material_index,
                mode=TRIANGLES,
            )
        )

    gltf.meshes = [mesh]
    gltf.nodes = [Node(mesh=0, name=shape.label)]
    gltf.scenes = [Scene(name=shape.label, nodes=[0])]
    gltf.scene = 0
    gltf.buffers = [Buffer(byteLength=len(blob))]
    gltf.set_binary_blob(bytes(blob))
    if not gltf.save_binary(str(path)):
        raise GlbExportError("Failed to save GLB file.")


def _build_face_primitive_bundles(
    shape: ShapePreset,
    textures_by_face: Mapping[int, TextureEntry],
) -> list[_FacePrimitiveBundle]:
    project = build_pfx3d_project(shape, textures_by_face)
    project_faces = {face.face_id: face for face in project.faces}
    min_y = min(vertex[1] for face in shape.face_groups for vertex in face.vertices)
    triangles_by_face: dict[int, list[tuple[tuple[float, float, float], tuple[float, float]]]] = {}
    normals_by_face: dict[int, tuple[float, float, float]] = {}

    for triangle in shape.triangles():
        points = [
            (position[0], position[1] - min_y, position[2])
            for position in triangle.positions
        ]
        triangles_by_face.setdefault(triangle.face_id, [])
        triangles_by_face[triangle.face_id].extend(zip(points, triangle.uvs))
        if triangle.face_id not in normals_by_face:
            normals_by_face[triangle.face_id] = _triangle_normal(points)

    bundles: list[_FacePrimitiveBundle] = []
    for face in shape.face_groups:
        triangle_points = triangles_by_face.get(face.face_id, [])
        if not triangle_points:
            continue
        position_rows = [position for position, _uv in triangle_points]
        uv_rows = [uv for _position, uv in triangle_points]
        count = len(position_rows)
        if count > 65535:
            raise GlbExportError(f"Face {face.label} exceeds GLB index limits.")
        normal = normals_by_face.get(face.face_id, (0.0, 1.0, 0.0))
        project_face = project_faces.get(face.face_id)
        if project_face is None:
            raise GlbExportError(f"Missing face texture data for {face.label}.")
        bundles.append(
            _FacePrimitiveBundle(
                face_id=face.face_id,
                face_label=face.label,
                texture_name=Path(project_face.texture_file).name,
                image_bytes=_png_bytes(project_face.image),
                positions=np.asarray(position_rows, dtype=np.float32),
                normals=np.asarray([normal] * count, dtype=np.float32),
                uvs=np.asarray(uv_rows, dtype=np.float32),
                indices=np.arange(count, dtype=np.uint16),
            )
        )
    return bundles


def _triangle_normal(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    if len(points) < 3:
        return (0.0, 1.0, 0.0)
    a = np.asarray(points[0], dtype=np.float64)
    b = np.asarray(points[1], dtype=np.float64)
    c = np.asarray(points[2], dtype=np.float64)
    normal = np.cross(b - a, c - a)
    length = float(np.linalg.norm(normal))
    if length <= 1e-9:
        return (0.0, 1.0, 0.0)
    unit = normal / length
    return (float(unit[0]), float(unit[1]), float(unit[2]))


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.convert("RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


def _append_float_accessor(
    *,
    gltf: GLTF2,
    blob: bytearray,
    values: np.ndarray,
    accessor_type: str,
    target: int,
    include_bounds: bool = False,
) -> int:
    raw = values.astype(np.float32).tobytes()
    view_index = _append_buffer_view(gltf=gltf, blob=blob, data=raw, target=target)
    accessor = Accessor(
        bufferView=view_index,
        byteOffset=0,
        componentType=FLOAT,
        count=int(values.shape[0]),
        type=accessor_type,
    )
    if include_bounds:
        accessor.min = [float(value) for value in values.min(axis=0)]
        accessor.max = [float(value) for value in values.max(axis=0)]
    gltf.accessors.append(accessor)
    return len(gltf.accessors) - 1


def _append_uint16_accessor(
    *,
    gltf: GLTF2,
    blob: bytearray,
    values: np.ndarray,
    target: int,
) -> int:
    raw = values.astype(np.uint16).tobytes()
    view_index = _append_buffer_view(gltf=gltf, blob=blob, data=raw, target=target)
    accessor = Accessor(
        bufferView=view_index,
        byteOffset=0,
        componentType=UNSIGNED_SHORT,
        count=int(values.shape[0]),
        type=SCALAR,
        min=[int(values.min()) if values.size else 0],
        max=[int(values.max()) if values.size else 0],
    )
    gltf.accessors.append(accessor)
    return len(gltf.accessors) - 1


def _append_buffer_view(
    *,
    gltf: GLTF2,
    blob: bytearray,
    data: bytes,
    target: int | None = None,
) -> int:
    _align_blob(blob, 4)
    offset = len(blob)
    blob.extend(data)
    view = BufferView(
        buffer=0,
        byteOffset=offset,
        byteLength=len(data),
        target=target,
    )
    gltf.bufferViews.append(view)
    return len(gltf.bufferViews) - 1


def _align_blob(blob: bytearray, alignment: int) -> None:
    padding = (-len(blob)) % alignment
    if padding:
        blob.extend(b"\x00" * padding)
