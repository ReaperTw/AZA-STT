$ErrorActionPreference = "Stop"

$shortcutPath = Join-Path ([Environment]::GetFolderPath("Startup")) "AZA-STT.lnk"
if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath
    Write-Output "Startup shortcut removed: $shortcutPath"
} else {
    Write-Output "No AZA-STT startup shortcut was found."
}
