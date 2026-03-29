param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $defaultPython = Join-Path $workspaceRoot ".venv\Scripts\python.exe"
    $PythonExe = if (Test-Path $defaultPython) { $defaultPython } else { "python" }
}

$originalPythonPath = $env:PYTHONPATH

try {
    $env:PYTHONPATH = Join-Path $workspaceRoot "src"
    & $PythonExe -m pytest -q tests
    if ($LASTEXITCODE -ne 0) { throw "Launcher tests failed." }

    $env:PYTHONPATH = Join-Path $workspaceRoot "pixel-fix-2D\src"
    & $PythonExe -m pytest -q pixel-fix-2D\tests
    if ($LASTEXITCODE -ne 0) { throw "Pixel-Fix 2D tests failed." }

    $env:PYTHONPATH = Join-Path $workspaceRoot "pixel-fix-3D\src"
    & $PythonExe -m pytest -q pixel-fix-3D\tests
    if ($LASTEXITCODE -ne 0) { throw "Pixel-Fix 3D tests failed." }
}
finally {
    if ($null -eq $originalPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $originalPythonPath
    }
}
