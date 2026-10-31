@echo off
rem ===========================================================================
rem  Blend Hub - INTERNET LINK (free Cloudflare Tunnel)
rem  Gives the team a https:// web address that works on iPhone/iPad and from
rem  anywhere - no router changes, no company IT, no fixed IP needed.
rem  Run this in a SECOND window, alongside START_TEAM.bat. Keep BOTH open.
rem  The first run downloads cloudflared.exe (~35 MB) once.
rem ===========================================================================
setlocal
title Blend Hub - Internet link (keep open)
cd /d "%~dp0"
set "CF=%~dp0cloudflared.exe"
if not exist "%CF%" (
  echo.
  echo  First time only: downloading the Cloudflare Tunnel tool...
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%CF%' } catch { Write-Host $_; exit 1 }"
  if errorlevel 1 (
    echo.
    echo  Automatic download failed. Download it by hand instead:
    echo    1. Open https://github.com/cloudflare/cloudflared/releases/latest
    echo    2. Download  cloudflared-windows-amd64.exe
    echo    3. Rename it to  cloudflared.exe  and put it in THIS folder
    echo    4. Run START_TUNNEL.bat again
    echo.
    pause & exit /b 1
  )
)
echo.
echo  Starting the internet link. In a few seconds a web address like
echo        https://random-words-1234.trycloudflare.com
echo  will appear below. THAT address is the link you send to your team.
echo  (It stays the same while this window is open. If you close/reopen it,
echo   a new link is created - see TEAM_SETUP for how to make it permanent.)
echo.
echo  Keep BOTH this window and the Blend Hub window open.
echo  ---------------------------------------------------------------
echo.
"%CF%" tunnel --url http://localhost:8765
echo.
echo  The internet link has stopped. Close this window or run it again.
pause
