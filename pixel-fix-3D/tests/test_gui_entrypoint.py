from __future__ import annotations

import runpy

import pytest

import pixel_fix_3d.gui as gui_package


def test_gui_package_runs_as_module(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(gui_package, "main", lambda: calls.append("main") or 0)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("pixel_fix_3d.gui", run_name="__main__")

    assert exc_info.value.code == 0
    assert calls == ["main"]
