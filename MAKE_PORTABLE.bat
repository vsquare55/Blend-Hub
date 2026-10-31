@echo off
setlocal
title Build portable package
cd /d "%~dp0"
call "%~dp0_python.bat"
if errorlevel 1 (pause & exit /b 1)
echo.
echo  Building a self-contained copy (tool + base deck + Excel + private Python)...
echo  Close the base deck and projects_registry.xlsx first if they are open.
echo.
"%PYEXE%" -X utf8 scripts\make_portable.py
echo.
echo  The zip is in the 'dist' folder.
pause
