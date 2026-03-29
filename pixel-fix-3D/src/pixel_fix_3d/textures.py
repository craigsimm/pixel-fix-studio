from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image


@dataclass(frozen=True)
class TextureEntry:
    texture_id: str
    name: str
    path: Path | None
    size: tuple[int, int]
    image: Image.Image


def create_texture_entry(
    *,
    texture_id: str,
    name: str,
    image: Image.Image,
    path: str | Path | None = None,
) -> TextureEntry:
    rgba = image.convert("RGBA").copy()
    return TextureEntry(
        texture_id=texture_id,
        name=name,
        path=Path(path).resolve() if path is not None else None,
        size=rgba.size,
        image=rgba,
    )


def load_texture_file(path: str | Path) -> TextureEntry:
    texture_path = Path(path)
    with Image.open(texture_path) as image:
        return create_texture_entry(
            texture_id=str(texture_path.resolve()).lower(),
            name=texture_path.name,
            image=image,
            path=texture_path,
        )


def load_texture_resource(path: str | Path, *, texture_id: str, name: str | None = None) -> TextureEntry:
    texture_path = Path(path)
    with Image.open(texture_path) as image:
        return create_texture_entry(
            texture_id=texture_id,
            name=name or texture_path.name,
            image=image,
            path=texture_path,
        )


def load_texture_bytes(data: bytes, *, texture_id: str, name: str, path: str | Path | None = None) -> TextureEntry:
    with Image.open(BytesIO(data)) as image:
        return create_texture_entry(
            texture_id=texture_id,
            name=name,
            image=image,
            path=path,
        )


def load_texture_library(paths: Iterable[str | Path]) -> tuple[list[TextureEntry], list[str]]:
    textures: list[TextureEntry] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    for candidate in paths:
        try:
            entry = load_texture_file(candidate)
        except (OSError, ValueError) as exc:
            errors.append(f"{Path(candidate).name}: {exc}")
            continue
        if entry.texture_id in seen_ids:
            continue
        seen_ids.add(entry.texture_id)
        textures.append(entry)
    return textures, errors


def build_thumbnail(image: Image.Image, size: int = 48) -> Image.Image:
    source = image.convert("RGBA")
    return source.resize((size, size), Image.Resampling.NEAREST)
