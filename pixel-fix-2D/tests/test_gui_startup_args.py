from pathlib import Path

from pixel_fix.gui import app as gui_app


class _FakeRoot:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def after_idle(self, callback) -> None:
        self.callbacks.append(callback)


class _FakeApp:
    def __init__(self) -> None:
        self.root = _FakeRoot()
        self.opened: list[Path] = []

    def _open_image_path(self, path: Path) -> None:
        self.opened.append(path)


def test_parse_gui_args_reads_optional_open_argument() -> None:
    args = gui_app.parse_gui_args(["--open", "C:/example.png"])

    assert args.open_path == "C:/example.png"


def test_schedule_initial_open_opens_existing_file(tmp_path: Path) -> None:
    image_path = tmp_path / "startup.png"
    image_path.write_bytes(b"png")
    app = _FakeApp()

    gui_app.schedule_initial_open(app, str(image_path))

    assert len(app.root.callbacks) == 1
    app.root.callbacks[0]()
    assert app.opened == [image_path]


def test_schedule_initial_open_warns_for_missing_file(tmp_path: Path, monkeypatch) -> None:
    app = _FakeApp()
    warnings: list[str] = []
    monkeypatch.setattr(gui_app.messagebox, "showwarning", lambda _title, message: warnings.append(message))

    gui_app.schedule_initial_open(app, str(tmp_path / "missing.png"))

    assert len(app.root.callbacks) == 1
    app.root.callbacks[0]()
    assert warnings
