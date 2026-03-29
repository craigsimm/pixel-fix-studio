from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .models import AppInstallation, LauncherSettings


@dataclass(frozen=True)
class LaunchRequest:
    command: list[str]
    cwd: Path
    env: dict[str, str] | None


@dataclass(frozen=True)
class AppSpec:
    key: str
    display_name: str
    source_dir_name: str
    bundled_dir_name: str
    package_dir: Path
    module_name: str
    executable_name: str
    data_subdir: str
    manifest_app_id: str
    supports_open_arg: bool = False


APP_SPECS: dict[str, AppSpec] = {
    "pixel_fix_2d": AppSpec(
        key="pixel_fix_2d",
        display_name="Pixel-Fix 2D",
        source_dir_name="pixel-fix-2D",
        bundled_dir_name="pixel-fix-2d",
        package_dir=Path("src") / "pixel_fix",
        module_name="pixel_fix.gui",
        executable_name="Pixel-Fix 2D.exe",
        data_subdir="palettes",
        manifest_app_id="pixel-fix-2d",
        supports_open_arg=True,
    ),
    "pixel_fix_3d": AppSpec(
        key="pixel_fix_3d",
        display_name="Pixel-Fix 3D",
        source_dir_name="pixel-fix-3D",
        bundled_dir_name="pixel-fix-3d",
        package_dir=Path("src") / "pixel_fix_3d",
        module_name="pixel_fix_3d.gui",
        executable_name="Pixel-Fix 3D.exe",
        data_subdir="textures",
        manifest_app_id="pixel-fix-3d",
    ),
}


def runtime_root(project_root: Path) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root.resolve()


def detect_default_install_dirs(project_root: Path) -> LauncherSettings:
    root = runtime_root(project_root)
    resolved: dict[str, str] = {}
    for spec in APP_SPECS.values():
        install = _resolve_from_candidates(
            spec,
            (
                ("bundled", root / "apps" / spec.bundled_dir_name),
                ("source", root / spec.source_dir_name),
            ),
        )
        resolved[f"{spec.key}_install_dir"] = str(install.install_root) if install.installed and install.install_root is not None else ""
    return LauncherSettings(**resolved)


def validate_install_dir(path_value: str | Path | None, app_key: str) -> AppInstallation:
    spec = _app_spec(app_key)
    if path_value is None:
        return _missing_installation(spec, "Not configured.")
    text = str(path_value).strip()
    if not text:
        return _missing_installation(spec, "Not configured.")
    path = Path(text).expanduser()
    if not path.exists():
        return _missing_installation(spec, "Directory does not exist.")
    if not path.is_dir():
        return _missing_installation(spec, "Path is not a directory.")

    package_dir = path / spec.package_dir
    if package_dir.is_dir():
        source = _source_installation(spec, path, mode="custom")
        if source.installed:
            return source
        return _missing_installation(spec, source.detail)

    bundled = _bundled_installation(spec, path, mode="custom")
    if bundled.installed:
        return bundled
    return _missing_installation(spec, bundled.detail)


def resolve_app_installation(project_root: Path, settings: LauncherSettings, app_key: str) -> AppInstallation:
    spec = _app_spec(app_key)
    root = runtime_root(project_root)
    custom_text = _saved_install_dir(settings, spec)
    custom_path = Path(custom_text).expanduser() if custom_text else None
    candidates: list[tuple[str, Path]] = [
        ("bundled", root / "apps" / spec.bundled_dir_name),
        ("source", root / spec.source_dir_name),
    ]
    if custom_path is not None and all(candidate.resolve() != custom_path.resolve() for _mode, candidate in candidates if candidate.exists()):
        candidates.append(("custom", custom_path))
    install = _resolve_from_candidates(spec, candidates)
    if install.installed:
        return install
    if custom_path is not None:
        custom = validate_install_dir(custom_path, spec.key)
        if custom.detail not in {"Not configured.", "Not installed."}:
            return custom
    return install


def build_launch_request(installation: AppInstallation, *, open_path: Path | None = None) -> LaunchRequest:
    if not installation.installed or installation.install_root is None:
        raise ValueError(installation.missing_app_message)
    spec = _app_spec(installation.key)
    if installation.executable_path is not None:
        command = [str(installation.executable_path)]
        if open_path is not None and spec.supports_open_arg:
            command.extend(["--open", str(open_path)])
        return LaunchRequest(command=command, cwd=installation.install_root, env=None)

    python_executable = preferred_source_python(installation.install_root)
    environment = os.environ.copy()
    repo_src = installation.install_root / "src"
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = f"{repo_src}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(repo_src)
    command = [str(python_executable), "-m", spec.module_name]
    if open_path is not None and spec.supports_open_arg:
        command.extend(["--open", str(open_path)])
    return LaunchRequest(command=command, cwd=installation.install_root, env=environment)


def preferred_source_python(source_root: Path) -> Path:
    source_root = source_root.resolve()
    workspace_root = source_root.parent
    workspace_python = workspace_root / ".venv" / "Scripts" / "python.exe"
    local_python = source_root / ".venv" / "Scripts" / "python.exe"
    current_python = Path(sys.executable).resolve()
    current_is_python = current_python.is_file() and current_python.name.lower().startswith("python")
    path_python_text = shutil.which("python")
    path_python = Path(path_python_text).resolve() if path_python_text else None

    in_combined_workspace = (workspace_root / "src" / "pixel_fix_studio").is_dir()
    candidates: list[Path] = []
    if in_combined_workspace:
        candidates.extend([workspace_python, current_python, local_python])
    else:
        candidates.extend([local_python, current_python, workspace_python])
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


def _resolve_from_candidates(spec: AppSpec, candidates: tuple[tuple[str, Path], ...] | list[tuple[str, Path]]) -> AppInstallation:
    seen: set[Path] = set()
    last_detail = "Not installed."
    for mode, candidate in candidates:
        try:
            resolved_candidate = candidate.resolve()
        except OSError:
            resolved_candidate = candidate
        if resolved_candidate in seen:
            continue
        seen.add(resolved_candidate)

        if mode == "bundled":
            install = _bundled_installation(spec, candidate, mode=mode)
        else:
            install = _source_installation(spec, candidate, mode=mode)
            if not install.installed and mode == "custom":
                bundled = _bundled_installation(spec, candidate, mode=mode)
                if bundled.installed:
                    install = bundled
                elif bundled.detail != "Not installed.":
                    last_detail = bundled.detail
        if install.installed:
            return install
        if install.detail != "Not installed.":
            last_detail = install.detail
    return _missing_installation(spec, last_detail)


def _bundled_installation(spec: AppSpec, root: Path, *, mode: str) -> AppInstallation:
    if not root.exists() or not root.is_dir():
        return _missing_installation(spec, "Not installed.")
    manifest_path = root / "app-manifest.json"
    if not manifest_path.exists():
        return _missing_installation(spec, "Missing app-manifest.json.")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _missing_installation(spec, "Invalid app-manifest.json.")
    app_id = data.get("app_id")
    executable_name = data.get("executable")
    if app_id != spec.manifest_app_id:
        return _missing_installation(spec, f"Unexpected manifest app_id: {app_id!r}.")
    if not isinstance(executable_name, str) or not executable_name.strip():
        return _missing_installation(spec, "Manifest missing executable.")
    executable_path = root / executable_name
    if not executable_path.exists() or not executable_path.is_file():
        return _missing_installation(spec, f"Missing executable: {executable_name}.")
    data_root = _seed_data_root(spec, root, mode=mode)
    detail = f"{spec.display_name} bundled install detected."
    launch_detail = f"Executable: {executable_path}"
    return AppInstallation(
        key=spec.key,
        display_name=spec.display_name,
        install_root=root.resolve(),
        executable_path=executable_path.resolve(),
        manifest_path=manifest_path.resolve(),
        data_root=data_root.resolve() if data_root.exists() else data_root,
        mode=mode,
        installed=True,
        detail=detail,
        launch_detail=launch_detail,
        missing_app_message=f"{spec.display_name} is not installed.",
    )


def _source_installation(spec: AppSpec, root: Path, *, mode: str) -> AppInstallation:
    if not root.exists() or not root.is_dir():
        return _missing_installation(spec, "Not installed.")
    package_dir = root / spec.package_dir
    if not package_dir.is_dir():
        return _missing_installation(spec, f"Missing {spec.package_dir.as_posix()} package.")
    data_root = _seed_data_root(spec, root, mode=mode)
    if not data_root.exists() or not data_root.is_dir():
        return _missing_installation(spec, f"Missing data/{spec.data_subdir} folder.")
    python_path = preferred_source_python(root)
    detail = f"{spec.display_name} source folder detected."
    launch_detail = f"Python: {python_path}"
    return AppInstallation(
        key=spec.key,
        display_name=spec.display_name,
        install_root=root.resolve(),
        executable_path=None,
        manifest_path=None,
        data_root=data_root.resolve(),
        mode=mode,
        installed=True,
        detail=detail,
        launch_detail=launch_detail,
        missing_app_message=f"{spec.display_name} is not installed.",
    )


def _missing_installation(spec: AppSpec, detail: str) -> AppInstallation:
    return AppInstallation(
        key=spec.key,
        display_name=spec.display_name,
        install_root=None,
        executable_path=None,
        manifest_path=None,
        data_root=None,
        mode=None,
        installed=False,
        detail=detail,
        launch_detail="",
        missing_app_message=f"{spec.display_name} is not installed.",
    )


def _seed_data_root(spec: AppSpec, install_root: Path, *, mode: str) -> Path:
    data_root = install_root / "data" / spec.data_subdir
    resource_root = _resource_library_root(spec, install_root, mode=mode)
    if resource_root is not None and resource_root.exists() and resource_root.is_dir():
        data_root.mkdir(parents=True, exist_ok=True)
        for source in resource_root.rglob("*"):
            relative = source.relative_to(resource_root)
            destination = data_root / relative
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    return data_root


def _resource_library_root(spec: AppSpec, install_root: Path, *, mode: str) -> Path | None:
    if mode == "bundled":
        return install_root / "_internal" / spec.package_dir.name / "resources" / spec.data_subdir
    return install_root / spec.package_dir / "resources" / spec.data_subdir


def _saved_install_dir(settings: LauncherSettings, spec: AppSpec) -> str:
    if spec.key == "pixel_fix_2d":
        return settings.pixel_fix_2d_install_dir
    return settings.pixel_fix_3d_install_dir


def _app_spec(app_key: str) -> AppSpec:
    try:
        return APP_SPECS[app_key]
    except KeyError as exc:
        raise ValueError(f"Unknown app key: {app_key}") from exc
