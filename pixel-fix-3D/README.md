> **Retired — 22 September 2026.** Pixel Fix Studio and Pixel Fix 3D are discontinued. Pixel Fix 2D continues as **[Pixel Fix](https://github.com/craigsimm/pixel-fix)**, a standalone editor with multiple document tabs and OpenAI-only image generation. Download the [standalone release](https://github.com/craigsimm/pixel-fix/releases/tag/v0.2.0). Pixel Fix 3D has no successor or project-conversion path. Historical source and releases remain available; this repository receives no further updates.

# Pixel-Fix Studio 3D

Pixel-Fix Studio 3D is a compact Windows-first desktop tool for quick retro 3D asset texturing. It is built as a separate sibling app to Pixel-Fix and focuses on one job only: pick a preset low poly model, click a face, and assign a pixel art texture.

The project is intentionally small. It is not a general 3D editor, scene builder, or modelling package.

## What It Does

- shows one preset low poly model at a time
- renders the model in a low-resolution PS1-style viewport
- lets you orbit the camera and zoom with the mouse wheel
- lets you click visible faces directly in the viewport
- loads a library of pixel art textures
- applies a selected texture to the selected face instantly
- keeps the UI styling aligned with the Pixel-Fix Studio tool family

## Included Model Presets

- Cube
- Box
- Tall Box
- 2D Plane
- Wedge
- Ramp
- 8-Sided Cylinder
- Roof
- Table
- Chair
- Car

## Current UI

The current interface uses a Pixel-Fix-style layout:

- top toolbar with `New`, `Open`, `Save`, and `Settings` icon buttons
- read-only zoom percentage display in the toolbar
- left tool palette with model buttons and camera/view buttons
- center viewport for preview and face selection
- right texture library for loading, assigning, and extracting textures
- bottom status bar showing shape, face, target texture size, and assigned texture

## Controls

- `Left drag`: orbit the model
- `Mouse wheel`: zoom in and out
- `Left click`: select the visible face under the cursor
- `Load Texture...`: import one PNG into the repo texture library
- `Texture button click`: apply that texture to the selected face
- `Save`: store the current model and one PNG per face into a `.pfx3d` project file
- `Open`: load a `.pfx3d` project file back into the app
- `Extract Textures...`: save one PNG per face to a folder, including grey templates for unassigned faces
- `Export GLB...`: export the current textured model as a single embedded `.glb`
- `Rotate View`: lock editing temporarily and play a 360 preview rotation

## `.pfx3d` Project Files

Pixel-Fix Studio 3D can save and load a single textured model as a `.pfx3d` file.

- `.pfx3d` is a ZIP-based project container
- it stores the current shape plus one embedded PNG per face
- unassigned faces are saved as flat grey template textures
- loading a `.pfx3d` file restores the saved shape and face textures into the current session
- the format is designed for one model at a time, not a full multi-object scene

## `.glb` Export

Pixel-Fix Studio 3D can export the current model to `.glb`.

- export writes the current shape only
- each face becomes its own glTF primitive and material
- face textures are embedded as PNG images inside the `.glb`
- unassigned faces export as flat grey template textures
- exported models are grounded so their lowest point sits at `Y=0`
- materials use unlit shading and nearest-neighbour texture sampling to preserve the retro look

## Camera Views

The tool palette includes quick camera snaps for:

- Left
- Right
- Top
- Bottom
- Back Left
- Back Right
- Rotate View

## Out Of Scope

These features are intentionally not part of the current version:

- multiple objects
- scene editing
- UV editing
- mesh editing
- vertex or edge editing
- animation
- advanced materials
- modern lighting or post effects
- `New` workflow
- `.glb` import

`New` is still a placeholder.

## Tech Notes

- Python desktop app using `tkinter`
- software-rendered viewport using `numpy` and `Pillow`
- `.glb` export using `pygltflib`
- nearest-neighbour texture sampling and viewport upscaling
- simple flat shading only
- tool and camera icons loaded from the repo `assets` folder during development

## Requirements

- Python `3.10+`
- Windows is the primary target environment

## Install

```bash
python -m pip install -e .
```

## Launch

From the project root:

```powershell
python -c "from pixel_fix_3d.gui import main; raise SystemExit(main())"
```

If editable install scripts are on `PATH`, this also works:

```powershell
pixel-fix-studio-3d
```

## Run Tests

```powershell
python -m pytest -q
```

## Build A Windows Executable

```powershell
.\scripts\build_windows_exe.ps1
```

## Project Layout

```text
src/pixel_fix_3d/
  gui/         Tkinter application shell, theme, persistence, tooltips
  renderer.py  Software rasterizer and face picking buffer
  shapes.py    Preset low poly model definitions
  state.py     Camera and editor state helpers
  textures.py  Texture loading and thumbnail helpers

assets/        Toolbar and tool-palette icon assets used during development
tests/         Unit and UI smoke tests
```
