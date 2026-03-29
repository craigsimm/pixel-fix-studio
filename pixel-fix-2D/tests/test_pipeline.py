from pathlib import Path

from PIL import Image

import pixel_fix.pipeline as pipeline_module
from pixel_fix.cleanup import CleanupResult
from pixel_fix.pipeline import PipelineConfig, PixelFixPipeline


def test_prepare_labels_uses_manual_pixel_size_and_resize_mode():
    labels = [
        [0, 1, 2, 3],
        [0, 1, 2, 3],
        [4, 5, 6, 7],
        [4, 5, 6, 7],
    ]

    prepared = PixelFixPipeline(PipelineConfig(pixel_width=2, downsample_mode="nearest")).prepare_labels(labels)

    assert prepared.pixel_width == 2
    assert prepared.grid_method == "manual"
    assert prepared.input_size == (4, 4)
    assert len(prepared.reduced_labels) == 2
    assert len(prepared.reduced_labels[0]) == 2


def test_run_on_labels_uses_generated_palette_size():
    labels = [
        [0, 1, 2, 3],
        [0, 1, 2, 3],
        [4, 5, 6, 7],
        [4, 5, 6, 7],
    ]

    result = PixelFixPipeline(
        PipelineConfig(pixel_width=2, key_colors=(0, 4), generated_shades=2)
    ).run_on_labels_detailed(labels)

    assert result.structured_palette is not None
    assert result.structured_palette.generated_shades == 2
    assert result.structured_palette.key_colors == [0, 4]
    assert result.effective_palette_size == 6
    output_colors = {value for row in result.labels for value in row}
    assert output_colors.issubset(set(result.structured_palette.labels()))


def test_run_on_labels_returns_structured_palette_metadata():
    labels = [
        [0xFF0000, 0xFF0000, 0x0000FF],
        [0xFF0000, 0x00FF00, 0x0000FF],
        [0xFFFF00, 0x00FF00, 0x0000FF],
    ]

    result = PixelFixPipeline(
        PipelineConfig(pixel_width=1, key_colors=(0xFF0000, 0x00FF00, 0x0000FF), generated_shades=2)
    ).run_on_labels_detailed(labels)

    assert result.structured_palette is not None
    assert result.structured_palette.source_mode == "advanced"
    assert result.histogram_size == 4
    assert result.seed_count == len(result.structured_palette.key_colors)
    assert result.ramp_count == len(result.structured_palette.ramps)
    assert result.effective_palette_size == result.structured_palette.palette_size()


def test_run_file_writes_real_png_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jpg"
    output_path = tmp_path / "output.png"
    image = Image.new("RGB", (2, 2))
    image.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)])
    image.save(input_path, format="JPEG")

    PixelFixPipeline(PipelineConfig(pixel_width=1, overwrite=True)).run_file(input_path, output_path)

    with Image.open(output_path) as output_image:
        assert output_image.format == "PNG"
        assert output_image.size == (2, 2)


def test_cleanup_runs_before_palette_mapping_and_after_mapping(monkeypatch) -> None:
    calls: list[tuple[str, list[list[int]]]] = []

    def fake_pre(labels, mode, *, workspace=None, alpha_mask=None):
        calls.append(("pre", [row[:] for row in labels]))
        return CleanupResult(labels=[[0x111111]], changed_pixels=1)

    def fake_post(labels, mode, *, alpha_mask=None):
        calls.append(("post", [row[:] for row in labels]))
        return CleanupResult(labels=[[0x222222]], changed_pixels=1)

    monkeypatch.setattr(pipeline_module, "cleanup_pre_palette_detailed", fake_pre)
    monkeypatch.setattr(pipeline_module, "cleanup_post_palette_detailed", fake_post)

    pipeline = PixelFixPipeline(PipelineConfig(pixel_width=1, cleanup_mode="balanced", palette_strategy="override"))
    prepared = pipeline.prepare_labels([[0xABCDEF]])
    result = pipeline.run_prepared_labels(prepared, palette_override=[0x010203])

    assert calls[0] == ("pre", [[0xABCDEF]])
    assert calls[1] == ("post", [[0x010203]])
    assert result.labels == [[0x222222]]
