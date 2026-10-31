@echo off
rem ===========================================================================
rem  Make Blend Hub start by itself whenever this PC logs in to Windows.
rem  Run this ONCE. (To undo, press Win+R, type  shell:startup , delete "Blend Hub".)
rem ===========================================================================
setlocal
cd /d "%~dp0"
set "TARGET=%~dp0BLEND_HUB.bat"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut(\"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Blend Hub.lnk\"); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
if errorlevel 1 ( echo Could not set auto-start. & pause & exit /b 1 )
echo.
echo  Done. Blend Hub will start automatically when this PC logs in.
echo  To stop that later: press Win+R, type  shell:startup  and delete "Blend Hub".
echo.
pause
