$ErrorActionPreference = "Stop"

$exePath = Join-Path $PSScriptRoot "AZA-STT.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    $exePath = Join-Path $PSScriptRoot "bin\AZA-STT.exe"
}
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "AZA-STT.exe was not found beside this script or under bin."
}

$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupFolder "AZA-STT.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = Split-Path -Parent $exePath
$shortcut.Description = "AZA-STT"
$shortcut.Save()

Write-Output "Startup shortcut created: $shortcutPath"
