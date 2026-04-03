from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image

from .processing import ProcessResult


@dataclass(frozen=True)
class RasterLayer:
    id: str
    name: str
    downsample_result: ProcessResult | None
    palette_result: ProcessResult | None = None
    visible: bool = True
    locked: bool = False

    @property
    def current_result(self) -> ProcessResult | None:
        return self.palette_result or self.downsample_result


@dataclass(frozen=True)
class LayerDocument:
    width: int
    height: int
    layers: tuple[RasterLayer, ...]
    active_layer_id: str
    project_path: Path | None = None
    last_export_path: Path | None = None

    @property
    def active_index(self) -> int:
        for index, layer in enumerate(self.layers):
            if layer.id == self.active_layer_id:
                return index
        return 0

    @property
    def active_layer(self) -> RasterLayer | None:
        if not self.layers:
            return None
        return self.layers[self.active_index]


@dataclass(frozen=True)
class DocumentHistorySnapshot:
    document: LayerDocument | None
    downsample_result: ProcessResult | None
    palette_result: ProcessResult | None
    source_path: Path | None
    image_state: str
    last_successful_process_snapshot: dict[str, object] | None
    active_palette: list[int] | None
    active_palette_source: str
    active_palette_path: str | None
    advanced_palette_preview: object | None
    transparent_colors: tuple[int, ...]
    settings: object
    original_display_image: Image.Image | None = None
    original_grid: list[list[tuple[int, int, int]]] | None = None
    palette_sort_reset_labels: tuple[int, ...] = ()
    palette_sort_reset_source: str | None = None
    palette_sort_reset_path: str | None = None


def clone_layer_document(document: LayerDocument | None) -> LayerDocument | None:
    if document is None:
        return None
    return replace(
        document,
        layers=tuple(
            replace(
                layer,
                downsample_result=layer.downsample_result,
                palette_result=layer.palette_result,
            )
            for layer in document.layers
        ),
        project_path=Path(document.project_path) if document.project_path is not None else None,
        last_export_path=Path(document.last_export_path) if document.last_export_path is not None else None,
    )


def make_layer_document(
    *,
    width: int,
    height: int,
    layers: list[RasterLayer] | tuple[RasterLayer, ...],
    active_layer_id: str | None = None,
    project_path: Path | None = None,
    last_export_path: Path | None = None,
) -> LayerDocument:
    if not layers:
        raise ValueError("Layer documents require at least one layer.")
    normalized_layers = tuple(layers)
    resolved_active_layer_id = active_layer_id or normalized_layers[0].id
    if all(layer.id != resolved_active_layer_id for layer in normalized_layers):
        resolved_active_layer_id = normalized_layers[0].id
    return LayerDocument(
        width=width,
        height=height,
        layers=normalized_layers,
        active_layer_id=resolved_active_layer_id,
        project_path=project_path,
        last_export_path=last_export_path,
    )


def replace_active_layer(document: LayerDocument, layer: RasterLayer) -> LayerDocument:
    updated_layers = list(document.layers)
    updated_layers[document.active_index] = layer
    return replace(document, layers=tuple(updated_layers), width=_document_width(updated_layers, document.width), height=_document_height(updated_layers, document.height))


def set_active_layer(document: LayerDocument, layer_id: str) -> LayerDocument:
    if all(layer.id != layer_id for layer in document.layers):
        return document
    return replace(document, active_layer_id=layer_id)


def add_layer_above_active(document: LayerDocument, layer: RasterLayer) -> LayerDocument:
    index = document.active_index
    updated_layers = list(document.layers)
    updated_layers.insert(index, layer)
    return replace(
        document,
        layers=tuple(updated_layers),
        active_layer_id=layer.id,
        width=_document_width(updated_layers, document.width),
        height=_document_height(updated_layers, document.height),
    )


def delete_active_layer(document: LayerDocument) -> LayerDocument:
    if len(document.layers) <= 1:
        raise ValueError("Cannot delete the last layer.")
    index = document.active_index
    updated_layers = list(document.layers)
    del updated_layers[index]
    next_index = min(index, len(updated_layers) - 1)
    next_active = updated_layers[next_index].id
    return replace(
        document,
        layers=tuple(updated_layers),
        active_layer_id=next_active,
        width=_document_width(updated_layers, document.width),
        height=_document_height(updated_layers, document.height),
    )


def rename_active_layer(document: LayerDocument, name: str) -> LayerDocument:
    normalized = name.strip()
    if not normalized:
        raise ValueError("Layer name cannot be empty.")
    active = document.active_layer
    if active is None:
        return document
    return replace_active_layer(document, replace(active, name=normalized))


def move_active_layer_up(document: LayerDocument) -> LayerDocument:
    index = document.active_index
    if index <= 0:
        return document
    updated_layers = list(document.layers)
    updated_layers[index - 1], updated_layers[index] = updated_layers[index], updated_layers[index - 1]
    return replace(document, layers=tuple(updated_layers))


def move_active_layer_down(document: LayerDocument) -> LayerDocument:
    index = document.active_index
    if index >= len(document.layers) - 1:
        return document
    updated_layers = list(document.layers)
    updated_layers[index], updated_layers[index + 1] = updated_layers[index + 1], updated_layers[index]
    return replace(document, layers=tuple(updated_layers))


def set_active_layer_visibility(document: LayerDocument, visible: bool) -> LayerDocument:
    active = document.active_layer
    if active is None:
        return document
    return replace_active_layer(document, replace(active, visible=bool(visible)))


def set_active_layer_locked(document: LayerDocument, locked: bool) -> LayerDocument:
    active = document.active_layer
    if active is None:
        return document
    return replace_active_layer(document, replace(active, locked=bool(locked)))


def next_layer_name(document: LayerDocument, prefix: str = "Layer") -> str:
    highest = 0
    for layer in document.layers:
        if not layer.name.startswith(f"{prefix} "):
            continue
        suffix = layer.name.removeprefix(f"{prefix} ").strip()
        try:
            highest = max(highest, int(suffix))
        except ValueError:
            continue
    return f"{prefix} {highest + 1}"


def composite_layer_images(
    document: LayerDocument | None,
    rendered_layers: dict[str, Image.Image | None],
) -> Image.Image | None:
    if document is None:
        return None
    base = Image.new("RGBA", (max(1, document.width), max(1, document.height)), (0, 0, 0, 0))
    for layer in reversed(document.layers):
        if not layer.visible:
            continue
        image = rendered_layers.get(layer.id)
        if image is None:
            continue
        base.alpha_composite(image.convert("RGBA"))
    return base


def _document_width(layers: list[RasterLayer], fallback: int) -> int:
    for layer in layers:
        current = layer.current_result
        if current is not None:
            return current.width
    return fallback


def _document_height(layers: list[RasterLayer], fallback: int) -> int:
    for layer in layers:
        current = layer.current_result
        if current is not None:
            return current.height
    return fallback
