from __future__ import annotations

import base64
import io
import subprocess
import sys
from typing import TYPE_CHECKING

from .ai_image_models import parse_model_id

if TYPE_CHECKING:
    pass


_MISSING_AI_DEPS = (
    "AI image packages are not installed. Install with:\n"
    '  python -m pip install -e ".[ai]"'
)
_AI_PACKAGE_SPECS = ("openai>=1.40.0", "google-genai>=1.0.0")


def generate_image_png_bytes(*, internal_model_id: str, api_key: str, prompt: str) -> bytes:
    """
    Call the configured provider and return PNG file bytes.

    internal_model_id format: "openai:gpt-image-1", "gemini:gemini-3.1-flash-image-preview", etc.
    """
    provider, api_model = parse_model_id(internal_model_id)
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("API key is empty.")
    text = (prompt or "").strip()
    if not text:
        raise RuntimeError("Prompt is empty.")

    if provider == "openai":
        return _openai_generate_png(api_model, key, text)
    if provider == "gemini":
        return _gemini_generate_png(api_model, key, text)
    raise RuntimeError(f"Unknown image model: {internal_model_id!r}")


def generate_image_png_bytes_with_auto_install(*, internal_model_id: str, api_key: str, prompt: str) -> bytes:
    try:
        return generate_image_png_bytes(
            internal_model_id=internal_model_id,
            api_key=api_key,
            prompt=prompt,
        )
    except RuntimeError as exc:
        if not is_missing_ai_dependencies_error(exc):
            raise
    install_missing_ai_dependencies()
    return generate_image_png_bytes(
        internal_model_id=internal_model_id,
        api_key=api_key,
        prompt=prompt,
    )


def is_missing_ai_dependencies_error(error: BaseException | str) -> bool:
    message = str(error)
    return message.startswith("AI image packages are not installed.")


def install_missing_ai_dependencies() -> None:
    python_executable = _pip_python_executable()
    command = [python_executable, "-m", "pip", "install", *_AI_PACKAGE_SPECS]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout or "").strip()
    if detail:
        raise RuntimeError(f"Failed to install AI image packages:\n{detail}") from None
    raise RuntimeError("Failed to install AI image packages.") from None


def _pip_python_executable() -> str:
    executable = sys.executable
    if executable and executable.lower().endswith(("python.exe", "python")):
        return executable
    raise RuntimeError(
        "AI image packages are missing from this build and cannot be installed automatically here."
    )


def _openai_generate_png(model: str, api_key: str, prompt: str) -> bytes:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(_MISSING_AI_DEPS) from exc

    client = OpenAI(api_key=api_key)
    kwargs: dict = {"model": model, "prompt": prompt, "n": 1}
    if model in ("gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5"):
        kwargs["size"] = "1024x1024"
        kwargs["quality"] = "medium"
    else:
        kwargs["size"] = "1024x1024"

    try:
        response = client.images.generate(**kwargs)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"OpenAI image generation failed: {exc}") from exc

    if not response.data:
        raise RuntimeError("OpenAI returned no images.")
    item = response.data[0]
    b64 = getattr(item, "b64_json", None)
    if b64:
        return base64.standard_b64decode(b64)
    url = getattr(item, "url", None)
    if url:
        import urllib.request

        try:
            with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310
                data = resp.read()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to download OpenAI image URL: {exc}") from exc
        return _ensure_png_bytes(data)
    raise RuntimeError("OpenAI response had neither b64_json nor url.")


def _gemini_generate_png(model: str, api_key: str, prompt: str) -> bytes:
    """Imagen uses generate_images; Gemini native image models use generate_content."""
    if model.startswith("imagen-"):
        return _gemini_imagen_generate_png(model, api_key, prompt)
    return _gemini_native_image_generate_png(model, api_key, prompt)


def _gemini_native_image_generate_png(model: str, api_key: str, prompt: str) -> bytes:
    """Gemini native image (Nano Banana) models: generate_content per Google docs."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(_MISSING_AI_DEPS) from exc

    client = genai.Client(api_key=api_key)
    # Prefer image-only responses; see https://ai.google.dev/gemini-api/docs/image-generation
    config = types.GenerateContentConfig(response_modalities=["IMAGE"])
    try:
        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=config,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Google Gemini image generation failed: {exc}") from exc

    parts = getattr(response, "parts", None)
    if not parts:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) if content is not None else None

    if not parts:
        raise RuntimeError("Google Gemini returned no content parts.")

    last_png: bytes | None = None
    for part in parts:
        # Skip "thinking" interim parts; keep the final rendered image (docs: Thinking / Nano Banana).
        if getattr(part, "thought", None):
            continue
        inline = getattr(part, "inline_data", None)
        if inline is not None:
            raw = getattr(inline, "data", None)
            if isinstance(raw, (bytes, bytearray)):
                last_png = _ensure_png_bytes(bytes(raw))
            elif isinstance(raw, str):
                last_png = _ensure_png_bytes(base64.standard_b64decode(raw))
        elif hasattr(part, "as_image"):
            try:
                image_obj = part.as_image()
                save_buf = io.BytesIO()
                image_obj.save(save_buf, format="PNG")
                last_png = save_buf.getvalue()
            except Exception:  # noqa: BLE001
                continue

    if last_png is not None:
        return last_png
    raise RuntimeError("Google Gemini response had no image data in parts.")


def _ensure_png_bytes(data: bytes) -> bytes:
    """If data is already PNG, return as-is; otherwise convert via Pillow."""
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return data
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to convert image data to PNG.") from exc
    with Image.open(io.BytesIO(data)) as im:
        rgba = im.convert("RGBA")
        out = io.BytesIO()
        rgba.save(out, format="PNG")
        return out.getvalue()


def _gemini_imagen_generate_png(model: str, api_key: str, prompt: str) -> bytes:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(_MISSING_AI_DEPS) from exc

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
                output_mime_type="image/png",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Google Imagen generation failed: {exc}") from exc

    if not response.generated_images:
        raise RuntimeError("Google Imagen returned no images.")
    first = response.generated_images[0]
    image_obj = getattr(first, "image", None)
    if image_obj is None:
        raise RuntimeError("Google Imagen response missing image payload.")

    raw = getattr(image_obj, "image_bytes", None)
    if raw is not None and isinstance(raw, (bytes, bytearray)):
        return _ensure_png_bytes(bytes(raw))

    # Some SDK versions expose PIL Image
    save_buf = io.BytesIO()
    try:
        image_obj.save(save_buf, format="PNG")
        return save_buf.getvalue()
    except Exception:  # noqa: BLE001
        pass

    raise RuntimeError("Could not read image bytes from Google Imagen response.")
