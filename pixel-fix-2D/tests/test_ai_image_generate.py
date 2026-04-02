import pixel_fix.gui.ai_image_generate as ai_image_generate


def test_generate_image_png_bytes_with_auto_install_retries_after_dependency_install(monkeypatch) -> None:
    calls: list[str] = []

    def fake_generate(**_: str) -> bytes:
        calls.append("generate")
        if len(calls) == 1:
            raise RuntimeError("AI image packages are not installed. Install with:\n  python -m pip install -e \".[ai]\"")
        return b"png"

    def fake_install() -> None:
        calls.append("install")

    monkeypatch.setattr(ai_image_generate, "generate_image_png_bytes", fake_generate)
    monkeypatch.setattr(ai_image_generate, "install_missing_ai_dependencies", fake_install)

    result = ai_image_generate.generate_image_png_bytes_with_auto_install(
        internal_model_id="openai:gpt-image-1",
        api_key="key",
        prompt="prompt",
    )

    assert result == b"png"
    assert calls == ["generate", "install", "generate"]


def test_generate_image_png_bytes_with_auto_install_does_not_retry_unrelated_errors(monkeypatch) -> None:
    def fake_generate(**_: str) -> bytes:
        raise RuntimeError("Prompt is empty.")

    monkeypatch.setattr(ai_image_generate, "generate_image_png_bytes", fake_generate)

    try:
        ai_image_generate.generate_image_png_bytes_with_auto_install(
            internal_model_id="openai:gpt-image-1",
            api_key="key",
            prompt="prompt",
        )
    except RuntimeError as exc:
        assert str(exc) == "Prompt is empty."
    else:
        raise AssertionError("Expected RuntimeError")


def test_install_missing_ai_dependencies_uses_current_python(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, capture_output, text, check):  # type: ignore[no-untyped-def]
        captured["command"] = command
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["check"] = check
        return Result()

    monkeypatch.setattr(ai_image_generate.sys, "executable", r"C:\Python\python.exe")
    monkeypatch.setattr(ai_image_generate.subprocess, "run", fake_run)

    ai_image_generate.install_missing_ai_dependencies()

    assert captured["command"] == [
        r"C:\Python\python.exe",
        "-m",
        "pip",
        "install",
        "openai>=1.40.0",
        "google-genai>=1.0.0",
    ]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["check"] is False
