@echo off
setlocal
title Replace base deck
cd /d "%~dp0"
call "%~dp0_python.bat"
if errorlevel 1 (pause & exit /b 1)
echo.
echo  This swaps in a new base deck (EPC or Investor). The old one is archived first,
echo  and nothing changes if the new deck fails the checks.
echo.
"%PYEXE%" -X utf8 scripts\replace_base.py %*
echo.
pause
