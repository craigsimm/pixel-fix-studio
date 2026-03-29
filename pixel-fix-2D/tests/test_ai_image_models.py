from __future__ import annotations

from pixel_fix.gui.ai_image_models import (
    AI_IMAGE_MODELS,
    coerce_selected_model,
    get_model_option,
    models_for_keys,
    parse_model_id,
)


def test_parse_model_id() -> None:
    assert parse_model_id("openai:gpt-image-1") == ("openai", "gpt-image-1")
    assert parse_model_id("openai:gpt-image-1-mini") == ("openai", "gpt-image-1-mini")
    assert parse_model_id("openai:gpt-image-1.5") == ("openai", "gpt-image-1.5")
    assert parse_model_id("gemini:gemini-3.1-flash-image-preview") == ("gemini", "gemini-3.1-flash-image-preview")
    assert parse_model_id("gemini:gemini-3-pro-image-preview") == ("gemini", "gemini-3-pro-image-preview")
    assert parse_model_id("gemini:gemini-2.5-flash-image") == ("gemini", "gemini-2.5-flash-image")
    assert parse_model_id("gemini:imagen-4.0-generate-001") == ("gemini", "imagen-4.0-generate-001")
    assert parse_model_id("bad") == ("", "")
    assert parse_model_id("") == ("", "")


def test_models_for_keys_filters_by_provider() -> None:
    openai_only = models_for_keys(openai_key="sk-test", gemini_key="")
    assert all(m.provider == "openai" for m in openai_only)
    assert len(openai_only) >= 1

    gemini_only = models_for_keys(openai_key="", gemini_key="x")
    assert all(m.provider == "gemini" for m in gemini_only)

    both = models_for_keys(openai_key="a", gemini_key="b")
    assert len(both) == len(AI_IMAGE_MODELS)

    assert models_for_keys(openai_key="", gemini_key="") == []


def test_coerce_selected_model() -> None:
    assert coerce_selected_model("openai:gpt-image-1", openai_key="", gemini_key="") == ""
    coerced = coerce_selected_model("openai:gpt-image-1", openai_key="k", gemini_key="")
    assert coerced == "openai:gpt-image-1"
    first_openai = next(m.id for m in AI_IMAGE_MODELS if m.provider == "openai")
    assert coerce_selected_model("gemini:imagen-4.0-generate-001", openai_key="k", gemini_key="") == first_openai


def test_get_model_option() -> None:
    m = get_model_option("openai:gpt-image-1")
    assert m is not None
    assert m.label.startswith("OpenAI")
