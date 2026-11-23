@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto launch
where py >nul 2>&1
if not errorlevel 1 (
    set "HAN_PY=py -3"
) else (
    where python >nul 2>&1
    if errorlevel 1 goto missing
    set "HAN_PY=python"
)
%HAN_PY% -c "import sys,struct; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,15) and struct.calcsize('P')==8 else 1)"
if errorlevel 1 goto unsupported
echo Preparing Hanroro Desktop. This is only needed the first time.
%HAN_PY% -m venv .venv
if errorlevel 1 goto failed
:dependencies
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt > setup.log 2>&1
if errorlevel 1 goto failed
:launch
".venv\Scripts\python.exe" -c "import numpy,psutil,pyaudiowpatch,pynvml; import PySide6; import winrt.windows.media.control; import winrt.windows.storage.streams; assert PySide6.__version__ == '6.12.0'" >nul 2>&1
if errorlevel 1 goto dependencies
if "%~2"=="--console" (
    ".venv\Scripts\python.exe" -X faulthandler main.py %~1
    pause
) else (
    start "" ".venv\Scripts\pythonw.exe" main.py %~1
)
exit /b 0
:missing
echo Python is not installed. Install 64-bit Python 3.12 or 3.14 from python.org.
echo Enable the Python launcher and Add Python to PATH, then run start.bat again.
pause
exit /b 1
:unsupported
echo This app needs 64-bit Python 3.11 through 3.14.
echo Install 64-bit Python 3.12 or 3.14, then run start.bat again.
pause
exit /b 1
:failed
echo Setup failed. Details are in setup.log in this folder.
if exist setup.log type setup.log
pause
exit /b 1
