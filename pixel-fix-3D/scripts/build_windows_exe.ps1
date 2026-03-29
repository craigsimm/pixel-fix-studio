param(
    [string]$PythonExe = "python",
    [string]$DistRoot = "",
    [string]$WorkRoot = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$workspaceRoot = Resolve-Path (Join-Path $repoRoot "..")
$entryScript = Join-Path $repoRoot "scripts\pyinstaller_gui_entry.py"
$iconFile = Join-Path $workspaceRoot "pixel-fix-studio.ico"
$resourceRoot = Join-Path $repoRoot "src\pixel_fix_3d\resources"
$projectToml = Join-Path $repoRoot "pyproject.toml"

if ([string]::IsNullOrWhiteSpace($DistRoot)) {
    $DistRoot = Join-Path $repoRoot "dist"
}
if ([string]::IsNullOrWhiteSpace($WorkRoot)) {
    $WorkRoot = Join-Path $repoRoot "build\pyinstaller"
}

New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null
New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null

$version = "0.0.0"
$versionLine = Get-Content $projectToml | Where-Object { $_ -match '^version\s*=' } | Select-Object -First 1
if ($versionLine -match '"([^"]+)"') {
    $version = $Matches[1]
}

Push-Location $repoRoot
try {
    & $PythonExe -m pip install pyinstaller

    & $PythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name "Pixel-Fix 3D" `
        --paths "src" `
        --distpath $DistRoot `
        --specpath $WorkRoot `
        --workpath $WorkRoot `
        --icon $iconFile `
        --collect-data "pixel_fix_3d" `
        --add-data "${resourceRoot};pixel_fix_3d/resources" `
        $entryScript

    $appRoot = Join-Path $DistRoot "Pixel-Fix 3D"
    $dataSource = Join-Path $repoRoot "data"
    $dataTarget = Join-Path $appRoot "data"
    if (Test-Path $dataSource) {
        New-Item -ItemType Directory -Path $dataTarget -Force | Out-Null
        Copy-Item -Path (Join-Path $dataSource "*") -Destination $dataTarget -Recurse -Force
    }
    $textureResourceSource = Join-Path $resourceRoot "textures"
    $textureDataTarget = Join-Path $dataTarget "textures"
    if (Test-Path $textureResourceSource) {
        New-Item -ItemType Directory -Path $textureDataTarget -Force | Out-Null
        Copy-Item -Path (Join-Path $textureResourceSource "*") -Destination $textureDataTarget -Recurse -Force
    }

    $manifestPath = Join-Path $appRoot "app-manifest.json"
    $manifest = @{
        app_id = "pixel-fix-3d"
        display_name = "Pixel-Fix 3D"
        version = $version
        executable = "Pixel-Fix 3D.exe"
    } | ConvertTo-Json
    Set-Content -LiteralPath $manifestPath -Value $manifest -Encoding utf8
}
finally {
    Pop-Location
}
