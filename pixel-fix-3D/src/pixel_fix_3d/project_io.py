from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Mapping

from PIL import Image

from .shapes import SHAPE_PRESETS_BY_KEY, FaceGroup, ShapePreset, recommended_texture_size
from .textures import TextureEntry

PFX3D_FORMAT = "pfx3d"
PFX3D_VERSION = 1
PFX3D_MANIFEST_PATH = "project.json"
TEMPLATE_RGBA = (128, 128, 128, 255)


class Pfx3dError(ValueError):
    pass


@dataclass(frozen=True)
class Pfx3dFaceTexture:
    face_id: int
    face_label: str
    texture_file: str
    image: Image.Image


@dataclass(frozen=True)
class Pfx3dProject:
    shape_key: str
    faces: tuple[Pfx3dFaceTexture, ...]


def save_pfx3d(path: str | Path, shape: ShapePreset, textures_by_face: Mapping[int, TextureEntry]) -> None:
    project = build_pfx3d_project(shape, textures_by_face)
    manifest = {
        "format": PFX3D_FORMAT,
        "version": PFX3D_VERSION,
        "shape_key": project.shape_key,
        "faces": [
            {
                "face_id": face.face_id,
                "face_label": face.face_label,
                "texture_file": face.texture_file,
            }
            for face in project.faces
        ],
    }

    with zipfile.ZipFile(Path(path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(PFX3D_MANIFEST_PATH, json.dumps(manifest, indent=2, sort_keys=True))
        for face in project.faces:
            buffer = BytesIO()
            face.image.save(buffer, format="PNG")
            archive.writestr(face.texture_file, buffer.getvalue())


def load_pfx3d(path: str | Path) -> Pfx3dProject:
    project_path = Path(path)
    try:
        with zipfile.ZipFile(project_path, "r") as archive:
            try:
                manifest = json.loads(archive.read(PFX3D_MANIFEST_PATH).decode("utf-8"))
            except KeyError as exc:
                raise Pfx3dError("Project manifest is missing.") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise Pfx3dError("Project manifest is invalid.") from exc

            shape = _validate_manifest(manifest)
            faces_raw = manifest["faces"]
            loaded_faces: list[Pfx3dFaceTexture] = []
            for face_data in sorted(faces_raw, key=lambda item: int(item["face_id"])):
                face_id = int(face_data["face_id"])
                texture_file = str(face_data["texture_file"])
                expected_face = shape.face_by_id(face_id)
                if expected_face is None:
                    raise Pfx3dError(f"Unknown face id {face_id} for shape {shape.label}.")
                if str(face_data["face_label"]) != expected_face.label:
                    raise Pfx3dError(f"Face label mismatch for face {face_id}.")
                try:
                    texture_bytes = archive.read(texture_file)
                except KeyError as exc:
                    raise Pfx3dError(f"Missing embedded texture: {texture_file}.") from exc
                try:
                    with Image.open(BytesIO(texture_bytes)) as image:
                        loaded_faces.append(
                            Pfx3dFaceTexture(
                                face_id=face_id,
                                face_label=expected_face.label,
                                texture_file=texture_file,
                                image=image.convert("RGBA").copy(),
                            )
                        )
                except (OSError, ValueError) as exc:
                    raise Pfx3dError(f"Embedded texture is invalid: {texture_file}.") from exc
    except zipfile.BadZipFile as exc:
        raise Pfx3dError("The selected file is not a valid .pfx3d archive.") from exc
    except OSError as exc:
        raise Pfx3dError(str(exc)) from exc

    return Pfx3dProject(shape_key=shape.key, faces=tuple(loaded_faces))


def extract_face_textures(path: str | Path, shape: ShapePreset, textures_by_face: Mapping[int, TextureEntry]) -> Path:
    destination_root = Path(path)
    export_dir = _unique_export_dir(destination_root, f"{shape.key}_textures")
    export_dir.mkdir(parents=True, exist_ok=False)
    for face in build_pfx3d_project(shape, textures_by_face).faces:
        export_path = export_dir / Path(face.texture_file).name
        face.image.save(export_path, format="PNG")
    return export_dir


def build_pfx3d_project(shape: ShapePreset, textures_by_face: Mapping[int, TextureEntry]) -> Pfx3dProject:
    faces: list[Pfx3dFaceTexture] = []
    for face in shape.face_groups:
        entry = textures_by_face.get(face.face_id)
        image = entry.image if entry is not None else build_template_texture(face)
        faces.append(
            Pfx3dFaceTexture(
                face_id=face.face_id,
                face_label=face.label,
                texture_file=_face_texture_archive_path(face.face_id, face.label),
                image=image.convert("RGBA").copy(),
            )
        )
    return Pfx3dProject(shape_key=shape.key, faces=tuple(faces))


def build_template_texture(face: FaceGroup) -> Image.Image:
    return Image.new("RGBA", recommended_texture_size(face), TEMPLATE_RGBA)


def _validate_manifest(manifest: object) -> ShapePreset:
    if not isinstance(manifest, dict):
        raise Pfx3dError("Project manifest is invalid.")
    if manifest.get("format") != PFX3D_FORMAT:
        raise Pfx3dError("Unsupported project format.")
    if manifest.get("version") != PFX3D_VERSION:
        raise Pfx3dError("Unsupported project version.")
    shape_key = manifest.get("shape_key")
    if not isinstance(shape_key, str) or shape_key not in SHAPE_PRESETS_BY_KEY:
        raise Pfx3dError("Project references an unknown shape.")
    faces = manifest.get("faces")
    if not isinstance(faces, list):
        raise Pfx3dError("Project face data is missing.")
    shape = SHAPE_PRESETS_BY_KEY[shape_key]
    expected_ids = {face.face_id for face in shape.face_groups}
    face_ids: list[int] = []
    for item in faces:
        if not isinstance(item, dict):
            raise Pfx3dError("Project face data is invalid.")
        if not {"face_id", "face_label", "texture_file"} <= set(item):
            raise Pfx3dError("Project face data is incomplete.")
        try:
            face_ids.append(int(item["face_id"]))
        except (TypeError, ValueError) as exc:
            raise Pfx3dError("Project face id is invalid.") from exc
    if set(face_ids) != expected_ids or len(face_ids) != len(expected_ids):
        raise Pfx3dError("Project face ids do not match the current shape definition.")
    return shape


def _face_texture_archive_path(face_id: int, face_label: str) -> str:
    slug = _slugify(face_label)
    return f"textures/{face_id:02d}-{slug}.png"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "face"


def _unique_export_dir(parent: Path, base_name: str) -> Path:
    candidate = parent / base_name
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = parent / f"{base_name}_{index}"
        if not candidate.exists():
            return candidate
        index += 1
