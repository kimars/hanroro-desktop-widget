@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" recover_desktop.py
) else (
    py -3 recover_desktop.py
)
if errorlevel 1 pause
