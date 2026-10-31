@echo off
rem ===========================================================================
rem  Blend Hub - TEAM MODE
rem  Runs the Hub so up to ~10 people can sign in and edit at the same time,
rem  from Windows or iPhone/iPad, in the office or anywhere via the tunnel link.
rem  Keep this window OPEN while the team is working (closing it stops the Hub).
rem ===========================================================================
setlocal
title Blend Hub (TEAM - keep open)
cd /d "%~dp0"
call "%~dp0_python.bat"
if errorlevel 1 (pause & exit /b 1)
set HUB_SHARE=1
echo.
echo  ==================== BLEND HUB - TEAM MODE ====================
echo   KEEP THIS WINDOW OPEN. Closing it signs everyone out.
echo.
echo   On THIS computer:            http://localhost:8765
echo.
echo   Same office Wi-Fi can use:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo        http://%%a:8765
echo.
echo   For phones / people OUTSIDE the office (iPhone, home, travel):
echo     open a SECOND window and double-click  START_TUNNEL.bat
echo     - it prints a https://...trycloudflare.com link to send your team.
echo.
echo   The very FIRST time, a master username + password is shown below.
echo   Write it down, sign in, then open "Users" to add your team.
echo  ===============================================================
echo.
"%PYEXE%" -X utf8 scripts\hubserver.py
if errorlevel 1 (echo. & echo  Something went wrong - see the message above. & pause)
