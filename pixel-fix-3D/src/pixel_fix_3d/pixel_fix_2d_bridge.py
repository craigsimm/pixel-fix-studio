from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PIXEL_FIX_2D_APP_DIR_NAME = "pixel-fix"
PIXEL_FIX_2D_SESSION_FILE_NAME = "gui-session.json"
PIXEL_FIX_2D_EXECUTABLE_NAME = "Pixel-Fix 2D.exe"


@dataclass(frozen=True)
class PixelFix2DLaunchSpec:
    command: list[str]
    cwd: Path
    env: dict[str, str] | None = None


def pixel_fix_2d_session_file() -> Path:
    appdata = os.getenv("APPDATA")
    base = Path(appdata) / PIXEL_FIX_2D_APP_DIR_NAME if appdata else Path.home() / f".{PIXEL_FIX_2D_APP_DIR_NAME}"
    return base / PIXEL_FIX_2D_SESSION_FILE_NAME


def read_pixel_fix_2d_session() -> dict[str, int] | None:
    path = pixel_fix_2d_session_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    port = data.get("port")
    pid = data.get("pid")
    if not isinstance(port, int) or port <= 0:
        return None
    if not isinstance(pid, int) or pid <= 0:
        return None
    return {"pid": pid, "port": port}


def clear_pixel_fix_2d_session() -> None:
    path = pixel_fix_2d_session_file()
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def send_open_path_to_pixel_fix_2d(path: Path, *, timeout: float = 1.0) -> bool:
    session = read_pixel_fix_2d_session()
    if session is None:
        return False
    payload = {"type": "open_path", "path": str(path)}
    try:
        with socket.create_connection(("127.0.0.1", int(session["port"])), timeout=timeout) as connection:
            connection.sendall(json.dumps(payload).encode("utf-8"))
            connection.shutdown(socket.SHUT_WR)
            response = connection.recv(4096)
    except OSError:
        clear_pixel_fix_2d_session()
        return False
    try:
        decoded = json.loads(response.decode("utf-8")) if response else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        clear_pixel_fix_2d_session()
        return False
    return bool(decoded.get("ok"))


def locate_pixel_fix_2d() -> PixelFix2DLaunchSpec | None:
    runtime_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else _workspace_root()
    bundled_candidates = (
        runtime_root / "apps" / "pixel-fix-2d",
        runtime_root / "build" / "portable-apps" / "pixel-fix-2d" / "Pixel-Fix 2D",
        runtime_root / "pixel-fix-2d",
    )
    for candidate in bundled_candidates:
        spec = _bundled_launch_spec(candidate)
        if spec is not None:
            return spec

    source_candidates = (
        runtime_root / "pixel-fix-2D",
        _workspace_root() / "pixel-fix-2D",
    )
    for candidate in source_candidates:
        spec = _source_launch_spec(candidate)
        if spec is not None:
            return spec
    return None


def launch_pixel_fix_2d(path: Path) -> bool:
    spec = locate_pixel_fix_2d()
    if spec is None:
        return False
    command = [*spec.command, "--open", str(path)]
    subprocess.Popen(command, cwd=str(spec.cwd), env=spec.env)
    return True


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _bundled_launch_spec(root: Path) -> PixelFix2DLaunchSpec | None:
    if not root.exists() or not root.is_dir():
        return None
    executable = root / PIXEL_FIX_2D_EXECUTABLE_NAME
    if executable.exists() and executable.is_file():
        return PixelFix2DLaunchSpec(command=[str(executable.resolve())], cwd=root.resolve())
    manifest_path = root / "app-manifest.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    executable_name = data.get("executable")
    if not isinstance(executable_name, str) or not executable_name.strip():
        return None
    executable = root / executable_name
    if not executable.exists() or not executable.is_file():
        return None
    return PixelFix2DLaunchSpec(command=[str(executable.resolve())], cwd=root.resolve())


def _source_launch_spec(root: Path) -> PixelFix2DLaunchSpec | None:
    package_dir = root / "src" / "pixel_fix"
    if not root.exists() or not root.is_dir() or not package_dir.is_dir():
        return None
    python_path = _preferred_source_python(root)
    environment = os.environ.copy()
    repo_src = root / "src"
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = f"{repo_src}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(repo_src)
    return PixelFix2DLaunchSpec(
        command=[str(python_path), "-m", "pixel_fix.gui"],
        cwd=root.resolve(),
        env=environment,
    )


def _preferred_source_python(source_root: Path) -> Path:
    source_root = source_root.resolve()
    workspace_root = source_root.parent
    workspace_python = workspace_root / ".venv" / "Scripts" / "python.exe"
    local_python = source_root / ".venv" / "Scripts" / "python.exe"
    current_python = Path(sys.executable).resolve()
    current_is_python = current_python.is_file() and current_python.name.lower().startswith("python")
    path_python_text = shutil.which("python")
    path_python = Path(path_python_text).resolve() if path_python_text else None

    candidates: list[Path] = [workspace_python, current_python, local_python]
    if path_python is not None:
        candidates.append(path_python)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate == current_python and not current_is_python:
            continue
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    if current_is_python:
        return current_python
    raise FileNotFoundError(f"No Python interpreter found for source launch under {source_root}.")
