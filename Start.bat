@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 優先使用當前使用者目錄下的 Python 3.10
set "PYTHON_PATH=%USERPROFILE%\AppData\Local\Programs\Python\Python310\python.exe"
if not exist "%PYTHON_PATH%" (
    :: 如果找不到，則嘗試直接呼叫環境變數中的 python
    set "PYTHON_PATH=python"
)

:: 執行 Python
"%PYTHON_PATH%" groq_dictate.py
