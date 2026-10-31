@echo off
rem Stops the Blend Hub that is still running in the background (closing its window does not stop it), then starts the new one.
title Restarting Blend Hub
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'hubserver\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
timeout /t 2 /nobreak >nul
cd /d "%~dp0"
call "%~dp0START_HERE.bat"
