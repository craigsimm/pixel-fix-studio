from pathlib import Path

import pixel_fix_studio.app as app_module
from pixel_fix_studio.app import PixelFixStudioApp
from pixel_fix_studio.launcher_apps import LaunchRequest
from pixel_fix_studio.models import AppInstallation


class _DummyProcess:
    def __init__(self, *, pid: int, returncode: int | None = None) -> None:
        self.pid = pid
        self._returncode = returncode

    def poll(self) -> int | None:
        return self._returncode


def _installation(root: Path) -> AppInstallation:
    return AppInstallation(
        key="pixel_fix_3d",
        display_name="Pixel-Fix 3D",
        install_root=root,
        executable_path=root / "Pixel-Fix 3D.exe",
        manifest_path=root / "app-manifest.json",
        data_root=root / "data" / "textures",
        mode="bundled",
        installed=True,
        detail="Pixel-Fix 3D bundled install detected.",
        launch_detail=f"Executable: {root / 'Pixel-Fix 3D.exe'}",
        missing_app_message="Pixel-Fix 3D is not installed.",
    )


def test_launch_installation_blocks_duplicate_running_process(tmp_path: Path, monkeypatch) -> None:
    app = PixelFixStudioApp.__new__(PixelFixStudioApp)
    app._active_launch_processes = {"pixel_fix_3d": _DummyProcess(pid=321)}
    statuses: list[tuple[str, str]] = []
    app._set_status = lambda message, detail: statuses.append((message, detail))
    monkeypatch.setattr(
        app_module,
        "build_launch_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("build_launch_request should not be called")),
    )

    app._launch_installation(_installation(tmp_path), success_message="Launching Pixel-Fix 3D.")

    assert statuses == [("Pixel-Fix 3D is already running.", f"Executable: {tmp_path / 'Pixel-Fix 3D.exe'}")]


def test_launch_installation_tracks_started_process(tmp_path: Path, monkeypatch) -> None:
    app = PixelFixStudioApp.__new__(PixelFixStudioApp)
    app._active_launch_processes = {}
    statuses: list[tuple[str, str]] = []
    app._set_status = lambda message, detail: statuses.append((message, detail))
    process = _DummyProcess(pid=654)
    monkeypatch.setattr(
        app_module,
        "build_launch_request",
        lambda installation, open_path=None: LaunchRequest(
            command=[str(installation.executable_path)],
            cwd=installation.install_root or tmp_path,
            env=None,
        ),
    )
    monkeypatch.setattr(app_module.subprocess, "Popen", lambda *args, **kwargs: process)

    app._launch_installation(_installation(tmp_path), success_message="Launching Pixel-Fix 3D.")

    assert app._active_launch_processes["pixel_fix_3d"] is process
    assert statuses == [("Launching Pixel-Fix 3D.", f"Executable: {tmp_path / 'Pixel-Fix 3D.exe'} | PID: 654")]
