from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from .layers import LayerDocument, RasterLayer, make_layer_document
from .processing import image_to_rgb_grid, process_result_from_original, process_result_to_rgba_image

PROJECT_VERSION = 1
MANIFEST_NAME = "document.json"
LAYER_DIRECTORY = "layers"


def save_layer_project(path: Path, document: LayerDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": PROJECT_VERSION,
        "canvas": {
            "width": document.width,
            "height": document.height,
        },
        "active_layer_id": document.active_layer_id,
        "layers": [],
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, layer in enumerate(document.layers):
            current = layer.current_result
            if current is None:
                continue
            layer_filename = f"{LAYER_DIRECTORY}/layer-{index + 1:03d}.png"
            image = process_result_to_rgba_image(current)
            with archive.open(layer_filename, "w") as handle:
                image.save(handle, format="PNG")
            manifest["layers"].append(
                {
                    "id": layer.id,
                    "name": layer.name,
                    "visible": layer.visible,
                    "locked": layer.locked,
                    "image": layer_filename,
                    "stage": current.stats.stage,
                    "has_palette_result": layer.palette_result is not None,
                }
            )
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True))


def load_layer_project(path: Path) -> LayerDocument:
    with zipfile.ZipFile(path, "r") as archive:
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        version = int(manifest.get("version", 0))
        if version != PROJECT_VERSION:
            raise ValueError(f"Unsupported project version: {version}")
        canvas = manifest.get("canvas") or {}
        width = int(canvas.get("width", 0))
        height = int(canvas.get("height", 0))
        layers: list[RasterLayer] = []
        for layer_entry in manifest.get("layers", []):
            image_name = str(layer_entry.get("image", "")).strip()
            if not image_name:
                continue
            image_bytes = archive.read(image_name)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            result = process_result_from_original(image, image_to_rgb_grid(image))
            if bool(layer_entry.get("has_palette_result", False)):
                downsample_result = result
                palette_result = result
            else:
                downsample_result = result
                palette_result = None
            layers.append(
                RasterLayer(
                    id=str(layer_entry.get("id") or f"layer-{len(layers) + 1}"),
                    name=str(layer_entry.get("name") or f"Layer {len(layers) + 1}"),
                    downsample_result=downsample_result,
                    palette_result=palette_result,
                    visible=bool(layer_entry.get("visible", True)),
                    locked=bool(layer_entry.get("locked", False)),
                )
            )
        if not layers:
            raise ValueError("Project file does not contain any layers.")
        active_layer_id = str(manifest.get("active_layer_id") or layers[0].id)
        resolved_width = width or layers[0].current_result.width
        resolved_height = height or layers[0].current_result.height
        return make_layer_document(
            width=resolved_width,
            height=resolved_height,
            layers=layers,
            active_layer_id=active_layer_id,
            project_path=path,
            last_export_path=None,
        )
