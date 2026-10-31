@echo off
setlocal
title Create Blend DealFlow shortcut
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Blend DealFlow.lnk'); $s.TargetPath='%~dp0START_HERE.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0assets\dealflow_icon.ico'; $s.Description='Blend DealFlow - pipeline, readiness, discussion, counterparties and decks'; $s.WindowStyle=7; $s.Save()"
echo.
echo  A "Blend DealFlow" shortcut (with the DealFlow icon) is now on your Desktop.
echo  If you move this folder, run this file again.
pause
