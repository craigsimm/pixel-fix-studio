from __future__ import annotations

import json
import os
import socket
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .persist import ensure_storage_dir

GUI_SESSION_FILE_NAME = "gui-session.json"


@dataclass(frozen=True)
class GuiSessionInfo:
    pid: int
    port: int


def gui_session_file_path() -> Path:
    return ensure_storage_dir() / GUI_SESSION_FILE_NAME


def read_gui_session_info() -> GuiSessionInfo | None:
    path = gui_session_file_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pid = data.get("pid")
    port = data.get("port")
    if not isinstance(pid, int) or pid <= 0:
        return None
    if not isinstance(port, int) or port <= 0:
        return None
    return GuiSessionInfo(pid=pid, port=port)


def write_gui_session_info(info: GuiSessionInfo) -> None:
    ensure_storage_dir()
    gui_session_file_path().write_text(
        json.dumps({"pid": info.pid, "port": info.port}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def clear_gui_session_info(*, expected_port: int | None = None) -> None:
    path = gui_session_file_path()
    if not path.exists():
        return
    if expected_port is not None:
        info = read_gui_session_info()
        if info is not None and info.port != expected_port:
            return
    try:
        path.unlink()
    except OSError:
        return


class GuiSessionServer:
    def __init__(self, root: tk.Misc, on_open_path: Callable[[Path], None]) -> None:
        self.root = root
        self._on_open_path = on_open_path
        self._socket: socket.socket | None = None
        self._port: int | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int | None:
        return self._port

    def start(self) -> None:
        if self._socket is not None:
            return
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen()
        server.settimeout(0.5)
        self._socket = server
        self._port = int(server.getsockname()[1])
        write_gui_session_info(GuiSessionInfo(pid=os.getpid(), port=self._port))
        self._thread = threading.Thread(target=self._serve, name="pixel-fix-gui-session", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop_event.set()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._port is not None:
            clear_gui_session_info(expected_port=self._port)
        self._thread = None
        self._port = None

    def _serve(self) -> None:
        while not self._stop_event.is_set():
            server = self._socket
            if server is None:
                return
            try:
                connection, _address = server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                self._handle_connection(connection)

    def _handle_connection(self, connection: socket.socket) -> None:
        payload = bytearray()
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            payload.extend(chunk)
        try:
            command = json.loads(payload.decode("utf-8")) if payload else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_response(connection, ok=False, error="Invalid request.")
            return
        if not isinstance(command, dict) or command.get("type") != "open_path" or not isinstance(command.get("path"), str):
            self._send_response(connection, ok=False, error="Unsupported request.")
            return
        path = Path(command["path"])
        self.root.after(0, lambda requested_path=path: self._handle_open_request(requested_path))
        self._send_response(connection, ok=True)

    def _handle_open_request(self, path: Path) -> None:
        self._focus_root()
        self._on_open_path(path)

    def _focus_root(self) -> None:
        try:
            self.root.winfo_toplevel().deiconify()
            self.root.winfo_toplevel().lift()
            self.root.winfo_toplevel().focus_force()
        except tk.TclError:
            return

    @staticmethod
    def _send_response(connection: socket.socket, *, ok: bool, error: str | None = None) -> None:
        response = {"ok": ok}
        if error:
            response["error"] = error
        connection.sendall(json.dumps(response).encode("utf-8"))
