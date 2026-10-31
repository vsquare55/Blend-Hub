@echo off
setlocal
title Blend Hub
cd /d "%~dp0"
call "%~dp0_python.bat"
if errorlevel 1 (pause & exit /b 1)
echo.
echo  Blend Hub is starting - it opens in its own window.
echo  Keep THIS window open while you work (closing it stops the Hub).
echo.
"%PYEXE%" -X utf8 scripts\hubserver.py
if errorlevel 1 (echo. & echo  Something went wrong - see the message above. & pause)
