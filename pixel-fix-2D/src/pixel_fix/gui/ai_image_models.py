from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AiImageModelOption:
    """One selectable image generation model in Preferences / generate dialog."""

    id: str
    label: str
    provider: str  # "openai" | "gemini"


# Internal ids are "provider:api_model_id" for persistence and dispatch.
# Google model ids match https://ai.google.dev/gemini-api/docs/image-generation
# (Nano Banana / Nano Banana 2 / Nano Banana Pro + Imagen 4).
AI_IMAGE_MODELS: tuple[AiImageModelOption, ...] = (
    AiImageModelOption(id="openai:gpt-image-1.5", label="OpenAI — GPT Image 1.5", provider="openai"),
    AiImageModelOption(id="openai:gpt-image-1", label="OpenAI — GPT Image 1", provider="openai"),
    AiImageModelOption(id="openai:gpt-image-1-mini", label="OpenAI — GPT Image 1 Mini", provider="openai"),
    AiImageModelOption(id="gemini:gemini-3.1-flash-image-preview", label="Google — Gemini 3.1 Flash Image (Nano Banana 2, preview)", provider="gemini"),
    AiImageModelOption(id="gemini:gemini-3-pro-image-preview", label="Google — Gemini 3 Pro Image (Nano Banana Pro, preview)", provider="gemini"),
    AiImageModelOption(id="gemini:gemini-2.5-flash-image", label="Google — Gemini 2.5 Flash Image (Nano Banana)", provider="gemini"),
    AiImageModelOption(id="gemini:imagen-4.0-generate-001", label="Google — Imagen 4", provider="gemini"),
    AiImageModelOption(id="gemini:imagen-4.0-fast-generate-001", label="Google — Imagen 4 Fast", provider="gemini"),
    AiImageModelOption(id="gemini:imagen-4.0-ultra-generate-001", label="Google — Imagen 4 Ultra", provider="gemini"),
)

_AI_MODEL_BY_ID = {m.id: m for m in AI_IMAGE_MODELS}


def parse_model_id(model_id: str) -> tuple[str, str]:
    """Return (provider, api_model_id) from internal id, or ("", "") if invalid."""
    if ":" not in model_id:
        return "", ""
    provider, _, rest = model_id.partition(":")
    rest = rest.strip()
    if provider not in {"openai", "gemini"} or not rest:
        return "", ""
    return provider, rest


def models_for_keys(*, openai_key: str, gemini_key: str) -> list[AiImageModelOption]:
    """Filter catalog by non-empty API keys (after strip)."""
    has_openai = bool((openai_key or "").strip())
    has_gemini = bool((gemini_key or "").strip())
    if not has_openai and not has_gemini:
        return []
    out: list[AiImageModelOption] = []
    for m in AI_IMAGE_MODELS:
        if m.provider == "openai" and has_openai:
            out.append(m)
        elif m.provider == "gemini" and has_gemini:
            out.append(m)
    return out


def get_model_option(model_id: str) -> AiImageModelOption | None:
    return _AI_MODEL_BY_ID.get(model_id)


def coerce_selected_model(
    requested: str,
    *,
    openai_key: str,
    gemini_key: str,
) -> str:
    """If requested is not valid for current keys, return first available id or ""."""
    available = models_for_keys(openai_key=openai_key, gemini_key=gemini_key)
    if not available:
        return ""
    ids = {m.id for m in available}
    if requested in ids:
        return requested
    return available[0].id
