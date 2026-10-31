@echo off
rem Makes a read-only HTML copy of the whole Blend Hub (opens by double-click on a Mac or any PC, no Python needed).
cd /d "%~dp0"
call "%~dp0_python.bat"
if errorlevel 1 (pause & exit /b 1)
"%PYEXE%" -X utf8 scripts\make_snapshot.py
echo.
echo  Done - the new Blend_Hub_Snapshot_<date>.html is in this folder. Send it to anyone.
pause
