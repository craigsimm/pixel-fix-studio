from __future__ import annotations

import json
import socket
from pathlib import Path

from pixel_fix.gui import app as gui_app
from pixel_fix.gui import session_ipc


class _FakeRoot:
    def __init__(self) -> None:
        self.focus_calls: list[str] = []

    def after(self, _delay_ms: int, callback) -> None:
        callback()

    def winfo_toplevel(self):
        return self

    def deiconify(self) -> None:
        self.focus_calls.append("deiconify")

    def lift(self) -> None:
        self.focus_calls.append("lift")

    def focus_force(self) -> None:
        self.focus_calls.append("focus_force")


class _FakeVar:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def test_gui_session_server_accepts_open_path_command(tmp_path: Path, monkeypatch) -> None:
    root = _FakeRoot()
    opened: list[Path] = []
    monkeypatch.setattr(session_ipc, "ensure_storage_dir", lambda: tmp_path)
    server = session_ipc.GuiSessionServer(root, lambda path: opened.append(path))
    server.start()
    try:
        info = session_ipc.read_gui_session_info()
        assert info is not None
        with socket.create_connection(("127.0.0.1", info.port), timeout=1.0) as connection:
            connection.sendall(json.dumps({"type": "open_path", "path": str(tmp_path / "edit.png")}).encode("utf-8"))
            connection.shutdown(socket.SHUT_WR)
            response = json.loads(connection.recv(4096).decode("utf-8"))
        assert response["ok"] is True
        assert opened == [tmp_path / "edit.png"]
        assert root.focus_calls == ["deiconify", "lift", "focus_force"]
    finally:
        server.close()
    assert session_ipc.read_gui_session_info() is None


def test_open_external_image_path_requires_confirmation_when_document_is_open(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "incoming.png"
    image_path.write_bytes(b"png")
    app = gui_app.PixelFixGui.__new__(gui_app.PixelFixGui)
    app.root = object()
    app.document = object()
    app.process_status_var = _FakeVar()
    opened: list[Path] = []
    app._open_image_path = lambda path: opened.append(path)
    monkeypatch.setattr(gui_app.messagebox, "askyesno", lambda *args, **kwargs: False)

    app._open_external_image_path(image_path)

    assert opened == []
    assert "was not loaded" in app.process_status_var.value


def test_open_external_image_path_opens_after_confirmation(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "incoming.png"
    image_path.write_bytes(b"png")
    app = gui_app.PixelFixGui.__new__(gui_app.PixelFixGui)
    app.root = object()
    app.document = object()
    app.process_status_var = _FakeVar()
    opened: list[Path] = []
    app._open_image_path = lambda path: opened.append(path)
    monkeypatch.setattr(gui_app.messagebox, "askyesno", lambda *args, **kwargs: True)

    app._open_external_image_path(image_path)

    assert opened == [image_path]
