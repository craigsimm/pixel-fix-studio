param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvRoot = Join-Path $workspaceRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
$sharedIcon = Join-Path $workspaceRoot "pixel-fix-studio.ico"
$distRoot = Join-Path $workspaceRoot "dist"
$stagingRoot = Join-Path $workspaceRoot "build\portable-apps"
$launcherWorkRoot = Join-Path $workspaceRoot "build\pyinstaller-launcher"
$launcherDistSource = Join-Path $distRoot "Pixel-Fix Studio"
$launcherBundleRoot = Join-Path $distRoot "Pixel-Fix-Studio"
$appsRoot = Join-Path $launcherBundleRoot "apps"

function Remove-WorkspaceTree {
    param(
        [string]$TargetPath
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return
    }

    $resolved = (Resolve-Path -LiteralPath $TargetPath).Path
    $workspacePath = $workspaceRoot.Path
    if (-not $resolved.StartsWith($workspacePath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside workspace: $resolved"
    }

    Remove-Item -LiteralPath $resolved -Recurse -Force
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    python -m venv $venvRoot
}

& $pythonExe -m pip install --upgrade pip setuptools wheel pyinstaller pytest
& $pythonExe -m pip install -e . -e '.\pixel-fix-2D[ai]' -e .\pixel-fix-3D

if (-not $SkipTests) {
    & (Join-Path $PSScriptRoot "test_all.ps1") -PythonExe $pythonExe
}

Remove-WorkspaceTree -TargetPath $stagingRoot
Remove-WorkspaceTree -TargetPath $launcherBundleRoot
Remove-WorkspaceTree -TargetPath $launcherDistSource
Remove-WorkspaceTree -TargetPath $launcherWorkRoot

New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null

& (Join-Path $workspaceRoot "pixel-fix-2D\scripts\build_windows_exe.ps1") `
    -PythonExe $pythonExe `
    -DistRoot (Join-Path $stagingRoot "pixel-fix-2d") `
    -WorkRoot (Join-Path $stagingRoot "work-pixel-fix-2d")

& (Join-Path $workspaceRoot "pixel-fix-3D\scripts\build_windows_exe.ps1") `
    -PythonExe $pythonExe `
    -DistRoot (Join-Path $stagingRoot "pixel-fix-3d") `
    -WorkRoot (Join-Path $stagingRoot "work-pixel-fix-3d")

Push-Location $workspaceRoot
try {
    & $pythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name "Pixel-Fix Studio" `
        --paths "src" `
        --distpath $distRoot `
        --specpath $launcherWorkRoot `
        --workpath $launcherWorkRoot `
        --icon $sharedIcon `
        --collect-data "pixel_fix_studio" `
        (Join-Path $PSScriptRoot "pyinstaller_launcher_entry.py")
}
finally {
    Pop-Location
}

Move-Item -LiteralPath $launcherDistSource -Destination $launcherBundleRoot
New-Item -ItemType Directory -Path $appsRoot -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $stagingRoot "pixel-fix-2d\Pixel-Fix 2D") -Destination (Join-Path $appsRoot "pixel-fix-2d") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $stagingRoot "pixel-fix-3d\Pixel-Fix 3D") -Destination (Join-Path $appsRoot "pixel-fix-3d") -Recurse -Force
