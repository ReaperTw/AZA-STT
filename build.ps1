$ErrorActionPreference = "Stop"

$pythonPath = Join-Path $env:USERPROFILE "AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = "python"
}

& $pythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name AZA-STT `
    --collect-all opencc `
    --collect-all _soundfile_data `
    groq_dictate.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

Write-Output "Built: $PSScriptRoot\dist\AZA-STT.exe"
