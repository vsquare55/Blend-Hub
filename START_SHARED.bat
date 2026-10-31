@echo off
rem Starts the Blend Hub so that others on the SAME Wi-Fi / office network can open it in their browser (Mac included).
setlocal
title Blend Hub (shared)
cd /d "%~dp0"
call "%~dp0_python.bat"
if errorlevel 1 (pause & exit /b 1)
set HUB_SHARE=1
echo.
echo  Others open one of these addresses in their browser (same network):
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo     http://%%a:8765
echo  They see everything read-only while you edit. Keep this window open.
echo.
"%PYEXE%" -X utf8 scripts\hubserver.py
pause
