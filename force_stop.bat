@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0force_stop.ps1"
if errorlevel 1 goto failed
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" recover_desktop.py
) else (
    py -3 recover_desktop.py
)
echo If the tray icon remains, move the mouse over it once.
pause
exit /b 0
:failed
echo Could not stop the app. Open Task Manager - Details to stop its pythonw.exe process.
pause
