@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" stop.py
) else (
    py -3 stop.py
)
if errorlevel 1 pause
