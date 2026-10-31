@echo off
rem ===========================================================================
rem  Blend Hub - INTERNET LINK (free Cloudflare Tunnel)
rem  Gives the team a https:// address that works on iPhone/Android and from
rem  anywhere - no router changes, no company IT, no fixed IP needed.
rem  Keep this window OPEN. The link is also written to LINK.txt in this folder.
rem  First run downloads cloudflared.exe (~35 MB) once.
rem ===========================================================================
setlocal EnableDelayedExpansion
title Blend Hub - Internet link (keep open)
cd /d "%~dp0"
set "CF=%~dp0cloudflared.exe"
if not exist "%CF%" (
  echo.
  echo  First time only: downloading the Cloudflare Tunnel tool...
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%CF%' } catch { Write-Host $_; exit 1 }"
  if errorlevel 1 (
    echo.
    echo  Automatic download failed. Download it by hand:
    echo    1. Open https://github.com/cloudflare/cloudflared/releases/latest
    echo    2. Download cloudflared-windows-amd64.exe
    echo    3. Rename it cloudflared.exe and put it in THIS folder
    echo    4. Run this again
    pause & exit /b 1
  )
)
del "%~dp0LINK.txt" 2>nul
echo.
echo  Starting the internet link... your team address will appear below
echo  (and be saved to LINK.txt) in a few seconds. Keep this window open.
echo  ---------------------------------------------------------------
echo.
rem Run the tunnel; echo every line so you can see it, and grab the https link into LINK.txt
for /f "usebackq delims=" %%L in (`"%CF%" tunnel --url http://localhost:8765 2^>^&1`) do (
  echo %%L
  echo %%L | findstr /c:"trycloudflare.com" >nul && (
    for %%W in (%%L) do (
      echo %%W | findstr /c:"https://" >nul && (
        if not exist "%~dp0LINK.txt" (
          >"%~dp0LINK.txt" echo %%W
          echo.
          echo  ============================================================
          echo    YOUR TEAM LINK  (open on phones + laptops, then sign in):
          echo        %%W
          echo    ^(also saved in LINK.txt in this folder^)
          echo  ============================================================
          echo.
        )
      )
    )
  )
)
echo.
echo  The internet link has stopped. Close this window or run it again.
pause
