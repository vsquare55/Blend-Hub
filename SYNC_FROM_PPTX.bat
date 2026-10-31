@echo off
setlocal
title Sync Excel from base decks
cd /d "%~dp0"
call "%~dp0_python.bat"
if errorlevel 1 (pause & exit /b 1)
echo.
echo  (Optional: close projects_registry.xlsx first so the changes can be saved)
echo.
"%PYEXE%" -X utf8 scripts\sync_registry.py
echo.
pause
