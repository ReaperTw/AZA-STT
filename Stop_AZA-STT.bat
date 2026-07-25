@echo off
chcp 65001 >nul
echo 正在關閉 AZA-STT...

:: 使用 PowerShell 尋找命令列包含 groq_dictate.py 的 python.exe 並強制結束
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' and CommandLine like '%%groq_dictate.py%%'\" | Invoke-CimMethod -MethodName Terminate" >nul 2>&1

echo.
echo 程式已嘗試關閉。
pause
