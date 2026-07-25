$ErrorActionPreference = "Stop"

$exePath = Join-Path $PSScriptRoot "AZA-STT.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "AZA-STT.exe must be in the same folder as this script."
}

$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupFolder "AZA-STT.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = "AZA-STT"
$shortcut.Save()

Write-Output "Startup shortcut created: $shortcutPath"
