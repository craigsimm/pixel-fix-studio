param()

$ErrorActionPreference = "Stop"

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Remove-GeneratedItems {
    param(
        [string[]]$Paths
    )

    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        $resolved = (Resolve-Path -LiteralPath $path).Path
        if (-not $resolved.StartsWith($workspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove path outside workspace: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

$generatedDirs = Get-ChildItem -Path $workspaceRoot -Recurse -Directory -Force |
    Where-Object {
        $_.Name -in @(".pytest_cache", "__pycache__", ".venv", "build", "dist") -or
        $_.Name -like "*.egg-info"
    } |
    Select-Object -ExpandProperty FullName

$generatedFiles = Get-ChildItem -Path $workspaceRoot -Recurse -File -Force |
    Where-Object { $_.Extension -eq ".spec" } |
    Select-Object -ExpandProperty FullName

Remove-GeneratedItems -Paths ($generatedDirs + $generatedFiles)
