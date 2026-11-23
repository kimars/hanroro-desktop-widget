@echo off
setlocal
cd /d "%~dp0"
set "HANRORO_SOFTWARE=1"
set "HANRORO_SKIP_CUSTOM_FONTS=1"
call run.cmd --desktop --console
