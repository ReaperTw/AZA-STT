@echo off
cd /d "%~dp0"
set "AZA_STT_EXE=%~dp0AZA-STT.exe"
if not exist "%AZA_STT_EXE%" set "AZA_STT_EXE=%~dp0bin\AZA-STT.exe"
if not exist "%AZA_STT_EXE%" (
    echo AZA-STT.exe not found.
    pause
    exit /b 1
)
start "" "%AZA_STT_EXE%" --configure
