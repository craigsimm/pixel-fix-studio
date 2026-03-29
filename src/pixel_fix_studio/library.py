from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from .models import LibraryFolderNode, PaletteItem, TextureItem

TEXTURE_SUFFIXES = {".png", ".bmp", ".gif", ".webp", ".jpg", ".jpeg"}


def list_library_folders(root: Path) -> list[LibraryFolderNode]:
    resolved_root = root.resolve()
    nodes = [LibraryFolderNode(path=resolved_root, key=".", label=resolved_root.name, parent_key=None)]
    directories = sorted(
        (path for path in resolved_root.rglob("*") if path.is_dir()),
        key=lambda value: (len(value.relative_to(resolved_root).parts), tuple(part.lower() for part in value.relative_to(resolved_root).parts)),
    )
    for directory in directories:
        relative = directory.relative_to(resolved_root)
        parent_key = "." if relative.parent == Path(".") else relative.parent.as_posix()
        nodes.append(
            LibraryFolderNode(
                path=directory.resolve(),
                key=relative.as_posix(),
                label=directory.name,
                parent_key=parent_key,
            )
        )
    return nodes


def list_palette_items(folder: Path) -> list[PaletteItem]:
    items: list[PaletteItem] = []
    for path in sorted((candidate for candidate in folder.iterdir() if candidate.is_file() and candidate.suffix.lower() == ".gpl"), key=lambda value: value.name.lower()):
        error: str | None = None
        colors: tuple[int, ...] = ()
        try:
            colors = tuple(_load_gpl_palette(path))
        except (OSError, ValueError) as exc:
            error = str(exc)
        items.append(
            PaletteItem(
                path=path.resolve(),
                name=path.name,
                folder=folder.resolve(),
                colors=colors,
                error=error,
            )
        )
    return items


def list_texture_items(folder: Path) -> list[TextureItem]:
    items: list[TextureItem] = []
    for path in sorted(
        (candidate for candidate in folder.iterdir() if candidate.is_file() and candidate.suffix.lower() in TEXTURE_SUFFIXES),
        key=lambda value: value.name.lower(),
    ):
        size: tuple[int, int] | None = None
        error: str | None = None
        try:
            with Image.open(path) as image:
                size = image.size
        except (OSError, ValueError) as exc:
            error = str(exc)
        items.append(
            TextureItem(
                path=path.resolve(),
                name=path.name,
                folder=folder.resolve(),
                size=size,
                error=error,
            )
        )
    return items


def import_palette_file(root: Path, target_folder: Path, source_path: Path) -> Path:
    return _import_library_file(root, target_folder, source_path, allowed_suffixes={".gpl"})


def import_texture_file(root: Path, target_folder: Path, source_path: Path) -> Path:
    return _import_library_file(root, target_folder, source_path, allowed_suffixes=TEXTURE_SUFFIXES)


def create_library_folder(root: Path, parent_folder: Path, name: str) -> Path:
    resolved_root = root.resolve()
    resolved_parent = _resolve_within_root(resolved_root, parent_folder)
    folder_name = name.strip()
    if not folder_name:
        raise ValueError("Folder name cannot be empty.")
    if Path(folder_name).name != folder_name or folder_name in {".", ".."}:
        raise ValueError("Folder name must be a single folder name.")
    destination = resolved_parent / folder_name
    destination.mkdir()
    return destination.resolve()


def move_library_item(root: Path, item_path: Path, target_folder: Path) -> Path:
    resolved_root = root.resolve()
    resolved_item = _resolve_within_root(resolved_root, item_path)
    resolved_target = _resolve_within_root(resolved_root, target_folder)
    if not resolved_target.is_dir():
        raise ValueError("Target folder does not exist.")
    destination = resolved_target / resolved_item.name
    if destination == resolved_item:
        raise ValueError("Item is already in the selected folder.")
    if destination.exists():
        raise FileExistsError(f"{destination.name} already exists in the selected folder.")
    shutil.move(str(resolved_item), str(destination))
    return destination.resolve()


def delete_library_item(root: Path, item_path: Path) -> None:
    resolved_item = _resolve_within_root(root.resolve(), item_path)
    if not resolved_item.exists() or not resolved_item.is_file():
        raise FileNotFoundError(resolved_item)
    resolved_item.unlink()


def _import_library_file(root: Path, target_folder: Path, source_path: Path, *, allowed_suffixes: set[str]) -> Path:
    resolved_root = root.resolve()
    resolved_target = _resolve_within_root(resolved_root, target_folder)
    if not resolved_target.is_dir():
        raise ValueError("Target folder does not exist.")
    resolved_source = source_path.resolve()
    if not resolved_source.exists() or not resolved_source.is_file():
        raise FileNotFoundError(resolved_source)
    suffix = resolved_source.suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(f"Unsupported file type: {resolved_source.suffix}")
    destination = resolved_target / resolved_source.name
    if destination.exists():
        raise FileExistsError(f"{destination.name} already exists in the selected folder.")
    shutil.copy2(resolved_source, destination)
    return destination.resolve()


def _resolve_within_root(root: Path, path_value: Path) -> Path:
    resolved = path_value.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{resolved} is outside {root}") from exc
    return resolved


def _load_gpl_palette(path: Path) -> list[int]:
    palette: list[int] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "GIMP Palette":
        raise ValueError("Invalid GPL palette header")

    for line in lines[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("Name:") or stripped.startswith("Columns:"):
            continue
        parts = stripped.split()
        if len(parts) < 3:
            raise ValueError(f"Invalid GPL palette line: {line!r}")
        try:
            red, green, blue = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError as exc:
            raise ValueError(f"Invalid GPL palette line: {line!r}") from exc
        for channel in (red, green, blue):
            if channel < 0 or channel > 255:
                raise ValueError(f"Invalid GPL colour channel: {line!r}")
        palette.append((red << 16) | (green << 8) | blue)

    if not palette:
        raise ValueError("Palette file is empty")
    return palette
