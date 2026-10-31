@echo off
rem ===========================================================================
rem  BLEND HUB - START EVERYTHING (one double-click)
rem  Opens the Hub for your team and the internet link, then shows the web
rem  address to share. This is the ONLY file you need to run each morning.
rem ===========================================================================
setlocal EnableDelayedExpansion
title Blend Hub - start everything
cd /d "%~dp0"
echo.
echo   Starting Blend Hub for your team. Two helper windows will open -
echo   leave them ALL open while people are using the Hub.
echo.

rem 1) The Hub server (in its own window)
start "Blend Hub SERVER (keep open)" "%~dp0START_TEAM.bat"

rem 2) The internet link (in its own window) - writes LINK.txt when ready
start "Blend Hub INTERNET LINK (keep open)" "%~dp0START_TUNNEL.bat"

rem 3) Wait for the link, then show it big and open it here
del "%~dp0LINK.txt" 2>nul
echo   Preparing your shareable link (usually 5-15 seconds)...
set "URL="
for /l %%i in (1,1,60) do (
  if not defined URL (
    if exist "%~dp0LINK.txt" ( set /p URL=<"%~dp0LINK.txt" )
    if not defined URL ( timeout /t 1 >nul )
  )
)
echo.
if defined URL (
  echo  ================================================================
  echo    SHARE THIS LINK with your team (phones + laptops), then sign in:
  echo.
  echo         !URL!
  echo.
  echo    It is saved in LINK.txt in this folder, too.
  echo  ================================================================
  start "" "!URL!"
) else (
  echo  Could not read the link automatically yet. Look in the window titled
  echo  "Blend Hub INTERNET LINK" for a https://...trycloudflare.com address,
  echo  or open LINK.txt in this folder once it appears.
)
echo.
echo  Setup done. You can minimise the windows, but do not close them.
echo  (To have this start by itself after a reboot, run INSTALL_AUTOSTART.bat once.)
echo.
pause
