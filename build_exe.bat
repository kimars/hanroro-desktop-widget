@echo off
setlocal
cd /d "%~dp0"
if exist ".build-venv\Scripts\python.exe" goto install
where py >nul 2>&1
if errorlevel 1 goto missing
py -3.12 -c "import sys" >nul 2>&1
if errorlevel 1 (set "BUILD_PY=py -3") else (set "BUILD_PY=py -3.12")
%BUILD_PY% -c "import sys,struct; sys.exit(0 if (3,11)<=sys.version_info[:2]<(3,15) and struct.calcsize('P')==8 else 1)"
if errorlevel 1 goto missing
%BUILD_PY% -m venv .build-venv
if errorlevel 1 goto failed
:install
".build-venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" -m pip install -r requirements.txt "pyinstaller>=6.16,<7"
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" build_release.py
if errorlevel 1 goto failed
echo.
echo EXE: dist\HanroroWidget\HanroroWidget.exe
echo SHARE THIS ZIP: release\HanroroWidget_Windows.zip
explorer "%CD%\release"
pause
exit /b 0
:missing
echo Install 64-bit Python 3.12 with the Python launcher, then run this file again.
pause
exit /b 1
:failed
echo Build failed. Check the error above.
pause
exit /b 1
